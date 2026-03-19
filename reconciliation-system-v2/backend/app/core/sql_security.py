"""
SQL Security Module — Defense-in-Depth

Multi-layer protection against SQL injection and unauthorized operations:

Layer 1: Statement Classification — only SELECT allowed
Layer 2: Dangerous Pattern Detection — block subqueries with DML, unions with DML, etc.
Layer 3: Parameter Sanitization — validate params contain no SQL fragments
Layer 4: Table Name Validation — whitelist pattern for temp table names
Layer 5: Audit Logging — log all SQL executions for review

Usage:
    from app.core.sql_security import SqlGuard

    # Validate before execution
    SqlGuard.validate_query(sql)           # raises SqlSecurityError if unsafe
    SqlGuard.validate_params(params)       # raises SqlSecurityError if params contain SQL
    SqlGuard.validate_table_name(name)     # raises SqlSecurityError if invalid
    SqlGuard.sanitize_and_log(sql, context)  # validate + audit log
"""

import re
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger('security')


class SqlSecurityError(Exception):
    """Raised when SQL validation fails"""

    def __init__(self, message: str, sql: str = "", violation_type: str = ""):
        self.sql = sql
        self.violation_type = violation_type
        super().__init__(message)


# ============================================================================
# Constants
# ============================================================================

# DML/DDL keywords that should NEVER appear as primary statement
_BLOCKED_STATEMENTS = re.compile(
    r'^\s*'
    r'(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|REPLACE|MERGE|'
    r'GRANT|REVOKE|EXEC|EXECUTE|CALL|BEGIN|DECLARE|SET|COMMIT|ROLLBACK|SAVEPOINT)',
    re.IGNORECASE | re.MULTILINE
)

# Dangerous patterns inside any SQL (even inside SELECT)
_DANGEROUS_PATTERNS = [
    # DML hidden inside subqueries or CTEs
    (re.compile(r'\b(INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM)\b', re.IGNORECASE),
     "DML statement detected (INSERT/UPDATE/DELETE)"),

    # DDL operations
    (re.compile(r'\b(DROP\s+(TABLE|VIEW|INDEX|DATABASE|SCHEMA)|'
                r'ALTER\s+(TABLE|VIEW|INDEX|DATABASE|SCHEMA)|'
                r'TRUNCATE\s+TABLE|'
                r'CREATE\s+(TABLE|VIEW|INDEX|DATABASE|SCHEMA|OR\s+REPLACE))\b', re.IGNORECASE),
     "DDL statement detected (DROP/ALTER/TRUNCATE/CREATE)"),

    # System/admin operations
    (re.compile(r'\b(GRANT\s|REVOKE\s|EXEC\s|EXECUTE\s|CALL\s)', re.IGNORECASE),
     "System/admin operation detected"),

    # Oracle-specific dangerous patterns
    (re.compile(r'\b(DBMS_|UTL_|SYS\.|DBA_)', re.IGNORECASE),
     "Oracle system package access detected"),

    # Transaction control (should not be in SELECT queries)
    (re.compile(r'\b(COMMIT|ROLLBACK|SAVEPOINT|BEGIN\s+TRANSACTION)\b', re.IGNORECASE),
     "Transaction control detected"),

    # Stacked queries (multiple statements via semicolon)
    (re.compile(r';\s*(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|EXEC|GRANT|REVOKE)',
                re.IGNORECASE),
     "Stacked query with dangerous statement detected"),

    # Comment-based injection patterns
    (re.compile(r'(--|/\*)\s*(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE)', re.IGNORECASE),
     "Suspicious comment pattern detected"),

    # UNION-based injection with DML
    (re.compile(r'UNION\s+(ALL\s+)?SELECT\s+.*\s+INTO\s+', re.IGNORECASE),
     "UNION SELECT INTO detected"),

    # File operations (Oracle/MySQL)
    (re.compile(r'\b(LOAD_FILE|INTO\s+(OUT|DUMP)FILE|UTL_FILE)\b', re.IGNORECASE),
     "File operation detected"),
]

# Pattern for safe table names (only alphanumeric + underscore, with optional prefix)
_SAFE_TABLE_NAME = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]{0,127}$')

# Pattern for safe SQL parameter values
_PARAM_INJECTION_PATTERNS = [
    re.compile(r';\s*(DROP|DELETE|INSERT|UPDATE|ALTER|TRUNCATE|CREATE|EXEC)', re.IGNORECASE),
    re.compile(r'(--|/\*|#)\s*(DROP|DELETE|INSERT|UPDATE)', re.IGNORECASE),
    re.compile(r"('\s*(OR|AND)\s+'?\d*'?\s*=\s*'?\d*)", re.IGNORECASE),  # ' OR '1'='1
    re.compile(r"(UNION\s+(ALL\s+)?SELECT)", re.IGNORECASE),
]


class SqlGuard:
    """
    Central SQL security validator.
    All SQL execution paths MUST go through this guard.
    """

    @staticmethod
    def validate_query(sql: str, context: str = "unknown") -> None:
        """
        Validate SQL query is safe to execute.
        Only SELECT (and WITH/CTE → SELECT) are allowed.

        Args:
            sql: The SQL query string
            context: Description of where this SQL comes from (for logging)

        Raises:
            SqlSecurityError: If the query is not safe
        """
        if not sql or not sql.strip():
            raise SqlSecurityError("Empty SQL query", sql=sql, violation_type="empty")

        # Strip leading SQL comments (-- and /* */) to find the actual statement
        cleaned = sql.strip()
        while cleaned.startswith('--') or cleaned.startswith('/*'):
            if cleaned.startswith('--'):
                # Single-line comment: skip to end of line
                newline = cleaned.find('\n')
                cleaned = cleaned[newline + 1:].strip() if newline >= 0 else ''
            elif cleaned.startswith('/*'):
                # Block comment: skip to */
                end = cleaned.find('*/')
                cleaned = cleaned[end + 2:].strip() if end >= 0 else ''
        if not cleaned:
            raise SqlSecurityError("SQL contains only comments", sql=sql, violation_type="empty")

        # Layer 1: Statement type — must be SELECT or WITH (CTE)
        if not re.match(r'^\s*(SELECT|WITH)\b', cleaned, re.IGNORECASE):
            match = _BLOCKED_STATEMENTS.match(cleaned)
            stmt_type = match.group(1) if match else cleaned.split()[0]
            logger.warning(
                f"[SQL_SECURITY] BLOCKED non-SELECT statement | context={context} | "
                f"type={stmt_type} | sql={cleaned[:200]}"
            )
            raise SqlSecurityError(
                f"Only SELECT queries are allowed. Got: {stmt_type}",
                sql=sql,
                violation_type="blocked_statement"
            )

        # Layer 2: Dangerous patterns inside the query
        for pattern, description in _DANGEROUS_PATTERNS:
            if pattern.search(cleaned):
                logger.warning(
                    f"[SQL_SECURITY] BLOCKED dangerous pattern | context={context} | "
                    f"pattern={description} | sql={cleaned[:200]}"
                )
                raise SqlSecurityError(
                    f"Dangerous SQL pattern detected: {description}",
                    sql=sql,
                    violation_type="dangerous_pattern"
                )

        # Layer 3: Multiple statements (semicolons followed by another statement)
        # Allow semicolons at end of query, but not in middle
        statements = [s.strip() for s in cleaned.rstrip(';').split(';') if s.strip()]
        if len(statements) > 1:
            logger.warning(
                f"[SQL_SECURITY] BLOCKED multiple statements | context={context} | "
                f"count={len(statements)} | sql={cleaned[:200]}"
            )
            raise SqlSecurityError(
                "Multiple SQL statements are not allowed",
                sql=sql,
                violation_type="multiple_statements"
            )

    @staticmethod
    def validate_params(params: Dict[str, Any], context: str = "unknown") -> None:
        """
        Validate SQL parameters don't contain injection attempts.

        Args:
            params: Dictionary of parameter name → value
            context: Description for logging

        Raises:
            SqlSecurityError: If any parameter looks like SQL injection
        """
        if not params:
            return

        for key, value in params.items():
            if not isinstance(value, str):
                continue

            for pattern in _PARAM_INJECTION_PATTERNS:
                if pattern.search(value):
                    logger.warning(
                        f"[SQL_SECURITY] BLOCKED suspicious param | context={context} | "
                        f"param={key} | value={value[:100]}"
                    )
                    raise SqlSecurityError(
                        f"Parameter '{key}' contains suspicious SQL pattern",
                        sql=f"param[{key}]={value[:100]}",
                        violation_type="param_injection"
                    )

    @staticmethod
    def validate_table_name(table_name: str, context: str = "unknown") -> None:
        """
        Validate table name is safe (alphanumeric + underscore only).

        Args:
            table_name: The table name to validate
            context: Description for logging

        Raises:
            SqlSecurityError: If table name is not safe
        """
        if not table_name:
            raise SqlSecurityError("Empty table name", violation_type="invalid_table_name")

        if not _SAFE_TABLE_NAME.match(table_name):
            logger.warning(
                f"[SQL_SECURITY] BLOCKED unsafe table name | context={context} | "
                f"name={table_name[:100]}"
            )
            raise SqlSecurityError(
                f"Invalid table name: '{table_name}'. "
                f"Only alphanumeric characters and underscores are allowed.",
                violation_type="invalid_table_name"
            )

    @staticmethod
    def sanitize_and_log(sql: str, context: str, params: Dict[str, Any] = None) -> str:
        """
        Full validation pipeline + audit logging.
        Returns cleaned SQL (trimmed, trailing semicolons removed).

        Args:
            sql: The SQL query
            context: Where this SQL comes from
            params: Optional parameters to validate

        Returns:
            Cleaned SQL string

        Raises:
            SqlSecurityError: If any validation fails
        """
        # Validate query
        SqlGuard.validate_query(sql, context)

        # Validate params if provided
        if params:
            SqlGuard.validate_params(params, context)

        # Clean and return
        cleaned = sql.strip().rstrip(';').strip()

        # Audit log (INFO level — all executed queries are logged)
        sql_preview = cleaned[:300] + ('...' if len(cleaned) > 300 else '')
        logger.info(
            f"[SQL_AUDIT] ALLOWED | context={context} | "
            f"params={list((params or {}).keys())} | sql={sql_preview}"
        )

        return cleaned

    @staticmethod
    def validate_format_params(sql_template: str, params: Dict[str, Any],
                               context: str = "unknown") -> str:
        """
        Safe alternative to sql_template.format(**params).

        1. Validates each param value for injection
        2. Formats the template
        3. Validates the final SQL

        Args:
            sql_template: SQL template with {param_name} placeholders
            params: Parameters to substitute
            context: Description for logging

        Returns:
            Formatted and validated SQL

        Raises:
            SqlSecurityError: If any validation fails
        """
        # First validate params
        SqlGuard.validate_params(params, context)

        # Format the template
        try:
            sql = sql_template.format(**params)
        except KeyError as e:
            raise SqlSecurityError(
                f"Missing SQL parameter: {e}",
                sql=sql_template[:200],
                violation_type="missing_param"
            )

        # Validate the final formatted SQL
        return SqlGuard.sanitize_and_log(sql, context, params)
