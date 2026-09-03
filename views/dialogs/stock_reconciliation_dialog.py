# views/dialogs/stock_reconciliation_dialog.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QWidget, QFrame, QGraphicsDropShadowEffect, QMessageBox,
    QAbstractItemView, QComboBox, QCompleter, QMenu
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QDoubleValidator
import qtawesome as qta
from utils.toast import show_toast

# Havano Palette
from theme import *
from models.company_defaults import get_defaults

def _top_btn(text, icon, bg, hov):
    b = QPushButton(text)
    b.setIcon(qta.icon(icon, color=WHITE))
    b.setFixedHeight(40)
    b.setCursor(Qt.PointingHandCursor)
    b.setStyleSheet(f"""
        QPushButton {{
            background:{bg}; color:{WHITE}; border:none; border-radius:8px;
            font-size:13px; font-weight:bold; padding:0 18px;
        }}
        QPushButton:hover {{ background:{hov}; }}
    """)
    return b

class StockReconciliationDialog(QDialog):
    def __init__(self, parent=None, entry_id=None):
        super().__init__(parent)
        self.entry_id = entry_id
        self.setWindowTitle("Stock Take")
        self.setWindowFlags(Qt.Window | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)
        self.setWindowState(Qt.WindowMaximized)
        
        self._products = []
        self._build_ui()
        if self.entry_id:
            self._load_read_only()
        else:
            self._execute_fetch()

    def _build_ui(self):
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(10, 10, 10, 10)
        
        card = QFrame()
        card.setObjectName("reconCard")
        card.setStyleSheet(f"""
            QFrame#reconCard {{
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
        
        # ── HEADER ────────────────────────────────────────────────────────
        hdr = QFrame()
        hdr.setFixedHeight(60)
        hdr.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border-bottom: 1px solid #e4eaf4;
            }
        """)
        hl = QHBoxLayout(hdr); hl.setContentsMargins(15, 8, 15, 6)
        
        v_title = QVBoxLayout(); v_title.setSpacing(2); v_title.setAlignment(Qt.AlignVCenter)
        title_lbl = QLabel("Stock Take")
        title_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #1a5fb4; border: none; padding: 0px; margin: 0px; background: transparent;")
        sub_lbl = QLabel("Adjust inventory levels to match physical count")
        sub_lbl.setStyleSheet("font-size: 11px; color: #666666; border: none; padding: 0px; margin: 0px; background: transparent;")
        v_title.addWidget(title_lbl); v_title.addWidget(sub_lbl)
        hl.addLayout(v_title)
        
        hl.addStretch()
        
        self.save_btn = QPushButton(" Submit")
        self.save_btn.setIcon(qta.icon("fa5s.check-circle", color="white", scale_factor=0.7))
        self.save_btn.setFixedHeight(30)
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.setStyleSheet("""
            QPushButton { background-color: #1a5fb4; color: white; border: none; border-radius: 4px; padding: 0 12px; font-weight: bold; font-size: 11px; }
            QPushButton:hover { background-color: #1c6dd0; }
        """)
        self.save_btn.clicked.connect(self._on_submit)
        
        self.btn_print = QPushButton(" Print Sheet")
        self.btn_print.setIcon(qta.icon("fa5s.print", color="white", scale_factor=0.7))
        self.btn_print.setFixedHeight(30)
        self.btn_print.setStyleSheet("""
            QPushButton { background-color: #1a7a3c; color: white; border: none; border-radius: 4px; padding: 4px 12px; font-weight: bold; font-size: 11px; }
            QPushButton::menu-indicator { image: none; }
            QPushButton:hover { background-color: #1e8f46; }
        """)
        
        print_menu = QMenu(self.btn_print)
        print_menu.setStyleSheet("QMenu { background: white; border: 1px solid #c8d8ec; } QMenu::item { padding: 8px 25px; color: #1a5fb4; } QMenu::item:selected { background: #e8f1f8; }")
        a_blind = print_menu.addAction("Print Blind Count (Hide Qty)")
        a_show = print_menu.addAction("Print Standard Count (Show Qty)")
        a_blind.triggered.connect(lambda: self._print_count_sheet(blind=True))
        a_show.triggered.connect(lambda: self._print_count_sheet(blind=False))
        self.btn_print.setMenu(print_menu)
        hl.addWidget(self.btn_print)
        
        hl.addWidget(self.save_btn)
        cl.addWidget(hdr)
        
        # ── BODY ──────────────────────────────────────────────────────────────
        body = QWidget()
        bl = QVBoxLayout(body); bl.setContentsMargins(25, 20, 25, 20); bl.setSpacing(15)
        
        # Fetch Options and Global Remarks
        filter_lay = QHBoxLayout(); filter_lay.setSpacing(15)
        
        self.fetch_mode_combo = QComboBox()
        self.fetch_mode_combo.addItems(["Fetch all items", "Filter by Category", "Filter by single item"])
        self.fetch_mode_combo.setFixedHeight(30)
        self.fetch_mode_combo.setStyleSheet("""
            QComboBox { border: 1px solid #c8d8ec; border-radius: 4px; padding: 4px 8px; font-size: 11px; background: white; color: #333; }
        """)
        self.fetch_mode_combo.currentTextChanged.connect(self._on_fetch_mode_changed)
        filter_lay.addWidget(self.fetch_mode_combo)
        
        self.fetch_filter_combo = QComboBox()
        self.fetch_filter_combo.setFixedHeight(30)
        self.fetch_filter_combo.setMinimumWidth(250)
        self.fetch_filter_combo.setStyleSheet("""
            QComboBox { border: 1px solid #c8d8ec; border-radius: 4px; padding: 4px 8px; font-size: 11px; background: white; color: #333; }
            QComboBox::drop-down { border:none; width:20px; }
            QComboBox QAbstractItemView { border: 1px solid #c8d8ec; background: white; selection-background-color: #e8f1f8; selection-color: #1a5fb4; }
        """)
        self.fetch_filter_combo.setPlaceholderText("Search or select...")
        self.fetch_filter_combo.hide()
        filter_lay.addWidget(self.fetch_filter_combo)
        
        self.btn_fetch = QPushButton(" Fetch")
        self.btn_fetch.setIcon(qta.icon("fa5s.sync", color="white", scale_factor=0.7))
        self.btn_fetch.setFixedHeight(30)
        self.btn_fetch.setStyleSheet("""
            QPushButton { background-color: #1a5fb4; color: white; border: none; border-radius: 4px; padding: 4px 12px; font-weight: bold; font-size: 11px; }
            QPushButton:hover { background-color: #1c6dd0; }
        """)
        self.btn_fetch.clicked.connect(self._execute_fetch)
        filter_lay.addWidget(self.btn_fetch)
        

        
        # Global Remarks
        self.remarks_edit = QLineEdit()
        self.remarks_edit.setPlaceholderText("Enter global remarks here...")
        self.remarks_edit.setFixedHeight(30)
        self.remarks_edit.setStyleSheet("""
            QLineEdit { border: 1px solid #c8d8ec; border-radius: 4px; padding: 4px 8px; font-size: 11px; background: white; color: #333; }
            QLineEdit:focus { border: 1px solid #1a5fb4; }
        """)
        filter_lay.addWidget(self.remarks_edit, 1)

        # Search within table
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search in table...")
        self.search_input.setFixedHeight(30)
        self.search_input.setStyleSheet(self.remarks_edit.styleSheet())
        self.search_input.textChanged.connect(self._filter_table)
        filter_lay.addWidget(self.search_input, 1)
        
        bl.addLayout(filter_lay)

        # Table
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["CODE", "ITEM NAME", "BATCH", "CATEGORY", "SYSTEM QTY", "PHYSICAL QTY", "VAR QTY", "VAR. VALUE"])
        hh = self.table.horizontalHeader()
        hh.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        hh.setSectionResizeMode(QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.setColumnWidth(0, 180)
        hh.setSectionResizeMode(1, QHeaderView.Stretch) # Item Name takes bigger space
        hh.setSectionResizeMode(5, QHeaderView.Fixed)
        hh.setSectionResizeMode(6, QHeaderView.Fixed)
        hh.setSectionResizeMode(7, QHeaderView.Fixed)
        self.table.setColumnWidth(5, 120)
        self.table.setColumnWidth(6, 110)
        self.table.setColumnWidth(7, 110)
        
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setShowGrid(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setStyleSheet(f"""
            QTableWidget {{ 
                gridline-color: {LIGHT}; 
                border: 1px solid {BORDER}; 
                background-color: {WHITE}; 
                font-size: 13px; color: {NAVY}; 
            }}
            QHeaderView::section {{ 
                background-color: {OFF_WHITE}; 
                padding: 8px; border: none; 
                border-bottom: 1px solid {BORDER}; 
                border-right: 1px solid {LIGHT}; 
                font-weight: bold; font-size: 13px; color: {MUTED}; 
            }}
            QTableWidget::item {{ 
                padding: 6px; 
                border-bottom: 1px solid {LIGHT}; 
            }}
            QTableWidget::item:selected {{ 
                background-color: #e8f1f8; color: {NAVY}; 
            }}
            QScrollBar:vertical {{
                border: none;
                background: {OFF_WHITE};
                width: 16px;
                border-radius: 8px;
            }}
            QScrollBar::handle:vertical {{
                background: #b0bec5;
                min-height: 30px;
                border-radius: 6px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: #90a4ae;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
        """)
        bl.addWidget(self.table)
        
        totals_lay = QHBoxLayout()
        totals_lay.addStretch()
        comp = get_defaults()
        currency = comp.get('currency', '$')
        self.lbl_totals = QLabel(f"Total Variance: {currency}0.00")
        self.lbl_totals.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {NAVY}; padding: 5px;")
        totals_lay.addWidget(self.lbl_totals)
        bl.addLayout(totals_lay)
        
        cl.addWidget(body)

    def _load_read_only(self):
        self.fetch_mode_combo.hide()
        self.fetch_filter_combo.hide()
        self.btn_fetch.hide()
        self.save_btn.hide()
        self.btn_print.hide()
        
        try:
            from database.db import get_connection, fetchall_dicts
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT p.part_no, p.name, p.category, p.stock,
                       sei.qty as variance, sei.cost_price, sei.selling_price,
                       sei.system_qty, sei.physical_qty
                FROM stock_entry_items sei
                JOIN products p ON p.id = sei.product_id
                WHERE sei.parent_id = ?
            """, (self.entry_id,))
            items = fetchall_dicts(cur)
            
            cur.execute("SELECT reference FROM stock_entries WHERE id = ?", (self.entry_id,))
            ref = cur.fetchone()
            if ref:
                self.remarks_edit.setText(f"Read Only - {ref[0]}")
            self.remarks_edit.setReadOnly(True)
            self.search_input.show()
                
            conn.close()
            
            self.table.blockSignals(True)
            self.table.setRowCount(len(items))
            for r, item in enumerate(items):
                # 0: CODE
                code_str = str(item['part_no'] or "")
                if code_str.isdigit(): code_str = code_str.zfill(4)
                it_code = QTableWidgetItem(code_str)
                it_code.setFlags(it_code.flags() & ~Qt.ItemIsEditable)
                it_code.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                self.table.setItem(r, 0, it_code)
                
                # 1: NAME
                it_name = QTableWidgetItem(item['name'] or "")
                it_name.setFlags(it_name.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(r, 1, it_name)
                
                # 3: CATEGORY
                it_cat = QTableWidgetItem(item['category'] or "")
                it_cat.setFlags(it_cat.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(r, 3, it_cat)
                
                # 6: VARIANCE
                diff = float(item['variance'] or 0)
                
                # 3: SYSTEM QTY
                sys_qty = item.get('system_qty')
                if sys_qty is None:
                    sys_qty = float(item['stock'] or 0)
                else:
                    sys_qty = float(sys_qty)
                    
                sys_qty_str = f"{sys_qty:.2f}"
                it_sys = QTableWidgetItem(sys_qty_str)
                it_sys.setFlags(it_sys.flags() & ~Qt.ItemIsEditable)
                it_sys.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(r, 4, it_sys)
                
                # 5: PHYSICAL QTY
                phys = float(item.get('physical_qty') or 0)
                it_phys = QTableWidgetItem(f"{phys:.2f}")
                it_phys.setFlags(it_phys.flags() & ~Qt.ItemIsEditable)
                it_phys.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                it_phys.setBackground(QColor("#fcfcfc"))
                self.table.setItem(r, 5, it_phys)
                
                # 6: VAR QTY
                it_diff = QTableWidgetItem(f"{diff:+.2f}" if diff != 0 else "0.00")
                it_diff.setFlags(it_diff.flags() & ~Qt.ItemIsEditable)
                it_diff.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                
                # 7: VAR VALUE
                cost_price = float(item.get('cost_price', 0) or 0)
                if cost_price == 0.0:
                    cost_price = float(item.get('selling_price', 0) or 0)
                var_val = diff * cost_price
                if abs(var_val) < 0.001:
                    var_val = 0.0
                comp = get_defaults()
                currency = comp.get('currency', '$')
                
                var_val_item = QTableWidgetItem(f"{currency}{var_val:+.2f}" if var_val != 0 else f"{currency}0.00")
                var_val_item.setFlags(var_val_item.flags() & ~Qt.ItemIsEditable)
                var_val_item.setTextAlignment(Qt.AlignCenter)
                
                for it, val in [(it_diff, diff), (var_val_item, var_val)]:
                    if val > 0:
                        it.setForeground(QColor(0, 150, 0))
                    elif val < 0:
                        it.setForeground(QColor(200, 0, 0))
                
                self.table.setItem(r, 6, it_diff)
                self.table.setItem(r, 7, var_val_item)
                
                self.table.setRowHeight(r, 45)
            
            self.table.setColumnHidden(2, True)
            self.table.blockSignals(False)
            self._update_totals()
                
        except Exception as e:
            print(f"Error loading read-only data: {e}")

    def _on_fetch_mode_changed(self, mode):
        self.fetch_filter_combo.clear()
        if mode == "Fetch all items":
            self.fetch_filter_combo.hide()
        elif mode == "Filter by Category":
            self.fetch_filter_combo.show()
            self._load_groups()
        elif mode == "Filter by single item":
            self.fetch_filter_combo.show()
            self._load_all_items()

    def _load_groups(self):
        try:
            from database.db import get_connection
            conn = get_connection(); cur = conn.cursor()
            cur.execute("SELECT DISTINCT category FROM products WHERE category IS NOT NULL AND TRIM(category) != '' ORDER BY category")
            groups = [row[0] for row in cur.fetchall()]
            conn.close()
            self.fetch_filter_combo.addItems(groups)
            self.fetch_filter_combo.setEditable(False)
            self.fetch_filter_combo.setCompleter(None)
        except Exception as e:
            print(f"Error loading groups: {e}")

    def _load_all_items(self):
        try:
            from database.db import get_connection, fetchall_dicts
            conn = get_connection(); cur = conn.cursor()
            cur.execute("SELECT part_no, name FROM products WHERE ISNULL(active, 1) = 1 ORDER BY name")
            items = fetchall_dicts(cur)
            conn.close()
            self.fetch_filter_combo.addItems([f"{row['part_no']} - {row['name']}" for row in items])
            self.fetch_filter_combo.setEditable(True)
            self.fetch_filter_combo.setInsertPolicy(QComboBox.NoInsert)
            
            completer = QCompleter([f"{row['part_no']} - {row['name']}" for row in items], self.fetch_filter_combo)
            completer.setFilterMode(Qt.MatchContains)
            completer.setCaseSensitivity(Qt.CaseInsensitive)
            completer.setCompletionMode(QCompleter.PopupCompletion)
            
            popup = completer.popup()
            popup.setStyleSheet(f"""
                QListView {{
                    background-color: white; border: 1px solid {BORDER}; border-radius: 4px;
                    selection-background-color: {ACCENT}; selection-color: white; font-size: 14px; padding: 4px; outline: none;
                }}
                QListView::item {{ padding: 8px; }}
            """)
            self.fetch_filter_combo.setCompleter(completer)
        except Exception as e:
            print(f"Error loading items: {e}")

    def _execute_fetch(self):
        mode = self.fetch_mode_combo.currentText()
        val = self.fetch_filter_combo.currentText()
        
        try:
            from database.db import get_connection, fetchall_dicts
            conn = get_connection(); cur = conn.cursor()
            
            sql = "SELECT id, part_no, name, stock, category, cost_price, price FROM products WHERE ISNULL(active, 1) = 1"
            params = []
            
            if mode == "Filter by Category" and val:
                sql += " AND category = ?"
                params.append(val)
            elif mode == "Filter by single item" and val:
                # "part_no - name" format
                part = val.split(" - ")[0]
                sql += " AND part_no = ?"
                params.append(part)
                
            cur.execute(sql, params)
            self._products = fetchall_dicts(cur)
            conn.close()
            
            self._render_table(self._products)
            # show_toast(self.parent() or self, f"Fetched {len(self._products)} items.", kind="info")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to fetch products: {e}")

    def _render_table(self, products):
        self.table.blockSignals(True)
        self.table.setRowCount(len(products))
        
        combo_style = f"QComboBox {{ border: none !important; background-color: transparent !important; background: transparent !important; padding:4px 8px; margin: 0; color:{NAVY}; font-size:13px; }} QComboBox::drop-down {{ border: none; }}"
        any_batches = False
        
        for r, p in enumerate(products):
            # 0: CODE
            code_str = str(p['part_no'] or "")
            if code_str.isdigit(): code_str = code_str.zfill(4)
            it_code = QTableWidgetItem(code_str)
            it_code.setFlags(it_code.flags() & ~Qt.ItemIsEditable)
            it_code.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.table.setItem(r, 0, it_code)
            
            # 1: ITEM NAME
            it_name = QTableWidgetItem(p['name'])
            it_name.setFlags(it_name.flags() & ~Qt.ItemIsEditable)
            it_name.setData(Qt.UserRole, p['id'])
            self.table.setItem(r, 1, it_name)
            
            # 2: BATCH
            # Conditionally load batches only if batch ticked (assuming we check product_batches for existence)
            try:
                from database.db import get_connection, fetchall_dicts
                conn = get_connection(); cur = conn.cursor()
                cur.execute("SELECT batch_no, expiry_date, qty AS quantity FROM product_batches WHERE product_id = ?", (p['id'],))
                batches = fetchall_dicts(cur)
                
                # Check if it has has_batch column in products
                try:
                    cur.execute("SELECT has_batch FROM products WHERE id = ?", (p['id'],))
                    has_batch_val = cur.fetchone()[0]
                except:
                    has_batch_val = 0
                conn.close()
            except:
                batches = []
                has_batch_val = 0
            
            if not batches and not has_batch_val:
                batch_label = QLabel("0")
                batch_label.setAlignment(Qt.AlignCenter)
                batch_label.setStyleSheet(f"color: {MUTED}; border: none !important; background-color: transparent !important; background: transparent !important;")
                self.table.setCellWidget(r, 2, batch_label)
            else:
                any_batches = True
                batch_combo = QComboBox()
                batch_combo.setEditable(False)
                batch_combo.addItem("None", {"bn": "", "qty": float(p['stock'])})
                for b in batches:
                    bn = b.get('batch_no') or ''
                    exp = b.get('expiry_date') or ''
                    qty = float(b.get('qty') or b.get('quantity') or 0)
                    label = f"{bn}  -  exp: {exp}  |  qty: {qty}" if exp else f"{bn}  |  qty: {qty}"
                    batch_combo.addItem(label, {"bn": bn, "qty": qty})
                batch_combo.setStyleSheet(combo_style)
                batch_combo.setProperty("row", r)
                batch_combo.currentIndexChanged.connect(self._on_batch_changed)
                self.table.setCellWidget(r, 2, batch_combo)
            
            # 3: CATEGORY
            it_cat = QTableWidgetItem(p['category'] or "")
            it_cat.setFlags(it_cat.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(r, 3, it_cat)
            
            # 4: SYSTEM QTY
            it_sys = QTableWidgetItem(f"{p['stock']:.2f}")
            it_sys.setFlags(it_sys.flags() & ~Qt.ItemIsEditable)
            it_sys.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(r, 4, it_sys)
            
            # 5: PHYSICAL QTY
            phys_edit = QLineEdit("")
            phys_edit.setPlaceholderText("")
            phys_edit.setValidator(QDoubleValidator(0.00, 100000.00, 2))
            phys_edit.setAlignment(Qt.AlignCenter)
            phys_edit.setStyleSheet("""
                QLineEdit {
                    border: none !important;
                    background-color: transparent !important; 
                    background: transparent !important; 
                    font-size: 13px; font-weight: bold;
                    color: #1a5fb4; margin: 0;
                }
            """)
            phys_edit.setProperty("row", r)
            phys_edit.setProperty("sys_val", float(p['stock'] or 0.0))
            
            c_price = float(p.get('cost_price', 0) or 0.0)
            if c_price == 0.0:
                c_price = float(p.get('price', 0) or 0.0)
            phys_edit.setProperty("cost_price", c_price)
            
            phys_edit.textChanged.connect(lambda t, row=r: self._on_phys_changed(row, t))
            self.table.setCellWidget(r, 5, phys_edit)
            
            # 6: VARIANCE QTY
            var_item = QTableWidgetItem("")
            var_item.setFlags(var_item.flags() & ~Qt.ItemIsEditable)
            var_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(r, 6, var_item)
            
            # 7: VAR. VALUE
            var_val_item = QTableWidgetItem("")
            var_val_item.setFlags(var_val_item.flags() & ~Qt.ItemIsEditable)
            var_val_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(r, 7, var_val_item)
            
            self.table.setRowHeight(r, 45)
            
        self.table.setColumnHidden(2, not any_batches)
        self.table.blockSignals(False)

    def _filter_table(self, text):
        query = text.lower()
        for r in range(self.table.rowCount()):
            code = self.table.item(r, 0).text().lower()
            name = self.table.item(r, 1).text().lower()
            self.table.setRowHidden(r, query not in code and query not in name)

    def _on_phys_changed(self, r, text):
        phys_edit = self.table.cellWidget(r, 5)
        var_item = self.table.item(r, 6)
        var_val_item = self.table.item(r, 7)
        if not phys_edit or not var_item or not var_val_item: return
        
        try:
            sys_val = float(phys_edit.property("sys_val") or 0.0)
            cost_price = float(phys_edit.property("cost_price") or 0.0)
            phys_val = float(text)
            diff = phys_val - sys_val
            var_val = diff * cost_price
            if abs(var_val) < 0.001:
                var_val = 0.0
            
            comp = get_defaults()
            currency = comp.get('currency', '$')
            
            var_item.setText(f"{diff:+.2f}" if diff != 0 else "0.00")
            var_val_item.setText(f"{currency}{var_val:+.2f}" if var_val != 0 else f"{currency}0.00")
            
            for it, val in [(var_item, diff), (var_val_item, var_val)]:
                if val > 0:
                    it.setForeground(QColor(0, 150, 0)) # Green
                elif val < 0:
                    it.setForeground(QColor(200, 0, 0)) # Red
                else:
                    it.setForeground(QColor(0, 0, 0)) # Black
        except ValueError:
            var_item.setText("")
            var_val_item.setText("")
        self._update_totals()

    def _on_batch_changed(self, idx):
        combo = self.sender()
        if not combo: return
        r = combo.property("row")
        data = combo.currentData()
        if not data: return
        
        new_sys_qty = data["qty"]
        sys_item = self.table.item(r, 4)
        if sys_item:
            sys_item.setText(f"{new_sys_qty:.2f}")
            
        phys_edit = self.table.cellWidget(r, 5)
        if phys_edit:
            phys_edit.setProperty("sys_val", new_sys_qty)

    def _update_totals(self):
        total_var = 0.0
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 7)
            if item:
                import re
                val_str = re.sub(r'[^\d\.\-\+]', '', item.text())
                try:
                    total_var += float(val_str)
                except ValueError:
                    pass
                    
        comp = get_defaults()
        currency = comp.get('currency', '$')
        if total_var > 0:
            color = "#009600"
            sign = "+"
        elif total_var < 0:
            color = "#c80000"
            sign = ""
        else:
            color = NAVY
            sign = ""
            
        self.lbl_totals.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {color}; padding: 5px;")
        self.lbl_totals.setText(f"Total Variance: {currency}{sign}{total_var:.2f}")

    def _on_submit(self):
        confirm = QMessageBox.question(self, "Confirm Changes", 
                                     "Are you sure you want to apply these inventory adjustments?",
                                     QMessageBox.Yes | QMessageBox.No)
        if confirm != QMessageBox.Yes:
            return

        remarks = self.remarks_edit.text().strip()
        if not remarks:
            remarks = "Stock Take"

        try:
            from models.product import update_product
            from database.db import get_connection
            conn = get_connection(); cur = conn.cursor()
            
            # Fetch created_by
            created_by = getattr(self.window(), 'user', {}).get('name', 'Admin') if hasattr(self.window(), 'user') else 'Admin'
            
            # Check if there are any changes first
            has_changes = False
            for r in range(self.table.rowCount()):
                phys_edit = self.table.cellWidget(r, 5)
                if phys_edit and phys_edit.text().strip():
                    has_changes = True
                    break
                    
            if not has_changes:
                conn.close()
                # show_toast(self.parent() or self, "No changes to apply.", kind="info")
                return
            
            # Create ONE Stock Entry for the entire take
            import time
            doc_no = f"TAKE-{int(time.time())}"
            
            warehouse_id = 1
            cur.execute("SELECT TOP 1 id FROM warehouses ORDER BY is_default DESC, id ASC")
            wh_row = cur.fetchone()
            if wh_row: warehouse_id = wh_row[0]
                
            cur.execute("""
                INSERT INTO stock_entries (date, doc_no, synced, warehouse_id, reference, created_by)
                OUTPUT INSERTED.id
                VALUES (SYSDATETIME(), ?, 0, ?, ?, ?)
            """, (doc_no, warehouse_id, remarks, created_by))
            se_id = int(cur.fetchone()[0])

            count = 0
            for r in range(self.table.rowCount()):
                phys_edit = self.table.cellWidget(r, 5)
                if not phys_edit or not phys_edit.text().strip():
                    continue
                    
                try:
                    new_stock = float(phys_edit.text())
                    sys_qty = float(phys_edit.property("sys_val"))
                    diff = new_stock - sys_qty
                except ValueError:
                    diff = 0.0
                    
                product_id = self.table.item(r, 1).data(Qt.UserRole)
                
                if diff != 0:
                    cur.execute("UPDATE products SET stock = ISNULL(stock, 0) + ? WHERE id = ?", (diff, product_id))
                    
                    batch_w = self.table.cellWidget(r, 2)
                    batch_no = None
                    if isinstance(batch_w, QComboBox):
                        data = batch_w.currentData()
                        if data and data.get("bn") and data.get("bn") != "None":
                            batch_no = data["bn"]
                    
                    if batch_no:
                        cur.execute("SELECT id FROM product_batches WHERE product_id = ? AND batch_no = ?", (product_id, batch_no))
                        if cur.fetchone():
                            cur.execute("UPDATE product_batches SET qty = ISNULL(qty, 0) + ? WHERE product_id = ? AND batch_no = ?", 
                                        (diff, product_id, batch_no))
                        else:
                            cur.execute("INSERT INTO product_batches (product_id, batch_no, qty) VALUES (?, ?, ?)", 
                                        (product_id, batch_no, new_stock))
                
                # Always insert into stock_entry_items to record that the count took place
                cur.execute("SELECT cost_price, price FROM products WHERE id = ?", (product_id,))
                p_row = cur.fetchone()
                c_price = float(p_row[0]) if p_row else 0.0
                s_price = float(p_row[1]) if p_row else 0.0
                
                cur.execute("""
                    INSERT INTO stock_entry_items (parent_id, product_id, qty, cost_price, selling_price, system_qty, physical_qty)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (se_id, product_id, diff, c_price, s_price, sys_qty, new_stock))

                count += 1
            
            conn.commit(); conn.close()
            
            if count > 0:
                # show_toast(self.parent() or self, f"Inventory updated for {count} items.", kind="success")
                self.remarks_edit.clear()
            else:
                pass # show_toast(self.parent() or self, "No changes to apply.", kind="info")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update inventory: {e}")

    def _print_count_sheet(self, blind=True):
        from PySide6.QtWidgets import QMessageBox
        from PySide6.QtCore import QStandardPaths
        from PySide6.QtPrintSupport import QPrinter
        from PySide6.QtGui import QTextDocument, QPageSize, QPageLayout
        from models.company_defaults import get_defaults
        from views.dialogs.pdf_preview_dialog import PdfPreviewDialog
        import os
        
        if self.table.rowCount() == 0:
            QMessageBox.information(self, "Empty", "No data to print. Please fetch items first.")
            return

        try:
            comp = get_defaults()
            c_name = comp.get('company_name', 'Havano POS')
            c_addr = f"{comp.get('address_1', '')} {comp.get('address_2', '')}"
        except:
            c_name, c_addr = "Havano POS", ""
            
        import datetime
        dt_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        c_header = f"<div style='font-size: 24px; font-weight: bold; color: #1a5fb4; margin:0;'>{c_name}</div>" if c_name.strip() else ""
        a_header = f"<div style='color: #666; margin:0; margin-bottom:10px;'>{c_addr}</div>" if c_addr.strip() else ""
        title = "Stock Count Sheet (Blind)" if blind else "Stock Count Sheet (Standard)"

        html = f"""<html><body style="font-family: 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; margin: 0; padding: 0;">
    <div style="text-align:center; margin-bottom: 10px;">{c_header}{a_header}<div style="font-size: 18px; font-weight: bold; color: #1a5fb4; margin-top: 5px; margin-bottom: 5px;">{title}</div><div style="color: #666; font-size:12px; margin: 0;">Date: {dt_str}</div></div>
    <table width="100%" cellpadding="8" cellspacing="0" style="border-collapse: collapse; font-size: 12px; border: 1px solid #ddd;">
                <thead>
                    <tr style="background-color: #1a5fb4; color: white; text-align: left;">
                        <th style="border: 1px solid #ddd; width: 15%;">CODE</th>
                        <th style="border: 1px solid #ddd; width: 40%;">ITEM NAME</th>
                        <th style="border: 1px solid #ddd; width: 15%;">CATEGORY</th>
        """
        if not blind:
            html += '<th style="border: 1px solid #ddd; width: 15%; text-align: right;">SYS QTY</th>'
        
        html += """
                        <th style="border: 1px solid #ddd; width: 15%; text-align: center;">COUNTED QTY</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for r in range(self.table.rowCount()):
            if self.table.isRowHidden(r): continue
            
            code = self.table.item(r, 0).text() if self.table.item(r, 0) else ""
            name = self.table.item(r, 1).text() if self.table.item(r, 1) else ""
            cat = self.table.item(r, 3).text() if self.table.item(r, 3) else ""
            sys = self.table.item(r, 4).text() if self.table.item(r, 4) else ""
            
            bg = "#fdfbf7" if r % 2 == 0 else "#ffffff"
            html += f"<tr style='background-color: {bg};'>"
            html += f"<td style='border: 1px solid #ddd; color:#333;'>{code}</td>"
            html += f"<td style='border: 1px solid #ddd; color:#333;'>{name}</td>"
            html += f"<td style='border: 1px solid #ddd; color:#333;'>{cat}</td>"
            
            if not blind:
                html += f"<td style='border: 1px solid #ddd; color:#333; text-align:right;'>{sys}</td>"
                
            html += "<td style='border: 1px solid #ddd; color:#333;'></td>"
            html += "</tr>"
            
        html += """
                </tbody>
            </table>
            <div style="margin-top:20px; font-size:12px; color:#333;">
                <p>Counted by: ________________________   Date: ________________________</p>
                <p>Checked by: ________________________   Date: ________________________</p>
            </div>
            <div style="margin-top:40px; font-size:10px; color:#888; text-align:center;">
                Generated by Havano ERP Inventory Module
            </div>
        </body>
        </html>
        """
        
        docs = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        export_path = os.path.join(docs, f"Stock_Count_Sheet_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.pdf")

        printer = QPrinter()
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(export_path)
        printer.setFullPage(True)
        printer.setPageSize(QPageSize(QPageSize.A4))
        printer.setPageOrientation(QPageLayout.Portrait)
        from PySide6.QtCore import QMarginsF
        printer.setPageMargins(QMarginsF(10, 10, 10, 10), QPageLayout.Millimeter)

        doc = QTextDocument()
        doc.setDocumentMargin(0)
        doc.setHtml(html.replace('\n', '').replace('\r', ''))
        doc.print_(printer)

        try:
            dlg = PdfPreviewDialog(export_path, title=title, parent=self)
            dlg.exec()
        except Exception as e:
            QMessageBox.information(self, "PDF Saved", f"Count sheet saved successfully to:\n{export_path}\n(Preview error: {e})")
