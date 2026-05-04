"""
views/dialogs/restaurant_settings_dialog.py
==========================================
Improved Frappe-style Restaurant Settings.
Buttons at the top, separate add dialog.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QDialog, QLineEdit, QSpinBox, QComboBox, QMessageBox, QFrame,
    QTabWidget, QInputDialog
)
from PySide6.QtCore import Qt, Signal

# Frappe-ish Palette
NAVY      = "#0d1f3c"
OFF_WHITE = "#f8fafc"
WHITE     = "#ffffff"
BORDER    = "#e2e8f0"
GRAY      = "#64748b"
ACCENT    = "#1a5fb4" # Primary Blue
SUCCESS   = "#10b981" # Emerald
DANGER    = "#ef4444" # Red
TEXT      = "#1e293b"

def _btn(text, handler, color=WHITE, bg=GRAY, border=True):
    b = QPushButton(text)
    b.setFixedHeight(32)
    b.setCursor(Qt.PointingHandCursor)
    border_style = f"border: 1px solid {BORDER};" if border else "border:none;"
    b.setStyleSheet(f"""
        QPushButton {{
            background-color: {bg}; color: {color};
            {border_style} border-radius: 6px;
            font-size: 12px; font-weight: 600; padding: 0 16px;
        }}
        QPushButton:hover {{ opacity: 0.9; }}
    """)
    b.clicked.connect(handler)
    return b

class AddTableDialog(QDialog):
    """Clean dialog to add a new table."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Table")
        self.setFixedWidth(350)
        self.setStyleSheet(f"QDialog {{ background: {WHITE}; }}")
        
        self.floors = []
        try:
            from models.restaurant_order import get_all_floors
            self.floors = get_all_floors()
        except Exception:
            pass
            
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(15)
        lay.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Table Details")
        title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {NAVY};")
        lay.addWidget(title)

        self.f_name = QLineEdit(); self.f_name.setPlaceholderText("e.g. Window Side")
        self.f_num = QLineEdit(); self.f_num.setPlaceholderText("e.g. T-10")
        self.f_cap = QSpinBox(); self.f_cap.setRange(1, 20); self.f_cap.setValue(2)
        self.f_floor = QComboBox()
        
        if self.floors:
            self.f_floor.addItems([f["name"] for f in self.floors])
        else:
            self.f_floor.addItems(["Main Floor"])

        for label, w in [
            ("Display Name", self.f_name),
            ("Table Number", self.f_num),
            ("No. of People", self.f_cap),
            ("Area / Floor", self.f_floor)
        ]:
            l = QLabel(label)
            l.setStyleSheet(f"color: {GRAY}; font-size: 11px; font-weight: 600;")
            lay.addWidget(l)
            w.setFixedHeight(35)
            w.setStyleSheet(f"border: 1px solid {BORDER}; border-radius: 4px; padding: 0 8px;")
            lay.addWidget(w)

        lay.addSpacing(10)
        
        btns = QHBoxLayout()
        can = _btn("Cancel", self.reject, color=NAVY, bg=WHITE)
        sub = _btn("Create Table", self.accept, color=WHITE, bg=ACCENT)
        btns.addWidget(can)
        btns.addWidget(sub)
        lay.addLayout(btns)

    def get_data(self):
        return {
            "name": self.f_name.text().strip(),
            "number": self.f_num.text().strip(),
            "capacity": self.f_cap.value(),
            "floor": self.f_floor.currentText()
        }

class RestaurantSettingsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"QWidget {{ background:{WHITE}; }}")
        self._build()
        self._load()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(20)

        # Header Action Bar
        header = QHBoxLayout()
        title = QLabel("Restaurant Management")
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {NAVY};")
        header.addWidget(title)
        header.addStretch()

        self.toggle_btn = QPushButton("Disabled")
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setFixedWidth(120)
        self.toggle_btn.setFixedHeight(32)
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.clicked.connect(self._on_toggle)
        header.addWidget(self.toggle_btn)

        root.addLayout(header)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: 1px solid {BORDER}; border-radius: 8px; background: {WHITE}; }}
            QTabBar::tab {{ background: {OFF_WHITE}; color: {TEXT}; padding: 10px 20px; border: 1px solid {BORDER}; border-bottom: none; border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 4px; font-weight: bold; }}
            QTabBar::tab:selected {{ background: {WHITE}; color: {ACCENT}; border-bottom: 2px solid {WHITE}; }}
        """)
        
        # --- Tab 1: Tables ---
        self.tab_tables = QWidget()
        lay_tables = QVBoxLayout(self.tab_tables)
        lay_tables.setContentsMargins(15, 15, 15, 15)
        lay_tables.setSpacing(10)
        
        t_header = QHBoxLayout()
        add_btn = _btn("+ Add Table", self._on_add_table, color=WHITE, bg=ACCENT)
        del_btn = _btn("Delete Table", self._on_del_table, color=WHITE, bg=DANGER)
        t_header.addStretch()
        t_header.addWidget(add_btn)
        t_header.addWidget(del_btn)
        lay_tables.addLayout(t_header)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Display Name", "Table No.", "No. of People", "Floor / Area"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.setStyleSheet(self._table_style())
        lay_tables.addWidget(self._table)
        
        self.tabs.addTab(self.tab_tables, "Tables")
        
        # --- Tab 2: Floors ---
        self.tab_floors = QWidget()
        lay_floors = QVBoxLayout(self.tab_floors)
        lay_floors.setContentsMargins(15, 15, 15, 15)
        lay_floors.setSpacing(10)
        
        f_header = QHBoxLayout()
        f_add_btn = _btn("+ Add Floor", self._on_add_floor, color=WHITE, bg=ACCENT)
        f_del_btn = _btn("Delete Floor", self._on_del_floor, color=WHITE, bg=DANGER)
        f_header.addStretch()
        f_header.addWidget(f_add_btn)
        f_header.addWidget(f_del_btn)
        lay_floors.addLayout(f_header)
        
        self._floor_table = QTableWidget(0, 1)
        self._floor_table.setHorizontalHeaderLabels(["Floor / Area Name"])
        self._floor_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._floor_table.verticalHeader().setVisible(False)
        self._floor_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._floor_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._floor_table.setAlternatingRowColors(True)
        self._floor_table.setShowGrid(False)
        self._floor_table.setStyleSheet(self._table_style())
        lay_floors.addWidget(self._floor_table)
        
        self.tabs.addTab(self.tab_floors, "Floors & Areas")

        root.addWidget(self.tabs)
        
    def _table_style(self):
        return f"""
            QTableWidget {{ 
                background-color: {WHITE}; 
                border: 1px solid {BORDER};
                border-radius: 8px;
                gridline-color: transparent;
            }}
            QTableWidget::item {{ 
                border-bottom: 1px solid {OFF_WHITE};
                padding: 12px;
                color: {TEXT};
            }}
            QTableWidget::item:selected {{ 
                background-color: {OFF_WHITE};
                color: {ACCENT};
                font-weight: bold;
            }}
            QHeaderView::section {{ 
                background-color: {WHITE}; 
                color: {GRAY};
                font-weight: bold;
                font-size: 11px;
                text-transform: uppercase;
                border: none;
                border-bottom: 2px solid {BORDER};
                padding: 10px;
            }}
        """

    def _load(self):
        from models.restaurant_order import is_restaurant_enabled, get_all_tables, get_all_floors
        enabled = is_restaurant_enabled()
        self._update_toggle_ui(enabled)

        # Load Tables
        tables = get_all_tables()
        self._table.setRowCount(0)
        for t in tables:
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._table.setItem(r, 0, QTableWidgetItem(t["name"]))
            self._table.setItem(r, 1, QTableWidgetItem(t["table_number"]))
            self._table.setItem(r, 2, QTableWidgetItem(str(t["capacity"])))
            self._table.setItem(r, 3, QTableWidgetItem(t["floor"]))
            self._table.item(r, 0).setData(Qt.UserRole, t["id"])

        # Load Floors
        try:
            floors = get_all_floors()
            self._floor_table.setRowCount(0)
            for f in floors:
                r = self._floor_table.rowCount()
                self._floor_table.insertRow(r)
                self._floor_table.setItem(r, 0, QTableWidgetItem(f["name"]))
                self._floor_table.item(r, 0).setData(Qt.UserRole, f["id"])
        except Exception as e:
            print(f"Error loading floors: {e}")

    def _update_toggle_ui(self, enabled: bool):
        self.toggle_btn.setChecked(enabled)
        if enabled:
            self.toggle_btn.setText("Enabled")
            self.toggle_btn.setStyleSheet(f"""
                QPushButton {{ background:{SUCCESS}; color:{WHITE}; font-weight:bold; border-radius:16px; border:none; }}
            """)
        else:
            self.toggle_btn.setText("Disabled")
            self.toggle_btn.setStyleSheet(f"""
                QPushButton {{ background:{GRAY}; color:{WHITE}; font-weight:bold; border-radius:16px; border:none; }}
            """)

    def _on_toggle(self):
        from models.restaurant_order import save_restaurant_enabled
        enabled = self.toggle_btn.isChecked()
        save_restaurant_enabled(enabled)
        self._update_toggle_ui(enabled)

    def _on_add_table(self):
        dlg = AddTableDialog(self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            if not data["name"] or not data["number"]:
                QMessageBox.warning(self, "Invalid Input", "Name and Number are required.")
                return
            from models.restaurant_order import create_table
            create_table(data["name"], data["number"], data["capacity"], data["floor"])
            self._load()

    def _on_del_table(self):
        row = self._table.currentRow()
        if row < 0: return
        if QMessageBox.question(self, "Confirm", "Delete this table?") != QMessageBox.Yes:
            return
        table_id = self._table.item(row, 0).data(Qt.UserRole)
        from models.restaurant_order import delete_table
        delete_table(table_id)
        self._load()
        
    def _on_add_floor(self):
        name, ok = QInputDialog.getText(self, "Add Floor", "Floor / Area Name:")
        if ok and name.strip():
            try:
                from models.restaurant_order import create_floor
                create_floor(name.strip())
                self._load()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to create floor:\n{e}")

    def _on_del_floor(self):
        row = self._floor_table.currentRow()
        if row < 0: return
        if QMessageBox.question(self, "Confirm", "Delete this floor?") != QMessageBox.Yes:
            return
        floor_id = self._floor_table.item(row, 0).data(Qt.UserRole)
        from models.restaurant_order import delete_floor
        delete_floor(floor_id)
        self._load()

