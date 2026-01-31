"""
Unit tests for IVR validators.

Tests the flexible validation logic for user inputs in IVR flows.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.flows.validators import (
    validate_name,
    validate_currency,
    validate_country,
    validate_timezone,
    validate_amount,
    validate_date,
    validate_confirmation,
    validate_card_type,
    validate_card_network,
    validate_last_four,
    validate_card_color,
)


# ─────────────────────────────────────────────────────────────────────────────
# Name Validation Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateName:
    """Tests for validate_name function."""

    def test_valid_name(self):
        """Valid names should pass."""
        result = validate_name("Harrison")
        assert result.valid is True
        assert result.value == "Harrison"

    def test_valid_name_with_spaces(self):
        """Names with spaces should be title-cased."""
        result = validate_name("john doe")
        assert result.valid is True
        assert result.value == "John Doe"

    def test_valid_name_trimmed(self):
        """Leading/trailing spaces should be trimmed."""
        result = validate_name("  Maria  ")
        assert result.valid is True
        assert result.value == "Maria"

    def test_name_too_short(self):
        """Names less than 2 chars should fail."""
        result = validate_name("J")
        assert result.valid is False
        assert "2 caracteres" in result.error

    def test_name_too_long(self):
        """Names over 100 chars should fail."""
        result = validate_name("A" * 101)
        assert result.valid is False
        assert "100 caracteres" in result.error

    def test_name_non_names_rejected(self):
        """Common non-name inputs should be rejected."""
        for input_text in ["1", "si", "sí", "no", "ok", "hola"]:
            result = validate_name(input_text)
            assert result.valid is False


# ─────────────────────────────────────────────────────────────────────────────
# Currency Validation Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateCurrency:
    """Tests for validate_currency function."""

    def test_valid_currency_code_uppercase(self):
        """Uppercase currency codes should pass."""
        result = validate_currency("USD")
        assert result.valid is True
        assert result.value == "USD"

    def test_valid_currency_code_lowercase(self):
        """Lowercase currency codes should be uppercased."""
        result = validate_currency("cop")
        assert result.valid is True
        assert result.value == "COP"

    def test_valid_currency_by_number(self):
        """Menu numbers should map to currencies."""
        # 1 = USD (first in list)
        result = validate_currency("1")
        assert result.valid is True
        assert result.value == "USD"

        # 2 = COP (second in list)
        result = validate_currency("2")
        assert result.valid is True
        assert result.value == "COP"

    def test_invalid_currency_code(self):
        """Invalid currency codes should fail."""
        result = validate_currency("XYZ")
        assert result.valid is False
        assert "no válida" in result.error.lower()

    def test_invalid_number(self):
        """Out-of-range numbers should fail."""
        result = validate_currency("99")
        assert result.valid is False


# ─────────────────────────────────────────────────────────────────────────────
# Country Validation Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateCountry:
    """Tests for validate_country function."""

    def test_valid_country_code(self):
        """ISO country codes should pass."""
        result = validate_country("CO")
        assert result.valid is True
        assert result.value == "CO"

    def test_valid_country_by_number(self):
        """Menu numbers should map to countries."""
        # 1 = CO (first in dict)
        result = validate_country("1")
        assert result.valid is True
        assert result.value == "CO"

    def test_valid_country_by_partial_name(self):
        """Partial country names should match."""
        result = validate_country("colombia")
        assert result.valid is True
        assert result.value == "CO"

        result = validate_country("col")
        assert result.valid is True
        assert result.value == "CO"

    def test_valid_country_by_full_name(self):
        """Full country names should match."""
        result = validate_country("México")
        assert result.valid is True
        assert result.value == "MX"

    def test_invalid_country(self):
        """Invalid country inputs should fail."""
        result = validate_country("Atlantis")
        assert result.valid is False


# ─────────────────────────────────────────────────────────────────────────────
# Timezone Validation Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateTimezone:
    """Tests for validate_timezone function."""

    def test_valid_timezone_recommended_option(self):
        """Option '1' should use country default."""
        result = validate_timezone("1", country="CO")
        assert result.valid is True
        assert result.value == "America/Bogota"

    def test_valid_timezone_iana(self):
        """Valid IANA timezone strings should pass."""
        result = validate_timezone("America/Lima")
        assert result.valid is True
        assert result.value == "America/Lima"

    def test_valid_timezone_by_city(self):
        """City names should map to timezones."""
        result = validate_timezone("bogota")
        assert result.valid is True
        assert result.value == "America/Bogota"

        result = validate_timezone("Santiago")
        assert result.valid is True
        assert result.value == "America/Santiago"

    def test_invalid_timezone_uses_default(self):
        """Invalid inputs should use country default (flexible validation)."""
        result = validate_timezone("invalid_tz", country="MX")
        assert result.valid is True  # Flexible - uses default
        assert result.value == "America/Mexico_City"

    def test_no_country_uses_global_default(self):
        """Without country, uses global default."""
        result = validate_timezone("invalid_tz", country=None)
        assert result.valid is True
        assert result.value == "America/Mexico_City"


# ─────────────────────────────────────────────────────────────────────────────
# Amount Validation Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateAmount:
    """Tests for validate_amount function."""

    def test_valid_integer(self):
        """Integer amounts should pass."""
        result = validate_amount("50000")
        assert result.valid is True
        assert result.value == Decimal("50000")

    def test_valid_decimal_with_dot(self):
        """Decimal amounts with dot should pass."""
        result = validate_amount("100.50")
        assert result.valid is True
        assert result.value == Decimal("100.50")

    def test_valid_with_comma_as_decimal(self):
        """European format (comma as decimal) should pass."""
        result = validate_amount("100,50")
        assert result.valid is True
        assert result.value == Decimal("100.50")

    def test_valid_with_thousand_separator(self):
        """US format with thousand separator should pass."""
        result = validate_amount("1,000.50")
        assert result.valid is True
        assert result.value == Decimal("1000.50")

    def test_valid_european_thousand_separator(self):
        """European format (dot as thousand, comma as decimal)."""
        result = validate_amount("1.000,50")
        assert result.valid is True
        assert result.value == Decimal("1000.50")

    def test_valid_with_currency_symbol(self):
        """Currency symbols should be stripped."""
        result = validate_amount("$50000")
        assert result.valid is True
        assert result.value == Decimal("50000")

        result = validate_amount("€100")
        assert result.valid is True
        assert result.value == Decimal("100")

    def test_invalid_zero(self):
        """Zero should fail."""
        result = validate_amount("0")
        assert result.valid is False
        assert "mayor a 0" in result.error

    def test_invalid_negative(self):
        """Negative amounts should fail."""
        result = validate_amount("-100")
        assert result.valid is False

    def test_invalid_text(self):
        """Non-numeric text should fail."""
        result = validate_amount("abc")
        assert result.valid is False


# ─────────────────────────────────────────────────────────────────────────────
# Date Validation Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateDate:
    """Tests for validate_date function."""

    def test_valid_iso_format(self):
        """ISO format (YYYY-MM-DD) should pass."""
        result = validate_date("2024-12-15")
        assert result.valid is True
        assert result.value == date(2024, 12, 15)

    def test_valid_european_format(self):
        """European format (DD/MM/YYYY) should pass."""
        result = validate_date("15/12/2024")
        assert result.valid is True
        assert result.value == date(2024, 12, 15)

    def test_valid_dash_format(self):
        """Dash format (DD-MM-YYYY) should pass."""
        result = validate_date("15-12-2024")
        assert result.valid is True
        assert result.value == date(2024, 12, 15)

    def test_valid_today_keyword_spanish(self):
        """'hoy' should return today's date."""
        result = validate_date("hoy")
        assert result.valid is True
        assert result.value == date.today()

    def test_valid_today_keyword_english(self):
        """'today' should return today's date."""
        result = validate_date("today")
        assert result.valid is True
        assert result.value == date.today()

    def test_valid_tomorrow_keyword(self):
        """'mañana' should return tomorrow's date."""
        result = validate_date("mañana")
        assert result.valid is True
        assert result.value == date.today() + timedelta(days=1)

    def test_invalid_format(self):
        """Invalid date format should fail."""
        result = validate_date("December 15, 2024")
        assert result.valid is False
        assert "DD/MM/YYYY" in result.error


# ─────────────────────────────────────────────────────────────────────────────
# Confirmation Validation Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateConfirmation:
    """Tests for validate_confirmation function."""

    def test_confirm_with_number(self):
        """'1' should confirm."""
        result = validate_confirmation("1")
        assert result.valid is True
        assert result.value is True

    def test_confirm_with_si(self):
        """'si' and 'sí' should confirm."""
        result = validate_confirmation("si")
        assert result.valid is True
        assert result.value is True

        result = validate_confirmation("sí")
        assert result.valid is True
        assert result.value is True

    def test_confirm_with_ok(self):
        """'ok' should confirm."""
        result = validate_confirmation("ok")
        assert result.valid is True
        assert result.value is True

    def test_deny_with_number(self):
        """'2' should deny."""
        result = validate_confirmation("2")
        assert result.valid is True
        assert result.value is False

    def test_deny_with_no(self):
        """'no' should deny."""
        result = validate_confirmation("no")
        assert result.valid is True
        assert result.value is False

    def test_deny_with_cancelar(self):
        """'cancelar' should deny."""
        result = validate_confirmation("cancelar")
        assert result.valid is True
        assert result.value is False

    def test_invalid_response(self):
        """Unknown inputs should fail."""
        result = validate_confirmation("maybe")
        assert result.valid is False


# ─────────────────────────────────────────────────────────────────────────────
# Card Validation Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateCardType:
    """Tests for validate_card_type function."""

    def test_credit_by_number(self):
        """'1' should map to credit."""
        result = validate_card_type("1")
        assert result.valid is True
        assert result.value == "credit"

    def test_debit_by_number(self):
        """'2' should map to debit."""
        result = validate_card_type("2")
        assert result.valid is True
        assert result.value == "debit"

    def test_credit_by_word(self):
        """'credito' and 'crédito' should map to credit."""
        result = validate_card_type("credito")
        assert result.valid is True
        assert result.value == "credit"

        result = validate_card_type("crédito")
        assert result.valid is True
        assert result.value == "credit"


class TestValidateCardNetwork:
    """Tests for validate_card_network function."""

    def test_visa_by_number(self):
        """'1' should map to visa."""
        result = validate_card_network("1")
        assert result.valid is True
        assert result.value == "visa"

    def test_mastercard_by_number(self):
        """'2' should map to mastercard."""
        result = validate_card_network("2")
        assert result.valid is True
        assert result.value == "mastercard"

    def test_network_by_name(self):
        """Network names should be recognized."""
        result = validate_card_network("visa")
        assert result.valid is True
        assert result.value == "visa"


class TestValidateLastFour:
    """Tests for validate_last_four function."""

    def test_valid_four_digits(self):
        """Four digits should pass."""
        result = validate_last_four("4532")
        assert result.valid is True
        assert result.value == "4532"

    def test_valid_with_spaces(self):
        """Spaces should be stripped."""
        result = validate_last_four("4 5 3 2")
        assert result.valid is True
        assert result.value == "4532"

    def test_invalid_not_four(self):
        """Non-4-digit inputs should fail."""
        result = validate_last_four("123")
        assert result.valid is False

        result = validate_last_four("12345")
        assert result.valid is False

    def test_invalid_non_numeric(self):
        """Non-numeric inputs should fail."""
        result = validate_last_four("ABCD")
        assert result.valid is False


class TestValidateCardColor:
    """Tests for validate_card_color function."""

    def test_valid_by_number(self):
        """Menu numbers should map to colors."""
        result = validate_card_color("1")
        assert result.valid is True
        assert result.value == "blue"

    def test_valid_by_spanish_name(self):
        """Spanish color names should be recognized."""
        result = validate_card_color("azul")
        assert result.valid is True
        assert result.value == "blue"

        result = validate_card_color("negro")
        assert result.valid is True
        assert result.value == "black"

    def test_valid_custom_alias(self):
        """Custom aliases should be allowed."""
        result = validate_card_color("mi tarjeta personal")
        assert result.valid is True
        assert result.value == "mi tarjeta personal"

    def test_invalid_too_short(self):
        """Single character should fail."""
        result = validate_card_color("a")
        assert result.valid is False

