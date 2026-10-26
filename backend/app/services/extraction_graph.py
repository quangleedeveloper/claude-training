import logging
from pathlib import Path
from typing import Any, Protocol, TypedDict, cast

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.core.llm import LLMClient
from app.core.prompt import EXTRACTION_SYSTEM_PROMPT
from app.models import MemoryFileKind
from app.services.extraction import (
    EXTRACTION_SCHEMA,
    ExtractedDraft,
    RawItem,
    chunk_text,
    embedding_text,
    filter_items,
    parse_items,
)

logger = logging.getLogger(__name__)


# Everything in the state is plain JSON (str, list, dict, float). It is saved at
# every step when a checkpointer is attached, and a resumed run has to read it back
# exactly, which custom classes would make fragile.
class ExtractionState(TypedDict, total=False):
    # Inputs: either `text` (a story) or `path` + `kind` (a media file)
    person_name: str
    text: str
    path: str
    kind: str
    # Filled in by the nodes
    chunks: list[str]
    items: list[dict[str, Any]]  # RawItem as a dict
    drafts: list[dict[str, Any]]  # {"item": RawItem as a dict, "embedding": [...]}


class MediaProcessor(Protocol):
    """Turns an uploaded file into text the AI can read; raise to mark it failed."""

    def process(self, path: Path, kind: MemoryFileKind) -> str: ...


# ty does not know LangGraph's TypedDict bound, so it is silenced here, once
ExtractionGraph = CompiledStateGraph[
    ExtractionState, None, ExtractionState, ExtractionState  # ty: ignore[invalid-type-arguments]
]


def drafts_from_state(state_drafts: list[dict[str, Any]]) -> list[ExtractedDraft]:
    return [
        ExtractedDraft(
            item=RawItem.model_validate(draft["item"]), embedding=draft["embedding"]
        )
        for draft in state_drafts
    ]


def build_extraction_graph(
    llm: LLMClient,
    processor: MediaProcessor | None = None,
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> ExtractionGraph:
    """media/story -> text -> chunks -> items -> filtered items -> embedded drafts.

        START -> read_media -> chunk -> extract -> filter -> embed -> END
              \\-------------^ (skips read_media when the text is already known)

    A file with no readable content ends early with no drafts instead of
    calling the model on an empty string.

    With a `checkpointer` the state is saved after every step, so a run that fails
    (Ollama down) or is interrupted (server restart) can continue from its last
    finished step; see `run_extraction`.
    """

    def read_media(state: ExtractionState) -> ExtractionState:
        if processor is None:
            raise ValueError("A media processor is needed to read a file")
        return {
            "text": processor.process(
                Path(state["path"]), MemoryFileKind(state["kind"])
            )
        }

    def chunk(state: ExtractionState) -> ExtractionState:
        return {"chunks": chunk_text(state["text"])}

    def extract(state: ExtractionState) -> ExtractionState:
        system = EXTRACTION_SYSTEM_PROMPT.format(person=state["person_name"])
        items: list[RawItem] = []
        for piece in state["chunks"]:
            items.extend(
                parse_items(llm.extract_json(system, piece, EXTRACTION_SCHEMA))
            )
        return {"items": [item.model_dump() for item in items]}

    def filter_node(state: ExtractionState) -> ExtractionState:
        items = [RawItem.model_validate(item) for item in state["items"]]
        return {"items": [item.model_dump() for item in filter_items(items)]}

    def embed(state: ExtractionState) -> ExtractionState:
        items = [RawItem.model_validate(item) for item in state["items"]]
        vectors = llm.embed(
            [
                embedding_text(i.content, i.people, i.event_date_text, i.location)
                for i in items
            ]
        )
        return {
            "drafts": [
                {"item": item.model_dump(), "embedding": vector}
                for item, vector in zip(items, vectors, strict=True)
            ]
        }

    def start_route(state: ExtractionState) -> str:
        return "chunk" if "text" in state else "read_media"

    def after_chunk(state: ExtractionState) -> str:
        return "extract" if state["chunks"] else END

    graph = StateGraph(ExtractionState)  # ty: ignore[invalid-argument-type]
    graph.add_node("read_media", read_media)
    graph.add_node("chunk", chunk)
    graph.add_node("extract", extract)
    graph.add_node("filter", filter_node)
    graph.add_node("embed", embed)
    graph.add_conditional_edges(START, start_route, ["read_media", "chunk"])
    graph.add_edge("read_media", "chunk")
    graph.add_conditional_edges("chunk", after_chunk, ["extract", END])
    graph.add_edge("extract", "filter")
    graph.add_edge("filter", "embed")
    graph.add_edge("embed", END)
    return graph.compile(checkpointer=checkpointer)


def run_extraction(
    graph: ExtractionGraph,
    checkpointer: BaseCheckpointSaver[Any],
    initial: ExtractionState,
    thread_id: str,
) -> ExtractionState:
    """Run a checkpointed graph, resuming a stopped run for this thread if there is one.

    The thread is the file being processed, so Retry on a failed file picks up after
    the last step that finished: a long transcription is not repeated just because
    the model was down for the step after it.
    """
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    if graph.get_state(config).next:
        logger.info("Resuming extraction for %s", thread_id)
        return cast(ExtractionState, graph.invoke(None, config))
    # Nothing to resume. Drop leftovers of an earlier finished run, which would
    # otherwise bleed old results into this one.
    checkpointer.delete_thread(thread_id)
    return cast(ExtractionState, graph.invoke(initial, config))
