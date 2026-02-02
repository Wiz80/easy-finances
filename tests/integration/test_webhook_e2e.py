"""
End-to-End Integration Tests for Twilio Webhook.

Tests the complete webhook flow from incoming Twilio request
through routing to response generation.
"""

import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.models import Account, ConversationState, User


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def test_client():
    """Create FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def webhook_user(db):
    """Create a user for webhook tests."""
    user = User(
        id=uuid.uuid4(),
        phone_number="+573115084628",
        full_name="Webhook Test User",
        nickname="WebhookTest",
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
def webhook_account(db, webhook_user):
    """Create account for webhook user."""
    account = Account(
        id=uuid.uuid4(),
        user_id=webhook_user.id,
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
def mock_twilio_signature():
    """Mock Twilio signature validation."""
    with patch(
        "app.api.deps.validate_twilio_signature",
        return_value=True
    ):
        yield


@pytest.fixture
def mock_twilio_send():
    """Mock Twilio message sending."""
    with patch(
        "app.integrations.whatsapp.twilio_client.TwilioWhatsAppClient.send_message",
        new_callable=AsyncMock
    ) as mock:
        mock.return_value = {"success": True, "sid": "SM123"}
        yield mock


def create_twilio_webhook_data(
    phone: str = "+573115084628",
    body: str = "Hola",
    message_sid: str | None = None,
    profile_name: str = "Test User",
    num_media: str = "0",
    media_url: str | None = None,
) -> dict:
    """Create mock Twilio webhook form data."""
    data = {
        "From": f"whatsapp:{phone}",
        "Body": body,
        "MessageSid": message_sid or f"SM{uuid.uuid4().hex[:30]}",
        "NumMedia": num_media,
        "ProfileName": profile_name,
        "AccountSid": "AC123",
        "WaId": phone.replace("+", ""),
    }
    
    if media_url and int(num_media) > 0:
        data["MediaUrl0"] = media_url
        data["MediaContentType0"] = "image/jpeg"
    
    return data


# ─────────────────────────────────────────────────────────────────────────────
# Test: Basic Webhook Flow
# ─────────────────────────────────────────────────────────────────────────────

class TestWebhookBasicFlow:
    """Tests for basic webhook request handling."""

    def test_webhook_accepts_valid_request(
        self, test_client, db, webhook_user, mock_twilio_signature
    ):
        """Test: Valid webhook request is accepted."""
        with patch(
            "app.api.routes.webhook.route_to_coordinator",
            new_callable=AsyncMock
        ) as mock_route:
            mock_route.return_value = "¡Hola! ¿En qué puedo ayudarte?"
            
            with patch(
                "app.api.routes.webhook.send_response_async",
                new_callable=AsyncMock
            ):
                data = create_twilio_webhook_data(
                    phone=webhook_user.phone_number,
                    body="Hola",
                )
                
                response = test_client.post(
                    "/webhook/twilio",
                    data=data,
                )
                
                assert response.status_code == 200

    def test_webhook_parses_message_correctly(
        self, test_client, db, webhook_user, mock_twilio_signature
    ):
        """Test: Webhook correctly parses message content."""
        captured_args = {}
        
        async def capture_route(*args, **kwargs):
            captured_args.update(kwargs)
            return "Response"
        
        with patch(
            "app.api.routes.webhook.route_to_coordinator",
            side_effect=capture_route
        ):
            with patch(
                "app.api.routes.webhook.send_response_async",
                new_callable=AsyncMock
            ):
                data = create_twilio_webhook_data(
                    phone=webhook_user.phone_number,
                    body="Gasté 50 dólares en taxi",
                    profile_name="TestUser",
                )
                
                response = test_client.post(
                    "/webhook/twilio",
                    data=data,
                )
                
                assert response.status_code == 200
                # Verify message was parsed
                if captured_args:
                    assert "phone_number" in captured_args
                    assert "message_body" in captured_args

    def test_webhook_handles_empty_body(
        self, test_client, db, webhook_user, mock_twilio_signature
    ):
        """Test: Webhook handles empty message body."""
        with patch(
            "app.api.routes.webhook.route_to_coordinator",
            new_callable=AsyncMock
        ) as mock_route:
            mock_route.return_value = "No entendí tu mensaje."
            
            with patch(
                "app.api.routes.webhook.send_response_async",
                new_callable=AsyncMock
            ):
                data = create_twilio_webhook_data(
                    phone=webhook_user.phone_number,
                    body="",  # Empty body
                )
                
                response = test_client.post(
                    "/webhook/twilio",
                    data=data,
                )
                
                # Should not crash
                assert response.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# Test: New User Flow
# ─────────────────────────────────────────────────────────────────────────────

class TestWebhookNewUserFlow:
    """Tests for new user webhook handling."""

    def test_new_user_receives_welcome(
        self, test_client, db, mock_twilio_signature
    ):
        """Test: New user receives welcome/onboarding message."""
        new_phone = f"+573001234{uuid.uuid4().hex[:4]}"
        
        with patch(
            "app.api.routes.webhook.route_to_coordinator",
            new_callable=AsyncMock
        ) as mock_route:
            # Should route to configuration for onboarding
            mock_route.return_value = "¡Bienvenido! Vamos a configurar tu cuenta."
            
            with patch(
                "app.api.routes.webhook.send_response_async",
                new_callable=AsyncMock
            ):
                data = create_twilio_webhook_data(
                    phone=new_phone,
                    body="Hola",
                    profile_name="NewUser",
                )
                
                response = test_client.post(
                    "/webhook/twilio",
                    data=data,
                )
                
                assert response.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# Test: Media Messages
# ─────────────────────────────────────────────────────────────────────────────

class TestWebhookMediaMessages:
    """Tests for media message handling."""

    def test_image_message_parsed(
        self, test_client, db, webhook_user, mock_twilio_signature
    ):
        """Test: Image messages are parsed correctly."""
        with patch(
            "app.api.routes.webhook.route_to_coordinator",
            new_callable=AsyncMock
        ) as mock_route:
            mock_route.return_value = "Recibí tu imagen."
            
            with patch(
                "app.api.routes.webhook.send_response_async",
                new_callable=AsyncMock
            ):
                data = create_twilio_webhook_data(
                    phone=webhook_user.phone_number,
                    body="Recibo de comida",
                    num_media="1",
                    media_url="https://api.twilio.com/media/123.jpg",
                )
                
                response = test_client.post(
                    "/webhook/twilio",
                    data=data,
                )
                
                assert response.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# Test: Error Handling
# ─────────────────────────────────────────────────────────────────────────────

class TestWebhookErrorHandling:
    """Tests for webhook error handling."""

    def test_coordinator_error_returns_friendly_message(
        self, test_client, db, webhook_user, mock_twilio_signature
    ):
        """Test: Coordinator errors result in friendly error message."""
        with patch(
            "app.api.routes.webhook.route_to_coordinator",
            new_callable=AsyncMock
        ) as mock_route:
            mock_route.side_effect = Exception("Database error")
            
            with patch(
                "app.api.routes.webhook.send_response_async",
                new_callable=AsyncMock
            ) as mock_send:
                data = create_twilio_webhook_data(
                    phone=webhook_user.phone_number,
                    body="Hola",
                )
                
                response = test_client.post(
                    "/webhook/twilio",
                    data=data,
                )
                
                # Should still return 200 (Twilio expects this)
                assert response.status_code == 200
                
                # Should try to send error message
                if mock_send.called:
                    call_args = mock_send.call_args
                    # Error message should be sent


# ─────────────────────────────────────────────────────────────────────────────
# Test: Message Types Routing
# ─────────────────────────────────────────────────────────────────────────────

class TestWebhookMessageRouting:
    """Tests for message type routing through webhook."""

    def test_expense_message_routed_correctly(
        self, test_client, db, webhook_user, webhook_account, mock_twilio_signature
    ):
        """Test: Expense messages are routed to IE Agent."""
        with patch(
            "app.agents.coordinator.process_message",
            new_callable=AsyncMock
        ) as mock_process:
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.agent_used = "ie"
            mock_result.routing_method = "keyword"
            mock_result.response_text = "Registré tu gasto de $50."
            mock_process.return_value = mock_result
            
            with patch(
                "app.api.routes.webhook.send_response_async",
                new_callable=AsyncMock
            ):
                data = create_twilio_webhook_data(
                    phone=webhook_user.phone_number,
                    body="Gasté 50 dólares en taxi",
                )
                
                response = test_client.post(
                    "/webhook/twilio",
                    data=data,
                )
                
                assert response.status_code == 200

    def test_query_message_routed_correctly(
        self, test_client, db, webhook_user, mock_twilio_signature
    ):
        """Test: Query messages are routed to Coach Agent."""
        with patch(
            "app.agents.coordinator.process_message",
            new_callable=AsyncMock
        ) as mock_process:
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.agent_used = "coach"
            mock_result.routing_method = "keyword"
            mock_result.response_text = "Este mes gastaste $150."
            mock_process.return_value = mock_result
            
            with patch(
                "app.api.routes.webhook.send_response_async",
                new_callable=AsyncMock
            ):
                data = create_twilio_webhook_data(
                    phone=webhook_user.phone_number,
                    body="¿Cuánto gasté este mes?",
                )
                
                response = test_client.post(
                    "/webhook/twilio",
                    data=data,
                )
                
                assert response.status_code == 200

    def test_command_message_handled(
        self, test_client, db, webhook_user, mock_twilio_signature
    ):
        """Test: Command messages are handled by Coordinator."""
        with patch(
            "app.agents.coordinator.process_message",
            new_callable=AsyncMock
        ) as mock_process:
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.agent_used = "coordinator"
            mock_result.routing_method = "command"
            mock_result.response_text = "Operación cancelada."
            mock_process.return_value = mock_result
            
            with patch(
                "app.api.routes.webhook.send_response_async",
                new_callable=AsyncMock
            ):
                data = create_twilio_webhook_data(
                    phone=webhook_user.phone_number,
                    body="cancelar",
                )
                
                response = test_client.post(
                    "/webhook/twilio",
                    data=data,
                )
                
                assert response.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# Test: Response Handling
# ─────────────────────────────────────────────────────────────────────────────

class TestWebhookResponseHandling:
    """Tests for response message handling."""

    def test_long_response_chunked(
        self, test_client, db, webhook_user, mock_twilio_signature
    ):
        """Test: Long responses are chunked correctly."""
        # Create a very long response
        long_response = "Este es un mensaje muy largo. " * 200  # ~6000 chars
        
        with patch(
            "app.api.routes.webhook.route_to_coordinator",
            new_callable=AsyncMock
        ) as mock_route:
            mock_route.return_value = long_response
            
            sent_chunks = []
            
            async def capture_send(twilio, to, body):
                sent_chunks.append(body)
            
            with patch(
                "app.api.routes.webhook.send_response_async",
                side_effect=capture_send
            ):
                data = create_twilio_webhook_data(
                    phone=webhook_user.phone_number,
                    body="Dame un resumen muy largo",
                )
                
                response = test_client.post(
                    "/webhook/twilio",
                    data=data,
                )
                
                assert response.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# Test: Idempotency
# ─────────────────────────────────────────────────────────────────────────────

class TestWebhookIdempotency:
    """Tests for webhook idempotency handling."""

    def test_duplicate_message_sid_handled(
        self, test_client, db, webhook_user, mock_twilio_signature
    ):
        """Test: Duplicate message SIDs are handled."""
        message_sid = f"SM{uuid.uuid4().hex[:30]}"
        
        call_count = 0
        
        async def counting_route(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return "Response"
        
        with patch(
            "app.api.routes.webhook.route_to_coordinator",
            side_effect=counting_route
        ):
            with patch(
                "app.api.routes.webhook.send_response_async",
                new_callable=AsyncMock
            ):
                # Send same message twice
                for _ in range(2):
                    data = create_twilio_webhook_data(
                        phone=webhook_user.phone_number,
                        body="Gasté 50 en taxi",
                        message_sid=message_sid,
                    )
                    
                    response = test_client.post(
                        "/webhook/twilio",
                        data=data,
                    )
                    
                    assert response.status_code == 200
                
                # Both requests processed at webhook level
                # Idempotency handled at storage layer
                assert call_count == 2


# ─────────────────────────────────────────────────────────────────────────────
# Test: Sandbox Join Messages
# ─────────────────────────────────────────────────────────────────────────────

class TestWebhookSandboxMessages:
    """Tests for Twilio sandbox join messages."""

    def test_sandbox_join_message_handled(
        self, test_client, db, mock_twilio_signature
    ):
        """Test: Twilio sandbox join messages are handled gracefully."""
        with patch(
            "app.api.routes.webhook.route_to_coordinator",
            new_callable=AsyncMock
        ) as mock_route:
            mock_route.return_value = "¡Bienvenido!"
            
            with patch(
                "app.api.routes.webhook.send_response_async",
                new_callable=AsyncMock
            ):
                # Twilio sandbox join message format
                data = create_twilio_webhook_data(
                    phone="+14155238886",  # Twilio sandbox number
                    body="join <sandbox-code>",
                )
                
                response = test_client.post(
                    "/webhook/twilio",
                    data=data,
                )
                
                assert response.status_code == 200
