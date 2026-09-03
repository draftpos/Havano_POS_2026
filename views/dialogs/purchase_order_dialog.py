# =============================================================================
# views/dialogs/purchase_order_dialog.py
# =============================================================================

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QWidget, QFrame, QGraphicsDropShadowEffect, QMessageBox,
    QComboBox, QAbstractItemView, QCompleter, QGridLayout
)
from PySide6.QtCore import Qt, QSize, QTimer, QEvent
from PySide6.QtGui import QColor, QIcon, QFont
import qtawesome as qta
import datetime

from models.product import search_products, get_all_products
from models.purchase_order import create_purchase_order
from models.supplier import get_all_suppliers, create_supplier
from models.warehouse import get_all_warehouses, create_warehouse
from models.cost_center import get_all_cost_centers, create_cost_center
from views.dialogs.purchase_invoice_dialog import QuickAddSupplierDialog
from utils.toast import show_toast

# Havano Palette
from theme import *

class PurchaseOrderDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Purchase Order")
        self.setWindowFlags(Qt.Window | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)
        self.setWindowState(Qt.WindowMaximized)

        self.items = [] # List of dicts: {"product_id", "name", "part_no", "qty", "cost", "uom", "disc", "tax"}
        self._supplier_cache = {}
        
        self._build_ui()
        self._load_combos()
        self._setup_completer()

    def eventFilter(self, obj, event):
        if getattr(self, "_block_popup", False):
            ret = super().eventFilter(obj, event)
            return bool(ret) if ret is not None else False

        if event.type() == QEvent.FocusIn:
            combos = [self.sup_combo, self.wh_combo, self.cc_combo]
            if hasattr(self, "inline_search_edit"):
                combos.append(self.inline_search_edit)
            for combo in combos:
                target = combo.lineEdit() if hasattr(combo, "lineEdit") else combo
                if obj == target:
                    completer = combo.completer() if hasattr(combo, "completer") else getattr(obj, "completer", lambda: None)()
                    if completer and not completer.popup().isVisible():
                        QTimer.singleShot(100, completer.complete)
        ret = super().eventFilter(obj, event)
        return bool(ret) if ret is not None else False

    def _build_ui(self):
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setObjectName("poCard")
        card.setStyleSheet(f"""
            QFrame#poCard {{
                background:{WHITE}; border-radius:0px;
                border: none;
            }}
        """)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15); shadow.setXOffset(0); shadow.setYOffset(5)
        shadow.setColor(QColor(0, 0, 0, 30))
        card.setGraphicsEffect(shadow)
        main_lay.addWidget(card)

        cl = QVBoxLayout(card); cl.setContentsMargins(0, 0, 0, 0); cl.setSpacing(0)

        # ── HEADER ──────────────────────────────────────────────────────────
        hdr = QWidget(); hdr.setFixedHeight(90)
        hdr.setStyleSheet(f"""
            QWidget {{
                background: {NAVY};
                border-top-left-radius:0px; border-top-right-radius:0px;
            }}
        """)
        hl = QHBoxLayout(hdr); hl.setContentsMargins(25, 0, 25, 0)
        
        v_title = QVBoxLayout(); v_title.setSpacing(2); v_title.setAlignment(Qt.AlignVCenter)
        ttl = QLabel("Purchase Order")
        ttl.setStyleSheet(f"color:{WHITE}; font-size:22px; font-weight:bold; background:transparent;")
        sub = QLabel("Order stock from suppliers, manage cost centers and warehouses")
        sub.setStyleSheet(f"color:{MUTED}; font-size:12px; background:transparent;")
        v_title.addWidget(ttl); v_title.addWidget(sub)
        hl.addLayout(v_title)

        hl.addStretch()

        # Action Buttons in Header
        self.save_btn = QPushButton("  Confirm Order")
        self.save_btn.setIcon(qta.icon("fa5s.check-circle", color=WHITE))
        self.save_btn.setFixedSize(180, 45)
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background: {SUCCESS}; color: {WHITE}; border: none;
                border-radius: 8px; font-size: 14px; font-weight: bold;
            }}
            QPushButton:hover {{ background: #1f9447; }}
        """)
        self.save_btn.clicked.connect(self._save)
        hl.addWidget(self.save_btn)
        # Close button removed - use the native title bar ✕ to close

        cl.addWidget(hdr)

        # ── BODY ──────────────────────────────────────────────────────────────
        body = QWidget()
        bl = QVBoxLayout(body); bl.setContentsMargins(25, 20, 25, 20); bl.setSpacing(15)

        # Container Frame for Inputs
        form_frame = QFrame()
        form_frame.setStyleSheet(f"""
            QFrame {{
                background: {OFF_WHITE};
                border: 1px solid {BORDER};
                border-radius: 12px;
            }}
            QLabel {{
                border: none; background: transparent;
            }}
        """)
        grid_lay = QGridLayout(form_frame)
        grid_lay.setContentsMargins(20, 20, 20, 20)
        grid_lay.setHorizontalSpacing(25)
        grid_lay.setVerticalSpacing(15)

        # Styles
        lbl_style = f"color:{MUTED}; font-size:10px; font-weight:bold;"
        input_style = f"""
            QLineEdit, QComboBox {{
                border: 1px solid {BORDER}; border-radius: 8px; 
                padding: 0 12px; background: {WHITE}; color: {NAVY};
                font-size: 13px; font-weight: 500;
            }}
            QLineEdit:focus, QComboBox:focus {{
                border: 1.5px solid {ACCENT};
            }}
        """

        # Supplier
        sup_lbl = QLabel("SUPPLIER")
        sup_lbl.setStyleSheet(lbl_style)
        
        sup_inner = QHBoxLayout(); sup_inner.setSpacing(5)
        self.sup_combo = QComboBox()
        self.sup_combo.setEditable(True)
        self.sup_combo.setFixedHeight(40)
        self.sup_combo.setStyleSheet(input_style)
        
        add_sup_btn = QPushButton()
        add_sup_btn.setIcon(qta.icon("fa5s.plus", color=WHITE))
        add_sup_btn.setFixedSize(40, 40)
        add_sup_btn.setCursor(Qt.PointingHandCursor)
        add_sup_btn.setStyleSheet(f"background:{ACCENT}; border-radius:8px; border:none;")
        add_sup_btn.clicked.connect(self._add_new_supplier)
        sup_inner.addWidget(self.sup_combo, 1); sup_inner.addWidget(add_sup_btn)

        # Warehouse
        wh_lbl = QLabel("WAREHOUSE")
        wh_lbl.setStyleSheet(lbl_style)
        
        wh_inner = QHBoxLayout(); wh_inner.setSpacing(5)
        self.wh_combo = QComboBox()
        self.wh_combo.setEditable(True)
        self.wh_combo.setFixedHeight(40)
        self.wh_combo.setStyleSheet(input_style)
        
        add_wh_btn = QPushButton()
        add_wh_btn.setIcon(qta.icon("fa5s.plus", color=WHITE))
        add_wh_btn.setFixedSize(40, 40)
        add_wh_btn.setCursor(Qt.PointingHandCursor)
        add_wh_btn.setStyleSheet(f"background:{ACCENT}; border-radius:8px; border:none;")
        add_wh_btn.clicked.connect(self._add_new_warehouse)
        wh_inner.addWidget(self.wh_combo, 1); wh_inner.addWidget(add_wh_btn)

        # Cost Center
        cc_lbl = QLabel("COST CENTER")
        cc_lbl.setStyleSheet(lbl_style)
        
        cc_inner = QHBoxLayout(); cc_inner.setSpacing(5)
        self.cc_combo = QComboBox()
        self.cc_combo.setEditable(True)
        self.cc_combo.setFixedHeight(40)
        self.cc_combo.setStyleSheet(input_style)
        
        add_cc_btn = QPushButton()
        add_cc_btn.setIcon(qta.icon("fa5s.plus", color=WHITE))
        add_cc_btn.setFixedSize(40, 40)
        add_cc_btn.setCursor(Qt.PointingHandCursor)
        add_cc_btn.setStyleSheet(f"background:{ACCENT}; border-radius:8px; border:none;")
        add_cc_btn.clicked.connect(self._add_new_cost_center)
        cc_inner.addWidget(self.cc_combo, 1); cc_inner.addWidget(add_cc_btn)

        # Add to Grid
        grid_lay.addWidget(sup_lbl, 0, 0)
        grid_lay.addLayout(sup_inner, 1, 0)
        
        grid_lay.addWidget(wh_lbl, 0, 1)
        grid_lay.addLayout(wh_inner, 1, 1)
        
        grid_lay.addWidget(cc_lbl, 0, 2)
        grid_lay.addLayout(cc_inner, 1, 2)

        bl.addWidget(form_frame)

        # ── ITEMS TABLE ───────────────────────────────────────────────────────
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels([
            "Item No.", "Item Details", "Amount", "Qty", "UOM", "Disc", "TAX", "Total", "Action"
        ])
        
        # Stylesheet & Section layout
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(8, QHeaderView.Fixed)
        self.table.setColumnWidth(8, 50)
        
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setShowGrid(True)
        self.table.setGridStyle(Qt.SolidLine)
        
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {WHITE};
                gridline-color: {LIGHT};
                border: 1px solid {BORDER};
                border-radius: 8px;
                outline: none;
            }}
            QTableWidget::item {{
                padding: 5px;
                color: {NAVY};
            }}
            QTableWidget::item:selected {{
                background-color: {LIGHT};
                color: {NAVY};
            }}
            QHeaderView::section {{
                background-color: {OFF_WHITE};
                color: {NAVY};
                padding: 8px;
                font-weight: bold;
                font-size: 12px;
                border: none;
                border-bottom: 2px solid {BORDER};
            }}
        """)
        bl.addWidget(self.table)

        # ── TABLE FOOTER SUMMARY ──────────────────────────────────────────────
        footer_summary = QFrame()
        footer_summary.setFixedHeight(50)
        footer_summary.setStyleSheet(f"""
            QFrame {{
                background: {OFF_WHITE};
                border: 1.5px solid {BORDER};
                border-radius: 8px;
            }}
            QLabel {{
                border: none; background: transparent;
                color: {NAVY}; font-size: 13px; font-weight: bold;
            }}
        """)
        fsl = QHBoxLayout(footer_summary)
        fsl.setContentsMargins(15, 0, 15, 0)
        
        self.lbl_row_count = QLabel("Rows: 0")
        
        lbl_tot_qty_title = QLabel("Total Qty: ")
        lbl_tot_qty_title.setStyleSheet(f"color:{MUTED}; font-weight:normal;")
        self.lbl_total_qty = QLabel("0.00")
        
        fsl.addWidget(self.lbl_row_count)
        fsl.addStretch()
        fsl.addWidget(lbl_tot_qty_title)
        fsl.addWidget(self.lbl_total_qty)
        
        # Grand Total Container
        total_card = QFrame()
        total_card.setStyleSheet(f"""
            QFrame {{
                background: {NAVY}; border-radius: 8px; border: none;
            }}
            QLabel {{
                color: {WHITE}; font-size: 16px; font-weight: bold;
            }}
        """)
        tcl = QHBoxLayout(total_card); tcl.setContentsMargins(20, 8, 20, 8)
        self.lbl_grand_total = QLabel("$0.00")
        tcl.addWidget(self.lbl_grand_total)
        
        fsl.addWidget(total_card)
        bl.addWidget(footer_summary)

        cl.addWidget(body, 1)

        # Initialize the inline search row at the bottom of the table
        self._setup_inline_search_row()

    def _setup_inline_search_row(self):
        row = self.table.rowCount()
        # If the table is not empty and the last row is already the search row, do nothing
        if row > 0:
            last_widget = self.table.cellWidget(row - 1, 0)
            if last_widget and getattr(last_widget, "is_inline_search", False):
                return

        # Insert search row at the bottom
        self.table.insertRow(row)
        self.table.setRowHeight(row, 40)
        self.table.setSpan(row, 0, 1, 2)

        search_edit = QLineEdit()
        search_edit.is_inline_search = True
        search_edit.setPlaceholderText("🔎 Scan barcode or search product here to add inline...")
        search_edit.setStyleSheet(f"""
            QLineEdit {{
                border: 1.5px solid {BORDER}; border-radius: 4px;
                padding: 4px 12px; background: {WHITE}; color: {NAVY};
                font-size: 13px; font-weight: 500;
            }}
            QLineEdit:focus {{
                border: 2.5px solid {ACCENT}; background: #fff8e1;
            }}
        """)

        if hasattr(self, "completer") and self.completer:
            search_edit.setCompleter(self.completer)

        search_edit.returnPressed.connect(lambda: self._on_inline_search_return(search_edit))
        self.table.setCellWidget(row, 0, search_edit)

        for col in range(2, 9):
            item = QTableWidgetItem("")
            item.setFlags(Qt.NoItemFlags)
            self.table.setItem(row, col, item)

        self.inline_search_edit = search_edit

    def _on_inline_search_return(self, search_edit):
        text = search_edit.text().strip()
        if not text:
            return

        # 1. Autocomplete mapping match
        product = self._product_map.get(text)
        if product:
            self.add_product(product)
            search_edit.clear()
            search_edit.setFocus()
            return

        # 2. Part number check
        from models.product import get_product_by_part_no
        product = get_product_by_part_no(text)
        if product:
            self.add_product(product)
            search_edit.clear()
            search_edit.setFocus()
            return

        # 3. Alternative barcode check
        try:
            from database.db import get_connection
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT part_no, uom FROM product_barcodes WHERE barcode = ?", (text,))
            row = cur.fetchone()
            conn.close()
            if row:
                part_no, alt_uom = row
                product = get_product_by_part_no(part_no)
                if product:
                    product["uom"] = alt_uom
                    self.add_product(product)
                    search_edit.clear()
                    search_edit.setFocus()
                    return
        except Exception as e:
            print(f"[PO] Inline alternative barcode check error: {e}")

        # 4. Wildcard search check
        prods = search_products(text)
        if len(prods) == 1:
            self.add_product(prods[0])
            search_edit.clear()
            search_edit.setFocus()
        elif len(prods) > 1:
            show_toast(self, "Multiple products found. Please select from the autocomplete popup.", kind="info")
        else:
            show_toast(self, "Product not found!", kind="warn")

    def add_product(self, product):
        for i, item in enumerate(self.items):
            if item["product_id"] == product["id"]:
                qty_widget = self.table.cellWidget(i, 3)
                if isinstance(qty_widget, QLineEdit):
                    try:
                        curr_qty = float(qty_widget.text() or 1.0)
                        qty_widget.setText(f"{curr_qty + 1.0:.2f}")
                    except:
                        qty_widget.setText("1.00")
                return

        new_item = {
            "product_id": product["id"],
            "name": product["name"],
            "part_no": product.get("part_no", ""),
            "qty": 1.0,
            "cost": product.get("cost", 0.0) or product.get("price", 0.0),
            "uom": product.get("uom", "nos") or "nos",
            "disc": 0.0,
            "tax": 0.0
        }
        self.items.append(new_item)
        self._add_row_to_table(len(self.items) - 1, new_item)

    def _add_row_to_table(self, idx, item):
        row = self.table.rowCount() - 1
        if row < 0:
            row = 0
        self.table.insertRow(row)
        self.table.setRowHeight(row, 40)

        # 0. Item No.
        p_item = QTableWidgetItem(item["part_no"])
        p_item.setTextAlignment(Qt.AlignCenter)
        p_item.setFlags(p_item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, 0, p_item)

        # 1. Item Details
        n_item = QTableWidgetItem(item["name"])
        n_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        n_item.setFlags(n_item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, 1, n_item)

        # Helper to create inputs
        def create_table_input(val, callback):
            edit = QLineEdit(str(val))
            edit.setAlignment(Qt.AlignCenter)
            edit.setStyleSheet(f"""
                QLineEdit {{
                    border: 1px solid {BORDER}; border-radius: 4px;
                    padding: 4px; background: {WHITE}; color: {NAVY};
                    font-size: 12px;
                }}
                QLineEdit:focus {{
                    border: 1.5px solid {ACCENT}; background: #fff8e1;
                }}
            """)
            edit.textChanged.connect(callback)
            return edit

        # 2. Amount $ (Cost)
        cost_edit = create_table_input(f"{item['cost']:.2f}", lambda t, i=idx: self._update_item(i, "cost", t))
        self.table.setCellWidget(row, 2, cost_edit)

        # 3. Qty
        qty_edit = create_table_input(f"{item['qty']:.2f}", lambda t, i=idx: self._update_item(i, "qty", t))
        self.table.setCellWidget(row, 3, qty_edit)

        # 4. UOM
        uom_edit = create_table_input(item["uom"], lambda t, i=idx: self._update_item(i, "uom", t))
        self.table.setCellWidget(row, 4, uom_edit)

        # 5. Disc
        disc_edit = create_table_input(f"{item['disc']:.2f}", lambda t, i=idx: self._update_item(i, "disc", t))
        self.table.setCellWidget(row, 5, disc_edit)

        # 6. TAX
        tax_edit = create_table_input(f"{item['tax']:.2f}", lambda t, i=idx: self._update_item(i, "tax", t))
        self.table.setCellWidget(row, 6, tax_edit)

        # 7. Total $
        tot_item = QTableWidgetItem()
        tot_item.setTextAlignment(Qt.AlignCenter)
        tot_item.setFlags(tot_item.flags() & ~Qt.ItemIsEditable)
        tot_item.setForeground(QColor(ACCENT))
        tot_item.setFont(QFont("Arial", 10, QFont.Bold))
        self.table.setItem(row, 7, tot_item)

        # 8. Action (Delete)
        del_btn = QPushButton()
        del_btn.setIcon(qta.icon("fa5s.trash-alt", color=DANGER))
        del_btn.setFixedSize(30, 30)
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setStyleSheet("border:none; background:transparent;")
        del_btn.clicked.connect(lambda _, i=idx: self._remove_item(i))
        self.table.setCellWidget(row, 8, del_btn)

        # Recalculate
        self._recalc_totals()

    def _refresh_table(self):
        self.table.setRowCount(0)
        for i, item in enumerate(self.items):
            self._add_row_to_table(i, item)
        self._setup_inline_search_row()
        self._recalc_totals()

    def _update_item(self, idx, field, val):
        if idx >= len(self.items): return
        try:
            if field in ["cost", "qty", "disc", "tax"]:
                self.items[idx][field] = float(val or 0.0)
            else:
                self.items[idx][field] = val
            self._recalc_totals()
        except: pass

    def _remove_item(self, idx):
        if idx < len(self.items):
            self.items.pop(idx)
            self._refresh_table()

    def _recalc_totals(self):
        total_qty = 0.0
        grand_total = 0.0
        
        for i in range(self.table.rowCount()):
            cost_widget = self.table.cellWidget(i, 2)
            qty_widget = self.table.cellWidget(i, 3)
            disc_widget = self.table.cellWidget(i, 5)
            tax_widget = self.table.cellWidget(i, 6)
            
            # Skip the inline search row
            c0_widget = self.table.cellWidget(i, 0)
            if c0_widget and getattr(c0_widget, "is_inline_search", False):
                continue
                
            cost = 0.0
            qty = 0.0
            disc = 0.0
            tax = 0.0
            try:
                if cost_widget: cost = float(cost_widget.text() or 0.0)
                if qty_widget: qty = float(qty_widget.text() or 0.0)
                if disc_widget: disc = float(disc_widget.text() or 0.0)
                if tax_widget: tax = float(tax_widget.text() or 0.0)
            except: pass
            
            total_qty += qty
            row_total = max((cost * qty) - disc + tax, 0.0)
            grand_total += row_total
            
            tot_item = self.table.item(i, 7)
            if tot_item:
                tot_item.setText(f"${row_total:.2f}")

        self.lbl_row_count.setText(f"Rows: {len(self.items)}")
        self.lbl_total_qty.setText(f"{total_qty:.2f}")
        self.lbl_grand_total.setText(f"${grand_total:.2f}")

    def _setup_completer(self):
        try:
            # 1. Product Search Completer
            products = get_all_products()
            self._product_map = {f"{p['part_no']} | {p['name']}": p for p in products}
            
            p_completer = QCompleter(list(self._product_map.keys()), self)
            p_completer.setCaseSensitivity(Qt.CaseInsensitive)
            p_completer.setFilterMode(Qt.MatchContains)
            self._style_completer(p_completer)
            
            self.completer = p_completer
            if hasattr(self, "inline_search_edit") and self.inline_search_edit:
                self.inline_search_edit.setCompleter(p_completer)
            p_completer.activated.connect(self._on_completer_activated)

            # 2. Helper for combo completers
            def _setup_combo_completer(combo):
                completer = QCompleter(combo.model(), self)
                completer.setCaseSensitivity(Qt.CaseInsensitive)
                completer.setFilterMode(Qt.MatchContains)
                completer.setCompletionMode(QCompleter.PopupCompletion)
                self._style_completer(completer)
                combo.setCompleter(completer)
                combo.setEditable(True)
                combo.lineEdit().installEventFilter(self)

            _setup_combo_completer(self.sup_combo)
            _setup_combo_completer(self.wh_combo)
            _setup_combo_completer(self.cc_combo)

        except Exception as e:
            print(f"[PO] Completer setup error: {e}")

    def _style_completer(self, completer):
        popup = completer.popup()
        popup.setStyleSheet(f"""
            QAbstractItemView {{
                background-color: {WHITE};
                color: {NAVY};
                selection-background-color: {ACCENT};
                selection-color: {WHITE};
                border: 1px solid {BORDER};
                border-radius: 4px;
                font-size: 13px;
            }}
        """)

    def _on_completer_activated(self, text):
        self._block_popup = True
        product = self._product_map.get(text)
        if product:
            self.add_product(product)
            search_widget = getattr(self, "inline_search_edit", None)
            if search_widget:
                if search_widget.completer():
                    search_widget.completer().popup().hide()
                search_widget.clear()
                search_widget.setFocus()
            
            # Focus the table (amount column of the last added row)
            self.table.setFocus()
            last_row = self.table.rowCount() - 2 # -2 since the very last row is the search box!
            if last_row >= 0:
                self.table.setCurrentCell(last_row, 2)
                amt_widget = self.table.cellWidget(last_row, 2)
                if amt_widget: amt_widget.setFocus()
        
        QTimer.singleShot(300, lambda: setattr(self, "_block_popup", False))

    def _load_combos(self):
        self._load_suppliers()
        self._load_warehouses()
        self._load_cost_centers()

    def _load_suppliers(self):
        try:
            self.sup_combo.clear()
            for s in get_all_suppliers():
                self.sup_combo.addItem(s.get("name"), s.get("id"))
        except Exception as e:
            print(f"[PO] Load suppliers error: {e}")

    def _load_warehouses(self):
        try:
            self.wh_combo.clear()
            whs = get_all_warehouses()
            for w in whs:
                self.wh_combo.addItem(w.get("name"), w.get("id"))
            
            from models.company_defaults import get_defaults
            defaults = get_defaults() or {}
            target = defaults.get("server_warehouse", "").strip()
            if target:
                idx = self.wh_combo.findText(target)
                if idx >= 0:
                    self.wh_combo.setCurrentIndex(idx)
        except Exception as e:
            print(f"[PO] Load warehouses error: {e}")

    def _load_cost_centers(self):
        try:
            self.cc_combo.clear()
            for cc in get_all_cost_centers():
                self.cc_combo.addItem(cc.get("name"), cc.get("id"))
        except Exception as e:
            print(f"[PO] Load cost centers error: {e}")

    def _add_new_supplier(self):
        dlg = QuickAddSupplierDialog(self)
        dlg.supplier_created.connect(self._on_supplier_created)
        dlg.exec()

    def _on_supplier_created(self, supplier_dict):
        self._load_suppliers()
        name = supplier_dict.get("name", "")
        idx = self.sup_combo.findText(name)
        if idx >= 0:
            self.sup_combo.setCurrentIndex(idx)

    def _add_new_warehouse(self):
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Add Warehouse", "Warehouse Name:")
        if ok and name.strip():
            try:
                from models.company_defaults import get_defaults
                defs = get_defaults()
                create_warehouse(name.strip(), defs.get("company_id", 1))
                self._load_warehouses()
                idx = self.wh_combo.findText(name.strip())
                if idx >= 0: self.wh_combo.setCurrentIndex(idx)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to add warehouse: {e}")

    def _add_new_cost_center(self):
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Add Cost Center", "Cost Center Name:")
        if ok and name.strip():
            try:
                from models.company_defaults import get_defaults
                defs = get_defaults()
                create_cost_center(name.strip(), defs.get("company_id", 1))
                self._load_cost_centers()
                idx = self.cc_combo.findText(name.strip())
                if idx >= 0: self.cc_combo.setCurrentIndex(idx)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to add cost center: {e}")

    def _save(self):
        if not self.items:
            QMessageBox.warning(self, "Empty Order", "Please add at least one product.")
            return
            
        supplier = self.sup_combo.currentText().strip() or "General Supplier"
        warehouse = self.wh_combo.currentText().strip() or "Main Warehouse"
        
        warehouse_id = self.wh_combo.currentData()
        cost_center_id = self.cc_combo.currentData()

        # Format items to expected DB inputs: list of dict with {"product_id", "qty", "cost_price"}
        formatted_items = []
        for item in self.items:
            formatted_items.append({
                "product_id": item["product_id"],
                "qty": item["qty"],
                "cost_price": item["cost"]
            })

        po_id = create_purchase_order(supplier, warehouse, formatted_items, warehouse_id=warehouse_id, cost_center_id=cost_center_id)

        if po_id:
            show_toast(self.parent() or self, f"Purchase Order #{po_id} recorded successfully!", kind="success")
            QTimer.singleShot(1500, self.accept)
        else:
            QMessageBox.critical(self, "Error", "Failed to create Purchase Order.")
