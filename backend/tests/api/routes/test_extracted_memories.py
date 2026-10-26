import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.api.deps import get_db
from app.core.config import settings
from app.core.db import engine
from app.main import app
from app.models import ExtractedStatus
from tests.utils.extracted_memory import create_random_extracted_memory
from tests.utils.llm import FakeLLMClient
from tests.utils.memory import create_random_memory
from tests.utils.memory_file import create_random_memory_file


def url(memory_id: uuid.UUID, extracted_id: uuid.UUID | None = None) -> str:
    base = f"{settings.API_V1_STR}/memories/{memory_id}/extracted/"
    return base if extracted_id is None else f"{base}{extracted_id}"


def test_read_extracted_memories(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    memory = create_random_memory(db)
    create_random_extracted_memory(db, memory, content="First fact.")
    create_random_extracted_memory(db, memory, content="Second fact.")

    response = client.get(url(memory.id), headers=superuser_token_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert {item["content"] for item in body["data"]} == {"First fact.", "Second fact."}
    assert "embedding" not in body["data"][0]


def test_read_extracted_memories_for_one_file(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    memory = create_random_memory(db)
    memory_file = create_random_memory_file(db, memory)
    create_random_extracted_memory(db, memory, memory_file, content="From the photo.")
    create_random_extracted_memory(db, memory, content="From the story.")

    response = client.get(
        url(memory.id),
        headers=superuser_token_headers,
        params={"file_id": str(memory_file.id)},
    )

    assert response.status_code == 200
    assert [i["content"] for i in response.json()["data"]] == ["From the photo."]


def test_read_extracted_memories_memory_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(url(uuid.uuid4()), headers=superuser_token_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Memory not found"


def test_read_extracted_memories_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    memory = create_random_memory(db)
    response = client.get(url(memory.id), headers=normal_user_token_headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"


def test_update_extracted_memory_edits_and_reembeds(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    extracted = create_random_extracted_memory(db, content="Dad fished.")
    old_embedding = list(extracted.embedding)

    response = client.patch(
        url(extracted.memory_id, extracted.id),
        headers=superuser_token_headers,
        json={"content": "Dad fished at Lake Erie.", "location": "Lake Erie"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["content"] == "Dad fished at Lake Erie."
    assert body["location"] == "Lake Erie"
    assert body["status"] == ExtractedStatus.EDITED
    db.refresh(extracted)
    assert list(extracted.embedding) != old_embedding


def test_update_extracted_memory_reject_and_restore(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    extracted = create_random_extracted_memory(db)
    path = url(extracted.memory_id, extracted.id)

    rejected = client.patch(
        path, headers=superuser_token_headers, json={"rejected": True}
    )
    restored = client.patch(
        path, headers=superuser_token_headers, json={"rejected": False}
    )

    assert rejected.json()["status"] == ExtractedStatus.REJECTED
    assert restored.json()["status"] == ExtractedStatus.ACTIVE


def test_update_extracted_memory_restore_keeps_edited_status(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    extracted = create_random_extracted_memory(db, status=ExtractedStatus.EDITED)

    response = client.patch(
        url(extracted.memory_id, extracted.id),
        headers=superuser_token_headers,
        json={"rejected": False},
    )

    assert response.json()["status"] == ExtractedStatus.EDITED


def test_update_extracted_memory_model_down(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    llm_client: FakeLLMClient,
) -> None:
    extracted = create_random_extracted_memory(db)
    llm_client.error = "Could not reach Ollama"

    response = client.patch(
        url(extracted.memory_id, extracted.id),
        headers=superuser_token_headers,
        json={"content": "New wording."},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Could not reach Ollama"


def test_update_extracted_memory_validation(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    extracted = create_random_extracted_memory(db)
    response = client.patch(
        url(extracted.memory_id, extracted.id),
        headers=superuser_token_headers,
        json={"content": ""},
    )
    assert response.status_code == 422


def test_update_extracted_memory_not_found(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    memory = create_random_memory(db)
    response = client.patch(
        url(memory.id, uuid.uuid4()),
        headers=superuser_token_headers,
        json={"rejected": True},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Extracted memory not found"


def test_update_extracted_memory_of_another_memory_is_not_found(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    extracted = create_random_extracted_memory(db)
    other = create_random_memory(db)
    response = client.patch(
        url(other.id, extracted.id),
        headers=superuser_token_headers,
        json={"rejected": True},
    )
    assert response.status_code == 404


def test_update_extracted_memory_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    extracted = create_random_extracted_memory(db)
    response = client.patch(
        url(extracted.memory_id, extracted.id),
        headers=normal_user_token_headers,
        json={"rejected": True},
    )
    assert response.status_code == 403


def test_delete_extracted_memory(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    extracted = create_random_extracted_memory(db)
    path = url(extracted.memory_id, extracted.id)

    response = client.delete(path, headers=superuser_token_headers)

    assert response.status_code == 200
    assert response.json()["message"] == "Extracted memory deleted successfully"
    assert (
        client.get(url(extracted.memory_id), headers=superuser_token_headers).json()[
            "count"
        ]
        == 0
    )


def test_delete_extracted_memory_not_found(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    memory = create_random_memory(db)
    response = client.delete(
        url(memory.id, uuid.uuid4()), headers=superuser_token_headers
    )
    assert response.status_code == 404


def test_delete_extracted_memory_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    extracted = create_random_extracted_memory(db)
    response = client.delete(
        url(extracted.memory_id, extracted.id), headers=normal_user_token_headers
    )
    assert response.status_code == 403


def test_deleting_a_file_removes_what_was_extracted_from_it(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    memory = create_random_memory(db)
    memory_file = create_random_memory_file(db, memory)
    create_random_extracted_memory(db, memory, memory_file, content="From the photo.")

    client.delete(
        f"{settings.API_V1_STR}/memories/{memory.id}/files/{memory_file.id}",
        headers=superuser_token_headers,
    )

    response = client.get(url(memory.id), headers=superuser_token_headers)
    assert response.json()["count"] == 0


@pytest.mark.parametrize("field", ["content", "category", "people"])
def test_update_extracted_memory_null_for_a_required_field(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    field: str,
) -> None:
    extracted = create_random_extracted_memory(db)

    response = client.patch(
        url(extracted.memory_id, extracted.id),
        headers=superuser_token_headers,
        json={field: None},
    )

    assert response.status_code == 422
    db.refresh(extracted)
    assert extracted.status == ExtractedStatus.ACTIVE


def test_update_extracted_memory_null_clears_optional_fields(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    extracted = create_random_extracted_memory(db)
    extracted.location = "Lake Erie"
    extracted.event_date_text = "summer 1998"
    db.add(extracted)
    db.commit()

    response = client.patch(
        url(extracted.memory_id, extracted.id),
        headers=superuser_token_headers,
        json={"location": None, "event_date_text": None},
    )

    assert response.status_code == 200
    assert response.json()["location"] is None
    assert response.json()["event_date_text"] is None


def test_update_extracted_memory_editing_a_rejected_item_is_refused(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    extracted = create_random_extracted_memory(db, status=ExtractedStatus.REJECTED)

    response = client.patch(
        url(extracted.memory_id, extracted.id),
        headers=superuser_token_headers,
        json={"content": "Sneaky edit."},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Restore the item before editing it"
    db.refresh(extracted)
    assert extracted.status == ExtractedStatus.REJECTED
    assert extracted.content != "Sneaky edit."


def test_update_extracted_memory_restore_and_edit_in_one_request(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    extracted = create_random_extracted_memory(db, status=ExtractedStatus.REJECTED)

    response = client.patch(
        url(extracted.memory_id, extracted.id),
        headers=superuser_token_headers,
        json={"rejected": False, "content": "Back with new wording."},
    )

    assert response.status_code == 200
    assert response.json()["status"] == ExtractedStatus.EDITED
    assert response.json()["content"] == "Back with new wording."


def test_rejecting_and_restoring_an_edited_item_keeps_it_edited(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    extracted = create_random_extracted_memory(db)
    path = url(extracted.memory_id, extracted.id)
    client.patch(path, headers=superuser_token_headers, json={"content": "Fixed."})

    rejected = client.patch(
        path, headers=superuser_token_headers, json={"rejected": True}
    )
    restored = client.patch(
        path, headers=superuser_token_headers, json={"rejected": False}
    )

    assert rejected.json()["status"] == ExtractedStatus.REJECTED
    # Back to edited, so a re-extraction still leaves the corrected wording alone
    assert restored.json()["status"] == ExtractedStatus.EDITED
    db.refresh(extracted)
    assert extracted.was_edited is True


def test_update_extracted_memory_holds_no_transaction_during_the_model_call(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    llm_client: FakeLLMClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extracted = create_random_extracted_memory(db)
    request_sessions: list[Session] = []

    def tracked_session() -> Generator[Session]:
        with Session(engine) as session:
            request_sessions.append(session)
            yield session

    app.dependency_overrides[get_db] = tracked_session
    in_transaction_during_embed: list[bool] = []
    real_embed = llm_client.embed

    def embed(texts: list[str]) -> list[list[float]]:
        in_transaction_during_embed.append(request_sessions[0].in_transaction())
        return real_embed(texts)

    monkeypatch.setattr(llm_client, "embed", embed)
    try:
        response = client.patch(
            url(extracted.memory_id, extracted.id),
            headers=superuser_token_headers,
            json={"content": "New wording."},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert in_transaction_during_embed == [False]
