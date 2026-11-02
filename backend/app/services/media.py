from dataclasses import dataclass
from pathlib import PurePosixPath

import filetype

from app.core.config import settings
from app.models import MemoryFileKind

# The signature check needs at most this many leading bytes
HEAD_BYTES = 261

# extension -> (kind, MIME types that the file signature may report)
ALLOWED_MEDIA: dict[str, tuple[MemoryFileKind, frozenset[str]]] = {
    ".jpg": (MemoryFileKind.IMAGE, frozenset({"image/jpeg"})),
    ".jpeg": (MemoryFileKind.IMAGE, frozenset({"image/jpeg"})),
    ".png": (MemoryFileKind.IMAGE, frozenset({"image/png"})),
    ".webp": (MemoryFileKind.IMAGE, frozenset({"image/webp"})),
    ".mp3": (MemoryFileKind.AUDIO, frozenset({"audio/mpeg"})),
    ".wav": (MemoryFileKind.AUDIO, frozenset({"audio/x-wav"})),
    ".m4a": (MemoryFileKind.AUDIO, frozenset({"audio/mp4"})),
    ".mp4": (MemoryFileKind.VIDEO, frozenset({"video/mp4"})),
    ".mov": (MemoryFileKind.VIDEO, frozenset({"video/quicktime"})),
    ".webm": (MemoryFileKind.VIDEO, frozenset({"video/webm"})),
}


class MediaValidationError(Exception):
    """The reason is shown to the user, so keep it human readable."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class ValidatedMedia:
    kind: MemoryFileKind
    content_type: str
    extension: str


def display_filename(raw_name: str | None) -> str:
    """Strip any client supplied directories; the result is only for display."""
    name = PurePosixPath((raw_name or "").replace("\\", "/")).name.strip()
    return name[:255] or "unnamed"


def max_bytes_for(kind: MemoryFileKind) -> int:
    limits = {
        MemoryFileKind.IMAGE: settings.MAX_IMAGE_BYTES,
        MemoryFileKind.AUDIO: settings.MAX_AUDIO_BYTES,
        MemoryFileKind.VIDEO: settings.MAX_VIDEO_BYTES,
    }
    return limits[kind]


def format_size(size_bytes: int) -> str:
    return f"{size_bytes / (1024 * 1024):g} MB"


def validate_media(filename: str, head: bytes) -> ValidatedMedia:
    """Accept a file only if its extension AND its signature are allowed together."""
    extension = PurePosixPath(filename).suffix.lower()
    allowed = ALLOWED_MEDIA.get(extension)
    if allowed is None:
        supported = ", ".join(sorted(ALLOWED_MEDIA))
        raise MediaValidationError(
            f"Unsupported file type '{extension or filename}'. Supported: {supported}"
        )
    kind, mime_types = allowed
    detected = filetype.guess(head)
    if detected is None or detected.mime not in mime_types:
        raise MediaValidationError(
            f"The content of the file does not match its '{extension}' extension"
        )
    return ValidatedMedia(kind=kind, content_type=detected.mime, extension=extension)
