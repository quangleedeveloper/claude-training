import logging
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from urllib.parse import quote

import psycopg
from langgraph.checkpoint.postgres import PostgresSaver

from app.core.config import settings

logger = logging.getLogger(__name__)


# Arbitrary app-specific key so workers starting together set the tables up in turn
SETUP_LOCK_KEY = 7_424_216_153
# Setup must never hang startup; a blocked index build is cancelled after this long
SETUP_TIMEOUT_MS = 60_000


def _connection_string(statement_timeout_ms: int | None = None) -> str:
    # psycopg wants a plain libpq URL, not SQLAlchemy's postgresql+psycopg://
    url = str(settings.DATABASE_URL).replace(
        "postgresql+psycopg://", "postgresql://", 1
    )
    if statement_timeout_ms is None:
        return url
    options = quote(f"-c statement_timeout={statement_timeout_ms}")
    return f"{url}{'&' if '?' in url else '?'}options={options}"


@contextmanager
def open_checkpointer(
    statement_timeout_ms: int | None = None,
) -> Iterator[PostgresSaver]:
    """A LangGraph checkpointer on the app's own PostgreSQL database."""
    with PostgresSaver.from_conn_string(
        _connection_string(statement_timeout_ms)
    ) as saver:
        yield saver


def setup_checkpoint_tables() -> None:
    """Create LangGraph's tables (checkpoints, checkpoint_blobs, checkpoint_writes).

    The library owns and migrates these, so they are made here instead of by Alembic,
    which is told to ignore them (see alembic/env.py). It is safe to call on every
    start: once the tables are current it does nothing.

    The first run builds an index with CREATE INDEX CONCURRENTLY, which waits for every
    open transaction to finish. Hence the timeout, and the advisory lock that keeps
    several workers starting together from all doing it at once.
    """
    with psycopg.connect(_connection_string(), autocommit=True) as lock_connection:
        lock_connection.execute("SELECT pg_advisory_lock(%s)", (SETUP_LOCK_KEY,))
        try:
            with open_checkpointer(SETUP_TIMEOUT_MS) as saver:
                saver.setup()
        finally:
            lock_connection.execute("SELECT pg_advisory_unlock(%s)", (SETUP_LOCK_KEY,))


def clear_threads(thread_ids: Sequence[str]) -> None:
    """Forget the saved progress of several runs over one database connection.

    Best effort: a leftover checkpoint only wastes space, so a failure here is
    logged rather than allowed to undo work that already succeeded. A thread that
    fails does not stop the others from being cleared.
    """
    if not thread_ids:
        return
    try:
        with open_checkpointer() as saver:
            for thread_id in thread_ids:
                try:
                    saver.delete_thread(thread_id)
                except Exception:
                    logger.exception("Could not clear checkpoints for %s", thread_id)
    except Exception:
        logger.exception("Could not clear checkpoints for %d runs", len(thread_ids))


def clear_thread(thread_id: str) -> None:
    """Forget the saved progress of one run (see `clear_threads`)."""
    clear_threads([thread_id])
