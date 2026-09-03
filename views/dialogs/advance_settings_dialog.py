"""
views/dialogs/advance_settings_dialog.py
────────────────────────────────────────
Per-device font-size editor for **both** print paths:

    • Receipt (customer-facing invoice)
        – models.advance_settings.contentHeaderSize
        – models.advance_settings.contentFontSize
    • Kitchen (KOT production slip)
        – models.advance_settings.kitchenHeaderSize
        – models.advance_settings.kitchenBodySize

Two independent tabs with their own sliders + live previews. Saving writes
every touched field to `advance_settings.json` via AdvanceSettings.save_to_file.

Font family + style are configured elsewhere; this dialog is deliberately
narrow (sizes only) because that's the knob 95% of merchants need to tune.
"""

from __future__ import annotations

import logging

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QTextEdit, QFrame, QGroupBox, QSizePolicy,
    QTabWidget, QWidget, QCheckBox
)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, Property as _Prop
from PySide6.QtGui import QColor, QPainter, QLinearGradient, QRadialGradient, QTextOption

# =============================================================================
# ToggleSwitch - pill toggle
# =============================================================================
class _TogglePill(QWidget):
    def __init__(self, size=20, parent=None):
        super().__init__(parent)
        self._size     = size
        self._checked  = False
        self._knob_pos = 0.0
        self.setFixedSize(int(2.2 * size), size)
        self.setCursor(Qt.PointingHandCursor)
        self._anim = QPropertyAnimation(self, b"knob_pos", self)
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.InOutCubic)

    def _get_knob_pos(self): return self._knob_pos
    def _set_knob_pos(self, v):
        self._knob_pos = v; self.update()
    knob_pos = _Prop(float, _get_knob_pos, _set_knob_pos)

    def isChecked(self): return self._checked
    def setChecked(self, value: bool, animated=False):
        self._checked = bool(value)
        target = 1.0 if self._checked else 0.0
        if animated:
            self._anim.stop()
            self._anim.setStartValue(self._knob_pos)
            self._anim.setEndValue(target)
            self._anim.start()
        else:
            self._knob_pos = target; self.update()
    def mousePressEvent(self, _ev):
        self.setChecked(not self._checked, animated=True)

    def paintEvent(self, _ev):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        s = self._size; w = self.width(); h = self.height(); r = h / 2
        t = self._knob_pos
        if t < 0.01:
            p.setBrush(QColor("#d7d7d7")); p.setPen(Qt.NoPen)
            p.drawRoundedRect(0, 0, w, h, r, r)
        else:
            grad = QLinearGradient(0, 0, w, 0)
            grad.setColorAt(0, QColor("#f19af3")); grad.setColorAt(1, QColor("#f099b5"))
            p.setBrush(QColor("#d7d7d7")); p.setPen(Qt.NoPen)
            p.drawRoundedRect(0, 0, w, h, r, r)
            if t > 0.99:
                p.setBrush(grad); p.drawRoundedRect(0, 0, w, h, r, r)
            else:
                p.setOpacity(t); p.setBrush(grad)
                p.drawRoundedRect(0, 0, w, h, r, r); p.setOpacity(1.0)
        knob_d = 0.8*s; knob_r = knob_d/2
        off_x = 0.1*s; on_x = 1.3*s
        knob_x = off_x + self._knob_pos*(on_x - off_x); knob_y = 0.1*s
        cx = knob_x+knob_r; cy = knob_y+knob_r
        shadow = QRadialGradient(cx, cy+4, knob_r*1.1)
        shadow.setColorAt(0, QColor(0,0,0,55)); shadow.setColorAt(0.6, QColor(0,0,0,30))
        shadow.setColorAt(1, QColor(0,0,0,0))
        p.setBrush(shadow); p.setPen(Qt.NoPen)
        p.drawEllipse(int(knob_x-knob_r*0.15), int(knob_y+knob_r*0.5),
                      int(knob_d*1.3), int(knob_d*0.9))
        kg = QLinearGradient(cx, knob_y, cx, knob_y+knob_d)
        kg.setColorAt(0, QColor("#dedede")); kg.setColorAt(1, QColor("#ffffff"))
        p.setBrush(kg); p.setPen(Qt.NoPen)
        p.drawEllipse(int(knob_x), int(knob_y), int(knob_d), int(knob_d))
        p.end()

class _ToggleSwitch(QWidget):
    """Pill toggle + label. API: isChecked() / setChecked(bool)."""
    def __init__(self, label: str, size: int = 18, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(12)
        self._pill = _TogglePill(size=size, parent=self)
        layout.addWidget(self._pill)
        self._lbl = QLabel(label)
        self._lbl.setStyleSheet(f"font-size:13px; font-weight:600; color:{DARK_TEXT}; background:transparent;")
        layout.addWidget(self._lbl)
        layout.addStretch()

    def isChecked(self) -> bool: return self._pill.isChecked()
    def setChecked(self, value: bool): self._pill.setChecked(value, animated=False)

from models.advance_settings import AdvanceSettings

log = logging.getLogger(__name__)

# Palette (matches other POS dialogs)
from theme import *

# Sensible clamps - outside these ranges the output looks terrible on 80 mm paper.
RECEIPT_HEADER_MIN, RECEIPT_HEADER_MAX = 8,  28
RECEIPT_BODY_MIN,   RECEIPT_BODY_MAX   = 7,  20
KITCHEN_HEADER_MIN, KITCHEN_HEADER_MAX = 10, 36   # KOT headers are usually bigger
KITCHEN_BODY_MIN,   KITCHEN_BODY_MAX   = 8,  24


class AdvanceSettingsDialog(QDialog):
    """Two-tab font editor: one tab per print path, each with live preview."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Advanced Settings")
        self.setModal(True)
        self.setMinimumSize(480, 520)
        self.resize(640, 700)
        self.setStyleSheet(f"QDialog {{ background: {WHITE}; }}")

        self._settings = AdvanceSettings.load_from_file()
        self._build()
        self._refresh_receipt_preview()
        self._refresh_kitchen_preview()

    # -----------------------------------------------------------------------
    # UI
    # -----------------------------------------------------------------------

    def _build(self) -> None:
        from PySide6.QtWidgets import QScrollArea, QFrame as _QFrame
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)

        root.addWidget(self._header_bar())

        # Wrap tabs in scroll area so small screens can still reach all controls
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(_QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        tab_container = QWidget()
        tc_lay = QVBoxLayout(tab_container)
        tc_lay.setContentsMargins(0, 0, 0, 0)
        tc_lay.addWidget(self._tabs())
        scroll.setWidget(tab_container)
        root.addWidget(scroll, 1)

        # Status label (full width, above buttons)
        self._save_status_lbl = QLabel("")
        self._save_status_lbl.setAlignment(Qt.AlignCenter)
        self._save_status_lbl.setFixedHeight(20)
        self._save_status_lbl.setStyleSheet("font-size:12px; font-weight:bold; background:transparent;")
        root.addWidget(self._save_status_lbl)



    def _header_bar(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(58)
        bar.setStyleSheet(f"background: {NAVY}; border-radius: 6px;")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(14, 6, 14, 6)
        title_sub_lay = QVBoxLayout()
        title_sub_lay.setSpacing(2)
        title = QLabel("Advanced Settings")
        title.setStyleSheet(
            f"color: {WHITE}; font-size: 15px; font-weight: bold; background: transparent;"
        )
        sub = QLabel("Adjust receipt, kitchen, UI and system mode settings below")
        sub.setStyleSheet("color: #b9cbe4; font-size: 11px; background: transparent;")
        title_sub_lay.addWidget(title)
        title_sub_lay.addWidget(sub)
        title_sub_lay.addStretch(1)
        lay.addLayout(title_sub_lay)
        lay.addStretch(1)

        # Action Buttons in Header
        save_btn = QPushButton(" Save")
        save_btn.setFixedHeight(32)
        save_btn.setMinimumWidth(90)
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setStyleSheet(f"""
            QPushButton {{ background: {SUCCESS}; color: {WHITE}; border: none; border-radius: 5px; font-weight: bold; font-size: 13px; }}
            QPushButton:hover {{ background: {SUCCESS_H}; }}
        """)
        save_btn.clicked.connect(self._save)

        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(32)
        close_btn.setMinimumWidth(80)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{ background: rgba(255, 255, 255, 0.15); color: {WHITE}; border: 1px solid rgba(255, 255, 255, 0.3); border-radius: 5px; font-weight: bold; font-size: 13px; }}
            QPushButton:hover {{ background: rgba(255, 255, 255, 0.25); border-color: {WHITE}; }}
        """)
        close_btn.clicked.connect(self.accept)

        lay.addWidget(save_btn)
        lay.addWidget(close_btn)
        return bar

    def _tabs(self) -> QTabWidget:
        tabs = QTabWidget()
        tabs.setStyleSheet(f"""
            QTabBar::tab {{
                background: {OFF_WHITE}; color: {DARK_TEXT};
                padding: 8px 18px; border: 1px solid {BORDER};
                border-bottom: none; border-top-left-radius: 6px;
                border-top-right-radius: 6px; font-weight: bold;
            }}
            QTabBar::tab:selected {{ background: {WHITE}; color: {NAVY}; }}
            QTabWidget::pane     {{ border: 1px solid {BORDER}; top: -1px; }}
        """)
        tabs.addTab(self._receipt_tab(), "Receipt")
        tabs.addTab(self._kitchen_tab(), "Kitchen Order")
        tabs.addTab(self._ui_tab(), "UI Features")
        tabs.addTab(self._system_mode_tab(), "System Mode")
        return tabs

    def _system_mode_tab(self) -> QWidget:
        page = QWidget()
        col = QVBoxLayout(page)
        col.setContentsMargins(12, 12, 12, 12)
        col.setSpacing(10)

        grp = QGroupBox("System Mode Toggle")
        grp.setStyleSheet(self._group_css())
        gl = QVBoxLayout(grp)
        gl.setContentsMargins(14, 14, 14, 14)
        gl.setSpacing(15)

        try:
            from services.credentials import get_system_mode
            current_mode = get_system_mode().upper()
        except Exception:
            current_mode = "UNKNOWN"

        lbl = QLabel(f"The system is currently running in: <b>{current_mode}</b> mode.")
        lbl.setStyleSheet(f"color: {DARK_TEXT}; font-size: 14px;")
        gl.addWidget(lbl)

        from PySide6.QtWidgets import QComboBox
        row = QHBoxLayout()
        label = QLabel("Override System Mode:")
        label.setStyleSheet(f"color: {DARK_TEXT}; font-size: 13px; font-weight: bold;")
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["Frappe", "Odoo", "SaaS", "Offline"])
        self._mode_combo.setFixedHeight(34)
        self._mode_combo.setStyleSheet(f"QComboBox {{ background:{WHITE}; border:1px solid {BORDER}; border-radius:5px; padding:0 10px; color:{DARK_TEXT}; }}")
        
        saved_mode = getattr(self._settings, "systemModeOverride", "") or current_mode
        saved_mode = saved_mode.capitalize()
        idx = self._mode_combo.findText(saved_mode, Qt.MatchContains)
        if idx >= 0:
            self._mode_combo.setCurrentIndex(idx)
        else:
            self._mode_combo.setCurrentIndex(0)

        row.addWidget(label)
        row.addWidget(self._mode_combo)
        row.addStretch()

        gl.addLayout(row)

        desc = QLabel("Changes to the system mode will take effect upon the next restart.")
        desc.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
        gl.addWidget(desc)

        col.addWidget(grp)
        col.addStretch(1)
        return page

    # ── RECEIPT TAB ─────────────────────────────────────────────────────────

    def _receipt_tab(self) -> QWidget:
        page = QWidget()
        col  = QVBoxLayout(page)
        col.setContentsMargins(12, 12, 12, 12)
        col.setSpacing(10)

        grp = QGroupBox("Receipt sizes")
        grp.setStyleSheet(self._group_css())
        gl = QVBoxLayout(grp)
        gl.setContentsMargins(14, 14, 14, 14)
        gl.setSpacing(10)

        (self._r_header_slider,
         self._r_header_value) = self._slider_row(
            "Header font size",
            RECEIPT_HEADER_MIN, RECEIPT_HEADER_MAX,
            int(self._settings.contentHeaderSize or 10),
            self._on_receipt_header_changed,
        )
        gl.addLayout(self._r_header_slider.parent_layout)

        (self._r_body_slider,
         self._r_body_value) = self._slider_row(
            "Body font size",
            RECEIPT_BODY_MIN, RECEIPT_BODY_MAX,
            int(self._settings.contentFontSize or 8),
            self._on_receipt_body_changed,
        )
        gl.addLayout(self._r_body_slider.parent_layout)

        col.addWidget(grp)
        col.addWidget(QLabel("Preview:"))
        self._r_preview = self._new_preview()
        col.addWidget(self._r_preview, 1)
        return page

    # ── KITCHEN TAB ─────────────────────────────────────────────────────────

    def _kitchen_tab(self) -> QWidget:
        page = QWidget()
        col  = QVBoxLayout(page)
        col.setContentsMargins(12, 12, 12, 12)
        col.setSpacing(10)

        grp = QGroupBox("Kitchen order sizes")
        grp.setStyleSheet(self._group_css())
        gl = QVBoxLayout(grp)
        gl.setContentsMargins(14, 14, 14, 14)
        gl.setSpacing(10)

        (self._k_header_slider,
         self._k_header_value) = self._slider_row(
            "Order # font size",
            KITCHEN_HEADER_MIN, KITCHEN_HEADER_MAX,
            int(getattr(self._settings, "kitchenHeaderSize", 14) or 14),
            self._on_kitchen_header_changed,
        )
        gl.addLayout(self._k_header_slider.parent_layout)

        (self._k_body_slider,
         self._k_body_value) = self._slider_row(
            "Item line font size",
            KITCHEN_BODY_MIN, KITCHEN_BODY_MAX,
            int(getattr(self._settings, "kitchenBodySize", 10) or 10),
            self._on_kitchen_body_changed,
        )
        gl.addLayout(self._k_body_slider.parent_layout)

        col.addWidget(grp)
        col.addWidget(QLabel("Preview:"))
        self._k_preview = self._new_preview()
        col.addWidget(self._k_preview, 1)
        return page

    # ── UI FEATURES TAB ──────────────────────────────────────────────────────

    def _ui_tab(self) -> QWidget:
        page = QWidget()
        col  = QVBoxLayout(page)
        col.setContentsMargins(12, 12, 12, 12)
        col.setSpacing(10)

        grp = QGroupBox("Main Window Toggles")
        grp.setStyleSheet(self._group_css())
        gl = QVBoxLayout(grp)
        gl.setContentsMargins(14, 14, 14, 14)
        gl.setSpacing(10)

        self._cb_laybyes = _ToggleSwitch("Enable Laybyes")
        self._cb_laybyes.setChecked(getattr(self._settings, "enableLaybyes", False))
        
        self._cb_quotes = _ToggleSwitch("Enable Payment Quotes")
        self._cb_quotes.setChecked(getattr(self._settings, "enableQuotes", False))

        self._cb_payments = _ToggleSwitch("Enable Payments")
        self._cb_payments.setChecked(getattr(self._settings, "enablePayments", False))

        self._cb_erp = _ToggleSwitch("Show ERP Modules in Dashboard")
        self._cb_erp.setChecked(getattr(self._settings, "enableERPModules", False))

        self._cb_sales_report = _ToggleSwitch("Show Sales Report (Dropdown)")
        self._cb_sales_report.setChecked(getattr(self._settings, "showSalesReport", False))
        
        self._cb_sales_list = _ToggleSwitch("Show Sales (Dropdown)")
        self._cb_sales_list.setChecked(getattr(self._settings, "showSalesList", False))

        self._cb_capitalize = _ToggleSwitch("Capitalize Item Names (Title Case)")
        self._cb_capitalize.setChecked(getattr(self._settings, "capitalizeItemNames", False))

        gl.addWidget(self._cb_laybyes)
        gl.addWidget(self._cb_quotes)
        gl.addWidget(self._cb_payments)
        gl.addWidget(self._cb_erp)
        gl.addWidget(self._cb_sales_report)
        gl.addWidget(self._cb_sales_list)
        gl.addWidget(self._cb_capitalize)

        # ── Backoffice App Grid Toggles ──
        app_grp = QGroupBox("Backoffice Dashboard Menus (Odoo/Frappe Modes)")
        app_grp.setStyleSheet(self._group_css())
        agl = QVBoxLayout(app_grp)
        agl.setContentsMargins(14, 14, 14, 14)
        agl.setSpacing(10)

        self._cb_app_sales = _ToggleSwitch("Show Sales Menu")
        self._cb_app_sales.setChecked(getattr(self._settings, "showAppSales", False))
        
        self._cb_app_suppliers = _ToggleSwitch("Show Suppliers Menu")
        self._cb_app_suppliers.setChecked(getattr(self._settings, "showAppSuppliers", False))

        self._cb_app_maint = _ToggleSwitch("Show Maintenance Menu")
        self._cb_app_maint.setChecked(getattr(self._settings, "showAppMaintenance", False))

        self._cb_app_finance = _ToggleSwitch("Show Finance Menu")
        self._cb_app_finance.setChecked(getattr(self._settings, "showAppFinance", False))

        self._cb_app_inventory = _ToggleSwitch("Show Inventory Menu")
        self._cb_app_inventory.setChecked(getattr(self._settings, "showAppInventory", False))

        self._cb_app_expenses = _ToggleSwitch("Show Expenses Menu")
        self._cb_app_expenses.setChecked(getattr(self._settings, "showAppExpenses", False))

        agl.addWidget(self._cb_app_sales)
        agl.addWidget(self._cb_app_suppliers)
        agl.addWidget(self._cb_app_maint)
        agl.addWidget(self._cb_app_finance)
        agl.addWidget(self._cb_app_inventory)
        agl.addWidget(self._cb_app_expenses)

        col.addWidget(grp)
        col.addWidget(app_grp)
        col.addStretch(1)
        return page

    # ── Shared builders ─────────────────────────────────────────────────────

    def _slider_row(self, label: str, lo: int, hi: int,
                    initial: int, on_change) -> tuple[QSlider, QLabel]:
        """Build a [label ────●──── value] row. Returns (slider, valueLbl)."""
        row = QHBoxLayout()
        row.setSpacing(10)

        lbl = QLabel(label)
        lbl.setMinimumWidth(150)
        lbl.setStyleSheet(f"color: {DARK_TEXT}; font-size: 13px;")

        slider = QSlider(Qt.Horizontal)
        slider.setRange(lo, hi)
        slider.setValue(max(lo, min(hi, initial)))
        slider.setSingleStep(1)
        slider.setPageStep(2)
        slider.setTickInterval(2)
        slider.setTickPosition(QSlider.TicksBelow)

        value_lbl = QLabel(f"{slider.value()} pt")
        value_lbl.setMinimumWidth(52)
        value_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        value_lbl.setStyleSheet(
            f"color: {ACCENT}; font-weight: bold; font-size: 13px;"
        )

        slider.valueChanged.connect(on_change)

        row.addWidget(lbl)
        row.addWidget(slider, 1)
        row.addWidget(value_lbl)

        slider.parent_layout = row  # type: ignore[attr-defined]
        return slider, value_lbl

    def _new_preview(self) -> QTextEdit:
        edit = QTextEdit()
        edit.setReadOnly(True)
        edit.setWordWrapMode(QTextOption.NoWrap)
        edit.setStyleSheet(f"""
            QTextEdit {{
                background: {OFF_WHITE}; color: {DARK_TEXT};
                border: 1px solid {BORDER}; border-radius: 6px;
                padding: 12px;
            }}
        """)
        edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        return edit



    # -----------------------------------------------------------------------
    # Slots
    # -----------------------------------------------------------------------

    def _on_receipt_header_changed(self, v: int) -> None:
        self._r_header_value.setText(f"{v} pt")
        self._refresh_receipt_preview()

    def _on_receipt_body_changed(self, v: int) -> None:
        self._r_body_value.setText(f"{v} pt")
        self._refresh_receipt_preview()

    def _on_kitchen_header_changed(self, v: int) -> None:
        self._k_header_value.setText(f"{v} pt")
        self._refresh_kitchen_preview()

    def _on_kitchen_body_changed(self, v: int) -> None:
        self._k_body_value.setText(f"{v} pt")
        self._refresh_kitchen_preview()

    # -----------------------------------------------------------------------
    # Preview renderers
    # -----------------------------------------------------------------------

    def _refresh_receipt_preview(self) -> None:
        hpt = int(self._r_header_slider.value())
        bpt = int(self._r_body_slider.value())
        html = self._receipt_html(
            header_family=self._settings.contentHeaderFontName or "Arial",
            header_pt=hpt,
            body_family=self._settings.contentFontName or "Arial",
            body_pt=bpt,
        )
        self._r_preview.setHtml(html)

    def _refresh_kitchen_preview(self) -> None:
        hpt = int(self._k_header_slider.value())
        bpt = int(self._k_body_slider.value())
        html = self._kitchen_html(
            family=self._settings.contentFontName or "Arial",
            header_pt=hpt,
            body_pt=bpt,
        )
        self._k_preview.setHtml(html)

    @staticmethod
    def _receipt_html(*, header_family: str, header_pt: int,
                      body_family: str, body_pt: int) -> str:
        """Small sample of the main receipt layout."""
        def hdr(text: str) -> str:
            return (f"<div style=\"font-family:{header_family}; "
                    f"font-size:{header_pt}pt; font-weight:bold; text-align:center;\">"
                    f"{text}</div>")

        def body(text: str, align: str = "left", bold: bool = False) -> str:
            w = "bold" if bold else "normal"
            return (f"<div style=\"font-family:{body_family}; "
                    f"font-size:{body_pt}pt; font-weight:{w}; text-align:{align};\">"
                    f"{text}</div>")

        return "".join([
            hdr("HAVANO POS"),
            body("123 Sample Street", "center"),
            body("&mdash;&mdash;&mdash;&mdash;&mdash;&mdash;&mdash;&mdash;&mdash;", "center"),
            body("Invoice: INV-0001", "left"),
            body("Cashier: Jane", "left"),
            body("&mdash;&mdash;&mdash;&mdash;&mdash;&mdash;&mdash;&mdash;&mdash;", "center"),
            body("1 x Coca-Cola 500ml &nbsp; 2.00", "left"),
            body("2 x Bread Loaf &nbsp; &nbsp; &nbsp; 3.00", "left"),
            body("&mdash;&mdash;&mdash;&mdash;&mdash;&mdash;&mdash;&mdash;&mdash;", "center"),
            body("TOTAL &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; 5.00", "left", bold=True),
            body("&nbsp;", "left"),
            body("Thank you!", "center"),
        ])

    @staticmethod
    def _kitchen_html(*, family: str, header_pt: int, body_pt: int) -> str:
        """Sample of the KOT slip - big order#, item lines, terminal footer."""
        def line(text: str, *, pt: int, bold: bool = False,
                 align: str = "left") -> str:
            w = "bold" if bold else "normal"
            return (f"<div style=\"font-family:{family}; "
                    f"font-size:{pt}pt; font-weight:{w}; text-align:{align};\">"
                    f"{text}</div>")

        small_pt = max(body_pt - 2, 6)
        return "".join([
            line("Order #12", pt=header_pt, bold=True, align="center"),
            line("&mdash;&mdash;&mdash;&mdash;&mdash;&mdash;&mdash;&mdash;&mdash;",
                 pt=body_pt, align="center"),
            line("Invoice: INV-0001", pt=body_pt, align="center"),
            line("Cashier: Jane",     pt=body_pt, align="center"),
            line("Time: 2026-04-24  11:42", pt=body_pt, align="center"),
            line("&mdash;&mdash;&mdash;&mdash;&mdash;&mdash;&mdash;&mdash;&mdash;",
                 pt=body_pt, align="center"),
            line("&nbsp;&nbsp;1 &nbsp; x &nbsp; 1/4 Chicken Meal-M", pt=body_pt, bold=True),
            line("&nbsp;&nbsp;2 &nbsp; x &nbsp; Chicken Burger-H",   pt=body_pt, bold=True),
            line("&mdash;&mdash;&mdash;&mdash;&mdash;&mdash;&mdash;&mdash;&mdash;",
                 pt=body_pt, align="center"),
            line("- end of order -", pt=body_pt, align="center"),
            line("Terminal: KITCHEN", pt=small_pt, align="center"),
        ])

    # -----------------------------------------------------------------------
    # Save / Cancel
    # -----------------------------------------------------------------------

    def _save(self) -> None:
        self._settings.contentHeaderSize  = int(self._r_header_slider.value())
        self._settings.contentFontSize    = int(self._r_body_slider.value())
        self._settings.kitchenHeaderSize  = int(self._k_header_slider.value())
        self._settings.kitchenBodySize    = int(self._k_body_slider.value())
        self._settings.enableLaybyes      = self._cb_laybyes.isChecked()
        self._settings.enableQuotes       = self._cb_quotes.isChecked()
        self._settings.enablePayments     = self._cb_payments.isChecked()
        self._settings.enableERPModules   = self._cb_erp.isChecked()
        self._settings.showSalesReport    = self._cb_sales_report.isChecked()
        self._settings.showSalesList      = self._cb_sales_list.isChecked()
        self._settings.capitalizeItemNames = self._cb_capitalize.isChecked()
        new_mode = self._mode_combo.currentText().lower()
        
        mode_changed = False
        try:
            from services.credentials import set_system_mode, get_system_mode
            if new_mode != get_system_mode().lower():
                mode_ok = set_system_mode(new_mode, parent=self)
                if not mode_ok:
                    # Revert combo box
                    saved_mode = get_system_mode().capitalize()
                    idx = self._mode_combo.findText(saved_mode, Qt.MatchContains)
                    if idx >= 0:
                        self._mode_combo.setCurrentIndex(idx)
                    return
                mode_changed = True
        except Exception as _ex_mode:
            print(f"[advance_settings_dialog] set_system_mode error: {_ex_mode}")

        self._settings.systemModeOverride = new_mode

        if new_mode in ("frappe", "odoo", "saas"):
            self._settings.showAppSales       = False
            self._settings.showAppSuppliers   = False
            self._settings.showAppMaintenance = False
            self._settings.showAppFinance     = False
            self._settings.showAppInventory   = False
            self._settings.showAppExpenses    = False
        else:
            self._settings.showAppSales       = self._cb_app_sales.isChecked()
            self._settings.showAppSuppliers   = self._cb_app_suppliers.isChecked()
            self._settings.showAppMaintenance = self._cb_app_maint.isChecked()
            self._settings.showAppFinance     = self._cb_app_finance.isChecked()
            self._settings.showAppInventory   = self._cb_app_inventory.isChecked()
            self._settings.showAppExpenses    = self._cb_app_expenses.isChecked()

        try:
            # Use a path relative to THIS file so CWD never matters
            import os
            _here = os.path.dirname(os.path.abspath(__file__))
            _root = os.path.normpath(os.path.join(_here, "..", ".."))
            _path = os.path.join(_root, "settings", "advance_settings.json")
            self._settings.save_to_file(_path)

            # Also propagate system mode to credentials so get_system_mode() returns the new value
            try:
                from services.credentials import set_system_mode
                set_system_mode(new_mode)
            except Exception:
                pass

            # Visual confirmation
            if hasattr(self, "_save_status_lbl"):
                self._save_status_lbl.setText("✓ Settings saved successfully!")
                self._save_status_lbl.setStyleSheet(
                    f"font-size:12px; font-weight:bold; color:{SUCCESS}; background:transparent;"
                )
                from PySide6.QtCore import QTimer
                QTimer.singleShot(3000, lambda: (
                    self._save_status_lbl.setText(""),
                ) if self._save_status_lbl else None)

            log.info(
                "Settings saved: receipt(hdr=%d body=%d)  kitchen(hdr=%d body=%d)  mode=%s",
                self._settings.contentHeaderSize, self._settings.contentFontSize,
                self._settings.kitchenHeaderSize, self._settings.kitchenBodySize,
                new_mode,
            )

            if mode_changed:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.information(
                    self,
                    "Mode Changed",
                    f"System mode changed to '{new_mode.upper()}'.\nDatabase was wiped and re-migrated.\n\nReturning to Login Screen..."
                )
                self.accept()
                p = getattr(self, "parent_window", None) or self.parent()
                if p and hasattr(p, "_logout"):
                    p._logout()
                elif p and hasattr(p, "_do_logout"):
                    p._do_logout()
        except Exception as e:
            log.error("AdvanceSettings save failed: %s", e)
            if hasattr(self, "_save_status_lbl"):
                self._save_status_lbl.setText(f"✗ Save failed: {e}")
                self._save_status_lbl.setStyleSheet(
                    "font-size:11px; font-weight:bold; color:#c0392b; background:transparent;"
                )
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Save Failed", f"Could not save settings:\n\n{e}")

    # -----------------------------------------------------------------------
    # Style helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _group_css() -> str:
        return f"""
            QGroupBox {{
                font-weight: bold; border: 1px solid {BORDER};
                border-radius: 6px; margin-top: 10px; padding-top: 8px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin; left: 10px; padding: 0 5px;
                color: {NAVY}; background: transparent;
            }}
        """

    @staticmethod
    def _btn_css(bg: str, hover: str) -> str:
        return f"""
            QPushButton {{
                background: {bg}; color: {WHITE}; border: none;
                border-radius: 5px; font-size: 13px; font-weight: bold;
                padding: 0 18px;
            }}
            QPushButton:hover {{ background: {hover}; }}
        """
