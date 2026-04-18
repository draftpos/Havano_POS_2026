# =============================================================================
# views/dialogs/pharmacy_masters_dialog.py
# Read-only viewer for pharmacy master data (Doctors & Dosages).
# Data is synced from ERPNext by services/doctor_sync_service.py and
# services/dosage_sync_service.py. The POS side only lists/searches/refreshes.
# =============================================================================

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QTabWidget, QFrame,
)
from PySide6.QtCore import Qt
import qtawesome as qta

from models.doctor import list_doctors
from models.dosage import list_dosages
from services.doctor_sync_service import sync_doctors
from services.dosage_sync_service import sync_dosages
from utils.toast import show_toast


# ── colour palette (matches stock_file_dialog / company_defaults_page) ────────
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
ROW_ALT   = "#edf3fb"


# =============================================================================
# Small helpers
# =============================================================================

def _header_btn(text: str, icon_name: str, bg: str, hov: str,
                fg: str = WHITE) -> QPushButton:
    b = QPushButton("  " + text)
    b.setIcon(qta.icon(icon_name, color=fg))
    b.setFixedHeight(34)
    b.setCursor(Qt.PointingHandCursor)
    b.setStyleSheet(f"""
        QPushButton {{
            background: {bg}; color: {fg}; border: none;
            border-radius: 6px; font-size: 12px; font-weight: bold;
            padding: 0 14px;
        }}
        QPushButton:hover   {{ background: {hov}; }}
        QPushButton:pressed {{ background: {NAVY_3}; }}
        QPushButton:disabled {{ background: {LIGHT}; color: {MUTED}; }}
    """)
    return b


def _search_input(placeholder: str = "Search…") -> QLineEdit:
    le = QLineEdit()
    le.setPlaceholderText(placeholder)
    le.setFixedHeight(32)
    le.setStyleSheet(f"""
        QLineEdit {{
            background: {WHITE}; color: {DARK_TEXT};
            border: 1px solid {BORDER}; border-radius: 6px;
            padding: 2px 10px; font-size: 12px;
        }}
        QLineEdit:focus {{ border: 1.5px solid {ACCENT}; }}
    """)
    return le


def _style_table(tbl: QTableWidget):
    tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
    tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
    tbl.setAlternatingRowColors(True)
    tbl.verticalHeader().setVisible(False)
    tbl.setShowGrid(False)
    tbl.setStyleSheet(f"""
        QTableWidget {{
            background: {WHITE}; color: {DARK_TEXT};
            alternate-background-color: {ROW_ALT};
            border: 1px solid {BORDER}; border-radius: 6px;
            gridline-color: {BORDER};
            font-size: 12px;
        }}
        QTableWidget::item {{ padding: 6px; }}
        QTableWidget::item:selected {{ background: {ACCENT}; color: {WHITE}; }}
        QHeaderView::section {{
            background: {NAVY}; color: {WHITE};
            padding: 6px 8px; border: none;
            font-size: 12px; font-weight: bold;
        }}
    """)


# =============================================================================
# Main dialog
# =============================================================================

class PharmacyMastersDialog(QDialog):
    """
    Read-only browser for Doctor and Dosage master data.

    Data comes from the local mirror (models.doctor / models.dosage),
    populated by the doctor_sync_service / dosage_sync_service. Users
    CAN NOT create / edit / delete records here — that all happens in
    ERPNext. The Refresh button triggers a one-shot sync pull.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pharmacy Masters")
        self.resize(900, 600)
        self.setModal(True)
        self.setStyleSheet(f"QDialog {{ background: {OFF_WHITE}; }}")

        # caches for client-side filtering
        self._doctors: list = []
        self._dosages: list = []

        self._build_ui()
        self._load_doctors()
        self._load_dosages()

    # -------------------------------------------------------------------------
    # UI construction
    # -------------------------------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── title bar ────────────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setFixedHeight(48)
        hdr.setStyleSheet(f"background: {NAVY};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(20, 0, 20, 0)
        title = QLabel("Pharmacy Masters")
        title.setStyleSheet(
            f"color: {WHITE}; font-size: 15px; font-weight: bold; background: transparent;"
        )
        hl.addWidget(title)
        hl.addStretch()
        root.addWidget(hdr)

        # ── tabs ─────────────────────────────────────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {BORDER};
                background: {WHITE};
                top: -1px;
            }}
            QTabBar::tab {{
                background: {LIGHT}; color: {DARK_TEXT};
                padding: 8px 18px; border: 1px solid {BORDER};
                border-bottom: none;
                font-size: 12px; font-weight: bold;
            }}
            QTabBar::tab:selected {{
                background: {WHITE}; color: {ACCENT};
                border-bottom: 2px solid {WHITE};
            }}
            QTabBar::tab:hover {{ background: {OFF_WHITE}; }}
        """)

        self._build_doctors_tab()
        self._build_dosages_tab()

        wrap = QWidget()
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(14, 12, 14, 12)
        wl.addWidget(self._tabs)
        root.addWidget(wrap, 1)

        # ── footer close button ──────────────────────────────────────────────
        foot = QFrame()
        foot.setStyleSheet(f"background: {OFF_WHITE}; border-top: 1px solid {BORDER};")
        fl = QHBoxLayout(foot)
        fl.setContentsMargins(14, 10, 14, 10)
        fl.addStretch()
        close_btn = _header_btn("Close", "fa5s.times", DANGER, DANGER_H)
        close_btn.clicked.connect(self.reject)
        fl.addWidget(close_btn)
        root.addWidget(foot)

    # -------------------------------------------------------------------------
    def _build_doctors_tab(self):
        page = QWidget()
        lay  = QVBoxLayout(page)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        # header row — search + refresh
        top = QHBoxLayout()
        top.setSpacing(8)
        search_lbl = QLabel()
        search_lbl.setPixmap(qta.icon("fa5s.search", color=MUTED).pixmap(16, 16))
        self._doctor_search = _search_input("Search doctors…")
        self._doctor_search.textChanged.connect(self._filter_doctors)
        self._doctor_refresh = _header_btn(
            "Refresh from server", "fa5s.sync-alt", ACCENT, ACCENT_H
        )
        self._doctor_refresh.clicked.connect(self._refresh_doctors)

        top.addWidget(search_lbl)
        top.addWidget(self._doctor_search, 1)
        top.addWidget(self._doctor_refresh)
        lay.addLayout(top)

        # table
        self._doctor_table = QTableWidget()
        self._doctor_table.setColumnCount(5)
        self._doctor_table.setHorizontalHeaderLabels(
            ["Full Name", "Practice No", "Qualification", "School", "Phone"]
        )
        _style_table(self._doctor_table)
        hh = self._doctor_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.Stretch)
        hh.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        lay.addWidget(self._doctor_table, 1)

        # count label
        self._doctor_count = QLabel("0 doctors")
        self._doctor_count.setStyleSheet(
            f"color: {MUTED}; font-size: 11px; background: transparent;"
        )
        lay.addWidget(self._doctor_count)

        self._tabs.addTab(page, "Doctors")

    # -------------------------------------------------------------------------
    def _build_dosages_tab(self):
        page = QWidget()
        lay  = QVBoxLayout(page)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        # header row — search + refresh
        top = QHBoxLayout()
        top.setSpacing(8)
        search_lbl = QLabel()
        search_lbl.setPixmap(qta.icon("fa5s.search", color=MUTED).pixmap(16, 16))
        self._dosage_search = _search_input("Search dosages…")
        self._dosage_search.textChanged.connect(self._filter_dosages)
        self._dosage_refresh = _header_btn(
            "Refresh from server", "fa5s.sync-alt", ACCENT, ACCENT_H
        )
        self._dosage_refresh.clicked.connect(self._refresh_dosages)

        top.addWidget(search_lbl)
        top.addWidget(self._dosage_search, 1)
        top.addWidget(self._dosage_refresh)
        lay.addLayout(top)

        # table
        self._dosage_table = QTableWidget()
        self._dosage_table.setColumnCount(2)
        self._dosage_table.setHorizontalHeaderLabels(["Code", "Description"])
        _style_table(self._dosage_table)
        hh = self._dosage_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        lay.addWidget(self._dosage_table, 1)

        # count label
        self._dosage_count = QLabel("0 dosages")
        self._dosage_count.setStyleSheet(
            f"color: {MUTED}; font-size: 11px; background: transparent;"
        )
        lay.addWidget(self._dosage_count)

        self._tabs.addTab(page, "Dosages")

    # -------------------------------------------------------------------------
    # Data loading
    # -------------------------------------------------------------------------
    def _load_doctors(self):
        try:
            self._doctors = list_doctors() or []
        except Exception as e:
            print(f"[PharmacyMasters] list_doctors error: {e}")
            self._doctors = []
        self._render_doctors(self._doctors)

    def _load_dosages(self):
        try:
            self._dosages = list_dosages() or []
        except Exception as e:
            print(f"[PharmacyMasters] list_dosages error: {e}")
            self._dosages = []
        self._render_dosages(self._dosages)

    # -------------------------------------------------------------------------
    # Rendering
    # -------------------------------------------------------------------------
    def _render_doctors(self, docs: list):
        self._doctor_table.setRowCount(len(docs))
        for r, d in enumerate(docs):
            self._doctor_table.setItem(r, 0, QTableWidgetItem(d.full_name or ""))
            self._doctor_table.setItem(r, 1, QTableWidgetItem(d.practice_no or ""))
            self._doctor_table.setItem(r, 2, QTableWidgetItem(d.qualification or ""))
            self._doctor_table.setItem(r, 3, QTableWidgetItem(d.school or ""))
            self._doctor_table.setItem(r, 4, QTableWidgetItem(d.phone or ""))
        self._doctor_count.setText(f"{len(docs)} doctor{'s' if len(docs) != 1 else ''}")

    def _render_dosages(self, doses: list):
        self._dosage_table.setRowCount(len(doses))
        for r, d in enumerate(doses):
            self._dosage_table.setItem(r, 0, QTableWidgetItem(d.code or ""))
            self._dosage_table.setItem(r, 1, QTableWidgetItem(d.description or ""))
        self._dosage_count.setText(f"{len(doses)} dosage{'s' if len(doses) != 1 else ''}")

    # -------------------------------------------------------------------------
    # Filtering (client-side, case-insensitive, any-column substring)
    # -------------------------------------------------------------------------
    def _filter_doctors(self):
        q = (self._doctor_search.text() or "").strip().lower()
        if not q:
            self._render_doctors(self._doctors)
            return
        filtered = [
            d for d in self._doctors
            if q in (d.full_name or "").lower()
            or q in (d.practice_no or "").lower()
            or q in (d.qualification or "").lower()
            or q in (d.school or "").lower()
            or q in (d.phone or "").lower()
        ]
        self._render_doctors(filtered)

    def _filter_dosages(self):
        q = (self._dosage_search.text() or "").strip().lower()
        if not q:
            self._render_dosages(self._dosages)
            return
        filtered = [
            d for d in self._dosages
            if q in (d.code or "").lower()
            or q in (d.description or "").lower()
        ]
        self._render_dosages(filtered)

    # -------------------------------------------------------------------------
    # Refresh handlers
    # -------------------------------------------------------------------------
    def _refresh_doctors(self):
        print("[PharmacyMasters] Refresh doctors — pulling from ERPNext…")
        self._doctor_refresh.setEnabled(False)
        try:
            result = sync_doctors() or {}
            synced = int(result.get("synced", 0))
            errors = result.get("errors") or []
            msg = f"{synced} synced, {len(errors)} error{'s' if len(errors) != 1 else ''}"
            kind = "success" if synced and not errors else ("warn" if errors else "info")
            show_toast(self, f"Doctors: {msg}", duration_ms=3000, kind=kind)
            print(f"[PharmacyMasters] Doctor sync → {msg}")
        except Exception as e:
            print(f"[PharmacyMasters] Doctor sync error: {e}")
            show_toast(self, f"Doctor sync failed: {e}",
                       duration_ms=4000, kind="error")
        finally:
            self._doctor_refresh.setEnabled(True)
            self._load_doctors()
            # preserve any active search filter
            self._filter_doctors()

    def _refresh_dosages(self):
        print("[PharmacyMasters] Refresh dosages — pulling from ERPNext…")
        self._dosage_refresh.setEnabled(False)
        try:
            result = sync_dosages() or {}
            synced = int(result.get("synced", 0))
            errors = result.get("errors") or []
            msg = f"{synced} synced, {len(errors)} error{'s' if len(errors) != 1 else ''}"
            kind = "success" if synced and not errors else ("warn" if errors else "info")
            show_toast(self, f"Dosages: {msg}", duration_ms=3000, kind=kind)
            print(f"[PharmacyMasters] Dosage sync → {msg}")
        except Exception as e:
            print(f"[PharmacyMasters] Dosage sync error: {e}")
            show_toast(self, f"Dosage sync failed: {e}",
                       duration_ms=4000, kind="error")
        finally:
            self._dosage_refresh.setEnabled(True)
            self._load_dosages()
            self._filter_dosages()
