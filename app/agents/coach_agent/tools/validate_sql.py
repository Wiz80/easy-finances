"""
Validate SQL Tool.

Pre-validates SQL queries before execution.
"""

import logging
from typing import Any

from langchain_core.tools import tool

from app.agents.coach_agent.services.sql_validator import SQLValidator

logger = logging.getLogger(__name__)


@tool
def validate_sql(sql: str) -> dict[str, Any]:
    """
    Valida un query SQL por seguridad y sintaxis antes de ejecutarlo.
    
    Esta herramienta verifica:
    - Solo sentencias SELECT permitidas
    - No keywords peligrosos (DROP, DELETE, UPDATE, INSERT, etc.)
    - Sintaxis SQL válida
    - Contiene filtro user_id (requerido para aislamiento de datos)
    - No patrones de inyección SQL
    
    Usa esta herramienta para validar SQL antes de llamar run_sql_query.
    
    Args:
        sql: Query SQL a validar
    
    Returns:
        dict con:
        - valid: bool - Si el SQL es seguro para ejecutar
        - errors: list[str] - Lista de errores de validación (bloqueantes)
        - warnings: list[str] - Lista de advertencias (no bloqueantes)
        - sql_type: str - Tipo de sentencia detectada (SELECT, etc.)
    
    Example:
        validate_sql("SELECT * FROM expense WHERE user_id = :user_id")
        → {"valid": true, "errors": [], "warnings": ["Consider selecting specific columns..."]}
    """
    logger.info(f"Validating SQL: {sql[:50]}...")

    try:
        validator = SQLValidator(require_user_id=True)
        result = validator.validate(sql)

        # Detect SQL type
        sql_upper = sql.strip().upper()
        if sql_upper.startswith("SELECT"):
            sql_type = "SELECT"
        elif sql_upper.startswith("INSERT"):
            sql_type = "INSERT"
        elif sql_upper.startswith("UPDATE"):
            sql_type = "UPDATE"
        elif sql_upper.startswith("DELETE"):
            sql_type = "DELETE"
        else:
            sql_type = "UNKNOWN"

        logger.info(f"Validation result: valid={result.valid}, type={sql_type}")

        return {
            "valid": result.valid,
            "errors": result.errors,
            "warnings": result.warnings,
            "sql_type": sql_type,
        }

    except Exception as e:
        logger.error(f"Error validating SQL: {e}")
        return {
            "valid": False,
            "errors": [str(e)],
            "warnings": [],
            "sql_type": "UNKNOWN",
        }

