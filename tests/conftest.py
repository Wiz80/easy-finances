"""
Pytest configuration and fixtures for the Finanzas Personales test suite.

Provides:
- Database fixtures (session, test data)
- User/Account/Trip/Budget fixtures
- Mocking utilities
"""

import os
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Set test environment before importing app modules
os.environ["ENVIRONMENT"] = "development"  # Use development for tests
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("TWILIO_ACCOUNT_SID", "test-sid")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "test-token")
os.environ.setdefault("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
# Don't set DATABASE_URL - use the environment variable or default to PostgreSQL

from app.database import Base
from app.models import (
    Account,
    Budget,
    BudgetAllocation,
    BudgetFundingSource,
    Card,
    Category,
    ConversationState,
    Trip,
    User,
)


# ─────────────────────────────────────────────────────────────────────────────
# Database Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def engine():
    """
    Create a test database engine using PostgreSQL.
    
    Uses the TEST_DATABASE_URL environment variable or constructs from
    individual POSTGRES_* environment variables.
    
    Environment variables:
        TEST_DATABASE_URL: Full database URL (takes precedence)
        POSTGRES_USER: Database user (default: finanzas_user)
        POSTGRES_PASSWORD: Database password (default: finanzas_password)
        POSTGRES_HOST: Database host (default: localhost)
        POSTGRES_PORT: Database port (default: 5432)
        POSTGRES_TEST_DB: Test database name (default: finanzas_test)
    """
    db_url = os.environ.get("TEST_DATABASE_URL")
    
    if not db_url:
        user = os.environ.get("POSTGRES_USER", "finanzas_user")
        password = os.environ.get("POSTGRES_PASSWORD", "finanzas_password")
        host = os.environ.get("POSTGRES_HOST", "localhost")
        port = os.environ.get("POSTGRES_PORT", "5432")
        db_name = os.environ.get("POSTGRES_TEST_DB", "finanzas_test")
        db_url = f"postgresql://{user}:{password}@{host}:{port}/{db_name}"
    
    engine = create_engine(db_url, echo=False)
    
    # Create all tables for tests (if they don't exist)
    Base.metadata.create_all(engine)
    
    yield engine
    
    # Note: We don't drop tables after tests to avoid issues with FK constraints.
    # Use a fresh test database or run migrations for cleanup.


@pytest.fixture(scope="function")
def db(engine) -> Generator[Session, None, None]:
    """
    Create a fresh database session for each test.
    
    Rolls back all changes after the test completes.
    """
    connection = engine.connect()
    transaction = connection.begin()
    
    SessionLocal = sessionmaker(bind=connection)
    session = SessionLocal()
    
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture(scope="function")
def db_with_categories(db: Session) -> Session:
    """Database session with seeded categories."""
    categories = [
        Category(
            id=uuid.uuid4(),
            name="Food",
            slug="food",
            description="Food and dining",
            icon="🍔",
            sort_order=1,
        ),
        Category(
            id=uuid.uuid4(),
            name="Lodging",
            slug="lodging",
            description="Accommodation",
            icon="🏨",
            sort_order=2,
        ),
        Category(
            id=uuid.uuid4(),
            name="Transport",
            slug="transport",
            description="Transportation",
            icon="🚕",
            sort_order=3,
        ),
        Category(
            id=uuid.uuid4(),
            name="Tourism",
            slug="tourism",
            description="Tourism and activities",
            icon="🎭",
            sort_order=4,
        ),
        Category(
            id=uuid.uuid4(),
            name="Gifts",
            slug="gifts",
            description="Gifts and souvenirs",
            icon="🎁",
            sort_order=5,
        ),
        Category(
            id=uuid.uuid4(),
            name="Miscellaneous",
            slug="misc",
            description="Other expenses",
            icon="⚡",
            sort_order=6,
        ),
    ]
    
    for cat in categories:
        db.add(cat)
    db.commit()
    
    return db


# ─────────────────────────────────────────────────────────────────────────────
# User Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_user(db: Session) -> User:
    """Create a sample user for testing."""
    user = User(
        id=uuid.uuid4(),
        phone_number="+573115084628",
        full_name="Test User",
        nickname="Test",
        home_currency="COP",
        timezone="America/Bogota",
        preferred_language="es",
        onboarding_status="completed",
        onboarding_completed_at=datetime.utcnow(),
        whatsapp_verified=True,
        whatsapp_verified_at=datetime.utcnow(),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def new_user(db: Session) -> User:
    """Create a new user that needs onboarding."""
    user = User(
        id=uuid.uuid4(),
        phone_number="+573001234567",
        full_name="Usuario",
        home_currency="USD",
        timezone="America/Mexico_City",
        preferred_language="es",
        onboarding_status="pending",
        whatsapp_verified=True,
        whatsapp_verified_at=datetime.utcnow(),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ─────────────────────────────────────────────────────────────────────────────
# Account & Card Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_account(db: Session, sample_user: User) -> Account:
    """Create a sample account for testing."""
    account = Account(
        id=uuid.uuid4(),
        user_id=sample_user.id,
        name="Cuenta Principal",
        account_type="checking",
        currency="COP",
        institution="Bancolombia",
        is_active=True,
        is_default=True,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@pytest.fixture
def sample_card(db: Session, sample_account: Account) -> Card:
    """Create a sample card for testing."""
    card = Card(
        id=uuid.uuid4(),
        account_id=sample_account.id,
        name="Visa Travel",
        card_type="credit",
        network="visa",
        last_four_digits="4532",
        issuer="Bancolombia",
        is_active=True,
        is_default=True,
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


# ─────────────────────────────────────────────────────────────────────────────
# Trip Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_trip(db: Session, sample_user: User) -> Trip:
    """Create a sample trip for testing."""
    trip = Trip(
        id=uuid.uuid4(),
        user_id=sample_user.id,
        name="Ecuador Adventure",
        description="Trip to Ecuador",
        start_date=date.today(),
        end_date=date.today() + timedelta(days=15),
        destination_country="EC",
        destination_city="Quito",
        local_currency="USD",
        timezone="America/Guayaquil",
        is_active=True,
        status="active",
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)
    
    # Set as current trip
    sample_user.current_trip_id = trip.id
    sample_user.travel_mode_active = True
    db.commit()
    
    return trip


# ─────────────────────────────────────────────────────────────────────────────
# Budget Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_budget(db_with_categories: Session, sample_user: User, sample_trip: Trip) -> Budget:
    """Create a sample budget with allocations for testing."""
    db = db_with_categories
    
    budget = Budget(
        id=uuid.uuid4(),
        user_id=sample_user.id,
        trip_id=sample_trip.id,
        name="Ecuador Budget",
        start_date=sample_trip.start_date,
        end_date=sample_trip.end_date,
        total_amount=Decimal("5000000"),
        currency="COP",
        status="active",
    )
    db.add(budget)
    db.flush()
    
    # Get categories
    food_cat = db.query(Category).filter(Category.slug == "food").first()
    lodging_cat = db.query(Category).filter(Category.slug == "lodging").first()
    
    if food_cat:
        alloc1 = BudgetAllocation(
            budget_id=budget.id,
            category_id=food_cat.id,
            allocated_amount=Decimal("1500000"),
            currency="COP",
            spent_amount=Decimal("0"),
            alert_threshold_percent=80,
        )
        db.add(alloc1)
    
    if lodging_cat:
        alloc2 = BudgetAllocation(
            budget_id=budget.id,
            category_id=lodging_cat.id,
            allocated_amount=Decimal("2000000"),
            currency="COP",
            spent_amount=Decimal("0"),
            alert_threshold_percent=80,
        )
        db.add(alloc2)
    
    db.commit()
    db.refresh(budget)
    return budget


# ─────────────────────────────────────────────────────────────────────────────
# Conversation Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_conversation(db: Session, sample_user: User) -> ConversationState:
    """Create a sample active conversation for testing."""
    conversation = ConversationState(
        id=uuid.uuid4(),
        user_id=sample_user.id,
        current_flow="trip_setup",
        current_step="trip_name",
        state_data={"partial": "data"},
        session_started_at=datetime.utcnow(),
        last_interaction_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(minutes=30),
        status="active",
        message_count=2,
        message_history=[
            {"role": "user", "content": "Nuevo viaje", "timestamp": datetime.utcnow().isoformat()},
            {"role": "bot", "content": "¿Cómo quieres llamar al viaje?", "timestamp": datetime.utcnow().isoformat()},
        ],
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@pytest.fixture
def onboarding_conversation(db: Session, new_user: User) -> ConversationState:
    """Create an onboarding conversation for a new user."""
    conversation = ConversationState(
        id=uuid.uuid4(),
        user_id=new_user.id,
        current_flow="onboarding",
        current_step="name",
        state_data={},
        session_started_at=datetime.utcnow(),
        last_interaction_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(minutes=30),
        status="active",
        message_count=1,
        message_history=[
            {"role": "bot", "content": "¡Hola! ¿Cómo te llamas?", "timestamp": datetime.utcnow().isoformat()},
        ],
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


# ─────────────────────────────────────────────────────────────────────────────
# Mock Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_openai(mocker):
    """Mock OpenAI API calls."""
    mock = mocker.patch("langchain_openai.ChatOpenAI")
    mock_instance = mocker.MagicMock()
    mock_instance.invoke.return_value.content = '{"intent": "unknown", "entities": {}, "confidence": 0.5}'
    mock.return_value = mock_instance
    return mock


@pytest.fixture
def mock_twilio(mocker):
    """Mock Twilio API calls."""
    mock = mocker.patch("app.integrations.whatsapp.twilio_client.TwilioWhatsAppClient")
    mock_instance = mocker.MagicMock()
    mock_instance.send_message.return_value = {"sid": "SM123", "status": "queued"}
    mock.return_value = mock_instance
    return mock


# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────────────────────

def create_test_user(
    db: Session,
    phone: str = "+573001234567",
    name: str = "Test User",
    onboarding_complete: bool = True,
) -> User:
    """Helper to create a test user with custom parameters."""
    user = User(
        id=uuid.uuid4(),
        phone_number=phone,
        full_name=name,
        nickname=name.split()[0],
        home_currency="COP",
        timezone="America/Bogota",
        preferred_language="es",
        onboarding_status="completed" if onboarding_complete else "pending",
        onboarding_completed_at=datetime.utcnow() if onboarding_complete else None,
        whatsapp_verified=True,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

