# =============================================================================
# main.py — Havano POS Entry Point
# =============================================================================

import sys
import os
import traceback
from pathlib import Path
import time as _timing

# Reconfigure stdout/stderr to UTF-8 so dev-log emojis in migrate.py etc. don't
# crash on Windows cp1252 consoles. In --windowed PyInstaller builds stdout is
# None, so the calls are guarded.
try:
    if sys.stdout is not None:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if sys.stderr is not None:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt

# Import view components
from views.main_window import MainWindow
from views.login_dialog import LoginDialog
from views.dialogs.sql_settings_dialog import SqlSettingsDialog
from views.dialogs.onboarding_dialog import OnboardingDialog
from database.db import is_connection_valid, get_connection

def resource_path(relative_path: str) -> str:
    """
    Handles asset paths for both dev and PyInstaller bundles.
    Use this for read-only bundled assets (icons, images shipped inside the exe).
    """
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def get_app_data_dir() -> Path:
    """
    Returns the writable 'app_data' directory that sits NEXT TO the .exe
    (or next to main.py in dev mode).

    WHY THIS MATTERS:
    - PyInstaller --onefile extracts to a temp folder (sys._MEIPASS).
      If you use Path("app_data") or Path.cwd() / "app_data" inside a
      bundled app, the working directory can be anywhere the user launched
      the exe from — it will NOT reliably point to the exe's own folder.
    - This function always resolves to <exe_folder>/app_data, which is
      where sql_settings.json, advance_settings.json, logos/, and
      offline_sync.json are expected to live.
    """
    if hasattr(sys, "_MEIPASS"):
        # Running as a bundled .exe — parent of sys.executable is the exe folder
        return Path(sys.executable).parent / "app_data"
    # Dev mode — use the project root (same as before)
    return Path(os.path.abspath(".")) / "app_data"

def global_exception_handler(exctype, value, tb):
    """Prevents the app from disappearing without a trace on crash."""
    if issubclass(exctype, KeyboardInterrupt):
        # Graceful exit on Ctrl+C
        sys.exit(0)

    error_msg = "".join(traceback.format_exception(exctype, value, tb))
    print(f"CRITICAL ERROR:\n{error_msg}")
    
    # Try to show a message box if QApplication exists
    try:
        if QApplication.instance():
            QMessageBox.critical(None, "Critical Error", 
                               f"An unexpected error occurred:\n{value}\n\nThe application will close.")
    except: pass
    
    sys.__excepthook__(exctype, value, tb)
    sys.exit(1)

def apply_global_styles(app: QApplication):
    """Centralized high-quality Professional White theme styling."""
    NAVY      = "#0d1f3c"
    ACCENT    = "#1a5fb4"
    WHITE     = "#ffffff"
    OFF_WHITE = "#f5f8fc"
    BORDER    = "#c8d8ec"
    MUTED     = "#5a7a9a"
    DARK_TEXT = "#1e293b"

    app.setStyleSheet(f"""
        QMainWindow, QDialog {{ background-color: {WHITE}; }}
        QWidget {{
            background-color: {WHITE};
            color: {DARK_TEXT};
            font-size: 14px;
            font-family: 'Segoe UI', 'Roboto', 'Arial';
        }}
        QLabel {{ background: transparent; }}
        
        QPushButton {{
            background-color: {NAVY};
            color: {WHITE};
            border: none;
            border-radius: 8px;
            padding: 10px 20px;
            min-width: 80px;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background-color: {ACCENT};
        }}
        QPushButton:pressed {{
            background-color: "#0a1424";
        }}
        QPushButton:disabled {{
            background-color: {BORDER};
            color: {MUTED};
        }}

        QLineEdit {{
            background-color: {WHITE};
            color: {DARK_TEXT};
            border: 1.5px solid {BORDER};
            border-radius: 8px;
            padding: 8px;
        }}
        QLineEdit:focus {{ border: 2px solid {ACCENT}; }}
        
        QMessageBox {{ background-color: {WHITE}; }}
        QMessageBox QLabel {{ color: {DARK_TEXT}; }}
        QMessageBox QPushButton {{ min-width: 100px; }}

        QHeaderView::section {{
            background-color: {OFF_WHITE};
            color: {NAVY};
            padding: 8px;
            border-bottom: 2px solid {BORDER};
            font-weight: bold;
        }}
        QTableWidget {{
            background-color: {WHITE};
            border: 1px solid {BORDER};
            gridline-color: {OFF_WHITE};
            border-radius: 8px;
            selection-background-color: {ACCENT};
            selection-color: {WHITE};
        }}
        QScrollBar:vertical {{
            border: none;
            background: {OFF_WHITE};
            width: 10px;
            margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background: {BORDER};
            min-height: 20px;
            border-radius: 5px;
        }}
        QScrollBar::handle:vertical:hover {{ background: {MUTED}; }}
    """)

if __name__ == "__main__":
    # Set the global exception handler immediately
    sys.excepthook = global_exception_handler

    # 1. Initialize Application
    app = QApplication(sys.argv)
    app.setApplicationName("Havano POS")
    app.setWindowIcon(QIcon(resource_path("assets/havano-logo.ico")))
    apply_global_styles(app)

    # 2. Ensure Environment is Ready
    # Create app_data folder next to the exe (or cwd in dev).
    # NOTE: get_app_data_dir() is exe-safe — do NOT use Path("app_data") here.
    app_data_dir = get_app_data_dir()
    app_data_dir.mkdir(exist_ok=True)
    settings_file = app_data_dir / "sql_settings.json"

    # 3. Connection & Setup Logic
    # We retry a few times if settings exist, to give the SQL server time to wake up.
    # This prevents unnecessary "System Configuration" popups on cold starts.
    connection_retries = 0
    max_connection_retries = 3

    while True:
        if settings_file.exists():
            if is_connection_valid():
                break
            else:
                if connection_retries < max_connection_retries:
                    connection_retries += 1
                    print(f"[startup] Database connection failed, retrying ({connection_retries}/{max_connection_retries})...")
                    import time
                    time.sleep(1.5)
                    continue
        
        # If settings don't exist, or retries failed, prompt the user
        print("[startup] Missing or invalid SQL settings. Prompting user...")
        dlg = SqlSettingsDialog()
        if dlg.exec() != QDialog.Accepted:
            print("[startup] Setup cancelled. Retrying connection check...")
            connection_retries = 0 # Reset retries for next loop
            continue
        # After accepting dialog, loop back to verify connection
        connection_retries = 0
        continue

    # 4. Database Setup & Migrations
    _t_mig = _timing.perf_counter()
    try:
        from setup_database import run as run_setup
        run_setup()
    except Exception as e:
        print(f"[startup] Database setup failed: {e}")
        traceback.print_exc()

    print(f"[startup] migrations phase: {int((_timing.perf_counter() - _t_mig) * 1000)} ms")

    # 5b. Onboarding Check
    is_offline = False
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT setting_value FROM pos_settings WHERE setting_key = 'offline_mode'")
        row = cur.fetchone()
        conn.close()
        
        if row is None:
            print("[startup] No mode selected. Launching onboarding...")
            onboard_dlg = OnboardingDialog()
            if onboard_dlg.exec() != QDialog.Accepted:
                print("[startup] Onboarding cancelled. Exiting.")
                sys.exit(0)
            # Re-check after onboarding
            conn = get_connection(); cur = conn.cursor()
            cur.execute("SELECT setting_value FROM pos_settings WHERE setting_key = 'offline_mode'")
            row = cur.fetchone(); conn.close()
            
        is_offline = (row[0] == "1") if row else False
    except Exception as e:
        print(f"[startup] Onboarding check failed: {e}")

    # 4. Update known URL (silently)
    try:
        from services.site_config import save_current_url
        save_current_url()
    except: pass
    
    if is_offline:
        print("[startup] Offline Mode active. Skipping server validation.")

    # 6. Execution Flow (Login -> Main)
    _t_login = _timing.perf_counter()
    login_dlg = LoginDialog()
    login_result = login_dlg.exec()
    print(f"[startup] login dialog (user interaction included): "
          f"{int((_timing.perf_counter() - _t_login) * 1000)} ms")
    if login_result == QDialog.Accepted:
        try:
            print(f"[startup] Login successful. Launching MainWindow for {login_dlg.logged_in_user.get('username')}...")
            _t_mw = _timing.perf_counter()
            window = MainWindow(user=login_dlg.logged_in_user)
            print(f"[startup] MainWindow __init__: "
                  f"{int((_timing.perf_counter() - _t_mw) * 1000)} ms")
            _t_show = _timing.perf_counter()
            window.show()
            print(f"[startup] window.show(): "
                  f"{int((_timing.perf_counter() - _t_show) * 1000)} ms")
            
            # Use app.exec() for the main loop
            exit_code = app.exec()
            print(f"[shutdown] App exited with code {exit_code}")
            sys.exit(exit_code)
        except Exception as e:
            QMessageBox.critical(None, "Launch Error", f"Could not start the main window:\n{e}")
            sys.exit(1)
    else:
        print("[startup] Login cancelled. Exiting.")
        sys.exit(0)
         
#pyinstaller --noconfirm --onefile --windowed --icon "assets/havano-logo.ico" --add-data "assets;assets" --name "HavanoPOS" main.py