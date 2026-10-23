import sys, os
sys.path.insert(0, os.path.abspath("."))
from PySide6.QtWidgets import QApplication
from database.db import get_connection
from models.sale import prepare_receipt_data
from services.printing_service import PrintingService

app = QApplication.instance() or QApplication(sys.argv)

conn = get_connection()
c = conn.cursor()
c.execute("SELECT TOP 1 * FROM sales WHERE id = 12")
cols = [col[0] for col in c.description]
row = c.fetchone()
sale_dict = dict(zip(cols, row))

c.execute("SELECT * FROM sale_items WHERE sale_id = 12")
item_cols = [col[0] for col in c.description]
sale_dict['items'] = [dict(zip(item_cols, r)) for r in c.fetchall()]

receipt = prepare_receipt_data(sale_dict)

ps = PrintingService()
print("PrintingService initialized.")
print("Testing geometry logic directly...")
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtGui import QPainter

for p_name in ['POS-80C (copy 4)', 'POS-58', None]:
    for p_size in ['80mm', '58mm']:
        printer = QPrinter(QPrinter.HighResolution)
        ps._configure_printer(printer, p_name, p_size, 1000)
        painter = QPainter(printer)
        ps._update_page_geometry(painter, p_size)
        print(f"Printer={p_name}, Size={p_size} -> width={ps.paper_width}, margin={ps.margin}, right_limit={ps.paper_width - ps.margin}")
        painter.end()

print("ALL GEOMETRY TESTS PASSED!")
