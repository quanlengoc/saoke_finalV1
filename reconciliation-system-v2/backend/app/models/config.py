"""
Partner Service Configuration model - V2 Simplified
Each row = 1 partner + 1 service + 1 validity period

Data sources, workflow steps, and output configs are now in separate tables:
- DataSourceConfig: Dynamic data sources (B1, B2, B3, B4, ...)
- WorkflowStep: Dynamic workflow steps (matching pairs)
- OutputConfig: Dynamic output configurations (A1, A2, ...)
"""

from datetime import datetime, date
from typing import Optional, List

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base


class PartnerServiceConfig(Base):
    """
    Configuration for partner + service combination - V2 Simplified
    
    Supports multiple configurations per partner/service with different validity periods.
    All data source configs, workflow steps, and output configs are now in child tables.
    """
    
    __tablename__ = "partner_service_config"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Partner and Service identification
    partner_code = Column(String(50), nullable=False, index=True)
    partner_name = Column(String(255), nullable=False)
    service_code = Column(String(50), nullable=False, index=True)
    service_name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    
    # Validity period - allows different configs for different time periods
    valid_from = Column(Date, nullable=False)
    valid_to = Column(Date, nullable=True)  # NULL = no end date
    
    # Report template configuration
    report_template_path = Column(String(500), nullable=True)
    # Cell mapping for filling report (JSON)
    # Example: {"sheets":[{"sheet_name":"Summary","sql_cells":[{"cell":"C10","sql":"SELECT COUNT(*) FROM temp_a1"}]}]}
    report_cell_mapping = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships to child tables
    data_sources = relationship("DataSourceConfig", back_populates="partner_service_config", 
                                cascade="all, delete-orphan", order_by="DataSourceConfig.display_order")
    workflow_steps = relationship("WorkflowStep", back_populates="partner_service_config",
                                  cascade="all, delete-orphan", order_by="WorkflowStep.step_order")
    output_configs = relationship("OutputConfig", back_populates="partner_service_config",
                                  cascade="all, delete-orphan", order_by="OutputConfig.display_order")
    
    # Unique constraint - one config per partner/service/valid_from
    __table_args__ = (
        UniqueConstraint('partner_code', 'service_code', 'valid_from', name='uq_partner_service_valid'),
    )
    
    def __repr__(self):
        return f"<PartnerServiceConfig(id={self.id}, partner='{self.partner_code}', service='{self.service_code}', valid_from='{self.valid_from}')>"
    
    def is_valid_for_date(self, check_date: date) -> bool:
        """Check if this config is valid for a given date"""
        if check_date < self.valid_from:
            return False
        if self.valid_to is not None and check_date > self.valid_to:
            return False
        return True
    
    def get_data_source(self, source_name: str):
        """Get a specific data source by name"""
        for ds in self.data_sources:
            if ds.source_name == source_name:
                return ds
        return None
    
    def get_required_data_sources(self) -> List:
        """Get all required data sources"""
        return [ds for ds in self.data_sources if ds.is_required]
    
    def get_file_upload_sources(self) -> List:
        """Get all FILE_UPLOAD data sources"""
        return [ds for ds in self.data_sources if ds.source_type == "FILE_UPLOAD"]
    
    def get_database_sources(self) -> List:
        """Get all DATABASE data sources"""
        return [ds for ds in self.data_sources if ds.source_type == "DATABASE"]
    
    def get_final_outputs(self) -> List:
        """Get all workflow steps that produce final outputs"""
        return [ws for ws in self.workflow_steps if ws.is_final_output]
    
    def get_output_config(self, output_name: str):
        """Get a specific output config by name"""
        for oc in self.output_configs:
            if oc.output_name == output_name:
                return oc
        return None
