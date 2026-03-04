"""
Generic Matching Engine - Refactored
Single matching function for all dataset pairs

Design principles:
1. ONE core matching function for all pairs (B1↔B4, B1↔B2, B3↔A1, etc.)
2. Configuration-driven workflow (list of matching steps)
3. Supports multiple join types (left, inner, right, outer)
4. Pluggable matching rules (key match, amount match, custom)
5. Output configuration for result columns
"""

import json
import logging
import importlib.util
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

import pandas as pd
import numpy as np

from app.core.config import get_storage_path
from app.core.exceptions import MatchingError, ConfigurationError
from app.utils.transform_utils import (
    apply_transforms_to_series, 
    concat_columns, 
    normalize_number_string, 
    normalize_number_series_vectorized, 
    transform_extract_amount
)

logger = logging.getLogger('reconciliation')


class JoinType(Enum):
    """Supported join types"""
    LEFT = 'left'
    RIGHT = 'right'
    INNER = 'inner'
    OUTER = 'outer'


@dataclass
class MatchingStep:
    """Configuration for a single matching step"""
    step_name: str           # e.g., "b1_b4", "b3_a1"
    left_source: str         # Source name: "B1", "B3", "A1.1", etc.
    right_source: str        # Source name: "B4", "B2", "A1", etc.
    output_name: str         # Output name: "A1.1", "A1.2", "A1", "A2"
    rules_config: Dict       # Matching rules (key_match, amount_match, etc.)
    join_type: JoinType = JoinType.LEFT
    output_columns: List[Dict] = None  # Output column configuration


class GenericMatchingEngine:
    """
    Generic Matching Engine
    
    All matching operations use the same core function.
    Workflow is driven by configuration, not hardcoded methods.
    """
    
    def __init__(self):
        self.datasets: Dict[str, pd.DataFrame] = {}  # Store intermediate results
        self.step_logs: List[Dict] = []
    
    def log_step(self, step: str, status: str, message: str):
        """Add a step log entry"""
        self.step_logs.append({
            "step": step,
            "time": datetime.now().isoformat(),
            "status": status,
            "message": message
        })
        logger.info(f"[{step}] {message}")
    
    def register_dataset(self, name: str, df: pd.DataFrame):
        """Register a dataset for use in matching steps"""
        self.datasets[name.upper()] = df
        self.log_step("register", "ok", f"Registered dataset '{name}' with {len(df)} rows")
    
    def get_dataset(self, name: str) -> pd.DataFrame:
        """Get a registered dataset by name"""
        return self.datasets.get(name.upper(), pd.DataFrame())
    
    # =========================================================================
    # CORE MATCHING FUNCTION - Single function for ALL matching operations
    # =========================================================================
    
    def match_datasets(
        self,
        left_df: pd.DataFrame,
        right_df: pd.DataFrame,
        left_name: str,
        right_name: str,
        rules_config: Dict[str, Any],
        join_type: JoinType = JoinType.LEFT
    ) -> pd.DataFrame:
        """
        Generic matching function for ANY pair of datasets
        
        This is the ONLY core matching function. All specific matches
        (B1↔B4, B1↔B2, B3↔A1, etc.) use this same function.
        
        Returns a result containing:
        - {left_name}_index, {right_name}_index: Index references for lookups
        - All LEFT source columns (no prefix, for chained step key availability)
        - status, note, amount_diff: Match result columns
        
        RIGHT source columns are NOT included in the result. They are resolved
        at output time via {right_name}_index → self.datasets[right_name][col],
        driven by output_config which already provides (source, column) → alias.
        This eliminates redundant prefixes — users already name columns in config.
        
        Args:
            left_df: Left DataFrame (drives the output rows for LEFT JOIN)
            right_df: Right DataFrame (lookup table)
            left_name: Name for left dataset (for column naming)
            right_name: Name for right dataset (for column naming)
            rules_config: Matching rules configuration containing:
                - match_type: 'expression' or 'custom_module'
                - rules: List of rule configs (key_match, amount_match, etc.)
                - status_logic: Status mapping for match results
            join_type: Type of join (LEFT, RIGHT, INNER, OUTER)
        
        Returns:
            DataFrame with: {left}_index + {right}_index + all LEFT cols + status + note + amount_diff
        """
        import time
        start_time = time.time()
        
        self.log_step(
            f"match_{left_name}_{right_name}", 
            "start", 
            f"Starting {left_name.upper()}↔{right_name.upper()} matching: "
            f"{left_name}={len(left_df)} rows, {right_name}={len(right_df)} rows, "
            f"join_type={join_type.value}"
        )
        
        # Handle empty DataFrames
        if left_df.empty:
            return pd.DataFrame()
        
        if right_df.empty:
            status_logic = rules_config.get('status_logic', {})
            result = pd.DataFrame({
                f'{left_name}_index': left_df.index.tolist(),
                f'{right_name}_index': [None] * len(left_df),
                'status': [status_logic.get('no_key_match', 'NOT_FOUND')] * len(left_df),
                'note': ['Dữ liệu đối chiếu trống'] * len(left_df),
                'amount_diff': [None] * len(left_df)
            })
            # Join LEFT source columns (for chained step key availability)
            for col in left_df.columns:
                if col not in result.columns:
                    result[col] = left_df[col].values
            return result
        
        # Get matching type
        match_type = rules_config.get('match_type', 'expression')
        
        if match_type == 'expression':
            result = self._match_by_expression(
                left_df, right_df, rules_config, 
                left_name, right_name, join_type
            )
        elif match_type == 'custom_module':
            result = self._match_by_custom_module(
                left_df, right_df, rules_config,
                left_name, right_name
            )
        else:
            raise MatchingError(f"Unknown match_type: {match_type}")
        
        elapsed = time.time() - start_time
        status_logic = rules_config.get('status_logic', {})
        matched_status = status_logic.get('all_match', 'MATCHED')
        matched_count = (result['status'] == matched_status).sum()
        
        self.log_step(
            f"match_{left_name}_{right_name}",
            "ok",
            f"Completed in {elapsed:.2f}s. Results: {len(result)} rows, "
            f"Matched: {matched_count}"
        )
        
        return result
    
    def _join_left_columns(
        self,
        results: pd.DataFrame,
        left_df: pd.DataFrame,
        left_name: str
    ) -> pd.DataFrame:
        """
        JOIN LEFT source columns back onto the match results.
        
        Only LEFT columns are added (no prefix) — these are needed so that
        chained workflow steps can reference source columns for key matching.
        
        RIGHT columns are NOT added here. They are resolved at output time
        via {right}_index → datasets[source][col], driven by output_config
        which already provides (source, column) → alias mapping.
        
        Internal columns (_match_key, _left_idx, _right_idx) are excluded.
        Existing result columns (status, note, amount_diff, *_index) are not overwritten.
        """
        internal_cols = {'_match_key', '_left_idx', '_right_idx'}
        
        left_cols = [c for c in left_df.columns if c not in internal_cols]
        if left_cols:
            left_idx_col = f'{left_name}_index'
            left_source = left_df[left_cols].copy()
            left_source['_join_idx'] = left_df['_left_idx'] if '_left_idx' in left_df.columns else left_df.index
            
            results = results.merge(
                left_source,
                left_on=left_idx_col,
                right_on='_join_idx',
                how='left',
                suffixes=('', '_dup')
            )
            results.drop(columns=['_join_idx'], inplace=True, errors='ignore')
            # Drop duplicate columns created by suffix
            dup_cols = [c for c in results.columns if c.endswith('_dup')]
            results.drop(columns=dup_cols, inplace=True, errors='ignore')
        
        logger.info(
            f"JOIN LEFT columns complete. "
            f"Result columns ({len(results.columns)}): {list(results.columns)}"
        )
        return results
    
    def _match_by_expression(
        self,
        left_df: pd.DataFrame,
        right_df: pd.DataFrame,
        rules_config: Dict[str, Any],
        left_name: str,
        right_name: str,
        join_type: JoinType
    ) -> pd.DataFrame:
        """
        Perform matching using expression rules with pandas merge
        """
        import re
        import time
        
        start_time = time.time()
        rules = rules_config.get('rules', [])
        status_logic = rules_config.get('status_logic', {})
        
        # Parse rules to extract key and amount columns
        key_rule = None
        amount_rule = None
        for rule in rules:
            if rule.get('rule_name') == 'key_match':
                key_rule = rule
            elif rule.get('rule_name') == 'amount_match':
                amount_rule = rule
        
        if not key_rule and rules:
            key_rule = rules[0]
        
        # =====================================================================
        # STRUCTURED CONFIG SUPPORT:
        # If no key_rule found in 'rules' array, check for top-level
        # key_match/amount_match structured config from the UI
        # =====================================================================
        structured_key_match = rules_config.get('key_match')
        structured_amount_match = rules_config.get('amount_match')
        use_structured = (not key_rule) and structured_key_match
        
        if use_structured:
            logger.info(f"Using structured key_match config (rules array is empty)")
            return self._match_by_structured_config(
                left_df, right_df,
                structured_key_match, structured_amount_match,
                left_name, right_name, join_type, status_logic
            )
        
        if not key_rule:
            return pd.DataFrame({
                f'{left_name}_index': left_df.index.tolist(),
                f'{right_name}_index': [None] * len(left_df),
                'status': ['NOT_FOUND'] * len(left_df),
                'amount_diff': [None] * len(left_df),
                'note': ['Không có rule matching'] * len(left_df)
            })
        
        # Parse key expression
        expression = key_rule.get('expression', '')
        left_key_col, left_transforms = self._parse_key_expression(expression, left_name)
        right_key_col, right_transforms = self._parse_key_expression(expression, right_name)
        
        logger.info(f"Parsed key columns: {left_name}[{left_key_col}] <-> {right_name}[{right_key_col}]")
        
        # Build key columns WITHOUT copying the full DataFrames
        left_keys = pd.DataFrame({
            '_left_idx': left_df.index,
            '_match_key': self._build_key_column(left_df, left_key_col, left_transforms),
        })
        right_keys = pd.DataFrame({
            '_right_idx': right_df.index,
            '_match_key': self._build_key_column(right_df, right_key_col, right_transforms),
        })
        
        left_unique = left_keys['_match_key'].nunique()
        right_unique = right_keys['_match_key'].nunique()
        logger.info(f"Built match keys. Left unique: {left_unique}, Right unique: {right_unique}")
        
        # Deduplicate right side before merge (prevent memory explosion)
        right_deduped = right_keys.drop_duplicates(
            subset=['_match_key'], keep='first'
        )
        logger.info(f"Right side deduped: {len(right_keys)} -> {len(right_deduped)} rows")
        
        # Perform merge based on join type
        merged = pd.merge(
            left_keys,
            right_deduped,
            on='_match_key',
            how=join_type.value,
            suffixes=('_left', '_right')
        )
        
        logger.info(f"Merge completed in {time.time() - start_time:.2f}s. Merged rows: {len(merged)}")
        
        # Handle duplicates on left side - keep first match
        merged = merged.drop_duplicates(subset=['_left_idx'], keep='first')
        
        # Build results DataFrame
        results = pd.DataFrame({
            f'{left_name}_index': merged['_left_idx'].values,
            f'{right_name}_index': merged['_right_idx'].values
        })
        
        # Determine status
        results['status'] = np.where(
            results[f'{right_name}_index'].isna(),
            status_logic.get('no_key_match', 'NOT_FOUND'),
            status_logic.get('all_match', 'MATCHED')
        )
        results['note'] = np.where(
            results[f'{right_name}_index'].isna(),
            'Không tìm thấy giao dịch khớp',
            'Khớp'
        )
        
        # Apply amount check if rule exists
        if amount_rule:
            results = self._apply_amount_check(
                results, left_df, right_df, amount_rule,
                left_name, right_name, status_logic
            )
        else:
            results['amount_diff'] = 0
        
        # JOIN LEFT source columns (for chained step key availability)
        results = self._join_left_columns(results, left_df, left_name)
        
        # No cleanup needed - we didn't modify original DataFrames
        
        return results
    
    def _match_by_structured_config(
        self,
        left_df: pd.DataFrame,
        right_df: pd.DataFrame,
        key_match: Dict[str, Any],
        amount_match: Optional[Dict[str, Any]],
        left_name: str,
        right_name: str,
        join_type: JoinType,
        status_logic: Dict[str, Any]
    ) -> pd.DataFrame:
        """
        Perform matching using structured key_match/amount_match config from UI.
        
        Config format:
        key_match = {
            "left": {
                "parts": [{"type": "column", "value": "col_name"}, {"type": "text", "value": "-"}],
                "transforms": ["strip", "upper"],
                "substring_start": 5,
                "substring_end": 17
            },
            "right": {
                "parts": [{"type": "column", "value": "col_name"}],
                "transforms": ["strip", "upper"]
            }
        }
        amount_match = {
            "left_column": "credit_amount",
            "right_column": "bill_amount",
            "tolerance": 0.01,
            "left": {"numberTransform": {"enabled": true, "thousandSeparator": ",", "decimalSeparator": "."}},
            "right": {"numberTransform": {...}}
        }
        """
        import time
        start_time = time.time()
        
        # Build key columns WITHOUT copying the full DataFrames
        # We only need the key column + index for the merge
        left_config = key_match.get('left', {})
        right_config = key_match.get('right', {})
        
        left_keys = pd.DataFrame({
            '_left_idx': left_df.index,
            '_match_key': self._build_structured_key_column(left_df, left_config, left_name),
        })
        right_keys = pd.DataFrame({
            '_right_idx': right_df.index,
            '_match_key': self._build_structured_key_column(right_df, right_config, right_name),
        })
        
        left_unique = left_keys['_match_key'].nunique()
        right_unique = right_keys['_match_key'].nunique()
        
        # Sample some keys for debugging
        left_sample = left_keys['_match_key'].dropna().head(3).tolist()
        right_sample = right_keys['_match_key'].dropna().head(3).tolist()
        logger.info(
            f"Structured match keys built. "
            f"Left unique: {left_unique}, Right unique: {right_unique}. "
            f"Left samples: {left_sample}, Right samples: {right_sample}"
        )
        
        # Deduplicate right side before merge
        right_deduped = right_keys.drop_duplicates(
            subset=['_match_key'], keep='first'
        )
        logger.info(f"Right side deduped: {len(right_keys)} -> {len(right_deduped)} rows")
        
        # Perform merge
        merged = pd.merge(
            left_keys,
            right_deduped,
            on='_match_key',
            how=join_type.value,
            suffixes=('_left', '_right')
        )
        
        logger.info(f"Merge completed in {time.time() - start_time:.2f}s. Merged rows: {len(merged)}")
        
        # Handle duplicates on left side
        merged = merged.drop_duplicates(subset=['_left_idx'], keep='first')
        
        # Build results DataFrame
        results = pd.DataFrame({
            f'{left_name}_index': merged['_left_idx'].values,
            f'{right_name}_index': merged['_right_idx'].values
        })
        
        # Determine status
        results['status'] = np.where(
            results[f'{right_name}_index'].isna(),
            status_logic.get('no_key_match', 'NOT_FOUND'),
            status_logic.get('all_match', 'MATCHED')
        )
        results['note'] = np.where(
            results[f'{right_name}_index'].isna(),
            'Không tìm thấy giao dịch khớp',
            'Khớp'
        )
        
        # Apply amount check if configured
        if amount_match:
            results = self._apply_structured_amount_check(
                results, left_df, right_df, amount_match,
                left_name, right_name, status_logic
            )
        else:
            results['amount_diff'] = 0
        
        # JOIN LEFT source columns (for chained step key availability)
        results = self._join_left_columns(results, left_df, left_name)
        
        # No cleanup needed - we didn't modify original DataFrames
        
        return results
    
    def _build_structured_key_column(
        self,
        df: pd.DataFrame,
        side_config: Dict[str, Any],
        side_name: str
    ) -> pd.Series:
        """
        Build a key column from structured config (parts + transforms + substring).
        
        side_config = {
            "parts": [{"type": "column", "value": "col_name"}, {"type": "text", "value": "-"}],
            "transforms": ["strip", "upper"],
            "substring_start": 5,
            "substring_end": 17
        }
        """
        parts = side_config.get('parts', [])
        transforms = side_config.get('transforms', [])
        substring_start = side_config.get('substring_start')
        substring_end = side_config.get('substring_end')
        
        if not parts:
            logger.warning(f"No parts in key config for {side_name}")
            return pd.Series([''] * len(df), index=df.index)
        
        # Build concatenated key from parts
        key_col = None
        for part in parts:
            part_type = part.get('type', 'column')
            part_value = part.get('value', '')
            
            if part_type == 'column':
                if part_value not in df.columns:
                    logger.warning(
                        f"Column '{part_value}' not found in {side_name}. "
                        f"Available: {list(df.columns)}"
                    )
                    part_series = pd.Series([''] * len(df), index=df.index)
                else:
                    part_series = df[part_value].astype(str).fillna('')
            elif part_type == 'text':
                part_series = pd.Series([part_value] * len(df), index=df.index)
            else:
                part_series = pd.Series([''] * len(df), index=df.index)
            
            if key_col is None:
                key_col = part_series
            else:
                key_col = key_col + part_series
        
        if key_col is None:
            return pd.Series([''] * len(df), index=df.index)
        
        # Apply substring if configured
        if substring_start is not None or substring_end is not None:
            start = int(substring_start) if substring_start is not None else None
            end = int(substring_end) if substring_end is not None else None
            key_col = key_col.str.slice(start, end)
            logger.info(f"Applied substring [{start}:{end}] to {side_name} key")
        
        # Apply transforms
        if isinstance(transforms, list):
            for t in transforms:
                if t == 'strip':
                    key_col = key_col.str.strip()
                elif t == 'upper':
                    key_col = key_col.str.upper()
                elif t == 'lower':
                    key_col = key_col.str.lower()
        
        # Default: strip and uppercase if no transforms specified
        if not transforms:
            key_col = key_col.str.strip()
        
        return key_col
    
    def _apply_structured_amount_check(
        self,
        results: pd.DataFrame,
        left_df: pd.DataFrame,
        right_df: pd.DataFrame,
        amount_match: Dict[str, Any],
        left_name: str,
        right_name: str,
        status_logic: Dict[str, Any]
    ) -> pd.DataFrame:
        """
        Apply amount check using structured amount_match config.
        
        amount_match = {
            "left_column": "credit_amount",
            "right_column": "bill_amount",
            "tolerance": 0.01,
            "left": {"numberTransform": {"enabled": true, "thousandSeparator": ",", ...}},
            "right": {"numberTransform": {...}}
        }
        """
        left_col = amount_match.get('left_column')
        right_col = amount_match.get('right_column')
        tolerance = amount_match.get('tolerance', 0.01)
        
        if not left_col or not right_col:
            results['amount_diff'] = 0
            return results
        
        matched_mask = results[f'{right_name}_index'].notna()
        results['amount_diff'] = None
        
        if matched_mask.any():
            left_indices = results.loc[matched_mask, f'{left_name}_index'].astype(int).values
            right_indices = results.loc[matched_mask, f'{right_name}_index'].astype(int).values
            
            try:
                left_raw = left_df.loc[left_indices, left_col] if left_col in left_df.columns else pd.Series([0]*len(left_indices))
                right_raw = right_df.loc[right_indices, right_col] if right_col in right_df.columns else pd.Series([0]*len(right_indices))
                
                # Apply number transforms if configured
                left_transform = amount_match.get('left', {}).get('numberTransform')
                right_transform = amount_match.get('right', {}).get('numberTransform')
                
                if left_transform and left_transform.get('enabled'):
                    thousand_sep = left_transform.get('thousandSeparator', ',')
                    decimal_sep = left_transform.get('decimalSeparator', '.')
                    left_amounts = normalize_number_series_vectorized(
                        left_raw, thousand_sep, decimal_sep
                    ).values
                else:
                    left_amounts = pd.to_numeric(left_raw, errors='coerce').fillna(0).values
                
                if right_transform and right_transform.get('enabled'):
                    thousand_sep = right_transform.get('thousandSeparator', ',')
                    decimal_sep = right_transform.get('decimalSeparator', '.')
                    right_amounts = normalize_number_series_vectorized(
                        right_raw, thousand_sep, decimal_sep
                    ).values
                else:
                    right_amounts = pd.to_numeric(right_raw, errors='coerce').fillna(0).values
                
                # Calculate difference
                diff = np.abs(left_amounts - right_amounts)
                results.loc[matched_mask, 'amount_diff'] = diff
                
                # Update status for mismatches
                mismatch_mask = matched_mask & (results['amount_diff'] > tolerance)
                mismatch_status = status_logic.get('key_match_amount_mismatch', 
                                    status_logic.get('amount_mismatch', 'MISMATCH'))
                results.loc[mismatch_mask, 'status'] = mismatch_status
                results.loc[mismatch_mask, 'note'] = 'Sai lệch số tiền'
                
            except Exception as e:
                logger.error(f"Structured amount check failed: {e}")
                import traceback
                logger.error(traceback.format_exc())
                results['amount_diff'] = 0
        
        return results
    
    def _parse_key_expression(self, expression: str, var_name: str) -> Tuple:
        """Parse expression to extract column name and transforms"""
        import re
        
        transforms = []
        parts = expression.split('==')
        
        if len(parts) != 2:
            pattern = rf"{var_name}\['(\w+)'\]"
            matches = re.findall(pattern, expression)
            return matches[0] if matches else None, transforms
        
        # Find the side containing this variable
        side = parts[0] if var_name in parts[0] else parts[1] if var_name in parts[1] else ''
        
        # Extract column names
        col_pattern = rf"{var_name}\['(\w+)'\]"
        col_matches = re.findall(col_pattern, side)
        
        # Extract transforms
        if '.str.strip()' in side:
            transforms.append('strip')
        if '.str.upper()' in side:
            transforms.append('upper')
        if '.str.lower()' in side:
            transforms.append('lower')
        
        # Check for .str.replace()
        replace_match = re.search(r"\.str\.replace\(r?'([^']+)',\s*'([^']*)'", side)
        if replace_match:
            transforms.append(('replace', replace_match.group(1), replace_match.group(2)))
        
        # Check for .str[start:end]
        slice_match = re.search(r'\.str\[(\d*):(\d*)\]', side)
        if slice_match:
            start = int(slice_match.group(1)) if slice_match.group(1) else 0
            end = int(slice_match.group(2)) if slice_match.group(2) else None
            transforms.append(('slice', start, end))
        
        # Extract literals for complex expressions
        literal_pattern = r"'([^']+)'"
        literals = re.findall(literal_pattern, side)
        
        if len(col_matches) == 1 and not literals:
            return col_matches[0], transforms
        elif col_matches:
            return {
                'columns': col_matches, 
                'literals': literals, 
                'side_expr': side.strip()
            }, transforms
        
        return None, transforms
    
    def _build_key_column(
        self, 
        df: pd.DataFrame, 
        key_spec, 
        transforms: list
    ) -> pd.Series:
        """Build a key column from specification"""
        if key_spec is None:
            return pd.Series([''] * len(df), index=df.index)
        
        if isinstance(key_spec, str):
            if key_spec not in df.columns:
                logger.warning(f"Column '{key_spec}' not found. Available: {list(df.columns)}")
                return pd.Series([''] * len(df), index=df.index)
            key_col = df[key_spec].astype(str).fillna('')
        elif isinstance(key_spec, dict):
            columns = key_spec.get('columns', [])
            if columns and columns[0] in df.columns:
                key_col = df[columns[0]].astype(str).fillna('')
                for col in columns[1:]:
                    if col in df.columns:
                        key_col = key_col + df[col].astype(str).fillna('')
            else:
                key_col = pd.Series([''] * len(df), index=df.index)
        else:
            key_col = pd.Series([''] * len(df), index=df.index)
        
        # Apply transforms in order
        for transform in transforms:
            if transform == 'strip':
                key_col = key_col.str.strip()
            elif transform == 'upper':
                key_col = key_col.str.upper()
            elif transform == 'lower':
                key_col = key_col.str.lower()
            elif isinstance(transform, tuple):
                if transform[0] == 'slice':
                    start, end = transform[1], transform[2]
                    key_col = key_col.str.slice(start, end)
                    logger.info(f"Applied slice [{start}:{end}]")
                elif transform[0] == 'replace':
                    pattern, replacement = transform[1], transform[2]
                    key_col = key_col.str.replace(pattern, replacement, regex=True)
                    logger.info(f"Applied replace: '{pattern}' -> '{replacement}'")
        
        return key_col
    
    def _apply_amount_check(
        self,
        results: pd.DataFrame,
        left_df: pd.DataFrame,
        right_df: pd.DataFrame,
        amount_rule: Dict,
        left_name: str,
        right_name: str,
        status_logic: Dict
    ) -> pd.DataFrame:
        """Apply amount matching check to results"""
        import re
        
        expression = amount_rule.get('expression', '')
        
        left_col_match = re.search(rf"{left_name}\['(\w+)'\]", expression)
        right_col_match = re.search(rf"{right_name}\['(\w+)'\]", expression)
        tolerance_match = re.search(r'<=\s*([\d.]+)', expression)
        
        if not left_col_match or not right_col_match:
            results['amount_diff'] = 0
            return results
        
        left_col = left_col_match.group(1)
        right_col = right_col_match.group(1)
        tolerance = float(tolerance_match.group(1)) if tolerance_match else 0.01
        
        matched_mask = results[f'{right_name}_index'].notna()
        results['amount_diff'] = None
        
        if matched_mask.any():
            left_indices = results.loc[matched_mask, f'{left_name}_index'].astype(int).values
            right_indices = results.loc[matched_mask, f'{right_name}_index'].astype(int).values
            
            try:
                left_raw = left_df.loc[left_indices, left_col]
                right_raw = right_df.loc[right_indices, right_col]
                
                # Apply number transforms if configured
                left_transform = amount_rule.get('left_number_transform')
                right_transform = amount_rule.get('right_number_transform')
                
                if left_transform and left_transform.get('enabled'):
                    thousand_sep = left_transform.get('thousandSeparator', ',')
                    decimal_sep = left_transform.get('decimalSeparator', '.')
                    left_amounts = normalize_number_series_vectorized(
                        left_raw, thousand_sep, decimal_sep
                    ).values
                else:
                    left_amounts = pd.to_numeric(left_raw, errors='coerce').fillna(0).values
                
                if right_transform and right_transform.get('enabled'):
                    thousand_sep = right_transform.get('thousandSeparator', ',')
                    decimal_sep = right_transform.get('decimalSeparator', '.')
                    right_amounts = normalize_number_series_vectorized(
                        right_raw, thousand_sep, decimal_sep
                    ).values
                else:
                    right_amounts = pd.to_numeric(right_raw, errors='coerce').fillna(0).values
                
                # Calculate difference
                diff = np.abs(left_amounts - right_amounts)
                results.loc[matched_mask, 'amount_diff'] = diff
                
                # Update status for mismatches
                mismatch_mask = matched_mask & (results['amount_diff'] > tolerance)
                results.loc[mismatch_mask, 'status'] = status_logic.get('amount_mismatch', 'MISMATCH')
                results.loc[mismatch_mask, 'note'] = 'Sai lệch số tiền'
                
            except Exception as e:
                logger.error(f"Amount check failed: {e}")
                results['amount_diff'] = 0
        
        return results
    
    def _match_by_custom_module(
        self,
        left_df: pd.DataFrame,
        right_df: pd.DataFrame,
        rules_config: Dict[str, Any],
        left_name: str,
        right_name: str
    ) -> pd.DataFrame:
        """Load and execute custom matching module"""
        module_name = rules_config.get('module_name', '')
        function_name = rules_config.get('function_name', 'match')
        
        custom_path = get_storage_path() / 'custom_matching' / f"{module_name}.py"
        
        if not custom_path.exists():
            raise MatchingError(f"Custom module not found: {custom_path}")
        
        spec = importlib.util.spec_from_file_location(module_name, custom_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        match_func = getattr(module, function_name, None)
        if not match_func:
            raise MatchingError(f"Function '{function_name}' not found in module")
        
        return match_func(left_df, right_df, rules_config, left_name, right_name)
    
    # =========================================================================
    # WORKFLOW EXECUTION - Configuration-driven matching pipeline
    # =========================================================================
    
    def execute_matching_step(self, step: MatchingStep) -> pd.DataFrame:
        """Execute a single matching step from configuration"""
        left_df = self.get_dataset(step.left_source)
        right_df = self.get_dataset(step.right_source)
        
        if left_df.empty:
            self.log_step(step.step_name, "skip", f"Left source '{step.left_source}' is empty")
            return pd.DataFrame()
        
        result = self.match_datasets(
            left_df=left_df,
            right_df=right_df,
            left_name=step.left_source.lower(),
            right_name=step.right_source.lower(),
            rules_config=step.rules_config,
            join_type=step.join_type
        )
        
        # Store result for next steps
        self.datasets[step.output_name.upper()] = result
        
        return result
    
    def execute_workflow(
        self,
        steps: List[MatchingStep],
        build_output_func=None
    ) -> Dict[str, Any]:
        """
        Execute complete matching workflow from configuration
        
        Args:
            steps: List of MatchingStep configurations
            build_output_func: Optional function to build final output DataFrames
        
        Returns:
            Dictionary with results and step logs
        """
        results = {}
        
        for step in steps:
            self.log_step("workflow", "processing", f"Executing step: {step.step_name}")
            result = self.execute_matching_step(step)
            results[step.output_name] = result
        
        return {
            "results": results,
            "datasets": self.datasets,
            "step_logs": self.step_logs
        }
    
    # =========================================================================
    # OUTPUT BUILDING - Build final DataFrames from matching results
    # =========================================================================
    
    def build_output_dataframe(
        self,
        match_results: pd.DataFrame,
        source_datasets: Dict[str, pd.DataFrame],
        output_config: Dict[str, Any],
        filter_status: List[str] = None
    ) -> pd.DataFrame:
        """
        Build output DataFrame from matching results
        
        This is generic for building A1, A2, or any output.
        
        Args:
            match_results: Matching results DataFrame
            source_datasets: Dict of source DataFrames by name
            output_config: Column configuration for output
            filter_status: Optional list of statuses to filter (e.g., ['NOT_FOUND'])
        
        Returns:
            Output DataFrame with configured columns
        """
        if match_results.empty:
            return pd.DataFrame()
        
        # Apply status filter if specified
        if filter_status:
            match_results = match_results[match_results['status'].isin(filter_status)]
        
        if match_results.empty:
            return pd.DataFrame()
        
        columns_config = output_config.get('columns', [])
        output_data = []
        
        # Get index column names from match_results
        index_cols = [c for c in match_results.columns if c.endswith('_index')]
        
        for _, result_row in match_results.iterrows():
            output_row = {}
            
            for col_config in columns_config:
                col_name = col_config.get('name')
                source = col_config.get('source', '').upper()
                source_col = col_config.get('column')
                default = col_config.get('default')
                
                if source == '_SYSTEM':
                    # System column from match_results
                    output_row[col_name] = result_row.get(source_col, default)
                elif source in source_datasets:
                    # Get from source dataset
                    idx_col = f'{source.lower()}_index'
                    if idx_col in result_row.index:
                        idx = result_row[idx_col]
                        if pd.notna(idx) and idx in source_datasets[source].index:
                            output_row[col_name] = source_datasets[source].loc[idx].get(
                                source_col, default
                            )
                        else:
                            output_row[col_name] = default
                    else:
                        output_row[col_name] = default
                else:
                    output_row[col_name] = default
            
            output_data.append(output_row)
        
        return pd.DataFrame(output_data)
