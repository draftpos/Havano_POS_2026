# views/dialogs/stock_adjust_dialog.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QWidget, QFrame, QGraphicsDropShadowEffect, QMessageBox,
    QAbstractItemView, QComboBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QDoubleValidator
import qtawesome as qta
from utils.toast import show_toast
from database.db import get_connection

# Havano Palette
from theme import *

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

class StockAdjustDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Stock Adjustment")
        self.setWindowFlags(Qt.Window | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)
        self.setWindowState(Qt.WindowMaximized)
        
        self._products = []
        self._build_ui()
        self._load_data()

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
        
        # ── HEADER ────────────────────────────────────────────────────────────
        hdr = QWidget(); hdr.setFixedHeight(80)
        hdr.setStyleSheet(f"""
            QWidget {{
                background: {NAVY};
                border-top-left-radius:15px; border-top-right-radius:15px;
            }}
        """)
        hl = QHBoxLayout(hdr); hl.setContentsMargins(25, 0, 25, 0)
        
        v_title = QVBoxLayout(); v_title.setSpacing(2); v_title.setAlignment(Qt.AlignVCenter)
        title_lbl = QLabel("STOCK ADJUSTMENT")
        title_lbl.setStyleSheet(f"color:{WHITE}; font-size:20px; font-weight:bold; background:transparent;")
        sub_lbl = QLabel("Add or Subtract stock due to Breakage, Wastage, or Adjustment")
        sub_lbl.setStyleSheet(f"color:{MUTED}; font-size:11px; background:transparent;")
        v_title.addWidget(title_lbl); v_title.addWidget(sub_lbl)
        hl.addLayout(v_title)
        
        hl.addStretch()
        
        self.save_btn = _top_btn("Submit Adjustments", "fa5s.check-circle", SUCCESS, SUCCESS_H)
        self.save_btn.setFixedSize(180, 42)
        self.save_btn.clicked.connect(self._on_submit)
        
        hl.addWidget(self.save_btn)
        cl.addWidget(hdr)
        
        # ── BODY ──────────────────────────────────────────────────────────────
        body = QWidget()
        bl = QVBoxLayout(body); bl.setContentsMargins(25, 20, 25, 20); bl.setSpacing(15)
        
        # Search & Filters
        filter_lay = QHBoxLayout(); filter_lay.setSpacing(15)
        
        search_ico = QLabel()
        search_ico.setPixmap(qta.icon("fa5s.search", color=MUTED).pixmap(16, 16))
        filter_lay.addWidget(search_ico)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter items by name or part number...")
        self.search_input.setFixedHeight(40)
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                border:1px solid {BORDER}; border-radius:10px; padding:0 12px;
                background: {OFF_WHITE}; font-size:14px;
            }}
            QLineEdit:focus {{ border:2px solid {ACCENT}; background:white; }}
        """)
        self.search_input.textChanged.connect(self._filter_table)
        filter_lay.addWidget(self.search_input, 1)
        
        filter_lay.addStretch(1)
        bl.addLayout(filter_lay)

        # Table
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["ITEM", "CURRENT STOCK", "TYPE", "QTY", "REASON", "NEW STOCK"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.setColumnWidth(0, 300)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background:{WHITE}; border:1px solid {BORDER}; 
                border-radius:10px; gridline-color:{OFF_WHITE}; outline:none;
                selection-background-color: {ACCENT};
                selection-color: {WHITE};
            }}
            QHeaderView::section {{
                background:{OFF_WHITE}; color:{NAVY}; font-weight:bold; font-size:11px;
                border:none; border-bottom:2px solid {BORDER}; padding:12px;
            }}
            QTableWidget::item {{ padding:4px 12px; border-bottom:1px solid {OFF_WHITE}; }}
        """)
        bl.addWidget(self.table)
        
        cl.addWidget(body)

    def _load_data(self):
        try:
            from models.product import get_all_products
            self._products = get_all_products()
            self._render_table(self._products)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load products: {e}")

    def _render_table(self, products):
        self.table.blockSignals(True)
        self.table.setRowCount(len(products))
        for r, p in enumerate(products):
            it_name = QTableWidgetItem(f"{p['part_no']} - {p['name']}")
            it_name.setFlags(it_name.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(r, 0, it_name)
            
            it_sys = QTableWidgetItem(f"{p['stock']:.2f}")
            it_sys.setFlags(it_sys.flags() & ~Qt.ItemIsEditable)
            it_sys.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(r, 1, it_sys)
            
            # Adjustment Type (blank default)
            cb_type = QComboBox()
            cb_type.addItem("")
            cb_type.addItems(["Add Stock", "Subtract Stock"])
            cb_type.setCurrentIndex(0)
            cb_type.setStyleSheet(f"QComboBox {{ border: 1px solid {BORDER}; border-radius: 4px; padding: 4px; background: {WHITE}; }}")
            self.table.setCellWidget(r, 2, cb_type)
            
            # Qty Input (disabled until type selected)
            phys_edit = QLineEdit()
            phys_edit.setValidator(QDoubleValidator(0, 999999, 2))
            phys_edit.setPlaceholderText("0.00")
            phys_edit.setEnabled(False)
            phys_edit.setStyleSheet(f"QLineEdit {{ border: 1px solid {BORDER}; border-radius: 4px; padding: 4px; }}")
            phys_edit.setProperty("sys_val", p['stock'])
            self.table.setCellWidget(r, 3, phys_edit)
            
            # Reason ComboBox
            cb_reason = QComboBox()
            cb_reason.addItems(["Adjustment", "Breakage", "Wastage", "Theft", "Expired"])
            cb_reason.setStyleSheet(f"QComboBox {{ border: 1px solid {BORDER}; border-radius: 4px; padding: 4px; background: {WHITE}; }}")
            self.table.setCellWidget(r, 4, cb_reason)
            
            # New Stock (Preview)
            it_diff = QTableWidgetItem(f"{p['stock']:.2f}")
            it_diff.setFlags(it_diff.flags() & ~Qt.ItemIsEditable)
            it_diff.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(r, 5, it_diff)
            
            it_name.setData(Qt.UserRole, p['id'])
            
    
            cb_type.currentIndexChanged.connect(lambda _, row=r: self._recalc_row(row))
            phys_edit.textChanged.connect(lambda _, row=r: self._recalc_row(row))
            
            self.table.setRowHeight(r, 45)
            
        self.table.blockSignals(False)

    def _recalc_row(self, row):
        sys_val = self.table.cellWidget(row, 3).property("sys_val")
        qty_text = self.table.cellWidget(row, 3).text()
        type_str = self.table.cellWidget(row, 2).currentText()
        diff_item = self.table.item(row, 5)
        phys_edit = self.table.cellWidget(row, 3)

        # If no action selected, keep qty disabled and show original stock
        if not type_str:
            phys_edit.setEnabled(False)
            diff_item.setText(f"{sys_val:.2f}")
            diff_item.setForeground(QColor(MUTED))
            return
        else:
            phys_edit.setEnabled(True)

        qty = 0.0
        try:
            qty = float(qty_text) if qty_text.strip() else 0.0
        except ValueError:
            pass

        if "Subtract" in type_str:
            new_stock = sys_val - qty
            diff_item.setForeground(QColor(DANGER) if qty > 0 else QColor(MUTED))
        else:
            new_stock = sys_val + qty
            diff_item.setForeground(QColor(SUCCESS) if qty > 0 else QColor(MUTED))
            
        diff_item.setText(f"{new_stock:.2f}")

    def _filter_table(self, text):
        query = text.lower()
        for r in range(self.table.rowCount()):
            item_text = self.table.item(r, 0).text().lower()
            self.table.setRowHidden(r, query not in item_text)

    def _on_submit(self):
        confirm = QMessageBox.question(self, "Confirm Adjustments", 
                                     "Are you sure you want to apply these stock adjustments?",
                                     QMessageBox.Yes | QMessageBox.No)
        if confirm != QMessageBox.Yes:
            return

        try:
            from models.product import update_product
            count = 0
            
            conn = get_connection()
            cur = conn.cursor()
            
            for r in range(self.table.rowCount()):
                qty_text = self.table.cellWidget(r, 3).text()
                try:
                    qty = float(qty_text)
                except ValueError:
                    qty = 0.0
                    
                if qty > 0:
                    product_id = self.table.item(r, 0).data(Qt.UserRole)
                    type_str = self.table.cellWidget(r, 2).currentText()
                    reason = self.table.cellWidget(r, 4).currentText()
                    
                    sys_val = self.table.cellWidget(r, 3).property("sys_val")
                    
                    adj_qty = -qty if "Subtract" in type_str else qty
                    new_stock = sys_val + adj_qty
                    
                    # 1. Update product stock
                    update_product(product_id, stock=new_stock)
                    
                    # 2. Add Stock Entry for history
                    import time
                    doc_no = f"ADJ-{int(time.time())}-{product_id}-{r}"
                    
                    warehouse_id = 1
                    cur.execute("SELECT TOP 1 id FROM warehouses ORDER BY is_default DESC, id ASC")
                    wh_row = cur.fetchone()
                    if wh_row: warehouse_id = wh_row[0]
                        
                    user_name = getattr(self.window(), 'user', {}).get('name', 'Admin') if hasattr(self.window(), 'user') else 'Admin'
                    cur.execute("""
                        INSERT INTO stock_entries (date, doc_no, synced, warehouse_id, reference, created_by)
                        OUTPUT INSERTED.id
                        VALUES (SYSDATETIME(), ?, 0, ?, ?, ?)
                    """, (doc_no, warehouse_id, reason, user_name))
                    se_id = int(cur.fetchone()[0])
                    
                    # We just log the adjustment qty as the 'qty' in stock_entry_items
                    cur.execute("SELECT cost_price, price FROM products WHERE id = ?", (product_id,))
                    p_row = cur.fetchone()
                    c_price = float(p_row[0]) if p_row else 0.0
                    s_price = float(p_row[1]) if p_row else 0.0
                    
                    cur.execute("""
                        INSERT INTO stock_entry_items (parent_id, product_id, qty, cost_price, selling_price)
                        VALUES (?, ?, ?, ?, ?)
                    """, (se_id, product_id, adj_qty, c_price, s_price))
                    
                    count += 1
            
            conn.commit()
            conn.close()
            
            if count > 0:
                pass # show_toast(self.parent() or self, f"Inventory updated for {count} items.", kind="success")
            else:
                pass # show_toast(self.parent() or self, "No adjustments entered.", kind="info")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update inventory: {e}")
