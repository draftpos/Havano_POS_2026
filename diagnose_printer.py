"""
diagnose_printer.py
Showline Solutions — Zebra Printer Diagnostics
-----------------------------------------------
Run this first to find out exactly what's wrong.

    py diagnose_printer.py
"""

import sys

# ─────────────────────────────────────────────
# STEP 1 — list all printers Windows can see
# ─────────────────────────────────────────────

def list_printers():
    try:
        import win32print
    except ImportError:
        print("  ERROR: pywin32 not installed.  Run: pip install pywin32")
        sys.exit(1)

    print("\n[ STEP 1 ] Printers visible to Windows:")
    print("-" * 50)
    printers = win32print.EnumPrinters(
        win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    )
    if not printers:
        print("  !! No printers found at all !!")
        return

    for i, p in enumerate(printers):
        # p = (flags, description, name, comment)
        print(f"  [{i}] Name      : {p[2]}")
        print(f"       Description: {p[1]}")
        print()

    print("  --> Copy the exact 'Name' above and paste it as PRINTER_NAME in pharmacy_sale_label.py")


# ─────────────────────────────────────────────
# STEP 2 — send the absolute minimal ZPL
#           to the printer name you supply
# ─────────────────────────────────────────────

def test_minimal_zpl(printer_name: str):
    try:
        import win32print
    except ImportError:
        print("  ERROR: pywin32 not installed.")
        sys.exit(1)

    # The simplest possible ZPL — just prints "HELLO TEST" on a label
    minimal_zpl = b"^XA^PW400^LL100^FO20,30^A0N,40,40^FDHELLO TEST^FS^XZ"

    print(f"\n[ STEP 2 ] Sending minimal ZPL to: {printer_name!r}")
    print("-" * 50)

    try:
        h = win32print.OpenPrinter(printer_name)
    except Exception as e:
        print(f"  !! OpenPrinter FAILED: {e}")
        print("     Check that the name matches exactly (case-sensitive).")
        return

    try:
        job = win32print.StartDocPrinter(h, 1, ("DIAG TEST", None, "RAW"))
        try:
            win32print.StartPagePrinter(h)
            written = win32print.WritePrinter(h, minimal_zpl)
            win32print.EndPagePrinter(h)
            print(f"  WritePrinter returned: {written} bytes written")
            print("  --> If the printer still did nothing, the issue is likely:")
            print("      a) The label size in the printer driver doesn't match")
            print("      b) The printer is paused — press the button on the printer")
            print("      c) The label is out of the sensor range — recalibrate:")
            print("         Hold the feed button for 2 seconds until it flashes.")
        finally:
            win32print.EndDocPrinter(h)
    except Exception as e:
        print(f"  !! Print job FAILED: {e}")
    finally:
        win32print.ClosePrinter(h)


# ─────────────────────────────────────────────
# STEP 3 — save ZPL to a .zpl file so you can
#           inspect it or send via other tools
# ─────────────────────────────────────────────

def save_zpl_to_file():
    from pharmacy_sale_label import _build_sale_label

    test_item = {
        "part_no":             "AMOX-500",
        "name":                "Amoxicillin 500mg Capsules",
        "price":               4.50,
        "quantity":            2,
        "uom":                 "Strip",
        "is_pharmacy_product": True,
        "batch_no":            "B20240901",
        "expiry_date":         "2026-09-30",
    }

    zpl_bytes = _build_sale_label(test_item)
    path = "test_label.zpl"
    with open(path, "wb") as f:
        f.write(zpl_bytes)

    print(f"\n[ STEP 3 ] ZPL saved to: {path}")
    print("  --> Open it in Notepad to inspect, or upload to")
    print("      https://labelary.com/viewer.html  to preview the label visually.")
    print()
    print("  ZPL content preview:")
    print("-" * 50)
    print(zpl_bytes.decode("utf-8"))


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    list_printers()

    # Ask user which printer name to test with
    print("\nEnter the printer name to test (or press Enter to skip print test):")
    name = input("  Printer name: ").strip()

    if name:
        test_minimal_zpl(name)
    else:
        print("  Skipping print test.")

    print()
    save_zpl_file = input("Save ZPL to file for visual preview? (y/n): ").strip().lower()
    if save_zpl_file == "y":
        try:
            save_zpl_to_file()
        except ImportError:
            print("  Make sure pharmacy_sale_label.py is in the same folder.")