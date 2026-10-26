import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from sqlmodel import col, func, select

from app import crud
from app.api.deps import CurrentUser, LLMClientDep, SessionDep, StorageDep
from app.models import (
    MemoriesPublic,
    Memory,
    MemoryCreate,
    MemoryPublic,
    MemoryUpdate,
    Message,
)
from app.services.processing import extract_memory_story

router = APIRouter(prefix="/memories", tags=["memories"])


@router.get("/", response_model=MemoriesPublic)
def read_memories(
    session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 100
) -> Any:
    """
    Retrieve memories.
    """

    if current_user.is_superuser:
        count_statement = select(func.count()).select_from(Memory)
        count = session.exec(count_statement).one()
        statement = (
            select(Memory)
            .order_by(col(Memory.created_at).desc())
            .offset(skip)
            .limit(limit)
        )
        memories = session.exec(statement).all()
    else:
        count_statement = (
            select(func.count())
            .select_from(Memory)
            .where(Memory.owner_id == current_user.id)
        )
        count = session.exec(count_statement).one()
        statement = (
            select(Memory)
            .where(Memory.owner_id == current_user.id)
            .order_by(col(Memory.created_at).desc())
            .offset(skip)
            .limit(limit)
        )
        memories = session.exec(statement).all()

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
    session.delete(memory)
    session.commit()
    return Message(message="Memory deleted successfully")
