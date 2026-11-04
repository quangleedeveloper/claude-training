import logging
import time
from collections.abc import Callable
from functools import partial

import anyio.to_thread
from fastapi import HTTPException
from mcp.server.mcpserver.exceptions import ToolError
from sqlmodel import Session

from app.core.db import engine
from app.mcp.auth import current_user
from app.mcp.errors import FAILED, to_tool_error
from app.models import User

logger = logging.getLogger("app.mcp")


def _run_as_user[T](tool: str, work: Callable[[Session, User], T]) -> T:
    started = time.monotonic()
    with Session(engine) as session:
        try:
            user = current_user(session)
            user_id = user.id
            result = work(session, user)
        except ToolError:
            logger.info("mcp tool refused: tool=%s", tool)
            raise
        except HTTPException as exc:
            logger.info("mcp tool refused: tool=%s status=%s", tool, exc.status_code)
            raise to_tool_error(exc) from None
        except Exception as exc:
            # Only the type: an exception's text or traceback could hold memory text
            logger.error("mcp tool failed: tool=%s error=%s", tool, type(exc).__name__)
            raise ToolError(FAILED) from None
    elapsed_ms = round((time.monotonic() - started) * 1000)
    logger.info("mcp tool ok: tool=%s user=%s ms=%d", tool, user_id, elapsed_ms)
    return result


async def run_as_user[T](tool: str, work: Callable[[Session, User], T]) -> T:
    """Run one tool call as the signed-in person, in its own database session.

    Every tool goes through here, so they all share the same sign-in, the same
    generic errors and the same log line. Logs hold the tool name, ids and timings
    only, never a question, an answer, memory text or the token (NFR-3).

    The work runs in a worker thread, so a slow call (a local model answering) does
    not freeze the server while it waits.
    """
    return await anyio.to_thread.run_sync(partial(_run_as_user, tool, work))
