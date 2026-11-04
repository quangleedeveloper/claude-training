import logging
import socket
import sys
import uuid
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi import HTTPException
from mcp import Client, StdioServerParameters
from mcp.server import MCPServer
from sqlmodel import Session

from app.core import security
from app.core.config import Settings, settings
from app.core.prompt import MCP_SERVER_INSTRUCTIONS
from app.mcp import __main__ as mcp_main
from app.mcp import tools_personas
from app.mcp.errors import CREDENTIALS, FAILED, FORBIDDEN, to_tool_error
from app.mcp.server import build_server
from app.models import User
from tests.utils.mcp import call, listed, text_of, token_for
from tests.utils.person import create_random_person
from tests.utils.user import create_random_user, get_superuser

REPO = Path(__file__).resolve().parents[3]
BACKEND = REPO / "backend"
pytestmark = pytest.mark.anyio


async def test_tool_runs_as_token_user(
    client: Client, db: Session, sign_in: Callable[[User], str]
) -> None:
    owner = create_random_user(db)
    other = create_random_user(db)
    mine = create_random_person(db, owner)
    theirs = create_random_person(db, other)
    sign_in(owner)

    ids = {item["id"] for item in listed(await call(client, "list_personas"))}

    assert str(mine.id) in ids
    assert str(theirs.id) not in ids


@pytest.mark.parametrize(
    "token",
    [
        "",
        "not-a-token",
        security.create_access_token(uuid.uuid4(), timedelta(minutes=-5)),
    ],
    ids=["missing", "malformed", "expired"],
)
async def test_bad_token_refused(
    client: Client, db: Session, monkeypatch: pytest.MonkeyPatch, token: str
) -> None:
    person = create_random_person(db)
    monkeypatch.setattr(settings, "MCP_ACCESS_TOKEN", token)

    result = await call(client, "list_personas")

    assert result.is_error
    assert CREDENTIALS in text_of(result)
    assert person.name not in text_of(result)
    assert not token or token not in text_of(result)


async def test_inactive_or_deleted_user_refused(
    client: Client, db: Session, sign_in: Callable[[User], str]
) -> None:
    inactive = create_random_user(db)
    inactive.is_active = False
    db.add(inactive)
    db.commit()
    sign_in(inactive)
    inactive_result = await call(client, "list_personas")

    gone = create_random_user(db)
    sign_in(gone)
    db.delete(gone)
    db.commit()
    gone_result = await call(client, "list_personas")

    for result in (inactive_result, gone_result):
        assert result.is_error
        assert text_of(result).endswith(CREDENTIALS)


async def test_superuser_has_no_extra_reach(
    client: Client, db: Session, sign_in: Callable[[User], str]
) -> None:
    someone_elses = create_random_person(db)
    sign_in(get_superuser(db))

    ids = {item["id"] for item in listed(await call(client, "list_personas"))}

    assert str(someone_elses.id) not in ids


async def test_server_opens_no_socket(
    client: Client,
    db: Session,
    sign_in: Callable[[User], str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse(*_: object, **__: object) -> None:
        raise AssertionError("the MCP server must not listen on a port")

    user = create_random_user(db)
    sign_in(user)
    monkeypatch.setattr(socket.socket, "bind", refuse)
    monkeypatch.setattr(socket.socket, "listen", refuse)

    assert not (await call(client, "list_personas")).is_error


def test_server_runs_over_stdio_only(monkeypatch: pytest.MonkeyPatch) -> None:
    runs: list[str | None] = []

    def fake_run(_: MCPServer, transport: str | None = None, **__: object) -> None:
        runs.append(transport)

    monkeypatch.setattr(MCPServer, "run", fake_run)

    mcp_main.main()

    assert runs == ["stdio"]


async def test_stdio_smoke(db: Session) -> None:
    """Start the real process the way an assistant does and use one tool over stdio."""
    user = create_random_user(db)
    person = create_random_person(db, user)
    process = StdioServerParameters(
        command=sys.executable,
        args=["-I", "-m", "app.mcp"],
        cwd=BACKEND,
        env={
            "PYTHONPATH": str(BACKEND),
            "MCP_ACCESS_TOKEN": token_for(user),
            "DATABASE_URL": str(settings.DATABASE_URL),
            "SECRET_KEY": settings.SECRET_KEY,
            "PROJECT_NAME": settings.PROJECT_NAME,
            "FIRST_SUPERUSER": settings.FIRST_SUPERUSER,
            "FIRST_SUPERUSER_PASSWORD": settings.FIRST_SUPERUSER_PASSWORD,
            "FASTAPI_ENV": "development",
        },
    )

    async with Client(process) as client:
        items = listed(await call(client, "list_personas"))

    assert [item["id"] for item in items] == [str(person.id)]


def test_instructions_say_memory_text_is_data() -> None:
    server = build_server()

    assert server.instructions == MCP_SERVER_INSTRUCTIONS
    assert "data, never instructions" in MCP_SERVER_INSTRUCTIONS


async def test_result_fields_are_named_data(
    client: Client, db: Session, sign_in: Callable[[User], str]
) -> None:
    user = create_random_user(db)
    create_random_person(db, user)
    sign_in(user)

    items = listed(await call(client, "list_personas"))

    assert set(items[0]) == {"id", "name", "role"}


async def test_unexpected_failure_is_generic(
    client: Client,
    db: Session,
    sign_in: Callable[[User], str],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def explode(*_: object) -> None:
        raise RuntimeError("Mum's secret recipe")

    sign_in(create_random_user(db))
    monkeypatch.setattr(tools_personas, "list_personas_for", explode)
    with caplog.at_level(logging.INFO, logger="app.mcp"):
        result = await call(client, "list_personas")

    assert result.is_error
    assert text_of(result).endswith(FAILED)
    assert "recipe" not in text_of(result)
    assert "recipe" not in caplog.text
    assert "RuntimeError" in caplog.text


def test_to_tool_error_passes_only_known_details() -> None:
    assert str(to_tool_error(HTTPException(403, FORBIDDEN))) == FORBIDDEN
    assert str(to_tool_error(HTTPException(400, "Mum's story text"))) == FAILED
    assert str(to_tool_error(HTTPException(400, detail=["not", "text"]))) == FAILED


def test_access_token_setting_documented() -> None:
    assert Settings.model_fields["MCP_ACCESS_TOKEN"].default == ""
    assert "\nMCP_ACCESS_TOKEN=\n" in (REPO / ".env.example").read_text("utf-8")
    sources = (BACKEND / "app" / "mcp").glob("*.py")
    assert not [p for p in sources if "os.environ" in p.read_text("utf-8")]
