import os
for root, dirs, files in os.walk("."):
    for file in files:
        if file.endswith(".py"):
            fn = os.path.join(root, file)
            try:
                with open(fn, "r", encoding="utf-8") as f:
                    for i, line in enumerate(f, 1):
                        if "allowed_payment_methods" in line:
                            print(f"{fn} Line {i}: {line.strip()}")
            except Exception:
                pass
