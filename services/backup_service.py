import os
import glob
import shutil
import datetime
import logging
from pathlib import Path

from database.db import get_app_data_dir

import json

log = logging.getLogger(__name__)


def _settings_file() -> Path:
    """Path to sql_settings.json (same logic as database.db uses)."""
    try:
        return get_app_data_dir() / "sql_settings.json"
    except Exception:
        return Path("app_data") / "sql_settings.json"


def get_backup_dir() -> Path:
    """
    Returns the active backup directory.
    Priority:
      1. User-configured path stored in sql_settings.json under "backup_dir"
      2. C:/Users/Public/HavanoPOS_Backups
      3. C:/ProgramData/HavanoPOS/Backups
      4. app_data/backups
    """
    # 1. User override
    try:
        raw = json.loads(_settings_file().read_text(encoding="utf-8"))
        custom = raw.get("backup_dir", "").strip()
        if custom:
            p = Path(custom)
            p.mkdir(parents=True, exist_ok=True)
            return p
    except Exception:
        pass

    # 2-4. Auto-resolve
    candidates = [
        Path(r"C:\Users\Public\HavanoPOS_Backups"),
        Path(r"C:\ProgramData\HavanoPOS\Backups"),
        get_app_data_dir() / "backups",
    ]
    for cand in candidates:
        try:
            cand.mkdir(parents=True, exist_ok=True)
            return cand
        except Exception:
            pass
    fallback = get_app_data_dir() / "backups"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def set_backup_dir(new_path: str) -> None:
    """
    Persist a user-chosen backup directory to sql_settings.json.
    Also refreshes the module-level BACKUP_DIR variable.
    """
    global BACKUP_DIR
    sf = _settings_file()
    try:
        raw = json.loads(sf.read_text(encoding="utf-8")) if sf.exists() else {}
    except Exception:
        raw = {}
    raw["backup_dir"] = new_path
    sf.write_text(json.dumps(raw, indent=4), encoding="utf-8")
    BACKUP_DIR = Path(new_path)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


# Module-level shortcut — evaluated once at import time but can be
# refreshed by calling set_backup_dir().
BACKUP_DIR = get_backup_dir()


def _get_db_name() -> str:
    from database.db import _load_settings
    return _load_settings().get("database", "havano_posop07978808")


def _get_backup_db_connection():
    from database.db import _load_settings, DRIVER
    import pyodbc
    cfg = _load_settings()
    db_name = cfg.get("database", "havano_posop07978808")
    server_val = cfg.get("server") or ".\\SQLEXPRESS"
    if cfg.get("auth_mode") == "windows":
        conn_str = (
            f"DRIVER={{{DRIVER}}};SERVER={server_val};DATABASE={db_name};"
            "Trusted_Connection=yes;TrustServerCertificate=yes;Encrypt=no;"
            "Application Name=POS_Backup;"
        )
    else:
        conn_str = (
            f"DRIVER={{{DRIVER}}};SERVER={server_val};DATABASE={db_name};"
            f"UID={cfg.get('username', '')};PWD={cfg.get('password', '')};"
            "TrustServerCertificate=yes;Encrypt=no;Application Name=POS_Backup;"
        )
    return pyodbc.connect(conn_str, autocommit=True, timeout=5)


def trigger_local_backup(label: str = "") -> dict:
    """
    Triggers a SQL Server backup directly to BACKUP_DIR.
    Returns {"ok": True/False, "path": str, "error": str}.
    Keeps only the 30 most recent backup files.
    """
    try:
        db_name = _get_db_name()
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        tag = f"_{label}" if label else ""
        backup_filename = f"{db_name}{tag}_{timestamp}.bak"
        final_backup_path = BACKUP_DIR / backup_filename

        conn = _get_backup_db_connection()
        cur = conn.cursor()

        print(f"[Backup] Creating backup '{backup_filename}' at {final_backup_path} ...")
        
        # Try direct backup to final_backup_path first
        direct_success = False
        try:
            cur.execute(f"BACKUP DATABASE [{db_name}] TO DISK = '{final_backup_path}' WITH INIT")
            while cur.nextset():
                pass
            if final_backup_path.exists():
                direct_success = True
                print(f"[Backup] SUCCESS: Created backup directly at {final_backup_path}")
        except Exception as _direct_err:
            log.warning(f"[Backup] Direct backup to {final_backup_path} failed ({_direct_err}). Falling back to SQL default path...")

        if not direct_success:
            # Fallback: SQL Server default path trick
            cur.execute(f"BACKUP DATABASE [{db_name}] TO DISK = '{backup_filename}' WITH INIT")
            while cur.nextset():
                pass

            cur.execute(
                "SELECT TOP 1 physical_device_name "
                "FROM msdb.dbo.backupmediafamily "
                f"WHERE physical_device_name LIKE '%{backup_filename}' "
                "ORDER BY media_set_id DESC"
            )
            row = cur.fetchone()
            if row and row[0]:
                sql_path = Path(row[0])
                try:
                    shutil.copy2(sql_path, final_backup_path)
                    print(f"[Backup] SUCCESS: Copied backup from {sql_path} to {final_backup_path}")
                    try:
                        os.remove(sql_path)
                    except Exception:
                        pass
                except PermissionError:
                    log.warning(f"[Backup] Permission Denied: Could not copy from {sql_path.parent}. The backup exists at {sql_path}.")
                    print(f"[Backup] WARNING: Backup succeeded but couldn't be copied due to permissions. Find it at: {sql_path}")
                    conn.close()
                    return {"ok": True, "path": str(sql_path), "error": "Backup exists but lacks copy permissions."}
            else:
                conn.close()
                return {"ok": False, "path": "", "error": "SQL backup succeeded but file could not be located."}

        conn.close()

        # Cleanup old backups
        _cleanup_old_backups(BACKUP_DIR, db_name, keep_count=30)
        app_backups_dir = get_app_data_dir() / "backups"
        if app_backups_dir.exists() and app_backups_dir != BACKUP_DIR:
            _cleanup_old_backups(app_backups_dir, db_name, keep_count=30)

        return {"ok": True, "path": str(final_backup_path), "error": ""}

    except Exception as e:
        log.error(f"[Backup] Failed: {e}")
        print(f"[Backup] FAILED: {e}")
        return {"ok": False, "path": "", "error": str(e)}


def _get_master_connection():
    from database.db import _load_settings, DRIVER
    # pyrefly: ignore [missing-import]
    import pyodbc
    cfg = _load_settings()
    server_val = cfg.get("server") or ".\\SQLEXPRESS"
    if cfg.get("auth_mode") == "windows":
        conn_str = (
            f"DRIVER={{{DRIVER}}};SERVER={server_val};DATABASE=master;"
            "Trusted_Connection=yes;TrustServerCertificate=yes;Encrypt=no;"
            "Application Name=POS_Restore;"
        )
    else:
        conn_str = (
            f"DRIVER={{{DRIVER}}};SERVER={server_val};DATABASE=master;"
            f"UID={cfg.get('username', '')};PWD={cfg.get('password', '')};"
            "TrustServerCertificate=yes;Encrypt=no;Application Name=POS_Restore;"
        )
    return pyodbc.connect(conn_str, autocommit=True, timeout=5)


def restore_database(bak_path: str) -> dict:
    """
    Restore a .bak file over the current database.
    Steps:
      1. Auto-backup the current state first (safety net).
      2. Copy .bak into SQL Server's readable backup dir.
      3. Read logical file list from the backup (RESTORE FILELISTONLY).
      4. Read the current physical file paths from sys.master_files.
      5. SET the database to SINGLE_USER to boot everyone out.
      6. RESTORE DATABASE … WITH REPLACE, MOVE … (maps logical → physical).
      7. SET the database back to MULTI_USER.
    Returns {"ok": True/False, "error": str}.
    """
    try:
        db_name = _get_db_name()
        bak = Path(bak_path)
        if not bak.exists():
            return {"ok": False, "error": f"Backup file not found: {bak_path}"}

        # Step 1 - safety backup of the current state
        print("[Restore] Creating safety backup before restore ...")
        safety = trigger_local_backup(label="pre_restore")
        if not safety["ok"]:
            return {"ok": False, "error": f"Pre-restore backup failed: {safety['error']}"}

        # Step 2 - Copy the .bak into SQL Server's default backup dir
        conn = _get_master_connection()
        conn.autocommit = True
        cur = conn.cursor()

        # Find the default backup directory
        cur.execute("SELECT SERVERPROPERTY('InstanceDefaultBackupPath')")
        row = cur.fetchone()
        if row and row[0]:
            sql_backup_dir = Path(row[0])
        else:
            cur.execute("SELECT physical_name FROM sys.master_files WHERE database_id = 1 AND type = 0")
            row2 = cur.fetchone()
            sql_backup_dir = Path(row2[0]).parent if row2 else Path(r"C:\Program Files\Microsoft SQL Server\MSSQL16.SQLEXPRESS\MSSQL\Backup")

        restore_filename = f"_restore_{db_name}_{datetime.datetime.now().strftime('%H%M%S')}.bak"
        sql_bak_path = sql_backup_dir / restore_filename
        shutil.copy2(bak, sql_bak_path)

        # Step 3 - Read logical file names from the backup file
        print("[Restore] Reading file list from backup ...")
        cur.execute(f"RESTORE FILELISTONLY FROM DISK = '{sql_bak_path}'")
        filelist_rows = cur.fetchall()
        # columns: LogicalName, PhysicalName, Type, ...
        # Type 'D' = data, 'L' = log
        logical_data = [r[0] for r in filelist_rows if r[2] == 'D']
        logical_log  = [r[0] for r in filelist_rows if r[2] == 'L']

        # Step 4 - Read the CURRENT physical paths for this database
        cur.execute(
            "SELECT type, physical_name FROM sys.master_files "
            "WHERE database_id = DB_ID(?)", (db_name,)
        )
        phys_rows = cur.fetchall()
        # type 0 = data, 1 = log
        phys_data = [r[1] for r in phys_rows if r[0] == 0]
        phys_log  = [r[1] for r in phys_rows if r[0] == 1]

        # If current paths are unknown, fall back to SQL Server DATA dir
        if not phys_data:
            cur.execute("SELECT physical_name FROM sys.master_files WHERE database_id=1 AND type=0")
            row_m = cur.fetchone()
            data_dir = Path(row_m[0]).parent if row_m else sql_backup_dir
            phys_data = [str(data_dir / f"{db_name}.mdf")]
            phys_log  = [str(data_dir / f"{db_name}_log.ldf")]

        # Build MOVE clauses — pair logical names from backup → physical paths of current DB
        move_clauses = []
        for i, lname in enumerate(logical_data):
            target = phys_data[i] if i < len(phys_data) else phys_data[0]
            move_clauses.append(f"MOVE '{lname}' TO '{target}'")
        for i, lname in enumerate(logical_log):
            target = phys_log[i] if i < len(phys_log) else phys_log[0]
            move_clauses.append(f"MOVE '{lname}' TO '{target}'")

        move_sql = ", ".join(move_clauses)

        # Step 5 - Boot everyone out
        print(f"[Restore] Restoring '{db_name}' from {bak.name} ...")
        try:
            cur.execute(f"ALTER DATABASE [{db_name}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE")
        except Exception as e:
            print(f"[Restore] Warning during SINGLE_USER: {e}")

        # Step 6 - Restore with MOVE so file path mismatches don't block it
        restore_sql = (
            f"RESTORE DATABASE [{db_name}] FROM DISK = '{sql_bak_path}' "
            f"WITH REPLACE, {move_sql}"
        )
        print(f"[Restore] SQL: {restore_sql}")
        cur.execute(restore_sql)
        while cur.nextset():
            pass

        # Step 7 - Back to multi-user
        cur.execute(f"ALTER DATABASE [{db_name}] SET MULTI_USER")

        # Step 8 - Re-grant access to the current login.
        # Restoring from a backup of a DIFFERENT database orphans the user
        # mappings, so the current login loses access. Fix by making it db_owner.
        print("[Restore] Re-granting database access to current login ...")
        try:
            from database.db import _load_settings, DRIVER
            cfg = _load_settings()
            if cfg.get("auth_mode") == "windows":
                # Windows auth — get the current OS login name from SQL itself
                cur.execute("SELECT SUSER_SNAME()")
                login_row = cur.fetchone()
                current_login = login_row[0] if login_row and login_row[0] else None
            else:
                current_login = cfg.get("username", "")

            if current_login:
                # ALTER AUTHORIZATION makes current_login the owner (db_owner)
                cur.execute(
                    f"ALTER AUTHORIZATION ON DATABASE::[{db_name}] TO [{current_login}]"
                )
                print(f"[Restore] Access granted to '{current_login}' on '{db_name}'.")

                # Also ensure the login exists as a user inside the restored DB
                # (in case the backup came from a completely different server)
                try:
                    cur.execute(
                        f"USE [{db_name}]; "
                        f"IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = '{current_login}') "
                        f"  CREATE USER [{current_login}] FOR LOGIN [{current_login}]; "
                        f"ALTER ROLE db_owner ADD MEMBER [{current_login}];"
                    )
                except Exception as _ue:
                    # Non-fatal — ALTER AUTHORIZATION above already covers this
                    print(f"[Restore] Note (non-fatal) during user role grant: {_ue}")
        except Exception as _pe:
            print(f"[Restore] Warning: could not re-grant permissions: {_pe}")

        conn.close()


        # Cleanup temp file
        try:
            os.remove(sql_bak_path)
        except Exception:
            pass

        print(f"[Restore] SUCCESS: Database '{db_name}' restored successfully.")
        return {"ok": True, "error": ""}

    except Exception as e:
        # Try to re-enable multi-user if something went wrong
        try:
            c = _get_master_connection(); c.autocommit = True
            c.cursor().execute(f"ALTER DATABASE [{_get_db_name()}] SET MULTI_USER")
            c.close()
        except Exception:
            pass
        log.error(f"[Restore] Failed: {e}")
        print(f"[Restore] FAILED: {e}")
        return {"ok": False, "error": str(e)}


def list_backups() -> list[dict]:
    """
    Return a list of backup files sorted newest-first.
    Scans ALL candidate backup directories so the UI always shows every
    .bak file regardless of which folder SQL Server actually wrote to.
    """
    from database.db import get_app_data_dir as _app_dir
    seen_names: set = set()
    all_files: list = []

    candidate_dirs = [
        Path(r"C:\Users\Public\HavanoPOS_Backups"),
        Path(r"C:\ProgramData\HavanoPOS\Backups"),
        _app_dir() / "backups",
        BACKUP_DIR,  # always include the resolved dir (may overlap with one above)
    ]

    for d in candidate_dirs:
        if not d.exists():
            continue
        for f in d.glob("*.bak"):
            if f.name in seen_names:
                continue  # skip duplicates (same file in two dirs)
            seen_names.add(f.name)
            all_files.append(f)

    all_files.sort(key=os.path.getmtime, reverse=True)

    results = []
    for f in all_files:
        stat = f.stat()
        results.append({
            "filename": f.name,
            "path": str(f),
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "created": datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
        })
    return results


def _cleanup_old_backups(backup_dir: Path, db_name: str, keep_count: int = 30):
    try:
        search_pattern = str(backup_dir / f"{db_name}_*.bak")
        files = glob.glob(search_pattern)
        files.sort(key=os.path.getmtime)
        if len(files) > keep_count:
            for old in files[:-keep_count]:
                try:
                    os.remove(old)
                    print(f"[Backup] Pruned old backup: {Path(old).name}")
                except Exception as e:
                    log.error(f"[Backup] Failed to prune {old}: {e}")
    except Exception as e:
        log.error(f"[Backup] Cleanup failed: {e}")
