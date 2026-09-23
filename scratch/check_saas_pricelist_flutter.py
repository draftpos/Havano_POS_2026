import os

flutter_lib = r"C:\Users\user\Desktop\havano-android-flutter-main\lib"

files_to_check = [
    "core/services/sync_service.dart",
    "core/services/auth_service.dart",
    "core/services/customers_service.dart",
    "core/providers/pos_state_provider.dart",
    "core/repositories/customer_repository.dart",
    "core/database/tables/customers.dart"
]

for rel in files_to_check:
    full = os.path.join(flutter_lib, rel.replace("/", os.sep))
    if os.path.exists(full):
        print(f"\n=== {rel} ===")
        with open(full, "r", encoding="utf-8", errors="ignore") as f:
            for l in f:
                if any(k in l.lower() for k in ["pricelist", "price_list", "default_price", "pos_profile", "selling_price_list", "standard selling"]):
                    safe_line = l.encode('ascii', 'replace').decode('ascii').strip()
                    print("  ", safe_line[:110])
