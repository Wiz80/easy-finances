"""
Manual end-to-end tests for WhatsApp integration.

This script provides utilities for testing the WhatsApp webhook
endpoint with simulated Twilio requests.

Usage:
    # Start the FastAPI server first:
    uvicorn app.api.main:app --reload --port 8000
    
    # Then run this script:
    python tests-manual/test_whatsapp_e2e.py
    
    # Or run specific tests:
    python tests-manual/test_whatsapp_e2e.py --test onboarding
    python tests-manual/test_whatsapp_e2e.py --test trip
"""

import argparse
import hashlib
import hmac
import time
from urllib.parse import urlencode
import httpx


# Configuration
WEBHOOK_URL = "http://localhost:8000/api/v1/webhook/twilio"
TEST_PHONE = "+573115084628"
TWILIO_NUMBER = "+14155238886"

# Twilio auth token for signature (use test token in dev)
# In real testing, set this to your actual auth token
AUTH_TOKEN = "test-token"


def generate_twilio_signature(url: str, params: dict, auth_token: str) -> str:
    """
    Generate Twilio request signature.
    
    In development/testing, if the server is configured to skip validation,
    this signature won't be checked.
    """
    # Sort params and concatenate
    sorted_params = sorted(params.items())
    param_str = "".join(f"{k}{v}" for k, v in sorted_params)
    
    # Create signature
    signature_input = url + param_str
    signature = hmac.new(
        auth_token.encode(),
        signature_input.encode(),
        hashlib.sha1
    ).digest()
    
    import base64
    return base64.b64encode(signature).decode()


def send_message(body: str, message_sid: str | None = None) -> dict:
    """
    Send a simulated WhatsApp message to the webhook.
    
    Args:
        body: Message text
        message_sid: Optional message SID (generated if not provided)
        
    Returns:
        Response dict with status and body
    """
    message_sid = message_sid or f"SM{int(time.time() * 1000)}"
    
    params = {
        "MessageSid": message_sid,
        "AccountSid": "ACtest",
        "From": f"whatsapp:{TEST_PHONE}",
        "To": f"whatsapp:{TWILIO_NUMBER}",
        "Body": body,
        "NumMedia": "0",
        "ProfileName": "Test User",
    }
    
    # Generate signature
    signature = generate_twilio_signature(WEBHOOK_URL, params, AUTH_TOKEN)
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Twilio-Signature": signature,
    }
    
    try:
        response = httpx.post(
            WEBHOOK_URL,
            data=params,
            headers=headers,
            timeout=30.0,
        )
        
        return {
            "status_code": response.status_code,
            "body": response.text,
            "headers": dict(response.headers),
        }
    except httpx.RequestError as e:
        return {
            "error": str(e),
            "status_code": None,
        }


def test_health_check():
    """Test the health endpoint."""
    print("\n" + "=" * 60)
    print("TEST: Health Check")
    print("=" * 60)
    
    try:
        response = httpx.get("http://localhost:8000/api/v1/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False


def test_onboarding_flow():
    """Test the complete onboarding flow."""
    print("\n" + "=" * 60)
    print("TEST: Onboarding Flow")
    print("=" * 60)
    
    steps = [
        ("Hola", "Greeting - should ask for name"),
        ("Harrison", "Provide name - should ask for currency"),
        ("COP", "Provide currency - should ask for timezone"),
        ("sí", "Confirm timezone - should complete onboarding"),
    ]
    
    for message, description in steps:
        print(f"\n--- Step: {description} ---")
        print(f"Sending: '{message}'")
        
        result = send_message(message)
        
        if result.get("error"):
            print(f"ERROR: {result['error']}")
            return False
        
        print(f"Status: {result['status_code']}")
        print(f"Response: {result['body'][:200]}...")
        
        time.sleep(1)  # Small delay between messages
    
    return True


def test_trip_flow():
    """Test the trip creation flow."""
    print("\n" + "=" * 60)
    print("TEST: Trip Creation Flow")
    print("=" * 60)
    
    steps = [
        ("Nuevo viaje", "Start trip creation"),
        ("Ecuador Adventure", "Provide trip name"),
        ("15/12/2024", "Provide start date"),
        ("30/12/2024", "Provide end date"),
        ("Ecuador", "Provide destination"),
        ("sí", "Confirm trip"),
    ]
    
    for message, description in steps:
        print(f"\n--- Step: {description} ---")
        print(f"Sending: '{message}'")
        
        result = send_message(message)
        
        if result.get("error"):
            print(f"ERROR: {result['error']}")
            return False
        
        print(f"Status: {result['status_code']}")
        print(f"Response: {result['body'][:200]}...")
        
        time.sleep(1)
    
    return True


def test_budget_flow():
    """Test the budget configuration flow."""
    print("\n" + "=" * 60)
    print("TEST: Budget Configuration Flow")
    print("=" * 60)
    
    steps = [
        ("Configurar presupuesto", "Start budget config"),
        ("5000000", "Total amount"),
        ("1500000", "Food allocation"),
        ("2000000", "Lodging allocation"),
        ("800000", "Transport allocation"),
        ("500000", "Tourism allocation"),
        ("300000", "Gifts allocation"),
        ("400000", "Contingency allocation"),
        ("sí", "Confirm budget"),
    ]
    
    for message, description in steps:
        print(f"\n--- Step: {description} ---")
        print(f"Sending: '{message}'")
        
        result = send_message(message)
        
        if result.get("error"):
            print(f"ERROR: {result['error']}")
            return False
        
        print(f"Status: {result['status_code']}")
        print(f"Response: {result['body'][:200]}...")
        
        time.sleep(1)
    
    return True


def test_help():
    """Test the help command."""
    print("\n" + "=" * 60)
    print("TEST: Help Command")
    print("=" * 60)
    
    result = send_message("ayuda")
    
    if result.get("error"):
        print(f"ERROR: {result['error']}")
        return False
    
    print(f"Status: {result['status_code']}")
    print(f"Response: {result['body']}")
    
    return result['status_code'] == 200


def interactive_mode():
    """Run in interactive mode for manual testing."""
    print("\n" + "=" * 60)
    print("INTERACTIVE MODE")
    print("=" * 60)
    print("Type messages to send to the webhook.")
    print("Type 'quit' or 'exit' to stop.")
    print("=" * 60)
    
    while True:
        try:
            message = input("\nYou: ").strip()
            
            if message.lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                break
            
            if not message:
                continue
            
            result = send_message(message)
            
            if result.get("error"):
                print(f"ERROR: {result['error']}")
            else:
                print(f"Bot: {result['body']}")
                
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break


def main():
    parser = argparse.ArgumentParser(description="WhatsApp E2E Test Script")
    parser.add_argument(
        "--test",
        choices=["health", "onboarding", "trip", "budget", "help", "all"],
        default="health",
        help="Test to run (default: health)",
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive mode",
    )
    
    args = parser.parse_args()
    
    print("\n" + "#" * 60)
    print("# WhatsApp E2E Test Script")
    print("#" * 60)
    print(f"Webhook URL: {WEBHOOK_URL}")
    print(f"Test Phone: {TEST_PHONE}")
    
    if args.interactive:
        interactive_mode()
        return
    
    tests = {
        "health": test_health_check,
        "onboarding": test_onboarding_flow,
        "trip": test_trip_flow,
        "budget": test_budget_flow,
        "help": test_help,
    }
    
    if args.test == "all":
        results = {}
        for name, func in tests.items():
            results[name] = func()
        
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        for name, passed in results.items():
            status = "✅ PASSED" if passed else "❌ FAILED"
            print(f"  {name}: {status}")
    else:
        tests[args.test]()


if __name__ == "__main__":
    main()






