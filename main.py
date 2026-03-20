# main.py
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication, QDialog
from PySide6.QtGui import QIcon

from views.main_window import MainWindow
from views.login_dialog import LoginDialog
from database.db import is_connection_valid
from views.dialogs.sql_settings_dialog import SqlSettingsDialog


if __name__ == "__main__":
    # ==================== 1. Create QApplication FIRST (required by Qt) ====================
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("assets/havano-logo.jpeg"))

    # Apply your dark theme for the main POS
    app.setStyleSheet("""
        QMainWindow { background-color: #1e1e2e; }
        QWidget {
            background-color: #1e1e2e;
            color: #cdd6f4;
            font-size: 14px;
            font-family: 'Segoe UI';
        }
        QPushButton {
            background-color: #313244;
            color: #cdd6f4;
            border: 1px solid #45475a;
            border-radius: 8px;
            padding: 10px;
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
            color: #cdd6f4;
            border: 1px solid #45475a;
            border-radius: 8px;
            padding: 8px;
        }
        QLineEdit:focus { border: 1px solid #cba6f7; }
        QListWidget {
            background-color: #181825;
            border: 1px solid #45475a;
            border-radius: 8px;
            padding: 6px;
        }
        QListWidget::item { padding: 8px; border-radius: 4px; }
        QListWidget::item:hover { background-color: #313244; }
        QTabBar::tab {
            background-color: #313244;
            color: #6c7086;
            padding: 10px 24px;
            border-radius: 6px;
            margin-right: 4px;
        }
        QTabBar::tab:selected {
            background-color: #cba6f7;
            color: #1e1e2e;
        }
        QTableWidget {
            background-color: #181825;
            border: 1px solid #45475a;
            border-radius: 8px;
            gridline-color: #313244;
        }
        QHeaderView::section {
            background-color: #313244;
            color: #cdd6f4;
            padding: 8px;
            border: none;
        }
        QLabel { color: #cdd6f4; background: transparent; }
        QScrollArea { border: none; }
        QDialog { background-color: #1e1e2e; }
    """)

    # ==================== 2. FIRST CHECK: Does sql_settings.json exist? ====================
    settings_file = Path("app_data/sql_settings.json")
    
    if not settings_file.exists():
        print("⚠️  sql_settings.json not found → opening SQL Settings...")
        dlg = SqlSettingsDialog()
        if dlg.exec() != QDialog.Accepted:
            print("❌ User cancelled settings. Exiting.")
            sys.exit(0)

    # ==================== 3. File exists → check connection ====================
    elif not is_connection_valid():
        print("⚠️  Settings file exists but connection failed → opening SQL Settings...")
        dlg = SqlSettingsDialog()
        if dlg.exec() != QDialog.Accepted:
            print("❌ User cancelled settings. Exiting.")
            sys.exit(0)

    # ==================== 4. Database is ready → show Login ====================
    login = LoginDialog()
    if login.exec() == QDialog.Accepted:
        window = MainWindow(user=login.logged_in_user)
        window.show()
        sys.exit(app.exec())
    else:
        sys.exit(0)