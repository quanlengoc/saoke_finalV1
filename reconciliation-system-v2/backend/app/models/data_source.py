"""
Data Source Configuration model
Supports dynamic data sources: FILE_UPLOAD, DATABASE, SFTP, API
"""

from datetime import datetime
from typing import Optional, Dict, Any
import json

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base


class DataSourceConfig(Base):
    """
    Dynamic data source configuration
    Each row = 1 data source for a partner_service_config
    
    Supports types:
    - FILE_UPLOAD: User uploads file via UI
    - DATABASE: Query from database connection
    - SFTP: Fetch from SFTP server (future)
    - API: Fetch from REST API (future)
    """
    
    __tablename__ = "data_source_config"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign key to partner_service_config
    config_id = Column(Integer, ForeignKey("partner_service_config.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Source identification
    source_name = Column(String(20), nullable=False)  # B1, B2, B3, B4, B5, etc.
    source_type = Column(String(20), nullable=False)  # FILE_UPLOAD, DATABASE, SFTP, API
    display_name = Column(String(100), nullable=True)  # "Sao kê ngân hàng", "Dữ liệu giao dịch"
    
    # Required for workflow?
    is_required = Column(Boolean, default=False)
    
    # Display order in UI
    display_order = Column(Integer, default=0)
    
    # Configuration JSON for each type
    # FILE_UPLOAD: {"header_row": 1, "data_start_row": 2, "columns": {"txn_id": "A", "amount": "C"}}
    file_config = Column(Text, nullable=True)
    
    # DATABASE: {"db_connection": "vnptmoney_main", "sql_file": "shared/query.sql", "sql_params": {}, "mock_file": "mock.csv"}
    db_config = Column(Text, nullable=True)
    
    # SFTP (future): {"host": "...", "path_pattern": "yyyymmdd/SACOMBANK_*.xlsx"}
    sftp_config = Column(Text, nullable=True)
    
    # API (future): {"url": "...", "method": "GET", "headers": {}}
    api_config = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    partner_service_config = relationship("PartnerServiceConfig", back_populates="data_sources")
    
    # Unique constraint - one source_name per config
    __table_args__ = (
        UniqueConstraint('config_id', 'source_name', name='uq_config_source_name'),
    )
    
    def __repr__(self):
        return f"<DataSourceConfig(config_id={self.config_id}, source='{self.source_name}', type='{self.source_type}')>"
    
    @property
    def file_config_dict(self) -> Dict[str, Any]:
        """Parse file_config JSON to dict"""
        if self.file_config:
            return json.loads(self.file_config)
        return {}
    
    @property
    def db_config_dict(self) -> Dict[str, Any]:
        """Parse db_config JSON to dict"""
        if self.db_config:
            return json.loads(self.db_config)
        return {}
    
    @property
    def sftp_config_dict(self) -> Dict[str, Any]:
        """Parse sftp_config JSON to dict"""
        if self.sftp_config:
            return json.loads(self.sftp_config)
        return {}
    
    @property
    def api_config_dict(self) -> Dict[str, Any]:
        """Parse api_config JSON to dict"""
        if self.api_config:
            return json.loads(self.api_config)
        return {}
    
    def get_config_for_type(self) -> Dict[str, Any]:
        """Get the config dict for current source_type"""
        type_config_map = {
            "FILE_UPLOAD": self.file_config_dict,
            "DATABASE": self.db_config_dict,
            "SFTP": self.sftp_config_dict,
            "API": self.api_config_dict,
        }
        return type_config_map.get(self.source_type, {})
