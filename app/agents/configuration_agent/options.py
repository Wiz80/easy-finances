"""
Selection options for Configuration Agent.

Defines menu options for currency, timezone, and other selectable fields.
Using numbered options reduces LLM token usage and eliminates interpretation errors.
"""

from dataclasses import dataclass


@dataclass
class SelectionOption:
    """A single selection option."""
    key: str  # The number/letter for selection (e.g., "1", "2", "a")
    value: str  # The actual value to store (e.g., "USD", "America/Bogota")
    label: str  # Display label with emoji (e.g., "🇺🇸 Dólar (USD)")


# ─────────────────────────────────────────────────────────────────────────────
# Currency Options
# ─────────────────────────────────────────────────────────────────────────────

CURRENCY_OPTIONS: list[SelectionOption] = [
    SelectionOption("1", "COP", "🇨🇴 Peso Colombiano (COP)"),
    SelectionOption("2", "USD", "🇺🇸 Dólar Americano (USD)"),
    SelectionOption("3", "MXN", "🇲🇽 Peso Mexicano (MXN)"),
    SelectionOption("4", "EUR", "🇪🇺 Euro (EUR)"),
    SelectionOption("5", "PEN", "🇵🇪 Sol Peruano (PEN)"),
    SelectionOption("6", "CLP", "🇨🇱 Peso Chileno (CLP)"),
    SelectionOption("7", "ARS", "🇦🇷 Peso Argentino (ARS)"),
    SelectionOption("8", "BRL", "🇧🇷 Real Brasileño (BRL)"),
]

CURRENCY_MAP = {opt.key: opt.value for opt in CURRENCY_OPTIONS}
CURRENCY_MAP.update({opt.value.lower(): opt.value for opt in CURRENCY_OPTIONS})  # Also accept "usd", "cop"


# ─────────────────────────────────────────────────────────────────────────────
# Timezone Options
# ─────────────────────────────────────────────────────────────────────────────

TIMEZONE_OPTIONS: list[SelectionOption] = [
    SelectionOption("1", "America/Bogota", "🇨🇴 Colombia (GMT-5)"),
    SelectionOption("2", "America/Mexico_City", "🇲🇽 México (GMT-6)"),
    SelectionOption("3", "America/Lima", "🇵🇪 Perú (GMT-5)"),
    SelectionOption("4", "America/Santiago", "🇨🇱 Chile (GMT-3/-4)"),
    SelectionOption("5", "America/Argentina/Buenos_Aires", "🇦🇷 Argentina (GMT-3)"),
    SelectionOption("6", "America/Sao_Paulo", "🇧🇷 Brasil (GMT-3)"),
    SelectionOption("7", "America/New_York", "🇺🇸 Nueva York (GMT-5)"),
    SelectionOption("8", "Europe/Madrid", "🇪🇸 España (GMT+1)"),
    SelectionOption("9", "America/Los_Angeles", "🇺🇸 Los Ángeles (GMT-8)"),
]

TIMEZONE_MAP = {opt.key: opt.value for opt in TIMEZONE_OPTIONS}


# ─────────────────────────────────────────────────────────────────────────────
# Budget Category Options (for quick setup)
# ─────────────────────────────────────────────────────────────────────────────

BUDGET_CATEGORY_OPTIONS: list[SelectionOption] = [
    SelectionOption("1", "food", "🍔 Comida"),
    SelectionOption("2", "lodging", "🏨 Hospedaje"),
    SelectionOption("3", "transport", "🚕 Transporte"),
    SelectionOption("4", "tourism", "🎭 Turismo/Entretenimiento"),
    SelectionOption("5", "gifts", "🎁 Regalos/Compras"),
    SelectionOption("6", "other", "📦 Otros"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Card Type Options
# ─────────────────────────────────────────────────────────────────────────────

CARD_TYPE_OPTIONS: list[SelectionOption] = [
    SelectionOption("1", "debit", "💳 Débito"),
    SelectionOption("2", "credit", "💳 Crédito"),
    SelectionOption("3", "cash", "💵 Efectivo"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────────────────────

def format_options_menu(options: list[SelectionOption], header: str = "") -> str:
    """
    Format a list of options as a numbered menu for WhatsApp.
    
    Args:
        options: List of SelectionOption
        header: Optional header text
        
    Returns:
        Formatted menu string
    """
    lines = []
    if header:
        lines.append(header)
        lines.append("")
    
    for opt in options:
        lines.append(f"{opt.key}. {opt.label}")
    
    lines.append("")
    lines.append("_Responde con el número de tu elección_")
    
    return "\n".join(lines)


def parse_selection(
    message: str,
    options_map: dict[str, str],
) -> str | None:
    """
    Parse a user's selection from a menu.
    
    Args:
        message: User's message (e.g., "1", "2", "usd", "cop")
        options_map: Map of key/alias to value
        
    Returns:
        The selected value, or None if not found
    """
    message_clean = message.strip().lower()
    
    # Try exact match first
    if message_clean in options_map:
        return options_map[message_clean]
    
    # Try just the first character (in case they wrote "1." or "1-")
    first_char = message_clean[0] if message_clean else ""
    if first_char in options_map:
        return options_map[first_char]
    
    return None


def get_currency_menu() -> str:
    """Get formatted currency selection menu."""
    return format_options_menu(
        CURRENCY_OPTIONS,
        "💰 *¿Cuál es tu moneda base?*\n(La moneda que usas normalmente en tu país)"
    )


def get_timezone_menu() -> str:
    """Get formatted timezone selection menu."""
    return format_options_menu(
        TIMEZONE_OPTIONS,
        "🌍 *¿En qué zona horaria te encuentras?*"
    )


def get_card_type_menu() -> str:
    """Get formatted card type selection menu."""
    return format_options_menu(
        CARD_TYPE_OPTIONS,
        "💳 *¿Qué tipo de método de pago quieres agregar?*"
    )

