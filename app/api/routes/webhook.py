"""
Twilio WhatsApp webhook endpoint.

Handles incoming messages from Twilio and routes them to the Configuration Agent.
This module should NOT contain business logic - it's a thin proxy layer.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Form, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import (
    DbSession,
    TwilioClient,
    get_or_create_user,
    validate_twilio_signature,
)
from app.integrations.whatsapp import (
    Emoji,
    TwilioWhatsAppClient,
    chunk_message,
    parse_twilio_webhook,
)
from app.logging_config import get_logger
from app.models import ConversationState

logger = get_logger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhook"])


# ─────────────────────────────────────────────────────────────────────────────
# Conversation State Helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_active_conversation(db: Session, user_id) -> ConversationState | None:
    """Get the active conversation for a user, if any."""
    return db.query(ConversationState).filter(
        ConversationState.user_id == user_id,
        ConversationState.status == "active"
    ).first()


# ─────────────────────────────────────────────────────────────────────────────
# Agent Router
# ─────────────────────────────────────────────────────────────────────────────

async def route_to_agent(
    phone_number: str,
    message_body: str,
    message_type: str,
    user_id: UUID,
    conversation_id: UUID | None,
    profile_name: str | None,
    db: Session
) -> str:
    """
    Route message to the Configuration Agent.
    
    Args:
        phone_number: User's phone number
        message_body: Text content of the message
        message_type: Type of message (text, audio, image)
        user_id: User UUID
        conversation_id: Active conversation UUID (if any)
        profile_name: WhatsApp profile name
        db: Database session
        
    Returns:
        Response text from the agent
    """
    from app.agents.configuration_agent import process_message
    
    result = await process_message(
        user_id=user_id,
        phone_number=phone_number,
        message_body=message_body,
        db=db,
        message_type=message_type,
        conversation_id=conversation_id,
        profile_name=profile_name,
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
    3. Identifies or creates the user
    4. Routes to the Configuration Agent (or appropriate agent)
    5. Sends the response back via Twilio API
    
    The actual conversation logic is handled by the agent (Phase 3D),
    NOT by this webhook endpoint.
    
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
        # Get or create user
        user = get_or_create_user(db, message.phone_number, message.profile_name)
        
        # Update last interaction timestamp
        user.last_whatsapp_interaction = datetime.utcnow()
        user.last_active_at = datetime.utcnow()
        db.commit()
        
        # Get active conversation (if any)
        conversation = get_active_conversation(db, user.id)
        
        # Check if conversation is expired
        if conversation and conversation.is_expired:
            conversation.expire()
            db.commit()
            conversation = None
        
        # Route to agent for processing
        response_text = await route_to_agent(
            phone_number=message.phone_number,
            message_body=message.body,
            message_type=message.message_type.value,
            user_id=user.id,
            conversation_id=conversation.id if conversation else None,
            profile_name=message.profile_name,
            db=db
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
            user_id=str(user.id),
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
