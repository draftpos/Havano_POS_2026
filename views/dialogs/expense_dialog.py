import qtawesome as qta
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem,
    QLabel, QHeaderView, QComboBox, QLineEdit, QMessageBox, QInputDialog, QWidget, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from models.expense import (
    get_expense_categories, create_expense_category, create_expense, get_expense_payment_methods
)
from models.supplier import get_all_suppliers

# Toggle switch fallback
try:
    from views.main_window import _ToggleSwitch
except ImportError:
    from PySide6.QtWidgets import QCheckBox as _ToggleSwitch


class AddExpenseDialog(QDialog):
    """
    Dedicated modal popup dialog to record new till expense(s).
    Matches the pattern of StockEditDialog in inventory.
    """
    def __init__(self, parent=None, shift_id=None, cashier_id=None, cashier_name=None):
        super().__init__(parent)
        self.setWindowTitle("Record Expense")
        self.setModal(True)
        self.resize(920, 460)
        self.setStyleSheet("QDialog { background-color: #ffffff; }")

        self.shift_id = shift_id
        self.cashier_id = cashier_id
        self.cashier_name = cashier_name
        self.categories = []
        self.suppliers = []
        self.payment_methods = []

        # Resolve shift and cashier if not provided
        self._resolve_context()
        self._build_ui()
        self._load_data()

    def _resolve_context(self):
        if not self.shift_id:
            try:
                from models.shift import get_active_shift
                act_shift = get_active_shift()
                self.shift_id = act_shift.get("id") if act_shift else None
            except Exception:
                self.shift_id = None

        if not self.cashier_name:
            u = None
            parent = self.parent()
            if parent and hasattr(parent, "user") and parent.user:
                u = parent.user
            elif parent and hasattr(parent, "_pos") and getattr(parent, "_pos", None) and hasattr(parent._pos, "user"):
                u = parent._pos.user
            elif parent and hasattr(parent, "parent_window") and getattr(parent, "parent_window", None) and hasattr(parent.parent_window, "user"):
                u = parent.parent_window.user
            if u:
                self.cashier_id = u.get("id")
                self.cashier_name = u.get("full_name") or u.get("username")

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Header bar
        hdr_widget = QWidget()
        hdr_widget.setStyleSheet("background-color: #1a5fb4; border-radius: 6px;")
        hl = QHBoxLayout(hdr_widget)
        hl.setContentsMargins(16, 10, 16, 10)

        title = QLabel("Add Expense")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: white;")
        hl.addWidget(title)

        hl.addStretch()

        pm_lbl = QLabel("Default Payment:")
        pm_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: white;")
        hl.addWidget(pm_lbl)

        self.global_payment_combo = QComboBox()
        self.global_payment_combo.setStyleSheet("""
            QComboBox {
                background-color: white; color: #1a5fb4; border: none;
                border-radius: 4px; padding: 5px 10px; font-weight: bold; font-size: 13px;
                min-width: 120px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background-color: white; color: #212121; selection-background-color: #e4eaf4;
            }
        """)
        self.global_payment_combo.currentTextChanged.connect(self._on_global_payment_changed)
        hl.addWidget(self.global_payment_combo)

        hl.addSpacing(10)

        add_cat_btn = QPushButton(" Add Category")
        add_cat_btn.setIcon(qta.icon("fa5s.tags", color="white", scale_factor=0.8))
        add_cat_btn.setCursor(Qt.PointingHandCursor)
        add_cat_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a5fb4; color: white; border: 1px solid white;
                border-radius: 4px; padding: 6px 12px; font-weight: bold; font-size: 12px;
            }
            QPushButton:hover { background-color: #1c6dd0; }
        """)
        add_cat_btn.clicked.connect(self._add_category)
        hl.addWidget(add_cat_btn)

        add_row_btn = QPushButton(" Add Row")
        add_row_btn.setIcon(qta.icon("fa5s.plus", color="white", scale_factor=0.8))
        add_row_btn.setCursor(Qt.PointingHandCursor)
        add_row_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a5fb4; color: white; border: 1px solid white;
                border-radius: 4px; padding: 6px 12px; font-weight: bold; font-size: 12px;
            }
            QPushButton:hover { background-color: #1c6dd0; }
        """)
        add_row_btn.clicked.connect(self._add_row)
        hl.addWidget(add_row_btn)

        layout.addWidget(hdr_widget)

        # Multi-row Entry Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Expense Name", "Category", "Amount ($)", "Payment Method", "Supplier", "Paid?"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setStyleSheet("""
            QTableWidget { gridline-color: #e4eaf4; border: 1px solid #c8d8ec; background: white; }
            QHeaderView::section { background-color: #f0e8d0; padding: 8px; border: none; border-right: 1px solid #c8d8ec; font-weight: bold; font-size: 13px; color: #1a5fb4;}
        """)
        layout.addWidget(self.table, 1)

        # Footer Actions & Total
        footer = QHBoxLayout()
        footer.setContentsMargins(4, 4, 4, 4)

        self.total_label = QLabel("Total: $0.00")
        self.total_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #1a7a3c;")
        footer.addWidget(self.total_label)

        footer.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f0f4f8; color: #475569; border: 1px solid #cbd5e1;
                border-radius: 4px; padding: 7px 18px; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background-color: #e2e8f0; }
        """)
        cancel_btn.clicked.connect(self.reject)
        footer.addWidget(cancel_btn)

        save_btn = QPushButton(" Save Expenses")
        save_btn.setIcon(qta.icon("fa5s.check-circle", color="white"))
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a7a3c; color: white; border: none;
                border-radius: 4px; padding: 7px 22px; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background-color: #1f9447; }
        """)
        save_btn.clicked.connect(self._save_expenses)
        footer.addWidget(save_btn)

        layout.addLayout(footer)

    def _load_data(self):
        # Load immediately from local database (instantaneous)
        self.categories = get_expense_categories()
        self.suppliers = get_all_suppliers()
        self.payment_methods = get_expense_payment_methods()

        # If local table has no categories and in SaaS mode, fetch in background
        if not self.categories:
            def _bg_fetch_cats():
                try:
                    from services.expense_sync_service import is_saas_mode, fetch_cloud_expense_categories
                    if is_saas_mode():
                        fetch_cloud_expense_categories()
                except Exception as e:
                    print(f"[expense_dialog] Background cloud category fetch notice: {e}")

            import threading
            threading.Thread(target=_bg_fetch_cats, daemon=True, name="BgFetchExpenseCats").start()

        self.global_payment_combo.blockSignals(True)
        self.global_payment_combo.clear()
        for pm in self.payment_methods:
            self.global_payment_combo.addItem(pm)
        cash_idx = self.global_payment_combo.findText("Cash")
        if cash_idx >= 0:
            self.global_payment_combo.setCurrentIndex(cash_idx)
        self.global_payment_combo.blockSignals(False)

        if self.table.rowCount() == 0:
            self._add_row()

    def _on_global_payment_changed(self, new_method: str):
        if not new_method:
            return
        for r in range(self.table.rowCount()):
            pm_combo = self.table.cellWidget(r, 3)
            if pm_combo:
                idx = pm_combo.findText(new_method)
                if idx >= 0:
                    pm_combo.setCurrentIndex(idx)

    def _add_category(self):
        name, ok = QInputDialog.getText(self, "Add Category", "Category Name:")
        if ok and name.strip():
            create_expense_category(name.strip())
            self.categories = get_expense_categories()
            for r in range(self.table.rowCount()):
                combo = self.table.cellWidget(r, 1)
                if combo:
                    cur_sel = combo.currentText()
                    combo.clear()
                    for c in self.categories:
                        combo.addItem(c['name'], c['id'])
                    idx = combo.findText(name.strip())
                    if idx >= 0:
                        combo.setCurrentIndex(idx)
                    elif cur_sel:
                        old_idx = combo.findText(cur_sel)
                        if old_idx >= 0:
                            combo.setCurrentIndex(old_idx)

    def _add_row(self):
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setRowHeight(r, 45)

        name_edit = QLineEdit()
        name_edit.setPlaceholderText("Expense description...")
        name_edit.setStyleSheet("padding: 5px; font-size: 13px; border: 1px solid #c8d8ec; border-radius: 3px;")
        self.table.setCellWidget(r, 0, name_edit)

        cat_combo = QComboBox()
        cat_combo.setStyleSheet("padding: 5px; font-size: 13px; border: 1px solid #c8d8ec; border-radius: 3px;")
        for c in self.categories:
            cat_combo.addItem(c['name'], c['id'])
        self.table.setCellWidget(r, 1, cat_combo)

        amount_edit = QLineEdit()
        amount_edit.setPlaceholderText("0.00")
        amount_edit.setStyleSheet("padding: 5px; font-size: 13px; border: 1px solid #c8d8ec; border-radius: 3px;")
        amount_edit.textChanged.connect(self._update_total)
        self.table.setCellWidget(r, 2, amount_edit)

        pm_combo = QComboBox()
        pm_combo.setStyleSheet("padding: 5px; font-size: 13px; border: 1px solid #c8d8ec; border-radius: 3px;")
        for pm in self.payment_methods:
            pm_combo.addItem(pm)
        current_def = self.global_payment_combo.currentText().strip() if hasattr(self, 'global_payment_combo') else "Cash"
        idx = pm_combo.findText(current_def)
        if idx >= 0:
            pm_combo.setCurrentIndex(idx)
        self.table.setCellWidget(r, 3, pm_combo)

        sup_combo = QComboBox()
        sup_combo.setStyleSheet("padding: 5px; font-size: 13px; border: 1px solid #c8d8ec; border-radius: 3px;")
        sup_combo.addItem("None", None)
        for s in self.suppliers:
            sup_combo.addItem(s['name'], s['id'])
        self.table.setCellWidget(r, 4, sup_combo)

        paid_pill = _ToggleSwitch("Paid")
        paid_pill.setChecked(True)
        w = QWidget()
        wl = QHBoxLayout(w)
        wl.addWidget(paid_pill)
        wl.setAlignment(Qt.AlignCenter)
        wl.setContentsMargins(0, 0, 0, 0)
        self.table.setCellWidget(r, 5, w)

        name_edit.setFocus()

    def _update_total(self):
        total = 0.0
        for r in range(self.table.rowCount()):
            amount_w = self.table.cellWidget(r, 2)
            if amount_w:
                try:
                    total += float(amount_w.text().replace("$", "").replace(",", "").strip())
                except ValueError:
                    pass
        self.total_label.setText(f"Total: ${total:,.2f}")

    def _save_expenses(self):
        saved = 0
        for r in range(self.table.rowCount()):
            name_w = self.table.cellWidget(r, 0)
            if not name_w or not name_w.text().strip():
                continue
            name = name_w.text().strip()

            cat_w = self.table.cellWidget(r, 1)
            cat_id = cat_w.currentData() if cat_w else None
            if not cat_id:
                continue

            amount_w = self.table.cellWidget(r, 2)
            try:
                amount = float(amount_w.text().replace("$", "").replace(",", "").strip())
            except ValueError:
                amount = 0.0

            if amount <= 0:
                continue

            pm_w = self.table.cellWidget(r, 3)
            payment_method = pm_w.currentText().strip() if pm_w else (self.global_payment_combo.currentText().strip() or "Cash")

            sup_w = self.table.cellWidget(r, 4)
            sup_id = sup_w.currentData() if sup_w else None

            w_box = self.table.cellWidget(r, 5)
            if w_box:
                pill = w_box.layout().itemAt(0).widget()
                paid = pill.isChecked()
            else:
                paid = True

            create_expense(
                name=name,
                category_id=cat_id,
                amount=amount,
                supplier_id=sup_id,
                paid=paid,
                shift_id=self.shift_id,
                cashier_id=self.cashier_id,
                cashier_name=self.cashier_name,
                payment_method=payment_method
            )
            saved += 1

        if saved > 0:
            if self.shift_id:
                try:
                    from models.shift import refresh_income
                    refresh_income(self.shift_id, force=True)
                except Exception as e:
                    print(f"Error refreshing shift income after expense: {e}")

            # SaaS Mode Cloud Post integration (run in background to avoid blocking the UI)
            try:
                from services.expense_sync_service import is_saas_mode, push_unsynced_expenses
                if is_saas_mode():
                    import threading
                    threading.Thread(target=push_unsynced_expenses, daemon=True, name="SaveExpenseCloudPush").start()
            except Exception as e:
                print(f"[expense_dialog] Cloud sync trigger notice: {e}")

            QMessageBox.information(self, "Success", f"{saved} expense(s) recorded successfully!")
            self.accept()
        else:
            QMessageBox.warning(self, "Warning", "No valid expenses found to save. Please enter expense name and amount.")


class ProcessExpenseDialog(QDialog):
    """
    Backbone Listview dialog for Expenses.
    Displays all recorded expenses with search, live filters, and totals,
    with an '+ Add Expense' button that pops up AddExpenseDialog (like Inventory).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Expenses")
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint | Qt.WindowMinimizeButtonHint)
        self.setStyleSheet("QDialog { background-color: #ffffff; }")

        self.shift_id = None
        self.cashier_id = None
        self.cashier_name = None
        self._history_rows = []

        self._build_ui()

    def showEvent(self, event):
        super().showEvent(event)
        self.showMaximized()
        self.setWindowState(Qt.WindowMaximized)

        # Resolve active shift and cashier on every open
        try:
            from models.shift import get_active_shift
            act_shift = get_active_shift()
            self.shift_id = act_shift.get("id") if act_shift else None
        except Exception:
            self.shift_id = None

        u = None
        parent = self.parent()
        if parent and hasattr(parent, "user") and parent.user:
            u = parent.user
        elif parent and hasattr(parent, "_pos") and getattr(parent, "_pos", None) and hasattr(parent._pos, "user"):
            u = parent._pos.user
        elif parent and hasattr(parent, "parent_window") and getattr(parent, "parent_window", None) and hasattr(parent.parent_window, "user"):
            u = parent.parent_window.user
        if u:
            self.cashier_id = u.get("id")
            self.cashier_name = u.get("full_name") or u.get("username")
        else:
            self.cashier_id = None
            self.cashier_name = None

        self._load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Top Navigation & Action Header
        hdr_widget = QWidget()
        hdr_widget.setStyleSheet("background-color: #1a5fb4; border-radius: 6px;")
        hl = QHBoxLayout(hdr_widget)
        hl.setContentsMargins(16, 10, 16, 10)
        hl.setSpacing(12)

        title = QLabel("Expenses")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: white;")
        hl.addWidget(title)

        hl.addSpacing(16)

        # Live Search input
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search expenses (name, category, cashier, payment method, #)...")
        self.search_edit.setFixedHeight(34)
        self.search_edit.setMinimumWidth(320)
        self.search_edit.setStyleSheet("""
            QLineEdit {
                background-color: white; color: #1e293b; border: none;
                border-radius: 4px; padding: 4px 12px; font-size: 13px;
            }
        """)
        self.search_edit.textChanged.connect(self._filter_history)
        hl.addWidget(self.search_edit)

        hl.addStretch()

        # Add Expense Button (Primary Action - Pops up AddExpenseDialog)
        add_exp_btn = QPushButton("  Add Expense")
        add_exp_btn.setIcon(qta.icon("fa5s.plus-circle", color="white"))
        add_exp_btn.setFixedHeight(34)
        add_exp_btn.setCursor(Qt.PointingHandCursor)
        add_exp_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a7a3c; color: white; border: none;
                border-radius: 4px; padding: 0 18px; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background-color: #1f9447; }
        """)
        add_exp_btn.clicked.connect(self._open_add_expense)
        hl.addWidget(add_exp_btn)

        # Add Category Button
        add_cat_btn = QPushButton("  Add Category")
        add_cat_btn.setIcon(qta.icon("fa5s.tags", color="white", scale_factor=0.85))
        add_cat_btn.setFixedHeight(34)
        add_cat_btn.setCursor(Qt.PointingHandCursor)
        add_cat_btn.setStyleSheet("""
            QPushButton {
                background-color: #154b8e; color: white; border: 1px solid rgba(255,255,255,0.4);
                border-radius: 4px; padding: 0 14px; font-weight: bold; font-size: 12px;
            }
            QPushButton:hover { background-color: #1a5fb4; }
        """)
        add_cat_btn.clicked.connect(self._add_category)
        hl.addWidget(add_cat_btn)

        # Refresh Button
        refresh_btn = QPushButton("  Refresh")
        refresh_btn.setIcon(qta.icon("fa5s.sync", color="#1a5fb4", scale_factor=0.85))
        refresh_btn.setFixedHeight(34)
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: white; color: #1a5fb4; border: none;
                border-radius: 4px; padding: 0 14px; font-weight: bold; font-size: 12px;
            }
            QPushButton:hover { background-color: #e4eaf4; }
        """)
        refresh_btn.clicked.connect(self._load_data)
        hl.addWidget(refresh_btn)

        # Close Button
        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(34)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #d32f2f; color: white; border: none;
                border-radius: 4px; padding: 0 16px; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background-color: #b71c1c; }
        """)
        close_btn.clicked.connect(self.reject)
        hl.addWidget(close_btn)

        layout.addWidget(hdr_widget)

        # The Backbone Listview Table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Date", "Expense #", "Expense Name", "Category", "Payment Method", "Cashier", "Status", "Amount"
        ])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                gridline-color: #e4eaf4; border: 1px solid #c8d8ec;
                background-color: white; alternate-background-color: #f9fbfe;
                font-size: 13px;
            }
            QHeaderView::section {
                background-color: #f0e8d0; padding: 8px; border: none;
                border-bottom: 1px solid #c8d8ec; border-right: 1px solid #e4eaf4;
                font-weight: bold; font-size: 13px; color: #1a5fb4;
            }
        """)

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

        layout.addWidget(self.table, 1)

        # Footer with Total
        footer = QHBoxLayout()
        hint = QLabel("Tip: Click '+ Add Expense' to record new expenses for this till or shift.")
        hint.setStyleSheet("font-size: 12px; color: #64748b;")
        footer.addWidget(hint)

        footer.addStretch()

        self.total_label = QLabel("Total Recorded (0 expenses): $0.00")
        self.total_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #1a7a3c; margin: 4px 8px;")
        footer.addWidget(self.total_label)

        layout.addLayout(footer)

    def _open_add_expense(self):
        """Pops up the AddExpenseDialog (modal) and reloads data upon saving."""
        dlg = AddExpenseDialog(
            parent=self,
            shift_id=self.shift_id,
            cashier_id=self.cashier_id,
            cashier_name=self.cashier_name
        )
        if dlg.exec():
            self._load_data()

    def _add_category(self):
        name, ok = QInputDialog.getText(self, "Add Category", "Category Name:")
        if ok and name.strip():
            create_expense_category(name.strip())
            QMessageBox.information(self, "Success", f"Category '{name.strip()}' created.")

    def _load_data(self):
        """Fetch all recorded expenses and display them in the backbone listview."""
        from database.db import get_connection, fetchall_dicts
        conn = get_connection()
        cur = conn.cursor()
        try:
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
                ORDER BY e.created_at DESC
            """)
            self._history_rows = fetchall_dicts(cur)
            self._populate_table(self._history_rows)
        except Exception as e:
            print(f"[expense_dialog] Error loading expenses: {e}")
        finally:
            conn.close()

    def _populate_table(self, rows):
        self.table.setRowCount(len(rows))
        total_amt = 0.0
        for r, row in enumerate(rows):
            date_str = str(row['created_at'])[:16] if row.get('created_at') else ""
            exp_num = str(row.get('expense_num') or "")
            desc_str = str(row.get('descr') or "")
            cat_str = str(row.get('category') or "")
            pm_str = str(row.get('payment_method') or "Cash")
            cashier_str = str(row.get('cashier') or "")
            paid = bool(row.get('paid', 1))
            status_str = "Paid" if paid else "Unpaid"
            amt = float(row.get('amount') or 0.0)
            total_amt += amt

            vals = [date_str, exp_num, desc_str, cat_str, pm_str, cashier_str, status_str, f"${amt:,.2f}"]
            for c, val in enumerate(vals):
                item = QTableWidgetItem(val)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                if c == 6:  # Status
                    item.setForeground(QColor("#1e8449") if paid else QColor("#b02020"))
                    f = item.font()
                    f.setBold(True)
                    item.setFont(f)
                    item.setTextAlignment(Qt.AlignCenter)
                elif c == 7:  # Amount
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    f = item.font()
                    f.setBold(True)
                    item.setFont(f)
                self.table.setItem(r, c, item)

        self.total_label.setText(f"Total Recorded ({len(rows)} expenses): ${total_amt:,.2f}")

    def _filter_history(self, query: str):
        q = (query or "").strip().lower()
        if not hasattr(self, "_history_rows"):
            return
        if not q:
            self._populate_table(self._history_rows)
            return
        filtered = []
        for row in self._history_rows:
            searchable = f"{row.get('created_at', '')} {row.get('expense_num', '')} {row.get('descr', '')} {row.get('category', '')} {row.get('payment_method', '')} {row.get('cashier', '')} {row.get('amount', '')}".lower()
            if q in searchable:
                filtered.append(row)
        self._populate_table(filtered)
