# =============================================================================
# views/dialogs/item_group_dialog.py
# Full-page dialog: shows Item Groups from local DB + syncs from Frappe API
# =============================================================================

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QMessageBox, QFrame, QGroupBox
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QColor

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
MID       = "#8fa8c8"
SUCCESS   = "#1a7a3c"
SUCCESS_H = "#1f9447"
DANGER    = "#b02020"
DANGER_H  = "#cc2828"
ROW_ALT   = "#edf3fb"
AMBER     = "#b06000"


from services.site_config import get_host as _get_host
FRAPPE_API_URL = (
    _get_host() + "/api/resource/Item%20Group"
    '?fields=["name","item_group_name","parent_item_group"]&limit_page_length=500'
)


# =============================================================================
# BACKGROUND SYNC WORKER  — reads api_key/api_secret from auth_service session
# =============================================================================
class SyncWorker(QThread):
    finished = Signal(dict)
    progress = Signal(str)

    def run(self):
        self.progress.emit("Reading auth session …")

        # ── 1. Pull credentials from the active login session ─────────────────
        api_key = api_secret = ""
        try:
            from services.auth_service import get_session
            session    = get_session()
            api_key    = session.get("api_key")    or ""
            api_secret = session.get("api_secret") or ""
        except Exception as e:
            self.progress.emit(f"⚠  Auth session error: {e}")

        # ── 2. Fetch from Frappe API ───────────────────────────────────────────
        import urllib.request, json

        headers = {"Accept": "application/json"}
        if api_key and api_secret:
            # Frappe uses "token key:secret" — NOT Basic auth
            headers["Authorization"] = f"token {api_key}:{api_secret}"

        self.progress.emit("Fetching from site …")
        try:
            req = urllib.request.Request(FRAPPE_API_URL, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                payload = json.loads(resp.read().decode())
        except Exception as e:
            self.finished.emit({"inserted": 0, "updated": 0, "errors": [str(e)]})
            return

        records = payload.get("data", [])
        if not records:
            self.finished.emit({
                "inserted": 0, "updated": 0,
                "errors": [
                    f"API returned 0 records. "
                    f"Response keys: {list(payload.keys())}. "
                    f"Make sure you are logged in online."
                ]
            })
            return

        # ── 3. Pass already-fetched records straight into the model ───────────
        self.progress.emit(f"Saving {len(records)} groups to local DB …")
        try:
            from models.item_group import sync_from_api
            result = sync_from_api(api_key, api_secret, prefetched=records)
        except Exception as e:
            result = {"inserted": 0, "updated": 0, "errors": [str(e)]}

        self.finished.emit(result)


# =============================================================================
# HELPERS
# =============================================================================
def _hr():
    ln = QFrame()
    ln.setFrameShape(QFrame.HLine)
    ln.setStyleSheet(f"background:{BORDER}; border:none;")
    ln.setFixedHeight(1)
    return ln


def _navy_btn(text, height=34, color=None, hover=None, width=None):
    bg  = color or NAVY
    hov = hover or NAVY_2
    b   = QPushButton(text)
    b.setFixedHeight(height)
    if width:
        b.setFixedWidth(width)
    b.setCursor(Qt.PointingHandCursor)
    b.setStyleSheet(f"""
        QPushButton {{
            background-color:{bg}; color:{WHITE}; border:none;
            border-radius:5px; font-size:12px; font-weight:bold; padding:0 14px;
        }}
        QPushButton:hover   {{ background-color:{hov}; }}
        QPushButton:pressed {{ background-color:{NAVY_3}; }}
    """)
    return b


def _tbl_style():
    return f"""
        QTableWidget {{
            background:{WHITE}; border:1px solid {BORDER};
            gridline-color:{LIGHT}; outline:none; font-size:13px;
        }}
        QTableWidget::item           {{ padding:6px 8px; }}
        QTableWidget::item:selected  {{ background:{ACCENT}; color:{WHITE}; }}
        QTableWidget::item:alternate {{ background:{ROW_ALT}; }}
        QHeaderView::section {{
            background:{NAVY}; color:{WHITE};
            padding:9px 8px; border:none; border-right:1px solid {NAVY_2};
            font-size:11px; font-weight:bold;
        }}
    """


# =============================================================================
# MAIN DIALOG
# =============================================================================
class ItemGroupDialog(QDialog):
    def __init__(self, parent=None, user=None):
        super().__init__(parent)
        self.user         = user or {}
        self._sync_worker = None
        self.setWindowTitle("Item Groups")
        self.setMinimumSize(900, 620)
        self.setModal(True)
        self.setStyleSheet(f"QDialog {{ background:{OFF_WHITE}; }}")
        self._build()
        self._reload()

    # =========================================================================
    # BUILD UI
    # =========================================================================
    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # ── header ────────────────────────────────────────────────────────────
        hdr = QWidget(); hdr.setFixedHeight(54)
        hdr.setStyleSheet(f"background:{NAVY};")
        hl  = QHBoxLayout(hdr); hl.setContentsMargins(20, 0, 20, 0); hl.setSpacing(12)

        title = QLabel("Item Groups")
        title.setStyleSheet(
            f"font-size:18px; font-weight:bold; color:{WHITE}; background:transparent;"
        )

        self._api_badge = QLabel("● API: site")
        self._api_badge.setStyleSheet(
            f"font-size:11px; color:{MID}; background:transparent;"
        )

        close_btn = QPushButton("✕  Close")
        close_btn.setFixedSize(90, 32); close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background:{DANGER}; color:{WHITE}; border:none;
                border-radius:4px; font-size:12px; font-weight:bold;
            }}
            QPushButton:hover {{ background:{DANGER_H}; }}
        """)
        close_btn.clicked.connect(self.accept)

        hl.addWidget(title)
        hl.addWidget(self._api_badge)
        hl.addStretch()
        hl.addWidget(close_btn)
        root.addWidget(hdr)

        # ── body ──────────────────────────────────────────────────────────────
        body = QWidget(); body.setStyleSheet(f"background:{OFF_WHITE};")
        bl   = QVBoxLayout(body); bl.setSpacing(10); bl.setContentsMargins(16, 14, 16, 14)

        # search + sync row
        top_row = QHBoxLayout(); top_row.setSpacing(8)

        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍  Search by name or parent group …")
        self._search.setFixedHeight(34)
        self._search.setStyleSheet(f"""
            QLineEdit {{
                background:{WHITE}; border:2px solid {ACCENT};
                border-radius:5px; font-size:13px; padding:0 10px; color:{DARK_TEXT};
            }}
        """)
        self._search.textChanged.connect(self._on_search)

        self._sync_btn = _navy_btn("⟳  Sync from API", color=ACCENT, hover=ACCENT_H, height=34)
        self._sync_btn.setFixedWidth(160)
        self._sync_btn.clicked.connect(self._on_sync)

        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet(
            f"color:{MUTED}; font-size:12px; background:transparent;"
        )

        top_row.addWidget(self._search, 1)
        top_row.addWidget(self._count_lbl)
        top_row.addWidget(self._sync_btn)
        bl.addLayout(top_row)

        # sync status bar
        self._status_lbl = QLabel("")
        self._status_lbl.setFixedHeight(22)
        self._status_lbl.setStyleSheet(
            f"font-size:12px; color:{SUCCESS}; background:transparent; padding-left:2px;"
        )
        bl.addWidget(self._status_lbl)

        # ── main table ────────────────────────────────────────────────────────
        self._tbl = QTableWidget(0, 5)
        self._tbl.setHorizontalHeaderLabels(
            ["#", "Name (ID)", "Item Group Name", "Parent Group", "Source"]
        )
        hh = self._tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed);  self._tbl.setColumnWidth(0, 45)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.Stretch)
        hh.setSectionResizeMode(4, QHeaderView.Fixed);  self._tbl.setColumnWidth(4, 80)
        self._tbl.verticalHeader().setVisible(False)
        self._tbl.setAlternatingRowColors(True)
        self._tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tbl.setSelectionMode(QAbstractItemView.SingleSelection)
        self._tbl.setStyleSheet(_tbl_style())
        self._tbl.doubleClicked.connect(self._on_row_double_click)
        bl.addWidget(self._tbl, 1)

        bl.addWidget(_hr())

        # ── add / edit form ───────────────────────────────────────────────────
        form_box = QGroupBox("Add / Edit Item Group")
        form_box.setStyleSheet(f"""
            QGroupBox {{
                font-size:12px; font-weight:bold; color:{NAVY};
                border:1px solid {BORDER}; border-radius:6px;
                margin-top:6px; padding:10px 12px;
                background:{WHITE};
            }}
            QGroupBox::title {{
                subcontrol-origin:margin; left:12px; padding:0 4px;
                background:{WHITE};
            }}
        """)
        fl = QHBoxLayout(form_box); fl.setSpacing(10)

        def _field(placeholder, width=None):
            e = QLineEdit()
            e.setPlaceholderText(placeholder)
            e.setFixedHeight(32)
            if width:
                e.setFixedWidth(width)
            e.setStyleSheet(f"""
                QLineEdit {{
                    background:{WHITE}; border:1px solid {BORDER};
                    border-radius:4px; padding:0 8px; font-size:13px; color:{DARK_TEXT};
                }}
                QLineEdit:focus {{ border:2px solid {ACCENT}; }}
            """)
            return e

        self._f_name    = _field("Name (required) *")
        self._f_igname  = _field("Item Group Name")
        self._f_parent  = _field("Parent Item Group")
        self._hidden_id = None

        self._save_btn   = _navy_btn("💾  Save",   color=SUCCESS, hover=SUCCESS_H, height=32)
        self._clear_btn  = _navy_btn("✕  Clear",  color=NAVY_2,  height=32, width=80)
        self._delete_btn = _navy_btn("🗑  Delete", color=DANGER,  hover=DANGER_H,  height=32, width=90)
        self._delete_btn.setEnabled(False)

        self._save_btn.clicked.connect(self._on_save)
        self._clear_btn.clicked.connect(self._clear_form)
        self._delete_btn.clicked.connect(self._on_delete)

        self._form_status = QLabel("")
        self._form_status.setStyleSheet(
            f"font-size:12px; background:transparent; color:{SUCCESS};"
        )

        fl.addWidget(QLabel("Name:"),       0)
        fl.addWidget(self._f_name,         2)
        fl.addWidget(QLabel("Group Name:"), 0)
        fl.addWidget(self._f_igname,       2)
        fl.addWidget(QLabel("Parent:"),     0)
        fl.addWidget(self._f_parent,       2)
        fl.addWidget(self._save_btn)
        fl.addWidget(self._delete_btn)
        fl.addWidget(self._clear_btn)
        fl.addWidget(self._form_status, 1)

        for lbl in form_box.findChildren(QLabel):
            if lbl.text() in ("Name:", "Group Name:", "Parent:"):
                lbl.setStyleSheet(
                    f"font-size:12px; color:{MUTED}; background:transparent;"
                )

        bl.addWidget(form_box)
        root.addWidget(body, 1)

    # =========================================================================
    # DATA
    # =========================================================================
    def _reload(self, query: str = ""):
        try:
            from models.item_group import get_all_item_groups, search_item_groups
            rows = search_item_groups(query) if query else get_all_item_groups()
        except Exception as e:
            rows = []
            self._set_status(f"DB error: {e}", error=True)

        self._tbl.setRowCount(0)
        for g in rows:
            r = self._tbl.rowCount(); self._tbl.insertRow(r)

            id_item = QTableWidgetItem(str(g["id"]))
            id_item.setTextAlignment(Qt.AlignCenter)
            id_item.setData(Qt.UserRole, g)

            source_synced = bool(g.get("synced_from_api"))
            src_item = QTableWidgetItem("API" if source_synced else "Local")
            src_item.setTextAlignment(Qt.AlignCenter)
            src_item.setForeground(QColor(ACCENT if source_synced else MUTED))

            self._tbl.setItem(r, 0, id_item)
            self._tbl.setItem(r, 1, QTableWidgetItem(str(g.get("name", ""))))
            self._tbl.setItem(r, 2, QTableWidgetItem(str(g.get("item_group_name", ""))))
            self._tbl.setItem(r, 3, QTableWidgetItem(str(g.get("parent_item_group", ""))))
            self._tbl.setItem(r, 4, src_item)
            self._tbl.setRowHeight(r, 30)

        count = len(rows)
        self._count_lbl.setText(f"{count} group{'s' if count != 1 else ''}")

    def _on_search(self, text):
        self._reload(text.strip())

    # =========================================================================
    # FORM ACTIONS
    # =========================================================================
    def _on_row_double_click(self, index):
        row = index.row()
        g   = self._tbl.item(row, 0).data(Qt.UserRole)
        if not g:
            return
        self._hidden_id = g["id"]
        self._f_name.setText(g.get("name", ""))
        self._f_igname.setText(g.get("item_group_name", ""))
        self._f_parent.setText(g.get("parent_item_group", ""))
        self._delete_btn.setEnabled(True)
        self._form_status.setText("Editing — make changes then press Save.")
        self._form_status.setStyleSheet(
            f"font-size:12px; background:transparent; color:{AMBER};"
        )
        self._f_name.setFocus()

    def _clear_form(self):
        self._hidden_id = None
        self._f_name.clear(); self._f_igname.clear(); self._f_parent.clear()
        self._delete_btn.setEnabled(False)
        self._form_status.setText("")

    def _on_save(self):
        name   = self._f_name.text().strip()
        igname = self._f_igname.text().strip()
        parent = self._f_parent.text().strip()

        if not name:
            self._set_form_status("Name is required.", error=True)
            self._f_name.setFocus()
            return

        try:
            if self._hidden_id:
                from models.item_group import update_item_group
                update_item_group(self._hidden_id, name, igname, parent)
                self._set_form_status(f"'{name}' updated.")
            else:
                from models.item_group import create_item_group
                create_item_group(name, igname, parent)
                self._set_form_status(f"'{name}' added.")
            self._clear_form()
            self._reload(self._search.text().strip())
        except Exception as e:
            msg = str(e)
            if "UNIQUE" in msg or "duplicate" in msg.lower():
                msg = f"'{name}' already exists."
            self._set_form_status(msg, error=True)

    def _on_delete(self):
        if not self._hidden_id:
            return
        name = self._f_name.text().strip() or f"ID {self._hidden_id}"
        reply = QMessageBox.question(
            self, "Delete",
            f"Delete item group '{name}'?\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        try:
            from models.item_group import delete_item_group
            delete_item_group(self._hidden_id)
            self._clear_form()
            self._reload(self._search.text().strip())
            self._set_form_status(f"'{name}' deleted.")
        except Exception as e:
            self._set_form_status(str(e), error=True)

    # =========================================================================
    # API SYNC
    # =========================================================================
    def _on_sync(self):
        if self._sync_worker and self._sync_worker.isRunning():
            return

        # Warn if no active credentials
        try:
            from services.auth_service import get_session
            session = get_session()
            if not (session.get("api_key") and session.get("api_secret")):
                self._set_status(
                    "⚠  Not logged in online — sync may return 0 results. "
                    "Login first for credentials.",
                    error=True
                )
        except Exception:
            pass

        self._sync_btn.setEnabled(False)
        self._sync_btn.setText("Syncing …")
        self._set_status("Connecting to site …")

        self._sync_worker = SyncWorker()
        self._sync_worker.progress.connect(self._set_status)
        self._sync_worker.finished.connect(self._on_sync_done)
        self._sync_worker.start()

    def _on_sync_done(self, result: dict):
        self._sync_btn.setEnabled(True)
        self._sync_btn.setText("⟳  Sync from API")

        ins  = result.get("inserted", 0)
        upd  = result.get("updated",  0)
        errs = result.get("errors",   [])

        if errs and ins == 0 and upd == 0:
            self._set_status(f"Sync failed: {errs[0]}", error=True)
            self._api_badge.setStyleSheet(
                f"font-size:11px; color:{DANGER}; background:transparent;"
            )
        else:
            msg = f"✅  Sync complete — {ins} inserted, {upd} updated"
            if errs:
                msg += f", {len(errs)} error(s)"
            self._set_status(msg)
            self._api_badge.setStyleSheet(
                f"font-size:11px; color:{SUCCESS}; background:transparent;"
            )

        self._reload(self._search.text().strip())
        QTimer.singleShot(8000, lambda: self._set_status(""))

    # =========================================================================
    # STATUS HELPERS
    # =========================================================================
    def _set_status(self, msg: str, error: bool = False):
        color = DANGER if error else SUCCESS
        self._status_lbl.setStyleSheet(
            f"font-size:12px; color:{color}; background:transparent; padding-left:2px;"
        )
        self._status_lbl.setText(msg)

    def _set_form_status(self, msg: str, error: bool = False):
        color = DANGER if error else SUCCESS
        self._form_status.setStyleSheet(
            f"font-size:12px; background:transparent; color:{color};"
        )
        self._form_status.setText(msg)
        QTimer.singleShot(5000, lambda: self._form_status.setText(""))