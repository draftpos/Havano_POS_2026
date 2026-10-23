import sys
import os
sys.path.insert(0, os.path.abspath("."))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QFontMetrics, QImage, QPainter, QColor
from PySide6.QtCore import Qt, QRect
from database.db import get_connection
from models.sale import prepare_receipt_data

app = QApplication.instance() or QApplication(sys.argv)

conn = get_connection()
c = conn.cursor()
c.execute("SELECT TOP 1 * FROM sales ORDER BY id DESC")
cols = [col[0] for col in c.description]
row = c.fetchone()
sale_dict = dict(zip(cols, row))

# Fetch sale items
c.execute("SELECT * FROM sale_items WHERE sale_id = ?", sale_dict['id'])
item_cols = [col[0] for col in c.description]
sale_dict['items'] = [dict(zip(item_cols, r)) for r in c.fetchall()]

receipt = prepare_receipt_data(sale_dict)

print("Invoice:", receipt.invoiceNo)
print("Grand Total:", receipt.grandTotal)
print("Amount Tendered:", getattr(receipt, "amountTendered", None))
print("Change:", getattr(receipt, "change", None))
print("Payment items:", [(pi.productName, pi.productid, pi.price, pi.amount) for pi in (getattr(receipt, "paymentItems", None) or [])])

# Test with paper_width = 639 (what _update_page_geometry set for POS-80C)
# and paper_width = 550, and 576
for pw in [639, 576, 550]:
    margin = 16 if pw >= 500 else 10
    font = QFont("Arial", 10)
    bold_font = QFont("Arial", 10)
    bold_font.setBold(True)
    fm = QFontMetrics(font)
    fm_bold = QFontMetrics(bold_font)
    
    print(f"\n--- Testing paper_width={pw}, margin={margin} ---")
    y = 100
    
    def test_draw_total(label: str, value: float, currency: str = "USD", is_bold=False):
        global y
        curr_fm = fm_bold if is_bold else fm
        text = f"{currency} {value:,.2f}"
        w = curr_fm.horizontalAdvance(text)
        row_h = curr_fm.height() + 6
        gap = 10
        avail = max(0, pw - margin * 2 - w - gap)
        label_w = curr_fm.horizontalAdvance(label)
        val_x = pw - margin - w
        print(f"[{'BOLD ' if is_bold else 'NORM '}] '{label}' (w={label_w}) at x={margin}, avail={avail} | '{text}' (w={w}) at x={val_x}..{val_x+w} | y={y}..{y+row_h}")
        if margin + label_w > val_x:
            print(f"   >>> OVERLAP DETECTED! Label right edge {margin+label_w} > Value left edge {val_x}!")
        y += row_h

    test_draw_total("GRAND TOTAL", float(receipt.grandTotal), "USD", is_bold=True)
    y += 10
    test_draw_total("Amount Tendered", float(getattr(receipt, "amountTendered", 0)), "USD")
    test_draw_total("Change", float(getattr(receipt, "change", 0)), "USD")
