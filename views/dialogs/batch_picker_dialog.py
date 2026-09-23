# views/dialogs/batch_picker_dialog.py
"""
Batch Picker Dialog:
Allows selecting a specific batch when selling a product with multiple batches.
Presents available batches sorted by expiry date ascending (FIFO).
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QPushButton, QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt
from theme import NAVY, NAVY_2, WHITE, ACCENT, BORDER, OFF_WHITE, SUCCESS, SUCCESS_H


class BatchPickerDialog(QDialog):
    def __init__(self, parent=None, product_name="", batches=None, requested_qty=1.0):
        super().__init__(parent)
        self.product_name = product_name
        self.batches = batches or []
        self.requested_qty = requested_qty
        self.selected_batch = None

        # Sort batches: earliest expiry first (FIFO)
        def _exp_key(b):
            e = b.get("expiry_date") or ""
            return (e == "", str(e))
        self.batches = sorted(self.batches, key=_exp_key)

        self.setWindowTitle("Select Batch")
        self.setModal(True)
        self.setMinimumSize(540, 360)
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet(f"""
            QDialog {{ background-color: {WHITE}; }}
            QLabel {{ color: {NAVY}; }}
            QTableWidget {{
                background-color: {WHITE};
                color: {NAVY};
                border: 1px solid {BORDER};
                border-radius: 6px;
                gridline-color: #f1f5f9;
                font-size: 13px;
                outline: none;
            }}
            QTableWidget::item:selected {{
                background-color: {ACCENT};
                color: {WHITE};
                font-weight: bold;
            }}
            QHeaderView::section {{
                background-color: #f8fafc;
                color: {NAVY};
                font-weight: bold;
                font-size: 12px;
                padding: 6px;
                border: none;
                border-bottom: 1px solid {BORDER};
            }}
        """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)

        title = QLabel(f"Select Batch for: {self.product_name}")
        title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {NAVY};")
        lay.addWidget(title)

        sub = QLabel("Multiple batches found in stock. Select the batch you are selling from (FIFO recommended):")
        sub.setStyleSheet("font-size: 12px; color: #64748b;")
        sub.setWordWrap(True)
        lay.addWidget(sub)

        # Batches table
        self.table = QTableWidget(self)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Batch No", "Expiry Date", "Available Qty", "Status"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)

        self.table.setRowCount(len(self.batches))
        for r, b in enumerate(self.batches):
            bn = b.get("batch_no") or "(no batch #)"
            exp = b.get("expiry_date") or "N/A"
            qty = b.get("qty", 0)

            item_bn = QTableWidgetItem(str(bn))
            item_exp = QTableWidgetItem(str(exp))
            item_exp.setTextAlignment(Qt.AlignCenter)
            item_qty = QTableWidgetItem(f"{float(qty):g}")
            item_qty.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

            status_text = "FIFO (Earliest)" if r == 0 else ""
            item_status = QTableWidgetItem(status_text)
            item_status.setTextAlignment(Qt.AlignCenter)
            if r == 0:
                item_status.setForeground(Qt.darkGreen)

            self.table.setItem(r, 0, item_bn)
            self.table.setItem(r, 1, item_exp)
            self.table.setItem(r, 2, item_qty)
            self.table.setItem(r, 3, item_status)
            self.table.setRowHeight(r, 32)

        if self.batches:
            self.table.selectRow(0)

        self.table.doubleClicked.connect(self._on_select)
        lay.addWidget(self.table)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        cancel_btn = QPushButton("Cancel (Esc)")
        cancel_btn.setFixedHeight(38)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #f1f5f9; color: {NAVY};
                border: 1px solid {BORDER}; border-radius: 6px;
                font-weight: bold; padding: 0 16px;
            }}
            QPushButton:hover {{ background-color: #e2e8f0; }}
        """)
        cancel_btn.clicked.connect(self.reject)

        select_btn = QPushButton("Select Batch (Enter)")
        select_btn.setFixedHeight(38)
        select_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {SUCCESS}; color: {WHITE};
                border: none; border-radius: 6px;
                font-weight: bold; padding: 0 20px;
            }}
            QPushButton:hover {{ background-color: {SUCCESS_H}; }}
        """)
        select_btn.clicked.connect(self._on_select)

        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(select_btn)
        lay.addLayout(btn_row)

        self.table.setFocus()

    def _on_select(self):
        row = self.table.currentRow()
        if 0 <= row < len(self.batches):
            self.selected_batch = self.batches[row]
            self.accept()
        else:
            self.reject()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._on_select()
            return
        if event.key() == Qt.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)
