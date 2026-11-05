import logging
import uuid
from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.api.routes.persons import get_person_for_conversation
from app.core.llm import LLMError, get_llm_client
from app.mcp.calls import run_as_user
from app.models import SearchHit, User
from app.services.ask_graph import AskState, build_ask_graph
from app.services.retrieval import search_persona

logger = logging.getLogger("app.mcp")

# Fixed text: the model's own error could quote a story or a path (NFR-3)
MODEL_DOWN = "The assistant could not answer right now"
MAX_QUESTION_CHARS = 500


class AskSource(BaseModel):
    """A memory the answer relied on: its words and the story it came from."""

    content: str
    memory_title: str


class AskMemoryAnswer(BaseModel):
    """`sources[n - 1]` is the memory cited as `[n]` in the answer."""

    answer: str
    sources: list[AskSource]


def ask_memory_for(
    session: Session, user: User, person_id: uuid.UUID, question: str
) -> AskMemoryAnswer:
    # Before anything is read or any model is called (AC-4.9)
    get_person_for_conversation(session, user, person_id)
    llm = get_llm_client()

    def retriever(state: AskState) -> list[SearchHit]:
        return search_persona(session, person_id, llm, state["question"])

    try:
        result = build_ask_graph(session, user, llm, retriever).invoke(
            {"question": question}
        )
    except LLMError:
        raise ToolError(MODEL_DOWN) from None
    sources = result["relevant"]
    logger.info("mcp ask_memory: person=%s sources=%d", person_id, len(sources))
    return AskMemoryAnswer(
        answer=result["answer"],
        sources=[
            AskSource(content=hit.item.content, memory_title=hit.memory_title)
            for hit in sources
        ],
    )


def register(server: MCPServer) -> None:
    @server.tool()
    async def ask_memory(
        person_id: uuid.UUID,
        question: Annotated[str, Field(min_length=1, max_length=MAX_QUESTION_CHARS)],
    ) -> AskMemoryAnswer:
        """Ask what the family's confirmed memories say about one person."""
        return await run_as_user(
            "ask_memory",
            lambda session, user: ask_memory_for(session, user, person_id, question),
        )
