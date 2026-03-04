"""
Database Data Loader - Load data from Oracle/SQLite databases
"""

import time
from pathlib import Path
from typing import Dict, Any, Optional
import pandas as pd
import configparser

from app.services.data_loaders.base_loader import BaseDataLoader, DataLoaderResult


class DatabaseDataLoader(BaseDataLoader):
    """
    Data loader for database sources
    
    Config format:
    {
        "db_connection": "vnptmoney_main",  # Connection name from config.ini
        "sql_file": "shared/query.sql",     # SQL template file
        "sql_params": {                     # Parameters for SQL
            "date_from": "2026-01-01",
            "date_to": "2026-01-31"
        },
        "mock_file": "mock_data.csv",       # Mock file for development
        "columns": {                        # Optional column mapping
            "txn_id": "TRANSACTION_ID",
            "amount": "TOTAL_AMOUNT"
        },
        "transforms": {                     # Optional transforms
            "txn_id": ".str.strip()"
        }
    }
    """
    
    SOURCE_TYPE = "DATABASE"
    
    def __init__(self, source_name: str, config: Dict[str, Any],
                 config_ini_path: str, storage_base_path: str,
                 cycle_params: Dict[str, Any] = None,
                 batch_id: str = None):
        """
        Initialize database loader
        
        Args:
            source_name: Name of the data source (B4, etc.)
            config: Database configuration dict
            config_ini_path: Path to config.ini
            storage_base_path: Base path for storage (sql_templates, mock_data)
            cycle_params: Cycle parameters (date_from, date_to, etc.)
            batch_id: Optional batch ID for logging
        """
        super().__init__(source_name, config, batch_id)
        self.config_ini_path = Path(config_ini_path)
        self.storage_base_path = Path(storage_base_path)
        self.cycle_params = cycle_params or {}
        
        # Load config.ini
        self.ini_config = configparser.ConfigParser()
        self.ini_config.read(self.config_ini_path)
    
    def validate_config(self) -> tuple[bool, str]:
        """Validate database configuration"""
        # Check required fields
        if 'db_connection' not in self.config:
            return False, "Missing 'db_connection' configuration"
        
        db_conn_name = self.config['db_connection']
        section_name = f"database.{db_conn_name}"
        
        # Check if connection exists in config.ini (or mock mode is enabled)
        if not self.ini_config.has_section(section_name):
            # Check if mock mode
            if self._is_mock_mode():
                if 'mock_file' not in self.config:
                    return False, f"Mock mode enabled but no 'mock_file' specified"
            else:
                return False, f"Database connection '{db_conn_name}' not found in config.ini"
        
        # Check SQL file exists (unless using mock)
        if not self._is_mock_mode():
            if 'sql_file' not in self.config:
                return False, "Missing 'sql_file' configuration"
            
            sql_path = self.storage_base_path / "sql_templates" / self.config['sql_file']
            if not sql_path.exists():
                return False, f"SQL file not found: {sql_path}"
        
        return True, ""
    
    def _is_mock_mode(self) -> bool:
        """Check if mock mode is enabled"""
        if self.ini_config.has_section('mock'):
            return self.ini_config.getboolean('mock', 'enabled', fallback=False)
        return False
    
    def load(self) -> DataLoaderResult:
        """Load data from database or mock file"""
        start_time = time.time()
        
        # Validate first
        is_valid, error = self.validate_config()
        if not is_valid:
            return DataLoaderResult(
                success=False,
                error_message=error,
                source_name=self.source_name,
                source_type=self.SOURCE_TYPE
            )
        
        try:
            # Check mock mode
            if self._is_mock_mode():
                df = self._load_from_mock()
            else:
                df = self._load_from_database()
            
            self.log('info', f"Loaded {len(df)} rows from database source")
            
            # Apply column mapping if specified
            columns_config = self.config.get('columns', {})
            if columns_config:
                df = self.apply_column_mapping(df, columns_config)
            
            # Apply transforms if specified
            transforms = self.config.get('transforms', {})
            if transforms:
                df = self.apply_transforms(df, transforms)
            
            # Add source column
            df['_source'] = self.source_name
            
            load_time = time.time() - start_time
            self.log('info', f"Database loading completed in {load_time:.2f}s")
            
            return DataLoaderResult(
                success=True,
                data=df,
                source_name=self.source_name,
                source_type=self.SOURCE_TYPE,
                load_time_seconds=load_time,
                metadata={
                    'db_connection': self.config.get('db_connection'),
                    'mock_mode': self._is_mock_mode(),
                    'columns_loaded': list(df.columns)
                }
            )
            
        except Exception as e:
            self.log('error', f"Failed to load from database: {e}")
            return DataLoaderResult(
                success=False,
                error_message=str(e),
                source_name=self.source_name,
                source_type=self.SOURCE_TYPE,
                load_time_seconds=time.time() - start_time
            )
    
    def _load_from_mock(self) -> pd.DataFrame:
        """Load from mock CSV file"""
        mock_file = self.config.get('mock_file')
        mock_path = self.storage_base_path / "mock_data" / mock_file
        
        self.log('info', f"Loading from mock file: {mock_path.name}")
        
        if not mock_path.exists():
            raise FileNotFoundError(f"Mock file not found: {mock_path}")
        
        df = pd.read_csv(mock_path, dtype=str)
        return df
    
    def _load_from_database(self) -> pd.DataFrame:
        """Load from actual database"""
        db_conn_name = self.config['db_connection']
        section_name = f"database.{db_conn_name}"
        
        # Get connection info
        db_type = self.ini_config.get(section_name, 'type')
        
        # Read SQL file
        sql_path = self.storage_base_path / "sql_templates" / self.config['sql_file']
        with open(sql_path, 'r', encoding='utf-8') as f:
            sql_template = f.read()
        
        # Merge sql_params with cycle_params
        params = {**self.config.get('sql_params', {}), **self.cycle_params}
        
        # Format SQL with parameters
        sql = sql_template.format(**params)
        
        self.log('debug', f"Executing SQL from {sql_path.name}")
        
        if db_type == 'oracle':
            return self._query_oracle(section_name, sql)
        elif db_type == 'sqlite':
            return self._query_sqlite(section_name, sql)
        else:
            raise ValueError(f"Unsupported database type: {db_type}")
    
    def _query_oracle(self, section_name: str, sql: str) -> pd.DataFrame:
        """Query Oracle database"""
        import oracledb
        
        dsn = self.ini_config.get(section_name, 'dsn')
        user = self.ini_config.get(section_name, 'user')
        password = self.ini_config.get(section_name, 'password')
        
        self.log('info', f"Connecting to Oracle: {dsn}")
        
        with oracledb.connect(user=user, password=password, dsn=dsn) as conn:
            df = pd.read_sql(sql, conn)
        
        return df
    
    def _query_sqlite(self, section_name: str, sql: str) -> pd.DataFrame:
        """Query SQLite database"""
        import sqlite3
        
        db_path = self.ini_config.get(section_name, 'path')
        
        self.log('info', f"Connecting to SQLite: {db_path}")
        
        with sqlite3.connect(db_path) as conn:
            df = pd.read_sql(sql, conn)
        
        return df
