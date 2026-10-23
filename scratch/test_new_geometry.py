import sys, os
sys.path.insert(0, os.path.abspath("."))
from PySide6.QtWidgets import QApplication
from PySide6.QtPrintSupport import QPrinter, QPrinterInfo
from PySide6.QtGui import QPainter, QPageSize
from PySide6.QtCore import QSizeF, QMarginsF
from database.db import get_connection
from models.sale import prepare_receipt_data

app = QApplication.instance() or QApplication(sys.argv)

def configure_and_check(printer_name, paper_size):
    printer = QPrinter(QPrinter.HighResolution)
    if printer_name and printer_name != "(None)":
        info = QPrinterInfo.printerInfo(printer_name)
        if not info.isNull():
            printer.setPrinterName(printer_name)

    is_58 = str(paper_size).strip().lower() == "58mm"
    matched_ps = None
    info = QPrinterInfo(printer)
    if not info.isNull():
        for ps in info.supportedPageSizes():
            name = ps.name().lower()
            if is_58:
                if "58" in name or "57" in name or "48" in name:
                    matched_ps = ps
                    if "3276" in name or "roll" in name:
                        break
            else:
                if "80(72" in name or "80 x" in name or "80mm" in name:
                    matched_ps = ps
                    if "3276" in name or "roll" in name:
                        break

    if matched_ps:
        printer.setPageSize(matched_ps)
        ps_name = matched_ps.name()
    else:
        roll_w = 58 if is_58 else 80
        printer.setPageSize(QPageSize(QSizeF(roll_w, 2000), QPageSize.Millimeter))
        ps_name = f"Custom {roll_w}mm"

    printer.setPageMargins(QMarginsF(0, 0, 0, 0))
    painter = QPainter(printer)
    
    dpi = printer.resolution() or 203
    dpm = dpi / 25.4
    if is_58:
        max_head = int(round(48.0 * dpm))
        paper_w = min(painter.device().width(), max_head)
        margin = 8
    else:
        max_head = int(round(72.0 * dpm))
        paper_w = min(painter.device().width(), max_head)
        margin = 12

    print(f"[{printer_name}] PageSize='{ps_name}', dev_w={painter.device().width()}, max_head={max_head} -> paper_w={paper_w}, margin={margin}")
    print(f"   Right drawing edge: {paper_w - margin}, Left drawing edge: {margin}")
    painter.end()

print("Testing 80mm on POS-80C:")
configure_and_check('POS-80C (copy 4)', '80mm')

print("\nTesting 58mm on POS-80C:")
configure_and_check('POS-80C (copy 4)', '58mm')

print("\nTesting 58mm on POS-58:")
configure_and_check('POS-58', '58mm')

print("\nTesting 80mm with no printer (default):")
configure_and_check(None, '80mm')
