"""
Unit tests for Card Configuration IVR Flow.

Tests:
- Card configuration name step
- Card type selection
- Network selection
- Last four digits validation
- Color selection (optional)
- Confirmation flow
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.flows.ivr_processor import IVRProcessor, IVRResponse
from app.models.user import User


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return MagicMock()


@pytest.fixture
def mock_user():
    """Create a mock user."""
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.full_name = "Test User"
    user.home_currency = "COP"
    return user


@pytest.fixture
def processor(mock_db):
    """Create an IVR processor with mocked DB."""
    return IVRProcessor(db=mock_db)


# ─────────────────────────────────────────────────────────────────────────────
# Start Flow Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestCardFlowStart:
    """Tests for starting the card configuration flow."""

    def test_start_flow_prompts_for_name(self, processor, mock_user):
        """Starting flow should prompt for card name."""
        response = processor.process_card_configuration(
            user=mock_user,
            current_step=None,
            user_input="",
        )

        assert response.next_step == "name"
        assert "nombre" in response.message.lower() or "llamar" in response.message.lower()

    def test_start_from_start_step(self, processor, mock_user):
        """Start step should also prompt for name."""
        response = processor.process_card_configuration(
            user=mock_user,
            current_step="start",
            user_input="",
        )

        assert response.next_step == "name"


# ─────────────────────────────────────────────────────────────────────────────
# Name Step Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestCardNameStep:
    """Tests for card name step."""

    def test_valid_name_proceeds_to_type(self, processor, mock_user):
        """Valid name should proceed to type selection."""
        response = processor.process_card_configuration(
            user=mock_user,
            current_step="name",
            user_input="Visa Travel",
        )

        assert response.next_step == "type"
        assert response.data.get("name") == "Visa Travel"
        assert "tipo" in response.message.lower() or "crédito" in response.message.lower()

    def test_short_name_rejected(self, processor, mock_user):
        """Short name should be rejected."""
        response = processor.process_card_configuration(
            user=mock_user,
            current_step="name",
            user_input="V",
        )

        assert response.next_step == "name"
        assert "❌" in response.message


# ─────────────────────────────────────────────────────────────────────────────
# Type Step Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestCardTypeStep:
    """Tests for card type selection step."""

    def test_credit_by_number(self, processor, mock_user):
        """Selecting credit by number works."""
        temp_data = {"name": "Visa Travel"}

        response = processor.process_card_configuration(
            user=mock_user,
            current_step="type",
            user_input="1",
            temp_data=temp_data,
        )

        assert response.next_step == "network"
        assert response.data.get("card_type") == "credit"

    def test_debit_by_number(self, processor, mock_user):
        """Selecting debit by number works."""
        temp_data = {"name": "Débito Nómina"}

        response = processor.process_card_configuration(
            user=mock_user,
            current_step="type",
            user_input="2",
            temp_data=temp_data,
        )

        assert response.next_step == "network"
        assert response.data.get("card_type") == "debit"

    def test_credit_by_word(self, processor, mock_user):
        """Selecting credit by word works."""
        temp_data = {"name": "Visa Travel"}

        response = processor.process_card_configuration(
            user=mock_user,
            current_step="type",
            user_input="crédito",
            temp_data=temp_data,
        )

        assert response.data.get("card_type") == "credit"

    def test_invalid_type_rejected(self, processor, mock_user):
        """Invalid type should be rejected."""
        temp_data = {"name": "Visa Travel"}

        response = processor.process_card_configuration(
            user=mock_user,
            current_step="type",
            user_input="prepago",
            temp_data=temp_data,
        )

        assert response.next_step == "type"
        assert "❌" in response.message


# ─────────────────────────────────────────────────────────────────────────────
# Network Step Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestCardNetworkStep:
    """Tests for card network selection step."""

    def test_visa_by_number(self, processor, mock_user):
        """Selecting Visa by number works."""
        temp_data = {"name": "Visa Travel", "card_type": "credit"}

        response = processor.process_card_configuration(
            user=mock_user,
            current_step="network",
            user_input="1",
            temp_data=temp_data,
        )

        assert response.next_step == "last_four"
        assert response.data.get("network") == "visa"

    def test_mastercard_by_number(self, processor, mock_user):
        """Selecting Mastercard by number works."""
        temp_data = {"name": "MC Gold", "card_type": "credit"}

        response = processor.process_card_configuration(
            user=mock_user,
            current_step="network",
            user_input="2",
            temp_data=temp_data,
        )

        assert response.data.get("network") == "mastercard"

    def test_network_by_name(self, processor, mock_user):
        """Selecting network by name works."""
        temp_data = {"name": "Visa Travel", "card_type": "credit"}

        response = processor.process_card_configuration(
            user=mock_user,
            current_step="network",
            user_input="visa",
            temp_data=temp_data,
        )

        assert response.data.get("network") == "visa"


# ─────────────────────────────────────────────────────────────────────────────
# Last Four Step Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestCardLastFourStep:
    """Tests for last four digits step."""

    def test_valid_four_digits(self, processor, mock_user):
        """Valid 4 digits should proceed."""
        temp_data = {
            "name": "Visa Travel",
            "card_type": "credit",
            "network": "visa",
        }

        response = processor.process_card_configuration(
            user=mock_user,
            current_step="last_four",
            user_input="4532",
            temp_data=temp_data,
        )

        assert response.next_step == "color"
        assert response.data.get("last_four") == "4532"

    def test_extracts_digits_from_text(self, processor, mock_user):
        """Should extract digits from mixed text."""
        temp_data = {
            "name": "Visa Travel",
            "card_type": "credit",
            "network": "visa",
        }

        response = processor.process_card_configuration(
            user=mock_user,
            current_step="last_four",
            user_input="terminada en 4532",
            temp_data=temp_data,
        )

        assert response.data.get("last_four") == "4532"

    def test_too_few_digits_rejected(self, processor, mock_user):
        """Less than 4 digits should be rejected."""
        temp_data = {
            "name": "Visa Travel",
            "card_type": "credit",
            "network": "visa",
        }

        response = processor.process_card_configuration(
            user=mock_user,
            current_step="last_four",
            user_input="123",
            temp_data=temp_data,
        )

        assert response.next_step == "last_four"
        assert "❌" in response.message

    def test_too_many_digits_rejected(self, processor, mock_user):
        """More than 4 digits should be rejected."""
        temp_data = {
            "name": "Visa Travel",
            "card_type": "credit",
            "network": "visa",
        }

        response = processor.process_card_configuration(
            user=mock_user,
            current_step="last_four",
            user_input="12345",
            temp_data=temp_data,
        )

        assert response.next_step == "last_four"


# ─────────────────────────────────────────────────────────────────────────────
# Color Step Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestCardColorStep:
    """Tests for optional color step."""

    def test_color_by_number(self, processor, mock_user):
        """Selecting color by number works."""
        temp_data = {
            "name": "Visa Travel",
            "card_type": "credit",
            "network": "visa",
            "last_four": "4532",
        }

        response = processor.process_card_configuration(
            user=mock_user,
            current_step="color",
            user_input="1",
            temp_data=temp_data,
        )

        assert response.next_step == "confirm"
        assert response.data.get("color") == "blue"

    def test_skip_color(self, processor, mock_user):
        """Skipping color works."""
        temp_data = {
            "name": "Visa Travel",
            "card_type": "credit",
            "network": "visa",
            "last_four": "4532",
        }

        response = processor.process_card_configuration(
            user=mock_user,
            current_step="color",
            user_input="saltar",
            temp_data=temp_data,
        )

        assert response.next_step == "confirm"
        assert response.data.get("color") is None


# ─────────────────────────────────────────────────────────────────────────────
# Confirmation Step Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestCardConfirmStep:
    """Tests for confirmation step."""

    def test_confirm_creates_card(self, processor, mock_user):
        """Confirming should create card."""
        temp_data = {
            "name": "Visa Travel",
            "card_type": "credit",
            "network": "visa",
            "last_four": "4532",
            "color": "blue",
        }

        mock_card = MagicMock()
        mock_card.id = uuid4()
        mock_card.name = "Visa Travel"
        mock_card.card_type = "credit"
        mock_card.network = "visa"
        mock_card.last_four_digits = "4532"

        with patch.object(processor, "_create_card_from_data", return_value=mock_card):
            response = processor.process_card_configuration(
                user=mock_user,
                current_step="confirm",
                user_input="1",
                temp_data=temp_data,
            )

        assert response.flow_complete is True
        assert "✅" in response.message

    def test_deny_cancels_flow(self, processor, mock_user):
        """Denying should cancel flow."""
        temp_data = {
            "name": "Visa Travel",
            "card_type": "credit",
            "network": "visa",
            "last_four": "4532",
        }

        response = processor.process_card_configuration(
            user=mock_user,
            current_step="confirm",
            user_input="2",
            temp_data=temp_data,
        )

        assert response.flow_complete is True
        assert "cancelada" in response.message.lower()

    def test_invalid_response_prompts_again(self, processor, mock_user):
        """Invalid response should prompt again."""
        temp_data = {
            "name": "Visa Travel",
            "card_type": "credit",
            "network": "visa",
            "last_four": "4532",
        }

        response = processor.process_card_configuration(
            user=mock_user,
            current_step="confirm",
            user_input="maybe",
            temp_data=temp_data,
        )

        assert response.next_step == "confirm"
        assert "❓" in response.message


# ─────────────────────────────────────────────────────────────────────────────
# Full Flow Test
# ─────────────────────────────────────────────────────────────────────────────


class TestCardFullFlow:
    """Test complete card configuration flow."""

    def test_full_flow_happy_path(self, processor, mock_user):
        """Test complete happy path flow."""
        # Start
        response = processor.process_card_configuration(
            user=mock_user,
            current_step=None,
            user_input="",
        )
        assert response.next_step == "name"

        # Name
        response = processor.process_card_configuration(
            user=mock_user,
            current_step="name",
            user_input="Visa Gold",
            temp_data=response.data,
        )
        assert response.next_step == "type"
        assert response.data["name"] == "Visa Gold"

        # Type
        response = processor.process_card_configuration(
            user=mock_user,
            current_step="type",
            user_input="1",
            temp_data=response.data,
        )
        assert response.next_step == "network"
        assert response.data["card_type"] == "credit"

        # Network
        response = processor.process_card_configuration(
            user=mock_user,
            current_step="network",
            user_input="1",
            temp_data=response.data,
        )
        assert response.next_step == "last_four"
        assert response.data["network"] == "visa"

        # Last Four
        response = processor.process_card_configuration(
            user=mock_user,
            current_step="last_four",
            user_input="4532",
            temp_data=response.data,
        )
        assert response.next_step == "color"
        assert response.data["last_four"] == "4532"

        # Color (skip)
        response = processor.process_card_configuration(
            user=mock_user,
            current_step="color",
            user_input="saltar",
            temp_data=response.data,
        )
        assert response.next_step == "confirm"

        # Confirm with mock
        mock_card = MagicMock()
        mock_card.id = uuid4()
        mock_card.name = "Visa Gold"
        mock_card.card_type = "credit"
        mock_card.network = "visa"
        mock_card.last_four_digits = "4532"

        with patch.object(processor, "_create_card_from_data", return_value=mock_card):
            response = processor.process_card_configuration(
                user=mock_user,
                current_step="confirm",
                user_input="1",
                temp_data=response.data,
            )

        assert response.flow_complete is True
        assert "Visa Gold" in response.message

