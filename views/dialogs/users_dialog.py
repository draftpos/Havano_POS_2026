# views/dialogs/users_dialog.py
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QComboBox,
    QListWidget, QListWidgetItem,
    QAbstractItemView, QMessageBox, QCheckBox, QFrame,
    QScrollArea, QSizePolicy, QSpinBox, QApplication
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QIcon

# ── Palette ───────────────────────────────────────────────────────────────────
NAVY      = "#0d1f3c"
NAVY_2    = "#162d52"
ACCENT    = "#1a5fb4"
ACCENT_H  = "#1c6dd0"
WHITE     = "#ffffff"
OFF_WHITE = "#f5f8fc"
SURFACE   = "#f0f3f9"
LIGHT     = "#e4eaf4"
BORDER    = "#c8d8ec"
DARK_TEXT = "#0d1f3c"
MUTED     = "#5a7a9a"
GREEN     = "#1a7a3c"
GREEN_H   = "#1f9447"
RED       = "#b02020"
RED_H     = "#cc2828"
AMBER     = "#b7770d"


def _get_defaults() -> dict:
    try:
        from models.company_defaults import get_defaults
        return get_defaults()
    except Exception:
        return {}


# ── Small helpers ─────────────────────────────────────────────────────────────

def _lbl(text, size=11, bold=False, color=MUTED):
    l = QLabel(text)
    w = "700" if bold else "400"
    l.setStyleSheet(
        f"font-size:{size}px; font-weight:{w}; color:{color}; background:transparent;"
    )
    return l


def _input(placeholder="", password=False, read_only=False):
    w = QLineEdit()
    w.setPlaceholderText(placeholder)
    w.setFixedHeight(36)
    if password:
        w.setEchoMode(QLineEdit.Password)
    if read_only:
        w.setReadOnly(True)
    bg = SURFACE if read_only else WHITE
    w.setStyleSheet(f"""
        QLineEdit {{
            background:{bg}; color:{DARK_TEXT};
            border:1.5px solid {BORDER}; border-radius:6px;
            font-size:13px; padding:0 10px;
        }}
        QLineEdit:focus {{ border:1.5px solid {ACCENT}; background:{WHITE}; }}
        QLineEdit:read-only {{ color:{MUTED}; }}
    """)
    return w


def _combo(options, editable=False):
    w = QComboBox()
    if editable:
        w.setEditable(True)
        w.setInsertPolicy(QComboBox.NoInsert)
    w.addItems(options)
    w.setFixedHeight(36)
    w.setStyleSheet(f"""
        QComboBox {{
            background:{WHITE}; color:{DARK_TEXT};
            border:1.5px solid {BORDER}; border-radius:6px;
            font-size:13px; padding:0 10px;
        }}
        QComboBox:focus {{ border:1.5px solid {ACCENT}; }}
        QComboBox QAbstractItemView {{
            background:{WHITE}; border:1px solid {BORDER};
            selection-background-color:{ACCENT}; selection-color:{WHITE};
        }}
    """)
    return w


def _section(text):
    w = QWidget(); w.setStyleSheet("background:transparent;")
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 8, 0, 2); lay.setSpacing(8)
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"font-size:10px; font-weight:800; color:{ACCENT}; letter-spacing:1px; background:transparent;"
    )
    line = QFrame(); line.setFrameShape(QFrame.HLine)
    line.setStyleSheet(f"background:{BORDER}; border:none; max-height:1px;")
    lay.addWidget(lbl); lay.addWidget(line, 1)
    return w


def _field_wrap(label_text, widget):
    w = QWidget(); w.setStyleSheet("background:transparent;")
    lay = QVBoxLayout(w)
    lay.setSpacing(3); lay.setContentsMargins(0, 0, 0, 0)
    lbl = QLabel(label_text)
    lbl.setStyleSheet(
        f"font-size:10px; font-weight:700; color:{NAVY}; "
        f"letter-spacing:0.5px; background:transparent;"
    )
    lay.addWidget(lbl); lay.addWidget(widget)
    return w


def _row_wrap(*widgets, spacing=10):
    w = QWidget(); w.setStyleSheet("background:transparent;")
    lay = QHBoxLayout(w)
    lay.setSpacing(spacing); lay.setContentsMargins(0, 0, 0, 0)
    for ww in widgets:
        lay.addWidget(ww, 1)
    return w


def _combo_set(combo: QComboBox, value: str):
    idx = combo.findText(value, Qt.MatchFixedString)
    if idx >= 0:
        combo.setCurrentIndex(idx)
    elif combo.isEditable() and value:
        combo.setCurrentText(value)


def _combo_get(combo: QComboBox) -> str:
    return (combo.currentText() or "").strip()


# keep old names for backward compat if anything imports them
def _combo_get_value(combo): return _combo_get(combo)
def _combo_set_value(combo, val): return _combo_set(combo, val)


# =============================================================================
# Add / Edit User popup
# =============================================================================

class _UserFormDialog(QDialog):
    """
    Small Frappe-style popup for Add New / Edit User.
    Company, Warehouse, Cost Center pre-filled from company_defaults.
    """

    def __init__(self, parent=None, user: dict = None):
        super().__init__(parent)
        self._user = user  # None = new, dict = edit
        self.saved_user = None
        title = f"Edit User — {user.get('full_name') or user.get('username')}" \
            if user else "New User"
        self.setWindowTitle(title)
        self.setFixedWidth(480)
        self.setSizeGripEnabled(False)
        self.setModal(True)
        self.setStyleSheet(f"QDialog {{ background:{WHITE}; font-family:'Segoe UI',sans-serif; }}")
        self._defs = _get_defaults()
        self._build()
        if user:
            self._populate(user)
        else:
            self._autofill_defaults()

    # ── build ─────────────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # header
        hdr = QWidget()
        hdr.setFixedHeight(48)
        hdr.setStyleSheet(f"background:{NAVY};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(20, 0, 20, 0)
        title_lbl = QLabel(self.windowTitle())
        title_lbl.setStyleSheet(
            f"color:{WHITE}; font-size:14px; font-weight:bold; background:transparent;"
        )
        hl.addWidget(title_lbl); hl.addStretch()
        root.addWidget(hdr)

        # scrollable form
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        form = QWidget(); form.setStyleSheet(f"background:{WHITE};")
        fl = QVBoxLayout(form)
        fl.setContentsMargins(24, 16, 24, 8)
        fl.setSpacing(8)

        # ── Identity ──────────────────────────────────────────────────────────
        fl.addWidget(_section("IDENTITY"))
        self._f_first    = _input("First name *")
        self._f_last     = _input("Last name")
        self._f_email    = _input("Email address")
        fl.addWidget(_row_wrap(
            _field_wrap("FIRST NAME", self._f_first),
            _field_wrap("LAST NAME",  self._f_last),
        ))
        fl.addWidget(_field_wrap("EMAIL", self._f_email))

        # ── Security ──────────────────────────────────────────────────────────
        fl.addWidget(_section("SECURITY"))
        self._f_username = _input("Username (auto-filled)")
        self._f_password = _input("Password (leave blank to keep)", password=True)
        self._f_pin      = _input("4-digit PIN")
        fl.addWidget(_field_wrap("USERNAME", self._f_username))
        fl.addWidget(_row_wrap(
            _field_wrap("PASSWORD", self._f_password),
            _field_wrap("PIN",      self._f_pin),
        ))

        # ── Role ──────────────────────────────────────────────────────────────
        fl.addWidget(_section("ROLE & STATUS"))
        self._f_role   = _combo(["cashier", "admin"])
        self._f_active = _combo(["Active", "Inactive"])
        fl.addWidget(_row_wrap(
            _field_wrap("ROLE",   self._f_role),
            _field_wrap("STATUS", self._f_active),
        ))

        # ── Assignment (auto-filled) ───────────────────────────────────────────
        fl.addWidget(_section("ASSIGNMENT  (auto-filled from defaults)"))
        self._f_company = _input("Company", read_only=False)
        self._f_cost    = _input("Cost center", read_only=False)
        self._f_whouse  = _input("Warehouse", read_only=False)
        fl.addWidget(_field_wrap("COMPANY",     self._f_company))
        fl.addWidget(_row_wrap(
            _field_wrap("COST CENTER", self._f_cost),
            _field_wrap("WAREHOUSE",   self._f_whouse),
        ))

        # ── Permissions ───────────────────────────────────────────────────────
        fl.addWidget(_section("PERMISSIONS & DISCOUNT"))
        self._f_max_disc = QSpinBox()
        self._f_max_disc.setRange(0, 100)
        self._f_max_disc.setSuffix(" %")
        self._f_max_disc.setFixedHeight(36)
        self._f_max_disc.setStyleSheet(
            f"border:1.5px solid {BORDER}; border-radius:6px; padding:4px 8px; font-size:13px;"
        )
        fl.addWidget(_field_wrap("MAX DISCOUNT", self._f_max_disc))

        perm_box = QFrame()
        perm_box.setStyleSheet(
            f"QFrame {{ background:{SURFACE}; border-radius:8px; border:1px solid {BORDER}; }}"
        )
        pl = QVBoxLayout(perm_box)
        pl.setContentsMargins(14, 12, 14, 12); pl.setSpacing(8)

        chk_style = f"""
            QCheckBox {{ font-size:13px; color:{DARK_TEXT}; spacing:10px; background:transparent; }}
            QCheckBox::indicator {{ width:18px; height:18px; border:1.5px solid {BORDER};
                border-radius:4px; background:{WHITE}; }}
            QCheckBox::indicator:checked {{ background:{ACCENT}; border-color:{ACCENT}; }}
        """
        self._p_discount = QCheckBox("Can give discounts")
        self._p_receipt  = QCheckBox("Can process payments")
        self._p_cn       = QCheckBox("Can issue credit notes")
        self._p_reprint  = QCheckBox("Can reprint receipts")
        for chk in [self._p_discount, self._p_receipt, self._p_cn, self._p_reprint]:
            chk.setStyleSheet(chk_style)
            chk.setChecked(True)
            pl.addWidget(chk)

        fl.addWidget(perm_box)
        fl.addStretch()

        scroll.setWidget(form)
        root.addWidget(scroll, 1)

        # footer
        foot = QWidget()
        foot.setStyleSheet(f"background:{SURFACE}; border-top:1px solid {BORDER};")
        ftl = QHBoxLayout(foot)
        ftl.setContentsMargins(24, 12, 24, 14); ftl.setSpacing(10)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("font-size:11px; background:transparent;")

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(36)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{ background:{WHITE}; color:{DARK_TEXT};
                border:1.5px solid {BORDER}; border-radius:6px; font-size:13px; padding:0 18px; }}
            QPushButton:hover {{ background:{LIGHT}; border-color:{ACCENT}; }}
        """)
        cancel_btn.clicked.connect(self.reject)

        self._save_btn = QPushButton("Save User")
        self._save_btn.setFixedHeight(36)
        self._save_btn.setStyleSheet(f"""
            QPushButton {{ background:{GREEN}; color:{WHITE};
                border:none; border-radius:6px;
                font-size:13px; font-weight:bold; padding:0 22px; }}
            QPushButton:hover {{ background:{GREEN_H}; }}
            QPushButton:disabled {{ background:{BORDER}; color:{MUTED}; }}
        """)
        self._save_btn.clicked.connect(self._save)

        ftl.addWidget(self._status_lbl, 1)
        ftl.addWidget(cancel_btn)
        ftl.addWidget(self._save_btn)
        root.addWidget(foot)

        # auto-build username when first/last changes
        self._f_first.textChanged.connect(self._auto_username)
        self._f_last.textChanged.connect(self._auto_username)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _auto_username(self):
        """Suggest username = firstname.lastname while field untouched."""
        first = self._f_first.text().strip().lower().replace(" ", "")
        last  = self._f_last.text().strip().lower().replace(" ", "")
        if first or last:
            self._f_username.setText(f"{first}.{last}" if last else first)

    def _autofill_defaults(self):
        d = self._defs
        self._f_company.setText(d.get("server_company", ""))
        self._f_cost.setText(d.get("server_cost_center", ""))
        self._f_whouse.setText(d.get("server_warehouse", ""))

    def _populate(self, u: dict):
        self._f_first.setText(u.get("first_name") or u.get("full_name", "").split(" ")[0])
        self._f_last.setText(u.get("last_name") or
                             " ".join(u.get("full_name", "").split(" ")[1:]))
        self._f_email.setText(u.get("email", ""))
        self._f_username.setText(u.get("username", ""))
        self._f_pin.setText(u.get("pin", ""))
        self._f_max_disc.setValue(int(u.get("max_discount_percent", 0)))
        _combo_set(self._f_role,   u.get("role", "cashier"))
        self._f_active.setCurrentIndex(0 if u.get("active", True) else 1)
        self._f_company.setText(u.get("company", "") or self._defs.get("server_company", ""))
        self._f_cost.setText(u.get("cost_center", "") or self._defs.get("server_cost_center", ""))
        self._f_whouse.setText(u.get("warehouse", "") or self._defs.get("server_warehouse", ""))
        self._p_discount.setChecked(bool(u.get("allow_discount", True)))
        self._p_receipt.setChecked(bool(u.get("allow_receipt", True)))
        self._p_cn.setChecked(bool(u.get("allow_credit_note", True)))
        self._p_reprint.setChecked(bool(u.get("allow_reprint", True)))

    def _set_status(self, msg, error=False):
        color = RED if error else GREEN
        self._status_lbl.setText(msg)
        self._status_lbl.setStyleSheet(f"font-size:11px; color:{color}; background:transparent;")
        if not error:
            QTimer.singleShot(3000, lambda: self._status_lbl.setText(""))

    # ── save ──────────────────────────────────────────────────────────────────

    def _save(self):
        first    = self._f_first.text().strip()
        last     = self._f_last.text().strip()
        username = self._f_username.text().strip()
        password = self._f_password.text().strip()
        pin      = self._f_pin.text().strip()

        if not first:
            self._set_status("First name is required.", True)
            self._f_first.setFocus(); return
        if not username:
            self._set_status("Username is required.", True)
            self._f_username.setFocus(); return

        full_name = f"{first} {last}".strip()
        self._save_btn.setEnabled(False)

        try:
            from database.db import get_connection
            import hashlib

            data = dict(
                username             = username,
                full_name            = full_name,
                first_name           = first,
                last_name            = last,
                email                = self._f_email.text().strip(),
                pin                  = pin,
                role                 = _combo_get(self._f_role),
                active               = 1 if self._f_active.currentIndex() == 0 else 0,
                company              = self._f_company.text().strip(),
                cost_center          = self._f_cost.text().strip(),
                warehouse            = self._f_whouse.text().strip(),
                max_discount_percent = self._f_max_disc.value(),
                allow_discount       = int(self._p_discount.isChecked()),
                allow_receipt        = int(self._p_receipt.isChecked()),
                allow_credit_note    = int(self._p_cn.isChecked()),
                allow_reprint        = int(self._p_reprint.isChecked()),
            )

            conn = get_connection(); cur = conn.cursor()

            if self._user:
                # UPDATE
                sets   = ", ".join(f"{k}=?" for k in data)
                vals   = list(data.values()) + [self._user["id"]]
                cur.execute(f"UPDATE users SET {sets} WHERE id=?", vals)
                if password:
                    cur.execute("UPDATE users SET password=? WHERE id=?",
                                (hashlib.sha256(password.encode()).hexdigest(),
                                 self._user["id"]))
                conn.commit(); conn.close()
                from models.user import get_user_by_id
                self.saved_user = get_user_by_id(self._user["id"])
            else:
                # INSERT
                pw_hash = hashlib.sha256((password or "changeme").encode()).hexdigest()
                cols = list(data.keys()) + ["password"]
                vals = list(data.values()) + [pw_hash]
                ph   = ", ".join("?" * len(cols))
                cur.execute(
                    f"INSERT INTO users ({', '.join(cols)}) OUTPUT INSERTED.id VALUES ({ph})",
                    vals
                )
                new_id = cur.fetchone()[0]
                conn.commit(); conn.close()
                from models.user import get_user_by_id
                self.saved_user = get_user_by_id(new_id)

            self.accept()

        except Exception as exc:
            import traceback; traceback.print_exc()
            self._set_status(f"Error: {exc}", True)
            self._save_btn.setEnabled(True)


# =============================================================================
# Main Users Dialog  — list view + action buttons
# =============================================================================

class ManageUsersDialog(QDialog):
    def __init__(self, parent=None, current_user=None):
        super().__init__(parent)
        self.current_user = current_user or {}
        self.setWindowTitle("User Accounts")
        self.setMinimumSize(700, 560)
        self.setStyleSheet(f"QDialog {{ background:{SURFACE}; font-family:'Segoe UI',sans-serif; }}")
        self._build()
        self._reload()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(0); root.setContentsMargins(0, 0, 0, 0)

        # header
        hdr = QWidget()
        hdr.setFixedHeight(60)
        hdr.setStyleSheet(f"background:{NAVY};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(24, 0, 20, 0); hl.setSpacing(12)

        title = QLabel("User Accounts")
        title.setStyleSheet(
            f"font-size:18px; font-weight:700; color:{WHITE}; background:transparent;"
        )
        sub = QLabel("Manage staff logins, roles and permissions")
        sub.setStyleSheet(f"font-size:11px; color:rgba(255,255,255,0.55); background:transparent;")

        txt = QVBoxLayout(); txt.setSpacing(2)
        txt.addWidget(title); txt.addWidget(sub)

        add_btn = QPushButton("+ Add User")
        add_btn.setFixedHeight(34)
        add_btn.setStyleSheet(f"""
            QPushButton {{ background:{ACCENT}; color:{WHITE};
                border:none; border-radius:6px;
                font-size:13px; font-weight:bold; padding:0 18px; }}
            QPushButton:hover {{ background:{ACCENT_H}; }}
        """)
        add_btn.clicked.connect(self._add_user)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(32, 32)
        close_btn.setStyleSheet(f"""
            QPushButton {{ background:rgba(255,255,255,0.1); color:{WHITE};
                border-radius:16px; font-weight:bold; font-size:14px; border:none; }}
            QPushButton:hover {{ background:{RED}; }}
        """)
        close_btn.clicked.connect(self.accept)

        hl.addLayout(txt); hl.addStretch()
        hl.addWidget(add_btn); hl.addWidget(close_btn)
        root.addWidget(hdr)

        # body
        body = QWidget()
        body.setStyleSheet(f"background:{SURFACE};")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(20, 16, 20, 16); bl.setSpacing(10)

        # search bar
        sr = QHBoxLayout(); sr.setSpacing(8)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search users by name, username or role…")
        self._search.setFixedHeight(36)
        self._search.setStyleSheet(f"""
            QLineEdit {{ background:{WHITE}; color:{DARK_TEXT};
                border:1.5px solid {BORDER}; border-radius:6px;
                font-size:13px; padding:0 10px; }}
            QLineEdit:focus {{ border:1.5px solid {ACCENT}; }}
        """)
        self._search.textChanged.connect(self._filter)
        sr.addWidget(self._search, 1)
        bl.addLayout(sr)

        # list
        self._list = QListWidget()
        self._list.setAlternatingRowColors(False)
        self._list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._list.setStyleSheet(f"""
            QListWidget {{
                background:{WHITE}; border:1px solid {BORDER};
                border-radius:8px; outline:none;
            }}
            QListWidget::item {{ border-bottom:1px solid {LIGHT}; padding:0; }}
            QListWidget::item:selected {{ background:{LIGHT}; }}
            QListWidget::item:hover {{ background:{OFF_WHITE}; }}
        """)
        self._list.itemDoubleClicked.connect(self._edit_selected)
        bl.addWidget(self._list, 1)

        # bottom actions
        bar = QHBoxLayout(); bar.setSpacing(8)
        self._edit_btn = QPushButton("✏  Edit")
        self._del_btn  = QPushButton("🗑  Delete")
        for btn in [self._edit_btn, self._del_btn]:
            btn.setFixedHeight(34); btn.setEnabled(False)
        self._edit_btn.setStyleSheet(f"""
            QPushButton {{ background:{WHITE}; color:{ACCENT};
                border:1.5px solid {ACCENT}; border-radius:6px;
                font-size:13px; padding:0 18px; }}
            QPushButton:hover {{ background:{LIGHT}; }}
            QPushButton:disabled {{ color:{BORDER}; border-color:{BORDER}; }}
        """)
        self._del_btn.setStyleSheet(f"""
            QPushButton {{ background:{WHITE}; color:{RED};
                border:1.5px solid {RED}; border-radius:6px;
                font-size:13px; padding:0 18px; }}
            QPushButton:hover {{ background:#fff0f0; }}
            QPushButton:disabled {{ color:{BORDER}; border-color:{BORDER}; }}
        """)
        self._edit_btn.clicked.connect(self._edit_selected)
        self._del_btn.clicked.connect(self._delete_selected)
        self._list.itemSelectionChanged.connect(self._on_selection)

        bar.addStretch()
        bar.addWidget(self._edit_btn)
        bar.addWidget(self._del_btn)
        bl.addLayout(bar)

        root.addWidget(body, 1)

    # ── list item card ────────────────────────────────────────────────────────

    def _make_item(self, u: dict) -> QListWidgetItem:
        item = QListWidgetItem()
        item.setData(Qt.UserRole, u)
        item.setSizeHint(__import__('PySide6.QtCore', fromlist=['QSize']).QSize(0, 64))

        card = QWidget()
        card.setStyleSheet("background:transparent;")
        lay = QHBoxLayout(card)
        lay.setContentsMargins(16, 10, 16, 10); lay.setSpacing(14)

        # avatar circle
        av = QLabel((u.get("full_name") or u.get("username") or "?")[0].upper())
        av.setFixedSize(40, 40)
        role_color = ACCENT if u.get("role") == "admin" else GREEN
        av.setStyleSheet(f"""
            background:{role_color}; color:{WHITE};
            border-radius:20px; font-size:16px; font-weight:bold;
        """)
        av.setAlignment(Qt.AlignCenter)

        # text
        info = QVBoxLayout(); info.setSpacing(2)
        name_lbl = QLabel(u.get("full_name") or u.get("username") or "—")
        name_lbl.setStyleSheet(
            f"font-size:14px; font-weight:600; color:{DARK_TEXT}; background:transparent;"
        )
        meta_parts = [
            u.get("username") or "",
            u.get("role", "").upper(),
        ]
        if u.get("company"):
            meta_parts.append(u["company"])
        if u.get("warehouse"):
            meta_parts.append(u["warehouse"])
        meta_lbl = QLabel("  ·  ".join(p for p in meta_parts if p))
        meta_lbl.setStyleSheet(f"font-size:11px; color:{MUTED}; background:transparent;")
        info.addWidget(name_lbl); info.addWidget(meta_lbl)

        # badges
        badges = QVBoxLayout(); badges.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        active = u.get("active", True)
        status_lbl = QLabel("● Active" if active else "○ Inactive")
        status_lbl.setStyleSheet(
            f"font-size:11px; font-weight:600; "
            f"color:{'#1a7a3c' if active else MUTED}; background:transparent;"
        )
        pin_lbl = QLabel(f"PIN: {u.get('pin') or '—'}")
        pin_lbl.setStyleSheet(f"font-size:11px; color:{MUTED}; background:transparent;")
        badges.addWidget(status_lbl); badges.addWidget(pin_lbl)

        lay.addWidget(av)
        lay.addLayout(info, 1)
        lay.addLayout(badges)

        return item, card

    # ── data ──────────────────────────────────────────────────────────────────

    def _reload(self):
        self._all_users = []
        try:
            from models.user import get_all_users
            self._all_users = get_all_users()
        except Exception as e:
            print(f"[UsersDialog] reload error: {e}")
        self._render(self._all_users)

    def _render(self, users: list):
        self._list.clear()
        for u in users:
            item, card = self._make_item(u)
            self._list.addItem(item)
            self._list.setItemWidget(item, card)
        self._on_selection()

    def _filter(self, q: str):
        q = q.lower().strip()
        if not q:
            self._render(self._all_users); return
        self._render([
            u for u in self._all_users
            if q in (u.get("full_name") or "").lower()
            or q in (u.get("username") or "").lower()
            or q in (u.get("role") or "").lower()
            or q in (u.get("company") or "").lower()
        ])

    def _on_selection(self):
        has = self._list.currentItem() is not None
        self._edit_btn.setEnabled(has)
        self._del_btn.setEnabled(has)

    def _selected_user(self) -> dict | None:
        item = self._list.currentItem()
        return item.data(Qt.UserRole) if item else None

    # ── actions ───────────────────────────────────────────────────────────────

    def _add_user(self):
        dlg = _UserFormDialog(self)
        if dlg.exec() == QDialog.Accepted:
            self._reload()

    def _edit_selected(self):
        u = self._selected_user()
        if not u: return
        dlg = _UserFormDialog(self, user=u)
        if dlg.exec() == QDialog.Accepted:
            self._reload()

    def _delete_selected(self):
        u = self._selected_user()
        if not u: return
        reply = QMessageBox.question(
            self, "Delete User",
            f"Permanently delete '{u.get('full_name') or u.get('username')}'?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            from models.user import delete_user
            delete_user(u["id"])
            self._reload()


# backward-compat alias
UsersDialog = ManageUsersDialog