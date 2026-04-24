"""
views/dialogs/variant_picker_dialog.py
──────────────────────────────────────
Touch-friendly picker for Item variants — mirrors the look and feel of
the UOM popup (views/main_window.py :: UomPickerDialog) so cashiers see
a consistent pattern whenever the POS needs a secondary pick.

Flow:
    1. Cashier taps a template tile on the POS grid.
    2. MainWindow._pick_variant() launches this dialog with the template
       product dict.
    3. Dialog loads variants via models.product.get_variants_of(part_no)
       and renders one large tappable button per variant.
    4. Up / Down / Enter are wired for keyboard selection.
    5. On click or Enter → self.selected_variant is populated and the
       dialog is accepted.

Pricing is deliberately NOT shown here — it's resolved against the active
customer's price list back in MainWindow._resolve_price_for_product().
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QWidget, QScrollArea,
)

try:
    import qtawesome as qta
except Exception:
    qta = None  # Cancel icon is optional

log = logging.getLogger(__name__)

# ── Palette (mirrors UomPickerDialog) ─────────────────────────────────────
NAVY      = "#0d1f3c"
WHITE     = "#ffffff"
LIGHT     = "#e4eaf4"
BORDER    = "#c8d8ec"
DARK_TEXT = "#0d1f3c"
MUTED     = "#5a7a9a"
ACCENT    = "#1a5fb4"


class VariantPickerDialog(QDialog):
    """Touch-friendly variant picker styled like the UOM picker."""

    def __init__(self, template: dict, parent=None):
        super().__init__(parent)
        self.template                             = template or {}
        self.selected_variant: Optional[dict]     = None
        self._variant_buttons: list[tuple[QPushButton, dict]] = []
        self._active_idx                          = 0

        self.setWindowTitle("Select Variant")
        self.setModal(True)
        self.setStyleSheet(f"""
            QDialog {{
                background: {WHITE};
                font-family: 'Segoe UI', sans-serif;
            }}
        """)

        variants = self._load_variants()

        # Size identically to the UOM popup: header ~110 + 82px per row + 60 cancel.
        n = max(1, len(variants))
        self.setFixedSize(460, min(110 + n * 82 + 60, 640))

        self._build(variants)
        self._refresh_active_highlight()

    # -----------------------------------------------------------------------
    # Data loading
    # -----------------------------------------------------------------------

    def _load_variants(self) -> list[dict]:
        """Pull variant rows for this template from the local products table."""
        part_no = (self.template.get("part_no") or "").strip()
        if not part_no:
            return []
        try:
            from models.product import get_variants_of
            return get_variants_of(part_no) or []
        except Exception as e:
            log.error("VariantPicker: get_variants_of(%s) failed: %s", part_no, e)
            return []

    # -----------------------------------------------------------------------
    # Build UI — same layout structure as UomPickerDialog
    # -----------------------------------------------------------------------

    def _build(self, variants: list[dict]) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(0)

        root.addWidget(self._header_widget())
        root.addSpacing(14)

        if not variants:
            root.addWidget(self._empty_state_widget())
        else:
            # Variants may legitimately exceed the visible area for very
            # large templates — drop them into a scroll wrapper so the
            # dialog never explodes in height.
            if len(variants) > 6:
                root.addWidget(self._variants_scroll(variants), 1)
            else:
                for i, v in enumerate(variants):
                    root.addWidget(self._variant_button(v))
                    if i < len(variants) - 1:
                        root.addSpacing(8)

        root.addSpacing(14)
        root.addWidget(self._cancel_button())

    def _header_widget(self) -> QWidget:
        """Dark navy header: small prompt above a bold product name."""
        hdr = QWidget()
        hdr.setStyleSheet(f"background:{NAVY}; border-radius:10px;")
        hl = QVBoxLayout(hdr)
        hl.setContentsMargins(16, 12, 16, 12)
        hl.setSpacing(2)

        prompt = QLabel("Select variant")
        prompt.setStyleSheet(
            "color:rgba(255,255,255,0.7); font-size:11px; "
            "font-weight:500; background:transparent;"
        )
        name = QLabel(self.template.get("name") or "Template")
        name.setStyleSheet(
            "color:#ffffff; font-size:15px; font-weight:bold; background:transparent;"
        )
        name.setWordWrap(True)

        hl.addWidget(prompt)
        hl.addWidget(name)
        return hdr

    def _empty_state_widget(self) -> QWidget:
        """Shown when the template has no synced variants."""
        msg = QLabel(
            "This item has no synced variants.\n\n"
            "Create variants on the server and re-sync products."
        )
        msg.setAlignment(Qt.AlignCenter)
        msg.setWordWrap(True)
        msg.setStyleSheet(
            f"color:{MUTED}; font-size:13px; background:transparent; padding:24px 8px;"
        )
        return msg

    def _variants_scroll(self, variants: list[dict]) -> QScrollArea:
        """Vertical scroll wrapper — only used when list is long."""
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.NoFrame)
        area.setStyleSheet("QScrollArea { background: transparent; }")

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        col = QVBoxLayout(inner)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(8)
        for v in variants:
            col.addWidget(self._variant_button(v))
        col.addStretch(1)

        area.setWidget(inner)
        return area

    def _variant_button(self, variant: dict) -> QPushButton:
        """
        One large row per variant.

        Layout inside the button:
            [ variant name    |    attribute summary ]

        Matches the UOM picker's two-label pattern — just swaps the price
        column for the variant's attribute string (e.g. "Red · M").
        """
        name  = variant.get("name")    or variant.get("part_no") or ""
        attrs = self._summarise_attributes(variant.get("attributes") or "")

        btn = QPushButton()
        btn.setFixedHeight(70)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFocusPolicy(Qt.NoFocus)

        inner = QHBoxLayout(btn)
        inner.setContentsMargins(18, 0, 18, 0)

        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(
            f"color:{DARK_TEXT}; font-size:16px; font-weight:bold; "
            "background:transparent;"
        )
        name_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        attr_lbl = QLabel(attrs or "—")
        attr_lbl.setStyleSheet(
            f"color:{ACCENT}; font-size:14px; font-weight:bold; "
            "background:transparent;"
        )
        attr_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        attr_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        inner.addWidget(name_lbl, 1)
        inner.addWidget(attr_lbl)

        btn.setStyleSheet(self._idle_button_css())
        btn.clicked.connect(lambda _=None, v=variant: self._pick(v))

        self._variant_buttons.append((btn, variant))
        return btn

    def _cancel_button(self) -> QPushButton:
        """Plain bottom-aligned cancel — same as UomPickerDialog."""
        btn = QPushButton("Cancel")
        if qta is not None:
            try:
                btn.setIcon(qta.icon("fa5s.times"))
            except Exception:
                pass
        btn.setFixedHeight(46)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFocusPolicy(Qt.NoFocus)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {WHITE};
                color: {MUTED};
                border: 1px solid {BORDER};
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {LIGHT};
                color: {DARK_TEXT};
            }}
        """)
        btn.clicked.connect(self.reject)
        return btn

    # -----------------------------------------------------------------------
    # Keyboard navigation (Up/Down/Enter) — same UX as UomPickerDialog
    # -----------------------------------------------------------------------

    def _refresh_active_highlight(self) -> None:
        """Paint the active row in accent-blue; the rest in the idle style."""
        for i, (btn, _v) in enumerate(self._variant_buttons):
            if i == self._active_idx:
                btn.setStyleSheet(self._active_button_css())
            else:
                btn.setStyleSheet(self._idle_button_css())

    def keyPressEvent(self, event):
        k = event.key()
        n = len(self._variant_buttons)
        if n == 0:
            return super().keyPressEvent(event)

        if k == Qt.Key_Up:
            self._active_idx = (self._active_idx - 1) % n
            self._refresh_active_highlight()
            return
        if k == Qt.Key_Down:
            self._active_idx = (self._active_idx + 1) % n
            self._refresh_active_highlight()
            return
        if k in (Qt.Key_Return, Qt.Key_Enter):
            _btn, variant = self._variant_buttons[self._active_idx]
            self._pick(variant)
            return
        super().keyPressEvent(event)

    # -----------------------------------------------------------------------
    # Styling helpers (button states)
    # -----------------------------------------------------------------------

    @staticmethod
    def _idle_button_css() -> str:
        return f"""
            QPushButton {{
                background: {LIGHT};
                border: 2px solid {BORDER};
                border-radius: 10px;
            }}
            QPushButton:hover {{
                background: {ACCENT};
                border-color: {ACCENT};
            }}
            QPushButton:hover QLabel {{ color: white; }}
            QPushButton:pressed {{
                background: {NAVY};
                border-color: {NAVY};
            }}
        """

    @staticmethod
    def _active_button_css() -> str:
        return f"""
            QPushButton {{
                background: {ACCENT};
                border: 2px solid {NAVY};
                border-radius: 10px;
            }}
            QPushButton QLabel {{ color: white; }}
        """

    # -----------------------------------------------------------------------
    # Misc helpers
    # -----------------------------------------------------------------------

    def _summarise_attributes(self, attributes_json: str) -> str:
        """
        Turn the attributes blob (JSON list of {attribute, attribute_value})
        into a short summary: "Red · M". Returns "" on any parse failure.
        We only show the *values* — the attribute names are implicit from
        the template selection.
        """
        if not attributes_json:
            return ""
        try:
            data = json.loads(attributes_json)
        except (TypeError, ValueError):
            return ""
        if not isinstance(data, list):
            return ""
        vals: list[str] = []
        for row in data:
            if not isinstance(row, dict):
                continue
            v = str(row.get("attribute_value") or "").strip()
            if v:
                vals.append(v)
        return " · ".join(vals)

    def _pick(self, variant: dict) -> None:
        self.selected_variant = variant
        log.info("Variant picked: %s (of template %s)",
                 variant.get("part_no"), self.template.get("part_no"))
        self.accept()
