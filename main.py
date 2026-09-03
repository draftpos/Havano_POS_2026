import sys
import os
import traceback
import time as _timing
from pathlib import Path

try:
    if sys.stdout is not None:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if sys.stderr is not None:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

try:
    import numpy
    for _k, _v in [('short', getattr(numpy, 'int16', int)), ('ushort', getattr(numpy, 'uint16', int)),
                   ('intc', getattr(numpy, 'int32', int)), ('uintc', getattr(numpy, 'uint32', int)),
                   ('int_', getattr(numpy, 'int64', int)), ('uint', getattr(numpy, 'uint64', int)),
                   ('half', getattr(numpy, 'float16', float)), ('single', getattr(numpy, 'float32', float)),
                   ('double', getattr(numpy, 'float64', float)), ('longdouble', getattr(numpy, 'float64', float))]:
        if not hasattr(numpy, _k):
            setattr(numpy, _k, _v)
except Exception:
    pass

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, QThread, Signal, QTimer

# from views.main_window import MainWindow # Lazy loaded
# from views.login_dialog import LoginDialog # Lazy loaded
from views.dialogs.sql_settings_dialog import SqlSettingsDialog
from database.db import is_connection_valid, get_connection

# ─────────────────────────────────────────────────────────────
#  APP VERSION — update this each release to match version.json
#  on Nextcloud. Example: "2.0.0" → "2.1.0" for next release.
# ────────────────────────────────────────────────────────s────

APP_VERSION = "2.0.8.37"


def resource_path(relative_path: str) -> str:
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def get_app_data_dir() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys.executable).parent / "app_data"
    return Path(os.path.abspath(".")) / "app_data"

class StartupWorker(QThread):
    status_changed = Signal(str)
    finished = Signal(bool)
    error = Signal(str)

    def run(self):
        try:
            self.status_changed.emit("Verifying database...")
            # --- AUTO CREATE OFFLINE DB ---
            try:
                import json
                from database.db import get_app_data_dir, DRIVER
                settings_file = get_app_data_dir() / "sql_settings.json"
                if settings_file.exists():
                    cfg = json.loads(settings_file.read_text(encoding="utf-8"))
                    if cfg.get("system_mode") == "offline" and cfg.get("auth_mode") == "windows":
                        import pyodbc
                        conn_str = f"DRIVER={{{DRIVER}}};SERVER={cfg['server']};Trusted_Connection=yes;TrustServerCertificate=yes;Encrypt=no;"
                        conn = pyodbc.connect(conn_str, autocommit=True, timeout=5)
                        cur = conn.cursor()
                        cur.execute(f"IF NOT EXISTS (SELECT name FROM master.sys.databases WHERE name = N'{cfg['database']}') CREATE DATABASE [{cfg['database']}]")
                        conn.close()
            except Exception as e:
                print(f"[startup] Auto-create DB error: {e}")
            # ------------------------------

            # 1. Connection check
            if not is_connection_valid():
                self.finished.emit(False) # Needs setup
                return

            self.status_changed.emit("Running migrations...")
            # 2. Migrations
            from setup_database import run as run_setup
            run_setup()
            
            try:
                from models.user import migrate as _user_migrate
                from models.restaurant_order import migrate as _restaurant_migrate
                _user_migrate()
                _restaurant_migrate()
            except Exception as e:
                print(f"[startup] Failed to migrate models: {e}")

            self.status_changed.emit("Havano POS Loading...")
            try:
                from services.stock_cache import init_stock_cache
                import threading
                threading.Thread(target=init_stock_cache, daemon=True).start()
            except Exception as e:
                print(f"[startup] Fast stock cache error: {e}")

            self.status_changed.emit("Checking configuration...")
            # 3. Site config
            from services.site_config import check_url_changed, save_current_url
            save_current_url()

            self.finished.emit(True)
        except Exception as e:
            self.error.emit(str(e))

def setup_crash_logging():
    import logging
    import threading
    import faulthandler
    import sys
    import datetime
    from PySide6.QtCore import qInstallMessageHandler

    log_dir = get_app_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    error_log = log_dir / "error.log"
    qt_log = log_dir / "qt.log"
    segfault_log = log_dir / "segfault.log"

    # Delete error log if older than 2 days
    if error_log.exists():
        try:
            today = datetime.date.today()
            mtime = datetime.date.fromtimestamp(error_log.stat().st_mtime)
            if (today - mtime).days >= 2:
                error_log.unlink()
        except Exception:
            pass

    # Enforce a 5MB size limit on all logs to prevent infinite growth
    MAX_SIZE = 2 * 1024 * 1024
    for log_path in [error_log, qt_log, segfault_log]:
        if log_path.exists() and log_path.stat().st_size > MAX_SIZE:
            try:
                import shutil
                shutil.copy2(log_path, log_path.with_suffix(".bak"))
                log_path.write_text("", encoding="utf-8")
            except Exception:
                pass

    # 1. Logging setup
    logging.basicConfig(
        filename=str(error_log),
        level=logging.ERROR,
        format="%(asctime)s %(levelname)s %(message)s"
    )
    
    # Redirect stderr to error_log
    class ErrorStreamLogger:
        def __init__(self, original_stream):
            self.original_stream = original_stream
            
        def write(self, message):
            if message.strip():
                try:
                    with open(error_log, "a", encoding="utf-8") as f:
                        f.write(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [STDERR] {message}\n")
                except Exception:
                    pass
            if self.original_stream:
                try:
                    self.original_stream.write(message)
                except Exception:
                    pass
                    
        def flush(self):
            if self.original_stream:
                try:
                    self.original_stream.flush()
                except Exception:
                    pass
            
    sys.stderr = ErrorStreamLogger(sys.stderr)

    # 2. Qt Message Handler (with throttle for known spam)
    _qt_msg_counts = {}
    _QT_SPAM_LIMIT = 5  # Only log first N of each repetitive message type
    _QT_SPAM_PATTERNS = [
        "setPointSize",
        "Could not parse stylesheet",
        "QWindowsWindow::setGeometry",
    ]

    def qt_message_handler(mode, context, message):
        # Throttle known spammy Qt warnings to prevent log explosion
        for pat in _QT_SPAM_PATTERNS:
            if pat in message:
                _qt_msg_counts[pat] = _qt_msg_counts.get(pat, 0) + 1
                if _qt_msg_counts[pat] > _QT_SPAM_LIMIT:
                    return  # Silently suppress after limit
                break
        try:
            with open(qt_log, "a", encoding="utf-8") as f:
                f.write(f"{mode}: {message}\n")
        except Exception:
            pass
    qInstallMessageHandler(qt_message_handler)

    # 3. Faulthandler for segfaults
    global _fault_file
    _fault_file = open(segfault_log, "w", encoding="utf-8")
    faulthandler.enable(_fault_file)

    # 4. Thread exceptions
    def thread_exception_handler(args):
        with open(error_log, "a", encoding="utf-8") as f:
            f.write("\n=== Thread Exception ===\n")
            traceback.print_exception(args.exc_type, args.exc_value, args.exc_traceback, file=f)
    threading.excepthook = thread_exception_handler

def global_exception_handler(exctype, value, tb):
    error_msg = "".join(traceback.format_exception(exctype, value, tb))
    print(f"CRITICAL EXCEPTION ({exctype.__name__}):\n{error_msg}")
    
    import logging
    logging.error(f"Uncaught exception ({exctype.__name__}):\n{error_msg}")
    
    try:
        log_dir = get_app_data_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "error.log"
        import datetime
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*50}\n[{datetime.datetime.now()}] EXCEPTION DETECTED ({exctype.__name__}):\n{error_msg}\n")
    except Exception as e:
        print(f"Failed to write crash log: {e}")

    if issubclass(exctype, (SystemExit, KeyboardInterrupt)):
        sys.__excepthook__(exctype, value, tb)
        return

    if QApplication.instance():
        msg = QMessageBox(None)
        msg.setWindowTitle("Critical Error")
        msg.setText(f"An unexpected error occurred. Please check logs in app_data.\n\n{value}\n\nThe application will close.")
        msg.setIcon(QMessageBox.Critical)
        msg.setStyleSheet("""
            QMessageBox { background-color: #ffffff; color: #0f172a; }
            QLabel { color: #0f172a; font-size: 13px; font-weight: bold; }
            QPushButton {
                background-color: #1a5fb4; color: #ffffff; border: none;
                border-radius: 6px; padding: 8px 18px; min-width: 80px; font-weight: bold;
            }
            QPushButton:hover { background-color: #164a91; }
        """)
        msg.exec()
    sys.__excepthook__(exctype, value, tb)
    sys.exit(1)

def apply_global_styles(app: QApplication):
    app.setStyleSheet("""
        QMainWindow, QDialog, QMessageBox { background-color: #ffffff; }
        QLineEdit {
            background-color: #ffffff;
            color: #0f172a;
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            padding: 8px;
        }
        QLineEdit:focus { border: 2px solid #1a5fb4; }

        QMessageBox { background-color: #ffffff; color: #0f172a; }
        QMessageBox QLabel { color: #0f172a; font-size: 13px; }
        QMessageBox QPushButton {
            background-color: #1a5fb4;
            color: #ffffff;
            border: none;
            border-radius: 6px;
            padding: 8px 18px;
            min-width: 80px;
            font-weight: bold;
        }
        QMessageBox QPushButton:hover { background-color: #164a91; }

        QHeaderView::section {
            background-color: #1a5fb4;
            color: #ffffff;
            padding: 8px;
            border: none;
        }
        QTableWidget {
            background-color: #ffffff;
            color: #0f172a;
            border: 1px solid #e2e8f0;
            gridline-color: #e2e8f0;
            border-radius: 8px;
        }
        QTableWidget::item:selected {
            background-color: #e8f1f8;
            color: #1a5fb4;
        }

        QCalendarWidget QWidget#qt_calendar_navigationbar { background-color: #1a5fb4; min-height: 36px; }
        QCalendarWidget QToolButton { color: #ffffff; font-weight: bold; background-color: #1a5fb4; border: none; border-radius: 4px; padding: 4px 6px; }
        QCalendarWidget QToolButton:hover { background-color: #1c6dd0; }
        QCalendarWidget QToolButton#qt_calendar_monthbutton,
        QCalendarWidget QToolButton#qt_calendar_yearbutton {
            color: #ffffff !important;
            font-weight: bold !important;
            font-size: 12px;
            background-color: #162d52 !important;
            border: 1px solid #3b82f6 !important;
            border-radius: 4px;
            padding: 4px 10px;
            margin: 2px;
        }
        QCalendarWidget QToolButton#qt_calendar_monthbutton:hover,
        QCalendarWidget QToolButton#qt_calendar_yearbutton:hover { background-color: #1c6dd0 !important; color: #ffffff !important; }
        QCalendarWidget QToolButton::menu-indicator { image: none; width: 0px; }
        QCalendarWidget QMenu { background-color: #ffffff; color: #1a5fb4; font-weight: bold; font-size: 12px; border: 1px solid #c8d8ec; border-radius: 6px; padding: 4px; }
        QCalendarWidget QMenu::item { color: #1a5fb4; background-color: #ffffff; padding: 6px 18px; }
        QCalendarWidget QMenu::item:selected { background-color: #1a5fb4; color: #ffffff; }
        QCalendarWidget QSpinBox#qt_calendar_yearedit { color: #1a5fb4; font-weight: bold; background-color: #ffffff; border: 1.5px solid #1a5fb4; border-radius: 4px; }
        QCalendarWidget QAbstractItemView:enabled { color: #0d1f3c; background-color: #ffffff; selection-background-color: #1a5fb4; selection-color: #ffffff; }
""")

if __name__ == "__main__":
    setup_crash_logging()
    sys.excepthook = global_exception_handler

    # 1. Initialize Application
    app = QApplication(sys.argv)
    apply_global_styles(app)

    # Pre-flight QtAwesome font integrity check & self-healing (must run after QApplication is initialized)
    try:
        from utils.icon_utils import verify_and_heal_fonts
        FONT_STATUS = verify_and_heal_fonts()
    except Exception as _fhe:
        print(f"[main] Font integrity check warning: {_fhe}")
        FONT_STATUS = {"success": False, "healed_count": 0, "disabled": False}

    def _on_about_to_quit():
        import traceback, datetime
        st = "".join(traceback.format_stack())
        try:
            log_file = get_app_data_dir() / "logs" / "error.log"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"\n{'='*50}\n[{datetime.datetime.now()}] [QUIT TRIGGERED] Application about to quit. Call stack:\n{st}\n")
        except Exception:
            pass

    app.aboutToQuit.connect(_on_about_to_quit)
    
    # Enforce Single Instance (Crash-safe QLockFile)
    from PySide6.QtCore import QLockFile, QDir
    global _lock_file
    _lock_path = QDir.tempPath() + "/havano_pos_2026.lock"
    _lock_file = QLockFile(_lock_path)
    _lock_file.setStaleLockTime(3000)
    
    is_locked = False
    for _ in range(3):
        if _lock_file.tryLock(500):
            is_locked = True
            break
        _lock_file.removeStaleLockFile()

    if not is_locked:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(None, "Already Running", "Havano POS is already running.\n\nPlease check your taskbar or system tray.")
        sys.exit(0)

    app.setApplicationName("Havano POS")
    app.setQuitOnLastWindowClosed(False)
    icon_file = "assets/havano_new_blue.ico"
    try:
        from PySide6.QtCore import Qt
        if app.styleHints().colorScheme() == Qt.ColorScheme.Dark:
            icon_file = "assets/havano_new_white.ico"
    except Exception:
        pass
    app.setWindowIcon(QIcon(resource_path(icon_file)))
    try:
        pass
        # from utils.title_bar import install_global_title_bar_hook
        # install_global_title_bar_hook(app)  # Blue title bar on all dialogs / windows
    except Exception as _e:
        print(f"[main] Title bar hook skipped: {_e}")

    # 2. Show Splash Screen ASAP
    from views.components.sleek_loader import SleekLoaderOverlay
    splash = SleekLoaderOverlay()
    splash.show_loading()
    app.processEvents()

    # 3. Check System Time and Updates
    def check_system_time():
        """Ensure the local system clock is accurate to prevent transaction/sync issues."""
        try:
            import urllib.request
            import datetime
            import email.utils
            
            # Use a fast HTTP HEAD request to Google. We use HTTP (not HTTPS) because 
            # if the clock is off by years, an HTTPS SSL handshake will fail before 
            # we even get the time.
            req = urllib.request.Request("http://google.com", method="HEAD")
            with urllib.request.urlopen(req, timeout=1) as response:
                date_str = response.headers.get('Date')
                if date_str:
                    # Parse RFC 2822 date string (e.g. "Mon, 13 Jul 2026 13:20:00 GMT")
                    parsed_tuple = email.utils.parsedate_tz(date_str)
                    if parsed_tuple:
                        timestamp = email.utils.mktime_tz(parsed_tuple)
                        real_utc = datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc)
                        local_utc = datetime.datetime.now(datetime.timezone.utc)
                        diff = abs((real_utc - local_utc).total_seconds())
                        if diff > 3600: # 1 hour threshold (prevents false positives from ISP/proxy cache drift)
                            return False
        except Exception as e:
            pass # Ignore if offline (e.g., DNS resolution fails or timeout)
        return True

    splash.set_status("Verifying system time...", "Security check")
    app.processEvents()
    if not check_system_time():
        splash.hide_loading()
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.critical(
            None, 
            "System Time Error", 
            "Your computer's date and time are incorrect.\n\n"
            "This will cause severe issues with transaction logging, daily sales reporting, and server synchronization.\n\n"
            "Please fix your Windows clock and time zone settings, then restart the POS."
        )
        sys.exit(1)

    from updater import check_for_updates
    # Run the update check, but the splash is already showing so the user knows it's doing something
    splash.set_status("Checking for updates...", "Network initialization")
    app.processEvents()
    check_for_updates(current_version=APP_VERSION)
    splash.set_status("Initializing...", "")
    app.processEvents()

    # 4. Background Initialization
    app_data_dir = get_app_data_dir()
    app_data_dir.mkdir(exist_ok=True)
    settings_file = app_data_dir / "sql_settings.json"
    # 3.5 Onboarding Check (Reads from json)
    import json
    _saved_mode = None
    if settings_file.exists():
        try:
            _saved_mode = json.loads(settings_file.read_text(encoding="utf-8")).get("system_mode")
        except Exception:
            pass

    if not _saved_mode:
        import json
        print("[startup] No settings found. Auto-configuring as OFFLINE mode with default SQLEXPRESS.")
        default_settings = {
            "auth_mode": "windows",
            "server": ".\\SQLEXPRESS",
            "database": "havano_pos_db",
            "username": "",
            "password": "",
            "system_mode": "offline",
            "api_url": "http://localhost:8000"
        }
        try:
            settings_file.write_text(json.dumps(default_settings), encoding="utf-8")
            _saved_mode = "offline"
        except Exception as e:
            print(f"[startup] Failed to write default settings: {e}")
    else:
        print(f"[startup] System mode already set: {_saved_mode} — skipping onboarding.")

    initialization_done = False
    needs_setup = False

    def on_init_finished(success):
        global initialization_done, needs_setup
        initialization_done = True
        needs_setup = not success

    def on_init_error(err_msg):
        global initialization_done
        initialization_done = True
        print(f"[startup] Initialization error: {err_msg}")
        QMessageBox.critical(None, "Startup Error", f"Database initialization failed:\n\n{err_msg}")

    worker = StartupWorker()
    worker.status_changed.connect(splash.set_status)
    worker.finished.connect(on_init_finished)
    worker.error.connect(on_init_error)
    worker.start()

    # Wait for initialization while keeping UI responsive
    while not initialization_done:
        app.processEvents()
        _timing.sleep(0.05)

    try:
        if splash:
            splash.hide_loading()
    except Exception:
        pass

    # 4. Connection Setup Loop (if needed)
    if needs_setup or not settings_file.exists():
        while True:
            if not settings_file.exists() or not is_connection_valid():
                dlg = SqlSettingsDialog()
                if dlg.exec() != QDialog.Accepted:
                    sys.exit(0)
                continue
            break
        # Run migrations again if setup was just done
        from setup_database import run as run_setup
        run_setup()
        try:
            from models.user import migrate as _user_migrate
            from models.restaurant_order import migrate as _restaurant_migrate
            _user_migrate()
            _restaurant_migrate()
        except Exception as e:
            print(f"[startup] Failed to migrate models after setup: {e}")

    # 5. Site Config UI Check (Main Thread)
    try:
        from services.credentials import get_system_mode
        from services.site_config import check_url_changed, wipe_database, save_current_url
        if check_url_changed():
            if get_system_mode() == "saas":
                confirm = QMessageBox(None)
                confirm.setWindowTitle("Server Configuration Changed")
                confirm.setIcon(QMessageBox.Warning)
                confirm.setText("The API server URL has changed.")
                confirm.setInformativeText("Your local database is tied to the previous server.\n\nTo continue, the local database must be wiped.\nDo you want to proceed?")
                confirm.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                if confirm.exec() == QMessageBox.Yes:
                    wipe_database()
                    save_current_url()
            else:
                save_current_url()
    except Exception:
        pass

    # 5.6 Offline License Gate — only for offline mode
    # (Moved to login_dialog.py so the user can log in first and be prompted for the trial)

    # 6. Login -> Main
    from views.login_dialog import LoginDialog
    login_dlg = LoginDialog()
    if login_dlg.exec() == QDialog.Accepted:
        _logged_user = login_dlg.logged_in_user or {}
        _role = (_logged_user.get("role") or "").lower()
        _allow_pos = _logged_user.get("allow_pos", True)  # default True for safety

        # Admins always get in; non-admins respect the allow_pos flag
        if _role != "admin" and not _allow_pos:
            QMessageBox.warning(
                None, "Access Denied",
                f"Your account does not have permission to access the POS.\n\n"
                f"Please contact your administrator."
            )
            sys.exit(0)

        # -- INITIAL OFFLINE COMPANY SETUP --
        try:
            from models.company_defaults import get_defaults
            defs = get_defaults()
            # If in offline mode and company name is not set
            if str(defs.get("work_offline", "0")) == "1" and not defs.get("company_name", "").strip():
                from views.dialogs.initial_company_setup_dialog import InitialCompanySetupDialog
                setup_dlg = InitialCompanySetupDialog()
                setup_dlg.exec()
        except Exception as e:
            print(f"[Startup] Error checking/showing company setup: {e}")

        try:
            # 💡 Smart Loader: show while MainWindow initializes 💡──────────
            from views.components.sleek_loader import SleekLoaderOverlay
            login_loader = SleekLoaderOverlay()
            login_loader.set_status("Havano POS Loading...")
            login_loader.show_loading()
            
            # Allow the UI to process events and paint the loader before the heavy MainWindow initialization blocks it
            import time
            for _ in range(5):
                app.processEvents()
                time.sleep(0.01)

            from views.main_window import MainWindow
            window = MainWindow(user=_logged_user)
            app._main_window = window  # Prevent garbage collection

            window.showMaximized()
            window.raise_()
            window.activateWindow()

            # Keep the loader visible while MainWindow processes its initial heavy 0ms timers.
            # QTimer ensures it only hides AFTER the event loop unblocks and is running smoothly.
            from PySide6.QtCore import QTimer
            QTimer.singleShot(500, login_loader.hide_loading)
            QTimer.singleShot(1000, login_loader.deleteLater)
            app.processEvents()
            
            # Clear any stale quit events queued during login/loader dialog transitions
            try:
                from PySide6.QtCore import QEvent, QCoreApplication
                QCoreApplication.removePostedEvents(None, QEvent.Quit)
            except Exception:
                pass

            # Defer heavy cache tasks until after UI is fully drawn (run in background thread)
            try:
                from PySide6.QtCore import QTimer
                from services.stock_cache import init_stock_cache
                import threading
                QTimer.singleShot(500, lambda: threading.Thread(target=init_stock_cache, daemon=True).start())
            except Exception as _ce:
                print(f"[Login] Deferred stock cache init error: {_ce}")

            sys.exit(app.exec())
        except Exception as e:
            # Hide loader on error too
            try:
                login_loader.hide_loading()
            except Exception:
                pass
            import traceback
            tb_str = traceback.format_exc()
            QMessageBox.critical(None, "Launch Error", f"Could not start:\n{e}\n\nTraceback:\n{tb_str}")
            sys.exit(1)
    else:
        sys.exit(0)

# Old command (Causes DLL Temp extraction errors):
# pyinstaller --noconfirm --onefile --windowed --icon "assets/havano_new_white.ico" --add-data "assets;assets" --name "HavanoPOS" main.py

# Recommended Build Command (Safely force-closes locked process & compiles):
# my/Scripts/python.exe build_exe.py
# or
# python build_exe.py


