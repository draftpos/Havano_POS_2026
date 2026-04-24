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

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextOption
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QTextEdit, QFrame, QGroupBox, QSizePolicy,
    QTabWidget, QWidget,
)

from models.advance_settings import AdvanceSettings

log = logging.getLogger(__name__)

# Palette (matches other POS dialogs)
NAVY      = "#0d1f3c"
NAVY_2    = "#162d52"
WHITE     = "#ffffff"
OFF_WHITE = "#f5f8fc"
BORDER    = "#c8d8ec"
DARK_TEXT = "#0d1f3c"
MUTED     = "#5a7a9a"
ACCENT    = "#1a5fb4"
SUCCESS   = "#1a7a3c"
SUCCESS_H = "#1f9447"

# Sensible clamps — outside these ranges the output looks terrible on 80 mm paper.
RECEIPT_HEADER_MIN, RECEIPT_HEADER_MAX = 8,  28
RECEIPT_BODY_MIN,   RECEIPT_BODY_MAX   = 7,  20
KITCHEN_HEADER_MIN, KITCHEN_HEADER_MAX = 10, 36   # KOT headers are usually bigger
KITCHEN_BODY_MIN,   KITCHEN_BODY_MAX   = 8,  24


class AdvanceSettingsDialog(QDialog):
    """Two-tab font editor: one tab per print path, each with live preview."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Print Font Sizes")
        self.setModal(True)
        self.setFixedSize(640, 600)
        self.setStyleSheet(f"QDialog {{ background: {WHITE}; }}")

        self._settings = AdvanceSettings.load_from_file()
        self._build()
        self._refresh_receipt_preview()
        self._refresh_kitchen_preview()

    # -----------------------------------------------------------------------
    # UI
    # -----------------------------------------------------------------------

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        root.addWidget(self._header_bar())
        root.addWidget(self._tabs(), 1)
        root.addLayout(self._buttons_row())

    def _header_bar(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(42)
        bar.setStyleSheet(f"background: {NAVY}; border-radius: 6px;")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(14, 0, 14, 0)
        title = QLabel("Print Font Sizes")
        title.setStyleSheet(
            f"color: {WHITE}; font-size: 15px; font-weight: bold; background: transparent;"
        )
        sub = QLabel("Receipt and kitchen tuned independently — changes save on OK")
        sub.setStyleSheet("color: #b9cbe4; font-size: 11px; background: transparent;")
        lay.addWidget(title)
        lay.addStretch(1)
        lay.addWidget(sub)
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
        return tabs

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

    def _buttons_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        cancel = QPushButton("Cancel")
        cancel.setFixedHeight(36)
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.setStyleSheet(self._btn_css(NAVY_2, NAVY))
        cancel.clicked.connect(self.reject)

        save = QPushButton("Save")
        save.setFixedHeight(36)
        save.setCursor(Qt.PointingHandCursor)
        save.setStyleSheet(self._btn_css(SUCCESS, SUCCESS_H))
        save.clicked.connect(self._save)

        row.addStretch(1)
        row.addWidget(cancel)
        row.addWidget(save)
        return row

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
        """Sample of the KOT slip — big order#, item lines, terminal footer."""
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
            line("— end of order —", pt=body_pt, align="center"),
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

        try:
            self._settings.save_to_file()
            log.info(
                "Print font sizes saved: receipt(hdr=%d body=%d)  "
                "kitchen(hdr=%d body=%d)",
                self._settings.contentHeaderSize,
                self._settings.contentFontSize,
                self._settings.kitchenHeaderSize,
                self._settings.kitchenBodySize,
            )
        except Exception as e:
            log.error("AdvanceSettings save failed: %s", e)
        self.accept()

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
