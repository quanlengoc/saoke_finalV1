"""
Reconciliation Log model
Tracks reconciliation batches, steps, and results

Design (V2.1):
- step_logs: stores FILE PATH to JSON log (not the JSON itself)
- files_uploaded: compact JSON {batch_folder, sources: {name: {folder, file_count}}}
- batch_run_history: separate table for each run attempt (initial + reruns)
"""

import json as _json
from datetime import datetime, date
from typing import Optional

from sqlalchemy import Column, Integer, String, DateTime, Date, Text, Float, ForeignKey, Index
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
    config_id = Column(Integer, nullable=True)
    
    # Reconciliation period
    period_from = Column(Date, nullable=False)
    period_to = Column(Date, nullable=False)
    
    # Status: UPLOADING, PROCESSING, COMPLETED, APPROVED, ERROR, FAILED
    status = Column(String(20), default='UPLOADING', nullable=False)
    
    # User tracking
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    
    # Step logs: FILE PATH to JSON log file (NOT the JSON array itself)
    # Example: "logs/batches/SACOMBANK_TOPUP_20260303_cd063ee4/run_2.json"
    # The file contains the full step-by-step log array.
    # For backward compat, may also contain a JSON array string (legacy data).
    step_logs = Column(Text, nullable=True)
    
    # Upload info (JSON) — compact format
    # NEW format: {"batch_folder": "...", "sources": {"B1": {"folder": "b1", "file_count": 3}}}
    # OLD format (legacy): {"B1": ["/full/path/file1.xlsx", ...]}
    # Both formats are supported when reading.
    files_uploaded = Column(Text, nullable=True)
    
    # Result file paths
    file_result_a1 = Column(String(500), nullable=True)
    file_result_a2 = Column(String(500), nullable=True)
    file_report = Column(String(500), nullable=True)
    
    # Dynamic result file paths (JSON dict: {output_name: file_path, ...})
    file_results = Column(Text, nullable=True)
    
    # Summary statistics (JSON) — latest run's summary
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
    run_history = relationship(
        "BatchRunHistory",
        back_populates="batch",
        order_by="BatchRunHistory.run_number",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self):
        return f"<ReconciliationLog(batch_id='{self.batch_id}', status='{self.status}')>"
    
    @property
    def is_locked(self) -> bool:
        """Check if this batch is locked (approved or pending approval)"""
        return self.status in ['APPROVED', 'PENDING_APPROVAL']
    
    @property
    def file_results_dict(self) -> dict:
        """Parse file_results JSON to dict"""
        if self.file_results:
            try:
                return _json.loads(self.file_results)
            except (_json.JSONDecodeError, TypeError):
                pass
        return {}
    
    def get_file_path(self, output_name: str) -> str:
        """Get file path for any output by name."""
        results = self.file_results_dict
        if output_name.upper() in results:
            return results[output_name.upper()]
        legacy_map = {
            'A1': self.file_result_a1,
            'A2': self.file_result_a2,
            'REPORT': self.file_report,
        }
        return legacy_map.get(output_name.upper())
    
    @property
    def is_editable(self) -> bool:
        """Check if this batch can be edited"""
        return self.status in ['UPLOADING', 'PROCESSING', 'COMPLETED', 'ERROR', 'FAILED']
    
    @property
    def can_approve(self) -> bool:
        """Check if this batch can be approved"""
        return self.status == 'COMPLETED'
    
    @property
    def upload_info_dict(self) -> dict:
        """Parse files_uploaded JSON. Supports both old & new format."""
        if not self.files_uploaded:
            return {}
        try:
            return _json.loads(self.files_uploaded)
        except (_json.JSONDecodeError, TypeError):
            return {}
    
    def get_upload_folder(self, partner_code: str = None) -> str:
        """Get the batch upload folder path from upload_info (new format)."""
        info = self.upload_info_dict
        return info.get('batch_folder', '')


class BatchRunHistory(Base):
    """
    History of each workflow execution attempt for a batch.
    
    Each time /run or /rerun is called, a new row is inserted here.
    The detailed step-by-step log is stored in a file (log_file_path),
    NOT in the database, to avoid DB bloat and lock contention.
    """
    
    __tablename__ = "batch_run_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Link to parent batch
    batch_id = Column(String(100), ForeignKey("reconciliation_logs.batch_id"), nullable=False, index=True)
    
    # Sequential run number (1, 2, 3 ...)
    run_number = Column(Integer, nullable=False)
    
    # How was this run triggered?
    triggered_by = Column(String(20), nullable=False, default='initial')  # 'initial' | 'rerun'
    
    # Status: PROCESSING, COMPLETED, FAILED
    status = Column(String(20), default='PROCESSING', nullable=False)
    
    # Timing
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    
    # File path to detailed step log JSON
    # Example: "logs/batches/SACOMBANK_TOPUP_20260303_cd063ee4/run_1.json"
    log_file_path = Column(String(500), nullable=True)
    
    # Compact summary (JSON) — row counts, match stats
    summary_stats = Column(Text, nullable=True)
    
    # Output file paths (JSON dict: {output_name: file_path})
    file_results = Column(Text, nullable=True)
    
    # Error message (if FAILED)
    error_message = Column(Text, nullable=True)
    
    # Relationship
    batch = relationship("ReconciliationLog", back_populates="run_history")
    
    __table_args__ = (
        Index('idx_run_history_batch', 'batch_id', 'run_number'),
    )
    
    def __repr__(self):
        return f"<BatchRunHistory(batch_id='{self.batch_id}', run={self.run_number}, status='{self.status}')>"
    
    @property
    def summary_stats_dict(self) -> dict:
        if self.summary_stats:
            try:
                return _json.loads(self.summary_stats)
            except:
                pass
        return {}
    
    @property
    def file_results_dict(self) -> dict:
        if self.file_results:
            try:
                return _json.loads(self.file_results)
            except:
                pass
        return {}
