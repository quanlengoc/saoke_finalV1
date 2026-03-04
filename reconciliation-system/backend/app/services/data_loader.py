"""
Data loader service
Loads data from various sources: CSV files, mock data, database
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional

import pandas as pd

from app.core.config import get_settings, get_config_reader, get_storage_path
from app.core.database import DatabaseManager
from app.core.exceptions import DatabaseConnectionError, ConfigurationError


class DataLoader:
    """
    Handles loading data from different sources:
    - Processed CSV files (B1, B2, B3)
    - Mock CSV files (for testing B4)
    - Database queries (for production B4)
    """
    
    def __init__(self, partner_code: str, service_code: str, batch_id: str, period: str):
        self.partner_code = partner_code
        self.service_code = service_code
        self.batch_id = batch_id
        self.period = period
        self.settings = get_settings()
        self.config_reader = get_config_reader()
    
    def load_processed_csv(self, file_type: str) -> pd.DataFrame:
        """
        Load processed CSV file
        
        Args:
            file_type: Type of file (B1, B2, B3)
        
        Returns:
            DataFrame or empty DataFrame if file doesn't exist
        """
        processed_path = get_storage_path('processed')
        csv_path = processed_path / self.partner_code / self.period / self.batch_id / f"{file_type}.csv"
        
        if not csv_path.exists():
            return pd.DataFrame()
        
        return pd.read_csv(csv_path)
    
    def load_b4_data(
        self,
        config: Dict[str, Any],
        period_from,
        period_to
    ) -> pd.DataFrame:
        """
        Load B4 data from database or mock file
        
        Args:
            config: B4 data configuration (data_b4_config)
            period_from: Period start date
            period_to: Period end date
        
        Returns:
            DataFrame with B4 data
        """
        # Check if mock mode is enabled
        if self.settings.MOCK_MODE or self.config_reader.is_mock_mode():
            return self._load_mock_b4(config)
        else:
            return self._load_db_b4(config, period_from, period_to)
    
    def _load_mock_b4(self, config: Dict[str, Any]) -> pd.DataFrame:
        """
        Load B4 data from mock CSV file
        
        Args:
            config: B4 data configuration
        
        Returns:
            DataFrame with mock data
        
        Note:
            Mock file phải đúng định dạng:
            - Dòng 1: Tên các cột (header)
            - Dòng 2 trở đi: Dữ liệu
        """
        mock_file = config.get('mock_file')
        
        if not mock_file:
            # Try to generate mock filename from partner/service
            mock_file = f"{self.partner_code}_{self.service_code}_b4_mock.csv"
        
        mock_path = get_storage_path('mock_data') / mock_file
        
        if not mock_path.exists():
            raise ConfigurationError(
                f"Không tìm thấy file mock B4: {mock_file}. "
                f"Vui lòng kiểm tra file tại: {mock_path}"
            )
        
        # Try to read CSV
        try:
            df = pd.read_csv(mock_path)
            # Normalize column names to lowercase for case-insensitive matching
            df.columns = df.columns.str.lower()
        except Exception as e:
            raise ConfigurationError(
                f"Lỗi đọc file mock B4 '{mock_file}': {str(e)}. "
                f"File mock phải đúng định dạng CSV: dòng 1 là tên cột, các dòng sau là dữ liệu."
            )
        
        # Validate: check if first row looks like data (not SQL statement or garbage)
        if len(df) == 0:
            raise ConfigurationError(
                f"File mock B4 '{mock_file}' không có dữ liệu."
            )
        
        # Check if columns look valid (not starting with SQL keywords)
        first_col = df.columns[0] if len(df.columns) > 0 else ''
        if first_col.upper().startswith(('SQL', 'SELECT', '--', '/*')):
            raise ConfigurationError(
                f"File mock B4 '{mock_file}' không đúng định dạng. "
                f"Dòng đầu tiên phải là tên các cột (header), không phải SQL statement. "
                f"Vui lòng xóa các dòng SQL statement và chỉ giữ lại header + data."
            )
        
        return df
    
    def _load_db_b4(
        self,
        config: Dict[str, Any],
        period_from,
        period_to
    ) -> pd.DataFrame:
        """
        Load B4 data from database
        
        Args:
            config: B4 data configuration
            period_from: Period start date
            period_to: Period end date
        
        Returns:
            DataFrame with database data
        """
        db_connection = config.get('db_connection')
        sql_file = config.get('sql_file')
        sql_params = config.get('sql_params', {})
        
        if not db_connection:
            raise ConfigurationError("Missing db_connection in B4 config")
        
        if not sql_file:
            raise ConfigurationError("Missing sql_file in B4 config")
        
        # Load SQL from file
        sql_path = get_storage_path('sql_templates') / sql_file
        
        if not sql_path.exists():
            raise ConfigurationError(f"SQL file not found: {sql_file}")
        
        with open(sql_path, 'r', encoding='utf-8') as f:
            sql = f.read()
        
        # Add period parameters
        sql_params['date_from'] = period_from
        sql_params['date_to'] = period_to
        
        try:
            # Execute query
            results = DatabaseManager.execute_query(db_connection, sql, sql_params)
            
            if not results:
                return pd.DataFrame()
            
            return pd.DataFrame(results)
        except Exception as e:
            raise DatabaseConnectionError(
                f"Failed to load B4 data: {str(e)}",
                {"connection": db_connection, "error": str(e)}
            )
    
    def load_all_data(
        self,
        b4_config: Dict[str, Any],
        period_from,
        period_to
    ) -> Dict[str, pd.DataFrame]:
        """
        Load all data sources
        
        Args:
            b4_config: B4 data configuration
            period_from: Period start date
            period_to: Period end date
        
        Returns:
            Dict with DataFrames: {'B1': df, 'B2': df, 'B3': df, 'B4': df}
        """
        return {
            'B1': self.load_processed_csv('B1'),
            'B2': self.load_processed_csv('B2'),
            'B3': self.load_processed_csv('B3'),
            'B4': self.load_b4_data(b4_config, period_from, period_to)
        }


def parse_json_config(json_str: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Parse JSON string to dict
    
    Args:
        json_str: JSON string or None
    
    Returns:
        Dict or None
    """
    if not json_str:
        return None
    
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None
