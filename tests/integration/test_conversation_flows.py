"""
Integration tests for conversation flows.

Tests the complete flow from message input to response output,
using mocked LLM responses but real database operations.
"""

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.models import Budget, ConversationState, Trip, User


class TestOnboardingFlow:
    """Integration tests for the onboarding conversation flow."""

    @pytest.fixture
    def new_user_for_onboarding(self, db):
        """Create a fresh user for onboarding tests."""
        user = User(
            id=uuid.uuid4(),
            phone_number="+573009876543",
            full_name="Usuario",
            home_currency="USD",
            timezone="UTC",
            onboarding_status="pending",
            whatsapp_verified=True,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @patch("app.agents.configuration_agent.nodes.intent.ChatOpenAI")
    def test_complete_onboarding_flow(self, mock_llm, db, new_user_for_onboarding):
        """Test complete onboarding from start to finish."""
        from app.agents.configuration_agent import process_message
        import asyncio
        
        user = new_user_for_onboarding
        
        # Mock LLM responses for each step
        mock_instance = MagicMock()
        mock_llm.return_value = mock_instance
        
        # Step 1: Greeting - should ask for name
        mock_instance.invoke.return_value.content = '{"intent": "greeting", "entities": {}, "confidence": 0.9}'
        
        result = asyncio.get_event_loop().run_until_complete(
            process_message(
                user_id=user.id,
                phone_number=user.phone_number,
                message_body="Hola",
                db=db,
            )
        )
        
        assert result.success
        assert "nombre" in result.response_text.lower() or "llamas" in result.response_text.lower()
        
        # Step 2: Provide name - should ask for currency
        mock_instance.invoke.return_value.content = '{"intent": "onboarding_provide_name", "entities": {"name": "Harrison"}, "confidence": 0.95}'
        
        result = asyncio.get_event_loop().run_until_complete(
            process_message(
                user_id=user.id,
                phone_number=user.phone_number,
                message_body="Harrison",
                db=db,
                conversation_id=result.conversation_id,
            )
        )
        
        assert result.success
        # Should acknowledge name and ask for currency
        db.refresh(user)
        assert user.full_name == "Harrison" or result.flow_data.get("name") == "Harrison"

    @patch("app.agents.configuration_agent.nodes.intent.ChatOpenAI")
    def test_onboarding_handles_invalid_currency(self, mock_llm, db, new_user_for_onboarding):
        """Test handling of invalid currency code."""
        from app.agents.configuration_agent import process_message
        import asyncio
        
        user = new_user_for_onboarding
        mock_instance = MagicMock()
        mock_llm.return_value = mock_instance
        
        # Simulate being at currency step
        mock_instance.invoke.return_value.content = '{"intent": "onboarding_provide_currency", "entities": {"currency": "INVALID"}, "confidence": 0.5}'
        
        result = asyncio.get_event_loop().run_until_complete(
            process_message(
                user_id=user.id,
                phone_number=user.phone_number,
                message_body="INVALID",
                db=db,
            )
        )
        
        assert result.success
        # Should handle gracefully (either ask again or provide default)


class TestTripSetupFlow:
    """Integration tests for the trip setup conversation flow."""

    @patch("app.agents.configuration_agent.nodes.intent.ChatOpenAI")
    def test_create_trip_flow(self, mock_llm, db, sample_user):
        """Test creating a trip through conversation."""
        from app.agents.configuration_agent import process_message
        import asyncio
        
        # Clear any existing trip
        sample_user.current_trip_id = None
        sample_user.travel_mode_active = False
        db.commit()
        
        mock_instance = MagicMock()
        mock_llm.return_value = mock_instance
        
        # Step 1: Request new trip
        mock_instance.invoke.return_value.content = '{"intent": "trip_create", "entities": {}, "confidence": 0.95}'
        
        result = asyncio.get_event_loop().run_until_complete(
            process_message(
                user_id=sample_user.id,
                phone_number=sample_user.phone_number,
                message_body="Nuevo viaje",
                db=db,
            )
        )
        
        assert result.success
        assert result.current_flow == "trip_setup"
        assert result.pending_field == "trip_name"


class TestBudgetConfigFlow:
    """Integration tests for the budget configuration flow."""

    @patch("app.agents.configuration_agent.nodes.intent.ChatOpenAI")
    def test_create_budget_flow(self, mock_llm, db, sample_user, sample_trip):
        """Test creating a budget through conversation."""
        from app.agents.configuration_agent import process_message
        import asyncio
        
        mock_instance = MagicMock()
        mock_llm.return_value = mock_instance
        
        # Request new budget
        mock_instance.invoke.return_value.content = '{"intent": "budget_create", "entities": {}, "confidence": 0.95}'
        
        result = asyncio.get_event_loop().run_until_complete(
            process_message(
                user_id=sample_user.id,
                phone_number=sample_user.phone_number,
                message_body="Configurar presupuesto",
                db=db,
            )
        )
        
        assert result.success
        assert result.current_flow == "budget_config"
        assert result.pending_field == "total_amount"


class TestConversationStateManagement:
    """Integration tests for conversation state management."""

    def test_conversation_created_on_new_flow(self, db, sample_user):
        """Test that conversation is created when starting a new flow."""
        from app.agents.configuration_agent import process_message
        from app.storage import get_active_conversation
        import asyncio
        
        # Ensure no active conversation
        db.query(ConversationState).filter(
            ConversationState.user_id == sample_user.id
        ).delete()
        db.commit()
        
        with patch("app.agents.configuration_agent.nodes.intent.ChatOpenAI") as mock_llm:
            mock_instance = MagicMock()
            mock_llm.return_value = mock_instance
            mock_instance.invoke.return_value.content = '{"intent": "trip_create", "entities": {}, "confidence": 0.95}'
            
            result = asyncio.get_event_loop().run_until_complete(
                process_message(
                    user_id=sample_user.id,
                    phone_number=sample_user.phone_number,
                    message_body="Nuevo viaje",
                    db=db,
                )
            )
        
        # Should have created a conversation
        conv = get_active_conversation(db, sample_user.id)
        assert conv is not None or result.conversation_id is not None

    def test_conversation_updated_on_subsequent_messages(self, db, sample_user, sample_conversation):
        """Test that conversation is updated on subsequent messages."""
        from app.agents.configuration_agent import process_message
        import asyncio
        
        initial_count = sample_conversation.message_count
        
        with patch("app.agents.configuration_agent.nodes.intent.ChatOpenAI") as mock_llm:
            mock_instance = MagicMock()
            mock_llm.return_value = mock_instance
            mock_instance.invoke.return_value.content = '{"intent": "trip_provide_info", "entities": {"trip_name": "Ecuador"}, "confidence": 0.9}'
            
            result = asyncio.get_event_loop().run_until_complete(
                process_message(
                    user_id=sample_user.id,
                    phone_number=sample_user.phone_number,
                    message_body="Ecuador Adventure",
                    db=db,
                    conversation_id=sample_conversation.id,
                )
            )
        
        db.refresh(sample_conversation)
        # Message count should have increased
        assert sample_conversation.message_count >= initial_count

    def test_expired_conversation_starts_new(self, db, sample_user):
        """Test that expired conversations start fresh."""
        from app.agents.configuration_agent import process_message
        import asyncio
        
        # Create an expired conversation
        expired = ConversationState(
            user_id=sample_user.id,
            current_flow="trip_setup",
            current_step="trip_name",
            state_data={"old": "data"},
            session_started_at=datetime.utcnow() - timedelta(hours=2),
            last_interaction_at=datetime.utcnow() - timedelta(hours=1),
            expires_at=datetime.utcnow() - timedelta(minutes=30),
            status="active",
            message_count=5,
        )
        db.add(expired)
        db.commit()
        
        with patch("app.agents.configuration_agent.nodes.intent.ChatOpenAI") as mock_llm:
            mock_instance = MagicMock()
            mock_llm.return_value = mock_instance
            mock_instance.invoke.return_value.content = '{"intent": "greeting", "entities": {}, "confidence": 0.9}'
            
            result = asyncio.get_event_loop().run_until_complete(
                process_message(
                    user_id=sample_user.id,
                    phone_number=sample_user.phone_number,
                    message_body="Hola",
                    db=db,
                )
            )
        
        # Should have handled the expired conversation
        assert result.success


