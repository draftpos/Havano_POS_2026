# # from __future__ import annotations

# # from PySide6.QtWidgets import (
# #     QDialog, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
# #     QLabel, QLineEdit, QFrame, QTableWidget, QTableWidgetItem,
# #     QHeaderView, QAbstractItemView, QMessageBox, QComboBox,
# #     QSizePolicy, QDoubleSpinBox, QListWidget, QListWidgetItem,
# # )
# # from PySide6.QtCore import Qt, Signal, QTimer
# # from PySide6.QtGui  import QColor

# # NAVY      = "#0d1f3c"
# # NAVY_2    = "#162d52"
# # WHITE     = "#ffffff"
# # OFF_WHITE = "#f5f8fc"
# # LIGHT     = "#e4eaf4"
# # BORDER    = "#c8d8ec"
# # DARK_TEXT = "#0d1f3c"
# # MUTED     = "#5a7a9a"
# # ACCENT    = "#1a5fb4"
# # ACCENT_H  = "#1c6dd0"
# # SUCCESS   = "#1a7a3c"
# # SUCCESS_H = "#1f9447"
# # DANGER    = "#b02020"
# # DANGER_H  = "#cc2828"
# # AMBER     = "#b7770d"
# # ORANGE    = "#c05a00"

# # REASONS = [
# #     "Customer Return",
# #     "Damaged Goods",
# #     "Wrong Item",
# #     "Overcharge",
# #     "Quality Issue",
# #     "Other",
# # ]


# # class CreditNoteDialog(QDialog):
# #     """
# #     Smart credit note dialog.
# #     After confirmation emits credit_note_ready(cn_dict) so the caller
# #     (POSView / OptionsDialog) can load it into the main table in return mode.
# #     """

# #     credit_note_ready = Signal(dict)   # emits the created CN dict

# #     def __init__(self, parent=None):
# #         super().__init__(parent)
# #         self.setWindowTitle("Credit Note / Return")
# #         self.setMinimumSize(860, 580)
# #         self.setModal(True)
# #         self.setWindowState(Qt.WindowMaximized)
# #         self.setStyleSheet(
# #             f"QDialog {{ background:{OFF_WHITE}; font-family:'Segoe UI',sans-serif; }}"
# #         )

# #         self._sale:        dict | None = None
# #         self._all_sales:   list[dict]  = []
# #         self._search_timer = QTimer(self)
# #         self._search_timer.setSingleShot(True)
# #         self._search_timer.setInterval(200)      # 200 ms debounce
# #         self._search_timer.timeout.connect(self._run_search)

# #         self._build()
# #         self._preload_sales()

# #     # =========================================================================
# #     # Preload
# #     # =========================================================================

# #     def _preload_sales(self):
# #         """Load all sales once into memory for fast autocomplete."""
# #         try:
# #             from models.sale import get_all_sales
# #             self._all_sales = get_all_sales()
# #         except Exception:
# #             self._all_sales = []

# #     # =========================================================================
# #     # Build UI
# #     # =========================================================================

# #     def _build(self):
# #         root = QVBoxLayout(self)
# #         root.setSpacing(0)
# #         root.setContentsMargins(0, 0, 0, 0)

# #         # ── header ────────────────────────────────────────────────────────────
# #         hdr = QWidget()
# #         hdr.setFixedHeight(52)
# #         hdr.setStyleSheet(f"background:{WHITE}; border-bottom:2px solid {BORDER};")
# #         hl  = QHBoxLayout(hdr)
# #         hl.setContentsMargins(28, 0, 28, 0)
# #         title = QLabel("Credit Note / Return")
# #         title.setStyleSheet(
# #             f"color:{NAVY}; font-size:17px; font-weight:bold; background:transparent;"
# #         )
# #         sub = QLabel("Search for an invoice, select items to return, then confirm.")
# #         sub.setStyleSheet(f"color:{MUTED}; font-size:11px; background:transparent;")
# #         hl.addWidget(title)
# #         hl.addSpacing(16)
# #         hl.addWidget(sub)
# #         hl.addStretch()
# #         root.addWidget(hdr)

# #         # ── body ──────────────────────────────────────────────────────────────
# #         body = QWidget()
# #         body.setStyleSheet(f"background:{OFF_WHITE};")
# #         bl = QVBoxLayout(body)
# #         bl.setContentsMargins(28, 18, 28, 18)
# #         bl.setSpacing(12)

# #         bl.addWidget(self._build_search_area())

# #         self._banner = self._build_banner()
# #         self._banner.setVisible(False)
# #         bl.addWidget(self._banner)

# #         self._items_frame = self._build_items_table()
# #         self._items_frame.setVisible(False)
# #         bl.addWidget(self._items_frame, stretch=1)

# #         bl.addWidget(self._build_btns())
# #         root.addWidget(body, stretch=1)

# #     # ── Search area ──────────────────────────────────────────────────────────

# #     def _build_search_area(self) -> QWidget:
# #         wrap = QWidget()
# #         wrap.setStyleSheet("background:transparent;")
# #         vl = QVBoxLayout(wrap)
# #         vl.setContentsMargins(0, 0, 0, 0)
# #         vl.setSpacing(4)

# #         row = QHBoxLayout()
# #         row.setSpacing(8)

# #         lbl = QLabel("Invoice / Customer:")
# #         lbl.setFixedWidth(140)
# #         lbl.setStyleSheet(
# #             f"color:{MUTED}; font-size:11px; font-weight:bold; background:transparent;"
# #         )

# #         self._search = QLineEdit()
# #         self._search.setPlaceholderText(
# #             "Type invoice number or customer name…"
# #         )
# #         self._search.setFixedHeight(38)
# #         self._search.setStyleSheet(f"""
# #             QLineEdit {{
# #                 background:{WHITE}; color:{DARK_TEXT};
# #                 border:2px solid {BORDER}; border-radius:6px;
# #                 font-size:13px; padding:0 12px;
# #             }}
# #             QLineEdit:focus {{ border:2px solid {ACCENT}; }}
# #         """)
# #         self._search.textChanged.connect(self._on_search_changed)
# #         self._search.returnPressed.connect(self._run_search)

# #         row.addWidget(lbl)
# #         row.addWidget(self._search, 1)
# #         vl.addLayout(row)

# #         # Autocomplete dropdown (hidden until there are results)
# #         self._ac_list = QListWidget()
# #         self._ac_list.setFixedHeight(0)        # collapsed by default
# #         self._ac_list.setStyleSheet(f"""
# #             QListWidget {{
# #                 background:{WHITE}; border:2px solid {ACCENT};
# #                 border-top:none; border-radius:0 0 6px 6px;
# #                 font-size:13px; color:{DARK_TEXT}; outline:none;
# #             }}
# #             QListWidget::item           {{ padding:7px 14px; min-height:28px; }}
# #             QListWidget::item:selected  {{ background:{ACCENT}; color:{WHITE}; }}
# #             QListWidget::item:hover     {{ background:{LIGHT}; }}
# #         """)
# #         self._ac_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
# #         self._ac_list.itemClicked.connect(self._on_ac_clicked)
# #         # Indent to align under the QLineEdit
# #         ac_row = QHBoxLayout()
# #         ac_row.setContentsMargins(148, 0, 0, 0)   # 140 label + 8 spacing
# #         ac_row.addWidget(self._ac_list)
# #         vl.addLayout(ac_row)

# #         return wrap

# #     # ── Info banner ──────────────────────────────────────────────────────────

# #     def _build_banner(self) -> QFrame:
# #         f = QFrame()
# #         f.setFixedHeight(58)
# #         f.setStyleSheet(
# #             f"QFrame {{ background:{WHITE}; border:1px solid {BORDER}; border-radius:8px; }}"
# #         )
# #         hl = QHBoxLayout(f)
# #         hl.setContentsMargins(16, 0, 16, 0)
# #         hl.setSpacing(28)

# #         self._b_inv    = self._pill("INVOICE NO")
# #         self._b_cust   = self._pill("CUSTOMER")
# #         self._b_date   = self._pill("DATE")
# #         self._b_total  = self._pill("TOTAL")
# #         self._b_status = self._pill("FRAPPE STATUS")

# #         for w in [self._b_inv, self._b_cust, self._b_date,
# #                   self._b_total, self._b_status]:
# #             hl.addWidget(w)
# #         hl.addStretch()
# #         return f

# #     def _pill(self, cap: str) -> QWidget:
# #         w  = QWidget(); w.setStyleSheet("background:transparent;")
# #         vl = QVBoxLayout(w); vl.setContentsMargins(0, 4, 0, 4); vl.setSpacing(1)
# #         c  = QLabel(cap)
# #         c.setStyleSheet(
# #             f"color:{MUTED}; font-size:8px; font-weight:bold;"
# #             f" letter-spacing:0.8px; background:transparent;"
# #         )
# #         v  = QLabel("—")
# #         v.setStyleSheet(
# #             f"color:{DARK_TEXT}; font-size:12px; font-weight:bold; background:transparent;"
# #         )
# #         vl.addWidget(c); vl.addWidget(v)
# #         w._val = v
# #         return w

# #     def _set_pill(self, pill: QWidget, text: str, color: str = DARK_TEXT):
# #         pill._val.setText(text)
# #         pill._val.setStyleSheet(
# #             f"color:{color}; font-size:12px; font-weight:bold; background:transparent;"
# #         )

# #     # ── Items table ──────────────────────────────────────────────────────────

# #     def _build_items_table(self) -> QFrame:
# #         f  = QFrame(); f.setStyleSheet("QFrame{background:transparent;}")
# #         vl = QVBoxLayout(f); vl.setContentsMargins(0, 0, 0, 0); vl.setSpacing(5)

# #         cap = QLabel("Select items and quantities to return:")
# #         cap.setStyleSheet(
# #             f"color:{MUTED}; font-size:10px; font-weight:bold;"
# #             f" letter-spacing:0.6px; background:transparent;"
# #         )
# #         vl.addWidget(cap)

# #         self._tbl = QTableWidget(0, 6)
# #         self._tbl.setHorizontalHeaderLabels(
# #             ["✓", "ITEM", "UNIT PRICE", "ORIG QTY", "RETURN QTY", "REASON"]
# #         )
# #         hh = self._tbl.horizontalHeader()
# #         hh.setSectionResizeMode(0, QHeaderView.Fixed);  self._tbl.setColumnWidth(0, 36)
# #         hh.setSectionResizeMode(1, QHeaderView.Stretch)
# #         hh.setSectionResizeMode(2, QHeaderView.Fixed);  self._tbl.setColumnWidth(2, 100)
# #         hh.setSectionResizeMode(3, QHeaderView.Fixed);  self._tbl.setColumnWidth(3, 80)
# #         hh.setSectionResizeMode(4, QHeaderView.Fixed);  self._tbl.setColumnWidth(4, 110)
# #         hh.setSectionResizeMode(5, QHeaderView.Fixed);  self._tbl.setColumnWidth(5, 160)
# #         self._tbl.verticalHeader().setVisible(False)
# #         self._tbl.setAlternatingRowColors(True)
# #         self._tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
# #         self._tbl.setSelectionMode(QAbstractItemView.NoSelection)
# #         self._tbl.setStyleSheet(f"""
# #             QTableWidget {{
# #                 background:{WHITE}; border:1px solid {BORDER};
# #                 gridline-color:{LIGHT}; font-size:12px; outline:none;
# #             }}
# #             QTableWidget::item           {{ padding:3px 8px; }}
# #             QTableWidget::item:alternate {{ background:{OFF_WHITE}; }}
# #             QHeaderView::section {{
# #                 background:{NAVY}; color:{WHITE};
# #                 padding:7px; border:none;
# #                 border-right:1px solid {NAVY_2};
# #                 font-size:10px; font-weight:bold;
# #             }}
# #         """)
# #         # Check/uncheck on row click
# #         self._tbl.cellClicked.connect(self._on_tbl_cell_clicked)
# #         vl.addWidget(self._tbl, 1)
# #         return f

# #     # ── Bottom buttons ────────────────────────────────────────────────────────

# #     def _build_btns(self) -> QWidget:
# #         w  = QWidget(); w.setStyleSheet("background:transparent;")
# #         hl = QHBoxLayout(w); hl.setContentsMargins(0, 0, 0, 0); hl.setSpacing(10)

# #         bcancel = QPushButton("Cancel")
# #         bcancel.setFixedHeight(44); bcancel.setFixedWidth(100)
# #         bcancel.setCursor(Qt.PointingHandCursor)
# #         bcancel.setFocusPolicy(Qt.NoFocus)
# #         bcancel.setStyleSheet(f"""
# #             QPushButton {{ background:{LIGHT}; color:{DARK_TEXT};
# #                            border:1px solid {BORDER}; border-radius:6px;
# #                            font-size:13px; font-weight:bold; }}
# #             QPushButton:hover {{ background:{BORDER}; }}
# #         """)
# #         bcancel.clicked.connect(self.reject)

# #         self._btn_confirm = QPushButton("✅  Issue Credit Note")
# #         self._btn_confirm.setFixedHeight(44)
# #         self._btn_confirm.setEnabled(False)
# #         self._btn_confirm.setCursor(Qt.PointingHandCursor)
# #         self._btn_confirm.setFocusPolicy(Qt.NoFocus)
# #         self._btn_confirm.setStyleSheet(f"""
# #             QPushButton {{ background:{SUCCESS}; color:{WHITE}; border:none;
# #                            border-radius:6px; font-size:13px; font-weight:bold; }}
# #             QPushButton:hover    {{ background:{SUCCESS_H}; }}
# #             QPushButton:disabled {{ background:{LIGHT}; color:{MUTED}; }}
# #         """)
# #         self._btn_confirm.clicked.connect(self._confirm)

# #         hl.addWidget(bcancel)
# #         hl.addStretch()
# #         hl.addWidget(self._btn_confirm)
# #         return w

# #     # =========================================================================
# #     # Autocomplete logic
# #     # =========================================================================

# #     def _on_search_changed(self, text: str):
# #         self._search_timer.start()   # debounce

# #     def _run_search(self):
# #         query = self._search.text().strip().lower()
# #         self._ac_list.clear()

# #         if len(query) < 1:
# #             self._ac_list.setFixedHeight(0)
# #             return

# #         matches = [
# #             s for s in self._all_sales
# #             if query in (s.get("invoice_no") or "").lower()
# #             or query in (s.get("customer_name") or "").lower()
# #         ][:15]   # cap at 15 results

# #         if not matches:
# #             self._ac_list.setFixedHeight(0)
# #             return

# #         for s in matches:
# #             inv_no  = s.get("invoice_no", "")
# #             cust    = s.get("customer_name") or "Walk-in"
# #             total   = f"${float(s.get('total', 0)):.2f}"
# #             date    = s.get("invoice_date", "")
# #             label   = f"{inv_no}   ·   {cust}   ·   {total}   ·   {date}"
# #             it = QListWidgetItem(label)
# #             it.setData(Qt.UserRole, s)
# #             self._ac_list.addItem(it)

# #         row_h = 42
# #         visible = min(len(matches), 6)
# #         self._ac_list.setFixedHeight(visible * row_h)

# #     def _on_ac_clicked(self, item: QListWidgetItem):
# #         sale_stub = item.data(Qt.UserRole)
# #         self._ac_list.setFixedHeight(0)
# #         self._ac_list.clear()
# #         self._search.setText(sale_stub.get("invoice_no", ""))
# #         self._load_sale(sale_stub["id"])

# #     # =========================================================================
# #     # Load sale
# #     # =========================================================================

# #     def _load_sale(self, sale_id: int):
# #         try:
# #             from models.sale import get_sale_by_id
# #             full = get_sale_by_id(sale_id)
# #         except Exception as e:
# #             QMessageBox.warning(self, "Error", f"Could not load sale:\n{e}")
# #             return
# #         if not full:
# #             return

# #         self._sale = full

# #         # ── Banner ────────────────────────────────────────────────────────────
# #         frappe_ref = full.get("frappe_ref", "")
# #         synced     = full.get("synced", False)
# #         if frappe_ref:
# #             status_txt, status_col = frappe_ref, SUCCESS
# #         elif synced:
# #             status_txt, status_col = "Synced (no ref)", AMBER
# #         else:
# #             status_txt, status_col = "Not yet synced", AMBER

# #         self._set_pill(self._b_inv,    full.get("invoice_no", "—"))
# #         self._set_pill(self._b_cust,   full.get("customer_name") or "Walk-in")
# #         self._set_pill(self._b_date,   full.get("invoice_date", "—"))
# #         self._set_pill(self._b_total,  f"${full.get('total', 0):.2f}")
# #         self._set_pill(self._b_status, status_txt, status_col)
# #         self._banner.setVisible(True)

# #         # ── Items ─────────────────────────────────────────────────────────────
# #         self._populate_items(full.get("items", []))
# #         self._items_frame.setVisible(True)
# #         self._btn_confirm.setEnabled(True)

# #     # =========================================================================
# #     # Items table
# #     # =========================================================================

# #     def _populate_items(self, items: list[dict]):
# #         self._tbl.setRowCount(0)
# #         for item in items:
# #             r = self._tbl.rowCount()
# #             self._tbl.insertRow(r)
# #             self._tbl.setRowHeight(r, 40)

# #             # Col 0 — checkbox (checked by default)
# #             chk = QTableWidgetItem()
# #             chk.setCheckState(Qt.Checked)
# #             chk.setTextAlignment(Qt.AlignCenter)
# #             chk.setData(Qt.UserRole, item)
# #             self._tbl.setItem(r, 0, chk)

# #             # Col 1 — name
# #             self._tbl.setItem(r, 1, QTableWidgetItem(item.get("product_name", "")))

# #             # Col 2 — unit price
# #             pi = QTableWidgetItem(f"${float(item.get('price', 0)):.2f}")
# #             pi.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
# #             self._tbl.setItem(r, 2, pi)

# #             # Col 3 — original qty
# #             orig_qty = float(item.get("qty", 0))
# #             oq = QTableWidgetItem(f"{orig_qty:.0f}")
# #             oq.setTextAlignment(Qt.AlignCenter)
# #             self._tbl.setItem(r, 3, oq)

# #             # Col 4 — return qty spinbox
# #             spin = QDoubleSpinBox()
# #             spin.setMinimum(0.01)
# #             spin.setMaximum(orig_qty)
# #             spin.setValue(orig_qty)
# #             spin.setDecimals(0)
# #             spin.setFixedHeight(30)
# #             spin.setStyleSheet(f"""
# #                 QDoubleSpinBox {{
# #                     background:{WHITE}; color:{DARK_TEXT};
# #                     border:1px solid {BORDER}; border-radius:5px;
# #                     font-size:12px; padding:0 6px;
# #                 }}
# #                 QDoubleSpinBox:focus {{ border:1px solid {ACCENT}; }}
# #             """)
# #             self._tbl.setCellWidget(r, 4, spin)

# #             # Col 5 — reason combo
# #             combo = QComboBox()
# #             combo.addItems(REASONS)
# #             combo.setFixedHeight(30)
# #             combo.setStyleSheet(f"""
# #                 QComboBox {{
# #                     background:{WHITE}; color:{DARK_TEXT};
# #                     border:1px solid {BORDER}; border-radius:5px;
# #                     font-size:11px; padding:0 6px;
# #                 }}
# #                 QComboBox::drop-down {{ border:none; }}
# #                 QComboBox QAbstractItemView {{
# #                     background:{WHITE}; border:1px solid {BORDER};
# #                     selection-background-color:{ACCENT}; selection-color:{WHITE};
# #                 }}
# #             """)
# #             self._tbl.setCellWidget(r, 5, combo)

# #     def _on_tbl_cell_clicked(self, row: int, col: int):
# #         """Clicking anywhere on a row toggles the checkbox."""
# #         chk = self._tbl.item(row, 0)
# #         if chk:
# #             new_state = Qt.Unchecked if chk.checkState() == Qt.Checked else Qt.Checked
# #             chk.setCheckState(new_state)

# #     # =========================================================================
# #     # Confirm
# #     # =========================================================================

# #     def _confirm(self):
# #         if not self._sale:
# #             return

# #         items_to_return = []
# #         for r in range(self._tbl.rowCount()):
# #             chk = self._tbl.item(r, 0)
# #             if not chk or chk.checkState() != Qt.Checked:
# #                 continue
# #             orig_item = chk.data(Qt.UserRole)
# #             spin      = self._tbl.cellWidget(r, 4)
# #             combo     = self._tbl.cellWidget(r, 5)
# #             qty       = float(spin.value()) if spin else float(orig_item.get("qty", 0))
# #             if qty <= 0:
# #                 continue
# #             price = float(orig_item.get("price", 0))
# #             items_to_return.append({
# #                 **orig_item,
# #                 "qty":    qty,
# #                 "total":  round(qty * price, 2),
# #                 "reason": combo.currentText() if combo else "Customer Return",
# #             })

# #         if not items_to_return:
# #             QMessageBox.warning(
# #                 self, "Nothing Selected",
# #                 "Please check at least one item and set a return quantity."
# #             )
# #             return

# #         total = sum(i["total"] for i in items_to_return)
# #         reply = QMessageBox.question(
# #             self, "Confirm Credit Note",
# #             f"Issue credit note for {len(items_to_return)} item(s)\n"
# #             f"Total: ${total:.2f}\n\n"
# #             f"Original invoice: {self._sale.get('invoice_no', '')}",
# #             QMessageBox.Yes | QMessageBox.No,
# #             QMessageBox.No,
# #         )
# #         if reply != QMessageBox.Yes:
# #             return

# #         try:
# #             from models.credit_note import create_credit_note
# #             cn = create_credit_note(
# #                 original_sale_id=self._sale["id"],
# #                 items_to_return=items_to_return,
# #                 currency=self._sale.get("currency", "USD"),
# #                 customer_name=self._sale.get("customer_name", ""),
# #             )
# #         except Exception as e:
# #             QMessageBox.critical(self, "Error", f"Could not create credit note:\n{e}")
# #             return

# #         # Status message
# #         status = cn.get("cn_status", "")
# #         if status == "ready":
# #             extra = "Will be submitted to Frappe shortly."
# #         elif status == "pending_sync":
# #             extra = "Queued — will sync after the original invoice syncs."
# #         else:
# #             extra = "Recorded locally."

# #         QMessageBox.information(
# #             self, "Credit Note Issued",
# #             f"✅  {cn['cn_number']} created.\n{extra}"
# #         )

# #         # Emit signal so POSView can load it into the main table
# #         self.credit_note_ready.emit({**cn, "items_to_return": items_to_return})
# #         self.accept()


# # # =============================================================================
# # # QuickAddCustomerDialog  — small "New Customer" popup launched from + New
# # # =============================================================================

# # class QuickAddCustomerDialog(QDialog):
# #     """
# #     Lightweight 3-field popup: Name · Phone · City.
# #     Everything else (warehouse, cost center, price list, group) is resolved
# #     automatically from company_defaults (the logged-in user's context).
# #     """

# #     customer_created = Signal(dict)   # emits the new customer dict on success

# #     def __init__(self, parent=None):
# #         super().__init__(parent)
# #         self.setWindowTitle("New Customer")
# #         self.setFixedWidth(400)
# #         self.setSizeGripEnabled(False)
# #         self.setModal(True)
# #         self.setStyleSheet(f"""
# #             QDialog {{
# #                 background: {WHITE};
# #                 font-family: 'Segoe UI', sans-serif;
# #             }}
# #             QLabel#section {{
# #                 color: {MUTED};
# #                 font-size: 10px;
# #                 font-weight: bold;
# #                 letter-spacing: 1px;
# #                 background: transparent;
# #             }}
# #         """)
# #         self._build()

# #     # -------------------------------------------------------------------------
# #     def _field(self, placeholder: str, required: bool = False) -> QLineEdit:
# #         le = QLineEdit()
# #         le.setPlaceholderText(placeholder + (" *" if required else ""))
# #         le.setFixedHeight(38)
# #         le.setStyleSheet(f"""
# #             QLineEdit {{
# #                 background: {OFF_WHITE};
# #                 color: {DARK_TEXT};
# #                 border: 1.5px solid {BORDER};
# #                 border-radius: 6px;
# #                 font-size: 13px;
# #                 padding: 0 10px;
# #             }}
# #             QLineEdit:focus {{ border: 1.5px solid {ACCENT}; background: {WHITE}; }}
# #         """)
# #         return le

# #     def _build(self):
# #         root = QVBoxLayout(self)
# #         root.setContentsMargins(0, 0, 0, 0)
# #         root.setSpacing(0)

# #         # ── header bar ────────────────────────────────────────────────────────
# #         hdr = QWidget()
# #         hdr.setFixedHeight(48)
# #         hdr.setStyleSheet(f"background: {NAVY}; border-radius: 0px;")
# #         hl = QHBoxLayout(hdr)
# #         hl.setContentsMargins(20, 0, 20, 0)
# #         title = QLabel("New Customer")
# #         title.setStyleSheet(
# #             f"color: {WHITE}; font-size: 15px; font-weight: bold; background: transparent;"
# #         )
# #         hl.addWidget(title)
# #         hl.addStretch()
# #         root.addWidget(hdr)

# #         # ── form body ─────────────────────────────────────────────────────────
# #         body = QWidget()
# #         body.setStyleSheet(f"background: {WHITE};")
# #         fl = QVBoxLayout(body)
# #         fl.setContentsMargins(24, 20, 24, 8)
# #         fl.setSpacing(10)

# #         self._f_first = self._field("First name", required=True)
# #         self._f_last  = self._field("Last name")
# #         self._f_phone = self._field("Phone number")
# #         self._f_city  = self._field("City")

# #         for lbl_txt, widget in [
# #             ("FIRST NAME",   self._f_first),
# #             ("LAST NAME",    self._f_last),
# #             ("PHONE NUMBER", self._f_phone),
# #             ("CITY",         self._f_city),
# #         ]:
# #             lbl = QLabel(lbl_txt)
# #             lbl.setObjectName("section")
# #             fl.addWidget(lbl)
# #             fl.addWidget(widget)

# #         # ── status label ──────────────────────────────────────────────────────
# #         self._status = QLabel("")
# #         self._status.setStyleSheet(
# #             f"color: {DANGER}; font-size: 11px; background: transparent;"
# #         )
# #         self._status.setAlignment(Qt.AlignCenter)
# #         fl.addWidget(self._status)

# #         root.addWidget(body)

# #         # ── footer buttons ────────────────────────────────────────────────────
# #         foot = QWidget()
# #         foot.setStyleSheet(
# #             f"background: {OFF_WHITE}; border-top: 1px solid {BORDER};"
# #         )
# #         bl = QHBoxLayout(foot)
# #         bl.setContentsMargins(24, 12, 24, 16)
# #         bl.setSpacing(10)

# #         cancel_btn = QPushButton("Cancel")
# #         cancel_btn.setFixedHeight(36)
# #         cancel_btn.setStyleSheet(f"""
# #             QPushButton {{
# #                 background: {WHITE}; color: {DARK_TEXT};
# #                 border: 1.5px solid {BORDER}; border-radius: 6px;
# #                 font-size: 13px; padding: 0 18px;
# #             }}
# #             QPushButton:hover {{ background: {LIGHT}; border-color: {ACCENT}; }}
# #         """)
# #         cancel_btn.clicked.connect(self.reject)

# #         self._save_btn = QPushButton("Save Customer")
# #         self._save_btn.setFixedHeight(36)
# #         self._save_btn.setStyleSheet(f"""
# #             QPushButton {{
# #                 background: {SUCCESS}; color: {WHITE};
# #                 border: none; border-radius: 6px;
# #                 font-size: 13px; font-weight: bold; padding: 0 22px;
# #             }}
# #             QPushButton:hover {{ background: {SUCCESS_H}; }}
# #             QPushButton:disabled {{ background: {BORDER}; color: {MUTED}; }}
# #         """)
# #         self._save_btn.clicked.connect(self._save)

# #         bl.addWidget(cancel_btn)
# #         bl.addStretch()
# #         bl.addWidget(self._save_btn)
# #         root.addWidget(foot)

# #         # focus the first field
# #         self._f_first.setFocus()

# #     # -------------------------------------------------------------------------
# #     def _save(self):
# #         first = self._f_first.text().strip()
# #         last  = self._f_last.text().strip()
# #         phone = self._f_phone.text().strip()
# #         city  = self._f_city.text().strip()

# #         if not first:
# #             self._status.setText("First name is required.")
# #             self._f_first.setFocus()
# #             return

# #         # Build full customer_name from first + last
# #         full_name = f"{first} {last}".strip()

# #         self._save_btn.setEnabled(False)
# #         self._status.setText("")

# #         try:
# #             print("\n" + "="*60)
# #             print("[QuickAddCustomer] Starting save...")
# #             print(f"  full_name='{full_name}'  phone='{phone}'  city='{city}'")

# #             # Try to resolve FK IDs — all are optional (tables may be empty)
# #             from models.company_defaults import get_defaults
# #             defs = get_defaults()
# #             print(f"[QuickAddCustomer] defaults: warehouse='{defs.get('server_warehouse')}'"
# #                   f"  cost_center='{defs.get('server_cost_center')}'")

# #             from database.db import get_connection
# #             conn = get_connection()
# #             cur  = conn.cursor()

# #             def _find_id(table: str, name_val: str) -> int | None:
# #                 if not name_val:
# #                     return None
# #                 cur.execute(
# #                     f"SELECT id FROM {table} WHERE LTRIM(RTRIM(name)) = ?",
# #                     (name_val.strip(),)
# #                 )
# #                 row = cur.fetchone()
# #                 if row:
# #                     print(f"  [_find_id] {table} '{name_val}' → id={row[0]}")
# #                     return row[0]
# #                 # fallback: first row
# #                 cur.execute(f"SELECT TOP 1 id, name FROM {table} ORDER BY id ASC")
# #                 fb = cur.fetchone()
# #                 print(f"  [_find_id] {table} '{name_val}' NOT FOUND → fallback={fb}")
# #                 return fb[0] if fb else None

# #             warehouse_id   = _find_id("warehouses",      defs.get("server_warehouse", ""))
# #             cost_center_id = _find_id("cost_centers",    defs.get("server_cost_center", ""))
# #             price_list_id  = _find_id("price_lists",     "Standard Selling ZWG")
# #             group_id       = _find_id("customer_groups", "All Customer Groups")
# #             conn.close()

# #             print(f"[QuickAddCustomer] IDs → warehouse={warehouse_id}  "
# #                   f"cost_center={cost_center_id}  price_list={price_list_id}  group={group_id}")

# #             # Direct INSERT — pass None for any FK that couldn't be resolved
# #             conn2 = get_connection()
# #             cur2  = conn2.cursor()
# #             cur2.execute("""
# #                 INSERT INTO customers (
# #                     customer_name, customer_group_id, customer_type,
# #                     custom_trade_name, custom_telephone_number, custom_email_address,
# #                     custom_city, custom_house_no,
# #                     custom_warehouse_id, custom_cost_center_id, default_price_list_id
# #                 ) OUTPUT INSERTED.id VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
# #             """, (
# #                 full_name, group_id, "Individual",
# #                 "", phone, "",
# #                 city, "",
# #                 warehouse_id, cost_center_id, price_list_id,
# #             ))
# #             new_id = int(cur2.fetchone()[0])
# #             conn2.commit()
# #             conn2.close()

# #             print(f"[QuickAddCustomer] SUCCESS: inserted id={new_id}  name='{full_name}'")
# #             print("="*60 + "\n")

# #             from models.customer import get_customer_by_id
# #             new_cust = get_customer_by_id(new_id) or {"id": new_id, "customer_name": full_name}
# #             self.customer_created.emit(new_cust)
# #             self.accept()

# #         except Exception as exc:
# #             import traceback
# #             print(f"[QuickAddCustomer] EXCEPTION:")
# #             traceback.print_exc()
# #             print("="*60 + "\n")
# #             self._status.setText(f"Error: {exc}")
# #             self._save_btn.setEnabled(True)
# from __future__ import annotations

# from PySide6.QtWidgets import (
#     QDialog, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
#     QLabel, QLineEdit, QFrame, QTableWidget, QTableWidgetItem,
#     QHeaderView, QAbstractItemView, QMessageBox, QComboBox,
#     QSizePolicy, QDoubleSpinBox, QListWidget, QListWidgetItem,
# )
# from PySide6.QtCore import Qt, Signal, QTimer
# from PySide6.QtGui  import QColor

# NAVY      = "#0d1f3c"
# NAVY_2    = "#162d52"
# WHITE     = "#ffffff"
# OFF_WHITE = "#f5f8fc"
# LIGHT     = "#e4eaf4"
# BORDER    = "#c8d8ec"
# DARK_TEXT = "#0d1f3c"
# MUTED     = "#5a7a9a"
# ACCENT    = "#1a5fb4"
# ACCENT_H  = "#1c6dd0"
# SUCCESS   = "#1a7a3c"
# SUCCESS_H = "#1f9447"
# DANGER    = "#b02020"
# DANGER_H  = "#cc2828"
# AMBER     = "#b7770d"
# ORANGE    = "#c05a00"

# REASONS = [
#     "Customer Return",
#     "Damaged Goods",
#     "Wrong Item",
#     "Overcharge",
#     "Quality Issue",
#     "Other",
# ]


# class CreditNoteDialog(QDialog):
#     """
#     Smart credit note dialog.
#     After confirmation emits credit_note_ready(cn_dict) so the caller
#     (POSView / OptionsDialog) can load it into the main table in return mode.
#     """

#     credit_note_ready = Signal(dict)   # emits the created CN dict

#     def __init__(self, parent=None):
#         super().__init__(parent)
#         self.setWindowTitle("Credit Note / Return")
#         self.setMinimumSize(860, 580)
#         self.setModal(True)
#         self.setWindowState(Qt.WindowMaximized)
#         self.setStyleSheet(
#             f"QDialog {{ background:{OFF_WHITE}; font-family:'Segoe UI',sans-serif; }}"
#         )

#         self._sale:        dict | None = None
#         self._all_sales:   list[dict]  = []
#         self._search_timer = QTimer(self)
#         self._search_timer.setSingleShot(True)
#         self._search_timer.setInterval(200)      # 200 ms debounce
#         self._search_timer.timeout.connect(self._run_search)

#         self._build()
#         self._preload_sales()

#     # =========================================================================
#     # Preload
#     # =========================================================================

#     def _preload_sales(self):
#         """Load all sales once into memory for fast autocomplete."""
#         try:
#             from models.sale import get_all_sales
#             self._all_sales = get_all_sales()
#         except Exception:
#             self._all_sales = []

#     # =========================================================================
#     # Build UI
#     # =========================================================================

#     def _build(self):
#         root = QVBoxLayout(self)
#         root.setSpacing(0)
#         root.setContentsMargins(0, 0, 0, 0)

#         # ── header ────────────────────────────────────────────────────────────
#         hdr = QWidget()
#         hdr.setFixedHeight(52)
#         hdr.setStyleSheet(f"background:{WHITE}; border-bottom:2px solid {BORDER};")
#         hl  = QHBoxLayout(hdr)
#         hl.setContentsMargins(28, 0, 28, 0)
#         title = QLabel("Credit Note / Return")
#         title.setStyleSheet(
#             f"color:{NAVY}; font-size:17px; font-weight:bold; background:transparent;"
#         )
#         sub = QLabel("Search for an invoice, select items to return, then confirm.")
#         sub.setStyleSheet(f"color:{MUTED}; font-size:11px; background:transparent;")
#         hl.addWidget(title)
#         hl.addSpacing(16)
#         hl.addWidget(sub)
#         hl.addStretch()
#         root.addWidget(hdr)

#         # ── body ──────────────────────────────────────────────────────────────
#         body = QWidget()
#         body.setStyleSheet(f"background:{OFF_WHITE};")
#         bl = QVBoxLayout(body)
#         bl.setContentsMargins(28, 18, 28, 18)
#         bl.setSpacing(12)

#         bl.addWidget(self._build_search_area())

#         self._banner = self._build_banner()
#         self._banner.setVisible(False)
#         bl.addWidget(self._banner)

#         self._items_frame = self._build_items_table()
#         self._items_frame.setVisible(False)
#         bl.addWidget(self._items_frame, stretch=1)

#         bl.addWidget(self._build_btns())
#         root.addWidget(body, stretch=1)

#     # ── Search area ──────────────────────────────────────────────────────────

#     def _build_search_area(self) -> QWidget:
#         wrap = QWidget()
#         wrap.setStyleSheet("background:transparent;")
#         vl = QVBoxLayout(wrap)
#         vl.setContentsMargins(0, 0, 0, 0)
#         vl.setSpacing(4)

#         row = QHBoxLayout()
#         row.setSpacing(8)

#         lbl = QLabel("Invoice / Customer:")
#         lbl.setFixedWidth(140)
#         lbl.setStyleSheet(
#             f"color:{MUTED}; font-size:11px; font-weight:bold; background:transparent;"
#         )

#         self._search = QLineEdit()
#         self._search.setPlaceholderText(
#             "Type invoice number or customer name…"
#         )
#         self._search.setFixedHeight(38)
#         self._search.setStyleSheet(f"""
#             QLineEdit {{
#                 background:{WHITE}; color:{DARK_TEXT};
#                 border:2px solid {BORDER}; border-radius:6px;
#                 font-size:13px; padding:0 12px;
#             }}
#             QLineEdit:focus {{ border:2px solid {ACCENT}; }}
#         """)
#         self._search.textChanged.connect(self._on_search_changed)
#         self._search.returnPressed.connect(self._run_search)

#         row.addWidget(lbl)
#         row.addWidget(self._search, 1)
#         vl.addLayout(row)

#         # Autocomplete dropdown (hidden until there are results)
#         self._ac_list = QListWidget()
#         self._ac_list.setFixedHeight(0)        # collapsed by default
#         self._ac_list.setStyleSheet(f"""
#             QListWidget {{
#                 background:{WHITE}; border:2px solid {ACCENT};
#                 border-top:none; border-radius:0 0 6px 6px;
#                 font-size:13px; color:{DARK_TEXT}; outline:none;
#             }}
#             QListWidget::item           {{ padding:7px 14px; min-height:28px; }}
#             QListWidget::item:selected  {{ background:{ACCENT}; color:{WHITE}; }}
#             QListWidget::item:hover     {{ background:{LIGHT}; }}
#         """)
#         self._ac_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
#         self._ac_list.itemClicked.connect(self._on_ac_clicked)
#         # Indent to align under the QLineEdit
#         ac_row = QHBoxLayout()
#         ac_row.setContentsMargins(148, 0, 0, 0)   # 140 label + 8 spacing
#         ac_row.addWidget(self._ac_list)
#         vl.addLayout(ac_row)

#         return wrap

#     # ── Info banner ──────────────────────────────────────────────────────────

#     def _build_banner(self) -> QFrame:
#         f = QFrame()
#         f.setFixedHeight(58)
#         f.setStyleSheet(
#             f"QFrame {{ background:{WHITE}; border:1px solid {BORDER}; border-radius:8px; }}"
#         )
#         hl = QHBoxLayout(f)
#         hl.setContentsMargins(16, 0, 16, 0)
#         hl.setSpacing(28)

#         self._b_inv    = self._pill("INVOICE NO")
#         self._b_cust   = self._pill("CUSTOMER")
#         self._b_date   = self._pill("DATE")
#         self._b_total  = self._pill("TOTAL")
#         self._b_status = self._pill("FRAPPE STATUS")

#         for w in [self._b_inv, self._b_cust, self._b_date,
#                   self._b_total, self._b_status]:
#             hl.addWidget(w)
#         hl.addStretch()
#         return f

#     def _pill(self, cap: str) -> QWidget:
#         w  = QWidget(); w.setStyleSheet("background:transparent;")
#         vl = QVBoxLayout(w); vl.setContentsMargins(0, 4, 0, 4); vl.setSpacing(1)
#         c  = QLabel(cap)
#         c.setStyleSheet(
#             f"color:{MUTED}; font-size:8px; font-weight:bold;"
#             f" letter-spacing:0.8px; background:transparent;"
#         )
#         v  = QLabel("—")
#         v.setStyleSheet(
#             f"color:{DARK_TEXT}; font-size:12px; font-weight:bold; background:transparent;"
#         )
#         vl.addWidget(c); vl.addWidget(v)
#         w._val = v
#         return w

#     def _set_pill(self, pill: QWidget, text: str, color: str = DARK_TEXT):
#         pill._val.setText(text)
#         pill._val.setStyleSheet(
#             f"color:{color}; font-size:12px; font-weight:bold; background:transparent;"
#         )

#     # ── Items table ──────────────────────────────────────────────────────────

#     def _build_items_table(self) -> QFrame:
#         f  = QFrame(); f.setStyleSheet("QFrame{background:transparent;}")
#         vl = QVBoxLayout(f); vl.setContentsMargins(0, 0, 0, 0); vl.setSpacing(5)

#         cap = QLabel("Select items and quantities to return:")
#         cap.setStyleSheet(
#             f"color:{MUTED}; font-size:10px; font-weight:bold;"
#             f" letter-spacing:0.6px; background:transparent;"
#         )
#         vl.addWidget(cap)

#         self._tbl = QTableWidget(0, 6)
#         self._tbl.setHorizontalHeaderLabels(
#             ["✓", "ITEM", "UNIT PRICE", "ORIG QTY", "RETURN QTY", "REASON"]
#         )
#         hh = self._tbl.horizontalHeader()
#         hh.setSectionResizeMode(0, QHeaderView.Fixed);  self._tbl.setColumnWidth(0, 36)
#         hh.setSectionResizeMode(1, QHeaderView.Stretch)
#         hh.setSectionResizeMode(2, QHeaderView.Fixed);  self._tbl.setColumnWidth(2, 100)
#         hh.setSectionResizeMode(3, QHeaderView.Fixed);  self._tbl.setColumnWidth(3, 80)
#         hh.setSectionResizeMode(4, QHeaderView.Fixed);  self._tbl.setColumnWidth(4, 110)
#         hh.setSectionResizeMode(5, QHeaderView.Fixed);  self._tbl.setColumnWidth(5, 160)
#         self._tbl.verticalHeader().setVisible(False)
#         self._tbl.setAlternatingRowColors(True)
#         self._tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
#         self._tbl.setSelectionMode(QAbstractItemView.NoSelection)
#         self._tbl.setStyleSheet(f"""
#             QTableWidget {{
#                 background:{WHITE}; border:1px solid {BORDER};
#                 gridline-color:{LIGHT}; font-size:12px; outline:none;
#             }}
#             QTableWidget::item           {{ padding:3px 8px; }}
#             QTableWidget::item:alternate {{ background:{OFF_WHITE}; }}
#             QHeaderView::section {{
#                 background:{NAVY}; color:{WHITE};
#                 padding:7px; border:none;
#                 border-right:1px solid {NAVY_2};
#                 font-size:10px; font-weight:bold;
#             }}
#         """)
#         # Check/uncheck on row click
#         self._tbl.cellClicked.connect(self._on_tbl_cell_clicked)
#         vl.addWidget(self._tbl, 1)
#         return f

#     # ── Bottom buttons ────────────────────────────────────────────────────────

#     def _build_btns(self) -> QWidget:
#         w  = QWidget(); w.setStyleSheet("background:transparent;")
#         hl = QHBoxLayout(w); hl.setContentsMargins(0, 0, 0, 0); hl.setSpacing(10)

#         bcancel = QPushButton("Cancel")
#         bcancel.setFixedHeight(44); bcancel.setFixedWidth(100)
#         bcancel.setCursor(Qt.PointingHandCursor)
#         bcancel.setFocusPolicy(Qt.NoFocus)
#         bcancel.setStyleSheet(f"""
#             QPushButton {{ background:{LIGHT}; color:{DARK_TEXT};
#                            border:1px solid {BORDER}; border-radius:6px;
#                            font-size:13px; font-weight:bold; }}
#             QPushButton:hover {{ background:{BORDER}; }}
#         """)
#         bcancel.clicked.connect(self.reject)

#         self._btn_confirm = QPushButton("✅  Issue Credit Note")
#         self._btn_confirm.setFixedHeight(44)
#         self._btn_confirm.setEnabled(False)
#         self._btn_confirm.setCursor(Qt.PointingHandCursor)
#         self._btn_confirm.setFocusPolicy(Qt.NoFocus)
#         self._btn_confirm.setStyleSheet(f"""
#             QPushButton {{ background:{SUCCESS}; color:{WHITE}; border:none;
#                            border-radius:6px; font-size:13px; font-weight:bold; }}
#             QPushButton:hover    {{ background:{SUCCESS_H}; }}
#             QPushButton:disabled {{ background:{LIGHT}; color:{MUTED}; }}
#         """)
#         self._btn_confirm.clicked.connect(self._confirm)

#         hl.addWidget(bcancel)
#         hl.addStretch()
#         hl.addWidget(self._btn_confirm)
#         return w

#     # =========================================================================
#     # Autocomplete logic
#     # =========================================================================

#     def _on_search_changed(self, text: str):
#         self._search_timer.start()   # debounce

#     def _run_search(self):
#         query = self._search.text().strip().lower()
#         self._ac_list.clear()

#         if len(query) < 1:
#             self._ac_list.setFixedHeight(0)
#             return

#         matches = [
#             s for s in self._all_sales
#             if query in (s.get("invoice_no") or "").lower()
#             or query in (s.get("customer_name") or "").lower()
#         ][:15]   # cap at 15 results

#         if not matches:
#             self._ac_list.setFixedHeight(0)
#             return

#         for s in matches:
#             inv_no  = s.get("invoice_no", "")
#             cust    = s.get("customer_name") or "Walk-in"
#             total   = f"${float(s.get('total', 0)):.2f}"
#             date    = s.get("invoice_date", "")
#             label   = f"{inv_no}   ·   {cust}   ·   {total}   ·   {date}"
#             it = QListWidgetItem(label)
#             it.setData(Qt.UserRole, s)
#             self._ac_list.addItem(it)

#         row_h = 42
#         visible = min(len(matches), 6)
#         self._ac_list.setFixedHeight(visible * row_h)

#     def _on_ac_clicked(self, item: QListWidgetItem):
#         sale_stub = item.data(Qt.UserRole)
#         self._ac_list.setFixedHeight(0)
#         self._ac_list.clear()
#         self._search.setText(sale_stub.get("invoice_no", ""))
#         self._load_sale(sale_stub["id"])

#     # =========================================================================
#     # Load sale
#     # =========================================================================

#     def _load_sale(self, sale_id: int):
#         try:
#             from models.sale import get_sale_by_id
#             full = get_sale_by_id(sale_id)
#         except Exception as e:
#             QMessageBox.warning(self, "Error", f"Could not load sale:\n{e}")
#             return
#         if not full:
#             return

#         self._sale = full

#         # ── Banner ────────────────────────────────────────────────────────────
#         frappe_ref = full.get("frappe_ref", "")
#         synced     = full.get("synced", False)
#         if frappe_ref:
#             status_txt, status_col = frappe_ref, SUCCESS
#         elif synced:
#             status_txt, status_col = "Synced (no ref)", AMBER
#         else:
#             status_txt, status_col = "Not yet synced", AMBER

#         self._set_pill(self._b_inv,    full.get("invoice_no", "—"))
#         self._set_pill(self._b_cust,   full.get("customer_name") or "Walk-in")
#         self._set_pill(self._b_date,   full.get("invoice_date", "—"))
#         self._set_pill(self._b_total,  f"${full.get('total', 0):.2f}")
#         self._set_pill(self._b_status, status_txt, status_col)
#         self._banner.setVisible(True)

#         # ── Items ─────────────────────────────────────────────────────────────
#         self._populate_items(full.get("items", []))
#         self._items_frame.setVisible(True)
#         self._btn_confirm.setEnabled(True)

#     # =========================================================================
#     # Items table
#     # =========================================================================

#     def _populate_items(self, items: list[dict]):
#         self._tbl.setRowCount(0)
#         for item in items:
#             r = self._tbl.rowCount()
#             self._tbl.insertRow(r)
#             self._tbl.setRowHeight(r, 40)

#             # Col 0 — checkbox (checked by default)
#             chk = QTableWidgetItem()
#             chk.setCheckState(Qt.Checked)
#             chk.setTextAlignment(Qt.AlignCenter)
#             chk.setData(Qt.UserRole, item)
#             self._tbl.setItem(r, 0, chk)

#             # Col 1 — name
#             self._tbl.setItem(r, 1, QTableWidgetItem(item.get("product_name", "")))

#             # Col 2 — unit price
#             pi = QTableWidgetItem(f"${float(item.get('price', 0)):.2f}")
#             pi.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
#             self._tbl.setItem(r, 2, pi)

#             # Col 3 — original qty
#             orig_qty = float(item.get("qty", 0))
#             oq = QTableWidgetItem(f"{orig_qty:.0f}")
#             oq.setTextAlignment(Qt.AlignCenter)
#             self._tbl.setItem(r, 3, oq)

#             # Col 4 — return qty spinbox
#             spin = QDoubleSpinBox()
#             spin.setMinimum(0.01)
#             spin.setMaximum(orig_qty)
#             spin.setValue(orig_qty)
#             spin.setDecimals(0)
#             spin.setFixedHeight(30)
#             spin.setStyleSheet(f"""
#                 QDoubleSpinBox {{
#                     background:{WHITE}; color:{DARK_TEXT};
#                     border:1px solid {BORDER}; border-radius:5px;
#                     font-size:12px; padding:0 6px;
#                 }}
#                 QDoubleSpinBox:focus {{ border:1px solid {ACCENT}; }}
#             """)
#             self._tbl.setCellWidget(r, 4, spin)

#             # Col 5 — reason combo
#             combo = QComboBox()
#             combo.addItems(REASONS)
#             combo.setFixedHeight(30)
#             combo.setStyleSheet(f"""
#                 QComboBox {{
#                     background:{WHITE}; color:{DARK_TEXT};
#                     border:1px solid {BORDER}; border-radius:5px;
#                     font-size:11px; padding:0 6px;
#                 }}
#                 QComboBox::drop-down {{ border:none; }}
#                 QComboBox QAbstractItemView {{
#                     background:{WHITE}; border:1px solid {BORDER};
#                     selection-background-color:{ACCENT}; selection-color:{WHITE};
#                 }}
#             """)
#             self._tbl.setCellWidget(r, 5, combo)

#     def _on_tbl_cell_clicked(self, row: int, col: int):
#         """Clicking anywhere on a row toggles the checkbox."""
#         chk = self._tbl.item(row, 0)
#         if chk:
#             new_state = Qt.Unchecked if chk.checkState() == Qt.Checked else Qt.Checked
#             chk.setCheckState(new_state)

#     # =========================================================================
#     # Confirm
#     # =========================================================================

#     def _confirm(self):
#         if not self._sale:
#             return

#         items_to_return = []
#         for r in range(self._tbl.rowCount()):
#             chk = self._tbl.item(r, 0)
#             if not chk or chk.checkState() != Qt.Checked:
#                 continue
#             orig_item = chk.data(Qt.UserRole)
#             spin      = self._tbl.cellWidget(r, 4)
#             combo     = self._tbl.cellWidget(r, 5)
#             qty       = float(spin.value()) if spin else float(orig_item.get("qty", 0))
#             if qty <= 0:
#                 continue
#             price = float(orig_item.get("price", 0))
#             items_to_return.append({
#                 **orig_item,
#                 "qty":    qty,
#                 "total":  round(qty * price, 2),
#                 "reason": combo.currentText() if combo else "Customer Return",
#             })

#         if not items_to_return:
#             QMessageBox.warning(
#                 self, "Nothing Selected",
#                 "Please check at least one item and set a return quantity."
#             )
#             return

#         total = sum(i["total"] for i in items_to_return)
#         reply = QMessageBox.question(
#             self, "Confirm Credit Note",
#             f"Issue credit note for {len(items_to_return)} item(s)\n"
#             f"Total: ${total:.2f}\n\n"
#             f"Original invoice: {self._sale.get('invoice_no', '')}",
#             QMessageBox.Yes | QMessageBox.No,
#             QMessageBox.No,
#         )
#         if reply != QMessageBox.Yes:
#             return

#         try:
#             from models.credit_note import create_credit_note
#             cn = create_credit_note(
#                 original_sale_id=self._sale["id"],
#                 items_to_return=items_to_return,
#                 currency=self._sale.get("currency", "USD"),
#                 customer_name=self._sale.get("customer_name", ""),
#             )
#         except Exception as e:
#             QMessageBox.critical(self, "Error", f"Could not create credit note:\n{e}")
#             return

#         # Status message
#         status = cn.get("cn_status", "")
#         if status == "ready":
#             extra = "Will be submitted to Frappe shortly."
#         elif status == "pending_sync":
#             extra = "Queued — will sync after the original invoice syncs."
#         else:
#             extra = "Recorded locally."

#         QMessageBox.information(
#             self, "Credit Note Issued",
#             f"✅  {cn['cn_number']} created.\n{extra}"
#         )

#         # Emit signal so POSView can load it into the main table
#         self.credit_note_ready.emit({**cn, "items_to_return": items_to_return})
#         self.accept()


# # =============================================================================
# # QuickAddCustomerDialog  — small "New Customer" popup launched from + New
# # =============================================================================

# class QuickAddCustomerDialog(QDialog):
#     """
#     Lightweight 3-field popup: Name · Phone · City.
#     Everything else (warehouse, cost center, price list, group) is resolved
#     automatically from company_defaults (the logged-in user's context).
#     """

#     customer_created = Signal(dict)   # emits the new customer dict on success

#     def __init__(self, parent=None):
#         super().__init__(parent)
#         self.setWindowTitle("New Customer")
#         self.setFixedWidth(400)
#         self.setSizeGripEnabled(False)
#         self.setModal(True)
#         self.setStyleSheet(f"""
#             QDialog {{
#                 background: {WHITE};
#                 font-family: 'Segoe UI', sans-serif;
#             }}
#             QLabel#section {{
#                 color: {MUTED};
#                 font-size: 10px;
#                 font-weight: bold;
#                 letter-spacing: 1px;
#                 background: transparent;
#             }}
#         """)
#         self._build()

#     # -------------------------------------------------------------------------
#     def _field(self, placeholder: str, required: bool = False) -> QLineEdit:
#         le = QLineEdit()
#         le.setPlaceholderText(placeholder + (" *" if required else ""))
#         le.setFixedHeight(38)
#         le.setStyleSheet(f"""
#             QLineEdit {{
#                 background: {OFF_WHITE};
#                 color: {DARK_TEXT};
#                 border: 1.5px solid {BORDER};
#                 border-radius: 6px;
#                 font-size: 13px;
#                 padding: 0 10px;
#             }}
#             QLineEdit:focus {{ border: 1.5px solid {ACCENT}; background: {WHITE}; }}
#         """)
#         return le

#     def _build(self):
#         root = QVBoxLayout(self)
#         root.setContentsMargins(0, 0, 0, 0)
#         root.setSpacing(0)

#         # ── header bar ────────────────────────────────────────────────────────
#         hdr = QWidget()
#         hdr.setFixedHeight(48)
#         hdr.setStyleSheet(f"background: {NAVY}; border-radius: 0px;")
#         hl = QHBoxLayout(hdr)
#         hl.setContentsMargins(20, 0, 20, 0)
#         title = QLabel("New Customer")
#         title.setStyleSheet(
#             f"color: {WHITE}; font-size: 15px; font-weight: bold; background: transparent;"
#         )
#         hl.addWidget(title)
#         hl.addStretch()
#         root.addWidget(hdr)

#         # ── form body ─────────────────────────────────────────────────────────
#         body = QWidget()
#         body.setStyleSheet(f"background: {WHITE};")
#         fl = QVBoxLayout(body)
#         fl.setContentsMargins(24, 20, 24, 8)
#         fl.setSpacing(10)

#         self._f_first = self._field("First name", required=True)
#         self._f_last  = self._field("Last name")
#         self._f_phone = self._field("Phone number")
#         self._f_city  = self._field("City")

#         for lbl_txt, widget in [
#             ("FIRST NAME",   self._f_first),
#             ("LAST NAME",    self._f_last),
#             ("PHONE NUMBER", self._f_phone),
#             ("CITY",         self._f_city),
#         ]:
#             lbl = QLabel(lbl_txt)
#             lbl.setObjectName("section")
#             fl.addWidget(lbl)
#             fl.addWidget(widget)

#         # ── status label ──────────────────────────────────────────────────────
#         self._status = QLabel("")
#         self._status.setStyleSheet(
#             f"color: {DANGER}; font-size: 11px; background: transparent;"
#         )
#         self._status.setAlignment(Qt.AlignCenter)
#         fl.addWidget(self._status)

#         root.addWidget(body)

#         # ── footer buttons ────────────────────────────────────────────────────
#         foot = QWidget()
#         foot.setStyleSheet(
#             f"background: {OFF_WHITE}; border-top: 1px solid {BORDER};"
#         )
#         bl = QHBoxLayout(foot)
#         bl.setContentsMargins(24, 12, 24, 16)
#         bl.setSpacing(10)

#         cancel_btn = QPushButton("Cancel")
#         cancel_btn.setFixedHeight(36)
#         cancel_btn.setStyleSheet(f"""
#             QPushButton {{
#                 background: {WHITE}; color: {DARK_TEXT};
#                 border: 1.5px solid {BORDER}; border-radius: 6px;
#                 font-size: 13px; padding: 0 18px;
#             }}
#             QPushButton:hover {{ background: {LIGHT}; border-color: {ACCENT}; }}
#         """)
#         cancel_btn.clicked.connect(self.reject)

#         self._save_btn = QPushButton("Save Customer")
#         self._save_btn.setFixedHeight(36)
#         self._save_btn.setStyleSheet(f"""
#             QPushButton {{
#                 background: {SUCCESS}; color: {WHITE};
#                 border: none; border-radius: 6px;
#                 font-size: 13px; font-weight: bold; padding: 0 22px;
#             }}
#             QPushButton:hover {{ background: {SUCCESS_H}; }}
#             QPushButton:disabled {{ background: {BORDER}; color: {MUTED}; }}
#         """)
#         self._save_btn.clicked.connect(self._save)

#         bl.addWidget(cancel_btn)
#         bl.addStretch()
#         bl.addWidget(self._save_btn)
#         root.addWidget(foot)

#         # focus the first field
#         self._f_first.setFocus()

#     # -------------------------------------------------------------------------
#     def _save(self):
#         first = self._f_first.text().strip()
#         last  = self._f_last.text().strip()
#         phone = self._f_phone.text().strip()
#         city  = self._f_city.text().strip()

#         if not first:
#             self._status.setText("First name is required.")
#             self._f_first.setFocus()
#             return

#         # Build full customer_name from first + last
#         full_name = f"{first} {last}".strip()

#         self._save_btn.setEnabled(False)
#         self._status.setText("")

#         try:
#             print("\n" + "="*60)
#             print("[QuickAddCustomer] Starting save...")
#             print(f"  full_name='{full_name}'  phone='{phone}'  city='{city}'")

#             # Try to resolve FK IDs — all are optional (tables may be empty)
#             from models.company_defaults import get_defaults
#             defs = get_defaults()
#             print(f"[QuickAddCustomer] defaults: warehouse='{defs.get('server_warehouse')}'"
#                   f"  cost_center='{defs.get('server_cost_center')}'")

#             from database.db import get_connection
#             conn = get_connection()
#             cur  = conn.cursor()

#             def _find_id(table: str, name_val: str) -> int | None:
#                 if not name_val:
#                     return None
#                 cur.execute(
#                     f"SELECT id FROM {table} WHERE LTRIM(RTRIM(name)) = ?",
#                     (name_val.strip(),)
#                 )
#                 row = cur.fetchone()
#                 if row:
#                     print(f"  [_find_id] {table} '{name_val}' → id={row[0]}")
#                     return row[0]
#                 # fallback: first row
#                 cur.execute(f"SELECT TOP 1 id, name FROM {table} ORDER BY id ASC")
#                 fb = cur.fetchone()
#                 print(f"  [_find_id] {table} '{name_val}' NOT FOUND → fallback={fb}")
#                 return fb[0] if fb else None

#             warehouse_id   = _find_id("warehouses",      defs.get("server_warehouse", ""))
#             cost_center_id = _find_id("cost_centers",    defs.get("server_cost_center", ""))
#             price_list_id  = _find_id("price_lists",     "Standard Selling ZWG")
#             group_id       = _find_id("customer_groups", "All Customer Groups")
#             conn.close()

#             print(f"[QuickAddCustomer] IDs → warehouse={warehouse_id}  "
#                   f"cost_center={cost_center_id}  price_list={price_list_id}  group={group_id}")

#             # Direct INSERT — pass None for any FK that couldn't be resolved
#             conn2 = get_connection()
#             cur2  = conn2.cursor()
#             cur2.execute("""
#                 INSERT INTO customers (
#                     customer_name, customer_group_id, customer_type,
#                     custom_trade_name, custom_telephone_number, custom_email_address,
#                     custom_city, custom_house_no,
#                     custom_warehouse_id, custom_cost_center_id, default_price_list_id
#                 ) OUTPUT INSERTED.id VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
#             """, (
#                 full_name, group_id, "Individual",
#                 "", phone, "",
#                 city, "",
#                 warehouse_id, cost_center_id, price_list_id,
#             ))
#             new_id = int(cur2.fetchone()[0])
#             conn2.commit()
#             conn2.close()

#             print(f"[QuickAddCustomer] SUCCESS: inserted id={new_id}  name='{full_name}'")
#             print("="*60 + "\n")

#             from models.customer import get_customer_by_id
#             new_cust = get_customer_by_id(new_id) or {"id": new_id, "customer_name": full_name}
#             self.customer_created.emit(new_cust)

#             # ── Push to Frappe in background (non-blocking) ───────────────────
#             self._push_to_frappe(
#                 full_name=full_name,
#                 phone=phone,
#                 city=city,
#                 defs=defs,
#             )

#             self.accept()

#         except Exception as exc:
#             import traceback
#             print(f"[QuickAddCustomer] EXCEPTION:")
#             traceback.print_exc()
#             print("="*60 + "\n")
#             self._status.setText(f"Error: {exc}")
#             self._save_btn.setEnabled(True)

#     # -------------------------------------------------------------------------
#     def _push_to_frappe(
#         self,
#         full_name: str,
#         phone: str,
#         city: str,
#         defs: dict,
#     ) -> None:
#         """
#         Pushes the newly created customer to Frappe via the REST API.
#         Runs in a daemon thread so it never blocks the UI.

#         Frappe endpoint (POST):
#           /api/resource/Customer

#         Payload mirrors the fields Frappe expects for a Customer doctype,
#         enriched with the company context stored in company_defaults.
#         """
#         import threading, json, urllib.request, urllib.error

#         def _worker():
#             try:
#                 from services.credentials import get_credentials
#                 api_key, api_secret = get_credentials()
#             except Exception:
#                 # Fallback: read directly from DB (same logic as customer_sync_service)
#                 try:
#                     from database.db import get_connection
#                     _conn = get_connection()
#                     _cur  = _conn.cursor()
#                     _cur.execute(
#                         "SELECT api_key, api_secret FROM companies "
#                         "WHERE id=(SELECT MIN(id) FROM companies)"
#                     )
#                     _row = _cur.fetchone()
#                     _conn.close()
#                     api_key    = str(_row[0]) if _row and _row[0] else ""
#                     api_secret = str(_row[1]) if _row and _row[1] else ""
#                 except Exception:
#                     api_key = api_secret = ""

#             if not api_key or not api_secret:
#                 print("[QuickAddCustomer→Frappe] No credentials — skipping push.")
#                 return

#             try:
#                 from services.site_config import get_host as _gh
#                 base_url = _gh()
#             except Exception as e:
#                 print(f"[QuickAddCustomer→Frappe] Could not get host: {e}")
#                 return

#             # Build the Frappe Customer payload.
#             # custom_warehouse / custom_cost_center come from company_defaults
#             # (the values already set on login, matching server_warehouse / server_cost_center).
#             payload = {
                
#     "name": full_name,
#     "customer_name": full_name,
#     "customer_type": "Individual",
#     "customer_group": "All Customer Groups",
#     "currency": "USD",
#     "custom_customer_tin": "00000000",
#     "custom_customer_vat": "11111111",
#     "custom_trade_name": "dansohol",
#     "custom_email_address": "no-email.havano.cloud",
#     "custom_telephone_number": phone or "0000000000",
#     "custom_house_no": "1",
#     "custom_street": "Unknown",
#     "custom_customer_address": "N/A",
#     "custom_city": city or "N/A",
#     "custom_province": "N/A",
#     "default_warehouse": defs.get("server_warehouse", ""),
#     "default_price_list": "Standard Selling",
#     "default_cost_center": defs.get("server_cost_center", ""),
#     "is_active": True,
# }
                

#             # Strip empty strings so Frappe doesn't reject with validation errors
#             payload = {k: v for k, v in payload.items() if v}

#             url  = f"{base_url}/api/method/saas_api.www.api.create_customer"
#             body = json.dumps(payload).encode()
#             req  = urllib.request.Request(
#                 url,
#                 data=body,
#                 method="POST",
#             )
#             req.add_header("Authorization",  f"token {api_key}:{api_secret}")
#             req.add_header("Content-Type",   "application/json")
#             req.add_header("Accept",         "application/json")

#             print(f"[QuickAddCustomer→Frappe] POST {url}")
#             print(f"[QuickAddCustomer→Frappe] Payload: {json.dumps(payload, indent=2)}")

#             try:
#                 with urllib.request.urlopen(req, timeout=20) as resp:
#                     result = json.loads(resp.read().decode())
#                     frappe_name = result.get("data", {}).get("name", "?")
#                     print(
#                         f"[QuickAddCustomer→Frappe] ✓ Created on Frappe: {frappe_name}"
#                     )
#             except urllib.error.HTTPError as http_err:
#                 body_text = http_err.read().decode(errors="replace")
#                 print(
#                     f"[QuickAddCustomer→Frappe] HTTP {http_err.code}: {body_text}"
#                 )
#             except Exception as push_err:
#                 print(f"[QuickAddCustomer→Frappe] Push failed: {push_err}")

#         t = threading.Thread(target=_worker, daemon=True, name="FrappeCustomerPush")
#         t.start()

# from __future__ import annotations

# from PySide6.QtWidgets import (
#     QDialog, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
#     QLabel, QLineEdit, QFrame, QTableWidget, QTableWidgetItem,
#     QHeaderView, QAbstractItemView, QMessageBox, QComboBox,
#     QSizePolicy, QDoubleSpinBox, QListWidget, QListWidgetItem,
# )
# from PySide6.QtCore import Qt, Signal, QTimer
# from PySide6.QtGui  import QColor

# NAVY      = "#0d1f3c"
# NAVY_2    = "#162d52"
# WHITE     = "#ffffff"
# OFF_WHITE = "#f5f8fc"
# LIGHT     = "#e4eaf4"
# BORDER    = "#c8d8ec"
# DARK_TEXT = "#0d1f3c"
# MUTED     = "#5a7a9a"
# ACCENT    = "#1a5fb4"
# ACCENT_H  = "#1c6dd0"
# SUCCESS   = "#1a7a3c"
# SUCCESS_H = "#1f9447"
# DANGER    = "#b02020"
# DANGER_H  = "#cc2828"
# AMBER     = "#b7770d"
# ORANGE    = "#c05a00"

# REASONS = [
#     "Customer Return",
#     "Damaged Goods",
#     "Wrong Item",
#     "Overcharge",
#     "Quality Issue",
#     "Other",
# ]


# class CreditNoteDialog(QDialog):
#     """
#     Smart credit note dialog.
#     After confirmation emits credit_note_ready(cn_dict) so the caller
#     (POSView / OptionsDialog) can load it into the main table in return mode.
#     """

#     credit_note_ready = Signal(dict)   # emits the created CN dict

#     def __init__(self, parent=None):
#         super().__init__(parent)
#         self.setWindowTitle("Credit Note / Return")
#         self.setMinimumSize(860, 580)
#         self.setModal(True)
#         self.setWindowState(Qt.WindowMaximized)
#         self.setStyleSheet(
#             f"QDialog {{ background:{OFF_WHITE}; font-family:'Segoe UI',sans-serif; }}"
#         )

#         self._sale:        dict | None = None
#         self._all_sales:   list[dict]  = []
#         self._search_timer = QTimer(self)
#         self._search_timer.setSingleShot(True)
#         self._search_timer.setInterval(200)      # 200 ms debounce
#         self._search_timer.timeout.connect(self._run_search)

#         self._build()
#         self._preload_sales()

#     # =========================================================================
#     # Preload
#     # =========================================================================

#     def _preload_sales(self):
#         """Load all sales once into memory for fast autocomplete."""
#         try:
#             from models.sale import get_all_sales
#             self._all_sales = get_all_sales()
#         except Exception:
#             self._all_sales = []

#     # =========================================================================
#     # Build UI
#     # =========================================================================

#     def _build(self):
#         root = QVBoxLayout(self)
#         root.setSpacing(0)
#         root.setContentsMargins(0, 0, 0, 0)

#         # ── header ────────────────────────────────────────────────────────────
#         hdr = QWidget()
#         hdr.setFixedHeight(52)
#         hdr.setStyleSheet(f"background:{WHITE}; border-bottom:2px solid {BORDER};")
#         hl  = QHBoxLayout(hdr)
#         hl.setContentsMargins(28, 0, 28, 0)
#         title = QLabel("Credit Note / Return")
#         title.setStyleSheet(
#             f"color:{NAVY}; font-size:17px; font-weight:bold; background:transparent;"
#         )
#         sub = QLabel("Search for an invoice, select items to return, then confirm.")
#         sub.setStyleSheet(f"color:{MUTED}; font-size:11px; background:transparent;")
#         hl.addWidget(title)
#         hl.addSpacing(16)
#         hl.addWidget(sub)
#         hl.addStretch()
#         root.addWidget(hdr)

#         # ── body ──────────────────────────────────────────────────────────────
#         body = QWidget()
#         body.setStyleSheet(f"background:{OFF_WHITE};")
#         bl = QVBoxLayout(body)
#         bl.setContentsMargins(28, 18, 28, 18)
#         bl.setSpacing(12)

#         bl.addWidget(self._build_search_area())

#         self._banner = self._build_banner()
#         self._banner.setVisible(False)
#         bl.addWidget(self._banner)

#         self._items_frame = self._build_items_table()
#         self._items_frame.setVisible(False)
#         bl.addWidget(self._items_frame, stretch=1)

#         bl.addWidget(self._build_btns())
#         root.addWidget(body, stretch=1)

#     # ── Search area ──────────────────────────────────────────────────────────

#     def _build_search_area(self) -> QWidget:
#         wrap = QWidget()
#         wrap.setStyleSheet("background:transparent;")
#         vl = QVBoxLayout(wrap)
#         vl.setContentsMargins(0, 0, 0, 0)
#         vl.setSpacing(4)

#         row = QHBoxLayout()
#         row.setSpacing(8)

#         lbl = QLabel("Invoice / Customer:")
#         lbl.setFixedWidth(140)
#         lbl.setStyleSheet(
#             f"color:{MUTED}; font-size:11px; font-weight:bold; background:transparent;"
#         )

#         self._search = QLineEdit()
#         self._search.setPlaceholderText(
#             "Type invoice number or customer name…"
#         )
#         self._search.setFixedHeight(38)
#         self._search.setStyleSheet(f"""
#             QLineEdit {{
#                 background:{WHITE}; color:{DARK_TEXT};
#                 border:2px solid {BORDER}; border-radius:6px;
#                 font-size:13px; padding:0 12px;
#             }}
#             QLineEdit:focus {{ border:2px solid {ACCENT}; }}
#         """)
#         self._search.textChanged.connect(self._on_search_changed)
#         self._search.returnPressed.connect(self._run_search)

#         row.addWidget(lbl)
#         row.addWidget(self._search, 1)
#         vl.addLayout(row)

#         # Autocomplete dropdown (hidden until there are results)
#         self._ac_list = QListWidget()
#         self._ac_list.setFixedHeight(0)        # collapsed by default
#         self._ac_list.setStyleSheet(f"""
#             QListWidget {{
#                 background:{WHITE}; border:2px solid {ACCENT};
#                 border-top:none; border-radius:0 0 6px 6px;
#                 font-size:13px; color:{DARK_TEXT}; outline:none;
#             }}
#             QListWidget::item           {{ padding:7px 14px; min-height:28px; }}
#             QListWidget::item:selected  {{ background:{ACCENT}; color:{WHITE}; }}
#             QListWidget::item:hover     {{ background:{LIGHT}; }}
#         """)
#         self._ac_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
#         self._ac_list.itemClicked.connect(self._on_ac_clicked)
#         # Indent to align under the QLineEdit
#         ac_row = QHBoxLayout()
#         ac_row.setContentsMargins(148, 0, 0, 0)   # 140 label + 8 spacing
#         ac_row.addWidget(self._ac_list)
#         vl.addLayout(ac_row)

#         return wrap

#     # ── Info banner ──────────────────────────────────────────────────────────

#     def _build_banner(self) -> QFrame:
#         f = QFrame()
#         f.setFixedHeight(58)
#         f.setStyleSheet(
#             f"QFrame {{ background:{WHITE}; border:1px solid {BORDER}; border-radius:8px; }}"
#         )
#         hl = QHBoxLayout(f)
#         hl.setContentsMargins(16, 0, 16, 0)
#         hl.setSpacing(28)

#         self._b_inv    = self._pill("INVOICE NO")
#         self._b_cust   = self._pill("CUSTOMER")
#         self._b_date   = self._pill("DATE")
#         self._b_total  = self._pill("TOTAL")
#         self._b_status = self._pill("FRAPPE STATUS")

#         for w in [self._b_inv, self._b_cust, self._b_date,
#                   self._b_total, self._b_status]:
#             hl.addWidget(w)
#         hl.addStretch()
#         return f

#     def _pill(self, cap: str) -> QWidget:
#         w  = QWidget(); w.setStyleSheet("background:transparent;")
#         vl = QVBoxLayout(w); vl.setContentsMargins(0, 4, 0, 4); vl.setSpacing(1)
#         c  = QLabel(cap)
#         c.setStyleSheet(
#             f"color:{MUTED}; font-size:8px; font-weight:bold;"
#             f" letter-spacing:0.8px; background:transparent;"
#         )
#         v  = QLabel("—")
#         v.setStyleSheet(
#             f"color:{DARK_TEXT}; font-size:12px; font-weight:bold; background:transparent;"
#         )
#         vl.addWidget(c); vl.addWidget(v)
#         w._val = v
#         return w

#     def _set_pill(self, pill: QWidget, text: str, color: str = DARK_TEXT):
#         pill._val.setText(text)
#         pill._val.setStyleSheet(
#             f"color:{color}; font-size:12px; font-weight:bold; background:transparent;"
#         )

#     # ── Items table ──────────────────────────────────────────────────────────

#     def _build_items_table(self) -> QFrame:
#         f  = QFrame(); f.setStyleSheet("QFrame{background:transparent;}")
#         vl = QVBoxLayout(f); vl.setContentsMargins(0, 0, 0, 0); vl.setSpacing(5)

#         cap = QLabel("Select items and quantities to return:")
#         cap.setStyleSheet(
#             f"color:{MUTED}; font-size:10px; font-weight:bold;"
#             f" letter-spacing:0.6px; background:transparent;"
#         )
#         vl.addWidget(cap)

#         self._tbl = QTableWidget(0, 6)
#         self._tbl.setHorizontalHeaderLabels(
#             ["✓", "ITEM", "UNIT PRICE", "ORIG QTY", "RETURN QTY", "REASON"]
#         )
#         hh = self._tbl.horizontalHeader()
#         hh.setSectionResizeMode(0, QHeaderView.Fixed);  self._tbl.setColumnWidth(0, 36)
#         hh.setSectionResizeMode(1, QHeaderView.Stretch)
#         hh.setSectionResizeMode(2, QHeaderView.Fixed);  self._tbl.setColumnWidth(2, 100)
#         hh.setSectionResizeMode(3, QHeaderView.Fixed);  self._tbl.setColumnWidth(3, 80)
#         hh.setSectionResizeMode(4, QHeaderView.Fixed);  self._tbl.setColumnWidth(4, 110)
#         hh.setSectionResizeMode(5, QHeaderView.Fixed);  self._tbl.setColumnWidth(5, 160)
#         self._tbl.verticalHeader().setVisible(False)
#         self._tbl.setAlternatingRowColors(True)
#         self._tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
#         self._tbl.setSelectionMode(QAbstractItemView.NoSelection)
#         self._tbl.setStyleSheet(f"""
#             QTableWidget {{
#                 background:{WHITE}; border:1px solid {BORDER};
#                 gridline-color:{LIGHT}; font-size:12px; outline:none;
#             }}
#             QTableWidget::item           {{ padding:3px 8px; }}
#             QTableWidget::item:alternate {{ background:{OFF_WHITE}; }}
#             QHeaderView::section {{
#                 background:{NAVY}; color:{WHITE};
#                 padding:7px; border:none;
#                 border-right:1px solid {NAVY_2};
#                 font-size:10px; font-weight:bold;
#             }}
#         """)
#         # Check/uncheck on row click
#         self._tbl.cellClicked.connect(self._on_tbl_cell_clicked)
#         vl.addWidget(self._tbl, 1)
#         return f

#     # ── Bottom buttons ────────────────────────────────────────────────────────

#     def _build_btns(self) -> QWidget:
#         w  = QWidget(); w.setStyleSheet("background:transparent;")
#         hl = QHBoxLayout(w); hl.setContentsMargins(0, 0, 0, 0); hl.setSpacing(10)

#         bcancel = QPushButton("Cancel")
#         bcancel.setFixedHeight(44); bcancel.setFixedWidth(100)
#         bcancel.setCursor(Qt.PointingHandCursor)
#         bcancel.setFocusPolicy(Qt.NoFocus)
#         bcancel.setStyleSheet(f"""
#             QPushButton {{ background:{LIGHT}; color:{DARK_TEXT};
#                            border:1px solid {BORDER}; border-radius:6px;
#                            font-size:13px; font-weight:bold; }}
#             QPushButton:hover {{ background:{BORDER}; }}
#         """)
#         bcancel.clicked.connect(self.reject)

#         self._btn_confirm = QPushButton("✅  Issue Credit Note")
#         self._btn_confirm.setFixedHeight(44)
#         self._btn_confirm.setEnabled(False)
#         self._btn_confirm.setCursor(Qt.PointingHandCursor)
#         self._btn_confirm.setFocusPolicy(Qt.NoFocus)
#         self._btn_confirm.setStyleSheet(f"""
#             QPushButton {{ background:{SUCCESS}; color:{WHITE}; border:none;
#                            border-radius:6px; font-size:13px; font-weight:bold; }}
#             QPushButton:hover    {{ background:{SUCCESS_H}; }}
#             QPushButton:disabled {{ background:{LIGHT}; color:{MUTED}; }}
#         """)
#         self._btn_confirm.clicked.connect(self._confirm)

#         hl.addWidget(bcancel)
#         hl.addStretch()
#         hl.addWidget(self._btn_confirm)
#         return w

#     # =========================================================================
#     # Autocomplete logic
#     # =========================================================================

#     def _on_search_changed(self, text: str):
#         self._search_timer.start()   # debounce

#     def _run_search(self):
#         query = self._search.text().strip().lower()
#         self._ac_list.clear()

#         if len(query) < 1:
#             self._ac_list.setFixedHeight(0)
#             return

#         matches = [
#             s for s in self._all_sales
#             if query in (s.get("invoice_no") or "").lower()
#             or query in (s.get("customer_name") or "").lower()
#         ][:15]   # cap at 15 results

#         if not matches:
#             self._ac_list.setFixedHeight(0)
#             return

#         for s in matches:
#             inv_no  = s.get("invoice_no", "")
#             cust    = s.get("customer_name") or "Walk-in"
#             total   = f"${float(s.get('total', 0)):.2f}"
#             date    = s.get("invoice_date", "")
#             label   = f"{inv_no}   ·   {cust}   ·   {total}   ·   {date}"
#             it = QListWidgetItem(label)
#             it.setData(Qt.UserRole, s)
#             self._ac_list.addItem(it)

#         row_h = 42
#         visible = min(len(matches), 6)
#         self._ac_list.setFixedHeight(visible * row_h)

#     def _on_ac_clicked(self, item: QListWidgetItem):
#         sale_stub = item.data(Qt.UserRole)
#         self._ac_list.setFixedHeight(0)
#         self._ac_list.clear()
#         self._search.setText(sale_stub.get("invoice_no", ""))
#         self._load_sale(sale_stub["id"])

#     # =========================================================================
#     # Load sale
#     # =========================================================================

#     def _load_sale(self, sale_id: int):
#         try:
#             from models.sale import get_sale_by_id
#             full = get_sale_by_id(sale_id)
#         except Exception as e:
#             QMessageBox.warning(self, "Error", f"Could not load sale:\n{e}")
#             return
#         if not full:
#             return

#         self._sale = full

#         # ── Banner ────────────────────────────────────────────────────────────
#         frappe_ref = full.get("frappe_ref", "")
#         synced     = full.get("synced", False)
#         if frappe_ref:
#             status_txt, status_col = frappe_ref, SUCCESS
#         elif synced:
#             status_txt, status_col = "Synced (no ref)", AMBER
#         else:
#             status_txt, status_col = "Not yet synced", AMBER

#         self._set_pill(self._b_inv,    full.get("invoice_no", "—"))
#         self._set_pill(self._b_cust,   full.get("customer_name") or "Walk-in")
#         self._set_pill(self._b_date,   full.get("invoice_date", "—"))
#         self._set_pill(self._b_total,  f"${full.get('total', 0):.2f}")
#         self._set_pill(self._b_status, status_txt, status_col)
#         self._banner.setVisible(True)

#         # ── Items ─────────────────────────────────────────────────────────────
#         self._populate_items(full.get("items", []))
#         self._items_frame.setVisible(True)
#         self._btn_confirm.setEnabled(True)

#     # =========================================================================
#     # Items table
#     # =========================================================================

#     def _populate_items(self, items: list[dict]):
#         self._tbl.setRowCount(0)
#         for item in items:
#             r = self._tbl.rowCount()
#             self._tbl.insertRow(r)
#             self._tbl.setRowHeight(r, 40)

#             # Col 0 — checkbox (checked by default)
#             chk = QTableWidgetItem()
#             chk.setCheckState(Qt.Checked)
#             chk.setTextAlignment(Qt.AlignCenter)
#             chk.setData(Qt.UserRole, item)
#             self._tbl.setItem(r, 0, chk)

#             # Col 1 — name
#             self._tbl.setItem(r, 1, QTableWidgetItem(item.get("product_name", "")))

#             # Col 2 — unit price
#             pi = QTableWidgetItem(f"${float(item.get('price', 0)):.2f}")
#             pi.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
#             self._tbl.setItem(r, 2, pi)

#             # Col 3 — original qty
#             orig_qty = float(item.get("qty", 0))
#             oq = QTableWidgetItem(f"{orig_qty:.0f}")
#             oq.setTextAlignment(Qt.AlignCenter)
#             self._tbl.setItem(r, 3, oq)

#             # Col 4 — return qty spinbox
#             spin = QDoubleSpinBox()
#             spin.setMinimum(0.01)
#             spin.setMaximum(orig_qty)
#             spin.setValue(orig_qty)
#             spin.setDecimals(0)
#             spin.setFixedHeight(30)
#             spin.setStyleSheet(f"""
#                 QDoubleSpinBox {{
#                     background:{WHITE}; color:{DARK_TEXT};
#                     border:1px solid {BORDER}; border-radius:5px;
#                     font-size:12px; padding:0 6px;
#                 }}
#                 QDoubleSpinBox:focus {{ border:1px solid {ACCENT}; }}
#             """)
#             self._tbl.setCellWidget(r, 4, spin)

#             # Col 5 — reason combo
#             combo = QComboBox()
#             combo.addItems(REASONS)
#             combo.setFixedHeight(30)
#             combo.setStyleSheet(f"""
#                 QComboBox {{
#                     background:{WHITE}; color:{DARK_TEXT};
#                     border:1px solid {BORDER}; border-radius:5px;
#                     font-size:11px; padding:0 6px;
#                 }}
#                 QComboBox::drop-down {{ border:none; }}
#                 QComboBox QAbstractItemView {{
#                     background:{WHITE}; border:1px solid {BORDER};
#                     selection-background-color:{ACCENT}; selection-color:{WHITE};
#                 }}
#             """)
#             self._tbl.setCellWidget(r, 5, combo)

#     def _on_tbl_cell_clicked(self, row: int, col: int):
#         """Clicking anywhere on a row toggles the checkbox."""
#         chk = self._tbl.item(row, 0)
#         if chk:
#             new_state = Qt.Unchecked if chk.checkState() == Qt.Checked else Qt.Checked
#             chk.setCheckState(new_state)

#     # =========================================================================
#     # Confirm
#     # =========================================================================

#     def _confirm(self):
#         if not self._sale:
#             return

#         items_to_return = []
#         for r in range(self._tbl.rowCount()):
#             chk = self._tbl.item(r, 0)
#             if not chk or chk.checkState() != Qt.Checked:
#                 continue
#             orig_item = chk.data(Qt.UserRole)
#             spin      = self._tbl.cellWidget(r, 4)
#             combo     = self._tbl.cellWidget(r, 5)
#             qty       = float(spin.value()) if spin else float(orig_item.get("qty", 0))
#             if qty <= 0:
#                 continue
#             price = float(orig_item.get("price", 0))
#             items_to_return.append({
#                 **orig_item,
#                 "qty":    qty,
#                 "total":  round(qty * price, 2),
#                 "reason": combo.currentText() if combo else "Customer Return",
#             })

#         if not items_to_return:
#             QMessageBox.warning(
#                 self, "Nothing Selected",
#                 "Please check at least one item and set a return quantity."
#             )
#             return

#         total = sum(i["total"] for i in items_to_return)
#         reply = QMessageBox.question(
#             self, "Confirm Credit Note",
#             f"Issue credit note for {len(items_to_return)} item(s)\n"
#             f"Total: ${total:.2f}\n\n"
#             f"Original invoice: {self._sale.get('invoice_no', '')}",
#             QMessageBox.Yes | QMessageBox.No,
#             QMessageBox.No,
#         )
#         if reply != QMessageBox.Yes:
#             return

#         try:
#             from models.credit_note import create_credit_note
#             cn = create_credit_note(
#                 original_sale_id=self._sale["id"],
#                 items_to_return=items_to_return,
#                 currency=self._sale.get("currency", "USD"),
#                 customer_name=self._sale.get("customer_name", ""),
#             )
#         except Exception as e:
#             QMessageBox.critical(self, "Error", f"Could not create credit note:\n{e}")
#             return

#         # Status message
#         status = cn.get("cn_status", "")
#         if status == "ready":
#             extra = "Will be submitted to Frappe shortly."
#         elif status == "pending_sync":
#             extra = "Queued — will sync after the original invoice syncs."
#         else:
#             extra = "Recorded locally."

#         QMessageBox.information(
#             self, "Credit Note Issued",
#             f"✅  {cn['cn_number']} created.\n{extra}"
#         )

#         # Emit signal so POSView can load it into the main table
#         self.credit_note_ready.emit({**cn, "items_to_return": items_to_return})
#         self.accept()


# # =============================================================================
# # QuickAddCustomerDialog  — small "New Customer" popup launched from + New
# # =============================================================================

# class QuickAddCustomerDialog(QDialog):
#     """
#     Lightweight 3-field popup: Name · Phone · City.
#     Everything else (warehouse, cost center, price list, group) is resolved
#     automatically from company_defaults (the logged-in user's context).
#     """

#     customer_created = Signal(dict)   # emits the new customer dict on success

#     def __init__(self, parent=None):
#         super().__init__(parent)
#         self.setWindowTitle("New Customer")
#         self.setFixedWidth(400)
#         self.setSizeGripEnabled(False)
#         self.setModal(True)
#         self.setStyleSheet(f"""
#             QDialog {{
#                 background: {WHITE};
#                 font-family: 'Segoe UI', sans-serif;
#             }}
#             QLabel#section {{
#                 color: {MUTED};
#                 font-size: 10px;
#                 font-weight: bold;
#                 letter-spacing: 1px;
#                 background: transparent;
#             }}
#         """)
#         self._build()

#     # -------------------------------------------------------------------------
#     def _field(self, placeholder: str, required: bool = False) -> QLineEdit:
#         le = QLineEdit()
#         le.setPlaceholderText(placeholder + (" *" if required else ""))
#         le.setFixedHeight(38)
#         le.setStyleSheet(f"""
#             QLineEdit {{
#                 background: {OFF_WHITE};
#                 color: {DARK_TEXT};
#                 border: 1.5px solid {BORDER};
#                 border-radius: 6px;
#                 font-size: 13px;
#                 padding: 0 10px;
#             }}
#             QLineEdit:focus {{ border: 1.5px solid {ACCENT}; background: {WHITE}; }}
#         """)
#         return le

#     def _build(self):
#         root = QVBoxLayout(self)
#         root.setContentsMargins(0, 0, 0, 0)
#         root.setSpacing(0)

#         # ── header bar ────────────────────────────────────────────────────────
#         hdr = QWidget()
#         hdr.setFixedHeight(48)
#         hdr.setStyleSheet(f"background: {NAVY}; border-radius: 0px;")
#         hl = QHBoxLayout(hdr)
#         hl.setContentsMargins(20, 0, 20, 0)
#         title = QLabel("New Customer")
#         title.setStyleSheet(
#             f"color: {WHITE}; font-size: 15px; font-weight: bold; background: transparent;"
#         )
#         hl.addWidget(title)
#         hl.addStretch()
#         root.addWidget(hdr)

#         # ── form body ─────────────────────────────────────────────────────────
#         body = QWidget()
#         body.setStyleSheet(f"background: {WHITE};")
#         fl = QVBoxLayout(body)
#         fl.setContentsMargins(24, 20, 24, 8)
#         fl.setSpacing(10)

#         self._f_first = self._field("First name", required=True)
#         self._f_last  = self._field("Last name")
#         self._f_phone = self._field("Phone number")
#         self._f_city  = self._field("City")

#         for lbl_txt, widget in [
#             ("FIRST NAME",   self._f_first),
#             ("LAST NAME",    self._f_last),
#             ("PHONE NUMBER", self._f_phone),
#             ("CITY",         self._f_city),
#         ]:
#             lbl = QLabel(lbl_txt)
#             lbl.setObjectName("section")
#             fl.addWidget(lbl)
#             fl.addWidget(widget)

#         # ── status label ──────────────────────────────────────────────────────
#         self._status = QLabel("")
#         self._status.setStyleSheet(
#             f"color: {DANGER}; font-size: 11px; background: transparent;"
#         )
#         self._status.setAlignment(Qt.AlignCenter)
#         fl.addWidget(self._status)

#         root.addWidget(body)

#         # ── footer buttons ────────────────────────────────────────────────────
#         foot = QWidget()
#         foot.setStyleSheet(
#             f"background: {OFF_WHITE}; border-top: 1px solid {BORDER};"
#         )
#         bl = QHBoxLayout(foot)
#         bl.setContentsMargins(24, 12, 24, 16)
#         bl.setSpacing(10)

#         cancel_btn = QPushButton("Cancel")
#         cancel_btn.setFixedHeight(36)
#         cancel_btn.setStyleSheet(f"""
#             QPushButton {{
#                 background: {WHITE}; color: {DARK_TEXT};
#                 border: 1.5px solid {BORDER}; border-radius: 6px;
#                 font-size: 13px; padding: 0 18px;
#             }}
#             QPushButton:hover {{ background: {LIGHT}; border-color: {ACCENT}; }}
#         """)
#         cancel_btn.clicked.connect(self.reject)

#         self._save_btn = QPushButton("Save Customer")
#         self._save_btn.setFixedHeight(36)
#         self._save_btn.setStyleSheet(f"""
#             QPushButton {{
#                 background: {SUCCESS}; color: {WHITE};
#                 border: none; border-radius: 6px;
#                 font-size: 13px; font-weight: bold; padding: 0 22px;
#             }}
#             QPushButton:hover {{ background: {SUCCESS_H}; }}
#             QPushButton:disabled {{ background: {BORDER}; color: {MUTED}; }}
#         """)
#         self._save_btn.clicked.connect(self._save)

#         bl.addWidget(cancel_btn)
#         bl.addStretch()
#         bl.addWidget(self._save_btn)
#         root.addWidget(foot)

#         # focus the first field
#         self._f_first.setFocus()

#     # -------------------------------------------------------------------------
#     def _save(self):
#         first = self._f_first.text().strip()
#         last  = self._f_last.text().strip()
#         phone = self._f_phone.text().strip()
#         city  = self._f_city.text().strip()

#         if not first:
#             self._status.setText("First name is required.")
#             self._f_first.setFocus()
#             return

#         # Build full customer_name from first + last
#         full_name = f"{first} {last}".strip()

#         self._save_btn.setEnabled(False)
#         self._status.setText("")

#         try:
#             print("\n" + "="*60)
#             print("[QuickAddCustomer] Starting save...")
#             print(f"  full_name='{full_name}'  phone='{phone}'  city='{city}'")

#             # Try to resolve FK IDs — all are optional (tables may be empty)
#             from models.company_defaults import get_defaults
#             defs = get_defaults()
#             print(f"[QuickAddCustomer] defaults: warehouse='{defs.get('server_warehouse')}'"
#                   f"  cost_center='{defs.get('server_cost_center')}'")

#             from database.db import get_connection
#             conn = get_connection()
#             cur  = conn.cursor()

#             def _find_id(table: str, name_val: str) -> int | None:
#                 if not name_val:
#                     return None
#                 cur.execute(
#                     f"SELECT id FROM {table} WHERE LTRIM(RTRIM(name)) = ?",
#                     (name_val.strip(),)
#                 )
#                 row = cur.fetchone()
#                 if row:
#                     print(f"  [_find_id] {table} '{name_val}' → id={row[0]}")
#                     return row[0]
#                 # fallback: first row
#                 cur.execute(f"SELECT TOP 1 id, name FROM {table} ORDER BY id ASC")
#                 fb = cur.fetchone()
#                 print(f"  [_find_id] {table} '{name_val}' NOT FOUND → fallback={fb}")
#                 return fb[0] if fb else None

#             warehouse_id   = _find_id("warehouses",      defs.get("server_warehouse", ""))
#             cost_center_id = _find_id("cost_centers",    defs.get("server_cost_center", ""))
#             price_list_id  = _find_id("price_lists",     "Standard Selling ZWG")
#             group_id       = _find_id("customer_groups", "All Customer Groups")
#             conn.close()

#             print(f"[QuickAddCustomer] IDs → warehouse={warehouse_id}  "
#                   f"cost_center={cost_center_id}  price_list={price_list_id}  group={group_id}")

#             # Direct INSERT — pass None for any FK that couldn't be resolved
#             conn2 = get_connection()
#             cur2  = conn2.cursor()
#             cur2.execute("""
#                 INSERT INTO customers (
#                     customer_name, customer_group_id, customer_type,
#                     custom_trade_name, custom_telephone_number, custom_email_address,
#                     custom_city, custom_house_no,
#                     custom_warehouse_id, custom_cost_center_id, default_price_list_id
#                 ) OUTPUT INSERTED.id VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
#             """, (
#                 full_name, group_id, "Individual",
#                 "", phone, "",
#                 city, "",
#                 warehouse_id, cost_center_id, price_list_id,
#             ))
#             new_id = int(cur2.fetchone()[0])
#             conn2.commit()
#             conn2.close()

#             print(f"[QuickAddCustomer] SUCCESS: inserted id={new_id}  name='{full_name}'")
#             print("="*60 + "\n")

#             from models.customer import get_customer_by_id
#             new_cust = get_customer_by_id(new_id) or {"id": new_id, "customer_name": full_name}
#             self.customer_created.emit(new_cust)
#             self.accept()

#         except Exception as exc:
#             import traceback
#             print(f"[QuickAddCustomer] EXCEPTION:")
#             traceback.print_exc()
#             print("="*60 + "\n")
#             self._status.setText(f"Error: {exc}")
#             self._save_btn.setEnabled(True)
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QFrame, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QMessageBox, QComboBox,
    QSizePolicy, QDoubleSpinBox, QListWidget, QListWidgetItem,
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui  import QColor
import qtawesome as qta

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
            ["", "ITEM", "UNIT PRICE", "ORIG QTY", "RETURN QTY", "REASON"]
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

        self._btn_confirm = QPushButton("Issue Credit Note")
        self._btn_confirm.setIcon(qta.icon("fa5s.check", color="white"))
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
            f"{cn['cn_number']} created.\n{extra}"
        )

        # Emit signal so POSView can load it into the main table
        self.credit_note_ready.emit({**cn, "items_to_return": items_to_return})
        self.accept()


# =============================================================================
# QuickAddCustomerDialog  — small "New Customer" popup launched from + New
# =============================================================================

class QuickAddCustomerDialog(QDialog):
    """
    Lightweight 3-field popup: Name · Phone · City.
    Everything else (warehouse, cost center, price list, group) is resolved
    automatically from company_defaults (the logged-in user's context).
    """

    customer_created = Signal(dict)   # emits the new customer dict on success

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Customer")
        self.setFixedWidth(400)
        self.setSizeGripEnabled(False)
        self.setModal(True)
        self.setStyleSheet(f"""
            QDialog {{
                background: {WHITE};
                font-family: 'Segoe UI', sans-serif;
            }}
            QLabel#section {{
                color: {MUTED};
                font-size: 10px;
                font-weight: bold;
                letter-spacing: 1px;
                background: transparent;
            }}
        """)
        self._build()

    # -------------------------------------------------------------------------
    def _field(self, placeholder: str, required: bool = False) -> QLineEdit:
        le = QLineEdit()
        le.setPlaceholderText(placeholder + (" *" if required else ""))
        le.setFixedHeight(38)
        le.setStyleSheet(f"""
            QLineEdit {{
                background: {OFF_WHITE};
                color: {DARK_TEXT};
                border: 1.5px solid {BORDER};
                border-radius: 6px;
                font-size: 13px;
                padding: 0 10px;
            }}
            QLineEdit:focus {{ border: 1.5px solid {ACCENT}; background: {WHITE}; }}
        """)
        return le

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── header bar ────────────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setFixedHeight(48)
        hdr.setStyleSheet(f"background: {NAVY}; border-radius: 0px;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(20, 0, 20, 0)
        title = QLabel("New Customer")
        title.setStyleSheet(
            f"color: {WHITE}; font-size: 15px; font-weight: bold; background: transparent;"
        )
        hl.addWidget(title)
        hl.addStretch()
        root.addWidget(hdr)

        # ── form body ─────────────────────────────────────────────────────────
        body = QWidget()
        body.setStyleSheet(f"background: {WHITE};")
        fl = QVBoxLayout(body)
        fl.setContentsMargins(24, 20, 24, 8)
        fl.setSpacing(10)

        self._f_first = self._field("First name", required=True)
        self._f_last  = self._field("Last name")
        self._f_phone = self._field("Phone number")
        self._f_city  = self._field("City")

        for lbl_txt, widget in [
            ("FIRST NAME",   self._f_first),
            ("LAST NAME",    self._f_last),
            ("PHONE NUMBER", self._f_phone),
            ("CITY",         self._f_city),
        ]:
            lbl = QLabel(lbl_txt)
            lbl.setObjectName("section")
            fl.addWidget(lbl)
            fl.addWidget(widget)

        # ── Doctor picker (pharmacy mode only) ────────────────────────────────
        self._doctor_lbl   = QLabel("DOCTOR")
        self._doctor_lbl.setObjectName("section")
        self._doctor_combo = QComboBox()
        self._doctor_combo.setFixedHeight(38)
        self._doctor_combo.setStyleSheet(f"""
            QComboBox {{
                background: {OFF_WHITE}; color: {DARK_TEXT};
                border: 1.5px solid {BORDER}; border-radius: 6px;
                font-size: 13px; padding: 0 10px;
            }}
            QComboBox:focus {{ border: 1.5px solid {ACCENT}; background: {WHITE}; }}
            QComboBox::drop-down {{ border: none; width: 22px; }}
            QComboBox QAbstractItemView {{
                background: {WHITE}; border: 1px solid {BORDER};
                selection-background-color: {ACCENT}; selection-color: {WHITE};
            }}
        """)
        # Populate doctor combo (blank first item, then all doctors)
        self._populate_doctor_combo()

        # ── Quick-add doctor "+" button (opens DoctorFormDialog) ──────────────
        self._doctor_add_btn = QPushButton()
        self._doctor_add_btn.setIcon(qta.icon("fa5s.plus", color=WHITE))
        self._doctor_add_btn.setFixedSize(38, 38)
        self._doctor_add_btn.setCursor(Qt.PointingHandCursor)
        self._doctor_add_btn.setToolTip("Add new doctor")
        self._doctor_add_btn.setStyleSheet(f"""
            QPushButton {{
                background: {SUCCESS}; color: {WHITE}; border: none;
                border-radius: 6px;
            }}
            QPushButton:hover   {{ background: {SUCCESS_H}; }}
            QPushButton:pressed {{ background: {NAVY_2}; }}
        """)
        self._doctor_add_btn.clicked.connect(self._on_add_doctor)

        _docrow = QHBoxLayout()
        _docrow.setContentsMargins(0, 0, 0, 0)
        _docrow.setSpacing(6)
        _docrow.addWidget(self._doctor_combo, 1)
        _docrow.addWidget(self._doctor_add_btn)

        fl.addWidget(self._doctor_lbl)
        fl.addLayout(_docrow)

        # Show the doctor row only in pharmacy mode
        try:
            from settings.pharmacy_settings import get_pharmacy_mode
            _pharm_on = bool(get_pharmacy_mode())
        except Exception as _e:
            print(f"[QuickAddCustomer] get_pharmacy_mode failed: {_e}")
            _pharm_on = False
        self._doctor_lbl.setVisible(_pharm_on)
        self._doctor_combo.setVisible(_pharm_on)
        self._doctor_add_btn.setVisible(_pharm_on)

        # ── status label ──────────────────────────────────────────────────────
        self._status = QLabel("")
        self._status.setStyleSheet(
            f"color: {DANGER}; font-size: 11px; background: transparent;"
        )
        self._status.setAlignment(Qt.AlignCenter)
        fl.addWidget(self._status)

        root.addWidget(body)

        # ── footer buttons ────────────────────────────────────────────────────
        foot = QWidget()
        foot.setStyleSheet(
            f"background: {OFF_WHITE}; border-top: 1px solid {BORDER};"
        )
        bl = QHBoxLayout(foot)
        bl.setContentsMargins(24, 12, 24, 16)
        bl.setSpacing(10)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(36)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: {WHITE}; color: {DARK_TEXT};
                border: 1.5px solid {BORDER}; border-radius: 6px;
                font-size: 13px; padding: 0 18px;
            }}
            QPushButton:hover {{ background: {LIGHT}; border-color: {ACCENT}; }}
        """)
        cancel_btn.clicked.connect(self.reject)

        self._save_btn = QPushButton("Save Customer")
        self._save_btn.setFixedHeight(36)
        self._save_btn.setStyleSheet(f"""
            QPushButton {{
                background: {SUCCESS}; color: {WHITE};
                border: none; border-radius: 6px;
                font-size: 13px; font-weight: bold; padding: 0 22px;
            }}
            QPushButton:hover {{ background: {SUCCESS_H}; }}
            QPushButton:disabled {{ background: {BORDER}; color: {MUTED}; }}
        """)
        self._save_btn.clicked.connect(self._save)

        bl.addWidget(cancel_btn)
        bl.addStretch()
        bl.addWidget(self._save_btn)
        root.addWidget(foot)

        # focus the first field
        self._f_first.setFocus()

    # -------------------------------------------------------------------------
    def _populate_doctor_combo(self, select_id: int | None = None):
        """
        (Re)populate the doctor QComboBox. Always keeps the blank "— none —"
        item at index 0. If select_id is given, selects that doctor by local id.
        """
        try:
            self._doctor_combo.blockSignals(True)
            self._doctor_combo.clear()
            self._doctor_combo.addItem("— none —", None)
            from models.doctor import list_doctors
            for _doc in (list_doctors() or []):
                _name = _doc.full_name or ""
                if _doc.practice_no:
                    _label = f"{_name}  ({_doc.practice_no})"
                else:
                    _label = _name
                self._doctor_combo.addItem(_label, _doc.id)

            # Select the newly-created doctor if requested
            if select_id is not None:
                for i in range(self._doctor_combo.count()):
                    if self._doctor_combo.itemData(i) == select_id:
                        self._doctor_combo.setCurrentIndex(i)
                        break
        except Exception as _e:
            print(f"[QuickAddCustomer] Could not load doctors: {_e}")
        finally:
            self._doctor_combo.blockSignals(False)

    # -------------------------------------------------------------------------
    def _on_add_doctor(self):
        """
        Quick-add doctor flow: open DoctorFormDialog → save locally → push to
        Frappe in the background (QTimer.singleShot so the dialog closes first)
        → refresh the combo and auto-select the new doctor.
        """
        try:
            from views.dialogs.pharmacy_masters_dialog import DoctorFormDialog
            from models.doctor import create_doctor_local
        except Exception as _e:
            print(f"[QuickAddCustomer] Doctor form/model import failed: {_e}")
            return

        dlg = DoctorFormDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return

        data = dlg.result_data or {}
        try:
            new_id = create_doctor_local(
                full_name=data.get("full_name") or "",
                practice_no=data.get("practice_no"),
                qualification=data.get("qualification"),
                school=data.get("school"),
                phone=data.get("phone"),
            )
            print(f"[QuickAddCustomer] ✅ Doctor created locally id={new_id} "
                  f"name='{data.get('full_name')}'")
        except Exception as e:
            print(f"[QuickAddCustomer] ❌ Could not create doctor: {e}")
            return

        # Fire-and-forget push (runs after dialog paints)
        def _push_bg():
            try:
                from services.doctor_push_service import push_unsynced_doctors
                res = push_unsynced_doctors() or {}
                print(f"[QuickAddCustomer] Doctor push → "
                      f"pushed={res.get('pushed', 0)} errors={res.get('errors', 0)}")
            except Exception as e:
                print(f"[QuickAddCustomer] Doctor push failed: {e}")

        QTimer.singleShot(0, _push_bg)

        # Refresh the combo and select the new doctor
        self._populate_doctor_combo(select_id=new_id)

    # -------------------------------------------------------------------------
    def _save(self):
        first = self._f_first.text().strip()
        last  = self._f_last.text().strip()
        phone = self._f_phone.text().strip()
        city  = self._f_city.text().strip()

        if not first:
            self._status.setText("First name is required.")
            self._f_first.setFocus()
            return

        # Build full customer_name from first + last
        full_name = f"{first} {last}".strip()

        self._save_btn.setEnabled(False)
        self._status.setText("")

        try:
            print("\n" + "="*60)
            print("[QuickAddCustomer] Starting save...")
            print(f"  full_name='{full_name}'  phone='{phone}'  city='{city}'")

            # Try to resolve FK IDs — all are optional (tables may be empty)
            from models.company_defaults import get_defaults
            defs = get_defaults()
            print(f"[QuickAddCustomer] defaults: warehouse='{defs.get('server_warehouse')}'"
                  f"  cost_center='{defs.get('server_cost_center')}'")

            from database.db import get_connection
            conn = get_connection()
            cur  = conn.cursor()

            def _find_id(table: str, name_val: str) -> int | None:
                if not name_val:
                    return None
                cur.execute(
                    f"SELECT id FROM {table} WHERE LTRIM(RTRIM(name)) = ?",
                    (name_val.strip(),)
                )
                row = cur.fetchone()
                if row:
                    print(f"  [_find_id] {table} '{name_val}' → id={row[0]}")
                    return row[0]
                # fallback: first row
                cur.execute(f"SELECT TOP 1 id, name FROM {table} ORDER BY id ASC")
                fb = cur.fetchone()
                print(f"  [_find_id] {table} '{name_val}' NOT FOUND → fallback={fb}")
                return fb[0] if fb else None

            warehouse_id   = _find_id("warehouses",      defs.get("server_warehouse", ""))
            cost_center_id = _find_id("cost_centers",    defs.get("server_cost_center", ""))
            price_list_id  = _find_id("price_lists",     "Standard Selling ZWG")
            group_id       = _find_id("customer_groups", "All Customer Groups")
            conn.close()

            print(f"[QuickAddCustomer] IDs → warehouse={warehouse_id}  "
                  f"cost_center={cost_center_id}  price_list={price_list_id}  group={group_id}")

            # ── Resolve optional doctor selection (pharmacy mode only) ────────
            doctor_id = None
            doctor_frappe_name = None
            try:
                if getattr(self, "_doctor_combo", None) is not None \
                        and self._doctor_combo.isVisible():
                    sel = self._doctor_combo.currentData()
                    if sel is not None:
                        doctor_id = int(sel)
                        from models.doctor import get_doctor_by_id
                        _doc = get_doctor_by_id(doctor_id)
                        if _doc:
                            doctor_frappe_name = _doc.frappe_name
                        print(f"[QuickAddCustomer] Doctor selected: "
                              f"id={doctor_id}  frappe_name='{doctor_frappe_name}'")
            except Exception as _e:
                print(f"[QuickAddCustomer] Doctor resolve failed: {_e}")
                doctor_id = None
                doctor_frappe_name = None

            # Direct INSERT — pass None for any FK that couldn't be resolved
            conn2 = get_connection()
            cur2  = conn2.cursor()
            cur2.execute("""
                INSERT INTO customers (
                    customer_name, customer_group_id, customer_type,
                    custom_trade_name, custom_telephone_number, custom_email_address,
                    custom_city, custom_house_no,
                    custom_warehouse_id, custom_cost_center_id, default_price_list_id,
                    doctor_id, doctor_frappe_name
                ) OUTPUT INSERTED.id VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                full_name, group_id, "Individual",
                "", phone, "",
                city, "",
                warehouse_id, cost_center_id, price_list_id,
                doctor_id, doctor_frappe_name,
            ))
            new_id = int(cur2.fetchone()[0])
            conn2.commit()
            conn2.close()

            print(f"[QuickAddCustomer] SUCCESS: inserted id={new_id}  name='{full_name}'")
            print("="*60 + "\n")

            from models.customer import get_customer_by_id
            new_cust = get_customer_by_id(new_id) or {"id": new_id, "customer_name": full_name}
            self.customer_created.emit(new_cust)

            # ── Push to Frappe in background (non-blocking) ───────────────────
            self._push_to_frappe(
                full_name=full_name,
                phone=phone,
                city=city,
                defs=defs,
                customer_id=new_id,
            )

            # ── 30-second sync-check: re-push if the first attempt failed ─────
            from models.customer import schedule_frappe_sync_check
            schedule_frappe_sync_check(
                customer_id=new_id,
                customer_name=full_name,
                phone=phone,
                city=city,
                defs=defs,
            )

            self.accept()

        except Exception as exc:
            import traceback
            print(f"[QuickAddCustomer] EXCEPTION:")
            traceback.print_exc()
            print("="*60 + "\n")
            self._status.setText(f"Error: {exc}")
            self._save_btn.setEnabled(True)

    # -------------------------------------------------------------------------
    def _push_to_frappe(
        self,
        full_name: str,
        phone: str,
        city: str,
        defs: dict,
        customer_id: int = 0,
    ) -> None:
        """
        Pushes the newly created customer to Frappe via the REST API.
        Runs in a daemon thread so it never blocks the UI.

        Frappe endpoint (POST):
          /api/resource/Customer

        Payload mirrors the fields Frappe expects for a Customer doctype,
        enriched with the company context stored in company_defaults.
        """
        import threading, json, urllib.request, urllib.error

        _cid = customer_id  # capture for closure

        def _worker():
            try:
                from services.credentials import get_credentials
                api_key, api_secret = get_credentials()
            except Exception:
                # Fallback: read directly from DB (same logic as customer_sync_service)
                try:
                    from database.db import get_connection
                    _conn = get_connection()
                    _cur  = _conn.cursor()
                    _cur.execute(
                        "SELECT api_key, api_secret FROM companies "
                        "WHERE id=(SELECT MIN(id) FROM companies)"
                    )
                    _row = _cur.fetchone()
                    _conn.close()
                    api_key    = str(_row[0]) if _row and _row[0] else ""
                    api_secret = str(_row[1]) if _row and _row[1] else ""
                except Exception:
                    api_key = api_secret = ""

            if not api_key or not api_secret:
                print("[QuickAddCustomer→Frappe] No credentials — skipping push.")
                return

            try:
                from services.site_config import get_host as _gh
                base_url = _gh()
            except Exception as e:
                print(f"[QuickAddCustomer→Frappe] Could not get host: {e}")
                return

            # Build the Frappe Customer payload.
            # custom_warehouse / custom_cost_center come from company_defaults
            # (the values already set on login, matching server_warehouse / server_cost_center).
            payload = {
                
    "name": full_name,
    "customer_name": full_name,
    "customer_type": "Individual",
    "customer_group": "All Customer Groups",
    "currency": "USD",
    "custom_customer_tin": "00000000",
    "custom_customer_vat": "11111111",
    "custom_trade_name": "dansohol",
    "custom_email_address": "no-email.havano.cloud",
    "custom_telephone_number": phone or "0000000000",
    "custom_house_no": "1",
    "custom_street": "Unknown",
    "custom_customer_address": "N/A",
    "custom_city": city or "N/A",
    "custom_province": "N/A",
    "default_warehouse": defs.get("server_warehouse", ""),
    "default_price_list": "Standard Selling",
    "default_cost_center": defs.get("server_cost_center", ""),
    "is_active": True,
}
                

            # Strip empty strings so Frappe doesn't reject with validation errors
            payload = {k: v for k, v in payload.items() if v}

            url  = f"{base_url}/api/method/saas_api.www.api.create_customer"
            body = json.dumps(payload).encode()
            req  = urllib.request.Request(
                url,
                data=body,
                method="POST",
            )
            req.add_header("Authorization",  f"token {api_key}:{api_secret}")
            req.add_header("Content-Type",   "application/json")
            req.add_header("Accept",         "application/json")

            print(f"[QuickAddCustomer→Frappe] POST {url}")
            print(f"[QuickAddCustomer→Frappe] Payload: {json.dumps(payload, indent=2)}")

            try:
                with urllib.request.urlopen(req, timeout=20) as resp:
                    result = json.loads(resp.read().decode())
                    frappe_name = result.get("data", {}).get("name", "?")
                    print(
                        f"[QuickAddCustomer→Frappe] ✓ Created on Frappe: {frappe_name}"
                    )
                    # Flag locally so the 30-second sync-check thread skips re-push
                    try:
                        from models.customer import mark_frappe_synced
                        mark_frappe_synced(_cid)
                    except Exception:
                        pass
            except urllib.error.HTTPError as http_err:
                body_text = http_err.read().decode(errors="replace")
                print(
                    f"[QuickAddCustomer→Frappe] HTTP {http_err.code}: {body_text}"
                )
            except Exception as push_err:
                print(f"[QuickAddCustomer→Frappe] Push failed: {push_err}")

        t = threading.Thread(target=_worker, daemon=True, name="FrappeCustomerPush")
        t.start()