"""
User and Permission models
"""

from datetime import datetime
from typing import Optional, List

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base


class User(Base):
    """User model for authentication"""
    
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    permissions = relationship("UserPermission", back_populates="user", cascade="all, delete-orphan")
    reconciliations_created = relationship(
        "ReconciliationLog",
        foreign_keys="ReconciliationLog.created_by",
        back_populates="creator"
    )
    reconciliations_approved = relationship(
        "ReconciliationLog",
        foreign_keys="ReconciliationLog.approved_by",
        back_populates="approver"
    )
    
    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}')>"


class UserPermission(Base):
    """User permission for partner/service access"""
    
    __tablename__ = "user_permissions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    partner_code = Column(String(50), nullable=False)
    service_code = Column(String(50), nullable=False)
    can_reconcile = Column(Boolean, default=True)
    can_approve = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Unique constraint
    __table_args__ = (
        UniqueConstraint('user_id', 'partner_code', 'service_code', name='uq_user_partner_service'),
    )
    
    # Relationships
    user = relationship("User", back_populates="permissions")
    
    def __repr__(self):
        return f"<UserPermission(user_id={self.user_id}, partner='{self.partner_code}', service='{self.service_code}')>"
