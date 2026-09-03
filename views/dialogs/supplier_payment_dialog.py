from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem,
    QLabel, QHeaderView, QComboBox, QLineEdit, QMessageBox, QWidget, QDateEdit, QAbstractItemView,
    QFrame, QCompleter
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor, QFont
from models.supplier_payment import create_supplier_payment
from models.supplier import get_all_suppliers
from database.db import get_connection, fetchall_dicts
import datetime

# ── Havano Palette ────────────────────────────────────────────────────────────
from theme import *

class ProcessSupplierPaymentDialog(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Supplier Payment Entry")
        self.setMinimumSize(950, 600)
        self.setStyleSheet(f"QWidget {{ background-color: {OFF_WHITE}; }}")
        
        self.suppliers = []
        self.payment_methods = []
        self._unpaid_invoices = []
        self._is_updating = False
        
        self._build()
        self._load_data()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # ── Header ───────────────────────────────────────────────
        hdr_widget = QWidget()
        hdr_widget.setStyleSheet(f"background-color: {NAVY}; border-radius: 6px;")
        hl = QHBoxLayout(hdr_widget)
        hl.setContentsMargins(16, 12, 16, 12)
        
        title = QLabel("Supplier Payment Entry")
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {WHITE};")
        hl.addWidget(title)
        hl.addStretch()
        
        self.save_btn = QPushButton("Save Payment")
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {SUCCESS}; color: {WHITE}; border: none;
                border-radius: 4px; padding: 8px 16px; font-weight: bold; font-size: 13px;
            }}
            QPushButton:hover {{ background-color: #1f9447; }}
        """)
        self.save_btn.clicked.connect(self._save_payment)
        hl.addWidget(self.save_btn)
        
        layout.addWidget(hdr_widget)

        # ── Form Frame ───────────────────────────────────────────
        form_frame = QFrame()
        form_frame.setStyleSheet(f"""
            QFrame {{ background: {WHITE}; border: 1px solid {BORDER}; border-radius: 6px; }}
            QLabel {{ border: none; font-size: 12px; font-weight: bold; color: {NAVY_2}; }}
            QLineEdit, QComboBox, QDateEdit {{
                border: 1px solid {BORDER}; border-radius: 4px; padding: 6px; font-size: 13px; background: {WHITE}; color: {NAVY};
            }}
            QLineEdit:focus, QComboBox:focus, QDateEdit:focus {{ border: 1.5px solid {ACCENT}; }}
        """)
        fl = QVBoxLayout(form_frame)
        fl.setContentsMargins(16, 16, 16, 16)
        fl.setSpacing(12)

        row1 = QHBoxLayout()
        row1.setSpacing(16)
        
        # Supplier
        v1 = QVBoxLayout()
        v1.setSpacing(4)
        v1.addWidget(QLabel("Supplier"))
        self.sup_combo = QComboBox()
        self.sup_combo.setEditable(True)
        self.sup_combo.setInsertPolicy(QComboBox.NoInsert)
        completer = self.sup_combo.completer()
        if completer:
            completer.setCompletionMode(QCompleter.PopupCompletion)
            completer.setFilterMode(Qt.MatchContains)
            completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.sup_combo.currentIndexChanged.connect(self._on_supplier_changed)
        v1.addWidget(self.sup_combo)
        row1.addLayout(v1, 2)

        # Date
        v2 = QVBoxLayout()
        v2.setSpacing(4)
        v2.addWidget(QLabel("Payment Date"))
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        v2.addWidget(self.date_edit)
        row1.addLayout(v2, 1)

        fl.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(16)

        # Payment Method
        v3 = QVBoxLayout()
        v3.setSpacing(4)
        v3.addWidget(QLabel("Payment Method"))
        self.method_combo = QComboBox()
        v3.addWidget(self.method_combo)
        row2.addLayout(v3, 1)

        # Amount Paid
        v4 = QVBoxLayout()
        v4.setSpacing(4)
        v4.addWidget(QLabel("Amount Paid"))
        self.amount_edit = QLineEdit("0.00")
        self.amount_edit.textChanged.connect(self._on_amount_paid_changed)
        v4.addWidget(self.amount_edit)
        row2.addLayout(v4, 1)

        # Reference
        v5 = QVBoxLayout()
        v5.setSpacing(4)
        v5.addWidget(QLabel("Reference / Cheque No."))
        self.ref_edit = QLineEdit()
        v5.addWidget(self.ref_edit)
        row2.addLayout(v5, 2)

        fl.addLayout(row2)
        layout.addWidget(form_frame)
        
        # ── Smart Table ──────────────────────────────────────────
        table_lbl = QLabel("Outstanding Invoices")
        table_lbl.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {NAVY}; margin-top: 8px;")
        layout.addWidget(table_lbl)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Type", "Doc No.", "Date", "Invoice Amount", "Outstanding", "Allocated"])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.setColumnWidth(3, 120)
        hh.setSectionResizeMode(4, QHeaderView.Fixed)
        self.table.setColumnWidth(4, 120)
        hh.setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.setColumnWidth(5, 120)
        
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {WHITE}; border: 1px solid {BORDER}; gridline-color: {LIGHT}; border-radius: 6px;
                font-size: 12px;
            }}
            QHeaderView::section {{
                background-color: {NAVY}; color: {WHITE}; padding: 8px; border: none; font-weight: bold;
            }}
            QTableWidget::item {{ padding: 4px 8px; color: {NAVY}; }}
        """)
        self.table.cellChanged.connect(self._on_cell_changed)
        layout.addWidget(self.table)
        
        # ── Footer Totals ────────────────────────────────────────
        foot_lay = QHBoxLayout()
        self.lbl_alloc = QLabel("Total Allocated: $0.00")
        self.lbl_alloc.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {NAVY};")
        
        self.lbl_unalloc = QLabel("Unallocated Amount: $0.00")
        self.lbl_unalloc.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {DANGER};")
        
        foot_lay.addStretch()
        foot_lay.addWidget(self.lbl_alloc)
        foot_lay.addSpacing(24)
        foot_lay.addWidget(self.lbl_unalloc)
        layout.addLayout(foot_lay)

    def _load_data(self):
        # Payment Methods
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT name FROM modes_of_payment WHERE enabled = 1 ORDER BY display_order ASC")
            rows = fetchall_dicts(cur)
            self.payment_methods = [r['name'] for r in rows]
            self.method_combo.addItems(self.payment_methods)
        except Exception as e:
            print("Error loading payment methods:", e)

        # Suppliers
        try:
            self.suppliers = get_all_suppliers()
            self.sup_combo.addItem("Select Supplier...", None)
            for s in self.suppliers:
                balance = float(s.get('balance') or 0)
                self.sup_combo.addItem(f"{s['name']} (Owed: ${balance:,.2f})", s)
        except Exception as e:
            print("Error loading suppliers:", e)
        finally:
            conn.close()

    def _on_supplier_changed(self):
        supplier = self.sup_combo.currentData()
        self.table.setRowCount(0)
        self._unpaid_invoices.clear()
        self._recalc_totals()
        
        if not supplier:
            return
            
        sup_id = supplier['id']
        sup_name = supplier['name']
        
        conn = get_connection()
        try:
            cur = conn.cursor()
            # 1. Purchase Invoices (stock_entries)
            cur.execute("""
                SELECT id, doc_no as name, date, balance, is_paid
                FROM stock_entries 
                WHERE UPPER(TRIM(supplier)) = UPPER(TRIM(?))
                  AND is_paid = 0 AND balance > 0 AND doc_no LIKE 'PINV-%'
                ORDER BY date ASC
            """, (sup_name,))
            pinv_rows = fetchall_dicts(cur)
            for r in pinv_rows:
                self._unpaid_invoices.append({
                    "type": "Purchase Invoice",
                    "id": r["id"],
                    "doc_no": r["name"],
                    "date": str(r["date"])[:10],
                    "total": r["balance"],      # Since balance might be the original or outstanding
                    "outstanding": r["balance"]
                })
                
            # 2. Expenses (expenses table, we ensure balance is present)
            cur.execute("""
                IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='expenses' AND COLUMN_NAME='balance')
                ALTER TABLE expenses ADD balance DECIMAL(18,4) NULL;
            """)
            cur.execute("""
                SELECT id, expense_number, created_at, amount, ISNULL(balance, amount) as balance, paid
                FROM expenses
                WHERE supplier_id = ? AND paid = 0 AND ISNULL(balance, amount) > 0
                ORDER BY created_at ASC
            """, (sup_id,))
            exp_rows = fetchall_dicts(cur)
            for r in exp_rows:
                self._unpaid_invoices.append({
                    "type": "Expense",
                    "id": r["id"],
                    "doc_no": r["expense_number"] or f"EXP-{r['id']:06d}",
                    "date": str(r["created_at"])[:10],
                    "total": r["amount"],
                    "outstanding": r["balance"]
                })
        except Exception as e:
            print("Error loading invoices:", e)
        finally:
            conn.close()
            
        self._populate_table()
        self._auto_allocate()

    def _populate_table(self):
        self._is_updating = True
        self.table.setRowCount(0)
        for i, inv in enumerate(self._unpaid_invoices):
            self.table.insertRow(i)
            
            it_type = QTableWidgetItem(inv["type"])
            it_type.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            
            it_doc = QTableWidgetItem(inv["doc_no"])
            it_doc.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            
            it_date = QTableWidgetItem(inv["date"])
            it_date.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            
            it_tot = QTableWidgetItem(f"${inv['total']:,.2f}")
            it_tot.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            it_tot.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            
            it_out = QTableWidgetItem(f"${inv['outstanding']:,.2f}")
            it_out.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            it_out.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            
            alloc_le = QLineEdit("0.00")
            alloc_le.setStyleSheet(f"border: 1px solid {BORDER}; background: {WHITE}; padding: 2px;")
            alloc_le.setAlignment(Qt.AlignRight)
            alloc_le.textChanged.connect(self._recalc_totals)
            
            self.table.setItem(i, 0, it_type)
            self.table.setItem(i, 1, it_doc)
            self.table.setItem(i, 2, it_date)
            self.table.setItem(i, 3, it_tot)
            self.table.setItem(i, 4, it_out)
            self.table.setCellWidget(i, 5, alloc_le)
            
        self._is_updating = False

    def _on_amount_paid_changed(self):
        if not self._is_updating:
            self._auto_allocate()
            self._recalc_totals()

    def _on_cell_changed(self, row, col):
        if not self._is_updating and col == 5:
            self._recalc_totals()

    def _auto_allocate(self):
        try:
            total_paid = float(self.amount_edit.text() or 0)
        except ValueError:
            total_paid = 0.0

        self._is_updating = True
        remaining = total_paid
        for i in range(self.table.rowCount()):
            alloc_le = self.table.cellWidget(i, 5)
            if not alloc_le: continue
            
            out_str = self.table.item(i, 4).text().replace("$","").replace(",","")
            try:
                outstanding = float(out_str)
            except:
                outstanding = 0.0
                
            if remaining > 0:
                allocate = min(outstanding, remaining)
                alloc_le.setText(f"{allocate:.2f}")
                remaining -= allocate
            else:
                alloc_le.setText("0.00")
        self._is_updating = False
        self._recalc_totals()

    def _recalc_totals(self):
        try:
            total_paid = float(self.amount_edit.text() or 0)
        except:
            total_paid = 0.0
            
        allocated = 0.0
        for i in range(self.table.rowCount()):
            alloc_le = self.table.cellWidget(i, 5)
            if alloc_le:
                try:
                    allocated += float(alloc_le.text() or 0)
                except:
                    pass
                    
        unallocated = total_paid - allocated
        
        self.lbl_alloc.setText(f"Total Allocated: ${allocated:,.2f}")
        self.lbl_unalloc.setText(f"Unallocated Amount: ${unallocated:,.2f}")
        if unallocated < 0:
            self.lbl_unalloc.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {DANGER};")
        else:
            self.lbl_unalloc.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {SUCCESS};")

    def _save_payment(self):
        supplier = self.sup_combo.currentData()
        if not supplier:
            QMessageBox.warning(self, "Validation", "Please select a supplier.")
            return
            
        try:
            total_paid = float(self.amount_edit.text() or 0)
        except:
            total_paid = 0.0
            
        if total_paid <= 0:
            QMessageBox.warning(self, "Validation", "Payment amount must be greater than zero.")
            return

        method = self.method_combo.currentText()
        reference = self.ref_edit.text().strip()
        sup_id = supplier['id']
        sup_name = supplier['name']
        
        # Gather allocations
        allocations = []
        allocated_total = 0.0
        for i in range(self.table.rowCount()):
            alloc_le = self.table.cellWidget(i, 5)
            if alloc_le:
                try:
                    alloc_amt = float(alloc_le.text() or 0)
                except:
                    alloc_amt = 0.0
                if alloc_amt > 0:
                    allocations.append({
                        "inv": self._unpaid_invoices[i],
                        "amount": alloc_amt
                    })
                    allocated_total += alloc_amt
                    
        if allocated_total > total_paid + 0.01:
            QMessageBox.warning(self, "Validation", "Allocated amount exceeds total paid amount.")
            return

        # 1. Create Supplier Payment (this also decrements the overall supplier balance)
        create_supplier_payment(sup_id, sup_name, total_paid, method, reference)
        
        # 2. Update specific invoices
        conn = get_connection()
        try:
            cur = conn.cursor()
            for alloc in allocations:
                inv = alloc["inv"]
                amt = alloc["amount"]
                
                if inv["type"] == "Purchase Invoice":
                    cur.execute("""
                        UPDATE stock_entries 
                        SET balance = ISNULL(balance, 0) - ?,
                            is_paid = CASE WHEN ISNULL(balance, 0) - ? <= 0.01 THEN 1 ELSE 0 END
                        WHERE id = ?
                    """, (amt, amt, inv["id"]))
                elif inv["type"] == "Expense":
                    cur.execute("""
                        UPDATE expenses 
                        SET balance = ISNULL(balance, amount) - ?,
                            paid = CASE WHEN ISNULL(balance, amount) - ? <= 0.01 THEN 1 ELSE 0 END
                        WHERE id = ?
                    """, (amt, amt, inv["id"]))
            conn.commit()
            QMessageBox.information(self, "Success", "Supplier payment and invoice allocations saved successfully!")
            self.sup_combo.setCurrentIndex(0)
            self.amount_edit.setText("0.00")
            self.ref_edit.clear()
            self._load_data()
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "Error", f"Failed to allocate invoices: {e}")
        finally:
            conn.close()
