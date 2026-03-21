# models/exchange_rate.py
from database.db import get_connection, fetchone_dict
from datetime import date


def get_rate(from_currency: str, to_currency: str,
             rate_date: str = None) -> float | None:
    """
    Returns the stored exchange rate for a currency pair on a given date.
    Falls back to most recent rate if exact date not found.
    Returns None if no rate exists at all.
    """
    if not rate_date:
        rate_date = date.today().isoformat()

    conn = get_connection(); cur = conn.cursor()

    # Exact date first
    cur.execute("""
        SELECT TOP 1 rate FROM exchange_rates
        WHERE from_currency = ? AND to_currency = ?
          AND rate_date = ?
    """, (from_currency.upper(), to_currency.upper(), rate_date))
    row = cur.fetchone()

    if not row:
        # Most recent available
        cur.execute("""
            SELECT TOP 1 rate FROM exchange_rates
            WHERE from_currency = ? AND to_currency = ?
            ORDER BY rate_date DESC
        """, (from_currency.upper(), to_currency.upper()))
        row = cur.fetchone()

    conn.close()
    return float(row[0]) if row else None


def upsert_rate(from_currency: str, to_currency: str,
                rate: float, rate_date: str = None) -> None:
    if not rate_date:
        rate_date = date.today().isoformat()

    conn = get_connection(); cur = conn.cursor()
    cur.execute("""
        MERGE exchange_rates AS target
        USING (SELECT ? AS from_currency, ? AS to_currency, ? AS rate_date) AS source
            ON target.from_currency = source.from_currency
           AND target.to_currency   = source.to_currency
           AND target.rate_date     = source.rate_date
        WHEN MATCHED THEN
            UPDATE SET rate = ?, updated_at = SYSDATETIME()
        WHEN NOT MATCHED THEN
            INSERT (from_currency, to_currency, rate, rate_date)
            VALUES (?, ?, ?, ?);
    """, (
        from_currency.upper(), to_currency.upper(), rate_date,
        rate,
        from_currency.upper(), to_currency.upper(), rate, rate_date,
    ))
    conn.commit(); conn.close()


def get_all_rates() -> list[dict]:
    conn = get_connection(); cur = conn.cursor()
    cur.execute("""
        SELECT * FROM exchange_rates
        ORDER BY rate_date DESC, from_currency
    """)
    from database.db import fetchall_dicts
    rows = fetchall_dicts(cur); conn.close()
    return rows