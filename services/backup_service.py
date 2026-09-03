import os
import glob
import shutil
import datetime
import logging
from pathlib import Path

from database.db import get_app_data_dir

def _resolve_backup_dir() -> Path:
    """
    Returns a backup directory accessible to both SQL Server service and local user applications.
    Priority:
      1. C:/Users/Public/HavanoPOS_Backups (Shared public directory on Windows)
      2. C:/ProgramData/HavanoPOS/Backups (Shared application data directory)
      3. app_data/backups (Local app data folder)
    """
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

BACKUP_DIR = _resolve_backup_dir()


def _get_db_name() -> str:
    from database.db import _load_settings
    return _load_settings().get("database", "pos_db")


def _get_backup_db_connection():
    from database.db import _load_settings, DRIVER
    import pyodbc
    cfg = _load_settings()
    db_name = cfg.get("database", "pos_db")
    if cfg.get("auth_mode") == "windows":
        conn_str = (
            f"DRIVER={{{DRIVER}}};SERVER={cfg['server']};DATABASE={db_name};"
            "Trusted_Connection=yes;TrustServerCertificate=yes;Encrypt=no;"
            "Application Name=POS_Backup;"
        )
    else:
        conn_str = (
            f"DRIVER={{{DRIVER}}};SERVER={cfg['server']};DATABASE={db_name};"
            f"UID={cfg['username']};PWD={cfg['password']};"
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
    if cfg.get("auth_mode") == "windows":
        conn_str = (
            f"DRIVER={{{DRIVER}}};SERVER={cfg['server']};DATABASE=master;"
            "Trusted_Connection=yes;TrustServerCertificate=yes;Encrypt=no;"
            "Application Name=POS_Restore;"
        )
    else:
        conn_str = (
            f"DRIVER={{{DRIVER}}};SERVER={cfg['server']};DATABASE=master;"
            f"UID={cfg['username']};PWD={cfg['password']};"
            "TrustServerCertificate=yes;Encrypt=no;Application Name=POS_Restore;"
        )
    return pyodbc.connect(conn_str, autocommit=True, timeout=5)


def restore_database(bak_path: str) -> dict:
    """
    Restore a .bak file over the current database.
    Steps:
      1. Auto-backup the current state first (safety net).
      2. SET the database to SINGLE_USER to boot everyone out.
      3. RESTORE DATABASE … WITH REPLACE.
      4. SET the database back to MULTI_USER.
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
        #          so the service account can read it.
        conn = _get_master_connection()
        conn.autocommit = True
        cur = conn.cursor()

        # Find the default backup directory by reading the registry through SQL
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

        # Step 3 - Boot everyone, restore, go back to multi-user
        print(f"[Restore] Restoring '{db_name}' from {bak.name} ...")
        try:
            cur.execute(f"ALTER DATABASE [{db_name}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE")
        except Exception as e:
            print(f"[Restore] Warning during SINGLE_USER: {e}")

        cur.execute(f"RESTORE DATABASE [{db_name}] FROM DISK = '{sql_bak_path}' WITH REPLACE")
        while cur.nextset():
            pass

        cur.execute(f"ALTER DATABASE [{db_name}] SET MULTI_USER")
        conn.close()

        # Cleanup the temporary file
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
    """Return a list of backup files sorted newest-first."""
    results = []
    db_name = _get_db_name()
    if not BACKUP_DIR.exists():
        return results
    for f in sorted(BACKUP_DIR.glob("*.bak"), key=os.path.getmtime, reverse=True):
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
