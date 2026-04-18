# =============================================================================
# services/dosage_sync_service.py
# Pulls Dosage reference records from Frappe (Pharmacy module) into the
# local DB. Patterned on services/user_sync_service.py.
# =============================================================================

from __future__ import annotations

import json
import logging
import time
import urllib.request
import urllib.error

from services.site_config import get_host as _get_host

log = logging.getLogger("DosageSync")
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

def sync_dosages() -> dict:
    """
    Fetch dosages from Frappe and upsert into the local dosages table.
    Returns {"synced": N, "errors": [...], "duration": seconds}.
    Offline / network errors return a neutral result and never raise.
    """
    started = time.monotonic()
    result = {"synced": 0, "errors": [], "duration": 0.0}

    api_key, api_secret = _get_credentials()
    if not api_key or not api_secret:
        log.warning("[dosage-sync] No credentials — skipping.")
        result["duration"] = time.monotonic() - started
        return result

    host = _get_host()
    if not host:
        log.warning("[dosage-sync] No API host configured — skipping.")
        result["duration"] = time.monotonic() - started
        return result

    try:
        from models.dosage import upsert_dosage_from_frappe
    except Exception as e:
        log.error("[dosage-sync] Could not import dosage model: %s", e)
        result["errors"].append(f"model import: {e}")
        result["duration"] = time.monotonic() - started
        return result

    page = 1
    while page <= MAX_PAGES:
        url = f"{host}/api/method/saas_api.www.api.get_dosages?page={page}&limit={PAGE_SIZE}"
        try:
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"token {api_key}:{api_secret}")
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
                data = json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            log.error("[dosage-sync] HTTP %s on page %d: %s", e.code, page, e.reason)
            result["errors"].append(f"HTTP {e.code} on page {page}")
            break
        except Exception as e:
            log.error("[dosage-sync] Network error on page %d: %s", page, e)
            result["errors"].append(f"Network error on page {page}: {e}")
            break

        msg = data.get("message", data)
        if isinstance(msg, dict):
            dosages = (
                msg.get("data")
                or msg.get("dosages")
                or msg.get("results")
                or []
            )
            pagination = msg.get("pagination") or {}
        elif isinstance(msg, list):
            dosages    = msg
            pagination = {}
        else:
            dosages    = []
            pagination = {}

        if not dosages:
            if page == 1:
                log.info("[dosage-sync] No dosages returned from Frappe.")
            break

        log.info("[dosage-sync] %d dosage(s) on page %d — upserting…", len(dosages), page)

        for d in dosages:
            code = d.get("code") or d.get("name") or "?"
            try:
                upsert_dosage_from_frappe(d)
                result["synced"] += 1
                log.info("[dosage-sync] ✅ Synced: %s", code)
            except Exception as e:
                log.error("[dosage-sync] ❌ Error upserting %s: %s", code, e)
                result["errors"].append(f"{code}: {e}")

        has_next = bool(pagination.get("has_next_page"))
        total_pages = int(pagination.get("total_pages") or 0)

        if not has_next and not total_pages:
            if len(dosages) < PAGE_SIZE:
                break
        elif total_pages and page >= total_pages:
            break
        elif not has_next:
            break

        page += 1

    result["duration"] = round(time.monotonic() - started, 3)
    log.info(
        "[dosage-sync] Done — %d synced, %d error(s), %.2fs.",
        result["synced"], len(result["errors"]), result["duration"],
    )
    return result


if __name__ == "__main__":
    import logging as _l
    _l.basicConfig(level=_l.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    r = sync_dosages()
    print(f"\nSynced: {r['synced']}  Errors: {len(r['errors'])}  Duration: {r['duration']}s")
