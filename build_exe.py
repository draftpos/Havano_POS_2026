import os
import sys
import subprocess
import shutil
import time

def build():
    print("=" * 60)
    print(" Havano POS -- Building Executable")
    print("=" * 60)

    # 1. Terminate running instances of HavanoPOS
    if os.name == "nt":
        subprocess.run("taskkill /F /IM HavanoPOS.exe /T", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run("taskkill /F /IM HavanoPOS_App.exe /T", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1)

    # 2. Clean build directories
    for folder in ["build", "dist", "build_temp", "build_out", "dist_out"]:
        if os.path.exists(folder):
            try:
                shutil.rmtree(folder)
                print(f"[clean] Removed old directory: {folder}")
            except Exception as e:
                print(f"[clean] Could not remove {folder}: {e}")

    # 3. Run PyInstaller with dedicated workpath
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "HavanoPOS.spec",
        "--noconfirm",
        "--clean",
        "--workpath", "build_temp"
    ]
    print(f"[build] Executing: {' '.join(cmd)}")
    res = subprocess.run(cmd)

    if res.returncode == 0:
        print("\n" + "=" * 60)
        print(" [OK] SUCCESS: Havano POS executable built in dist/HavanoPOS/")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print(f" [FAIL] Build failed with exit code: {res.returncode}")
        print("=" * 60)

if __name__ == "__main__":
    build()
