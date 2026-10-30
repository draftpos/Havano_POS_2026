import os
import sys
import subprocess
import shutil
import time

def build():
    print("=" * 60)
    print(" Havano POS -- Building Executable")
    print("=" * 60)

    # 1. Ensure Debug = False in main.py for production release builds
    main_py_path = os.path.join(os.path.dirname(__file__), "main.py")
    if os.path.exists(main_py_path):
        try:
            import re
            with open(main_py_path, "r", encoding="utf-8") as f:
                code = f.read()
            new_code = re.sub(r'^(Debug\s*=\s*)True', r'\g<1>False', code, flags=re.MULTILINE)
            if new_code != code:
                with open(main_py_path, "w", encoding="utf-8") as f:
                    f.write(new_code)
                print("[config] Production build: Automatically set Debug = False in main.py")
            else:
                print("[config] Debug is already False in main.py")
        except Exception as e:
            print(f"[config] Warning: Could not update Debug flag in main.py: {e}")

    # 2. Terminate running instances of HavanoPOS
    if os.name == "nt":
        subprocess.run("taskkill /F /IM HavanoPOS.exe /T", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run("taskkill /F /IM HavanoPOS_App.exe /T", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1)

    # 3. Clean build directories
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
        dist_dir = os.path.join(os.path.dirname(__file__), "dist", "HavanoPOS")
        if os.path.exists(dist_dir):
            app_data_dir = os.path.join(dist_dir, "app_data")
            os.makedirs(app_data_dir, exist_ok=True)
            
            # Copy havanoconfig.ini to dist and app_data
            src_cfg = os.path.join(os.path.dirname(__file__), "havanoconfig.ini")
            if os.path.exists(src_cfg):
                shutil.copy2(src_cfg, os.path.join(dist_dir, "havanoconfig.ini"))
                shutil.copy2(src_cfg, os.path.join(app_data_dir, "havanoconfig.ini"))
                print("[deploy] Included havanoconfig.ini in dist and dist/app_data")

            # Copy havano_cert to dist and app_data
            src_cert = os.path.join(os.path.dirname(__file__), "havano_cert")
            if os.path.exists(src_cert):
                for target_cert in [os.path.join(dist_dir, "havano_cert"), os.path.join(app_data_dir, "havano_cert")]:
                    if os.path.exists(target_cert):
                        shutil.rmtree(target_cert)
                    shutil.copytree(src_cert, target_cert)
                print("[deploy] Included havano_cert in dist and dist/app_data")

        print("\n" + "=" * 60)
        print(" [OK] SUCCESS: Havano POS executable built in dist/HavanoPOS/")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print(f" [FAIL] Build failed with exit code: {res.returncode}")
        print("=" * 60)
        sys.exit(res.returncode)

if __name__ == "__main__":
    build()
