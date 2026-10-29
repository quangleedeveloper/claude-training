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
    Memory,
    Message,
    User,
    get_datetime_utc,
)
from app.services.conversation_summary import delete_person_summaries
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


def get_own_extracted_or_error(
    session: Session, current_user: User, memory_id: uuid.UUID, extracted_id: uuid.UUID
) -> ExtractedMemory:
    """Like `get_extracted_or_error`, but only for the memory's owner: confirming
    decides what the persona may say, so superusers get no exception."""
    extracted = get_extracted_or_error(session, current_user, memory_id, extracted_id)
    memory = session.get(Memory, memory_id)
    if memory is None or memory.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return extracted


def check_editable(
    extracted: ExtractedMemory, update: dict[str, Any], rejected: bool | None
) -> None:
    """A rejected item can only be restored, not edited: editing it would quietly
    bring it back into search."""
    if (
        update
        and extracted.status == ExtractedStatus.REJECTED
        and rejected is not False
    ):
        raise HTTPException(
            status_code=409, detail="Restore the item before editing it"
        )


def forget_summaries(session: Session, memory_id: uuid.UUID) -> None:
    """Delete the summaries of the person this memory is linked to, if any. The
    caller commits."""
    memory = session.get(Memory, memory_id)
    if memory is not None and memory.person_id is not None:
        delete_person_summaries(session, memory.person_id)


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
    check_editable(extracted, update, rejected)
    if update:
        # The model call is slow: end the read transaction first so no database
        # connection is held while Ollama works, then load the item again
        wording = {
            field: update.get(field, getattr(extracted, field))
            for field in ("content", "people", "event_date_text", "location")
        }
        session.rollback()
        try:
            # Search must find the corrected wording, not the old one
            (vector,) = llm.embed([embedding_text(**wording)])
        except LLMError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        extracted = get_extracted_or_error(
            session, current_user, memory_id, extracted_id
        )
        check_editable(extracted, update, rejected)
        restoring = rejected is False and extracted.status == ExtractedStatus.REJECTED
        extracted.sqlmodel_update(update)
        extracted.embedding = vector
        extracted.was_edited = True
        extracted.status = ExtractedStatus.EDITED
        # Correcting an item counts as confirming it (AC-2.2), but only when the
        # owner does it: a superuser may edit anyone's items, and that must not
        # widen what the persona is allowed to say
        memory = session.get(Memory, memory_id)
        if (
            extracted.confirmed_at is None
            and memory is not None
            and memory.owner_id == current_user.id
        ):
            extracted.confirmed_at = get_datetime_utc()
    else:
        restoring = rejected is False and extracted.status == ExtractedStatus.REJECTED
    if rejected is True:
        extracted.status = ExtractedStatus.REJECTED
    elif restoring:
        extracted.status = (
            ExtractedStatus.EDITED if extracted.was_edited else ExtractedStatus.ACTIVE
        )
    extracted.updated_at = get_datetime_utc()
    session.add(extracted)
    if update or rejected is True:
        # A summary may still hold the old value or the rejected fact
        forget_summaries(session, memory_id)
    session.commit()
    session.refresh(extracted)
    return extracted


@router.post("/{extracted_id}/confirm", response_model=ExtractedMemoryPublic)
def confirm_extracted_memory(
    session: SessionDep,
    current_user: CurrentUser,
    memory_id: uuid.UUID,
    extracted_id: uuid.UUID,
) -> Any:
    """
    Confirm an extracted memory so the persona may use it.
    """
    extracted = get_own_extracted_or_error(
        session, current_user, memory_id, extracted_id
    )
    if extracted.status == ExtractedStatus.REJECTED:
        raise HTTPException(
            status_code=409, detail="Restore the item before confirming it"
        )
    if extracted.confirmed_at is None:
        extracted.confirmed_at = get_datetime_utc()
        extracted.updated_at = get_datetime_utc()
        session.add(extracted)
        session.commit()
        session.refresh(extracted)
    return extracted


@router.delete("/{extracted_id}/confirm", response_model=ExtractedMemoryPublic)
def unconfirm_extracted_memory(
    session: SessionDep,
    current_user: CurrentUser,
    memory_id: uuid.UUID,
    extracted_id: uuid.UUID,
) -> Any:
    """
    Undo the confirmation so the persona stops using the item.
    """
    extracted = get_own_extracted_or_error(
        session, current_user, memory_id, extracted_id
    )
    if extracted.confirmed_at is not None:
        extracted.confirmed_at = None
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
    forget_summaries(session, memory_id)
    session.commit()
    return Message(message="Extracted memory deleted successfully")
