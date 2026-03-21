# views/dialogs/sql_settings_dialog.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QFormLayout, QMessageBox, QGroupBox
)
from PySide6.QtCore import Qt
import pyodbc
import json
import re
import sys
from pathlib import Path

class SqlSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ System Configuration")
        self.setMinimumSize(680, 700)
        self.setModal(True)
        
        self._apply_stylesheet()

        self.settings_file = Path("app_data/sql_settings.json")
        self._load_or_create_default()
        self._build_ui()

    def _apply_stylesheet(self):
        self.setStyleSheet("""
            QDialog { background-color: #F8FAFC; font-family: 'Segoe UI', sans-serif; }
            QLabel { color: #334155; font-size: 13px; }
            QGroupBox {
                background-color: #FFFFFF; border: 1px solid #E2E8F0;
                border-radius: 8px; margin-top: 1.5em; font-weight: bold; color: #0F172A;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 15px; color: #2563EB; }
            QLineEdit, QComboBox {
                min-height: 40px; padding: 0 12px; border: 1px solid #CBD5E1;
                border-radius: 6px; background-color: #FFFFFF; color: #0F172A;
                font-size: 13px;
            }
            QLineEdit:focus, QComboBox:focus { border: 1px solid #3B82F6; background-color: #F0F9FF; }
            QPushButton {
                min-height: 40px; padding: 0 20px; border-radius: 6px;
                background-color: #FFFFFF; border: 1px solid #CBD5E1; color: #334155;
                font-weight: 600; font-size: 13px;
            }
            QPushButton:hover { background-color: #F8FAFC; border-color: #94A3B8; }
            QPushButton#PrimaryButton {
                background-color: #2563EB; color: white; border: none;
            }
            QPushButton#PrimaryButton:hover { background-color: #1D4ED8; }
            QPushButton#TestButton {
                background-color: #F0FDF4; color: #166534; border: 1px solid #BBF7D0;
            }
        """)

    def _load_or_create_default(self):
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.settings_file.exists():
            default = {
                "auth_mode": "windows", "server": ".", "database": "pos_db",
                "username": "", "password": "", "api_url": "", "api_token": "",
                "api_key": "", "api_secret": ""
            }
            self.settings_file.write_text(json.dumps(default, indent=4), encoding="utf-8")

        data = json.loads(self.settings_file.read_text(encoding="utf-8"))
        self.auth_mode = data.get("auth_mode", "windows")
        self.server    = data.get("server",   ".")
        self.database  = data.get("database", "pos_db")
        self.username  = data.get("username", "")
        self.password  = data.get("password", "")
        self.api_url   = data.get("api_url",   "")   # Frappe base URL
        self.api_token = data.get("api_token", "")
        self.api_key   = data.get("api_key",   "")
        self.api_secret = data.get("api_secret", "")

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(30, 30, 30, 30)

        title = QLabel("System Configuration")
        title.setStyleSheet("font-size: 22px; font-weight: 800; color: #0F172A;")
        subtitle = QLabel("Configure your database connection and external API integrations.")
        subtitle.setStyleSheet("color: #64748B; font-size: 13px;")
        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)

        sql_group = QGroupBox("🗄️ SQL Server Database")
        sql_layout = QFormLayout(sql_group)
        sql_layout.setSpacing(15)
        sql_layout.setContentsMargins(20, 25, 20, 20)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Windows Authentication", "SQL Server Authentication"])
        self.mode_combo.setCurrentText(
            "Windows Authentication" if self.auth_mode == "windows"
            else "SQL Server Authentication"
        )
        self.mode_combo.currentTextChanged.connect(self._toggle_auth_fields)

        self.server_input = QLineEdit(self.server)
        self.db_input     = QLineEdit(self.database)
        self.user_input   = QLineEdit(self.username)
        self.pass_input   = QLineEdit(self.password)
        self.pass_input.setEchoMode(QLineEdit.Password)

        sql_layout.addRow("Auth Mode:",     self.mode_combo)
        sql_layout.addRow("Server Name:",   self.server_input)
        sql_layout.addRow("Database Name:", self.db_input)
        sql_layout.addRow("Username:",      self.user_input)
        sql_layout.addRow("Password:",      self.pass_input)
        # Frappe site URL row
        frappe_url_group = QGroupBox("🌐 Frappe Site")
        frappe_url_layout = QFormLayout(frappe_url_group)
        frappe_url_layout.setSpacing(15)
        frappe_url_layout.setContentsMargins(20, 25, 20, 20)
        self.frappe_url_input = QLineEdit(self.api_url)
        self.frappe_url_input.setPlaceholderText("https://apk.havano.cloud")
        frappe_url_layout.addRow("Site URL:", self.frappe_url_input)
        main_layout.addWidget(frappe_url_group)

        main_layout.addWidget(sql_group)

        api_group = QGroupBox("🌐 API Integrations")
        api_layout = QFormLayout(api_group)
        api_layout.setSpacing(15)
        api_layout.setContentsMargins(20, 25, 20, 20)
        self.api_url_input    = QLineEdit(self.api_url)
        self.api_token_input  = QLineEdit(self.api_token)
        self.api_key_input    = QLineEdit(self.api_key)
        self.api_secret_input = QLineEdit(self.api_secret)
        self.api_secret_input.setEchoMode(QLineEdit.Password)
        api_layout.addRow("Base URL:",     self.api_url_input)
        api_layout.addRow("Access Token:", self.api_token_input)
        api_layout.addRow("API Key:",      self.api_key_input)
        api_layout.addRow("API Secret:",   self.api_secret_input)
        main_layout.addWidget(api_group)

        btn_layout = QHBoxLayout()
        test_sql_btn = QPushButton("🔍 Test SQL Connection")
        test_sql_btn.setObjectName("TestButton")
        test_sql_btn.clicked.connect(self._test_sql_connection)
        test_api_btn = QPushButton("🔍 Test API")
        test_api_btn.setObjectName("TestButton")
        test_api_btn.clicked.connect(self._test_api)
        save_btn = QPushButton("Save Configuration")
        save_btn.setObjectName("PrimaryButton")
        save_btn.clicked.connect(self._save_and_close)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(test_sql_btn)
        btn_layout.addWidget(test_api_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        main_layout.addLayout(btn_layout)
        self._toggle_auth_fields()

    def _toggle_auth_fields(self):
        is_sql = self.mode_combo.currentText() == "SQL Server Authentication"
        self.user_input.setEnabled(is_sql)
        self.pass_input.setEnabled(is_sql)
        if not is_sql:
            self.user_input.clear()
            self.pass_input.clear()

    def _get_connection_string(self, include_db=True):
        # Try ODBC Driver 18 first, fall back to 17
        for driver in ("ODBC Driver 18 for SQL Server",
                       "ODBC Driver 17 for SQL Server"):
            if driver in pyodbc.drivers():
                break

        server = self.server_input.text().strip() or "."
        db     = self.db_input.text().strip()     or "pos_db"
        base   = f"DRIVER={{{driver}}};SERVER={server};"
        if include_db:
            base += f"DATABASE={db};"

        if self.mode_combo.currentText() == "Windows Authentication":
            return f"{base}Trusted_Connection=yes;TrustServerCertificate=yes;"
        else:
            uid = self.user_input.text().strip()
            pwd = self.pass_input.text().strip()
            return f"{base}UID={uid};PWD={pwd};TrustServerCertificate=yes;"

    def _test_sql_connection(self):
        try:
            conn = pyodbc.connect(self._get_connection_string(include_db=False), timeout=5)
            conn.close()
            QMessageBox.information(self, "Success", "✅ Server connection successful!")
        except Exception as e:
            QMessageBox.critical(self, "Connection Failed", f"❌ Failed:\n{str(e)}")

    def _test_api(self):
        QMessageBox.information(self, "API Test", "✅ API URL saved.")

    def _save_and_close(self):
        data = {
            "auth_mode": "windows" if self.mode_combo.currentText() == "Windows Authentication" else "sql",
            "server":    self.server_input.text().strip()    or ".",
            "database":  self.db_input.text().strip()        or "pos_db",
            "username":  self.user_input.text().strip(),
            "password":  self.pass_input.text().strip(),
            "api_url":   self.frappe_url_input.text().strip() or self.api_url_input.text().strip(),
            "api_token": self.api_token_input.text().strip(),
            "api_key":   self.api_key_input.text().strip(),
            "api_secret":self.api_secret_input.text().strip(),
        }
        self.settings_file.write_text(json.dumps(data, indent=4), encoding="utf-8")
        try:
            from services.site_config import invalidate_cache
            invalidate_cache()
        except Exception:
            pass
        self._run_migration_script()
        self.accept()

    # =========================================================================
    # _run_migration_script
    #
    # WHAT CHANGED vs the old version:
    #   OLD: dropped + recreated the DB every save, then ran a minimal embedded
    #        SQL script that was missing ~20 columns.
    #
    #   NEW: only creates the DB if it doesn't exist (never drops it).
    #        After ensuring the DB exists it calls setup_database.run() which
    #        has the complete correct schema for all 20 tables, handles nullable
    #        fixes, and seeds the default admin user — all safely with
    #        IF NOT EXISTS guards.
    # =========================================================================
    def _run_migration_script(self):
        db_name = self.db_input.text().strip() or "pos_db"
        try:
            # ── Step 1: Create the database if it doesn't exist ──────────────
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

        try:
            # ── Step 2: Run setup_database.run() for all tables + columns ────
            import setup_database
            setup_database.run()
            print("[sql_settings] setup_database.run() completed.")

        except Exception as e:
            QMessageBox.critical(
                self, "Setup Failed",
                f"❌ Table setup failed:\n{e}\n\n"
                f"The database was created but tables may be incomplete.\n"
                f"Run setup_database.py manually to fix."
            )
            return

        QMessageBox.information(
            self, "Success",
            f"✅ Database '{db_name}' is ready!\n\n"
            f"All tables created and verified.\n"
            f"Default login:  admin / admin123"
        )
        sys.exit(0)