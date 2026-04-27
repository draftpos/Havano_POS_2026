# views/dialogs/reprint_quotation_labels_dialog.py
# =============================================================================
# Standalone dialog — search a quotation by number/customer, then reprint
# its pharmacy ZPL labels.
#
# Usage:
#   from views.dialogs.reprint_quotation_labels_dialog import ReprintQuotationLabelsDialog
#   ReprintQuotationLabelsDialog(parent=self).exec()
#
#   # Or pre-select a quotation:
#   ReprintQuotationLabelsDialog(parent=self, quotation_id=42).exec()
# =============================================================================

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QPushButton, QFrame, QWidget,
    QMessageBox, QSplitter,
)
from PySide6.QtCore import Qt, QTimer, QSortFilterProxyModel
from PySide6.QtGui import QColor, QFont

try:
    import qtawesome as qta
except Exception:
    qta = None


# ── Palette (mirrors QuotationDialog) ────────────────────────────────────────
_STYLE = """
QDialog { background: #f0f2f5; }
QLabel  { color: #1a1a2e; font-size: 13px; background: transparent; }
QLineEdit {
    background: white; color: #1a1a2e;
    border: 1px solid #d0d5dd; border-radius: 6px;
    padding: 7px 12px; font-size: 13px; min-height: 20px;
}
QLineEdit:focus { border: 2px solid #2563eb; }
QLineEdit:hover { border: 1px solid #2563eb; }
QListWidget {
    background: white; border: 1px solid #e2e8f0;
    border-radius: 6px; font-size: 13px; outline: none;
}
QListWidget::item { padding: 8px 12px; border-bottom: 1px solid #f0f2f5; }
QListWidget::item:selected  { background: #eff6ff; color: #1e40af; }
QListWidget::item:hover     { background: #f8fafc; }
QTableWidget {
    background: white; border: none;
    gridline-color: #f0f2f5; font-size: 13px;
    selection-background-color: #eff6ff;
    selection-color: #1e40af;
    alternate-background-color: #f8fafc;
}
QTableWidget::item {
    padding: 10px; border-bottom: 1px solid #f0f2f5; color: #1a1a2e;
}
QTableWidget::item:selected { background: #eff6ff; color: #1e40af; }
QHeaderView::section {
    background: #f8fafc; color: #64748b;
    padding: 10px; font-weight: 600; font-size: 11px;
    border: none; border-bottom: 2px solid #e2e8f0;
    letter-spacing: 0.3px;
}
QPushButton {
    border: none; border-radius: 6px;
    padding: 9px 20px; font-weight: 600;
    font-size: 13px; font-family: 'Segoe UI', sans-serif;
}
QPushButton#primaryBtn   { background: #2563eb; color: white; }
QPushButton#primaryBtn:hover   { background: #1d4ed8; }
QPushButton#dangerBtn    { background: #ef4444; color: white; }
QPushButton#dangerBtn:hover    { background: #dc2626; }
QPushButton#secondaryBtn { background: #64748b; color: white; }
QPushButton#secondaryBtn:hover { background: #475569; }
QPushButton#successBtn   { background: #16a34a; color: white; }
QPushButton#successBtn:hover   { background: #15803d; }
QPushButton:disabled     { background: #e2e8f0; color: #94a3b8; }
QFrame#card {
    background: white; border: 1px solid #e2e8f0; border-radius: 10px;
}
QSplitter::handle { background: #e2e8f0; width: 2px; }
"""


def _card():
    f = QFrame()
    f.setObjectName("card")
    return f


def _sep():
    s = QFrame()
    s.setFrameShape(QFrame.HLine)
    s.setStyleSheet("color: #f0f2f5; background: #e2e8f0;")
    s.setFixedHeight(1)
    return s


# =============================================================================
class ReprintQuotationLabelsDialog(QDialog):
    """
    Search for a quotation by number or customer name (live autocomplete),
    see its pharmacy items, and reprint ZPL labels.
    """

    def __init__(self, parent=None, quotation_id: int = None):
        super().__init__(parent)
        self._all_quotations   = []   # list of quotation model objects
        self._filtered         = []   # currently shown in list
        self._selected_q       = None  # the chosen quotation object
        self._preselect_id     = quotation_id

        self.setWindowTitle("Reprint Pharmacy Labels")
        self.setMinimumSize(1100, 700)
        self.setModal(True)
        self.setWindowState(Qt.WindowMaximized)
        self.setStyleSheet(_STYLE)

        self._build_ui()

        # Debounce timer for search
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(200)
        self._search_timer.timeout.connect(self._apply_filter)

        self._load_quotations()

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(18, 18, 18, 12)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("Reprint Pharmacy Labels")
        title.setStyleSheet(
            "font-size: 22px; font-weight: 700; color: #1e40af; letter-spacing: -0.3px;"
        )
        hdr.addWidget(title)
        hdr.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setObjectName("secondaryBtn")
        close_btn.clicked.connect(self.accept)
        hdr.addWidget(close_btn)
        root.addLayout(hdr)

        # Search bar card
        search_card = _card()
        search_card.setStyleSheet(
            "QFrame#card { background: white; border: 1px solid #e2e8f0;"
            " border-radius: 8px; }"
        )
        sl = QHBoxLayout(search_card)
        sl.setContentsMargins(12, 10, 12, 10)
        sl.setSpacing(10)

        search_icon_lbl = QLabel("🔍")
        search_icon_lbl.setStyleSheet("font-size: 15px; background: transparent;")
        sl.addWidget(search_icon_lbl)

        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText(
            "Type quotation number or customer name to search…"
        )
        self._search_box.textChanged.connect(self._on_search_changed)
        sl.addWidget(self._search_box, 1)

        self._count_lbl = QLabel("0 quotations")
        self._count_lbl.setStyleSheet("color: #94a3b8; font-size: 12px;")
        sl.addWidget(self._count_lbl)

        sep_lbl = QLabel("|")
        sep_lbl.setStyleSheet("color: #d0d5dd; font-size: 16px; background: transparent;")
        sl.addWidget(sep_lbl)

        printer_icon_lbl = QLabel("🖨")
        printer_icon_lbl.setStyleSheet("font-size: 15px; background: transparent;")
        sl.addWidget(printer_icon_lbl)

        self._printer_name_lbl = QLabel("No printer configured")
        self._printer_name_lbl.setStyleSheet(
            "color: #ef4444; font-size: 12px; font-weight: 600;"
        )
        sl.addWidget(self._printer_name_lbl)

        root.addWidget(search_card)

        # Splitter — left: quotation list | right: details + actions
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(2)

        # ── LEFT: quotation list ──────────────────────────────────────────────
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(0)

        list_card = _card()
        list_card.setStyleSheet(
            "QFrame#card { background: white; border: 1px solid #e2e8f0; border-radius: 10px; }"
        )
        lc_lay = QVBoxLayout(list_card)
        lc_lay.setContentsMargins(0, 0, 0, 0)
        lc_lay.setSpacing(0)

        list_title = QLabel("  Quotations")
        list_title.setFixedHeight(38)
        list_title.setStyleSheet(
            "font-weight: 700; font-size: 13px; color: #1a1a2e;"
            " border-bottom: 1px solid #e2e8f0; padding-left: 12px;"
        )
        lc_lay.addWidget(list_title)

        self._q_list = QListWidget()
        self._q_list.setAlternatingRowColors(True)
        self._q_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._q_list.itemSelectionChanged.connect(self._on_list_selection_changed)
        lc_lay.addWidget(self._q_list)

        ll.addWidget(list_card)
        splitter.addWidget(left)

        # ── RIGHT: details ────────────────────────────────────────────────────
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(8, 0, 0, 0)
        rl.setSpacing(10)

        # Info card
        info_card = _card()
        info_card.setStyleSheet(
            "QFrame#card { background: white; border: 1px solid #e2e8f0;"
            " border-radius: 10px; padding: 6px; }"
        )
        il = QVBoxLayout(info_card)
        il.setSpacing(8)
        il.setContentsMargins(16, 14, 16, 14)

        top_row = QHBoxLayout()
        self._cust_lbl = QLabel("—")
        self._cust_lbl.setStyleSheet(
            "font-size: 17px; font-weight: 700; color: #1e40af;"
        )
        top_row.addWidget(self._cust_lbl)
        top_row.addStretch()

        self._status_badge = QLabel("—")
        self._status_badge.setAlignment(Qt.AlignCenter)
        self._status_badge.setFixedHeight(24)
        self._status_badge.setStyleSheet(
            "QLabel { background: #e2e8f0; color: #64748b;"
            " border-radius: 12px; padding: 2px 14px;"
            " font-weight: 700; font-size: 11px; }"
        )
        top_row.addWidget(self._status_badge)
        il.addLayout(top_row)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(24)

        def _meta_col(label_text):
            col = QVBoxLayout()
            col.setSpacing(2)
            lbl = QLabel(label_text)
            lbl.setStyleSheet("font-size: 11px; color: #94a3b8; font-weight: 600;")
            val = QLabel("—")
            val.setStyleSheet("font-size: 13px; font-weight: 600; color: #1a1a2e;")
            col.addWidget(lbl)
            col.addWidget(val)
            return col, val

        col1, self._q_ref_lbl    = _meta_col("QUOTATION")
        col2, self._q_date_lbl   = _meta_col("DATE")
        col3, self._q_total_lbl  = _meta_col("GRAND TOTAL")
        col4, self._pharm_ct_lbl = _meta_col("PHARMACY ITEMS")
        for c in (col1, col2, col3, col4):
            meta_row.addLayout(c)
        meta_row.addStretch()
        il.addLayout(meta_row)
        rl.addWidget(info_card)

        # Items table card
        items_card = _card()
        items_card.setStyleSheet(
            "QFrame#card { background: white; border: 1px solid #e2e8f0; border-radius: 10px; }"
        )
        ic_lay = QVBoxLayout(items_card)
        ic_lay.setContentsMargins(0, 0, 0, 0)
        ic_lay.setSpacing(0)

        items_hdr = QHBoxLayout()
        items_hdr.setContentsMargins(16, 12, 16, 8)
        items_title = QLabel("Pharmacy Items on this Quotation")
        items_title.setStyleSheet("font-weight: 700; font-size: 13px; color: #1a1a2e;")
        items_hdr.addWidget(items_title)
        items_hdr.addStretch()
        self._no_items_lbl = QLabel("Select a quotation to see its pharmacy items")
        self._no_items_lbl.setStyleSheet("color: #94a3b8; font-size: 12px;")
        items_hdr.addWidget(self._no_items_lbl)
        ic_lay.addLayout(items_hdr)
        ic_lay.addWidget(_sep())

        self._items_tbl = QTableWidget(0, 6)
        self._items_tbl.setHorizontalHeaderLabels(
            ["Product", "Batch", "Expiry", "Qty", "UOM", "Dosage"]
        )
        hh = self._items_tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        for ci, w in [(1, 90), (2, 90), (3, 60), (4, 60), (5, 130)]:
            hh.setSectionResizeMode(ci, QHeaderView.Fixed)
            self._items_tbl.setColumnWidth(ci, w)
        self._items_tbl.verticalHeader().setVisible(False)
        self._items_tbl.setAlternatingRowColors(True)
        self._items_tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._items_tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._items_tbl.setSelectionMode(QAbstractItemView.SingleSelection)
        self._items_tbl.setShowGrid(False)
        self._items_tbl.itemSelectionChanged.connect(self._on_items_table_selection)
        ic_lay.addWidget(self._items_tbl)
        rl.addWidget(items_card, 1)

        # Action buttons
        act = QHBoxLayout()
        act.setSpacing(10)
        act.setContentsMargins(0, 4, 0, 0)

        self._reprint_sel_btn = QPushButton("Reprint Selected")
        self._reprint_sel_btn.setObjectName("primaryBtn")
        self._reprint_sel_btn.setEnabled(False)
        self._reprint_sel_btn.setToolTip("Reprint the label for the highlighted item")
        if qta is not None:
            try:
                self._reprint_sel_btn.setIcon(
                    qta.icon("fa5s.print", color="white")
                )
            except Exception:
                pass
        self._reprint_sel_btn.clicked.connect(self._reprint_selected)

        self._reprint_all_btn = QPushButton("Reprint All Labels")
        self._reprint_all_btn.setObjectName("successBtn")
        self._reprint_all_btn.setEnabled(False)
        self._reprint_all_btn.setToolTip("Reprint all pharmacy labels for this quotation")
        if qta is not None:
            try:
                self._reprint_all_btn.setIcon(
                    qta.icon("fa5s.print", color="white")
                )
            except Exception:
                pass
        self._reprint_all_btn.clicked.connect(self._reprint_all)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("font-size: 12px; color: #16a34a;")

        act.addWidget(self._status_lbl, 1)
        act.addWidget(self._reprint_sel_btn)
        act.addWidget(self._reprint_all_btn)
        rl.addLayout(act)

        splitter.addWidget(right)
        splitter.setSizes([420, 680])
        root.addWidget(splitter, 1)

    # ── Data loading ──────────────────────────────────────────────────────────
    def _load_quotations(self):
        # Show configured ZPL printer in the toolbar
        try:
            from services.pharmacy_label_zpl_printer import _get_pharmacy_printer_name
            pname = _get_pharmacy_printer_name()
        except Exception:
            pname = "(None)"

        if pname and pname != "(None)":
            self._printer_name_lbl.setText(pname)
            self._printer_name_lbl.setStyleSheet(
                "color: #16a34a; font-size: 12px; font-weight: 600;"
            )
        else:
            self._printer_name_lbl.setText("No printer configured")
            self._printer_name_lbl.setStyleSheet(
                "color: #ef4444; font-size: 12px; font-weight: 600;"
            )

        try:
            from models.quotation import get_all_quotations
            self._all_quotations = get_all_quotations()
        except Exception as e:
            QMessageBox.warning(self, "Load Error", f"Failed to load quotations:\n{e}")
            self._all_quotations = []

        self._apply_filter()

        # Pre-select if a quotation_id was supplied
        if self._preselect_id is not None:
            self._preselect(self._preselect_id)

    def _preselect(self, quotation_id: int):
        """Select the row matching quotation_id, clear search so it's visible."""
        for i, q in enumerate(self._filtered):
            if getattr(q, "local_id", None) == quotation_id:
                self._q_list.setCurrentRow(i)
                self._q_list.scrollToItem(self._q_list.item(i))
                return

    # ── Search / filter ───────────────────────────────────────────────────────
    def _on_search_changed(self):
        self._search_timer.start()

    def _apply_filter(self):
        text = self._search_box.text().strip().lower()

        if text:
            self._filtered = [
                q for q in self._all_quotations
                if text in q.name.lower()
                or text in q.customer.lower()
                or (q.reference_number and text in q.reference_number.lower())
            ]
        else:
            self._filtered = list(self._all_quotations)

        self._populate_list()

        # Auto-select if exactly one result
        if len(self._filtered) == 1:
            self._q_list.setCurrentRow(0)

    def _populate_list(self):
        self._q_list.blockSignals(True)
        self._q_list.clear()

        STATUS_COLORS = {
            "Submitted": "#16a34a",
            "Draft":     "#d97706",
            "Cancelled": "#ef4444",
        }

        for q in self._filtered:
            date_str = q.transaction_date[:10] if len(q.transaction_date) >= 10 else q.transaction_date
            text = f"{q.name}   ·   {q.customer}   ·   {date_str}   ·   ${q.grand_total:,.2f}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, q)
            color = STATUS_COLORS.get(q.status, "#64748b")
            item.setForeground(QColor(color))
            font = QFont("Segoe UI", 12)
            item.setFont(font)
            self._q_list.addItem(item)

        self._q_list.blockSignals(False)

        total  = len(self._all_quotations)
        shown  = len(self._filtered)
        self._count_lbl.setText(
            f"{shown} of {total} quotations" if shown != total else f"{total} quotations"
        )

    # ── Selection ─────────────────────────────────────────────────────────────
    def _on_list_selection_changed(self):
        items = self._q_list.selectedItems()
        if not items:
            self._selected_q = None
            self._clear_details()
            return

        q = items[0].data(Qt.UserRole)
        self._selected_q = q
        self._show_details(q)

    def _clear_details(self):
        self._cust_lbl.setText("—")
        self._q_ref_lbl.setText("—")
        self._q_date_lbl.setText("—")
        self._q_total_lbl.setText("—")
        self._pharm_ct_lbl.setText("—")
        self._status_badge.setText("—")
        self._status_badge.setStyleSheet(
            "QLabel { background: #e2e8f0; color: #64748b;"
            " border-radius: 12px; padding: 2px 14px;"
            " font-weight: 700; font-size: 11px; }"
        )
        self._items_tbl.setRowCount(0)
        self._no_items_lbl.setText("Select a quotation to see its pharmacy items")
        self._reprint_sel_btn.setEnabled(False)
        self._reprint_all_btn.setEnabled(False)
        self._set_status("")

    def _show_details(self, q):
        self._cust_lbl.setText(q.customer or "—")
        self._q_ref_lbl.setText(q.name or "—")
        date_str = q.transaction_date[:10] if len(q.transaction_date) >= 10 else q.transaction_date
        self._q_date_lbl.setText(date_str)
        self._q_total_lbl.setText(f"${q.grand_total:,.2f}")

        STATUS_BADGE = {
            "Submitted": ("SUBMITTED", "#16a34a", "white"),
            "Draft":     ("DRAFT",     "#f59e0b", "white"),
            "Cancelled": ("CANCELLED", "#ef4444", "white"),
        }
        text, bg, fg = STATUS_BADGE.get(q.status, (q.status, "#e2e8f0", "#64748b"))
        self._status_badge.setText(text)
        self._status_badge.setStyleSheet(
            f"QLabel {{ background: {bg}; color: {fg};"
            " border-radius: 12px; padding: 2px 14px;"
            " font-weight: 700; font-size: 11px; }"
        )

        # Load pharmacy items
        qid = getattr(q, "local_id", None)
        self._pharm_labels = []
        if qid:
            try:
                from services.pharmacy_label_zpl_printer import (
                    _get_pharmacy_items_from_quotation,
                )
                self._pharm_labels = _get_pharmacy_items_from_quotation(int(qid))
            except Exception:
                self._pharm_labels = []

        self._pharm_ct_lbl.setText(str(len(self._pharm_labels)))
        self._populate_items_table()

        has_items = bool(self._pharm_labels)
        self._reprint_all_btn.setEnabled(has_items)
        self._reprint_sel_btn.setEnabled(False)  # needs a row selected
        self._no_items_lbl.setText(
            "" if has_items else "No pharmacy items on this quotation"
        )
        self._set_status("")

    def _populate_items_table(self):
        self._items_tbl.setRowCount(0)

        for row_idx, lbl in enumerate(self._pharm_labels):
            self._items_tbl.insertRow(row_idx)
            expiry = lbl.get("expiry_date") or ""
            if hasattr(expiry, "isoformat"):
                expiry = expiry.isoformat()[:10]
            else:
                expiry = str(expiry)[:10]

            values = [
                lbl.get("product_name", ""),
                lbl.get("batch_no", ""),
                expiry,
                str(lbl.get("qty", "")),
                lbl.get("uom", ""),
                lbl.get("dosage", ""),
            ]
            for col, val in enumerate(values):
                it = QTableWidgetItem(val)
                it.setData(Qt.UserRole, row_idx)
                self._items_tbl.setItem(row_idx, col, it)
            self._items_tbl.setRowHeight(row_idx, 38)

    def _on_items_table_selection(self):
        has_selection = bool(self._items_tbl.selectedItems())
        self._reprint_sel_btn.setEnabled(
            has_selection and bool(self._pharm_labels)
        )

    # ── Print actions ─────────────────────────────────────────────────────────
    def _reprint_selected(self):
        row = self._items_tbl.currentRow()
        if row < 0 or row >= len(self._pharm_labels):
            self._set_status("Select an item row first.", error=True)
            return
        self._do_print([self._pharm_labels[row]], "1 label")

    def _reprint_all(self):
        if not self._pharm_labels:
            self._set_status("No pharmacy labels to print.", error=True)
            return
        self._do_print(self._pharm_labels, f"{len(self._pharm_labels)} label(s)")

    def _do_print(self, label_list, description: str):
        try:
            from services.pharmacy_label_zpl_printer import (
                _build_zpl_label,
                _send_to_printer,
                _get_pharmacy_printer_name,
            )
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Could not load printer service:\n{e}")
            return

        printer_name = _get_pharmacy_printer_name()
        if printer_name == "(None)" or not printer_name:
            QMessageBox.warning(
                self, "No Printer Configured",
                "No pharmacy label printer is set.\n"
                "Go to Settings → Hardware Settings and select a ZPL printer.",
            )
            return

        printed = 0
        failed  = 0
        for lbl in label_list:
            zpl = _build_zpl_label(
                product_name    = lbl.get("product_name", ""),
                part_no         = lbl.get("part_no", ""),
                qty             = lbl.get("qty", 0),
                uom             = lbl.get("uom", ""),
                price           = lbl.get("price", 0),
                batch_no        = lbl.get("batch_no", ""),
                expiry_date     = lbl.get("expiry_date"),
                dosage          = lbl.get("dosage", ""),
                doctor_name     = lbl.get("doctor_name", ""),
                pharmacist_name = lbl.get("pharmacist_name", ""),
            )
            if _send_to_printer(zpl):
                printed += 1
            else:
                failed += 1

        if failed == 0:
            self._set_status(
                f"✓  Reprinted {description} → '{printer_name}'"
            )
        else:
            self._set_status(
                f"Sent {printed}, failed {failed} — check printer connection.",
                error=True,
            )

    def _set_status(self, text: str, error: bool = False):
        color = "#ef4444" if error else "#16a34a"
        self._status_lbl.setStyleSheet(f"font-size: 12px; color: {color};")
        self._status_lbl.setText(text)

    # ── Keyboard ──────────────────────────────────────────────────────────────
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.accept()
        else:
            super().keyPressEvent(event)