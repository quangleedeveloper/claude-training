import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import sentry_sdk
from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.concurrency import run_in_threadpool
from starlette.middleware.cors import CORSMiddleware

from app.api.main import api_router
from app.core.checkpoint import setup_checkpoint_tables
from app.core.config import settings

logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).parent / "frontend"


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


if settings.SENTRY_DSN and settings.FASTAPI_ENV != "development":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Resumable processing needs LangGraph's tables. Creating them here means a
    # start without the prestart step still works. A failure is logged, not fatal:
    # the rest of the app does not need them, and each file that does shows why.
    try:
        await run_in_threadpool(setup_checkpoint_tables)
    except Exception:
        logger.exception(
            "Could not create the LangGraph checkpoint tables; processing files "
            "will fail until they exist (run scripts/prestart.sh)"
        )
    yield


app = FastAPI(
    lifespan=lifespan,
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_HOST],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)
app.frontend("/", directory=FRONTEND_DIR)
