import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, col, func, select

from app import crud
from app.core.config import settings
from app.models import (
    Conversation,
    ConversationStatus,
    ConversationSummary,
    ExtractedMemory,
    Memory,
    MessageRole,
    Person,
    User,
)
from app.services import persona_graph
from app.services.persona_events import DoneEvent, PersonaEvent, TokenEvent
from tests.utils.conversation import (
    add_message,
    create_random_conversation,
    create_random_summary,
)
from tests.utils.extracted_memory import create_random_extracted_memory
from tests.utils.memory import create_random_memory
from tests.utils.person import create_random_person
from tests.utils.user import create_random_user

API = settings.API_V1_STR


def get_normal_user(db: Session) -> User:
    user = crud.get_user_by_email(session=db, email=settings.EMAIL_TEST_USER)
    assert user is not None
    return user


def summary_url(person: Person) -> str:
    return f"{API}/persons/{person.id}/summary"


def own_person(db: Session) -> Person:
    return create_random_person(db, owner=get_normal_user(db))


def count_summaries(db: Session, person_id: uuid.UUID) -> int:
    db.expire_all()
    return db.exec(
        select(func.count())
        .select_from(ConversationSummary)
        .where(col(ConversationSummary.person_id) == person_id)
    ).one()


def linked_item(
    db: Session, person: Person, owner: User | None = None
) -> tuple[Memory, ExtractedMemory]:
    """A memory of the person's owner, linked to them, with one item."""
    memory = create_random_memory(db, owner or get_normal_user(db))
    memory.person_id = person.id
    db.add(memory)
    db.commit()
    db.refresh(memory)
    return memory, create_random_extracted_memory(db, memory, content="garden tomatoes")


def test_end_conversation_keeps_a_summary_the_caller_can_read(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    person = own_person(db)
    conversation = create_random_conversation(db, person=person)
    add_message(db, conversation, MessageRole.USER, "Tell me about the garden")

    ended = client.post(
        f"{API}/conversations/{conversation.id}/end",
        headers=normal_user_token_headers,
    )
    response = client.get(summary_url(person), headers=normal_user_token_headers)

    assert ended.status_code == 200
    assert response.status_code == 200
    assert response.json()["content"] == "Fake answer citing [1]."
    assert "updated_at" in response.json()


def test_read_summary_not_found(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    response = client.get(
        summary_url(own_person(db)), headers=normal_user_token_headers
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Summary not found"


def test_read_summary_person_not_found(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{API}/persons/{uuid.uuid4()}/summary", headers=normal_user_token_headers
    )
    assert response.status_code == 404


def test_read_summary_outsider_forbidden(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    person = create_random_person(db)
    create_random_summary(db, person)

    response = client.get(summary_url(person), headers=normal_user_token_headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"


def test_superuser_no_access_to_summaries(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    person = create_random_person(db)
    create_random_summary(db, person)

    assert (
        client.get(summary_url(person), headers=superuser_token_headers).status_code
        == 403
    )
    assert (
        client.delete(summary_url(person), headers=superuser_token_headers).status_code
        == 403
    )
    assert count_summaries(db, person.id) == 1


def test_another_users_summary_is_not_returned(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    person = own_person(db)
    other = create_random_user(db)
    create_random_summary(db, person, user=other, content="Someone else's note.")

    read = client.get(summary_url(person), headers=normal_user_token_headers)
    delete = client.delete(summary_url(person), headers=normal_user_token_headers)

    assert read.status_code == 404
    assert "Someone else's note." not in read.text
    assert delete.status_code == 404
    assert count_summaries(db, person.id) == 1


def test_delete_own_summary(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    person = own_person(db)
    create_random_summary(db, person, user=get_normal_user(db))

    response = client.delete(summary_url(person), headers=normal_user_token_headers)

    assert response.status_code == 200
    assert response.json() == {"message": "Summary deleted"}
    assert count_summaries(db, person.id) == 0
    assert (
        client.get(summary_url(person), headers=normal_user_token_headers).status_code
        == 404
    )


def test_delete_summary_not_found(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    response = client.delete(
        summary_url(own_person(db)), headers=normal_user_token_headers
    )
    assert response.status_code == 404


def test_delete_summary_outsider_forbidden(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    person = create_random_person(db)
    create_random_summary(db, person)

    response = client.delete(summary_url(person), headers=normal_user_token_headers)

    assert response.status_code == 403
    assert count_summaries(db, person.id) == 1


def test_send_message_passes_the_callers_summary_to_the_reply(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    person = own_person(db)
    create_random_summary(
        db, person, user=get_normal_user(db), content="They spoke about the boat."
    )
    conversation = create_random_conversation(db, person=person)
    seen: list[str | None] = []

    def recording(*_args: Any, **kwargs: Any) -> Iterator[PersonaEvent]:
        seen.append(kwargs["summary"])
        yield TokenEvent("ok")
        yield DoneEvent(sources=[], fallback=True)

    monkeypatch.setattr(persona_graph, "reply", recording)
    client.post(
        f"{API}/conversations/{conversation.id}/messages",
        headers=normal_user_token_headers,
        json={"text": "hello"},
    )

    assert seen == ["They spoke about the boat."]


def test_send_message_without_a_summary_passes_none(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    person = own_person(db)
    # Another user's note about the same person must not reach this conversation
    create_random_summary(db, person, user=create_random_user(db), content="Not yours.")
    conversation = create_random_conversation(db, person=person)
    seen: list[str | None] = []

    def recording(*_args: Any, **kwargs: Any) -> Iterator[PersonaEvent]:
        seen.append(kwargs["summary"])
        yield TokenEvent("ok")
        yield DoneEvent(sources=[], fallback=True)

    monkeypatch.setattr(persona_graph, "reply", recording)
    client.post(
        f"{API}/conversations/{conversation.id}/messages",
        headers=normal_user_token_headers,
        json={"text": "hello"},
    )

    assert seen == [None]


def test_idle_conversation_can_still_be_ended_by_hand(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    conversation = create_random_conversation(db, person=own_person(db))
    conversation_id = conversation.id

    response = client.post(
        f"{API}/conversations/{conversation_id}/end",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 200
    db.expire_all()
    ended = db.get(Conversation, conversation_id)
    assert ended is not None
    assert ended.status == ConversationStatus.ENDED


def test_delete_memory_deletes_person_summaries(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    person = own_person(db)
    memory, _ = linked_item(db, person)
    create_random_summary(db, person, user=create_random_user(db))
    create_random_summary(db, person)
    elsewhere = create_random_person(db)
    create_random_summary(db, elsewhere)

    response = client.delete(
        f"{API}/memories/{memory.id}", headers=normal_user_token_headers
    )

    assert response.status_code == 200
    assert count_summaries(db, person.id) == 0
    assert count_summaries(db, elsewhere.id) == 1


def test_delete_unlinked_memory_keeps_summaries(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    person = own_person(db)
    create_random_summary(db, person)
    memory = create_random_memory(db, get_normal_user(db))

    response = client.delete(
        f"{API}/memories/{memory.id}", headers=normal_user_token_headers
    )

    assert response.status_code == 200
    assert count_summaries(db, person.id) == 1


def test_reject_item_deletes_summaries(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    person = own_person(db)
    memory, item = linked_item(db, person)
    create_random_summary(db, person)

    response = client.patch(
        f"{API}/memories/{memory.id}/extracted/{item.id}",
        headers=normal_user_token_headers,
        json={"rejected": True},
    )

    assert response.status_code == 200
    assert count_summaries(db, person.id) == 0


def test_correct_item_deletes_summaries(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    person = own_person(db)
    memory, item = linked_item(db, person)
    create_random_summary(db, person)

    response = client.patch(
        f"{API}/memories/{memory.id}/extracted/{item.id}",
        headers=normal_user_token_headers,
        json={"content": "born in Da Nang"},
    )

    assert response.status_code == 200
    assert count_summaries(db, person.id) == 0


def test_delete_item_deletes_summaries(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    person = own_person(db)
    memory, item = linked_item(db, person)
    create_random_summary(db, person)

    response = client.delete(
        f"{API}/memories/{memory.id}/extracted/{item.id}",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 200
    assert count_summaries(db, person.id) == 0


def test_changes_that_do_not_touch_a_fact_keep_summaries(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    person = own_person(db)
    memory, item = linked_item(db, person)
    create_random_summary(db, person)
    item_url = f"{API}/memories/{memory.id}/extracted/{item.id}"

    confirmed = client.post(f"{item_url}/confirm", headers=normal_user_token_headers)
    unconfirmed = client.delete(
        f"{item_url}/confirm", headers=normal_user_token_headers
    )
    untouched = client.patch(item_url, headers=normal_user_token_headers, json={})

    assert [confirmed.status_code, unconfirmed.status_code, untouched.status_code] == [
        200,
        200,
        200,
    ]
    assert count_summaries(db, person.id) == 1


def test_reject_item_of_an_unlinked_memory_keeps_summaries(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    person = own_person(db)
    create_random_summary(db, person)
    memory = create_random_memory(db, get_normal_user(db))
    item = create_random_extracted_memory(db, memory)

    client.patch(
        f"{API}/memories/{memory.id}/extracted/{item.id}",
        headers=normal_user_token_headers,
        json={"rejected": True},
    )

    assert count_summaries(db, person.id) == 1


def test_delete_person_deletes_summaries(db: Session) -> None:
    person = create_random_person(db)
    create_random_summary(db, person)
    create_random_summary(db, person, user=create_random_user(db))
    person_id = person.id

    db.delete(person)
    db.commit()

    assert count_summaries(db, person_id) == 0


def test_delete_user_deletes_summaries(db: Session) -> None:
    person = create_random_person(db)
    member = create_random_user(db)
    create_random_summary(db, person, user=member)
    person_id = person.id

    db.delete(member)
    db.commit()

    assert count_summaries(db, person_id) == 0
