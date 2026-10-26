import functools
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from app.core.config import settings

if TYPE_CHECKING:
    from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)


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


class FasterWhisperTranscriber:
    """Runs Whisper locally. It decodes audio straight out of video containers."""

    def transcribe(self, path: Path) -> str:
        model = _load_model(settings.WHISPER_MODEL)
        # Voice activity detection skips silence, which stops Whisper inventing
        # words for quiet stretches
        segments, _info = model.transcribe(str(path), vad_filter=True)
        return " ".join(segment.text.strip() for segment in segments).strip()


def get_transcriber() -> Transcriber:
    return FasterWhisperTranscriber()
