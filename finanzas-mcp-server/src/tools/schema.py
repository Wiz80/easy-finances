"""
Schema Tool.

Returns database schema information.
"""

from typing import Any

from src.services.database import get_available_tables, get_table_ddl


def get_schema_context(table_name: str | None = None) -> dict[str, Any]:
    """
    Get schema context for SQL generation.
    
    Args:
        table_name: Optional specific table
        
    Returns:
        dict with schema information
    """
    if table_name:
        return {
            "table": table_name,
            "schema": get_table_ddl(table_name),
        }
    else:
        tables = get_available_tables()
        return {
            "tables": tables,
            "schemas": {t: get_table_ddl(t) for t in tables[:10]},
        }

