import logging
import uuid
from pathlib import Path

from sqlmodel import Session

from app.core.checkpoint import clear_thread, open_checkpointer
from app.core.db import engine
from app.core.errors import UserFacingError
from app.core.llm import LLMClient, get_llm_client
from app.core.storage import FileStorage
from app.models import (
    ExtractedSource,
    Memory,
    MemoryFile,
    MemoryFileKind,
    MemoryFileStatus,
    get_datetime_utc,
)
from app.services.extraction import ExtractedDraft, replace_extracted
from app.services.extraction_graph import (
    ExtractionState,
    MediaProcessor,
    build_extraction_graph,
    drafts_from_state,
    extraction_config,
    run_extraction,
)
from app.services.transcription import Transcriber, get_transcriber

logger = logging.getLogger(__name__)

GENERIC_FAILURE = "Processing failed. Check the server logs for details."

__all__ = [
    "MediaProcessor",
    "ModelMediaProcessor",
    "extract_memory_story",
    "get_media_processor",
    "process_memory_file",
]


class ModelMediaProcessor:
    """Photos are described by a vision model, audio and video are transcribed."""

    def __init__(self, llm: LLMClient, transcriber: Transcriber) -> None:
        self.llm = llm
        self.transcriber = transcriber

    def process(self, path: Path, kind: MemoryFileKind) -> str:
        if kind == MemoryFileKind.IMAGE:
            return self.llm.describe_image(path)
        return self.transcriber.transcribe(path)


def get_media_processor() -> MediaProcessor:
    return ModelMediaProcessor(get_llm_client(), get_transcriber())


def process_memory_file(
    file_id: uuid.UUID,
    processor: MediaProcessor,
    storage: FileStorage,
    llm: LLMClient,
) -> None:
    """Background task. Opens its own session: the request's is closed by now.

    The slow work (transcribing, model calls) runs inside the extraction graph with
    no database transaction held open.
    """
    with Session(engine) as session:
        memory_file = session.get(MemoryFile, file_id)
        if memory_file is None:
            return
        memory = session.get(Memory, memory_file.memory_id)
        if memory is None:
            return
        memory_file.status = MemoryFileStatus.PROCESSING
        memory_file.error_message = None
        session.add(memory_file)
        session.commit()
        initial: ExtractionState = {
            "person_name": memory.person_name,
            "path": str(storage.path(memory_file.storage_key)),
            "kind": memory_file.kind,
        }
        memory_id = memory_file.memory_id
        thread_id = str(file_id)
        source = ExtractedSource(memory_file.kind)

        error: str | None = None
        text = ""
        drafts: list[ExtractedDraft] = []
        try:
            with open_checkpointer() as checkpointer:
                graph = build_extraction_graph(llm, processor, checkpointer)
                result = run_extraction(graph, checkpointer, initial, thread_id)
            text = result.get("text", "")
            drafts = drafts_from_state(result.get("drafts", []))
        except Exception as exc:
            logger.exception("Processing failed for memory file %s", file_id)
            # Only messages written for users are stored; anything else can carry
            # server details, and is in the log above
            error = (str(exc) if isinstance(exc, UserFacingError) else "")[:500]
            error = error or GENERIC_FAILURE

        # The file may have been deleted while it was processing
        session.expire_all()
        memory_file = session.get(MemoryFile, file_id)
        if memory_file is None:
            clear_thread(thread_id)
            return
        if error is None:
            memory_file.extracted_text = text
            memory_file.status = MemoryFileStatus.PROCESSED
            memory_file.processed_at = get_datetime_utc()
            replace_extracted(
                session,
                memory_id=memory_id,
                file_id=file_id,
                source=source,
                drafts=drafts,
            )
        else:
            memory_file.status = MemoryFileStatus.FAILED
            memory_file.error_message = error
        session.add(memory_file)
        session.commit()
        if error is None:
            # Done and stored. On failure the checkpoints stay, so Retry can resume.
            clear_thread(thread_id)


def extract_memory_story(memory_id: uuid.UUID, llm: LLMClient) -> None:
    """Background task: extract from what the family wrote. Failures are logged, not
    raised, because a story has no status to show them on and saving it must not
    depend on the model being up."""
    with Session(engine) as session:
        memory = session.get(Memory, memory_id)
        if memory is None:
            return
        initial: ExtractionState = {
            "person_name": memory.person_name,
            "text": memory.content,
        }
    try:
        result = build_extraction_graph(llm).invoke(initial, extraction_config())
    except Exception:
        logger.exception("Story extraction failed for memory %s", memory_id)
        return
    with Session(engine) as session:
        if session.get(Memory, memory_id) is None:
            return
        replace_extracted(
            session,
            memory_id=memory_id,
            file_id=None,
            source=ExtractedSource.STORY,
            drafts=drafts_from_state(result.get("drafts", [])),
        )
        session.commit()
