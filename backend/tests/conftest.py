from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from app.api.deps import get_media_processor
from app.core.config import settings
from app.core.db import engine, init_db
from app.main import app
from app.models import Item, Memory, MemoryFile, User
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


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session]:
    with Session(engine) as session:
        init_db(session)
        yield session
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
