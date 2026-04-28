# =============================================================================
# models/shift.py  —  SQL Server version (Fixed income capture with split payments)
# FIX: Added 'currency' column to shift_rows (ALTER TABLE migration for existing DBs)
# FIX: Payment method totals now use actual paid_amount per entry, not sale total
# FIX: get_print_ready_cashiers now correctly calculates expected per cashier
# =============================================================================

from database.db import get_connection, fetchall_dicts, fetchone_dict
import logging
from datetime import datetime
from decimal import Decimal
import json

log = logging.getLogger("shift")

# =============================================================================
# AUTO MIGRATION ON IMPORT
# =============================================================================

_MIGRATED = False

def _auto_migrate():
    """Ensure the currency column exists on shift_rows. Safe to call multiple times."""
    global _MIGRATED
    if _MIGRATED:
        return
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM sys.columns
                WHERE object_id = OBJECT_ID('shift_rows') AND name = 'currency'
            )
            ALTER TABLE shift_rows ADD currency NVARCHAR(10) NOT NULL DEFAULT 'USD'
        """)
        conn.commit()
        conn.close()
        log.info("[shift] Auto-migration: currency column ensured on shift_rows.")
    except Exception as e:
        log.warning(f"[shift] Auto-migration warning: {e}")
    _MIGRATED = True

_auto_migrate()

# =============================================================================
# READ
# =============================================================================

def get_active_shift() -> dict | None:
    """Return the currently open (not ended) shift, or None."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT TOP 1
               s.id, s.shift_number, s.station, s.cashier_id, s.date,
               s.created_at, s.end_time, s.door_counter, s.customers, s.notes,
               COALESCE(u.username, '') AS username,
               COALESCE(u.full_name, u.username, '') AS cashier_fullname
        FROM shifts s
        LEFT JOIN users u ON u.id = s.cashier_id
        WHERE s.end_time IS NULL
        ORDER BY s.id DESC
    """)
    row = fetchone_dict(cur)
    if not row:
        conn.close()
        return None
    row["rows"] = _get_shift_rows(row["id"], cur)
    row["is_open"] = True
    row["cashier_sales"] = _get_cashier_sales_for_shift(row["id"], cur)
    conn.close()
    return row


def get_last_shift() -> dict | None:
    """Return the most recent shift (open or closed)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT TOP 1
               s.id, s.shift_number, s.station, s.cashier_id, s.date,
               s.created_at, s.end_time, s.door_counter, s.customers, s.notes,
               COALESCE(u.username, '') AS username,
               COALESCE(u.full_name, u.username, '') AS cashier_fullname
        FROM shifts s
        LEFT JOIN users u ON u.id = s.cashier_id
        ORDER BY s.id DESC
    """)
    row = fetchone_dict(cur)
    if not row:
        conn.close()
        return None
    row["rows"] = _get_shift_rows(row["id"], cur)
    row["is_open"] = row["end_time"] is None
    row["cashier_sales"] = _get_cashier_sales_for_shift(row["id"], cur)
    conn.close()
    return row


def get_next_shift_number() -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(MAX(shift_number), 0) FROM shifts")
    row = cur.fetchone()
    conn.close()
    return int(row[0]) + 1


def get_closed_shift_detail(shift_id: int) -> dict | None:
    return get_shift_by_id(shift_id)


def get_all_closed_shifts(date_from: str = None, date_to: str = None) -> list[dict]:
    conn = get_connection()
    cur = conn.cursor()

    query = """
        SELECT s.id, s.shift_number, s.station, s.cashier_id, s.date,
               s.created_at, s.end_time, s.door_counter, s.customers, s.notes,
               COALESCE(u.username, '') AS username,
               COALESCE(u.full_name, u.username, '') AS cashier_fullname
        FROM shifts s
        LEFT JOIN users u ON u.id = s.cashier_id
        WHERE s.end_time IS NOT NULL
    """
    params = []
    if date_from and date_to:
        query += " AND s.date BETWEEN ? AND ?"
        params = [date_from, date_to]
    elif date_from:
        query += " AND s.date >= ?"
        params = [date_from]

    query += " ORDER BY s.id DESC"
    cur.execute(query, params)
    shifts = fetchall_dicts(cur)
    result = []
    for s in shifts:
        s["rows"] = _get_shift_rows(s["id"], cur)
        s["is_open"] = False
        s["total_expected"] = sum(r["total"] for r in s["rows"])
        s["total_counted"] = sum(r["counted"] for r in s["rows"])
        s["total_variance"] = sum(r["variance"] for r in s["rows"])
        s["cashier_sales"] = _get_cashier_sales_for_shift(s["id"], cur)
        result.append(s)
    conn.close()
    return result


def get_income_by_method_since(shift_id: int) -> dict:
    """Returns combined income for this specific shift only, including On Account."""
    conn = get_connection()
    cur = conn.cursor()
    result: dict = {}

    cur.execute("SELECT created_at FROM shifts WHERE id = ?", (shift_id,))
    row = cur.fetchone()
    if not row or not row[0]:
        log.error(f"Could not find shift {shift_id}")
        conn.close()
        return {}

    shift_start = row[0]
    if isinstance(shift_start, str):
        try:
            if '.' in shift_start:
                shift_start = datetime.strptime(shift_start.split('.')[0], "%Y-%m-%d %H:%M:%S")
            else:
                shift_start = datetime.strptime(shift_start[:19], "%Y-%m-%d %H:%M:%S")
        except:
            pass

    log.info(f"[INCOME DEBUG] Shift {shift_id} start timestamp: {shift_start}")

    try:
        cur.execute("""
            SELECT 
                LTRIM(RTRIM(pe.mode_of_payment)) AS payment_method,
                pe.received_amount,
                COALESCE(gl.account_currency, pe.currency, 'USD') as currency
            FROM payment_entries pe
            LEFT JOIN gl_accounts gl ON pe.paid_to = gl.name
            WHERE pe.shift_id = ?
              AND (pe.payment_type IS NULL OR pe.payment_type = 'Receive')
        """, (shift_id,))

        matches = cur.fetchall()
        log.info(f"[INCOME DEBUG] Found {len(matches)} payment entries for shift_id {shift_id}")

        for m_method, m_amount, m_curr in matches:
            if m_method:
                method = m_method.strip()
                curr = m_curr.strip() if m_curr else "USD"
                key = (method, curr)
                if key not in result:
                    result[key] = {"amount": 0.0, "method": method, "currency": curr}
                result[key]["amount"] += float(m_amount)

        cur.execute("""
            SELECT 
                COALESCE(SUM(total - tendered), 0) AS total_amount,
                COALESCE(MAX(currency), 'USD') as currency
            FROM sales
            WHERE shift_id = ?
              AND is_on_account = 1
              AND total > tendered
        """, (shift_id,))

        oa_row = cur.fetchone()
        if oa_row and oa_row[0] > 0:
            result["ON ACCOUNT"] = {"amount": float(oa_row[0]), "currency": oa_row[1] or "USD"}
            log.info(f"  [INCOME DEBUG] ON ACCOUNT: ${oa_row[0]:.2f}")

    except Exception as e:
        log.error(f"Error fetching income by shift_id: {e}. Falling back to timestamp...")
        cur.execute("SELECT created_at FROM shifts WHERE id = ?", (shift_id,))
        row = cur.fetchone()
        if row and row[0]:
            shift_start = row[0]
            cur.execute("""
                SELECT LTRIM(RTRIM(mode_of_payment)) as meth, received_amount, COALESCE(currency, 'USD')
                FROM payment_entries WHERE created_at >= ? AND (shift_id IS NULL OR shift_id = 0)
            """, (shift_start,))
            for m, a, c in cur.fetchall():
                if m:
                    if m not in result:
                        result[m] = {"amount": 0.0, "currency": c or "USD"}
                    result[m]["amount"] += float(a)

    conn.close()
    log.info(f"[INCOME DEBUG] Final Income Map for Shift {shift_id}: {result}")
    return result


def refresh_income(shift_id: int) -> dict:
    """Read live sales/payment totals and write them into shift_rows.income."""
    income_by_method = get_income_by_method_since(shift_id)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT method, currency, id FROM shift_rows WHERE shift_id = ?", (shift_id,))
    shift_rows_data = cur.fetchall()
    shift_methods = [row[0] for row in shift_rows_data]

    cur.execute("SELECT end_time FROM shifts WHERE id = ?", (shift_id,))
    shift_row = cur.fetchone()
    is_closed = shift_row and shift_row[0] is not None

    updated_income = {}

    # Handle ON ACCOUNT
    on_account_amount = 0.0
    on_account_entry = income_by_method.get("ON ACCOUNT")
    if on_account_entry:
        on_account_amount = float(on_account_entry) if isinstance(on_account_entry, (int, float)) else float(on_account_entry.get("amount", 0))

    has_on_account = any(m.upper() == "ON ACCOUNT" for m in shift_methods)

    if on_account_amount > 0 and not has_on_account:
        cur.execute("""
            INSERT INTO shift_rows (shift_id, method, currency, start_float, income, counted)
            VALUES (?, ?, ?, 0, ?, 0)
        """, (shift_id, "ON ACCOUNT", "USD", float(on_account_amount)))
        shift_methods.append("ON ACCOUNT")
        print(f"[INFO] Added ON ACCOUNT row to shift_rows with income: {on_account_amount}")
    elif has_on_account and on_account_amount == 0:
        cur.execute("""
            UPDATE shift_rows SET income = 0 WHERE shift_id = ? AND method = 'ON ACCOUNT'
        """, (shift_id,))
    elif has_on_account and on_account_amount > 0:
        cur.execute("""
            UPDATE shift_rows SET income = ? WHERE shift_id = ? AND method = 'ON ACCOUNT'
        """, (float(on_account_amount), shift_id))

    # Process all other payment methods
    for key, method_data in income_by_method.items():
        if key == "ON ACCOUNT":
            continue

        if isinstance(key, tuple):
            method_name, currency_val = key
        else:
            method_name = key
            currency_val = method_data.get("currency", "USD") if isinstance(method_data, dict) else "USD"

        income_val = float(method_data["amount"]) if isinstance(method_data, dict) else float(method_data)

        # 1. Exact match on method + currency
        cur.execute("""
            SELECT id FROM shift_rows 
            WHERE shift_id = ? AND method = ? AND currency = ?
        """, (shift_id, method_name, currency_val))
        exact_row = cur.fetchone()

        if exact_row:
            if not is_closed:
                cur.execute("UPDATE shift_rows SET income = ? WHERE id = ?", (income_val, exact_row[0]))
            continue

        # 2. Default USD row for same method with no income yet
        cur.execute("""
            SELECT id FROM shift_rows 
            WHERE shift_id = ? AND method = ? AND currency = 'USD' AND income = 0
        """, (shift_id, method_name))
        default_row = cur.fetchone()

        if default_row:
            if not is_closed:
                cur.execute("UPDATE shift_rows SET currency = ?, income = ? WHERE id = ?",
                            (currency_val, income_val, default_row[0]))
                print(f"[INFO] Updated default USD row for '{method_name}' to {currency_val} with income {income_val}")
            continue

        # 3. Insert new row if income > 0
        if not is_closed and income_val != 0:
            cur.execute("""
                INSERT INTO shift_rows (shift_id, method, currency, start_float, income, counted)
                VALUES (?, ?, ?, 0, ?, 0)
            """, (shift_id, method_name, currency_val, income_val))
            print(f"[INFO] Discovered new payment method '{method_name}' ({currency_val}). Added to shift_rows.")

    if not is_closed:
        conn.commit()
    conn.close()

    return updated_income


def get_shift_payment_methods(shift_id: int) -> list:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT method
        FROM shift_rows
        WHERE shift_id = ?
        ORDER BY method
    """, (shift_id,))
    methods = [row[0] for row in cur.fetchall()]
    conn.close()
    return methods


def get_cashier_sales_for_shift(shift_id: int) -> list[dict]:
    """Get detailed breakdown of what each cashier sold during a shift, including On Account."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT s.created_at, s.end_time, s.cashier_id 
        FROM shifts s
        WHERE s.id = ?
    """, (shift_id,))

    shift_row = cur.fetchone()
    if not shift_row:
        conn.close()
        return []

    start_time = shift_row[0]
    end_time = shift_row[1] if shift_row[1] else datetime.now()

    cur.execute("""
        SELECT 
            s.id as sale_id,
            s.invoice_no,
            s.invoice_date,
            s.created_at,
            s.cashier_id,
            COALESCE(u.username, u.full_name, 'Cashier') as cashier_name,
            s.total,
            s.subtotal,
            s.total_vat,
            s.discount_amount,
            s.method as sale_method,
            s.company_name,
            s.customer_name,
            s.synced,
            s.is_on_account,
            s.tendered,
            si.id as item_id,
            si.part_no,
            si.product_name,
            si.qty,
            si.price,
            si.discount as item_discount,
            si.total as item_total,
            si.tax_rate,
            si.tax_amount,
            si.tax_type,
            pe.mode_of_payment,
            pe.paid_amount,
            pe.payment_type
        FROM sales s
        LEFT JOIN sale_items si ON si.sale_id = s.id
        LEFT JOIN payment_entries pe ON pe.sale_id = s.id AND pe.payment_type = 'Receive'
        LEFT JOIN users u ON u.id = s.cashier_id
        WHERE s.shift_id = ?
        ORDER BY s.created_at DESC, s.id, si.id
    """, (shift_id,))

    rows = fetchall_dicts(cur)
    conn.close()

    result = {}
    for row in rows:
        cashier_id = row.get('cashier_id')
        cashier_name = row.get('cashier_name', 'Unknown Cashier')

        if not cashier_name or cashier_name == 'Cashier':
            cashier_name = f"Cashier #{cashier_id}" if cashier_id else "Unknown Cashier"

        cashier_key = f"{cashier_id}_{cashier_name}"

        if cashier_key not in result:
            result[cashier_key] = {
                'cashier_id': cashier_id,
                'cashier_name': cashier_name,
                'sales': [],
                'totals': {
                    'total_sales': 0.0,
                    'total_items': 0,
                    'total_vat': 0.0,
                    'total_discount': 0.0,
                    'total_payments': 0.0,
                    'payment_methods': {}
                }
            }

        sale_exists = False
        for existing_sale in result[cashier_key]['sales']:
            if existing_sale['sale_id'] == row['sale_id']:
                sale_exists = True

                if row['mode_of_payment'] and row['mode_of_payment'] not in existing_sale['payment_methods']:
                    existing_sale['payment_methods'].append(row['mode_of_payment'])
                    paid = float(row['paid_amount'] or 0)
                    existing_sale['payment_amounts'].append(paid)
                    pmt_key = row['mode_of_payment'].strip().upper()
                    result[cashier_key]['totals']['payment_methods'][pmt_key] = (
                        result[cashier_key]['totals']['payment_methods'].get(pmt_key, 0.0) + paid
                    )

                if row.get('is_on_account', False) and row.get('total', 0) > row.get('tendered', 0):
                    oa_amount = float(row.get('total', 0)) - float(row.get('tendered', 0))
                    if "ON ACCOUNT" not in existing_sale['payment_methods']:
                        existing_sale['payment_methods'].append("ON ACCOUNT")
                        existing_sale['payment_amounts'].append(oa_amount)
                        pmt_key = "ON ACCOUNT"
                        result[cashier_key]['totals']['payment_methods'][pmt_key] = (
                            result[cashier_key]['totals']['payment_methods'].get(pmt_key, 0.0) + oa_amount
                        )

                if row['item_id']:
                    existing_sale['items'].append({
                        'part_no': row['part_no'],
                        'product_name': row['product_name'],
                        'qty': float(row['qty']) if row['qty'] else 0,
                        'price': float(row['price']) if row['price'] else 0,
                        'discount': float(row['item_discount']) if row['item_discount'] else 0,
                        'total': float(row['item_total']) if row['item_total'] else 0,
                        'tax_rate': float(row['tax_rate']) if row['tax_rate'] else 0,
                        'tax_amount': float(row['tax_amount']) if row['tax_amount'] else 0
                    })
                break

        if not sale_exists and row['sale_id']:
            sale_record = {
                'sale_id': row['sale_id'],
                'invoice_no': row['invoice_no'],
                'invoice_date': row['invoice_date'],
                'created_at': row['created_at'],
                'total': float(row['total']) if row['total'] else 0,
                'subtotal': float(row['subtotal']) if row['subtotal'] else 0,
                'total_vat': float(row['total_vat']) if row['total_vat'] else 0,
                'discount_amount': float(row['discount_amount']) if row['discount_amount'] else 0,
                'sale_method': row['sale_method'],
                'customer_name': row['customer_name'],
                'company_name': row['company_name'],
                'synced': row['synced'],
                'is_on_account': row.get('is_on_account', False),
                'tendered': float(row.get('tendered', 0)),
                'payment_methods': [],
                'payment_amounts': [],
                'items': []
            }

            if row['mode_of_payment']:
                paid = float(row['paid_amount'] or 0)
                sale_record['payment_methods'].append(row['mode_of_payment'])
                sale_record['payment_amounts'].append(paid)
                pmt_key = row['mode_of_payment'].strip().upper()
                result[cashier_key]['totals']['payment_methods'][pmt_key] = (
                    result[cashier_key]['totals']['payment_methods'].get(pmt_key, 0.0) + paid
                )

            if row.get('is_on_account', False) and row.get('total', 0) > row.get('tendered', 0):
                oa_amount = float(row.get('total', 0)) - float(row.get('tendered', 0))
                sale_record['payment_methods'].append("ON ACCOUNT")
                sale_record['payment_amounts'].append(oa_amount)
                pmt_key = "ON ACCOUNT"
                result[cashier_key]['totals']['payment_methods'][pmt_key] = (
                    result[cashier_key]['totals']['payment_methods'].get(pmt_key, 0.0) + oa_amount
                )

            if row['item_id']:
                sale_record['items'].append({
                    'part_no': row['part_no'],
                    'product_name': row['product_name'],
                    'qty': float(row['qty']) if row['qty'] else 0,
                    'price': float(row['price']) if row['price'] else 0,
                    'discount': float(row['item_discount']) if row['item_discount'] else 0,
                    'total': float(row['item_total']) if row['item_total'] else 0,
                    'tax_rate': float(row['tax_rate']) if row['tax_rate'] else 0,
                    'tax_amount': float(row['tax_amount']) if row['tax_amount'] else 0
                })

            result[cashier_key]['sales'].append(sale_record)
            result[cashier_key]['totals']['total_sales'] += sale_record['total']
            result[cashier_key]['totals']['total_items'] += len(sale_record['items'])
            result[cashier_key]['totals']['total_vat'] += sale_record['total_vat']
            result[cashier_key]['totals']['total_discount'] += sale_record['discount_amount']

    return list(result.values())


def get_shift_cashier_summary(shift_id: int) -> list[dict]:
    """Get summary of what each cashier sold during a shift."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT created_at, end_time FROM shifts WHERE id = ?", (shift_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return []

    start_time = row[0]
    end_time = row[1] if row[1] else datetime.now()

    cur.execute("""
        SELECT 
            s.cashier_id,
            s.cashier_name,
            COUNT(DISTINCT s.id) as num_sales,
            COUNT(DISTINCT si.id) as num_items_sold,
            COALESCE(SUM(s.total), 0) as total_amount,
            COALESCE(SUM(s.total_vat), 0) as total_vat,
            COALESCE(SUM(s.discount_amount), 0) as total_discount,
            COALESCE(AVG(s.total), 0) as avg_sale_value,
            COALESCE(SUM(pe.paid_amount), 0) as total_payments
        FROM sales s
        LEFT JOIN sale_items si ON si.sale_id = s.id
        LEFT JOIN payment_entries pe ON pe.sale_id = s.id AND pe.payment_type = 'Receive'
        WHERE s.created_at >= ? AND s.created_at <= ?
        GROUP BY s.cashier_id, s.cashier_name
        ORDER BY total_amount DESC
    """, (start_time, end_time))

    results = fetchall_dicts(cur)
    conn.close()

    for r in results:
        for key in ['total_amount', 'total_vat', 'total_discount', 'avg_sale_value', 'total_payments']:
            if key in r:
                r[key] = float(r[key])
        r['num_sales'] = int(r['num_sales'])
        r['num_items_sold'] = int(r['num_items_sold'])

    return results


def get_cashier_shift_history(cashier_id: int, limit: int = 10) -> list[dict]:
    """Get shift history for a specific cashier."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            s.id as shift_id,
            s.shift_number,
            s.date,
            s.created_at as start_time,
            s.end_time,
            s.door_counter,
            s.customers,
            COUNT(DISTINCT sal.id) as sales_count,
            COALESCE(SUM(sal.total), 0) as total_sales,
            COALESCE(SUM(sal.total_vat), 0) as total_vat,
            COALESCE(AVG(sal.total), 0) as avg_sale,
            COALESCE(SUM(pe.paid_amount), 0) as total_payments
        FROM shifts s
        LEFT JOIN sales sal ON sal.cashier_id = s.cashier_id 
            AND sal.created_at >= s.created_at
            AND (sal.created_at <= s.end_time OR s.end_time IS NULL)
        LEFT JOIN payment_entries pe ON pe.sale_id = sal.id AND pe.payment_type = 'Receive'
        WHERE s.cashier_id = ?
        GROUP BY s.id, s.shift_number, s.date, s.created_at, s.end_time, 
                 s.door_counter, s.customers
        ORDER BY s.id DESC
        OFFSET 0 ROWS FETCH NEXT ? ROWS ONLY
    """, (cashier_id, limit))

    results = fetchall_dicts(cur)
    conn.close()

    for r in results:
        for key in ['total_sales', 'total_vat', 'avg_sale', 'total_payments']:
            if key in r:
                r[key] = float(r[key])
        r['sales_count'] = int(r['sales_count'])
        r['customers_served'] = int(r.get('customers', 0))

    return results


def get_print_ready_cashiers(shift_id: int) -> list[dict]:
    """Get cashier data for printing with CORRECT expected, counted, and variance."""
    shift_data = get_shift_by_id(shift_id)
    if not shift_data:
        return []

    cashier_sales = get_cashier_sales_for_shift(shift_id)

    shift_row_map = {}
    for row in shift_data.get("rows", []):
        method_upper = row["method"].strip().upper()
        shift_row_map[method_upper] = {
            "expected_global": float(row["total"]),
            "counted_global": float(row["counted"]),
        }

    total_collected_per_method = {}
    for cashier in cashier_sales:
        cashier_payment_methods = cashier.get('totals', {}).get('payment_methods', {})
        for method_key, amount_collected in cashier_payment_methods.items():
            method_upper = method_key.strip().upper()
            total_collected_per_method[method_upper] = total_collected_per_method.get(method_upper, 0.0) + amount_collected

    result = []

    for cashier in cashier_sales:
        payment_rows = []
        cashier_payment_methods = cashier.get('totals', {}).get('payment_methods', {})

        if not cashier_payment_methods:
            continue

        for method_key, amount_collected in cashier_payment_methods.items():
            method_upper = method_key.strip().upper()

            global_expected = shift_row_map.get(method_upper, {}).get("expected_global", 0.0)
            global_counted = shift_row_map.get(method_upper, {}).get("counted_global", 0.0)
            total_method_collected = total_collected_per_method.get(method_upper, 0.0)

            proportion = (amount_collected / total_method_collected) if total_method_collected > 0 else 0.0
            cashier_expected = global_expected * proportion
            cashier_counted = global_counted * proportion
            variance = cashier_counted - cashier_expected

            transaction_count = 0
            for sale in cashier.get('sales', []):
                for pm in sale.get('payment_methods', []):
                    if pm.strip().upper() == method_upper:
                        transaction_count += 1
                        break

            payment_rows.append({
                "method": method_key,
                "collected": amount_collected,
                "expected": cashier_expected,
                "counted": cashier_counted,
                "variance": variance,
                "transaction_count": transaction_count,
            })

        if not payment_rows:
            continue

        payment_rows.sort(key=lambda x: x["method"])

        total_expected = sum(r["expected"] for r in payment_rows)
        total_counted = sum(r["counted"] for r in payment_rows)
        total_variance = total_counted - total_expected

        result.append({
            "username": cashier['cashier_name'],
            "cashier_id": cashier['cashier_id'],
            "rows": payment_rows,
            "total_sales": cashier['totals']['total_sales'],
            "transactions": len(cashier['sales']),
            "total_expected": total_expected,
            "total_counted": total_counted,
            "total_variance": total_variance,
        })

    result.sort(key=lambda x: x["username"])
    return result


def print_shift_cashier_report(shift_id: int):
    """Print a formatted report showing what each cashier sold during a shift."""
    print(f"\n{'='*80}")
    print(f"SHIFT CASHIER REPORT - Shift #{shift_id}")
    print(f"{'='*80}")

    shift = get_shift_by_id(shift_id)
    if not shift:
        print(f"Shift {shift_id} not found")
        return

    print(f"Shift Date: {shift.get('date')}")
    print(f"Period: {shift.get('created_at')} - {shift.get('end_time', 'Still Open')}")
    print(f"{'='*80}\n")

    summary = get_shift_cashier_summary(shift_id)

    if not summary:
        print("No sales recorded for this shift.")
        return

    print(f"{'Cashier':<25} {'# Sales':<10} {'# Items':<10} {'Total Sales':<15} {'Avg Sale':<12} {'Payments':<12}")
    print(f"{'-'*80}")

    grand_total = 0
    for cashier in summary:
        print(f"{cashier['cashier_name']:<25} "
              f"{cashier['num_sales']:<10} "
              f"{cashier['num_items_sold']:<10} "
              f"${cashier['total_amount']:<14.2f} "
              f"${cashier['avg_sale_value']:<11.2f} "
              f"${cashier['total_payments']:<11.2f}")
        grand_total += cashier['total_amount']

    print(f"{'-'*80}")
    print(f"{'TOTAL':<25} {'':<10} {'':<10} ${grand_total:<14.2f}")
    print(f"{'='*80}\n")


# =============================================================================
# WRITE
# =============================================================================

def start_shift(station: int, shift_number: int, cashier_id: int,
                date: str, opening_floats: dict) -> dict:
    """Create a new shift. opening_floats: {method: float} or {method: (float, currency)}."""
    now = datetime.now()
    start_time = now.strftime("%H:%M:%S")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO shifts (shift_number, station, cashier_id, date, start_time, created_at)
        OUTPUT INSERTED.id
        VALUES (?, ?, ?, ?, ?, ?)
    """, (shift_number, station, cashier_id, date, start_time, now))

    shift_id = int(cur.fetchone()[0])

    for method, value in opening_floats.items():
        if isinstance(value, tuple):
            start_float, currency = value
        else:
            start_float, currency = value, "USD"
        cur.execute("""
            INSERT INTO shift_rows (shift_id, method, currency, start_float, income, counted)
            VALUES (?, ?, ?, ?, 0, 0)
        """, (shift_id, method, currency, float(start_float)))

    conn.commit()
    conn.close()
    log.info(f"Shift {shift_id} started with methods: {list(opening_floats.keys())}")
    return get_shift_by_id(shift_id)


def end_shift(shift_id: int, counted_values: dict,
              door_counter: int = 0, customers: int = 0) -> dict | None:
    """Close shift and save counted values.
    counted_values can be {(method, currency): amount} or {method: amount}.
    """
    end_time = datetime.now()

    conn = get_connection()
    cur = conn.cursor()

    try:
        for key, counted in counted_values.items():
            if isinstance(key, tuple):
                method, currency = key
                log.info(f"end_shift {shift_id}: Saving counted for {method} ({currency}) = {float(counted)}")
                cur.execute("""
                    UPDATE shift_rows 
                    SET counted = ?
                    WHERE shift_id = ? AND method = ? AND currency = ?
                """, (float(counted), shift_id, method, currency))
            else:
                method = key
                log.info(f"end_shift {shift_id}: Saving counted for {method} = {float(counted)}")
                cur.execute("""
                    UPDATE shift_rows 
                    SET counted = ?
                    WHERE shift_id = ? AND method = ?
                """, (float(counted), shift_id, method))

        cur.execute("""
            UPDATE shifts
            SET end_time = ?, door_counter = ?, customers = ?
            WHERE id = ?
        """, (end_time, door_counter, customers, shift_id))

        conn.commit()
        log.info(f"end_shift {shift_id}: closed successfully at {end_time}")

        try:
            income_written = refresh_income(shift_id)
            log.info(f"end_shift {shift_id}: final income refresh -> {income_written}")
        except Exception as e:
            log.error(f"end_shift {shift_id}: final income refresh failed: {e}")

    except Exception as e:
        conn.rollback()
        log.error(f"end_shift {shift_id}: failed - {e}")
        conn.close()
        raise
    finally:
        conn.close()

    return get_shift_by_id(shift_id)


def save_shift_floats(shift_id: int, opening_floats: dict):
    """Update opening floats mid-shift."""
    conn = get_connection()
    cur = conn.cursor()
    for method, start_float in opening_floats.items():
        cur.execute("""
            UPDATE shift_rows
            SET start_float = ?
            WHERE shift_id = ? AND method = ?
        """, (float(start_float), shift_id, method))
    conn.commit()
    conn.close()


# =============================================================================
# MIGRATION
# =============================================================================

def migrate():
    """Run database migrations for shifts and reconciliations."""
    conn = get_connection()
    cur = conn.cursor()

    # ── shifts table ──────────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'shifts')
        CREATE TABLE shifts (
            id           INT           IDENTITY(1,1) PRIMARY KEY,
            shift_number INT           NOT NULL DEFAULT 1,
            station      INT           NOT NULL DEFAULT 1,
            cashier_id   INT           NULL,
            date         NVARCHAR(20)  NOT NULL,
            start_time   NVARCHAR(20)  NOT NULL,
            end_time     DATETIME2     NULL,
            door_counter INT           NOT NULL DEFAULT 0,
            customers    INT           NOT NULL DEFAULT 0,
            notes        NVARCHAR(MAX) NOT NULL DEFAULT '',
            created_at   DATETIME2     NOT NULL DEFAULT SYSDATETIME()
        )
    """)

    # ── shift_rows table (includes currency) ──────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'shift_rows')
        CREATE TABLE shift_rows (
            id           INT           IDENTITY(1,1) PRIMARY KEY,
            shift_id     INT           NOT NULL REFERENCES shifts(id) ON DELETE CASCADE,
            method       NVARCHAR(50)  NOT NULL,
            currency     NVARCHAR(10)  NOT NULL DEFAULT 'USD',
            start_float  DECIMAL(12,2) NOT NULL DEFAULT 0,
            income       DECIMAL(12,2) NOT NULL DEFAULT 0,
            counted      DECIMAL(12,2) NOT NULL DEFAULT 0
        )
    """)

    # ── ADD currency column to existing shift_rows if missing ─────────────────
    cur.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM sys.columns
            WHERE object_id = OBJECT_ID('shift_rows') AND name = 'currency'
        )
        ALTER TABLE shift_rows ADD currency NVARCHAR(10) NOT NULL DEFAULT 'USD'
    """)

    # ── shift_reconciliations table ───────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'shift_reconciliations')
        CREATE TABLE shift_reconciliations (
            id                   INT           IDENTITY(1,1) PRIMARY KEY,
            shift_id             INT           NOT NULL,
            shift_number         INT           NOT NULL,
            shift_date           NVARCHAR(20)  NOT NULL,
            start_time           NVARCHAR(20)  NOT NULL,
            end_time             NVARCHAR(20)  NOT NULL,
            closing_cashier_id   INT           NULL,
            closing_cashier_name NVARCHAR(100) NULL,
            total_expected       DECIMAL(12,2) NOT NULL DEFAULT 0,
            total_counted        DECIMAL(12,2) NOT NULL DEFAULT 0,
            total_variance       DECIMAL(12,2) NOT NULL DEFAULT 0,
            reconciliation_json  NVARCHAR(MAX) NOT NULL,
            printed_at           DATETIME2     NULL,
            created_at           DATETIME2     NOT NULL DEFAULT SYSDATETIME()
        )
    """)

    conn.commit()
    conn.close()
    print("✅ Database migration completed successfully")


# =============================================================================
# INTERNAL HELPERS
# =============================================================================

def _get_shift_rows(shift_id: int, cur) -> list[dict]:
    cur.execute("""
        SELECT id, shift_id, method, currency, start_float, income, counted
        FROM shift_rows
        WHERE shift_id = ?
        ORDER BY 
            CASE WHEN method = 'ON ACCOUNT' THEN 999 ELSE 0 END,
            id
    """, (shift_id,))
    rows = fetchall_dicts(cur)
    for r in rows:
        start = float(r["start_float"])
        income = float(r["income"])
        counted = float(r["counted"])
        total = start + income
        r["start_float"] = start
        r["income"] = income
        r["counted"] = counted
        r["total"] = total
        r["currency"] = r.get("currency", "USD") or "USD"

        if r["method"].upper() == "ON ACCOUNT":
            r["counted"] = 0.0
            r["variance"] = -total
        else:
            r["variance"] = counted - total
    return rows


def _get_cashier_sales_for_shift(shift_id: int, cur) -> list[dict]:
    """Internal version that uses existing cursor."""
    cur.execute("""
        SELECT created_at, end_time, cashier_id 
        FROM shifts 
        WHERE id = ?
    """, (shift_id,))

    shift_row = cur.fetchone()
    if not shift_row:
        return []

    start_time = shift_row[0]
    end_time = shift_row[1] if shift_row[1] else datetime.now()

    cur.execute("""
        SELECT 
            s.id as sale_id,
            s.invoice_no,
            s.invoice_date,
            s.created_at,
            s.cashier_id,
            COALESCE(u.full_name, u.username, s.cashier_name, 'Unknown Cashier') as cashier_name,
            s.total,
            s.subtotal,
            s.total_vat,
            s.discount_amount,
            s.method as sale_method,
            s.company_name,
            s.customer_name,
            s.synced,
            si.id as item_id,
            si.part_no,
            si.product_name,
            si.qty,
            si.price,
            si.discount as item_discount,
            si.total as item_total,
            si.tax_rate,
            si.tax_amount,
            si.tax_type,
            pe.mode_of_payment,
            pe.paid_amount,
            pe.payment_type
        FROM sales s
        LEFT JOIN sale_items si ON si.sale_id = s.id
        LEFT JOIN payment_entries pe ON pe.sale_id = s.id AND pe.payment_type = 'Receive'
        LEFT JOIN users u ON u.id = s.cashier_id
        WHERE s.created_at >= ? AND s.created_at <= ?
        ORDER BY s.created_at DESC, s.id, si.id
    """, (start_time, end_time))

    rows = fetchall_dicts(cur)

    result = {}
    for row in rows:
        cashier_name = row['cashier_name'] or 'Unknown Cashier'
        if not cashier_name.strip() or cashier_name.strip() == 'Cashier':
            cashier_name = f"Cashier #{row['cashier_id']}" if row['cashier_id'] else 'Unknown Cashier'
        cashier_key = f"{row['cashier_id']}_{cashier_name}"
        if cashier_key not in result:
            result[cashier_key] = {
                'cashier_id': row['cashier_id'],
                'cashier_name': cashier_name,
                'sales': [],
                'totals': {
                    'total_sales': 0.0,
                    'total_items': 0,
                    'total_vat': 0.0,
                    'total_discount': 0.0,
                    'total_payments': 0.0,
                    'payment_methods': {}
                }
            }

        sale_exists = False
        for existing_sale in result[cashier_key]['sales']:
            if existing_sale['sale_id'] == row['sale_id']:
                sale_exists = True
                if row['mode_of_payment'] and row['mode_of_payment'] not in existing_sale['payment_methods']:
                    existing_sale['payment_methods'].append(row['mode_of_payment'])
                    paid = float(row['paid_amount'] or 0)
                    existing_sale['payment_amounts'].append(paid)
                    pmt_key = row['mode_of_payment'].strip().upper()
                    result[cashier_key]['totals']['payment_methods'][pmt_key] = (
                        result[cashier_key]['totals']['payment_methods'].get(pmt_key, 0.0) + paid
                    )
                if row['item_id']:
                    existing_sale['items'].append({
                        'part_no': row['part_no'],
                        'product_name': row['product_name'],
                        'qty': float(row['qty']) if row['qty'] else 0,
                        'price': float(row['price']) if row['price'] else 0,
                        'discount': float(row['item_discount']) if row['item_discount'] else 0,
                        'total': float(row['item_total']) if row['item_total'] else 0,
                        'tax_rate': float(row['tax_rate']) if row['tax_rate'] else 0,
                        'tax_amount': float(row['tax_amount']) if row['tax_amount'] else 0
                    })
                break

        if not sale_exists and row['sale_id']:
            sale_record = {
                'sale_id': row['sale_id'],
                'invoice_no': row['invoice_no'],
                'invoice_date': row['invoice_date'],
                'created_at': row['created_at'],
                'total': float(row['total']) if row['total'] else 0,
                'subtotal': float(row['subtotal']) if row['subtotal'] else 0,
                'total_vat': float(row['total_vat']) if row['total_vat'] else 0,
                'discount_amount': float(row['discount_amount']) if row['discount_amount'] else 0,
                'sale_method': row['sale_method'],
                'customer_name': row['customer_name'],
                'company_name': row['company_name'],
                'synced': row['synced'],
                'payment_methods': [],
                'payment_amounts': [],
                'items': []
            }

            if row['mode_of_payment']:
                paid = float(row['paid_amount'] or 0)
                sale_record['payment_methods'].append(row['mode_of_payment'])
                sale_record['payment_amounts'].append(paid)
                pmt_key = row['mode_of_payment'].strip().upper()
                result[cashier_key]['totals']['payment_methods'][pmt_key] = (
                    result[cashier_key]['totals']['payment_methods'].get(pmt_key, 0.0) + paid
                )

            if row['item_id']:
                sale_record['items'].append({
                    'part_no': row['part_no'],
                    'product_name': row['product_name'],
                    'qty': float(row['qty']) if row['qty'] else 0,
                    'price': float(row['price']) if row['price'] else 0,
                    'discount': float(row['item_discount']) if row['item_discount'] else 0,
                    'total': float(row['item_total']) if row['item_total'] else 0,
                    'tax_rate': float(row['tax_rate']) if row['tax_rate'] else 0,
                    'tax_amount': float(row['tax_amount']) if row['tax_amount'] else 0
                })

            result[cashier_key]['sales'].append(sale_record)
            result[cashier_key]['totals']['total_sales'] += sale_record['total']
            result[cashier_key]['totals']['total_items'] += len(sale_record['items'])
            result[cashier_key]['totals']['total_vat'] += sale_record['total_vat']
            result[cashier_key]['totals']['total_discount'] += sale_record['discount_amount']

    return list(result.values())


def get_shift_by_id(shift_id: int) -> dict | None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT s.id, s.shift_number, s.station, s.cashier_id, s.date,
               s.created_at, s.end_time, s.door_counter, s.customers, s.notes,
               COALESCE(u.username, '') AS username,
               COALESCE(u.full_name, u.username, '') AS cashier_fullname
        FROM shifts s
        LEFT JOIN users u ON u.id = s.cashier_id
        WHERE s.id = ?
    """, (shift_id,))
    row = fetchone_dict(cur)
    if not row:
        conn.close()
        return None
    row["rows"] = _get_shift_rows(shift_id, cur)
    row["is_open"] = row["end_time"] is None
    row["cashier_sales"] = _get_cashier_sales_for_shift(shift_id, cur)
    conn.close()
    return row


def get_shift_reports(date_from=None, date_to=None) -> list[dict]:
    conn = get_connection()
    cur = conn.cursor()
    query = """
        SELECT s.id, s.shift_number as shift_no, s.created_at,
               u.username as cashier_name,
               (SELECT SUM(start_float + income) FROM shift_rows WHERE shift_id = s.id) as expected_amount,
               (SELECT SUM(counted) FROM shift_rows WHERE shift_id = s.id) as actual_amount
        FROM shifts s
        LEFT JOIN users u ON u.id = s.cashier_id
    """
    params = []
    if date_from and date_to:
        query += " WHERE CAST(s.created_at AS DATE) BETWEEN ? AND ?"
        params = [date_from, date_to]

    query += " ORDER BY s.id DESC"
    cur.execute(query, params)
    rows = fetchall_dicts(cur)
    for r in rows:
        r['variance'] = float(r['actual_amount'] or 0) - float(r['expected_amount'] or 0)
    conn.close()
    return rows


def diagnose_income(shift_id: int = None):
    """Diagnostic function to debug income calculation."""
    conn = get_connection()
    cur = conn.cursor()

    print("\n" + "="*60)
    print("SHIFT INCOME DIAGNOSTIC")
    print("="*60)

    if shift_id is None:
        active = get_active_shift()
        if not active:
            print("No active shift found. Please provide shift_id parameter.")
            conn.close()
            return
        shift_id = active['id']
        print(f"\n[1] Diagnosing Active Shift: #{active.get('shift_number')}")
    else:
        shift = get_shift_by_id(shift_id)
        if not shift:
            print(f"Shift {shift_id} not found")
            conn.close()
            return
        print(f"\n[1] Diagnosing Shift: #{shift.get('shift_number')}")

    cur.execute("SELECT created_at, end_time FROM shifts WHERE id = ?", (shift_id,))
    row = cur.fetchone()
    shift_start = row[0]
    shift_end = row[1] if row[1] else datetime.now()
    print(f"    Shift period: {shift_start} to {shift_end}")

    print(f"\n[2] Payment Entries during shift period:")
    cur.execute("""
        SELECT 
            pe.mode_of_payment,
            COUNT(*) as payment_count,
            SUM(pe.paid_amount) as total_amount
        FROM payment_entries pe
        INNER JOIN sales s ON s.id = pe.sale_id
        WHERE s.created_at >= ? AND s.created_at <= ?
          AND pe.payment_type = 'Receive'
        GROUP BY pe.mode_of_payment
    """, (shift_start, shift_end))

    rows = cur.fetchall()
    if rows:
        for method, count, total in rows:
            print(f"    {method}: {count} payments, ${total:.2f}")
    else:
        print("    No payment entries found")

    print(f"\n[3] Shift rows (expected income):")
    cur.execute("""
        SELECT method, currency, start_float, income, counted
        FROM shift_rows
        WHERE shift_id = ?
    """, (shift_id,))

    rows = cur.fetchall()
    if rows:
        for method, currency, start_float, income, counted in rows:
            total = start_float + income
            variance = counted - total
            print(f"    {method} ({currency}): start_float=${start_float:.2f}, income=${income:.2f}, total=${total:.2f}, counted=${counted:.2f}, variance=${variance:.2f}")
    else:
        print("    No shift rows found")

    print(f"\n[4] Cashier Sales Breakdown:")
    cashier_sales = get_cashier_sales_for_shift(shift_id)
    for cashier in cashier_sales:
        print(f"    {cashier['cashier_name']}: ${cashier['totals']['total_sales']:.2f} ({cashier['totals']['total_items']} items)")
        if cashier['totals']['payment_methods']:
            for method, amount in cashier['totals']['payment_methods'].items():
                print(f"      - {method}: ${amount:.2f}")

    conn.close()
    print("\n" + "="*60)


def debug_payment_entries(shift_id: int):
    """Debug function specifically for payment_entries."""
    conn = get_connection()
    cur = conn.cursor()

    print(f"\n=== Payment Entries Debug for Shift {shift_id} ===")

    cur.execute("SELECT created_at, end_time FROM shifts WHERE id = ?", (shift_id,))
    row = cur.fetchone()
    if not row:
        print(f"Shift {shift_id} not found")
        conn.close()
        return

    shift_start = row[0]
    shift_end = row[1] if row[1] else datetime.now()
    print(f"Shift period: {shift_start} to {shift_end}\n")

    cur.execute("""
        SELECT 
            s.invoice_no,
            s.created_at,
            s.cashier_name,
            pe.mode_of_payment,
            pe.paid_amount,
            pe.payment_type,
            pe.sale_id
        FROM payment_entries pe
        LEFT JOIN sales s ON s.id = pe.sale_id
        WHERE (s.created_at >= ? AND s.created_at <= ?) OR (pe.created_at >= ? AND pe.created_at <= ?)
        ORDER BY s.created_at DESC
    """, (shift_start, shift_end, shift_start, shift_end))

    rows = cur.fetchall()
    if rows:
        print(f"{'Invoice No':<15} {'Cashier':<20} {'Created At':<25} {'Method':<15} {'Amount':<10} {'Type':<10}")
        print("-" * 100)
        for invoice_no, created_at, cashier_name, method, amount, payment_type, sale_id in rows:
            inv = invoice_no if invoice_no else f"ID:{sale_id}"
            cashier = cashier_name or 'Unknown'
            print(f"{inv:<15} {cashier:<20} {str(created_at):<25} {method:<15} ${amount:<9.2f} {payment_type:<10}")
    else:
        print("No payment_entries found for this shift period")

    conn.close()


# =============================================================================
# SAVE RECONCILIATION TO DATABASE
# =============================================================================

def _clean_for_json(obj):
    """Recursively clean objects for JSON serialization."""
    if isinstance(obj, datetime):
        return obj.strftime("%Y-%m-%d %H:%M:%S")
    if hasattr(obj, 'strftime'):
        return obj.strftime("%Y-%m-%d")
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _clean_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean_for_json(item) for item in obj]
    return obj


def save_shift_reconciliation(shift_id: int, reconciliation_data: dict) -> int:
    """Save the complete shift reconciliation data to database. Returns the reconciliation ID."""
    conn = get_connection()
    cur = conn.cursor()

    try:
        clean_data = _clean_for_json(reconciliation_data)
        reconciliation_json = json.dumps(clean_data, indent=2)

        shift_number = reconciliation_data.get('shift_number', 0)
        shift_date = reconciliation_data.get('date', datetime.now().strftime("%Y-%m-%d"))
        start_time = reconciliation_data.get('start_time', '—')
        end_time = reconciliation_data.get('end_time', datetime.now().strftime("%H:%M:%S"))
        closing_cashier_id = reconciliation_data.get('closing_cashier_id')

        if closing_cashier_id is None or closing_cashier_id == '':
            closing_cashier_id = None
        else:
            try:
                closing_cashier_id = int(closing_cashier_id)
            except (ValueError, TypeError):
                closing_cashier_id = None

        closing_cashier_name = reconciliation_data.get('closing_cashier_name', '')
        total_expected = float(reconciliation_data.get('total_expected', 0))
        total_counted = float(reconciliation_data.get('total_counted', 0))
        total_variance = float(reconciliation_data.get('total_variance', total_counted - total_expected))

        cur.execute("""
            INSERT INTO shift_reconciliations 
            (shift_id, shift_number, shift_date, start_time, end_time, 
             closing_cashier_id, closing_cashier_name, total_expected, total_counted, 
             total_variance, reconciliation_json, printed_at, created_at)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, GETDATE())
        """, (
            shift_id, shift_number, shift_date, start_time, end_time,
            closing_cashier_id, closing_cashier_name, total_expected, total_counted,
            total_variance, reconciliation_json, None
        ))

        row = cur.fetchone()
        if row and row[0]:
            reconciliation_id = int(row[0])
        else:
            cur.execute("SELECT SCOPE_IDENTITY()")
            reconciliation_id = int(cur.fetchone()[0])

        conn.commit()
        log.info(f"Saved reconciliation {reconciliation_id} for shift {shift_id}")
        return reconciliation_id

    except Exception as e:
        log.error(f"Failed to save reconciliation: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return 0
    finally:
        conn.close()


def get_shift_reconciliation(reconciliation_id: int) -> dict | None:
    """Get a specific reconciliation by ID."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM shift_reconciliations WHERE id = ?", (reconciliation_id,))
        row = fetchone_dict(cur)
        if row:
            try:
                row['reconciliation_data'] = json.loads(row['reconciliation_json'])
            except:
                row['reconciliation_data'] = {}
        return row
    except Exception as e:
        log.error(f"Failed to get reconciliation: {e}")
        return None
    finally:
        conn.close()


def get_shift_reconciliations_by_shift(shift_id: int) -> list[dict]:
    """Get all reconciliations for a specific shift."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT * FROM shift_reconciliations 
            WHERE shift_id = ?
            ORDER BY created_at DESC
        """, (shift_id,))
        rows = fetchall_dicts(cur)
        for row in rows:
            try:
                row['reconciliation_data'] = json.loads(row['reconciliation_json'])
            except:
                row['reconciliation_data'] = {}
        return rows
    except Exception as e:
        log.error(f"Failed to get reconciliations: {e}")
        return []
    finally:
        conn.close()


def get_all_shift_reconciliations(limit: int = 100, offset: int = 0) -> list[dict]:
    """Get all shift reconciliations with pagination."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT * FROM shift_reconciliations 
            ORDER BY created_at DESC
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """, (offset, limit))
        rows = fetchall_dicts(cur)
        for row in rows:
            try:
                row['reconciliation_data'] = json.loads(row['reconciliation_json'])
            except:
                row['reconciliation_data'] = {}
        return rows
    except Exception as e:
        log.error(f"Failed to get reconciliations: {e}")
        return []
    finally:
        conn.close()


def update_reconciliation_print_status(reconciliation_id: int, printed: bool = True) -> bool:
    """Update the print status of a reconciliation."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE shift_reconciliations 
            SET printed_at = ?
            WHERE id = ?
        """, (datetime.now() if printed else None, reconciliation_id))
        conn.commit()
        return True
    except Exception as e:
        log.error(f"Failed to update print status: {e}")
        return False
    finally:
        conn.close()