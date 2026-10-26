import struct
import wave
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import av
import numpy as np
import pytest

from app.core.config import settings
from app.core.errors import UserFacingError
from app.services import transcription
from app.services.transcription import (
    SAMPLE_RATE,
    FasterWhisperTranscriber,
    MediaTooLongError,
    get_transcriber,
)


class FakeWhisperModel:
    """Records the audio it is given instead of running Whisper."""

    def __init__(self) -> None:
        self.calls: list[tuple[Any, dict[str, Any]]] = []

    def transcribe(self, audio: Any, **options: Any) -> tuple[list[Any], None]:
        self.calls.append((audio, options))
        segments = [
            SimpleNamespace(text=" Hello there. ", end=2.0),
            SimpleNamespace(text="Bye.", end=3.5),
        ]
        return segments, None


def write_wav(
    path: Path,
    samples: int = 1600,
    rate: int = SAMPLE_RATE,
    channels: int = 1,
    amplitude: int = 0,
) -> Path:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(
            struct.pack(f"<{samples * channels}h", *([amplitude] * samples * channels))
        )
    return path


def never_load(*_: object) -> None:
    raise AssertionError("the model must not be loaded for a refused file")


class FakeContainer:
    """Stands in for an av container, as a context manager."""

    def __init__(
        self, duration: int | None = None, audio: tuple[int, ...] = ()
    ) -> None:
        self.duration = duration
        self.streams = SimpleNamespace(audio=list(audio))

    def __enter__(self) -> FakeContainer:
        return self

    def __exit__(self, *_: object) -> None:
        return None


def test_transcriber_joins_the_segments_and_hands_whisper_the_decoded_audio(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    model = FakeWhisperModel()
    loaded: list[str] = []

    def load(name: str) -> FakeWhisperModel:
        loaded.append(name)
        return model

    monkeypatch.setattr(transcription, "_load_model", load)

    text = FasterWhisperTranscriber().transcribe(write_wav(tmp_path / "a.wav"))

    assert text == "Hello there. Bye."
    assert loaded == [settings.WHISPER_MODEL]
    ((audio, options),) = model.calls
    assert options == {"vad_filter": True}
    assert audio.dtype == np.float32
    assert audio.shape == (1600,)


def test_get_transcriber_returns_whisper() -> None:
    assert isinstance(get_transcriber(), FasterWhisperTranscriber)


def test_decoding_scales_samples_to_floats(tmp_path: Path) -> None:
    recording = write_wav(tmp_path / "half.wav", amplitude=16384)

    audio = transcription._decode_audio(recording, limit=60)

    assert audio is not None
    assert audio.shape == (1600,)
    assert audio == pytest.approx(0.5)


def test_decoding_resamples_stereo_at_another_rate_to_16khz_mono(
    tmp_path: Path,
) -> None:
    """This is the path real recordings take; PyAV 19 broke the equivalent call in
    faster-whisper, which only shows up when a real file is decoded."""
    recording = write_wav(tmp_path / "stereo.wav", samples=8000, rate=8000, channels=2)

    audio = transcription._decode_audio(recording, limit=60)

    assert audio is not None
    # One second in, one second out, give or take the resampler's filter delay
    assert abs(audio.shape[0] - SAMPLE_RATE) < 200


def test_decoding_a_file_with_no_audio_track_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(av, "open", lambda path: FakeContainer())
    assert transcription._decode_audio(Path("silent.mp4"), limit=60) is None


def test_a_silent_video_is_transcribed_as_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(av, "open", lambda path: FakeContainer())
    monkeypatch.setattr(transcription, "_load_model", never_load)

    assert FasterWhisperTranscriber().transcribe(Path("silent.mp4")) == ""


def test_decoding_an_empty_recording_returns_no_samples(tmp_path: Path) -> None:
    audio = transcription._decode_audio(write_wav(tmp_path / "e.wav", samples=0), 60)
    assert audio is not None
    assert audio.shape == (0,)


def test_duration_is_read_from_the_container_header(tmp_path: Path) -> None:
    recording = write_wav(tmp_path / "tenth.wav", samples=1600)
    assert transcription._duration_seconds(recording) == pytest.approx(0.1)


def test_duration_is_unknown_when_the_header_does_not_say(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(av, "open", lambda path: FakeContainer())
    assert transcription._duration_seconds(Path("stream.mp4")) is None


def test_duration_is_unknown_for_a_file_that_cannot_be_opened(tmp_path: Path) -> None:
    assert transcription._duration_seconds(tmp_path / "missing.mp3") is None


def test_a_recording_over_the_limit_is_refused_from_its_header(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(settings, "MAX_MEDIA_SECONDS", 0.05)
    monkeypatch.setattr(transcription, "_load_model", never_load)
    decoded: list[Path] = []
    monkeypatch.setattr(
        transcription, "_decode_audio", lambda path, limit: decoded.append(path)
    )

    with pytest.raises(MediaTooLongError, match="at most 0.05 seconds long"):
        FasterWhisperTranscriber().transcribe(write_wav(tmp_path / "tenth.wav"))

    # Rejected before any audio was decoded
    assert decoded == []


def test_the_limit_holds_when_the_header_is_unknown_or_wrong(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A header can be missing or lie, so decoding enforces the limit itself and
    never builds more than the limit's worth of audio in memory."""
    monkeypatch.setattr(settings, "MAX_MEDIA_SECONDS", 1)
    monkeypatch.setattr(transcription, "_duration_seconds", lambda path: None)
    monkeypatch.setattr(transcription, "_load_model", never_load)
    long_recording = write_wav(tmp_path / "minute.wav", samples=SAMPLE_RATE * 60)

    with pytest.raises(MediaTooLongError, match="at most 1 seconds long"):
        FasterWhisperTranscriber().transcribe(long_recording)


def test_a_recording_exactly_at_the_limit_is_allowed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(settings, "MAX_MEDIA_SECONDS", 1)
    monkeypatch.setattr(transcription, "_load_model", lambda name: FakeWhisperModel())
    one_second = write_wav(tmp_path / "second.wav", samples=SAMPLE_RATE)

    assert FasterWhisperTranscriber().transcribe(one_second) == "Hello there. Bye."


@pytest.mark.parametrize(
    ("limit", "shown"),
    [(3600, "60 minutes"), (90, "1.5 minutes"), (30, "30 seconds")],
)
def test_the_limit_is_described_in_plain_units(limit: float, shown: str) -> None:
    assert str(transcription._too_long_error(limit)) == (
        f"Recordings can be at most {shown} long"
    )


def test_the_limit_message_is_user_facing() -> None:
    assert issubclass(MediaTooLongError, UserFacingError)
