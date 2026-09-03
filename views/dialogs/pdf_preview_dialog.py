from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QSizePolicy
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QIcon
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
import os

class PdfPreviewDialog(QDialog):
    def __init__(self, pdf_path, title="Report Preview", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setStyleSheet("QDialog { background-color: #f8fafc; }")
        self.resize(1000, 800)
        self.showMaximized()
        self.pdf_path = pdf_path
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Toolbar layout
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(10, 10, 10, 10)
        
        self.btn_print = QPushButton("Print")
        btn_style = """
            QPushButton {
                background-color: #2563eb; color: white; border: none;
                padding: 8px 20px; font-weight: bold; border-radius: 4px;
            }
            QPushButton:hover { background-color: #1d4ed8; }
        """
        self.btn_print.setStyleSheet(btn_style)
        self.btn_print.clicked.connect(self.print_document)
        toolbar.addWidget(self.btn_print)
        
        self.btn_save = QPushButton("Save as PDF")
        self.btn_save.setStyleSheet(btn_style.replace("#2563eb", "#10b981").replace("#1d4ed8", "#059669"))
        self.btn_save.clicked.connect(self.save_pdf)
        toolbar.addWidget(self.btn_save)

        secondary_btn_style = """
            QPushButton {
                background-color: #475569; color: white; border: none;
                padding: 8px 16px; font-weight: bold; border-radius: 4px;
            }
            QPushButton:hover { background-color: #334155; }
        """
        self.btn_fit_page = QPushButton("Fit Page")
        self.btn_fit_page.setStyleSheet(secondary_btn_style)
        self.btn_fit_page.clicked.connect(lambda: self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitInView))
        toolbar.addWidget(self.btn_fit_page)

        self.btn_fit_width = QPushButton("Fit Width")
        self.btn_fit_width.setStyleSheet(secondary_btn_style)
        self.btn_fit_width.clicked.connect(lambda: self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth))
        toolbar.addWidget(self.btn_fit_width)
        
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        # PDF Document and View
        self.document = QPdfDocument(self)
        self.document.load(self.pdf_path)
        
        self.pdf_view = QPdfView(self)
        self.pdf_view.setDocument(self.document)
        self.pdf_view.setPageMode(QPdfView.PageMode.MultiPage)
        # Default zoom mode: Fit Width (was FitInView) so the page fills the
        # available horizontal space instead of shrinking to show a full page.
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self.pdf_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        layout.addWidget(self.pdf_view)

    def print_document(self):
        try:
            from PySide6.QtPrintSupport import QPrinter, QPrintDialog
            from PySide6.QtGui import QPainter
            from PySide6.QtCore import QSize

            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            dialog = QPrintDialog(printer, self)
            if dialog.exec() == QPrintDialog.DialogCode.Accepted:
                painter = QPainter()
                if painter.begin(printer):
                    page_count = self.document.pageCount()
                    for i in range(page_count):
                        if i > 0:
                            printer.newPage()
                            
                        # Get point size and calculate a high-res image size (approx 300 DPI -> 4x points)
                        pt_size = self.document.pagePointSize(i)
                        render_size = QSize(int(pt_size.width() * 4), int(pt_size.height() * 4))
                        
                        # Render the PDF page into a QImage
                        image = self.document.render(i, render_size)
                        
                        # Draw the image onto the printer page
                        rect = printer.pageRect(QPrinter.Unit.DevicePixel)
                        painter.drawImage(rect, image)
                        
                    painter.end()
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Print Error", f"Could not print the document natively:\n{e}")

    def save_pdf(self):
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        import shutil
        import os
        import re
        
        title = self.windowTitle()
        if title.startswith("Preview: "):
            title = title[9:]
        elif title.startswith("Preview:"):
            title = title[8:]
            
        safe_title = "".join(c if c.isalnum() else "_" for c in title).strip("_")
        safe_title = re.sub(r'_+', '_', safe_title)
        
        default_name = f"{safe_title}.pdf" if safe_title else "Report.pdf"

        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save PDF", default_name, "PDF Files (*.pdf)"
        )
        if save_path:
            try:
                shutil.copy2(self.pdf_path, save_path)
                QMessageBox.information(self, "Success", f"PDF saved successfully to:\n{save_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save PDF:\n{e}")