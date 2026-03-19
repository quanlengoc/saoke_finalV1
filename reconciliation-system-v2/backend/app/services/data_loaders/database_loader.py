"""
Database Data Loader - Load data from Oracle/SQLite databases
"""

import time
from pathlib import Path
from typing import Dict, Any, Optional
import pandas as pd
import configparser

from app.services.data_loaders.base_loader import BaseDataLoader, DataLoaderResult
from app.core.sql_security import SqlGuard, SqlSecurityError


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
        
        # Check if connection exists in config.ini
        if not self.ini_config.has_section(section_name):
            return False, f"Database connection '{db_conn_name}' not found in config.ini"

        # Check SQL file exists
        if 'sql_file' not in self.config:
            return False, "Missing 'sql_file' configuration"

        sql_path = self.storage_base_path / "sql_templates" / self.config['sql_file']
        if not sql_path.exists():
            return False, f"SQL file not found: {sql_path}"
        
        return True, ""
    
    def load(self) -> DataLoaderResult:
        """Load data from database"""
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
            df = self._load_from_database()
            
            self.log('info', f"Loaded {len(df)} rows from database source")
            
            # Apply column mapping if specified, otherwise auto-normalize column names
            columns_config = self.config.get('columns', {})
            if columns_config:
                df = self.apply_column_mapping(df, columns_config)
            else:
                df = self.auto_normalize_columns(df)
            
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
                    'columns_loaded': list(df.columns)
                }
            )
            
        except SqlSecurityError as e:
            self.log('error', f"SQL security violation: {e}")
            return DataLoaderResult(
                success=False,
                error_message=f"SQL security violation: {e}",
                source_name=self.source_name,
                source_type=self.SOURCE_TYPE,
                load_time_seconds=time.time() - start_time
            )
        except Exception as e:
            # Log full error to app log (for ops), show generic message to user
            import logging
            logging.getLogger('app').error(
                f"[DB_QUERY_ERROR] source={self.source_name} | error={e}", exc_info=True
            )
            self.log('error', f"Failed to load from database: {type(e).__name__}")
            return DataLoaderResult(
                success=False,
                error_message=f"Lỗi truy vấn database. Vui lòng kiểm tra cấu hình SQL và tham số. Chi tiết xem trong log vận hành.",
                source_name=self.source_name,
                source_type=self.SOURCE_TYPE,
                load_time_seconds=time.time() - start_time
            )
    
    def _load_from_database(self) -> pd.DataFrame:
        """Load from database"""
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

        # Security: validate params + format template + validate final SQL
        try:
            sql = SqlGuard.validate_format_params(
                sql_template, params,
                context=f"database_loader/{self.source_name}/{sql_path.name}"
            )
        except SqlSecurityError as e:
            self.log('error', f"SQL security violation: {e}")
            raise ValueError(f"SQL security violation: {e}")

        self.log('debug', f"Executing SQL from {sql_path.name}")
        # Log full SQL to app logger (for ops team), not to batch step log (user-facing)
        import logging
        logging.getLogger('app').info(
            f"[DB_QUERY] source={self.source_name} | file={sql_path.name} | "
            f"params={params} | SQL: {sql}"
        )

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
