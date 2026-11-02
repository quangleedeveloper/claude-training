import logging
import re
import uuid
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field, ValidationError
from sqlmodel import Session, col, delete, select

from app.core.config import settings
from app.models import (
    ExtractedCategory,
    ExtractedMemory,
    ExtractedSource,
    ExtractedStatus,
)

logger = logging.getLogger(__name__)

# A few paragraphs per model call keeps small local models focused
CHUNK_CHARS = 3000
MAX_CONTENT_CHARS = 2000

EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "memories": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": [category.value for category in ExtractedCategory],
                    },
                    "content": {"type": "string"},
                    "people": {"type": "array", "items": {"type": "string"}},
                    "event_date_text": {"type": ["string", "null"]},
                    "location": {"type": ["string", "null"]},
                    "confidence": {"type": "number"},
                },
                "required": ["category", "content", "confidence"],
            },
        }
    },
    "required": ["memories"],
}


class RawItem(BaseModel):
    """One item as the model returned it, validated before anything is stored."""

    category: ExtractedCategory
    content: str = Field(min_length=1)
    people: list[str] = Field(default_factory=list)
    event_date_text: str | None = None
    location: str | None = None
    confidence: float = Field(ge=0, le=1)


@dataclass
class ExtractedDraft:
    item: RawItem
    embedding: list[float]


def normalize(content: str) -> str:
    """Key used to spot the same fact worded with different spacing or case."""
    return re.sub(r"[\W_]+", " ", content.lower()).strip()


def chunk_text(text: str, size: int = CHUNK_CHARS) -> list[str]:
    """Split on sentence ends so a fact is rarely cut in half."""
    chunks: list[str] = []
    current = ""
    for sentence in re.split(r"(?<=[.!?])\s+", text.strip()):
        # A transcript without punctuation can be one huge "sentence"
        for piece in (sentence[i : i + size] for i in range(0, len(sentence), size)):
            if current and len(current) + len(piece) + 1 > size:
                chunks.append(current)
                current = piece
            else:
                current = f"{current} {piece}".strip()
    if current:
        chunks.append(current)
    return chunks


def embedding_text(
    content: str, people: list[str], event_date_text: str | None, location: str | None
) -> str:
    """What gets embedded: the fact plus its details, so a search for a place or a
    name finds it even when the sentence itself does not repeat them."""
    parts = [content]
    if people:
        parts.append(f"People: {', '.join(people)}")
    if event_date_text:
        parts.append(f"When: {event_date_text}")
    if location:
        parts.append(f"Where: {location}")
    return ". ".join(parts)


def parse_items(data: dict[str, Any]) -> list[RawItem]:
    """Validate the model's JSON. A malformed item is dropped, not fatal: small
    models drift from the schema now and then."""
    raw_items = data.get("memories")
    if not isinstance(raw_items, list):
        return []
    items: list[RawItem] = []
    for raw in raw_items:
        try:
            item = RawItem.model_validate(raw)
        except ValidationError as exc:
            # Say what was wrong, never the item itself: it is the family's own text
            problems = [(".".join(map(str, e["loc"])), e["type"]) for e in exc.errors()]
            logger.warning("Skipping malformed extracted item: %s", problems)
            continue
        item.content = item.content.strip()[:MAX_CONTENT_CHARS]
        item.people = [name.strip() for name in item.people if name.strip()]
        items.append(item)
    return items


def filter_items(items: list[RawItem]) -> list[RawItem]:
    """Drop low-confidence items and repeats (chunks often overlap in topic)."""
    kept: list[RawItem] = []
    seen: set[str] = set()
    for item in items:
        key = normalize(item.content)
        if item.confidence < settings.MIN_EXTRACTION_CONFIDENCE or not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        kept.append(item)
    return kept


def replace_extracted(
    session: Session,
    *,
    memory_id: uuid.UUID,
    file_id: uuid.UUID | None,
    source: ExtractedSource,
    drafts: list[ExtractedDraft],
) -> int:
    """Swap the untouched items of one source (a file, or the story) for new ones.

    Items the user edited, confirmed or rejected stay, and a re-extraction never
    brings a rejected fact back. The caller commits.
    """
    same_source = (
        col(ExtractedMemory.file_id).is_(None)
        if file_id is None
        else col(ExtractedMemory.file_id) == file_id
    )
    session.exec(
        delete(ExtractedMemory).where(
            col(ExtractedMemory.memory_id) == memory_id,
            same_source,
            col(ExtractedMemory.status) == ExtractedStatus.ACTIVE,
            col(ExtractedMemory.confirmed_at).is_(None),
        )
    )
    kept = session.exec(
        select(ExtractedMemory.content).where(
            col(ExtractedMemory.memory_id) == memory_id, same_source
        )
    ).all()
    kept_keys = {normalize(content) for content in kept}
    added = 0
    for draft in drafts:
        if normalize(draft.item.content) in kept_keys:
            continue
        session.add(
            ExtractedMemory(
                memory_id=memory_id,
                file_id=file_id,
                category=draft.item.category,
                content=draft.item.content,
                people=draft.item.people,
                event_date_text=draft.item.event_date_text,
                location=draft.item.location,
                confidence=draft.item.confidence,
                source=source,
                embedding=draft.embedding,
            )
        )
        added += 1
    return added
