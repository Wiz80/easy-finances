"""
Prompts for the Coordinator Agent.

These prompts are used for:
1. Intent detection: Determine which agent should handle a message
2. Command handling: Process special commands (cancel, help, etc.)
3. Welcome/fallback messages
"""

# ─────────────────────────────────────────────────────────────────────────────
# Intent Detection for Agent Routing
# ─────────────────────────────────────────────────────────────────────────────

AGENT_ROUTING_SYSTEM = """Eres un clasificador de intenciones para un asistente de finanzas personales.
Tu trabajo es determinar qué agente especializado debe procesar el mensaje del usuario.

AGENTES DISPONIBLES:

1. **configuration** - Configuración y setup
   - Crear/modificar viajes
   - Agregar tarjetas o cuentas bancarias
   - Configurar presupuestos
   - Cambiar configuración del usuario (moneda, zona horaria)
   - Onboarding de nuevos usuarios

2. **expense** - Registro de gastos
   - Registrar un gasto ("gasté X en Y", "pagué X", "compré X")
   - Enviar recibos o facturas (imágenes)
   - Notas de voz con gastos
   - Cualquier mensaje que mencione dinero gastado

3. **query** - Consultas y reportes
   - Preguntas sobre finanzas ("¿cuánto gasté?", "¿cuál es mi saldo?")
   - Solicitar reportes o resúmenes
   - Consultas de presupuesto ("¿cómo voy?")
   - Comparaciones y análisis

REGLAS:
- Si el mensaje contiene una cantidad de dinero CON una acción de gasto → **expense**
- Si el mensaje es una pregunta sobre dinero → **query**  
- Si menciona "configurar", "crear viaje", "agregar tarjeta" → **configuration**
- Si es ambiguo, elige el más probable basándote en el contexto

Responde ÚNICAMENTE con una de estas palabras: configuration, expense, query"""

AGENT_ROUTING_USER = """Mensaje del usuario: "{message}"

Contexto:
- Onboarding completado: {onboarding_completed}
- Tiene viaje activo: {has_active_trip}
- Último agente usado: {last_agent}

¿Qué agente debe procesar este mensaje?"""


# ─────────────────────────────────────────────────────────────────────────────
# Intent Change Detection
# ─────────────────────────────────────────────────────────────────────────────

INTENT_CHANGE_DETECTION_SYSTEM = """Eres un detector de cambios de intención.
Un agente especializado está procesando la conversación, pero el usuario podría querer cambiar de tema.

Determina si el mensaje del usuario indica un CAMBIO de intención que requiera otro agente.

AGENTE ACTUAL: {current_agent}
- configuration: Configuración de usuario, viajes, tarjetas, presupuestos
- expense: Registro de gastos
- query: Consultas y reportes financieros

SEÑALES DE CAMBIO:
- Frase que claramente pertenece a otro dominio
- "Espera", "primero", "antes" seguido de otra intención
- Pregunta mientras se estaba registrando un gasto
- Gasto mientras se estaba haciendo una consulta

SEÑALES DE CONTINUACIÓN (NO cambiar):
- Respuesta directa a una pregunta del bot
- Confirmación o negación
- Datos adicionales para el flujo actual
- Aclaraciones sobre lo mismo

Responde SOLO con JSON:
{{"should_change": true/false, "new_agent": "configuration|expense|query|null", "reason": "explicación breve"}}"""

INTENT_CHANGE_DETECTION_USER = """El usuario está en una conversación con el agente "{current_agent}".

Último mensaje del bot: "{last_bot_message}"

Mensaje actual del usuario: "{message}"

¿El usuario quiere cambiar de tema/agente?"""


# ─────────────────────────────────────────────────────────────────────────────
# Command Responses
# ─────────────────────────────────────────────────────────────────────────────

CANCEL_RESPONSE = """❌ Operación cancelada.

¿En qué más puedo ayudarte?
• Registrar gasto: "50 dólares taxi"
• Nueva consulta: "¿cuánto gasté hoy?"
• Configurar viaje: "nuevo viaje\""""

MENU_RESPONSE = """📋 *Menú Principal*

¿Qué te gustaría hacer?

💰 *Registrar gasto*
   Ejemplo: "30 soles almuerzo"

📊 *Consultar finanzas*
   Ejemplo: "¿cuánto llevo gastado?"

✈️ *Configurar viaje*
   Escribe: "nuevo viaje"

💳 *Agregar tarjeta*
   Escribe: "agregar tarjeta"

📈 *Ver presupuesto*
   Escribe: "cómo voy con el presupuesto"

Simplemente escribe lo que necesites."""

HELP_RESPONSE = """ℹ️ *Ayuda - FinBot*

Soy tu asistente de finanzas personales. Puedo:

*📝 Registrar gastos*
• Por texto: "Gasté 50 dólares en taxi"
• Por voz: Envía una nota de voz
• Por foto: Envía una foto del recibo

*📊 Responder consultas*
• "¿Cuánto gasté este mes?"
• "¿Cómo voy con el presupuesto de comida?"
• "Resumen de gastos de la semana"

*⚙️ Configuración*
• "Nuevo viaje" - Crear un viaje
• "Agregar tarjeta" - Registrar tarjeta
• "Configurar presupuesto" - Crear presupuesto

*Comandos especiales:*
• "cancelar" - Cancelar operación actual
• "menú" - Ver opciones
• "ayuda" - Ver esta ayuda

¿En qué puedo ayudarte?"""

STATUS_RESPONSE = """📍 *Estado Actual*

👤 Usuario: {user_name}
💵 Moneda base: {home_currency}
🌍 Zona horaria: {timezone}

✈️ Viaje activo: {active_trip}
📊 Presupuesto: {budget_status}
🤖 Agente actual: {active_agent}

Para más opciones escribe "menú\""""


# ─────────────────────────────────────────────────────────────────────────────
# Fallback and Error Messages
# ─────────────────────────────────────────────────────────────────────────────

FALLBACK_RESPONSE = """🤔 No estoy seguro de cómo ayudarte con eso.

Puedo:
• Registrar gastos: "50 dólares taxi"
• Responder preguntas: "¿cuánto gasté?"
• Configurar viajes: "nuevo viaje"

Escribe "ayuda" para ver todas las opciones."""

ERROR_RESPONSE = """⚠️ Ocurrió un error procesando tu mensaje.

Por favor intenta de nuevo o escribe "ayuda" si necesitas asistencia."""

ONBOARDING_REQUIRED_RESPONSE = """👋 ¡Hola! Parece que aún no has completado tu configuración inicial.

Necesito conocerte un poco para ayudarte mejor.
*¿Cómo te llamas?*"""


# ─────────────────────────────────────────────────────────────────────────────
# Context Templates for Prompts
# ─────────────────────────────────────────────────────────────────────────────

def build_routing_prompt(
    message: str,
    onboarding_completed: bool = True,
    has_active_trip: bool = False,
    last_agent: str | None = None,
) -> tuple[str, str]:
    """
    Build the system and user prompts for agent routing.
    
    Args:
        message: User's message
        onboarding_completed: Whether user completed onboarding
        has_active_trip: Whether user has an active trip
        last_agent: Last agent that processed a message
        
    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    user_prompt = AGENT_ROUTING_USER.format(
        message=message,
        onboarding_completed="Sí" if onboarding_completed else "No",
        has_active_trip="Sí" if has_active_trip else "No",
        last_agent=last_agent or "Ninguno",
    )
    return AGENT_ROUTING_SYSTEM, user_prompt


def build_intent_change_prompt(
    message: str,
    current_agent: str,
    last_bot_message: str | None = None,
) -> tuple[str, str]:
    """
    Build prompts to detect if user wants to change agents.
    
    Args:
        message: User's current message
        current_agent: Currently active agent
        last_bot_message: Last message sent by the bot
        
    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    system_prompt = INTENT_CHANGE_DETECTION_SYSTEM.format(
        current_agent=current_agent,
    )
    user_prompt = INTENT_CHANGE_DETECTION_USER.format(
        current_agent=current_agent,
        last_bot_message=last_bot_message or "(sin mensaje previo)",
        message=message,
    )
    return system_prompt, user_prompt


def build_status_response(
    user_name: str,
    home_currency: str,
    timezone: str,
    active_trip: str | None = None,
    budget_status: str | None = None,
    active_agent: str | None = None,
) -> str:
    """Build the status response message."""
    return STATUS_RESPONSE.format(
        user_name=user_name,
        home_currency=home_currency,
        timezone=timezone,
        active_trip=active_trip or "Ninguno",
        budget_status=budget_status or "No configurado",
        active_agent=active_agent or "Coordinador",
    )

