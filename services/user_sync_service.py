
from __future__ import annotations

import json
import logging
import urllib.request
from services.network_utils import safe_urlopen

log = logging.getLogger("UserSync")
REQUEST_TIMEOUT = 30


def _get_credentials() -> tuple[str, str]:
    try:
        from services.credentials import get_credentials
        return get_credentials()
    except Exception:
        pass
    return "", ""


from services.site_config import get_host as _get_host


# =============================================================================
# MAIN SYNC
# =============================================================================

def sync_users() -> dict:
    """
    Fetch users from Frappe and upsert into local users table.
    Syncs all enabled users - no completeness filter applied.
    Returns {"synced": N, "skipped": N, "errors": N}
    """
    result = {"synced": 0, "skipped": 0, "errors": 0}

    api_key, api_secret = _get_credentials()
    if not api_key:
        log.warning("[user-sync] No credentials - skipping.")
        return result

    host = _get_host()
    endpoints = [
        f"{host}/api/method/saas_api.www.api.get_users",
        f"{host}/api/method/havano_pos_integration.api.get_users",
        f"{host}/api/method/saas_api.www.api.get_user",
        f"{host}/api/resource/User?fields=[\"name\",\"full_name\",\"email\",\"enabled\",\"username\",\"role_profile_name\"]&limit_page_length=0",
    ]

    data = None
    from services.credentials import build_auth_header
    auth_hdr = build_auth_header(api_key, api_secret)

    for url in endpoints:
        try:
            req = urllib.request.Request(url)
            if auth_hdr:
                req.add_header("Authorization", auth_hdr)
            with safe_urlopen(req, timeout=REQUEST_TIMEOUT) as r:
                data = json.loads(r.read().decode())
                if data:
                    break
        except urllib.error.HTTPError as e:
            log.warning("[user-sync] HTTP %s fetching users from %s", e.code, url)
        except Exception as e:
            log.warning("[user-sync] Error fetching from %s: %s", url, e)

    if not data:
        log.error("[user-sync] Could not fetch users from any endpoint.")
        return result

    users = []
    if "data" in data and isinstance(data["data"], list):
        users = data["data"]
    else:
        msg = data.get("message", {})
        if isinstance(msg, dict):
            users = msg.get("data", []) or msg.get("users", [])
        elif isinstance(msg, list):
            users = msg

    if not users and isinstance(data.get("data"), list):
        users = data["data"]

    if not users:
        log.info("[user-sync] No users returned from Frappe.")
        return result

    log.info("[user-sync] %d user(s) received - syncing all enabled users…", len(users))

    from models.user import upsert_frappe_user
    for u in users:
        name = u.get("full_name") or u.get("name") or "?"

        # Skip disabled users only
        if not u.get("enabled", 1):
            log.debug("[user-sync] Skipped (disabled): %s", name)
            result["skipped"] += 1
            continue

        try:
            upsert_frappe_user(u)
            result["synced"] += 1
            log.info("[user-sync] [OK] Synced: %s", name)
        except Exception as e:
            log.error("[user-sync] ❌ Error upserting %s: %s", name, e)
            result["errors"] += 1

    log.info(
        "[user-sync] Done - %d synced, %d skipped, %d errors.",
        result["synced"], result["skipped"], result["errors"],
    )
    return result


if __name__ == "__main__":
    import logging as _l
    _l.basicConfig(level=_l.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    r = sync_users()
    print(f"\nSynced: {r['synced']}  Skipped: {r['skipped']}  Errors: {r['errors']}")