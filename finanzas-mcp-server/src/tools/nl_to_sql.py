"""
NL to SQL Tool.

Converts natural language questions to SQL using Vanna AI concepts:
- Search similar questions in Qdrant
- Get DDL and documentation context
- Generate SQL with LLM
- Validate and inject user_id
"""

import logging
from typing import Any

from src.config import settings
from src.services.embeddings import generate_embedding, search_similar
from src.services.llm import generate_sql_with_llm
from src.sql_validator import validate_sql, inject_user_id_filter, SQLValidationError

logger = logging.getLogger(__name__)


def nl_to_sql(question: str, user_id: str) -> dict[str, Any]:
    """
    Convert natural language question to SQL.
    
    Args:
        question: Natural language question
        user_id: User ID for filtering
        
    Returns:
        dict with sql, confidence, similar_questions, explanation
    """
    logger.info(f"Generating SQL for: {question[:50]}...")
    
    # Get context from Qdrant
    similar_questions = search_similar(
        collection=settings.qdrant_sql_collection,
        query=question,
        limit=5,
    )
    
    ddl_context = search_similar(
        collection=settings.qdrant_ddl_collection,
        query=question,
        limit=3,
    )
    
    doc_context = search_similar(
        collection=settings.qdrant_doc_collection,
        query=question,
        limit=3,
    )
    
    # Generate SQL with LLM
    sql = generate_sql_with_llm(
        question=question,
        user_id=user_id,
        similar_questions=similar_questions,
        ddl_context=ddl_context,
        doc_context=doc_context,
    )
    
    # Validate SQL
    validation = validate_sql(sql, require_user_id=True)
    if not validation.valid:
        raise SQLValidationError(
            message=f"Generated invalid SQL: {', '.join(validation.violations)}",
            sql=sql,
            violations=validation.violations,
        )
    
    # Inject user_id if needed
    if not validation.has_user_id_filter:
        sql = inject_user_id_filter(sql, user_id)
    
    # Calculate confidence
    confidence = 0.5
    if similar_questions:
        top_score = similar_questions[0].get("score", 0)
        confidence = min(0.95, 0.5 + top_score * 0.5)
    
    return {
        "sql": sql,
        "confidence": confidence,
        "similar_questions": [q.get("question") for q in similar_questions if q.get("question")],
        "explanation": f"SQL generado basado en {len(similar_questions)} ejemplos similares",
    }

