# database/db.py  —  Dynamic SQL Server connection (Windows or SQL Auth)

import sys
import json
import pyodbc
from pathlib import Path

# =============================================================================
# CONFIG  —  edit these two lines only
# =============================================================================
SERVER = r"."
DATABASE = "havano_posop07978808"
# =============================================================================

def _best_driver() -> str:
    preferred = [
        "ODBC Driver 17 for SQL Server",
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 13 for SQL Server",
        "SQL Server",
    ]
    for d in preferred:
        if d in pyodbc.drivers():
            return d
    raise RuntimeError("No SQL Server ODBC driver found. Download from: https://aka.ms/downloadmsodbcsql")

DRIVER = _best_driver()

def get_app_data_dir() -> Path:
    """
    Returns the writable app_data directory next to the .exe (or next to
    main.py in dev mode). Mirrors the same logic used in main.py so that
    both dev and bundled builds always find sql_settings.json in the right place.
    """
    if hasattr(sys, "_MEIPASS"):
        # Running as a bundled .exe — use the folder that contains the exe
        return Path(sys.executable).parent / "app_data"
    # Dev mode — go two levels up from database/db.py to reach the project root
    return Path(__file__).resolve().parent.parent / "app_data"

_cached_settings = None
_cached_settings_mtime = 0.0

def _load_settings() -> dict:
    defaults = {
        "auth_mode": "windows",
        "server": ".\\SQLEXPRESS",
        "database": "havano_posop07978808",
        "username": "",
        "password": "",
        "system_mode": "saas"
    }
    path = get_app_data_dir() / "sql_settings.json"
    if not path.exists():
        return defaults
    try:
        mtime = path.stat().st_mtime
        global _cached_settings, _cached_settings_mtime
        if _cached_settings is not None and mtime == _cached_settings_mtime:
            return _cached_settings
        data = json.loads(path.read_text(encoding="utf-8")) or {}
        merged = {**defaults, **data}
        _cached_settings = merged
        _cached_settings_mtime = mtime
        return merged
    except Exception:
        try:
            data = json.loads(path.read_text(encoding="utf-8")) or {}
            return {**defaults, **data}
        except Exception:
            return defaults

def is_connection_valid() -> bool:
    """Returns True only if settings file exists AND connection works."""
    path = get_app_data_dir() / "sql_settings.json"
    print(f"[db] is_connection_valid() — checking: {path}")
    if not path.exists():
        print("[db] Settings file not found.")
        return False
    try:
        cfg = _load_settings()
        server_val = cfg.get("server") or ".\\SQLEXPRESS"
        db_val = cfg.get("database") or "havano_posop07978808"
        if cfg.get("auth_mode") == "windows":
            conn_str = (
                f"DRIVER={{{DRIVER}}};"
                f"SERVER={server_val};"
                f"DATABASE={db_val};"
                "Trusted_Connection=yes;"
                "TrustServerCertificate=yes;"
                "Encrypt=no;"
            )
        else:
            conn_str = (
                f"DRIVER={{{DRIVER}}};"
                f"SERVER={server_val};"
                f"DATABASE={db_val};"
                f"UID={cfg.get('username', '')};"
                f"PWD={cfg.get('password', '')};"
                "TrustServerCertificate=yes;"
                "Encrypt=no;"
            )
        conn = pyodbc.connect(conn_str, timeout=4)
        conn.close()
        print("[db] Connection valid.")
        return True
    except Exception as e:
        print(f"[db] Connection failed: {e}")
        return False

import threading
import time

class PooledConnection:
    def __init__(self, conn):
        self._conn = conn
    def cursor(self):
        return self._conn.cursor()
    def commit(self):
        self._conn.commit()
    def rollback(self):
        self._conn.rollback()
    def close(self):
        pass # Ignore close to keep the connection alive in the pool
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

_thread_local = threading.local()

def get_connection() -> pyodbc.Connection:
    now = time.time()
    
    # Return cached thread-local connection if valid
    if hasattr(_thread_local, "conn"):
        last_check = getattr(_thread_local, "last_check", 0.0)
        if now - last_check < 60.0:
            return PooledConnection(_thread_local.conn)
        try:
            # Re-verify idle connection only once every 60s
            c = _thread_local.conn.cursor()
            c.execute("SELECT 1")
            c.fetchone()
            c.close()
            _thread_local.last_check = now
            return PooledConnection(_thread_local.conn)
        except Exception:
            try: _thread_local.conn.close()
            except: pass
            delattr(_thread_local, "conn")

    cfg = _load_settings()
    server_val = cfg.get("server") or ".\\SQLEXPRESS"
    db_val = cfg.get("database") or "havano_posop07978808"

    if cfg.get("auth_mode") == "windows":
        conn_str = (
            f"DRIVER={{{DRIVER}}};"
            f"SERVER={server_val};"
            f"DATABASE={db_val};"
            "Trusted_Connection=yes;"
            "TrustServerCertificate=yes;"
            "Encrypt=no;"
        )
    else:
        conn_str = (
            f"DRIVER={{{DRIVER}}};"
            f"SERVER={server_val};"
            f"DATABASE={db_val};"
            f"UID={cfg.get('username', '')};"
            f"PWD={cfg.get('password', '')};"
            "TrustServerCertificate=yes;"
            "Encrypt=no;"
        )
    
    conn = pyodbc.connect(conn_str)
    _thread_local.conn = conn
    _thread_local.last_check = now
    return PooledConnection(conn)

def get_api_url() -> str:
    """Returns the Frappe API base URL from sql_settings.json."""
    cfg = _load_settings()
    return str(cfg.get("api_url") or "").strip().rstrip("/")

def fetchall_dicts(cursor, sql: str = None, params: tuple = ()) -> list:
    if sql:
        cursor.execute(sql, params)
    if not getattr(cursor, "description", None):
        return []
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]

fetchall_dict = fetchall_dicts

def fetchone_dict(cursor, sql: str = None, params: tuple = ()) -> dict | None:
    if sql:
        cursor.execute(sql, params)
    if not getattr(cursor, "description", None):
        return None
    row = cursor.fetchone()
    if row is None:
        return None
    cols = [d[0] for d in cursor.description]
    return dict(zip(cols, row))