"""
views/dialogs/restaurant_settings_dialog.py
==========================================
Restaurant Settings — Tables, Floors, and all new behaviour flags.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QDialog, QLineEdit, QSpinBox, QComboBox, QMessageBox, QFrame,
    QTabWidget, QInputDialog, QCheckBox, QScrollArea
)
from PySide6.QtCore import Qt, Signal

# Palette
NAVY      = "#0d1f3c"
OFF_WHITE = "#f8fafc"
WHITE     = "#ffffff"
BORDER    = "#e2e8f0"
GRAY      = "#64748b"
ACCENT    = "#1a5fb4"
SUCCESS   = "#10b981"
DANGER    = "#ef4444"
TEXT      = "#1e293b"
LIGHT_BG  = "#f1f5f9"


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
        QPushButton:hover {{ background-color: {"#0f4a96" if bg == ACCENT else "#4e5f73"}; }}
    """)
    b.clicked.connect(handler)
    return b


def _section(title: str) -> QLabel:
    lbl = QLabel(title.upper())
    lbl.setStyleSheet(f"""
        font-size: 10px; font-weight: 700; color: {GRAY};
        letter-spacing: 1px; padding: 0; margin-top: 6px;
    """)
    return lbl


from PySide6.QtCore import Qt, Signal, Property, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPainter, QColor

# ── Sliding Toggle (Cool Pill) ───────────────────────────────────────────────
class SlidingToggle(QCheckBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(44, 22)
        self.setCursor(Qt.PointingHandCursor)
        
        self._position = 0.0 
        self.animation = QPropertyAnimation(self, b"position")
        self.animation.setDuration(160)
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)

    @Property(float)
    def position(self): return self._position

    @position.setter
    def position(self, pos):
        self._position = pos
        self.update() 

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setChecked(not self.isChecked())
        super().mouseReleaseEvent(event)

    def checkStateSet(self):
        super().checkStateSet()
        self.animation.stop()
        self.animation.setEndValue(1.0 if self.isChecked() else 0.0)
        self.animation.start()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        
        bg_color = QColor(209, 217, 230) 
        if self._position > 0:
            r = int(209 + (self._position * (13 - 209)))
            g = int(217 + (self._position * (31 - 217)))
            b = int(230 + (self._position * (60 - 230)))
            bg_color = QColor(r, g, b)
            
        p.setBrush(bg_color)
        p.drawRoundedRect(0, 0, self.width(), self.height(), 11, 11)
        
        p.setBrush(QColor("#ffffff"))
        handle_size = 16
        margin = 3
        range_x = self.width() - handle_size - (margin * 2)
        handle_x = margin + (self._position * range_x)
        
        p.drawEllipse(handle_x, margin, handle_size, handle_size)
        p.end()


def _toggle(label: str, desc: str = "") -> tuple[QWidget, SlidingToggle]:
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 10, 0, 10)
    
    row = QHBoxLayout()
    txt = QVBoxLayout(); txt.setSpacing(2)
    
    title = QLabel(label)
    title.setStyleSheet(f"color: {TEXT}; font-size: 13px; font-weight: 600;")
    txt.addWidget(title)
    
    if desc:
        sub = QLabel(desc)
        sub.setStyleSheet(f"color: {GRAY}; font-size: 11px;")
        sub.setWordWrap(True)
        txt.addWidget(sub)
        
    tog = SlidingToggle()
    row.addLayout(txt, 1)
    row.addSpacing(20)
    row.addWidget(tog)
    layout.addLayout(row)
    
    line = QFrame()
    line.setFixedHeight(1)
    line.setStyleSheet(f"background: {BORDER}; border: none;")
    layout.addWidget(line)
    
    return container, tog


class AddTableDialog(QDialog):
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
        lay.setSpacing(12)
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
            ("Area / Floor", self.f_floor),
        ]:
            l = QLabel(label)
            l.setStyleSheet(f"color: {GRAY}; font-size: 11px; font-weight: 600;")
            lay.addWidget(l)
            w.setFixedHeight(35)
            w.setStyleSheet(f"border: 1px solid {BORDER}; border-radius: 4px; padding: 0 8px;")
            lay.addWidget(w)

        lay.addSpacing(10)
        btns = QHBoxLayout()
        btns.addWidget(_btn("Cancel", self.reject, color=NAVY, bg=WHITE))
        btns.addWidget(_btn("Create Table", self.accept, color=WHITE, bg=ACCENT))
        lay.addLayout(btns)

    def get_data(self):
        return {
            "name": self.f_name.text().strip(),
            "number": self.f_num.text().strip(),
            "capacity": self.f_cap.value(),
            "floor": self.f_floor.currentText(),
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

        # Header
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
            QTabBar::tab {{
                background: {OFF_WHITE}; color: {TEXT}; padding: 10px 20px;
                border: 1px solid {BORDER}; border-bottom: none;
                border-top-left-radius: 6px; border-top-right-radius: 6px;
                margin-right: 4px; font-weight: bold;
            }}
            QTabBar::tab:selected {{ background: {WHITE}; color: {ACCENT}; border-bottom: 2px solid {WHITE}; }}
        """)

        self.tabs.addTab(self._build_tables_tab(), "Tables")
        self.tabs.addTab(self._build_floors_tab(), "Floors & Areas")
        self.tabs.addTab(self._build_settings_tab(), "Order Settings")
        self.tabs.addTab(self._build_log_tab(), "KOT Log")

        root.addWidget(self.tabs)

    # ── Tab 1: Tables ──────────────────────────────────────────────────────
    def _build_tables_tab(self) -> QWidget:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(15, 15, 15, 15)
        lay.setSpacing(10)

        t_header = QHBoxLayout()
        t_header.addStretch()
        t_header.addWidget(_btn("+ Add Table", self._on_add_table, color=WHITE, bg=ACCENT))
        t_header.addWidget(_btn("Delete Table", self._on_del_table, color=WHITE, bg=DANGER))
        lay.addLayout(t_header)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["Display Name", "Table No.", "Capacity", "Floor / Area", "Waiter"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.setStyleSheet(self._tbl_style())
        lay.addWidget(self._table)
        return tab

    # ── Tab 2: Floors ──────────────────────────────────────────────────────
    def _build_floors_tab(self) -> QWidget:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(15, 15, 15, 15)
        lay.setSpacing(10)

        f_header = QHBoxLayout()
        f_header.addStretch()
        f_header.addWidget(_btn("+ Add Floor", self._on_add_floor, color=WHITE, bg=ACCENT))
        f_header.addWidget(_btn("Delete Floor", self._on_del_floor, color=WHITE, bg=DANGER))
        lay.addLayout(f_header)

        self._floor_table = QTableWidget(0, 1)
        self._floor_table.setHorizontalHeaderLabels(["Floor / Area Name"])
        self._floor_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._floor_table.verticalHeader().setVisible(False)
        self._floor_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._floor_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._floor_table.setAlternatingRowColors(True)
        self._floor_table.setShowGrid(False)
        self._floor_table.setStyleSheet(self._tbl_style())
        lay.addWidget(self._floor_table)
        return tab

    # ── Tab 3: Order Settings ───────────────────────────────────────────────
    def _build_settings_tab(self) -> QWidget:
        tab = QWidget()
        outer = QVBoxLayout(tab)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        content.setStyleSheet(f"background: {WHITE};")
        lay = QVBoxLayout(content)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(8)

        # ── Cashier / Waiter ────────────────────────────────────────────
        lay.addWidget(_section("Cashier / Waiter"))
        
        w_logout, self.chk_auto_logout = _toggle(
            "Auto-logout after transaction",
            "Automatically log out the current user after Pre-bill, Payment, or KOT actions."
        )
        w_isolation, self.chk_waiter_isolation = _toggle(
            "Waiter Isolation",
            "Waiters only see their own occupied tables and available ones. Admins see all."
        )
        lay.addWidget(w_logout)
        lay.addWidget(w_isolation)

        lay.addSpacing(16)
        # lay.addWidget(self._divider())

        # ── KOT Actions ─────────────────────────────────────────────────
        lay.addWidget(_section("KOT Actions"))
        
        w_cancel, self.chk_cancel_reason = _toggle(
            "Require Cancel Reason",
            "Prompt for a reason when a Kitchen Order Ticket is cancelled."
        )
        w_modify, self.chk_modify_reason = _toggle(
            "Require Modify Reason",
            "Prompt for a reason when an existing Kitchen Order is edited."
        )
        w_lock_pay, self.chk_lock_pay_kot = _toggle(
            "Lock Pay KOT (Supervisor PIN)",
            "Require a supervisor PIN to close/pay a Kitchen Order Ticket."
        )
        lay.addWidget(w_cancel)
        lay.addWidget(w_modify)
        lay.addWidget(w_lock_pay)

        lay.addSpacing(16)
        # lay.addWidget(self._divider())

        # ── Billing ─────────────────────────────────────────────────────
        lay.addWidget(_section("Billing"))
        
        w_split, self.chk_split_bill = _toggle(
            "Allow Split Bill",
            "Enable the split-payment interface for restaurant tables."
        )
        w_partial, self.chk_partial_payment = _toggle(
            "Allow Partial / Collect Shares",
            "Let cashiers collect each person's share (by MOP) before firing the final payment."
        )
        lay.addWidget(w_split)
        lay.addWidget(w_partial)

        lay.addStretch()

        save_btn = _btn("Save Settings", self._on_save_settings, color=WHITE, bg=ACCENT)
        save_btn.setFixedHeight(38)
        save_row = QHBoxLayout()
        save_row.addStretch()
        save_row.addWidget(save_btn)
        lay.addLayout(save_row)

        scroll.setWidget(content)
        outer.addWidget(scroll)
        return tab

    # ── Tab 4: KOT Log ──────────────────────────────────────────────────────
    def _build_log_tab(self) -> QWidget:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(15, 15, 15, 15)
        lay.setSpacing(10)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Show:"))
        self._log_filter = QComboBox()
        self._log_filter.addItems(["All", "Cancelled", "Modified"])
        self._log_filter.setFixedWidth(160)
        self._log_filter.setFixedHeight(32)
        self._log_filter.currentIndexChanged.connect(self._load_log)
        filter_row.addWidget(self._log_filter)
        filter_row.addStretch()
        refresh_log = _btn("↻ Refresh", self._load_log, color=ACCENT, bg=WHITE)
        filter_row.addWidget(refresh_log)
        lay.addLayout(filter_row)

        self._log_table = QTableWidget(0, 5)
        self._log_table.setHorizontalHeaderLabels(
            ["Date/Time", "Action", "Order #", "Table", "Reason"])
        self._log_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._log_table.verticalHeader().setVisible(False)
        self._log_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._log_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._log_table.setAlternatingRowColors(True)
        self._log_table.setShowGrid(False)
        self._log_table.setStyleSheet(self._tbl_style())
        lay.addWidget(self._log_table)
        return tab

    # ── Helpers ────────────────────────────────────────────────────────────
    def _divider(self) -> QFrame:
        f = QFrame(); f.setFrameShape(QFrame.HLine)
        f.setStyleSheet(f"border: none; border-top: 1px solid {BORDER};")
        f.setFixedHeight(1)
        return f

    def _tbl_style(self) -> str:
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

    # ── Data Loading ───────────────────────────────────────────────────────
    def _load(self):
        from models.restaurant_order import (
            is_restaurant_enabled, get_all_tables, get_all_floors,
            get_restaurant_settings, get_waiter_name
        )
        enabled = is_restaurant_enabled()
        self._update_toggle_ui(enabled)

        # Tables
        tables = get_all_tables()
        self._table.setRowCount(0)
        for t in tables:
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._table.setItem(r, 0, QTableWidgetItem(t["name"]))
            self._table.setItem(r, 1, QTableWidgetItem(t["table_number"]))
            self._table.setItem(r, 2, QTableWidgetItem(str(t["capacity"])))
            self._table.setItem(r, 3, QTableWidgetItem(t["floor"]))
            waiter = get_waiter_name(t.get("active_waiter_id"))
            self._table.setItem(r, 4, QTableWidgetItem(waiter or "—"))
            self._table.item(r, 0).setData(Qt.UserRole, t["id"])

        # Floors
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

        # Settings toggles
        try:
            s = get_restaurant_settings()
            for key, chk in [
                ("auto_logout_on_finalise", self.chk_auto_logout),
                ("waiter_isolation",        self.chk_waiter_isolation),
                ("allow_split_bill",        self.chk_split_bill),
                ("allow_partial_payment",   self.chk_partial_payment),
                ("require_cancel_reason",   self.chk_cancel_reason),
                ("require_modify_reason",   self.chk_modify_reason),
                ("lock_pay_kot",            self.chk_lock_pay_kot),
            ]:
                val = bool(s.get(key))
                chk.setChecked(val)
                chk.position = 1.0 if val else 0.0
        except Exception as e:
            print(f"Error loading restaurant settings: {e}")

        self._load_log()

    def _load_log(self):
        try:
            from models.restaurant_order import get_kot_log
            filter_map = {"All": None, "Cancelled": "Cancel", "Modified": "Modify"}
            action = filter_map.get(self._log_filter.currentText())
            rows = get_kot_log(action=action)
            self._log_table.setRowCount(0)
            for entry in rows:
                r = self._log_table.rowCount()
                self._log_table.insertRow(r)
                dt = entry.get("logged_at")
                dt_str = dt.strftime("%Y-%m-%d %H:%M") if dt else ""
                self._log_table.setItem(r, 0, QTableWidgetItem(dt_str))
                self._log_table.setItem(r, 1, QTableWidgetItem(entry.get("action", "")))
                self._log_table.setItem(r, 2, QTableWidgetItem(f"ORD-{entry.get('order_id', '')}"))
                tname = f"{entry.get('table_name', '')} {entry.get('table_number', '')}".strip()
                self._log_table.setItem(r, 3, QTableWidgetItem(tname or "—"))
                self._log_table.setItem(r, 4, QTableWidgetItem(entry.get("reason") or "—"))
        except Exception as e:
            print(f"Error loading KOT log: {e}")

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

    # ── Actions ────────────────────────────────────────────────────────────
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
        if row < 0:
            return
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
        if row < 0:
            return
        if QMessageBox.question(self, "Confirm", "Delete this floor?") != QMessageBox.Yes:
            return
        floor_id = self._floor_table.item(row, 0).data(Qt.UserRole)
        from models.restaurant_order import delete_floor
        delete_floor(floor_id)
        self._load()

    def _on_save_settings(self):
        try:
            from models.restaurant_order import save_restaurant_settings, is_restaurant_enabled
            settings = {
                "enabled": is_restaurant_enabled(),
                "auto_logout_on_finalise": self.chk_auto_logout.isChecked(),
                "waiter_isolation": self.chk_waiter_isolation.isChecked(),
                "allow_split_bill": self.chk_split_bill.isChecked(),
                "allow_partial_payment": self.chk_partial_payment.isChecked(),
                "require_cancel_reason": self.chk_cancel_reason.isChecked(),
                "require_modify_reason": self.chk_modify_reason.isChecked(),
                "lock_pay_kot": self.chk_lock_pay_kot.isChecked(),
            }
            save_restaurant_settings(settings)
            QMessageBox.information(self, "Saved", "Restaurant settings saved successfully.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save settings:\n{e}")