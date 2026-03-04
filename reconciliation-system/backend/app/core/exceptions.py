"""
Custom exceptions for the application
"""

from typing import Any, Optional, Dict


class ReconciliationException(Exception):
    """Base exception for reconciliation system"""
    
    def __init__(
        self,
        message: str,
        code: str = "RECONCILIATION_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)


class ConfigurationError(ReconciliationException):
    """Raised when there's a configuration error"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "CONFIGURATION_ERROR", details)


class FileProcessingError(ReconciliationException):
    """Raised when file processing fails"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "FILE_PROCESSING_ERROR", details)


class MatchingError(ReconciliationException):
    """Raised when matching process fails"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "MATCHING_ERROR", details)


class DatabaseConnectionError(ReconciliationException):
    """Raised when database connection fails"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "DATABASE_CONNECTION_ERROR", details)


class AuthenticationError(ReconciliationException):
    """Raised when authentication fails"""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, "AUTHENTICATION_ERROR")


class AuthorizationError(ReconciliationException):
    """Raised when user doesn't have permission"""
    
    def __init__(self, message: str = "Permission denied"):
        super().__init__(message, "AUTHORIZATION_ERROR")


class ValidationError(ReconciliationException):
    """Raised when validation fails"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "VALIDATION_ERROR", details)


class WorkflowError(ReconciliationException):
    """Raised when workflow operation is not allowed"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "WORKFLOW_ERROR", details)


class BatchLockedError(WorkflowError):
    """Raised when trying to modify a locked/approved batch"""
    
    def __init__(self, batch_id: str):
        super().__init__(
            f"Batch {batch_id} is locked and cannot be modified",
            {"batch_id": batch_id}
        )


class DuplicateBatchError(WorkflowError):
    """Raised when trying to create a duplicate batch"""
    
    def __init__(self, partner_code: str, service_code: str, period: str):
        super().__init__(
            f"A batch for {partner_code}/{service_code} in period {period} already exists and is approved",
            {
                "partner_code": partner_code,
                "service_code": service_code,
                "period": period
            }
        )
