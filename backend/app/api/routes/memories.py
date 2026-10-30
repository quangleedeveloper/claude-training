import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from sqlmodel import col, func, select

from app import crud
from app.api.deps import CurrentUser, LLMClientDep, SessionDep, StorageDep
from app.api.routes.persons import get_person_or_error
from app.models import (
    ConfirmAllResult,
    ExtractedMemory,
    ExtractedStatus,
    MemoriesPublic,
    Memory,
    MemoryCreate,
    MemoryPersonLink,
    MemoryPublic,
    MemoryUpdate,
    Message,
    get_datetime_utc,
)
from app.services.conversation_summary import delete_person_summaries
from app.services.processing import extract_memory_story

router = APIRouter(prefix="/memories", tags=["memories"])


@router.get("/", response_model=MemoriesPublic)
def read_memories(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
    person_id: uuid.UUID | None = None,
) -> Any:
    """
    Retrieve memories, optionally only those linked to one person.
    """
    # Same scoping as before; the person filter only narrows what the caller can see
    conditions = []
    if not current_user.is_superuser:
        conditions.append(col(Memory.owner_id) == current_user.id)
    if person_id is not None:
        conditions.append(col(Memory.person_id) == person_id)

    count = session.exec(
        select(func.count()).select_from(Memory).where(*conditions)
    ).one()
    memories = session.exec(
        select(Memory)
        .where(*conditions)
        .order_by(col(Memory.created_at).desc())
        .offset(skip)
        .limit(limit)
    ).all()

    memories_public = [MemoryPublic.model_validate(memory) for memory in memories]
    return MemoriesPublic(data=memories_public, count=count)


@router.get("/{id}", response_model=MemoryPublic)
def read_memory(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """
    Get memory by ID.
    """
    memory = session.get(Memory, id)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    if not current_user.is_superuser and (memory.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return memory


@router.post("/", response_model=MemoryPublic)
def create_memory(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    llm: LLMClientDep,
    background_tasks: BackgroundTasks,
    memory_in: MemoryCreate,
) -> Any:
    """
    Create new memory.
    """
    memory = Memory.model_validate(memory_in, update={"owner_id": current_user.id})
    session.add(memory)
    session.commit()
    session.refresh(memory)
    background_tasks.add_task(extract_memory_story, memory.id, llm)
    return memory


@router.put("/{id}", response_model=MemoryPublic)
def update_memory(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    llm: LLMClientDep,
    background_tasks: BackgroundTasks,
    id: uuid.UUID,
    memory_in: MemoryUpdate,
) -> Any:
    """
    Update a memory.
    """
    memory = session.get(Memory, id)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    if not current_user.is_superuser and (memory.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    update_dict = memory_in.model_dump(exclude_unset=True)
    memory.sqlmodel_update(update_dict)
    session.add(memory)
    session.commit()
    session.refresh(memory)
    # The story or the person it is about changed, so what was extracted is stale
    if "content" in update_dict or "person_name" in update_dict:
        background_tasks.add_task(extract_memory_story, memory.id, llm)
    return memory


@router.post("/{id}/confirm-all", response_model=ConfirmAllResult)
def confirm_all_extracted(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Any:
    """
    Confirm every unconfirmed, non-rejected item extracted from a memory.
    """
    memory = session.get(Memory, id)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    # Strictly the owner's: confirming decides what the persona may say, so
    # superusers get no exception here
    if memory.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    pending = session.exec(
        select(ExtractedMemory).where(
            col(ExtractedMemory.memory_id) == memory.id,
            col(ExtractedMemory.status) != ExtractedStatus.REJECTED,
            col(ExtractedMemory.confirmed_at).is_(None),
        )
    ).all()
    now = get_datetime_utc()
    for extracted in pending:
        extracted.confirmed_at = now
        extracted.updated_at = now
        session.add(extracted)
    session.commit()
    return ConfirmAllResult(confirmed=len(pending))


@router.put("/{id}/person", response_model=MemoryPublic)
def link_memory_person(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    link_in: MemoryPersonLink,
) -> Any:
    """
    Link a memory to one of the caller's persons, or unlink it with null.
    """
    memory = session.get(Memory, id)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    # Strictly the owner's: linking exposes the memory to the persona, so superusers
    # get no exception here
    if memory.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    if link_in.person_id is not None:
        person = get_person_or_error(session, current_user, link_in.person_id)
        # The AI reads stories "about <name>", so the name follows the link
        memory.person_name = person.name
    memory.person_id = link_in.person_id
    session.add(memory)
    session.commit()
    session.refresh(memory)
    return memory


@router.delete("/{id}")
def delete_memory(
    session: SessionDep, current_user: CurrentUser, storage: StorageDep, id: uuid.UUID
) -> Message:
    """
    Delete a memory.
    """
    memory = session.get(Memory, id)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    if not current_user.is_superuser and (memory.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    crud.remove_memory_files(session=session, storage=storage, memory_ids=[memory.id])
    # A summary may repeat something from this memory, so those go with it
    if memory.person_id is not None:
        delete_person_summaries(session, memory.person_id)
    session.delete(memory)
    session.commit()
    return Message(message="Memory deleted successfully")
