from typing import Optional
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QPushButton, QMessageBox, QWidget,
)
import qtawesome as qta

class SalesOrderListDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None, user: Optional[dict] = None):
        super().__init__(parent)
        self.setWindowTitle("Sales Orders")
        self.setWindowState(Qt.WindowMaximized)
        self.setStyleSheet("QDialog { background: white; }")
        self._user = user or {}
        self._selected_order: Optional[dict] = None
        self._rows_cache: list[dict] = []
        self._build()
        self._reload()

    def _build(self):
        from views.reports.report_template import ReportTemplate
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.report = ReportTemplate("Sales Orders", is_report=True, parent=self)
        self.report.set_headers(["Order No.", "Customer", "Order Date", "Total", "Deposit", "Balance", "Status", "Frappe Ref"])
        
        self.report.table.itemSelectionChanged.connect(self._on_selection_changed)
        
        # Add custom buttons
        self._refresh_btn = QPushButton(" Refresh")
        self._refresh_btn.setIcon(qta.icon("fa5s.sync", color="white"))
        self._refresh_btn.setStyleSheet("""
            QPushButton { background-color: #1a5fb4; color: white; border-radius: 4px; padding: 4px 12px; font-weight: bold; font-size: 11px; }
            QPushButton:hover { background-color: #1c6dd0; }
        """)
        self._refresh_btn.clicked.connect(self._on_refresh)
        
        self._convert_btn = QPushButton(" Convert to Invoice")
        self._convert_btn.setIcon(qta.icon("fa5s.file-invoice-dollar", color="white"))
        self._convert_btn.setStyleSheet("""
            QPushButton { background-color: #1a7a3c; color: white; border-radius: 4px; padding: 4px 12px; font-weight: bold; font-size: 11px; }
            QPushButton:hover { background-color: #1e8f46; }
            QPushButton:disabled { background-color: #a0c2ab; }
        """)
        self._convert_btn.setEnabled(False)
        self._convert_btn.clicked.connect(self._on_convert)
        
        self._delete_btn = QPushButton(" Delete")
        self._delete_btn.setIcon(qta.icon("fa5s.trash", color="white"))
        self._delete_btn.setStyleSheet("""
            QPushButton { background-color: #b02020; color: white; border-radius: 4px; padding: 4px 12px; font-weight: bold; font-size: 11px; }
            QPushButton:hover { background-color: #c92a2a; }
            QPushButton:disabled { background-color: #d19a9a; }
        """)
        self._delete_btn.setEnabled(False)
        self._delete_btn.clicked.connect(self._on_delete)
        
        fl = self.report.filters_layout
        fl.addWidget(self._refresh_btn)
        fl.addWidget(self._convert_btn)
        fl.addWidget(self._delete_btn)
        
        layout.addWidget(self.report)

    def _reload(self):
        try:
            from models.sales_order import list_orders
            self._rows_cache = list_orders()
        except Exception as e:
            self._rows_cache = []

        data = []
        for order in self._rows_cache:
            data.append([
                order.get("order_no", ""),
                order.get("customer_name", ""),
                order.get("order_date", ""),
                f"${float(order.get('total') or 0):,.2f}",
                f"${float(order.get('deposit_amount') or 0):,.2f}",
                f"${float(order.get('balance_due') or 0):,.2f}",
                order.get("status", ""),
                order.get("frappe_ref", "")
            ])
            
        self.report.set_data(data)
        
        # Colorize the balance column
        for r in range(1, self.report.table.rowCount() - 1):
            balance_item = self.report.table.item(r, 5)
            if balance_item:
                try:
                    val = float(balance_item.text().replace("$", "").replace(",", ""))
                    if val <= 0.005:
                        balance_item.setForeground(QColor("#1a7a3c"))
                        f = balance_item.font()
                        f.setBold(True)
                        balance_item.setFont(f)
                except:
                    pass

        self._selected_order = None
        self._convert_btn.setEnabled(False)
        self._delete_btn.setEnabled(False)

    def _on_selection_changed(self):
        rows = self.report.table.selectionModel().selectedRows()
        if not rows:
            self._selected_order = None
            self._convert_btn.setEnabled(False)
            self._delete_btn.setEnabled(False)
            return
            
        row = rows[0].row()
        if row == 0 or row == self.report.table.rowCount() - 1:
            self._selected_order = None
            self._convert_btn.setEnabled(False)
            self._delete_btn.setEnabled(False)
            return
            
        order_no_item = self.report.table.item(row, 0)
        if not order_no_item: return
        
        order_no = order_no_item.text()
        self._selected_order = next((o for o in self._rows_cache if str(o.get("order_no")) == order_no), None)
        self._update_convert_enabled()

    def _update_convert_enabled(self):
        order = self._selected_order or {}
        bal = float(order.get("balance_due") or 0)
        status = (order.get("status") or "").lower()
        can_convert = (bal <= 0.005) and status not in ("completed", "cancelled")
        self._convert_btn.setEnabled(can_convert)
        self._delete_btn.setEnabled(self._selected_order is not None)

    def _on_refresh(self):
        self._refresh_btn.setEnabled(False)
        try:
            from services.sales_order_pull_service import pull_sales_orders_from_frappe
            pull_sales_orders_from_frappe()
        except Exception:
            pass
        finally:
            self._refresh_btn.setEnabled(True)
            self._reload()

    def _on_convert(self):
        order = self._selected_order
        if not order: return
        bal = float(order.get("balance_due") or 0)
        if bal > 0.005:
            QMessageBox.warning(self, "Not Ready", f"Order {order.get('order_no','?')} still has a balance of {bal:.2f}.")
            return
            
        reply = QMessageBox.question(
            self, "Convert to Invoice",
            f"Convert order {order.get('order_no','?')} into a Sales Invoice?\nCustomer: {order.get('customer_name','-')}\nTotal: {float(order.get('total',0)):,.2f}",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
        )
        if reply != QMessageBox.Yes: return

        self._convert_btn.setEnabled(False)
        try:
            from models.sales_order import convert_order_to_sale
            sale = convert_order_to_sale(
                int(order["id"]),
                cashier_id = self._user.get("id") if isinstance(self._user, dict) else None,
                cashier_name = self._user.get("username") if isinstance(self._user, dict) else "",
            )
        except Exception as e:
            QMessageBox.critical(self, "Convert Failed", f"Could not convert order:\n{e}")
            return

        if not sale:
            QMessageBox.warning(self, "Convert Failed", "Order could not be converted. Check the logs for details.")
            return

        QMessageBox.information(self, "Invoice Created", f"Invoice {sale.get('invoice_no','?')} created from order {order.get('order_no','?')}.")
        self._reload()

    def _on_delete(self):
        order = self._selected_order
        if not order: return
        ans = QMessageBox.question(self, "Delete", f"Are you sure you want to delete order {order.get('order_no')}?", QMessageBox.Yes | QMessageBox.No)
        if ans == QMessageBox.Yes:
            try:
                from database.db import get_connection
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("DELETE FROM sales_orders WHERE id = ?", (order['id'],))
                cur.execute("DELETE FROM sales_order_items WHERE order_id = ?", (order['id'],))
                conn.commit()
                conn.close()
                self._reload()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not delete order:\n{str(e)}")
