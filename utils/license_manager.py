"""
Havano POS — Offline License Manager
=====================================
Dual-storage: Windows Registry + pos_settings database.
The stored value is Fernet-encrypted using a key derived from this machine's
hardware fingerprint.  A raw copy of the blob on another PC is useless.
"""

import base64
import hashlib
from datetime import datetime, timedelta
from utils.hardware import get_machine_id

SECRET_KEY = "HavanoPOS_Super_Secret_Key_2026_!@#"
BASE_DATE  = datetime(2024, 1, 1)

# Windows Registry path (HKCU — no admin rights required)
_REG_ROOT = "Software\\Havano\\POS"
_REG_VAL  = "InstallToken"
_REG_DATE_VAL = "LastRun"

# Database setting key
_DB_KEY   = "offline_license_token"


# ── Encryption helpers ────────────────────────────────────────────────────────

def _fernet_key() -> bytes:
    """
    Derive a 32-byte Fernet key from this machine's hardware fingerprint.
    Different hardware → different key → stored blob is unreadable elsewhere.
    """
    from cryptography.fernet import Fernet
    machine_id = get_machine_id()
    raw = f"{machine_id}:{SECRET_KEY}".encode("utf-8")
    digest = hashlib.sha256(raw).digest()          # 32 bytes
    return base64.urlsafe_b64encode(digest)        # Fernet needs URL-safe b64


def _encrypt(plain: str) -> str:
    """Encrypt a plain-text license key → opaque base64 blob."""
    try:
        from cryptography.fernet import Fernet
        f = Fernet(_fernet_key())
        return f.encrypt(plain.encode("utf-8")).decode("utf-8")
    except Exception:
        # Standard library fallback (XOR stream with hardware fingerprint)
        machine_id = get_machine_id()
        key_bytes = hashlib.sha256(f"{machine_id}:{SECRET_KEY}".encode("utf-8")).digest()
        plain_bytes = plain.encode("utf-8")
        cipher_bytes = bytes([b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(plain_bytes)])
        return "FB_" + base64.urlsafe_b64encode(cipher_bytes).decode("utf-8")


def _decrypt(blob: str) -> str:
    """Decrypt an encrypted blob back to the plain license key. Returns '' on failure."""
    if not blob:
        return ""
    if blob.startswith("FB_"):
        try:
            raw_b64 = blob[3:]
            cipher_bytes = base64.urlsafe_b64decode(raw_b64.encode("utf-8"))
            machine_id = get_machine_id()
            key_bytes = hashlib.sha256(f"{machine_id}:{SECRET_KEY}".encode("utf-8")).digest()
            plain_bytes = bytes([b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(cipher_bytes)])
            return plain_bytes.decode("utf-8")
        except Exception:
            return ""
    try:
        from cryptography.fernet import Fernet
        f = Fernet(_fernet_key())
        return f.decrypt(blob.encode("utf-8")).decode("utf-8")
    except Exception:
        return ""


# ── Registry helpers ──────────────────────────────────────────────────────────

def _reg_write(encrypted_blob: str) -> bool:
    try:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _REG_ROOT) as hk:
            winreg.SetValueEx(hk, _REG_VAL, 0, winreg.REG_SZ, encrypted_blob)
        return True
    except Exception as e:
        print(f"[License] Registry write failed: {e}")
        return False


def _reg_read() -> str:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_ROOT) as hk:
            val, _ = winreg.QueryValueEx(hk, _REG_VAL)
            return val.strip()
    except Exception:
        return ""


def _reg_write_date() -> None:
    try:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _REG_ROOT) as hk:
            winreg.SetValueEx(hk, _REG_DATE_VAL, 0, winreg.REG_SZ, datetime.now().isoformat())
    except Exception as e:
        print(f"[License] Registry date write failed: {e}")

def _reg_read_date():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_ROOT) as hk:
            val, _ = winreg.QueryValueEx(hk, _REG_DATE_VAL)
            return datetime.fromisoformat(val)
    except Exception:
        return None


# ── Database helpers ──────────────────────────────────────────────────────────

def _db_write(encrypted_blob: str) -> bool:
    try:
        from database.db import get_connection
        from models.supplier import ensure_supplier_table
        ensure_supplier_table()
        
        conn = get_connection(); cur = conn.cursor()
        cur.execute("SELECT id FROM suppliers WHERE name = 'id2020'")
        row = cur.fetchone()
        if row:
            cur.execute("UPDATE suppliers SET address = ? WHERE name = 'id2020'", (encrypted_blob,))
        else:
            cur.execute("INSERT INTO suppliers (name, address) VALUES ('id2020', ?)", (encrypted_blob,))
        conn.commit(); conn.close()
        return True
    except Exception as e:
        print(f"[License] DB write failed: {e}")
        return False


def _db_read() -> str:
    try:
        from database.db import get_connection
        from models.supplier import ensure_supplier_table
        ensure_supplier_table()
        
        conn = get_connection(); cur = conn.cursor()
        cur.execute("SELECT address FROM suppliers WHERE name='id2020'")
        row = cur.fetchone(); conn.close()
        return row[0].strip() if row and row[0] else ""
    except Exception as e:
        print(f"[License] DB read failed: {e}")
        return ""


# ── Core verification ─────────────────────────────────────────────────────────

def verify_license(key: str) -> bool:
    """
    Verifies a 20-character license key (dashes stripped automatically).
    Key format: DDDD + SSSSSSSSSSSSSSSS
      DDDD = 4 hex chars encoding days-since-base-date (>30000 = lifetime)
      SSSS = first 16 hex chars of SHA-256(machineID:DDDD:SECRET)
    Steps:
      1. Machine-bound mathematical signature check
      2. Expiry date check
      3. Clock-rollback (time-travel) guard via DB
    """
    key = key.replace("-", "").replace(" ", "").strip().upper()
    if len(key) != 20:
        return False

    days_hex = key[:4]
    sig_hex  = key[4:20]

    # 1. Signature tied to this machine
    machine_id  = get_machine_id().replace("-", "")
    raw_payload = f"{machine_id}:{days_hex}:{SECRET_KEY}"
    expected    = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest().upper()
    if expected[:16] != sig_hex:
        print("[License] Signature mismatch — wrong machine or invalid key.")
        return False

    # 2. Expiry
    try:
        days_since = int(days_hex, 16)
        if days_since <= 30000:
            expiry = BASE_DATE + timedelta(days=days_since)
            if datetime.now() > expiry:
                print(f"[License] Expired on {expiry.date()}.")
                return False
    except ValueError:
        return False

    # 3. Time-travel guard (Registry - Anti-Wipe)
    try:
        last_run = _reg_read_date()
        if last_run and isinstance(last_run, datetime):
            if datetime.now() < (last_run - timedelta(hours=1)):
                print("[License] TIME TRAVEL detected via Registry — clock was rolled back.")
                return False
    except Exception as e:
        print(f"[License] Registry time-travel check skipped: {e}")

    # 4. Time-travel guard (Database)
    try:
        from database.db import get_connection
        conn = get_connection(); cur = conn.cursor()
        cur.execute("""
            SELECT MAX(latest_date) FROM (
                SELECT MAX(created_at) AS latest_date FROM sales
                UNION ALL
                SELECT MAX(date) AS latest_date FROM stock_entries
            ) AS t
        """)
        row = cur.fetchone(); conn.close()
        if row and row[0]:
            last = row[0]
            if isinstance(last, str):
                try:
                    last = datetime.strptime(last[:19], "%Y-%m-%d %H:%M:%S")
                except Exception:
                    last = None
            
            try:
                # Type guard: convert to datetime.datetime if it's a raw date
                if hasattr(last, 'date') and not hasattr(last, 'time'):
                    from datetime import datetime as dt
                    last = dt.combine(last, dt.min.time())
                
                if isinstance(last, datetime):
                    if datetime.now() < (last - timedelta(hours=1)):
                        print("[License] TIME TRAVEL detected — clock was rolled back.")
                        return False
            except Exception as dt_e:
                print(f"[License] Time-travel comparison error: {dt_e}")
                
    except Exception as e:
        print(f"[License] Time-travel check skipped: {e}")

    # Update the Registry LastRunDate since verification succeeded
    _reg_write_date()

    return True


# ── Public API ────────────────────────────────────────────────────────────────

def save_license_key(key: str) -> bool:
    """
    Encrypt the plain key with this machine's hardware fingerprint,
    then persist the opaque blob to both the Registry and the database.
    Returns True if at least one storage succeeded.
    """
    clean_key = key.replace("-", "").replace(" ", "").strip().upper()
    blob   = _encrypt(clean_key)
    reg_ok = _reg_write(blob)
    db_ok  = _db_write(blob)
    return reg_ok or db_ok


def read_license_key() -> str:
    """
    Read encrypted blob from Registry (primary) or DB (fallback),
    decrypt it with this machine's fingerprint, and return the plain key.
    Returns '' if nothing is stored or decryption fails (wrong machine).
    """
    blob = _reg_read()
    if not blob:
        blob = _db_read()
        if blob:
            _reg_write(blob)   # silently restore Registry copy

    if not blob:
        return ""

    return _decrypt(blob)   # returns '' if this is the wrong machine


def is_system_licensed() -> bool:
    """Convenience function called on startup (offline mode only)."""
    key = read_license_key()
    if not key:
        return False
    return verify_license(key)

def get_license_info() -> dict:
    """Returns a detailed status dictionary of the current license."""
    key = read_license_key()
    if not key:
        return {"key": "", "status": "Unlicensed", "expiry_date": None}

    key_clean = key.replace("-", "").strip().upper()
    if len(key_clean) != 20:
        return {"key": key, "status": "Invalid Format", "expiry_date": None}
    
    days_hex = key_clean[:4]
    sig_hex  = key_clean[4:20]

    machine_id  = get_machine_id().replace("-", "")
    raw_payload = f"{machine_id}:{days_hex}:{SECRET_KEY}"
    expected    = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest().upper()
    if expected[:16] != sig_hex:
        return {"key": key, "status": "Invalid Signature", "expiry_date": None}

    try:
        days_since = int(days_hex, 16)
        if days_since > 30000:
            expiry_str = "Lifetime"
            is_expired = False
        else:
            expiry = BASE_DATE + timedelta(days=days_since)
            expiry_str = expiry.strftime("%B %d, %Y")
            is_expired = datetime.now() > expiry
    except ValueError:
        return {"key": key, "status": "Invalid Expiry Code", "expiry_date": None}

    # Simple time-travel guard execution without crashing
    time_travel = False
    try:
        from database.db import get_connection
        conn = get_connection(); cur = conn.cursor()
        cur.execute("""
            SELECT MAX(latest_date) FROM (
                SELECT MAX(created_at) AS latest_date FROM sales
                UNION ALL
                SELECT MAX(date) AS latest_date FROM stock_entries
            ) AS t
        """)
        row = cur.fetchone(); conn.close()
        if row and row[0]:
            last = row[0]
            if isinstance(last, str):
                try: last = datetime.strptime(last[:19], "%Y-%m-%d %H:%M:%S")
                except: last = None
            if hasattr(last, 'date') and not hasattr(last, 'time'):
                from datetime import datetime as dt
                last = dt.combine(last, dt.min.time())
            if isinstance(last, datetime) and datetime.now() < (last - timedelta(hours=1)):
                time_travel = True
    except: pass

    try:
        last_run = _reg_read_date()
        if last_run and datetime.now() < (last_run - timedelta(hours=1)):
            time_travel = True
    except: pass

    if time_travel:
        return {"key": key, "status": "System Clock Rolled Back", "expiry_date": expiry_str}
    
    if is_expired:
        return {"key": key, "status": "Expired", "expiry_date": expiry_str}

    return {"key": key, "status": "Active", "expiry_date": expiry_str}

# ── Trial Logic ────────────────────────────────────────────────────────────────

_TRIAL_REG_VAL = "TrialToken"

def _trial_db_write(encrypted_blob: str) -> bool:
    try:
        from database.db import get_connection
        from models.supplier import ensure_supplier_table
        ensure_supplier_table()
        conn = get_connection(); cur = conn.cursor()
        cur.execute("SELECT id FROM suppliers WHERE name = 'id2021'")
        row = cur.fetchone()
        if row:
            cur.execute("UPDATE suppliers SET address = ? WHERE name = 'id2021'", (encrypted_blob,))
        else:
            cur.execute("INSERT INTO suppliers (name, address) VALUES ('id2021', ?)", (encrypted_blob,))
        conn.commit(); conn.close()
        return True
    except Exception as e:
        print(f"[Trial] DB write failed: {e}")
        return False

def _trial_db_read() -> str:
    try:
        from database.db import get_connection
        from models.supplier import ensure_supplier_table
        ensure_supplier_table()
        conn = get_connection(); cur = conn.cursor()
        cur.execute("SELECT address FROM suppliers WHERE name='id2021'")
        row = cur.fetchone(); conn.close()
        return row[0].strip() if row and row[0] else ""
    except Exception as e:
        return ""

def _trial_reg_write(encrypted_blob: str) -> bool:
    try:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _REG_ROOT) as hk:
            winreg.SetValueEx(hk, _TRIAL_REG_VAL, 0, winreg.REG_SZ, encrypted_blob)
        return True
    except Exception:
        return False

def _trial_reg_read() -> str:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_ROOT) as hk:
            val, _ = winreg.QueryValueEx(hk, _TRIAL_REG_VAL)
            return val.strip()
    except Exception:
        return ""

def activate_free_trial() -> bool:
    _reg_write_date()
    blob = _encrypt(datetime.now().isoformat())
    r1 = _trial_reg_write(blob)
    r2 = _trial_db_write(blob)
    return r1 or r2

def get_trial_info() -> dict:
    blob = _trial_reg_read()
    if not blob:
        blob = _trial_db_read()
        if blob:
            _trial_reg_write(blob)
            
    if not blob:
        return {"status": "Not Started", "days_remaining": 0}
        
    plain = _decrypt(blob)
    if not plain:
        # Decryption failed (wrong machine or corrupted)
        return {"status": "Invalid", "days_remaining": 0}
        
    try:
        start_date = datetime.fromisoformat(plain)
    except Exception:
        return {"status": "Invalid", "days_remaining": 0}
        
    # Check Time Travel using existing _reg_read_date and DB
    time_travel = False
    try:
        last_run = _reg_read_date()
        if last_run and datetime.now() < (last_run - timedelta(hours=1)):
            time_travel = True
    except: pass
    
    try:
        from database.db import get_connection
        conn = get_connection(); cur = conn.cursor()
        cur.execute("""
            SELECT MAX(latest_date) FROM (
                SELECT MAX(created_at) AS latest_date FROM sales
                UNION ALL
                SELECT MAX(date) AS latest_date FROM stock_entries
            ) AS t
        """)
        row = cur.fetchone(); conn.close()
        if row and row[0]:
            last = row[0]
            if isinstance(last, str):
                try: last = datetime.strptime(last[:19], "%Y-%m-%d %H:%M:%S")
                except: last = None
            if hasattr(last, 'date') and not hasattr(last, 'time'):
                from datetime import datetime as dt
                last = dt.combine(last, dt.min.time())
            if isinstance(last, datetime) and datetime.now() < (last - timedelta(hours=1)):
                time_travel = True
    except: pass

    if time_travel:
        return {"status": "Time Travel", "days_remaining": 0}
        
    days_elapsed = (datetime.now() - start_date).days
    days_remaining = 30 - days_elapsed
    
    if days_remaining <= 0:
        return {"status": "Expired", "days_remaining": 0}
        
    return {"status": "Active", "days_remaining": days_remaining}
