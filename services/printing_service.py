from models.receipt import ReceiptData
from models.advance_settings import AdvanceSettings
from PySide6.QtPrintSupport import QPrinter, QPrinterInfo
from PySide6.QtGui import QPainter, QFont, QFontMetrics, QPixmap
from PySide6.QtCore import Qt, QMarginsF, QSizeF
from PySide6.QtGui import QPageSize
from datetime import datetime
from pathlib import Path


class PrintingService:
    def __init__(self):
        self.paper_width = 550
        self.margin = 10

        
    def print_kitchen_order(self, receipt: ReceiptData, printer_name: str = None) -> bool:
        """Prints simple KOT for kitchen - Qty + Name only"""
        settings = AdvanceSettings.load_from_file()   # Fresh settings every print

        painter = None
        try:
            printer = QPrinter(QPrinter.HighResolution)
            if printer_name and printer_name != "(None)":
                info = QPrinterInfo.printerInfo(printer_name)
                if not info.isNull():
                    printer.setPrinterName(printer_name)

            printer.setPageSize(QPageSize(QSizeF(80, 2000), QPageSize.Millimeter))
            printer.setPageMargins(QMarginsF(0, 0, 0, 0))

            painter = QPainter(printer)
            y = 20

            # ====================== FONT SETUP (from AdvanceSettings) ======================
            header_font = self._create_font(
                settings.contentHeaderFontName,
                settings.contentHeaderSize,
                settings.contentHeaderStyle
            )

            normal_font = self._create_font(
                settings.contentFontName,
                settings.contentFontSize,
                settings.contentFontStyle
            )

            order_font = self._create_font(
                settings.orderContentFontName,
                settings.orderContentFontSize,
                settings.orderContentStyle
            )

            # ====================== KOT HEADER (uses Header Font) ======================
            painter.setFont(header_font)
            painter.drawText(self.margin, y, self.paper_width - self.margin*2, 50,
                             Qt.AlignCenter, "KITCHEN ORDER")
            y += 60

            # ====================== ORDER & INVOICE NO (uses Normal Font) ======================
            painter.setFont(order_font)

            painter.drawText(self.margin, y, self.paper_width - self.margin*2, 30,
                             Qt.AlignCenter, f"Order No : {receipt.KOT or 'KOT-' + str(receipt.invoiceNo)}")
            y += 35

            painter.setFont(normal_font)

            painter.drawText(self.margin, y, self.paper_width - self.margin*2, 30,
                             Qt.AlignCenter, f"Invoice No : {receipt.invoiceNo or 'N/A'}")
            y += 35

            painter.drawText(self.margin, y, self.paper_width - self.margin*2, 30,
                             Qt.AlignCenter, f"Time : {datetime.now().strftime('%H:%M')}")
            y += 40

            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 30

            # ====================== ITEMS (Qty × Name) - uses Order Content Font ======================
            painter.setFont(order_font)

            for item in receipt.items:
                line = f"{int(item.qty)} × {item.productName}"
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 35,
                                 Qt.AlignLeft, line)
                y += 38

            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 30

            # ====================== FOOTER (uses Normal Font) ======================
            painter.setFont(normal_font)
            painter.drawText(self.margin, y, self.paper_width - self.margin*2, 30,
                             Qt.AlignCenter, "Please prepare quickly!")
            y += 25
            painter.drawText(self.margin, y, self.paper_width - self.margin*2, 25,
                             Qt.AlignCenter, "Thank you - Havano POS")

            painter.end()
            print(f"✅ KITCHEN ORDER printed successfully → {printer_name or 'Default'}")
            return True

        except Exception as e:
            print(f"❌ KOT Printing failed: {str(e)}")
            if painter and painter.isActive():
                painter.end()
            return False

    def _create_font(self, family: str, size: int, style_str: str = "Regular") -> QFont:
        font = QFont(family or "Arial", max(size or 10, 8))

        if not style_str:
            style_str = "Regular"
        style_lower = style_str.strip().lower()

        is_bold = any(word in style_lower for word in ["bold", "heavy", "black", "extrabold", "semibold", "demi"])
        font.setWeight(QFont.Bold if is_bold else QFont.Normal)

        is_italic = any(word in style_lower for word in ["italic", "oblique", "cursive", "slant"])
        font.setItalic(is_italic)

        return font

    def print_receipt(self, receipt: ReceiptData, printer_name: str = None) -> bool:
        # Fresh settings every print
        settings = AdvanceSettings.load_from_file()

        try:
            printer = QPrinter(QPrinter.HighResolution)
            if printer_name and printer_name != "(None)":
                info = QPrinterInfo.printerInfo(printer_name)
                if not info.isNull():
                    printer.setPrinterName(printer_name)

            printer.setPageSize(QPageSize(QSizeF(100, 1000), QPageSize.Millimeter))
            printer.setFullPage(True)
            printer.setPageMargins(QMarginsF(0, 0, 0, 0))

            painter = QPainter(printer)

            # eliminate top offset from printer
            rect = printer.pageRect(QPrinter.DevicePixel)
            painter.translate(0, -rect.top())

            y = 0

            # ====================== LOGO (NEW - loads from app_data/logos/) ======================
            if settings.logoDirectory:
                logo_full_path = Path("app_data/logos") / settings.logoDirectory
                if logo_full_path.exists():
                    logo_pix = QPixmap(str(logo_full_path))
                    if not logo_pix.isNull():
                        scaled = logo_pix.scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        x = (self.paper_width - scaled.width()) // 2
                        painter.drawPixmap(x, y, scaled)
                        y += scaled.height() + 10

            # ====================== FONT SETUP ======================
            header_font = self._create_font(
                settings.contentHeaderFontName,
                settings.contentHeaderSize,
                settings.contentHeaderStyle
            )

            normal_font = self._create_font(
                settings.contentFontName,
                settings.contentFontSize,
                settings.contentFontStyle
            )

            order_font = self._create_font(
                settings.orderContentFontName,
                settings.orderContentFontSize,
                settings.orderContentStyle
            )

            subheader_font = self._create_font(
                settings.subheaderFontName,
                settings.subheaderSize,
                settings.subheaderStyle
            )

            # ====================== HEADER ======================
            painter.setFont(header_font)
            painter.drawText(
                self.margin, y,
                self.paper_width - self.margin * 2, 40,
                Qt.AlignCenter,
                (receipt.companyName or "Havano POS").upper()
            )
            y += 60

            # ====================== COMPANY INFO ======================
            painter.setFont(subheader_font)

            if receipt.companyAddress:
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 22,
                                 Qt.AlignCenter, receipt.companyAddress)
                y += 30

            if receipt.companyAddressLine1:
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 22,
                                 Qt.AlignCenter, receipt.companyAddressLine1)
                y += 30

            if receipt.companyAddressLine2:
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 22,
                                 Qt.AlignCenter, receipt.companyAddressLine2)
                y += 30

            if receipt.city or receipt.state or receipt.postcode:
                city_state = f"{receipt.city} {receipt.state} {receipt.postcode}".strip()
                if city_state:
                    painter.drawText(self.margin, y, self.paper_width - self.margin*2, 22,
                                     Qt.AlignCenter, city_state)
                    y += 30

            if receipt.tel:
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 22,
                                 Qt.AlignCenter, f"Tel: {receipt.tel}")
                y += 30

            if receipt.companyEmail:
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 22,
                                 Qt.AlignCenter, receipt.companyEmail)
                y += 24

            if receipt.tin:
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 22,
                                 Qt.AlignCenter, f"TIN: {receipt.tin}")
                y += 24

            if receipt.vatNo:
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 22,
                                 Qt.AlignCenter, f"VAT: {receipt.vatNo}")
                y += 24

            y += 10
            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 25

            # ====================== INVOICE INFO ======================
            painter.drawText(self.margin, y, f"Invoice : {receipt.invoiceNo or 'N/A'}")
            y += 30
            painter.drawText(self.margin, y, f"Date : {receipt.invoiceDate or datetime.now().strftime('%d/%m/%Y')}")
            y += 30
            painter.drawText(self.margin, y, f"Cashier : {receipt.cashierName or 'Admin'}")
            y += 30

            if receipt.customerName:
                painter.drawText(self.margin, y, f"Customer : {receipt.customerName}")
                y += 22

            if receipt.customerContact:
                painter.drawText(self.margin, y, f"Contact : {receipt.customerContact}")
                y += 22

            if receipt.customerTin:
                painter.drawText(self.margin, y, f"Customer TIN : {receipt.customerTin}")
                y += 22

            if receipt.customerVat:
                painter.drawText(self.margin, y, f"Customer VAT : {receipt.customerVat}")
                y += 22

            y += 10
            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 24

            # ====================== DYNAMIC WIDTH CALC ======================
            painter.setFont(normal_font)
            fm: QFontMetrics = painter.fontMetrics()

            max_qty_w   = fm.horizontalAdvance("Qty")
            max_price_w = fm.horizontalAdvance("Price")
            max_total_w = fm.horizontalAdvance("Total")

            for item in receipt.items:
                max_qty_w   = max(max_qty_w,   fm.horizontalAdvance(f"{item.qty:.0f}"))
                max_price_w = max(max_price_w, fm.horizontalAdvance(f"{item.price:,.2f}"))
                max_total_w = max(max_total_w, fm.horizontalAdvance(f"{item.amount:,.2f}"))

            max_qty_w   += 10
            max_price_w += 14
            max_total_w += 14

            TOTAL_X = self.paper_width - self.margin - max_total_w
            PRICE_X = TOTAL_X - max_price_w - 10
            QTY_X   = PRICE_X - max_qty_w - 10

            # ====================== ITEM HEADER ======================
            painter.setFont(subheader_font)

            painter.drawText(QTY_X,   y, max_qty_w,   24, Qt.AlignCenter, "Qty")
            painter.drawText(PRICE_X, y, max_price_w, 24, Qt.AlignRight,  "Price")
            painter.drawText(TOTAL_X, y, max_total_w, 24, Qt.AlignRight,  "Total")

            y += 40
            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 24

            # ====================== ITEMS ======================
            painter.setFont(normal_font)
            line_h = fm.height() + 6

            for item in receipt.items:
                name = item.productName or ""

                # Product name wrapped
                rect = fm.boundingRect(0, 0, self.paper_width - self.margin * 2, 1000,
                                       Qt.TextWordWrap, name)

                painter.drawText(self.margin, y, self.paper_width - self.margin * 2,
                                 rect.height(), Qt.TextWordWrap, name)
                y += rect.height() + 4

                # Qty / Price / Total
                painter.drawText(QTY_X,   y, max_qty_w,   line_h, Qt.AlignCenter, f"{item.qty:.0f}")
                painter.drawText(PRICE_X, y, max_price_w, line_h, Qt.AlignRight,  f"{item.price:,.2f}")
                painter.drawText(TOTAL_X, y, max_total_w, line_h, Qt.AlignRight,  f"{item.amount:,.2f}")

                y += line_h + 8

                # Dotted line
                self._draw_dot_line(painter, self.margin, y, self.paper_width - self.margin * 2, ".")
                y += 14

            # ====================== TOTALS ======================
            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 14

            painter.setFont(subheader_font)
            fm = painter.fontMetrics()
            line_h = fm.height() + 6

            def draw_total(label: str, value: float):
                nonlocal y
                text = f"{value:,.2f}"
                w = fm.horizontalAdvance(text)
                painter.drawText(self.margin, y, 200, line_h, Qt.AlignLeft, label)
                painter.drawText(self.paper_width - self.margin - w, y, w, line_h,
                                 Qt.AlignRight, text)
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
                             Qt.AlignCenter, receipt.footer or "Thank you for your purchase!")
            y += 26
            painter.drawText(self.margin, y, self.paper_width - self.margin*2, 20,
                             Qt.AlignCenter, "Come again soon!")

            painter.end()
            print(f"✅ Receipt printed successfully on {printer_name or 'Default Printer'}")
            return True

        except Exception as e:
            print(f"❌ Printing failed: {str(e)}")
            if 'painter' in locals() and painter.isActive():
                painter.end()
            return False

    def _draw_dot_line(self, painter, start_x, y, width, dot_char="."):
        fm = painter.fontMetrics()
        dot_width = fm.horizontalAdvance(dot_char)
        if dot_width <= 0:
            return
        num_dots = int(width / dot_width) + 1
        painter.drawText(start_x, y, dot_char * num_dots)

    def get_available_printers(self) -> list[str]:
        try:
            return ["(None)"] + [p.printerName() for p in QPrinterInfo.availablePrinters()]
        except:
            return ["(None)", "Default Printer"]

















# Singleton
printing_service = PrintingService()