"""Ending a conversation, the short note kept from it, and the sweep that ends idle
ones.

The note is private to the member it is about. It can hold what they said about
themselves, so nothing here logs it, and it is never a source for an answer.
"""

import asyncio
import logging
import uuid
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import text, update
from sqlmodel import Session, col, delete, select
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.db import engine
from app.core.llm import LLMClient, LLMError, get_llm_client
from app.core.prompt import SUMMARY_SYSTEM_PROMPT, SUMMARY_USER_PROMPT
from app.models import (
    Conversation,
    ConversationMessage,
    ConversationStatus,
    ConversationSummary,
    MessageRole,
    Person,
    PersonMember,
)

logger = logging.getLogger(__name__)

SUMMARY_MAX_CHARS = 2000
# Arbitrary app-specific key so only one worker sweeps at a time
SWEEP_LOCK_KEY = 7_424_216_154


def get_summary(
    session: Session, person_id: uuid.UUID, user_id: uuid.UUID
) -> ConversationSummary | None:
    return session.exec(
        select(ConversationSummary).where(
            col(ConversationSummary.person_id) == person_id,
            col(ConversationSummary.user_id) == user_id,
        )
    ).first()


def delete_person_summaries(session: Session, person_id: uuid.UUID) -> None:
    """Drop every member's summary for a person. A summary may repeat a fact that was
    just deleted, rejected or corrected, so none of them can be trusted any more.
    The caller commits."""
    session.exec(
        delete(ConversationSummary).where(
            col(ConversationSummary.person_id) == person_id
        )
    )


def may_talk_with(session: Session, person_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    """Whether the user is the person's owner or one of its members."""
    owner_id = session.exec(
        select(Person.owner_id).where(col(Person.id) == person_id)
    ).first()
    if owner_id is None:
        return False
    if owner_id == user_id:
        return True
    return (
        session.exec(
            select(PersonMember.id).where(
                col(PersonMember.person_id) == person_id,
                col(PersonMember.user_id) == user_id,
            )
        ).first()
        is not None
    )


def end_member_conversations(
    session: Session, person_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """End a member's open conversations with a person without a summary, and delete
    their messages. No model call; the caller commits, together with whatever else
    the revoke changes, so no half-revoked state can be left behind."""
    # End first: the update takes the row locks a reply being saved also needs, so
    # that reply waits, then sees an ended conversation and is dropped. Deleting the
    # messages of every conversation of the pair afterwards leaves nothing behind.
    session.exec(
        update(Conversation)
        .where(
            col(Conversation.person_id) == person_id,
            col(Conversation.user_id) == user_id,
            col(Conversation.status) == ConversationStatus.OPEN,
        )
        .values(status=ConversationStatus.ENDED, ended_at=datetime.now(UTC))
    )
    pair_ids = select(Conversation.id).where(
        col(Conversation.person_id) == person_id,
        col(Conversation.user_id) == user_id,
    )
    session.exec(
        delete(ConversationMessage).where(
            col(ConversationMessage.conversation_id).in_(pair_ids)
        )
    )


def format_transcript(messages: Sequence[ConversationMessage]) -> str:
    """The family member's own messages for the summary prompt, one per line. The AI's
    replies stay out: the note is about what the member said, and a model that sees
    the replies starts writing about the AI and the remembered person instead."""
    return "\n".join(
        f"Family member: {' '.join(message.content.split())}"
        for message in messages
        if message.role == MessageRole.USER
    )


def continues_the_dialogue(note: str) -> bool:
    """Whether the model wrote more turns instead of a note. That is made-up
    conversation, and keeping it would put words in the member's mouth."""
    return any(
        line.strip().lower().startswith(("family member:", "ai:"))
        for line in note.splitlines()
    )


def end_conversation(
    session: Session,
    llm: LLMClient,
    conversation: Conversation,
    *,
    only_if_quiet: bool = False,
) -> bool:
    """End a conversation: keep a summary of it when something was said, then delete
    its messages. The conversation ends even when the model is down: deleting the chat
    matters more than keeping a note of it.

    With `only_if_quiet` (the idle sweep) it is left open if someone wrote in it while
    the summary was being written. Returns whether this call ended it."""
    if conversation.status != ConversationStatus.OPEN:
        return False
    last_message_at = conversation.last_message_at
    conversation_id = conversation.id
    person_id = conversation.person_id
    user_id = conversation.user_id
    messages = list(
        session.exec(
            select(ConversationMessage)
            .where(col(ConversationMessage.conversation_id) == conversation_id)
            .order_by(col(ConversationMessage.created_at), col(ConversationMessage.id))
        ).all()
    )
    said_something = any(m.role == MessageRole.USER for m in messages)

    summary_text: str | None = None
    # Which note the new one is built on, to notice if it changes during the model call
    based_on: tuple[uuid.UUID, datetime] | None = None
    if said_something:
        previous = get_summary(session, person_id, user_id)
        if previous:
            based_on = (previous.id, previous.updated_at)
        prompt = SUMMARY_USER_PROMPT.format(
            previous=previous.content if previous else "(none)",
            transcript=format_transcript(messages),
        )
        # Nothing may hold a database connection while the model works
        session.rollback()
        try:
            summary_text = llm.answer(SUMMARY_SYSTEM_PROMPT, prompt).strip()
            if continues_the_dialogue(summary_text):
                logger.warning(
                    "summary dropped, it continued the dialogue: conversation=%s",
                    conversation_id,
                )
                summary_text = None
            summary_text = (summary_text or "")[:SUMMARY_MAX_CHARS] or None
        except LLMError:
            logger.warning("summary not written: conversation=%s", conversation_id)

    # Reload under a row lock: the member or the sweep may have ended it meanwhile
    locked = session.exec(
        select(Conversation)
        .where(col(Conversation.id) == conversation_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if locked is None or locked.status != ConversationStatus.OPEN:
        session.rollback()
        return False
    if only_if_quiet and locked.last_message_at != last_message_at:
        session.rollback()
        return False
    if summary_text and not may_talk_with(session, person_id, user_id):
        # Access was taken away after this conversation was opened (a revoke racing
        # the open): a revoked member must not get a summary written
        summary_text = None
    existing = get_summary(session, person_id, user_id)
    current = (existing.id, existing.updated_at) if existing else None
    if summary_text and current != based_on:
        # The note it was built on was deleted (a memory it rested on changed) or
        # replaced while the model worked; writing the new one would bring it back
        logger.info(
            "summary dropped, it was out of date: conversation=%s", conversation_id
        )
        summary_text = None
    if summary_text:
        if existing:
            existing.content = summary_text
            existing.updated_at = datetime.now(UTC)
            session.add(existing)
        else:
            session.add(
                ConversationSummary(
                    person_id=person_id, user_id=user_id, content=summary_text
                )
            )
    locked.status = ConversationStatus.ENDED
    locked.ended_at = datetime.now(UTC)
    session.add(locked)
    session.exec(
        delete(ConversationMessage).where(
            col(ConversationMessage.conversation_id) == conversation_id
        )
    )
    session.commit()
    logger.info(
        "conversation ended: conversation=%s turns=%s summarized=%s",
        conversation_id,
        len(messages),
        bool(summary_text),
    )
    return True


def end_idle_conversations(
    session: Session, llm: LLMClient, now: datetime | None = None
) -> int:
    """End every open conversation nobody has written in for
    `CONVERSATION_IDLE_MINUTES`; returns how many were ended."""
    cutoff = (now or datetime.now(UTC)) - timedelta(
        minutes=settings.CONVERSATION_IDLE_MINUTES
    )
    idle_ids = session.exec(
        select(Conversation.id).where(
            col(Conversation.status) == ConversationStatus.OPEN,
            col(Conversation.last_message_at) < cutoff,
        )
    ).all()
    ended = 0
    for conversation_id in idle_ids:
        try:
            conversation = session.get(Conversation, conversation_id)
            if conversation is not None and end_conversation(
                session, llm, conversation, only_if_quiet=True
            ):
                ended += 1
        except Exception as exc:
            # One broken conversation must not stop the others; the error text
            # can quote database values, so only its type is logged
            logger.warning(
                "idle end failed: conversation=%s error=%s",
                conversation_id,
                type(exc).__name__,
            )
            session.rollback()
    return ended


def sweep_once() -> int:
    """One pass over idle conversations. A held advisory lock makes sure only one
    worker does it at a time; the others skip the pass."""
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as lock:
        locked = lock.execute(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": SWEEP_LOCK_KEY}
        ).scalar()
        if not locked:
            return 0
        try:
            with Session(engine) as session:
                return end_idle_conversations(session, get_llm_client())
        finally:
            lock.execute(
                text("SELECT pg_advisory_unlock(:key)"), {"key": SWEEP_LOCK_KEY}
            )


async def run_idle_sweep(
    interval: float | None = None, once: Callable[[], int] = sweep_once
) -> None:
    """Run `once` every `interval` seconds until cancelled; a failed pass is logged
    and the next one still happens."""
    wait = settings.CONVERSATION_SWEEP_SECONDS if interval is None else interval
    while True:
        await asyncio.sleep(wait)
        try:
            await run_in_threadpool(once)
        except Exception as exc:
            logger.warning("idle sweep failed: error=%s", type(exc).__name__)
