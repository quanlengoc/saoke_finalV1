"""
AuditLog model — append-only audit trail for all user actions.
"""

import json as _json
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Index

from app.core.database import Base


class AuditLog(Base):
    """
    Audit trail — append-only, never update or delete.
    Tracks: approve/reject/submit batch, CRUD user, permission changes, config changes, login/logout.
    """

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Who
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user_email = Column(String(255), nullable=False)  # denormalized for fast query

    # What
    action = Column(String(50), nullable=False)  # SUBMIT, APPROVE, REJECT, CREATE, UPDATE, DELETE, LOGIN, LOGOUT

    # Target
    entity_type = Column(String(50), nullable=False)  # BATCH, USER, CONFIG, PERMISSION
    entity_id = Column(String(255), nullable=False)    # batch_id, user id, config id, etc.

    # Before / After (JSON, nullable)
    old_values = Column(Text, nullable=True)
    new_values = Column(Text, nullable=True)

    # Human-readable summary
    summary = Column(String(500), nullable=True)

    # Client info
    ip_address = Column(String(50), nullable=True)

    __table_args__ = (
        Index('idx_audit_entity', 'entity_type', 'entity_id'),
        Index('idx_audit_user', 'user_id'),
        Index('idx_audit_timestamp', 'timestamp'),
    )

    def __init__(self, **kwargs):
        # Auto-serialize dict values to JSON strings
        if 'old_values' in kwargs and isinstance(kwargs['old_values'], dict):
            kwargs['old_values'] = _json.dumps(kwargs['old_values'], ensure_ascii=False)
        if 'new_values' in kwargs and isinstance(kwargs['new_values'], dict):
            kwargs['new_values'] = _json.dumps(kwargs['new_values'], ensure_ascii=False)
        super().__init__(**kwargs)

    @property
    def old_values_dict(self) -> dict:
        if self.old_values:
            try:
                return _json.loads(self.old_values)
            except (_json.JSONDecodeError, TypeError):
                pass
        return {}

    @property
    def new_values_dict(self) -> dict:
        if self.new_values:
            try:
                return _json.loads(self.new_values)
            except (_json.JSONDecodeError, TypeError):
                pass
        return {}

    def __repr__(self):
        return f"<AuditLog({self.action} {self.entity_type}:{self.entity_id} by {self.user_email})>"
