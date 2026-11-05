from unittest.mock import patch

from sqlmodel import Session

from app.models import SearchHit
from app.services import ask_graph
from app.services.ask_graph import NO_ANSWER, AskState, build_ask_graph
from tests.utils.llm import FakeLLMClient
from tests.utils.user import get_superuser


def test_build_ask_graph_searches_own_memories_by_default(
    db: Session, llm_client: FakeLLMClient
) -> None:
    user = get_superuser(db)

    with patch.object(ask_graph, "search_extracted", return_value=[]) as search:
        result = build_ask_graph(db, user, llm_client).invoke({"question": "Who?"})

    search.assert_called_once()
    assert result["answer"] == NO_ANSWER
    assert llm_client.answer_prompts == []


def test_build_ask_graph_uses_the_given_retriever(
    db: Session, llm_client: FakeLLMClient
) -> None:
    user = get_superuser(db)
    seen: list[str] = []

    def retriever(state: AskState) -> list[SearchHit]:
        seen.append(state["question"])
        return []

    with patch.object(ask_graph, "search_extracted") as search:
        result = build_ask_graph(db, user, llm_client, retriever).invoke(
            {"question": "Who?"}
        )

    search.assert_not_called()
    assert seen == ["Who?"]
    assert result["answer"] == NO_ANSWER
