"""
Unit tests for Coordinator escape mechanism.

Tests:
- "Cancelar" command releases agent lock
- Menu/Help commands release agent lock
- Restart command resets conversation
- Command detection during locked session
- Intent change detection while locked
- Escape always possible (no deadlocks)
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.agents.common.intents import (
    AgentType,
    is_coordinator_command,
    detect_intent_fast,
    COORDINATOR_COMMANDS,
)
from app.agents.coordinator.graph import (
    should_detect_intent,
    check_agent_lock_node,
    _check_intent_change,
)
from app.agents.coordinator.handlers.commands import (
    handle_coordinator_command,
    _handle_cancel,
    _handle_menu,
    _handle_help,
    _handle_restart,
)
from app.agents.common.response import AgentResponse, AgentStatus


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def base_state():
    """Create a base state for testing."""
    return {
        "request_id": "test-123",
        "user_id": uuid4(),
        "phone_number": "+573115084628",
        "message_body": "",
        "onboarding_completed": True,
    }


@pytest.fixture
def locked_state(base_state):
    """Create a state with agent lock."""
    return {
        **base_state,
        "agent_locked": True,
        "active_agent": "ie",
        "lock_reason": "awaiting_input",
    }


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return MagicMock()


# ─────────────────────────────────────────────────────────────────────────────
# Command Detection Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestCommandDetection:
    """Tests for coordinator command detection."""

    @pytest.mark.parametrize(
        "message,expected_action",
        [
            ("cancelar", "cancel_current_flow"),
            ("Cancelar", "cancel_current_flow"),
            ("CANCELAR", "cancel_current_flow"),
            ("cancel", "cancel_current_flow"),
            ("salir", "cancel_current_flow"),
            ("exit", "cancel_current_flow"),
        ],
    )
    def test_cancel_commands_detected(self, message, expected_action):
        """Should detect cancel commands in any case."""
        is_cmd, action = is_coordinator_command(message)
        assert is_cmd is True
        assert action == expected_action

    @pytest.mark.parametrize(
        "message,expected_action",
        [
            ("menu", "show_menu"),
            ("menú", "show_menu"),
            ("Menu", "show_menu"),
        ],
    )
    def test_menu_commands_detected(self, message, expected_action):
        """Should detect menu commands."""
        is_cmd, action = is_coordinator_command(message)
        assert is_cmd is True
        assert action == expected_action

    @pytest.mark.parametrize(
        "message,expected_action",
        [
            ("ayuda", "show_help"),
            ("Ayuda", "show_help"),
            ("help", "show_help"),
        ],
    )
    def test_help_commands_detected(self, message, expected_action):
        """Should detect help commands."""
        is_cmd, action = is_coordinator_command(message)
        assert is_cmd is True
        assert action == expected_action

    @pytest.mark.parametrize(
        "message,expected_action",
        [
            ("reiniciar", "restart_conversation"),
            ("reset", "restart_conversation"),
            ("/reset", "admin_reset"),
        ],
    )
    def test_reset_commands_detected(self, message, expected_action):
        """Should detect reset commands."""
        is_cmd, action = is_coordinator_command(message)
        assert is_cmd is True
        assert action == expected_action

    def test_non_command_not_detected(self):
        """Should not detect regular messages as commands."""
        messages = [
            "gasté 50 soles",
            "cuánto gasté hoy?",
            "hola",
            "50000 pesos almuerzo",
            "quiero ver mi presupuesto",
        ]
        
        for message in messages:
            is_cmd, action = is_coordinator_command(message)
            assert is_cmd is False
            assert action is None

    def test_command_in_sentence_not_detected(self):
        """Should only detect exact command matches, not within sentences."""
        messages = [
            "no quiero cancelar",
            "dame el menu del día",
            "necesito ayuda con mi gasto",
        ]
        
        for message in messages:
            is_cmd, action = is_coordinator_command(message)
            assert is_cmd is False


# ─────────────────────────────────────────────────────────────────────────────
# Cancel Command Handler Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestCancelCommandHandler:
    """Tests for cancel command handler."""

    @pytest.mark.asyncio
    async def test_cancel_releases_lock(self, mock_db):
        """Cancel command should release agent lock."""
        response = await _handle_cancel(
            user_id=uuid4(),
            conversation_id=uuid4(),
            db=mock_db,
            request_id="test-123",
        )
        
        assert response.release_lock is True
        assert response.continue_flow is False

    @pytest.mark.asyncio
    async def test_cancel_returns_confirmation(self, mock_db):
        """Cancel command should return confirmation message."""
        response = await _handle_cancel(
            user_id=uuid4(),
            conversation_id=uuid4(),
            db=mock_db,
            request_id="test-123",
        )
        
        assert response.response_text is not None
        assert response.status == AgentStatus.COMPLETED

    @pytest.mark.asyncio
    @patch("app.storage.conversation_manager.cancel_conversation")
    async def test_cancel_calls_cancel_conversation(self, mock_cancel, mock_db):
        """Cancel command should call cancel_conversation."""
        conversation_id = uuid4()
        
        await _handle_cancel(
            user_id=uuid4(),
            conversation_id=conversation_id,
            db=mock_db,
            request_id="test-123",
        )
        
        mock_cancel.assert_called_once_with(mock_db, conversation_id)

    @pytest.mark.asyncio
    async def test_cancel_clears_handoff_context(self, mock_db):
        """Cancel command should clear handoff context."""
        response = await _handle_cancel(
            user_id=uuid4(),
            conversation_id=uuid4(),
            db=mock_db,
            request_id="test-123",
        )
        
        assert response.handoff_context is None


# ─────────────────────────────────────────────────────────────────────────────
# Menu Command Handler Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestMenuCommandHandler:
    """Tests for menu command handler."""

    @pytest.mark.asyncio
    async def test_menu_releases_lock(self):
        """Menu command should release agent lock."""
        response = await _handle_menu(request_id="test-123")
        
        assert response.release_lock is True
        assert response.continue_flow is False

    @pytest.mark.asyncio
    async def test_menu_returns_menu_text(self):
        """Menu command should return menu options."""
        response = await _handle_menu(request_id="test-123")
        
        assert response.response_text is not None
        assert len(response.response_text) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Help Command Handler Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestHelpCommandHandler:
    """Tests for help command handler."""

    @pytest.mark.asyncio
    async def test_help_releases_lock(self):
        """Help command should release agent lock."""
        response = await _handle_help(request_id="test-123")
        
        assert response.release_lock is True

    @pytest.mark.asyncio
    async def test_help_returns_help_text(self):
        """Help command should return help information."""
        response = await _handle_help(request_id="test-123")
        
        assert response.response_text is not None
        assert len(response.response_text) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Restart Command Handler Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestRestartCommandHandler:
    """Tests for restart command handler."""

    @pytest.mark.asyncio
    async def test_restart_releases_lock(self, mock_db):
        """Restart command should release agent lock."""
        response = await _handle_restart(
            user_id=uuid4(),
            conversation_id=uuid4(),
            db=mock_db,
            request_id="test-123",
        )
        
        assert response.release_lock is True

    @pytest.mark.asyncio
    @patch("app.storage.conversation_manager.cancel_conversation")
    async def test_restart_cancels_conversation(self, mock_cancel, mock_db):
        """Restart command should cancel active conversation."""
        conversation_id = uuid4()
        
        await _handle_restart(
            user_id=uuid4(),
            conversation_id=conversation_id,
            db=mock_db,
            request_id="test-123",
        )
        
        mock_cancel.assert_called_once_with(mock_db, conversation_id)


# ─────────────────────────────────────────────────────────────────────────────
# Check Lock Node Tests - Command Detection During Lock
# ─────────────────────────────────────────────────────────────────────────────


class TestCheckLockWithCommands:
    """Tests for command detection during locked session."""

    def test_cancel_detected_during_lock(self, locked_state):
        """Should detect cancel command even when session is locked."""
        locked_state["message_body"] = "cancelar"
        
        result = check_agent_lock_node(locked_state)
        
        assert result["is_command"] is True
        assert result["command_action"] == "cancel_current_flow"
        assert result["routing_method"] == "command"

    def test_menu_detected_during_lock(self, locked_state):
        """Should detect menu command even when session is locked."""
        locked_state["message_body"] = "menu"
        
        result = check_agent_lock_node(locked_state)
        
        assert result["is_command"] is True
        assert result["command_action"] == "show_menu"

    def test_help_detected_during_lock(self, locked_state):
        """Should detect help command even when session is locked."""
        locked_state["message_body"] = "ayuda"
        
        result = check_agent_lock_node(locked_state)
        
        assert result["is_command"] is True
        assert result["command_action"] == "show_help"

    def test_regular_message_continues_locked_flow(self, locked_state):
        """Regular messages should continue with locked agent."""
        locked_state["message_body"] = "50 soles taxi"
        
        result = check_agent_lock_node(locked_state)
        
        assert result["is_command"] is False
        assert result["routing_method"] == "locked"


# ─────────────────────────────────────────────────────────────────────────────
# Should Detect Intent Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestShouldDetectIntent:
    """Tests for should_detect_intent conditional edge."""

    def test_command_routes_to_command(self, base_state):
        """Should route to 'command' when is_command is True."""
        base_state["is_command"] = True
        
        result = should_detect_intent(base_state)
        
        assert result == "command"

    def test_onboarding_routes_to_onboarding(self, base_state):
        """Should route to 'onboarding' when not onboarding completed."""
        base_state["onboarding_completed"] = False
        base_state["is_command"] = False
        
        result = should_detect_intent(base_state)
        
        assert result == "onboarding"

    def test_locked_routes_to_locked(self, locked_state):
        """Should route to 'locked' when session is locked."""
        locked_state["is_command"] = False
        
        result = should_detect_intent(locked_state)
        
        assert result == "locked"

    def test_unlocked_routes_to_unlocked(self, base_state):
        """Should route to 'unlocked' when session is not locked."""
        base_state["agent_locked"] = False
        base_state["is_command"] = False
        
        result = should_detect_intent(base_state)
        
        assert result == "unlocked"


# ─────────────────────────────────────────────────────────────────────────────
# Intent Change Detection Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestIntentChangeDetection:
    """Tests for intent change detection while locked."""

    def test_no_change_for_same_agent_keywords(self):
        """Should not change when keywords match current agent."""
        # Currently in IE, message has expense keywords
        result = _check_intent_change("50 soles taxi", AgentType.IE)
        
        assert result["changed"] is False

    def test_change_from_ie_to_coach(self):
        """Should detect change from IE to Coach."""
        # Currently in IE, but query keywords
        result = _check_intent_change("cuánto gasté este mes?", AgentType.IE)
        
        assert result["changed"] is True
        assert result["new_agent"] == AgentType.COACH

    def test_change_from_coach_to_ie(self):
        """Should detect change from Coach to IE."""
        # Currently in Coach, but expense keywords
        result = _check_intent_change("gasté 50 soles en taxi", AgentType.COACH)
        
        assert result["changed"] is True
        assert result["new_agent"] == AgentType.IE

    def test_command_triggers_change(self):
        """Command should always trigger change."""
        result = _check_intent_change("cancelar", AgentType.IE)
        
        assert result["changed"] is True
        assert result["new_agent"] is None  # Commands handled separately

    def test_no_change_for_ambiguous_message(self):
        """Should not change for ambiguous messages."""
        result = _check_intent_change("hola", AgentType.IE)
        
        assert result["changed"] is False


# ─────────────────────────────────────────────────────────────────────────────
# User Cannot Be Trapped Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestNoDeadlocks:
    """Tests to ensure user can always escape from any state."""

    @pytest.mark.parametrize(
        "active_agent",
        ["ie", "coach", "configuration", "ivr"],
    )
    def test_cancel_works_from_any_agent(self, locked_state, active_agent):
        """User should be able to cancel from any locked agent."""
        locked_state["active_agent"] = active_agent
        locked_state["message_body"] = "cancelar"
        
        result = check_agent_lock_node(locked_state)
        
        assert result["is_command"] is True
        assert result["command_action"] == "cancel_current_flow"

    @pytest.mark.parametrize(
        "lock_reason",
        [
            "awaiting_input",
            "awaiting_confirmation",
            "processing",
            "unknown_reason",
        ],
    )
    def test_cancel_works_with_any_lock_reason(self, locked_state, lock_reason):
        """User should be able to cancel regardless of lock reason."""
        locked_state["lock_reason"] = lock_reason
        locked_state["message_body"] = "cancelar"
        
        result = check_agent_lock_node(locked_state)
        
        assert result["is_command"] is True

    @pytest.mark.parametrize(
        "escape_command",
        ["cancelar", "cancel", "salir", "menu", "ayuda", "reiniciar"],
    )
    def test_all_escape_commands_work_when_locked(self, locked_state, escape_command):
        """All escape commands should work when session is locked."""
        locked_state["message_body"] = escape_command
        
        result = check_agent_lock_node(locked_state)
        
        assert result["is_command"] is True

    def test_escape_works_even_with_deep_flow_data(self, locked_state):
        """User should be able to escape even with complex flow state."""
        locked_state["flow_data"] = {
            "step_1": "completed",
            "step_2": "completed",
            "step_3": "in_progress",
            "nested": {"deep": {"data": "value"}},
        }
        locked_state["message_body"] = "cancelar"
        
        result = check_agent_lock_node(locked_state)
        
        assert result["is_command"] is True


# ─────────────────────────────────────────────────────────────────────────────
# Full Command Handler Integration Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestFullCommandHandlerIntegration:
    """Integration tests for full command handler flow."""

    @pytest.mark.asyncio
    @patch("app.storage.conversation_manager.cancel_conversation")
    async def test_full_cancel_flow(self, mock_cancel, mock_db):
        """Test complete cancel command flow."""
        user_id = uuid4()
        conversation_id = uuid4()
        
        response = await handle_coordinator_command(
            command_action="cancel_current_flow",
            user_id=user_id,
            user_name="Test User",
            home_currency="USD",
            timezone="America/Bogota",
            active_trip_name=None,
            budget_status=None,
            active_agent="ie",
            conversation_id=conversation_id,
            db=mock_db,
            request_id="test-123",
        )
        
        assert response.release_lock is True
        assert response.agent_name == "coordinator"
        mock_cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_unknown_command_returns_fallback(self, mock_db):
        """Unknown command should return fallback response."""
        response = await handle_coordinator_command(
            command_action="unknown_command",
            user_id=uuid4(),
            user_name=None,
            home_currency=None,
            timezone=None,
            active_trip_name=None,
            budget_status=None,
            active_agent=None,
            conversation_id=None,
            db=mock_db,
            request_id="test-123",
        )
        
        assert response.release_lock is True
        assert response.response_text is not None


# ─────────────────────────────────────────────────────────────────────────────
# Coordinator Commands Constant Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestCoordinatorCommandsConstant:
    """Tests for COORDINATOR_COMMANDS constant."""

    def test_all_cancel_variants_mapped(self):
        """All cancel variants should be mapped to cancel_current_flow."""
        cancel_variants = ["cancelar", "cancel", "salir", "exit"]
        
        for variant in cancel_variants:
            assert variant in COORDINATOR_COMMANDS
            assert COORDINATOR_COMMANDS[variant] == "cancel_current_flow"

    def test_all_commands_have_handlers(self):
        """All command actions should have corresponding handlers."""
        valid_actions = {
            "cancel_current_flow",
            "show_menu",
            "show_help",
            "show_status",
            "restart_conversation",
            "admin_reset",
        }
        
        for action in COORDINATOR_COMMANDS.values():
            assert action in valid_actions
