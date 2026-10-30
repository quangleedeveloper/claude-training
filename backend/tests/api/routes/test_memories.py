import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from tests.utils.memory import create_random_memory
from tests.utils.person import create_random_person
from tests.utils.user import create_random_user

MEMORY_DATA = {
    "title": "Fishing trips",
    "person_name": "Grandpa Tom",
    "content": "He woke us up before dawn every summer.",
}


def test_create_memory(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/memories/",
        headers=superuser_token_headers,
        json=MEMORY_DATA,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["title"] == MEMORY_DATA["title"]
    assert content["person_name"] == MEMORY_DATA["person_name"]
    assert content["content"] == MEMORY_DATA["content"]
    assert "id" in content
    assert "owner_id" in content


def test_create_memory_invalid(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/memories/",
        headers=superuser_token_headers,
        json={**MEMORY_DATA, "title": ""},
    )
    assert response.status_code == 422


def test_read_memory(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    memory = create_random_memory(db)
    response = client.get(
        f"{settings.API_V1_STR}/memories/{memory.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["title"] == memory.title
    assert content["person_name"] == memory.person_name
    assert content["content"] == memory.content
    assert content["id"] == str(memory.id)
    assert content["owner_id"] == str(memory.owner_id)


def test_read_memory_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/memories/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Memory not found"


def test_read_memory_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    memory = create_random_memory(db)
    response = client.get(
        f"{settings.API_V1_STR}/memories/{memory.id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"


def test_read_memories(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    create_random_memory(db)
    create_random_memory(db)
    response = client.get(
        f"{settings.API_V1_STR}/memories/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert len(response.json()["data"]) >= 2


def test_read_memories_only_own_for_normal_user(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    other_memory = create_random_memory(db)
    response = client.get(
        f"{settings.API_V1_STR}/memories/",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    ids = [memory["id"] for memory in response.json()["data"]]
    assert str(other_memory.id) not in ids


def test_update_memory(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    memory = create_random_memory(db)
    data = {"title": "Updated title", "content": "Updated content"}
    response = client.put(
        f"{settings.API_V1_STR}/memories/{memory.id}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["title"] == data["title"]
    assert content["content"] == data["content"]
    assert content["person_name"] == memory.person_name
    assert content["id"] == str(memory.id)


def test_update_memory_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.put(
        f"{settings.API_V1_STR}/memories/{uuid.uuid4()}",
        headers=superuser_token_headers,
        json={"title": "Updated title"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Memory not found"


def test_update_memory_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    memory = create_random_memory(db)
    response = client.put(
        f"{settings.API_V1_STR}/memories/{memory.id}",
        headers=normal_user_token_headers,
        json={"title": "Updated title"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"


def test_update_memory_invalid(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    memory = create_random_memory(db)
    response = client.put(
        f"{settings.API_V1_STR}/memories/{memory.id}",
        headers=superuser_token_headers,
        json={"content": ""},
    )
    assert response.status_code == 422


def test_delete_memory(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    memory = create_random_memory(db)
    response = client.delete(
        f"{settings.API_V1_STR}/memories/{memory.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Memory deleted successfully"


def test_delete_memory_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.delete(
        f"{settings.API_V1_STR}/memories/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Memory not found"


def test_delete_memory_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    memory = create_random_memory(db)
    response = client.delete(
        f"{settings.API_V1_STR}/memories/{memory.id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"


def test_read_memories_filtered_by_person(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    user = crud.get_user_by_email(session=db, email=settings.EMAIL_TEST_USER)
    assert user is not None
    person = create_random_person(db, owner=user)
    linked = create_random_memory(db, owner=user)
    linked.person_id = person.id
    db.add(linked)
    db.commit()
    unlinked = create_random_memory(db, owner=user)
    response = client.get(
        f"{settings.API_V1_STR}/memories/",
        headers=normal_user_token_headers,
        params={"person_id": str(person.id)},
    )
    assert response.status_code == 200
    content = response.json()
    assert [memory["id"] for memory in content["data"]] == [str(linked.id)]
    assert content["count"] == 1
    assert str(unlinked.id) not in [memory["id"] for memory in content["data"]]


def test_read_memories_filtered_by_person_of_another_user(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    other = create_random_user(db)
    person = create_random_person(db, owner=other)
    memory = create_random_memory(db, owner=other)
    memory.person_id = person.id
    db.add(memory)
    db.commit()
    response = client.get(
        f"{settings.API_V1_STR}/memories/",
        headers=normal_user_token_headers,
        params={"person_id": str(person.id)},
    )
    assert response.status_code == 200
    assert response.json() == {"data": [], "count": 0}


def test_read_memories_filter_rejects_a_bad_person_id(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/memories/",
        headers=normal_user_token_headers,
        params={"person_id": "not-a-uuid"},
    )
    assert response.status_code == 422
