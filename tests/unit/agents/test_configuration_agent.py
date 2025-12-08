"""Unit tests for Configuration Agent nodes and state."""

import uuid
from datetime import datetime

import pytest

from app.agents.configuration_agent.state import (
    ConfigurationAgentState,
    create_initial_state,
)
from app.agents.configuration_agent.nodes.intent import (
    _quick_intent_detection,
    _parse_llm_response,
)
from app.agents.configuration_agent.nodes.processor import (
    _parse_amount,
    _process_onboarding,
    _process_general,
)


class TestCreateInitialState:
    """Tests for create_initial_state function."""

    def test_creates_state_with_required_fields(self):
        """Should create state with all required fields."""
        user_id = uuid.uuid4()
        
        state = create_initial_state(
            user_id=user_id,
            phone_number="+573115084628",
            message_body="Hola",
        )
        
        assert state["user_id"] == user_id
        assert state["phone_number"] == "+573115084628"
        assert state["message_body"] == "Hola"
        assert state["status"] == "processing"
        assert state["current_flow"] == "unknown"
        assert state["flow_data"] == {}
        assert state["errors"] == []

    def test_creates_state_with_optional_fields(self):
        """Should include optional fields when provided."""
        user_id = uuid.uuid4()
        conv_id = uuid.uuid4()
        
        state = create_initial_state(
            user_id=user_id,
            phone_number="+573115084628",
            message_body="Test",
            conversation_id=conv_id,
            current_flow="trip_setup",
            flow_data={"partial": "data"},
            user_name="Harrison",
            home_currency="COP",
            onboarding_completed=True,
        )
        
        assert state["conversation_id"] == conv_id
        assert state["current_flow"] == "trip_setup"
        assert state["flow_data"] == {"partial": "data"}
        assert state["user_name"] == "Harrison"
        assert state["home_currency"] == "COP"
        assert state["onboarding_completed"] is True


class TestQuickIntentDetection:
    """Tests for quick intent detection patterns."""

    def test_detects_confirmation(self):
        """Should detect confirmation intents."""
        test_cases = ["sí", "si", "yes", "ok", "dale", "correcto"]
        
        for msg in test_cases:
            result = _quick_intent_detection(msg, "general", None)
            assert result is not None, f"Failed for: {msg}"
            assert result["intent"] == "confirm"

    def test_detects_denial(self):
        """Should detect denial intents."""
        test_cases = ["no", "cancelar", "cambiar"]
        
        for msg in test_cases:
            result = _quick_intent_detection(msg, "general", None)
            assert result is not None, f"Failed for: {msg}"
            assert result["intent"] == "deny"

    def test_detects_help(self):
        """Should detect help requests."""
        test_cases = ["ayuda", "help", "?"]
        
        for msg in test_cases:
            result = _quick_intent_detection(msg, "general", None)
            assert result is not None, f"Failed for: {msg}"
            assert result["intent"] == "help"

    def test_detects_greeting(self):
        """Should detect greetings."""
        test_cases = ["hola", "hi", "hello", "buenas"]
        
        for msg in test_cases:
            result = _quick_intent_detection(msg, "general", None)
            assert result is not None, f"Failed for: {msg}"
            assert result["intent"] == "greeting"

    def test_detects_trip_creation(self):
        """Should detect trip creation intent."""
        test_cases = ["nuevo viaje", "crear viaje", "configurar viaje"]
        
        for msg in test_cases:
            result = _quick_intent_detection(msg, "general", None)
            assert result is not None, f"Failed for: {msg}"
            assert result["intent"] == "trip_create"

    def test_detects_currency_during_onboarding(self):
        """Should detect currency codes during onboarding."""
        test_cases = [("COP", "COP"), ("usd", "USD"), ("MXN", "MXN")]
        
        for msg, expected in test_cases:
            result = _quick_intent_detection(msg, "onboarding", None)
            assert result is not None, f"Failed for: {msg}"
            assert result["intent"] == "onboarding_provide_currency"
            assert result["entities"]["currency"] == expected

    def test_returns_none_for_complex_messages(self):
        """Should return None for messages needing LLM analysis."""
        complex_messages = [
            "Quiero ir a Ecuador del 15 al 30 de diciembre",
            "Tengo una tarjeta Visa de Bancolombia",
            "Me gustaría saber cuánto he gastado esta semana",
        ]
        
        for msg in complex_messages:
            result = _quick_intent_detection(msg, "general", None)
            assert result is None, f"Should be None for: {msg}"
    
    def test_detects_budget_keyword(self):
        """Should detect budget-related messages."""
        result = _quick_intent_detection("Mi presupuesto es de 5 millones", "general", None)
        assert result is not None
        assert result["intent"] == "budget_create"


class TestParseLlmResponse:
    """Tests for LLM response parsing."""

    def test_parses_valid_json(self):
        """Should parse valid JSON response."""
        content = '{"intent": "trip_create", "entities": {"name": "Ecuador"}, "confidence": 0.9}'
        
        result = _parse_llm_response(content)
        
        assert result["intent"] == "trip_create"
        assert result["entities"]["name"] == "Ecuador"
        assert result["confidence"] == 0.9

    def test_parses_json_in_code_block(self):
        """Should parse JSON from markdown code block."""
        content = '''Here's the analysis:
```json
{"intent": "budget_create", "entities": {}, "confidence": 0.8}
```
'''
        result = _parse_llm_response(content)
        
        assert result["intent"] == "budget_create"

    def test_returns_unknown_for_invalid_json(self):
        """Should return unknown for invalid JSON."""
        content = "I don't understand the question"
        
        result = _parse_llm_response(content)
        
        assert result["intent"] == "unknown"


class TestParseAmount:
    """Tests for amount parsing."""

    def test_parses_simple_numbers(self):
        """Should parse simple numeric strings."""
        assert _parse_amount("5000000") == "5000000"
        assert _parse_amount("100") == "100"

    def test_removes_currency_symbols(self):
        """Should remove currency symbols."""
        assert _parse_amount("$5000000") == "5000000"
        assert _parse_amount("$1,500,000") == "1500000"

    def test_removes_formatting(self):
        """Should remove commas and dots used for formatting."""
        assert _parse_amount("1,500,000") == "1500000"
        assert _parse_amount("1.500.000") == "1500000"

    def test_handles_empty_input(self):
        """Should return 0 for empty input."""
        assert _parse_amount("") == "0"
        assert _parse_amount(None) == "0"


class TestProcessOnboarding:
    """Tests for onboarding flow processor."""

    def test_greeting_starts_name_collection(self):
        """Should ask for name after greeting."""
        state = ConfigurationAgentState(
            user_id=uuid.uuid4(),
            phone_number="+573115084628",
            message_body="Hola",
            current_flow="onboarding",
            flow_data={},
            detected_intent="greeting",
            extracted_entities={},
            onboarding_completed=False,
        )
        
        result = _process_onboarding(state, "greeting", {})
        
        assert result.get("pending_field") == "name"

    def test_name_provision_moves_to_currency(self):
        """Should move to currency after name provided."""
        state = ConfigurationAgentState(
            user_id=uuid.uuid4(),
            phone_number="+573115084628",
            message_body="Harrison",
            current_flow="onboarding",
            flow_data={},
            pending_field="name",
            detected_intent="onboarding_provide_name",
            extracted_entities={"name": "Harrison"},
            onboarding_completed=False,
        )
        
        result = _process_onboarding(state, "onboarding_provide_name", {"name": "Harrison"})
        
        assert result["flow_data"]["name"] == "Harrison"
        assert result["pending_field"] == "currency"

    def test_currency_provision_moves_to_timezone(self):
        """Should move to timezone after currency provided."""
        state = ConfigurationAgentState(
            user_id=uuid.uuid4(),
            phone_number="+573115084628",
            message_body="COP",
            current_flow="onboarding",
            flow_data={"name": "Harrison"},
            pending_field="currency",
            detected_intent="onboarding_provide_currency",
            extracted_entities={"currency": "COP"},
            onboarding_completed=False,
        )
        
        result = _process_onboarding(state, "onboarding_provide_currency", {"currency": "COP"})
        
        assert result["flow_data"]["currency"] == "COP"
        assert result["pending_field"] == "timezone"


class TestProcessGeneral:
    """Tests for general flow processor."""

    def test_trip_create_starts_trip_flow(self):
        """Should switch to trip_setup flow."""
        state = ConfigurationAgentState(
            user_id=uuid.uuid4(),
            phone_number="+573115084628",
            message_body="Nuevo viaje",
            current_flow="general",
            flow_data={},
            detected_intent="trip_create",
            extracted_entities={},
            onboarding_completed=True,
        )
        
        result = _process_general(state, "trip_create", {})
        
        assert result["current_flow"] == "trip_setup"
        assert result["pending_field"] == "trip_name"

    def test_budget_create_starts_budget_flow(self):
        """Should switch to budget_config flow."""
        state = ConfigurationAgentState(
            user_id=uuid.uuid4(),
            phone_number="+573115084628",
            message_body="Configurar presupuesto",
            current_flow="general",
            flow_data={},
            detected_intent="budget_create",
            extracted_entities={},
            onboarding_completed=True,
        )
        
        result = _process_general(state, "budget_create", {})
        
        assert result["current_flow"] == "budget_config"
        assert result["pending_field"] == "total_amount"

