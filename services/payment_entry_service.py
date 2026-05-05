from __future__ import annotations

import json
import logging
import time
import threading
import urllib.request
import urllib.error
from datetime import date

log = logging.getLogger("PaymentEntryService")

SYNC_INTERVAL = 15       # seconds between auto-sync cycles
REQUEST_TIMEOUT = 30

_sync_lock = threading.Lock()
_sync_thread: threading.Thread | None = None

# Exchange rate cache: "FROM::TO::DATE" → float
_RATE_CACHE: dict[str, float] = {}


# =============================================================================
# CREDENTIALS / HOST / DEFAULTS
# =============================================================================

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
    """Return the account_currency for a GL account from local gl_accounts table."""
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


def _get_exchange_rate(from_currency: str, to_currency: str,
                       transaction_date: str,
                       api_key: str, api_secret: str, host: str) -> float:
    """
    Fetch live exchange rate from Frappe.
    Returns 1.0 for same currency, 0.0 if fetch fails.
    """
    if not from_currency or from_currency.upper() == to_currency.upper():
        return 1.0

    cache_key = f"{from_currency.upper()}::{to_currency.upper()}::{transaction_date}"
    if cache_key in _RATE_CACHE:
        return _RATE_CACHE[cache_key]

    try:
        import urllib.parse
        url = (
            f"{host}/api/method/erpnext.setup.utils.get_exchange_rate"
            f"?from_currency={urllib.parse.quote(from_currency)}"
            f"&to_currency={urllib.parse.quote(to_currency)}"
            f"&transaction_date={transaction_date}"
        )
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"token {api_key}:{api_secret}")
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
            data = json.loads(r.read().decode())
            rate = float(data.get("message") or data.get("result") or 0)
            if rate > 0:
                _RATE_CACHE[cache_key] = rate
                log.debug("Rate %s->%s on %s: %.6f", from_currency, to_currency, transaction_date, rate)
                return rate
    except Exception as e:
        log.debug("Rate fetch failed (%s->%s): %s", from_currency, to_currency, e)

    return 0.0


def _resolve_mop(raw_method: str, gl_account: str, currency: str) -> tuple[str, str]:
    """
    Given the raw method name from the sale and optional gl_account,
    return (frappe_mop_name, gl_account_name).
    Resolution order: gl_account match -> exact name match -> currency match -> fallback.
    """
    from database.db import get_connection, fetchone_dict

    if not raw_method:
        raw_method = "Cash"

    conn = get_connection()
    cur = conn.cursor()

    try:
        # 1. Try to find by gl_account first
        if gl_account:
            cur.execute(
                "SELECT name, gl_account FROM modes_of_payment WHERE gl_account = ?",
                (gl_account,)
            )
            row = fetchone_dict(cur)
            if row:
                log.debug("MOP resolved by gl_account: %s -> %s", gl_account, row["name"])
                return row["name"], row["gl_account"]

        # 2. Try exact name match
        cur.execute(
            "SELECT name, gl_account FROM modes_of_payment WHERE name = ?",
            (raw_method,)
        )
        row = fetchone_dict(cur)
        if row and row.get("gl_account"):
            log.debug("MOP resolved by exact name: %s -> %s", raw_method, row["gl_account"])
            return row["name"], row["gl_account"]

        # 3. Try by currency
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

    # Fallback
    log.warning("No MOP found for method='%s', using fallback", raw_method)
    return raw_method, gl_account


# =============================================================================
# AMOUNT RESOLUTION (creation side)
# =============================================================================

def _resolve_amounts(sale: dict, override_rate: float = None) -> dict:
    """
    Central resolver for ALL currency amounts for a payment entry.

    CONVENTION:
      - paid_amount    = the USD base amount (what was tendered / invoiced in USD terms)
      - exchange_rate  = LOCAL units per 1 USD  (e.g. ZWG 30 per USD → rate = 30)
      - received_amount = paid_amount * exchange_rate
                        = the LOCAL currency figure (ZWG/ZWD amount)

    For USD payments exchange_rate = 1.0, so received_amount == paid_amount.

    Returns a dict with:
      currency         – normalised currency code
      amount           – native paid_amount (USD basis)
      amount_usd       – always the USD equivalent (== amount for USD payments)
      amount_zwd       – ZWD received_amount (non-zero only when currency == ZWD)
      amount_zwg       – ZWG/ZIG received_amount (non-zero only when currency == ZWG/ZIG)
      exchange_rate    – LOCAL units per 1 USD  (>= 1 for ZWG/ZWD, 1.0 for USD)
      received_amount  – paid_amount * exchange_rate  (LOCAL currency figure stored in DB)
    """
    _defaults = _get_defaults()
    base_currency = _defaults.get("server_company_currency", "USD").strip().upper() or "USD"
    currency = (sale.get("currency") or base_currency).strip().upper()
    if currency == "US":
        currency = "USD"

    
    # paid_amount is always the USD-basis figure coming from the sale
    amount = float(sale.get("paid_amount") or sale.get("base_value") or sale.get("total") or 0)

    # --- resolve exchange_rate as LOCAL-per-USD (always >= 1 for ZWG/ZWD) ---
    if override_rate is not None:
        exch_rate = float(override_rate)
        if exch_rate > 0 and exch_rate < 1 and currency in ("ZWD", "ZWG", "ZIG"):
            exch_rate = exch_rate
    elif currency == "USD":
        exch_rate = 1.0
    else:
        exch_rate = float(sale.get("exchange_rate") or 0)
        if exch_rate <= 0:
            try:
                from models.exchange_rate import get_rate
                rate = get_rate(currency, "USD")
                if rate and rate > 0:
                    # get_rate may return USD-per-local; invert to local-per-USD
                    exch_rate = (1.0 / rate) if rate < 1 else rate
                    log.info("[resolve_amounts] Got current rate for %s: %.6f (local per USD)",
                             currency, exch_rate)
            except Exception:
                pass

        # Normalise: we always want local-per-USD (> 1 for ZWG/ZWD)
        # If what we have is USD-per-local (< 1), invert it
        if exch_rate > 0 and exch_rate < 1 and currency in ("ZWD", "ZWG", "ZIG"):
            exch_rate = 1.0 / exch_rate
            log.info("[resolve_amounts] Inverted rate to local per USD for %s: %.6f",
                     currency, exch_rate)

    # --- received_amount = paid_amount * exchange_rate ---
    # For USD  : 1.0 * 1.0  = USD amount  (no change)
    # For ZWG  : USD_amount * ZWG_per_USD = ZWG amount
    # For ZWD  : USD_amount * ZWD_per_USD = ZWD amount
    received_amount = round(amount * exch_rate, 4)

    # --- derive convenience breakdowns ---
    if currency == "USD":
        amount_usd = amount
        amount_zwd = 0.0
        amount_zwg = 0.0
    elif currency == "ZWD":
        amount_usd = amount          # paid_amount IS the USD basis
        amount_zwd = received_amount # local figure
        amount_zwg = 0.0
    elif currency in ("ZWG", "ZIG"):
        amount_usd = amount          # paid_amount IS the USD basis
        amount_zwd = 0.0
        amount_zwg = received_amount # local figure
    else:
        amount_usd = amount
        amount_zwd = 0.0
        amount_zwg = 0.0

    log.debug(
        "[resolve_amounts] %s: paid_amount=%.4f USD  rate=%.6f (local/USD)"
        "  received_amount=%.4f %s",
        currency, amount, exch_rate, received_amount, currency,
    )

    return {
        "currency":        currency,
        "amount":          amount,           # USD-basis paid_amount
        "amount_usd":      amount_usd,
        "amount_zwd":      amount_zwd,
        "amount_zwg":      amount_zwg,
        "exchange_rate":   exch_rate,        # local per USD  (>= 1 for ZWG/ZWD)
        "received_amount": received_amount,  # paid_amount * exchange_rate = LOCAL figure
    }


# =============================================================================
# LOCAL DB - create payment entries
# =============================================================================

def create_payment_entry(sale: dict, override_rate: float = None,
                         override_account: str = None,
                         _is_split: bool = False,
                         shift_id: int = None) -> int | None:
    """
    Write one payment entry row to the local DB, then immediately trigger a
    sync cycle so it is pushed to Frappe without waiting for the next daemon tick.

    Key invariant stored in DB:
      paid_amount      = USD basis figure
      received_amount  = paid_amount * exchange_rate  (LOCAL currency figure for ZWG/ZWD)
      exchange_rate    = local-per-USD  (>= 1 for ZWG/ZWD, 1.0 for USD)
    """
    from database.db import get_connection

    conn = get_connection()
    cur = conn.cursor()

    raw_method = str(sale.get("method") or "Cash").strip()
    _defaults  = _get_defaults()

    log.info("[create_PE] ========== START ==========")
    log.info("[create_PE] sale_id=%s  method=%s  currency=%s  paid_amount=%s",
             sale.get("id"), raw_method, sale.get("currency"), sale.get("paid_amount"))
    log.info("[create_PE] gl_account from sale: %s  override_account: %s",
             sale.get("gl_account"), override_account)

    resolved        = _resolve_amounts(sale, override_rate)
    currency        = resolved["currency"]
    amount          = resolved["amount"]           # USD basis
    amount_usd      = resolved["amount_usd"]
    amount_zwd      = resolved["amount_zwd"]
    amount_zwg      = resolved["amount_zwg"]
    exch_rate       = resolved["exchange_rate"]    # local per USD
    received_amount = resolved["received_amount"]  # paid_amount * rate = LOCAL figure

    gl_hint = (override_account or sale.get("gl_account")
               or sale.get("paid_to") or "").strip()
    mop_name, gl_account = _resolve_mop(raw_method, gl_hint, currency)

    sid = shift_id or sale.get("shift_id")

    log.info("[create_PE] Resolved mop_name=%s  gl_account=%s", mop_name, gl_account)
    log.info(
        "[create_PE] paid_amount(USD)=%.4f  exchange_rate=%.6f (local/USD)"
        "  received_amount=%.4f %s",
        amount, exch_rate, received_amount, currency,
    )
    if amount_zwd > 0:
        log.info("[create_PE] ZWD received_amount: %.4f", amount_zwd)
    if amount_zwg > 0:
        log.info("[create_PE] ZWG received_amount: %.4f", amount_zwg)

    _walk_in = _defaults.get("server_walk_in_customer", "").strip() or "Default"
    customer = (sale.get("customer_name") or "").strip() or _walk_in
    inv_no   = sale.get("invoice_no", "")
    inv_date = sale.get("invoice_date") or date.today().isoformat()
    
    # CRITICAL FIX: Ensure frappe_ref is properly passed for split payments
    frappe_ref = sale.get("frappe_ref") or sale.get("frappe_invoice_ref") or None

    try:
        cur.execute("""
            INSERT INTO payment_entries (
                sale_id, sale_invoice_no, frappe_invoice_ref,
                party, party_name,
                paid_amount, received_amount, source_exchange_rate,
                paid_to_account_currency, currency,
                paid_to, mode_of_payment,
                reference_no, reference_date,
                remarks, synced,
                amount_usd, amount_zwd, amount_zwg, exchange_rate,
                discount_amount, discount_percent,
                shift_id
            )
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sale["id"], inv_no,
            frappe_ref,  # Use the properly resolved frappe_ref
            customer, customer,
            amount,           # paid_amount  = USD basis
            received_amount,  # received_amount = paid_amount * exchange_rate = LOCAL figure
            exch_rate,        # source_exchange_rate = local per USD
            currency, currency,
            gl_account or None,
            mop_name,
            inv_no, inv_date,
            f"POS Payment - {mop_name}" + (f" (Disc: {sale.get('discount_percent')}% / ${sale.get('discount_amount')})" if float(sale.get('discount_amount') or 0) > 0 else ""),
            amount_usd, amount_zwd, amount_zwg, exch_rate,
            float(sale.get("discount_amount") or 0),
            float(sale.get("discount_percent") or 0),
            sid
        ))

        new_id = cur.fetchone()[0]
        conn.commit()
        conn.close()

        log.info(
            "[create_PE] Created PE %s: %s - paid=%.4f USD  rate=%.6f (local/USD)"
            "  received=%.4f %s  frappe_ref=%s",
            new_id, mop_name,
            amount, exch_rate,
            received_amount, currency,
            frappe_ref
        )

        log.info(
            "[create_PE] Outgoing -> Frappe  PE=%s  sale_id=%s  inv=%s  party=%s  "
            "%s %.4f (USD %.4f)  mop=%s  frappe_ref=%s",
            new_id, sale.get("id"), inv_no, customer,
            currency, received_amount, amount_usd,
            mop_name, frappe_ref or "(pending)",
        )

        # Trigger an immediate sync so this entry doesn't wait for the next daemon tick
        _trigger_sync_now()
        return new_id

    except Exception as e:
        log.error("[create_PE] Database error: %s", e)
        conn.rollback()
        conn.close()
        return None


def create_split_payment_entries(sale: dict, splits: list[dict], shift_id: int = None) -> list[int]:
    """
    Create one payment entry per split leg.
    Each create_payment_entry call triggers an immediate sync internally.

    Exchange rate convention: local-per-USD (>= 1 for ZWG/ZWD).

    IMPORTANT – what the POS sends in split["paid_amount"]:
      - USD  leg : already a USD figure  → pass straight through
      - ZWG/ZWD  : the LOCAL currency figure (e.g. ZWG 300)
                   → must divide by rate to get the USD basis BEFORE passing
                     to create_payment_entry, which will then multiply back:
                     received_amount = paid_amount_usd * rate = local figure ✓

    So the flow for a ZWG split is:
        split["paid_amount"] = 300  ZWG  (what the customer handed over)
        rate                 = 30   ZWG per USD
        paid_amount_usd      = 300 / 30 = 10 USD   ← stored in DB as paid_amount
        received_amount      = 10  * 30 = 300 ZWG  ← stored in DB as received_amount
    """
    ids        = []
    _defaults  = _get_defaults()
    _base_curr = _defaults.get("server_company_currency", "USD").strip().upper()

    # Track the invoice's remaining USD allocation — each PE gets capped at the
    # remainder so Frappe receives only what's REQUIRED on that mode, not what
    # the customer tendered. Overpayment / change stays on the receipt side.
    sale_total_usd  = float(sale.get("total_usd") or sale.get("total") or 0)
    remaining_usd   = sale_total_usd if sale_total_usd > 0 else float("inf")

    log.info("[create_split_PE] ========== START ==========")
    log.info("[create_split_PE] Sale ID: %s  Total splits: %d  total_usd=%.4f",
             sale.get("id"), len(splits), sale_total_usd)
    log.info("[create_split_PE] Parent sale frappe_ref: %s", sale.get("frappe_ref"))

    for idx, split in enumerate(splits):
        log.info("[create_split_PE] --- Split %d/%d ---", idx + 1, len(splits))
        log.info("[create_split_PE] Split data: %s", split)

        currency = (split.get("currency") or _base_curr).strip().upper()

        # amount_local is whatever the POS recorded – for ZWG/ZWD this is the
        # LOCAL currency figure; for USD it is already a USD figure.
        amount_local = float(split.get("paid_amount") or split.get("base_value") or 0)

        if amount_local <= 0:
            log.info("[create_split_PE] Split %d: skipping zero amount", idx + 1)
            continue

        method     = (split.get("method") or split.get("mode") or "Cash").strip()
        gl_account = (split.get("gl_account") or split.get("paid_to") or "").strip()

        # ------------------------------------------------------------------ #
        # Resolve exchange_rate as local-per-USD (>= 1 for ZWG/ZWD, 1 for USD)
        # ------------------------------------------------------------------ #
        rate = float(split.get("exchange_rate") or split.get("rate") or 0)

        if currency in ("ZWD", "ZWG", "ZIG") and rate <= 0:
            try:
                from models.exchange_rate import get_rate
                raw = get_rate(currency, "USD")
                if raw and raw > 0:
                    # Normalise to local-per-USD
                    rate = (1.0 / raw) if raw < 1 else raw
                    log.info("[create_split_PE] Fetched rate for %s: %.6f (local/USD)",
                             currency, rate)
                else:
                    raise ValueError(f"No exchange rate found for {currency}. Please update exchange rates in settings.")
            except Exception as e:
                log.error("[create_split_PE] Rate lookup failed for %s: %s", currency, e)
                raise

        # If caller supplied a USD-per-local rate (< 1), invert it
        if 0 < rate < 1 and currency in ("ZWD", "ZWG", "ZIG"):
            rate = 1.0 / rate
            log.info("[create_split_PE] Inverted to local per USD for %s: %.6f", currency, rate)

        if currency == "USD":
            rate = 1.0

        # ------------------------------------------------------------------ #
        # Convert local amount → USD basis for ZWG/ZWD splits
        # For USD splits amount_local is already USD, no conversion needed.
        # ------------------------------------------------------------------ #
        if currency in ("ZWD", "ZWG", "ZIG") and rate > 0:
            amount_usd = round(amount_local / rate, 6)
            
        else:
            amount_usd = amount_local   # USD leg

        # Cap at the invoice's remaining allocation — we never push more
        # than what was required on this mode, even if the customer tendered
        # extra cash (the surplus prints as change on the receipt).
        if remaining_usd != float("inf") and amount_usd > remaining_usd + 0.005:
            log.info(
                "[create_split_PE] capping %s: tendered_USD=%.4f -> allocation_USD=%.4f "
                "(remaining=%.4f)", method, amount_usd, remaining_usd, remaining_usd)
            amount_usd = round(remaining_usd, 4)

        if amount_usd <= 0.005:
            log.info("[create_split_PE] Split %d: allocation exhausted — skipping", idx + 1)
            continue

        log.info(
            "[create_split_PE] method=%s  currency=%s  local_amount=%.4f %s  "
            "rate=%.6f (local/USD)  -> paid_amount(USD)=%.6f  "
            "-> received_amount=%.4f %s",
            method, currency, amount_local, currency,
            rate, amount_usd,
            round(amount_usd * rate, 4), currency,
        )

        # CRITICAL FIX: Create a proper copy of the sale dict with ALL required fields
        split_sale = {
            "id": sale.get("id"),
            "invoice_no": sale.get("invoice_no"),
            "invoice_date": sale.get("invoice_date"),
            "customer_name": sale.get("customer_name"),
            "frappe_ref": sale.get("frappe_ref"),  # ← THIS IS THE KEY FIX - pass parent frappe_ref
            "currency": currency,
            "paid_amount": amount_usd,   # ← USD basis, NOT local amount
            "total": amount_usd,
            "method": method,
            "exchange_rate": rate,       # local per USD
            "gl_account": gl_account,
        }
        
        log.info("[create_split_PE] Split sale frappe_ref being passed: %s", split_sale.get("frappe_ref"))

        new_id = create_payment_entry(
            split_sale,
            override_rate=rate if rate > 0 else None,
            override_account=gl_account,
            shift_id=shift_id or sale.get("shift_id"),
            _is_split=True,
        )
        if new_id:
            ids.append(new_id)
            if remaining_usd != float("inf"):
                remaining_usd = max(remaining_usd - amount_usd, 0.0)
            log.info(
                "[create_split_PE] Created PE %d for %s "
                "(local=%.4f %s  paid_USD=%.6f  rate=%.6f  received=%.4f %s  "
                "remaining_usd=%.4f)",
                new_id, method,
                amount_local, currency,
                amount_usd, rate,
                round(amount_usd * rate, 4), currency,
                remaining_usd if remaining_usd != float("inf") else -1,
            )
        else:
            log.warning("[create_split_PE] Failed to create PE for %s", method)

    log.info("[create_split_PE] ========== END ==========")
    log.info("[create_split_PE] Created %d of %d entries", len(ids), len(splits))
    return ids


# =============================================================================
# LOCAL DB - read / update payment_entries for sync
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
          AND (pe.sync_attempts IS NULL OR pe.sync_attempts < 20)
          AND (pe.payment_type IS NULL OR pe.payment_type = 'Receive')
          AND (pe.frappe_invoice_ref IS NOT NULL
               OR s.frappe_ref IS NOT NULL)
        ORDER BY ISNULL(pe.sync_attempts, 0) ASC, pe.id DESC
    """)
    rows = fetchall_dicts(cur)
    conn.close()
    
    # Debug logging to see what's being fetched
    for row in rows:
        log.debug("Unsynced PE %d: frappe_invoice_ref=%s, sale_frappe_ref=%s", 
                 row.get("id"), row.get("frappe_invoice_ref"), row.get("sale_frappe_ref"))
    
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
        UPDATE payment_entries
        SET frappe_invoice_ref = s.frappe_ref
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


def _increment_sync_attempt(pe_id: int, error_msg: str) -> None:
    try:
        from database.db import get_connection
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute("""
            UPDATE payment_entries
            SET sync_attempts = ISNULL(sync_attempts, 0) + 1,
                last_error = ?
            WHERE id = ?
        """, (str(error_msg)[:500], pe_id))
        conn.commit()
        conn.close()
    except Exception as ex:
        log.debug("Failed to increment sync attempt: %s", ex)


# =============================================================================
# BUILD FRAPPE PAYLOAD (sync side)
# =============================================================================

def _build_payload(pe: dict, defaults: dict,
                   api_key: str, api_secret: str, host: str) -> dict:
    """
    Build the Frappe Payment Entry payload from a local payment_entries row.

    DB invariants (set at creation time):
      pe["paid_amount"]      = USD basis figure
      pe["received_amount"]  = paid_amount * exchange_rate  = LOCAL currency figure
      pe["exchange_rate"]    = local-per-USD  (>= 1 for ZWG/ZWD, 1.0 for USD)

    Frappe mapping:
      paid_amount            → USD basis  (pe["paid_amount"])
      received_amount        → LOCAL figure  (pe["received_amount"])
      source_exchange_rate   → local-per-USD  (pe["exchange_rate"])
      target_exchange_rate   → 1.0  (paid_to GL account is local-currency denominated)

    For USD payments all three figures are equal and both rates are 1.0.
    """
    company       = defaults.get("server_company", "")
    base_currency = defaults.get("server_company_currency", "USD").strip().upper() or "USD"

    currency = (pe.get("currency") or pe.get("paid_to_account_currency") or base_currency).upper()

    # --- pull stored figures directly from DB row ---
    paid_amount_usd    = float(pe.get("paid_amount") or 0)
    received_amount_local = float(pe.get("received_amount") or 0)
    exch_rate          = float(pe.get("exchange_rate") or pe.get("source_exchange_rate") or 0)

    # Guard: normalise rate to local-per-USD (>= 1 for ZWG/ZWD)
    if currency in ("ZWD", "ZWG", "ZIG"):
        if exch_rate > 0 and exch_rate < 1:
            exch_rate = 1.0 / exch_rate
            log.info("[build_payload] Normalised rate to local/USD for %s: %.6f",
                     currency, exch_rate)
        # If received_amount wasn't stored correctly, recompute it
        if received_amount_local <= 0 and paid_amount_usd > 0 and exch_rate > 0:
            received_amount_local = round(paid_amount_usd * exch_rate, 4)
            log.warning(
                "[build_payload] PE %d: received_amount was 0, recomputed as %.4f %s",
                pe.get("id", 0), received_amount_local, currency,
            )

        # Frappe: paid_amount = USD basis, received_amount = LOCAL figure
        paid_amount_for_frappe    = paid_amount_usd
        received_amount_for_frappe = received_amount_local
        # FRAPPE: rates are from [account currency] to [company base currency]
        # Since paid_from is base_currency (USD), its rate is always 1.0
        source_exch_rate           = 1.0
        # paid_to is ZIG, so its rate is USD-per-ZIG (e.g. 1/30 = 0.033)
        target_exch_rate           = round(1.0 / exch_rate, 9) if exch_rate > 0 else 1.0

        log.info(
            "[build_payload] %s payment: paid(USD)=%.4f -> FromRate=%.4f, ToRate=%.6f",
            currency, paid_amount_for_frappe, source_exch_rate, target_exch_rate
        )

    # --- MOP / GL account ---
    frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()
    stored_mop = (pe.get("mode_of_payment") or "").strip()
    paid_to    = (pe.get("paid_to") or "").strip()
    mop_name, gl_account = _resolve_mop(stored_mop, paid_to, currency)

    paid_to_currency = _get_gl_account_currency(
        gl_account,
        fallback=currency if currency != "USD" else base_currency,
    )

    if currency.startswith("USD") and paid_to_currency in ("ZWD", "ZWG", "ZIG"):
        # Special Case: Paid in USD but deposited to a local-currency account.
        # Frappe requires the received_amount to be in the target account currency.
        try:
            from models.exchange_rate import get_rate
            rate = get_rate(paid_to_currency, "USD")
            if rate and rate > 0:
                raw_rate = (1.0 / rate) if rate < 1 else rate
            else:
                raw_rate = 1.0 # fallback
        except Exception:
            raw_rate = 1.0

        paid_amount_for_frappe     = paid_amount_usd
        received_amount_for_frappe = round(paid_amount_usd * raw_rate, 4)
        source_exch_rate           = 1.0
        target_exch_rate           = round(1.0 / raw_rate, 9) if raw_rate > 0 else 1.0
        log.info("[build_payload] USD-to-%s transfer identified. Multiplied received_amount by %.4f",
                 paid_to_currency, raw_rate)
    else:
        # Pure USD — all amounts identical, rates both 1.0
        paid_amount_for_frappe     = paid_amount_usd
        received_amount_for_frappe = received_amount_local if received_amount_local > 0 \
                                     else paid_amount_usd
        source_exch_rate           = 1.0
        target_exch_rate           = 1.0

    # --- Party ---
    _walk_in         = defaults.get("server_walk_in_customer", "").strip() or "Default"
    _WALK_IN_ALIASES = {"walk-in", "walk in", "walkin", ""}
    raw_party        = (pe.get("party") or "").strip()
    party            = _walk_in if raw_party.lower() in _WALK_IN_ALIASES else raw_party or _walk_in

    log.info(
        "[build_payload] PE id=%d  MOP='%s'  GL='%s'  currency=%s  "
        "paid_frappe=%.4f USD  received_frappe=%.4f %s  "
        "source_rate=%.8f (local/USD)  target_rate=%.8f  inv=%s",
        pe.get("id", 0), mop_name, gl_account,
        currency,
        paid_amount_for_frappe,
        received_amount_for_frappe, currency,
        source_exch_rate, target_exch_rate,
        frappe_inv or "MISSING",
    )

    if not frappe_inv:
        log.warning("[build_payload] PE %d has no frappe_invoice_ref - will be skipped",
                    pe.get("id", 0))

    payload = {
        "doctype":                    "Payment Entry",
        "payment_type":               "Receive",
        "party_type":                 "Customer",
        "party":                      party,
        "party_name":                 party,
        "paid_from_account_currency": base_currency,
        "paid_to_account_currency":   paid_to_currency,
        "paid_amount":                paid_amount_for_frappe,      # USD basis
        "received_amount":            received_amount_for_frappe,  # LOCAL figure (ZWG/ZWD)
        "source_exchange_rate":       source_exch_rate,            # local per USD
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
            f"POS Payment - {mop_name} | "
            f"USD {paid_amount_for_frappe:.2f} @ {source_exch_rate:.4f} {currency}/USD = "
            f"{currency} {received_amount_for_frappe:.2f}" +
            (f" | Discount: {pe.get('discount_percent')}% / ${pe.get('discount_amount')}" if float(pe.get('discount_amount') or 0) > 0 else "")
        ),
        "docstatus": 1,
    }

    if gl_account:
        payload["paid_to"] = gl_account
    if company:
        payload["company"] = company

    if frappe_inv:
        payload["references"] = [{
            "reference_doctype": "Sales Invoice",
            "reference_name":    frappe_inv,
            "allocated_amount":  paid_amount_for_frappe,   # USD amount for allocation
        }]

    log.debug(
        "[build_payload] Final: paid=%.4f USD  received=%.4f %s  "
        "source_rate=%.8f (%s/USD)  target_rate=%.8f  MOP='%s'  GL='%s'",
        paid_amount_for_frappe, received_amount_for_frappe, currency,
        source_exch_rate, currency, target_exch_rate, mop_name, gl_account,
    )
    return payload


# =============================================================================
# PUSH ONE PAYMENT ENTRY TO FRAPPE
# =============================================================================

def _push_payment_entry(pe: dict, api_key: str, api_secret: str,
                        defaults: dict, host: str) -> str | None:
    pe_id  = pe["id"]
    inv_no = pe.get("sale_invoice_no", str(pe_id))

    frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()
    if not frappe_inv:
        log.warning("Payment %d - Sales Invoice not yet on Frappe, skipping. pe.frappe_invoice_ref=%s, pe.sale_frappe_ref=%s", 
                   pe_id, pe.get("frappe_invoice_ref"), pe.get("sale_frappe_ref"))
        return None

    payload = _build_payload(pe, defaults, api_key, api_secret, host)

    log.info("Pushing PE %d: %s  paid=%.2f USD  received=%.2f %s  linked to invoice=%s",
             pe_id, inv_no,
             float(pe.get("paid_amount", 0)),
             float(pe.get("received_amount", 0)),
             pe.get("currency", ""),
             frappe_inv)

    url = f"{host}/api/resource/Payment%20Entry"
    req = urllib.request.Request(
        url=url,
        data=json.dumps(
            payload,
            default=lambda o: o.isoformat() if hasattr(o, "isoformat") else str(o),
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
            log.info("PE %d -> Frappe %s", pe_id, name)
            return name or "SYNCED"

    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode())
            msg = (err.get("exception") or err.get("message") or
                   str(err.get("_server_messages", "")) or f"HTTP {e.code}")
        except Exception:
            msg = f"HTTP {e.code}"

        if e.code == 409:
            log.info("PE %d already on Frappe (409)", pe_id)
            return "DUPLICATE"

        if e.code == 417:
            _perma = ("already been fully paid", "already paid", "fully paid",
                      "allocated amount cannot be greater than outstanding amount")
            if any(p in msg.lower() for p in _perma):
                log.info("PE %d - invoice already paid", pe_id)
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
# PUBLIC - push all unsynced payment entries
# =============================================================================

def push_unsynced_payment_entries() -> dict:
    result = {"pushed": 0, "failed": 0, "skipped": 0, "total": 0}

    api_key, api_secret = _get_credentials()
    if not api_key or not api_secret:
        log.warning("No credentials - skipping payment entry sync.")
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

    log.info("Pushing %d payment entry(ies) to Frappe...", len(entries))

    for pe in entries:
        frappe_name = _push_payment_entry(pe, api_key, api_secret, defaults, host)
        if frappe_name:
            mark_payment_synced(pe["id"], frappe_name)
            result["pushed"] += 1
        elif frappe_name is None:
            result["skipped"] += 1
        else:
            result["failed"] += 1
        time.sleep(3)

    log.info("Payment sync done - pushed=%d  failed=%d  skipped=%d",
             result["pushed"], result["failed"], result["skipped"])
    return result


# =============================================================================
# IMMEDIATE SYNC TRIGGER (called after create_payment_entry)
# =============================================================================

def _trigger_sync_now() -> None:
    """
    Fire a single sync cycle in a background thread immediately after a
    payment entry is created.  Uses the same lock as the daemon so the two
    never run concurrently.
    """
    def _run():
        if _sync_lock.acquire(blocking=False):
            try:
                log.info("[trigger_sync_now] Running immediate sync after PE creation.")
                push_unsynced_payment_entries()
            except Exception as e:
                log.error("[trigger_sync_now] Sync error: %s", e)
            finally:
                _sync_lock.release()
        else:
            log.debug("[trigger_sync_now] Sync already running - skipping immediate trigger.")

    t = threading.Thread(target=_run, daemon=True, name="PaymentSyncImmediate")
    t.start()


# =============================================================================
# BACKGROUND DAEMON
# =============================================================================

def _sync_loop() -> None:
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
            log.debug("Previous payment sync still running - skipping.")
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


# =============================================================================
# DEBUG
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    print("Running one payment entry sync cycle...")
    r = push_unsynced_payment_entries()
    print(f"\nResult: {r['pushed']} pushed, {r['failed']} failed, "
          f"{r['skipped']} skipped (of {r['total']} total)")