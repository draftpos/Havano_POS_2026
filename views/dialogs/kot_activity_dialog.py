# =============================================================================
# views/dialogs/kot_activity_dialog.py
# Full-page "KOT Activity" dialog - shows Cancelled and Modified orders
# Accessible from both: Admin Dashboard and Restaurant view toolbar
# =============================================================================

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QComboBox,
    QPushButton, QFrame, QWidget, QScrollArea, QLineEdit, QDateEdit,
    QSizePolicy, QMessageBox
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor, QFont

# ── Color palette (matches main_window palette) ────────────────────────────
from theme import *


def _section_header(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"font-size: 11px; font-weight: 700; color: {TEXT_MUTED}; "
        f"letter-spacing: 1.2px; text-transform: uppercase; "
        f"background: transparent; padding: 0;"
    )
    return lbl


def _tag(text: str, bg: str, fg: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"background: {bg}; color: {fg}; border-radius: 4px; "
        f"font-size: 10px; font-weight: 700; padding: 2px 8px;"
    )
    lbl.setAlignment(Qt.AlignCenter)
    return lbl


class KOTActivityDialog(QDialog):
    """
    Full-page KOT Activity viewer - Cancelled + Modified orders.
    Can be opened from Admin Dashboard or Restaurant toolbar.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("KOT Activity - Cancelled & Modified Orders")
        self.setMinimumSize(1100, 700)
        self.setModal(True)
        self._setup_style()
        self._build_ui()
        self._load_data()

    def _setup_style(self):
        self.setStyleSheet(f"""
            QDialog {{
                background: {OFF_WHITE};
            }}
            QLabel {{
                color: {TEXT};
                background: transparent;
            }}
            QLineEdit, QComboBox, QDateEdit {{
                background: {WHITE};
                color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }}
            QLineEdit:focus, QComboBox:focus, QDateEdit:focus {{
                border-color: {ACCENT};
            }}
            QComboBox::drop-down {{
                border: none;
                padding-right: 8px;
            }}
            QTableWidget {{
                background: {WHITE};
                border: 1px solid {BORDER};
                border-radius: 8px;
                gridline-color: {BORDER_LT};
                font-size: 12px;
                alternate-background-color: {ROW_ALT};
            }}
            QTableWidget::item {{
                padding: 10px 12px;
                color: {TEXT};
                border: none;
            }}
            QTableWidget::item:selected {{
                background: {ACCENT_SOFT};
                color: {ACCENT};
            }}
            QHeaderView::section {{
                background: {SURFACE};
                color: {TEXT_MUTED};
                font-size: 11px;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.8px;
                padding: 10px 12px;
                border: none;
                border-bottom: 2px solid {BORDER};
            }}
            QPushButton {{
                border: none;
                border-radius: 6px;
                font-weight: 600;
                font-size: 12px;
                padding: 8px 18px;
                cursor: pointer;
            }}
        """)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header bar ────────────────────────────────────────────────────
        hdr = QFrame()
        hdr.setFixedHeight(56)
        hdr.setStyleSheet(f"""
            QFrame {{
                background: {NAVY};
                border: none;
            }}
        """)
        hdr_lay = QHBoxLayout(hdr)
        hdr_lay.setContentsMargins(24, 0, 24, 0)
        hdr_lay.setSpacing(12)

        title_icon = QLabel("📋")
        title_icon.setStyleSheet("font-size: 18px; background: transparent;")
        hdr_lay.addWidget(title_icon)

        title = QLabel("KOT Activity")
        title.setStyleSheet(f"font-size: 17px; font-weight: 700; color: {WHITE}; background: transparent;")
        hdr_lay.addWidget(title)

        sub = QLabel("- Cancelled & Modified Orders")
        sub.setStyleSheet(f"font-size: 13px; color: #94a3b8; background: transparent;")
        hdr_lay.addWidget(sub)
        hdr_lay.addStretch()

        close_btn = QPushButton("✕  Close")
        close_btn.setFixedHeight(32)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: #94a3b8;
                border: 1px solid #334155; border-radius: 6px;
                font-size: 12px; padding: 0 16px;
            }}
            QPushButton:hover {{ background: #1e293b; color: {WHITE}; border-color: #475569; }}
        """)
        close_btn.clicked.connect(self.reject)
        hdr_lay.addWidget(close_btn)

        root.addWidget(hdr)

        # ── Filter toolbar ────────────────────────────────────────────────
        toolbar = QFrame()
        toolbar.setFixedHeight(60)
        toolbar.setStyleSheet(f"""
            QFrame {{
                background: {WHITE};
                border-bottom: 1px solid {BORDER};
            }}
        """)
        tb_lay = QHBoxLayout(toolbar)
        tb_lay.setContentsMargins(24, 0, 24, 0)
        tb_lay.setSpacing(12)

        # Filter: Action type
        lbl_type = QLabel("Show:")
        lbl_type.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {TEXT_SEC};")
        tb_lay.addWidget(lbl_type)

        self._filter_type = QComboBox()
        self._filter_type.addItems(["All", "Cancelled", "Modified"])
        self._filter_type.setFixedWidth(150)
        self._filter_type.setFixedHeight(34)
        tb_lay.addWidget(self._filter_type)

        tb_lay.addSpacing(8)

        # Filter: Date from
        lbl_from = QLabel("From:")
        lbl_from.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {TEXT_SEC};")
        tb_lay.addWidget(lbl_from)

        self._date_from = QDateEdit()
        self._date_from.setCalendarPopup(True)
        self._date_from.setDate(QDate.currentDate().addDays(-30))
        self._date_from.setFixedHeight(34)
        self._date_from.setFixedWidth(130)
        self._date_from.setDisplayFormat("dd/MM/yyyy")
        tb_lay.addWidget(self._date_from)

        lbl_to = QLabel("To:")
        lbl_to.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {TEXT_SEC};")
        tb_lay.addWidget(lbl_to)

        self._date_to = QDateEdit()
        self._date_to.setCalendarPopup(True)
        self._date_to.setDate(QDate.currentDate())
        self._date_to.setFixedHeight(34)
        self._date_to.setFixedWidth(130)
        self._date_to.setDisplayFormat("dd/MM/yyyy")
        tb_lay.addWidget(self._date_to)

        tb_lay.addSpacing(8)

        # Search
        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍  Search order, table, reason…")
        self._search.setFixedHeight(34)
        self._search.setFixedWidth(240)
        tb_lay.addWidget(self._search)

        tb_lay.addStretch()

        # Refresh btn
        refresh_btn = QPushButton("↻  Refresh")
        refresh_btn.setFixedHeight(34)
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT_SOFT}; color: {ACCENT};
                border: 1px solid #bfdbfe; padding: 0 16px;
            }}
            QPushButton:hover {{ background: #bfdbfe; }}
        """)
        refresh_btn.clicked.connect(self._load_data)
        tb_lay.addWidget(refresh_btn)

        # Print btn
        print_btn = QPushButton("🖨  Print Log")
        print_btn.setFixedHeight(34)
        print_btn.setCursor(Qt.PointingHandCursor)
        print_btn.setStyleSheet(f"""
            QPushButton {{
                background: {NAVY}; color: {WHITE};
                border: none; padding: 0 16px;
            }}
            QPushButton:hover {{ background: {ACCENT}; }}
        """)
        print_btn.clicked.connect(self._print_log)
        tb_lay.addWidget(print_btn)

        root.addWidget(toolbar)

        # ── Summary chips ─────────────────────────────────────────────────
        summary_bar = QFrame()
        summary_bar.setFixedHeight(48)
        summary_bar.setStyleSheet(f"background: {SURFACE}; border-bottom: 1px solid {BORDER};")
        sb_lay = QHBoxLayout(summary_bar)
        sb_lay.setContentsMargins(24, 0, 24, 0)
        sb_lay.setSpacing(20)

        self._chip_total     = self._make_chip("Total",     "-",  TEXT_SEC)
        self._chip_cancelled = self._make_chip("Cancelled", "-",  DANGER)
        self._chip_modified  = self._make_chip("Modified",  "-",  WARNING)

        for chip in (self._chip_total, self._chip_cancelled, self._chip_modified):
            sb_lay.addWidget(chip)
        sb_lay.addStretch()

        root.addWidget(summary_bar)

        # ── Main table ────────────────────────────────────────────────────
        body = QFrame()
        body.setStyleSheet(f"background: {OFF_WHITE};")
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(20, 16, 20, 16)
        body_lay.setSpacing(0)

        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels([
            "Date / Time", "Action", "Order #", "Table", "Waiter", "Reason", "Items"
        ])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.setWordWrap(True)
        body_lay.addWidget(self._table)

        root.addWidget(body, 1)

        # ── Wire filter triggers ──────────────────────────────────────────
        self._filter_type.currentIndexChanged.connect(self._load_data)
        self._date_from.dateChanged.connect(self._load_data)
        self._date_to.dateChanged.connect(self._load_data)
        self._search.textChanged.connect(self._apply_search_filter)

    def _make_chip(self, label: str, value: str, color: str) -> QWidget:
        """Small pill widget showing a label + count."""
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        lbl = QLabel(label + ":")
        lbl.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {TEXT_MUTED};")
        val = QLabel(value)
        val.setObjectName(f"chip_val_{label.lower()}")
        val.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {color};")
        lay.addWidget(lbl)
        lay.addWidget(val)
        return w

    def _update_chip(self, chip: QWidget, value: str):
        for child in chip.findChildren(QLabel):
            if child.objectName().startswith("chip_val_"):
                child.setText(value)
                break

    # ── Data loading ──────────────────────────────────────────────────────

    def _load_data(self):
        try:
            from models.restaurant_order import get_kot_log
            filter_map = {"All": None, "Cancelled": "Cancel", "Modified": "Modify"}
            action_filter = filter_map.get(self._filter_type.currentText())
            rows = get_kot_log(action=action_filter)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not load KOT log:\n{e}")
            return

        # Apply date filter
        date_from = self._date_from.date().toString("yyyy-MM-dd")
        date_to   = self._date_to.date().toString("yyyy-MM-dd")

        filtered = []
        for entry in rows:
            dt = entry.get("logged_at")
            if dt:
                dt_str = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)[:10]
                if dt_str < date_from or dt_str > date_to:
                    continue
            filtered.append(entry)

        self._all_rows = filtered
        self._populate_table(filtered)

    def _apply_search_filter(self):
        query = self._search.text().strip().lower()
        if not query:
            self._populate_table(self._all_rows)
            return

        matched = []
        for entry in self._all_rows:
            haystack = " ".join([
                str(entry.get("order_id", "")),
                str(entry.get("table_name", "")),
                str(entry.get("table_number", "")),
                str(entry.get("reason", "")),
                str(entry.get("action", "")),
                str(entry.get("waiter_name", "")),
            ]).lower()
            if query in haystack:
                matched.append(entry)
        self._populate_table(matched)

    def _populate_table(self, rows: list):
        self._table.setRowCount(0)

        total = len(rows)
        cancelled = sum(1 for r in rows if "cancel" in str(r.get("action", "")).lower())
        modified  = sum(1 for r in rows if "modify"  in str(r.get("action", "")).lower())

        self._update_chip(self._chip_total,     str(total))
        self._update_chip(self._chip_cancelled, str(cancelled))
        self._update_chip(self._chip_modified,  str(modified))

        for entry in rows:
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._table.setRowHeight(r, 46)

            # Col 0 - Date/Time
            dt = entry.get("logged_at")
            dt_str = dt.strftime("%d/%m/%Y  %H:%M") if hasattr(dt, "strftime") else str(dt or "")[:16]
            self._table.setItem(r, 0, self._cell(dt_str, align=Qt.AlignCenter))

            # Col 1 - Action tag
            action = str(entry.get("action", "")).strip()
            is_cancel = "cancel" in action.lower()
            tag_bg  = "#fee2e2" if is_cancel else "#fef3c7"
            tag_fg  = "#991b1b" if is_cancel else "#92400e"
            tag_lbl = "CANCELLED" if is_cancel else "MODIFIED"
            tag_widget = _tag(tag_lbl, tag_bg, tag_fg)
            self._table.setCellWidget(r, 1, tag_widget)

            # Col 2 - Order #
            oid = entry.get("order_id", "")
            self._table.setItem(r, 2, self._cell(f"ORD-{oid}" if oid else "-", align=Qt.AlignCenter))

            # Col 3 - Table
            tname = f"{entry.get('table_name', '')} {entry.get('table_number', '')}".strip()
            self._table.setItem(r, 3, self._cell(tname or "-"))

            # Col 4 - Waiter
            waiter = entry.get("waiter_name") or entry.get("cashier_name") or "-"
            self._table.setItem(r, 4, self._cell(str(waiter)))

            # Col 5 - Reason
            reason = str(entry.get("reason") or "-")
            reason_item = self._cell(reason)
            if reason != "-":
                reason_item.setForeground(QColor(ACCENT))
            self._table.setItem(r, 5, reason_item)

            # Col 6 - Item count
            items = entry.get("items") or []
            item_count = len(items) if isinstance(items, list) else "-"
            self._table.setItem(r, 6, self._cell(str(item_count), align=Qt.AlignCenter))

    def _cell(self, text: str, align=Qt.AlignLeft | Qt.AlignVCenter) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setTextAlignment(align)
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        return item

    # ── Print log ─────────────────────────────────────────────────────────

    def _print_log(self):
        """Simple text-based print of the visible log entries."""
        try:
            from services.printing_service import PrintingService
            from models.hardware_settings import get_hardware_settings
            hw = get_hardware_settings()
            printer_name = hw.get("main_printer") or None
            if printer_name == "(None)":
                printer_name = None

            from PySide6.QtPrintSupport import QPrinter, QPrinterInfo
            from PySide6.QtGui import QPainter, QFont
            from PySide6.QtCore import QSizeF, QMarginsF
            from PySide6.QtGui import QPageSize
            from datetime import datetime

            printer = QPrinter(QPrinter.HighResolution)
            if printer_name:
                info = QPrinterInfo.printerInfo(printer_name)
                if not info.isNull():
                    printer.setPrinterName(printer_name)

            printer.setPageSize(QPageSize(QSizeF(80, 2000), QPageSize.Millimeter))
            printer.setFullPage(True)
            printer.setPageMargins(QMarginsF(0, 0, 0, 0))

            painter = QPainter(printer)
            paper_w = 550
            margin  = 10
            y = 10

            bold_font   = QFont("Arial", 10); bold_font.setBold(True)
            normal_font = QFont("Arial", 9)
            small_font  = QFont("Arial", 8)

            painter.setFont(bold_font)
            painter.drawText(margin, y, paper_w - margin*2, 30, Qt.AlignCenter, "KOT ACTIVITY LOG")
            y += 32
            painter.setFont(small_font)
            action_label = self._filter_type.currentText()
            painter.drawText(margin, y, paper_w - margin*2, 20, Qt.AlignCenter,
                             f"Filter: {action_label}  |  "
                             f"{self._date_from.date().toString('dd/MM/yyyy')} - "
                             f"{self._date_to.date().toString('dd/MM/yyyy')}")
            y += 22
            painter.drawText(margin, y, paper_w - margin*2, 20, Qt.AlignCenter,
                             f"Printed: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
            y += 22
            painter.drawLine(margin, y, paper_w - margin, y)
            y += 14

            painter.setFont(bold_font)
            painter.drawText(margin, y, 100, 18, Qt.AlignLeft, "Date/Time")
            painter.drawText(margin + 100, y, 80, 18, Qt.AlignLeft, "Action")
            painter.drawText(margin + 180, y, 70, 18, Qt.AlignLeft, "Order")
            painter.drawText(margin + 250, y, 80, 18, Qt.AlignLeft, "Table")
            painter.drawText(margin + 330, y, paper_w - margin - 330, 18, Qt.AlignLeft, "Reason")
            y += 22
            painter.drawLine(margin, y, paper_w - margin, y)
            y += 10

            painter.setFont(normal_font)
            for entry in getattr(self, "_all_rows", []):
                dt = entry.get("logged_at")
                dt_str = dt.strftime("%d/%m %H:%M") if hasattr(dt, "strftime") else str(dt or "")[:13]
                action = str(entry.get("action", ""))
                oid    = f"ORD-{entry.get('order_id','')}"
                tname  = f"{entry.get('table_name', '')} {entry.get('table_number', '')}".strip() or "-"
                reason = str(entry.get("reason") or "-")

                painter.drawText(margin,       y, 100, 18, Qt.AlignLeft, dt_str)
                painter.drawText(margin + 100, y,  80, 18, Qt.AlignLeft, action)
                painter.drawText(margin + 180, y,  70, 18, Qt.AlignLeft, oid)
                painter.drawText(margin + 250, y,  80, 18, Qt.AlignLeft, tname)
                painter.drawText(margin + 330, y, paper_w - margin - 330, 18, Qt.AlignLeft, reason)
                y += 20

            y += 10
            painter.drawLine(margin, y, paper_w - margin, y)
            y += 12
            painter.setFont(small_font)
            painter.drawText(margin, y, paper_w - margin*2, 18, Qt.AlignCenter, "Havano Version 1.1.8")

            painter.end()
            print("[KOTActivity] Log printed.")
        except Exception as e:
            QMessageBox.warning(self, "Print Failed", f"Could not print log:\n{e}")


def open_kot_activity(parent=None):
    """Convenience function to open the dialog."""
    dlg = KOTActivityDialog(parent)
    dlg.exec()
