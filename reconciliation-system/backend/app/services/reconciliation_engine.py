"""
Reconciliation Engine
Core matching logic for B1↔B4, B1↔B2, A1↔B3
Supports expression-based and custom module matching
"""

import json
import logging
import importlib.util
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

import pandas as pd
import numpy as np

from app.core.config import get_storage_path
from app.core.exceptions import MatchingError, ConfigurationError
from app.utils.transform_utils import apply_transforms_to_series, concat_columns, normalize_number_string, normalize_number_series_vectorized, transform_extract_amount

# Setup logger - use 'reconciliation' logger for dedicated log file
logger = logging.getLogger('reconciliation')


class ReconciliationEngine:
    """
    Core reconciliation engine
    Performs matching between data sources using configurable rules
    """
    
    def __init__(self):
        self.match_results = {}
        self.step_logs = []
    
    def log_step(self, step: str, status: str, message: str):
        """Add a step log entry"""
        self.step_logs.append({
            "step": step,
            "time": datetime.now().isoformat(),
            "status": status,
            "message": message
        })
    
    def match_b1_b4(
        self,
        b1_df: pd.DataFrame,
        b4_df: pd.DataFrame,
        rules_config: Dict[str, Any]
    ) -> pd.DataFrame:
        """
        Match B1 (bank statement) with B4 (system data)
        
        Args:
            b1_df: DataFrame B1
            b4_df: DataFrame B4
            rules_config: Matching rules configuration
        
        Returns:
            DataFrame with match results (b1_index, b4_index, status_b1b4, ...)
        """
        self.log_step("match_b1b4", "start", f"Starting B1↔B4 matching: B1={len(b1_df)} rows, B4={len(b4_df)} rows")
        
        match_type = rules_config.get('match_type', 'expression')
        
        if match_type == 'expression':
            result = self._match_expression(b1_df, b4_df, rules_config, 'b1', 'b4')
        elif match_type == 'custom_module':
            result = self._match_custom_module(b1_df, b4_df, rules_config)
        else:
            raise MatchingError(f"Unknown match_type: {match_type}")
        
        # Count results
        matched = (result['status'] == 'MATCHED').sum()
        not_found = (result['status'] == 'NOT_FOUND').sum()
        mismatch = (result['status'] == 'MISMATCH').sum()
        
        self.log_step("match_b1b4", "ok", f"Completed: MATCHED={matched}, NOT_FOUND={not_found}, MISMATCH={mismatch}")
        
        return result
    
    def match_b1_b2(
        self,
        b1_df: pd.DataFrame,
        b2_df: pd.DataFrame,
        rules_config: Dict[str, Any]
    ) -> pd.DataFrame:
        """
        Match B1 with B2 (refund data)
        
        Args:
            b1_df: DataFrame B1
            b2_df: DataFrame B2
            rules_config: Matching rules configuration
        
        Returns:
            DataFrame with match results
        """
        if b2_df.empty:
            # No B2 data, all B1 records are NOT_FOUND in B2
            result = pd.DataFrame({
                'b1_index': b1_df.index,
                'b2_index': None,
                'status': 'NOT_FOUND'
            })
            self.log_step("match_b1b2", "ok", "No B2 data, all marked as NOT_FOUND")
            return result
        
        self.log_step("match_b1b2", "start", f"Starting B1↔B2 matching: B1={len(b1_df)} rows, B2={len(b2_df)} rows")
        
        match_type = rules_config.get('match_type', 'expression')
        
        if match_type == 'expression':
            result = self._match_expression(b1_df, b2_df, rules_config, 'b1', 'b2')
        elif match_type == 'custom_module':
            result = self._match_custom_module(b1_df, b2_df, rules_config)
        else:
            raise MatchingError(f"Unknown match_type: {match_type}")
        
        matched = (result['status'] == 'MATCHED').sum()
        self.log_step("match_b1b2", "ok", f"Completed: MATCHED={matched}")
        
        return result
    
    def match_b3_a1(
        self,
        b3_df: pd.DataFrame,
        a1_df: pd.DataFrame,
        rules_config: Dict[str, Any]
    ) -> pd.DataFrame:
        """
        Match B3 with A1 - B3 is LEFT (standard), A1 is RIGHT
        
        This matches each B3 record against A1 to find which B3 transactions
        have corresponding records in our system (A1).
        Result A2 = B3 records that don't match A1
        
        Args:
            b3_df: DataFrame B3 (partner feedback - LEFT side)
            a1_df: DataFrame A1 (our result from B1↔B4↔B2 - RIGHT side)
            rules_config: Matching rules configuration
        
        Returns:
            DataFrame with match results (b3_index, a1_index, status)
        """
        if b3_df.empty:
            self.log_step("match_b3a1", "ok", "No B3 data, skipping B3↔A1 matching")
            return pd.DataFrame()
        
        self.log_step("match_b3a1", "start", f"Starting B3↔A1 matching: B3={len(b3_df)} rows, A1={len(a1_df)} rows")
        
        match_type = rules_config.get('match_type', 'expression')
        
        if match_type == 'expression':
            # B3 is LEFT, A1 is RIGHT - matches the config expression order
            result = self._match_expression(b3_df, a1_df, rules_config, 'b3', 'a1')
        elif match_type == 'custom_module':
            result = self._match_custom_module(b3_df, a1_df, rules_config)
        else:
            raise MatchingError(f"Unknown match_type: {match_type}")
        
        self.log_step("match_b3a1", "ok", f"Completed B3↔A1 matching")
        
        return result
    
    # Keep old method for backward compatibility
    def match_a1_b3(
        self,
        a1_df: pd.DataFrame,
        b3_df: pd.DataFrame,
        rules_config: Dict[str, Any]
    ) -> pd.DataFrame:
        """
        DEPRECATED: Use match_b3_a1 instead.
        This method swaps parameters to call match_b3_a1 correctly.
        """
        return self.match_b3_a1(b3_df, a1_df, rules_config)
    
    def _match_expression(
        self,
        left_df: pd.DataFrame,
        right_df: pd.DataFrame,
        rules_config: Dict[str, Any],
        left_name: str,
        right_name: str
    ) -> pd.DataFrame:
        """
        Perform matching using expression rules with pandas merge (optimized for large datasets)
        
        Args:
            left_df: Left DataFrame (e.g., B1)
            right_df: Right DataFrame (e.g., B4)
            rules_config: Rules configuration
            left_name: Name for left DataFrame (b1, a1)
            right_name: Name for right DataFrame (b4, b2, b3)
        
        Returns:
            Match results DataFrame
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
        
        if not key_rule:
            # No rules - return all as not found
            return pd.DataFrame({
                f'{left_name}_index': left_df.index.tolist(),
                f'{right_name}_index': [None] * len(left_df),
                'status': ['NOT_FOUND'] * len(left_df),
                'amount_diff': [None] * len(left_df),
                'note': ['Không có rule matching'] * len(left_df)
            })
        
        # Parse key expression to extract column names and transforms
        expression = key_rule.get('expression', '')
        left_key_col, left_transforms = self._parse_key_expression(expression, left_name)
        right_key_col, right_transforms = self._parse_key_expression(expression, right_name)
        
        logger.info(f"Parsed key columns: {left_name}[{left_key_col}] <-> {right_name}[{right_key_col}]")
        
        # Create temporary key columns for matching
        left_df = left_df.copy()
        right_df = right_df.copy()
        
        # Build left key
        left_df['_match_key'] = self._build_key_column(left_df, left_key_col, left_transforms)
        right_df['_match_key'] = self._build_key_column(right_df, right_key_col, right_transforms)
        
        # Store original indices
        left_df['_left_idx'] = left_df.index
        right_df['_right_idx'] = right_df.index
        
        left_unique_keys = left_df['_match_key'].nunique()
        right_unique_keys = right_df['_match_key'].nunique()
        logger.info(f"Built match keys. Left unique keys: {left_unique_keys}, Right unique keys: {right_unique_keys}")
        
        # IMPORTANT: Remove duplicates BEFORE merge to prevent memory explosion
        # When keys have many duplicates, merge creates cartesian product
        # E.g., 1000 rows with same key on left × 1000 rows with same key on right = 1,000,000 rows
        # We only need first match, so deduplicate right side first
        right_deduped = right_df[['_right_idx', '_match_key']].drop_duplicates(subset=['_match_key'], keep='first')
        
        logger.info(f"Right side deduped: {len(right_df)} -> {len(right_deduped)} rows")
        
        # Use pandas merge for fast matching (vectorized, O(n+m) with hash join)
        merged = pd.merge(
            left_df[['_left_idx', '_match_key']],
            right_deduped,
            on='_match_key',
            how='left',
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
        
        # Check amount matching if rule exists
        if amount_rule:
            results = self._apply_amount_check(
                results, left_df, right_df, amount_rule,
                left_name, right_name, status_logic
            )
        else:
            results['amount_diff'] = 0
        
        # Cleanup temporary columns
        left_df.drop(columns=['_match_key', '_left_idx'], inplace=True, errors='ignore')
        right_df.drop(columns=['_match_key', '_right_idx'], inplace=True, errors='ignore')
        
        elapsed = time.time() - start_time
        logger.info(f"Matching completed in {elapsed:.2f}s. Results: {len(results)} rows, Matched: {(results['status'] == status_logic.get('all_match', 'MATCHED')).sum()}")
        
        return results
    
    def _parse_key_expression(self, expression: str, var_name: str) -> tuple:
        """
        Parse expression to extract column name and transforms for a variable
        
        Args:
            expression: Full expression like "b1['txn_id'].str.strip().str[5:17] == b4['ref']"
            var_name: Variable name to extract (b1 or b4)
        
        Returns:
            tuple: (column_name_or_list, transforms_list)
        """
        import re
        
        transforms = []
        
        # Extract the side for this variable
        parts = expression.split('==')
        if len(parts) != 2:
            # Try to find the variable in the full expression
            pattern = rf"{var_name}\['(\w+)'\]"
            matches = re.findall(pattern, expression)
            return matches[0] if matches else None, transforms
        
        # Determine which side contains this variable
        side = parts[0] if var_name in parts[0] else parts[1] if var_name in parts[1] else ''
        
        # Simple pattern: var['col']
        col_pattern = rf"{var_name}\['(\w+)'\]"
        col_matches = re.findall(col_pattern, side)
        
        # Extract transforms
        if '.str.strip()' in side:
            transforms.append('strip')
        if '.str.upper()' in side:
            transforms.append('upper')
        if '.str.lower()' in side:
            transforms.append('lower')
        
        # Check for .str.replace(r'pattern', 'replacement', regex=True)
        replace_match = re.search(r"\.str\.replace\(r?'([^']+)',\s*'([^']*)'", side)
        if replace_match:
            pattern = replace_match.group(1)
            replacement = replace_match.group(2)
            transforms.append(('replace', pattern, replacement))
        
        # Check for substring: .str[start:end] or .str.slice(start, end)
        slice_match = re.search(r'\.str\[(\d*):(\d*)\]', side)
        if slice_match:
            start = int(slice_match.group(1)) if slice_match.group(1) else 0
            end = int(slice_match.group(2)) if slice_match.group(2) else None
            transforms.append(('slice', start, end))
        else:
            slice_match2 = re.search(r'\.str\.slice\((\d+),\s*(\d+)\)', side)
            if slice_match2:
                start = int(slice_match2.group(1))
                end = int(slice_match2.group(2))
                transforms.append(('slice', start, end))
        
        # Check for literal prefix/suffix
        literal_pattern = r"'([^']+)'"
        literals = re.findall(literal_pattern, side)
        
        if len(col_matches) == 1 and not literals:
            return col_matches[0], transforms
        elif col_matches:
            # Multiple columns or with literals - return as concatenation spec
            return {'columns': col_matches, 'literals': literals, 'side_expr': side.strip()}, transforms
        
        return None, transforms
    
    def _build_key_column(self, df: pd.DataFrame, key_spec, transforms: list) -> pd.Series:
        """
        Build a key column from specification
        
        Args:
            df: DataFrame to build key from
            key_spec: Column name (str) or dict with columns/literals
            transforms: List of transforms to apply
        
        Returns:
            Series with built keys
        """
        if key_spec is None:
            return pd.Series([''] * len(df), index=df.index)
        
        if isinstance(key_spec, str):
            # Simple single column
            if key_spec not in df.columns:
                logger.warning(f"Column '{key_spec}' not found in DataFrame. Available: {list(df.columns)}")
                return pd.Series([''] * len(df), index=df.index)
            key_col = df[key_spec].astype(str).fillna('')
        elif isinstance(key_spec, dict):
            # Complex key with multiple columns or literals
            columns = key_spec.get('columns', [])
            literals = key_spec.get('literals', [])
            side_expr = key_spec.get('side_expr', '')
            
            # Try to rebuild the concatenation from the expression
            # For now, simple approach: concatenate all columns
            if columns:
                key_col = df[columns[0]].astype(str).fillna('')
                for col in columns[1:]:
                    if col in df.columns:
                        key_col = key_col + df[col].astype(str).fillna('')
                
                # Add literals as prefix/suffix based on expression structure
                for lit in literals:
                    if lit and side_expr.startswith(f"'{lit}'"):
                        key_col = lit + key_col
                    elif lit and side_expr.endswith(f"'{lit}'"):
                        key_col = key_col + lit
            else:
                key_col = pd.Series([''] * len(df), index=df.index)
        else:
            key_col = pd.Series([''] * len(df), index=df.index)
        
        # Apply transforms
        for transform in transforms:
            if transform == 'strip':
                key_col = key_col.str.strip()
            elif transform == 'upper':
                key_col = key_col.str.upper()
            elif transform == 'lower':
                key_col = key_col.str.lower()
            elif transform == 'normalize_number':
                # Normalize number format with default params
                key_col = key_col.apply(lambda x: normalize_number_string(x, ',', '.'))
            elif transform == 'extract_amount':
                # Extract amount from text and normalize
                key_col = key_col.apply(transform_extract_amount)
            elif isinstance(transform, dict):
                # Transform with params
                if 'normalize_number' in transform:
                    params = transform['normalize_number']
                    thousand_sep = params.get('thousandSeparator', ',')
                    decimal_sep = params.get('decimalSeparator', '.')
                    key_col = key_col.apply(lambda x, t=thousand_sep, d=decimal_sep: normalize_number_string(x, t, d))
            elif isinstance(transform, tuple) and transform[0] == 'slice':
                # Handle slice transform: ('slice', start, end)
                start = transform[1]
                end = transform[2]
                key_col = key_col.str.slice(start, end)
                logger.info(f"Applied slice transform [{start}:{end}]")
            elif isinstance(transform, tuple) and transform[0] == 'replace':
                # Handle replace transform: ('replace', pattern, replacement)
                pattern = transform[1]
                replacement = transform[2]
                key_col = key_col.str.replace(pattern, replacement, regex=True)
                logger.info(f"Applied replace transform: '{pattern}' -> '{replacement}'")
        
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
        """
        Apply amount matching check to results
        """
        import re
        
        expression = amount_rule.get('expression', '')
        
        # Parse amount expression: abs(b1['amount'] - b4['total_amount']) <= 0.01
        left_col_match = re.search(rf"{left_name}\['(\w+)'\]", expression)
        right_col_match = re.search(rf"{right_name}\['(\w+)'\]", expression)
        tolerance_match = re.search(r'<=\s*([\d.]+)', expression)
        
        if not left_col_match or not right_col_match:
            results['amount_diff'] = 0
            return results
        
        left_col = left_col_match.group(1)
        right_col = right_col_match.group(1)
        tolerance = float(tolerance_match.group(1)) if tolerance_match else 0.01
        
        # Get amounts for matched rows
        matched_mask = results[f'{right_name}_index'].notna()
        results['amount_diff'] = None
        
        if matched_mask.any():
            left_indices = results.loc[matched_mask, f'{left_name}_index'].astype(int).values
            right_indices = results.loc[matched_mask, f'{right_name}_index'].astype(int).values
            
            # Get amount values - apply number transform if configured
            try:
                left_raw = left_df.loc[left_indices, left_col]
                right_raw = right_df.loc[right_indices, right_col]
                
                # Check if number transform is configured (from UI config)
                left_number_transform = amount_rule.get('left_number_transform')
                right_number_transform = amount_rule.get('right_number_transform')
                
                if left_number_transform and left_number_transform.get('enabled'):
                    thousand_sep = left_number_transform.get('thousandSeparator', ',')
                    decimal_sep = left_number_transform.get('decimalSeparator', '.')
                    # VECTORIZED - FAST! No loop through rows
                    left_amounts = normalize_number_series_vectorized(left_raw, thousand_sep, decimal_sep).values
                    logger.debug(f"Left amount transform (VECTORIZED): {thousand_sep=}, {decimal_sep=}")
                else:
                    left_amounts = pd.to_numeric(left_raw, errors='coerce').fillna(0).values
                
                if right_number_transform and right_number_transform.get('enabled'):
                    thousand_sep = right_number_transform.get('thousandSeparator', ',')
                    decimal_sep = right_number_transform.get('decimalSeparator', '.')
                    # VECTORIZED - FAST! No loop through rows
                    right_amounts = normalize_number_series_vectorized(right_raw, thousand_sep, decimal_sep).values
                    logger.debug(f"Right amount transform (VECTORIZED): {thousand_sep=}, {decimal_sep=}")
                else:
                    right_amounts = pd.to_numeric(right_raw, errors='coerce').fillna(0).values
                
                logger.debug(f"Amount comparison - Left: {left_raw.values[:3]} -> {left_amounts[:3]}, Right: {right_raw.values[:3]} -> {right_amounts[:3]}")
                
                amount_diffs = np.abs(left_amounts - right_amounts)
                results.loc[matched_mask, 'amount_diff'] = amount_diffs
                
                # Update status for amount mismatch
                mismatch_mask = matched_mask & (results['amount_diff'] > tolerance)
                results.loc[mismatch_mask, 'status'] = status_logic.get('key_match_amount_mismatch', 'MISMATCH')
                results.loc[mismatch_mask, 'note'] = 'Lệch số tiền'
            except Exception as e:
                logger.warning(f"Error checking amounts: {e}")
                results.loc[matched_mask, 'amount_diff'] = 0
        
        return results
    
    # ==================== DEPRECATED METHODS ====================
    # The following methods are deprecated and kept for reference only.
    # Use _match_expression with pandas merge instead for O(n+m) performance.
    # These old methods use O(n*m) nested loops and are extremely slow for large datasets.
    
    def _find_match_for_row(
        self,
        left_row: pd.Series,
        left_idx: int,
        right_df: pd.DataFrame,
        rules: List[Dict],
        status_logic: Dict[str, str],
        left_name: str,
        right_name: str
    ) -> Dict[str, Any]:
        """
        Find matching row in right DataFrame for a single left row
        """
        # Create a temporary DataFrame with single row for expression evaluation
        left_df_single = pd.DataFrame([left_row])
        
        # Evaluate key_match rule first to find candidates
        key_match_rule = None
        amount_match_rule = None
        
        for rule in rules:
            if rule.get('rule_name') == 'key_match':
                key_match_rule = rule
            elif rule.get('rule_name') == 'amount_match':
                amount_match_rule = rule
        
        if not key_match_rule:
            # If no explicit key_match, use first rule
            key_match_rule = rules[0] if rules else None
        
        # Find matching rows using key expression
        matched_indices = []
        
        if key_match_rule:
            expression = key_match_rule.get('expression', '')
            
            try:
                # Create namespace for expression evaluation
                # We need to compare each right row with left row
                for right_idx, right_row in right_df.iterrows():
                    # Create single-row DataFrames for comparison
                    namespace = {
                        left_name: left_df_single.iloc[0],
                        right_name: pd.DataFrame([right_row]).iloc[0],
                        'pd': pd,
                        'np': np,
                        'abs': abs,
                    }
                    
                    # Modify expression to work with Series
                    expr_modified = expression
                    
                    # Simple evaluation for row-by-row comparison
                    try:
                        result = self._eval_row_expression(left_row, right_row, expression, left_name, right_name)
                        if result:
                            matched_indices.append(right_idx)
                    except:
                        continue
                        
            except Exception as e:
                pass  # No matches found due to expression error
        
        # Determine status
        if not matched_indices:
            return {
                f'{left_name}_index': left_idx,
                f'{right_name}_index': None,
                'status': status_logic.get('no_key_match', 'NOT_FOUND'),
                'amount_diff': None,
                'note': 'Không tìm thấy giao dịch khớp'
            }
        
        # Found key match(es), check amount if needed
        right_idx = matched_indices[0]  # Take first match
        right_row = right_df.loc[right_idx]
        
        amount_matched = True
        amount_diff = None
        
        if amount_match_rule:
            try:
                amount_result = self._eval_row_expression(
                    left_row, right_row, 
                    amount_match_rule.get('expression', 'True'),
                    left_name, right_name
                )
                amount_matched = bool(amount_result)
                
                # Try to calculate amount difference
                # This is a simplified approach
            except:
                amount_matched = True
        
        if amount_matched:
            return {
                f'{left_name}_index': left_idx,
                f'{right_name}_index': right_idx,
                'status': status_logic.get('all_match', 'MATCHED'),
                'amount_diff': 0,
                'note': 'Khớp'
            }
        else:
            return {
                f'{left_name}_index': left_idx,
                f'{right_name}_index': right_idx,
                'status': status_logic.get('key_match_amount_mismatch', 'MISMATCH'),
                'amount_diff': amount_diff,
                'note': 'Lệch số tiền'
            }
    
    def _eval_row_expression(
        self,
        left_row: pd.Series,
        right_row: pd.Series,
        expression: str,
        left_name: str,
        right_name: str
    ) -> bool:
        """
        Evaluate expression for a pair of rows
        
        This handles expressions like:
        b1['txn_id'].str.strip().str.upper() == b4['transaction_ref'].str.strip().str.upper()
        """
        # For row-by-row comparison, we need to handle Series string operations
        # Convert the expression to work with individual values
        
        # Simple approach: replace DataFrame operations with value operations
        expr = expression
        
        # Create namespace with row values accessible
        namespace = {
            left_name: left_row,
            right_name: right_row,
            'pd': pd,
            'np': np,
            'abs': abs,
            'str': str,
        }
        
        # Handle common patterns
        try:
            # Pattern: df['col'].str.strip().str.upper() -> str(value).strip().upper()
            import re
            
            def replace_series_ops(match):
                var_name = match.group(1)
                col_name = match.group(2)
                ops = match.group(3) if match.lastindex >= 3 else ''
                
                # Build value extraction
                result = f"str({var_name}['{col_name}'])"
                
                # Handle string operations
                if '.str.strip()' in ops:
                    result = f"{result}.strip()"
                    ops = ops.replace('.str.strip()', '')
                if '.str.upper()' in ops:
                    result = f"{result}.upper()"
                    ops = ops.replace('.str.upper()', '')
                if '.str.lower()' in ops:
                    result = f"{result}.lower()"
                    ops = ops.replace('.str.lower()', '')
                
                return result
            
            # Pattern to match: b1['col'].str.xxx()
            pattern = r"(\w+)\['(\w+)'\]((?:\.str\.\w+\(\))*)"
            expr_modified = re.sub(pattern, replace_series_ops, expr)
            
            # Handle .astype(float) and .astype(int)
            expr_modified = re.sub(r'\.astype\(float\)', '', expr_modified)
            expr_modified = re.sub(r'\.astype\(int\)', '', expr_modified)
            
            # Handle str.cat for concatenation
            # b4['prefix'].str.cat(b4['txn_ref'], sep='')
            cat_pattern = r"(\w+)\['(\w+)'\]\.str\.cat\((\w+)\['(\w+)'\],\s*sep='([^']*)'\)"
            def replace_cat(m):
                var1, col1, var2, col2, sep = m.groups()
                return f"(str({var1}['{col1}']) + '{sep}' + str({var2}['{col2}']))"
            expr_modified = re.sub(cat_pattern, replace_cat, expr_modified)
            
            # Evaluate
            result = eval(expr_modified, {"__builtins__": {}}, namespace)
            return bool(result)
            
        except Exception as e:
            # Fallback: direct comparison
            return False
    
    def _match_custom_module(
        self,
        left_df: pd.DataFrame,
        right_df: pd.DataFrame,
        rules_config: Dict[str, Any]
    ) -> pd.DataFrame:
        """
        Perform matching using custom Python module
        """
        module_path = rules_config.get('module_path')
        function_name = rules_config.get('function_name')
        params = rules_config.get('params', {})
        
        if not module_path or not function_name:
            raise ConfigurationError("custom_module requires module_path and function_name")
        
        # Load module
        custom_matching_path = get_storage_path('custom_matching')
        full_path = custom_matching_path / module_path.replace('custom_matching/', '')
        
        if not full_path.exists():
            raise ConfigurationError(f"Custom module not found: {module_path}")
        
        # Import module dynamically
        spec = importlib.util.spec_from_file_location("custom_match", full_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Get function
        if not hasattr(module, function_name):
            raise ConfigurationError(f"Function {function_name} not found in {module_path}")
        
        match_func = getattr(module, function_name)
        
        # Call function
        return match_func(left_df, right_df, params)
    
    def combine_statuses(
        self,
        b1b4_results: pd.DataFrame,
        b1b2_results: pd.DataFrame,
        combine_rules: Dict[str, Any]
    ) -> pd.DataFrame:
        """
        Combine B1↔B4 and B1↔B2 statuses into final status
        
        Args:
            b1b4_results: Results from B1↔B4 matching
            b1b2_results: Results from B1↔B2 matching
            combine_rules: Rules for combining statuses
        
        Returns:
            DataFrame with final_status column
        """
        rules = combine_rules.get('rules', [])
        default = combine_rules.get('default', 'UNKNOWN')
        
        # Merge results
        combined = b1b4_results.copy()
        combined = combined.rename(columns={'status': 'status_b1b4'})
        
        # Add B1B2 status AND b2_index from B1B2 matching results
        b1b2_status_map = dict(zip(b1b2_results['b1_index'], b1b2_results['status']))
        combined['status_b1b2'] = combined['b1_index'].map(b1b2_status_map).fillna('NOT_FOUND')
        
        # Add b2_index for joining B2 data later
        if 'b2_index' in b1b2_results.columns:
            b1b2_index_map = dict(zip(b1b2_results['b1_index'], b1b2_results['b2_index']))
            combined['b2_index'] = combined['b1_index'].map(b1b2_index_map)
            self.log_step("combine_status", "info", f"Added b2_index mapping, non-null: {combined['b2_index'].notna().sum()}")
        
        # Determine final status
        def get_final_status(row):
            b1b4 = row['status_b1b4']
            b1b2 = row['status_b1b2']
            
            for rule in rules:
                rule_b1b4 = rule.get('b1b4')
                rule_b1b2 = rule.get('b1b2')
                
                b1b4_match = (rule_b1b4 == '*' or rule_b1b4 == b1b4)
                b1b2_match = (rule_b1b2 == '*' or rule_b1b2 == b1b2)
                
                if b1b4_match and b1b2_match:
                    return rule.get('final', default)
            
            return default
        
        combined['final_status'] = combined.apply(get_final_status, axis=1)
        
        self.log_step("combine_status", "ok", "Combined B1↔B4 and B1↔B2 statuses")
        
        return combined
    
    def build_a1_dataframe(
        self,
        b1_df: pd.DataFrame,
        b4_df: pd.DataFrame,
        b2_df: pd.DataFrame,
        match_results: pd.DataFrame,
        output_config: Dict[str, Any]
    ) -> pd.DataFrame:
        """
        Build A1 result DataFrame by selecting columns from B1, B4, B2
        
        Args:
            b1_df: Original B1 DataFrame
            b4_df: Original B4 DataFrame
            b2_df: Original B2 DataFrame
            match_results: Combined match results with final_status
            output_config: Output column configuration
        
        Returns:
            A1 DataFrame with selected columns
        """
        columns_config = output_config.get('columns', [])
        
        if not columns_config:
            logger.warning("No columns_config provided for A1 output, using default columns from B1")
            # Fallback: use all B1 columns + status columns
            columns_config = []
            for col in b1_df.columns:
                columns_config.append({
                    'name': col,
                    'source': 'B1',
                    'column': col
                })
            # Add system columns
            columns_config.append({'name': 'match_status', 'source': '_SYSTEM', 'column': 'status'})
            columns_config.append({'name': 'final_status', 'source': '_SYSTEM', 'column': 'final_status'})
        
        logger.info(f"Building A1 with {len(columns_config)} columns, match_results has {len(match_results)} rows")
        logger.info(f"B1 columns: {list(b1_df.columns)}, B1 index range: {b1_df.index.min()}-{b1_df.index.max()}")
        
        a1_data = []
        
        for i, (_, result_row) in enumerate(match_results.iterrows()):
            b1_idx = result_row['b1_index']
            b4_idx = result_row.get('b4_index')
            
            # Get source rows
            b1_row = b1_df.loc[b1_idx] if b1_idx in b1_df.index else None
            b4_row = b4_df.loc[b4_idx] if b4_idx is not None and b4_idx in b4_df.index else None
            
            if i == 0:
                logger.info(f"First match: b1_idx={b1_idx}, b1_row is {'found' if b1_row is not None else 'None'}")
                if b1_row is not None:
                    logger.info(f"First B1 row sample: {dict(list(b1_row.items())[:3])}")
            
            # Find B2 row (from b1b2 matching if exists)
            b2_row = None
            if 'b2_index' in result_row and result_row.get('b2_index') is not None:
                b2_idx = result_row['b2_index']
                if b2_idx in b2_df.index:
                    b2_row = b2_df.loc[b2_idx]
            
            # Build output row
            output_row = {}
            
            for col_config in columns_config:
                col_name = col_config.get('name')
                source = col_config.get('source')
                source_col = col_config.get('column')
                default = col_config.get('default')
                
                if source == 'B1' and b1_row is not None:
                    # Use .get() for Series with proper default handling
                    val = b1_row.get(source_col)
                    output_row[col_name] = val if val is not None else default
                elif source == 'B4' and b4_row is not None:
                    val = b4_row.get(source_col)
                    output_row[col_name] = val if val is not None else default
                elif source == 'B4':
                    output_row[col_name] = default
                elif source == 'B2' and b2_row is not None:
                    val = b2_row.get(source_col)
                    output_row[col_name] = val if val is not None else default
                elif source == 'B2':
                    output_row[col_name] = default
                elif source == '_SYSTEM':
                    # System columns from match results
                    if source_col in result_row.index:
                        output_row[col_name] = result_row[source_col]
                    else:
                        # Column not found - use default
                        output_row[col_name] = default
                else:
                    output_row[col_name] = default
            
            a1_data.append(output_row)
        
        a1_df = pd.DataFrame(a1_data)
        self.log_step("build_a1", "ok", f"Built A1 with {len(a1_df)} rows and {len(a1_df.columns)} columns")
        
        return a1_df
    
    def build_a2_dataframe(
        self,
        b3_df: pd.DataFrame,
        a1_df: pd.DataFrame,
        match_results: pd.DataFrame,
        output_config: Dict[str, Any]
    ) -> pd.DataFrame:
        """
        Build A2 result DataFrame from B3↔A1 matching
        
        A2 contains B3 records that don't match A1 (NOT_FOUND status)
        B3 is the LEFT side (source of truth from partner)
        A1 is the RIGHT side (our reconciliation result)
        
        Args:
            b3_df: DataFrame B3 (partner feedback - LEFT)
            a1_df: DataFrame A1 (our result - RIGHT)
            match_results: Matching results with b3_index, a1_index, status
            output_config: Output column configuration
        
        Returns:
            A2 DataFrame with NOT_FOUND records from B3
        """
        if match_results.empty or b3_df.empty:
            return pd.DataFrame()
        
        columns_config = output_config.get('columns', [])
        
        # A2 = B3 records that are NOT_FOUND in A1
        # Filter only NOT_FOUND records
        not_found_results = match_results[match_results['status'] == 'NOT_FOUND']
        
        self.log_step("build_a2", "processing", 
            f"Building A2: total match_results={len(match_results)}, NOT_FOUND={len(not_found_results)}")
        
        a2_data = []
        
        for _, result_row in not_found_results.iterrows():
            # B3 is LEFT so index is b3_index
            b3_idx = result_row.get('b3_index')
            # A1 is RIGHT so index is a1_index (will be None for NOT_FOUND)
            a1_idx = result_row.get('a1_index')
            
            b3_row = b3_df.loc[b3_idx] if b3_idx is not None and b3_idx in b3_df.index else None
            a1_row = a1_df.loc[a1_idx] if a1_idx is not None and a1_idx in a1_df.index else None
            
            if b3_row is None:
                continue
            
            output_row = {}
            
            for col_config in columns_config:
                col_name = col_config.get('name')
                source = col_config.get('source')
                source_col = col_config.get('column')
                default = col_config.get('default')
                
                if source == 'B3' and b3_row is not None:
                    output_row[col_name] = b3_row.get(source_col, default)
                elif source == 'A1' and a1_row is not None:
                    output_row[col_name] = a1_row.get(source_col, default)
                elif source == '_SYSTEM':
                    if source_col in result_row.index:
                        output_row[col_name] = result_row[source_col]
                    else:
                        output_row[col_name] = default
                else:
                    output_row[col_name] = default
            
            a2_data.append(output_row)
        
        a2_df = pd.DataFrame(a2_data)
        self.log_step("build_a2", "ok", f"Built A2 with {len(a2_df)} NOT_FOUND rows from B3")
        
        return a2_df
    
    def get_summary_stats(self, a1_df: pd.DataFrame) -> Dict[str, int]:
        """
        Calculate summary statistics from A1 result
        """
        stats = {
            'total_b1': len(a1_df),
            'matched': 0,
            'not_found': 0,
            'mismatch': 0,
            'refunded': 0,
            'other': 0
        }
        
        if 'final_status' in a1_df.columns:
            status_counts = a1_df['final_status'].value_counts().to_dict()
            
            stats['matched'] = status_counts.get('OK', 0) + status_counts.get('MATCHED', 0)
            stats['not_found'] = status_counts.get('NOT_IN_SYSTEM', 0) + status_counts.get('NOT_FOUND', 0)
            stats['mismatch'] = status_counts.get('AMOUNT_ERROR', 0) + status_counts.get('MISMATCH', 0)
            stats['refunded'] = status_counts.get('REFUNDED', 0)
            
            counted = stats['matched'] + stats['not_found'] + stats['mismatch'] + stats['refunded']
            stats['other'] = len(a1_df) - counted
        
        return stats

    def run_full_reconciliation(
        self,
        df_b1: pd.DataFrame,
        df_b4: pd.DataFrame,
        df_b2: Optional[pd.DataFrame] = None,
        df_b3: Optional[pd.DataFrame] = None,
        matching_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Run full reconciliation workflow:
        1. Match B1 with B4
        2. Match B1 with B2 (if B2 provided)
        3. Match A1 with B3 (if B3 provided)
        4. Build A1 (matched results) and A2 (unmatched)
        
        Args:
            df_b1: Bank statement data (required)
            df_b4: System data from database (required)
            df_b2: Additional data source (optional)
            df_b3: Third data source for verification (optional)
            matching_config: Matching rules configuration
            
        Returns:
            Dict with a1_df, a2_df, summary_stats, step_logs
        """
        self.log_step("reconciliation_start", "ok", f"Starting reconciliation with B1={len(df_b1)} rows, B4={len(df_b4)} rows")
        
        # Default matching config if not provided
        if matching_config is None:
            matching_config = {
                "b1_b4": {
                    "type": "expression",
                    "rules": [
                        {
                            "name": "match_by_txn_id",
                            "match_expression": "B1['transaction_id'] == B4['transaction_id']",
                            "match_status": "MATCHED"
                        }
                    ]
                }
            }
        
        # Ensure df_b2 is a DataFrame (empty if None)
        if df_b2 is None:
            df_b2 = pd.DataFrame()
        
        # Ensure df_b3 is a DataFrame (empty if None)
        if df_b3 is None:
            df_b3 = pd.DataFrame()
        
        try:
            # Step 1: Match B1 with B4
            self.log_step("match_b1_b4", "processing", "Matching B1 with B4...")
            b1_b4_config = matching_config.get("b1_b4", {})
            match_result_b1_b4 = self.match_b1_b4(df_b1, df_b4, b1_b4_config)
            self.log_step("match_b1_b4", "ok", f"B1-B4 matching complete: {len(match_result_b1_b4)} rows")
            
            # Step 2: Match with B2 (always call, even if B2 is empty)
            self.log_step("match_b1_b2", "processing", f"Matching with B2 ({len(df_b2)} rows)...")
            b1_b2_config = matching_config.get("b1_b2", {})
            match_result_b1_b2 = self.match_b1_b2(df_b1, df_b2, b1_b2_config)
            self.log_step("match_b1_b2", "ok", "B1-B2 matching complete")
            
            # Step 3: Combine statuses
            self.log_step("combine_status", "processing", "Combining match statuses...")
            combine_rules = matching_config.get("status_combine", {})
            combined_result = self.combine_statuses(match_result_b1_b4, match_result_b1_b2, combine_rules)
            self.log_step("combine_status", "ok", "Status combination complete")
            
            # Step 4: Build A1 DataFrame (simplified - use combined result directly)
            self.log_step("build_a1", "processing", "Building A1 result...")
            output_config = matching_config.get("output_columns", {})
            
            # Build A1 with all source data
            a1_df = self.build_a1_dataframe(df_b1, df_b4, df_b2, combined_result, output_config)
            self.log_step("build_a1", "ok", f"A1 built with {len(a1_df)} rows")
            
            # Step 5: Match B3 with A1 if B3 provided
            # B3 is LEFT (partner feedback), A1 is RIGHT (our result)
            # This finds B3 transactions that exist/don't exist in our system
            match_result_b3_a1 = pd.DataFrame()
            if not df_b3.empty:
                self.log_step("match_b3_a1", "processing", f"Matching B3 ({len(df_b3)} rows) with A1 ({len(a1_df)} rows)...")
                b3_a1_config = matching_config.get("a1_b3", {})  # Config still uses a1_b3 key
                match_result_b3_a1 = self.match_b3_a1(df_b3, a1_df, b3_a1_config)
                self.log_step("match_b3_a1", "ok", "B3-A1 matching complete")
            
            # Step 6: Build A2 (B3 records NOT_FOUND in A1)
            self.log_step("build_a2", "processing", "Building A2 (B3 NOT_FOUND records)...")
            a2_config = matching_config.get("a2_output", {})
            
            if not df_b3.empty and not match_result_b3_a1.empty:
                # B3 is LEFT, A1 is RIGHT
                a2_df = self.build_a2_dataframe(df_b3, a1_df, match_result_b3_a1, a2_config)
            else:
                # Fallback: A2 = records from A1 that are not OK/MATCHED
                if 'final_status' in a1_df.columns:
                    a2_df = a1_df[~a1_df['final_status'].isin(['OK', 'MATCHED'])].copy()
                else:
                    a2_df = pd.DataFrame()
            self.log_step("build_a2", "ok", f"A2 built with {len(a2_df)} rows")
            
            # Step 7: Calculate summary statistics
            summary_stats = self.get_summary_stats(a1_df)
            summary_stats['total_b4'] = len(df_b4)
            summary_stats['total_a1'] = len(a1_df)
            summary_stats['total_a2'] = len(a2_df)
            
            # Add detailed matching stats by step - ALWAYS create this structure
            matching_stats = {
                'b1_b4': {'total': 0, 'matched': 0, 'not_found': 0, 'mismatch': 0},
                'b1_b2': {'total': 0, 'matched': 0, 'not_found': 0, 'mismatch': 0},
                'b3_a1': {'total': 0, 'matched': 0, 'not_found': 0}
            }
            
            # B1↔B4 matching stats
            if not match_result_b1_b4.empty:
                self.log_step("calc_stats", "processing", f"B1B4 result columns: {list(match_result_b1_b4.columns)}")
                if 'status' in match_result_b1_b4.columns:
                    b1b4_counts = match_result_b1_b4['status'].value_counts().to_dict()
                    matching_stats['b1_b4'] = {
                        'total': len(match_result_b1_b4),
                        'matched': b1b4_counts.get('MATCHED', 0),
                        'not_found': b1b4_counts.get('NOT_FOUND', 0),
                        'mismatch': b1b4_counts.get('MISMATCH', 0)
                    }
                    self.log_step("calc_stats", "ok", f"B1B4 stats: {matching_stats['b1_b4']}")
            
            # B1↔B2 matching stats
            if not match_result_b1_b2.empty and 'status' in match_result_b1_b2.columns:
                b1b2_counts = match_result_b1_b2['status'].value_counts().to_dict()
                matching_stats['b1_b2'] = {
                    'total': len(match_result_b1_b2),
                    'matched': b1b2_counts.get('MATCHED', 0),
                    'not_found': b1b2_counts.get('NOT_FOUND', 0),
                    'mismatch': b1b2_counts.get('MISMATCH', 0)
                }
            
            # B3↔A1 matching stats (to generate A2)
            if not match_result_b3_a1.empty and 'status' in match_result_b3_a1.columns:
                b3a1_counts = match_result_b3_a1['status'].value_counts().to_dict()
                matching_stats['b3_a1'] = {
                    'total': len(match_result_b3_a1),
                    'matched': b3a1_counts.get('MATCHED', 0),
                    'not_found': b3a1_counts.get('NOT_FOUND', 0)
                }
            
            summary_stats['matching_stats'] = matching_stats
            self.log_step("calc_stats", "ok", f"Final matching_stats: {matching_stats}")
            
            self.log_step("reconciliation_complete", "ok", 
                f"Reconciliation complete: matched={summary_stats['matched']}, "
                f"not_found={summary_stats['not_found']}, mismatch={summary_stats['mismatch']}")
            
            return {
                "a1_df": a1_df,
                "a2_df": a2_df,
                "summary_stats": summary_stats,
                "step_logs": self.step_logs
            }
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"Reconciliation failed: {str(e)}")
            logger.error(f"Full traceback:\n{error_trace}")
            self.log_step("reconciliation_error", "error", f"{str(e)}\n{error_trace}")
            raise MatchingError(f"Reconciliation failed: {str(e)}")
