#!/usr/bin/env python3
"""
Manual testing script for the Coordinator Agent.

This script tests the Coordinator Agent end-to-end, simulating
WhatsApp messages and verifying routing to the correct agents.

Run with:
    python tests-manual/test_coordinator_agent.py

Or debug with VSCode using the "Test Coordinator Agent" configuration.

Test scenarios:
1. New user → Configuration Agent (onboarding)
2. Expense message → IE Agent
3. Query message → Coach Agent
4. Coordinator commands (cancel, menu, help)
5. Sticky sessions (maintaining agent lock)
6. Intent change detection
"""

import asyncio
import sys
from pathlib import Path
from uuid import uuid4

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# ─────────────────────────────────────────────────────────────────────────────
# Test Configuration
# ─────────────────────────────────────────────────────────────────────────────

# Test phone number (use a unique one for testing)
TEST_PHONE = "+573001234567"
TEST_PROFILE_NAME = "Test User"


# ─────────────────────────────────────────────────────────────────────────────
# Test Utilities
# ─────────────────────────────────────────────────────────────────────────────

def print_header(title: str) -> None:
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_result(result, message: str) -> None:
    """Print test result in a readable format."""
    print(f"\n📱 User: {message}")
    print(f"🤖 Bot: {result.response_text[:200]}..." if len(result.response_text) > 200 else f"🤖 Bot: {result.response_text}")
    print(f"   ├─ Agent: {result.agent_used}")
    print(f"   ├─ Method: {result.routing_method}")
    print(f"   ├─ Success: {result.success}")
    if result.errors:
        print(f"   └─ Errors: {result.errors}")


async def send_message(message: str, phone: str = TEST_PHONE) -> "CoordinatorResult":
    """Send a message through the Coordinator."""
    from app.agents.coordinator import process_message
    
    result = await process_message(
        phone_number=phone,
        message_body=message,
        message_type="text",
        profile_name=TEST_PROFILE_NAME,
    )
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Test: Intent Detection (Fast Path)
# ─────────────────────────────────────────────────────────────────────────────

async def test_intent_detection():
    """Test keyword-based intent detection without full agent execution."""
    print_header("Test: Intent Detection (Fast Path)")
    
    from app.agents.common.intents import detect_intent_fast, AgentType
    
    test_cases = [
        # (message, expected_agent)
        ("Gasté 50 soles en taxi", AgentType.IE),
        ("Pagué 100 dólares por el hotel", AgentType.IE),
        ("¿Cuánto gasté este mes?", AgentType.COACH),
        ("Muéstrame el resumen", AgentType.COACH),
        ("Quiero configurar un viaje", AgentType.CONFIGURATION),
        ("Crear nuevo viaje", AgentType.CONFIGURATION),
        ("cancelar", AgentType.COORDINATOR),
        ("ayuda", AgentType.COORDINATOR),
        ("Hola", None),  # Ambiguous
    ]
    
    passed = 0
    failed = 0
    
    for message, expected in test_cases:
        result = detect_intent_fast(message)
        status = "✅" if result == expected else "❌"
        
        if result == expected:
            passed += 1
        else:
            failed += 1
        
        print(f"{status} '{message}' → {result} (expected: {expected})")
    
    print(f"\n📊 Results: {passed} passed, {failed} failed")
    return failed == 0


# ─────────────────────────────────────────────────────────────────────────────
# Test: Coordinator Commands
# ─────────────────────────────────────────────────────────────────────────────

async def test_coordinator_commands():
    """Test special coordinator commands."""
    print_header("Test: Coordinator Commands")
    
    commands = [
        ("cancelar", "cancel"),
        ("menu", "menu"),
        ("ayuda", "help"),
    ]
    
    for message, expected_action in commands:
        result = await send_message(message)
        print_result(result, message)
        
        # Verify it was handled by coordinator
        assert result.agent_used == "coordinator", f"Expected coordinator, got {result.agent_used}"
        assert result.success, f"Command failed: {result.errors}"
    
    print("\n✅ All coordinator commands work!")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Test: Routing to IE Agent
# ─────────────────────────────────────────────────────────────────────────────

async def test_expense_routing():
    """Test routing expense messages to IE Agent."""
    print_header("Test: Expense Routing → IE Agent")
    
    # Use a unique phone to avoid state from other tests
    test_phone = f"+5730012345{uuid4().hex[:2]}"
    
    # First, we need to complete onboarding or the user will go to configuration
    # For this test, we'll check that expense keywords are detected correctly
    
    from app.agents.coordinator.router import detect_agent_for_message
    from app.agents.common.intents import AgentType
    
    expense_messages = [
        "Gasté 50 soles en taxi",
        "Pagué 30 dólares por el almuerzo",
        "Compré comida por 25 pesos",
        "100 soles uber",
    ]
    
    for message in expense_messages:
        result = await detect_agent_for_message(
            message=message,
            onboarding_completed=True,  # Simulate completed onboarding
            has_active_trip=True,
        )
        
        print(f"📝 '{message}'")
        print(f"   → Agent: {result.agent.value}, Method: {result.method}, Confidence: {result.confidence:.2f}")
        
        assert result.agent == AgentType.IE, f"Expected IE, got {result.agent}"
    
    print("\n✅ All expense messages route to IE Agent!")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Test: Routing to Coach Agent
# ─────────────────────────────────────────────────────────────────────────────

async def test_query_routing():
    """Test routing query messages to Coach Agent."""
    print_header("Test: Query Routing → Coach Agent")
    
    from app.agents.coordinator.router import detect_agent_for_message
    from app.agents.common.intents import AgentType
    
    query_messages = [
        "¿Cuánto gasté este mes?",
        "¿Cómo voy con el presupuesto?",
        "Muéstrame el resumen de gastos",
        "¿Qué gasté ayer?",
    ]
    
    for message in query_messages:
        result = await detect_agent_for_message(
            message=message,
            onboarding_completed=True,
            has_active_trip=True,
        )
        
        print(f"❓ '{message}'")
        print(f"   → Agent: {result.agent.value}, Method: {result.method}, Confidence: {result.confidence:.2f}")
        
        assert result.agent == AgentType.COACH, f"Expected COACH, got {result.agent}"
    
    print("\n✅ All query messages route to Coach Agent!")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Test: Full Flow with Simulated User
# ─────────────────────────────────────────────────────────────────────────────

async def test_full_conversation_flow():
    """Test a full conversation flow through the Coordinator."""
    print_header("Test: Full Conversation Flow")
    
    # Use unique phone for this test
    test_phone = f"+5730099{uuid4().hex[:4]}"
    
    print(f"📱 Testing with phone: {test_phone}")
    
    # Message 1: Initial greeting (new user → should go to configuration)
    print("\n--- Step 1: New User Greeting ---")
    result1 = await send_message("Hola!", test_phone)
    print_result(result1, "Hola!")
    
    # Message 2: Provide name (configuration agent)
    print("\n--- Step 2: Provide Name ---")
    result2 = await send_message("Me llamo Carlos", test_phone)
    print_result(result2, "Me llamo Carlos")
    
    # Message 3: Provide currency
    print("\n--- Step 3: Provide Currency ---")
    result3 = await send_message("USD", test_phone)
    print_result(result3, "USD")
    
    print("\n✅ Full flow test completed!")
    print("   Note: Check the responses to verify correct agent routing.")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Test: Intent Change Detection
# ─────────────────────────────────────────────────────────────────────────────

async def test_intent_change_detection():
    """Test detection of intent changes within a session."""
    print_header("Test: Intent Change Detection")
    
    from app.agents.coordinator.router import detect_intent_change
    
    test_cases = [
        # (message, current_agent, should_change, expected_new_agent)
        ("¿Cuánto llevo gastado?", "ie", True, "coach"),
        ("Gasté 50 soles en taxi", "coach", True, "ie"),
        ("Pagué 100 dólares hotel", "configuration", True, "ie"),
        ("cancelar", "ie", True, None),  # Command always changes
        ("sí, correcto", "configuration", False, None),  # Confirmation continues
    ]
    
    for message, current_agent, expected_change, expected_agent in test_cases:
        result = await detect_intent_change(
            message=message,
            current_agent=current_agent,
            last_bot_message="Anterior mensaje del bot",
        )
        
        status = "✅" if result.should_change == expected_change else "❌"
        print(f"{status} In {current_agent}: '{message}'")
        print(f"   → should_change: {result.should_change}, new_agent: {result.new_agent}")
        
        if expected_change:
            assert result.should_change, f"Expected change but got no change"
    
    print("\n✅ Intent change detection works!")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Test: Router Class
# ─────────────────────────────────────────────────────────────────────────────

async def test_intent_router_class():
    """Test the IntentRouter class directly."""
    print_header("Test: IntentRouter Class")
    
    from app.agents.coordinator.router import IntentRouter
    from app.agents.common.intents import AgentType
    
    router = IntentRouter()
    
    # Test 1: Command detection
    result = await router.route("cancelar")
    print(f"📌 Command 'cancelar': agent={result.agent.value}, is_command={result.is_command}")
    assert result.is_command, "Should be a command"
    
    # Test 2: Onboarding required
    result = await router.route("Hola", onboarding_completed=False)
    print(f"📌 New user 'Hola': agent={result.agent.value}, method={result.method}")
    assert result.agent == AgentType.CONFIGURATION, "Should go to configuration"
    
    # Test 3: Expense detection
    result = await router.route("Gasté 50 soles en taxi", onboarding_completed=True)
    print(f"📌 Expense: agent={result.agent.value}, method={result.method}")
    assert result.agent == AgentType.IE, "Should go to IE"
    
    # Test 4: Query detection
    result = await router.route("¿Cuánto gasté?", onboarding_completed=True)
    print(f"📌 Query: agent={result.agent.value}, method={result.method}")
    assert result.agent == AgentType.COACH, "Should go to Coach"
    
    # Test 5: Forced agent
    result = await router.route("cualquier cosa", force_agent=AgentType.IE)
    print(f"📌 Forced: agent={result.agent.value}, method={result.method}")
    assert result.method == "forced", "Should be forced"
    
    print("\n✅ IntentRouter class works correctly!")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Test: Graph Structure
# ─────────────────────────────────────────────────────────────────────────────

async def test_graph_structure():
    """Test that the LangGraph is correctly structured."""
    print_header("Test: Graph Structure")
    
    from app.agents.coordinator.graph import create_coordinator_graph
    
    graph = create_coordinator_graph()
    
    # Check nodes exist
    expected_nodes = [
        "load_context",
        "check_lock",
        "detect_intent",
        "handle_command",
        "route_to_agent",
        "process_response",
        "update_state",
    ]
    
    print("📊 Checking graph nodes...")
    for node in expected_nodes:
        assert node in graph.nodes, f"Missing node: {node}"
        print(f"   ✅ Node '{node}' exists")
    
    print(f"\n📊 Total nodes: {len(graph.nodes)}")
    print("✅ Graph structure is correct!")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Main Test Runner
# ─────────────────────────────────────────────────────────────────────────────

async def run_all_tests():
    """Run all tests."""
    print("\n" + "🚀" * 35)
    print("     COORDINATOR AGENT TEST SUITE")
    print("🚀" * 35)
    
    tests = [
        ("Intent Detection (Fast Path)", test_intent_detection),
        ("IntentRouter Class", test_intent_router_class),
        ("Graph Structure", test_graph_structure),
        ("Coordinator Commands", test_coordinator_commands),
        ("Expense Routing", test_expense_routing),
        ("Query Routing", test_query_routing),
        ("Intent Change Detection", test_intent_change_detection),
        ("Full Conversation Flow", test_full_conversation_flow),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            success = await test_func()
            if success:
                passed += 1
            else:
                failed += 1
                print(f"\n❌ Test '{name}' failed!")
        except Exception as e:
            failed += 1
            print(f"\n❌ Test '{name}' raised exception: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary
    print("\n" + "=" * 70)
    print("                        TEST SUMMARY")
    print("=" * 70)
    print(f"   ✅ Passed: {passed}")
    print(f"   ❌ Failed: {failed}")
    print(f"   📊 Total:  {len(tests)}")
    print("=" * 70)
    
    return failed == 0


async def run_single_test(test_name: str):
    """Run a single test by name."""
    tests = {
        "intent": test_intent_detection,
        "router": test_intent_router_class,
        "graph": test_graph_structure,
        "commands": test_coordinator_commands,
        "expense": test_expense_routing,
        "query": test_query_routing,
        "change": test_intent_change_detection,
        "flow": test_full_conversation_flow,
    }
    
    if test_name in tests:
        await tests[test_name]()
    else:
        print(f"Unknown test: {test_name}")
        print(f"Available tests: {', '.join(tests.keys())}")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Coordinator Agent")
    parser.add_argument(
        "test",
        nargs="?",
        default="all",
        help="Test to run: all, intent, router, graph, commands, expense, query, change, flow"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode with breakpoints"
    )
    
    args = parser.parse_args()
    
    if args.debug:
        # Set a breakpoint here for debugging
        print("🔍 Debug mode enabled. Set breakpoints and run.")
        breakpoint()
    
    if args.test == "all":
        success = asyncio.run(run_all_tests())
        sys.exit(0 if success else 1)
    else:
        asyncio.run(run_single_test(args.test))


if __name__ == "__main__":
    main()

