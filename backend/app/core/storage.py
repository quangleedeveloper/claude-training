import logging
from pathlib import Path
from typing import BinaryIO, Protocol

from app.core.config import settings

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1024 * 1024


class FileTooLargeError(Exception):
    def __init__(self, max_bytes: int) -> None:
        super().__init__(f"File is larger than {max_bytes} bytes")
        self.max_bytes = max_bytes


class FileStorage(Protocol):
    """Where uploaded bytes live; swap the implementation to move to S3."""

    def save(self, stream: BinaryIO, key: str, max_bytes: int) -> int: ...

    def path(self, key: str) -> Path: ...

    def exists(self, key: str) -> bool: ...

    def delete(self, key: str) -> None: ...


class LocalFileStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def path(self, key: str) -> Path:
        target = (self.root / key).resolve()
        # Keys are server generated, but never trust that to stay inside the root
        if not target.is_relative_to(self.root):
            raise ValueError("Storage key escapes the upload directory")
        return target

    def exists(self, key: str) -> bool:
        return self.path(key).is_file()

    def save(self, stream: BinaryIO, key: str, max_bytes: int) -> int:
        """Stream to disk, returning the size. Nothing is kept on failure."""
        target = self.path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(target.name + ".part")
        size = 0
        try:
            with partial.open("wb") as out:
                while chunk := stream.read(CHUNK_SIZE):
                    size += len(chunk)
                    if size > max_bytes:
                        raise FileTooLargeError(max_bytes)
                    out.write(chunk)
            partial.replace(target)
        except BaseException:
            partial.unlink(missing_ok=True)
            raise
        return size

    def delete(self, key: str) -> None:
        try:
            self.path(key).unlink(missing_ok=True)
        except OSError:
            # The DB row is the source of truth; an orphan file is only wasted space
            logger.exception("Could not delete stored file %s", key)


def get_storage() -> FileStorage:
    # Read the setting per call so tests can point it at a temp directory
    return LocalFileStorage(settings.UPLOAD_DIR)
