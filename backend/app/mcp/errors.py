from fastapi import HTTPException
from mcp.server.mcpserver.exceptions import ToolError

# A tool error is read by the assistant's model and shown to a family member, so it
# is one of these fixed texts and never carries a story, a question or a token
# (memorial-privacy rule 3). The first three are the web API's own details.
CREDENTIALS = "Could not validate credentials"
NOT_FOUND = "Person not found"
FORBIDDEN = "Not enough permissions"
FAILED = "Something went wrong"

KNOWN_DETAILS = frozenset({CREDENTIALS, NOT_FOUND, FORBIDDEN})


def to_tool_error(exc: HTTPException) -> ToolError:
    """The tool error for an access check that failed with an `HTTPException`.

    Only the app's known details pass through; anything else becomes `FAILED`.
    """
    detail = exc.detail if isinstance(exc.detail, str) else ""
    return ToolError(detail if detail in KNOWN_DETAILS else FAILED)
