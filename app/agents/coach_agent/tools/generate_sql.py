"""
Generate SQL Tool.

Converts natural language questions to SQL using Vanna AI 2.x.
"""

import asyncio
import logging
from typing import Any

from langchain_core.tools import tool

from app.agents.coach_agent.services.vanna_service import get_vanna_service
from app.agents.coach_agent.services.sql_validator import SQLValidator

logger = logging.getLogger(__name__)


@tool
def generate_sql(question: str, user_id: str) -> dict[str, Any]:
    """
    Genera un query SQL a partir de una pregunta en lenguaje natural usando Vanna AI.
    
    Esta herramienta usa RAG (Retrieval-Augmented Generation) para:
    1. Buscar preguntas similares en los datos de entrenamiento
    2. Recuperar contexto relevante del schema y documentación
    3. Generar un query SQL preciso usando el LLM
    
    El SQL generado incluirá automáticamente filtro por user_id.
    
    Args:
        question: Pregunta en lenguaje natural sobre finanzas 
                  (ej: "¿Cuánto gasté en comida este mes?")
        user_id: ID del usuario (UUID) para aislamiento de datos
    
    Returns:
        dict con:
        - success: bool - Si se generó el SQL exitosamente
        - sql: str | None - El query SQL generado (con filtro user_id)
        - validation: dict - Resultado de la validación de seguridad
        - similar_patterns: list | None - Preguntas similares encontradas
        - error: str | None - Mensaje de error si falló
    
    Example:
        generate_sql("¿Cuánto gasté este mes?", "abc-123-def")
        → {"success": true, "sql": "SELECT SUM(amount_original)...WHERE user_id = :user_id..."}
    """
    logger.info(f"Generating SQL for question: {question[:50]}...")

    try:
        # Get Vanna service
        vanna_service = get_vanna_service()

        # Generate SQL using Vanna (run async in sync context)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(vanna_service.generate_sql(question))
        finally:
            loop.close()

        if not result["success"]:
            return {
                "success": False,
                "sql": None,
                "validation": {"valid": False, "warnings": []},
                "similar_patterns": result.get("similar_patterns"),
                "error": result["error"],
            }

        sql = result["sql"]

        # Validate and enhance SQL
        validator = SQLValidator(require_user_id=True)

        # Inject user_id if not present
        sql = validator.inject_user_id(sql, user_id)

        # Validate the SQL
        validation = validator.validate(sql)

        if not validation.valid:
            logger.warning(f"Generated SQL failed validation: {validation.errors}")
            return {
                "success": False,
                "sql": sql,
                "validation": {
                    "valid": False,
                    "errors": validation.errors,
                    "warnings": validation.warnings,
                },
                "similar_patterns": result.get("similar_patterns"),
                "error": f"SQL validation failed: {', '.join(validation.errors)}",
            }

        logger.info("Successfully generated SQL")

        return {
            "success": True,
            "sql": sql,
            "validation": {
                "valid": True,
                "warnings": validation.warnings,
            },
            "similar_patterns": result.get("similar_patterns"),
            "error": None,
        }

    except Exception as e:
        logger.error(f"Error in generate_sql: {e}", exc_info=True)
        return {
            "success": False,
            "sql": None,
            "validation": {"valid": False, "warnings": []},
            "similar_patterns": None,
            "error": str(e),
        }





