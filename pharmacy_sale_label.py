"""
pharmacy_sale_label.py
Showline Solutions — Automatic Pharmacy Sale Label Printer
-----------------------------------------------------------
SETUP — run once:
    pip install pywin32

USAGE — call this from your POS after a sale is recorded:

    from pharmacy_sale_label import print_pharmacy_sale_labels

    # sale_items is the list of dicts your POS already builds,
    # exactly the same shape as your cart / order lines.
    print_pharmacy_sale_labels(sale_items)

It will silently skip any item that is NOT a pharmacy product.
Only pharmacy items get a label — no extra code needed in the caller.
"""

import sys
import datetime

# ─────────────────────────────────────────────────────────────────
# CONFIGURATION  —  edit these to match your setup
# ─────────────────────────────────────────────────────────────────

PRINTER_NAME   = "ZDesigner GK420d"      # must match  wmic printer get name
COMPANY_NAME   = "Showline Solutions"
COMPANY_FOOTER = "Showline Solutions (Pvt) Ltd  |  Harare, Zimbabwe"

# ─────────────────────────────────────────────────────────────────
# PUBLIC ENTRY POINT
# ─────────────────────────────────────────────────────────────────

def print_pharmacy_sale_labels(sale_items: list[dict]) -> None:
    """
    Accepts a list of sale-line dicts.  Each dict must contain at least:

        {
            "part_no":              str,
            "name":                 str,
            "price":                float,
            "quantity":             float,   # qty sold in this transaction
            "is_pharmacy_product":  bool,
            # optional but printed when present:
            "batch_no":             str | None,
            "expiry_date":          str | None,   # "YYYY-MM-DD" or None
            "uom":                  str | None,
        }

    One label is printed per pharmacy item.  Non-pharmacy items are skipped.
    """
    pharmacy_items = [i for i in sale_items if i.get("is_pharmacy_product")]

    if not pharmacy_items:
        return   # nothing to print — no output, no error

    for item in pharmacy_items:
        zpl = _build_sale_label(item)
        _print_raw(zpl)
        _log(f"Label printed for pharmacy item: {item.get('part_no')} — {item.get('name')}")


# ─────────────────────────────────────────────────────────────────
# ZPL BUILDER  —  one label per sold pharmacy item
# ─────────────────────────────────────────────────────────────────

def _build_sale_label(item: dict) -> bytes:
    """
    Builds a compact sale label for a single pharmacy product.

    Layout (top → bottom):
        ┌─────────────────────────────┐  ← solid header bar
        │  SHOWLINE SOLUTIONS         │
        ├─────────────────────────────┤
        │  Rx  PHARMACY               │
        │  Product name (wraps)       │
        │  Part No: XXX   UOM: ea     │
        │  Qty Sold: 2    Price: $5   │
        │  Batch: B001  Exp: 2026-12  │
        │  Date: 2025-04-22           │
        ├─────────────────────────────┤  ← barcode (part_no)
        │  |||||||||||||||||||        │
        │  SSL-001                    │
        ├─────────────────────────────┤
        │  Showline Solutions (Pvt).. │
        └─────────────────────────────┘
    """
    part_no      = str(item.get("part_no")   or "").upper().strip()
    name         = str(item.get("name")      or "Unknown Product").strip()
    price        = float(item.get("price")   or 0)
    qty          = float(item.get("quantity") or 1)
    uom          = str(item.get("uom")       or "Unit").strip()
    batch_no     = str(item.get("batch_no")  or "").strip()
    expiry_raw   = item.get("expiry_date")
    sale_date    = datetime.date.today().isoformat()

    # Format expiry nicely
    if expiry_raw:
        try:
            exp_str = str(expiry_raw)[:10]   # keep YYYY-MM-DD portion
        except Exception:
            exp_str = str(expiry_raw)
    else:
        exp_str = "N/A"

    # Truncate long names so they don't overflow the 400-dot width
    name_line1 = name[:38]
    name_line2 = name[38:76] if len(name) > 38 else ""

    # ── Y positions ──────────────────────────────────────────────
    y = 0
    HEADER_H  = 55
    y_rx      = HEADER_H + 8
    y_name1   = y_rx + 28
    y_name2   = y_name1 + 26 if name_line2 else y_name1
    y_partrow = (y_name2 if name_line2 else y_name1) + 26
    y_qtyrow  = y_partrow + 26
    y_batchrow = y_qtyrow + 26
    y_daterow = y_batchrow + 26
    y_divider1 = y_daterow + 20
    y_barcode  = y_divider1 + 8
    y_divider2 = y_barcode + 75
    y_footer   = y_divider2 + 10
    label_height = y_footer + 30

    # ── Optional second name line ─────────────────────────────────
    name2_zpl = ""
    if name_line2:
        name2_zpl = f"^FO15,{y_name2}^A0N,22,22^FD{name_line2}^FS\n"

    # ── Batch row (hide if no batch) ──────────────────────────────
    batch_zpl = ""
    if batch_no:
        batch_zpl = f"^FO15,{y_batchrow}^A0N,20,20^FDBatch: {batch_no}   Exp: {exp_str}^FS\n"
    else:
        # shift subsequent rows up by one slot
        y_daterow  -= 26
        y_divider1 -= 26
        y_barcode  -= 26
        y_divider2 -= 26
        y_footer   -= 26
        label_height -= 26

    zpl = f"""^XA
^PW400
^LL{label_height}

^FO0,0^GB400,{HEADER_H},{HEADER_H},B^FS
^FO15,10^A0N,32,32^FR^FD{COMPANY_NAME}^FS

^FO15,{y_rx}^A0N,20,20^FDRx  PHARMACY ITEM^FS
^FO15,{y_rx + 22}^GB370,2,2^FS

^FO15,{y_name1}^A0N,24,24^FD{name_line1}^FS
{name2_zpl}
^FO15,{y_partrow}^A0N,20,20^FDPart No: {part_no}   UOM: {uom}^FS
^FO15,{y_qtyrow}^A0N,20,20^FDQty Sold: {_fmt_qty(qty)}   Price: ${price:,.2f}^FS
{batch_zpl}
^FO15,{y_daterow}^A0N,20,20^FDDate: {sale_date}^FS

^FO15,{y_divider1}^GB370,2,2^FS

^FO15,{y_barcode}^BCN,55,N,N,N^FD{part_no}^FS

^FO15,{y_divider2}^GB370,2,2^FS
^FO15,{y_footer}^A0N,18,18^FD{COMPANY_FOOTER}^FS

^XZ"""

    return zpl.encode("utf-8")


def _fmt_qty(qty: float) -> str:
    """Show 2 as '2', 1.5 as '1.5' — no unnecessary decimals."""
    return str(int(qty)) if qty == int(qty) else f"{qty:.2f}"


# ─────────────────────────────────────────────────────────────────
# RAW PRINT  (identical pattern to your original zpl.py)
# ─────────────────────────────────────────────────────────────────

def _print_raw(zpl_bytes: bytes) -> None:
    try:
        import win32print
    except ImportError:
        _log("ERROR: win32print not found.  Run:  pip install pywin32", error=True)
        raise

    hPrinter = win32print.OpenPrinter(PRINTER_NAME)
    try:
        hJob = win32print.StartDocPrinter(hPrinter, 1, ("Pharmacy Sale Label", None, "RAW"))
        try:
            win32print.StartPagePrinter(hPrinter)
            win32print.WritePrinter(hPrinter, zpl_bytes)
            win32print.EndPagePrinter(hPrinter)
        finally:
            win32print.EndDocPrinter(hPrinter)
    finally:
        win32print.ClosePrinter(hPrinter)


# ─────────────────────────────────────────────────────────────────
# LOGGING  (simple — swap for your app's logger if preferred)
# ─────────────────────────────────────────────────────────────────

def _log(msg: str, error: bool = False) -> None:
    prefix = "[pharmacy_label] ERROR:" if error else "[pharmacy_label]"
    print(f"{prefix} {msg}", file=sys.stderr if error else sys.stdout)


# ─────────────────────────────────────────────────────────────────
# QUICK MANUAL TEST  —  python pharmacy_sale_label.py
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_sale = [
        {
            "part_no":             "AMOX-500",
            "name":                "Amoxicillin 500mg Capsules",
            "price":               4.50,
            "quantity":            2,
            "uom":                 "Strip",
            "is_pharmacy_product": True,
            "batch_no":            "B20240901",
            "expiry_date":         "2026-09-30",
        },
        {
            # Non-pharmacy item — should be silently skipped
            "part_no":             "SOAP-001",
            "name":                "Hand Soap 500ml",
            "price":               2.00,
            "quantity":            1,
            "uom":                 "Each",
            "is_pharmacy_product": False,
            "batch_no":            None,
            "expiry_date":         None,
        },
        {
            "part_no":             "PARA-1000",
            "name":                "Paracetamol 1000mg",
            "price":               1.80,
            "quantity":            3,
            "uom":                 "Tab",
            "is_pharmacy_product": True,
            "batch_no":            "",          # no batch — row hidden automatically
            "expiry_date":         None,
        },
    ]

    print("Running test sale (2 pharmacy items, 1 skipped)...")
    print_pharmacy_sale_labels(test_sale)
    print("Done.")