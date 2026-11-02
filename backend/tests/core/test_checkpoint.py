import logging

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session

from app import main
from app.core import checkpoint
from app.core.checkpoint import SETUP_LOCK_KEY, setup_checkpoint_tables
from app.core.config import settings

TABLES = (
    "checkpoint_writes",
    "checkpoint_blobs",
    "checkpoints",
    "checkpoint_migrations",
)


def tables_exist(db: Session) -> bool:
    db.rollback()  # end any transaction so we see the current catalog
    found = all(
        db.execute(text("select to_regclass(:name)"), {"name": name}).scalar_one()
        for name in TABLES
    )
    # Leave no transaction open: setup builds an index concurrently, which waits for
    # every open transaction, this session's included
    db.rollback()
    return found


def test_connection_string_uses_a_plain_postgres_url() -> None:
    url = checkpoint._connection_string()
    assert url.startswith("postgresql://")
    assert "+psycopg" not in url
    assert "options=" not in url


def test_connection_string_can_carry_a_statement_timeout() -> None:
    url = checkpoint._connection_string(60_000)
    assert url.endswith("?options=-c%20statement_timeout%3D60000")


def test_connection_string_adds_the_timeout_to_existing_parameters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        settings, "DATABASE_URL", "postgresql+psycopg://u:p@host/db?sslmode=require"
    )
    url = checkpoint._connection_string(1000)
    assert url == (
        "postgresql://u:p@host/db?sslmode=require&options=-c%20statement_timeout%3D1000"
    )


def test_setup_creates_missing_tables(db: Session) -> None:
    db.rollback()
    db.execute(text(f"DROP TABLE IF EXISTS {', '.join(TABLES)}"))
    db.commit()
    assert not tables_exist(db)

    setup_checkpoint_tables()

    assert tables_exist(db)


def test_setup_can_run_again_and_releases_its_lock(db: Session) -> None:
    setup_checkpoint_tables()
    setup_checkpoint_tables()

    assert tables_exist(db)
    with psycopg.connect(checkpoint._connection_string(), autocommit=True) as other:
        (acquired,) = other.execute(
            "SELECT pg_try_advisory_lock(%s)", (SETUP_LOCK_KEY,)
        ).fetchone() or (False,)
        assert acquired, "setup left the advisory lock held"
        other.execute("SELECT pg_advisory_unlock(%s)", (SETUP_LOCK_KEY,))


def test_app_startup_creates_the_tables(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(main, "setup_checkpoint_tables", lambda: calls.append("setup"))

    with TestClient(main.app):
        pass

    assert calls == ["setup"]


def test_app_still_starts_when_the_tables_cannot_be_created(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def broken() -> None:
        raise RuntimeError("no permission")

    monkeypatch.setattr(main, "setup_checkpoint_tables", broken)

    with caplog.at_level(logging.ERROR, logger="app.main"):
        with TestClient(main.app) as client:
            response = client.get(f"{settings.API_V1_STR}/utils/health-check/")

    assert response.status_code == 200
    assert "Could not create the LangGraph checkpoint tables" in caplog.text
