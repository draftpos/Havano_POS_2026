"""
test_ram_wipe_credentials.py
=============================
Simulates a full RAM/process restart to verify the system ALWAYS reads
the API token from SQL Server (company_defaults) and never depends on
in-memory state.

How to run:
    python test_ram_wipe_credentials.py

What it tests:
    1. Reads current token from DB (what the system actually has)
    2. Completely wipes the in-memory _session dict (simulates a cold restart)
    3. Calls build_auth_header() - should still return a valid header from DB
    4. Calls get_all_credentials() - should return the stored token
    5. Simulates push_unsynced_sales credential validation (SaaS mode)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 65)
print("  Havano POS  -  RAM-Wipe Credential Resilience Test")
print("=" * 65)

# -- Step 1: Check what is stored in DB right now ----------------------
print("\n[1] Reading company_defaults directly from SQL Server...")
try:
    from database.db import get_connection
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT api_key, api_secret, system_mode, odoo_token
        FROM   company_defaults
        WHERE  id = (SELECT MIN(id) FROM company_defaults)
    """)
    row = cur.fetchone()
    conn.close()
    if row and row[0]:
        stored_key    = str(row[0] or "").strip()
        stored_secret = str(row[1] or "").strip()
        stored_mode   = str(row[2] or "saas").strip()
        print(f"   api_key     : {stored_key[:12]}...{stored_key[-6:] if len(stored_key) > 18 else '(short)'}")
        print(f"   api_secret  : {'(empty - SaaS mode OK)' if not stored_secret else stored_secret[:6] + '...'}")
        print(f"   system_mode : {stored_mode}")
        print(f"   OK: DB has a valid token stored.")
    else:
        print("   PROBLEM: company_defaults has no api_key stored!")
        print("      Log in to the POS once, then re-run this test.")
        sys.exit(1)
except Exception as e:
    print(f"   Could not connect to DB: {e}")
    sys.exit(1)

# -- Step 2: Nuke in-memory RAM completely -----------------------------
print("\n[2] Simulating RAM wipe (clearing _session dict)...")
import services.credentials as creds_module
before = dict(creds_module._session)
creds_module._session.clear()
creds_module._loaded_from_db = False
print(f"   _session before wipe : {list(before.keys()) or '(was already empty)'}")
print(f"   _session after wipe  : {dict(creds_module._session)}")
print(f"   OK: RAM cleared. In-memory token is GONE.")

# -- Step 3: build_auth_header() must recover from DB ------------------
print("\n[3] Calling build_auth_header() with no arguments (cold-start sim)...")
from services.credentials import build_auth_header
header = build_auth_header()
if header and header.startswith("token "):
    print(f"   Result : {header[:20]}...  (truncated for security)")
    print(f"   PASS - Header built from DB even after RAM wipe!")
else:
    print(f"   FAIL - build_auth_header() returned: '{header}'")
    print("      This means the DB token is missing or build logic has a bug.")
    sys.exit(1)

# -- Step 4: get_all_credentials() returns full dict -------------------
print("\n[4] Calling get_all_credentials() after RAM wipe...")
creds_module._session.clear()  # wipe again to be sure
from services.credentials import get_all_credentials
creds = get_all_credentials()
k = creds.get("api_key", "")
m = creds.get("system_mode", "")
if k:
    print(f"   api_key     : {k[:12]}...{k[-6:] if len(k)>18 else '(short)'}")
    print(f"   system_mode : {m}")
    print(f"   PASS - Credentials recovered from DB on every call.")
else:
    print(f"   FAIL - get_all_credentials() returned empty api_key.")
    sys.exit(1)

# -- Step 5: SaaS push_unsynced_sales credential check -----------------
print("\n[5] Simulating SaaS mode credential validation (like pos_upload_service)...")
creds_module._session.clear()  # wipe RAM one more time
mode = creds.get("system_mode", "saas").lower()
c2 = get_all_credentials()
up_key    = c2.get("api_key", "").strip()
up_secret = c2.get("api_secret", "").strip()
is_saas   = (mode == "saas")

has_valid_creds = bool(up_key) if is_saas else bool(up_key and up_secret)
if has_valid_creds:
    print(f"   Mode        : {mode}")
    print(f"   Has api_key : YES")
    print(f"   PASS - Sales upload would proceed with stored credentials.")
else:
    print(f"   FAIL - pos_upload_service would SKIP upload due to missing credentials.")
    sys.exit(1)

# -- Summary -----------------------------------------------------------
print()
print("=" * 65)
print("  ALL TESTS PASSED")
print()
print("  What this means:")
print("  - Turning off your laptop CLEARS RAM completely.")
print("  - On next startup, _session starts empty (like after wipe).")
print("  - EVERY call to get_all_credentials() / build_auth_header()")
print("    reads FRESH from SQL Server company_defaults table.")
print("  - As long as SQL Server is running on restart, cloud sync")
print("    and sales upload WILL work without requiring a new login.")
print("=" * 65)
