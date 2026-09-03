"""
Diagnostic: test terminal takeover directly.
Shows full request payload and full raw response so we can see why it fails.
"""
import sys, os, json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models.company_defaults import get_defaults
from utils.hardware import get_machine_id
from services.credentials import get_credentials, get_system_mode

print("=== System Mode ===")
mode = get_system_mode()
print(f"  mode: {mode}")
if mode != "saas":
    print("  WARNING: not in saas mode — takeover won't run in production")

print("\n=== Company Defaults (relevant fields) ===")
d = get_defaults() or {}
term_id = d.get("server_terminal_id") or d.get("terminal_id")
host    = d.get("server_api_host") or d.get("host") or ""
email   = d.get("server_email") or ""
print(f"  terminal_id : {term_id}")
print(f"  api_host    : {host}")
print(f"  server_email: {email}")

print("\n=== Credentials ===")
api_key, api_secret = get_credentials()
print(f"  api_key   : {api_key[:8] + '...' if api_key else 'MISSING'}")
print(f"  api_secret: {'set' if api_secret else 'MISSING'}")

print("\n=== Device ID ===")
my_dev = get_machine_id()
print(f"  device: {my_dev}")

if not term_id:
    print("\nERROR: No terminal_id found — cannot takeover. Check company_defaults.")
    sys.exit(1)

# ── Call select_terminal with full debug output ────────────────────────────────
print(f"\n=== Calling select_terminal(term_id={term_id}, takeover=True, user={email}) ===")
import urllib.request, urllib.error, ssl, traceback

# Replicate the exact request from auth_service.select_terminal
from services.auth_service import select_terminal

try:
    res = select_terminal(term_id, takeover=True, user_email=email)
    print("\n=== Response ===")
    print(json.dumps(res, indent=2, default=str))

    if res.get("success"):
        print("\n[OK] Takeover succeeded!")
        # Try to extract bound device from response
        user_obj = res.get("data", {}).get("user") or {}
        if isinstance(user_obj, dict):
            sel_tid = user_obj.get("selected_terminal_id") or term_id
            for shop in (user_obj.get("shops") or []):
                for term in (shop.get("terminals") or []):
                    if str(term.get("id")) == str(sel_tid):
                        bound = term.get("device_hardware_id", "")
                        print(f"  Cloud bound device : {bound}")
                        print(f"  This device        : {my_dev}")
                        print(f"  Match              : {bound.lower().replace('-','') == my_dev.lower().replace('-','')}")
    else:
        print(f"\n[FAIL] Takeover failed!")
        print(f"  error   : {res.get('error')}")
        print(f"  message : {res.get('message')}")
        print(f"  status  : {res.get('status_code')}")
        print(f"  raw     : {res.get('raw', '')[:500]}")

except Exception as e:
    print(f"\n[EXCEPTION] {e}")
    traceback.print_exc()
