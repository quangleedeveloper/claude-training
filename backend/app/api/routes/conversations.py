import json
import logging
import time
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from sqlmodel import Session, col, delete, func, select

from app.api.deps import CurrentUser, LLMClientDep, SessionDep
from app.api.routes.persons import get_person_for_conversation
from app.core.db import engine
from app.core.llm import LLMClient, LLMError
from app.core.prompt import PERSONA_NOTICE
from app.models import (
    Conversation,
    ConversationMessage,
    ConversationOpened,
    ConversationStatus,
    Message,
    MessageRole,
    PersonaTurn,
    SendMessageRequest,
    User,
)
from app.services import persona_graph
from app.services.persona_events import DoneEvent, TokenEvent

router = APIRouter(tags=["conversations"])
logger = logging.getLogger(__name__)

GENERIC_ERROR = "The AI service is unavailable."


def get_conversation_or_error(
    session: Session, user: User, conversation_id: uuid.UUID
) -> Conversation:
    """Return the caller's own conversation; nobody else reaches it, superusers
    included."""
    conversation = session.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conversation.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return conversation


def server_event(name: str, data: dict[str, Any]) -> str:
    return f"event: {name}\ndata: {json.dumps(jsonable_encoder(data))}\n\n"


def elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


@router.post("/persons/{person_id}/conversations", response_model=ConversationOpened)
def open_conversation(
    session: SessionDep, current_user: CurrentUser, person_id: uuid.UUID
) -> Any:
    """
    Open a conversation with a person's persona; the first message is the notice.
    """
    get_person_for_conversation(session, current_user, person_id)
    conversation = Conversation(person_id=person_id, user_id=current_user.id)
    session.add(conversation)
    session.add(
        ConversationMessage(
            conversation_id=conversation.id,
            role=MessageRole.PERSONA,
            content=PERSONA_NOTICE,
        )
    )
    session.commit()
    logger.info("conversation opened: conversation=%s", conversation.id)
    return ConversationOpened(conversation_id=conversation.id, notice=PERSONA_NOTICE)


def stream_turn(
    llm: LLMClient,
    *,
    conversation_id: uuid.UUID,
    person_id: uuid.UUID,
    person_name: str,
    history: list[ConversationMessage],
    text: str,
    turn_number: int,
) -> Iterator[str]:
    """Server-sent events for one turn. It opens its own session: the request's may
    be closed before a streamed body ends, and none may stay open while the model
    runs."""
    started = time.perf_counter()
    first_token_ms: int | None = None
    parts: list[str] = []
    with Session(engine) as session:
        try:
            for event in persona_graph.reply(
                session,
                llm,
                person_id=person_id,
                person_name=person_name,
                history=history,
                message=text,
            ):
                if isinstance(event, TokenEvent):
                    if first_token_ms is None:
                        first_token_ms = elapsed_ms(started)
                    parts.append(event.text)
                    yield server_event("token", {"text": event.text})
                elif isinstance(event, DoneEvent):
                    total_ms = elapsed_ms(started)
                    # The user may have ended the conversation while this reply was
                    # streaming. Ending deletes the messages, so a reply saved after
                    # that would outlive it; the lock makes the check and the insert
                    # one step against `end_conversation`.
                    still_open = session.exec(
                        select(Conversation.status)
                        .where(col(Conversation.id) == conversation_id)
                        .with_for_update()
                    ).first()
                    if still_open == ConversationStatus.OPEN:
                        session.add(
                            ConversationMessage(
                                conversation_id=conversation_id,
                                role=MessageRole.PERSONA,
                                content="".join(parts),
                            )
                        )
                    session.add(
                        PersonaTurn(
                            conversation_id=conversation_id,
                            item_ids=[str(hit.item.id) for hit in event.sources],
                            fallback=event.fallback,
                            first_token_ms=first_token_ms,
                            total_ms=total_ms,
                        )
                    )
                    session.commit()
                    logger.info(
                        "persona turn: conversation=%s turn=%s sources=%s "
                        "fallback=%s first_token_ms=%s total_ms=%s",
                        conversation_id,
                        turn_number,
                        len(event.sources),
                        event.fallback,
                        first_token_ms,
                        total_ms,
                    )
                    yield server_event(
                        "done",
                        {
                            "sources": event.sources,
                            "fallback": event.fallback,
                            "notice": PERSONA_NOTICE,
                            "cited_ids": event.cited_ids,
                            "invalid_citations": event.invalid_citations,
                            "uncited": event.uncited,
                        },
                    )
        except Exception as exc:
            # Only the type: the message of a failure can quote the user's text
            logger.warning(
                "persona turn failed: conversation=%s turn=%s error=%s",
                conversation_id,
                turn_number,
                type(exc).__name__,
            )
            session.rollback()
            detail = str(exc) if isinstance(exc, LLMError) else GENERIC_ERROR
            yield server_event("error", {"detail": detail})


@router.post("/conversations/{conversation_id}/messages")
def send_message(
    session: SessionDep,
    current_user: CurrentUser,
    llm: LLMClientDep,
    conversation_id: uuid.UUID,
    message_in: SendMessageRequest,
) -> StreamingResponse:
    """
    Send a message and stream the persona's reply as server-sent events.
    """
    conversation = get_conversation_or_error(session, current_user, conversation_id)
    if conversation.status != ConversationStatus.OPEN:
        raise HTTPException(status_code=409, detail="Conversation has ended")
    # Checked on every message so access taken away later stops a running chat
    person = get_person_for_conversation(session, current_user, conversation.person_id)
    history = list(
        session.exec(
            select(ConversationMessage)
            .where(col(ConversationMessage.conversation_id) == conversation.id)
            .order_by(col(ConversationMessage.created_at), col(ConversationMessage.id))
        ).all()
    )
    turn_number = (
        session.exec(
            select(func.count())
            .select_from(ConversationMessage)
            .where(
                col(ConversationMessage.conversation_id) == conversation.id,
                col(ConversationMessage.role) == MessageRole.USER,
            )
        ).one()
        + 1
    )
    person_id, person_name = person.id, person.name
    for earlier in history:
        session.expunge(earlier)
    session.add(
        ConversationMessage(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content=message_in.text,
        )
    )
    conversation.last_message_at = datetime.now(UTC)
    session.add(conversation)
    session.commit()
    return StreamingResponse(
        stream_turn(
            llm,
            conversation_id=conversation_id,
            person_id=person_id,
            person_name=person_name,
            history=history,
            text=message_in.text,
            turn_number=turn_number,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/conversations/{conversation_id}/end", response_model=Message)
def end_conversation(
    session: SessionDep, current_user: CurrentUser, conversation_id: uuid.UUID
) -> Any:
    """
    End a conversation and delete its messages. Ending twice is harmless.
    """
    conversation = get_conversation_or_error(session, current_user, conversation_id)
    if conversation.status == ConversationStatus.OPEN:
        # MR-106 saves the summary here, before the messages are deleted
        conversation.status = ConversationStatus.ENDED
        conversation.ended_at = datetime.now(UTC)
        session.add(conversation)
        session.exec(
            delete(ConversationMessage).where(
                col(ConversationMessage.conversation_id) == conversation.id
            )
        )
        session.commit()
        logger.info("conversation ended: conversation=%s", conversation.id)
    return Message(message="Conversation ended")
