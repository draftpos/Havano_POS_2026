# =============================================================================
# services/doctor_sync_service.py
# Pulls Doctor records from Frappe (Pharmacy module) into the local DB.
# Patterned on services/user_sync_service.py.
# =============================================================================

from __future__ import annotations

import json
import logging
import time
import urllib.request
import urllib.error

from services.site_config import get_host as _get_host

log = logging.getLogger("DoctorSync")
REQUEST_TIMEOUT = 30
PAGE_SIZE       = 1000
MAX_PAGES       = 50


def _get_credentials() -> tuple[str, str]:
    try:
        from services.credentials import get_credentials
        return get_credentials()
    except Exception:
        pass
    return "", ""


# =============================================================================
# MAIN SYNC
# =============================================================================

def sync_doctors() -> dict:
    """
    Fetch doctors from Frappe and upsert into the local doctors table.
    Returns {"synced": N, "errors": [...], "duration": seconds}.
    Offline / network errors return a neutral result and never raise.
    """
    started = time.monotonic()
    result = {"synced": 0, "errors": [], "duration": 0.0}

    api_key, api_secret = _get_credentials()
    if not api_key or not api_secret:
        log.warning("[doctor-sync] No credentials — skipping.")
        result["duration"] = time.monotonic() - started
        return result

    host = _get_host()
    if not host:
        log.warning("[doctor-sync] No API host configured — skipping.")
        result["duration"] = time.monotonic() - started
        return result

    # Lazy-import the model so a missing table pre-migration doesn't break
    # callers that merely import this module.
    try:
        from models.doctor import upsert_doctor_from_frappe
    except Exception as e:
        log.error("[doctor-sync] Could not import doctor model: %s", e)
        result["errors"].append(f"model import: {e}")
        result["duration"] = time.monotonic() - started
        return result

    page = 1
    while page <= MAX_PAGES:
        url = f"{host}/api/method/saas_api.www.api.get_doctors?page={page}&limit={PAGE_SIZE}"
        try:
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"token {api_key}:{api_secret}")
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
                data = json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            log.error("[doctor-sync] HTTP %s on page %d: %s", e.code, page, e.reason)
            result["errors"].append(f"HTTP {e.code} on page {page}")
            break
        except Exception as e:
            log.error("[doctor-sync] Network error on page %d: %s", page, e)
            result["errors"].append(f"Network error on page {page}: {e}")
            break

        # Frappe responses come back as {"message": {...}} — support both
        # {"message": {"data": [...]}} and {"message": [...]} shapes.
        msg = data.get("message", data)
        if isinstance(msg, dict):
            doctors = (
                msg.get("data")
                or msg.get("doctors")
                or msg.get("results")
                or []
            )
            pagination = msg.get("pagination") or {}
        elif isinstance(msg, list):
            doctors    = msg
            pagination = {}
        else:
            doctors    = []
            pagination = {}

        if not doctors:
            if page == 1:
                log.info("[doctor-sync] No doctors returned from Frappe.")
            break

        log.info("[doctor-sync] %d doctor(s) on page %d — upserting…", len(doctors), page)

        for d in doctors:
            name = d.get("full_name") or d.get("name") or "?"
            try:
                upsert_doctor_from_frappe(d)
                result["synced"] += 1
                log.info("[doctor-sync] ✅ Synced: %s", name)
            except Exception as e:
                log.error("[doctor-sync] ❌ Error upserting %s: %s", name, e)
                result["errors"].append(f"{name}: {e}")

        # Pagination: stop when page is short or explicitly marked last
        has_next = bool(pagination.get("has_next_page"))
        total_pages = int(pagination.get("total_pages") or 0)

        if not has_next and not total_pages:
            # No pagination metadata — stop if we got fewer than PAGE_SIZE
            if len(doctors) < PAGE_SIZE:
                break
        elif total_pages and page >= total_pages:
            break
        elif not has_next:
            break

        page += 1

    result["duration"] = round(time.monotonic() - started, 3)
    log.info(
        "[doctor-sync] Done — %d synced, %d error(s), %.2fs.",
        result["synced"], len(result["errors"]), result["duration"],
    )
    return result


if __name__ == "__main__":
    import logging as _l
    _l.basicConfig(level=_l.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    r = sync_doctors()
    print(f"\nSynced: {r['synced']}  Errors: {len(r['errors'])}  Duration: {r['duration']}s")
