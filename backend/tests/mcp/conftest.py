from collections.abc import AsyncIterator, Callable

import pytest
from mcp import Client

from app.core.config import settings
from app.mcp.server import build_server
from app.models import User
from tests.utils.mcp import token_for


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def sign_in(monkeypatch: pytest.MonkeyPatch) -> Callable[[User], str]:
    """Make the server act as `user` (what MCP_ACCESS_TOKEN does); returns the token."""

    def sign_in_as(user: User) -> str:
        token = token_for(user)
        monkeypatch.setattr(settings, "MCP_ACCESS_TOKEN", token)
        return token

    return sign_in_as


@pytest.fixture
async def client() -> AsyncIterator[Client]:
    """An in-memory client of the real server: same protocol layer, no process."""
    async with Client(build_server()) as connected:
        yield connected
