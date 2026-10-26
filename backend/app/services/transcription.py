import functools
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import av
import numpy as np
from numpy.typing import NDArray

from app.core.config import settings
from app.core.errors import UserFacingError

if TYPE_CHECKING:
    from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

# Whisper's input format
SAMPLE_RATE = 16000


class MediaTooLongError(UserFacingError):
    """The recording is longer than `MAX_MEDIA_SECONDS`."""


class Transcriber(Protocol):
    """Turns speech in an audio or video file into text."""

    def transcribe(self, path: Path) -> str: ...


@functools.cache
def _load_model(name: str) -> WhisperModel:
    # Imported here: loading ctranslate2 is slow and only needed when transcribing.
    # The weights download on first use and are cached under HF_HOME.
    from faster_whisper import WhisperModel

    logger.info("Loading Whisper model %s", name)
    return WhisperModel(name, device="cpu", compute_type="int8")


def _duration_seconds(path: Path) -> float | None:
    """Length according to the container header, or None when it does not say."""
    try:
        with av.open(str(path)) as container:
            if container.duration is None:
                return None
            return float(container.duration) / av.time_base
    except Exception:
        # A file PyAV cannot open will fail properly when it is decoded
        logger.debug("Could not read the duration of %s", path.name, exc_info=True)
        return None


def _too_long_error(limit: float) -> MediaTooLongError:
    shown = f"{limit / 60:g} minutes" if limit >= 60 else f"{limit:g} seconds"
    return MediaTooLongError(f"Recordings can be at most {shown} long")


def _decode_audio(path: Path, limit: float) -> NDArray[np.float32] | None:
    """Decode to 16 kHz mono floats, refusing to go past `limit` seconds.

    faster-whisper would decode the whole file into memory before transcribing, so a
    small file that expands into hours of audio could exhaust the server. Decoding
    here stops the moment the limit is crossed, whatever the header claims. Returns
    None when the file has no audio track (a silent video).
    """
    max_samples = int(limit * SAMPLE_RATE)
    resampler = av.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
    chunks: list[NDArray[np.int16]] = []
    total = 0
    with av.open(str(path)) as container:
        if not container.streams.audio:
            return None

        def resampled_frames() -> Iterator[av.AudioFrame]:
            for frame in container.decode(audio=0):
                yield from resampler.resample(frame)
            # Passing None flushes what the resampler is still holding
            yield from resampler.resample(None)

        for resampled in resampled_frames():
            # The resampler was asked for s16, so this does not copy
            samples = resampled.to_ndarray().reshape(-1).astype(np.int16, copy=False)
            total += samples.size
            if total > max_samples:
                raise _too_long_error(limit)
            chunks.append(samples)
    if not chunks:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(chunks).astype(np.float32) / 32768.0


class FasterWhisperTranscriber:
    """Runs Whisper locally. It decodes audio straight out of video containers."""

    def transcribe(self, path: Path) -> str:
        # The upload size limits do not bound length: compressed audio can run for
        # hours, and on a CPU that would tie the worker up for just as long. The
        # header is a cheap first check, but it can be missing or wrong, so the
        # decoder enforces the limit too.
        limit = settings.MAX_MEDIA_SECONDS
        duration = _duration_seconds(path)
        if duration is not None and duration > limit:
            raise _too_long_error(limit)
        audio = _decode_audio(path, limit)
        if audio is None:
            return ""
        model = _load_model(settings.WHISPER_MODEL)
        # Voice activity detection skips silence, which stops Whisper inventing
        # words for quiet stretches
        segments, _info = model.transcribe(audio, vad_filter=True)
        return " ".join(segment.text.strip() for segment in segments).strip()


def get_transcriber() -> Transcriber:
    return FasterWhisperTranscriber()
