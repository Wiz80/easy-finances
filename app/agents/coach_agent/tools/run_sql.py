"""
Run SQL Tool.

Executes validated SELECT queries against PostgreSQL.
"""

import logging
from typing import Any

from langchain_core.tools import tool

from app.config import settings
from app.agents.coach_agent.services.database import DatabaseService
from app.agents.coach_agent.services.sql_validator import SQLValidator

logger = logging.getLogger(__name__)


@tool
def run_sql_query(
    sql: str,
    user_id: str,
    limit: int = 100,
) -> dict[str, Any]:
    """
    Ejecuta un query SQL de solo lectura contra la base de datos financiera.
    
    Medidas de seguridad:
    - Solo se permiten sentencias SELECT
    - Todos los queries se filtran por user_id
    - Timeout de protección (30 segundos)
    - Límite de filas
    - Prevención de inyección SQL
    
    Args:
        sql: Query SQL SELECT a ejecutar
        user_id: ID del usuario (UUID) para filtrar datos - REQUERIDO
        limit: Máximo de filas a retornar (default: 100, max: 1000)
    
    Returns:
        dict con:
        - success: bool - Si el query se ejecutó exitosamente
        - columns: list[str] - Nombres de columnas del resultado
        - rows: list[dict] - Resultados como lista de diccionarios
        - row_count: int - Número de filas retornadas
        - sql_executed: str - El SQL que realmente se ejecutó
        - error: str | None - Mensaje de error si falló
    
    Example:
        run_sql_query(
            "SELECT SUM(amount_original) FROM expense WHERE user_id = :user_id",
            "abc-123-def"
        )
    """
    logger.info(f"Executing SQL query (limit={limit})")

    # Validate and clamp limit
    max_limit = settings.vanna_max_result_rows
    if limit > max_limit:
        logger.warning(f"Requested limit {limit} exceeds max {max_limit}")
        limit = max_limit
    if limit < 1:
        limit = 1

    try:
        # Initialize services
        validator = SQLValidator(require_user_id=True)
        db = DatabaseService()

        # Validate SQL
        validation = validator.validate(sql)

        if not validation.valid:
            logger.warning(f"SQL validation failed: {validation.errors}")
            return {
                "success": False,
                "columns": [],
                "rows": [],
                "row_count": 0,
                "sql_executed": sql,
                "error": f"SQL validation failed: {', '.join(validation.errors)}",
            }

        # Ensure user_id filter and limit
        sql = validator.inject_user_id(sql, user_id)
        sql = validator.enforce_limit(sql, limit)

        logger.info(f"Executing: {sql[:100]}...")

        # Execute query with user_id parameter
        result = db.execute_query(
            sql=sql,
            params={"user_id": user_id},
            timeout_seconds=settings.vanna_query_timeout_seconds,
        )

        if not result["success"]:
            return {
                "success": False,
                "columns": [],
                "rows": [],
                "row_count": 0,
                "sql_executed": sql,
                "error": result["error"],
            }

        logger.info(f"Query returned {len(result['rows'])} rows")

        return {
            "success": True,
            "columns": result["columns"],
            "rows": result["rows"],
            "row_count": result["row_count"],
            "sql_executed": sql,
            "error": None,
        }

    except Exception as e:
        logger.error(f"Error executing SQL: {e}")
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "sql_executed": sql,
            "error": str(e),
        }

