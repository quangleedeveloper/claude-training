from fastapi import HTTPException
from mcp.server.mcpserver.exceptions import ToolError
from sqlmodel import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.mcp.errors import CREDENTIALS
from app.models import User


def current_user(session: Session) -> User:
    """The person the server acts as, checked on every call.

    It applies the web API's own checks (valid token, user exists, user active) and
    reads the token each time, so a token that expires or a user who is deactivated
    while the server runs is refused on the next call. Every failure gives the same
    message, so it never says which check failed.
    """
    token = settings.MCP_ACCESS_TOKEN
    if not token:
        raise ToolError(CREDENTIALS)
    try:
        return get_current_user(session, token)
    except HTTPException:
        raise ToolError(CREDENTIALS) from None
