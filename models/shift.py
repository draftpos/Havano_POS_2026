# =============================================================================
# models/shift.py  —  SQL Server version
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


def get_all_shifts() -> list[dict]:
    """Return all shifts newest first."""
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT s.id, s.shift_number, s.station, s.cashier_id, s.date,
               s.start_time, s.end_time, s.door_counter, s.customers, s.notes,
               COALESCE(u.username, '') AS username
        FROM shifts s
        LEFT JOIN users u ON u.id = s.cashier_id
        ORDER BY s.id DESC
    """)
    rows = fetchall_dicts(cur)
    conn.close()
    for r in rows:
        r["is_open"] = r["end_time"] is None
    return rows


def get_shift_rows(shift_id: int) -> list[dict]:
    conn = get_connection()
    cur  = conn.cursor()
    result = _get_shift_rows(shift_id, cur)
    conn.close()
    return result


def get_next_shift_number() -> int:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("SELECT COALESCE(MAX(shift_number), 0) FROM shifts")
    row = cur.fetchone()
    conn.close()
    return int(row[0]) + 1


def get_income_by_method(date_str: str = None) -> dict:
    """Return sales income grouped by payment method for a given date."""
    METHOD_MAP = {
        "Cash":   "CASH",
        "Card":   "C / CARD",
        "Mobile": "EFTPOS",
        "Credit": "CHECK",
    }
    conn = get_connection()
    cur  = conn.cursor()
    if date_str:
        cur.execute("""
            SELECT method, COALESCE(SUM(total), 0)
            FROM sales
            WHERE CAST(created_at AS DATE) = ?
            GROUP BY method
        """, (date_str,))
    else:
        cur.execute("""
            SELECT method, COALESCE(SUM(total), 0)
            FROM sales
            WHERE CAST(created_at AS DATE) = CAST(GETDATE() AS DATE)
            GROUP BY method
        """)
    rows = cur.fetchall()
    conn.close()
    result = {}
    for method, total in rows:
        mapped = METHOD_MAP.get(method, method.upper())
        result[mapped] = float(total)
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


def save_shift_floats(shift_id: int, opening_floats: dict) -> bool:
    conn = get_connection()
    cur  = conn.cursor()
    for method, start_float in opening_floats.items():
        cur.execute("""
            UPDATE shift_rows SET start_float = ?
            WHERE shift_id = ? AND method = ?
        """, (float(start_float), shift_id, method))
    conn.commit()
    conn.close()
    return True


def refresh_income(shift_id: int) -> dict:
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


def delete_shift(shift_id: int) -> bool:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("DELETE FROM shifts WHERE id = ?", (shift_id,))
    affected = cur.rowcount
    conn.commit()
    conn.close()
    return affected > 0


# =============================================================================
# MIGRATION  —  run once to create tables in SQL Server
# =============================================================================

def migrate():
    """Create shifts and shift_rows tables if they don't exist."""
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'shifts'
        )
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

    cur.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'shift_rows'
        )
        CREATE TABLE shift_rows (
            id           INT           IDENTITY(1,1) PRIMARY KEY,
            shift_id     INT           NOT NULL
                             REFERENCES shifts(id) ON DELETE CASCADE,
            method       NVARCHAR(50)  NOT NULL,
            start_float  DECIMAL(12,2) NOT NULL DEFAULT 0,
            income       DECIMAL(12,2) NOT NULL DEFAULT 0,
            counted      DECIMAL(12,2) NOT NULL DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()
    print("[shift] ✅  Tables ready.")


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
        r["variance"]    = total - counted
    return rows