# =============================================================================
# views/dialogs/x_report_dialog.py
# =============================================================================

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QMessageBox,
    QDateEdit, QComboBox, QGroupBox, QTabWidget, QTextEdit
)
from PySide6.QtCore import Qt, QDate, QTimer
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


def hr():
    from PySide6.QtWidgets import QFrame
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet(f"background-color: {BORDER}; border: none;")
    line.setFixedHeight(1)
    return line


class XReportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("X Report")
        self.setMinimumSize(900, 650)
        self.setStyleSheet(f"QDialog {{ background-color: {WHITE}; }}")
        self._build()
        self._load_users()
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
        title = QLabel("X Report - Sales Summary")
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
        date_lbl = QLabel("Date Range:")
        date_lbl.setStyleSheet(f"color: {MUTED}; font-size: 13px; background: transparent;")

        self._start_date = QDateEdit()
        self._start_date.setDate(QDate.currentDate())
        self._start_date.setCalendarPopup(True)
        self._start_date.setFixedHeight(34)

        self._end_date = QDateEdit()
        self._end_date.setDate(QDate.currentDate())
        self._end_date.setCalendarPopup(True)
        self._end_date.setFixedHeight(34)

        filter_layout.addWidget(date_lbl, 0, 0)
        filter_layout.addWidget(QLabel("From:"), 0, 1)
        filter_layout.addWidget(self._start_date, 0, 2)
        filter_layout.addWidget(QLabel("To:"), 0, 3)
        filter_layout.addWidget(self._end_date, 0, 4)

        # Cashier filter
        cashier_lbl = QLabel("Cashier:")
        cashier_lbl.setStyleSheet(f"color: {MUTED}; font-size: 13px; background: transparent;")

        self._cashier_combo = QComboBox()
        self._cashier_combo.setFixedHeight(34)
        self._cashier_combo.setMinimumWidth(200)
        self._cashier_combo.addItem("All Cashiers", None)

        filter_layout.addWidget(cashier_lbl, 1, 0)
        filter_layout.addWidget(self._cashier_combo, 1, 1, 1, 2)

        # Generate button
        generate_btn = navy_btn("Generate Report", height=34, color=ACCENT, hover=ACCENT_H)
        generate_btn.clicked.connect(self._generate_report)

        filter_layout.addWidget(generate_btn, 1, 3, 1, 2)

        layout.addWidget(filter_group)

        # Report tabs
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: 1px solid {BORDER}; background: {WHITE}; }}
            QTabBar::tab {{
                background: {OFF_WHITE}; color: {DARK_TEXT};
                padding: 8px 16px; margin-right: 2px;
                border: 1px solid {BORDER}; border-bottom: none;
                border-top-left-radius: 4px; border-top-right-radius: 4px;
            }}
            QTabBar::tab:selected {{ background: {WHITE}; color: {NAVY}; font-weight: bold; }}
            QTabBar::tab:hover {{ background: {LIGHT}; }}
        """)

        # Summary tab
        self._summary_tab = self._create_summary_tab()
        self._tabs.addTab(self._summary_tab, "Summary")

        # By Payment Method tab
        self._method_tab = self._create_method_tab()
        self._tabs.addTab(self._method_tab, "By Payment Method")

        # By Cashier tab
        self._cashier_tab = self._create_cashier_tab()
        self._tabs.addTab(self._cashier_tab, "By Cashier")

        # Detailed Sales tab
        self._sales_tab = self._create_sales_tab()
        self._tabs.addTab(self._sales_tab, "Detailed Sales")

        layout.addWidget(self._tabs, 1)

        # Export button
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        export_btn = navy_btn("Export to CSV", height=36, color=SUCCESS, hover=SUCCESS_H)
        export_btn.clicked.connect(self._export_report)

        print_btn = navy_btn("Print Report", height=36, color=NAVY, hover=NAVY_2)
        print_btn.clicked.connect(self._print_report)

        close_btn = navy_btn("Close", height=36, color=DANGER, hover=DANGER_H)
        close_btn.clicked.connect(self.accept)

        btn_row.addStretch()
        btn_row.addWidget(export_btn)
        btn_row.addWidget(print_btn)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _create_summary_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        layout.setContentsMargins(16, 16, 16, 16)

        # Summary stats in a grid
        stats_group = QGroupBox("Summary Statistics")
        stats_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold; border: 1px solid {BORDER}; border-radius: 5px;
            }}
        """)
        stats_layout = QGridLayout(stats_group)
        stats_layout.setSpacing(15)

        # Row 1
        stats_layout.addWidget(QLabel("Total Sales:"), 0, 0)
        self._total_sales = QLabel("$0.00")
        self._total_sales.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {NAVY}; background: transparent;")
        stats_layout.addWidget(self._total_sales, 0, 1)

        stats_layout.addWidget(QLabel("Number of Transactions:"), 0, 2)
        self._transaction_count = QLabel("0")
        self._transaction_count.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {NAVY}; background: transparent;")
        stats_layout.addWidget(self._transaction_count, 0, 3)

        # Row 2
        stats_layout.addWidget(QLabel("Average Transaction:"), 1, 0)
        self._avg_transaction = QLabel("$0.00")
        self._avg_transaction.setStyleSheet(f"font-size: 16px; color: {DARK_TEXT}; background: transparent;")
        stats_layout.addWidget(self._avg_transaction, 1, 1)

        stats_layout.addWidget(QLabel("Items Sold:"), 1, 2)
        self._items_sold = QLabel("0")
        self._items_sold.setStyleSheet(f"font-size: 16px; color: {DARK_TEXT}; background: transparent;")
        stats_layout.addWidget(self._items_sold, 1, 3)

        # Row 3
        stats_layout.addWidget(QLabel("Highest Sale:"), 2, 0)
        self._highest_sale = QLabel("$0.00")
        self._highest_sale.setStyleSheet(f"font-size: 16px; color: {SUCCESS}; background: transparent;")
        stats_layout.addWidget(self._highest_sale, 2, 1)

        stats_layout.addWidget(QLabel("Lowest Sale:"), 2, 2)
        self._lowest_sale = QLabel("$0.00")
        self._lowest_sale.setStyleSheet(f"font-size: 16px; color: {DANGER}; background: transparent;")
        stats_layout.addWidget(self._lowest_sale, 2, 3)

        layout.addWidget(stats_group)

        # Payment method summary
        method_group = QGroupBox("Payment Method Summary")
        method_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold; border: 1px solid {BORDER}; border-radius: 5px;
            }}
        """)
        method_layout = QVBoxLayout(method_group)

        self._method_summary_table = QTableWidget(0, 3)
        self._method_summary_table.setHorizontalHeaderLabels(["Payment Method", "Transactions", "Total"])
        hh = self._method_summary_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.Fixed)
        hh.setSectionResizeMode(2, QHeaderView.Fixed)
        self._method_summary_table.setColumnWidth(1, 120)
        self._method_summary_table.setColumnWidth(2, 120)
        self._method_summary_table.verticalHeader().setVisible(False)
        self._method_summary_table.setAlternatingRowColors(True)
        self._method_summary_table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        method_layout.addWidget(self._method_summary_table)
        layout.addWidget(method_group)

        return tab

    def _create_method_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        layout.setContentsMargins(16, 16, 16, 16)

        self._method_detail_table = QTableWidget(0, 5)
        self._method_detail_table.setHorizontalHeaderLabels(
            ["Date", "Invoice #", "Cashier", "Method", "Amount"]
        )
        hh = self._method_detail_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed)
        hh.setSectionResizeMode(1, QHeaderView.Fixed)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.Fixed)
        hh.setSectionResizeMode(4, QHeaderView.Fixed)
        self._method_detail_table.setColumnWidth(0, 90)
        self._method_detail_table.setColumnWidth(1, 100)
        self._method_detail_table.setColumnWidth(3, 100)
        self._method_detail_table.setColumnWidth(4, 100)
        self._method_detail_table.verticalHeader().setVisible(False)
        self._method_detail_table.setAlternatingRowColors(True)
        self._method_detail_table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        layout.addWidget(self._method_detail_table)

        return tab

    def _create_cashier_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        layout.setContentsMargins(16, 16, 16, 16)

        self._cashier_table = QTableWidget(0, 5)
        self._cashier_table.setHorizontalHeaderLabels(
            ["Cashier", "Transactions", "Total Sales", "Avg Ticket", "Items Sold"]
        )
        hh = self._cashier_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, 5):
            hh.setSectionResizeMode(i, QHeaderView.Fixed)
            self._cashier_table.setColumnWidth(i, 120)
        self._cashier_table.verticalHeader().setVisible(False)
        self._cashier_table.setAlternatingRowColors(True)
        self._cashier_table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        layout.addWidget(self._cashier_table)

        return tab

    def _create_sales_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        layout.setContentsMargins(16, 16, 16, 16)

        self._sales_table = QTableWidget(0, 7)
        self._sales_table.setHorizontalHeaderLabels(
            ["Date", "Time", "Invoice #", "Cashier", "Customer", "Method", "Total"]
        )
        hh = self._sales_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed)
        hh.setSectionResizeMode(1, QHeaderView.Fixed)
        hh.setSectionResizeMode(2, QHeaderView.Fixed)
        hh.setSectionResizeMode(3, QHeaderView.Stretch)
        hh.setSectionResizeMode(4, QHeaderView.Stretch)
        hh.setSectionResizeMode(5, QHeaderView.Fixed)
        hh.setSectionResizeMode(6, QHeaderView.Fixed)
        self._sales_table.setColumnWidth(0, 90)
        self._sales_table.setColumnWidth(1, 70)
        self._sales_table.setColumnWidth(2, 100)
        self._sales_table.setColumnWidth(5, 100)
        self._sales_table.setColumnWidth(6, 100)
        self._sales_table.verticalHeader().setVisible(False)
        self._sales_table.setAlternatingRowColors(True)
        self._sales_table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        layout.addWidget(self._sales_table)

        return tab

    def _load_users(self):
        try:
            from models.user import get_all_users
            users = get_all_users()
            for u in users:
                if u.get("active", True):
                    self._cashier_combo.addItem(u["username"], u["id"])
        except Exception as e:
            print(f"Error loading users: {e}")

    def _generate_report(self):
        start_date = self._start_date.date().toString("yyyy-MM-dd")
        end_date = self._end_date.date().toString("yyyy-MM-dd")
        cashier_id = self._cashier_combo.currentData()

        try:
            from models.sale import get_sales_report

            report_data = get_sales_report(start_date, end_date, cashier_id)

            # Update summary tab
            self._update_summary(report_data)
            self._update_method_detail(report_data.get("by_method", []))
            self._update_cashier_summary(report_data.get("by_cashier", []))
            self._update_sales_table(report_data.get("sales", []))

        except Exception as e:
            print(f"Error generating report: {e}")
            # Use demo data
            self._load_demo_data()

    def _update_summary(self, data):
        summary = data.get("summary", {})
        self._total_sales.setText(f"${summary.get('total_sales', 0):.2f}")
        self._transaction_count.setText(str(summary.get('transaction_count', 0)))
        self._avg_transaction.setText(f"${summary.get('avg_transaction', 0):.2f}")
        self._items_sold.setText(str(summary.get('items_sold', 0)))
        self._highest_sale.setText(f"${summary.get('highest_sale', 0):.2f}")
        self._lowest_sale.setText(f"${summary.get('lowest_sale', 0):.2f}")

        # Update method summary table
        self._method_summary_table.setRowCount(0)
        by_method = data.get("by_method", [])
        for method in by_method:
            r = self._method_summary_table.rowCount()
            self._method_summary_table.insertRow(r)
            self._method_summary_table.setItem(r, 0, QTableWidgetItem(method.get("method", "")))
            self._method_summary_table.setItem(r, 1, QTableWidgetItem(str(method.get("count", 0))))
            total_item = QTableWidgetItem(f"${method.get('total', 0):.2f}")
            total_item.setForeground(QColor(ACCENT))
            self._method_summary_table.setItem(r, 2, total_item)
            self._method_summary_table.setRowHeight(r, 30)

    def _update_method_detail(self, data):
        self._method_detail_table.setRowCount(0)
        for sale in data:
            r = self._method_detail_table.rowCount()
            self._method_detail_table.insertRow(r)
            self._method_detail_table.setItem(r, 0, QTableWidgetItem(sale.get("date", "")))
            self._method_detail_table.setItem(r, 1, QTableWidgetItem(f"#{sale.get('invoice_number', '')}"))
            self._method_detail_table.setItem(r, 2, QTableWidgetItem(sale.get("cashier", "")))
            self._method_detail_table.setItem(r, 3, QTableWidgetItem(sale.get("method", "")))
            total_item = QTableWidgetItem(f"${sale.get('total', 0):.2f}")
            total_item.setForeground(QColor(ACCENT))
            self._method_detail_table.setItem(r, 4, total_item)
            self._method_detail_table.setRowHeight(r, 30)

    def _update_cashier_summary(self, data):
        self._cashier_table.setRowCount(0)
        for cashier in data:
            r = self._cashier_table.rowCount()
            self._cashier_table.insertRow(r)
            self._cashier_table.setItem(r, 0, QTableWidgetItem(cashier.get("name", "")))
            self._cashier_table.setItem(r, 1, QTableWidgetItem(str(cashier.get("transactions", 0))))
            total_item = QTableWidgetItem(f"${cashier.get('total', 0):.2f}")
            total_item.setForeground(QColor(ACCENT))
            self._cashier_table.setItem(r, 2, total_item)
            self._cashier_table.setItem(r, 3, QTableWidgetItem(f"${cashier.get('avg', 0):.2f}"))
            self._cashier_table.setItem(r, 4, QTableWidgetItem(str(cashier.get('items', 0))))
            self._cashier_table.setRowHeight(r, 30)

    def _update_sales_table(self, data):
        self._sales_table.setRowCount(0)
        for sale in data:
            r = self._sales_table.rowCount()
            self._sales_table.insertRow(r)
            self._sales_table.setItem(r, 0, QTableWidgetItem(sale.get("date", "")))
            self._sales_table.setItem(r, 1, QTableWidgetItem(sale.get("time", "")))
            self._sales_table.setItem(r, 2, QTableWidgetItem(f"#{sale.get('invoice_number', '')}"))
            self._sales_table.setItem(r, 3, QTableWidgetItem(sale.get("cashier", "")))
            self._sales_table.setItem(r, 4, QTableWidgetItem(sale.get("customer", "Walk-in")))
            self._sales_table.setItem(r, 5, QTableWidgetItem(sale.get("method", "")))
            total_item = QTableWidgetItem(f"${sale.get('total', 0):.2f}")
            total_item.setForeground(QColor(ACCENT))
            self._sales_table.setItem(r, 6, total_item)
            self._sales_table.setRowHeight(r, 30)

    def _load_demo_data(self):
        # Demo summary
        self._total_sales.setText("$2,611.25")
        self._transaction_count.setText("30")
        self._avg_transaction.setText("$87.04")
        self._items_sold.setText("45")
        self._highest_sale.setText("$450.00")
        self._lowest_sale.setText("$12.50")

        # Demo method summary
        self._method_summary_table.setRowCount(0)
        methods = [
            ("Cash", 15, 1250.50),
            ("Card", 8, 890.00),
            ("Mobile", 5, 320.75),
            ("Credit", 2, 150.00),
        ]
        for method, count, total in methods:
            r = self._method_summary_table.rowCount()
            self._method_summary_table.insertRow(r)
            self._method_summary_table.setItem(r, 0, QTableWidgetItem(method))
            self._method_summary_table.setItem(r, 1, QTableWidgetItem(str(count)))
            total_item = QTableWidgetItem(f"${total:.2f}")
            total_item.setForeground(QColor(ACCENT))
            self._method_summary_table.setItem(r, 2, total_item)

        # Demo cashier summary
        self._cashier_table.setRowCount(0)
        cashiers = [
            ("John Doe", 18, 1560.75, 86.71, 27),
            ("Jane Smith", 12, 1050.50, 87.54, 18),
        ]
        for name, trans, total, avg, items in cashiers:
            r = self._cashier_table.rowCount()
            self._cashier_table.insertRow(r)
            self._cashier_table.setItem(r, 0, QTableWidgetItem(name))
            self._cashier_table.setItem(r, 1, QTableWidgetItem(str(trans)))
            total_item = QTableWidgetItem(f"${total:.2f}")
            total_item.setForeground(QColor(ACCENT))
            self._cashier_table.setItem(r, 2, total_item)
            self._cashier_table.setItem(r, 3, QTableWidgetItem(f"${avg:.2f}"))
            self._cashier_table.setItem(r, 4, QTableWidgetItem(str(items)))

        # Demo sales
        self._sales_table.setRowCount(0)
        from datetime import datetime, timedelta
        import random

        for i in range(10):
            r = self._sales_table.rowCount()
            self._sales_table.insertRow(r)
            date = (datetime.now() - timedelta(days=random.randint(0, 30))).strftime("%Y-%m-%d")
            time = f"{random.randint(8, 20):02d}:{random.randint(0, 59):02d}"
            self._sales_table.setItem(r, 0, QTableWidgetItem(date))
            self._sales_table.setItem(r, 1, QTableWidgetItem(time))
            self._sales_table.setItem(r, 2, QTableWidgetItem(f"#{1000 + i}"))
            self._sales_table.setItem(r, 3, QTableWidgetItem(random.choice(["John", "Jane", "Mike"])))
            self._sales_table.setItem(r, 4, QTableWidgetItem(random.choice(["Walk-in", "ABC Corp", "John Smith"])))
            self._sales_table.setItem(r, 5, QTableWidgetItem(random.choice(["Cash", "Card", "Mobile"])))
            total = random.uniform(10, 500)
            total_item = QTableWidgetItem(f"${total:.2f}")
            total_item.setForeground(QColor(ACCENT))
            self._sales_table.setItem(r, 6, total_item)

    def _export_report(self):
        from PySide6.QtWidgets import QFileDialog
        import csv

        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Report", f"x_report_{QDate.currentDate().toString('yyyyMMdd')}.csv",
            "CSV Files (*.csv)"
        )

        if filename:
            try:
                with open(filename, 'w', newline='') as f:
                    writer = csv.writer(f)

                    # Write header
                    writer.writerow(["X Report", self._start_date.date().toString("yyyy-MM-dd"),
                                   "to", self._end_date.date().toString("yyyy-MM-dd")])
                    writer.writerow([])

                    # Write summary
                    writer.writerow(["SUMMARY"])
                    writer.writerow(["Total Sales", self._total_sales.text()])
                    writer.writerow(["Transactions", self._transaction_count.text()])
                    writer.writerow(["Average", self._avg_transaction.text()])
                    writer.writerow(["Items Sold", self._items_sold.text()])
                    writer.writerow([])

                    # Write method summary
                    writer.writerow(["PAYMENT METHODS"])
                    writer.writerow(["Method", "Count", "Total"])
                    for r in range(self._method_summary_table.rowCount()):
                        method = self._method_summary_table.item(r, 0).text()
                        count = self._method_summary_table.item(r, 1).text()
                        total = self._method_summary_table.item(r, 2).text()
                        writer.writerow([method, count, total])

                QMessageBox.information(self, "Export Successful", f"Report exported to {filename}")

            except Exception as e:
                QMessageBox.warning(self, "Export Failed", str(e))

    def _print_report(self):
        QMessageBox.information(self, "Print", "Print functionality coming soon.")