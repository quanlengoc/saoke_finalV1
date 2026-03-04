"""
User management endpoints (Admin only)
"""

from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_admin
from app.core.security import get_password_hash
from app.models import User, UserPermission
from app.schemas.user import (
    UserCreate, UserUpdate, UserResponse, UserWithPermissions,
    PermissionCreate, PermissionResponse, UserPermissionsBulkUpdate
)


router = APIRouter()


@router.get("/", response_model=List[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin)
) -> Any:
    """
    List all users (Admin only)
    """
    users = db.query(User).offset(skip).limit(limit).all()
    return users


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin)
) -> Any:
    """
    Create a new user (Admin only)
    """
    # Check if email exists
    existing = db.query(User).filter(User.email == request.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    user = User(
        email=request.email,
        password_hash=get_password_hash(request.password),
        full_name=request.full_name,
        is_admin=request.is_admin,
        is_active=True
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return user


@router.get("/{user_id}", response_model=UserWithPermissions)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin)
) -> Any:
    """
    Get user details with permissions (Admin only)
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    request: UserUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin)
) -> Any:
    """
    Update user (Admin only)
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update fields
    if request.email is not None:
        # Check if email is taken by another user
        existing = db.query(User).filter(
            User.email == request.email,
            User.id != user_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        user.email = request.email
    
    if request.full_name is not None:
        user.full_name = request.full_name
    
    if request.password is not None:
        user.password_hash = get_password_hash(request.password)
    
    if request.is_admin is not None:
        user.is_admin = request.is_admin
    
    if request.is_active is not None:
        user.is_active = request.is_active
    
    db.commit()
    db.refresh(user)
    
    return user


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
) -> Any:
    """
    Delete user (Admin only)
    """
    if user_id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete yourself"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    db.delete(user)
    db.commit()
    
    return {"message": "User deleted successfully"}


# ============================================================================
# Permission Management
# ============================================================================

@router.post("/{user_id}/permissions", response_model=PermissionResponse)
async def add_permission(
    user_id: int,
    request: PermissionCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin)
) -> Any:
    """
    Add permission for a user (Admin only)
    """
    # Check user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if permission already exists
    existing = db.query(UserPermission).filter(
        UserPermission.user_id == user_id,
        UserPermission.partner_code == request.partner_code,
        UserPermission.service_code == request.service_code
    ).first()
    
    if existing:
        # Update existing permission
        existing.can_reconcile = request.can_reconcile
        existing.can_approve = request.can_approve
        db.commit()
        db.refresh(existing)
        return existing
    
    # Create new permission
    permission = UserPermission(
        user_id=user_id,
        partner_code=request.partner_code,
        service_code=request.service_code,
        can_reconcile=request.can_reconcile,
        can_approve=request.can_approve
    )
    
    db.add(permission)
    db.commit()
    db.refresh(permission)
    
    return permission


@router.delete("/{user_id}/permissions/{permission_id}")
async def remove_permission(
    user_id: int,
    permission_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin)
) -> Any:
    """
    Remove a permission (Admin only)
    """
    permission = db.query(UserPermission).filter(
        UserPermission.id == permission_id,
        UserPermission.user_id == user_id
    ).first()
    
    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permission not found"
        )
    
    db.delete(permission)
    db.commit()
    
    return {"message": "Permission removed successfully"}


@router.put("/{user_id}/permissions/bulk", response_model=List[PermissionResponse])
async def bulk_update_permissions(
    user_id: int,
    request: UserPermissionsBulkUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin)
) -> Any:
    """
    Bulk update user permissions - replace all permissions (Admin only)
    """
    # Check user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Delete existing permissions
    db.query(UserPermission).filter(UserPermission.user_id == user_id).delete()
    
    # Add new permissions
    new_permissions = []
    for perm in request.permissions:
        permission = UserPermission(
            user_id=user_id,
            partner_code=perm.partner_code,
            service_code=perm.service_code,
            can_reconcile=perm.can_reconcile,
            can_approve=perm.can_approve
        )
        db.add(permission)
        new_permissions.append(permission)
    
    db.commit()
    
    for p in new_permissions:
        db.refresh(p)
    
    return new_permissions
