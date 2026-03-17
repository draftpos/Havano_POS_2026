# =============================================================================
# views/dialogs/customer_dialog.py
# =============================================================================

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QComboBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QMessageBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor

# Import colors from main window or define here
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


def _friendly_db_error(e: Exception) -> str:
    msg = str(e)
    if "REFERENCE constraint" in msg or "FK_" in msg or "foreign key" in msg.lower():
        return "Cannot delete — record is still linked to other data. Remove those links first."
    if "UNIQUE" in msg or "duplicate key" in msg.lower():
        return "A record with that name already exists."
    if "Cannot insert the value NULL" in msg:
        return "A required field is missing."
    return msg


def navy_btn(text, height=36, font_size=12, width=None, color=None, hover=None):
    bg  = color or NAVY
    hov = hover or NAVY_2
    btn = QPushButton(text)
    btn.setFixedHeight(height)
    if width:
        btn.setFixedWidth(width)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {bg}; color: {WHITE}; border: none;
            border-radius: 5px; font-size: {font_size}px; font-weight: bold; padding: 0 14px;
        }}
        QPushButton:hover   {{ background-color: {hov}; }}
        QPushButton:pressed {{ background-color: {NAVY_3}; }}
    """)
    return btn


def hr():
    from PySide6.QtWidgets import QFrame
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet(f"background-color: {BORDER}; border: none;")
    line.setFixedHeight(1)
    return line


def _settings_table_style():
    return f"""
        QTableWidget {{ background:{WHITE}; border:1px solid {BORDER};
            gridline-color:{LIGHT}; outline:none; font-size:13px; }}
        QTableWidget::item           {{ padding:8px; }}
        QTableWidget::item:selected  {{ background-color:{ACCENT}; color:{WHITE}; }}
        QTableWidget::item:alternate {{ background-color:{ROW_ALT}; }}
        QHeaderView::section {{
            background-color:{NAVY}; color:{WHITE};
            padding:10px 8px; border:none; border-right:1px solid {NAVY_2};
            font-size:11px; font-weight:bold;
        }}
    """


class CustomerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Customers")
        self.setMinimumSize(900, 600)
        self.setStyleSheet(f"QDialog {{ background-color:{WHITE}; }}")
        self._build()
        self._reload()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.setContentsMargins(20, 16, 20, 16)

        # Header
        hdr = QWidget()
        hdr.setFixedHeight(44)
        hdr.setStyleSheet(f"background-color:{NAVY}; border-radius:5px;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(16, 0, 16, 0)
        hl.addWidget(QLabel("Customers", styleSheet=f"font-size:15px;font-weight:bold;color:{WHITE};background:transparent;"))
        lay.addWidget(hdr)

        # Search row
        sr = QHBoxLayout()
        sr.setSpacing(8)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search by name, trade name, phone or email...")
        self._search.setFixedHeight(34)
        self._search.textChanged.connect(self._do_search)
        sr.addWidget(self._search)
        lay.addLayout(sr)

        # Customer table
        self._tbl = QTableWidget(0, 7)
        self._tbl.setHorizontalHeaderLabels(["Name", "Type", "Group", "Phone", "Email", "City", "Balance"])
        hh = self._tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        for ci in [1, 2, 3, 4, 5]:
            hh.setSectionResizeMode(ci, QHeaderView.Fixed)
            self._tbl.setColumnWidth(ci, 100)
        hh.setSectionResizeMode(6, QHeaderView.Fixed)
        self._tbl.setColumnWidth(6, 100)

        self._tbl.verticalHeader().setVisible(False)
        self._tbl.setAlternatingRowColors(True)
        self._tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tbl.setStyleSheet(_settings_table_style())
        lay.addWidget(self._tbl, 1)
        lay.addWidget(hr())

        # Form for adding/editing
        form = QGridLayout()
        form.setSpacing(8)

        # Labels
        labels = [
            ("Name *", 0, 0), ("Type", 0, 2), ("Trade Name", 1, 0),
            ("Phone", 1, 2), ("Email", 2, 0), ("City", 2, 2),
            ("House No.", 3, 0), ("Group *", 3, 2), ("Warehouse *", 4, 0),
            ("Cost Center *", 4, 2), ("Price List *", 5, 0)
        ]

        for text, r, c in labels:
            lbl = QLabel(text)
            lbl.setStyleSheet("background:transparent;font-size:12px;color:{MUTED};")
            form.addWidget(lbl, r, c)

        # Input fields
        self._f_name = QLineEdit()
        self._f_name.setPlaceholderText("Customer name *")
        self._f_name.setFixedHeight(32)
        form.addWidget(self._f_name, 0, 1)

        self._f_type = QComboBox()
        self._f_type.addItems(["", "Individual", "Company"])
        self._f_type.setFixedHeight(32)
        form.addWidget(self._f_type, 0, 3)

        self._f_trade = QLineEdit()
        self._f_trade.setPlaceholderText("Trade name")
        self._f_trade.setFixedHeight(32)
        form.addWidget(self._f_trade, 1, 1)

        self._f_phone = QLineEdit()
        self._f_phone.setPlaceholderText("Phone")
        self._f_phone.setFixedHeight(32)
        form.addWidget(self._f_phone, 1, 3)

        self._f_email = QLineEdit()
        self._f_email.setPlaceholderText("Email")
        self._f_email.setFixedHeight(32)
        form.addWidget(self._f_email, 2, 1)

        self._f_city = QLineEdit()
        self._f_city.setPlaceholderText("City")
        self._f_city.setFixedHeight(32)
        form.addWidget(self._f_city, 2, 3)

        self._f_house = QLineEdit()
        self._f_house.setPlaceholderText("House No.")
        self._f_house.setFixedHeight(32)
        form.addWidget(self._f_house, 3, 1)

        self._f_group = QComboBox()
        self._f_group.setFixedHeight(32)
        form.addWidget(self._f_group, 3, 3)

        self._f_wh = QComboBox()
        self._f_wh.setFixedHeight(32)
        form.addWidget(self._f_wh, 4, 1)

        self._f_cc = QComboBox()
        self._f_cc.setFixedHeight(32)
        form.addWidget(self._f_cc, 4, 3)

        self._f_pl = QComboBox()
        self._f_pl.setFixedHeight(32)
        form.addWidget(self._f_pl, 5, 1)

        lay.addLayout(form)

        # Button row
        br = QHBoxLayout()
        br.setSpacing(8)
        self._status = QLabel("")
        self._status.setStyleSheet(f"font-size:12px;color:{SUCCESS};background:transparent;")

        add_btn = navy_btn("Add Customer", height=34, color=SUCCESS, hover=SUCCESS_H)
        edit_btn = navy_btn("Edit Selected", height=34, color=NAVY, hover=NAVY_2)
        del_btn = navy_btn("Delete", height=34, color=DANGER, hover=DANGER_H)
        cls_btn = navy_btn("Close", height=34)

        add_btn.clicked.connect(self._add)
        edit_btn.clicked.connect(self._edit)
        del_btn.clicked.connect(self._delete)
        cls_btn.clicked.connect(self.accept)

        br.addWidget(self._status, 1)
        br.addWidget(add_btn)
        br.addWidget(edit_btn)
        br.addWidget(del_btn)
        br.addWidget(cls_btn)
        lay.addLayout(br)

    def _reload(self):
        self._tbl.setRowCount(0)
        try:
            from models.customer import get_all_customers_with_balance
            custs = get_all_customers_with_balance()
        except Exception:
            custs = []
        self._populate_combos()
        self._populate_table(custs)

    def _do_search(self, query):
        if not query.strip():
            self._reload()
            return
        try:
            from models.customer import search_customers_with_balance
            custs = search_customers_with_balance(query)
        except Exception:
            custs = []
        self._populate_table(custs)

    def _populate_table(self, custs):
        self._tbl.setRowCount(0)
        for c in custs:
            r = self._tbl.rowCount()
            self._tbl.insertRow(r)
            balance = float(c.get("balance", 0))
            balance_text = f"${balance:.2f}" if balance != 0 else ""
            balance_color = DANGER if balance > 0 else SUCCESS if balance < 0 else DARK_TEXT

            for col, (val, align) in enumerate([
                (c["customer_name"], Qt.AlignLeft),
                (c.get("customer_type", ""), Qt.AlignCenter),
                (c.get("customer_group_name", ""), Qt.AlignCenter),
                (c.get("custom_telephone_number", ""), Qt.AlignCenter),
                (c.get("custom_email_address", ""), Qt.AlignLeft),
                (c.get("custom_city", ""), Qt.AlignCenter),
                (balance_text, Qt.AlignRight | Qt.AlignVCenter),
            ]):
                it = QTableWidgetItem(str(val))
                it.setTextAlignment(align)
                if col == 6:
                    it.setForeground(QColor(balance_color))
                it.setData(Qt.UserRole, c)
                self._tbl.setItem(r, col, it)
            self._tbl.setRowHeight(r, 32)

    def _populate_combos(self):
        try:
            from models.customer_group import get_all_customer_groups
            from models.warehouse import get_all_warehouses
            from models.cost_center import get_all_cost_centers
            from models.price_list import get_all_price_lists
            groups = get_all_customer_groups()
            whs = get_all_warehouses()
            ccs = get_all_cost_centers()
            pls = get_all_price_lists()
        except Exception:
            groups = []
            whs = []
            ccs = []
            pls = []

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

    def _add(self):
        name = self._f_name.text().strip()
        if not name:
            self._show_status("Customer name required.", error=True)
            return

        gid = self._f_group.currentData()
        wid = self._f_wh.currentData()
        ccid = self._f_cc.currentData()
        plid = self._f_pl.currentData()

        if not all([gid, wid, ccid, plid]):
            self._show_status("Group, Warehouse, Cost Center and Price List are required.", error=True)
            return

        try:
            from models.customer import create_customer
            create_customer(
                customer_name=name,
                customer_group_id=gid,
                custom_warehouse_id=wid,
                custom_cost_center_id=ccid,
                default_price_list_id=plid,
                customer_type=self._f_type.currentText() or None,
                custom_trade_name=self._f_trade.text().strip(),
                custom_telephone_number=self._f_phone.text().strip(),
                custom_email_address=self._f_email.text().strip(),
                custom_city=self._f_city.text().strip(),
                custom_house_no=self._f_house.text().strip(),
            )
            self._clear_form()
            self._reload()
            self._show_status(f"Customer '{name}' added.")
        except Exception as e:
            self._show_status(_friendly_db_error(e), error=True)

    def _edit(self):
        row = self._tbl.currentRow()
        if row < 0:
            self._show_status("Select a customer to edit.", error=True)
            return

        c = self._tbl.item(row, 0).data(Qt.UserRole)

        # Populate form with selected customer data
        self._f_name.setText(c.get("customer_name", ""))
        self._f_type.setCurrentText(c.get("customer_type", ""))
        self._f_trade.setText(c.get("custom_trade_name", ""))
        self._f_phone.setText(c.get("custom_telephone_number", ""))
        self._f_email.setText(c.get("custom_email_address", ""))
        self._f_city.setText(c.get("custom_city", ""))
        self._f_house.setText(c.get("custom_house_no", ""))

        # Set combo boxes
        self._set_combo_value(self._f_group, c.get("customer_group_id"))
        self._set_combo_value(self._f_wh, c.get("custom_warehouse_id"))
        self._set_combo_value(self._f_cc, c.get("custom_cost_center_id"))
        self._set_combo_value(self._f_pl, c.get("default_price_list_id"))

        # Change add button to update
        sender = self.sender()
        if sender.text() == "Edit Selected":
            sender.setText("Update Customer")
            sender.setStyleSheet(f"""
                QPushButton {{
                    background-color: {NAVY}; color: {WHITE}; border: none;
                    border-radius: 5px; font-size: 12px; font-weight: bold; padding: 0 14px;
                }}
                QPushButton:hover {{ background-color: {NAVY_2}; }}
            """)
            sender.clicked.disconnect()
            sender.clicked.connect(lambda: self._update(c["id"]))

    def _update(self, customer_id):
        name = self._f_name.text().strip()
        if not name:
            self._show_status("Customer name required.", error=True)
            return

        try:
            from models.customer import update_customer
            update_customer(
                customer_id=customer_id,
                customer_name=name,
                customer_type=self._f_type.currentText() or None,
                custom_trade_name=self._f_trade.text().strip(),
                custom_telephone_number=self._f_phone.text().strip(),
                custom_email_address=self._f_email.text().strip(),
                custom_city=self._f_city.text().strip(),
                custom_house_no=self._f_house.text().strip(),
                customer_group_id=self._f_group.currentData(),
                custom_warehouse_id=self._f_wh.currentData(),
                custom_cost_center_id=self._f_cc.currentData(),
                default_price_list_id=self._f_pl.currentData(),
            )
            self._clear_form()
            self._reload()
            self._show_status(f"Customer '{name}' updated.")

            # Reset edit button
            self._reset_edit_button()

        except Exception as e:
            self._show_status(_friendly_db_error(e), error=True)

    def _delete(self):
        row = self._tbl.currentRow()
        if row < 0:
            self._show_status("Select a customer to delete.", error=True)
            return

        c = self._tbl.item(row, 0).data(Qt.UserRole)
        if QMessageBox.question(self, "Delete", f"Delete customer '{c['customer_name']}'?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return

        try:
            from models.customer import delete_customer
            delete_customer(c["id"])
            self._reload()
            self._show_status("Deleted.")
        except Exception as e:
            self._show_status(_friendly_db_error(e), error=True)

    def _set_combo_value(self, combo, value):
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _clear_form(self):
        for field in [self._f_name, self._f_trade, self._f_phone,
                      self._f_email, self._f_city, self._f_house]:
            field.clear()
        self._f_type.setCurrentIndex(0)
        if self._f_group.count() > 0:
            self._f_group.setCurrentIndex(0)
        if self._f_wh.count() > 0:
            self._f_wh.setCurrentIndex(0)
        if self._f_cc.count() > 0:
            self._f_cc.setCurrentIndex(0)
        if self._f_pl.count() > 0:
            self._f_pl.setCurrentIndex(0)

        self._reset_edit_button()

    def _reset_edit_button(self):
        # Find edit button and reset it
        for btn in self.findChildren(QPushButton):
            if btn.text() == "Update Customer":
                btn.setText("Edit Selected")
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {NAVY}; color: {WHITE}; border: none;
                        border-radius: 5px; font-size: 12px; font-weight: bold; padding: 0 14px;
                    }}
                    QPushButton:hover {{ background-color: {NAVY_2}; }}
                """)
                btn.clicked.disconnect()
                btn.clicked.connect(self._edit)
                break

    def _show_status(self, msg, error=False):
        color = DANGER if error else SUCCESS
        self._status.setStyleSheet(f"font-size:12px;color:{color};background:transparent;")
        self._status.setText(msg)
        QTimer.singleShot(4000, lambda: self._status.setText(""))