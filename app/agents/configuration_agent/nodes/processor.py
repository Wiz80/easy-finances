"""
Flow processor node for Configuration Agent.

Processes the current flow based on detected intent and updates state.
"""

from app.agents.configuration_agent.state import ConfigurationAgentState, FlowType
from app.integrations.whatsapp import infer_timezone_from_phone
from app.logging_config import get_logger

logger = get_logger(__name__)


def process_flow_node(state: ConfigurationAgentState) -> ConfigurationAgentState:
    """
    Process the current flow based on detected intent.
    
    This node:
    1. Routes to the appropriate flow handler
    2. Updates flow_data with extracted entities
    3. Determines what to persist and what response to generate
    
    Args:
        state: Current agent state
        
    Returns:
        Updated state with flow progress and persistence instructions
    """
    current_flow = state.get("current_flow", "unknown")
    intent = state.get("detected_intent", "unknown")
    entities = state.get("extracted_entities", {})
    
    logger.debug(
        "process_flow_start",
        request_id=state.get("request_id"),
        flow=current_flow,
        intent=intent
    )
    
    # Route to flow handler
    if current_flow == "onboarding":
        return _process_onboarding(state, intent, entities)
    elif current_flow == "trip_setup":
        return _process_trip_setup(state, intent, entities)
    elif current_flow == "budget_config":
        return _process_budget_config(state, intent, entities)
    elif current_flow == "card_setup":
        return _process_card_setup(state, intent, entities)
    elif current_flow == "general":
        return _process_general(state, intent, entities)
    else:
        return _process_unknown(state, intent, entities)


def _process_onboarding(
    state: ConfigurationAgentState,
    intent: str,
    entities: dict
) -> ConfigurationAgentState:
    """Process onboarding flow."""
    flow_data = state.get("flow_data", {}).copy()
    pending_field = state.get("pending_field")
    phone = state.get("phone_number", "")
    
    # Determine what step we're in based on what data we have
    has_name = bool(flow_data.get("name") or state.get("user_name"))
    has_currency = bool(flow_data.get("currency") or state.get("home_currency"))
    has_timezone = bool(flow_data.get("timezone") or state.get("timezone"))
    
    # Handle greeting - start onboarding
    if intent == "greeting" and not has_name:
        return {
            **state,
            "flow_data": flow_data,
            "pending_field": "name",
            "response_text": None,  # Let response node generate welcome
        }
    
    # Handle name provision
    if intent == "onboarding_provide_name" or (not has_name and entities.get("name")):
        name = entities.get("name", state.get("message_body", "").strip())
        flow_data["name"] = name
        
        return {
            **state,
            "flow_data": flow_data,
            "pending_field": "currency",
            "should_persist": True,
            "persist_type": "user_update",
            "persist_data": {"full_name": name, "nickname": name.split()[0]},
        }
    
    # Handle currency provision
    if intent == "onboarding_provide_currency" or entities.get("currency"):
        currency = entities.get("currency", state.get("message_body", "").upper().strip())
        
        # Validate currency
        valid_currencies = ["USD", "COP", "MXN", "EUR", "PEN", "CLP", "ARS", "BRL", "GBP"]
        if currency not in valid_currencies:
            return {
                **state,
                "flow_data": flow_data,
                "pending_field": "currency",
                "response_text": f"No reconozco '{currency}'. Por favor usa uno de: USD, COP, MXN, EUR, PEN",
            }
        
        flow_data["currency"] = currency
        
        # Try to infer timezone
        suggested_tz = infer_timezone_from_phone(phone)
        if suggested_tz:
            flow_data["suggested_timezone"] = suggested_tz
        
        return {
            **state,
            "flow_data": flow_data,
            "pending_field": "timezone",
            "should_persist": True,
            "persist_type": "user_update",
            "persist_data": {"home_currency": currency},
        }
    
    # Handle timezone confirmation/provision
    if intent == "confirm" and pending_field == "timezone":
        tz = flow_data.get("suggested_timezone", "America/Mexico_City")
        flow_data["timezone"] = tz
        
        return {
            **state,
            "flow_data": flow_data,
            "pending_field": None,
            "current_flow": "general",
            "should_persist": True,
            "persist_type": "user_complete_onboarding",
            "persist_data": {"timezone": tz},
        }
    
    if intent == "deny" and pending_field == "timezone":
        return {
            **state,
            "flow_data": flow_data,
            "pending_field": "timezone_manual",
            "response_text": "¿En qué zona horaria te encuentras?\nEjemplos: America/Bogota, America/Mexico_City, America/Lima",
        }
    
    if intent == "onboarding_provide_timezone" or pending_field == "timezone_manual":
        tz = entities.get("timezone", state.get("message_body", "").strip())
        flow_data["timezone"] = tz
        
        return {
            **state,
            "flow_data": flow_data,
            "pending_field": None,
            "current_flow": "general",
            "should_persist": True,
            "persist_type": "user_complete_onboarding",
            "persist_data": {"timezone": tz},
        }
    
    # Default - continue with next step
    if not has_name:
        return {**state, "pending_field": "name"}
    elif not has_currency:
        return {**state, "flow_data": flow_data, "pending_field": "currency"}
    elif not has_timezone:
        return {**state, "flow_data": flow_data, "pending_field": "timezone"}
    
    return state


def _process_trip_setup(
    state: ConfigurationAgentState,
    intent: str,
    entities: dict
) -> ConfigurationAgentState:
    """Process trip setup flow."""
    flow_data = state.get("flow_data", {}).copy()
    pending_field = state.get("pending_field")
    
    # Start trip setup
    if intent == "trip_create":
        return {
            **state,
            "flow_data": {},
            "pending_field": "trip_name",
        }
    
    # Handle trip name
    if pending_field == "trip_name" or entities.get("trip_name"):
        name = entities.get("trip_name", state.get("message_body", "").strip())
        flow_data["name"] = name
        return {
            **state,
            "flow_data": flow_data,
            "pending_field": "start_date",
        }
    
    # Handle start date
    if pending_field == "start_date" or entities.get("start_date"):
        date = entities.get("start_date", state.get("message_body", "").strip())
        flow_data["start_date"] = date
        return {
            **state,
            "flow_data": flow_data,
            "pending_field": "end_date",
        }
    
    # Handle end date
    if pending_field == "end_date" or entities.get("end_date"):
        date = entities.get("end_date", state.get("message_body", "").strip())
        flow_data["end_date"] = date
        return {
            **state,
            "flow_data": flow_data,
            "pending_field": "country",
        }
    
    # Handle country
    if pending_field == "country" or entities.get("country"):
        country = entities.get("country", state.get("message_body", "").strip())
        flow_data["country"] = country
        # TODO: Infer currency from country
        return {
            **state,
            "flow_data": flow_data,
            "pending_field": "confirm_trip",
        }
    
    # Handle confirmation
    if intent == "confirm" and pending_field == "confirm_trip":
        return {
            **state,
            "flow_data": flow_data,
            "pending_field": None,
            "current_flow": "general",
            "should_persist": True,
            "persist_type": "trip_create",
            "persist_data": flow_data,
        }
    
    if intent == "deny" and pending_field == "confirm_trip":
        return {
            **state,
            "flow_data": {},
            "pending_field": "trip_name",
            "response_text": "Ok, empecemos de nuevo. ¿Cómo quieres llamar a este viaje?",
        }
    
    return state


def _process_budget_config(
    state: ConfigurationAgentState,
    intent: str,
    entities: dict
) -> ConfigurationAgentState:
    """Process budget configuration flow."""
    flow_data = state.get("flow_data", {}).copy()
    pending_field = state.get("pending_field")
    message = state.get("message_body", "").strip()
    
    # Budget category sequence
    CATEGORY_SEQUENCE = [
        ("category_food", "category_lodging", "🍔 Comida"),
        ("category_lodging", "category_transport", "🏨 Hospedaje"),
        ("category_transport", "category_tourism", "🚕 Transporte"),
        ("category_tourism", "category_gifts", "🎭 Turismo"),
        ("category_gifts", "category_contingency", "🎁 Regalos"),
        ("category_contingency", "confirm_budget", "⚡ Imprevistos"),
    ]
    
    # Start budget setup
    if intent == "budget_create":
        return {
            **state,
            "flow_data": {},
            "pending_field": "total_amount",
        }
    
    # Handle total amount
    if pending_field == "total_amount":
        amount = entities.get("amount", message)
        flow_data["total_amount"] = _parse_amount(amount)
        return {
            **state,
            "flow_data": flow_data,
            "pending_field": "category_food",
        }
    
    # Handle category allocations
    for current, next_field, label in CATEGORY_SEQUENCE:
        if pending_field == current:
            amount = entities.get("amount", message)
            flow_data[current] = _parse_amount(amount)
            return {
                **state,
                "flow_data": flow_data,
                "pending_field": next_field,
            }
    
    # Handle confirmation
    if intent == "confirm" and pending_field == "confirm_budget":
        return {
            **state,
            "flow_data": flow_data,
            "pending_field": None,
            "current_flow": "general",
            "should_persist": True,
            "persist_type": "budget_create",
            "persist_data": flow_data,
        }
    
    if intent == "deny" and pending_field == "confirm_budget":
        return {
            **state,
            "flow_data": {},
            "pending_field": "total_amount",
            "response_text": "Ok, empecemos de nuevo. ¿Cuál es el monto total del presupuesto?",
        }
    
    return state


def _parse_amount(value: str) -> str:
    """Parse amount string, removing currency symbols and formatting."""
    if not value:
        return "0"
    # Remove common currency symbols and formatting
    cleaned = value.replace("$", "").replace(",", "").replace(".", "").strip()
    # Keep only digits
    digits = "".join(c for c in cleaned if c.isdigit())
    return digits if digits else "0"


def _process_card_setup(
    state: ConfigurationAgentState,
    intent: str,
    entities: dict
) -> ConfigurationAgentState:
    """Process card setup flow."""
    flow_data = state.get("flow_data", {}).copy()
    pending_field = state.get("pending_field")
    
    # Start card setup
    if intent == "card_add":
        return {
            **state,
            "flow_data": {},
            "pending_field": "card_type",
        }
    
    # TODO: Handle card setup steps
    
    return state


def _process_general(
    state: ConfigurationAgentState,
    intent: str,
    entities: dict
) -> ConfigurationAgentState:
    """Process general conversation (no active flow)."""
    
    # Route to new flow based on intent
    if intent == "trip_create":
        return {
            **state,
            "current_flow": "trip_setup",
            "flow_data": {},
            "pending_field": "trip_name",
        }
    
    if intent == "budget_create":
        return {
            **state,
            "current_flow": "budget_config",
            "flow_data": {},
            "pending_field": "total_amount",
        }
    
    if intent == "card_add":
        return {
            **state,
            "current_flow": "card_setup",
            "flow_data": {},
            "pending_field": "card_type",
        }
    
    if intent == "help":
        return {
            **state,
            "response_text": None,  # Let response node generate help
        }
    
    # Default - general response
    return state


def _process_unknown(
    state: ConfigurationAgentState,
    intent: str,
    entities: dict
) -> ConfigurationAgentState:
    """Process unknown flow state."""
    # If user needs onboarding, start it
    if not state.get("onboarding_completed"):
        return {
            **state,
            "current_flow": "onboarding",
            "pending_field": "name",
        }
    
    # Otherwise, go to general
    return {
        **state,
        "current_flow": "general",
    }

