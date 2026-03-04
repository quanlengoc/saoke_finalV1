"""
Workflow Step model
Dynamic workflow steps for matching operations
"""

from datetime import datetime
from typing import Dict, Any, List
import json

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base


class WorkflowStep(Base):
    """
    Workflow step configuration
    Each row = 1 matching step in the workflow
    
    Steps are executed in order of step_order
    Each step matches left_source with right_source and produces output_name
    """
    
    __tablename__ = "workflow_step"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign key to partner_service_config
    config_id = Column(Integer, ForeignKey("partner_service_config.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Step order (1, 2, 3, ...)
    step_order = Column(Integer, nullable=False)
    
    # Step name for display
    step_name = Column(String(100), nullable=False)  # "Match B1 with B4", "Match A1 with B3"
    
    # Matching sources
    left_source = Column(String(50), nullable=False)   # B1, A1 (can be output from previous step)
    right_source = Column(String(50), nullable=False)  # B4, B3 (data source)
    
    # Join type
    join_type = Column(String(10), default="left")  # left, inner, right, outer
    
    # Matching rules (JSON)
    # {
    #   "key_match": {
    #     "mode": "expression",
    #     "left_expr": "LEFT['txn_id'].astype(str) + '_' + LEFT['amount'].astype(str)",
    #     "right_expr": "RIGHT['ref_id'].astype(str) + '_' + RIGHT['total_amount'].astype(str)"
    #   },
    #   "amount_match": {
    #     "enabled": true,
    #     "left_col": "amount",
    #     "right_col": "total_amount",
    #     "tolerance": 0
    #   }
    # }
    matching_rules = Column(Text, nullable=False)
    
    # Output configuration
    output_name = Column(String(50), nullable=False)  # A1, A2, intermediate_1
    output_type = Column(String(20), default="intermediate")  # intermediate, report
    output_columns = Column(Text, nullable=True)  # JSON config for output columns
    
    # Is this output used for final report?
    is_final_output = Column(Boolean, default=False)
    
    # Status combination rules (optional, only for steps that need to combine status)
    # {"rules": [{"b1b4": "MATCHED", "b1b2": "NOT_FOUND", "final": "OK"}], "default": "UNKNOWN"}
    status_combine_rules = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    partner_service_config = relationship("PartnerServiceConfig", back_populates="workflow_steps")
    
    # Unique constraints
    __table_args__ = (
        UniqueConstraint('config_id', 'step_order', name='uq_config_step_order'),
        UniqueConstraint('config_id', 'output_name', name='uq_config_output_name'),
    )
    
    def __repr__(self):
        return f"<WorkflowStep(config_id={self.config_id}, step={self.step_order}, '{self.left_source}'↔'{self.right_source}')>"
    
    @property
    def matching_rules_dict(self) -> Dict[str, Any]:
        """Parse matching_rules JSON to dict"""
        if self.matching_rules:
            return json.loads(self.matching_rules)
        return {}
    
    @property
    def output_columns_list(self) -> List[Dict[str, Any]]:
        """Parse output_columns JSON to list of column configs.
        
        Each item: {
            'id': 'col_xxx',           # frontend UI key (ignored by backend)
            'source': 'B1',            # source dataset name, or 'MATCH_STATUS'
            'source_column': 'credit_amount',  # column name in source dataset
            'column_name': 'credit_amount',    # output column name (alias)
            'display_name': 'Credit Amount'    # display label
        }
        """
        if self.output_columns:
            if isinstance(self.output_columns, list):
                return self.output_columns
            try:
                parsed = json.loads(self.output_columns)
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, TypeError):
                pass
        return []

    @property
    def status_combine_rules_dict(self) -> Dict[str, Any]:
        """Parse status_combine_rules JSON to dict"""
        if self.status_combine_rules:
            return json.loads(self.status_combine_rules)
        return {}
    
    def get_key_match_config(self) -> Dict[str, Any]:
        """Get key_match configuration from matching_rules"""
        rules = self.matching_rules_dict
        return rules.get("key_match", {})
    
    def get_amount_match_config(self) -> Dict[str, Any]:
        """Get amount_match configuration from matching_rules"""
        rules = self.matching_rules_dict
        return rules.get("amount_match", {})
    
    def is_expression_mode(self) -> bool:
        """Check if key matching uses expression mode"""
        key_match = self.get_key_match_config()
        return key_match.get("mode") == "expression"
    
    def is_custom_module_mode(self) -> bool:
        """Check if key matching uses custom module mode"""
        key_match = self.get_key_match_config()
        return key_match.get("mode") == "custom_module"
