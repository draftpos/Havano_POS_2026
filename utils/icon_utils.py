# =============================================================================
# utils/icon_utils.py
# QtAwesome Resilient Font Integrity, Self-Healing & Safe Call Utilities
# =============================================================================
import os
import sys
import shutil
import datetime
import traceback
from pathlib import Path
from PySide6.QtGui import QIcon, QPixmap, QColor
from PySide6.QtCore import Qt

# Minimum sane threshold size for valid font files (10KB)
FONT_MIN_SIZE_BYTES = 10240

# Global state tracking if QtAwesome is operating in degraded (disabled) mode
QTA_DISABLED = False
_HEAL_LOG_PATH = None


def get_log_file_path() -> str:
    """Resolve destination for font integrity logs inside app_data."""
    global _HEAL_LOG_PATH
    if _HEAL_LOG_PATH:
        return _HEAL_LOG_PATH

    try:
        if hasattr(sys, "_MEIPASS"):
            base_dir = Path(sys.executable).parent / "app_data"
        else:
            base_dir = Path(os.path.abspath(".")).resolve() / "app_data"
        base_dir.mkdir(parents=True, exist_ok=True)
        _HEAL_LOG_PATH = str(base_dir / "font_integrity.log")
    except Exception:
        _HEAL_LOG_PATH = os.path.join(os.path.abspath("."), "font_integrity.log")

    return _HEAL_LOG_PATH


def log_font_diagnostic(message: str) -> None:
    """Log a diagnostic entry with ISO timestamp to font_integrity.log."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] [FontIntegrity] {message}\n"
    print(entry.strip())
    try:
        log_path = get_log_file_path()
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception as e:
        print(f"[FontIntegrity] Warning: Failed to write to log file: {e}")


def get_backup_fonts_directory() -> str:
    """Resolve the bundled read-only backup fonts directory (assets/fonts_backup)."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, "assets", "fonts_backup")
    return os.path.abspath(os.path.join(".", "assets", "fonts_backup"))


def get_qtawesome_fonts_directory() -> str:
    """Dynamically locate qtawesome runtime fonts directory."""
    try:
        import qtawesome
        return os.path.join(os.path.dirname(os.path.abspath(qtawesome.__file__)), "fonts")
    except Exception as e:
        log_font_diagnostic(f"Error resolving qtawesome directory: {e}")
        return ""


def get_windows_user_fonts_directory() -> str:
    """Locate Windows AppData user fonts directory where QtAwesome caches font files."""
    if os.name != "nt":
        return ""
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    if not local_appdata:
        return ""
    return os.path.join(local_appdata, "Microsoft", "Windows", "Fonts")


def verify_and_heal_fonts() -> dict:
    """
    Perform early startup integrity check and automatic self-healing for QtAwesome fonts.
    - Scans qtawesome package directory and Windows LocalAppData fonts directory.
    - Verifies all .ttf files exist and exceed FONT_MIN_SIZE_BYTES (10KB).
    - Attempts automatic self-heal from assets/fonts_backup/ if corrupted or empty.
    - Sets QTA_DISABLED = True if self-healing fails, protecting app from hard crash.
    """
    global QTA_DISABLED
    result = {
        "success": True,
        "healed_count": 0,
        "corrupted_files": [],
        "disabled": False
    }

    qta_dir = get_qtawesome_fonts_directory()
    backup_dir = get_backup_fonts_directory()
    win_user_fonts_dir = get_windows_user_fonts_directory()

    log_font_diagnostic("Starting pre-init font integrity check...")

    if not qta_dir or not os.path.isdir(qta_dir):
        log_font_diagnostic(f"CRITICAL: qtawesome fonts directory missing: {qta_dir}")
        QTA_DISABLED = True
        result["success"] = False
        result["disabled"] = True
        return result

    # Directories to inspect and sanitize
    target_dirs = [qta_dir]
    if win_user_fonts_dir and os.path.isdir(win_user_fonts_dir):
        target_dirs.append(win_user_fonts_dir)

    for target_dir in target_dirs:
        if not os.path.isdir(target_dir):
            continue

        try:
            for fname in os.listdir(target_dir):
                if not (fname.endswith(".ttf") or fname.endswith(".json")):
                    continue

                fpath = os.path.join(target_dir, fname)
                if not os.path.isfile(fpath):
                    continue

                actual_size = os.path.getsize(fpath)
                
                # Check for 0-byte or corrupted font file (<10KB for .ttf)
                if fname.endswith(".ttf") and actual_size < FONT_MIN_SIZE_BYTES:
                    log_font_diagnostic(
                        f"CORRUPTED FONT DETECTED: {fpath} | Expected: >{FONT_MIN_SIZE_BYTES} bytes, Actual: {actual_size} bytes"
                    )
                    result["corrupted_files"].append(fpath)
                    
                    # Attempt Self-Heal from backup
                    backup_file = os.path.join(backup_dir, fname)
                    healed = False
                    if os.path.isfile(backup_file) and os.path.getsize(backup_file) >= FONT_MIN_SIZE_BYTES:
                        try:
                            os.remove(fpath)
                        except OSError:
                            pass
                        try:
                            shutil.copy2(backup_file, fpath)
                            new_size = os.path.getsize(fpath)
                            if new_size >= FONT_MIN_SIZE_BYTES:
                                log_font_diagnostic(f"SELF-HEAL SUCCESSFUL: Restored {fname} from backup ({new_size} bytes)")
                                result["healed_count"] += 1
                                healed = True
                        except Exception as copy_err:
                            log_font_diagnostic(f"SELF-HEAL FAILED for {fname}: {copy_err}")

                    if not healed:
                        log_font_diagnostic(f"CRITICAL: Could not self-heal {fname}.")
                        result["success"] = False
        except Exception as scan_err:
            log_font_diagnostic(f"Error during font scanning in {target_dir}: {scan_err}")

    # Test loading QtAwesome explicitly in a try-except sandbox
    try:
        from PySide6.QtWidgets import QApplication
        if not QApplication.instance():
            log_font_diagnostic("Notice: QApplication not active yet; skipping pre-warm icon test.")
        else:
            import qtawesome as qta
            # Pre-warm default font set
            qta.icon("fa5s.check")
            log_font_diagnostic("QtAwesome font engine initialized successfully.")
    except Exception as qta_err:
        log_font_diagnostic(f"QtAwesome initialization failed after self-heal: {qta_err}")
        log_font_diagnostic(traceback.format_exc())
        log_font_diagnostic("ACTIVATING DEGRADED MODE: QtAwesome icons disabled to prevent app crash.")
        QTA_DISABLED = True
        result["success"] = False
        result["disabled"] = True

    install_qtawesome_monkey_patch()
    return result


_ORIGINAL_QTA_ICON = None


def install_qtawesome_monkey_patch():
    """
    Monkey-patch qtawesome.icon globally so that any direct call to qta.icon(...)
    in legacy code automatically routes through safe_icon() exception wrapper.
    """
    global _ORIGINAL_QTA_ICON
    try:
        import qtawesome as qta
        if _ORIGINAL_QTA_ICON is None and hasattr(qta, "icon"):
            _ORIGINAL_QTA_ICON = qta.icon
        qta.icon = safe_icon
    except Exception as e:
        log_font_diagnostic(f"Notice: qtawesome monkey-patch warning: {e}")


def safe_icon(name: str, color=None, fallback: QIcon = None, **kwargs) -> QIcon:
    """
    Thin, resilient wrapper around qtawesome.icon().
    - Catches all exceptions at the call site.
    - Returns fallback or a blank QIcon() if qtawesome fails or is disabled.
    - Never throws an exception or crashes the UI.
    """
    if QTA_DISABLED:
        return fallback if fallback is not None else QIcon()

    try:
        import qtawesome as qta
        if color:
            kwargs["color"] = color
        target_fn = _ORIGINAL_QTA_ICON
        if target_fn and target_fn != safe_icon:
            return target_fn(name, **kwargs)
        return fallback if fallback is not None else QIcon()
    except Exception as e:
        log_font_diagnostic(f"safe_icon warning for '{name}': {e}")
        return fallback if fallback is not None else QIcon()


def safe_pixmap(name: str, width: int = 16, height: int = 16, color=None, fallback: QPixmap = None) -> QPixmap:
    """
    Safely render a QPixmap from a QtAwesome icon without propagating exceptions.
    """
    icon = safe_icon(name, color=color)
    if icon and not icon.isNull():
        try:
            return icon.pixmap(width, height)
        except Exception as e:
            log_font_diagnostic(f"safe_pixmap warning for '{name}': {e}")

    if fallback is not None:
        return fallback

    # Blank transparent pixmap
    pm = QPixmap(width, height)
    pm.fill(Qt.transparent)
    return pm
