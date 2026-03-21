# database/db.py  —  Dynamic SQL Server connection (Windows or SQL Auth)

import json
import pyodbc
from pathlib import Path

# =============================================================================
# CONFIG  —  edit these two lines only
# =============================================================================
SERVER = r".\SQLEXPRESS"
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

def _load_settings():
    path = Path("app_data/sql_settings.json")
    if not path.exists():
        return {
            "auth_mode": "windows",
            "server": ".",
            "database": "pos_db",
            "username": "",
            "password": ""
        }
    return json.loads(path.read_text(encoding="utf-8"))

def is_connection_valid() -> bool:
    """Returns True only if settings file exists AND connection works"""
    path = Path("app_data/sql_settings.json")
    if not path.exists():
        return False
    try:
        cfg = _load_settings()
        if cfg.get("auth_mode") == "windows":
            conn_str = (
                f"DRIVER={{{DRIVER}}};"
                f"SERVER={cfg['server']};"
                f"DATABASE={cfg['database']};"
                "Trusted_Connection=yes;"
                "TrustServerCertificate=yes;"
            )
        else:
            conn_str = (
                f"DRIVER={{{DRIVER}}};"
                f"SERVER={cfg['server']};"
                f"DATABASE={cfg['database']};"
                f"UID={cfg['username']};"
                f"PWD={cfg['password']};"
                "TrustServerCertificate=yes;"
            )
        conn = pyodbc.connect(conn_str, timeout=4)
        conn.close()
        return True
    except Exception:
        return False

def get_connection() -> pyodbc.Connection:
    cfg = _load_settings()
    if cfg.get("auth_mode") == "windows":
        conn_str = (
            f"DRIVER={{{DRIVER}}};"
            f"SERVER={cfg['server']};"
            f"DATABASE={cfg['database']};"
            "Trusted_Connection=yes;"
            "TrustServerCertificate=yes;"
            "Application Name=POSSystem;"
        )
    else:
        conn_str = (
            f"DRIVER={{{DRIVER}}};"
            f"SERVER={cfg['server']};"
            f"DATABASE={cfg['database']};"
            f"UID={cfg['username']};"
            f"PWD={cfg['password']};"
            "TrustServerCertificate=yes;"
            "Application Name=POSSystem;"
        )
    return pyodbc.connect(conn_str)

def fetchall_dicts(cursor) -> list:
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]

def fetchone_dict(cursor) -> dict | None:
    row = cursor.fetchone()
    if row is None:
        return None
    cols = [d[0] for d in cursor.description]
    return dict(zip(cols, row))