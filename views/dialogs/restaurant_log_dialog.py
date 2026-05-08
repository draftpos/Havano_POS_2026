# =============================================================================
# views/dialogs/restaurant_log_dialog.py
# =============================================================================

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor

# ERP Palette
HDR_BG      = "#1e293b"
HDR_TEXT    = "#f1f5f9"
WHITE       = "#ffffff"
BORDER      = "#d1d5db"
SURFACE     = "#f4f5f7"
TEXT        = "#111827"
TEXT_SEC    = "#6b7280"
ACCENT      = "#2563eb"

class RestaurantLogDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("KOT Traceability Log")
        self.setMinimumSize(900, 600)
        self.setStyleSheet(f"QDialog {{ background: {WHITE}; }}")

        self._build_ui()
        self._load_data()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Header
        hdr = QFrame()
        hdr.setFixedHeight(50)
        hdr.setStyleSheet(f"background: {HDR_BG}; border-bottom: 1px solid {BORDER};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(20, 0, 20, 0)
        
        title = QLabel("KOT CANCELLATION & MODIFICATION LOG")
        title.setStyleSheet(f"color: {HDR_TEXT}; font-size: 14px; font-weight: 700; letter-spacing: 0.5px;")
        hl.addWidget(title)
        hl.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(80)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: #94a3b8; border: 1px solid #334155;
                border-radius: 4px; padding: 5px; font-weight: 600;
            }}
            QPushButton:hover {{ background: #334155; color: {WHITE}; }}
        """)
        close_btn.clicked.connect(self.accept)
        hl.addWidget(close_btn)
        lay.addWidget(hdr)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "ID", "Order ID", "Action", "Reason", "User", "Timestamp"
        ])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setVisible(False)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)

        self.table.setStyleSheet(f"""
            QTableWidget {{
                background: {WHITE}; border: none; gridline-color: {SURFACE};
                font-size: 12px; color: {TEXT};
            }}
            QTableWidget::item {{ padding: 10px; }}
            QHeaderView::section {{
                background: {SURFACE}; color: {TEXT_SEC}; font-weight: 700;
                padding: 10px; border: none; border-bottom: 2px solid {BORDER};
            }}
        """)
        lay.addWidget(self.table)

    def _load_data(self):
        try:
            from database.db import get_connection, fetchall_dicts
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT l.id, l.order_id, l.action, l.reason, u.username, l.created_at
                FROM restaurant_kot_log l
                LEFT JOIN users u ON l.user_id = u.id
                ORDER BY l.created_at DESC
            """)
            rows = fetchall_dicts(cur)
            conn.close()

            self.table.setRowCount(len(rows))
            for i, r in enumerate(rows):
                self.table.setItem(i, 0, QTableWidgetItem(str(r['id'])))
                self.table.setItem(i, 1, QTableWidgetItem(f"ORD-{r['order_id']}"))
                
                action_item = QTableWidgetItem(str(r['action']).upper())
                if str(r['action']).lower() == 'cancel':
                    action_item.setForeground(QColor("#dc2626"))
                else:
                    action_item.setForeground(QColor("#d97706"))
                action_item.setFont(self._bold_font())
                
                self.table.setItem(i, 2, action_item)
                self.table.setItem(i, 3, QTableWidgetItem(str(r['reason'])))
                self.table.setItem(i, 4, QTableWidgetItem(str(r['username'] or "Unknown")))
                self.table.setItem(i, 5, QTableWidgetItem(str(r['created_at'])[:19]))
        except Exception as e:
            print(f"Error loading KOT log: {e}")

    def _bold_font(self):
        f = QFont(); f.setBold(True); return f
