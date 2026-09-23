import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget, QPushButton
from services.bugsink_service import init_bugsink, set_current_page, get_current_page
from services.hang_watchdog import start_hang_watchdog

def run_test():
    app = QApplication(sys.argv)

    # Initialize Bugsink in active mode for testing
    init_bugsink(enabled=True)
    set_current_page("Test Payment Screen")

    print("\n" + "=" * 60)
    print(" 1. Starting UI Hang Watchdog (1.0s interval, alert at 5s)...")
    print("=" * 60)
    watchdog = start_hang_watchdog(check_interval_seconds=0.5)

    print("\n 2. Simulating a 6.5-second UI freeze on the main thread...")
    print("    Watchdog should detect freeze at 5.0s, capture the stack, and send alert.")
    print("=" * 60 + "\n")

    # Freeze the main thread for 6.5 seconds
    time.sleep(6.5)

    print("\n" + "=" * 60)
    print(" 3. Main thread resumed! Processing Qt events to trigger recovery...")
    print("=" * 60 + "\n")

    # Let Qt process events so the watchdog's pong signal fires and triggers recovery
    app.processEvents()
    time.sleep(0.5)
    app.processEvents()

    watchdog.stop()
    print("\n[OK] Test completed successfully!")

if __name__ == "__main__":
    run_test()
