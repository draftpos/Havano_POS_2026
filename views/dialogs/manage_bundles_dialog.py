import json
import threading
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QPushButton, QHeaderView, QAbstractItemView,
    QWidget,
)
from PySide6.QtCore import Qt, Slot
from theme import *


class ManageBundlesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Product Bundles")
        self.setWindowState(Qt.WindowMaximized)
        self.setStyleSheet(f"QDialog {{ background: #f5f8fc; }}")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        from views.reports.report_template import ReportTemplate
        self.report = ReportTemplate("Product Bundles", is_report=False, show_date_filter=False, parent=self)
        self.report.set_headers(["SKU / Code", "Bundle Name", "Status", "Actions"])

        self.sync_btn = QPushButton("⟳  Sync Pending")
        self.sync_btn.setFixedHeight(32)
        self.sync_btn.setCursor(Qt.PointingHandCursor)
        self.sync_btn.setStyleSheet(f"""
            QPushButton {{
                background: {SUCCESS}; color: {WHITE};
                border: none; border-radius: 4px;
                font-size: 12px; font-weight: bold; padding: 0 14px;
            }}
            QPushButton:hover {{ background: {SUCCESS_H}; }}
            QPushButton:disabled {{ background: {MUTED}; }}
        """)
        self.sync_btn.clicked.connect(self._sync_pending)
        self.report.filters_layout.insertWidget(4, self.sync_btn)

        self.report.btn_add.setText(" Add Product Bundle")
        self.report.btn_add.clicked.connect(self._create_bundle)
        self.report.btn_add.show()

        self.table = self.report.table
        root.addWidget(self.report, 1)

        self._load_bundles()

    # ─────────────────────────────────────────────────────────────────────
    def _sync_pending(self):
        """Push all pending bundles to Odoo immediately (background thread)."""
        self.sync_btn.setEnabled(False)
        self.sync_btn.setText("Syncing…")

        def _run():
            try:
                from services.odoo.sync_service import push_unsynced_bundles_odoo
                push_unsynced_bundles_odoo()
            except Exception as e:
                print(f"[ManageBundles] Sync error: {e}")
            finally:
                from PySide6.QtCore import QMetaObject, Qt as _Qt
                QMetaObject.invokeMethod(self, "_after_sync", _Qt.QueuedConnection)

        threading.Thread(target=_run, daemon=True).start()

    @Slot()
    def _after_sync(self):
        self.sync_btn.setEnabled(True)
        self.sync_btn.setText("⟳  Sync Pending")
        self._load_bundles()

    # ─────────────────────────────────────────────────────────────────────
    def _load_bundles(self):
        try:
            from database.db import get_connection
            conn = get_connection()
            cur = conn.cursor()
            # Safely try to include sync_error (added in schema 2026.05.26.2)
            try:
                cur.execute(
                    "SELECT part_no, name, sync_status, bundle_lines, sync_error "
                    "FROM products WHERE is_product_bundle = 1"
                )
                rows = [(r[0], r[1], r[2], r[3], r[4]) for r in cur.fetchall()]
            except Exception:
                cur.execute(
                    "SELECT part_no, name, sync_status, bundle_lines "
                    "FROM products WHERE is_product_bundle = 1"
                )
                rows = [(r[0], r[1], r[2], r[3], None) for r in cur.fetchall()]
            conn.close()

            while self.table.rowCount() > 1:
                self.table.removeRow(1)
                
            for code, name, status, lines_json, sync_error in rows:
                row_idx = self.table.rowCount()
                self.table.insertRow(row_idx)

                self.table.setItem(row_idx, 0, QTableWidgetItem(str(code)))
                self.table.setItem(row_idx, 1, QTableWidgetItem(str(name)))

                status_str = str(status or "").upper()
                status_item = QTableWidgetItem(status_str)
                if status_str == "PENDING":
                    status_item.setForeground(Qt.GlobalColor.darkYellow)
                elif status_str == "SYNCED":
                    status_item.setForeground(Qt.GlobalColor.darkGreen)
                elif status_str == "FAILED":
                    status_item.setForeground(Qt.GlobalColor.red)
                    if sync_error:
                        status_item.setToolTip(str(sync_error))
                self.table.setItem(row_idx, 2, status_item)

                lines_count = 0
                if lines_json:
                    try:
                        lines_count = len(json.loads(lines_json))
                    except Exception:
                        pass

                # Actions: Edit button + Reset button for failed bundles
                w = QWidget()
                l = QHBoxLayout(w)
                l.setContentsMargins(4, 2, 4, 2)
                l.setSpacing(4)

                btn = QPushButton(f"Edit ({lines_count} items)")
                btn.setCursor(Qt.PointingHandCursor)
                btn.setStyleSheet(
                    f"background: {ACCENT}; color: {WHITE}; border: none; "
                    f"padding: 4px 12px; border-radius: 3px;"
                )
                btn.clicked.connect(lambda _, c=code: self._edit_bundle(c))
                l.addWidget(btn)

                if status_str == "FAILED":
                    reset_btn = QPushButton("↺ Retry")
                    reset_btn.setCursor(Qt.PointingHandCursor)
                    reset_btn.setToolTip("Reset to pending so it will be retried on next sync")
                    reset_btn.setStyleSheet(
                        f"background: #b05000; color: {WHITE}; border: none; "
                        f"padding: 4px 10px; border-radius: 3px; font-size: 11px;"
                    )
                    reset_btn.clicked.connect(lambda _, c=code: self._reset_bundle(c))
                    l.addWidget(reset_btn)

                self.table.setCellWidget(row_idx, 3, w)

        except Exception as e:
            print(f"Failed to load bundles: {e}")

    def _reset_bundle(self, part_no: str):
        """Reset a failed bundle back to pending so the next sync will retry it."""
        try:
            from database.db import get_connection
            conn = get_connection()
            cur = conn.cursor()
            try:
                cur.execute(
                    "UPDATE products SET sync_status = 'pending', sync_error = NULL "
                    "WHERE part_no = ?",
                    (part_no,)
                )
            except Exception:
                # sync_error column may not exist yet - update without it
                cur.execute(
                    "UPDATE products SET sync_status = 'pending' WHERE part_no = ?",
                    (part_no,)
                )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Failed to reset bundle {part_no}: {e}")
        finally:
            self._load_bundles()

    def _edit_bundle(self, part_no):
        from views.dialogs.bundle_dialog import BundleDialog
        dlg = BundleDialog(self, bundle_id=part_no)
        dlg.bundle_saved.connect(self._load_bundles)
        dlg.exec()

    def _create_bundle(self):
        from views.dialogs.bundle_dialog import BundleDialog
        dlg = BundleDialog(self)
        dlg.bundle_saved.connect(self._load_bundles)
        dlg.exec()
