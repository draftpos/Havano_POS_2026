# # =============================================================================
# # views/dialogs/customer_dialog.py
# # =============================================================================

# from PySide6.QtWidgets import (
#     QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QWidget,
#     QPushButton, QLabel, QLineEdit, QComboBox, QTableWidget,
#     QTableWidgetItem, QHeaderView, QAbstractItemView, QMessageBox
# )
# from PySide6.QtCore import Qt, QTimer
# from PySide6.QtGui import QColor
# import threading

# # Colors
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


# def _friendly_db_error(e: Exception) -> str:
#     msg = str(e)
#     if "REFERENCE constraint" in msg or "FK_" in msg or "foreign key" in msg.lower():
#         return "Cannot delete — record is still linked to other data."
#     if "UNIQUE" in msg or "duplicate key" in msg.lower():
#         return "A record with that name already exists."
#     return msg


# def navy_btn(text, height=36, font_size=12, width=None, color=None, hover=None):
#     bg  = color or NAVY
#     hov = hover or NAVY_2
#     btn = QPushButton(text)
#     btn.setFixedHeight(height)
#     if width:
#         btn.setFixedWidth(width)
#     btn.setCursor(Qt.PointingHandCursor)
#     btn.setStyleSheet(f"""
#         QPushButton {{
#             background-color: {bg}; color: {WHITE}; border: none;
#             border-radius: 5px; font-size: {font_size}px; font-weight: bold; padding: 0 14px;
#         }}
#         QPushButton:hover   {{ background-color: {hov}; }}
#         QPushButton:pressed {{ background-color: {NAVY_3}; }}
#         QPushButton:disabled {{ background-color: {MID}; }}
#     """)
#     return btn


# def hr():
#     from PySide6.QtWidgets import QFrame
#     line = QFrame()
#     line.setFrameShape(QFrame.HLine)
#     line.setStyleSheet(f"background-color: {BORDER}; border: none;")
#     line.setFixedHeight(1)
#     return line


# def _settings_table_style():
#     return f"""
#         QTableWidget {{ background:{WHITE}; border:1px solid {BORDER};
#             gridline-color:{LIGHT}; outline:none; font-size:13px; }}
#         QTableWidget::item           {{ padding:8px; }}
#         QTableWidget::item:selected  {{ background-color:{ACCENT}; color:{WHITE}; }}
#         QTableWidget::item:alternate {{ background-color:{ROW_ALT}; }}
#         QHeaderView::section {{
#             background-color:{NAVY}; color:{WHITE};
#             padding:10px 8px; border:none; border-right:1px solid {NAVY_2};
#             font-size:11px; font-weight:bold;
#         }}
#     """


# class CustomerDialog(QDialog):
#     def __init__(self, parent=None):
#         super().__init__(parent)
#         self.setWindowTitle("Customer Management")
#         self.setMinimumSize(1000, 750)
#         self.setStyleSheet(f"QDialog {{ background-color:{WHITE}; }}")
#         self._build()
#         self._reload()

#     def _build(self):
#         lay = QVBoxLayout(self)
#         lay.setSpacing(10)
#         lay.setContentsMargins(20, 16, 20, 16)

#         # --- HEADER (DARK BAR) WITH SYNC BUTTON ---
#         hdr = QWidget()
#         hdr.setFixedHeight(50)
#         hdr.setStyleSheet(f"background-color:{NAVY}; border-radius:5px;")
        
#         # Horizontal layout for inside the navy bar
#         hl = QHBoxLayout(hdr)
#         hl.setContentsMargins(16, 0, 16, 0)
        
#         title_lbl = QLabel("Customer Directory")
#         title_lbl.setStyleSheet(f"font-size:16px;font-weight:bold;color:{WHITE};background:transparent;")
#         hl.addWidget(title_lbl)
        
#         hl.addStretch() # Pushes the button to the right

#         self._sync_btn = navy_btn("Sync from Cloud", height=30, color=ACCENT, hover=ACCENT_H)
#         self._sync_btn.clicked.connect(self._on_sync_clicked)
#         hl.addWidget(self._sync_btn)
        
#         lay.addWidget(hdr)

#         # --- SEARCH ROW ---
#         sr = QHBoxLayout()
#         sr.setSpacing(8)
#         self._search = QLineEdit()
#         self._search.setPlaceholderText("Search by name, trade name, or phone...")
#         self._search.setFixedHeight(34)
#         self._search.textChanged.connect(self._do_search)
#         sr.addWidget(self._search)
#         lay.addLayout(sr)

#         # --- CUSTOMER TABLE ---
#         self._tbl = QTableWidget(0, 8)
#         self._tbl.setHorizontalHeaderLabels([
#             "Name", "Type", "Group", "Phone", "Email", "City", "Balance", "Loyalty"
#         ])
#         hh = self._tbl.horizontalHeader()
#         hh.setSectionResizeMode(0, QHeaderView.Stretch)
#         for ci in range(1, 8):
#             hh.setSectionResizeMode(ci, QHeaderView.Fixed)
#             self._tbl.setColumnWidth(ci, 100)
        
#         self._tbl.setColumnWidth(4, 150) # Email wider
#         self._tbl.verticalHeader().setVisible(False)
#         self._tbl.setAlternatingRowColors(True)
#         self._tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
#         self._tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
#         self._tbl.setStyleSheet(_settings_table_style())
#         lay.addWidget(self._tbl, 1)
        
#         lay.addWidget(hr())

#         # --- FORM FOR ADDING/EDITING ---
#         form = QGridLayout()
#         form.setSpacing(8)

#         labels = [
#             ("Name *", 0, 0), ("Type", 0, 2), ("Trade Name", 1, 0),
#             ("Phone", 1, 2), ("Email", 2, 0), ("City", 2, 2),
#             ("House No.", 3, 0), ("Group *", 3, 2), ("Warehouse *", 4, 0),
#             ("Cost Center *", 4, 2), ("Price List *", 5, 0)
#         ]

#         for text, r, c in labels:
#             lbl = QLabel(text)
#             lbl.setStyleSheet(f"background:transparent;font-size:12px;color:{MUTED};")
#             form.addWidget(lbl, r, c)

#         self._f_name = QLineEdit(); self._f_name.setFixedHeight(30)
#         form.addWidget(self._f_name, 0, 1)

#         self._f_type = QComboBox(); self._f_type.addItems(["", "Individual", "Company"])
#         self._f_type.setFixedHeight(30)
#         form.addWidget(self._f_type, 0, 3)

#         self._f_trade = QLineEdit(); self._f_trade.setFixedHeight(30)
#         form.addWidget(self._f_trade, 1, 1)

#         self._f_phone = QLineEdit(); self._f_phone.setFixedHeight(30)
#         form.addWidget(self._f_phone, 1, 3)

#         self._f_email = QLineEdit(); self._f_email.setFixedHeight(30)
#         form.addWidget(self._f_email, 2, 1)

#         self._f_city = QLineEdit(); self._f_city.setFixedHeight(30)
#         form.addWidget(self._f_city, 2, 3)

#         self._f_house = QLineEdit(); self._f_house.setFixedHeight(30)
#         form.addWidget(self._f_house, 3, 1)

#         self._f_group = QComboBox(); self._f_group.setFixedHeight(30)
#         form.addWidget(self._f_group, 3, 3)

#         self._f_wh = QComboBox(); self._f_wh.setFixedHeight(30)
#         form.addWidget(self._f_wh, 4, 1)

#         self._f_cc = QComboBox(); self._f_cc.setFixedHeight(30)
#         form.addWidget(self._f_cc, 4, 3)

#         self._f_pl = QComboBox(); self._f_pl.setFixedHeight(30)
#         form.addWidget(self._f_pl, 5, 1)

#         lay.addLayout(form)

#         # --- FOOTER BUTTON ROW ---
#         br = QHBoxLayout()
#         br.setSpacing(8)
#         self._status = QLabel("Ready")
#         self._status.setStyleSheet(f"font-size:12px;color:{MUTED};")

#         self.add_btn = navy_btn("Add Customer", height=34, color=SUCCESS, hover=SUCCESS_H)
#         self.edit_btn = navy_btn("Edit Selected", height=34, color=NAVY, hover=NAVY_2)
#         del_btn = navy_btn("Delete", height=34, color=DANGER, hover=DANGER_H)
#         cls_btn = navy_btn("Close", height=34)

#         self.add_btn.clicked.connect(self._add)
#         self.edit_btn.clicked.connect(self._edit)
#         del_btn.clicked.connect(self._delete)
#         cls_btn.clicked.connect(self.accept)

#         br.addWidget(self._status, 1)
#         br.addWidget(self.add_btn)
#         br.addWidget(self.edit_btn)
#         br.addWidget(del_btn)
#         br.addWidget(cls_btn)
#         lay.addLayout(br)

#     def _reload(self):
#         try:
#             from models.customer import get_all_customers
#             custs = get_all_customers()
#         except Exception:
#             custs = []
#         self._populate_combos()
#         self._populate_table(custs)

#     def _do_search(self, query):
#         if not query.strip():
#             self._reload()
#             return
#         try:
#             from models.customer import search_customers
#             custs = search_customers(query)
#         except Exception:
#             custs = []
#         self._populate_table(custs)

#     def _populate_table(self, custs):
#         self._tbl.setRowCount(0)
#         for c in custs:
#             r = self._tbl.rowCount()
#             self._tbl.insertRow(r)
            
#             # Logic for coloring the balance column
#             balance = float(c.get("balance") or 0)
#             balance_text = f"{balance:,.2f}"
#             balance_color = DANGER if balance > 0 else SUCCESS if balance < 0 else DARK_TEXT
            
#             points = int(c.get("loyalty_points") or 0)

#             data_map = [
#                 (c["customer_name"], Qt.AlignLeft),
#                 (c.get("customer_type") or "", Qt.AlignCenter),
#                 (c.get("customer_group_name") or "", Qt.AlignCenter),
#                 (c.get("custom_telephone_number") or "", Qt.AlignCenter),
#                 (c.get("custom_email_address") or "", Qt.AlignLeft),
#                 (c.get("custom_city") or "", Qt.AlignCenter),
#                 (balance_text, Qt.AlignRight | Qt.AlignVCenter),
#                 (str(points), Qt.AlignCenter),
#             ]

#             for col, (val, align) in enumerate(data_map):
#                 it = QTableWidgetItem(str(val))
#                 it.setTextAlignment(align)
#                 if col == 6: # Set balance color
#                     it.setForeground(QColor(balance_color))
#                 it.setData(Qt.UserRole, c) # Store full object in the first cell data
#                 self._tbl.setItem(r, col, it)
#             self._tbl.setRowHeight(r, 38)

#     def _populate_combos(self):
#         try:
#             from models.customer_group import get_all_customer_groups
#             from models.warehouse import get_all_warehouses
#             from models.cost_center import get_all_cost_centers
#             from models.price_list import get_all_price_lists
            
#             groups = get_all_customer_groups()
#             whs = get_all_warehouses()
#             ccs = get_all_cost_centers()
#             pls = get_all_price_lists()
            
#             for cb in [self._f_group, self._f_wh, self._f_cc, self._f_pl]:
#                 cb.clear()
            
#             for g in groups: self._f_group.addItem(g["name"], g["id"])
#             for w in whs: self._f_wh.addItem(w['name'], w["id"])
#             for cc in ccs: self._f_cc.addItem(cc['name'], cc["id"])
#             for pl in pls: self._f_pl.addItem(pl["name"], pl["id"])
#         except: pass

#     # --- CLOUD SYNC LOGIC ---
#     def _on_sync_clicked(self):
#         self._sync_btn.setEnabled(False)
#         self._sync_btn.setText("Syncing...")
#         self._show_status("Connecting to cloud...")
        
#         from services.customer_sync_service import sync_customers
        
#         def run_sync():
#             try:
#                 sync_customers()
#                 QTimer.singleShot(0, self._on_sync_finished)
#             except Exception as e:
#                 QTimer.singleShot(0, lambda: self._show_status(f"Sync failed: {e}", True))
#                 QTimer.singleShot(0, lambda: self._sync_btn.setEnabled(True))
#                 QTimer.singleShot(0, lambda: self._sync_btn.setText("Sync from Cloud"))

#         threading.Thread(target=run_sync, daemon=True).start()

#     def _on_sync_finished(self):
#         self._sync_btn.setEnabled(True)
#         self._sync_btn.setText("Sync from Cloud")
#         self._reload()
#         self._show_status("Sync successful.")

#     def _add(self):
#         name = self._f_name.text().strip()
#         if not name:
#             self._show_status("Name required.", True); return

#         try:
#             from models.customer import create_customer
#             create_customer(
#                 customer_name=name,
#                 customer_group_id=self._f_group.currentData(),
#                 custom_warehouse_id=self._f_wh.currentData(),
#                 custom_cost_center_id=self._f_cc.currentData(),
#                 default_price_list_id=self._f_pl.currentData(),
#                 customer_type=self._f_type.currentText(),
#                 custom_trade_name=self._f_trade.text(),
#                 custom_telephone_number=self._f_phone.text(),
#                 custom_email_address=self._f_email.text(),
#                 custom_city=self._f_city.text(),
#                 custom_house_no=self._f_house.text()
#             )
#             self._clear_form()
#             self._reload()
#             self._show_status(f"Added {name}")
#         except Exception as e:
#             self._show_status(_friendly_db_error(e), True)

#     def _edit(self):
#         row = self._tbl.currentRow()
#         if row < 0:
#             self._show_status("Select a customer.", True); return

#         c = self._tbl.item(row, 0).data(Qt.UserRole)
#         self._f_name.setText(c.get("customer_name", ""))
#         self._f_type.setCurrentText(c.get("customer_type", ""))
#         self._f_trade.setText(c.get("custom_trade_name", ""))
#         self._f_phone.setText(c.get("custom_telephone_number", ""))
#         self._f_email.setText(c.get("custom_email_address", ""))
#         self._f_city.setText(c.get("custom_city", ""))
#         self._f_house.setText(c.get("custom_house_no", ""))

#         self._set_combo_value(self._f_group, c.get("customer_group_id"))
#         self._set_combo_value(self._f_wh, c.get("custom_warehouse_id"))
#         self._set_combo_value(self._f_cc, c.get("custom_cost_center_id"))
#         self._set_combo_value(self._f_pl, c.get("default_price_list_id"))

#         self.edit_btn.setText("Update Selected")
#         self.edit_btn.clicked.disconnect()
#         self.edit_btn.clicked.connect(lambda: self._update(c["id"]))

#     def _update(self, customer_id):
#         try:
#             from models.customer import update_customer
#             update_customer(
#                 customer_id=customer_id,
#                 customer_name=self._f_name.text().strip(),
#                 customer_group_id=self._f_group.currentData(),
#                 custom_warehouse_id=self._f_wh.currentData(),
#                 custom_cost_center_id=self._f_cc.currentData(),
#                 default_price_list_id=self._f_pl.currentData(),
#                 customer_type=self._f_type.currentText(),
#                 custom_trade_name=self._f_trade.text(),
#                 custom_telephone_number=self._f_phone.text(),
#                 custom_email_address=self._f_email.text(),
#                 custom_city=self._f_city.text(),
#                 custom_house_no=self._f_house.text()
#             )
#             self._clear_form()
#             self._reload()
#             self._show_status("Updated.")
#             self._reset_edit_btn()
#         except Exception as e:
#             self._show_status(_friendly_db_error(e), True)

#     def _delete(self):
#         row = self._tbl.currentRow()
#         if row < 0: return
#         c = self._tbl.item(row, 0).data(Qt.UserRole)
#         if QMessageBox.question(self, "Delete", f"Delete {c['customer_name']}?") == QMessageBox.Yes:
#             try:
#                 from models.customer import delete_customer
#                 delete_customer(c["id"])
#                 self._reload()
#             except Exception as e:
#                 self._show_status(_friendly_db_error(e), True)

#     def _set_combo_value(self, combo, value):
#         idx = combo.findData(value)
#         if idx >= 0: combo.setCurrentIndex(idx)

#     def _clear_form(self):
#         for f in [self._f_name, self._f_trade, self._f_phone, self._f_email, self._f_city, self._f_house]:
#             f.clear()
#         self._reset_edit_btn()

#     def _reset_edit_btn(self):
#         self.edit_btn.setText("Edit Selected")
#         try: self.edit_btn.clicked.disconnect()
#         except: pass
#         self.edit_btn.clicked.connect(self._edit)

#     def _show_status(self, msg, error=False):
#         color = DANGER if error else SUCCESS
#         self._status.setStyleSheet(f"font-size:12px;color:{color};")
#         self._status.setText(msg)
#         QTimer.singleShot(4000, lambda: self._status.setText(""))# =============================================================================
# views/dialogs/credit_note_dialog.py  —  Credit Note / Return Dialog
#
# Flow:
#   1. Cashier types invoice no OR customer name  → smart autocomplete dropdown
#   2. Selected invoice loads — header shows invoice no, customer, total, date,
#      Frappe ref status
#   3. Items shown with checkboxes, return qty spinbox, reason combo
#   4. Confirm → creates credit note → emits signal so POSView loads it
#      into the main invoice table in RETURN MODE
# =============================================================================
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QFrame, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QMessageBox, QComboBox,
    QSizePolicy, QDoubleSpinBox, QListWidget, QListWidgetItem,
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui  import QColor

NAVY      = "#0d1f3c"
NAVY_2    = "#162d52"
WHITE     = "#ffffff"
OFF_WHITE = "#f5f8fc"
LIGHT     = "#e4eaf4"
BORDER    = "#c8d8ec"
DARK_TEXT = "#0d1f3c"
MUTED     = "#5a7a9a"
ACCENT    = "#1a5fb4"
ACCENT_H  = "#1c6dd0"
SUCCESS   = "#1a7a3c"
SUCCESS_H = "#1f9447"
DANGER    = "#b02020"
DANGER_H  = "#cc2828"
AMBER     = "#b7770d"
ORANGE    = "#c05a00"

REASONS = [
    "Customer Return",
    "Damaged Goods",
    "Wrong Item",
    "Overcharge",
    "Quality Issue",
    "Other",
]


class CreditNoteDialog(QDialog):
    """
    Smart credit note dialog.
    After confirmation emits credit_note_ready(cn_dict) so the caller
    (POSView / OptionsDialog) can load it into the main table in return mode.
    """

    credit_note_ready = Signal(dict)   # emits the created CN dict

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Credit Note / Return")
        self.setMinimumSize(860, 580)
        self.setModal(True)
        self.setWindowState(Qt.WindowMaximized)
        self.setStyleSheet(
            f"QDialog {{ background:{OFF_WHITE}; font-family:'Segoe UI',sans-serif; }}"
        )

        self._sale:        dict | None = None
        self._all_sales:   list[dict]  = []
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(200)      # 200 ms debounce
        self._search_timer.timeout.connect(self._run_search)

        self._build()
        self._preload_sales()

    # =========================================================================
    # Preload
    # =========================================================================

    def _preload_sales(self):
        """Load all sales once into memory for fast autocomplete."""
        try:
            from models.sale import get_all_sales
            self._all_sales = get_all_sales()
        except Exception:
            self._all_sales = []

    # =========================================================================
    # Build UI
    # =========================================================================

    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # ── header ────────────────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setFixedHeight(52)
        hdr.setStyleSheet(f"background:{WHITE}; border-bottom:2px solid {BORDER};")
        hl  = QHBoxLayout(hdr)
        hl.setContentsMargins(28, 0, 28, 0)
        title = QLabel("Credit Note / Return")
        title.setStyleSheet(
            f"color:{NAVY}; font-size:17px; font-weight:bold; background:transparent;"
        )
        sub = QLabel("Search for an invoice, select items to return, then confirm.")
        sub.setStyleSheet(f"color:{MUTED}; font-size:11px; background:transparent;")
        hl.addWidget(title)
        hl.addSpacing(16)
        hl.addWidget(sub)
        hl.addStretch()
        root.addWidget(hdr)

        # ── body ──────────────────────────────────────────────────────────────
        body = QWidget()
        body.setStyleSheet(f"background:{OFF_WHITE};")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(28, 18, 28, 18)
        bl.setSpacing(12)

        bl.addWidget(self._build_search_area())

        self._banner = self._build_banner()
        self._banner.setVisible(False)
        bl.addWidget(self._banner)

        self._items_frame = self._build_items_table()
        self._items_frame.setVisible(False)
        bl.addWidget(self._items_frame, stretch=1)

        bl.addWidget(self._build_btns())
        root.addWidget(body, stretch=1)

    # ── Search area ──────────────────────────────────────────────────────────

    def _build_search_area(self) -> QWidget:
        wrap = QWidget()
        wrap.setStyleSheet("background:transparent;")
        vl = QVBoxLayout(wrap)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(4)

        row = QHBoxLayout()
        row.setSpacing(8)

        lbl = QLabel("Invoice / Customer:")
        lbl.setFixedWidth(140)
        lbl.setStyleSheet(
            f"color:{MUTED}; font-size:11px; font-weight:bold; background:transparent;"
        )

        self._search = QLineEdit()
        self._search.setPlaceholderText(
            "Type invoice number or customer name…"
        )
        self._search.setFixedHeight(38)
        self._search.setStyleSheet(f"""
            QLineEdit {{
                background:{WHITE}; color:{DARK_TEXT};
                border:2px solid {BORDER}; border-radius:6px;
                font-size:13px; padding:0 12px;
            }}
            QLineEdit:focus {{ border:2px solid {ACCENT}; }}
        """)
        self._search.textChanged.connect(self._on_search_changed)
        self._search.returnPressed.connect(self._run_search)

        row.addWidget(lbl)
        row.addWidget(self._search, 1)
        vl.addLayout(row)

        # Autocomplete dropdown (hidden until there are results)
        self._ac_list = QListWidget()
        self._ac_list.setFixedHeight(0)        # collapsed by default
        self._ac_list.setStyleSheet(f"""
            QListWidget {{
                background:{WHITE}; border:2px solid {ACCENT};
                border-top:none; border-radius:0 0 6px 6px;
                font-size:13px; color:{DARK_TEXT}; outline:none;
            }}
            QListWidget::item           {{ padding:7px 14px; min-height:28px; }}
            QListWidget::item:selected  {{ background:{ACCENT}; color:{WHITE}; }}
            QListWidget::item:hover     {{ background:{LIGHT}; }}
        """)
        self._ac_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._ac_list.itemClicked.connect(self._on_ac_clicked)
        # Indent to align under the QLineEdit
        ac_row = QHBoxLayout()
        ac_row.setContentsMargins(148, 0, 0, 0)   # 140 label + 8 spacing
        ac_row.addWidget(self._ac_list)
        vl.addLayout(ac_row)

        return wrap

    # ── Info banner ──────────────────────────────────────────────────────────

    def _build_banner(self) -> QFrame:
        f = QFrame()
        f.setFixedHeight(58)
        f.setStyleSheet(
            f"QFrame {{ background:{WHITE}; border:1px solid {BORDER}; border-radius:8px; }}"
        )
        hl = QHBoxLayout(f)
        hl.setContentsMargins(16, 0, 16, 0)
        hl.setSpacing(28)

        self._b_inv    = self._pill("INVOICE NO")
        self._b_cust   = self._pill("CUSTOMER")
        self._b_date   = self._pill("DATE")
        self._b_total  = self._pill("TOTAL")
        self._b_status = self._pill("FRAPPE STATUS")

        for w in [self._b_inv, self._b_cust, self._b_date,
                  self._b_total, self._b_status]:
            hl.addWidget(w)
        hl.addStretch()
        return f

    def _pill(self, cap: str) -> QWidget:
        w  = QWidget(); w.setStyleSheet("background:transparent;")
        vl = QVBoxLayout(w); vl.setContentsMargins(0, 4, 0, 4); vl.setSpacing(1)
        c  = QLabel(cap)
        c.setStyleSheet(
            f"color:{MUTED}; font-size:8px; font-weight:bold;"
            f" letter-spacing:0.8px; background:transparent;"
        )
        v  = QLabel("—")
        v.setStyleSheet(
            f"color:{DARK_TEXT}; font-size:12px; font-weight:bold; background:transparent;"
        )
        vl.addWidget(c); vl.addWidget(v)
        w._val = v
        return w

    def _set_pill(self, pill: QWidget, text: str, color: str = DARK_TEXT):
        pill._val.setText(text)
        pill._val.setStyleSheet(
            f"color:{color}; font-size:12px; font-weight:bold; background:transparent;"
        )

    # ── Items table ──────────────────────────────────────────────────────────

    def _build_items_table(self) -> QFrame:
        f  = QFrame(); f.setStyleSheet("QFrame{background:transparent;}")
        vl = QVBoxLayout(f); vl.setContentsMargins(0, 0, 0, 0); vl.setSpacing(5)

        cap = QLabel("Select items and quantities to return:")
        cap.setStyleSheet(
            f"color:{MUTED}; font-size:10px; font-weight:bold;"
            f" letter-spacing:0.6px; background:transparent;"
        )
        vl.addWidget(cap)

        self._tbl = QTableWidget(0, 6)
        self._tbl.setHorizontalHeaderLabels(
            ["✓", "ITEM", "UNIT PRICE", "ORIG QTY", "RETURN QTY", "REASON"]
        )
        hh = self._tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed);  self._tbl.setColumnWidth(0, 36)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Fixed);  self._tbl.setColumnWidth(2, 100)
        hh.setSectionResizeMode(3, QHeaderView.Fixed);  self._tbl.setColumnWidth(3, 80)
        hh.setSectionResizeMode(4, QHeaderView.Fixed);  self._tbl.setColumnWidth(4, 110)
        hh.setSectionResizeMode(5, QHeaderView.Fixed);  self._tbl.setColumnWidth(5, 160)
        self._tbl.verticalHeader().setVisible(False)
        self._tbl.setAlternatingRowColors(True)
        self._tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tbl.setSelectionMode(QAbstractItemView.NoSelection)
        self._tbl.setStyleSheet(f"""
            QTableWidget {{
                background:{WHITE}; border:1px solid {BORDER};
                gridline-color:{LIGHT}; font-size:12px; outline:none;
            }}
            QTableWidget::item           {{ padding:3px 8px; }}
            QTableWidget::item:alternate {{ background:{OFF_WHITE}; }}
            QHeaderView::section {{
                background:{NAVY}; color:{WHITE};
                padding:7px; border:none;
                border-right:1px solid {NAVY_2};
                font-size:10px; font-weight:bold;
            }}
        """)
        # Check/uncheck on row click
        self._tbl.cellClicked.connect(self._on_tbl_cell_clicked)
        vl.addWidget(self._tbl, 1)
        return f

    # ── Bottom buttons ────────────────────────────────────────────────────────

    def _build_btns(self) -> QWidget:
        w  = QWidget(); w.setStyleSheet("background:transparent;")
        hl = QHBoxLayout(w); hl.setContentsMargins(0, 0, 0, 0); hl.setSpacing(10)

        bcancel = QPushButton("Cancel")
        bcancel.setFixedHeight(44); bcancel.setFixedWidth(100)
        bcancel.setCursor(Qt.PointingHandCursor)
        bcancel.setFocusPolicy(Qt.NoFocus)
        bcancel.setStyleSheet(f"""
            QPushButton {{ background:{LIGHT}; color:{DARK_TEXT};
                           border:1px solid {BORDER}; border-radius:6px;
                           font-size:13px; font-weight:bold; }}
            QPushButton:hover {{ background:{BORDER}; }}
        """)
        bcancel.clicked.connect(self.reject)

        self._btn_confirm = QPushButton("✅  Issue Credit Note")
        self._btn_confirm.setFixedHeight(44)
        self._btn_confirm.setEnabled(False)
        self._btn_confirm.setCursor(Qt.PointingHandCursor)
        self._btn_confirm.setFocusPolicy(Qt.NoFocus)
        self._btn_confirm.setStyleSheet(f"""
            QPushButton {{ background:{SUCCESS}; color:{WHITE}; border:none;
                           border-radius:6px; font-size:13px; font-weight:bold; }}
            QPushButton:hover    {{ background:{SUCCESS_H}; }}
            QPushButton:disabled {{ background:{LIGHT}; color:{MUTED}; }}
        """)
        self._btn_confirm.clicked.connect(self._confirm)

        hl.addWidget(bcancel)
        hl.addStretch()
        hl.addWidget(self._btn_confirm)
        return w

    # =========================================================================
    # Autocomplete logic
    # =========================================================================

    def _on_search_changed(self, text: str):
        self._search_timer.start()   # debounce

    def _run_search(self):
        query = self._search.text().strip().lower()
        self._ac_list.clear()

        if len(query) < 1:
            self._ac_list.setFixedHeight(0)
            return

        matches = [
            s for s in self._all_sales
            if query in (s.get("invoice_no") or "").lower()
            or query in (s.get("customer_name") or "").lower()
        ][:15]   # cap at 15 results

        if not matches:
            self._ac_list.setFixedHeight(0)
            return

        for s in matches:
            inv_no  = s.get("invoice_no", "")
            cust    = s.get("customer_name") or "Walk-in"
            total   = f"${float(s.get('total', 0)):.2f}"
            date    = s.get("invoice_date", "")
            label   = f"{inv_no}   ·   {cust}   ·   {total}   ·   {date}"
            it = QListWidgetItem(label)
            it.setData(Qt.UserRole, s)
            self._ac_list.addItem(it)

        row_h = 42
        visible = min(len(matches), 6)
        self._ac_list.setFixedHeight(visible * row_h)

    def _on_ac_clicked(self, item: QListWidgetItem):
        sale_stub = item.data(Qt.UserRole)
        self._ac_list.setFixedHeight(0)
        self._ac_list.clear()
        self._search.setText(sale_stub.get("invoice_no", ""))
        self._load_sale(sale_stub["id"])

    # =========================================================================
    # Load sale
    # =========================================================================

    def _load_sale(self, sale_id: int):
        try:
            from models.sale import get_sale_by_id
            full = get_sale_by_id(sale_id)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not load sale:\n{e}")
            return
        if not full:
            return

        self._sale = full

        # ── Banner ────────────────────────────────────────────────────────────
        frappe_ref = full.get("frappe_ref", "")
        synced     = full.get("synced", False)
        if frappe_ref:
            status_txt, status_col = frappe_ref, SUCCESS
        elif synced:
            status_txt, status_col = "Synced (no ref)", AMBER
        else:
            status_txt, status_col = "Not yet synced", AMBER

        self._set_pill(self._b_inv,    full.get("invoice_no", "—"))
        self._set_pill(self._b_cust,   full.get("customer_name") or "Walk-in")
        self._set_pill(self._b_date,   full.get("invoice_date", "—"))
        self._set_pill(self._b_total,  f"${full.get('total', 0):.2f}")
        self._set_pill(self._b_status, status_txt, status_col)
        self._banner.setVisible(True)

        # ── Items ─────────────────────────────────────────────────────────────
        self._populate_items(full.get("items", []))
        self._items_frame.setVisible(True)
        self._btn_confirm.setEnabled(True)

    # =========================================================================
    # Items table
    # =========================================================================

    def _populate_items(self, items: list[dict]):
        self._tbl.setRowCount(0)
        for item in items:
            r = self._tbl.rowCount()
            self._tbl.insertRow(r)
            self._tbl.setRowHeight(r, 40)

            # Col 0 — checkbox (checked by default)
            chk = QTableWidgetItem()
            chk.setCheckState(Qt.Checked)
            chk.setTextAlignment(Qt.AlignCenter)
            chk.setData(Qt.UserRole, item)
            self._tbl.setItem(r, 0, chk)

            # Col 1 — name
            self._tbl.setItem(r, 1, QTableWidgetItem(item.get("product_name", "")))

            # Col 2 — unit price
            pi = QTableWidgetItem(f"${float(item.get('price', 0)):.2f}")
            pi.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._tbl.setItem(r, 2, pi)

            # Col 3 — original qty
            orig_qty = float(item.get("qty", 0))
            oq = QTableWidgetItem(f"{orig_qty:.0f}")
            oq.setTextAlignment(Qt.AlignCenter)
            self._tbl.setItem(r, 3, oq)

            # Col 4 — return qty spinbox
            spin = QDoubleSpinBox()
            spin.setMinimum(0.01)
            spin.setMaximum(orig_qty)
            spin.setValue(orig_qty)
            spin.setDecimals(0)
            spin.setFixedHeight(30)
            spin.setStyleSheet(f"""
                QDoubleSpinBox {{
                    background:{WHITE}; color:{DARK_TEXT};
                    border:1px solid {BORDER}; border-radius:5px;
                    font-size:12px; padding:0 6px;
                }}
                QDoubleSpinBox:focus {{ border:1px solid {ACCENT}; }}
            """)
            self._tbl.setCellWidget(r, 4, spin)

            # Col 5 — reason combo
            combo = QComboBox()
            combo.addItems(REASONS)
            combo.setFixedHeight(30)
            combo.setStyleSheet(f"""
                QComboBox {{
                    background:{WHITE}; color:{DARK_TEXT};
                    border:1px solid {BORDER}; border-radius:5px;
                    font-size:11px; padding:0 6px;
                }}
                QComboBox::drop-down {{ border:none; }}
                QComboBox QAbstractItemView {{
                    background:{WHITE}; border:1px solid {BORDER};
                    selection-background-color:{ACCENT}; selection-color:{WHITE};
                }}
            """)
            self._tbl.setCellWidget(r, 5, combo)

    def _on_tbl_cell_clicked(self, row: int, col: int):
        """Clicking anywhere on a row toggles the checkbox."""
        chk = self._tbl.item(row, 0)
        if chk:
            new_state = Qt.Unchecked if chk.checkState() == Qt.Checked else Qt.Checked
            chk.setCheckState(new_state)

    # =========================================================================
    # Confirm
    # =========================================================================

    def _confirm(self):
        if not self._sale:
            return

        items_to_return = []
        for r in range(self._tbl.rowCount()):
            chk = self._tbl.item(r, 0)
            if not chk or chk.checkState() != Qt.Checked:
                continue
            orig_item = chk.data(Qt.UserRole)
            spin      = self._tbl.cellWidget(r, 4)
            combo     = self._tbl.cellWidget(r, 5)
            qty       = float(spin.value()) if spin else float(orig_item.get("qty", 0))
            if qty <= 0:
                continue
            price = float(orig_item.get("price", 0))
            items_to_return.append({
                **orig_item,
                "qty":    qty,
                "total":  round(qty * price, 2),
                "reason": combo.currentText() if combo else "Customer Return",
            })

        if not items_to_return:
            QMessageBox.warning(
                self, "Nothing Selected",
                "Please check at least one item and set a return quantity."
            )
            return

        total = sum(i["total"] for i in items_to_return)
        reply = QMessageBox.question(
            self, "Confirm Credit Note",
            f"Issue credit note for {len(items_to_return)} item(s)\n"
            f"Total: ${total:.2f}\n\n"
            f"Original invoice: {self._sale.get('invoice_no', '')}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            from models.credit_note import create_credit_note
            cn = create_credit_note(
                original_sale_id=self._sale["id"],
                items_to_return=items_to_return,
                currency=self._sale.get("currency", "USD"),
                customer_name=self._sale.get("customer_name", ""),
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not create credit note:\n{e}")
            return

        # Status message
        status = cn.get("cn_status", "")
        if status == "ready":
            extra = "Will be submitted to Frappe shortly."
        elif status == "pending_sync":
            extra = "Queued — will sync after the original invoice syncs."
        else:
            extra = "Recorded locally."

        QMessageBox.information(
            self, "Credit Note Issued",
            f"✅  {cn['cn_number']} created.\n{extra}"
        )

        # Emit signal so POSView can load it into the main table
        self.credit_note_ready.emit({**cn, "items_to_return": items_to_return})
        self.accept()