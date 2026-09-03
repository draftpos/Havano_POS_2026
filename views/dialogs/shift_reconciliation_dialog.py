# =============================================================================
# views/dialogs/shift_reconciliation_dialog.py
# Complete shift reconciliation with database storage
# =============================================================================

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QLineEdit,
    QMessageBox, QPushButton, QFrame, QTabWidget, QWidget, QInputDialog
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont
from datetime import datetime
from decimal import Decimal
import json
import traceback
from models.shift import get_payment_method_currency, get_company_base_currency
from views.dialogs.payment_dialog import _get_local_rate


class AdminCashierOverrideReconciliationDialog(QDialog):
    """Dialog for Admins to reconcile unfinalized cashier counts before closing a shift."""

    def __init__(self, parent, active_shift, unfinalized_cashiers, all_cashiers, show_expected=True):
        super().__init__(parent)
        self.active_shift = active_shift
        self.unfinalized_cashiers = unfinalized_cashiers
        self.all_cashiers = all_cashiers
        self.show_expected = show_expected
        self.parent_dialog = parent
        self.setWindowTitle("Reconcile Unfinalized Cashier Counts")
        self.showMaximized()
        self.setModal(True)
        self.setStyleSheet("""
            QDialog { background: white; }
            QLabel { color: #212121; font-size: 12px; }
            QLineEdit {
                background: white; 
                color: #212121;
                border: 1px solid #bdbdbd; 
                border-radius: 4px;
                padding: 6px 10px; 
                font-size: 13px;
                font-weight: bold;
            }
            QLineEdit:focus { 
                border: 2px solid #1976d2; 
            }
            QTableWidget {
                background: white; 
                border: 1px solid #bdbdbd;
                gridline-color: #e0e0e0; 
                font-size: 13px;
            }
            QTableWidget::item { 
                padding: 8px; 
                color: #212121;
            }
            QHeaderView::section {
                background: #e0e0e0; 
                color: #212121;
                padding: 8px; 
                font-weight: bold;
            }
            QTabWidget::pane {
                border: 1px solid #bdbdbd; 
                border-radius: 4px;
                background: white;
            }
            QTabBar::tab {
                background: #f5f5f5; 
                color: #212121;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background: #1976d2; 
                color: white;
            }
            QTabBar::tab:hover {
                background: #e3f2fd;
                color: #0d47a1;
            }
        """)
        
        self.cashier_inputs = {} # map cashier_id -> list of (method_upper, exp_val, line_edit, var_item)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Slim Modern Title Label instead of large warning banner
        hdr_widget = QWidget()
        hdr_widget.setStyleSheet("background: #f5f5f7; border-radius: 6px; border-left: 4px solid #1976d2;")
        hdr_lay = QHBoxLayout(hdr_widget)
        hdr_lay.setContentsMargins(15, 10, 15, 10)
        title_lbl = QLabel("<b>Reconcile Unfinalized Cashier Counts</b> - Admin Override Counts Mode")
        title_lbl.setStyleSheet("font-size: 13px; color: #1565c0; font-family: 'Segoe UI';")
        hdr_lay.addWidget(title_lbl)
        hdr_lay.addStretch()
        layout.addWidget(hdr_widget)

        # Dialog Action Buttons (Moved to the top!)
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 5, 0, 5)
        
        save_btn = QPushButton("Save & Reconcile Counts")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #388e3c;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 4px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2e7d32;
            }
        """)
        save_btn.clicked.connect(self._on_save_reconciliations)
        
        cancel_btn = QPushButton("Cancel Closing")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #757575;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 4px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #616161;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # Tabs
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget, 1)
        
        # Build global maps to calculate prorated expected
        global_expected_map = {}
        for sr in self.active_shift.get("rows", []):
            m_key = sr["method"].strip().upper()
            global_expected_map[m_key] = float(sr.get("total", 0.0))
            
        global_collected_map = {}
        for ac in self.all_cashiers:
            ac_methods = ac.get("totals", {}).get("payment_methods", {})
            ac_credit_total = 0.0
            for sale in ac.get("sales", []):
                if sale.get("is_on_account", False) and sale.get("total", 0) > sale.get("tendered", 0):
                    ac_credit_total += sale.get("total", 0) - sale.get("tendered", 0)
            
            ac_methods_dict = dict(ac_methods)
            if ac_credit_total > 0:
                ac_methods_dict["ON ACCOUNT"] = ac_credit_total
                
            for m, amt in ac_methods_dict.items():
                m_key = m.strip().upper()
                global_collected_map[m_key] = global_collected_map.get(m_key, 0.0) + float(amt)
                
        # Populate tabs for each unfinalized cashier
        for cashier_data in self.unfinalized_cashiers:
            cashier_name = cashier_data.get("cashier_name", "Unknown")
            cashier_id = cashier_data.get("cashier_id")
            
            tab_widget = QWidget()
            tab_lay = QVBoxLayout(tab_widget)
            tab_lay.setContentsMargins(10, 10, 10, 10)
            
            # Cashier details mini-header
            c_total = float(cashier_data.get("totals", {}).get("total_sales", 0))
            c_txs = len(cashier_data.get("sales", []))
            hdr_lbl = QLabel(f"<b>Cashier:</b> {cashier_name} (ID: {cashier_id})  |  <b>Sales:</b> ${c_total:,.2f} ({c_txs} transactions)")
            hdr_lbl.setStyleSheet("font-size: 13px; color: #333333; padding-bottom: 5px;")
            tab_lay.addWidget(hdr_lbl)
            
            # Payment Methods Table
            base_ccy = get_company_base_currency() or "USD"
            table = QTableWidget(0, 8)
            table.setHorizontalHeaderLabels(["Payment Method", "Currency", "Expected", f"Expected ({base_ccy})", "Counted Actual", "Variance", f"Variance ({base_ccy})", "Transaction Count"])
            table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
            table.setColumnWidth(1, 65)
            table.setColumnWidth(2, 95)
            table.setColumnWidth(3, 115)
            table.setColumnWidth(4, 120)
            table.setColumnWidth(5, 95)
            table.setColumnWidth(6, 115)
            table.setColumnWidth(7, 100)
            table.verticalHeader().setVisible(False)  # Hide vertical headers
            table.setFrameShape(QFrame.NoFrame)       # Modern flat borderless frame
            table.setShowGrid(True)
            table.setStyleSheet("""
                QTableWidget {
                    background: white; 
                    gridline-color: #e0e0e0; 
                    font-size: 13px;
                }
                QHeaderView::section {
                    background: #f5f5f5; 
                    color: #212121;
                    padding: 8px; 
                    font-weight: bold;
                    border: none;
                    border-bottom: 2px solid #e0e0e0;
                }
            """)
            tab_lay.addWidget(table)
            
            payment_methods = cashier_data.get("totals", {}).get("payment_methods", {})
            # Handle credit sales (ON ACCOUNT) if any
            cashier_credit_total = 0.0
            for sale in cashier_data.get("sales", []):
                if sale.get("is_on_account", False) and sale.get("total", 0) > sale.get("tendered", 0):
                    cashier_credit_total += sale.get("total", 0) - sale.get("tendered", 0)
            
            if cashier_credit_total > 0:
                payment_methods = dict(payment_methods)
                payment_methods["ON ACCOUNT"] = cashier_credit_total
                
            self.cashier_inputs[cashier_id] = []
            
            if not payment_methods:
                table.setRowCount(1)
                no_data_item = QTableWidgetItem("No payment methods recorded")
                no_data_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                no_data_item.setForeground(QColor("#757575"))
                table.setItem(0, 0, no_data_item)
                table.setSpan(0, 0, 1, 4)
            else:
                table.setRowCount(len(payment_methods))
                for row_idx, (method, amount) in enumerate(payment_methods.items()):
                    method_upper = method.strip().upper()
                    amount_collected = float(amount)
                    total_collected = global_collected_map.get(method_upper, 0.0)
                    proportion = (amount_collected / total_collected) if total_collected > 0 else 0.0
                    
                    expected = global_expected_map.get(method_upper, 0.0) * proportion
                    
                    currency = get_payment_method_currency(method)
                    count = 0
                    for sale in cashier_data.get("sales", []):
                        for pm in sale.get("payment_methods", []):
                            if pm.upper() == method_upper:
                                count += 1
                                break
                        if method_upper == "ON ACCOUNT" and sale.get("is_on_account", False):
                            count += 1
                            
                    rate_to_base = _get_local_rate(currency, base_ccy)
                    
                    # Col 0 - Method Name
                    m_item = QTableWidgetItem(str(method))
                    m_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    m_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
                    table.setItem(row_idx, 0, m_item)
                    
                    # Col 1 - Currency
                    c_item = QTableWidgetItem(currency)
                    c_item.setTextAlignment(Qt.AlignCenter)
                    c_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    c_item.setForeground(QColor("#757575"))
                    table.setItem(row_idx, 1, c_item)
                    
                    # Col 2 - Expected
                    exp_item = QTableWidgetItem(f"{expected:,.2f}")
                    exp_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    exp_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    table.setItem(row_idx, 2, exp_item)
                    
                    # Col 3 - Expected Base
                    exp_base_item = QTableWidgetItem(f"{expected * rate_to_base:,.2f}")
                    exp_base_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    exp_base_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    exp_base_item.setForeground(QColor("#1565c0"))
                    table.setItem(row_idx, 3, exp_base_item)
                    
                    # Col 4 - Counted Input
                    actual_edit = QLineEdit("")
                    actual_edit.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    actual_edit.setStyleSheet("""
                        QLineEdit {
                            background: #e3f2fd;
                            color: #0d47a1;
                            border: 1px solid #90caf9;
                            border-radius: 4px;
                            padding: 4px 10px;
                            font-size: 13px;
                            font-weight: bold;
                        }
                        QLineEdit:focus {
                            border: 2px solid #1976d2;
                            background: white;
                        }
                    """)
                    table.setCellWidget(row_idx, 4, actual_edit)
                    
                    # Col 5 - Variance Display
                    var_item = QTableWidgetItem(f"{-expected:,.2f}")
                    var_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    var_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    var_item.setForeground(QColor("#d32f2f"))
                    table.setItem(row_idx, 5, var_item)
                    
                    # Col 6 - Variance Base Display
                    var_base_item = QTableWidgetItem(f"{-expected * rate_to_base:,.2f}")
                    var_base_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    var_base_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    var_base_item.setForeground(QColor("#d32f2f"))
                    table.setItem(row_idx, 6, var_base_item)
                    
                    # Col 7 - Transaction Count
                    tx_item = QTableWidgetItem(str(count))
                    tx_item.setTextAlignment(Qt.AlignCenter)
                    tx_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    tx_item.setForeground(QColor("#757575"))
                    table.setItem(row_idx, 7, tx_item)
                    
                    actual_edit.textChanged.connect(
                        lambda _, r=row_idx, t=table, exp=expected, rtb=rate_to_base: self._update_variance(r, t, exp, rtb)
                    )
                    
                    # Still keep the old tuple for _on_save_reconciliations
                    self.cashier_inputs[cashier_id].append((method_upper, expected, actual_edit, var_item))
                    table.setRowHeight(row_idx, 40)
                    
            # Add TOTAL row at the bottom
            total_row_idx = len(payment_methods)
            table.setRowCount(total_row_idx + 1)
            
            tot_label = QTableWidgetItem("TOTAL")
            font = QFont()
            font.setBold(True)
            tot_label.setFont(font)
            tot_label.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            bg_color = QColor("#e0e0e0")
            tot_label.setBackground(bg_color)
            tot_label.setForeground(QColor("#212121"))
            table.setItem(total_row_idx, 0, tot_label)
            
            tot_curr_item = QTableWidgetItem("")
            tot_curr_item.setBackground(bg_color)
            tot_curr_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            table.setItem(total_row_idx, 1, tot_curr_item)
            
            for col in range(2, 8):
                item = QTableWidgetItem("0.00" if col < 7 else "0")
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                item.setFont(font)
                item.setBackground(bg_color)
                item.setForeground(QColor("#212121"))
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                table.setItem(total_row_idx, col, item)
                    
            self._update_totals(table)
            self.tab_widget.addTab(tab_widget, cashier_name)

    def _update_variance(self, row, table, expected, rate_to_base):
        try:
            actual_edit = table.cellWidget(row, 4)
            if not actual_edit: return
            
            var_item = table.item(row, 5)
            var_base_item = table.item(row, 6)
            
            val_str = actual_edit.text().strip()
            if not val_str:
                var_item.setText("")
                var_base_item.setText("")
            else:
                val = float(val_str)
                variance = val - expected
                var_base = variance * rate_to_base
                
                var_item.setText(f"{variance:,.2f}")
                var_base_item.setText(f"{var_base:,.2f}")
                
                if variance < 0:
                    var_item.setForeground(QColor("#d32f2f"))
                    var_base_item.setForeground(QColor("#d32f2f"))
                elif variance > 0:
                    var_item.setForeground(QColor("#388e3c"))
                    var_base_item.setForeground(QColor("#388e3c"))
                else:
                    var_item.setForeground(QColor("#757575"))
                    var_base_item.setForeground(QColor("#757575"))
                    
            self._update_totals(table)
        except ValueError:
            pass

    def _update_totals(self, table):
        total_row = table.rowCount() - 1
        if total_row < 0: return
        
        tot_exp, tot_exp_base = 0.0, 0.0
        tot_cnt = 0.0
        tot_var, tot_var_base = 0.0, 0.0
        tot_tx = 0
        
        for r in range(total_row):
            exp_item = table.item(r, 2)
            if exp_item: tot_exp += float(exp_item.text().replace(",", "") or 0)
            
            exp_base_item = table.item(r, 3)
            if exp_base_item: tot_exp_base += float(exp_base_item.text().replace(",", "") or 0)
            
            edit = table.cellWidget(r, 4)
            cnt_item = table.item(r, 4)
            if edit and edit.text().strip():
                tot_cnt += float(edit.text().strip().replace(",", ""))
            elif cnt_item and cnt_item.text().strip():
                tot_cnt += float(cnt_item.text().strip().replace(",", ""))
                
            var_base_item = table.item(r, 6)
            if var_base_item and var_base_item.text().strip():
                tot_var_base += float(var_base_item.text().replace(",", ""))
                
            tx_item = table.item(r, 7)
            if tx_item and tx_item.text().strip():
                tot_tx += int(tx_item.text().replace(",", ""))
                
        tot_var = tot_cnt - tot_exp
        
        table.item(total_row, 2).setText(f"{tot_exp:,.2f}")
        table.item(total_row, 3).setText(f"{tot_exp_base:,.2f}")
        table.item(total_row, 4).setText(f"{tot_cnt:,.2f}")
        table.item(total_row, 5).setText(f"{tot_var:,.2f}")
        table.item(total_row, 6).setText(f"{tot_var_base:,.2f}")
        table.item(total_row, 7).setText(str(tot_tx))

    def _on_save_reconciliations(self):
        # 1. Parse and validate inputs for all unfinalized cashiers
        to_save = {} # cashier_id -> counted_data dict
        
        for cashier_data in self.unfinalized_cashiers:
            c_name = cashier_data.get("cashier_name", "Unknown")
            c_id = cashier_data.get("cashier_id")
            inputs = self.cashier_inputs.get(c_id, [])
            
            counted_data = {}
            for method_upper, expected, edit, var_item in inputs:
                text = edit.text().strip()
                if not text:
                    text = "0.00"
                try:
                    val = float(text)
                except ValueError:
                    QMessageBox.warning(
                        self,
                        "Invalid Input",
                        f"Please enter a valid numeric counted amount for cashier '{c_name}' in '{method_upper}'."
                    )
                    edit.setFocus()
                    return
                counted_data[method_upper] = val
            to_save[c_id] = (c_name, counted_data)
            
        # 2. Confirm save with the Admin
        confirm = QMessageBox.question(
            self,
            "Confirm Override Reconciliations",
            "Are you sure you want to save these counted amounts on behalf of the unfinalized cashiers and finalize their slots?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
            
        # 3. Save all reconciliations and trigger their variance slip printouts!
        from models.shift import save_cashier_reconciliation
        
        for c_id, (c_name, counted_data) in to_save.items():
            success = save_cashier_reconciliation(
                shift_id=self.active_shift["id"],
                cashier_id=c_id,
                cashier_name=c_name,
                counted_json=json.dumps(counted_data),
                is_finalized=True,
                is_modified=True
            )
            if success:
                # Dispatch printer variance slips automatically!
                try:
                    from services.printing_service import PrintingService
                    from views.dialogs.settings_dialog import _load_hw
                    hw = _load_hw()
                    printer_name = hw.get("main_printer", None)
                    if printer_name == "(None)":
                        printer_name = None
                    
                    ps = PrintingService()
                    ps.print_cashier_reconciliation(
                        shift_id=self.active_shift["id"],
                        cashier_id=c_id,
                        printer_name=printer_name
                    )
                except Exception as print_err:
                    print(f"[OverrideRecon] Auto print failed for cashier {c_name}: {print_err}")
                    
        QMessageBox.information(
            self,
            "Counts Saved",
            "All cashier session counts have been successfully entered, finalized, and logged!"
        )
        self.accept()


class ShiftReconciliationDialog(QDialog):
    """Dialog for shift reconciliation with complete data storage."""

    def __init__(self, parent=None, cashier_id=None, cashier_name=None, closing_cashier_id=None, closing_cashier_name=None):
        super().__init__(parent)
        
        # Resolve the logged-in user and role robustly
        self.logged_in_user = None
        if parent and hasattr(parent, "user") and parent.user:
            self.logged_in_user = parent.user
        elif parent and hasattr(parent, "parent_window") and getattr(parent, "parent_window", None) and hasattr(parent.parent_window, "user"):
            self.logged_in_user = parent.parent_window.user
            
        if self.logged_in_user and self.logged_in_user.get("id"):
            try:
                from models.user import get_user_by_id
                fresh = get_user_by_id(self.logged_in_user["id"])
                if fresh:
                    self.logged_in_user = fresh
            except Exception:
                pass
            
        self.is_user_admin = False
        self.allow_shift_reconciliation = False
        if self.logged_in_user:
            self.is_user_admin = (self.logged_in_user.get("role") == "admin")
            self.allow_shift_reconciliation = bool(self.logged_in_user.get("allow_shift_reconciliation", False))
            if not cashier_id:
                cashier_id = self.logged_in_user.get("id")
            if not cashier_name:
                cashier_name = self.logged_in_user.get("full_name") or self.logged_in_user.get("username")

        self.can_reconcile_shift = self.is_user_admin or self.allow_shift_reconciliation

        self.closing_cashier_id = closing_cashier_id or cashier_id
        # Resolve the cashier name - look it up from the DB if not passed in
        self.closing_cashier_name = closing_cashier_name or cashier_name
        if not self.closing_cashier_name and self.closing_cashier_id:
            try:
                from database.db import get_connection
                conn = get_connection()
                cur = conn.cursor()
                cur.execute(
                    "SELECT COALESCE(full_name, username, '') AS name FROM users WHERE id = ?",
                    (self.closing_cashier_id,)
                )
                row = cur.fetchone()
                conn.close()
                self.closing_cashier_name = row[0] if row and row[0] else f"Cashier #{self.closing_cashier_id}"
            except Exception:
                self.closing_cashier_name = f"Cashier #{self.closing_cashier_id}"
        if not self.closing_cashier_name:
            self.closing_cashier_name = ""
        self._active_shift = None
        self._reconciliation_id = None
        
        self.setWindowTitle("Shift Reconciliation")
        self.setMinimumSize(850, 520)
        self.setModal(True)
        self.showMaximized()

        # HIDE EXPECTED amount check
        self.show_expected = True
        try:
            # First respect global maintenance setting
            from database.db import get_connection
            conn = get_connection(); cur = conn.cursor()
            cur.execute("SELECT setting_value FROM pos_settings WHERE setting_key = 'show_expected_in_reconciliation'")
            r = cur.fetchone()
            if r: self.show_expected = (str(r[0]) == "1")
            conn.close()

            # Next, if the user is a cashier, check their specific permission
            parent_win = self.parent()
            if parent_win and hasattr(parent_win, "user"):
                u = parent_win.user
                if u and u.get("role", "").lower() != "admin":
                    if not u.get("allow_view_expected", False):
                        self.show_expected = False
        except: pass

        self._setup_styles()
        self._refresh_shift()
        
        if self.can_reconcile_shift:
            self._build_ui()
            self._load_data()
        else:
            self._build_cashier_ui()
            self._load_cashier_data()

    def _setup_styles(self):
        self.setStyleSheet("""
            QDialog { background: white; }
            QLabel { color: #212121; font-size: 12px; }
            QLineEdit {
                background: white; 
                color: #212121;
                border: 1px solid #bdbdbd; 
                border-radius: 4px;
                padding: 8px 10px; 
                font-size: 13px;
            }
            QLineEdit:focus { 
                border: 2px solid #1976d2; 
                background: white;
                color: #212121;
            }
            QLineEdit:hover {
                border: 1px solid #1976d2;
                background: white;
            }
            QTableWidget {
                background: white; 
                border: 1px solid #bdbdbd;
                gridline-color: #e0e0e0; 
                font-size: 13px;
                alternate-background-color: #f5f5f5;
                selection-background-color: #1a5fb4;
                selection-color: #ffffff;
            }
            QTableWidget::item { 
                padding: 10px 8px; 
                color: #212121;
            }
            QTableWidget::item:selected {
                background-color: #1a5fb4;
                color: #ffffff;
            }
            QHeaderView::section {
                background: #e0e0e0; 
                color: #212121;
                padding: 10px; 
                font-weight: bold;
            }
            QTabWidget::pane {
                border: 1px solid #bdbdbd; 
                border-radius: 4px;
                background: white;
            }
            QTabBar::tab {
                background: #f5f5f5; 
                color: #212121;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background: #1976d2; 
                color: white;
            }
            QTabBar::tab:hover {
                background: #e3f2fd;
                color: #0d47a1;
            }
            QPushButton {
                border: none;
                border-radius: 4px;
                padding: 10px 25px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton#closeBtn {
                background-color: #388e3c;
                color: white;
            }
            QPushButton#closeBtn:hover {
                background-color: #2e7d32;
            }
            QPushButton#cancelBtn {
                background-color: #757575;
                color: white;
            }
            QPushButton#cancelBtn:hover {
                background-color: #616161;
            }
        """)

    def _refresh_shift(self):
        try:
            from models.shift import get_active_shift, refresh_income, get_shift_by_id
            self._active_shift = get_active_shift()
            if self._active_shift:
                print(f"\n[DEBUG] Active shift found: #{self._active_shift.get('shift_number')}")
                print(f"[DEBUG] Shift ID: {self._active_shift.get('id')}")
                refresh_income(self._active_shift["id"])
                self._active_shift = get_shift_by_id(self._active_shift["id"])
                
                # Debug shift rows after refresh
                shift_rows = self._active_shift.get("rows", [])
                print(f"[DEBUG] Shift rows after refresh: {len(shift_rows)}")
                for sr in shift_rows:
                    print(f"  - {sr.get('method')}: start_float={sr.get('start_float')}, income={sr.get('income')}, total={sr.get('total')}, counted={sr.get('counted')}")
            else:
                print("[DEBUG] No active shift found")
        except Exception as e:
            print(f"[Recon] Error refreshing shift: {e}")
            traceback.print_exc()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 12, 15, 12)

        # Header Bar with Heading & Action Buttons on the same line
        header_widget = QWidget()
        header_widget.setStyleSheet("border-bottom: 2px solid #1976d2; padding-bottom: 6px;")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 6)
        header_layout.setSpacing(10)

        header = QLabel("Shift Reconciliation")
        header.setStyleSheet("font-size: 17px; font-weight: bold; color: #1976d2; border: none;")

        self.close_btn = QPushButton("Finalize & Close Shift")
        self.close_btn.setObjectName("closeBtn")
        self.close_btn.setStyleSheet("""
            QPushButton#closeBtn {
                background-color: #2e7d32;
                color: white;
                font-weight: bold;
                padding: 6px 14px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton#closeBtn:hover {
                background-color: #1b5e20;
            }
        """)
        self.close_btn.clicked.connect(self._on_finalize)
        self.close_btn.setEnabled(self.can_reconcile_shift)
        if not self.can_reconcile_shift:
            self.close_btn.hide()

        self.reprint_btn = QPushButton("Reprint Shift Recon")
        self.reprint_btn.setObjectName("reprintBtn")
        self.reprint_btn.setStyleSheet("""
            QPushButton#reprintBtn {
                background-color: #0288d1;
                color: white;
                font-weight: bold;
                padding: 6px 14px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton#reprintBtn:hover {
                background-color: #01579b;
            }
        """)
        self.reprint_btn.setCursor(Qt.PointingHandCursor)
        self.reprint_btn.clicked.connect(self._on_reprint_shift)

        cancel_btn_text = "Close Window" if not self.can_reconcile_shift else "Cancel"
        cancel_btn = QPushButton(cancel_btn_text)
        cancel_btn.setObjectName("cancelBtn")
        cancel_btn.setStyleSheet("""
            QPushButton#cancelBtn {
                background-color: #616161;
                color: white;
                font-weight: bold;
                padding: 6px 14px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton#cancelBtn:hover {
                background-color: #424242;
            }
        """)
        cancel_btn.clicked.connect(self.reject)

        header_layout.addWidget(header)
        header_layout.addStretch()
        header_layout.addWidget(self.reprint_btn)
        header_layout.addWidget(self.close_btn)
        header_layout.addWidget(cancel_btn)

        layout.addWidget(header_widget)

        # Offscreen shift_info label to maintain attribute compatibility
        self.shift_info = QLabel()


        # Tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("QTabWidget::pane { border: 1px solid #d0d0d0; top: -1px; } QTabBar::tab { font-size: 12px; font-weight: bold; padding: 6px 14px; }")
        layout.addWidget(self.tab_widget)

        # Main reconciliation tab
        main_tab = QWidget(self)
        main_layout = QVBoxLayout(main_tab)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(6)
        
        instr_label = QLabel("Enter actual counted amounts for each payment method:")
        instr_label.setStyleSheet("font-weight: bold; margin-bottom: 2px; font-size: 11px; color: #424242;")
        main_layout.addWidget(instr_label)

        # Main table - 7 columns: Method | Currency | Expected | Expected (Base) | Actual | Variance | Variance (Base)
        base_ccy = get_company_base_currency() or "USD"
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Payment Method", 
            "Currency", 
            "Expected", 
            f"Expected ({base_ccy})", 
            "Actual", 
            "Variance", 
            f"Variance ({base_ccy})"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setColumnWidth(1, 65)
        self.table.setColumnWidth(2, 95)
        self.table.setColumnWidth(3, 115)
        self.table.setColumnWidth(4, 100)
        self.table.setColumnWidth(5, 95)
        self.table.setColumnWidth(6, 115)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.setStyleSheet("""
            QTableWidget { font-size: 12px; gridline-color: #e0e0e0; }
            QHeaderView::section { font-weight: bold; font-size: 11px; padding: 4px; background-color: #eceff1; border: 1px solid #cfd8dc; }
            QTableWidget::item { padding: 2px 4px; }
        """)
        
        if not self.show_expected:
            self.table.setColumnHidden(2, True)
            self.table.setColumnHidden(3, True)
            self.table.setColumnHidden(5, True)
            self.table.setColumnHidden(6, True)
            
        main_layout.addWidget(self.table)

        if self.can_reconcile_shift:
            self.tab_widget.addTab(main_tab, "Reconciliation")

    def _on_reprint_shift(self):
        try:
            from views.dialogs.shift_reprint_dialog import show_shift_reprint
            show_shift_reprint(self)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open reprint dialog: {e}")

    def _load_data(self):
        if not self._active_shift:
            QMessageBox.warning(self, "No Active Shift", "No open shift was found.")
            self.close_btn.setEnabled(False)
            return

        shift_num = self._active_shift.get("shift_number", "?")
        shift_date = self._active_shift.get("date", "")
        
        # Convert date to string if it's a date object
        if hasattr(shift_date, 'strftime'):
            shift_date = shift_date.strftime("%Y-%m-%d")
        
        raw_start = self._active_shift.get("start_time") or self._active_shift.get("created_at")
        if raw_start and hasattr(raw_start, 'strftime'):
            shift_time = raw_start.strftime("%H:%M:%S")
        elif isinstance(raw_start, str) and raw_start:
            shift_time = raw_start.split("T")[-1].split(" ")[-1][:8] if "T" in raw_start else raw_start[:8]
        else:
            shift_time = "-"

        cashier_info = f" | Closing Cashier: {self.closing_cashier_name}" if self.closing_cashier_name else ""
        self.shift_info.setText(f"Shift #{shift_num}  |  {shift_date}  |  Started: {shift_time}{cashier_info}")

        # Get all recorded cashier counts from the database for this shift
        from models.shift import get_all_cashier_reconciliations_for_shift
        recorded_cashier_counts = get_all_cashier_reconciliations_for_shift(self._active_shift["id"])
        
        # Build a map of method to total counted sum across all cashiers
        cashier_counted_map = {}
        for rc in recorded_cashier_counts:
            counted_data = rc.get("counted_data", {})
            for key, val in counted_data.items():
                cashier_counted_map[key] = cashier_counted_map.get(key, 0.0) + float(val)

        # Clear existing tabs to avoid duplication on refresh
        base_tab_count = 1 if self.can_reconcile_shift else 0
        while self.tab_widget.count() > base_tab_count:
            self.tab_widget.removeTab(base_tab_count)

        # Load cashier tabs (ALL cashiers who worked this shift)
        self._load_cashier_tabs()
        
        # Load data directly from shift_rows - the RAW source of truth
        shift_rows = self._active_shift.get("rows", [])
        print(f"\n[DEBUG] _load_data: Found {len(shift_rows)} shift rows")

        # Build list of methods to display
        methods_to_show = []
        for sr in shift_rows:
            method_name = sr.get("method", "").strip()
            if not method_name:
                continue
            
            expected = float(sr.get("total", 0.0))
            counted = cashier_counted_map.get(method_name.upper(), 0.0)
            currency = sr.get("currency")
            if not currency:
                currency = get_payment_method_currency(method_name)
            
            methods_to_show.append({
                "method": method_name,
                "expected": expected,
                "counted": counted,
                "currency": currency
            })

        # Sort so ON ACCOUNT is last
        methods_to_show.sort(key=lambda x: (x["method"].upper() == "ON ACCOUNT", x["method"]))

        if not methods_to_show:
            QMessageBox.warning(self, "No Data", "No payment methods found for this shift.")
            self.close_btn.setEnabled(False)
            return

        self.table.setRowCount(len(methods_to_show) + 1)
        
        for i, data in enumerate(methods_to_show):
            method = data["method"]
            expected = data["expected"]
            counted = data["counted"]
            curr = data["currency"]
            variance = counted - expected

            print(f"[DEBUG] Method {method}: expected={expected}, counted={counted}, variance={variance}")

            # Col 0 - Payment Method
            name_item = QTableWidgetItem(method)
            name_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            name_item.setForeground(QColor("#212121"))
            font = QFont()
            font.setBold(True)
            name_item.setFont(font)
            self.table.setItem(i, 0, name_item)

            # Col 1 - Currency
            curr_item = QTableWidgetItem(curr)
            curr_item.setTextAlignment(Qt.AlignCenter)
            curr_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            curr_item.setForeground(QColor("#757575"))
            self.table.setItem(i, 1, curr_item)

            # Col 2 - Expected (Native)
            exp_item = QTableWidgetItem(f"{expected:,.2f}")
            exp_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            exp_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            exp_item.setForeground(QColor("#212121"))
            self.table.setItem(i, 2, exp_item)

            # Col 3 - Expected (Base Currency Equivalent)
            base_ccy = get_company_base_currency() or "USD"
            rate_to_base = _get_local_rate(curr, base_ccy)
            exp_base = expected * rate_to_base
            exp_base_item = QTableWidgetItem(f"{exp_base:,.2f}")
            exp_base_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            exp_base_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            exp_base_item.setForeground(QColor("#1565c0"))
            self.table.setItem(i, 3, exp_base_item)

            # Col 4 - Actual (Native) - Editable
            actual_text = f"{counted:.2f}" if counted > 0 else ""
            actual_edit = QLineEdit(actual_text)
            actual_edit.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            actual_edit.setStyleSheet("""
                QLineEdit {
                    background: #e3f2fd;
                    color: #0d47a1;
                    border: 1px solid #90caf9;
                    border-radius: 4px;
                    padding: 4px 10px;
                    font-size: 13px;
                    font-weight: bold;
                }
                QLineEdit:focus {
                    border: 2px solid #1976d2;
                    background: white;
                }
            """)
            self.table.setCellWidget(i, 4, actual_edit)
            actual_edit.textChanged.connect(lambda _, r=i: self._update_variance(r))
            self.table.setRowHeight(i, 40)

            # Col 5 - Variance (Native)
            if counted > 0 or expected > 0:
                var_text = f"{variance:,.2f}"
            else:
                var_text = ""

            var_item = QTableWidgetItem(var_text)
            var_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            var_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            if var_text:
                if variance < 0:
                    var_item.setForeground(QColor("#d32f2f"))
                elif variance > 0:
                    var_item.setForeground(QColor("#388e3c"))
                else:
                    var_item.setForeground(QColor("#757575"))
            self.table.setItem(i, 5, var_item)

            # Col 6 - Variance (Base Currency Equivalent)
            var_base = variance * rate_to_base
            if counted > 0 or expected > 0:
                var_base_text = f"{var_base:,.2f}"
            else:
                var_base_text = ""

            var_base_item = QTableWidgetItem(var_base_text)
            var_base_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            var_base_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            if var_base_text:
                if var_base < 0:
                    var_base_item.setForeground(QColor("#d32f2f"))
                elif var_base > 0:
                    var_base_item.setForeground(QColor("#388e3c"))
                else:
                    var_base_item.setForeground(QColor("#757575"))
            self.table.setItem(i, 6, var_base_item)

            self.table.setRowHeight(i, 36)
        
        self._update_summary()

    def _load_cashier_tabs(self):
        """Load cashier breakdown tabs from actual sales data - ALL cashiers who worked."""
        try:
            from models.shift import get_cashier_sales_for_shift
            
            shift_id = self._active_shift.get("id")
            if not shift_id:
                return
            
            # Get ALL cashiers who made sales during this shift
            cashiers = get_cashier_sales_for_shift(shift_id)
            
            if not self.can_reconcile_shift:
                cashiers = [c for c in cashiers if c.get("cashier_id") == self.closing_cashier_id]
                if not cashiers:
                    # Construct a default mock cashier dict so they can see their own tab
                    cashiers = [{
                        "cashier_id": self.closing_cashier_id,
                        "cashier_name": self.closing_cashier_name,
                        "sales": [],
                        "totals": {
                            "total_sales": 0.0,
                            "total_items": 0,
                            "payment_methods": {}
                        }
                    }]
            
            print(f"\n[DEBUG] _load_cashier_tabs: Found {len(cashiers)} cashier(s) who worked this shift")
            for c in cashiers:
                print(f"  - {c.get('cashier_name')}: ${c.get('totals', {}).get('total_sales', 0):,.2f}")
                pm = c.get('totals', {}).get('payment_methods', {})
                for method, amount in pm.items():
                    print(f"      {method}: ${amount:,.2f}")
            
            if not cashiers:
                no_data_tab = QWidget()
                no_layout = QVBoxLayout(no_data_tab)
                no_layout.addWidget(QLabel("No cashier sales data available for this shift."))
                self.tab_widget.addTab(no_data_tab, "No Data")
                return
            
            # Add a tab for EACH cashier who worked
            for cashier in cashiers:
                self._add_cashier_tab(cashier)
                
        except Exception as e:
            print(f"Error loading cashier tabs: {e}")
            import traceback
            traceback.print_exc()

    def _add_cashier_tab(self, cashier_data: dict):
        """Add a tab for each cashier with their actual sales."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        cashier_name = cashier_data.get("cashier_name", "Unknown")
        cashier_id = cashier_data.get("cashier_id")
        total_sales = float(cashier_data.get("totals", {}).get("total_sales", 0))
        num_transactions = len(cashier_data.get("sales", []))
        total_items = int(cashier_data.get("totals", {}).get("total_items", 0))
        
        # Load recorded counts for this cashier
        from models.shift import get_cashier_reconciliation
        recorded = get_cashier_reconciliation(self._active_shift["id"], cashier_id)
        is_slot_finalized = False
        recorded_counted = {}
        if recorded:
            is_slot_finalized = bool(recorded.get("is_finalized", 0))
            recorded_counted = recorded.get("counted_data", {})

        # Cashier info header
        info_frame = QFrame()
        info_frame.setStyleSheet("QFrame { background: #f5f5f5; border-radius: 6px; padding: 12px; }")
        info_layout = QHBoxLayout(info_frame)
        
        info_text = f"""
        <b>{cashier_name}</b><br>
        <span style='font-size: 11px; color: #666;'>ID: {cashier_id if cashier_id else '-'}</span><br>
        Transactions: {num_transactions}  |  Items Sold: {total_items}  |  Total Sales: ${total_sales:,.2f}
        """
        info_label = QLabel(info_text)
        info_label.setTextFormat(Qt.RichText)
        info_label.setStyleSheet("font-size: 13px; color: #212121;")
        info_layout.addWidget(info_label)
        info_layout.addStretch()
        
        # Payment methods table
        base_ccy = get_company_base_currency() or "USD"
        table = QTableWidget(0, 8)
        table.setHorizontalHeaderLabels(["Payment Method", "Currency", "Expected", f"Expected ({base_ccy})", "Counted", "Variance", f"Variance ({base_ccy})", "Transaction Count"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table.setColumnWidth(1, 65)
        table.setColumnWidth(2, 95)
        table.setColumnWidth(3, 115)
        table.setColumnWidth(4, 120)
        table.setColumnWidth(5, 95)
        table.setColumnWidth(6, 115)
        table.setColumnWidth(7, 100)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setStyleSheet("""
            QTableWidget {
                background: white;
                color: #212121;
                selection-background-color: #1a5fb4;
                selection-color: #ffffff;
            }
            QTableWidget::item {
                color: #212121;
            }
            QTableWidget::item:selected {
                background-color: #1a5fb4;
                color: #ffffff;
            }
        """)

        if not self.show_expected:
            table.setColumnHidden(2, True)
            table.setColumnHidden(3, True)
            table.setColumnHidden(5, True)
            table.setColumnHidden(6, True)
            
        # Add action buttons inside the info frame at the far right
        is_own_tab = (cashier_id == self.closing_cashier_id)
        if is_slot_finalized:
            modify_btn = QPushButton("Modify Count")
            modify_btn.setStyleSheet("""
                QPushButton {
                    background-color: #d32f2f;
                    color: white;
                    font-weight: bold;
                    padding: 10px 20px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #b71c1c;
                }
            """)
            modify_btn.setCursor(Qt.PointingHandCursor)
            modify_btn.clicked.connect(lambda _, c_id=cashier_id, c_nm=cashier_name: self._on_modify_cashier_count(c_id, c_nm))
            info_layout.addWidget(modify_btn)
            
            if is_own_tab:
                status_lbl = QLabel("[OK] Your cashier slot count is finalized and locked.")
            else:
                status_lbl = QLabel(f"[OK] Finalized by {cashier_name} (locked).")
            status_lbl.setStyleSheet("font-weight: bold; color: #388e3c; font-size: 13px; margin-left: 10px;")
            info_layout.addWidget(status_lbl)
        else:
            if is_own_tab:
                finalize_btn = QPushButton("Finalize My Count")
                finalize_btn.setObjectName("finalizeBtn")
                finalize_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #1976d2;
                        color: white;
                        font-weight: bold;
                        padding: 10px 20px;
                        border-radius: 4px;
                    }
                    QPushButton:hover {
                        background-color: #1565c0;
                    }
                """)
                finalize_btn.setCursor(Qt.PointingHandCursor)
                finalize_btn.clicked.connect(lambda _, c_id=cashier_id, c_nm=cashier_name, tbl=table: self._on_finalize_cashier_count(c_id, c_nm, tbl))
                info_layout.addWidget(finalize_btn)
            else:
                status_lbl = QLabel(f"[!] Unfinalized by {cashier_name}")
                status_lbl.setStyleSheet("font-weight: bold; color: #d32f2f; font-size: 13px; padding: 5px;")
                info_layout.addWidget(status_lbl)
                
        # Now add the completed info_frame to the main layout
        layout.addWidget(info_frame)

        
        payment_methods = cashier_data.get("totals", {}).get("payment_methods", {})
        
        # Handle credit sales (ON ACCOUNT) if any
        cashier_credit_total = 0.0
        for sale in cashier_data.get("sales", []):
            if sale.get("is_on_account", False) and sale.get("total", 0) > sale.get("tendered", 0):
                cashier_credit_total += sale.get("total", 0) - sale.get("tendered", 0)
        
        if cashier_credit_total > 0:
            payment_methods = dict(payment_methods)
            payment_methods["ON ACCOUNT"] = cashier_credit_total

        # Build global maps to calculate prorated expected
        from models.shift import get_cashier_sales_for_shift
        all_cashiers = get_cashier_sales_for_shift(self._active_shift["id"])
        
        global_expected_map = {}
        for sr in self._active_shift.get("rows", []):
            m_key = sr["method"].strip().upper()
            global_expected_map[m_key] = float(sr.get("total", 0.0))
            
        global_collected_map = {}
        for ac in all_cashiers:
            ac_methods = ac.get("totals", {}).get("payment_methods", {})
            ac_credit_total = 0.0
            for sale in ac.get("sales", []):
                if sale.get("is_on_account", False) and sale.get("total", 0) > sale.get("tendered", 0):
                    ac_credit_total += sale.get("total", 0) - sale.get("tendered", 0)
            
            ac_methods_dict = dict(ac_methods)
            if ac_credit_total > 0:
                ac_methods_dict["ON ACCOUNT"] = ac_credit_total
                
            for m, amt in ac_methods_dict.items():
                m_key = m.strip().upper()
                global_collected_map[m_key] = global_collected_map.get(m_key, 0.0) + float(amt)

        if not payment_methods:
            table.setRowCount(1)
            no_data_item = QTableWidgetItem("No payment methods recorded")
            no_data_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            no_data_item.setForeground(QColor("#757575"))
            table.setItem(0, 0, no_data_item)
            table.setSpan(0, 0, 1, 6)
        else:
            table.setRowCount(len(payment_methods) + 1)
            for i, (method, amount) in enumerate(payment_methods.items()):
                method_upper = method.strip().upper()
                amount_collected = float(amount)
                total_collected = global_collected_map.get(method_upper, 0.0)
                proportion = (amount_collected / total_collected) if total_collected > 0 else 0.0
                
                expected = global_expected_map.get(method_upper, 0.0) * proportion
                counted = float(recorded_counted.get(method_upper, 0.0))
                variance = counted - expected

                # Determine currency
                currency = get_payment_method_currency(method)

                # Count transactions for this cashier/method
                count = 0
                for sale in cashier_data.get("sales", []):
                    for pm in sale.get("payment_methods", []):
                        if pm.upper() == method_upper:
                            count += 1
                            break
                    if method_upper == "ON ACCOUNT" and sale.get("is_on_account", False):
                        count += 1
                
                # Col 0 - Payment Method
                method_item = QTableWidgetItem(str(method))
                method_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                method_item.setForeground(QColor("#212121"))
                font = QFont()
                font.setBold(True)
                method_item.setFont(font)
                table.setItem(i, 0, method_item)
                
                # Col 1 - Currency
                curr_item = QTableWidgetItem(currency)
                curr_item.setTextAlignment(Qt.AlignCenter)
                curr_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                curr_item.setForeground(QColor("#757575"))
                table.setItem(i, 1, curr_item)
                
                # Col 2 - Expected
                exp_item = QTableWidgetItem(f"{expected:,.2f}")
                exp_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                exp_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                exp_item.setForeground(QColor("#212121"))
                table.setItem(i, 2, exp_item)
                
                # Col 3 - Expected (Base Currency Equivalent)
                rate_to_base = _get_local_rate(currency, base_ccy)
                exp_base = expected * rate_to_base
                exp_base_item = QTableWidgetItem(f"{exp_base:,.2f}")
                exp_base_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                exp_base_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                exp_base_item.setForeground(QColor("#1565c0"))
                table.setItem(i, 3, exp_base_item)
                
                # Col 4 - Counted
                is_own_tab = (cashier_id == self.closing_cashier_id)
                if is_own_tab and not is_slot_finalized:
                    actual_edit = QLineEdit()
                    actual_edit.setAlignment(Qt.AlignRight)
                    actual_edit.setMinimumHeight(32)
                    actual_edit.setStyleSheet("""
                        QLineEdit {
                            background: white;
                            color: #212121;
                            border: 1px solid #bdbdbd;
                            border-radius: 4px;
                            padding: 8px 10px;
                            font-size: 13px;
                        }
                        QLineEdit:focus {
                            border: 2px solid #1976d2;
                            background: white;
                            color: #212121;
                        }
                        QLineEdit:hover {
                            border: 1px solid #1976d2;
                        }
                    """)
                    if method.upper() == "ON ACCOUNT":
                        actual_edit.setEnabled(False)
                        if counted:
                            actual_edit.setText(f"{counted:.2f}")
                        actual_edit.setStyleSheet(actual_edit.styleSheet() + "background: #f5f5f5; color: #757575;")
                    elif counted > 0:
                        actual_edit.setText(f"{counted:.2f}")
                        
                    actual_edit.textChanged.connect(lambda _, r=i, tbl=table, exp_val=expected, rtb=rate_to_base: self._update_cashier_tab_variance(r, tbl, exp_val, rtb))
                    table.setCellWidget(i, 4, actual_edit)
                else:
                    actual_text = f"{counted:,.2f}" if counted > 0 else ""
                    actual_item = QTableWidgetItem(actual_text)
                    actual_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    actual_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    actual_item.setForeground(QColor("#212121"))
                    if method.upper() == "ON ACCOUNT":
                        actual_item.setBackground(QColor("#f5f5f5"))
                    table.setItem(i, 4, actual_item)

                # Col 5 - Variance
                if counted > 0 or expected > 0:
                    var_text = f"{variance:,.2f}"
                else:
                    var_text = ""
                var_item = QTableWidgetItem(var_text)
                var_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                var_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                if var_text:
                    if variance < 0:
                        var_item.setForeground(QColor("#d32f2f"))
                        var_item.setBackground(QColor("#ffebee"))
                    elif variance > 0:
                        var_item.setForeground(QColor("#388e3c"))
                        var_item.setBackground(QColor("#e8f5e9"))
                    else:
                        var_item.setForeground(QColor("#757575"))
                table.setItem(i, 5, var_item)
                
                # Col 6 - Variance (Base Currency Equivalent)
                var_base = variance * rate_to_base
                if counted > 0 or expected > 0:
                    var_base_text = f"{var_base:,.2f}"
                else:
                    var_base_text = ""
                var_base_item = QTableWidgetItem(var_base_text)
                var_base_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                var_base_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                if var_base_text:
                    if var_base < 0:
                        var_base_item.setForeground(QColor("#d32f2f"))
                        var_base_item.setBackground(QColor("#ffebee"))
                    elif var_base > 0:
                        var_base_item.setForeground(QColor("#388e3c"))
                        var_base_item.setBackground(QColor("#e8f5e9"))
                    else:
                        var_base_item.setForeground(QColor("#757575"))
                table.setItem(i, 6, var_base_item)
                
                # Col 7 - Transaction Count
                tx_item = QTableWidgetItem(str(count))
                tx_item.setTextAlignment(Qt.AlignCenter)
                tx_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                tx_item.setForeground(QColor("#212121"))
                table.setItem(i, 7, tx_item)
                
                table.setRowHeight(i, 40)

            # Add TOTAL row at the bottom
            total_row_idx = len(payment_methods)
            
            tot_label = QTableWidgetItem("TOTAL")
            font = QFont()
            font.setBold(True)
            tot_label.setFont(font)
            tot_label.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            bg_color = QColor("#e0e0e0")
            tot_label.setBackground(bg_color)
            tot_label.setForeground(QColor("#212121"))
            table.setItem(total_row_idx, 0, tot_label)
            
            tot_curr_item = QTableWidgetItem("")
            tot_curr_item.setBackground(bg_color)
            tot_curr_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            table.setItem(total_row_idx, 1, tot_curr_item)
            
            for col in range(2, 8):
                item = QTableWidgetItem("0.00" if col < 7 else "0")
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                item.setFont(font)
                item.setBackground(bg_color)
                item.setForeground(QColor("#212121"))
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                table.setItem(total_row_idx, col, item)
            
            table.setRowHeight(total_row_idx, 36)
        
        layout.addWidget(table)
        
        # Initial calculation of the TOTAL row
        if payment_methods:
            self._update_cashier_tab_totals(table)
        

        # Add tab with cashier name
        tab_name = cashier_name[:20] if cashier_name else "Unknown"
        self.tab_widget.addTab(tab, tab_name)

    def _update_cashier_tab_variance(self, row, table, expected, rate_to_base):
        try:
            actual_edit = table.cellWidget(row, 4)
            if not actual_edit:
                return
            
            actual_text = actual_edit.text().strip()
            var_item = table.item(row, 5)
            if not var_item:
                var_item = QTableWidgetItem("")
                var_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                var_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                table.setItem(row, 5, var_item)
                
            var_base_item = table.item(row, 6)
            if not var_base_item:
                var_base_item = QTableWidgetItem("")
                var_base_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                var_base_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                table.setItem(row, 6, var_base_item)
                
            if not actual_text:
                var_item.setText("")
                var_item.setForeground(QColor("#757575"))
                var_item.setBackground(QColor("white"))
                var_base_item.setText("")
                var_base_item.setForeground(QColor("#757575"))
                var_base_item.setBackground(QColor("white"))
            else:
                actual = float(actual_text)
                variance = actual - expected
                var_base = variance * rate_to_base
                
                var_item.setText(f"{variance:,.2f}")
                var_base_item.setText(f"{var_base:,.2f}")
                
                if variance < 0:
                    var_item.setForeground(QColor("#d32f2f"))
                    var_item.setBackground(QColor("#ffebee"))
                    var_base_item.setForeground(QColor("#d32f2f"))
                    var_base_item.setBackground(QColor("#ffebee"))
                elif variance > 0:
                    var_item.setForeground(QColor("#388e3c"))
                    var_item.setBackground(QColor("#e8f5e9"))
                    var_base_item.setForeground(QColor("#388e3c"))
                    var_base_item.setBackground(QColor("#e8f5e9"))
                else:
                    var_item.setForeground(QColor("#757575"))
                    var_item.setBackground(QColor("white"))
                    var_base_item.setForeground(QColor("#757575"))
                    var_base_item.setBackground(QColor("white"))
                    
            self._update_cashier_tab_totals(table)
            
        except ValueError:
            pass

    def _update_cashier_tab_totals(self, table):
        """Update the inline TOTAL row for a cashier tab."""
        total_row = table.rowCount() - 1
        if total_row < 0:
            return
            
        tot_exp, tot_exp_base = 0.0, 0.0
        tot_cnt = 0.0
        tot_var, tot_var_base = 0.0, 0.0
        tot_tx = 0
        
        for r in range(total_row):
            # Expected (Col 2)
            exp_item = table.item(r, 2)
            if exp_item:
                tot_exp += float(exp_item.text().replace(",", "") or 0)
                
            # Expected Base (Col 3)
            exp_base_item = table.item(r, 3)
            if exp_base_item:
                tot_exp_base += float(exp_base_item.text().replace(",", "") or 0)
                
            # Counted (Col 4)
            edit = table.cellWidget(r, 4)
            cnt_item = table.item(r, 4)
            if edit:
                tot_cnt += float(edit.text().strip().replace(",", "") or 0)
            elif cnt_item:
                tot_cnt += float(cnt_item.text().strip().replace(",", "") or 0)
                
            # Variance Base (Col 6)
            var_base_item = table.item(r, 6)
            if var_base_item and var_base_item.text().strip():
                tot_var_base += float(var_base_item.text().replace(",", "") or 0)
                
            # Transaction Count (Col 7)
            tx_item = table.item(r, 7)
            if tx_item:
                tot_tx += int(tx_item.text().replace(",", "") or 0)
                
        tot_var = tot_cnt - tot_exp
        
        # Update the TOTAL row
        table.item(total_row, 2).setText(f"{tot_exp:,.2f}")
        table.item(total_row, 3).setText(f"{tot_exp_base:,.2f}")
        table.item(total_row, 4).setText(f"{tot_cnt:,.2f}")
        table.item(total_row, 5).setText(f"{tot_var:,.2f}")
        table.item(total_row, 6).setText(f"{tot_var_base:,.2f}")
        table.item(total_row, 7).setText(str(tot_tx))

    def _on_finalize_cashier_count(self, cashier_id, cashier_name, table):
        # 1. Validate inputs in the cashier's table
        counted_data = {}
        expected_data = {}
        for row in range(table.rowCount()):
            method_item = table.item(row, 0)
            if not method_item:
                continue
            method_base = method_item.text().strip().upper()
            
            curr_item = table.item(row, 1)
            currency = curr_item.text().strip() if curr_item else "USD"
            
            # The database needs the original method name for reconciliation matching, 
            # but printing needs the currency. We will append it later for printing.
            method_name = method_base
            
            # Expected is stored in column 2
            exp_item = table.item(row, 2)
            expected_val = 0.0
            if exp_item:
                try:
                    expected_val = float(exp_item.text().replace(",", ""))
                except ValueError:
                    pass
            expected_data[method_name] = expected_val
            
            # Counted/Actual is in column 4
            counted_val = 0.0
            actual_edit = table.cellWidget(row, 4)
            if actual_edit:
                text = actual_edit.text().strip()
                if text:
                    try:
                        counted_val = float(text)
                    except ValueError:
                        QMessageBox.warning(self, "Invalid Amount", f"Payment method '{method_name}' has an invalid amount: '{text}'")
                        actual_edit.setFocus()
                        return
            else:
                # In case it is read-only or was already saved
                actual_item = table.item(row, 4)
                if actual_item and actual_item.text().strip():
                    try:
                        counted_val = float(actual_item.text().replace(",", ""))
                    except ValueError:
                        pass
            counted_data[method_name] = counted_val

        # 2. Confirm finalization of their count
        confirm = QMessageBox.question(
            self,
            "Confirm Cashier Finalization",
            f"Are you sure you want to finalize your cashier count slot?\n\n"
            "This will lock your counts for this shift and submit them to the system.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        # 3. Save to database
        from models.shift import save_cashier_reconciliation
        success = save_cashier_reconciliation(
            shift_id=self._active_shift["id"],
            cashier_id=cashier_id,
            cashier_name=cashier_name,
            counted_json=json.dumps(counted_data),
            is_finalized=True
        )
        
        if success:
            # Re-load data to update visual state
            self._refresh_shift()
            self._load_data()

            # 4. Print the cashier's slip automatically!
            try:
                from services.printing_service import PrintingService
                from views.dialogs.settings_dialog import _load_hw
                hw = _load_hw()
                printer_name = hw.get("main_printer", None)
                if printer_name == "(None)":
                    printer_name = None
                
                # Build currency-aware data for printing
                print_expected_data = {}
                print_counted_data = {}
                for r_idx in range(table.rowCount()):
                    m_item = table.item(r_idx, 0)
                    if not m_item: continue
                    m_base = m_item.text().strip().upper()
                    c_item = table.item(r_idx, 1)
                    curr = c_item.text().strip() if c_item else "USD"
                    
                    if curr.upper() not in ("USD", "US"):
                        p_name = f"{m_base} ({curr.upper()})"
                    else:
                        p_name = m_base
                        
                    if m_base in expected_data:
                        print_expected_data[p_name] = expected_data[m_base]
                    if m_base in counted_data:
                        print_counted_data[p_name] = counted_data[m_base]
                
                ps = PrintingService()
                ps.print_cashier_reconciliation(
                    shift_id=self._active_shift["id"],
                    cashier_id=cashier_id,
                    cashier_name=cashier_name,
                    expected_data=print_expected_data,
                    counted_data=print_counted_data,
                    printer_name=printer_name
                )
            except Exception as pe:
                print(f"[ERROR] Failed to print cashier reconciliation: {pe}")

            QMessageBox.information(
                self,
                "Success",
                "Your count has been successfully finalized, locked, and printed!"
            )
        else:
            QMessageBox.critical(
                self,
                "Error",
                "Failed to save your count to the database. Please try again."
            )

    def _on_modify_cashier_count(self, cashier_id, cashier_name):
        # 1. Ask for PIN
        pin, ok = QInputDialog.getText(
            self, "PIN Required", "Enter PIN to unlock & modify count:",
            QLineEdit.Password
        )
        if not ok or not pin:
            return
            
        # 2. Authenticate PIN and check if they have reconciliation permissions
        from models.user import authenticate_by_pin, is_admin
        admin_user = authenticate_by_pin(pin)
        if not admin_user or (not is_admin(admin_user) and not admin_user.get("allow_shift_reconciliation", False)):
            QMessageBox.warning(self, "Access Denied", "Incorrect PIN or insufficient permissions.")
            return

        # 2.5 Ask for modify reason
        reason, ok = QInputDialog.getText(
            self, "Reason Required", f"Enter reason for modifying {cashier_name}'s count:",
            QLineEdit.Normal
        )
        if not ok or not reason.strip():
            QMessageBox.warning(self, "Required", "A reason for modifying the count is mandatory.")
            return

        # 3. Retrieve current counted_data to preserve it
        from models.shift import get_cashier_reconciliation, save_cashier_reconciliation
        recorded = get_cashier_reconciliation(self._active_shift["id"], cashier_id)
        counted_json = "{}"
        if recorded:
            counted_json = recorded.get("counted_json", "{}")

        # 4. Save with is_finalized = False
        success = save_cashier_reconciliation(
            shift_id=self._active_shift["id"],
            cashier_id=cashier_id,
            cashier_name=cashier_name,
            counted_json=counted_json,
            is_finalized=False,
            is_modified=True,
            modify_reason=reason.strip()
        )
        
        if success:
            QMessageBox.information(
                self, "Reconciliation Unlocked", 
                f"Cashier {cashier_name}'s count has been unlocked. You can now modify and finalize the counts again."
            )
            # Reload the view so the UI shows input fields again!
            self._refresh_shift()
            self._load_data()
        else:
            QMessageBox.critical(self, "Error", "Failed to unlock cashier reconciliation.")

    def _update_variance(self, row):
        try:
            exp_item = self.table.item(row, 2)          # Col 2 - Expected (Native)
            actual_edit = self.table.cellWidget(row, 4) # Col 4 - Actual widget
            actual_item = self.table.item(row, 4)       # Col 4 - Actual item
            curr_item = self.table.item(row, 1)

            if not exp_item:
                return

            curr = curr_item.text().strip() if curr_item else "USD"
            base_ccy = get_company_base_currency() or "USD"
            rate_to_base = _get_local_rate(curr, base_ccy)

            expected = float(exp_item.text().replace(",", "")) if exp_item.text() else 0
            actual_text = ""
            if actual_edit:
                actual_text = actual_edit.text().strip()
            elif actual_item:
                actual_text = actual_item.text().replace(",", "").strip()

            var_item = self.table.item(row, 5)        # Col 5 - Variance (Native)
            var_base_item = self.table.item(row, 6)   # Col 6 - Variance (Base)

            if not var_item:
                var_item = QTableWidgetItem("")
                var_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                var_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.table.setItem(row, 5, var_item)

            if not var_base_item:
                var_base_item = QTableWidgetItem("")
                var_base_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                var_base_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.table.setItem(row, 6, var_base_item)

            if not actual_text:
                var_item.setText("")
                var_item.setForeground(QColor("#757575"))
                var_item.setBackground(QColor("white"))
                var_base_item.setText("")
                var_base_item.setForeground(QColor("#757575"))
                var_base_item.setBackground(QColor("white"))
            else:
                actual = float(actual_text)
                variance = actual - expected
                var_base = variance * rate_to_base

                var_item.setText(f"{variance:,.2f}")
                if variance < 0:
                    var_item.setForeground(QColor("#d32f2f"))
                    var_item.setBackground(QColor("#ffebee"))
                elif variance > 0:
                    var_item.setForeground(QColor("#388e3c"))
                    var_item.setBackground(QColor("#e8f5e9"))
                else:
                    var_item.setForeground(QColor("#757575"))
                    var_item.setBackground(QColor("white"))

                var_base_item.setText(f"{var_base:,.2f}")
                if var_base < 0:
                    var_base_item.setForeground(QColor("#d32f2f"))
                    var_base_item.setBackground(QColor("#ffebee"))
                elif var_base > 0:
                    var_base_item.setForeground(QColor("#388e3c"))
                    var_base_item.setBackground(QColor("#e8f5e9"))
                else:
                    var_base_item.setForeground(QColor("#757575"))
                    var_base_item.setBackground(QColor("white"))

        except ValueError:
            pass

        self._update_summary()

    def _update_summary(self):
        base_ccy = get_company_base_currency() or "USD"
        currency_totals = {}
        base_expected_total = 0.0
        base_counted_total = 0.0
        raw_expected_total = 0.0
        raw_counted_total = 0.0
        
        total_row_idx = self.table.rowCount() - 1 if self.table.rowCount() > 0 else -1
        data_rows_count = total_row_idx if total_row_idx >= 0 else 0
        
        for row in range(data_rows_count):
            try:
                name_item = self.table.item(row, 0)
                if name_item and name_item.text().startswith("TOTAL"):
                    continue
                exp_item = self.table.item(row, 2)       # Col 2 - Expected
                actual_edit = self.table.cellWidget(row, 4)  # Col 4 - Actual widget
                actual_item = self.table.item(row, 4)     # Col 4 - Actual item
                curr_item = self.table.item(row, 1)      # Col 1 - Currency
                
                currency = curr_item.text().strip() if curr_item else ""
                if not currency:
                    currency = get_payment_method_currency(exp_item.text() if exp_item else "")
                expected = float(exp_item.text().replace(",", "")) if exp_item and exp_item.text() else 0.0
                
                actual = 0.0
                if actual_edit:
                    actual_text = actual_edit.text().strip()
                    actual = float(actual_text) if actual_text else 0.0
                elif actual_item:
                    actual_text = actual_item.text().replace(",", "").strip()
                    actual = float(actual_text) if actual_text else 0.0
                
                if currency not in currency_totals:
                    currency_totals[currency] = {"expected": 0.0, "counted": 0.0}
                currency_totals[currency]["expected"] += expected
                currency_totals[currency]["counted"] += actual

                raw_expected_total += expected
                raw_counted_total += actual

                # Accumulate base currency equivalent totals
                rate_to_base = _get_local_rate(currency, base_ccy)
                base_expected_total += expected * rate_to_base
                base_counted_total += actual * rate_to_base
            except Exception as e:
                print(f"[DEBUG] Error in _update_summary row {row}: {e}")
        
        # Populate / Update the INLINE TOTAL ROW at the bottom of the table
        if total_row_idx >= 0:
            bg_color = QColor("#eceff1")
            font = QFont()
            font.setBold(True)

            tot_name_item = QTableWidgetItem("TOTAL")
            tot_name_item.setFont(font)
            tot_name_item.setForeground(QColor("#0d47a1"))
            tot_name_item.setBackground(bg_color)
            tot_name_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(total_row_idx, 0, tot_name_item)

            tot_curr_item = QTableWidgetItem("")
            tot_curr_item.setTextAlignment(Qt.AlignCenter)
            tot_curr_item.setFont(font)
            tot_curr_item.setForeground(QColor("#0d47a1"))
            tot_curr_item.setBackground(bg_color)
            tot_curr_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(total_row_idx, 1, tot_curr_item)

            native_exp_text = f"{raw_expected_total:,.2f}"
            native_cnt_text = f"{raw_counted_total:,.2f}"
            raw_var = raw_counted_total - raw_expected_total
            native_var_text = f"{raw_var:,.2f}"

            tot_exp_item = QTableWidgetItem(native_exp_text)
            tot_exp_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            tot_exp_item.setFont(font)
            tot_exp_item.setForeground(QColor("#212121"))
            tot_exp_item.setBackground(bg_color)
            tot_exp_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(total_row_idx, 2, tot_exp_item)

            # Col 3: Expected Base Total
            tot_exp_base_item = QTableWidgetItem(f"{base_expected_total:,.2f}")
            tot_exp_base_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            tot_exp_base_item.setFont(font)
            tot_exp_base_item.setForeground(QColor("#1565c0"))
            tot_exp_base_item.setBackground(bg_color)
            tot_exp_base_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(total_row_idx, 3, tot_exp_base_item)

            # Col 4: Actual Native
            tot_act_item = QTableWidgetItem(native_cnt_text)
            tot_act_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            tot_act_item.setFont(font)
            tot_act_item.setForeground(QColor("#212121"))
            tot_act_item.setBackground(bg_color)
            tot_act_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(total_row_idx, 4, tot_act_item)

            # Col 5: Variance Native
            tot_var_item = QTableWidgetItem(native_var_text)
            tot_var_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            tot_var_item.setFont(font)
            tot_var_item.setForeground(QColor("#212121"))
            tot_var_item.setBackground(bg_color)
            tot_var_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(total_row_idx, 5, tot_var_item)

            # Col 6: Variance Base Total
            base_variance_total = base_counted_total - base_expected_total
            tot_var_base_text = f"{base_variance_total:,.2f}" if (base_counted_total > 0 or base_expected_total > 0) else ""
            tot_var_base_item = QTableWidgetItem(tot_var_base_text)
            tot_var_base_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            tot_var_base_item.setFont(font)
            tot_var_base_item.setBackground(bg_color)
            tot_var_base_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            if base_variance_total < 0:
                tot_var_base_item.setForeground(QColor("#d32f2f"))
            elif base_variance_total > 0:
                tot_var_base_item.setForeground(QColor("#388e3c"))
            else:
                tot_var_base_item.setForeground(QColor("#212121"))
            self.table.setItem(total_row_idx, 6, tot_var_base_item)

            self.table.setRowHeight(total_row_idx, 36)

            self.table.setRowHeight(total_row_idx, 36)


    def _clean_for_json(self, obj):
        """Recursively clean objects for JSON serialization."""
        if isinstance(obj, datetime):
            return obj.strftime("%Y-%m-%d %H:%M:%S")
        if hasattr(obj, 'strftime'):  # date object
            return obj.strftime("%Y-%m-%d")
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, dict):
            return {k: self._clean_for_json(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [self._clean_for_json(item) for item in obj]
        return obj

    def _build_reconciliation_data(self, totals: list) -> dict:
        """Build complete reconciliation data structure including ALL cashiers."""
        
        print("\n" + "="*80)
        print("DEBUG: _build_reconciliation_data - START")
        print("="*80)

        shift_id = self._active_shift.get("id")

        # Get all recorded cashier counts from the database
        from models.shift import get_all_cashier_reconciliations_for_shift
        recorded_cashiers = {rc["cashier_id"]: rc for rc in get_all_cashier_reconciliations_for_shift(shift_id)}

        # Load global expected maps to calculate prorated expected per cashier
        global_expected_map = {}
        global_currency_map = {}
        for sr in self._active_shift.get("rows", []):
            m_key = sr["method"].strip().upper()
            global_expected_map[m_key] = float(sr.get("total", 0.0))
            global_currency_map[m_key] = sr.get("currency", "USD")

        cashier_sales = self._active_shift.get("cashier_sales", [])
        
        # Build global collected maps across all cashiers
        global_collected_map = {}
        for cashier in cashier_sales:
            cashier_payment_methods = cashier.get("totals", {}).get("payment_methods", {})
            cashier_credit_total = 0.0
            for sale in cashier.get("sales", []):
                if sale.get("is_on_account", False) and sale.get("total", 0) > sale.get("tendered", 0):
                    cashier_credit_total += sale.get("total", 0) - sale.get("tendered", 0)
            
            c_methods = dict(cashier_payment_methods)
            if cashier_credit_total > 0:
                c_methods["ON ACCOUNT"] = cashier_credit_total
                
            for m, amt in c_methods.items():
                m_key = m.strip().upper()
                global_collected_map[m_key] = global_collected_map.get(m_key, 0.0) + float(amt)

        # Harvest payment method totals from the main summary table first
        payment_methods = []
        main_counted_map = {}
        for row in range(self.table.rowCount()):
            method = self.table.item(row, 0).text()
            method_upper = method.strip().upper()
            currency = self.table.item(row, 1).text() if self.table.item(row, 1) else "USD"
            expected = float(self.table.item(row, 2).text().replace(",", "")) if self.table.item(row, 2) else 0
            
            # Read counted values directly from the main table's editable input!
            actual_edit = self.table.cellWidget(row, 4)
            actual_item = self.table.item(row, 4)
            if actual_edit and actual_edit.text().strip():
                counted_val = float(actual_edit.text().replace(",", ""))
            elif actual_item and actual_item.text().strip():
                counted_val = float(actual_item.text().replace(",", ""))
            else:
                counted_val = 0.0
            
            main_counted_map[method_upper] = counted_val
            payment_methods.append({
                "method": str(method),
                "currency": str(currency),
                "expected": float(expected),
                "counted": float(counted_val),
                "variance": float(counted_val - expected)
            })

        cashier_details = []
        for cashier in cashier_sales:
            cashier_id = cashier.get("cashier_id")
            cashier_name = cashier.get("cashier_name", "Unknown")
            cashier_payment_methods = cashier.get("totals", {}).get("payment_methods", {})
            
            cashier_credit_total = 0.0
            for sale in cashier.get("sales", []):
                if sale.get("is_on_account", False) and sale.get("total", 0) > sale.get("tendered", 0):
                    cashier_credit_total += sale.get("total", 0) - sale.get("tendered", 0)
            
            if cashier_credit_total > 0:
                cashier_payment_methods = dict(cashier_payment_methods)
                cashier_payment_methods["ON ACCOUNT"] = cashier_credit_total
            
            if not cashier_payment_methods:
                continue

            # Load actual counted counts for this cashier from the DB
            rc_record = recorded_cashiers.get(cashier_id, {})
            counted_data = rc_record.get("counted_data", {})
            is_finalized = bool(rc_record.get("is_finalized", 0))

            rows = []
            for method_key, amount_collected in cashier_payment_methods.items():
                method_upper = method_key.strip().upper()
                amount_collected = float(amount_collected)
                total_collected = global_collected_map.get(method_upper, 0.0)
                proportion = (amount_collected / total_collected) if total_collected > 0 else 0.0

                cashier_expected = global_expected_map.get(method_upper, 0.0) * proportion
                
                # If cashier has explicit count session, use that count.
                # Otherwise, map from main summary table counted amount (prorated if multi-cashier).
                if method_upper in counted_data:
                    cashier_counted = float(counted_data[method_upper])
                elif is_finalized:
                    cashier_counted = 0.0
                elif method_upper in main_counted_map:
                    if len(cashier_sales) <= 1:
                        cashier_counted = main_counted_map[method_upper]
                    else:
                        cashier_counted = main_counted_map[method_upper] * proportion
                else:
                    cashier_counted = cashier_expected
                    
                variance = cashier_counted - cashier_expected

                tx_count = 0
                for sale in cashier.get("sales", []):
                    for pm in sale.get("payment_methods", []):
                        if pm.strip().upper() == method_upper:
                            tx_count += 1
                            break
                    if method_upper == "ON ACCOUNT" and sale.get("is_on_account", False):
                        tx_count += 1

                rows.append({
                    "method": method_key,
                    "currency": global_currency_map.get(method_upper, "USD"),
                    "expected": round(cashier_expected, 2),
                    "counted": round(cashier_counted, 2),
                    "collected": round(amount_collected, 2),
                    "variance": round(variance, 2),
                    "transaction_count": tx_count,
                })

            rows.sort(key=lambda r: r["method"])
            total_exp = sum(r["expected"] for r in rows)
            total_cnt = sum(r["counted"] for r in rows)

            cashier_details.append({
                "cashier_id": cashier_id,
                "cashier_name": cashier_name,
                "total_sales": float(cashier.get("totals", {}).get("total_sales", 0)),
                "total_items": int(cashier.get("totals", {}).get("total_items", 0)),
                "transaction_count": len(cashier.get("sales", [])),
                "total_expected": round(total_exp, 2),
                "total_counted": round(total_cnt, 2),
                "total_variance": round(total_cnt - total_exp, 2),
                "rows": rows,
                "payment_breakdown": rows,
            })
        
        # Calculate global totals across all payment methods
        total_expected = sum(p["expected"] for p in payment_methods)
        total_counted = sum(p["counted"] for p in payment_methods)
        
        raw_start = self._active_shift.get("start_time") or self._active_shift.get("created_at")
        if raw_start and hasattr(raw_start, 'strftime'):
            start_time_str = raw_start.strftime("%H:%M:%S")
        elif isinstance(raw_start, str) and raw_start:
            start_time_str = raw_start.split("T")[-1].split(" ")[-1][:8] if "T" in raw_start else raw_start[:8]
        else:
            start_time_str = "-"
        
        shift_date = self._active_shift.get("date", "")
        if hasattr(shift_date, 'strftime'):
            shift_date = shift_date.strftime("%Y-%m-%d")
        
        data = {
            "shift_id": int(shift_id) if shift_id else None,
            "shift_number": int(self._active_shift.get("shift_number", 0)),
            "date": str(shift_date),
            "start_time": str(start_time_str),
            "end_time": str(datetime.now().strftime("%H:%M:%S")),
            "closing_cashier_id": int(self.closing_cashier_id) if self.closing_cashier_id else None,
            "closing_cashier_name": str(self.closing_cashier_name or ""),
            "total_expected": float(total_expected),
            "total_counted": float(total_counted),
            "total_variance": float(total_counted - total_expected),
            "payment_methods": payment_methods,
            "cashiers": cashier_details,
            "closed_at": str(datetime.now().isoformat())
        }
        
        return self._clean_for_json(data)

    def _on_finalize(self):
        if not self.can_reconcile_shift:
            QMessageBox.critical(
                self,
                "Permission Denied",
                "You do not have permission to finalize and close the entire shift."
            )
            return

        # ── Restaurant Check ──────────────────────────────────────────────────
        try:
            from models.restaurant_order import get_active_orders
            active_tables = get_active_orders()
            if active_tables:
                table_list = "\n".join([f"• Table {t.get('table_number')} (ORD-{t.get('id')})" for t in active_tables[:10]])
                if len(active_tables) > 10:
                    table_list += f"\n... and {len(active_tables)-10} more."
                
                QMessageBox.critical(
                    self, 
                    "Open Tables Found",
                    f"You cannot close the shift while there are open restaurant tables.\n\n"
                    f"Please settle or cancel these orders first:\n{table_list}"
                )
                return
        except Exception as _e:
            print(f"[ShiftRecon] Active tables check failed: {_e}")

        # 2. Check for unfinalized cashiers who worked this shift
        # bypassed: user requested money insertion directly on the main tab to act as the sole "close shift" dialog.

        # 3. Confirm close shift
        confirm = QMessageBox.question(
            self, 
            "Confirm Close Shift",
            "Are you sure you want to close this shift?\n\n"
            "This action cannot be undone and will save the reconciliation data.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if confirm != QMessageBox.StandardButton.Yes:
            print("[DEBUG] User cancelled shift closure")
            return

        try:
            from models.shift import end_shift, get_active_shift, save_shift_reconciliation
            
            active = get_active_shift()
            if not active:
                QMessageBox.warning(self, "Error", "No active shift found.")
                return

            print(f"\n[DEBUG] Active shift ID: {active['id']}, Number: {active.get('shift_number')}")

            reconciliation_data = self._build_reconciliation_data([])
            
            print("\n[DEBUG] Reconciliation data before save:")
            print(f"  cashiers count: {len(reconciliation_data.get('cashiers', []))}")
            for c in reconciliation_data.get('cashiers', []):
                print(f"    {c.get('cashier_name')}:")
                print(f"      total_expected: {c.get('total_expected')}")
                print(f"      total_counted: {c.get('total_counted')}")
                print(f"      rows count: {len(c.get('rows', []))}")
                for r in c.get('rows', []):
                    print(f"        {r.get('method')}: expected={r.get('expected')}, counted={r.get('counted')}, variance={r.get('variance')}")
            
            reconciliation_id = save_shift_reconciliation(active["id"], reconciliation_data)
            
            if reconciliation_id:
                print(f"[OK] Reconciliation saved with ID: {reconciliation_id}")
                self._reconciliation_id = reconciliation_id
            else:
                print("[!] Failed to save reconciliation")
            
            # Compile composite key counted map for end_shift
            counted_map = {}
            for pm in reconciliation_data.get("payment_methods", []):
                method_name = pm["method"]
                # Look up the currency from the table
                currency = "USD"
                for r in range(self.table.rowCount()):
                    if self.table.item(r, 0).text().strip().upper() == method_name.strip().upper():
                        currency = self.table.item(r, 1).text()
                        break
                counted_map[(method_name, currency)] = pm["counted"]

            print(f"\n[DEBUG] Closing shift with counted_map (composite keys): {counted_map}")
            closed_shift = end_shift(active["id"], counted_map)
            
            if not closed_shift:
                QMessageBox.warning(self, "Error", "Failed to close shift.")
                return

            print("\n[DEBUG] Attempting to print shift reconciliation...")
            try:
                from services.printing_service import printing_service
                from models.advance_settings import AdvanceSettings
                
                settings = AdvanceSettings.load_from_file()
                printer_name = getattr(settings, "receiptPrinterName", None)
                
                # Build simple totals list for backward compatibility in printer service
                totals = []
                for pm in reconciliation_data.get("payment_methods", []):
                    currency = "USD"
                    for r in range(self.table.rowCount()):
                        if self.table.item(r, 0).text().strip().upper() == pm["method"].strip().upper():
                            currency = self.table.item(r, 1).text()
                            break
                    totals.append({
                        "method": pm["method"],
                        "currency": currency,
                        "expected": pm["expected"],
                        "actual": pm["counted"],
                        "variance": pm["variance"]
                    })
                
                printing_service.print_shift_reconciliation(
                    shift=closed_shift,
                    totals=totals,
                    reconciliation_data=reconciliation_data,
                    printer_name=printer_name
                )
                
                try:
                    from models.shift import update_reconciliation_print_status
                    update_reconciliation_print_status(reconciliation_id, True)
                    print("[DEBUG] Print status updated in database")
                except Exception as e:
                    print(f"[DEBUG] Failed to update print status: {e}")
                
            except Exception as print_err:
                print(f"[DEBUG] Print error: {print_err}")
                traceback.print_exc()
                QMessageBox.warning(
                    self, 
                    "Print Warning",
                    f"Shift closed but receipt printing failed:\n{print_err}"
                )

            QMessageBox.information(
                self,
                "Success",
                f"Shift #{active.get('shift_number')} closed successfully.\n\nReconciliation ID: {reconciliation_id}"
            )
            print("="*80)
            print("DEBUG: _on_finalize - SUCCESS")
            print("="*80 + "\n")
            self.accept()


        except Exception as e:
            print(f"[DEBUG] Error in _on_finalize: {e}")
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to close shift: {str(e)}")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if hasattr(self, 'finalize_btn') and self.finalize_btn.isEnabled():
                self._on_cashier_finalize_only()
            elif hasattr(self, 'close_btn') and self.close_btn.isEnabled():
                self._on_finalize()
        else:
            super().keyPressEvent(event)

    def _build_cashier_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(25, 25, 25, 25)

        # Header
        header = QLabel(f"Finalize Count - {self.closing_cashier_name}")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #1976d2; padding-bottom: 15px; border-bottom: 2px solid #1976d2;")
        layout.addWidget(header)

        instr = QLabel("Please enter the amount you have counted for each payment method:")
        instr.setStyleSheet("font-weight: bold; color: #212121; font-size: 14px;")
        layout.addWidget(instr)

        # Simple table
        self.cashier_table = QTableWidget(0, 3)
        self.cashier_table.setHorizontalHeaderLabels(["Payment Method", "Currency", "Counted Amount"])
        self.cashier_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.cashier_table.setColumnWidth(1, 100)
        self.cashier_table.setColumnWidth(2, 200)
        self.cashier_table.setAlternatingRowColors(True)
        self.cashier_table.setSelectionMode(QAbstractItemView.NoSelection)
        layout.addWidget(self.cashier_table)

        # Bottom buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)
        
        self.finalize_btn = QPushButton("Finalize Count")
        self.finalize_btn.setObjectName("closeBtn")
        self.finalize_btn.clicked.connect(self._on_cashier_finalize_only)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("cancelBtn")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.finalize_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _load_cashier_data(self):
        if not self._active_shift:
            QMessageBox.warning(self, "No Active Shift", "No open shift was found.")
            self.finalize_btn.setEnabled(False)
            return

        from models.shift import get_cashier_sales_for_shift, get_cashier_reconciliation
        shift_id = self._active_shift["id"]
        cashiers = get_cashier_sales_for_shift(shift_id)
        
        my_data = next((c for c in cashiers if c.get("cashier_id") == self.closing_cashier_id), None)
        if not my_data:
            QMessageBox.warning(self, "No Sales", "You have no recorded sales for this shift.")
            self.finalize_btn.setEnabled(False)
            return

        recorded = get_cashier_reconciliation(shift_id, self.closing_cashier_id)
        if recorded and recorded.get("is_finalized"):
            QMessageBox.information(self, "Already Finalized", "Your count for this shift is already finalized and locked.")
            self.finalize_btn.setEnabled(False)
            self.finalize_btn.setText("Already Finalized")
            
        payment_methods = my_data.get("totals", {}).get("payment_methods", {})
        
        cashier_credit_total = 0.0
        for sale in my_data.get("sales", []):
            if sale.get("is_on_account", False) and sale.get("total", 0) > sale.get("tendered", 0):
                cashier_credit_total += sale.get("total", 0) - sale.get("tendered", 0)
        
        if cashier_credit_total > 0:
            payment_methods = dict(payment_methods)
            payment_methods["ON ACCOUNT"] = cashier_credit_total

        if not payment_methods:
            QMessageBox.warning(self, "No Methods", "No payment methods used.")
            self.finalize_btn.setEnabled(False)
            return

        self.cashier_table.setRowCount(len(payment_methods))
        self.cashier_expected_data = {}
        
        global_expected_map = {}
        global_currency_map = {}
        for sr in self._active_shift.get("rows", []):
            m_key = sr["method"].strip().upper()
            global_expected_map[m_key] = float(sr.get("total", 0.0))
            global_currency_map[m_key] = sr.get("currency", "USD")
            
        global_collected_map = {}
        for ac in cashiers:
            ac_methods = ac.get("totals", {}).get("payment_methods", {})
            ac_credit_total = 0.0
            for sale in ac.get("sales", []):
                if sale.get("is_on_account", False) and sale.get("total", 0) > sale.get("tendered", 0):
                    ac_credit_total += sale.get("total", 0) - sale.get("tendered", 0)
            ac_m = dict(ac_methods)
            if ac_credit_total > 0: ac_m["ON ACCOUNT"] = ac_credit_total
            for m, amt in ac_m.items():
                m_key = m.strip().upper()
                global_collected_map[m_key] = global_collected_map.get(m_key, 0.0) + float(amt)

        for i, (method, amount) in enumerate(payment_methods.items()):
            method_upper = method.strip().upper()
            amount_collected = float(amount)
            total_collected = global_collected_map.get(method_upper, 0.0)
            proportion = (amount_collected / total_collected) if total_collected > 0 else 0.0
            expected = global_expected_map.get(method_upper, 0.0) * proportion
            self.cashier_expected_data[method_upper] = expected
            
            currency = get_payment_method_currency(method)

            m_item = QTableWidgetItem(method)
            m_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            font = QFont(); font.setBold(True); m_item.setFont(font)
            self.cashier_table.setItem(i, 0, m_item)

            c_item = QTableWidgetItem(currency)
            c_item.setTextAlignment(Qt.AlignCenter)
            c_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.cashier_table.setItem(i, 1, c_item)

            if method_upper == "ON ACCOUNT":
                item = QTableWidgetItem(f"{amount_collected:.2f}")
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.cashier_table.setItem(i, 2, item)
            else:
                edit = QLineEdit()
                edit.setAlignment(Qt.AlignRight)
                edit.setMinimumHeight(32)
                self.cashier_table.setCellWidget(i, 2, edit)

            self.cashier_table.setRowHeight(i, 45)

    def _on_cashier_finalize_only(self):
        counted_data = {}
        for row in range(self.cashier_table.rowCount()):
            m_item = self.cashier_table.item(row, 0)
            if not m_item: continue
            method_name = m_item.text().strip()
            method_upper = method_name.upper()

            counted_val = 0.0
            if method_upper == "ON ACCOUNT":
                item = self.cashier_table.item(row, 2)
                if item: counted_val = float(item.text().replace(",",""))
            else:
                edit = self.cashier_table.cellWidget(row, 2)
                if edit:
                    text = edit.text().strip()
                    if text:
                        try:
                            counted_val = float(text)
                        except ValueError:
                            QMessageBox.warning(self, "Invalid Amount", f"Please enter a valid amount for {method_name}")
                            edit.setFocus()
                            return
            counted_data[method_name] = counted_val

        confirm = QMessageBox.question(self, "Confirm Count", "Are you sure you want to finalize your count? This will lock it.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if confirm != QMessageBox.StandardButton.Yes:
            return

        from models.shift import save_cashier_reconciliation
        success = save_cashier_reconciliation(
            shift_id=self._active_shift["id"],
            cashier_id=self.closing_cashier_id,
            cashier_name=self.closing_cashier_name,
            counted_json=json.dumps(counted_data),
            is_finalized=True
        )

        if success:
            try:
                from services.printing_service import PrintingService
                from views.dialogs.settings_dialog import _load_hw
                hw = _load_hw()
                printer_name = hw.get("main_printer", None)
                if printer_name == "(None)": printer_name = None
                
                print_expected = {}
                print_counted = {}
                for row in range(self.cashier_table.rowCount()):
                    m_item = self.cashier_table.item(row, 0)
                    c_item = self.cashier_table.item(row, 1)
                    if not m_item: continue
                    m_base = m_item.text().strip().upper()
                    curr = c_item.text().strip() if c_item else ""
                    p_name = f"{m_base} ({curr.upper()})" if (curr and curr.upper() not in m_base.upper()) else m_base
                    
                    if m_base in self.cashier_expected_data:
                        print_expected[p_name] = self.cashier_expected_data[m_base]
                    if m_item.text().strip() in counted_data:
                        print_counted[p_name] = counted_data[m_item.text().strip()]
                
                ps = PrintingService()
                ps.print_cashier_reconciliation(
                    shift_id=self._active_shift["id"],
                    cashier_id=self.closing_cashier_id,
                    cashier_name=self.closing_cashier_name,
                    expected_data=print_expected,
                    counted_data=print_counted,
                    printer_name=printer_name
                )
            except Exception as e:
                print("Error printing slip:", e)
                
            QMessageBox.information(self, "Success", "Count finalized and printed successfully!")
            
            self.accept()
        else:
            QMessageBox.critical(self, "Error", "Failed to save your count.")


def show_shift_reconciliation(parent=None, cashier_id=None, cashier_name=None):
    """Helper function to show the shift reconciliation dialog."""
    dialog = ShiftReconciliationDialog(parent, cashier_id=cashier_id, cashier_name=cashier_name)
    return dialog.exec()