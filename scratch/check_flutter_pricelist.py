import os

flutter_lib = r"C:\Users\user\Desktop\havano-android-flutter-main\lib"
if os.path.exists(flutter_lib):
    print("Found flutter lib directory. Searching for pricelist and product sync files...")
    matches = []
    for root, dirs, files in os.walk(flutter_lib):
        for file in files:
            if file.endswith(".dart"):
                full_path = os.path.join(root, file)
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        if "price_list" in content.lower() or "pricelist" in content.lower() or "price_type" in content.lower():
                            matches.append((full_path, len(content)))
                except Exception:
                    pass
    print(f"Total matching files with price list logic: {len(matches)}")
    for m in matches[:15]:
        rel = os.path.relpath(m[0], flutter_lib)
        print(f" - {rel}")
else:
    print("Flutter lib directory not found at path.")
