import sys
from pathlib import Path
import time

# Ensure imports work from the root project directory
sys.path.insert(0, str(Path(__file__).resolve().parent))

from services.bugsink_service import init_bugsink, set_user_context, capture_message, shutdown

def run_test():
    print("1. Initializing Bugsink Client...")
    init_bugsink(version="2.0-test", enabled=True)

    print("2. Setting mock logged-in user context...")
    set_user_context(
        username="cashier_test",
        email="cashier@machipisa.com",
        role="Cashier",
        name="Test Cashier (Bugsink Verification)"
    )

    print("3. Sending test event to Bugsink...")
    capture_message(
        message="Manual Test Event: Verifying Logged-In User Context Tracking",
        level="info",
        extra={"reason": "User verification test"}
    )

    print("4. Waiting for background thread to dispatch event (3s)...")
    time.sleep(3)

    print("5. Shutting down Bugsink client...")
    shutdown()

    print("\n✅ Test complete! Check your Bugsink dashboard. You should see an event with user: cashier@machipisa.com")

if __name__ == "__main__":
    run_test()
