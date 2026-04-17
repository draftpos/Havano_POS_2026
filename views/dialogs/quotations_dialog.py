# =============================================================================
# views/dialogs/quotations_dialog.py
# Quotations Viewer - Frappe-style table with sync status
# =============================================================================

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QScrollArea, QFrame, QMessageBox, QApplication, QSplitter,
    QGroupBox, QGridLayout, QTextEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QTabWidget, QProgressBar
)
from PySide6.QtCore import Qt, QTimer, QDate, QSize
from PySide6.QtGui import QColor, QFont, QClipboard

import json
from datetime import datetime
from typing import List

# ── Palette (matches UsersDialog exactly) ──────────────────────────────────────
NAVY      = "#0d1f3c"
NAVY_2    = "#162d52"
NAVY_3    = "#1e3d6e"
ACCENT    = "#1a5fb4"
WHITE     = "#ffffff"
OFF_WHITE = "#f5f8fc"
LIGHT     = "#e4eaf4"
BORDER    = "#c8d8ec"
MID       = "#8fa8c8"
MUTED     = "#5a7a9a"
DARK_TEXT = "#0d1f3c"
SUCCESS   = "#1a7a3c"
SUCCESS_H = "#1f9447"
DANGER    = "#b02020"
DANGER_H  = "#cc2828"
AMBER     = "#b7770d"
WARNING   = "#e67e22"

FIELD_H   = 36
LBL_W     = 120
ROW_SP    = 12


# ── Shared widget helpers (same as users_dialog) ──────────────────────────────

def _sec(text):
    l = QLabel(text.upper())
    l.setStyleSheet(
        f"color:{MUTED};font-size:10px;font-weight:bold;"
        f"background:transparent;letter-spacing:1.5px;"
    )
    l.setFixedHeight(20)
    return l


def _hr():
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setFixedHeight(1)
    f.setStyleSheet(f"background:{BORDER};border:none;")
    return f


def _lbl(text, w=LBL_W):
    l = QLabel(text)
    l.setFixedWidth(w)
    l.setFixedHeight(FIELD_H)
    l.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    l.setStyleSheet(
        f"color:{MUTED};font-size:12px;font-weight:bold;background:transparent;"
    )
    return l


def _action_btn(text, color=ACCENT, hover=None, text_color=WHITE, border=None):
    hover = hover or color
    border_css = f"border:1.5px solid {border};" if border else "border:none;"
    w = QPushButton(text)
    w.setFixedHeight(34)
    w.setCursor(Qt.PointingHandCursor)
    w.setStyleSheet(f"""
        QPushButton {{
            background:{color}; color:{text_color};
            {border_css}
            border-radius:6px; font-size:12px;
            font-weight:600; padding:0 16px;
        }}
        QPushButton:hover {{ background:{hover}; }}
        QPushButton:disabled {{ background:{LIGHT}; color:{MUTED}; border:1px solid {BORDER}; }}
    """)
    return w


def _status_badge(text, status_type="success"):
    """Create a status badge label"""
    colors = {
        "success": (SUCCESS, "#e8f5e9"),
        "danger": (DANGER, "#ffebee"),
        "warning": (WARNING, "#fff3e0"),
        "info": (ACCENT, "#e3f2fd"),
        "muted": (MUTED, "#f0f0f0"),
    }
    text_color, bg_color = colors.get(status_type, colors["muted"])
    
    lbl = QLabel(text)
    lbl.setFixedHeight(24)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet(f"""
        QLabel {{
            background:{bg_color};
            color:{text_color};
            border-radius:12px;
            font-size:10px;
            font-weight:bold;
            padding:0 10px;
        }}
    """)
    return lbl


# =============================================================================
# Quotations Dialog - Main UI
# =============================================================================

# Column proportions [Name, Customer, Date, Total, Status, Sync]
_COLS = [
    ("Quotation #",    180, Qt.AlignLeft),
    ("Customer",       150, Qt.AlignLeft),
    ("Date",           100, Qt.AlignLeft),
    ("Total",          100, Qt.AlignRight),
    ("Status",         100, Qt.AlignCenter),
    ("Synced",         80,  Qt.AlignCenter),
]


class QuotationsDialog(QDialog):
    def __init__(self, parent=None, current_user=None):
        super().__init__(parent)
        self.current_user = current_user or {}
        self._quotations: List[dict] = []
        self._selected: dict = {}
        self._syncing = False
        
        self.setWindowTitle("Quotations")
        self.setMinimumSize(1100, 650)
        self.setStyleSheet(
            f"QDialog {{ background:{OFF_WHITE}; font-family:'Segoe UI',sans-serif; }}"
        )
        
        self._build()
        self._load_quotations()
    
    # -------------------------------------------------------------------------
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        
        # ── Header ────────────────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setFixedHeight(60)
        hdr.setStyleSheet(f"background:{NAVY};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(28, 0, 20, 0)
        hl.setSpacing(12)
        
        title = QLabel("Quotations")
        title.setStyleSheet(
            f"color:{WHITE};font-size:18px;font-weight:bold;background:transparent;"
        )
        
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(
            f"font-size:12px;background:transparent;color:#2ecc71;"
        )
        
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(30, 30)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background:rgba(255,255,255,0.15); color:{WHITE};
                border:none; border-radius:15px; font-size:14px;
            }}
            QPushButton:hover {{ background:rgba(255,255,255,0.25); }}
        """)
        close_btn.clicked.connect(self.accept)
        
        hl.addWidget(title)
        hl.addStretch()
        hl.addWidget(self._status_lbl)
        hl.addWidget(close_btn)
        root.addWidget(hdr)
        
        # Accent gradient line
        bar = QFrame()
        bar.setFixedHeight(3)
        bar.setStyleSheet(f"""
            background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 {NAVY},stop:0.5 {ACCENT},stop:1 {NAVY_3});
        """)
        root.addWidget(bar)
        
        # ── Main content splitter ─────────────────────────────────────────────
        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet(f"QSplitter::handle {{ background:{BORDER}; width:1px; }}")
        
        # Left panel - Quotations list
        left_panel = self._build_list_panel()
        splitter.addWidget(left_panel)
        
        # Right panel - Details view
        right_panel = self._build_details_panel()
        splitter.addWidget(right_panel)
        
        splitter.setSizes([600, 500])
        root.addWidget(splitter, 1)
        
        # ── Footer ────────────────────────────────────────────────────────────
        foot = self._build_footer()
        root.addWidget(foot)
    
    # -------------------------------------------------------------------------
    def _build_list_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Toolbar
        toolbar = QWidget()
        toolbar.setFixedHeight(54)
        toolbar.setStyleSheet(f"background:{WHITE};border-bottom:1px solid {BORDER};")
        tbl = QHBoxLayout(toolbar)
        tbl.setContentsMargins(20, 0, 16, 0)
        tbl.setSpacing(10)
        
        # Search input
        self._search = QLineEdit()
        self._search.setFixedHeight(34)
        self._search.setPlaceholderText("Search by quotation #, customer...")
        self._search.setStyleSheet(f"""
            QLineEdit {{
                background:{OFF_WHITE}; color:{DARK_TEXT};
                border:1px solid {BORDER}; border-radius:6px;
                padding:0 12px; font-size:12px;
            }}
            QLineEdit:focus {{ border:2px solid {ACCENT}; background:{WHITE}; }}
        """)
        self._search.setFixedWidth(240)
        self._search.textChanged.connect(self._filter)
        tbl.addWidget(self._search)
        
        tbl.addStretch()
        
        self._sync_btn = _action_btn("Sync from Frappe", color=ACCENT, hover="#1c6dd0")
        self._sync_btn.clicked.connect(self._sync_quotations)
        tbl.addWidget(self._sync_btn)
        
        self._refresh_btn = _action_btn("⟳", color=WHITE, hover=LIGHT, text_color=DARK_TEXT, border=BORDER)
        self._refresh_btn.setFixedWidth(40)
        self._refresh_btn.clicked.connect(self._load_quotations)
        tbl.addWidget(self._refresh_btn)
        
        layout.addWidget(toolbar)
        
        # Column header
        col_hdr = QWidget()
        col_hdr.setFixedHeight(34)
        col_hdr.setStyleSheet(f"background:{LIGHT};border-bottom:1px solid {BORDER};")
        chl = QHBoxLayout(col_hdr)
        chl.setContentsMargins(20, 0, 20, 0)
        chl.setSpacing(0)
        
        for name, width, align in _COLS:
            lbl = QLabel(name.upper())
            lbl.setFixedWidth(width)
            lbl.setAlignment(align | Qt.AlignVCenter)
            lbl.setStyleSheet(
                f"color:{MUTED};font-size:10px;font-weight:bold;"
                f"letter-spacing:1px;background:transparent;"
            )
            chl.addWidget(lbl)
        
        chl.addStretch()
        layout.addWidget(col_hdr)
        
        # Scrollable rows
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"""
            QScrollArea {{ border:none; background:{OFF_WHITE}; }}
            QScrollBar:vertical {{
                background:{LIGHT}; width:8px; border-radius:4px;
            }}
            QScrollBar::handle:vertical {{
                background:#b0c4de; border-radius:4px; min-height:32px;
            }}
        """)
        
        self._rows_widget = QWidget()
        self._rows_widget.setStyleSheet(f"background:{OFF_WHITE};")
        self._rows_layout = QVBoxLayout(self._rows_widget)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(0)
        self._rows_layout.addStretch()
        
        scroll.setWidget(self._rows_widget)
        layout.addWidget(scroll, 1)
        
        return panel
    
    # -------------------------------------------------------------------------
    def _build_details_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"background:{WHITE};border-left:1px solid {BORDER};")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        hdr = QWidget()
        hdr.setFixedHeight(54)
        hdr.setStyleSheet(f"background:{WHITE};border-bottom:1px solid {BORDER};")
        hdr_layout = QHBoxLayout(hdr)
        hdr_layout.setContentsMargins(20, 0, 20, 0)
        
        self._detail_title = QLabel("Select a quotation")
        self._detail_title.setStyleSheet(
            f"font-size:14px;font-weight:bold;color:{DARK_TEXT};background:transparent;"
        )
        hdr_layout.addWidget(self._detail_title)
        hdr_layout.addStretch()
        
        self._copy_btn = _action_btn("Copy", color=WHITE, hover=LIGHT, text_color=DARK_TEXT, border=BORDER)
        self._copy_btn.clicked.connect(self._copy_to_clipboard)
        self._copy_btn.setEnabled(False)
        hdr_layout.addWidget(self._copy_btn)
        
        layout.addWidget(hdr)
        
        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"QScrollArea {{ border:none; background:{WHITE}; }}")
        
        self._detail_content = QWidget()
        self._detail_content.setStyleSheet(f"background:{WHITE};")
        self._detail_layout = QVBoxLayout(self._detail_content)
        self._detail_layout.setContentsMargins(20, 20, 20, 20)
        self._detail_layout.setSpacing(16)
        
        # Placeholder text
        placeholder = QLabel("👈 Select a quotation from the list to view details")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet(f"color:{MUTED};font-size:13px;background:transparent;padding:40px;")
        self._detail_layout.addWidget(placeholder)
        
        scroll.setWidget(self._detail_content)
        layout.addWidget(scroll, 1)
        
        return panel
    
    # -------------------------------------------------------------------------
    def _build_footer(self) -> QWidget:
        foot = QWidget()
        foot.setFixedHeight(36)
        foot.setStyleSheet(f"background:{WHITE};border-top:1px solid {BORDER};")
        fl = QHBoxLayout(foot)
        fl.setContentsMargins(20, 0, 20, 0)
        
        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet(f"font-size:11px;color:{MUTED};background:transparent;")
        fl.addWidget(self._count_lbl)
        
        fl.addStretch()
        
        # Sync stats
        self._sync_stats = QLabel("")
        self._sync_stats.setStyleSheet(f"font-size:11px;color:{SUCCESS};background:transparent;")
        fl.addWidget(self._sync_stats)
        
        return foot
    
    # -------------------------------------------------------------------------
    def _clear_rows(self):
        layout = self._rows_layout
        while layout.count() > 1:
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
    
    # -------------------------------------------------------------------------
    def _render(self, quotations: List[dict]):
        self._clear_rows()
        self._selected = {}
        
        for i, q in enumerate(quotations):
            row = self._make_row(q, i)
            self._rows_layout.insertWidget(self._rows_layout.count() - 1, row)
        
        total = len(self._quotations)
        shown = len(quotations)
        self._count_lbl.setText(
            f"{total} quotation{'s' if total != 1 else ''}" if shown == total
            else f"Showing {shown} of {total} quotations"
        )
    
    # -------------------------------------------------------------------------
    def _make_row(self, q: dict, idx: int) -> QWidget:
        bg = WHITE if idx % 2 == 0 else OFF_WHITE
        row_id = q.get("name", idx)
        row = QWidget()
        row.setObjectName(f"row_{row_id}")
        row.setFixedHeight(48)
        row.setStyleSheet(f"""
            QWidget#row_{row_id} {{
                background:{bg};
                border-bottom:1px solid {BORDER};
            }}
            QWidget#row_{row_id}:hover {{
                background:{LIGHT};
            }}
        """)
        row.setCursor(Qt.PointingHandCursor)
        
        rl = QHBoxLayout(row)
        rl.setContentsMargins(20, 0, 20, 0)
        rl.setSpacing(0)
        
        def _cell(text, width, align=Qt.AlignLeft, style=""):
            l = QLabel(text)
            l.setFixedWidth(width)
            l.setAlignment(align | Qt.AlignVCenter)
            l.setWordWrap(False)
            base = f"font-size:12px;color:{DARK_TEXT};background:transparent;"
            l.setStyleSheet(base + style)
            return l
        
        # Quotation #
        rl.addWidget(_cell(q.get("name", "—"), _COLS[0][1], Qt.AlignLeft, "font-weight:600;"))
        
        # Customer
        rl.addWidget(_cell(q.get("customer", "—"), _COLS[1][1], Qt.AlignLeft))
        
        # Date
        date_str = q.get("transaction_date", "")[:10]
        rl.addWidget(_cell(date_str, _COLS[2][1], Qt.AlignLeft, f"color:{MUTED};"))
        
        # Total
        total = float(q.get("grand_total", 0))
        total_str = f"${total:,.2f}"
        rl.addWidget(_cell(total_str, _COLS[3][1], Qt.AlignRight, "font-weight:600;"))
        
        # Status
        status = q.get("status", "Draft")
        status_color = SUCCESS if status == "Submitted" else (DANGER if status == "Cancelled" else WARNING)
        status_lbl = QLabel(status)
        status_lbl.setFixedWidth(_COLS[4][1])
        status_lbl.setAlignment(Qt.AlignCenter)
        status_lbl.setStyleSheet(f"""
            font-size:11px; font-weight:600; color:{status_color};
            background:transparent;
        """)
        rl.addWidget(status_lbl)
        
        # Synced badge
        synced = q.get("synced", False)
        sync_lbl = _status_badge("Synced" if synced else "Pending", "success" if synced else "warning")
        sync_lbl.setFixedWidth(_COLS[5][1])
        rl.addWidget(sync_lbl)
        
        rl.addStretch()
        
        # Click handlers
        row.mousePressEvent = lambda _ev, _q=q, _r=row: self._select_row(_q, _r)
        row.mouseDoubleClickEvent = lambda _ev, _q=q: self._show_quotation_details(_q)
        
        return row
    
    # -------------------------------------------------------------------------
    def _select_row(self, q: dict, row: QWidget):
        # Deselect previous
        prev = getattr(self, "_selected_row_widget", None)
        if prev:
            prev_id = self._selected.get("name", "")
            prev_bg = WHITE if self._selected.get("_idx", 0) % 2 == 0 else OFF_WHITE
            prev.setStyleSheet(f"""
                QWidget#row_{prev_id} {{
                    background:{prev_bg}; border-bottom:1px solid {BORDER};
                }}
                QWidget#row_{prev_id}:hover {{ background:{LIGHT}; }}
            """)
        
        self._selected = q
        self._selected_row_widget = row
        row_id = q.get("name", "")
        row.setStyleSheet(f"""
            QWidget#row_{row_id} {{
                background:{LIGHT}; border-bottom:1px solid {BORDER};
                border-left:3px solid {ACCENT};
            }}
        """)
        
        self._copy_btn.setEnabled(True)
        self._show_quotation_details(q)
    
    # -------------------------------------------------------------------------
    def _show_quotation_details(self, q: dict):
        """Display quotation details in right panel"""
        # Clear existing content
        self._clear_detail_panel()
        
        self._detail_title.setText(f"Quotation: {q.get('name', '—')}")
        
        layout = self._detail_layout
        
        # Info grid
        info_group = QGroupBox("Quotation Information")
        info_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight:bold; color:{DARK_TEXT}; border:1px solid {BORDER};
                border-radius:8px; margin-top:10px; padding-top:10px;
                background:{OFF_WHITE};
            }}
            QGroupBox::title {{ subcontrol-origin:margin; left:10px; padding:0 5px; }}
        """)
        grid = QGridLayout(info_group)
        grid.setSpacing(12)
        grid.setContentsMargins(16, 20, 16, 16)
        
        row = 0
        fields = [
            ("Quotation #:", q.get("name", "—")),
            ("Customer:", q.get("customer", "—")),
            ("Date:", q.get("transaction_date", "—")),
            ("Valid Till:", q.get("valid_till") or "—"),
            ("Reference #:", q.get("reference_number") or "—"),
            ("Company:", q.get("company", "—")),
            ("Status:", q.get("status", "—")),
            ("Grand Total:", f"${float(q.get('grand_total', 0)):,.2f}"),
            ("Synced:", "✓ Yes" if q.get("synced") else "✗ No"),
        ]
        
        for label, value in fields:
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color:{MUTED};font-weight:bold;background:transparent;")
            val_lbl = QLabel(str(value))
            val_lbl.setStyleSheet(f"color:{DARK_TEXT};background:transparent;")
            if "Total" in label:
                val_lbl.setStyleSheet(f"color:{SUCCESS};font-weight:bold;font-size:14px;background:transparent;")
            grid.addWidget(lbl, row, 0)
            grid.addWidget(val_lbl, row, 1)
            row += 1
        
        layout.addWidget(info_group)
        
        # Items table
        items_group = QGroupBox("Items")
        items_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight:bold; color:{DARK_TEXT}; border:1px solid {BORDER};
                border-radius:8px; margin-top:10px; padding-top:10px;
            }}
            QGroupBox::title {{ subcontrol-origin:margin; left:10px; padding:0 5px; }}
        """)
        items_layout = QVBoxLayout(items_group)
        
        items = q.get("items", [])
        
        if items:
            table = QTableWidget()
            table.setColumnCount(5)
            table.setHorizontalHeaderLabels(["Item Code", "Item Name", "Qty", "Rate", "Amount"])
            table.setRowCount(len(items))
            table.setAlternatingRowColors(True)
            table.setStyleSheet(f"""
                QTableWidget {{
                    background:{WHITE}; alternate-background-color:{OFF_WHITE};
                    border:none; gridline-color:{BORDER};
                }}
                QTableWidget::item {{ padding:8px; }}
                QHeaderView::section {{
                    background:{LIGHT}; color:{MUTED}; font-weight:bold;
                    padding:8px; border:none; border-bottom:1px solid {BORDER};
                }}
            """)
            
            for i, item in enumerate(items):
                table.setItem(i, 0, QTableWidgetItem(item.get("item_code", "—")))
                table.setItem(i, 1, QTableWidgetItem(item.get("item_name", "—")))
                table.setItem(i, 2, QTableWidgetItem(str(float(item.get("qty", 0)))))
                table.setItem(i, 3, QTableWidgetItem(f"${float(item.get('rate', 0)):.2f}"))
                table.setItem(i, 4, QTableWidgetItem(f"${float(item.get('amount', 0)):.2f}"))
            
            table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
            table.setFixedHeight(min(300, len(items) * 45 + 40))
            items_layout.addWidget(table)
        else:
            no_items = QLabel("No items in this quotation")
            no_items.setAlignment(Qt.AlignCenter)
            no_items.setStyleSheet(f"color:{MUTED};padding:20px;")
            items_layout.addWidget(no_items)
        
        layout.addWidget(items_group)
        
        # JSON view (collapsible)
        json_group = QGroupBox("Raw JSON")
        json_group.setCheckable(True)
        json_group.setChecked(False)
        json_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight:bold; color:{DARK_TEXT}; border:1px solid {BORDER};
                border-radius:8px; margin-top:10px; padding-top:10px;
            }}
            QGroupBox::title {{ subcontrol-origin:margin; left:10px; padding:0 5px; }}
        """)
        json_layout = QVBoxLayout(json_group)
        
        json_text = QTextEdit()
        json_text.setPlainText(json.dumps(q, indent=2, default=str))
        json_text.setFont(QFont("Consolas", 10))
        json_text.setStyleSheet(f"""
            QTextEdit {{
                background:{NAVY}; color:#a8d8ff;
                border:1px solid {BORDER}; border-radius:6px;
                padding:10px;
            }}
        """)
        json_text.setMinimumHeight(200)
        json_layout.addWidget(json_text)
        
        layout.addWidget(json_group)
        
        layout.addStretch()
    
    # -------------------------------------------------------------------------
    def _clear_detail_panel(self):
        """Clear the detail panel content"""
        while self._detail_layout.count():
            item = self._detail_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
    
    # -------------------------------------------------------------------------
    def _load_quotations(self):
        """Load quotations from local database"""
        try:
            from models.quotation import get_all_quotations
            
            quotations = get_all_quotations()
            self._quotations = [q.to_dict() for q in quotations]
            self._render(self._quotations)
            
            synced_count = sum(1 for q in self._quotations if q.get("synced"))
            self._sync_stats.setText(f"📁 {synced_count}/{len(self._quotations)} synced")
            
        except Exception as e:
            self._show_status(f"Error loading: {e}", error=True)
            self._quotations = []
            self._render([])
    
    # -------------------------------------------------------------------------
    def _sync_quotations(self):
        """Sync quotations from Frappe"""
        if self._syncing:
            return
        
        self._syncing = True
        self._sync_btn.setEnabled(False)
        self._sync_btn.setText("Syncing...")
        self._show_status("Syncing quotations from Frappe...")
        
        def do_sync():
            try:
                from models.quotation import sync_quotations_from_frappe
                
                result = sync_quotations_from_frappe()
                
                from PySide6.QtCore import QMetaObject, Qt, Q_ARG
                
                if result["success"]:
                    QMetaObject.invokeMethod(self, "_on_sync_success", 
                        Qt.QueuedConnection,
                        Q_ARG(int, result["synced"]),
                        Q_ARG(int, result["total"]))
                else:
                    QMetaObject.invokeMethod(self, "_on_sync_error",
                        Qt.QueuedConnection,
                        Q_ARG(str, result["message"]))
                        
            except Exception as e:
                QMetaObject.invokeMethod(self, "_on_sync_error",
                    Qt.QueuedConnection,
                    Q_ARG(str, str(e)))
        
        import threading
        threading.Thread(target=do_sync, daemon=True).start()
    
    # -------------------------------------------------------------------------
    def _on_sync_success(self, synced: int, total: int):
        """Called when sync completes successfully"""
        self._syncing = False
        self._sync_btn.setEnabled(True)
        self._sync_btn.setText("Sync from Frappe")
        self._show_status(f"Synced {synced} of {total} quotations")
        self._load_quotations()
        
        QMessageBox.information(self, "Sync Complete", 
            f"Successfully synced {synced} quotation(s).\nTotal received: {total}")
    
    # -------------------------------------------------------------------------
    def _on_sync_error(self, error_msg: str):
        """Called when sync fails"""
        self._syncing = False
        self._sync_btn.setEnabled(True)
        self._sync_btn.setText("Sync from Frappe")
        self._show_status(f"Sync failed: {error_msg}", error=True)
        
        QMessageBox.warning(self, "Sync Failed", f"Could not sync quotations:\n{error_msg}")
    
    # -------------------------------------------------------------------------
    def _filter(self, text: str):
        """Filter quotations by search text"""
        q = text.lower().strip()
        if not q:
            self._render(self._quotations)
            return
        
        filtered = [
            q for q in self._quotations
            if q.get("name", "").lower().find(q) >= 0
            or q.get("customer", "").lower().find(q) >= 0
            or q.get("reference_number", "").lower().find(q) >= 0
        ]
        self._render(filtered)
    
    # -------------------------------------------------------------------------
    def _copy_to_clipboard(self):
        """Copy selected quotation JSON to clipboard"""
        if self._selected:
            clipboard = QApplication.clipboard()
            clipboard.setText(json.dumps(self._selected, indent=2, default=str))
            self._show_status("Copied to clipboard!")
    
    # -------------------------------------------------------------------------
    def _show_status(self, msg: str, error: bool = False):
        """Show status message in footer"""
        color = DANGER if error else SUCCESS
        self._status_lbl.setStyleSheet(
            f"font-size:12px;background:transparent;color:{color};"
        )
        self._status_lbl.setText(msg)
        QTimer.singleShot(3000, lambda: self._status_lbl.setText(""))


# =============================================================================
# Quick access function
# =============================================================================

def show_quotations_dialog(parent=None, current_user=None):
    """Show the quotations dialog"""
    dialog = QuotationsDialog(parent, current_user)
    return dialog.exec()