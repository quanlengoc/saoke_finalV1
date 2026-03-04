"""
Reconciliation Log model
Tracks reconciliation batches, steps, and results
"""

from datetime import datetime, date
from typing import Optional

from sqlalchemy import Column, Integer, String, DateTime, Date, Text, ForeignKey, Index
from sqlalchemy.orm import relationship

from app.core.database import Base


class ReconciliationLog(Base):
    """
    Reconciliation batch log
    Tracks the entire reconciliation process from upload to approval
    """
    
    __tablename__ = "reconciliation_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Batch identification
    # Format: PARTNER_SERVICE_YYYYMMDD_HHMMSS
    batch_id = Column(String(100), unique=True, nullable=False, index=True)
    
    # Partner and Service
    partner_code = Column(String(50), nullable=False)
    service_code = Column(String(50), nullable=False)
    
    # Config ID - reference to the config used for this batch
    # Important: Keep track of which config was applied since configs can change over time
    # Note: No ForeignKey constraint to avoid SQLite issues with existing data
    config_id = Column(Integer, nullable=True)
    
    # Reconciliation period
    period_from = Column(Date, nullable=False)
    period_to = Column(Date, nullable=False)
    
    # Status: UPLOADING, PROCESSING, COMPLETED, APPROVED, ERROR
    status = Column(String(20), default='UPLOADING', nullable=False)
    
    # User tracking
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    
    # Step-by-step logs (JSON array)
    # Example: [{"step":"upload_b1","time":"...","status":"ok","message":"..."}]
    step_logs = Column(Text, nullable=True)
    
    # Uploaded files info (JSON)
    # Example: {"b1":["file1.xlsx","file2.xlsx"],"b2":[],"b3":[]}
    files_uploaded = Column(Text, nullable=True)
    
    # Result file paths
    file_result_a1 = Column(String(500), nullable=True)
    file_result_a2 = Column(String(500), nullable=True)
    file_report = Column(String(500), nullable=True)
    
    # Summary statistics (JSON)
    # Example: {"total_b1":1000,"matched":950,"not_found":30,"mismatch":20}
    summary_stats = Column(Text, nullable=True)
    
    # Error information
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Indexes for common queries
    __table_args__ = (
        Index('idx_recon_partner_service', 'partner_code', 'service_code'),
        Index('idx_recon_period', 'period_from', 'period_to'),
        Index('idx_recon_status', 'status'),
    )
    
    # Relationships
    creator = relationship(
        "User",
        foreign_keys=[created_by],
        back_populates="reconciliations_created"
    )
    approver = relationship(
        "User",
        foreign_keys=[approved_by],
        back_populates="reconciliations_approved"
    )
    # Note: config relationship removed to avoid FK constraint issues with SQLite
    # Use config_id directly to query PartnerServiceConfig when needed
    
    def __repr__(self):
        return f"<ReconciliationLog(batch_id='{self.batch_id}', status='{self.status}')>"
    
    @property
    def is_locked(self) -> bool:
        """Check if this batch is locked (approved or pending approval)"""
        return self.status in ['APPROVED', 'PENDING_APPROVAL']
    
    @property
    def is_editable(self) -> bool:
        """Check if this batch can be edited"""
        return self.status in ['UPLOADING', 'PROCESSING', 'COMPLETED', 'ERROR']
    
    @property
    def can_approve(self) -> bool:
        """Check if this batch can be approved"""
        return self.status == 'COMPLETED'
