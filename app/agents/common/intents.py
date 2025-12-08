"""
Intent Definitions for Agent Routing.

This module defines:
- Agent types and their domains
- Keywords for fast intent detection
- Special coordinator commands
- Intent classification utilities
"""

from enum import Enum


class AgentType(str, Enum):
    """
    Available agent types for routing.
    
    Each agent handles a specific domain:
    - CONFIGURATION: User setup, trips, cards, budgets
    - IE: Expense extraction and storage
    - COACH: Financial queries and reports
    - COORDINATOR: Routing and orchestration (not a target)
    """
    
    CONFIGURATION = "configuration"
    IE = "ie"
    COACH = "coach"
    COORDINATOR = "coordinator"  # For handoff back to router
    UNKNOWN = "unknown"


# ─────────────────────────────────────────────────────────────────────────────
# Intent Categories
# ─────────────────────────────────────────────────────────────────────────────

CONFIGURATION_INTENTS = [
    "configurar_viaje",
    "agregar_tarjeta",
    "crear_presupuesto",
    "modificar_presupuesto",
    "cambiar_configuracion",
    "cambiar_moneda",
    "cambiar_timezone",
    "ayuda_configuracion",
    "ver_viajes",
    "ver_tarjetas",
]

EXPENSE_INTENTS = [
    "registrar_gasto",
    "adjuntar_recibo",
    "gasto_voz",
    "pago",
    "compra",
    "gasto_efectivo",
    "gasto_tarjeta",
]

QUERY_INTENTS = [
    "consulta_gasto",
    "reporte",
    "resumen",
    "presupuesto_status",
    "pregunta_finanzas",
    "balance",
    "comparacion",
]


# ─────────────────────────────────────────────────────────────────────────────
# Keywords for Fast Intent Detection
# ─────────────────────────────────────────────────────────────────────────────

# Keywords that strongly suggest expense registration
EXPENSE_KEYWORDS = [
    # Actions
    "gasté", "gaste", "pagué", "pague", "compré", "compre",
    "gastos", "gasto", "pago", "compra",
    # Currencies
    "soles", "sol", "dólares", "dolares", "dólar", "dolar",
    "pesos", "peso", "euros", "euro", "usd", "pen", "cop", "mxn",
    # Payment methods
    "efectivo", "tarjeta", "cash", "card",
    # Common expense types
    "uber", "taxi", "almuerzo", "cena", "desayuno",
    "comida", "restaurante", "café", "cafe", "hotel",
    "vuelo", "transporte", "bus", "metro",
    # Indicators
    "recibo", "factura", "ticket",
]

# Keywords that suggest a query/question
QUERY_KEYWORDS = [
    # Question words
    "cuánto", "cuanto", "cuánta", "cuanta",
    "qué", "que", "cuál", "cual",
    "cómo", "como", "dónde", "donde",
    # Query verbs
    "muéstrame", "muestrame", "dime", "mostrar",
    "ver", "consultar", "revisar",
    # Report words
    "resumen", "reporte", "total", "balance",
    "presupuesto", "saldo", "gastado",
    # Time references in questions
    "este mes", "esta semana", "hoy", "ayer",
    # Status questions
    "voy", "llevo", "quedan", "queda", "falta",
]

# Keywords that suggest configuration/setup
CONFIG_KEYWORDS = [
    # Actions
    "configurar", "crear", "agregar", "añadir", "nuevo", "nueva",
    "modificar", "cambiar", "editar", "actualizar",
    # Entities
    "viaje", "trip", "tarjeta", "card", "cuenta", "account",
    "presupuesto", "budget",
    # Setup phrases
    "quiero configurar", "necesito configurar",
    "crear viaje", "nuevo viaje", "agregar tarjeta", "nueva tarjeta",
    "presupuesto para",
]


# ─────────────────────────────────────────────────────────────────────────────
# Special Coordinator Commands
# ─────────────────────────────────────────────────────────────────────────────

COORDINATOR_COMMANDS = {
    # Cancel/Reset commands
    "cancelar": "cancel_current_flow",
    "cancel": "cancel_current_flow",
    "salir": "cancel_current_flow",
    "exit": "cancel_current_flow",
    
    # Menu/Help commands
    "menu": "show_menu",
    "menú": "show_menu",
    "ayuda": "show_help",
    "help": "show_help",
    
    # Reset commands
    "reiniciar": "restart_conversation",
    "reset": "restart_conversation",
    "/reset": "admin_reset",
    
    # Status commands
    "estado": "show_status",
    "status": "show_status",
}

# Commands that should always be handled by Coordinator (not passed to agents)
INTERCEPT_COMMANDS = {"cancelar", "cancel", "menu", "menú", "ayuda", "help", "/reset"}


# ─────────────────────────────────────────────────────────────────────────────
# Intent Detection Utilities
# ─────────────────────────────────────────────────────────────────────────────

def is_coordinator_command(message: str) -> tuple[bool, str | None]:
    """
    Check if message is a special coordinator command.
    
    Args:
        message: User message text
        
    Returns:
        Tuple of (is_command, command_action)
    """
    message_lower = message.lower().strip()
    
    # Check exact matches
    if message_lower in COORDINATOR_COMMANDS:
        return True, COORDINATOR_COMMANDS[message_lower]
    
    return False, None


def count_keywords(message: str, keywords: list[str]) -> int:
    """
    Count how many keywords from a list appear in the message.
    
    Args:
        message: User message text
        keywords: List of keywords to check
        
    Returns:
        Count of keywords found
    """
    message_lower = message.lower()
    return sum(1 for kw in keywords if kw in message_lower)


def detect_intent_fast(message: str) -> AgentType | None:
    """
    Fast intent detection using keyword matching.
    
    This is the "fast path" that avoids LLM calls for obvious cases.
    Returns None if intent is ambiguous and LLM should be used.
    
    Args:
        message: User message text
        
    Returns:
        AgentType if confidently detected, None if ambiguous
    """
    message_lower = message.lower()
    
    # Check if it's a coordinator command first
    is_cmd, _ = is_coordinator_command(message)
    if is_cmd:
        return AgentType.COORDINATOR
    
    # Count keywords for each agent type
    expense_score = count_keywords(message_lower, EXPENSE_KEYWORDS)
    query_score = count_keywords(message_lower, QUERY_KEYWORDS)
    config_score = count_keywords(message_lower, CONFIG_KEYWORDS)
    
    # Clear winner: expense keywords
    if expense_score >= 2 and expense_score > query_score and expense_score > config_score:
        return AgentType.IE
    
    # Clear winner: query keywords
    if query_score >= 2 and query_score > expense_score:
        return AgentType.COACH
    
    # Clear winner: config keywords
    if config_score >= 1 and config_score > expense_score and config_score > query_score:
        return AgentType.CONFIGURATION
    
    # Single strong expense indicator (common pattern: "50 soles taxi")
    if expense_score == 1 and query_score == 0 and config_score == 0:
        # Check if message contains a number (likely expense)
        import re
        if re.search(r'\d+', message):
            return AgentType.IE
    
    # Ambiguous - needs LLM
    return None


def get_agent_description(agent_type: AgentType) -> str:
    """Get human-readable description of an agent."""
    descriptions = {
        AgentType.CONFIGURATION: "Configuración (viajes, tarjetas, presupuestos)",
        AgentType.IE: "Registro de gastos",
        AgentType.COACH: "Consultas y reportes financieros",
        AgentType.COORDINATOR: "Coordinador",
        AgentType.UNKNOWN: "Desconocido",
    }
    return descriptions.get(agent_type, "Desconocido")

