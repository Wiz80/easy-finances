"""
Database Service.

Handles PostgreSQL connections and query execution for the coach agent.
"""

import logging
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import psycopg2
from psycopg2.extras import RealDictCursor

from app.config import settings

logger = logging.getLogger(__name__)


def serialize_value(value: Any) -> Any:
    """Convert non-JSON-serializable values to strings."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def serialize_row(row: dict) -> dict:
    """Serialize a row dict for JSON output."""
    return {k: serialize_value(v) for k, v in row.items()}


class DatabaseService:
    """
    PostgreSQL database service for read-only queries.
    
    Uses the main database credentials (can be restricted to read-only user).
    """

    def __init__(self):
        """Initialize database service."""
        self._connection_params = {
            "host": settings.postgres_host,
            "port": settings.postgres_port,
            "user": settings.postgres_user,
            "password": settings.postgres_password,
            "dbname": settings.postgres_db,
        }

    @contextmanager
    def get_connection(self):
        """
        Get a database connection with automatic cleanup.
        
        Yields:
            psycopg2 connection
        """
        conn = None
        try:
            conn = psycopg2.connect(**self._connection_params)
            yield conn
        finally:
            if conn:
                conn.close()

    def execute_query(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
        timeout_seconds: int | None = None,
    ) -> dict[str, Any]:
        """
        Execute a SELECT query and return results.
        
        Args:
            sql: SQL SELECT query
            params: Query parameters (for parameterized queries)
            timeout_seconds: Query timeout in seconds
            
        Returns:
            {
                "success": bool,
                "columns": list[str],
                "rows": list[dict],
                "row_count": int,
                "error": str | None
            }
        """
        timeout = timeout_seconds or settings.vanna_query_timeout_seconds

        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # Set statement timeout
                    cursor.execute(f"SET statement_timeout = '{timeout}s'")

                    # Execute query with parameters
                    if params:
                        # Convert :param to %(param)s format for psycopg2
                        sql_converted = sql
                        for key in params.keys():
                            sql_converted = sql_converted.replace(
                                f":{key}", f"%({key})s"
                            )
                        cursor.execute(sql_converted, params)
                    else:
                        cursor.execute(sql)

                    # Get results
                    columns = (
                        [desc[0] for desc in cursor.description]
                        if cursor.description
                        else []
                    )
                    rows = cursor.fetchall()

                    # Convert RealDictRow to regular dict and serialize
                    rows_dict = [serialize_row(dict(row)) for row in rows]

                    logger.info(
                        f"Query executed successfully. Rows returned: {len(rows_dict)}"
                    )

                    return {
                        "success": True,
                        "columns": columns,
                        "rows": rows_dict,
                        "row_count": len(rows_dict),
                        "error": None,
                    }

        except psycopg2.errors.QueryCanceled:
            logger.error(f"Query timed out after {timeout}s")
            return {
                "success": False,
                "columns": [],
                "rows": [],
                "row_count": 0,
                "error": f"Query timed out after {timeout} seconds",
            }
        except psycopg2.Error as e:
            logger.error(f"Database error: {e}")
            return {
                "success": False,
                "columns": [],
                "rows": [],
                "row_count": 0,
                "error": str(e),
            }
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {
                "success": False,
                "columns": [],
                "rows": [],
                "row_count": 0,
                "error": str(e),
            }

    def get_table_names(self) -> list[str]:
        """Get list of table names in the public schema."""
        sql = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """
        result = self.execute_query(sql, params={})
        if result["success"]:
            return [row["table_name"] for row in result["rows"]]
        return []

    def get_table_ddl(self, table_name: str) -> str | None:
        """
        Get DDL (CREATE TABLE) for a specific table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            DDL string or None if table not found
        """
        sql = """
            SELECT 
                column_name,
                data_type,
                is_nullable,
                column_default
            FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = %(table_name)s
            ORDER BY ordinal_position
        """
        result = self.execute_query(sql, params={"table_name": table_name})

        if not result["success"] or not result["rows"]:
            return None

        # Build DDL
        columns = []
        for col in result["rows"]:
            col_def = f"    {col['column_name']} {col['data_type']}"
            if col["is_nullable"] == "NO":
                col_def += " NOT NULL"
            if col["column_default"]:
                col_def += f" DEFAULT {col['column_default']}"
            columns.append(col_def)

        ddl = f"CREATE TABLE {table_name} (\n"
        ddl += ",\n".join(columns)
        ddl += "\n);"

        return ddl

    def test_connection(self) -> bool:
        """Test database connection."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    return True
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False

