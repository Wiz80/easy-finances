"""
Execute SQL Tool.

Executes validated SELECT queries against PostgreSQL.
"""

import logging
import time
from typing import Any

from src.services.database import execute_query
from src.sql_validator import validate_sql, inject_user_id_filter, SQLValidationError

logger = logging.getLogger(__name__)


def execute_sql(sql: str, user_id: str) -> dict[str, Any]:
    """
    Execute a validated SQL query.
    
    Args:
        sql: SQL SELECT query
        user_id: User ID for verification
        
    Returns:
        dict with results, row_count, columns, execution_time_ms
    """
    logger.info(f"Executing SQL: {sql[:100]}...")
    
    # Validate
    validation = validate_sql(sql, require_user_id=True)
    if not validation.valid:
        raise SQLValidationError(
            message=f"SQL validation failed: {', '.join(validation.violations)}",
            sql=sql,
            violations=validation.violations,
        )
    
    # Inject user_id if needed
    if not validation.has_user_id_filter:
        sql = inject_user_id_filter(sql, user_id)
    
    # Execute
    start_time = time.time()
    result = execute_query(sql, {"user_id": user_id})
    execution_time = (time.time() - start_time) * 1000
    
    return {
        "results": result["results"],
        "row_count": result["row_count"],
        "columns": result["columns"],
        "execution_time_ms": round(execution_time, 2),
    }

