# database/db.py  —  SQL Server version (Windows Authentication)

import pyodbc

# =============================================================================
# CONFIG  —  edit these two lines only
# =============================================================================
SERVER   = r".\SQLEXPRESS"
DATABASE = "pos_db"
# =============================================================================

def _best_driver() -> str:
    preferred = [
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "ODBC Driver 13 for SQL Server",
        "SQL Server",
    ]
    for d in preferred:
        if d in pyodbc.drivers():
            return d
    raise RuntimeError("No SQL Server ODBC driver found. Download from: https://aka.ms/downloadmsodbcsql")

DRIVER = _best_driver()

def _conn_str(database: str = "") -> str:
    db_part = f"DATABASE={database};" if database else ""
    return (
        f"DRIVER={{{DRIVER}}};"
        f"SERVER={SERVER};"
        f"{db_part}"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
        "Application Name=POSSystem;"
    )

def get_connection() -> pyodbc.Connection:
    return pyodbc.connect(_conn_str(DATABASE))

def fetchall_dicts(cursor) -> list:
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]

def fetchone_dict(cursor) -> dict | None:
    row = cursor.fetchone()
    if row is None:
        return None
    cols = [d[0] for d in cursor.description]
    return dict(zip(cols, row))