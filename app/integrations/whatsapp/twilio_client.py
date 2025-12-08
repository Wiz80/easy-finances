"""
Twilio WhatsApp client for sending and receiving messages.

This module provides a clean interface for interacting with Twilio's
WhatsApp API, handling message sending, media downloads, and webhook
signature validation.
"""

import hashlib
import hmac
from base64 import b64encode
from typing import Any
from urllib.parse import urlencode

from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class TwilioWhatsAppClient:
    """
    Client for Twilio WhatsApp API operations.
    
    Handles:
    - Sending text messages
    - Sending media (images, documents)
    - Downloading media from incoming messages
    - Webhook signature validation
    
    Example:
        client = TwilioWhatsAppClient()
        await client.send_message(
            to="+573115084628",
            body="¡Hola! Soy tu asistente de finanzas."
        )
    """

    def __init__(
        self,
        account_sid: str | None = None,
        auth_token: str | None = None,
        from_number: str | None = None,
    ):
        """
        Initialize Twilio client.
        
        Args:
            account_sid: Twilio Account SID (defaults to settings)
            auth_token: Twilio Auth Token (defaults to settings)
            from_number: WhatsApp sender number (defaults to settings)
        """
        self.account_sid = account_sid or settings.twilio_account_sid
        self.auth_token = auth_token or settings.twilio_auth_token
        self.from_number = from_number or settings.twilio_whatsapp_from
        
        if not self.account_sid or not self.auth_token:
            logger.warning(
                "twilio_credentials_missing",
                message="Twilio credentials not configured. Messages will not be sent."
            )
            self._client = None
        else:
            self._client = Client(self.account_sid, self.auth_token)
            logger.info(
                "twilio_client_initialized",
                from_number=self.from_number
            )

    @property
    def is_configured(self) -> bool:
        """Check if Twilio client is properly configured."""
        return self._client is not None

    def _format_whatsapp_number(self, phone: str) -> str:
        """
        Format phone number for WhatsApp.
        
        Args:
            phone: Phone number (with or without whatsapp: prefix)
            
        Returns:
            Formatted WhatsApp number (whatsapp:+XXXXXXXXXXX)
        """
        if phone.startswith("whatsapp:"):
            return phone
        
        # Remove any non-digit characters except +
        cleaned = "".join(c for c in phone if c.isdigit() or c == "+")
        
        # Ensure it starts with +
        if not cleaned.startswith("+"):
            cleaned = f"+{cleaned}"
        
        return f"whatsapp:{cleaned}"

    async def send_message(
        self,
        to: str,
        body: str,
        media_url: str | None = None,
    ) -> dict[str, Any]:
        """
        Send a WhatsApp message via Twilio.
        
        Args:
            to: Recipient phone number
            body: Message text content
            media_url: Optional URL to media file (image, PDF)
            
        Returns:
            Dict with message details (sid, status, etc.)
            
        Raises:
            TwilioClientError: If sending fails
        """
        if not self.is_configured:
            logger.error(
                "twilio_send_failed",
                reason="Client not configured",
                to=to
            )
            return {
                "success": False,
                "error": "Twilio client not configured",
                "sid": None
            }
        
        to_formatted = self._format_whatsapp_number(to)
        
        try:
            message_params = {
                "from_": self.from_number,
                "to": to_formatted,
                "body": body,
            }
            
            if media_url:
                message_params["media_url"] = [media_url]
            
            message = self._client.messages.create(**message_params)
            
            logger.info(
                "twilio_message_sent",
                message_sid=message.sid,
                to=to_formatted,
                status=message.status,
                body_preview=body[:50] if body else None
            )
            
            return {
                "success": True,
                "sid": message.sid,
                "status": message.status,
                "to": to_formatted,
                "from": self.from_number,
            }
            
        except TwilioRestException as e:
            logger.error(
                "twilio_send_error",
                error_code=e.code,
                error_message=str(e),
                to=to_formatted
            )
            return {
                "success": False,
                "error": str(e),
                "error_code": e.code,
                "sid": None
            }
        except Exception as e:
            logger.error(
                "twilio_send_unexpected_error",
                error=str(e),
                to=to_formatted,
                exc_info=True
            )
            return {
                "success": False,
                "error": str(e),
                "sid": None
            }

    async def send_template_message(
        self,
        to: str,
        template_sid: str,
        template_variables: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Send a pre-approved WhatsApp template message.
        
        Required for initiating conversations outside the 24-hour window.
        
        Args:
            to: Recipient phone number
            template_sid: Content SID of the approved template
            template_variables: Variables to substitute in template
            
        Returns:
            Dict with message details
        """
        if not self.is_configured:
            return {
                "success": False,
                "error": "Twilio client not configured",
                "sid": None
            }
        
        to_formatted = self._format_whatsapp_number(to)
        
        try:
            message_params = {
                "from_": self.from_number,
                "to": to_formatted,
                "content_sid": template_sid,
            }
            
            if template_variables:
                message_params["content_variables"] = str(template_variables)
            
            message = self._client.messages.create(**message_params)
            
            logger.info(
                "twilio_template_sent",
                message_sid=message.sid,
                to=to_formatted,
                template_sid=template_sid
            )
            
            return {
                "success": True,
                "sid": message.sid,
                "status": message.status,
            }
            
        except TwilioRestException as e:
            logger.error(
                "twilio_template_error",
                error_code=e.code,
                error_message=str(e),
                to=to_formatted
            )
            return {
                "success": False,
                "error": str(e),
                "error_code": e.code,
                "sid": None
            }

    def download_media(self, media_url: str) -> bytes | None:
        """
        Download media from a Twilio media URL.
        
        Args:
            media_url: Twilio media URL from incoming message
            
        Returns:
            Media bytes or None if download fails
        """
        if not self.is_configured:
            return None
        
        try:
            import httpx
            
            # Twilio media URLs require authentication
            response = httpx.get(
                media_url,
                auth=(self.account_sid, self.auth_token),
                follow_redirects=True,
                timeout=30.0
            )
            response.raise_for_status()
            
            logger.info(
                "twilio_media_downloaded",
                url=media_url[:50],
                size_bytes=len(response.content)
            )
            
            return response.content
            
        except Exception as e:
            logger.error(
                "twilio_media_download_error",
                error=str(e),
                url=media_url[:50]
            )
            return None

    def validate_webhook_signature(
        self,
        url: str,
        params: dict[str, str],
        signature: str,
    ) -> bool:
        """
        Validate Twilio webhook request signature.
        
        Args:
            url: Full webhook URL
            params: Request parameters (form data)
            signature: X-Twilio-Signature header value
            
        Returns:
            True if signature is valid
        """
        if not self.auth_token:
            logger.warning("twilio_signature_validation_skipped", reason="No auth token")
            return True  # Skip validation in development
        
        # Sort and concatenate params
        sorted_params = sorted(params.items())
        param_string = urlencode(sorted_params)
        
        # Create signature base
        data = f"{url}{param_string}"
        
        # Compute HMAC-SHA1
        computed_sig = b64encode(
            hmac.new(
                self.auth_token.encode("utf-8"),
                data.encode("utf-8"),
                hashlib.sha1
            ).digest()
        ).decode("utf-8")
        
        is_valid = hmac.compare_digest(computed_sig, signature)
        
        if not is_valid:
            logger.warning(
                "twilio_invalid_signature",
                url=url,
                expected=computed_sig[:10] + "...",
                received=signature[:10] + "..."
            )
        
        return is_valid

    def get_message_status(self, message_sid: str) -> dict[str, Any] | None:
        """
        Get status of a sent message.
        
        Args:
            message_sid: Twilio message SID
            
        Returns:
            Message details or None if not found
        """
        if not self.is_configured:
            return None
        
        try:
            message = self._client.messages(message_sid).fetch()
            return {
                "sid": message.sid,
                "status": message.status,
                "error_code": message.error_code,
                "error_message": message.error_message,
                "date_sent": message.date_sent,
                "date_updated": message.date_updated,
            }
        except TwilioRestException as e:
            logger.error(
                "twilio_status_fetch_error",
                message_sid=message_sid,
                error=str(e)
            )
            return None


# Global client instance (lazy initialization)
_twilio_client: TwilioWhatsAppClient | None = None


def get_twilio_client() -> TwilioWhatsAppClient:
    """
    Get or create the global Twilio client instance.
    
    Returns:
        TwilioWhatsAppClient instance
    """
    global _twilio_client
    if _twilio_client is None:
        _twilio_client = TwilioWhatsAppClient()
    return _twilio_client

