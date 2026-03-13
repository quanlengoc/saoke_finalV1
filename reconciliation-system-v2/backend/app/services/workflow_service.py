"""
Workflow service for managing reconciliation status and approvals
"""

import json
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session

from app.models import ReconciliationLog, PartnerServiceConfig
from app.core.exceptions import WorkflowError, BatchLockedError, DuplicateBatchError


class WorkflowService:
    """
    Manages reconciliation workflow:
    - Status transitions: UPLOADING -> PROCESSING -> COMPLETED -> APPROVED
    - Approval/rejection
    - Locking after approval
    - Reset for re-reconciliation
    """
    
    # Valid status transitions
    # Flow: UPLOADING → PROCESSING → COMPLETED/ERROR/CANCELLED → PENDING_APPROVAL → APPROVED
    # Reject: PENDING_APPROVAL → COMPLETED (back to completed, user can rerun or resubmit)
    VALID_TRANSITIONS = {
        'UPLOADING': ['PROCESSING'],
        'PROCESSING': ['COMPLETED', 'ERROR', 'CANCELLED'],
        'COMPLETED': ['PROCESSING', 'PENDING_APPROVAL'],       # rerun or submit for approval
        'ERROR': ['PROCESSING', 'UPLOADING'],                   # rerun or re-upload
        'CANCELLED': ['PROCESSING', 'UPLOADING'],               # rerun or re-upload
        'PENDING_APPROVAL': ['APPROVED', 'COMPLETED'],          # approve or reject (→COMPLETED)
        'APPROVED': [],                                          # final state
    }
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_batch(
        self,
        batch_id: str,
        partner_code: str,
        service_code: str,
        period_from,
        period_to,
        created_by: int,
        config_id: int = None
    ) -> ReconciliationLog:
        """
        Create a new reconciliation batch
        
        Args:
            batch_id: Unique batch identifier
            partner_code: Partner code
            service_code: Service code
            period_from: Period start date
            period_to: Period end date
            created_by: User ID who created the batch
            config_id: ID of the config applied to this batch
        
        Returns:
            Created ReconciliationLog
        
        Raises:
            DuplicateBatchError: If approved batch exists for same period
        """
        # Check for existing approved batch
        existing = self.db.query(ReconciliationLog).filter(
            ReconciliationLog.partner_code == partner_code,
            ReconciliationLog.service_code == service_code,
            ReconciliationLog.period_from == period_from,
            ReconciliationLog.period_to == period_to,
            ReconciliationLog.status == 'APPROVED'
        ).first()
        
        if existing:
            raise DuplicateBatchError(partner_code, service_code, f"{period_from} - {period_to}")
        
        # Delete any non-approved batches for same period (reset)
        self.db.query(ReconciliationLog).filter(
            ReconciliationLog.partner_code == partner_code,
            ReconciliationLog.service_code == service_code,
            ReconciliationLog.period_from == period_from,
            ReconciliationLog.period_to == period_to,
            ReconciliationLog.status != 'APPROVED'
        ).delete()
        
        # Create new batch
        batch = ReconciliationLog(
            batch_id=batch_id,
            partner_code=partner_code,
            service_code=service_code,
            config_id=config_id,
            period_from=period_from,
            period_to=period_to,
            status='UPLOADING',
            created_by=created_by,
            step_logs=json.dumps([]),
            files_uploaded=json.dumps({"b1": [], "b2": [], "b3": []})
        )
        
        self.db.add(batch)
        self.db.commit()
        self.db.refresh(batch)
        
        return batch
    
    def get_batch(self, batch_id: str) -> Optional[ReconciliationLog]:
        """Get batch by ID"""
        return self.db.query(ReconciliationLog).filter(
            ReconciliationLog.batch_id == batch_id
        ).first()
    
    def update_status(
        self,
        batch_id: str,
        new_status: str,
        error_message: Optional[str] = None
    ) -> ReconciliationLog:
        """
        Update batch status
        
        Args:
            batch_id: Batch ID
            new_status: New status
            error_message: Error message if status is ERROR
        
        Returns:
            Updated ReconciliationLog
        
        Raises:
            WorkflowError: If transition is not valid
        """
        batch = self.get_batch(batch_id)
        if not batch:
            raise WorkflowError(f"Batch not found: {batch_id}")
        
        # Check valid transition
        valid_next = self.VALID_TRANSITIONS.get(batch.status, [])
        if new_status not in valid_next:
            raise WorkflowError(
                f"Invalid status transition: {batch.status} -> {new_status}",
                {"current_status": batch.status, "requested_status": new_status}
            )
        
        batch.status = new_status
        batch.updated_at = datetime.utcnow()
        
        if error_message:
            batch.error_message = error_message
        
        self.db.commit()
        self.db.refresh(batch)
        
        return batch
    
    def add_step_log(
        self,
        batch_id: str,
        step: str,
        status: str,
        message: str
    ):
        """Add a step log entry to batch"""
        batch = self.get_batch(batch_id)
        if not batch:
            return
        
        step_logs = json.loads(batch.step_logs or '[]')
        step_logs.append({
            "step": step,
            "time": datetime.now().isoformat(),
            "status": status,
            "message": message
        })
        batch.step_logs = json.dumps(step_logs)
        
        self.db.commit()
    
    def update_files_uploaded(
        self,
        batch_id: str,
        file_type: str,
        filenames: List[str]
    ):
        """Update the list of uploaded files for a batch"""
        batch = self.get_batch(batch_id)
        if not batch:
            return
        
        files_uploaded = json.loads(batch.files_uploaded or '{"b1":[],"b2":[],"b3":[]}')
        files_uploaded[file_type.lower()] = filenames
        batch.files_uploaded = json.dumps(files_uploaded)
        
        self.db.commit()
    
    def update_results(
        self,
        batch_id: str,
        file_result_a1: Optional[str] = None,
        file_result_a2: Optional[str] = None,
        file_report: Optional[str] = None,
        summary_stats: Optional[Dict[str, Any]] = None
    ):
        """Update result files and statistics"""
        batch = self.get_batch(batch_id)
        if not batch:
            return
        
        if file_result_a1:
            batch.file_result_a1 = file_result_a1
        if file_result_a2:
            batch.file_result_a2 = file_result_a2
        if file_report:
            batch.file_report = file_report
        if summary_stats:
            batch.summary_stats = json.dumps(summary_stats)
        
        batch.updated_at = datetime.utcnow()
        self.db.commit()
    
    def lock_batch(
        self,
        batch_id: str,
        user_id: int
    ) -> ReconciliationLog:
        """
        Lock a batch (submit for approval) by changing status to PENDING_APPROVAL

        Args:
            batch_id: Batch ID (can be int id or string batch_id)
            user_id: User ID who submitted

        Returns:
            Locked batch

        Raises:
            WorkflowError: If batch not found or already locked
        """
        batch = self.db.query(ReconciliationLog).filter(
            ReconciliationLog.id == batch_id
        ).first() if isinstance(batch_id, int) else self.get_batch(batch_id)

        if not batch:
            raise WorkflowError(f"Batch not found: {batch_id}")

        if batch.status not in ('COMPLETED',):
            raise WorkflowError(f"Can only lock COMPLETED batches, current: {batch.status}")

        batch.status = 'PENDING_APPROVAL'
        batch.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(batch)

        return batch

    def unlock_batch(
        self,
        batch_id: str,
        user_id: int
    ) -> ReconciliationLog:
        """
        Unlock a batch (allow rerun/edit) by reverting status to COMPLETED

        Args:
            batch_id: Batch ID (can be int id or string batch_id)
            user_id: User ID who unlocked

        Returns:
            Unlocked batch
        """
        batch = self.db.query(ReconciliationLog).filter(
            ReconciliationLog.id == batch_id
        ).first() if isinstance(batch_id, int) else self.get_batch(batch_id)

        if not batch:
            raise WorkflowError(f"Batch not found: {batch_id}")

        batch.status = 'COMPLETED'
        batch.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(batch)

        return batch

    def reject_batch(
        self,
        batch_id: str,
        user_id: int,
        reason: Optional[str] = None
    ) -> ReconciliationLog:
        """
        Reject a batch — returns it to COMPLETED so user can rerun or resubmit.

        Args:
            batch_id: Batch ID (can be int id or string batch_id)
            user_id: User ID who rejected
            reason: Rejection reason

        Returns:
            Batch with COMPLETED status
        """
        batch = self.db.query(ReconciliationLog).filter(
            ReconciliationLog.id == batch_id
        ).first() if isinstance(batch_id, int) else self.get_batch(batch_id)

        if not batch:
            raise WorkflowError(f"Batch not found: {batch_id}")

        if batch.status != 'PENDING_APPROVAL':
            raise WorkflowError(f"Can only reject PENDING_APPROVAL batches, current: {batch.status}")

        batch.status = 'COMPLETED'
        batch.error_message = reason
        batch.approved_by = None
        batch.approved_at = None
        batch.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(batch)

        return batch

    def approve_batch(
        self,
        batch_id: str,
        approved_by: int = None,
        user_id: int = None,
        notes: Optional[str] = None
    ) -> ReconciliationLog:
        """
        Approve a completed batch
        
        Args:
            batch_id: Batch ID
            approved_by: User ID who approved
        
        Returns:
            Approved batch
        
        Raises:
            WorkflowError: If batch cannot be approved
        """
        batch = self.db.query(ReconciliationLog).filter(
            ReconciliationLog.id == batch_id
        ).first() if isinstance(batch_id, int) else self.get_batch(batch_id)

        if not batch:
            raise WorkflowError(f"Batch not found: {batch_id}")

        if batch.status != 'PENDING_APPROVAL':
            raise WorkflowError(
                f"Can only approve PENDING_APPROVAL batches, current status: {batch.status}"
            )

        # Support both parameter names
        approver_id = approved_by or user_id

        batch.status = 'APPROVED'
        batch.approved_by = approver_id
        batch.approved_at = datetime.utcnow()
        batch.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(batch)
        
        return batch
    
    def reset_batch(
        self,
        batch_id: str,
        user_id: int,
        is_admin: bool = False
    ) -> ReconciliationLog:
        """
        Reset a batch for re-reconciliation
        
        Args:
            batch_id: Batch ID
            user_id: User requesting reset
            is_admin: Whether user is admin
        
        Returns:
            Reset batch
        
        Raises:
            WorkflowError: If batch cannot be reset
            BatchLockedError: If trying to reset approved batch without admin rights
        """
        batch = self.get_batch(batch_id)
        if not batch:
            raise WorkflowError(f"Batch not found: {batch_id}")
        
        if batch.status == 'APPROVED' and not is_admin:
            raise BatchLockedError(batch_id)
        
        # Reset batch
        batch.status = 'UPLOADING'
        batch.step_logs = json.dumps([])
        batch.summary_stats = None
        batch.error_message = None
        batch.approved_by = None
        batch.approved_at = None
        batch.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(batch)
        
        return batch
    
    def get_batch_history(
        self,
        partner_code: Optional[str] = None,
        service_code: Optional[str] = None,
        status: Optional[str] = None,
        user_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 20
    ) -> tuple:
        """
        Get reconciliation batch history with filters
        
        Returns:
            Tuple of (items, total_count)
        """
        query = self.db.query(ReconciliationLog)
        
        if partner_code:
            query = query.filter(ReconciliationLog.partner_code == partner_code)
        if service_code:
            query = query.filter(ReconciliationLog.service_code == service_code)
        if status:
            query = query.filter(ReconciliationLog.status == status)
        if user_id:
            query = query.filter(ReconciliationLog.created_by == user_id)
        
        # Get total count
        total = query.count()
        
        # Get paginated items
        items = query.order_by(ReconciliationLog.created_at.desc())\
            .offset((page - 1) * page_size)\
            .limit(page_size)\
            .all()
        
        return items, total
