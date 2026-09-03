import time
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QTableWidgetItem, QHeaderView, QMessageBox
)
from PySide6.QtCore import Qt
from views.reports.report_template import ReportTemplate
from database.db import get_connection, fetchall_dicts
import qtawesome as qta
from theme import WHITE, SUCCESS, SUCCESS_H

class DisabledItemsReport(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {WHITE};")
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)

        self.report = ReportTemplate("Disabled Items Report", is_report=False, show_date_filter=True, parent=self)
        self.report.set_headers(["Part No.", "Product Name", "Category", "Qty on Hand", "Action"])
        
        # Hide default report buttons not needed
        self.report.btn_add.hide()
        
        self._tbl = self.report.table
        hh = self._tbl.horizontalHeader()
        hh.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        hh.setSectionResizeMode(0, QHeaderView.Interactive)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Interactive)
        hh.setSectionResizeMode(3, QHeaderView.Interactive)
        hh.setSectionResizeMode(4, QHeaderView.Fixed)
        
        self._tbl.setColumnWidth(0, 150)
        self._tbl.setColumnWidth(2, 120)
        self._tbl.setColumnWidth(3, 100)
        self._tbl.setColumnWidth(4, 100)
        
        self.report.global_search.textChanged.connect(self._on_search)
        
        main_lay.addWidget(self.report, 1)

    def _load_data(self):
        self._tbl.setRowCount(0)
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT id, part_no, name, category, stock 
                FROM products 
                WHERE ISNULL(active, 1) = 0
                ORDER BY name
            """)
            rows = fetchall_dicts(cur)
            conn.close()

            self._tbl.setRowCount(len(rows))
            for r, row in enumerate(rows):
                def _item(val, align=Qt.AlignLeft | Qt.AlignVCenter):
                    it = QTableWidgetItem(str(val) if val is not None else "")
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                    it.setTextAlignment(align)
                    return it

                self._tbl.setItem(r, 0, _item(row['part_no']))
                self._tbl.setItem(r, 1, _item(row['name']))
                self._tbl.setItem(r, 2, _item(row['category']))
                qty = float(row.get('stock') or 0.0)
                self._tbl.setItem(r, 3, _item(f"{qty:.2f}", Qt.AlignCenter))
                
                btn_enable = QPushButton(" Enable")
                btn_enable.setIcon(qta.icon("fa5s.check", color="white"))
                btn_enable.setStyleSheet(f"""
                    QPushButton {{
                        background: {SUCCESS}; color: white; border-radius: 4px; font-weight: bold; padding: 4px;
                    }}
                    QPushButton:hover {{ background: {SUCCESS_H}; }}
                """)
                btn_enable.setCursor(Qt.PointingHandCursor)
                btn_enable.clicked.connect(lambda checked=False, pid=row['id']: self._enable_product(pid))
                
                self._tbl.setCellWidget(r, 4, btn_enable)
                self._tbl.setRowHeight(r, 35)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load disabled items:\n{e}")

    def _enable_product(self, product_id):
        reply = QMessageBox.question(self, "Enable Product", "Are you sure you want to enable this product?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("UPDATE products SET active = 1 WHERE id = ?", (product_id,))
                conn.commit()
                conn.close()
                self._load_data()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to enable product:\n{e}")

    def _on_search(self, text):
        query = text.lower()
        for r in range(self._tbl.rowCount()):
            match = False
            for c in range(4): # Search in data columns only
                item = self._tbl.item(r, c)
                if item and query in item.text().lower():
                    match = True
                    break
            self._tbl.setRowHidden(r, not match)
