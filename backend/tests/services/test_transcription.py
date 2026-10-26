import struct
import wave
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.core.config import settings
from app.services import transcription
from app.services.transcription import FasterWhisperTranscriber, get_transcriber


class FakeWhisperModel:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def transcribe(self, path: str, **options: Any) -> tuple[list[Any], None]:
        self.calls.append((path, options))
        segments = [
            SimpleNamespace(text=" Hello there. "),
            SimpleNamespace(text="Bye."),
        ]
        return segments, None


def test_transcriber_joins_the_segments(monkeypatch: pytest.MonkeyPatch) -> None:
    model = FakeWhisperModel()
    loaded: list[str] = []

    def load(name: str) -> FakeWhisperModel:
        loaded.append(name)
        return model

    monkeypatch.setattr(transcription, "_load_model", load)

    text = FasterWhisperTranscriber().transcribe(Path("voice.mp3"))

    assert text == "Hello there. Bye."
    assert loaded == [settings.WHISPER_MODEL]
    assert model.calls == [("voice.mp3", {"vad_filter": True})]


def test_get_transcriber_returns_whisper() -> None:
    assert isinstance(get_transcriber(), FasterWhisperTranscriber)


def test_whisper_can_decode_audio_with_the_installed_pyav(tmp_path: Path) -> None:
    """faster-whisper opens files through PyAV with options some PyAV releases
    removed (metadata_errors), which only shows up when a real file is decoded."""
    from faster_whisper.audio import decode_audio

    recording = tmp_path / "silence.wav"
    with wave.open(str(recording), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(struct.pack("<1600h", *([0] * 1600)))

    samples = decode_audio(str(recording))

    assert samples.shape == (1600,)
