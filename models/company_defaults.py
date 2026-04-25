# =============================================================================
# models/company_defaults.py
# =============================================================================

from database.db import get_connection, fetchone_dict

_BLANK = {
    # Editable — receipt header
    "company_name": "", "address_1": "", "address_2": "",
    "email": "", "phone": "", "vat_number": "", "tin_number": "",
    # Editable — receipt header (shown bold/centered below the company block
    # on every sales receipt). Falls back to "*** SALES RECEIPT ***" when blank.
    "receipt_header": "",
    # Editable — receipt footer
    "footer_text": "",
    "allow_credit_sales": "0",
    # Editable — terms & conditions (printed on sales orders)
    "terms_and_conditions": "",
    # Editable — ZIMRA
    "zimra_serial_no": "", "zimra_device_id": "",
    "zimra_api_key": "", "zimra_api_url": "",
    # Editable — invoice numbering
    "invoice_prefix":       "",   # up to 6 chars e.g. "ABC"
    "invoice_start_number": "0",  # integer as string
    # Readable from logo_config.json (not in company_defaults DB record)
    "logo_path":            "",   # local filename
    # Read-only — from login
    "server_company": "", "server_warehouse": "", "server_cost_center": "",
    "server_username": "", "server_email": "", "server_role": "",
    "server_full_name": "", "server_first_name": "", "server_last_name": "",
    "server_mobile": "", "server_profile": "", "server_vat_enabled": "",
    "server_company_currency": "USD",
}


def get_defaults() -> dict:
    conn = get_connection()
    cur  = conn.cursor()
    try:
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
            result[key] = str(row.get(key) or "")
    
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
                vat_number            = ?,
                tin_number            = ?,
                footer_text           = ?,
                receipt_header        = ?,
                terms_and_conditions  = ?,
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
                updated_at            = GETDATE()
            WHERE id = (SELECT MIN(id) FROM company_defaults)
        """, (
            str(data.get("company_name",          "")),
            str(data.get("address_1",             "")),
            str(data.get("address_2",             "")),
            str(data.get("email",                 "")),
            str(data.get("phone",                 "")),
            str(data.get("vat_number",            "")),
            str(data.get("tin_number",            "")),
            str(data.get("footer_text",           "")),
            str(data.get("receipt_header",        "")),
            str(data.get("terms_and_conditions",  "")),
            str(data.get("zimra_serial_no",       "")),
            str(data.get("zimra_device_id",       "")),
            str(data.get("zimra_api_key",         "")),
            str(data.get("zimra_api_url",         "")),
            str(data.get("invoice_prefix",        "")),
            str(data.get("invoice_start_number",  "0")),
            str(data.get("allow_credit_sales",    "0")),
            str(data.get("server_company",        "")),
            str(data.get("server_warehouse",      "")),
            str(data.get("server_cost_center",    "")),
            str(data.get("server_username",       "")),
            str(data.get("server_email",          "")),
            str(data.get("server_role",           "")),
            str(data.get("server_full_name",      "")),
            str(data.get("server_first_name",     "")),
            str(data.get("server_last_name",      "")),
            str(data.get("server_mobile",         "")),
            str(data.get("server_profile",        "")),
            str(data.get("server_vat_enabled",    "")),
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