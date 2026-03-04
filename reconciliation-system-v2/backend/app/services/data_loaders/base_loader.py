"""
Base Data Loader - Abstract base class for all data loaders
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional
import pandas as pd

from app.core.logging_config import get_data_loader_logger


@dataclass
class DataLoaderResult:
    """Result from data loading operation"""
    success: bool
    data: Optional[pd.DataFrame] = None
    row_count: int = 0
    error_message: Optional[str] = None
    source_name: str = ""
    source_type: str = ""
    load_time_seconds: float = 0.0
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.data is not None:
            self.row_count = len(self.data)


class BaseDataLoader(ABC):
    """
    Abstract base class for data loaders
    
    Subclasses must implement:
    - load(): Load data and return DataLoaderResult
    - validate_config(): Validate configuration before loading
    """
    
    def __init__(self, source_name: str, config: Dict[str, Any], batch_id: str = None):
        """
        Initialize loader
        
        Args:
            source_name: Name of the data source (B1, B2, etc.)
            config: Configuration dict for this source type
            batch_id: Optional batch ID for logging correlation
        """
        self.source_name = source_name
        self.config = config
        self.batch_id = batch_id or "NO_BATCH"
        self.logger = get_data_loader_logger()
    
    def log(self, level: str, message: str):
        """Log with batch ID prefix"""
        msg = f"[{self.batch_id}] [{self.source_name}] {message}"
        getattr(self.logger, level)(msg)
    
    @abstractmethod
    def validate_config(self) -> tuple[bool, str]:
        """
        Validate configuration before loading
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        pass
    
    @abstractmethod
    def load(self) -> DataLoaderResult:
        """
        Load data from source
        
        Returns:
            DataLoaderResult with loaded data or error
        """
        pass
    
    def apply_column_mapping(self, df: pd.DataFrame, columns_config: Dict[str, str]) -> pd.DataFrame:
        """
        Apply column mapping/renaming
        
        Args:
            df: Source DataFrame
            columns_config: Mapping of internal_name -> source_column
                           Example: {"txn_id": "A", "amount": "C"}
        
        Returns:
            DataFrame with renamed columns
        """
        if not columns_config:
            return df
        
        # For Excel-style column letters (A, B, C, ...)
        # First, check if values are letters
        rename_map = {}
        for internal_name, source_col in columns_config.items():
            if source_col in df.columns:
                rename_map[source_col] = internal_name
            elif source_col.isalpha() and len(source_col) <= 2:
                # Convert Excel column letter to index
                col_idx = self._excel_col_to_index(source_col)
                if col_idx < len(df.columns):
                    actual_col = df.columns[col_idx]
                    rename_map[actual_col] = internal_name
        
        if rename_map:
            df = df.rename(columns=rename_map)
        
        return df
    
    def _excel_col_to_index(self, col: str) -> int:
        """Convert Excel column letter to 0-based index (A=0, B=1, AA=26, etc.)"""
        result = 0
        for char in col.upper():
            result = result * 26 + (ord(char) - ord('A') + 1)
        return result - 1
    
    def apply_transforms(self, df: pd.DataFrame, transforms: Dict[str, str]) -> pd.DataFrame:
        """
        Apply transforms to columns
        
        Args:
            df: Source DataFrame
            transforms: Mapping of column -> transform expression
                       Example: {"txn_id": ".str.strip().str.upper()"}
        
        Returns:
            DataFrame with transforms applied
        """
        if not transforms:
            return df
        
        for col, transform in transforms.items():
            if col in df.columns:
                try:
                    # Build expression: df['col'].str.strip()...
                    expr = f"df['{col}']{transform}"
                    df[col] = eval(expr)
                    self.log('debug', f"Applied transform to {col}: {transform}")
                except Exception as e:
                    self.log('warning', f"Failed to apply transform to {col}: {e}")
        
        return df
