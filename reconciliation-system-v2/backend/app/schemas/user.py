"""
User schemas for API requests and responses
"""

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, EmailStr, Field


# ============================================================================
# User Schemas
# ============================================================================

class UserBase(BaseModel):
    """Base user schema"""
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=255)


class UserCreate(UserBase):
    """Schema for creating a new user"""
    password: str = Field(..., min_length=6, max_length=100)
    is_admin: bool = False


class UserUpdate(BaseModel):
    """Schema for updating a user"""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    password: Optional[str] = Field(None, min_length=6, max_length=100)
    is_admin: Optional[bool] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    """Schema for user response"""
    id: int
    is_admin: bool
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class UserWithPermissions(UserResponse):
    """User with permissions list"""
    permissions: List["PermissionResponse"] = []
    
    class Config:
        from_attributes = True


# ============================================================================
# Permission Schemas
# ============================================================================

class PermissionBase(BaseModel):
    """Base permission schema"""
    partner_code: str = Field(..., min_length=1, max_length=50)
    service_code: str = Field(..., min_length=1, max_length=50)
    can_reconcile: bool = True
    can_approve: bool = False


class PermissionCreate(PermissionBase):
    """Schema for creating a permission (user_id comes from URL path)"""
    pass


class PermissionUpdate(BaseModel):
    """Schema for updating a permission"""
    can_reconcile: Optional[bool] = None
    can_approve: Optional[bool] = None


class PermissionResponse(PermissionBase):
    """Schema for permission response"""
    id: int
    user_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============================================================================
# Bulk Permission Management
# ============================================================================

class UserPermissionsBulkUpdate(BaseModel):
    """Schema for bulk updating user permissions"""
    permissions: List[PermissionBase]


# Update forward reference
UserWithPermissions.model_rebuild()
