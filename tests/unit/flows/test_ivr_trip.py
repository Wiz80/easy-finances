"""
Unit tests for Trip Creation IVR Flow.

Tests:
- Trip creation flow steps
- Budget linking options
- Trip with new budget
- Trip with existing budget
- Trip without budget
"""

from datetime import date
from decimal import Decimal
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
    user.timezone = "America/Bogota"
    return user


@pytest.fixture
def processor(mock_db):
    """Create an IVR processor with mocked DB."""
    return IVRProcessor(db=mock_db)


# ─────────────────────────────────────────────────────────────────────────────
# Start Flow Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestTripFlowStart:
    """Tests for starting the trip creation flow."""

    def test_start_flow_prompts_for_name(self, processor, mock_user):
        """Starting flow should prompt for trip name."""
        response = processor.process_trip_creation(
            user=mock_user,
            current_step=None,
            user_input="",
        )

        assert response.next_step == "name"
        assert "nombre" in response.message.lower() or "llamar" in response.message.lower()

    def test_start_from_start_step(self, processor, mock_user):
        """Start step should also prompt for name."""
        response = processor.process_trip_creation(
            user=mock_user,
            current_step="start",
            user_input="",
        )

        assert response.next_step == "name"


# ─────────────────────────────────────────────────────────────────────────────
# Name Step Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestTripNameStep:
    """Tests for trip name step."""

    def test_valid_name_proceeds_to_country(self, processor, mock_user):
        """Valid name should proceed to country selection."""
        response = processor.process_trip_creation(
            user=mock_user,
            current_step="name",
            user_input="Ecuador Adventure",
        )

        assert response.next_step == "country"
        assert response.data.get("name") == "Ecuador Adventure"

    def test_short_name_rejected(self, processor, mock_user):
        """Short name should be rejected."""
        response = processor.process_trip_creation(
            user=mock_user,
            current_step="name",
            user_input="E",
        )

        assert response.next_step == "name"
        assert "❌" in response.message


# ─────────────────────────────────────────────────────────────────────────────
# Country Step Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestTripCountryStep:
    """Tests for country selection step."""

    def test_country_by_number(self, processor, mock_user):
        """Selecting country by number works."""
        temp_data = {"name": "Ecuador Trip"}

        response = processor.process_trip_creation(
            user=mock_user,
            current_step="country",
            user_input="9",  # Ecuador is 9th in the list
            temp_data=temp_data,
        )

        assert response.next_step == "start_date"
        assert response.data.get("country") == "EC"

    def test_country_by_name(self, processor, mock_user):
        """Selecting country by name works."""
        temp_data = {"name": "Mexico Trip"}

        response = processor.process_trip_creation(
            user=mock_user,
            current_step="country",
            user_input="México",
            temp_data=temp_data,
        )

        assert response.next_step == "start_date"
        assert response.data.get("country") == "MX"


# ─────────────────────────────────────────────────────────────────────────────
# Date Steps Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestTripDateSteps:
    """Tests for date selection steps."""

    def test_start_date_valid(self, processor, mock_user):
        """Valid start date should proceed."""
        temp_data = {"name": "Ecuador Trip", "country": "EC"}

        response = processor.process_trip_creation(
            user=mock_user,
            current_step="start_date",
            user_input="15/02/2026",
            temp_data=temp_data,
        )

        assert response.next_step == "end_date"
        assert response.data.get("start_date") == "2026-02-15"

    def test_start_date_keyword_hoy(self, processor, mock_user):
        """'hoy' keyword should set today's date."""
        temp_data = {"name": "Ecuador Trip", "country": "EC"}

        response = processor.process_trip_creation(
            user=mock_user,
            current_step="start_date",
            user_input="hoy",
            temp_data=temp_data,
        )

        assert response.next_step == "end_date"
        assert response.data.get("start_date") == date.today().isoformat()

    def test_end_date_valid(self, processor, mock_user):
        """Valid end date should proceed to budget linking."""
        temp_data = {
            "name": "Ecuador Trip",
            "country": "EC",
            "start_date": "2026-02-15",
        }

        with patch.object(processor, "_build_budget_linking_menu") as mock_menu:
            mock_menu.return_value = "Budget menu"

            response = processor.process_trip_creation(
                user=mock_user,
                current_step="end_date",
                user_input="28/02/2026",
                temp_data=temp_data,
            )

        assert response.next_step == "link_budget"
        assert response.data.get("end_date") == "2026-02-28"


# ─────────────────────────────────────────────────────────────────────────────
# Budget Linking Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestTripBudgetLinking:
    """Tests for budget linking step."""

    def test_create_new_budget(self, processor, mock_user):
        """Option 1 should create new budget."""
        temp_data = {
            "name": "Ecuador Trip",
            "country": "EC",
            "start_date": "2026-02-15",
            "end_date": "2026-02-28",
        }

        response = processor.process_trip_creation(
            user=mock_user,
            current_step="link_budget",
            user_input="1",
            temp_data=temp_data,
        )

        assert response.next_step == "budget_amount"
        assert response.data.get("budget_action") == "create"

    def test_no_budget(self, processor, mock_user):
        """Option 2 should skip budget."""
        temp_data = {
            "name": "Ecuador Trip",
            "country": "EC",
            "start_date": "2026-02-15",
            "end_date": "2026-02-28",
        }

        response = processor.process_trip_creation(
            user=mock_user,
            current_step="link_budget",
            user_input="2",
            temp_data=temp_data,
        )

        assert response.next_step == "confirm"
        assert response.data.get("budget_action") == "none"

    def test_link_existing_budget(self, processor, mock_user):
        """Option 3+ should link existing budget."""
        temp_data = {
            "name": "Ecuador Trip",
            "country": "EC",
            "start_date": "2026-02-15",
            "end_date": "2026-02-28",
            "existing_budgets": [
                {"id": str(uuid4()), "name": "Existing Budget"}
            ],
        }

        response = processor.process_trip_creation(
            user=mock_user,
            current_step="link_budget",
            user_input="3",
            temp_data=temp_data,
        )

        assert response.next_step == "confirm"
        assert response.data.get("budget_action") == "link"
        assert response.data.get("linked_budget_name") == "Existing Budget"


# ─────────────────────────────────────────────────────────────────────────────
# Budget Amount Step Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestTripBudgetAmount:
    """Tests for budget amount step."""

    def test_valid_budget_amount(self, processor, mock_user):
        """Valid amount should proceed to confirm."""
        temp_data = {
            "name": "Ecuador Trip",
            "country": "EC",
            "start_date": "2026-02-15",
            "end_date": "2026-02-28",
            "budget_action": "create",
        }

        response = processor.process_trip_creation(
            user=mock_user,
            current_step="budget_amount",
            user_input="5000000",
            temp_data=temp_data,
        )

        assert response.next_step == "confirm"
        assert response.data.get("budget_amount") == "5000000"
        assert response.data.get("budget_currency") == "COP"


# ─────────────────────────────────────────────────────────────────────────────
# Confirmation Step Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestTripConfirmation:
    """Tests for confirmation step."""

    def test_confirm_creates_trip(self, processor, mock_user):
        """Confirming should create trip."""
        temp_data = {
            "name": "Ecuador Trip",
            "country": "EC",
            "start_date": "2026-02-15",
            "end_date": "2026-02-28",
            "budget_action": "none",
        }

        mock_trip = MagicMock()
        mock_trip.id = uuid4()
        mock_trip.name = "Ecuador Trip"
        mock_trip.start_date = date(2026, 2, 15)
        mock_trip.end_date = date(2026, 2, 28)

        with patch.object(
            processor, "_create_trip_with_budget", return_value=(mock_trip, None)
        ):
            response = processor.process_trip_creation(
                user=mock_user,
                current_step="confirm",
                user_input="1",
                temp_data=temp_data,
            )

        assert response.flow_complete is True
        assert "✅" in response.message
        assert "Ecuador Trip" in response.message

    def test_confirm_creates_trip_with_budget(self, processor, mock_user):
        """Confirming should create trip with budget."""
        temp_data = {
            "name": "Ecuador Trip",
            "country": "EC",
            "start_date": "2026-02-15",
            "end_date": "2026-02-28",
            "budget_action": "create",
            "budget_amount": "5000000",
            "budget_currency": "COP",
        }

        mock_trip = MagicMock()
        mock_trip.id = uuid4()
        mock_trip.name = "Ecuador Trip"
        mock_trip.start_date = date(2026, 2, 15)
        mock_trip.end_date = date(2026, 2, 28)

        mock_budget = MagicMock()
        mock_budget.name = "Presupuesto Ecuador Trip"
        mock_budget.total_amount = Decimal("5000000")
        mock_budget.currency = "COP"

        with patch.object(
            processor, "_create_trip_with_budget", return_value=(mock_trip, mock_budget)
        ):
            response = processor.process_trip_creation(
                user=mock_user,
                current_step="confirm",
                user_input="1",
                temp_data=temp_data,
            )

        assert response.flow_complete is True
        assert "✅" in response.message
        assert "Presupuesto" in response.message

    def test_deny_cancels_flow(self, processor, mock_user):
        """Denying should cancel flow."""
        temp_data = {
            "name": "Ecuador Trip",
            "country": "EC",
            "start_date": "2026-02-15",
            "end_date": "2026-02-28",
            "budget_action": "none",
        }

        response = processor.process_trip_creation(
            user=mock_user,
            current_step="confirm",
            user_input="2",
            temp_data=temp_data,
        )

        assert response.flow_complete is True
        assert "cancelado" in response.message.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Full Flow Test
# ─────────────────────────────────────────────────────────────────────────────


class TestTripFullFlow:
    """Test complete trip creation flow."""

    def test_full_flow_happy_path(self, processor, mock_user):
        """Test complete happy path flow without budget."""
        # Start
        response = processor.process_trip_creation(
            user=mock_user,
            current_step=None,
            user_input="",
        )
        assert response.next_step == "name"

        # Name
        response = processor.process_trip_creation(
            user=mock_user,
            current_step="name",
            user_input="Ecuador Adventure",
            temp_data=response.data,
        )
        assert response.next_step == "country"
        assert response.data["name"] == "Ecuador Adventure"

        # Country
        response = processor.process_trip_creation(
            user=mock_user,
            current_step="country",
            user_input="Ecuador",
            temp_data=response.data,
        )
        assert response.next_step == "start_date"
        assert response.data["country"] == "EC"

        # Start Date
        response = processor.process_trip_creation(
            user=mock_user,
            current_step="start_date",
            user_input="hoy",
            temp_data=response.data,
        )
        assert response.next_step == "end_date"

        # End Date
        with patch.object(processor, "_build_budget_linking_menu") as mock_menu:
            mock_menu.return_value = "Budget menu"

            response = processor.process_trip_creation(
                user=mock_user,
                current_step="end_date",
                user_input="15/02/2026",
                temp_data=response.data,
            )
        assert response.next_step == "link_budget"

        # Link Budget (none)
        response = processor.process_trip_creation(
            user=mock_user,
            current_step="link_budget",
            user_input="2",
            temp_data=response.data,
        )
        assert response.next_step == "confirm"
        assert response.data["budget_action"] == "none"

        # Confirm with mock
        mock_trip = MagicMock()
        mock_trip.id = uuid4()
        mock_trip.name = "Ecuador Adventure"
        mock_trip.start_date = date.today()
        mock_trip.end_date = date(2026, 2, 15)

        with patch.object(
            processor, "_create_trip_with_budget", return_value=(mock_trip, None)
        ):
            response = processor.process_trip_creation(
                user=mock_user,
                current_step="confirm",
                user_input="1",
                temp_data=response.data,
            )

        assert response.flow_complete is True
        assert "Ecuador Adventure" in response.message


# ─────────────────────────────────────────────────────────────────────────────
# Budget Writer Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestBudgetWriterFunctions:
    """Tests for budget writer helper functions."""

    def test_get_user_active_budgets(self):
        """Test getting active budgets for user."""
        from app.models.budget import Budget

        mock_db = MagicMock()
        mock_budget = MagicMock(spec=Budget)
        mock_budget.id = uuid4()
        mock_budget.name = "Test Budget"
        mock_budget.status = "active"

        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            mock_budget
        ]

        from app.storage.budget_writer import get_user_active_budgets

        result = get_user_active_budgets(mock_db, uuid4())

        assert len(result) == 1
        assert result[0].name == "Test Budget"

    def test_link_budget_to_trip(self):
        """Test linking budget to trip."""
        from app.models.budget import Budget

        mock_db = MagicMock()
        mock_budget = MagicMock(spec=Budget)
        mock_budget.id = uuid4()
        mock_budget.trip_id = None

        mock_db.query.return_value.filter.return_value.first.return_value = mock_budget

        from app.storage.budget_writer import link_budget_to_trip

        trip_id = uuid4()
        result = link_budget_to_trip(mock_db, mock_budget.id, trip_id)

        assert result is not None
        assert result.trip_id == trip_id


# ─────────────────────────────────────────────────────────────────────────────
# Deprecation Warning Test
# ─────────────────────────────────────────────────────────────────────────────


class TestConfigurationAgentDeprecation:
    """Tests for Configuration Agent deprecation warning."""

    def test_deprecation_warning_emitted(self):
        """Importing configuration_agent should emit warning."""
        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            # Force reimport
            import importlib
            import app.agents.configuration_agent

            importlib.reload(app.agents.configuration_agent)

            # Check that a deprecation warning was issued
            deprecation_warnings = [
                warning for warning in w if issubclass(warning.category, DeprecationWarning)
            ]

            assert len(deprecation_warnings) >= 1
            assert "deprecated" in str(deprecation_warnings[0].message).lower()

