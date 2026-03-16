# =============================================================================
# views/dialogs/stock_file_dialog.py
#
# HOW TO ADD TO main_window.py:
# ──────────────────────────────
# 1. In _build_menubar(), after the Sales menu, add:
#
#       stock_menu = mb.addMenu("📦  Stock")
#       a = QAction("Stock File", self)
#       a.triggered.connect(self._open_stock_file)
#       stock_menu.addAction(a)
#
# 2. Add the opener method to MainWindow:
#
#       def _open_stock_file(self):
#           from views.dialogs.stock_file_dialog import StockFileDialog
#           StockFileDialog(self).exec()
# =============================================================================

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QComboBox, QFrame, QGroupBox,
    QMessageBox, QSizePolicy
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from models.product import (
    get_all_products,
    search_products,
    get_categories,
    create_product,
    update_product,
)

# ── colours ───────────────────────────────────────────────────────────────────
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
SUCCESS   = "#1a7a3c"
SUCCESS_H = "#1f9447"
DANGER    = "#b02020"
DANGER_H  = "#cc2828"
ROW_SEL   = "#1a5fb4"
ROW_ALT   = "#edf3fb"


def _hr():
    ln = QFrame()
    ln.setFrameShape(QFrame.HLine)
    ln.setStyleSheet(f"background: {BORDER}; border: none;")
    ln.setFixedHeight(1)
    return ln


def _btn(text, bg, hov, w=100, h=64):
    b = QPushButton(text)
    b.setFixedSize(w, h)
    b.setCursor(Qt.PointingHandCursor)
    b.setStyleSheet(f"""
        QPushButton {{
            background-color: {bg}; color: {WHITE}; border: none;
            border-radius: 8px; font-size: 11px; font-weight: bold; text-align: center;
        }}
        QPushButton:hover   {{ background-color: {hov}; }}
        QPushButton:pressed {{ background-color: {NAVY_3}; }}
        QPushButton:disabled {{ background-color: {LIGHT}; color: {MUTED}; }}
    """)
    return b


def _combo():
    c = QComboBox()
    c.setFixedHeight(28)
    c.setStyleSheet(f"""
        QComboBox {{
            background-color: {WHITE}; color: {DARK_TEXT};
            border: 1px solid {BORDER}; border-radius: 4px;
            padding: 2px 8px; font-size: 12px;
        }}
        QComboBox::drop-down {{ border: none; width: 20px; }}
        QComboBox QAbstractItemView {{
            background: {WHITE}; border: 1px solid {BORDER};
            selection-background-color: {ACCENT}; selection-color: {WHITE};
        }}
    """)
    return c


# =============================================================================
class StockFileDialog(QDialog):
    """
    Stock File — browse, search, and manage stock items.

    Data comes entirely from models/product.py — no hardcoding.

    self._all_products   : full list loaded from DB (used to reset after search)
    self._shown_products : currently displayed list (filtered / searched)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Stock File")
        self.setMinimumSize(900, 620)
        self.setModal(True)
        self.setStyleSheet(f"""
            QDialog  {{ background-color: {OFF_WHITE}; }}
            QWidget  {{ background-color: {OFF_WHITE}; color: {DARK_TEXT}; font-size: 13px; }}
            QGroupBox {{
                border: 1px solid {BORDER}; border-radius: 6px;
                margin-top: 6px; font-size: 11px; color: {MUTED};
            }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}
        """)
        self._all_products   = []
        self._shown_products = []
        self._category_combo = None   # assigned in _build_ui

        self._build_ui()
        self._load_data()

    # =========================================================================
    # BUILD UI
    # =========================================================================
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(12, 12, 12, 12)

        # title strip
        title = QLabel("Stock File")
        title.setFixedHeight(38)
        title.setStyleSheet(f"""
            font-size: 15px; font-weight: bold; color: {WHITE};
            background-color: {NAVY}; border-radius: 6px; padding: 0 16px;
        """)
        root.addWidget(title)

        # ── search + filter row ───────────────────────────────────────────────
        filter_row = QHBoxLayout()
        filter_row.setSpacing(10)

        # Search Text group
        search_grp = QGroupBox("Search Text")
        search_grp.setFixedWidth(260)
        sg = QGridLayout(search_grp)
        sg.setSpacing(4)
        sg.setContentsMargins(8, 12, 8, 8)

        pn_lbl = QLabel("Part Number")
        pn_lbl.setStyleSheet(f"color: {MUTED}; font-size: 11px; background: transparent;")

        self._search_input = QLineEdit()
        self._search_input.setFixedHeight(28)
        self._search_input.setPlaceholderText("part no. or name…")
        self._search_input.setStyleSheet(f"""
            QLineEdit {{
                background: {WHITE}; border: 1px solid {BORDER};
                border-radius: 4px; font-size: 13px; padding: 2px 8px;
            }}
            QLineEdit:focus {{ border: 2px solid {ACCENT}; }}
        """)
        self._search_input.textChanged.connect(self._do_search)
        self._search_input.returnPressed.connect(self._do_search)

        search_btn = QPushButton("Search")
        search_btn.setFixedSize(70, 28)
        search_btn.setCursor(Qt.PointingHandCursor)
        search_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT}; color: {WHITE}; border: none;
                border-radius: 4px; font-size: 12px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {ACCENT_H}; }}
        """)
        search_btn.clicked.connect(self._do_search)

        sg.addWidget(pn_lbl,             0, 0, 1, 2)
        sg.addWidget(self._search_input, 1, 0)
        sg.addWidget(search_btn,         1, 1)
        filter_row.addWidget(search_grp)

        # Filter By group
        filter_grp = QGroupBox("Filter By")
        fg = QHBoxLayout(filter_grp)
        fg.setSpacing(8)
        fg.setContentsMargins(8, 12, 8, 8)

        # Category — populated from DB
        cat_col = QWidget(); cat_col.setStyleSheet("background: transparent;")
        cat_l = QVBoxLayout(cat_col); cat_l.setSpacing(2); cat_l.setContentsMargins(0,0,0,0)
        cat_lbl = QLabel("Category")
        cat_lbl.setStyleSheet(f"color: {MUTED}; font-size: 11px; background: transparent;")
        self._category_combo = _combo()
        self._category_combo.addItem("All")
        self._category_combo.currentTextChanged.connect(self._apply_category_filter)
        cat_l.addWidget(cat_lbl)
        cat_l.addWidget(self._category_combo)
        fg.addWidget(cat_col)

        # Static filter stubs — wire when product table has type/group fields
        for label in ["Type", "Stock Group", "Group1", "Group2"]:
            col_w = QWidget(); col_w.setStyleSheet("background: transparent;")
            col_l = QVBoxLayout(col_w); col_l.setSpacing(2); col_l.setContentsMargins(0,0,0,0)
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {MUTED}; font-size: 11px; background: transparent;")
            combo = _combo(); combo.addItem("All")
            col_l.addWidget(lbl); col_l.addWidget(combo)
            fg.addWidget(col_w)

        filter_row.addWidget(filter_grp, 1)
        root.addLayout(filter_row)

        # ── Stock table ───────────────────────────────────────────────────────
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Part no.", "Details", "Retail $"])

        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed);  self.table.setColumnWidth(0, 130)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Fixed);  self.table.setColumnWidth(2, 100)

        self.table.verticalHeader().setVisible(True)
        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.verticalHeader().setStyleSheet(f"""
            QHeaderView::section {{
                background-color: {WHITE}; color: {MUTED};
                border: none; border-right: 1px solid {BORDER};
                font-size: 11px; padding: 0 4px;
            }}
        """)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {WHITE}; color: {DARK_TEXT};
                border: 1px solid {BORDER}; gridline-color: {LIGHT};
                font-size: 13px; outline: none;
            }}
            QTableWidget::item           {{ padding: 4px 8px; }}
            QTableWidget::item:selected  {{ background-color: {ROW_SEL}; color: {WHITE}; }}
            QTableWidget::item:alternate {{ background-color: {ROW_ALT}; }}
            QHeaderView::section {{
                background-color: {WHITE}; color: {DARK_TEXT};
                padding: 8px; border: none;
                border-bottom: 2px solid {BORDER};
                border-right: 1px solid {BORDER};
                font-size: 12px; font-weight: bold;
            }}
        """)
        self.table.doubleClicked.connect(self._on_modify)
        self.table.selectionModel().selectionChanged.connect(self._on_selection)
        root.addWidget(self.table, 1)

        # record count
        self._count_lbl = QLabel("0 records")
        self._count_lbl.setStyleSheet(
            f"color: {MUTED}; font-size: 11px; background: transparent;"
        )
        root.addWidget(self._count_lbl)
        root.addWidget(_hr())

        # ── Action buttons ────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._modify_btn  = _btn("✏️\nModify",     SUCCESS, SUCCESS_H)
        self._new_btn     = _btn("➕\nNew",         ACCENT,  ACCENT_H)
        self._clone_btn   = _btn("📋\nClone",       NAVY,    NAVY_2)
        self._picture_btn = _btn("🖼\nPicture",     NAVY_2,  NAVY_3)
        self._history_btn = _btn("ℹ\nHistory",      ACCENT,  ACCENT_H)
        self._labels_btn  = _btn("🏷\nLabels",      NAVY,    NAVY_2)
        self._close_btn   = _btn("✕\nClose (Esc)",  DANGER,  DANGER_H)

        for b in [self._modify_btn, self._clone_btn,
                  self._picture_btn, self._history_btn, self._labels_btn]:
            b.setEnabled(False)

        self._modify_btn.clicked.connect(self._on_modify)
        self._new_btn.clicked.connect(self._on_new)
        self._clone_btn.clicked.connect(self._on_clone)
        self._picture_btn.clicked.connect(
            lambda: self._info("Picture\n\nAttach product image — coming soon"))
        self._history_btn.clicked.connect(self._on_history)
        self._labels_btn.clicked.connect(
            lambda: self._info("Labels\n\nPrint product labels — coming soon"))
        self._close_btn.clicked.connect(self.reject)

        for b in [self._modify_btn, self._new_btn, self._clone_btn,
                  self._picture_btn, self._history_btn, self._labels_btn]:
            btn_row.addWidget(b)
        btn_row.addStretch()
        btn_row.addWidget(self._close_btn)
        root.addLayout(btn_row)

    # =========================================================================
    # DATA  — all reads go through models/product.py, no DB calls here
    # =========================================================================
    def _load_data(self):
        """
        Reload everything from DB. Called on open and after any save.
        """
        self._all_products = get_all_products()

        # populate category combo from DB — no hardcoding
        if self._category_combo:
            self._category_combo.blockSignals(True)
            self._category_combo.clear()
            self._category_combo.addItem("All")
            for cat in get_categories():
                self._category_combo.addItem(cat)
            self._category_combo.blockSignals(False)

        self._render_table(self._all_products)

    def _render_table(self, products: list[dict]):
        """
        Render a list of product dicts into the table.
        Expected dict keys: id, part_no, name, price, stock, category
        """
        self._shown_products = products
        BLANK_ROWS = 3
        self.table.setRowCount(len(products) + BLANK_ROWS)

        for r, p in enumerate(products):
            self.table.setRowHeight(r, 28)
            cols = [
                (p["part_no"],         Qt.AlignLeft  | Qt.AlignVCenter),
                (p["name"],            Qt.AlignLeft  | Qt.AlignVCenter),
                (f"{p['price']:.2f}",  Qt.AlignRight | Qt.AlignVCenter),
            ]
            for c, (val, align) in enumerate(cols):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(align)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                if c == 0:
                    item.setData(Qt.UserRole, p)   # full dict on col 0 for retrieval
                self.table.setItem(r, c, item)

        # blank filler rows
        for r in range(len(products), self.table.rowCount()):
            self.table.setRowHeight(r, 28)
            for c in range(3):
                item = QTableWidgetItem("")
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(r, c, item)

        n = len(products)
        self._count_lbl.setText(f"{n} record{'s' if n != 1 else ''}")

        if products:
            self.table.selectRow(0)

    # =========================================================================
    # SEARCH & FILTER
    # =========================================================================
    def _do_search(self):
        """
        Live search via models/product.search_products(query).
        Then narrows further by active category filter.
        """
        query = self._search_input.text().strip()
        cat   = self._category_combo.currentText() if self._category_combo else "All"

        if not query:
            self._apply_category_filter(cat)
            return

        results = search_products(query)

        if cat and cat != "All":
            results = [p for p in results if p["category"] == cat]

        self._render_table(results)

    def _apply_category_filter(self, category: str):
        """Filter the full list by category without hitting DB again."""
        if not category or category == "All":
            self._render_table(self._all_products)
        else:
            self._render_table(
                [p for p in self._all_products if p["category"] == category]
            )

    # =========================================================================
    # SELECTION
    # =========================================================================
    def _on_selection(self):
        has = self._get_selected_product() is not None
        for b in [self._modify_btn, self._clone_btn,
                  self._picture_btn, self._history_btn, self._labels_btn]:
            b.setEnabled(has)

    def _get_selected_product(self) -> dict | None:
        """Return the full product dict stored on col 0, or None."""
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        item = self.table.item(rows[0].row(), 0)
        if not item:
            return None
        return item.data(Qt.UserRole)

    # =========================================================================
    # BUTTON HANDLERS
    # =========================================================================
    def _on_modify(self):
        """
        TODO: build views/dialogs/stock_edit_dialog.py then replace with:
              from views.dialogs.stock_edit_dialog import StockEditDialog
              p   = self._get_selected_product()
              dlg = StockEditDialog(self, product=p)
              if dlg.exec() == QDialog.Accepted:
                  update_product(p["id"], **dlg.result)
                  self._load_data()
        """
        p = self._get_selected_product()
        if not p:
            return
        self._info(
            f"Modify  ·  {p['part_no']}  —  {p['name']}\n\n"
            f"Price: ${p['price']:.2f}     Stock: {p['stock']}\n"
            f"Category: {p['category'] or '—'}\n\n"
            f"TODO: build StockEditDialog"
        )

    def _on_new(self):
        """
        TODO: build views/dialogs/stock_edit_dialog.py then replace with:
              from views.dialogs.stock_edit_dialog import StockEditDialog
              dlg = StockEditDialog(self, product=None)
              if dlg.exec() == QDialog.Accepted:
                  create_product(**dlg.result)
                  self._load_data()
        """
        self._info("New Product\n\nTODO: build StockEditDialog(product=None)")

    def _on_clone(self):
        """
        TODO: build views/dialogs/stock_edit_dialog.py then replace with:
              from views.dialogs.stock_edit_dialog import StockEditDialog
              p   = self._get_selected_product()
              dlg = StockEditDialog(self, product={**p, "id": None, "part_no": ""})
              if dlg.exec() == QDialog.Accepted:
                  create_product(**dlg.result)
                  self._load_data()
        """
        p = self._get_selected_product()
        if not p:
            return
        self._info(f"Clone  ·  {p['part_no']}\n\nTODO: build StockEditDialog(clone)")

    def _on_history(self):
        """
        TODO: show sale line items for this product:
              from models.sale import get_sale_items_by_product
              history = get_sale_items_by_product(product_id=p["id"])
              # display in a simple read-only table dialog
        """
        p = self._get_selected_product()
        if not p:
            return
        self._info(
            f"History  ·  {p['part_no']}  —  {p['name']}\n\n"
            f"TODO: query sale_items for this product"
        )

    # =========================================================================
    # HELPERS
    # =========================================================================
    def _info(self, msg: str):
        dlg = QMessageBox(self)
        dlg.setWindowTitle("Stock File")
        dlg.setText(msg)
        dlg.setStyleSheet(f"""
            QMessageBox {{ background-color: {WHITE}; }}
            QLabel {{ color: {DARK_TEXT}; font-size: 13px; }}
            QPushButton {{
                background-color: {ACCENT}; color: {WHITE}; border: none;
                border-radius: 6px; padding: 8px 20px; min-width: 70px;
            }}
            QPushButton:hover {{ background-color: {ACCENT_H}; }}
        """)
        dlg.exec()

    # =========================================================================
    # KEYBOARD SHORTCUTS
    # =========================================================================
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reject()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._on_modify()
        else:
            super().keyPressEvent(event)