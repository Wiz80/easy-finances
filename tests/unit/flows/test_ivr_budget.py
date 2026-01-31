"""
Unit tests for IVR Budget Creation Flow.

Tests the menu-based budget creation without LLM.
"""

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.flows.ivr_processor import IVRProcessor, IVRResponse
from app.models.user import User
from app.models.budget import Budget


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def ivr_processor(db: Session) -> IVRProcessor:
    """Create an IVR processor with test database."""
    return IVRProcessor(db)


@pytest.fixture
def onboarded_user(db: Session) -> User:
    """Create an onboarded user for budget tests."""
    user = User(
        id=uuid.uuid4(),
        phone_number="+573001234567",
        full_name="Budget Test User",
        nickname="Budget",
        home_currency="COP",
        country="CO",
        timezone="America/Bogota",
        preferred_language="es",
        onboarding_status="completed",
        onboarding_completed_at=datetime.utcnow(),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ─────────────────────────────────────────────────────────────────────────────
# Budget Flow Start Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestBudgetFlowStart:
    """Tests for starting budget creation flow."""

    def test_start_budget_creation(self, ivr_processor: IVRProcessor, onboarded_user: User):
        """Starting budget creation should ask for name."""
        response = ivr_processor.process_budget_creation(
            user=onboarded_user,
            current_step=None,
            user_input="crear presupuesto",
        )

        assert response.next_step == "name"
        assert "nombre" in response.message.lower() or "llamar" in response.message.lower()

    def test_start_budget_explicit_start(self, ivr_processor: IVRProcessor, onboarded_user: User):
        """Explicit 'start' step should begin budget creation."""
        response = ivr_processor.process_budget_creation(
            user=onboarded_user,
            current_step="start",
            user_input="ok",
        )

        assert response.next_step == "name"


# ─────────────────────────────────────────────────────────────────────────────
# Budget Name Step Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestBudgetNameStep:
    """Tests for budget name step."""

    def test_valid_budget_name(self, ivr_processor: IVRProcessor, onboarded_user: User):
        """Valid name should proceed to amount step."""
        response = ivr_processor.process_budget_creation(
            user=onboarded_user,
            current_step="name",
            user_input="Enero 2025",
            temp_data={},
        )

        assert response.next_step == "amount"
        assert response.data.get("name") == "Enero 2025"
        assert "monto" in response.message.lower()

    def test_invalid_budget_name(self, ivr_processor: IVRProcessor, onboarded_user: User):
        """Invalid name should stay at name step."""
        response = ivr_processor.process_budget_creation(
            user=onboarded_user,
            current_step="name",
            user_input="A",  # Too short
            temp_data={},
        )

        assert response.next_step == "name"
        assert response.error is not None


# ─────────────────────────────────────────────────────────────────────────────
# Budget Amount Step Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestBudgetAmountStep:
    """Tests for budget amount step."""

    def test_valid_amount_integer(self, ivr_processor: IVRProcessor, onboarded_user: User):
        """Integer amount should proceed to currency step."""
        response = ivr_processor.process_budget_creation(
            user=onboarded_user,
            current_step="amount",
            user_input="5000000",
            temp_data={"name": "Test Budget"},
        )

        assert response.next_step == "currency"
        assert response.data.get("amount") == "5000000"

    def test_valid_amount_with_comma(self, ivr_processor: IVRProcessor, onboarded_user: User):
        """Amount with comma should work."""
        response = ivr_processor.process_budget_creation(
            user=onboarded_user,
            current_step="amount",
            user_input="1,500.50",
            temp_data={"name": "Test Budget"},
        )

        assert response.next_step == "currency"

    def test_invalid_amount_zero(self, ivr_processor: IVRProcessor, onboarded_user: User):
        """Zero amount should fail."""
        response = ivr_processor.process_budget_creation(
            user=onboarded_user,
            current_step="amount",
            user_input="0",
            temp_data={"name": "Test Budget"},
        )

        assert response.next_step == "amount"
        assert response.error is not None

    def test_invalid_amount_text(self, ivr_processor: IVRProcessor, onboarded_user: User):
        """Non-numeric amount should fail."""
        response = ivr_processor.process_budget_creation(
            user=onboarded_user,
            current_step="amount",
            user_input="mucho dinero",
            temp_data={"name": "Test Budget"},
        )

        assert response.next_step == "amount"
        assert response.error is not None


# ─────────────────────────────────────────────────────────────────────────────
# Budget Currency Step Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestBudgetCurrencyStep:
    """Tests for budget currency step."""

    def test_select_home_currency(self, ivr_processor: IVRProcessor, onboarded_user: User):
        """Selecting '1' should use home currency."""
        response = ivr_processor.process_budget_creation(
            user=onboarded_user,
            current_step="currency",
            user_input="1",
            temp_data={"name": "Test", "amount": "5000000"},
        )

        assert response.next_step == "start_date"
        assert response.data.get("currency") == "COP"

    def test_select_other_currency_by_code(self, ivr_processor: IVRProcessor, onboarded_user: User):
        """Selecting by code should work."""
        response = ivr_processor.process_budget_creation(
            user=onboarded_user,
            current_step="currency",
            user_input="USD",
            temp_data={"name": "Test", "amount": "3000"},
        )

        assert response.next_step == "start_date"
        assert response.data.get("currency") == "USD"


# ─────────────────────────────────────────────────────────────────────────────
# Budget Date Steps Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestBudgetDateSteps:
    """Tests for budget start/end date steps."""

    def test_start_date_today(self, ivr_processor: IVRProcessor, onboarded_user: User):
        """Selecting '1' for start date should use today."""
        response = ivr_processor.process_budget_creation(
            user=onboarded_user,
            current_step="start_date",
            user_input="1",
            temp_data={"name": "Test", "amount": "5000000", "currency": "COP"},
        )

        assert response.next_step == "end_date"
        assert response.data.get("start_date") == date.today().isoformat()

    def test_start_date_custom(self, ivr_processor: IVRProcessor, onboarded_user: User):
        """Custom start date should work."""
        response = ivr_processor.process_budget_creation(
            user=onboarded_user,
            current_step="start_date",
            user_input="01/02/2025",
            temp_data={"name": "Test", "amount": "5000000", "currency": "COP"},
        )

        assert response.next_step == "end_date"
        assert response.data.get("start_date") == "2025-02-01"

    def test_end_date_end_of_month(self, ivr_processor: IVRProcessor, onboarded_user: User):
        """Selecting '1' for end date should use end of month."""
        response = ivr_processor.process_budget_creation(
            user=onboarded_user,
            current_step="end_date",
            user_input="1",
            temp_data={
                "name": "Test",
                "amount": "5000000",
                "currency": "COP",
                "start_date": date.today().isoformat(),
            },
        )

        assert response.next_step == "confirm"
        assert response.data.get("end_date") is not None

    def test_end_date_30_days(self, ivr_processor: IVRProcessor, onboarded_user: User):
        """Selecting '2' for end date should use 30 days from today."""
        response = ivr_processor.process_budget_creation(
            user=onboarded_user,
            current_step="end_date",
            user_input="2",
            temp_data={
                "name": "Test",
                "amount": "5000000",
                "currency": "COP",
                "start_date": date.today().isoformat(),
            },
        )

        assert response.next_step == "confirm"
        expected_end = (date.today() + timedelta(days=30)).isoformat()
        assert response.data.get("end_date") == expected_end


# ─────────────────────────────────────────────────────────────────────────────
# Budget Confirmation Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestBudgetConfirmation:
    """Tests for budget confirmation step."""

    def test_cancel_budget(self, ivr_processor: IVRProcessor, onboarded_user: User):
        """Cancelling should complete flow without creating budget."""
        temp_data = {
            "name": "Test Budget",
            "amount": "5000000",
            "currency": "COP",
            "start_date": date.today().isoformat(),
            "end_date": (date.today() + timedelta(days=30)).isoformat(),
        }

        response = ivr_processor.process_budget_creation(
            user=onboarded_user,
            current_step="confirm",
            user_input="2",  # No
            temp_data=temp_data,
        )

        assert response.flow_complete is True
        assert "cancelado" in response.message.lower()
        assert onboarded_user.current_budget_id is None

    def test_invalid_confirmation_response(self, ivr_processor: IVRProcessor, onboarded_user: User):
        """Invalid response should stay at confirm step."""
        temp_data = {
            "name": "Test Budget",
            "amount": "5000000",
            "currency": "COP",
            "start_date": date.today().isoformat(),
            "end_date": (date.today() + timedelta(days=30)).isoformat(),
        }

        response = ivr_processor.process_budget_creation(
            user=onboarded_user,
            current_step="confirm",
            user_input="maybe",
            temp_data=temp_data,
        )

        assert response.next_step == "confirm"
        assert "1" in response.message and "2" in response.message


# ─────────────────────────────────────────────────────────────────────────────
# Full Flow Test
# ─────────────────────────────────────────────────────────────────────────────

class TestBudgetFullFlow:
    """Tests for complete budget creation flow."""

    def test_full_budget_creation_flow(
        self, ivr_processor: IVRProcessor, onboarded_user: User, db_with_categories: Session
    ):
        """Complete budget flow should work end-to-end."""
        db = db_with_categories
        
        # Update processor with correct db
        ivr_processor.db = db

        # Step 1: Start
        response = ivr_processor.process_budget_creation(
            user=onboarded_user,
            current_step=None,
            user_input="crear presupuesto",
        )
        assert response.next_step == "name"
        temp_data = response.data

        # Step 2: Name
        response = ivr_processor.process_budget_creation(
            user=onboarded_user,
            current_step="name",
            user_input="Febrero 2025",
            temp_data=temp_data,
        )
        assert response.next_step == "amount"
        temp_data = response.data

        # Step 3: Amount
        response = ivr_processor.process_budget_creation(
            user=onboarded_user,
            current_step="amount",
            user_input="3000000",
            temp_data=temp_data,
        )
        assert response.next_step == "currency"
        temp_data = response.data

        # Step 4: Currency (use home currency)
        response = ivr_processor.process_budget_creation(
            user=onboarded_user,
            current_step="currency",
            user_input="1",
            temp_data=temp_data,
        )
        assert response.next_step == "start_date"
        temp_data = response.data

        # Step 5: Start date (today)
        response = ivr_processor.process_budget_creation(
            user=onboarded_user,
            current_step="start_date",
            user_input="1",
            temp_data=temp_data,
        )
        assert response.next_step == "end_date"
        temp_data = response.data

        # Step 6: End date (30 days)
        response = ivr_processor.process_budget_creation(
            user=onboarded_user,
            current_step="end_date",
            user_input="2",
            temp_data=temp_data,
        )
        assert response.next_step == "confirm"
        temp_data = response.data

        # Verify confirmation message contains all data
        assert "Febrero 2025" in response.message
        assert "3000000" in response.message
        assert "COP" in response.message

