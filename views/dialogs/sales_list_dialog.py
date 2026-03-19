# =============================================================================
# views/dialogs/sales_list_dialog.py
# =============================================================================

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame, QAbstractItemView, QMessageBox,
    QMainWindow, QScrollArea, QStackedWidget
)
from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtGui  import QColor

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
# (header, sale_dict_key, fixed_width, alignment, stretch)
# width=0 + stretch=True → column stretches to fill space
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
# BACKGROUND SYNC WORKER
# =============================================================================

class _SyncWorker(QObject):
    finished = Signal(int, int)

    def run(self):
        try:
            from services.pos_upload_service import push_unsynced_sales
            r = push_unsynced_sales()
            self.finished.emit(r.get("pushed", 0), r.get("failed", 0))
        except Exception:
            self.finished.emit(0, -1)


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

        self.print_btn  = _toolbar_btn("🖨  Print (F3)",  NAVY_2, NAVY_3)
        self.recall_btn = _toolbar_btn("⟵  Recall",      ACCENT, ACCENT_H, size=(100,36))
        self.delete_btn = _toolbar_btn("🗑  Delete (F4)", DANGER, DANGER_H)
        self.sync_btn   = _toolbar_btn("⟳  Sync Now",    ACCENT, ACCENT_H, size=(120,36))
        self.filter_btn = _toolbar_btn("⏳ Unsynced",    "#7d6608","#a07d0a", size=(110,36))
        close_btn       = _toolbar_btn("✕  Close (Esc)", DANGER, DANGER_H)

        self.print_btn.setEnabled(False)
        self.recall_btn.setEnabled(False)
        self.delete_btn.setVisible(False)

        self.print_btn.clicked.connect(self._on_print)
        self.recall_btn.clicked.connect(self._on_recall)
        self.delete_btn.clicked.connect(self._on_delete)
        self.sync_btn.clicked.connect(self._on_sync_now)
        self.filter_btn.clicked.connect(self._toggle_unsynced_filter)
        close_btn.clicked.connect(self.on_close)

        root.addWidget(_build_toolbar("🧾  Sales List", right_widgets=[
            self.filter_btn, self.sync_btn,
            self.recall_btn, self.print_btn, self.delete_btn, close_btn,
        ]))

        # status bar (hidden until used)
        self._status_bar = QLabel("")
        self._status_bar.setFixedHeight(0)
        self._status_bar.setAlignment(Qt.AlignCenter)
        self._status_bar.setStyleSheet(
            f"background:{NAVY_2};color:{WHITE};font-size:12px;font-weight:bold;"
        )
        root.addWidget(self._status_bar)

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
                # Show Frappe ref in parentheses if available, else plain status
                if synced and frappe_ref:
                    text = f"✅ Synced"
                elif synced:
                    text = "✅ Synced"
                else:
                    text = "⏳ Pending"

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

            # Sync column — green if synced, amber if pending
            if key == "synced":
                it.setForeground(QColor(GREEN if synced else AMBER))
                f = it.font(); f.setBold(True); it.setFont(f)

            # Frappe ref column — muted grey if not yet assigned
            elif key == "frappe_ref":
                it.setForeground(QColor(MUTED if not frappe_ref else "#1a5fb4"))

            # Amber row tint for unsynced rows
            elif not synced:
                it.setBackground(QColor(AMBER_BG))

            if c == 0:
                it.setData(Qt.UserRole, sale["id"])
            self.table.setItem(row, c, it)

    def _update_sync_label(self):
        pending    = sum(1 for s in self._all_sales if not s.get("synced"))
        total      = len(self._all_sales)
        synced     = total - pending
        no_ref     = sum(1 for s in self._all_sales if s.get("synced") and not s.get("frappe_ref"))

        if pending:
            text = f"✅ {synced} synced  ⏳ {pending} pending"
            color = AMBER
        else:
            text = f"✅ All {total} synced"
            color = GREEN

        # Warn if some synced sales still have no Frappe ref
        if no_ref:
            text += f"  ⚠️ {no_ref} missing Frappe ref"
            color = AMBER

        self.sync_lbl.setText(text)
        self.sync_lbl.setStyleSheet(f"font-weight:bold;font-size:13px;color:{color};background:transparent;")

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

    # ── recall into POS ───────────────────────────────────────────────────────

    def _on_recall(self):
        sale = self._get_selected_sale()
        if not sale:
            return
        items = get_sale_items(sale["id"])
        if not items:
            self._show_status("⚠️  No items found for this invoice.", color=AMBER)
            return
        self.on_recall(sale, items)

    # ── unsynced filter ───────────────────────────────────────────────────────

    def _toggle_unsynced_filter(self):
        self._show_unsynced_only = not self._show_unsynced_only
        if self._show_unsynced_only:
            self.filter_btn.setText("📋 Show All")
            self.filter_btn.setStyleSheet(f"""
                QPushButton {{ background-color:{AMBER};color:{WHITE};border:none;
                               border-radius:6px;font-size:12px;font-weight:bold; }}
                QPushButton:hover {{ background-color:#c8860e; }}
            """)
        else:
            self.filter_btn.setText("⏳ Unsynced")
            self.filter_btn.setStyleSheet(f"""
                QPushButton {{ background-color:#7d6608;color:{WHITE};border:none;
                               border-radius:6px;font-size:12px;font-weight:bold; }}
                QPushButton:hover {{ background-color:#a07d0a; }}
            """)
        self._render_table(self._visible_sales())

    # ── sync now ──────────────────────────────────────────────────────────────

    def _on_sync_now(self):
        if self._sync_thread and self._sync_thread.isRunning(): return
        pending = [s for s in self._all_sales if not s.get("synced")]
        if not pending:
            self._show_status("✅ All sales are already synced.", color=GREEN)
            return

        self.sync_btn.setEnabled(False); self.sync_btn.setText("Syncing…")
        self._show_status(f"Pushing {len(pending)} sale(s) to Frappe…")

        self._sync_thread = QThread()
        self._worker      = _SyncWorker()
        self._worker.moveToThread(self._sync_thread)
        self._sync_thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_sync_done)
        self._worker.finished.connect(self._sync_thread.quit)
        self._sync_thread.start()

    def _on_sync_done(self, pushed, failed):
        self.sync_btn.setEnabled(True); self.sync_btn.setText("⟳  Sync Now")
        if   failed == -1: self._show_status("❌ Sync error — check logs.", color=DANGER)
        elif failed  >  0: self._show_status(f"⚠️  {pushed} pushed, {failed} failed.", color=AMBER)
        else:              self._show_status(f"✅ {pushed} sale(s) pushed to Frappe.", color=GREEN)
        self._load_data()

    def _show_status(self, msg, color=WHITE):
        self._status_bar.setText(msg)
        self._status_bar.setStyleSheet(
            f"background:{NAVY_2};color:{color};font-size:12px;font-weight:bold;padding:0 16px;"
        )
        self._status_bar.setFixedHeight(28)

    # ── delete / print ────────────────────────────────────────────────────────

    def _on_print(self):
        sale = self._get_selected_sale()
        if sale: self._msg("Print", f"Print Sale #{sale['number']}\n\nTODO: utils/printer.py")

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
        dlg = SalesListDialog(pos_view)   # pass POSView as parent
        dlg.show()

    Double-clicking a row recalls the sale's items into the POS invoice table
    and closes this window.
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

        # Confirm if the table already has items
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

        # Clear table
        pos._block_signals = True
        for r in range(pos.MAX_ROWS):
            pos._init_row(r)
        pos._block_signals   = False
        pos._numpad_buffer   = ""
        pos._active_row      = 0
        pos._active_col      = 0
        pos._last_filled_row = -1
        pos._reset_customer_btn()

        # Load items
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

        # Restore customer
        cust_name = (sale.get("customer_name") or "").strip()
        if cust_name and hasattr(pos, "_cust_btn"):
            pos._cust_btn.setText(f"👤  {cust_name}")
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