import pytest

from app.core.config import settings
from app.models import MemoryFileKind
from app.services.media import (
    MediaValidationError,
    display_filename,
    format_size,
    max_bytes_for,
    validate_media,
)
from tests.utils.memory_file import MP3_BYTES, MP4_BYTES, PNG_BYTES

WAV_BYTES = b"RIFF\x00\x00\x00\x00WAVEfmt " + b"\x00" * 16
M4A_BYTES = b"\x00\x00\x00\x20ftypM4A \x00\x00\x00\x00" + b"\x00" * 16
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 16
WEBP_BYTES = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 16
MOV_BYTES = b"\x00\x00\x00\x14ftypqt  \x00\x00\x00\x00" + b"\x00" * 16
WEBM_BYTES = b"\x1a\x45\xdf\xa3" + b"\x00" * 4 + b"\x42\x82\x84webm" + b"\x00" * 16


@pytest.mark.parametrize(
    ("filename", "head", "kind", "content_type"),
    [
        ("a.png", PNG_BYTES, MemoryFileKind.IMAGE, "image/png"),
        ("a.JPG", JPEG_BYTES, MemoryFileKind.IMAGE, "image/jpeg"),
        ("a.jpeg", JPEG_BYTES, MemoryFileKind.IMAGE, "image/jpeg"),
        ("a.webp", WEBP_BYTES, MemoryFileKind.IMAGE, "image/webp"),
        ("a.mp3", MP3_BYTES, MemoryFileKind.AUDIO, "audio/mpeg"),
        ("a.wav", WAV_BYTES, MemoryFileKind.AUDIO, "audio/x-wav"),
        ("a.m4a", M4A_BYTES, MemoryFileKind.AUDIO, "audio/mp4"),
        ("a.mp4", MP4_BYTES, MemoryFileKind.VIDEO, "video/mp4"),
        ("a.mov", MOV_BYTES, MemoryFileKind.VIDEO, "video/quicktime"),
        ("a.webm", WEBM_BYTES, MemoryFileKind.VIDEO, "video/webm"),
    ],
)
def test_validate_media_accepts_supported_files(
    filename: str, head: bytes, kind: MemoryFileKind, content_type: str
) -> None:
    media = validate_media(filename, head)
    assert media.kind == kind
    assert media.content_type == content_type
    assert media.extension == filename[filename.rindex(".") :].lower()


@pytest.mark.parametrize(
    ("filename", "head", "message"),
    [
        ("notes.txt", b"hello", "Unsupported file type"),
        ("README", b"hello", "Unsupported file type"),
        ("page.svg", b"<svg></svg>", "Unsupported file type"),
        ("fake.png", b"MZ\x90\x00" + b"\x00" * 16, "does not match"),
        ("fake.png", b"", "does not match"),
        ("song.png", MP3_BYTES, "does not match"),
        ("photo.mp3", PNG_BYTES, "does not match"),
    ],
)
def test_validate_media_rejects_unsupported_files(
    filename: str, head: bytes, message: str
) -> None:
    with pytest.raises(MediaValidationError, match=message):
        validate_media(filename, head)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("photo.png", "photo.png"),
        ("../../etc/passwd", "passwd"),
        ("C:\\Users\\me\\photo.png", "photo.png"),
        ("  spaced.png  ", "spaced.png"),
        ("", "unnamed"),
        (None, "unnamed"),
        ("a" * 400 + ".png", ("a" * 400 + ".png")[:255]),
    ],
)
def test_display_filename(raw: str | None, expected: str) -> None:
    assert display_filename(raw) == expected


def test_max_bytes_for_each_kind() -> None:
    assert max_bytes_for(MemoryFileKind.IMAGE) == settings.MAX_IMAGE_BYTES
    assert max_bytes_for(MemoryFileKind.AUDIO) == settings.MAX_AUDIO_BYTES
    assert max_bytes_for(MemoryFileKind.VIDEO) == settings.MAX_VIDEO_BYTES


def test_format_size() -> None:
    assert format_size(10 * 1024 * 1024) == "10 MB"
    assert format_size(1024 * 1024 // 2) == "0.5 MB"
