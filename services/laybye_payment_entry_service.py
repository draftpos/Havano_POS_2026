# =============================================================================
# services/laybye_payment_entry_service.py
#
# Creates and syncs Payment Entries for Laybye (Sales Order) deposits.
#
# The POST payload is built to EXACTLY match the Flutter _syncSinglePaymentEntry
# implementation:
#
#   doctype            = 'Payment Entry'
#   payment_type       = 'Receive'
#   party_type         = 'Customer'
#   party              = order.customer_id      (ERPNext customer name / id)
#   party_name         = order.customer_name
#   paid_to            = account_paid_to        (company cash/bank account)
#   paid_to_account_currency   = account_currency
#   paid_from_account_currency = account_currency
#   paid_amount        = round(deposit_amount, decimals)
#   paid_amount_after_tax      = same
#   received_amount    = round(deposit_amount, decimals)   # same field, base ccy
#   received_amount_after_tax  = same
#   reference_no       = deposit_method (or '')
#   reference_date     = today ISO
#   remarks            = 'Laybye deposit — <order_no>'
#   docstatus          = 1  (submit directly)
#
# If the sales order has a Frappe Sales Order ref (frappe_ref), a
# 'references' block is added just like the Flutter code adds a Sales Invoice
# reference when invoiceOnlineId is set.
# =============================================================================

from __future__ import annotations
import logging
import requests
from datetime import date, datetime

log = logging.getLogger("laybye_payment_entry_service")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_conn():
    from database.db import get_connection
    return get_connection()


def _get_credentials() -> tuple[str, str]:
    """Return (api_key, api_secret) from company_defaults."""
    try:
        from models.company_defaults import get_defaults
        d = get_defaults() or {}
        return d.get("api_key", ""), d.get("api_secret", "")
    except Exception:
        return "", ""


def _get_host() -> str:
    try:
        from services.site_config import get_host_label
        host = get_host_label()
        if host and not host.startswith("http"):
            host = "https://" + host
        return host.rstrip("/")
    except Exception:
        return ""


def _get_float_precision() -> int:
    """Read float precision from company defaults (mirrors Flutter getFloatValue)."""
    try:
        from models.company_defaults import get_defaults
        d = get_defaults() or {}
        return int(d.get("float_precision", 2) or 2)
    except Exception:
        return 2


def _get_account_paid_to(company: str, currency: str = "USD") -> tuple[str, str]:
    """
    Return (account_name, account_currency) for the company's default
    cash/bank account that matches the given currency.
    Falls back to the first cash account found.
    """
    try:
        from models.gl_account import get_all_accounts
        accounts = get_all_accounts()
        # Prefer exact currency + company match
        for a in accounts:
            if (
                a.get("company") == company
                and (a.get("account_currency") or "USD").upper() == currency.upper()
                and a.get("account_type", "").lower() in ("cash", "bank", "")
            ):
                return a.get("account_name") or a.get("name") or "", (a.get("account_currency") or "USD").upper()
        # Any account for this company
        for a in accounts:
            if a.get("company") == company:
                return a.get("account_name") or a.get("name") or "", (a.get("account_currency") or "USD").upper()
        # Fallback: first account
        if accounts:
            a = accounts[0]
            return a.get("account_name") or a.get("name") or "", (a.get("account_currency") or "USD").upper()
    except Exception:
        pass
    return "", "USD"


def _ensure_laybye_pe_table():
    """
    Ensure the laybye_payment_entries table exists for tracking sync state.

    Columns:
        id              INT PK IDENTITY
        sales_order_id  INT  (FK → sales_order.id)
        order_no        NVARCHAR(100)
        customer_id     NVARCHAR(255)   (ERPNext customer name)
        customer_name   NVARCHAR(255)
        deposit_amount  FLOAT
        deposit_method  NVARCHAR(100)
        account_paid_to NVARCHAR(255)
        account_currency NVARCHAR(20)
        frappe_so_ref   NVARCHAR(255)   (ERPNext Sales Order name, if synced)
        frappe_pe_ref   NVARCHAR(255)   (Payment Entry name returned by ERPNext)
        status          NVARCHAR(50)    DEFAULT 'pending'
        sync_attempts   INT             DEFAULT 0
        created_at      NVARCHAR(50)
        last_attempt_at NVARCHAR(50)
        error_message   NVARCHAR(MAX)
    """
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM sys.objects WHERE object_id = OBJECT_ID('laybye_payment_entries') AND type = 'U'"
    )
    if cur.fetchone() is None:
        cur.execute("""
            CREATE TABLE laybye_payment_entries (
                id               INT           PRIMARY KEY IDENTITY(1,1),
                sales_order_id   INT           NOT NULL,
                order_no         NVARCHAR(100) NOT NULL DEFAULT '',
                customer_id      NVARCHAR(255) NOT NULL DEFAULT '',
                customer_name    NVARCHAR(255) NOT NULL DEFAULT '',
                deposit_amount   FLOAT         NOT NULL DEFAULT 0,
                deposit_method   NVARCHAR(100) NOT NULL DEFAULT '',
                account_paid_to  NVARCHAR(255) NOT NULL DEFAULT '',
                account_currency NVARCHAR(20)  NOT NULL DEFAULT 'USD',
                frappe_so_ref    NVARCHAR(255) NOT NULL DEFAULT '',
                frappe_pe_ref    NVARCHAR(255) NOT NULL DEFAULT '',
                status           NVARCHAR(50)  NOT NULL DEFAULT 'pending',
                sync_attempts    INT           NOT NULL DEFAULT 0,
                created_at       NVARCHAR(50)  NOT NULL DEFAULT '',
                last_attempt_at  NVARCHAR(50)  NOT NULL DEFAULT '',
                error_message    NVARCHAR(MAX) NOT NULL DEFAULT ''
            )
        """)
        conn.commit()
        log.info("Created table: laybye_payment_entries")
    return conn


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_laybye_payment_entry(order: dict) -> int | None:
    """
    Queue a Payment Entry record for a Laybye deposit.
    Called immediately after the Sales Order is saved locally.

    Parameters
    ----------
    order : dict
        A sales_order row (as returned by get_order_by_id), containing at
        minimum: id, order_no, customer_id, customer_name, deposit_amount,
        deposit_method, frappe_ref (may be empty).

    Returns
    -------
    The new laybye_payment_entries.id, or None on failure.
    """
    if not order:
        return None

    deposit_amount = float(order.get("deposit_amount") or 0)
    if deposit_amount <= 0:
        log.info("Skipping PE queue — deposit_amount is 0 for order %s", order.get("order_no"))
        return None

    company = order.get("company") or ""
    deposit_method = order.get("deposit_method") or ""

    # Determine account_paid_to from GL accounts
    account_paid_to, account_currency = _get_account_paid_to(company)

    try:
        conn = _ensure_laybye_pe_table()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO laybye_payment_entries
                (sales_order_id, order_no, customer_id, customer_name,
                 deposit_amount, deposit_method,
                 account_paid_to, account_currency,
                 frappe_so_ref, status, created_at)
            OUTPUT INSERTED.id
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            int(order["id"]),
            order.get("order_no") or "",
            order.get("customer_id") or order.get("customer_name") or "",
            order.get("customer_name") or "",
            deposit_amount,
            deposit_method,
            account_paid_to,
            account_currency,
            order.get("frappe_ref") or "",
            "pending",
            datetime.now().isoformat(timespec="seconds"),
        ))
        pe_id = cur.fetchone()[0]
        conn.commit()
        log.info("Queued laybye PE id=%d for order %s deposit=%.2f",
                 pe_id, order.get("order_no"), deposit_amount)
        return pe_id
    except Exception as exc:
        log.error("create_laybye_payment_entry failed: %s", exc)
        return None


def sync_laybye_payment_entries():
    """
    Background daemon call — push all pending laybye payment entries to ERPNext.
    Matches the Flutter _syncSinglePaymentEntry payload EXACTLY.
    """
    try:
        conn = _ensure_laybye_pe_table()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, sales_order_id, order_no, customer_id, customer_name,
                   deposit_amount, deposit_method,
                   account_paid_to, account_currency,
                   frappe_so_ref, sync_attempts
            FROM   laybye_payment_entries
            WHERE  status IN ('pending', 'retry')
            AND    sync_attempts < 5
            ORDER  BY id ASC
        """)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        pending = [dict(zip(cols, r)) for r in rows]
    except Exception as exc:
        log.error("sync_laybye_payment_entries — DB read failed: %s", exc)
        return

    if not pending:
        return

    api_key, api_secret = _get_credentials()
    host = _get_host()

    if not api_key or not host:
        log.warning("sync_laybye_payment_entries — missing credentials or host, skipping.")
        return

    for pe in pending:
        _sync_single(pe, api_key, api_secret, host)


def _sync_single(pe: dict, api_key: str, api_secret: str, host: str):
    """
    Push one pending laybye payment entry to ERPNext.

    The payload is constructed to match the Flutter _syncSinglePaymentEntry
    implementation field-for-field.
    """
    pe_id = pe["id"]
    order_no = pe.get("order_no") or ""
    conn = _get_conn()

    # ── Increment sync attempts first (mirrors Flutter incrementSyncAttempts) ──
    try:
        conn.execute(
            """
            UPDATE laybye_payment_entries
            SET    sync_attempts    = sync_attempts + 1,
                   last_attempt_at  = ?
            WHERE  id = ?
            """,
            (datetime.now().isoformat(timespec="seconds"), pe_id),
        )
        conn.commit()
    except Exception as exc:
        log.warning("Could not increment sync_attempts for PE %d: %s", pe_id, exc)

    # ── Float precision (mirrors Flutter getFloatValue) ──────────────────────
    decimals = _get_float_precision()

    def _round(value: float) -> float:
        return round(value, decimals)

    deposit_amount   = float(pe.get("deposit_amount") or 0)
    account_paid_to  = pe.get("account_paid_to") or ""
    account_currency = (pe.get("account_currency") or "USD").upper()
    customer_id      = pe.get("customer_id") or ""
    customer_name    = pe.get("customer_name") or ""
    deposit_method   = pe.get("deposit_method") or ""
    frappe_so_ref    = pe.get("frappe_so_ref") or ""

    # ── Build payload — EXACT mirror of Flutter _syncSinglePaymentEntry ───────
    payment_data: dict = {
        "doctype":                      "Payment Entry",
        "payment_type":                 "Receive",
        "party_type":                   "Customer",
        "party":                        customer_id,
        "party_name":                   customer_name,
        "paid_to":                      account_paid_to,   # Company account receiving payment
        "paid_to_account_currency":     account_currency,
        "paid_from_account_currency":   account_currency,
        "paid_amount":                  _round(deposit_amount),   # Amount in payment currency
        "paid_amount_after_tax":        _round(deposit_amount),
        "received_amount":              _round(deposit_amount),   # Amount in account currency
        "received_amount_after_tax":    _round(deposit_amount),
        "reference_no":                 deposit_method or "",
        "reference_date":               date.today().isoformat(),
        "remarks":                      f"Laybye deposit — {order_no}" if order_no else "Payment from POS",
        "docstatus":                    1,   # Submit directly
    }

    # ── Add Sales Order reference if the SO has been synced to ERPNext ────────
    # (mirrors Flutter: add 'references' block when invoiceOnlineId is set)
    if frappe_so_ref:
        # allocated_amount = deposit in base currency (mirrors Flutter baseAmount usage)
        allocated_amount = _round(deposit_amount)
        payment_data["references"] = [
            {
                "reference_doctype": "Sales Order",
                "reference_name":    frappe_so_ref,
                "allocated_amount":  allocated_amount,
            }
        ]
        log.info("PE %d — allocated_amount: %.4f (SO ref: %s)", pe_id, allocated_amount, frappe_so_ref)

    log.info("PE %d — payload: %s", pe_id, payment_data)

    # ── POST to ERPNext ───────────────────────────────────────────────────────
    url = f"{host}/api/resource/Payment Entry"
    headers = {
        "Authorization": f"token {api_key}:{api_secret}",
        "Content-Type":  "application/json",
    }

    try:
        response = requests.post(url, json=payment_data, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        frappe_pe_name = (data.get("data") or {}).get("name") or ""

        # ── Mark as synced ────────────────────────────────────────────────────
        conn.execute(
            """
            UPDATE laybye_payment_entries
            SET    status          = 'synced',
                   frappe_pe_ref   = ?,
                   last_attempt_at = ?
            WHERE  id = ?
            """,
            (frappe_pe_name, datetime.now().isoformat(timespec="seconds"), pe_id),
        )
        conn.commit()
        log.info("PE %d synced → Frappe PE: %s", pe_id, frappe_pe_name)

    except requests.HTTPError as exc:
        body = ""
        try:
            body = exc.response.text[:500]
        except Exception:
            pass
        error_msg = f"HTTP {exc.response.status_code}: {body}"
        log.error("PE %d HTTP error: %s", pe_id, error_msg)
        _mark_failed(conn, pe_id, error_msg, pe.get("sync_attempts", 0) + 1)

    except Exception as exc:
        error_msg = str(exc)[:500]
        log.error("PE %d sync error: %s", pe_id, error_msg)
        _mark_failed(conn, pe_id, error_msg, pe.get("sync_attempts", 0) + 1)


def _mark_failed(conn, pe_id: int, error_msg: str, attempts: int):
    """Set status to 'retry' (< 5 attempts) or 'failed' (≥ 5)."""
    status = "failed" if attempts >= 5 else "retry"
    try:
        conn.execute(
            """
            UPDATE laybye_payment_entries
            SET    status          = ?,
                   error_message   = ?,
                   last_attempt_at = ?
            WHERE  id = ?
            """,
            (status, error_msg, datetime.now().isoformat(timespec="seconds"), pe_id),
        )
        conn.commit()
    except Exception as exc:
        log.error("_mark_failed: could not update PE %d: %s", pe_id, exc)


# ---------------------------------------------------------------------------
# Background daemon (called from MainWindow startup)
# ---------------------------------------------------------------------------

def start_laybye_pe_sync_daemon():
    """
    Start a background thread that polls for pending laybye payment entries
    every 60 seconds and pushes them to ERPNext.
    """
    import threading
    import time

    def _loop():
        while True:
            try:
                sync_laybye_payment_entries()
            except Exception as exc:
                log.error("laybye_pe_sync_daemon error: %s", exc)
            time.sleep(60)

    t = threading.Thread(target=_loop, daemon=True, name="laybye_pe_sync")
    t.start()
    log.info("Laybye Payment Entry sync daemon started.")
    return t