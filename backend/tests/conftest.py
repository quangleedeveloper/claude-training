from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session, delete

from app.core.checkpoint import setup_checkpoint_tables
from app.core.config import settings
from app.core.db import engine, init_db
from app.core.llm import get_llm_client
from app.main import app
from app.models import ExtractedMemory, Item, Memory, MemoryFile, User
from app.services.processing import get_media_processor
from tests.utils.llm import FakeLLMClient
from tests.utils.memory_file import FakeMediaProcessor
from tests.utils.user import authentication_token_from_email
from tests.utils.utils import get_superuser_token_headers


@pytest.fixture(scope="session", autouse=True)
def upload_dir(tmp_path_factory: pytest.TempPathFactory) -> Generator[Path]:
    """Keep test uploads out of the real upload directory."""
    path = tmp_path_factory.mktemp("uploads")
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(settings, "UPLOAD_DIR", path)
        yield path


@pytest.fixture(autouse=True)
def media_processor() -> Generator[FakeMediaProcessor]:
    """Tests never run the real processor; set `.error` to simulate a failure."""
    processor = FakeMediaProcessor()
    app.dependency_overrides[get_media_processor] = lambda: processor
    yield processor
    app.dependency_overrides.pop(get_media_processor, None)


@pytest.fixture(autouse=True)
def llm_client() -> Generator[FakeLLMClient]:
    """Tests never call Ollama; set `.error` to simulate it being down."""
    llm = FakeLLMClient()
    app.dependency_overrides[get_llm_client] = lambda: llm
    yield llm
    app.dependency_overrides.pop(get_llm_client, None)


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session]:
    # Before the session below opens a transaction, which would block the index build
    setup_checkpoint_tables()
    with Session(engine) as session:
        init_db(session)
        yield session
        session.execute(delete(ExtractedMemory))
        for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
            session.execute(text(f"DELETE FROM {table}"))
        statement = delete(MemoryFile)
        session.execute(statement)
        statement = delete(Memory)
        session.execute(statement)
        statement = delete(Item)
        session.execute(statement)
        statement = delete(User)
        session.execute(statement)
        session.commit()


@pytest.fixture(scope="module")
def client() -> Generator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    return get_superuser_token_headers(client)


@pytest.fixture(scope="module")
def normal_user_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    return authentication_token_from_email(
        client=client, email=settings.EMAIL_TEST_USER, db=db
    )
