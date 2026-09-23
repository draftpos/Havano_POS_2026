# views/dialogs/reindexing_dialog.py
import qtawesome as qta
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QCheckBox,
    QPushButton, QFrame, QWidget, QGraphicsDropShadowEffect,
    QApplication, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

from theme import *
from services.credentials import get_system_mode, set_system_mode, clear_session_credentials
from models.company_defaults import invalidate_defaults_cache
from models.saas_snapshot import (
    take_saas_snapshot_once, update_or_take_saas_snapshot, wipe_saas_snapshot, get_saas_snapshot_info,
    log_mode_action, get_recent_mode_audit_logs, restore_saas_defaults_from_snapshot,
    get_company_defaults_mode, get_saas_snapshot_mode, get_sql_settings_mode
)

def _get_wipe_company_defaults_fn():
    try:
        from models.company_defaults import wipe_company_defaults
        return wipe_company_defaults
    except ImportError:
        import importlib
        import models.company_defaults
        importlib.reload(models.company_defaults)
        from models.company_defaults import wipe_company_defaults
        return wipe_company_defaults

class ReindexingDialog(QDialog):
    """
    Clean, borderless, high-end settings dialog for inspecting system mode status,
    managing single-write SaaS company_defaults snapshots, mode reindexing, and audit logs.
    """
    def __init__(self, parent=None, active_username: str = "Admin"):
        super().__init__(parent)
        self.active_username = active_username or "Admin"
        self.reindexed = False
        self.setWindowTitle("System Reindexing")
        self.setFixedSize(650, 690)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self._current_mode = get_system_mode() or "frappe"
        self._build_ui()
        self._refresh_audit_logs()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)

        # Outer Card Container (Clean, Soft Shadow, Borderless)
        card = QFrame()
        card.setObjectName("mainCard")
        card.setStyleSheet("""
            QFrame#mainCard {
                background: #ffffff;
                border-radius: 20px;
                border: none;
            }
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setColor(QColor(15, 23, 42, 60))
        shadow.setYOffset(10)
        card.setGraphicsEffect(shadow)

        cl = QVBoxLayout(card)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)

        # ── Header Bar ──────────────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setFixedHeight(84)
        hdr.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0f172a, stop:0.6 #1e293b, stop:1 #334155);
                border-top-left-radius: 20px;
                border-top-right-radius: 20px;
            }
        """)
        hh = QHBoxLayout(hdr)
        hh.setContentsMargins(24, 0, 18, 0)

        icon_bg = QFrame()
        icon_bg.setFixedSize(42, 42)
        icon_bg.setStyleSheet("background: rgba(255, 255, 255, 0.12); border-radius: 12px; border: none;")
        icon_lay = QVBoxLayout(icon_bg)
        icon_lay.setContentsMargins(0, 0, 0, 0)
        
        self.icon_lbl = QLabel()
        self.icon_lbl.setAlignment(Qt.AlignCenter)
        self.icon_lbl.setPixmap(qta.icon("fa5s.sync-alt", color="#38bdf8").pixmap(22, 22))
        self.icon_lbl.setStyleSheet("background: transparent;")
        icon_lay.addWidget(self.icon_lbl)

        txt_box = QVBoxLayout()
        txt_box.setSpacing(2)
        txt_box.addStretch()

        self.title_lbl = QLabel("System Reindexing & Maintenance")
        self.title_lbl.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.title_lbl.setStyleSheet("color: #ffffff; background: transparent;")

        sub_lbl = QLabel("Mode Synchronization • Defaults Maintenance • Audit Logs")
        sub_lbl.setFont(QFont("Segoe UI", 9))
        sub_lbl.setStyleSheet("color: #94a3b8; background: transparent;")

        txt_box.addWidget(self.title_lbl)
        txt_box.addWidget(sub_lbl)
        txt_box.addStretch()

        hh.addWidget(icon_bg)
        hh.addSpacing(12)
        hh.addLayout(txt_box, 1)

        close_x = QPushButton("✕")
        close_x.setFixedSize(30, 30)
        close_x.setCursor(Qt.PointingHandCursor)
        close_x.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.12);
                color: #f8fafc;
                border: none;
                border-radius: 15px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover { background: rgba(255, 255, 255, 0.25); }
        """)
        close_x.clicked.connect(self.reject)
        hh.addWidget(close_x)

        cl.addWidget(hdr)

        # ── Body Canvas ─────────────────────────────────────────────────────────
        body = QWidget()
        body.setStyleSheet("background: #f8fafc; border-bottom-left-radius: 20px; border-bottom-right-radius: 20px;")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(20, 18, 20, 18)
        bl.setSpacing(14)

        # ── Section 1: Mode Status Cards (Borderless Cards with Pill Badges) ───
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        def _create_status_card(title: str, text_attr: str, color_bg: str = "#f1f5f9"):
            card_w = QFrame()
            card_w.setStyleSheet("""
                QFrame {
                    background: #ffffff;
                    border-radius: 12px;
                    border: none;
                    padding: 10px 14px;
                }
            """)
            # Subtle card shadow
            c_shadow = QGraphicsDropShadowEffect()
            c_shadow.setBlurRadius(15)
            c_shadow.setColor(QColor(15, 23, 42, 12))
            c_shadow.setYOffset(3)
            card_w.setGraphicsEffect(c_shadow)

            l = QVBoxLayout(card_w)
            l.setContentsMargins(0, 0, 0, 0)
            l.setSpacing(6)

            head_lbl = QLabel(title.upper())
            head_lbl.setFont(QFont("Segoe UI", 8, QFont.Bold))
            head_lbl.setStyleSheet("color: #64748b; background: transparent; letter-spacing: 0.5px;")

            val_lbl = QLabel("-")
            val_lbl.setFont(QFont("Segoe UI", 11, QFont.Bold))
            val_lbl.setStyleSheet("color: #0f172a; background: transparent;")

            l.addWidget(head_lbl)
            l.addWidget(val_lbl)
            setattr(self, text_attr, val_lbl)
            return card_w

        top_row.addWidget(_create_status_card("Company Defaults", "lbl_cd_mode"), 1)
        top_row.addWidget(_create_status_card("SaaS Snapshot", "lbl_snap_mode"), 1)
        top_row.addWidget(_create_status_card("JSON Config", "lbl_sql_mode"), 1)
        bl.addLayout(top_row)

        # ── Section 2: Operating Mode Selector & Options ──────────────────────
        sel_card = QFrame()
        sel_card.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border-radius: 14px;
                border: none;
                padding: 14px 16px;
            }
        """)
        s_shadow = QGraphicsDropShadowEffect()
        s_shadow.setBlurRadius(15)
        s_shadow.setColor(QColor(15, 23, 42, 12))
        s_shadow.setYOffset(3)
        sel_card.setGraphicsEffect(s_shadow)

        s_lay = QVBoxLayout(sel_card)
        s_lay.setContentsMargins(0, 0, 0, 0)
        s_lay.setSpacing(10)

        lbl_sel_title = QLabel("System Operating Mode & Options")
        lbl_sel_title.setFont(QFont("Segoe UI", 10, QFont.Bold))
        lbl_sel_title.setStyleSheet("color: #0f172a; background: transparent;")

        self.cbo_mode = QComboBox()
        self.cbo_mode.setFixedHeight(42)
        self.cbo_mode.setFont(QFont("Segoe UI", 10))
        self.cbo_mode.setStyleSheet("""
            QComboBox {
                background: #f1f5f9;
                color: #0f172a;
                border-radius: 10px;
                border: none;
                padding: 0 14px;
                font-weight: 600;
            }
            QComboBox:hover { background: #e2e8f0; }
            QComboBox:focus { background: #ffffff; border: 2px solid #2563eb; }
            QComboBox::drop-down { border: none; padding-right: 10px; }
            QComboBox QAbstractItemView {
                background: #ffffff;
                color: #0f172a;
                selection-background-color: #2563eb;
                selection-color: #ffffff;
                border-radius: 8px;
                border: none;
                outline: none;
                padding: 6px;
            }
        """)

        modes = [
            ("Frappe ERP Mode", "frappe"),
            ("Havano / Odoo Mode", "odoo"),
            ("SaaS Cloud Mode", "saas"),
            ("Offline Mode", "offline"),
        ]

        for idx, (label, val) in enumerate(modes):
            self.cbo_mode.addItem(label, val)
            if val == self._current_mode.lower():
                self.cbo_mode.setCurrentIndex(idx)

        # Checkbox: Wipe Company Defaults table on reindex
        self.chk_wipe_defaults = QCheckBox("Wipe Company Defaults table on reindex")
        self.chk_wipe_defaults.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        self.chk_wipe_defaults.setCursor(Qt.PointingHandCursor)
        self.chk_wipe_defaults.setStyleSheet("""
            QCheckBox {
                color: #475569;
                background: transparent;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 5px;
                border: 1.5px solid #cbd5e1;
                background: #f8fafc;
            }
            QCheckBox::indicator:hover {
                border-color: #2563eb;
            }
            QCheckBox::indicator:checked {
                background: #2563eb;
                border-color: #2563eb;
                image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='white'%3E%3Cpath d='M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z'/%3E%3C/svg%3E");
            }
        """)
        self.chk_wipe_defaults.setChecked(False)
        self.chk_wipe_defaults.setToolTip("When enabled, wipes all stored company_defaults table rows and resets it to a clean state during reindexing.")

        s_lay.addWidget(lbl_sel_title)
        s_lay.addWidget(self.cbo_mode)
        s_lay.addWidget(self.chk_wipe_defaults)
        bl.addWidget(sel_card)

        # ── Section 3: User Action Audit History Table ──────────────────────────
        audit_card = QFrame()
        audit_card.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border-radius: 14px;
                border: none;
                padding: 12px 14px;
            }
        """)
        a_shadow = QGraphicsDropShadowEffect()
        a_shadow.setBlurRadius(15)
        a_shadow.setColor(QColor(15, 23, 42, 12))
        a_shadow.setYOffset(3)
        audit_card.setGraphicsEffect(a_shadow)

        al_lay = QVBoxLayout(audit_card)
        al_lay.setContentsMargins(0, 0, 0, 0)
        al_lay.setSpacing(8)

        lbl_audit_hdr = QLabel("User Action Audit History")
        lbl_audit_hdr.setFont(QFont("Segoe UI", 10, QFont.Bold))
        lbl_audit_hdr.setStyleSheet("color: #0f172a; background: transparent;")
        al_lay.addWidget(lbl_audit_hdr)

        self.tbl_logs = QTableWidget()
        self.tbl_logs.setColumnCount(4)
        self.tbl_logs.setHorizontalHeaderLabels(["Timestamp", "User", "Action", "Details"])
        self.tbl_logs.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_logs.verticalHeader().setVisible(False)
        self.tbl_logs.setShowGrid(False)
        self.tbl_logs.setStyleSheet("""
            QTableWidget {
                background: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 11px;
                color: #334155;
            }
            QTableWidget::item {
                padding: 6px 8px;
                border-bottom: 1px solid #f1f5f9;
            }
            QTableWidget::item:selected {
                background: #eff6ff;
                color: #1d4ed8;
            }
            QHeaderView::section {
                background: #f8fafc;
                color: #64748b;
                font-weight: 700;
                font-size: 10px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                padding: 8px;
                border: none;
                border-bottom: 2px solid #e2e8f0;
            }
        """)
        self.tbl_logs.setFixedHeight(145)
        al_lay.addWidget(self.tbl_logs)
        bl.addWidget(audit_card)

        # Status Notification Label
        self.lbl_status = QLabel("")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.lbl_status.setStyleSheet("color: #16a34a; background: transparent;")
        bl.addWidget(self.lbl_status)

        # ── Bottom Action Button Bar ─────────────────────────────────────────────
        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)

        self.btn_reindex = QPushButton("Reindex & Sync Mode")
        self.btn_reindex.setFixedHeight(44)
        self.btn_reindex.setCursor(Qt.PointingHandCursor)
        self.btn_reindex.setIcon(qta.icon("fa5s.sync", color="#ffffff"))
        self.btn_reindex.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #1d4ed8);
                color: #ffffff;
                font-size: 13px;
                font-weight: 700;
                border-radius: 10px;
                border: none;
                padding: 0 16px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1d4ed8, stop:1 #1e40af);
            }
            QPushButton:pressed { background: #1e40af; }
        """)
        self.btn_reindex.clicked.connect(self._run_reindexing)

        self.btn_wipe_defaults = QPushButton("Wipe Defaults Only")
        self.btn_wipe_defaults.setFixedHeight(44)
        self.btn_wipe_defaults.setCursor(Qt.PointingHandCursor)
        self.btn_wipe_defaults.setIcon(qta.icon("fa5s.trash-alt", color="#ffffff"))
        self.btn_wipe_defaults.setStyleSheet("""
            QPushButton {
                background: #ef4444;
                color: #ffffff;
                font-size: 13px;
                font-weight: 700;
                border-radius: 10px;
                border: none;
                padding: 0 16px;
            }
            QPushButton:hover { background: #dc2626; }
            QPushButton:pressed { background: #b91c1c; }
        """)
        self.btn_wipe_defaults.clicked.connect(self._run_wipe_defaults)

        self.btn_close = QPushButton("Close")
        self.btn_close.setFixedHeight(44)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setStyleSheet("""
            QPushButton {
                background: #f1f5f9;
                color: #334155;
                font-size: 13px;
                font-weight: 700;
                border-radius: 10px;
                border: none;
                padding: 0 16px;
            }
            QPushButton:hover { background: #e2e8f0; color: #0f172a; }
        """)
        self.btn_close.clicked.connect(self.accept)

        btn_box.addWidget(self.btn_reindex, 2)
        btn_box.addWidget(self.btn_wipe_defaults, 2)
        btn_box.addWidget(self.btn_close, 1)
        bl.addLayout(btn_box)

        cl.addWidget(body)
        root.addWidget(card)

    def _refresh_audit_logs(self):
        logs = get_recent_mode_audit_logs(limit=10)
        self.tbl_logs.setRowCount(len(logs))
        for row_idx, log_entry in enumerate(logs):
            ts = str(log_entry.get("timestamp") or "")[:19]
            usr = str(log_entry.get("username") or "Admin")
            act = str(log_entry.get("action") or "")
            dtl = str(log_entry.get("details") or "")

            self.tbl_logs.setItem(row_idx, 0, QTableWidgetItem(ts))
            self.tbl_logs.setItem(row_idx, 1, QTableWidgetItem(usr))
            self.tbl_logs.setItem(row_idx, 2, QTableWidgetItem(act))
            self.tbl_logs.setItem(row_idx, 3, QTableWidgetItem(dtl))

        # Refresh Mode indicators with clean pill badge formatting
        cd_m = get_company_defaults_mode()
        snap_m = get_saas_snapshot_mode()
        sql_m = get_sql_settings_mode()

        self.lbl_cd_mode.setText(f"  {cd_m.upper()}  ")
        self.lbl_cd_mode.setStyleSheet("background: #e0f2fe; color: #0369a1; border-radius: 6px; font-weight: 800; padding: 2px 6px;")

        if snap_m != "none":
            self.lbl_snap_mode.setText(f"  {snap_m.upper()}  ")
            self.lbl_snap_mode.setStyleSheet("background: #dcfce7; color: #15803d; border-radius: 6px; font-weight: 800; padding: 2px 6px;")
        else:
            self.lbl_snap_mode.setText("  NONE  ")
            self.lbl_snap_mode.setStyleSheet("background: #f1f5f9; color: #64748b; border-radius: 6px; font-weight: 700; padding: 2px 6px;")

        self.lbl_sql_mode.setText(f"  {sql_m.upper()}  ")
        self.lbl_sql_mode.setStyleSheet("background: #f3e8ff; color: #7e22ce; border-radius: 6px; font-weight: 800; padding: 2px 6px;")

    def _run_wipe_defaults(self):
        reply = QMessageBox.question(
            self,
            "Confirm Wipe Company Defaults",
            "Are you sure you want to wipe all records from the company_defaults table?\n\n"
            "This will clear stored company details, server URLs, and cached API tokens.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                curr_mode = get_system_mode() or self._current_mode
                _get_wipe_company_defaults_fn()(system_mode=curr_mode)
                wipe_saas_snapshot(username=self.active_username)
                log_mode_action(
                    username=self.active_username,
                    old_mode=curr_mode,
                    new_mode=curr_mode,
                    action="WIPE_COMPANY_DEFAULTS",
                    details="Wiped company_defaults table and SaaS snapshot cleanly"
                )
                self.reindexed = True
                self.lbl_status.setText("✓ Company Defaults table wiped cleanly")
                self._refresh_audit_logs()

                QMessageBox.information(
                    self, "Wipe Complete",
                    "company_defaults table has been wiped.\n\nPlease log in using Admin Email and Password to generate fresh authentication tokens."
                )
            except Exception as err:
                QMessageBox.critical(self, "Wipe Error", f"Failed to wipe company_defaults table:\n{err}")

    def _run_reindexing(self):
        new_mode = self.cbo_mode.currentData()
        old_mode = self._current_mode

        try:
            # 1. Synchronize mode to company_defaults DB & sql_settings.json without full DB wipe
            set_system_mode(new_mode, wipe_full_db=False)
            invalidate_defaults_cache()
            clear_session_credentials()

            # 2. Check if user selected option to wipe company_defaults table
            do_wipe_cd = hasattr(self, "chk_wipe_defaults") and self.chk_wipe_defaults.isChecked()
            if do_wipe_cd:
                _get_wipe_company_defaults_fn()(system_mode=new_mode)

            # 3. Update or wipe SaaS snapshot table through Reindexing
            if new_mode == "saas":
                update_or_take_saas_snapshot(username=self.active_username)
            else:
                wipe_saas_snapshot(username=self.active_username)

            log_mode_action(
                username=self.active_username,
                old_mode=old_mode,
                new_mode=new_mode,
                action="REINDEX_MODE_SYNC",
                details=f"Sync of system_mode to {new_mode.upper()} (Wipe Defaults: {do_wipe_cd})"
            )

            self.reindexed = True

            # 4. Refresh display
            self._current_mode = get_system_mode() or new_mode
            self.lbl_status.setText(f"✓ Synchronized mode to {self._current_mode.upper()}")
            self._refresh_audit_logs()

            QMessageBox.information(
                self, "Reindex Complete",
                f"Mode updated to {self._current_mode.upper()}.\nSynced across Company Defaults DB, SaaS Snapshot & JSON config.\n\nPlease log in with Admin email and password to update session tokens."
            )
        except Exception as err:
            QMessageBox.critical(self, "Reindexing Error", f"Failed to reindex defaults:\n{err}")


