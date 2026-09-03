from models.receipt import ReceiptData
from models.advance_settings import AdvanceSettings
from PySide6.QtPrintSupport import QPrinter, QPrinterInfo
from PySide6.QtGui import QPainter, QFont, QFontMetrics, QPixmap
from PySide6.QtCore import Qt, QMarginsF, QSizeF
from PySide6.QtGui import QPageSize
from PySide6.QtWidgets import QMessageBox
from datetime import datetime
from pathlib import Path
import sys


# =============================================================================
# PATH HELPER — works in both dev (python main.py) and PyInstaller .exe
# =============================================================================
def _get_app_data_dir() -> Path:
    """
    Always returns the 'app_data' folder next to the running executable/script.

    - PyInstaller one-file .exe  → folder that contains HavanoPOS.exe
    - Dev (python main.py)       → current working directory (project root)
    """
    if hasattr(sys, "_MEIPASS"):
        # Running as a bundled .exe — use the folder containing the .exe
        return Path(sys.executable).parent / "app_data"
    return Path.cwd() / "app_data"


def _get_logo_path(logo_filename: str) -> Path:
    """Returns the full path to a logo file inside app_data/logos/."""
    return _get_app_data_dir() / "logos" / logo_filename


class PrintingService:
    def __init__(self):
        self.paper_width = 550
        self.margin = 10

    # =========================================================================
    # KITCHEN ORDER
    # =========================================================================
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
                             Qt.AlignCenter, f"Time : {datetime.now().strftime('%H:%M:%S')}")
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
            QMessageBox.warning(None, "Print Failed", f"Kitchen order could not be printed:\n\n{e}")
            return False

    # =========================================================================
    # FONT HELPERS
    # =========================================================================
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

    # =========================================================================
    # LOGO HELPER  (shared by all print methods)
    # =========================================================================
    def _draw_logo(self, painter: QPainter, settings: AdvanceSettings, y: int) -> int:
        """
        Draws the logo if configured and the file exists.
        Returns the updated y position after the logo (or the same y if no logo drawn).
        """
        if settings.logoDirectory:
            logo_full_path = _get_logo_path(settings.logoDirectory)
            if logo_full_path.exists():
                logo_pix = QPixmap(str(logo_full_path))
                if not logo_pix.isNull():
                    scaled = logo_pix.scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    x = (self.paper_width - scaled.width()) // 2
                    painter.drawPixmap(x, y, scaled)
                    y += scaled.height() + 10
        return y

    # =========================================================================
    # ROUTING
    # =========================================================================
    def print_receipt(self, receipt: ReceiptData, printer_name: str = None) -> bool:
        """Main entry point — routes to the correct template by doc_type."""
        doc_type = getattr(receipt, "doc_type", "receipt")
        if doc_type == "sales_order":
            return self.print_sales_order_receipt(receipt, printer_name=printer_name)
        if doc_type == "payment":
            return self._print_payment_receipt(receipt, printer_name=printer_name)
        if doc_type == "credit_note":
            return self._print_credit_note(receipt, printer_name=printer_name)
        return self._print_invoice_receipt(receipt, printer_name=printer_name)

    def reprint(self, receipt: ReceiptData, printer_name: str = None) -> bool:
        """Reprint any receipt — stamps a REPRINT banner then delegates to the
        correct full template so nothing is lost."""
        receipt.is_reprint = True
        return self.print_receipt(receipt, printer_name=printer_name)

    # =========================================================================
    # INVOICE RECEIPT
    # =========================================================================
    def _print_invoice_receipt(self, receipt: ReceiptData, printer_name: str = None) -> bool:
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
            bold_font   = self._make_bold(normal_font)

            # ── LOGO ──────────────────────────────────────────────────────────
            y = self._draw_logo(painter, settings, y)

            # ── COMPANY HEADER ────────────────────────────────────────────────
            painter.setFont(bold_font)
            painter.drawText(self.margin, y, self.paper_width - self.margin * 2, 40,
                             Qt.AlignCenter, (receipt.companyName or "Havano POS").upper())
            y += 60

            # ── REPRINT BANNER ────────────────────────────────────────────────
            if getattr(receipt, "is_reprint", False):
                painter.setFont(bold_font)
                painter.drawText(self.margin, y, self.paper_width - self.margin * 2, 34,
                                 Qt.AlignCenter, "*** REPRINT ***")
                y += 40

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

            # ── RECEIPT HEADING ───────────────────────────────────────────────
            painter.setFont(bold_font)
            painter.drawText(self.margin, y, self.paper_width - self.margin * 2, 44,
                             Qt.AlignCenter, "***SALES RECEIPT ***")
            y += 56

            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 25

            # ── INVOICE DETAILS ───────────────────────────────────────────────
            painter.setFont(normal_font)
            painter.drawText(self.margin, y, self.paper_width - self.margin*2, 30, Qt.AlignCenter, f"Invoice : {receipt.invoiceNo or 'N/A'}")
            y += 30
            _raw_date = str(receipt.invoiceDate or "").split(" ")[0].split("T")[0]
            try:
                _display_date = datetime.strptime(_raw_date, "%Y-%m-%d").strftime("%d/%m/%Y") if _raw_date else datetime.now().strftime("%d/%m/%Y")
            except ValueError:
                _display_date = _raw_date or datetime.now().strftime("%d/%m/%Y")
            painter.drawText(self.margin, y, self.paper_width - self.margin*2, 30, Qt.AlignCenter, f"Date    : {_display_date}")
            y += 30
            painter.drawText(self.margin, y, self.paper_width - self.margin*2, 30, Qt.AlignCenter, f"Time    : {datetime.now().strftime('%H:%M:%S')}")
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

            # ── ITEMS TABLE ───────────────────────────────────────────────────
            painter.setFont(normal_font)
            fm: QFontMetrics = painter.fontMetrics()

            max_qty_w   = fm.horizontalAdvance("Qty")
            max_price_w = fm.horizontalAdvance("Price")
            max_total_w = fm.horizontalAdvance("Total")
            for item in receipt.items:
                max_qty_w   = max(max_qty_w,   fm.horizontalAdvance(f"{item.qty:.0f}"))
                max_price_w = max(max_price_w, fm.horizontalAdvance(f"{item.price:,.2f}"))
                max_total_w = max(max_total_w, fm.horizontalAdvance(f"{item.amount:,.2f}"))
            max_qty_w += 10; max_price_w += 14; max_total_w += 14

            TOTAL_X = self.paper_width - self.margin - max_total_w
            PRICE_X = TOTAL_X - max_price_w - 10
            QTY_X   = PRICE_X - max_qty_w - 10

            painter.setFont(bold_font)
            painter.drawText(QTY_X,   y, max_qty_w,   24, Qt.AlignCenter, "Qty")
            painter.drawText(PRICE_X, y, max_price_w, 24, Qt.AlignRight,  "Price")
            painter.drawText(TOTAL_X, y, max_total_w, 24, Qt.AlignRight,  "Total")
            y += 40
            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 24

            painter.setFont(normal_font)
            line_h = fm.height() + 6
            for item in receipt.items:
                name = item.productName or ""
                rect = fm.boundingRect(0, 0, self.paper_width - self.margin * 2, 1000, Qt.TextWordWrap, name)
                painter.drawText(self.margin, y, self.paper_width - self.margin * 2, rect.height(), Qt.TextWordWrap, name)
                y += rect.height() + 4
                painter.drawText(QTY_X,   y, max_qty_w,   line_h, Qt.AlignCenter, f"{item.qty:.0f}")
                painter.drawText(PRICE_X, y, max_price_w, line_h, Qt.AlignRight,  f"{item.price:,.2f}")
                painter.drawText(TOTAL_X, y, max_total_w, line_h, Qt.AlignRight,  f"{item.amount:,.2f}")
                y += line_h + 8
                self._draw_dot_line(painter, self.margin, y, self.paper_width - self.margin * 2, ".")
                y += 14

            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 14

            # ── TOTALS ────────────────────────────────────────────────────────
            painter.setFont(normal_font)
            fm = painter.fontMetrics()
            line_h = fm.height() + 6

            def draw_total(label: str, value: float):
                nonlocal y
                text = f"{value:,.2f}"
                w = fm.horizontalAdvance(text)
                painter.drawText(self.margin, y, 200, line_h, Qt.AlignLeft,  label)
                painter.drawText(self.paper_width - self.margin - w, y, w, line_h, Qt.AlignRight, text)
                y += line_h

            if receipt.totalVat > 0:
                draw_total("VAT", receipt.totalVat)
            painter.setFont(bold_font)
            draw_total("GRAND TOTAL", receipt.grandTotal)
            painter.setFont(normal_font)
            y += 6
            draw_total("Paid", receipt.amountTendered)
            draw_total("Change", receipt.change)

            y += 20

            painter.setFont(normal_font)
            painter.drawText(self.margin, y, self.paper_width - self.margin*2, 30,
                             Qt.AlignCenter, receipt.footer or "Thank you for your purchase!")
            y += 26
            painter.drawText(self.margin, y, self.paper_width - self.margin*2, 20,
                             Qt.AlignCenter, "Come again soon!")

            painter.end()
            return True

        except Exception as e:
            print(f"❌ Printing failed: {str(e)}")
            if painter and painter.isActive():
                painter.end()
            QMessageBox.warning(None, "Print Failed", f"Invoice receipt could not be printed:\n\n{e}")
            return False

    # =========================================================================
    # PAYMENT RECEIPT
    # =========================================================================
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
            bold_font   = self._make_bold(normal_font)

            # Capture print time once so Date and Time lines are always consistent
            now = datetime.now()

            # ── LOGO ──────────────────────────────────────────────────────────
            y = self._draw_logo(painter, settings, y)

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
                             Qt.AlignCenter, f"Date      :  {receipt.invoiceDate or now.strftime('%d/%m/%Y')}")
            y += 32
            painter.drawText(self.margin, y, self.paper_width - self.margin*2, 28,
                             Qt.AlignCenter, f"Time      :  {now.strftime('%H:%M:%S')}")
            y += 32
            painter.drawText(self.margin, y, self.paper_width - self.margin*2, 28,
                             Qt.AlignCenter, f"Customer  :  {receipt.customerName or 'Walk-in'}")
            y += 32

            y += 8
            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 20

            # ── LAYBYE DEPOSIT SECTION ────────────────────────────────────────
            is_laybye = getattr(receipt, "is_laybye_deposit", False)
            if is_laybye:
                laybye_ref = getattr(receipt, "laybye_ref", "") or ""
                painter.setFont(bold_font)
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 28,
                                 Qt.AlignCenter, "LAYBYE DEPOSIT")
                y += 32
                if laybye_ref:
                    painter.setFont(normal_font)
                    painter.drawText(self.margin, y, self.paper_width - self.margin*2, 28,
                                     Qt.AlignCenter, f"Laybye Ref  :  {laybye_ref}")
                    y += 32
                y += 4
                painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
                y += 20

            # ── FORMS OF PAYMENT ──────────────────────────────────────────────
            fm = painter.fontMetrics()
            line_h = fm.height() + 10

            painter.setFont(bold_font)
            painter.drawText(self.margin, y, self.paper_width - self.margin*2, line_h,
                             Qt.AlignLeft, "Forms of Payment")
            y += line_h + 4

            painter.setFont(normal_font)
            items = receipt.items or []
            for item in items:
                method_name  = item.productName or "Payment"
                method_value = f"{item.amount:,.2f}"
                w = fm.horizontalAdvance(method_value)
                painter.drawText(self.margin, y, self.paper_width - self.margin*2 - w - 4,
                                 line_h, Qt.AlignLeft, method_name)
                painter.drawText(self.paper_width - self.margin - w, y, w,
                                 line_h, Qt.AlignRight, method_value)
                y += line_h

            y += 8
            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 14

            # ── AMOUNT PAID ───────────────────────────────────────────────────
            painter.setFont(bold_font)
            amount_text = f"{receipt.total:,.2f}"
            w = fm.horizontalAdvance(amount_text)
            painter.drawText(self.margin, y, 300, line_h, Qt.AlignLeft, "Amount Paid")
            painter.drawText(self.paper_width - self.margin - w, y, w, line_h, Qt.AlignRight, amount_text)
            y += line_h + 4

            # ── CUSTOMER BALANCE ──────────────────────────────────────────────
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
            QMessageBox.warning(None, "Print Failed", f"Payment receipt could not be printed:\n\n{e}")
            return False

    # =========================================================================
    # SALES ORDER / LAYBYE RECEIPT
    # =========================================================================
    def print_sales_order_receipt(self, receipt: ReceiptData, printer_name: str = None) -> bool:
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
            bold_font   = self._make_bold(normal_font)

            # ── LOGO ──────────────────────────────────────────────────────────
            y = self._draw_logo(painter, settings, y)

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

            time_text = f"Order Time  :  {datetime.now().strftime('%H:%M:%S')}"
            painter.drawText(self.margin, y, self.paper_width - self.margin*2, 28, Qt.AlignCenter, time_text)
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

            painter.setFont(normal_font)
            fm: QFontMetrics = painter.fontMetrics()

            max_qty_w   = fm.horizontalAdvance("Qty")
            max_price_w = fm.horizontalAdvance("Price")
            max_total_w = fm.horizontalAdvance("Amount")

            for item in receipt.items:
                max_qty_w   = max(max_qty_w,   fm.horizontalAdvance(f"{item.qty:.0f}"))
                max_price_w = max(max_price_w, fm.horizontalAdvance(f"{item.price:,.2f}"))
                max_total_w = max(max_total_w, fm.horizontalAdvance(f"{item.amount:,.2f}"))

            max_qty_w += 10
            max_price_w += 14
            max_total_w += 14

            TOTAL_X = self.paper_width - self.margin - max_total_w
            PRICE_X = TOTAL_X - max_price_w - 10
            QTY_X   = PRICE_X - max_qty_w - 10

            painter.setFont(bold_font)
            painter.drawText(self.margin, y, QTY_X - self.margin, 24, Qt.AlignLeft,   "Item")
            painter.drawText(QTY_X,       y, max_qty_w,           24, Qt.AlignCenter, "Qty")
            painter.drawText(PRICE_X,     y, max_price_w,         24, Qt.AlignRight,  "Price")
            painter.drawText(TOTAL_X,     y, max_total_w,         24, Qt.AlignRight,  "Amount")
            y += 30
            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 18

            painter.setFont(normal_font)
            line_h = fm.height() + 6

            for item in receipt.items:
                name   = item.productName or ""
                name_w = QTY_X - self.margin - 6
                rect   = fm.boundingRect(0, 0, name_w, 1000, Qt.TextWordWrap, name)
                painter.drawText(self.margin, y, name_w, rect.height(), Qt.TextWordWrap, name)
                row_h = max(rect.height(), line_h)

                painter.drawText(QTY_X,   y, max_qty_w,   row_h, Qt.AlignCenter, f"{item.qty:.0f}")
                painter.drawText(PRICE_X, y, max_price_w, row_h, Qt.AlignRight,  f"{item.price:,.2f}")
                painter.drawText(TOTAL_X, y, max_total_w, row_h, Qt.AlignRight,  f"{item.amount:,.2f}")

                y += row_h + 6
                self._draw_dot_line(painter, self.margin, y, self.paper_width - self.margin * 2, ".")
                y += 12

            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 14

            painter.setFont(normal_font)
            fm_n     = painter.fontMetrics()
            n_line_h = fm_n.height() + 6

            def draw_so_total(label: str, value: float):
                nonlocal y
                text = f"{receipt.currency or 'USD'} {value:,.2f}"
                w = fm_n.horizontalAdvance(text)
                painter.drawText(self.margin, y, 260, n_line_h, Qt.AlignLeft,  label)
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
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 28, Qt.AlignLeft, f"Payment Method : {receipt.paymentMode}")
                y += 26

            so_terms = getattr(receipt, "salesOrderTerms", "")
            if not so_terms:
                try:
                    from models.company_defaults import get_defaults
                    so_terms = get_defaults().get("terms_and_conditions", "")
                except Exception:
                    so_terms = ""
            if so_terms:
                y += 6
                painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
                y += 14

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
                    painter.drawText(self.margin, y,
                                     self.paper_width - self.margin * 2,
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
            QMessageBox.warning(None, "Print Failed", f"Sales order could not be printed:\n\n{e}")
            return False

    # =========================================================================
    # CREDIT NOTE  (full template — mirrors invoice with CREDIT NOTE heading)
    # =========================================================================
    def _print_credit_note(self, receipt: ReceiptData, printer_name: str = None) -> bool:
        """Full credit note receipt."""
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

            now = datetime.now()
            normal_font = self._create_font(settings.contentFontName, settings.contentFontSize, settings.contentFontStyle)
            bold_font   = self._make_bold(normal_font)

            # ── LOGO ──────────────────────────────────────────────────────────
            y = self._draw_logo(painter, settings, y)

            # ── COMPANY HEADER ────────────────────────────────────────────────
            painter.setFont(bold_font)
            painter.drawText(self.margin, y, self.paper_width - self.margin * 2, 40,
                             Qt.AlignCenter, (receipt.companyName or "Havano POS").upper())
            y += 60

            painter.setFont(normal_font)
            for line in [receipt.companyAddress, receipt.companyAddressLine1, receipt.companyAddressLine2]:
                if line:
                    painter.drawText(self.margin, y, self.paper_width - self.margin*2, 22, Qt.AlignCenter, line)
                    y += 28
            city_state = f"{receipt.city} {receipt.state} {receipt.postcode}".strip()
            if city_state:
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 22, Qt.AlignCenter, city_state)
                y += 28
            if receipt.tel:
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 22, Qt.AlignCenter, f"Tel: {receipt.tel}")
                y += 28
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
                             Qt.AlignCenter, "*** CREDIT NOTE ***")
            y += 60

            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 25

            # ── DOCUMENT DETAILS ──────────────────────────────────────────────
            painter.setFont(normal_font)
            painter.drawText(self.margin, y, self.paper_width - self.margin*2, 28,
                             Qt.AlignCenter, f"Credit Note No  :  {receipt.invoiceNo or 'N/A'}")
            y += 32
            orig_inv = getattr(receipt, "originalInvoiceNo", "") or ""
            if orig_inv:
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 28,
                                 Qt.AlignCenter, f"Orig. Invoice   :  {orig_inv}")
                y += 32
            _raw_date = str(receipt.invoiceDate or "").split(" ")[0].split("T")[0]
            try:
                _display_date = datetime.strptime(_raw_date, "%Y-%m-%d").strftime("%d/%m/%Y") if _raw_date else now.strftime("%d/%m/%Y")
            except ValueError:
                _display_date = _raw_date or now.strftime("%d/%m/%Y")
            painter.drawText(self.margin, y, self.paper_width - self.margin*2, 28,
                             Qt.AlignCenter, f"Date            :  {_display_date}")
            y += 32
            painter.drawText(self.margin, y, self.paper_width - self.margin*2, 28,
                             Qt.AlignCenter, f"Time            :  {now.strftime('%H:%M:%S')}")
            y += 32
            painter.drawText(self.margin, y, self.paper_width - self.margin*2, 28,
                             Qt.AlignCenter, f"Cashier         :  {receipt.cashierName or 'Admin'}")
            y += 32
            if receipt.customerName:
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 28,
                                 Qt.AlignCenter, f"Customer        :  {receipt.customerName}")
                y += 32
            if receipt.customerContact:
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 28,
                                 Qt.AlignCenter, f"Contact         :  {receipt.customerContact}")
                y += 32

            y += 8
            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 24

            # ── ITEMS TABLE ───────────────────────────────────────────────────
            painter.setFont(normal_font)
            fm: QFontMetrics = painter.fontMetrics()

            max_qty_w   = fm.horizontalAdvance("Qty")
            max_price_w = fm.horizontalAdvance("Price")
            max_total_w = fm.horizontalAdvance("Total")
            for item in receipt.items:
                max_qty_w   = max(max_qty_w,   fm.horizontalAdvance(f"{item.qty:.0f}"))
                max_price_w = max(max_price_w, fm.horizontalAdvance(f"{item.price:,.2f}"))
                max_total_w = max(max_total_w, fm.horizontalAdvance(f"{item.amount:,.2f}"))
            max_qty_w += 10; max_price_w += 14; max_total_w += 14

            TOTAL_X = self.paper_width - self.margin - max_total_w
            PRICE_X = TOTAL_X - max_price_w - 10
            QTY_X   = PRICE_X - max_qty_w - 10

            painter.setFont(bold_font)
            painter.drawText(self.margin, y, QTY_X - self.margin, 24, Qt.AlignLeft,   "Item (Returned)")
            painter.drawText(QTY_X,       y, max_qty_w,           24, Qt.AlignCenter, "Qty")
            painter.drawText(PRICE_X,     y, max_price_w,         24, Qt.AlignRight,  "Price")
            painter.drawText(TOTAL_X,     y, max_total_w,         24, Qt.AlignRight,  "Total")
            y += 30
            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 24

            painter.setFont(normal_font)
            line_h = fm.height() + 6
            for item in receipt.items:
                name   = item.productName or ""
                name_w = QTY_X - self.margin - 6
                rect   = fm.boundingRect(0, 0, name_w, 1000, Qt.TextWordWrap, name)
                painter.drawText(self.margin, y, name_w, rect.height(), Qt.TextWordWrap, name)
                row_h  = max(rect.height(), line_h)
                painter.drawText(QTY_X,   y, max_qty_w,   row_h, Qt.AlignCenter, f"{item.qty:.0f}")
                painter.drawText(PRICE_X, y, max_price_w, row_h, Qt.AlignRight,  f"{item.price:,.2f}")
                painter.drawText(TOTAL_X, y, max_total_w, row_h, Qt.AlignRight,  f"{item.amount:,.2f}")
                y += row_h + 6
                self._draw_dot_line(painter, self.margin, y, self.paper_width - self.margin * 2, ".")
                y += 12

            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 14

            # ── TOTALS ────────────────────────────────────────────────────────
            fm2  = painter.fontMetrics()
            lh2  = fm2.height() + 6

            def draw_cn_total(label: str, value: float, use_bold: bool = False):
                nonlocal y
                text = f"{value:,.2f}"
                w = fm2.horizontalAdvance(text)
                painter.setFont(bold_font if use_bold else normal_font)
                painter.drawText(self.margin, y, 220, lh2, Qt.AlignLeft,  label)
                painter.drawText(self.paper_width - self.margin - w, y, w, lh2, Qt.AlignRight, text)
                y += lh2

            if receipt.totalVat > 0:
                draw_cn_total("VAT", receipt.totalVat)
            draw_cn_total("CREDIT TOTAL", receipt.grandTotal, use_bold=True)

            y += 14
            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 20

            # ── REASON ────────────────────────────────────────────────────────
            cn_reason = getattr(receipt, "creditNoteReason", "") or ""
            if cn_reason:
                painter.setFont(bold_font)
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 24, Qt.AlignLeft, "Reason:")
                y += 26
                painter.setFont(normal_font)
                fm_r = painter.fontMetrics()
                for rline in cn_reason.split("\n"):
                    rline = rline.strip()
                    if not rline:
                        continue
                    rr = fm_r.boundingRect(0, 0, self.paper_width - self.margin*2, 1000, Qt.TextWordWrap, rline)
                    painter.drawText(self.margin, y, self.paper_width - self.margin*2,
                                     rr.height(), Qt.TextWordWrap, rline)
                    y += rr.height() + 4
                y += 10
                painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
                y += 14

            # ── FOOTER ────────────────────────────────────────────────────────
            painter.setFont(normal_font)
            painter.drawText(self.margin, y, self.paper_width - self.margin*2, 30,
                             Qt.AlignCenter, receipt.footer or "Credit note issued. Thank you.")
            y += 30

            painter.end()
            print(f"✅ CREDIT NOTE printed successfully → {printer_name or 'Default'}")
            return True

        except Exception as e:
            print(f"❌ Credit note printing failed: {str(e)}")
            if painter and painter.isActive():
                painter.end()
            QMessageBox.warning(None, "Print Failed", f"Credit note could not be printed:\n\n{e}")
            return False

    # =========================================================================
    # DRAW HELPERS
    # =========================================================================
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
        except Exception:
            return ["(None)", "Default Printer"]

    # =========================================================================
    # OFFLINE SYNC COUNTER
    # Persists to app_data/offline_sync.json — increments every transaction
    # so the sync number keeps rising even without a server round-trip.
    # =========================================================================
    @property
    def _SYNC_FILE(self) -> Path:
        """Always resolves next to the .exe (or cwd in dev)."""
        return _get_app_data_dir() / "offline_sync.json"

    def get_next_sync_number(self) -> int:
        """Read, increment, persist, and return the next offline sync number."""
        import json as _json
        try:
            self._SYNC_FILE.parent.mkdir(parents=True, exist_ok=True)
            current = 0
            if self._SYNC_FILE.exists():
                try:
                    data = _json.loads(self._SYNC_FILE.read_text(encoding="utf-8"))
                    current = int(data.get("sync_no", 0))
                except Exception:
                    current = 0
            next_no = current + 1
            self._SYNC_FILE.write_text(
                _json.dumps({"sync_no": next_no}, indent=2), encoding="utf-8"
            )
            return next_no
        except Exception as e:
            print(f"⚠️  Could not update offline sync counter: {e}")
            return 0

    def peek_sync_number(self) -> int:
        """Return the current sync number without incrementing (for display)."""
        import json as _json
        try:
            if self._SYNC_FILE.exists():
                data = _json.loads(self._SYNC_FILE.read_text(encoding="utf-8"))
                return int(data.get("sync_no", 0))
        except Exception:
            pass
        return 0

    # =========================================================================
    # LAYBYE CART GUARD
    # Call before opening the laybye/sales-order flow.
    # =========================================================================
    @staticmethod
    def cart_has_items(cart_items: list) -> bool:
        """Return True when the cart contains at least one row with qty > 0."""
        if not cart_items:
            return False
        return any((getattr(i, "qty", 0) or 0) > 0 for i in cart_items)


printing_service = PrintingService()