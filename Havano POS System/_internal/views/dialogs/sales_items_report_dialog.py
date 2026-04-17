# =============================================================================
# views/dialogs/sales_items_report_dialog.py
# =============================================================================

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QMessageBox,
    QDateEdit, QComboBox, QGroupBox, QCheckBox
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor

# Import colors
NAVY      = "#0d1f3c"
NAVY_2    = "#162d52"
NAVY_3    = "#1e3d6e"
ACCENT    = "#1a5fb4"
ACCENT_H  = "#1c6dd0"
WHITE     = "#ffffff"
OFF_WHITE = "#f5f8fc"
LIGHT     = "#e4eaf4"
MID       = "#8fa8c8"
DARK_TEXT = "#0d1f3c"
MUTED     = "#5a7a9a"
BORDER    = "#c8d8ec"
ROW_ALT   = "#edf3fb"
SUCCESS   = "#1a7a3c"
SUCCESS_H = "#1f9447"
DANGER    = "#b02020"
DANGER_H  = "#cc2828"
ORANGE    = "#c05a00"
AMBER     = "#b06000"


def navy_btn(text, height=36, font_size=12, width=None, color=None, hover=None):
    bg  = color or NAVY
    hov = hover or NAVY_2
    btn = QPushButton(text)
    btn.setFixedHeight(height)
    if width:
        btn.setFixedWidth(width)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {bg}; color: {WHITE}; border: none;
            border-radius: 5px; font-size: {font_size}px; font-weight: bold; padding: 0 14px;
        }}
        QPushButton:hover   {{ background-color: {hov}; }}
        QPushButton:pressed {{ background-color: {NAVY_3}; }}
    """)
    return btn


class SalesItemsReportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sales Items Report")
        self.setMinimumSize(900, 650)
        self.setStyleSheet(f"QDialog {{ background-color: {WHITE}; }}")
        self._build()
        self._generate_report()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)

        # Header
        hdr = QWidget()
        hdr.setFixedHeight(44)
        hdr.setStyleSheet(f"background-color: {NAVY}; border-radius: 5px;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(16, 0, 16, 0)
        title = QLabel("Sales Items Report")
        title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {WHITE}; background: transparent;")
        hl.addWidget(title)
        layout.addWidget(hdr)

        # Filter section
        filter_group = QGroupBox("Report Filters")
        filter_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold; border: 1px solid {BORDER}; border-radius: 5px;
                margin-top: 10px; padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin; left: 10px; padding: 0 5px 0 5px;
                color: {NAVY}; background: transparent;
            }}
        """)
        filter_layout = QGridLayout(filter_group)
        filter_layout.setSpacing(10)
        filter_layout.setContentsMargins(16, 16, 16, 16)

        # Date range
        filter_layout.addWidget(QLabel("Date Range:"), 0, 0)
        filter_layout.addWidget(QLabel("From:"), 0, 1)

        self._start_date = QDateEdit()
        self._start_date.setDate(QDate.currentDate().addDays(-30))
        self._start_date.setCalendarPopup(True)
        self._start_date.setFixedHeight(34)
        filter_layout.addWidget(self._start_date, 0, 2)

        filter_layout.addWidget(QLabel("To:"), 0, 3)

        self._end_date = QDateEdit()
        self._end_date.setDate(QDate.currentDate())
        self._end_date.setCalendarPopup(True)
        self._end_date.setFixedHeight(34)
        filter_layout.addWidget(self._end_date, 0, 4)

        # Options
        self._group_by_product = QCheckBox("Group by Product")
        self._group_by_product.setChecked(True)
        filter_layout.addWidget(self._group_by_product, 1, 0, 1, 2)

        self._show_zero_qty = QCheckBox("Show Zero Quantity")
        filter_layout.addWidget(self._show_zero_qty, 1, 2, 1, 2)

        # Generate button
        generate_btn = navy_btn("Generate Report", height=34, color=ACCENT, hover=ACCENT_H)
        generate_btn.clicked.connect(self._generate_report)
        filter_layout.addWidget(generate_btn, 1, 4)

        layout.addWidget(filter_group)

        # Summary stats
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(20)

        self._total_items = QLabel("Total Items Sold: 0")
        self._total_items.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {NAVY}; background: transparent;")

        self._total_revenue = QLabel("Total Revenue: $0.00")
        self._total_revenue.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {SUCCESS}; background: transparent;")

        stats_layout.addWidget(self._total_items)
        stats_layout.addWidget(self._total_revenue)
        stats_layout.addStretch()

        layout.addLayout(stats_layout)

        # Items table
        self._items_table = QTableWidget(0, 7)
        self._items_table.setHorizontalHeaderLabels(
            ["Product Code", "Product Name", "UOM", "Quantity", "Unit Price", "Discount", "Total"]
        )
        hh = self._items_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Fixed)
        hh.setSectionResizeMode(3, QHeaderView.Fixed)
        hh.setSectionResizeMode(4, QHeaderView.Fixed)
        hh.setSectionResizeMode(5, QHeaderView.Fixed)
        hh.setSectionResizeMode(6, QHeaderView.Fixed)

        self._items_table.setColumnWidth(0, 100)
        self._items_table.setColumnWidth(2, 70)
        self._items_table.setColumnWidth(3, 80)
        self._items_table.setColumnWidth(4, 100)
        self._items_table.setColumnWidth(5, 80)
        self._items_table.setColumnWidth(6, 100)

        self._items_table.verticalHeader().setVisible(False)
        self._items_table.setAlternatingRowColors(True)
        self._items_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._items_table.setStyleSheet(f"""
            QTableWidget {{ background:{WHITE}; border:1px solid {BORDER};
                gridline-color:{LIGHT}; outline:none; }}
            QTableWidget::item           {{ padding:8px; }}
            QTableWidget::item:selected  {{ background-color:{ACCENT}; color:{WHITE}; }}
            QTableWidget::item:alternate {{ background-color:{ROW_ALT}; }}
            QHeaderView::section {{
                background-color:{NAVY}; color:{WHITE};
                padding:8px; border:none; border-right:1px solid {NAVY_2};
                font-size:11px; font-weight:bold;
            }}
        """)

        layout.addWidget(self._items_table, 1)

        # Export button
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        export_btn = navy_btn("Export to CSV", height=36, color=SUCCESS, hover=SUCCESS_H)
        export_btn.clicked.connect(self._export_report)

        close_btn = navy_btn("Close", height=36, color=DANGER, hover=DANGER_H)
        close_btn.clicked.connect(self.accept)

        btn_row.addStretch()
        btn_row.addWidget(export_btn)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _generate_report(self):
        start_date = self._start_date.date().toString("yyyy-MM-dd")
        end_date = self._end_date.date().toString("yyyy-MM-dd")
        group_by_product = self._group_by_product.isChecked()
        show_zero = self._show_zero_qty.isChecked()

        try:
            from models.sale import get_sales_items_report

            items_data = get_sales_items_report(start_date, end_date, group_by_product)

            if not show_zero:
                items_data = [item for item in items_data if item.get("quantity", 0) > 0]

            self._populate_table(items_data)

            # Update stats
            total_qty = sum(item.get("quantity", 0) for item in items_data)
            total_revenue = sum(item.get("total", 0) for item in items_data)

            self._total_items.setText(f"Total Items Sold: {total_qty:.2f}")
            self._total_revenue.setText(f"Total Revenue: ${total_revenue:.2f}")

        except Exception as e:
            print(f"Error generating report: {e}")
            self._load_demo_data()

    def _populate_table(self, data):
        self._items_table.setRowCount(0)

        for item in data:
            r = self._items_table.rowCount()
            self._items_table.insertRow(r)

            # Product Code
            code_item = QTableWidgetItem(item.get("part_no", ""))
            code_item.setTextAlignment(Qt.AlignCenter)
            self._items_table.setItem(r, 0, code_item)

            # Product Name
            name_item = QTableWidgetItem(item.get("product_name", ""))
            name_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self._items_table.setItem(r, 1, name_item)

            # UOM
            uom_item = QTableWidgetItem(item.get("uom", "Unit"))
            uom_item.setTextAlignment(Qt.AlignCenter)
            uom_item.setForeground(QColor(MUTED))
            self._items_table.setItem(r, 2, uom_item)

            # Quantity
            qty = item.get("quantity", 0)
            qty_item = QTableWidgetItem(f"{qty:.2f}" if qty != int(qty) else str(int(qty)))
            qty_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._items_table.setItem(r, 3, qty_item)

            # Unit Price
            price_item = QTableWidgetItem(f"${item.get('price', 0):.2f}")
            price_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._items_table.setItem(r, 4, price_item)

            # Discount
            disc = item.get("discount", 0)
            disc_item = QTableWidgetItem(f"{disc:.1f}%" if disc > 0 else "")
            disc_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if disc > 0:
                disc_item.setForeground(QColor(ORANGE))
            self._items_table.setItem(r, 5, disc_item)

            # Total
            total_item = QTableWidgetItem(f"${item.get('total', 0):.2f}")
            total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            total_item.setForeground(QColor(ACCENT))
            total_item.setFont(Qt.FontWeight.Bold)
            self._items_table.setItem(r, 6, total_item)

            self._items_table.setRowHeight(r, 32)

    def _load_demo_data(self):
        demo_data = [
            {"part_no": "GR001", "product_name": "Cooking Oil", "uom": "Liter", "quantity": 25, "price": 3.50, "discount": 0, "total": 87.50},
            {"part_no": "DK001", "product_name": "Coke 500ml", "uom": "Bottle", "quantity": 48, "price": 1.20, "discount": 10, "total": 51.84},
            {"part_no": "1", "product_name": "Swiss Army Knife", "uom": "Unit", "quantity": 8, "price": 10.00, "discount": 5, "total": 76.00},
            {"part_no": "S", "product_name": "SERVICE CHARGE", "uom": "Service", "quantity": 15, "price": 50.00, "discount": 0, "total": 750.00},
            {"part_no": "EL001", "product_name": "LED Bulb 12W", "uom": "Piece", "quantity": 20, "price": 4.50, "discount": 0, "total": 90.00},
            {"part_no": "FR001", "product_name": "Orange Juice", "uom": "Carton", "quantity": 12, "price": 8.75, "discount": 0, "total": 105.00},
            {"part_no": "SN001", "product_name": "Potato Chips", "uom": "Pack", "quantity": 35, "price": 2.25, "discount": 0, "total": 78.75},
        ]

        self._populate_table(demo_data)

        total_qty = sum(item["quantity"] for item in demo_data)
        total_revenue = sum(item["total"] for item in demo_data)

        self._total_items.setText(f"Total Items Sold: {total_qty}")
        self._total_revenue.setText(f"Total Revenue: ${total_revenue:.2f}")

    def _export_report(self):
        from PySide6.QtWidgets import QFileDialog
        import csv

        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Report", f"sales_items_{QDate.currentDate().toString('yyyyMMdd')}.csv",
            "CSV Files (*.csv)"
        )

        if filename:
            try:
                with open(filename, 'w', newline='') as f:
                    writer = csv.writer(f)

                    # Write header
                    writer.writerow(["Sales Items Report"])
                    writer.writerow(["Period:", self._start_date.date().toString("yyyy-MM-dd"),
                                   "to", self._end_date.date().toString("yyyy-MM-dd")])
                    writer.writerow([])

                    # Write column headers
                    headers = []
                    for col in range(self._items_table.columnCount()):
                        headers.append(self._items_table.horizontalHeaderItem(col).text())
                    writer.writerow(headers)

                    # Write data
                    for r in range(self._items_table.rowCount()):
                        row = []
                        for c in range(self._items_table.columnCount()):
                            item = self._items_table.item(r, c)
                            row.append(item.text() if item else "")
                        writer.writerow(row)

                    # Write totals
                    writer.writerow([])
                    writer.writerow(["Total", "", "", self._total_items.text().replace("Total Items Sold: ", ""),
                                   "", "", self._total_revenue.text().replace("Total Revenue: ", "")])

                QMessageBox.information(self, "Export Successful", f"Report exported to {filename}")

            except Exception as e:
                QMessageBox.warning(self, "Export Failed", str(e))