"""
IVR Flow Constants.

Defines the steps, keywords, and supported values for IVR-based configuration flows.
"""

from enum import Enum


class IVRFlow(str, Enum):
    """Types of IVR configuration flows."""
    ONBOARDING = "onboarding"
    BUDGET = "budget"
    TRIP = "trip"
    CARD = "card"


# ─────────────────────────────────────────────────────────────────────────────
# Flow Step Definitions
# ─────────────────────────────────────────────────────────────────────────────

ONBOARDING_STEPS = ["name", "currency", "country", "timezone", "confirm"]
BUDGET_STEPS = ["name", "amount", "currency", "start_date", "end_date", "confirm"]
TRIP_STEPS = ["name", "country", "start_date", "end_date", "link_budget", "confirm"]
CARD_STEPS = ["name", "type", "network", "last_four", "color", "confirm"]


# ─────────────────────────────────────────────────────────────────────────────
# Supported Currencies (ISO 4217)
# ─────────────────────────────────────────────────────────────────────────────

SUPPORTED_CURRENCIES = ["USD", "COP", "EUR", "MXN", "ARS", "CLP", "PEN", "BRL"]

CURRENCY_NAMES = {
    "USD": "Dólar Estadounidense",
    "COP": "Peso Colombiano",
    "EUR": "Euro",
    "MXN": "Peso Mexicano",
    "ARS": "Peso Argentino",
    "CLP": "Peso Chileno",
    "PEN": "Sol Peruano",
    "BRL": "Real Brasileño",
}

CURRENCY_SYMBOLS = {
    "USD": "$",
    "COP": "$",
    "EUR": "€",
    "MXN": "$",
    "ARS": "$",
    "CLP": "$",
    "PEN": "S/",
    "BRL": "R$",
}


# ─────────────────────────────────────────────────────────────────────────────
# Supported Countries (ISO 3166-1 alpha-2)
# ─────────────────────────────────────────────────────────────────────────────

SUPPORTED_COUNTRIES = {
    "CO": "Colombia",
    "US": "Estados Unidos",
    "MX": "México",
    "ES": "España",
    "AR": "Argentina",
    "CL": "Chile",
    "PE": "Perú",
    "BR": "Brasil",
    "EC": "Ecuador",
}

# Default timezone per country
COUNTRY_TIMEZONES = {
    "CO": "America/Bogota",
    "US": "America/New_York",
    "MX": "America/Mexico_City",
    "ES": "Europe/Madrid",
    "AR": "America/Argentina/Buenos_Aires",
    "CL": "America/Santiago",
    "PE": "America/Lima",
    "BR": "America/Sao_Paulo",
    "EC": "America/Guayaquil",
}

# Default currency per country
COUNTRY_CURRENCIES = {
    "CO": "COP",
    "US": "USD",
    "MX": "MXN",
    "ES": "EUR",
    "AR": "ARS",
    "CL": "CLP",
    "PE": "PEN",
    "BR": "BRL",
    "EC": "USD",
}


# ─────────────────────────────────────────────────────────────────────────────
# Keywords for IVR Flow Activation
# ─────────────────────────────────────────────────────────────────────────────

IVR_KEYWORDS: dict[str, IVRFlow] = {
    # Budget keywords
    "presupuesto": IVRFlow.BUDGET,
    "nuevo presupuesto": IVRFlow.BUDGET,
    "crear presupuesto": IVRFlow.BUDGET,
    "configurar presupuesto": IVRFlow.BUDGET,
    # Trip keywords
    "viaje": IVRFlow.TRIP,
    "nuevo viaje": IVRFlow.TRIP,
    "modo viaje": IVRFlow.TRIP,
    "crear viaje": IVRFlow.TRIP,
    "configurar viaje": IVRFlow.TRIP,
    # Card keywords
    "tarjeta": IVRFlow.CARD,
    "configurar tarjeta": IVRFlow.CARD,
    "nueva tarjeta": IVRFlow.CARD,
    "agregar tarjeta": IVRFlow.CARD,
}


# ─────────────────────────────────────────────────────────────────────────────
# Card Configuration Options
# ─────────────────────────────────────────────────────────────────────────────

CARD_TYPES = {
    "1": "credit",
    "2": "debit",
    "credito": "credit",
    "crédito": "credit",
    "debito": "debit",
    "débito": "debit",
}

CARD_NETWORKS = {
    "1": "visa",
    "2": "mastercard",
    "3": "amex",
    "4": "other",
    "visa": "visa",
    "mastercard": "mastercard",
    "amex": "amex",
}

CARD_COLORS = {
    "1": "blue",
    "2": "black",
    "3": "gold",
    "4": "silver",
    "5": "green",
    "6": "red",
    "azul": "blue",
    "negro": "black",
    "dorado": "gold",
    "plateado": "silver",
    "verde": "green",
    "rojo": "red",
}


# ─────────────────────────────────────────────────────────────────────────────
# Confirmation Keywords
# ─────────────────────────────────────────────────────────────────────────────

CONFIRM_KEYWORDS = {"1", "si", "sí", "yes", "ok", "dale", "confirmo", "correcto"}
DENY_KEYWORDS = {"2", "no", "cancelar", "cancel", "cambiar", "reiniciar"}


# ─────────────────────────────────────────────────────────────────────────────
# Fixed UUIDs for System Categories
# ─────────────────────────────────────────────────────────────────────────────

UNEXPECTED_CATEGORY_ID = "a0000000-0000-0000-0000-000000000001"

