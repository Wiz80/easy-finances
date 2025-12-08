"""
Format responses for WhatsApp messaging.

This module handles formatting of bot responses to be compatible with
WhatsApp's text formatting and character limits.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.logging_config import get_logger

logger = get_logger(__name__)

# WhatsApp message limits
MAX_MESSAGE_LENGTH = 4096  # WhatsApp limit
RECOMMENDED_MESSAGE_LENGTH = 1600  # For better UX


@dataclass
class FormattedResponse:
    """
    A formatted response ready to send via WhatsApp.
    
    Attributes:
        body: Main message text
        media_url: Optional media attachment URL
        chunks: If message exceeds limit, split into chunks
        quick_replies: Suggested reply options (for templates)
    """
    body: str
    media_url: str | None = None
    chunks: list[str] = field(default_factory=list)
    quick_replies: list[str] = field(default_factory=list)
    
    @property
    def needs_chunking(self) -> bool:
        """Check if message needs to be split into chunks."""
        return len(self.body) > MAX_MESSAGE_LENGTH
    
    @property
    def message_count(self) -> int:
        """Number of messages needed to send this response."""
        if self.chunks:
            return len(self.chunks)
        return 1


# ─────────────────────────────────────────────────────────────────────────────
# WhatsApp Text Formatting
# ─────────────────────────────────────────────────────────────────────────────

def bold(text: str) -> str:
    """Format text as bold for WhatsApp."""
    return f"*{text}*"


def italic(text: str) -> str:
    """Format text as italic for WhatsApp."""
    return f"_{text}_"


def strikethrough(text: str) -> str:
    """Format text with strikethrough for WhatsApp."""
    return f"~{text}~"


def monospace(text: str) -> str:
    """Format text as monospace for WhatsApp."""
    return f"```{text}```"


def code_inline(text: str) -> str:
    """Format inline code for WhatsApp."""
    return f"`{text}`"


# ─────────────────────────────────────────────────────────────────────────────
# Common Emojis for Finance App
# ─────────────────────────────────────────────────────────────────────────────

class Emoji:
    """Common emojis used in the finance assistant."""
    # Status
    CHECK = "✅"
    CROSS = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    QUESTION = "❓"
    
    # Actions
    WAVE = "👋"
    THUMBS_UP = "👍"
    POINT_RIGHT = "👉"
    THINKING = "🤔"
    CELEBRATE = "🎉"
    
    # Finance
    MONEY_BAG = "💰"
    DOLLAR = "💵"
    CARD = "💳"
    CHART = "📊"
    RECEIPT = "🧾"
    CALCULATOR = "🧮"
    
    # Categories
    FOOD = "🍔"
    LODGING = "🏨"
    TRANSPORT = "🚕"
    TOURISM = "🎭"
    HEALTHCARE = "⚕️"
    SHOPPING = "🛒"
    MISC = "📦"
    
    # Travel
    PLANE = "✈️"
    GLOBE = "🌍"
    PIN = "📍"
    CALENDAR = "📅"
    CLOCK = "🕐"
    
    # Flags (common destinations)
    FLAG_CO = "🇨🇴"
    FLAG_EC = "🇪🇨"
    FLAG_PE = "🇵🇪"
    FLAG_MX = "🇲🇽"
    FLAG_US = "🇺🇸"


# Country code to flag emoji mapping
COUNTRY_FLAGS = {
    "CO": "🇨🇴",
    "EC": "🇪🇨",
    "PE": "🇵🇪",
    "MX": "🇲🇽",
    "US": "🇺🇸",
    "CL": "🇨🇱",
    "AR": "🇦🇷",
    "BR": "🇧🇷",
    "ES": "🇪🇸",
}

# Category slug to emoji mapping
CATEGORY_EMOJIS = {
    "delivery": "🚗",
    "in_house_food": "🛒",
    "out_house_food": "🍽️",
    "lodging": "🏨",
    "transport": "🚕",
    "tourism": "🎭",
    "healthcare": "⚕️",
    "misc": "📦",
}


# ─────────────────────────────────────────────────────────────────────────────
# Formatting Functions
# ─────────────────────────────────────────────────────────────────────────────

def format_currency(
    amount: Decimal | float | int,
    currency: str,
    include_symbol: bool = True
) -> str:
    """
    Format a currency amount for display.
    
    Args:
        amount: Numeric amount
        currency: ISO 4217 currency code
        include_symbol: Whether to include currency symbol
        
    Returns:
        Formatted string, e.g., "$1,500.00 COP"
    """
    # Convert to Decimal for precision
    if not isinstance(amount, Decimal):
        amount = Decimal(str(amount))
    
    # Format with thousand separators
    formatted = f"{amount:,.2f}"
    
    # Currency symbols (add more as needed)
    symbols = {
        "USD": "$",
        "COP": "$",
        "MXN": "$",
        "PEN": "S/",
        "EUR": "€",
        "GBP": "£",
    }
    
    symbol = symbols.get(currency, "")
    
    if include_symbol and symbol:
        return f"{symbol}{formatted} {currency}"
    return f"{formatted} {currency}"


def format_date(date_str: str, format_type: str = "short") -> str:
    """
    Format a date string for display.
    
    Args:
        date_str: Date string (ISO format or DD/MM/YYYY)
        format_type: "short" (15 dic), "medium" (15 dic 2024), "full" (15 de diciembre de 2024)
        
    Returns:
        Formatted date string
    """
    from datetime import datetime
    
    # Parse various formats
    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]:
        try:
            dt = datetime.strptime(date_str, fmt)
            break
        except ValueError:
            continue
    else:
        return date_str  # Return as-is if parsing fails
    
    months_es = [
        "", "ene", "feb", "mar", "abr", "may", "jun",
        "jul", "ago", "sep", "oct", "nov", "dic"
    ]
    months_full = [
        "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
    ]
    
    day = dt.day
    month_short = months_es[dt.month]
    month_full = months_full[dt.month]
    year = dt.year
    
    if format_type == "short":
        return f"{day} {month_short}"
    elif format_type == "medium":
        return f"{day} {month_short} {year}"
    else:  # full
        return f"{day} de {month_full} de {year}"


def format_percentage(value: float, decimals: int = 0) -> str:
    """
    Format a percentage value.
    
    Args:
        value: Percentage value (0-100)
        decimals: Number of decimal places
        
    Returns:
        Formatted string, e.g., "85%"
    """
    if decimals == 0:
        return f"{int(round(value))}%"
    return f"{value:.{decimals}f}%"


def format_phone(phone: str) -> str:
    """
    Format phone number for display.
    
    Args:
        phone: Phone number (e.g., "+573115084628")
        
    Returns:
        Formatted string (e.g., "+57 311 508 4628")
    """
    # Remove non-digit characters except +
    cleaned = "".join(c for c in phone if c.isdigit() or c == "+")
    
    # Simple formatting for Colombian numbers
    if cleaned.startswith("+57") and len(cleaned) == 13:
        return f"+57 {cleaned[3:6]} {cleaned[6:9]} {cleaned[9:]}"
    
    return phone  # Return as-is for other formats


def get_country_flag(country_code: str) -> str:
    """
    Get flag emoji for country code.
    
    Args:
        country_code: ISO 3166-1 alpha-2 code (e.g., "CO")
        
    Returns:
        Flag emoji or empty string
    """
    return COUNTRY_FLAGS.get(country_code.upper(), "")


def get_category_emoji(category_slug: str) -> str:
    """
    Get emoji for category slug.
    
    Args:
        category_slug: Category slug (e.g., "lodging")
        
    Returns:
        Category emoji or default
    """
    return CATEGORY_EMOJIS.get(category_slug.lower(), "📦")


# ─────────────────────────────────────────────────────────────────────────────
# Message Templates
# ─────────────────────────────────────────────────────────────────────────────

def format_welcome_message(name: str | None = None) -> str:
    """
    Format welcome message for new users.
    
    Args:
        name: User's name if known
        
    Returns:
        Welcome message
    """
    greeting = f"¡Hola{', ' + name if name else ''}! {Emoji.WAVE}"
    
    return f"""{greeting}

Soy tu asistente de finanzas personales para viajes.

Te ayudo a:
{Emoji.POINT_RIGHT} Registrar gastos por voz, texto o foto
{Emoji.POINT_RIGHT} Controlar tu presupuesto por categoría
{Emoji.POINT_RIGHT} Ver reportes y estadísticas

Para comenzar, necesito conocerte mejor.
{bold('¿Cómo te llamas?')}"""


def format_trip_summary(
    name: str,
    start_date: str,
    end_date: str,
    country: str,
    city: str | None,
    currency: str
) -> str:
    """
    Format trip configuration summary.
    
    Args:
        name: Trip name
        start_date: Start date
        end_date: End date
        country: Destination country code
        city: Destination city
        currency: Local currency code
        
    Returns:
        Formatted trip summary
    """
    flag = get_country_flag(country)
    location = f"{flag} {country}"
    if city:
        location += f" ({city})"
    
    return f"""
{Emoji.PIN} {bold(name)}
{Emoji.CALENDAR} {format_date(start_date)} - {format_date(end_date)}
{Emoji.GLOBE} {location}
{Emoji.DOLLAR} Moneda local: {currency}
""".strip()


def format_budget_summary(
    trip_name: str,
    total: Decimal | float,
    currency: str,
    allocations: list[dict[str, Any]],
    funding_sources: list[dict[str, Any]]
) -> str:
    """
    Format budget configuration summary.
    
    Args:
        trip_name: Name of the trip
        total: Total budget amount
        currency: Budget currency
        allocations: List of category allocations
        funding_sources: List of funding sources
        
    Returns:
        Formatted budget summary
    """
    lines = [
        f"{Emoji.CHART} {bold(trip_name)}",
        f"{Emoji.MONEY_BAG} Total: {format_currency(total, currency)}",
        "",
        bold("Categorías:")
    ]
    
    for alloc in allocations:
        emoji = get_category_emoji(alloc.get("category_slug", "misc"))
        name = alloc.get("category_name", "Sin categoría")
        amount = alloc.get("amount", 0)
        lines.append(f"{emoji} {name}: {format_currency(amount, currency)}")
    
    if funding_sources:
        lines.append("")
        lines.append(bold("Fuentes:"))
        for source in funding_sources:
            source_type = source.get("type", "unknown")
            if source_type == "card":
                card_name = source.get("name", "Tarjeta")
                last_four = source.get("last_four", "****")
                is_default = source.get("is_default", False)
                default_tag = " (principal)" if is_default else ""
                lines.append(f"{Emoji.CARD} {card_name} ****{last_four}{default_tag}")
            elif source_type == "cash":
                amount = source.get("amount", 0)
                cash_currency = source.get("currency", currency)
                lines.append(f"{Emoji.DOLLAR} {format_currency(amount, cash_currency)} efectivo")
    
    return "\n".join(lines)


def format_expense_confirmation(
    amount: Decimal | float,
    currency: str,
    description: str,
    category: str,
    method: str
) -> str:
    """
    Format expense confirmation message.
    
    Args:
        amount: Expense amount
        currency: Currency code
        description: Expense description
        category: Category name
        method: Payment method (cash/card)
        
    Returns:
        Formatted confirmation
    """
    category_emoji = get_category_emoji(category)
    method_emoji = Emoji.DOLLAR if method == "cash" else Emoji.CARD
    
    return f"""{Emoji.CHECK} {bold('Gasto registrado')}

{Emoji.MONEY_BAG} {format_currency(amount, currency)}
{category_emoji} {category}
{method_emoji} {method.capitalize()}
{Emoji.RECEIPT} {description}"""


def format_error_message(error_type: str, details: str | None = None) -> str:
    """
    Format an error message for the user.
    
    Args:
        error_type: Type of error
        details: Additional details
        
    Returns:
        User-friendly error message
    """
    messages = {
        "invalid_amount": "No pude entender el monto. Por favor, escribe un número válido.",
        "invalid_date": "No pude entender la fecha. Usa el formato DD/MM/YYYY.",
        "invalid_currency": "No reconozco esa moneda. Usa códigos como USD, COP, MXN.",
        "no_active_trip": "No tienes un viaje activo. ¿Quieres configurar uno?",
        "no_active_budget": "No tienes un presupuesto activo para este viaje.",
        "processing_error": "Hubo un error procesando tu mensaje. Por favor, intenta de nuevo.",
        "unknown": "Algo salió mal. Por favor, intenta de nuevo.",
    }
    
    message = messages.get(error_type, messages["unknown"])
    
    if details:
        message += f"\n\n{italic(details)}"
    
    return f"{Emoji.WARNING} {message}"


def chunk_message(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> list[str]:
    """
    Split a long message into chunks that fit WhatsApp limits.
    
    Args:
        text: Long message text
        max_length: Maximum chunk size
        
    Returns:
        List of message chunks
    """
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    current_chunk = ""
    
    # Split by paragraphs first
    paragraphs = text.split("\n\n")
    
    for para in paragraphs:
        # If paragraph itself is too long, split by lines
        if len(para) > max_length:
            lines = para.split("\n")
            for line in lines:
                if len(current_chunk) + len(line) + 2 <= max_length:
                    current_chunk += ("\n" if current_chunk else "") + line
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = line
        else:
            if len(current_chunk) + len(para) + 4 <= max_length:
                current_chunk += ("\n\n" if current_chunk else "") + para
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    # Add continuation indicators
    if len(chunks) > 1:
        for i in range(len(chunks) - 1):
            chunks[i] += f"\n\n{italic(f'(continúa {i+2}/{len(chunks)})')}"
    
    return chunks


def create_response(
    body: str,
    media_url: str | None = None,
    quick_replies: list[str] | None = None
) -> FormattedResponse:
    """
    Create a formatted response object.
    
    Args:
        body: Message text
        media_url: Optional media URL
        quick_replies: Optional quick reply suggestions
        
    Returns:
        FormattedResponse object
    """
    chunks = chunk_message(body) if len(body) > MAX_MESSAGE_LENGTH else []
    
    return FormattedResponse(
        body=body,
        media_url=media_url,
        chunks=chunks,
        quick_replies=quick_replies or []
    )

