from __future__ import annotations
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QWidget, QLineEdit, QComboBox
)

# Havano Palette
from theme import *

def _btn(text, bg, hov):
    b = QPushButton(text)
    b.setFixedHeight(34)
    b.setCursor(Qt.PointingHandCursor)
    b.setStyleSheet(f"""
        QPushButton {{
            background:{bg}; color:{WHITE}; border:none; border-radius:6px;
            font-size:12px; font-weight:bold; padding:0 14px;
        }}
        QPushButton:hover {{ background:{hov}; }}
    """)
    return b

class ProductPriceDialog(QDialog):
    """Manage multiple price list entries for a single product."""
    
    def __init__(self, parent: Optional[QWidget], product: dict):
        super().__init__(parent)
        self.product = product
        self.setWindowTitle(f"Prices: {product['name']}")
        self.resize(700, 500)
        self.setStyleSheet(f"QDialog {{ background:{WHITE}; }}")
        self._build()
        self._reload()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        hdr = QWidget(); hdr.setFixedHeight(80); hdr.setStyleSheet(f"background:{NAVY};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(20, 0, 20, 0)
        
        v = QVBoxLayout(); v.setSpacing(2); v.setAlignment(Qt.AlignVCenter)
        title = QLabel(f"PRICES: {self.product['part_no']}")
        title.setStyleSheet(f"color:{WHITE}; font-size:18px; font-weight:bold;")
        sub = QLabel(self.product['name'])
        sub.setStyleSheet(f"color:{MUTED}; font-size:11px;")
        v.addWidget(title); v.addWidget(sub)
        hl.addLayout(v)
        hl.addStretch()

        self._close_btn = _btn("Close", MUTED, "#6a8aaa")
        self._close_btn.clicked.connect(self.accept)
        hl.addWidget(self._close_btn)
        root.addWidget(hdr)

        # Content
        body = QWidget(); bl = QVBoxLayout(body); bl.setContentsMargins(20, 20, 20, 20)
        
        # Form
        fl = QHBoxLayout(); fl.setSpacing(10)
        self._f_list = QComboBox()
        self._f_list.setPlaceholderText("Wholesale Price")
        self._f_list.setFixedHeight(34)
        
        # Load price lists
        try:
            from models.price_list import get_all_price_lists
            pls = get_all_price_lists()
            self._f_list.addItems([p["name"] for p in pls])
        except: pass

        self._f_uom = QComboBox()
        self._f_uom.addItems(["Unit", "Kg", "Litre", "Meter", "Box", "Pack"])
        self._f_uom.setCurrentText(self.product.get('uom', 'Unit'))
        self._f_uom.setFixedHeight(34)

        self._f_price = QLineEdit()
        self._f_price.setPlaceholderText("Price")
        self._f_price.setFixedHeight(34)

        add_btn = _btn("+ Add Price", SUCCESS, SUCCESS_H)
        add_btn.clicked.connect(self._on_add)

        fl.addWidget(self._f_list, 2)
        fl.addWidget(self._f_uom, 1)
        fl.addWidget(self._f_price, 1)
        fl.addWidget(add_btn)
        bl.addLayout(fl)
        bl.addSpacing(15)

        # Table
        self._tbl = QTableWidget(0, 4)
        self._tbl.setHorizontalHeaderLabels(["Wholesale Price", "UOM", "Price", "Action"])
        self._tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._tbl.verticalHeader().setVisible(False)
        self._tbl.setAlternatingRowColors(True)
        self._tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tbl.setStyleSheet(f"""
            QTableWidget {{ background:{WHITE}; border:1px solid {BORDER}; }}
            QHeaderView::section {{ background:{OFF_WHITE}; font-weight:bold; padding:8px; }}
        """)
        bl.addWidget(self._tbl)
        
        root.addWidget(body)

    def _reload(self):
        self._tbl.setRowCount(0)
        try:
            from models.product import get_item_prices
            rows = get_item_prices(self.product['part_no'])
            for r in rows:
                idx = self._tbl.rowCount()
                self._tbl.insertRow(idx)
                self._tbl.setItem(idx, 0, QTableWidgetItem(r['price_list']))
                self._tbl.setItem(idx, 1, QTableWidgetItem(r['uom']))
                
                p_item = QTableWidgetItem(f"{float(r['price']):.2f}")
                p_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self._tbl.setItem(idx, 2, p_item)

                del_btn = QPushButton("Delete")
                del_btn.setStyleSheet(f"color:{DANGER}; border:none; background:transparent; font-weight:bold;")
                del_btn.setCursor(Qt.PointingHandCursor)
                del_btn.clicked.connect(lambda _, rid=r['id']: self._on_delete(rid))
                self._tbl.setCellWidget(idx, 3, del_btn)
        except Exception as e:
            print(f"Error loading item prices: {e}")

    def _on_add(self):
        plist = self._f_list.currentText().strip()
        uom = self._f_uom.currentText().strip()
        price_txt = self._f_price.text().strip()
        
        if not plist or not price_txt:
            QMessageBox.warning(self, "Required", "Wholesale Price and Price are required.")
            return
        
        try:
            val = float(price_txt)
            from models.product import upsert_item_price
            upsert_item_price(self.product['part_no'], plist, uom, val)
            self._f_price.clear()
            self._reload()
        except ValueError:
            QMessageBox.warning(self, "Invalid Price", "Please enter a valid number.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save price: {e}")

    def _on_delete(self, rid):
        if QMessageBox.question(self, "Confirm", "Delete this price entry?") == QMessageBox.Yes:
            try:
                from models.product import delete_item_price
                delete_item_price(rid)
                self._reload()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete: {e}")
