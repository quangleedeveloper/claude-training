import uuid

from sqlmodel import Session

from app.models import (
    ExtractedMemory,
    ExtractedSource,
    ExtractedStatus,
    Memory,
    MemoryFile,
)
from tests.utils.llm import fake_embedding
from tests.utils.memory import create_random_memory


def create_random_extracted_memory(
    db: Session,
    memory: Memory | None = None,
    memory_file: MemoryFile | None = None,
    content: str = "Grandma baked bread every Sunday.",
    status: ExtractedStatus = ExtractedStatus.ACTIVE,
    people: list[str] | None = None,
) -> ExtractedMemory:
    memory = memory or create_random_memory(db)
    extracted = ExtractedMemory(
        id=uuid.uuid4(),
        memory_id=memory.id,
        file_id=memory_file.id if memory_file else None,
        category="fact",
        content=content,
        people=people or [],
        confidence=0.9,
        status=status,
        source=ExtractedSource.STORY,
        embedding=fake_embedding(content),
    )
    db.add(extracted)
    db.commit()
    db.refresh(extracted)
    return extracted
