"""
Conversation Cache using Azure Blob Storage.

This module provides a fast, TTL-based cache for conversation state
that persists between HTTP requests. It's designed to:
- Store conversation context temporarily during active sessions
- Auto-expire conversations after inactivity
- Be faster than DB lookups for hot conversation data

Reference: https://docs.langchain.com/oss/python/integrations/document_loaders/azure_blob_storage
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import BlobServiceClient, ContentSettings

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class CachedConversation:
    """
    Cached conversation state.
    
    This is a lightweight representation of the conversation state
    optimized for fast serialization/deserialization.
    """
    user_id: str
    phone_number: str
    
    # Conversation identity
    conversation_id: str | None = None  # DB conversation ID for syncing
    
    # Flow state
    current_flow: str = "unknown"
    current_step: str | None = None
    pending_field: str | None = None
    flow_data: dict[str, Any] = field(default_factory=dict)
    
    # Agent routing
    active_agent: str | None = None
    agent_locked: bool = False
    lock_reason: str | None = None
    
    # User context (cached to avoid DB lookups)
    user_name: str | None = None
    home_currency: str | None = None
    timezone: str | None = None
    onboarding_completed: bool = False
    
    # Conversation tracking
    message_count: int = 0
    last_user_message: str | None = None
    last_bot_message: str | None = None
    
    # Timestamps
    created_at: str = ""
    updated_at: str = ""
    expires_at: str = ""
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "CachedConversation":
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    def update_timestamp(self) -> None:
        """Update the updated_at and expires_at timestamps."""
        now = datetime.utcnow()
        self.updated_at = now.isoformat()
        self.expires_at = (now + timedelta(hours=settings.azure_conversation_ttl_hours)).isoformat()
    
    def is_expired(self) -> bool:
        """Check if the conversation has expired."""
        if not self.expires_at:
            return True
        try:
            expires = datetime.fromisoformat(self.expires_at)
            return datetime.utcnow() > expires
        except ValueError:
            return True


class ConversationCache:
    """
    Azure Blob Storage-based conversation cache.
    
    Each conversation is stored as a JSON blob with the phone number as key.
    This provides:
    - Fast lookups by phone number
    - Automatic expiration via blob lifecycle policies
    - Separation from the main database
    """
    
    def __init__(self):
        self._client: BlobServiceClient | None = None
        self._container_name = settings.azure_conversation_container
        self._initialized = False
    
    def _get_client(self) -> BlobServiceClient:
        """Get or create the blob service client."""
        if self._client is None:
            # Prefer Account Name + Key (more reliable)
            if settings.azure_storage_account_name and settings.azure_storage_account_key:
                account_url = f"https://{settings.azure_storage_account_name}.blob.core.windows.net"
                self._client = BlobServiceClient(
                    account_url=account_url,
                    credential=settings.azure_storage_account_key,
                )
                logger.debug("azure_client_created", method="account_key")
            elif settings.azure_storage_connection_string:
                self._client = BlobServiceClient.from_connection_string(
                    settings.azure_storage_connection_string
                )
                logger.debug("azure_client_created", method="connection_string")
            else:
                raise ValueError("Azure Storage not configured. Set AZURE_STORAGE_ACCOUNT_NAME + AZURE_STORAGE_ACCOUNT_KEY")
        
        return self._client
    
    def _ensure_container(self) -> None:
        """Ensure the container exists."""
        if self._initialized:
            return
        
        try:
            client = self._get_client()
            container = client.get_container_client(self._container_name)
            
            if not container.exists():
                container.create_container()
                logger.info("azure_container_created", container=self._container_name)
            
            self._initialized = True
        except Exception as e:
            logger.error("azure_container_error", error=str(e))
            raise
    
    def _get_blob_name(self, phone_number: str) -> str:
        """Generate blob name from phone number."""
        # Remove special characters for safe blob naming
        safe_phone = phone_number.replace("+", "").replace("-", "").replace(" ", "")
        return f"conversations/{safe_phone}.json"
    
    async def get(self, phone_number: str) -> CachedConversation | None:
        """
        Get cached conversation by phone number.
        
        Args:
            phone_number: User's phone number
            
        Returns:
            CachedConversation if found and not expired, None otherwise
        """
        try:
            self._ensure_container()
            client = self._get_client()
            blob_name = self._get_blob_name(phone_number)
            
            blob_client = client.get_blob_client(
                container=self._container_name,
                blob=blob_name
            )
            
            # Download and parse
            data = blob_client.download_blob().readall()
            conversation = CachedConversation.from_dict(json.loads(data))
            
            # Check expiration
            if conversation.is_expired():
                logger.debug("conversation_cache_expired", phone=phone_number)
                await self.delete(phone_number)
                return None
            
            logger.debug(
                "conversation_cache_hit",
                phone=phone_number,
                flow=conversation.current_flow,
                step=conversation.pending_field
            )
            return conversation
            
        except ResourceNotFoundError:
            logger.debug("conversation_cache_miss", phone=phone_number)
            return None
        except Exception as e:
            logger.error("conversation_cache_get_error", phone=phone_number, error=str(e))
            return None
    
    async def set(
        self,
        phone_number: str,
        conversation: CachedConversation,
    ) -> bool:
        """
        Save conversation to cache.
        
        Args:
            phone_number: User's phone number
            conversation: Conversation state to cache
            
        Returns:
            True if successful
        """
        try:
            self._ensure_container()
            client = self._get_client()
            blob_name = self._get_blob_name(phone_number)
            
            # Update timestamps
            conversation.update_timestamp()
            if not conversation.created_at:
                conversation.created_at = conversation.updated_at
            
            # Serialize
            data = json.dumps(conversation.to_dict(), ensure_ascii=False, indent=2)
            
            # Upload
            blob_client = client.get_blob_client(
                container=self._container_name,
                blob=blob_name
            )
            
            blob_client.upload_blob(
                data,
                overwrite=True,
                content_settings=ContentSettings(content_type="application/json")
            )
            
            logger.debug(
                "conversation_cache_set",
                phone=phone_number,
                flow=conversation.current_flow,
                step=conversation.pending_field
            )
            return True
            
        except Exception as e:
            logger.error("conversation_cache_set_error", phone=phone_number, error=str(e))
            return False
    
    async def delete(self, phone_number: str) -> bool:
        """
        Delete conversation from cache.
        
        Args:
            phone_number: User's phone number
            
        Returns:
            True if successful
        """
        try:
            self._ensure_container()
            client = self._get_client()
            blob_name = self._get_blob_name(phone_number)
            
            blob_client = client.get_blob_client(
                container=self._container_name,
                blob=blob_name
            )
            
            blob_client.delete_blob()
            
            logger.debug("conversation_cache_deleted", phone=phone_number)
            return True
            
        except ResourceNotFoundError:
            return True  # Already deleted
        except Exception as e:
            logger.error("conversation_cache_delete_error", phone=phone_number, error=str(e))
            return False
    
    async def update_from_state(
        self,
        phone_number: str,
        user_id: str | UUID,
        current_flow: str,
        pending_field: str | None,
        flow_data: dict,
        user_name: str | None = None,
        home_currency: str | None = None,
        timezone: str | None = None,
        onboarding_completed: bool = False,
        active_agent: str | None = None,
        agent_locked: bool = False,
        lock_reason: str | None = None,
        last_user_message: str | None = None,
        last_bot_message: str | None = None,
        current_step: str | None = None,  # Explicit step parameter
        conversation_id: str | UUID | None = None,  # DB conversation ID
    ) -> CachedConversation:
        """
        Update or create cached conversation from agent state.
        
        This is the main method to call after processing a message.
        
        Args:
            pending_field: Field we're waiting for from the user (for intent detection)
            current_step: Current step in the flow (can be same as pending_field)
        """
        # Try to get existing conversation
        existing = await self.get(phone_number)
        
        # current_step defaults to pending_field if not explicitly provided
        step = current_step or pending_field
        
        # Convert conversation_id to string if provided
        conv_id_str = str(conversation_id) if conversation_id else None
        
        if existing:
            # Update existing
            existing.current_flow = current_flow
            existing.current_step = step
            existing.pending_field = pending_field
            existing.flow_data = flow_data
            existing.active_agent = active_agent
            existing.agent_locked = agent_locked
            existing.lock_reason = lock_reason
            existing.message_count += 1
            
            # Update conversation_id if provided
            if conv_id_str:
                existing.conversation_id = conv_id_str
            
            # Update user context if provided
            if user_name:
                existing.user_name = user_name
            if home_currency:
                existing.home_currency = home_currency
            if timezone:
                existing.timezone = timezone
            existing.onboarding_completed = onboarding_completed
            
            # Update messages
            if last_user_message:
                existing.last_user_message = last_user_message
            if last_bot_message:
                existing.last_bot_message = last_bot_message
            
            await self.set(phone_number, existing)
            return existing
        else:
            # Create new
            conversation = CachedConversation(
                user_id=str(user_id),
                phone_number=phone_number,
                conversation_id=conv_id_str,
                current_flow=current_flow,
                current_step=step,
                pending_field=pending_field,
                flow_data=flow_data,
                active_agent=active_agent,
                agent_locked=agent_locked,
                lock_reason=lock_reason,
                user_name=user_name,
                home_currency=home_currency,
                timezone=timezone,
                onboarding_completed=onboarding_completed,
                message_count=1,
                last_user_message=last_user_message,
                last_bot_message=last_bot_message,
            )
            await self.set(phone_number, conversation)
            return conversation


# Global cache instance
conversation_cache = ConversationCache()

