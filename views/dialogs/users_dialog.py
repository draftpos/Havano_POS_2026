# views/dialogs/users_dialog.py
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QMessageBox, QCheckBox, QFrame,
    QScrollArea, QSizePolicy, QSpinBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont

# ── Palette ───────────────────────────────────────────────────────────────────
NAVY    = "#0d1f3c"
ACCENT  = "#1a5fb4"
WHITE   = "#ffffff"
SURFACE = "#f8f9fc"
LIGHT   = "#eef1f7"
BORDER  = "#dde3ef"
MUTED   = "#6b7a99"
GREEN   = "#1a7a3c"
GREEN_H = "#1f9447"
RED     = "#c0392b"
RED_H   = "#e74c3c"


# ── Shared widget styles ──────────────────────────────────────────────────────
def _input(placeholder="", password=False):
    w = QLineEdit()
    w.setPlaceholderText(placeholder)
    w.setFixedHeight(38)
    if password:
        w.setEchoMode(QLineEdit.Password)
    w.setStyleSheet(f"""
        QLineEdit {{
            background: {WHITE};
            color: {NAVY};
            border: 1px solid {BORDER};
            border-radius: 7px;
            font-size: 13px;
            padding: 0 12px;
        }}
        QLineEdit:focus {{ border: 2px solid {ACCENT}; }}
        QLineEdit:disabled {{ background: {SURFACE}; color: {MUTED}; }}
    """)
    return w


def _select(options):
    w = QComboBox()
    w.addItems(options)
    w.setFixedHeight(38)
    w.setStyleSheet(f"""
        QComboBox {{
            background: {WHITE};
            color: {NAVY};
            border: 1px solid {BORDER};
            border-radius: 7px;
            font-size: 13px;
            padding: 0 12px;
        }}
        QComboBox:focus {{ border: 2px solid {ACCENT}; }}
    """)
    return w


def _field_label(text):
    l = QLabel(text)
    l.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {NAVY}; text-transform: uppercase; margin-bottom: 2px;")
    return l


def _section_sep(text):
    w = QWidget(); w.setStyleSheet("background: transparent;")
    lay = QHBoxLayout(w); lay.setContentsMargins(0, 10, 0, 5); lay.setSpacing(10)
    lbl = QLabel(text)
    lbl.setStyleSheet(f"font-size: 10px; font-weight: 800; color: {ACCENT}; letter-spacing: 1px;")
    line = QFrame(); line.setFrameShape(QFrame.HLine)
    line.setStyleSheet(f"background: {BORDER}; border: none;")
    line.setFixedHeight(1)
    lay.addWidget(lbl); lay.addWidget(line, 1)
    return w


def _combo_search(placeholder="— select or type —"):
    w = QComboBox()
    w.setEditable(True)
    w.setInsertPolicy(QComboBox.NoInsert)
    w.lineEdit().setPlaceholderText(placeholder)
    w.setFixedHeight(38)
    w.setStyleSheet(f"""
        QComboBox {{
            background: {WHITE};
            color: {NAVY};
            border: 1px solid {BORDER};
            border-radius: 7px;
            font-size: 13px;
            padding: 0 12px;
        }}
        QComboBox:focus {{ border: 2px solid {ACCENT}; }}
    """)
    return w


def _combo_get_value(combo: QComboBox) -> str:
    return (combo.currentText() or "").strip()


def _field(label, widget):
    w = QWidget(); w.setStyleSheet("background: transparent;")
    lay = QVBoxLayout(w); lay.setSpacing(5); lay.setContentsMargins(0, 0, 0, 0)
    lay.addWidget(_field_label(label))
    lay.addWidget(widget)
    return w


def _row(*widgets, spacing=12):
    w = QWidget(); w.setStyleSheet("background: transparent;")
    lay = QHBoxLayout(w); lay.setSpacing(spacing); lay.setContentsMargins(0, 0, 0, 0)
    for item in widgets:
        lay.addWidget(item, 1)
    return w


class ManageUsersDialog(QDialog):
    def __init__(self, parent=None, current_user=None):
        super().__init__(parent)
        self.current_user = current_user or {}
        self._editing_id = None
        self.setWindowTitle("User Accounts")
        self.setMinimumSize(1100, 750)
        self.setStyleSheet(f"QDialog {{ background: {SURFACE}; }}")
        self._build()
        self._reload()

    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # Header
        hdr = QWidget()
        hdr.setFixedHeight(65)
        hdr.setStyleSheet(f"background: {NAVY};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(25, 0, 20, 0)
        
        t_box = QVBoxLayout()
        t = QLabel("User Management")
        t.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {WHITE};")
        s = QLabel("Setup staff accounts, permissions and assignment")
        s.setStyleSheet(f"font-size: 12px; color: rgba(255,255,255,0.6);")
        t_box.addWidget(t); t_box.addWidget(s)
        
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(35, 35)
        close_btn.setStyleSheet(f"QPushButton {{ background: rgba(255,255,255,0.1); color: {WHITE}; border-radius: 17px; font-weight: bold; }} QPushButton:hover {{ background: {RED}; }}")
        close_btn.clicked.connect(self.accept)

        hl.addLayout(t_box); hl.addStretch(); hl.addWidget(close_btn)
        root.addWidget(hdr)

        body = QWidget()
        body_lay = QHBoxLayout(body)
        body_lay.setSpacing(0)
        body_lay.setContentsMargins(0, 0, 0, 0)

        # Left: Table
        body_lay.addWidget(self._build_list(), 7)
        
        # Right: Form
        body_lay.addWidget(self._build_form(), 4)
        root.addWidget(body, 1)

    def _build_list(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(20, 20, 20, 20)

        bar = QHBoxLayout()
        title = QLabel("System Users")
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {NAVY};")
        
        self._del_btn = QPushButton("Delete User")
        self._del_btn.setFixedHeight(34)
        self._del_btn.setEnabled(False)
        self._del_btn.setStyleSheet(f"QPushButton {{ background: transparent; color: {RED}; border: 1px solid {RED}; border-radius: 6px; font-weight: 600; padding: 0 15px; }} QPushButton:hover {{ background: {RED}; color: {WHITE}; }}")
        self._del_btn.clicked.connect(self._delete_user)
        
        bar.addWidget(title); bar.addStretch(); bar.addWidget(self._del_btn)
        lay.addLayout(bar)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Name", "Username", "Role", "PIN"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setShowGrid(False)
        self.table.setStyleSheet(f"QTableWidget {{ background: {WHITE}; border-radius: 10px; border: 1px solid {BORDER}; }} QTableWidget::item {{ padding: 10px; }}")
        self.table.cellClicked.connect(self._on_row_click)
        lay.addWidget(self.table)
        return w

    def _build_form(self):
        container = QWidget()
        container.setFixedWidth(400)
        container.setStyleSheet(f"background: {WHITE}; border-left: 1px solid {BORDER};")
        outer = QVBoxLayout(container)
        outer.setSpacing(0); outer.setContentsMargins(0, 0, 0, 0)

        fh = QWidget()
        fh.setFixedHeight(50)
        fh.setStyleSheet(f"background: {SURFACE};")
        fhl = QHBoxLayout(fh)
        self._panel_title = QLabel("Add New User")
        self._panel_title.setStyleSheet(f"font-weight: 700; color: {ACCENT};")
        fhl.addWidget(self._panel_title)
        outer.addWidget(fh)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        form = QWidget()
        fl = QVBoxLayout(form); fl.setSpacing(15); fl.setContentsMargins(20, 20, 20, 20)

        # Account Section
        fl.addWidget(_section_sep("ACCOUNT DETAILS"))
        self._f_fullname = _input("Enter full name")
        self._f_username = _input("Username (Login)")
        self._f_email    = _input("Email Address")
        fl.addWidget(_field("Full Name", self._f_fullname))
        fl.addWidget(_field("Username", self._f_username))
        fl.addWidget(_field("Email", self._f_email))

        fl.addWidget(_section_sep("SECURITY"))
        self._f_password = _input("Password", password=True)
        self._f_pin      = _input("Login PIN")
        fl.addWidget(_field("Password", self._f_password))
        fl.addWidget(_field("User PIN", self._f_pin))

        self._f_role = _select(["cashier", "admin"])
        self._f_active = _select(["Yes", "No"])
        fl.addWidget(_row(_field("Role", self._f_role), _field("Is Active", self._f_active)))

        # Assignment Section
        fl.addWidget(_section_sep("ASSIGNMENT"))
        self._f_company = _combo_search("Company")
        self._f_cost    = _combo_search("Cost Center")
        self._f_whouse  = _combo_search("Warehouse")
        fl.addWidget(_field("Company", self._f_company))
        fl.addWidget(_field("Cost Center", self._f_cost))
        fl.addWidget(_field("Warehouse", self._f_whouse))

        # Permissions Section
        fl.addWidget(_section_sep("DISCOUNT & PERMISSIONS"))
        self._f_max_discount = QSpinBox()
        self._f_max_discount.setRange(0, 100); self._f_max_discount.setSuffix(" %")
        self._f_max_discount.setFixedHeight(38)
        self._f_max_discount.setStyleSheet(f"border: 1px solid {BORDER}; border-radius: 6px; padding: 5px;")
        fl.addWidget(_field("Max Discount Limit", self._f_max_discount))

        # SIMPLE CHECKBOXES
        perm_box = QFrame()
        perm_box.setStyleSheet(f"background: {SURFACE}; border-radius: 8px; border: 1px solid {BORDER};")
        p_lay = QVBoxLayout(perm_box)
        p_lay.setSpacing(10); p_lay.setContentsMargins(15, 15, 15, 15)

        checkbox_style = f"""
            QCheckBox {{ font-size: 13px; color: {NAVY}; spacing: 10px; }}
            QCheckBox::indicator {{ width: 20px; height: 20px; border: 1px solid {BORDER}; border-radius: 4px; background: {WHITE}; }}
            QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
        """
        self._perm_discount = QCheckBox("Allowed to give discounts")
        self._perm_receipt  = QCheckBox("Allowed to process payments")
        self._perm_cn       = QCheckBox("Allowed to issue credit notes")
        self._perm_reprint  = QCheckBox("Allowed to reprint receipts")
        
        for chk in [self._perm_discount, self._perm_receipt, self._perm_cn, self._perm_reprint]:
            chk.setStyleSheet(checkbox_style)
            p_lay.addWidget(chk)
        
        fl.addWidget(perm_box)
        scroll.setWidget(form)
        outer.addWidget(scroll)

        footer = QWidget()
        footer.setFixedHeight(70); footer.setStyleSheet(f"background: {SURFACE}; border-top: 1px solid {BORDER};")
        ftl = QHBoxLayout(footer)
        self._status_lbl = QLabel("")
        btn_save = QPushButton("Save User")
        btn_save.setFixedHeight(40); btn_save.setFixedWidth(130)
        btn_save.setStyleSheet(f"QPushButton {{ background: {GREEN}; color: {WHITE}; font-weight: 700; border-radius: 7px; }} QPushButton:hover {{ background: {GREEN_H}; }}")
        btn_save.clicked.connect(self._save_user)
        
        ftl.addWidget(self._status_lbl, 1); ftl.addWidget(btn_save)
        outer.addWidget(footer)

        self._load_assignment_options()
        return container

    def _load_assignment_options(self):
        """Loads UNIQUE values for Company, Warehouse, and Cost Center from existing user records."""
        try:
            from database.db import get_connection
            conn = get_connection()
            cur = conn.cursor()
            
            companies = set()
            cost_centers = set()
            warehouses = set()

            # collect values currently existing in the users table
            cur.execute("SELECT DISTINCT company, cost_center, warehouse FROM users")
            for r in cur.fetchall():
                if r[0]: companies.add(str(r[0]).strip())
                if r[1]: cost_centers.add(str(r[1]).strip())
                if r[2]: warehouses.add(str(r[2]).strip())

            # Fallback to master tables
            try:
                cur.execute("SELECT name FROM companies"); companies.update([str(r[0]).strip() for r in cur.fetchall()])
                cur.execute("SELECT name FROM cost_centers"); cost_centers.update([str(r[0]).strip() for r in cur.fetchall()])
                cur.execute("SELECT name FROM warehouses"); warehouses.update([str(r[0]).strip() for r in cur.fetchall()])
            except: pass

            for cb, data in [(self._f_company, companies), (self._f_cost, cost_centers), (self._f_whouse, warehouses)]:
                cb.clear()
                cb.addItem("")
                cb.addItems(sorted(list(data)))
            conn.close()
        except Exception as e:
            print(f"Error loading options: {e}")

    def _reload(self):
        self.table.setRowCount(0)
        try:
            from models.user import get_all_users
            users = get_all_users()
            for u in users:
                r = self.table.rowCount(); self.table.insertRow(r)
                self.table.setItem(r, 0, QTableWidgetItem(u.get("full_name") or ""))
                self.table.setItem(r, 1, QTableWidgetItem(u.get("username") or ""))
                self.table.setItem(r, 2, QTableWidgetItem(u.get("role", "cashier").upper()))
                self.table.setItem(r, 3, QTableWidgetItem(u.get("pin") or "—"))
                self.table.item(r, 0).setData(Qt.UserRole, u)
                self.table.setRowHeight(r, 45)
        except: pass

    def _on_row_click(self, row, _col):
        u = self.table.item(row, 0).data(Qt.UserRole)
        self._editing_id = u.get("id"); self._del_btn.setEnabled(True)
        self._panel_title.setText(f"Editing: {u.get('username')}")
        self._f_fullname.setText(u.get("full_name") or "")
        self._f_username.setText(u.get("username") or "")
        self._f_email.setText(u.get("email") or "")
        self._f_pin.setText(u.get("pin") or "")
        self._f_max_discount.setValue(int(u.get("max_discount_percent", 0)))
        self._f_role.setCurrentText(u.get("role", "cashier"))
        self._f_active.setCurrentIndex(0 if u.get("active") else 1)
        
        from views.dialogs.users_dialog import _combo_set_value
        _combo_set_value(self._f_company, u.get("company") or "")
        _combo_set_value(self._f_cost, u.get("cost_center") or "")
        _combo_set_value(self._f_whouse, u.get("warehouse") or "")

        self._perm_discount.setChecked(bool(u.get("allow_discount")))
        self._perm_receipt.setChecked(bool(u.get("allow_receipt")))
        self._perm_cn.setChecked(bool(u.get("allow_credit_note")))
        self._perm_reprint.setChecked(bool(u.get("allow_reprint")))

    def _clear_form(self):
        self._editing_id = None; self._panel_title.setText("Add New User")
        for w in [self._f_fullname, self._f_username, self._f_email, self._f_password, self._f_pin]: w.clear()
        self._f_max_discount.setValue(0); self._del_btn.setEnabled(False)
        self._f_company.setCurrentIndex(0); self._f_cost.setCurrentIndex(0); self._f_whouse.setCurrentIndex(0)
        self.table.clearSelection()

    def _save_user(self):
        username = self._f_username.text().strip()
        if not username:
            self._status("Username is required", True)
            return

        from views.dialogs.users_dialog import _combo_get_value
        data = (
            username, self._f_fullname.text().strip(), self._f_email.text().strip(), self._f_pin.text().strip(),
            self._f_role.currentText(), 1 if self._f_active.currentIndex() == 0 else 0,
            _combo_get_value(self._f_company), _combo_get_value(self._f_cost), _combo_get_value(self._f_whouse),
            self._f_max_discount.value(), int(self._perm_discount.isChecked()), int(self._perm_receipt.isChecked()),
            int(self._perm_cn.isChecked()), int(self._perm_reprint.isChecked())
        )

        try:
            from database.db import get_connection
            conn = get_connection(); cur = conn.cursor()
            if self._editing_id:
                cur.execute("""UPDATE users SET username=?, full_name=?, email=?, pin=?, role=?, active=?, company=?, cost_center=?, warehouse=?, max_discount_percent=?, allow_discount=?, allow_receipt=?, allow_credit_note=?, allow_reprint=? WHERE id=?""", (*data, self._editing_id))
                if self._f_password.text():
                    import hashlib
                    cur.execute("UPDATE users SET password=? WHERE id=?", (hashlib.sha256(self._f_password.text().encode()).hexdigest(), self._editing_id))
            else:
                import hashlib
                pw = hashlib.sha256((self._f_password.text() or "1234").encode()).hexdigest()
                cur.execute("""INSERT INTO users (username, full_name, email, pin, role, active, company, cost_center, warehouse, max_discount_percent, allow_discount, allow_receipt, allow_credit_note, allow_reprint, password) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (*data, pw))
            conn.commit(); conn.close()
            self._status("User Saved"); self._reload(); self._clear_form(); self._load_assignment_options()
        except Exception as e: self._status(str(e), True)

    def _delete_user(self):
        if self._editing_id and QMessageBox.question(self, "Confirm", "Delete User?") == QMessageBox.Yes:
            from models.user import delete_user
            delete_user(self._editing_id); self._reload(); self._clear_form(); self._load_assignment_options()

    def _status(self, msg, error=False):
        self._status_lbl.setText(msg)
        self._status_lbl.setStyleSheet(f"color: {RED if error else GREEN}; font-weight: bold;")
        QTimer.singleShot(3000, lambda: self._status_lbl.setText(""))

UsersDialog = ManageUsersDialog