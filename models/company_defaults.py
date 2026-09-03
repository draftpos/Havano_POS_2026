# =============================================================================
# models/company_defaults.py
# =============================================================================

from database.db import get_connection, fetchone_dict

_BLANK = {
    # Editable - receipt header
    "company_name": "", "address_1": "", "address_2": "",
    "email": "", "phone": "", "vat_number": "", "tin_number": "",
    # Editable - receipt header (shown bold/centered below the company block
    # on every sales receipt). Falls back to "*** SALES RECEIPT ***" when blank.
    "receipt_header": "",
    # Editable - receipt footer
    "footer_text": "",
    "allow_credit_sales": "0",
    # Editable - terms & conditions (printed on sales orders)
    "terms_and_conditions": "",
    # Editable - banking details (printed on A4 Tax Invoices)
    "banking_details": "",
    # Editable - ZIMRA
    "zimra_serial_no": "", "zimra_device_id": "",
    "zimra_api_key": "", "zimra_api_url": "",
    # Editable - invoice numbering
    "invoice_prefix":       "",   # up to 6 chars e.g. "ABC"
    "invoice_start_number": "0",  # integer as string
    # Readable from logo_config.json (not in company_defaults DB record)
    "logo_path":            "",   # local filename
    # Read-only - from login
    "server_company": "", "server_warehouse": "", "server_cost_center": "",
    "server_username": "", "server_email": "", "server_role": "",
    "server_full_name": "", "server_first_name": "", "server_last_name": "",
    "server_mobile": "", "server_profile": "", "server_vat_enabled": "",
    "server_company_currency": "USD",
    "server_company_currency_symbol": "$",
    "server_api_host": "", "server_pos_account": "", "server_taxes_and_charges": "",
    "server_walk_in_customer": "", "default_price_list_id": "",
    "server_terminal_id": "", "server_shop_id": "", "server_terminal_name": "",
    "api_key": "", "api_secret": "", "odoo_token": "", "system_mode": "frappe",
    "work_offline": "0", "server_database": "",
    "pharmacy_mode": "0", "butchery_mode": "0",
    "allow_cashier_pharmacy_sales": "0",
    "support_number": "0782168407", "agent_number": "Agent", "agent": "",
    "bound_device_id": "",
    "subscription_days_left": "", "subscription_expiry": "",
}


def _ensure_columns(cur):
    try:
        cur.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'company_defaults'
            )
            CREATE TABLE company_defaults (
                id                             INT IDENTITY(1,1) PRIMARY KEY,
                company_name                   NVARCHAR(255) NULL,
                address_1                      NVARCHAR(255) NULL,
                address_2                      NVARCHAR(255) NULL,
                email                          NVARCHAR(255) NULL,
                phone                          NVARCHAR(50) NULL,
                support_number                 NVARCHAR(50) NULL,
                agent_number                   NVARCHAR(50) NULL,
                agent                          NVARCHAR(255) NULL,
                vat_number                     NVARCHAR(50) NULL,
                tin_number                     NVARCHAR(50) NULL,
                footer_text                    NVARCHAR(MAX) NULL,
                receipt_header                 NVARCHAR(255) NULL,
                terms_and_conditions           NVARCHAR(MAX) NULL,
                banking_details                NVARCHAR(MAX) NULL,
                zimra_serial_no                NVARCHAR(100) NULL,
                zimra_device_id                NVARCHAR(100) NULL,
                zimra_api_key                  NVARCHAR(255) NULL,
                zimra_api_url                  NVARCHAR(255) NULL,
                invoice_prefix                 NVARCHAR(50) NULL,
                invoice_start_number           NVARCHAR(50) NULL,
                allow_credit_sales             NVARCHAR(10) NULL,
                server_company                 NVARCHAR(255) NULL,
                server_warehouse               NVARCHAR(255) NULL,
                server_cost_center             NVARCHAR(255) NULL,
                server_username                NVARCHAR(255) NULL,
                server_email                   NVARCHAR(255) NULL,
                server_role                    NVARCHAR(50) NULL,
                server_full_name               NVARCHAR(255) NULL,
                server_first_name              NVARCHAR(255) NULL,
                server_last_name               NVARCHAR(255) NULL,
                server_mobile                  NVARCHAR(50) NULL,
                server_profile                 NVARCHAR(100) NULL,
                server_vat_enabled             NVARCHAR(10) NULL,
                server_company_currency        NVARCHAR(10) NULL,
                server_company_currency_symbol NVARCHAR(10) NULL,
                server_api_host                NVARCHAR(255) NULL,
                server_pos_account             NVARCHAR(255) NULL,
                server_taxes_and_charges       NVARCHAR(255) NULL,
                server_walk_in_customer        NVARCHAR(255) NULL,
                default_price_list_id          INT NULL,
                server_terminal_id             NVARCHAR(50) NULL,
                server_terminal_name           NVARCHAR(255) NULL,
                server_shop_id                 NVARCHAR(50) NULL,
                api_key                        NVARCHAR(255) NULL,
                api_secret                     NVARCHAR(255) NULL,
                odoo_token                     NVARCHAR(255) NULL,
                system_mode                    NVARCHAR(20) NULL,
                work_offline                   NVARCHAR(10) NULL,
                server_database                NVARCHAR(255) NULL,
                pharmacy_mode                  NVARCHAR(10) NULL,
                allow_cashier_pharmacy_sales  NVARCHAR(10) NULL,
                butchery_mode                  NVARCHAR(10) NULL,
                bound_device_id                NVARCHAR(255) NULL,
                subscription_days_left         NVARCHAR(255) NULL,
                subscription_expiry            NVARCHAR(255) NULL,
                sale_id_prefix                 NVARCHAR(50) NULL,
                updated_at                     DATETIME NULL
            )
        """)
        cur.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'company_defaults' AND COLUMN_NAME = 'bound_device_id'")
        if cur.fetchone()[0] == 0:
            cur.execute("ALTER TABLE company_defaults ADD bound_device_id VARCHAR(255) NULL")
        cur.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'company_defaults' AND COLUMN_NAME = 'subscription_days_left'")
        if cur.fetchone()[0] == 0:
            cur.execute("ALTER TABLE company_defaults ADD subscription_days_left VARCHAR(255) NULL")
        cur.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'company_defaults' AND COLUMN_NAME = 'subscription_expiry'")
        if cur.fetchone()[0] == 0:
            cur.execute("ALTER TABLE company_defaults ADD subscription_expiry VARCHAR(255) NULL")
        cur.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'company_defaults' AND COLUMN_NAME = 'banking_details'")
        if cur.fetchone()[0] == 0:
            cur.execute("ALTER TABLE company_defaults ADD banking_details NVARCHAR(MAX) NULL")
    except Exception as e:
        print(f"[CompanyDefaults] _ensure_columns error: {e}")


def get_defaults() -> dict:
    conn = get_connection()
    cur  = conn.cursor()
    try:
        _ensure_columns(cur)
        cur.execute("SELECT TOP 1 * FROM company_defaults ORDER BY id")
        row = fetchone_dict(cur)
    except Exception:
        row = None
    finally:
        conn.close()

    if not row:
        return dict(_BLANK)

    result = dict(_BLANK)
    for key in _BLANK:
        if key != "logo_path":
            val = row.get(key)
            if val is None:
                result[key] = _BLANK[key]
            else:
                result[key] = str(val).strip()
    
    # Decrypt api_secret if encrypted
    if result.get("api_secret"):
        try:
            from utils.crypto import decrypt_secret
            result["api_secret"] = decrypt_secret(result["api_secret"])
        except Exception:
            pass

    # Load logo_path from JSON helper
    try:
        import os, json
        from database.db import get_app_data_dir
        json_path = os.path.join(get_app_data_dir(), "logo_config.json")
        if os.path.exists(json_path):
            with open(json_path, "r") as f:
                cfg = json.load(f)
                result["logo_path"] = cfg.get("logo_path", "")
    except Exception as e:
        print(f"[CompanyDefaults] Error loading logo_path from JSON: {e}")

    return result


def save_defaults(data: dict) -> None:
    conn = get_connection()
    cur  = conn.cursor()
    try:
        _ensure_columns(cur)
        cur.execute("""
            IF NOT EXISTS (SELECT 1 FROM company_defaults)
                INSERT INTO company_defaults DEFAULT VALUES
        """)
        cur.execute("""
            UPDATE company_defaults SET
                company_name          = ?,
                address_1             = ?,
                address_2             = ?,
                email                 = ?,
                phone                 = ?,
                support_number        = ?,
                agent_number          = ?,
                agent                 = ?,
                vat_number            = ?,
                tin_number            = ?,
                footer_text           = ?,
                receipt_header        = ?,
                terms_and_conditions  = ?,
                banking_details       = ?,
                zimra_serial_no       = ?,
                zimra_device_id       = ?,
                zimra_api_key         = ?,
                zimra_api_url         = ?,
                invoice_prefix        = ?,
                invoice_start_number  = ?,
                allow_credit_sales    = ?,
                server_company        = ?,
                server_warehouse      = ?,
                server_cost_center    = ?,
                server_username       = ?,
                server_email          = ?,
                server_role           = ?,
                server_full_name      = ?,
                server_first_name     = ?,
                server_last_name      = ?,
                server_mobile         = ?,
                server_profile        = ?,
                server_vat_enabled    = ?,
                server_company_currency        = ?,
                server_company_currency_symbol = ?,
                server_api_host       = ?,
                server_pos_account    = ?,
                server_taxes_and_charges = ?,
                server_walk_in_customer  = ?,
                default_price_list_id    = ?,
                server_terminal_id    = ?,
                server_terminal_name  = ?,
                server_shop_id        = ?,
                api_key               = ?,
                api_secret            = ?,
                odoo_token            = ?,
                system_mode           = ?,
                work_offline          = ?,
                server_database       = ?,
                pharmacy_mode         = ?,
                allow_cashier_pharmacy_sales = ?,
                butchery_mode         = ?,
                bound_device_id       = ?,
                subscription_days_left= ?,
                subscription_expiry   = ?,
                updated_at            = GETDATE()
            WHERE id = (SELECT MIN(id) FROM company_defaults)
        """, (
            str(data.get("company_name") or ""),
            str(data.get("address_1") or ""),
            str(data.get("address_2") or ""),
            str(data.get("email") or ""),
            str(data.get("phone") or ""),
            str(data.get("support_number") or ""),
            str(data.get("agent_number") or ""),
            str(data.get("agent") or ""),
            str(data.get("vat_number") or ""),
            str(data.get("tin_number") or ""),
            str(data.get("footer_text") or ""),
            str(data.get("receipt_header") or ""),
            str(data.get("terms_and_conditions") or ""),
            str(data.get("banking_details") or ""),
            str(data.get("zimra_serial_no") or ""),
            str(data.get("zimra_device_id") or ""),
            str(data.get("zimra_api_key") or ""),
            str(data.get("zimra_api_url") or ""),
            str(data.get("invoice_prefix") or ""),
            str(data.get("invoice_start_number") or "0"),
            str(data.get("allow_credit_sales") or "0"),
            str(data.get("server_company") or ""),
            str(data.get("server_warehouse") or ""),
            str(data.get("server_cost_center") or ""),
            str(data.get("server_username") or ""),
            str(data.get("server_email") or ""),
            str(data.get("server_role") or ""),
            str(data.get("server_full_name") or ""),
            str(data.get("server_first_name") or ""),
            str(data.get("server_last_name") or ""),
            str(data.get("server_mobile") or ""),
            str(data.get("server_profile") or ""),
            str(data.get("server_vat_enabled") or ""),
            str(data.get("server_company_currency") or ""),
            str(data.get("server_company_currency_symbol") or ""),
            str(data.get("server_api_host") or ""),
            str(data.get("server_pos_account") or ""),
            str(data.get("server_taxes_and_charges") or ""),
            str(data.get("server_walk_in_customer") or ""),
            data.get("default_price_list_id") or None,
            str(data.get("server_terminal_id") or ""),
            str(data.get("server_terminal_name") or ""),
            str(data.get("server_shop_id") or ""),
            str(data.get("api_key") or ""),
            __import__("utils.crypto", fromlist=["encrypt_secret"]).encrypt_secret(str(data.get("api_secret") or "")) if str(data.get("system_mode") or "saas").lower() == "saas" else str(data.get("api_secret") or ""),
            str(data.get("odoo_token") or ""),
            str(data.get("system_mode") or "frappe"),
            str(data.get("work_offline") or "0"),
            str(data.get("server_database") or ""),
            str(data.get("pharmacy_mode") or "0"),
            str(data.get("allow_cashier_pharmacy_sales") or "0"),
            str(data.get("butchery_mode") or "0"),
            str(data.get("bound_device_id") or data.get("device_hardware_id") or ""),
            str(data.get("subscription_days_left") or ""),
            str(data.get("subscription_expiry") or ""),
        ))
        conn.commit()

        # Save logo_path to JSON helper
        try:
            import os, json
            from database.db import get_app_data_dir
            json_path = os.path.join(get_app_data_dir(), "logo_config.json")
            with open(json_path, "w") as f:
                json.dump({"logo_path": data.get("logo_path", "")}, f)
        except Exception as e:
            print(f"[CompanyDefaults] Error saving logo_path to JSON: {e}")
    finally:
        conn.close()


def get_currency_symbol() -> str:
    """
    Returns the active base currency symbol (e.g. 'ZAR ', '$', 'R ', 'ZIG ').
    Falls back to 'server_company_currency' if symbol is missing or generic '$' for non-USD currencies.
    """
    try:
        d = get_defaults() or {}
        sym = (d.get("server_company_currency_symbol") or "").strip()
        ccy = (d.get("server_company_currency") or "").strip().upper()
        if ccy and ccy != "USD":
            if sym and sym not in ("$", ""):
                return f"{sym} " if len(sym) < 4 and not sym.endswith(" ") else sym
            return f"{ccy} "
        return sym or "$"
    except Exception:
        return "$"