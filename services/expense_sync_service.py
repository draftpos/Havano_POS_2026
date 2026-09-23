# =============================================================================
# services/expense_sync_service.py  -  SaaS Expense & Claims Cloud Sync Service
# =============================================================================
# Connects Havano POS Desk expenses to the SaaS backoffice cloud API:
#
#   GET  /api/resource/Expense Claim Type   -> Fetch categories
#   POST /api/resource/Expense Claim Type   -> Create category on the fly
#   POST /api/resource/Expense Claim        -> Submit expense (single / batch)
#   GET  /api/resource/Expense Claim        -> List recorded expenses
#
# IMPORTANT:
#   Runs ONLY when get_system_mode() == "saas".
#   In offline, frappe, or odoo modes, this service is inactive and records
#   remain local-only.
# =============================================================================

from __future__ import annotations

import json
import logging
import ssl
import threading
import time
import urllib.request
import urllib.parse
import urllib.error

from services.network_utils import safe_urlopen
from database.db import get_connection, fetchall_dicts

log = logging.getLogger("ExpenseSync")

REQUEST_TIMEOUT = 10
_sync_daemon_thread: threading.Thread | None = None
_sync_daemon_running: bool = False
_sync_lock = threading.Lock()


def is_saas_mode() -> bool:
    """Check if active system mode is 'saas'."""
    try:
        from services.credentials import get_system_mode
        return str(get_system_mode() or "").strip().lower() == "saas"
    except Exception:
        return False


def _get_api_context() -> tuple[str, str, int | str | None]:
    """
    Returns (host, token, store_id) for SaaS cloud requests.
    """
    from services.site_config import get_host
    from services.credentials import get_credentials
    from models.company_defaults import get_defaults

    host = ""
    try:
        host = get_host()
    except Exception:
        pass

    defaults = get_defaults() or {}
    if not host:
        host = str(defaults.get("server_api_host") or "").strip()

    if host and not host.startswith("http"):
        host = "https://" + host
    host = host.rstrip("/") if host else ""

    # Token resolution
    token = ""
    try:
        from services.auth_service import _session
        token = str(_session.get("token") or "").strip()
    except Exception:
        pass

    if not token:
        from services.credentials import build_auth_header
        api_key, api_secret = get_credentials()
        if api_key and api_secret:
            token = build_auth_header(api_key, api_secret)
        elif api_key:
            token = str(api_key or "").strip()

    # Store resolution
    store_id = defaults.get("server_shop_id") or defaults.get("store_id") or None
    if store_id:
        try:
            store_id = int(store_id)
        except (ValueError, TypeError):
            pass

    return host, token, store_id


def _get_headers(token: str) -> dict:
    """Build Authorization and Content-Type headers for cloud API."""
    hdrs = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if token:
        if token.lower().startswith("bearer ") or token.lower().startswith("token "):
            hdrs["Authorization"] = token
        else:
            hdrs["Authorization"] = f"Bearer {token}"
    return hdrs


def _create_ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


# =============================================================================
# 1. CATEGORIES: GET & POST /api/resource/Expense Claim Type
# =============================================================================

def fetch_cloud_expense_categories() -> list[dict]:
    """
    Fetch expense categories from cloud backoffice:
      GET /api/resource/Expense Claim Type
    Upserts results into local SQL table 'expense_categories'.
    Returns list of dicts: [{"name": ..., "expense_type": ..., ...}].
    Runs ONLY in SaaS mode.
    """
    if not is_saas_mode():
        return []

    host, token, _ = _get_api_context()
    if not host or not token:
        log.warning("[expense_sync] Cannot fetch categories: missing host or token.")
        return []

    url = f"{host}/api/resource/Expense%20Claim%20Type"
    headers = _get_headers(token)
    req = urllib.request.Request(url=url, headers=headers, method="GET")

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT, context=_create_ssl_context()) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            cat_list = data.get("data") or []
            if isinstance(cat_list, list):
                _upsert_local_categories(cat_list)
                log.info(f"[expense_sync] Fetched {len(cat_list)} expense categories from cloud.")
                return cat_list
    except Exception as e:
        log.warning(f"[expense_sync] Error fetching categories from {url}: {e}")

    return []


def _upsert_local_categories(categories: list[dict]):
    """Ensure local expense_categories table contains categories fetched from cloud."""
    if not categories:
        return
    try:
        from models.expense import ensure_expense_tables
        ensure_expense_tables()
        conn = get_connection()
        cur = conn.cursor()
        for cat in categories:
            name = (cat.get("expense_type") or cat.get("name") or "").strip()
            def_acc = (cat.get("default_account") or name).strip()
            desc = (cat.get("description") or "Expense Account").strip()
            if not name:
                continue
            cur.execute("""
                IF EXISTS (SELECT 1 FROM expense_categories WHERE LOWER(name) = LOWER(?))
                BEGIN
                    UPDATE expense_categories
                    SET default_account = ?, description = ?
                    WHERE LOWER(name) = LOWER(?)
                END
                ELSE
                BEGIN
                    INSERT INTO expense_categories (name, default_account, description)
                    VALUES (?, ?, ?)
                END
            """, (name, def_acc, desc, name, name, def_acc, desc))
        conn.commit()
        conn.close()
    except Exception as e:
        log.error(f"[expense_sync] Failed to cache categories in local DB: {e}")


def create_cloud_expense_category(expense_type: str) -> dict | None:
    """
    Create a new expense category on the fly in the cloud:
      POST /api/resource/Expense Claim Type
      Body: {"expense_type": "<name>"}
    Runs ONLY in SaaS mode.
    """
    if not is_saas_mode():
        return None

    name = str(expense_type or "").strip()
    if not name:
        return None

    host, token, _ = _get_api_context()
    if not host or not token:
        return None

    url = f"{host}/api/resource/Expense%20Claim%20Type"
    headers = _get_headers(token)
    payload = {"expense_type": name}
    body = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url=url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT, context=_create_ssl_context()) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            log.info(f"[expense_sync] Created cloud expense category '{name}': {data}")
            return data.get("data")
    except Exception as e:
        log.warning(f"[expense_sync] Failed to create cloud expense category '{name}': {e}")
        return None


# =============================================================================
# 2. EXPENSE SUBMISSION: POST /api/resource/Expense Claim
# =============================================================================

def post_cloud_expenses_batch(expenses_list: list[dict]) -> dict | None:
    """
    Submits one or more expenses to cloud:
      POST /api/resource/Expense Claim
    Accepts single object or batch with {"expenses": [...]}.
    Runs ONLY in SaaS mode.
    """
    if not is_saas_mode():
        return None

    if not expenses_list:
        return None

    host, token, default_store_id = _get_api_context()
    if not host or not token:
        raise RuntimeError("Missing cloud API host or authentication token.")

    formatted_expenses = []
    for item in expenses_list:
        amt = float(item.get("amount") or item.get("claim_amount") or 0.0)
        if amt <= 0:
            continue
        exp_type = item.get("expense_type") or item.get("category_name") or "General Expense"
        desc = item.get("description") or item.get("name") or exp_type
        paid_val = item.get("is_paid", True) if "is_paid" in item else item.get("paid", True)
        
        entry = {
            "expense_type": exp_type,
            "amount": amt,
            "description": desc,
            "is_paid": bool(paid_val),
            "account": item.get("account") or item.get("payment_method") or "Cash",
        }
        
        # Store
        s_id = item.get("store_id") or default_store_id
        if s_id is not None:
            entry["store_id"] = s_id
            
        # Shift
        sh_id = item.get("shift_id")
        if sh_id is not None:
            entry["shift_id"] = sh_id

        formatted_expenses.append(entry)

    if not formatted_expenses:
        return None

    payload = {"expenses": formatted_expenses} if len(formatted_expenses) > 1 else formatted_expenses[0]
    body = json.dumps(payload).encode("utf-8")
    url = f"{host}/api/resource/Expense%20Claim"
    headers = _get_headers(token)

    req = urllib.request.Request(url=url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT, context=_create_ssl_context()) as resp:
        resp_bytes = resp.read()
        resp_json = json.loads(resp_bytes.decode("utf-8"))
        log.info(f"[expense_sync] Expense POST response: {resp_json}")
        return resp_json.get("data") or resp_json


# =============================================================================
# 3. UNSYNCED EXPENSE PUSH & RECONCILIATION
# =============================================================================

def push_unsynced_expenses() -> int:
    """
    Finds all local expenses with synced = 0 (or NULL).
    In SaaS mode: sends them to cloud POST /api/resource/Expense Claim,
    and updates local records with synced=1, cloud_name, cloud_status.
    Returns the count of newly synced expenses.
    """
    if not is_saas_mode():
        return 0

    with _sync_lock:
        from models.expense import ensure_expense_tables
        ensure_expense_tables()

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT e.id, e.name, e.amount, e.paid, e.shift_id, e.expense_number,
                   COALESCE(c.name, 'Expense') AS category_name,
                   COALESCE(NULLIF(LTRIM(RTRIM(e.payment_method)), ''), 'Cash') AS payment_method
            FROM expenses e
            LEFT JOIN expense_categories c ON e.expense_category_id = c.id
            WHERE e.synced = 0 OR e.synced IS NULL
            ORDER BY e.id ASC
        """)
        unsynced_rows = fetchall_dicts(cur)
        conn.close()

        if not unsynced_rows:
            return 0

        log.info(f"[expense_sync] Found {len(unsynced_rows)} unsynced expense(s) to push.")

        batch_payload = []
        for row in unsynced_rows:
            batch_payload.append({
                "local_id": row["id"],
                "expense_type": row["category_name"],
                "amount": float(row["amount"]),
                "description": f"{row['expense_number'] or ''} - {row['name']}".strip(" -"),
                "is_paid": bool(row["paid"]),
                "account": row.get("payment_method") or "Cash",
                "shift_id": row.get("shift_id"),
            })

        try:
            cloud_res = post_cloud_expenses_batch(batch_payload)
            if not cloud_res:
                return 0

            # Parse returned cloud expenses
            # e.g. {"name": "EXP-2026-00012", "status": "Posted", "expenses": [{"id": 45, "name": "...", "status": "..."}], "requires_approval": false}
            cloud_exps = cloud_res.get("expenses") or []
            fallback_status = cloud_res.get("status") or ("Pending Approval" if cloud_res.get("requires_approval") else "Posted")
            fallback_name = cloud_res.get("name") or "EXP-POSTED"

            conn = get_connection()
            cur = conn.cursor()

            synced_count = 0
            for idx, item in enumerate(batch_payload):
                loc_id = item["local_id"]
                if idx < len(cloud_exps):
                    c_info = cloud_exps[idx]
                    c_name = c_info.get("name") or fallback_name
                    c_status = c_info.get("status") or fallback_status
                else:
                    c_name = fallback_name
                    c_status = fallback_status

                cur.execute("""
                    UPDATE expenses
                    SET synced = 1, cloud_name = ?, cloud_status = ?, sync_error = NULL
                    WHERE id = ?
                """, (c_name, c_status, loc_id))
                synced_count += 1

            conn.commit()
            conn.close()

            log.info(f"[expense_sync] Successfully pushed & updated {synced_count} expense(s) to cloud.")
            return synced_count

        except Exception as e:
            err_str = str(e)
            log.warning(f"[expense_sync] Error pushing expenses to cloud: {err_str}")
            # Mark sync_error on records
            try:
                conn = get_connection()
                cur = conn.cursor()
                for item in batch_payload:
                    cur.execute("UPDATE expenses SET sync_error = ? WHERE id = ?", (err_str[:400], item["local_id"]))
                conn.commit()
                conn.close()
            except Exception:
                pass
            return 0


# =============================================================================
# 4. BACKGROUND SYNC DAEMON
# =============================================================================

def start_expense_sync_daemon():
    """Start background worker to periodically push unsynced expenses in SaaS mode."""
    global _sync_daemon_thread, _sync_daemon_running
    if not is_saas_mode():
        return
    if _sync_daemon_thread and _sync_daemon_thread.is_alive():
        return

    _sync_daemon_running = True

    def _worker():
        while _sync_daemon_running:
            try:
                if is_saas_mode():
                    push_unsynced_expenses()
            except Exception as e:
                log.error(f"[expense_sync] Daemon push error: {e}")
            time.sleep(60)

    _sync_daemon_thread = threading.Thread(target=_worker, daemon=True, name="ExpenseSyncDaemon")
    _sync_daemon_thread.start()
    log.info("[expense_sync] Background expense sync daemon started.")


def stop_expense_sync_daemon():
    """Stop the background expense sync daemon."""
    global _sync_daemon_running
    _sync_daemon_running = False
    log.info("[expense_sync] Stop requested for expense sync daemon.")
