# =============================================================================
# views/dialogs/shift_reconciliation_dialog.py
# Complete shift reconciliation with database storage
# =============================================================================

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QLineEdit,
    QMessageBox, QPushButton, QFrame, QTabWidget, QWidget
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont
from datetime import datetime
from decimal import Decimal
import json
import traceback


class ShiftReconciliationDialog(QDialog):
    """Dialog for shift reconciliation with complete data storage."""

    def __init__(self, parent=None, cashier_id=None, cashier_name=None, closing_cashier_id=None, closing_cashier_name=None):
        super().__init__(parent)
        
        self.closing_cashier_id = closing_cashier_id or cashier_id
        # Resolve the cashier name — look it up from the DB if not passed in
        self.closing_cashier_name = closing_cashier_name or cashier_name
        if not self.closing_cashier_name and self.closing_cashier_id:
            try:
                from database.db import get_connection, fetchone_dict
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
        self.setMinimumSize(1000, 750)
        self.setModal(True)
        self._setup_styles()
        self._refresh_shift()
        self._build_ui()
        self._load_data()

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
            }
            QTableWidget::item { 
                padding: 10px 8px; 
                color: #212121;
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
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: #1976d2; 
                color: white;
            }
            QTabBar::tab:hover {
                background: #e3f2fd;
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
        layout.setSpacing(20)
        layout.setContentsMargins(25, 25, 25, 25)

        # Header
        header = QLabel("Shift Reconciliation")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #1976d2; padding-bottom: 15px; border-bottom: 2px solid #1976d2;")
        layout.addWidget(header)

        # Shift info panel
        info_frame = QFrame()
        info_frame.setStyleSheet("QFrame { background: #f5f5f5; border-radius: 6px; padding: 12px; }")
        info_layout = QHBoxLayout(info_frame)
        
        self.shift_info = QLabel("Loading shift information...")
        self.shift_info.setStyleSheet("font-size: 13px; color: #212121;")
        info_layout.addWidget(self.shift_info)
        info_layout.addStretch()
        layout.addWidget(info_frame)

        # Tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # Main reconciliation tab
        main_tab = QWidget()
        main_layout = QVBoxLayout(main_tab)
        
        instr_label = QLabel("Enter actual counted amounts for each payment method:")
        instr_label.setStyleSheet("font-weight: bold; margin-bottom: 5px; color: #212121;")
        main_layout.addWidget(instr_label)

        # Main table
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Payment Method", "Expected ($)", "Actual ($)", "Variance ($)"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setColumnWidth(1, 140)
        self.table.setColumnWidth(2, 160)
        self.table.setColumnWidth(3, 140)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        main_layout.addWidget(self.table)

        # Summary panel
        summary_frame = QFrame()
        summary_frame.setStyleSheet("QFrame { background: #f5f5f5; border-radius: 6px; margin-top: 10px; }")
        summary_layout = QHBoxLayout(summary_frame)
        
        self.summary_label = QLabel("Expected: $0.00  |  Counted: $0.00  |  Variance: $0.00")
        self.summary_label.setStyleSheet("font-weight: bold; font-size: 14px; padding: 12px;")
        summary_layout.addWidget(self.summary_label)
        main_layout.addWidget(summary_frame)

        self.tab_widget.addTab(main_tab, "Reconciliation")

        # Button panel
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        
        self.close_btn = QPushButton("Finalize & Close Shift")
        self.close_btn.setObjectName("closeBtn")
        self.close_btn.clicked.connect(self._on_finalize)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("cancelBtn")
        cancel_btn.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.close_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

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
            shift_time = "—"

        cashier_info = f" | Closing Cashier: {self.closing_cashier_name}" if self.closing_cashier_name else ""
        self.shift_info.setText(f"Shift #{shift_num}  |  {shift_date}  |  Started: {shift_time}{cashier_info}")

        # Load cashier tabs (ALL cashiers who worked this shift)
        self._load_cashier_tabs()
        
        # Load main table — build rows from MOPs (same source as payment_dialog)
        # then merge in actual income/counted from the shift rows.
        shift_id = self._active_shift.get("id")
        shift_rows = self._active_shift.get("rows", [])
        print(f"\n[DEBUG] _load_data: Found {len(shift_rows)} shift rows")

        # Build a lookup from shift rows keyed by UPPER(method)
        shift_row_by_method = {}
        for sr in shift_rows:
            key = sr.get("method", "").strip().upper()
            shift_row_by_method[key] = sr

        # Load MOPs (same query as payment_dialog._load_payment_methods)
        mop_rows = []
        try:
            from database.db import get_connection, fetchall_dicts
            _conn = get_connection()
            _cur = _conn.cursor()
            _cur.execute("""
                SELECT
                    m.name            AS mop_name,
                    m.gl_account      AS gl_account,
                    m.account_currency AS currency
                FROM modes_of_payment m
                WHERE m.gl_account IS NOT NULL
                  AND m.gl_account <> ''
                  AND m.enabled = 1
                ORDER BY m.name
            """)
            mop_rows = fetchall_dicts(_cur)
            _conn.close()
            print(f"[DEBUG] Loaded {len(mop_rows)} MOPs from modes_of_payment")
        except Exception as e:
            print(f"[DEBUG] Could not load MOPs: {e}")

        # Skip group accounts (no account_type), same as payment_dialog
        valid_mops = []
        seen_mop = set()
        for row in mop_rows:
            mop_name = (row.get("mop_name") or "").strip()
            gl_account = (row.get("gl_account") or "").strip()
            if not mop_name or not gl_account:
                continue
            key = mop_name.lower()
            if key in seen_mop:
                continue
            try:
                from database.db import get_connection as _gc, fetchone_dict as _fd
                _c = _gc(); _cu = _c.cursor()
                _cu.execute("SELECT account_type FROM gl_accounts WHERE name = ?", (gl_account,))
                _r = _fd(_cu)
                _c.close()
                if _r is not None and (_r.get("account_type") or "").strip() == "":
                    print(f"  [skip] '{gl_account}' is a group account")
                    continue
            except Exception:
                pass
            seen_mop.add(key)
            valid_mops.append(mop_name)
        print(f"[DEBUG] Valid MOPs after filtering: {valid_mops}")

        # Build method_map: start from MOPs, fill totals from shift rows.
        # Any shift method not in MOPs is still included (e.g. ON ACCOUNT).
        method_map = {}
        for mop_name in valid_mops:
            upper = mop_name.strip().upper()
            sr = shift_row_by_method.get(upper, {})
            method_map[mop_name] = {
                "method": mop_name,
                "total":   float(sr.get("total",   0.0)),
                "counted": float(sr.get("counted",  0.0)),
            }

        # Add any shift rows whose method is NOT already in method_map
        for sr in shift_rows:
            m = sr.get("method", "").strip()
            if m.upper() not in {k.upper() for k in method_map}:
                method_map[m] = {
                    "method": m,
                    "total":   float(sr.get("total",   0.0)),
                    "counted": float(sr.get("counted",  0.0)),
                }

        # Check for credit sales — add ON ACCOUNT if needed
        from models.sale import get_sales_by_shift
        credit_sales = get_sales_by_shift(shift_id) if shift_id else []
        on_account_total = sum(
            s.get("total", 0) - s.get("tendered", 0)
            for s in credit_sales if s.get("is_on_account", False)
        )
        has_on_account = any(k.upper() == "ON ACCOUNT" for k in method_map)
        if on_account_total > 0 and not has_on_account:
            print(f"[DEBUG] Adding ON ACCOUNT row with total: {on_account_total}")
            method_map["ON ACCOUNT"] = {
                "method": "ON ACCOUNT",
                "total":   on_account_total,
                "counted": 0.0,
            }

        for name, row_data in method_map.items():
            print(f"  - {name}: total={row_data.get('total')}, counted={row_data.get('counted')}")

        if not method_map:
            QMessageBox.warning(self, "No Data", "No payment methods found for this shift.")
            self.close_btn.setEnabled(False)
            return

        methods = sorted(k for k in method_map if k.upper() != "ON ACCOUNT")
        
        # Add ON ACCOUNT at the end if it exists
        if "ON ACCOUNT" in method_map:
            methods.append("ON ACCOUNT")
        
        self.table.setRowCount(len(methods))
        
        for i, method in enumerate(methods):
            row_data = method_map.get(method) or method_map.get(method.upper(), {})
            expected = float(row_data.get("total", 0.0))
            counted = float(row_data.get("counted", 0.0))
            variance = counted - expected
            
            print(f"[DEBUG] Method {method}: expected={expected}, counted={counted}, variance={variance}")
            
            name_item = QTableWidgetItem(method)
            name_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            name_item.setForeground(QColor("#212121"))
            font = QFont()
            font.setBold(True)
            name_item.setFont(font)
            self.table.setItem(i, 0, name_item)
            
            exp_item = QTableWidgetItem(f"{expected:,.2f}")
            exp_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            exp_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            exp_item.setForeground(QColor("#212121"))
            self.table.setItem(i, 1, exp_item)
            
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
            
            # For ON ACCOUNT, disable editing and set to 0
            if method.upper() == "ON ACCOUNT":
                actual_edit.setEnabled(False)
                actual_edit.setText("0.00")
                actual_edit.setStyleSheet(actual_edit.styleSheet() + "background: #f5f5f5; color: #757575;")
            elif counted > 0:
                actual_edit.setText(f"{counted:.2f}")
                
            actual_edit.textChanged.connect(lambda _, row=i: self._update_variance(row))
            self.table.setCellWidget(i, 2, actual_edit)
            
            var_item = QTableWidgetItem(f"{variance:,.2f}")
            var_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            var_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            if variance < 0:
                var_item.setForeground(QColor("#d32f2f"))
            elif variance > 0:
                var_item.setForeground(QColor("#388e3c"))
            else:
                var_item.setForeground(QColor("#757575"))
            self.table.setItem(i, 3, var_item)
            
            self.table.setRowHeight(i, 45)
        
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
        cashier_id = cashier_data.get("cashier_id", "")
        total_sales = float(cashier_data.get("totals", {}).get("total_sales", 0))
        num_transactions = len(cashier_data.get("sales", []))
        total_items = int(cashier_data.get("totals", {}).get("total_items", 0))
        
        # Cashier info header
        info_frame = QFrame()
        info_frame.setStyleSheet("QFrame { background: #f5f5f5; border-radius: 6px; padding: 12px; }")
        info_layout = QHBoxLayout(info_frame)
        
        info_text = f"""
        <b>{cashier_name}</b><br>
        <span style='font-size: 11px; color: #666;'>ID: {cashier_id if cashier_id else '—'}</span><br>
        Transactions: {num_transactions}  |  Items Sold: {total_items}  |  Total Sales: ${total_sales:,.2f}
        """
        info_label = QLabel(info_text)
        info_label.setTextFormat(Qt.RichText)
        info_label.setStyleSheet("font-size: 13px; color: #212121;")
        info_layout.addWidget(info_label)
        info_layout.addStretch()
        layout.addWidget(info_frame)
        
        # Payment methods table - shows ONLY what THIS cashier collected
        table = QTableWidget(0, 3)
        table.setHorizontalHeaderLabels(["Payment Method", "Amount Collected ($)", "Transaction Count"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table.setColumnWidth(1, 160)
        table.setColumnWidth(2, 120)
        table.setAlternatingRowColors(True)
        table.setStyleSheet("""
            QTableWidget {
                background: white;
                color: #212121;
            }
            QTableWidget::item {
                color: #212121;
            }
        """)
        
        payment_methods = cashier_data.get("totals", {}).get("payment_methods", {})
        
        if not payment_methods:
            table.setRowCount(1)
            no_data_item = QTableWidgetItem("No payment methods recorded")
            no_data_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            no_data_item.setForeground(QColor("#757575"))
            table.setItem(0, 0, no_data_item)
            table.setSpan(0, 0, 1, 3)
        else:
            table.setRowCount(len(payment_methods))
            for i, (method, amount) in enumerate(payment_methods.items()):
                # Count transactions for this method for this cashier
                count = 0
                for sale in cashier_data.get("sales", []):
                    for pm in sale.get("payment_methods", []):
                        if pm.upper() == method.upper():
                            count += 1
                            break
                
                method_item = QTableWidgetItem(str(method))
                method_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                method_item.setForeground(QColor("#212121"))
                table.setItem(i, 0, method_item)
                
                amount_item = QTableWidgetItem(f"{float(amount):,.2f}")
                amount_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                amount_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                amount_item.setForeground(QColor("#212121"))
                table.setItem(i, 1, amount_item)
                
                count_item = QTableWidgetItem(str(count))
                count_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                count_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                count_item.setForeground(QColor("#212121"))
                table.setItem(i, 2, count_item)
        
        layout.addWidget(table)
        
        # Cashier summary
        summary_frame = QFrame()
        summary_frame.setStyleSheet("QFrame { background: #f5f5f5; border-radius: 6px; margin-top: 10px; }")
        summary_layout = QHBoxLayout(summary_frame)
        
        summary_text = f"<b>Cashier Summary:</b>  Total Collected: ${total_sales:,.2f}  |  Total Transactions: {num_transactions}  |  Items Sold: {total_items}"
        summary_label = QLabel(summary_text)
        summary_label.setTextFormat(Qt.RichText)
        summary_label.setStyleSheet("padding: 12px; font-size: 13px; color: #212121;")
        summary_layout.addWidget(summary_label)
        summary_layout.addStretch()
        layout.addWidget(summary_frame)
        
        # Add tab with cashier name
        tab_name = cashier_name[:20] if cashier_name else "Unknown"
        self.tab_widget.addTab(tab, tab_name)

    def _update_variance(self, row):
        try:
            exp_item = self.table.item(row, 1)
            actual_edit = self.table.cellWidget(row, 2)
            
            if not exp_item or not actual_edit:
                return
                
            expected = float(exp_item.text().replace(",", "")) if exp_item.text() else 0
            actual_text = actual_edit.text().strip()
            actual = float(actual_text) if actual_text else 0
            variance = actual - expected
            
            var_item = self.table.item(row, 3)
            if var_item:
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
        except ValueError:
            var_item = self.table.item(row, 3)
            if var_item:
                var_item.setText("0.00")
                var_item.setForeground(QColor("#757575"))
                var_item.setBackground(QColor("white"))
        self._update_summary()

    def _update_summary(self):
        total_expected = 0.0
        total_counted = 0.0
        
        for row in range(self.table.rowCount()):
            try:
                exp_item = self.table.item(row, 1)
                actual_edit = self.table.cellWidget(row, 2)
                
                if exp_item and actual_edit:
                    expected = float(exp_item.text().replace(",", "")) if exp_item.text() else 0
                    actual_text = actual_edit.text().strip()
                    actual = float(actual_text) if actual_text else 0
                    total_expected += expected
                    total_counted += actual
            except:
                pass
        
        total_variance = total_counted - total_expected
        variance_color = "#d32f2f" if total_variance < 0 else "#388e3c" if total_variance > 0 else "#212121"
        variance_sign = "+" if total_variance > 0 else ""
        
        self.summary_label.setText(f"Expected: ${total_expected:,.2f}  |  Counted: ${total_counted:,.2f}  |  Variance: {variance_sign}${total_variance:,.2f}")
        self.summary_label.setStyleSheet(f"font-weight: bold; font-size: 14px; padding: 12px; color: {variance_color};")

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

        # ── Step 1: expected per method from already-loaded shift rows ────────
        # shift_rows.total = start_float + income — the authoritative expected value.
        expected_by_method = {}
        shift_rows = self._active_shift.get("rows", [])
        
        # Add ON ACCOUNT to expected_by_method if it exists in shift_rows
        for sr in shift_rows:
            method_key = sr["method"].strip().upper()
            total_value = float(sr.get("total", 0))
            expected_by_method[method_key] = total_value
            print(f"  {method_key}: total={total_value}")
        
        print(f"\n[DEBUG] Step 1: Processed {len(shift_rows)} shift rows")

        # ── Step 2: user-entered counted values keyed by UPPER(method) ───────
        counted_by_method = {}
        print(f"\n[DEBUG] Step 2: Processing {len(totals)} user-entered totals")
        for t in totals:
            method_key = t["method"].strip().upper()
            counted_by_method[method_key] = float(t["actual"])
            print(f"  {method_key}: actual={t['actual']}")

        # ── Step 3: cashier_sales already loaded with the shift ───────────────
        cashier_sales = self._active_shift.get("cashier_sales", [])
        print(f"\n[DEBUG] Step 3: Found {len(cashier_sales)} cashier(s) with sales")

        # ── Step 4: total collected per method across ALL cashiers ────────────
        total_collected_per_method = {}
        for cashier in cashier_sales:
            print(f"\n  Cashier: {cashier.get('cashier_name')}")
            for method_key, amount in cashier.get("totals", {}).get("payment_methods", {}).items():
                # Store the original method name and also create a normalized version
                key = method_key.strip().upper()
                total_collected_per_method[key] = total_collected_per_method.get(key, 0.0) + float(amount)
                print(f"    {key}: +{amount} = {total_collected_per_method[key]}")
        
        print(f"\n[DEBUG] Step 4: Total collected per method: {total_collected_per_method}")

        # ── Step 5: build per-cashier rows with prorated expected/counted ─────
        cashier_details = []
        for cashier in cashier_sales:
            cashier_payment_methods = cashier.get("totals", {}).get("payment_methods", {})
            
            # Add ON ACCOUNT to cashier's payment methods if they have credit sales
            cashier_credit_total = 0.0
            for sale in cashier.get("sales", []):
                if sale.get("is_on_account", False) and sale.get("total", 0) > sale.get("tendered", 0):
                    cashier_credit_total += sale.get("total", 0) - sale.get("tendered", 0)
            
            if cashier_credit_total > 0:
                cashier_payment_methods = dict(cashier_payment_methods)
                cashier_payment_methods["ON ACCOUNT"] = cashier_credit_total
                print(f"  Added ON ACCOUNT to {cashier.get('cashier_name')}: ${cashier_credit_total:.2f}")
            
            if not cashier_payment_methods:
                print(f"\n  Skipping {cashier.get('cashier_name')} - no payment methods")
                continue

            print(f"\n[DEBUG] Building rows for cashier: {cashier.get('cashier_name')}")
            rows = []
            for method_key, amount_collected in cashier_payment_methods.items():
                method_upper = method_key.strip().upper()
                amount_collected = float(amount_collected)
                total_collected = total_collected_per_method.get(method_upper, 0.0)
                proportion = (amount_collected / total_collected) if total_collected > 0 else 0.0

                # FIX: Match expected and counted by finding the method in expected_by_method and counted_by_method
                # Try exact match first, then try to find a match without suffixes
                expected_value = 0.0
                counted_value = 0.0
                
                # Try exact match
                if method_upper in expected_by_method:
                    expected_value = expected_by_method[method_upper]
                else:
                    # Try to find a match where the expected method key contains this method
                    for exp_method in expected_by_method:
                        if method_upper in exp_method or exp_method in method_upper:
                            print(f"    Fuzzy match: {method_upper} matched to {exp_method}")
                            expected_value = expected_by_method[exp_method]
                            break
                
                # Same for counted
                if method_upper in counted_by_method:
                    counted_value = counted_by_method[method_upper]
                else:
                    for cnt_method in counted_by_method:
                        if method_upper in cnt_method or cnt_method in method_upper:
                            print(f"    Fuzzy match counted: {method_upper} matched to {cnt_method}")
                            counted_value = counted_by_method[cnt_method]
                            break

                cashier_expected = expected_value * proportion
                cashier_counted = counted_value * proportion
                variance = cashier_counted - cashier_expected

                print(f"    {method_key}:")
                print(f"      amount_collected={amount_collected}, total_collected={total_collected}, proportion={proportion}")
                print(f"      expected_value={expected_value}, counted_value={counted_value}")
                print(f"      cashier_expected={cashier_expected}, cashier_counted={cashier_counted}, variance={variance}")

                tx_count = 0
                for sale in cashier.get("sales", []):
                    for pm in sale.get("payment_methods", []):
                        if pm.strip().upper() == method_upper:
                            tx_count += 1
                            break
                    # Count ON ACCOUNT transactions
                    if method_upper == "ON ACCOUNT" and sale.get("is_on_account", False):
                        tx_count += 1

                rows.append({
                    "method": method_key,
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
                "cashier_id": cashier.get("cashier_id"),
                "cashier_name": cashier.get("cashier_name", "Unknown"),
                "total_sales": float(cashier.get("totals", {}).get("total_sales", 0)),
                "total_items": int(cashier.get("totals", {}).get("total_items", 0)),
                "transaction_count": len(cashier.get("sales", [])),
                "total_expected": round(total_exp, 2),
                "total_counted": round(total_cnt, 2),
                "total_variance": round(total_cnt - total_exp, 2),
                "rows": rows,
                "payment_breakdown": rows,
            })
            
            print(f"    FINAL: total_expected={total_exp}, total_counted={total_cnt}, total_variance={total_cnt - total_exp}")
        
        # Get payment method totals from the main table
        payment_methods = []
        print(f"\n[DEBUG] Building payment_methods from main table ({self.table.rowCount()} rows)")
        for row in range(self.table.rowCount()):
            method = self.table.item(row, 0).text()
            expected = float(self.table.item(row, 1).text().replace(",", "")) if self.table.item(row, 1) else 0
            actual_edit = self.table.cellWidget(row, 2)
            actual_text = actual_edit.text().strip() if actual_edit else ""
            actual = float(actual_text) if actual_text else 0
            
            payment_methods.append({
                "method": str(method),
                "expected": float(expected),
                "counted": float(actual),
                "variance": float(actual - expected)
            })
            print(f"  {method}: expected={expected}, actual={actual}, variance={actual-expected}")
        
        total_expected = sum(p["expected"] for p in payment_methods)
        total_counted = sum(p["counted"] for p in payment_methods)
        
        raw_start = self._active_shift.get("start_time") or self._active_shift.get("created_at")
        if raw_start and hasattr(raw_start, 'strftime'):
            start_time_str = raw_start.strftime("%H:%M:%S")
        elif isinstance(raw_start, str) and raw_start:
            start_time_str = raw_start.split("T")[-1].split(" ")[-1][:8] if "T" in raw_start else raw_start[:8]
        else:
            start_time_str = "—"
        
        # Get date as string
        shift_date = self._active_shift.get("date", "")
        if hasattr(shift_date, 'strftime'):
            shift_date = shift_date.strftime("%Y-%m-%d")
        
        # Build the data dictionary with proper types
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
        
        print("\n[DEBUG] Final reconciliation data summary:")
        print(f"  total_expected: {total_expected}")
        print(f"  total_counted: {total_counted}")
        print(f"  total_variance: {total_counted - total_expected}")
        print(f"  cashiers count: {len(cashier_details)}")
        for c in cashier_details:
            print(f"    {c.get('cashier_name')}: rows={len(c.get('rows', []))}, total_expected={c.get('total_expected')}, total_counted={c.get('total_counted')}")
        
        print("="*80)
        print("DEBUG: _build_reconciliation_data - END")
        print("="*80 + "\n")
        
        # Clean the data for JSON serialization
        return self._clean_for_json(data)

    def _on_finalize(self):
        print("\n" + "="*80)
        print("DEBUG: _on_finalize - START")
        print("="*80)
        
        # Validate all inputs first
        for row in range(self.table.rowCount()):
            actual_edit = self.table.cellWidget(row, 2)
            if actual_edit:
                actual_text = actual_edit.text().strip()
                if actual_text:
                    try:
                        float(actual_text)
                    except ValueError:
                        QMessageBox.warning(self, "Invalid Input", f"Row {row + 1} has an invalid amount: '{actual_text}'")
                        actual_edit.setFocus()
                        return
        
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

        # Collect counted values
        totals = []
        print("\n[DEBUG] Collecting totals from main table:")
        for row in range(self.table.rowCount()):
            try:
                method = self.table.item(row, 0).text()
                expected = float(self.table.item(row, 1).text().replace(",", "")) if self.table.item(row, 1) else 0
                actual_edit = self.table.cellWidget(row, 2)
                actual_text = actual_edit.text().strip() if actual_edit else ""
                actual = float(actual_text) if actual_text else 0
                
                totals.append({
                    "method": method,
                    "expected": expected,
                    "actual": actual,
                    "variance": actual - expected
                })
                print(f"  {method}: expected={expected}, actual={actual}, variance={actual-expected}")
            except Exception as e:
                QMessageBox.warning(self, "Invalid Data", f"Row {row + 1} has invalid data: {e}")
                return

        try:
            from models.shift import end_shift, get_active_shift, save_shift_reconciliation
            
            active = get_active_shift()
            if not active:
                QMessageBox.warning(self, "Error", "No active shift found.")
                return

            print(f"\n[DEBUG] Active shift ID: {active['id']}, Number: {active.get('shift_number')}")

            # Build complete reconciliation data (includes ALL cashiers)
            reconciliation_data = self._build_reconciliation_data(totals)
            
            # Debug the reconciliation data before saving
            print("\n[DEBUG] Reconciliation data before save:")
            print(f"  cashiers count: {len(reconciliation_data.get('cashiers', []))}")
            for c in reconciliation_data.get('cashiers', []):
                print(f"    {c.get('cashier_name')}:")
                print(f"      total_expected: {c.get('total_expected')}")
                print(f"      total_counted: {c.get('total_counted')}")
                print(f"      rows count: {len(c.get('rows', []))}")
                for r in c.get('rows', []):
                    print(f"        {r.get('method')}: expected={r.get('expected')}, counted={r.get('counted')}, variance={r.get('variance')}")
            
            # Save to database FIRST
            reconciliation_id = save_shift_reconciliation(active["id"], reconciliation_data)
            
            if reconciliation_id:
                print(f"✅ Reconciliation saved with ID: {reconciliation_id}")
                self._reconciliation_id = reconciliation_id
            else:
                print("⚠️ Failed to save reconciliation")
            
            # Close the shift
            counted_map = {t["method"]: t["actual"] for t in totals}
            print(f"\n[DEBUG] Closing shift with counted_map: {counted_map}")
            closed_shift = end_shift(active["id"], counted_map)
            
            if not closed_shift:
                QMessageBox.warning(self, "Error", "Failed to close shift.")
                return

            # Print receipt
            print("\n[DEBUG] Attempting to print shift reconciliation...")
            try:
                from services.printing_service import printing_service
                from models.advance_settings import AdvanceSettings
                
                settings = AdvanceSettings.load_from_file()
                printer_name = getattr(settings, "receiptPrinterName", None)
                print(f"[DEBUG] Printer name: {printer_name}")
                print(f"[DEBUG] reconciliation_data keys: {reconciliation_data.keys()}")
                print(f"[DEBUG] reconciliation_data cashiers: {len(reconciliation_data.get('cashiers', []))}")
                
                printing_service.print_shift_reconciliation(
                    shift=closed_shift,
                    totals=totals,
                    reconciliation_data=reconciliation_data,
                    printer_name=printer_name
                )
                
                # Update print status
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

            # Shift is now closed — return to login screen so the next cashier
            # (or the same one starting a fresh shift) sees a clean prompt.
            try:
                mw = self.window()
                while mw is not None and not hasattr(mw, "_logout_after_shift_close"):
                    mw = mw.parent() if hasattr(mw, "parent") else None
                if mw is not None:
                    QTimer.singleShot(0, mw._logout_after_shift_close)
                else:
                    print("[shift close] could not find MainWindow for logout — staying open.")
            except Exception as _e:
                print(f"[shift close] logout trigger failed: {_e}")

        except Exception as e:
            print(f"[DEBUG] Error in _on_finalize: {e}")
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to close shift: {str(e)}")
            import traceback
            traceback.print_exc()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.close_btn.isEnabled():
                self._on_finalize()
        else:
            super().keyPressEvent(event)


def show_shift_reconciliation(parent=None, cashier_id=None, cashier_name=None):
    """Helper function to show the shift reconciliation dialog."""
    dialog = ShiftReconciliationDialog(parent, cashier_id=cashier_id, cashier_name=cashier_name)
    return dialog.exec()