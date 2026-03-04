"""
Logging Configuration
Centralized logging for the reconciliation system

Log files location: backend/logs/
- app.log: General application logs (rotated daily, keep 30 days)
- error.log: Error logs only (rotated daily, keep 90 days)
- reconciliation.log: Reconciliation process logs (rotated daily, keep 30 days)
- api.log: API request/response logs (rotated daily, keep 7 days)
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from datetime import datetime


# Log directory
LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"


def setup_logging(debug: bool = False):
    """
    Setup logging configuration for the entire application
    
    Args:
        debug: Enable debug level logging
    """
    # Create logs directory
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    # Log format
    detailed_format = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_format = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if debug else logging.INFO)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # ===== Console Handler =====
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if debug else logging.INFO)
    console_handler.setFormatter(simple_format)
    root_logger.addHandler(console_handler)
    
    # ===== Main App Log (app.log) =====
    # Rotates daily, keeps 30 days
    app_handler = TimedRotatingFileHandler(
        filename=LOG_DIR / "app.log",
        when='midnight',
        interval=1,
        backupCount=30,
        encoding='utf-8'
    )
    app_handler.setLevel(logging.INFO)
    app_handler.setFormatter(detailed_format)
    app_handler.suffix = "%Y-%m-%d"
    root_logger.addHandler(app_handler)
    
    # ===== Error Log (error.log) =====
    # Only ERROR and above, keeps 90 days
    error_handler = TimedRotatingFileHandler(
        filename=LOG_DIR / "error.log",
        when='midnight',
        interval=1,
        backupCount=90,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_format)
    error_handler.suffix = "%Y-%m-%d"
    root_logger.addHandler(error_handler)
    
    # ===== Reconciliation Log =====
    recon_logger = logging.getLogger('reconciliation')
    recon_handler = TimedRotatingFileHandler(
        filename=LOG_DIR / "reconciliation.log",
        when='midnight',
        interval=1,
        backupCount=30,
        encoding='utf-8'
    )
    recon_handler.setLevel(logging.DEBUG)
    recon_handler.setFormatter(detailed_format)
    recon_handler.suffix = "%Y-%m-%d"
    recon_logger.addHandler(recon_handler)
    
    # ===== API Request Log =====
    api_logger = logging.getLogger('api')
    api_handler = TimedRotatingFileHandler(
        filename=LOG_DIR / "api.log",
        when='midnight',
        interval=1,
        backupCount=7,
        encoding='utf-8'
    )
    api_handler.setLevel(logging.INFO)
    api_handler.setFormatter(detailed_format)
    api_handler.suffix = "%Y-%m-%d"
    api_logger.addHandler(api_handler)
    
    # ===== Report Generation Log =====
    report_logger = logging.getLogger('report')
    report_handler = TimedRotatingFileHandler(
        filename=LOG_DIR / "report.log",
        when='midnight',
        interval=1,
        backupCount=30,
        encoding='utf-8'
    )
    report_handler.setLevel(logging.DEBUG)
    report_handler.setFormatter(detailed_format)
    report_handler.suffix = "%Y-%m-%d"
    report_logger.addHandler(report_handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger('uvicorn').setLevel(logging.WARNING)
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    
    # Log startup
    root_logger.info("=" * 60)
    root_logger.info(f"Application started at {datetime.now().isoformat()}")
    root_logger.info(f"Log directory: {LOG_DIR}")
    root_logger.info(f"Debug mode: {debug}")
    root_logger.info("=" * 60)
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger by name
    
    Common logger names:
    - 'reconciliation': For reconciliation process
    - 'api': For API requests
    - 'report': For report generation
    - 'app.services.xxx': For specific services
    
    Args:
        name: Logger name
    
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


# Convenience loggers
def get_reconciliation_logger():
    """Get logger for reconciliation process"""
    return logging.getLogger('reconciliation')


def get_api_logger():
    """Get logger for API requests"""
    return logging.getLogger('api')


def get_report_logger():
    """Get logger for report generation"""
    return logging.getLogger('report')
