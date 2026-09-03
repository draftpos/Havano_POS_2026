"""
POS Auto-Updater — Nextcloud Edition
=====================================
Drop this file next to your main POS script and call:

    from updater import check_for_updates
    check_for_updates(current_version="1.0.0")

You need two files in your Nextcloud public-shared folder:
  1. version.json          (metadata)
  2. HavanoPOS_Installer_vX.Y.Z.exe  (the installer)
"""

import os
import sys
import ssl
import json
import subprocess
import tempfile
import urllib.request
from packaging.version import Version

try:
    import certifi
    _SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CONTEXT = ssl.create_default_context()

from PySide6.QtCore    import Qt, QThread, Signal, QTimer
from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QProgressBar, QMessageBox, QWidget, QFrame,
    QGraphicsDropShadowEffect
)
from PySide6.QtGui import QFont, QColor

# ─────────────────────────────────────────────────────────────
#  Palette — mirrors login_dialog.py exactly
# ─────────────────────────────────────────────────────────────
from theme import *

# ─────────────────────────────────────────────────────────────
#  CONFIGURE THIS — your Nextcloud public share
# ─────────────────────────────────────────────────────────────
NEXTCLOUD_SHARE_URL = "https://vmi3020185.contaboserver.net/index.php/s/3kiXJJQC4LiwPrd"
# ─────────────────────────────────────────────────────────────


def _nc_download_url(filename: str) -> str:
    base = NEXTCLOUD_SHARE_URL.rstrip("/")
    return f"{base}/download?path=%2F&files={filename}"


def _fetch_version_info() -> dict:
    url = _nc_download_url("version.json")
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    with urllib.request.urlopen(req, context=_SSL_CONTEXT, timeout=10.0) as resp:
        return json.loads(resp.read().decode())


# ── Background download thread ────────────────────────────────────────────────

class DownloadThread(QThread):
    progress = Signal(int)
    finished = Signal(str)
    error    = Signal(str)

    def __init__(self, url: str, dest_path: str):
        super().__init__()
        self.url       = url
        self.dest_path = dest_path

    def run(self):
        try:
            req = urllib.request.Request(self.url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            with urllib.request.urlopen(req, context=_SSL_CONTEXT, timeout=120) as resp:
                total      = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                tmp_path = self.dest_path + ".tmp"
                with open(tmp_path, "wb") as f:
                    while True:
                        data = resp.read(65536)
                        if not data:
                            break
                        f.write(data)
                        downloaded += len(data)
                        if total:
                            self.progress.emit(int(downloaded / total * 100))
                        else:
                            # Send negative downloaded bytes to indicate indeterminate mode
                            self.progress.emit(-downloaded)
            if os.path.exists(self.dest_path):
                try: os.remove(self.dest_path)
                except Exception: pass
            os.rename(tmp_path, self.dest_path)
            self.finished.emit(self.dest_path)
        except Exception as e:
            self.error.emit(str(e))


# ── Update dialog ─────────────────────────────────────────────────────────────

class UpdateDialog(QDialog):
    def __init__(self, current_version: str, info: dict, parent=None):
        super().__init__(parent)
        self.info            = info
        self.current_version = current_version
        self.new_version     = info["version"]
        self.download_thread = None
        self._installer_path = None

        self.setWindowTitle("Havano POS — Software Update")
        self.setFixedWidth(460)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)

        # Drop shadow on the card
        card = QFrame()
        card.setObjectName("updateCard")
        card.setStyleSheet(f"QFrame#updateCard {{ background:{WHITE}; border-radius:20px; }}")
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(60); shadow.setXOffset(0); shadow.setYOffset(16)
        shadow.setColor(QColor(13, 31, 60, 100))
        card.setGraphicsEffect(shadow)
        outer.addWidget(card)

        root = QVBoxLayout(card)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header — same gradient as login ───────────────────────────────────
        header = QWidget()
        header.setFixedHeight(110)
        header.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {NAVY}, stop:0.6 {NAVY_2}, stop:1 {NAVY_3});
                border-top-left-radius:20px;
                border-top-right-radius:20px;
            }}
        """)

        # Use a stacked layout: titles centred, X pinned top-right
        from PySide6.QtWidgets import QGridLayout
        hg = QGridLayout(header)
        hg.setContentsMargins(12, 10, 12, 10)
        hg.setSpacing(0)

        # ── X close button ────────────────────────────────────────────────────
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(30, 30)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFocusPolicy(Qt.NoFocus)
        close_btn.setToolTip("Close")
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {MID};
                border: none;
                border-radius: 15px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.15);
                color: {WHITE};
            }}
            QPushButton:pressed {{
                background: rgba(255,255,255,0.25);
            }}
        """)
        close_btn.clicked.connect(self.reject)

        # Titles (centred across all columns)
        title_lbl = QLabel("Software Update Available")
        title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title_lbl.setStyleSheet(f"color:{WHITE}; background:transparent; letter-spacing:0.5px;")

        sub_lbl = QLabel("A new version of Havano POS is ready to install")
        sub_lbl.setAlignment(Qt.AlignCenter)
        sub_lbl.setFont(QFont("Segoe UI", 9))
        sub_lbl.setStyleSheet(f"color:{MID}; background:transparent;")

        # Row 0: spacer | title | X button
        hg.addWidget(QLabel(""), 0, 0)          # left spacer (same width as X)
        hg.addWidget(title_lbl,  0, 1, Qt.AlignCenter)
        hg.addWidget(close_btn,  0, 2, Qt.AlignTop | Qt.AlignRight)
        hg.addWidget(sub_lbl,    1, 0, 1, 3, Qt.AlignCenter)
        hg.setColumnStretch(0, 1)
        hg.setColumnStretch(1, 6)
        hg.setColumnStretch(2, 1)

        root.addWidget(header)

        # ── Accent line — same as login ───────────────────────────────────────
        accent = QFrame()
        accent.setFixedHeight(3)
        accent.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {NAVY_3}, stop:0.3 {ACCENT},
                stop:0.7 {ACCENT_H}, stop:1 {NAVY_3});
        """)
        root.addWidget(accent)

        # ── Body ──────────────────────────────────────────────────────────────
        body = QWidget()
        body.setStyleSheet(f"background:{OFF_WHITE};")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(28, 24, 28, 20)
        bl.setSpacing(16)

        # Version row — clean, no borders
        ver_widget = QWidget()
        ver_widget.setStyleSheet("background:transparent;")
        ver_layout = QHBoxLayout(ver_widget)
        ver_layout.setContentsMargins(0, 0, 0, 0)
        ver_layout.setSpacing(0)
        ver_layout.addStretch()

        cur_cap = QLabel("INSTALLED")
        cur_cap.setAlignment(Qt.AlignCenter)
        cur_cap.setStyleSheet(
            f"color:{MUTED}; font-size:9px; font-weight:700; "
            "letter-spacing:1.4px; background:transparent;"
        )
        cur_val = QLabel(f"v{self.current_version}")
        cur_val.setAlignment(Qt.AlignCenter)
        cur_val.setFont(QFont("Segoe UI", 22, QFont.Bold))
        cur_val.setStyleSheet(f"color:{NAVY}; background:transparent;")
        cur_col = QVBoxLayout(); cur_col.setSpacing(2)
        cur_col.addWidget(cur_cap); cur_col.addWidget(cur_val)
        ver_layout.addLayout(cur_col)

        arrow_lbl = QLabel("→")
        arrow_lbl.setAlignment(Qt.AlignCenter)
        arrow_lbl.setStyleSheet(
            f"color:{MID}; font-size:20px; background:transparent; padding:18px 24px 0 24px;"
        )
        ver_layout.addWidget(arrow_lbl)

        new_cap = QLabel("NEW VERSION")
        new_cap.setAlignment(Qt.AlignCenter)
        new_cap.setStyleSheet(
            f"color:{ACCENT}; font-size:9px; font-weight:700; "
            "letter-spacing:1.4px; background:transparent;"
        )
        new_val = QLabel(f"v{self.new_version}")
        new_val.setAlignment(Qt.AlignCenter)
        new_val.setFont(QFont("Segoe UI", 22, QFont.Bold))
        new_val.setStyleSheet(f"color:{ACCENT}; background:transparent;")
        new_col = QVBoxLayout(); new_col.setSpacing(2)
        new_col.addWidget(new_cap); new_col.addWidget(new_val)
        ver_layout.addLayout(new_col)

        ver_layout.addStretch()
        bl.addWidget(ver_widget)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet(f"color:{BORDER};")
        bl.addWidget(div)

        # Release notes
        notes = self.info.get("release_notes", "")
        if notes:
            notes_lbl = QLabel(notes)
            notes_lbl.setFont(QFont("Segoe UI", 10))
            notes_lbl.setStyleSheet(f"color:{MUTED}; background:transparent;")
            notes_lbl.setWordWrap(True)
            bl.addWidget(notes_lbl)

        # Progress bar (hidden until download starts)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background:{LIGHT};
                border:none;
                border-radius:4px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {ACCENT}, stop:1 {ACCENT_H});
                border-radius:4px;
            }}
        """)
        self.progress_bar.hide()
        bl.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setFont(QFont("Segoe UI", 9))
        self.status_label.setStyleSheet(f"color:{MUTED}; background:transparent;")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.hide()
        bl.addWidget(self.status_label)

        root.addWidget(body)

        # ── Footer with buttons ───────────────────────────────────────────────
        footer = QWidget()
        footer.setFixedHeight(64)
        footer.setStyleSheet(f"""
            QWidget {{
                background:{CREAM};
                border-bottom-left-radius:20px;
                border-bottom-right-radius:20px;
            }}
        """)
        btn_row = QHBoxLayout(footer)
        btn_row.setContentsMargins(24, 12, 24, 12)
        btn_row.setSpacing(10)

        self.skip_btn = QPushButton("Remind Me Later")
        self.skip_btn.setFixedHeight(40)
        self.skip_btn.setCursor(Qt.PointingHandCursor)
        self.skip_btn.setFocusPolicy(Qt.NoFocus)
        self.skip_btn.setStyleSheet(f"""
            QPushButton {{
                background:{WHITE};
                color:{MUTED};
                border:1.5px solid {BORDER};
                border-radius:10px;
                font-size:12px;
                font-weight:600;
                padding:0 18px;
            }}
            QPushButton:hover {{
                background:{LIGHT};
                color:{NAVY};
                border-color:{MID};
            }}
            QPushButton:pressed {{
                background:{BORDER};
            }}
        """)
        self.skip_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.skip_btn)

        btn_row.addStretch()

        import tempfile, os
        filename = self.info.get("installer_filename", "")
        dest = os.path.join(tempfile.gettempdir(), filename) if filename else ""
        
        if dest and os.path.exists(dest):
            self.install_btn = QPushButton("Install Update Now")
        else:
            self.install_btn = QPushButton("Download and Install")
        self.install_btn.setFixedHeight(40)
        self.install_btn.setDefault(True)
        self.install_btn.setCursor(Qt.PointingHandCursor)
        self.install_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {NAVY}, stop:1 {ACCENT});
                color:{WHITE};
                border:none;
                border-radius:10px;
                font-size:13px;
                font-weight:700;
                padding:0 22px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {NAVY_3}, stop:1 {ACCENT_H});
            }}
            QPushButton:pressed {{
                background:{NAVY_2};
            }}
            QPushButton:disabled {{
                background:{LIGHT};
                color:{MID};
            }}
        """)
        self.install_btn.clicked.connect(self._start_download)
        btn_row.addWidget(self.install_btn)

        if self.info.get("mandatory"):
            self.skip_btn.hide()

        root.addWidget(footer)

    # ── Download & install flow ────────────────────────────────────────────────

    def _start_download(self):
        filename = self.info["installer_filename"]
        url      = _nc_download_url(filename)
        dest     = os.path.join(tempfile.gettempdir(), filename)

        if os.path.exists(dest):
            self._installer_path = dest
            self.install_btn.setText("Install Update Now")
            self.install_btn.setEnabled(True)
            try:
                self.install_btn.clicked.disconnect()
            except Exception:
                pass
            self.install_btn.clicked.connect(self._launch_installer)
            self.status_label.setStyleSheet(f"color:{SUCCESS}; font-weight:bold; background:transparent;")
            self.status_label.setText("Update already downloaded. Click 'Install Update Now' to proceed.")
            self.status_label.show()
            return

        self.install_btn.setEnabled(False)
        self.skip_btn.setEnabled(False)
        self.progress_bar.show()
        self.progress_bar.setValue(0)
        self.status_label.setStyleSheet(f"color:{MUTED}; background:transparent;")
        self.status_label.setText("Connecting to update server...")
        self.status_label.show()

        self.download_thread = DownloadThread(url, dest)
        self.download_thread.progress.connect(self._on_progress)
        self.download_thread.finished.connect(self._on_download_done)
        self.download_thread.error.connect(self._on_download_error)
        self.download_thread.start()

        # Swap button to "Please wait..." until we get progress
        self.install_btn.setText("Please wait...")
        self.install_btn.setEnabled(False)
        self.install_btn.clicked.disconnect()
        self.install_btn.clicked.connect(self._run_in_background)

    def _run_in_background(self):
        # Keep a hard module-level reference so the thread is NEVER garbage-
        # collected while the download is still in progress.
        global _background_thread_ref
        _background_thread_ref = self.download_thread
        self.hide()
        # Return from exec() without destroying the dialog object
        QDialog.accept(self)

    def _on_progress(self, value: int):
        if value < 0:
            # Indeterminate mode: value is -downloaded_bytes
            mb = (-value) / (1024 * 1024)
            if self.progress_bar.maximum() != 0:
                self.progress_bar.setRange(0, 0)
            self.status_label.setText(f"Downloading update... {mb:.1f} MB")
            if -value > 1024 and not self.install_btn.isEnabled():
                self.install_btn.setText("Run in Background")
                self.install_btn.setEnabled(True)
            update_notifier.progress.emit(0)
        else:
            self.progress_bar.setValue(value)
            self.status_label.setText(f"Downloading update...  {value}%")
            
            # Only allow backgrounding once it's actually downloading
            if value >= 1 and not self.install_btn.isEnabled():
                self.install_btn.setText("Run in Background")
                self.install_btn.setEnabled(True)
                
            update_notifier.progress.emit(value)

    def _on_download_done(self, path: str):
        self._installer_path = path
        update_notifier.finished.emit()

        if not self.isVisible():
            # ── Background mode ────────────────────────────────────────────
            # Always use the active window as parent so the box is never
            # hidden behind the main POS window.
            parent_win = QApplication.activeWindow()
            reply = QMessageBox.question(
                parent_win,
                "Update Ready",
                "The software update has finished downloading in the background."
                "\n\nDo you want to install it now?\n(The POS will restart to apply the update)",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,          # default = Yes
            )
            if reply == QMessageBox.Yes:
                self._launch_installer()
        else:
            # ── Foreground mode ────────────────────────────────────────────
            self.progress_bar.setValue(100)
            self.status_label.setStyleSheet(
                f"color:{SUCCESS}; font-weight:bold; background:transparent;"
            )
            self.status_label.setText("Download complete — launching installer...")
            QTimer.singleShot(900, self._launch_installer)

    def _on_download_error(self, msg: str):
        if not self.isVisible():
            self.show()
            self.raise_()
            self.activateWindow()
        self.status_label.setStyleSheet(f"color:{DANGER}; background:transparent;")
        self.status_label.setText(f"Download failed: {msg}")
        self.install_btn.setEnabled(True)
        self.skip_btn.setEnabled(True)

    def _launch_installer(self):
        try:
            if sys.platform == "win32":
                import ctypes
                # "runas" requests administrator privileges (UAC prompt)
                params = "/SILENT /SP- /SUPPRESSMSGBOXES /FORCECLOSEAPPLICATIONS"
                ctypes.windll.shell32.ShellExecuteW(None, "runas", self._installer_path, params, None, 1)
            else:
                import subprocess
                subprocess.Popen([self._installer_path, "/SILENT", "/SP-", "/SUPPRESSMSGBOXES"])
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not launch installer:\n{e}")
            return
        QApplication.quit()
        os._exit(0)


_global_update_dialog = None
_background_thread_ref = None   # prevents GC when dialog is hidden

from PySide6.QtCore import QObject

class _UpdateNotifier(QObject):
    progress = Signal(int)
    finished = Signal()
    error = Signal(str)

update_notifier = _UpdateNotifier()

def check_for_updates(current_version: str, parent: QWidget = None, silent: bool = True) -> None:
    """
    Call this once on POS startup.
        from updater import check_for_updates
        check_for_updates(current_version=APP_VERSION)
    """
    global _global_update_dialog
    try:
        info = _fetch_version_info()
    except Exception as e:
        if not silent:
            QMessageBox.warning(parent, "Update Check Failed", f"Could not check for updates:\n{e}")
        return

    try:
        is_newer = Version(info["version"]) > Version(current_version)
    except Exception as e:
        if not silent:
            QMessageBox.warning(parent, "Update Check Failed", f"Invalid version format:\n{e}")
        return

    if not is_newer:
        if not silent:
            QMessageBox.information(parent, "Up to Date", f"You are running the latest version: {current_version}")
        return

    loaders = [w for w in QApplication.topLevelWidgets() if w.__class__.__name__ == "SleekLoaderOverlay"]
    for loader in loaders:
        loader.hide_loading()

    _global_update_dialog = UpdateDialog(current_version, info, parent=parent)
    _global_update_dialog.exec()

    for loader in loaders:
        loader.show_loading()