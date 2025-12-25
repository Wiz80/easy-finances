"""
Integration tests for the Coordinator Agent.

Tests the complete routing flow from message input through agent selection
to response output, using real database operations.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.models import Account, ConversationState, User


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def new_user(db):
    """Create a user who hasn't completed onboarding."""
    user = User(
        id=uuid.uuid4(),
        phone_number=f"+5730012345{uuid.uuid4().hex[:2]}",
        full_name="Usuario Nuevo",
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


@pytest.fixture
def onboarded_user(db):
    """Create a user who has completed onboarding."""
    user = User(
        id=uuid.uuid4(),
        phone_number=f"+5730099887{uuid.uuid4().hex[:2]}",
        full_name="Usuario Completo",
        nickname="Completo",
        home_currency="USD",
        timezone="America/Bogota",
        onboarding_status="completed",
        onboarding_completed_at=datetime.utcnow() - timedelta(days=1),
        whatsapp_verified=True,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Add an account for the user
    account = Account(
        id=uuid.uuid4(),
        user_id=user.id,
        name="Cuenta Principal",
        account_type="cash",
        currency="USD",
        is_active=True,
        is_default=True,
    )
    db.add(account)
    db.commit()
    
    return user


# ─────────────────────────────────────────────────────────────────────────────
# Test: Routing to Configuration Agent
# ─────────────────────────────────────────────────────────────────────────────

class TestRoutingToConfiguration:
    """Tests for routing to the Configuration Agent."""

    @pytest.mark.asyncio
    async def test_new_user_goes_to_configuration(self, db, new_user):
        """New users without onboarding should go to ConfigurationAgent."""
        from app.agents.coordinator import process_message
        
        result = await process_message(
            phone_number=new_user.phone_number,
            message_body="Hola!",
            profile_name="Test User",
        )
        
        assert result.success
        assert result.agent_used == "configuration"
        assert result.routing_method == "onboarding"
        assert len(result.response_text) > 0

    @pytest.mark.asyncio
    async def test_config_intent_detected(self, db, onboarded_user):
        """Configuration intents should route to ConfigurationAgent."""
        from app.agents.coordinator import process_message
        
        result = await process_message(
            phone_number=onboarded_user.phone_number,
            message_body="Quiero crear un nuevo viaje",
            profile_name="Test User",
        )
        
        assert result.success
        # Should detect config intent
        assert result.routing_method in ("keyword", "llm", "onboarding")


# ─────────────────────────────────────────────────────────────────────────────
# Test: Routing to IE Agent
# ─────────────────────────────────────────────────────────────────────────────

class TestRoutingToIEAgent:
    """Tests for routing expense messages to the IE Agent."""

    @pytest.mark.asyncio
    async def test_expense_message_detected(self, db, onboarded_user):
        """Expense messages should be detected correctly."""
        from app.agents.coordinator.router import detect_agent_for_message
        from app.agents.common.intents import AgentType
        
        result = await detect_agent_for_message(
            message="Gasté 50 soles en taxi",
            onboarding_completed=True,
            has_active_trip=True,
        )
        
        assert result.agent == AgentType.IE
        assert result.method == "keyword"

    @pytest.mark.asyncio
    async def test_multiple_expense_keywords(self, db, onboarded_user):
        """Messages with multiple expense keywords should route to IE."""
        from app.agents.coordinator.router import detect_agent_for_message
        from app.agents.common.intents import AgentType
        
        test_cases = [
            "Pagué 100 dólares por el hotel",
            "Compré comida por 25 soles",
            "Uber 15 dólares",
            "Almuerzo 30 pesos efectivo",
        ]
        
        for message in test_cases:
            result = await detect_agent_for_message(
                message=message,
                onboarding_completed=True,
                has_active_trip=True,
            )
            assert result.agent == AgentType.IE, f"Failed for: {message}"


# ─────────────────────────────────────────────────────────────────────────────
# Test: Routing to Coach Agent
# ─────────────────────────────────────────────────────────────────────────────

class TestRoutingToCoachAgent:
    """Tests for routing query messages to the Coach Agent."""

    @pytest.mark.asyncio
    async def test_query_message_detected(self, db, onboarded_user):
        """Query messages should be detected correctly."""
        from app.agents.coordinator.router import detect_agent_for_message
        from app.agents.common.intents import AgentType
        
        result = await detect_agent_for_message(
            message="¿Cuánto gasté este mes?",
            onboarding_completed=True,
            has_active_trip=True,
        )
        
        assert result.agent == AgentType.COACH
        assert result.method in ("keyword", "llm")

    @pytest.mark.asyncio
    async def test_multiple_query_patterns(self, db, onboarded_user):
        """Various query patterns should route to Coach."""
        from app.agents.coordinator.router import detect_agent_for_message
        from app.agents.common.intents import AgentType
        
        test_cases = [
            "¿Cómo voy con el presupuesto?",
            "Muéstrame el resumen de gastos",
            "¿Qué gasté ayer?",
            "Dame el total del mes",
        ]
        
        for message in test_cases:
            result = await detect_agent_for_message(
                message=message,
                onboarding_completed=True,
                has_active_trip=True,
            )
            assert result.agent == AgentType.COACH, f"Failed for: {message}"


# ─────────────────────────────────────────────────────────────────────────────
# Test: Coordinator Commands
# ─────────────────────────────────────────────────────────────────────────────

class TestCoordinatorCommands:
    """Tests for special coordinator commands."""

    @pytest.mark.asyncio
    async def test_cancel_command(self, db, onboarded_user):
        """Cancel command should be handled by Coordinator."""
        from app.agents.coordinator import process_message
        
        result = await process_message(
            phone_number=onboarded_user.phone_number,
            message_body="cancelar",
        )
        
        assert result.success
        assert result.agent_used == "coordinator"
        assert result.routing_method == "command"

    @pytest.mark.asyncio
    async def test_menu_command(self, db, onboarded_user):
        """Menu command should show menu options."""
        from app.agents.coordinator import process_message
        
        result = await process_message(
            phone_number=onboarded_user.phone_number,
            message_body="menu",
        )
        
        assert result.success
        assert result.agent_used == "coordinator"
        # Response should contain menu options
        assert "gasto" in result.response_text.lower() or "menú" in result.response_text.lower()

    @pytest.mark.asyncio
    async def test_help_command(self, db, onboarded_user):
        """Help command should show help information."""
        from app.agents.coordinator import process_message
        
        result = await process_message(
            phone_number=onboarded_user.phone_number,
            message_body="ayuda",
        )
        
        assert result.success
        assert result.agent_used == "coordinator"


# ─────────────────────────────────────────────────────────────────────────────
# Test: Sticky Sessions
# ─────────────────────────────────────────────────────────────────────────────

class TestStickySessions:
    """Tests for sticky session behavior."""

    @pytest.mark.asyncio
    async def test_session_locks_to_agent(self, db, new_user):
        """Session should lock to an agent during a flow."""
        from app.agents.coordinator import process_message
        
        # First message - should start onboarding
        result1 = await process_message(
            phone_number=new_user.phone_number,
            message_body="Hola",
            profile_name="Test",
        )
        
        assert result1.success
        assert result1.agent_used == "configuration"
        
        # Second message - should continue with configuration
        result2 = await process_message(
            phone_number=new_user.phone_number,
            message_body="Me llamo Pedro",
            profile_name="Test",
        )
        
        assert result2.success
        # Should still be in configuration
        assert result2.agent_used == "configuration"


# ─────────────────────────────────────────────────────────────────────────────
# Test: Intent Change Detection
# ─────────────────────────────────────────────────────────────────────────────

class TestIntentChangeDetection:
    """Tests for detecting intent changes during a session."""

    @pytest.mark.asyncio
    async def test_detect_clear_intent_change(self):
        """Clear intent changes should be detected."""
        from app.agents.coordinator.router import detect_intent_change
        
        # User in IE agent asks a query question
        result = await detect_intent_change(
            message="¿Cuánto gasté este mes?",
            current_agent="ie",
            last_bot_message="Gasto registrado.",
        )
        
        assert result.should_change
        assert result.new_agent == "coach"

    @pytest.mark.asyncio
    async def test_confirmation_continues_flow(self):
        """Confirmations should not trigger intent change."""
        from app.agents.coordinator.router import detect_intent_change
        
        result = await detect_intent_change(
            message="Sí, correcto",
            current_agent="configuration",
            last_bot_message="¿Es America/Bogota tu zona horaria?",
        )
        
        assert not result.should_change


# ─────────────────────────────────────────────────────────────────────────────
# Test: Full Multi-Agent Flow
# ─────────────────────────────────────────────────────────────────────────────

class TestMultiAgentFlow:
    """Tests for complete multi-agent flows."""

    @pytest.mark.asyncio
    async def test_onboarding_to_expense_flow(self, db):
        """Test flow from onboarding completion to expense registration."""
        from app.agents.coordinator import process_message
        from app.models import User
        
        # Create a user mid-onboarding (almost complete)
        phone = f"+573001111{uuid.uuid4().hex[:4]}"
        user = User(
            id=uuid.uuid4(),
            phone_number=phone,
            full_name="Test User",
            nickname="Test",
            home_currency="USD",
            timezone="America/Bogota",
            onboarding_status="completed",  # Already completed
            onboarding_completed_at=datetime.utcnow(),
            whatsapp_verified=True,
            is_active=True,
        )
        db.add(user)
        
        # Add account
        account = Account(
            id=uuid.uuid4(),
            user_id=user.id,
            name="Main",
            account_type="cash",
            currency="USD",
            is_active=True,
        )
        db.add(account)
        db.commit()
        
        # Now send an expense message
        result = await process_message(
            phone_number=phone,
            message_body="Gasté 50 soles en taxi",
        )
        
        assert result.success
        # Should be routed to IE agent since onboarding is complete
        assert result.agent_used == "ie" or result.routing_method == "keyword"


# ─────────────────────────────────────────────────────────────────────────────
# Test: Error Handling
# ─────────────────────────────────────────────────────────────────────────────

class TestErrorHandling:
    """Tests for error handling in the Coordinator."""

    @pytest.mark.asyncio
    async def test_empty_message_handled(self, db, onboarded_user):
        """Empty messages should be handled gracefully."""
        from app.agents.coordinator import process_message
        
        result = await process_message(
            phone_number=onboarded_user.phone_number,
            message_body="",
        )
        
        # Should not crash - either success or handled error
        assert result.response_text is not None
        assert len(result.response_text) > 0

    @pytest.mark.asyncio
    async def test_unknown_phone_creates_user(self, db):
        """Unknown phone numbers should create new users."""
        from app.agents.coordinator import process_message
        
        # Use a unique phone that doesn't exist
        phone = f"+5730055555{uuid.uuid4().hex[:2]}"
        
        result = await process_message(
            phone_number=phone,
            message_body="Hola",
            profile_name="Nuevo Usuario",
        )
        
        assert result.success
        assert result.user_id is not None
        # New user should go to configuration for onboarding
        assert result.agent_used == "configuration"

