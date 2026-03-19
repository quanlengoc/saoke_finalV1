"""
Application Configuration
Load settings from environment variables and config.ini
"""

import os
import configparser
from pathlib import Path
from typing import Optional, Dict, Any
from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # App settings
    APP_NAME: str = "Reconciliation System"
    DEBUG: bool = True
    
    # Database type: sqlite or oracle
    DB_TYPE: str = "sqlite"
    
    # JWT settings
    SECRET_KEY: str = "your-super-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    
    # Mock mode for testing
    MOCK_MODE: bool = True
    
    # CORS Origins
    CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:5173", "*"]
    
    # Base paths
    # BACKEND_DIR = backend folder (for database)
    BACKEND_DIR: Path = Path(__file__).resolve().parent.parent.parent
    # BASE_DIR = reconciliation-system folder (for storage/mock_data)
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent.parent
    
    @property
    def STORAGE_PATH(self) -> str:
        return str(self.BASE_DIR / "storage")
    
    @property
    def UPLOAD_PATH(self) -> str:
        return str(self.BASE_DIR / "storage" / "uploads")
    
    @property
    def OUTPUT_PATH(self) -> str:
        return str(self.BASE_DIR / "storage" / "exports")
    
    @property
    def TEMPLATE_PATH(self) -> str:
        return str(self.BASE_DIR / "storage" / "templates")
    
    class Config:
        env_file = ".env"
        case_sensitive = True


class ConfigIniReader:
    """Read configuration from config.ini file"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config = configparser.ConfigParser()
        if config_path is None:
            config_path = Path(__file__).resolve().parent.parent.parent / "config.ini"
        self.config.read(config_path, encoding='utf-8')
    
    def get_database_config(self, name: str) -> Dict[str, Any]:
        """
        Get database configuration by name
        
        Args:
            name: Database name (e.g., 'app', 'vnptmoney_main')
        
        Returns:
            Dict with database configuration
        """
        section = f"database.{name}"
        if not self.config.has_section(section):
            raise ValueError(f"Database configuration '{name}' not found in config.ini")
        
        return dict(self.config.items(section))
    
    def get_storage_paths(self) -> Dict[str, Path]:
        """Get all storage paths"""
        # parent of backend folder = reconciliation-system
        base_dir = Path(__file__).resolve().parent.parent.parent.parent
        paths = {}
        
        if self.config.has_section('storage'):
            for key, value in self.config.items('storage'):
                # Convert relative paths to absolute
                path = Path(value)
                if not path.is_absolute():
                    path = base_dir / value
                paths[key] = path
        
        return paths
    
    def get_app_config(self) -> Dict[str, Any]:
        """Get application configuration"""
        if self.config.has_section('app'):
            return dict(self.config.items('app'))
        return {}
    
    def list_database_connections(self) -> list:
        """List all available database connection names"""
        connections = []
        for section in self.config.sections():
            if section.startswith('database.'):
                name = section.replace('database.', '')
                connections.append(name)
        return connections


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


@lru_cache()
def get_config_reader() -> ConfigIniReader:
    """Get cached config reader instance"""
    return ConfigIniReader()


# Convenience function to get storage paths
def get_storage_path(name: str) -> Path:
    """
    Get storage path by name
    
    Args:
        name: Path name (uploads, processed, exports, templates, etc.)
    
    Returns:
        Absolute Path object
    """
    config = get_config_reader()
    paths = config.get_storage_paths()
    
    if name not in paths:
        # Default paths if not in config
        base_dir = get_settings().BASE_DIR
        defaults = {
            'uploads': base_dir / 'storage' / 'uploads',
            'processed': base_dir / 'storage' / 'processed',
            'exports': base_dir / 'storage' / 'exports',
            'templates': base_dir / 'storage' / 'templates',
            'sql_templates': base_dir / 'storage' / 'sql_templates',
            'custom_matching': base_dir / 'storage' / 'custom_matching',
        }
        return defaults.get(name, base_dir / 'storage' / name)
    
    return paths[name]
