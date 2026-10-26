from fastapi import APIRouter

from app.api.routes import (
    extracted_memories,
    items,
    login,
    memories,
    memory_files,
    private,
    search,
    users,
    utils,
)
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(items.router)
api_router.include_router(memories.router)
api_router.include_router(memory_files.router)
api_router.include_router(extracted_memories.router)
api_router.include_router(search.router)


if settings.FASTAPI_ENV == "development":
    api_router.include_router(private.router)
