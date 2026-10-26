import logging
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session, col, func, select

from app import crud
from app.api.deps import CurrentUser, MediaProcessorDep, SessionDep, StorageDep
from app.core.config import settings
from app.core.storage import FileTooLargeError
from app.models import (
    Memory,
    MemoryFile,
    MemoryFilePublic,
    MemoryFilesPublic,
    MemoryFileStatus,
    MemoryFilesUploadResult,
    Message,
    RejectedMemoryFile,
    User,
)
from app.services.media import (
    HEAD_BYTES,
    MediaValidationError,
    display_filename,
    format_size,
    max_bytes_for,
    validate_media,
)
from app.services.processing import process_memory_file

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memories/{memory_id}/files", tags=["memory_files"])


def get_memory_or_error(
    session: Session, current_user: User, memory_id: uuid.UUID
) -> Memory:
    memory = session.get(Memory, memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    if not current_user.is_superuser and (memory.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return memory


def get_file_or_error(
    session: Session, current_user: User, memory_id: uuid.UUID, file_id: uuid.UUID
) -> MemoryFile:
    get_memory_or_error(session, current_user, memory_id)
    memory_file = session.get(MemoryFile, file_id)
    if not memory_file or memory_file.memory_id != memory_id:
        raise HTTPException(status_code=404, detail="File not found")
    return memory_file


@router.get("/", response_model=MemoryFilesPublic)
def read_memory_files(
    session: SessionDep, current_user: CurrentUser, memory_id: uuid.UUID
) -> Any:
    """
    List the files of a memory with their processing status.
    """
    get_memory_or_error(session, current_user, memory_id)
    count = session.exec(
        select(func.count())
        .select_from(MemoryFile)
        .where(MemoryFile.memory_id == memory_id)
    ).one()
    statement = (
        select(MemoryFile)
        .where(MemoryFile.memory_id == memory_id)
        .order_by(col(MemoryFile.created_at).desc())
    )
    memory_files = session.exec(statement).all()
    return MemoryFilesPublic(
        data=[MemoryFilePublic.model_validate(f) for f in memory_files], count=count
    )


@router.post("/", response_model=MemoryFilesUploadResult)
def upload_memory_files(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    storage: StorageDep,
    processor: MediaProcessorDep,
    background_tasks: BackgroundTasks,
    memory_id: uuid.UUID,
    files: Annotated[list[UploadFile], File()],
) -> Any:
    """
    Upload photos, videos and audio to a memory; each file is accepted or rejected alone.
    """
    memory = get_memory_or_error(session, current_user, memory_id)
    if len(files) > settings.MAX_FILES_PER_UPLOAD:
        raise HTTPException(
            status_code=400,
            detail=f"Too many files: at most {settings.MAX_FILES_PER_UPLOAD} per upload",
        )

    uploaded: list[MemoryFile] = []
    rejected: list[RejectedMemoryFile] = []
    for upload in files:
        filename = display_filename(upload.filename)
        try:
            head = upload.file.read(HEAD_BYTES)
            upload.file.seek(0)
            media = validate_media(filename, head)
            limit = max_bytes_for(media.kind)
            if upload.size is not None and upload.size > limit:
                raise FileTooLargeError(limit)
            file_id = uuid.uuid4()
            storage_key = f"{memory.id}/{file_id}{media.extension}"
            size_bytes = storage.save(upload.file, storage_key, limit)
        except MediaValidationError as exc:
            rejected.append(RejectedMemoryFile(filename=filename, reason=exc.reason))
            continue
        except FileTooLargeError as exc:
            reason = f"File is larger than the {format_size(exc.max_bytes)} limit"
            rejected.append(RejectedMemoryFile(filename=filename, reason=reason))
            continue
        except OSError:
            logger.exception("Could not store upload %s", filename)
            reason = "The file could not be stored, please try again"
            rejected.append(RejectedMemoryFile(filename=filename, reason=reason))
            continue

        try:
            memory_file = crud.create_memory_file(
                session=session,
                memory_id=memory.id,
                file_id=file_id,
                filename=filename,
                content_type=media.content_type,
                kind=media.kind,
                size_bytes=size_bytes,
                storage_key=storage_key,
            )
        except Exception:
            # Don't leave bytes behind for a row that was never written
            session.rollback()
            storage.delete(storage_key)
            raise
        uploaded.append(memory_file)

    for memory_file in uploaded:
        background_tasks.add_task(
            process_memory_file, memory_file.id, processor, storage
        )
    return MemoryFilesUploadResult(
        uploaded=[MemoryFilePublic.model_validate(f) for f in uploaded],
        rejected=rejected,
    )


@router.get("/{file_id}/content")
def read_memory_file_content(
    session: SessionDep,
    current_user: CurrentUser,
    storage: StorageDep,
    memory_id: uuid.UUID,
    file_id: uuid.UUID,
) -> Any:
    """
    Download the original file.
    """
    memory_file = get_file_or_error(session, current_user, memory_id, file_id)
    if not storage.exists(memory_file.storage_key):
        raise HTTPException(status_code=404, detail="File content not found")
    return FileResponse(
        storage.path(memory_file.storage_key),
        media_type=memory_file.content_type,
        filename=memory_file.filename,
        content_disposition_type="inline",
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.post("/{file_id}/retry", response_model=MemoryFilePublic)
def retry_memory_file(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    storage: StorageDep,
    processor: MediaProcessorDep,
    background_tasks: BackgroundTasks,
    memory_id: uuid.UUID,
    file_id: uuid.UUID,
) -> Any:
    """
    Process a failed file again.
    """
    memory_file = get_file_or_error(session, current_user, memory_id, file_id)
    if memory_file.status != MemoryFileStatus.FAILED:
        raise HTTPException(status_code=400, detail="Only failed files can be retried")
    memory_file.status = MemoryFileStatus.UPLOADED
    memory_file.error_message = None
    session.add(memory_file)
    session.commit()
    session.refresh(memory_file)
    background_tasks.add_task(process_memory_file, memory_file.id, processor, storage)
    return memory_file


@router.delete("/{file_id}")
def delete_memory_file(
    session: SessionDep,
    current_user: CurrentUser,
    storage: StorageDep,
    memory_id: uuid.UUID,
    file_id: uuid.UUID,
) -> Message:
    """
    Delete a file from a memory.
    """
    memory_file = get_file_or_error(session, current_user, memory_id, file_id)
    storage_key = memory_file.storage_key
    session.delete(memory_file)
    session.commit()
    storage.delete(storage_key)
    return Message(message="File deleted successfully")
