# # views/dialogs/sql_settings_dialog.py
# from PySide6.QtWidgets import (
#     QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
#     QPushButton, QComboBox, QFormLayout, QMessageBox, QGroupBox
# )
# from PySide6.QtCore import Qt
# import pyodbc
# import json
# import re
# import sys
# from pathlib import Path

# class SqlSettingsDialog(QDialog):
#     def __init__(self, parent=None):
#         super().__init__(parent)
#         self.setWindowTitle("⚙️ System Configuration")
#         self.setMinimumSize(680, 700)
#         self.setModal(True)
        
#         self._apply_stylesheet()

#         self.settings_file = Path("app_data/sql_settings.json")
#         self._load_or_create_default()
#         self._build_ui()

#     def _apply_stylesheet(self):
#         self.setStyleSheet("""
#             QDialog { background-color: #F8FAFC; font-family: 'Segoe UI', sans-serif; }
#             QLabel { color: #334155; font-size: 13px; }
#             QGroupBox {
#                 background-color: #FFFFFF; border: 1px solid #E2E8F0;
#                 border-radius: 8px; margin-top: 1.5em; font-weight: bold; color: #0F172A;
#             }
#             QGroupBox::title { subcontrol-origin: margin; left: 15px; color: #2563EB; }
#             QLineEdit, QComboBox {
#                 min-height: 40px; padding: 0 12px; border: 1px solid #CBD5E1;
#                 border-radius: 6px; background-color: #FFFFFF; color: #0F172A;
#                 font-size: 13px;
#             }
#             QLineEdit:focus, QComboBox:focus { border: 1px solid #3B82F6; background-color: #F0F9FF; }
#             QPushButton {
#                 min-height: 40px; padding: 0 20px; border-radius: 6px;
#                 background-color: #FFFFFF; border: 1px solid #CBD5E1; color: #334155;
#                 font-weight: 600; font-size: 13px;
#             }
#             QPushButton:hover { background-color: #F8FAFC; border-color: #94A3B8; }
#             QPushButton#PrimaryButton {
#                 background-color: #2563EB; color: white; border: none;
#             }
#             QPushButton#PrimaryButton:hover { background-color: #1D4ED8; }
#             QPushButton#TestButton {
#                 background-color: #F0FDF4; color: #166534; border: 1px solid #BBF7D0;
#             }
#         """)

#     def _load_or_create_default(self):
#         self.settings_file.parent.mkdir(parents=True, exist_ok=True)
#         if not self.settings_file.exists():
#             default = {
#                 "auth_mode": "windows", "server": ".", "database": "POS_DB",
#                 "username": "", "password": "", "api_url": "", "api_token": "",
#                 "api_key": "", "api_secret": ""
#             }
#             self.settings_file.write_text(json.dumps(default, indent=4), encoding="utf-8")

#         data = json.loads(self.settings_file.read_text(encoding="utf-8"))
#         self.auth_mode = data.get("auth_mode", "windows")
#         self.server = data.get("server", ".")
#         self.database = data.get("database", "POS_DB")
#         self.username = data.get("username", "")
#         self.password = data.get("password", "")
#         self.api_url = data.get("api_url", "")
#         self.api_token = data.get("api_token", "")
#         self.api_key = data.get("api_key", "")
#         self.api_secret = data.get("api_secret", "")

#     def _build_ui(self):
#         main_layout = QVBoxLayout(self)
#         main_layout.setSpacing(20)
#         main_layout.setContentsMargins(30, 30, 30, 30)

#         title = QLabel("System Configuration")
#         title.setStyleSheet("font-size: 22px; font-weight: 800; color: #0F172A;")
#         subtitle = QLabel("Configure your database connection and external API integrations.")
#         subtitle.setStyleSheet("color: #64748B; font-size: 13px;")
#         main_layout.addWidget(title)
#         main_layout.addWidget(subtitle)

#         sql_group = QGroupBox("🗄️ SQL Server Database")
#         sql_layout = QFormLayout(sql_group)
#         sql_layout.setSpacing(15)
#         sql_layout.setContentsMargins(20, 25, 20, 20)

#         self.mode_combo = QComboBox()
#         self.mode_combo.addItems(["Windows Authentication", "SQL Server Authentication"])
#         self.mode_combo.setCurrentText("Windows Authentication" if self.auth_mode == "windows" else "SQL Server Authentication")
#         self.mode_combo.currentTextChanged.connect(self._toggle_auth_fields)

#         self.server_input = QLineEdit(self.server)
#         self.db_input = QLineEdit(self.database)
#         self.user_input = QLineEdit(self.username)
#         self.pass_input = QLineEdit(self.password)
#         self.pass_input.setEchoMode(QLineEdit.Password)

#         sql_layout.addRow("Auth Mode:", self.mode_combo)
#         sql_layout.addRow("Server Name:", self.server_input)
#         sql_layout.addRow("Database Name:", self.db_input)
#         sql_layout.addRow("Username:", self.user_input)
#         sql_layout.addRow("Password:", self.pass_input)
#         main_layout.addWidget(sql_group)

#         api_group = QGroupBox("🌐 API Integrations")
#         api_layout = QFormLayout(api_group)
#         api_layout.setSpacing(15)
#         api_layout.setContentsMargins(20, 25, 20, 20)
#         self.api_url_input = QLineEdit(self.api_url)
#         self.api_token_input = QLineEdit(self.api_token)
#         self.api_key_input = QLineEdit(self.api_key)
#         self.api_secret_input = QLineEdit(self.api_secret)
#         self.api_secret_input.setEchoMode(QLineEdit.Password)
#         api_layout.addRow("Base URL:", self.api_url_input)
#         api_layout.addRow("Access Token:", self.api_token_input)
#         api_layout.addRow("API Key:", self.api_key_input)
#         api_layout.addRow("API Secret:", self.api_secret_input)
#         main_layout.addWidget(api_group)

#         btn_layout = QHBoxLayout()
#         test_sql_btn = QPushButton("🔍 Test SQL Connection")
#         test_sql_btn.setObjectName("TestButton")
#         test_sql_btn.clicked.connect(self._test_sql_connection)
#         test_api_btn = QPushButton("🔍 Test API")
#         test_api_btn.setObjectName("TestButton")
#         test_api_btn.clicked.connect(self._test_api)
#         save_btn = QPushButton("Save Configuration")
#         save_btn.setObjectName("PrimaryButton")
#         save_btn.clicked.connect(self._save_and_close)
#         cancel_btn = QPushButton("Cancel")
#         cancel_btn.clicked.connect(self.reject)

#         btn_layout.addWidget(test_sql_btn)
#         btn_layout.addWidget(test_api_btn)
#         btn_layout.addStretch()
#         btn_layout.addWidget(cancel_btn)
#         btn_layout.addWidget(save_btn)
#         main_layout.addLayout(btn_layout)
#         self._toggle_auth_fields()

#     def _toggle_auth_fields(self):
#         is_sql = self.mode_combo.currentText() == "SQL Server Authentication"
#         self.user_input.setEnabled(is_sql)
#         self.pass_input.setEnabled(is_sql)
#         if not is_sql:
#             self.user_input.clear()
#             self.pass_input.clear()

#     def _get_connection_string(self, include_db=True):
#         driver = "ODBC Driver 17 for SQL Server"
#         server = self.server_input.text().strip() or "."
#         db = self.db_input.text().strip() or "POS_DB"
#         base = f"DRIVER={{{driver}}};SERVER={server};"
#         if include_db:
#             base += f"DATABASE={db};"
        
#         if self.mode_combo.currentText() == "Windows Authentication":
#             return f"{base}Trusted_Connection=yes;TrustServerCertificate=yes;"
#         else:
#             uid = self.user_input.text().strip()
#             pwd = self.pass_input.text().strip()
#             return f"{base}UID={uid};PWD={pwd};TrustServerCertificate=yes;"

#     def _test_sql_connection(self):
#         try:
#             conn_str = self._get_connection_string(include_db=False)
#             conn = pyodbc.connect(conn_str, timeout=5)
#             conn.close()
#             QMessageBox.information(self, "Success", "✅ Server connection successful!")
#         except Exception as e:
#             QMessageBox.critical(self, "Connection Failed", f"❌ Failed:\n{str(e)}")

#     def _test_api(self):
#         QMessageBox.information(self, "API Test", "✅ API URL saved.")

#     def _save_and_close(self):
#         data = {
#             "auth_mode": "windows" if self.mode_combo.currentText() == "Windows Authentication" else "sql",
#             "server": self.server_input.text().strip() or ".",
#             "database": self.db_input.text().strip() or "POS_DB",
#             "username": self.user_input.text().strip(),
#             "password": self.pass_input.text().strip(),
#             "api_url": self.api_url_input.text().strip(),
#             "api_token": self.api_token_input.text().strip(),
#             "api_key": self.api_key_input.text().strip(),
#             "api_secret": self.api_secret_input.text().strip()
#         }
#         self.settings_file.write_text(json.dumps(data, indent=4), encoding="utf-8")
#         self._run_migration_script()
#         self.accept()

#     def _get_embedded_sql_script(self):
#         """Return embedded SQL script for table creation"""
#         return """
# -- 1. ORGANIZATIONAL STRUCTURE
# IF OBJECT_ID('dbo.companies', 'U') IS NULL
# BEGIN
#     CREATE TABLE dbo.companies(
#         id INT IDENTITY(1,1) PRIMARY KEY,
#         name NVARCHAR(120) NOT NULL UNIQUE,
#         abbreviation NVARCHAR(40) NOT NULL,
#         default_currency NVARCHAR(10) NOT NULL DEFAULT 'USD',
#         country NVARCHAR(80) NOT NULL
#     );
# END

# IF OBJECT_ID('dbo.company_defaults', 'U') IS NULL
# BEGIN
#     CREATE TABLE dbo.company_defaults(
#         [id] [int] IDENTITY(1,1) NOT NULL PRIMARY KEY,
#         [company_name] [nvarchar](200) NOT NULL DEFAULT '',
#         [address_1] [nvarchar](200) NOT NULL DEFAULT '',
#         [address_2] [nvarchar](200) NOT NULL DEFAULT '',
#         [email] [nvarchar](200) NOT NULL DEFAULT '',
#         [phone] [nvarchar](100) NOT NULL DEFAULT '',
#         [vat_number] [nvarchar](100) NOT NULL DEFAULT '',
#         [tin_number] [nvarchar](100) NOT NULL DEFAULT '',
#         [footer_text] [nvarchar](500) NOT NULL DEFAULT '',
#         [zimra_serial_no] [nvarchar](100) NOT NULL DEFAULT '',
#         [zimra_device_id] [nvarchar](100) NOT NULL DEFAULT '',
#         [zimra_api_key] [nvarchar](500) NOT NULL DEFAULT '',
#         [zimra_api_url] [nvarchar](300) NOT NULL DEFAULT '',
#         [server_company] [nvarchar](200) NOT NULL DEFAULT '',
#         [server_warehouse] [nvarchar](200) NOT NULL DEFAULT '',
#         [server_cost_center] [nvarchar](200) NOT NULL DEFAULT '',
#         [server_username] [nvarchar](200) NOT NULL DEFAULT '',
#         [server_email] [nvarchar](200) NOT NULL DEFAULT '',
#         [server_role] [nvarchar](100) NOT NULL DEFAULT '',
#         [server_full_name] [nvarchar](200) NOT NULL DEFAULT '',
#         [updated_at] [datetime] NOT NULL DEFAULT GETDATE(),
#         [server_first_name] [nvarchar](100) NOT NULL DEFAULT '',
#         [server_last_name] [nvarchar](100) NOT NULL DEFAULT '',
#         [server_mobile] [nvarchar](100) NOT NULL DEFAULT '',
#         [server_profile] [nvarchar](100) NOT NULL DEFAULT '',
#         [server_vat_enabled] [nvarchar](10) NOT NULL DEFAULT '',
#         [api_key] [nvarchar](200) NOT NULL DEFAULT '',
#         [api_secret] [nvarchar](200) NOT NULL DEFAULT '',
#         [invoice_prefix] [nvarchar](6) NOT NULL DEFAULT '',
#         [invoice_start_number] [int] NOT NULL DEFAULT 0
#     );
# END

# IF OBJECT_ID('dbo.cost_centers', 'U') IS NULL
# BEGIN
#     CREATE TABLE dbo.cost_centers(
#         id INT IDENTITY(1,1) PRIMARY KEY,
#         name NVARCHAR(120) NOT NULL,
#         company_id INT NOT NULL
#     );
# END

# IF OBJECT_ID('dbo.warehouses', 'U') IS NULL
# BEGIN
#     CREATE TABLE dbo.warehouses(
#         id INT IDENTITY(1,1) PRIMARY KEY,
#         name NVARCHAR(120) NOT NULL,
#         company_id INT NOT NULL
#     );
# END

# -- 2. MASTER DATA
# IF OBJECT_ID('dbo.customer_groups', 'U') IS NULL
# BEGIN
#     CREATE TABLE dbo.customer_groups(
#         id INT IDENTITY(1,1) PRIMARY KEY,
#         name NVARCHAR(120) NOT NULL UNIQUE,
#         parent_group_id INT NULL
#     );
# END

# IF OBJECT_ID('dbo.price_lists', 'U') IS NULL
# BEGIN
#     CREATE TABLE dbo.price_lists(
#         id INT IDENTITY(1,1) PRIMARY KEY,
#         name NVARCHAR(120) NOT NULL UNIQUE,
#         selling BIT DEFAULT 1
#     );
# END

# IF OBJECT_ID('dbo.customers', 'U') IS NULL
# BEGIN
#     CREATE TABLE dbo.customers(
#         [id] [int] IDENTITY(1,1) NOT NULL PRIMARY KEY,
#         [customer_name] [nvarchar](120) NOT NULL,
#         [customer_group_id] [int] NULL,
#         [customer_type] [nvarchar](20) NULL,
#         [custom_trade_name] [nvarchar](120) NOT NULL,
#         [custom_telephone_number] [nvarchar](40) NOT NULL,
#         [custom_email_address] [nvarchar](120) NOT NULL,
#         [custom_city] [nvarchar](80) NOT NULL,
#         [custom_house_no] [nvarchar](40) NOT NULL,
#         [custom_warehouse_id] [int] NULL,
#         [custom_cost_center_id] [int] NULL,
#         [default_price_list_id] [int] NULL,
#         [balance] [decimal](18, 2) DEFAULT 0,
#         [outstanding_amount] [decimal](18, 2) DEFAULT 0,
#         [loyalty_points] [int] DEFAULT 0
#     );
# END

# IF OBJECT_ID('dbo.products', 'U') IS NULL
# BEGIN
#     CREATE TABLE dbo.products(
#         [id] [int] IDENTITY(1,1) NOT NULL PRIMARY KEY,
#         [part_no] [nvarchar](50) NOT NULL,
#         [name] [nvarchar](120) NOT NULL,
#         [price] [decimal](12, 2) NOT NULL,
#         [stock] [int] NOT NULL,
#         [category] [nvarchar](80) NOT NULL,
#         [active] [bit] NOT NULL,
#         [image_path] [nvarchar](500) NULL,
#         [order_1] [bit] NOT NULL DEFAULT 0,
#         [order_2] [bit] NOT NULL DEFAULT 0,
#         [order_3] [bit] NOT NULL DEFAULT 0,
#         [order_4] [bit] NOT NULL DEFAULT 0,
#         [order_5] [bit] NOT NULL DEFAULT 0,
#         [order_6] [bit] NOT NULL DEFAULT 0,
#         [uom] [nvarchar](20) NULL,
#         [conversion_factor] [decimal](12, 4) NULL 
#     );
# END

# IF OBJECT_ID('dbo.users', 'U') IS NULL
# BEGIN
#     CREATE TABLE dbo.users(
#         [id] [int] IDENTITY(1,1) NOT NULL PRIMARY KEY,
#         [username] [nvarchar](80) NOT NULL UNIQUE,
#         [password] [nvarchar](255) NOT NULL,
#         [display_name] [nvarchar](120) NULL,
#         [active] [bit] NOT NULL DEFAULT 1,
#         role NVARCHAR(20) DEFAULT 'cashier'
#     );
# END

# -- 3. TRANSACTIONS
# IF OBJECT_ID('dbo.sales', 'U') IS NULL
# BEGIN
#     CREATE TABLE dbo.sales(
#         [id] [int] IDENTITY(1,1) NOT NULL PRIMARY KEY,
#         [invoice_number] [int] NOT NULL,
#         [invoice_no] [nvarchar](40) NOT NULL,
#         [invoice_date] DATETIME2 NOT NULL,
#         [total] [decimal](12, 2) NOT NULL,
#         [tendered] [decimal](12, 2) NOT NULL,
#         [method] [nvarchar](30) NOT NULL,
#         [cashier_id] [int] NULL,
#         [cashier_name] [nvarchar](120) NOT NULL,
#         [customer_name] [nvarchar](120) NOT NULL,
#         [customer_contact] [nvarchar](80) NOT NULL,
#         [kot] [nvarchar](40) NOT NULL,
#         [currency] [nvarchar](10) NOT NULL,
#         [subtotal] [decimal](12, 2) NOT NULL,
#         [total_vat] [decimal](12, 2) NOT NULL,
#         [discount_amount] [decimal](12, 2) NOT NULL,
#         [receipt_type] [nvarchar](30) NOT NULL,
#         [footer] [nvarchar](max) NOT NULL,
#         [synced] [bit] NOT NULL DEFAULT 0,
#         [total_items] [decimal](12, 4) NOT NULL,
#         [change_amount] [decimal](12, 2) NOT NULL,
#         [company_name] [nvarchar](120) NOT NULL,
#         [frappe_ref] [nvarchar](80) NULL,
#         created_at DATETIME2 DEFAULT SYSDATETIME()
#     );
# END

# IF OBJECT_ID('dbo.sale_items', 'U') IS NULL
# BEGIN
#     CREATE TABLE dbo.sale_items(
#         [id] [int] IDENTITY(1,1) NOT NULL PRIMARY KEY,
#         [sale_id] [int] NOT NULL,
#         [part_no] [nvarchar](50) NOT NULL,
#         [product_name] [nvarchar](120) NOT NULL,
#         [qty] [decimal](12, 4) NOT NULL,
#         [price] [decimal](12, 2) NOT NULL,
#         [discount] [decimal](12, 2) NOT NULL,
#         [tax] [nvarchar](20) NOT NULL,
#         [total] [decimal](12, 2) NOT NULL,
#         [tax_type] [nvarchar](20) NOT NULL,
#         [tax_rate] [decimal](8, 4) NOT NULL,
#         [tax_amount] [decimal](12, 2) NOT NULL
#     );
# END

# -- 4. SHIFT MANAGEMENT & REPORTING
# IF OBJECT_ID('dbo.shifts', 'U') IS NULL
# BEGIN
#     CREATE TABLE dbo.shifts(
#        [id] [int] IDENTITY(1,1) NOT NULL PRIMARY KEY,
#         [shift_number] [int] NOT NULL,
#         [station] [int] NOT NULL,
#         [cashier_id] [int] NULL,
#         [date] DATE NOT NULL,
#         [start_time] DATETIME2 NOT NULL,
#         [end_time] DATETIME2 NULL,
#         [door_counter] [int] NOT NULL DEFAULT 0,
#         [customers] [int] NOT NULL DEFAULT 0,
#         [notes] [nvarchar](max) NULL,
#         created_at DATETIME2 DEFAULT SYSDATETIME()
#     );
# END

# IF OBJECT_ID('dbo.shift_rows', 'U') IS NULL
# BEGIN
#     CREATE TABLE dbo.shift_rows(
#         [id] [int] IDENTITY(1,1) NOT NULL PRIMARY KEY,
#         [shift_id] [int] NOT NULL,
#         [method] [nvarchar](50) NOT NULL,
#         [start_float] [decimal](12, 2) NOT NULL,
#         [income] [decimal](12, 2) NOT NULL,
#         [counted] [decimal](12, 2) NOT NULL
#     );
# END

# IF OBJECT_ID('dbo.shift_reports', 'U') IS NULL
# BEGIN
#     CREATE TABLE [dbo].[shift_reports](
#         [id] [int] IDENTITY(1,1) NOT NULL PRIMARY KEY,
#         [cashier_id] [int] NULL,
#         [cashier_name] [nvarchar](100) NULL,
#         [shift_number] [int] NULL,
#         [total_expected] [decimal](18, 2) NULL,
#         [total_actual] [decimal](18, 2) NULL,
#         [total_variance] [decimal](18, 2) NULL,
#         [report_date] [date] NULL,
#         [created_at] [datetime2](7) DEFAULT SYSDATETIME()
#     );
# END

# IF OBJECT_ID('dbo.shift_report_details', 'U') IS NULL
# BEGIN
#     CREATE TABLE [dbo].[shift_report_details](
#         [id] [int] IDENTITY(1,1) NOT NULL PRIMARY KEY,
#         [report_id] [int] NULL,
#         [payment_method] [nvarchar](50) NULL,
#         [amount_expected] [decimal](18, 2) NULL,
#         [amount_available] [decimal](18, 2) NULL,
#         [variance] [decimal](18, 2) NULL,
#         [created_at] [datetime2](7) DEFAULT SYSDATETIME()
#     );
# END

# -- 5. FOREIGN KEYS
# IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE name = 'FK_cost_centers_companies')
#     ALTER TABLE dbo.cost_centers ADD CONSTRAINT FK_cost_centers_companies FOREIGN KEY (company_id) REFERENCES dbo.companies(id);

# IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE name = 'FK_customers_customer_groups')
#     ALTER TABLE dbo.customers ADD CONSTRAINT FK_customers_customer_groups FOREIGN KEY (customer_group_id) REFERENCES dbo.customer_groups(id);

# IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE name = 'FK_customers_warehouses')
#     ALTER TABLE dbo.customers ADD CONSTRAINT FK_customers_warehouses FOREIGN KEY (custom_warehouse_id) REFERENCES dbo.warehouses(id);

# IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE name = 'FK_customers_cost_centers')
#     ALTER TABLE dbo.customers ADD CONSTRAINT FK_customers_cost_centers FOREIGN KEY (custom_cost_center_id) REFERENCES dbo.cost_centers(id);

# IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE name = 'FK_customers_price_lists')
#     ALTER TABLE dbo.customers ADD CONSTRAINT FK_customers_price_lists FOREIGN KEY (default_price_list_id) REFERENCES dbo.price_lists(id);

# IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE name = 'FK_sale_items_sales')
#     ALTER TABLE dbo.sale_items ADD CONSTRAINT FK_sale_items_sales FOREIGN KEY (sale_id) REFERENCES dbo.sales(id) ON DELETE CASCADE;

# IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE name = 'FK_shift_rows_shifts')
#     ALTER TABLE dbo.shift_rows ADD CONSTRAINT FK_shift_rows_shifts FOREIGN KEY (shift_id) REFERENCES dbo.shifts(id) ON DELETE CASCADE;

# IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE name = 'FK_warehouses_companies')
#     ALTER TABLE dbo.warehouses ADD CONSTRAINT FK_warehouses_companies FOREIGN KEY (company_id) REFERENCES dbo.companies(id);

# -- 6. SEED DATA
# IF NOT EXISTS (SELECT 1 FROM dbo.companies WHERE name = 'Confidence Pro')
# BEGIN
#     INSERT INTO dbo.companies (name, abbreviation, default_currency, country)
#     VALUES ('Confidence Pro', 'CP', 'NGN', 'Nigeria');
# END

# IF NOT EXISTS (SELECT 1 FROM dbo.users WHERE username = 'admin')
# BEGIN
#     INSERT INTO dbo.users (username, password, role)
#     VALUES ('admin', 'admin123', 'admin');
# END
# IF NOT EXISTS (SELECT 1 FROM dbo.company_defaults)
# BEGIN
#     INSERT INTO dbo.company_defaults (
#         company_name,
#         address_1,
#         address_2,
#         email,
#         phone,
#         vat_number,
#         tin_number,
#         footer_text
#     )
#     VALUES (
#         'Confidence Pro',
#         'Lagos Office',
#         '',
#         'info@confidencepro.com',
#         '+2340000000000',
#         '',
#         '',
#         'Thank you for your business!'
#     );
# END
#         """

#     def _run_migration_script(self):
#         try:
#             db_name = self.db_input.text().strip() or "POS_DB"
            
#             # STEP 1: Connect to master and create database
#             conn_master = pyodbc.connect(
#                 self._get_connection_string(include_db=False),
#                 autocommit=True
#             )
#             cursor_master = conn_master.cursor()
            
#             # Drop existing database if it exists
#             try:
#                 cursor_master.execute(f"""
#                     IF EXISTS (SELECT name FROM sys.databases WHERE name = '{db_name}')
#                     BEGIN
#                         ALTER DATABASE [{db_name}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE
#                         DROP DATABASE [{db_name}]
#                     END
#                 """)
#                 print(f"✅ Dropped existing database '{db_name}'")
#             except Exception as e:
#                 print(f"⚠️ Warning dropping database: {str(e)}")
            
#             # Create new database
#             try:
#                 cursor_master.execute(f"CREATE DATABASE [{db_name}]")
#                 print(f"✅ Created database '{db_name}'")
#             except Exception as e:
#                 if "already exists" not in str(e):
#                     raise
            
#             cursor_master.close()
#             conn_master.close()

#             # STEP 2: Connect to the new database and execute table creation scripts
#             conn_target = pyodbc.connect(
#                 self._get_connection_string(include_db=True),
#                 autocommit=True
#             )
#             cursor_target = conn_target.cursor()
            
#             # Get embedded SQL script
#             script_text = self._get_embedded_sql_script()
            
#             # Split script by GO (case insensitive)
#             batches = re.split(r'\bGO\b', script_text, flags=re.IGNORECASE)
            
#             table_count = 0
#             for batch in batches:
#                 batch = batch.strip()
#                 if batch:
#                     try:
#                         cursor_target.execute(batch)
#                         if "CREATE TABLE" in batch.upper():
#                             table_count += 1
#                         print(f"✅ Executed: {batch[:60]}...")
#                     except Exception as e:
#                         print(f"⚠️ Batch error (continuing): {str(e)}")
            
#             cursor_target.close()
#             conn_target.close()
            
#             QMessageBox.information(
#                 self, 
#                 "Success", 
#                 f"✅ Database '{db_name}' created successfully!\n\n"
#                 f"✨ Tables created: {table_count}\n"
#                 f"🔗 Foreign keys configured"
#             )
#             sys.exit(1)
#         except Exception as e:
#             QMessageBox.critical(
#                 self, 
#                 "Migration Failed", 
#                 f"❌ Error:\n{str(e)}"
#             )
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
<<<<<<< HEAD
                "auth_mode": "windows", "server": ".", "database": "pos_db",
                "username": "", "password": "", "api_url": "", "api_token": "",
                "api_key": "", "api_secret": ""
=======
                "auth_mode": "windows", 
                "server": ".", 
                "database": "POS_DB",
                "username": "", 
                "password": "", 
                "api_url": "", 
                "api_username": "", 
                "api_password": ""
>>>>>>> 0e8d1deb42ba6831c3c6714405de42a075fc17fd
            }
            self.settings_file.write_text(json.dumps(default, indent=4), encoding="utf-8")

        data = json.loads(self.settings_file.read_text(encoding="utf-8"))
        
        # SQL settings
        self.auth_mode = data.get("auth_mode", "windows")
<<<<<<< HEAD
        self.server    = data.get("server",   ".")
        self.database  = data.get("database", "pos_db")
        self.username  = data.get("username", "")
        self.password  = data.get("password", "")
        self.api_url   = data.get("api_url",   "")
        self.api_token = data.get("api_token", "")
        self.api_key   = data.get("api_key",   "")
        self.api_secret = data.get("api_secret", "")
=======
        self.server = data.get("server", ".")
        self.database = data.get("database", "POS_DB")
        self.username = data.get("username", "")
        self.password = data.get("password", "")
        
        # API settings (only url, username, password)
        self.api_url = data.get("api_url", "")
        self.api_username = data.get("api_username", "")
        self.api_password = data.get("api_password", "")
>>>>>>> 0e8d1deb42ba6831c3c6714405de42a075fc17fd

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

        # ==================== SQL SERVER SECTION ====================
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
        main_layout.addWidget(sql_group)

        # ==================== API SECTION (ONLY URL + USERNAME + PASSWORD) ====================
        api_group = QGroupBox("🌐 API Integration")
        api_layout = QFormLayout(api_group)
        api_layout.setSpacing(15)
        api_layout.setContentsMargins(20, 25, 20, 20)
<<<<<<< HEAD
        self.api_url_input    = QLineEdit(self.api_url)
        self.api_token_input  = QLineEdit(self.api_token)
        self.api_key_input    = QLineEdit(self.api_key)
        self.api_secret_input = QLineEdit(self.api_secret)
        self.api_secret_input.setEchoMode(QLineEdit.Password)
        api_layout.addRow("Base URL:",     self.api_url_input)
        api_layout.addRow("Access Token:", self.api_token_input)
        api_layout.addRow("API Key:",      self.api_key_input)
        api_layout.addRow("API Secret:",   self.api_secret_input)
=======
        
        self.api_url_input = QLineEdit(self.api_url)
        self.api_username_input = QLineEdit(self.api_username)
        self.api_password_input = QLineEdit(self.api_password)
        self.api_password_input.setEchoMode(QLineEdit.Password)
        
        api_layout.addRow("API URL:", self.api_url_input)
        api_layout.addRow("API Username:", self.api_username_input)
        api_layout.addRow("API Password:", self.api_password_input)
        
>>>>>>> 0e8d1deb42ba6831c3c6714405de42a075fc17fd
        main_layout.addWidget(api_group)

        # ==================== BUTTONS ====================
        btn_layout = QHBoxLayout()
        test_sql_btn = QPushButton("🔍 Test SQL Connection")
        test_sql_btn.setObjectName("TestButton")
        test_sql_btn.clicked.connect(self._test_sql_connection)
        
        save_btn = QPushButton("Save Configuration")
        save_btn.setObjectName("PrimaryButton")
        save_btn.clicked.connect(self._save_and_close)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(test_sql_btn)
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

    def _save_and_close(self):
        data = {
            "auth_mode": "windows" if self.mode_combo.currentText() == "Windows Authentication" else "sql",
<<<<<<< HEAD
            "server":    self.server_input.text().strip()    or ".",
            "database":  self.db_input.text().strip()        or "pos_db",
            "username":  self.user_input.text().strip(),
            "password":  self.pass_input.text().strip(),
            "api_url":   self.api_url_input.text().strip(),
            "api_token": self.api_token_input.text().strip(),
            "api_key":   self.api_key_input.text().strip(),
            "api_secret":self.api_secret_input.text().strip(),
=======
            "server": self.server_input.text().strip() or ".",
            "database": self.db_input.text().strip() or "POS_DB",
            "username": self.user_input.text().strip(),
            "password": self.pass_input.text().strip(),
            # API section now contains ONLY url, username, and password
            "api_url": self.api_url_input.text().strip(),
            "api_username": self.api_username_input.text().strip(),
            "api_password": self.api_password_input.text().strip()
>>>>>>> 0e8d1deb42ba6831c3c6714405de42a075fc17fd
        }
        self.settings_file.write_text(json.dumps(data, indent=4), encoding="utf-8")
        self._run_migration_script()
        self.accept()

<<<<<<< HEAD
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
=======
    def _get_embedded_sql_script(self):
        """Return embedded SQL script for table creation"""
        return """
-- 1. ORGANIZATIONAL STRUCTURE
IF OBJECT_ID('dbo.companies', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.companies(
        id INT IDENTITY(1,1) PRIMARY KEY,
        name NVARCHAR(120) NOT NULL UNIQUE,
        abbreviation NVARCHAR(40) NOT NULL,
        default_currency NVARCHAR(10) NOT NULL DEFAULT 'USD',
        country NVARCHAR(80) NOT NULL
    );
END

IF OBJECT_ID('dbo.company_defaults', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.company_defaults(
        [id] [int] IDENTITY(1,1) NOT NULL PRIMARY KEY,
        [company_name] [nvarchar](200) NOT NULL DEFAULT '',
        [address_1] [nvarchar](200) NOT NULL DEFAULT '',
        [address_2] [nvarchar](200) NOT NULL DEFAULT '',
        [email] [nvarchar](200) NOT NULL DEFAULT '',
        [phone] [nvarchar](100) NOT NULL DEFAULT '',
        [vat_number] [nvarchar](100) NOT NULL DEFAULT '',
        [tin_number] [nvarchar](100) NOT NULL DEFAULT '',
        [footer_text] [nvarchar](500) NOT NULL DEFAULT '',
        [zimra_serial_no] [nvarchar](100) NOT NULL DEFAULT '',
        [zimra_device_id] [nvarchar](100) NOT NULL DEFAULT '',
        [zimra_api_key] [nvarchar](500) NOT NULL DEFAULT '',
        [zimra_api_url] [nvarchar](300) NOT NULL DEFAULT '',
        [server_company] [nvarchar](200) NOT NULL DEFAULT '',
        [server_warehouse] [nvarchar](200) NOT NULL DEFAULT '',
        [server_cost_center] [nvarchar](200) NOT NULL DEFAULT '',
        [server_username] [nvarchar](200) NOT NULL DEFAULT '',
        [server_email] [nvarchar](200) NOT NULL DEFAULT '',
        [server_role] [nvarchar](100) NOT NULL DEFAULT '',
        [server_full_name] [nvarchar](200) NOT NULL DEFAULT '',
        [updated_at] [datetime] NOT NULL DEFAULT GETDATE(),
        [server_first_name] [nvarchar](100) NOT NULL DEFAULT '',
        [server_last_name] [nvarchar](100) NOT NULL DEFAULT '',
        [server_mobile] [nvarchar](100) NOT NULL DEFAULT '',
        [server_profile] [nvarchar](100) NOT NULL DEFAULT '',
        [server_vat_enabled] [nvarchar](10) NOT NULL DEFAULT '',
        [api_username] [nvarchar](200) NOT NULL DEFAULT '',
        [api_key] [nvarchar](200) NOT NULL DEFAULT '',
        [api_secret] [nvarchar](200) NOT NULL DEFAULT '',
        [invoice_prefix] [nvarchar](6) NOT NULL DEFAULT '',
        [invoice_start_number] [int] NOT NULL DEFAULT 0
    );
END

IF OBJECT_ID('dbo.cost_centers', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.cost_centers(
        id INT IDENTITY(1,1) PRIMARY KEY,
        name NVARCHAR(120) NOT NULL,
        company_id INT NOT NULL
    );
END

IF OBJECT_ID('dbo.warehouses', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.warehouses(
        id INT IDENTITY(1,1) PRIMARY KEY,
        name NVARCHAR(120) NOT NULL,
        company_id INT NOT NULL
    );
END

-- 2. MASTER DATA
IF OBJECT_ID('dbo.customer_groups', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.customer_groups(
        id INT IDENTITY(1,1) PRIMARY KEY,
        name NVARCHAR(120) NOT NULL UNIQUE,
        parent_group_id INT NULL
    );
END

IF OBJECT_ID('dbo.price_lists', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.price_lists(
        id INT IDENTITY(1,1) PRIMARY KEY,
        name NVARCHAR(120) NOT NULL UNIQUE,
        selling BIT DEFAULT 1
    );
END

IF OBJECT_ID('dbo.customers', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.customers(
        [id] [int] IDENTITY(1,1) NOT NULL PRIMARY KEY,
        [customer_name] [nvarchar](120) NOT NULL,
        [customer_group_id] [int] NULL,
        [customer_type] [nvarchar](20) NULL,
        [custom_trade_name] [nvarchar](120) NOT NULL,
        [custom_telephone_number] [nvarchar](40) NOT NULL,
        [custom_email_address] [nvarchar](120) NOT NULL,
        [custom_city] [nvarchar](80) NOT NULL,
        [custom_house_no] [nvarchar](40) NOT NULL,
        [custom_warehouse_id] [int] NULL,
        [custom_cost_center_id] [int] NULL,
        [default_price_list_id] [int] NULL,
        [balance] [decimal](18, 2) DEFAULT 0,
        [outstanding_amount] [decimal](18, 2) DEFAULT 0,
        [loyalty_points] [int] DEFAULT 0
    );
END

IF OBJECT_ID('dbo.products', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.products(
        [id] [int] IDENTITY(1,1) NOT NULL PRIMARY KEY,
        [part_no] [nvarchar](50) NOT NULL,
        [name] [nvarchar](120) NOT NULL,
        [price] [decimal](12, 2) NOT NULL,
        [stock] [int] NOT NULL,
        [category] [nvarchar](80) NOT NULL,
        [active] [bit] NOT NULL,
        [image_path] [nvarchar](500) NULL,
        [order_1] [bit] NOT NULL DEFAULT 0,
        [order_2] [bit] NOT NULL DEFAULT 0,
        [order_3] [bit] NOT NULL DEFAULT 0,
        [order_4] [bit] NOT NULL DEFAULT 0,
        [order_5] [bit] NOT NULL DEFAULT 0,
        [order_6] [bit] NOT NULL DEFAULT 0,
        [uom] [nvarchar](20) NULL,
        [conversion_factor] [decimal](12, 4) NULL 
    );
END

IF OBJECT_ID('dbo.users', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.users(
        [id] [int] IDENTITY(1,1) NOT NULL PRIMARY KEY,
        [username] [nvarchar](80) NOT NULL UNIQUE,
        [password] [nvarchar](255) NOT NULL,
        [display_name] [nvarchar](120) NULL,
        [active] [bit] NOT NULL DEFAULT 1,
        role NVARCHAR(20) DEFAULT 'cashier'
    );
END

-- 3. TRANSACTIONS
IF OBJECT_ID('dbo.sales', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.sales(
        [id] [int] IDENTITY(1,1) NOT NULL PRIMARY KEY,
        [invoice_number] [int] NOT NULL,
        [invoice_no] [nvarchar](40) NOT NULL,
        [invoice_date] DATETIME2 NOT NULL,
        [total] [decimal](12, 2) NOT NULL,
        [tendered] [decimal](12, 2) NOT NULL,
        [method] [nvarchar](30) NOT NULL,
        [cashier_id] [int] NULL,
        [cashier_name] [nvarchar](120) NOT NULL,
        [customer_name] [nvarchar](120) NOT NULL,
        [customer_contact] [nvarchar](80) NOT NULL,
        [kot] [nvarchar](40) NOT NULL,
        [currency] [nvarchar](10) NOT NULL,
        [subtotal] [decimal](12, 2) NOT NULL,
        [total_vat] [decimal](12, 2) NOT NULL,
        [discount_amount] [decimal](12, 2) NOT NULL,
        [receipt_type] [nvarchar](30) NOT NULL,
        [footer] [nvarchar](max) NOT NULL,
        [synced] [bit] NOT NULL DEFAULT 0,
        [total_items] [decimal](12, 4) NOT NULL,
        [change_amount] [decimal](12, 2) NOT NULL,
        [company_name] [nvarchar](120) NOT NULL,
        [frappe_ref] [nvarchar](80) NULL,
        created_at DATETIME2 DEFAULT SYSDATETIME()
    );
END

IF OBJECT_ID('dbo.sale_items', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.sale_items(
        [id] [int] IDENTITY(1,1) NOT NULL PRIMARY KEY,
        [sale_id] [int] NOT NULL,
        [part_no] [nvarchar](50) NOT NULL,
        [product_name] [nvarchar](120) NOT NULL,
        [qty] [decimal](12, 4) NOT NULL,
        [price] [decimal](12, 2) NOT NULL,
        [discount] [decimal](12, 2) NOT NULL,
        [tax] [nvarchar](20) NOT NULL,
        [total] [decimal](12, 2) NOT NULL,
        [tax_type] [nvarchar](20) NOT NULL,
        [tax_rate] [decimal](8, 4) NOT NULL,
        [tax_amount] [decimal](12, 2) NOT NULL
    );
END

-- 4. SHIFT MANAGEMENT & REPORTING
IF OBJECT_ID('dbo.shifts', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.shifts(
       [id] [int] IDENTITY(1,1) NOT NULL PRIMARY KEY,
        [shift_number] [int] NOT NULL,
        [station] [int] NOT NULL,
        [cashier_id] [int] NULL,
        [date] DATE NOT NULL,
        [start_time] DATETIME2 NOT NULL,
        [end_time] DATETIME2 NULL,
        [door_counter] [int] NOT NULL DEFAULT 0,
        [customers] [int] NOT NULL DEFAULT 0,
        [notes] [nvarchar](max) NULL,
        created_at DATETIME2 DEFAULT SYSDATETIME()
    );
END

IF OBJECT_ID('dbo.shift_rows', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.shift_rows(
        [id] [int] IDENTITY(1,1) NOT NULL PRIMARY KEY,
        [shift_id] [int] NOT NULL,
        [method] [nvarchar](50) NOT NULL,
        [start_float] [decimal](12, 2) NOT NULL,
        [income] [decimal](12, 2) NOT NULL,
        [counted] [decimal](12, 2) NOT NULL
    );
END

IF OBJECT_ID('dbo.shift_reports', 'U') IS NULL
BEGIN
    CREATE TABLE [dbo].[shift_reports](
        [id] [int] IDENTITY(1,1) NOT NULL PRIMARY KEY,
        [cashier_id] [int] NULL,
        [cashier_name] [nvarchar](100) NULL,
        [shift_number] [int] NULL,
        [total_expected] [decimal](18, 2) NULL,
        [total_actual] [decimal](18, 2) NULL,
        [total_variance] [decimal](18, 2) NULL,
        [report_date] [date] NULL,
        [created_at] [datetime2](7) DEFAULT SYSDATETIME()
    );
END

IF OBJECT_ID('dbo.shift_report_details', 'U') IS NULL
BEGIN
    CREATE TABLE [dbo].[shift_report_details](
        [id] [int] IDENTITY(1,1) NOT NULL PRIMARY KEY,
        [report_id] [int] NULL,
        [payment_method] [nvarchar](50) NULL,
        [amount_expected] [decimal](18, 2) NULL,
        [amount_available] [decimal](18, 2) NULL,
        [variance] [decimal](18, 2) NULL,
        [created_at] [datetime2](7) DEFAULT SYSDATETIME()
    );
END

-- 5. FOREIGN KEYS
IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE name = 'FK_cost_centers_companies')
    ALTER TABLE dbo.cost_centers ADD CONSTRAINT FK_cost_centers_companies FOREIGN KEY (company_id) REFERENCES dbo.companies(id);

IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE name = 'FK_customers_customer_groups')
    ALTER TABLE dbo.customers ADD CONSTRAINT FK_customers_customer_groups FOREIGN KEY (customer_group_id) REFERENCES dbo.customer_groups(id);

IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE name = 'FK_customers_warehouses')
    ALTER TABLE dbo.customers ADD CONSTRAINT FK_customers_warehouses FOREIGN KEY (custom_warehouse_id) REFERENCES dbo.warehouses(id);

IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE name = 'FK_customers_cost_centers')
    ALTER TABLE dbo.customers ADD CONSTRAINT FK_customers_cost_centers FOREIGN KEY (custom_cost_center_id) REFERENCES dbo.cost_centers(id);

IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE name = 'FK_customers_price_lists')
    ALTER TABLE dbo.customers ADD CONSTRAINT FK_customers_price_lists FOREIGN KEY (default_price_list_id) REFERENCES dbo.price_lists(id);

IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE name = 'FK_sale_items_sales')
    ALTER TABLE dbo.sale_items ADD CONSTRAINT FK_sale_items_sales FOREIGN KEY (sale_id) REFERENCES dbo.sales(id) ON DELETE CASCADE;

IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE name = 'FK_shift_rows_shifts')
    ALTER TABLE dbo.shift_rows ADD CONSTRAINT FK_shift_rows_shifts FOREIGN KEY (shift_id) REFERENCES dbo.shifts(id) ON DELETE CASCADE;

IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE name = 'FK_warehouses_companies')
    ALTER TABLE dbo.warehouses ADD CONSTRAINT FK_warehouses_companies FOREIGN KEY (company_id) REFERENCES dbo.companies(id);

-- 6. SEED DATA
IF NOT EXISTS (SELECT 1 FROM dbo.companies WHERE name = 'Confidence Pro')
BEGIN
    INSERT INTO dbo.companies (name, abbreviation, default_currency, country)
    VALUES ('Confidence Pro', 'CP', 'NGN', 'Nigeria');
END

IF NOT EXISTS (SELECT 1 FROM dbo.users WHERE username = 'admin')
BEGIN
    INSERT INTO dbo.users (username, password, role)
    VALUES ('admin', 'admin123', 'admin');
END
IF NOT EXISTS (SELECT 1 FROM dbo.company_defaults)
BEGIN
    INSERT INTO dbo.company_defaults (
        company_name,
        address_1,
        address_2,
        email,
        phone,
        vat_number,
        tin_number,
        footer_text
    )
    VALUES (
        'Confidence Pro',
        'Lagos Office',
        '',
        'info@confidencepro.com',
        '+2340000000000',
        '',
        '',
        'Thank you for your business!'
    );
END
        """

>>>>>>> 0e8d1deb42ba6831c3c6714405de42a075fc17fd
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