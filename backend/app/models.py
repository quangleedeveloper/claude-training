import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Self

from pgvector.sqlalchemy import Vector
from pydantic import EmailStr, computed_field, field_validator, model_validator
from sqlalchemy import JSON, BigInteger, Column, Index, Text
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
    persons: list[Person] = Relationship(back_populates="owner", cascade_delete=True)


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


MAX_OTHER_NAMES = 10


def clean_other_names(names: list[str] | None) -> list[str] | None:
    """Trim each name and drop case-insensitive duplicates, keeping the first."""
    if names is None:
        return None
    if len(names) > MAX_OTHER_NAMES:
        raise ValueError(f"at most {MAX_OTHER_NAMES} other names")
    cleaned: list[str] = []
    seen: set[str] = set()
    for name in names:
        name = name.strip()
        if not 1 <= len(name) <= 255:
            raise ValueError("each other name must be 1 to 255 characters")
        if name.casefold() not in seen:
            seen.add(name.casefold())
            cleaned.append(name)
    return cleaned


# Shared properties
class PersonBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    # What the family calls them besides `name` ("Mom", "Mẹ")
    other_names: list[str] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )

    @field_validator("other_names")
    @classmethod
    def clean_names(cls, value: list[str]) -> list[str]:
        return clean_other_names(value) or []


# Properties to receive on person creation
class PersonCreate(PersonBase):
    pass


# Properties to receive on person update
class PersonUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    other_names: list[str] | None = None

    @field_validator("other_names")
    @classmethod
    def clean_names(cls, value: list[str] | None) -> list[str] | None:
        return clean_other_names(value)

    @model_validator(mode="after")
    def refuse_null_fields(self) -> Self:
        for name in ("name", "other_names"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


# Someone the family remembers. The owner links their memories to it; later
# tickets hang the persona, its conversations and its members off `person.id`.
# `memory.person_id` is SET NULL, so deleting a person never deletes memories.
class Person(PersonBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(default_factory=get_datetime_utc)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE", index=True
    )
    owner: User | None = Relationship(back_populates="persons")


# Properties to return via API, id is always required
class PersonPublic(PersonBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None


class PersonsPublic(SQLModel):
    data: list[PersonPublic]
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


class MemoryExtractionStatus(StrEnum):
    IDLE = "idle"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


# Database model, database table inferred from class name
class Memory(MemoryBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(default_factory=get_datetime_utc)
    # State of reading the written story. Plain VARCHAR like the other statuses;
    # the server default keeps memories that existed before this column as "done"
    extraction_status: str = Field(
        default=MemoryExtractionStatus.DONE,
        max_length=20,
        sa_column_kwargs={"server_default": MemoryExtractionStatus.DONE.value},
    )
    # A message written for users (see UserFacingError), never a raw exception
    extraction_error: str | None = Field(default=None, max_length=500)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    # Not a Relationship on purpose: one declared with cascade_delete would delete
    # the memories along with the person
    person_id: uuid.UUID | None = Field(
        default=None, foreign_key="person.id", ondelete="SET NULL", index=True
    )
    owner: User | None = Relationship(back_populates="memories")
    files: list[MemoryFile] = Relationship(back_populates="memory", cascade_delete=True)


# Properties to return via API, id is always required
class MemoryPublic(MemoryBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None
    person_id: uuid.UUID | None = None
    extraction_status: MemoryExtractionStatus
    extraction_error: str | None = None


# `person_id: null` unlinks the memory
class MemoryPersonLink(SQLModel):
    person_id: uuid.UUID | None = None


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
    # Transcript (audio/video) or caption (image) the extracted memories came from
    extracted_text: str | None = Field(default=None, sa_type=Text)
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
    extracted_text: str | None = None
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


# Must match the embedding model's output size (nomic-embed-text is 768)
EMBEDDING_DIMENSIONS = 768


class ExtractedCategory(StrEnum):
    EVENT = "event"
    PERSON = "person"
    PLACE = "place"
    FACT = "fact"
    QUOTE = "quote"


class ExtractedStatus(StrEnum):
    ACTIVE = "active"
    EDITED = "edited"
    REJECTED = "rejected"


class ExtractedSource(StrEnum):
    STORY = "story"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"


# One fact the AI pulled out of a story or an uploaded file. Dates stay free text
# ("summer 1998") because the source is often vague or contradicts another item;
# `confidence` tells the reviewer how far to trust it. Enums are plain VARCHAR.
class ExtractedMemory(SQLModel, table=True):
    # Approximate nearest-neighbour index for cosine search (see retrieval.py)
    __table_args__ = (
        Index(
            "ix_extractedmemory_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    memory_id: uuid.UUID = Field(
        foreign_key="memory.id", nullable=False, ondelete="CASCADE", index=True
    )
    # None when the item came from the memory's written story
    file_id: uuid.UUID | None = Field(
        default=None, foreign_key="memoryfile.id", ondelete="CASCADE", index=True
    )
    category: str = Field(max_length=20)
    content: str = Field(max_length=2000)
    people: list[str] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    event_date_text: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=255)
    confidence: float
    status: str = Field(default=ExtractedStatus.ACTIVE, max_length=20)
    # Stays true once the user edits the item, also while it is rejected, so a
    # restore goes back to EDITED and a re-extraction never replaces their wording
    was_edited: bool = Field(
        default=False, sa_column_kwargs={"server_default": "false"}
    )
    # Set when a family member confirms the item or corrects it; the persona only
    # reads confirmed items. Cleared by undoing the confirmation.
    confirmed_at: datetime | None = None
    source: str = Field(max_length=20)
    embedding: list[float] = Field(
        sa_column=Column(Vector(EMBEDDING_DIMENSIONS), nullable=False)
    )
    created_at: datetime | None = Field(default_factory=get_datetime_utc)
    updated_at: datetime | None = Field(default_factory=get_datetime_utc)


class ExtractedMemoryPublic(SQLModel):
    id: uuid.UUID
    memory_id: uuid.UUID
    file_id: uuid.UUID | None = None
    category: ExtractedCategory
    content: str
    people: list[str]
    event_date_text: str | None = None
    location: str | None = None
    confidence: float
    status: ExtractedStatus
    source: ExtractedSource
    confirmed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def confirmed(self) -> bool:
        return self.confirmed_at is not None


class ExtractedMemoriesPublic(SQLModel):
    data: list[ExtractedMemoryPublic]
    count: int


# How many items "confirm all" newly confirmed on a memory
class ConfirmAllResult(SQLModel):
    confirmed: int


# Editing any field marks the item as edited; `rejected` removes it from search.
# Omit a field to leave it alone. `event_date_text` and `location` may be sent as
# null to clear them; the other three are required on the item, so null is refused.
class ExtractedMemoryUpdate(SQLModel):
    category: ExtractedCategory | None = None
    content: str | None = Field(default=None, min_length=1, max_length=2000)
    people: list[str] | None = None
    event_date_text: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=255)
    rejected: bool | None = None

    @model_validator(mode="after")
    def refuse_null_required_fields(self) -> Self:
        for name in ("category", "content", "people"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class SearchRequest(SQLModel):
    query: str = Field(min_length=1, max_length=500)
    memory_id: uuid.UUID | None = None
    limit: int | None = Field(default=None, ge=1, le=20)
    # Superusers only: search everyone's memories instead of their own
    all_users: bool = False


class SearchHit(SQLModel):
    item: ExtractedMemoryPublic
    memory_title: str
    person_name: str
    # Cosine similarity, 1 is identical
    score: float


class SearchResults(SQLModel):
    data: list[SearchHit]


class AskRequest(SQLModel):
    question: str = Field(min_length=1, max_length=500)
    memory_id: uuid.UUID | None = None
    # Superusers only: answer from everyone's memories instead of their own
    all_users: bool = False


class AskResponse(SQLModel):
    answer: str
    sources: list[SearchHit]


class ConversationStatus(StrEnum):
    OPEN = "open"
    ENDED = "ended"


class MessageRole(StrEnum):
    USER = "user"
    PERSONA = "persona"


# Enums are plain VARCHAR here, like the other statuses.
# One sitting between a user and a person's persona. The messages hold what was said
# and are deleted when the conversation ends; `PersonaTurn` keeps only ids and
# timings, never text. Everything cascades from the person and from the user.
class Conversation(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    person_id: uuid.UUID = Field(
        foreign_key="person.id", nullable=False, ondelete="CASCADE", index=True
    )
    user_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE", index=True
    )
    status: str = Field(default=ConversationStatus.OPEN, max_length=16)
    created_at: datetime = Field(default_factory=get_datetime_utc)
    last_message_at: datetime = Field(default_factory=get_datetime_utc)
    ended_at: datetime | None = None


class ConversationMessage(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    conversation_id: uuid.UUID = Field(
        foreign_key="conversation.id", nullable=False, ondelete="CASCADE", index=True
    )
    role: str = Field(max_length=16)
    content: str = Field(sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=get_datetime_utc)


# Audit row, one per answered turn: ids and timings only (no text).
class PersonaTurn(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    conversation_id: uuid.UUID = Field(
        foreign_key="conversation.id", nullable=False, ondelete="CASCADE", index=True
    )
    item_ids: list[str] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    fallback: bool = False
    first_token_ms: int | None = None
    total_ms: int | None = None
    created_at: datetime = Field(default_factory=get_datetime_utc)


class ConversationOpened(SQLModel):
    conversation_id: uuid.UUID
    notice: str


class SendMessageRequest(SQLModel):
    text: str = Field(min_length=1, max_length=2000)


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
