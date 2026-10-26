import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import Session, col, func, select

from app.api.deps import CurrentUser, LLMClientDep, SessionDep
from app.api.routes.memory_files import get_memory_or_error
from app.core.llm import LLMError
from app.models import (
    ExtractedMemoriesPublic,
    ExtractedMemory,
    ExtractedMemoryPublic,
    ExtractedMemoryUpdate,
    ExtractedStatus,
    Message,
    User,
    get_datetime_utc,
)
from app.services.extraction import embedding_text

router = APIRouter(
    prefix="/memories/{memory_id}/extracted", tags=["extracted_memories"]
)


def get_extracted_or_error(
    session: Session, current_user: User, memory_id: uuid.UUID, extracted_id: uuid.UUID
) -> ExtractedMemory:
    get_memory_or_error(session, current_user, memory_id)
    extracted = session.get(ExtractedMemory, extracted_id)
    if not extracted or extracted.memory_id != memory_id:
        raise HTTPException(status_code=404, detail="Extracted memory not found")
    return extracted


@router.get("/", response_model=ExtractedMemoriesPublic)
def read_extracted_memories(
    session: SessionDep,
    current_user: CurrentUser,
    memory_id: uuid.UUID,
    file_id: uuid.UUID | None = None,
) -> Any:
    """
    List what the AI extracted from a memory, optionally for one file.
    """
    get_memory_or_error(session, current_user, memory_id)
    condition = [col(ExtractedMemory.memory_id) == memory_id]
    if file_id is not None:
        condition.append(col(ExtractedMemory.file_id) == file_id)
    count = session.exec(
        select(func.count()).select_from(ExtractedMemory).where(*condition)
    ).one()
    extracted = session.exec(
        select(ExtractedMemory)
        .where(*condition)
        .order_by(col(ExtractedMemory.created_at).desc())
    ).all()
    return ExtractedMemoriesPublic(
        data=[ExtractedMemoryPublic.model_validate(e) for e in extracted], count=count
    )


@router.patch("/{extracted_id}", response_model=ExtractedMemoryPublic)
def update_extracted_memory(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    llm: LLMClientDep,
    memory_id: uuid.UUID,
    extracted_id: uuid.UUID,
    extracted_in: ExtractedMemoryUpdate,
) -> Any:
    """
    Edit an extracted memory, or reject it so it no longer appears in search.
    """
    extracted = get_extracted_or_error(session, current_user, memory_id, extracted_id)
    update = extracted_in.model_dump(exclude_unset=True)
    rejected = update.pop("rejected", None)
    if update:
        extracted.sqlmodel_update(update)
        try:
            # Search must find the corrected wording, not the old one
            (extracted.embedding,) = llm.embed(
                [
                    embedding_text(
                        extracted.content,
                        extracted.people,
                        extracted.event_date_text,
                        extracted.location,
                    )
                ]
            )
        except LLMError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        extracted.status = ExtractedStatus.EDITED
    if rejected is True:
        extracted.status = ExtractedStatus.REJECTED
    elif rejected is False and extracted.status == ExtractedStatus.REJECTED:
        extracted.status = ExtractedStatus.ACTIVE
    extracted.updated_at = get_datetime_utc()
    session.add(extracted)
    session.commit()
    session.refresh(extracted)
    return extracted


@router.delete("/{extracted_id}")
def delete_extracted_memory(
    session: SessionDep,
    current_user: CurrentUser,
    memory_id: uuid.UUID,
    extracted_id: uuid.UUID,
) -> Message:
    """
    Permanently delete an extracted memory.
    """
    extracted = get_extracted_or_error(session, current_user, memory_id, extracted_id)
    session.delete(extracted)
    session.commit()
    return Message(message="Extracted memory deleted successfully")
