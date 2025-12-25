"""
Twilio WhatsApp webhook endpoint.

Handles incoming messages from Twilio and routes them through the Coordinator Agent.
The Coordinator handles all routing logic to specialized agents:
- ConfigurationAgent: User setup, trips, cards, budgets
- IEAgent: Expense extraction
- CoachAgent: Financial queries

This module should NOT contain business logic - it's a thin proxy layer.
"""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Form, Request, Response

from app.api.deps import (
    DbSession,
    TwilioClient,
    validate_twilio_signature,
)
from app.integrations.whatsapp import (
    Emoji,
    TwilioWhatsAppClient,
    chunk_message,
    parse_twilio_webhook,
)
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhook"])


# ─────────────────────────────────────────────────────────────────────────────
# Agent Router (via Coordinator)
# ─────────────────────────────────────────────────────────────────────────────

async def route_to_coordinator(
    phone_number: str,
    message_body: str,
    message_type: str,
    profile_name: str | None,
    message_sid: str | None = None,
    media_url: str | None = None,
) -> str:
    """
    Route message through the Coordinator Agent.
    
    The Coordinator handles all routing logic:
    - New users → ConfigurationAgent (onboarding)
    - Expense messages → IEAgent
    - Query messages → CoachAgent
    - Commands → Coordinator (cancel, menu, help)
    
    Args:
        phone_number: User's phone number (e.g., "+573115084628")
        message_body: Text content of the message
        message_type: Type of message (text, audio, image)
        profile_name: WhatsApp profile name
        message_sid: Twilio message SID (for idempotency)
        media_url: URL for media content
        
    Returns:
        Response text from the Coordinator
    """
    from app.agents.coordinator import process_message
    
    result = await process_message(
        phone_number=phone_number,
        message_body=message_body,
        message_type=message_type,
        media_url=media_url,
        message_sid=message_sid,
        profile_name=profile_name,
    )
    
    logger.debug(
        "coordinator_result",
        success=result.success,
        agent=result.agent_used,
        method=result.routing_method,
    )
    
    return result.response_text


# ─────────────────────────────────────────────────────────────────────────────
# Webhook Endpoint
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/twilio")
async def twilio_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: DbSession,
    twilio: TwilioClient,
    # Twilio webhook fields (form-encoded)
    From: Annotated[str, Form()],
    Body: Annotated[str, Form()] = "",
    MessageSid: Annotated[str, Form()] = "",
    NumMedia: Annotated[str, Form()] = "0",
    ProfileName: Annotated[str | None, Form()] = None,
    # Signature validation
    _signature_valid: bool = Depends(validate_twilio_signature),
):
    """
    Twilio WhatsApp webhook endpoint.
    
    This endpoint:
    1. Receives incoming WhatsApp messages from Twilio
    2. Parses the message payload
    3. Routes ALL messages through the Coordinator Agent
    4. Coordinator handles user lookup, agent routing, and state management
    5. Sends the response back via Twilio API
    
    The Coordinator Agent handles:
    - User creation/lookup
    - Agent routing (Configuration, IE, Coach)
    - Sticky sessions and handoffs
    - Conversation state management
    
    Form Parameters (from Twilio):
        From: Sender phone number (whatsapp:+XXXXXXXXXXX)
        Body: Message text content
        MessageSid: Unique message identifier
        NumMedia: Number of media attachments
        ProfileName: WhatsApp profile name
    """
    # Parse the incoming webhook
    form_data = await request.form()
    payload = {key: value for key, value in form_data.items()}
    message = parse_twilio_webhook(payload)
    
    logger.info(
        "webhook_received",
        message_sid=message.message_sid,
        phone=message.phone_number[-4:],
        message_type=message.message_type.value,
        has_media=message.has_media,
        body_preview=message.body[:50] if message.body else None
    )
    
    try:
        # Get media URL if present
        media_url = None
        if message.has_media and message.media_items:
            media_url = message.media_items[0].url
        
        # Route ALL messages through Coordinator Agent
        # The Coordinator handles:
        # - User creation/lookup
        # - Agent selection (config, ie, coach)
        # - Sticky sessions
        # - Conversation state
        response_text = await route_to_coordinator(
            phone_number=message.phone_number,
            message_body=message.body,
            message_type=message.message_type.value,
            profile_name=message.profile_name,
            message_sid=message.message_sid,
            media_url=media_url,
        )
        
        # Send response via Twilio (in background to not block)
        background_tasks.add_task(
            send_response_async,
            twilio,
            message.phone_number,
            response_text
        )
        
        logger.info(
            "webhook_processed",
            message_sid=message.message_sid,
            response_length=len(response_text)
        )
        
    except Exception as e:
        logger.error(
            "webhook_error",
            message_sid=message.message_sid,
            error=str(e),
            exc_info=True
        )
        # Send error response
        background_tasks.add_task(
            send_response_async,
            twilio,
            message.phone_number,
            f"{Emoji.WARNING} Ocurrió un error procesando tu mensaje. Por favor intenta de nuevo."
        )
    
    # Return empty response to Twilio (we send response via API)
    return Response(content="", media_type="text/plain")


async def send_response_async(
    twilio: TwilioWhatsAppClient,
    to: str,
    body: str
) -> None:
    """
    Send response message asynchronously via Twilio.
    
    Handles chunking for long messages that exceed WhatsApp limits.
    """
    # Split long messages if needed (WhatsApp limit: 4096 chars)
    chunks = chunk_message(body)
    
    for chunk in chunks:
        result = await twilio.send_message(to, chunk)
        if not result.get("success"):
            logger.error(
                "send_response_failed",
                to=to[-4:],
                error=result.get("error")
            )
