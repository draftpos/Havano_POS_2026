# # =============================================================================
# # views/dialogs/sales_list_dialog.py
# # =============================================================================

# from PySide6.QtWidgets import (
#     QWidget, QVBoxLayout, QHBoxLayout,
#     QPushButton, QLabel, QTableWidget, QTableWidgetItem,
#     QHeaderView, QFrame, QAbstractItemView, QMessageBox,
#     QMainWindow, QScrollArea, QStackedWidget
# )
# from PySide6.QtCore import Qt, QThread, Signal, QObject
# from PySide6.QtGui  import QColor

# from models.sale import get_all_sales, delete_sale, get_sale_items

# NAVY      = "#0d1f3c"
# NAVY_2    = "#162d52"
# NAVY_3    = "#1e3d6e"
# ACCENT    = "#1a5fb4"
# ACCENT_H  = "#1c6dd0"
# WHITE     = "#ffffff"
# OFF_WHITE = "#f5f8fc"
# LIGHT     = "#e4eaf4"
# BORDER    = "#c8d8ec"
# DARK_TEXT = "#0d1f3c"
# MUTED     = "#5a7a9a"
# DANGER    = "#b02020"
# DANGER_H  = "#cc2828"
# ROW_ALT   = "#edf3fb"
# GREEN     = "#1e8449"
# AMBER     = "#b7770d"
# AMBER_BG  = "#fef9ec"

# # ── Column definitions ────────────────────────────────────────────────────────
# # (header, sale_dict_key, fixed_width, alignment, stretch)
# # width=0 + stretch=True → column stretches to fill space
# _COLUMNS = [
#     ("Invoice No.",   "number",        100, Qt.AlignCenter,                   False),
#     ("Date",          "date",          100, Qt.AlignCenter,                   False),
#     ("Time",          "time",           75, Qt.AlignCenter,                   False),
#     ("Cashier",       "user",           90, Qt.AlignCenter,                   False),
#     ("Customer",      "customer_name",   0, Qt.AlignLeft | Qt.AlignVCenter,   True),
#     ("Company",       "company_name",    0, Qt.AlignLeft | Qt.AlignVCenter,   True),
#     ("Method",        "method",          85, Qt.AlignCenter,                  False),
#     ("Currency",      "currency",        75, Qt.AlignCenter,                  False),
#     ("Items",         "total_items",     60, Qt.AlignCenter,                  False),
#     ("Amount $",      "amount",         105, Qt.AlignRight | Qt.AlignVCenter, False),
#     ("Tendered $",    "tendered",       105, Qt.AlignRight | Qt.AlignVCenter, False),
#     ("Change $",      "change_amount",  105, Qt.AlignRight | Qt.AlignVCenter, False),
#     ("Sync",          "synced",          90, Qt.AlignCenter,                  False),
#     ("Frappe Ref",    "frappe_ref",     160, Qt.AlignLeft  | Qt.AlignVCenter, False),
# ]


# def _hr():
#     ln = QFrame(); ln.setFrameShape(QFrame.HLine)
#     ln.setStyleSheet(f"background:{BORDER};border:none;"); ln.setFixedHeight(1)
#     return ln

# def _vr():
#     ln = QFrame(); ln.setFrameShape(QFrame.VLine)
#     ln.setStyleSheet(f"background:{BORDER};border:none;"); ln.setFixedWidth(1)
#     return ln

# def _toolbar_btn(text, bg, hov, size=(130, 36)):
#     b = QPushButton(text); b.setFixedSize(*size)
#     b.setCursor(Qt.PointingHandCursor); b.setFocusPolicy(Qt.NoFocus)
#     b.setStyleSheet(f"""
#         QPushButton {{ background-color:{bg};color:{WHITE};border:none;
#                        border-radius:6px;font-size:12px;font-weight:bold; }}
#         QPushButton:hover    {{ background-color:{hov}; }}
#         QPushButton:pressed  {{ background-color:{NAVY_3}; }}
#         QPushButton:disabled {{ background-color:{LIGHT};color:{MUTED}; }}
#     """)
#     return b

# def _build_toolbar(title, left_widget=None, right_widgets=None):
#     toolbar = QWidget(); toolbar.setFixedHeight(56)
#     toolbar.setStyleSheet(f"background-color:{NAVY};")
#     tl = QHBoxLayout(toolbar); tl.setContentsMargins(20,0,20,0); tl.setSpacing(10)
#     if left_widget: tl.addWidget(left_widget)
#     if title:
#         lbl = QLabel(title)
#         lbl.setStyleSheet(f"color:{WHITE};font-size:17px;font-weight:bold;background:transparent;")
#         tl.addWidget(lbl)
#     tl.addStretch()
#     for w in (right_widgets or []): tl.addWidget(w)
#     return toolbar


# # =============================================================================
# # BACKGROUND SYNC WORKER
# # =============================================================================

# class _SyncWorker(QObject):
#     finished = Signal(int, int)

#     def run(self):
#         try:
#             from services.pos_upload_service import push_unsynced_sales
#             r = push_unsynced_sales()
#             self.finished.emit(r.get("pushed", 0), r.get("failed", 0))
#         except Exception:
#             self.finished.emit(0, -1)


# # =============================================================================
# # SALES LIST PAGE
# # =============================================================================

# class SalesListPage(QWidget):

#     def __init__(self, on_recall, on_close, parent=None):
#         super().__init__(parent)
#         self.on_recall           = on_recall
#         self.on_close            = on_close
#         self._all_sales          = []
#         self._show_unsynced_only = False
#         self._sync_thread        = None
#         self._build_ui()
#         self._load_data()

#     def _build_ui(self):
#         root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

#         self.print_btn  = _toolbar_btn("🖨  Print (F3)",  NAVY_2, NAVY_3)
#         self.recall_btn = _toolbar_btn("⟵  Recall",      ACCENT, ACCENT_H, size=(100,36))
#         self.delete_btn = _toolbar_btn("🗑  Delete (F4)", DANGER, DANGER_H)
#         self.sync_btn   = _toolbar_btn("⟳  Sync Now",    ACCENT, ACCENT_H, size=(120,36))
#         self.filter_btn = _toolbar_btn("⏳ Unsynced",    "#7d6608","#a07d0a", size=(110,36))
#         close_btn       = _toolbar_btn("✕  Close (Esc)", DANGER, DANGER_H)

#         self.print_btn.setEnabled(False)
#         self.recall_btn.setEnabled(False)
#         self.delete_btn.setVisible(False)

#         self.print_btn.clicked.connect(self._on_print)
#         self.recall_btn.clicked.connect(self._on_recall)
#         self.delete_btn.clicked.connect(self._on_delete)
#         self.sync_btn.clicked.connect(self._on_sync_now)
#         self.filter_btn.clicked.connect(self._toggle_unsynced_filter)
#         close_btn.clicked.connect(self.on_close)

#         root.addWidget(_build_toolbar("🧾  Sales List", right_widgets=[
#             self.filter_btn, self.sync_btn,
#             self.recall_btn, self.print_btn, self.delete_btn, close_btn,
#         ]))

#         # status bar (hidden until used)
#         self._status_bar = QLabel("")
#         self._status_bar.setFixedHeight(0)
#         self._status_bar.setAlignment(Qt.AlignCenter)
#         self._status_bar.setStyleSheet(
#             f"background:{NAVY_2};color:{WHITE};font-size:12px;font-weight:bold;"
#         )
#         root.addWidget(self._status_bar)

#         body = QWidget(); body.setStyleSheet(f"background-color:{OFF_WHITE};")
#         bl = QVBoxLayout(body); bl.setContentsMargins(32,20,32,20); bl.setSpacing(12)

#         hint = QLabel("Double-click a row to recall the invoice into the POS table")
#         hint.setStyleSheet(f"color:{MUTED};font-size:12px;background:transparent;")
#         bl.addWidget(hint)

#         # main table
#         self.table = QTableWidget()
#         self.table.setColumnCount(len(_COLUMNS))
#         self.table.setHorizontalHeaderLabels([c[0] for c in _COLUMNS])

#         hh = self.table.horizontalHeader()
#         for i, (_, _, w, _, stretch) in enumerate(_COLUMNS):
#             if stretch:
#                 hh.setSectionResizeMode(i, QHeaderView.Stretch)
#             else:
#                 hh.setSectionResizeMode(i, QHeaderView.Fixed)
#                 self.table.setColumnWidth(i, w)

#         self.table.verticalHeader().setVisible(False)
#         self.table.setAlternatingRowColors(True)
#         self.table.setShowGrid(True)
#         self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
#         self.table.setSelectionMode(QAbstractItemView.SingleSelection)
#         self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
#         self.table.setStyleSheet(f"""
#             QTableWidget {{
#                 background-color:{WHITE};color:{DARK_TEXT};
#                 border:1px solid {BORDER};gridline-color:{LIGHT};
#                 font-size:13px;outline:none;
#             }}
#             QTableWidget::item           {{ padding:8px 10px; }}
#             QTableWidget::item:selected  {{ background-color:{ACCENT};color:{WHITE}; }}
#             QTableWidget::item:alternate {{ background-color:{ROW_ALT}; }}
#             QHeaderView::section {{
#                 background-color:{NAVY};color:{WHITE};
#                 padding:10px;border:none;border-right:1px solid {NAVY_2};
#                 font-size:12px;font-weight:bold;
#             }}
#         """)
#         self.table.doubleClicked.connect(self._on_recall)
#         self.table.selectionModel().selectionChanged.connect(self._on_selection)
#         bl.addWidget(self.table, 1)

#         # summary bar
#         summary = QWidget(); summary.setFixedHeight(44)
#         summary.setStyleSheet(f"background-color:{WHITE};border:1px solid {BORDER};border-radius:8px;")
#         sl = QHBoxLayout(summary); sl.setContentsMargins(20,0,20,0); sl.setSpacing(32)

#         self.count_lbl    = QLabel("Sales: 0")
#         self.total_lbl    = QLabel("Total: $0.00")
#         self.tendered_lbl = QLabel("Tendered: $0.00")
#         self.change_lbl   = QLabel("Change: $0.00")
#         self.sync_lbl     = QLabel("")

#         for lbl, color in [(self.count_lbl, DARK_TEXT),(self.total_lbl, ACCENT),
#                            (self.tendered_lbl, DARK_TEXT),(self.change_lbl, DARK_TEXT),
#                            (self.sync_lbl, AMBER)]:
#             lbl.setStyleSheet(f"font-weight:bold;font-size:13px;color:{color};background:transparent;")
#             sl.addWidget(lbl)
#         sl.addStretch()
#         bl.addWidget(summary)
#         root.addWidget(body)

#     # ── data ──────────────────────────────────────────────────────────────────

#     def _load_data(self):
#         self._all_sales = get_all_sales()
#         self._render_table(self._visible_sales())
#         self._update_sync_label()

#     def _visible_sales(self):
#         if self._show_unsynced_only:
#             return [s for s in self._all_sales if not s.get("synced")]
#         return self._all_sales

#     def _render_table(self, sales):
#         PADDING = 6
#         self.table.setRowCount(len(sales) + PADDING)
#         total = tendered = change = 0.0

#         for r, sale in enumerate(sales):
#             self.table.setRowHeight(r, 38)
#             self._fill_row(r, sale)
#             total    += sale.get("amount",        0.0)
#             tendered += sale.get("tendered",      0.0)
#             change   += sale.get("change_amount", 0.0)

#         for r in range(len(sales), self.table.rowCount()):
#             self.table.setRowHeight(r, 38)
#             for c in range(len(_COLUMNS)):
#                 it = QTableWidgetItem(""); it.setFlags(it.flags() & ~Qt.ItemIsEditable)
#                 self.table.setItem(r, c, it)

#         self.count_lbl.setText(f"Sales: {len(sales)}")
#         self.total_lbl.setText(f"Total: ${total:.2f}")
#         self.tendered_lbl.setText(f"Tendered: ${tendered:.2f}")
#         self.change_lbl.setText(f"Change: ${change:.2f}")

#     def _fill_row(self, row, sale):
#         synced     = bool(sale.get("synced"))
#         frappe_ref = (sale.get("frappe_ref") or "").strip()

#         for c, (_, key, _, align, _) in enumerate(_COLUMNS):

#             if key == "synced":
#                 # Show Frappe ref in parentheses if available, else plain status
#                 if synced and frappe_ref:
#                     text = f"✅ Synced"
#                 elif synced:
#                     text = "✅ Synced"
#                 else:
#                     text = "⏳ Pending"

#             elif key == "frappe_ref":
#                 text = frappe_ref if frappe_ref else "—"

#             elif key in ("amount", "tendered", "change_amount"):
#                 text = f"{float(sale.get(key, 0)):.2f}"

#             elif key == "total_items":
#                 v = float(sale.get(key, 0))
#                 text = str(int(v)) if v == int(v) else f"{v:.2f}"

#             else:
#                 raw = sale.get(key, "")
#                 text = str(raw) if raw is not None else ""

#             it = QTableWidgetItem(text)
#             it.setFlags(it.flags() & ~Qt.ItemIsEditable)
#             it.setTextAlignment(align)

#             # Sync column — green if synced, amber if pending
#             if key == "synced":
#                 it.setForeground(QColor(GREEN if synced else AMBER))
#                 f = it.font(); f.setBold(True); it.setFont(f)

#             # Frappe ref column — muted grey if not yet assigned
#             elif key == "frappe_ref":
#                 it.setForeground(QColor(MUTED if not frappe_ref else "#1a5fb4"))

#             # Amber row tint for unsynced rows
#             elif not synced:
#                 it.setBackground(QColor(AMBER_BG))

#             if c == 0:
#                 it.setData(Qt.UserRole, sale["id"])
#             self.table.setItem(row, c, it)

#     def _update_sync_label(self):
#         pending    = sum(1 for s in self._all_sales if not s.get("synced"))
#         total      = len(self._all_sales)
#         synced     = total - pending
#         no_ref     = sum(1 for s in self._all_sales if s.get("synced") and not s.get("frappe_ref"))

#         if pending:
#             text = f"✅ {synced} synced  ⏳ {pending} pending"
#             color = AMBER
#         else:
#             text = f"✅ All {total} synced"
#             color = GREEN

#         # Warn if some synced sales still have no Frappe ref
#         if no_ref:
#             text += f"  ⚠️ {no_ref} missing Frappe ref"
#             color = AMBER

#         self.sync_lbl.setText(text)
#         self.sync_lbl.setStyleSheet(f"font-weight:bold;font-size:13px;color:{color};background:transparent;")

#     # ── selection ─────────────────────────────────────────────────────────────

#     def _get_selected_sale(self):
#         rows = self.table.selectionModel().selectedRows()
#         if not rows: return None
#         it = self.table.item(rows[0].row(), 0)
#         if not it or not it.text().strip(): return None
#         sale_id = it.data(Qt.UserRole)
#         return next((s for s in self._all_sales if s["id"] == sale_id), None)

#     def _on_selection(self):
#         has = self._get_selected_sale() is not None
#         self.recall_btn.setEnabled(has)
#         self.print_btn.setEnabled(has)
#         self.delete_btn.setEnabled(has)

#     # ── recall into POS ───────────────────────────────────────────────────────

#     def _on_recall(self):
#         sale = self._get_selected_sale()
#         if not sale:
#             return
#         items = get_sale_items(sale["id"])
#         if not items:
#             self._show_status("⚠️  No items found for this invoice.", color=AMBER)
#             return
#         self.on_recall(sale, items)

#     # ── unsynced filter ───────────────────────────────────────────────────────

#     def _toggle_unsynced_filter(self):
#         self._show_unsynced_only = not self._show_unsynced_only
#         if self._show_unsynced_only:
#             self.filter_btn.setText("📋 Show All")
#             self.filter_btn.setStyleSheet(f"""
#                 QPushButton {{ background-color:{AMBER};color:{WHITE};border:none;
#                                border-radius:6px;font-size:12px;font-weight:bold; }}
#                 QPushButton:hover {{ background-color:#c8860e; }}
#             """)
#         else:
#             self.filter_btn.setText("⏳ Unsynced")
#             self.filter_btn.setStyleSheet(f"""
#                 QPushButton {{ background-color:#7d6608;color:{WHITE};border:none;
#                                border-radius:6px;font-size:12px;font-weight:bold; }}
#                 QPushButton:hover {{ background-color:#a07d0a; }}
#             """)
#         self._render_table(self._visible_sales())

#     # ── sync now ──────────────────────────────────────────────────────────────

#     def _on_sync_now(self):
#         if self._sync_thread and self._sync_thread.isRunning(): return
#         pending = [s for s in self._all_sales if not s.get("synced")]
#         if not pending:
#             self._show_status("✅ All sales are already synced.", color=GREEN)
#             return

#         self.sync_btn.setEnabled(False); self.sync_btn.setText("Syncing…")
#         self._show_status(f"Pushing {len(pending)} sale(s) to Frappe…")

#         self._sync_thread = QThread()
#         self._worker      = _SyncWorker()
#         self._worker.moveToThread(self._sync_thread)
#         self._sync_thread.started.connect(self._worker.run)
#         self._worker.finished.connect(self._on_sync_done)
#         self._worker.finished.connect(self._sync_thread.quit)
#         self._sync_thread.start()

#     def _on_sync_done(self, pushed, failed):
#         self.sync_btn.setEnabled(True); self.sync_btn.setText("⟳  Sync Now")
#         if   failed == -1: self._show_status("❌ Sync error — check logs.", color=DANGER)
#         elif failed  >  0: self._show_status(f"⚠️  {pushed} pushed, {failed} failed.", color=AMBER)
#         else:              self._show_status(f"✅ {pushed} sale(s) pushed to Frappe.", color=GREEN)
#         self._load_data()

#     def _show_status(self, msg, color=WHITE):
#         self._status_bar.setText(msg)
#         self._status_bar.setStyleSheet(
#             f"background:{NAVY_2};color:{color};font-size:12px;font-weight:bold;padding:0 16px;"
#         )
#         self._status_bar.setFixedHeight(28)

#     # ── delete / print ────────────────────────────────────────────────────────

#     def _on_print(self):
#         sale = self._get_selected_sale()
#         if sale: self._msg("Print", f"Print Sale #{sale['number']}\n\nTODO: utils/printer.py")

#     def _on_delete(self):
#         sale = self._get_selected_sale()
#         if not sale: return
#         confirm = QMessageBox(self)
#         confirm.setWindowTitle("Confirm Delete")
#         confirm.setText(f"Delete Sale #{sale['number']}?")
#         confirm.setInformativeText("This cannot be undone.")
#         confirm.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
#         confirm.setDefaultButton(QMessageBox.No)
#         confirm.setStyleSheet(f"""
#             QMessageBox {{ background-color:{WHITE}; }} QLabel {{ color:{DARK_TEXT}; }}
#             QPushButton {{ background-color:{ACCENT};color:{WHITE};border:none;
#                            border-radius:6px;padding:8px 20px;min-width:70px; }}
#             QPushButton:hover {{ background-color:{ACCENT_H}; }}
#         """)
#         if confirm.exec() == QMessageBox.Yes:
#             delete_sale(sale["id"]); self._load_data()

#     def _msg(self, title, text):
#         m = QMessageBox(self); m.setWindowTitle(title); m.setText(text)
#         m.setStyleSheet(f"""
#             QMessageBox {{ background-color:{WHITE}; }}
#             QLabel {{ color:{DARK_TEXT};font-size:13px; }}
#             QPushButton {{ background-color:{ACCENT};color:{WHITE};border:none;
#                            border-radius:6px;padding:8px 20px;min-width:70px; }}
#             QPushButton:hover {{ background-color:{ACCENT_H}; }}
#         """)
#         m.exec()

#     def keyPressEvent(self, event):
#         k = event.key()
#         if   k == Qt.Key_F3:                     self._on_print()
#         elif k == Qt.Key_F4:                     self._on_delete()
#         elif k in (Qt.Key_Return, Qt.Key_Enter): self._on_recall()
#         else: super().keyPressEvent(event)


# # =============================================================================
# # MAIN DIALOG
# # =============================================================================

# class SalesListDialog(QMainWindow):
#     """
#     Usage:
#         dlg = SalesListDialog(pos_view)   # pass POSView as parent
#         dlg.show()

#     Double-clicking a row recalls the sale's items into the POS invoice table
#     and closes this window.
#     """

#     def __init__(self, parent=None):
#         super().__init__(parent)
#         self.setWindowTitle("Sales")
#         self.showMaximized()

#         self._list_page = SalesListPage(
#             on_recall=self._recall_into_pos,
#             on_close=self.close,
#         )
#         self.setCentralWidget(self._list_page)

#     def _recall_into_pos(self, sale: dict, items: list[dict]):
#         pos = self.parent()

#         if not pos or not hasattr(pos, "invoice_table") or not hasattr(pos, "_init_row"):
#             QMessageBox.warning(self, "Error", "Cannot recall — POS view not available.")
#             return

#         # Confirm if the table already has items
#         has_items = any(
#             pos.invoice_table.item(r, 1) and pos.invoice_table.item(r, 1).text().strip()
#             for r in range(pos.MAX_ROWS)
#         )
#         if has_items:
#             reply = QMessageBox.question(
#                 self, "Recall Invoice",
#                 f"Load invoice #{sale.get('number', '')} into the POS?\n\n"
#                 "This will clear the current invoice.",
#                 QMessageBox.Yes | QMessageBox.No,
#             )
#             if reply != QMessageBox.Yes:
#                 return

#         # Clear table
#         pos._block_signals = True
#         for r in range(pos.MAX_ROWS):
#             pos._init_row(r)
#         pos._block_signals   = False
#         pos._numpad_buffer   = ""
#         pos._active_row      = 0
#         pos._active_col      = 0
#         pos._last_filled_row = -1
#         pos._reset_customer_btn()

#         # Load items
#         for r, item in enumerate(items[:pos.MAX_ROWS]):
#             pos._init_row(
#                 r,
#                 part_no = str(item.get("part_no",      "")),
#                 details = str(item.get("product_name", "")),
#                 qty     = str(item.get("qty",          "")),
#                 amount  = str(item.get("price",        "")),
#                 disc    = str(item.get("discount",     "0")),
#                 tax     = str(item.get("tax",          "")),
#                 total   = str(item.get("total",        "")),
#             )

#         # Restore customer
#         cust_name = (sale.get("customer_name") or "").strip()
#         if cust_name and hasattr(pos, "_cust_btn"):
#             pos._cust_btn.setText(f"👤  {cust_name}")
#             try:
#                 from models.customer import get_customer_by_name
#                 cust = get_customer_by_name(cust_name)
#                 if cust:
#                     pos._selected_customer = cust
#             except Exception:
#                 pass

#         pos._recalc_totals()
#         pos._highlight_active_row(len(items))
#         pos.invoice_table.setCurrentCell(0, 0)
#         pos.invoice_table.setFocus()

#         if hasattr(pos, "parent_window") and pos.parent_window:
#             frappe_ref = sale.get("frappe_ref", "")
#             ref_info   = f" (Frappe: {frappe_ref})" if frappe_ref else ""
#             pos.parent_window._set_status(
#                 f"Recalled invoice #{sale.get('number', '')}{ref_info} — {len(items)} item(s) loaded."
#             )

#         self.close()

#     def keyPressEvent(self, event):
#         self._list_page.keyPressEvent(event)
# =============================================================================
# views/dialogs/sales_list_dialog.py
# =============================================================================

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame, QAbstractItemView, QMessageBox,
    QMainWindow, QScrollArea, QStackedWidget, QSizePolicy,
    QTextEdit,
)
from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtGui  import QColor, QFont
import qtawesome as qta

from models.sale import get_all_sales, delete_sale, get_sale_items

NAVY      = "#0d1f3c"
NAVY_2    = "#162d52"
NAVY_3    = "#1e3d6e"
ACCENT    = "#1a5fb4"
ACCENT_H  = "#1c6dd0"
WHITE     = "#ffffff"
OFF_WHITE = "#f5f8fc"
LIGHT     = "#e4eaf4"
BORDER    = "#c8d8ec"
DARK_TEXT = "#0d1f3c"
MUTED     = "#5a7a9a"
DANGER    = "#b02020"
DANGER_H  = "#cc2828"
ROW_ALT   = "#edf3fb"
GREEN     = "#1e8449"
AMBER     = "#b7770d"
AMBER_BG  = "#fef9ec"

# ── Column definitions ────────────────────────────────────────────────────────
_COLUMNS = [
    ("Invoice No.",   "number",        100, Qt.AlignCenter,                   False),
    ("Date",          "date",          100, Qt.AlignCenter,                   False),
    ("Time",          "time",           75, Qt.AlignCenter,                   False),
    ("Cashier",       "user",           90, Qt.AlignCenter,                   False),
    ("Customer",      "customer_name",   0, Qt.AlignLeft | Qt.AlignVCenter,   True),
    ("Company",       "company_name",    0, Qt.AlignLeft | Qt.AlignVCenter,   True),
    ("Method",        "method",          85, Qt.AlignCenter,                  False),
    ("Currency",      "currency",        75, Qt.AlignCenter,                  False),
    ("Items",         "total_items",     60, Qt.AlignCenter,                  False),
    ("Amount $",      "amount",         105, Qt.AlignRight | Qt.AlignVCenter, False),
    ("Tendered $",    "tendered",       105, Qt.AlignRight | Qt.AlignVCenter, False),
    ("Change $",      "change_amount",  105, Qt.AlignRight | Qt.AlignVCenter, False),
    ("Sync",          "synced",          90, Qt.AlignCenter,                  False),
    ("Frappe Ref",    "frappe_ref",     160, Qt.AlignLeft  | Qt.AlignVCenter, False),
]


def _hr():
    ln = QFrame(); ln.setFrameShape(QFrame.HLine)
    ln.setStyleSheet(f"background:{BORDER};border:none;"); ln.setFixedHeight(1)
    return ln

def _vr():
    ln = QFrame(); ln.setFrameShape(QFrame.VLine)
    ln.setStyleSheet(f"background:{BORDER};border:none;"); ln.setFixedWidth(1)
    return ln

def _toolbar_btn(text, bg, hov, size=(130, 36)):
    b = QPushButton(text); b.setFixedSize(*size)
    b.setCursor(Qt.PointingHandCursor); b.setFocusPolicy(Qt.NoFocus)
    b.setStyleSheet(f"""
        QPushButton {{ background-color:{bg};color:{WHITE};border:none;
                       border-radius:6px;font-size:12px;font-weight:bold; }}
        QPushButton:hover    {{ background-color:{hov}; }}
        QPushButton:pressed  {{ background-color:{NAVY_3}; }}
        QPushButton:disabled {{ background-color:{LIGHT};color:{MUTED}; }}
    """)
    return b

def _build_toolbar(title, left_widget=None, right_widgets=None):
    toolbar = QWidget(); toolbar.setFixedHeight(56)
    toolbar.setStyleSheet(f"background-color:{NAVY};")
    tl = QHBoxLayout(toolbar); tl.setContentsMargins(20,0,20,0); tl.setSpacing(10)
    if left_widget: tl.addWidget(left_widget)
    if title:
        lbl = QLabel(title)
        lbl.setStyleSheet(f"color:{WHITE};font-size:17px;font-weight:bold;background:transparent;")
        tl.addWidget(lbl)
    tl.addStretch()
    for w in (right_widgets or []): tl.addWidget(w)
    return toolbar


# =============================================================================
# SYNC RESULT  — structured record for one sale's sync attempt
# =============================================================================

class SyncResult:
    """
    Holds the outcome of attempting to sync a single sale.

    Attributes
    ----------
    sale_number : str
        The invoice number, e.g. "INV-00042".
    ok : bool
        True if the sale was pushed successfully.
    frappe_ref : str
        The Frappe document name returned on success (empty on failure).
    error_type : str
        Short classification: "network", "auth", "validation", "server", "unknown".
    error_message : str
        The full exception message.
    error_location : str
        The innermost traceback location, e.g. "File pos_upload_service.py, line 87".
    http_status : int | None
        HTTP status code if the error came from an HTTP response.
    raw_response : str
        The raw response body (truncated) for API errors.
    """
    __slots__ = (
        "sale_number", "ok", "frappe_ref",
        "error_type", "error_message", "error_location",
        "http_status", "raw_response",
    )

    def __init__(self, sale_number: str):
        self.sale_number    = sale_number
        self.ok             = False
        self.frappe_ref     = ""
        self.error_type     = ""
        self.error_message  = ""
        self.error_location = ""
        self.http_status    = None
        self.raw_response   = ""

    @staticmethod
    def _classify(exc: Exception, tb: str) -> tuple[str, str]:
        """Returns (error_type, error_message)."""
        msg = str(exc)
        name = type(exc).__name__

        if any(k in name for k in ("ConnectionError", "Timeout", "URLError", "SSLError")):
            return "network", f"{name}: {msg}"
        if any(k in msg.lower() for k in ("401", "403", "unauthorized", "forbidden", "token")):
            return "auth", f"Authentication/permission error — {msg}"
        if any(k in msg.lower() for k in ("validation", "mandatory", "missing", "required")):
            return "validation", f"Frappe validation error — {msg}"
        if any(k in msg.lower() for k in ("500", "502", "503", "internal server")):
            return "server", f"Server-side error — {msg}"
        return "unknown", f"{name}: {msg}"

    @staticmethod
    def _extract_location(tb: str) -> str:
        lines = [l.strip() for l in tb.splitlines() if l.strip().startswith("File ")]
        return lines[-1] if lines else ""

    @classmethod
    def from_exception(cls, sale_number: str, exc: Exception, tb: str,
                       http_status: int = None, raw_response: str = "") -> "SyncResult":
        r = cls(sale_number)
        r.ok            = False
        r.error_type, r.error_message = cls._classify(exc, tb)
        r.error_location = cls._extract_location(tb)
        r.http_status    = http_status
        r.raw_response   = raw_response[:800] if raw_response else ""
        return r

    @classmethod
    def success(cls, sale_number: str, frappe_ref: str = "") -> "SyncResult":
        r = cls(sale_number)
        r.ok         = True
        r.frappe_ref = frappe_ref
        return r

    def friendly_cause(self) -> str:
        """One-sentence human explanation of why this sale failed."""
        tips = {
            "network":    "The server could not be reached. Check your internet connection.",
            "auth":       "API credentials are invalid or expired. Re-login with email to refresh them.",
            "validation": "Frappe rejected the data. A required field may be missing or invalid.",
            "server":     "The Frappe server returned an internal error. Check the server logs.",
            "unknown":    "An unexpected error occurred. See the detail below.",
        }
        return tips.get(self.error_type, tips["unknown"])


# =============================================================================
# BACKGROUND SYNC WORKER  — per-sale detailed reporting
# =============================================================================

class _SyncWorker(QObject):
    """
    Signals
    -------
    sale_started(invoice_number)
        Emitted just before attempting each sale.
    sale_done(SyncResult)
        Emitted after each sale attempt, success or failure.
    finished(pushed, failed, results)
        Emitted once when all sales have been attempted.
        results is list[SyncResult].
    """
    sale_started = Signal(str)
    sale_done    = Signal(object)           # SyncResult
    finished     = Signal(int, int, list)   # pushed, failed, results

    def run(self):
        import traceback
        results: list[SyncResult] = []

        try:
            # ── Try to use the granular per-sale API if available ─────────────
            from services.pos_upload_service import push_single_sale, get_unsynced_sales
            sales = get_unsynced_sales()
        except ImportError:
            # Fallback: call the bulk push and wrap the aggregate result
            results = self._run_bulk_fallback()
            pushed = sum(1 for r in results if r.ok)
            failed = len(results) - pushed
            self.finished.emit(pushed, failed, results)
            return
        except Exception as e:
            tb  = traceback.format_exc()
            res = SyncResult.from_exception("(load)", e, tb)
            res.error_message = f"Could not load unsynced sales: {res.error_message}"
            self.finished.emit(0, -1, [res])
            return

        if not sales:
            self.finished.emit(0, 0, [])
            return

        for sale in sales:
            number = str(sale.get("number") or sale.get("id", "?"))
            self.sale_started.emit(number)
            try:
                ref = push_single_sale(sale)
                res = SyncResult.success(number, ref or "")
            except Exception as e:
                tb  = traceback.format_exc()
                # Try to extract HTTP details if the exception carries them
                http_status  = getattr(e, "status_code", None) or getattr(e, "code", None)
                raw_response = getattr(e, "response_text", "") or getattr(e, "text", "")
                res = SyncResult.from_exception(number, e, tb, http_status, raw_response)
            self.sale_done.emit(res)
            results.append(res)

        pushed = sum(1 for r in results if r.ok)
        failed = len(results) - pushed
        self.finished.emit(pushed, failed, results)

    # ── Fallback when push_single_sale is not available ───────────────────────
    def _run_bulk_fallback(self) -> list[SyncResult]:
        import traceback
        try:
            from services.pos_upload_service import push_unsynced_sales
            r   = push_unsynced_sales()
            ok  = r.get("pushed", 0)
            bad = r.get("failed", 0)
            results = [SyncResult.success(f"batch-{i}") for i in range(ok)]
            for i in range(bad):
                err_detail = (r.get("errors") or [{}])[i] if r.get("errors") else {}
                res = SyncResult("batch-fail")
                res.ok            = False
                res.error_type    = "unknown"
                res.error_message = str(err_detail)
                results.append(res)
            return results
        except Exception as e:
            tb  = traceback.format_exc()
            res = SyncResult.from_exception("batch", e, tb)
            return [res]


# =============================================================================
# SYNC ERROR PANEL  — expandable detail view shown below the status bar
# =============================================================================

class SyncErrorPanel(QFrame):
    """
    Appears below the status bar after a sync attempt.

    • Green pill  → all synced, auto-hides.
    • Amber/red   → stays visible, click to expand.
    • Expanded    → scrollable list: one row per failed sale with full detail.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("syncErrorPanel")
        self.setStyleSheet("QFrame#syncErrorPanel { background: transparent; }")
        self._results:  list[SyncResult] = []
        self._expanded: bool = False
        self._build()
        self.hide()

    # ── Construction ──────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Summary pill
        self._pill = QPushButton()
        self._pill.setCursor(Qt.PointingHandCursor)
        self._pill.setFixedHeight(28)
        self._pill.clicked.connect(self._toggle)
        root.addWidget(self._pill)

        # Detail area
        self._detail = QFrame()
        self._detail.setObjectName("syncDetail")
        self._detail.setStyleSheet(f"""
            QFrame#syncDetail {{
                background: {WHITE};
                border: 1px solid {BORDER};
                border-top: none;
            }}
        """)
        dl = QVBoxLayout(self._detail)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(0)

        # Scrollable inner area for the rows
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setMaximumHeight(260)
        self._scroll.setStyleSheet(f"""
            QScrollArea {{ border: none; background: {WHITE}; }}
            QScrollBar:vertical {{
                background: {LIGHT}; width: 8px; border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: #b0c4de; border-radius: 4px; min-height: 24px;
            }}
        """)

        self._rows_widget = QWidget()
        self._rows_widget.setStyleSheet(f"background: {WHITE};")
        self._rows_layout = QVBoxLayout(self._rows_widget)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(0)
        self._scroll.setWidget(self._rows_widget)

        dl.addWidget(self._scroll)
        self._detail.hide()
        root.addWidget(self._detail)

    # ── Public API ────────────────────────────────────────────────────────────

    def show_results(self, results: list[SyncResult]):
        self._results  = results
        self._expanded = False
        self._detail.hide()
        self._rebuild_rows()

        failures = [r for r in results if not r.ok]
        pushed   = len(results) - len(failures)
        total    = len(results)

        if not results:
            self.hide()
            return

        if not failures:
            self._set_pill(f"{pushed} sale(s) synced successfully.", GREEN, "#e8f5e9")
            self.show()
            from PySide6.QtCore import QTimer
            QTimer.singleShot(6000, self.hide)
            return

        # Has failures
        if pushed > 0:
            label = f"{pushed} synced, {len(failures)} failed — click to see details"
            color, bg = AMBER, "#fff3e0"
        else:
            label = f"{len(failures)} sale(s) failed to sync — click to see details"
            color, bg = DANGER, "#fdecea"

        self._set_pill(label, color, bg)
        self.show()
        # Auto-expand so the user immediately sees what went wrong
        self._expanded = True
        self._detail.show()
        self._update_pill_radius()

    # ── Internals ─────────────────────────────────────────────────────────────

    def _toggle(self):
        self._expanded = not self._expanded
        self._detail.setVisible(self._expanded)
        self._update_pill_radius()

    def _update_pill_radius(self):
        if self._expanded:
            self._pill.setStyleSheet(
                self._pill.styleSheet().replace("border-radius:4px", "border-radius:4px 4px 0 0")
            )
        # pill style is rebuilt on next show_results; no need to patch here

    def _set_pill(self, text: str, color: str, bg: str):
        self._pill.setText(text)
        self._pill.setStyleSheet(f"""
            QPushButton {{
                background: {bg};
                color: {color};
                border: 1px solid {BORDER};
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
                padding: 0 14px;
                text-align: left;
            }}
            QPushButton:hover {{ background: {LIGHT}; }}
        """)

    def _rebuild_rows(self):
        # Clear
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        failures = [r for r in self._results if not r.ok]
        if not failures:
            return

        # Column header
        hdr = QWidget()
        hdr.setStyleSheet(f"background: {LIGHT};")
        hdr.setFixedHeight(26)
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(12, 0, 12, 0)
        hl.setSpacing(0)
        for text, w in [("Invoice", 100), ("Error Type", 110), ("Cause", 0), ("Location", 240)]:
            lbl = QLabel(text)
            lbl.setStyleSheet(
                f"font-size:10px;font-weight:700;color:{MUTED};"
                f"letter-spacing:0.8px;background:transparent;"
            )
            if w:
                lbl.setFixedWidth(w)
            else:
                lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            hl.addWidget(lbl)
        self._rows_layout.addWidget(hdr)

        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background:{BORDER};border:none;")
        self._rows_layout.addWidget(divider)

        for i, res in enumerate(failures):
            row = self._make_error_row(res, i)
            self._rows_layout.addWidget(row)

    def _make_error_row(self, res: SyncResult, idx: int) -> QWidget:
        bg = WHITE if idx % 2 == 0 else "#fafbfc"

        outer = QWidget()
        outer.setStyleSheet(f"background:{bg};")
        ol = QVBoxLayout(outer)
        ol.setContentsMargins(0, 0, 0, 0)
        ol.setSpacing(0)

        # Main row
        main = QWidget()
        main.setStyleSheet(f"background:transparent;")
        ml = QHBoxLayout(main)
        ml.setContentsMargins(12, 8, 12, 4)
        ml.setSpacing(0)

        # Invoice number
        inv_lbl = QLabel(res.sale_number)
        inv_lbl.setFixedWidth(100)
        inv_lbl.setStyleSheet(
            f"font-size:12px;font-weight:700;color:{DARK_TEXT};background:transparent;"
        )
        ml.addWidget(inv_lbl)

        # Error type badge
        type_colors = {
            "network":    ("#1565c0", "#e3f2fd"),
            "auth":       ("#6a1b9a", "#f3e5f5"),
            "validation": (AMBER,     AMBER_BG),
            "server":     (DANGER,    "#fdecea"),
            "unknown":    (MUTED,     LIGHT),
        }
        tc, tbg = type_colors.get(res.error_type, (MUTED, LIGHT))
        type_lbl = QLabel(res.error_type.upper())
        type_lbl.setFixedWidth(110)
        type_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        type_lbl.setStyleSheet(f"""
            font-size:10px;font-weight:700;color:{tc};
            background:{tbg};border-radius:3px;
            padding:2px 6px;
        """)
        ml.addWidget(type_lbl)

        # Human-friendly cause (stretches)
        cause_lbl = QLabel(res.friendly_cause())
        cause_lbl.setWordWrap(True)
        cause_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        cause_lbl.setStyleSheet(
            f"font-size:11px;color:{DARK_TEXT};background:transparent;padding-right:8px;"
        )
        ml.addWidget(cause_lbl, 1)

        # Location (file + line)
        loc_lbl = QLabel(res.error_location or "—")
        loc_lbl.setFixedWidth(240)
        loc_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        loc_lbl.setWordWrap(True)
        loc_lbl.setStyleSheet(
            f"font-size:10px;color:{MUTED};"
            f"font-family:'Consolas','Courier New',monospace;"
            f"background:transparent;"
        )
        ml.addWidget(loc_lbl)

        ol.addWidget(main)

        # Detail line: full error message (always visible, monospace, selectable)
        detail_lbl = QLabel(res.error_message)
        detail_lbl.setWordWrap(True)
        detail_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        detail_lbl.setStyleSheet(f"""
            font-size:10px;
            color:{DANGER if res.error_type in ("server","unknown") else MUTED};
            font-family:'Consolas','Courier New',monospace;
            background:transparent;
            padding: 0 12px 4px 112px;
        """)
        ol.addWidget(detail_lbl)

        # HTTP status + raw response (if available)
        if res.http_status or res.raw_response:
            extra_parts = []
            if res.http_status:
                extra_parts.append(f"HTTP {res.http_status}")
            if res.raw_response:
                snippet = res.raw_response.replace("\n", " ").strip()
                if len(snippet) > 120:
                    snippet = snippet[:120] + "…"
                extra_parts.append(f"Response: {snippet}")
            extra_lbl = QLabel("  ·  ".join(extra_parts))
            extra_lbl.setWordWrap(True)
            extra_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            extra_lbl.setStyleSheet(f"""
                font-size:10px;color:#7d6608;
                font-family:'Consolas','Courier New',monospace;
                background:transparent;
                padding: 0 12px 6px 112px;
            """)
            ol.addWidget(extra_lbl)

        # Row divider
        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setFixedHeight(1)
        div.setStyleSheet(f"background:{BORDER};border:none;")
        ol.addWidget(div)

        return outer


# =============================================================================
# SALES LIST PAGE
# =============================================================================

class SalesListPage(QWidget):

    def __init__(self, on_recall, on_close, parent=None):
        super().__init__(parent)
        self.on_recall           = on_recall
        self.on_close            = on_close
        self._all_sales          = []
        self._show_unsynced_only = False
        self._sync_thread        = None
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        self.print_btn  = _toolbar_btn("Print (F3)",  NAVY_2, NAVY_3)
        self.print_btn.setIcon(qta.icon("fa5s.print", color="white"))
        self.recall_btn = _toolbar_btn("Recall",      ACCENT, ACCENT_H, size=(100,36))
        self.recall_btn.setIcon(qta.icon("fa5s.undo", color="white"))
        self.delete_btn = _toolbar_btn("Delete (F4)", DANGER, DANGER_H)
        self.delete_btn.setIcon(qta.icon("fa5s.trash", color="white"))
        self.sync_btn   = _toolbar_btn("Sync Now",    ACCENT, ACCENT_H, size=(120,36))
        self.sync_btn.setIcon(qta.icon("fa5s.sync-alt", color="white"))
        self.filter_btn = _toolbar_btn("Unsynced",    "#7d6608","#a07d0a", size=(110,36))
        close_btn       = _toolbar_btn("Close (Esc)", DANGER, DANGER_H)
        close_btn.setIcon(qta.icon("fa5s.times", color="white"))

        self.print_btn.setEnabled(False)
        self.recall_btn.setEnabled(False)
        self.delete_btn.setVisible(False)

        self.print_btn.clicked.connect(self._on_print)
        self.recall_btn.clicked.connect(self._on_recall)
        self.delete_btn.clicked.connect(self._on_delete)
        self.sync_btn.clicked.connect(self._on_sync_now)
        self.filter_btn.clicked.connect(self._toggle_unsynced_filter)
        close_btn.clicked.connect(self.on_close)

        root.addWidget(_build_toolbar("Sales List", right_widgets=[
            self.filter_btn, self.sync_btn,
            self.recall_btn, self.print_btn, self.delete_btn, close_btn,
        ]))

        # Status bar (shown during / after sync)
        self._status_bar = QLabel("")
        self._status_bar.setFixedHeight(0)
        self._status_bar.setAlignment(Qt.AlignCenter)
        self._status_bar.setStyleSheet(
            f"background:{NAVY_2};color:{WHITE};font-size:12px;font-weight:bold;"
        )
        root.addWidget(self._status_bar)

        # Sync error panel (hidden until a sync attempt finishes with errors)
        self._error_panel = SyncErrorPanel()
        root.addWidget(self._error_panel)

        body = QWidget(); body.setStyleSheet(f"background-color:{OFF_WHITE};")
        bl = QVBoxLayout(body); bl.setContentsMargins(32,20,32,20); bl.setSpacing(12)

        hint = QLabel("Double-click a row to recall the invoice into the POS table")
        hint.setStyleSheet(f"color:{MUTED};font-size:12px;background:transparent;")
        bl.addWidget(hint)

        # main table
        self.table = QTableWidget()
        self.table.setColumnCount(len(_COLUMNS))
        self.table.setHorizontalHeaderLabels([c[0] for c in _COLUMNS])

        hh = self.table.horizontalHeader()
        for i, (_, _, w, _, stretch) in enumerate(_COLUMNS):
            if stretch:
                hh.setSectionResizeMode(i, QHeaderView.Stretch)
            else:
                hh.setSectionResizeMode(i, QHeaderView.Fixed)
                self.table.setColumnWidth(i, w)

        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color:{WHITE};color:{DARK_TEXT};
                border:1px solid {BORDER};gridline-color:{LIGHT};
                font-size:13px;outline:none;
            }}
            QTableWidget::item           {{ padding:8px 10px; }}
            QTableWidget::item:selected  {{ background-color:{ACCENT};color:{WHITE}; }}
            QTableWidget::item:alternate {{ background-color:{ROW_ALT}; }}
            QHeaderView::section {{
                background-color:{NAVY};color:{WHITE};
                padding:10px;border:none;border-right:1px solid {NAVY_2};
                font-size:12px;font-weight:bold;
            }}
        """)
        self.table.doubleClicked.connect(self._on_recall)
        self.table.selectionModel().selectionChanged.connect(self._on_selection)
        bl.addWidget(self.table, 1)

        # summary bar
        summary = QWidget(); summary.setFixedHeight(44)
        summary.setStyleSheet(f"background-color:{WHITE};border:1px solid {BORDER};border-radius:8px;")
        sl = QHBoxLayout(summary); sl.setContentsMargins(20,0,20,0); sl.setSpacing(32)

        self.count_lbl    = QLabel("Sales: 0")
        self.total_lbl    = QLabel("Total: $0.00")
        self.tendered_lbl = QLabel("Tendered: $0.00")
        self.change_lbl   = QLabel("Change: $0.00")
        self.sync_lbl     = QLabel("")

        for lbl, color in [(self.count_lbl, DARK_TEXT),(self.total_lbl, ACCENT),
                           (self.tendered_lbl, DARK_TEXT),(self.change_lbl, DARK_TEXT),
                           (self.sync_lbl, AMBER)]:
            lbl.setStyleSheet(f"font-weight:bold;font-size:13px;color:{color};background:transparent;")
            sl.addWidget(lbl)
        sl.addStretch()
        bl.addWidget(summary)
        root.addWidget(body)

    # ── data ──────────────────────────────────────────────────────────────────

    def _load_data(self):
        self._all_sales = get_all_sales()
        self._render_table(self._visible_sales())
        self._update_sync_label()

    def _visible_sales(self):
        if self._show_unsynced_only:
            return [s for s in self._all_sales if not s.get("synced")]
        return self._all_sales

    def _render_table(self, sales):
        PADDING = 6
        self.table.setRowCount(len(sales) + PADDING)
        total = tendered = change = 0.0

        for r, sale in enumerate(sales):
            self.table.setRowHeight(r, 38)
            self._fill_row(r, sale)
            total    += sale.get("amount",        0.0)
            tendered += sale.get("tendered",      0.0)
            change   += sale.get("change_amount", 0.0)

        for r in range(len(sales), self.table.rowCount()):
            self.table.setRowHeight(r, 38)
            for c in range(len(_COLUMNS)):
                it = QTableWidgetItem(""); it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(r, c, it)

        self.count_lbl.setText(f"Sales: {len(sales)}")
        self.total_lbl.setText(f"Total: ${total:.2f}")
        self.tendered_lbl.setText(f"Tendered: ${tendered:.2f}")
        self.change_lbl.setText(f"Change: ${change:.2f}")

    def _fill_row(self, row, sale):
        synced     = bool(sale.get("synced"))
        frappe_ref = (sale.get("frappe_ref") or "").strip()

        for c, (_, key, _, align, _) in enumerate(_COLUMNS):
            if key == "synced":
                text = "Synced" if synced else "Pending"
            elif key == "frappe_ref":
                text = frappe_ref if frappe_ref else "—"
            elif key in ("amount", "tendered", "change_amount"):
                text = f"{float(sale.get(key, 0)):.2f}"
            elif key == "total_items":
                v = float(sale.get(key, 0))
                text = str(int(v)) if v == int(v) else f"{v:.2f}"
            else:
                raw = sale.get(key, "")
                text = str(raw) if raw is not None else ""

            it = QTableWidgetItem(text)
            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
            it.setTextAlignment(align)

            if key == "synced":
                if synced:
                    it.setIcon(qta.icon("fa5s.check", color=GREEN))
                it.setForeground(QColor(GREEN if synced else AMBER))
                f = it.font(); f.setBold(True); it.setFont(f)
            elif key == "frappe_ref":
                it.setForeground(QColor(MUTED if not frappe_ref else ACCENT))
            elif not synced:
                it.setBackground(QColor(AMBER_BG))

            if c == 0:
                it.setData(Qt.UserRole, sale["id"])
            self.table.setItem(row, c, it)

    def _update_sync_label(self):
        pending = sum(1 for s in self._all_sales if not s.get("synced"))
        total   = len(self._all_sales)
        synced  = total - pending
        no_ref  = sum(1 for s in self._all_sales if s.get("synced") and not s.get("frappe_ref"))

        if pending:
            text  = f"{synced} synced  ·  {pending} pending"
            color = AMBER
        else:
            text  = f"All {total} synced"
            color = GREEN

        if no_ref:
            text  += f"  ·  {no_ref} missing Frappe ref"
            color  = AMBER

        self.sync_lbl.setText(text)
        self.sync_lbl.setStyleSheet(
            f"font-weight:bold;font-size:13px;color:{color};background:transparent;"
        )

    # ── selection ─────────────────────────────────────────────────────────────

    def _get_selected_sale(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows: return None
        it = self.table.item(rows[0].row(), 0)
        if not it or not it.text().strip(): return None
        sale_id = it.data(Qt.UserRole)
        return next((s for s in self._all_sales if s["id"] == sale_id), None)

    def _on_selection(self):
        has = self._get_selected_sale() is not None
        self.recall_btn.setEnabled(has)
        self.print_btn.setEnabled(has)
        self.delete_btn.setEnabled(has)

    # ── recall ────────────────────────────────────────────────────────────────

    def _on_recall(self):
        sale = self._get_selected_sale()
        if not sale:
            return
        items = get_sale_items(sale["id"])
        if not items:
            self._show_status("No items found for this invoice.", color=AMBER)
            return
        self.on_recall(sale, items)

    # ── unsynced filter ───────────────────────────────────────────────────────

    def _toggle_unsynced_filter(self):
        self._show_unsynced_only = not self._show_unsynced_only
        if self._show_unsynced_only:
            self.filter_btn.setText("Show All")
            self.filter_btn.setIcon(qta.icon("fa5s.clipboard", color="white"))
            self.filter_btn.setStyleSheet(f"""
                QPushButton {{ background-color:{AMBER};color:{WHITE};border:none;
                               border-radius:6px;font-size:12px;font-weight:bold; }}
                QPushButton:hover {{ background-color:#c8860e; }}
            """)
        else:
            self.filter_btn.setText("Unsynced")
            self.filter_btn.setIcon(qta.icon("fa5s.hourglass-half", color="white"))
            self.filter_btn.setStyleSheet(f"""
                QPushButton {{ background-color:#7d6608;color:{WHITE};border:none;
                               border-radius:6px;font-size:12px;font-weight:bold; }}
                QPushButton:hover {{ background-color:#a07d0a; }}
            """)
        self._render_table(self._visible_sales())

    # ── sync now ──────────────────────────────────────────────────────────────

    def _on_sync_now(self):
        if self._sync_thread and self._sync_thread.isRunning():
            return
        pending = [s for s in self._all_sales if not s.get("synced")]
        if not pending:
            self._show_status("All sales are already synced.", color=GREEN)
            self._error_panel.hide()
            return

        self.sync_btn.setEnabled(False)
        self.sync_btn.setText("Syncing…")
        self._show_status(f"Pushing {len(pending)} sale(s) to Frappe…")
        self._error_panel.hide()

        self._sync_thread = QThread()
        self._worker      = _SyncWorker()
        self._worker.moveToThread(self._sync_thread)
        self._sync_thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_sync_done)
        self._worker.finished.connect(self._sync_thread.quit)
        self._sync_thread.start()

    def _on_sync_done(self, pushed: int, failed: int, results: list):
        self.sync_btn.setEnabled(True)
        self.sync_btn.setText("Sync Now")
        self.sync_btn.setIcon(qta.icon("fa5s.sync-alt", color="white"))

        if failed == -1:
            # Special: worker itself crashed before processing any sale
            self._show_status("Sync could not start — see details below.", color=DANGER)
        elif failed > 0:
            self._show_status(
                f"{pushed} pushed, {failed} failed — see details below.", color=AMBER
            )
        else:
            self._show_status(f"{pushed} sale(s) pushed to Frappe.", color=GREEN)

        # Always pass results to the panel; it decides what to show
        self._error_panel.show_results(results)
        self._load_data()

    def _show_status(self, msg, color=WHITE):
        self._status_bar.setText(msg)
        self._status_bar.setStyleSheet(
            f"background:{NAVY_2};color:{color};font-size:12px;"
            f"font-weight:bold;padding:0 16px;"
        )
        self._status_bar.setFixedHeight(28)

    # ── delete / print ────────────────────────────────────────────────────────

    def _on_print(self):
        sale = self._get_selected_sale()
        if sale:
            self._msg("Print", f"Print Sale #{sale['number']}\n\nTODO: utils/printer.py")

    def _on_delete(self):
        sale = self._get_selected_sale()
        if not sale: return
        confirm = QMessageBox(self)
        confirm.setWindowTitle("Confirm Delete")
        confirm.setText(f"Delete Sale #{sale['number']}?")
        confirm.setInformativeText("This cannot be undone.")
        confirm.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        confirm.setDefaultButton(QMessageBox.No)
        confirm.setStyleSheet(f"""
            QMessageBox {{ background-color:{WHITE}; }} QLabel {{ color:{DARK_TEXT}; }}
            QPushButton {{ background-color:{ACCENT};color:{WHITE};border:none;
                           border-radius:6px;padding:8px 20px;min-width:70px; }}
            QPushButton:hover {{ background-color:{ACCENT_H}; }}
        """)
        if confirm.exec() == QMessageBox.Yes:
            delete_sale(sale["id"]); self._load_data()

    def _msg(self, title, text):
        m = QMessageBox(self); m.setWindowTitle(title); m.setText(text)
        m.setStyleSheet(f"""
            QMessageBox {{ background-color:{WHITE}; }}
            QLabel {{ color:{DARK_TEXT};font-size:13px; }}
            QPushButton {{ background-color:{ACCENT};color:{WHITE};border:none;
                           border-radius:6px;padding:8px 20px;min-width:70px; }}
            QPushButton:hover {{ background-color:{ACCENT_H}; }}
        """)
        m.exec()

    def keyPressEvent(self, event):
        k = event.key()
        if   k == Qt.Key_F3:                     self._on_print()
        elif k == Qt.Key_F4:                     self._on_delete()
        elif k in (Qt.Key_Return, Qt.Key_Enter): self._on_recall()
        else: super().keyPressEvent(event)


# =============================================================================
# MAIN DIALOG
# =============================================================================

class SalesListDialog(QMainWindow):
    """
    Usage:
        dlg = SalesListDialog(pos_view)
        dlg.show()
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sales")
        self.showMaximized()

        self._list_page = SalesListPage(
            on_recall=self._recall_into_pos,
            on_close=self.close,
        )
        self.setCentralWidget(self._list_page)

    def _recall_into_pos(self, sale: dict, items: list[dict]):
        pos = self.parent()

        if not pos or not hasattr(pos, "invoice_table") or not hasattr(pos, "_init_row"):
            QMessageBox.warning(self, "Error", "Cannot recall — POS view not available.")
            return

        has_items = any(
            pos.invoice_table.item(r, 1) and pos.invoice_table.item(r, 1).text().strip()
            for r in range(pos.MAX_ROWS)
        )
        if has_items:
            reply = QMessageBox.question(
                self, "Recall Invoice",
                f"Load invoice #{sale.get('number', '')} into the POS?\n\n"
                "This will clear the current invoice.",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        pos._block_signals = True
        for r in range(pos.MAX_ROWS):
            pos._init_row(r)
        pos._block_signals   = False
        pos._numpad_buffer   = ""
        pos._active_row      = 0
        pos._active_col      = 0
        pos._last_filled_row = -1
        pos._reset_customer_btn()

        for r, item in enumerate(items[:pos.MAX_ROWS]):
            pos._init_row(
                r,
                part_no = str(item.get("part_no",      "")),
                details = str(item.get("product_name", "")),
                qty     = str(item.get("qty",          "")),
                amount  = str(item.get("price",        "")),
                disc    = str(item.get("discount",     "0")),
                tax     = str(item.get("tax",          "")),
                total   = str(item.get("total",        "")),
            )

        cust_name = (sale.get("customer_name") or "").strip()
        if cust_name and hasattr(pos, "_cust_btn"):
            pos._cust_btn.setText(f"{cust_name}")
            try:
                from models.customer import get_customer_by_name
                cust = get_customer_by_name(cust_name)
                if cust:
                    pos._selected_customer = cust
            except Exception:
                pass

        pos._recalc_totals()
        pos._highlight_active_row(len(items))
        pos.invoice_table.setCurrentCell(0, 0)
        pos.invoice_table.setFocus()

        if hasattr(pos, "parent_window") and pos.parent_window:
            frappe_ref = sale.get("frappe_ref", "")
            ref_info   = f" (Frappe: {frappe_ref})" if frappe_ref else ""
            pos.parent_window._set_status(
                f"Recalled invoice #{sale.get('number', '')}{ref_info} — {len(items)} item(s) loaded."
            )

        self.close()

    def keyPressEvent(self, event):
        self._list_page.keyPressEvent(event)