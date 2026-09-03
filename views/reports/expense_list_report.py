from PySide6.QtWidgets import QWidget, QPushButton
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
import qtawesome as qta
from database.db import get_connection, fetchall_dicts
from views.reports.report_template import ReportTemplate

class ExpenseListReport(ReportTemplate):
    def __init__(self, parent=None):
        super().__init__("Expenses", is_report=True, show_date_filter=True, parent=parent)
        self.set_headers(["Date", "Description", "Category", "Supplier", "Status", "Amount"])
        
        self.btn_add.setText("  Add Expense")
        self.btn_add.clicked.connect(self._open_add_expense_dialog)
        self.btn_add.show()
        self.btn_apply.clicked.connect(self._load_data)
        
        self._load_data()

    def showEvent(self, event):
        super().showEvent(event)
        self._load_data()

    def _open_add_expense_dialog(self):
        from views.dialogs.expense_dialog import ProcessExpenseDialog
        dlg = ProcessExpenseDialog(self)
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
                    e.created_at, e.name as descr, 
                    ISNULL(c.name, 'Uncategorized') as category,
                    ISNULL(s.name, '') as supplier,
                    e.paid, e.amount
                FROM expenses e
                LEFT JOIN expense_categories c ON e.expense_category_id = c.id
                LEFT JOIN suppliers s ON e.supplier_id = s.id
                WHERE e.created_at BETWEEN ? AND ?
                ORDER BY e.created_at DESC
            """, (date_from, date_to))
            rows = fetchall_dicts(cur)
            
            display_data = []
            total_amt = 0.0
            
            for row in rows:
                date_str = str(row['created_at'])[:16] if row['created_at'] else ""
                desc_str = str(row['descr'])
                cat_str = str(row['category'])
                sup_str = str(row['supplier'])
                status_str = "Paid" if row['paid'] else "Unpaid"
                amt = float(row['amount'] or 0)
                total_amt += amt
                
                display_data.append([
                    date_str, desc_str, cat_str, sup_str, status_str, f"${amt:,.2f}"
                ])
                
            self.set_data(display_data)
            
            # Post-process for colors, bolding, alignment
            for r, row in enumerate(rows, start=1):
                status_item = self.table.item(r, 4)
                if status_item:
                    if not row['paid']:
                        status_item.setForeground(QColor("#b02020"))
                        f = status_item.font()
                        f.setBold(True)
                        status_item.setFont(f)
                    else:
                        status_item.setForeground(QColor("#1e8449"))
                        
                amt_item = self.table.item(r, 5)
                if amt_item:
                    amt_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                            
        except Exception as e:
            print("Error loading Expense List:", e)
        finally:
            conn.close()
