import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import EmailStr
from sqlalchemy import BigInteger
from sqlmodel import Field, Relationship, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(UTC)


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(SQLModel):
    email: EmailStr | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    is_superuser: bool | None = None
    full_name: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    created_at: datetime | None = Field(default_factory=get_datetime_utc)
    items: list[Item] = Relationship(back_populates="owner", cascade_delete=True)
    memories: list[Memory] = Relationship(back_populates="owner", cascade_delete=True)


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime | None = None


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# Shared properties
class ItemBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Properties to receive on item creation
class ItemCreate(ItemBase):
    pass


# Properties to receive on item update
class ItemUpdate(SQLModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Database model, database table inferred from class name
class Item(ItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(default_factory=get_datetime_utc)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="items")


# Properties to return via API, id is always required
class ItemPublic(ItemBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None


class ItemsPublic(SQLModel):
    data: list[ItemPublic]
    count: int


# Shared properties
class MemoryBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    person_name: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=5000)


# Properties to receive on memory creation
class MemoryCreate(MemoryBase):
    pass


# Properties to receive on memory update
class MemoryUpdate(SQLModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    person_name: str | None = Field(default=None, min_length=1, max_length=255)
    content: str | None = Field(default=None, min_length=1, max_length=5000)


# Database model, database table inferred from class name
class Memory(MemoryBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(default_factory=get_datetime_utc)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="memories")
    files: list[MemoryFile] = Relationship(back_populates="memory", cascade_delete=True)


# Properties to return via API, id is always required
class MemoryPublic(MemoryBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None


class MemoriesPublic(SQLModel):
    data: list[MemoryPublic]
    count: int


class MemoryFileKind(StrEnum):
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"


class MemoryFileStatus(StrEnum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


# Database model; kind and status are stored as plain VARCHAR (not a Postgres enum)
# so adding a value later never needs an ALTER TYPE migration
class MemoryFile(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    memory_id: uuid.UUID = Field(
        foreign_key="memory.id", nullable=False, ondelete="CASCADE", index=True
    )
    filename: str = Field(max_length=255)
    content_type: str = Field(max_length=100)
    kind: str = Field(max_length=20)
    # BigInteger: the size limits are configurable and may exceed 2 GB
    size_bytes: int = Field(sa_type=BigInteger)
    # Server-generated, never derived from user input
    storage_key: str = Field(max_length=255)
    status: str = Field(default=MemoryFileStatus.UPLOADED, max_length=20)
    error_message: str | None = Field(default=None, max_length=500)
    created_at: datetime | None = Field(default_factory=get_datetime_utc)
    processed_at: datetime | None = None
    memory: Memory | None = Relationship(back_populates="files")


# Properties to return via API
class MemoryFilePublic(SQLModel):
    id: uuid.UUID
    memory_id: uuid.UUID
    filename: str
    content_type: str
    kind: MemoryFileKind
    size_bytes: int
    status: MemoryFileStatus
    error_message: str | None = None
    created_at: datetime | None = None
    processed_at: datetime | None = None


class MemoryFilesPublic(SQLModel):
    data: list[MemoryFilePublic]
    count: int


class RejectedMemoryFile(SQLModel):
    filename: str
    reason: str


# Each uploaded file succeeds or is rejected on its own
class MemoryFilesUploadResult(SQLModel):
    uploaded: list[MemoryFilePublic]
    rejected: list[RejectedMemoryFile]


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)
