
import asyncio
import logging

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.schema_init import init_db
from app.api.v1.router import api_router
from app.services.retention import cleanup_expired_records


logger = logging.getLogger(__name__)


async def retention_worker():
    """
    Run cleanup immediately, then repeat at the
    configured interval.
    """

    while True:
        try:
            deleted = await asyncio.to_thread(
                cleanup_expired_records
            )

            logger.info(
                "Retention worker finished. Deleted: %s",
                deleted
            )

        except Exception:
            logger.exception(
                "Retention worker encountered an error"
            )

        await asyncio.sleep(
            settings.CLEANUP_INTERVAL_SECONDS
        )


@asynccontextmanager
async def lifespan(app: FastAPI):

    init_db()

    cleanup_task = asyncio.create_task(
        retention_worker()
    )

    try:
        yield

    finally:
        cleanup_task.cancel()

        try:
            await cleanup_task
        except asyncio.CancelledError:
            logger.info("Retention worker stopped.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    api_router,
    prefix=settings.API_V1_STR
)


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "QueryShark Monitoring System"
    }
