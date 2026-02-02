"""
Unit Tests for Conversation Cache (Azure Blob Storage).

Tests the ConversationCache class with mocked Azure SDK.
"""

import json
import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from app.storage.conversation_cache import (
    CachedConversation,
    ConversationCache,
    conversation_cache,
)


# ─────────────────────────────────────────────────────────────────────────────
# Test: CachedConversation Data Class
# ─────────────────────────────────────────────────────────────────────────────

class TestCachedConversation:
    """Tests for the CachedConversation data class."""

    def test_create_conversation(self):
        """Test: Create a new CachedConversation."""
        conv = CachedConversation(
            user_id="user-123",
            phone_number="+573115084628",
            current_flow="onboarding",
            current_step="name",
        )
        
        assert conv.user_id == "user-123"
        assert conv.phone_number == "+573115084628"
        assert conv.current_flow == "onboarding"
        assert conv.current_step == "name"
        assert conv.message_count == 0
        assert conv.agent_locked is False

    def test_to_dict(self):
        """Test: Convert conversation to dictionary."""
        conv = CachedConversation(
            user_id="user-123",
            phone_number="+573115084628",
            current_flow="trip_setup",
            flow_data={"trip_name": "Europa 2026"},
        )
        
        data = conv.to_dict()
        
        assert isinstance(data, dict)
        assert data["user_id"] == "user-123"
        assert data["current_flow"] == "trip_setup"
        assert data["flow_data"]["trip_name"] == "Europa 2026"

    def test_from_dict(self):
        """Test: Create conversation from dictionary."""
        data = {
            "user_id": "user-456",
            "phone_number": "+573001234567",
            "current_flow": "budget_creation",
            "current_step": "amount",
            "flow_data": {"budget_name": "Vacaciones"},
            "message_count": 5,
        }
        
        conv = CachedConversation.from_dict(data)
        
        assert conv.user_id == "user-456"
        assert conv.current_flow == "budget_creation"
        assert conv.message_count == 5

    def test_from_dict_ignores_unknown_fields(self):
        """Test: Unknown fields in dictionary are ignored."""
        data = {
            "user_id": "user-789",
            "phone_number": "+573001234567",
            "unknown_field": "should be ignored",
            "another_unknown": 123,
        }
        
        conv = CachedConversation.from_dict(data)
        
        assert conv.user_id == "user-789"
        assert not hasattr(conv, "unknown_field")

    def test_update_timestamp(self):
        """Test: Update timestamps updates updated_at and expires_at."""
        conv = CachedConversation(
            user_id="user-123",
            phone_number="+573115084628",
        )
        
        assert conv.updated_at == ""
        assert conv.expires_at == ""
        
        conv.update_timestamp()
        
        assert conv.updated_at != ""
        assert conv.expires_at != ""
        
        # expires_at should be in the future
        expires = datetime.fromisoformat(conv.expires_at)
        assert expires > datetime.utcnow()

    def test_is_expired_when_no_expires_at(self):
        """Test: Conversation is expired when expires_at is empty."""
        conv = CachedConversation(
            user_id="user-123",
            phone_number="+573115084628",
            expires_at="",
        )
        
        assert conv.is_expired() is True

    def test_is_expired_when_past(self):
        """Test: Conversation is expired when expires_at is in the past."""
        past = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        
        conv = CachedConversation(
            user_id="user-123",
            phone_number="+573115084628",
            expires_at=past,
        )
        
        assert conv.is_expired() is True

    def test_is_not_expired_when_future(self):
        """Test: Conversation is not expired when expires_at is in the future."""
        future = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        
        conv = CachedConversation(
            user_id="user-123",
            phone_number="+573115084628",
            expires_at=future,
        )
        
        assert conv.is_expired() is False

    def test_is_expired_with_invalid_date(self):
        """Test: Invalid expires_at date is treated as expired."""
        conv = CachedConversation(
            user_id="user-123",
            phone_number="+573115084628",
            expires_at="not-a-date",
        )
        
        assert conv.is_expired() is True


# ─────────────────────────────────────────────────────────────────────────────
# Test: ConversationCache._get_blob_name
# ─────────────────────────────────────────────────────────────────────────────

class TestGetBlobName:
    """Tests for blob name generation."""

    def test_blob_name_from_phone(self):
        """Test: Generate blob name from phone number."""
        cache = ConversationCache()
        
        blob_name = cache._get_blob_name("+573115084628")
        
        assert blob_name == "conversations/573115084628.json"

    def test_blob_name_removes_special_chars(self):
        """Test: Some special characters are removed from blob name."""
        cache = ConversationCache()
        
        blob_name = cache._get_blob_name("+1-555-123-4567")
        
        # The implementation removes +, -, and spaces
        assert "+" not in blob_name
        assert "-" not in blob_name
        assert " " not in blob_name
        # Note: parentheses are NOT removed by the current implementation
        # The blob name should still be valid for Azure


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures for Azure Mocks
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_blob_service_client():
    """Create a mock BlobServiceClient."""
    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_blob = MagicMock()
    
    # Container exists
    mock_container.exists.return_value = True
    
    # Setup chain
    mock_client.get_container_client.return_value = mock_container
    mock_client.get_blob_client.return_value = mock_blob
    
    return mock_client, mock_container, mock_blob


@pytest.fixture
def conversation_cache_with_mock(mock_blob_service_client):
    """Create ConversationCache with mocked Azure client."""
    mock_client, mock_container, mock_blob = mock_blob_service_client
    
    cache = ConversationCache()
    cache._client = mock_client
    cache._initialized = True
    
    return cache, mock_client, mock_container, mock_blob


# ─────────────────────────────────────────────────────────────────────────────
# Test: ConversationCache.get
# ─────────────────────────────────────────────────────────────────────────────

class TestConversationCacheGet:
    """Tests for getting conversations from cache."""

    @pytest.mark.asyncio
    async def test_get_existing_conversation(self, conversation_cache_with_mock):
        """Test: Get existing non-expired conversation."""
        cache, mock_client, _, mock_blob = conversation_cache_with_mock
        
        # Setup mock data
        future = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        conv_data = {
            "user_id": "user-123",
            "phone_number": "+573115084628",
            "current_flow": "trip_setup",
            "current_step": "name",
            "expires_at": future,
        }
        
        mock_download = MagicMock()
        mock_download.readall.return_value = json.dumps(conv_data).encode()
        mock_blob.download_blob.return_value = mock_download
        
        result = await cache.get("+573115084628")
        
        assert result is not None
        assert result.user_id == "user-123"
        assert result.current_flow == "trip_setup"

    @pytest.mark.asyncio
    async def test_get_expired_conversation_returns_none(
        self, conversation_cache_with_mock
    ):
        """Test: Expired conversation returns None and is deleted."""
        cache, mock_client, _, mock_blob = conversation_cache_with_mock
        
        # Setup expired data
        past = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        conv_data = {
            "user_id": "user-123",
            "phone_number": "+573115084628",
            "current_flow": "trip_setup",
            "expires_at": past,
        }
        
        mock_download = MagicMock()
        mock_download.readall.return_value = json.dumps(conv_data).encode()
        mock_blob.download_blob.return_value = mock_download
        
        result = await cache.get("+573115084628")
        
        assert result is None
        # Should have tried to delete
        mock_blob.delete_blob.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_nonexistent_conversation_returns_none(
        self, conversation_cache_with_mock
    ):
        """Test: Non-existent conversation returns None."""
        cache, mock_client, _, mock_blob = conversation_cache_with_mock
        
        from azure.core.exceptions import ResourceNotFoundError
        mock_blob.download_blob.side_effect = ResourceNotFoundError("Not found")
        
        result = await cache.get("+573001234567")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_get_handles_json_error(self, conversation_cache_with_mock):
        """Test: JSON parse error is handled gracefully."""
        cache, mock_client, _, mock_blob = conversation_cache_with_mock
        
        mock_download = MagicMock()
        mock_download.readall.return_value = b"invalid json {"
        mock_blob.download_blob.return_value = mock_download
        
        result = await cache.get("+573001234567")
        
        # Should return None on error
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# Test: ConversationCache.set
# ─────────────────────────────────────────────────────────────────────────────

class TestConversationCacheSet:
    """Tests for setting conversations in cache."""

    @pytest.mark.asyncio
    async def test_set_conversation(self, conversation_cache_with_mock):
        """Test: Set conversation saves to blob."""
        cache, mock_client, _, mock_blob = conversation_cache_with_mock
        
        conv = CachedConversation(
            user_id="user-123",
            phone_number="+573115084628",
            current_flow="onboarding",
            current_step="currency",
        )
        
        result = await cache.set("+573115084628", conv)
        
        assert result is True
        mock_blob.upload_blob.assert_called_once()
        
        # Verify JSON content
        call_args = mock_blob.upload_blob.call_args
        uploaded_data = call_args[0][0]
        parsed = json.loads(uploaded_data)
        
        assert parsed["user_id"] == "user-123"
        assert parsed["current_flow"] == "onboarding"

    @pytest.mark.asyncio
    async def test_set_updates_timestamps(self, conversation_cache_with_mock):
        """Test: Set updates timestamps before saving."""
        cache, mock_client, _, mock_blob = conversation_cache_with_mock
        
        conv = CachedConversation(
            user_id="user-123",
            phone_number="+573115084628",
            updated_at="",
            expires_at="",
        )
        
        await cache.set("+573115084628", conv)
        
        # Timestamps should be set
        assert conv.updated_at != ""
        assert conv.expires_at != ""

    @pytest.mark.asyncio
    async def test_set_handles_upload_error(self, conversation_cache_with_mock):
        """Test: Upload error is handled gracefully."""
        cache, mock_client, _, mock_blob = conversation_cache_with_mock
        
        mock_blob.upload_blob.side_effect = Exception("Upload failed")
        
        conv = CachedConversation(
            user_id="user-123",
            phone_number="+573115084628",
        )
        
        result = await cache.set("+573115084628", conv)
        
        assert result is False


# ─────────────────────────────────────────────────────────────────────────────
# Test: ConversationCache.delete
# ─────────────────────────────────────────────────────────────────────────────

class TestConversationCacheDelete:
    """Tests for deleting conversations from cache."""

    @pytest.mark.asyncio
    async def test_delete_existing_conversation(self, conversation_cache_with_mock):
        """Test: Delete existing conversation."""
        cache, mock_client, _, mock_blob = conversation_cache_with_mock
        
        result = await cache.delete("+573115084628")
        
        assert result is True
        mock_blob.delete_blob.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_true(self, conversation_cache_with_mock):
        """Test: Delete non-existent conversation returns True."""
        cache, mock_client, _, mock_blob = conversation_cache_with_mock
        
        from azure.core.exceptions import ResourceNotFoundError
        mock_blob.delete_blob.side_effect = ResourceNotFoundError("Not found")
        
        result = await cache.delete("+573001234567")
        
        assert result is True  # Already deleted

    @pytest.mark.asyncio
    async def test_delete_handles_error(self, conversation_cache_with_mock):
        """Test: Delete error is handled gracefully."""
        cache, mock_client, _, mock_blob = conversation_cache_with_mock
        
        mock_blob.delete_blob.side_effect = Exception("Delete failed")
        
        result = await cache.delete("+573001234567")
        
        assert result is False


# ─────────────────────────────────────────────────────────────────────────────
# Test: ConversationCache.update_from_state
# ─────────────────────────────────────────────────────────────────────────────

class TestConversationCacheUpdateFromState:
    """Tests for updating cache from agent state."""

    @pytest.mark.asyncio
    async def test_update_creates_new_conversation(self, conversation_cache_with_mock):
        """Test: Update creates new conversation if none exists."""
        cache, mock_client, _, mock_blob = conversation_cache_with_mock
        
        # No existing conversation
        from azure.core.exceptions import ResourceNotFoundError
        mock_blob.download_blob.side_effect = ResourceNotFoundError("Not found")
        
        result = await cache.update_from_state(
            phone_number="+573115084628",
            user_id="user-123",
            current_flow="onboarding",
            pending_field="name",
            flow_data={},
            user_name="Juan",
        )
        
        assert result is not None
        assert result.user_id == "user-123"
        assert result.current_flow == "onboarding"
        assert result.user_name == "Juan"
        assert result.message_count == 1

    @pytest.mark.asyncio
    async def test_update_modifies_existing_conversation(
        self, conversation_cache_with_mock
    ):
        """Test: Update modifies existing conversation."""
        cache, mock_client, _, mock_blob = conversation_cache_with_mock
        
        # Existing conversation
        future = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        existing_data = {
            "user_id": "user-123",
            "phone_number": "+573115084628",
            "current_flow": "onboarding",
            "current_step": "name",
            "pending_field": "name",
            "flow_data": {},
            "message_count": 2,
            "user_name": "Juan",
            "expires_at": future,
        }
        
        mock_download = MagicMock()
        mock_download.readall.return_value = json.dumps(existing_data).encode()
        mock_blob.download_blob.return_value = mock_download
        
        result = await cache.update_from_state(
            phone_number="+573115084628",
            user_id="user-123",
            current_flow="onboarding",
            pending_field="currency",
            flow_data={"name": "Juan"},
            last_user_message="COP",
        )
        
        assert result.pending_field == "currency"
        assert result.flow_data["name"] == "Juan"
        assert result.message_count == 3  # Incremented
        assert result.last_user_message == "COP"

    @pytest.mark.asyncio
    async def test_update_preserves_user_context(self, conversation_cache_with_mock):
        """Test: Update preserves existing user context if not provided."""
        cache, mock_client, _, mock_blob = conversation_cache_with_mock
        
        # Existing conversation with user context
        future = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        existing_data = {
            "user_id": "user-123",
            "phone_number": "+573115084628",
            "current_flow": "trip_setup",
            "current_step": "name",
            "pending_field": "name",
            "flow_data": {},
            "message_count": 1,
            "user_name": "Juan",
            "home_currency": "COP",
            "timezone": "America/Bogota",
            "expires_at": future,
        }
        
        mock_download = MagicMock()
        mock_download.readall.return_value = json.dumps(existing_data).encode()
        mock_blob.download_blob.return_value = mock_download
        
        result = await cache.update_from_state(
            phone_number="+573115084628",
            user_id="user-123",
            current_flow="trip_setup",
            pending_field="destination",
            flow_data={"name": "Europa 2026"},
            # Not providing user_name, home_currency, timezone
        )
        
        # Should preserve existing values
        assert result.user_name == "Juan"
        assert result.home_currency == "COP"
        assert result.timezone == "America/Bogota"

    @pytest.mark.asyncio
    async def test_update_sets_agent_lock(self, conversation_cache_with_mock):
        """Test: Update can set agent lock."""
        cache, mock_client, _, mock_blob = conversation_cache_with_mock
        
        from azure.core.exceptions import ResourceNotFoundError
        mock_blob.download_blob.side_effect = ResourceNotFoundError("Not found")
        
        result = await cache.update_from_state(
            phone_number="+573115084628",
            user_id="user-123",
            current_flow="trip_setup",
            pending_field="name",
            flow_data={},
            active_agent="configuration",
            agent_locked=True,
            lock_reason="In multi-step flow",
        )
        
        assert result.active_agent == "configuration"
        assert result.agent_locked is True
        assert result.lock_reason == "In multi-step flow"


# ─────────────────────────────────────────────────────────────────────────────
# Test: ConversationCache._ensure_container
# ─────────────────────────────────────────────────────────────────────────────

class TestEnsureContainer:
    """Tests for container initialization."""

    def test_ensure_container_creates_if_not_exists(self):
        """Test: Container is created if it doesn't exist."""
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_container.exists.return_value = False
        mock_client.get_container_client.return_value = mock_container
        
        cache = ConversationCache()
        cache._client = mock_client
        
        cache._ensure_container()
        
        mock_container.create_container.assert_called_once()
        assert cache._initialized is True

    def test_ensure_container_skips_if_exists(self):
        """Test: Container creation is skipped if it exists."""
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_container.exists.return_value = True
        mock_client.get_container_client.return_value = mock_container
        
        cache = ConversationCache()
        cache._client = mock_client
        
        cache._ensure_container()
        
        mock_container.create_container.assert_not_called()
        assert cache._initialized is True

    def test_ensure_container_skips_if_already_initialized(self):
        """Test: Container check is skipped if already initialized."""
        mock_client = MagicMock()
        
        cache = ConversationCache()
        cache._client = mock_client
        cache._initialized = True
        
        cache._ensure_container()
        
        # Should not call get_container_client
        mock_client.get_container_client.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# Test: ConversationCache._get_client
# ─────────────────────────────────────────────────────────────────────────────

class TestGetClient:
    """Tests for Azure client initialization."""

    def test_get_client_with_account_key(self):
        """Test: Client is created with account name and key."""
        with patch("app.storage.conversation_cache.settings") as mock_settings:
            mock_settings.azure_storage_account_name = "testaccount"
            mock_settings.azure_storage_account_key = "testkey123"
            mock_settings.azure_storage_connection_string = None
            mock_settings.azure_conversation_container = "conversations"
            
            with patch(
                "app.storage.conversation_cache.BlobServiceClient"
            ) as mock_blob_class:
                mock_client = MagicMock()
                mock_blob_class.return_value = mock_client
                
                cache = ConversationCache()
                cache._client = None  # Reset
                
                result = cache._get_client()
                
                assert result is mock_client
                mock_blob_class.assert_called_once()

    def test_get_client_with_connection_string(self):
        """Test: Client is created with connection string fallback."""
        with patch("app.storage.conversation_cache.settings") as mock_settings:
            mock_settings.azure_storage_account_name = None
            mock_settings.azure_storage_account_key = None
            mock_settings.azure_storage_connection_string = "DefaultEndpointsProtocol=https;..."
            mock_settings.azure_conversation_container = "conversations"
            
            with patch(
                "app.storage.conversation_cache.BlobServiceClient"
            ) as mock_blob_class:
                mock_client = MagicMock()
                mock_blob_class.from_connection_string.return_value = mock_client
                
                cache = ConversationCache()
                cache._client = None  # Reset
                
                result = cache._get_client()
                
                assert result is mock_client
                mock_blob_class.from_connection_string.assert_called_once()

    def test_get_client_raises_if_not_configured(self):
        """Test: ValueError is raised if Azure not configured."""
        with patch("app.storage.conversation_cache.settings") as mock_settings:
            mock_settings.azure_storage_account_name = None
            mock_settings.azure_storage_account_key = None
            mock_settings.azure_storage_connection_string = None
            mock_settings.azure_conversation_container = "conversations"
            
            cache = ConversationCache()
            cache._client = None  # Reset
            
            with pytest.raises(ValueError, match="Azure Storage not configured"):
                cache._get_client()

    def test_get_client_returns_cached_client(self):
        """Test: Cached client is returned on subsequent calls."""
        mock_client = MagicMock()
        
        cache = ConversationCache()
        cache._client = mock_client
        
        result = cache._get_client()
        
        assert result is mock_client


# ─────────────────────────────────────────────────────────────────────────────
# Test: Global Cache Instance
# ─────────────────────────────────────────────────────────────────────────────

class TestGlobalCacheInstance:
    """Tests for the global conversation_cache instance."""

    def test_global_instance_exists(self):
        """Test: Global conversation_cache instance exists."""
        assert conversation_cache is not None
        assert isinstance(conversation_cache, ConversationCache)

    def test_global_instance_not_initialized(self):
        """Test: Global instance is not initialized by default."""
        # This prevents automatic Azure connections on import
        fresh_cache = ConversationCache()
        assert fresh_cache._initialized is False
        assert fresh_cache._client is None
