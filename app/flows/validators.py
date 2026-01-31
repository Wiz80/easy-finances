"""
IVR Input Validators.

Provides flexible validation for user inputs in IVR flows.
Uses intelligent defaults when possible instead of strict validation.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import pytz

from app.flows.constants import (
    SUPPORTED_CURRENCIES,
    SUPPORTED_COUNTRIES,
    COUNTRY_TIMEZONES,
    CONFIRM_KEYWORDS,
    DENY_KEYWORDS,
)


@dataclass
class ValidationResult:
    """Result of a validation operation."""
    valid: bool
    value: Any = None
    error: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Name Validation
# ─────────────────────────────────────────────────────────────────────────────

def validate_name(input_text: str) -> ValidationResult:
    """
    Validate user name (2-100 characters).
    
    Args:
        input_text: User's input
        
    Returns:
        ValidationResult with title-cased name
    """
    name = input_text.strip()
    
    if len(name) < 2:
        return ValidationResult(
            valid=False,
            error="El nombre debe tener al menos 2 caracteres"
        )
    
    if len(name) > 100:
        return ValidationResult(
            valid=False,
            error="El nombre no puede exceder 100 caracteres"
        )
    
    # Filter out obvious non-name inputs
    non_names = {"1", "2", "3", "si", "sí", "no", "ok", "hola", "ayuda", "help"}
    if name.lower() in non_names:
        return ValidationResult(
            valid=False,
            error="Por favor ingresa tu nombre"
        )
    
    return ValidationResult(valid=True, value=name.title())


# ─────────────────────────────────────────────────────────────────────────────
# Currency Validation
# ─────────────────────────────────────────────────────────────────────────────

def validate_currency(input_text: str) -> ValidationResult:
    """
    Validate currency (ISO code or menu number).
    
    Args:
        input_text: User's input (e.g., "1", "USD", "usd")
        
    Returns:
        ValidationResult with ISO currency code
    """
    text = input_text.strip().upper()
    
    # Direct match by code
    if text in SUPPORTED_CURRENCIES:
        return ValidationResult(valid=True, value=text)
    
    # Match by menu number
    try:
        idx = int(input_text.strip()) - 1
        if 0 <= idx < len(SUPPORTED_CURRENCIES):
            return ValidationResult(valid=True, value=SUPPORTED_CURRENCIES[idx])
    except ValueError:
        pass
    
    return ValidationResult(
        valid=False,
        error=f"Moneda no válida. Opciones: {', '.join(SUPPORTED_CURRENCIES)}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Country Validation
# ─────────────────────────────────────────────────────────────────────────────

def validate_country(input_text: str) -> ValidationResult:
    """
    Validate country (ISO code, menu number, or partial name).
    
    Args:
        input_text: User's input (e.g., "1", "CO", "Colombia", "col")
        
    Returns:
        ValidationResult with ISO country code
    """
    text = input_text.strip()
    text_upper = text.upper()
    text_lower = text.lower()
    
    # Direct match by code
    if text_upper in SUPPORTED_COUNTRIES:
        return ValidationResult(valid=True, value=text_upper)
    
    # Match by menu number
    try:
        idx = int(text) - 1
        codes = list(SUPPORTED_COUNTRIES.keys())
        if 0 <= idx < len(codes):
            return ValidationResult(valid=True, value=codes[idx])
    except ValueError:
        pass
    
    # Match by partial name
    for code, name in SUPPORTED_COUNTRIES.items():
        if text_lower in name.lower() or name.lower().startswith(text_lower):
            return ValidationResult(valid=True, value=code)
    
    return ValidationResult(
        valid=False,
        error="País no válido. Usa el número o nombre del país."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Timezone Validation
# ─────────────────────────────────────────────────────────────────────────────

def validate_timezone(input_text: str, country: str | None = None) -> ValidationResult:
    """
    Validate timezone with intelligent defaults based on country.
    
    This is a flexible validator - if the input is invalid, it uses
    the default timezone for the country instead of failing.
    
    Args:
        input_text: User's input (e.g., "1", "America/Bogota")
        country: User's country code for default lookup
        
    Returns:
        ValidationResult with IANA timezone
    """
    text = input_text.strip()
    default_tz = COUNTRY_TIMEZONES.get(country, "America/Mexico_City")
    
    # If user selects "1" (recommended), use country default
    if text == "1":
        return ValidationResult(valid=True, value=default_tz)
    
    # Try to validate as IANA timezone
    try:
        pytz.timezone(text)
        return ValidationResult(valid=True, value=text)
    except pytz.UnknownTimeZoneError:
        pass
    
    # Match common city names to timezones
    city_timezones = {
        "bogota": "America/Bogota",
        "bogotá": "America/Bogota",
        "medellin": "America/Bogota",
        "medellín": "America/Bogota",
        "santiago": "America/Santiago",
        "lima": "America/Lima",
        "mexico": "America/Mexico_City",
        "méxico": "America/Mexico_City",
        "buenos aires": "America/Argentina/Buenos_Aires",
        "madrid": "Europe/Madrid",
        "new york": "America/New_York",
        "sao paulo": "America/Sao_Paulo",
        "são paulo": "America/Sao_Paulo",
    }
    
    text_lower = text.lower()
    for city, tz in city_timezones.items():
        if city in text_lower:
            return ValidationResult(valid=True, value=tz)
    
    # Flexible: use default instead of failing
    return ValidationResult(valid=True, value=default_tz)


# ─────────────────────────────────────────────────────────────────────────────
# Amount Validation
# ─────────────────────────────────────────────────────────────────────────────

def validate_amount(input_text: str) -> ValidationResult:
    """
    Validate numeric amount.
    
    Handles various formats:
    - "1000"
    - "1,000"
    - "1.000" (European)
    - "1000.50"
    
    Args:
        input_text: User's input
        
    Returns:
        ValidationResult with Decimal amount
    """
    text = input_text.strip()
    
    # Remove currency symbols and spaces
    text = text.replace("$", "").replace("€", "").replace(" ", "")
    
    # Handle thousand separators
    # If there's both comma and dot, determine which is the decimal separator
    if "," in text and "." in text:
        # Assume last separator is decimal
        if text.rfind(",") > text.rfind("."):
            # Comma is decimal separator (European: 1.000,50)
            text = text.replace(".", "").replace(",", ".")
        else:
            # Dot is decimal separator (US: 1,000.50)
            text = text.replace(",", "")
    elif "," in text:
        # Could be thousand separator or decimal
        # If there are 3 digits after comma, it's a thousand separator
        parts = text.split(",")
        if len(parts[-1]) == 3:
            text = text.replace(",", "")
        else:
            text = text.replace(",", ".")
    
    try:
        amount = Decimal(text)
        if amount <= 0:
            return ValidationResult(
                valid=False,
                error="El monto debe ser mayor a 0"
            )
        return ValidationResult(valid=True, value=amount)
    except InvalidOperation:
        return ValidationResult(
            valid=False,
            error="Monto no válido. Ingresa solo números."
        )


# ─────────────────────────────────────────────────────────────────────────────
# Date Validation
# ─────────────────────────────────────────────────────────────────────────────

def validate_date(input_text: str) -> ValidationResult:
    """
    Validate date in multiple formats.
    
    Supported formats:
    - YYYY-MM-DD
    - DD/MM/YYYY
    - DD-MM-YYYY
    - DD.MM.YYYY
    - "hoy" / "today"
    
    Args:
        input_text: User's input
        
    Returns:
        ValidationResult with date object
    """
    text = input_text.strip().lower()
    
    # Handle "today" keywords
    if text in ("hoy", "today"):
        return ValidationResult(valid=True, value=date.today())
    
    # Handle "tomorrow" keywords
    if text in ("mañana", "manana", "tomorrow"):
        from datetime import timedelta
        return ValidationResult(valid=True, value=date.today() + timedelta(days=1))
    
    # Try various date formats
    formats = [
        "%Y-%m-%d",    # 2024-12-15
        "%d/%m/%Y",    # 15/12/2024
        "%d-%m-%Y",    # 15-12-2024
        "%d.%m.%Y",    # 15.12.2024
        "%d/%m/%y",    # 15/12/24
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(input_text.strip(), fmt)
            return ValidationResult(valid=True, value=dt.date())
        except ValueError:
            continue
    
    return ValidationResult(
        valid=False,
        error="Fecha no válida. Usa formato DD/MM/YYYY o escribe 'hoy'"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Confirmation Validation
# ─────────────────────────────────────────────────────────────────────────────

def validate_confirmation(input_text: str) -> ValidationResult:
    """
    Validate yes/no confirmation.
    
    Args:
        input_text: User's input
        
    Returns:
        ValidationResult with True (confirmed) or False (denied)
    """
    text = input_text.strip().lower()
    
    if text in CONFIRM_KEYWORDS:
        return ValidationResult(valid=True, value=True)
    
    if text in DENY_KEYWORDS:
        return ValidationResult(valid=True, value=False)
    
    return ValidationResult(
        valid=False,
        error="Responde 1 para confirmar o 2 para cancelar"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Card-Specific Validators
# ─────────────────────────────────────────────────────────────────────────────

def validate_card_type(input_text: str) -> ValidationResult:
    """Validate card type (credit/debit)."""
    from app.flows.constants import CARD_TYPES
    
    text = input_text.strip().lower()
    
    if text in CARD_TYPES:
        return ValidationResult(valid=True, value=CARD_TYPES[text])
    
    return ValidationResult(
        valid=False,
        error="Tipo no válido. Responde 1 para crédito o 2 para débito."
    )


def validate_card_network(input_text: str) -> ValidationResult:
    """Validate card network (visa, mastercard, amex)."""
    from app.flows.constants import CARD_NETWORKS
    
    text = input_text.strip().lower()
    
    if text in CARD_NETWORKS:
        return ValidationResult(valid=True, value=CARD_NETWORKS[text])
    
    return ValidationResult(
        valid=False,
        error="Red no válida. Responde 1 (Visa), 2 (Mastercard), 3 (Amex)."
    )


def validate_last_four(input_text: str) -> ValidationResult:
    """Validate last 4 digits of card."""
    text = input_text.strip()
    
    # Remove any spaces or dashes
    text = text.replace(" ", "").replace("-", "")
    
    if len(text) != 4:
        return ValidationResult(
            valid=False,
            error="Ingresa los últimos 4 dígitos de tu tarjeta"
        )
    
    if not text.isdigit():
        return ValidationResult(
            valid=False,
            error="Solo números. Ingresa los últimos 4 dígitos."
        )
    
    return ValidationResult(valid=True, value=text)


def validate_card_color(input_text: str) -> ValidationResult:
    """Validate card color/alias."""
    from app.flows.constants import CARD_COLORS
    
    text = input_text.strip().lower()
    
    if text in CARD_COLORS:
        return ValidationResult(valid=True, value=CARD_COLORS[text])
    
    # Allow any custom color as alias
    if len(text) >= 2:
        return ValidationResult(valid=True, value=text)
    
    return ValidationResult(
        valid=False,
        error="Ingresa un color o alias para identificar la tarjeta"
    )

