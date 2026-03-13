"""
Partners and services endpoints (V2)
Get available partners/services based on user permissions
Uses V2 dynamic DataSourceConfig instead of V1 hardcoded file_b2_config/file_b3_config
"""

from typing import Any, List
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import distinct

from app.api.deps import get_db, get_current_user, get_user_permissions
from app.models import User, PartnerServiceConfig, UserPermission
from app.models.data_source import DataSourceConfig
from app.schemas.config import PartnerServiceSimple


router = APIRouter()


@router.get("/", response_model=List[PartnerServiceSimple])
async def list_partners_services(
    current_user: User = Depends(get_current_user),
    permissions: list = Depends(get_user_permissions),
    db: Session = Depends(get_db)
) -> Any:
    """Get list of partners and services the current user has access to"""
    if current_user.is_admin:
        configs = db.query(
            PartnerServiceConfig.partner_code,
            PartnerServiceConfig.partner_name,
            PartnerServiceConfig.service_code,
            PartnerServiceConfig.service_name
        ).filter(
            PartnerServiceConfig.is_active == True
        ).distinct().all()

        return [
            {
                "partner_code": c.partner_code,
                "partner_name": c.partner_name,
                "service_code": c.service_code,
                "service_name": c.service_name
            }
            for c in configs
        ]

    result = []
    for perm in permissions:
        if isinstance(perm, dict):
            result.append({
                "partner_code": perm["partner_code"],
                "partner_name": perm.get("partner_name", perm["partner_code"]),
                "service_code": perm["service_code"],
                "service_name": perm.get("service_name", perm["service_code"])
            })
        else:
            config = db.query(PartnerServiceConfig).filter(
                PartnerServiceConfig.partner_code == perm.partner_code,
                PartnerServiceConfig.service_code == perm.service_code,
                PartnerServiceConfig.is_active == True
            ).first()

            if config:
                result.append({
                    "partner_code": perm.partner_code,
                    "partner_name": config.partner_name,
                    "service_code": perm.service_code,
                    "service_name": config.service_name
                })

    return result


@router.get("/partners")
async def list_partners(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """Get unique list of partners the user has access to"""
    if current_user.is_admin:
        partners = db.query(
            distinct(PartnerServiceConfig.partner_code),
            PartnerServiceConfig.partner_name
        ).filter(
            PartnerServiceConfig.is_active == True
        ).all()

        return [
            {"partner_code": p[0], "partner_name": p[1]}
            for p in partners
        ]

    permissions = db.query(
        distinct(UserPermission.partner_code)
    ).filter(
        UserPermission.user_id == current_user.id
    ).all()

    partner_codes = [p[0] for p in permissions]

    partners = db.query(
        distinct(PartnerServiceConfig.partner_code),
        PartnerServiceConfig.partner_name
    ).filter(
        PartnerServiceConfig.partner_code.in_(partner_codes),
        PartnerServiceConfig.is_active == True
    ).all()

    return [
        {"partner_code": p[0], "partner_name": p[1]}
        for p in partners
    ]


@router.get("/services/{partner_code}")
async def list_services_for_partner(
    partner_code: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """Get services for a specific partner that user has access to"""
    if current_user.is_admin:
        services = db.query(
            distinct(PartnerServiceConfig.service_code),
            PartnerServiceConfig.service_name
        ).filter(
            PartnerServiceConfig.partner_code == partner_code,
            PartnerServiceConfig.is_active == True
        ).all()

        return [
            {"service_code": s[0], "service_name": s[1]}
            for s in services
        ]

    permissions = db.query(UserPermission.service_code).filter(
        UserPermission.user_id == current_user.id,
        UserPermission.partner_code == partner_code
    ).all()

    service_codes = [p[0] for p in permissions]

    services = db.query(
        distinct(PartnerServiceConfig.service_code),
        PartnerServiceConfig.service_name
    ).filter(
        PartnerServiceConfig.partner_code == partner_code,
        PartnerServiceConfig.service_code.in_(service_codes),
        PartnerServiceConfig.is_active == True
    ).all()

    return [
        {"service_code": s[0], "service_name": s[1]}
        for s in services
    ]


@router.get("/config/{partner_code}/{service_code}")
async def get_config_for_date(
    partner_code: str,
    service_code: str,
    target_date: date = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get configuration for a partner/service valid for a specific date.
    V2: Uses dynamic DataSourceConfig instead of hardcoded file_b2/b3 fields.
    """
    if target_date is None:
        target_date = date.today()

    config = db.query(PartnerServiceConfig).options(
        joinedload(PartnerServiceConfig.data_sources)
    ).filter(
        PartnerServiceConfig.partner_code == partner_code,
        PartnerServiceConfig.service_code == service_code,
        PartnerServiceConfig.is_active == True,
        PartnerServiceConfig.valid_from <= target_date,
        (PartnerServiceConfig.valid_to >= target_date) | (PartnerServiceConfig.valid_to == None)
    ).order_by(PartnerServiceConfig.valid_from.desc()).first()

    if not config:
        return None

    # V2: Dynamically check data sources instead of hardcoded has_b2/has_b3
    data_source_names = [ds.source_name for ds in (config.data_sources or [])]

    return {
        "id": config.id,
        "partner_code": config.partner_code,
        "partner_name": config.partner_name,
        "service_code": config.service_code,
        "service_name": config.service_name,
        "valid_from": config.valid_from,
        "valid_to": config.valid_to,
        "data_sources": data_source_names,
        "data_source_count": len(data_source_names),
        "has_report_template": config.report_template_path is not None
    }
