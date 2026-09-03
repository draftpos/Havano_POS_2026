"""
Backup & Restore Settings Dialog
─────────────────────────────────
A polished UI allowing the admin to:
  • Create a manual backup right now
  • See all backups in the local app_data directory with size & date
  • Upload / import an external .bak file
  • Restore any backup (auto-backs-up the current DB first)
  • Delete old backups
"""
from __future__ import annotations
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QWidget, QFileDialog, QProgressBar, QApplication,
)
import qtawesome as qta

# ── Havano Palette ─────────────────────────────────────────────────────────
from theme import *


def _btn(text, bg, hov, icon_name=None, icon_color=WHITE):
    b = QPushButton(text)
    b.setFixedHeight(36)
    b.setCursor(Qt.PointingHandCursor)
    if icon_name:
        b.setIcon(qta.icon(icon_name, color=icon_color))
    b.setStyleSheet(f"""
        QPushButton {{
            background:{bg}; color:{WHITE}; border:none; border-radius:6px;
            font-size:12px; font-weight:bold; padding:0 16px;
        }}
        QPushButton:hover {{ background:{hov}; }}
        QPushButton:disabled {{ background:{MUTED}; }}
    """)
    return b


# ── Background workers ─────────────────────────────────────────────────────
class _BackupWorker(QThread):
    finished = Signal(dict)

    def run(self):
        from services.backup_service import trigger_local_backup
        result = trigger_local_backup(label="manual")
        self.finished.emit(result)


class _RestoreWorker(QThread):
    finished = Signal(dict)

    def __init__(self, bak_path: str, parent=None):
        super().__init__(parent)
        self._bak_path = bak_path

    def run(self):
        from services.backup_service import restore_database
        result = restore_database(self._bak_path)
        self.finished.emit(result)


# ── Dialog ─────────────────────────────────────────────────────────────────
class BackupSettingsView(QWidget):
    """Full-featured Backup & Restore management view."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setStyleSheet(f"QWidget {{ background:{WHITE}; }}")
        self._workers = []
        self._build()
        self._reload()

    # ── UI construction ────────────────────────────────────────────────────
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ──
        hdr = QWidget()
        hdr.setFixedHeight(90)
        hdr.setStyleSheet(f"background:{NAVY};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(24, 0, 24, 0)

        vl = QVBoxLayout()
        vl.setSpacing(2)
        vl.setAlignment(Qt.AlignVCenter)
        title = QLabel("BACKUP  &  RESTORE")
        title.setStyleSheet(f"color:{WHITE}; font-size:20px; font-weight:bold; letter-spacing:1px;")
        sub = QLabel("Create, import and restore database backups  •  Saved in app_data/backups")
        sub.setStyleSheet(f"color:{MUTED}; font-size:11px;")
        vl.addWidget(title)
        vl.addWidget(sub)
        hl.addLayout(vl)
        hl.addStretch()

        # Progress indicator (hidden by default)
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)  # indeterminate
        self._progress.setFixedWidth(180)
        self._progress.setFixedHeight(20)
        self._progress.setTextVisible(False)
        self._progress.setStyleSheet(f"""
            QProgressBar {{ background:{NAVY_2}; border:1px solid {MUTED}; border-radius:4px; }}
            QProgressBar::chunk {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {ACCENT}, stop:1 {SUCCESS}); border-radius:3px; }}
        """)
        self._progress.hide()
        hl.addWidget(self._progress, alignment=Qt.AlignVCenter)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(f"color:{MUTED}; font-size:11px; font-weight:bold;")
        hl.addWidget(self._status_lbl, alignment=Qt.AlignVCenter)

        root.addWidget(hdr)

        # ── Action bar ──
        action_bar = QWidget()
        action_bar.setFixedHeight(60)
        action_bar.setStyleSheet(f"background:{OFF_WHITE}; border-bottom:1px solid {BORDER};")
        abl = QHBoxLayout(action_bar)
        abl.setContentsMargins(24, 0, 24, 0)
        abl.setSpacing(12)

        self._backup_btn = _btn("  Backup Now", SUCCESS, SUCCESS_H, "fa5s.database")
        self._backup_btn.clicked.connect(self._on_backup_now)
        abl.addWidget(self._backup_btn)

        self._upload_btn = _btn("  Upload Backup", ACCENT, ACCENT_H, "fa5s.upload")
        self._upload_btn.clicked.connect(self._on_upload)
        abl.addWidget(self._upload_btn)

        abl.addStretch()

        self._restore_btn = _btn("  Restore Selected", AMBER, "#cc6a1c", "fa5s.undo")
        self._restore_btn.setEnabled(False)
        self._restore_btn.clicked.connect(self._on_restore)
        abl.addWidget(self._restore_btn)

        self._delete_btn = _btn("  Delete", DANGER, DANGER_H, "fa5s.trash")
        self._delete_btn.setEnabled(False)
        self._delete_btn.clicked.connect(self._on_delete)
        abl.addWidget(self._delete_btn)

        root.addWidget(action_bar)

        # ── Table ──
        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(24, 16, 24, 16)

        self._tbl = QTableWidget(0, 4)
        self._tbl.setHorizontalHeaderLabels(["Backup File", "Size", "Created", "Path"])
        hh = self._tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.Stretch)
        self._tbl.verticalHeader().setVisible(False)
        self._tbl.setAlternatingRowColors(True)
        self._tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tbl.setSelectionMode(QAbstractItemView.SingleSelection)
        self._tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tbl.setStyleSheet(f"""
            QTableWidget {{
                background:{WHITE}; border:1px solid {BORDER}; border-radius:6px;
                font-size:12px;
            }}
            QTableWidget::item {{ padding:6px 10px; }}
            QTableWidget::item:selected {{
                background-color:{ACCENT}; color:{WHITE};
            }}
            QHeaderView::section {{
                background:{NAVY}; color:{WHITE}; font-weight:bold;
                padding:10px 12px; border:none; font-size:11px;
            }}
        """)
        self._tbl.itemSelectionChanged.connect(self._on_selection_changed)
        bl.addWidget(self._tbl)

        # ── Footer ──
        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet(f"color:{MUTED}; font-size:11px;")
        bl.addWidget(self._count_lbl)

        root.addWidget(body, 1)

    # ── Data loading ───────────────────────────────────────────────────────
    def _reload(self):
        self._tbl.setRowCount(0)
        try:
            from services.backup_service import list_backups
            backups = list_backups()
            for b in backups:
                idx = self._tbl.rowCount()
                self._tbl.insertRow(idx)

                # File name
                name_item = QTableWidgetItem(f"  {b['filename']}")
                name_item.setData(Qt.UserRole, b["path"])
                self._tbl.setItem(idx, 0, name_item)

                # Size
                size_item = QTableWidgetItem(f"  {b['size_mb']} MB")
                size_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self._tbl.setItem(idx, 1, size_item)

                # Created
                self._tbl.setItem(idx, 2, QTableWidgetItem(f"  {b['created']}"))

                # Path
                path_item = QTableWidgetItem(f"  {b['path']}")
                path_item.setForeground(Qt.MUTED)
                self._tbl.setItem(idx, 3, path_item)

            self._count_lbl.setText(f"{len(backups)} backup(s) found in Application Data")
        except Exception as e:
            self._count_lbl.setText(f"Error loading backups: {e}")

        self._restore_btn.setEnabled(False)
        self._delete_btn.setEnabled(False)

    def _on_selection_changed(self):
        has_sel = len(self._tbl.selectedItems()) > 0
        self._restore_btn.setEnabled(has_sel)
        self._delete_btn.setEnabled(has_sel)

    def _selected_path(self) -> str | None:
        rows = self._tbl.selectionModel().selectedRows()
        if not rows:
            return None
        return self._tbl.item(rows[0].row(), 0).data(Qt.UserRole)

    # ── Actions ────────────────────────────────────────────────────────────
    def _set_busy(self, busy: bool, msg: str = ""):
        self._progress.setVisible(busy)
        self._status_lbl.setText(msg)
        self._backup_btn.setEnabled(not busy)
        self._upload_btn.setEnabled(not busy)
        self._restore_btn.setEnabled(not busy)
        self._delete_btn.setEnabled(not busy)
        QApplication.processEvents()

    def _on_backup_now(self):
        self._set_busy(True, "Creating backup …")
        w = _BackupWorker(self)
        w.finished.connect(self._on_backup_done)
        self._workers.append(w)
        w.start()

    def _on_backup_done(self, result: dict):
        self._set_busy(False)
        if result["ok"]:
            QMessageBox.information(self, "Backup Complete",
                f"Database backed up successfully.\n\n{result['path']}")
        else:
            QMessageBox.critical(self, "Backup Failed", result["error"])
        self._reload()

    def _on_upload(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Backup File", "",
            "SQL Server Backup (*.bak);;All Files (*)")
        if not path:
            return
        try:
            import shutil
            from services.backup_service import BACKUP_DIR
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            dest = BACKUP_DIR / Path(path).name
            if dest.exists():
                reply = QMessageBox.question(self, "Overwrite?",
                    f"A file named '{dest.name}' already exists.\nOverwrite?")
                if reply != QMessageBox.Yes:
                    return
            shutil.copy2(path, dest)
            QMessageBox.information(self, "Imported",
                f"Backup file copied to:\n{dest}")
            self._reload()
        except Exception as e:
            QMessageBox.critical(self, "Import Failed", str(e))

    def _on_restore(self):
        bak_path = self._selected_path()
        if not bak_path:
            return

        reply = QMessageBox.warning(self, "Restore Database",
            f"This will OVERWRITE the current database with:\n\n"
            f"{Path(bak_path).name}\n\n"
            "A safety backup of the current state will be created first.\n\n"
            "The application will need to restart after restoring.\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return

        self._set_busy(True, "Restoring database …")
        w = _RestoreWorker(bak_path, self)
        w.finished.connect(self._on_restore_done)
        self._workers.append(w)
        w.start()

    def _on_restore_done(self, result: dict):
        self._set_busy(False)
        if result["ok"]:
            QMessageBox.information(self, "Restore Complete",
                "Database restored successfully.\n\n"
                "The application will now restart for the changes to take effect.")
            
            # Force quit immediately to prevent background threads from throwing pyodbc connection errors
            import os
            os._exit(0)
        else:
            QMessageBox.critical(self, "Restore Failed", result["error"])
        self._reload()

    def _on_delete(self):
        bak_path = self._selected_path()
        if not bak_path:
            return

        reply = QMessageBox.question(self, "Delete Backup",
            f"Permanently delete this backup?\n\n{Path(bak_path).name}",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return

        try:
            import os
            os.remove(bak_path)
            self._reload()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not delete file:\n{e}")


# Convenience import
from pathlib import Path
