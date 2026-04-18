# views/dashboard_view.py
import qtawesome as qta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QFrame
)
from PySide6.QtCore import Qt
from models.sale import get_all_sales, get_sales_summary, get_sale_items


class DashboardView(QWidget):

    def __init__(self):
        super().__init__()
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(20)
        root.setContentsMargins(24, 24, 24, 24)

        # ── Header ───────────────────────────────────
        header = QHBoxLayout()
        title = QLabel("Sales Dashboard")
        title.setStyleSheet("""
            font-size: 20px;
            font-weight: bold;
            color: #cdd6f4;
        """)
        header.addWidget(title)
        header.addStretch()
        root.addLayout(header)

        # ── Stat cards row ───────────────────────────
        self.cards_row = QHBoxLayout()
        self.cards_row.setSpacing(16)
        root.addLayout(self.cards_row)

        # ── Section label ────────────────────────────
        recent_label = QLabel("Recent Transactions")
        recent_label.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: #6c7086;
            padding-top: 8px;
        """)
        root.addWidget(recent_label)

        # ── Sales table ──────────────────────────────
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "  #", "  Items", "  Qty", "  Total", "  Date"
        ])

        # column widths
        self.table.setColumnWidth(0, 60)   # sale id
        self.table.setColumnWidth(1, 340)  # items
        self.table.setColumnWidth(2, 60)   # qty
        self.table.setColumnWidth(3, 100)  # total
        self.table.horizontalHeader().setStretchLastSection(True)  # date fills rest

        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setWordWrap(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)

        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #181825;
                border: 1px solid #313244;
                border-radius: 12px;
                font-size: 13px;
                color: #cdd6f4;
                gridline-color: transparent;
                outline: none;
            }
            QTableWidget::item {
                padding: 10px 8px;
                border-bottom: 1px solid #1e1e2e;
            }
            QTableWidget::item:selected {
                background-color: #313244;
                color: #cba6f7;
            }
            QTableWidget::item:alternate {
                background-color: #1e1e2e;
            }
            QHeaderView::section {
                background-color: #181825;
                color: #6c7086;
                font-size: 11px;
                font-weight: bold;
                padding: 10px 8px;
                border: none;
                border-bottom: 1px solid #313244;
                text-transform: uppercase;
            }
            QScrollBar:vertical {
                background: #181825;
                width: 6px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #45475a;
                border-radius: 3px;
            }
        """)

        root.addWidget(self.table, 1)   # 1 = stretch to fill remaining space

    # ─────────────────────────────────────────────
    # STAT CARD  — reusable widget
    # ─────────────────────────────────────────────
    def _stat_card(self, title, value, icon, color):
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #1e1e2e;
                border: 1px solid #313244;
                border-radius: 14px;
                padding: 8px;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setSpacing(6)
        layout.setContentsMargins(16, 16, 16, 16)

        # icon + title row
        top_row = QHBoxLayout()
        icon_label = QLabel()
        icon_label.setPixmap(qta.icon(icon, color=color).pixmap(20, 20))
        icon_label.setStyleSheet("background: transparent;")
        top_row.addWidget(icon_label)
        top_row.addStretch()
        layout.addLayout(top_row)

        # value
        val_label = QLabel(str(value))
        val_label.setStyleSheet(f"""
            font-size: 30px;
            font-weight: bold;
            color: {color};
            background: transparent;
        """)
        layout.addWidget(val_label)

        # title
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            font-size: 12px;
            color: #6c7086;
            background: transparent;
        """)
        layout.addWidget(title_label)

        return card

    # ─────────────────────────────────────────────
    # DATA LOADER
    # ─────────────────────────────────────────────
    def _load_data(self):
        summary = get_sales_summary()
        count   = summary["count"]   or 0
        revenue = summary["revenue"] or 0.0
        avg     = (revenue / count)  if count else 0.0

        # clear old cards
        while self.cards_row.count():
            item = self.cards_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 3 stat cards with different colors and icons
        self.cards_row.addWidget(
            self._stat_card("Total Sales",   str(count),         "fa5s.receipt",    "#cba6f7")
        )
        self.cards_row.addWidget(
            self._stat_card("Total Revenue", f"${revenue:.2f}",  "fa5s.money-bill", "#a6e3a1")
        )
        self.cards_row.addWidget(
            self._stat_card("Avg per Sale",  f"${avg:.2f}",      "fa5s.chart-line", "#89dceb")
        )

        # ── fill table ───────────────────────────
        sales = get_all_sales()
        self.table.setRowCount(len(sales))

        for i, sale in enumerate(sales):
            items     = get_sale_items(sale["id"])
            qty       = len(items)
            items_str = ",   ".join(
                f"{item['product_name']} (${item['price']:.2f})"
                for item in items
            )

            # Sale ID — centered
            id_item = QTableWidgetItem(str(sale["id"]))
            id_item.setTextAlignment(Qt.AlignCenter)

            # Items string
            items_item = QTableWidgetItem(items_str)

            # Qty badge — centered
            qty_item = QTableWidgetItem(str(qty))
            qty_item.setTextAlignment(Qt.AlignCenter)
            qty_item.setForeground(Qt.white)

            # Total — right aligned, green
            total_item = QTableWidgetItem(f"${sale['total']:.2f}")
            total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            total_item.setForeground(
                __import__('PySide6.QtGui', fromlist=['QColor']).QColor("#a6e3a1")
            )

            # Date
            date_item = QTableWidgetItem(sale["created_at"])
            date_item.setForeground(
                __import__('PySide6.QtGui', fromlist=['QColor']).QColor("#6c7086")
            )

            self.table.setItem(i, 0, id_item)
            self.table.setItem(i, 1, items_item)
            self.table.setItem(i, 2, qty_item)
            self.table.setItem(i, 3, total_item)
            self.table.setItem(i, 4, date_item)

            self.table.setRowHeight(i, 52)

    def refresh(self):
        """Called after every checkout — live update"""
        self._load_data()
