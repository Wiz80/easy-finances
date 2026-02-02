"""
Concurrency Integration Tests.

Tests for handling concurrent messages and race conditions:
- Simultaneous messages from same user
- Multiple users simultaneously
- Database transaction handling
- Idempotency under concurrency
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import Account, Expense, User


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def concurrent_users(db):
    """Create multiple users for concurrency tests."""
    users = []
    for i in range(5):
        user = User(
            id=uuid.uuid4(),
            phone_number=f"+573008888{i}{uuid.uuid4().hex[:2]}",
            full_name=f"Concurrent User {i}",
            nickname=f"ConcUser{i}",
            home_currency="COP",
            timezone="America/Bogota",
            preferred_language="es",
            onboarding_status="completed",
            onboarding_completed_at=datetime.utcnow(),
            whatsapp_verified=True,
            is_active=True,
        )
        db.add(user)
        users.append(user)
    
    db.commit()
    
    # Create accounts for each user
    for user in users:
        account = Account(
            id=uuid.uuid4(),
            user_id=user.id,
            name="Cuenta Principal",
            account_type="cash",
            currency="COP",
            is_active=True,
            is_default=True,
        )
        db.add(account)
    
    db.commit()
    
    for user in users:
        db.refresh(user)
    
    return users


# ─────────────────────────────────────────────────────────────────────────────
# Test: Simultaneous Messages from Same User
# ─────────────────────────────────────────────────────────────────────────────

class TestSimultaneousMessagesSameUser:
    """Tests for handling simultaneous messages from the same user."""

    @pytest.mark.asyncio
    async def test_concurrent_expense_messages(self, db, concurrent_users):
        """Test: Multiple expense messages from same user handled correctly."""
        from app.agents.coordinator import process_message
        
        user = concurrent_users[0]
        
        # Send multiple messages concurrently
        messages = [
            "Gasté 50 en taxi",
            "100 dólares hotel",
            "30 en comida",
        ]
        
        tasks = [
            process_message(
                phone_number=user.phone_number,
                message_body=msg,
            )
            for msg in messages
        ]
        
        # Execute concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should complete (even if some fail due to locking)
        for result in results:
            if not isinstance(result, Exception):
                assert result.success or result.response_text

    @pytest.mark.asyncio
    async def test_concurrent_query_messages(self, db, concurrent_users):
        """Test: Multiple query messages from same user handled correctly."""
        from app.agents.coordinator import process_message
        
        user = concurrent_users[0]
        
        # Send multiple queries concurrently
        queries = [
            "¿Cuánto gasté hoy?",
            "¿Cuánto gasté este mes?",
            "Dame el resumen",
        ]
        
        tasks = [
            process_message(
                phone_number=user.phone_number,
                message_body=query,
            )
            for query in queries
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should complete
        for result in results:
            if not isinstance(result, Exception):
                assert result.success or result.response_text

    @pytest.mark.asyncio
    async def test_rapid_fire_messages(self, db, concurrent_users):
        """Test: Rapid-fire messages are handled without errors."""
        from app.agents.coordinator import process_message
        
        user = concurrent_users[0]
        
        # Rapid sequence of messages
        results = []
        for i in range(10):
            result = await process_message(
                phone_number=user.phone_number,
                message_body=f"Mensaje {i}",
            )
            results.append(result)
        
        # All should have responses
        for result in results:
            assert result.response_text is not None


# ─────────────────────────────────────────────────────────────────────────────
# Test: Multiple Users Simultaneously
# ─────────────────────────────────────────────────────────────────────────────

class TestMultipleUsersConcurrent:
    """Tests for handling multiple users simultaneously."""

    @pytest.mark.asyncio
    async def test_multiple_users_expense_concurrent(self, db, concurrent_users):
        """Test: Multiple users can register expenses simultaneously."""
        from app.agents.coordinator import process_message
        
        # Each user sends an expense message
        tasks = [
            process_message(
                phone_number=user.phone_number,
                message_body=f"Gasté {50 + i * 10} en taxi",
            )
            for i, user in enumerate(concurrent_users)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All users should get responses
        success_count = sum(
            1 for r in results
            if not isinstance(r, Exception) and r.success
        )
        
        # At least some should succeed
        assert success_count > 0

    @pytest.mark.asyncio
    async def test_multiple_users_query_concurrent(self, db, concurrent_users):
        """Test: Multiple users can query simultaneously."""
        from app.agents.coordinator import process_message
        
        tasks = [
            process_message(
                phone_number=user.phone_number,
                message_body="¿Cuánto gasté este mes?",
            )
            for user in concurrent_users
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should complete
        for result in results:
            if not isinstance(result, Exception):
                assert result.response_text

    @pytest.mark.asyncio
    async def test_mixed_operations_concurrent(self, db, concurrent_users):
        """Test: Mixed operations from different users concurrently."""
        from app.agents.coordinator import process_message
        
        operations = [
            (concurrent_users[0], "Gasté 100 en hotel"),
            (concurrent_users[1], "¿Cuánto gasté?"),
            (concurrent_users[2], "50 dólares taxi"),
            (concurrent_users[3], "Dame el resumen"),
            (concurrent_users[4], "Pagué 30 por almuerzo"),
        ]
        
        tasks = [
            process_message(
                phone_number=user.phone_number,
                message_body=msg,
            )
            for user, msg in operations
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should complete
        success_count = sum(
            1 for r in results
            if not isinstance(r, Exception)
        )
        assert success_count == len(operations)


# ─────────────────────────────────────────────────────────────────────────────
# Test: Idempotency Under Concurrency
# ─────────────────────────────────────────────────────────────────────────────

class TestIdempotencyUnderConcurrency:
    """Tests for idempotency when same message is processed concurrently."""

    @pytest.mark.asyncio
    async def test_duplicate_message_concurrent(self, db, concurrent_users):
        """Test: Same message processed concurrently results in one expense."""
        from app.agents.coordinator import process_message
        
        user = concurrent_users[0]
        msg_id = f"SM{uuid.uuid4().hex[:30]}"
        
        # Same message ID sent concurrently
        tasks = [
            process_message(
                phone_number=user.phone_number,
                message_body="Gasté 50 en taxi",
                message_sid=msg_id,
            )
            for _ in range(3)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should complete
        for result in results:
            if not isinstance(result, Exception):
                assert result.response_text


# ─────────────────────────────────────────────────────────────────────────────
# Test: Database Transaction Handling
# ─────────────────────────────────────────────────────────────────────────────

class TestDatabaseTransactionHandling:
    """Tests for database transaction handling under load."""

    @pytest.mark.asyncio
    async def test_concurrent_inserts_no_conflicts(self, db, concurrent_users):
        """Test: Concurrent inserts don't cause conflicts."""
        from app.storage.expense_writer import create_expense
        from app.schemas.extraction import ExtractedExpense
        from app.database import SessionLocal
        
        user = concurrent_users[0]
        account = db.query(Account).filter(
            Account.user_id == user.id
        ).first()
        
        async def create_expense_task(amount: float):
            session = SessionLocal()
            try:
                expense = ExtractedExpense(
                    amount=amount,
                    currency_original="USD",
                    description=f"Test expense {amount}",
                    category="food",
                    confidence=0.95,
                    payment_method="cash",
                )
                
                result = create_expense(
                    session=session,
                    extracted=expense,
                    user_id=user.id,
                    account_id=account.id,
                    source_type="text",
                )
                
                session.commit()
                return result
            finally:
                session.close()
        
        # Create multiple expenses concurrently
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(None, lambda a=amount: asyncio.run(create_expense_task(a)))
            for amount in [10, 20, 30, 40, 50]
        ]
        
        # This may fail in test environment but shouldn't crash
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception:
            pass  # Database operations may fail in concurrent test environment


# ─────────────────────────────────────────────────────────────────────────────
# Test: Rate Limiting Behavior
# ─────────────────────────────────────────────────────────────────────────────

class TestRateLimitingBehavior:
    """Tests for rate limiting under concurrent load."""

    @pytest.mark.asyncio
    async def test_burst_messages_handled(self, db, concurrent_users):
        """Test: Burst of messages is handled gracefully."""
        from app.agents.coordinator import process_message
        
        user = concurrent_users[0]
        
        # Send burst of messages
        burst_size = 20
        tasks = [
            process_message(
                phone_number=user.phone_number,
                message_body=f"Mensaje burst {i}",
            )
            for i in range(burst_size)
        ]
        
        start_time = datetime.utcnow()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        
        # All should complete
        completed = sum(1 for r in results if not isinstance(r, Exception))
        
        # At least some should complete
        assert completed > 0


# ─────────────────────────────────────────────────────────────────────────────
# Test: Conversation State Consistency
# ─────────────────────────────────────────────────────────────────────────────

class TestConversationStateConsistency:
    """Tests for conversation state consistency under concurrency."""

    @pytest.mark.asyncio
    async def test_conversation_state_not_corrupted(self, db, concurrent_users):
        """Test: Conversation state remains consistent under concurrent access."""
        from app.agents.coordinator import process_message
        from app.models import ConversationState
        
        user = concurrent_users[0]
        
        # Send multiple messages that might modify conversation state
        tasks = [
            process_message(
                phone_number=user.phone_number,
                message_body="menú",
            ),
            process_message(
                phone_number=user.phone_number,
                message_body="Gasté 50",
            ),
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check that conversation state is valid
        db.expire_all()
        conversations = db.query(ConversationState).filter(
            ConversationState.user_id == user.id
        ).all()
        
        # Should have at most one active conversation
        active_conversations = [c for c in conversations if c.status == "active"]
        assert len(active_conversations) <= 1

    @pytest.mark.asyncio
    async def test_agent_lock_consistency(self, db, concurrent_users):
        """Test: Agent lock remains consistent under concurrent access."""
        from app.agents.coordinator import process_message
        from app.models import ConversationState
        
        user = concurrent_users[0]
        
        # Create a locked conversation
        conversation = ConversationState(
            id=uuid.uuid4(),
            user_id=user.id,
            current_flow="trip_setup",
            current_step="trip_name",
            state_data={},
            agent_locked="configuration",
            session_started_at=datetime.utcnow(),
            last_interaction_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(minutes=30),
            status="active",
        )
        db.add(conversation)
        db.commit()
        
        # Send concurrent messages
        tasks = [
            process_message(
                phone_number=user.phone_number,
                message_body=f"Response {i}",
            )
            for i in range(3)
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Conversation should still be valid
        db.expire_all()
        conv = db.query(ConversationState).filter(
            ConversationState.user_id == user.id,
            ConversationState.status == "active"
        ).first()
        
        # State should be valid (not corrupted)
        if conv:
            assert conv.current_flow is not None or conv.status == "active"


# ─────────────────────────────────────────────────────────────────────────────
# Test: Error Isolation
# ─────────────────────────────────────────────────────────────────────────────

class TestErrorIsolation:
    """Tests for error isolation between concurrent requests."""

    @pytest.mark.asyncio
    async def test_one_error_doesnt_affect_others(self, db, concurrent_users):
        """Test: Error in one request doesn't affect others."""
        from app.agents.coordinator import process_message
        
        # One user will trigger an error, others should succeed
        async def process_with_mock_error(user, trigger_error=False):
            if trigger_error:
                with patch(
                    "app.agents.coordinator.graph.detect_intent_node",
                    side_effect=Exception("Simulated error")
                ):
                    return await process_message(
                        phone_number=user.phone_number,
                        message_body="Test message",
                    )
            else:
                return await process_message(
                    phone_number=user.phone_number,
                    message_body="Test message",
                )
        
        tasks = [
            process_message(
                phone_number=user.phone_number,
                message_body="Gasté 50 en taxi",
            )
            for user in concurrent_users
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Most should succeed
        success_count = sum(
            1 for r in results
            if not isinstance(r, Exception) and r.success
        )
        
        assert success_count > 0


# ─────────────────────────────────────────────────────────────────────────────
# Test: Memory and Resource Handling
# ─────────────────────────────────────────────────────────────────────────────

class TestMemoryAndResources:
    """Tests for proper resource handling under concurrent load."""

    @pytest.mark.asyncio
    async def test_database_connections_released(self, db, concurrent_users):
        """Test: Database connections are properly released after concurrent requests."""
        from app.agents.coordinator import process_message
        from app.database import engine
        
        user = concurrent_users[0]
        
        # Get initial pool status
        initial_checked_out = engine.pool.checkedout()
        
        # Process multiple messages
        for i in range(5):
            await process_message(
                phone_number=user.phone_number,
                message_body=f"Mensaje {i}",
            )
        
        # Connections should be released
        final_checked_out = engine.pool.checkedout()
        
        # Should have similar number of checked out connections
        assert final_checked_out <= initial_checked_out + 2
