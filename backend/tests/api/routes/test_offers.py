import logging
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, col, func, select

from app import crud
from app.core.config import settings
from app.core.prompt import PERSONA_NO_MEMORY
from app.models import ExtractedMemory, Memory, MemoryOffer, Person, User
from tests.utils.conversation import create_random_conversation
from tests.utils.person import (
    add_member,
    create_random_offer,
    create_random_person,
)
from tests.utils.user import authentication_token_from_email

API = settings.API_V1_STR
STORY = "Grandma sang folk songs while she baked bread on Sundays."


def get_normal_user(db: Session) -> User:
    user = crud.get_user_by_email(session=db, email=settings.EMAIL_TEST_USER)
    assert user is not None
    return user


def own_person(db: Session) -> Person:
    return create_random_person(db, owner=get_normal_user(db))


def headers_for(client: TestClient, db: Session, user: User) -> dict[str, str]:
    return authentication_token_from_email(client=client, email=user.email, db=db)


def offers_url(person: Person, offer_id: uuid.UUID | None = None) -> str:
    base = f"{API}/persons/{person.id}/offers"
    return base if offer_id is None else f"{base}/{offer_id}"


def count(db: Session, model: type, *where: object) -> int:
    db.expire_all()
    return db.exec(select(func.count()).select_from(model).where(*where)).one()  # type: ignore[arg-type]


def offer_count(db: Session, person: Person) -> int:
    return count(db, MemoryOffer, col(MemoryOffer.person_id) == person.id)


def test_member_offers_a_memory(client: TestClient, db: Session) -> None:
    person = create_random_person(db)
    guest = add_member(db, person)
    memories_before = count(db, Memory)
    items_before = count(db, ExtractedMemory)

    response = client.post(
        offers_url(person),
        headers=headers_for(client, db, guest),
        json={"content": STORY},
    )

    assert response.status_code == 200
    assert response.json() == {"message": "Your offer was sent to the family."}
    offer = db.exec(
        select(MemoryOffer).where(col(MemoryOffer.person_id) == person.id)
    ).one()
    assert offer.content == STORY
    assert offer.from_user_id == guest.id
    # Nothing else changes: an offer is not a memory
    assert count(db, Memory) == memories_before
    assert count(db, ExtractedMemory) == items_before


def test_owner_can_offer(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    person = own_person(db)

    response = client.post(
        offers_url(person), headers=normal_user_token_headers, json={"content": STORY}
    )

    assert response.status_code == 200
    assert offer_count(db, person) == 1


@pytest.mark.parametrize("content", ["", "x" * 5001])
def test_offer_validation(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
    content: str,
) -> None:
    person = own_person(db)

    response = client.post(
        offers_url(person), headers=normal_user_token_headers, json={"content": content}
    )

    assert response.status_code == 422
    assert offer_count(db, person) == 0


def test_offer_limit_per_member(client: TestClient, db: Session) -> None:
    person = create_random_person(db)
    guest = add_member(db, person)
    for number in range(20):
        create_random_offer(db, person, guest, content=f"Offer number {number}")
    headers = headers_for(client, db, guest)

    over = client.post(offers_url(person), headers=headers, json={"content": STORY})
    other_guest = add_member(db, person)
    fine = client.post(
        offers_url(person),
        headers=headers_for(client, db, other_guest),
        json={"content": STORY},
    )

    assert over.status_code == 409
    assert over.json()["detail"] == (
        "Too many offers are waiting for the family to review"
    )
    # The limit is per member: someone else can still offer
    assert fine.status_code == 200
    assert offer_count(db, person) == 21


def test_offer_person_not_found(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{API}/persons/{uuid.uuid4()}/offers",
        headers=normal_user_token_headers,
        json={"content": STORY},
    )
    assert response.status_code == 404


def test_outsider_and_superuser_cannot_use_offers(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    person = create_random_person(db)
    offer = create_random_offer(db, person)
    results = []
    for headers in (normal_user_token_headers, superuser_token_headers):
        results += [
            client.post(offers_url(person), headers=headers, json={"content": STORY}),
            client.get(offers_url(person), headers=headers),
            client.post(f"{offers_url(person, offer.id)}/accept", headers=headers),
            client.delete(offers_url(person, offer.id), headers=headers),
        ]

    assert [r.status_code for r in results] == [403] * 8
    assert offer_count(db, person) == 1
    assert count(db, Memory, col(Memory.person_id) == person.id) == 0


def test_member_cannot_list_accept_or_decline(client: TestClient, db: Session) -> None:
    person = create_random_person(db)
    guest = add_member(db, person)
    offer = create_random_offer(db, person, guest)
    headers = headers_for(client, db, guest)

    attempts = [
        client.get(offers_url(person), headers=headers),
        client.post(f"{offers_url(person, offer.id)}/accept", headers=headers),
        client.delete(offers_url(person, offer.id), headers=headers),
    ]

    assert [a.status_code for a in attempts] == [403, 403, 403]
    assert offer_count(db, person) == 1


def test_revoked_member_cannot_offer(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    person = own_person(db)
    guest = add_member(db, person)
    headers = headers_for(client, db, guest)
    client.delete(
        f"{API}/persons/{person.id}/members/{guest.id}",
        headers=normal_user_token_headers,
    )

    response = client.post(offers_url(person), headers=headers, json={"content": STORY})

    assert response.status_code == 403


def test_list_offers(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    person = own_person(db)
    guest = add_member(db, person)
    create_random_offer(db, person, guest, content="First offer.")
    create_random_offer(db, person, guest, content="Second offer.")
    create_random_offer(db, create_random_person(db), guest, content="Not this one.")

    response = client.get(offers_url(person), headers=normal_user_token_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert [o["content"] for o in body["data"]] == ["Second offer.", "First offer."]
    assert body["data"][0]["from_name"] == guest.email


def test_accept_offer_creates_the_owners_memory(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    person = own_person(db)
    guest = add_member(db, person)
    offer = create_random_offer(db, person, guest, content=STORY)
    offer_id = offer.id

    response = client.post(
        f"{offers_url(person, offer_id)}/accept", headers=normal_user_token_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["owner_id"] == str(get_normal_user(db).id)
    assert body["content"] == STORY
    assert body["person_name"] == person.name
    assert body["title"].startswith("Offered: Grandma sang folk songs")
    memory = db.get(Memory, uuid.UUID(body["id"]))
    assert memory is not None
    assert memory.person_id == person.id
    assert count(db, MemoryOffer, col(MemoryOffer.id) == offer_id) == 0
    # Extraction ran as for any new memory, and nothing is confirmed
    items = db.exec(
        select(ExtractedMemory).where(col(ExtractedMemory.memory_id) == memory.id)
    ).all()
    assert items
    assert all(item.confirmed_at is None for item in items)


def test_accept_twice_gives_404(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    person = own_person(db)
    offer = create_random_offer(db, person)
    url = f"{offers_url(person, offer.id)}/accept"
    memories_before = count(db, Memory)

    first = client.post(url, headers=normal_user_token_headers)
    second = client.post(url, headers=normal_user_token_headers)

    assert first.status_code == 200
    assert second.status_code == 404
    assert second.json()["detail"] == "Offer not found"
    assert count(db, Memory) == memories_before + 1


def test_accepted_items_are_not_used_by_the_persona_until_confirmed(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    person = own_person(db)
    offer = create_random_offer(db, person, content=STORY)
    client.post(
        f"{offers_url(person, offer.id)}/accept", headers=normal_user_token_headers
    )
    conversation = create_random_conversation(db, person=person)

    response = client.post(
        f"{API}/conversations/{conversation.id}/messages",
        headers=normal_user_token_headers,
        json={"text": STORY},
    )

    assert PERSONA_NO_MEMORY in response.text
    assert '"fallback": true' in response.text
    assert '"sources": []' in response.text


def test_decline_offer(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    person = own_person(db)
    offer = create_random_offer(db, person)
    memories_before = count(db, Memory)

    response = client.delete(
        offers_url(person, offer.id), headers=normal_user_token_headers
    )

    assert response.status_code == 200
    assert response.json() == {"message": "Offer declined"}
    assert offer_count(db, person) == 0
    assert count(db, Memory) == memories_before


def test_offer_of_another_person_is_not_found(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    mine = own_person(db)
    theirs = create_random_person(db)
    foreign = create_random_offer(db, theirs)

    accept = client.post(
        f"{offers_url(mine, foreign.id)}/accept", headers=normal_user_token_headers
    )
    decline = client.delete(
        offers_url(mine, foreign.id), headers=normal_user_token_headers
    )

    assert [accept.status_code, decline.status_code] == [404, 404]
    assert offer_count(db, theirs) == 1


def test_offer_not_found(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    person = own_person(db)
    missing = uuid.uuid4()

    results = [
        client.post(
            f"{offers_url(person, missing)}/accept", headers=normal_user_token_headers
        ),
        client.delete(offers_url(person, missing), headers=normal_user_token_headers),
    ]

    assert [r.status_code for r in results] == [404, 404]


def test_a_conversation_creates_no_memory_or_extracted_item(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    person = own_person(db)
    conversation = create_random_conversation(db, person=person)
    memories_before = count(db, Memory)
    items_before = count(db, ExtractedMemory)
    offers_before = offer_count(db, person)

    for text in ("Please remember that she loved tulips.", "Add this to her stories"):
        client.post(
            f"{API}/conversations/{conversation.id}/messages",
            headers=normal_user_token_headers,
            json={"text": text},
        )
    client.post(
        f"{API}/conversations/{conversation.id}/end",
        headers=normal_user_token_headers,
    )

    assert count(db, Memory) == memories_before
    assert count(db, ExtractedMemory) == items_before
    assert offer_count(db, person) == offers_before


def test_delete_person_deletes_offers(db: Session) -> None:
    person = create_random_person(db)
    create_random_offer(db, person)
    person_id = person.id

    db.delete(person)
    db.commit()

    assert count(db, MemoryOffer, col(MemoryOffer.person_id) == person_id) == 0


def test_delete_member_user_deletes_their_offers(db: Session) -> None:
    person = create_random_person(db)
    guest = add_member(db, person)
    create_random_offer(db, person, guest)
    guest_id = guest.id

    db.delete(guest)
    db.commit()

    assert count(db, MemoryOffer, col(MemoryOffer.from_user_id) == guest_id) == 0
    assert db.get(Person, person.id) is not None


def test_revoke_keeps_waiting_offers(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    person = own_person(db)
    guest = add_member(db, person)
    create_random_offer(db, person, guest)

    client.delete(
        f"{API}/persons/{person.id}/members/{guest.id}",
        headers=normal_user_token_headers,
    )

    assert offer_count(db, person) == 1


def test_offer_text_is_not_logged(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
    caplog: pytest.LogCaptureFixture,
) -> None:
    person = own_person(db)
    secret = "Her private diagnosis was never shared with the cousins."

    with caplog.at_level(logging.DEBUG):
        client.post(
            offers_url(person),
            headers=normal_user_token_headers,
            json={"content": secret},
        )
        offer = db.exec(
            select(MemoryOffer).where(col(MemoryOffer.person_id) == person.id)
        ).one()
        client.post(
            f"{offers_url(person, offer.id)}/accept", headers=normal_user_token_headers
        )

    assert "memory offered" in caplog.text
    assert "offer accepted" in caplog.text
    assert secret not in caplog.text
