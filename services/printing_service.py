from models.receipt import ReceiptData
from models.advance_settings import AdvanceSettings
from PySide6.QtPrintSupport import QPrinter, QPrinterInfo
from PySide6.QtGui import QPainter, QFont, QFontMetrics, QPixmap, QColor
from PySide6.QtCore import Qt, QMarginsF, QSizeF
from PySide6.QtGui import QPageSize
from PySide6.QtWidgets import QMessageBox
from datetime import datetime
from pathlib import Path
from services.qr_print_service import get_qr_print_service
from services.fiscalization_service import get_fiscalization_service
import sys


# =============================================================================
# PATH HELPER
# =============================================================================
def _get_app_data_dir() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys.executable).parent / "app_data"
    return Path.cwd() / "app_data"


def _get_logo_path(logo_filename: str) -> Path:
    return _get_app_data_dir() / "logos" / logo_filename


# Color constants
DARK_TEXT = "#0d1f3c"
SUCCESS   = "#1a7a3c"
DANGER    = "#b02020"
ORANGE    = "#c05a00"


class PrintingService:
    def __init__(self):
        self.paper_width = 550
        self.margin = 10
        
    def _create_font(self, font_name: str, size: int, style: str) -> QFont:
        font = QFont(font_name if font_name else "Arial", size if size else 10)
        if style == "Bold":
            font.setBold(True)
        elif style == "Italic":
            font.setItalic(True)
        return font
    
    def _make_bold(self, font: QFont) -> QFont:
        bold_font = QFont(font)
        bold_font.setBold(True)
        return bold_font
    
    def _draw_logo(self, painter: QPainter, settings, y: int) -> int:
        try:
            logo_filename = getattr(settings, "logoFilename", None)
            if logo_filename:
                logo_path = _get_logo_path(logo_filename)
                if logo_path.exists():
                    pixmap = QPixmap(str(logo_path))
                    if not pixmap.isNull():
                        scaled_pixmap = pixmap.scaled(150, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        x = (self.paper_width - scaled_pixmap.width()) // 2
                        painter.drawPixmap(x, y, scaled_pixmap)
                        return y + scaled_pixmap.height() + 10
        except Exception as e:
            print(f"Logo draw error: {e}")
        return y
    
    def print_credit_note(self, receipt: ReceiptData, printer_name: str = None) -> bool:
        """Full credit note receipt with fiscal QR code support and waiting for fiscalization."""
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

            # Logo
            y = self._draw_logo(painter, settings, y)

            # Company Header
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

            # Heading
            painter.setFont(bold_font)
            painter.drawText(self.margin, y, self.paper_width - self.margin * 2, 44,
                             Qt.AlignCenter, "*** CREDIT NOTE ***")
            y += 60
            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 25

            # Document Details
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

            # Items Table
            painter.setFont(normal_font)
            fm: QFontMetrics = painter.fontMetrics()

            max_qty_w   = fm.horizontalAdvance("Qty")
            max_price_w = fm.horizontalAdvance("Price")
            max_total_w = fm.horizontalAdvance("Total")
            
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

            # Totals
            fm2  = painter.fontMetrics()
            lh2  = fm2.height() + 6

            def draw_cn_total(label: str, value: float, use_bold: bool = False):
                nonlocal y
                text = f"{receipt.currency or 'USD'} {value:,.2f}"
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

            # =========================================================================
            # FISCAL QR CODE SECTION FOR CREDIT NOTE
            # QR data is pre-resolved synchronously by main_window before printing
            # and injected into receipt.fiscal_qr_code / receipt.fiscal_verification_code.
            # No polling needed here.
            # =========================================================================
            try:
                fiscal_service = get_fiscalization_service()
                fiscal_enabled = fiscal_service.is_fiscalization_enabled() if fiscal_service else False
            except Exception as e:
                print(f"[PrintService] Error checking fiscal status: {e}")
                fiscal_enabled = False

            qr_code = (getattr(receipt, "fiscal_qr_code", "") or "").strip()
            v_code  = (getattr(receipt, "fiscal_verification_code", "") or "").strip()
            fiscal_ready = bool(qr_code)

            # Draw fiscal QR or pending message
            if fiscal_enabled and fiscal_ready and qr_code:
                try:
                    qr_service = get_qr_print_service()
                    qr_pixmap = qr_service.generate_qr_pixmap(qr_code, size=200)
                    if not qr_pixmap.isNull():
                        qr_x = (self.paper_width - qr_pixmap.width()) // 2
                        painter.drawPixmap(qr_x, y, qr_pixmap)
                        y += qr_pixmap.height() + 10

                        if v_code:
                            v_font = QFont(normal_font)
                            ps = normal_font.pointSize()
                            v_size = max(ps - 1, 8) if ps > 0 else max(normal_font.pixelSize() - 2, 8)
                            if ps > 0:
                                v_font.setPointSize(v_size)
                            else:
                                v_font.setPixelSize(v_size)
                            painter.setFont(v_font)
                            painter.drawText(self.margin, y, self.paper_width - self.margin * 2, 24,
                                             Qt.AlignCenter, f"Verification: {v_code}")
                            y += 30

                        painter.setFont(normal_font)
                        painter.drawText(self.margin, y, self.paper_width - self.margin * 2, 24,
                                         Qt.AlignCenter, "Scan QR code to verify with ZIMRA")
                        y += 40
                        painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
                        y += 20
                    else:
                        print(f"[PrintService] QR pixmap generation failed for credit note {receipt.invoiceNo}")
                except Exception as e:
                    print(f"[PrintService] Error drawing fiscal QR for credit note: {e}")
            elif fiscal_enabled and not fiscal_ready:
                # Placeholder QR + label + explanation. The image must
                # advance `y` before the label renders or the two overlap
                # on the slip (the original merged code missed that and
                # drew the text right on top of the pixmap).
                pixmap = QPixmap("assets/qr.png")
                if not pixmap.isNull():
                    painter.drawPixmap(
                        self.margin + (self.paper_width - self.margin * 2 - pixmap.width()) // 2,
                        y, pixmap,
                    )
                    y += pixmap.height() + 10
                painter.setFont(bold_font)
                painter.setPen(QColor(ORANGE))
                painter.drawText(self.margin, y, self.paper_width - self.margin * 2, 30,
                                 Qt.AlignCenter, "FISCALIZATION PENDING")
                y += 30
                painter.setFont(normal_font)
                painter.setPen(QColor(DARK_TEXT))
                painter.drawText(self.margin, y, self.paper_width - self.margin * 2, 24,
                                 Qt.AlignCenter,
                                 "Credit note will be re-issued once fiscalized")
                y += 40
                painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
                y += 20

            # Reason
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

            # Footer
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


# # Singleton instance
# printing_service = PrintingService()
    def print_shift_reconciliation(
        self,
        shift: dict = None,
        totals: list[dict] = None,
        cashier_id=None,
        printer_name: str = None,
        print_data: dict = None,
        reconciliation_data: dict = None,
    ) -> bool:
        """
        Prints the end-of-shift reconciliation report.
        """
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
            y = 10

            normal_font = self._create_font(settings.contentFontName, settings.contentFontSize, settings.contentFontStyle)
            bold_font   = self._make_bold(normal_font)
            small_font  = QFont(normal_font)
            
            # Robustly calculate small size (avoiding -1 for pixel-based fonts)
            base_size = normal_font.pointSize()
            if base_size < 1: 
                base_size = normal_font.pixelSize()
            
            new_size = max(base_size - 1, 8)
            if normal_font.pointSize() > 0:
                small_font.setPointSize(new_size)
            else:
                small_font.setPixelSize(new_size)

            # Logo
            y = self._draw_logo(painter, settings, y)

            # Company Name
            painter.setFont(bold_font)
            company = getattr(settings, "companyName", None) or "Havano POS"
            painter.drawText(self.margin, y, self.paper_width - self.margin * 2, 40,
                             Qt.AlignCenter, company.upper())
            y += 50

            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 20

            # Report Title
            painter.setFont(bold_font)
            painter.drawText(self.margin, y, self.paper_width - self.margin * 2, 36,
                             Qt.AlignCenter, "SHIFT RECONCILIATION REPORT")
            y += 44

            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 20

            # Shift Meta - use reconciliation_data first
            if reconciliation_data:
                shift_num = reconciliation_data.get('shift_number', '—')
                shift_date = reconciliation_data.get('date', datetime.now().strftime("%d/%m/%Y"))
                start_time = reconciliation_data.get('start_time', '—')
                end_time = reconciliation_data.get('end_time', datetime.now().strftime("%H:%M:%S"))
                closing_cashier = reconciliation_data.get('closing_cashier_name', '')
            elif print_data:
                shift_num = print_data.get('shift_number', '—')
                shift_date = print_data.get('date', datetime.now().strftime("%d/%m/%Y"))
                start_time = print_data.get('start_time', '—')
                end_time = print_data.get('end_time', datetime.now().strftime("%H:%M:%S"))
                closing_cashier = print_data.get('closing_cashier_name', '')
            else:
                shift_num = shift.get('shift_number', '—') if shift else '—'
                shift_date = shift.get('date', datetime.now().strftime("%d/%m/%Y")) if shift else datetime.now().strftime("%d/%m/%Y")
                start_time = shift.get('start_time', '—') if shift else '—'
                end_time = datetime.now().strftime("%H:%M:%S")
                closing_cashier = ''

            painter.setFont(normal_font)
            fm = painter.fontMetrics()
            line_h = fm.height() + 6

            def draw_meta(label: str, value: str):
                nonlocal y
                painter.setFont(bold_font)
                painter.drawText(self.margin, y, 140, line_h, Qt.AlignLeft, label)
                painter.setFont(normal_font)
                painter.drawText(self.margin + 140, y,
                                 self.paper_width - self.margin * 2 - 140, line_h,
                                 Qt.AlignLeft, value)
                y += line_h

            draw_meta("Shift #:", str(shift_num))
            draw_meta("Date:", str(shift_date))
            draw_meta("Started:", str(start_time))
            draw_meta("Closed:", str(end_time))
            if closing_cashier:
                draw_meta("Closed By:", str(closing_cashier))

            y += 6
            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 16

            # Column positions
            COL_METHOD = self.margin
            COL_EXP = self.margin + 130
            COL_ACTUAL = self.margin + 230
            COL_VAR = self.margin + 320
            COL_W = 75

            # Get data from reconciliation_data or print_data
            cashiers = []
            payment_methods = []
            grand_expected = 0.0
            grand_counted = 0.0
            
            if reconciliation_data:
                cashiers = reconciliation_data.get('cashiers', [])
                payment_methods = reconciliation_data.get('payment_methods', [])
                grand_expected = float(reconciliation_data.get('total_expected', 0))
                grand_counted = float(reconciliation_data.get('total_counted', 0))
            elif print_data:
                cashiers = print_data.get('cashiers', [])
                payment_methods = print_data.get('payment_methods', [])
                grand_expected = float(print_data.get('grand_expected', print_data.get('total_expected', 0)))
                grand_counted = float(print_data.get('grand_counted', print_data.get('total_counted', 0)))
            elif totals:
                for t in totals:
                    payment_methods.append({
                        'method': t.get('method'),
                        'expected': float(t.get('expected', 0)),
                        'counted': float(t.get('actual', 0)),
                        'variance': float(t.get('variance', 0))
                    })
                grand_expected = sum(float(t.get('expected', 0)) for t in totals)
                grand_counted = sum(float(t.get('actual', 0)) for t in totals)

            # Cashier Breakdown
            if cashiers:
                for cashier in cashiers:
                    cashier_name = cashier.get('cashier_name') or cashier.get('username', 'Unknown')
                    total_sales = float(cashier.get('total_sales', 0))
                    transactions = cashier.get('transaction_count', cashier.get('transactions', 0))

                    painter.setFont(bold_font)
                    painter.drawText(self.margin, y, self.paper_width - self.margin * 2, line_h,
                                     Qt.AlignLeft, f"CASHIER: {cashier_name.upper()}")
                    y += line_h + 4

                    painter.setFont(small_font)
                    painter.drawText(self.margin + 10, y, self.paper_width - self.margin * 2 - 10, line_h,
                                     Qt.AlignLeft, f"Sales: ${total_sales:,.2f} | Transactions: {transactions}")
                    y += line_h
                    y += 4

                    # Table headers
                    painter.setFont(bold_font)
                    painter.drawText(COL_METHOD, y, 120, line_h, Qt.AlignLeft, "Method")
                    painter.drawText(COL_EXP,    y, COL_W, line_h, Qt.AlignRight, "Expected")
                    painter.drawText(COL_ACTUAL, y, COL_W, line_h, Qt.AlignRight, "Counted")
                    painter.drawText(COL_VAR,    y, COL_W, line_h, Qt.AlignRight, "Variance")
                    y += line_h + 2

                    painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
                    y += 8

                    # "rows" is the primary key (set by _build_reconciliation_data).
                    # Fall back to "payment_breakdown" for any old saved JSON.
                    rows_to_print = cashier.get('rows') or cashier.get('payment_breakdown', [])

                    painter.setFont(normal_font)
                    if rows_to_print:
                        for row in rows_to_print:
                            method   = row.get('method', '')
                            expected = float(row.get('expected', 0))
                            counted  = float(row.get('counted',
                                             row.get('collected',
                                             row.get('amount_collected', 0))))
                            variance = counted - expected

                            display_method = method if len(method) <= 18 else method[:15] + "..."
                            
                            # Special styling for ON ACCOUNT
                            if method.upper() == "ON ACCOUNT":
                                painter.setPen(QColor(ORANGE))
                                painter.setFont(bold_font)
                            else:
                                painter.setPen(QColor(DARK_TEXT))
                                painter.setFont(normal_font)

                            painter.drawText(COL_METHOD, y, 120, line_h, Qt.AlignLeft, display_method)
                            painter.drawText(COL_EXP,    y, COL_W, line_h, Qt.AlignRight, f"{expected:,.2f}")
                            painter.drawText(COL_ACTUAL, y, COL_W, line_h, Qt.AlignRight, f"{counted:,.2f}")

                            variance_color = DANGER if variance < 0 else SUCCESS if variance > 0 else DARK_TEXT
                            old_color = painter.pen().color()
                            painter.setPen(QColor(variance_color))
                            painter.drawText(COL_VAR, y, COL_W, line_h, Qt.AlignRight, f"{variance:+,.2f}")
                            painter.setPen(old_color)
                            y += line_h + 2
                    else:
                        painter.setFont(small_font)
                        painter.drawText(self.margin + 10, y, self.paper_width - self.margin * 2, line_h,
                                         Qt.AlignLeft, "No payment methods recorded")
                        y += line_h + 2

                    y += 4

                    # Cashier sub-total
                    painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
                    y += 6

                    painter.setFont(bold_font)
                    total_exp = float(cashier.get('total_expected', 0))
                    total_cnt = float(cashier.get('total_counted', cashier.get('total_sales', 0)))
                    total_var = total_cnt - total_exp

                    painter.drawText(COL_METHOD, y, 120, line_h, Qt.AlignLeft, "SUB-TOTAL")
                    painter.drawText(COL_EXP,    y, COL_W, line_h, Qt.AlignRight, f"{total_exp:,.2f}")
                    painter.drawText(COL_ACTUAL, y, COL_W, line_h, Qt.AlignRight, f"{total_cnt:,.2f}")

                    variance_color = DANGER if total_var < 0 else SUCCESS if total_var > 0 else DARK_TEXT
                    old_color = painter.pen().color()
                    painter.setPen(QColor(variance_color))
                    painter.drawText(COL_VAR, y, COL_W, line_h, Qt.AlignRight, f"{total_var:+,.2f}")
                    painter.setPen(old_color)
                    y += line_h + 8

                    # Separator between cashiers
                    painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
                    y += 12

                    if y > 2500:
                        printer.newPage()
                        y = 20

            # Payment methods only (no cashier breakdown) - INCLUDING ON ACCOUNT
            if payment_methods:
                painter.setFont(bold_font)
                painter.drawText(COL_METHOD, y, 130, line_h, Qt.AlignLeft, "Method")
                painter.drawText(COL_EXP, y, COL_W, line_h, Qt.AlignRight, "Expected")
                painter.drawText(COL_ACTUAL, y, COL_W, line_h, Qt.AlignRight, "Counted")
                painter.drawText(COL_VAR, y, COL_W, line_h, Qt.AlignRight, "Variance")
                y += line_h + 4

                painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
                y += 10

                painter.setFont(normal_font)
                for pm in payment_methods:
                    method = pm.get('method', '')
                    expected = float(pm.get('expected', 0))
                    counted = float(pm.get('counted', pm.get('actual', 0)))
                    variance = counted - expected
                    
                    # Special styling for ON ACCOUNT
                    if method.upper() == "ON ACCOUNT":
                        painter.setPen(QColor(ORANGE))
                        painter.setFont(bold_font)
                    else:
                        painter.setPen(QColor(DARK_TEXT))
                        painter.setFont(normal_font)

                    painter.drawText(COL_METHOD, y, 130, line_h, Qt.AlignLeft, method)
                    painter.drawText(COL_EXP, y, COL_W, line_h, Qt.AlignRight, f"{expected:,.2f}")
                    painter.drawText(COL_ACTUAL, y, COL_W, line_h, Qt.AlignRight, f"{counted:,.2f}")
                    
                    variance_color = DANGER if variance < 0 else SUCCESS if variance > 0 else DARK_TEXT
                    old_color = painter.pen().color()
                    painter.setPen(QColor(variance_color))
                    painter.drawText(COL_VAR, y, COL_W, line_h, Qt.AlignRight, f"{variance:+,.2f}")
                    painter.setPen(old_color)
                    y += line_h + 4

                painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
                y += 10

                painter.setFont(bold_font)
                painter.drawText(COL_METHOD, y, 130, line_h, Qt.AlignLeft, "TOTAL")
                painter.drawText(COL_EXP, y, COL_W, line_h, Qt.AlignRight, f"{grand_expected:,.2f}")
                painter.drawText(COL_ACTUAL, y, COL_W, line_h, Qt.AlignRight, f"{grand_counted:,.2f}")

                grand_var = grand_counted - grand_expected
                variance_color = DANGER if grand_var < 0 else SUCCESS if grand_var > 0 else DARK_TEXT
                old_color = painter.pen().color()
                painter.setPen(QColor(variance_color))
                painter.drawText(COL_VAR, y, COL_W, line_h, Qt.AlignRight, f"{grand_var:+,.2f}")
                painter.setPen(old_color)
                y += line_h + 6

                painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
                y += 20

            # ─────────────────────────────────────────────────────────────
            # Invoice count — aggregate across all cashiers for this shift.
            # Sources, in order: reconciliation_data.total_invoices (if the
            # caller already computed it), sum of per-cashier transaction
            # counts, or a direct DB count keyed by shift id.
            # ─────────────────────────────────────────────────────────────
            invoice_count = self._resolve_shift_invoice_count(
                reconciliation_data=reconciliation_data,
                print_data=print_data,
                shift=shift,
                cashiers=cashiers,
            )
            if invoice_count is not None:
                painter.setFont(bold_font)
                painter.drawText(self.margin, y,
                                 self.paper_width - self.margin * 2, line_h,
                                 Qt.AlignCenter,
                                 f"Total Invoices: {invoice_count}")
                y += line_h + 10
                painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
                y += 10

            # Footer
            painter.setFont(normal_font)
            painter.drawText(self.margin, y, self.paper_width - self.margin * 2, 30,
                             Qt.AlignCenter, f"Printed: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
            y += 30
            painter.drawText(self.margin, y, self.paper_width - self.margin * 2, 24,
                             Qt.AlignCenter, "— End of Shift Report —")

            painter.end()
            print(f"✅ SHIFT RECONCILIATION printed → {printer_name or 'Default'}")
            return True

        except Exception as e:
            print(f"❌ Shift reconciliation print failed: {str(e)}")
            import traceback
            traceback.print_exc()
            if painter and painter.isActive():
                painter.end()
            QMessageBox.warning(None, "Print Failed", f"Shift report could not be printed:\n\n{e}")
            return False

    # =========================================================================
    # PAYMENT-CURRENCY HELPERS
    # =========================================================================
    def _sole_non_usd_payment_rate(
        self, payment_items: list,
    ) -> tuple[str, float, float, float]:
        """
        Single-non-USD-tender detection for the currency display rule.

        Returns (currency_code, rate, native_amount, usd_amount).
        All zeros + empty string when the heuristic doesn't apply:
        no payments, >1 payment row, or the sole row is USD.

        Rate is local-per-USD, derived from the payment item itself
        (`native / usd`) — same rate that was locked in at payment time,
        so totals and tendered stay internally consistent.

        Why return native_amount + usd_amount too:
        `PaymentDialog._active_method` stores tendered/change in NATIVE
        currency on the single-method path, while the splits path stores
        them in USD. The caller uses `native_amount` / `usd_amount` to
        work out which form a given receipt carries (by comparing to
        `receipt.amountTendered`) so we know whether to multiply by rate
        or display the value as-is.
        """
        if not payment_items or len(payment_items) != 1:
            return ("", 0.0, 0.0, 0.0)

        pi       = payment_items[0]
        cur      = (getattr(pi, "productid", "") or "USD").strip().upper()
        if not cur or cur == "USD":
            return ("", 0.0, 0.0, 0.0)

        try:
            native = float(getattr(pi, "price",  0) or 0)
            usd    = float(getattr(pi, "amount", 0) or 0)
        except (TypeError, ValueError):
            return ("", 0.0, 0.0, 0.0)
        if usd <= 0.005 or native <= 0.005:
            return ("", 0.0, 0.0, 0.0)

        return (cur, native / usd, native, usd)

    # =========================================================================
    # SHIFT INVOICE-COUNT HELPER
    # =========================================================================
    def _resolve_shift_invoice_count(
        self,
        reconciliation_data: dict | None,
        print_data:          dict | None,
        shift:               dict | None,
        cashiers:            list,
    ) -> int | None:
        """
        Best-effort invoice-count resolution for the shift summary print-out.

        Preference order:
          1. Explicit override in reconciliation/print_data (`total_invoices`).
          2. Sum of per-cashier `transaction_count` / `transactions` keys.
          3. Direct `COUNT(*)` on `sales` table keyed by shift id.
        Returns None only when every strategy fails — caller skips the line
        silently in that case.
        """
        # 1. Caller-supplied number (set by the reconciliation builder).
        for src in (reconciliation_data, print_data):
            if not src:
                continue
            n = src.get("total_invoices")
            if n is not None:
                try:
                    return int(n)
                except (TypeError, ValueError):
                    pass

        # 2. Sum from cashier breakdown.
        try:
            total = 0
            got_any = False
            for c in (cashiers or []):
                n = c.get("transaction_count", c.get("transactions"))
                if n is None:
                    continue
                got_any = True
                try:
                    total += int(n)
                except (TypeError, ValueError):
                    pass
            if got_any:
                return total
        except Exception:
            pass

        # 3. DB fallback — only if we have a shift id to key on.
        shift_id = None
        if shift and isinstance(shift, dict):
            shift_id = shift.get("id") or shift.get("shift_id")
        if shift_id:
            try:
                from database.db import get_connection
                conn = get_connection()
                cur  = conn.cursor()
                cur.execute(
                    "SELECT COUNT(*) FROM sales WHERE shift_id = ?",
                    (int(shift_id),),
                )
                row = cur.fetchone()
                conn.close()
                if row and row[0] is not None:
                    return int(row[0])
            except Exception as e:
                print(f"[print] invoice-count DB fallback failed: {e}")

        return None

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
    # LOGO HELPER
    # =========================================================================
    def _draw_logo(self, painter: QPainter, settings: AdvanceSettings, y: int) -> int:
        """
        Draws the logo if configured and the file exists.
        Returns the updated y position after the logo.
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
            return self.print_payment_receipt(receipt, printer_name=printer_name)
        if doc_type == "credit_note":
            return self.print_credit_note(receipt, printer_name=printer_name)
        return self.print_invoice_receipt(receipt, printer_name=printer_name)

    def reprint(self, receipt: ReceiptData, printer_name: str = None) -> bool:
        """Reprint any receipt — stamps a REPRINT banner."""
        receipt.is_reprint = True
        return self.print_receipt(receipt, printer_name=printer_name)

    # =========================================================================
    # KITCHEN ORDER TICKET (KOT)
    # =========================================================================
    def print_kitchen_order(self, receipt: ReceiptData, printer_name: str = None) -> bool:
        """
        Kitchen Order Ticket — prints only qty + item name grouped by station.
        Intentionally carries NO prices, tax, totals, payment or company block —
        it's a production slip, not a customer-facing receipt. Triggered from
        models/sale.print_kitchen_orders when kitchen_printing_enabled is True.
        """
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
            y = 20

            # Kitchen font sizes live on their own fields so a change to
            # the receipt's contentFontSize never re-scales the KOT. Fall
            # back to the old derived sizes on pre-migration AdvanceSettings
            # files so the first launch after an upgrade still prints sanely.
            kitchen_body_size   = int(getattr(settings, "kitchenBodySize", 0)
                                      or settings.contentFontSize or 10)
            kitchen_header_size = int(getattr(settings, "kitchenHeaderSize", 0)
                                      or (kitchen_body_size + 4))

            normal_font = self._create_font(settings.contentFontName,
                                            kitchen_body_size,
                                            settings.contentFontStyle)
            bold_font   = self._make_bold(normal_font)
            # Order-number header — large + bold so kitchen staff can read
            # it from across the bench. Independent of receipt header size.
            header_font = self._make_bold(self._create_font(
                settings.contentFontName,
                kitchen_header_size,
                settings.contentFontStyle,
            ))
            # Terminal tag at the footer — clamped to a small readable size
            # (~2pt below the body) so it doesn't compete with the header.
            small_font = self._create_font(settings.contentFontName,
                                           max(kitchen_body_size - 2, 6),
                                           settings.contentFontStyle)

            station = (getattr(receipt, "KOT", "") or "KITCHEN").strip() or "KITCHEN"
            order_no = int(getattr(receipt, "orderNumber", 0) or 0)

            # Order number is the KOT header (falls back to invoice no on pre-
            # migration rows where order_number = 0).
            painter.setFont(header_font)
            if order_no > 0:
                header_text = f"Order #{order_no}"
            else:
                header_text = f"Invoice: {receipt.invoiceNo or '—'}"
            painter.drawText(self.margin, y, self.paper_width - self.margin * 2, 40,
                             Qt.AlignCenter, header_text)
            y += 44

            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 22

            # Meta — invoice, cashier, time.
            # Invoice prints here (below the Order # header) when we have both,
            # so kitchen staff can still cross-reference the bar/till slip.
            painter.setFont(normal_font)
            if order_no > 0 and receipt.invoiceNo:
                painter.drawText(self.margin, y, self.paper_width - self.margin * 2, 26,
                                 Qt.AlignCenter, f"Invoice: {receipt.invoiceNo}")
                y += 28
            if receipt.cashierName:
                painter.drawText(self.margin, y, self.paper_width - self.margin * 2, 26,
                                 Qt.AlignCenter, f"Cashier: {receipt.cashierName}")
                y += 28
            painter.drawText(self.margin, y, self.paper_width - self.margin * 2, 26,
                             Qt.AlignCenter, f"Time: {datetime.now().strftime('%Y-%m-%d  %H:%M')}")
            y += 34

            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 20

            # Items — qty and product name only.  Grouped by product name so
            # multiple cart rows of the same dish merge into a single line.
            grouped: dict[str, float] = {}
            for it in receipt.items:
                name = (getattr(it, "productName", "") or "").strip() or "(item)"
                qty  = float(getattr(it, "qty", 1) or 1)
                grouped[name] = grouped.get(name, 0.0) + qty

            painter.setFont(bold_font)
            for name, qty in grouped.items():
                qty_txt = str(int(qty)) if qty == int(qty) else f"{qty:.2f}"
                line = f"{qty_txt:>4}  x  {name}"
                painter.drawText(self.margin, y, self.paper_width - self.margin * 2, 32,
                                 Qt.AlignLeft, line)
                y += 34

            y += 16
            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 24

            painter.setFont(normal_font)
            painter.drawText(self.margin, y, self.paper_width - self.margin * 2, 26,
                             Qt.AlignCenter, "— end of order —")
            y += 28

            # Terminal tag — small, footer-sized text under the end-of-order
            # line so kitchen staff see which printer/station the slip came
            # from when tearing it off, without competing with the header.
            painter.setFont(small_font)
            painter.drawText(self.margin, y, self.paper_width - self.margin * 2, 22,
                             Qt.AlignCenter, f"Terminal: {station}")

            painter.end()
            print(f"✅ KOT printed for {station} → {printer_name or 'Default'}")
            return True

        except Exception as e:
            print(f"❌ KOT print failed for {printer_name}: {e}")
            if painter and painter.isActive():
                painter.end()
            return False

    # =========================================================================
    # INVOICE RECEIPT
    # =========================================================================
    def print_invoice_receipt(self, receipt: ReceiptData, printer_name: str = None) -> bool:
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

            # Logo
            y = self._draw_logo(painter, settings, y)

            # Company Header
            painter.setFont(bold_font)
            painter.drawText(self.margin, y, self.paper_width - self.margin * 2, 40,
                             Qt.AlignCenter, (receipt.companyName or "Havano POS").upper())
            y += 60

            # Reprint Banner
            if getattr(receipt, "is_reprint", False):
                painter.setFont(bold_font)
                painter.drawText(self.margin, y, self.paper_width - self.margin * 2, 34,
                                 Qt.AlignCenter, "*** REPRINT ***")
                y += 40

            # Company Address
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

            # Receipt Heading — configurable via Company Settings → Receipt Header
            painter.setFont(bold_font)
            _heading = (getattr(receipt, "receiptHeader", "") or "").strip() or "*** SALES RECEIPT ***"
            painter.drawText(self.margin, y, self.paper_width - self.margin * 2, 44,
                             Qt.AlignCenter, _heading)
            y += 56
            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 25

            # Invoice Details
            painter.setFont(normal_font)
            _order_no = int(getattr(receipt, "orderNumber", 0) or 0)
            if _order_no > 0:
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 30,
                                 Qt.AlignCenter, f"Order   : #{_order_no}")
                y += 30
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

            # Items Table
            painter.setFont(normal_font)
            fm: QFontMetrics = painter.fontMetrics()

            max_qty_w   = fm.horizontalAdvance("Qty")
            max_price_w = fm.horizontalAdvance("Price")
            max_total_w = fm.horizontalAdvance("Total")
            
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
            painter.drawText(self.margin, y, QTY_X - self.margin, 24, Qt.AlignLeft, "Item")
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

            # Totals
            painter.setFont(normal_font)
            fm = painter.fontMetrics()
            line_h = fm.height() + 6

            def draw_total(label: str, value: float, currency: str = None):
                nonlocal y
                _cur = (currency or receipt.currency or "USD")
                text = f"{_cur} {value:,.2f}"
                w = fm.horizontalAdvance(text)
                painter.drawText(self.margin, y, 260, line_h, Qt.AlignLeft,  label)
                painter.drawText(self.paper_width - self.margin - w, y, w, line_h, Qt.AlignRight, text)
                y += line_h

            # Amount BEFORE tax — reverse calculation off the tax-inclusive total.
            # Subtotal + VAT lines are fiscalisation-only — when fiscalisation is
            # off the slip is not a tax invoice, so only the GRAND TOTAL matters.
            _grand = float(receipt.grandTotal or 0)
            _vat   = float(receipt.totalVat   or 0)
            _net   = max(_grand - _vat, 0.0)
            try:
                _fiscal_on = bool(get_fiscalization_service()
                                  and get_fiscalization_service().is_fiscalization_enabled())
            except Exception:
                _fiscal_on = False

            # Currency-display rule: when the sale was paid with exactly
            # ONE non-USD tender, render the whole totals block + tendered
            # + change in that native currency so the triplet stays
            # internally consistent (a USD grand total next to a ZWG
            # tendered looks broken). Multi-method or mixed currencies
            # keep USD — "real" native totals are ambiguous.
            #
            # The fiscal record itself is still stored in USD upstream;
            # this only affects the printed display.
            pay_cur, pay_rate, pay_native, pay_usd = \
                self._sole_non_usd_payment_rate(
                    getattr(receipt, "paymentItems", None) or []
                )
            _display_cur  = pay_cur or "USD"
            _display_rate = pay_rate if (pay_cur and pay_rate > 0) else 1.0

            # Grand total / subtotal / VAT are ALWAYS stored in USD
            # (sales.total / sales.subtotal / sales.total_vat are base
            # currency). Multiply to display.
            if _fiscal_on:
                draw_total("Subtotal (excl. tax)",
                           _net * _display_rate, _display_cur)
                if _vat > 0:
                    draw_total("VAT",
                               _vat * _display_rate, _display_cur)

            painter.setFont(bold_font)
            draw_total("GRAND TOTAL",
                       _grand * _display_rate, _display_cur)
            painter.setFont(normal_font)

            y += 10

            # Amount tendered + change — trickier: PaymentDialog stores
            # these as NATIVE on single-method non-USD sales but as USD on
            # split payments. If `receipt.amountTendered` looks closer to
            # the payment row's native amount than its USD equivalent,
            # assume the values are already native and display them as-is
            # (no rate multiplication — that would double-convert).
            _tendered_base = float(getattr(receipt, "amountTendered", 0) or 0)
            _change_base   = float(getattr(receipt, "change",         0) or 0)

            tendered_is_already_native = False
            if pay_cur and pay_native > 0 and pay_usd > 0 and _tendered_base > 0:
                _dist_native = abs(_tendered_base - pay_native)
                _dist_usd    = abs(_tendered_base - pay_usd)
                tendered_is_already_native = _dist_native < _dist_usd

            if _tendered_base > 0.005:
                if pay_cur and tendered_is_already_native:
                    # Already in the display currency — skip the multiply.
                    draw_total("Amount Tendered", _tendered_base, _display_cur)
                    draw_total("Change",          _change_base,   _display_cur)
                else:
                    draw_total("Amount Tendered",
                               _tendered_base * _display_rate, _display_cur)
                    draw_total("Change",
                               _change_base   * _display_rate, _display_cur)

            # Payment Details — modes + amounts per currency.
            # paymentItems is populated by _print_receipt; each carries
            #   productName = MOP name
            #   productid   = native currency code
            #   price       = native amount
            #   amount      = USD base equivalent
            payment_items = getattr(receipt, "paymentItems", None) or []
            if payment_items:
                y += 10
                painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
                y += 14

                painter.setFont(bold_font)
                painter.drawText(self.margin, y, self.paper_width - self.margin * 2, line_h,
                                 Qt.AlignLeft, "PAYMENT DETAILS")
                y += line_h + 4

                painter.setFont(normal_font)
                for _pi in payment_items:
                    method_name = (getattr(_pi, "productName", "") or "").strip() or "PAYMENT"
                    native_cur  = (getattr(_pi, "productid",   "") or "USD").strip().upper()
                    native_amt  = float(getattr(_pi, "price",  0) or 0)
                    usd_amt     = float(getattr(_pi, "amount", 0) or 0)

                    # "<Method>                     <NATIVE> 123.00"
                    right_text = f"{native_cur} {native_amt:,.2f}"
                    w = fm.horizontalAdvance(right_text)
                    painter.drawText(self.margin, y, 260, line_h, Qt.AlignLeft, method_name)
                    painter.drawText(self.paper_width - self.margin - w, y, w, line_h,
                                     Qt.AlignRight, right_text)
                    y += line_h

                    # # Show USD equivalent on its own line when native != USD
                    # if native_cur != "USD" and usd_amt > 0.005:
                    #     eq_text = f"(= USD {usd_amt:,.2f})"
                    #     w2 = fm.horizontalAdvance(eq_text)
                    #     painter.drawText(self.paper_width - self.margin - w2, y, w2, line_h,
                    #                      Qt.AlignRight, eq_text)
                    #     y += line_h

            y += 20

            # =========================================================================
            # FISCAL QR CODE SECTION
            # Always do a fresh DB lookup right before drawing — the receipt object
            # may have been built before fiscalization completed, so receipt.qrCode
            # is unreliable.  The DB is the only source of truth at print time.
            # =========================================================================
            fiscal_service = get_fiscalization_service()
            fiscal_enabled = fiscal_service.is_fiscalization_enabled() if fiscal_service else False

            if fiscal_enabled:
                # Fresh lookup by invoice number — never trust the receipt object here
                qr_code  = ""
                v_code   = ""
                try:
                    from database.db import get_connection
                    _conn = get_connection()
                    _cur  = _conn.cursor()
                    _cur.execute(
                        "SELECT fiscal_qr_code, fiscal_verification_code "
                        "FROM sales WHERE invoice_no = ?",
                        (receipt.invoiceNo,)
                    )
                    _row = _cur.fetchone()
                    _conn.close()
                    if _row:
                        qr_code = (_row[0] or "").strip()
                        v_code  = (_row[1] or "").strip()
                except Exception as _e:
                    print(f"[PrintService] DB fiscal lookup failed: {_e}")
                    # Fall back to whatever was set on the receipt object
                    qr_code = (getattr(receipt, "qrCode", "") or "").strip()
                    v_code  = (getattr(receipt, "vCode",  "") or "").strip()

                if qr_code:
                    try:
                        qr_service = get_qr_print_service()
                        qr_pixmap  = qr_service.generate_qr_pixmap(qr_code, size=200)
                        if not qr_pixmap.isNull():
                            qr_x = (self.paper_width - qr_pixmap.width()) // 2
                            painter.drawPixmap(qr_x, y, qr_pixmap)
                            y += qr_pixmap.height() + 10

                            if v_code:
                                v_font = QFont(normal_font)
                                ps = normal_font.pointSize()
                                v_size = max(ps - 1, 8) if ps > 0 else max(normal_font.pixelSize() - 2, 8)
                                if ps > 0:
                                    v_font.setPointSize(v_size)
                                else:
                                    v_font.setPixelSize(v_size)
                                painter.setFont(v_font)
                                painter.drawText(self.margin, y, self.paper_width - self.margin * 2, 24,
                                                 Qt.AlignCenter, f"Verification: {v_code}")
                                y += 30

                            painter.setFont(normal_font)
                            painter.drawText(self.margin, y, self.paper_width - self.margin * 2, 24,
                                             Qt.AlignCenter, "Scan QR code to verify with ZIMRA")
                            y += 40
                            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
                            y += 20
                        else:
                            print(f"[PrintService] QR pixmap generation failed for invoice {receipt.invoiceNo}")
                    except Exception as e:
                        print(f"[PrintService] Error drawing fiscal QR: {e}")
                else:
                    # Fiscalization enabled but QR not in DB yet — already
                    # waited upstream. We show three things in this case:
                    #   1. A placeholder QR image (assets/qr.png) so the
                    #      receipt visually resembles a fiscalised slip
                    #      even without the real code yet.
                    #   2. A clear "NOT FISCALIZED" label so staff don't
                    #      mistake the placeholder for a live QR.
                    #   3. A small note explaining that the receipt will
                    #      be re-issued once fiscalisation succeeds.
                    y += 20
                    pixmap = QPixmap("assets/qr.png")
                    if not pixmap.isNull():
                        painter.drawPixmap(
                            self.margin + (self.paper_width - self.margin * 2 - pixmap.width()) // 2,
                            y, pixmap,
                        )
                        y += pixmap.height() + 10
                    painter.setFont(bold_font)
                    painter.setPen(QColor(ORANGE))
                    painter.drawText(self.margin, y, self.paper_width - self.margin * 2, 28,
                                     Qt.AlignCenter, "FISCALIZATION PENDING")
                    y += 28
                    painter.setFont(normal_font)
                    painter.setPen(QColor(DARK_TEXT))
                    painter.drawText(self.margin, y, self.paper_width - self.margin * 2, 22,
                                     Qt.AlignCenter,
                                     "Receipt will be re-issued once fiscalized")
                    y += 30
                    painter.drawLine(self.margin, y,
                                     self.paper_width - self.margin, y)
                    y += 14


            # Footer — fully user-configurable via Company Defaults → Footer Text.
            # Multi-line values are rendered as separate centered lines so the
            # user can put "Thank you for your purchase!" / "Come again soon!"
            # / anything else in the settings instead of shipping a hardcoded
            # second line.
            painter.setFont(normal_font)
            _footer_raw = (receipt.footer or "Thank you for your purchase!").strip()
            for _line in _footer_raw.splitlines():
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 22,
                                 Qt.AlignCenter, _line)
                y += 22

            painter.end()
            print(f"✅ INVOICE printed successfully → {printer_name or 'Default'}")
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
    def print_payment_receipt(self, receipt: ReceiptData, printer_name: str = None) -> bool:
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
            now = datetime.now()

            # Logo
            y = self._draw_logo(painter, settings, y)

            # Company Details
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

            # Heading
            painter.setFont(bold_font)
            painter.drawText(self.margin, y, self.paper_width - self.margin * 2, 44,
                             Qt.AlignCenter, "*** PAYMENT RECEIPT ***")
            y += 60
            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 25

            # Payment Details
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

            # Laybye Deposit Section
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

            # Forms of Payment
            fm = painter.fontMetrics()
            line_h = fm.height() + 10

            painter.setFont(bold_font)
            painter.drawText(self.margin, y, self.paper_width - self.margin*2, line_h,
                             Qt.AlignLeft, "Forms of Payment")
            y += line_h + 4

            painter.setFont(normal_font)

            receipt_splits = getattr(receipt, "splits", None) or []
            if isinstance(receipt_splits, str):
                import json as _json
                try:
                    receipt_splits = _json.loads(receipt_splits)
                except Exception:
                    receipt_splits = []

            if receipt_splits:
                for s in receipt_splits:
                    method_name  = s.get("method", "Payment")
                    curr         = s.get("currency", "USD")
                    amt          = float(s.get("amount", 0))
                    method_value = f"{curr}  {amt:,.2f}"
                    w = fm.horizontalAdvance(method_value)
                    painter.drawText(self.margin, y, self.paper_width - self.margin*2 - w - 4,
                                     line_h, Qt.AlignLeft, method_name)
                    painter.drawText(self.paper_width - self.margin - w, y, w,
                                     line_h, Qt.AlignRight, method_value)
                    y += line_h
            else:
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

            # Amount Paid
            painter.setFont(bold_font)
            amount_text = f"{receipt.total:,.2f}"
            w = fm.horizontalAdvance(amount_text)
            painter.drawText(self.margin, y, 300, line_h, Qt.AlignLeft, "Amount Paid")
            painter.drawText(self.paper_width - self.margin - w, y, w, line_h, Qt.AlignRight, amount_text)
            y += line_h + 4

            # Customer Balance
            painter.setFont(normal_font)
            balance = getattr(receipt, "balanceDue", 0.0) or 0.0
            balance_text = f"{balance:,.2f}"
            w2 = fm.horizontalAdvance(balance_text)
            painter.drawText(self.margin, y, 300, line_h, Qt.AlignLeft, "Customer Balance")
            painter.drawText(self.paper_width - self.margin - w2, y, w2, line_h, Qt.AlignRight, balance_text)
            y += line_h + 10

            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 20

            # Footer
            painter.setFont(normal_font)
            painter.drawText(self.margin, y, self.paper_width - self.margin*2, 30,
                             Qt.AlignCenter, receipt.footer or "Thank you for your payment!")
            y += 30

            painter.end()
            print(f"✅ PAYMENT RECEIPT printed successfully → {printer_name or 'Default'}")
            return True

        except Exception as e:
            print(f"❌ Payment receipt printing failed: {str(e)}")
            if painter and painter.isActive():
                painter.end()
            QMessageBox.warning(None, "Print Failed", f"Payment receipt could not be printed:\n\n{e}")
            return False

    # =========================================================================
    # SALES ORDER RECEIPT
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

            # Logo
            y = self._draw_logo(painter, settings, y)

            # Company Header
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

            # Document Heading
            painter.setFont(bold_font)
            doc_heading = f"*** {(receipt.receiptType or 'SALES ORDER').upper()} ***"
            painter.drawText(self.margin, y, self.paper_width - self.margin * 2, 44,
                             Qt.AlignCenter, doc_heading)
            y += 60

            # Order Meta
            painter.setFont(normal_font)
            painter.drawText(self.margin, y, self.paper_width - self.margin*2, 28,
                             Qt.AlignCenter, f"Order No  :  {receipt.invoiceNo or 'N/A'}")
            y += 32

            order_date = receipt.invoiceDate or datetime.now().strftime("%Y-%m-%d")
            painter.drawText(self.margin, y, self.paper_width - self.margin*2, 28,
                             Qt.AlignCenter, f"Order Date  :  {order_date}")
            y += 32

            painter.drawText(self.margin, y, self.paper_width - self.margin*2, 28,
                             Qt.AlignCenter, f"Order Time  :  {datetime.now().strftime('%H:%M:%S')}")
            y += 32

            delivery_date = getattr(receipt, "deliveryDate", "")
            if delivery_date:
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 28,
                                 Qt.AlignCenter, f"Delivery  :  {delivery_date}")
                y += 32

            if receipt.customerName:
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 28,
                                 Qt.AlignCenter, f"Customer  :  {receipt.customerName}")
                y += 32

            if receipt.customerContact:
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, 28,
                                 Qt.AlignCenter, f"Contact  :  {receipt.customerContact}")
                y += 32

            y += 8
            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 20

            # Items Table
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

            # Order Summary
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

            # Forms of Payment
            payment_items = getattr(receipt, "paymentItems", None) or []

            if payment_items:
                painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
                y += 14
                painter.setFont(bold_font)
                painter.drawText(self.margin, y, self.paper_width - self.margin*2, n_line_h,
                                 Qt.AlignLeft, "Forms of Payment")
                y += n_line_h + 4

                painter.setFont(normal_font)
                fm_p = painter.fontMetrics()
                lh_p = fm_p.height() + 8
                for pm in payment_items:
                    method_name  = pm.productName or "Payment"
                    method_value = f"{pm.amount:,.2f}"
                    w = fm_p.horizontalAdvance(method_value)
                    painter.drawText(self.margin, y,
                                     self.paper_width - self.margin*2 - w - 4,
                                     lh_p, Qt.AlignLeft, method_name)
                    painter.drawText(self.paper_width - self.margin - w, y,
                                     w, lh_p, Qt.AlignRight, method_value)
                    y += lh_p
                y += 6

            # Footer
            painter.setFont(normal_font)
            painter.drawText(self.margin, y, self.paper_width - self.margin*2, 30,
                             Qt.AlignCenter, receipt.footer or "Thank you for your business!")
            y += 30

            painter.end()
            print(f"✅ SALES ORDER printed successfully → {printer_name or 'Default'}")
            return True

        except Exception as e:
            print(f"❌ Sales Order printing failed: {str(e)}")
            if painter and painter.isActive():
                painter.end()
            QMessageBox.warning(None, "Print Failed", f"Sales order could not be printed:\n\n{e}")
            return False

    # =========================================================================
    # CREDIT NOTE
    # =========================================================================
    
    # =========================================================================
    # LAYBYE DEPOSIT (from order_id)
    # =========================================================================
    def print_laybye_deposit(self, order_id, printer_name: str = None) -> bool:
        """Fetches the sales order by ID and prints a deposit receipt."""
        settings = AdvanceSettings.load_from_file()

        painter = None
        try:
            from models.sales_order import get_order_by_id
            order = get_order_by_id(order_id)
            if not order:
                print(f"⚠️  print_laybye_deposit: order {order_id} not found")
                return False

            printer = QPrinter(QPrinter.HighResolution)
            if printer_name and printer_name != "(None)":
                info = QPrinterInfo.printerInfo(printer_name)
                if not info.isNull():
                    printer.setPrinterName(printer_name)

            printer.setPageSize(QPageSize(QSizeF(80, 2000), QPageSize.Millimeter))
            printer.setPageMargins(QMarginsF(0, 0, 0, 0))

            painter = QPainter(printer)
            y = 10

            normal_font = self._create_font(settings.contentFontName, settings.contentFontSize, settings.contentFontStyle)
            bold_font   = self._make_bold(normal_font)

            # Logo
            y = self._draw_logo(painter, settings, y)

            # Company Name
            painter.setFont(bold_font)
            company = getattr(settings, "companyName", None) or "Havano POS"
            painter.drawText(self.margin, y, self.paper_width - self.margin * 2, 40,
                             Qt.AlignCenter, company.upper())
            y += 50

            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 20

            # Title
            painter.setFont(bold_font)
            painter.drawText(self.margin, y, self.paper_width - self.margin * 2, 36,
                             Qt.AlignCenter, "*** LAYBYE RECEIPT ***")
            y += 44

            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 20

            # Order Meta
            painter.setFont(normal_font)
            fm     = painter.fontMetrics()
            line_h = fm.height() + 6

            def draw_meta(label: str, value: str):
                nonlocal y
                painter.setFont(bold_font)
                painter.drawText(self.margin, y, 160, line_h, Qt.AlignLeft, label)
                painter.setFont(normal_font)
                painter.drawText(self.margin + 160, y,
                                 self.paper_width - self.margin * 2 - 160,
                                 line_h, Qt.AlignLeft, str(value or "—"))
                y += line_h

            draw_meta("Order #:",    str(order.get("id", order_id)))
            draw_meta("Date:",       str(order.get("date", datetime.now().strftime("%d/%m/%Y"))))
            draw_meta("Time:",       datetime.now().strftime("%H:%M:%S"))
            draw_meta("Customer:",   str(order.get("customer_name", order.get("customer", "—"))))
            draw_meta("Delivery:",   str(order.get("delivery_date", "—")))

            y += 6
            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 16

            # Items
            painter.setFont(bold_font)
            TOTAL_X = self.paper_width - self.margin - 80
            painter.drawText(self.margin, y, TOTAL_X - self.margin - 10, line_h, Qt.AlignLeft,  "Item")
            painter.drawText(TOTAL_X,    y, 80,                          line_h, Qt.AlignRight, "Amount")
            y += line_h + 4

            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 10

            painter.setFont(normal_font)
            items = order.get("items", order.get("cart_items", []))
            for item in items:
                name   = item.get("item_name", item.get("product_name", ""))
                qty    = item.get("qty", 1)
                amount = item.get("amount", item.get("total", 0.0))
                label  = f"{qty} × {name}"
                painter.drawText(self.margin, y, TOTAL_X - self.margin - 10, line_h, Qt.AlignLeft,  label)
                painter.drawText(TOTAL_X,    y, 80,                          line_h, Qt.AlignRight, f"{float(amount):,.2f}")
                y += line_h + 4

            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 14

            # Totals
            def draw_total(label: str, value: float, use_bold: bool = False):
                nonlocal y
                text = f"{value:,.2f}"
                w    = fm.horizontalAdvance(text)
                painter.setFont(bold_font if use_bold else normal_font)
                painter.drawText(self.margin, y, 220, line_h, Qt.AlignLeft,  label)
                painter.drawText(self.paper_width - self.margin - w, y, w, line_h, Qt.AlignRight, text)
                y += line_h

            order_total = float(order.get("total", 0.0))
            deposit     = float(order.get("deposit_amount", 0.0))
            balance     = order_total - deposit

            draw_total("Order Total:", order_total, use_bold=True)

            # Forms of Payment
            raw_methods   = order.get("deposit_methods") or []
            single_method = order.get("deposit_method", "") or ""

            y += 4
            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 8
            painter.setFont(bold_font)
            painter.drawText(self.margin, y, self.paper_width - self.margin*2, line_h,
                             Qt.AlignLeft, "Forms of Payment")
            y += line_h + 2

            painter.setFont(normal_font)
            if raw_methods:
                for pm in raw_methods:
                    m_name   = str(pm.get("method", "Payment"))
                    m_amount = float(pm.get("amount", 0.0))
                    m_text   = f"{m_amount:,.2f}"
                    w        = fm.horizontalAdvance(m_text)
                    painter.drawText(self.margin, y, self.paper_width - self.margin*2 - w - 4,
                                     line_h, Qt.AlignLeft, m_name)
                    painter.drawText(self.paper_width - self.margin - w, y, w,
                                     line_h, Qt.AlignRight, m_text)
                    y += line_h + 2
            elif single_method:
                dep_text = f"{deposit:,.2f}"
                w        = fm.horizontalAdvance(dep_text)
                painter.drawText(self.margin, y, self.paper_width - self.margin*2 - w - 4,
                                 line_h, Qt.AlignLeft, single_method)
                painter.drawText(self.paper_width - self.margin - w, y, w,
                                 line_h, Qt.AlignRight, dep_text)
                y += line_h + 2

            y += 4
            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 8
            draw_total("Balance Due:", balance, use_bold=True)

            y += 16
            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)
            y += 20

            # Footer
            painter.setFont(normal_font)
            painter.drawText(self.margin, y, self.paper_width - self.margin * 2, 30,
                             Qt.AlignCenter, "Thank you for your laybye!")
            y += 28
            painter.drawText(self.margin, y, self.paper_width - self.margin * 2, 24,
                             Qt.AlignCenter, f"Printed: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

            painter.end()
            print(f"✅ LAYBYE DEPOSIT printed → Order #{order_id}")
            return True

        except Exception as e:
            print(f"❌ Laybye deposit print failed: {str(e)}")
            if painter and painter.isActive():
                painter.end()
            QMessageBox.warning(None, "Print Failed", f"Laybye receipt could not be printed:\n\n{e}")
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
    # =========================================================================
    @property
    def _SYNC_FILE(self) -> Path:
        return _get_app_data_dir() / "offline_sync.json"

    def get_next_sync_number(self) -> int:
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
    # =========================================================================
    @staticmethod
    def cart_has_items(cart_items: list) -> bool:
        if not cart_items:
            return False
        return any((getattr(i, "qty", 0) or 0) > 0 for i in cart_items)


# Singleton instance
printing_service = PrintingService()


def print_laybye_deposit(order_id, printer_name: str = None) -> bool:
    """Module-level shim for laybye deposit printing."""
    return printing_service.print_laybye_deposit(order_id, printer_name=printer_name)