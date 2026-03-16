# utils/pdf_receipt.py
import os
from datetime import datetime
from reportlab.lib.pagesizes import A6
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

def generate_receipt(sale_id, cart_items, total, save_dir=None):
    """
    Generates a PDF receipt and saves it to the desktop by default.
    Returns the full path of the saved file.
    """
    if save_dir is None:
        save_dir = os.path.join(os.path.expanduser("~"), "Desktop")

    filename = f"receipt_{sale_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = os.path.join(save_dir, filename)

    # A6 is receipt size — like a thermal printer page
    c = canvas.Canvas(filepath, pagesize=A6)
    width, height = A6

    y = height - 20 * mm   # start from top, work downward

    def line(text, font="Helvetica", size=10, gap=7):
        """Helper — draw one line then move down"""
        nonlocal y
        c.setFont(font, size)
        c.drawCentredString(width / 2, y, text)
        y -= gap * mm

    def divider():
        nonlocal y
        c.setLineWidth(0.5)
        c.line(10 * mm, y, width - 10 * mm, y)
        y -= 6 * mm

    # Header
    line("MY POS SYSTEM",        font="Helvetica-Bold", size=14, gap=8)
    line(datetime.now().strftime("%Y-%m-%d   %H:%M"),   size=9,  gap=6)
    line(f"Receipt #  {sale_id}",                       size=9,  gap=8)
    divider()

    # Items — left aligned
    for name, price in cart_items:
        c.setFont("Helvetica", 10)
        c.drawString(12 * mm, y, name)
        c.drawRightString(width - 12 * mm, y, f"${price:.2f}")
        y -= 7 * mm

    divider()

    # Total
    c.setFont("Helvetica-Bold", 12)
    c.drawString(12 * mm, y, "TOTAL")
    c.drawRightString(width - 12 * mm, y, f"${total:.2f}")
    y -= 10 * mm

    # Footer
    divider()
    line("Thank you!",  size=9, gap=5)
    line("Come again.", size=9, gap=5)

    c.save()
    return filepath