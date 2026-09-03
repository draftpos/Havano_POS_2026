# views/receipt_dialog.py
import os
import qtawesome as qta
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel,
    QPushButton, QFrame, QHBoxLayout, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt
from datetime import datetime
from utils.pdf_receipt import generate_receipt


class ReceiptDialog(QDialog):

    def __init__(self, cart_items, total, sale_id, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Receipt")
        self.setFixedWidth(340)
        self.cart_items = cart_items
        self.total      = total
        self.sale_id    = sale_id
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        title = QLabel("MY POS SYSTEM")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        date_label = QLabel(datetime.now().strftime("%Y-%m-%d   %H:%M"))
        date_label.setAlignment(Qt.AlignCenter)
        date_label.setStyleSheet("color: #6c7086; font-size: 12px;")
        layout.addWidget(date_label)

        sale_label = QLabel(f"Receipt  #  {self.sale_id}")
        sale_label.setAlignment(Qt.AlignCenter)
        sale_label.setStyleSheet("color: #6c7086; font-size: 12px;")
        layout.addWidget(sale_label)

        layout.addWidget(self._divider())

        # Items
        for name, price in self.cart_items:
            row = QHBoxLayout()
            row.addWidget(QLabel(name))
            price_lbl = QLabel(f"${price:.2f}")
            price_lbl.setAlignment(Qt.AlignRight)
            price_lbl.setStyleSheet("color: #a6e3a1;")
            row.addWidget(price_lbl)
            layout.addLayout(row)

        layout.addWidget(self._divider())

        # Total
        total_row = QHBoxLayout()
        total_text = QLabel("TOTAL")
        total_text.setStyleSheet("font-weight: bold; font-size: 14px;")
        total_amount = QLabel(f"${self.total:.2f}")
        total_amount.setAlignment(Qt.AlignRight)
        total_amount.setStyleSheet("font-weight: bold; font-size: 14px; color: #a6e3a1;")
        total_row.addWidget(total_text)
        total_row.addWidget(total_amount)
        layout.addLayout(total_row)

        layout.addWidget(self._divider())

        # Buttons row
        btn_row = QHBoxLayout()

        download_btn = QPushButton("Download PDF")
        download_btn.setIcon(qta.icon("fa5s.download"))
        download_btn.setFixedHeight(40)
        download_btn.setStyleSheet("""
            QPushButton {
                background-color: #cba6f7;
                color: #1e1e2e;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #b48ead; }
        """)
        download_btn.clicked.connect(self._download_pdf)

        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(40)
        close_btn.clicked.connect(self.accept)

        btn_row.addWidget(download_btn)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _divider(self):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #45475a;")
        return line

    def _download_pdf(self):
        # Ask user where to save
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Receipt",
            os.path.join(os.path.expanduser("~"), "Desktop", f"receipt_{self.sale_id}.pdf"),
            "PDF Files (*.pdf)"
        )
        if path:
            generate_receipt(self.sale_id, self.cart_items, self.total, save_dir=os.path.dirname(path))
            QMessageBox.information(self, "Saved", f"Receipt saved to:\n{path}")