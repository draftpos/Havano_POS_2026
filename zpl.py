"""
print_pharmacy_label.py
Showline Solutions - Pharmacy Product Label Printer
-----------------------------------------------------
SETUP — run once:
    pip install pywin32

RUN:
    python print_pharmacy_label.py

WHY THIS WORKS:
    Uses win32print to open a direct raw print job on Windows.
    This bypasses the spooler and sends ZPL bytes straight to
    the printer — exactly like a network socket but over USB.
"""

import sys

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

PRINTER_NAME = "ZDesigner GK420d"   # Must match wmic printer get name exactly

# ─────────────────────────────────────────────
# LABEL DATA — edit freely
# ─────────────────────────────────────────────

COMPANY_NAME   = "Showline Solutions"
COMPANY_FOOTER = "Showline Solutions (Pvt) Ltd  |  Harare, Zimbabwe"
LABEL_TITLE    = "Pharmacy Products"
BARCODE_REF    = "SSL-PHARM-001"

PRODUCTS = [
    "Amoxicillin 500mg",
    "Paracetamol 1000mg",
    "Ibuprofen 400mg",
    "Metformin 850mg",
    "Omeprazole 20mg",
]

# ─────────────────────────────────────────────
# BUILD ZPL
# ─────────────────────────────────────────────

def build_zpl():
    product_start_y = 110
    line_gap        = 30

    product_lines = ""
    for i, product in enumerate(PRODUCTS):
        y      = product_start_y + (i * line_gap)
        number = str(i + 1).zfill(2)
        product_lines += f"^FO15,{y}^A0N,22,22^FD{number}  {product}^FS\n"

    after_products_y = product_start_y + (len(PRODUCTS) * line_gap) + 10
    barcode_y        = after_products_y + 12
    footer_divider_y = barcode_y + 88
    footer_y         = footer_divider_y + 10
    label_height     = footer_y + 30

    zpl = f"""^XA
^PW400
^LL{label_height}

^FO0,0^GB400,60,60,B^FS
^FO15,12^A0N,35,35^FR^FD{COMPANY_NAME}^FS

^FO15,72^A0N,20,20^FD{LABEL_TITLE}^FS
^FO15,96^GB370,2,2^FS

{product_lines}
^FO15,{after_products_y}^GB370,2,2^FS

^FO15,{barcode_y}^BCN,60,N,N,N^FD{BARCODE_REF}^FS

^FO15,{footer_divider_y}^GB370,2,2^FS

^FO15,{footer_y}^A0N,18,18^FD{COMPANY_FOOTER}^FS

^XZ"""

    return zpl.encode("utf-8")


# ─────────────────────────────────────────────
# RAW PRINT VIA win32print
# ─────────────────────────────────────────────

def print_raw(zpl_bytes):
    """
    Opens a raw print job directly on the Windows printer.
    RAW data type tells the spooler to pass bytes straight
    through to the printer without any processing.
    This is the correct way to send ZPL over USB on Windows.
    """
    try:
        import win32print
    except ImportError:
        print("  ERROR: win32print not found.")
        print("  Run:  pip install pywin32")
        sys.exit(1)

    print(f"  Opening printer: {PRINTER_NAME}")

    # Open a handle to the printer
    hPrinter = win32print.OpenPrinter(PRINTER_NAME)

    try:
        # Start a raw print job
        # "RAW" tells Windows to pass bytes through unmodified
        hJob = win32print.StartDocPrinter(hPrinter, 1, ("ZPL Label", None, "RAW"))

        try:
            win32print.StartPagePrinter(hPrinter)

            # Write the raw ZPL bytes directly
            win32print.WritePrinter(hPrinter, zpl_bytes)

            win32print.EndPagePrinter(hPrinter)
            print("  ZPL bytes written successfully.")

        finally:
            win32print.EndDocPrinter(hPrinter)

    finally:
        win32print.ClosePrinter(hPrinter)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    print("=" * 50)
    print("  Showline Solutions — Pharmacy Label Printer")
    print("=" * 50)

    print("\n  Building label...")
    zpl = build_zpl()
    print(f"  Label built — {len(zpl)} bytes")

    print("\n  Sending to printer...")
    print_raw(zpl)

    print("\n  Done. Label should be printing now.")
    print("=" * 50)


if __name__ == "__main__":
    main()


# ─────────────────────────────────────────────
# HOW TO CALL THIS FROM YOUR POS SYSTEM
# ─────────────────────────────────────────────
#
# Import the functions into your existing code like this:
#
#   from print_pharmacy_label import build_zpl, print_raw
#
#   zpl = build_zpl()
#   print_raw(zpl)
#
# Or pass dynamic data by modifying build_zpl() to accept
# parameters instead of reading the globals at the top.
#
# Example for dynamic labels in your POS:
#
#   def print_label(products, barcode):
#       zpl = build_zpl(products=products, barcode=barcode)
#       print_raw(zpl)
#
# ─────────────────────────────────────────────