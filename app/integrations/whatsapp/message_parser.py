"""
Parse incoming Twilio WhatsApp webhook messages.

This module handles parsing of Twilio webhook payloads into structured
message objects that can be processed by the application.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from app.logging_config import get_logger

logger = get_logger(__name__)


class MessageType(str, Enum):
    """Type of incoming WhatsApp message."""
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"
    LOCATION = "location"
    CONTACT = "contact"
    BUTTON_REPLY = "button_reply"
    LIST_REPLY = "list_reply"
    UNKNOWN = "unknown"


@dataclass
class MediaContent:
    """Media attachment in a message."""
    url: str
    content_type: str
    media_id: str | None = None
    filename: str | None = None
    size_bytes: int | None = None


@dataclass
class LocationContent:
    """Location data from a message."""
    latitude: float
    longitude: float
    label: str | None = None
    address: str | None = None


@dataclass
class ParsedMessage:
    """
    Structured representation of an incoming WhatsApp message.
    
    Attributes:
        message_sid: Unique Twilio message ID
        phone_number: Sender's phone number (without whatsapp: prefix)
        phone_number_raw: Raw phone number as received from Twilio
        body: Text content of the message
        message_type: Type of message (text, image, audio, etc.)
        media: List of media attachments
        location: Location data if present
        profile_name: WhatsApp profile name of sender
        num_media: Number of media attachments
        num_segments: Number of SMS segments
        timestamp: When the message was received
        raw_payload: Original Twilio webhook payload
    """
    message_sid: str
    phone_number: str
    phone_number_raw: str
    body: str
    message_type: MessageType
    media: list[MediaContent] = field(default_factory=list)
    location: LocationContent | None = None
    profile_name: str | None = None
    num_media: int = 0
    num_segments: int = 1
    timestamp: datetime = field(default_factory=datetime.utcnow)
    raw_payload: dict[str, Any] = field(default_factory=dict)
    
    @property
    def has_media(self) -> bool:
        """Check if message has media attachments."""
        return len(self.media) > 0
    
    @property
    def is_text_only(self) -> bool:
        """Check if message is text-only (no media)."""
        return self.message_type == MessageType.TEXT and not self.has_media
    
    @property
    def display_phone(self) -> str:
        """Phone number formatted for display."""
        # Format: +57 311 508 4628
        if len(self.phone_number) >= 10:
            return self.phone_number  # TODO: Better formatting
        return self.phone_number


def _extract_phone_number(raw_phone: str) -> str:
    """
    Extract clean phone number from Twilio format.
    
    Args:
        raw_phone: Phone in format "whatsapp:+573115084628"
        
    Returns:
        Clean phone number: "+573115084628"
    """
    if raw_phone.startswith("whatsapp:"):
        return raw_phone[9:]  # Remove "whatsapp:" prefix
    return raw_phone


def _determine_message_type(
    body: str,
    num_media: int,
    media_content_types: list[str],
    payload: dict[str, Any]
) -> MessageType:
    """
    Determine the type of message based on content.
    
    Args:
        body: Message text
        num_media: Number of media attachments
        media_content_types: List of media MIME types
        payload: Full webhook payload
        
    Returns:
        MessageType enum value
    """
    # Check for button/list replies (interactive messages)
    if payload.get("ButtonPayload") or payload.get("ButtonText"):
        return MessageType.BUTTON_REPLY
    if payload.get("ListId"):
        return MessageType.LIST_REPLY
    
    # Check for location
    if payload.get("Latitude") and payload.get("Longitude"):
        return MessageType.LOCATION
    
    # Check for media
    if num_media > 0 and media_content_types:
        first_type = media_content_types[0].lower()
        
        if "image" in first_type:
            return MessageType.IMAGE
        elif "audio" in first_type or "ogg" in first_type:
            return MessageType.AUDIO
        elif "video" in first_type:
            return MessageType.VIDEO
        elif "pdf" in first_type or "document" in first_type:
            return MessageType.DOCUMENT
        else:
            return MessageType.DOCUMENT  # Default for unknown media
    
    # Default to text
    if body:
        return MessageType.TEXT
    
    return MessageType.UNKNOWN


def _extract_media(payload: dict[str, Any], num_media: int) -> list[MediaContent]:
    """
    Extract media attachments from webhook payload.
    
    Twilio sends media as MediaUrl0, MediaUrl1, etc.
    
    Args:
        payload: Webhook payload
        num_media: Number of media items
        
    Returns:
        List of MediaContent objects
    """
    media_list = []
    
    for i in range(num_media):
        url = payload.get(f"MediaUrl{i}")
        content_type = payload.get(f"MediaContentType{i}", "application/octet-stream")
        
        if url:
            media_list.append(MediaContent(
                url=url,
                content_type=content_type,
                media_id=payload.get(f"MediaId{i}"),
                filename=None,  # Not provided by Twilio
                size_bytes=None  # Not provided directly
            ))
    
    return media_list


def _extract_location(payload: dict[str, Any]) -> LocationContent | None:
    """
    Extract location data from webhook payload.
    
    Args:
        payload: Webhook payload
        
    Returns:
        LocationContent or None
    """
    lat = payload.get("Latitude")
    lon = payload.get("Longitude")
    
    if lat and lon:
        try:
            return LocationContent(
                latitude=float(lat),
                longitude=float(lon),
                label=payload.get("Label"),
                address=payload.get("Address")
            )
        except (ValueError, TypeError):
            logger.warning("invalid_location_data", lat=lat, lon=lon)
            return None
    
    return None


def parse_twilio_webhook(payload: dict[str, Any]) -> ParsedMessage:
    """
    Parse a Twilio WhatsApp webhook payload into a structured message.
    
    Args:
        payload: Dictionary from Twilio webhook (form data)
        
    Returns:
        ParsedMessage object
        
    Example payload:
        {
            "MessageSid": "SMxxxxxxxx",
            "From": "whatsapp:+573115084628",
            "To": "whatsapp:+14155238886",
            "Body": "Hola, quiero registrar un gasto",
            "NumMedia": "0",
            "ProfileName": "Harrison",
            ...
        }
    """
    # Extract basic fields
    message_sid = payload.get("MessageSid", payload.get("SmsSid", "unknown"))
    from_raw = payload.get("From", "")
    body = payload.get("Body", "").strip()
    profile_name = payload.get("ProfileName")
    
    # Parse numeric fields
    try:
        num_media = int(payload.get("NumMedia", 0))
    except (ValueError, TypeError):
        num_media = 0
    
    try:
        num_segments = int(payload.get("NumSegments", 1))
    except (ValueError, TypeError):
        num_segments = 1
    
    # Extract media content types
    media_content_types = []
    for i in range(num_media):
        ct = payload.get(f"MediaContentType{i}")
        if ct:
            media_content_types.append(ct)
    
    # Determine message type
    message_type = _determine_message_type(
        body, num_media, media_content_types, payload
    )
    
    # Extract media and location
    media = _extract_media(payload, num_media)
    location = _extract_location(payload)
    
    parsed = ParsedMessage(
        message_sid=message_sid,
        phone_number=_extract_phone_number(from_raw),
        phone_number_raw=from_raw,
        body=body,
        message_type=message_type,
        media=media,
        location=location,
        profile_name=profile_name,
        num_media=num_media,
        num_segments=num_segments,
        timestamp=datetime.utcnow(),
        raw_payload=payload
    )
    
    logger.info(
        "twilio_message_parsed",
        message_sid=message_sid,
        phone=parsed.phone_number[-4:],  # Last 4 digits for privacy
        message_type=message_type.value,
        body_preview=body[:30] if body else None,
        num_media=num_media,
        profile_name=profile_name
    )
    
    return parsed


def extract_country_code(phone_number: str) -> str | None:
    """
    Extract country code from phone number.
    
    Args:
        phone_number: Phone number with country code (e.g., "+573115084628")
        
    Returns:
        Country code (e.g., "57" for Colombia) or None
    """
    # Remove + prefix if present
    cleaned = phone_number.lstrip("+")
    
    # Common country codes (add more as needed)
    # Order matters: check longer codes first
    country_codes = [
        ("52", "MX"),   # Mexico
        ("57", "CO"),   # Colombia
        ("51", "PE"),   # Peru
        ("593", "EC"),  # Ecuador
        ("56", "CL"),   # Chile
        ("54", "AR"),   # Argentina
        ("55", "BR"),   # Brazil
        ("1", "US"),    # USA/Canada
        ("34", "ES"),   # Spain
    ]
    
    for code, _ in sorted(country_codes, key=lambda x: -len(x[0])):
        if cleaned.startswith(code):
            return code
    
    return None


def infer_timezone_from_phone(phone_number: str) -> str | None:
    """
    Infer timezone from phone number country code.
    
    Args:
        phone_number: Phone number with country code
        
    Returns:
        IANA timezone string or None
    """
    country_code = extract_country_code(phone_number)
    
    # Default timezone per country code
    timezone_map = {
        "52": "America/Mexico_City",
        "57": "America/Bogota",
        "51": "America/Lima",
        "593": "America/Guayaquil",
        "56": "America/Santiago",
        "54": "America/Buenos_Aires",
        "55": "America/Sao_Paulo",
        "1": "America/New_York",
        "34": "Europe/Madrid",
    }
    
    return timezone_map.get(country_code) if country_code else None


def is_join_message(body: str) -> bool:
    """
    Check if message is a Twilio sandbox join message.
    
    Args:
        body: Message body text
        
    Returns:
        True if this is a join message
    """
    body_lower = body.lower().strip()
    return body_lower.startswith("join ")


def extract_join_code(body: str) -> str | None:
    """
    Extract sandbox join code from message.
    
    Args:
        body: Message body (e.g., "join happy-elephant")
        
    Returns:
        Join code or None
    """
    match = re.match(r"^join\s+(.+)$", body.strip(), re.IGNORECASE)
    return match.group(1).strip() if match else None

