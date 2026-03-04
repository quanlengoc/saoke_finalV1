"""
Output Configuration model
Dynamic output configurations for reports
"""

from datetime import datetime
from typing import Dict, Any, List
import json

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base


class OutputConfig(Base):
    """
    Output configuration
    Each row = 1 output configuration (which columns to include, filter, report usage)
    
    Outputs are created by WorkflowStep and can be used for:
    - Display in UI
    - Export to Excel
    - Fill into report template
    """
    
    __tablename__ = "output_config"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign key to partner_service_config
    config_id = Column(Integer, ForeignKey("partner_service_config.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Output identification (matches WorkflowStep.output_name)
    output_name = Column(String(50), nullable=False)  # A1, A2
    display_name = Column(String(100), nullable=True)  # "Kết quả đối soát chi tiết"
    
    # Column configuration (JSON)
    # {
    #   "columns": [
    #     {"name": "stt", "source": "auto", "type": "row_number"},
    #     {"name": "txn_id", "source": "B1", "column": "txn_id", "display_name": "Mã giao dịch"},
    #     {"name": "amount", "source": "B4", "column": "total_amount", "display_name": "Số tiền"},
    #     {"name": "status", "source": "computed", "column": "match_status_b1b4"}
    #   ]
    # }
    columns_config = Column(Text, nullable=False)
    
    # Filter by status (optional, JSON)
    # {"match_status": ["NOT_MATCHED", "AMOUNT_MISMATCH"]}
    filter_status = Column(Text, nullable=True)
    
    # Use this output for report template filling?
    use_for_report = Column(Boolean, default=True)
    
    # Display order in UI
    display_order = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    partner_service_config = relationship("PartnerServiceConfig", back_populates="output_configs")
    
    # Unique constraint
    __table_args__ = (
        UniqueConstraint('config_id', 'output_name', name='uq_config_output_name_config'),
    )
    
    def __repr__(self):
        return f"<OutputConfig(config_id={self.config_id}, output='{self.output_name}')>"
    
    @property
    def columns_config_dict(self) -> Dict[str, Any]:
        """Parse columns_config JSON to dict"""
        if self.columns_config:
            return json.loads(self.columns_config)
        return {}
    
    @property
    def filter_status_dict(self) -> Dict[str, Any]:
        """Parse filter_status JSON to dict"""
        if self.filter_status:
            return json.loads(self.filter_status)
        return {}
    
    def get_columns_list(self) -> List[Dict[str, Any]]:
        """Get list of column configurations"""
        config = self.columns_config_dict
        return config.get("columns", [])
    
    def get_column_names(self) -> List[str]:
        """Get list of output column names"""
        return [col.get("name") for col in self.get_columns_list() if col.get("name")]
    
    def get_columns_from_source(self, source: str) -> List[Dict[str, Any]]:
        """Get columns that come from a specific source (B1, B4, computed, etc.)"""
        return [col for col in self.get_columns_list() if col.get("source") == source]
