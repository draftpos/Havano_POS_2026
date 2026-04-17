# =============================================================================
# views/dialogs/user_sync_dialog.py
# =============================================================================

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView,
)
from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtGui  import QColor

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
SUCCESS   = "#1a7a3c"
SUCCESS_H = "#1f9447"
GREEN     = "#1e8449"
CREAM     = "#f0e8d0"

_TBL = f"""
    QTableWidget {{
        background:{WHITE}; border:1px solid {BORDER};
        gridline-color:{LIGHT}; font-size:12px; outline:none;
    }}
    QTableWidget::item           {{ padding:8px 10px; }}
    QTableWidget::item:alternate {{ background:{OFF_WHITE}; }}
    QHeaderView::section {{
        background:{CREAM}; color:{NAVY};
        padding:8px 10px; border:none;
        border-right:1px solid {BORDER};
        font-size:11px; font-weight:bold;
    }}
"""


# =============================================================================
# SYNC WORKER
# =============================================================================

class _SyncWorker(QObject):
    finished = Signal(dict)

    def run(self):
        try:
            from services.user_sync_service import sync_users
            r = sync_users()
        except Exception as e:
            r = {"synced": 0, "errors": 1, "error_msg": str(e)}
        self.finished.emit(r)


# =============================================================================
# DIALOG
# =============================================================================

class UserSyncDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("User Sync")
        self.setMinimumSize(720, 500)
        self.setModal(True)
        self.setStyleSheet(f"QDialog {{ background:{OFF_WHITE}; }}")
        self._thread  = None
        self._worker  = None
        self._syncing = False   # simple flag — avoids touching deleted QThread
        self._build()
        self._load_users()

    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = QWidget(); hdr.setFixedHeight(52)
        hdr.setStyleSheet(f"background:{NAVY};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(20, 0, 20, 0)
        title = QLabel("👥  User Sync")
        title.setStyleSheet(
            f"font-size:16px; font-weight:bold; color:{WHITE}; background:transparent;"
        )
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(f"color:{MUTED}; font-size:12px; background:transparent;")
        self._close_btn = QPushButton("✕  Close")
        self._close_btn.setFixedSize(90, 32)
        self._close_btn.setCursor(Qt.PointingHandCursor)
        self._close_btn.setStyleSheet(f"""
            QPushButton {{ background:{DANGER};color:{WHITE};border:none;
                           border-radius:4px;font-size:12px;font-weight:bold; }}
            QPushButton:hover {{ background:{DANGER_H}; }}
        """)
        self._close_btn.clicked.connect(self.reject)
        hl.addWidget(title); hl.addSpacing(12); hl.addWidget(self._status_lbl)
        hl.addStretch(); hl.addWidget(self._close_btn)
        root.addWidget(hdr)

        # ── Body ──────────────────────────────────────────────────────────────
        body = QWidget(); body.setStyleSheet(f"background:{OFF_WHITE};")
        bl = QVBoxLayout(body); bl.setContentsMargins(20,16,20,16); bl.setSpacing(12)

        # User table
        self._tbl = QTableWidget(0, 6)
        self._tbl.setHorizontalHeaderLabels(
            ["Full Name", "Email / Username", "Role", "PIN", "Cost Centre", "Warehouse"]
        )
        hh = self._tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self._tbl.verticalHeader().setVisible(False)
        self._tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tbl.setAlternatingRowColors(True)
        self._tbl.setStyleSheet(_TBL)
        bl.addWidget(self._tbl, 1)

        # Footer: count + button
        foot = QHBoxLayout(); foot.setSpacing(10)
        self._count_lbl = QLabel("Loading…")
        self._count_lbl.setStyleSheet(f"color:{MUTED}; font-size:12px; background:transparent;")

        self._sync_btn = QPushButton("🔄  Sync from Frappe")
        self._sync_btn.setFixedHeight(40)
        self._sync_btn.setCursor(Qt.PointingHandCursor)
        self._sync_btn.setStyleSheet(f"""
            QPushButton {{ background:{ACCENT};color:{WHITE};border:none;
                           border-radius:6px;font-size:13px;font-weight:bold; }}
            QPushButton:hover {{ background:{ACCENT_H}; }}
            QPushButton:disabled {{ background:{LIGHT};color:{MUTED}; }}
        """)
        self._sync_btn.clicked.connect(self._start_sync)

        foot.addWidget(self._count_lbl, 1)
        foot.addWidget(self._sync_btn)
        bl.addLayout(foot)

        root.addWidget(body, 1)

    # ── Load local users ───────────────────────────────────────────────────────

    def _load_users(self):
        self._tbl.setRowCount(0)
        try:
            from models.user import get_all_users
            users = get_all_users()
        except Exception as e:
            self._count_lbl.setText(f"Error loading users: {e}")
            return

        for u in users:
            r = self._tbl.rowCount()
            self._tbl.insertRow(r)
            self._tbl.setRowHeight(r, 36)

            name  = u.get("full_name") or u.get("username") or ""
            email = u.get("email")     or u.get("frappe_user") or u.get("username") or ""
            role  = (u.get("role") or "cashier").capitalize()
            pin   = u.get("pin") or "—"
            cc    = u.get("cost_center") or "—"
            wh    = u.get("warehouse")   or "—"

            for col, val in enumerate([name, email, role, pin, cc, wh]):
                it = QTableWidgetItem(str(val))
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                if col == 2:
                    it.setForeground(QColor(ACCENT if role.lower() == "admin" else MUTED))
                    it.setFont(_bold_font())
                if col == 3 and val == "—":
                    it.setForeground(QColor(MUTED))
                if col == 0 and u.get("synced_from_frappe"):
                    it.setText(f"☁  {val}")
                self._tbl.setItem(r, col, it)

        total  = self._tbl.rowCount()
        synced = sum(1 for u in users if u.get("synced_from_frappe"))
        self._count_lbl.setText(
            f"{total} user(s) — {synced} synced from Frappe, {total - synced} local"
        )

    # ── Sync ──────────────────────────────────────────────────────────────────

    def _start_sync(self):
        # Use a plain bool flag instead of calling isRunning() on a
        # potentially-deleted C++ QThread object
        if self._syncing:
            return

        self._syncing = True
        self._sync_btn.setEnabled(False)
        self._sync_btn.setText("Syncing…")
        self._close_btn.setEnabled(False)
        self._status_lbl.setText("Fetching from Frappe…")
        self._status_lbl.setStyleSheet(f"color:{MUTED}; font-size:12px; background:transparent;")

        self._thread = QThread(self)
        self._worker = _SyncWorker()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_done)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._clear_thread)
        self._thread.start()

    def _clear_thread(self):
        """Called after thread finishes — clears refs so GC can clean up."""
        self._thread  = None
        self._worker  = None
        self._syncing = False

    def _on_done(self, result: dict):
        self._sync_btn.setEnabled(True)
        self._sync_btn.setText("🔄  Sync from Frappe")
        self._close_btn.setEnabled(True)

        n = result.get("synced", 0)
        e = result.get("errors", 0)

        if e and not n:
            self._status_lbl.setText(f"❌ {result.get('error_msg', 'Sync failed')}")
            self._status_lbl.setStyleSheet(f"color:{DANGER}; font-size:12px; background:transparent;")
        else:
            self._status_lbl.setText(f"✅ {n} user(s) synced")
            self._status_lbl.setStyleSheet(
                f"color:{GREEN}; font-size:12px; font-weight:bold; background:transparent;"
            )

        self._load_users()


def _bold_font():
    from PySide6.QtGui import QFont
    f = QFont(); f.setBold(True); return f