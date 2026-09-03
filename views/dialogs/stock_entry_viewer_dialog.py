import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QAbstractItemView, QWidget
)
from PySide6.QtCore import Qt
import qtawesome as qta
from database.db import get_connection, fetchall_dicts
from theme import *

class StockEntryViewerDialog(QDialog):
    def __init__(self, parent=None, entry_id=None, title="Stock Entry Details"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(700)
        self.setMinimumHeight(500)
        self.setStyleSheet(f"background-color: {WHITE};")
        self.entry_id = entry_id
        
        self._build_ui(title)
        self._load_data()

    def _build_ui(self, title):
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(20, 20, 20, 20)
        main_lay.setSpacing(15)

        # Header
        hdr = QHBoxLayout()
        v_title = QVBoxLayout()
        v_title.setSpacing(2)
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(f"color:{NAVY}; font-size:18px; font-weight:bold;")
        self.lbl_subtitle = QLabel(f"Document ID: {self.entry_id}")
        self.lbl_subtitle.setStyleSheet(f"color:{MUTED}; font-size:12px;")
        
        v_title.addWidget(lbl_title)
        v_title.addWidget(self.lbl_subtitle)
        hdr.addLayout(v_title)
        hdr.addStretch()

        btn_close = QPushButton(" Close")
        btn_close.setIcon(qta.icon("fa5s.times", color="white"))
        btn_close.setStyleSheet(f"background:{NAVY}; color:{WHITE}; padding:8px 15px; border-radius:4px; font-weight:bold;")
        btn_close.clicked.connect(self.accept)
        hdr.addWidget(btn_close)
        
        main_lay.addLayout(hdr)

        # Table
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Part No", "Product Name", "Adjustment", "Current Stock", "Unit Price", "Variance Value"])
        hh = self.table.horizontalHeader()
        hh.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        hh.setSectionResizeMode(QHeaderView.Stretch)
        hh.setStyleSheet(f"background-color: {NAVY}; color: white; font-weight: bold; padding: 5px;")
        
        self.table.setStyleSheet(f"QTableWidget {{ border: 1px solid {BORDER}; border-radius: 4px; background: {WHITE}; }} QTableWidget::item {{ padding: 5px; border-bottom: 1px solid #f1f5f9; }}")
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        main_lay.addWidget(self.table)
        
        self.lbl_totals = QLabel("Total Variance: $0.00")
        self.lbl_totals.setStyleSheet(f"color:{NAVY}; font-size:16px; font-weight:bold; padding: 5px;")
        
        tot_lay = QHBoxLayout()
        tot_lay.addStretch()
        tot_lay.addWidget(self.lbl_totals)
        main_lay.addLayout(tot_lay)

    def _load_data(self):
        if not self.entry_id: return
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("SELECT doc_no, date, reference FROM stock_entries WHERE id = ?", (self.entry_id,))
            entry = cur.fetchone()
            if entry:
                self.lbl_subtitle.setText(f"Doc No: {entry[0]} | Date: {str(entry[1]).split('.')[0]} | Ref: {entry[2] or 'N/A'}")
            
            cur.execute("""
                SELECT p.part_no, p.name, sei.qty, p.stock, sei.cost_price, sei.selling_price 
                FROM stock_entry_items sei
                JOIN products p ON sei.product_id = p.id
                WHERE sei.parent_id = ?
            """, (self.entry_id,))
            items = fetchall_dicts(cur)
            conn.close()

            self.table.setRowCount(0)
            total_variance = 0.0
            for r, item in enumerate(items):
                self.table.insertRow(r)
                
                def _item(val):
                    it = QTableWidgetItem(str(val))
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                    return it

                self.table.setItem(r, 0, _item(item['part_no']))
                self.table.setItem(r, 1, _item(item['name']))
                
                adj = float(item['qty'] or 0)
                adj_str = f"+{adj:.2f}" if adj > 0 else f"{adj:.2f}"
                
                from PySide6.QtGui import QColor
                adj_item = _item(adj_str)
                if adj > 0:
                    adj_item.setForeground(QColor("#1a7a3c")) # Green
                elif adj < 0:
                    adj_item.setForeground(QColor("#b02020")) # Red
                
                self.table.setItem(r, 2, adj_item)
                self.table.setItem(r, 3, _item(f"{float(item['stock'] or 0):.2f}"))
                
                cost = float(item['cost_price'] or 0)
                if cost == 0.0:
                    cost = float(item['selling_price'] or 0)
                
                var_val = adj * cost
                total_variance += var_val
                
                self.table.setItem(r, 4, _item(f"${cost:.2f}"))
                
                var_item = _item(f"${var_val:+.2f}" if var_val != 0 else "$0.00")
                if var_val > 0:
                    var_item.setForeground(QColor("#1a7a3c"))
                elif var_val < 0:
                    var_item.setForeground(QColor("#b02020"))
                self.table.setItem(r, 5, var_item)
                
            if total_variance > 0:
                self.lbl_totals.setStyleSheet(f"color: #1a7a3c; font-size: 16px; font-weight: bold; padding: 5px;")
                self.lbl_totals.setText(f"Total Variance: +${total_variance:.2f}")
            elif total_variance < 0:
                self.lbl_totals.setStyleSheet(f"color: #b02020; font-size: 16px; font-weight: bold; padding: 5px;")
                self.lbl_totals.setText(f"Total Variance: -${abs(total_variance):.2f}")
            else:
                self.lbl_totals.setStyleSheet(f"color: {NAVY}; font-size: 16px; font-weight: bold; padding: 5px;")
                self.lbl_totals.setText(f"Total Variance: $0.00")
                
        except Exception as e:
            print(f"Error loading entry items: {e}")
