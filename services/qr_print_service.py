# # services/qr_print_service.py
# """
# Standalone QR Code printing service for fiscal receipts.
# Completely decoupled from the main printing service.
# """

# from PySide6.QtPrintSupport import QPrinter, QPrinterInfo
# from PySide6.QtGui import QPainter, QFont, QColor, QPixmap, QPageSize
# from PySide6.QtCore import Qt, QMarginsF, QSizeF, QByteArray
# from PySide6.QtWidgets import QMessageBox
# from pathlib import Path
# import sys
# try:
#     import qrcode
# except ImportError:
#     qrcode = None

# from io import BytesIO
# from datetime import datetime
# import logging

# log = logging.getLogger("QRPrintService")

# # Colors
# NAVY = "#0d1f3c"
# WHITE = "#ffffff"
# DARK_TEXT = "#0d1f3c"
# SUCCESS = "#1a7a3c"
# BORDER = "#c8d8ec"

# # Paper settings
# PAPER_WIDTH_MM = 80
# PAPER_HEIGHT_MM = 200
# MARGIN_MM = 2


# def _get_app_data_dir() -> Path:
#     if hasattr(sys, "_MEIPASS"):
#         return Path(sys.executable).parent / "app_data"
#     return Path.cwd() / "app_data"


# def _get_logo_path() -> Path:
#     return _get_app_data_dir() / "logos" / "logo.png"


# class QRPrintService:
#     """
#     Standalone service for printing fiscal QR codes.
#     Can be used independently without affecting main receipt printing.
#     """
    
#     def __init__(self):
#         self._paper_width_pt = None
#         self._margin_pt = None
#         self._setup_printer_units()
    
#     def _setup_printer_units(self):
#         """Setup printer units based on standard 80mm thermal printer"""
#         try:
#             test_printer = QPrinter(QPrinter.HighResolution)
#             mm_to_pt = test_printer.logicalDpiX() / 25.4
#             self._paper_width_pt = PAPER_WIDTH_MM * mm_to_pt
#             self._margin_pt = MARGIN_MM * mm_to_pt
#         except Exception:
#             self._paper_width_pt = 226  # Approx 80mm at 72dpi
#             self._margin_pt = 5
    
#     def get_available_printers(self) -> list[str]:
#         """Get list of available printers"""
#         try:
#             return [p.printerName() for p in QPrinterInfo.availablePrinters()]
#         except Exception:
#             return []
    
#     def generate_qr_pixmap(self, qr_url: str, size: int = 200) -> QPixmap:
#         """
#         Generate a QPixmap from a QR code URL.
        
#         Args:
#             qr_url: The URL or text to encode in QR code
#             size: Size of the QR code in pixels
        
#         Returns:
#             QPixmap of the QR code
#         """
#         if qrcode is None:
#             log.error("QR Code generation failed: 'qrcode' module not installed.")
#             return QPixmap()

#         try:
#             # Generate QR code
#             qr = qrcode.QRCode(
#                 version=2,
#                 error_correction=qrcode.constants.ERROR_CORRECT_L,
#                 box_size=4,
#                 border=2,
#             )
#             qr.add_data(qr_url)
#             qr.make(fit=True)
            
#             # Create image
#             qr_image = qr.make_image(fill_color="black", back_color="white")
            
#             # Convert to bytes
#             buffer = BytesIO()
#             qr_image.save(buffer, format="PNG")
#             buffer.seek(0)
            
#             # Create QPixmap from bytes
#             pixmap = QPixmap()
#             pixmap.loadFromData(buffer.getvalue(), "PNG")
            
#             # Scale to desired size
#             scaled = pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
#             return scaled
            
#         except Exception as e:
#             log.error(f"Failed to generate QR code: {e}")
#             return QPixmap()
    
#     def print_fiscal_qr(
#         self,
#         qr_url: str,
#         invoice_number: str = "",
#         verification_code: str = "",
#         printer_name: str = None,
#         show_preview: bool = False,
#     ) -> bool:
#         """
#         Print a fiscal QR code receipt.
        
#         Args:
#             qr_url: The QR code URL from ZIMRA
#             invoice_number: Invoice number for reference
#             verification_code: Verification code from ZIMRA
#             printer_name: Name of printer to use (None = default)
#             show_preview: If True, shows a preview dialog instead of printing
        
#         Returns:
#             True if successful, False otherwise
#         """
#         painter = None
#         try:
#             # Setup printer
#             printer = QPrinter(QPrinter.HighResolution)
#             if printer_name and printer_name != "(None)":
#                 info = QPrinterInfo.printerInfo(printer_name)
#                 if not info.isNull():
#                     printer.setPrinterName(printer_name)
            
#             # Set page size for thermal receipt
#             printer.setPageSize(QPageSize(QSizeF(PAPER_WIDTH_MM, PAPER_HEIGHT_MM), QPageSize.Millimeter))
#             printer.setFullPage(True)
#             printer.setPageMargins(QMarginsF(0, 0, 0, 0))
            
#             if show_preview:
#                 printer.setOutputFormat(QPrinter.NativeFormat)
            
#             painter = QPainter(printer)
            
#             # Draw the receipt
#             self._draw_fiscal_qr_receipt(painter, qr_url, invoice_number, verification_code)
#             painter.end()
            
#             log.info(f"✅ Fiscal QR printed successfully → {printer_name or 'Default'}")
#             return True
            
#         except Exception as e:
#             log.error(f"❌ Fiscal QR printing failed: {e}")
#             if painter and painter.isActive():
#                 painter.end()
            
#             if not show_preview:
#                 QMessageBox.warning(
#                     None, 
#                     "Print Failed", 
#                     f"Fiscal QR code could not be printed:\n\n{e}"
#                 )
#             return False
    
#     def preview_fiscal_qr(
#         self,
#         qr_url: str,
#         invoice_number: str = "",
#         verification_code: str = "",
#     ) -> bool:
#         """
#         Show a preview of the fiscal QR receipt before printing.
        
#         Returns:
#             True if user confirmed print, False otherwise
#         """
#         from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
        
#         # Create preview dialog
#         preview = QDialog()
#         preview.setWindowTitle("Fiscal QR Code Preview")
#         preview.setMinimumSize(400, 600)
#         preview.setModal(True)
        
#         layout = QVBoxLayout(preview)
        
#         # Generate QR pixmap
#         qr_pixmap = self.generate_qr_pixmap(qr_url, size=250)
        
#         # QR Code label
#         qr_label = QLabel()
#         qr_label.setPixmap(qr_pixmap)
#         qr_label.setAlignment(Qt.AlignCenter)
#         layout.addWidget(qr_label)
        
#         # Invoice info
#         info_label = QLabel()
#         info_label.setText(
#             f"Invoice: {invoice_number}\n"
#             f"Verification: {verification_code}\n"
#             f"\nScan QR code to verify with ZIMRA"
#         )
#         info_label.setAlignment(Qt.AlignCenter)
#         info_label.setStyleSheet("font-size: 12px; padding: 10px;")
#         layout.addWidget(info_label)
        
#         # Buttons
#         btn_layout = QHBoxLayout()
#         print_btn = QPushButton("Print")
#         print_btn.setStyleSheet(f"""
#             QPushButton {{
#                 background-color: {SUCCESS};
#                 color: white;
#                 border: none;
#                 border-radius: 5px;
#                 padding: 10px 20px;
#                 font-weight: bold;
#             }}
#             QPushButton:hover {{ background-color: #1f9447; }}
#         """)
#         cancel_btn = QPushButton("Cancel")
#         cancel_btn.setStyleSheet(f"""
#             QPushButton {{
#                 background-color: {NAVY};
#                 color: white;
#                 border: none;
#                 border-radius: 5px;
#                 padding: 10px 20px;
#             }}
#             QPushButton:hover {{ background-color: #162d52; }}
#         """)
        
#         btn_layout.addWidget(print_btn)
#         btn_layout.addWidget(cancel_btn)
#         layout.addLayout(btn_layout)
        
#         print_btn.clicked.connect(preview.accept)
#         cancel_btn.clicked.connect(preview.reject)
        
#         return preview.exec() == QDialog.Accepted
    
#     def _draw_fiscal_qr_receipt(self, painter: QPainter, qr_url: str, invoice_number: str, verification_code: str):
#         """
#         Draw the fiscal QR receipt on the painter.
#         """
#         # Get settings
#         from models.advance_settings import AdvanceSettings
#         settings = AdvanceSettings.load_from_file()
        
#         # Setup fonts
#         normal_font = self._create_font(settings.contentFontName, settings.contentFontSize, settings.contentFontStyle)
#         bold_font = self._make_bold(normal_font)
#         small_font = QFont(normal_font)
        
#         # Robustly calculate small size (avoiding -1 for pixel-based fonts)
#         # QFont.pointSize() returns -1 if size is in pixels.
#         base_size = normal_font.pointSize()
#         if base_size < 1: 
#             base_size = normal_font.pixelSize()
        
#         new_size = max(base_size - 1, 8)
#         if normal_font.pointSize() > 0:
#             small_font.setPointSize(new_size)
#         else:
#             small_font.setPixelSize(new_size)
        
#         painter.setFont(normal_font)
        
#         # Get paper width in pixels
#         paper_width = painter.device().width()
#         margin = int(paper_width * 0.05)  # 5% margin
#         content_width = paper_width - (margin * 2)
        
#         y = margin
        
#         # Draw logo if exists
#         y = self._draw_logo(painter, margin, y, content_width)
        
#         # Company name
#         painter.setFont(bold_font)
#         company = getattr(settings, "companyName", None) or "Havano POS"
#         painter.drawText(margin, y, content_width, 40, Qt.AlignCenter, company.upper())
#         y += 50
        
#         # Divider
#         painter.drawLine(margin, y, paper_width - margin, y)
#         y += 15
        
#         # Title
#         painter.setFont(bold_font)
#         painter.drawText(margin, y, content_width, 35, Qt.AlignCenter, "*** FISCAL RECEIPT ***")
#         y += 45
        
#         # Divider
#         painter.drawLine(margin, y, paper_width - margin, y)
#         y += 15
        
#         # Invoice info
#         painter.setFont(normal_font)
#         fm = painter.fontMetrics()
#         line_height = fm.height() + 5
        
#         painter.drawText(margin, y, content_width, line_height, Qt.AlignLeft, f"Invoice: {invoice_number}")
#         y += line_height
        
#         painter.drawText(margin, y, content_width, line_height, Qt.AlignLeft, f"Verification: {verification_code}")
#         y += line_height + 10
        
#         # Draw QR Code
#         qr_pixmap = self.generate_qr_pixmap(qr_url, size=180)
#         if not qr_pixmap.isNull():
#             qr_x = (paper_width - qr_pixmap.width()) // 2
#             painter.drawPixmap(qr_x, y, qr_pixmap)
#             y += qr_pixmap.height() + 15
        
#         # QR Code hint
#         painter.setFont(small_font)
#         painter.drawText(margin, y, content_width, 20, Qt.AlignCenter, "Scan QR code to verify with ZIMRA")
#         y += 30
        
#         # Divider
#         painter.drawLine(margin, y, paper_width - margin, y)
#         y += 15
        
#         # Footer
#         painter.setFont(small_font)
#         now = datetime.now()
#         painter.drawText(margin, y, content_width, 20, Qt.AlignCenter, f"Printed: {now.strftime('%d/%m/%Y %H:%M:%S')}")
#         y += 25
        
#         painter.drawText(margin, y, content_width, 20, Qt.AlignCenter, "Thank you for your purchase!")
#         y += 20
    
#     def _draw_logo(self, painter: QPainter, margin: int, y: int, content_width: int) -> int:
#         """Draw company logo if exists"""
#         logo_path = _get_logo_path()
#         if logo_path.exists():
#             pixmap = QPixmap(str(logo_path))
#             if not pixmap.isNull():
#                 scaled = pixmap.scaled(120, 50, Qt.KeepAspectRatio, Qt.SmoothTransformation)
#                 x = margin + (content_width - scaled.width()) // 2
#                 painter.drawPixmap(x, y, scaled)
#                 return y + scaled.height() + 10
#         return y
    
#     def _create_font(self, family: str, size: int, style_str: str = "Regular") -> QFont:
#         """Create a QFont with given parameters"""
#         font = QFont(family or "Arial", max(size or 10, 8))
#         style_lower = style_str.strip().lower()
#         is_bold = any(w in style_lower for w in ["bold", "heavy", "black"])
#         is_italic = any(w in style_lower for w in ["italic", "oblique"])
#         font.setWeight(QFont.Bold if is_bold else QFont.Normal)
#         font.setItalic(is_italic)
#         return font

#     def _make_bold(self, font: QFont) -> QFont:
#         """Return a copy of font with Bold weight forced on."""
#         f = QFont(font)
#         f.setWeight(QFont.Bold)
#         return f


# # Singleton instance
# _qr_print_service = None


# def get_qr_print_service() -> QRPrintService:
#     """Get the singleton QR print service instance"""
#     global _qr_print_service
#     if _qr_print_service is None:
#         _qr_print_service = QRPrintService()
#     return _qr_print_service


# def print_fiscal_qr(
#     qr_url: str,
#     invoice_number: str = "",
#     verification_code: str = "",
#     printer_name: str = None,
#     show_preview: bool = True,
# ) -> bool:
#     """
#     Convenience function to print a fiscal QR code.
    
#     Args:
#         qr_url: The QR code URL from ZIMRA
#         invoice_number: Invoice number for reference
#         verification_code: Verification code from ZIMRA
#         printer_name: Name of printer to use
#         show_preview: If True, shows preview before printing
    
#     Returns:
#         True if successful, False otherwise
#     """
#     service = get_qr_print_service()
    
#     if show_preview:
#         if service.preview_fiscal_qr(qr_url, invoice_number, verification_code):
#             return service.print_fiscal_qr(qr_url, invoice_number, verification_code, printer_name, show_preview=False)
#         return False
#     else:
#         return service.print_fiscal_qr(qr_url, invoice_number, verification_code, printer_name, show_preview=False)

# services/qr_print_service.py
"""
Standalone QR Code printing service for fiscal receipts.
Completely decoupled from the main printing service.
"""

from PySide6.QtPrintSupport import QPrinter, QPrinterInfo
from PySide6.QtGui import QPainter, QFont, QColor, QPixmap, QPageSize
from PySide6.QtCore import Qt, QMarginsF, QSizeF, QByteArray
from PySide6.QtWidgets import QMessageBox
from pathlib import Path
import sys
try:
    import qrcode
except ImportError:
    qrcode = None

from io import BytesIO
from datetime import datetime
import logging

log = logging.getLogger("QRPrintService")

# Colors
NAVY = "#0d1f3c"
WHITE = "#ffffff"
DARK_TEXT = "#0d1f3c"
SUCCESS = "#1a7a3c"
BORDER = "#c8d8ec"

# Paper settings
PAPER_WIDTH_MM = 80
PAPER_HEIGHT_MM = 200
MARGIN_MM = 2


def _get_app_data_dir() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys.executable).parent / "app_data"
    return Path.cwd() / "app_data"


def _get_logo_path() -> Path:
    return _get_app_data_dir() / "logos" / "logo.png"


class QRPrintService:
    """
    Standalone service for printing fiscal QR codes.
    Can be used independently without affecting main receipt printing.
    """
    
    def __init__(self):
        self._paper_width_pt = None
        self._margin_pt = None
        self._setup_printer_units()
    
    def _setup_printer_units(self):
        """Setup printer units based on standard 80mm thermal printer"""
        try:
            test_printer = QPrinter(QPrinter.HighResolution)
            mm_to_pt = test_printer.logicalDpiX() / 25.4
            self._paper_width_pt = PAPER_WIDTH_MM * mm_to_pt
            self._margin_pt = MARGIN_MM * mm_to_pt
        except Exception:
            self._paper_width_pt = 226  # Approx 80mm at 72dpi
            self._margin_pt = 5
    
    def get_available_printers(self) -> list[str]:
        """Get list of available printers"""
        try:
            return [p.printerName() for p in QPrinterInfo.availablePrinters()]
        except Exception:
            return []
    
    def generate_qr_pixmap(self, qr_url: str, size: int = 200) -> QPixmap:
        """
        Generate a QPixmap from a QR code URL.
        
        Args:
            qr_url: The URL or text to encode in QR code
            size: Size of the QR code in pixels
        
        Returns:
            QPixmap of the QR code
        """
        if qrcode is None:
            log.error("QR Code generation failed: 'qrcode' module not installed.")
            return QPixmap()

        try:
            # Generate QR code
            qr = qrcode.QRCode(
                version=2,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=4,
                border=2,
            )
            qr.add_data(qr_url)
            qr.make(fit=True)
            
            # Create image
            qr_image = qr.make_image(fill_color="black", back_color="white")
            
            # Convert to bytes
            buffer = BytesIO()
            qr_image.save(buffer, format="PNG")
            buffer.seek(0)
            
            # Create QPixmap from bytes
            pixmap = QPixmap()
            pixmap.loadFromData(buffer.getvalue(), "PNG")
            
            # Scale to desired size
            scaled = pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            return scaled
            
        except Exception as e:
            log.error(f"Failed to generate QR code: {e}")
            return QPixmap()
    
    def print_fiscal_qr(
        self,
        qr_url: str,
        invoice_number: str = "",
        verification_code: str = "",
        printer_name: str = None,
        show_preview: bool = False,
    ) -> bool:
        """
        Fiscal QR printing is disabled.
        Returns True to avoid breaking any callers.
        """
        log.info(f"[QRPrintService] Fiscal QR printing disabled — skipping print for invoice {invoice_number}")
        return True
    
    def preview_fiscal_qr(
        self,
        qr_url: str,
        invoice_number: str = "",
        verification_code: str = "",
    ) -> bool:
        """
        Show a preview of the fiscal QR receipt before printing.
        
        Returns:
            True if user confirmed print, False otherwise
        """
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
        
        # Create preview dialog
        preview = QDialog()
        preview.setWindowTitle("Fiscal QR Code Preview")
        preview.setMinimumSize(400, 600)
        preview.setModal(True)
        
        layout = QVBoxLayout(preview)
        
        # Generate QR pixmap
        qr_pixmap = self.generate_qr_pixmap(qr_url, size=250)
        
        # QR Code label
        qr_label = QLabel()
        qr_label.setPixmap(qr_pixmap)
        qr_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(qr_label)
        
        # Invoice info
        info_label = QLabel()
        info_label.setText(
            f"Invoice: {invoice_number}\n"
            f"Verification: {verification_code}\n"
            f"\nScan QR code to verify with ZIMRA"
        )
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setStyleSheet("font-size: 12px; padding: 10px;")
        layout.addWidget(info_label)
        
        # Buttons
        btn_layout = QHBoxLayout()
        print_btn = QPushButton("Print")
        print_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {SUCCESS};
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #1f9447; }}
        """)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {NAVY};
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
            }}
            QPushButton:hover {{ background-color: #162d52; }}
        """)
        
        btn_layout.addWidget(print_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        print_btn.clicked.connect(preview.accept)
        cancel_btn.clicked.connect(preview.reject)
        
        return preview.exec() == QDialog.Accepted
    
    def _draw_fiscal_qr_receipt(self, painter: QPainter, qr_url: str, invoice_number: str, verification_code: str):
        """
        Draw the fiscal QR receipt on the painter.
        """
        # Get settings
        from models.advance_settings import AdvanceSettings
        settings = AdvanceSettings.load_from_file()
        
        # Setup fonts
        normal_font = self._create_font(settings.contentFontName, settings.contentFontSize, settings.contentFontStyle)
        bold_font = self._make_bold(normal_font)
        small_font = QFont(normal_font)
        
        # Robustly calculate small size (avoiding -1 for pixel-based fonts)
        # QFont.pointSize() returns -1 if size is in pixels.
        base_size = normal_font.pointSize()
        if base_size < 1: 
            base_size = normal_font.pixelSize()
        
        new_size = max(base_size - 1, 8)
        if normal_font.pointSize() > 0:
            small_font.setPointSize(new_size)
        else:
            small_font.setPixelSize(new_size)
        
        painter.setFont(normal_font)
        
        # Get paper width in pixels
        paper_width = painter.device().width()
        margin = int(paper_width * 0.05)  # 5% margin
        content_width = paper_width - (margin * 2)
        
        y = margin
        
        # Draw logo if exists
        y = self._draw_logo(painter, margin, y, content_width)
        
        # Company name
        painter.setFont(bold_font)
        company = getattr(settings, "companyName", None) or "Havano POS"
        painter.drawText(margin, y, content_width, 40, Qt.AlignCenter, company.upper())
        y += 50
        
        # Divider
        painter.drawLine(margin, y, paper_width - margin, y)
        y += 15
        
        # Title
        painter.setFont(bold_font)
        painter.drawText(margin, y, content_width, 35, Qt.AlignCenter, "*** FISCAL RECEIPT ***")
        y += 45
        
        # Divider
        painter.drawLine(margin, y, paper_width - margin, y)
        y += 15
        
        # Invoice info
        painter.setFont(normal_font)
        fm = painter.fontMetrics()
        line_height = fm.height() + 5
        
        painter.drawText(margin, y, content_width, line_height, Qt.AlignLeft, f"Invoice: {invoice_number}")
        y += line_height
        
        painter.drawText(margin, y, content_width, line_height, Qt.AlignLeft, f"Verification: {verification_code}")
        y += line_height + 10
        
        # Draw QR Code
        qr_pixmap = self.generate_qr_pixmap(qr_url, size=180)
        if not qr_pixmap.isNull():
            qr_x = (paper_width - qr_pixmap.width()) // 2
            painter.drawPixmap(qr_x, y, qr_pixmap)
            y += qr_pixmap.height() + 15
        
        # QR Code hint
        painter.setFont(small_font)
        painter.drawText(margin, y, content_width, 20, Qt.AlignCenter, "Scan QR code to verify with ZIMRA")
        y += 30
        
        # Divider
        painter.drawLine(margin, y, paper_width - margin, y)
        y += 15
        
        # Footer
        painter.setFont(small_font)
        now = datetime.now()
        painter.drawText(margin, y, content_width, 20, Qt.AlignCenter, f"Printed: {now.strftime('%d/%m/%Y %H:%M:%S')}")
        y += 25
        
        painter.drawText(margin, y, content_width, 20, Qt.AlignCenter, "Thank you for your purchase!")
        y += 20
    
    def _draw_logo(self, painter: QPainter, margin: int, y: int, content_width: int) -> int:
        """Draw company logo if exists"""
        logo_path = _get_logo_path()
        if logo_path.exists():
            pixmap = QPixmap(str(logo_path))
            if not pixmap.isNull():
                scaled = pixmap.scaled(120, 50, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                x = margin + (content_width - scaled.width()) // 2
                painter.drawPixmap(x, y, scaled)
                return y + scaled.height() + 10
        return y
    
    def _create_font(self, family: str, size: int, style_str: str = "Regular") -> QFont:
        """Create a QFont with given parameters"""
        font = QFont(family or "Arial", max(size or 10, 8))
        style_lower = style_str.strip().lower()
        is_bold = any(w in style_lower for w in ["bold", "heavy", "black"])
        is_italic = any(w in style_lower for w in ["italic", "oblique"])
        font.setWeight(QFont.Bold if is_bold else QFont.Normal)
        font.setItalic(is_italic)
        return font

    def _make_bold(self, font: QFont) -> QFont:
        """Return a copy of font with Bold weight forced on."""
        f = QFont(font)
        f.setWeight(QFont.Bold)
        return f


# Singleton instance
_qr_print_service = None


def get_qr_print_service() -> QRPrintService:
    """Get the singleton QR print service instance"""
    global _qr_print_service
    if _qr_print_service is None:
        _qr_print_service = QRPrintService()
    return _qr_print_service


def print_fiscal_qr(
    qr_url: str,
    invoice_number: str = "",
    verification_code: str = "",
    printer_name: str = None,
    show_preview: bool = True,
) -> bool:
    """
    Fiscal QR printing is disabled.
    Returns True to avoid breaking any callers.
    """
    log.info(f"[print_fiscal_qr] Fiscal QR printing disabled — skipping print for invoice {invoice_number}")
    return True