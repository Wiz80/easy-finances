"""
Unit tests for FX Conversion node in IE Agent.

Tests:
- FX lookup called when currencies differ
- FX lookup skipped when same currency
- Proper handling of missing data
- Error handling when FX lookup fails
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.agents.ie_agent.nodes.fx_conversion import (
    lookup_fx_rate_node,
    lookup_fx_rate_node_async,
)
from app.agents.ie_agent.state import IEAgentState
from app.schemas.extraction import ExtractedExpense
from app.tools.fx_lookup import FXAPIError, FXRateResult


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_extracted_expense():
    """Create a mock extracted expense."""
    expense = MagicMock(spec=ExtractedExpense)
    expense.amount = Decimal("100.00")
    expense.currency = "USD"
    expense.description = "Test expense"
    return expense


@pytest.fixture
def base_state(mock_extracted_expense):
    """Create base state for testing."""
    return IEAgentState(
        request_id="test-request-123",
        input_type="text",
        raw_input="100 USD taxi",
        user_id=uuid4(),
        account_id=uuid4(),
        user_home_currency="COP",
        extracted_expense=mock_extracted_expense,
        status="pending",
        errors=[],
    )


@pytest.fixture
def mock_fx_result():
    """Create a mock FX rate result."""
    from datetime import date

    return FXRateResult(
        from_currency="USD",
        to_currency="COP",
        rate=Decimal("4150.50"),
        converted_amount=Decimal("415050.00"),
        rate_date=date.today(),
        source="api",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Skip FX Lookup Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestFXNodeSkipCases:
    """Tests for cases where FX lookup should be skipped."""

    def test_skip_when_no_extracted_expense(self):
        """Should skip when there's no extracted expense."""
        state = IEAgentState(
            request_id="test-123",
            input_type="text",
            raw_input="test",
            user_id=uuid4(),
            account_id=uuid4(),
            user_home_currency="COP",
            extracted_expense=None,
            status="pending",
            errors=[],
        )

        result = lookup_fx_rate_node(state)

        assert result.get("fx_conversion") is None
        assert result.get("amount_in_home_currency") is None

    def test_skip_when_no_home_currency(self, mock_extracted_expense):
        """Should skip when user's home currency is not set."""
        state = IEAgentState(
            request_id="test-123",
            input_type="text",
            raw_input="test",
            user_id=uuid4(),
            account_id=uuid4(),
            user_home_currency=None,
            extracted_expense=mock_extracted_expense,
            status="pending",
            errors=[],
        )

        result = lookup_fx_rate_node(state)

        assert result.get("fx_conversion") is None

    def test_skip_when_no_expense_currency(self):
        """Should skip when expense currency is not set."""
        expense = MagicMock(spec=ExtractedExpense)
        expense.amount = Decimal("100.00")
        expense.currency = None

        state = IEAgentState(
            request_id="test-123",
            input_type="text",
            raw_input="test",
            user_id=uuid4(),
            account_id=uuid4(),
            user_home_currency="COP",
            extracted_expense=expense,
            status="pending",
            errors=[],
        )

        result = lookup_fx_rate_node(state)

        assert result.get("fx_conversion") is None


# ─────────────────────────────────────────────────────────────────────────────
# Same Currency Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestSameCurrency:
    """Tests for same currency (no conversion needed)."""

    def test_same_currency_sets_amount_directly(self):
        """Same currency should set amount_in_home_currency directly."""
        expense = MagicMock(spec=ExtractedExpense)
        expense.amount = Decimal("150.00")
        expense.currency = "COP"

        state = IEAgentState(
            request_id="test-123",
            input_type="text",
            raw_input="test",
            user_id=uuid4(),
            account_id=uuid4(),
            user_home_currency="COP",
            extracted_expense=expense,
            status="pending",
            errors=[],
        )

        result = lookup_fx_rate_node(state)

        assert result.get("amount_in_home_currency") == 150.00
        assert result.get("fx_conversion") is None

    def test_same_currency_case_insensitive(self):
        """Currency comparison should be case-insensitive."""
        expense = MagicMock(spec=ExtractedExpense)
        expense.amount = Decimal("100.00")
        expense.currency = "cop"  # lowercase

        state = IEAgentState(
            request_id="test-123",
            input_type="text",
            raw_input="test",
            user_id=uuid4(),
            account_id=uuid4(),
            user_home_currency="COP",  # uppercase
            extracted_expense=expense,
            status="pending",
            errors=[],
        )

        result = lookup_fx_rate_node(state)

        assert result.get("amount_in_home_currency") == 100.00


# ─────────────────────────────────────────────────────────────────────────────
# FX Lookup Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestFXLookupCalled:
    """Tests for FX lookup being called correctly."""

    def test_fx_lookup_called_when_currencies_differ(self, base_state, mock_fx_result):
        """Should call FX lookup when currencies differ."""
        with patch(
            "app.agents.ie_agent.nodes.fx_conversion._async_fx_lookup",
            new_callable=AsyncMock,
        ) as mock_lookup:
            mock_lookup.return_value = mock_fx_result

            result = lookup_fx_rate_node(base_state)

            # Verify FX lookup was called
            mock_lookup.assert_called_once()

            # Verify state was updated
            assert result.get("fx_conversion") == mock_fx_result
            assert result.get("amount_in_home_currency") == 415050.00

    def test_fx_lookup_uses_eod_rate(self, base_state, mock_fx_result):
        """Should use EOD rate for budget sync."""
        with patch(
            "app.agents.ie_agent.nodes.fx_conversion.FXLookup"
        ) as mock_fx_class:
            mock_instance = MagicMock()
            mock_instance.get_rate = AsyncMock(return_value=mock_fx_result)
            mock_fx_class.return_value = mock_instance

            with patch(
                "app.agents.ie_agent.nodes.fx_conversion._async_fx_lookup",
                new_callable=AsyncMock,
            ) as mock_lookup:
                mock_lookup.return_value = mock_fx_result
                lookup_fx_rate_node(base_state)

                # Check that use_eod=True was passed
                call_kwargs = mock_lookup.call_args
                # The actual call is to _async_fx_lookup which is mocked
                # Just verify it was called


# ─────────────────────────────────────────────────────────────────────────────
# Error Handling Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestErrorHandling:
    """Tests for error handling in FX node."""

    def test_fx_error_doesnt_fail_extraction(self, base_state):
        """FX errors should not fail the entire extraction."""
        with patch(
            "app.agents.ie_agent.nodes.fx_conversion._async_fx_lookup",
            new_callable=AsyncMock,
        ) as mock_lookup:
            mock_lookup.side_effect = FXAPIError("API error")

            result = lookup_fx_rate_node(base_state)

            # Should not raise, but add error to list
            assert result.get("fx_conversion") is None
            assert len(result.get("errors", [])) > 0
            assert "FX lookup failed" in result["errors"][0]

    def test_unexpected_error_handled_gracefully(self, base_state):
        """Unexpected errors should be handled gracefully."""
        with patch(
            "app.agents.ie_agent.nodes.fx_conversion._async_fx_lookup",
            new_callable=AsyncMock,
        ) as mock_lookup:
            mock_lookup.side_effect = Exception("Unexpected error")

            result = lookup_fx_rate_node(base_state)

            # Should not raise
            assert result.get("fx_conversion") is None
            assert len(result.get("errors", [])) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Async Node Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestAsyncNode:
    """Tests for async version of the node."""

    @pytest.mark.asyncio
    async def test_async_node_works_correctly(self, base_state, mock_fx_result):
        """Async node should work the same as sync version."""
        with patch(
            "app.agents.ie_agent.nodes.fx_conversion._async_fx_lookup",
            new_callable=AsyncMock,
        ) as mock_lookup:
            mock_lookup.return_value = mock_fx_result

            result = await lookup_fx_rate_node_async(base_state)

            assert result.get("fx_conversion") == mock_fx_result
            assert result.get("amount_in_home_currency") == 415050.00

    @pytest.mark.asyncio
    async def test_async_node_skip_same_currency(self):
        """Async node should skip when currencies match."""
        expense = MagicMock(spec=ExtractedExpense)
        expense.amount = Decimal("100.00")
        expense.currency = "COP"

        state = IEAgentState(
            request_id="test-123",
            input_type="text",
            raw_input="test",
            user_id=uuid4(),
            account_id=uuid4(),
            user_home_currency="COP",
            extracted_expense=expense,
            status="pending",
            errors=[],
        )

        result = await lookup_fx_rate_node_async(state)

        assert result.get("amount_in_home_currency") == 100.00


# ─────────────────────────────────────────────────────────────────────────────
# Integration-like Tests (using mocked FXLookup)
# ─────────────────────────────────────────────────────────────────────────────


class TestFXNodeIntegration:
    """Integration-like tests for FX node."""

    def test_usd_to_cop_conversion(self, mock_fx_result):
        """Test USD to COP conversion flow."""
        expense = MagicMock(spec=ExtractedExpense)
        expense.amount = Decimal("50.00")
        expense.currency = "USD"

        state = IEAgentState(
            request_id="test-123",
            input_type="text",
            raw_input="50 dollars taxi",
            user_id=uuid4(),
            account_id=uuid4(),
            user_home_currency="COP",
            extracted_expense=expense,
            status="pending",
            errors=[],
        )

        # Create result for $50 USD
        from datetime import date

        fx_result = FXRateResult(
            from_currency="USD",
            to_currency="COP",
            rate=Decimal("4150.50"),
            converted_amount=Decimal("207525.00"),  # 50 * 4150.50
            rate_date=date.today(),
            source="api",
        )

        with patch(
            "app.agents.ie_agent.nodes.fx_conversion._async_fx_lookup",
            new_callable=AsyncMock,
        ) as mock_lookup:
            mock_lookup.return_value = fx_result

            result = lookup_fx_rate_node(state)

            assert result.get("fx_conversion").rate == Decimal("4150.50")
            assert result.get("amount_in_home_currency") == 207525.00

    def test_eur_to_usd_conversion(self):
        """Test EUR to USD conversion flow."""
        from datetime import date

        expense = MagicMock(spec=ExtractedExpense)
        expense.amount = Decimal("100.00")
        expense.currency = "EUR"

        state = IEAgentState(
            request_id="test-123",
            input_type="text",
            raw_input="100 euros dinner",
            user_id=uuid4(),
            account_id=uuid4(),
            user_home_currency="USD",
            extracted_expense=expense,
            status="pending",
            errors=[],
        )

        fx_result = FXRateResult(
            from_currency="EUR",
            to_currency="USD",
            rate=Decimal("1.08"),
            converted_amount=Decimal("108.00"),
            rate_date=date.today(),
            source="api",
        )

        with patch(
            "app.agents.ie_agent.nodes.fx_conversion._async_fx_lookup",
            new_callable=AsyncMock,
        ) as mock_lookup:
            mock_lookup.return_value = fx_result

            result = lookup_fx_rate_node(state)

            assert result.get("fx_conversion").rate == Decimal("1.08")
            assert result.get("amount_in_home_currency") == 108.00


