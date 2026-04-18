# =============================================================================
# services/doctor_push_service.py
# Pushes locally-created / locally-edited Doctor records to Frappe via
# saas_api.www.api.create_doctor / update_doctor.
# Mirrors services/doctor_sync_service.py auth + host handling.
# =============================================================================

from __future__ import annotations

import json
import logging
import time
import urllib.request
import urllib.error

from services.site_config import get_host as _get_host

log = logging.getLogger("DoctorPush")
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

def push_unsynced_doctors() -> dict:
    """
    Push every local doctor with synced=0 up to Frappe.

    - frappe_name NULL → POST saas_api.www.api.create_doctor
    - frappe_name SET  → POST saas_api.www.api.update_doctor

    Offline / network failures return a neutral result and never raise.
    Returns {"pushed": N, "errors": N, "skipped": N}.
    """
    started = time.monotonic()
    result = {"pushed": 0, "errors": 0, "skipped": 0}

    api_key, api_secret = _get_credentials()
    if not api_key or not api_secret:
        log.warning("[doctor-push] No credentials — skipping.")
        return result

    host = _get_host()
    if not host:
        log.warning("[doctor-push] No API host configured — skipping.")
        return result

    try:
        from models.doctor import get_unsynced_doctors, mark_doctor_synced
    except Exception as e:
        log.error("[doctor-push] Could not import doctor model: %s", e)
        return result

    try:
        doctors = get_unsynced_doctors() or []
    except Exception as e:
        log.error("[doctor-push] Could not load unsynced doctors: %s", e)
        return result

    if not doctors:
        log.info("[doctor-push] No unsynced doctors.")
        return result

    log.info("[doctor-push] %d unsynced doctor(s) to push…", len(doctors))

    for d in doctors:
        payload = {
            "full_name":     d.full_name or "",
            "practice_no":   d.practice_no or "",
            "qualification": d.qualification or "",
            "school":        d.school or "",
            "phone":         d.phone or "",
        }

        if d.frappe_name:
            # Previously pushed, locally edited → update
            endpoint = "saas_api.www.api.update_doctor"
            payload["name"] = d.frappe_name
        else:
            # Brand-new locally → create
            endpoint = "saas_api.www.api.create_doctor"

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
            log.error("[doctor-push] ❌ HTTP %s on %s: %s — %s",
                      e.code, d.full_name, e.reason, body_text)
            print(f"[doctor-push] ❌ HTTP {e.code} for {d.full_name}: {body_text}")
            result["errors"] += 1
            continue
        except Exception as e:
            log.error("[doctor-push] ❌ Network error pushing %s: %s",
                      d.full_name, e)
            print(f"[doctor-push] ❌ Network error for {d.full_name}: {e}")
            result["errors"] += 1
            continue

        msg = resp.get("message", resp)
        returned_name = None
        if isinstance(msg, dict):
            returned_name = msg.get("name") or (msg.get("data") or {}).get("name")
        if not returned_name:
            # Frappe sometimes 200s with an error shape; log and skip.
            log.warning("[doctor-push] ⚠ No name returned for %s — response=%r",
                        d.full_name, msg)
            print(f"[doctor-push] ⚠ No name returned for {d.full_name}: {msg}")
            result["skipped"] += 1
            continue

        try:
            mark_doctor_synced(d.id, returned_name)
            result["pushed"] += 1
            log.info("[doctor-push] ✅ Pushed: %s → %s",
                     d.full_name, returned_name)
            print(f"[doctor-push] ✅ Pushed: {d.full_name} → {returned_name}")
        except Exception as e:
            log.error("[doctor-push] ❌ mark_doctor_synced failed for %s: %s",
                      d.full_name, e)
            result["errors"] += 1

    duration = round(time.monotonic() - started, 3)
    log.info(
        "[doctor-push] Done — %d pushed, %d error(s), %d skipped, %.2fs.",
        result["pushed"], result["errors"], result["skipped"], duration,
    )
    return result


if __name__ == "__main__":
    import logging as _l
    _l.basicConfig(level=_l.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    r = push_unsynced_doctors()
    print(f"\nPushed: {r['pushed']}  Errors: {r['errors']}  Skipped: {r['skipped']}")
