"""
API Dependencies
Common dependencies for FastAPI endpoints
"""

from typing import Generator, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import DatabaseManager
from app.core.security import decode_access_token
from app.models import User, UserPermission


# Security scheme
security = HTTPBearer()


def get_db() -> Generator[Session, None, None]:
    """Get database session"""
    yield from DatabaseManager.get_app_session()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Get current authenticated user from JWT token
    
    Raises:
        HTTPException 401: If token is invalid or user not found
    """
    token = credentials.credentials
    print(f"[DEBUG] Token received: {token[:30]}..." if token else "[DEBUG] No token")
    
    payload = decode_access_token(token)
    
    if payload is None:
        print("[DEBUG] Token decode failed - invalid or expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    print(f"[DEBUG] Token payload sub: {user_id}")
    
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = db.query(User).filter(User.id == int(user_id)).first()
    
    if user is None:
        print(f"[DEBUG] User not found for id: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    print(f"[DEBUG] User found: {user.email}, is_admin={user.is_admin}")
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled",
        )
    
    return user


async def get_current_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current user and verify admin privileges
    
    Raises:
        HTTPException 403: If user is not admin
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user


def check_permission(
    partner_code: str,
    service_code: str,
    action: str = "reconcile"
):
    """
    Dependency factory to check user permission for partner/service
    
    Args:
        partner_code: Partner code to check
        service_code: Service code to check
        action: Action to check - "reconcile" or "approve"
    
    Returns:
        Dependency function
    """
    async def _check_permission(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> User:
        # Admin has all permissions
        if current_user.is_admin:
            return current_user
        
        # Check user permission
        permission = db.query(UserPermission).filter(
            UserPermission.user_id == current_user.id,
            UserPermission.partner_code == partner_code,
            UserPermission.service_code == service_code
        ).first()
        
        if not permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"No permission for {partner_code}/{service_code}"
            )
        
        if action == "reconcile" and not permission.can_reconcile:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No reconciliation permission"
            )
        
        if action == "approve" and not permission.can_approve:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No approval permission"
            )
        
        return current_user
    
    return _check_permission


async def get_user_permissions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> list:
    """
    Get list of partner/service permissions for current user
    
    Returns:
        List of UserPermission objects
    """
    if current_user.is_admin:
        # Admin can access all - return all distinct partner/service combinations
        from app.models import PartnerServiceConfig
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
                "service_name": c.service_name,
                "can_reconcile": True,
                "can_approve": True
            }
            for c in configs
        ]
    
    # Regular user - get their permissions
    permissions = db.query(UserPermission).filter(
        UserPermission.user_id == current_user.id
    ).all()
    
    return permissions
