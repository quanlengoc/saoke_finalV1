"""
API V2 Router
Mount all v2 endpoints here
"""

from fastapi import APIRouter
from app.api.v2.endpoints import (
    configs, data_sources, workflows, outputs, reconciliation,
    auth, users, partners, reports, approvals, mock_data
)

api_router = APIRouter()

# --- Auth & Users ---
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["auth"]
)

api_router.include_router(
    users.router,
    prefix="/users",
    tags=["users"]
)

api_router.include_router(
    partners.router,
    prefix="/partners",
    tags=["partners"]
)

# --- Core V2 ---
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

# --- Reports & Approvals ---
api_router.include_router(
    reports.router,
    prefix="/reports",
    tags=["reports"]
)

api_router.include_router(
    approvals.router,
    prefix="/approvals",
    tags=["approvals"]
)

# --- Admin Tools ---
api_router.include_router(
    mock_data.router,
    prefix="/mock-data",
    tags=["mock-data"]
)
