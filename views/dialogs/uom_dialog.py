import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QMessageBox, QTableWidgetItem, QHeaderView,
    QWidget, QLabel, QLineEdit, QComboBox
)
from PySide6.QtCore import Qt, QTimer
from theme import *
from views.reports.report_template import ReportTemplate

def navy_btn(text, height=36, font_size=12, width=None, color=None, hover=None):
    from PySide6.QtWidgets import QPushButton
    from PySide6.QtCore import Qt
    bg = color or NAVY
    hov = hover or "#2a2f45"
    btn = QPushButton(text)
    btn.setFixedHeight(height)
    if width: btn.setFixedWidth(width)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {bg}; color: white; border: none;
            border-radius: 5px; font-size: {font_size}px; font-weight: bold; padding: 0 14px;
        }}
        QPushButton:hover   {{ background-color: {hov}; }}
    """)
    return btn

class UOMFormPopup(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add UOM")
        self.setFixedSize(400, 250)
        self.setStyleSheet(f"QDialog {{ background-color:{WHITE}; }}")
        lay = QVBoxLayout(self)
        
        self.status = QLabel()
        self.status.setStyleSheet("color:#b02020;")
        lay.addWidget(self.status)
        
        self.f_name = QLineEdit(); self.f_name.setPlaceholderText("UOM Name *"); self.f_name.setFixedHeight(36)
        self.f_abbr = QLineEdit(); self.f_abbr.setPlaceholderText("Abbreviation"); self.f_abbr.setFixedHeight(36)
        
        lay.addWidget(QLabel("<b>Name *</b>")); lay.addWidget(self.f_name)
        lay.addWidget(QLabel("<b>Abbreviation</b>")); lay.addWidget(self.f_abbr)
        
        lay.addStretch()
        br = QHBoxLayout()
        add_btn = navy_btn("Save UOM", color=SUCCESS)
        add_btn.clicked.connect(self._add)
        cls_btn = navy_btn("Close")
        cls_btn.clicked.connect(self.accept)
        br.addWidget(add_btn); br.addWidget(cls_btn)
        lay.addLayout(br)

    def _add(self):
        name = self.f_name.text().strip()
        abbr = self.f_abbr.text().strip()
        if not name: self.status.setText("Name required."); return
        try:
            from database.db import get_connection
            conn = get_connection(); c = conn.cursor()
            
            # Check for duplicate UOM name (case-insensitive)
            c.execute("SELECT 1 FROM uoms WHERE LOWER(name) = LOWER(?)", (name,))
            if c.fetchone():
                self.status.setStyleSheet("color:#b02020;")
                self.status.setText(f"Error: UOM '{name}' already exists.")
                conn.close()
                return

            c.execute("INSERT INTO uoms (name, abbreviation) VALUES (?, ?)", (name, abbr))
            conn.commit(); conn.close()
            self.status.setStyleSheet("color:#1a7a3c;")
            self.status.setText("Added successfully!")
            QTimer.singleShot(1000, self.accept)
        except Exception as e:
            self.status.setStyleSheet("color:#b02020;")
            self.status.setText(f"Error: {e}")
            try:
                conn.close()
            except Exception:
                pass


class UOMDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Units of Measure")
        self.setMinimumSize(800, 600)
        self.setStyleSheet(f"QDialog {{ background-color:{WHITE}; }}")
        
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        
        self.report = ReportTemplate("Units of Measure", is_report=False, show_date_filter=False, parent=self)
        self.report.set_headers(["ID", "Name", "Abbreviation"])
        self.report.btn_add.clicked.connect(self._open_add)
        
        del_btn = navy_btn("Delete", color="#b02020")
        del_btn.clicked.connect(self._delete)
        self.report.filters_layout.addWidget(del_btn)
        
        self._tbl = self.report.table
        hh = self._tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed); self._tbl.setColumnWidth(0, 80)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        
        self.report.global_search.textChanged.connect(self._on_search)
        
        lay.addWidget(self.report)
        self._reload()

    def _open_add(self):
        if UOMFormPopup(self).exec(): pass
        self._reload()

    def _reload(self):
        try:
            from database.db import get_connection, fetchall_dicts
            conn = get_connection(); c = conn.cursor()
            c.execute("SELECT * FROM uoms ORDER BY name")
            self._data = fetchall_dicts(c)
            conn.close()
        except: self._data = []
        self._populate(self._data)

    def _on_search(self, q):
        if not q.strip(): self._populate(self._data); return
        filtered = [d for d in self._data if q.lower() in (d.get("name") or "").lower() or q.lower() in (d.get("abbreviation") or "").lower()]
        self._populate(filtered)

    def _populate(self, data):
        self._tbl.setRowCount(0)
        for r in data:
            row = self._tbl.rowCount(); self._tbl.insertRow(row)
            it_id = QTableWidgetItem(str(r["id"])); it_id.setData(Qt.UserRole, r)
            self._tbl.setItem(row, 0, it_id)
            self._tbl.setItem(row, 1, QTableWidgetItem(str(r["name"])))
            self._tbl.setItem(row, 2, QTableWidgetItem(str(r.get("abbreviation") or "")))

    def _delete(self):
        r = self._tbl.currentRow()
        if r < 0: return
        item = self._tbl.item(r, 0).data(Qt.UserRole)
        if QMessageBox.question(self, "Delete", f"Delete {item['name']}?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
            try:
                from database.db import get_connection
                conn = get_connection(); c = conn.cursor()
                c.execute("DELETE FROM uoms WHERE id=?", (item["id"],))
                conn.commit(); conn.close()
                self._reload()
            except Exception as e: QMessageBox.critical(self, "Error", str(e))
