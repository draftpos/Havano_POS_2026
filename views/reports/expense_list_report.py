from PySide6.QtWidgets import QWidget, QPushButton, QHeaderView
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
import qtawesome as qta
from database.db import get_connection, fetchall_dicts
from views.reports.report_template import ReportTemplate

class ExpenseListReport(ReportTemplate):
    def __init__(self, parent=None, on_back=None):
        super().__init__("Expenses", is_report=False, show_date_filter=True, parent=parent)
        self.on_back = on_back

        # Optional "Back to Apps" button when embedded in AdminDashboard
        if self.on_back:
            self.btn_back = QPushButton(" Apps")
            self.btn_back.setIcon(qta.icon("fa5s.th", color="#1a5fb4"))
            self.btn_back.setCursor(Qt.PointingHandCursor)
            self.btn_back.setFixedHeight(30)
            self.btn_back.setStyleSheet("""
                QPushButton {
                    background-color: #ffffff; color: #1a5fb4; border: 1px solid #c8d8ec;
                    border-radius: 4px; padding: 0px 12px; font-weight: bold; font-size: 11px;
                }
                QPushButton:hover { background-color: #e4eaf4; }
            """)
            self.btn_back.clicked.connect(self.on_back)
            self.filters_layout.insertWidget(0, self.btn_back)
            self.filters_layout.insertSpacing(1, 8)

        self.set_headers(["Date", "Expense #", "Description", "Category", "Payment Method", "Cashier", "Status", "Amount"])

        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Interactive)
        hh.setSectionResizeMode(1, QHeaderView.Interactive)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.Interactive)
        hh.setSectionResizeMode(4, QHeaderView.Interactive)
        hh.setSectionResizeMode(5, QHeaderView.Interactive)
        hh.setSectionResizeMode(6, QHeaderView.Interactive)
        hh.setSectionResizeMode(7, QHeaderView.Interactive)
        self.table.setColumnWidth(0, 140)
        self.table.setColumnWidth(1, 110)
        self.table.setColumnWidth(3, 130)
        self.table.setColumnWidth(4, 120)
        self.table.setColumnWidth(5, 120)
        self.table.setColumnWidth(6, 90)
        self.table.setColumnWidth(7, 120)

        self.btn_add.setText("  Add Expense")
        self.btn_add.clicked.connect(self._open_add_expense_dialog)
        self.btn_add.show()
        self.btn_apply.clicked.connect(self._load_data)

        # Default start date to 30 days ago so expense history is immediately visible
        from PySide6.QtCore import QDate
        self.start_date.setDate(QDate.currentDate().addDays(-30))
        self.end_date.setDate(QDate.currentDate())

        self._load_data()

    def showEvent(self, event):
        super().showEvent(event)
        self._load_data()

    def refresh_data(self):
        self._load_data()

    def _open_add_expense_dialog(self):
        from views.dialogs.expense_dialog import AddExpenseDialog
        parent_w = getattr(self.parent(), "parent_window", None) or self.parent() or self
        dlg = AddExpenseDialog(parent_w)
        if dlg.exec():
            self._load_data()

    def _load_data(self):
        conn = get_connection()
        cur = conn.cursor()
        
        try:
            date_from = self.start_date.date().toString("yyyy-MM-dd") + " 00:00:00"
            date_to = self.end_date.date().toString("yyyy-MM-dd") + " 23:59:59"
            cur.execute("""
                SELECT 
                    e.created_at, 
                    ISNULL(e.expense_number, '') as expense_num,
                    e.name as descr, 
                    ISNULL(c.name, 'Uncategorized') as category,
                    ISNULL(e.payment_method, 'Cash') as payment_method,
                    ISNULL(e.cashier_name, '') as cashier,
                    e.paid, 
                    e.amount
                FROM expenses e
                LEFT JOIN expense_categories c ON e.expense_category_id = c.id
                WHERE e.created_at BETWEEN ? AND ?
                ORDER BY e.created_at DESC
            """, (date_from, date_to))
            rows = fetchall_dicts(cur)
            
            display_data = []
            total_amt = 0.0
            
            for row in rows:
                date_str = str(row['created_at'])[:16] if row['created_at'] else ""
                exp_num = str(row['expense_num'] or "")
                desc_str = str(row['descr'])
                cat_str = str(row['category'])
                pm_str = str(row['payment_method'] or "Cash")
                cashier_str = str(row['cashier'] or "")
                status_str = "Paid" if row['paid'] else "Unpaid"
                amt = float(row['amount'] or 0)
                total_amt += amt
                
                display_data.append([
                    date_str, exp_num, desc_str, cat_str, pm_str, cashier_str, status_str, f"${amt:,.2f}"
                ])
                
            self.set_data(display_data)
            
            # Post-process for colors, bolding, alignment
            for r, row in enumerate(rows, start=1):
                status_item = self.table.item(r, 6)
                if status_item:
                    if not row['paid']:
                        status_item.setForeground(QColor("#b02020"))
                        f = status_item.font()
                        f.setBold(True)
                        status_item.setFont(f)
                    else:
                        status_item.setForeground(QColor("#1e8449"))
                        
                amt_item = self.table.item(r, 7)
                if amt_item:
                    amt_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                            
        except Exception as e:
            print("Error loading Expense List:", e)
        finally:
            conn.close()
