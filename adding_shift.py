# add_shifts_tables.py
# Run once:  python add_shifts_tables.py

import sqlite3, os, sys

DB_PATH = os.path.join(os.path.dirname(__file__), "pos.db")

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database not found at {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH, timeout=10)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS shifts (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            shift_number   INTEGER NOT NULL DEFAULT 1,
            station        INTEGER NOT NULL DEFAULT 1,
            cashier_id     INTEGER,
            date           TEXT    NOT NULL,
            start_time     TEXT    NOT NULL,
            end_time       TEXT,
            door_counter   INTEGER NOT NULL DEFAULT 0,
            customers      INTEGER NOT NULL DEFAULT 0,
            notes          TEXT    NOT NULL DEFAULT '',
            created_at     TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    """)
    print("✔  shifts table created / verified.")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS shift_rows (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            shift_id     INTEGER NOT NULL REFERENCES shifts(id) ON DELETE CASCADE,
            method       TEXT    NOT NULL,
            start_float  REAL    NOT NULL DEFAULT 0,
            income       REAL    NOT NULL DEFAULT 0,
            counted      REAL    NOT NULL DEFAULT 0
        )
    """)
    print("✔  shift_rows table created / verified.")

    conn.commit()
    conn.close()
    print("\n✅  Done! Run: python main.py")

if __name__ == "__main__":
    migrate()