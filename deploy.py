"""
Havano POS — Deploy Script
===========================
Run this AFTER building your installer with PyInstaller.

Usage:
    python deploy.py patch           # 2.0.0 → 2.0.1
    python deploy.py minor           # 2.0.0 → 2.1.0
    python deploy.py major           # 2.0.0 → 3.0.0
    python deploy.py 2.3.1           # set exact version

What it does:
    1. Reads current APP_VERSION from main.py
    2. Bumps (or sets) the version
    3. Writes the new version back to main.py
    4. Finds the built .exe installer in the dist/ folder
    5. Generates version.json
    6. Uploads version.json + the .exe to Nextcloud via WebDAV
"""

import re
import sys
import json
import os
from pathlib import Path

# Ensure UTF-8 output encoding for Windows command line / PowerShell
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ─────────────────────────────────────────────────────────────────────────────
#  Nextcloud WebDAV credentials (can be overridden by environment variables)
# ─────────────────────────────────────────────────────────────────────────────
NC_BASE_URL     = (os.environ.get("NEXTCLOUD_BASE_URL") or os.environ.get("NEXTCLOUD_URL") or "https://vmi3020185.contaboserver.net").rstrip("/")
NC_SHARE_TOKEN  = os.environ.get("NEXTCLOUD_SHARE_TOKEN") or "3kiXJJQC4LiwPrd"
NC_USERNAME     = os.environ.get("NEXTCLOUD_USERNAME") or "admin"
NC_APP_PASS     = os.environ.get("NEXTCLOUD_APP_PASS") or "Farai@#$1234"
NC_FOLDER       = (os.environ.get("NEXTCLOUD_FOLDER") or "Pos-Updates").strip("/")
# ─────────────────────────────────────────────────────────────────────────────

MAIN_PY       = Path(__file__).parent / "main.py"
INSTALLER_DIR = Path(__file__).parent / "combined" / "Output"  # ← where Inno Setup drops the .exe
RELEASE_NOTES = os.environ.get("RELEASE_NOTES", "Bug fixes and performance improvements.")


def _upload(local_path: Path, remote_filename: str):
    """Upload a file to Nextcloud via WebDAV (PUT) with streamed file chunking."""
    import requests
    import time

    total_bytes = local_path.stat().st_size
    size_mb = total_bytes / (1024 * 1024)
    print(f"  Uploading {remote_filename} ({size_mb:.1f} MB) to Nextcloud ...")

    endpoints = []
    if NC_SHARE_TOKEN:
        endpoints.append((
            f"{NC_BASE_URL}/public.php/webdav/{remote_filename}",
            (NC_SHARE_TOKEN, "")
        ))
    if NC_USERNAME and NC_APP_PASS:
        endpoints.append((
            f"{NC_BASE_URL}/remote.php/dav/files/{NC_USERNAME}/{NC_FOLDER}/{remote_filename}",
            (NC_USERNAME, NC_APP_PASS)
        ))

    last_error = None
    for url, auth in endpoints:
        for attempt in range(1, 4):
            try:
                with open(local_path, "rb") as f:
                    resp = requests.put(
                        url,
                        data=f,
                        auth=auth,
                        headers={"Content-Type": "application/octet-stream"},
                        timeout=(30, 1800),  # 30s connect timeout, 30min transfer timeout
                    )
                if resp.status_code in (200, 201, 204):
                    print(f"  [OK] {remote_filename} uploaded successfully (HTTP {resp.status_code})")
                    return
                else:
                    raise RuntimeError(f"Upload failed: HTTP {resp.status_code} ({resp.text[:200]})")
            except Exception as e:
                last_error = e
                if attempt < 3:
                    print(f"  Warning: Attempt {attempt} failed ({e}), retrying in 3s...")
                    time.sleep(3)
                else:
                    break

    if last_error:
        raise last_error


def _read_current_version() -> str:
    text = MAIN_PY.read_text(encoding="utf-8")
    m = re.search(r'^APP_VERSION\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
    if not m:
        raise RuntimeError("Could not find APP_VERSION in main.py")
    return m.group(1)


def _write_version(new_version: str):
    text = MAIN_PY.read_text(encoding="utf-8")
    new_text = re.sub(
        r'^(APP_VERSION\s*=\s*)["\'][^"\']+["\']',
        f'\\g<1>"{new_version}"',
        text,
        flags=re.MULTILINE,
    )
    MAIN_PY.write_text(new_text, encoding="utf-8")
    print(f"  ✏️  main.py  →  APP_VERSION = \"{new_version}\"")


def _bump(current: str, bump_type: str) -> str:
    parts = [int(x) for x in current.split(".")]
    while len(parts) < 3:
        parts.append(0)
    if bump_type == "major":
        parts = [parts[0] + 1, 0, 0]
    elif bump_type == "minor":
        parts = [parts[0], parts[1] + 1, 0]
    elif bump_type == "patch":
        parts = [parts[0], parts[1], parts[2] + 1]
    return ".".join(str(p) for p in parts)


def _find_installer(version: str) -> Path:
    """Look for the built installer in combined/Output."""
    candidates = [
        INSTALLER_DIR / f"HavanoPOS_Update_Installer_v{version}.exe",
        INSTALLER_DIR / f"HavanoPOS_Installer_v{version}.exe",
        INSTALLER_DIR / f"HavanoPOS_v{version}.exe",
    ]
    for c in candidates:
        if c.exists():
            return c

    # Fallback: pick the NEWEST .exe matching version or most recently modified
    matching = sorted(INSTALLER_DIR.glob(f"*{version}*.exe"), key=lambda p: p.stat().st_mtime, reverse=True)
    if matching:
        print(f"  ℹ️  Found version-matching installer: {matching[0].name}")
        return matching[0]

    exes = sorted(INSTALLER_DIR.glob("*.exe"), key=lambda p: p.stat().st_mtime, reverse=True)
    if exes:
        print(f"  ⚠️  Exact match not found — using newest installer: {exes[0].name}")
        return exes[0]
    raise FileNotFoundError(
        f"No installer .exe found in {INSTALLER_DIR}.\n"
        f"Build with Inno Setup first, then run deploy.py."
    )


def main():
    args = [a.strip() for a in sys.argv[1:]]
    auto_yes = ("-y" in args) or ("--yes" in args) or (os.environ.get("CI") == "true") or (not sys.stdin.isatty())
    bump_args = [a for a in args if a not in ("-y", "--yes", "--current", "current")]
    bump_arg = bump_args[0] if bump_args else ("current" if ("--current" in args or "current" in args) else "patch")

    print("\n==============================================")
    print("  Havano POS -- Deploy to Nextcloud")
    print("==============================================\n")

    # 1. Version
    current = _read_current_version()
    print(f"  Current version : {current}")

    if bump_arg in ("current", "--current"):
        new_version = current
    elif bump_arg in ("major", "minor", "patch"):
        new_version = _bump(current, bump_arg)
    else:
        new_version = bump_arg  # explicit e.g. "2.3.1"

    print(f"  Target version  : {new_version}\n")

    # 2. Confirm (if interactive)
    if not auto_yes:
        ans = input(f"  Deploy v{new_version} and upload to Nextcloud? [y/N] ").strip().lower()
        if ans != "y":
            print("  Aborted.")
            return
    else:
        print(f"  Deploying v{new_version} (auto-confirmed)...")

    # 3. Update main.py if version changed
    if new_version != current:
        _write_version(new_version)

    # 4. Find installer
    installer_path = _find_installer(new_version)
    installer_filename = installer_path.name
    print(f"  📦 Found installer : {installer_filename} ({installer_path.stat().st_size / (1024*1024):.1f} MB)")

    # 5. Generate version.json
    version_info = {
        "version": new_version,
        "installer_filename": installer_filename,
        "release_notes": RELEASE_NOTES,
        "mandatory": False,
    }
    INSTALLER_DIR.mkdir(parents=True, exist_ok=True)
    version_json_path = INSTALLER_DIR / "version.json"
    version_json_path.write_text(json.dumps(version_info, indent=2), encoding="utf-8")
    print(f"  📄 version.json written:\n{json.dumps(version_info, indent=4)}\n")

    # 6. Upload both to Nextcloud
    print(f"  Connecting to Nextcloud endpoint: {NC_BASE_URL} ...")
    _upload(version_json_path, "version.json")
    _upload(installer_path,    installer_filename)

    print(f"\n  🎉 SUCCESS: Havano POS v{new_version} is deployed and live on Nextcloud!")
    print(f"     File: {installer_filename}")
    print("     Existing client POS installations will see the update on next launch.\n")


if __name__ == "__main__":
    main()
