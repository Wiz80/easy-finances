"""
Database Service.

Handles PostgreSQL connections and query execution.
Uses read-only user for security.
"""

from typing import Any

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError

from src.config import settings

# Lazy-loaded engine
_readonly_engine = None


def get_readonly_engine():
    """Get read-only database engine."""
    global _readonly_engine
    if _readonly_engine is None:
        _readonly_engine = create_engine(
            settings.vanna_database_url,
            pool_pre_ping=True,
            pool_size=5,
            connect_args={
                "connect_timeout": settings.sql_query_timeout_seconds,
                "options": f"-c statement_timeout={settings.sql_query_timeout_seconds * 1000}",
            },
        )
    return _readonly_engine


def get_main_engine():
    """Get main database engine (for schema introspection)."""
    return create_engine(settings.database_url, pool_pre_ping=True)


def execute_query(sql: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Execute a SQL query.
    
    Args:
        sql: SQL query to execute
        params: Query parameters
        
    Returns:
        dict with results, row_count, columns
    """
    engine = get_readonly_engine()
    
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql), params or {})
            rows = result.fetchmany(settings.sql_max_result_rows)
            columns = list(result.keys())
            
            return {
                "results": [dict(zip(columns, row)) for row in rows],
                "row_count": len(rows),
                "columns": columns,
            }
    except SQLAlchemyError as e:
        raise RuntimeError(f"Query execution failed: {e}")


def get_available_tables() -> list[str]:
    """Get list of available tables."""
    engine = get_main_engine()
    inspector = inspect(engine)
    return inspector.get_table_names()


def get_table_ddl(table_name: str) -> str:
    """Get DDL for a specific table."""
    engine = get_main_engine()
    inspector = inspect(engine)
    
    if table_name not in inspector.get_table_names():
        return f"Table '{table_name}' not found"
    
    columns = inspector.get_columns(table_name)
    pk = inspector.get_pk_constraint(table_name)
    
    ddl_parts = [f"CREATE TABLE {table_name} ("]
    
    col_defs = []
    for col in columns:
        col_def = f"  {col['name']} {col['type']}"
        if not col.get("nullable", True):
            col_def += " NOT NULL"
        col_defs.append(col_def)
    
    if pk and pk.get("constrained_columns"):
        pk_cols = ", ".join(pk["constrained_columns"])
        col_defs.append(f"  PRIMARY KEY ({pk_cols})")
    
    ddl_parts.append(",\n".join(col_defs))
    ddl_parts.append(");")
    
    return "\n".join(ddl_parts)

