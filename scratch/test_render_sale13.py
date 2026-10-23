import sys
import os
sys.path.insert(0, os.path.abspath("."))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QFontMetrics, QImage, QPainter, QColor, QPageSize
from PySide6.QtCore import Qt, QRect, QSizeF, QMarginsF
from database.db import get_connection
from models.sale import prepare_receipt_data
from services.printing_service import PrintingService, AdvanceSettings

app = QApplication.instance() or QApplication(sys.argv)

conn = get_connection()
c = conn.cursor()
c.execute("SELECT TOP 1 * FROM sales ORDER BY id DESC")
cols = [col[0] for col in c.description]
row = c.fetchone()
sale_dict = dict(zip(cols, row))

c.execute("SELECT * FROM sale_items WHERE sale_id = ?", sale_dict['id'])
item_cols = [col[0] for col in c.description]
sale_dict['items'] = [dict(zip(item_cols, r)) for r in c.fetchall()]

receipt = prepare_receipt_data(sale_dict)

ps = PrintingService()

# Render to QImage simulating POS-80C
img = QImage(640, 1200, QImage.Format_ARGB32)
img.fill(QColor("white"))

painter = QPainter(img)
# Simulate _update_page_geometry
ps._update_page_geometry(painter)

# Let's see what self.paper_width and margin became:
print("paper_width:", ps.paper_width, "margin:", ps.margin)

# Now let's execute the exact drawing logic of _do_print_invoice_receipt
# We can extract or run the exact draw commands onto this painter
settings = AdvanceSettings.load_from_file()

y = 10
normal_font = ps._create_font(settings.contentFontName, settings.contentFontSize, settings.contentFontStyle)
bold_font   = ps._make_bold(normal_font)

y = ps._draw_logo(painter, receipt, settings, y)

painter.setFont(bold_font)
painter.drawText(ps.margin, y, ps.paper_width - ps.margin * 2, 40, Qt.AlignCenter, (receipt.companyName or "Havano POS").upper())
y += 60

painter.setFont(normal_font)
for line in [receipt.companyAddress, receipt.companyAddressLine1, receipt.companyAddressLine2]:
    if line:
        painter.drawText(ps.margin, y, ps.paper_width - ps.margin*2, 22, Qt.AlignCenter, line)
        y += 30

city_state = f"{receipt.city} {receipt.state} {receipt.postcode}".strip()
if city_state:
    painter.drawText(ps.margin, y, ps.paper_width - ps.margin*2, 22, Qt.AlignCenter, city_state)
    y += 30
if receipt.tel:
    painter.drawText(ps.margin, y, ps.paper_width - ps.margin*2, 22, Qt.AlignCenter, f"Tel: {receipt.tel}")
    y += 30

y += 10
painter.drawLine(ps.margin, y, ps.paper_width - ps.margin, y)
y += 25

painter.setFont(bold_font)
painter.drawText(ps.margin, y, ps.paper_width - ps.margin * 2, 44, Qt.AlignCenter, "*** SALES RECEIPT ***")
y += 44

painter.drawLine(ps.margin, y, ps.paper_width - ps.margin, y)
y += 24

# Doc details
_inv_row_h = 24
ps._draw_doc_row(painter, "Invoice #:", receipt.invoiceNo or "N/A", y, _inv_row_h, bold_font, normal_font)
y += _inv_row_h + 4

y += 10
painter.drawLine(ps.margin, y, ps.paper_width - ps.margin, y)
y += 24

# Items Table
painter.setFont(normal_font)
fm = painter.fontMetrics()
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

painter.setFont(bold_font)
painter.drawText(ps.margin, y, QTY_X - ps.margin, 24, Qt.AlignLeft, "Item")
painter.drawText(QTY_X,   y, max_qty_w,   24, Qt.AlignCenter, "Qty")
painter.drawText(PRICE_X, y, max_price_w, 24, Qt.AlignRight,  "Price")
painter.drawText(TOTAL_X, y, max_total_w, 24, Qt.AlignRight,  "Total")
y += 44
painter.drawLine(ps.margin, y, ps.paper_width - ps.margin, y)
y += 24


painter.setFont(normal_font)
line_h = fm.height() + 6
for item in receipt.items:
    name_w = QTY_X - ps.margin - 8
    rect = fm.boundingRect(ps.margin, y, name_w, 1000, Qt.TextWordWrap, item.productName or "")
    painter.drawText(ps.margin, y, name_w, rect.height(), Qt.TextWordWrap, item.productName or "")
    item_bot = y + rect.height()
    painter.drawText(QTY_X,   y, max_qty_w,   line_h, Qt.AlignCenter, f"{float(item.qty):g}")
    painter.drawText(PRICE_X, y, max_price_w, line_h, Qt.AlignRight,  f"{item.price:,.2f}")
    painter.drawText(TOTAL_X, y, max_total_w, line_h, Qt.AlignRight,  f"{item.amount:,.2f}")
    y = max(item_bot, y + line_h) + 8
    ps._draw_dot_line(painter, ps.margin, y, ps.paper_width - ps.margin * 2, ".")
    y += 14

painter.drawLine(ps.margin, y, ps.paper_width - ps.margin, y)
y += 14

# Totals
painter.setFont(normal_font)
fm = painter.fontMetrics()
line_h = fm.height() + 6

def draw_total(label: str, value: float, currency: str = None):
    global y
    _cur = (currency or receipt.currency or "USD")
    text = f"{_cur} {value:,.2f}"
    fm_tot = painter.fontMetrics()
    w = fm_tot.horizontalAdvance(text)
    row_h = fm_tot.height() + 6
    gap = 10
    avail = max(0, ps.paper_width - ps.margin * 2 - w - gap)
    print(f"DRAW TOTAL: y={y} label='{label}' text='{text}' avail={avail} w={w} x_text={ps.paper_width - ps.margin - w}")
    painter.drawText(ps.margin, y, avail, row_h, Qt.AlignLeft, label)
    painter.drawText(ps.paper_width - ps.margin - w, y, w, row_h, Qt.AlignRight, text)
    y += row_h

painter.setFont(bold_font)
draw_total("GRAND TOTAL", float(receipt.grandTotal or 0), "USD")
painter.setFont(normal_font)

y += 10

_tendered_base = float(getattr(receipt, "amountTendered", 0) or 0)
_change_base   = float(getattr(receipt, "change",         0) or 0)
tender_cur = "USD"
if _tendered_base > 0.005:
    draw_total("Amount Tendered", _tendered_base, tender_cur)
    draw_total("Change",          _change_base,   tender_cur)

payment_items = getattr(receipt, "paymentItems", None) or []
if payment_items:
    y += 10
    painter.drawLine(ps.margin, y, ps.paper_width - ps.margin, y)
    y += 14

    painter.setFont(bold_font)
    painter.drawText(ps.margin, y, ps.paper_width - ps.margin * 2, line_h, Qt.AlignLeft, "PAYMENT DETAILS")
    y += line_h + 4

    painter.setFont(normal_font)
    for _pi in payment_items:
        method_name = (getattr(_pi, "productName", "") or "").strip() or "PAYMENT"
        native_cur  = (getattr(_pi, "productid",   "") or "USD").strip().upper()
        native_amt  = float(getattr(_pi, "price",  0) or 0)
        right_text = f"{native_cur} {native_amt:,.2f}"
        fm_pi = painter.fontMetrics()
        w = fm_pi.horizontalAdvance(right_text)
        gap = 10
        avail = max(0, ps.paper_width - ps.margin * 2 - w - gap)
        print(f"PAYMENT ITEM: y={y} method='{method_name}' right_text='{right_text}' avail={avail} w={w}")
        painter.drawText(ps.margin, y, avail, line_h, Qt.AlignLeft, method_name)
        painter.drawText(ps.paper_width - ps.margin - w, y, w, line_h, Qt.AlignRight, right_text)
        y += line_h

y += 20
painter.end()

out_path = os.path.abspath("scratch/test_receipt.png")
cropped = img.copy(0, 0, ps.paper_width, y)
cropped.save(out_path)
print("Saved to:", out_path)
