# database/db.py  —  Dynamic SQL Server connection (Windows or SQL Auth)

import sys
import json
import time
import threading
import pyodbc
from pathlib import Path

# =============================================================================
# CONFIG  —  edit these two lines only
# =============================================================================
SERVER = r"."
DATABASE = ""
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
        "database": "",
        "username": "",
        "password": "",
        "system_mode": "saas",
        "api_url": "https://backoffice.havano.pro"
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

TRANSIENT_ERRORS = (
    "08001", "258", "timeout", "login timeout", "08s01", "08s02", "08004",
    "communication link", "connection is closed", "forcibly closed",
    "connection reset", "broken pipe", "no process is on the other end",
    "named pipes provider", "shared memory provider", "tcp provider",
    "semaphore timeout", "hyt00", "hy000", "233", "10054", "10061",
    "4060", "921", "922", "in recovery", "in transition", "cannot open database"
)

def is_connection_valid(status_callback=None, timeout: int = 12, retries: int = 5) -> bool:
    """Returns True only if settings file exists AND connection works.
    Includes retry logic to allow cold SQL Server services / databases to initialize without failing.
    """
    path = get_app_data_dir() / "sql_settings.json"
    print(f"[db] is_connection_valid() — checking: {path}")
    if not path.exists():
        print("[db] Settings file not found.")
        return False
    try:
        cfg = _load_settings()
        server_val = cfg.get("server") or ".\\SQLEXPRESS"
        db_val = str(cfg.get("database") or "").strip()
        if not db_val:
            raise ValueError("No database configured (strict no-fallback policy)")
        if cfg.get("auth_mode") == "windows":
            conn_str = (
                f"DRIVER={{{DRIVER}}};"
                f"SERVER={server_val};"
                f"DATABASE={db_val};"
                "Trusted_Connection=yes;"
                "TrustServerCertificate=yes;"
                "Encrypt=no;"
                "MARS_Connection=yes;"
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
                "MARS_Connection=yes;"
            )
    except Exception as e:
        print(f"[db] Settings read failed: {e}")
        return False

    last_err = None
    for attempt in range(1, retries + 1):
        try:
            if status_callback and attempt > 1:
                status_callback(f"Connecting to database (attempt {attempt}/{retries})...")
            conn = pyodbc.connect(conn_str, timeout=timeout)
            conn.close()
            print(f"[db] Connection valid (attempt {attempt}).")
            return True
        except Exception as e:
            last_err = e
            err_msg = str(e).lower()
            is_transient = any(k in err_msg for k in TRANSIENT_ERRORS)
            if attempt < retries and is_transient:
                wait_sec = 2.0
                print(f"[db] Attempt {attempt} failed ({e}). Retrying in {wait_sec}s...")
                if status_callback:
                    status_callback(f"Waiting for database server to respond (attempt {attempt}/{retries})...")
                time.sleep(wait_sec)
            elif attempt < retries:
                # Even if not explicitly transient, allow a quick retry during cold wake-ups
                time.sleep(1.0)
            else:
                break

    print(f"[db] Connection failed: {last_err}")
    return False

def reset_connection():
    """Drops and closes the current thread's cached pooled connection."""
    if hasattr(_thread_local, "conn"):
        try:
            _thread_local.conn.close()
        except Exception:
            pass
        try:
            delattr(_thread_local, "conn")
        except AttributeError:
            pass

class PooledCursor:
    def __init__(self, raw_cursor, parent_conn=None):
        self._cursor = raw_cursor
        self._parent_conn = parent_conn

    def execute(self, sql, params=()):
        try:
            if params:
                return self._cursor.execute(sql, params)
            return self._cursor.execute(sql)
        except (pyodbc.Error, Exception) as e:
            err_msg = str(e).lower()
            if any(k in err_msg for k in TRANSIENT_ERRORS):
                print(f"[db] PooledCursor detected connection drop ({e}). Re-establishing connection...")
                reset_connection()
                last_rec_err = e
                for rec_attempt in range(1, 4):
                    try:
                        new_conn = _create_raw_connection()
                        _thread_local.conn = new_conn
                        _thread_local.last_check = time.time()
                        self._cursor = new_conn.cursor()
                        if self._parent_conn:
                            self._parent_conn._conn = new_conn
                        if params:
                            return self._cursor.execute(sql, params)
                        return self._cursor.execute(sql)
                    except Exception as rec_err:
                        last_rec_err = rec_err
                        time.sleep(1.0)
                raise last_rec_err
            raise

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def fetchmany(self, size=None):
        return self._cursor.fetchmany(size) if size else self._cursor.fetchmany()

    @property
    def description(self):
        return self._cursor.description

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def close(self):
        try:
            self._cursor.close()
        except Exception:
            pass

    def __getattr__(self, name):
        return getattr(self._cursor, name)

    def __setattr__(self, name, value):
        if name in ("_cursor", "_parent_conn"):
            super().__setattr__(name, value)
        elif name == "timeout":
            if self._parent_conn and hasattr(self._parent_conn, "_conn"):
                try:
                    self._parent_conn._conn.timeout = value
                except Exception:
                    pass
            try:
                setattr(self._cursor, name, value)
            except Exception:
                pass
        else:
            try:
                setattr(self._cursor, name, value)
            except Exception:
                super().__setattr__(name, value)


class PooledConnection:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        try:
            raw_cur = self._conn.cursor()
            return PooledCursor(raw_cur, parent_conn=self)
        except Exception:
            reset_connection()
            new_conn = _create_raw_connection()
            _thread_local.conn = new_conn
            _thread_local.last_check = time.time()
            self._conn = new_conn
            return PooledCursor(new_conn.cursor(), parent_conn=self)

    def commit(self):
        try:
            self._conn.commit()
        except Exception:
            reset_connection()
            raise

    def rollback(self):
        try:
            self._conn.rollback()
        except Exception:
            reset_connection()
            raise

    def close(self):
        pass # Ignore close to keep the connection alive in the pool

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def __getattr__(self, name):
        return getattr(self._conn, name)

_thread_local = threading.local()

def _create_raw_connection() -> pyodbc.Connection:
    cfg = _load_settings()
    server_val = cfg.get("server") or ".\\SQLEXPRESS"
    db_val = str(cfg.get("database") or "").strip()
    if not db_val:
        raise ValueError("Database configuration is missing. Cannot fall back to a default database.")

    if cfg.get("auth_mode") == "windows":
        conn_str = (
            f"DRIVER={{{DRIVER}}};"
            f"SERVER={server_val};"
            f"DATABASE={db_val};"
            "Trusted_Connection=yes;"
            "TrustServerCertificate=yes;"
            "Encrypt=no;"
            "MARS_Connection=yes;"
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
            "MARS_Connection=yes;"
        )
    
    last_err = None
    for attempt in range(1, 6):
        try:
            conn = pyodbc.connect(conn_str, timeout=12)
            conn.timeout = 12
            return conn
        except Exception as e:
            last_err = e
            err_msg = str(e).lower()
            is_transient = any(k in err_msg for k in TRANSIENT_ERRORS)
            if attempt < 5 and is_transient:
                wait_sec = 1.0 + (attempt * 0.5)
                print(f"[db] Raw connection attempt {attempt} failed ({e}). Retrying in {wait_sec}s...")
                time.sleep(wait_sec)
                continue
            raise

def get_connection() -> pyodbc.Connection:
    now = time.time()
    
    # Return cached thread-local connection if valid
    if hasattr(_thread_local, "conn"):
        last_check = getattr(_thread_local, "last_check", 0.0)
        if now - last_check < 15.0:
            return PooledConnection(_thread_local.conn)
        try:
            # Re-verify idle connection if older than 15s
            c = _thread_local.conn.cursor()
            c.execute("SELECT 1")
            c.fetchone()
            c.close()
            _thread_local.last_check = now
            return PooledConnection(_thread_local.conn)
        except Exception:
            reset_connection()

    conn = _create_raw_connection()
    _thread_local.conn = conn
    _thread_local.last_check = now

    try:
        cfg = _load_settings()
        db_val = str(cfg.get("database") or "").strip()
        from services.bugsink_service import check_and_report_database_change
        check_and_report_database_change(db_val, context="db_connect")
    except Exception:
        pass

    return PooledConnection(conn)

def get_api_url() -> str:
    """Returns the Frappe API base URL from sql_settings.json."""
    cfg = _load_settings()
    return str(cfg.get("api_url") or "https://backoffice.havano.pro").strip().rstrip("/")

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