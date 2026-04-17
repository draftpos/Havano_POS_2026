# services/external_quotation_service.py
# =============================================================================
# Fetch quotations from a SEPARATE external Frappe site and save locally.
#
# KEY FIX: External quotations are saved with an "EXT-" prefix on their name
# (e.g. "SAL-QTN-2024-00001" becomes "EXT-SAL-QTN-2024-00001") so they never
# collide with quotations that came from your own main site.
# =============================================================================

from __future__ import annotations

import json
import logging
import urllib.request
import urllib.error
import traceback

# ---------------------------------------------------------------------------
# Logger — forced console handler so output always appears
# ---------------------------------------------------------------------------
log = logging.getLogger("ExternalQuotationService")
if not log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("[ExternalQtn] %(levelname)s — %(message)s"))
    log.addHandler(_h)
log.setLevel(logging.DEBUG)

REQUEST_TIMEOUT = 20

# Prefix applied to every external quotation name to avoid clashing with
# quotations that already exist from your own main Frappe site.
EXTERNAL_PREFIX = "EXT-"


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------

def _get_external_settings() -> dict:
    print("[ExternalQtn] Loading settings from disk…")
    try:
        from views.dialogs.external_quotation_settings_dialog import load_external_settings
        cfg = load_external_settings()
        masked = {**cfg, "api_secret": ("***" if cfg.get("api_secret") else "<empty>")}
        print(f"[ExternalQtn] Settings loaded: {masked}")
        return cfg
    except Exception as e:
        print(f"[ExternalQtn] ERROR loading settings: {e}")
        traceback.print_exc()
        return {}


# ---------------------------------------------------------------------------
# Core fetch — one page
# ---------------------------------------------------------------------------

def fetch_quotations_from_external_site(page: int = 1, limit: int = 100) -> dict:
    """Fetch one page of quotations from the external Frappe site."""
    print(f"\n[ExternalQtn] ── fetch page={page} limit={limit} ──")

    cfg        = _get_external_settings()
    url        = cfg.get("url", "").strip().rstrip("/")
    api_key    = cfg.get("api_key", "").strip()
    api_secret = cfg.get("api_secret", "").strip()

    print(f"[ExternalQtn] URL     : {url or '<EMPTY>'}")
    print(f"[ExternalQtn] API Key : {api_key[:6] + '…' if len(api_key) > 6 else (api_key or '<EMPTY>')}")
    print(f"[ExternalQtn] Secret  : {'set (' + str(len(api_secret)) + ' chars)' if api_secret else '<EMPTY>'}")

    if not url:
        return _err(page, "External site URL is empty. Open 🌐 External Site settings.")
    if not api_key:
        return _err(page, "API Key is empty. Open 🌐 External Site settings.")
    if not api_secret:
        return _err(page, "API Secret is empty. Open 🌐 External Site settings.")

    endpoint = f"{url}/api/method/saas_api.www.api.get_quotations?page={page}&limit={limit}"
    print(f"[ExternalQtn] Endpoint: {endpoint}")

    try:
        req = urllib.request.Request(endpoint)
        req.add_header("Authorization", f"token {api_key}:{api_secret}")
        req.add_header("Accept", "application/json")
        req.add_header("Content-Type", "application/json")

        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            status_code  = resp.status
            content_type = resp.headers.get("Content-Type", "")
            raw_bytes    = resp.read()
            raw_text     = raw_bytes.decode("utf-8", errors="replace")

            print(f"[ExternalQtn] HTTP status  : {status_code}")
            print(f"[ExternalQtn] Content-Type : {content_type}")
            print(f"[ExternalQtn] Response size: {len(raw_bytes)} bytes")
            print(f"[ExternalQtn] Raw response : {raw_text[:800]}")

            try:
                data = json.loads(raw_text)
            except json.JSONDecodeError as je:
                return _err(page, f"Response is not valid JSON: {je}. Raw: {raw_text[:300]}")

            print(f"[ExternalQtn] JSON root keys: {list(data.keys())}")
            message = data.get("message", {})
            print(f"[ExternalQtn] 'message' type: {type(message).__name__}")

            if isinstance(message, dict):
                quotations = message.get("quotations", [])
                total      = message.get("total", len(quotations))
                has_next   = message.get("has_next", False)
            elif isinstance(message, list):
                print("[ExternalQtn] 'message' is a list — treating as quotations directly")
                quotations = message
                total      = len(quotations)
                has_next   = False
            else:
                quotations = data.get("quotations", data.get("data", []))
                total      = data.get("total", len(quotations))
                has_next   = data.get("has_next", False)
                print(f"[ExternalQtn] WARNING: unexpected message format, fell back to root keys")

            print(f"[ExternalQtn] ✅ Quotations on page : {len(quotations)}")
            print(f"[ExternalQtn]    Total (server)     : {total}")
            print(f"[ExternalQtn]    Has next page      : {has_next}")

            if quotations and isinstance(quotations[0], dict):
                print(f"[ExternalQtn] First quotation keys: {list(quotations[0].keys())}")
                print(f"[ExternalQtn] First quotation name: {quotations[0].get('name', '<no name>')}")

            return {"quotations": quotations, "total": total, "page": page, "has_next": has_next, "error": None}

    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = "<could not read body>"
        msg = f"HTTP {e.code} {e.reason}: {body[:500]}"
        print(f"[ExternalQtn] ❌ HTTPError: {msg}")
        if e.code == 401:
            print("[ExternalQtn] HINT: 401 = wrong API key or secret.")
        elif e.code == 403:
            print("[ExternalQtn] HINT: 403 = user has no permission to read Quotations.")
        elif e.code == 404:
            print("[ExternalQtn] HINT: 404 = endpoint does not exist on that site.")
        elif e.code == 500:
            print("[ExternalQtn] HINT: 500 = server-side error on the external site.")
        return _err(page, msg)

    except urllib.error.URLError as e:
        msg = f"Cannot reach external site ({url}): {e.reason}"
        print(f"[ExternalQtn] ❌ URLError: {msg}")
        return _err(page, msg)

    except TimeoutError:
        msg = f"Request timed out after {REQUEST_TIMEOUT}s — site may be slow or URL is wrong."
        print(f"[ExternalQtn] ❌ TIMEOUT: {msg}")
        return _err(page, msg)

    except Exception as e:
        msg = f"{type(e).__name__}: {e}"
        print(f"[ExternalQtn] ❌ Unexpected error: {msg}")
        traceback.print_exc()
        return _err(page, msg)


def _err(page: int, msg: str) -> dict:
    log.error(msg)
    return {"quotations": [], "total": 0, "page": page, "has_next": False, "error": msg}


# ---------------------------------------------------------------------------
# Save to local DB — with EXT- prefix to avoid name collisions
# ---------------------------------------------------------------------------

def save_external_quotations_locally(quotations_data: list) -> dict:
    """
    Save raw quotation dicts from external site into the local database.
    Each quotation name is prefixed with EXTERNAL_PREFIX ("EXT-") so it
    never collides with quotations from your own main Frappe site.
    """
    result = {"saved": 0, "skipped": 0, "errors": 0}
    print(f"[ExternalQtn] Saving {len(quotations_data)} records (prefix='{EXTERNAL_PREFIX}')…")

    try:
        from models.quotation import Quotation, save_quotation, get_all_quotations
        existing_names = {q.name for q in get_all_quotations()}
        print(f"[ExternalQtn] Existing local quotations: {len(existing_names)}")
    except Exception as e:
        print(f"[ExternalQtn] ❌ Cannot access local quotation model: {e}")
        traceback.print_exc()
        result["errors"] += len(quotations_data)
        return result

    for i, qtn_data in enumerate(quotations_data):
        original_name = qtn_data.get("name", f"<no-name-{i}>")

        # Apply prefix so this never collides with main-site quotations
        prefixed_name = EXTERNAL_PREFIX + original_name if not original_name.startswith(EXTERNAL_PREFIX) else original_name

        if prefixed_name in existing_names:
            print(f"[ExternalQtn]   [{i+1}] SKIP (already saved as '{prefixed_name}')")
            result["skipped"] += 1
            continue

        try:
            # Inject the prefixed name before building the model object
            qtn_data_copy = {**qtn_data, "name": prefixed_name}
            print(f"[ExternalQtn]   [{i+1}] Saving '{original_name}' → '{prefixed_name}'")

            quotation        = Quotation.from_dict(qtn_data_copy)
            quotation.synced = True   # pulled from remote — do not push back
            save_quotation(quotation)
            existing_names.add(prefixed_name)
            result["saved"] += 1
            print(f"[ExternalQtn]   [{i+1}] ✅ Saved as '{prefixed_name}'")

        except Exception as e:
            print(f"[ExternalQtn]   [{i+1}] ❌ Failed to save '{original_name}': {e}")
            traceback.print_exc()
            result["errors"] += 1

    print(f"[ExternalQtn] Save done — saved={result['saved']}  skipped={result['skipped']}  errors={result['errors']}")
    return result


# ---------------------------------------------------------------------------
# All-in-one entry point
# ---------------------------------------------------------------------------

def pull_all_external_quotations() -> dict:
    """Fetch ALL pages from the external site and save locally."""
    print("\n[ExternalQtn] ═══════════════════════════════════")
    print("[ExternalQtn]  pull_all_external_quotations() START")
    print(f"[ExternalQtn]  Name prefix for external records: '{EXTERNAL_PREFIX}'")
    print("[ExternalQtn] ═══════════════════════════════════")

    stats    = {"fetched": 0, "saved": 0, "skipped": 0, "errors": 0, "pages": 0, "error": None}
    page     = 1
    limit    = 100
    has_next = True

    while has_next:
        print(f"\n[ExternalQtn] ── Page {page} ──")
        response = fetch_quotations_from_external_site(page=page, limit=limit)

        if response.get("error"):
            stats["error"] = response["error"]
            print(f"[ExternalQtn] Stopping — error on page {page}: {response['error']}")
            break

        quotations_data  = response.get("quotations", [])
        stats["fetched"] += len(quotations_data)
        stats["pages"]   += 1

        if not quotations_data:
            print("[ExternalQtn] No quotations on this page — stopping pagination.")
            break

        save_result      = save_external_quotations_locally(quotations_data)
        stats["saved"]   += save_result["saved"]
        stats["skipped"] += save_result["skipped"]
        stats["errors"]  += save_result["errors"]

        has_next = response.get("has_next", False)
        page    += 1

    print(f"\n[ExternalQtn] ═══════════════════════════════════")
    print(f"[ExternalQtn]  DONE — fetched={stats['fetched']}  saved={stats['saved']}  "
          f"skipped={stats['skipped']}  errors={stats['errors']}  pages={stats['pages']}")
    if stats["error"]:
        print(f"[ExternalQtn]  ERROR: {stats['error']}")
    print(f"[ExternalQtn] ═══════════════════════════════════\n")

    return stats