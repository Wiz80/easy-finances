"""
Prompts for SQL generation from natural language queries.

Used by the Coach Agent (VannaService) for text-to-SQL conversion.
"""

# System prompt for Vanna SQL generation
SQL_GENERATION_SYSTEM = """Eres un experto en SQL para PostgreSQL. Genera consultas SQL basadas en preguntas en lenguaje natural.

REGLAS IMPORTANTES:
1. Retorna SOLO el query SQL, sin explicaciones ni markdown
2. Usa sintaxis PostgreSQL
3. SIEMPRE incluye WHERE user_id = :user_id para filtrar por usuario
4. Usa occurred_at para filtros de fecha (no created_at)
5. Los montos están en amount_original con currency_original
6. Para "este mes" usa: occurred_at >= DATE_TRUNC('month', CURRENT_DATE)
7. Para "última semana" usa: occurred_at >= CURRENT_DATE - INTERVAL '7 days'
8. Solo genera SELECT, nunca INSERT/UPDATE/DELETE
9. Incluye LIMIT 100 si no se especifica un límite
"""

# Template for adding RAG context to the prompt
SQL_GENERATION_CONTEXT_TEMPLATE = """
CONTEXTO DE ENTRENAMIENTO:
{context}
"""

# Date filter patterns for reference
DATE_FILTER_PATTERNS = {
    "este_mes": "occurred_at >= DATE_TRUNC('month', CURRENT_DATE)",
    "mes_pasado": "occurred_at >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month') AND occurred_at < DATE_TRUNC('month', CURRENT_DATE)",
    "ultima_semana": "occurred_at >= CURRENT_DATE - INTERVAL '7 days'",
    "ultimo_mes": "occurred_at >= CURRENT_DATE - INTERVAL '30 days'",
    "hoy": "occurred_at >= CURRENT_DATE AND occurred_at < CURRENT_DATE + INTERVAL '1 day'",
    "ayer": "occurred_at >= CURRENT_DATE - INTERVAL '1 day' AND occurred_at < CURRENT_DATE",
}
