import uuid
from collections.abc import Sequence
from typing import Any

from sqlmodel import Session, col, select

from app.core.checkpoint import clear_thread
from app.core.security import get_password_hash, verify_password
from app.core.storage import FileStorage
from app.models import (
    Item,
    ItemCreate,
    Memory,
    MemoryCreate,
    MemoryFile,
    MemoryFileKind,
    User,
    UserCreate,
    UserUpdate,
)


def create_user(*, session: Session, user_create: UserCreate) -> User:
    db_obj = User.model_validate(
        user_create, update={"hashed_password": get_password_hash(user_create.password)}
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> Any:
    user_data = user_in.model_dump(exclude_unset=True)
    extra_data = {}
    if "password" in user_data:
        password = user_data["password"]
        hashed_password = get_password_hash(password)
        extra_data["hashed_password"] = hashed_password
    db_user.sqlmodel_update(user_data, update=extra_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


def get_user_by_email(*, session: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    session_user = session.exec(statement).first()
    return session_user


# Dummy hash to use for timing attack prevention when user is not found
# This is an Argon2 hash of a random password, used to ensure constant-time comparison
DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$MjQyZWE1MzBjYjJlZTI0Yw$YTU4NGM5ZTZmYjE2NzZlZjY0ZWY3ZGRkY2U2OWFjNjk"


def authenticate(*, session: Session, email: str, password: str) -> User | None:
    db_user = get_user_by_email(session=session, email=email)
    if not db_user:
        # Prevent timing attacks by running password verification even when user doesn't exist
        # This ensures the response time is similar whether or not the email exists
        verify_password(password, DUMMY_HASH)
        return None
    verified, updated_password_hash = verify_password(password, db_user.hashed_password)
    if not verified:
        return None
    if updated_password_hash:
        db_user.hashed_password = updated_password_hash
        session.add(db_user)
        session.commit()
        session.refresh(db_user)
    return db_user


def create_item(*, session: Session, item_in: ItemCreate, owner_id: uuid.UUID) -> Item:
    db_item = Item.model_validate(item_in, update={"owner_id": owner_id})
    session.add(db_item)
    session.commit()
    session.refresh(db_item)
    return db_item


def create_memory(
    *, session: Session, memory_in: MemoryCreate, owner_id: uuid.UUID
) -> Memory:
    db_memory = Memory.model_validate(memory_in, update={"owner_id": owner_id})
    session.add(db_memory)
    session.commit()
    session.refresh(db_memory)
    return db_memory


def create_memory_file(
    *,
    session: Session,
    memory_id: uuid.UUID,
    file_id: uuid.UUID,
    filename: str,
    content_type: str,
    kind: MemoryFileKind,
    size_bytes: int,
    storage_key: str,
) -> MemoryFile:
    db_file = MemoryFile(
        id=file_id,
        memory_id=memory_id,
        filename=filename,
        content_type=content_type,
        kind=kind,
        size_bytes=size_bytes,
        storage_key=storage_key,
    )
    session.add(db_file)
    session.commit()
    session.refresh(db_file)
    return db_file


def remove_memory_files(
    *, session: Session, storage: FileStorage, memory_ids: Sequence[uuid.UUID]
) -> None:
    """Delete stored bytes and saved processing progress; the rows go with their
    memory (DB cascade).

    Call this before deleting the memories or their owner, or the files are orphaned.
    """
    if not memory_ids:
        return
    statement = select(MemoryFile.id, MemoryFile.storage_key).where(
        col(MemoryFile.memory_id).in_(memory_ids)
    )
    for file_id, storage_key in session.exec(statement).all():
        storage.delete(storage_key)
        clear_thread(str(file_id))
