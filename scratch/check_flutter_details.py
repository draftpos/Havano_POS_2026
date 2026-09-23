import os

flutter_lib = r"C:\Users\user\Desktop\havano-android-flutter-main\lib"

files_to_check = [
    "core/repositories/cart_repository.dart",
    "core/services/products_service.dart",
    "core/services/sync_service.dart",
    "core/database/tables/price_lists.dart",
    "core/providers/pos_state_provider.dart"
]

for rel in files_to_check:
    full = os.path.join(flutter_lib, rel.replace("/", os.sep))
    if os.path.exists(full):
        print(f"=== {rel} ===")
        with open(full, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            for l in lines:
                if any(w in l.lower() for w in ["price_list", "pricelist", "getprice", "selling_price", "rates"]):
                    print("  ", l.strip()[:100])
