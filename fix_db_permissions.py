"""
fix_db_permissions.py
─────────────────────
Run this once to fix the 'Login failed (4060)' error caused by a failed
database restore that orphaned the Windows user permissions.

Usage:  python fix_db_permissions.py
"""
import json
import sys
from pathlib import Path

# ── Load settings ─────────────────────────────────────────────────────────────
settings_file = Path("app_data/sql_settings.json")
if not settings_file.exists():
    settings_file = Path(__file__).parent / "app_data" / "sql_settings.json"

with open(settings_file, encoding="utf-8") as f:
    cfg = json.load(f)

server   = cfg.get("server", r".\SQLEXPRESS")
db_name  = cfg.get("database", "")
auth     = cfg.get("auth_mode", "windows")
username = cfg.get("username", "")
password = cfg.get("password", "")

if not db_name:
    print("ERROR: No database name found in sql_settings.json")
    sys.exit(1)

print(f"[fix] Server  : {server}")
print(f"[fix] Database: {db_name}")
print(f"[fix] Auth    : {auth}")

# ── Connect to master ─────────────────────────────────────────────────────────
try:
    import pyodbc
except ImportError:
    print("ERROR: pyodbc not installed. Run: pip install pyodbc")
    sys.exit(1)

DRIVER = "ODBC Driver 17 for SQL Server"

if auth == "windows":
    conn_str = (
        f"DRIVER={{{DRIVER}}};SERVER={server};DATABASE=master;"
        "Trusted_Connection=yes;TrustServerCertificate=yes;Encrypt=no;"
    )
else:
    conn_str = (
        f"DRIVER={{{DRIVER}}};SERVER={server};DATABASE=master;"
        f"UID={username};PWD={password};"
        "TrustServerCertificate=yes;Encrypt=no;"
    )

try:
    conn = pyodbc.connect(conn_str, autocommit=True, timeout=10)
    cur  = conn.cursor()
    print("[fix] Connected to master OK")
except Exception as e:
    print(f"ERROR: Cannot connect to SQL Server master database: {e}")
    sys.exit(1)

# ── Step 1: Make sure the DB is MULTI_USER ────────────────────────────────────
print(f"[fix] Setting [{db_name}] to MULTI_USER ...")
try:
    cur.execute(f"ALTER DATABASE [{db_name}] SET MULTI_USER WITH ROLLBACK IMMEDIATE")
    print("[fix] MULTI_USER OK")
except Exception as e:
    print(f"[fix] Note: {e}  (may already be MULTI_USER)")

# ── Step 2: Get the current login ─────────────────────────────────────────────
if auth == "windows":
    cur.execute("SELECT SUSER_SNAME()")
    row = cur.fetchone()
    current_login = row[0] if row else None
else:
    current_login = username

if not current_login:
    print("ERROR: Could not determine current login name.")
    sys.exit(1)

print(f"[fix] Current login: {current_login}")

# ── Step 3: Make current login the db owner ───────────────────────────────────
print(f"[fix] Granting [{current_login}] db_owner on [{db_name}] ...")
try:
    cur.execute(f"ALTER AUTHORIZATION ON DATABASE::[{db_name}] TO [{current_login}]")
    print("[fix] ALTER AUTHORIZATION OK")
except Exception as e:
    print(f"[fix] ALTER AUTHORIZATION failed: {e}")

# ── Step 4: Ensure user exists inside the DB ─────────────────────────────────
try:
    cur.execute(
        f"USE [{db_name}]; "
        f"IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = '{current_login}') "
        f"  CREATE USER [{current_login}] FOR LOGIN [{current_login}]; "
        f"IF IS_ROLEMEMBER('db_owner', '{current_login}') = 0 "
        f"  ALTER ROLE db_owner ADD MEMBER [{current_login}];"
    )
    print("[fix] User role assignment OK")
except Exception as e:
    print(f"[fix] Note (non-fatal): {e}")

conn.close()
print()
print("=" * 60)
print(f"  Done!  [{current_login}] now has full access to [{db_name}].")
print("  Restart the POS application.")
print("=" * 60)
