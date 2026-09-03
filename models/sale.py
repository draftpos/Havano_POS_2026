from database.db import get_connection, fetchall_dicts, fetchone_dict
from models.product import adjust_stock, get_product_by_id
from models.receipt import ReceiptData, Item, MultiCurrencyDetail
from services.printing_service import PrintingService

from datetime import date
import json
from pathlib import Path
import threading
import time

# =============================================================================
# INVOICE NUMBER  -  uses prefix + start_number from company_defaults
#
# Examples:
#   prefix="INV",  start=1   ->  INV-000001
#   prefix="HV",   start=100 ->  HV-000100
#   prefix="",     start=1   ->  000001
# =============================================================================

def _get_invoice_settings() -> tuple[str, int]:
    """Returns (prefix, start_number) from company_defaults."""
    try:
        from models.company_defaults import get_defaults
        d = get_defaults()
        prefix = str(d.get("invoice_prefix") or "").strip().upper()
        
        start_str = str(d.get("invoice_start_number") or "0").strip()
        if not start_str:
            start_str = "0"
            
        try:
            start = int(start_str)
        except ValueError:
            start = 0
            
        return prefix, start
    except Exception:
        return "", 0


def _clamp_num(val, max_val=99999999.99, min_val=-99999999.99):
    try:
        if val is None: return 0.0
        f = float(val)
        if f > max_val: return max_val
        if f < min_val: return min_val
        return round(f, 4)
    except Exception:
        return 0.0


def _format_invoice_no(seq: int) -> str:
    """
    Format invoice number and ensure it hasn't been used before.
    """
    prefix, _ = _get_invoice_settings()

    if prefix:
        clean_prefix = prefix.replace("-", "").replace("_", "").upper()
        candidate = f"{clean_prefix}-{seq:04d}"  # Updated to 4 digits as requested
    else:
        candidate = f"{seq:04d}"

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
       s.discount_amount, s.discount_percent, s.receipt_type, s.footer,
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
       -- exchange_rate: rate at time of sale (foreign -> USD)
       COALESCE(s.total_usd,     0)    AS total_usd,
       COALESCE(s.total_zwd,     0)    AS total_zwd,
       COALESCE(s.tendered_usd,  0)    AS tendered_usd,
       COALESCE(s.tendered_zwd,  0)    AS tendered_zwd,
       COALESCE(s.exchange_rate, 1)    AS exchange_rate,
       s.waiter_name,
       COALESCE(s.order_number,  0)    AS order_number,
       s.warehouse_id,
       s.cost_center_id,
       s.cashier_cloud_user_id,
       s.pos_profile,
       s.terminal_id,
       s.store,
       s.payment_method,
       s.payment_splits,
       s.payments,

       COALESCE(C.company_name,  '')  AS company_name,
       COALESCE(C.address_1,     '')  AS address_1,
       COALESCE(C.address_2,     '')  AS address_2,
       COALESCE(C.vat_number,    '')  AS vat_number,
       C.tin_number,
       C.footer_text,
       C.phone,
       C.email,
       C.zimra_serial_no,
       C.zimra_device_id,
       (SELECT COALESCE(SUM(qty * cost_price), 0) FROM sale_items WHERE sale_id = s.id) AS total_cost
FROM sales s
LEFT JOIN users u ON u.id = s.cashier_id
LEFT JOIN company_defaults C ON 1=1
"""


def get_all_sales(date_from=None, date_to=None) -> list[dict]:
    conn = get_connection()
    cur  = conn.cursor()
    query = _SALE_SELECT
    params = []
    if date_from and date_to:
        query += " WHERE s.created_at BETWEEN ? AND ?"
        params = [date_from, date_to]
    cur.execute(query + " ORDER BY s.id DESC", tuple(params))
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
    # Exclude rows where syncing=1 - those are mid-push in another thread.
    # 1. If fiscalization is NOT required or already completed ('not_required', 'fiscalized'), push immediately (0s).
    # 2. If fiscalization is ON and pending, wait up to 120s (2 minutes) for fiscalization to complete before pushing fallback.
    cur.execute(_SALE_SELECT + """ 
        WHERE s.synced = 0 
          AND (s.syncing IS NULL OR s.syncing = 0) 
          AND (
              s.fiscal_status IS NULL 
              OR s.fiscal_status IN ('fiscalized', 'not_required')
              OR DATEDIFF(SECOND, s.created_at, SYSDATETIME()) >= 120
          ) 
        ORDER BY s.id
    """)
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
    splits:            list | None = None,
    waiter_name:       str   = "",
    warehouse_id:      int   = None,
    cost_center_id:    int   = None,
    exchange_rate:     float = None,
    total_usd:         float = None,
    pos_profile:       str = None,
    terminal_id:       int | str | None = None,
    store:             str = None,
    payment_method:    str = None,
) -> dict:

    """
    Creates a single invoice and triggers fiscalization in background.

    idempotency_key and transaction_id both serve the same purpose - preventing
    duplicate sales. If idempotency_key is supplied it is used as the
    transaction_id so a single duplicate-detection path handles both.
    """
    from datetime import date, datetime
    from models.product import get_product_by_id, adjust_stock

    transaction_id = transaction_id or idempotency_key

    print(f"\n{'=' * 40}")
    print(f"CREATE_SALE CALLED at {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
    print(f"Transaction ID: {transaction_id}")
    print(f"Total: {total}, Items: {len(items)}")
    print(f"{'=' * 40}\n")

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
                print(f"[!] DUPLICATE DETECTED! transaction_id={transaction_id} "
                      f"already processed at {created_at}. "
                      f"Returning existing sale ID: {sale_id}")
                conn.close()
                return get_sale_by_id(sale_id)

            conn.close()
        except Exception as e:
            print(f"[WARNING] Transaction tracking error: {e}")

    tendered_amount = float(tendered) if tendered else 0.0
    total_amount    = float(total)

    # [OK] NO FALLBACK: Use provided waiter_name or empty string
    if not (waiter_name or "").strip():
        waiter_name = ""
    
    if not (company_name or "").strip():
        try:
            from models.company_defaults import get_defaults
            d = get_defaults() or {}
            company_name = str(d.get("server_warehouse") or d.get("warehouse") or d.get("server_company") or d.get("company_name") or "").strip()
        except Exception:
            company_name = ""
    
    print(f"[DEBUG] create_sale: Received waiter_name='{waiter_name}' (type: {type(waiter_name)})")

    currency_upper = (currency or "USD").strip().upper()

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
                    inv = get_rate("USD", currency_upper)
                    if inv and float(inv) > 0:
                        _exch = 1.0 / float(inv)
            except Exception as _e:
                print(f"[create_sale] WARNING: Could not get exchange rate for {currency_upper}->USD: {_e}")

    if total_usd is not None:
        _total_usd = float(total_usd)
    else:
        _total_usd = total_amount

    if currency_upper in ("ZWD", "ZWG") and _exch > 0:
        _total_zwd = round(total_amount / _exch, 4)
    else:
        _total_zwd = 0.0

    if currency_upper == "USD":
        _tendered_usd = tendered_amount
        _tendered_zwd = 0.0
    elif currency_upper in ("ZWD", "ZWG", "ZIG"):
        _tendered_zwd = tendered_amount
        _tendered_usd = round(tendered_amount * _exch, 4) if _exch > 0 else tendered_amount
    else:
        _tendered_usd = round(tendered_amount * _exch, 4) if _exch > 0 else tendered_amount
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
        # Caller (PaymentDialog) already computed change in the correct currency
        change_val = float(change_amount)
    else:
        # Fallback - caller didn't pass change_amount
        # Single USD: plain subtraction
        # Single non-USD: keep change in NATIVE currency
        if currency_upper == "USD":
            change_val = round(max(0.0, tendered_amount - total_amount), 4)
        elif _exch > 0:
            _total_native = round(total_amount / _exch, 4)
            change_val    = round(max(0.0, tendered_amount - _total_native), 4)
        else:
            change_val = 0.0

    # Split payments - update tendered totals to reflect ALL methods combined.
    # Change for splits is ALWAYS stored in USD (no single native currency applies).
    # Only recalculates change when caller did NOT pass change_amount.
    if splits:
        try:
            _splits_usd = sum(float(s.get("base_value") or 0) for s in splits)
            if _splits_usd > 0:
                _tendered_usd = round(_splits_usd, 4)
                _z = sum(
                    float(s.get("native_amount") or 0)
                    for s in splits
                    if (s.get("native_currency") or "").upper() in ("ZWD", "ZWG", "ZIG")
                )
                if _z > 0:
                    _tendered_zwd = round(_z, 4)

                # Split change always in USD - no single native currency to use
                if change_amount is None:
                    change_val = round(max(_splits_usd - _total_usd, 0.0), 4)

            print(f"[create_sale] splits recalc -> tendered_usd={_tendered_usd} "
                  f"tendered_zwd={_tendered_zwd} change_val={change_val}")
        except Exception as _e:
            print(f"[create_sale] splits tendered_usd recalc failed: {_e}")

    effective_sub    = subtotal if subtotal is not None else total
    
    # Clamp all numeric parameters to prevent SQL Server arithmetic overflow error (8115)
    total_amount     = _clamp_num(total_amount)
    tendered_amount  = _clamp_num(tendered_amount)
    effective_sub    = _clamp_num(effective_sub)
    total_vat        = _clamp_num(total_vat)
    discount_amount  = _clamp_num(discount_amount)
    discount_percent = _clamp_num(discount_percent, max_val=100.0, min_val=0.0)
    change_val       = _clamp_num(change_val)
    _total_usd       = _clamp_num(_total_usd)
    _total_zwd       = _clamp_num(_total_zwd)
    _tendered_usd    = _clamp_num(_tendered_usd)
    _tendered_zwd    = _clamp_num(_tendered_zwd)
    _exch            = _clamp_num(_exch if _exch else 1.0)

    seq             = get_next_invoice_number()
    invoice_no      = _format_invoice_no(seq)
    invoice_date    = date.today().isoformat()
    total_items_val = sum(float(it.get("qty", 1)) for it in items)

    print(f"[create_sale] Creating sale with {len(items)} items, total: {total_amount}")
    print(f"[create_sale] Invoice number: {invoice_no}")
    print(f"[create_sale] Transaction ID: {transaction_id}")

    conn = get_connection()
    cur  = conn.cursor()

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

    cashier_cloud_user_id = None
    if cashier_id or cashier_name:
        try:
            cur.execute("""
                SELECT cloud_user_id FROM users
                WHERE id = ? OR username = ? OR email = ?
            """, (cashier_id, cashier_name, cashier_name))
            r_c = cur.fetchone()
            if r_c and r_c[0]:
                cashier_cloud_user_id = int(r_c[0])
        except Exception as _ce:
            print(f"[create_sale] cashier_cloud_user_id lookup error: {_ce}")

    has_fiscal = False
    try:
        cur.execute("""
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'sales' AND COLUMN_NAME = 'fiscal_status'
        """)
        has_fiscal = cur.fetchone()[0] > 0
    except Exception:
        pass

    eff_payment_method = str(payment_method or method or "Cash").strip()
    eff_pos_profile    = str(pos_profile or "").strip() if pos_profile else None
    eff_terminal_id    = str(terminal_id).strip() if terminal_id is not None else None
    eff_store          = str(store or company_name or "").strip() if (store or company_name) else None

    try:
        from models.company_defaults import get_defaults
        co_d = get_defaults() or {}
        if not eff_store:
            eff_store = (co_d.get("server_warehouse") or co_d.get("warehouse") or co_d.get("company_name") or "").strip() or None
        if not eff_pos_profile:
            eff_pos_profile = (co_d.get("server_profile") or co_d.get("server_terminal_name") or co_d.get("pos_profile") or "").strip() or None
        if not eff_terminal_id:
            eff_terminal_id = (co_d.get("server_terminal_id") or co_d.get("server_shop_id") or "").strip() or None
    except Exception as _ex_res:
        print(f"[create_sale] store/profile resolution warning: {_ex_res}")

    if eff_store and not company_name:
        company_name = eff_store



    eff_splits = splits
    splits_json_str = None
    if eff_splits:
        if isinstance(eff_splits, str):
            splits_json_str = eff_splits
        else:
            try:
                splits_json_str = json.dumps(eff_splits)
            except Exception:
                splits_json_str = None

    try:
        if has_fiscal:
            cur.execute("""
                INSERT INTO sales (
                    invoice_number, invoice_no, invoice_date,
                    total, tendered, method, cashier_id,
                    cashier_name, customer_name, customer_contact,
                    company_name, kot, currency,
                    subtotal, total_vat, discount_amount, discount_percent,
                    receipt_type, footer, synced,
                    total_items, change_amount, is_on_account,
                    shift_id, fiscal_status,
                    total_usd, total_zwd, tendered_usd, tendered_zwd, exchange_rate,
                    order_number, waiter_name, warehouse_id, cost_center_id, cashier_cloud_user_id,
                    pos_profile, terminal_id, store, payment_method,
                    payment_splits, payments
                )
                OUTPUT INSERTED.id
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                seq, invoice_no, invoice_date,
                total_amount, tendered_amount, method, cashier_id,
                cashier_name, customer_name, customer_contact,
                company_name, kot, currency,
                float(effective_sub), float(total_vat), float(discount_amount), float(discount_percent),
                receipt_type, footer, 0,
                float(total_items_val), float(change_val), 1 if is_on_account else 0,
                shift_id, "pending",
                _total_usd, _total_zwd, _tendered_usd, _tendered_zwd, _exch,
                order_number, waiter_name, warehouse_id, cost_center_id, cashier_cloud_user_id,
                eff_pos_profile, eff_terminal_id, eff_store, eff_payment_method,
                splits_json_str, splits_json_str,
            ))

        else:
            cur.execute("""
                INSERT INTO sales (
                    invoice_number, invoice_no, invoice_date,
                    total, tendered, method, cashier_id,
                    cashier_name, customer_name, customer_contact,
                    company_name, kot, currency,
                    subtotal, total_vat, discount_amount, discount_percent,
                    receipt_type, footer, synced,
                    total_items, change_amount, is_on_account,
                    shift_id,
                    total_usd, total_zwd, tendered_usd, tendered_zwd, exchange_rate,
                    order_number, waiter_name, warehouse_id, cost_center_id, cashier_cloud_user_id,
                    pos_profile, terminal_id, store, payment_method,
                    payment_splits, payments
                )
                OUTPUT INSERTED.id
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                seq, invoice_no, invoice_date,
                total_amount, tendered_amount, method, cashier_id,
                cashier_name, customer_name, customer_contact,
                company_name, kot, currency,
                float(effective_sub), float(total_vat), float(discount_amount), float(discount_percent),
                receipt_type, footer, 0,
                float(total_items_val), float(change_val), 1 if is_on_account else 0,
                shift_id,
                _total_usd, _total_zwd, _tendered_usd, _tendered_zwd, _exch,
                order_number, waiter_name, warehouse_id, cost_center_id, cashier_cloud_user_id,
                eff_pos_profile, eff_terminal_id, eff_store, eff_payment_method,
                splits_json_str, splits_json_str,
            ))

            print(f"[DEBUG] create_sale: Executed INSERT into sales with waiter_name='{waiter_name}'")

        sale_id = int(cur.fetchone()[0])
        print(f"[create_sale] Created sale ID: {sale_id}")

        # Lookup order station flags from products table by id, part_no, or name
        order_map: dict[str, tuple] = {}
        try:
            cur.execute(
                "SELECT id, part_no, name, order_1, order_2, order_3, order_4, order_5, order_6 "
                "FROM products"
            )
            for row in cur.fetchall():
                pid = str(row[0] or "")
                pno = str(row[1] or "").strip()
                pname = str(row[2] or "").strip().lower()
                flags = tuple(1 if row[i] else 0 for i in range(3, 9))
                if pid: order_map[f"id:{pid}"] = flags
                if pno: order_map[f"pno:{pno}"] = flags
                if pname: order_map[f"name:{pname}"] = flags
        except Exception as _oe:
            print(f"[create_sale] order_N lookup failed: {_oe}")

        item_insert_count = 0
        for idx, item in enumerate(items):
            part_no = str(item.get("part_no", "")).strip()
            if any(item.get(f"order_{i}") for i in range(1, 7)):
                order_flags = tuple(1 if item.get(f"order_{i}") else 0 for i in range(1, 7))
            else:
                pid = str(item.get("product_id") or item.get("id") or "")
                pno = part_no
                pname = str(item.get("product_name") or item.get("name") or "").strip().lower()
                order_flags = (
                    order_map.get(f"id:{pid}") or
                    order_map.get(f"pno:{pno}") or
                    order_map.get(f"name:{pname}") or
                    (0, 0, 0, 0, 0, 0)
                )

            # 🔥🔥🔥 TEST CODE - FORCE ORDER 1 FOR TESTING 🔥🔥🔥
            # Remove this block after testing
            # print(f"[DEBUG] Original order_flags for '{item.get('product_name')}': {order_flags}")
            # order_flags = (1, 0, 0, 0, 0, 0)  # Force ALL items to Order 1
            # print(f"[DEBUG] FORCED order_flags to: {order_flags}")
            # # 🔥🔥🔥 END TEST CODE 🔥🔥5555🔥

            item_cost = float(item.get("cost_price", 0))
            item_uom = item.get("uom")
            if (not item_uom or item_cost == 0) and (part_no or item.get("id") or item.get("product_id")):
                try:
                    pid = item.get("id") or item.get("product_id")
                    cur.execute("SELECT uom, cost_price FROM products WHERE id = ? OR part_no = ?", (pid or -1, part_no or ""))
                    p_row = cur.fetchone()
                    if p_row:
                        if not item_uom and p_row[0]:
                            item_uom = str(p_row[0])
                        if item_cost == 0 and p_row[1]:
                            item_cost = float(p_row[1])
                except Exception:
                    pass

            cur.execute("""
                INSERT INTO sale_items (
                    sale_id, part_no, product_name, qty, price, cost_price,
                    discount, tax, total,
                    tax_type, tax_rate, tax_amount, remarks,
                    is_pharmacy, dosage, batch_no, expiry_date,
                    uom, serial_no, price_list_rate,
                    order_1, order_2, order_3, order_4, order_5, order_6
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sale_id,
                part_no,
                str(item.get("product_name", "")),
                _clamp_num(item.get("qty", 1)),
                _clamp_num(item.get("price", 0)),
                _clamp_num(item_cost),
                _clamp_num(item.get("discount", 0)),
                str(item.get("tax", "")),
                _clamp_num(item.get("total", 0)),
                str(item.get("tax_type", "")),
                _clamp_num(item.get("tax_rate", 0.0)),
                _clamp_num(item.get("tax_amount", 0.0)),
                str(item.get("remarks", "")),
                1 if item.get("is_pharmacy") else 0,
                item.get("dosage"),
                item.get("batch_no"),
                item.get("expiry_date"),
                (str(item_uom) if item_uom else None),
                item.get("serial_no"),
                _clamp_num(item.get("price_list_rate") or item.get("price") or 0.0),
                *order_flags,
            ))
            item_insert_count += 1
            
            # Deduct Stock
            if not skip_stock:
                try:
                    prod_id = item.get("id") or item.get("product_id")
                    p_row = None
                    if prod_id:
                        p_row = get_product_by_id(prod_id)
                    elif part_no:
                        # Fallback: lookup by part_no if ID missing
                        p_row = get_product_by_part_no(part_no)
                        
                    if p_row:
                        prod_id = p_row["id"]
                        if p_row.get("track_stock", True):
                            qty = float(item.get("qty", 1))
                            # Use the specific warehouse for deduction
                            adjust_stock(prod_id, -qty, warehouse_id=warehouse_id)
                        else:
                            print(f"[create_sale] Item {part_no} has track_stock=False, skipping stock adjustment.")
                except Exception as _se:
                    print(f"[create_sale] Stock adjustment failed for item {idx}: {_se}")


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

        if splits:
            sale["splits"] = list(splits)

        _trigger_fiscalization_background(sale_id)

        # ── Auto-Quotation for Cashier Pharmacy Sales ──
        try:
            from database.db import get_connection as _gc
            _c = _gc(); _cur = _c.cursor()
            _cur.execute("""
                IF EXISTS (
                    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = 'company_defaults' AND COLUMN_NAME = 'allow_cashier_pharmacy_sales'
                )
                SELECT allow_cashier_pharmacy_sales FROM company_defaults
                ELSE
                SELECT 0
            """)
            _row = _cur.fetchone()
            _c.close()
            _allow_cashier = (_row and str(_row[0]).strip() == "1")
            
            if _allow_cashier and any(item.get("is_pharmacy") for item in items):
                from models.quotation import Quotation, QuotationItem, save_quotation
                import uuid
                q_items = []
                for it in items:
                    q_items.append(QuotationItem(
                        item_code=it.get("part_no") or "",
                        item_name=it.get("product_name") or "",
                        description="",
                        qty=float(it.get("qty", 1)),
                        rate=float(it.get("price", 0)),
                        amount=float(it.get("total", 0)),
                        uom=it.get("uom") or "Nos",
                        product_id=it.get("product_id") or it.get("id"),
                        part_no=it.get("part_no") or "",
                        is_pharmacy=bool(it.get("is_pharmacy")),
                        dosage=it.get("dosage"),
                        batch_no=it.get("batch_no"),
                        expiry_date=it.get("expiry_date"),
                    ))
                q_name = f"AUTO-{invoice_no}"
                new_q = Quotation(
                    name=q_name,
                    transaction_date=date.today().isoformat(),
                    grand_total=total_amount,
                    docstatus=0, # Draft
                    company=company_name,
                    status="Draft",
                    customer=customer_name or "Walk-in Customer",
                    items=q_items,
                    cashier_name=cashier_name,
                    waiter_name=waiter_name,
                )
                q_id = save_quotation(new_q)
                print(f"[Auto-Quote] Generated quotation {q_name} (ID: {q_id}) for sale {sale_id}")
        except Exception as _aqe:
            print(f"[Auto-Quote] Failed to generate quote: {_aqe}")

        if not skip_print:
            print(f"[DEBUG] create_sale: Starting print thread because skip_print={skip_print}")
            _sale_snap  = dict(sale)
            _items_snap = list(items)
            def _do_print(
                _s=_sale_snap, _i=_items_snap,
                _t=tendered_amount, _c=change_val, _cur=currency,
                _k=kot, _m=method, _cn=cashier_name,
                _cust=customer_name, _cc=customer_contact, _f=footer
            ):
                _print_receipt(_s, _i, _t, _c, _cur, _k, _m, _cn, _cust, _cc, _f)
                print_s(_s)  # ← FIXED: was print_kitchen_orders(_s)
            
            threading.Thread(target=_do_print, daemon=True).start()
        else:
            print(f"[DEBUG] create_sale: SKIPPING print because skip_print={skip_print}")
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
                    print(f"[Fiscalization] [OK] Sale {sale_id} fiscalized successfully on attempt {attempt}")
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
# =============================================================================

def _print_receipt(sale: dict, items: list, tendered: float, change: float,
                   currency: str, kot: str, method: str, cashier_name: str,
                   customer_name: str, customer_contact: str, footer_text: str):
    """Internal function to print receipt with fiscalization wait (up to 6 seconds)."""
    import time
    import threading

    active_printers = _get_active_printers()
    if not active_printers or not sale:
        print("[!] No active printers configured")
        return

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

    fiscal_qr_code = sale.get("fiscal_qr_code", "")
    fiscal_v_code  = sale.get("fiscal_verification_code", "")
    fiscal_ready   = bool(fiscal_qr_code and fiscal_qr_code.strip())

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
                        print(f"[OK] Fiscalization ready after {time.time() - wait_start:.1f} seconds")
                        sale.update(refreshed_sale)
                        break
            except Exception as e:
                print(f"[!] Error checking fiscal status: {e}")

            time.sleep(0.3)

        if not fiscal_ready:
            print(f"[!] Fiscalization not ready after {wait_seconds}s, printing with pending message")
    else:
        fiscal_ready = bool(fiscal_qr_code and fiscal_qr_code.strip())

    # ── Totals ────────────────────────────────────────────────────────────────
    _total_usd  = float(sale.get("total_usd") or 0) or float(total or 0)
    _exch       = float(sale.get("exchange_rate") or 1) or 1
    _cur        = (currency or "USD").strip().upper()

    # Native grand total - used for Payment Details price field
    if _cur not in ("USD", "US"):
        _total_native = float(sale.get("total_zwd") or 0) or round(_total_usd / _exch, 4)
    else:
        _total_native = _total_usd

    # Tendered in USD - only used for change calc, never for Payment Details
    _splits_raw  = sale.get("splits") or []
    _splits_usd  = sum(float(s.get("base_value") or 0) for s in _splits_raw)
    if _splits_usd > 0:
        _tendered_usd = round(_splits_usd, 4)
    else:
        _tendered_usd = float(sale.get("tendered_usd") or 0)
        if _tendered_usd <= 0.005:
            _native = float(tendered or 0)
            if _exch > 0 and _native > 0 and _cur not in ("USD", "US"):
                _tendered_usd = round(_native * _exch, 4)
            elif _cur in ("USD", "US"):
                _tendered_usd = _native

    # Native tendered - shown on receipt header (Amount Tendered field)
    if _cur not in ("USD", "US"):
        _tendered_native = float(sale.get("tendered_zwd") or 0) or float(tendered or 0)
    else:
        _tendered_native = _tendered_usd

    _change_native = float(sale.get("change_amount") or 0)

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
            amountTendered=_tendered_native,
            change=_change_native,
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

        # ── Payment Details ───────────────────────────────────────────────────
        # Priority:
        #   1. payment_entries table - received_amount (local) + paid_amount (USD)
        #   2. splits stashed on sale dict - for fresh sales before DB write
        #   3. Synthesize from grand total - single payment fallback
        pe_splits = []
        sale_id = sale.get("id")
        if sale_id:
            try:
                from database.db import get_connection as _gc
                _conn = _gc()
                _cur  = _conn.cursor()
                # ── FIX: fetch received_amount (local currency) alongside paid_amount (USD) ──
                _cur.execute("""
                    SELECT mode_of_payment, currency, paid_amount,
                           COALESCE(received_amount, paid_amount) AS received_amount
                    FROM payment_entries
                    WHERE sale_id = ?
                      AND (payment_type IS NULL OR payment_type = 'Receive')
                    ORDER BY id
                """, (sale_id,))
                _rows = _cur.fetchall()
                _conn.close()
                pe_splits = [
                    {
                        "method":        r[0],
                        "currency":      (r[1] or "USD").strip().upper(),
                        "amount_usd":    float(r[2]),   # paid_amount     -> USD basis
                        "amount_native": float(r[3]),   # received_amount -> local currency
                    }
                    for r in _rows
                ]
            except Exception as _pe:
                print(f"[_print_receipt] payment_entries lookup failed: {_pe}")

        from models.receipt import Item as _RItem

        if pe_splits:
            receipt.paymentItems = [
                _RItem(
                    productName=ps["method"],
                    productid=ps["currency"],
                    qty=1,
                    price=ps["amount_native"],   # ← local amount (e.g. 900 ZIG)
                    amount=ps["amount_usd"],      # ← USD basis
                    tax_amount=0.0,
                )
                for ps in pe_splits
            ]
        elif _splits_raw:
            # Fresh sale - splits stashed on sale dict before payment_entries written
            receipt.paymentItems = [
                _RItem(
                    productName=str(s.get("method", "CASH")),
                    productid=(s.get("native_currency") or s.get("currency") or "USD").strip().upper(),
                    qty=1,
                    price=float(s.get("native_amount") or s.get("base_value") or 0),
                    amount=float(s.get("base_value") or 0),
                    tax_amount=0.0,
                )
                for s in _splits_raw
            ]
        else:
            # Single payment - use grand total, never tendered
            receipt.paymentItems = [
                _RItem(
                    productName=method or sale.get("method", "CASH"),
                    productid=_cur,
                    qty=1,
                    price=round(_total_native, 2),  # native grand total
                    amount=round(_total_usd, 2),     # USD grand total
                    tax_amount=0.0,
                )
            ]

        # Add fiscal QR code if available
        if fiscal_qr_code and fiscal_qr_code.strip():
            receipt.qrCode = fiscal_qr_code
            receipt.vCode  = fiscal_v_code
        elif fiscal_enabled:
            receipt.qrCode         = ""
            receipt.vCode          = ""
            receipt.fiscal_pending = True

        for it in sale.get("items", []):
            receipt.items.append(Item(
                productName=it["product_name"],
                productid=it.get("part_no", ""),
                qty=float(it["qty"]),
                price=float(it["price"]),
                amount=float(it["total"]),
                tax_amount=float(it.get("tax_amount", 0)),
                batch_no=it.get("batch_no") or "",
                expiry_date=it.get("expiry_date") or "",
            ))

        # Check if packaging list is enabled
        print_pkg = False
        try:
            from database.db import get_connection as _gc
            _conn = _gc()
            _cur = _conn.cursor()
            _cur.execute("SELECT setting_value FROM pos_settings WHERE setting_key = 'print_packaging_list'")
            _row = _cur.fetchone()
            if _row and str(_row[0]) == "1":
                print_pkg = True
            _conn.close()
        except:
            pass

        for printer_name in active_printers:
            try:
                success = PrintingService().print_receipt(receipt, printer_name=printer_name)
                if success:
                    print(f"[OK] Receipt printed successfully -> {printer_name}")
                    if fiscal_enabled and not fiscal_ready:
                        print(f"   Note: Printed with 'Fiscalization Pending' message")
                    if print_pkg:
                        PrintingService().print_packaging_list(receipt, printer_name=printer_name)
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
        "UPDATE sales SET synced = 1, syncing = 0, sync_error = NULL, frappe_ref = ? WHERE id = ?",
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
        ("discount_percent",           "DECIMAL(8,4)  NOT NULL DEFAULT 0"),
        ("fiscal_error",               "NVARCHAR(MAX) NULL"),
        
        # syncing flag - set to 1 while a background thread is pushing this
        # sale to Frappe; cleared to 0 when push succeeds or fails.
        # Prevents two threads from posting the same invoice simultaneously.
        ("syncing",                    "BIT           NOT NULL DEFAULT 0"),
        ("waiter_name",                "NVARCHAR(120) NULL"),
        ("sync_error",                 "NVARCHAR(MAX) NULL"),
        ("cashier_cloud_user_id",      "INT NULL"),
        ("pos_profile",                "NVARCHAR(150) NULL"),
        ("terminal_id",                "NVARCHAR(100) NULL"),
        ("store",                      "NVARCHAR(200) NULL"),
        ("payment_method",             "NVARCHAR(80)  NULL"),
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
            uom          NVARCHAR(20)  NULL,
            serial_no    NVARCHAR(100) NULL,
            price_list_rate DECIMAL(12,2) NULL
        )
    """)

    for col, definition in [
        ("discount",   "DECIMAL(12,2) NOT NULL DEFAULT 0"),
        ("tax",        "NVARCHAR(20)  NOT NULL DEFAULT ''"),
        ("tax_type",   "NVARCHAR(20)  NOT NULL DEFAULT ''"),
        ("tax_rate",   "DECIMAL(8,4)  NOT NULL DEFAULT 0"),
        ("tax_amount", "DECIMAL(12,2) NOT NULL DEFAULT 0"),
        ("serial_no",  "NVARCHAR(100) NULL"),
        ("price_list_rate", "DECIMAL(12,2) NULL"),
        ("remarks",    "NVARCHAR(MAX) NOT NULL DEFAULT ''"),
        ("order_1",    "BIT           NOT NULL DEFAULT 0"),
        ("order_2",    "BIT           NOT NULL DEFAULT 0"),
        ("order_3",    "BIT           NOT NULL DEFAULT 0"),
        ("order_4",    "BIT           NOT NULL DEFAULT 0"),
        ("order_5",    "BIT           NOT NULL DEFAULT 0"),
        ("order_6",    "BIT           NOT NULL DEFAULT 0"),
        ("uom",        "NVARCHAR(20)  NULL"),
        ("cost_price", "DECIMAL(12,4) NOT NULL DEFAULT 0"),
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
    print("[sale] [OK] Tables and columns verified.")


# =============================================================================
# PRIVATE HELPERS
# =============================================================================

def _fetch_items(sale_id: int, cur) -> list[dict]:
    # Pharmacy columns + uom + serial_no + price_list_rate are selected defensively - the SELECT will fail
    # if the migration hasn't run yet, so we fall back to the legacy column set.
    try:
        cur.execute("""
            SELECT id, sale_id, part_no, product_name, qty, price, cost_price,
                   discount, tax, total,
                   tax_type, tax_rate, tax_amount, remarks,
                   order_1, order_2, order_3, order_4, order_5, order_6,
                   is_pharmacy, dosage, batch_no, expiry_date, serial_no, price_list_rate,
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
        "id":              row["id"],
        "sale_id":         row["sale_id"],
        "part_no":         row.get("part_no",      "") or "",
        "product_name":    row.get("product_name", "") or "",
        "qty":             float(row.get("qty",    0)),
        "price":           float(row.get("price",  0)),
        "cost_price":      float(row.get("cost_price", 0) or 0),
        "discount":        float(row.get("discount", 0)),
        "tax":             row.get("tax",      "") or "",
        "total":           float(row.get("total",  0)),
        "tax_type":        row.get("tax_type", "") or "",
        "tax_rate":        float(row.get("tax_rate",   0) or 0),
        "tax_amount":      float(row.get("tax_amount", 0) or 0),
        "remarks":         row.get("remarks",  "") or "",
        "order_1":         bool(row.get("order_1", False)),
        "order_2":         bool(row.get("order_2", False)),
        "order_3":         bool(row.get("order_3", False)),
        "order_4":         bool(row.get("order_4", False)),
        "order_5":         bool(row.get("order_5", False)),
        "order_6":         bool(row.get("order_6", False)),
        # ── Pharmacy-specific fields (safe default if columns absent) ────
        "is_pharmacy":     bool(row.get("is_pharmacy", False)),
        "dosage":          row.get("dosage"),
        "batch_no":        row.get("batch_no"),
        "expiry_date":     expiry_str,
        "serial_no":       row.get("serial_no") or "",
        "price_list_rate": float(row.get("price_list_rate") or row.get("price") or 0.0),
        # UOM from cart (empty string when column is NULL or missing)
        "uom":             row.get("uom") or "",
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

    res = {
        "id":               row["id"],
        "number":           row["invoice_number"],
        "date":             f"{dt.month}/{dt.day}/{dt.year}" if dt else "",
        "time":             dt.strftime("%H:%M")             if dt else "",
        "cashier_id":       row["cashier_id"],
        "user":             row["username"] or str(row["cashier_id"] or ""),
        "total":            float(row["total"]),
        "tendered":         float(row["tendered"]),
        "method":           row["method"]           or "Cash",
        "total_cost":       float(row.get("total_cost", 0) or 0),
        "profit":           float(row["total"]) - float(row.get("total_cost", 0) or 0),
        "gross_percent":    ((float(row["total"]) - float(row.get("total_cost", 0) or 0)) / float(row["total"]) * 100) if float(row["total"]) > 0 else 0.0,
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
        "discount_percent": float(row.get("discount_percent", 0) or 0),
        "receipt_type":     row["receipt_type"]     or "Invoice",
        "footer":           row["footer"]           or "",
        "cashier_name":     row["cashier_name"]     or "",
        "waiter_name":      row.get("waiter_name")  or "",
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
        #   total_usd    -> what the Sales Invoice and Payment Entry use in Frappe
        #   total_zwd    -> the ZWD amount (populated only for ZWD sales)
        #   tendered_usd -> USD cash given (receipt/change display only)
        #   tendered_zwd -> ZWD cash given (receipt/change display only)
        #   exchange_rate-> rate at time of sale (e.g. ZWD->USD = 0.00277)
        "total_usd":     float(row.get("total_usd",    0) or 0),
        "total_zwd":     float(row.get("total_zwd",    0) or 0),
        "tendered_usd":  float(row.get("tendered_usd", 0) or 0),
        "tendered_zwd":  float(row.get("tendered_zwd", 0) or 0),
        "exchange_rate": float(row.get("exchange_rate", 1) or 1),
        "order_number":  int(row.get("order_number",   0) or 0),
        "warehouse_id":   row.get("warehouse_id"),
        "cost_center_id": row.get("cost_center_id"),
        "payment_method":        row.get("payment_method") or row.get("method") or "Cash",
        "pos_profile":           row.get("pos_profile") or "",
        "terminal_id":           row.get("terminal_id"),
        "store":                 row.get("store") or row.get("company_name") or "",
        "cashier_cloud_user_id": row.get("cashier_cloud_user_id"),
    }

    raw_splits = row.get("payment_splits") or row.get("payments")
    parsed_splits = []
    if raw_splits:
        if isinstance(raw_splits, str):
            try:
                parsed_splits = json.loads(raw_splits)
            except Exception:
                parsed_splits = []
        elif isinstance(raw_splits, (list, dict)):
            parsed_splits = raw_splits

    res["payment_splits"] = parsed_splits
    res["payments"]       = parsed_splits
    return res



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
def print_s(sale: dict, is_cancelled: bool = False):
    """Print separate KOT for every active Order 1–6 station.
    Gated on hardware_settings.kitchen_printing_enabled - when off this is a
    no-op so non-restaurant tills don't spam empty KOTs."""
    try:
        from pathlib import Path
        import json
        from models.receipt import ReceiptData, Item
        from services.printing_service import PrintingService
        
        print(f"\n{'='*60}")
        print(f"[KITCHEN DEBUG] print_s() called for invoice: {sale.get('invoice_no', 'N/A')}")
        print(f"[KITCHEN DEBUG] Sale has {len(sale.get('items', []))} items")
        
        # Debug: Print all items and their order flags
        for idx, it in enumerate(sale.get("items", [])):
            print(f"[KITCHEN DEBUG]   Item {idx+1}: {it.get('product_name')}")
            print(f"[KITCHEN DEBUG]     order_1={it.get('order_1', 0)}, order_2={it.get('order_2', 0)}, order_3={it.get('order_3', 0)}")
            print(f"[KITCHEN DEBUG]     order_4={it.get('order_4', 0)}, order_5={it.get('order_5', 0)}, order_6={it.get('order_6', 0)}")
        
        # Check hardware settings file
        hw_file = Path("app_data/hardware_settings.json")
        print(f"[KITCHEN DEBUG] Looking for hardware file at: {hw_file.absolute()}")
        print(f"[KITCHEN DEBUG] File exists: {hw_file.exists()}")
        
        if not hw_file.exists():
            print(f"[KITCHEN DEBUG] ❌ hardware_settings.json NOT FOUND at {hw_file.absolute()}")
            print(f"[KITCHEN DEBUG] Current working directory: {Path.cwd()}")
            return
        
        with open(hw_file, "r", encoding="utf-8") as f:
            hw = json.load(f)
        
        print(f"[KITCHEN DEBUG] Loaded HW settings: {json.dumps(hw, indent=2)}")
        
        kitchen_enabled = True
        print(f"[KITCHEN DEBUG] kitchen_printing_enabled = {kitchen_enabled}")
        
        if not kitchen_enabled:
            print(f"[KITCHEN DEBUG] ❌ Kitchen printing disabled in settings - exiting")
            return

        orders_config = hw.get("orders", {})
        print(f"[KITCHEN DEBUG] Orders config: {orders_config}")
        
        any_active = False
        for order_key in ["Order 1", "Order 2", "Order 3", "Order 4", "Order 5", "Order 6"]:
            config = orders_config.get(order_key, {})
            is_active = config.get("active", False)
            printer = config.get("printer", "(None)")
            print(f"[KITCHEN DEBUG] {order_key}: active={is_active}, printer={printer}")
            if is_active and printer != "(None)":
                any_active = True
        
        if not any_active:
            print(f"[KITCHEN DEBUG] ❌ No active order stations with printers configured")
            return

        printed_count = 0
        for order_key in ["Order 1", "Order 2", "Order 3", "Order 4", "Order 5", "Order 6"]:
            config = orders_config.get(order_key, {})
            if not config.get("active", False):
                continue

            printer_name = config.get("printer")
            if not printer_name or printer_name == "(None)":
                continue

            order_field = order_key.lower().replace(" ", "_")
            print(f"[KITCHEN DEBUG] Checking for {order_key} (field: {order_field})")
            
            order_items = [it for it in sale.get("items", []) if it.get(order_field)]
            print(f"[KITCHEN DEBUG]   Found {len(order_items)} items for {order_key}: {[it.get('product_name') for it in order_items]}")
            
            if not order_items:
                continue

            # Fetch company branding if missing from the sale dict
            company_name = sale.get("company_name", "")
            address_1 = sale.get("address_1", "")
            address_2 = sale.get("address_2", "")
            phone = sale.get("phone", "")
            
            if not company_name:
                try:
                    from models.company_defaults import get_defaults
                    co = get_defaults() or {}
                    company_name = co.get("company_name", "Havano POS")
                    address_1 = co.get("address", "")
                    phone = co.get("phone", "")
                except Exception:
                    company_name = "Havano POS"

            print(f"[KITCHEN DEBUG] Creating KOT receipt for {order_key} with {len(order_items)} items")
            kot_receipt = ReceiptData(
                invoiceNo=str(sale.get("invoice_no") or "N/A"),
                KOT=order_key,
                cashierName=sale.get("cashier_name", ""),
                orderNumber=int(sale.get("order_number", 0) or 0),
                companyName=company_name,
                items=[Item(
                    productName=it["product_name"],
                    qty=float(it["qty"] if it.get("qty") is not None else 1),
                    productid=it.get("part_no", ""),
                    item_notes=it.get("item_notes", it.get("notes", "")),
                    is_cancelled=bool(it.get("is_cancelled", False)),
                    old_qty=float(it.get("old_qty", 0.0) or 0.0)
                ) for it in order_items],
                bill_notes=sale.get("bill_notes", ""),
                customerName=sale.get("customer_name", ""),
                cancel_reason=sale.get("cancel_reason", ""),
                is_modified=bool(sale.get("is_modified", False)),
                modify_reason=str(sale.get("modify_reason") or ""),
            )
            # Populate additional branding fields
            kot_receipt.companyAddress = address_1
            kot_receipt.companyAddressLine1 = address_2
            kot_receipt.tel = phone
            
            print(f"[KITCHEN DEBUG] Sending to printer: {printer_name}")
            success = PrintingService().print_kitchen_order(kot_receipt, printer_name=printer_name, is_cancelled=is_cancelled)
            if success:
                print(f"[OK] KOT printed for {order_key} -> {printer_name}")
                printed_count += 1
            else:
                print(f"[!] KOT failed for {order_key} -> {printer_name}")
        
        print(f"[KITCHEN DEBUG] Total KOTs printed: {printed_count}")
        print(f"{'='*60}\n")

    except Exception as e:
        print(f"❌ Kitchen Order printing error: {e}")
        import traceback
        traceback.print_exc()

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
        print("\n[OK] No duplicate transactions found!")
    else:
        print(f"\n[!] FOUND {len(duplicates)} POTENTIAL DUPLICATE TRANSACTIONS:\n")
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
    print("\n[INFO] TIPS:")
    print("   1. Check if your frontend is submitting the form twice")
    print("   2. Check if button click handlers are firing twice")
    print("   3. Pass idempotency_key= to create_sale() to prevent duplicates automatically")


def prepare_receipt_data(sale: dict) -> ReceiptData:
    """Centralized converter to transform a raw sale dictionary into a ReceiptData object."""
    # Build items list
    items_list = []
    for it in sale.get("items", []):
        items_list.append(Item(
            productName=it.get("product_name", ""),
            productid=it.get("part_no", ""),
            qty=float(it.get("qty", 1)),
            price=float(it.get("price", 0)),
            amount=float(it.get("total", 0)),
            tax_amount=float(it.get("tax_amount", 0)),
            batch_no=it.get("batch_no") or "",
            expiry_date=it.get("expiry_date") or "",
            item_notes=it.get("item_notes", it.get("notes", "")),
        ))

    currency    = (sale.get("currency") or "USD").strip().upper()
    splits      = sale.get("splits") or []

    # ── Amount Tendered ───────────────────────────────────────────────────────
    tendered_native = float(sale.get("tendered") or 0)
    tendered_usd    = float(sale.get("tendered_usd") or 0)

    if len(splits) > 1:
        display_tendered = tendered_usd if tendered_usd > 0 else tendered_native
        display_currency = "USD"
    else:
        display_tendered = tendered_native
        display_currency = currency

    # ── Change ────────────────────────────────────────────────────────────────
    change_value = float(sale.get("change_amount") or 0)

    # Fetch company defaults for receipt header, footer, and company details
    co_defs = {}
    try:
        from models.company_defaults import get_defaults
        co_defs = get_defaults() or {}
    except Exception:
        pass

    default_header = (co_defs.get("receipt_header") or "").strip()
    company_footer = (co_defs.get("footer_text") or "").strip()
    sale_footer = (sale.get("footer") or "").strip()

    header_text = default_header or sale.get("receipt_type", "SALES RECEIPT")
    footer_text = company_footer if company_footer else (sale_footer or "Thank you for your purchase!")

    # Strip dining option suffix from header text for clean display
    if " - " in header_text:
        parts = header_text.split(" - ")
        if parts[-1].lower() in ["take away", "takeaway", "sit in", "sitin"]:
            header_text = " - ".join(parts[:-1])

    # ── Build ReceiptData ─────────────────────────────────────────────────────
    receipt = ReceiptData(
        invoiceNo=sale.get("invoice_no", ""),
        invoiceDate=sale.get("invoice_date", sale.get("date", "")),
        cashierName=sale.get("cashier_name", sale.get("user", "")),
        customerName=sale.get("customer_name", "Walk-in"),
        customerContact=sale.get("customer_contact", ""),
        companyName=sale.get("company_name") or co_defs.get("company_name") or "HAVANO POS",
        grandTotal=float(sale.get("total") or 0),
        subtotal=float(sale.get("subtotal") or 0),
        totalVat=float(sale.get("total_vat") or 0),
        amountTendered=display_tendered,
        change=change_value,
        currency=display_currency,
        items=items_list,
        footer=footer_text,
        receiptHeader=header_text,
        receiptType=sale.get("receipt_type", "Sales"),
        orderNumber=int(sale.get("order_number", 0) or 0),
        bill_notes=sale.get("bill_notes", "")
    )

    # ── Company info ──────────────────────────────────────────────────────────
    receipt.companyAddress      = sale.get("address_1") or co_defs.get("address_1", "")
    receipt.companyAddressLine1 = sale.get("address_2") or co_defs.get("address_2", "")
    receipt.tel                 = sale.get("phone") or co_defs.get("phone", "")
    receipt.companyEmail        = sale.get("email") or co_defs.get("email", "")
    receipt.tin                 = sale.get("tin_number") or co_defs.get("tin_number", "")
    receipt.vatNo               = sale.get("vat_number") or co_defs.get("vat_number", "")

    # ── Fetch Customer details to print on receipt ────────────────────────────
    cust_name = sale.get("customer_name", "").strip()
    if cust_name and cust_name.lower() not in ("walk-in", "walk in customer", "default customer", "default"):
        try:
            from database.db import get_connection
            _c_conn = get_connection()
            _c_cur = _c_conn.cursor()
            _c_cur.execute(
                "SELECT custom_email_address, custom_house_no, custom_city, custom_customer_tin, custom_customer_vat "
                "FROM customers WHERE customer_name = ?", (cust_name,)
            )
            _c_row = _c_cur.fetchone()
            _c_conn.close()
            if _c_row:
                receipt.customerEmail = _c_row[0] or ""
                
                addr_parts = [p for p in (_c_row[1], _c_row[2]) if p]
                receipt.customeraddress = ", ".join(addr_parts)
                
                receipt.customerTin = _c_row[3] or ""
                receipt.customerVat = _c_row[4] or ""
        except Exception:
            pass

    # ── Fiscal fields ─────────────────────────────────────────────────────────
    receipt.qrCode       = sale.get("fiscal_qr_code", "")
    receipt.vCode        = sale.get("fiscal_verification_code", "")
    receipt.deviceSerial = sale.get("zimra_serial_no", "")
    receipt.deviceId     = sale.get("zimra_device_id", "")
    receipt.receiptNo    = sale.get("fiscal_global_no", "")
    receipt.fiscalDay    = sale.get("fiscal_day", "")
    receipt.fiscal_status = sale.get("fiscal_status", "pending")

    # ── Payment Details (paymentItems) ───────────────────────────────────────
    # Priority:
    #   1. payment_entries table - received_amount (local) + paid_amount (USD)
    #   2. splits stashed on sale dict - fresh sales before payment_entries written
    #   3. Synthesize from grand total - single payment fallback
    _exch         = float(sale.get("exchange_rate") or 1) or 1
    _total_usd    = float(sale.get("total_usd") or sale.get("total") or 0)
    _total_native = float(sale.get("total_zwd") or 0) or (
        round(_total_usd / _exch, 2) if currency not in ("USD", "US") else _total_usd
    )

    pe_splits = []
    sale_id = sale.get("id")
    if sale_id:
        try:
            from database.db import get_connection as _gc
            _conn = _gc()
            _cur  = _conn.cursor()
            # ── FIX: fetch received_amount (local currency) alongside paid_amount (USD) ──
            _cur.execute("""
                SELECT mode_of_payment, currency, paid_amount,
                       COALESCE(received_amount, paid_amount) AS received_amount
                FROM payment_entries
                WHERE sale_id = ?
                  AND (payment_type IS NULL OR payment_type = 'Receive')
                ORDER BY id
            """, (sale_id,))
            _rows = _cur.fetchall()
            _conn.close()
            pe_splits = [
                {
                    "method":        r[0],
                    "currency":      (r[1] or "USD").strip().upper(),
                    "amount_usd":    float(r[2]),   # paid_amount     -> USD basis
                    "amount_native": float(r[3]),   # received_amount -> local currency
                }
                for r in _rows
            ]
        except Exception as _e:
            print(f"[prepare_receipt_data] payment_entries lookup failed: {_e}")

    if pe_splits:
        for ps in pe_splits:
            receipt.paymentItems.append(Item(
                productName=ps["method"],
                productid=ps["currency"],
                qty=1,
                price=ps["amount_native"],   # ← local amount (e.g. 900 ZIG)
                amount=ps["amount_usd"],      # ← USD basis
            ))
    elif splits:
        for sp in splits:
            native_cur = (sp.get("native_currency") or sp.get("currency") or "USD").strip().upper()
            if native_cur in ("US", ""):
                native_cur = "USD"
            receipt.paymentItems.append(Item(
                productName=sp.get("method", "PAYMENT"),
                productid=native_cur,
                qty=1,
                price=float(sp.get("native_amount") or sp.get("base_value") or 0),
                amount=float(sp.get("base_value") or 0),
            ))
    else:
        # Single payment - grand total in native, never tendered
        receipt.paymentItems.append(Item(
            productName=sale.get("method", "PAYMENT"),
            productid=currency,
            qty=1,
            price=round(_total_native, 2),  # native (e.g. 5010 ZIG)
            amount=round(_total_usd, 2),     # USD
        ))

    # ── Multi-currency detail block ───────────────────────────────────────────
    if sale.get("total_zwd", 0) > 0:
        receipt.multiCurrencyDetails.append(MultiCurrencyDetail(
            key="ZWG",
            value=float(sale["total_zwd"])
        ))

    return receipt