"""
Unit tests for Coordinator IVR Integration.

Tests the routing of onboarding and configuration flows through IVR.
"""

import pytest

from app.agents.common.intents import (
    AgentType,
    detect_intent_fast,
    detect_ivr_flow,
    IVR_BUDGET_KEYWORDS,
    IVR_TRIP_KEYWORDS,
    IVR_CARD_KEYWORDS,
)


# ─────────────────────────────────────────────────────────────────────────────
# IVR Flow Detection Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestDetectIVRFlow:
    """Tests for detect_ivr_flow function."""

    # Budget Keywords
    def test_detect_budget_crear_presupuesto(self):
        """'crear presupuesto' should detect budget flow."""
        result = detect_ivr_flow("quiero crear presupuesto")
        assert result == "budget"

    def test_detect_budget_nuevo_presupuesto(self):
        """'nuevo presupuesto' should detect budget flow."""
        result = detect_ivr_flow("nuevo presupuesto por favor")
        assert result == "budget"

    def test_detect_budget_configurar_presupuesto(self):
        """'configurar presupuesto' should detect budget flow."""
        result = detect_ivr_flow("necesito configurar presupuesto")
        assert result == "budget"

    # Trip Keywords
    def test_detect_trip_nuevo_viaje(self):
        """'nuevo viaje' should detect trip flow."""
        result = detect_ivr_flow("quiero crear un nuevo viaje")
        assert result == "trip"

    def test_detect_trip_modo_viaje(self):
        """'modo viaje' should detect trip flow."""
        result = detect_ivr_flow("activar modo viaje")
        assert result == "trip"

    def test_detect_trip_voy_a_viajar(self):
        """'voy a viajar' should detect trip flow."""
        result = detect_ivr_flow("voy a viajar la próxima semana")
        assert result == "trip"

    # Card Keywords
    def test_detect_card_nueva_tarjeta(self):
        """'nueva tarjeta' should detect card flow."""
        result = detect_ivr_flow("agregar nueva tarjeta")
        assert result == "card"

    def test_detect_card_configurar_tarjeta(self):
        """'configurar tarjeta' should detect card flow."""
        result = detect_ivr_flow("quiero configurar tarjeta")
        assert result == "card"

    # No match
    def test_no_ivr_flow_detected(self):
        """Regular text should not detect IVR flow."""
        result = detect_ivr_flow("hola como estas")
        assert result is None

    def test_expense_not_ivr_flow(self):
        """Expense text should not detect IVR flow."""
        result = detect_ivr_flow("gasté 50000 en almuerzo")
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# Intent Detection with IVR Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestDetectIntentFastWithIVR:
    """Tests for detect_intent_fast including IVR detection."""

    def test_ivr_budget_returns_ivr_agent(self):
        """Budget keywords should return IVR agent."""
        result = detect_intent_fast("crear presupuesto")
        assert result == AgentType.IVR

    def test_ivr_trip_returns_ivr_agent(self):
        """Trip keywords should return IVR agent."""
        result = detect_intent_fast("nuevo viaje a México")
        assert result == AgentType.IVR

    def test_ivr_card_returns_ivr_agent(self):
        """Card keywords should return IVR agent."""
        result = detect_intent_fast("configurar tarjeta visa")
        assert result == AgentType.IVR

    def test_expense_returns_ie_agent(self):
        """Expense should still return IE agent."""
        result = detect_intent_fast("gasté 50000 pesos en uber")
        assert result == AgentType.IE

    def test_query_returns_coach_agent(self):
        """Query should still return COACH agent."""
        # Use a clear query with multiple query keywords
        result = detect_intent_fast("cuánto gasté en total este mes, muéstrame el resumen")
        assert result == AgentType.COACH

    def test_config_keywords_redirect_to_ivr(self):
        """Config keywords should now redirect to IVR."""
        # Generic config keywords should use IVR for simplicity
        result = detect_intent_fast("quiero configurar mi cuenta")
        assert result == AgentType.IVR


# ─────────────────────────────────────────────────────────────────────────────
# IVR Keywords Coverage Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestIVRKeywordsCoverage:
    """Tests to ensure all IVR keywords work."""

    @pytest.mark.parametrize("keyword", IVR_BUDGET_KEYWORDS)
    def test_all_budget_keywords(self, keyword: str):
        """All budget keywords should detect budget flow."""
        result = detect_ivr_flow(keyword)
        assert result == "budget", f"Keyword '{keyword}' should detect budget"

    @pytest.mark.parametrize("keyword", IVR_TRIP_KEYWORDS)
    def test_all_trip_keywords(self, keyword: str):
        """All trip keywords should detect trip flow."""
        result = detect_ivr_flow(keyword)
        assert result == "trip", f"Keyword '{keyword}' should detect trip"

    @pytest.mark.parametrize("keyword", IVR_CARD_KEYWORDS)
    def test_all_card_keywords(self, keyword: str):
        """All card keywords should detect card flow."""
        result = detect_ivr_flow(keyword)
        assert result == "card", f"Keyword '{keyword}' should detect card"


# ─────────────────────────────────────────────────────────────────────────────
# Case Insensitivity Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestCaseInsensitivity:
    """Tests for case-insensitive keyword detection."""

    def test_uppercase_budget(self):
        """Uppercase should work."""
        result = detect_ivr_flow("CREAR PRESUPUESTO")
        assert result == "budget"

    def test_mixed_case_trip(self):
        """Mixed case should work."""
        result = detect_ivr_flow("Nuevo Viaje")
        assert result == "trip"

    def test_lowercase_card(self):
        """Lowercase should work."""
        result = detect_ivr_flow("nueva tarjeta")
        assert result == "card"

