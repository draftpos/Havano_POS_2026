import sys, os
sys.path.insert(0, os.path.abspath("."))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QFontMetrics, QImage, QPainter, QColor, QPageSize
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtCore import Qt, QRect, QSizeF, QMarginsF
from database.db import get_connection
from models.sale import prepare_receipt_data
from services.printing_service import PrintingService, AdvanceSettings

app = QApplication.instance() or QApplication(sys.argv)

conn = get_connection()
c = conn.cursor()
c.execute("SELECT * FROM sales WHERE id = 12")
cols = [col[0] for col in c.description]
row = c.fetchone()
sale_dict = dict(zip(cols, row))

c.execute("SELECT * FROM sale_items WHERE sale_id = 12")
item_cols = [col[0] for col in c.description]
sale_dict['items'] = [dict(zip(item_cols, r)) for r in c.fetchall()]

receipt = prepare_receipt_data(sale_dict)

print("Sale 12:", receipt.invoiceNo)
print("Items:", [(it.productName, it.qty, it.price, it.amount) for it in receipt.items])
print("Grand Total:", receipt.grandTotal)
print("Amount Tendered:", receipt.amountTendered)
print("Change:", receipt.change)
print("Payments:", [(pi.productName, pi.productid, pi.price, pi.amount) for pi in (receipt.paymentItems or [])])

# Let's inspect with QPrinter for 'POS-80C (copy 4)'
printer = QPrinter(QPrinter.HighResolution)
printer.setPrinterName('POS-80C (copy 4)')
printer.setPageSize(QPageSize(QSizeF(80, 200), QPageSize.Millimeter))
printer.setPageMargins(QMarginsF(0, 0, 0, 0))

painter = QPainter(printer)
ps = PrintingService()
ps._update_page_geometry(painter)
print(f"Device width from QPainter on POS-80C: {painter.device().width()}")
print(f"ps.paper_width: {ps.paper_width}, ps.margin: {ps.margin}")

# Now let's calculate the exact layout
settings = AdvanceSettings.load_from_file()
normal_font = ps._create_font(settings.contentFontName, settings.contentFontSize, settings.contentFontStyle)
bold_font   = ps._make_bold(normal_font)

painter.setFont(normal_font)
fm = painter.fontMetrics()
painter.setFont(bold_font)
fm_bold = painter.fontMetrics()

# Check Items table width
max_qty_w   = fm.horizontalAdvance("Qty")
max_price_w = fm.horizontalAdvance("Price")
max_total_w = fm.horizontalAdvance("Total")
for item in receipt.items:
    max_qty_w   = max(max_qty_w,   fm.horizontalAdvance(f"{float(item.qty):g}"))
    max_price_w = max(max_price_w, fm.horizontalAdvance(f"{item.price:,.2f}"))
    max_total_w = max(max_total_w, fm.horizontalAdvance(f"{item.amount:,.2f}"))

max_qty_w += 10
max_price_w += 14
max_total_w += 14

TOTAL_X = ps.paper_width - ps.margin - max_total_w
PRICE_X = TOTAL_X - max_price_w - 10
QTY_X   = PRICE_X - max_qty_w - 10

print(f"Columns: margin={ps.margin}, QTY_X={QTY_X}, PRICE_X={PRICE_X}, TOTAL_X={TOTAL_X}, RIGHT_EDGE={ps.paper_width - ps.margin}")

# Check Totals
print("\n--- TOTALS SECTION ---")
def check_total(label, val_str, font, is_bold=False):
    painter.setFont(font)
    f_m = painter.fontMetrics()
    w = f_m.horizontalAdvance(val_str)
    row_h = f_m.height() + 6
    gap = 10
    avail = max(0, ps.paper_width - ps.margin * 2 - w - gap)
    lbl_w = f_m.horizontalAdvance(label)
    val_x = ps.paper_width - ps.margin - w
    print(f"Label '{label}' (w={lbl_w}) drawn in [x={ps.margin}..{ps.margin+avail}], Value '{val_str}' (w={w}) drawn in [x={val_x}..{val_x+w}]")
    if ps.margin + lbl_w > val_x:
        print(f"  >>> OVERLAP HORIZONTALLY! lbl ends at {ps.margin+lbl_w}, val starts at {val_x}")

check_total("GRAND TOTAL", f"USD {receipt.grandTotal:,.2f}", bold_font, True)
check_total("Amount Tendered", f"USD {receipt.amountTendered:,.2f}", normal_font)
check_total("Change", f"USD {receipt.change:,.2f}", normal_font)
for pi in (receipt.paymentItems or []):
    check_total(pi.productName, f"{pi.productid} {pi.price:,.2f}", normal_font)

painter.end()
