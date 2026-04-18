# views/pos_view.py
import qtawesome as qta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QListWidget, QLineEdit, QScrollArea
)
from PySide6.QtCore import Qt
from models.product import (
    get_all_products, get_all_categories,
    search_products, get_products_by_category
)
from models.sale import create_sale
from views.receipt_dialog import ReceiptDialog


class POSView(QWidget):

    def __init__(self, on_sale=None):
        super().__init__()
        self.cart    = []
        self.on_sale = on_sale
        self._build_ui()
        self._load_categories()
        self._load_products(get_all_products())

    # ─────────────────────────────────────────────
    # UI BUILDER  (like your Django template)
    # ─────────────────────────────────────────────
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # ── LEFT PANEL ───────────────────────────
        left_panel = QWidget()
        left_panel.setStyleSheet("background-color: #1e1e2e;")
        left_col = QVBoxLayout(left_panel)
        left_col.setSpacing(12)
        left_col.setContentsMargins(16, 16, 16, 16)

        # Search bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search products...")
        self.search_input.setFixedHeight(44)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 10px;
                padding: 0px 14px;
                font-size: 14px;
            }
            QLineEdit:focus { border: 1px solid #cba6f7; }
        """)
        self.search_input.textChanged.connect(self._on_search)
        left_col.addWidget(self.search_input)

        # Category buttons row
        self.category_row = QHBoxLayout()
        self.category_row.setSpacing(8)
        left_col.addLayout(self.category_row)

        # Product grid — aligned to top so no empty gap
        self.products_area = QGridLayout()
        self.products_area.setSpacing(12)
        self.products_area.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        products_widget = QWidget()
        products_widget.setLayout(self.products_area)
        products_widget.setStyleSheet("background-color: transparent;")

        scroll = QScrollArea()
        scroll.setWidget(products_widget)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea         { border: none; background: transparent; }
            QScrollBar:vertical { background: #181825; width: 6px; border-radius: 3px; }
            QScrollBar::handle:vertical { background: #45475a; border-radius: 3px; }
        """)

        left_col.addWidget(scroll, 1)   # 1 = stretch to fill remaining height

        # ── RIGHT PANEL ──────────────────────────
        right_panel = QWidget()
        right_panel.setFixedWidth(320)
        right_panel.setStyleSheet("""
            background-color: #181825;
            border-left: 1px solid #313244;
        """)
        right_col = QVBoxLayout(right_panel)
        right_col.setSpacing(10)
        right_col.setContentsMargins(16, 16, 16, 16)

        # Cart header
        cart_label = QLabel("Cart")
        cart_label.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #cdd6f4;
            padding-bottom: 4px;
        """)
        right_col.addWidget(cart_label)

        # Cart list — stretches to fill space
        self.cart_list = QListWidget()
        self.cart_list.setSpacing(4)
        self.cart_list.setStyleSheet("""
            QListWidget {
                background-color: #1e1e2e;
                border: 1px solid #313244;
                border-radius: 10px;
                padding: 6px;
                color: #cdd6f4;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 8px 6px;
                border-radius: 6px;
            }
            QListWidget::item:hover { background-color: #313244; }
        """)
        right_col.addWidget(self.cart_list, 1)   # 1 = take all leftover height

        # Divider line
        divider = QWidget()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background-color: #313244;")
        right_col.addWidget(divider)

        # Total label
        self.total_label = QLabel("Total:   $0.00")
        self.total_label.setAlignment(Qt.AlignRight)
        self.total_label.setStyleSheet("""
            font-size: 22px;
            font-weight: bold;
            color: #a6e3a1;
            padding: 6px 0px;
        """)
        right_col.addWidget(self.total_label)

        # Clear button
        clear_btn = QPushButton("Clear Cart")
        clear_btn.setIcon(qta.icon("fa5s.trash", color="#f38ba8"))
        clear_btn.setFixedHeight(38)
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #313244;
                color: #f38ba8;
                border: 1px solid #45475a;
                border-radius: 8px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #45475a; }
        """)
        clear_btn.clicked.connect(self._clear_cart)
        right_col.addWidget(clear_btn)

        # Checkout button
        checkout_btn = QPushButton("CHECKOUT")
        checkout_btn.setFixedHeight(58)
        checkout_btn.setCursor(Qt.PointingHandCursor)
        checkout_btn.setStyleSheet("""
            QPushButton {
                background-color: #a6e3a1;
                color: #1e1e2e;
                font-size: 16px;
                font-weight: bold;
                border-radius: 12px;
                border: none;
            }
            QPushButton:hover  { background-color: #94d3a2; }
            QPushButton:pressed{ background-color: #74c99a; }
        """)
        checkout_btn.clicked.connect(self._checkout)
        right_col.addWidget(checkout_btn)

        # Add both panels to root
        root.addWidget(left_panel,  1)   # left stretches
        root.addWidget(right_panel)      # right is fixed 320px

    # ─────────────────────────────────────────────
    # DATA LOADERS  (like Django view queryset)
    # ─────────────────────────────────────────────
    def _load_categories(self):
        categories = get_all_categories()

        all_btn = QPushButton("All")
        all_btn.setFixedHeight(32)
        all_btn.setCursor(Qt.PointingHandCursor)
        all_btn.setStyleSheet(self._category_btn_style(active=True))
        all_btn.clicked.connect(lambda: self._load_products(get_all_products()))
        self.category_row.addWidget(all_btn)

        for cat in categories:
            btn = QPushButton(cat)
            btn.setFixedHeight(32)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(self._category_btn_style(active=False))
            btn.clicked.connect(
                lambda _, c=cat: self._load_products(get_products_by_category(c))
            )
            self.category_row.addWidget(btn)

        self.category_row.addStretch()

    def _load_products(self, products):
        # clear old cards
        while self.products_area.count():
            item = self.products_area.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for index, p in enumerate(products):
            btn = QPushButton(f"{p['name']}\n${p['price']:.2f}")
            btn.setFixedSize(170, 90)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #313244;
                    color: #cdd6f4;
                    border: 1px solid #45475a;
                    border-radius: 12px;
                    font-size: 13px;
                    text-align: center;
                    padding: 8px;
                }
                QPushButton:hover {
                    background-color: #45475a;
                    border: 1px solid #cba6f7;
                    color: #cba6f7;
                }
                QPushButton:pressed {
                    background-color: #cba6f7;
                    color: #1e1e2e;
                }
            """)
            btn.clicked.connect(
                lambda _, name=p["name"], price=p["price"]: self._add_to_cart(name, price)
            )
            self.products_area.addWidget(btn, index // 3, index % 3)

    # ─────────────────────────────────────────────
    # ACTIONS  (like Django view POST handlers)
    # ─────────────────────────────────────────────
    def _on_search(self, text):
        if text.strip():
            self._load_products(search_products(text))
        else:
            self._load_products(get_all_products())

    def _add_to_cart(self, name, price):
        self.cart.append((name, price))
        self.cart_list.addItem(f"  {name:<20}  ${price:.2f}")
        self._update_total()

    def _update_total(self):
        total = sum(p for _, p in self.cart)
        self.total_label.setText(f"Total:   ${total:.2f}")

    def _clear_cart(self):
        self.cart.clear()
        self.cart_list.clear()
        self.total_label.setText("Total:   $0.00")

    def _checkout(self):
        if not self.cart:
            return
        sale_id, total = create_sale(self.cart)
        dialog = ReceiptDialog(self.cart, total, sale_id, parent=self)
        dialog.exec()
        self._clear_cart()
        if self.on_sale:
            self.on_sale()   # ping dashboard to refresh

    # ─────────────────────────────────────────────
    # STYLE HELPERS
    # ─────────────────────────────────────────────
    def _category_btn_style(self, active=False):
        if active:
            return """
                QPushButton {
                    background-color: #cba6f7;
                    color: #1e1e2e;
                    border: none;
                    border-radius: 8px;
                    font-size: 12px;
                    padding: 0px 14px;
                    font-weight: bold;
                }
            """
        return """
            QPushButton {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 8px;
                font-size: 12px;
                padding: 0px 14px;
            }
            QPushButton:hover {
                background-color: #45475a;
                border: 1px solid #cba6f7;
            }
        """