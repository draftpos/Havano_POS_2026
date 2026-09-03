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

# ─────────────────────────────────────────────────────────────────────────────
#  CONFIGURE ONCE — your Nextcloud WebDAV credentials
#  Use an App Password from Nextcloud Settings → Security → App Passwords
# ─────────────────────────────────────────────────────────────────────────────
NC_BASE_URL  = "https://vmi3020185.contaboserver.net"
NC_USERNAME  = "admin"           # ← change if your Nextcloud username is different
NC_APP_PASS  = "Farai@#$1234"
NC_FOLDER    = "Pos-Updates"
# ─────────────────────────────────────────────────────────────────────────────

MAIN_PY       = Path(__file__).parent / "main.py"
INSTALLER_DIR = Path(__file__).parent / "combined" / "Output"  # ← where Inno Setup drops the .exe
RELEASE_NOTES = "Bug fixes and performance improvements."  # ← edit before deploying


def _webdav_url(filename: str) -> str:
    return f"{NC_BASE_URL}/remote.php/dav/files/{NC_USERNAME}/{NC_FOLDER}/{filename}"


def _upload(local_path: Path, remote_filename: str):
    """Upload a file to Nextcloud via WebDAV (PUT)."""
    import urllib.request
    import base64
    creds = base64.b64encode(f"{NC_USERNAME}:{NC_APP_PASS}".encode()).decode()
    url   = _webdav_url(remote_filename)
    data  = local_path.read_bytes()
    req   = urllib.request.Request(url, data=data, method="PUT")
    req.add_header("Authorization", f"Basic {creds}")
    req.add_header("Content-Type", "application/octet-stream")
    print(f"  ↑  Uploading {remote_filename} ({len(data)/1024/1024:.1f} MB) ...")
    with urllib.request.urlopen(req, timeout=120) as resp:
        code = resp.getcode()
        if code in (200, 201, 204):
            print(f"  ✅ {remote_filename} uploaded (HTTP {code})")
        else:
            raise RuntimeError(f"Upload failed: HTTP {code}")


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
        INSTALLER_DIR / f"HavanoPOS_Installer_v{version}.exe",
        INSTALLER_DIR / f"HavanoPOS_v{version}.exe",
    ]
    for c in candidates:
        if c.exists():
            return c

    # Fallback: pick the NEWEST .exe in the folder (most recently modified)
    exes = sorted(INSTALLER_DIR.glob("*.exe"), key=lambda p: p.stat().st_mtime, reverse=True)
    if exes:
        print(f"  ⚠️  Exact match not found — using newest installer: {exes[0].name}")
        return exes[0]
    raise FileNotFoundError(
        f"No installer .exe found in {INSTALLER_DIR}.\n"
        f"Build with Inno Setup first, then run deploy.py."
    )


def main():
    bump_arg = sys.argv[1].strip() if len(sys.argv) > 1 else "patch"

    print("\n══════════════════════════════════════════════")
    print("  Havano POS — Deploy to Nextcloud")
    print("══════════════════════════════════════════════\n")

    # 1. Version
    current = _read_current_version()
    print(f"  Current version : {current}")

    if bump_arg in ("major", "minor", "patch"):
        new_version = _bump(current, bump_arg)
    else:
        new_version = bump_arg  # explicit e.g. "2.3.1"

    print(f"  New version     : {new_version}\n")

    # 2. Confirm
    ans = input(f"  Bump {current} → {new_version} and upload to Nextcloud? [y/N] ").strip().lower()
    if ans != "y":
        print("  Aborted.")
        return

    # 3. Update main.py
    _write_version(new_version)

    # 4. Find installer
    installer_path = _find_installer(new_version)
    installer_filename = f"HavanoPOS_Installer_v{new_version}.exe"

    # Rename if needed so Nextcloud filename matches version.json
    if installer_path.name != installer_filename:
        new_path = installer_path.parent / installer_filename
        installer_path.rename(new_path)
        installer_path = new_path
        print(f"  📝 Renamed installer → {installer_filename}")

    # 5. Generate version.json
    version_info = {
        "version": new_version,
        "installer_filename": installer_filename,
        "release_notes": RELEASE_NOTES,
        "mandatory": False,
    }
    version_json_path = INSTALLER_DIR / "version.json"
    version_json_path.write_text(json.dumps(version_info, indent=2), encoding="utf-8")
    print(f"  📄 version.json written:\n     {json.dumps(version_info, indent=5)}\n")

    # 6. Upload both to Nextcloud
    print("  Uploading to Nextcloud...")
    _upload(version_json_path, "version.json")
    _upload(installer_path,    installer_filename)

    print(f"\n  🎉 Done! v{new_version} is live on Nextcloud.")
    print("     Existing installs will see the update prompt on next startup.\n")


if __name__ == "__main__":
    main()
