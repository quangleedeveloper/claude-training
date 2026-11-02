import uuid
from pathlib import Path

from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.core.storage import LocalFileStorage
from app.models import Memory, MemoryFile, MemoryFileKind
from tests.utils.memory import create_random_memory

# Smallest byte strings whose signatures the validator recognises
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
MP3_BYTES = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\x00" * 32
MP4_BYTES = b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00" + b"\x00" * 32


class FakeMediaProcessor:
    """Stands in for the AI pipeline; set `error` to make processing fail."""

    def __init__(self) -> None:
        self.error: str | None = None
        self.text = "Grandma baked bread every Sunday."
        self.processed: list[Path] = []

    def process(self, path: Path, kind: MemoryFileKind) -> str:
        if self.error is not None:
            raise RuntimeError(self.error)
        self.processed.append(path)
        return self.text


def create_random_memory_file(
    db: Session, memory: Memory | None = None, content: bytes = PNG_BYTES
) -> MemoryFile:
    """Store real bytes on disk and a matching row, as an upload would."""
    memory = memory or create_random_memory(db)
    file_id = uuid.uuid4()
    storage_key = f"{memory.id}/{file_id}.png"
    target = LocalFileStorage(settings.UPLOAD_DIR).path(storage_key)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return crud.create_memory_file(
        session=db,
        memory_id=memory.id,
        file_id=file_id,
        filename="photo.png",
        content_type="image/png",
        kind=MemoryFileKind.IMAGE,
        size_bytes=len(content),
        storage_key=storage_key,
    )
