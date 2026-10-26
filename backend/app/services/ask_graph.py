import uuid
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from sqlmodel import Session

from app.core.config import settings
from app.core.llm import LLMClient
from app.core.prompt import ANSWER_SYSTEM_PROMPT, ANSWER_USER_PROMPT
from app.models import AskResponse, SearchHit, User
from app.services.retrieval import search_extracted

NO_ANSWER = (
    "I could not find a memory about that yet. Try adding a story or uploading "
    "photos, audio or video that mention it."
)


class AskState(TypedDict, total=False):
    question: str
    memory_id: uuid.UUID | None
    hits: list[SearchHit]
    relevant: list[SearchHit]
    answer: str


# ty does not know LangGraph's TypedDict bound, so it is silenced here, once
AskGraph = CompiledStateGraph[AskState, None, AskState, AskState]  # ty: ignore[invalid-type-arguments]


def format_context(hits: list[SearchHit]) -> str:
    lines: list[str] = []
    for number, hit in enumerate(hits, start=1):
        item = hit.item
        details = [f"about {hit.person_name}", f"story: {hit.memory_title}"]
        if item.event_date_text:
            details.append(f"when: {item.event_date_text}")
        if item.location:
            details.append(f"where: {item.location}")
        if item.people:
            details.append(f"people: {', '.join(item.people)}")
        lines.append(f"[{number}] {item.content} ({'; '.join(details)})")
    return "\n".join(lines)


def build_ask_graph(session: Session, user: User, llm: LLMClient) -> AskGraph:
    """Retrieval-augmented answering that refuses to guess.

        START -> retrieve -> grade --(relevant memories)--> generate -> END
                                   \\--(none)--> no_answer ---------> END

    Skipping the model when nothing relevant was found is what keeps the answer
    grounded: a language model asked with an empty context will happily invent one.
    """

    def retrieve(state: AskState) -> AskState:
        hits = search_extracted(
            session, user, llm, state["question"], memory_id=state.get("memory_id")
        )
        return {"hits": hits}

    def grade(state: AskState) -> AskState:
        return {
            "relevant": [
                hit
                for hit in state["hits"]
                if hit.score >= settings.MIN_RELEVANCE_SCORE
            ]
        }

    def generate(state: AskState) -> AskState:
        prompt = ANSWER_USER_PROMPT.format(
            context=format_context(state["relevant"]), question=state["question"]
        )
        return {"answer": llm.answer(ANSWER_SYSTEM_PROMPT, prompt)}

    # LangGraph passes the state to every node, even one that ignores it
    def no_answer(state: AskState) -> AskState:  # noqa: ARG001
        return {"answer": NO_ANSWER, "relevant": []}

    def route(state: AskState) -> str:
        return "generate" if state["relevant"] else "no_answer"

    graph = StateGraph(AskState)  # ty: ignore[invalid-argument-type]
    graph.add_node("retrieve", retrieve)
    graph.add_node("grade", grade)
    graph.add_node("generate", generate)
    graph.add_node("no_answer", no_answer)
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "grade")
    graph.add_conditional_edges("grade", route, ["generate", "no_answer"])
    graph.add_edge("generate", END)
    graph.add_edge("no_answer", END)
    return graph.compile()


def ask(
    session: Session,
    user: User,
    llm: LLMClient,
    question: str,
    memory_id: uuid.UUID | None = None,
) -> AskResponse:
    result = build_ask_graph(session, user, llm).invoke(
        {"question": question, "memory_id": memory_id}
    )
    return AskResponse(answer=result["answer"], sources=result["relevant"])
