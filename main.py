# main.py
import sys
from PySide6.QtWidgets import QApplication, QDialog
from PySide6.QtGui import QIcon
from views.main_window import MainWindow
from views.login_dialog import LoginDialog
from database.db import get_connection   # confirms DB is reachable on startup

if __name__ == "__main__":
    # Verify DB connection on startup — crashes early with a clear message if not reachable
    try:
        conn = get_connection()
        conn.close()
    except Exception as e:
        print(f"[main] ❌  Cannot connect to SQL Server: {e}")
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("assets/havano-logo.jpeg"))

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

    # ── show login first ──────────────────────────
    login = LoginDialog()
    if login.exec() == QDialog.Accepted:
        window = MainWindow(user=login.logged_in_user)
        window.show()
        sys.exit(app.exec())
    # if login closed without success — app exits silently