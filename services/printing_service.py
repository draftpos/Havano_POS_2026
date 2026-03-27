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
        self.page_break_threshold = 50  # pixels from bottom to trigger page break

    def print_kitchen_order(self, receipt: ReceiptData, printer_name: str = None) -> bool:
        """Prints simple KOT for kitchen - Qty + Name only"""
        settings = AdvanceSettings.load_from_file()

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

            painter.setFont(header_font)
            painter.drawText(self.margin, y, self.paper_width - self.margin*2, 50,
                             Qt.AlignCenter, "KITCHEN ORDER")
            y += 60

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

            painter.setFont(order_font)
            for item in receipt.items:
                line = f"{int(item.qty)} × {item.productName}"
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 35,
                                  Qt.AlignLeft, line)
                y += 38

            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 30

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
        is_bold   = any(w in style_lower for w in ["bold", "heavy", "black", "extrabold", "semibold", "demi"])
        is_italic = any(w in style_lower for w in ["italic", "oblique", "cursive", "slant"])
        font.setWeight(QFont.Bold if is_bold else QFont.Normal)
        font.setItalic(is_italic)
        return font

    def _make_bold(self, font: QFont) -> QFont:
        """Return a copy of font with Bold weight forced on."""
        f = QFont(font)
        f.setWeight(QFont.Bold)
        return f

    def print_receipt(self, receipt: ReceiptData, printer_name: str = None) -> bool:
        if getattr(receipt, "doc_type", "receipt") == "sales_order":
            return self.print_sales_order_receipt(receipt, printer_name=printer_name)
        if getattr(receipt, "doc_type", "receipt") == "payment":
            return self._print_payment_receipt(receipt, printer_name=printer_name)
        return self._print_invoice_receipt(receipt, printer_name=printer_name)

    def _calculate_required_height(self, receipt: ReceiptData, settings: AdvanceSettings) -> float:
        """Calculate the total height needed for all content in pixels."""
        fm = QFontMetrics(self._create_font(settings.contentFontName, settings.contentFontSize, settings.contentFontStyle))
        height = 0

        # Logo estimation
        if settings.logoDirectory:
            logo_full_path = Path("app_data/logos") / settings.logoDirectory
            if logo_full_path.exists():
                height += 150  # Estimated logo height

        # Header section
        height += 60 + 60 + 30 * 6  # Company name + address lines

        # Invoice details section
        height += 35 * 5  # Invoice, Date, Cashier, Customer info

        # Items section
        height += 40 + 24  # Header row + line
        for item in receipt.items:
            item_height = fm.height() + 6
            text_rect = fm.boundingRect(0, 0, self.paper_width - self.margin * 2, 1000, 
                                       Qt.TextWordWrap, item.productName or "")
            item_height = max(item_height, text_rect.height()) + 4
            height += item_height + 14  # Item + dot line

        # Footer section
        height += 40 * 5 + 50  # Totals + footer

        return height

    def _print_invoice_receipt(self, receipt: ReceiptData, printer_name: str = None) -> bool:
        """Print invoice with dynamic multi-page support."""
        settings = AdvanceSettings.load_from_file()

        painter = None
        try:
            # Calculate required height
            total_height_pixels = self._calculate_required_height(receipt, settings)
            
            # Convert to millimeters (203 DPI thermal printer standard)
            dpi = 203
            height_mm = (total_height_pixels / dpi) * 25.4 + 10  # +10mm buffer

            printer = QPrinter(QPrinter.HighResolution)
            printer.setResolution(dpi)
            
            if printer_name and printer_name != "(None)":
                info = QPrinterInfo.printerInfo(printer_name)
                if not info.isNull():
                    printer.setPrinterName(printer_name)

            custom_size = QSizeF(80.0, height_mm)
            printer.setPageSize(QPageSize(custom_size, QPageSize.Millimeter, "Receipt80mm", QPageSize.ExactMatch))
            printer.setFullPage(True)
            printer.setPageMargins(QMarginsF(0, 0, 0, 0))

            painter = QPainter(printer)
            rect = printer.pageRect(QPrinter.DevicePixel)
            page_height = rect.height()
            
            painter.translate(0, -rect.top())
            y = 0
            page_num = 1

            normal_font = self._create_font(settings.contentFontName, settings.contentFontSize, settings.contentFontStyle)
            bold_font = self._make_bold(normal_font)

            # ─── LOGO ───
            if settings.logoDirectory:
                logo_full_path = Path("app_data/logos") / settings.logoDirectory
                if logo_full_path.exists():
                    logo_pix = QPixmap(str(logo_full_path))
                    if not logo_pix.isNull():
                        scaled = logo_pix.scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        x = (self.paper_width - scaled.width()) // 2
                        painter.drawPixmap(x, y, scaled)
                        y += scaled.height() + 10

            # ─── COMPANY HEADER ───
            painter.setFont(bold_font)
            painter.drawText(self.margin, y, self.paper_width - self.margin * 2, 40,
                             Qt.AlignCenter, (receipt.companyName or "Havano POS").upper())
            y += 60

            painter.setFont(normal_font)
            for line in [receipt.companyAddress, receipt.companyAddressLine1, receipt.companyAddressLine2]:
                if line:
                    painter.drawText(self.margin, y, self.paper_width - self.margin*2, 22, Qt.AlignCenter, line)
                    y += 30
            
            city_state = f"{receipt.city} {receipt.state} {receipt.postcode}".strip()
            if city_state:
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 22, Qt.AlignCenter, city_state)
                y += 30
            if receipt.tel:
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 22, Qt.AlignCenter, f"Tel: {receipt.tel}")
                y += 30
            if receipt.companyEmail:
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 22, Qt.AlignCenter, receipt.companyEmail)
                y += 24
            if receipt.tin:
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 22, Qt.AlignCenter, f"TIN: {receipt.tin}")
                y += 24
            if receipt.vatNo:
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 22, Qt.AlignCenter, f"VAT: {receipt.vatNo}")
                y += 24

            y += 10
            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 25

            # ─── INVOICE DETAILS ───
            painter.setFont(normal_font)
            painter.drawText(self.margin, y, self.paper_width - self.margin*2, 30, Qt.AlignCenter, f"Invoice : {receipt.invoiceNo or 'N/A'}")
            y += 30
            painter.drawText(self.margin, y, self.paper_width - self.margin*2, 30, Qt.AlignCenter, f"Date    : {receipt.invoiceDate or datetime.now().strftime('%d/%m/%Y')}")
            y += 30
            painter.drawText(self.margin, y, self.paper_width - self.margin*2, 30, Qt.AlignCenter, f"Cashier : {receipt.cashierName or 'Admin'}")
            y += 30
            
            if receipt.customerName:
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 22, Qt.AlignCenter, f"Customer : {receipt.customerName}")
                y += 22
            if receipt.customerContact:
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 22, Qt.AlignCenter, f"Contact  : {receipt.customerContact}")
                y += 22
            if receipt.customerTin:
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 22, Qt.AlignCenter, f"Customer TIN : {receipt.customerTin}")
                y += 22
            if receipt.customerVat:
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 22, Qt.AlignCenter, f"Customer VAT : {receipt.customerVat}")
                y += 22

            y += 10
            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 24

            # ─── ITEMS TABLE HEADER ───
            painter.setFont(normal_font)
            fm: QFontMetrics = painter.fontMetrics()

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

            # Check if we need to start a new page for items
            if y + 80 > page_height - self.page_break_threshold:
                printer.newPage()
                y = 0

            painter.setFont(bold_font)
            painter.drawText(QTY_X, y, max_qty_w, 24, Qt.AlignCenter, "Qty")
            painter.drawText(PRICE_X, y, max_price_w, 24, Qt.AlignRight, "Price")
            painter.drawText(TOTAL_X, y, max_total_w, 24, Qt.AlignRight, "Total")
            y += 40
            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 24

            # ─── ITEMS ───
            painter.setFont(normal_font)
            line_h = fm.height() + 6
            
            for item in receipt.items:
                name = item.productName or ""
                rect = fm.boundingRect(0, 0, self.paper_width - self.margin * 2, 1000, Qt.TextWordWrap, name)
                item_height = rect.height() + line_h + 22

                # Check if item fits on current page
                if y + item_height > page_height - self.page_break_threshold:
                    # Add footer to current page
                    painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
                    
                    # Start new page
                    printer.newPage()
                    y = 0
                    page_num += 1

                painter.drawText(self.margin, y, self.paper_width - self.margin * 2, rect.height(), Qt.TextWordWrap, name)
                y += rect.height() + 4
                painter.drawText(QTY_X, y, max_qty_w, line_h, Qt.AlignCenter, f"{item.qty:.0f}")
                painter.drawText(PRICE_X, y, max_price_w, line_h, Qt.AlignRight, f"{item.price:,.2f}")
                painter.drawText(TOTAL_X, y, max_total_w, line_h, Qt.AlignRight, f"{item.amount:,.2f}")
                y += line_h + 8
                self._draw_dot_line(painter, self.margin, y, self.paper_width - self.margin * 2, ".")
                y += 14

            # ─── TOTALS SECTION ───
            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 14

            # Check if totals fit
            totals_height = 90
            if y + totals_height > page_height - self.page_break_threshold:
                printer.newPage()
                y = 0

            painter.setFont(normal_font)
            fm = painter.fontMetrics()
            line_h = fm.height() + 6

            def draw_total(label: str, value: float):
                nonlocal y
                text = f"{value:,.2f}"
                w = fm.horizontalAdvance(text)
                painter.drawText(self.margin, y, 200, line_h, Qt.AlignLeft, label)
                painter.drawText(self.paper_width - self.margin - w, y, w, line_h, Qt.AlignRight, text)
                y += line_h

            draw_total("Subtotal", receipt.subtotal)
            if receipt.totalVat > 0:
                draw_total("VAT", receipt.totalVat)
            draw_total("Grand Total", receipt.grandTotal)
            y += 6
            draw_total("Amount Tendered", receipt.amountTendered)
            draw_total("Change", receipt.change)
            y += 20

            # ─── FOOTER ───
            painter.setFont(normal_font)
            painter.drawText(self.margin, y, self.paper_width - self.margin*2, 30,
                             Qt.AlignCenter, receipt.footer or "Thank you for your purchase!")
            y += 26
            painter.drawText(self.margin, y, self.paper_width - self.margin*2, 20,
                             Qt.AlignCenter, "Come again soon!")

            painter.end()
            print(f"✅ INVOICE printed successfully ({page_num} pages) → {printer_name or 'Default'}")
            return True

        except Exception as e:
            print(f"❌ Invoice printing failed: {str(e)}")
            if painter and painter.isActive():
                painter.end()
            return False

    def _print_payment_receipt(self, receipt: ReceiptData, printer_name: str = None) -> bool:
        """Dedicated template for customer payment receipts."""
        settings = AdvanceSettings.load_from_file()

        painter = None
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
            rect = printer.pageRect(QPrinter.DevicePixel)
            painter.translate(0, -rect.top())
            y = 0

            normal_font = self._create_font(settings.contentFontName, settings.contentFontSize, settings.contentFontStyle)
            bold_font = self._make_bold(normal_font)

            # ── LOGO ─────────────────────────────────────────────────────────
            if settings.logoDirectory:
                logo_full_path = Path("app_data/logos") / settings.logoDirectory
                if logo_full_path.exists():
                    logo_pix = QPixmap(str(logo_full_path))
                    if not logo_pix.isNull():
                        scaled = logo_pix.scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        x = (self.paper_width - scaled.width()) // 2
                        painter.drawPixmap(x, y, scaled)
                        y += scaled.height() + 10

            # ── COMPANY DETAILS ───────────────────────────────────────────────
            painter.setFont(bold_font)
            painter.drawText(self.margin, y, self.paper_width - self.margin * 2, 40,
                             Qt.AlignCenter, (receipt.companyName or "Havano POS").upper())
            y += 60

            painter.setFont(normal_font)
            for line in [receipt.companyAddress, receipt.companyAddressLine1, receipt.companyAddressLine2]:
                if line:
                    painter.drawText(self.margin, y, self.paper_width - self.margin*2, 22, Qt.AlignCenter, line)
                    y += 30
            city_state = f"{receipt.city} {receipt.state} {receipt.postcode}".strip()
            if city_state:
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 22, Qt.AlignCenter, city_state)
                y += 30
            if receipt.tel:
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 22, Qt.AlignCenter, f"Tel: {receipt.tel}")
                y += 30
            if receipt.companyEmail:
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 22, Qt.AlignCenter, receipt.companyEmail)
                y += 24
            if receipt.tin:
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 22, Qt.AlignCenter, f"TIN: {receipt.tin}")
                y += 24
            if receipt.vatNo:
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 22, Qt.AlignCenter, f"VAT: {receipt.vatNo}")
                y += 24

            y += 10
            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 25

            # ── HEADING ───────────────────────────────────────────────────────
            painter.setFont(bold_font)
            painter.drawText(self.margin, y, self.paper_width - self.margin * 2, 44,
                             Qt.AlignCenter, "*** PAYMENT RECEIPT ***")
            y += 60

            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 25

            # ── PAYMENT DETAILS ───────────────────────────────────────────────
            painter.setFont(normal_font)
            painter.drawText(self.margin, y, self.paper_width - self.margin*2, 28,
                             Qt.AlignCenter, f"Ref No    :  {receipt.orderNo or 'N/A'}")
            y += 32
            painter.drawText(self.margin, y, self.paper_width - self.margin*2, 28,
                             Qt.AlignCenter, f"Date      :  {receipt.date or datetime.now().strftime('%d/%m/%Y')}")
            y += 32
            painter.drawText(self.margin, y, self.paper_width - self.margin*2, 28,
                             Qt.AlignCenter, f"Customer  :  {receipt.customer or 'Walk-in'}")
            y += 32

            y += 8
            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 20

            # ── AMOUNT PAID & BALANCE ─────────────────────────────────────────
            fm = painter.fontMetrics()
            line_h = fm.height() + 10

            painter.setFont(bold_font)
            amount_text = f"{receipt.total:,.2f}"
            w = fm.horizontalAdvance(amount_text)
            painter.drawText(self.margin, y, 300, line_h, Qt.AlignLeft, "Amount Paid")
            painter.drawText(self.paper_width - self.margin - w, y, w, line_h, Qt.AlignRight, amount_text)
            y += line_h + 4

            painter.setFont(normal_font)
            balance = getattr(receipt, "balanceDue", 0.0) or 0.0
            balance_text = f"{balance:,.2f}"
            w2 = fm.horizontalAdvance(balance_text)
            painter.drawText(self.margin, y, 300, line_h, Qt.AlignLeft, "Customer Balance")
            painter.drawText(self.paper_width - self.margin - w2, y, w2, line_h, Qt.AlignRight, balance_text)
            y += line_h + 10

            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 20

            # ── FOOTER ────────────────────────────────────────────────────────
            painter.setFont(normal_font)
            painter.drawText(self.margin, y, self.paper_width - self.margin*2, 30,
                             Qt.AlignCenter, receipt.footer or "Thank you for your payment!")
            y += 30

            painter.end()
            return True

        except Exception as e:
            print(f"❌ Payment receipt printing failed: {str(e)}")
            if painter and painter.isActive():
                painter.end()
            return False

    def print_sales_order_receipt(self, receipt: ReceiptData, printer_name: str = None) -> bool:
        """Print sales order with multi-page support."""
        settings = AdvanceSettings.load_from_file()

        painter = None
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
            rect = printer.pageRect(QPrinter.DevicePixel)
            page_height = rect.height()
            painter.translate(0, -rect.top())
            y = 0

            normal_font = self._create_font(settings.contentFontName, settings.contentFontSize, settings.contentFontStyle)
            bold_font = self._make_bold(normal_font)

            if settings.logoDirectory:
                logo_full_path = Path("app_data/logos") / settings.logoDirectory
                if logo_full_path.exists():
                    logo_pix = QPixmap(str(logo_full_path))
                    if not logo_pix.isNull():
                        scaled = logo_pix.scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        x_logo = (self.paper_width - scaled.width()) // 2
                        painter.drawPixmap(x_logo, y, scaled)
                        y += scaled.height() + 10

            painter.setFont(bold_font)
            painter.drawText(self.margin, y, self.paper_width - self.margin * 2, 40,
                             Qt.AlignCenter, (receipt.companyName or "Havano POS").upper())
            y += 50

            painter.setFont(normal_font)
            for line in [receipt.companyAddress, receipt.companyAddressLine1]:
                if line:
                    painter.drawText(self.margin, y, self.paper_width - self.margin*2, 22, Qt.AlignCenter, line)
                    y += 26
            if receipt.tel:
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 22, Qt.AlignCenter, f"Tel: {receipt.tel}")
                y += 26
            if receipt.companyEmail:
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 22, Qt.AlignCenter, receipt.companyEmail)
                y += 22
            if receipt.tin:
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 22, Qt.AlignCenter, f"TIN: {receipt.tin}")
                y += 22
            if receipt.vatNo:
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 22, Qt.AlignCenter, f"VAT: {receipt.vatNo}")
                y += 22

            y += 8
            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 20

            painter.setFont(bold_font)
            doc_heading = f"*** {(receipt.receiptType or 'SALES ORDER').upper()} ***"
            painter.drawText(self.margin, y, self.paper_width - self.margin * 2, 44,
                             Qt.AlignCenter, doc_heading)
            y += 60

            painter.setFont(normal_font)
            order_text = f"Order No  :  {receipt.invoiceNo or 'N/A'}"
            painter.drawText(self.margin, y, self.paper_width - self.margin*2, 28, Qt.AlignCenter, order_text)
            y += 32

            order_date = receipt.invoiceDate or datetime.now().strftime("%Y-%m-%d")
            date_text = f"Order Date  :  {order_date}"
            painter.drawText(self.margin, y, self.paper_width - self.margin*2, 28, Qt.AlignCenter, date_text)
            y += 32

            delivery_date = getattr(receipt, "deliveryDate", "")
            if delivery_date:
                delivery_text = f"Delivery  :  {delivery_date}"
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 28, Qt.AlignCenter, delivery_text)
                y += 32

            if receipt.customerName:
                customer_text = f"Customer  :  {receipt.customerName}"
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 28, Qt.AlignCenter, customer_text)
                y += 32

            if receipt.customerContact:
                contact_text = f"Contact  :  {receipt.customerContact}"
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 28, Qt.AlignCenter, contact_text)
                y += 32

            y += 8
            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 20

            # Check if items section fits
            if y + 60 > page_height - self.page_break_threshold:
                printer.newPage()
                y = 0

            painter.setFont(normal_font)
            fm: QFontMetrics = painter.fontMetrics()

            max_qty_w = fm.horizontalAdvance("Qty")
            max_price_w = fm.horizontalAdvance("Price")
            max_total_w = fm.horizontalAdvance("Amount")

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

            painter.setFont(bold_font)
            painter.drawText(self.margin, y, QTY_X - self.margin, 24, Qt.AlignLeft, "Item")
            painter.drawText(QTY_X, y, max_qty_w, 24, Qt.AlignCenter, "Qty")
            painter.drawText(PRICE_X, y, max_price_w, 24, Qt.AlignRight, "Price")
            painter.drawText(TOTAL_X, y, max_total_w, 24, Qt.AlignRight, "Amount")
            y += 30
            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 18

            painter.setFont(normal_font)
            line_h = fm.height() + 6

            for item in receipt.items:
                name = item.productName or ""
                name_w = QTY_X - self.margin - 6
                rect = fm.boundingRect(0, 0, name_w, 1000, Qt.TextWordWrap, name)
                item_height = max(rect.height(), line_h) + 18

                # Check if item fits
                if y + item_height > page_height - self.page_break_threshold:
                    painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
                    printer.newPage()
                    y = 0

                painter.drawText(self.margin, y, name_w, rect.height(), Qt.TextWordWrap, name)
                row_h = max(rect.height(), line_h)
                painter.drawText(QTY_X, y, max_qty_w, row_h, Qt.AlignCenter, f"{item.qty:.0f}")
                painter.drawText(PRICE_X, y, max_price_w, row_h, Qt.AlignRight, f"{item.price:,.2f}")
                painter.drawText(TOTAL_X, y, max_total_w, row_h, Qt.AlignRight, f"{item.amount:,.2f}")
                y += row_h + 6
                self._draw_dot_line(painter, self.margin, y, self.paper_width - self.margin * 2, ".")
                y += 12

            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 14

            # Totals section
            if y + 80 > page_height - self.page_break_threshold:
                printer.newPage()
                y = 0

            painter.setFont(normal_font)
            fm_n = painter.fontMetrics()
            n_line_h = fm_n.height() + 6

            def draw_so_total(label: str, value: float):
                nonlocal y
                text = f"{receipt.currency or 'USD'} {value:,.2f}"
                w = fm_n.horizontalAdvance(text)
                painter.drawText(self.margin, y, 260, n_line_h, Qt.AlignLeft, label)
                painter.drawText(self.paper_width - self.margin - w, y, w, n_line_h, Qt.AlignRight, text)
                y += n_line_h

            if receipt.multiCurrencyDetails:
                for detail in receipt.multiCurrencyDetails:
                    draw_so_total(detail.key, detail.value)
            else:
                draw_so_total("Order Total", receipt.grandTotal)

            y += 6

            if receipt.paymentMode:
                painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
                y += 14
                painter.setFont(normal_font)
                painter.drawText(self.margin, y, f"Payment Method : {receipt.paymentMode}")
                y += 26

            so_terms = getattr(receipt, "salesOrderTerms", "")
            if so_terms:
                y += 6
                painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
                y += 14

                # Check if terms fit
                if y + 80 > page_height - self.page_break_threshold:
                    printer.newPage()
                    y = 0

                painter.setFont(bold_font)
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 26,
                                  Qt.AlignLeft, "TERMS & CONDITIONS")
                y += 28

                painter.setFont(normal_font)
                fm_t = painter.fontMetrics()
                for term_line in so_terms.split("\n"):
                    term_line = term_line.strip()
                    if not term_line:
                        continue
                    rect = fm_t.boundingRect(0, 0, self.paper_width - self.margin * 2,
                                             1000, Qt.TextWordWrap, term_line)
                    
                    if y + rect.height() > page_height - self.page_break_threshold:
                        printer.newPage()
                        y = 0

                    painter.drawText(self.margin, y, self.paper_width - self.margin * 2,
                                     rect.height(), Qt.TextWordWrap, term_line)
                    y += rect.height() + 4

            y += 10
            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 14

            painter.setFont(normal_font)
            painter.drawText(self.margin, y, self.paper_width - self.margin*2, 30,
                             Qt.AlignCenter, receipt.footer or "Thank you for your business!")
            y += 30

            painter.end()
            return True

        except Exception as e:
            print(f"❌ Sales Order printing failed: {str(e)}")
            if painter and painter.isActive():
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


printing_service = PrintingService()