"""
FX Rate Lookup Tool.

Provides real-time and end-of-day exchange rate lookups with caching.
Uses Exchange Rate API (exchangerate-api.com) as the data source.

Usage:
    >>> fx_lookup = FXLookup()
    >>> result = await fx_lookup.get_rate("USD", "COP", amount=Decimal("100"))
    >>> print(result.converted_amount)  # ~415000 COP
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import httpx

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class FXLookupError(Exception):
    """Base exception for FX lookup errors."""

    pass


class FXRateNotFoundError(FXLookupError):
    """Raised when exchange rate cannot be found."""

    pass


class FXAPIError(FXLookupError):
    """Raised when API call fails."""

    pass


@dataclass
class FXRateResult:
    """Result of an FX rate lookup."""

    from_currency: str
    to_currency: str
    rate: Decimal
    converted_amount: Decimal | None
    rate_date: date
    source: str  # "cache" | "api"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "from_currency": self.from_currency,
            "to_currency": self.to_currency,
            "rate": str(self.rate),
            "converted_amount": str(self.converted_amount) if self.converted_amount else None,
            "rate_date": self.rate_date.isoformat(),
            "source": self.source,
        }


class FXLookup:
    """
    Exchange rate lookup with caching.

    Supports:
    - Real-time rate lookups (5 min cache)
    - End-of-day rates (24h cache)
    - Optional Redis caching (falls back to in-memory if not available)

    Example:
        >>> fx = FXLookup()
        >>> result = await fx.get_rate("USD", "COP")
        >>> print(f"1 USD = {result.rate} COP")
    """

    # In-memory cache fallback when Redis is not available
    _memory_cache: dict[str, tuple[str, float]] = {}

    def __init__(self, redis_client: Any | None = None):
        """
        Initialize FX Lookup.

        Args:
            redis_client: Optional Redis client for caching.
                          If not provided and Redis is enabled, will create one.
        """
        self.redis = redis_client
        self.api_url = settings.exchange_rate_api_url
        self.api_key = settings.exchange_rate_api_key
        self.cache_ttl = settings.fx_cache_ttl_seconds
        self.eod_cache_ttl = settings.fx_eod_cache_ttl_seconds

        # Initialize Redis if enabled and not provided
        if self.redis is None and settings.redis_enabled:
            self._init_redis()

    def _init_redis(self) -> None:
        """Initialize Redis connection if available."""
        try:
            import redis

            self.redis = redis.Redis.from_url(
                settings.redis_url,
                decode_responses=True,
            )
            # Test connection
            self.redis.ping()
            logger.debug("fx_lookup_redis_connected")
        except Exception as e:
            logger.warning(
                "fx_lookup_redis_unavailable",
                error=str(e),
                fallback="memory_cache",
            )
            self.redis = None

    def _get_cache_key(
        self,
        from_currency: str,
        to_currency: str,
        use_eod: bool = False,
    ) -> str:
        """Generate cache key for rate lookup."""
        key = f"fx:{from_currency}:{to_currency}"
        if use_eod:
            key += f":eod:{date.today().isoformat()}"
        return key

    def _get_from_cache(self, cache_key: str) -> Decimal | None:
        """Get rate from cache (Redis or memory)."""
        try:
            if self.redis:
                cached = self.redis.get(cache_key)
                if cached:
                    logger.debug("fx_lookup_cache_hit", key=cache_key)
                    return Decimal(cached)
            else:
                # Memory cache fallback
                import time

                if cache_key in self._memory_cache:
                    value, expiry = self._memory_cache[cache_key]
                    if time.time() < expiry:
                        logger.debug("fx_lookup_memory_cache_hit", key=cache_key)
                        return Decimal(value)
                    else:
                        # Expired
                        del self._memory_cache[cache_key]
        except Exception as e:
            logger.warning("fx_lookup_cache_error", error=str(e))

        return None

    def _set_in_cache(self, cache_key: str, rate: Decimal, ttl: int) -> None:
        """Set rate in cache (Redis or memory)."""
        try:
            if self.redis:
                self.redis.setex(cache_key, ttl, str(rate))
                logger.debug("fx_lookup_cache_set", key=cache_key, ttl=ttl)
            else:
                # Memory cache fallback
                import time

                self._memory_cache[cache_key] = (str(rate), time.time() + ttl)
                logger.debug("fx_lookup_memory_cache_set", key=cache_key, ttl=ttl)
        except Exception as e:
            logger.warning("fx_lookup_cache_set_error", error=str(e))

    async def get_rate(
        self,
        from_currency: str,
        to_currency: str,
        amount: Decimal | None = None,
        use_eod: bool = False,
    ) -> FXRateResult:
        """
        Get exchange rate between two currencies.

        Args:
            from_currency: Source currency code (ISO 4217, e.g., "USD")
            to_currency: Target currency code (ISO 4217, e.g., "COP")
            amount: Optional amount to convert
            use_eod: Use end-of-day rate (longer cache, for budget sync)

        Returns:
            FXRateResult with rate and optional converted amount

        Raises:
            FXRateNotFoundError: If rate cannot be found
            FXAPIError: If API call fails

        Example:
            >>> result = await fx.get_rate("USD", "COP", Decimal("100"))
            >>> print(result.converted_amount)
        """
        # Normalize currency codes
        from_currency = from_currency.upper().strip()
        to_currency = to_currency.upper().strip()

        # Same currency - no conversion needed
        if from_currency == to_currency:
            return FXRateResult(
                from_currency=from_currency,
                to_currency=to_currency,
                rate=Decimal("1"),
                converted_amount=amount,
                rate_date=date.today(),
                source="identity",
            )

        cache_key = self._get_cache_key(from_currency, to_currency, use_eod)

        # Try cache first
        cached_rate = self._get_from_cache(cache_key)
        if cached_rate is not None:
            return FXRateResult(
                from_currency=from_currency,
                to_currency=to_currency,
                rate=cached_rate,
                converted_amount=amount * cached_rate if amount else None,
                rate_date=date.today(),
                source="cache",
            )

        # Fetch from API
        rate = await self._fetch_rate_from_api(from_currency, to_currency)

        # Cache the result
        ttl = self.eod_cache_ttl if use_eod else self.cache_ttl
        self._set_in_cache(cache_key, rate, ttl)

        logger.info(
            "fx_rate_fetched",
            from_currency=from_currency,
            to_currency=to_currency,
            rate=str(rate),
            use_eod=use_eod,
        )

        return FXRateResult(
            from_currency=from_currency,
            to_currency=to_currency,
            rate=rate,
            converted_amount=amount * rate if amount else None,
            rate_date=date.today(),
            source="api",
        )

    async def _fetch_rate_from_api(
        self,
        from_currency: str,
        to_currency: str,
    ) -> Decimal:
        """
        Fetch exchange rate from Exchange Rate API.

        Args:
            from_currency: Source currency code
            to_currency: Target currency code

        Returns:
            Exchange rate as Decimal

        Raises:
            FXAPIError: If API call fails
            FXRateNotFoundError: If currency pair is not supported
        """
        if not self.api_key:
            raise FXAPIError(
                "Exchange Rate API key not configured. "
                "Set EXCHANGE_RATE_API_KEY in environment."
            )

        url = f"{self.api_url}/{self.api_key}/pair/{from_currency}/{to_currency}"

        logger.debug(
            "fx_api_request",
            from_currency=from_currency,
            to_currency=to_currency,
        )

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)

                if response.status_code == 404:
                    raise FXRateNotFoundError(
                        f"Currency pair not found: {from_currency}/{to_currency}"
                    )

                if response.status_code == 403:
                    raise FXAPIError("Invalid API key or quota exceeded")

                response.raise_for_status()

                data = response.json()

                if data.get("result") != "success":
                    error_type = data.get("error-type", "unknown")
                    raise FXAPIError(f"API error: {error_type}")

                rate = Decimal(str(data["conversion_rate"]))

                logger.debug(
                    "fx_api_response",
                    from_currency=from_currency,
                    to_currency=to_currency,
                    rate=str(rate),
                )

                return rate

        except httpx.TimeoutException:
            raise FXAPIError(
                f"Timeout fetching rate for {from_currency}/{to_currency}"
            )
        except httpx.HTTPError as e:
            raise FXAPIError(f"HTTP error: {str(e)}")
        except (KeyError, ValueError) as e:
            raise FXAPIError(f"Invalid API response: {str(e)}")

    async def convert(
        self,
        amount: Decimal,
        from_currency: str,
        to_currency: str,
        use_eod: bool = False,
    ) -> Decimal:
        """
        Convenience method to convert an amount.

        Args:
            amount: Amount to convert
            from_currency: Source currency code
            to_currency: Target currency code
            use_eod: Use end-of-day rate

        Returns:
            Converted amount

        Example:
            >>> converted = await fx.convert(Decimal("100"), "USD", "COP")
        """
        result = await self.get_rate(from_currency, to_currency, amount, use_eod)
        return result.converted_amount or Decimal("0")

    async def get_multiple_rates(
        self,
        base_currency: str,
        target_currencies: list[str],
        use_eod: bool = False,
    ) -> dict[str, FXRateResult]:
        """
        Get rates for multiple currencies at once.

        Useful for prefetching rates during trip setup.

        Args:
            base_currency: Base currency code
            target_currencies: List of target currency codes
            use_eod: Use end-of-day rates

        Returns:
            Dictionary mapping currency codes to FXRateResult
        """
        results = {}
        for target in target_currencies:
            try:
                result = await self.get_rate(base_currency, target, use_eod=use_eod)
                results[target] = result
            except FXLookupError as e:
                logger.warning(
                    "fx_rate_lookup_failed",
                    base=base_currency,
                    target=target,
                    error=str(e),
                )
        return results

    def clear_cache(self, pattern: str = "fx:*") -> int:
        """
        Clear cached rates.

        Args:
            pattern: Cache key pattern to clear (default: all fx rates)

        Returns:
            Number of keys cleared
        """
        cleared = 0
        try:
            if self.redis:
                keys = self.redis.keys(pattern)
                if keys:
                    cleared = self.redis.delete(*keys)
            else:
                # Memory cache
                keys_to_delete = [
                    k for k in self._memory_cache.keys() if k.startswith("fx:")
                ]
                for k in keys_to_delete:
                    del self._memory_cache[k]
                    cleared += 1

            logger.info("fx_cache_cleared", pattern=pattern, count=cleared)
        except Exception as e:
            logger.warning("fx_cache_clear_error", error=str(e))

        return cleared

