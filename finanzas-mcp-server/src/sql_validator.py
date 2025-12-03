"""
SQL Validation for MCP Server.

Ensures only safe SELECT queries are executed.
"""

import re
from dataclasses import dataclass, field

import sqlparse
from sqlparse.tokens import DML, DDL, Keyword


# Forbidden SQL patterns
FORBIDDEN_PATTERNS: tuple[str, ...] = (
    r"\bCREATE\b",
    r"\bALTER\b",
    r"\bDROP\b",
    r"\bTRUNCATE\b",
    r"\bINSERT\b",
    r"\bUPDATE\b",
    r"\bDELETE\b",
    r"\bMERGE\b",
    r"\bGRANT\b",
    r"\bREVOKE\b",
    r"\bEXECUTE\b",
    r"\bCALL\b",
    r"--",
    r"/\*",
)

# Tables that require user_id filter
USER_SCOPED_TABLES: tuple[str, ...] = (
    "expense",
    "receipt",
    "trip",
    "budget",
    "account",
    "card",
)


class SQLValidationError(Exception):
    """Raised when SQL validation fails."""

    def __init__(self, message: str, sql: str, violations: list[str]) -> None:
        super().__init__(message)
        self.message = message
        self.sql = sql
        self.violations = violations


@dataclass
class SQLValidationResult:
    """Result of SQL validation."""

    valid: bool
    sql: str
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    has_user_id_filter: bool = False

    def __bool__(self) -> bool:
        return self.valid


def is_select_only(sql: str) -> bool:
    """Check if SQL is SELECT only."""
    try:
        parsed = sqlparse.parse(sql)
        if not parsed:
            return False

        for statement in parsed:
            if not statement.tokens:
                continue
            stmt_type = statement.get_type()
            if stmt_type not in ("SELECT", "UNKNOWN"):
                return False
            if stmt_type == "UNKNOWN":
                first_word = str(statement.tokens[0]).strip().upper()
                if not first_word.startswith("SELECT"):
                    return False
        return True
    except Exception:
        return False


def contains_user_id_filter(sql: str) -> bool:
    """Check if SQL contains user_id filter."""
    patterns = [
        r"\buser_id\s*=\s*[:$@]?user_id\b",
        r"\buser_id\s*=\s*'[^']+'\b",
        r"\buser_id\s*=\s*\$\d+\b",
        r"\.user_id\s*=",
    ]
    for pattern in patterns:
        if re.search(pattern, sql, re.IGNORECASE):
            return True
    return False


def _extract_tables(sql: str) -> list[str]:
    """Extract table names from SQL."""
    tables = []
    patterns = [
        r"\bFROM\s+(\w+)",
        r"\bJOIN\s+(\w+)",
    ]
    for pattern in patterns:
        matches = re.findall(pattern, sql, re.IGNORECASE)
        tables.extend(matches)
    return list(set(t.lower() for t in tables))


def validate_sql(
    sql: str,
    require_user_id: bool = True,
    max_length: int = 10000,
) -> SQLValidationResult:
    """
    Validate SQL for security.

    Args:
        sql: SQL query to validate
        require_user_id: Whether to require user_id filter
        max_length: Maximum SQL length

    Returns:
        SQLValidationResult with validation status
    """
    violations = []
    warnings = []

    # Length check
    if len(sql) > max_length:
        violations.append(f"SQL exceeds maximum length of {max_length}")
        return SQLValidationResult(valid=False, sql=sql, violations=violations)

    # Empty check
    sql_stripped = sql.strip()
    if not sql_stripped:
        violations.append("Empty SQL query")
        return SQLValidationResult(valid=False, sql=sql, violations=violations)

    # SELECT only check
    if not is_select_only(sql_stripped):
        violations.append("Only SELECT statements are allowed")

    # Forbidden patterns check
    sql_upper = sql_stripped.upper()
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, sql_upper, re.IGNORECASE):
            match = re.search(pattern, sql_upper, re.IGNORECASE)
            if match:
                violations.append(f"Forbidden pattern: {match.group()}")

    # User ID filter check
    has_user_filter = contains_user_id_filter(sql_stripped)
    tables = _extract_tables(sql_stripped)

    if require_user_id:
        user_scoped = [t for t in tables if t in USER_SCOPED_TABLES]
        if user_scoped and not has_user_filter:
            violations.append(
                f"User-scoped tables ({', '.join(user_scoped)}) require user_id filter"
            )

    # Warnings
    if "SELECT *" in sql.upper():
        warnings.append("SELECT * may return more data than needed")

    return SQLValidationResult(
        valid=len(violations) == 0,
        sql=sql,
        violations=violations,
        warnings=warnings,
        has_user_id_filter=has_user_filter,
    )


def inject_user_id_filter(sql: str, user_id: str) -> str:
    """Inject user_id filter if not present."""
    if contains_user_id_filter(sql):
        return sql

    sql_upper = sql.upper()
    where_pos = sql_upper.find(" WHERE ")

    if where_pos != -1:
        # Has WHERE - add AND
        end_markers = [" ORDER BY", " GROUP BY", " LIMIT", " HAVING", ";"]
        insert_pos = len(sql)
        for marker in end_markers:
            pos = sql_upper.find(marker, where_pos)
            if pos != -1 and pos < insert_pos:
                insert_pos = pos
        user_filter = f" AND user_id = '{user_id}'"
        sql = sql[:insert_pos] + user_filter + sql[insert_pos:]
    else:
        # No WHERE - add one
        end_markers = [" ORDER BY", " GROUP BY", " LIMIT", " HAVING", ";"]
        insert_pos = len(sql.rstrip())
        for marker in end_markers:
            pos = sql_upper.find(marker)
            if pos != -1 and pos < insert_pos:
                insert_pos = pos
        user_filter = f" WHERE user_id = '{user_id}'"
        sql = sql[:insert_pos] + user_filter + sql[insert_pos:]

    return sql

