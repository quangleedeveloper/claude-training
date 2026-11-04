from datetime import timedelta
from typing import Any

from mcp import Client
from mcp.types import CallToolResult, TextContent

from app.core import security
from app.models import User


def token_for(user: User, expires_in: timedelta = timedelta(minutes=30)) -> str:
    """A real access token for `user`, like the one POST /login/access-token gives."""
    return security.create_access_token(user.id, expires_in)


async def call(client: Client, tool: str, **arguments: Any) -> CallToolResult:
    """Call a tool; a refused call comes back with `is_error` set instead of raising."""
    return await client.call_tool(tool, arguments)


def text_of(result: CallToolResult) -> str:
    """All the text a model would read in the result."""
    return " ".join(
        block.text for block in result.content if isinstance(block, TextContent)
    )


def listed(result: CallToolResult) -> list[dict[str, Any]]:
    """The items of a tool that returns a list, after checking the call succeeded."""
    assert not result.is_error, text_of(result)
    assert result.structured_content is not None
    items: list[dict[str, Any]] = result.structured_content["result"]
    return items
