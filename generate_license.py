"""
Havano POS — Admin License Generator
====================================
Keep this script PRIVATE. Do not distribute it with the POS.
Run this to generate activation keys for your customers.
"""

import hashlib
from datetime import datetime, timedelta

# THIS MUST MATCH THE SECRET IN THE POS APP EXACTLY!
SECRET_KEY = "HavanoPOS_Super_Secret_Key_2026_!@#"
BASE_DATE  = datetime(2024, 1, 1)

def generate_key(machine_id: str, days_since_base: int) -> str:
    """
    Generates a 20-character license key based on exact days from BASE_DATE.
    """
    machine_id = machine_id.replace("-", "").strip().upper()
    if len(machine_id) != 16:
        print("Error: Machine ID must be exactly 16 characters (ignoring dashes).")
        return ""

    if days_since_base > 30000:
        days_hex = "FFFF"
    else:
        # Prevent negative hex issues
        days_hex = f"{max(0, days_since_base):04X}"
        
    raw_payload = f"{machine_id}:{days_hex}:{SECRET_KEY}"
    sig = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest().upper()[:16]
    
    raw_key = f"{days_hex}{sig}"
    return f"{raw_key[:4]}-{raw_key[4:8]}-{raw_key[8:12]}-{raw_key[12:16]}-{raw_key[16:20]}"


if __name__ == "__main__":
    print("\n==========================================")
    print("      HAVANO POS - LICENSE GENERATOR      ")
    print("==========================================\n")
    
    mid = input("Enter Customer's Machine ID: ")
    
    print("\nLicense Duration:")
    print("1. Lifetime (Never expires)")
    print("2. 30 Days (Standard Trial)")
    print("3. Custom Days")
    print("4. TEST - Expired Yesterday (To test rejection)")
    
    choice = input("\nSelect duration (1-4): ").strip()
    
    # Calculate how many days have passed since our base date (Jan 1, 2024)
    days_passed_so_far = (datetime.now() - BASE_DATE).days
    
    days_to_encode = 65535 # default to lifetime
    
    if choice == "1":
        days_to_encode = 65535
    elif choice == "2":
        days_to_encode = days_passed_so_far + 30
    elif choice == "3":
        custom = int(input("Enter number of days from today: ").strip())
        days_to_encode = days_passed_so_far + custom
    elif choice == "4":
        # Make it expire 1 day ago!
        days_to_encode = days_passed_so_far - 1
        
    key = generate_key(mid, days_to_encode)
    
    if key:
        print("\n==========================================")
        print("SUCCESS! Give this key to the customer:")
        print(f"\n   {key}\n")
        print("==========================================\n")
