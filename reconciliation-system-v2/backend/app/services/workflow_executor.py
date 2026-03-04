"""
Workflow Executor - V2
Orchestrates the reconciliation workflow from DB configuration

Uses:
- DataSourceConfig for loading data
- WorkflowStep for matching operations  
- OutputConfig for result building
- GenericMatchingEngine for actual matching
"""

import time
from typing import Dict, Any, List, Optional
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd

from app.models import PartnerServiceConfig, DataSourceConfig, WorkflowStep, OutputConfig
from app.services.generic_matching_engine import GenericMatchingEngine, JoinType
from app.services.data_loaders import DataLoaderFactory, DataLoaderResult
from app.core.logging_config import get_workflow_logger, BatchLogger


@dataclass
class WorkflowResult:
    """Result of workflow execution"""
    success: bool
    batch_id: str
    config_id: int
    outputs: Dict[str, pd.DataFrame]  # output_name -> DataFrame
    stats: Dict[str, Any]
    step_logs: List[Dict]
    error_message: Optional[str] = None
    total_time_seconds: float = 0.0


class WorkflowExecutor:
    """
    Executes reconciliation workflow from database configuration
    
    Flow:
    1. Load all required data sources (FILE_UPLOAD, DATABASE)
    2. Execute workflow steps in order
    3. Build output DataFrames according to OutputConfig
    4. Return results for export/report generation
    
    Usage:
        executor = WorkflowExecutor(config, batch_id, file_paths, cycle_params)
        result = executor.execute()
        
        if result.success:
            for name, df in result.outputs.items():
                print(f"{name}: {len(df)} rows")
    """
    
    def __init__(
        self,
        config: PartnerServiceConfig,
        batch_id: str,
        file_paths: Dict[str, str],  # source_name -> file_path
        cycle_params: Dict[str, Any] = None,
        config_ini_path: str = None,
        storage_base_path: str = None,
        on_step_log: callable = None
    ):
        """
        Initialize workflow executor
        
        Args:
            config: PartnerServiceConfig with loaded relationships
            batch_id: Unique batch identifier
            file_paths: Map of source_name to file_path for FILE_UPLOAD sources
            cycle_params: Parameters for database queries (date_from, date_to, etc.)
            config_ini_path: Path to config.ini (optional, uses default if not provided)
            storage_base_path: Base path for storage (optional)
            on_step_log: Optional callback(step_logs: List[Dict]) called after each log entry
        """
        self.config = config
        self.batch_id = batch_id
        self.file_paths = file_paths
        self.cycle_params = cycle_params or {}
        
        # Setup paths
        self.config_ini_path = config_ini_path or self._get_default_config_path()
        self.storage_base_path = storage_base_path or self._get_default_storage_path()
        
        # Initialize components
        self.logger = BatchLogger('workflow', batch_id)
        self.matching_engine = GenericMatchingEngine()
        self.loader_factory = DataLoaderFactory(self.config_ini_path, self.storage_base_path)
        
        # Storage for loaded data and results
        self.datasets: Dict[str, pd.DataFrame] = {}
        self.outputs: Dict[str, pd.DataFrame] = {}
        self.step_logs: List[Dict] = []
        self.stats: Dict[str, Any] = {}
        self.on_step_log = on_step_log  # Callback for real-time step progress
    
    def _get_default_config_path(self) -> str:
        """Get default config.ini path"""
        return str(Path(__file__).parent.parent.parent / "config.ini")
    
    def _get_default_storage_path(self) -> str:
        """Get default storage base path"""
        return str(Path(__file__).parent.parent.parent.parent / "storage")
    
    def _log_step(self, step: str, status: str, message: str, data_preview: dict = None):
        """Add a step log entry"""
        log_entry = {
            "step": step,
            "time": datetime.now().isoformat(),
            "status": status,
            "message": message
        }
        if data_preview:
            log_entry["data_preview"] = data_preview
        self.step_logs.append(log_entry)
        
        if status == "error":
            self.logger.error(f"[{step}] {message}")
        else:
            self.logger.info(f"[{step}] {message}")
        
        # Invoke callback for real-time progress updates
        if self.on_step_log:
            try:
                self.on_step_log(self.step_logs)
            except Exception:
                pass  # Don't let callback errors break the workflow
    
    def _build_data_preview(self, df, source_name: str, display_name: str, 
                            data_source_config=None, max_rows: int = 10) -> dict:
        """Build a preview dict of the first N rows of a DataFrame.
        
        Shows only the columns defined in the data source's file_config/db_config 'columns' mapping,
        so the user can verify the data that matters for matching.
        If no columns config exists, shows all columns.
        """
        import numpy as np
        
        # Determine which columns to show based on config
        config_columns = None
        if data_source_config:
            fc = data_source_config.file_config_dict or {}
            dc = data_source_config.db_config_dict or {}
            # file_config.columns = {internal_name: source_col_or_letter}
            config_columns = fc.get('columns') or dc.get('columns')
        
        if config_columns and isinstance(config_columns, dict):
            # Keys are the internal column names (post-rename)
            show_cols = [col for col in config_columns.keys() if col in df.columns]
            if not show_cols:
                # Fallback: maybe mapping hasn't been applied, show all
                show_cols = list(df.columns)
        else:
            show_cols = list(df.columns)
        
        # Filter to configured columns only
        preview_df = df[show_cols].head(max_rows).copy()
        
        # Convert to JSON-safe types
        for col in preview_df.columns:
            preview_df[col] = preview_df[col].apply(
                lambda x: None if (isinstance(x, float) and np.isnan(x)) else x
            )
        return {
            "source_name": source_name,
            "display_name": display_name,
            "columns": list(preview_df.columns),
            "rows": preview_df.astype(object).where(preview_df.notna(), None).to_dict(orient='records'),
            "total_rows": len(df)
        }
    
    def execute(self) -> WorkflowResult:
        """
        Execute the complete reconciliation workflow
        
        Returns:
            WorkflowResult with outputs and stats
        """
        start_time = time.time()
        
        try:
            self._log_step("init", "start", f"Starting workflow for config_id={self.config.id}")
            
            # Step 1: Load all data sources
            self._log_step("load_data", "start", "Loading data sources...")
            self._load_all_data_sources()
            
            # Step 2: Execute workflow steps
            self._log_step("matching", "start", "Executing matching steps...")
            self._execute_workflow_steps()
            
            # Step 3: Build outputs
            self._log_step("build_outputs", "start", "Building outputs...")
            self._build_outputs()
            
            # Calculate stats
            self._calculate_stats()
            
            total_time = time.time() - start_time
            self._log_step("complete", "ok", f"Workflow completed in {total_time:.2f}s")
            
            return WorkflowResult(
                success=True,
                batch_id=self.batch_id,
                config_id=self.config.id,
                outputs=self.outputs,
                stats=self.stats,
                step_logs=self.step_logs,
                total_time_seconds=total_time
            )
            
        except Exception as e:
            self.logger.exception(f"Workflow failed: {e}")
            return WorkflowResult(
                success=False,
                batch_id=self.batch_id,
                config_id=self.config.id,
                outputs={},
                stats={},
                step_logs=self.step_logs,
                error_message=str(e),
                total_time_seconds=time.time() - start_time
            )
    
    def _load_all_data_sources(self):
        """Load all configured data sources"""
        for ds in self.config.data_sources:
            result = self._load_single_source(ds)
            
            if not result.success:
                if ds.is_required:
                    self._log_step(f"load_{ds.source_name}", "error",
                                   f"FAILED to load required source {ds.source_name} ({ds.display_name}): {result.error_message}")
                    raise RuntimeError(f"Failed to load required source {ds.source_name}: {result.error_message}")
                else:
                    self._log_step(f"load_{ds.source_name}", "warning", 
                                   f"Optional source {ds.source_name} failed: {result.error_message}")
            else:
                self.datasets[ds.source_name.upper()] = result.data
                # Build data preview (first 10 rows) showing only configured columns
                preview = self._build_data_preview(
                    result.data, ds.source_name, ds.display_name,
                    data_source_config=ds
                )
                self._log_step(f"load_{ds.source_name}", "ok", 
                               f"Loaded {ds.source_name}: {result.row_count} rows in {result.load_time_seconds:.2f}s",
                               data_preview=preview)
    
    def _load_single_source(self, ds: DataSourceConfig) -> DataLoaderResult:
        """Load a single data source"""
        file_path = self.file_paths.get(ds.source_name)
        
        loader = self.loader_factory.create_loader(
            data_source=ds,
            file_path=file_path,
            cycle_params=self.cycle_params,
            batch_id=self.batch_id
        )
        
        return loader.load()
    
    def _execute_workflow_steps(self):
        """Execute all workflow steps in order"""
        # Sort steps by step_order
        steps = sorted(self.config.workflow_steps, key=lambda s: s.step_order)
        
        for step in steps:
            self._execute_single_step(step)
    
    def _find_output_config(self, output_name: str):
        """Find OutputConfig matching the given output name"""
        for cfg in self.config.output_configs:
            if cfg.output_name.upper() == output_name.upper():
                return cfg
        return None

    def _execute_single_step(self, step: WorkflowStep):
        """Execute a single matching step.
        
        match_datasets() returns a result containing:
        - {left}_index, {right}_index (row references)
        - All LEFT source columns (no prefix)  
        - status, note, amount_diff
        
        Output columns config is read from:
        1. step.output_columns (primary — saved by frontend on workflow_step)
        2. output_config table (fallback — legacy)
        
        The output_columns format from frontend:
        [
            {"source": "B1", "source_column": "credit_amount", "column_name": "credit_amount", ...},
            {"source": "B4", "source_column": "bill_amount", "column_name": "bill_amount", ...},
            {"source": "MATCH_STATUS", "source_column": "match_status", "column_name": "match_status", ...}
        ]
        """
        step_name = f"step_{step.step_order}_{step.left_source}_{step.right_source}"
        self._log_step(step_name, "start", f"Matching {step.left_source} ↔ {step.right_source}")
        
        # Get source DataFrames
        left_df = self._get_dataset(step.left_source)
        right_df = self._get_dataset(step.right_source)
        
        if left_df.empty:
            self._log_step(step_name, "warning", f"Left source {step.left_source} is empty")
        
        if right_df.empty:
            self._log_step(step_name, "warning", f"Right source {step.right_source} is empty")
        
        # Parse join type
        join_type = JoinType(step.join_type.lower()) if step.join_type else JoinType.LEFT
        
        # Get matching rules
        rules_config = step.matching_rules_dict
        
        # Execute matching — returns result with LEFT columns + indexes + status
        result_df = self.matching_engine.match_datasets(
            left_df=left_df,
            right_df=right_df,
            left_name=step.left_source.lower(),
            right_name=step.right_source.lower(),
            rules_config=rules_config,
            join_type=join_type
        )
        
        # Log stats
        matched = (result_df['status'] == 'MATCHED').sum() if 'status' in result_df.columns else 0
        not_found = (result_df['status'] == 'NOT_FOUND').sum() if 'status' in result_df.columns else 0
        
        # Get output columns config: prefer step.output_columns, fallback to output_config table
        step_output_cols = step.output_columns_list
        output_cfg = self._find_output_config(step.output_name)
        
        if step_output_cols:
            # PRIMARY: Use output_columns from workflow_step (frontend format)
            resolved_df = self._apply_step_output_columns(result_df, step_output_cols)
            
            # Apply filter from output_config if available
            if output_cfg:
                filter_config = output_cfg.filter_status_dict
                if filter_config:
                    resolved_df = self._apply_filter(resolved_df, filter_config)
                    resolved_df = resolved_df.reset_index(drop=True)
            
            self.datasets[step.output_name.upper()] = resolved_df
            self.logger.info(
                f"[{step_name}] Applied step output_columns for {step.output_name}: "
                f"{list(resolved_df.columns)}"
            )
        elif output_cfg:
            # FALLBACK: Use output_config table (legacy format)
            columns_config = output_cfg.columns_config_dict
            resolved_df = self._apply_output_columns(result_df, columns_config)
            
            filter_config = output_cfg.filter_status_dict
            if filter_config:
                resolved_df = self._apply_filter(resolved_df, filter_config)
                resolved_df = resolved_df.reset_index(drop=True)
            
            self.datasets[step.output_name.upper()] = resolved_df
            self.logger.info(
                f"[{step_name}] Applied output_config table for {step.output_name}: "
                f"{list(resolved_df.columns)}"
            )
        else:
            # No output config — store full matching result directly
            self.datasets[step.output_name.upper()] = result_df
        
        # Register with matching engine (for potential chained steps)
        self.matching_engine.register_dataset(
            step.output_name, self.datasets[step.output_name.upper()]
        )
        
        # Mark as final output if configured (only final outputs get exported to CSV)
        if step.is_final_output or (step.output_type == 'report'):
            self.outputs[step.output_name] = self.datasets[step.output_name.upper()]
        
        self._log_step(step_name, "ok", 
                       f"Completed: {len(result_df)} rows, MATCHED={matched}, NOT_FOUND={not_found}")
    
    def _get_dataset(self, source_name: str) -> pd.DataFrame:
        """Get dataset by name (from loaded data or intermediate results)"""
        return self.datasets.get(source_name.upper(), pd.DataFrame())
    
    def _build_outputs(self):
        """Build final outputs.
        
        Most outputs are already resolved during step execution
        (in _execute_single_step). This method handles any remaining 
        output configs that weren't already processed.
        
        Checks both:
        1. output_config table (legacy)
        2. workflow_steps with output_type='report' or is_final_output=True
        """
        # Collect all output names that should be final
        final_output_names = set()
        
        # From output_config table
        for output_cfg in self.config.output_configs:
            final_output_names.add(output_cfg.output_name)
        
        # From workflow_steps with output_type='report' or is_final_output
        for step in self.config.workflow_steps:
            if step.is_final_output or step.output_type == 'report':
                final_output_names.add(step.output_name)
        
        for output_name in final_output_names:
            # Skip if already built during step execution
            if output_name in self.outputs:
                self._log_step(f"output_{output_name}", "ok",
                               f"Output {output_name} already built: {len(self.outputs[output_name])} rows")
                continue
            
            # Get base data (from workflow step with same output_name)
            base_df = self._get_dataset(output_name)
            
            if base_df.empty:
                self._log_step(f"output_{output_name}", "warning", 
                               f"No data for output {output_name}")
                continue
            
            # Try to apply output_config from table (legacy fallback)
            output_cfg = self._find_output_config(output_name)
            if output_cfg:
                columns_config = output_cfg.columns_config_dict
                result_df = self._apply_output_columns(base_df, columns_config)
                
                filter_config = output_cfg.filter_status_dict
                if filter_config:
                    result_df = self._apply_filter(result_df, filter_config)
                    result_df = result_df.reset_index(drop=True)
                
                self.outputs[output_name] = result_df
            else:
                # No further config — use as-is
                self.outputs[output_name] = base_df
            
            self._log_step(f"output_{output_name}", "ok", 
                           f"Built output {output_name}: {len(self.outputs[output_name])} rows")
    
    # Column name mapping for MATCH_STATUS / computed source type.
    # The matching engine outputs: status, note, amount_diff.
    # Users may configure columns as match_status, match_detail, etc.
    MATCH_STATUS_COLUMN_MAP = {
        'match_status': 'status',
        'final_status': 'status',
        'match_detail': 'note',
        'amount_difference': 'amount_diff',
    }

    def _apply_step_output_columns(self, df: pd.DataFrame, columns_list: list) -> pd.DataFrame:
        """Apply output columns from workflow_step.output_columns (frontend format).
        
        Each column config from frontend:
        {
            'id': 'col_xxx',               # UI key (ignored)
            'source': 'B1',                # source name or 'MATCH_STATUS'
            'source_column': 'credit_amount',  # actual column in source
            'column_name': 'credit_amount',    # output column name (alias)
            'display_name': 'Credit Amount'    # display label
        }
        
        Resolution strategies:
        - source == 'MATCH_STATUS': map to status/note/amount_diff in raw result
        - source == LEFT name: column should be directly in df (LEFT propagated)
        - source == RIGHT name: lookup via {right}_index → datasets[source][column]
        - source == intermediate: chain lookup through index columns
        """
        if not columns_list:
            return df
        
        result_cols = {}
        expression_cols = []  # Deferred: process after all normal columns
        
        for col_cfg in columns_list:
            source = col_cfg.get('source', '')
            source_col = col_cfg.get('source_column', '')
            # Output column name: display_name (primary) → column_name (legacy fallback) → source_column
            output_col_name = col_cfg.get('display_name', '') or col_cfg.get('column_name', '') or source_col
            
            if not source:
                continue
            
            if source.upper() == 'EXPRESSION':
                # Defer EXPRESSION columns — they reference other output columns
                expression_cols.append((output_col_name, col_cfg))
                continue
            
            if not source_col:
                continue
            
            if source.upper() == 'MATCH_STATUS':
                # Match status columns from the raw matching result
                actual_col = self.MATCH_STATUS_COLUMN_MAP.get(source_col, source_col)
                if actual_col in df.columns:
                    result_cols[output_col_name] = df[actual_col].values
                elif source_col in df.columns:
                    result_cols[output_col_name] = df[source_col].values
                else:
                    self.logger.warning(
                        f"MATCH_STATUS column '{source_col}' (mapped: '{actual_col}') "
                        f"not in result. Available: {list(df.columns)}"
                    )
                    result_cols[output_col_name] = None
            else:
                # Source is a dataset name (B1, B4, A1_1, A1_2, etc.)
                resolved = self._resolve_column_value(df, source, source_col)
                if resolved is not None:
                    result_cols[output_col_name] = resolved
                else:
                    self.logger.warning(
                        f"Cannot resolve column: source={source}, col={source_col}. "
                        f"Result columns: {list(df.columns)}"
                    )
        
        # Process EXPRESSION columns (they reference already-resolved columns)
        if expression_cols and result_cols:
            temp_df = pd.DataFrame(result_cols)
            for output_col_name, col_cfg in expression_cols:
                expr_config = col_cfg.get('expression', {})
                rules = expr_config.get('rules', [])
                default_val = expr_config.get('default', '')
                
                if not rules:
                    self.logger.warning(f"EXPRESSION column '{output_col_name}' has no rules")
                    result_cols[output_col_name] = default_val
                    continue
                
                conditions = []
                values = []
                for rule in rules:
                    when_spec = rule.get('when', {})
                    then_val = rule.get('then', '')
                    if not when_spec:
                        continue
                    
                    # Support two formats:
                    # New: when = [ [{column, value}, ...], [...] ] → OR of AND-groups
                    # Old: when = {col: val, ...} → single AND-group (backward compat)
                    if isinstance(when_spec, dict):
                        # Legacy flat dict format → convert to new format
                        or_groups = [[{'column': k, 'value': v} for k, v in when_spec.items()]]
                    elif isinstance(when_spec, list):
                        or_groups = when_spec
                    else:
                        continue
                    
                    # Build OR of AND-groups
                    overall_cond = pd.Series(False, index=temp_df.index)
                    for group in or_groups:
                        if not isinstance(group, list) or not group:
                            continue
                        group_cond = pd.Series(True, index=temp_df.index)
                        for cond_item in group:
                            ref_col = cond_item.get('column', '')
                            ref_val = str(cond_item.get('value', ''))
                            if ref_col in temp_df.columns:
                                group_cond = group_cond & (temp_df[ref_col].astype(str) == ref_val)
                            else:
                                self.logger.warning(
                                    f"EXPRESSION '{output_col_name}': referenced column '{ref_col}' "
                                    f"not found. Available: {list(temp_df.columns)}"
                                )
                                group_cond = group_cond & False
                        overall_cond = overall_cond | group_cond
                    
                    conditions.append(overall_cond.values)
                    values.append(then_val)
                
                result_cols[output_col_name] = np.select(conditions, values, default=default_val)
                self.logger.info(
                    f"EXPRESSION column '{output_col_name}': {len(rules)} rules, "
                    f"default='{default_val}'"
                )
        
        if result_cols:
            return pd.DataFrame(result_cols)
        return df

    def _apply_output_columns(self, df: pd.DataFrame, columns_config: Dict[str, Any]) -> pd.DataFrame:
        """Apply output column configuration from output_config table (legacy format).
        
        Legacy format: {"columns": [{"name": "...", "source": "...", "column": "..."}]}
        """
        if not columns_config or 'columns' not in columns_config:
            return df
        
        columns = columns_config.get('columns', [])
        result_cols = {}
        
        for col_cfg in columns:
            col_name = col_cfg.get('name')
            source = col_cfg.get('source', '')
            source_col = col_cfg.get('column', col_name)
            
            if source == 'auto':
                if col_cfg.get('type') == 'row_number':
                    result_cols[col_name] = range(1, len(df) + 1)
            
            elif source.upper() in ('COMPUTED', 'MATCH_STATUS'):
                # Computed / match-status columns from the raw matching result.
                actual_col = self.MATCH_STATUS_COLUMN_MAP.get(source_col, source_col)
                if actual_col in df.columns:
                    result_cols[col_name] = df[actual_col].values
                elif source_col in df.columns:
                    result_cols[col_name] = df[source_col].values
            
            else:
                # Source is a dataset name (B1, B4, A1_1, A1_2, etc.)
                resolved = self._resolve_column_value(df, source, source_col)
                if resolved is not None:
                    result_cols[col_name] = resolved
                else:
                    self.logger.warning(
                        f"Cannot resolve column: source={source}, col={source_col}. "
                        f"Result columns: {list(df.columns)}"
                    )
        
        if result_cols:
            return pd.DataFrame(result_cols)
        return df
    
    def _resolve_column_value(self, df: pd.DataFrame, source: str, source_col: str):
        """
        Resolve a column value from a source dataset.
        
        match_datasets() returns: {left}_index + {right}_index + LEFT columns + status.
        RIGHT columns are NOT in the result — they are resolved via index lookup.
        
        Resolution order (IMPORTANT: index lookup BEFORE direct column check):
        1. Index lookup: {source}_index in df → self.datasets[source][source_col]
           This is checked FIRST to avoid incorrectly returning LEFT columns
           when RIGHT source has the same column name (e.g., both A1_1 and A1_2
           have 'match_status' — direct check would always return A1_1's value).
        2. Direct: source_col exists in df (LEFT columns propagated through chain)
           Only used when no index column for the source exists in df.
        3. Chain lookup: df has {inter}_index → datasets[inter] has {source}_index
           → datasets[source][source_col]
           (for RIGHT-side sources of previous steps, e.g., B2 via A1_2)
        
        Returns numpy array of values or None if not resolvable.
        """
        source_upper = source.upper()
        source_lower = source.lower()
        idx_col = f'{source_lower}_index'
        
        # 1. Index lookup: {source}_index → datasets[source][col]
        #    PRIORITY: Use index lookup when available to correctly resolve
        #    columns from the right source (avoids LEFT column name collision).
        if idx_col in df.columns and source_upper in self.datasets:
            source_df = self.datasets[source_upper]
            if source_col in source_df.columns:
                return self._index_lookup(df, idx_col, source_df, source_col,
                                          f"{source}.{source_col} → index lookup")
            # Also check MATCH_STATUS_COLUMN_MAP for sub-step status columns
            # (e.g., source_col='match_status' but dataset has 'status')
            alt_col = self.MATCH_STATUS_COLUMN_MAP.get(source_col, None)
            if alt_col and alt_col in source_df.columns:
                return self._index_lookup(df, idx_col, source_df, alt_col,
                                          f"{source}.{source_col} → mapped '{alt_col}' index lookup")
        
        # 2. Direct column in df (LEFT source columns, no prefix)
        #    Only used when no {source}_index exists (meaning source IS the LEFT)
        if source_col in df.columns:
            self.logger.info(f"Resolve: {source}.{source_col} → direct column ✓")
            return df[source_col].values
        
        # 3. Chain lookup: find an intermediate dataset that has {source}_index
        #    e.g., output wants B4.bill_amount, df has a1_1_index,
        #    datasets['A1_1'] has b4_index → datasets['B4'].bill_amount
        index_cols_in_df = [c for c in df.columns if c.endswith('_index')]
        for inter_idx_col in index_cols_in_df:
            inter_name = inter_idx_col.replace('_index', '').upper()
            if inter_name not in self.datasets:
                continue
            inter_df = self.datasets[inter_name]
            
            # 3a. Intermediate has source_col directly (LEFT propagation)
            if source_col in inter_df.columns:
                return self._chain_lookup(df, inter_idx_col, inter_df, source_col,
                                          f"{inter_idx_col} → {inter_name}.{source_col}")
            # 3a-fallback: try mapped column name (e.g., match_status → status)
            alt_col = self.MATCH_STATUS_COLUMN_MAP.get(source_col, None)
            if alt_col and alt_col in inter_df.columns:
                return self._chain_lookup(df, inter_idx_col, inter_df, alt_col,
                                          f"{inter_idx_col} → {inter_name}.{alt_col} (mapped from {source_col})")
            
            # 3b. Intermediate has {source}_index → chain to source dataset
            target_idx_col = f'{source_lower}_index'
            if target_idx_col in inter_df.columns and source_upper in self.datasets:
                source_df = self.datasets[source_upper]
                if source_col in source_df.columns:
                    return self._two_hop_lookup(
                        df, inter_idx_col, inter_df, target_idx_col,
                        source_df, source_col,
                        f"{inter_idx_col} → {inter_name}.{target_idx_col} → {source_upper}.{source_col}"
                    )
                # 3b-fallback: try mapped column name
                if alt_col and alt_col in source_df.columns:
                    return self._two_hop_lookup(
                        df, inter_idx_col, inter_df, target_idx_col,
                        source_df, alt_col,
                        f"{inter_idx_col} → {inter_name}.{target_idx_col} → {source_upper}.{alt_col} (mapped from {source_col})"
                    )
        
        # Not found
        self.logger.warning(
            f"Cannot resolve: source={source}, column={source_col}. "
            f"df columns: {list(df.columns)}, datasets: {list(self.datasets.keys())}"
        )
        return None
    
    def _index_lookup(self, df, idx_col, source_df, source_col, desc):
        """Single-hop index lookup: df[idx_col] → source_df[source_col]"""
        idx_series = df[idx_col].copy()
        valid = idx_series.notna()
        result_series = pd.Series([None] * len(df), index=df.index)
        if valid.any():
            result_series.loc[valid] = idx_series.loc[valid].astype(int).map(source_df[source_col])
        self.logger.info(f"Resolve: {desc} ✓")
        return result_series.values
    
    def _chain_lookup(self, df, inter_idx_col, inter_df, target_col, desc):
        """One-hop chain: df[inter_idx_col] → inter_df[target_col]"""
        idx_series = df[inter_idx_col].copy()
        valid = idx_series.notna()
        result_series = pd.Series([None] * len(df), index=df.index)
        if valid.any():
            result_series.loc[valid] = idx_series.loc[valid].astype(int).map(inter_df[target_col])
        self.logger.info(f"Resolve: {desc} ✓")
        return result_series.values
    
    def _two_hop_lookup(self, df, inter_idx_col, inter_df, target_idx_col,
                        source_df, source_col, desc):
        """Two-hop chain: df[inter_idx] → inter_df[target_idx] → source_df[source_col]"""
        inter_idx_series = df[inter_idx_col].copy()
        valid_inter = inter_idx_series.notna()
        result_series = pd.Series([None] * len(df), index=df.index)
        if valid_inter.any():
            inter_indices = inter_idx_series.loc[valid_inter].astype(int)
            target_indices = inter_indices.map(inter_df[target_idx_col])
            valid_target = target_indices.notna()
            if valid_target.any():
                values = target_indices.loc[valid_target].astype(int).map(source_df[source_col])
                result_series.loc[valid_target.index[valid_target]] = values
        self.logger.info(f"Resolve: {desc} ✓")
        return result_series.values
    
    def _apply_filter(self, df: pd.DataFrame, filter_config: Dict[str, Any]) -> pd.DataFrame:
        """Apply status filter.
        
        Checks for 'match_status' key in filter_config and filters rows.
        Looks for the status column under various names (status, match_status).
        """
        if 'match_status' in filter_config:
            statuses = filter_config['match_status']
            # Find the actual status column name
            for col_name in ('status', 'match_status', 'Status'):
                if col_name in df.columns:
                    return df[df[col_name].isin(statuses)]
        return df
    
    def _calculate_stats(self):
        """Calculate workflow statistics"""
        self.stats = {
            'config_id': self.config.id,
            'partner_code': self.config.partner_code,
            'service_code': self.config.service_code,
            'batch_id': self.batch_id,
            'data_sources_loaded': len(self.datasets),
            'outputs_generated': len(self.outputs),
            'output_details': {}
        }
        
        for name, df in self.outputs.items():
            status_counts = {}
            # Find status column (may be 'status' or 'match_status' after output config)
            for col in ('status', 'match_status', 'Status'):
                if col in df.columns:
                    status_counts = df[col].value_counts().to_dict()
                    break
            
            self.stats['output_details'][name] = {
                'row_count': len(df),
                'status_counts': status_counts
            }
