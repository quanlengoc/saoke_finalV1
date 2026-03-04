"""
String transform utilities for matching rules
"""

import re
from typing import Any, List, Dict, Callable, Optional
import pandas as pd


# ============================================================================
# Transform Functions
# ============================================================================

def transform_trim(value: Any) -> Any:
    """Trim whitespace from string"""
    if isinstance(value, str):
        return value.strip()
    return value


def transform_uppercase(value: Any) -> Any:
    """Convert to uppercase"""
    if isinstance(value, str):
        return value.upper()
    return value


def transform_lowercase(value: Any) -> Any:
    """Convert to lowercase"""
    if isinstance(value, str):
        return value.lower()
    return value


def transform_remove_prefix(value: Any, prefix: str) -> Any:
    """Remove prefix from string"""
    if isinstance(value, str) and value.startswith(prefix):
        return value[len(prefix):]
    return value


def transform_remove_suffix(value: Any, suffix: str) -> Any:
    """Remove suffix from string"""
    if isinstance(value, str) and value.endswith(suffix):
        return value[:-len(suffix)]
    return value


def transform_substring(value: Any, start: int, end: Optional[int] = None) -> Any:
    """Extract substring"""
    if isinstance(value, str):
        return value[start:end]
    return value


def transform_replace(value: Any, old: str, new: str) -> Any:
    """Replace substring"""
    if isinstance(value, str):
        return value.replace(old, new)
    return value


def transform_regex_extract(value: Any, pattern: str) -> Any:
    """Extract first regex match"""
    if isinstance(value, str):
        match = re.search(pattern, value)
        if match:
            return match.group(1) if match.groups() else match.group(0)
    return value


def transform_lpad(value: Any, width: int, fillchar: str = '0') -> Any:
    """Left pad string"""
    if value is not None:
        return str(value).rjust(width, fillchar)
    return value


def transform_rpad(value: Any, width: int, fillchar: str = '0') -> Any:
    """Right pad string"""
    if value is not None:
        return str(value).ljust(width, fillchar)
    return value


def transform_to_string(value: Any) -> str:
    """Convert value to string"""
    if value is None:
        return ''
    return str(value)


def transform_to_float(value: Any) -> float:
    """Convert value to float"""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def normalize_number_string(value: Any, thousand_sep: str = ',', decimal_sep: str = '.') -> str:
    """
    Normalize a number string by removing thousand separators and standardizing decimal separator.
    
    Args:
        value: The value to normalize
        thousand_sep: The character used as thousand separator (',' or '.' or '')
        decimal_sep: The character used as decimal separator ('.' or ',' or '')
    
    Examples with thousand_sep=',' decimal_sep='.':
        "1,000" -> "1000"
        "1,000.50" -> "1000.50"
        
    Examples with thousand_sep='.' decimal_sep=',':
        "1.000" -> "1000"
        "1.000,50" -> "1000.50"
    """
    if value is None:
        return '0'
    
    s = str(value).strip()
    if not s:
        return '0'
    
    # Remove currency symbols and spaces
    s = re.sub(r'[^\d,.\-]', '', s)
    
    if not s:
        return '0'
    
    # If both separators are the same or one is empty, handle accordingly
    if thousand_sep and thousand_sep in s:
        s = s.replace(thousand_sep, '')
    
    if decimal_sep and decimal_sep != '.' and decimal_sep in s:
        s = s.replace(decimal_sep, '.')
    
    return s if s else '0'


def transform_normalize_number(value: Any, thousand_sep: str = ',', decimal_sep: str = '.') -> float:
    """
    Normalize a number from various formats and convert to float.
    
    Args:
        value: The value to normalize
        thousand_sep: The character used as thousand separator
        decimal_sep: The character used as decimal separator
    """
    try:
        normalized = normalize_number_string(value, thousand_sep, decimal_sep)
        return float(normalized)
    except (ValueError, TypeError):
        return 0.0


def extract_amount_from_string(value: Any) -> str:
    """
    Extract the first amount-like number from a string.
    
    Looks for patterns like:
    - "20,000" or "20.000" (with thousand separators)
    - "1,234,567" or "1.234.567" (multiple thousand separators)
    - "20,000.50" or "20.000,50" (with decimals)
    - Plain numbers like "20000" or "20000.50"
    
    Example: "TOPUP 20,000 cho so dt 0942257882" -> "20,000"
    
    Priority: Numbers with thousand separators first, then plain numbers.
    Avoids phone numbers (10+ consecutive digits without separators).
    """
    if value is None:
        return '0'
    
    s = str(value).strip()
    if not s:
        return '0'
    
    # Pattern 1: Numbers with thousand separators (highest priority)
    # Matches: 1,000 or 1.000 or 1,000,000 or 1.000.000 or 1,000.50 or 1.000,50
    pattern_with_sep = r'\d{1,3}(?:[,\.]\d{3})+(?:[,\.]\d{1,2})?'
    match = re.search(pattern_with_sep, s)
    if match:
        return match.group(0)
    
    # Pattern 2: Decimal numbers (e.g., 20.50, 100.5)
    pattern_decimal = r'\d+[,\.]\d{1,2}(?!\d)'
    match = re.search(pattern_decimal, s)
    if match:
        return match.group(0)
    
    # Pattern 3: Plain numbers but NOT phone numbers (avoid 10+ digits)
    # Find all number sequences
    all_numbers = re.findall(r'\d+', s)
    for num in all_numbers:
        # Skip if looks like phone number (10+ digits)
        if len(num) >= 10:
            continue
        # Return first reasonable number (less than 10 digits)
        if len(num) <= 9:
            return num
    
    # Fallback: return first number found
    match = re.search(r'\d+', s)
    if match:
        return match.group(0)
    
    return '0'


def transform_extract_amount(value: Any) -> str:
    """
    Extract amount from text and return as normalized number string.
    
    Example: "TOPUP 20,000 cho so dt 0942257882" -> "20000"
    """
    extracted = extract_amount_from_string(value)
    return normalize_number_string(extracted)


def transform_to_int(value: Any) -> int:
    """Convert value to integer"""
    if value is None:
        return 0
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return 0


def normalize_number_series_vectorized(series: pd.Series, thousand_sep: str = ',', decimal_sep: str = '.') -> pd.Series:
    """
    VECTORIZED version - FAST for millions of rows!
    Normalize number strings in a pandas Series using vectorized operations.
    
    This is 10-100x FASTER than .apply(lambda) for large datasets!
    
    Args:
        series: Pandas Series containing number strings
        thousand_sep: Thousand separator character (',' or '.' or '')
        decimal_sep: Decimal separator character ('.' or ',' or '')
    
    Returns:
        Pandas Series with normalized floats
    
    Performance:
        - 1M rows with .apply(lambda): ~10-30 seconds
        - 1M rows vectorized: ~0.5-2 seconds
    """
    # Convert to string, handle nulls
    result = series.fillna('0').astype(str).str.strip()
    
    # Remove currency symbols, spaces, and keep only digits, commas, dots, minus
    result = result.str.replace(r'[^\d,.\-]', '', regex=True)
    
    # Remove thousand separators if specified
    if thousand_sep and thousand_sep != '':
        result = result.str.replace(thousand_sep, '', regex=False)
    
    # Replace decimal separator with standard dot if needed
    if decimal_sep and decimal_sep != '.' and decimal_sep != '':
        result = result.str.replace(decimal_sep, '.', regex=False)
    
    # Replace empty strings with '0'
    result = result.replace('', '0')
    
    # Convert to numeric (float), coerce errors to NaN, then fillna with 0
    return pd.to_numeric(result, errors='coerce').fillna(0.0)


# ============================================================================
# Transform Registry
# ============================================================================

TRANSFORMS: Dict[str, Callable] = {
    'trim': transform_trim,
    'uppercase': transform_uppercase,
    'lowercase': transform_lowercase,
    'to_string': transform_to_string,
    'to_float': transform_to_float,
    'to_int': transform_to_int,
    'normalize_number': transform_normalize_number,
    'extract_amount': transform_extract_amount,
}

TRANSFORMS_WITH_PARAMS: Dict[str, Callable] = {
    'remove_prefix': transform_remove_prefix,
    'remove_suffix': transform_remove_suffix,
    'substring': transform_substring,
    'replace': transform_replace,
    'regex_extract': transform_regex_extract,
    'lpad': transform_lpad,
    'rpad': transform_rpad,
}


# ============================================================================
# Apply Transforms
# ============================================================================

def apply_transform(value: Any, transform: Any) -> Any:
    """
    Apply a single transform to a value
    
    Args:
        value: Value to transform
        transform: Transform name (str) or dict with params
    
    Returns:
        Transformed value
    """
    if isinstance(transform, str):
        # Simple transform without params
        if transform in TRANSFORMS:
            return TRANSFORMS[transform](value)
    elif isinstance(transform, dict):
        # Transform with parameters
        for transform_name, params in transform.items():
            if transform_name in TRANSFORMS_WITH_PARAMS:
                if isinstance(params, (list, tuple)):
                    return TRANSFORMS_WITH_PARAMS[transform_name](value, *params)
                else:
                    return TRANSFORMS_WITH_PARAMS[transform_name](value, params)
            elif transform_name in TRANSFORMS:
                return TRANSFORMS[transform_name](value)
    
    return value


def apply_transforms(value: Any, transforms: List[Any]) -> Any:
    """
    Apply a list of transforms to a value
    
    Args:
        value: Value to transform
        transforms: List of transform names or dicts
    
    Returns:
        Transformed value
    """
    result = value
    for transform in transforms:
        result = apply_transform(result, transform)
    return result


def apply_transforms_to_series(series: pd.Series, transforms: List[Any]) -> pd.Series:
    """
    Apply transforms to a pandas Series
    
    Args:
        series: Pandas Series
        transforms: List of transforms
    
    Returns:
        Transformed Series
    """
    result = series.copy()
    
    for transform in transforms:
        if isinstance(transform, str):
            if transform == 'trim':
                result = result.astype(str).str.strip()
            elif transform == 'uppercase':
                result = result.astype(str).str.upper()
            elif transform == 'lowercase':
                result = result.astype(str).str.lower()
            elif transform == 'to_string':
                result = result.astype(str)
            elif transform == 'to_float':
                result = pd.to_numeric(result, errors='coerce').fillna(0.0)
            elif transform == 'to_int':
                result = pd.to_numeric(result, errors='coerce').fillna(0).astype(int)
            elif transform == 'normalize_number':
                # Apply normalize_number_string with default params
                result = result.apply(lambda x: normalize_number_string(x, ',', '.')).astype(float)
            elif transform == 'extract_amount':
                # Extract amount from text and normalize
                result = result.apply(transform_extract_amount)
        elif isinstance(transform, dict):
            for transform_name, params in transform.items():
                if transform_name == 'normalize_number':
                    # normalize_number with explicit params
                    thousand_sep = params.get('thousandSeparator', ',') if isinstance(params, dict) else ','
                    decimal_sep = params.get('decimalSeparator', '.') if isinstance(params, dict) else '.'
                    result = result.apply(lambda x: normalize_number_string(x, thousand_sep, decimal_sep)).astype(float)
                elif transform_name == 'remove_prefix':
                    prefix = params if isinstance(params, str) else params[0]
                    result = result.astype(str).str.lstrip(prefix)
                elif transform_name == 'remove_suffix':
                    suffix = params if isinstance(params, str) else params[0]
                    result = result.astype(str).str.rstrip(suffix)
                elif transform_name == 'substring':
                    if isinstance(params, (list, tuple)):
                        start, end = params[0], params[1] if len(params) > 1 else None
                    else:
                        start, end = params, None
                    result = result.astype(str).str.slice(start, end)
                elif transform_name == 'replace':
                    old, new = params if isinstance(params, (list, tuple)) else (params, '')
                    result = result.astype(str).str.replace(old, new, regex=False)
                elif transform_name == 'regex_extract':
                    pattern = params if isinstance(params, str) else params[0]
                    result = result.astype(str).str.extract(pattern, expand=False)
    
    return result


def concat_columns(df: pd.DataFrame, columns: List[str], separator: str = '') -> pd.Series:
    """
    Concatenate multiple columns into one
    
    Args:
        df: DataFrame
        columns: List of column names
        separator: Separator between values
    
    Returns:
        Concatenated Series
    """
    if not columns:
        return pd.Series([''] * len(df))
    
    result = df[columns[0]].astype(str)
    for col in columns[1:]:
        result = result + separator + df[col].astype(str)
    
    return result
