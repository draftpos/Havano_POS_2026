"""
Havano POS — Manual License Key Inserter, Generator & Activator
================================================================
Usage:
  1. Interactive Mode (prompts you to enter your license key):
     python activate_license.py

  2. Insert / Activate your own License Key directly:
     python activate_license.py --key "FFFF-4266-9A70-69F8-2A5E"

  3. Auto-Generate & Activate Lifetime License for this PC:
     python activate_license.py --auto

  4. Check Current License Status:
     python activate_license.py --check
"""

import sys
import os
import argparse
import hashlib
from datetime import datetime, timedelta

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.hardware import get_machine_id
from utils.license_manager import (
    SECRET_KEY,
    BASE_DATE,
    save_license_key,
    verify_license,
    get_license_info,
    read_license_key
)


def generate_license_key(machine_id: str, days: int = None) -> str:
    """Generate a signed license key for a given Machine ID."""
    mid_clean = machine_id.replace("-", "").strip().upper()

    if days is None or days >= 9999:
        days_hex = "FFFF"
    else:
        target_expiry = datetime.now() + timedelta(days=days)
        delta_days = (target_expiry - BASE_DATE).days
        days_hex = "FFFF" if delta_days > 30000 else f"{delta_days:04X}"

    raw_payload = f"{mid_clean}:{days_hex}:{SECRET_KEY}"
    sig_hex = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest().upper()[:16]
    key_raw = f"{days_hex}{sig_hex}"

    return f"{key_raw[:4]}-{key_raw[4:8]}-{key_raw[8:12]}-{key_raw[12:16]}-{key_raw[16:20]}"


def insert_user_license(key_str: str) -> bool:
    """Validates and saves a user-provided license key into Registry and Database."""
    local_mid = get_machine_id()
    clean_key = key_str.replace("-", "").strip().upper()

    print(f"\n[*] Validating provided key for Machine ID: {local_mid}")
    if len(clean_key) != 20:
        print(" ERROR: License key must be 20 characters (excluding dashes).")
        return False

    if not verify_license(key_str):
        print(" ERROR: License key is invalid for this machine or has expired.")
        return False

    saved = save_license_key(key_str)
    if saved:
        print(" SUCCESS: License key accepted and saved to Registry & Database!")
        info = get_license_info()
        print(f" License Status: {info.get('status')}")
        print(f" Expiry Date   : {info.get('expiry_date')}")
        return True
    else:
        print(" ERROR: Verification passed, but failed to save to storage.")
        return False


def main():
    parser = argparse.ArgumentParser(description="Havano POS Manual License Key Inserter & Activator")
    parser.add_argument("--key", type=str, help="Insert and activate a specific license key")
    parser.add_argument("--check", action="store_true", help="Check current license status")
    parser.add_argument("--auto", action="store_true", help="Auto-generate and activate Lifetime license for this PC")
    parser.add_argument("--machine-id", type=str, help="Generate key for a remote Machine ID")
    parser.add_argument("--days", type=int, help="Days duration when generating key")

    args = parser.parse_args()
    local_mid = get_machine_id()

    print("=" * 65)
    print("           HAVANO POS — LICENSE INSERTER & MANAGER          ")
    print("=" * 65)
    print(f"Local Machine ID: {local_mid}")
    print("-" * 65)

    if args.check:
        info = get_license_info()
        print(f"Current Key    : {info.get('key', 'None')}")
        print(f"License Status : {info.get('status')}")
        print(f"Expiry Date    : {info.get('expiry_date')}")
        print("=" * 65)
        return

    if args.key:
        insert_user_license(args.key)
        print("=" * 65)
        return

    if args.auto:
        auto_key = generate_license_key(local_mid)
        print(f"Generated Key : {auto_key}")
        insert_user_license(auto_key)
        print("=" * 65)
        return

    if args.machine_id:
        gen_key = generate_license_key(args.machine_id, days=args.days)
        print(f"Target Machine ID : {args.machine_id}")
        print(f"Generated Key     : {gen_key}")
        print("=" * 65)
        return

    # Interactive CLI menu if no arguments passed
    print("\nSelect an option:")
    print("  1) Insert & Activate your License Key")
    print("  2) Check Current License Status")
    print("  3) Auto-Generate & Activate Lifetime License for this PC")
    print("  4) Generate License Key for another PC")
    print("  Q) Quit")

    try:
        choice = input("\nEnter choice (1-4 or Q): ").strip()
    except EOFError:
        choice = ""

    if choice == "1":
        user_key = input("\nEnter your 20-character License Key: ").strip()
        if user_key:
            insert_user_license(user_key)
    elif choice == "2":
        info = get_license_info()
        print(f"\nCurrent Key    : {info.get('key', 'None')}")
        print(f"License Status : {info.get('status')}")
        print(f"Expiry Date    : {info.get('expiry_date')}")
    elif choice == "3":
        auto_key = generate_license_key(local_mid)
        print(f"\nGenerated Key : {auto_key}")
        insert_user_license(auto_key)
    elif choice == "4":
        remote_id = input("Enter Remote Machine ID (e.g. XXXX-XXXX-XXXX-XXXX): ").strip()
        if remote_id:
            gen_key = generate_license_key(remote_id)
            print(f"\nGenerated Key for {remote_id}: {gen_key}")
    else:
        print("Exiting.")

    print("=" * 65)


if __name__ == "__main__":
    main()
