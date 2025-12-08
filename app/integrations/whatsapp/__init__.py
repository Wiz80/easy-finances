"""
WhatsApp integration via Twilio.

This module provides:
- TwilioWhatsAppClient: Send and receive WhatsApp messages
- Message parsing: Parse incoming Twilio webhooks
- Response formatting: Format responses for WhatsApp

Example usage:
    from app.integrations.whatsapp import (
        get_twilio_client,
        parse_twilio_webhook,
        create_response,
        format_currency,
    )
    
    # Parse incoming webhook
    message = parse_twilio_webhook(webhook_payload)
    
    # Process and send response
    client = get_twilio_client()
    response = create_response("¡Hola! ¿En qué te puedo ayudar?")
    await client.send_message(message.phone_number, response.body)
"""

from app.integrations.whatsapp.message_parser import (
    MessageType,
    MediaContent,
    LocationContent,
    ParsedMessage,
    parse_twilio_webhook,
    extract_country_code,
    infer_timezone_from_phone,
    is_join_message,
    extract_join_code,
)

from app.integrations.whatsapp.response_formatter import (
    FormattedResponse,
    Emoji,
    CATEGORY_EMOJIS,
    COUNTRY_FLAGS,
    # Formatting helpers
    bold,
    italic,
    strikethrough,
    monospace,
    code_inline,
    format_currency,
    format_date,
    format_percentage,
    format_phone,
    get_country_flag,
    get_category_emoji,
    # Message templates
    format_welcome_message,
    format_trip_summary,
    format_budget_summary,
    format_expense_confirmation,
    format_error_message,
    chunk_message,
    create_response,
)

from app.integrations.whatsapp.twilio_client import (
    TwilioWhatsAppClient,
    get_twilio_client,
)

__all__ = [
    # Client
    "TwilioWhatsAppClient",
    "get_twilio_client",
    # Message parsing
    "MessageType",
    "MediaContent",
    "LocationContent",
    "ParsedMessage",
    "parse_twilio_webhook",
    "extract_country_code",
    "infer_timezone_from_phone",
    "is_join_message",
    "extract_join_code",
    # Response formatting
    "FormattedResponse",
    "Emoji",
    "CATEGORY_EMOJIS",
    "COUNTRY_FLAGS",
    "bold",
    "italic",
    "strikethrough",
    "monospace",
    "code_inline",
    "format_currency",
    "format_date",
    "format_percentage",
    "format_phone",
    "get_country_flag",
    "get_category_emoji",
    "format_welcome_message",
    "format_trip_summary",
    "format_budget_summary",
    "format_expense_confirmation",
    "format_error_message",
    "chunk_message",
    "create_response",
]

