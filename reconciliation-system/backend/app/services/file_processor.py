"""
File processing service
Handles file upload, parsing, and conversion to standard CSV format
"""

import os
import json
import zipfile
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import pandas as pd

from app.core.config import get_storage_path
from app.core.exceptions import FileProcessingError
from app.utils.file_utils import (
    get_upload_path, get_processed_path, get_period_folder,
    generate_stored_filename, sanitize_filename,
    is_excel_file, is_csv_file, is_zip_file, is_supported_file
)
from app.utils.excel_utils import read_excel_with_config, read_csv_with_config


class FileProcessor:
    """
    Handles file upload and processing
    - Save uploaded files
    - Extract ZIP archives
    - Parse Excel/CSV files according to config
    - Merge multiple files into single DataFrame
    - Export processed data to standard CSV
    """
    
    def __init__(
        self,
        partner_code: str,
        service_code: str,
        period_from,
        period_to,
        batch_id: str
    ):
        self.partner_code = partner_code
        self.service_code = service_code
        self.period_from = period_from
        self.period_to = period_to
        self.batch_id = batch_id
        self.period = get_period_folder(period_from, period_to)
        
        # Initialize paths
        self.upload_path = get_upload_path(partner_code, self.period, batch_id)
        self.processed_path = get_processed_path(partner_code, self.period, batch_id)
    
    async def save_uploaded_file(
        self,
        file_content: bytes,
        original_filename: str,
        file_type: str,
        index: int = 0
    ) -> Tuple[str, str]:
        """
        Save an uploaded file to storage
        
        Args:
            file_content: File content as bytes
            original_filename: Original filename from upload
            file_type: Type of file (B1, B2, B3)
            index: File index for multiple files
        
        Returns:
            Tuple of (stored_filename, relative_path)
        """
        if not is_supported_file(original_filename):
            raise FileProcessingError(
                f"Unsupported file type: {original_filename}",
                {"filename": original_filename}
            )
        
        # Generate stored filename
        stored_filename = generate_stored_filename(
            file_type=file_type,
            partner_code=self.partner_code,
            service_code=self.service_code,
            period=self.period,
            batch_id=self.batch_id,
            original_name=original_filename,
            index=index
        )
        
        # Create type-specific subfolder
        type_folder = self.upload_path / file_type.lower()
        type_folder.mkdir(parents=True, exist_ok=True)
        
        # Save file
        file_path = type_folder / stored_filename
        with open(file_path, 'wb') as f:
            f.write(file_content)
        
        return stored_filename, str(file_path)
    
    def extract_zip(self, zip_path: Path) -> List[Path]:
        """
        Extract a ZIP file and return list of extracted files
        
        Args:
            zip_path: Path to ZIP file
        
        Returns:
            List of extracted file paths
        """
        extracted_files = []
        extract_dir = zip_path.parent / f"{zip_path.stem}_extracted"
        extract_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            # Collect extracted files
            for root, _, files in os.walk(extract_dir):
                for file in files:
                    file_path = Path(root) / file
                    if is_excel_file(file) or is_csv_file(file):
                        extracted_files.append(file_path)
        except zipfile.BadZipFile:
            raise FileProcessingError(
                f"Invalid ZIP file: {zip_path.name}",
                {"filename": zip_path.name}
            )
        
        return extracted_files
    
    def process_files(
        self,
        file_type: str,
        config: Dict[str, Any]
    ) -> pd.DataFrame:
        """
        Process all uploaded files of a type and merge into single DataFrame
        
        Args:
            file_type: Type of file (B1, B2, B3)
            config: File reading configuration
        
        Returns:
            Merged DataFrame
        """
        type_folder = self.upload_path / file_type.lower()
        
        if not type_folder.exists():
            return pd.DataFrame()
        
        all_dfs = []
        
        for file_path in type_folder.iterdir():
            if not file_path.is_file():
                continue
            
            try:
                if is_zip_file(file_path.name):
                    # Extract and process ZIP contents
                    extracted_files = self.extract_zip(file_path)
                    for extracted_file in extracted_files:
                        df = self._read_single_file(extracted_file, config)
                        if not df.empty:
                            all_dfs.append(df)
                else:
                    df = self._read_single_file(file_path, config)
                    if not df.empty:
                        all_dfs.append(df)
            except Exception as e:
                raise FileProcessingError(
                    f"Error processing file {file_path.name}: {str(e)}",
                    {"filename": file_path.name, "error": str(e)}
                )
        
        if not all_dfs:
            return pd.DataFrame()
        
        # Merge all DataFrames
        merged_df = pd.concat(all_dfs, ignore_index=True)
        
        return merged_df
    
    def process_file(
        self,
        file_path: str,
        file_type: str,
        config: Dict[str, Any] = None
    ) -> pd.DataFrame:
        """
        Process a single file from a given path
        
        Args:
            file_path: Path to file
            file_type: Type of file (B1, B2, B3)
            config: Optional reading configuration
        
        Returns:
            DataFrame
        """
        from pathlib import Path as PathLib
        path = PathLib(file_path)
        
        if not path.exists():
            raise FileProcessingError(
                f"File not found: {file_path}",
                {"filename": file_path}
            )
        
        # Default config if not provided
        if config is None:
            config = {"header_row": 1, "data_start_row": 2}
        
        try:
            if is_zip_file(path.name):
                # Extract and process ZIP contents
                extracted_files = self.extract_zip(path)
                all_dfs = []
                for extracted_file in extracted_files:
                    df = self._read_single_file(extracted_file, config)
                    if not df.empty:
                        all_dfs.append(df)
                return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()
            else:
                return self._read_single_file(path, config)
        except Exception as e:
            raise FileProcessingError(
                f"Error processing file {path.name}: {str(e)}",
                {"filename": path.name, "error": str(e)}
            )
    
    def _read_single_file(
        self,
        file_path: Path,
        config: Dict[str, Any]
    ) -> pd.DataFrame:
        """
        Read a single file according to config
        
        Args:
            file_path: Path to file
            config: Reading configuration
        
        Returns:
            DataFrame
        """
        if is_excel_file(file_path.name):
            return read_excel_with_config(file_path, config)
        elif is_csv_file(file_path.name):
            return read_csv_with_config(file_path, config)
        else:
            return pd.DataFrame()
    
    def save_processed_data(
        self,
        df: pd.DataFrame,
        file_type: str
    ) -> str:
        """
        Save processed DataFrame to CSV
        
        Args:
            df: DataFrame to save
            file_type: Type of file (B1, B2, B3)
        
        Returns:
            Path to saved CSV file
        """
        output_filename = f"{file_type}.csv"
        output_path = self.processed_path / output_filename
        
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        
        return str(output_path)
    
    def load_processed_data(self, file_type: str) -> pd.DataFrame:
        """
        Load processed data from CSV
        
        Args:
            file_type: Type of file (B1, B2, B3)
        
        Returns:
            DataFrame
        """
        csv_path = self.processed_path / f"{file_type}.csv"
        
        if not csv_path.exists():
            return pd.DataFrame()
        
        return pd.read_csv(csv_path)
    
    def get_uploaded_files_list(self) -> Dict[str, List[str]]:
        """
        Get list of uploaded files by type
        
        Returns:
            Dict with file types as keys and lists of filenames as values
        """
        result = {"b1": [], "b2": [], "b3": []}
        
        for file_type in ["b1", "b2", "b3"]:
            type_folder = self.upload_path / file_type
            if type_folder.exists():
                result[file_type] = [f.name for f in type_folder.iterdir() if f.is_file()]
        
        return result
    
    def cleanup_upload_folder(self):
        """Remove upload folder and all contents"""
        if self.upload_path.exists():
            shutil.rmtree(self.upload_path)
    
    def cleanup_processed_folder(self):
        """Remove processed folder and all contents"""
        if self.processed_path.exists():
            shutil.rmtree(self.processed_path)
