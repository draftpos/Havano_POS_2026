import os

flutter_lib = r"C:\Users\user\Desktop\havano-android-flutter-main\lib"

for root, dirs, files in os.walk(flutter_lib):
    for file in files:
        if file.endswith(".dart"):
            full_path = os.path.join(root, file)
            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    if "warehouse" in content.lower() and "pricelist" in content.lower().replace("_", ""):
                        rel = os.path.relpath(full_path, flutter_lib)
                        print(f"Match: {rel}")
                        for l in content.splitlines():
                            if "pricelist" in l.lower().replace("_", ""):
                                safe_l = l.encode('ascii', 'replace').decode('ascii').strip()
                                print(f"  {safe_l[:120]}")
            except Exception:
                pass
