import uuid
from typing import Any, cast

from sqlmodel import Session, col, select

from app.core.config import settings
from app.core.llm import LLMClient
from app.models import (
    ExtractedCategory,
    ExtractedMemory,
    ExtractedMemoryPublic,
    ExtractedStatus,
    Memory,
    SearchHit,
    User,
)


def search_extracted(
    session: Session,
    user: User,
    llm: LLMClient,
    query: str,
    *,
    memory_id: uuid.UUID | None = None,
    limit: int | None = None,
    all_users: bool = False,
) -> list[SearchHit]:
    """Nearest extracted memories to `query` from `user`'s own memories.

    Ownership is part of the query itself, so a hit from someone else's memory can
    never reach the answer prompt. That holds for superusers too: they only reach
    other people's memories by asking for `all_users` explicitly, which no one else
    can. Rejected items are excluded.
    """
    # Read what is needed from `user`, then end the read transaction the caller
    # may have open: a database connection must not wait on a slow model call
    user_id = user.id
    everyone = all_users and user.is_superuser
    session.rollback()
    (vector,) = llm.embed([query])
    # pgvector adds cosine_distance to the column at runtime; type checkers can't see it
    distance = cast(Any, ExtractedMemory.embedding).cosine_distance(vector)
    statement = (
        select(ExtractedMemory, Memory, distance)
        .join(Memory, col(Memory.id) == col(ExtractedMemory.memory_id))
        .where(col(ExtractedMemory.status) != ExtractedStatus.REJECTED)
        .order_by(distance)
        .limit(limit or settings.RETRIEVAL_TOP_K)
    )
    if not everyone:
        statement = statement.where(col(Memory.owner_id) == user_id)
    if memory_id is not None:
        statement = statement.where(col(ExtractedMemory.memory_id) == memory_id)
    return [
        SearchHit(
            item=ExtractedMemoryPublic.model_validate(extracted),
            memory_title=memory.title,
            person_name=memory.person_name,
            score=round(1 - float(dist), 4),
        )
        for extracted, memory, dist in session.exec(statement).all()
    ]


def search_persona(
    session: Session,
    person_id: uuid.UUID,
    llm: LLMClient,
    query: str,
    *,
    limit: int | None = None,
) -> list[SearchHit]:
    """Nearest confirmed memories of one person to `query`, for the persona.

    The persona may only say what the family confirmed or corrected (editing an item
    confirms it), so that rule is part of the query itself: an unconfirmed or
    rejected item, or one from a memory linked to someone else, can never reach the
    prompt. The route checks that the caller may talk to this person first.
    """
    # End the caller's read transaction: a database connection must not wait on a
    # slow model call
    session.rollback()
    (vector,) = llm.embed([query])
    # pgvector adds cosine_distance to the column at runtime; type checkers can't see it
    distance = cast(Any, ExtractedMemory.embedding).cosine_distance(vector)
    statement = (
        select(ExtractedMemory, Memory, distance)
        .join(Memory, col(Memory.id) == col(ExtractedMemory.memory_id))
        .where(
            col(Memory.person_id) == person_id,
            col(ExtractedMemory.status) != ExtractedStatus.REJECTED,
            col(ExtractedMemory.confirmed_at).is_not(None),
        )
        .order_by(distance)
        .limit(limit or settings.RETRIEVAL_TOP_K)
    )
    return [
        SearchHit(
            item=ExtractedMemoryPublic.model_validate(extracted),
            memory_title=memory.title,
            person_name=memory.person_name,
            score=round(1 - float(dist), 4),
        )
        for extracted, memory, dist in session.exec(statement).all()
    ]


def persona_quotes(
    session: Session, person_id: uuid.UUID, limit: int
) -> list[ExtractedMemoryPublic]:
    """The person's confirmed quotes, newest first: examples of how they spoke."""
    statement = (
        select(ExtractedMemory)
        .join(Memory, col(Memory.id) == col(ExtractedMemory.memory_id))
        .where(
            col(Memory.person_id) == person_id,
            col(ExtractedMemory.category) == ExtractedCategory.QUOTE,
            col(ExtractedMemory.status) != ExtractedStatus.REJECTED,
            col(ExtractedMemory.confirmed_at).is_not(None),
        )
        .order_by(col(ExtractedMemory.created_at).desc())
        .limit(limit)
    )
    return [
        ExtractedMemoryPublic.model_validate(extracted)
        for extracted in session.exec(statement).all()
    ]
