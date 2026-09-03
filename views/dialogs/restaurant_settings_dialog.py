"""
views/dialogs/restaurant_settings_dialog.py
==========================================
Restaurant Settings - SYSTEM-LEVEL settings only.
User-level settings (auto_logout, allow_close_table, allow_prebill,
allow_edit_kot) live in the Users dialog, NOT here.

System-level:
  - Tables & Floors management
  - Waiter Isolation
  - KOT Actions (require cancel/modify reason, lock pay kot)
  - Billing (split bill, partial payment)
  - Global: Default to Restaurant View on Login
  - Printing: KOT font sizes & header text
  - Predefined Data: Notes & Cancel Reasons
  - KOT Log
"""

from __future__ import annotations

# pyrefly: ignore [missing-import]
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QDialog, QLineEdit, QSpinBox, QComboBox, QMessageBox, QFrame,
    QTabWidget, QInputDialog, QCheckBox, QScrollArea, QDateEdit
)
# pyrefly: ignore [missing-import]
from PySide6.QtCore import Qt, Signal, Property, QPropertyAnimation, QEasingCurve, QDate
# pyrefly: ignore [missing-import]
from PySide6.QtGui import QPainter, QColor

# Palette
from theme import *


def _btn(text, handler, color=WHITE, bg=MUTED, border=True):
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
        QPushButton:hover {{ background-color: {"#0f4a96" if bg == ACCENT else "#4e5f73" if bg == MUTED else bg}; }}
    """)
    b.clicked.connect(handler)
    return b


def _section(title: str) -> QLabel:
    lbl = QLabel(title.upper())
    lbl.setStyleSheet(f"""
        font-size: 10px; font-weight: 700; color: {MUTED};
        letter-spacing: 1px; padding: 0; margin-top: 6px;
    """)
    return lbl


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
    title.setStyleSheet(f"color: {DARK_TEXT}; font-size: 13px; font-weight: 600;")
    txt.addWidget(title)

    if desc:
        sub = QLabel(desc)
        sub.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
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
            l.setStyleSheet(f"color: {MUTED}; font-size: 11px; font-weight: 600;")
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
                background: {OFF_WHITE}; color: {DARK_TEXT}; padding: 10px 20px;
                border: 1px solid {BORDER}; border-bottom: none;
                border-top-left-radius: 6px; border-top-right-radius: 6px;
                margin-right: 4px; font-weight: bold;
            }}
            QTabBar::tab:selected {{ background: {WHITE}; color: {ACCENT}; border-bottom: 2px solid {WHITE}; }}
        """)

        self.tabs.addTab(self._build_tables_tab(), "Tables")
        self.tabs.addTab(self._build_floors_tab(), "Floors & Areas")
        self.tabs.addTab(self._build_settings_tab(), "System Settings")
        self.tabs.addTab(self._build_printing_tab(), "Printing")
        self.tabs.addTab(self._build_predefined_tab(), "Predefined Data")
        self.tabs.addTab(self._build_log_tab(), "KOT Log")
        self.tabs.addTab(self._build_sales_report_tab(), "Sales Report")

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

    # ── Tab 3: System Settings (NO user-level fields here) ─────────────────
    def _build_settings_tab(self) -> QWidget:
        """
        SYSTEM-LEVEL settings only.
        Auto-logout is per-user and lives in the Users dialog.
        allow_close_table / allow_prebill / allow_edit_kot are per-user too.
        """
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

        # ── Info banner ──────────────────────────────────────────────────
        info_banner = QLabel(
            "⚙  These are system-wide defaults that apply to all users.\n"
            "   Per-user settings (Auto-logout, Close Table, Pre-bill, Edit KOT)\n"
            "   are managed in Settings -> Users."
        )
        info_banner.setStyleSheet(f"""
            background: #eff6ff; color: {ACCENT}; border: 1px solid #bfdbfe;
            border-radius: 6px; padding: 10px 14px; font-size: 11px;
        """)
        info_banner.setWordWrap(True)
        lay.addWidget(info_banner)
        lay.addSpacing(10)

        # ── Waiter Behaviour ────────────────────────────────────────────
        lay.addWidget(_section("Waiter Behaviour"))

        w_isolation, self.chk_waiter_isolation = _toggle(
            "Waiter Isolation",
            "Waiters only see their own occupied tables and available ones. Admins see all."
        )
        lay.addWidget(w_isolation)

        lay.addSpacing(16)

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

        lay.addSpacing(16)

        # ── Global Application Settings ──────────────────────────────────
        lay.addWidget(_section("Global Application Settings"))
        w_default, self.chk_default_restaurant = _toggle(
            "Default to Restaurant View on Login",
            "Automatically switch to the table view layout after a successful login (applies to all users)."
        )
        lay.addWidget(w_default)

        lay.addStretch()

        save_btn = _btn("Save System Settings", self._on_save_settings, color=WHITE, bg=ACCENT)
        save_btn.setFixedHeight(38)
        save_row = QHBoxLayout()
        save_row.addStretch()
        save_row.addWidget(save_btn)
        lay.addLayout(save_row)

        scroll.setWidget(content)
        outer.addWidget(scroll)
        return tab

    # ── Tab 4: Printing ────────────────────────────────────────────────────
    def _build_printing_tab(self) -> QWidget:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)

        lay.addWidget(_section("Kitchen Order Ticket (KOT) Customisation"))

        # Header Text
        h_lay = QHBoxLayout()
        h_lay.addWidget(QLabel("KOT Header Text:"), 1)
        self.f_kot_hdr_text = QLineEdit()
        self.f_kot_hdr_text.setPlaceholderText("e.g. KITCHEN ORDER")
        self.f_kot_hdr_text.setFixedHeight(32)
        h_lay.addWidget(self.f_kot_hdr_text, 2)
        lay.addLayout(h_lay)

        # Font Sizes
        f_lay = QHBoxLayout(); f_lay.setSpacing(20)

        v1 = QVBoxLayout(); v1.setSpacing(4)
        v1.addWidget(QLabel("Header Font Size:"))
        self.f_kot_hdr_size = QSpinBox()
        self.f_kot_hdr_size.setRange(8, 48); self.f_kot_hdr_size.setValue(12)
        self.f_kot_hdr_size.setFixedHeight(32)
        v1.addWidget(self.f_kot_hdr_size)
        f_lay.addLayout(v1)

        v2 = QVBoxLayout(); v2.setSpacing(4)
        v2.addWidget(QLabel("Order # Font Size:"))
        self.f_kot_num_size = QSpinBox()
        self.f_kot_num_size.setRange(8, 72); self.f_kot_num_size.setValue(16)
        self.f_kot_num_size.setFixedHeight(32)
        v2.addWidget(self.f_kot_num_size)
        f_lay.addLayout(v2)

        lay.addLayout(f_lay)
        lay.addSpacing(20)

        lay.addWidget(_section("Branding & Versioning"))
        footer_info = QLabel(
            "The mandatory branding 'Havano Version 1.1.8' is automatically "
            "appended to all KOT printouts."
        )
        footer_info.setStyleSheet(f"color: {MUTED}; font-size: 11px; font-style: italic;")
        footer_info.setWordWrap(True)
        lay.addWidget(footer_info)

        lay.addSpacing(10)
        save_print_btn = _btn("Save Printing Settings", self._on_save_settings, color=WHITE, bg=ACCENT)
        save_print_btn.setFixedHeight(38)
        pr_row = QHBoxLayout()
        pr_row.addStretch()
        pr_row.addWidget(save_print_btn)
        lay.addLayout(pr_row)

        lay.addStretch()
        return tab

    # ── Tab 5: Predefined Data ──────────────────────────────────────────────
    def _build_predefined_tab(self) -> QWidget:
        tab = QWidget()
        lay = QHBoxLayout(tab)
        lay.setContentsMargins(15, 15, 15, 15)
        lay.setSpacing(20)

        # Left: Table Notes
        v1 = QVBoxLayout()
        v1.addWidget(_section("Predefined Table/Item Notes"))

        b1 = QHBoxLayout()
        b1.addWidget(_btn("+ Add Note", self._on_add_note, color=WHITE, bg=ACCENT))
        b1.addWidget(_btn("Delete", self._on_del_note, color=WHITE, bg=DANGER))
        v1.addLayout(b1)

        self._notes_list = QTableWidget(0, 1)
        self._notes_list.setHorizontalHeaderLabels(["Note Text"])
        self._notes_list.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._notes_list.verticalHeader().setVisible(False)
        self._notes_list.setStyleSheet(self._tbl_style())
        v1.addWidget(self._notes_list)
        lay.addLayout(v1, 1)

        # Right: Cancel Reasons
        v2 = QVBoxLayout()
        v2.addWidget(_section("KOT Cancellation Reasons"))

        b2 = QHBoxLayout()
        b2.addWidget(_btn("+ Add Reason", self._on_add_reason, color=WHITE, bg=ACCENT))
        b2.addWidget(_btn("Delete", self._on_del_reason, color=WHITE, bg=DANGER))
        v2.addLayout(b2)

        self._reasons_list = QTableWidget(0, 1)
        self._reasons_list.setHorizontalHeaderLabels(["Reason Text"])
        self._reasons_list.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._reasons_list.verticalHeader().setVisible(False)
        self._reasons_list.setStyleSheet(self._tbl_style())
        v2.addWidget(self._reasons_list)
        lay.addLayout(v2, 1)

        return tab

    # ── Tab 6: KOT Log ──────────────────────────────────────────────────────
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

    # ── Tab 7: Sales Report ──────────────────────────────────────────────────
    def _build_sales_report_tab(self) -> QWidget:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(15, 15, 15, 15)
        lay.setSpacing(10)

        # Filters
        filter_row = QHBoxLayout()
        
        filter_row.addWidget(QLabel("Waiter:"))
        self.report_waiter_combo = QComboBox()
        self.report_waiter_combo.setFixedHeight(32)
        self.report_waiter_combo.setMinimumWidth(150)
        filter_row.addWidget(self.report_waiter_combo)

        filter_row.addSpacing(10)
        filter_row.addWidget(QLabel("From:"))
        self.report_start_date = QDateEdit()
        self.report_start_date.setCalendarPopup(True)
        self.report_start_date.setDate(QDate.currentDate().addDays(-7))
        self.report_start_date.setFixedHeight(32)
        filter_row.addWidget(self.report_start_date)

        filter_row.addWidget(QLabel("To:"))
        self.report_end_date = QDateEdit()
        self.report_end_date.setCalendarPopup(True)
        self.report_end_date.setDate(QDate.currentDate())
        self.report_end_date.setFixedHeight(32)
        filter_row.addWidget(self.report_end_date)

        filter_row.addSpacing(10)
        btn_filter = _btn("Filter", self._on_filter_sales, color=WHITE, bg=ACCENT)
        filter_row.addWidget(btn_filter)

        filter_row.addStretch()
        lay.addLayout(filter_row)

        # Summary Row
        self.report_summary_label = QLabel("Total Sales: $0.00")
        self.report_summary_label.setStyleSheet(f"font-weight: bold; color: {NAVY}; font-size: 14px;")
        lay.addWidget(self.report_summary_label)

        # Table
        self.report_table = QTableWidget(0, 6)
        self.report_table.setHorizontalHeaderLabels(
            ["Date", "Invoice #", "Customer", "Waiter", "Amount", "Status"]
        )
        self.report_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.report_table.verticalHeader().setVisible(False)
        self.report_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.report_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.report_table.setAlternatingRowColors(True)
        self.report_table.setShowGrid(False)
        self.report_table.setStyleSheet(self._tbl_style())
        lay.addWidget(self.report_table)

        return tab

    # ── Helpers ────────────────────────────────────────────────────────────
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
                color: {DARK_TEXT};
            }}
            QTableWidget::item:selected {{
                background-color: {OFF_WHITE};
                color: {ACCENT};
                font-weight: bold;
            }}
            QHeaderView::section {{
                background-color: {WHITE};
                color: {MUTED};
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
            self._table.setItem(r, 4, QTableWidgetItem(waiter or "-"))
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

        # Settings toggles - SYSTEM LEVEL ONLY
        # Note: auto_logout_on_finalise is intentionally NOT loaded here.
        # It is a per-user flag stored on the users table.
        try:
            s = get_restaurant_settings()
            for key, chk in [
                ("waiter_isolation",      self.chk_waiter_isolation),
                ("allow_split_bill",      self.chk_split_bill),
                ("allow_partial_payment", self.chk_partial_payment),
                ("require_cancel_reason", self.chk_cancel_reason),
                ("require_modify_reason", self.chk_modify_reason),
                ("lock_pay_kot",          self.chk_lock_pay_kot),
            ]:
                val = bool(s.get(key))
                chk.setChecked(val)
                chk.position = 1.0 if val else 0.0

            dv = bool(s.get("default_view_restaurant", False))
            self.chk_default_restaurant.setChecked(dv)
            self.chk_default_restaurant.position = 1.0 if dv else 0.0

            # --- sanitise printing values (guard against old corrupted "True"/1 rows) ---
            def _safe_text(v, default):
                """Return v only if it looks like real text, else default."""
                sv = str(v).strip() if v is not None else ""
                if sv.lower() in ("true", "false", "0", "1", "") or not any(c.isalpha() for c in sv) and len(sv) <= 2:
                    return default
                return sv
            def _safe_int(v, default, lo, hi):
                """Return v as int only if it is a sane size value, else default."""
                try:
                    i = int(v)
                    return i if lo <= i <= hi else default
                except (ValueError, TypeError):
                    return default
            self.f_kot_hdr_text.setText(_safe_text(s.get("kot_header_text"), "KITCHEN ORDER"))
            self.f_kot_hdr_size.setValue(_safe_int(s.get("kot_header_size"), 12, 8, 48))
            self.f_kot_num_size.setValue(_safe_int(s.get("kot_order_num_size"), 16, 8, 72))
        except Exception as e:
            print(f"Error loading restaurant settings: {e}")

        # Predefined data
        self._load_predefined()
        self._load_log()
        self._load_waiters()

    def _load_waiters(self):
        try:
            from models.restaurant_order import get_all_waiter_names
            names = get_all_waiter_names()
            if hasattr(self, "report_waiter_combo"):
                self.report_waiter_combo.clear()
                self.report_waiter_combo.addItem("All Waiters")
                self.report_waiter_combo.addItems(names)
        except Exception as e:
            print(f"Error loading waiters: {e}")

    def _load_predefined(self):
        try:
            from models.restaurant_order import get_predefined_notes, get_cancel_reasons
            notes = get_predefined_notes()
            self._notes_list.setRowCount(0)
            for n in notes:
                r = self._notes_list.rowCount()
                self._notes_list.insertRow(r)
                self._notes_list.setItem(r, 0, QTableWidgetItem(n))

            reasons = get_cancel_reasons()
            self._reasons_list.setRowCount(0)
            for rs in reasons:
                r = self._reasons_list.rowCount()
                self._reasons_list.insertRow(r)
                self._reasons_list.setItem(r, 0, QTableWidgetItem(rs))
        except Exception:
            pass

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
                self._log_table.setItem(r, 3, QTableWidgetItem(tname or "-"))
                self._log_table.setItem(r, 4, QTableWidgetItem(entry.get("reason") or "-"))
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
                QPushButton {{ background:{MUTED}; color:{WHITE}; font-weight:bold; border-radius:16px; border:none; }}
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
        """
        Save SYSTEM-LEVEL settings only.
        auto_logout is per-user -> NOT saved here.
        """
        try:
            from models.restaurant_order import save_restaurant_settings, is_restaurant_enabled
            settings = {
                "enabled":                 is_restaurant_enabled(),
                # SYSTEM flags only - no auto_logout_on_finalise
                "waiter_isolation":        self.chk_waiter_isolation.isChecked(),
                "allow_split_bill":        self.chk_split_bill.isChecked(),
                "allow_partial_payment":   self.chk_partial_payment.isChecked(),
                "require_cancel_reason":   self.chk_cancel_reason.isChecked(),
                "require_modify_reason":   self.chk_modify_reason.isChecked(),
                "lock_pay_kot":            self.chk_lock_pay_kot.isChecked(),
                "kot_header_text":         self.f_kot_hdr_text.text().strip() or "KITCHEN ORDER",
                "kot_header_size":         self.f_kot_hdr_size.value(),
                "kot_order_num_size":      self.f_kot_num_size.value(),
                "default_view_restaurant": self.chk_default_restaurant.isChecked(),
            }
            save_restaurant_settings(settings)
            QMessageBox.information(self, "Saved", "Restaurant settings saved successfully.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save settings:\n{e}")

    def _on_add_note(self):
        text, ok = QInputDialog.getText(self, "Add Predefined Note", "Note Text:")
        if ok and text.strip():
            from models.restaurant_order import add_predefined_note
            add_predefined_note(text.strip())
            self._load_predefined()

    def _on_del_note(self):
        row = self._notes_list.currentRow()
        if row < 0: return
        note = self._notes_list.item(row, 0).text()
        from models.restaurant_order import delete_predefined_note
        delete_predefined_note(note)
        self._load_predefined()

    def _on_add_reason(self):
        text, ok = QInputDialog.getText(self, "Add Cancel Reason", "Reason Text:")
        if ok and text.strip():
            from models.restaurant_order import add_cancel_reason
            add_cancel_reason(text.strip())
            self._load_predefined()

    def _on_del_reason(self):
        row = self._reasons_list.currentRow()
        if row < 0: return
        reason = self._reasons_list.item(row, 0).text()
        from models.restaurant_order import delete_cancel_reason
        delete_cancel_reason(reason)
        self._load_predefined()

    def _on_filter_sales(self):
        try:
            from models.restaurant_order import get_sales_by_waiter
            waiter = self.report_waiter_combo.currentText()
            start = self.report_start_date.date().toString("yyyy-MM-dd")
            end = self.report_end_date.date().toString("yyyy-MM-dd")
            
            rows = get_sales_by_waiter(waiter, start, end)
            self.report_table.setRowCount(0)
            total = 0.0
            
            for s in rows:
                r = self.report_table.rowCount()
                self.report_table.insertRow(r)
                self.report_table.setItem(r, 0, QTableWidgetItem(s.get("invoice_date", "")))
                self.report_table.setItem(r, 1, QTableWidgetItem(s.get("invoice_number", "")))
                self.report_table.setItem(r, 2, QTableWidgetItem(s.get("customer_name", "")))
                self.report_table.setItem(r, 3, QTableWidgetItem(s.get("waiter_name", "") or "-"))
                
                amt = float(s.get("total_amount") or 0.0)
                total += amt
                self.report_table.setItem(r, 4, QTableWidgetItem(f"${amt:,.2f}"))
                self.report_table.setItem(r, 5, QTableWidgetItem(s.get("status", "Paid")))
                
            self.report_summary_label.setText(f"Total Sales: ${total:,.2f}")
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load sales report:\n{e}")


class RestaurantSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Restaurant Management")
        self.setMinimumSize(960, 720)
        self.setWindowState(Qt.WindowMaximized)
        self.setModal(True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.page = RestaurantSettingsPage(self)
        lay.addWidget(self.page)
