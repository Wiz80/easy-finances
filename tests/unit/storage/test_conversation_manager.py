"""Unit tests for conversation_manager storage module."""

import uuid
from datetime import datetime, timedelta

import pytest

from app.models import ConversationState
from app.storage.conversation_manager import (
    cancel_conversation,
    cleanup_expired_conversations,
    clear_pending_confirmation,
    complete_conversation,
    create_conversation,
    expire_conversation,
    get_active_conversation,
    get_conversation_by_id,
    get_conversation_summary,
    get_user_conversations,
    set_pending_confirmation,
    update_conversation,
    update_conversation_state_data,
)


class TestCreateConversation:
    """Tests for create_conversation function."""

    def test_creates_conversation(self, db, sample_user):
        """Should create a new conversation."""
        result = create_conversation(
            db=db,
            user_id=sample_user.id,
            flow="onboarding",
            step="name",
            state_data={"test": "data"},
        )
        
        assert result.success is True
        assert result.conversation_id is not None
        assert result.conversation.current_flow == "onboarding"
        assert result.conversation.current_step == "name"
        assert result.conversation.status == "active"

    def test_expires_existing_conversations(self, db, sample_user, sample_conversation):
        """Should expire existing active conversations."""
        old_id = sample_conversation.id
        
        result = create_conversation(
            db=db,
            user_id=sample_user.id,
            flow="budget_config",
            step="total_amount",
        )
        
        assert result.success is True
        
        # Old conversation should be expired
        old_conv = get_conversation_by_id(db, old_id)
        assert old_conv.status == "expired"


class TestGetActiveConversation:
    """Tests for get_active_conversation function."""

    def test_returns_active_conversation(self, db, sample_user, sample_conversation):
        """Should return active conversation."""
        conv = get_active_conversation(db, sample_user.id)
        
        assert conv is not None
        assert conv.id == sample_conversation.id
        assert conv.status == "active"

    def test_returns_none_when_no_active(self, db, sample_user):
        """Should return None when no active conversation."""
        # Expire any existing
        db.query(ConversationState).filter(
            ConversationState.user_id == sample_user.id
        ).update({"status": "completed"})
        db.commit()
        
        conv = get_active_conversation(db, sample_user.id)
        
        assert conv is None

    def test_expires_and_returns_none_when_expired(self, db, sample_user, sample_conversation):
        """Should expire and return None for expired conversations."""
        # Make conversation expired
        sample_conversation.expires_at = datetime.utcnow() - timedelta(minutes=1)
        db.commit()
        
        conv = get_active_conversation(db, sample_user.id)
        
        assert conv is None
        
        # Check it was marked as expired
        db.refresh(sample_conversation)
        assert sample_conversation.status == "expired"


class TestUpdateConversation:
    """Tests for update_conversation function."""

    def test_updates_flow_and_step(self, db, sample_conversation):
        """Should update flow and step."""
        result = update_conversation(
            db=db,
            conversation_id=sample_conversation.id,
            flow="budget_config",
            step="category_food",
        )
        
        assert result.success is True
        assert result.conversation.current_flow == "budget_config"
        assert result.conversation.current_step == "category_food"

    def test_merges_state_data(self, db, sample_conversation):
        """Should merge state data with existing."""
        original_data = dict(sample_conversation.state_data)
        
        result = update_conversation(
            db=db,
            conversation_id=sample_conversation.id,
            state_data={"new_key": "new_value"},
        )
        
        assert result.success is True
        # Original data preserved
        for key in original_data:
            assert key in result.conversation.state_data
        # New data added
        assert result.conversation.state_data["new_key"] == "new_value"

    def test_adds_messages_to_history(self, db, sample_conversation):
        """Should add messages to history."""
        initial_count = sample_conversation.message_count
        
        result = update_conversation(
            db=db,
            conversation_id=sample_conversation.id,
            user_message="Test user message",
            bot_message="Test bot response",
        )
        
        assert result.success is True
        assert result.conversation.message_count == initial_count + 2
        assert result.conversation.last_user_message == "Test user message"
        assert result.conversation.last_bot_message == "Test bot response"


class TestUpdateConversationStateData:
    """Tests for update_conversation_state_data function."""

    def test_updates_specific_fields(self, db, sample_conversation):
        """Should update specific state data fields."""
        result = update_conversation_state_data(
            db=db,
            conversation_id=sample_conversation.id,
            trip_name="Ecuador",
            start_date="2024-12-15",
        )
        
        assert result.success is True
        assert result.conversation.state_data["trip_name"] == "Ecuador"
        assert result.conversation.state_data["start_date"] == "2024-12-15"


class TestSetPendingConfirmation:
    """Tests for set_pending_confirmation function."""

    def test_sets_pending_data(self, db, sample_conversation):
        """Should set pending confirmation data."""
        result = set_pending_confirmation(
            db=db,
            conversation_id=sample_conversation.id,
            confirmation="Confirmar viaje?",
            entity_type="trip",
            entity_data={"name": "Ecuador", "country": "EC"},
        )
        
        assert result.success is True
        assert result.conversation.pending_confirmation == "Confirmar viaje?"
        assert result.conversation.pending_entity_type == "trip"
        assert result.conversation.pending_entity_data["name"] == "Ecuador"


class TestClearPendingConfirmation:
    """Tests for clear_pending_confirmation function."""

    def test_clears_pending_data(self, db, sample_conversation):
        """Should clear pending confirmation data."""
        # First set some pending data
        sample_conversation.pending_confirmation = "Test"
        sample_conversation.pending_entity_type = "trip"
        sample_conversation.pending_entity_data = {"test": "data"}
        db.commit()
        
        result = clear_pending_confirmation(db, sample_conversation.id)
        
        assert result.success is True
        assert result.conversation.pending_confirmation is None
        assert result.conversation.pending_entity_type is None
        assert result.conversation.pending_entity_data is None


class TestCompleteConversation:
    """Tests for complete_conversation function."""

    def test_completes_conversation(self, db, sample_conversation):
        """Should mark conversation as completed."""
        result = complete_conversation(db, sample_conversation.id)
        
        assert result.success is True
        assert result.conversation.status == "completed"


class TestCancelConversation:
    """Tests for cancel_conversation function."""

    def test_cancels_conversation(self, db, sample_conversation):
        """Should mark conversation as cancelled."""
        result = cancel_conversation(db, sample_conversation.id)
        
        assert result.success is True
        assert result.conversation.status == "cancelled"


class TestExpireConversation:
    """Tests for expire_conversation function."""

    def test_expires_conversation(self, db, sample_conversation):
        """Should mark conversation as expired."""
        result = expire_conversation(db, sample_conversation.id)
        
        assert result.success is True
        assert result.conversation.status == "expired"


class TestCleanupExpiredConversations:
    """Tests for cleanup_expired_conversations function."""

    def test_expires_old_conversations(self, db, sample_user):
        """Should expire conversations past their expiration time."""
        # Create an expired conversation
        expired_conv = ConversationState(
            user_id=sample_user.id,
            current_flow="test",
            current_step="test",
            state_data={},
            session_started_at=datetime.utcnow() - timedelta(hours=2),
            last_interaction_at=datetime.utcnow() - timedelta(hours=1),
            expires_at=datetime.utcnow() - timedelta(minutes=30),  # Expired
            status="active",
            message_count=0,
        )
        db.add(expired_conv)
        db.commit()
        
        count = cleanup_expired_conversations(db)
        
        assert count >= 1
        
        db.refresh(expired_conv)
        assert expired_conv.status == "expired"


class TestGetConversationSummary:
    """Tests for get_conversation_summary function."""

    def test_returns_summary(self, db, sample_conversation):
        """Should return conversation summary dict."""
        summary = get_conversation_summary(db, sample_conversation.id)
        
        assert summary is not None
        assert summary["id"] == str(sample_conversation.id)
        assert summary["flow"] == sample_conversation.current_flow
        assert summary["step"] == sample_conversation.current_step
        assert summary["status"] == "active"
        assert "is_active" in summary
        assert "is_expired" in summary

    def test_returns_none_for_invalid_id(self, db):
        """Should return None for invalid conversation ID."""
        summary = get_conversation_summary(db, uuid.uuid4())
        
        assert summary is None

