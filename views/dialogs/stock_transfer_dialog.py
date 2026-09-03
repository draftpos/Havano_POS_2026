# =============================================================================
# views/dialogs/stock_transfer_dialog.py
# =============================================================================

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, 
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QLineEdit, QComboBox, QMessageBox, QFrame, QCompleter
)
from PySide6.QtCore import Qt, QEvent, QTimer
from PySide6.QtGui import QColor, QDoubleValidator
import qtawesome as qta

from models.product import get_all_products, search_products
from models.warehouse import get_all_warehouses
from models.company_defaults import get_defaults
from utils.toast import show_toast

# Havano Palette
from theme import *

class StockTransferDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Stock Transfer")
        self.setWindowFlags(Qt.Window | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)
        self.setWindowState(Qt.WindowMaximized)
        self.setStyleSheet(f"QDialog {{ background-color: {WHITE}; }}")
        
        self.defaults = get_defaults()
        self.local_warehouse = self.defaults.get("server_warehouse", "")
        
        self._items = [] # list of dicts: {part_no, name, qty, uom, id}
        self._build_ui()
        

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── HEADER ───────────────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setFixedHeight(64)
        hdr.setStyleSheet(f"background-color: {NAVY};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(24, 0, 24, 0)
        
        v_title = QVBoxLayout(); v_title.setSpacing(2); v_title.setAlignment(Qt.AlignVCenter)
        title = QLabel("STOCK TRANSFER")
        title.setStyleSheet(f"color: {WHITE}; font-size: 18px; font-weight: bold;")
        sub = QLabel("Move inventory between warehouses")
        sub.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
        v_title.addWidget(title); v_title.addWidget(sub)
        hl.addLayout(v_title)
        
        hl.addStretch()
        
        self.save_btn = QPushButton("  Process Transfer")
        self.save_btn.setIcon(qta.icon("fa5s.exchange-alt", color=WHITE))
        self.save_btn.setFixedHeight(38)
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {SUCCESS}; color: {WHITE}; border-radius: 6px;
                font-weight: bold; padding: 0 20px; font-size: 12px;
            }}
            QPushButton:hover {{ background-color: {SUCCESS_H}; }}
        """)
        self.save_btn.clicked.connect(self._on_save)
        hl.addWidget(self.save_btn)
        # Close button removed - use the native title bar ✕ to close
        layout.addWidget(hdr)

        # ── WAREHOUSE SELECTION ──────────────────────────────────────────────
        wh_row = QWidget()
        wh_row.setStyleSheet(f"background-color: {OFF_WHITE}; border-bottom: 1px solid {BORDER};")
        wh_lay = QHBoxLayout(wh_row)
        wh_lay.setContentsMargins(24, 15, 24, 15)
        wh_lay.setSpacing(20)

        # From
        v1 = QVBoxLayout(); v1.setSpacing(5)
        v1.addWidget(QLabel("SOURCE WAREHOUSE", styleSheet=f"color:{MUTED}; font-size:10px; font-weight:bold;"))
        self.cb_from = QComboBox()
        self.cb_from.setFixedHeight(36)
        self._style_combo(self.cb_from)
        v1.addWidget(self.cb_from)
        wh_lay.addLayout(v1, 1)

        # Arrow
        arrow = QLabel()
        arrow.setPixmap(qta.icon("fa5s.long-arrow-alt-right", color=NAVY_3).pixmap(24, 24))
        wh_lay.addWidget(arrow, 0, Qt.AlignBottom)

        # To
        v2 = QVBoxLayout(); v2.setSpacing(5)
        v2.addWidget(QLabel("TARGET WAREHOUSE", styleSheet=f"color:{MUTED}; font-size:10px; font-weight:bold;"))
        self.cb_to = QComboBox()
        self.cb_to.setFixedHeight(36)
        self._style_combo(self.cb_to)
        v2.addWidget(self.cb_to)
        wh_lay.addLayout(v2, 1)
        
        layout.addWidget(wh_row)

        # ── ITEM ENTRY ───────────────────────────────────────────────────────
        entry_row = QWidget()
        entry_row.setStyleSheet(f"background-color: {WHITE}; border-bottom: 1px solid {BORDER};")
        el = QHBoxLayout(entry_row)
        el.setContentsMargins(24, 12, 24, 12)
        
        self.btn_fetch = QPushButton(" Fetch Source Stock")
        self.btn_fetch.setIcon(qta.icon("fa5s.sync", color="white", scale_factor=0.7))
        self.btn_fetch.setFixedHeight(40)
        self.btn_fetch.setCursor(Qt.PointingHandCursor)
        self.btn_fetch.setStyleSheet(f"""
            QPushButton {{ background-color: {ACCENT}; color: white; border: none; border-radius: 6px; padding: 0 15px; font-weight: bold; font-size: 13px; }}
            QPushButton:hover {{ background-color: {ACCENT_H}; }}
        """)
        self.btn_fetch.clicked.connect(self._fetch_items)
        el.addWidget(self.btn_fetch)

        self.item_search = QLineEdit()
        self.item_search.setPlaceholderText("Search in table...")
        self.item_search.setFixedHeight(40)
        self.item_search.setStyleSheet(f"""
            QLineEdit {{
                border: 2px solid {BORDER}; border-radius: 8px;
                padding: 0 15px; font-size: 14px; background: {WHITE};
            }}
            QLineEdit:focus {{ border-color: {ACCENT}; }}
        """)
        self.item_search.textChanged.connect(self._filter_table)
        el.addWidget(self.item_search, 1)
        
        layout.addWidget(entry_row)

        # ── TABLE ────────────────────────────────────────────────────────────
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Part No.", "Product Name", "UOM", "Available Qty", "Transfer Qty"])
        self.table.setStyleSheet(f"""
            QTableWidget {{ border: none; gridline-color: {BORDER}; background: {WHITE}; }}
            QHeaderView::section {{
                background-color: {OFF_WHITE}; color: {NAVY};
                font-weight: bold; padding: 10px; border: none; border-bottom: 1px solid {BORDER};
            }}
            QScrollBar:vertical {{ border: none; background: {OFF_WHITE}; width: 16px; border-radius: 8px; }}
            QScrollBar::handle:vertical {{ background: #b0bec5; min-height: 30px; border-radius: 6px; margin: 2px; }}
            QScrollBar::handle:vertical:hover {{ background: #90a4ae; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
            QScrollBar:horizontal {{ border: none; background: {OFF_WHITE}; height: 16px; border-radius: 8px; }}
            QScrollBar::handle:horizontal {{ background: #b0bec5; min-width: 30px; border-radius: 6px; margin: 2px; }}
            QScrollBar::handle:horizontal:hover {{ background: #90a4ae; }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}
        """)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.table)

        # ── FOOTER ───────────────────────────────────────────────────────────
        footer = QWidget()
        footer.setFixedHeight(50)
        footer.setStyleSheet(f"background-color: {OFF_WHITE}; border-top: 1px solid {BORDER};")
        fl = QHBoxLayout(footer)
        self.lbl_status = QLabel("Ready")
        self.lbl_status.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        fl.addWidget(self.lbl_status)
        fl.addStretch()
        layout.addWidget(footer)

        # Load Warehouses
        whs = get_all_warehouses()
        for w in whs:
            self.cb_from.addItem(w['name'], w['id'])
            self.cb_to.addItem(w['name'], w['id'])
        
        # Try to set local warehouse as default Source
        idx = self.cb_from.findText(self.local_warehouse)
        if idx >= 0: self.cb_from.setCurrentIndex(idx)

    def _style_combo(self, cb):
        cb.setStyleSheet(f"""
            QComboBox {{
                background-color: {WHITE}; border: 1px solid {BORDER};
                border-radius: 6px; padding: 0 12px; font-size: 13px; color: {DARK_TEXT};
            }}
            QComboBox::drop-down {{ border: none; width: 30px; }}
            QComboBox::down-arrow {{ image: none; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 5px solid {MUTED}; }}
            QComboBox QAbstractItemView {{ background: {WHITE}; selection-background-color: {ACCENT}; selection-color: {WHITE}; outline: 0; }}
        """)

    def _fetch_items(self):
        from database.db import get_connection, fetchall_dicts
        conn = get_connection(); cur = conn.cursor()
        from_wh = self.cb_from.currentData()
        # Fetch all items that have stock in the source warehouse
        cur.execute("""
            SELECT p.id, p.part_no, p.name, p.uom, IFNULL(w.quantity, 0) as available
            FROM products p
            LEFT JOIN warehouse_stock w ON w.product_id = p.id AND w.warehouse_id = ?
            WHERE p.status = 1 AND p.type != 'Service'
            ORDER BY p.name ASC
        """, (from_wh,))
        items = fetchall_dicts(cur)
        conn.close()

        self.table.setRowCount(0)
        for p in items:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            self.table.setItem(row, 0, QTableWidgetItem(str(p['part_no'] or "")))
            self.table.setItem(row, 1, QTableWidgetItem(str(p['name'] or "")))
            self.table.setItem(row, 2, QTableWidgetItem(str(p.get('uom') or 'Unit')))
            
            avail_item = QTableWidgetItem(str(p['available']))
            avail_item.setFlags(avail_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 3, avail_item)
            
            qty_edit = QLineEdit("0")
            qty_edit.setValidator(QDoubleValidator(0, 100000, 4))
            qty_edit.setAlignment(Qt.AlignCenter)
            qty_edit.setStyleSheet("border: 1px solid #c8d8ec; background: white; font-size: 13px; font-weight: bold; border-radius: 4px;")
            self.table.setCellWidget(row, 4, qty_edit)

    def _filter_table(self, text):
        query = text.lower()
        for r in range(self.table.rowCount()):
            code = self.table.item(r, 0).text().lower() if self.table.item(r, 0) else ""
            name = self.table.item(r, 1).text().lower() if self.table.item(r, 1) else ""
            self.table.setRowHidden(r, query not in code and query not in name)
    def _on_save(self):
        if self.cb_from.currentData() == self.cb_to.currentData():
            QMessageBox.warning(self, "Invalid Transfer", "Source and Target warehouses cannot be the same.")
            return
            
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "Empty Transfer", "Please fetch items and add at least one item to transfer.")
            return

        from_wh = self.cb_from.currentText()
        to_wh = self.cb_to.currentText()
        
        msg = f"Process stock transfer from {from_wh} to {to_wh}?"
        if QMessageBox.question(self, "Confirm Transfer", msg) == QMessageBox.Yes:
            self._process_transfer()

    def _process_transfer(self):
        from_id = self.cb_from.currentData()
        to_id = self.cb_to.currentData()
        
        try:
            from database.db import get_connection
            conn = get_connection(); cur = conn.cursor()
            from models.product import adjust_stock, get_product_by_part_no
            
            transfers = 0
            for i in range(self.table.rowCount()):
                part_no = self.table.item(i, 0).text()
                qty_text = self.table.cellWidget(i, 4).text()
                try:
                    qty = float(qty_text or 0)
                except ValueError:
                    qty = 0
                
                if qty <= 0: continue
                
                prod = get_product_by_part_no(part_no)
                if not prod: continue
                product_id = prod['id']
                
                # 1. Deduct from Source
                adjust_stock(product_id, -qty, warehouse_id=from_id)
                # 2. Add to Target
                adjust_stock(product_id, qty, warehouse_id=to_id)
                transfers += 1
            
            conn.commit(); conn.close()
            
            if transfers == 0:
                QMessageBox.information(self, "No Transfers", "No quantities were entered to transfer.")
                return
                
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to process transfer:\n{e}")
