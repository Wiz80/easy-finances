"""
Unit tests for IVR Processor.

Tests the menu-based onboarding flow without LLM calls.
"""

import uuid
from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from app.flows.ivr_processor import IVRProcessor, IVRResponse
from app.models.account import Account
from app.models.user import User


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def ivr_processor(db: Session) -> IVRProcessor:
    """Create an IVR processor with test database."""
    return IVRProcessor(db)


@pytest.fixture
def pending_user(db: Session) -> User:
    """Create a user that needs onboarding."""
    user = User(
        id=uuid.uuid4(),
        phone_number="+573001112222",
        full_name="Usuario",
        home_currency="USD",
        timezone="America/Mexico_City",
        preferred_language="es",
        onboarding_status="pending",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def user_at_name_step(db: Session) -> User:
    """Create a user at the name step of onboarding."""
    user = User(
        id=uuid.uuid4(),
        phone_number="+573001113333",
        full_name="Usuario",
        home_currency="USD",
        timezone="America/Mexico_City",
        preferred_language="es",
        onboarding_status="in_progress",
        onboarding_step="name",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def user_at_currency_step(db: Session) -> User:
    """Create a user at the currency step of onboarding."""
    user = User(
        id=uuid.uuid4(),
        phone_number="+573001114444",
        full_name="Harrison",
        nickname="Harrison",
        home_currency="USD",
        timezone="America/Mexico_City",
        preferred_language="es",
        onboarding_status="in_progress",
        onboarding_step="currency",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def user_at_country_step(db: Session) -> User:
    """Create a user at the country step of onboarding."""
    user = User(
        id=uuid.uuid4(),
        phone_number="+573001115555",
        full_name="Harrison",
        nickname="Harrison",
        home_currency="COP",
        timezone="America/Mexico_City",
        preferred_language="es",
        onboarding_status="in_progress",
        onboarding_step="country",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def user_at_timezone_step(db: Session) -> User:
    """Create a user at the timezone step of onboarding."""
    user = User(
        id=uuid.uuid4(),
        phone_number="+573001116666",
        full_name="Harrison",
        nickname="Harrison",
        home_currency="COP",
        country="CO",
        timezone="America/Mexico_City",
        preferred_language="es",
        onboarding_status="in_progress",
        onboarding_step="timezone",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def user_at_confirm_step(db: Session) -> User:
    """Create a user at the confirmation step of onboarding."""
    user = User(
        id=uuid.uuid4(),
        phone_number="+573001117777",
        full_name="Harrison",
        nickname="Harrison",
        home_currency="COP",
        country="CO",
        timezone="America/Bogota",
        preferred_language="es",
        onboarding_status="in_progress",
        onboarding_step="confirm",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ─────────────────────────────────────────────────────────────────────────────
# Onboarding Start Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestOnboardingStart:
    """Tests for starting the onboarding flow."""

    def test_start_onboarding_no_step(self, ivr_processor: IVRProcessor, pending_user: User):
        """Starting onboarding should ask for name."""
        response = ivr_processor.process_onboarding(
            user=pending_user,
            current_step=None,
            user_input="hola"
        )

        assert response.next_step == "name"
        assert "nombre" in response.message.lower()
        assert pending_user.onboarding_status == "in_progress"
        assert pending_user.onboarding_step == "name"

    def test_start_onboarding_explicit_start(self, ivr_processor: IVRProcessor, pending_user: User):
        """Explicit 'start' step should begin onboarding."""
        response = ivr_processor.process_onboarding(
            user=pending_user,
            current_step="start",
            user_input="hola"
        )

        assert response.next_step == "name"
        assert "nombre" in response.message.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Name Step Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestOnboardingNameStep:
    """Tests for the name step of onboarding."""

    def test_valid_name(self, ivr_processor: IVRProcessor, user_at_name_step: User):
        """Valid name should proceed to currency step."""
        response = ivr_processor.process_onboarding(
            user=user_at_name_step,
            current_step="name",
            user_input="Harrison"
        )

        assert response.next_step == "currency"
        assert user_at_name_step.full_name == "Harrison"
        assert user_at_name_step.nickname == "Harrison"
        assert "moneda" in response.message.lower()

    def test_valid_name_with_spaces(self, ivr_processor: IVRProcessor, user_at_name_step: User):
        """Name with spaces should work and use first name as nickname."""
        response = ivr_processor.process_onboarding(
            user=user_at_name_step,
            current_step="name",
            user_input="Juan Carlos"
        )

        assert response.next_step == "currency"
        assert user_at_name_step.full_name == "Juan Carlos"
        assert user_at_name_step.nickname == "Juan"

    def test_invalid_name_too_short(self, ivr_processor: IVRProcessor, user_at_name_step: User):
        """Short name should stay at name step."""
        response = ivr_processor.process_onboarding(
            user=user_at_name_step,
            current_step="name",
            user_input="J"
        )

        assert response.next_step == "name"
        assert response.error is not None
        assert "❌" in response.message


# ─────────────────────────────────────────────────────────────────────────────
# Currency Step Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestOnboardingCurrencyStep:
    """Tests for the currency step of onboarding."""

    def test_valid_currency_by_number(self, ivr_processor: IVRProcessor, user_at_currency_step: User):
        """Selecting currency by number should proceed to country step."""
        response = ivr_processor.process_onboarding(
            user=user_at_currency_step,
            current_step="currency",
            user_input="2"  # COP
        )

        assert response.next_step == "country"
        assert user_at_currency_step.home_currency == "COP"
        assert "país" in response.message.lower()

    def test_valid_currency_by_code(self, ivr_processor: IVRProcessor, user_at_currency_step: User):
        """Selecting currency by code should work."""
        response = ivr_processor.process_onboarding(
            user=user_at_currency_step,
            current_step="currency",
            user_input="EUR"
        )

        assert response.next_step == "country"
        assert user_at_currency_step.home_currency == "EUR"

    def test_invalid_currency(self, ivr_processor: IVRProcessor, user_at_currency_step: User):
        """Invalid currency should stay at currency step."""
        response = ivr_processor.process_onboarding(
            user=user_at_currency_step,
            current_step="currency",
            user_input="XYZ"
        )

        assert response.next_step == "currency"
        assert response.error is not None


# ─────────────────────────────────────────────────────────────────────────────
# Country Step Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestOnboardingCountryStep:
    """Tests for the country step of onboarding."""

    def test_valid_country_by_number(self, ivr_processor: IVRProcessor, user_at_country_step: User):
        """Selecting country by number should proceed to timezone step."""
        response = ivr_processor.process_onboarding(
            user=user_at_country_step,
            current_step="country",
            user_input="1"  # CO
        )

        assert response.next_step == "timezone"
        assert user_at_country_step.country == "CO"
        assert "zona horaria" in response.message.lower() or "timezone" in response.message.lower()

    def test_valid_country_by_name(self, ivr_processor: IVRProcessor, user_at_country_step: User):
        """Selecting country by name should work."""
        response = ivr_processor.process_onboarding(
            user=user_at_country_step,
            current_step="country",
            user_input="México"
        )

        assert response.next_step == "timezone"
        assert user_at_country_step.country == "MX"

    def test_invalid_country(self, ivr_processor: IVRProcessor, user_at_country_step: User):
        """Invalid country should stay at country step."""
        response = ivr_processor.process_onboarding(
            user=user_at_country_step,
            current_step="country",
            user_input="Atlantis"
        )

        assert response.next_step == "country"
        assert response.error is not None


# ─────────────────────────────────────────────────────────────────────────────
# Timezone Step Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestOnboardingTimezoneStep:
    """Tests for the timezone step of onboarding."""

    def test_valid_timezone_recommended(self, ivr_processor: IVRProcessor, user_at_timezone_step: User):
        """Selecting '1' should use recommended timezone and proceed to confirm."""
        response = ivr_processor.process_onboarding(
            user=user_at_timezone_step,
            current_step="timezone",
            user_input="1"
        )

        assert response.next_step == "confirm"
        assert user_at_timezone_step.timezone == "America/Bogota"
        assert "confirma" in response.message.lower()

    def test_valid_timezone_custom(self, ivr_processor: IVRProcessor, user_at_timezone_step: User):
        """Custom timezone should work."""
        response = ivr_processor.process_onboarding(
            user=user_at_timezone_step,
            current_step="timezone",
            user_input="America/Lima"
        )

        assert response.next_step == "confirm"
        assert user_at_timezone_step.timezone == "America/Lima"

    def test_invalid_timezone_uses_default(self, ivr_processor: IVRProcessor, user_at_timezone_step: User):
        """Invalid timezone should use country default (flexible validation)."""
        response = ivr_processor.process_onboarding(
            user=user_at_timezone_step,
            current_step="timezone",
            user_input="invalid_tz"
        )

        # Flexible validation - proceeds with default
        assert response.next_step == "confirm"
        assert user_at_timezone_step.timezone == "America/Bogota"


# ─────────────────────────────────────────────────────────────────────────────
# Confirmation Step Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestOnboardingConfirmStep:
    """Tests for the confirmation step of onboarding."""

    def test_confirm_with_yes(self, ivr_processor: IVRProcessor, user_at_confirm_step: User):
        """Confirming with '1' should complete onboarding."""
        response = ivr_processor.process_onboarding(
            user=user_at_confirm_step,
            current_step="confirm",
            user_input="1"
        )

        assert response.flow_complete is True
        assert response.next_step is None
        assert user_at_confirm_step.onboarding_status == "completed"
        assert user_at_confirm_step.onboarding_step is None
        assert user_at_confirm_step.onboarding_completed_at is not None

    def test_confirm_with_si(self, ivr_processor: IVRProcessor, user_at_confirm_step: User):
        """Confirming with 'si' should complete onboarding."""
        response = ivr_processor.process_onboarding(
            user=user_at_confirm_step,
            current_step="confirm",
            user_input="si"
        )

        assert response.flow_complete is True
        assert user_at_confirm_step.onboarding_status == "completed"

    def test_confirm_with_ok(self, ivr_processor: IVRProcessor, user_at_confirm_step: User):
        """Confirming with 'ok' should complete onboarding."""
        response = ivr_processor.process_onboarding(
            user=user_at_confirm_step,
            current_step="confirm",
            user_input="ok"
        )

        assert response.flow_complete is True
        assert user_at_confirm_step.onboarding_status == "completed"

    def test_deny_restarts_onboarding(self, ivr_processor: IVRProcessor, user_at_confirm_step: User):
        """Denying should restart onboarding."""
        response = ivr_processor.process_onboarding(
            user=user_at_confirm_step,
            current_step="confirm",
            user_input="2"
        )

        assert response.next_step == "name"
        assert response.flow_complete is False
        assert user_at_confirm_step.onboarding_step == "name"

    def test_deny_with_no(self, ivr_processor: IVRProcessor, user_at_confirm_step: User):
        """Denying with 'no' should restart onboarding."""
        response = ivr_processor.process_onboarding(
            user=user_at_confirm_step,
            current_step="confirm",
            user_input="no"
        )

        assert response.next_step == "name"

    def test_invalid_response(self, ivr_processor: IVRProcessor, user_at_confirm_step: User):
        """Unknown response should ask again."""
        response = ivr_processor.process_onboarding(
            user=user_at_confirm_step,
            current_step="confirm",
            user_input="maybe"
        )

        assert response.next_step == "confirm"
        assert "1" in response.message and "2" in response.message


# ─────────────────────────────────────────────────────────────────────────────
# Full Flow Test
# ─────────────────────────────────────────────────────────────────────────────

class TestOnboardingFullFlow:
    """Tests for complete onboarding flow."""

    def test_full_onboarding_happy_path(self, ivr_processor: IVRProcessor, pending_user: User):
        """Complete onboarding flow should work end-to-end."""
        # Step 1: Start
        response = ivr_processor.process_onboarding(
            user=pending_user,
            current_step=None,
            user_input="hola"
        )
        assert response.next_step == "name"

        # Step 2: Name
        response = ivr_processor.process_onboarding(
            user=pending_user,
            current_step="name",
            user_input="Carlos García"
        )
        assert response.next_step == "currency"
        assert pending_user.full_name == "Carlos García"

        # Step 3: Currency
        response = ivr_processor.process_onboarding(
            user=pending_user,
            current_step="currency",
            user_input="2"  # COP
        )
        assert response.next_step == "country"
        assert pending_user.home_currency == "COP"

        # Step 4: Country
        response = ivr_processor.process_onboarding(
            user=pending_user,
            current_step="country",
            user_input="Colombia"
        )
        assert response.next_step == "timezone"
        assert pending_user.country == "CO"

        # Step 5: Timezone
        response = ivr_processor.process_onboarding(
            user=pending_user,
            current_step="timezone",
            user_input="1"  # Recommended
        )
        assert response.next_step == "confirm"
        assert pending_user.timezone == "America/Bogota"

        # Step 6: Confirm
        response = ivr_processor.process_onboarding(
            user=pending_user,
            current_step="confirm",
            user_input="1"
        )
        assert response.flow_complete is True
        assert pending_user.onboarding_status == "completed"
        assert pending_user.onboarding_completed_at is not None

        # Verify welcome message contains instructions
        assert "registrar gastos" in response.message.lower() or "gasto" in response.message.lower()
        assert "presupuesto" in response.message.lower()


# ─────────────────────────────────────────────────────────────────────────────
# IVRResponse Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestIVRResponse:
    """Tests for IVRResponse dataclass."""

    def test_default_values(self):
        """IVRResponse should have correct defaults."""
        response = IVRResponse(message="Test")
        
        assert response.message == "Test"
        assert response.next_step is None
        assert response.flow_complete is False
        assert response.data == {}
        assert response.error is None

    def test_with_all_values(self):
        """IVRResponse should accept all values."""
        response = IVRResponse(
            message="Test",
            next_step="currency",
            flow_complete=False,
            data={"name": "Harrison"},
            error=None
        )
        
        assert response.message == "Test"
        assert response.next_step == "currency"
        assert response.data["name"] == "Harrison"


# ─────────────────────────────────────────────────────────────────────────────
# Default Account Creation Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestDefaultAccountCreation:
    """Tests for automatic default account creation on onboarding completion."""

    def test_confirm_creates_default_cash_account(
        self, ivr_processor: IVRProcessor, user_at_confirm_step: User, db: Session
    ):
        """Confirming onboarding should create a default cash account."""
        response = ivr_processor.process_onboarding(
            user=user_at_confirm_step,
            current_step="confirm",
            user_input="1"
        )

        assert response.flow_complete is True
        
        # Verify account was created
        accounts = db.query(Account).filter(Account.user_id == user_at_confirm_step.id).all()
        assert len(accounts) == 1
        
        account = accounts[0]
        assert account.name == "Efectivo"
        assert account.account_type == "cash"
        assert account.currency == user_at_confirm_step.home_currency
        assert account.is_default is True
        assert account.is_active is True

    def test_confirm_returns_account_id_in_data(
        self, ivr_processor: IVRProcessor, user_at_confirm_step: User, db: Session
    ):
        """Onboarding response should include the created account ID."""
        response = ivr_processor.process_onboarding(
            user=user_at_confirm_step,
            current_step="confirm",
            user_input="si"
        )

        assert response.flow_complete is True
        assert "default_account_id" in response.data
        assert response.data["default_account_id"] is not None
        
        # Verify the ID matches the created account
        account = db.query(Account).filter(Account.user_id == user_at_confirm_step.id).first()
        assert str(account.id) == response.data["default_account_id"]

    def test_welcome_message_mentions_cash_account(
        self, ivr_processor: IVRProcessor, user_at_confirm_step: User
    ):
        """Welcome message should mention the created cash account."""
        response = ivr_processor.process_onboarding(
            user=user_at_confirm_step,
            current_step="confirm",
            user_input="1"
        )

        assert "efectivo" in response.message.lower()
        assert "método de pago" in response.message.lower() or "pago predeterminado" in response.message.lower()

    def test_does_not_create_duplicate_account(
        self, ivr_processor: IVRProcessor, user_at_confirm_step: User, db: Session
    ):
        """If user already has an account, onboarding should not create another."""
        # Create an existing account for the user
        existing_account = Account(
            user_id=user_at_confirm_step.id,
            name="Cuenta Existente",
            account_type="checking",
            currency="USD",
            is_default=True,
            is_active=True,
        )
        db.add(existing_account)
        db.commit()
        
        response = ivr_processor.process_onboarding(
            user=user_at_confirm_step,
            current_step="confirm",
            user_input="1"
        )

        assert response.flow_complete is True
        
        # Should still have only one account
        accounts = db.query(Account).filter(Account.user_id == user_at_confirm_step.id).all()
        assert len(accounts) == 1
        assert accounts[0].name == "Cuenta Existente"

    def test_full_flow_creates_account(
        self, ivr_processor: IVRProcessor, pending_user: User, db: Session
    ):
        """Complete onboarding flow should create default account."""
        # Run through entire flow
        ivr_processor.process_onboarding(pending_user, None, "hola")
        ivr_processor.process_onboarding(pending_user, "name", "María")
        ivr_processor.process_onboarding(pending_user, "currency", "MXN")
        ivr_processor.process_onboarding(pending_user, "country", "México")
        ivr_processor.process_onboarding(pending_user, "timezone", "1")
        response = ivr_processor.process_onboarding(pending_user, "confirm", "1")

        assert response.flow_complete is True
        
        # Verify account was created with correct currency
        account = db.query(Account).filter(Account.user_id == pending_user.id).first()
        assert account is not None
        assert account.name == "Efectivo"
        assert account.currency == "MXN"
        assert account.is_default is True


class TestOnboardingAlreadyCompleted:
    """Tests for safety check when user has already completed onboarding."""

    @pytest.fixture
    def completed_user(self, db: Session) -> User:
        """Create a user that has already completed onboarding."""
        user = User(
            id=uuid.uuid4(),
            phone_number="+573009998888",
            full_name="Usuario Completo",
            nickname="Usuario",
            home_currency="USD",
            country="CO",
            timezone="America/Bogota",
            preferred_language="es",
            onboarding_status="completed",
            onboarding_step=None,
            onboarding_completed_at=datetime.utcnow(),
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def test_completed_user_does_not_restart_onboarding(
        self, ivr_processor: IVRProcessor, completed_user: User
    ):
        """User who completed onboarding should not restart it."""
        response = ivr_processor.process_onboarding(
            user=completed_user,
            current_step=None,  # This is what triggers the issue
            user_input="configurar tarjeta"
        )

        # Should NOT restart onboarding
        assert response.flow_complete is True
        assert "ya está configurada" in response.message
        # User status should remain completed
        assert completed_user.onboarding_status == "completed"
        assert completed_user.onboarding_step is None

    def test_completed_user_with_random_message_does_not_restart(
        self, ivr_processor: IVRProcessor, completed_user: User
    ):
        """Any message to completed user should not restart onboarding."""
        response = ivr_processor.process_onboarding(
            user=completed_user,
            current_step=None,
            user_input="hola"
        )

        assert response.flow_complete is True
        assert "ya está configurada" in response.message
        assert completed_user.onboarding_status == "completed"

