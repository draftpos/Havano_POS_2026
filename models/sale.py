from database.db import get_connection, fetchall_dicts, fetchone_dict
from models.product import adjust_stock, get_product_by_id
from models.receipt import ReceiptData, Item
from services.printing_service import printing_service

from datetime import date
import json
from pathlib import Path
import threading
import time

# =============================================================================
# INVOICE NUMBER  —  uses prefix + start_number from company_defaults
#
# Examples:
#   prefix="INV",  start=1   →  INV-000001
#   prefix="HV",   start=100 →  HV-000100
#   prefix="",     start=1   →  000001
# =============================================================================

def _get_invoice_settings() -> tuple[str, int]:
    """Returns (prefix, start_number) from company_defaults."""
    try:
        from models.company_defaults import get_defaults
        d = get_defaults()
        prefix = str(d.get("invoice_prefix") or "").strip().upper()
        start  = int(d.get("invoice_start_number") or 0)
        return prefix, start
    except Exception:
        return "", 0


def _format_invoice_no(seq: int) -> str:
    """
    Format invoice number and ensure it hasn't been used before.
    """
    prefix, _ = _get_invoice_settings()

    if prefix:
        clean_prefix = prefix.replace("-", "").replace("_", "").upper()
        candidate = f"{clean_prefix}-{seq:09d}"  # 9 digits required by ZIMRA
    else:
        candidate = f"{seq:09d}"

    # Check if this invoice number already exists in sales table
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM sales WHERE invoice_no = ?", (candidate,))
    count = cur.fetchone()[0]
    conn.close()

    if count > 0:
        # If exists, add timestamp to make it unique
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"{candidate}-{timestamp}"

    return candidate


def get_next_invoice_number() -> int:
    """
    Returns the next invoice sequence number.
    Starts from invoice_start_number if no sales exist yet,
    otherwise continues from MAX(invoice_number) + 1.
    """
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("SELECT COALESCE(MAX(invoice_number), 0) FROM sales")
    row = cur.fetchone()
    conn.close()
    current_max = int(row[0])
    if current_max == 0:
        _, start = _get_invoice_settings()
        return max(start, 1)
    return current_max + 1


# =============================================================================
# READ
# =============================================================================

_SALE_SELECT = """
    SELECT s.id, s.invoice_number, s.created_at, s.cashier_id,
       s.total, s.tendered, s.method,
       COALESCE(u.username, '') AS username,
       s.invoice_no, s.invoice_date, s.kot,
       s.customer_name, s.customer_contact,
       s.currency, s.subtotal, s.total_vat,
       s.discount_amount, s.receipt_type, s.footer,
       s.cashier_name,
       s.synced,
       COALESCE(s.frappe_ref,      '')  AS frappe_ref,
       COALESCE(s.total_items,     0)   AS total_items,
       COALESCE(s.change_amount,   0)   AS change_amount,
       COALESCE(s.is_on_account,   0)   AS is_on_account,
       COALESCE(s.shift_id,        NULL) AS shift_id,
       s.fiscal_status,
       s.fiscal_qr_code,
       s.fiscal_verification_code,
       s.fiscal_receipt_counter,
       s.fiscal_global_no,
       s.fiscal_sync_date,
       s.fiscal_error,
       -- ── Multi-currency fields ──────────────────────────────────────────
       -- total_usd    : invoice total always in USD  (used by Frappe PE)
       -- total_zwd    : invoice total in ZWD if paid in ZWD, else NULL
       -- tendered_usd : raw USD cash given by customer (change calc only)
       -- tendered_zwd : raw ZWD cash given by customer (change calc only)
       -- exchange_rate: rate at time of sale (foreign → USD)
       COALESCE(s.total_usd,     0)    AS total_usd,
       COALESCE(s.total_zwd,     0)    AS total_zwd,
       COALESCE(s.tendered_usd,  0)    AS tendered_usd,
       COALESCE(s.tendered_zwd,  0)    AS tendered_zwd,
       COALESCE(s.exchange_rate, 1)    AS exchange_rate,
       COALESCE(s.order_number,  0)    AS order_number,
       COALESCE(C.company_name,  '')  AS company_name,
       COALESCE(C.address_1,     '')  AS address_1,
       COALESCE(C.address_2,     '')  AS address_2,
       COALESCE(C.vat_number,    '')  AS vat_number,
       C.tin_number,
       C.footer_text,
       C.phone,
       C.email,
       C.zimra_serial_no,
       C.zimra_device_id
FROM sales s
LEFT JOIN users u ON u.id = s.cashier_id
CROSS JOIN company_defaults C
"""


def get_all_sales() -> list[dict]:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(_SALE_SELECT + " ORDER BY s.id DESC")
    rows = fetchall_dicts(cur)
    conn.close()
    return [_sale_to_dict(r) for r in rows]


def get_sale_by_id(sale_id: int) -> dict | None:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(_SALE_SELECT + " WHERE s.id = ?", (sale_id,))
    row = fetchone_dict(cur)
    if not row:
        conn.close()
        return None
    sale = _sale_to_dict(row)
    sale["items"] = _fetch_items(sale_id, cur)
    sale["outstanding"] = float(sale["total"]) - float(sale["tendered"])
    conn.close()
    return sale


def get_sale_items(sale_id: int) -> list[dict]:
    conn = get_connection()
    cur  = conn.cursor()
    items = _fetch_items(sale_id, cur)
    conn.close()
    return items


def get_today_sales() -> list[dict]:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(
        _SALE_SELECT +
        " WHERE CAST(s.created_at AS DATE) = CAST(GETDATE() AS DATE)"
        " ORDER BY s.id DESC"
    )
    rows = fetchall_dicts(cur)
    conn.close()
    return [_sale_to_dict(r) for r in rows]


def get_today_total() -> float:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT COALESCE(SUM(total), 0)
        FROM sales
        WHERE CAST(created_at AS DATE) = CAST(GETDATE() AS DATE)
    """)
    row = cur.fetchone()
    conn.close()
    return float(row[0])


def get_today_total_by_method() -> dict:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT method, COALESCE(SUM(total), 0)
        FROM sales
        WHERE CAST(created_at AS DATE) = CAST(GETDATE() AS DATE)
        GROUP BY method
    """)
    rows = cur.fetchall()
    conn.close()
    return {r[0]: float(r[1]) for r in rows}


def get_unsynced_sales() -> list[dict]:
    conn = get_connection()
    cur  = conn.cursor()
    # Exclude rows where syncing=1 — those are mid-push in another thread.
    # The upload worker will pick them up on the next cycle if the push failed
    # and the lock was released.
    cur.execute(_SALE_SELECT + " WHERE s.synced = 0 AND (s.syncing IS NULL OR s.syncing = 0) ORDER BY s.id")
    rows = fetchall_dicts(cur)
    conn.close()
    return [_sale_to_dict(r) for r in rows]


def get_sales_with_frappe_ref() -> list[dict]:
    """Returns all sales that have been matched to a Frappe document."""
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(
        _SALE_SELECT +
        " WHERE s.frappe_ref IS NOT NULL AND s.frappe_ref != ''"
        " ORDER BY s.id DESC"
    )
    rows = fetchall_dicts(cur)
    conn.close()
    return [_sale_to_dict(r) for r in rows]


def get_credit_sales() -> list[dict]:
    """Returns all sales with outstanding balance (is_on_account = True)."""
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(
        _SALE_SELECT +
        " WHERE s.is_on_account = 1 AND s.total > s.tendered"
        " ORDER BY s.id DESC"
    )
    rows = fetchall_dicts(cur)
    conn.close()
    sales = [_sale_to_dict(r) for r in rows]
    for sale in sales:
        sale["outstanding"] = sale["total"] - sale["tendered"]
    return sales


def get_inconsistent_sales() -> list[dict]:
    """
    Returns sales that are inconsistent: tendered = 0 but is_on_account = 0
    These should be fixed by calling fix_inconsistent_sales()
    """
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(
        _SALE_SELECT +
        " WHERE s.tendered = 0 AND s.is_on_account = 0"
        " ORDER BY s.id"
    )
    rows = fetchall_dicts(cur)
    conn.close()
    return [_sale_to_dict(r) for r in rows]


def fix_inconsistent_sales() -> int:
    """
    Fixes inconsistent sales where tendered = 0 but is_on_account = 0
    by setting is_on_account = 1.
    Returns number of sales fixed.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, invoice_no, total, created_at
        FROM sales
        WHERE tendered = 0 AND (is_on_account = 0 OR is_on_account IS NULL)
    """)
    inconsistent = cur.fetchall()

    for row in inconsistent:
        sale_id, invoice_no, total, created_at = row
        print(f"[FIX] Sale {invoice_no} (ID: {sale_id}) has tendered=0 but is_on_account=0 - fixing...")

    cur.execute("""
        UPDATE sales
        SET is_on_account = 1
        WHERE tendered = 0 AND (is_on_account = 0 OR is_on_account IS NULL)
    """)

    affected = cur.rowcount
    conn.commit()
    conn.close()

    if affected > 0:
        print(f"[FIX] Updated {affected} inconsistent sale(s) to is_on_account=1")

    return affected


def get_sales_by_shift(shift_id: int) -> list[dict]:
    """Get all sales that belong to a specific shift."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        _SALE_SELECT +
        " WHERE s.shift_id = ?"
        " ORDER BY s.id DESC",
        (shift_id,)
    )
    rows = fetchall_dicts(cur)
    conn.close()
    return [_sale_to_dict(r) for r in rows]


def get_pending_fiscalization_sales() -> list[dict]:
    """Get sales that need fiscalization (pending or failed)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, invoice_no, total, fiscal_status, fiscal_error, frappe_ref
        FROM sales
        WHERE fiscal_status IN ('pending', 'failed')
        AND (frappe_ref IS NOT NULL AND frappe_ref != '')
        ORDER BY id
    """)
    rows = fetchall_dicts(cur)
    conn.close()
    return rows


# =============================================================================
# WRITE - CREATE INVOICE
# =============================================================================

def create_sale(
    items:             list[dict],
    total:             float,
    tendered:          float,
    method:            str   = "Cash",
    cashier_id:        int   = None,
    cashier_name:      str   = "",
    customer_name:     str   = "",
    customer_contact:  str   = "",
    company_name:      str   = "",
    kot:               str   = "",
    currency:          str   = "USD",
    subtotal:          float = None,
    total_vat:         float = 0.0,
    discount_amount:   float = 0.0,
    discount_percent:  float = 0.0,
    receipt_type:      str   = "Invoice",
    footer:            str   = "",
    change_amount:     float = None,
    is_on_account:     bool  = False,
    skip_stock:        bool  = False,
    skip_print:        bool  = False,
    shift_id:          int   = None,
    transaction_id:    str   = None,
    idempotency_key:   str   = None,
    # ── Multi-currency fields ──────────────────────────────────────────────
    # total_usd    : invoice total in USD — always required for Frappe PE
    #                If not supplied we calculate it from total + exchange_rate.
    # exchange_rate: foreign_currency → USD rate at time of sale (e.g. ZWD→USD)
    #                If currency == "USD" this is always 1.0.
    total_usd:         float = None,
    exchange_rate:     float = None,
    # Per-method payment breakdown used for the receipt's Payment Details block.
    # Each dict is expected to carry: method, base_value (USD), native_amount,
    # native_currency, is_credit. Stashed on the sale dict so _print_receipt
    # can render a multi-currency breakdown without re-querying payment_entries.
    splits:            list | None = None,
) -> dict:
    """
    Creates a single invoice and triggers fiscalization in background.

    idempotency_key and transaction_id both serve the same purpose — preventing
    duplicate sales. If idempotency_key is supplied it is used as the
    transaction_id so a single duplicate-detection path handles both.
    """
    from datetime import date, datetime
    from models.product import get_product_by_id, adjust_stock

    # Unify the two alias parameters — whichever is provided wins
    transaction_id = transaction_id or idempotency_key

    # Log every call
    print(f"\n{'🔔' * 40}")
    print(f"CREATE_SALE CALLED at {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
    print(f"Transaction ID: {transaction_id}")
    print(f"Total: {total}, Items: {len(items)}")
    print(f"{'🔔' * 40}\n")

    # Duplicate prevention
    if transaction_id:
        try:
            conn = get_connection()
            cur = conn.cursor()

            cur.execute("""
                IF NOT EXISTS (
                    SELECT 1 FROM INFORMATION_SCHEMA.TABLES
                    WHERE TABLE_NAME = 'transaction_tracking'
                )
                CREATE TABLE transaction_tracking (
                    id             INT IDENTITY(1,1) PRIMARY KEY,
                    transaction_id NVARCHAR(100) NOT NULL UNIQUE,
                    sale_id        INT           NULL,
                    created_at     DATETIME2     NOT NULL DEFAULT SYSDATETIME(),
                    total          DECIMAL(12,2),
                    item_count     INT
                )
            """)
            conn.commit()

            cur.execute("""
                SELECT sale_id, created_at
                FROM transaction_tracking
                WHERE transaction_id = ?
                AND created_at > DATEADD(SECOND, -60, SYSDATETIME())
            """, (transaction_id,))

            existing = cur.fetchone()
            if existing:
                sale_id, created_at = existing
                print(f"⚠️ DUPLICATE DETECTED! transaction_id={transaction_id} "
                      f"already processed at {created_at}. "
                      f"Returning existing sale ID: {sale_id}")
                conn.close()
                return get_sale_by_id(sale_id)

            conn.close()
        except Exception as e:
            print(f"[WARNING] Transaction tracking error: {e}")

    tendered_amount = float(tendered) if tendered else 0.0
    total_amount    = float(total)

    # ── Multi-currency calculations ────────────────────────────────────────
    # currency     : the currency the cashier selected (e.g. "ZWD" or "USD")
    # total        : the invoice total IN THAT CURRENCY as displayed on screen
    #                e.g. if currency=ZWD, total=5000 means ZWD 5000
    # total_usd    : always the USD equivalent  → used by Frappe PE + pos_upload
    # total_zwd    : the ZWD amount if currency==ZWD, else 0
    # tendered_usd : USD equivalent of cash given (change display only)
    # tendered_zwd : ZWD cash given if currency==ZWD (change display only)
    # exchange_rate: foreign→USD rate (e.g. ZWD→USD = 0.00277)
    #                If currency==USD this is always 1.0
    currency_upper = (currency or "USD").strip().upper()

    # Resolve exchange rate: use supplied value, else look up local DB
    if exchange_rate is not None:
        _exch = float(exchange_rate)
    else:
        _exch = 1.0
        if currency_upper != "USD":
            try:
                from models.exchange_rate import get_rate
                r = get_rate(currency_upper, "USD")
                if r and float(r) > 0:
                    _exch = float(r)
                else:
                    # try inverse
                    inv = get_rate("USD", currency_upper)
                    if inv and float(inv) > 0:
                        _exch = 1.0 / float(inv)
            except Exception as _e:
                print(f"[create_sale] WARNING: Could not get exchange rate for {currency_upper}→USD: {_e}")

    # total_usd: if currency is USD use total directly, else convert
    if total_usd is not None:
        _total_usd = float(total_usd)
    elif currency_upper == "USD":
        _total_usd = total_amount
    else:
        _total_usd = round(total_amount * _exch, 4)

    # total_zwd: only set when currency is ZWD (or ZWG — treated same)
    _total_zwd = total_amount if currency_upper in ("ZWD", "ZWG") else 0.0

    # tendered split by currency
    if currency_upper == "USD":
        _tendered_usd = tendered_amount
        _tendered_zwd = 0.0
    elif currency_upper in ("ZWD", "ZWG"):
        _tendered_zwd = tendered_amount
        _tendered_usd = round(tendered_amount * _exch, 4)
    else:
        _tendered_usd = round(tendered_amount * _exch, 4)
        _tendered_zwd = 0.0

    print(f"[create_sale] Currency={currency_upper}  total={total_amount}  "
          f"total_usd={_total_usd}  total_zwd={_total_zwd}  "
          f"exchange_rate={_exch}  tendered_usd={_tendered_usd}  tendered_zwd={_tendered_zwd}")

    if tendered_amount == 0 and not is_on_account:
        raise ValueError(
            "Cannot create sale with no payment (tendered=0) without marking it as "
            "on account. Please set is_on_account=True for credit sales."
        )

    if change_amount is not None:
        change_val = float(change_amount)
    else:
        change_val = max(0.0, tendered_amount - total_amount)

    # When the POS passed a splits list (multi-method / split payment), the
    # single-active-method `tendered_amount` arg represents only one row, not
    # the real total tendered. Sum the splits' base_value (USD) so tendered_usd,
    # tendered_zwd and change_val reflect every method the cashier took.
    # This must run AFTER change_val is first assigned above so it overrides
    # the single-method calculation.
    if splits:
        try:
            _splits_usd = sum(float(s.get("base_value") or 0) for s in splits)
            if _splits_usd > 0:
                _tendered_usd = round(_splits_usd, 4)
                _z = sum(
                    float(s.get("native_amount") or 0)
                    for s in splits
                    if (s.get("native_currency") or "").upper() in ("ZWD", "ZWG")
                )
                if _z > 0:
                    _tendered_zwd = round(_z, 4)
                change_val = round(max(_tendered_usd - _total_usd, 0.0), 4)
                print(f"[create_sale] splits recalc → tendered_usd={_tendered_usd} "
                      f"tendered_zwd={_tendered_zwd} change_val={change_val}")
        except Exception as _e:
            print(f"[create_sale] splits tendered_usd recalc failed: {_e}")

    seq             = get_next_invoice_number()
    invoice_no      = _format_invoice_no(seq)
    invoice_date    = date.today().isoformat()
    effective_sub   = subtotal if subtotal is not None else total
    total_items_val = sum(float(it.get("qty", 1)) for it in items)

    print(f"[create_sale] Creating sale with {len(items)} items, total: {total_amount}")
    print(f"[create_sale] Invoice number: {invoice_no}")
    print(f"[create_sale] Transaction ID: {transaction_id}")

    conn = get_connection()
    cur  = conn.cursor()

    # Per-shift order number — resets to 1 whenever a new shift opens.
    # Falls back gracefully if the column doesn't exist yet (pre-migration).
    order_number = 1
    if shift_id:
        try:
            cur.execute(
                "SELECT ISNULL(MAX(order_number), 0) + 1 FROM sales WHERE shift_id = ?",
                (shift_id,),
            )
            row = cur.fetchone()
            if row and row[0]:
                order_number = int(row[0])
        except Exception as _oe:
            print(f"[create_sale] order_number lookup skipped: {_oe}")
            order_number = 1

    # Check if fiscal_status column exists
    has_fiscal = False
    try:
        cur.execute("""
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'sales' AND COLUMN_NAME = 'fiscal_status'
        """)
        has_fiscal = cur.fetchone()[0] > 0
    except Exception:
        pass

    try:
        if has_fiscal:
            cur.execute("""
                INSERT INTO sales (
                    invoice_number, invoice_no, invoice_date,
                    total, tendered, method, cashier_id,
                    cashier_name, customer_name, customer_contact,
                    company_name, kot, currency,
                    subtotal, total_vat, discount_amount,
                    receipt_type, footer, synced,
                    total_items, change_amount, is_on_account,
                    shift_id, fiscal_status,
                    total_usd, total_zwd, tendered_usd, tendered_zwd, exchange_rate,
                    order_number
                )
                OUTPUT INSERTED.id
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                seq, invoice_no, invoice_date,
                total_amount, tendered_amount, method, cashier_id,
                cashier_name, customer_name, customer_contact,
                company_name, kot, currency,
                float(effective_sub), float(total_vat), float(discount_amount),
                receipt_type, footer, 0,
                float(total_items_val), float(change_val), 1 if is_on_account else 0,
                shift_id, "pending",
                _total_usd, _total_zwd, _tendered_usd, _tendered_zwd, _exch,
                order_number,
            ))
        else:
            cur.execute("""
                INSERT INTO sales (
                    invoice_number, invoice_no, invoice_date,
                    total, tendered, method, cashier_id,
                    cashier_name, customer_name, customer_contact,
                    company_name, kot, currency,
                    subtotal, total_vat, discount_amount,
                    receipt_type, footer, synced,
                    total_items, change_amount, is_on_account,
                    shift_id,
                    total_usd, total_zwd, tendered_usd, tendered_zwd, exchange_rate,
                    order_number
                )
                OUTPUT INSERTED.id
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                seq, invoice_no, invoice_date,
                total_amount, tendered_amount, method, cashier_id,
                cashier_name, customer_name, customer_contact,
                company_name, kot, currency,
                float(effective_sub), float(total_vat), float(discount_amount),
                receipt_type, footer, 0,
                float(total_items_val), float(change_val), 1 if is_on_account else 0,
                shift_id,
                _total_usd, _total_zwd, _tendered_usd, _tendered_zwd, _exch,
                order_number,
            ))

        sale_id = int(cur.fetchone()[0])
        print(f"[create_sale] Created sale ID: {sale_id}")

        # Pre-fetch order_1..6 (kitchen-printer routing flags) for every part_no
        # in the cart. Cart items don't carry these fields through the UI, so we
        # resolve them from the products table in a single batch query.
        part_nos = {str(it.get("part_no", "")).strip() for it in items if it.get("part_no")}
        order_map: dict[str, tuple] = {}
        if part_nos:
            placeholders = ",".join("?" * len(part_nos))
            try:
                cur.execute(
                    f"SELECT part_no, order_1, order_2, order_3, order_4, order_5, order_6 "
                    f"FROM products WHERE part_no IN ({placeholders})",
                    tuple(part_nos),
                )
                for row in cur.fetchall():
                    order_map[(row[0] or "").strip()] = tuple(1 if row[i] else 0 for i in range(1, 7))
            except Exception as _oe:
                print(f"[create_sale] order_N lookup failed: {_oe}")

        # Insert sale items
        item_insert_count = 0
        for idx, item in enumerate(items):
            part_no = str(item.get("part_no", "")).strip()
            # Prefer the item's own order_N if already set (quotations / laybye
            # conversions carry them forward); else fall back to the product lookup.
            if any(item.get(f"order_{i}") is not None for i in range(1, 7)):
                order_flags = tuple(1 if item.get(f"order_{i}") else 0 for i in range(1, 7))
            else:
                order_flags = order_map.get(part_no, (0, 0, 0, 0, 0, 0))

            cur.execute("""
                INSERT INTO sale_items (
                    sale_id, part_no, product_name, qty, price,
                    discount, tax, total,
                    tax_type, tax_rate, tax_amount, remarks,
                    is_pharmacy, dosage, batch_no, expiry_date,
                    uom,
                    order_1, order_2, order_3, order_4, order_5, order_6
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sale_id,
                part_no,
                str(item.get("product_name", "")),
                float(item.get("qty", 1)),
                float(item.get("price", 0)),
                float(item.get("discount", 0)),
                str(item.get("tax", "")),
                float(item.get("total", 0)),
                str(item.get("tax_type", "")),
                float(item.get("tax_rate", 0.0)),
                float(item.get("tax_amount", 0.0)),
                str(item.get("remarks", "")),
                1 if item.get("is_pharmacy") else 0,
                item.get("dosage"),
                item.get("batch_no"),
                item.get("expiry_date"),
                (str(item.get("uom")) if item.get("uom") else None),
                *order_flags,
            ))
            item_insert_count += 1

        # Record transaction for duplicate prevention
        if transaction_id:
            try:
                cur.execute("""
                    INSERT INTO transaction_tracking (transaction_id, sale_id, total, item_count)
                    VALUES (?, ?, ?, ?)
                """, (transaction_id, sale_id, total_amount, len(items)))
            except Exception as e:
                print(f"[WARNING] Failed to record transaction: {e}")

        conn.commit()
        conn.close()

        print(f"[create_sale] Successfully created sale ID: {sale_id} with invoice: {invoice_no}")

        sale = get_sale_by_id(sale_id)

        # Stash the payment split list on the sale dict so _print_receipt /
        # receipt builders can render Payment Details without re-querying
        # payment_entries (which are created AFTER this create_sale call).
        if splits:
            sale["splits"] = list(splits)

        # Fiscalization starts FIRST so the print-wait poll has something to detect.
        _trigger_fiscalization_background(sale_id)

        if not skip_print:
            # Run print on a background thread so time.sleep() in _print_receipt
            # never blocks the Qt main thread, which would starve the fiscalization
            # thread and make the 3-second poll always time out.
            _sale_snap   = dict(sale)   # snapshot so thread has its own reference
            _items_snap  = list(items)
            def _do_print(
                _s=_sale_snap, _i=_items_snap,
                _t=tendered_amount, _c=change_val, _cur=currency,
                _k=kot, _m=method, _cn=cashier_name,
                _cust=customer_name, _cc=customer_contact, _f=footer
            ):
                _print_receipt(_s, _i, _t, _c, _cur, _k, _m, _cn, _cust, _cc, _f)
                print_kitchen_orders(_s)

            threading.Thread(target=_do_print, daemon=True).start()

        return sale

    except Exception as e:
        conn.rollback()
        conn.close()
        print(f"[ERROR] Failed to create sale: {e}")
        import traceback
        traceback.print_exc()
        raise


# =============================================================================
# FISCALIZATION
# =============================================================================

def _trigger_fiscalization_background(sale_id: int):
    """Trigger fiscalization in a background thread. Retries until successful."""
    def _run_fiscalization():
        retry_delay = 30
        attempt = 0

        while True:
            attempt += 1
            try:
                from services.fiscalization_service import get_fiscalization_service

                fiscal_service = get_fiscalization_service()

                if not fiscal_service.is_fiscalization_enabled():
                    print(f"[Fiscalization] Not enabled, marking sale {sale_id} as not_required")
                    _mark_sale_fiscal_status(sale_id, "not_required")
                    return

                sale = get_sale_by_id(sale_id)
                if sale and sale.get("fiscal_status") == "fiscalized":
                    print(f"[Fiscalization] Sale {sale_id} already fiscalized")
                    return

                print(f"[Fiscalization] Attempt {attempt} for sale {sale_id}")
                success = fiscal_service.process_sale_fiscalization(sale_id, skip_sync=False)

                if success:
                    print(f"[Fiscalization] ✅ Sale {sale_id} fiscalized successfully on attempt {attempt}")
                    return
                else:
                    print(f"[Fiscalization] ❌ Sale {sale_id} failed on attempt {attempt}, retrying in {retry_delay}s")
                    time.sleep(retry_delay)

            except Exception as e:
                print(f"[Fiscalization] Error for sale {sale_id}: {e}, retrying in {retry_delay}s")
                time.sleep(retry_delay)

    thread = threading.Thread(target=_run_fiscalization, daemon=True)
    thread.start()


def _mark_sale_fiscal_status(sale_id: int, status: str):
    """Mark sale fiscal status in database."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE sales SET fiscal_status = ? WHERE id = ?", (status, sale_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Fiscalization] Error marking status: {e}")


# =============================================================================
# RECEIPT PRINTING
# =====
# =============================================================================
# RECEIPT PRINTING
# =============================================================================
# # =============================================================================
# RECEIPT PRINTING
# =============================================================================

# def _print_receipt(sale: dict, items: list, tendered: float, change: float,
#                    currency: str, kot: str, method: str, cashier_name: str,
#                    customer_name: str, customer_contact: str, footer_text: str):
#     """Internal function to print receipt with fiscalization wait (up to 3 seconds)."""
#     import time
#     import threading

#     active_printers = _get_active_printers()
#     if not active_printers or not sale:
#         print("⚠️ No active printers configured")
#         return

#     footer = sale.get("footer_text", footer_text or "Thank you for your purchase!")
#     total  = sale["total"]
#     paid   = sale["tendered"]
#     outstanding = total - paid
    
#     # ✅ IMPORTANT: Get the actual currency from the sale record
#     # The currency field in sales table stores what currency was used for payment
#     actual_currency = sale.get("currency", currency or "USD")
    
#     # Get exchange rate and convert display amounts if needed
#     exchange_rate = sale.get("exchange_rate", 1.0)
#     total_usd = sale.get("total_usd", total)
#     tendered_usd = sale.get("tendered_usd", paid)
#     change_usd = sale.get("change_amount", change)
    
#     # For display on receipt, we need to show amounts in the actual payment currency
#     if actual_currency.upper() != "USD" and exchange_rate != 1.0:
#         # Convert from USD to actual currency for display
#         display_total = total_usd * exchange_rate if total_usd else total
#         display_tendered = tendered_usd * exchange_rate if tendered_usd else paid
#         display_change = change_usd * exchange_rate if change_usd else change
#     else:
#         display_total = total
#         display_tendered = paid
#         display_change = change

#     # Only annotate footer for credit/partial cases
#     if sale.get("is_on_account", False) and paid == 0:
#         footer = f"CREDIT SALE - Total Due: {display_total:.2f} {actual_currency}\n{footer}"
#     elif 0 < paid < total:
#         footer = f"PARTIAL PAYMENT - Paid: {display_tendered:.2f} {actual_currency} | Balance: {outstanding:.2f} {actual_currency}\n{footer}"

#     # Check if fiscalization is enabled
#     try:
#         from services.fiscalization_service import get_fiscalization_service
#         fiscal_service = get_fiscalization_service()
#         fiscal_enabled = fiscal_service.is_fiscalization_enabled() if fiscal_service else False
#     except Exception as e:
#         print(f"[Fiscalization] Error checking fiscal status: {e}")
#         fiscal_enabled = False

#     # Get current fiscal data
#     fiscal_qr_code = sale.get("fiscal_qr_code", "")
#     fiscal_v_code  = sale.get("fiscal_verification_code", "")
#     fiscal_ready   = bool(fiscal_qr_code and fiscal_qr_code.strip())

#     # If fiscalization is enabled but QR not ready yet, wait up to 3 seconds
#     if fiscal_enabled and not fiscal_ready:
#         print(f"⏳ Waiting for fiscalization for sale {sale.get('id')}...")
#         wait_start   = time.time()
#         wait_seconds = 3

#         while time.time() - wait_start < wait_seconds:
#             try:
#                 from models.sale import get_sale_by_id
#                 refreshed_sale = get_sale_by_id(sale.get("id"))
#                 if refreshed_sale:
#                     fiscal_qr_code = refreshed_sale.get("fiscal_qr_code", "")
#                     fiscal_v_code  = refreshed_sale.get("fiscal_verification_code", "")
#                     if fiscal_qr_code and fiscal_qr_code.strip():
#                         fiscal_ready = True
#                         print(f"✅ Fiscalization ready after {time.time() - wait_start:.1f} seconds")
#                         sale.update(refreshed_sale)
#                         # Update display amounts with refreshed data
#                         if actual_currency.upper() != "USD" and exchange_rate != 1.0:
#                             display_total = sale.get("total_usd", total) * exchange_rate
#                             display_tendered = sale.get("tendered_usd", paid) * exchange_rate
#                             display_change = sale.get("change_amount", change) * exchange_rate
#                         break
#             except Exception as e:
#                 print(f"⚠️ Error checking fiscal status: {e}")

#             time.sleep(0.3)

#         if not fiscal_ready:
#             print(f"⚠️ Fiscalization not ready after {wait_seconds}s, printing with pending message")
#     else:
#         fiscal_ready = bool(fiscal_qr_code and fiscal_qr_code.strip())

#     try:
#         receipt = ReceiptData(
#             invoiceNo=sale["invoice_no"],
#             invoiceDate=sale["invoice_date"],
#             companyName=sale.get("company_name", ""),
#             companyAddress=sale.get("address_1", ""),
#             companyAddressLine1=sale.get("address_2", ""),
#             companyAddressLine2="",
#             city="",
#             state="",
#             postcode="",
#             companyEmail=sale.get("email", ""),
#             tel=sale.get("phone", ""),
#             tin=sale.get("tin_number", ""),
#             vatNo=sale.get("vat_number", ""),
#             deviceSerial=sale.get("zimra_serial_no", ""),
#             deviceId=sale.get("zimra_device_id", ""),
#             cashierName=sale.get("cashier_name", cashier_name),
#             customerName=sale.get("customer_name", customer_name),
#             customerContact=sale.get("customer_contact", customer_contact),
#             customerTin="",
#             customerVat="",
#             amountTendered=display_tendered,  # ✅ Use converted amount
#             change=display_change,            # ✅ Use converted amount
#             grandTotal=display_total,         # ✅ Use converted amount
#             subtotal=float(sale.get("subtotal", total)),
#             totalVat=float(sale.get("total_vat", 0)),
#             currency=actual_currency,          # ✅ Use actual payment currency from sales table
#             footer=footer,
#             KOT=kot or "",
#             paymentMode=method,
#         )

#         # Add fiscal QR code if available
#         if fiscal_qr_code and fiscal_qr_code.strip():
#             receipt.qrCode = fiscal_qr_code
#             receipt.vCode  = fiscal_v_code
#         elif fiscal_enabled:
#             receipt.qrCode        = ""
#             receipt.vCode         = ""
#             receipt.fiscal_pending = True

#         for it in sale.get("items", []):
#             # For item display, convert prices to actual currency if needed
#             item_price = float(it["price"])
#             item_total = float(it["total"])
            
#             if actual_currency.upper() != "USD" and exchange_rate != 1.0:
#                 item_price = item_price * exchange_rate
#                 item_total = item_total * exchange_rate
            
#             receipt.items.append(Item(
#                 productName=it["product_name"],
#                 productid=it.get("part_no", ""),
#                 qty=float(it["qty"]),
#                 price=item_price,      # ✅ Converted price
#                 amount=item_total,     # ✅ Converted total
#                 tax_amount=float(it.get("tax_amount", 0)) * exchange_rate if actual_currency.upper() != "USD" else float(it.get("tax_amount", 0))
#             ))

#         for printer_name in active_printers:
#             try:
#                 success = printing_service.print_receipt(receipt, printer_name=printer_name)
#                 if success:
#                     print(f"✅ Receipt printed successfully → {printer_name} (Currency: {actual_currency})")
#                     if fiscal_enabled and not fiscal_ready:
#                         print(f"   Note: Printed with 'Fiscalization Pending' message")
#             except Exception as e:
#                 print(f"❌ Printer error on {printer_name}: {e}")

#     except Exception as e:
#         print(f"❌ PRINT ERROR: {str(e)}")
#         import traceback
#         traceback.print_exc()
def _print_receipt(sale: dict, items: list, tendered: float, change: float,
                   currency: str, kot: str, method: str, cashier_name: str,
                   customer_name: str, customer_contact: str, footer_text: str):
    """Internal function to print receipt with fiscalization wait (up to 3 seconds)."""
    import time
    import threading

    active_printers = _get_active_printers()
    if not active_printers or not sale:
        print("⚠️ No active printers configured")
        return

    # Pull receipt header + footer from company_defaults so the printed slip
    # picks up whatever the user saved in Maintenance → Company Defaults
    # instead of a hardcoded heading/footer.
    try:
        from models.company_defaults import get_defaults
        _co = get_defaults() or {}
    except Exception:
        _co = {}
    receipt_header = (_co.get("receipt_header") or "").strip()

    footer = sale.get("footer_text") or footer_text or _co.get("footer_text") or "Thank you for your purchase!"
    total  = sale["total"]
    paid   = sale["tendered"]
    outstanding = total - paid

    # Only annotate footer for credit/partial cases — change is already
    # printed after Grand Total by printing_service, so no "FULLY PAID" line.
    if sale.get("is_on_account", False) and paid == 0:
        footer = f"CREDIT SALE - Total Due: {total:.2f}\n{footer}"
    elif 0 < paid < total:
        footer = f"PARTIAL PAYMENT - Paid: {paid:.2f} | Balance: {outstanding:.2f}\n{footer}"

    # Check if fiscalization is enabled
    try:
        from services.fiscalization_service import get_fiscalization_service
        fiscal_service = get_fiscalization_service()
        fiscal_enabled = fiscal_service.is_fiscalization_enabled() if fiscal_service else False
    except Exception as e:
        print(f"[Fiscalization] Error checking fiscal status: {e}")
        fiscal_enabled = False

    # Get current fiscal data
    fiscal_qr_code = sale.get("fiscal_qr_code", "")
    fiscal_v_code  = sale.get("fiscal_verification_code", "")
    fiscal_ready   = bool(fiscal_qr_code and fiscal_qr_code.strip())

    # If fiscalization is enabled but QR not ready yet, wait up to 3 seconds
    if fiscal_enabled and not fiscal_ready:
        print(f"⏳ Waiting for fiscalization for sale {sale.get('id')}...")
        wait_start   = time.time()
        wait_seconds = 6

        while time.time() - wait_start < wait_seconds:
            try:
                from models.sale import get_sale_by_id
                refreshed_sale = get_sale_by_id(sale.get("id"))
                if refreshed_sale:
                    fiscal_qr_code = refreshed_sale.get("fiscal_qr_code", "")
                    fiscal_v_code  = refreshed_sale.get("fiscal_verification_code", "")
                    if fiscal_qr_code and fiscal_qr_code.strip():
                        fiscal_ready = True
                        print(f"✅ Fiscalization ready after {time.time() - wait_start:.1f} seconds")
                        sale.update(refreshed_sale)
                        break
            except Exception as e:
                print(f"⚠️ Error checking fiscal status: {e}")

            time.sleep(0.3)

        if not fiscal_ready:
            print(f"⚠️ Fiscalization not ready after {wait_seconds}s, printing with pending message")
    else:
        fiscal_ready = bool(fiscal_qr_code and fiscal_qr_code.strip())

    # Tendered + change are ALWAYS shown in the business's base currency (USD
    # per company_defaults default) so the cashier doesn't have to mental-math
    # multi-currency splits. Priority for tendered:
    #   1. Sum of sale["splits"][i].base_value  — definitive multi-method total
    #   2. sale.tendered_usd                    — stored on the sales row
    #   3. tendered arg (single-method fallback)
    _total_usd    = float(sale.get("total_usd") or 0) or float(total or 0)
    _splits       = sale.get("splits") or []
    _splits_usd   = sum(float(s.get("base_value") or 0) for s in _splits)
    if _splits_usd > 0:
        _tendered_usd = round(_splits_usd, 4)
    else:
        _tendered_usd = float(sale.get("tendered_usd") or 0) or float(tendered or 0)
    _change_usd = round(max(_tendered_usd - _total_usd, 0.0), 4)

    try:
        receipt = ReceiptData(
            invoiceNo=sale["invoice_no"],
            invoiceDate=sale["invoice_date"],
            companyName=sale.get("company_name", ""),
            companyAddress=sale.get("address_1", ""),
            companyAddressLine1=sale.get("address_2", ""),
            companyAddressLine2="",
            city="",
            state="",
            postcode="",
            companyEmail=sale.get("email", ""),
            tel=sale.get("phone", ""),
            tin=sale.get("tin_number", ""),
            vatNo=sale.get("vat_number", ""),
            deviceSerial=sale.get("zimra_serial_no", ""),
            deviceId=sale.get("zimra_device_id", ""),
            cashierName=sale.get("cashier_name", cashier_name),
            customerName=sale.get("customer_name", customer_name),
            customerContact=sale.get("customer_contact", customer_contact),
            customerTin="",
            customerVat="",
            amountTendered=_tendered_usd,
            change=_change_usd,
            grandTotal=total,
            subtotal=float(sale.get("subtotal", total)),
            totalVat=float(sale.get("total_vat", 0)),
            currency=currency,
            receiptHeader=receipt_header,
            footer=footer,
            KOT=kot or "",
            paymentMode=method,
            orderNumber=int(sale.get("order_number", 0) or 0),
        )

        # Payment Details breakdown — one row per split (method + currency).
        # Non-split sales get a single synthetic split so the block still renders.
        _splits = sale.get("splits") or []
        if not _splits:
            _splits = [{
                "method":          method or sale.get("method", "CASH"),
                "base_value":      _total_usd,
                "native_amount":   float(tendered or _total_usd),
                "native_currency": (currency or "USD").upper(),
                "is_credit":       bool(sale.get("is_on_account", False)),
            }]
        try:
            from models.receipt import Item as _RItem
            receipt.paymentItems = [
                _RItem(
                    productName = str(s.get("method", "CASH")),
                    productid   = (s.get("native_currency") or "USD").upper(),
                    qty         = 1,
                    price       = float(s.get("native_amount") or s.get("base_value") or 0),
                    amount      = float(s.get("base_value") or 0),   # USD-basis
                    tax_amount  = 0.0,
                )
                for s in _splits
            ]
        except Exception as _pe:
            print(f"[_print_receipt] could not build paymentItems: {_pe}")

        # Add fiscal QR code if available
        if fiscal_qr_code and fiscal_qr_code.strip():
            receipt.qrCode = fiscal_qr_code
            receipt.vCode  = fiscal_v_code
        elif fiscal_enabled:
            receipt.qrCode        = ""
            receipt.vCode         = ""
            receipt.fiscal_pending = True

        for it in sale.get("items", []):
            receipt.items.append(Item(
                productName=it["product_name"],
                productid=it.get("part_no", ""),
                qty=float(it["qty"]),
                price=float(it["price"]),
                amount=float(it["total"]),
                tax_amount=float(it.get("tax_amount", 0))
            ))

        for printer_name in active_printers:
            try:
                success = printing_service.print_receipt(receipt, printer_name=printer_name)
                if success:
                    print(f"✅ Receipt printed successfully → {printer_name}")
                    if fiscal_enabled and not fiscal_ready:
                        print(f"   Note: Printed with 'Fiscalization Pending' message")
            except Exception as e:
                print(f"❌ Printer error on {printer_name}: {e}")

    except Exception as e:
        print(f"❌ PRINT ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
def update_tendered_amount(sale_id: int, additional_payment: float) -> bool:
    """
    Update the tendered amount on an existing invoice.
    Called by payment_entry_service when a payment is recorded.
    """
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("SELECT total, tendered, is_on_account FROM sales WHERE id = ?", (sale_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Sale ID {sale_id} not found")

    total             = float(row[0])
    current_tendered  = float(row[1])
    is_on_account     = bool(row[2])
    new_tendered      = current_tendered + additional_payment

    if new_tendered > total:
        conn.close()
        raise ValueError(
            f"Cannot add payment of {additional_payment}. "
            f"Current paid: {current_tendered}, Total: {total}, "
            f"Maximum additional: {total - current_tendered}"
        )

    cur.execute(
        "UPDATE sales SET tendered = tendered + ? WHERE id = ?",
        (additional_payment, sale_id)
    )
    affected = cur.rowcount
    conn.commit()
    conn.close()

    if is_on_account and new_tendered >= total:
        print(f"[INFO] Credit sale {sale_id} is now fully paid")

    return affected > 0


def update_sale_shift(sale_id: int, shift_id: int) -> bool:
    """Update a sale to associate it with a shift."""
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("UPDATE sales SET shift_id = ? WHERE id = ?", (shift_id, sale_id))
    affected = cur.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def mark_synced(sale_id: int) -> bool:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("UPDATE sales SET synced = 1 WHERE id = ?", (sale_id,))
    affected = cur.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def mark_synced_with_ref(sale_id: int, frappe_ref: str = "") -> bool:
    conn = get_connection()
    cur  = conn.cursor()
    # Clear syncing at the same time as setting synced=1 so the row is never
    # left in a half-finished state if the caller forgets to unlock.
    cur.execute(
        "UPDATE sales SET synced = 1, syncing = 0, frappe_ref = ? WHERE id = ?",
        (frappe_ref or None, sale_id)
    )
    affected = cur.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def try_lock_sale(sale_id: int) -> bool:
    """
    Atomically attempt to lock a sale for syncing. 
    Returns True only if we successfully set syncing=1 and it was previously 0/NULL.
    """
    conn = get_connection()
    cur  = conn.cursor()
    # Atomic UPDATE with condition is the standard way to handle locks in SQL
    cur.execute(
        "UPDATE sales SET syncing = 1 WHERE id = ? AND (syncing = 0 OR syncing IS NULL) AND synced = 0", 
        (sale_id,)
    )
    affected = cur.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def clear_stale_locks() -> int:
    """Reset the syncing flag for any sales that got stuck (e.g. app crash)."""
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("UPDATE sales SET syncing = 0 WHERE syncing = 1 AND synced = 0")
    affected = cur.rowcount
    conn.commit()
    conn.close()
    return affected


def mark_many_synced(sale_ids: list[int]) -> int:
    if not sale_ids:
        return 0
    conn = get_connection()
    cur  = conn.cursor()
    placeholders = ", ".join("?" * len(sale_ids))
    cur.execute(f"UPDATE sales SET synced = 1 WHERE id IN ({placeholders})", sale_ids)
    affected = cur.rowcount
    conn.commit()
    conn.close()
    return affected


def delete_sale(sale_id: int) -> bool:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("DELETE FROM sales WHERE id = ?", (sale_id,))
    affected = cur.rowcount
    conn.commit()
    conn.close()
    return affected > 0


# =============================================================================
# MIGRATION
# =============================================================================

def migrate():
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'sales'
        )
        CREATE TABLE sales (
            id               INT           IDENTITY(1,1) PRIMARY KEY,
            invoice_number   INT           NOT NULL DEFAULT 0,
            invoice_no       NVARCHAR(40)  NOT NULL DEFAULT '',
            invoice_date     NVARCHAR(20)  NOT NULL DEFAULT '',
            total            DECIMAL(12,2) NOT NULL DEFAULT 0,
            tendered         DECIMAL(12,2) NOT NULL DEFAULT 0,
            method           NVARCHAR(30)  NOT NULL DEFAULT 'Cash',
            cashier_id       INT           NULL,
            cashier_name     NVARCHAR(120) NOT NULL DEFAULT '',
            customer_name    NVARCHAR(120) NOT NULL DEFAULT '',
            customer_contact NVARCHAR(80)  NOT NULL DEFAULT '',
            company_name     NVARCHAR(120) NOT NULL DEFAULT '',
            kot              NVARCHAR(40)  NOT NULL DEFAULT '',
            currency         NVARCHAR(10)  NOT NULL DEFAULT '',
            subtotal         DECIMAL(12,2) NOT NULL DEFAULT 0,
            total_vat        DECIMAL(12,2) NOT NULL DEFAULT 0,
            discount_amount  DECIMAL(12,2) NOT NULL DEFAULT 0,
            receipt_type     NVARCHAR(30)  NOT NULL DEFAULT 'Invoice',
            footer           NVARCHAR(MAX) NOT NULL DEFAULT '',
            created_at       DATETIME2     NOT NULL DEFAULT SYSDATETIME(),
            total_items      DECIMAL(12,4) NOT NULL DEFAULT 0,
            change_amount    DECIMAL(12,2) NOT NULL DEFAULT 0,
            synced           BIT           NOT NULL DEFAULT 0,
            frappe_ref       NVARCHAR(80)  NULL
        )
    """)

    for col, definition in [
        ("total_items",                "DECIMAL(12,4) NOT NULL DEFAULT 0"),
        ("change_amount",              "DECIMAL(12,2) NOT NULL DEFAULT 0"),
        ("synced",                     "BIT           NOT NULL DEFAULT 0"),
        ("company_name",               "NVARCHAR(120) NOT NULL DEFAULT ''"),
        ("frappe_ref",                 "NVARCHAR(80)  NULL"),
        ("is_on_account",              "BIT           NOT NULL DEFAULT 0"),
        ("shift_id",                   "INT           NULL"),
        ("fiscal_status",              "NVARCHAR(20)  DEFAULT 'pending'"),
        ("fiscal_qr_code",             "NVARCHAR(500) NULL"),
        ("fiscal_verification_code",   "NVARCHAR(100) NULL"),
        ("fiscal_receipt_counter",     "INT NULL"),
        ("fiscal_global_no",           "NVARCHAR(50)  NULL"),
        ("fiscal_sync_date",           "DATETIME2     NULL"),
        ("fiscal_error",               "NVARCHAR(MAX) NULL"),
        # syncing flag — set to 1 while a background thread is pushing this
        # sale to Frappe; cleared to 0 when push succeeds or fails.
        # Prevents two threads from posting the same invoice simultaneously.
        ("syncing",                    "BIT           NOT NULL DEFAULT 0"),
    ]:
        cur.execute(f"""
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = 'sales' AND COLUMN_NAME = '{col}'
            )
            ALTER TABLE sales ADD {col} {definition}
        """)

    cur.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'sale_items'
        )
        CREATE TABLE sale_items (
            id           INT           IDENTITY(1,1) PRIMARY KEY,
            sale_id      INT           NOT NULL
                                       REFERENCES sales(id) ON DELETE CASCADE,
            part_no      NVARCHAR(50)  NOT NULL DEFAULT '',
            product_name NVARCHAR(120) NOT NULL DEFAULT '',
            qty          DECIMAL(12,4) NOT NULL DEFAULT 1,
            price        DECIMAL(12,2) NOT NULL DEFAULT 0,
            discount     DECIMAL(12,2) NOT NULL DEFAULT 0,
            tax          NVARCHAR(20)  NOT NULL DEFAULT '',
            total        DECIMAL(12,2) NOT NULL DEFAULT 0,
            tax_type     NVARCHAR(20)  NOT NULL DEFAULT '',
            tax_rate     DECIMAL(8,4)  NOT NULL DEFAULT 0,
            tax_amount   DECIMAL(12,2) NOT NULL DEFAULT 0,
            remarks      NVARCHAR(MAX) NOT NULL DEFAULT '',
            order_1      BIT           NOT NULL DEFAULT 0,
            order_2      BIT           NOT NULL DEFAULT 0,
            order_3      BIT           NOT NULL DEFAULT 0,
            order_4      BIT           NOT NULL DEFAULT 0,
            order_5      BIT           NOT NULL DEFAULT 0,
            order_6      BIT           NOT NULL DEFAULT 0,
            uom          NVARCHAR(20)  NULL
        )
    """)

    for col, definition in [
        ("discount",   "DECIMAL(12,2) NOT NULL DEFAULT 0"),
        ("tax",        "NVARCHAR(20)  NOT NULL DEFAULT ''"),
        ("tax_type",   "NVARCHAR(20)  NOT NULL DEFAULT ''"),
        ("tax_rate",   "DECIMAL(8,4)  NOT NULL DEFAULT 0"),
        ("tax_amount", "DECIMAL(12,2) NOT NULL DEFAULT 0"),
        ("remarks",    "NVARCHAR(MAX) NOT NULL DEFAULT ''"),
        ("order_1",    "BIT           NOT NULL DEFAULT 0"),
        ("order_2",    "BIT           NOT NULL DEFAULT 0"),
        ("order_3",    "BIT           NOT NULL DEFAULT 0"),
        ("order_4",    "BIT           NOT NULL DEFAULT 0"),
        ("order_5",    "BIT           NOT NULL DEFAULT 0"),
        ("order_6",    "BIT           NOT NULL DEFAULT 0"),
        ("uom",        "NVARCHAR(20)  NULL"),
    ]:
        cur.execute(f"""
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = 'sale_items' AND COLUMN_NAME = '{col}'
            )
            ALTER TABLE sale_items ADD {col} {definition}
        """)

    cur.execute("""
        UPDATE sales
        SET is_on_account = 1
        WHERE tendered = 0 AND (is_on_account = 0 OR is_on_account IS NULL)
    """)
    fixed_count = cur.rowcount
    if fixed_count > 0:
        print(f"[MIGRATION] Fixed {fixed_count} inconsistent sale(s)")

    conn.commit()
    conn.close()
    print("[sale] ✅ Tables and columns verified.")


# =============================================================================
# PRIVATE HELPERS
# =============================================================================

def _fetch_items(sale_id: int, cur) -> list[dict]:
    # Pharmacy columns + uom are selected defensively — the SELECT will fail
    # if the migration hasn't run yet, so we fall back to the legacy column set.
    try:
        cur.execute("""
            SELECT id, sale_id, part_no, product_name, qty, price,
                   discount, tax, total,
                   tax_type, tax_rate, tax_amount, remarks,
                   order_1, order_2, order_3, order_4, order_5, order_6,
                   is_pharmacy, dosage, batch_no, expiry_date,
                   COALESCE(uom, '') AS uom
            FROM sale_items
            WHERE sale_id = ?
            ORDER BY id
        """, (sale_id,))
        return [_item_to_dict(r) for r in fetchall_dicts(cur)]
    except Exception:
        cur.execute("""
            SELECT id, sale_id, part_no, product_name, qty, price,
                   discount, tax, total,
                   tax_type, tax_rate, tax_amount, remarks,
                   order_1, order_2, order_3, order_4, order_5, order_6
            FROM sale_items
            WHERE sale_id = ?
            ORDER BY id
        """, (sale_id,))
        return [_item_to_dict(r) for r in fetchall_dicts(cur)]


def _item_to_dict(row: dict) -> dict:
    expiry = row.get("expiry_date")
    expiry_str = expiry.isoformat() if hasattr(expiry, "isoformat") else (str(expiry) if expiry else None)
    return {
        "id":           row["id"],
        "sale_id":      row["sale_id"],
        "part_no":      row.get("part_no",      "") or "",
        "product_name": row.get("product_name", "") or "",
        "qty":          float(row.get("qty",    0)),
        "price":        float(row.get("price",  0)),
        "discount":     float(row.get("discount", 0)),
        "tax":          row.get("tax",      "") or "",
        "total":        float(row.get("total",  0)),
        "tax_type":     row.get("tax_type", "") or "",
        "tax_rate":     float(row.get("tax_rate",   0) or 0),
        "tax_amount":   float(row.get("tax_amount", 0) or 0),
        "remarks":      row.get("remarks",  "") or "",
        "order_1":      bool(row.get("order_1", False)),
        "order_2":      bool(row.get("order_2", False)),
        "order_3":      bool(row.get("order_3", False)),
        "order_4":      bool(row.get("order_4", False)),
        "order_5":      bool(row.get("order_5", False)),
        "order_6":      bool(row.get("order_6", False)),
        # ── Pharmacy-specific fields (safe default if columns absent) ────
        "is_pharmacy":  bool(row.get("is_pharmacy", False)),
        "dosage":       row.get("dosage"),
        "batch_no":     row.get("batch_no"),
        "expiry_date":  expiry_str,
        # UOM from cart (empty string when column is NULL or missing)
        "uom":          row.get("uom") or "",
    }


def _sale_to_dict(row: dict) -> dict:
    from datetime import datetime
    raw_dt = row.get("created_at")
    if isinstance(raw_dt, str):
        try:
            dt = datetime.fromisoformat(raw_dt)
        except Exception:
            dt = None
    elif hasattr(raw_dt, "strftime"):
        dt = raw_dt
    else:
        dt = None

    return {
        "id":               row["id"],
        "number":           row["invoice_number"],
        "date":             f"{dt.month}/{dt.day}/{dt.year}" if dt else "",
        "time":             dt.strftime("%H:%M")             if dt else "",
        "cashier_id":       row["cashier_id"],
        "user":             row["username"] or str(row["cashier_id"] or ""),
        "total":            float(row["total"]),
        "tendered":         float(row["tendered"]),
        "method":           row["method"]           or "Cash",
        "amount":           float(row["total"]),
        "invoice_no":       row["invoice_no"]       or "",
        "invoice_date":     row["invoice_date"]     or "",
        "kot":              row["kot"]              or "",
        "customer_name":    row["customer_name"]    or "",
        "customer_contact": row["customer_contact"] or "",
        "company_name":     row.get("company_name", ""),
        "currency":         row["currency"]         or "",
        "subtotal":         float(row["subtotal"]        or 0),
        "total_vat":        float(row["total_vat"]       or 0),
        "discount_amount":  float(row["discount_amount"] or 0),
        "receipt_type":     row["receipt_type"]     or "Invoice",
        "footer":           row["footer"]           or "",
        "cashier_name":     row["cashier_name"]     or "",
        "synced":           bool(row.get("synced", False)),
        "frappe_ref":       row.get("frappe_ref")   or "",
        "total_items":      float(row.get("total_items",   0) or 0),
        "change_amount":    float(row.get("change_amount",  0) or 0),
        "is_on_account":    bool(row.get("is_on_account",  0)),
        "shift_id":         row.get("shift_id"),
        "fiscal_status":    row.get("fiscal_status", "pending"),
        "fiscal_qr_code":   row.get("fiscal_qr_code") or "",
        "fiscal_verification_code": row.get("fiscal_verification_code") or "",
        "fiscal_receipt_counter":   row.get("fiscal_receipt_counter"),
        "fiscal_global_no": row.get("fiscal_global_no") or "",
        "fiscal_sync_date": row.get("fiscal_sync_date"),
        "fiscal_error":     row.get("fiscal_error") or "",
        "address_1":        row.get("address_1",        ""),
        "address_2":        row.get("address_2",        ""),
        "phone":            row.get("phone",            ""),
        "email":            row.get("email",            ""),
        "vat_number":       row.get("vat_number",       ""),
        "tin_number":       row.get("tin_number",       ""),
        "zimra_serial_no":  row.get("zimra_serial_no",  ""),
        "zimra_device_id":  row.get("zimra_device_id",  ""),
        "footer_text":      row.get("footer_text",      ""),
        # ── Multi-currency fields ──────────────────────────────────────────
        # These are the source of truth for Frappe syncing:
        #   total_usd    → what the Sales Invoice and Payment Entry use in Frappe
        #   total_zwd    → the ZWD amount (populated only for ZWD sales)
        #   tendered_usd → USD cash given (receipt/change display only)
        #   tendered_zwd → ZWD cash given (receipt/change display only)
        #   exchange_rate→ rate at time of sale (e.g. ZWD→USD = 0.00277)
        "total_usd":     float(row.get("total_usd",    0) or 0),
        "total_zwd":     float(row.get("total_zwd",    0) or 0),
        "tendered_usd":  float(row.get("tendered_usd", 0) or 0),
        "tendered_zwd":  float(row.get("tendered_zwd", 0) or 0),
        "exchange_rate": float(row.get("exchange_rate", 1) or 1),
        "order_number":  int(row.get("order_number",   0) or 0),
    }


# =============================================================================
# ACTIVE PRINTERS
# =============================================================================

def _get_active_printers() -> list[str]:
    hw_file = Path("app_data/hardware_settings.json")
    try:
        with open(hw_file, "r", encoding="utf-8") as f:
            hw = json.load(f)
        printers = []
        if hw.get("main_printer") and hw["main_printer"] != "(None)":
            printers.append(hw["main_printer"])
        return list(dict.fromkeys(printers))
    except Exception:
        return []


# =============================================================================
# KITCHEN ORDER PRINTING
# =============================================================================

def print_kitchen_orders(sale: dict):
    """Print separate KOT for every active Order 1–6 station.
    Gated on hardware_settings.kitchen_printing_enabled — when off this is a
    no-op so non-restaurant tills don't spam empty KOTs."""
    try:
        hw_file = Path("app_data/hardware_settings.json")
        with open(hw_file, "r", encoding="utf-8") as f:
            hw = json.load(f)

        if not bool(hw.get("kitchen_printing_enabled", False)):
            return

        orders_config = hw.get("orders", {})

        for order_key in ["Order 1", "Order 2", "Order 3", "Order 4", "Order 5", "Order 6"]:
            config = orders_config.get(order_key, {})
            if not config.get("active", False):
                continue

            printer_name = config.get("printer")
            if not printer_name or printer_name == "(None)":
                continue

            order_field = order_key.lower().replace(" ", "_")
            order_items = [it for it in sale.get("items", []) if it.get(order_field)]

            if not order_items:
                continue

            kot_receipt = ReceiptData(
                invoiceNo=sale["invoice_no"],
                KOT=order_key,
                cashierName=sale.get("cashier_name", ""),
                orderNumber=int(sale.get("order_number", 0) or 0),
                items=[Item(
                    productName=it["product_name"],
                    qty=float(it["qty"]),
                    productid=it.get("part_no", "")
                ) for it in order_items]
            )

            success = printing_service.print_kitchen_order(kot_receipt, printer_name=printer_name)
            if success:
                print(f"✅ KOT printed for {order_key} → {printer_name}")
            else:
                print(f"⚠️ KOT failed for {order_key}")

    except Exception as e:
        print(f"❌ Kitchen Order printing error: {e}")



# =============================================================================
# TRANSACTION HASH HELPERS
# =============================================================================

def check_recent_transaction_by_hash(transaction_hash: str, seconds: int = 10) -> bool:
    """Check if a transaction with this hash was processed recently."""
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_NAME = 'transaction_hashes'
            )
            CREATE TABLE transaction_hashes (
                id               INT IDENTITY(1,1) PRIMARY KEY,
                transaction_hash NVARCHAR(64) NOT NULL UNIQUE,
                sale_id          INT NULL,
                created_at       DATETIME2 NOT NULL DEFAULT SYSDATETIME()
            )
        """)
        conn.commit()

        cur.execute("""
            SELECT COUNT(*) FROM transaction_hashes
            WHERE transaction_hash = ?
            AND created_at > DATEADD(SECOND, -?, SYSDATETIME())
        """, (transaction_hash, seconds))

        return cur.fetchone()[0] > 0
    except Exception as e:
        print(f"[ERROR] check_recent_transaction_by_hash: {e}")
        return False
    finally:
        conn.close()


def record_transaction_hash(transaction_hash: str, sale_id: int):
    """Record a transaction hash with its sale ID."""
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_NAME = 'transaction_hashes'
            )
            CREATE TABLE transaction_hashes (
                id               INT IDENTITY(1,1) PRIMARY KEY,
                transaction_hash NVARCHAR(64) NOT NULL UNIQUE,
                sale_id          INT NULL,
                created_at       DATETIME2 NOT NULL DEFAULT SYSDATETIME()
            )
        """)
        conn.commit()

        cur.execute("""
            MERGE transaction_hashes AS target
            USING (SELECT ? AS hash, ? AS sid) AS source
            ON target.transaction_hash = source.hash
            WHEN MATCHED THEN
                UPDATE SET sale_id = source.sid, created_at = SYSDATETIME()
            WHEN NOT MATCHED THEN
                INSERT (transaction_hash, sale_id, created_at)
                VALUES (source.hash, source.sid, SYSDATETIME());
        """, (transaction_hash, sale_id))
        conn.commit()

        # Clean up records older than 24 hours
        cur.execute("""
            DELETE FROM transaction_hashes
            WHERE created_at < DATEADD(HOUR, -24, SYSDATETIME())
        """)
        conn.commit()

    except Exception as e:
        print(f"[ERROR] record_transaction_hash: {e}")
    finally:
        conn.close()


# =============================================================================
# DEBUGGING
# =============================================================================

def print_duplicate_transactions():
    """Find transactions that created multiple invoices for the same cart."""
    conn = get_connection()
    cur  = conn.cursor()

    print("\n" + "=" * 80)
    print("🔍 FINDING DUPLICATE TRANSACTIONS")
    print("=" * 80)

    cur.execute("""
        SELECT
            s1.id as id1, s1.invoice_no as invoice1, s1.created_at as time1,
            s2.id as id2, s2.invoice_no as invoice2, s2.created_at as time2,
            s1.total, s1.cashier_name,
            DATEDIFF(SECOND, s1.created_at, s2.created_at) as seconds_apart
        FROM sales s1
        INNER JOIN sales s2
            ON s1.id < s2.id
            AND ABS(s1.total - s2.total) < 0.01
            AND s1.cashier_name = s2.cashier_name
            AND DATEDIFF(SECOND, s1.created_at, s2.created_at) BETWEEN 0 AND 10
        ORDER BY s1.created_at DESC
    """)

    duplicates = cur.fetchall()
    if not duplicates:
        print("\n✅ No duplicate transactions found!")
    else:
        print(f"\n⚠️ FOUND {len(duplicates)} POTENTIAL DUPLICATE TRANSACTIONS:\n")
        for dup in duplicates:
            print(f"{'─' * 80}")
            print(f"Transaction 1: ID={dup[0]}, Invoice={dup[1]}, Time={dup[2]}")
            print(f"Transaction 2: ID={dup[3]}, Invoice={dup[4]}, Time={dup[5]}")
            print(f"Total Amount: {float(dup[6]):.2f}  Cashier: {dup[7]}  Seconds apart: {dup[8]}")

    print("=" * 80 + "\n")
    conn.close()


def debug_duplicate_invoices():
    """Quick debug function to identify duplicate transactions."""
    print("\n" + "🔍" * 40)
    print("DEBUGGING DUPLICATE INVOICE CREATION")
    print("🔍" * 40)
    print_duplicate_transactions()
    print("\n💡 TIPS:")
    print("   1. Check if your frontend is submitting the form twice")
    print("   2. Check if button click handlers are firing twice")
    print("   3. Pass idempotency_key= to create_sale() to prevent duplicates automatically")