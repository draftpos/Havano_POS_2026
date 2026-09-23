"""
System Updates Settings View — Clean & Minimalist Edition
──────────────────────────────────────────────────────────
A modern, ultra-clean UI for inspecting, downloading, and installing Havano POS updates.
"""
from __future__ import annotations
import os
import tempfile
from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QFrame, QMessageBox, QApplication,
    QScrollArea, QGraphicsDropShadowEffect, QSizePolicy
)
from PySide6.QtGui import QFont, QColor
import qtawesome as qta
from packaging.version import Version

from theme import *
import main
from updater import (
    _fetch_version_info,
    _nc_download_url,
    DownloadThread,
    launch_installer,
)


class _UpdateCheckWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)

    def run(self):
        try:
            info = _fetch_version_info()
            self.finished.emit(info)
        except Exception as e:
            self.error.emit(str(e))


class UpdateSettingsView(QWidget):
    """Ultra-clean, modern System Updates page under Settings -> Configurations."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setStyleSheet(f"QWidget {{ background: #f8fafc; font-family: 'Segoe UI', -apple-system, sans-serif; }}")
        self.current_version = getattr(main, "APP_VERSION", "2.0.8.36")
        self.latest_info: Optional[dict] = None
        self.check_worker: Optional[_UpdateCheckWorker] = None
        self.download_thread: Optional[DownloadThread] = None
        self._installer_path: Optional[str] = None
        self._last_checked_str = "Never"

        self._build_ui()
        QTimer.singleShot(250, self._start_check_updates)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Scroll Area for smooth responsiveness ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: #f8fafc; border: none; }")

        container = QWidget()
        container.setStyleSheet("background: #f8fafc;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(36, 28, 36, 36)
        layout.setSpacing(24)

        # ── 1. Top Header Bar (Title & Quick Action) ──
        header_row = QHBoxLayout()
        header_row.setSpacing(16)

        title_col = QVBoxLayout()
        title_col.setSpacing(4)

        title_label = QLabel("Software Updates")
        title_label.setStyleSheet("color: #0f172a; font-size: 22px; font-weight: 700; background: transparent;")
        
        self._subtitle_label = QLabel("Check for new features, performance improvements, and security patches.")
        self._subtitle_label.setStyleSheet("color: #64748b; font-size: 13px; background: transparent;")

        title_col.addWidget(title_label)
        title_col.addWidget(self._subtitle_label)
        header_row.addLayout(title_col)

        header_row.addStretch()

        # Check for Updates Button
        self._check_btn = QPushButton(" Check for Updates")
        self._check_btn.setFixedHeight(40)
        self._check_btn.setCursor(Qt.PointingHandCursor)
        try:
            self._check_btn.setIcon(qta.icon("fa5s.sync-alt", color="#334155"))
            self._check_btn.setIconSize(QSize(14, 14))
        except Exception:
            pass
        self._check_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #334155;
                border: 1px solid #cbd5e1;
                border-radius: 9px;
                font-size: 13px;
                font-weight: 600;
                padding: 0 18px;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
                border-color: #94a3b8;
                color: #0f172a;
            }
            QPushButton:disabled {
                background-color: #e2e8f0;
                color: #94a3b8;
                border-color: #e2e8f0;
            }
        """)
        self._check_btn.clicked.connect(self._start_check_updates)
        header_row.addWidget(self._check_btn)

        layout.addLayout(header_row)

        # ── 2. Dynamic Content Area (States: Loading, Up to Date, Update Available, Error) ──
        self._content_stack = QVBoxLayout()
        self._content_stack.setSpacing(20)

        # State A: Loading Card
        self._loading_card = self._build_loading_card()
        self._content_stack.addWidget(self._loading_card)

        # State B: Up to Date Zen Card
        self._up_to_date_card = self._build_up_to_date_card()
        self._up_to_date_card.hide()
        self._content_stack.addWidget(self._up_to_date_card)

        # State C: Update Available Card
        self._update_available_card = self._build_update_available_card()
        self._update_available_card.hide()
        self._content_stack.addWidget(self._update_available_card)

        # State D: Error Card
        self._error_card = self._build_error_card()
        self._error_card.hide()
        self._content_stack.addWidget(self._error_card)

        layout.addLayout(self._content_stack)

        # ── 3. System Details Grid ──
        sys_info_card = self._build_system_info_card()
        layout.addWidget(sys_info_card)

        layout.addStretch()
        scroll.setWidget(container)
        root.addWidget(scroll)

    # ── State Cards ────────────────────────────────────────────────────────────

    def _build_loading_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 14px;
                padding: 36px;
            }
        """)
        l = QVBoxLayout(card)
        l.setAlignment(Qt.AlignCenter)
        l.setSpacing(12)

        icon_lbl = QLabel()
        try:
            icon_lbl.setPixmap(qta.icon("fa5s.spinner", color="#3b82f6", animation=qta.Pulse(icon_lbl)).pixmap(32, 32))
        except Exception:
            pass
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("background: transparent; border: none;")
        l.addWidget(icon_lbl)

        txt = QLabel("Checking for available updates...")
        txt.setAlignment(Qt.AlignCenter)
        txt.setStyleSheet("color: #475569; font-size: 14px; font-weight: 600; background: transparent; border: none;")
        l.addWidget(txt)
        return card

    def _build_up_to_date_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 14px;
                padding: 36px 32px;
            }
        """)
        l = QVBoxLayout(card)
        l.setAlignment(Qt.AlignCenter)
        l.setSpacing(10)

        # Green Check Icon Circle
        icon_box = QLabel()
        try:
            icon_box.setPixmap(qta.icon("fa5s.check-circle", color="#10b981").pixmap(48, 48))
        except Exception:
            pass
        icon_box.setAlignment(Qt.AlignCenter)
        icon_box.setStyleSheet("background: transparent; border: none;")
        l.addWidget(icon_box)

        title = QLabel("Havano POS is Up to Date")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #0f172a; font-size: 18px; font-weight: 700; background: transparent; border: none;")
        l.addWidget(title)

        self._up_to_date_desc = QLabel(f"You are running version v{self.current_version}. Your system has the latest features and security patches.")
        self._up_to_date_desc.setAlignment(Qt.AlignCenter)
        self._up_to_date_desc.setStyleSheet("color: #64748b; font-size: 13px; background: transparent; border: none;")
        l.addWidget(self._up_to_date_desc)

        self._last_checked_lbl = QLabel("Last checked: Just now")
        self._last_checked_lbl.setAlignment(Qt.AlignCenter)
        self._last_checked_lbl.setStyleSheet("color: #94a3b8; font-size: 12px; margin-top: 4px; background: transparent; border: none;")
        l.addWidget(self._last_checked_lbl)

        return card

    def _build_update_available_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame#UpdateHeroCard {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 14px;
            }
        """)
        card.setObjectName("UpdateHeroCard")

        l = QVBoxLayout(card)
        l.setContentsMargins(28, 24, 28, 24)
        l.setSpacing(20)

        # ── Row 1: Hero Header (Icon + Title + Urgency Badge + CTA) ──
        top_row = QHBoxLayout()
        top_row.setSpacing(16)

        # Blue accent icon
        icon_box = QFrame()
        icon_box.setFixedSize(50, 50)
        icon_box.setStyleSheet("background-color: #eff6ff; border-radius: 12px; border: none;")
        ibl = QVBoxLayout(icon_box)
        ibl.setContentsMargins(0, 0, 0, 0)
        icon_lbl = QLabel()
        try:
            icon_lbl.setPixmap(qta.icon("fa5s.arrow-alt-circle-up", color="#2563eb").pixmap(26, 26))
        except Exception:
            pass
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("background: transparent; border: none;")
        ibl.addWidget(icon_lbl)
        top_row.addWidget(icon_box)

        # Titles
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        ver_badge_row = QHBoxLayout()
        ver_badge_row.setSpacing(8)

        self._update_ver_title = QLabel("Havano POS v2.0.8.37 is Available")
        self._update_ver_title.setStyleSheet("color: #0f172a; font-size: 18px; font-weight: 700; background: transparent; border: none;")
        ver_badge_row.addWidget(self._update_ver_title)

        self._badge_lbl = QLabel("Optional Update")
        self._badge_lbl.setFixedHeight(22)
        self._badge_lbl.setStyleSheet("""
            background-color: #ecfdf5;
            color: #059669;
            font-size: 11px;
            font-weight: 700;
            border-radius: 6px;
            padding: 2px 8px;
            border: 1px solid #a7f3d0;
        """)
        ver_badge_row.addWidget(self._badge_lbl)
        ver_badge_row.addStretch()

        self._update_ver_subtitle = QLabel(f"Current version: v{self.current_version} • Ready to install")
        self._update_ver_subtitle.setStyleSheet("color: #64748b; font-size: 13px; background: transparent; border: none;")

        title_box.addLayout(ver_badge_row)
        title_box.addWidget(self._update_ver_subtitle)
        top_row.addLayout(title_box)

        top_row.addStretch()

        # Primary CTA button
        self._main_action_btn = QPushButton("Download & Install")
        self._main_action_btn.setFixedHeight(42)
        self._main_action_btn.setCursor(Qt.PointingHandCursor)
        try:
            self._main_action_btn.setIcon(qta.icon("fa5s.download", color="#ffffff"))
            self._main_action_btn.setIconSize(QSize(14, 14))
        except Exception:
            pass
        self._main_action_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a5fb4, stop:1 #2563eb);
                color: #ffffff;
                border: none;
                border-radius: 9px;
                font-size: 13px;
                font-weight: 700;
                padding: 0 22px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #164e96, stop:1 #1d4ed8);
            }
            QPushButton:disabled {
                background: #cbd5e1;
                color: #ffffff;
            }
        """)
        self._main_action_btn.clicked.connect(self._on_action_install_clicked)
        top_row.addWidget(self._main_action_btn)

        l.addLayout(top_row)

        # ── Row 2: Progress Section (Hidden until downloading) ──
        self._progress_container = QWidget()
        self._progress_container.setStyleSheet("background: transparent; border: none;")
        pl = QVBoxLayout(self._progress_container)
        pl.setContentsMargins(0, 4, 0, 0)
        pl.setSpacing(6)

        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(8)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #e2e8f0;
                border: none;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #10b981);
                border-radius: 4px;
            }
        """)
        pl.addWidget(self._progress_bar)

        self._progress_status_lbl = QLabel("Downloading update...")
        self._progress_status_lbl.setStyleSheet("color: #475569; font-size: 12px; font-weight: 600; background: transparent; border: none;")
        pl.addWidget(self._progress_status_lbl)

        self._progress_container.hide()
        l.addWidget(self._progress_container)

        # ── Row 3: Release Notes Box (Clean modern layout) ──
        notes_box = QFrame()
        notes_box.setStyleSheet("""
            QFrame {
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                padding: 16px;
            }
        """)
        nbl = QVBoxLayout(notes_box)
        nbl.setContentsMargins(0, 0, 0, 0)
        nbl.setSpacing(8)

        n_hdr = QLabel("WHAT'S NEW IN THIS VERSION")
        n_hdr.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 700; letter-spacing: 0.8px; background: transparent; border: none;")
        nbl.addWidget(n_hdr)

        self._notes_label = QLabel("Loading release notes...")
        self._notes_label.setWordWrap(True)
        self._notes_label.setStyleSheet("color: #334155; font-size: 13px; line-height: 1.5; background: transparent; border: none;")
        nbl.addWidget(self._notes_label)

        l.addWidget(notes_box)

        # ── Row 4: Package Metadata Footer ──
        meta_row = QHBoxLayout()
        meta_row.setSpacing(20)

        self._package_lbl = QLabel("Package: --")
        self._package_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; background: transparent; border: none;")
        meta_row.addWidget(self._package_lbl)

        meta_row.addStretch()

        dist_lbl = QLabel("Source: Official Havano CDN")
        dist_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; background: transparent; border: none;")
        meta_row.addWidget(dist_lbl)

        l.addLayout(meta_row)

        return card

    def _build_error_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #fee2e2;
                border-radius: 14px;
                padding: 28px;
            }
        """)
        l = QVBoxLayout(card)
        l.setAlignment(Qt.AlignCenter)
        l.setSpacing(10)

        icon_lbl = QLabel()
        try:
            icon_lbl.setPixmap(qta.icon("fa5s.exclamation-circle", color="#ef4444").pixmap(36, 36))
        except Exception:
            pass
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("background: transparent; border: none;")
        l.addWidget(icon_lbl)

        self._err_msg_lbl = QLabel("Unable to connect to the update server.")
        self._err_msg_lbl.setAlignment(Qt.AlignCenter)
        self._err_msg_lbl.setStyleSheet("color: #b91c1c; font-size: 14px; font-weight: 600; background: transparent; border: none;")
        l.addWidget(self._err_msg_lbl)

        retry_btn = QPushButton(" Retry Connection")
        retry_btn.setFixedHeight(36)
        retry_btn.setCursor(Qt.PointingHandCursor)
        try:
            retry_btn.setIcon(qta.icon("fa5s.redo-alt", color="#ffffff"))
        except Exception:
            pass
        retry_btn.setStyleSheet("""
            QPushButton {
                background-color: #b91c1c;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 12px;
                font-weight: 600;
                padding: 0 16px;
            }
            QPushButton:hover { background-color: #991b1b; }
        """)
        retry_btn.clicked.connect(self._start_check_updates)
        l.addWidget(retry_btn, alignment=Qt.AlignCenter)

        return card

    def _build_system_info_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 14px;
                padding: 20px 24px;
            }
        """)
        l = QVBoxLayout(card)
        l.setSpacing(14)

        hdr = QLabel("SYSTEM & CHANNEL INFORMATION")
        hdr.setStyleSheet("color: #64748b; font-size: 11px; font-weight: 700; letter-spacing: 0.8px; background: transparent; border: none;")
        l.addWidget(hdr)

        grid = QHBoxLayout()
        grid.setSpacing(24)

        # Col 1: Installed Version
        col1 = QVBoxLayout(); col1.setSpacing(3)
        lbl1 = QLabel("Installed Version"); lbl1.setStyleSheet("color: #94a3b8; font-size: 11px; background: transparent; border: none;")
        val1 = QLabel(f"v{self.current_version}"); val1.setStyleSheet("color: #0f172a; font-size: 14px; font-weight: 700; background: transparent; border: none;")
        col1.addWidget(lbl1); col1.addWidget(val1)
        grid.addLayout(col1)

        # Col 2: Release Channel
        col2 = QVBoxLayout(); col2.setSpacing(3)
        lbl2 = QLabel("Release Channel"); lbl2.setStyleSheet("color: #94a3b8; font-size: 11px; background: transparent; border: none;")
        val2 = QLabel("Stable (Production)"); val2.setStyleSheet("color: #0f172a; font-size: 14px; font-weight: 700; background: transparent; border: none;")
        col2.addWidget(lbl2); col2.addWidget(val2)
        grid.addLayout(col2)

        # Col 3: Architecture
        col3 = QVBoxLayout(); col3.setSpacing(3)
        lbl3 = QLabel("Platform"); lbl3.setStyleSheet("color: #94a3b8; font-size: 11px; background: transparent; border: none;")
        val3 = QLabel("Windows x64"); val3.setStyleSheet("color: #0f172a; font-size: 14px; font-weight: 700; background: transparent; border: none;")
        col3.addWidget(lbl3); col3.addWidget(val3)
        grid.addLayout(col3)

        # Col 4: Last Checked
        col4 = QVBoxLayout(); col4.setSpacing(3)
        lbl4 = QLabel("Last Verified"); lbl4.setStyleSheet("color: #94a3b8; font-size: 11px; background: transparent; border: none;")
        self._last_verified_val = QLabel("Checking..."); self._last_verified_val.setStyleSheet("color: #0f172a; font-size: 14px; font-weight: 700; background: transparent; border: none;")
        col4.addWidget(lbl4); col4.addWidget(self._last_verified_val)
        grid.addLayout(col4)

        grid.addStretch()
        l.addLayout(grid)
        return card

    # ── Handlers & Logic ───────────────────────────────────────────────────────

    def _start_check_updates(self):
        self._check_btn.setEnabled(False)
        self._check_btn.setText(" Checking...")

        self._loading_card.show()
        self._up_to_date_card.hide()
        self._update_available_card.hide()
        self._error_card.hide()

        self.check_worker = _UpdateCheckWorker()
        self.check_worker.finished.connect(self._on_check_finished)
        self.check_worker.error.connect(self._on_check_error)
        self.check_worker.start()

    def _on_check_finished(self, info: dict):
        self._check_btn.setEnabled(True)
        self._check_btn.setText(" Check for Updates")
        self._loading_card.hide()
        self.latest_info = info

        now_str = datetime.now().strftime("%I:%M %p")
        self._last_checked_lbl.setText(f"Last checked: Today at {now_str}")
        self._last_verified_val.setText(now_str)

        try:
            remote_ver = info.get("version", "0.0.0")
            is_newer = Version(remote_ver) > Version(self.current_version)
        except Exception as e:
            self._show_error(f"Invalid version string from server: {e}")
            return

        if not is_newer:
            self._up_to_date_desc.setText(f"You are running version v{self.current_version}. Your system is completely up to date.")
            self._up_to_date_card.show()
            return

        # New version available!
        is_mandatory = bool(info.get("mandatory", False) or info.get("is_mandatory", False))
        self._update_ver_title.setText(f"Havano POS v{remote_ver} is Ready")
        self._update_ver_subtitle.setText(f"Installed: v{self.current_version}   →   Available: v{remote_ver}")

        if is_mandatory:
            self._badge_lbl.setText("Mandatory Update")
            self._badge_lbl.setStyleSheet("""
                background-color: #fef2f2;
                color: #dc2626;
                font-size: 11px;
                font-weight: 700;
                border-radius: 6px;
                padding: 2px 8px;
                border: 1px solid #fecaca;
            """)
        else:
            self._badge_lbl.setText("Optional Update")
            self._badge_lbl.setStyleSheet("""
                background-color: #ecfdf5;
                color: #059669;
                font-size: 11px;
                font-weight: 700;
                border-radius: 6px;
                padding: 2px 8px;
                border: 1px solid #a7f3d0;
            """)

        notes = info.get("release_notes", "").strip() or "General performance improvements, bug fixes, and stability updates."
        self._notes_label.setText(notes)

        filename = info.get("installer_filename", "")
        self._package_lbl.setText(f"Installer: {filename}")

        # Check if installer is already downloaded in temp
        dest = os.path.join(tempfile.gettempdir(), filename) if filename else ""
        if dest and os.path.exists(dest):
            self._installer_path = dest
            self._main_action_btn.setText("Install Update Now")
            try:
                self._main_action_btn.setIcon(qta.icon("fa5s.play-circle", color="#ffffff"))
            except Exception:
                pass
        else:
            self._main_action_btn.setText("Download & Install")
            try:
                self._main_action_btn.setIcon(qta.icon("fa5s.download", color="#ffffff"))
            except Exception:
                pass

        self._progress_container.hide()
        self._update_available_card.show()

    def _on_check_error(self, err_msg: str):
        self._check_btn.setEnabled(True)
        self._check_btn.setText(" Check for Updates")
        self._last_verified_val.setText("Check Failed")
        self._show_error(f"Could not connect to update repository:\n{err_msg}")

    def _show_error(self, msg: str):
        self._loading_card.hide()
        self._up_to_date_card.hide()
        self._update_available_card.hide()
        self._err_msg_lbl.setText(msg)
        self._error_card.show()

    # ── Download & Install Flow ───────────────────────────────────────────────

    def _on_action_install_clicked(self):
        if not self.latest_info:
            return

        filename = self.latest_info.get("installer_filename", "")
        if not filename:
            QMessageBox.warning(self, "Error", "No installer filename found in update manifest.")
            return

        dest = os.path.join(tempfile.gettempdir(), filename)
        if os.path.exists(dest):
            self._installer_path = dest
            self._launch_installer()
            return

        # Start download
        url = _nc_download_url(filename)
        self._main_action_btn.setEnabled(False)
        self._check_btn.setEnabled(False)

        self._progress_container.show()
        self._progress_bar.setValue(0)
        self._progress_status_lbl.setText("Connecting to update repository...")

        self.download_thread = DownloadThread(url, dest)
        self.download_thread.progress.connect(self._on_download_progress)
        self.download_thread.finished.connect(self._on_download_finished)
        self.download_thread.error.connect(self._on_download_error)
        self.download_thread.start()

    def _on_download_progress(self, value: int):
        if value < 0:
            mb = (-value) / (1024 * 1024)
            if self._progress_bar.maximum() != 0:
                self._progress_bar.setRange(0, 0)
            self._progress_status_lbl.setText(f"Downloading update... {mb:.1f} MB downloaded")
        else:
            if self._progress_bar.maximum() == 0:
                self._progress_bar.setRange(0, 100)
            self._progress_bar.setValue(value)
            self._progress_status_lbl.setText(f"Downloading update... {value}% complete")

    def _on_download_finished(self, path: str):
        self._installer_path = path
        self._progress_bar.setValue(100)
        self._progress_status_lbl.setText("Download complete! Launching installer...")

        self._main_action_btn.setText("Install Update Now")
        self._main_action_btn.setEnabled(True)
        self._check_btn.setEnabled(True)

        reply = QMessageBox.question(
            self,
            "Install Update",
            "The update package has finished downloading successfully.\n\n"
            "Do you want to install it now?\n"
            "(The POS application will close to perform the installation)",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply == QMessageBox.Yes:
            self._launch_installer()

    def _on_download_error(self, err_msg: str):
        self._main_action_btn.setEnabled(True)
        self._check_btn.setEnabled(True)
        self._progress_status_lbl.setText(f"Download failed: {err_msg}")
        QMessageBox.critical(self, "Download Error", f"Failed to download update package:\n{err_msg}")

    def _launch_installer(self):
        if self._installer_path and os.path.exists(self._installer_path):
            launch_installer(self._installer_path, parent=self)
        else:
            QMessageBox.critical(self, "Error", "Installer executable not found on disk.")
