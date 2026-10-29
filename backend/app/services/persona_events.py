"""The events a persona reply is made of; `persona_graph.reply` yields them."""

import uuid
from dataclasses import dataclass, field

from app.core.prompt import PERSONA_NOTICE
from app.models import SearchHit


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
