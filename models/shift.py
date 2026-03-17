# =============================================================================
# models/shift.py  —  SQL Server version (Updated for Variance & Account Payments)
# =============================================================================

from database.db import get_connection, fetchall_dicts, fetchone_dict

# =============================================================================
# READ
# =============================================================================

def get_active_shift() -> dict | None:
    """Return the currently open (not ended) shift, or None."""
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT TOP 1
               s.id, s.shift_number, s.station, s.cashier_id, s.date,
               s.start_time, s.end_time, s.door_counter, s.customers, s.notes,
               COALESCE(u.username, '') AS username
        FROM shifts s
        LEFT JOIN users u ON u.id = s.cashier_id
        WHERE s.end_time IS NULL
        ORDER BY s.id DESC
    """)
    row = fetchone_dict(cur)
    if not row:
        conn.close()
        return None
    row["rows"]    = _get_shift_rows(row["id"], cur)
    row["is_open"] = True
    conn.close()
    return row


def get_last_shift() -> dict | None:
    """Return the most recent shift (open or closed)."""
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT TOP 1
               s.id, s.shift_number, s.station, s.cashier_id, s.date,
               s.start_time, s.end_time, s.door_counter, s.customers, s.notes,
               COALESCE(u.username, '') AS username
        FROM shifts s
        LEFT JOIN users u ON u.id = s.cashier_id
        ORDER BY s.id DESC
    """)
    row = fetchone_dict(cur)
    if not row:
        conn.close()
        return None
    row["rows"]    = _get_shift_rows(row["id"], cur)
    row["is_open"] = row["end_time"] is None
    conn.close()
    return row


def get_next_shift_number() -> int:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("SELECT COALESCE(MAX(shift_number), 0) FROM shifts")
    row = cur.fetchone()
    conn.close()
    return int(row[0]) + 1


def get_income_by_method(date_str: str = None) -> dict:
    """
    Requirement 4 & 3: Returns combined income (Sales + Account Payments)
    grouped by payment method for the shift report.
    """
    METHOD_MAP = {
        "Cash":   "CASH",
        "Card":   "C / CARD",
        "Mobile": "EFTPOS",
        "Credit": "CHECK",
    }
    conn = get_connection()
    cur  = conn.cursor()
    
    # 1. Query Sales Totals
    sales_query = """
        SELECT method, COALESCE(SUM(total), 0)
        FROM sales
        WHERE CAST(created_at AS DATE) = {}
        GROUP BY method
    """
    date_filter = "?" if date_str else "CAST(GETDATE() AS DATE)"
    params = (date_str,) if date_str else ()
    
    cur.execute(sales_query.format(date_filter), params)
    sales_rows = cur.fetchall()

    # 2. Query Account Payment Totals (Requirement 3)
    payments_query = """
        SELECT method, COALESCE(SUM(amount), 0)
        FROM customer_payments
        WHERE CAST(created_at AS DATE) = {}
        GROUP BY method
    """
    cur.execute(payments_query.format(date_filter), params)
    payment_rows = cur.fetchall()
    conn.close()

    result = {}
    # Combine Sales
    for method, total in sales_rows:
        mapped = METHOD_MAP.get(method, method.upper())
        result[mapped] = result.get(mapped, 0.0) + float(total)
    
    # Combine Account Payments
    for method, total in payment_rows:
        mapped = METHOD_MAP.get(method, method.upper())
        result[mapped] = result.get(mapped, 0.0) + float(total)

    return result


# =============================================================================
# WRITE
# =============================================================================

def start_shift(station: int, shift_number: int, cashier_id: int,
                date: str, opening_floats: dict) -> dict:
    from datetime import datetime
    start_time = datetime.now().strftime("%H:%M:%S")
    income_by_method = get_income_by_method()

    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        INSERT INTO shifts (shift_number, station, cashier_id, date, start_time)
        OUTPUT INSERTED.id
        VALUES (?, ?, ?, ?, ?)
    """, (shift_number, station, cashier_id, date, start_time))

    shift_id = int(cur.fetchone()[0])

    for method, start_float in opening_floats.items():
        income = income_by_method.get(method, 0.0)
        cur.execute("""
            INSERT INTO shift_rows (shift_id, method, start_float, income, counted)
            VALUES (?, ?, ?, ?, 0)
        """, (shift_id, method, float(start_float), income))

    conn.commit()
    conn.close()
    return get_shift_by_id(shift_id)


def end_shift(shift_id: int, counted_values: dict,
              door_counter: int = 0, customers: int = 0) -> dict | None:
    """Requirement 4: Finalizes the shift and saves actual counted amounts."""
    from datetime import datetime
    end_time = datetime.now().strftime("%H:%M:%S")

    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        UPDATE shifts
        SET end_time = ?, door_counter = ?, customers = ?
        WHERE id = ?
    """, (end_time, door_counter, customers, shift_id))

    for method, counted in counted_values.items():
        cur.execute("""
            UPDATE shift_rows SET counted = ?
            WHERE shift_id = ? AND method = ?
        """, (float(counted), shift_id, method))

    conn.commit()
    conn.close()
    return get_shift_by_id(shift_id)


def refresh_income(shift_id: int) -> dict:
    """Updates the expected income in the shift rows based on latest DB records."""
    income_by_method = get_income_by_method()
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("SELECT method FROM shift_rows WHERE shift_id = ?", (shift_id,))
    methods = [r[0] for r in cur.fetchall()]
    for method in methods:
        income = income_by_method.get(method, 0.0)
        cur.execute("""
            UPDATE shift_rows SET income = ?
            WHERE shift_id = ? AND method = ?
        """, (income, shift_id, method))
    conn.commit()
    conn.close()
    return income_by_method


# =============================================================================
# MIGRATION
# =============================================================================

def migrate():
    conn = get_connection()
    cur  = conn.cursor()
    # Master Shifts Table
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'shifts')
        CREATE TABLE shifts (
            id           INT           IDENTITY(1,1) PRIMARY KEY,
            shift_number INT           NOT NULL DEFAULT 1,
            station      INT           NOT NULL DEFAULT 1,
            cashier_id   INT           NULL,
            date         NVARCHAR(20)  NOT NULL,
            start_time   NVARCHAR(20)  NOT NULL,
            end_time     NVARCHAR(20)  NULL,
            door_counter INT           NOT NULL DEFAULT 0,
            customers    INT           NOT NULL DEFAULT 0,
            notes        NVARCHAR(MAX) NOT NULL DEFAULT '',
            created_at   DATETIME2     NOT NULL DEFAULT SYSDATETIME()
        )
    """)
    # Detail rows per payment method (for Variance calculation)
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'shift_rows')
        CREATE TABLE shift_rows (
            id           INT           IDENTITY(1,1) PRIMARY KEY,
            shift_id     INT           NOT NULL REFERENCES shifts(id) ON DELETE CASCADE,
            method       NVARCHAR(50)  NOT NULL,
            start_float  DECIMAL(12,2) NOT NULL DEFAULT 0,
            income       DECIMAL(12,2) NOT NULL DEFAULT 0,
            counted      DECIMAL(12,2) NOT NULL DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

# =============================================================================
# PRIVATE
# =============================================================================

def _get_shift_rows(shift_id: int, cur) -> list[dict]:
    cur.execute("""
        SELECT id, shift_id, method, start_float, income, counted
        FROM shift_rows
        WHERE shift_id = ?
        ORDER BY id
    """, (shift_id,))
    rows = fetchall_dicts(cur)
    for r in rows:
        start   = float(r["start_float"])
        income  = float(r["income"])
        counted = float(r["counted"])
        total   = start + income
        r["start_float"] = start
        r["income"]      = income
        r["counted"]     = counted
        r["total"]       = total
        r["variance"]    = total - counted  # Calculation for Requirement 4
    return rows

def get_shift_by_id(shift_id: int) -> dict | None:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT s.id, s.shift_number, s.station, s.cashier_id, s.date,
               s.start_time, s.end_time, s.door_counter, s.customers, s.notes,
               COALESCE(u.username, '') AS username
        FROM shifts s
        LEFT JOIN users u ON u.id = s.cashier_id
        WHERE s.id = ?
    """, (shift_id,))
    row = fetchone_dict(cur)
    if not row:
        conn.close()
        return None
    row["rows"]    = _get_shift_rows(shift_id, cur)
    row["is_open"] = row["end_time"] is None
    conn.close()
    return row

def get_shift_reports(date_from=None, date_to=None) -> list[dict]:
    """Retrieves shift history for Requirement 5 (X-Report)."""
    conn = get_connection(); cur = conn.cursor()
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