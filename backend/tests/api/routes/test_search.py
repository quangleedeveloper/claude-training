import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.api.deps import get_db
from app.core.config import settings
from app.core.db import engine
from app.main import app
from app.services.ask_graph import NO_ANSWER
from tests.utils.extracted_memory import create_random_extracted_memory
from tests.utils.llm import FakeLLMClient
from tests.utils.memory import create_random_memory
from tests.utils.user import get_superuser

SEARCH = f"{settings.API_V1_STR}/search/"
ASK = f"{settings.API_V1_STR}/search/ask"


def test_search_memories(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    memory = create_random_memory(db, get_superuser(db))
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
    memory = create_random_memory(db, get_superuser(db))
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
    memory = create_random_memory(db, get_superuser(db))
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


def test_search_by_a_superuser_is_limited_to_their_own_memories(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    mine = create_random_memory(db, get_superuser(db))
    theirs = create_random_memory(db)
    create_random_extracted_memory(db, mine, content="kumquat jam of mine")
    create_random_extracted_memory(db, theirs, content="kumquat jam of theirs")

    response = client.post(
        SEARCH, headers=superuser_token_headers, json={"query": "kumquat jam"}
    )

    assert response.status_code == 200
    found = {h["item"]["memory_id"] for h in response.json()["data"]}
    assert str(mine.id) in found
    assert str(theirs.id) not in found


def test_search_by_a_superuser_can_ask_for_all_users(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    mine = create_random_memory(db, get_superuser(db))
    theirs = create_random_memory(db)
    create_random_extracted_memory(db, mine, content="quince jam of mine")
    create_random_extracted_memory(db, theirs, content="quince jam of theirs")

    response = client.post(
        SEARCH,
        headers=superuser_token_headers,
        json={"query": "quince jam", "all_users": True, "limit": 20},
    )

    assert response.status_code == 200
    found = {h["item"]["memory_id"] for h in response.json()["data"]}
    assert {str(mine.id), str(theirs.id)} <= found


def test_search_by_a_superuser_in_another_users_memory_needs_all_users(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    theirs = create_random_memory(db)
    create_random_extracted_memory(db, theirs, content="plum chutney recipe")
    body = {"query": "plum chutney", "memory_id": str(theirs.id)}

    default = client.post(SEARCH, headers=superuser_token_headers, json=body)
    explicit = client.post(
        SEARCH, headers=superuser_token_headers, json=body | {"all_users": True}
    )

    assert default.json()["data"] == []
    assert len(explicit.json()["data"]) == 1


def test_search_all_users_is_forbidden_for_a_normal_user(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.post(
        SEARCH,
        headers=normal_user_token_headers,
        json={"query": "x", "all_users": True},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"


def test_ask_by_a_superuser_is_limited_to_their_own_memories(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    theirs = create_random_memory(db)
    create_random_extracted_memory(db, theirs, content="Aunt Rosa grew mangoes")

    default = client.post(
        ASK, headers=superuser_token_headers, json={"question": "Aunt Rosa mangoes"}
    )
    everyone = client.post(
        ASK,
        headers=superuser_token_headers,
        json={"question": "Aunt Rosa mangoes", "all_users": True},
    )

    assert default.json() == {"answer": NO_ANSWER, "sources": []}
    assert [s["item"]["content"] for s in everyone.json()["sources"]] == [
        "Aunt Rosa grew mangoes"
    ]


def test_ask_all_users_is_forbidden_for_a_normal_user(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.post(
        ASK,
        headers=normal_user_token_headers,
        json={"question": "x", "all_users": True},
    )
    assert response.status_code == 403


def test_search_and_ask_hold_no_transaction_during_the_model_call(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    llm_client: FakeLLMClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_sessions: list[Session] = []

    def tracked_session() -> Generator[Session]:
        with Session(engine) as session:
            request_sessions.append(session)
            yield session

    in_transaction_during_embed: list[bool] = []
    real_embed = llm_client.embed

    def embed(texts: list[str]) -> list[list[float]]:
        in_transaction_during_embed.append(request_sessions[-1].in_transaction())
        return real_embed(texts)

    monkeypatch.setattr(llm_client, "embed", embed)
    memory_id = str(create_random_memory(db, get_superuser(db)).id)
    app.dependency_overrides[get_db] = tracked_session
    try:
        # memory_id makes the route read the database before the model is called
        client.post(
            SEARCH,
            headers=superuser_token_headers,
            json={"query": "x", "memory_id": memory_id},
        )
        client.post(
            ASK,
            headers=superuser_token_headers,
            json={"question": "x", "memory_id": memory_id},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert in_transaction_during_embed == [False, False]
