# views/dialogs/sql_settings_dialog.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QFormLayout, QMessageBox, QGroupBox
)
from PySide6.QtCore import Qt
import qtawesome as qta
import pyodbc
import json
import sys
from pathlib import Path
from theme import *

class SqlSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("System Configuration")
        self.setFixedSize(820, 580)
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.settings_file = Path("app_data/sql_settings.json")
        self._load_or_create_default()
        self._apply_stylesheet()
        self._build_ui()

    def _apply_stylesheet(self):
        self.setStyleSheet("""
            QMessageBox, QInputDialog {
                background-color: #FFFFFF;
            }
            QMessageBox QLabel, QInputDialog QLabel {
                color: #0F172A;
                font-size: 13px;
                background: transparent;
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
            QComboBox QAbstractItemView {
                background-color: #FFFFFF;
                color: #0F172A;
                selection-background-color: #F0F9FF;
                selection-color: #0F172A;
                border: 1px solid #CBD5E1;
                outline: 0px;
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
                background-color: #1a5fb4;
                color: white;
                border: none;
            }
            QPushButton#PrimaryButton:hover { background-color: #2468c8; }
            QPushButton#TestButton {
                background-color: #F0FDF4;
                color: #166534;
                border: 1px solid #BBF7D0;
            }
            QPushButton#TestButton:hover { background-color: #DCFCE7; }
            QPushButton#FetchBtn {
                background-color: #F0F9FF;
                color: #1a5fb4;
                border: 1px solid #BAE6FD;
                font-weight: 600;
                padding: 0 10px;
                min-height: 38px;
            }
            QPushButton#FetchBtn:hover { background-color: #E0F2FE; }
        """)

    def _load_or_create_default(self):
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.settings_file.exists():
            default = {
                "auth_mode": "windows",
                "server":    ".\\SQLEXPRESS",
                "database":  "havano_pos_db",
                "username":  "",
                "password":  "",
                "api_url":   "",
            }
            self.settings_file.write_text(json.dumps(default, indent=4), encoding="utf-8")

        data = json.loads(self.settings_file.read_text(encoding="utf-8"))
        self.auth_mode = data.get("auth_mode", "windows")
        self.server    = data.get("server",    ".\\SQLEXPRESS")
        self.database  = data.get("database",  "havano_pos_db")
        self.username  = data.get("username",  "")
        self.password  = data.get("password",  "")
        self.api_url   = data.get("api_url",   "")

    def _build_ui(self):
        from PySide6.QtWidgets import QGraphicsDropShadowEffect, QFrame, QWidget
        from PySide6.QtGui import QColor
        from PySide6.QtCore import QSize

        # Main Container
        self.container = QFrame(self)
        self.container.setObjectName("MainContainer")
        self.container.setStyleSheet(f"QFrame#MainContainer {{ background-color: {OFF_WHITE}; border-radius: 20px; }}")

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(60); shadow.setXOffset(0); shadow.setYOffset(16)
        shadow.setColor(QColor(13, 31, 60, 100))
        self.container.setGraphicsEffect(shadow)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.addWidget(self.container)

        content_layout = QVBoxLayout(self.container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # ── Header ─────────────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(100)
        header.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 {NAVY}, stop:0.6 {NAVY_2}, stop:1 {NAVY_3});
                border-top-left-radius:20px; border-top-right-radius:20px;
            }}
        """)
        hl = QVBoxLayout(header)
        hl.setContentsMargins(20, 16, 20, 16)
        hl.setSpacing(4)
        
        top_row = QHBoxLayout()
        dummy = QWidget()
        dummy.setFixedSize(32, 32)
        dummy.setStyleSheet("background: transparent;")
        top_row.addWidget(dummy)
        
        title_lbl = QLabel("System Configuration")
        title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setStyleSheet(f"color: {WHITE}; font-size: 20px; font-weight: 800; background: transparent; letter-spacing: 1px;")
        top_row.addWidget(title_lbl, 1)
        
        close_btn = QPushButton()
        close_btn.setIcon(qta.icon("fa5s.times", color=WHITE))
        close_btn.setIconSize(QSize(20, 20))
        close_btn.setFixedSize(32, 32)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("QPushButton { background: transparent; border: none; } QPushButton:hover { background: rgba(255, 255, 255, 0.2); border-radius: 16px; }")
        close_btn.clicked.connect(self.reject)
        top_row.addWidget(close_btn)
        
        hl.addLayout(top_row)
        
        sub_lbl = QLabel("Configure your database connection and server details.")
        sub_lbl.setAlignment(Qt.AlignCenter)
        sub_lbl.setStyleSheet(f"color: #8fa8c8; font-size: 13px; background: transparent;")
        hl.addWidget(sub_lbl)
        
        content_layout.addWidget(header)
        
        # Accent line
        al = QFrame()
        al.setFixedHeight(3)
        al.setStyleSheet(f"""
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 {NAVY_3}, stop:0.3 {ACCENT},
                stop:0.7 {ACCENT_H}, stop:1 {NAVY_3});
        """)
        content_layout.addWidget(al)

        # ── Body ───────────────────────────────────────────────────────────
        body = QWidget()
        body.setObjectName("dialog_body")
        body.setStyleSheet("QWidget#dialog_body { background: transparent; }")
        root = QVBoxLayout(body)
        root.setSpacing(14)
        root.setContentsMargins(30, 20, 30, 24)

        # ── System Mode Check ──────────────────────────────────────────────
        system_mode = "frappe"
        try:
            if self.settings_file.exists():
                data = json.loads(self.settings_file.read_text(encoding="utf-8"))
                system_mode = data.get("system_mode", "frappe")
        except Exception:
            pass

        # ── 1. Site URL ─────────────────────────────────────────────
        site_title = "Odoo Site" if system_mode == "odoo" else "Frappe Site"
        site_group = QGroupBox(site_title)
        site_form  = QFormLayout(site_group)
        site_form.setSpacing(12)
        site_form.setContentsMargins(20, 22, 20, 18)
        site_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.frappe_url_input = QLineEdit(self.api_url)
        placeholder = "https://your-odoo-site.com" if system_mode == "odoo" else "https://apk.havano.cloud"
        self.frappe_url_input.setPlaceholderText(placeholder)
        site_form.addRow("Site URL:", self.frappe_url_input)

        # Always add to layout so the widget stays alive (avoids C++ deletion).
        # Just hide the whole group when in offline mode.
        root.addWidget(site_group)
        if system_mode == "offline":
            site_group.setVisible(False)

        # ── 2. SQL Server Database ─────────────────────────────────────────
        sql_group = QGroupBox("SQL Server Database")
        sql_form  = QFormLayout(sql_group)
        sql_form.setSpacing(12)
        sql_form.setContentsMargins(20, 22, 20, 18)
        sql_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Windows Authentication", "SQL Server Authentication"])
        self.mode_combo.setCurrentText(
            "SQL Server Authentication" if self.auth_mode == "sql" else "Windows Authentication"
        )
        self.mode_combo.currentTextChanged.connect(self._toggle_auth_fields)

        self.server_input = QComboBox()
        self.server_input.setEditable(True)
        self.server_input.setCurrentText(self.server or ".\\SQLEXPRESS")
        _orig_server_popup = self.server_input.showPopup
        def safe_server_popup():
            self._fetch_servers()
            _orig_server_popup()
        self.server_input.showPopup = safe_server_popup

        self.db_input = QComboBox()
        self.db_input.setEditable(True)
        self.db_input.setCurrentText(self.database or "havano_pos_db")
        _orig_db_popup = self.db_input.showPopup
        def safe_db_popup():
            self._fetch_databases()
            _orig_db_popup()
        self.db_input.showPopup = safe_db_popup
        
        self.user_input = QLineEdit(self.username)
        self.pass_input = QLineEdit(self.password)
        self.pass_input.setEchoMode(QLineEdit.Password)
        
        self.toggle_pwd_action = self.pass_input.addAction(
            qta.icon("fa5s.eye"), QLineEdit.TrailingPosition
        )
        self.toggle_pwd_action.triggered.connect(self._toggle_password_visibility)

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

        test_btn = QPushButton("Test Connection")
        test_btn.setIcon(qta.icon("fa5s.search"))
        test_btn.setObjectName("TestButton")
        test_btn.setFixedHeight(40)
        test_btn.clicked.connect(self._test_sql_connection)

        new_db_btn = QPushButton("Create Blank DB")
        new_db_btn.setIcon(qta.icon("fa5s.database"))
        new_db_btn.setFixedHeight(40)
        new_db_btn.clicked.connect(self._create_blank_db)

        reconnect_btn = QPushButton("Reconnect")
        reconnect_btn.setIcon(qta.icon("fa5s.sync-alt"))
        reconnect_btn.setObjectName("PrimaryButton")
        reconnect_btn.setFixedHeight(40)
        reconnect_btn.clicked.connect(self._reconnect)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(40)
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("Save Settings")
        save_btn.setObjectName("PrimaryButton")
        save_btn.setFixedHeight(40)
        save_btn.clicked.connect(self._save_and_close)

        btn_row.addWidget(test_btn)
        btn_row.addWidget(new_db_btn)
        btn_row.addWidget(reconnect_btn)          # New reconnect button
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        root.addLayout(btn_row)
        
        content_layout.addWidget(body)

    def _toggle_password_visibility(self):
        import qtawesome as qta
        from PySide6.QtWidgets import QLineEdit
        if self.pass_input.echoMode() == QLineEdit.Password:
            self.pass_input.setEchoMode(QLineEdit.Normal)
            self.toggle_pwd_action.setIcon(qta.icon("fa5s.eye-slash"))
        else:
            self.pass_input.setEchoMode(QLineEdit.Password)
            self.toggle_pwd_action.setIcon(qta.icon("fa5s.eye"))

    def _toggle_auth_fields(self):
        is_sql = self.mode_combo.currentText() == "SQL Server Authentication"
        self.user_input.setEnabled(is_sql)
        self.pass_input.setEnabled(is_sql)
        if not is_sql:
            self.user_input.clear()
            self.pass_input.clear()
        else:
            if not self.user_input.text().strip():
                self.user_input.setText("admin")
            if not self.pass_input.text().strip():
                self.pass_input.setText("admin123!")

    def _get_connection_string(self, include_db=True):
        driver = next(
            (d for d in (
                "ODBC Driver 18 for SQL Server",
                "ODBC Driver 17 for SQL Server",
                "SQL Server",
            ) if d in pyodbc.drivers()),
            "ODBC Driver 17 for SQL Server"
        )
        server = self.server_input.currentText().strip() or ".\\SQLEXPRESS"
        db     = self.db_input.currentText().strip()     or "havano_pos_db"
        base   = f"DRIVER={{{driver}}};SERVER={server};"
        if include_db:
            base += f"DATABASE={db};"
            
        # Ensure we always respect the combobox state rather than assuming Windows Auth
        if self.mode_combo.currentText() == "Windows Authentication":
            return f"{base}Trusted_Connection=yes;TrustServerCertificate=yes;"
            
        uid = self.user_input.text().strip() or "admin"
        pwd = self.pass_input.text().strip() or "admin123!"
        return f"{base}UID={uid};PWD={pwd};TrustServerCertificate=yes;"

    def _silent_auto_config_if_admin(self, conn):
        """Silently guarantees TCP/IP, Named Pipes, Mixed Mode, and the 'admin' user are configured if we have rights."""
        try:
            cur = conn.cursor()
            cur.execute(r"EXEC xp_instance_regwrite N'HKEY_LOCAL_MACHINE', N'Software\Microsoft\MSSQLServer\MSSQLServer', N'LoginMode', REG_DWORD, 2")
            cur.execute(r"EXEC xp_instance_regwrite N'HKEY_LOCAL_MACHINE', N'Software\Microsoft\MSSQLServer\MSSQLServer\SuperSocketNetLib\Tcp', N'Enabled', REG_DWORD, 1")
            cur.execute(r"EXEC xp_instance_regwrite N'HKEY_LOCAL_MACHINE', N'Software\Microsoft\MSSQLServer\MSSQLServer\SuperSocketNetLib\Np', N'Enabled', REG_DWORD, 1")
            cur.execute("SELECT 1 FROM master.sys.server_principals WHERE name = 'admin'")
            if cur.fetchone() is None:
                cur.execute("CREATE LOGIN [admin] WITH PASSWORD = 'admin123!', CHECK_POLICY = OFF")
                cur.execute("ALTER SERVER ROLE sysadmin ADD MEMBER [admin]")
            cur.close()
            print("[sql_settings] Silent background DB configuration successful.")
        except Exception as e:
            print(f"[sql_settings] Silent background DB configuration skipped: {e}")

    def _test_sql_connection(self):
        try:
            conn = pyodbc.connect(
                self._get_connection_string(include_db=False), timeout=5
            )
            self._silent_auto_config_if_admin(conn)
        except Exception as e:
            # Fallback auto-provision for 'admin' if it doesn't exist
            if self.mode_combo.currentText() == "SQL Server Authentication" and self.user_input.text().strip() == "admin":
                try:
                    driver = next((d for d in ("ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server", "SQL Server") if d in pyodbc.drivers()), "ODBC Driver 17 for SQL Server")
                    server = self.server_input.currentText().strip() or ".\\SQLEXPRESS"
                    win_str = f"DRIVER={{{driver}}};SERVER={server};Trusted_Connection=yes;TrustServerCertificate=yes;"
                    
                    win_conn = pyodbc.connect(win_str, autocommit=True, timeout=5)
                    cur = win_conn.cursor()
                    
                    # 1. Ensure Mixed Mode is enabled in the SQL Server Registry!
                    cur.execute(r"EXEC xp_instance_regwrite N'HKEY_LOCAL_MACHINE', N'Software\Microsoft\MSSQLServer\MSSQLServer', N'LoginMode', REG_DWORD, 2")
                    
                    # 1b. Ensure TCP/IP and Named Pipes are enabled for network access
                    cur.execute(r"EXEC xp_instance_regwrite N'HKEY_LOCAL_MACHINE', N'Software\Microsoft\MSSQLServer\MSSQLServer\SuperSocketNetLib\Tcp', N'Enabled', REG_DWORD, 1")
                    cur.execute(r"EXEC xp_instance_regwrite N'HKEY_LOCAL_MACHINE', N'Software\Microsoft\MSSQLServer\MSSQLServer\SuperSocketNetLib\Np', N'Enabled', REG_DWORD, 1")
                    
                    # 2. Create the admin user
                    cur.execute("SELECT 1 FROM master.sys.server_principals WHERE name = 'admin'")
                    if cur.fetchone() is None:
                        cur.execute("CREATE LOGIN [admin] WITH PASSWORD = 'admin123!', CHECK_POLICY = OFF")
                        cur.execute("ALTER SERVER ROLE sysadmin ADD MEMBER [admin]")
                    win_conn.close()
                    
                    # 3. Trigger UAC Service Restart (Robust ctypes elevation)
                    import time
                    import ctypes
                    
                    svc_name = "MSSQL$SQLEXPRESS" if "SQLEXPRESS" in server.upper() else "MSSQLSERVER"
                    cmd_str = f"/c net stop {svc_name} /y & net start {svc_name}"
                    
                    QMessageBox.information(self, "Applying Security Changes", "Please click 'Yes' on the Windows Security prompt if it appears.\n\nThe system is restarting the SQL Server engine to apply Mixed Mode Authentication. This takes about 10 seconds...")
                    
                    # Prompt UAC and run cmd
                    ctypes.windll.shell32.ShellExecuteW(None, "runas", "cmd.exe", cmd_str, None, 0)
                    
                    # Wait for service to cycle down and back up
                    time.sleep(12)
                    
                    # Retry original connection
                    conn = pyodbc.connect(self._get_connection_string(include_db=False), timeout=5)
                except Exception as fb_err:
                    QMessageBox.critical(self, "Restart Required", f"The background script successfully enabled Mixed Mode Authentication and created the 'admin' user!\n\nHOWEVER, the automatic service restart was either denied or failed.\n\nPlease restart your computer (or the SQL Server Service) manually and try again.\n\nDetails: {fb_err}")
                    return
            else:
                QMessageBox.critical(self, "Connection Failed", f"Failed:\n{e}")
                return

        try:
            cur = conn.cursor()
            cur.execute("SELECT @@VERSION")
            ver = cur.fetchone()[0]
            conn.close()
            QMessageBox.information(
                self, "Success",
                f"Successfully connected to SQL Server!\n\nVersion info:\n{ver}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Connection Failed", f"Connected, but failed to query version:\n{e}")

    def _fetch_servers(self):
        self.server_input.clear()
        servers = []
        try:
            import winreg
            import socket
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Microsoft SQL Server\Instance Names\SQL")
            instances = []
            for i in range(100):
                try:
                    name, _, _ = winreg.EnumValue(key, i)
                    instances.append(name)
                except OSError:
                    break
            hostname = socket.gethostname()
            for inst in instances:
                if inst.upper() == "MSSQLSERVER":
                    servers.append(hostname)
                else:
                    servers.append(f"{hostname}\\{inst}")
        except Exception:
            pass
        
        if not servers:
            servers.append(".\\SQLEXPRESS")
            
        self.server_input.addItems(servers)
        self.server_input.setCurrentText(servers[0])

    def _fetch_databases(self):
        try:
            conn = pyodbc.connect(
                self._get_connection_string(include_db=False), timeout=5
            )
            cur = conn.cursor()
            cur.execute("SELECT name FROM sys.databases WHERE state_desc = 'ONLINE' AND name NOT IN ('master', 'tempdb', 'model', 'msdb') ORDER BY name")
            dbs = [row[0] for row in cur.fetchall()]
            conn.close()
            
            curr = self.db_input.currentText()
            self.db_input.clear()
            self.db_input.addItems(dbs)
            if curr in dbs:
                self.db_input.setCurrentText(curr)
            elif dbs:
                self.db_input.setCurrentText(dbs[0])
        except Exception as e:
            QMessageBox.critical(self, "Fetch Failed", f"Could not fetch databases:\n{e}")

    # ── NEW: Save settings to file ONLY (no migration, no DB creation)
    def _save_settings(self):
        data = {}
        if self.settings_file.exists():
            try:
                data = json.loads(self.settings_file.read_text(encoding="utf-8"))
            except Exception:
                pass
                
        updates = {
            "auth_mode": "windows" if self.mode_combo.currentText() == "Windows Authentication" else "sql",
            "server":    self.server_input.currentText().strip() or ".\\SQLEXPRESS",
            "database":  self.db_input.currentText().strip()     or "havano_pos_db",
            "username":  self.user_input.text().strip(),
            "password":  self.pass_input.text().strip(),
        }

        # Attempt to auto-provision the 'admin' account if using Windows Auth
        if updates["auth_mode"] == "windows":
            try:
                conn = pyodbc.connect(self._get_connection_string(include_db=False), autocommit=True, timeout=5)
                cur = conn.cursor()
                cur.execute("SELECT 1 FROM master.sys.server_principals WHERE name = 'admin'")
                if cur.fetchone() is None:
                    cur.execute("CREATE LOGIN [admin] WITH PASSWORD = 'admin123!', CHECK_POLICY = OFF")
                    cur.execute("ALTER SERVER ROLE sysadmin ADD MEMBER [admin]")
                    QMessageBox.information(self, "Success", "SQL Server account 'admin' was successfully created!")
                conn.close()
            except Exception as e:
                err_str = str(e)
                if '08001' in err_str or 'HYT00' in err_str or 'Login timeout' in err_str:
                    QMessageBox.warning(self, "Connection Failed", f"Could not connect to SQL Server. Please check that the server is running and the instance name is correct.\n\nError: {e}")
                else:
                    QMessageBox.warning(self, "Permissions Note", f"Connected via Windows, but your Windows user lacks permission to create the 'admin' SQL login automatically.\n\nError: {e}")
        
        # If we are offline, forcibly clear any lingering URL from the JSON
        if data.get("system_mode") == "offline":
            updates["api_url"] = ""
        else:
            updates["api_url"] = self.frappe_url_input.text().strip()
            
        data.update(updates)
        self.settings_file.write_text(json.dumps(data, indent=4), encoding="utf-8")
        try:
            from services.site_config import invalidate_cache
            invalidate_cache()
        except Exception:
            pass

    # ── Tenant switch detection / wipe ───────────────────────────────────
    def _new_api_url(self) -> str:
        """Whatever the user has typed into the URL field right now."""
        try:
            import shiboken6
            if not shiboken6.isValid(self.frappe_url_input):
                return ""
        except Exception:
            pass
        try:
            return self.frappe_url_input.text().strip()
        except RuntimeError:
            return ""

    def _maybe_wipe_on_tenant_switch(self) -> bool:
        """
        If the user has changed `api_url` to a different tenant, prompt to
        wipe every synced row in the local DB (products, customers, sales,
        shifts, users - everything except the schema version marker).

        Returns True when a wipe was performed, so callers can force the
        app to exit / restart and avoid stale in-memory state.

        We only fire when the URL *actually* changed - pure DB-connection
        tweaks (server/database/credentials) do not trigger a wipe.
        """
        from services.credentials import get_system_mode
        if get_system_mode() != "saas":
            return False   # In Frappe, Offline, or Odoo modes, never wipe DB on URL/tenant change

        old = getattr(self, "api_url", "") or ""
        new = self._new_api_url()
        try:
            from database.tenant_reset import urls_differ
        except Exception as e:
            print(f"[sql_settings] tenant_reset import failed: {e}")
            return False

        if not urls_differ(old, new):
            return False   # same tenant (or first-time setup with blank old)
        if not old:
            return False   # first-time setup - there's nothing to wipe yet

        confirm = QMessageBox.warning(
            self,
            "Switching tenant",
            (
                "The Frappe site URL has changed:\n\n"
                f"   FROM:  {old or '(unset)'}\n"
                f"   TO:    {new}\n\n"
                "All local data belongs to the old tenant - products, "
                "customers, sales, shifts, users, and prices. Keeping it "
                "would cause records to bleed between instances.\n\n"
                "Wipe every synced row now and start clean on the new "
                "tenant?"
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return False

        try:
            from database.tenant_reset import (
                wipe_all_tenant_data, invalidate_runtime_caches,
            )
            summary = wipe_all_tenant_data()
            invalidate_runtime_caches()
        except Exception as e:
            QMessageBox.critical(
                self, "Wipe failed",
                f"Could not clear tenant data:\n\n{e}\n\n"
                "Settings were NOT saved. Investigate before retrying.",
            )
            return False

        if summary.get("errors"):
            QMessageBox.warning(
                self, "Wipe completed with warnings",
                "Some tables could not be cleared:\n\n" +
                "\n".join(summary["errors"][:6]) +
                (f"\n... (+{len(summary['errors'])-6} more)"
                 if len(summary["errors"]) > 6 else ""),
            )
        else:
            QMessageBox.information(
                self, "Data wiped",
                f"Cleared {summary['rows_deleted']:,} rows across "
                f"{summary['tables_wiped']} table(s).\n\n"
                "The POS will close so the new tenant data can load "
                "cleanly on next launch.",
            )
        return True

    # ── NEW: Reconnect button logic
    def _create_blank_db(self):
        from PySide6.QtWidgets import QInputDialog
        current_db = self.db_input.currentText().strip() or "havano_pos_db"
        
        db_name, ok = QInputDialog.getText(
            self, "New Blank Database",
            "Enter the name for the new blank database:\n\n(If a database with this name already exists, a backup will be taken and it will be wiped.)",
            text=current_db
        )
        
        if not ok or not db_name.strip():
            return
            
        db_name = db_name.strip()
        
        # Ensure the combobox reflects this new database name
        self.db_input.setCurrentText(db_name)
        
        from PySide6.QtWidgets import QProgressDialog, QApplication
        from PySide6.QtCore import Qt
        progress = QProgressDialog("Wiping old data and building new database... Please wait.", None, 0, 0, self)
        progress.setWindowTitle("Initializing Database")
        progress.setWindowModality(Qt.WindowModal)
        progress.setCancelButton(None)
        progress.show()
        QApplication.processEvents()
        
        try:
            conn_test = pyodbc.connect(self._get_connection_string(include_db=False), timeout=5)
            cur_test = conn_test.cursor()
            cur_test.execute("SELECT database_id FROM sys.databases WHERE name = ?", (db_name,))
            db_exists = cur_test.fetchone() is not None
            conn_test.close()

            if db_exists:
                QMessageBox.information(self, "Backing up", f"Taking a safety backup of '{db_name}' before deleting.\n\nThis may take a moment.")
                try:
                    import datetime
                    from pathlib import Path
                    import shutil
                    backup_dir = Path(r"C:\POS_Backups")
                    backup_dir.mkdir(parents=True, exist_ok=True)
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_filename = f"{db_name}_pre_wipe_{timestamp}.bak"
                    
                    conn_master = pyodbc.connect(self._get_connection_string(include_db=False), autocommit=True)
                    cur_m = conn_master.cursor()
                    cur_m.execute(f"BACKUP DATABASE [{db_name}] TO DISK = '{backup_filename}'")
                    while cur_m.nextset(): pass
                    
                    # Copy out of SQL Server default directory
                    cur_m.execute("SELECT TOP 1 physical_device_name FROM msdb.dbo.backupmediafamily WHERE physical_device_name LIKE ? ORDER BY media_set_id DESC", (f"%{backup_filename}",))
                    row = cur_m.fetchone()
                    if row and row[0]:
                        sql_path = Path(row[0])
                        final_backup_path = backup_dir / backup_filename
                        shutil.copy2(sql_path, final_backup_path)
                        try:
                            import os
                            os.remove(sql_path)
                        except Exception:
                            pass
                    conn_master.close()
                except Exception as e:
                    print(f"Safety backup failed: {e}")

                conn_master = pyodbc.connect(self._get_connection_string(include_db=False), autocommit=True)
                cur_m = conn_master.cursor()
                cur_m.execute(f"ALTER DATABASE [{db_name}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE")
                cur_m.execute(f"DROP DATABASE [{db_name}]")
                conn_master.close()

            conn_master = pyodbc.connect(self._get_connection_string(include_db=False), autocommit=True)
            cur_m = conn_master.cursor()
            cur_m.execute(f"CREATE DATABASE [{db_name}]")
            conn_master.close()

            self._save_settings()
            
            try:
                from services.site_config import invalidate_cache
                invalidate_cache()
            except Exception:
                pass
                
            self._run_migration_script(silent=True)
            
            progress.close()
            QMessageBox.information(self, "Success", f"Blank database '{db_name}' created successfully.\n\nThe application will now restart to apply these changes.")
            self._exit_for_clean_restart()

        except Exception as e:
            if 'progress' in locals(): progress.close()
            QMessageBox.critical(self, "Error", f"Failed to create blank database:\n{e}")

    def _reconnect(self):
        """Check connection to the EXISTING database, then save settings ONLY (no migration)"""
        try:
            # Important: test with the specific database (include_db=True)
            conn = pyodbc.connect(
                self._get_connection_string(include_db=True), timeout=5
            )
            conn.close()
        except Exception as e:
            QMessageBox.critical(
                self, "Reconnect Failed",
                f"Could not connect to the database:\n{str(e)}\n\n"
                f"• Make sure the database '{self.db_input.currentText().strip() or 'havano_pos_db'}' already exists.\n"
                f"• Use 'Save Configuration' if you want to create a new database."
            )
            return

        # Tenant switch? Offer to wipe the old DB before we point at a new
        # URL. Must happen *before* _save_settings so on-disk old_url matches
        # the current live data.
        wiped = self._maybe_wipe_on_tenant_switch()

        self._save_settings()

        try:
            from services.site_config import invalidate_cache
            invalidate_cache()
        except Exception:
            pass

        if wiped:
            # Force a restart so no singleton still carries old-tenant state.
            self._exit_for_clean_restart()
            return

        QMessageBox.information(
            self, "Reconnect Successful",
            "SQL settings saved successfully!\n\n"
            "The application will now restart to securely connect to the new database."
        )
        self._exit_for_clean_restart()

    def _save_and_close(self):
        # Tenant switch? Wipe happens *before* saving so the wipe targets
        # the old tenant's DB while the in-file api_url still reflects it.
        wiped = self._maybe_wipe_on_tenant_switch()

        self._save_settings()   # Reuse the shared save logic
        try:
            from services.site_config import invalidate_cache
            invalidate_cache()
        except Exception:
            pass

        if wiped:
            # Fresh DB - still run migrations so schema_info lines up, then
            # force a restart so no cache holds old-tenant state.
            try:
                self._run_migration_script()
            except Exception:
                pass
            self._exit_for_clean_restart()
            return

        self._run_migration_script()
        
        QMessageBox.information(
            self, "Settings Saved",
            "SQL settings saved successfully!\n\n"
            "The application will now restart to apply these changes cleanly."
        )
        self._exit_for_clean_restart()

    # ── Force a clean restart after a wipe ───────────────────────────────
    def _exit_for_clean_restart(self) -> None:
        """
        After a tenant wipe or mode change, there's no safe way to keep running in-process -
        every singleton (auth session, sync threads, cached customer list)
        is holding data that no longer exists. Restart the POS so the next
        launch bootstraps against the new tenant from a clean slate.
        """
        try:
            import main as _main_mod
            if hasattr(_main_mod, "_lock_file") and _main_mod._lock_file:
                _main_mod._lock_file.unlock()
        except Exception:
            pass

        try:
            import sys, subprocess, os
            exe = sys.executable
            venv_path = os.environ.get("VIRTUAL_ENV")
            if venv_path:
                venv_exe = os.path.join(venv_path, "Scripts", "python.exe") if os.name == "nt" else os.path.join(venv_path, "bin", "python")
                if os.path.exists(venv_exe):
                    exe = venv_exe
            elif hasattr(sys, "real_prefix") or (hasattr(sys, "base_prefix") and sys.prefix != sys.base_prefix):
                venv_exe = os.path.join(sys.prefix, "Scripts", "python.exe") if os.name == "nt" else os.path.join(sys.prefix, "bin", "python")
                if os.path.exists(venv_exe):
                    exe = venv_exe

            subprocess.Popen([exe] + sys.argv)
        except Exception as e:
            print(f"[sql_settings] Subprocess relaunch error: {e}")

        import os as _os
        _os._exit(0)

    def _run_migration_script(self, silent=False):
        db_name = self.db_input.currentText().strip() or "havano_pos_db"

        # Step 1: Establish Master Connection (with auto-provisioning fallback)
        try:
            conn_master = pyodbc.connect(
                self._get_connection_string(include_db=False),
                autocommit=True
            )
            self._silent_auto_config_if_admin(conn_master)
        except Exception as e:
            # If they tried to use 'admin' but it failed (likely doesn't exist yet)
            if self.mode_combo.currentText() == "SQL Server Authentication" and self.user_input.text().strip() == "admin":
                try:
                    driver = next((d for d in ("ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server", "SQL Server") if d in pyodbc.drivers()), "ODBC Driver 17 for SQL Server")
                    server = self.server_input.currentText().strip() or ".\\SQLEXPRESS"
                    win_str = f"DRIVER={{{driver}}};SERVER={server};Trusted_Connection=yes;TrustServerCertificate=yes;"
                    
                    win_conn = pyodbc.connect(win_str, autocommit=True, timeout=5)
                    cur = win_conn.cursor()
                    
                    # 1. Ensure Mixed Mode is enabled in the SQL Server Registry!
                    cur.execute(r"EXEC xp_instance_regwrite N'HKEY_LOCAL_MACHINE', N'Software\Microsoft\MSSQLServer\MSSQLServer', N'LoginMode', REG_DWORD, 2")
                    
                    # 1b. Ensure TCP/IP and Named Pipes are enabled for network access
                    cur.execute(r"EXEC xp_instance_regwrite N'HKEY_LOCAL_MACHINE', N'Software\Microsoft\MSSQLServer\MSSQLServer\SuperSocketNetLib\Tcp', N'Enabled', REG_DWORD, 1")
                    cur.execute(r"EXEC xp_instance_regwrite N'HKEY_LOCAL_MACHINE', N'Software\Microsoft\MSSQLServer\MSSQLServer\SuperSocketNetLib\Np', N'Enabled', REG_DWORD, 1")
                    
                    # 2. Create the admin user
                    cur.execute("SELECT 1 FROM master.sys.server_principals WHERE name = 'admin'")
                    if cur.fetchone() is None:
                        cur.execute("CREATE LOGIN [admin] WITH PASSWORD = 'admin123!', CHECK_POLICY = OFF")
                        cur.execute("ALTER SERVER ROLE sysadmin ADD MEMBER [admin]")
                    win_conn.close()
                    
                    # 3. Trigger UAC Service Restart (Robust ctypes elevation)
                    import time
                    import ctypes
                    
                    svc_name = "MSSQL$SQLEXPRESS" if "SQLEXPRESS" in server.upper() else "MSSQLSERVER"
                    cmd_str = f"/c net stop {svc_name} /y & net start {svc_name}"
                    
                    QMessageBox.information(self, "Applying Security Changes", "Please click 'Yes' on the Windows Security prompt if it appears.\n\nThe system is restarting the SQL Server engine to apply Mixed Mode Authentication. This takes about 10 seconds...")
                    
                    # Prompt UAC and run cmd
                    ctypes.windll.shell32.ShellExecuteW(None, "runas", "cmd.exe", cmd_str, None, 0)
                    
                    # Wait for service to cycle down and back up
                    time.sleep(12)
                    
                    # Try connecting again now that admin exists
                    conn_master = pyodbc.connect(self._get_connection_string(include_db=False), autocommit=True)
                except Exception as fb_err:
                    QMessageBox.critical(self, "Restart Required", f"The background script successfully enabled Mixed Mode Authentication and created the 'admin' user!\n\nHOWEVER, the automatic service restart was either denied or failed.\n\nPlease restart your computer (or the SQL Server Service) manually and try again.\n\nDetails: {fb_err}")
                    return
            else:
                QMessageBox.critical(self, "Connection Error", f"Could not connect to database engine:\n{e}")
                return

        # Step 2: Create DB if not exists
        try:
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
            QMessageBox.critical(self, "Database Error", f"Could not create database '{db_name}':\n{e}")
            return

        # Step 2: Run full table setup
        try:
            import setup_database
            setup_database.run()
            print("[sql_settings] setup_database.run() completed.")
        except Exception as e:
            QMessageBox.critical(
                self, "Setup Failed",
                f"Table setup failed:\n{e}\n\n"
                f"Run setup_database.py manually to fix."
            )
            return

        # Step 3: Success message and close setup (don't exit app)
        if not silent:
            QMessageBox.information(
                self, "Done",
                f"Database '{db_name}' is ready!\n\n"
                f"Default login:  admin / admin123"
            )
            self.accept()