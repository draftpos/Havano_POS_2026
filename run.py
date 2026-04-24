"""
pharmacy_label_printer.py
Showline Solutions — Auto Pharmacy Label Printer
-------------------------------------------------
Drop this file into your project root (same level as models/).

HOW IT WORKS:
    Call  print_pharmacy_label_for_sale(sale_items)  right after a sale
    is confirmed.  It will:
        1. Filter only items whose product has is_pharmacy_product = True
        2. Pull the product's current batches from the DB
        3. Build a ZPL label per pharmacy item (one label per line item)
        4. Send each label straight to the Zebra printer via win32print

SETUP — run once:
    pip install pywin32

INTEGRATION (in your POS sale-confirm handler):
    from pharmacy_label_printer import print_pharmacy_label_for_sale

    def confirm_sale(sale_items):
        # ... your existing sale logic ...
        save_sale(sale_items)
        print_pharmacy_label_for_sale(sale_items)   # ← add this one line
"""

import sys
from datetime import date
from models.product import get_product_by_id, get_batches_for_product

# ─────────────────────────────────────────────
# CONFIGURATION — edit to match your setup
# ─────────────────────────────────────────────

PRINTER_NAME   = "ZDesigner GK420d"   # Must match  wmic printer get name  exactly
COMPANY_NAME   = "Showline Solutions"
COMPANY_FOOTER = "Showline Solutions (Pvt) Ltd  |  Harare, Zimbabwe"

# ─────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────

def print_pharmacy_label_for_sale(sale_items: list[dict]) -> None:
    """
    Main entry point. Call this after every sale is saved.

    sale_items — list of dicts, each with at minimum:
        {
            "product_id":  int,          # required
            "quantity":    float | int,  # required
            "price":       float,        # optional — shown on label if present
            "batch_no":    str | None,   # optional — override auto-looked-up batch
        }

    Labels are printed only for products flagged is_pharmacy_product = True.
    If a product has no batches in the DB the label still prints — batch
    fields are simply left blank.
    """
    printed = 0
    for item in sale_items:
        product_id = item.get("product_id")
        if not product_id:
            continue

        product = get_product_by_id(product_id)
        if not product:
            continue

        if not product.get("is_pharmacy_product"):
            continue                       # skip non-pharmacy items silently

        # ── resolve batch info ───────────────────────────────────────────────
        batch_no    = item.get("batch_no") or ""
        expiry_date = ""

        if not batch_no:
            # look up the earliest-expiring batch that still has stock
            batches = get_batches_for_product(product_id)
            if batches:
                first = batches[0]         # already sorted by expiry_date, batch_no
                batch_no    = first.get("batch_no", "")
                expiry_date = first.get("expiry_date", "") or ""

        # ── build and send label ─────────────────────────────────────────────
        qty   = item.get("quantity", 1)
        price = item.get("price", product.get("price", 0.0))

        zpl = _build_item_zpl(
            product_name    = product.get("name", "Unknown Product"),
            part_no         = product.get("part_no", ""),
            qty             = qty,
            uom             = product.get("uom", "Unit"),
            price           = price,
            batch_no        = batch_no,
            expiry_date     = str(expiry_date)[:10] if expiry_date else "",
        )

        print(f"  [Pharmacy Print] {product.get('name')}  qty={qty}  batch={batch_no or '—'}")
        _print_raw(zpl)
        printed += 1

    if printed:
        print(f"  ✓ {printed} pharmacy label(s) sent to {PRINTER_NAME}")
    else:
        print("  [Pharmacy Print] No pharmacy items in this sale — nothing printed.")


# ─────────────────────────────────────────────
# ZPL BUILDER — one label per line item
# ─────────────────────────────────────────────

def _build_item_zpl(
    product_name: str,
    part_no:      str,
    qty:          float,
    uom:          str,
    price:        float,
    batch_no:     str,
    expiry_date:  str,
) -> bytes:
    """
    Builds a single pharmacy item ZPL label.

    Layout (400 dots wide, ~3" label):
    ┌─────────────────────────────────────────┐
    │ ░░░ SHOWLINE SOLUTIONS ░░░ (solid bar)  │
    │ PHARMACY PRODUCT                        │
    │ ─────────────────────────────────────── │
    │ Product Name (wraps if long)            │
    │ Part No: SSL-XXX-001                    │
    │ ─────────────────────────────────────── │
    │ Qty: 2 Units          Price: $12.50     │
    │ Batch: BCH-001        Expiry: 2026-06   │
    │ ─────────────────────────────────────── │
    │ ▐▌▐▌▌▐▌▌▐   (barcode — part_no)        │
    │ ─────────────────────────────────────── │
    │ Showline Solutions (Pvt) Ltd | Harare   │
    └─────────────────────────────────────────┘
    """
    today        = date.today().isoformat()
    price_str    = f"${price:,.2f}"
    qty_str      = f"{qty:g} {uom}"
    barcode_data = part_no if part_no else "PHARM"

    # truncate very long names so they fit on 400-dot label
    name_display = product_name[:38]

    zpl = f"""^XA
^PW400
^LL340

^FO0,0^GB400,58,58,B^FS
^FO12,10^A0N,34,34^FR^FD{COMPANY_NAME}^FS

^FO12,68^A0N,18,18^FDPHARMACY PRODUCT^FS
^FO12,90^GB374,2,2^FS

^FO12,98^A0N,24,24^FD{name_display}^FS
^FO12,126^A0N,18,18^FDPart No: {part_no}^FS
^FO12,148^GB374,2,2^FS

^FO12,156^A0N,20,20^FDQty: {qty_str}^FS
^FO210,156^A0N,20,20^FDPrice: {price_str}^FS

^FO12,180^A0N,18,18^FDBatch: {batch_no if batch_no else "N/A"}^FS
^FO210,180^A0N,18,18^FDExpiry: {expiry_date if expiry_date else "N/A"}^FS

^FO12,202^A0N,16,16^FDDate: {today}^FS
^FO12,222^GB374,2,2^FS

^FO12,230^BCN,55,N,N,N^FD{barcode_data}^FS

^FO12,296^GB374,2,2^FS
^FO12,302^A0N,16,16^FD{COMPANY_FOOTER}^FS

^XZ"""

    return zpl.encode("utf-8")


# ─────────────────────────────────────────────
# RAW PRINT — sends ZPL bytes straight to Zebra
# ─────────────────────────────────────────────

def _print_raw(zpl_bytes: bytes) -> None:
    """
    Sends raw ZPL bytes to the Zebra printer via win32print.
    RAW data type bypasses Windows GDI — the printer gets ZPL directly.
    """
    try:
        import win32print
    except ImportError:
        print("  ERROR: win32print not found.  Run:  pip install pywin32")
        sys.exit(1)

    hPrinter = win32print.OpenPrinter(PRINTER_NAME)
    try:
        hJob = win32print.StartDocPrinter(hPrinter, 1, ("Pharmacy ZPL Label", None, "RAW"))
        try:
            win32print.StartPagePrinter(hPrinter)
            win32print.WritePrinter(hPrinter, zpl_bytes)
            win32print.EndPagePrinter(hPrinter)
        finally:
            win32print.EndDocPrinter(hPrinter)
    finally:
        win32print.ClosePrinter(hPrinter)


# ─────────────────────────────────────────────
# STANDALONE TEST — run directly to verify
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 54)
    print("  Showline Solutions — Pharmacy Label Test Print")
    print("=" * 54)

    # Simulated sale items — replace product_id with real IDs from your DB
    test_sale = [
        {
            "product_id": 1,          # <- change to a real pharmacy product id
            "quantity":   2,
            "price":      12.50,
            "batch_no":   "",         # leave blank to auto-lookup from DB
        },
        {
            "product_id": 2,          # <- change to another pharmacy product id
            "quantity":   1,
            "price":      8.00,
            "batch_no":   "BCH-TEST-001",
        },
    ]

    print_pharmacy_label_for_sale(test_sale)
    print("=" * 54)