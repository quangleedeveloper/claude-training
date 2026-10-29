import json
import logging
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, col, func, select

from app import crud
from app.core.config import settings
from app.core.llm import LLMError
from app.core.prompt import PERSONA_NO_MEMORY, PERSONA_NOTICE
from app.models import (
    Conversation,
    ConversationMessage,
    ConversationStatus,
    ExtractedMemoryPublic,
    MessageRole,
    Person,
    PersonaTurn,
    SearchHit,
    User,
)
from app.services import persona_events
from app.services.persona_events import DoneEvent, PersonaEvent, TokenEvent
from tests.utils.conversation import create_random_conversation
from tests.utils.extracted_memory import create_random_extracted_memory
from tests.utils.memory import create_random_memory
from tests.utils.person import create_random_person
from tests.utils.user import create_random_user

API = settings.API_V1_STR
TEXT = "Tell me about the garden"


def get_normal_user(db: Session) -> User:
    user = crud.get_user_by_email(session=db, email=settings.EMAIL_TEST_USER)
    assert user is not None
    return user


def messages_url(conversation: Conversation) -> str:
    return f"{API}/conversations/{conversation.id}/messages"


def end_url(conversation: Conversation) -> str:
    return f"{API}/conversations/{conversation.id}/end"


def open_url(person: Person) -> str:
    return f"{API}/persons/{person.id}/conversations"


def parse_events(body: str) -> list[tuple[str, dict[str, Any]]]:
    events = []
    for block in body.strip().split("\n\n"):
        name_line, data_line = block.split("\n")
        events.append(
            (
                name_line.removeprefix("event: "),
                json.loads(data_line.removeprefix("data: ")),
            )
        )
    return events


def stored_messages(db: Session, conversation: Conversation) -> list[tuple[str, str]]:
    db.expire_all()
    rows = db.exec(
        select(ConversationMessage)
        .where(col(ConversationMessage.conversation_id) == conversation.id)
        .order_by(col(ConversationMessage.created_at), col(ConversationMessage.id))
    ).all()
    return [(row.role, row.content) for row in rows]


def turns(db: Session, conversation: Conversation) -> list[PersonaTurn]:
    db.expire_all()
    return list(
        db.exec(
            select(PersonaTurn).where(
                col(PersonaTurn.conversation_id) == conversation.id
            )
        ).all()
    )


def script_reply(monkeypatch: pytest.MonkeyPatch, events: list[PersonaEvent]) -> None:
    def scripted(*_args: Any, **_kwargs: Any) -> Iterator[PersonaEvent]:
        yield from events

    monkeypatch.setattr(persona_events, "reply", scripted)


def own_person(db: Session) -> Person:
    return create_random_person(db, owner=get_normal_user(db))


def own_conversation(db: Session) -> Conversation:
    return create_random_conversation(db, person=own_person(db))


def test_open_conversation(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    person = own_person(db)
    response = client.post(open_url(person), headers=normal_user_token_headers)

    assert response.status_code == 200
    content = response.json()
    assert content["notice"] == PERSONA_NOTICE
    conversation = db.get(Conversation, uuid.UUID(content["conversation_id"]))
    assert conversation is not None
    assert conversation.status == ConversationStatus.OPEN
    assert conversation.person_id == person.id
    assert conversation.user_id == get_normal_user(db).id
    assert stored_messages(db, conversation) == [(MessageRole.PERSONA, PERSONA_NOTICE)]


def test_open_conversation_person_not_found(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{API}/persons/{uuid.uuid4()}/conversations",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Person not found"


def test_open_conversation_outsider_forbidden(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    person = create_random_person(db)
    response = client.post(open_url(person), headers=normal_user_token_headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"
    count = db.exec(
        select(func.count())
        .select_from(Conversation)
        .where(col(Conversation.person_id) == person.id)
    ).one()
    assert count == 0


def test_send_message_streams_tokens_then_done(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    conversation = own_conversation(db)
    response = client.post(
        messages_url(conversation),
        headers=normal_user_token_headers,
        json={"text": TEXT},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = parse_events(response.text)
    assert [name for name, _ in events] == ["token", "done"]
    assert events[0][1] == {"text": PERSONA_NO_MEMORY}
    done = events[1][1]
    assert done["sources"] == []
    assert done["fallback"] is True
    assert done["notice"] == PERSONA_NOTICE
    assert done["cited_ids"] == []
    assert done["invalid_citations"] == []
    assert done["uncited"] is False
    assert stored_messages(db, conversation) == [
        (MessageRole.PERSONA, PERSONA_NOTICE),
        (MessageRole.USER, TEXT),
        (MessageRole.PERSONA, PERSONA_NO_MEMORY),
    ]


def test_send_message_passes_earlier_turns_to_the_reply(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation = own_conversation(db)
    seen: list[dict[str, Any]] = []

    def recording(*_args: Any, **kwargs: Any) -> Iterator[PersonaEvent]:
        seen.append(
            {**kwargs, "history": [(m.role, m.content) for m in kwargs["history"]]}
        )
        yield TokenEvent("ok")
        yield DoneEvent(sources=[], fallback=True)

    monkeypatch.setattr(persona_events, "reply", recording)
    for text in ("first", "second"):
        client.post(
            messages_url(conversation),
            headers=normal_user_token_headers,
            json={"text": text},
        )

    assert seen[0]["message"] == "first"
    assert seen[0]["history"] == [(MessageRole.PERSONA, PERSONA_NOTICE)]
    assert seen[1]["message"] == "second"
    assert seen[1]["history"] == [
        (MessageRole.PERSONA, PERSONA_NOTICE),
        (MessageRole.USER, "first"),
        (MessageRole.PERSONA, "ok"),
    ]
    assert seen[1]["person_id"] == conversation.person_id


def test_send_message_conversation_not_found(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{API}/conversations/{uuid.uuid4()}/messages",
        headers=normal_user_token_headers,
        json={"text": TEXT},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation not found"


def test_send_message_other_users_conversation_forbidden(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    conversation = create_random_conversation(db)
    response = client.post(
        messages_url(conversation),
        headers=normal_user_token_headers,
        json={"text": TEXT},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"
    assert stored_messages(db, conversation) == [(MessageRole.PERSONA, PERSONA_NOTICE)]


def test_send_message_after_person_changed_hands_forbidden(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    conversation = own_conversation(db)
    person = db.get(Person, conversation.person_id)
    assert person is not None
    person.owner_id = create_random_user(db).id
    db.add(person)
    db.commit()

    response = client.post(
        messages_url(conversation),
        headers=normal_user_token_headers,
        json={"text": TEXT},
    )
    assert response.status_code == 403


def test_send_message_ended_conversation(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    conversation = own_conversation(db)
    client.post(end_url(conversation), headers=normal_user_token_headers)

    response = client.post(
        messages_url(conversation),
        headers=normal_user_token_headers,
        json={"text": TEXT},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Conversation has ended"


@pytest.mark.parametrize("text", ["", "x" * 2001])
def test_send_message_invalid_text(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
    text: str,
) -> None:
    conversation = own_conversation(db)
    response = client.post(
        messages_url(conversation),
        headers=normal_user_token_headers,
        json={"text": text},
    )
    assert response.status_code == 422
    assert stored_messages(db, conversation) == [(MessageRole.PERSONA, PERSONA_NOTICE)]


def test_superuser_no_access_to_conversations(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    person = own_person(db)
    conversation = create_random_conversation(db, person=person)

    assert (
        client.post(open_url(person), headers=superuser_token_headers).status_code
        == 403
    )
    assert (
        client.post(
            messages_url(conversation),
            headers=superuser_token_headers,
            json={"text": TEXT},
        ).status_code
        == 403
    )
    assert (
        client.post(end_url(conversation), headers=superuser_token_headers).status_code
        == 403
    )
    db.refresh(conversation)
    assert conversation.status == ConversationStatus.OPEN


def test_turn_writes_audit_row_without_text(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation = own_conversation(db)
    memory = create_random_memory(db, owner=get_normal_user(db))
    item = create_random_extracted_memory(db, memory=memory)
    hit = SearchHit(
        item=ExtractedMemoryPublic.model_validate(item),
        memory_title=memory.title,
        person_name=memory.person_name,
        score=0.9,
    )
    script_reply(
        monkeypatch,
        [
            TokenEvent("She grew "),
            TokenEvent("roses [1]."),
            DoneEvent(sources=[hit], fallback=False, cited_ids=[item.id]),
        ],
    )

    response = client.post(
        messages_url(conversation),
        headers=normal_user_token_headers,
        json={"text": TEXT},
    )

    events = parse_events(response.text)
    assert [name for name, _ in events] == ["token", "token", "done"]
    done = events[2][1]
    assert done["sources"][0]["item"]["id"] == str(item.id)
    assert done["fallback"] is False
    assert done["cited_ids"] == [str(item.id)]
    (turn,) = turns(db, conversation)
    assert turn.item_ids == [str(item.id)]
    assert turn.fallback is False
    assert turn.first_token_ms is not None
    assert turn.total_ms is not None
    assert turn.total_ms >= turn.first_token_ms
    # The audit row has no column that could hold what was said
    assert set(PersonaTurn.model_fields) == {
        "id",
        "conversation_id",
        "item_ids",
        "fallback",
        "first_token_ms",
        "total_ms",
        "created_at",
    }
    assert stored_messages(db, conversation)[-1] == (
        MessageRole.PERSONA,
        "She grew roses [1].",
    )


def test_turn_logs_hold_no_text(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
    caplog: pytest.LogCaptureFixture,
) -> None:
    conversation = own_conversation(db)
    secret = "my mother's secret recipe"
    with caplog.at_level(logging.DEBUG):
        client.post(
            messages_url(conversation),
            headers=normal_user_token_headers,
            json={"text": secret},
        )

    assert str(conversation.id) in caplog.text
    assert "persona turn" in caplog.text
    assert secret not in caplog.text
    assert PERSONA_NO_MEMORY not in caplog.text


@pytest.mark.parametrize(
    ("error", "detail"),
    [
        (LLMError("The AI service is unavailable."), "The AI service is unavailable."),
        (RuntimeError("secret story text"), "The AI service is unavailable."),
    ],
)
def test_send_message_model_error_streams_generic_error(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    error: Exception,
    detail: str,
) -> None:
    conversation = own_conversation(db)

    def failing(*_args: Any, **_kwargs: Any) -> Iterator[PersonaEvent]:
        yield TokenEvent("Hel")
        raise error

    monkeypatch.setattr(persona_events, "reply", failing)
    with caplog.at_level(logging.DEBUG):
        response = client.post(
            messages_url(conversation),
            headers=normal_user_token_headers,
            json={"text": TEXT},
        )

    assert response.status_code == 200
    events = parse_events(response.text)
    assert [name for name, _ in events] == ["token", "error"]
    assert events[1][1] == {"detail": detail}
    assert "secret story text" not in response.text
    assert "secret story text" not in caplog.text
    # The user's message stays for a retry; the broken reply and audit row do not
    assert stored_messages(db, conversation) == [
        (MessageRole.PERSONA, PERSONA_NOTICE),
        (MessageRole.USER, TEXT),
    ]
    assert turns(db, conversation) == []


def test_end_conversation(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    conversation = own_conversation(db)
    client.post(
        messages_url(conversation),
        headers=normal_user_token_headers,
        json={"text": TEXT},
    )

    response = client.post(end_url(conversation), headers=normal_user_token_headers)

    assert response.status_code == 200
    assert response.json() == {"message": "Conversation ended"}
    db.refresh(conversation)
    assert conversation.status == ConversationStatus.ENDED
    assert conversation.ended_at is not None
    assert stored_messages(db, conversation) == []
    # The audit row records the turn without any text, so it stays
    assert len(turns(db, conversation)) == 1


def test_end_conversation_twice(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    conversation = own_conversation(db)
    client.post(end_url(conversation), headers=normal_user_token_headers)
    db.refresh(conversation)
    ended_at = conversation.ended_at

    response = client.post(end_url(conversation), headers=normal_user_token_headers)

    assert response.status_code == 200
    db.refresh(conversation)
    assert conversation.ended_at == ended_at


def test_end_conversation_not_found(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{API}/conversations/{uuid.uuid4()}/end", headers=normal_user_token_headers
    )
    assert response.status_code == 404


def test_end_conversation_other_users_conversation_forbidden(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    conversation = create_random_conversation(db)
    response = client.post(end_url(conversation), headers=normal_user_token_headers)

    assert response.status_code == 403
    db.refresh(conversation)
    assert conversation.status == ConversationStatus.OPEN


def count_rows(db: Session, conversation_id: uuid.UUID) -> tuple[int, int, int]:
    db.expire_all()

    def count(model: Any, column: Any) -> int:
        return db.exec(
            select(func.count())
            .select_from(model)
            .where(col(column) == conversation_id)
        ).one()

    return (
        count(Conversation, Conversation.id),
        count(ConversationMessage, ConversationMessage.conversation_id),
        count(PersonaTurn, PersonaTurn.conversation_id),
    )


def conversation_with_a_turn(
    client: TestClient, headers: dict[str, str], db: Session
) -> Conversation:
    conversation = own_conversation(db)
    client.post(messages_url(conversation), headers=headers, json={"text": TEXT})
    assert count_rows(db, conversation.id) == (1, 3, 1)
    return conversation


def test_delete_person_deletes_conversations(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    conversation = conversation_with_a_turn(client, normal_user_token_headers, db)
    conversation_id = conversation.id
    person = db.get(Person, conversation.person_id)
    assert person is not None

    db.delete(person)
    db.commit()

    assert count_rows(db, conversation_id) == (0, 0, 0)


def test_delete_user_deletes_conversations(db: Session) -> None:
    owner = create_random_user(db)
    conversation = create_random_conversation(
        db, person=create_random_person(db, owner=owner)
    )
    db.add(PersonaTurn(conversation_id=conversation.id, item_ids=[], fallback=True))
    db.commit()

    conversation_id = conversation.id
    db.delete(owner)
    db.commit()

    assert count_rows(db, conversation_id) == (0, 0, 0)
