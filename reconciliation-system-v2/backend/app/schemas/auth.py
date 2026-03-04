"""
Authentication schemas
"""

from typing import Optional

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    """Schema for login request"""
    email: EmailStr
    password: str


class Token(BaseModel):
    """Schema for JWT token response"""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Schema for token payload data"""
    user_id: Optional[int] = None
    email: Optional[str] = None


class PasswordChange(BaseModel):
    """Schema for password change request"""
    current_password: str
    new_password: str
