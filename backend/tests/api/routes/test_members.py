import logging
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, col, func, select

from app import crud
from app.core.config import settings
from app.core.prompt import PERSONA_NOTICE
from app.models import (
    Conversation,
    ConversationMessage,
    ConversationStatus,
    ConversationSummary,
    MessageRole,
    Person,
    PersonMember,
    User,
)
from tests.utils.conversation import (
    add_message,
    create_random_conversation,
    create_random_summary,
)
from tests.utils.extracted_memory import create_random_extracted_memory
from tests.utils.llm import FakeLLMClient
from tests.utils.memory import create_random_memory
from tests.utils.person import add_member, create_random_person
from tests.utils.user import authentication_token_from_email, create_random_user

API = settings.API_V1_STR
ANSWER = "If an account exists for that email it can now talk with this persona."
GARDEN = "garden tomatoes"


def get_normal_user(db: Session) -> User:
    user = crud.get_user_by_email(session=db, email=settings.EMAIL_TEST_USER)
    assert user is not None
    return user


def own_person(db: Session) -> Person:
    return create_random_person(db, owner=get_normal_user(db))


def headers_for(client: TestClient, db: Session, user: User) -> dict[str, str]:
    return authentication_token_from_email(client=client, email=user.email, db=db)


def members_url(person: Person) -> str:
    return f"{API}/persons/{person.id}/members"


def invite(
    client: TestClient,
    headers: dict[str, str],
    person: Person,
    email: str,
    adult_confirmed: bool | None = True,
) -> object:
    body: dict[str, object] = {"email": email}
    if adult_confirmed is not None:
        body["adult_confirmed"] = adult_confirmed
    return client.post(members_url(person), headers=headers, json=body)


def member_count(db: Session, person: Person) -> int:
    db.expire_all()
    return db.exec(
        select(func.count())
        .select_from(PersonMember)
        .where(col(PersonMember.person_id) == person.id)
    ).one()


def test_invite_member(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    person = own_person(db)
    guest = create_random_user(db)

    response = invite(client, normal_user_token_headers, person, guest.email)

    assert response.status_code == 200  # type: ignore[attr-defined]
    assert response.json() == {"message": ANSWER}  # type: ignore[attr-defined]
    db.expire_all()
    row = db.exec(
        select(PersonMember).where(col(PersonMember.person_id) == person.id)
    ).one()
    assert row.user_id == guest.id
    assert row.adult_confirmed is True


def test_invite_is_idempotent(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    person = own_person(db)
    guest = create_random_user(db)

    first = invite(client, normal_user_token_headers, person, guest.email)
    second = invite(client, normal_user_token_headers, person, guest.email)

    assert first.json() == second.json()  # type: ignore[attr-defined]
    assert member_count(db, person) == 1


def test_list_members(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    person = own_person(db)
    guest = add_member(db, person)

    response = client.get(members_url(person), headers=normal_user_token_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["data"][0]["user_id"] == str(guest.id)
    assert body["data"][0]["email"] == guest.email
    assert "invited_at" in body["data"][0]


@pytest.mark.parametrize("adult_confirmed", [None, False])
def test_invite_requires_adult_confirmed(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
    adult_confirmed: bool | None,
) -> None:
    person = own_person(db)
    guest = create_random_user(db)

    response = invite(
        client, normal_user_token_headers, person, guest.email, adult_confirmed
    )

    assert response.status_code == 422  # type: ignore[attr-defined]
    assert member_count(db, person) == 0


def test_invite_with_null_confirmation_is_refused(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    person = own_person(db)
    guest = create_random_user(db)

    response = client.post(
        members_url(person),
        headers=normal_user_token_headers,
        json={"email": guest.email, "adult_confirmed": None},
    )

    assert response.status_code == 422
    assert member_count(db, person) == 0


def test_invite_invalid_email(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    response = invite(client, normal_user_token_headers, own_person(db), "not-an-email")
    assert response.status_code == 422  # type: ignore[attr-defined]


def test_invite_unknown_email_gets_the_same_answer(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    person = own_person(db)
    known = invite(
        client, normal_user_token_headers, person, create_random_user(db).email
    )

    unknown = invite(
        client, normal_user_token_headers, person, f"nobody-{uuid.uuid4()}@example.com"
    )

    assert unknown.status_code == known.status_code  # type: ignore[attr-defined]
    assert unknown.json() == known.json()  # type: ignore[attr-defined]
    assert member_count(db, person) == 1


def test_invite_owner_and_inactive_accounts_get_the_same_answer(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    person = own_person(db)
    inactive = create_random_user(db)
    inactive.is_active = False
    db.add(inactive)
    db.commit()

    own = invite(client, normal_user_token_headers, person, settings.EMAIL_TEST_USER)
    gone = invite(client, normal_user_token_headers, person, inactive.email)

    assert own.json() == {"message": ANSWER}  # type: ignore[attr-defined]
    assert gone.json() == {"message": ANSWER}  # type: ignore[attr-defined]
    assert member_count(db, person) == 0


def test_invite_person_not_found(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{API}/persons/{uuid.uuid4()}/members",
        headers=normal_user_token_headers,
        json={"email": "a@example.com", "adult_confirmed": True},
    )
    assert response.status_code == 404


def test_outsider_cannot_manage_members(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    person = create_random_person(db)
    guest = add_member(db, person)
    other = create_random_user(db)

    attempts = [
        invite(client, normal_user_token_headers, person, other.email),
        client.get(members_url(person), headers=normal_user_token_headers),
        client.delete(
            f"{members_url(person)}/{guest.id}", headers=normal_user_token_headers
        ),
    ]

    assert [a.status_code for a in attempts] == [403, 403, 403]  # type: ignore[attr-defined]
    assert member_count(db, person) == 1


def test_superuser_cannot_manage_members(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    person = own_person(db)
    guest = add_member(db, person)

    attempts = [
        invite(client, superuser_token_headers, person, create_random_user(db).email),
        client.get(members_url(person), headers=superuser_token_headers),
        client.delete(
            f"{members_url(person)}/{guest.id}", headers=superuser_token_headers
        ),
    ]

    assert [a.status_code for a in attempts] == [403, 403, 403]  # type: ignore[attr-defined]
    assert member_count(db, person) == 1


def test_member_cannot_manage_members_or_reach_owner_endpoints(
    client: TestClient, db: Session
) -> None:
    owner = create_random_user(db)
    person = create_random_person(db, owner=owner)
    memory = create_random_memory(db, owner)
    memory.person_id = person.id
    db.add(memory)
    db.commit()
    item = create_random_extracted_memory(db, memory, content=GARDEN, confirmed=True)
    guest = add_member(db, person)
    other = create_random_user(db)
    headers = headers_for(client, db, guest)

    attempts = {
        "invite": invite(client, headers, person, other.email),
        "list members": client.get(members_url(person), headers=headers),
        "revoke": client.delete(f"{members_url(person)}/{guest.id}", headers=headers),
        "read person": client.get(f"{API}/persons/{person.id}", headers=headers),
        "delete person": client.delete(f"{API}/persons/{person.id}", headers=headers),
        "read memory": client.get(f"{API}/memories/{memory.id}", headers=headers),
        "edit memory": client.put(
            f"{API}/memories/{memory.id}", headers=headers, json={"title": "x"}
        ),
        "delete memory": client.delete(f"{API}/memories/{memory.id}", headers=headers),
        "read items": client.get(
            f"{API}/memories/{memory.id}/extracted/", headers=headers
        ),
        "confirm item": client.post(
            f"{API}/memories/{memory.id}/extracted/{item.id}/confirm", headers=headers
        ),
        "confirm all": client.post(
            f"{API}/memories/{memory.id}/confirm-all", headers=headers
        ),
        "edit item": client.patch(
            f"{API}/memories/{memory.id}/extracted/{item.id}",
            headers=headers,
            json={"content": "changed"},
        ),
        "read files": client.get(f"{API}/memories/{memory.id}/files/", headers=headers),
    }

    statuses = {name: response.status_code for name, response in attempts.items()}  # type: ignore[attr-defined]
    assert statuses == dict.fromkeys(attempts, 403)
    assert member_count(db, person) == 1


def test_member_search_never_reaches_the_owners_memories(
    client: TestClient, db: Session
) -> None:
    owner = create_random_user(db)
    person = create_random_person(db, owner=owner)
    memory = create_random_memory(db, owner)
    memory.person_id = person.id
    db.add(memory)
    db.commit()
    create_random_extracted_memory(db, memory, content=GARDEN, confirmed=True)
    headers = headers_for(client, db, add_member(db, person))

    response = client.post(f"{API}/search/", headers=headers, json={"query": GARDEN})

    assert response.status_code == 200
    assert response.json()["data"] == []


def test_member_converses_using_the_owners_confirmed_memory(
    client: TestClient, db: Session
) -> None:
    owner = create_random_user(db)
    person = create_random_person(db, owner=owner)
    memory = create_random_memory(db, owner)
    memory.person_id = person.id
    db.add(memory)
    db.commit()
    item = create_random_extracted_memory(db, memory, content=GARDEN, confirmed=True)
    # Another family's confirmed item must never reach this persona
    create_random_extracted_memory(
        db, create_random_memory(db), content=GARDEN, confirmed=True
    )
    guest = add_member(db, person)
    headers = headers_for(client, db, guest)

    opened = client.post(f"{API}/persons/{person.id}/conversations", headers=headers)
    assert opened.status_code == 200
    assert opened.json()["notice"] == PERSONA_NOTICE
    conversation_id = opened.json()["conversation_id"]
    response = client.post(
        f"{API}/conversations/{conversation_id}/messages",
        headers=headers,
        json={"text": GARDEN},
    )

    assert response.status_code == 200
    assert '"fallback": false' in response.text
    assert str(item.id) in response.text
    conversation = db.get(Conversation, uuid.UUID(conversation_id))
    assert conversation is not None
    assert conversation.user_id == guest.id


def test_owner_cannot_use_a_members_conversation(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    person = own_person(db)
    guest = add_member(db, person)
    conversation = create_random_conversation(db, user=guest, person=person)
    conversation.user_id = guest.id
    db.add(conversation)
    db.commit()

    response = client.post(
        f"{API}/conversations/{conversation.id}/messages",
        headers=normal_user_token_headers,
        json={"text": "hello"},
    )

    assert response.status_code == 403


def test_member_reads_and_deletes_only_their_own_summary(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    person = own_person(db)
    guest = add_member(db, person)
    create_random_summary(db, person, user=guest, content="Guest's private note.")
    create_random_summary(
        db, person, user=get_normal_user(db), content="Owner's private note."
    )
    headers = headers_for(client, db, guest)
    url = f"{API}/persons/{person.id}/summary"

    read = client.get(url, headers=headers)
    owner_read = client.get(url, headers=normal_user_token_headers)

    assert read.json()["content"] == "Guest's private note."
    assert owner_read.json()["content"] == "Owner's private note."
    assert client.delete(url, headers=headers).status_code == 200
    # Deleting the member's own note leaves the owner's alone
    assert (
        client.get(url, headers=normal_user_token_headers).json()["content"]
        == "Owner's private note."
    )


def test_revoke_ends_conversations_without_summary_and_deletes_the_old_one(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
    llm_client: FakeLLMClient,
) -> None:
    person = own_person(db)
    guest = add_member(db, person)
    conversation = create_random_conversation(db, user=guest, person=person)
    conversation.user_id = guest.id
    db.add(conversation)
    db.commit()
    add_message(db, conversation, MessageRole.USER, "I miss her so much")
    create_random_summary(db, person, user=guest, content="Older note.")
    conversation_id = conversation.id

    response = client.delete(
        f"{members_url(person)}/{guest.id}", headers=normal_user_token_headers
    )

    assert response.status_code == 200
    assert llm_client.answer_prompts == []
    assert member_count(db, person) == 0
    db.expire_all()
    ended = db.get(Conversation, conversation_id)
    assert ended is not None
    assert ended.status == ConversationStatus.ENDED
    assert ended.ended_at is not None
    left = db.exec(
        select(func.count())
        .select_from(ConversationMessage)
        .where(col(ConversationMessage.conversation_id) == conversation_id)
    ).one()
    assert left == 0
    summaries = db.exec(
        select(func.count())
        .select_from(ConversationSummary)
        .where(col(ConversationSummary.person_id) == person.id)
    ).one()
    assert summaries == 0


def test_revoked_member_gets_403_on_the_next_message_open_and_summary(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    person = own_person(db)
    guest = add_member(db, person)
    conversation = create_random_conversation(db, user=guest, person=person)
    conversation.user_id = guest.id
    db.add(conversation)
    db.commit()
    headers = headers_for(client, db, guest)
    client.delete(
        f"{members_url(person)}/{guest.id}", headers=normal_user_token_headers
    )

    send = client.post(
        f"{API}/conversations/{conversation.id}/messages",
        headers=headers,
        json={"text": "hello?"},
    )
    reopen = client.post(f"{API}/persons/{person.id}/conversations", headers=headers)
    summary = client.get(f"{API}/persons/{person.id}/summary", headers=headers)

    assert [send.status_code, reopen.status_code, summary.status_code] == [
        403,
        403,
        403,
    ]


def test_revoke_leaves_other_members_alone(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    person = own_person(db)
    leaving = add_member(db, person)
    staying = add_member(db, person)
    for member in (leaving, staying):
        conversation = create_random_conversation(db, user=member, person=person)
        conversation.user_id = member.id
        db.add(conversation)
        db.commit()
        create_random_summary(db, person, user=member)
        if member is staying:
            kept = conversation.id

    client.delete(
        f"{members_url(person)}/{leaving.id}", headers=normal_user_token_headers
    )

    db.expire_all()
    still_open = db.get(Conversation, kept)
    assert still_open is not None
    assert still_open.status == ConversationStatus.OPEN
    assert member_count(db, person) == 1
    remaining = db.exec(
        select(ConversationSummary).where(
            col(ConversationSummary.person_id) == person.id
        )
    ).all()
    assert [row.user_id for row in remaining] == [staying.id]


def test_revoke_member_not_found(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    response = client.delete(
        f"{members_url(own_person(db))}/{uuid.uuid4()}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Member not found"


def test_invite_and_revoke_log_ids_only(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
    caplog: pytest.LogCaptureFixture,
) -> None:
    person = own_person(db)
    guest = create_random_user(db)

    with caplog.at_level(logging.DEBUG):
        invite(client, normal_user_token_headers, person, guest.email)
        client.delete(
            f"{members_url(person)}/{guest.id}", headers=normal_user_token_headers
        )

    assert str(guest.id) in caplog.text
    assert guest.email not in caplog.text


def test_delete_person_deletes_members(db: Session) -> None:
    person = create_random_person(db)
    add_member(db, person)
    person_id = person.id

    db.delete(person)
    db.commit()

    db.expire_all()
    left = db.exec(
        select(func.count())
        .select_from(PersonMember)
        .where(col(PersonMember.person_id) == person_id)
    ).one()
    assert left == 0


def test_delete_user_deletes_membership(db: Session) -> None:
    person = create_random_person(db)
    guest = add_member(db, person)
    guest_id = guest.id

    db.delete(guest)
    db.commit()

    db.expire_all()
    left = db.exec(
        select(func.count())
        .select_from(PersonMember)
        .where(col(PersonMember.user_id) == guest_id)
    ).one()
    assert left == 0
    assert db.get(Person, person.id) is not None


def test_delete_owner_deletes_members(db: Session) -> None:
    owner = create_random_user(db)
    person = create_random_person(db, owner=owner)
    add_member(db, person)
    person_id = person.id

    db.delete(owner)
    db.commit()

    db.expire_all()
    left = db.exec(
        select(func.count())
        .select_from(PersonMember)
        .where(col(PersonMember.person_id) == person_id)
    ).one()
    assert left == 0


def test_stream_turn_stops_if_the_conversation_ended_since_the_request(
    db: Session, llm_client: FakeLLMClient
) -> None:
    # Imported here: it is the function behind the streamed body
    from app.api.routes.conversations import stream_turn

    person = create_random_person(db)
    guest = add_member(db, person)
    conversation = create_random_conversation(db, user=guest, person=person)
    conversation.user_id = guest.id
    conversation.status = ConversationStatus.ENDED
    db.add(conversation)
    db.commit()

    events = list(
        stream_turn(
            llm_client,
            conversation_id=conversation.id,
            person_id=person.id,
            person_name="Margaret",
            history=[],
            text=GARDEN,
            summary=None,
            turn_number=1,
        )
    )

    assert len(events) == 1
    assert events[0].startswith("event: error")
    assert llm_client.stream_calls == []


def test_no_summary_is_written_for_someone_who_lost_access_meanwhile(
    db: Session, llm_client: FakeLLMClient
) -> None:
    from app.services.conversation_summary import end_conversation, get_summary

    person = create_random_person(db)
    guest = create_random_user(db)
    # Opened while a member, then revoked before it was ended
    conversation = create_random_conversation(db, user=guest, person=person)
    conversation.user_id = guest.id
    db.add(conversation)
    db.commit()
    add_message(db, conversation, MessageRole.USER, "I miss her")
    person_id, user_id = person.id, guest.id

    end_conversation(db, llm_client, conversation)

    assert get_summary(db, person_id, user_id) is None
    db.refresh(conversation)
    assert conversation.status == ConversationStatus.ENDED


def test_revoke_leaves_no_message_in_any_conversation_of_the_member(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    person = own_person(db)
    guest = add_member(db, person)
    conversation = create_random_conversation(db, user=guest, person=person)
    conversation.user_id = guest.id
    db.add(conversation)
    db.commit()
    add_message(db, conversation, MessageRole.USER, "hello")
    add_message(db, conversation, MessageRole.PERSONA, "hi")
    conversation_id = conversation.id

    client.delete(
        f"{members_url(person)}/{guest.id}", headers=normal_user_token_headers
    )

    db.expire_all()
    left = db.exec(
        select(func.count())
        .select_from(ConversationMessage)
        .where(col(ConversationMessage.conversation_id) == conversation_id)
    ).one()
    assert left == 0
