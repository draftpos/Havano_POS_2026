# views/dialogs/purchase_invoice_dialog.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QWidget, QFrame, QGraphicsDropShadowEffect, QMessageBox,
    QComboBox, QAbstractItemView, QCompleter, QCheckBox, QGridLayout,
    QDateEdit
)
from PySide6.QtCore import Qt, QSize, QTimer, QEvent, Signal
from PySide6.QtGui import QColor, QIcon, QFont
import qtawesome as qta
import datetime
import random

from models.product import search_products, get_all_products
from models.stock_entry import create_stock_entry
from models.warehouse import get_all_warehouses, create_warehouse
from models.supplier import get_all_suppliers, create_supplier
from utils.toast import show_toast

# ── Havano Palette ────────────────────────────────────────────────────────────
from theme import *


# ── Tick Toggle Button ────────────────────────────────────────────────────────
class TickToggleButton(QPushButton):
    """A proper tick / un-tick toggle for 'Mark as Paid'."""
    toggled_state = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._checked = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(28)
        self.clicked.connect(self._toggle)
        self._refresh()

    def _toggle(self):
        self._checked = not self._checked
        self._refresh()
        self.toggled_state.emit(self._checked)

    def _refresh(self):
        if self._checked:
            self.setText("  ✓  Paid")
            self.setStyleSheet(f"""
                QPushButton {{
                    background: {SUCCESS};
                    color: {WHITE};
                    border: none;
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: bold;
                    padding: 0 14px;
                    letter-spacing: 0.5px;
                }}
                QPushButton:hover {{ background: #1f9447; }}
            """)
        else:
            self.setText("  ○  Unpaid")
            self.setStyleSheet(f"""
                QPushButton {{
                    background: {WHITE};
                    color: {MUTED};
                    border: 1.5px solid {BORDER};
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: bold;
                    padding: 0 14px;
                    letter-spacing: 0.5px;
                }}
                QPushButton:hover {{
                    border-color: {ACCENT};
                    color: {ACCENT};
                    background: #eef4ff;
                }}
            """)

    def isChecked(self):
        return self._checked

    def setChecked(self, val: bool):
        if self._checked != val:
            self._checked = val
            self._refresh()
            self.toggled_state.emit(self._checked)


# ── Quick-Add Supplier ────────────────────────────────────────────────────────
class QuickAddSupplierDialog(QDialog):
    supplier_created = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Supplier")
        self.setFixedWidth(420)
        self.setSizeGripEnabled(False)
        self.setModal(True)
        self.setStyleSheet(f"""
            QDialog {{
                background: {WHITE};
                font-family: 'Segoe UI', sans-serif;
            }}
            QLabel#section {{
                color: {MUTED};
                font-size: 9px;
                font-weight: bold;
                letter-spacing: 1px;
                background: transparent;
            }}
        """)
        self._build()

    def _field(self, placeholder: str, required: bool = False) -> QLineEdit:
        le = QLineEdit()
        le.setPlaceholderText(placeholder + (" *" if required else ""))
        le.setFixedHeight(36)
        le.setStyleSheet(f"""
            QLineEdit {{
                background: {OFF_WHITE};
                color: {NAVY};
                border: 1.5px solid {BORDER};
                border-radius: 6px;
                font-size: 12px;
                padding: 0 10px;
            }}
            QLineEdit:focus {{ border: 1.5px solid {ACCENT}; background: {WHITE}; }}
        """)
        return le

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # header
        hdr = QWidget()
        hdr.setFixedHeight(46)
        hdr.setStyleSheet(f"background: {NAVY};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(20, 0, 20, 0)
        title = QLabel("New Supplier")
        title.setStyleSheet(
            f"color:{WHITE}; font-size:14px; font-weight:bold; background:transparent;"
        )
        hl.addWidget(title)
        root.addWidget(hdr)

        # body
        body = QWidget()
        body.setStyleSheet(f"background:{WHITE};")
        fl = QVBoxLayout(body)
        fl.setContentsMargins(22, 18, 22, 8)
        fl.setSpacing(9)

        self._f_name    = self._field("Supplier Name", required=True)
        self._f_address = self._field("Supplier Address")
        self._f_phone   = self._field("Phone Number")

        for lbl_txt, widget in [
            ("SUPPLIER NAME",    self._f_name),
            ("SUPPLIER ADDRESS", self._f_address),
            ("PHONE NUMBER",     self._f_phone),
        ]:
            lbl = QLabel(lbl_txt)
            lbl.setObjectName("section")
            fl.addWidget(lbl)
            fl.addWidget(widget)

        self._status = QLabel("")
        self._status.setStyleSheet(
            f"color:{DANGER}; font-size:10px; background:transparent;"
        )
        self._status.setAlignment(Qt.AlignCenter)
        fl.addWidget(self._status)
        root.addWidget(body)

        # footer
        foot = QWidget()
        foot.setStyleSheet(f"background:{OFF_WHITE}; border-top:1px solid {BORDER};")
        bl = QHBoxLayout(foot)
        bl.setContentsMargins(22, 10, 22, 14)
        bl.setSpacing(10)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(34)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background:{WHITE}; color:{NAVY};
                border:1.5px solid {BORDER}; border-radius:6px;
                font-size:12px; padding:0 16px;
            }}
            QPushButton:hover {{ background:{LIGHT}; border-color:{ACCENT}; }}
        """)
        cancel_btn.clicked.connect(self.reject)

        self._save_btn = QPushButton("Save Supplier")
        self._save_btn.setFixedHeight(34)
        self._save_btn.setStyleSheet(f"""
            QPushButton {{
                background:{SUCCESS}; color:{WHITE};
                border:none; border-radius:6px;
                font-size:12px; font-weight:bold; padding:0 20px;
            }}
            QPushButton:hover {{ background:#1f9447; }}
            QPushButton:disabled {{ background:{BORDER}; color:{MUTED}; }}
        """)
        self._save_btn.clicked.connect(self._save)

        bl.addWidget(cancel_btn)
        bl.addStretch()
        bl.addWidget(self._save_btn)
        root.addWidget(foot)

        self._f_name.setFocus()

    def _save(self):
        name    = self._f_name.text().strip()
        address = self._f_address.text().strip()
        phone   = self._f_phone.text().strip()

        if not name:
            self._status.setText("Supplier Name is required.")
            self._f_name.setFocus()
            return

        self._save_btn.setEnabled(False)
        self._status.setText("")
        try:
            from models.supplier import create_supplier
            new_id  = create_supplier(name=name, address=address, phone=phone)
            new_sup = {"id": new_id, "name": name, "address": address, "phone": phone}
            self.supplier_created.emit(new_sup)
            self.accept()
        except Exception as exc:
            self._status.setText(f"Error: {exc}")
            self._save_btn.setEnabled(True)


# ── Main Dialog ───────────────────────────────────────────────────────────────
class PurchaseInvoiceDialog(QDialog):
    def __init__(self, parent=None, read_only_data=None, is_return=False, source_invoice_doc_no=None):
        super().__init__(parent)
        self.read_only_data = read_only_data
        self.is_read_only = bool(read_only_data)
        self.invoice_id = self.read_only_data.get("id") if self.read_only_data else None
        self.is_return = is_return
        
        title_text = "Purchase Return Details" if self.is_return else "Purchase Invoice Details"
        if not self.is_read_only:
            title_text = "New Purchase Return" if self.is_return else "New Purchase Invoice"
            
        self.setWindowTitle(title_text)
        self.setMinimumSize(1100, 800)
        self.setWindowFlags(Qt.Window | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)
        self.setWindowState(Qt.WindowMaximized)

        self.items = []
        self._supplier_cache = {}
        self._supplier_prev_balance = 0.0
        self.source_doc_no = None

        self._build_ui()
        self._load_combos()
        self._setup_completer()

        if self.is_read_only:
            self._load_invoice_data()
            self._set_read_only_mode()
        else:
            now = datetime.datetime.now()
            self.date_time_edit.setText(now.strftime("%Y-%m-%d %H:%M"))
            prefix = "PRET" if self.is_return else "PINV"
            doc_no = f"{prefix}-{now.strftime('%Y%m%d%H%M')}-{random.randint(1000, 9999)}"
            self.doc_no_edit.setText(doc_no)

            if source_invoice_doc_no:
                self._on_return_invoice_selected(source_invoice_doc_no)
                
            if self.is_return:
                self.sup_combo.setEnabled(False)
                if hasattr(self, 'add_sup_btn'): self.add_sup_btn.setEnabled(False)
                self.wh_combo.setEnabled(False)
                if hasattr(self, 'add_wh_btn'): self.add_wh_btn.setEnabled(False)
                if hasattr(self, 'reference_edit'): self.reference_edit.setEnabled(False)
                if hasattr(self, 'supplier_invoice_edit'): self.supplier_invoice_edit.setEnabled(False)

    # ── helpers ──────────────────────────────────────────────────────────────
    def _generate_doc_no(self):
        now  = datetime.datetime.now()
        rand = random.randint(1000, 9999)
        prefix = "PRET" if self.is_return else "PINV"
        return f"{prefix}-{now.strftime('%Y%m%d%H%M')}-{rand}"

    def eventFilter(self, obj, event):
        if getattr(self, "_block_popup", False):
            ret = super().eventFilter(obj, event)
            return bool(ret) if ret is not None else False

        # Delete key on the table -> remove selected product row
        if (obj is self.table or obj is self.table.viewport()) and event.type() == QEvent.KeyPress:
            if self.is_read_only:
                ret = super().eventFilter(obj, event)
                return bool(ret) if ret is not None else False
            if event.key() == Qt.Key_Delete:
                row = self.table.currentRow()
                if row >= 0:
                    # Skip the inline search row
                    c0 = self.table.cellWidget(row, 0)
                    if not (c0 and getattr(c0, "is_inline_search", False)):
                        if row < len(self.items):
                            self._remove_item(row)
                return True

        if event.type() == QEvent.FocusIn:
            combos = [self.sup_combo, self.wh_combo]
            if hasattr(self, "search_edit"):       combos.append(self.search_edit)
            if hasattr(self, "inline_search_edit"): combos.append(self.inline_search_edit)
            for combo in combos:
                target = combo.lineEdit() if hasattr(combo, "lineEdit") else combo
                if obj == target:
                    completer = (
                        combo.completer()
                        if hasattr(combo, "completer")
                        else getattr(obj, "completer", lambda: None)()
                    )
                    if completer and not completer.popup().isVisible():
                        QTimer.singleShot(100, completer.complete)
        ret = super().eventFilter(obj, event)
        return bool(ret) if ret is not None else False

    # ── UI build ─────────────────────────────────────────────────────────────
    def _build_ui(self):
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setObjectName("piCard")
        card.setStyleSheet(f"""
            QFrame#piCard {{
                background:{WHITE};
                border-radius:0px;
                border:none;
            }}
        """)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(18); shadow.setXOffset(0); shadow.setYOffset(6)
        shadow.setColor(QColor(0, 0, 0, 28))
        card.setGraphicsEffect(shadow)
        main_lay.addWidget(card)

        cl = QVBoxLayout(card)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)

        # Header removed to use native title bar with minimize/maximize/close buttons

        # ── BODY ─────────────────────────────────────────────────────────────
        body = QWidget()
        bl   = QVBoxLayout(body)
        bl.setContentsMargins(22, 14, 22, 14)
        bl.setSpacing(12)

        # ── FORM FRAME: 2 rows × 4 cols ──────────────────────────────────────
        form_frame = QFrame()
        form_frame.setStyleSheet(f"""
            QFrame {{
                background:{OFF_WHITE};
                border:1px solid {BORDER};
                border-radius:10px;
            }}
            QLabel {{ border:none; background:transparent; }}
        """)
        top_hbox = QHBoxLayout(form_frame)
        top_hbox.setContentsMargins(14, 12, 14, 12)
        top_hbox.setSpacing(0)

        # Shared styles (smaller, premium, and smoother font)
        lbl_s = (
            f"color:{MUTED}; font-size:9px; font-weight:bold; letter-spacing:0.8px;"
        )
        inp_s = f"""
            QLineEdit, QComboBox {{
                border:1px solid {BORDER}; border-radius:5px;
                padding:0 8px; background:{WHITE}; color:{NAVY};
                font-size:11px; font-weight:500;
            }}
            QLineEdit:focus, QComboBox:focus {{
                border:1.5px solid {ACCENT};
            }}
            QComboBox::drop-down {{
                border:none; width:20px;
            }}
            QComboBox::down-arrow {{
                image:none;
                border-left:4px solid transparent;
                border-right:4px solid transparent;
                border-top:5px solid {MUTED};
                margin-right:4px;
            }}
        """

        def _le(placeholder="", readonly=False, h=34):
            le = QLineEdit()
            le.setPlaceholderText(placeholder)
            le.setFixedHeight(h)
            le.setReadOnly(readonly)
            if readonly:
                le.setStyleSheet(f"""
                    QLineEdit {{
                        border:1px solid {BORDER}; border-radius:5px;
                        padding:0 8px; font-size:11px;
                        background:#f0f4f9; color:{NAVY};
                    }}
                """)
            else:
                le.setStyleSheet(inp_s)
            return le

        def _combo(h=34):
            cb = QComboBox()
            cb.setEditable(True)
            cb.setFixedHeight(h)
            cb.setMinimumWidth(180)  # Increase field width
            cb.setStyleSheet(inp_s)
            return cb

        def _plus_btn(slot):
            btn = QPushButton()
            btn.setIcon(qta.icon("fa5s.plus", color=WHITE))
            btn.setIconSize(QSize(12, 12))  
            btn.setFixedSize(24, 34)        # Thin width, tall height (matches combo)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(
                f"background:{ACCENT}; border-radius:4px; border:none;"
            )
            btn.clicked.connect(slot)
            return btn

        def _row(label_txt, widget, label_w=100):
            """Horizontal row: [Label] [Widget]"""
            row = QHBoxLayout()
            row.setSpacing(6)
            row.setContentsMargins(0, 0, 0, 0)
            lbl = QLabel(label_txt)
            lbl.setFixedWidth(label_w)
            lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            lbl.setStyleSheet(lbl_s)
            row.addWidget(lbl)
            row.addWidget(widget, 1)
            return row

        def _row_with_btn(label_txt, widget_layout, label_w=100):
            """Horizontal row: [Label] [Layout (widget+btn)]"""
            row = QHBoxLayout()
            row.setSpacing(6)
            row.setContentsMargins(0, 0, 0, 0)
            lbl = QLabel(label_txt)
            lbl.setFixedWidth(label_w)
            lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            lbl.setStyleSheet(lbl_s)
            row.addWidget(lbl)
            row.addLayout(widget_layout, 1)
            return row

        # ── Title & Save Command Bar ──────────────────────────────────────────
        top_bar_lay = QHBoxLayout()
        top_bar_lay.setContentsMargins(0, 0, 0, 10)

        title_lbl = QLabel("Purchase Invoice")
        title_lbl.setStyleSheet(f"color:{NAVY}; font-size:18px; font-weight:bold;")
        top_bar_lay.addWidget(title_lbl)
        top_bar_lay.addStretch()

        save_text = "  Save Return" if self.is_return else "  Save"
        self.save_btn = QPushButton(save_text)
        self.save_btn.setIcon(qta.icon("fa5s.save", color=WHITE))
        self.save_btn.setFixedSize(130 if self.is_return else 110, 32)
        self.save_btn.setCursor(Qt.PointingHandCursor)
        
        save_print_text = "  Save Return & Print" if self.is_return else "  Save & Print"
        self.save_print_btn = QPushButton(save_print_text)
        self.save_print_btn.setIcon(qta.icon("fa5s.print", color=WHITE))
        self.save_print_btn.setFixedSize(160 if self.is_return else 130, 32)
        self.save_print_btn.setCursor(Qt.PointingHandCursor)
        
        # Add shadow to make button pop
        save_shadow = QGraphicsDropShadowEffect()
        save_shadow.setBlurRadius(8); save_shadow.setXOffset(0); save_shadow.setYOffset(3)
        save_shadow.setColor(QColor(0, 0, 0, 30))
        self.save_btn.setGraphicsEffect(save_shadow)
        
        print_shadow = QGraphicsDropShadowEffect()
        print_shadow.setBlurRadius(8); print_shadow.setXOffset(0); print_shadow.setYOffset(3)
        print_shadow.setColor(QColor(0, 0, 0, 30))
        self.save_print_btn.setGraphicsEffect(print_shadow)
        
        btn_style = f"""
            QPushButton {{
                background:{SUCCESS}; color:{WHITE}; border:1px solid #1a823e;
                border-radius:6px; font-size:12px; font-weight:bold;
            }}
            QPushButton:hover {{ background:#1f9447; }}
            QPushButton:pressed {{ background:#177536; margin-top:2px; margin-bottom:-2px; }}
        """
        
        self.save_btn.setStyleSheet(btn_style)
        self.save_print_btn.setStyleSheet(btn_style)
        
        self.reprint_btn = QPushButton("  Reprint")
        self.reprint_btn.setIcon(qta.icon("fa5s.print", color=WHITE))
        self.reprint_btn.setFixedHeight(32)
        self.reprint_btn.setMinimumWidth(100)
        self.reprint_btn.setCursor(Qt.PointingHandCursor)
        self.reprint_btn.setStyleSheet(btn_style)
        self.reprint_btn.clicked.connect(self._on_reprint)
        self.reprint_btn.hide()
        
        self.save_btn.clicked.connect(lambda: self._on_save(print_invoice=False))
        self.save_print_btn.clicked.connect(lambda: self._on_save(print_invoice=True))
        
        top_bar_lay.addWidget(self.reprint_btn)
        top_bar_lay.addWidget(self.save_print_btn)
        top_bar_lay.addWidget(self.save_btn)
        bl.addLayout(top_bar_lay)

        # ── Column 0: Supplier, Balance, Address ─────────────────────────────
        col0_lay = QVBoxLayout()
        col0_lay.setSpacing(5)
        col0_lay.setContentsMargins(0, 0, 0, 0)

        # Supplier + plus btn
        self.sup_combo = _combo()
        self.add_sup_btn = _plus_btn(self._add_new_supplier)
        sup_inner = QHBoxLayout(); sup_inner.setSpacing(5)
        sup_inner.addWidget(self.sup_combo, 1)
        sup_inner.addWidget(self.add_sup_btn)
        col0_lay.addLayout(_row_with_btn("Supplier", sup_inner))

        # Balance field (Always read-only)
        self.balance_edit = _le("0.00", readonly=True)
        self.balance_edit.setText("0.00")
        col0_lay.addLayout(_row("Balance Due", self.balance_edit))

        # Address (Hidden)
        self.address_edit = _le(readonly=True)
        self.address_edit.setPlaceholderText("Auto-filled from supplier")
        self.address_edit.hide()

        # ── Column 1: Doc No, Warehouse, Supplier Invoice ────────────────────
        col1_lay = QVBoxLayout()
        col1_lay.setSpacing(5)
        col1_lay.setContentsMargins(0, 0, 0, 0)

        # Doc No (Always read-only, Hidden)
        self.doc_no_edit = _le(readonly=True)
        self.doc_no_edit.hide()

        # IF RETURN, add "Return From" field
        if self.is_return and not self.is_read_only:
            self.return_from_edit = QLineEdit()
            self.return_from_edit.setPlaceholderText("Search PINV-...")
            self.return_from_edit.setStyleSheet("border: 1px solid #c8d8ec; border-radius: 4px; padding: 2px 8px; font-size: 12px; background: white;")
            self.return_from_edit.setFixedHeight(28)
            col1_lay.addLayout(_row("Return From", self.return_from_edit))
            
            from database.db import get_connection, fetchall_dicts
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT doc_no FROM stock_entries WHERE doc_no LIKE 'PINV-%'")
            invoices = [r['doc_no'] for r in fetchall_dicts(cur)]
            conn.close()
            
            self.return_completer = QCompleter(invoices)
            self.return_completer.setCaseSensitivity(Qt.CaseInsensitive)
            self.return_completer.setFilterMode(Qt.MatchContains)
            self.return_from_edit.setCompleter(self.return_completer)
            
            self.return_completer.activated.connect(self._on_return_invoice_selected)

        # Warehouse + plus btn
        self.wh_combo = _combo()
        self.add_wh_btn = _plus_btn(self._add_new_warehouse)
        wh_inner = QHBoxLayout(); wh_inner.setSpacing(5)
        wh_inner.addWidget(self.wh_combo, 1)
        wh_inner.addWidget(self.add_wh_btn)
        col1_lay.addLayout(_row_with_btn("Warehouse", wh_inner))

        # Supplier Invoice
        self.supplier_invoice_edit = _le("Optional")
        col1_lay.addLayout(_row("Sup. Invoice", self.supplier_invoice_edit))

        # ── Column 2: DateTime, Paid, Account Reference ──────────────────────
        col2_lay = QVBoxLayout()
        col2_lay.setSpacing(5)
        col2_lay.setContentsMargins(0, 0, 0, 0)

        # DateTime
        self.date_time_edit = _le()
        col2_lay.addLayout(_row("Date & Time", self.date_time_edit))



        # Paid toggle
        self.paid_btn = TickToggleButton()
        self.paid_btn.setMaximumWidth(100)
        paid_row = _row("Paid Status", self.paid_btn)
        paid_row.addStretch()               # absorb remaining space
        col2_lay.addLayout(paid_row)

        # Account Reference (Combo from modes_of_payment) (Hidden)
        self.reference_edit = _combo()
        self.reference_edit.hide()

        # Assemble form layout:
        # col0 on left | stretchy space | col1 and col2 grouped together on right
        top_hbox.addLayout(col0_lay, 0)     
        top_hbox.addStretch(1)              
        top_hbox.addLayout(col1_lay, 0)     
        top_hbox.addSpacing(16)             
        top_hbox.addLayout(col2_lay, 0)     

        bl.addWidget(form_frame)



        # ── Hidden backing search ─────────────────────────────────────────────
        self.search_edit = QLineEdit()

        # ── TABLE ────────────────────────────────────────────────────────────
        self.table = QTableWidget(0, 11)
        self.table.setHorizontalHeaderLabels(
            ["Item No.", "Item Details", "Batch No", "Expiry", "Cost", "Qty", "UOM", "Disc", "TAX", "Total", ""]
        )

        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed);  self.table.setColumnWidth(0, 105)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Fixed);  self.table.setColumnWidth(2, 100)
        hh.setSectionResizeMode(3, QHeaderView.Fixed);  self.table.setColumnWidth(3, 110)
        hh.setSectionResizeMode(4, QHeaderView.Fixed);  self.table.setColumnWidth(4, 85)
        hh.setSectionResizeMode(5, QHeaderView.Fixed);  self.table.setColumnWidth(5, 75)
        hh.setSectionResizeMode(6, QHeaderView.Fixed);  self.table.setColumnWidth(6, 65)
        hh.setSectionResizeMode(7, QHeaderView.Fixed);  self.table.setColumnWidth(7, 65)
        hh.setSectionResizeMode(8, QHeaderView.Fixed);  self.table.setColumnWidth(8, 65)
        hh.setSectionResizeMode(9, QHeaderView.Fixed);  self.table.setColumnWidth(9, 100)
        hh.setSectionResizeMode(10, QHeaderView.Fixed); self.table.setColumnWidth(10, 42)
        
        # Hide unnecessary columns
        self.table.setColumnHidden(7, True) # Disc
        self.table.setColumnHidden(8, True) # TAX
        self._update_batch_columns_visibility()

        self.table.verticalHeader().setVisible(False)
        self.table.installEventFilter(self)
        self.table.viewport().installEventFilter(self)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color:{WHITE}; color:{NAVY};
                border:1px solid {BORDER}; gridline-color:{LIGHT};
                font-size:11px; outline:none;
                selection-background-color:transparent;
            }}
            QTableWidget::item {{
                padding:0 4px; color:{NAVY}; border-bottom:1px solid {LIGHT};
            }}
            QTableWidget::item:selected {{
                background-color:#fff8e1; color:{NAVY}; border:1px solid #d4af37;
            }}
            QTableWidget::item:focus {{
                background-color:#fff8e1; color:{NAVY};
                border:2px solid #f57f17; font-weight:bold;
            }}
            QHeaderView::section {{
                background-color:#eef2fa; color:{NAVY};
                padding:5px 7px; border:none;
                border-right:1px solid {BORDER};
                border-bottom:1px solid {BORDER};
                font-size:10px; font-weight:bold; letter-spacing:0.4px;
            }}
        """)
        bl.addWidget(self.table)

        # ── FOOTER SUMMARY BAR ────────────────────────────────────────────────
        footer_lay = QHBoxLayout()
        footer_lay.setContentsMargins(8, 4, 8, 0)

        self.lbl_row_count = QLabel("Rows: 0")
        self.lbl_row_count.setStyleSheet(
            f"color:{MUTED}; font-size:11px; font-weight:bold;"
        )
        footer_lay.addWidget(self.lbl_row_count)
        footer_lay.addStretch()

        summary_box = QHBoxLayout(); summary_box.setSpacing(20)

        qty_lbl = QLabel("TOTAL QTY:")
        qty_lbl.setStyleSheet(f"color:{MUTED}; font-size:11px; font-weight:bold;")
        self.lbl_total_qty = QLabel("0.00")
        self.lbl_total_qty.setStyleSheet(
            f"color:{NAVY}; font-size:13px; font-weight:bold;"
        )
        summary_box.addWidget(qty_lbl); summary_box.addWidget(self.lbl_total_qty)

        sep = QLabel("|")
        sep.setStyleSheet(f"color:{BORDER}; font-size:16px;")
        summary_box.addWidget(sep)

        tot_lbl = QLabel("GRAND TOTAL:")
        tot_lbl.setStyleSheet(f"color:{MUTED}; font-size:11px; font-weight:bold;")
        self.lbl_grand_total = QLabel("$0.00")
        self.lbl_grand_total.setStyleSheet(
            f"color:{ACCENT}; font-size:17px; font-weight:bold;"
        )
        summary_box.addWidget(tot_lbl); summary_box.addWidget(self.lbl_grand_total)

        footer_lay.addLayout(summary_box)
        footer_lay.addStretch()

        bl.addLayout(footer_lay)

        # Inline search row
        self._setup_inline_search_row()

        # Wire signals
        self.paid_btn.toggled_state.connect(self._on_paid_state_changed)
        self._balance_manually_edited = False

        cl.addWidget(body)

    # ── Combos ───────────────────────────────────────────────────────────────
    def _load_combos(self):
        try:
            self.wh_combo.clear()
            for wh in get_all_warehouses():
                self.wh_combo.addItem(wh.get("name"), wh.get("id"))

            self.sup_combo.clear()
            self._supplier_cache = {}
            for s in get_all_suppliers():
                self.sup_combo.addItem(s.get("name"), s.get("id"))
                self._supplier_cache[s.get("id")] = s

            # Load accounts/payment modes into self.reference_edit combo box
            self.reference_edit.clear()
            self.reference_edit.addItem("Optional", "")
            try:
                from database.db import get_connection, fetchall_dicts
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("""
                    SELECT DISTINCT
                        LTRIM(RTRIM(m.name)) AS mop_name,
                        LTRIM(RTRIM(m.gl_account)) AS gl_account
                    FROM modes_of_payment m
                    WHERE m.gl_account IS NOT NULL
                      AND m.gl_account <> ''
                      AND m.enabled = 1
                    ORDER BY mop_name
                """)
                rows = fetchall_dicts(cur)
                conn.close()
                for row in rows:
                    name = row.get("mop_name")
                    gl = row.get("gl_account")
                    display_text = f"{name} ({gl})" if gl else name
                    self.reference_edit.addItem(display_text, name)
            except Exception as pe_err:
                print(f"[PI] Load payment modes/accounts error: {pe_err}")

            from models.company_defaults import get_defaults
            defs = get_defaults() or {}
            wh_name = defs.get("server_warehouse")
            if wh_name:
                idx = self.wh_combo.findText(wh_name)
                if idx >= 0: self.wh_combo.setCurrentIndex(idx)

            if not getattr(self, "_sup_combo_connected", False):
                self.sup_combo.currentIndexChanged.connect(self._on_supplier_changed)
                self._sup_combo_connected = True
            self._on_supplier_changed()

            # Rebuild combo completers so new items are included
            self._refresh_combo_completers()

        except Exception as e:
            print(f"[PI] Load combos error: {e}")

    def _refresh_combo_completers(self):
        """Rebuild supplier & warehouse completers from current combo contents."""
        for combo in (self.sup_combo, self.wh_combo):
            items = [combo.itemText(i) for i in range(combo.count())]
            c = QCompleter(items, self)
            c.setCaseSensitivity(Qt.CaseInsensitive)
            c.setFilterMode(Qt.MatchContains)
            c.setCompletionMode(QCompleter.PopupCompletion)
            self._style_completer(c)
            def _on_activated(text, cb=combo):
                idx = cb.findText(text, Qt.MatchFixedString)
                if idx >= 0:
                    cb.setCurrentIndex(idx)
            c.activated.connect(_on_activated)
            combo.setCompleter(c)

    def _on_supplier_changed(self):
        sup_id = self.sup_combo.currentData()
        if sup_id and sup_id in self._supplier_cache:
            addr = self._supplier_cache[sup_id].get("address") or ""
            self.address_edit.setText(addr)
            self._supplier_prev_balance = float(self._supplier_cache[sup_id].get("balance") or 0.0)
        else:
            self.address_edit.clear()
            self._supplier_prev_balance = 0.0
        self._recalc_totals()

    # ── Paid toggle ──────────────────────────────────────────────────────────
    def _on_paid_state_changed(self, is_paid: bool):
        # Balance is always read-only; just auto-fill based on paid state
        prev_bal = getattr(self, "_supplier_prev_balance", 0.0)
        if is_paid:
            self.balance_edit.setText(f"{prev_bal:.2f}")
        else:
            self._balance_manually_edited = False
        self._recalc_totals()


    def _on_balance_edited(self):
        self._balance_manually_edited = True

    def _on_return_invoice_selected(self, doc_no):
        from database.db import get_connection, fetchall_dicts
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM stock_entries WHERE doc_no = ?", (doc_no,))
        se = cur.fetchone()
        if not se: 
            conn.close()
            return
            
        cols = [desc[0] for desc in cur.description]
        se_dict = dict(zip(cols, se))
        
        # Populate supplier
        if se_dict.get('supplier'):
            idx = self.sup_combo.findText(se_dict['supplier'])
            if idx >= 0:
                self.sup_combo.setCurrentIndex(idx)
                
        # Populate warehouse
        if se_dict.get('warehouse_id'):
            idx = self.wh_combo.findData(se_dict['warehouse_id'])
            if idx >= 0:
                self.wh_combo.setCurrentIndex(idx)
                
        # Fetch items and calculate remaining returnable qty
        cur.execute("""
            SELECT sei.product_id, p.part_no, p.name, p.uom,
                   sei.cost_price, sei.selling_price,
                   sei.batch_no, sei.expiry_date,
                   sei.qty as original_qty,
                   ISNULL((
                       SELECT SUM(ret_sei.qty)
                       FROM stock_entry_items ret_sei
                       JOIN stock_entries ret_se ON ret_se.id = ret_sei.parent_id
                       WHERE ret_se.source_doc_no = ? AND ret_sei.product_id = sei.product_id
                   ), 0) as returned_qty
            FROM stock_entry_items sei
            JOIN products p ON sei.product_id = p.id
            WHERE sei.parent_id = ?
        """, (doc_no, se_dict['id']))
        
        items = fetchall_dicts(cur)
        conn.close()
        
        self.source_doc_no = doc_no
        self.items.clear()
        for it in items:
            orig = float(it.get("original_qty") or 0.0)
            ret = float(it.get("returned_qty") or 0.0)
            rem = orig - ret
            if rem <= 0: continue
            
            self.items.append({
                "product_id": it["product_id"],
                "part_no": it["part_no"],
                "name": it["name"],
                "batch_no": it.get("batch_no") or "",
                "expiry_date": str(it.get("expiry_date") or "") if it.get("expiry_date") else "",
                "cost": float(it.get("cost_price") or 0.0),
                "selling": float(it.get("selling_price") or 0.0),
                "qty": rem,
                "disc": 0.0,
                "tax": 0.0,
                "uom": it.get("uom") or "Unit"
            })
            
        if not self.items:
            QMessageBox.information(self, "Fully Returned", "This invoice has already been fully returned!")
            
        self._refresh_table()

    # ── Completers ───────────────────────────────────────────────────────────
    def _setup_completer(self):
        try:
            if not self.is_return and not self.is_read_only:
                products = get_all_products()
                self._product_map = {
                    f"{p['part_no']} | {p['name']}": p for p in products
                }

                p_completer = QCompleter(list(self._product_map.keys()), self)
                p_completer.setCaseSensitivity(Qt.CaseInsensitive)
                p_completer.setFilterMode(Qt.MatchContains)
                p_completer.setCompletionMode(QCompleter.PopupCompletion)
                self._style_completer(p_completer)

                self.completer = p_completer
                if hasattr(self, "search_edit"):
                    self.search_edit.setCompleter(p_completer)
                    self.search_edit.installEventFilter(self)
                p_completer.activated.connect(self._on_completer_activated)

                if hasattr(self, "inline_search_edit") and self.inline_search_edit:
                    self.inline_search_edit.setCompleter(p_completer)
            else:
                self._product_map = {}

            # Build completers from plain string lists so MatchContains works reliably
            def _setup_combo_completer(combo):
                items = [combo.itemText(i) for i in range(combo.count())]
                c = QCompleter(items, self)
                c.setCaseSensitivity(Qt.CaseInsensitive)
                c.setFilterMode(Qt.MatchContains)
                c.setCompletionMode(QCompleter.PopupCompletion)
                self._style_completer(c)
                combo.setCompleter(c)
                # When the user picks from the popup, sync the combo index
                def _on_activated(text, cb=combo):
                    idx = cb.findText(text, Qt.MatchFixedString)
                    if idx >= 0:
                        cb.setCurrentIndex(idx)
                c.activated.connect(_on_activated)
                combo.lineEdit().installEventFilter(self)

            _setup_combo_completer(self.sup_combo)
            _setup_combo_completer(self.wh_combo)

        except Exception as e:
            print(f"[PI] Completer setup error: {e}")

    def _style_completer(self, completer):
        completer.popup().setStyleSheet(f"""
            QListView {{
                background-color: {WHITE}; color: {NAVY};
                border: 1px solid {BORDER}; border-radius: 4px;
                font-size: 14px; padding: 4px; outline: none;
            }}
            QListView::item {{
                padding: 12px;
                border-radius: 4px;
                border-bottom: 1px solid #f1f5f9;
            }}
            QListView::item:selected {{
                background-color: {SUCCESS};
                color: {WHITE};
            }}
            QListView::item:hover {{
                background-color: #e2e8f0;
                color: {NAVY};
            }}
        """)

    def _on_completer_activated(self, text):
        self._block_popup = True
        product = self._product_map.get(text)
        if product:
            self.add_product(product)
            sw = getattr(self, "inline_search_edit", None)
            if sw:
                if sw.completer(): sw.completer().popup().hide()
                sw.clear(); sw.setFocus()
            self.search_edit.clear()

            self.table.setFocus()
            last_row = self.table.rowCount() - 2
            if last_row >= 0:
                self.table.setCurrentCell(last_row, 2)
                w = self.table.cellWidget(last_row, 2)
                if w: w.setFocus()

        QTimer.singleShot(300, lambda: setattr(self, "_block_popup", False))

    # ── Inline search row ────────────────────────────────────────────────────
    def _setup_inline_search_row(self):
        row = self.table.rowCount()
        if row > 0:
            lw = self.table.cellWidget(row - 1, 0)
            if lw and getattr(lw, "is_inline_search", False):
                return

        self.table.insertRow(row)
        self.table.setRowHeight(row, 38)
        self.table.setSpan(row, 0, 1, 2)

        search_edit = QLineEdit()
        search_edit.is_inline_search = True
        search_edit.setPlaceholderText(
            "Scan barcode or search product here to add inline…"
        )
        search_edit.setStyleSheet(f"""
            QLineEdit {{
                border:1.5px solid {BORDER}; border-radius:4px;
                padding:3px 12px; background:{WHITE}; color:{NAVY};
                font-size:12px; font-weight:500;
            }}
            QLineEdit:focus {{
                border:2px solid {ACCENT}; background:#fff8e1;
            }}
        """)

        if hasattr(self, "completer") and self.completer:
            search_edit.setCompleter(self.completer)

        search_edit.returnPressed.connect(
            lambda: self._on_inline_search_return(search_edit)
        )
        self.table.setCellWidget(row, 0, search_edit)

        for col in range(2, 11):
            item = QTableWidgetItem("")
            item.setFlags(Qt.NoItemFlags)
            self.table.setItem(row, col, item)

        self.inline_search_edit = search_edit

    def _on_inline_search_return(self, search_edit):
        text = search_edit.text().strip()
        if not text: return

        product = self._product_map.get(text)
        if product:
            self.add_product(product); search_edit.clear(); search_edit.setFocus(); return

        from models.product import get_product_by_part_no
        product = get_product_by_part_no(text)
        if product:
            self.add_product(product); search_edit.clear(); search_edit.setFocus(); return

        try:
            from database.db import get_connection
            conn = get_connection(); cur = conn.cursor()
            cur.execute(
                "SELECT part_no, uom FROM product_barcodes WHERE barcode = ?", (text,)
            )
            row = cur.fetchone(); conn.close()
            if row:
                part_no, alt_uom = row
                product = get_product_by_part_no(part_no)
                if product:
                    product["uom"] = alt_uom
                    self.add_product(product); search_edit.clear(); search_edit.setFocus(); return
        except Exception as e:
            print(f"[PI] Inline alternative barcode check error: {e}")

        prods = search_products(text)
        if len(prods) == 1:
            self.add_product(prods[0]); search_edit.clear(); search_edit.setFocus()
        elif len(prods) > 1:
            show_toast(self, "Multiple products found. Select from the popup.", kind="info")
        else:
            show_toast(self, "Product not found!", kind="warn")

    # ── Product / table management ───────────────────────────────────────────
    def _update_batch_columns_visibility(self):
        try:
            from database.db import get_connection
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM products WHERE is_pharmacy_product = 1 OR has_batch = 1 LIMIT 1")
            has_system_batches = bool(cur.fetchone())
            conn.close()
        except Exception:
            has_system_batches = False

        any_batch = any(
            bool(it.get("batch_no")) or bool(it.get("is_pharmacy_product")) or bool(it.get("has_batch"))
            for it in getattr(self, "items", [])
        )

        show = has_system_batches or any_batch
        self.table.setColumnHidden(2, not show) # Batch No
        self.table.setColumnHidden(3, not show) # Expiry

    def add_product(self, product):
        for i, item in enumerate(self.items):
            if item["product_id"] == product["id"]:
                # Product already in table - just focus its qty field, don't auto-fill
                qty_widget = self.table.cellWidget(i, 3)
                if isinstance(qty_widget, QLineEdit):
                    qty_widget.setFocus()
                    qty_widget.selectAll()
                return

        new_item = {
            "product_id": product["id"],
            "name":       product["name"],
            "part_no":    product.get("part_no", ""),
            "batch_no":   "",
            "expiry_date":"",
            "qty":        0.0,
            "cost":       product.get("cost_price", 0.0),
            "uom":        product.get("uom", "nos") or "nos",
            "disc":       0.0,
            "tax":        0.0,
            "selling":    product.get("price", 0.0),
            "is_pharmacy_product": bool(product.get("is_pharmacy_product", False)),
        }
        self.items.append(new_item)
        self._update_batch_columns_visibility()
        self._add_row_to_table(len(self.items) - 1, new_item)

    def _add_row_to_table(self, idx, item):
        self._update_batch_columns_visibility()
        row = max(self.table.rowCount() - 1, 0)
        self.table.insertRow(row)
        self.table.setRowHeight(row, 38)

        # 0 – Item No.
        p_item = QTableWidgetItem(item["part_no"])
        p_item.setTextAlignment(Qt.AlignCenter)
        p_item.setFlags(p_item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, 0, p_item)

        # 1 – Item Details
        n_item = QTableWidgetItem(item["name"])
        n_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        n_item.setFlags(n_item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, 1, n_item)

        def _tbl_input(val, cb):
            e = QLineEdit(str(val))
            e.setAlignment(Qt.AlignCenter)
            e.setStyleSheet(f"""
                QLineEdit {{
                    border:1px solid {BORDER}; border-radius:4px;
                    padding:3px; background:{WHITE}; color:{NAVY}; font-size:11px;
                }}
                QLineEdit:focus {{
                    border:1.5px solid {ACCENT}; background:#fff8e1;
                }}
            """)
            e.textChanged.connect(cb)
            return e

        class DatePickerButton(QPushButton):
            def __init__(self, val=""):
                super().__init__()
                self.val = val
                self.setText(val if val else "Select Date")
                self.setCursor(Qt.PointingHandCursor)
                self.setStyleSheet(f"""
                    QPushButton {{
                        background: {WHITE}; color: {NAVY};
                        border: 1px solid {BORDER}; border-radius: 4px;
                        padding: 3px; font-size: 11px; text-align: left;
                    }}
                    QPushButton:hover {{ border: 1.5px solid {ACCENT}; background: #fff8e1; }}
                """)
                self.clicked.connect(self._show_calendar)
                self._cb = None

            def setCallback(self, cb):
                self._cb = cb

            def setReadOnly(self, ro):
                self.setEnabled(not ro)

            def _show_calendar(self):
                from PySide6.QtWidgets import QDialog, QVBoxLayout, QCalendarWidget
                from PySide6.QtCore import QDate, Qt
                
                dlg = QDialog(self)
                dlg.setWindowFlags(Qt.Popup)
                lay = QVBoxLayout(dlg)
                lay.setContentsMargins(0, 0, 0, 0)
                
                cal = QCalendarWidget()
                if self.val:
                    cal.setSelectedDate(QDate.fromString(self.val, "yyyy-MM-dd"))
                lay.addWidget(cal)
                
                def on_date_selected():
                    selected = cal.selectedDate().toString("yyyy-MM-dd")
                    self.val = selected
                    self.setText(selected)
                    if self._cb:
                        self._cb(selected)
                    dlg.accept()
                    
                cal.activated.connect(on_date_selected)
                cal.clicked.connect(on_date_selected)
                
                dlg.move(self.mapToGlobal(self.rect().bottomLeft()))
                dlg.exec()

        def _date_input(val, cb):
            btn = DatePickerButton(val)
            btn.setCallback(cb)
            return btn

        try:
            from database.db import get_connection, fetchall_dicts
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT batch_no, expiry_date FROM product_batches WHERE product_id = ?", (item['product_id'],))
            batches = fetchall_dicts(cur)
            conn.close()
        except:
            batches = []

        batch_edit = QComboBox()
        batch_edit.setEditable(True)
        batch_edit.addItems([b['batch_no'] for b in batches if b.get('batch_no')])
        batch_edit.setCurrentText(item.get("batch_no", ""))
        batch_edit.setStyleSheet(f"""
            QComboBox {{
                border:1px solid {BORDER}; border-radius:4px;
                padding:3px; background:{WHITE}; color:{NAVY}; font-size:11px;
            }}
            QComboBox:focus {{
                border:1.5px solid {ACCENT}; background:#fff8e1;
            }}
            QComboBox QAbstractItemView {{
                background: {WHITE}; color: {NAVY};
                border: 1px solid {BORDER}; border-radius: 4px;
                font-size: 13px; padding: 4px; outline: none;
                selection-background-color: {SUCCESS};
                selection-color: {WHITE};
            }}
            QComboBox QAbstractItemView::item {{
                padding: 10px;
                min-height: 30px;
                border-bottom: 1px solid #f1f5f9;
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: {SUCCESS};
                color: {WHITE};
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {SUCCESS};
                color: {WHITE};
            }}
        """)

        expiry_edit = _date_input(item.get("expiry_date", ""), lambda t, i=idx: self._update_item(i, "expiry_date", t))

        def _on_batch_changed(text):
            self._update_item(idx, "batch_no", text)
            for b in batches:
                if b['batch_no'] == text and b['expiry_date']:
                    expiry_str = str(b['expiry_date'])
                    expiry_edit.setText(expiry_str)
                    self._update_item(idx, "expiry_date", expiry_str)
                    break
        
        batch_edit.currentTextChanged.connect(_on_batch_changed)


        cost_edit = _tbl_input(f"{item['cost']:.2f}" if item['cost'] > 0.0 else "",
                               lambda t, i=idx: self._update_item(i, "cost", t))
        qty_edit = _tbl_input(f"{item['qty']:.2f}" if item['qty'] > 0.0 else "",
                               lambda t, i=idx: self._update_item(i, "qty", t))
        uom_edit = _tbl_input(item["uom"],
                               lambda t, i=idx: self._update_item(i, "uom", t))
        disc_edit = _tbl_input(f"{item['disc']:.2f}",
                               lambda t, i=idx: self._update_item(i, "disc", t))
        tax_edit = _tbl_input(f"{item['tax']:.2f}",
                               lambda t, i=idx: self._update_item(i, "tax", t))

        if self.is_return:
            cost_edit.setReadOnly(True)
            uom_edit.setReadOnly(True)
            disc_edit.setReadOnly(True)
            tax_edit.setReadOnly(True)
            batch_edit.setEnabled(False)
            expiry_edit.setReadOnly(True)
            for ed in [cost_edit, uom_edit, disc_edit, tax_edit]:
                ed.setStyleSheet(ed.styleSheet() + f" QLineEdit {{ background:#f0f4f9; color:{MUTED}; }}")

        self.table.setCellWidget(row, 2, batch_edit)
        self.table.setCellWidget(row, 3, expiry_edit)
        self.table.setCellWidget(row, 4, cost_edit)
        self.table.setCellWidget(row, 5, qty_edit)
        self.table.setCellWidget(row, 6, uom_edit)
        self.table.setCellWidget(row, 7, disc_edit)
        self.table.setCellWidget(row, 8, tax_edit)

        tot_item = QTableWidgetItem()
        tot_item.setTextAlignment(Qt.AlignCenter)
        tot_item.setFlags(tot_item.flags() & ~Qt.ItemIsEditable)
        tot_item.setForeground(QColor(ACCENT))
        tot_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.table.setItem(row, 9, tot_item)

        del_btn = QPushButton()
        del_btn.setIcon(qta.icon("fa5s.trash-alt", color=DANGER))
        del_btn.setFixedSize(28, 28)
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setStyleSheet("border:none; background:transparent;")
        del_btn.clicked.connect(lambda _, i=idx: self._remove_item(i))
        if self.is_return:
            del_btn.setEnabled(False)
        self.table.setCellWidget(row, 10, del_btn)

        self._recalc_totals()

    def _refresh_table(self):
        self.table.setRowCount(0)
        for i, item in enumerate(self.items):
            self._add_row_to_table(i, item)
        if not getattr(self, "invoice_id", None) and not self.is_return:
            self._setup_inline_search_row()
        self._recalc_totals()

    def _update_item(self, idx, field, val):
        if idx >= len(self.items): return
        try:
            if field in ["cost", "qty", "disc", "tax"]:
                val_str = val.strip() if isinstance(val, str) else str(val).strip()
                self.items[idx][field] = float(val_str) if val_str else 0.0
            else:
                self.items[idx][field] = val
            self._recalc_totals()
        except: pass

    def _recalc_totals(self):
        total_qty  = 0.0
        grand_total = 0.0

        for i in range(self.table.rowCount()):
            c0 = self.table.cellWidget(i, 0)
            if c0 and getattr(c0, "is_inline_search", False):
                continue

            cost = qty = disc = tax = 0.0
            try:
                cw = self.table.cellWidget(i, 4)
                qw = self.table.cellWidget(i, 5)
                dw = self.table.cellWidget(i, 7)
                tw = self.table.cellWidget(i, 8)
                if cw: t = cw.text().strip(); cost = float(t) if t else 0.0
                if qw: t = qw.text().strip(); qty  = float(t) if t else 0.0
                if dw: t = dw.text().strip(); disc = float(t) if t else 0.0
                if tw: t = tw.text().strip(); tax  = float(t) if t else 0.0
            except: pass

            total_qty   += qty
            row_total    = max((cost * qty) - disc + tax, 0.0)
            grand_total += row_total

            ti = self.table.item(i, 9)
            if ti: ti.setText(f"${row_total:.2f}")

        self.lbl_row_count.setText(f"Rows: {len(self.items)}")
        self.lbl_total_qty.setText(f"{total_qty:.2f}")
        self.lbl_grand_total.setText(f"${grand_total:.2f}")

        prev_bal = getattr(self, "_supplier_prev_balance", 0.0)
        if self.paid_btn.isChecked():
            self.balance_edit.setText(f"{prev_bal:.2f}")
        else:
            if not getattr(self, "_balance_manually_edited", False):
                if self.is_return:
                    accumulated = prev_bal - grand_total
                else:
                    accumulated = prev_bal + grand_total
                self.balance_edit.setText(f"{accumulated:.2f}")

    def _remove_item(self, idx):
        if idx < len(self.items):
            self.items.pop(idx)
            self._refresh_table()

    # ── Save ─────────────────────────────────────────────────────────────────
    def _on_save(self, print_invoice=False):
        if not self.items:
            QMessageBox.warning(self, "Empty Invoice", "Please add at least one item.")
            return

        wh_id    = self.wh_combo.currentData()
        sup_name = self.sup_combo.currentText().strip()
        doc_no   = self.doc_no_edit.text().strip()
        date_time = self.date_time_edit.text().strip()
        is_paid = self.paid_btn.isChecked()
        balance_val = 0.0
        if not is_paid:
            try:
                entered_val = float(self.balance_edit.text().strip() or 0.0)
                prev_bal = getattr(self, "_supplier_prev_balance", 0.0)
                if self.is_return:
                    # For returns, we expect balance to go down by grand_total
                    balance_val = max(prev_bal - entered_val, 0.0)
                else:
                    # For invoices, we expect balance to go up by grand_total
                    balance_val = max(entered_val - prev_bal, 0.0)
            except:
                pass
        address            = self.address_edit.text().strip()
        supplier_invoice_no = self.supplier_invoice_edit.text().strip()
        reference_val      = self.reference_edit.currentData() or self.reference_edit.currentText()
        reference          = (reference_val or "").strip()

        from models.company_defaults import get_defaults
        defs  = get_defaults() or {}
        pl_id = defs.get("default_price_list_id", 1)



        try:
            success = create_stock_entry(
                warehouse_id=wh_id,
                price_list_id=pl_id,
                items=self.items,
                supplier=sup_name,
                doc_no=doc_no,
                date_time=date_time,
                balance=balance_val,
                is_paid=is_paid,
                address=address,
                supplier_invoice_no=supplier_invoice_no,
                reference=reference,
                is_return=self.is_return,
                source_doc_no=self.source_doc_no
            )
            if success:
                if print_invoice:
                    pass
                else:
                    pass
                self.accept()
            else:
                raise Exception("DB query did not return success status.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save invoice: {e}")

    def _on_reprint(self):
        show_toast(self, "Invoice sent to printer!", kind="success")

    def _load_invoice_data(self):
        try:
            from database.db import get_connection, fetchall_dicts, fetchone_dict
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT * FROM stock_entries WHERE id = ?", (self.invoice_id,))
            inv = fetchone_dict(cur)
            if not inv:
                conn.close()
                return

            self.doc_no_edit.setText(inv.get("doc_no") or "")
            self.date_time_edit.setText(str(inv.get("date_time") or ""))
            self.address_edit.setText(inv.get("address") or "")
            self.supplier_invoice_edit.setText(inv.get("supplier_invoice_no") or "")
            self.balance_edit.setText(f"{float(inv.get('balance') or 0):.2f}")
            self.paid_btn.setChecked(bool(inv.get("is_paid")))
            
            ref = inv.get("reference")
            if ref:
                idx = self.reference_edit.findData(ref)
                if idx == -1: idx = self.reference_edit.findText(ref)
                if idx >= 0: self.reference_edit.setCurrentIndex(idx)

            # Set warehouse
            wh_id = inv.get("warehouse_id")
            if wh_id:
                idx = self.wh_combo.findData(wh_id)
                if idx >= 0: self.wh_combo.setCurrentIndex(idx)
            
            # Set supplier
            sup = inv.get("supplier")
            if sup:
                idx = self.sup_combo.findText(sup)
                if idx >= 0: self.sup_combo.setCurrentIndex(idx)

            # Load items
            cur.execute("""
                SELECT sei.*, p.name, p.part_no, p.uom
                FROM stock_entry_items sei
                JOIN products p ON sei.product_id = p.id
                WHERE sei.parent_id = ?
            """, (self.invoice_id,))
            items = fetchall_dicts(cur)
            conn.close()

            self.items = []
            for item in items:
                self.items.append({
                    "product_id": item["product_id"],
                    "name": item["name"],
                    "part_no": item["part_no"],
                    "batch_no": item.get("batch_no") or "",
                    "expiry_date": str(item.get("expiry_date") or "") if item.get("expiry_date") else "",
                    "qty": float(item["qty"] or 0),
                    "cost": float(item["cost_price"] or 0),
                    "selling": float(item.get("selling_price") or 0),
                    "uom": item.get("uom") or "nos",
                    "disc": 0.0,
                    "tax": 0.0
                })
            
            self._refresh_table()

        except Exception as e:
            print(f"Error loading invoice data: {e}")

    def _set_read_only_mode(self):
        self.sup_combo.setEnabled(False)
        self.wh_combo.setEnabled(False)
        self.supplier_invoice_edit.setReadOnly(True)
        self.paid_btn.setEnabled(False)
        self.balance_edit.setReadOnly(True)
        self.reference_edit.setEnabled(False)
        self.date_time_edit.setReadOnly(True)
        
        self.save_btn.hide()
        self.save_print_btn.hide()
        self.reprint_btn.show()
        
        self.add_sup_btn.hide()
        self.add_wh_btn.hide()
        if hasattr(self, "search_edit") and self.search_edit:
            self.search_edit.hide()
        
        # Hide delete buttons and inline search if they exist
        if hasattr(self, "inline_search_edit") and self.inline_search_edit:
            self.inline_search_edit.hide()
        
        # Disable editing in table cells
        for i in range(self.table.rowCount()):
            for j in range(self.table.columnCount()):
                w = self.table.cellWidget(i, j)
                if isinstance(w, QLineEdit):
                    w.setReadOnly(True)
                elif isinstance(w, QPushButton) or isinstance(w, QComboBox):
                    w.setEnabled(False)

    # ── Quick-add helpers ────────────────────────────────────────────────────
    def _add_new_supplier(self):
        try:
            dlg = QuickAddSupplierDialog(self)

            def on_created(new_sup):
                self._load_combos()
                idx = self.sup_combo.findText(new_sup["name"])
                if idx >= 0: self.sup_combo.setCurrentIndex(idx)

            dlg.supplier_created.connect(on_created)
            dlg.exec()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to add supplier: {e}")

    def _add_new_warehouse(self):
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Add Warehouse", "Warehouse Name:")
        if ok and name.strip():
            try:
                from database.db import get_connection
                conn = get_connection(); cur = conn.cursor()
                cur.execute("SELECT TOP 1 id FROM companies")
                row = cur.fetchone()
                c_id = row[0] if row else 1
                conn.close()
                create_warehouse(name.strip(), c_id)
                self._load_combos()
                idx = self.wh_combo.findText(name.strip())
                if idx >= 0: self.wh_combo.setCurrentIndex(idx)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to add warehouse: {e}")

    # ── Key events ───────────────────────────────────────────────────────────
    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            sw  = getattr(self, "inline_search_edit", None)
            txt = sw.text().strip() if sw else ""
            if not txt: txt = self.search_edit.text().strip()

            if txt:
                try:
                    from database.db import get_connection
                    conn = get_connection(); cur = conn.cursor()
                    cur.execute(
                        "SELECT part_no, uom FROM product_barcodes WHERE barcode = ?",
                        (txt,),
                    )
                    row = cur.fetchone(); conn.close()
                    if row:
                        from models.product import get_product_by_part_no
                        prod = get_product_by_part_no(row[0])
                        if prod:
                            prod["uom"] = row[1]
                            self.add_product(prod)
                            if sw: sw.clear()
                            self.search_edit.clear()
                            return
                except Exception as e:
                    print(f"[PI] Alternative barcode lookup failed: {e}")

                prods = search_products(txt)
                if prods:
                    self.add_product(prods[0])
                    if sw: sw.clear()
                    self.search_edit.clear()
                    return
        super().keyPressEvent(event)
