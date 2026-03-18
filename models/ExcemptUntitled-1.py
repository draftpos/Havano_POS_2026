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
# INVOICE NUMBER
# =============================================================================
def _format_invoice_no(seq: int) -> str:
    return f"ACC-SINV-{date.today().year}-{seq:05d}"


def get_next_invoice_number() -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(MAX(invoice_number), 0) FROM sales")
    row = cur.fetchone()
    conn.close()
    return int(row[0]) + 1


# =============================================================================
# CREATE SALE (WITH PRINTING)
# =============================================================================
def create_sale(
    items: list[dict],
    total: float,
    tendered: float,
    method: str = "Cash",
    cashier_id: int = None,
    cashier_name: str = "",
    customer_name: str = "",
    customer_contact: str = "",
    company_name: str = "",
    kot: str = "",
    currency: str = "USD",
    subtotal: float = None,
    total_vat: float = 0.0,
    discount_amount: float = 0.0,
    receipt_type: str = "Invoice",
    footer: str = "",
    change_amount: float = None,
) -> dict:

    seq = get_next_invoice_number()
    invoice_no = _format_invoice_no(seq)
    invoice_date = date.today().isoformat()

    effective_sub = subtotal if subtotal is not None else total
    total_items_val = sum(float(it.get("qty", 1)) for it in items)
    change_val = change_amount if change_amount is not None else max(float(tendered) - float(total), 0.0)

    conn = get_connection()
    cur = conn.cursor()

    # ── Insert Sale ─────────────────────────────────────────────
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

    # ── Insert Items + Adjust Stock ─────────────────────────────
    for item in items:
        cur.execute("""
            INSERT INTO sale_items (
                sale_id, part_no, product_name, qty, price,
                discount, tax, total,
                tax_type, tax_rate, tax_amount, remarks
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sale_id,
            item.get("part_no", ""),
            item.get("product_name", ""),
            float(item.get("qty", 1)),
            float(item.get("price", 0)),
            float(item.get("discount", 0)),
            item.get("tax", ""),
            float(item.get("total", 0)),
            item.get("tax_type", ""),
            float(item.get("tax_rate", 0.0)),
            float(item.get("tax_amount", 0.0)),
            item.get("remarks", ""),
        ))

        # Adjust stock
        product_id = item.get("product_id")
        if product_id:
            prod = get_product_by_id(product_id)
            factor = float(prod.get("conversion_factor", 1.0) or 1.0)
            adjust_stock(product_id, -(float(item.get("qty", 1)) * factor))

    conn.commit()
    conn.close()

    # ── FETCH SALE FOR PRINTING ─────────────────────────────
    sale = get_sale_by_id(sale_id)

    # ── PRINTING ─────────────────────────────────────────────
    active_printers = _get_active_printers()

    if active_printers and sale:
        try:
            receipt = ReceiptData(
                invoiceNo=sale["invoice_no"],
                invoiceDate=sale["invoice_date"],
                companyName=sale.get("company_name", "Havano POS"),
                cashierName=sale.get("cashier_name", cashier_name),
                customerName=sale.get("customer_name", customer_name),
                customerContact=sale.get("customer_contact", customer_contact),
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

            for printer_name in active_printers:
                print(f"🖨 Printing to: {printer_name}")
                printing_service.print_receipt(receipt, printer_name=printer_name)

        except Exception as e:
            print(f"❌ PRINT ERROR: {str(e)}")

    else:
        print("⚠️ No active printers configured")

    return sale


# =============================================================================
# GET SALE BY ID (REQUIRED FOR PRINTING)
# =============================================================================
def get_sale_by_id(sale_id: int) -> dict | None:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM sales WHERE id = ?", (sale_id,))
    row = fetchone_dict(cur)

    if not row:
        conn.close()
        return None

    sale = _sale_to_dict(row)
    sale["items"] = _fetch_items(sale_id, cur)

    conn.close()
    return sale


# =============================================================================
# FETCH ITEMS
# =============================================================================
def _fetch_items(sale_id: int, cur) -> list[dict]:
    cur.execute("SELECT * FROM sale_items WHERE sale_id = ?", (sale_id,))
    return [_item_to_dict(r) for r in fetchall_dicts(cur)]


# =============================================================================
# FORMATTERS
# =============================================================================
def _sale_to_dict(row: dict) -> dict:
    return {
        "id": row["id"],
        "invoice_no": row["invoice_no"],
        "invoice_date": row["invoice_date"],
        "total": float(row["total"]),
        "subtotal": float(row["subtotal"]),
        "total_vat": float(row["total_vat"]),
        "change_amount": float(row["change_amount"]),
        "customer_name": row["customer_name"],
        "customer_contact": row["customer_contact"],
        "cashier_name": row["cashier_name"],
        "company_name": row["company_name"],
    }


def _item_to_dict(row: dict) -> dict:
    return {
        "product_name": row["product_name"],
        "part_no": row["part_no"],
        "qty": float(row["qty"]),
        "price": float(row["price"]),
        "total": float(row["total"]),
        "tax_amount": float(row.get("tax_amount", 0)),
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

        for station in hw.get("orders", {}).values():
            if station.get("active") and station.get("printer") != "(None)":
                printers.append(station["printer"])

        return list(dict.fromkeys(printers))

    except:
        return []