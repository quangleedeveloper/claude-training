import io
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.core.storage import FileTooLargeError, LocalFileStorage, get_storage


class ExplodingStream(io.BytesIO):
    """Delivers one chunk, then fails like a dropped connection."""

    def __init__(self) -> None:
        super().__init__(b"first chunk")
        self.calls = 0

    def read(self, size: int | None = -1) -> bytes:
        self.calls += 1
        if self.calls > 1:
            raise ConnectionResetError("client went away")
        return super().read(size)


@pytest.fixture
def storage(tmp_path: Path) -> Iterator[LocalFileStorage]:
    yield LocalFileStorage(tmp_path)


def test_save_writes_the_stream(storage: LocalFileStorage) -> None:
    size = storage.save(io.BytesIO(b"hello"), "m/f.png", max_bytes=100)
    assert size == 5
    assert storage.path("m/f.png").read_bytes() == b"hello"
    assert storage.exists("m/f.png")


def test_save_too_large_keeps_nothing(storage: LocalFileStorage) -> None:
    with pytest.raises(FileTooLargeError) as error:
        storage.save(io.BytesIO(b"x" * 11), "m/f.png", max_bytes=10)
    assert error.value.max_bytes == 10
    assert not storage.exists("m/f.png")
    assert list(storage.path("m").iterdir()) == []


def test_save_interrupted_keeps_nothing(storage: LocalFileStorage) -> None:
    with pytest.raises(ConnectionResetError):
        storage.save(ExplodingStream(), "m/f.png", max_bytes=100)
    assert not storage.exists("m/f.png")
    assert list(storage.path("m").iterdir()) == []


def test_path_rejects_keys_outside_the_root(storage: LocalFileStorage) -> None:
    with pytest.raises(ValueError, match="escapes"):
        storage.path("../outside.png")


def test_delete_removes_the_file_and_ignores_missing(
    storage: LocalFileStorage,
) -> None:
    storage.save(io.BytesIO(b"hello"), "m/f.png", max_bytes=100)
    storage.delete("m/f.png")
    assert not storage.exists("m/f.png")
    storage.delete("m/f.png")


def test_delete_logs_instead_of_raising_on_os_error(
    storage: LocalFileStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise PermissionError("locked", args, kwargs)

    monkeypatch.setattr(Path, "unlink", fail)
    storage.delete("m/f.png")


def test_get_storage_uses_the_current_setting(upload_dir: Path) -> None:
    storage = get_storage()
    assert isinstance(storage, LocalFileStorage)
    assert storage.root == upload_dir.resolve()
