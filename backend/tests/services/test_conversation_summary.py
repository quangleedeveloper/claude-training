import asyncio
import contextlib
import logging
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlmodel import Session, col, func, select

from app.core.config import settings
from app.core.db import engine
from app.core.prompt import PERSONA_NOTICE
from app.models import (
    Conversation,
    ConversationMessage,
    ConversationStatus,
    ConversationSummary,
    MessageRole,
    Person,
)
from app.services import conversation_summary
from app.services.conversation_summary import (
    SWEEP_LOCK_KEY,
    end_conversation,
    end_idle_conversations,
    get_summary,
    run_idle_sweep,
    sweep_once,
)
from tests.utils.conversation import (
    add_message,
    create_random_conversation,
    create_random_summary,
)
from tests.utils.llm import FakeLLMClient

GARDEN = "Tell me about the garden"


def talked(db: Session, conversation: Conversation) -> None:
    add_message(db, conversation, MessageRole.USER, GARDEN)
    add_message(db, conversation, MessageRole.PERSONA, "It was lovely.")


def messages_left(db: Session, conversation_id: object) -> int:
    db.expire_all()
    return db.exec(
        select(func.count())
        .select_from(ConversationMessage)
        .where(col(ConversationMessage.conversation_id) == conversation_id)
    ).one()


def backdate(db: Session, conversation: Conversation, minutes: int) -> None:
    conversation.last_message_at = datetime.now(UTC) - timedelta(minutes=minutes)
    db.add(conversation)
    db.commit()


def test_end_conversation_saves_summary(db: Session, llm_client: FakeLLMClient) -> None:
    conversation = create_random_conversation(db)
    talked(db, conversation)
    person_id, user_id, conversation_id = (
        conversation.person_id,
        conversation.user_id,
        conversation.id,
    )

    end_conversation(db, llm_client, conversation)

    (prompt,) = llm_client.answer_prompts
    assert f"Family member: {GARDEN}" in prompt
    assert "AI: It was lovely." in prompt
    assert PERSONA_NOTICE not in prompt
    summary = get_summary(db, person_id, user_id)
    assert summary is not None
    assert summary.content == "Fake answer citing [1]."
    db.expire_all()
    ended = db.get(Conversation, conversation_id)
    assert ended is not None
    assert ended.status == ConversationStatus.ENDED
    assert ended.ended_at is not None
    assert messages_left(db, conversation_id) == 0


def test_end_replaces_previous_summary(db: Session, llm_client: FakeLLMClient) -> None:
    conversation = create_random_conversation(db)
    person = db.get(Person, conversation.person_id)
    assert person is not None
    create_random_summary(db, person, content="Earlier they spoke about the boat.")
    talked(db, conversation)
    person_id, user_id = conversation.person_id, conversation.user_id

    end_conversation(db, llm_client, conversation)

    assert "Earlier they spoke about the boat." in llm_client.answer_prompts[0]
    db.expire_all()
    rows = db.exec(
        select(ConversationSummary).where(
            col(ConversationSummary.person_id) == person_id,
            col(ConversationSummary.user_id) == user_id,
        )
    ).all()
    assert [row.content for row in rows] == ["Fake answer citing [1]."]


def test_summary_cut_to_2000(
    db: Session, llm_client: FakeLLMClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(llm_client, "answer", lambda system, prompt: "x" * 3000)  # noqa: ARG005
    conversation = create_random_conversation(db)
    talked(db, conversation)
    person_id, user_id = conversation.person_id, conversation.user_id

    end_conversation(db, llm_client, conversation)

    summary = get_summary(db, person_id, user_id)
    assert summary is not None
    assert len(summary.content) == 2000


def test_end_without_turns_writes_no_summary_and_calls_no_model(
    db: Session, llm_client: FakeLLMClient
) -> None:
    conversation = create_random_conversation(db)
    person_id, user_id, conversation_id = (
        conversation.person_id,
        conversation.user_id,
        conversation.id,
    )

    end_conversation(db, llm_client, conversation)

    assert llm_client.answer_prompts == []
    assert get_summary(db, person_id, user_id) is None
    db.expire_all()
    ended = db.get(Conversation, conversation_id)
    assert ended is not None
    assert ended.status == ConversationStatus.ENDED
    assert messages_left(db, conversation_id) == 0


def test_end_when_model_down_still_ends_and_keeps_old_summary(
    db: Session, llm_client: FakeLLMClient
) -> None:
    conversation = create_random_conversation(db)
    owner_person = db.get(Person, conversation.person_id)
    assert owner_person is not None
    create_random_summary(db, owner_person, content="Kept note.")
    talked(db, conversation)
    person_id, user_id, conversation_id = (
        conversation.person_id,
        conversation.user_id,
        conversation.id,
    )
    llm_client.error = "down"

    end_conversation(db, llm_client, conversation)

    summary = get_summary(db, person_id, user_id)
    assert summary is not None
    assert summary.content == "Kept note."
    db.expire_all()
    ended = db.get(Conversation, conversation_id)
    assert ended is not None
    assert ended.status == ConversationStatus.ENDED
    assert messages_left(db, conversation_id) == 0


def test_ending_twice_summarizes_once(db: Session, llm_client: FakeLLMClient) -> None:
    conversation = create_random_conversation(db)
    talked(db, conversation)

    end_conversation(db, llm_client, conversation)
    db.refresh(conversation)
    end_conversation(db, llm_client, conversation)

    assert len(llm_client.answer_prompts) == 1


def test_idle_sweep_ends_and_summarizes_old_conversations(
    db: Session, llm_client: FakeLLMClient
) -> None:
    idle = create_random_conversation(db)
    talked(db, idle)
    backdate(db, idle, settings.CONVERSATION_IDLE_MINUTES + 1)
    fresh = create_random_conversation(db)
    talked(db, fresh)
    idle_id, fresh_id = idle.id, fresh.id
    idle_person, idle_user = idle.person_id, idle.user_id

    ended = end_idle_conversations(db, llm_client)

    assert ended >= 1
    db.expire_all()
    idle_after = db.get(Conversation, idle_id)
    fresh_after = db.get(Conversation, fresh_id)
    assert idle_after is not None
    assert fresh_after is not None
    assert idle_after.status == ConversationStatus.ENDED
    assert fresh_after.status == ConversationStatus.OPEN
    assert get_summary(db, idle_person, idle_user) is not None
    assert messages_left(db, fresh_id) == 3


def test_idle_sweep_skips_ended_conversations(
    db: Session, llm_client: FakeLLMClient
) -> None:
    conversation = create_random_conversation(db)
    talked(db, conversation)
    end_conversation(db, llm_client, conversation)
    db.refresh(conversation)
    backdate(db, conversation, settings.CONVERSATION_IDLE_MINUTES + 5)
    calls = len(llm_client.answer_prompts)

    end_idle_conversations(db, llm_client)

    assert len(llm_client.answer_prompts) == calls


def test_idle_sweep_keeps_going_after_one_failure(
    db: Session, llm_client: FakeLLMClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    broken = create_random_conversation(db)
    working = create_random_conversation(db)
    for conversation in (broken, working):
        talked(db, conversation)
        backdate(db, conversation, settings.CONVERSATION_IDLE_MINUTES + 1)
    broken_id, working_id = broken.id, working.id
    real_end = conversation_summary.end_conversation

    def flaky(session: Session, llm: FakeLLMClient, conversation: Conversation) -> None:
        if conversation.id == broken_id:
            raise RuntimeError("secret story text")
        real_end(session, llm, conversation)

    monkeypatch.setattr(conversation_summary, "end_conversation", flaky)

    end_idle_conversations(db, llm_client)

    db.expire_all()
    after = db.get(Conversation, working_id)
    assert after is not None
    assert after.status == ConversationStatus.ENDED


def test_summary_and_transcript_are_not_logged(
    db: Session, llm_client: FakeLLMClient, caplog: pytest.LogCaptureFixture
) -> None:
    secret = "my private worry about the surgery"
    conversation = create_random_conversation(db)
    add_message(db, conversation, MessageRole.USER, secret)
    conversation_id = str(conversation.id)

    with caplog.at_level(logging.DEBUG):
        end_conversation(db, llm_client, conversation)

    assert conversation_id in caplog.text
    assert secret not in caplog.text
    assert "Fake answer citing" not in caplog.text


def test_sweep_once_ends_idle_conversations(
    db: Session, llm_client: FakeLLMClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(conversation_summary, "get_llm_client", lambda: llm_client)
    conversation = create_random_conversation(db)
    talked(db, conversation)
    backdate(db, conversation, settings.CONVERSATION_IDLE_MINUTES + 1)
    conversation_id = conversation.id

    assert sweep_once() >= 1

    db.expire_all()
    after = db.get(Conversation, conversation_id)
    assert after is not None
    assert after.status == ConversationStatus.ENDED


def test_sweep_once_skips_when_another_worker_is_sweeping(
    db: Session, llm_client: FakeLLMClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(conversation_summary, "get_llm_client", lambda: llm_client)
    conversation = create_random_conversation(db)
    talked(db, conversation)
    backdate(db, conversation, settings.CONVERSATION_IDLE_MINUTES + 1)
    conversation_id = conversation.id

    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as other:
        other.execute(text("SELECT pg_advisory_lock(:key)"), {"key": SWEEP_LOCK_KEY})
        try:
            assert sweep_once() == 0
        finally:
            other.execute(
                text("SELECT pg_advisory_unlock(:key)"), {"key": SWEEP_LOCK_KEY}
            )

    db.expire_all()
    after = db.get(Conversation, conversation_id)
    assert after is not None
    assert after.status == ConversationStatus.OPEN
    end_conversation(db, llm_client, after)


def test_sweep_loop_survives_a_failed_pass() -> None:
    calls: list[int] = []

    def once() -> int:
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")
        return 0

    async def main() -> None:
        task = asyncio.create_task(run_idle_sweep(0.01, once))
        while len(calls) < 3:
            await asyncio.sleep(0.01)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    asyncio.run(asyncio.wait_for(main(), timeout=10))

    assert len(calls) >= 3
