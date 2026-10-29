"""The events a persona reply is made of, and the reply itself.

`reply` is the interface agreed between MR-104 (the API around it) and MR-105 (the
real reply graph). Until MR-105 lands it answers every message with the fixed
no-memory text and never calls the model.
"""

import uuid
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field

from sqlmodel import Session

from app.core.llm import LLMClient
from app.core.prompt import PERSONA_NO_MEMORY, PERSONA_NOTICE
from app.models import ConversationMessage, SearchHit


@dataclass(frozen=True)
class TokenEvent:
    text: str


@dataclass(frozen=True)
class DoneEvent:
    sources: list[SearchHit]
    fallback: bool
    notice: str = PERSONA_NOTICE
    cited_ids: list[uuid.UUID] = field(default_factory=list)
    invalid_citations: list[int] = field(default_factory=list)
    uncited: bool = False


PersonaEvent = TokenEvent | DoneEvent


def reply(
    session: Session,  # noqa: ARG001
    llm: LLMClient,  # noqa: ARG001
    *,
    person_id: uuid.UUID,  # noqa: ARG001
    person_name: str,  # noqa: ARG001
    history: Sequence[ConversationMessage],  # noqa: ARG001
    message: str,  # noqa: ARG001
    summary: str | None = None,  # noqa: ARG001
) -> Iterator[PersonaEvent]:
    """Stream the persona's answer to `message`: tokens, then one done event."""
    yield TokenEvent(PERSONA_NO_MEMORY)
    yield DoneEvent(sources=[], fallback=True)
