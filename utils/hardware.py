import subprocess
import hashlib
import platform

def get_system_uuid() -> str:
    """Gets a stable hardware UUID that doesn't change with network interfaces."""
    if platform.system() != "Windows":
        import uuid
        return str(uuid.getnode()) # Fallback for non-windows
    
    try:
        # 1. Try BIOS UUID (Extremely stable hardware ID)
        output = subprocess.check_output("wmic csproduct get uuid", shell=True, text=True)
        lines = [line.strip() for line in output.strip().split('\n') if line.strip()]
        if len(lines) > 1:
            serial = lines[1]
            if serial and serial.lower() not in ["ffffffff-ffff-ffff-ffff-ffffffffffff", "03000200-0400-0500-0006-000700080009"]:
                return serial
    except Exception:
        pass
        
    try:
        # 2. Try Windows MachineGuid (Stable OS install ID)
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
        val, _ = winreg.QueryValueEx(key, "MachineGuid")
        winreg.CloseKey(key)
        if val:
            return str(val)
    except Exception:
        pass
        
    # 3. Final fallback
    import uuid
    return str(uuid.getnode())

def get_machine_id() -> str:
    """
    Creates a clean, 16-character Machine ID string based on stable system UUIDs.
    """
    stable_id = get_system_uuid()
    
    hashed = hashlib.sha256(stable_id.encode('utf-8')).hexdigest().upper()
    
    # Return a 16-character chunk formatted with dashes for readability
    chunk = hashed[:16]
    formatted_id = f"{chunk[:4]}-{chunk[4:8]}-{chunk[8:12]}-{chunk[12:16]}"
    return formatted_id

def is_same_device(dev1: str, dev2: str) -> bool:
    """
    Compares two device hardware IDs, accounting for string formatting,
    dashes, case sensitivity, and cloud 16-character truncation.
    Returns True if the IDs represent the same physical machine.
    """
    if not dev1 or not dev2:
        return True
    d1 = str(dev1).strip().lower().replace("-", "").replace(":", "")
    d2 = str(dev2).strip().lower().replace("-", "").replace(":", "")
    if d1 == d2:
        return True
    if len(d1) >= 6 and len(d2) >= 6:
        if d1.startswith(d2) or d2.startswith(d1) or d1 in d2 or d2 in d1:
            return True
    return False

if __name__ == "__main__":
    print("========================================")
    print("      HARDWARE FINGERPRINT TESTER       ")
    print("========================================")
    print(f"[*] Stable System UUID: {get_system_uuid()}")
    print(f"[*] Generated ID      : {get_machine_id()}")
    print("========================================")
