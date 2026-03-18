from models.receipt import ReceiptData
from models.advance_settings import AdvanceSettings
from PySide6.QtPrintSupport import QPrinter, QPrinterInfo
from PySide6.QtGui import QPainter, QFont
from PySide6.QtCore import Qt, QMarginsF, QSizeF
from PySide6.QtGui import QPageSize
from datetime import datetime


class PrintingService:
    def __init__(self):
        self.settings = AdvanceSettings.load_from_file()
        self.paper_width = 550   # 80mm thermal printer
        self.margin = 10

    def print_receipt(self, receipt: ReceiptData, printer_name: str = None) -> bool:
        try:
            # ====================== PRINTER SETUP ======================
            printer = QPrinter(QPrinter.HighResolution)

            if printer_name and printer_name != "(None)":
                info = QPrinterInfo.printerInfo(printer_name)
                if not info.isNull():
                    printer.setPrinterName(printer_name)

            page_size = QPageSize(QSizeF(100, 1000), QPageSize.Millimeter)
            printer.setPageSize(page_size)
            printer.setPageMargins(QMarginsF(-10, 0, 0, 0))

            painter = QPainter(printer)
            y = -10

            # ====================== FONT SETUP ======================
            header_font = QFont(self.settings.contentHeaderFontName or "Arial",
                                max(self.settings.contentHeaderSize or 12, 10))
            header_font.setBold(True)

            normal_font = QFont(self.settings.contentFontName or "Arial",
                                max(self.settings.contentFontSize or 10, 8))

            bold_font = QFont(self.settings.subheaderFontName or "Arial",
                              max(self.settings.subheaderSize or 11, 10))
            bold_font.setBold(True)

            # ====================== HEADER ======================
            painter.setFont(header_font)
            painter.drawText(
                self.margin, y,
                self.paper_width - self.margin * 2, 40,
                Qt.AlignCenter,
                (receipt.companyName or "Havano POS").upper()
            )
            y += 60

            painter.setFont(normal_font)

            if receipt.companyAddressLine1:
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 22,
                                 Qt.AlignCenter, receipt.companyAddressLine1)
                y += 24

            if receipt.companyAddressLine2:
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 22,
                                 Qt.AlignCenter, receipt.companyAddressLine2)
                y += 24

            y += 10

            # ====================== INVOICE INFO ======================
            full_width = self.paper_width - self.margin * 2

            invoice_text = f"Invoice : {receipt.invoiceNo or 'N/A'}"
            date_text = f"Date : {receipt.invoiceDate or datetime.now().strftime('%d/%m/%Y')}"

            painter.drawText(self.margin, y, invoice_text)
            y += 30
            painter.drawText(self.margin, y, date_text )
            y += 30

            painter.drawText(self.margin, y, f"Cashier : {receipt.cashierName or 'Admin'}")
            y += 30

            if receipt.customerName:
                painter.drawText(self.margin, y, f"Customer : {receipt.customerName}")
                y += 22

            y += 10
            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            # y += 10
            # painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 24

            # ====================== DYNAMIC WIDTH CALC ======================
            painter.setFont(normal_font)
            fm = painter.fontMetrics()

            max_qty_w = fm.horizontalAdvance("Qty")
            max_price_w = fm.horizontalAdvance("Price")
            max_total_w = fm.horizontalAdvance("Total")

            for item in receipt.items:
                max_qty_w = max(max_qty_w, fm.horizontalAdvance(f"{item.qty:.0f}"))
                max_price_w = max(max_price_w, fm.horizontalAdvance(f"{item.price:,.2f}"))
                max_total_w = max(max_total_w, fm.horizontalAdvance(f"{item.amount:,.2f}"))

            max_qty_w += 10
            max_price_w += 14
            max_total_w += 14

            TOTAL_X = self.paper_width - self.margin - max_total_w
            PRICE_X = TOTAL_X - max_price_w - 10
            QTY_X = PRICE_X - max_qty_w - 10

            # ====================== HEADER ROW ======================
            painter.setFont(bold_font)

            painter.drawText(QTY_X, y, max_qty_w, 24, Qt.AlignCenter, "Qty")
            painter.drawText(PRICE_X, y, max_price_w, 24, Qt.AlignRight, "Price")
            painter.drawText(TOTAL_X, y, max_total_w, 24, Qt.AlignRight, "Total")

            y += 40
            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
           
            y += 24

            # ====================== ITEMS ======================
            painter.setFont(normal_font)
            line_h = fm.height() + 6

            for item in receipt.items:
                name = item.productName or ""

                # 🔹 PRODUCT NAME (WRAPPED FULL WIDTH)
                rect = fm.boundingRect(
                    0, 0,
                    self.paper_width - self.margin * 2,
                    1000,
                    Qt.TextWordWrap,
                    name
                )

                painter.drawText(
                    self.margin, y,
                    self.paper_width - self.margin * 2,
                    rect.height(),
                    Qt.TextWordWrap,
                    name
                )

                y += rect.height() + 4

                # 🔹 VALUES ROW
                painter.drawText(QTY_X, y, max_qty_w, line_h, Qt.AlignCenter, f"{item.qty:.0f}")
                painter.drawText(PRICE_X, y, max_price_w, line_h, Qt.AlignRight, f"{item.price:,.2f}")
                painter.drawText(TOTAL_X, y, max_total_w, line_h, Qt.AlignRight, f"{item.amount:,.2f}")
                
                y += line_h + 8

                # 🔹 DOT UNDERLINE SEPARATOR AT BOTTOM OF EACH ITEM
                self._draw_dot_line(painter, self.margin, y, self.paper_width - self.margin * 2, ".")
                y += 14

            # ====================== TOTALS SECTION ======================
            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 14

            # ====================== TOTALS ======================
            painter.setFont(bold_font)
            fm = painter.fontMetrics()
            line_h = fm.height() + 6

            def draw_total(label, value):
                nonlocal y
                text = f"{value:,.2f}"
                w = fm.horizontalAdvance(text)

                painter.drawText(self.margin, y, 200, line_h, Qt.AlignLeft, label)
                painter.drawText(
                    self.paper_width - self.margin - w,
                    y,
                    w,
                    line_h,
                    Qt.AlignRight,
                    text
                )
                y += line_h

            draw_total("Subtotal", receipt.subtotal)

            if receipt.totalVat > 0:
                draw_total("VAT", receipt.totalVat)

            draw_total("GRAND TOTAL", receipt.grandTotal)
            y += 6
            draw_total("Paid", receipt.amountTendered)
            draw_total("Change", receipt.change)

            y += 20

            # ====================== FOOTER ======================
            painter.setFont(normal_font)

            painter.drawText(self.margin, y, self.paper_width - self.margin*2, 30,
                             Qt.AlignCenter,
                             receipt.footer or "Thank you for your purchase!")
            y += 26

            painter.drawText(self.margin, y, self.paper_width - self.margin*2, 20,
                             Qt.AlignCenter,
                             "Come again soon!")

            painter.end()

            print(f"✅ Receipt printed successfully to: {printer_name or 'Default Printer'}")
            return True

        except Exception as e:
            print(f"❌ Printing failed: {str(e)}")
            return False

    def _draw_dot_line(self, painter, start_x, y, width, dot_char="."):
        """Draw a dotted line using dot characters"""
        fm = painter.fontMetrics()
        dot_width = fm.horizontalAdvance(dot_char)
        
        if dot_width <= 0:
            return
        
        num_dots = int(width / dot_width)
        dot_line = dot_char * num_dots
        
        painter.drawText(start_x, y, dot_line)

    def get_available_printers(self) -> list[str]:
        try:
            return ["(None)"] + [p.printerName() for p in QPrinterInfo.availablePrinters()]
        except:
            return ["(None)", "Default Printer"]


# Singleton
printing_service = PrintingService()