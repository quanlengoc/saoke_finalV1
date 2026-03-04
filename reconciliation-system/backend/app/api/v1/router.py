"""
API v1 Router
Combines all endpoint routers
"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, partners, configs, reconciliation, reports, approvals, mock_data


router = APIRouter()

# Auth endpoints - no prefix
router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"]
)

# User management - admin only
router.include_router(
    users.router,
    prefix="/users",
    tags=["Users"]
)

# Partners and services
router.include_router(
    partners.router,
    prefix="/partners",
    tags=["Partners"]
)

# Configuration management - admin only
router.include_router(
    configs.router,
    prefix="/configs",
    tags=["Configurations"]
)

# Mock data management - admin only
router.include_router(
    mock_data.router,
    prefix="/mock-data",
    tags=["Mock Data"]
)

# Reconciliation operations
router.include_router(
    reconciliation.router,
    prefix="/reconciliation",
    tags=["Reconciliation"]
)

# Reports and downloads
router.include_router(
    reports.router,
    prefix="/reports",
    tags=["Reports"]
)

# Approval workflow
router.include_router(
    approvals.router,
    prefix="/approvals",
    tags=["Approvals"]
)
