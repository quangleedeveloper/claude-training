import struct
import wave
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.core.config import settings
from app.services import transcription
from app.services.transcription import (
    FasterWhisperTranscriber,
    MediaTooLongError,
    get_transcriber,
)


class FakeWhisperModel:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def transcribe(self, path: str, **options: Any) -> tuple[list[Any], None]:
        self.calls.append((path, options))
        segments = [
            SimpleNamespace(text=" Hello there. ", end=2.0),
            SimpleNamespace(text="Bye.", end=3.5),
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


def write_wav(path: Path, samples: int = 1600) -> Path:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(struct.pack(f"<{samples}h", *([0] * samples)))
    return path


def never_load(*_: object) -> None:
    raise AssertionError("the model must not be loaded for a refused file")


def test_duration_is_read_from_the_container_header(tmp_path: Path) -> None:
    recording = write_wav(tmp_path / "tenth.wav", samples=1600)
    assert transcription._duration_seconds(recording) == pytest.approx(0.1)


def test_duration_is_unknown_for_a_file_that_cannot_be_opened(tmp_path: Path) -> None:
    assert transcription._duration_seconds(tmp_path / "missing.mp3") is None


def test_a_recording_over_the_limit_is_refused_before_the_model_loads(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(settings, "MAX_MEDIA_SECONDS", 0.05)
    monkeypatch.setattr(transcription, "_load_model", never_load)

    with pytest.raises(MediaTooLongError, match="at most 0.05 seconds long"):
        FasterWhisperTranscriber().transcribe(write_wav(tmp_path / "tenth.wav"))


def test_the_limit_is_also_enforced_while_transcribing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A header can be missing or wrong, so the transcript's own timing is checked."""
    monkeypatch.setattr(settings, "MAX_MEDIA_SECONDS", 3600)
    monkeypatch.setattr(transcription, "_duration_seconds", lambda path: None)

    class LongRecording:
        def transcribe(self, path: str, **options: Any) -> tuple[list[Any], None]:
            return [SimpleNamespace(text="Hello.", end=7200.0)], None

    monkeypatch.setattr(transcription, "_load_model", lambda name: LongRecording())

    with pytest.raises(MediaTooLongError, match="at most 60 minutes long"):
        FasterWhisperTranscriber().transcribe(Path("hours.mp3"))


def test_a_recording_within_the_limit_is_transcribed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(transcription, "_load_model", lambda name: FakeWhisperModel())
    text = FasterWhisperTranscriber().transcribe(write_wav(tmp_path / "tenth.wav"))
    assert text == "Hello there. Bye."


def test_the_limit_message_is_user_facing() -> None:
    from app.core.errors import UserFacingError

    assert issubclass(MediaTooLongError, UserFacingError)
