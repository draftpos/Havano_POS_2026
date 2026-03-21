# views/dialogs/sql_settings_dialog.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QFormLayout, QMessageBox, QGroupBox
)
from PySide6.QtCore import Qt
import pyodbc
import json
import sys
from pathlib import Path


class SqlSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ System Configuration")
        self.setFixedSize(680, 560)
        self.setModal(True)
        self._apply_stylesheet()
        self.settings_file = Path("app_data/sql_settings.json")
        self._load_or_create_default()
        self._build_ui()

    def _apply_stylesheet(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #F8FAFC;
                font-family: 'Segoe UI', sans-serif;
            }
            QLabel {
                color: #334155;
                font-size: 13px;
                background: transparent;
            }
            QGroupBox {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                margin-top: 1.2em;
                font-weight: bold;
                color: #0F172A;
                font-size: 13px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 6px;
                color: #2563EB;
            }
            QLineEdit, QComboBox {
                min-height: 38px;
                padding: 0 12px;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                background-color: #FFFFFF;
                color: #0F172A;
                font-size: 13px;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #3B82F6;
                background-color: #F0F9FF;
            }
            QLineEdit:disabled {
                background-color: #F1F5F9;
                color: #94A3B8;
            }
            QPushButton {
                min-height: 40px;
                padding: 0 20px;
                border-radius: 6px;
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                color: #334155;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #F8FAFC; border-color: #94A3B8; }
            QPushButton#PrimaryButton {
                background-color: #2563EB;
                color: white;
                border: none;
            }
            QPushButton#PrimaryButton:hover { background-color: #1D4ED8; }
            QPushButton#TestButton {
                background-color: #F0FDF4;
                color: #166534;
                border: 1px solid #BBF7D0;
            }
            QPushButton#TestButton:hover { background-color: #DCFCE7; }
        """)

    def _load_or_create_default(self):
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.settings_file.exists():
            default = {
                "auth_mode": "windows",
                "server":    ".\\SQLEXPRESS",
                "database":  "pos_db",
                "username":  "",
                "password":  "",
                "api_url":   "",
            }
            self.settings_file.write_text(json.dumps(default, indent=4), encoding="utf-8")

        data = json.loads(self.settings_file.read_text(encoding="utf-8"))
        self.auth_mode = data.get("auth_mode", "windows")
        self.server    = data.get("server",    ".\\SQLEXPRESS")
        self.database  = data.get("database",  "pos_db")
        self.username  = data.get("username",  "")
        self.password  = data.get("password",  "")
        self.api_url   = data.get("api_url",   "")

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(30, 28, 30, 24)

        # ── Title ──────────────────────────────────────────────────────────
        title = QLabel("System Configuration")
        title.setStyleSheet(
            "font-size: 20px; font-weight: 800; color: #0F172A; background: transparent;"
        )
        subtitle = QLabel("Configure your database connection and Frappe site URL.")
        subtitle.setStyleSheet("color: #64748B; font-size: 12px; background: transparent;")
        root.addWidget(title)
        root.addWidget(subtitle)

        # ── 1. Frappe Site URL ─────────────────────────────────────────────
        site_group = QGroupBox("🌐  Frappe Site")
        site_form  = QFormLayout(site_group)
        site_form.setSpacing(12)
        site_form.setContentsMargins(20, 22, 20, 18)
        site_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.frappe_url_input = QLineEdit(self.api_url)
        self.frappe_url_input.setPlaceholderText("https://apk.havano.cloud")
        site_form.addRow("Site URL:", self.frappe_url_input)
        root.addWidget(site_group)

        # ── 2. SQL Server Database ─────────────────────────────────────────
        sql_group = QGroupBox("🗄️  SQL Server Database")
        sql_form  = QFormLayout(sql_group)
        sql_form.setSpacing(12)
        sql_form.setContentsMargins(20, 22, 20, 18)
        sql_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Windows Authentication", "SQL Server Authentication"])
        self.mode_combo.setCurrentText(
            "Windows Authentication" if self.auth_mode == "windows"
            else "SQL Server Authentication"
        )
        self.mode_combo.currentTextChanged.connect(self._toggle_auth_fields)

        self.server_input = QLineEdit(self.server)
        self.server_input.setPlaceholderText(".\\SQLEXPRESS")
        self.db_input = QLineEdit(self.database)
        self.db_input.setPlaceholderText("pos_db")
        self.user_input = QLineEdit(self.username)
        self.pass_input = QLineEdit(self.password)
        self.pass_input.setEchoMode(QLineEdit.Password)

        sql_form.addRow("Auth Mode:",     self.mode_combo)
        sql_form.addRow("Server Name:",   self.server_input)
        sql_form.addRow("Database Name:", self.db_input)
        sql_form.addRow("Username:",      self.user_input)
        sql_form.addRow("Password:",      self.pass_input)
        root.addWidget(sql_group)

        self._toggle_auth_fields()
        root.addStretch()

        # ── Buttons ────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        test_btn = QPushButton("🔍 Test SQL Connection")
        test_btn.setObjectName("TestButton")
        test_btn.setFixedHeight(40)
        test_btn.clicked.connect(self._test_sql_connection)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(40)
        cancel_btn.setFixedWidth(90)
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("Save Configuration")
        save_btn.setObjectName("PrimaryButton")
        save_btn.setFixedHeight(40)
        save_btn.clicked.connect(self._save_and_close)

        btn_row.addWidget(test_btn)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        root.addLayout(btn_row)

    def _toggle_auth_fields(self):
        is_sql = self.mode_combo.currentText() == "SQL Server Authentication"
        self.user_input.setEnabled(is_sql)
        self.pass_input.setEnabled(is_sql)
        if not is_sql:
            self.user_input.clear()
            self.pass_input.clear()

    def _get_connection_string(self, include_db=True):
        driver = next(
            (d for d in (
                "ODBC Driver 18 for SQL Server",
                "ODBC Driver 17 for SQL Server",
                "SQL Server",
            ) if d in pyodbc.drivers()),
            "ODBC Driver 17 for SQL Server"
        )
        server = self.server_input.text().strip() or ".\\SQLEXPRESS"
        db     = self.db_input.text().strip()     or "pos_db"
        base   = f"DRIVER={{{driver}}};SERVER={server};"
        if include_db:
            base += f"DATABASE={db};"
        if self.mode_combo.currentText() == "Windows Authentication":
            return f"{base}Trusted_Connection=yes;TrustServerCertificate=yes;"
        uid = self.user_input.text().strip()
        pwd = self.pass_input.text().strip()
        return f"{base}UID={uid};PWD={pwd};TrustServerCertificate=yes;"

    def _test_sql_connection(self):
        try:
            conn = pyodbc.connect(
                self._get_connection_string(include_db=False), timeout=5
            )
            conn.close()
            QMessageBox.information(self, "Success", "✅ SQL Server connection successful!")
        except Exception as e:
            QMessageBox.critical(self, "Connection Failed", f"❌ Failed:\n{str(e)}")

    def _save_and_close(self):
        data = {
            "auth_mode": "windows" if self.mode_combo.currentText() == "Windows Authentication" else "sql",
            "server":    self.server_input.text().strip() or ".\\SQLEXPRESS",
            "database":  self.db_input.text().strip()     or "pos_db",
            "username":  self.user_input.text().strip(),
            "password":  self.pass_input.text().strip(),
            "api_url":   self.frappe_url_input.text().strip(),
        }
        self.settings_file.write_text(json.dumps(data, indent=4), encoding="utf-8")
        try:
            from services.site_config import invalidate_cache
            invalidate_cache()
        except Exception:
            pass
        self._run_migration_script()

    def _run_migration_script(self):
        db_name = self.db_input.text().strip() or "pos_db"

        # Step 1: Create DB if not exists
        try:
            conn_master = pyodbc.connect(
                self._get_connection_string(include_db=False),
                autocommit=True
            )
            cur = conn_master.cursor()
            cur.execute(f"""
                IF NOT EXISTS (
                    SELECT name FROM sys.databases WHERE name = N'{db_name}'
                )
                CREATE DATABASE [{db_name}]
            """)
            cur.close()
            conn_master.close()
            print(f"[sql_settings] Database '{db_name}' ready.")
        except Exception as e:
            QMessageBox.critical(
                self, "Database Error",
                f"❌ Could not create database '{db_name}':\n{e}"
            )
            return

        # Step 2: Run full table setup
        try:
            import setup_database
            setup_database.run()
            print("[sql_settings] setup_database.run() completed.")
        except Exception as e:
            QMessageBox.critical(
                self, "Setup Failed",
                f"❌ Table setup failed:\n{e}\n\n"
                f"Run setup_database.py manually to fix."
            )
            return

        QMessageBox.information(
            self, "Done",
            f"✅ Database '{db_name}' is ready!\n\n"
            f"Default login:  admin / admin123"
        )
        self.accept()
        sys.exit(0)