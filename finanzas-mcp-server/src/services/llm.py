"""
LLM Service.

Handles SQL generation using OpenAI.
"""

from typing import Any

from src.config import settings
from src.services.embeddings import get_openai_client


# System prompt for SQL generation
SQL_SYSTEM_PROMPT = """Eres un experto en SQL para una aplicación de finanzas personales.

Tu trabajo es generar consultas SQL SELECT válidas basadas en preguntas en lenguaje natural.

REGLAS ESTRICTAS:
1. SOLO genera sentencias SELECT
2. SIEMPRE incluye "WHERE user_id = :user_id" para filtrar por usuario
3. Usa los nombres exactos de tablas y columnas del esquema proporcionado
4. Para fechas, usa occurred_at (cuando ocurrió el gasto) no created_at
5. Las cantidades están en amount_original con currency_original
6. NUNCA uses DROP, DELETE, UPDATE, INSERT u otras operaciones destructivas

TABLAS PRINCIPALES:
- expense: Gastos del usuario (amount_original, currency_original, occurred_at, category_id, user_id)
- category: Categorías de gastos (id, name, slug)
- trip: Viajes para agrupar gastos (id, name, start_date, end_date, user_id)
- receipt: Recibos escaneados (id, expense_id, user_id)
- account: Cuentas bancarias (id, name, user_id)
- card: Tarjetas de crédito/débito (id, name, account_id)

Responde SOLO con la consulta SQL, sin explicaciones adicionales.
No uses bloques de código markdown, solo el SQL puro."""


def generate_sql_with_llm(
    question: str,
    user_id: str,
    similar_questions: list[dict[str, Any]],
    ddl_context: list[dict[str, Any]],
    doc_context: list[dict[str, Any]],
) -> str:
    """
    Generate SQL using LLM with context.
    
    Args:
        question: User's question
        user_id: User ID for filtering
        similar_questions: Similar question-SQL pairs
        ddl_context: DDL statements for context
        doc_context: Documentation for context
        
    Returns:
        Generated SQL query
    """
    # Build prompt
    prompt_parts = []
    
    # Add DDL context
    if ddl_context:
        prompt_parts.append("ESQUEMA DE BASE DE DATOS:")
        for ctx in ddl_context:
            if ctx.get("content"):
                prompt_parts.append(ctx["content"])
        prompt_parts.append("")
    
    # Add documentation context
    if doc_context:
        prompt_parts.append("DOCUMENTACIÓN:")
        for ctx in doc_context:
            if ctx.get("content"):
                prompt_parts.append(ctx["content"])
        prompt_parts.append("")
    
    # Add similar examples
    if similar_questions:
        prompt_parts.append("EJEMPLOS SIMILARES:")
        for ex in similar_questions[:3]:
            if ex.get("question") and ex.get("content"):
                prompt_parts.append(f"Pregunta: {ex['question']}")
                prompt_parts.append(f"SQL: {ex['content']}")
                prompt_parts.append("")
    
    # Add the question
    prompt_parts.append(f"PREGUNTA: {question}")
    prompt_parts.append(f"USER_ID: {user_id}")
    prompt_parts.append("")
    prompt_parts.append("Genera el SQL:")
    
    prompt = "\n".join(prompt_parts)
    
    # Call LLM
    client = get_openai_client()
    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": SQL_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
    )
    
    sql = response.choices[0].message.content.strip()
    
    # Clean SQL
    return _clean_sql(sql)


def _clean_sql(sql: str) -> str:
    """Remove markdown code blocks from SQL."""
    sql = sql.strip()
    if sql.startswith("```sql"):
        sql = sql[6:]
    elif sql.startswith("```"):
        sql = sql[3:]
    if sql.endswith("```"):
        sql = sql[:-3]
    return sql.strip()

