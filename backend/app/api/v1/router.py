from fastapi import APIRouter
from app.api.v1.endpoints import queries, export

api_router = APIRouter()
api_router.include_router(queries.router, prefix="/queries", tags=["Queries"])
api_router.include_router(export.router, prefix="/export", tags=["Export"])