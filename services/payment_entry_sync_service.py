from __future__ import annotations

import json
import logging
import time
import threading
import urllib.request
import urllib.error
import urllib.parse
from datetime import date

log = logging.getLogger("PaymentEntrySync")

SYNC_INTERVAL   = 20
REQUEST_TIMEOUT = 60

_sync_lock  = threading.Lock()
_sync_thread: threading.Thread | None = None


def _get_credentials() -> tuple[str, str]:
    try:
        from services.credentials import get_credentials
        return get_credentials()
    except Exception:
        pass
    return "", ""


from services.site_config import get_host as _get_host


def _get_defaults() -> dict:
    try:
        from models.company_defaults import get_defaults
        return get_defaults() or {}
    except Exception:
        return {}


def _get_gl_account_currency(gl_account_name: str, fallback: str = "USD") -> str:
    if not gl_account_name:
        return fallback
    try:
        from models.gl_account import get_account_by_name
        acct = get_account_by_name(gl_account_name)
        if acct:
            return (acct.get("account_currency") or fallback).upper()
    except Exception:
        pass
    return fallback


def _resolve_mop(raw_method: str, gl_account: str, currency: str) -> tuple[str, str]:
    """
    Resolve (frappe_mop_name, gl_account_name).

    Priority:
      1. Exact GL account match
      2. Exact MOP name match
      3. Fuzzy / partial name match  ← FIXES "Bank Accounts" → Cash bug
      4. Currency fallback           ← only when method name is truly empty

    The currency fallback is intentionally blocked when a method name exists
    so that an unrecognised bank method never silently becomes Cash.
    """
    from database.db import get_connection, fetchone_dict

    if not raw_method:
        raw_method = ""

    conn = get_connection()
    cur  = conn.cursor()

    try:
        # 1. Exact GL account
        if gl_account:
            cur.execute(
                "SELECT name, gl_account FROM modes_of_payment WHERE gl_account = ?",
                (gl_account,)
            )
            row = fetchone_dict(cur)
            if row:
                log.debug("MOP by gl_account: %s → %s", gl_account, row["name"])
                return row["name"], row["gl_account"]

        # 2. Exact name
        if raw_method:
            cur.execute(
                "SELECT name, gl_account FROM modes_of_payment WHERE name = ?",
                (raw_method,)
            )
            row = fetchone_dict(cur)
            if row and row.get("gl_account"):
                log.debug("MOP by exact name: %s → %s", raw_method, row["gl_account"])
                return row["name"], row["gl_account"]

        # 3. Fuzzy match — handles "Bank Accounts" ↔ "Bank" etc.
        # Reduced aggressiveness: only if one is a full substring of the other
        # and we don't already have a match.
        if raw_method and len(raw_method) > 2:
            cur.execute(
                "SELECT name, gl_account FROM modes_of_payment "
                "WHERE gl_account IS NOT NULL AND gl_account != ''"
            )
            all_mops = cur.fetchall()
            method_lower = raw_method.lower()
            for mop_name, mop_gl in all_mops:
                if not mop_name:
                    continue
                mop_lower = mop_name.lower()
                # Strict check: "Bank" (local) should match "Bank - USD" (Frappe)
                # but "Cash" should not match "Bank Cash".
                if (mop_lower == method_lower):
                    return mop_name, mop_gl
                    
        # 4. Currency fallback — ONLY when method name is truly missing or Generic
        if (not raw_method or raw_method.lower() == "cash") and currency:
            cur.execute(
                """
                SELECT name, gl_account FROM modes_of_payment
                WHERE account_currency = ?
                  AND gl_account IS NOT NULL AND gl_account != ''
                """,
                (currency.upper(),)
            )
            rows = cur.fetchall()
            if rows:
                mop_name, mop_gl = rows[0]
                log.warning("MOP currency fallback (%s): '%s'", currency, mop_name)
                return mop_name, mop_gl

    except Exception as e:
        log.error("MOP resolution error: %s", e)
    finally:
        conn.close()

    log.warning("No MOP found for method='%s' — using raw name.", raw_method)
    return raw_method or "Cash", gl_account or ""


def _fetch_receivable_account(customer: str, company: str,
                               api_key: str, api_secret: str, host: str) -> str | None:
    """
    Fetch the per-customer receivable (Debtors) account from Frappe.
    Without this every Payment Entry collapses into the company-wide default.
    """
    if not customer or not company:
        return None
    try:
        url = (
            f"{host}/api/method/erpnext.accounts.party.get_party_account"
            f"?party_type=Customer"
            f"&party={urllib.parse.quote(customer)}"
            f"&company={urllib.parse.quote(company)}"
        )
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"token {api_key}:{api_secret}")
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
            data = json.loads(r.read().decode())
            acct = (data.get("message") or data.get("result") or "").strip()
            if acct:
                log.debug("Receivable account for '%s': %s", customer, acct)
                return acct
    except Exception as e:
        log.debug("Could not fetch receivable account for '%s': %s", customer, e)
    return None


# =============================================================================
# LOCAL DB
# =============================================================================

def get_unsynced_payment_entries() -> list[dict]:
    from database.db import get_connection, fetchall_dicts
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT pe.*, s.frappe_ref AS sale_frappe_ref
        FROM payment_entries pe
        LEFT JOIN sales s ON s.id = pe.sale_id
        WHERE pe.synced = 0
          AND (pe.sync_attempts IS NULL OR pe.sync_attempts < 60)
          AND (pe.frappe_invoice_ref IS NOT NULL OR s.frappe_ref IS NOT NULL)
        ORDER BY ISNULL(pe.sync_attempts, 0) ASC, pe.id DESC
    """)
    rows = fetchall_dicts(cur)
    conn.close()
    return rows


def mark_payment_synced(pe_id: int, frappe_payment_ref: str = "") -> None:
    from database.db import get_connection
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(
        "UPDATE payment_entries SET synced=1, frappe_payment_ref=? WHERE id=?",
        (frappe_payment_ref or None, pe_id)
    )
    cur.execute("""
        UPDATE sales SET payment_entry_ref=?, payment_synced=1
        WHERE id = (SELECT sale_id FROM payment_entries WHERE id=?)
    """, (frappe_payment_ref or None, pe_id))
    conn.commit()
    conn.close()


def refresh_frappe_refs() -> int:
    from database.db import get_connection
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        UPDATE pe
        SET pe.frappe_invoice_ref = s.frappe_ref
        FROM payment_entries pe
        JOIN sales s ON s.id = pe.sale_id
        WHERE pe.synced = 0
          AND (pe.frappe_invoice_ref IS NULL OR pe.frappe_invoice_ref = '')
          AND s.frappe_ref IS NOT NULL AND s.frappe_ref != ''
    """)
    count = cur.rowcount
    conn.commit()
    conn.close()
    return count


def _increment_sync_attempt(pe_id: int, error_msg: str):
    try:
        from database.db import get_connection
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute("""
            UPDATE payment_entries
            SET sync_attempts   = ISNULL(sync_attempts, 0) + 1,
                last_error      = ?,
                sync_error      = ?,
                last_attempt_at = GETDATE()
            WHERE id = ?
        """, (str(error_msg)[:500], str(error_msg), pe_id))
        conn.commit()
        conn.close()
    except Exception as ex:
        log.debug("Failed to increment sync attempt: %s", ex)


# =============================================================================
# BUILD PAYLOAD
# =============================================================================

def _build_payload(pe: dict, defaults: dict,
                   api_key: str, api_secret: str, host: str) -> dict:
    company       = defaults.get("server_company", "")
    base_currency = (defaults.get("server_company_currency", "USD") or "USD").strip().upper()

    if pe.get("payment_type") == "Pay":
        try:
            from services.cn_payment_entry_service import _build_cn_payload
            return _build_cn_payload(pe, defaults, api_key, api_secret, host)
        except Exception as e:
            log.error("[build_payload] CN delegation failed: %s", e)

    currency = (
        pe.get("currency") or
        pe.get("paid_to_account_currency") or
        base_currency
    ).upper()

    stored_amount_usd = float(pe.get("amount_usd") or 0)
    native_amount     = float(pe.get("paid_amount") or 0)
    exch_rate         = float(pe.get("exchange_rate") or pe.get("source_exchange_rate") or 0)

    frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()
    stored_mop = (pe.get("mode_of_payment") or "").strip()
    paid_to    = (pe.get("paid_to") or "").strip()
    mop_name, gl_account = _resolve_mop(stored_mop, paid_to, currency)

    paid_to_currency = _get_gl_account_currency(
        gl_account, fallback=currency if currency != "USD" else base_currency
    )

    if currency in ("ZWD", "ZWG"):
        if exch_rate <= 0:
            exch_rate = 1.0
        elif exch_rate > 1:
            exch_rate = 1.0 / exch_rate
        paid_amount_for_frappe     = round(native_amount * exch_rate, 4)
        received_amount_for_frappe = native_amount
        source_exch_rate           = exch_rate
        target_exch_rate           = 1.0
        log.info("[build_payload] ZWD: %.4f × %.6f = %.4f USD",
                 native_amount, exch_rate, paid_amount_for_frappe)

    elif currency == "USD" and paid_to_currency in ("ZWD", "ZWG", "ZIG"):
        try:
            from models.exchange_rate import get_rate
            rate = get_rate(paid_to_currency, "USD")
            raw_rate = (1.0 / rate) if (rate and 0 < rate < 1) else (rate or 1.0)
        except Exception:
            raw_rate = 1.0
        paid_amount_for_frappe     = native_amount
        received_amount_for_frappe = round(native_amount * raw_rate, 4)
        source_exch_rate           = 1.0
        target_exch_rate           = raw_rate

    else:
        paid_amount_for_frappe     = stored_amount_usd if stored_amount_usd > 0 else native_amount
        received_amount_for_frappe = paid_amount_for_frappe
        source_exch_rate           = 1.0
        target_exch_rate           = 1.0

    # Party
    _walk_in         = defaults.get("server_walk_in_customer", "").strip() or "Default"
    _WALK_IN_ALIASES = {"walk-in", "walk in", "walkin", ""}
    raw_party        = (pe.get("party") or "").strip()
    party            = _walk_in if raw_party.lower() in _WALK_IN_ALIASES else raw_party or _walk_in

    # Per-customer receivable account (paid_from)
    paid_from_account = _fetch_receivable_account(party, company, api_key, api_secret, host)
    if not paid_from_account:
        paid_from_account = defaults.get("server_receivable_account", "").strip() or None
        if paid_from_account:
            log.debug("Fallback receivable account '%s' for '%s'.", paid_from_account, party)
        else:
            log.warning("No receivable account for '%s' — Frappe will use its default.", party)

    log.info(
        "[build_payload] PE=%d  party='%s'  paid_from='%s'  MOP='%s'  GL='%s'  "
        "currency=%s  paid=%.4f  received=%.4f  inv=%s",
        pe.get("id", 0), party, paid_from_account or "(frappe default)",
        mop_name, gl_account, currency,
        paid_amount_for_frappe, received_amount_for_frappe, frappe_inv or "MISSING",
    )

    if not frappe_inv:
        log.warning("[build_payload] PE %d has no frappe_invoice_ref — will be skipped.", pe.get("id", 0))

    payload: dict = {
        "doctype":                    "Payment Entry",
        "payment_type":               "Receive",
        "party_type":                 "Customer",
        "party":                      party,
        "party_name":                 party,
        "paid_from_account_currency": base_currency,
        "paid_to_account_currency":   paid_to_currency,
        "paid_amount":                paid_amount_for_frappe,
        "received_amount":            received_amount_for_frappe,
        "source_exchange_rate":       source_exch_rate,
        "target_exchange_rate":       target_exch_rate,
        "mode_of_payment":            mop_name,
        "reference_no":               pe.get("reference_no") or pe.get("sale_invoice_no", ""),
        "reference_date": (
            pe.get("reference_date").isoformat()
            if hasattr(pe.get("reference_date"), "isoformat")
            else pe.get("reference_date") or date.today().isoformat()
        ),
        "remarks": (
            pe.get("remarks") or
            f"POS Payment — {mop_name} | "
            f"{currency} {received_amount_for_frappe:.2f} = USD {paid_amount_for_frappe:.2f}"
        ),
        "docstatus": 1,
    }

    if paid_from_account:
        payload["paid_from"] = paid_from_account   # ← per-customer Debtors account
    if gl_account:
        payload["paid_to"] = gl_account
    if company:
        payload["company"] = company

    cost_center = defaults.get("server_cost_center", "").strip()
    if cost_center:
        payload["cost_center"] = cost_center

    if frappe_inv:
        payload["references"] = [{
            "reference_doctype": "Sales Invoice",
            "reference_name":    frappe_inv,
            "allocated_amount":  paid_amount_for_frappe,
        }]

    return payload


# =============================================================================
# PUSH ONE PAYMENT ENTRY
# =============================================================================

def _push_payment_entry(pe: dict, api_key: str, api_secret: str,
                        defaults: dict, host: str) -> str | None:
    pe_id  = pe["id"]
    inv_no = pe.get("sale_invoice_no", str(pe_id))

    frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()
    if not frappe_inv:
        log.warning("Payment %d — Sales Invoice not yet on Frappe, skipping.", pe_id)
        return None

    payload = _build_payload(pe, defaults, api_key, api_secret, host)

    log.info("Pushing PE %d: %s %.2f %s",
             pe_id, inv_no, float(pe.get("paid_amount", 0)), pe.get("currency", ""))

    url = f"{host}/api/resource/Payment%20Entry"
    req = urllib.request.Request(
        url=url,
        data=json.dumps(
            payload,
            default=lambda o: o.isoformat() if hasattr(o, "isoformat") else str(o)
        ).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type":  "application/json",
            "Accept":        "application/json",
            "Authorization": f"token {api_key}:{api_secret}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
            name = (data.get("data") or {}).get("name", "")
            log.info("✅ PE %d → Frappe %s", pe_id, name)
            return name or "SYNCED"

    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode())
            msg = (err.get("exception") or err.get("message") or
                   str(err.get("_server_messages", "")) or f"HTTP {e.code}")
        except Exception:
            msg = f"HTTP {e.code}"

        if e.code == 409:
            log.info("PE %d already on Frappe (409).", pe_id)
            return "DUPLICATE"

        if e.code == 417:
            _perma = ("already been fully paid", "already paid", "fully paid",
                      "allocated amount cannot be greater than outstanding amount")
            if any(p in msg.lower() for p in _perma):
                log.info("PE %d — invoice already paid.", pe_id)
                return "ALREADY_PAID"

        log.error("FAIL PE %d HTTP %s: %s", pe_id, e.code, msg[:200])
        _increment_sync_attempt(pe_id, f"HTTP {e.code}: {msg[:200]}")
        return None

    except urllib.error.URLError as e:
        log.warning("Network error pushing PE %d: %s", pe_id, e.reason)
        _increment_sync_attempt(pe_id, f"Network: {e.reason}")
        return None

    except Exception as e:
        log.error("Unexpected error pushing PE %d: %s", pe_id, e)
        _increment_sync_attempt(pe_id, str(e))
        return None


# =============================================================================
# PUBLIC
# =============================================================================

def push_unsynced_payment_entries() -> dict:
    result = {"pushed": 0, "failed": 0, "skipped": 0, "total": 0}

    api_key, api_secret = _get_credentials()
    if not api_key or not api_secret:
        log.warning("No credentials — skipping payment entry sync.")
        return result

    host     = _get_host()
    defaults = _get_defaults()

    updated = refresh_frappe_refs()
    if updated:
        log.info("Refreshed frappe_invoice_ref on %d PE(s).", updated)

    entries = get_unsynced_payment_entries()
    result["total"] = len(entries)

    if not entries:
        log.debug("No unsynced payment entries.")
        return result

    log.info("Pushing %d payment entry(ies) to Frappe…", len(entries))

    for pe in entries:
        attempts = pe.get("sync_attempts") or 0
        time.sleep(min(1 + attempts, 5))

        frappe_name = _push_payment_entry(pe, api_key, api_secret, defaults, host)
        if frappe_name:
            mark_payment_synced(pe["id"], frappe_name)
            result["pushed"] += 1
        elif frappe_name is None:
            result["skipped"] += 1
        else:
            result["failed"] += 1
        time.sleep(3)

    log.info("Payment sync done — ✅ %d pushed  ❌ %d failed  ⏭ %d skipped",
             result["pushed"], result["failed"], result["skipped"])
    return result


# =============================================================================
# BACKGROUND DAEMON
# =============================================================================

def _sync_loop():
    log.info("Payment entry sync daemon started (interval=%ds).", SYNC_INTERVAL)
    while True:
        if _sync_lock.acquire(blocking=False):
            try:
                push_unsynced_payment_entries()
            except Exception as e:
                log.error("Payment sync cycle error: %s", e)
            finally:
                _sync_lock.release()
        else:
            log.debug("Previous payment sync still running — skipping.")
        time.sleep(SYNC_INTERVAL)


def start_payment_sync_daemon() -> threading.Thread:
    global _sync_thread
    if _sync_thread and _sync_thread.is_alive():
        return _sync_thread
    t = threading.Thread(target=_sync_loop, daemon=True, name="PaymentSyncDaemon")
    t.start()
    _sync_thread = t
    log.info("Payment entry sync daemon started.")
    return t


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    print("Running one payment entry sync cycle...")
    r = push_unsynced_payment_entries()
    print(f"\nResult: {r['pushed']} pushed, {r['failed']} failed, "
          f"{r['skipped']} skipped (of {r['total']} total)")