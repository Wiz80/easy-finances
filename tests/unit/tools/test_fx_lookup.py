"""
Unit tests for FX Lookup tool.

Tests:
- Cache hits and misses
- API calls (mocked)
- Currency conversion
- Error handling
- EOD rate caching
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tools.fx_lookup import (
    FXAPIError,
    FXLookup,
    FXLookupError,
    FXRateNotFoundError,
    FXRateResult,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def fx_lookup():
    """Create FX Lookup instance without Redis."""
    return FXLookup(redis_client=None)


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    redis = MagicMock()
    redis.get.return_value = None
    redis.setex.return_value = True
    return redis


@pytest.fixture
def fx_lookup_with_redis(mock_redis):
    """Create FX Lookup instance with mocked Redis."""
    return FXLookup(redis_client=mock_redis)


# ─────────────────────────────────────────────────────────────────────────────
# Basic Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestFXRateResult:
    """Tests for FXRateResult dataclass."""

    def test_to_dict(self):
        """Test serialization to dictionary."""
        from datetime import date

        result = FXRateResult(
            from_currency="USD",
            to_currency="COP",
            rate=Decimal("4150.50"),
            converted_amount=Decimal("415050.00"),
            rate_date=date(2026, 1, 30),
            source="api",
        )

        d = result.to_dict()

        assert d["from_currency"] == "USD"
        assert d["to_currency"] == "COP"
        assert d["rate"] == "4150.50"
        assert d["converted_amount"] == "415050.00"
        assert d["rate_date"] == "2026-01-30"
        assert d["source"] == "api"

    def test_to_dict_no_amount(self):
        """Test serialization when converted_amount is None."""
        from datetime import date

        result = FXRateResult(
            from_currency="USD",
            to_currency="EUR",
            rate=Decimal("0.92"),
            converted_amount=None,
            rate_date=date(2026, 1, 30),
            source="cache",
        )

        d = result.to_dict()

        assert d["converted_amount"] is None


# ─────────────────────────────────────────────────────────────────────────────
# Same Currency Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestSameCurrency:
    """Tests for same currency (no conversion needed)."""

    @pytest.mark.asyncio
    async def test_same_currency_returns_identity(self, fx_lookup):
        """Same currency should return rate of 1."""
        result = await fx_lookup.get_rate("USD", "USD", Decimal("100"))

        assert result.rate == Decimal("1")
        assert result.converted_amount == Decimal("100")
        assert result.source == "identity"

    @pytest.mark.asyncio
    async def test_same_currency_case_insensitive(self, fx_lookup):
        """Currency comparison should be case-insensitive."""
        result = await fx_lookup.get_rate("usd", "USD", Decimal("50"))

        assert result.rate == Decimal("1")
        assert result.converted_amount == Decimal("50")

    @pytest.mark.asyncio
    async def test_same_currency_with_whitespace(self, fx_lookup):
        """Currency comparison should trim whitespace."""
        result = await fx_lookup.get_rate(" USD ", "  USD", Decimal("75"))

        assert result.rate == Decimal("1")


# ─────────────────────────────────────────────────────────────────────────────
# Cache Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestCache:
    """Tests for caching behavior."""

    @pytest.mark.asyncio
    async def test_get_rate_from_cache(self, mock_redis):
        """Should return cached rate when available."""
        # Setup cache hit
        mock_redis.get.return_value = "4150.50"

        fx_lookup = FXLookup(redis_client=mock_redis)
        result = await fx_lookup.get_rate("USD", "COP", Decimal("100"))

        assert result.rate == Decimal("4150.50")
        assert result.converted_amount == Decimal("415050.00")
        assert result.source == "cache"

        # Verify cache was queried
        mock_redis.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_eod_rate_uses_different_cache_key(self, mock_redis):
        """EOD rates should use a different cache key."""
        from datetime import date

        mock_redis.get.return_value = "4150.50"

        fx_lookup = FXLookup(redis_client=mock_redis)

        # Regular rate
        await fx_lookup.get_rate("USD", "COP", use_eod=False)
        call1 = mock_redis.get.call_args_list[0][0][0]

        mock_redis.get.reset_mock()

        # EOD rate
        await fx_lookup.get_rate("USD", "COP", use_eod=True)
        call2 = mock_redis.get.call_args_list[0][0][0]

        # Keys should be different
        assert call1 != call2
        assert "eod" in call2
        assert date.today().isoformat() in call2

    @pytest.mark.asyncio
    async def test_memory_cache_fallback(self, fx_lookup):
        """Should use memory cache when Redis is not available."""
        # Clear any existing memory cache
        FXLookup._memory_cache.clear()

        # Mock the API call
        with patch.object(fx_lookup, "_fetch_rate_from_api", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = Decimal("4150.50")

            # First call - should hit API
            result1 = await fx_lookup.get_rate("USD", "COP")
            assert result1.source == "api"
            assert mock_api.call_count == 1

            # Second call - should hit memory cache
            result2 = await fx_lookup.get_rate("USD", "COP")
            assert result2.source == "cache"
            assert mock_api.call_count == 1  # No additional API call

    @pytest.mark.asyncio
    async def test_cache_stores_rate_after_api_call(self, mock_redis):
        """Rate should be cached after API fetch."""
        mock_redis.get.return_value = None  # Cache miss

        fx_lookup = FXLookup(redis_client=mock_redis)

        with patch.object(fx_lookup, "_fetch_rate_from_api", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = Decimal("4150.50")

            await fx_lookup.get_rate("USD", "COP")

            # Verify rate was cached
            mock_redis.setex.assert_called_once()
            call_args = mock_redis.setex.call_args
            assert "4150.50" in str(call_args)


# ─────────────────────────────────────────────────────────────────────────────
# API Tests (Mocked)
# ─────────────────────────────────────────────────────────────────────────────


class TestAPICall:
    """Tests for API calls (mocked)."""

    @pytest.mark.asyncio
    async def test_get_rate_from_api(self, fx_lookup):
        """Should fetch rate from API when not cached."""
        # Clear memory cache to ensure we hit API
        FXLookup._memory_cache.clear()

        with patch.object(fx_lookup, "_fetch_rate_from_api", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = Decimal("4150.50")

            result = await fx_lookup.get_rate("USD", "COP", Decimal("100"))

            assert result.rate == Decimal("4150.50")
            assert result.converted_amount == Decimal("415050.00")
            assert result.source == "api"
            mock_api.assert_called_once_with("USD", "COP")

    @pytest.mark.asyncio
    async def test_api_error_no_api_key(self, fx_lookup):
        """Should raise error when API key is not configured."""
        # Clear memory cache
        FXLookup._memory_cache.clear()

        # Temporarily remove API key
        original_key = fx_lookup.api_key
        fx_lookup.api_key = ""

        try:
            with pytest.raises(FXAPIError) as exc_info:
                await fx_lookup.get_rate("USD", "COP")

            assert "API key not configured" in str(exc_info.value)
        finally:
            fx_lookup.api_key = original_key

    @pytest.mark.asyncio
    async def test_get_rate_with_amount_conversion(self, fx_lookup):
        """Should correctly convert amount."""
        with patch.object(fx_lookup, "_fetch_rate_from_api", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = Decimal("0.92")

            result = await fx_lookup.get_rate("USD", "EUR", Decimal("100"))

            assert result.rate == Decimal("0.92")
            assert result.converted_amount == Decimal("92.00")


# ─────────────────────────────────────────────────────────────────────────────
# Convert Method Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestConvertMethod:
    """Tests for the convenience convert method."""

    @pytest.mark.asyncio
    async def test_convert_basic(self, fx_lookup):
        """Test basic amount conversion."""
        with patch.object(fx_lookup, "_fetch_rate_from_api", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = Decimal("4150.50")

            result = await fx_lookup.convert(
                Decimal("100"),
                "USD",
                "COP",
            )

            assert result == Decimal("415050.00")

    @pytest.mark.asyncio
    async def test_convert_same_currency(self, fx_lookup):
        """Convert same currency should return original amount."""
        result = await fx_lookup.convert(Decimal("100"), "USD", "USD")

        assert result == Decimal("100")


# ─────────────────────────────────────────────────────────────────────────────
# Multiple Rates Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestMultipleRates:
    """Tests for fetching multiple rates at once."""

    @pytest.mark.asyncio
    async def test_get_multiple_rates(self, fx_lookup):
        """Should fetch rates for multiple currencies."""
        with patch.object(fx_lookup, "_fetch_rate_from_api", new_callable=AsyncMock) as mock_api:
            # Return different rates for different currencies
            async def mock_fetch(from_curr, to_curr):
                rates = {
                    "COP": Decimal("4150.50"),
                    "EUR": Decimal("0.92"),
                    "MXN": Decimal("17.25"),
                }
                return rates.get(to_curr, Decimal("1"))

            mock_api.side_effect = mock_fetch

            results = await fx_lookup.get_multiple_rates(
                "USD",
                ["COP", "EUR", "MXN"],
            )

            assert len(results) == 3
            assert results["COP"].rate == Decimal("4150.50")
            assert results["EUR"].rate == Decimal("0.92")
            assert results["MXN"].rate == Decimal("17.25")

    @pytest.mark.asyncio
    async def test_get_multiple_rates_partial_failure(self, fx_lookup):
        """Should return partial results if some lookups fail."""
        with patch.object(fx_lookup, "_fetch_rate_from_api", new_callable=AsyncMock) as mock_api:
            async def mock_fetch(from_curr, to_curr):
                if to_curr == "INVALID":
                    raise FXRateNotFoundError("Not found")
                return Decimal("4150.50")

            mock_api.side_effect = mock_fetch

            results = await fx_lookup.get_multiple_rates(
                "USD",
                ["COP", "INVALID", "MXN"],
            )

            # Should have results for valid currencies only
            assert len(results) == 2
            assert "COP" in results
            assert "MXN" in results
            assert "INVALID" not in results


# ─────────────────────────────────────────────────────────────────────────────
# Cache Clear Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestCacheClear:
    """Tests for cache clearing."""

    def test_clear_cache_redis(self, mock_redis):
        """Should clear Redis cache."""
        mock_redis.keys.return_value = ["fx:USD:COP", "fx:EUR:USD"]
        mock_redis.delete.return_value = 2

        fx_lookup = FXLookup(redis_client=mock_redis)
        cleared = fx_lookup.clear_cache()

        assert cleared == 2
        mock_redis.delete.assert_called_once()

    def test_clear_cache_memory(self, fx_lookup):
        """Should clear memory cache."""
        # Clear first to ensure clean state
        FXLookup._memory_cache.clear()

        # Add some items to memory cache
        FXLookup._memory_cache["fx:USD:COP"] = ("4150.50", 9999999999)
        FXLookup._memory_cache["fx:EUR:USD"] = ("1.08", 9999999999)
        FXLookup._memory_cache["other:key"] = ("value", 9999999999)

        cleared = fx_lookup.clear_cache()

        assert cleared == 2
        assert "fx:USD:COP" not in FXLookup._memory_cache
        assert "fx:EUR:USD" not in FXLookup._memory_cache
        assert "other:key" in FXLookup._memory_cache  # Non-FX key preserved


# ─────────────────────────────────────────────────────────────────────────────
# Error Handling Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_rate_not_found_error(self, fx_lookup):
        """Should raise FXRateNotFoundError for unknown currency pair."""
        with patch.object(fx_lookup, "_fetch_rate_from_api", new_callable=AsyncMock) as mock_api:
            mock_api.side_effect = FXRateNotFoundError("Currency pair not found")

            with pytest.raises(FXRateNotFoundError):
                await fx_lookup.get_rate("USD", "INVALID")

    @pytest.mark.asyncio
    async def test_api_error(self, fx_lookup):
        """Should raise FXAPIError on API failure."""
        with patch.object(fx_lookup, "_fetch_rate_from_api", new_callable=AsyncMock) as mock_api:
            mock_api.side_effect = FXAPIError("API error")

            with pytest.raises(FXAPIError):
                await fx_lookup.get_rate("USD", "COP")

    def test_cache_error_doesnt_break_lookup(self, mock_redis, fx_lookup):
        """Cache errors should not break the lookup flow."""
        # Simulate Redis error
        mock_redis.get.side_effect = Exception("Redis connection error")

        # Should still work using memory cache
        # (This tests the graceful degradation)
        fx = FXLookup(redis_client=mock_redis)

        # The cache error is caught and logged, not raised
        with patch.object(fx, "_fetch_rate_from_api", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = Decimal("4150.50")

            # Should not raise despite Redis error
            import asyncio
            result = asyncio.get_event_loop().run_until_complete(
                fx.get_rate("USD", "COP")
            )

            assert result.rate == Decimal("4150.50")


# ─────────────────────────────────────────────────────────────────────────────
# Integration Test (Skipped in CI)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.skip(reason="Requires real API key - run manually")
class TestRealAPI:
    """Integration tests with real API - skip in CI."""

    @pytest.mark.asyncio
    async def test_real_api_call(self):
        """Test real API call - requires EXCHANGE_RATE_API_KEY."""
        fx_lookup = FXLookup()

        result = await fx_lookup.get_rate("USD", "COP", Decimal("100"))

        # Basic sanity checks
        assert result.rate > 0
        assert result.converted_amount is not None
        assert result.converted_amount > Decimal("100")  # COP is worth less than USD
        assert result.source in ("api", "cache")

