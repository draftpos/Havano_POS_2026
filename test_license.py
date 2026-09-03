"""Quick smoke test for the license encryption round-trip."""
import sys
sys.path.insert(0, 'C:\\Users\\DELL\\New_POS\\Havano_POS_2026')

from utils.hardware import get_machine_id
from utils.license_manager import _encrypt, _decrypt, _fernet_key, verify_license, save_license_key, read_license_key
import hashlib

# 1. Show machine ID
mid = get_machine_id()
print(f"Machine ID : {mid}")

# 2. Generate a sample LIFETIME key for this machine
mid_raw = mid.replace("-", "")
days_hex = "FFFF"  # 65535 > 30000 = lifetime
raw = f"{mid_raw}:{days_hex}:HavanoPOS_Super_Secret_Key_2026_!@#"
sig = hashlib.sha256(raw.encode()).hexdigest().upper()[:16]
test_key = f"{days_hex}{sig}"
formatted = f"{test_key[:4]}-{test_key[4:8]}-{test_key[8:12]}-{test_key[12:16]}-{test_key[16:20]}"
print(f"Test Key   : {formatted}")

# 3. Verify it passes
print(f"Verify     : {verify_license(test_key)}")

# 4. Encrypt / decrypt round-trip
blob = _encrypt(test_key)
print(f"Encrypted  : {blob[:40]}...")
back = _decrypt(blob)
print(f"Decrypted  : {back}")
print(f"Match      : {back == test_key}")
