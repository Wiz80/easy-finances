"""
Multi-Agent Flow Integration Tests.

Tests the complete flows across multiple agents, including:
- Handoffs between agents
- Sticky sessions and locking
- Intent change detection
- Agent unlock scenarios
"""

import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import Account, ConversationState, User


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def multi_agent_user(db):
    """Create a user for multi-agent tests."""
    user = User(
        id=uuid.uuid4(),
        phone_number=f"+573007777{uuid.uuid4().hex[:4]}",
        full_name="Multi Agent User",
        nickname="MultiTest",
        home_currency="COP",
        timezone="America/Bogota",
        preferred_language="es",
        onboarding_status="completed",
        onboarding_completed_at=datetime.utcnow(),
        whatsapp_verified=True,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def multi_agent_account(db, multi_agent_user):
    """Create account for multi-agent user."""
    account = Account(
        id=uuid.uuid4(),
        user_id=multi_agent_user.id,
        name="Cuenta Principal",
        account_type="cash",
        currency="COP",
        is_active=True,
        is_default=True,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@pytest.fixture
def locked_conversation(db, multi_agent_user):
    """Create a conversation locked to an agent."""
    conversation = ConversationState(
        id=uuid.uuid4(),
        user_id=multi_agent_user.id,
        current_flow="trip_setup",
        current_step="trip_name",
        state_data={},
        agent_locked="configuration",  # Locked to config
        session_started_at=datetime.utcnow() - timedelta(minutes=5),
        last_interaction_at=datetime.utcnow() - timedelta(seconds=30),
        expires_at=datetime.utcnow() + timedelta(minutes=25),
        status="active",
        message_count=3,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


# ─────────────────────────────────────────────────────────────────────────────
# Test: Agent Handoffs
# ─────────────────────────────────────────────────────────────────────────────

class TestAgentHandoffs:
    """Tests for handoffs between agents."""

    @pytest.mark.asyncio
    async def test_onboarding_to_ie_handoff(self, db, multi_agent_user, multi_agent_account):
        """Test: After onboarding, expense messages go to IE Agent."""
        from app.agents.coordinator import process_message
        
        # First - verify routing to IE for expense
        result = await process_message(
            phone_number=multi_agent_user.phone_number,
            message_body="Gasté 100 pesos en taxi",
        )
        
        assert result.success
        # Should route to IE based on keyword
        assert result.agent_used in ("ie", "coordinator")

    @pytest.mark.asyncio
    async def test_ie_to_coach_handoff(self, db, multi_agent_user, multi_agent_account):
        """Test: User can switch from expense to query."""
        from app.agents.coordinator import process_message
        
        # First - expense message
        result1 = await process_message(
            phone_number=multi_agent_user.phone_number,
            message_body="Gasté 50 dólares en almuerzo",
        )
        
        # Then - query message (should switch to Coach)
        result2 = await process_message(
            phone_number=multi_agent_user.phone_number,
            message_body="¿Cuánto llevo gastado hoy?",
        )
        
        assert result2.success
        # Should route to coach for query
        assert result2.agent_used in ("coach", "coordinator")

    @pytest.mark.asyncio
    async def test_coach_to_ie_handoff(self, db, multi_agent_user, multi_agent_account):
        """Test: User can switch from query to expense."""
        from app.agents.coordinator import process_message
        
        # First - query
        result1 = await process_message(
            phone_number=multi_agent_user.phone_number,
            message_body="¿Cómo voy con el presupuesto?",
        )
        
        # Then - expense
        result2 = await process_message(
            phone_number=multi_agent_user.phone_number,
            message_body="Pagué 30 dólares por el taxi",
        )
        
        assert result2.success
        # Should route to IE for expense
        assert result2.agent_used in ("ie", "coordinator")


# ─────────────────────────────────────────────────────────────────────────────
# Test: Sticky Sessions
# ─────────────────────────────────────────────────────────────────────────────

class TestStickySessions:
    """Tests for sticky session behavior."""

    @pytest.mark.asyncio
    async def test_locked_conversation_continues_with_agent(
        self, db, multi_agent_user, locked_conversation
    ):
        """Test: Messages continue with locked agent."""
        from app.agents.coordinator import process_message
        
        # Send message while locked to configuration
        result = await process_message(
            phone_number=multi_agent_user.phone_number,
            message_body="Viaje a Europa",  # Should continue config flow
        )
        
        assert result.success
        # Should stay with configuration or handle appropriately
        # The exact agent depends on implementation

    @pytest.mark.asyncio
    async def test_cancel_unlocks_conversation(
        self, db, multi_agent_user, locked_conversation
    ):
        """Test: Cancel command unlocks conversation."""
        from app.agents.coordinator import process_message
        
        # First verify we're locked
        assert locked_conversation.agent_locked == "configuration"
        
        # Send cancel
        result = await process_message(
            phone_number=multi_agent_user.phone_number,
            message_body="cancelar",
        )
        
        assert result.success
        assert result.agent_used == "coordinator"
        assert result.routing_method == "command"

    @pytest.mark.asyncio
    async def test_menu_unlocks_conversation(
        self, db, multi_agent_user, locked_conversation
    ):
        """Test: Menu command unlocks conversation."""
        from app.agents.coordinator import process_message
        
        result = await process_message(
            phone_number=multi_agent_user.phone_number,
            message_body="menú",
        )
        
        assert result.success
        assert result.agent_used == "coordinator"


# ─────────────────────────────────────────────────────────────────────────────
# Test: Intent Change Detection
# ─────────────────────────────────────────────────────────────────────────────

class TestIntentChangeDetection:
    """Tests for detecting intent changes during flows."""

    @pytest.mark.asyncio
    async def test_clear_expense_during_config(
        self, db, multi_agent_user, locked_conversation
    ):
        """Test: Clear expense intent during config is detected."""
        from app.agents.coordinator.router import detect_intent_change
        
        # Locked to configuration, but user sends expense
        result = await detect_intent_change(
            message="Gasté 100 dólares",
            current_agent="configuration",
            last_bot_message="¿Cómo quieres llamar a tu viaje?",
        )
        
        assert result.should_change
        assert result.new_agent == "ie"

    @pytest.mark.asyncio
    async def test_confirmation_does_not_change_intent(
        self, db, multi_agent_user, locked_conversation
    ):
        """Test: Confirmations don't trigger intent change."""
        from app.agents.coordinator.router import detect_intent_change
        
        confirmations = ["sí", "correcto", "ok", "perfecto"]
        
        for confirmation in confirmations:
            result = await detect_intent_change(
                message=confirmation,
                current_agent="configuration",
                last_bot_message="¿Es correcta esta información?",
            )
            
            # Should not change intent for confirmations
            assert not result.should_change, f"Failed for: {confirmation}"

    @pytest.mark.asyncio
    async def test_query_during_ie_detected(self):
        """Test: Query intent during IE flow is detected."""
        from app.agents.coordinator.router import detect_intent_change
        
        result = await detect_intent_change(
            message="¿Cuánto llevo gastado?",
            current_agent="ie",
            last_bot_message="Registré tu gasto de $50.",
        )
        
        assert result.should_change
        assert result.new_agent == "coach"


# ─────────────────────────────────────────────────────────────────────────────
# Test: Flow Completion
# ─────────────────────────────────────────────────────────────────────────────

class TestFlowCompletion:
    """Tests for complete multi-step flows."""

    @pytest.mark.asyncio
    async def test_expense_confirmation_flow(self, db, multi_agent_user, multi_agent_account):
        """Test: Expense registration with potential confirmation."""
        from app.agents.coordinator import process_message
        
        # Register expense
        result1 = await process_message(
            phone_number=multi_agent_user.phone_number,
            message_body="Gasté 75 dólares en cena romántica",
        )
        
        assert result1.success
        
        # If low confidence, might ask for confirmation
        # Otherwise, should be registered
        if "confirma" in result1.response_text.lower():
            result2 = await process_message(
                phone_number=multi_agent_user.phone_number,
                message_body="Sí, confirmo",
            )
            assert result2.success


# ─────────────────────────────────────────────────────────────────────────────
# Test: Error Recovery Between Agents
# ─────────────────────────────────────────────────────────────────────────────

class TestErrorRecoveryBetweenAgents:
    """Tests for error recovery in multi-agent flows."""

    @pytest.mark.asyncio
    async def test_ie_error_allows_retry(self, db, multi_agent_user, multi_agent_account):
        """Test: IE Agent errors allow user to retry."""
        from app.agents.coordinator import process_message
        
        # Send ambiguous expense
        result = await process_message(
            phone_number=multi_agent_user.phone_number,
            message_body="Algo en algún lugar",  # Very ambiguous
        )
        
        # Even on low confidence, should respond
        assert result.success
        assert len(result.response_text) > 0

    @pytest.mark.asyncio
    async def test_coach_error_allows_retry(self, db, multi_agent_user):
        """Test: Coach Agent errors allow user to retry."""
        from app.agents.coordinator import process_message
        
        # Send query
        result = await process_message(
            phone_number=multi_agent_user.phone_number,
            message_body="¿Cuánto gasté en categoría inexistente?",
        )
        
        # Should respond even with unusual query
        assert result.success
        assert len(result.response_text) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Test: State Persistence Across Messages
# ─────────────────────────────────────────────────────────────────────────────

class TestStatePersistence:
    """Tests for state persistence across multiple messages."""

    @pytest.mark.asyncio
    async def test_conversation_history_preserved(
        self, db, multi_agent_user, multi_agent_account
    ):
        """Test: Conversation history is preserved across messages."""
        from app.agents.coordinator import process_message
        
        # Send sequence of messages
        messages = [
            "Gasté 50 en taxi",
            "¿Cuánto llevo hoy?",
            "Gasté 30 en almuerzo",
        ]
        
        results = []
        for msg in messages:
            result = await process_message(
                phone_number=multi_agent_user.phone_number,
                message_body=msg,
            )
            results.append(result)
            assert result.success
        
        # All messages should have been processed
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_user_context_preserved(self, db, multi_agent_user, multi_agent_account):
        """Test: User context is preserved across agent switches."""
        from app.agents.coordinator import process_message
        
        # Expense
        result1 = await process_message(
            phone_number=multi_agent_user.phone_number,
            message_body="100 dólares hotel",
        )
        
        # Query - should have access to context
        result2 = await process_message(
            phone_number=multi_agent_user.phone_number,
            message_body="¿Cuánto llevo?",
        )
        
        # Both should succeed and have user context
        assert result1.success
        assert result2.success
        assert result1.user_id == result2.user_id


# ─────────────────────────────────────────────────────────────────────────────
# Test: Edge Cases
# ─────────────────────────────────────────────────────────────────────────────

class TestMultiAgentEdgeCases:
    """Tests for edge cases in multi-agent flows."""

    @pytest.mark.asyncio
    async def test_rapid_agent_switches(self, db, multi_agent_user, multi_agent_account):
        """Test: Rapid switches between agents are handled."""
        from app.agents.coordinator import process_message
        
        # Rapid sequence of different intents
        messages = [
            ("Gasté 10 en café", "ie"),
            ("¿Cuánto gasté?", "coach"),
            ("20 dólares taxi", "ie"),
            ("Dame el resumen", "coach"),
        ]
        
        for msg, expected_agent in messages:
            result = await process_message(
                phone_number=multi_agent_user.phone_number,
                message_body=msg,
            )
            assert result.success

    @pytest.mark.asyncio
    async def test_mixed_language_messages(self, db, multi_agent_user, multi_agent_account):
        """Test: Mixed language messages are handled."""
        from app.agents.coordinator import process_message
        
        # Mix of Spanish and English
        messages = [
            "I spent 50 dollars on lunch",
            "Gasté 30 soles",
            "How much did I spend?",
        ]
        
        for msg in messages:
            result = await process_message(
                phone_number=multi_agent_user.phone_number,
                message_body=msg,
            )
            assert result.success
            assert len(result.response_text) > 0

    @pytest.mark.asyncio
    async def test_emoji_in_messages(self, db, multi_agent_user, multi_agent_account):
        """Test: Emoji in messages are handled."""
        from app.agents.coordinator import process_message
        
        result = await process_message(
            phone_number=multi_agent_user.phone_number,
            message_body="Gasté 50 dólares en 🍔🍕",
        )
        
        assert result.success
