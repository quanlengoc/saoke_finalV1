"""
File Data Loader - Load data from uploaded files (Excel, CSV, ZIP)
Supports multi-file upload and ZIP extraction
"""

import gc
import time
import zipfile
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import numpy as np
import pandas as pd

from app.services.data_loaders.base_loader import BaseDataLoader, DataLoaderResult


class FileDataLoader(BaseDataLoader):
    """
    Data loader for file uploads (Excel, CSV, ZIP)
    
    Supports:
    - Single file path
    - Folder path containing multiple files
    - ZIP files (automatically extracted)
    - Multiple files merged into single DataFrame
    
    Config format:
    {
        "header_row": 1,           # 1-based row number for headers
        "data_start_row": 2,       # 1-based row number for data start
        "sheet_name": "Sheet1",    # For Excel files (optional)
        "columns": {               # Column mapping
            "txn_id": "A",
            "amount": "C",
            "date": "B"
        },
        "transforms": {            # Optional transforms
            "txn_id": ".str.strip().str.upper()",
            "amount": ".astype(float)"
        }
    }
    """
    
    SOURCE_TYPE = "FILE_UPLOAD"
    SUPPORTED_EXTENSIONS = {'.xlsx', '.xls', '.xlsb', '.csv', '.zip'}
    DATA_EXTENSIONS = {'.xlsx', '.xls', '.xlsb', '.csv'}
    
    def __init__(self, source_name: str, config: Dict[str, Any], 
                 file_path: str, batch_id: str = None):
        """
        Initialize file loader
        
        Args:
            source_name: Name of the data source (B1, B2, etc.)
            config: File configuration dict
            file_path: Path to file OR folder containing files
            batch_id: Optional batch ID for logging
        """
        super().__init__(source_name, config, batch_id)
        self.file_path = Path(file_path)
        self._temp_dirs: List[Path] = []  # Track temp dirs for cleanup
    
    def validate_config(self) -> Tuple[bool, str]:
        """Validate file configuration"""
        # Check path exists
        if not self.file_path.exists():
            return False, f"Path not found: {self.file_path}"
        
        # 'columns' is optional - if not present, all columns will be loaded as-is
        # This allows uploading files without pre-configuring column mapping
        
        return True, ""
    
    def _is_supported_file(self, path: Path) -> bool:
        """Check if file extension is supported"""
        return path.suffix.lower() in self.SUPPORTED_EXTENSIONS
    
    def _is_data_file(self, path: Path) -> bool:
        """Check if file is a data file (not ZIP)"""
        return path.suffix.lower() in self.DATA_EXTENSIONS
    
    def _is_zip_file(self, path: Path) -> bool:
        """Check if file is a ZIP archive"""
        return path.suffix.lower() == '.zip'
    
    def _extract_zip(self, zip_path: Path) -> List[Path]:
        """
        Extract ZIP file to temp directory
        
        Returns list of extracted data file paths
        """
        # Create temp directory
        temp_dir = Path(tempfile.mkdtemp(prefix=f"recon_{self.source_name}_"))
        self._temp_dirs.append(temp_dir)
        
        extracted_files = []
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            self.log('info', f"Extracted ZIP to: {temp_dir}")
            
            # Find all data files recursively
            for file_path in temp_dir.rglob('*'):
                if file_path.is_file() and self._is_data_file(file_path):
                    # Skip hidden files and temp files
                    if not file_path.name.startswith(('.', '~')):
                        extracted_files.append(file_path)
            
            self.log('info', f"Found {len(extracted_files)} data files in ZIP")
            
        except zipfile.BadZipFile as e:
            self.log('error', f"Invalid ZIP file: {zip_path.name} - {e}")
            raise ValueError(f"Invalid ZIP file: {zip_path.name}")
        
        return extracted_files
    
    def _collect_files(self) -> List[Path]:
        """
        Collect all files to process
        
        Handles:
        - Single file
        - Folder with multiple files
        - ZIP extraction (including nested ZIPs in folders)
        
        Returns sorted list of file paths
        """
        files_to_process = []
        
        if self.file_path.is_file():
            # Single file
            if self._is_zip_file(self.file_path):
                files_to_process.extend(self._extract_zip(self.file_path))
            elif self._is_data_file(self.file_path):
                files_to_process.append(self.file_path)
            else:
                raise ValueError(f"Unsupported file type: {self.file_path.suffix}")
        
        elif self.file_path.is_dir():
            # Folder with multiple files (supports mixed: ZIP + Excel + CSV)
            for file_path in sorted(self.file_path.iterdir()):
                if not file_path.is_file():
                    continue
                
                # Skip hidden/temp files
                if file_path.name.startswith(('.', '~')):
                    continue
                
                if self._is_zip_file(file_path):
                    # Extract ZIP and add contents
                    extracted = self._extract_zip(file_path)
                    self.log('info', f"ZIP '{file_path.name}' -> {len(extracted)} data file(s)")
                    files_to_process.extend(extracted)
                elif self._is_data_file(file_path):
                    files_to_process.append(file_path)
                else:
                    self.log('warning', f"Skipping unsupported file: {file_path.name}")
        
        # Sort for consistent ordering
        return sorted(files_to_process, key=lambda p: p.name)
    
    @staticmethod
    def _optimize_memory(df: pd.DataFrame) -> pd.DataFrame:
        """
        Reduce memory usage of a DataFrame.
        - Convert low-cardinality string columns to category
        NOTE: Do NOT drop columns here — it breaks column index-based mapping.
        """
        if df.empty:
            return df

        for col in df.columns:
            if isinstance(col, str) and col.startswith('_'):  # skip internal columns
                continue
            if df[col].dtype == object and not df[col].isna().all():
                nunique = df[col].nunique()
                total = len(df[col])
                # Convert to category if cardinality < 50% of total rows
                if nunique < total * 0.5:
                    df[col] = df[col].astype('category')

        return df

    def _cleanup_temp_dirs(self):
        """Clean up temporary extraction directories"""
        for temp_dir in self._temp_dirs:
            try:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
            except Exception as e:
                self.log('warning', f"Failed to cleanup temp dir: {temp_dir} - {e}")
        self._temp_dirs.clear()
    
    def load(self) -> DataLoaderResult:
        """Load data from file(s)"""
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
            self.log('info', f"Loading from: {self.file_path}")
            
            # Get config values
            columns_config = self.config.get('columns', {})
            transforms = self.config.get('transforms', {})
            sheet_name = self.config.get('sheet_name', 0)  # Default first sheet
            data_start_row = self.config.get('data_start_row', 2) - 1  # Convert to 0-based

            # Khi có columns_config (mapping by Excel position), header_row không cần thiết
            # vì user đã chỉ định alias cho từng cột theo vị trí (A, B, C...)
            # → đọc file với header=None, chỉ dùng data_start_row
            has_column_mapping = bool(columns_config)
            if has_column_mapping:
                header_row = None  # Signal to readers: no header row
                self.log('info', f"Column mapping configured — ignoring header_row, data starts at row {data_start_row + 1}")
            else:
                header_row = self.config.get('header_row', 1) - 1  # Convert to 0-based
            
            # Collect all files to process
            files = self._collect_files()
            
            if not files:
                return DataLoaderResult(
                    success=False,
                    error_message=f"No data files found in: {self.file_path}",
                    source_name=self.source_name,
                    source_type=self.SOURCE_TYPE
                )
            
            self.log('info', f"Processing {len(files)} file(s) for source {self.source_name}")
            if len(files) > 1:
                self.log('info', f"Multiple files detected - will merge data after reading")
            
            # Read and merge files incrementally to save memory
            merged_df = None
            file_stats = []
            
            for file_path in files:
                try:
                    chunk_df = self._read_single_file(file_path, header_row, data_start_row, sheet_name, has_column_mapping)
                    if not chunk_df.empty:
                        # Add file source tracking
                        chunk_df['_file_source'] = file_path.name
                        file_stats.append({
                            'file': file_path.name,
                            'rows': len(chunk_df)
                        })
                        self.log('info', f"  - {file_path.name}: {len(chunk_df)} rows")
                        
                        # Incremental concat to avoid holding all dfs in memory
                        if merged_df is None:
                            merged_df = chunk_df
                        else:
                            merged_df = pd.concat([merged_df, chunk_df], ignore_index=True)
                        del chunk_df
                        gc.collect()
                except Exception as e:
                    self.log('warning', f"  - {file_path.name}: Failed - {e}")
                    # Continue processing other files
            
            if merged_df is None or merged_df.empty:
                return DataLoaderResult(
                    success=False,
                    error_message=f"No data could be loaded from files",
                    source_name=self.source_name,
                    source_type=self.SOURCE_TYPE
                )
            
            df = merged_df
            del merged_df
            
            # Optimize memory: convert low-cardinality strings to category
            mem_before = df.memory_usage(deep=True).sum() / (1024 * 1024)
            df = self._optimize_memory(df)
            mem_after = df.memory_usage(deep=True).sum() / (1024 * 1024)
            gc.collect()
            self.log('info', f"Total rows after merge: {len(df)} | Memory: {mem_before:.1f}MB -> {mem_after:.1f}MB")
            
            # Apply column mapping
            df = self.apply_column_mapping(df, columns_config)
            
            # Apply transforms
            df = self.apply_transforms(df, transforms)
            
            # Add source column
            df['_source'] = self.source_name
            
            load_time = time.time() - start_time
            self.log('info', f"File loading completed in {load_time:.2f}s")
            
            return DataLoaderResult(
                success=True,
                data=df,
                source_name=self.source_name,
                source_type=self.SOURCE_TYPE,
                load_time_seconds=load_time,
                metadata={
                    'files_processed': len(files),
                    'file_stats': file_stats,
                    'total_rows': len(df),
                    'columns_loaded': list(df.columns)
                }
            )
            
        except Exception as e:
            self.log('error', f"Failed to load files: {e}")
            return DataLoaderResult(
                success=False,
                error_message=str(e),
                source_name=self.source_name,
                source_type=self.SOURCE_TYPE,
                load_time_seconds=time.time() - start_time
            )
        finally:
            # Always cleanup temp directories
            self._cleanup_temp_dirs()
    
    def _read_single_file(self, file_path: Path, header_row,
                          data_start_row: int, sheet_name,
                          has_column_mapping: bool = False) -> pd.DataFrame:
        """Read a single data file"""
        suffix = file_path.suffix.lower()

        if suffix == '.csv':
            return self._read_csv(file_path, header_row, data_start_row, has_column_mapping)
        elif suffix in {'.xlsx', '.xls', '.xlsb'}:
            return self._read_excel(file_path, header_row, data_start_row, sheet_name, has_column_mapping)
        else:
            raise ValueError(f"Unsupported file type: {suffix}")
    
    def _detect_csv_header_row(self, file_path: Path, encoding: str = 'utf-8') -> int:
        """
        Auto-detect the actual header row in a CSV file.
        Skips preamble lines (SQL statements, comments, blank lines) 
        by finding the first line that looks like a CSV header (multiple comma-separated fields).
        
        Returns 0-based row index of the header.
        """
        try:
            with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                for i, line in enumerate(f):
                    stripped = line.strip()
                    # Skip empty lines
                    if not stripped:
                        continue
                    # A header line should have multiple comma-separated fields
                    # and look like column names (mostly alphanumeric/underscore)
                    parts = [p.strip() for p in stripped.split(',')]
                    if len(parts) >= 3:
                        # Check if parts look like column names (alphanumeric, underscore, spaces)
                        # Non-header lines typically have SQL keywords, operators, etc.
                        looks_like_header = all(
                            p.replace('_', '').replace(' ', '').replace('-', '').isalnum() 
                            for p in parts if p
                        )
                        if looks_like_header:
                            return i
                    # Stop scanning after 50 lines
                    if i > 50:
                        break
        except Exception:
            pass
        return 0  # Default to first row
    
    def _read_csv(self, file_path: Path, header_row, data_start_row: int,
                  has_column_mapping: bool = False) -> pd.DataFrame:
        """Read CSV file with auto-detection of preamble/header"""
        encodings = ['utf-8', 'utf-8-sig', 'latin1', 'cp1252']
        df = None

        if has_column_mapping:
            # Có column mapping → đọc không header, skip đến data_start_row
            for encoding in encodings:
                try:
                    df = pd.read_csv(
                        file_path,
                        header=None,  # Không dùng header
                        skiprows=data_start_row,  # Skip tất cả dòng trước data
                        encoding=encoding,
                        dtype=str
                    )
                    break
                except UnicodeDecodeError:
                    continue
            if df is None:
                raise ValueError(f"Could not read CSV with any supported encoding")
            return df.reset_index(drop=True)

        # Không có column mapping → giữ logic cũ (đọc với header row)
        for encoding in encodings:
            try:
                skiprows = list(range(header_row)) if header_row > 0 else None
                df = pd.read_csv(
                    file_path,
                    header=0,
                    skiprows=skiprows,
                    encoding=encoding,
                    dtype=str
                )
                break
            except UnicodeDecodeError:
                continue
            except Exception as parse_error:
                if header_row == 0:
                    self.log('warning', f"CSV parse failed with header_row={header_row}, attempting auto-detection: {parse_error}")
                    detected_row = self._detect_csv_header_row(file_path, encoding)
                    if detected_row > 0:
                        self.log('info', f"Auto-detected CSV header at line {detected_row + 1} (skipping {detected_row} preamble lines)")
                        try:
                            df = pd.read_csv(
                                file_path,
                                header=0,
                                skiprows=list(range(detected_row)),
                                encoding=encoding,
                                dtype=str
                            )
                            data_start_row = detected_row + 1
                            header_row = detected_row
                            break
                        except Exception as e2:
                            self.log('warning', f"Auto-detect retry also failed: {e2}")
                            continue
                else:
                    raise

        if df is None:
            raise ValueError(f"Could not read CSV with any supported encoding")

        rows_to_skip = data_start_row - header_row - 1
        if rows_to_skip > 0:
            df = df.iloc[rows_to_skip:]

        return df.reset_index(drop=True)
    
    def _read_excel(self, file_path: Path, header_row,
                    data_start_row: int, sheet_name,
                    has_column_mapping: bool = False) -> pd.DataFrame:
        """Read Excel file (xlsx, xls, xlsb)"""
        suffix = file_path.suffix.lower()

        # Normalize empty/None sheet_name to default (first sheet = 0)
        if sheet_name is None or (isinstance(sheet_name, str) and sheet_name.strip() == ''):
            sheet_name = 0

        # For xlsb files, need pyxlsb engine
        engine = None
        if suffix == '.xlsb':
            engine = 'pyxlsb'
            if isinstance(sheet_name, int):
                try:
                    from pyxlsb import open_workbook
                    with open_workbook(str(file_path)) as wb:
                        sheets = wb.sheets
                        if sheet_name < len(sheets):
                            resolved_name = sheets[sheet_name]
                            self.log('info', f"xlsb: Resolved sheet index {sheet_name} to '{resolved_name}' (available: {sheets})")
                            sheet_name = resolved_name
                        else:
                            self.log('warning', f"xlsb: Sheet index {sheet_name} out of range, available sheets: {sheets}")
                            if sheets:
                                sheet_name = sheets[0]
                except Exception as e:
                    self.log('warning', f"xlsb: Could not resolve sheet name from index: {e}")
        elif suffix == '.xls':
            engine = 'xlrd'

        if has_column_mapping:
            # Có column mapping → đọc không header, skip đến data_start_row
            try:
                df = pd.read_excel(
                    file_path,
                    sheet_name=sheet_name,
                    header=None,  # Không dùng header
                    skiprows=data_start_row,  # Skip tất cả dòng trước data
                    dtype=str,
                    engine=engine
                )
            except Exception as e:
                self.log('warning', f"Failed with engine={engine}, trying default: {e}")
                df = pd.read_excel(
                    file_path,
                    sheet_name=sheet_name,
                    header=None,
                    skiprows=data_start_row,
                    dtype=str
                )
            return df.reset_index(drop=True)

        # Không có column mapping → giữ logic cũ
        try:
            df = pd.read_excel(
                file_path,
                sheet_name=sheet_name,
                header=header_row,
                dtype=str,
                engine=engine
            )
        except Exception as e:
            self.log('warning', f"Failed with engine={engine}, trying default: {e}")
            df = pd.read_excel(
                file_path,
                sheet_name=sheet_name,
                header=header_row,
                dtype=str
            )

        rows_to_skip = data_start_row - header_row - 1
        if rows_to_skip > 0:
            df = df.iloc[rows_to_skip:]

        return df.reset_index(drop=True)
