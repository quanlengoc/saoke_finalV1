"""
Reconciliation System - FastAPI Application
Main entry point
"""

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.database import DatabaseManager
from app.core.logging_config import setup_logging, get_api_logger
from app.api.v1.router import router as api_v1_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup and shutdown events
    """
    # Startup
    settings = get_settings()
    
    # Setup logging first
    setup_logging(debug=settings.DEBUG)
    logger = logging.getLogger(__name__)
    
    # Initialize database
    logger.info(f"Initializing database (DB_TYPE={settings.DB_TYPE})...")
    DatabaseManager.init_app_db()
    
    # Create storage directories
    os.makedirs(settings.STORAGE_PATH, exist_ok=True)
    os.makedirs(settings.UPLOAD_PATH, exist_ok=True)
    os.makedirs(settings.OUTPUT_PATH, exist_ok=True)
    os.makedirs(settings.TEMPLATE_PATH, exist_ok=True)
    os.makedirs(settings.MOCK_DATA_PATH, exist_ok=True)
    
    # Run initial data setup if needed
    if settings.DB_TYPE == "sqlite":
        from app.init_db import init_database
        init_database()
    
    logger.info("Application startup complete!")
    
    yield
    
    # Shutdown
    logger.info("Application shutting down...")


# Create FastAPI application
app = FastAPI(
    title="Transaction Reconciliation System",
    description="""
    Hệ thống đối soát giao dịch giữa ngân hàng (sao kê) và VNPT Money.
    
    ## Features
    - Upload và xử lý file sao kê ngân hàng (B1)
    - Upload file hoàn tiền (B2) và chi tiết đối tác (B3)
    - Query dữ liệu giao dịch từ VNPT Money (B4)
    - Đối soát tự động với luật cấu hình được
    - Xuất báo cáo theo template Excel
    - Quy trình phê duyệt
    """,
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# API Request Logging Middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all API requests"""
    import time
    api_logger = get_api_logger()
    
    start_time = time.time()
    
    # Log request
    api_logger.info(f"REQUEST | {request.method} {request.url.path} | Client: {request.client.host if request.client else 'unknown'}")
    
    try:
        response = await call_next(request)
        
        # Log response
        process_time = (time.time() - start_time) * 1000
        api_logger.info(f"RESPONSE | {request.method} {request.url.path} | Status: {response.status_code} | Time: {process_time:.2f}ms")
        
        return response
    except Exception as e:
        process_time = (time.time() - start_time) * 1000
        api_logger.error(f"ERROR | {request.method} {request.url.path} | Error: {str(e)} | Time: {process_time:.2f}ms")
        raise


# Include API router
app.include_router(api_v1_router, prefix="/api/v1")


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "db_type": settings.DB_TYPE,
        "mock_mode": settings.MOCK_MODE
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint - redirect to docs"""
    return {
        "message": "Transaction Reconciliation System API",
        "docs": "/docs",
        "version": "1.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
