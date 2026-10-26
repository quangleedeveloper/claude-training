import functools
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import av

from app.core.config import settings
from app.core.errors import UserFacingError

if TYPE_CHECKING:
    from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)


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
        # A file PyAV cannot open will fail properly in the transcription itself
        logger.debug("Could not read the duration of %s", path.name, exc_info=True)
        return None


def _too_long_error(limit: float) -> MediaTooLongError:
    shown = f"{limit / 60:g} minutes" if limit >= 60 else f"{limit:g} seconds"
    return MediaTooLongError(f"Recordings can be at most {shown} long")


class FasterWhisperTranscriber:
    """Runs Whisper locally. It decodes audio straight out of video containers."""

    def transcribe(self, path: Path) -> str:
        # The upload size limits do not bound length: compressed audio can run for
        # hours, and on a CPU that would tie the worker up for just as long. A header
        # can lie or be missing, so the length is checked again while transcribing.
        limit = settings.MAX_MEDIA_SECONDS
        duration = _duration_seconds(path)
        if duration is not None and duration > limit:
            raise _too_long_error(limit)
        model = _load_model(settings.WHISPER_MODEL)
        # Voice activity detection skips silence, which stops Whisper inventing
        # words for quiet stretches
        segments, _info = model.transcribe(str(path), vad_filter=True)
        parts: list[str] = []
        # `segments` is lazy: the work happens as it is iterated, so stopping here
        # stops the transcription
        for segment in segments:
            if segment.end > limit:
                raise _too_long_error(limit)
            parts.append(segment.text.strip())
        return " ".join(parts).strip()


def get_transcriber() -> Transcriber:
    return FasterWhisperTranscriber()
