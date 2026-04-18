from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QWidget, QMessageBox,
)
from PySide6.QtCore import Qt, QTimer
import qtawesome as qta

# --- UI CONSTANTS ---
NAVY      = "#0d1f3c"
NAVY_2    = "#162d52"
WHITE     = "#ffffff"
LIGHT     = "#e4eaf4"
BORDER    = "#c8d8ec"
DARK_TEXT = "#0d1f3c"
MUTED     = "#5a7a9a"
ACCENT    = "#1a5fb4"
ACCENT_H  = "#1c6dd0"
DANGER    = "#b02020"
ORANGE    = "#c05a00"

_WALK_IN_NAMES = {"walk-in", "walk in", "walkin", "default", "cash customer", ""}

# --- HELPERS ---
def _is_walk_in(customer: dict | None) -> bool:
    if not customer:
        return True
    return (customer.get("customer_name") or "").strip().lower() in _WALK_IN_NAMES

def _item_display_name(item: dict) -> str:
    return (
        item.get("product_name") or 
        item.get("item_name") or 
        item.get("name") or 
        item.get("part_no") or 
        "—"
    )

def _lbl(text: str, style: str = "") -> QLabel:
    w = QLabel(text)
    if style:
        w.setStyleSheet(style + " background:transparent;")
    return w

def _hline() -> QFrame:
    ln = QFrame()
    ln.setFrameShape(QFrame.HLine)
    ln.setStyleSheet(f"background:{BORDER}; border:none;")
    ln.setFixedHeight(1)
    return ln

# --- MAIN DIALOG ---
class LaybyeConfirmDialog(QDialog):
    """
    Step 1 of the Laybye flow.
    Requires a real named customer — blocks walk-in.
    """

    def __init__(self, parent=None, cart_items: list = None,
                 cart_total: float = 0.0, customer: dict | None = None):
        super().__init__(parent)
        self.cart_items         = cart_items or []
        self.cart_total         = cart_total
        self.selected_customer = customer

        self.setWindowTitle("Laybye Confirmation")
        self.setFixedSize(500, 430)
        self.setModal(True)
        self.setStyleSheet(f"QDialog {{ background:{WHITE}; }} QLabel {{ background:transparent; }}")
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(0); root.setContentsMargins(0, 0, 0, 0)

        # Header: Replaced "Save Cart" with "Confirm Laybye"
        hdr = QWidget(); hdr.setStyleSheet(f"background:{ORANGE};"); hdr.setFixedHeight(56)
        hl = QHBoxLayout(hdr); hl.setContentsMargins(20, 0, 20, 0)
        _icon_lbl = QLabel()
        _icon_lbl.setPixmap(qta.icon("fa5s.clipboard", color=WHITE).pixmap(22, 22))
        _icon_lbl.setStyleSheet("background:transparent;")
        hl.addWidget(_icon_lbl)
        hl.addSpacing(8)
        hl.addWidget(_lbl("Confirm Laybye Details",
                         f"color:{WHITE}; font-size:15px; font-weight:bold;"))
        hl.addStretch()
        root.addWidget(hdr)

        body = QVBoxLayout(); body.setContentsMargins(24, 14, 24, 12); body.setSpacing(8)

        # --- Customer row ---
        cr = QHBoxLayout(); cr.setSpacing(6)
        cr.addWidget(_lbl("Customer:", f"color:{MUTED}; font-size:12px;"))
        
        cname = (self.selected_customer or {}).get("customer_name", "") if self.selected_customer else ""
        self._cust_val = QLabel(cname or "No customer selected")
        self._cust_val.setStyleSheet(
            (f"color:{DARK_TEXT}; font-size:12px; font-weight:bold;"
             if (cname and not _is_walk_in(self.selected_customer))
             else f"color:{DANGER}; font-size:12px; font-weight:bold;")
            + " background:transparent;"
        )
        cr.addWidget(self._cust_val)
        cr.addStretch()
        
        chg = QPushButton("Change…"); chg.setFixedHeight(26); chg.setCursor(Qt.PointingHandCursor)
        chg.setStyleSheet(
            f"QPushButton {{ background:{ACCENT}; color:{WHITE}; border:none;"
            f" border-radius:4px; font-size:11px; font-weight:bold; padding:0 10px; }}"
            f"QPushButton:hover {{ background:{ACCENT_H}; }}"
        )
        chg.clicked.connect(self._pick_customer)
        cr.addWidget(chg)
        body.addLayout(cr)
        body.addWidget(_hline())

        # --- Items Preview ---
        for item in self.cart_items[:6]:
            name = _item_display_name(item)
            qty  = item.get("qty", 1)
            # Support multiple price key formats
            amt  = float(
                item.get("total") or item.get("amount") or
                float(item.get("qty", 1)) * float(item.get("price", item.get("rate", 0)))
            )
            row = QHBoxLayout(); row.setSpacing(4)
            nl = QLabel(f"  {name}"); nl.setStyleSheet(f"color:{DARK_TEXT}; font-size:12px;")
            ql = QLabel(f"×{qty}");  ql.setStyleSheet(f"color:{MUTED}; font-size:11px;")
            ql.setFixedWidth(36); ql.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            al = QLabel(f"${amt:.2f}"); al.setStyleSheet(f"color:{NAVY_2}; font-size:12px; font-weight:bold;")
            al.setFixedWidth(76); al.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row.addWidget(nl, 1); row.addWidget(ql); row.addWidget(al)
            body.addLayout(row)

        if len(self.cart_items) > 6:
            body.addWidget(_lbl(f"  … and {len(self.cart_items)-6} more item(s)",
                                f"color:{MUTED}; font-size:11px;"))

        body.addWidget(_hline())

        # --- Totals ---
        tr = QHBoxLayout()
        tr.addWidget(_lbl("Laybye Total:", "font-weight:bold; font-size:13px;"))
        tr.addStretch()
        tr.addWidget(_lbl(f"USD  {self.cart_total:.2f}",
                         f"color:{NAVY_2}; font-size:16px; font-weight:bold;"
                         f" font-family:'Courier New',monospace;"))
        body.addLayout(tr)

        note = QLabel("Note: A deposit is required to activate the Laybye order. Named customers are required for tracking.")
        note.setWordWrap(True)
        note.setStyleSheet(f"color:{MUTED}; font-size:11px; background:{LIGHT};"
                           f" border-radius:5px; padding:6px 10px;")
        body.addWidget(note)
        root.addLayout(body)

        # --- Action Buttons ---
        br = QHBoxLayout(); br.setContentsMargins(20, 8, 20, 16); br.setSpacing(12)
        
        cxl = QPushButton("Cancel"); cxl.setFixedHeight(44); cxl.setCursor(Qt.PointingHandCursor)
        cxl.setStyleSheet(
            f"QPushButton {{ background:{WHITE}; color:{DARK_TEXT}; border:1px solid {BORDER};"
            f" border-radius:6px; font-size:13px; }} QPushButton:hover {{ background:{LIGHT}; }}"
        )
        cxl.clicked.connect(self.reject)
        
        self._ok = QPushButton("Confirm Laybye")
        self._ok.setIcon(qta.icon("fa5s.check", color="white"))
        self._ok.setFixedHeight(44)
        self._ok.setCursor(Qt.PointingHandCursor)
        self._ok.setStyleSheet(
            f"QPushButton {{ background:{ORANGE}; color:{WHITE}; border:none;"
            f" border-radius:6px; font-size:13px; font-weight:bold; }}"
            f"QPushButton:hover {{ background:#d96a00; }}"
        )
        self._ok.clicked.connect(self._on_confirm)
        
        br.addWidget(cxl); br.addWidget(self._ok)
        root.addLayout(br)

    def _pick_customer(self):
        """Dynamic importer for Customer Search Popup."""
        Popup = None
        for mod in ("main_window", "views.dialogs.main_window", "views.main_window"):
            try:
                import importlib
                m = importlib.import_module(mod)
                Popup = getattr(m, "CustomerSearchPopup", None)
                if Popup: break
            except Exception:
                pass

        if Popup is None:
            QMessageBox.warning(
                self, "Error",
                "Please select a customer on the main screen before continuing."
            )
            return

        dlg = Popup(self)
        if dlg.exec() == QDialog.Accepted:
            c = dlg.selected_customer
            if _is_walk_in(c):
                self._cust_val.setText("Walk-in not allowed for Laybye")
                self._cust_val.setStyleSheet(f"color:{DANGER}; font-size:12px; font-weight:bold;")
                self.selected_customer = None
            else:
                self.selected_customer = c
                self._cust_val.setText(c.get("customer_name", ""))
                self._cust_val.setStyleSheet(f"color:{DARK_TEXT}; font-size:12px; font-weight:bold;")

    def _on_confirm(self):
        if _is_walk_in(self.selected_customer):
            QMessageBox.warning(
                self, "Customer Required",
                "A Laybye must be linked to a named customer.\n\nPlease select one to continue."
            )
            return
        self.accept()

    def showEvent(self, event):
        super().showEvent(event)
        # Auto-trigger customer picker if a walk-in is currently active
        if _is_walk_in(self.selected_customer):
            QTimer.singleShot(250, self._pick_customer)