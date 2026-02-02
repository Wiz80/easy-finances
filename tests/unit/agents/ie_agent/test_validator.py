"""
Unit tests for IE Agent validator node.

Tests:
- Validation of required fields
- Amount validation (positive, reasonable)
- Currency validation
- Confidence threshold checks
- Routing decisions based on validation
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.agents.ie_agent.nodes.validator import (
    validate_extraction_node,
    get_storage_route,
)
from app.agents.ie_agent.state import IEAgentState
from app.schemas.extraction import ExtractedExpense


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def valid_expense():
    """Create a valid ExtractedExpense."""
    return ExtractedExpense(
        amount=Decimal("50000"),
        currency="COP",
        description="almuerzo en restaurante",
        category_candidate="out_house_food",
        method="cash",
        merchant="McDonald's",
        card_hint=None,
        occurred_at=None,
        notes=None,
        installments=1,
        category_confidence=0.9,
        category_source="llm",
        confidence=0.85,
        raw_input="Gasté 50000 pesos en almuerzo",
    )


@pytest.fixture
def base_state():
    """Create a base state."""
    return {
        "request_id": "test-123",
        "user_id": uuid4(),
        "account_id": uuid4(),
    }


@pytest.fixture
def valid_state(base_state, valid_expense):
    """Create a state with valid extracted expense."""
    return {
        **base_state,
        "extracted_expense": valid_expense,
        "confidence": 0.85,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Required Fields Validation Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestRequiredFieldsValidation:
    """Tests for required fields validation."""

    @patch("app.agents.ie_agent.nodes.validator.settings")
    def test_valid_expense_passes(self, mock_settings, valid_state):
        """Should pass validation for valid expense."""
        mock_settings.confidence_threshold = 0.7
        
        result = validate_extraction_node(valid_state)
        
        assert result["validation_passed"] is True
        assert len([e for e in result["validation_errors"] if "Invalid" in e or "Missing" in e]) == 0

    def test_missing_expense_fails(self, base_state):
        """Should fail validation when no expense extracted."""
        state = {
            **base_state,
            "extracted_expense": None,
            "confidence": 0.0,
        }
        
        result = validate_extraction_node(state)
        
        assert result["validation_passed"] is False
        assert any("No expense data" in e for e in result["validation_errors"])

    @patch("app.agents.ie_agent.nodes.validator.settings")
    def test_zero_amount_fails(self, mock_settings, base_state):
        """Should fail validation for zero amount.
        
        Note: Pydantic already validates amount > 0 at schema level.
        This test uses a mock expense with amount set to 0 after creation.
        """
        mock_settings.confidence_threshold = 0.5
        
        # Create a valid expense first, then modify the amount
        expense = MagicMock()
        expense.amount = Decimal("0")  # Invalid amount
        expense.currency = "USD"
        expense.description = "test"
        
        state = {
            **base_state,
            "extracted_expense": expense,
            "confidence": 0.9,
        }
        
        result = validate_extraction_node(state)
        
        assert result["validation_passed"] is False
        assert any("Invalid amount" in e for e in result["validation_errors"])

    @patch("app.agents.ie_agent.nodes.validator.settings")
    def test_negative_amount_fails(self, mock_settings, base_state):
        """Should fail validation for negative amount.
        
        Note: Pydantic already validates amount > 0 at schema level.
        This test uses a mock expense with amount set to -50 after creation.
        """
        mock_settings.confidence_threshold = 0.5
        
        # Create a mock expense with invalid amount
        expense = MagicMock()
        expense.amount = Decimal("-50")  # Invalid amount
        expense.currency = "USD"
        expense.description = "test"
        
        state = {
            **base_state,
            "extracted_expense": expense,
            "confidence": 0.9,
        }
        
        result = validate_extraction_node(state)
        
        assert result["validation_passed"] is False

    @patch("app.agents.ie_agent.nodes.validator.settings")
    def test_empty_description_fails(self, mock_settings, base_state):
        """Should fail validation for empty description."""
        mock_settings.confidence_threshold = 0.5
        
        expense = ExtractedExpense(
            amount=Decimal("50"),
            currency="USD",
            description="   ",  # Whitespace only
            category_candidate="misc",
            method="cash",
            confidence=0.9,
            raw_input="test",
        )
        
        state = {
            **base_state,
            "extracted_expense": expense,
            "confidence": 0.9,
        }
        
        result = validate_extraction_node(state)
        
        assert result["validation_passed"] is False
        assert any("Missing description" in e for e in result["validation_errors"])


# ─────────────────────────────────────────────────────────────────────────────
# Currency Validation Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestCurrencyValidation:
    """Tests for currency validation."""

    @patch("app.agents.ie_agent.nodes.validator.settings")
    def test_valid_currencies_pass(self, mock_settings, base_state):
        """Should pass validation for known currencies."""
        mock_settings.confidence_threshold = 0.5
        
        for currency in ["USD", "EUR", "COP", "PEN", "MXN"]:
            expense = ExtractedExpense(
                amount=Decimal("50"),
                currency=currency,
                description="test",
                category_candidate="misc",
                method="cash",
                confidence=0.9,
                raw_input="test",
            )
            
            state = {
                **base_state,
                "extracted_expense": expense,
                "confidence": 0.9,
            }
            
            result = validate_extraction_node(state)
            
            # Should not have currency errors
            currency_errors = [e for e in result["validation_errors"] if "currency" in e.lower()]
            assert len(currency_errors) == 0, f"Failed for {currency}"

    @patch("app.agents.ie_agent.nodes.validator.settings")
    def test_invalid_currency_code_length(self, mock_settings, base_state):
        """Should flag invalid currency code length.
        
        Note: Pydantic validates currency length at schema level.
        This test uses a mock expense to bypass Pydantic validation.
        """
        mock_settings.confidence_threshold = 0.5
        
        # Create a mock expense with invalid currency
        expense = MagicMock()
        expense.amount = Decimal("50")
        expense.currency = "USDD"  # 4 chars instead of 3
        expense.description = "test"
        
        state = {
            **base_state,
            "extracted_expense": expense,
            "confidence": 0.9,
        }
        
        result = validate_extraction_node(state)
        
        assert any("Invalid currency" in e for e in result["validation_errors"])

    @patch("app.agents.ie_agent.nodes.validator.settings")
    def test_unknown_currency_flagged(self, mock_settings, base_state):
        """Should flag unknown currency code."""
        mock_settings.confidence_threshold = 0.5
        
        expense = ExtractedExpense(
            amount=Decimal("50"),
            currency="XYZ",  # Unknown currency
            description="test",
            category_candidate="misc",
            method="cash",
            confidence=0.9,
            raw_input="test",
        )
        
        state = {
            **base_state,
            "extracted_expense": expense,
            "confidence": 0.9,
        }
        
        result = validate_extraction_node(state)
        
        assert any("Unknown currency" in e for e in result["validation_errors"])


# ─────────────────────────────────────────────────────────────────────────────
# Amount Limit Validation Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestAmountLimitValidation:
    """Tests for amount limit validation."""

    @patch("app.agents.ie_agent.nodes.validator.settings")
    def test_reasonable_amount_passes(self, mock_settings, valid_state):
        """Should pass validation for reasonable amounts."""
        mock_settings.confidence_threshold = 0.5
        
        result = validate_extraction_node(valid_state)
        
        # Should not have amount limit errors
        limit_errors = [e for e in result["validation_errors"] if "exceeds" in e.lower()]
        assert len(limit_errors) == 0

    @patch("app.agents.ie_agent.nodes.validator.settings")
    def test_exceeding_max_amount_fails(self, mock_settings, base_state):
        """Should fail validation for amount exceeding max."""
        mock_settings.confidence_threshold = 0.5
        
        expense = ExtractedExpense(
            amount=Decimal("99999999999"),  # Very high amount
            currency="USD",
            description="test",
            category_candidate="misc",
            method="cash",
            confidence=0.9,
            raw_input="test",
        )
        
        state = {
            **base_state,
            "extracted_expense": expense,
            "confidence": 0.9,
        }
        
        result = validate_extraction_node(state)
        
        assert result["validation_passed"] is False
        assert any("exceeds maximum" in e for e in result["validation_errors"])


# ─────────────────────────────────────────────────────────────────────────────
# Confidence Threshold Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestConfidenceThreshold:
    """Tests for confidence threshold validation."""

    @patch("app.agents.ie_agent.nodes.validator.settings")
    def test_above_threshold_passes(self, mock_settings, valid_state):
        """Should pass validation when confidence above threshold."""
        mock_settings.confidence_threshold = 0.7
        valid_state["confidence"] = 0.85
        
        result = validate_extraction_node(valid_state)
        
        assert result["validation_passed"] is True
        assert result["status"] == "validating"

    @patch("app.agents.ie_agent.nodes.validator.settings")
    def test_below_threshold_flags_low_confidence(self, mock_settings, valid_state):
        """Should flag low confidence when below threshold."""
        mock_settings.confidence_threshold = 0.9
        valid_state["confidence"] = 0.7
        
        result = validate_extraction_node(valid_state)
        
        # Validation can still pass for non-critical fields
        assert result["status"] == "low_confidence"
        assert any("Confidence" in e and "below threshold" in e for e in result["validation_errors"])

    @patch("app.agents.ie_agent.nodes.validator.settings")
    def test_exactly_at_threshold_passes(self, mock_settings, valid_state):
        """Should pass validation when confidence equals threshold."""
        mock_settings.confidence_threshold = 0.85
        valid_state["confidence"] = 0.85
        
        result = validate_extraction_node(valid_state)
        
        # Equal to threshold should pass (not below)
        # Check that there's no low confidence warning
        low_conf_errors = [e for e in result.get("validation_errors", []) if "Confidence" in e]
        assert len(low_conf_errors) == 0


# ─────────────────────────────────────────────────────────────────────────────
# Status Determination Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestStatusDetermination:
    """Tests for status determination based on validation."""

    def test_missing_expense_sets_error_status(self, base_state):
        """Should set error status for missing expense."""
        state = {
            **base_state,
            "extracted_expense": None,
        }
        
        result = validate_extraction_node(state)
        
        assert result["status"] == "error"

    @patch("app.agents.ie_agent.nodes.validator.settings")
    def test_critical_error_sets_error_status(self, mock_settings, base_state):
        """Should set error status for critical validation failures."""
        mock_settings.confidence_threshold = 0.5
        
        # Create a mock expense with invalid amount
        expense = MagicMock()
        expense.amount = Decimal("0")  # Invalid
        expense.currency = "USD"
        expense.description = "test"
        
        state = {
            **base_state,
            "extracted_expense": expense,
            "confidence": 0.9,
        }
        
        result = validate_extraction_node(state)
        
        assert result["status"] == "error"

    @patch("app.agents.ie_agent.nodes.validator.settings")
    def test_low_confidence_only_sets_low_confidence_status(self, mock_settings, valid_state):
        """Should set low_confidence status when only confidence is low."""
        mock_settings.confidence_threshold = 0.95
        valid_state["confidence"] = 0.7
        
        result = validate_extraction_node(valid_state)
        
        assert result["status"] == "low_confidence"
        assert result["validation_passed"] is True

    @patch("app.agents.ie_agent.nodes.validator.settings")
    def test_valid_expense_sets_validating_status(self, mock_settings, valid_state):
        """Should set validating status for valid expense above threshold."""
        mock_settings.confidence_threshold = 0.7
        valid_state["confidence"] = 0.9
        
        result = validate_extraction_node(valid_state)
        
        assert result["status"] == "validating"


# ─────────────────────────────────────────────────────────────────────────────
# Storage Routing Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestGetStorageRoute:
    """Tests for get_storage_route function."""

    def test_error_status_routes_to_end(self, base_state):
        """Should route to end when status is error."""
        state = {
            **base_state,
            "status": "error",
            "validation_passed": False,
        }
        
        result = get_storage_route(state)
        
        assert result == "end"

    def test_validation_failed_routes_to_end(self, base_state):
        """Should route to end when validation failed."""
        state = {
            **base_state,
            "status": "validating",
            "validation_passed": False,
        }
        
        result = get_storage_route(state)
        
        assert result == "end"

    def test_validation_passed_routes_to_store(self, base_state):
        """Should route to store_expense when validation passed."""
        state = {
            **base_state,
            "status": "validating",
            "validation_passed": True,
        }
        
        result = get_storage_route(state)
        
        assert result == "store_expense"

    def test_low_confidence_routes_to_store(self, base_state):
        """Should route to store even with low confidence if validation passed."""
        state = {
            **base_state,
            "status": "low_confidence",
            "validation_passed": True,
        }
        
        result = get_storage_route(state)
        
        assert result == "store_expense"

    def test_missing_validation_passed_defaults_to_end(self, base_state):
        """Should route to end when validation_passed is not set."""
        state = {
            **base_state,
            "status": "validating",
            # No validation_passed key
        }
        
        result = get_storage_route(state)
        
        assert result == "end"


# ─────────────────────────────────────────────────────────────────────────────
# Edge Cases Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestEdgeCases:
    """Tests for edge cases in validation."""

    @patch("app.agents.ie_agent.nodes.validator.settings")
    def test_very_small_amount_passes(self, mock_settings, base_state):
        """Should pass validation for very small amounts."""
        mock_settings.confidence_threshold = 0.5
        
        expense = ExtractedExpense(
            amount=Decimal("0.01"),  # 1 cent
            currency="USD",
            description="test fee",
            category_candidate="misc",
            method="cash",
            confidence=0.9,
            raw_input="test",
        )
        
        state = {
            **base_state,
            "extracted_expense": expense,
            "confidence": 0.9,
        }
        
        result = validate_extraction_node(state)
        
        assert result["validation_passed"] is True

    @patch("app.agents.ie_agent.nodes.validator.settings")
    def test_borderline_max_amount_passes(self, mock_settings, base_state):
        """Should pass validation for amount at max limit."""
        mock_settings.confidence_threshold = 0.5
        
        expense = ExtractedExpense(
            amount=Decimal("10000000"),  # Exactly at max
            currency="USD",
            description="expensive purchase",
            category_candidate="misc",
            method="card",
            confidence=0.9,
            raw_input="test",
        )
        
        state = {
            **base_state,
            "extracted_expense": expense,
            "confidence": 0.9,
        }
        
        result = validate_extraction_node(state)
        
        # Exactly at max should pass (not exceeding)
        limit_errors = [e for e in result["validation_errors"] if "exceeds" in e.lower()]
        assert len(limit_errors) == 0

    @patch("app.agents.ie_agent.nodes.validator.settings")
    def test_multiple_validation_errors(self, mock_settings, base_state):
        """Should collect all validation errors."""
        mock_settings.confidence_threshold = 0.95
        
        # Create a mock expense with multiple issues
        expense = MagicMock()
        expense.amount = Decimal("0")  # Invalid amount
        expense.currency = "XX"  # Invalid currency (only 2 chars)
        expense.description = " "  # Whitespace only
        
        state = {
            **base_state,
            "extracted_expense": expense,
            "confidence": 0.3,
        }
        
        result = validate_extraction_node(state)
        
        # Should have multiple errors
        assert len(result["validation_errors"]) >= 2
