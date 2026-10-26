from typing import Any

from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUser, LLMClientDep, SessionDep
from app.api.routes.memory_files import get_memory_or_error
from app.core.llm import LLMError
from app.models import AskRequest, AskResponse, SearchRequest, SearchResults
from app.services.ask_graph import ask
from app.services.retrieval import search_extracted

router = APIRouter(prefix="/search", tags=["search"])


@router.post("/", response_model=SearchResults)
def search_memories(
    session: SessionDep,
    current_user: CurrentUser,
    llm: LLMClientDep,
    search_in: SearchRequest,
) -> Any:
    """
    Find extracted memories that match a free-text query.
    """
    if search_in.memory_id is not None:
        get_memory_or_error(session, current_user, search_in.memory_id)
    try:
        hits = search_extracted(
            session,
            current_user,
            llm,
            search_in.query,
            memory_id=search_in.memory_id,
            limit=search_in.limit,
        )
    except LLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return SearchResults(data=hits)


@router.post("/ask", response_model=AskResponse)
def ask_memories(
    session: SessionDep,
    current_user: CurrentUser,
    llm: LLMClientDep,
    ask_in: AskRequest,
) -> Any:
    """
    Answer a question from the extracted memories, citing the ones it used.
    """
    if ask_in.memory_id is not None:
        get_memory_or_error(session, current_user, ask_in.memory_id)
    try:
        return ask(session, current_user, llm, ask_in.question, ask_in.memory_id)
    except LLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
