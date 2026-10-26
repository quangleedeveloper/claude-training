import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.memory import create_random_memory

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
