"""
Finanzas MCP Server.

MCP server that exposes tools for:
1. nl_to_sql: Convert natural language to SQL using Vanna AI
2. execute_sql: Execute validated SELECT queries

Uses FastMCP for simple server definition.

Usage:
    # STDIO mode (development)
    python -m src.server
    
    # Or using uv
    uv run src/server.py
"""

from mcp.server.fastmcp import FastMCP

from src.config import settings
from src.tools.nl_to_sql import nl_to_sql
from src.tools.execute_sql import execute_sql
from src.tools.schema import get_schema_context

# Initialize FastMCP server
mcp = FastMCP(
    "finanzas-mcp-server",
    dependencies=["openai", "qdrant-client", "sqlalchemy", "psycopg2-binary"],
)


# =============================================================================
# TOOLS
# =============================================================================

@mcp.tool()
def generate_sql(question: str, user_id: str) -> dict:
    """
    Convert a natural language question to SQL query using Vanna AI.
    
    The generated SQL will:
    - Only be a SELECT statement (no modifications)
    - Include user_id filter for data isolation
    - Be validated for security
    
    Use this tool when the user asks a question about their financial data.
    
    Args:
        question: Natural language question in Spanish about financial data
        user_id: User ID (UUID) for data isolation
        
    Returns:
        dict with: sql, confidence, similar_questions, explanation
        
    Example questions:
        - "¿Cuánto gasté este mes?"
        - "¿Cuáles son mis gastos por categoría?"
        - "Muéstrame los gastos de la última semana"
    """
    return nl_to_sql(question=question, user_id=user_id)


@mcp.tool()
def run_sql_query(sql: str, user_id: str) -> dict:
    """
    Execute a validated SQL SELECT query against the database.
    
    Security measures:
    - Only SELECT statements allowed
    - Must include user_id filter
    - Query timeout enforced (30s)
    - Results limited to 1000 rows
    
    Use this tool after generating SQL with generate_sql to get the actual data.
    
    Args:
        sql: SQL SELECT query to execute
        user_id: User ID (UUID) for verification
        
    Returns:
        dict with: results, row_count, columns, execution_time_ms
    """
    return execute_sql(sql=sql, user_id=user_id)


@mcp.tool()
def get_database_schema(table_name: str | None = None) -> dict:
    """
    Get database schema information for context.
    
    Returns DDL statements and documentation for the financial tables.
    Use this to understand the data structure.
    
    Args:
        table_name: Optional specific table name to get schema for
        
    Returns:
        dict with schema information
    """
    return get_schema_context(table_name=table_name)


# =============================================================================
# RESOURCES
# =============================================================================

@mcp.resource("postgres://tables")
def list_tables() -> str:
    """List of tables available for querying."""
    import json
    from src.services.database import get_available_tables
    tables = get_available_tables()
    return json.dumps(tables, indent=2)


@mcp.resource("postgres://schema/{table_name}")
def table_schema(table_name: str) -> str:
    """DDL for a specific table."""
    from src.services.database import get_table_ddl
    return get_table_ddl(table_name)


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Run the MCP server."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Finanzas MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default=settings.transport,
        help="Transport mode (stdio for dev, sse for prod)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=settings.http_port,
        help="HTTP port (for sse transport)"
    )
    
    args = parser.parse_args()
    
    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="sse", port=args.port)


if __name__ == "__main__":
    main()
