import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.core.storage import LocalFileStorage
from app.main import app
from app.services.processing import GENERIC_FAILURE
from tests.utils.memory import create_random_memory
from tests.utils.memory_file import (
    MP3_BYTES,
    MP4_BYTES,
    PNG_BYTES,
    FakeMediaProcessor,
    create_random_memory_file,
)
from tests.utils.user import create_random_user

MEMORIES_URL = f"{settings.API_V1_STR}/memories"
MEMORY_DATA = {"title": "Fishing", "person_name": "Grandpa Tom", "content": "Lake"}


def files_url(memory_id: uuid.UUID | str) -> str:
    return f"{MEMORIES_URL}/{memory_id}/files/"


def upload(
    client: TestClient,
    headers: dict[str, str],
    memory_id: uuid.UUID | str,
    *files: tuple[str, bytes, str],
) -> dict[str, object]:
    multipart = [("files", (name, data, mime)) for name, data, mime in files]
    response = client.post(files_url(memory_id), headers=headers, files=multipart)
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


def create_memory_via_api(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post(f"{MEMORIES_URL}/", headers=headers, json=MEMORY_DATA)
    assert response.status_code == 200
    return response.json()["id"]  # type: ignore[no-any-return]


def stored_files(upload_dir: Path, memory_id: uuid.UUID | str) -> list[Path]:
    directory = upload_dir / str(memory_id)
    return sorted(directory.iterdir()) if directory.exists() else []


def test_upload_memory_files(
    client: TestClient, normal_user_token_headers: dict[str, str], upload_dir: Path
) -> None:
    memory_id = create_memory_via_api(client, normal_user_token_headers)
    result = upload(
        client,
        normal_user_token_headers,
        memory_id,
        ("photo.png", PNG_BYTES, "image/png"),
        ("voice.mp3", MP3_BYTES, "audio/mpeg"),
        ("clip.mp4", MP4_BYTES, "video/mp4"),
    )
    assert result["rejected"] == []
    uploaded = result["uploaded"]
    assert isinstance(uploaded, list)
    assert [f["kind"] for f in uploaded] == ["image", "audio", "video"]
    assert uploaded[0]["filename"] == "photo.png"
    assert uploaded[0]["content_type"] == "image/png"
    assert uploaded[0]["size_bytes"] == len(PNG_BYTES)
    assert uploaded[0]["status"] == "uploaded"
    assert len(stored_files(upload_dir, memory_id)) == 3


def test_upload_memory_files_are_processed(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    media_processor: FakeMediaProcessor,
) -> None:
    memory_id = create_memory_via_api(client, normal_user_token_headers)
    upload(
        client,
        normal_user_token_headers,
        memory_id,
        ("photo.png", PNG_BYTES, "image/png"),
    )
    response = client.get(files_url(memory_id), headers=normal_user_token_headers)
    assert response.status_code == 200
    content = response.json()
    assert content["count"] == 1
    assert content["data"][0]["status"] == "processed"
    assert content["data"][0]["processed_at"] is not None
    assert len(media_processor.processed) == 1


def test_upload_memory_files_mixed_batch(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    memory_id = create_memory_via_api(client, normal_user_token_headers)
    result = upload(
        client,
        normal_user_token_headers,
        memory_id,
        ("photo.png", PNG_BYTES, "image/png"),
        ("notes.txt", b"just some text", "text/plain"),
    )
    assert len(result["uploaded"]) == 1  # type: ignore[arg-type]
    rejected = result["rejected"]
    assert isinstance(rejected, list)
    assert rejected[0]["filename"] == "notes.txt"
    assert "Unsupported file type" in rejected[0]["reason"]


def test_upload_memory_files_signature_mismatch(
    client: TestClient, normal_user_token_headers: dict[str, str], upload_dir: Path
) -> None:
    memory_id = create_memory_via_api(client, normal_user_token_headers)
    result = upload(
        client,
        normal_user_token_headers,
        memory_id,
        ("photo.png", b"MZ\x90\x00" + b"\x00" * 32, "image/png"),
    )
    assert result["uploaded"] == []
    rejected = result["rejected"]
    assert isinstance(rejected, list)
    assert "does not match" in rejected[0]["reason"]
    assert stored_files(upload_dir, memory_id) == []


def test_upload_memory_files_extension_kind_mismatch(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    memory_id = create_memory_via_api(client, normal_user_token_headers)
    result = upload(
        client,
        normal_user_token_headers,
        memory_id,
        ("voice.png", MP3_BYTES, "image/png"),
    )
    assert result["uploaded"] == []


def test_upload_memory_files_too_large(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    upload_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "MAX_IMAGE_BYTES", len(PNG_BYTES) - 1)
    memory_id = create_memory_via_api(client, normal_user_token_headers)
    result = upload(
        client,
        normal_user_token_headers,
        memory_id,
        ("photo.png", PNG_BYTES, "image/png"),
        ("voice.mp3", MP3_BYTES, "audio/mpeg"),
    )
    assert len(result["uploaded"]) == 1  # type: ignore[arg-type]
    rejected = result["rejected"]
    assert isinstance(rejected, list)
    assert rejected[0]["filename"] == "photo.png"
    assert "larger than" in rejected[0]["reason"]
    assert len(stored_files(upload_dir, memory_id)) == 1


def test_upload_memory_files_too_many(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "MAX_FILES_PER_UPLOAD", 1)
    memory_id = create_memory_via_api(client, normal_user_token_headers)
    response = client.post(
        files_url(memory_id),
        headers=normal_user_token_headers,
        files=[
            ("files", ("a.png", PNG_BYTES, "image/png")),
            ("files", ("b.png", PNG_BYTES, "image/png")),
        ],
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Too many files: at most 1 per upload"


def test_upload_memory_files_no_files(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    memory_id = create_memory_via_api(client, normal_user_token_headers)
    response = client.post(files_url(memory_id), headers=normal_user_token_headers)
    assert response.status_code == 422


def test_upload_memory_files_sanitizes_filename(
    client: TestClient, normal_user_token_headers: dict[str, str], upload_dir: Path
) -> None:
    memory_id = create_memory_via_api(client, normal_user_token_headers)
    result = upload(
        client,
        normal_user_token_headers,
        memory_id,
        ("../../evil.png", PNG_BYTES, "image/png"),
    )
    uploaded = result["uploaded"]
    assert isinstance(uploaded, list)
    assert uploaded[0]["filename"] == "evil.png"
    # The stored name is generated by the server, never taken from the client
    assert [p.name for p in stored_files(upload_dir, memory_id)] != ["evil.png"]
    assert not (upload_dir.parent / "evil.png").exists()


def test_upload_memory_files_memory_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.post(
        files_url(uuid.uuid4()),
        headers=superuser_token_headers,
        files=[("files", ("a.png", PNG_BYTES, "image/png"))],
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Memory not found"


def test_upload_memory_files_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    memory = create_random_memory(db)
    response = client.post(
        files_url(memory.id),
        headers=normal_user_token_headers,
        files=[("files", ("a.png", PNG_BYTES, "image/png"))],
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"


def test_superuser_can_upload_to_any_memory(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    memory = create_random_memory(db)
    result = upload(
        client,
        superuser_token_headers,
        memory.id,
        ("a.png", PNG_BYTES, "image/png"),
    )
    assert len(result["uploaded"]) == 1  # type: ignore[arg-type]


def test_read_memory_files_memory_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(files_url(uuid.uuid4()), headers=superuser_token_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Memory not found"


def test_read_memory_files_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    memory = create_random_memory(db)
    response = client.get(files_url(memory.id), headers=normal_user_token_headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"


def test_failed_processing_can_be_retried(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    media_processor: FakeMediaProcessor,
) -> None:
    media_processor.error = "transcoder crashed"
    memory_id = create_memory_via_api(client, normal_user_token_headers)
    upload(
        client,
        normal_user_token_headers,
        memory_id,
        ("photo.png", PNG_BYTES, "image/png"),
    )
    listing = client.get(files_url(memory_id), headers=normal_user_token_headers)
    failed = listing.json()["data"][0]
    assert failed["status"] == "failed"
    # The crash text is logged; the user is only told that processing failed
    assert failed["error_message"] == GENERIC_FAILURE
    assert "transcoder" not in failed["error_message"]

    media_processor.error = None
    response = client.post(
        f"{files_url(memory_id)}{failed['id']}/retry",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "uploaded"
    assert response.json()["error_message"] is None

    listing = client.get(files_url(memory_id), headers=normal_user_token_headers)
    assert listing.json()["data"][0]["status"] == "processed"


def test_retry_memory_file_only_when_failed(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    memory_id = create_memory_via_api(client, normal_user_token_headers)
    upload(
        client,
        normal_user_token_headers,
        memory_id,
        ("photo.png", PNG_BYTES, "image/png"),
    )
    file_id = client.get(
        files_url(memory_id), headers=normal_user_token_headers
    ).json()["data"][0]["id"]
    response = client.post(
        f"{files_url(memory_id)}{file_id}/retry", headers=normal_user_token_headers
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Only failed files can be retried"


def test_retry_memory_file_not_found(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    memory_id = create_memory_via_api(client, normal_user_token_headers)
    response = client.post(
        f"{files_url(memory_id)}{uuid.uuid4()}/retry",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "File not found"


def test_memory_file_of_another_memory_is_not_found(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    memory_file = create_random_memory_file(db)
    other_memory = create_random_memory(db)
    response = client.get(
        f"{files_url(other_memory.id)}{memory_file.id}/content",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "File not found"


def test_retry_memory_file_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    memory_file = create_random_memory_file(db)
    response = client.post(
        f"{files_url(memory_file.memory_id)}{memory_file.id}/retry",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"


def test_read_memory_file_content(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    memory_file = create_random_memory_file(db)
    response = client.get(
        f"{files_url(memory_file.memory_id)}{memory_file.id}/content",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.content == PNG_BYTES
    assert response.headers["content-type"] == "image/png"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_read_memory_file_content_missing_on_disk(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    memory_file = create_random_memory_file(db)
    LocalFileStorage(settings.UPLOAD_DIR).delete(memory_file.storage_key)
    response = client.get(
        f"{files_url(memory_file.memory_id)}{memory_file.id}/content",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "File content not found"


def test_read_memory_file_content_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    memory_file = create_random_memory_file(db)
    response = client.get(
        f"{files_url(memory_file.memory_id)}{memory_file.id}/content",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403


def test_delete_memory_file(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    memory_file = create_random_memory_file(db)
    storage = LocalFileStorage(settings.UPLOAD_DIR)
    assert storage.exists(memory_file.storage_key)
    response = client.delete(
        f"{files_url(memory_file.memory_id)}{memory_file.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["message"] == "File deleted successfully"
    assert not storage.exists(memory_file.storage_key)
    listing = client.get(
        files_url(memory_file.memory_id), headers=superuser_token_headers
    )
    assert listing.json()["count"] == 0


def test_delete_memory_file_not_found(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    memory = create_random_memory(db)
    response = client.delete(
        f"{files_url(memory.id)}{uuid.uuid4()}", headers=superuser_token_headers
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "File not found"


def test_delete_memory_file_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    memory_file = create_random_memory_file(db)
    response = client.delete(
        f"{files_url(memory_file.memory_id)}{memory_file.id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403
    assert LocalFileStorage(settings.UPLOAD_DIR).exists(memory_file.storage_key)


def test_delete_memory_removes_its_files(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    memory_file = create_random_memory_file(db)
    storage = LocalFileStorage(settings.UPLOAD_DIR)
    response = client.delete(
        f"{MEMORIES_URL}/{memory_file.memory_id}", headers=superuser_token_headers
    )
    assert response.status_code == 200
    assert not storage.exists(memory_file.storage_key)


def test_delete_user_removes_their_memory_files(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    user = create_random_user(db)
    memory = create_random_memory(db)
    memory.owner_id = user.id
    db.add(memory)
    db.commit()
    memory_file = create_random_memory_file(db, memory)
    storage = LocalFileStorage(settings.UPLOAD_DIR)
    assert storage.exists(memory_file.storage_key)
    response = client.delete(
        f"{settings.API_V1_STR}/users/{user.id}", headers=superuser_token_headers
    )
    assert response.status_code == 200
    assert not storage.exists(memory_file.storage_key)


def test_upload_memory_files_storage_failure_rejects_only_that_file(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_to_save(*args: object, **kwargs: object) -> int:
        raise OSError("disk full", args, kwargs)

    monkeypatch.setattr(LocalFileStorage, "save", fail_to_save)
    memory_id = create_memory_via_api(client, normal_user_token_headers)
    result = upload(
        client,
        normal_user_token_headers,
        memory_id,
        ("photo.png", PNG_BYTES, "image/png"),
    )
    assert result["uploaded"] == []
    rejected = result["rejected"]
    assert isinstance(rejected, list)
    assert rejected[0]["reason"] == "The file could not be stored, please try again"


def test_upload_memory_files_database_failure_removes_stored_bytes(
    normal_user_token_headers: dict[str, str],
    upload_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_to_record(*args: object, **kwargs: object) -> None:
        raise RuntimeError("database unavailable", args, kwargs)

    monkeypatch.setattr(crud, "create_memory_file", fail_to_record)
    with TestClient(app, raise_server_exceptions=False) as client:
        memory_id = create_memory_via_api(client, normal_user_token_headers)
        response = client.post(
            files_url(memory_id),
            headers=normal_user_token_headers,
            files=[("files", ("photo.png", PNG_BYTES, "image/png"))],
        )
    assert response.status_code == 500
    assert stored_files(upload_dir, memory_id) == []
