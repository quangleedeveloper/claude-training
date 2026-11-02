from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from sqlmodel import Session, col, select

from app.core.config import Settings, settings
from app.core.fake_ai import FakeLLMClient, FakeTranscriber
from app.core.llm import LLMError, OllamaClient, get_llm_client
from app.core.storage import LocalFileStorage
from app.models import ExtractedMemory, MemoryFileStatus
from app.services.processing import (
    ModelMediaProcessor,
    get_media_processor,
    process_memory_file,
)
from app.services.transcription import FasterWhisperTranscriber, get_transcriber
from tests.utils.memory_file import create_random_memory_file


def make_settings(**overrides: Any) -> Settings:
    """Settings as the app builds them (secrets from the environment), with changes."""
    return Settings(**overrides)


def test_fake_ai_is_refused_outside_development() -> None:
    with pytest.raises(ValidationError, match="only allowed when FASTAPI_ENV"):
        make_settings(AI_BACKEND="fake", FASTAPI_ENV=None)


def test_fake_ai_is_allowed_in_development() -> None:
    assert (
        make_settings(AI_BACKEND="fake", FASTAPI_ENV="development").AI_BACKEND == "fake"
    )


def test_the_real_models_are_the_default() -> None:
    assert make_settings(FASTAPI_ENV="development").AI_BACKEND == "ollama"
    assert isinstance(get_llm_client(), OllamaClient)
    assert isinstance(get_transcriber(), FasterWhisperTranscriber)


def test_fake_mode_swaps_in_the_stand_ins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "AI_BACKEND", "fake")

    assert isinstance(get_llm_client(), FakeLLMClient)
    assert isinstance(get_transcriber(), FakeTranscriber)
    assert isinstance(get_media_processor(), ModelMediaProcessor)


def test_fake_mode_processes_a_file_without_any_model(
    monkeypatch: pytest.MonkeyPatch, db: Session
) -> None:
    """What the Playwright run relies on: files reach Processed with no Ollama."""
    monkeypatch.setattr(settings, "AI_BACKEND", "fake")
    memory_file = create_random_memory_file(db)

    process_memory_file(
        memory_file.id,
        get_media_processor(),
        LocalFileStorage(settings.UPLOAD_DIR),
        get_llm_client(),
    )

    db.refresh(memory_file)
    assert memory_file.status == MemoryFileStatus.PROCESSED
    db.expire_all()
    found = db.exec(
        select(ExtractedMemory).where(col(ExtractedMemory.file_id) == memory_file.id)
    ).all()
    assert [item.content for item in found] == [
        "A photo of the family having a picnic by the lake."
    ]


def test_the_fake_transcriber_never_reads_the_file() -> None:
    transcriber = FakeTranscriber()
    text = transcriber.transcribe(Path("does-not-exist.mp3"))
    assert "old farm" in text
    assert transcriber.paths == [Path("does-not-exist.mp3")]


def test_the_fake_can_simulate_an_outage() -> None:
    llm = FakeLLMClient()
    llm.error = "down"
    with pytest.raises(LLMError, match="down"):
        llm.embed(["x"])


def test_the_fake_can_return_chosen_extractions() -> None:
    llm = FakeLLMClient()
    llm.extracted = [{"category": "event", "content": "A wedding", "confidence": 0.8}]
    assert llm.extract_json("sys", "ignored", {}) == {"memories": llm.extracted}
