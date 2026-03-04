"""
Partner Service Configuration model
Each row = 1 partner + 1 service + 1 validity period
"""

from datetime import datetime, date
from typing import Optional

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Text, UniqueConstraint

from app.core.database import Base


class PartnerServiceConfig(Base):
    """
    Configuration for partner + service combination
    Supports multiple configurations per partner/service with different validity periods
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
    
    # File reading configs (JSON)
    # Example: {"header_row":1,"data_start_row":2,"columns":{"txn_id":"A","amount":"C"}}
    file_b1_config = Column(Text, nullable=False)
    file_b2_config = Column(Text, nullable=True)
    file_b3_config = Column(Text, nullable=True)
    
    # B4 data configuration (JSON) - includes db_connection name, sql_file, params, mock_file
    # Example: {"db_connection":"vnptmoney_main","sql_file":"shared/query.sql","sql_params":{},"mock_file":"mock.csv"}
    data_b4_config = Column(Text, nullable=False)
    
    # Matching rules (JSON)
    # Supports: expression mode or custom_module mode
    matching_rules_b1b4 = Column(Text, nullable=False)
    matching_rules_b1b2 = Column(Text, nullable=True)
    matching_rules_b3a1 = Column(Text, nullable=True)  # B3 as standard, matching with A1
    
    # Status combination rules (JSON)
    # Example: {"rules":[{"b1b4":"MATCHED","b1b2":"NOT_FOUND","final":"OK"}],"default":"UNKNOWN"}
    status_combine_rules = Column(Text, nullable=False)
    
    # Output column configuration (JSON) - which columns from B1, B2, B4 to include in A1
    # Example: {"columns":[{"name":"txn_id","source":"B1","column":"txn_id"},{"name":"amount","source":"B4","column":"total_amount"}]}
    output_a1_config = Column(Text, nullable=False)
    output_a2_config = Column(Text, nullable=True)
    
    # Report template configuration
    report_template_path = Column(String(500), nullable=True)
    # Cell mapping for filling report (JSON)
    # Example: {"sheets":[{"sheet_name":"Summary","sql_cells":[{"cell":"C10","sql":"SELECT COUNT(*) FROM temp_a1"}]}]}
    report_cell_mapping = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Unique constraint - one config per partner/service/valid_from
    __table_args__ = (
        UniqueConstraint('partner_code', 'service_code', 'valid_from', name='uq_partner_service_valid'),
    )
    
    def __repr__(self):
        return f"<PartnerServiceConfig(partner='{self.partner_code}', service='{self.service_code}', valid_from='{self.valid_from}')>"
    
    @property
    def is_valid_for_date(self, check_date: date) -> bool:
        """Check if this config is valid for a given date"""
        if check_date < self.valid_from:
            return False
        if self.valid_to is not None and check_date > self.valid_to:
            return False
        return True
