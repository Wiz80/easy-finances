"""
SQL Validator Service.

Validates SQL queries for security before execution.
"""

import re
from dataclasses import dataclass, field

import sqlparse


@dataclass
class ValidationResult:
    """Result of SQL validation."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class SQLValidator:
    """
    SQL security validator.
    
    Ensures only safe SELECT queries are executed.
    """

    # Keywords that are never allowed
    FORBIDDEN_KEYWORDS = [
        "DROP",
        "DELETE",
        "UPDATE",
        "INSERT",
        "TRUNCATE",
        "ALTER",
        "CREATE",
        "GRANT",
        "REVOKE",
        "EXECUTE",
        "EXEC",
        "CALL",
        "SET",
        "COPY",
        "VACUUM",
        "REINDEX",
        "CLUSTER",
        "LOCK",
        "UNLISTEN",
        "NOTIFY",
        "LISTEN",
    ]

    # Patterns that indicate potential SQL injection
    DANGEROUS_PATTERNS = [
        r";\s*--",  # Comment after semicolon
        r";\s*\/\*",  # Block comment after semicolon
        r";\s*(DROP|DELETE|UPDATE|INSERT)",  # Multiple statements
        r"UNION\s+ALL\s+SELECT",  # Union injection
        r"OR\s+1\s*=\s*1",  # Always true condition
        r"OR\s+'[^']*'\s*=\s*'[^']*'",  # String always true
        r"--\s*$",  # Trailing comment
    ]

    def __init__(self, require_user_id: bool = True):
        """
        Initialize validator.
        
        Args:
            require_user_id: If True, queries must contain user_id filter
        """
        self.require_user_id = require_user_id

    def validate(self, sql: str) -> ValidationResult:
        """
        Validate a SQL query.
        
        Args:
            sql: SQL query string
            
        Returns:
            ValidationResult with errors and warnings
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Clean and normalize
        sql_clean = sql.strip()
        sql_upper = sql_clean.upper()

        # Check if empty
        if not sql_clean:
            errors.append("SQL query is empty")
            return ValidationResult(valid=False, errors=errors)

        # Parse SQL
        try:
            parsed = sqlparse.parse(sql_clean)
            if not parsed:
                errors.append("Failed to parse SQL")
                return ValidationResult(valid=False, errors=errors)
        except Exception as e:
            errors.append(f"SQL parsing error: {str(e)}")
            return ValidationResult(valid=False, errors=errors)

        # Check statement count (only one statement allowed)
        statements = [s for s in parsed if s.get_type() != "UNKNOWN" or str(s).strip()]
        if len(statements) > 1:
            errors.append("Multiple SQL statements not allowed")

        # Check statement type
        if statements:
            stmt_type = statements[0].get_type()
            if stmt_type != "SELECT":
                errors.append(f"Only SELECT statements allowed, got: {stmt_type}")

        # Must start with SELECT
        if not sql_upper.lstrip().startswith("SELECT"):
            errors.append("Query must start with SELECT")

        # Check for forbidden keywords
        for keyword in self.FORBIDDEN_KEYWORDS:
            # Use word boundary to avoid false positives
            pattern = rf"\b{keyword}\b"
            if re.search(pattern, sql_upper):
                errors.append(f"Forbidden keyword: {keyword}")

        # Check for dangerous patterns
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, sql_upper, re.IGNORECASE):
                errors.append(f"Dangerous pattern detected")
                break

        # Check for user_id filter
        if self.require_user_id:
            if "user_id" not in sql.lower():
                errors.append("Query must filter by user_id")

        # Warnings (non-blocking)
        if "SELECT *" in sql_upper:
            warnings.append("Consider selecting specific columns instead of *")

        if "LIMIT" not in sql_upper:
            warnings.append("Query has no LIMIT clause")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def inject_user_id(self, sql: str, user_id: str) -> str:
        """
        Ensure user_id filter is present in the query.
        
        If user_id placeholder exists, return as-is.
        Otherwise, try to add it to WHERE clause.
        
        Args:
            sql: SQL query
            user_id: User ID to inject
            
        Returns:
            SQL with user_id filter
        """
        sql_lower = sql.lower()

        # Check if already has user_id placeholder
        if ":user_id" in sql_lower or "%(user_id)" in sql_lower:
            return sql

        # Check if already has user_id with value
        if f"user_id = '{user_id}'" in sql_lower:
            return sql

        # Try to add WHERE clause with user_id
        # This is a simple implementation - complex queries may need manual handling
        if "where" in sql_lower:
            # Add to existing WHERE
            where_idx = sql_lower.find("where")
            before = sql[:where_idx + 5]  # Include 'WHERE'
            after = sql[where_idx + 5:]
            return f"{before} user_id = :user_id AND {after.strip()}"
        else:
            # No WHERE clause - need to find appropriate place
            # Look for GROUP BY, ORDER BY, LIMIT
            insert_before = None
            for keyword in ["group by", "order by", "limit", ";"]:
                idx = sql_lower.find(keyword)
                if idx != -1:
                    insert_before = idx
                    break

            if insert_before:
                before = sql[:insert_before].rstrip()
                after = sql[insert_before:]
                return f"{before} WHERE user_id = :user_id {after}"
            else:
                return f"{sql.rstrip()} WHERE user_id = :user_id"

    def enforce_limit(self, sql: str, max_limit: int = 1000) -> str:
        """
        Ensure query has a LIMIT clause.
        
        Args:
            sql: SQL query
            max_limit: Maximum allowed limit
            
        Returns:
            SQL with LIMIT clause
        """
        sql_upper = sql.upper()

        if "LIMIT" in sql_upper:
            # Extract and validate existing limit
            match = re.search(r"LIMIT\s+(\d+)", sql_upper)
            if match:
                existing_limit = int(match.group(1))
                if existing_limit > max_limit:
                    # Replace with max limit
                    sql = re.sub(
                        r"LIMIT\s+\d+",
                        f"LIMIT {max_limit}",
                        sql,
                        flags=re.IGNORECASE,
                    )
            return sql
        else:
            # Add LIMIT clause
            sql = sql.rstrip().rstrip(";")
            return f"{sql} LIMIT {max_limit}"

