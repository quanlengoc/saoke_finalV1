"""
Step Log File Manager

Handles reading/writing step logs to JSON files instead of DB.
This eliminates DB lock contention during workflow execution.

Log file structure:
    logs/batches/{batch_id}/run_{run_number}.json
    
Content: JSON array of step log entries
    [{"step": "load_B4", "time": "...", "status": "ok", "message": "...", "data_preview": {...}}, ...]
"""

import json
import os
import logging
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Base directory for log files (backend/logs/batches/)
_LOGS_BASE: Optional[Path] = None


def _get_logs_base() -> Path:
    """Get the base directory for batch log files."""
    global _LOGS_BASE
    if _LOGS_BASE is None:
        _LOGS_BASE = Path(__file__).resolve().parent.parent.parent / "logs" / "batches"
    return _LOGS_BASE


def _get_backend_dir() -> Path:
    """Get the backend directory root."""
    return Path(__file__).resolve().parent.parent.parent


def get_log_file_path(batch_id: str, run_number: int) -> str:
    """
    Get the relative file path for a run's log file.
    Returns path relative to backend dir, e.g. "logs/batches/{batch_id}/run_1.json"
    """
    return f"logs/batches/{batch_id}/run_{run_number}.json"


def get_log_file_abs_path(batch_id: str, run_number: int) -> Path:
    """Get absolute path for a run's log file."""
    return _get_logs_base() / batch_id / f"run_{run_number}.json"


def write_step_logs(batch_id: str, run_number: int, step_logs: List[Dict]) -> str:
    """
    Write step logs to a JSON file. Creates directories as needed.
    
    Returns the relative file path (for storing in DB).
    """
    abs_path = get_log_file_abs_path(batch_id, run_number)
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        abs_path.write_text(
            json.dumps(step_logs, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception as e:
        logger.error(f"Failed to write step logs to {abs_path}: {e}")
    
    return get_log_file_path(batch_id, run_number)


def append_step_log(batch_id: str, run_number: int, log_entry: Dict) -> None:
    """
    Append a single step log entry to the file.
    Reads existing logs, appends, and writes back.
    """
    abs_path = get_log_file_abs_path(batch_id, run_number)
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    
    logs = read_step_logs_from_file(abs_path)
    logs.append(log_entry)
    
    try:
        abs_path.write_text(
            json.dumps(logs, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception as e:
        logger.error(f"Failed to append step log to {abs_path}: {e}")


def append_step_log_to_batch(batch, log_entry: Dict, db=None) -> None:
    """
    Append a step log entry to the latest log file for a batch.
    
    Determines the correct log file from:
    1. batch.step_logs (if it contains a file path)
    2. Latest BatchRunHistory record
    3. Falls back to run_1
    
    Args:
        batch: ReconciliationLog ORM object
        log_entry: Dict with step log data
        db: Optional SQLAlchemy session (needed for BatchRunHistory query)
    """
    log_path = None
    
    # Try from batch.step_logs (should be a file path like "logs/batches/.../run_N.json")
    if batch.step_logs:
        stripped = batch.step_logs.strip()
        if not stripped.startswith("[") and stripped:  # Not legacy JSON
            log_path = stripped
    
    # Try from BatchRunHistory
    if not log_path and db:
        try:
            from app.models import BatchRunHistory
            latest = db.query(BatchRunHistory).filter(
                BatchRunHistory.batch_id == batch.batch_id
            ).order_by(BatchRunHistory.run_number.desc()).first()
            if latest and latest.log_file_path:
                log_path = latest.log_file_path
        except Exception:
            pass
    
    # Fallback: use run_1
    if not log_path:
        log_path = get_log_file_path(batch.batch_id, 1)
    
    # Resolve and append
    p = Path(log_path)
    if not p.is_absolute():
        p = _get_backend_dir() / log_path
    p.parent.mkdir(parents=True, exist_ok=True)
    
    logs = read_step_logs_from_file(p)
    logs.append(log_entry)
    
    try:
        p.write_text(
            json.dumps(logs, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception as e:
        logger.error(f"Failed to append step log to {p}: {e}")


def read_step_logs(batch_id: str, run_number: int) -> List[Dict]:
    """Read step logs from file by batch_id + run_number."""
    abs_path = get_log_file_abs_path(batch_id, run_number)
    return read_step_logs_from_file(abs_path)


def read_step_logs_from_path(rel_or_abs_path: str) -> List[Dict]:
    """
    Read step logs from a file path.
    Accepts either:
    - Relative path from backend dir (e.g. "logs/batches/.../run_1.json")
    - Absolute path
    - Legacy: JSON array string (returns parsed JSON directly)
    """
    if not rel_or_abs_path:
        return []
    
    # If it looks like a JSON array, parse directly (legacy data in DB)
    stripped = rel_or_abs_path.strip()
    if stripped.startswith("["):
        try:
            return json.loads(stripped)
        except (json.JSONDecodeError, TypeError):
            return []
    
    # Try as absolute path first
    p = Path(rel_or_abs_path)
    if p.is_absolute() and p.exists():
        return read_step_logs_from_file(p)
    
    # Try as relative path from backend dir
    abs_path = _get_backend_dir() / rel_or_abs_path
    return read_step_logs_from_file(abs_path)


def read_step_logs_from_file(file_path: Path) -> List[Dict]:
    """Read and parse a step log JSON file."""
    if not file_path or not file_path.exists():
        return []
    try:
        text = file_path.read_text(encoding="utf-8")
        data = json.loads(text)
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.warning(f"Failed to read step logs from {file_path}: {e}")
        return []


def make_on_step_log_callback(batch_id: str, run_number: int):
    """
    Create an on_step_log callback that writes to file.
    
    This replaces the old callback that did DB UPDATE on every step.
    Now it simply writes the full step_logs array to a JSON file.
    No DB interaction = no lock contention.
    
    Usage:
        callback = make_on_step_log_callback(batch_id, run_number)
        executor = WorkflowExecutor(..., on_step_log=callback)
    """
    def on_step_log(step_logs: List[Dict]):
        write_step_logs(batch_id, run_number, step_logs)
    
    return on_step_log
