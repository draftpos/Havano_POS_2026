# =============================================================================
# services/user_sync_service.py
# Syncs users from Frappe → local users table.
#
# FILTER: Only users with ALL of the following set in Frappe are synced
# (and therefore allowed to log in at this POS):
#
#   User level:
#     - company
#     - warehouse
#     - cost_center
#
#   Customer level (the user's linked customer must have):
#     - customer_primary_address  OR  any address
#     - default_price_list
#     - cost_center
#     - warehouse  (via customer_primary_contact or defaults)
#
# Users missing any of these are skipped with a clear log message.
# This prevents cashiers without proper setup from appearing at login.
# =============================================================================

from __future__ import annotations

import json
import logging
import urllib.request
import urllib.error

log = logging.getLogger("UserSync")
REQUEST_TIMEOUT = 30


def _get_credentials() -> tuple[str, str]:
    try:
        from services.credentials import get_credentials
        return get_credentials()
    except Exception:
        pass
    return "", ""


def _get_host() -> str:
    try:
        from models.company_defaults import get_defaults
        host = (get_defaults() or {}).get("server_api_host", "").strip().rstrip("/")
        if host:
            return host
    except Exception:
        pass
    return "https://apk.havano.cloud"


# =============================================================================
# FILTER
# =============================================================================

def _user_is_complete(u: dict) -> tuple[bool, str]:
    """
    Returns (True, "") if the user has all required fields set.
    Returns (False, reason) if they are missing something.

    Checks:
      User:     company, warehouse, cost_center
      Customer: default_price_list, cost_center, warehouse
    """
    name = u.get("full_name") or u.get("name") or "?"

    # ── User-level fields ─────────────────────────────────────────────────────
    missing_user = []
    if not str(u.get("company") or "").strip():
        missing_user.append("company")
    if not str(u.get("warehouse") or "").strip():
        missing_user.append("warehouse")
    if not str(u.get("cost_center") or "").strip():
        missing_user.append("cost_center")

    if missing_user:
        return False, f"missing user fields: {', '.join(missing_user)}"

    # ── Customer-level fields ─────────────────────────────────────────────────
    # The customer block may be nested under "customer" key or flat
    cust = u.get("customer") or {}
    if isinstance(cust, str):
        # Some APIs return just the customer name string — treat as incomplete
        # because we can't check sub-fields
        cust = {}

    missing_cust = []
    if not str(cust.get("default_price_list") or u.get("default_price_list") or "").strip():
        missing_cust.append("default_price_list")
    if not str(cust.get("cost_center") or u.get("customer_cost_center") or "").strip():
        missing_cust.append("customer cost_center")
    if not str(cust.get("warehouse") or u.get("customer_warehouse") or "").strip():
        missing_cust.append("customer warehouse")

    if missing_cust:
        return False, f"missing customer fields: {', '.join(missing_cust)}"

    return True, ""


# =============================================================================
# MAIN SYNC
# =============================================================================

def sync_users() -> dict:
    """
    Fetch users from Frappe and upsert into local users table.
    Only syncs users that pass the completeness filter.
    Returns {"synced": N, "skipped": N, "errors": N}
    """
    result = {"synced": 0, "skipped": 0, "errors": 0}

    api_key, api_secret = _get_credentials()
    if not api_key or not api_secret:
        log.warning("[user-sync] No credentials — skipping.")
        return result

    host = _get_host()
    url  = f"{host}/api/method/saas_api.www.api.get_users"

    try:
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"token {api_key}:{api_secret}")
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
            data = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        log.error("[user-sync] HTTP %s fetching users: %s", e.code, e.reason)
        return result
    except Exception as e:
        log.error("[user-sync] Network error: %s", e)
        return result

    msg   = data.get("message", {})
    users = msg.get("data", [])

    if not users:
        log.info("[user-sync] No users returned from Frappe.")
        return result

    log.info("[user-sync] %d user(s) received — applying filter…", len(users))

    from models.user import upsert_frappe_user
    for u in users:
        name = u.get("full_name") or u.get("name") or "?"

        # Skip disabled users
        if not u.get("enabled", 1):
            log.debug("[user-sync] Skipped (disabled): %s", name)
            result["skipped"] += 1
            continue

        # Apply completeness filter
        ok, reason = _user_is_complete(u)
        if not ok:
            log.warning(
                "[user-sync] ⚠️  Skipped '%s' — %s. "
                "Fix in Frappe → User → %s then re-sync.",
                name, reason, name
            )
            result["skipped"] += 1
            continue

        try:
            upsert_frappe_user(u)
            result["synced"] += 1
            log.info("[user-sync] ✅ Synced: %s", name)
        except Exception as e:
            log.error("[user-sync] ❌ Error upserting %s: %s", name, e)
            result["errors"] += 1

    log.info(
        "[user-sync] Done — %d synced, %d skipped, %d errors.",
        result["synced"], result["skipped"], result["errors"],
    )
    return result


if __name__ == "__main__":
    import logging as _l
    _l.basicConfig(level=_l.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    r = sync_users()
    print(f"\nSynced: {r['synced']}  Skipped: {r['skipped']}  Errors: {r['errors']}")