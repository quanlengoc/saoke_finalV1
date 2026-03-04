"""
Data Loader Factory - Create appropriate loader based on source type
"""

from typing import Dict, Any
from pathlib import Path

from app.services.data_loaders.base_loader import BaseDataLoader
from app.services.data_loaders.file_loader import FileDataLoader
from app.services.data_loaders.database_loader import DatabaseDataLoader
from app.models.data_source import DataSourceConfig
from app.core.logging_config import get_data_loader_logger


class DataLoaderFactory:
    """
    Factory for creating appropriate data loader based on source type
    
    Usage:
        factory = DataLoaderFactory(config_ini_path, storage_base_path)
        loader = factory.create_loader(data_source_config, file_path, batch_id)
        result = loader.load()
    """
    
    def __init__(self, config_ini_path: str, storage_base_path: str):
        """
        Initialize factory
        
        Args:
            config_ini_path: Path to config.ini
            storage_base_path: Base path for storage
        """
        self.config_ini_path = Path(config_ini_path)
        self.storage_base_path = Path(storage_base_path)
        self.logger = get_data_loader_logger()
    
    def create_loader(
        self,
        data_source: DataSourceConfig,
        file_path: str = None,
        cycle_params: Dict[str, Any] = None,
        batch_id: str = None
    ) -> BaseDataLoader:
        """
        Create appropriate loader for data source
        
        Args:
            data_source: DataSourceConfig model instance
            file_path: Path to uploaded file (for FILE_UPLOAD type)
            cycle_params: Cycle parameters for database queries
            batch_id: Batch ID for logging correlation
        
        Returns:
            Appropriate DataLoader instance
        
        Raises:
            ValueError: If source type is not supported
        """
        source_type = data_source.source_type
        source_name = data_source.source_name
        
        self.logger.info(f"[{batch_id or 'NO_BATCH'}] Creating loader for {source_name} (type={source_type})")
        
        if source_type == "FILE_UPLOAD":
            if not file_path:
                raise ValueError(f"file_path required for FILE_UPLOAD source: {source_name}")
            
            return FileDataLoader(
                source_name=source_name,
                config=data_source.file_config_dict,
                file_path=file_path,
                batch_id=batch_id
            )
        
        elif source_type == "DATABASE":
            return DatabaseDataLoader(
                source_name=source_name,
                config=data_source.db_config_dict,
                config_ini_path=str(self.config_ini_path),
                storage_base_path=str(self.storage_base_path),
                cycle_params=cycle_params,
                batch_id=batch_id
            )
        
        elif source_type == "SFTP":
            # Future implementation
            raise NotImplementedError(f"SFTP loader not yet implemented")
        
        elif source_type == "API":
            # Future implementation
            raise NotImplementedError(f"API loader not yet implemented")
        
        else:
            raise ValueError(f"Unsupported source type: {source_type}")
    
    def create_loader_from_dict(
        self,
        source_name: str,
        source_type: str,
        config: Dict[str, Any],
        file_path: str = None,
        cycle_params: Dict[str, Any] = None,
        batch_id: str = None
    ) -> BaseDataLoader:
        """
        Create loader from dict config (without DataSourceConfig model)
        Useful for testing or dynamic configurations
        
        Args:
            source_name: Name of the source (B1, B2, etc.)
            source_type: Type of source (FILE_UPLOAD, DATABASE, etc.)
            config: Configuration dict for the source type
            file_path: Path to uploaded file
            cycle_params: Cycle parameters
            batch_id: Batch ID for logging
        
        Returns:
            Appropriate DataLoader instance
        """
        self.logger.info(f"[{batch_id or 'NO_BATCH'}] Creating loader from dict for {source_name}")
        
        if source_type == "FILE_UPLOAD":
            if not file_path:
                raise ValueError(f"file_path required for FILE_UPLOAD source")
            
            return FileDataLoader(
                source_name=source_name,
                config=config,
                file_path=file_path,
                batch_id=batch_id
            )
        
        elif source_type == "DATABASE":
            return DatabaseDataLoader(
                source_name=source_name,
                config=config,
                config_ini_path=str(self.config_ini_path),
                storage_base_path=str(self.storage_base_path),
                cycle_params=cycle_params,
                batch_id=batch_id
            )
        
        else:
            raise ValueError(f"Unsupported source type: {source_type}")
