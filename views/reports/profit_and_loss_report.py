from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QFrame, QDateEdit
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QFont, QColor
from database.db import get_connection, fetchall_dicts
from models.company_defaults import get_currency_symbol

class ProfitAndLossReport(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #f5f8fc;")
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 15, 40, 40)
        
        # Header
        hdr_layout = QHBoxLayout()
        title = QLabel("Profit & Loss Report")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #1a5fb4;")
        hdr_layout.addWidget(title)
        hdr_layout.addStretch()
        
        # Date Filters
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate())
        self.start_date.setStyleSheet("padding: 5px; font-size: 14px; border: 1px solid #c8d8ec; border-radius: 4px; background: white;")
        
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setStyleSheet("padding: 5px; font-size: 14px; border: 1px solid #c8d8ec; border-radius: 4px; background: white;")
        
        hdr_layout.addWidget(QLabel("From:"))
        hdr_layout.addWidget(self.start_date)
        hdr_layout.addWidget(QLabel("To:"))
        hdr_layout.addWidget(self.end_date)
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a5fb4; color: white; border: none;
                border-radius: 4px; padding: 6px 16px; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background-color: #1c6dd0; }
        """)
        refresh_btn.clicked.connect(self._load_data)
        hdr_layout.addWidget(refresh_btn)
        
        layout.addLayout(hdr_layout)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Description", "Amount"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.setStyleSheet("""
            QTableWidget { gridline-color: #e4eaf4; border: 1px solid #c8d8ec; background-color: white; font-size: 14px;}
            QHeaderView::section { background-color: #f0e8d0; padding: 8px; border: none; border-right: 1px solid #c8d8ec; font-weight: bold; font-size: 14px; color: #1a5fb4;}
            QTableWidget::item { padding: 8px; }
        """)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        layout.addWidget(self.table)
        
        self._load_data()

    def showEvent(self, event):
        super().showEvent(event)
        self._load_data()

    def _add_row(self, label, amount, is_header=False, is_total=False, indent=0):
        r = self.table.rowCount()
        self.table.insertRow(r)
        
        lbl_item = QTableWidgetItem(" " * (indent * 4) + label)
        sym = get_currency_symbol()
        amt_str = f"{sym}{amount:,.2f}" if amount is not None else ""
        amt_item = QTableWidgetItem(amt_str)
        amt_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        font = QFont()
        if is_header or is_total:
            font.setBold(True)
        if is_total:
            font.setPointSize(11)
            
        lbl_item.setFont(font)
        amt_item.setFont(font)
        
        if is_total:
            bg_color = QColor("#eaf0f8")
            lbl_item.setBackground(bg_color)
            amt_item.setBackground(bg_color)
        
        self.table.setItem(r, 0, lbl_item)
        self.table.setItem(r, 1, amt_item)

    def _load_data(self):
        self.table.setRowCount(0)
        conn = get_connection()
        cur = conn.cursor()
        
        start_d = self.start_date.date().toString("yyyy-MM-dd")
        end_d = self.end_date.date().toString("yyyy-MM-dd")
        
        try:
            # Total Sales
            cur.execute("SELECT ISNULL(SUM(total), 0) as total_sales FROM sales WHERE CAST(created_at AS DATE) BETWEEN ? AND ?", (start_d, end_d))
            total_sales = float(cur.fetchone()[0] or 0)
            
            # Cost of Goods Sold
            cur.execute("""
                SELECT ISNULL(SUM(si.qty * ISNULL(p.cost_price, 0)), 0) as cogs
                FROM sale_items si
                JOIN sales s ON si.sale_id = s.id
                LEFT JOIN products p ON si.part_no = p.part_no
                WHERE CAST(s.created_at AS DATE) BETWEEN ? AND ?
            """, (start_d, end_d))
            cogs = float(cur.fetchone()[0] or 0)
            
            gross_profit = total_sales - cogs
            
            # Expenses
            cur.execute("""
                SELECT c.name, ISNULL(SUM(e.amount), 0) as total
                FROM expenses e
                LEFT JOIN expense_categories c ON e.expense_category_id = c.id
                WHERE CAST(e.created_at AS DATE) BETWEEN ? AND ?
                GROUP BY c.name
                HAVING SUM(e.amount) > 0
                ORDER BY c.name
            """, (start_d, end_d))
            expense_rows = fetchall_dicts(cur)
            
            total_expenses = sum(float(r['total']) for r in expense_rows)
            net_profit = gross_profit - total_expenses
            
            # Build Table
            self._add_row("Income", None, is_header=True)
            self._add_row("Total Sales", total_sales, indent=1)
            self._add_row("Cost of Goods Sold (COGS)", cogs, indent=1)
            self._add_row("Gross Profit", gross_profit, is_total=True)
            
            self._add_row("", None) # Spacer
            
            self._add_row("Expenses", None, is_header=True)
            if expense_rows:
                for row in expense_rows:
                    self._add_row(row['name'] or "Uncategorized", float(row['total']), indent=1)
            else:
                self._add_row("No Expenses", 0, indent=1)
                
            self._add_row("Total Expenses", total_expenses, is_total=True)
            
            self._add_row("", None) # Spacer
            
            self._add_row("Net Profit", net_profit, is_total=True)
            
            # Highlight Net Profit differently
            r = self.table.rowCount() - 1
            bg_color = QColor("#d4edda") if net_profit >= 0 else QColor("#f8d7da")
            self.table.item(r, 0).setBackground(bg_color)
            self.table.item(r, 1).setBackground(bg_color)
            
        except Exception as e:
            print("Error loading P&L:", e)
        finally:
            conn.close()
