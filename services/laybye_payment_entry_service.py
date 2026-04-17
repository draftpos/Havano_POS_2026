# =============================================================================
# services/laybye_payment_entry_service.py
#
# Records laybye deposit Payment Entries in a local queue table,
# then syncs them to Frappe via /api/resource/Payment Entry.
#
# SYNC STRATEGY: iterate rows one by one in order, push each to Frappe.
# No split tracking needed on sync — we just push whatever is in the table.
# =============================================================================

from __future__ import annotations
import logging
import json
import threading
import time
from datetime import date, datetime

log = logging.getLogger("laybye_payment_entry_service")

SYNC_INTERVAL = 20          # Check for unsynced entries frequently
REQUEST_TIMEOUT = 60        # Higher timeout for slow connections
MAX_SYNC_ATTEMPTS = 60      # Keep retrying for up to 60 times

_sync_lock   = threading.Lock()
_sync_thread: threading.Thread | None = None


# =============================================================================
# Internal helpers
# =============================================================================

def _get_conn():
    from database.db import get_connection
    return get_connection()


def _get_credentials() -> tuple[str, str]:
    try:
        from services.credentials import get_credentials
        return get_credentials()
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


def _get_defaults() -> dict:
    try:
        from models.company_defaults import get_defaults
        return get_defaults() or {}
    except Exception:
        return {}


def _get_gl_account_currency(gl_account_name: str, fallback: str = "USD") -> str:
    """Return the account_currency for a GL account from the local gl_accounts table."""
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


# =============================================================================
# MOP / GL account resolution  — mirrors payment_entry_service exactly
# =============================================================================

def _resolve_mop(raw_method: str, gl_account: str, currency: str) -> tuple[str, str]:
    """
    Given the raw method name from the payment and optional gl_account hint,
    return (frappe_mop_name, gl_account_name).

    Resolution order (same as payment_entry_service):
      1. gl_account direct match in modes_of_payment
      2. Exact name match
      3. Currency match
      4. Fallback — return raw_method with whatever gl_account was passed in
    """
    from database.db import get_connection, fetchone_dict

    if not raw_method:
        raw_method = "Cash"

    conn = get_connection()
    cur  = conn.cursor()

    try:
        # 1. By gl_account
        if gl_account:
            cur.execute(
                "SELECT name, gl_account FROM modes_of_payment WHERE gl_account = ?",
                (gl_account,)
            )
            row = fetchone_dict(cur)
            if row:
                log.debug("MOP resolved by gl_account: %s -> %s", gl_account, row["name"])
                return row["name"], row["gl_account"]

        # 2. Exact name match
        cur.execute(
            "SELECT name, gl_account FROM modes_of_payment WHERE name = ?",
            (raw_method,)
        )
        row = fetchone_dict(cur)
        if row and row.get("gl_account"):
            log.debug("MOP resolved by exact name: %s -> %s", raw_method, row["gl_account"])
            return row["name"], row["gl_account"]

        # 3. Currency match
        if currency:
            cur.execute("""
                SELECT name, gl_account FROM modes_of_payment
                WHERE account_currency = ? AND gl_account IS NOT NULL AND gl_account != ''
            """, (currency.upper(),))
            rows = cur.fetchall()
            if rows:
                mop_name, mop_gl = rows[0]
                log.debug("MOP resolved by currency %s: %s -> %s", currency, mop_name, mop_gl)
                return mop_name, mop_gl

    except Exception as e:
        log.error("MOP resolution error: %s", e)
    finally:
        conn.close()

    log.warning("No MOP found for method='%s', using fallback", raw_method)
    return raw_method, gl_account


# =============================================================================
# Amount resolution  — mirrors payment_entry_service exactly
# =============================================================================

def _resolve_amounts(deposit: dict, override_rate: float = None) -> dict:
    """
    Resolve currency amounts for a laybye deposit payment entry.

    CONVENTION (same as payment_entry_service):
      paid_amount      = USD basis figure
      exchange_rate    = LOCAL units per 1 USD  (e.g. 30 ZIG = 1 USD → rate = 30)
      received_amount  = paid_amount * exchange_rate  (LOCAL currency figure)

    For USD:  exchange_rate = 1.0, received_amount == paid_amount.

    Returns dict with: currency, amount, amount_usd, amount_zwd, amount_zwg,
                       exchange_rate, received_amount
    """
    _defaults     = _get_defaults()
    base_currency = _defaults.get("server_company_currency", "USD").strip().upper() or "USD"
    currency      = (deposit.get("currency") or base_currency).strip().upper()

    # paid_amount is always the USD-basis figure
    amount = float(deposit.get("deposit_amount") or deposit.get("paid_amount")
                   or deposit.get("amount") or 0)

    # --- resolve exchange_rate as LOCAL-per-USD (>= 1 for ZWG/ZWD/ZIG) ---
    if override_rate is not None and override_rate > 0:
        exch_rate = float(override_rate)
        log.debug("[laybye resolve_amounts] Using override rate: %.6f", exch_rate)
    elif currency == "USD":
        exch_rate = 1.0
    else:
        exch_rate = float(deposit.get("exchange_rate") or 0)
        if exch_rate <= 0:
            try:
                from models.exchange_rate import get_rate
                rate = get_rate(currency, "USD")
                if rate and rate > 0:
                    # Normalise to local-per-USD
                    exch_rate = (1.0 / rate) if rate < 1 else rate
                    log.info("[laybye resolve_amounts] Got rate for %s: %.6f (local/USD)",
                             currency, exch_rate)
                else:
                    raise ValueError(f"No exchange rate found for {currency}. Please update exchange rates in settings.")
            except Exception as e:
                log.error("[laybye resolve_amounts] Rate lookup failed for %s: %s", currency, e)
                raise

        # If caller supplied USD-per-local (< 1), invert it
        if 0 < exch_rate < 1 and currency in ("ZWD", "ZWG", "ZIG"):
            exch_rate = 1.0 / exch_rate
            log.info("[laybye resolve_amounts] Inverted to local/USD for %s: %.6f",
                     currency, exch_rate)

    # received_amount = paid_amount(USD) * rate = LOCAL figure
    received_amount = round(amount * exch_rate, 4)

    # Derive convenience breakdowns
    if currency == "USD":
        amount_usd = amount
        amount_zwd = 0.0
        amount_zwg = 0.0
    elif currency == "ZWD":
        amount_usd = amount
        amount_zwd = received_amount
        amount_zwg = 0.0
    elif currency in ("ZWG", "ZIG"):
        amount_usd = amount
        amount_zwd = 0.0
        amount_zwg = received_amount
    else:
        amount_usd = amount
        amount_zwd = 0.0
        amount_zwg = 0.0

    log.debug(
        "[laybye resolve_amounts] %s: paid(USD)=%.4f  rate=%.6f (local/USD)"
        "  received=%.4f %s",
        currency, amount, exch_rate, received_amount, currency,
    )

    return {
        "currency":        currency,
        "amount":          amount,           # USD-basis paid_amount
        "amount_usd":      amount_usd,
        "amount_zwd":      amount_zwd,
        "amount_zwg":      amount_zwg,
        "exchange_rate":   exch_rate,        # local per USD (>= 1 for ZWG/ZWD/ZIG)
        "received_amount": received_amount,  # paid_amount * rate = LOCAL figure
    }


# =============================================================================
# Local queue table
# =============================================================================

def _ensure_table():
    """Create laybye_payment_entries table if it does not exist."""
    conn = _get_conn()
    cur  = conn.cursor()

    cur.execute("""
        SELECT 1 FROM sys.objects
        WHERE object_id = OBJECT_ID('laybye_payment_entries') AND type = 'U'
    """)

    if cur.fetchone() is None:
        cur.execute("""
            CREATE TABLE laybye_payment_entries (
                id               INT           PRIMARY KEY IDENTITY(1,1),
                sales_order_id   INT           NOT NULL,
                order_no         NVARCHAR(100) NOT NULL DEFAULT '',
                customer_name    NVARCHAR(255) NOT NULL DEFAULT '',
                deposit_amount   FLOAT         NOT NULL DEFAULT 0,
                deposit_method   NVARCHAR(100) NOT NULL DEFAULT '',
                deposit_currency NVARCHAR(10)  NOT NULL DEFAULT 'USD',
                gl_account       NVARCHAR(255) NOT NULL DEFAULT '',
                exchange_rate    FLOAT         NOT NULL DEFAULT 1.0,
                received_amount  FLOAT         NOT NULL DEFAULT 0,
                frappe_pe_ref    NVARCHAR(255) NOT NULL DEFAULT '',
                frappe_so_ref    NVARCHAR(255) NOT NULL DEFAULT '',
                status           NVARCHAR(50)  NOT NULL DEFAULT 'pending',
                sync_attempts    INT           NOT NULL DEFAULT 0,
                created_at       NVARCHAR(50)  NOT NULL DEFAULT '',
                last_attempt_at  NVARCHAR(50)  NOT NULL DEFAULT '',
                error_message    NVARCHAR(MAX) NOT NULL DEFAULT ''
            )
        """)
        conn.commit()
        log.info("Created table: laybye_payment_entries")
    else:
        _add_missing_columns(conn, cur)

    return conn


def _add_missing_columns(conn, cur):
    """Add any missing columns to an existing table."""
    cur.execute("""
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = 'laybye_payment_entries'
    """)
    existing = {row[0].lower() for row in cur.fetchall()}

    columns_to_add = [
        ("deposit_currency", "NVARCHAR(10)  NOT NULL DEFAULT 'USD'"),
        ("gl_account",       "NVARCHAR(255) NOT NULL DEFAULT ''"),
        ("exchange_rate",    "FLOAT         NOT NULL DEFAULT 1.0"),
        ("received_amount",  "FLOAT         NOT NULL DEFAULT 0"),
    ]
    for col_name, col_def in columns_to_add:
        if col_name not in existing:
            try:
                cur.execute(f"ALTER TABLE laybye_payment_entries ADD {col_name} {col_def}")
                log.info("Added column: %s", col_name)
            except Exception as e:
                log.warning("Could not add column %s: %s", col_name, e)
    conn.commit()


# =============================================================================
# Queue a single payment entry row
# =============================================================================

def _create_single_payment_entry(order: dict) -> int | None:
    """Write one laybye payment entry row into the local queue table."""

    deposit_amount = float(order.get("deposit_amount") or 0)
    deposit_method = order.get("deposit_method") or "Cash"
    deposit_currency = (order.get("deposit_currency") or "USD").upper()

    # Resolve MOP + GL account (same DB-direct approach as payment_entry_service)
    mop_name, gl_account = _resolve_mop(
        deposit_method,
        order.get("gl_account", ""),
        deposit_currency,
    )

    # If resolution gave us a MOP name, refresh the currency from that MOP record
    # so we always store the account's true currency, not a guess.
    if not deposit_currency or deposit_currency == "USD":
        try:
            from database.db import get_connection, fetchone_dict
            _c = get_connection()
            _cur = _c.cursor()
            _cur.execute(
                "SELECT account_currency FROM modes_of_payment WHERE name = ?",
                (mop_name,)
            )
            row = fetchone_dict(_cur)
            _c.close()
            if row and row.get("account_currency"):
                deposit_currency = row["account_currency"].upper()
        except Exception:
            pass

    resolved        = _resolve_amounts({
        "deposit_amount": deposit_amount,
        "currency":       deposit_currency,
        "exchange_rate":  order.get("exchange_rate", 0),
    })
    exch_rate       = resolved["exchange_rate"]
    received_amount = resolved["received_amount"]

    log.info(
        "[laybye queue] order=%s  method=%s  amount=%.4f %s  rate=%.6f  received=%.4f  GL=%s",
        order.get("order_no"), mop_name,
        deposit_amount, deposit_currency,
        exch_rate, received_amount, gl_account,
    )

    try:
        conn = _ensure_table()
        cur  = conn.cursor()
        cur.execute("""
            INSERT INTO laybye_payment_entries
                (sales_order_id, order_no, customer_name,
                 deposit_amount, deposit_method, deposit_currency,
                 gl_account, exchange_rate, received_amount,
                 status, created_at)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
        """, (
            int(order["id"]),
            order.get("order_no") or "",
            order.get("customer_name") or "Walk-in Customer",
            deposit_amount,
            mop_name,
            deposit_currency,
            gl_account or None,
            exch_rate,
            received_amount,
            datetime.now().isoformat(timespec="seconds"),
        ))
        pe_id = cur.fetchone()[0]
        conn.commit()
        log.info(
            "Queued laybye PE id=%d  order=%s  method=%s  amount=%.2f %s"
            "  paid(USD)=%.2f  rate=%.4f",
            pe_id, order.get("order_no"), mop_name,
            received_amount, deposit_currency,
            deposit_amount, exch_rate,
        )
        return pe_id
    except Exception as exc:
        log.error("_create_single_payment_entry failed: %s", exc)
        return None


# =============================================================================
# Public API — queue entries
# =============================================================================

def create_laybye_payment_entry(order: dict, splits: dict[str, dict] | None = None) -> list[int]:
    """
    Queue laybye deposit payment entries for sync.
    Can handle either a single deposit (in order dict) or split deposits (in splits dict).

    Args:
        order: Laybye order dict with keys:
                 id, order_no, customer_name,
                 deposit_amount, deposit_method, deposit_currency,
                 exchange_rate (optional), gl_account (optional)
        splits: Optional dictionary of splits (e.g. from laybye_payment_dialog).

    Returns:
        List of payment entry IDs queued.
    """
    if not order:
        return []

    if splits:
        ids = []
        for method_label, data in splits.items():
            # Construct a sub-order dict for each split
            split_order = order.copy()
            split_order["deposit_amount"] = data["usd"]         # USD basis
            split_order["deposit_method"] = method_label
            split_order["deposit_currency"] = data["currency"]
            split_order["gl_account"] = data.get("gl_account", "")
            split_order["exchange_rate"] = data.get("rate_to_usd", 1.0)  # Local/USD rate
            
            res = _create_single_payment_entry(split_order)
            if res:
                ids.append(res)
        return ids
    else:
        # Fallback to single payment if splits not provided
        deposit_amount = float(order.get("deposit_amount") or 0)
        if deposit_amount <= 0:
            log.warning("create_laybye_payment_entry: zero deposit_amount, skipping")
            return []

        result = _create_single_payment_entry(order)
        return [result] if result else []


# =============================================================================
# Build Frappe payload  — mirrors payment_entry_service._build_payload exactly
# =============================================================================

def _build_payment_payload(payment: dict, defaults: dict) -> dict | None:
    """
    Build the Frappe Payment Entry payload from a laybye_payment_entries row.

    DB invariants (same convention as payment_entry_service):
      deposit_amount   = USD basis figure (paid_amount)
      received_amount  = deposit_amount * exchange_rate  = LOCAL currency figure
      exchange_rate    = local-per-USD  (>= 1 for ZIG/ZWG/ZWD, 1.0 for USD)

    Frappe mapping:
      paid_amount            → USD basis  (deposit_amount)
      received_amount        → LOCAL figure  (received_amount)
      source_exchange_rate   → local-per-USD  (exchange_rate)
      target_exchange_rate   → 1.0
    """
    company       = defaults.get("server_company", "")
    base_currency = defaults.get("server_company_currency", "USD").strip().upper() or "USD"

    currency = (payment.get("deposit_currency") or base_currency).upper()

    # Pull stored figures from the DB row
    paid_amount_usd       = float(payment.get("deposit_amount") or 0)
    received_amount_local = float(payment.get("received_amount") or 0)
    exch_rate             = float(payment.get("exchange_rate") or 1.0)

    # --- MOP / GL account (same DB-direct resolution as payment_entry_service) ---
    stored_method = (payment.get("deposit_method") or "").strip()
    stored_gl     = (payment.get("gl_account") or "").strip()
    mop_name, gl_account = _resolve_mop(stored_method, stored_gl, currency)

    if not gl_account:
        log.error("No paid_to GL account found for laybye PE id=%s", payment.get("id"))
        return None

    # Determine the actual currency of the paid_to GL account
    paid_to_currency = _get_gl_account_currency(
        gl_account,
        fallback=currency if currency != "USD" else base_currency,
    )

    # Exchange rate logic for ERPNext (rates must be relative to base_currency)
    # If base_currency is USD:
    #   USD rate = 1.0
    #   ZIG rate = 1.0 / exch_rate (where exch_rate is local-per-USD)
    if currency in ("ZWD", "ZWG", "ZIG"):
        if 0 < exch_rate < 1:
            exch_rate = 1.0 / exch_rate
            log.info("[laybye build_payload] Normalised rate to local/USD for %s: %.6f",
                     currency, exch_rate)
        
        # If received_amount_local was not stored correctly, recompute it
        if received_amount_local <= 0 and paid_amount_usd > 0 and exch_rate > 0:
            received_amount_local = round(paid_amount_usd * exch_rate, 4)

        paid_amount_for_frappe     = paid_amount_usd
        received_amount_for_frappe = received_amount_local
        
        # FRAPPE: rates are from [account currency] to [company base currency]
        # Since paid_from is base_currency (USD), its rate is always 1.0
        source_exch_rate           = 1.0
        # paid_to is ZIG, so its rate is USD-per-ZIG (e.g. 1/30 = 0.033)
        target_exch_rate           = round(1.0 / exch_rate, 9) if exch_rate > 0 else 1.0

        log.info(
            "[laybye build_payload] %s payment: paid(USD)=%.4f -> FromRate=%.4f, ToRate=%.6f",
            currency, paid_amount_for_frappe, source_exch_rate, target_exch_rate
        )
    elif currency == "USD" and paid_to_currency in ("ZWD", "ZWG", "ZIG"):
        # SPECIAL CASE: USD payment going into a ZIG account
        try:
            from models.exchange_rate import get_rate
            rate = get_rate(paid_to_currency, "USD")
            raw_rate = (1.0 / rate) if (rate and 0 < rate < 1) else (rate or 1.0)
        except Exception:
            raw_rate = 1.0
            
        paid_amount_for_frappe     = paid_amount_usd
        received_amount_for_frappe = round(paid_amount_usd * raw_rate, 4)
        source_exch_rate           = 1.0
        target_exch_rate           = raw_rate
        log.info("[laybye build_payload] USD-to-%s transfer identify (Laybye): received_amount=%.4f",
                 paid_to_currency, received_amount_for_frappe)
    else:
        # Pure USD
        paid_amount_for_frappe     = paid_amount_usd
        received_amount_for_frappe = received_amount_local if received_amount_local > 0 else paid_amount_usd
        source_exch_rate           = 1.0
        target_exch_rate           = 1.0

    # --- Reference fields ---
    payment_id     = payment.get("id", 0)
    reference_no   = f"LAYBYE-{payment_id:07d}"
    created_at     = payment.get("created_at") or ""
    reference_date = created_at[:10] if created_at else date.today().isoformat()

    customer_name = (payment.get("customer_name") or "Walk-in Customer").strip()
    method_label  = payment.get("deposit_method", "")
    remarks = (
        f"Laybye Deposit via {method_label} | "
        f"USD {paid_amount_for_frappe:.2f} @ {exch_rate:.4f} {currency}/USD = "
        f"{currency} {received_amount_for_frappe:.2f}"
        if method_label else "Laybye Deposit"
    )

    payload = {
        "doctype":                    "Payment Entry",
        "payment_type":               "Receive",
        "party_type":                 "Customer",
        "party":                      customer_name,
        "party_name":                 customer_name,
        "paid_from_account_currency": base_currency,
        "paid_to_account_currency":   paid_to_currency,
        "paid_to":                    gl_account,
        "paid_amount":                paid_amount_for_frappe,        # USD basis
        "received_amount":            received_amount_for_frappe,    # LOCAL figure
        "source_exchange_rate":       source_exch_rate,              # local per USD
        "target_exchange_rate":       target_exch_rate,
        "mode_of_payment":            mop_name,
        "reference_no":               reference_no,
        "reference_date":             reference_date,
        "remarks":                    remarks,
        "docstatus":                  1,
        "references":                 [],
    }

    # Add reference to Sales Order if available
    frappe_so_ref = (payment.get("frappe_so_ref") or "").strip()
    if frappe_so_ref:
        # Cap allocated_amount at the Sales Order's local total to prevent 417 errors
        # caused by tiny rounding differences in multi-currency conversions.
        allocation = round(paid_amount_for_frappe, 4)
        
        try:
            so_id = payment.get("sales_order_id")
            if so_id:
                from database.db import get_connection
                _conn = get_connection()
                _cur = _conn.cursor()
                _cur.execute("SELECT total FROM sales_order WHERE id = ?", (so_id,))
                so_row = _cur.fetchone()
                _conn.close()
                if so_row:
                    so_total = round(float(so_row[0]), 4)
                    if allocation > so_total:
                        log.warning(
                            "[laybye sync] Capping allocation for PE %d: %.4f -> %.4f (SO total)",
                            payment_id, allocation, so_total
                        )
                        allocation = so_total
        except Exception as e:
            log.debug("[laybye sync] Could not fetch SO total for capping: %s", e)

        payload["references"].append({
            "reference_doctype": "Sales Order",
            "reference_name":    frappe_so_ref,
            "allocated_amount":  allocation
        })
        log.info("[laybye build_payload] Added reference to Sales Order: %s (allocated=%.4f)", 
                 frappe_so_ref, allocation)

    if company:
        payload["company"] = company

    cost_center = defaults.get("server_cost_center", "").strip()
    if cost_center:
        payload["cost_center"] = cost_center

    log.info(
        "[laybye build_payload] PE id=%d  MOP='%s'  GL='%s'  currency=%s  "
        "paid_frappe=%.4f USD  received_frappe=%.4f %s  "
        "source_rate=%.6f (local/USD)  target_rate=%.6f",
        payment_id, mop_name, gl_account,
        currency,
        paid_amount_for_frappe,
        received_amount_for_frappe, currency,
        source_exch_rate, target_exch_rate,
    )

    # Full debug dump
    print("\n" + "=" * 80)
    print(f"🔍 LAYBYE PAYMENT DEBUG: PE id={payment_id}")
    print(json.dumps({
        "raw_row":  payment,
        "computed": {
            "currency":           currency,
            "paid_amount_usd":    paid_amount_for_frappe,
            "received_amount":    received_amount_for_frappe,
            "source_exch_rate":   source_exch_rate,
            "target_exch_rate":   target_exch_rate,
            "mop_name":           mop_name,
            "gl_account":         gl_account,
            "paid_to_currency":   paid_to_currency,
            "reference_no":       reference_no,
            "reference_date":     reference_date,
        },
        "final_payload": payload,
    }, indent=2, default=str))
    print("=" * 80 + "\n")

    return payload


# =============================================================================
# Sync helpers
# =============================================================================

def get_unsynced_payment_entries() -> list[dict]:
    """Return all pending/retry laybye payment entries."""
    try:
        conn = _ensure_table()
        cur  = conn.cursor()
        cur.execute("""
            SELECT id, order_no, customer_name,
                   deposit_amount, deposit_method, deposit_currency,
                   gl_account, exchange_rate, received_amount,
                   frappe_so_ref, sync_attempts, status, created_at
            FROM laybye_payment_entries
            WHERE status IN ('pending', 'retry')
              AND sync_attempts < 60
            ORDER BY id ASC
        """)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in rows]
    except Exception as exc:
        log.error("get_unsynced_payment_entries failed: %s", exc)
        return []


def _push_single(pe: dict, api_key: str, api_secret: str,
                 host: str, defaults: dict) -> None:
    """POST a single laybye payment entry to Frappe and update its status."""
    import requests

    pe_id          = pe["id"]
    attempts_so_far = int(pe.get("sync_attempts", 0))

    payload = _build_payment_payload(pe, defaults)
    if not payload:
        log.error("PE %d — no payload built, skipping", pe_id)
        return

    url     = f"{host}/api/resource/Payment%20Entry"
    headers = {
        "Authorization": f"token {api_key}:{api_secret}",
        "Content-Type":  "application/json",
    }

    conn = _get_conn()
    try:
        # Increment attempt counter first
        conn.execute(
            "UPDATE laybye_payment_entries "
            "SET sync_attempts = sync_attempts + 1, last_attempt_at = ? "
            "WHERE id = ?",
            (datetime.now().isoformat(timespec="seconds"), pe_id),
        )
        conn.commit()

        response = requests.post(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)

        if response.status_code == 200:
            frappe_name = response.json().get("data", {}).get("name", "")
            conn.execute(
                "UPDATE laybye_payment_entries "
                "SET status = 'synced', frappe_pe_ref = ?, error_message = '' "
                "WHERE id = ?",
                (frappe_name, pe_id),
            )
            conn.commit()
            log.info("✅ Laybye PE %d synced → %s", pe_id, frappe_name)
            print(f"✅ Laybye PE {pe_id} ({pe.get('order_no')}) synced to Frappe: {frappe_name}")

        else:
            error_text = response.text[:500] if response.text else f"HTTP {response.status_code}"
            print(f"\n❌ Frappe rejected Laybye PE {pe_id} ({pe.get('order_no')})")
            print(f"   Status : {response.status_code}")
            print(f"   Error  : {error_text}")

            new_status = "failed" if (attempts_so_far + 1) >= 60 else "retry"
            conn.execute(
                "UPDATE laybye_payment_entries "
                "SET status = ?, error_message = ?, sync_error = ?, last_attempt_at = ? "
                "WHERE id = ?",
                (new_status, error_text[:1000], error_text,
                 datetime.now().isoformat(timespec="seconds"), pe_id),
            )
            conn.commit()
            log.warning("Laybye PE %d → %s (Attempt %d/60)",
                        pe_id, new_status, attempts_so_far + 1)

    except requests.exceptions.RequestException as e:
        error_text = str(e)[:500]
        log.error("Laybye PE %d request failed: %s", pe_id, e)
        new_status = "failed" if (attempts_so_far + 1) >= 60 else "retry"
        conn.execute(
            "UPDATE laybye_payment_entries "
            "SET status = ?, error_message = ?, last_attempt_at = ? WHERE id = ?",
            (new_status, error_text, datetime.now().isoformat(timespec="seconds"), pe_id),
        )
        conn.commit()

    except Exception as e:
        error_text = str(e)[:500]
        log.error("Laybye PE %d unexpected error: %s", pe_id, e)
        new_status = "failed" if (attempts_so_far + 1) >= 60 else "retry"
        conn.execute(
            "UPDATE laybye_payment_entries "
            "SET status = ?, error_message = ?, last_attempt_at = ? WHERE id = ?",
            (new_status, error_text, datetime.now().isoformat(timespec="seconds"), pe_id),
        )
        conn.commit()

    finally:
        conn.close()


def sync_laybye_payment_entries(force: bool = False) -> dict:
    """
    Push all pending laybye entries to Frappe, one after the other.
    """
    result = {"pushed": 0, "failed": 0, "skipped": 0, "total": 0}

    # AUTO-RESOLVE: Try to link PEs that are missing frappe_so_ref
    try:
        conn = _get_conn()
        conn.execute("""
            UPDATE laybye_payment_entries
            SET frappe_so_ref = (
                SELECT TOP 1 frappe_ref 
                FROM sales 
                WHERE sales.invoice_no = laybye_payment_entries.order_no
                  AND sales.frappe_ref IS NOT NULL 
                  AND sales.frappe_ref != ''
            )
            WHERE (frappe_so_ref IS NULL OR frappe_so_ref = '')
              AND status IN ('pending', 'retry')
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        log.debug("[laybye-sync] Auto-resolve frappe_so_ref failed: %s", e)

    # When forced (manual retry): reset failed/stuck entries so they get picked up
    if force:
        try:
            conn = _get_conn()
            conn.execute("""
                UPDATE laybye_payment_entries
                SET status = 'retry', sync_attempts = 0
                WHERE status IN ('failed', 'syncing')
            """)
            conn.commit()
            conn.close()
            log.info("[laybye-sync] Force=True: reset all failed/stuck entries to retry.")
        except Exception as e:
            log.debug("[laybye-sync] Force reset failed: %s", e)

    pending = get_unsynced_payment_entries()
    if not pending:
        return result
    
    result["total"] = len(pending)

    api_key, api_secret = _get_credentials()
    host     = _get_host()
    defaults = _get_defaults()

    if not api_key or not host:
        log.warning("sync — missing api_key or host, skipping")
        return result

    # STALE LOCK CLEANUP: Only release PEs stuck in 'syncing' if they are over 5 minutes old
    try:
        conn = _get_conn()
        # SQL Server DATEADD(MINUTE, -5, GETDATE())
        conn.execute("""
            UPDATE laybye_payment_entries 
            SET status = 'retry' 
            WHERE status = 'syncing'
              AND (last_attempt_at IS NULL OR last_attempt_at < CONVERT(NVARCHAR(50), DATEADD(MINUTE, -5, GETDATE()), 126))
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        log.debug("[laybye-sync] Stale lock cleanup failed: %s", e)

    log.info("Syncing %d laybye payment(s) to Frappe …", len(pending))

    for pe in pending:
        # ATOMIC LOCK: Try to claim this PE
        try:
            conn = _get_conn()
            cur = conn.cursor()
            cur.execute(
                "UPDATE laybye_payment_entries SET status = 'syncing' "
                "WHERE id = ? AND status IN ('pending', 'retry')",
                (pe["id"],)
            )
            conn.commit()
            if cur.rowcount == 0:
                conn.close()
                continue
            conn.close()
        except Exception as e:
            log.error("Failed to lock Laybye PE %d: %s", pe["id"], e)
            continue

        try:
            # Exponential backoff check:
            attempts = pe.get("sync_attempts", 0)
            last_at_str = pe.get("last_attempt_at", "")
            
            if last_at_str and not force:
                try:
                    last_at = datetime.fromisoformat(last_at_str)
                    waited = (datetime.now() - last_at).total_seconds()
                    required = min(20 + (attempts * 10), 60) 
                    if waited < required:
                        log.debug("PE %d skipping sync (backoff): waited %.1fs < required %ds", 
                                  pe["id"], waited, required)
                        # Unlock it
                        conn = _get_conn()
                        conn.execute("UPDATE laybye_payment_entries SET status = 'retry' WHERE id = ?", (pe["id"],))
                        conn.commit()
                        conn.close()
                        continue
                except Exception:
                    pass

            _push_single(pe, api_key, api_secret, host, defaults)
        except Exception as e:
            log.error("Laybye sync loop error for PE %d: %s", pe["id"], e)
        finally:
            # Ensure syncing status is not stuck if _push_single failed but didn't set final status
            try:
                conn = _get_conn()
                cur = conn.cursor()
                cur.execute("SELECT status FROM laybye_payment_entries WHERE id = ?", (pe["id"],))
                row = cur.fetchone()
                if row and row[0] == 'syncing':
                    cur.execute("UPDATE laybye_payment_entries SET status = 'retry' WHERE id = ?", (pe["id"],))
                    conn.commit()
                conn.close()
            except Exception:
                pass

        time.sleep(2)   # brief pause between requests

    log.info("Laybye sync done — total=%d", result["total"])
    return result


# =============================================================================
# Linking helper
# =============================================================================

def link_laybye_payment_to_frappe(so_number: str, frappe_so_ref: str) -> None:
    """Link all laybye payments for a Sales Order to the Frappe SO reference."""
    try:
        conn = _get_conn()
        cur  = conn.cursor()
        cur.execute("""
            UPDATE laybye_payment_entries
            SET frappe_so_ref = ?
            WHERE order_no = ? AND (frappe_so_ref IS NULL OR frappe_so_ref = '')
        """, (frappe_so_ref, so_number))
        conn.commit()
        conn.close()
        log.info("✅ Linked laybye payments for %s to %s", so_number, frappe_so_ref)
        print(f"✅ Linked laybye payments for {so_number} to Frappe SO: {frappe_so_ref}")
    except Exception as e:
        log.error("link_laybye_payment_to_frappe failed for %s: %s", so_number, e)


# =============================================================================
# Background sync daemon
# =============================================================================

def _sync_loop() -> None:
    log.info("Laybye PE sync daemon started (interval=%ds).", SYNC_INTERVAL)
    while True:
        if _sync_lock.acquire(blocking=False):
            try:
                sync_laybye_payment_entries()
            except Exception as exc:
                log.error("Laybye sync cycle error: %s", exc)
            finally:
                _sync_lock.release()
        else:
            log.debug("Previous laybye sync still running — skipping.")
        time.sleep(SYNC_INTERVAL)


def start_laybye_pe_sync_daemon() -> threading.Thread:
    """Start the background daemon (idempotent — returns existing thread if running)."""
    global _sync_thread
    if _sync_thread and _sync_thread.is_alive():
        return _sync_thread
    t = threading.Thread(target=_sync_loop, daemon=True, name="laybye_pe_sync")
    t.start()
    _sync_thread = t
    log.info("Laybye PE sync daemon started.")
    return t