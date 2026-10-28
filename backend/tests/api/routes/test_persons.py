import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import Memory, Person, User, UserCreate
from tests.utils.memory import create_random_memory
from tests.utils.person import create_random_person
from tests.utils.utils import random_email, random_lower_string

PERSONS_URL = f"{settings.API_V1_STR}/persons"
MEMORIES_URL = f"{settings.API_V1_STR}/memories"
PERSON_DATA = {"name": "Margaret Thomas", "other_names": ["Mom", "Mum"]}


def get_normal_user(db: Session) -> User:
    user = crud.get_user_by_email(session=db, email=settings.EMAIL_TEST_USER)
    assert user is not None
    return user


def test_create_person(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    response = client.post(
        f"{PERSONS_URL}/", headers=normal_user_token_headers, json=PERSON_DATA
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == "Margaret Thomas"
    assert content["other_names"] == ["Mom", "Mum"]
    assert content["owner_id"] == str(get_normal_user(db).id)
    assert "id" in content


def test_create_person_cleans_other_names(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{PERSONS_URL}/",
        headers=normal_user_token_headers,
        json={"name": "Margaret", "other_names": [" Mom ", "mom", "Mẹ"]},
    )
    assert response.status_code == 200
    assert response.json()["other_names"] == ["Mom", "Mẹ"]


def test_create_person_without_other_names(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{PERSONS_URL}/", headers=normal_user_token_headers, json={"name": "Tom"}
    )
    assert response.status_code == 200
    assert response.json()["other_names"] == []


def test_create_person_invalid(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    for body in (
        {"name": ""},
        {"name": "x", "other_names": ["a"] * 11},
        {"name": "x", "other_names": [""]},
        {"name": "x", "other_names": ["a" * 256]},
    ):
        response = client.post(
            f"{PERSONS_URL}/", headers=normal_user_token_headers, json=body
        )
        assert response.status_code == 422


def test_read_persons_only_own(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    mine = create_random_person(db, owner=get_normal_user(db))
    other = create_random_person(db)
    response = client.get(f"{PERSONS_URL}/", headers=normal_user_token_headers)
    assert response.status_code == 200
    content = response.json()
    ids = {person["id"] for person in content["data"]}
    assert str(mine.id) in ids
    assert str(other.id) not in ids
    assert content["count"] == len(content["data"])


def test_read_person(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    created = client.post(
        f"{PERSONS_URL}/", headers=normal_user_token_headers, json=PERSON_DATA
    ).json()
    response = client.get(
        f"{PERSONS_URL}/{created['id']}", headers=normal_user_token_headers
    )
    assert response.status_code == 200
    assert response.json() == created


def test_read_person_not_found(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{PERSONS_URL}/{uuid.uuid4()}", headers=normal_user_token_headers
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Person not found"


def test_update_person(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    created = client.post(
        f"{PERSONS_URL}/", headers=normal_user_token_headers, json=PERSON_DATA
    ).json()
    response = client.patch(
        f"{PERSONS_URL}/{created['id']}",
        headers=normal_user_token_headers,
        json={"other_names": ["Mẹ"]},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Margaret Thomas"
    assert response.json()["other_names"] == ["Mẹ"]


def test_update_person_invalid(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    created = client.post(
        f"{PERSONS_URL}/", headers=normal_user_token_headers, json=PERSON_DATA
    ).json()
    for body in ({"name": None}, {"other_names": None}, {"name": ""}):
        response = client.patch(
            f"{PERSONS_URL}/{created['id']}",
            headers=normal_user_token_headers,
            json=body,
        )
        assert response.status_code == 422


def test_delete_person(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    created = client.post(
        f"{PERSONS_URL}/", headers=normal_user_token_headers, json=PERSON_DATA
    ).json()
    response = client.delete(
        f"{PERSONS_URL}/{created['id']}", headers=normal_user_token_headers
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Person deleted successfully"
    again = client.get(
        f"{PERSONS_URL}/{created['id']}", headers=normal_user_token_headers
    )
    assert again.status_code == 404


def test_delete_person_keeps_memories(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    me = get_normal_user(db)
    person = create_random_person(db, owner=me)
    memory = create_random_memory(db, owner=me)
    memory.person_id = person.id
    db.add(memory)
    db.commit()

    response = client.delete(
        f"{PERSONS_URL}/{person.id}", headers=normal_user_token_headers
    )
    assert response.status_code == 200
    db.expire_all()
    kept = db.get(Memory, memory.id)
    assert kept is not None
    assert kept.person_id is None


def test_outsider_403_every_person_endpoint(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    person = create_random_person(db)
    url = f"{PERSONS_URL}/{person.id}"
    responses = [
        client.get(url, headers=normal_user_token_headers),
        client.patch(url, headers=normal_user_token_headers, json={"name": "x"}),
        client.delete(url, headers=normal_user_token_headers),
    ]
    for response in responses:
        assert response.status_code == 403
        assert response.json()["detail"] == "Not enough permissions"
    assert db.get(Person, person.id) is not None


def test_superuser_cannot_access_others_persons(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    person = create_random_person(db)
    memory = create_random_memory(db)
    url = f"{PERSONS_URL}/{person.id}"
    assert client.get(url, headers=superuser_token_headers).status_code == 403
    response = client.patch(url, headers=superuser_token_headers, json={"name": "x"})
    assert response.status_code == 403
    assert client.delete(url, headers=superuser_token_headers).status_code == 403
    listed = client.get(f"{PERSONS_URL}/", headers=superuser_token_headers).json()
    assert str(person.id) not in {item["id"] for item in listed["data"]}
    # Linking a stranger's memory to a stranger's person
    link = client.put(
        f"{MEMORIES_URL}/{memory.id}/person",
        headers=superuser_token_headers,
        json={"person_id": str(person.id)},
    )
    assert link.status_code == 403


def test_link_memory_to_person(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    me = get_normal_user(db)
    person = create_random_person(db, owner=me)
    memory = create_random_memory(db, owner=me)
    url = f"{MEMORIES_URL}/{memory.id}/person"

    response = client.put(
        url, headers=normal_user_token_headers, json={"person_id": str(person.id)}
    )
    assert response.status_code == 200
    assert response.json()["person_id"] == str(person.id)
    # Linking leaves the free-text name alone
    assert response.json()["person_name"] == memory.person_name

    response = client.put(
        url, headers=normal_user_token_headers, json={"person_id": None}
    )
    assert response.status_code == 200
    assert response.json()["person_id"] is None


def test_link_memory_not_found(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    me = get_normal_user(db)
    person = create_random_person(db, owner=me)
    memory = create_random_memory(db, owner=me)

    response = client.put(
        f"{MEMORIES_URL}/{uuid.uuid4()}/person",
        headers=normal_user_token_headers,
        json={"person_id": str(person.id)},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Memory not found"

    response = client.put(
        f"{MEMORIES_URL}/{memory.id}/person",
        headers=normal_user_token_headers,
        json={"person_id": str(uuid.uuid4())},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Person not found"


def test_link_foreign_memory_or_person_403(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    me = get_normal_user(db)
    my_person = create_random_person(db, owner=me)
    my_memory = create_random_memory(db, owner=me)
    foreign_person = create_random_person(db)
    foreign_memory = create_random_memory(db)

    response = client.put(
        f"{MEMORIES_URL}/{foreign_memory.id}/person",
        headers=normal_user_token_headers,
        json={"person_id": str(my_person.id)},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"

    response = client.put(
        f"{MEMORIES_URL}/{my_memory.id}/person",
        headers=normal_user_token_headers,
        json={"person_id": str(foreign_person.id)},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"

    db.expire_all()
    for memory in (my_memory, foreign_memory):
        stored = db.get(Memory, memory.id)
        assert stored is not None
        assert stored.person_id is None


def test_delete_user_cascades_persona_data(db: Session) -> None:
    owner = crud.create_user(
        session=db,
        user_create=UserCreate(email=random_email(), password=random_lower_string()),
    )
    person = create_random_person(db, owner=owner)
    person_id = person.id

    db.delete(owner)
    db.commit()

    db.expire_all()
    assert db.get(Person, person_id) is None
