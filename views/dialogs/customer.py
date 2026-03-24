# """
# views/dialogs/customer_dialog.py
# ==================================
# Standalone "Add Customer" dialog  —  Point #12.

# * Matches the look and field layout of the CustomerDialog in main_window.py.
# * Calls POST /api/method/saas_api.www.api.create_customer in a background
#   thread so the UI never freezes.
# * Auto-assigns Cost Centre, Warehouse and Price List from the first available
#   entry in the local DB (nothing is hard-coded).
# * On API success the customer is also saved locally so it is immediately
#   available in CustomerSearchPopup without a manual sync.

# Used by CustomerSearchPopup._quick_add_customer():
#     from views.dialogs.customer_dialog import CustomerDialog
#     dlg = CustomerDialog(self)
#     if dlg.exec() == QDialog.Accepted:
#         self._load_all()
# """

# from __future__ import annotations

# import json
# import urllib.request
# import urllib.error
# from typing import Optional

# from PySide6.QtCore  import Qt, QThread, Signal
# from PySide6.QtWidgets import (
#     QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
#     QLabel, QLineEdit, QComboBox, QPushButton,
#     QFrame, QMessageBox, QSizePolicy,
#     QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
# )

# # ── Colour palette (mirrors main_window.py) ───────────────────────────────────
# NAVY      = "#0d1f3c"
# NAVY_2    = "#162d52"
# NAVY_3    = "#1e3d6e"
# ACCENT    = "#1a5fb4"
# ACCENT_H  = "#1c6dd0"
# WHITE     = "#ffffff"
# OFF_WHITE = "#f5f8fc"
# LIGHT     = "#e4eaf4"
# MID       = "#8fa8c8"
# DARK_TEXT = "#0d1f3c"
# MUTED     = "#5a7a9a"
# BORDER    = "#c8d8ec"
# ROW_ALT   = "#edf3fb"
# SUCCESS   = "#1a7a3c"
# SUCCESS_H = "#1f9447"
# DANGER    = "#b02020"
# DANGER_H  = "#cc2828"


# # ── Shared widget helpers (same as main_window.py) ────────────────────────────

# def _navy_btn(text: str, height: int = 34,
#               color: str = NAVY, hover: str = NAVY_2) -> QPushButton:
#     btn = QPushButton(text)
#     btn.setFixedHeight(height)
#     btn.setCursor(Qt.PointingHandCursor)
#     btn.setStyleSheet(f"""
#         QPushButton {{
#             background-color:{color}; color:{WHITE}; border:none;
#             border-radius:5px; font-size:12px; font-weight:bold; padding:0 14px;
#         }}
#         QPushButton:hover   {{ background-color:{hover}; }}
#         QPushButton:pressed {{ background-color:{NAVY_3}; }}
#         QPushButton:disabled {{ background-color:{MID}; color:rgba(255,255,255,0.5); }}
#     """)
#     return btn


# def _hr() -> QFrame:
#     line = QFrame()
#     line.setFrameShape(QFrame.HLine)
#     line.setStyleSheet(f"background-color:{BORDER}; border:none;")
#     line.setFixedHeight(1)
#     return line


# def _table_style() -> str:
#     return f"""
#         QTableWidget {{
#             background-color:{WHITE}; color:{DARK_TEXT};
#             border:1px solid {BORDER}; gridline-color:{LIGHT};
#             font-size:13px; outline:none;
#         }}
#         QTableWidget::item           {{ padding:0 8px; }}
#         QTableWidget::item:selected  {{ background-color:{ACCENT}; color:{WHITE}; }}
#         QTableWidget::item:alternate {{ background-color:{ROW_ALT}; }}
#         QHeaderView::section {{
#             background-color:#f0e8d0; color:{NAVY};
#             padding:10px 8px; border:none;
#             border-right:1px solid {BORDER};
#             font-size:11px; font-weight:bold; letter-spacing:0.5px;
#         }}
#     """


# # ── Site-config / credential helpers ─────────────────────────────────────────

# def _get_host() -> str:
#     try:
#         from services.site_config import get_host_label  # type: ignore
#         return get_host_label()
#     except Exception:
#         return "apk.havano.cloud"


# def _get_credentials() -> tuple[str, str]:
#     # Try the shared helper used by the other sync services first
#     try:
#         from services.credit_note_sync_service import _get_credentials as _c  # type: ignore
#         return _c()
#     except Exception:
#         pass
#     # Fallback: read directly from the companies table
#     try:
#         from database.db import get_connection  # type: ignore
#         conn = get_connection()
#         cur  = conn.cursor()
#         cur.execute(
#             "SELECT api_key, api_secret FROM companies "
#             "WHERE id=(SELECT MIN(id) FROM companies)"
#         )
#         row = cur.fetchone()
#         conn.close()
#         if row and row[0]:
#             return str(row[0]), str(row[1] or "")
#     except Exception:
#         pass
#     return "", ""


# # ── Background worker ─────────────────────────────────────────────────────────

# class _ApiWorker(QThread):
#     """POST to create_customer in a background thread."""

#     success = Signal(dict)
#     error   = Signal(str)

#     def __init__(self, payload: dict, parent=None):
#         super().__init__(parent)
#         self._payload = payload

#     def run(self):
#         host        = _get_host()
#         key, secret = _get_credentials()
#         url         = f"https://{host}/api/method/saas_api.www.api.create_customer"
#         body        = json.dumps(self._payload).encode("utf-8")
#         req         = urllib.request.Request(
#             url, data=body, method="POST",
#             headers={"Content-Type": "application/json"},
#         )
#         if key:
#             req.add_header("Authorization", f"token {key}:{secret}")

#         try:
#             with urllib.request.urlopen(req, timeout=20) as resp:
#                 self.success.emit(json.loads(resp.read().decode("utf-8")))
#         except urllib.error.HTTPError as exc:
#             try:
#                 raw  = exc.read().decode("utf-8")
#                 data = json.loads(raw)
#                 msg  = data.get("exc_value") or data.get("message") or raw
#             except Exception:
#                 msg = str(exc)
#             self.error.emit(f"HTTP {exc.code}: {msg}")
#         except Exception as exc:
#             self.error.emit(str(exc))


# # ── Main dialog ───────────────────────────────────────────────────────────────

# class CustomerDialog(QDialog):
#     """
#     Add-Customer dialog (standalone, opened by CustomerSearchPopup "+ New").

#     After a successful save `dlg.exec()` returns `QDialog.Accepted` and
#     `dlg.created_customer` holds the API response dict.
#     """

#     def __init__(self, parent=None):
#         super().__init__(parent)
#         self.created_customer: Optional[dict] = None
#         self._worker: Optional[_ApiWorker]    = None

#         self.setWindowTitle("Add New Customer")
#         self.setMinimumSize(860, 560)
#         self.setModal(True)
#         self.setStyleSheet(f"QDialog {{ background-color:{WHITE}; }}")
#         self._build()
#         self._populate_combos()

#     # ── Build UI ──────────────────────────────────────────────────────────────

#     def _build(self):
#         lay = QVBoxLayout(self)
#         lay.setSpacing(10)
#         lay.setContentsMargins(20, 16, 20, 16)

#         # ── Header bar ────────────────────────────────────────────────────────
#         hdr = QWidget()
#         hdr.setFixedHeight(44)
#         hdr.setStyleSheet(f"background-color:{NAVY}; border-radius:5px;")
#         hl  = QHBoxLayout(hdr)
#         hl.setContentsMargins(16, 0, 16, 0)
#         title = QLabel("Add New Customer")
#         title.setStyleSheet(
#             f"font-size:15px; font-weight:bold; color:{WHITE}; background:transparent;"
#         )
#         self._hdr_status = QLabel("")
#         self._hdr_status.setStyleSheet(
#             f"font-size:11px; color:{MID}; background:transparent;"
#         )
#         hl.addWidget(title)
#         hl.addStretch()
#         hl.addWidget(self._hdr_status)
#         lay.addWidget(hdr)

#         # ── Existing customers table ──────────────────────────────────────────
#         self._tbl = QTableWidget(0, 6)
#         self._tbl.setHorizontalHeaderLabels(
#             ["Name", "Type", "Group", "Phone", "City", "Price List"]
#         )
#         hh = self._tbl.horizontalHeader()
#         hh.setSectionResizeMode(0, QHeaderView.Stretch)
#         for ci in [1, 2, 3, 4, 5]:
#             hh.setSectionResizeMode(ci, QHeaderView.Fixed)
#             self._tbl.setColumnWidth(ci, 110)
#         self._tbl.verticalHeader().setVisible(False)
#         self._tbl.setAlternatingRowColors(True)
#         self._tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
#         self._tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
#         self._tbl.setStyleSheet(_table_style())
#         lay.addWidget(self._tbl, 1)
#         lay.addWidget(_hr())

#         # ── Form ──────────────────────────────────────────────────────────────
#         form = QGridLayout()
#         form.setSpacing(8)

#         def _le(ph: str) -> QLineEdit:
#             f = QLineEdit()
#             f.setPlaceholderText(ph)
#             f.setFixedHeight(32)
#             return f

#         def _cb() -> QComboBox:
#             c = QComboBox()
#             c.setFixedHeight(32)
#             return c

#         def _lbl(t: str) -> QLabel:
#             return QLabel(t, styleSheet="background:transparent; font-size:12px;")

#         self._f_name   = _le("Customer name *")
#         self._f_type   = _cb(); self._f_type.addItems(["", "Individual", "Company"])
#         self._f_trade  = _le("Trade name")
#         self._f_phone  = _le("Phone")
#         self._f_email  = _le("Email")
#         self._f_city   = _le("City")
#         self._f_house  = _le("House No.")
#         self._f_tin    = _le("TIN")
#         self._f_vat    = _le("VAT number")
#         self._f_addr   = _le("Address")
#         self._f_prov   = _le("Province")
#         self._f_street = _le("Street")
#         self._f_group  = _cb()
#         self._f_wh     = _cb()
#         self._f_cc     = _cb()
#         self._f_pl     = _cb()

#         # Row layout: label | field | label | field  (4 columns)
#         rows = [
#             # r   c0-label          c0-widget       c2-label           c2-widget
#             (0, "Name *",        self._f_name,   "Type",            self._f_type  ),
#             (1, "Trade Name",    self._f_trade,  "Phone",           self._f_phone ),
#             (2, "Email",         self._f_email,  "City",            self._f_city  ),
#             (3, "House No.",     self._f_house,  "Address",         self._f_addr  ),
#             (4, "Province",      self._f_prov,   "Street",          self._f_street),
#             (5, "TIN",           self._f_tin,    "VAT",             self._f_vat   ),
#             (6, "Group *",       self._f_group,  "Warehouse *",     self._f_wh    ),
#             (7, "Cost Center *", self._f_cc,     "Price List *",    self._f_pl    ),
#         ]
#         for r, l0, w0, l2, w2 in rows:
#             form.addWidget(_lbl(l0), r, 0)
#             form.addWidget(w0,       r, 1)
#             form.addWidget(_lbl(l2), r, 2)
#             form.addWidget(w2,       r, 3)

#         lay.addLayout(form)

#         # ── Bottom bar ────────────────────────────────────────────────────────
#         br = QHBoxLayout()
#         br.setSpacing(8)

#         self._status  = QLabel("")
#         self._status.setStyleSheet(
#             f"font-size:12px; color:{SUCCESS}; background:transparent;"
#         )
#         self._add_btn = _navy_btn("Add Customer", height=34, color=SUCCESS, hover=SUCCESS_H)
#         cls_btn       = _navy_btn("Close",        height=34)

#         self._add_btn.clicked.connect(self._on_add)
#         cls_btn.clicked.connect(self.reject)

#         br.addWidget(self._status, 1)
#         br.addWidget(self._add_btn)
#         br.addWidget(cls_btn)
#         lay.addLayout(br)

#     # ── Populate combos & table ───────────────────────────────────────────────

#     def _populate_combos(self):
#         try:
#             from models.customer_group import get_all_customer_groups  # type: ignore
#             from models.warehouse      import get_all_warehouses        # type: ignore
#             from models.cost_center    import get_all_cost_centers      # type: ignore
#             from models.price_list     import get_all_price_lists       # type: ignore
#             groups = get_all_customer_groups()
#             whs    = get_all_warehouses()
#             ccs    = get_all_cost_centers()
#             pls    = get_all_price_lists()
#         except Exception:
#             groups = []; whs = []; ccs = []; pls = []

#         for cb in [self._f_group, self._f_wh, self._f_cc, self._f_pl]:
#             cb.clear()

#         for g in groups:
#             self._f_group.addItem(g["name"], g["id"])
#         for w in whs:
#             self._f_wh.addItem(f"{w['name']} ({w.get('company_name', '')})", w["id"])
#         for cc in ccs:
#             self._f_cc.addItem(f"{cc['name']} ({cc.get('company_name', '')})", cc["id"])
#         for pl in pls:
#             self._f_pl.addItem(pl["name"], pl["id"])

#         self._reload_table()

#     def _reload_table(self):
#         self._tbl.setRowCount(0)
#         try:
#             from models.customer import get_all_customers  # type: ignore
#             custs = get_all_customers()
#         except Exception:
#             custs = []
#         for c in custs:
#             r = self._tbl.rowCount()
#             self._tbl.insertRow(r)
#             for col, val in enumerate([
#                 c["customer_name"],
#                 c.get("customer_type", ""),
#                 c.get("customer_group_name", ""),
#                 c.get("custom_telephone_number", ""),
#                 c.get("custom_city", ""),
#                 c.get("price_list_name", ""),
#             ]):
#                 it = QTableWidgetItem(str(val or ""))
#                 it.setData(Qt.UserRole, c)
#                 self._tbl.setItem(r, col, it)
#             self._tbl.setRowHeight(r, 32)

#     # ── Status helpers ────────────────────────────────────────────────────────

#     def _set_status(self, msg: str, color: str = DANGER):
#         self._status.setText(msg)
#         self._status.setStyleSheet(
#             f"font-size:12px; color:{color}; background:transparent;"
#         )

#     def _set_busy(self, busy: bool):
#         self._add_btn.setEnabled(not busy)
#         self._add_btn.setText("⏳  Saving…" if busy else "Add Customer")
#         self._hdr_status.setText("Connecting to cloud…" if busy else "")

#     # ── Validate & build API payload ──────────────────────────────────────────

#     def _build_payload(self) -> Optional[dict]:
#         name = self._f_name.text().strip()
#         if not name:
#             self._set_status("Customer name is required.")
#             self._f_name.setFocus()
#             return None

#         gid  = self._f_group.currentData()
#         wid  = self._f_wh.currentData()
#         ccid = self._f_cc.currentData()
#         plid = self._f_pl.currentData()

#         if not all([gid, wid, ccid, plid]):
#             self._set_status("Group, Warehouse, Cost Center and Price List are required.")
#             return None

#         # The API expects display names, not local integer IDs.
#         # Strip the " (Company)" suffix we added when populating the combos.
#         wh_name = self._f_wh.currentText().split(" (")[0]
#         cc_name = self._f_cc.currentText().split(" (")[0]
#         pl_name = self._f_pl.currentText()

#         return {
#             "customer_name":           name,
#             "custom_trade_name":       self._f_trade.text().strip(),
#             "custom_customer_tin":     self._f_tin.text().strip(),
#             "custom_customer_vat":     self._f_vat.text().strip(),
#             "custom_customer_address": self._f_addr.text().strip(),
#             "custom_telephone_number": self._f_phone.text().strip(),
#             "custom_province":         self._f_prov.text().strip(),
#             "custom_street":           self._f_street.text().strip(),
#             "custom_city":             self._f_city.text().strip(),
#             "custom_house_no":         self._f_house.text().strip(),
#             "custom_email_address":    self._f_email.text().strip(),
#             # auto-assigned defaults (names the API expects)
#             "default_price_list":  pl_name,
#             "default_cost_center": cc_name,
#             "default_warehouse":   wh_name,
#         }

#     # ── Add button ────────────────────────────────────────────────────────────

#     def _on_add(self):
#         payload = self._build_payload()
#         if payload is None:
#             return

#         self._set_busy(True)
#         self._set_status("")

#         self._worker = _ApiWorker(payload, parent=self)
#         self._worker.success.connect(self._on_api_success)
#         self._worker.error.connect(self._on_api_error)
#         self._worker.start()

#     # ── API callbacks ─────────────────────────────────────────────────────────

#     def _on_api_success(self, response: dict):
#         self._set_busy(False)

#         # Frappe wraps the created doc in  response["message"]
#         customer_data = response.get("message") or response.get("data") or response
#         if isinstance(customer_data, str):
#             customer_data = {"customer_name": customer_data}

#         self.created_customer = customer_data
#         name = customer_data.get("customer_name", self._f_name.text().strip())

#         # Save locally so the customer appears in search immediately
#         try:
#             from models.customer import create_customer  # type: ignore
#             create_customer(
#                 customer_name           = name,
#                 customer_group_id       = self._f_group.currentData(),
#                 custom_warehouse_id     = self._f_wh.currentData(),
#                 custom_cost_center_id   = self._f_cc.currentData(),
#                 default_price_list_id   = self._f_pl.currentData(),
#                 customer_type           = self._f_type.currentText() or None,
#                 custom_trade_name       = self._f_trade.text().strip(),
#                 custom_telephone_number = self._f_phone.text().strip(),
#                 custom_email_address    = self._f_email.text().strip(),
#                 custom_city             = self._f_city.text().strip(),
#                 custom_house_no         = self._f_house.text().strip(),
#             )
#         except Exception:
#             pass  # cloud record already exists; local save is best-effort

#         # Clear form fields
#         for f in [self._f_name, self._f_trade, self._f_phone, self._f_email,
#                   self._f_city, self._f_house, self._f_tin, self._f_vat,
#                   self._f_addr, self._f_prov, self._f_street]:
#             f.clear()

#         self._reload_table()
#         self._set_status(f"Customer '{name}' added.", color=SUCCESS)

#         QMessageBox.information(
#             self, "Customer Created",
#             f"✅  '{name}' has been created in the cloud and saved locally.\n"
#             "They will now appear in the customer search."
#         )
#         self.accept()

#     def _on_api_error(self, error_msg: str):
#         self._set_busy(False)
#         self._hdr_status.setText("")
#         self._set_status(f"Error: {error_msg}")
#         QMessageBox.critical(
#             self, "Could Not Create Customer",
#             f"The server returned an error:\n\n{error_msg}\n\n"
#             "Check your internet connection and API credentials\n"
#             "in Settings → Companies."
#         )

#     # ── Keyboard ──────────────────────────────────────────────────────────────

#     def keyPressEvent(self, event):
#         if event.key() in (Qt.Key_Return, Qt.Key_Enter):
#             if self._add_btn.isEnabled():
#                 self._on_add()
#         else:
#             super().keyPressEvent(event)

"""
views/dialogs/customer_dialog.py
==================================
Customer Management Dialog  —  Points #12 (Add Customer) + Offline Management.

Features:
* Add new customer with auto-assigned cost centre, warehouse, price list
* ALL fields editable (name, phone, email, TIN, VAT, city, address, etc.)
* Customer list table with EDIT and DELETE buttons per row
* Double-click row → populate form for editing
* Saves locally first (offline-safe), then syncs to cloud in background
* Edit mode: updates local DB and optionally pushes update to Frappe
* Delete: removes from local DB
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import Optional

from PySide6.QtCore  import Qt, QThread, Signal, QTimer
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QComboBox, QPushButton,
    QFrame, QMessageBox, QSizePolicy,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QScrollArea, QTabWidget,
)

# ── Colour palette (mirrors main_window.py) ───────────────────────────────────
NAVY      = "#0d1f3c"
NAVY_2    = "#162d52"
NAVY_3    = "#1e3d6e"
ACCENT    = "#1a5fb4"
ACCENT_H  = "#1c6dd0"
WHITE     = "#ffffff"
OFF_WHITE = "#f5f8fc"
LIGHT     = "#e4eaf4"
MID       = "#8fa8c8"
DARK_TEXT = "#0d1f3c"
MUTED     = "#5a7a9a"
BORDER    = "#c8d8ec"
ROW_ALT   = "#edf3fb"
SUCCESS   = "#1a7a3c"
SUCCESS_H = "#1f9447"
DANGER    = "#b02020"
DANGER_H  = "#cc2828"
AMBER     = "#b06000"
ORANGE    = "#c05a00"


# ── Shared widget helpers ─────────────────────────────────────────────────────

def _navy_btn(text: str, height: int = 34,
              color: str = NAVY, hover: str = NAVY_2,
              width: int = None) -> QPushButton:
    btn = QPushButton(text)
    btn.setFixedHeight(height)
    if width:
        btn.setFixedWidth(width)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color:{color}; color:{WHITE}; border:none;
            border-radius:5px; font-size:12px; font-weight:bold; padding:0 14px;
        }}
        QPushButton:hover   {{ background-color:{hover}; }}
        QPushButton:pressed {{ background-color:{NAVY_3}; }}
        QPushButton:disabled {{ background-color:{MID}; color:rgba(255,255,255,0.5); }}
    """)
    return btn


def _hr() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet(f"background-color:{BORDER}; border:none;")
    line.setFixedHeight(1)
    return line


def _field(label: str, placeholder: str = "", fixed_height: int = 34) -> tuple:
    """Return (QLabel, QLineEdit) styled for the form."""
    lbl = QLabel(label)
    lbl.setStyleSheet(
        f"font-size:11px; font-weight:bold; color:{MUTED}; background:transparent;"
    )
    inp = QLineEdit()
    inp.setPlaceholderText(placeholder)
    inp.setFixedHeight(fixed_height)
    inp.setStyleSheet(f"""
        QLineEdit {{
            background:{WHITE}; color:{DARK_TEXT};
            border:1px solid {BORDER}; border-radius:5px;
            font-size:13px; padding:0 10px;
        }}
        QLineEdit:focus {{ border:2px solid {ACCENT}; }}
    """)
    return lbl, inp


def _combo(label: str, fixed_height: int = 34) -> tuple:
    """Return (QLabel, QComboBox) styled for the form."""
    lbl = QLabel(label)
    lbl.setStyleSheet(
        f"font-size:11px; font-weight:bold; color:{MUTED}; background:transparent;"
    )
    cb = QComboBox()
    cb.setFixedHeight(fixed_height)
    cb.setStyleSheet(f"""
        QComboBox {{
            background:{WHITE}; color:{DARK_TEXT};
            border:1px solid {BORDER}; border-radius:5px;
            font-size:13px; padding:0 10px;
        }}
        QComboBox:focus {{ border:2px solid {ACCENT}; }}
        QComboBox::drop-down {{ border:none; width:20px; }}
        QComboBox QAbstractItemView {{
            background:{WHITE}; border:1px solid {BORDER};
            selection-background-color:{ACCENT}; selection-color:{WHITE};
        }}
    """)
    return lbl, cb


def _table_style() -> str:
    return f"""
        QTableWidget {{
            background-color:{WHITE}; color:{DARK_TEXT};
            border:1px solid {BORDER}; gridline-color:{LIGHT};
            font-size:13px; outline:none;
        }}
        QTableWidget::item           {{ padding:0 8px; }}
        QTableWidget::item:selected  {{ background-color:{ACCENT}; color:{WHITE}; }}
        QTableWidget::item:alternate {{ background-color:{ROW_ALT}; }}
        QHeaderView::section {{
            background-color:#f0e8d0; color:{NAVY};
            padding:10px 8px; border:none;
            border-right:1px solid {BORDER};
            font-size:11px; font-weight:bold; letter-spacing:0.5px;
        }}
    """


# ── Site-config / credential helpers ─────────────────────────────────────────

def _get_host() -> str:
    try:
        from services.site_config import get_host_label  # type: ignore
        return get_host_label()
    except Exception:
        return "apk.havano.cloud"


def _get_credentials() -> tuple[str, str]:
    try:
        from services.credentials import get_credentials  # type: ignore
        return get_credentials()
    except Exception:
        pass
    try:
        from services.credit_note_sync_service import _get_credentials as _c  # type: ignore
        return _c()
    except Exception:
        pass
    try:
        from database.db import get_connection  # type: ignore
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute(
            "SELECT api_key, api_secret FROM companies "
            "WHERE id=(SELECT MIN(id) FROM companies)"
        )
        row = cur.fetchone()
        conn.close()
        if row and row[0]:
            return str(row[0]), str(row[1] or "")
    except Exception:
        pass
    return "", ""


# ── Background worker ─────────────────────────────────────────────────────────

class _ApiWorker(QThread):
    """POST to create_customer or update in a background thread."""

    success = Signal(dict)
    error   = Signal(str)

    def __init__(self, payload: dict, endpoint: str = "create_customer", parent=None):
        super().__init__(parent)
        self._payload  = payload
        self._endpoint = endpoint

    def run(self):
        host        = _get_host()
        key, secret = _get_credentials()
        url         = f"https://{host}/api/method/saas_api.www.api.{self._endpoint}"
        body        = json.dumps(self._payload).encode("utf-8")
        req         = urllib.request.Request(
            url, data=body, method="POST",
            headers={"Content-Type": "application/json"},
        )
        if key:
            req.add_header("Authorization", f"token {key}:{secret}")

        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                self.success.emit(json.loads(resp.read().decode("utf-8")))
        except urllib.error.HTTPError as exc:
            try:
                raw  = exc.read().decode("utf-8")
                data = json.loads(raw)
                msg  = data.get("exc_value") or data.get("message") or raw
            except Exception:
                msg = str(exc)
            self.error.emit(f"HTTP {exc.code}: {msg}")
        except Exception as exc:
            self.error.emit(str(exc))


# ── Main dialog ───────────────────────────────────────────────────────────────

class CustomerDialog(QDialog):
    """
    Full Customer Management dialog.

    Modes:
    - Add:  blank form → saves locally + syncs to cloud
    - Edit: double-click row → form filled → "Update Customer" saves locally

    After exec() == Accepted, `dlg.created_customer` holds the saved dict.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.created_customer: Optional[dict] = None
        self._worker:          Optional[_ApiWorker] = None
        self._editing_id:      Optional[int]        = None  # None = Add mode

        self.setWindowTitle("Customer Management")
        self.setMinimumSize(1080, 680)
        self.setModal(True)
        self.setStyleSheet(f"QDialog {{ background-color:{WHITE}; }}")
        self._build()
        self._populate_combos()

    # =========================================================================
    # BUILD UI
    # =========================================================================

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(0)
        lay.setContentsMargins(0, 0, 0, 0)

        # ── Header bar ────────────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setFixedHeight(50)
        hdr.setStyleSheet(f"background-color:{NAVY};")
        hl  = QHBoxLayout(hdr)
        hl.setContentsMargins(20, 0, 20, 0); hl.setSpacing(12)

        self._mode_badge = QLabel("ADD NEW CUSTOMER")
        self._mode_badge.setStyleSheet(
            f"font-size:14px; font-weight:bold; color:{WHITE}; background:transparent;"
        )
        self._hdr_status = QLabel("")
        self._hdr_status.setStyleSheet(
            f"font-size:11px; color:{MID}; background:transparent;"
        )
        hl.addWidget(self._mode_badge)
        hl.addStretch()
        hl.addWidget(self._hdr_status)
        lay.addWidget(hdr)

        # ── Body: left form + right table ─────────────────────────────────────
        body = QWidget()
        body.setStyleSheet(f"background:{OFF_WHITE};")
        bl = QHBoxLayout(body)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(0)

        # Left panel: form
        form_panel = QWidget()
        form_panel.setFixedWidth(430)
        form_panel.setStyleSheet(f"background:{WHITE}; border-right:1px solid {BORDER};")
        fl = QVBoxLayout(form_panel)
        fl.setContentsMargins(20, 16, 20, 16)
        fl.setSpacing(10)

        form_scroll = QScrollArea()
        form_scroll.setWidgetResizable(True)
        form_scroll.setStyleSheet(f"QScrollArea {{ border:none; background:{WHITE}; }}")

        form_inner = QWidget()
        form_inner.setStyleSheet(f"background:{WHITE};")
        fi = QVBoxLayout(form_inner)
        fi.setContentsMargins(0, 0, 0, 0)
        fi.setSpacing(8)

        def _section_hdr(text):
            lbl = QLabel(text)
            lbl.setStyleSheet(
                f"font-size:10px; font-weight:bold; color:{MUTED}; background:transparent;"
                f" letter-spacing:1px; text-transform:uppercase; "
                f" border-left:3px solid {ACCENT}; padding-left:6px; margin-top:6px;"
            )
            return lbl

        def _row(*widgets):
            row = QWidget(); row.setStyleSheet("background:transparent;")
            rl  = QHBoxLayout(row); rl.setSpacing(8); rl.setContentsMargins(0, 0, 0, 0)
            for w in widgets:
                rl.addWidget(w, 1)
            return row

        def _wrap(lbl, inp):
            w = QWidget(); w.setStyleSheet("background:transparent;")
            wl = QVBoxLayout(w); wl.setSpacing(3); wl.setContentsMargins(0, 0, 0, 0)
            wl.addWidget(lbl); wl.addWidget(inp)
            return w

        # ── Section: Identity ─────────────────────────────────────────────────
        fi.addWidget(_section_hdr("Identity"))

        l1, self._f_name  = _field("Customer Name *", "Full customer name")
        l2, self._f_trade = _field("Trade Name",       "Trading / store name")
        fi.addWidget(_row(_wrap(l1, self._f_name), _wrap(l2, self._f_trade)))

        l3, self._f_type  = _combo("Type")
        self._f_type.addItems(["", "Company", "Individual"])
        l4, self._f_group = _combo("Customer Group *")
        fi.addWidget(_row(_wrap(l3, self._f_type), _wrap(l4, self._f_group)))

        # ── Section: Contact ──────────────────────────────────────────────────
        fi.addWidget(_section_hdr("Contact"))

        l5, self._f_phone = _field("Phone",  "+263 …")
        l6, self._f_email = _field("Email",  "email@example.com")
        fi.addWidget(_row(_wrap(l5, self._f_phone), _wrap(l6, self._f_email)))

        # ── Section: Address ──────────────────────────────────────────────────
        fi.addWidget(_section_hdr("Address"))

        l7, self._f_city  = _field("City",       "Harare")
        l8, self._f_prov  = _field("Province",   "Harare Province")
        fi.addWidget(_row(_wrap(l7, self._f_city), _wrap(l8, self._f_prov)))

        l9,  self._f_street = _field("Street",   "5th Ave")
        l10, self._f_house  = _field("House No.", "12")
        fi.addWidget(_row(_wrap(l9, self._f_street), _wrap(l10, self._f_house)))

        l11, self._f_addr = _field("Full Address (optional)", "Combine of above")
        fi.addWidget(_wrap(l11, self._f_addr))

        # ── Section: Tax ─────────────────────────────────────────────────────
        fi.addWidget(_section_hdr("Tax / Registration"))

        l12, self._f_tin = _field("TIN",  "Tax Identification Number")
        l13, self._f_vat = _field("VAT",  "VAT Registration Number")
        fi.addWidget(_row(_wrap(l12, self._f_tin), _wrap(l13, self._f_vat)))

        # ── Section: Defaults (auto-assigned) ─────────────────────────────────
        fi.addWidget(_section_hdr("Auto-assigned Defaults"))

        l14, self._f_wh = _combo("Warehouse *")
        l15, self._f_cc = _combo("Cost Centre *")
        fi.addWidget(_row(_wrap(l14, self._f_wh), _wrap(l15, self._f_cc)))

        l16, self._f_pl = _combo("Price List *")
        fi.addWidget(_wrap(l16, self._f_pl))

        fi.addStretch()
        form_scroll.setWidget(form_inner)
        fl.addWidget(form_scroll, 1)

        # ── Form action buttons ───────────────────────────────────────────────
        fl.addWidget(_hr())
        self._status = QLabel("")
        self._status.setStyleSheet(f"font-size:12px; color:{DANGER}; background:transparent;")
        fl.addWidget(self._status)

        btn_row = QHBoxLayout(); btn_row.setSpacing(8)
        self._save_btn  = _navy_btn("➕  Add Customer",  height=36, color=SUCCESS, hover=SUCCESS_H)
        self._clear_btn = _navy_btn("Clear Form",        height=36, color=MUTED,   hover=NAVY_2)
        self._save_btn.clicked.connect(self._on_save)
        self._clear_btn.clicked.connect(self._clear_form)
        btn_row.addWidget(self._save_btn)
        btn_row.addWidget(self._clear_btn)
        fl.addLayout(btn_row)

        bl.addWidget(form_panel)

        # Right panel: customer table
        right_panel = QWidget()
        right_panel.setStyleSheet(f"background:{OFF_WHITE};")
        rl2 = QVBoxLayout(right_panel)
        rl2.setContentsMargins(16, 14, 16, 14)
        rl2.setSpacing(8)

        # Search
        srch_row = QHBoxLayout(); srch_row.setSpacing(8)
        srch_lbl = QLabel("🔍  Search customers:")
        srch_lbl.setStyleSheet(f"color:{MUTED}; font-size:11px; background:transparent;")
        self._srch = QLineEdit()
        self._srch.setPlaceholderText("Name, phone or city…")
        self._srch.setFixedHeight(32)
        self._srch.setStyleSheet(f"""
            QLineEdit {{ background:{WHITE}; color:{DARK_TEXT};
                border:1px solid {BORDER}; border-radius:5px;
                font-size:13px; padding:0 10px; }}
            QLineEdit:focus {{ border:2px solid {ACCENT}; }}
        """)
        self._srch.textChanged.connect(self._filter_table)
        srch_row.addWidget(srch_lbl); srch_row.addWidget(self._srch, 1)
        rl2.addLayout(srch_row)

        self._count_lbl = QLabel("Loading…")
        self._count_lbl.setStyleSheet(f"color:{MUTED}; font-size:11px; background:transparent;")
        rl2.addWidget(self._count_lbl)

        # Table — 7 cols + Actions
        self._tbl = QTableWidget(0, 8)
        self._tbl.setHorizontalHeaderLabels([
            "Name", "Trade Name", "Type", "Phone", "City",
            "Price List", "Group", "Actions",
        ])
        hh = self._tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        for ci in [2, 3, 4, 5, 6]:
            hh.setSectionResizeMode(ci, QHeaderView.Fixed)
            self._tbl.setColumnWidth(ci, 100)
        hh.setSectionResizeMode(7, QHeaderView.Fixed)
        self._tbl.setColumnWidth(7, 130)
        self._tbl.verticalHeader().setVisible(False)
        self._tbl.setAlternatingRowColors(True)
        self._tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tbl.setSelectionMode(QAbstractItemView.SingleSelection)
        self._tbl.setStyleSheet(_table_style())
        self._tbl.doubleClicked.connect(self._on_row_double_clicked)
        rl2.addWidget(self._tbl, 1)

        # Bottom bar
        bb = QHBoxLayout(); bb.setSpacing(8)
        self._sync_btn = _navy_btn("☁  Sync from Cloud", height=34, color=NAVY_2, hover=NAVY_3)
        self._sync_btn.clicked.connect(self._on_sync)
        close_btn = _navy_btn("Close", height=34, color=DANGER, hover=DANGER_H)
        close_btn.clicked.connect(self.reject)
        bb.addWidget(self._sync_btn)
        bb.addStretch()
        bb.addWidget(close_btn)
        rl2.addLayout(bb)

        bl.addWidget(right_panel, 1)

        lay.addWidget(body, 1)

    # =========================================================================
    # POPULATE COMBOS & TABLE
    # =========================================================================

    def _populate_combos(self):
        try:
            from models.customer_group import get_all_customer_groups  # type: ignore
            from models.warehouse      import get_all_warehouses        # type: ignore
            from models.cost_center    import get_all_cost_centers      # type: ignore
            from models.price_list     import get_all_price_lists       # type: ignore
            groups = get_all_customer_groups()
            whs    = get_all_warehouses()
            ccs    = get_all_cost_centers()
            pls    = get_all_price_lists()
        except Exception:
            groups = []; whs = []; ccs = []; pls = []

        for cb in [self._f_group, self._f_wh, self._f_cc, self._f_pl]:
            cb.clear()

        for g in groups:
            self._f_group.addItem(g["name"], g["id"])
        for w in whs:
            self._f_wh.addItem(f"{w['name']} ({w.get('company_name', '')})", w["id"])
        for cc in ccs:
            self._f_cc.addItem(f"{cc['name']} ({cc.get('company_name', '')})", cc["id"])
        for pl in pls:
            self._f_pl.addItem(pl["name"], pl["id"])

        self._reload_table()

    # ── All customers ─────────────────────────────────────────────────────────
    def _reload_table(self):
        try:
            from models.customer import get_all_customers  # type: ignore
            self._all_customers = get_all_customers()
        except Exception:
            self._all_customers = []
        self._render_table(self._all_customers)

    def _filter_table(self, query: str):
        if not query.strip():
            self._render_table(self._all_customers)
            return
        ql = query.lower()
        filtered = [
            c for c in self._all_customers
            if ql in (c.get("customer_name", "") or "").lower()
            or ql in (c.get("custom_telephone_number", "") or "").lower()
            or ql in (c.get("custom_city", "") or "").lower()
            or ql in (c.get("custom_trade_name", "") or "").lower()
        ]
        self._render_table(filtered)

    def _render_table(self, custs: list):
        self._tbl.setRowCount(0)
        for c in custs:
            r = self._tbl.rowCount()
            self._tbl.insertRow(r)
            for col, val in enumerate([
                c.get("customer_name", ""),
                c.get("custom_trade_name", ""),
                c.get("customer_type", ""),
                c.get("custom_telephone_number", ""),
                c.get("custom_city", ""),
                c.get("price_list_name", ""),
                c.get("customer_group_name", ""),
            ]):
                it = QTableWidgetItem(str(val or ""))
                it.setData(Qt.UserRole, c)
                self._tbl.setItem(r, col, it)

            # Actions cell
            act_w = QWidget(); act_w.setStyleSheet("background:transparent;")
            act_l = QHBoxLayout(act_w); act_l.setContentsMargins(4, 2, 4, 2); act_l.setSpacing(4)
            edit_btn = QPushButton("✏  Edit")
            edit_btn.setFixedHeight(26)
            edit_btn.setCursor(Qt.PointingHandCursor)
            edit_btn.setStyleSheet(f"""
                QPushButton {{ background:{ACCENT}; color:{WHITE}; border:none;
                    border-radius:3px; font-size:11px; font-weight:bold; padding:0 8px; }}
                QPushButton:hover {{ background:{ACCENT_H}; }}
            """)
            del_btn = QPushButton("🗑")
            del_btn.setFixedHeight(26)
            del_btn.setCursor(Qt.PointingHandCursor)
            del_btn.setStyleSheet(f"""
                QPushButton {{ background:{DANGER}; color:{WHITE}; border:none;
                    border-radius:3px; font-size:11px; font-weight:bold; padding:0 8px; }}
                QPushButton:hover {{ background:{DANGER_H}; }}
            """)
            edit_btn.clicked.connect(lambda _, cust=c: self._load_into_form(cust))
            del_btn.clicked.connect(lambda _, cust=c: self._delete_customer(cust))
            act_l.addWidget(edit_btn); act_l.addWidget(del_btn)
            self._tbl.setCellWidget(r, 7, act_w)
            self._tbl.setRowHeight(r, 36)

        n = self._tbl.rowCount()
        self._count_lbl.setText(f"{n} customer{'s' if n != 1 else ''}")

    # =========================================================================
    # FORM OPERATIONS
    # =========================================================================

    def _load_into_form(self, cust: dict):
        """Load a customer dict into the form for editing."""
        self._editing_id = cust.get("id")
        self._mode_badge.setText("✏  EDIT CUSTOMER")
        self._mode_badge.setStyleSheet(
            f"font-size:14px; font-weight:bold; color:{AMBER}; background:transparent;"
        )
        self._save_btn.setText("💾  Update Customer")
        self._save_btn.setStyleSheet(self._save_btn.styleSheet().replace(SUCCESS, AMBER).replace(SUCCESS_H, ORANGE))

        self._f_name.setText(cust.get("customer_name", ""))
        self._f_trade.setText(cust.get("custom_trade_name", ""))
        self._f_phone.setText(cust.get("custom_telephone_number", ""))
        self._f_email.setText(cust.get("custom_email_address", ""))
        self._f_tin.setText(cust.get("custom_customer_tin", ""))
        self._f_vat.setText(cust.get("custom_customer_vat", ""))
        self._f_addr.setText(cust.get("custom_customer_address", ""))
        self._f_prov.setText(cust.get("custom_province", ""))
        self._f_street.setText(cust.get("custom_street", ""))
        self._f_city.setText(cust.get("custom_city", ""))
        self._f_house.setText(cust.get("custom_house_no", ""))

        # type
        idx = self._f_type.findText(cust.get("customer_type", ""))
        if idx >= 0:
            self._f_type.setCurrentIndex(idx)

        # group
        gname = cust.get("customer_group_name", "")
        for i in range(self._f_group.count()):
            if self._f_group.itemText(i) == gname:
                self._f_group.setCurrentIndex(i); break

        # warehouse, cost center, price list — best-effort by name
        wh = cust.get("custom_warehouse_name", "")
        for i in range(self._f_wh.count()):
            if self._f_wh.itemText(i).startswith(wh):
                self._f_wh.setCurrentIndex(i); break

        cc = cust.get("custom_cost_center_name", "")
        for i in range(self._f_cc.count()):
            if self._f_cc.itemText(i).startswith(cc):
                self._f_cc.setCurrentIndex(i); break

        pl = cust.get("price_list_name", "")
        for i in range(self._f_pl.count()):
            if self._f_pl.itemText(i) == pl:
                self._f_pl.setCurrentIndex(i); break

        self._set_status("Editing customer — make changes then click Update.", color=AMBER)
        self._f_name.setFocus()

    def _clear_form(self):
        """Reset form to Add mode."""
        self._editing_id = None
        self._mode_badge.setText("ADD NEW CUSTOMER")
        self._mode_badge.setStyleSheet(
            f"font-size:14px; font-weight:bold; color:{WHITE}; background:transparent;"
        )
        self._save_btn.setText("➕  Add Customer")
        self._save_btn.setStyleSheet(
            self._save_btn.styleSheet().replace(AMBER, SUCCESS).replace(ORANGE, SUCCESS_H)
        )
        for f in [self._f_name, self._f_trade, self._f_phone, self._f_email,
                  self._f_city, self._f_house, self._f_tin, self._f_vat,
                  self._f_addr, self._f_prov, self._f_street]:
            f.clear()
        self._f_type.setCurrentIndex(0)
        self._set_status("")

    def _on_row_double_clicked(self, index):
        row = index.row()
        item = self._tbl.item(row, 0)
        if item:
            self._load_into_form(item.data(Qt.UserRole))

    # =========================================================================
    # DELETE
    # =========================================================================

    def _delete_customer(self, cust: dict):
        name = cust.get("customer_name", "?")
        reply = QMessageBox.question(
            self, "Delete Customer",
            f"Delete customer '{name}' from the local database?\n\n"
            "Note: this does NOT delete them from Frappe/cloud.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            from models.customer import delete_customer  # type: ignore
            delete_customer(cust["id"])
            self._reload_table()
            self._set_status(f"'{name}' deleted locally.", color=SUCCESS)
        except Exception as e:
            QMessageBox.warning(self, "Delete Error", f"Could not delete:\n{e}")

    # =========================================================================
    # STATUS HELPERS
    # =========================================================================

    def _set_status(self, msg: str, color: str = DANGER):
        self._status.setText(msg)
        self._status.setStyleSheet(
            f"font-size:12px; color:{color}; background:transparent;"
        )

    def _set_busy(self, busy: bool):
        self._save_btn.setEnabled(not busy)
        self._save_btn.setText("⏳  Saving…" if busy else (
            "💾  Update Customer" if self._editing_id else "➕  Add Customer"
        ))
        self._hdr_status.setText("Connecting to cloud…" if busy else "")

    # =========================================================================
    # VALIDATE & BUILD PAYLOAD
    # =========================================================================

    def _build_payload(self) -> Optional[dict]:
        name = self._f_name.text().strip()
        if not name:
            self._set_status("Customer name is required.")
            self._f_name.setFocus()
            return None

        gid  = self._f_group.currentData()
        wid  = self._f_wh.currentData()
        ccid = self._f_cc.currentData()
        plid = self._f_pl.currentData()

        if not all([gid, wid, ccid, plid]):
            self._set_status("Group, Warehouse, Cost Centre and Price List are required.")
            return None

        wh_name = self._f_wh.currentText().split(" (")[0]
        cc_name = self._f_cc.currentText().split(" (")[0]
        pl_name = self._f_pl.currentText()

        return {
            "customer_name":           name,
            "custom_trade_name":       self._f_trade.text().strip(),
            "custom_customer_tin":     self._f_tin.text().strip(),
            "custom_customer_vat":     self._f_vat.text().strip(),
            "custom_customer_address": self._f_addr.text().strip(),
            "custom_telephone_number": self._f_phone.text().strip(),
            "custom_province":         self._f_prov.text().strip(),
            "custom_street":           self._f_street.text().strip(),
            "custom_city":             self._f_city.text().strip(),
            "custom_house_no":         self._f_house.text().strip(),
            "custom_email_address":    self._f_email.text().strip(),
            "default_price_list":      pl_name,
            "default_cost_center":     cc_name,
            "default_warehouse":       wh_name,
            # local IDs for DB
            "_group_id": gid,
            "_wh_id":    wid,
            "_cc_id":    ccid,
            "_pl_id":    plid,
            "_type":     self._f_type.currentText() or None,
        }

    # =========================================================================
    # SAVE / UPDATE
    # =========================================================================

    def _on_save(self):
        payload = self._build_payload()
        if payload is None:
            return

        if self._editing_id is not None:
            self._do_local_update(payload)
        else:
            self._do_add(payload)

    def _do_local_update(self, payload: dict):
        """Update existing customer in local DB only (offline-safe)."""
        try:
            from models.customer import update_customer  # type: ignore
            update_customer(
                customer_id             = self._editing_id,
                customer_name           = payload["customer_name"],
                customer_group_id       = payload["_group_id"],
                custom_warehouse_id     = payload["_wh_id"],
                custom_cost_center_id   = payload["_cc_id"],
                default_price_list_id   = payload["_pl_id"],
                customer_type           = payload["_type"],
                custom_trade_name       = payload["custom_trade_name"],
                custom_telephone_number = payload["custom_telephone_number"],
                custom_email_address    = payload["custom_email_address"],
                custom_city             = payload["custom_city"],
                custom_house_no         = payload["custom_house_no"],
                custom_customer_tin     = payload["custom_customer_tin"],
                custom_customer_vat     = payload["custom_customer_vat"],
                custom_customer_address = payload["custom_customer_address"],
                custom_province         = payload["custom_province"],
                custom_street           = payload["custom_street"],
            )
            name = payload["customer_name"]
            self._reload_table()
            self._clear_form()
            self._set_status(f"'{name}' updated locally.", color=SUCCESS)
            self.created_customer = payload
        except AttributeError:
            # models.customer.update_customer not yet implemented — graceful fallback
            self._set_status(
                "update_customer() not found in models.customer — "
                "add it to your models to enable offline edit.", color=AMBER
            )
        except Exception as e:
            self._set_status(f"Update error: {e}")

    def _do_add(self, payload: dict):
        """Save locally first, then push to cloud in background."""
        # 1. Save locally so customer is available offline immediately
        try:
            from models.customer import create_customer  # type: ignore
            create_customer(
                customer_name           = payload["customer_name"],
                customer_group_id       = payload["_group_id"],
                custom_warehouse_id     = payload["_wh_id"],
                custom_cost_center_id   = payload["_cc_id"],
                default_price_list_id   = payload["_pl_id"],
                customer_type           = payload["_type"],
                custom_trade_name       = payload["custom_trade_name"],
                custom_telephone_number = payload["custom_telephone_number"],
                custom_email_address    = payload["custom_email_address"],
                custom_city             = payload["custom_city"],
                custom_house_no         = payload["custom_house_no"],
            )
            self._reload_table()
            self._set_status(
                f"'{payload['customer_name']}' saved locally. Syncing to cloud…",
                color=SUCCESS,
            )
        except Exception as e:
            self._set_status(f"Local save error: {e}")
            # still try cloud

        # 2. Push to cloud in background thread
        self._set_busy(True)
        clean_payload = {k: v for k, v in payload.items() if not k.startswith("_")}
        self._worker = _ApiWorker(clean_payload, endpoint="create_customer", parent=self)
        self._worker.success.connect(self._on_api_success)
        self._worker.error.connect(self._on_api_error)
        self._worker.start()

    # =========================================================================
    # API CALLBACKS
    # =========================================================================

    def _on_api_success(self, response: dict):
        self._set_busy(False)
        customer_data = response.get("message") or response.get("data") or response
        if isinstance(customer_data, str):
            customer_data = {"customer_name": customer_data}
        self.created_customer = customer_data
        name = customer_data.get("customer_name", "")
        self._reload_table()
        self._clear_form()
        self._set_status(f"✅  '{name}' synced to cloud.", color=SUCCESS)

    def _on_api_error(self, error_msg: str):
        self._set_busy(False)
        self._hdr_status.setText("")
        # Don't overwrite the local-save success message aggressively
        self._set_status(
            f"Cloud sync failed (saved locally): {error_msg}", color=AMBER
        )

    # =========================================================================
    # CLOUD SYNC
    # =========================================================================

    def _on_sync(self):
        self._sync_btn.setEnabled(False)
        self._sync_btn.setText("⏳  Syncing…")
        self._hdr_status.setText("Syncing customers from cloud…")

        class _SyncThread(QThread):
            finished = Signal()
            def run(self_t):
                try:
                    from services.customer_sync_service import sync_customers  # type: ignore
                    sync_customers()
                except Exception as e:
                    pass
                self_t.finished.emit()

        self._sync_thread = _SyncThread(self)
        self._sync_thread.finished.connect(self._on_sync_done)
        self._sync_thread.start()

    def _on_sync_done(self):
        self._sync_btn.setEnabled(True)
        self._sync_btn.setText("☁  Sync from Cloud")
        self._hdr_status.setText("")
        self._reload_table()
        self._set_status("Sync complete.", color=SUCCESS)

    # =========================================================================
    # KEYBOARD
    # =========================================================================

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if self._save_btn.isEnabled():
                self._on_save()
        elif event.key() == Qt.Key_Escape:
            if self._editing_id is not None:
                self._clear_form()
            else:
                self.reject()
        else:
            super().keyPressEvent(event)