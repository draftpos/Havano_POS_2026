import os

flutter_lib = r"C:\Users\user\Desktop\havano-android-flutter-main\lib"

patterns = ["pos_profile", "branch", "shop", "selling_price_list", "warehouse"]

print("=== Checking Flutter for Branch/POS Profile Price List ===")
for root, dirs, files in os.walk(flutter_lib):
    for file in files:
        if file.endswith(".dart"):
            full_path = os.path.join(root, file)
            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    if ("branch" in content.lower() or "pos_profile" in content.lower() or "posprofile" in content.lower()) and ("price_list" in content.lower() or "pricelist" in content.lower() or "selling_price" in content.lower()):
                        rel = os.path.relpath(full_path, flutter_lib)
                        print(f"File: {rel}")
                        for l in content.splitlines():
                            if any(k in l.lower() for k in ["pricelist", "price_list", "selling_price_list"]):
                                safe_l = l.encode('ascii', 'replace').decode('ascii').strip()
                                print(f"  {safe_l[:120]}")
            except Exception:
                pass
