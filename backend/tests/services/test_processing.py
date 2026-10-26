import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlmodel import Session, col, select

from app.core import checkpoint
from app.core.checkpoint import clear_thread
from app.core.config import settings
from app.core.errors import UserFacingError
from app.core.storage import LocalFileStorage
from app.models import (
    ExtractedMemory,
    ExtractedSource,
    ExtractedStatus,
    MemoryFile,
    MemoryFileKind,
    MemoryFileStatus,
)
from app.services.processing import (
    GENERIC_FAILURE,
    ModelMediaProcessor,
    extract_memory_story,
    get_media_processor,
    process_memory_file,
)
from tests.utils.llm import FakeLLMClient, FakeTranscriber
from tests.utils.memory import create_random_memory
from tests.utils.memory_file import FakeMediaProcessor, create_random_memory_file


def extracted_for(db: Session, file_id: uuid.UUID) -> list[ExtractedMemory]:
    db.expire_all()
    return list(
        db.exec(
            select(ExtractedMemory).where(col(ExtractedMemory.file_id) == file_id)
        ).all()
    )


def test_process_memory_file_marks_it_processed_and_extracts(
    db: Session, media_processor: FakeMediaProcessor, llm_client: FakeLLMClient
) -> None:
    memory_file = create_random_memory_file(db)
    storage = LocalFileStorage(settings.UPLOAD_DIR)

    process_memory_file(memory_file.id, media_processor, storage, llm_client)

    db.refresh(memory_file)
    assert memory_file.status == MemoryFileStatus.PROCESSED
    assert memory_file.processed_at is not None
    assert memory_file.error_message is None
    assert memory_file.extracted_text == media_processor.text
    assert media_processor.processed == [storage.path(memory_file.storage_key)]
    (extracted,) = extracted_for(db, memory_file.id)
    assert extracted.content == media_processor.text
    assert extracted.source == ExtractedSource.IMAGE
    assert extracted.status == ExtractedStatus.ACTIVE


def test_process_memory_file_records_the_failure(
    db: Session, media_processor: FakeMediaProcessor, llm_client: FakeLLMClient
) -> None:
    media_processor.error = "unreadable audio"
    memory_file = create_random_memory_file(db)

    process_memory_file(
        memory_file.id,
        media_processor,
        LocalFileStorage(settings.UPLOAD_DIR),
        llm_client,
    )

    db.refresh(memory_file)
    assert memory_file.status == MemoryFileStatus.FAILED
    # What went wrong is logged; the user sees a message that cannot leak internals
    assert memory_file.error_message == GENERIC_FAILURE
    assert "unreadable audio" not in (memory_file.error_message or "")
    assert memory_file.processed_at is None
    assert extracted_for(db, memory_file.id) == []


def test_process_memory_file_fails_when_the_model_is_down(
    db: Session, media_processor: FakeMediaProcessor, llm_client: FakeLLMClient
) -> None:
    llm_client.error = "Could not reach Ollama"
    memory_file = create_random_memory_file(db)

    process_memory_file(
        memory_file.id,
        media_processor,
        LocalFileStorage(settings.UPLOAD_DIR),
        llm_client,
    )

    db.refresh(memory_file)
    assert memory_file.status == MemoryFileStatus.FAILED
    assert memory_file.error_message == "Could not reach Ollama"


def test_process_memory_file_without_speech_extracts_nothing(
    db: Session, media_processor: FakeMediaProcessor, llm_client: FakeLLMClient
) -> None:
    media_processor.text = "   "
    memory_file = create_random_memory_file(db)

    process_memory_file(
        memory_file.id,
        media_processor,
        LocalFileStorage(settings.UPLOAD_DIR),
        llm_client,
    )

    db.refresh(memory_file)
    assert memory_file.status == MemoryFileStatus.PROCESSED
    assert extracted_for(db, memory_file.id) == []
    assert llm_client.extract_prompts == []


def test_process_memory_file_again_keeps_rejected_items_rejected(
    db: Session, media_processor: FakeMediaProcessor, llm_client: FakeLLMClient
) -> None:
    storage = LocalFileStorage(settings.UPLOAD_DIR)
    memory_file = create_random_memory_file(db)
    process_memory_file(memory_file.id, media_processor, storage, llm_client)
    (first,) = extracted_for(db, memory_file.id)
    first.status = ExtractedStatus.REJECTED
    db.add(first)
    db.commit()

    media_processor.text = "Grandma baked bread every Sunday. She sang in church."
    process_memory_file(memory_file.id, media_processor, storage, llm_client)

    contents = {item.content: item.status for item in extracted_for(db, memory_file.id)}
    assert contents == {
        "Grandma baked bread every Sunday.": ExtractedStatus.REJECTED,
        "She sang in church.": ExtractedStatus.ACTIVE,
    }


def test_process_memory_file_unknown_id_does_nothing(
    media_processor: FakeMediaProcessor, llm_client: FakeLLMClient
) -> None:
    process_memory_file(
        uuid.uuid4(),
        media_processor,
        LocalFileStorage(settings.UPLOAD_DIR),
        llm_client,
    )
    assert media_processor.processed == []


def test_process_memory_file_deleted_while_processing(
    db: Session, llm_client: FakeLLMClient
) -> None:
    memory_file = create_random_memory_file(db)
    file_id = memory_file.id

    class DeletingProcessor:
        def process(self, path: Path, kind: MemoryFileKind) -> str:
            with Session(db.get_bind()) as other:
                row = other.get(MemoryFile, file_id)
                assert row is not None
                other.delete(row)
                other.commit()
            return "Grandma baked bread every Sunday."

    process_memory_file(
        file_id,
        DeletingProcessor(),
        LocalFileStorage(settings.UPLOAD_DIR),
        llm_client,
    )

    db.expire_all()
    assert db.get(MemoryFile, file_id) is None


def test_model_media_processor_describes_images_and_transcribes_the_rest(
    llm_client: FakeLLMClient,
) -> None:
    transcriber = FakeTranscriber()
    processor = ModelMediaProcessor(llm_client, transcriber)

    assert "picnic" in processor.process(Path("photo.png"), MemoryFileKind.IMAGE)
    assert "old farm" in processor.process(Path("voice.mp3"), MemoryFileKind.AUDIO)
    assert "old farm" in processor.process(Path("clip.mp4"), MemoryFileKind.VIDEO)
    assert transcriber.paths == [Path("voice.mp3"), Path("clip.mp4")]


def test_get_media_processor_uses_the_models() -> None:
    assert isinstance(get_media_processor(), ModelMediaProcessor)


def test_extract_memory_story_replaces_untouched_items(
    db: Session, llm_client: FakeLLMClient
) -> None:
    memory = create_random_memory(db)
    memory.content = "Dad fished at the lake. He caught nothing."
    db.add(memory)
    db.commit()

    extract_memory_story(memory.id, llm_client)
    extract_memory_story(memory.id, llm_client)

    db.expire_all()
    mine = db.exec(
        select(ExtractedMemory).where(col(ExtractedMemory.memory_id) == memory.id)
    ).all()
    assert sorted(i.content for i in mine) == [
        "Dad fished at the lake.",
        "He caught nothing.",
    ]
    assert {i.source for i in mine} == {ExtractedSource.STORY}


def test_extract_memory_story_survives_a_model_outage(
    db: Session, llm_client: FakeLLMClient
) -> None:
    memory = create_random_memory(db)
    llm_client.error = "Ollama is down"

    extract_memory_story(memory.id, llm_client)

    db.expire_all()
    assert (
        db.exec(
            select(ExtractedMemory).where(col(ExtractedMemory.memory_id) == memory.id)
        ).all()
        == []
    )


def test_extract_memory_story_unknown_memory_does_nothing(
    llm_client: FakeLLMClient,
) -> None:
    extract_memory_story(uuid.uuid4(), llm_client)
    assert llm_client.extract_prompts == []


def checkpoint_count(db: Session, file_id: uuid.UUID) -> int:
    db.rollback()  # see what the background task committed
    return int(
        db.execute(
            text("select count(*) from checkpoints where thread_id = :id"),
            {"id": str(file_id)},
        ).scalar_one()
    )


def test_a_finished_file_leaves_no_checkpoints(
    db: Session, media_processor: FakeMediaProcessor, llm_client: FakeLLMClient
) -> None:
    memory_file = create_random_memory_file(db)

    process_memory_file(
        memory_file.id,
        media_processor,
        LocalFileStorage(settings.UPLOAD_DIR),
        llm_client,
    )

    assert checkpoint_count(db, memory_file.id) == 0


def test_retry_resumes_after_the_last_finished_step(
    db: Session, media_processor: FakeMediaProcessor, llm_client: FakeLLMClient
) -> None:
    storage = LocalFileStorage(settings.UPLOAD_DIR)
    memory_file = create_random_memory_file(db)
    llm_client.error = "Ollama went away"

    # The media is read, then the model call fails: progress up to there is kept
    process_memory_file(memory_file.id, media_processor, storage, llm_client)
    db.refresh(memory_file)
    assert memory_file.status == MemoryFileStatus.FAILED
    assert checkpoint_count(db, memory_file.id) > 0

    llm_client.error = None
    process_memory_file(memory_file.id, media_processor, storage, llm_client)

    db.refresh(memory_file)
    assert memory_file.status == MemoryFileStatus.PROCESSED
    assert memory_file.error_message is None
    # The expensive step ran once, not again on retry
    assert len(media_processor.processed) == 1
    (extracted,) = extracted_for(db, memory_file.id)
    assert extracted.content == media_processor.text
    assert checkpoint_count(db, memory_file.id) == 0


def test_deleting_a_failed_file_forgets_its_progress(
    db: Session, media_processor: FakeMediaProcessor, llm_client: FakeLLMClient
) -> None:
    memory_file = create_random_memory_file(db)
    llm_client.error = "Ollama went away"
    process_memory_file(
        memory_file.id,
        media_processor,
        LocalFileStorage(settings.UPLOAD_DIR),
        llm_client,
    )
    assert checkpoint_count(db, memory_file.id) > 0

    clear_thread(str(memory_file.id))

    assert checkpoint_count(db, memory_file.id) == 0


def test_clearing_checkpoints_never_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken() -> None:
        raise RuntimeError("database gone")

    monkeypatch.setattr(checkpoint, "open_checkpointer", broken)
    clear_thread("anything")


def test_a_user_facing_error_is_shown_as_written(
    db: Session, llm_client: FakeLLMClient
) -> None:
    class TooLong(UserFacingError):
        pass

    class RefusingProcessor:
        def process(self, path: Path, kind: MemoryFileKind) -> str:
            raise TooLong("Recordings can be at most 60 minutes long")

    memory_file = create_random_memory_file(db)

    process_memory_file(
        memory_file.id,
        RefusingProcessor(),
        LocalFileStorage(settings.UPLOAD_DIR),
        llm_client,
    )

    db.refresh(memory_file)
    assert memory_file.status == MemoryFileStatus.FAILED
    assert memory_file.error_message == "Recordings can be at most 60 minutes long"


def test_an_unexpected_error_never_shows_server_details(
    db: Session, media_processor: FakeMediaProcessor, llm_client: FakeLLMClient
) -> None:
    media_processor.error = "[Errno 2] No such file: /srv/uploads/secret/path.mp3"
    memory_file = create_random_memory_file(db)

    process_memory_file(
        memory_file.id,
        media_processor,
        LocalFileStorage(settings.UPLOAD_DIR),
        llm_client,
    )

    db.refresh(memory_file)
    assert memory_file.error_message == GENERIC_FAILURE
