import qtawesome as qta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QMenu, QFrame
)
from PySide6.QtCore import Qt, Signal

class StandardListView(QWidget):
    """
    A globally reusable, standard list view template similar to Odoo/Frappe.
    Provides standard capabilities: Search, Hide/Show Columns, and an Add button.
    """
    # Signal emitted when the Add button is clicked
    add_requested = Signal()
    # Signal emitted when search text changes
    search_changed = Signal(str)

    def __init__(self, title="List View", parent=None):
        super().__init__(parent)
        self.title_text = title
        self.headers = []
        self.setStyleSheet("background-color: #f5f8fc;")
        self._build_ui()

    def _build_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 1. Top Bar Frame
        self.top_frame = QFrame()
        self.top_frame.setStyleSheet("background-color: #ffffff; border-bottom: 1px solid #e4eaf4;")
        top_layout = QHBoxLayout(self.top_frame)
        top_layout.setContentsMargins(20, 15, 20, 15)

        # Title
        self.title_label = QLabel(self.title_text)
        self.title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #1a5fb4; border: none;")
        top_layout.addWidget(self.title_label)
        
        top_layout.addSpacing(20)

        # Add Button
        self.btn_add = QPushButton(" Add")
        self.btn_add.setIcon(qta.icon("fa5s.plus", color="white", scale_factor=0.8))
        self.btn_add.setStyleSheet("""
            QPushButton {
                background-color: #1a5fb4; color: white; border: none;
                border-radius: 4px; padding: 6px 16px; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background-color: #1c6dd0; }
        """)
        self.btn_add.clicked.connect(self.add_requested.emit)
        top_layout.addWidget(self.btn_add)
        
        top_layout.addStretch()

        # Search Bar
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search...")
        self.search_bar.setFixedWidth(350)
        self.search_bar.setStyleSheet("""
            QLineEdit {
                padding: 6px 12px; font-size: 13px; border: 1px solid #c8d8ec; 
                border-radius: 4px; background: white;
            }
        """)
        self.search_bar.textChanged.connect(self.search_changed.emit)
        self.search_bar.textChanged.connect(self._filter_table)
        top_layout.addWidget(self.search_bar)
        
        top_layout.addStretch()

        # Columns Visibility Button
        self.btn_columns = QPushButton(" Columns")
        self.btn_columns.setIcon(qta.icon("fa5s.columns", color="#1a5fb4", scale_factor=0.8))
        self.btn_columns.setStyleSheet("""
            QPushButton {
                background-color: white; color: #1a5fb4; 
                border: 1px solid #c8d8ec; border-radius: 4px; 
                padding: 6px 12px; font-size: 13px;
            }
            QPushButton:hover { background-color: #f0f4f8; }
        """)
        
        # Menu for toggling columns
        self.columns_menu = QMenu(self)
        self.columns_menu.setStyleSheet("""
            QMenu { background-color: white; border: 1px solid #c8d8ec; } 
            QMenu::item { padding: 6px 25px 6px 25px; color: #1a5fb4; } 
            QMenu::item:selected { background-color: #e8f1f8; color: #1a5fb4; }
        """)
        self.btn_columns.setMenu(self.columns_menu)
        top_layout.addWidget(self.btn_columns)

        self.main_layout.addWidget(self.top_frame)

        # 2. Table Area
        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(20, 20, 20, 20)
        
        self.table = QTableWidget()
        self.table.setStyleSheet('''
            QTableWidget { 
                gridline-color: #e4eaf4; 
                border: 1px solid #c8d8ec; 
                background-color: white; 
                font-size: 13px;
                color: #333333;
            }
            QHeaderView::section { 
                background-color: #fdfbf7; 
                padding: 8px; 
                border: none; 
                border-bottom: 2px solid #e4eaf4; 
                border-right: 1px solid #e4eaf4;
                font-weight: bold; 
                font-size: 13px; 
                color: #1a5fb4;
                text-align: left;
            }
            QTableWidget::item { 
                padding: 6px; 
                border-bottom: 1px solid #f0f4f8;
            }
            QTableWidget::item:selected {
                background-color: #e8f1f8;
                color: #1a5fb4;
            }
        ''')
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)

        self.content_layout.addWidget(self.table)
        self.main_layout.addLayout(self.content_layout)

    def set_headers(self, headers):
        """Sets the table headers and populates the Columns hide/show menu."""
        self.headers = headers
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        
        # Make all columns stretch equally and align headers to the left
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        self.columns_menu.clear()
        for idx, header in enumerate(headers):
            action = self.columns_menu.addAction(header)
            action.setCheckable(True)
            action.setChecked(True)
            # Use default argument binding for idx
            action.toggled.connect(lambda checked, col=idx: self._toggle_column(col, checked))

    def _toggle_column(self, col_index, is_checked):
        """Hides or shows the specific column."""
        self.table.setColumnHidden(col_index, not is_checked)

    def set_data(self, data_list):
        """
        Populates the table with data. 
        data_list should be a list of lists or tuples.
        """
        self.table.setRowCount(0)
        for row_idx, row_data in enumerate(data_list):
            self.table.insertRow(row_idx)
            for col_idx, item in enumerate(row_data):
                table_item = QTableWidgetItem(str(item))
                table_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                self.table.setItem(row_idx, col_idx, table_item)

    def add_custom_filter(self, widget):
        """Allows injecting custom filters (like Date pickers) into the top bar."""
        # Insert before the stretch (which is index 3: Title, Spacing, Add, Stretch)
        index = self.top_frame.layout().count() - 3
        self.top_frame.layout().insertWidget(index, widget)

    def get_table(self):
        """Returns the underlying QTableWidget for advanced customization."""
        return self.table

    def _filter_table(self, text):
        """Filters the table rows based on the search text."""
        text = text.lower()
        for row in range(self.table.rowCount()):
            match = False
            # Check if any column in the row contains the search text
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item and text in item.text().lower():
                    match = True
                    break
            self.table.setRowHidden(row, not match)
