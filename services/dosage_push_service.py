# =============================================================================
# services/dosage_push_service.py
# Pushes locally-created / locally-edited Dosage records to Frappe via
# saas_api.www.api.create_dosage / update_dosage.
# Mirrors services/dosage_sync_service.py auth + host handling.
# =============================================================================

from __future__ import annotations

import json
import logging
import time
import urllib.request
import urllib.error

from services.site_config import get_host as _get_host

log = logging.getLogger("DosagePush")
REQUEST_TIMEOUT = 30


def _get_credentials() -> tuple[str, str]:
    try:
        from services.credentials import get_credentials
        return get_credentials()
    except Exception:
        pass
    return "", ""


# =============================================================================
# MAIN PUSH
# =============================================================================

def push_unsynced_dosages() -> dict:
    """
    Push every local dosage with synced=0 up to Frappe.

    - frappe_name NULL → POST saas_api.www.api.create_dosage
    - frappe_name SET  → POST saas_api.www.api.update_dosage

    Offline / network failures return a neutral result and never raise.
    Returns {"pushed": N, "errors": N, "skipped": N}.
    """
    started = time.monotonic()
    result = {"pushed": 0, "errors": 0, "skipped": 0}

    api_key, api_secret = _get_credentials()
    if not api_key or not api_secret:
        log.warning("[dosage-push] No credentials — skipping.")
        return result

    host = _get_host()
    if not host:
        log.warning("[dosage-push] No API host configured — skipping.")
        return result

    try:
        from models.dosage import get_unsynced_dosages, mark_dosage_synced
    except Exception as e:
        log.error("[dosage-push] Could not import dosage model: %s", e)
        return result

    try:
        dosages = get_unsynced_dosages() or []
    except Exception as e:
        log.error("[dosage-push] Could not load unsynced dosages: %s", e)
        return result

    if not dosages:
        log.info("[dosage-push] No unsynced dosages.")
        return result

    log.info("[dosage-push] %d unsynced dosage(s) to push…", len(dosages))

    for d in dosages:
        payload = {
            "code":        d.code or "",
            "description": d.description or "",
        }

        if d.frappe_name:
            endpoint = "saas_api.www.api.update_dosage"
            payload["name"] = d.frappe_name
        else:
            endpoint = "saas_api.www.api.create_dosage"

        url  = f"{host}/api/method/{endpoint}"
        body = json.dumps(payload).encode("utf-8")
        req  = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Authorization", f"token {api_key}:{api_secret}")
        req.add_header("Content-Type",  "application/json")
        req.add_header("Accept",        "application/json")

        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
                resp = json.loads(r.read().decode() or "{}")
        except urllib.error.HTTPError as e:
            try:
                body_text = e.read().decode(errors="replace")[:300]
            except Exception:
                body_text = ""
            log.error("[dosage-push] ❌ HTTP %s on %s: %s — %s",
                      e.code, d.code, e.reason, body_text)
            print(f"[dosage-push] ❌ HTTP {e.code} for {d.code}: {body_text}")
            result["errors"] += 1
            continue
        except Exception as e:
            log.error("[dosage-push] ❌ Network error pushing %s: %s",
                      d.code, e)
            print(f"[dosage-push] ❌ Network error for {d.code}: {e}")
            result["errors"] += 1
            continue

        msg = resp.get("message", resp)
        returned_name = None
        if isinstance(msg, dict):
            returned_name = msg.get("name") or (msg.get("data") or {}).get("name")
        if not returned_name:
            log.warning("[dosage-push] ⚠ No name returned for %s — response=%r",
                        d.code, msg)
            print(f"[dosage-push] ⚠ No name returned for {d.code}: {msg}")
            result["skipped"] += 1
            continue

        try:
            mark_dosage_synced(d.id, returned_name)
            result["pushed"] += 1
            log.info("[dosage-push] ✅ Pushed: %s → %s", d.code, returned_name)
            print(f"[dosage-push] ✅ Pushed: {d.code} → {returned_name}")
        except Exception as e:
            log.error("[dosage-push] ❌ mark_dosage_synced failed for %s: %s",
                      d.code, e)
            result["errors"] += 1

    duration = round(time.monotonic() - started, 3)
    log.info(
        "[dosage-push] Done — %d pushed, %d error(s), %d skipped, %.2fs.",
        result["pushed"], result["errors"], result["skipped"], duration,
    )
    return result


if __name__ == "__main__":
    import logging as _l
    _l.basicConfig(level=_l.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    r = push_unsynced_dosages()
    print(f"\nPushed: {r['pushed']}  Errors: {r['errors']}  Skipped: {r['skipped']}")
