import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.services.ask_graph import NO_ANSWER
from tests.utils.extracted_memory import create_random_extracted_memory
from tests.utils.llm import FakeLLMClient
from tests.utils.memory import create_random_memory

SEARCH = f"{settings.API_V1_STR}/search/"
ASK = f"{settings.API_V1_STR}/search/ask"


def test_search_memories(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    memory = create_random_memory(db)
    create_random_extracted_memory(db, memory, content="Grandma baked sourdough")

    response = client.post(
        SEARCH,
        headers=superuser_token_headers,
        json={"query": "sourdough", "memory_id": str(memory.id), "limit": 3},
    )

    assert response.status_code == 200
    (hit,) = response.json()["data"]
    assert hit["item"]["content"] == "Grandma baked sourdough"
    assert hit["memory_title"] == memory.title
    assert hit["score"] > 0


def test_search_memories_validation(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    assert (
        client.post(
            SEARCH, headers=superuser_token_headers, json={"query": ""}
        ).status_code
        == 422
    )
    assert (
        client.post(
            SEARCH, headers=superuser_token_headers, json={"query": "x", "limit": 99}
        ).status_code
        == 422
    )


def test_search_memories_memory_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.post(
        SEARCH,
        headers=superuser_token_headers,
        json={"query": "x", "memory_id": str(uuid.uuid4())},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Memory not found"


def test_search_memories_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    memory = create_random_memory(db)
    response = client.post(
        SEARCH,
        headers=normal_user_token_headers,
        json={"query": "x", "memory_id": str(memory.id)},
    )
    assert response.status_code == 403


def test_search_memories_only_returns_the_users_own_items(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    foreign = create_random_memory(db)
    create_random_extracted_memory(db, foreign, content="someone elses private story")

    response = client.post(
        SEARCH, headers=normal_user_token_headers, json={"query": "private story"}
    )

    assert response.status_code == 200
    assert all(
        hit["item"]["memory_id"] != str(foreign.id) for hit in response.json()["data"]
    )


def test_search_memories_model_down(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    llm_client: FakeLLMClient,
) -> None:
    llm_client.error = "Could not reach Ollama"
    response = client.post(SEARCH, headers=superuser_token_headers, json={"query": "x"})
    assert response.status_code == 503
    assert response.json()["detail"] == "Could not reach Ollama"


def test_ask_memories(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    memory = create_random_memory(db)
    create_random_extracted_memory(db, memory, content="Uncle Joe sailed to Malta")

    response = client.post(
        ASK,
        headers=superuser_token_headers,
        json={"question": "Did Uncle Joe sail to Malta", "memory_id": str(memory.id)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Fake answer citing [1]."
    assert [s["item"]["content"] for s in body["sources"]] == [
        "Uncle Joe sailed to Malta"
    ]


def test_ask_memories_without_a_relevant_memory(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    memory = create_random_memory(db)
    response = client.post(
        ASK,
        headers=superuser_token_headers,
        json={"question": "xylophone quarterback", "memory_id": str(memory.id)},
    )
    assert response.status_code == 200
    assert response.json() == {"answer": NO_ANSWER, "sources": []}


def test_ask_memories_validation(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.post(ASK, headers=superuser_token_headers, json={})
    assert response.status_code == 422


def test_ask_memories_memory_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.post(
        ASK,
        headers=superuser_token_headers,
        json={"question": "x", "memory_id": str(uuid.uuid4())},
    )
    assert response.status_code == 404


def test_ask_memories_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    memory = create_random_memory(db)
    response = client.post(
        ASK,
        headers=normal_user_token_headers,
        json={"question": "x", "memory_id": str(memory.id)},
    )
    assert response.status_code == 403


def test_ask_memories_model_down(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    llm_client: FakeLLMClient,
) -> None:
    llm_client.error = "Could not reach Ollama"
    response = client.post(ASK, headers=superuser_token_headers, json={"question": "x"})
    assert response.status_code == 503
