import logging
import uuid
from pathlib import Path
from typing import Protocol

from sqlmodel import Session

from app.core.db import engine
from app.core.storage import FileStorage
from app.models import MemoryFile, MemoryFileKind, MemoryFileStatus, get_datetime_utc

logger = logging.getLogger(__name__)


class MediaProcessor(Protocol):
    """Turns an uploaded file into something the AI can use; raise to mark it failed."""

    def process(self, path: Path, kind: MemoryFileKind) -> None: ...


class StubMediaProcessor:
    """Placeholder until the AI pipeline exists; accepts every file."""

    def process(self, path: Path, kind: MemoryFileKind) -> None:
        logger.info("Processed %s file %s", kind, path.name)


def get_media_processor() -> MediaProcessor:
    return StubMediaProcessor()


def process_memory_file(
    file_id: uuid.UUID, processor: MediaProcessor, storage: FileStorage
) -> None:
    """Background task. Opens its own session: the request's is closed by now."""
    with Session(engine) as session:
        memory_file = session.get(MemoryFile, file_id)
        if memory_file is None:
            return
        memory_file.status = MemoryFileStatus.PROCESSING
        memory_file.error_message = None
        session.add(memory_file)
        session.commit()

        error: str | None = None
        try:
            processor.process(
                storage.path(memory_file.storage_key), MemoryFileKind(memory_file.kind)
            )
        except Exception as exc:
            logger.exception("Processing failed for memory file %s", file_id)
            error = (str(exc) or type(exc).__name__)[:500]

        # The file may have been deleted while it was processing
        session.expire_all()
        memory_file = session.get(MemoryFile, file_id)
        if memory_file is None:
            return
        if error is None:
            memory_file.status = MemoryFileStatus.PROCESSED
            memory_file.processed_at = get_datetime_utc()
        else:
            memory_file.status = MemoryFileStatus.FAILED
            memory_file.error_message = error
        session.add(memory_file)
        session.commit()
