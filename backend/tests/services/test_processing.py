import uuid
from pathlib import Path

from sqlmodel import Session

from app.core.config import settings
from app.core.storage import LocalFileStorage
from app.models import MemoryFile, MemoryFileKind, MemoryFileStatus
from app.services.processing import (
    StubMediaProcessor,
    get_media_processor,
    process_memory_file,
)
from tests.utils.memory_file import FakeMediaProcessor, create_random_memory_file


def test_process_memory_file_marks_it_processed(
    db: Session, media_processor: FakeMediaProcessor
) -> None:
    memory_file = create_random_memory_file(db)
    storage = LocalFileStorage(settings.UPLOAD_DIR)

    process_memory_file(memory_file.id, media_processor, storage)

    db.refresh(memory_file)
    assert memory_file.status == MemoryFileStatus.PROCESSED
    assert memory_file.processed_at is not None
    assert memory_file.error_message is None
    assert media_processor.processed == [storage.path(memory_file.storage_key)]


def test_process_memory_file_records_the_failure(
    db: Session, media_processor: FakeMediaProcessor
) -> None:
    media_processor.error = "unreadable audio"
    memory_file = create_random_memory_file(db)

    process_memory_file(
        memory_file.id, media_processor, LocalFileStorage(settings.UPLOAD_DIR)
    )

    db.refresh(memory_file)
    assert memory_file.status == MemoryFileStatus.FAILED
    assert memory_file.error_message == "unreadable audio"
    assert memory_file.processed_at is None


def test_process_memory_file_unknown_id_does_nothing(
    media_processor: FakeMediaProcessor,
) -> None:
    process_memory_file(
        uuid.uuid4(), media_processor, LocalFileStorage(settings.UPLOAD_DIR)
    )
    assert media_processor.processed == []


def test_process_memory_file_deleted_while_processing(db: Session) -> None:
    memory_file = create_random_memory_file(db)
    file_id = memory_file.id

    class DeletingProcessor:
        def process(self, path: Path, kind: MemoryFileKind) -> None:
            with Session(db.get_bind()) as other:
                row = other.get(MemoryFile, file_id)
                assert row is not None
                other.delete(row)
                other.commit()

    process_memory_file(
        file_id, DeletingProcessor(), LocalFileStorage(settings.UPLOAD_DIR)
    )

    db.expire_all()
    assert db.get(MemoryFile, file_id) is None


def test_stub_processor_accepts_every_file() -> None:
    processor = get_media_processor()
    assert isinstance(processor, StubMediaProcessor)
    processor.process(Path("photo.png"), MemoryFileKind.IMAGE)
