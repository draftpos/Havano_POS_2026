
# # =============================================================================
# # models/sale.py  —  SQL Server version (FIXED WITH PRINTING)
# # =============================================================================

# from database.db import get_connection, fetchall_dicts, fetchone_dict
# from models.product import adjust_stock, get_product_by_id
# from models.receipt import ReceiptData, Item
# from services.printing_service import printing_service

# from datetime import date
# import os
# import json


# # =============================================================================
# # INVOICE NUMBER  —  uses prefix + start_number from company_defaults
# #
# # Examples:
# #   prefix="INV",  start=1   →  INV-000001
# #   prefix="HV",   start=100 →  HV-000100
# #   prefix="",     start=1   →  000001
# # =============================================================================

# def _get_invoice_settings() -> tuple[str, int]:
#     """Returns (prefix, start_number) from company_defaults."""
#     try:
#         from models.company_defaults import get_defaults
#         d = get_defaults()
#         prefix = str(d.get("invoice_prefix") or "").strip().upper()
#         start  = int(d.get("invoice_start_number") or 0)
#         return prefix, start
#     except Exception:
#         return "", 0


# def _format_invoice_no(seq: int) -> str:
#     """Format invoice number using company_defaults prefix."""
#     prefix, _ = _get_invoice_settings()
#     number = f"{seq:06d}"
#     return f"{prefix}-{number}" if prefix else number


# def get_next_invoice_number() -> int:
#     """
#     Returns the next invoice sequence number.
#     Starts from invoice_start_number if no sales exist yet,
#     otherwise continues from MAX(invoice_number) + 1.
#     """
#     conn = get_connection()
#     cur  = conn.cursor()
#     cur.execute("SELECT COALESCE(MAX(invoice_number), 0) FROM sales")
#     row = cur.fetchone()
#     conn.close()
#     current_max = int(row[0])
#     if current_max == 0:
#         # First ever invoice — start from company_defaults setting
#         _, start = _get_invoice_settings()
#         return max(start, 1)
#     return current_max + 1


# # =============================================================================
# # READ
# # =============================================================================

# _SALE_SELECT = """
#     SELECT s.id, s.invoice_number, s.created_at, s.cashier_id,
#        s.total, s.tendered, s.method,
#        COALESCE(u.username, '') AS username,
#        s.invoice_no, s.invoice_date, s.kot,
#        s.customer_name, s.customer_contact,
#        s.currency, s.subtotal, s.total_vat,
#        s.discount_amount, s.receipt_type, s.footer,
#        s.cashier_name,
#        s.synced,
#        COALESCE(s.frappe_ref,    '')  AS frappe_ref,
#        COALESCE(s.total_items,   0)   AS total_items,
#        COALESCE(s.change_amount, 0)   AS change_amount,
#        COALESCE(C.company_name,  '')  AS company_name,
#        COALESCE(C.address_1,     '')  AS address_1,
#        COALESCE(C.address_2,     '')  AS address_2,
#        COALESCE(C.vat_number,    '')  AS vat_number,
#        C.tin_number,
#        C.footer_text,
#        C.phone,
#        C.email,
#        C.zimra_serial_no,
#        C.zimra_device_id
# FROM sales s
# LEFT JOIN users u ON u.id = s.cashier_id
# CROSS JOIN company_defaults C 
# """


# def get_all_sales() -> list[dict]:
#     conn = get_connection()
#     cur  = conn.cursor()
#     cur.execute(_SALE_SELECT + " ORDER BY s.id DESC")
#     rows = fetchall_dicts(cur)
#     conn.close()
#     return [_sale_to_dict(r) for r in rows]


# def get_sale_by_id(sale_id: int) -> dict | None:
#     conn = get_connection()
#     cur  = conn.cursor()
#     cur.execute(_SALE_SELECT + " WHERE s.id = ?", (sale_id,))
#     row = fetchone_dict(cur)
#     if not row:
#         conn.close()
#         return None
#     sale = _sale_to_dict(row)
#     sale["items"] = _fetch_items(sale_id, cur)
#     conn.close()
#     # print(f"✅ Sales Data 2   → {sale}\n\n Sql \n  {_SALE_SELECT}")
#     # print(f"✅ \n   → ")
#     return sale


# def get_sale_items(sale_id: int) -> list[dict]:
#     conn = get_connection()
#     cur  = conn.cursor()
#     items = _fetch_items(sale_id, cur)
#     conn.close()
#     return items


# def get_today_sales() -> list[dict]:
#     conn = get_connection()
#     cur  = conn.cursor()
#     cur.execute(
#         _SALE_SELECT +
#         " WHERE CAST(s.created_at AS DATE) = CAST(GETDATE() AS DATE)"
#         " ORDER BY s.id DESC"
#     )
#     rows = fetchall_dicts(cur)
#     conn.close()
#     return [_sale_to_dict(r) for r in rows]


# def get_today_total() -> float:
#     conn = get_connection()
#     cur  = conn.cursor()
#     cur.execute("""
#         SELECT COALESCE(SUM(total), 0)
#         FROM sales
#         WHERE CAST(created_at AS DATE) = CAST(GETDATE() AS DATE)
#     """)
#     row = cur.fetchone()
#     conn.close()
#     return float(row[0])


# def get_today_total_by_method() -> dict:
#     conn = get_connection()
#     cur  = conn.cursor()
#     cur.execute("""
#         SELECT method, COALESCE(SUM(total), 0)
#         FROM sales
#         WHERE CAST(created_at AS DATE) = CAST(GETDATE() AS DATE)
#         GROUP BY method
#     """)
#     rows = cur.fetchall()
#     conn.close()
#     return {r[0]: float(r[1]) for r in rows}


# def get_unsynced_sales() -> list[dict]:
#     conn = get_connection()
#     cur  = conn.cursor()
#     cur.execute(_SALE_SELECT + " WHERE s.synced = 0 ORDER BY s.id")
#     rows = fetchall_dicts(cur)
#     conn.close()
#     return [_sale_to_dict(r) for r in rows]


# def get_sales_with_frappe_ref() -> list[dict]:
#     """Returns all sales that have been matched to a Frappe document."""
#     conn = get_connection()
#     cur  = conn.cursor()
#     cur.execute(
#         _SALE_SELECT +
#         " WHERE s.frappe_ref IS NOT NULL AND s.frappe_ref != ''"
#         " ORDER BY s.id DESC"
#     )
#     rows = fetchall_dicts(cur)
#     conn.close()
#     return [_sale_to_dict(r) for r in rows]


# # =============================================================================
# # WRITE
# # =============================================================================

# def create_sale(
#     items:             list[dict],
#     total:             float,
#     tendered:          float,
#     method:            str   = "Cash",
#     cashier_id:        int   = None,
#     cashier_name:      str   = "",
#     customer_name:     str   = "",
#     customer_contact:  str   = "",
#     company_name:      str   = "",
#     kot:               str   = "",
#     currency:          str   = "USD",
#     subtotal:          float = None,
#     total_vat:         float = 0.0,
#     discount_amount:   float = 0.0,
#     receipt_type:      str   = "Invoice",
#     footer:            str   = "",
#     change_amount:     float = None,
# ) -> dict:
#     from datetime import date
#     from models.product import get_product_by_id, adjust_stock

#     seq           = get_next_invoice_number()
#     invoice_no    = _format_invoice_no(seq)
#     invoice_date  = date.today().isoformat()
#     effective_sub = subtotal if subtotal is not None else total

#     total_items_val = sum(float(it.get("qty", 1)) for it in items)
#     change_val      = change_amount if change_amount is not None else max(float(tendered) - float(total), 0.0)

#     conn = get_connection()
#     cur  = conn.cursor()

#     cur.execute("""
#         INSERT INTO sales (
#             invoice_number, invoice_no, invoice_date,
#             total, tendered, method, cashier_id,
#             cashier_name, customer_name, customer_contact,
#             company_name,
#             kot, currency,
#             subtotal, total_vat, discount_amount,
#             receipt_type, footer, synced,
#             total_items, change_amount
#         )
#         OUTPUT INSERTED.id
#         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
#     """, (
#         seq, invoice_no, invoice_date,
#         float(total), float(tendered), method, cashier_id,
#         cashier_name, customer_name, customer_contact,
#         company_name,
#         kot, currency,
#         float(effective_sub), float(total_vat), float(discount_amount),
#         receipt_type, footer, 0,
#         float(total_items_val), float(change_val),
#     ))

#     sale_id = int(cur.fetchone()[0])

#     for item in items:
#         cur.execute("""
#             INSERT INTO sale_items (
#                 sale_id, part_no, product_name, qty, price,
#                 discount, tax, total,
#                 tax_type, tax_rate, tax_amount, remarks
#             ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
#         """, (
#             sale_id,
#             item.get("part_no",      ""),
#             item.get("product_name", ""),
#             float(item.get("qty",      1)),
#             float(item.get("price",    0)),
#             float(item.get("discount", 0)),
#             item.get("tax",            ""),
#             float(item.get("total",    0)),
#             item.get("tax_type",       ""),
#             float(item.get("tax_rate",   0.0)),
#             float(item.get("tax_amount", 0.0)),
#             item.get("remarks",        ""),
#         ))

#         product_id = item.get("product_id")
#         if product_id:
#             prod_data = get_product_by_id(product_id)
#             factor    = float(prod_data.get("conversion_factor", 1.0) or 1.0)
#             adjust_stock(product_id, -(float(item.get("qty", 1)) * factor))

#     conn.commit()
#     conn.close()

#     # ── FETCH SALE FOR PRINTING ─────────────────────────────
#     sale = get_sale_by_id(sale_id)

#     # ── PRINTING ─────────────────────────────────────────────
#     # active_printers = _get_active_printers()
#     active_printers = _get_active_printers()
#     # print(f"✅ Sales Data → {sale}")
#     if active_printers and sale:
#         footer=sale["footer_text"]
#         try:
#             receipt = ReceiptData(
#                 invoiceNo=sale["invoice_no"],
#                 invoiceDate=sale["invoice_date"],
#                 companyName=sale.get("company_name", "Havano POS"),
#                 companyAddress=sale.get("address_1", ""),
#                 companyAddressLine1=sale.get("address_2", ""),
#                 companyAddressLine2="",
#                 city="",
#                 state="",
#                 postcode="",
#                 companyEmail=sale.get("email", ""),
#                 tel=sale.get("phone", ""),
#                 tin=sale.get("tin_number", ""),
#                 vatNo=sale.get("vat_number", ""),
#                 deviceSerial=sale.get("zimra_serial_no", ""),
#                 deviceId=sale.get("zimra_device_id", ""),
#                 cashierName=sale.get("cashier_name", cashier_name),
#                 customerName=sale.get("customer_name", customer_name),
#                 customerContact=sale.get("customer_contact", customer_contact),
#                 customerTin="",
#                 customerVat="",
#                 amountTendered=float(tendered),
#                 change=float(sale.get("change_amount", 0)),
#                 grandTotal=float(total),
#                 subtotal=float(sale.get("subtotal", effective_sub)),
#                 totalVat=float(sale.get("total_vat", 0)),
#                 currency=currency,
#                 footer=footer or "Thank you for your purchase!",
#                 KOT=kot or "",
#                 paymentMode=method,
#             )

#             for it in sale.get("items", []):
#                 receipt.items.append(Item(
#                     productName=it["product_name"],
#                     productid=it.get("part_no", ""),
#                     qty=float(it["qty"]),
#                     price=float(it["price"]),
#                     amount=float(it["total"]),
#                     tax_amount=float(it.get("tax_amount", 0))
#                 ))

#             print(f"Active Printer {active_printers}")
#             # return
#             for printer_name in active_printers:
#                 try:
#                     success = printing_service.print_receipt(receipt, printer_name=printer_name)
#                     if success:
#                         print(f"✅ Receipt printed successfully → {printer_name}")
#                     else:
#                         print(f"⚠️ Print failed on {printer_name}")
#                 except Exception as e:
#                     print(f"❌ Printer error on {printer_name}: {e}")



#         except Exception as e:
#             print(f"❌ PRINT ERROR: {str(e)}")
#             import traceback
#             traceback.print_exc()

#     else:
#         print("⚠️ No active printers configured")


#         # ====================== KITCHEN ORDERS (KOT) ======================
#     print_kitchen_orders(sale)          # ←←← MOVED HERE (before return)

#     return sale



#         # ── KITCHEN ORDERS (NEW) ─────────────────────────────
#     # print_kitchen_orders(sale)

# def mark_synced(sale_id: int) -> bool:
#     """Mark a sale as synced (no Frappe ref available)."""
#     conn = get_connection()
#     cur  = conn.cursor()
#     cur.execute("UPDATE sales SET synced = 1 WHERE id = ?", (sale_id,))
#     affected = cur.rowcount
#     conn.commit()
#     conn.close()
#     return affected > 0


# def mark_synced_with_ref(sale_id: int, frappe_ref: str = "") -> bool:
#     """
#     Mark a sale as synced and store the Frappe document name.

#     frappe_ref: Frappe Sales Invoice name e.g. 'ACC-SINV-2026-00565'
#                 Pass empty string for permanent-error cases (not-sales-item etc.)
#                 where the sale is marked done but has no Frappe counterpart.
#     """
#     conn = get_connection()
#     cur  = conn.cursor()
#     cur.execute(
#         "UPDATE sales SET synced = 1, frappe_ref = ? WHERE id = ?",
#         (frappe_ref or None, sale_id)
#     )
#     affected = cur.rowcount
#     conn.commit()
#     conn.close()
#     return affected > 0


# def mark_many_synced(sale_ids: list[int]) -> int:
#     if not sale_ids:
#         return 0
#     conn = get_connection()
#     cur  = conn.cursor()
#     placeholders = ", ".join("?" * len(sale_ids))
#     cur.execute(f"UPDATE sales SET synced = 1 WHERE id IN ({placeholders})", sale_ids)
#     affected = cur.rowcount
#     conn.commit()
#     conn.close()
#     return affected


# def delete_sale(sale_id: int) -> bool:
#     conn = get_connection()
#     cur  = conn.cursor()
#     cur.execute("DELETE FROM sales WHERE id = ?", (sale_id,))
#     affected = cur.rowcount
#     conn.commit()
#     conn.close()
#     return affected > 0


# # =============================================================================
# # MIGRATION
# # =============================================================================

# def migrate():
#     conn = get_connection()
#     cur  = conn.cursor()

#     cur.execute("""
#         IF NOT EXISTS (
#             SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'sales'
#         )
#         CREATE TABLE sales (
#             id               INT           IDENTITY(1,1) PRIMARY KEY,
#             invoice_number   INT           NOT NULL DEFAULT 0,
#             invoice_no       NVARCHAR(40)  NOT NULL DEFAULT '',
#             invoice_date     NVARCHAR(20)  NOT NULL DEFAULT '',
#             total            DECIMAL(12,2) NOT NULL DEFAULT 0,
#             tendered         DECIMAL(12,2) NOT NULL DEFAULT 0,
#             method           NVARCHAR(30)  NOT NULL DEFAULT 'Cash',
#             cashier_id       INT           NULL,
#             cashier_name     NVARCHAR(120) NOT NULL DEFAULT '',
#             customer_name    NVARCHAR(120) NOT NULL DEFAULT '',
#             customer_contact NVARCHAR(80)  NOT NULL DEFAULT '',
#             company_name     NVARCHAR(120) NOT NULL DEFAULT '',
#             kot              NVARCHAR(40)  NOT NULL DEFAULT '',
#             currency         NVARCHAR(10)  NOT NULL DEFAULT 'USD',
#             subtotal         DECIMAL(12,2) NOT NULL DEFAULT 0,
#             total_vat        DECIMAL(12,2) NOT NULL DEFAULT 0,
#             discount_amount  DECIMAL(12,2) NOT NULL DEFAULT 0,
#             receipt_type     NVARCHAR(30)  NOT NULL DEFAULT 'Invoice',
#             footer           NVARCHAR(MAX) NOT NULL DEFAULT '',
#             created_at       DATETIME2     NOT NULL DEFAULT SYSDATETIME(),
#             total_items      DECIMAL(12,4) NOT NULL DEFAULT 0,
#             change_amount    DECIMAL(12,2) NOT NULL DEFAULT 0,
#             synced           INT           NOT NULL DEFAULT 0,
#             frappe_ref       NVARCHAR(80)  NULL
#         )
#     """)

#     for col, definition in [
#         ("total_items",   "DECIMAL(12,4) NOT NULL DEFAULT 0"),
#         ("change_amount", "DECIMAL(12,2) NOT NULL DEFAULT 0"),
#         ("synced",        "INT NOT NULL DEFAULT 0"),
#         ("company_name",  "NVARCHAR(120) NOT NULL DEFAULT ''"),
#         ("frappe_ref",    "NVARCHAR(80) NULL"),                  # ← Frappe doc name
#     ]:
#         cur.execute(f"""
#             IF NOT EXISTS (
#                 SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
#                 WHERE TABLE_NAME = 'sales' AND COLUMN_NAME = '{col}'
#             )
#             ALTER TABLE sales ADD {col} {definition}
#         """)

#     cur.execute("""
#         IF NOT EXISTS (
#             SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'sale_items'
#         )
#         CREATE TABLE sale_items (
#             id           INT           IDENTITY(1,1) PRIMARY KEY,
#             sale_id      INT           NOT NULL
#                              REFERENCES sales(id) ON DELETE CASCADE,
#             part_no      NVARCHAR(50)  NOT NULL DEFAULT '',
#             product_name NVARCHAR(120) NOT NULL,
#             qty          DECIMAL(12,4) NOT NULL DEFAULT 1,
#             price        DECIMAL(12,2) NOT NULL DEFAULT 0,
#             discount     DECIMAL(12,2) NOT NULL DEFAULT 0,
#             tax          NVARCHAR(20)  NOT NULL DEFAULT '',
#             total        DECIMAL(12,2) NOT NULL DEFAULT 0,
#             tax_type     NVARCHAR(20)  NOT NULL DEFAULT '',
#             tax_rate     DECIMAL(8,4)  NOT NULL DEFAULT 0,
#             tax_amount   DECIMAL(12,2) NOT NULL DEFAULT 0,
#             remarks      NVARCHAR(MAX) NOT NULL DEFAULT ''
#         )
#     """)

#     conn.commit()
#     conn.close()
#     print("[sale] ✅  Tables ready.")


# # =============================================================================
# # PRIVATE
# # =============================================================================

# def _fetch_items(sale_id: int, cur) -> list[dict]:
#     cur.execute("""
#        SELECT s.id, s.sale_id, s.part_no, s.product_name, qty, s.price,
#                discount, tax, total,
#                tax_type, tax_rate, tax_amount, remarks,order_1,order_2,order_3,order_4,order_5,order_6  
#         FROM sale_items s
# 		inner join products p on p.part_no= s.part_no  
#                 WHERE sale_id = ?
#         ORDER BY id
#     """, (sale_id,))
#     return [_item_to_dict(r) for r in fetchall_dicts(cur)]


# def _item_to_dict(row: dict) -> dict:
#     return {
#         "id":           row["id"],
#         "sale_id":      row["sale_id"],
#         "part_no":      row.get("part_no", "") or "",
#         "product_name": row.get("product_name", "") or "",
#         "qty":          float(row.get("qty", 0)),
#         "price":        float(row.get("price", 0)),
#         "discount":     float(row.get("discount", 0)),
#         "tax":          row.get("tax", "") or "",
#         "total":        float(row.get("total", 0)),
#         "tax_type":     row.get("tax_type", "") or "",
#         "tax_rate":     float(row.get("tax_rate", 0)),
#         "tax_amount":   float(row.get("tax_amount", 0)),
#         "remarks":      row.get("remarks", "") or "",

#         # ── ORDER FLAGS (used for KOT routing) ─────────────────────
#         "order_1": row.get("order_1", False),
#         "order_2": row.get("order_2", False),
#         "order_3": row.get("order_3", False),
#         "order_4": row.get("order_4", False),
#         "order_5": row.get("order_5", False),
#         "order_6": row.get("order_6", False),
#     }

# def _sale_to_dict(row: dict) -> dict:
#     from datetime import datetime
#     raw_dt = row.get("created_at")
#     if isinstance(raw_dt, str):
#         try:
#             dt = datetime.fromisoformat(raw_dt)
#         except Exception:
#             dt = None
#     elif hasattr(raw_dt, "strftime"):
#         dt = raw_dt
#     else:
#         dt = None

#     return {
#         "id":               row["id"],
#         "number":           row["invoice_number"],
#         "date":             f"{dt.month}/{dt.day}/{dt.year}" if dt else "",
#         "time":             dt.strftime("%H:%M")             if dt else "",
#         "cashier_id":       row["cashier_id"],
#         "user":             row["username"] or str(row["cashier_id"] or ""),
#         "total":            float(row["total"]),
#         "tendered":         float(row["tendered"]),
#         "method":           row["method"]           or "Cash",
#         "amount":           float(row["total"]),
#         "invoice_no":       row["invoice_no"]       or "",
#         "invoice_date":     row["invoice_date"]     or "",
#         "kot":              row["kot"]              or "",
#         "customer_name":    row["customer_name"]    or "",
#         "customer_contact": row["customer_contact"] or "",
#         "company_name":     row["company_name"]     or "",
#         "currency":         row["currency"]         or "USD",
#         "subtotal":         float(row["subtotal"]        or 0),
#         "total_vat":        float(row["total_vat"]       or 0),
#         "discount_amount":  float(row["discount_amount"] or 0),
#         "receipt_type":     row["receipt_type"]     or "Invoice",
#         "footer":           row["footer"]           or "",
#         "cashier_name":     row["cashier_name"]     or "",
#         "synced":           bool(row.get("synced", False)),
#         "frappe_ref":       row.get("frappe_ref")   or "",      # ← Frappe doc name
#         "total_items":      float(row.get("total_items",   0) or 0),
#         "change_amount":    float(row.get("change_amount", 0) or 0),
#         "company_name":     row.get("company_name", "Havano POS"),
#         "address_1":        row.get("address_1", ""),
#         "address_2":        row.get("address_2", ""),
#         "phone":            row.get("phone", ""),
#         "email":            row.get("email", ""),
#         "vat_number":       row.get("vat_number", ""),
#         "tin_number":       row.get("tin_number", ""),
#         "zimra_serial_no":  row.get("zimra_serial_no", ""),
#         "zimra_device_id":  row.get("zimra_device_id", ""),
#         "footer_text":      row.get("footer_text", ""),
#     }


# def _item_to_dict(row: dict) -> dict:
#     return {
#         "id":           row["id"],
#         "sale_id":      row["sale_id"],
#         "part_no":      row["part_no"]      or "",
#         "product_name": row["product_name"] or "",
#         "qty":          float(row["qty"]),
#         "price":        float(row["price"]),
#         "discount":     float(row["discount"]),
#         "tax":          row["tax"]          or "",
#         "total":        float(row["total"]),
#         "tax_type":     row["tax_type"]     or "",
#         "tax_rate":     float(row["tax_rate"]   or 0),
#         "tax_amount":   float(row["tax_amount"] or 0),
#         "remarks":      row["remarks"]      or "",
#         # ── NEW ORDER COLUMNS ─────────────────────────────────────
#         "order_1": row.get("order_1", "") or "",
#         "order_2": row.get("order_2", "") or "",
#         "order_3": row.get("order_3", "") or "",
#         "order_4": row.get("order_4", "") or "",
#         "order_5": row.get("order_5", "") or "",
#         "order_6": row.get("order_6", "") or "",
#     }


# # =============================================================================
# # GET ACTIVE PRINTERS
# # =============================================================================
# def _get_active_printers() -> list[str]:
#     hw_file = os.path.join(os.path.dirname(__file__), "..", "hardware_settings.json")

#     try:
#         with open(hw_file, "r", encoding="utf-8") as f:
#             hw = json.load(f)

#         printers = []

#         if hw.get("main_printer") and hw["main_printer"] != "(None)":
#             printers.append(hw["main_printer"])

#         # for station in hw.get("orders", {}).values():
#         #     if station.get("active") and station.get("printer") != "(None)":
#         #         printers.append(station["printer"])

#         return list(dict.fromkeys(printers))

#     except:
#         return []



# # def _get_active_printersorder() -> list[str]:
# #     hw_file = os.path.join(os.path.dirname(__file__), "..", "hardware_settings.json")

# #     try:
# #         with open(hw_file, "r", encoding="utf-8") as f:
# #             hw = json.load(f)

# #         printers = []

# #         # if hw.get("main_printer") and hw["main_printer"] != "(None)":
# #         #     printers.append(hw["main_printer"])

# #         for station in hw.get("orders", {}).values():
# #             if station.get("active") and station.get("printer") != "(None)":
# #                 printers.append(station["printer"])

# #         return list(dict.fromkeys(printers))

# #     except:
# #         return []
# # # =============================================================================
# # KITCHEN ORDER PRINTING (Multi-Station)
# # =============================================================================
# def print_kitchen_orders(sale: dict):
#     """Print separate KOT for every active Order 1–6 station"""
#     try:
#         hw_file = os.path.join(os.path.dirname(__file__), "..", "hardware_settings.json")
#         with open(hw_file, "r", encoding="utf-8") as f:
#             hw = json.load(f)

#         orders_config = hw.get("orders", {})

#         for order_key in ["Order 1", "Order 2", "Order 3", "Order 4", "Order 5", "Order 6"]:
#             config = orders_config.get(order_key, {})
#             if not config.get("active", False):
#                 continue

#             printer_name = config.get("printer")
#             if not printer_name or printer_name == "(None)":
#                 continue

#             # Filter items that belong to this order
#             order_items = [
#                 it for it in sale.get("items", [])
#                 if it.get(order_key.lower().replace(" ", "_"))  # order_1, order_2...
#             ]

#             if not order_items:
#                 continue

#             # Build mini ReceiptData for KOT
#             from models.receipt import ReceiptData, Item
#             kot_receipt = ReceiptData(
#                 invoiceNo=sale["invoice_no"],
#                 KOT=order_key,
#                 cashierName=sale.get("cashier_name", ""),
#                 items=[Item(
#                     productName=it["product_name"],
#                     qty=float(it["qty"]),
#                     productid=it.get("part_no", "")
#                 ) for it in order_items]
#             )

#             success = printing_service.print_kitchen_order(kot_receipt, printer_name=printer_name)
#             if success:
#                 print(f"✅ KOT printed for {order_key} → {printer_name}")
#             else:
#                 print(f"⚠️ KOT failed for {order_key}")

#     except Exception as e:
#         print(f"❌ Kitchen Order printing error: {e}")

# def create_credit_note(original_sale_id: int, items_to_return: list[dict]) -> bool:
#     """
#     Processes a return.
#     1. Adjusts stock (adds items back).
#     2. Records the credit note entry.
#     """
#     from models.product import adjust_stock
#     conn = get_connection()
#     cur  = conn.cursor()
#     try:
#         for item in items_to_return:
#             # 1. Add the quantity back to inventory
#             if item.get("product_id"):
#                 adjust_stock(item["product_id"], float(item["qty"]))
            
#             # 2. Record the credit note entry
#             cur.execute("""
#                 INSERT INTO credit_notes (original_sale_id, part_no, qty, reason, created_at)
#                 VALUES (?, ?, ?, ?, GETDATE())
#             """, (
#                 original_sale_id,
#                 item["part_no"],
#                 item["qty"],
#                 item.get("reason", "Customer Return"),
#             ))
            
#         conn.commit()
#         return True
#     except Exception as e:
#         conn.rollback()
#         raise e
#     finally:
#         conn.close()
# =============================================================================
# models/sale.py  —  SQL Server version (FIXED WITH PRINTING)
# =============================================================================

from database.db import get_connection, fetchall_dicts, fetchone_dict
from models.product import adjust_stock, get_product_by_id
from models.receipt import ReceiptData, Item
from services.printing_service import printing_service

from datetime import date
import os
import json


# =============================================================================
# INVOICE NUMBER  —  uses prefix + start_number from company_defaults
#
# Examples:
#   prefix="INV",  start=1   →  INV-000001
#   prefix="HV",   start=100 →  HV-000100
#   prefix="",     start=1   →  000001
# =============================================================================

def _get_invoice_settings() -> tuple[str, int]:
    """Returns (prefix, start_number) from company_defaults."""
    try:
        from models.company_defaults import get_defaults
        d = get_defaults()
        prefix = str(d.get("invoice_prefix") or "").strip().upper()
        start  = int(d.get("invoice_start_number") or 0)
        return prefix, start
    except Exception:
        return "", 0


def _format_invoice_no(seq: int) -> str:
    """Format invoice number using company_defaults prefix."""
    prefix, _ = _get_invoice_settings()
    number = f"{seq:06d}"
    return f"{prefix}-{number}" if prefix else number


def get_next_invoice_number() -> int:
    """
    Returns the next invoice sequence number.
    Starts from invoice_start_number if no sales exist yet,
    otherwise continues from MAX(invoice_number) + 1.
    """
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("SELECT COALESCE(MAX(invoice_number), 0) FROM sales")
    row = cur.fetchone()
    conn.close()
    current_max = int(row[0])
    if current_max == 0:
        _, start = _get_invoice_settings()
        return max(start, 1)
    return current_max + 1


# =============================================================================
# READ
# =============================================================================

_SALE_SELECT = """
    SELECT s.id, s.invoice_number, s.created_at, s.cashier_id,
       s.total, s.tendered, s.method,
       COALESCE(u.username, '') AS username,
       s.invoice_no, s.invoice_date, s.kot,
       s.customer_name, s.customer_contact,
       s.currency, s.subtotal, s.total_vat,
       s.discount_amount, s.receipt_type, s.footer,
       s.cashier_name,
       s.synced,
       COALESCE(s.frappe_ref,    '')  AS frappe_ref,
       COALESCE(s.total_items,   0)   AS total_items,
       COALESCE(s.change_amount, 0)   AS change_amount,
       COALESCE(C.company_name,  '')  AS company_name,
       COALESCE(C.address_1,     '')  AS address_1,
       COALESCE(C.address_2,     '')  AS address_2,
       COALESCE(C.vat_number,    '')  AS vat_number,
       C.tin_number,
       C.footer_text,
       C.phone,
       C.email,
       C.zimra_serial_no,
       C.zimra_device_id
FROM sales s
LEFT JOIN users u ON u.id = s.cashier_id
CROSS JOIN company_defaults C
"""


def get_all_sales() -> list[dict]:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(_SALE_SELECT + " ORDER BY s.id DESC")
    rows = fetchall_dicts(cur)
    conn.close()
    return [_sale_to_dict(r) for r in rows]


def get_sale_by_id(sale_id: int) -> dict | None:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(_SALE_SELECT + " WHERE s.id = ?", (sale_id,))
    row = fetchone_dict(cur)
    if not row:
        conn.close()
        return None
    sale = _sale_to_dict(row)
    sale["items"] = _fetch_items(sale_id, cur)
    conn.close()
    return sale


def get_sale_items(sale_id: int) -> list[dict]:
    conn = get_connection()
    cur  = conn.cursor()
    items = _fetch_items(sale_id, cur)
    conn.close()
    return items


def get_today_sales() -> list[dict]:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(
        _SALE_SELECT +
        " WHERE CAST(s.created_at AS DATE) = CAST(GETDATE() AS DATE)"
        " ORDER BY s.id DESC"
    )
    rows = fetchall_dicts(cur)
    conn.close()
    return [_sale_to_dict(r) for r in rows]


def get_today_total() -> float:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT COALESCE(SUM(total), 0)
        FROM sales
        WHERE CAST(created_at AS DATE) = CAST(GETDATE() AS DATE)
    """)
    row = cur.fetchone()
    conn.close()
    return float(row[0])


def get_today_total_by_method() -> dict:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT method, COALESCE(SUM(total), 0)
        FROM sales
        WHERE CAST(created_at AS DATE) = CAST(GETDATE() AS DATE)
        GROUP BY method
    """)
    rows = cur.fetchall()
    conn.close()
    return {r[0]: float(r[1]) for r in rows}


def get_unsynced_sales() -> list[dict]:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(_SALE_SELECT + " WHERE s.synced = 0 ORDER BY s.id")
    rows = fetchall_dicts(cur)
    conn.close()
    return [_sale_to_dict(r) for r in rows]


def get_sales_with_frappe_ref() -> list[dict]:
    """Returns all sales that have been matched to a Frappe document."""
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(
        _SALE_SELECT +
        " WHERE s.frappe_ref IS NOT NULL AND s.frappe_ref != ''"
        " ORDER BY s.id DESC"
    )
    rows = fetchall_dicts(cur)
    conn.close()
    return [_sale_to_dict(r) for r in rows]


# =============================================================================
# WRITE
# =============================================================================

def create_sale(
    items:             list[dict],
    total:             float,
    tendered:          float,
    method:            str   = "Cash",
    cashier_id:        int   = None,
    cashier_name:      str   = "",
    customer_name:     str   = "",
    customer_contact:  str   = "",
    company_name:      str   = "",
    kot:               str   = "",
    currency:          str   = "USD",
    subtotal:          float = None,
    total_vat:         float = 0.0,
    discount_amount:   float = 0.0,
    receipt_type:      str   = "Invoice",
    footer:            str   = "",
    change_amount:     float = None,
) -> dict:
    from datetime import date
    from models.product import get_product_by_id, adjust_stock

    seq           = get_next_invoice_number()
    invoice_no    = _format_invoice_no(seq)
    invoice_date  = date.today().isoformat()
    effective_sub = subtotal if subtotal is not None else total

    total_items_val = sum(float(it.get("qty", 1)) for it in items)
    change_val      = change_amount if change_amount is not None else max(float(tendered) - float(total), 0.0)

    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""
        INSERT INTO sales (
            invoice_number, invoice_no, invoice_date,
            total, tendered, method, cashier_id,
            cashier_name, customer_name, customer_contact,
            company_name,
            kot, currency,
            subtotal, total_vat, discount_amount,
            receipt_type, footer, synced,
            total_items, change_amount
        )
        OUTPUT INSERTED.id
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        seq, invoice_no, invoice_date,
        float(total), float(tendered), method, cashier_id,
        cashier_name, customer_name, customer_contact,
        company_name,
        kot, currency,
        float(effective_sub), float(total_vat), float(discount_amount),
        receipt_type, footer, 0,
        float(total_items_val), float(change_val),
    ))

    sale_id = int(cur.fetchone()[0])

    for item in items:
        cur.execute("""
            INSERT INTO sale_items (
                sale_id, part_no, product_name, qty, price,
                discount, tax, total,
                tax_type, tax_rate, tax_amount, remarks
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sale_id,
            item.get("part_no",      ""),
            item.get("product_name", ""),
            float(item.get("qty",      1)),
            float(item.get("price",    0)),
            float(item.get("discount", 0)),
            item.get("tax",            ""),
            float(item.get("total",    0)),
            item.get("tax_type",       ""),
            float(item.get("tax_rate",   0.0)),
            float(item.get("tax_amount", 0.0)),
            item.get("remarks",        ""),
        ))

        product_id = item.get("product_id")
        if product_id:
            prod_data = get_product_by_id(product_id)
            factor    = float(prod_data.get("conversion_factor", 1.0) or 1.0)
            adjust_stock(product_id, -(float(item.get("qty", 1)) * factor))

    conn.commit()
    conn.close()

    # ── FETCH SALE FOR PRINTING ─────────────────────────────
    sale = get_sale_by_id(sale_id)

    # ── PRINTING ─────────────────────────────────────────────
    active_printers = _get_active_printers()
    if active_printers and sale:
        footer = sale["footer_text"]
        try:
            receipt = ReceiptData(
                invoiceNo=sale["invoice_no"],
                invoiceDate=sale["invoice_date"],
                companyName=sale.get("company_name", "Havano POS"),
                companyAddress=sale.get("address_1", ""),
                companyAddressLine1=sale.get("address_2", ""),
                companyAddressLine2="",
                city="",
                state="",
                postcode="",
                companyEmail=sale.get("email", ""),
                tel=sale.get("phone", ""),
                tin=sale.get("tin_number", ""),
                vatNo=sale.get("vat_number", ""),
                deviceSerial=sale.get("zimra_serial_no", ""),
                deviceId=sale.get("zimra_device_id", ""),
                cashierName=sale.get("cashier_name", cashier_name),
                customerName=sale.get("customer_name", customer_name),
                customerContact=sale.get("customer_contact", customer_contact),
                customerTin="",
                customerVat="",
                amountTendered=float(tendered),
                change=float(sale.get("change_amount", 0)),
                grandTotal=float(total),
                subtotal=float(sale.get("subtotal", effective_sub)),
                totalVat=float(sale.get("total_vat", 0)),
                currency=currency,
                footer=footer or "Thank you for your purchase!",
                KOT=kot or "",
                paymentMode=method,
            )

            for it in sale.get("items", []):
                receipt.items.append(Item(
                    productName=it["product_name"],
                    productid=it.get("part_no", ""),
                    qty=float(it["qty"]),
                    price=float(it["price"]),
                    amount=float(it["total"]),
                    tax_amount=float(it.get("tax_amount", 0))
                ))

            print(f"Active Printer {active_printers}")
            for printer_name in active_printers:
                try:
                    success = printing_service.print_receipt(receipt, printer_name=printer_name)
                    if success:
                        print(f"✅ Receipt printed successfully → {printer_name}")
                    else:
                        print(f"⚠️ Print failed on {printer_name}")
                except Exception as e:
                    print(f"❌ Printer error on {printer_name}: {e}")

        except Exception as e:
            print(f"❌ PRINT ERROR: {str(e)}")
            import traceback
            traceback.print_exc()

    else:
        print("⚠️ No active printers configured")

    # ── KITCHEN ORDERS (KOT) ─────────────────────────────────
    print_kitchen_orders(sale)

    return sale


def mark_synced(sale_id: int) -> bool:
    """Mark a sale as synced (no Frappe ref available)."""
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("UPDATE sales SET synced = 1 WHERE id = ?", (sale_id,))
    affected = cur.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def mark_synced_with_ref(sale_id: int, frappe_ref: str = "") -> bool:
    """
    Mark a sale as synced and store the Frappe document name.

    frappe_ref: Frappe Sales Invoice name e.g. 'ACC-SINV-2026-00565'
                Pass empty string for permanent-error cases (not-sales-item etc.)
                where the sale is marked done but has no Frappe counterpart.
    """
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(
        "UPDATE sales SET synced = 1, frappe_ref = ? WHERE id = ?",
        (frappe_ref or None, sale_id)
    )
    affected = cur.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def mark_many_synced(sale_ids: list[int]) -> int:
    if not sale_ids:
        return 0
    conn = get_connection()
    cur  = conn.cursor()
    placeholders = ", ".join("?" * len(sale_ids))
    cur.execute(f"UPDATE sales SET synced = 1 WHERE id IN ({placeholders})", sale_ids)
    affected = cur.rowcount
    conn.commit()
    conn.close()
    return affected


def delete_sale(sale_id: int) -> bool:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("DELETE FROM sales WHERE id = ?", (sale_id,))
    affected = cur.rowcount
    conn.commit()
    conn.close()
    return affected > 0


# =============================================================================
# MIGRATION
# =============================================================================

def migrate():
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'sales'
        )
        CREATE TABLE sales (
            id               INT           IDENTITY(1,1) PRIMARY KEY,
            invoice_number   INT           NOT NULL DEFAULT 0,
            invoice_no       NVARCHAR(40)  NOT NULL DEFAULT '',
            invoice_date     NVARCHAR(20)  NOT NULL DEFAULT '',
            total            DECIMAL(12,2) NOT NULL DEFAULT 0,
            tendered         DECIMAL(12,2) NOT NULL DEFAULT 0,
            method           NVARCHAR(30)  NOT NULL DEFAULT 'Cash',
            cashier_id       INT           NULL,
            cashier_name     NVARCHAR(120) NOT NULL DEFAULT '',
            customer_name    NVARCHAR(120) NOT NULL DEFAULT '',
            customer_contact NVARCHAR(80)  NOT NULL DEFAULT '',
            company_name     NVARCHAR(120) NOT NULL DEFAULT '',
            kot              NVARCHAR(40)  NOT NULL DEFAULT '',
            currency         NVARCHAR(10)  NOT NULL DEFAULT 'USD',
            subtotal         DECIMAL(12,2) NOT NULL DEFAULT 0,
            total_vat        DECIMAL(12,2) NOT NULL DEFAULT 0,
            discount_amount  DECIMAL(12,2) NOT NULL DEFAULT 0,
            receipt_type     NVARCHAR(30)  NOT NULL DEFAULT 'Invoice',
            footer           NVARCHAR(MAX) NOT NULL DEFAULT '',
            created_at       DATETIME2     NOT NULL DEFAULT SYSDATETIME(),
            total_items      DECIMAL(12,4) NOT NULL DEFAULT 0,
            change_amount    DECIMAL(12,2) NOT NULL DEFAULT 0,
            synced           INT           NOT NULL DEFAULT 0,
            frappe_ref       NVARCHAR(80)  NULL
        )
    """)

    for col, definition in [
        ("total_items",   "DECIMAL(12,4) NOT NULL DEFAULT 0"),
        ("change_amount", "DECIMAL(12,2) NOT NULL DEFAULT 0"),
        ("synced",        "INT NOT NULL DEFAULT 0"),
        ("company_name",  "NVARCHAR(120) NOT NULL DEFAULT ''"),
        ("frappe_ref",    "NVARCHAR(80) NULL"),
    ]:
        cur.execute(f"""
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = 'sales' AND COLUMN_NAME = '{col}'
            )
            ALTER TABLE sales ADD {col} {definition}
        """)

    cur.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'sale_items'
        )
        CREATE TABLE sale_items (
            id           INT           IDENTITY(1,1) PRIMARY KEY,
            sale_id      INT           NOT NULL
                             REFERENCES sales(id) ON DELETE CASCADE,
            part_no      NVARCHAR(50)  NOT NULL DEFAULT '',
            product_name NVARCHAR(120) NOT NULL DEFAULT '',
            qty          DECIMAL(12,4) NOT NULL DEFAULT 1,
            price        DECIMAL(12,2) NOT NULL DEFAULT 0,
            discount     DECIMAL(12,2) NOT NULL DEFAULT 0,
            tax          NVARCHAR(20)  NOT NULL DEFAULT '',
            total        DECIMAL(12,2) NOT NULL DEFAULT 0,
            tax_type     NVARCHAR(20)  NOT NULL DEFAULT '',
            tax_rate     DECIMAL(8,4)  NOT NULL DEFAULT 0,
            tax_amount   DECIMAL(12,2) NOT NULL DEFAULT 0,
            remarks      NVARCHAR(MAX) NOT NULL DEFAULT '',
            order_1      BIT           NOT NULL DEFAULT 0,
            order_2      BIT           NOT NULL DEFAULT 0,
            order_3      BIT           NOT NULL DEFAULT 0,
            order_4      BIT           NOT NULL DEFAULT 0,
            order_5      BIT           NOT NULL DEFAULT 0,
            order_6      BIT           NOT NULL DEFAULT 0
        )
    """)

    # Add missing columns to existing sale_items tables
    for col, definition in [
        ("discount",   "DECIMAL(12,2) NOT NULL DEFAULT 0"),
        ("tax",        "NVARCHAR(20)  NOT NULL DEFAULT ''"),
        ("tax_type",   "NVARCHAR(20)  NOT NULL DEFAULT ''"),
        ("tax_rate",   "DECIMAL(8,4)  NOT NULL DEFAULT 0"),
        ("tax_amount", "DECIMAL(12,2) NOT NULL DEFAULT 0"),
        ("remarks",    "NVARCHAR(MAX) NOT NULL DEFAULT ''"),
        ("order_1",    "BIT           NOT NULL DEFAULT 0"),
        ("order_2",    "BIT           NOT NULL DEFAULT 0"),
        ("order_3",    "BIT           NOT NULL DEFAULT 0"),
        ("order_4",    "BIT           NOT NULL DEFAULT 0"),
        ("order_5",    "BIT           NOT NULL DEFAULT 0"),
        ("order_6",    "BIT           NOT NULL DEFAULT 0"),
    ]:
        cur.execute(f"""
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = 'sale_items' AND COLUMN_NAME = '{col}'
            )
            ALTER TABLE sale_items ADD {col} {definition}
        """)

    conn.commit()
    conn.close()
    print("[sale] ✅  Tables ready.")


# =============================================================================
# PRIVATE HELPERS
# =============================================================================

def _fetch_items(sale_id: int, cur) -> list[dict]:
    cur.execute("""
        SELECT s.id, s.sale_id, s.part_no, s.product_name, s.qty, s.price,
               s.discount, s.tax, s.total,
               s.tax_type, s.tax_rate, s.tax_amount, s.remarks,
               s.order_1, s.order_2, s.order_3, s.order_4, s.order_5, s.order_6
        FROM sale_items s
        INNER JOIN products p ON p.part_no = s.part_no
        WHERE s.sale_id = ?
        ORDER BY s.id
    """, (sale_id,))
    return [_item_to_dict(r) for r in fetchall_dicts(cur)]


def _item_to_dict(row: dict) -> dict:
    return {
        "id":           row["id"],
        "sale_id":      row["sale_id"],
        "part_no":      row.get("part_no",      "") or "",
        "product_name": row.get("product_name", "") or "",
        "qty":          float(row.get("qty",    0)),
        "price":        float(row.get("price",  0)),
        "discount":     float(row.get("discount", 0)),
        "tax":          row.get("tax",      "") or "",
        "total":        float(row.get("total",  0)),
        "tax_type":     row.get("tax_type", "") or "",
        "tax_rate":     float(row.get("tax_rate",   0) or 0),
        "tax_amount":   float(row.get("tax_amount", 0) or 0),
        "remarks":      row.get("remarks",  "") or "",
        # ── ORDER FLAGS (used for KOT routing) ──────────────────────
        "order_1": bool(row.get("order_1", False)),
        "order_2": bool(row.get("order_2", False)),
        "order_3": bool(row.get("order_3", False)),
        "order_4": bool(row.get("order_4", False)),
        "order_5": bool(row.get("order_5", False)),
        "order_6": bool(row.get("order_6", False)),
    }


def _sale_to_dict(row: dict) -> dict:
    from datetime import datetime
    raw_dt = row.get("created_at")
    if isinstance(raw_dt, str):
        try:
            dt = datetime.fromisoformat(raw_dt)
        except Exception:
            dt = None
    elif hasattr(raw_dt, "strftime"):
        dt = raw_dt
    else:
        dt = None

    return {
        "id":               row["id"],
        "number":           row["invoice_number"],
        "date":             f"{dt.month}/{dt.day}/{dt.year}" if dt else "",
        "time":             dt.strftime("%H:%M")             if dt else "",
        "cashier_id":       row["cashier_id"],
        "user":             row["username"] or str(row["cashier_id"] or ""),
        "total":            float(row["total"]),
        "tendered":         float(row["tendered"]),
        "method":           row["method"]           or "Cash",
        "amount":           float(row["total"]),
        "invoice_no":       row["invoice_no"]       or "",
        "invoice_date":     row["invoice_date"]     or "",
        "kot":              row["kot"]              or "",
        "customer_name":    row["customer_name"]    or "",
        "customer_contact": row["customer_contact"] or "",
        "company_name":     row.get("company_name", "Havano POS"),
        "currency":         row["currency"]         or "USD",
        "subtotal":         float(row["subtotal"]        or 0),
        "total_vat":        float(row["total_vat"]       or 0),
        "discount_amount":  float(row["discount_amount"] or 0),
        "receipt_type":     row["receipt_type"]     or "Invoice",
        "footer":           row["footer"]           or "",
        "cashier_name":     row["cashier_name"]     or "",
        "synced":           bool(row.get("synced", False)),
        "frappe_ref":       row.get("frappe_ref")   or "",
        "total_items":      float(row.get("total_items",   0) or 0),
        "change_amount":    float(row.get("change_amount", 0) or 0),
        "address_1":        row.get("address_1",        ""),
        "address_2":        row.get("address_2",        ""),
        "phone":            row.get("phone",            ""),
        "email":            row.get("email",            ""),
        "vat_number":       row.get("vat_number",       ""),
        "tin_number":       row.get("tin_number",       ""),
        "zimra_serial_no":  row.get("zimra_serial_no",  ""),
        "zimra_device_id":  row.get("zimra_device_id",  ""),
        "footer_text":      row.get("footer_text",      ""),
    }


# =============================================================================
# GET ACTIVE PRINTERS
# =============================================================================

def _get_active_printers() -> list[str]:
    hw_file = os.path.join(os.path.dirname(__file__), "..", "hardware_settings.json")
    try:
        with open(hw_file, "r", encoding="utf-8") as f:
            hw = json.load(f)
        printers = []
        if hw.get("main_printer") and hw["main_printer"] != "(None)":
            printers.append(hw["main_printer"])
        return list(dict.fromkeys(printers))
    except Exception:
        return []


# =============================================================================
# KITCHEN ORDER PRINTING (Multi-Station)
# =============================================================================

def print_kitchen_orders(sale: dict):
    """Print separate KOT for every active Order 1–6 station."""
    try:
        hw_file = os.path.join(os.path.dirname(__file__), "..", "hardware_settings.json")
        with open(hw_file, "r", encoding="utf-8") as f:
            hw = json.load(f)

        orders_config = hw.get("orders", {})

        for order_key in ["Order 1", "Order 2", "Order 3", "Order 4", "Order 5", "Order 6"]:
            config = orders_config.get(order_key, {})
            if not config.get("active", False):
                continue

            printer_name = config.get("printer")
            if not printer_name or printer_name == "(None)":
                continue

            # Filter items that belong to this order station
            order_field = order_key.lower().replace(" ", "_")  # "order_1" … "order_6"
            order_items = [
                it for it in sale.get("items", [])
                if it.get(order_field)
            ]

            if not order_items:
                continue

            kot_receipt = ReceiptData(
                invoiceNo=sale["invoice_no"],
                KOT=order_key,
                cashierName=sale.get("cashier_name", ""),
                items=[Item(
                    productName=it["product_name"],
                    qty=float(it["qty"]),
                    productid=it.get("part_no", "")
                ) for it in order_items]
            )

            success = printing_service.print_kitchen_order(kot_receipt, printer_name=printer_name)
            if success:
                print(f"✅ KOT printed for {order_key} → {printer_name}")
            else:
                print(f"⚠️ KOT failed for {order_key}")

    except Exception as e:
        print(f"❌ Kitchen Order printing error: {e}")


# =============================================================================
# CREDIT NOTES  (Returns)
# =============================================================================

def create_credit_note(original_sale_id: int, items_to_return: list[dict]) -> bool:
    """
    Processes a return.
    1. Adjusts stock (adds items back).
    2. Records the credit note entry in credit_notes table.
    """
    from models.product import adjust_stock
    conn = get_connection()
    cur  = conn.cursor()
    try:
        for item in items_to_return:
            # 1. Add the quantity back to inventory
            if item.get("product_id"):
                adjust_stock(item["product_id"], float(item["qty"]))

            # 2. Record the credit note entry
            cur.execute("""
                INSERT INTO credit_notes (original_sale_id, part_no, qty, reason, created_at)
                VALUES (?, ?, ?, ?, GETDATE())
            """, (
                original_sale_id,
                item["part_no"],
                item["qty"],
                item.get("reason", "Customer Return"),
            ))

        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()