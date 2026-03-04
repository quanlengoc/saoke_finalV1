"""
API V2 Router
Mount all v2 endpoints here
"""

from fastapi import APIRouter
from app.api.v2.endpoints import configs, data_sources, workflows, outputs, reconciliation

api_router = APIRouter()

api_router.include_router(
    configs.router,
    prefix="/configs",
    tags=["configs"]
)

api_router.include_router(
    data_sources.router,
    prefix="/data-sources",
    tags=["data-sources"]
)

api_router.include_router(
    workflows.router,
    prefix="/workflows",
    tags=["workflows"]
)

api_router.include_router(
    outputs.router,
    prefix="/outputs",
    tags=["outputs"]
)

api_router.include_router(
    reconciliation.router,
    prefix="/reconciliation",
    tags=["reconciliation"]
)
