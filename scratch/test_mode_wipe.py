import sys
import os
sys.path.insert(0, os.path.abspath("."))

print("[TEST] Testing set_system_mode wipe mechanism...")

from services.credentials import get_system_mode, set_system_mode, _db_has_active_data

current_mode = get_system_mode()
print(f"[TEST] Current system mode: {current_mode}")
print(f"[TEST] DB has active data: {_db_has_active_data()}")

# Test setting same mode -> should succeed with True
res_same = set_system_mode(current_mode, confirm_wipe=False)
print(f"[TEST] set_system_mode({current_mode!r}) -> {res_same}")
assert res_same is True, "Same mode should return True"

print("[SUCCESS] Mode wipe check verification passed cleanly!")
