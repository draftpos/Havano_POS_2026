# =============================================================================
# main.py — Havano POS Entry Point
# =============================================================================

import sys
import os
import traceback
from pathlib import Path

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
from database.db import is_connection_valid

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
    error_msg = "".join(traceback.format_exception(exctype, value, tb))
    print(f"CRITICAL ERROR:\n{error_msg}")
    
    # Try to show a message box if QApplication exists
    if QApplication.instance():
        QMessageBox.critical(None, "Critical Error", 
                           f"An unexpected error occurred:\n{value}\n\nThe application will close.")
    sys.__excepthook__(exctype, value, tb)
    sys.exit(1)

def apply_global_styles(app: QApplication):
    """Centralized high-quality dark theme styling."""
    app.setStyleSheet("""
        QMainWindow, QDialog { background-color: #1e1e2e; }
        QWidget {
            background-color: #1e1e2e;
            color: #cdd6f4;
            font-size: 14px;
            font-family: 'Segoe UI', 'Roboto', 'Arial';
        }
        QPushButton {
            background-color: #313244;
            color: #cdd6f4;
            border: 1px solid #45475a;
            border-radius: 8px;
            padding: 10px 20px;
            min-width: 80px;
        }
        QPushButton:hover {
            background-color: #45475a;
            border: 1px solid #cba6f7;
        }
        QPushButton:pressed {
            background-color: #cba6f7;
            color: #1e1e2e;
        }
        QLineEdit {
            background-color: #313244;
            color: #ffffff; /* Brighter text for readability */
            border: 1px solid #45475a;
            border-radius: 8px;
            padding: 8px;
        }
        QLineEdit:focus { border: 2px solid #cba6f7; }
        
        QMessageBox { background-color: #1e1e2e; }
        QMessageBox QLabel { color: #cdd6f4; }
        QMessageBox QPushButton { min-width: 100px; }

        QHeaderView::section {
            background-color: #313244;
            color: #cdd6f4;
            padding: 8px;
            border: none;
        }
        QTableWidget {
            background-color: #181825;
            border: 1px solid #45475a;
            gridline-color: #313244;
            border-radius: 8px;
        }
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
    # We loop here in case the user enters wrong settings, so they can retry
    while True:
        if not settings_file.exists() or not is_connection_valid():
            print("[startup] Missing or invalid SQL settings. Prompting user...")
            dlg = SqlSettingsDialog()
            if dlg.exec() != QDialog.Accepted:
                print("[startup] Setup cancelled. Retrying connection check...")
                continue
            # After accepting dialog, loop back to verify connection
            continue
        break

    # 4. API URL Logic (Server Change Detection)
    print("[startup] Verifying API Server configuration...")
    try:
        from services.site_config import check_url_changed, wipe_database, save_current_url

        if check_url_changed():
            confirm = QMessageBox(None)
            confirm.setWindowTitle("Server Configuration Changed")
            confirm.setIcon(QMessageBox.Warning)
            confirm.setText("The API server URL has changed.")
            confirm.setInformativeText(
                "Your local database is tied to the previous server.\n\n"
                "To continue, the local database must be wiped and re-synced.\n"
                "Do you want to proceed with a database wipe?"
            )
            confirm.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            confirm.setDefaultButton(QMessageBox.No)
            
            if confirm.exec() == QMessageBox.Yes:
                wipe_database()
                save_current_url()
                print("[startup] Database wiped successfully.")
            else:
                print("[startup] User declined DB wipe. Proceeding at own risk.")
        else:
            save_current_url()
    except Exception as e:
        print(f"[startup] Site configuration error: {e}")

    # 5. Database Schema Migration (short-circuits when schema version matches)
    import time as _timing
    _t_mig = _timing.perf_counter()
    print("[startup] Running database migrations...")
    try:
        from setup_database import run as setup_db
        setup_db()
    except Exception as e:
        QMessageBox.critical(None, "Database Error", f"Failed to initialize database:\n{e}")
        sys.exit(1)
    print(f"[startup] migrations phase: {int((_timing.perf_counter() - _t_mig) * 1000)} ms")

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