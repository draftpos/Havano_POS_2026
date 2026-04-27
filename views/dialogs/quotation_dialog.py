# views/dialogs/quotation_dialog.py
# =============================================================================

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QPushButton,
    QFrame, QWidget, QMessageBox, QLineEdit, QComboBox,
    QSplitter, QProgressBar, QApplication, QDateEdit
)
from PySide6.QtCore import Qt, Signal, QTimer, QThread, QObject
from PySide6.QtGui import QColor, QFont
from datetime import datetime, timedelta
from typing import List
import traceback

try:
    import qtawesome as qta
except Exception:  # pragma: no cover — icons are optional decoration
    qta = None


class QuotationDialog(QDialog):

    quotation_converted = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.current_quotation = None
        self.quotations = []
        self.all_quotations = []

        self.setWindowTitle("Quotations")
        self.setMinimumSize(1300, 850)
        self.setModal(False)
        self.setWindowState(Qt.WindowMaximized)

        self._setup_styles()
        self._build_ui()
        self._load_quotations()

        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(300)
        self.search_timer.timeout.connect(self._apply_search)

    def _setup_styles(self):
        self.setStyleSheet("""
            QDialog {
                background: #f0f2f5;
            }
            QLabel {
                color: #1a1a2e;
                font-size: 13px;
                background: transparent;
            }
            QLineEdit, QComboBox, QDateEdit {
                background: white;
                color: #1a1a2e;
                border: 1px solid #d0d5dd;
                border-radius: 6px;
                padding: 7px 12px;
                font-size: 13px;
                min-height: 20px;
            }
            QLineEdit:focus, QComboBox:focus, QDateEdit:focus {
                border: 2px solid #2563eb;
            }
            QLineEdit:hover, QComboBox:hover, QDateEdit:hover {
                border: 1px solid #2563eb;
            }
            QComboBox::drop-down { border: none; width: 24px; }
            QDateEdit::drop-down { border: none; width: 24px; }
            QTableWidget {
                background: white;
                border: none;
                gridline-color: #f0f2f5;
                font-size: 13px;
                selection-background-color: #eff6ff;
                selection-color: #1e40af;
                alternate-background-color: #f8fafc;
            }
            QTableWidget::item {
                padding: 10px 10px;
                border-bottom: 1px solid #f0f2f5;
                color: #1a1a2e;
            }
            QTableWidget::item:selected {
                background: #eff6ff;
                color: #1e40af;
            }
            QHeaderView::section {
                background: #f8fafc;
                color: #64748b;
                padding: 10px 10px;
                font-weight: 600;
                font-size: 11px;
                border: none;
                border-bottom: 2px solid #e2e8f0;
                letter-spacing: 0.3px;
            }
            QPushButton {
                border: none;
                border-radius: 6px;
                padding: 9px 20px;
                font-weight: 600;
                font-size: 13px;
                font-family: 'Segoe UI', sans-serif;
            }
            QPushButton#primaryBtn   { background: #2563eb; color: white; }
            QPushButton#primaryBtn:hover   { background: #1d4ed8; }
            QPushButton#dangerBtn    { background: #ef4444; color: white; }
            QPushButton#dangerBtn:hover    { background: #dc2626; }
            QPushButton#secondaryBtn { background: #64748b; color: white; }
            QPushButton#secondaryBtn:hover { background: #475569; }
            QPushButton#successBtn   { background: #16a34a; color: white; }
            QPushButton#successBtn:hover   { background: #15803d; }
            QPushButton#warningBtn   { background: #f59e0b; color: white; }
            QPushButton#warningBtn:hover   { background: #d97706; }
            QPushButton:disabled     { background: #e2e8f0; color: #94a3b8; }
            QProgressBar {
                border: none;
                border-radius: 4px;
                background: #e2e8f0;
                height: 6px;
                text-align: center;
            }
            QProgressBar::chunk {
                background: #2563eb;
                border-radius: 4px;
            }
            QSplitter::handle { background: #e2e8f0; width: 2px; }
            QFrame#card {
                background: white;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
            }
        """)

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(18, 18, 18, 12)

        # ── Header bar ───────────────────────────────────────────────
        header_row = QHBoxLayout()

        title = QLabel("Quotations")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #1e40af; letter-spacing: -0.3px;")
        header_row.addWidget(title)
        header_row.addStretch()

        # Buttons on the right of the header
        self.fetch_external_btn = QPushButton("Fetch External")
        self.fetch_external_btn.setObjectName("warningBtn")
        self.fetch_external_btn.setToolTip("Pull quotations from the configured external site")
        self.fetch_external_btn.clicked.connect(self._fetch_external_quotations)
        header_row.addWidget(self.fetch_external_btn)

        # Commented out external settings button
        # self.ext_settings_btn = QPushButton("External Site Settings")
        # self.ext_settings_btn.setObjectName("secondaryBtn")
        # self.ext_settings_btn.setToolTip("Configure URL / API key for external site")
        # self.ext_settings_btn.clicked.connect(self._open_external_settings)
        # header_row.addWidget(self.ext_settings_btn)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setObjectName("primaryBtn")
        self.refresh_btn.clicked.connect(self._load_quotations)
        header_row.addWidget(self.refresh_btn)

        # Back to POS — lets the user close the Quotations view and return to
        # the cart (important for pharmacists who auto-land here on login).
        self.back_to_pos_btn = QPushButton("Back to POS")
        self.back_to_pos_btn.setObjectName("secondaryBtn")
        self.back_to_pos_btn.setToolTip("Close Quotations and return to the POS cart")
        if qta is not None:
            try:
                self.back_to_pos_btn.setIcon(qta.icon("fa5s.arrow-left", color="white"))
            except Exception:
                pass
        self.back_to_pos_btn.clicked.connect(self.reject)
        header_row.addWidget(self.back_to_pos_btn)

        main_layout.addLayout(header_row)

        # ── Search / filter toolbar ───────────────────────────────────
        toolbar_frame = QFrame()
        toolbar_frame.setObjectName("card")
        toolbar_frame.setStyleSheet("QFrame#card { background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 4px 8px; }")
        toolbar_layout = QHBoxLayout(toolbar_frame)
        toolbar_layout.setContentsMargins(12, 8, 12, 8)
        toolbar_layout.setSpacing(12)

        search_lbl = QLabel("Search")
        search_lbl.setStyleSheet("font-weight: 600; color: #475569; font-size: 12px;")
        toolbar_layout.addWidget(search_lbl)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Quotation number, customer or reference...")
        self.search_input.setMinimumWidth(320)
        self.search_input.textChanged.connect(self._on_search_changed)
        toolbar_layout.addWidget(self.search_input)

        status_lbl = QLabel("Status")
        status_lbl.setStyleSheet("font-weight: 600; color: #475569; font-size: 12px;")
        toolbar_layout.addWidget(status_lbl)

        self.status_filter = QComboBox()
        self.status_filter.addItems(["All", "Submitted", "Draft", "Cancelled"])
        self.status_filter.setFixedWidth(130)
        self.status_filter.currentTextChanged.connect(self._apply_search)
        toolbar_layout.addWidget(self.status_filter)

        # Created On filter
        created_on_lbl = QLabel("Created On")
        created_on_lbl.setStyleSheet("font-weight: 600; color: #475569; font-size: 12px;")
        toolbar_layout.addWidget(created_on_lbl)

        self.date_filter = QComboBox()
        self.date_filter.addItems(["All", "Today", "Yesterday", "This Week", "This Month", "Custom"])
        self.date_filter.setCurrentText("Today")
        self.date_filter.setFixedWidth(130)
        self.date_filter.currentTextChanged.connect(self._on_date_filter_changed)
        toolbar_layout.addWidget(self.date_filter)

        self.custom_date = QDateEdit()
        self.custom_date.setCalendarPopup(True)
        self.custom_date.setDate(datetime.now().date())
        self.custom_date.setFixedWidth(130)
        self.custom_date.setVisible(False)
        self.custom_date.dateChanged.connect(self._apply_search)
        toolbar_layout.addWidget(self.custom_date)

        toolbar_layout.addStretch()

        self.quotation_count_lbl = QLabel("0 quotations")
        self.quotation_count_lbl.setStyleSheet("color: #94a3b8; font-size: 12px;")
        toolbar_layout.addWidget(self.quotation_count_lbl)

        main_layout.addWidget(toolbar_frame)

        # ── Main splitter ─────────────────────────────────────────────
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(2)

        # Left — quotations list
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        list_card = QFrame()
        list_card.setObjectName("card")
        list_card.setStyleSheet("QFrame#card { background: white; border: 1px solid #e2e8f0; border-radius: 10px; }")
        list_card_layout = QVBoxLayout(list_card)
        list_card_layout.setContentsMargins(0, 0, 0, 0)
        list_card_layout.setSpacing(0)

        self.quotation_table = QTableWidget(0, 6)
        self.quotation_table.setHorizontalHeaderLabels([
            "Quotation", "Date", "Customer", "Valid Till", "Status", "Total"
        ])
        hv = self.quotation_table.horizontalHeader()
        hv.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hv.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hv.setSectionResizeMode(2, QHeaderView.Stretch)
        hv.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hv.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        hv.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.quotation_table.verticalHeader().setVisible(False)
        self.quotation_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.quotation_table.setAlternatingRowColors(True)
        self.quotation_table.setSortingEnabled(True)
        self.quotation_table.setShowGrid(False)
        self.quotation_table.setFocusPolicy(Qt.StrongFocus)
        self.quotation_table.itemSelectionChanged.connect(self._on_quotation_selected)
        self.quotation_table.doubleClicked.connect(self._on_double_click)

        list_card_layout.addWidget(self.quotation_table)
        left_layout.addWidget(list_card)

        # Right — details panel
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(8, 0, 0, 0)
        right_layout.setSpacing(10)

        # Customer info card
        info_card = QFrame()
        info_card.setObjectName("card")
        info_card.setStyleSheet("QFrame#card { background: white; border: 1px solid #e2e8f0; border-radius: 10px; padding: 6px; }")
        info_layout = QVBoxLayout(info_card)
        info_layout.setSpacing(10)
        info_layout.setContentsMargins(16, 14, 16, 14)

        # Top row: customer name + status badge
        top_row = QHBoxLayout()
        self.customer_name_label = QLabel("—")
        self.customer_name_label.setStyleSheet("font-size: 17px; font-weight: 700; color: #1e40af;")
        top_row.addWidget(self.customer_name_label)
        top_row.addStretch()

        self.status_badge = QLabel("—")
        self.status_badge.setAlignment(Qt.AlignCenter)
        self.status_badge.setFixedHeight(24)
        self.status_badge.setStyleSheet("""
            QLabel {
                background: #e2e8f0; color: #64748b;
                border-radius: 12px; padding: 2px 14px;
                font-weight: 700; font-size: 11px;
            }
        """)
        top_row.addWidget(self.status_badge)
        info_layout.addLayout(top_row)

        # Details grid
        grid = QHBoxLayout()
        grid.setSpacing(24)

        def _detail_col(*pairs):
            col = QVBoxLayout()
            col.setSpacing(4)
            labels = []
            for lbl_text, _ in pairs:
                lbl = QLabel(lbl_text)
                lbl.setStyleSheet("font-size: 11px; color: #94a3b8; font-weight: 600;")
                col.addWidget(lbl)
                val = QLabel("—")
                val.setStyleSheet("font-size: 13px; font-weight: 600; color: #1a1a2e;")
                col.addWidget(val)
                labels.append(val)
                col.addSpacing(6)
            return col, labels

        col1, [self.quotation_ref_label, self.company_label] = _detail_col(
            ("QUOTATION", ""), ("COMPANY", "")
        )
        col2, [self.transaction_date_label, self.valid_till_label] = _detail_col(
            ("DATE", ""), ("VALID UNTIL", "")
        )
        grid.addLayout(col1)
        grid.addLayout(col2)
        grid.addStretch()
        info_layout.addLayout(grid)

        right_layout.addWidget(info_card)

        # Summary card
        summary_card = QFrame()
        summary_card.setObjectName("card")
        summary_card.setStyleSheet("QFrame#card { background: white; border: 1px solid #e2e8f0; border-radius: 10px; }")
        summary_layout = QHBoxLayout(summary_card)
        summary_layout.setContentsMargins(20, 14, 20, 14)

        def _stat(title, large=False):
            col = QVBoxLayout()
            col.setSpacing(2)
            t = QLabel(title)
            t.setStyleSheet("font-size: 11px; color: #94a3b8; font-weight: 600;")
            v = QLabel("—")
            size = "20px" if large else "26px"
            color = "#1e40af" if not large else "#16a34a"
            v.setStyleSheet(f"font-size: {size}; font-weight: 700; color: {color};")
            col.addWidget(t)
            col.addWidget(v)
            return col, v

        col_items, self.items_count_label = _stat("ITEMS")
        col_total, self.grand_total_label = _stat("GRAND TOTAL", large=True)

        summary_layout.addLayout(col_items)
        summary_layout.addStretch()
        summary_layout.addLayout(col_total)
        right_layout.addWidget(summary_card)

        # Items table card
        items_card = QFrame()
        items_card.setObjectName("card")
        items_card.setStyleSheet("QFrame#card { background: white; border: 1px solid #e2e8f0; border-radius: 10px; }")
        items_card_layout = QVBoxLayout(items_card)
        items_card_layout.setContentsMargins(0, 0, 0, 0)
        items_card_layout.setSpacing(0)

        items_title_row = QHBoxLayout()
        items_title_row.setContentsMargins(16, 12, 16, 8)
        items_title = QLabel("Line Items")
        items_title.setStyleSheet("font-weight: 700; font-size: 13px; color: #1a1a2e;")
        items_title_row.addWidget(items_title)
        items_card_layout.addLayout(items_title_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #f0f2f5;")
        items_card_layout.addWidget(sep)

        self.items_table = QTableWidget(0, 5)
        self.items_table.setHorizontalHeaderLabels(["Item Code", "Description", "Qty", "Rate", "Amount"])
        iv = self.items_table.horizontalHeader()
        iv.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        iv.setSectionResizeMode(1, QHeaderView.Stretch)
        iv.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        iv.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        iv.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.items_table.verticalHeader().setVisible(False)
        self.items_table.setAlternatingRowColors(True)
        self.items_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.items_table.setShowGrid(False)
        items_card_layout.addWidget(self.items_table)

        right_layout.addWidget(items_card, 1)

        # Action buttons
        action_layout = QHBoxLayout()
        action_layout.setSpacing(10)
        action_layout.setContentsMargins(0, 4, 0, 0)

        self.convert_btn = QPushButton("Load to Cart")
        self.convert_btn.setObjectName("successBtn")
        self.convert_btn.setEnabled(False)
        self.convert_btn.setMinimumWidth(130)
        self.convert_btn.clicked.connect(self._convert_to_sale)

        # Pharmacy label preview — enabled only when exactly one row is selected
        self.label_preview_btn = QPushButton("Preview Label")
        self.label_preview_btn.setObjectName("primaryBtn")
        self.label_preview_btn.setEnabled(False)
        self.label_preview_btn.setToolTip(
            "Preview pharmacy labels for pharmacy items on this quotation"
        )
        if qta is not None:
            try:
                self.label_preview_btn.setIcon(
                    qta.icon("fa5s.prescription-bottle-alt", color="white")
                )
            except Exception:
                pass
        self.label_preview_btn.clicked.connect(self._preview_pharmacy_labels)

        # Reprint — prints ZPL labels for the selected quotation inline
        self.reprint_btn = QPushButton("Reprint Labels")
        self.reprint_btn.setObjectName("primaryBtn")
        self.reprint_btn.setEnabled(False)
        self.reprint_btn.setToolTip("Reprint pharmacy labels for this quotation")
        if qta is not None:
            try:
                self.reprint_btn.setIcon(qta.icon("fa5s.print", color="white"))
            except Exception:
                pass
        self.reprint_btn.clicked.connect(self._reprint_labels)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setObjectName("dangerBtn")
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._delete_quotation)

        close_btn = QPushButton("Close")
        close_btn.setObjectName("secondaryBtn")
        close_btn.clicked.connect(self.accept)

        action_layout.addStretch()
        action_layout.addWidget(self.reprint_btn)
        action_layout.addWidget(self.convert_btn)
        action_layout.addWidget(self.label_preview_btn)
        action_layout.addWidget(self.delete_btn)
        action_layout.addWidget(close_btn)
        right_layout.addLayout(action_layout)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([620, 580])
        main_layout.addWidget(splitter, 1)

        # ── Status bar ────────────────────────────────────────────────
        status_bar = QFrame()
        status_bar.setStyleSheet("QFrame { background: white; border: 1px solid #e2e8f0; border-radius: 6px; }")
        status_bar_layout = QHBoxLayout(status_bar)
        status_bar_layout.setContentsMargins(12, 6, 12, 6)

        self.status_label_bottom = QLabel("Ready")
        self.status_label_bottom.setStyleSheet("color: #64748b; font-size: 12px;")
        status_bar_layout.addWidget(self.status_label_bottom)
        status_bar_layout.addStretch()

        self.sync_progress = QProgressBar()
        self.sync_progress.setVisible(False)
        self.sync_progress.setMaximumWidth(140)
        self.sync_progress.setMaximumHeight(6)
        self.sync_progress.setTextVisible(False)
        status_bar_layout.addWidget(self.sync_progress)

        main_layout.addWidget(status_bar)

    # ─────────────────────────────────────────────────────────────────
    # Search / filter
    # ─────────────────────────────────────────────────────────────────

    def _on_search_changed(self):
        self.search_timer.start()

    def _on_date_filter_changed(self):
        """Show/hide custom date picker and apply filter"""
        if self.date_filter.currentText() == "Custom":
            self.custom_date.setVisible(True)
        else:
            self.custom_date.setVisible(False)
        self._apply_search()

    def _get_date_filter_range(self):
        """Get date range based on selected filter"""
        filter_text = self.date_filter.currentText()
        today = datetime.now().date()
        
        if filter_text == "Today":
            return today, today
        elif filter_text == "Yesterday":
            yesterday = today - timedelta(days=1)
            return yesterday, yesterday
        elif filter_text == "This Week":
            start = today - timedelta(days=today.weekday())
            return start, today
        elif filter_text == "This Month":
            start = today.replace(day=1)
            return start, today
        elif filter_text == "Custom":
            custom_date = self.custom_date.date().toPython()
            return custom_date, custom_date
        else:  # "All"
            return None, None

    def _apply_search(self):
        search_text   = self.search_input.text().strip().lower()
        status_filter = self.status_filter.currentText()
        
        # Get date filter range
        date_start, date_end = self._get_date_filter_range()

        filtered = []
        for q in self.all_quotations:
            # Status filter
            if status_filter != "All" and q.status != status_filter:
                continue
            
            # Date filter
            if date_start and date_end:
                try:
                    # Parse transaction_date (format: YYYY-MM-DD)
                    q_date = datetime.strptime(q.transaction_date[:10], "%Y-%m-%d").date()
                    if q_date < date_start or q_date > date_end:
                        continue
                except:
                    # If date parsing fails, include the quotation
                    pass
            
            # Search filter
            if search_text:
                if not (search_text in q.name.lower()
                        or search_text in q.customer.lower()
                        or (q.reference_number and search_text in q.reference_number.lower())):
                    continue
                    
            filtered.append(q)

        self.quotations = filtered
        self._update_quotation_table()
        total = len(self.all_quotations)
        shown = len(filtered)
        self.quotation_count_lbl.setText(
            f"{shown} of {total} quotations" if shown != total else f"{total} quotations"
        )

    # ─────────────────────────────────────────────────────────────────
    # Load / table
    # ─────────────────────────────────────────────────────────────────

    def _load_quotations(self):
        try:
            from models.quotation import get_all_quotations
            self.status_label_bottom.setText("Loading...")
            QApplication.processEvents()
            self.all_quotations = get_all_quotations()
            self._apply_search()
            self.status_label_bottom.setText(f"Loaded {len(self.all_quotations)} quotations")
        except Exception as e:
            self.status_label_bottom.setText(f"Error: {str(e)[:60]}")
            QMessageBox.warning(self, "Load Error", f"Failed to load quotations:\n{e}")
            traceback.print_exc()

    def _update_quotation_table(self):
        self.quotation_table.setRowCount(0)
        self.quotation_table.setSortingEnabled(False)

        STATUS_COLORS = {
            "Submitted": "#16a34a",
            "Draft":     "#d97706",
            "Cancelled": "#ef4444",
        }

        for row, q in enumerate(self.quotations):
            self.quotation_table.insertRow(row)

            name_item = QTableWidgetItem(q.name)
            name_item.setData(Qt.UserRole, q)
            name_item.setFont(QFont("Segoe UI", 12, QFont.Bold))
            self.quotation_table.setItem(row, 0, name_item)

            date_str = q.transaction_date[:10] if len(q.transaction_date) >= 10 else q.transaction_date
            self.quotation_table.setItem(row, 1, QTableWidgetItem(date_str))

            self.quotation_table.setItem(row, 2, QTableWidgetItem(q.customer))

            valid = (q.valid_till[:10] if q.valid_till and len(q.valid_till) >= 10
                     else (q.valid_till or "—"))
            self.quotation_table.setItem(row, 3, QTableWidgetItem(valid))

            status_item = QTableWidgetItem(q.status)
            color = STATUS_COLORS.get(q.status, "#64748b")
            status_item.setForeground(QColor(color))
            status_item.setFont(QFont("Segoe UI", 11, QFont.Bold))
            self.quotation_table.setItem(row, 4, status_item)

            total_item = QTableWidgetItem(f"${q.grand_total:,.2f}")
            total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            total_item.setFont(QFont("Segoe UI", 12, QFont.Bold))
            self.quotation_table.setItem(row, 5, total_item)

            self.quotation_table.setRowHeight(row, 42)

        self.quotation_table.setSortingEnabled(True)

    # ─────────────────────────────────────────────────────────────────
    # Selection / details
    # ─────────────────────────────────────────────────────────────────

    def _on_quotation_selected(self):
        selected = self.quotation_table.selectedItems()
        if not selected:
            self.convert_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            self.label_preview_btn.setEnabled(False)
            self.reprint_btn.setEnabled(False)
            self.current_quotation = None
            return

        # Only enable row-action buttons when exactly one row is selected.
        selected_rows = {idx.row() for idx in self.quotation_table.selectedIndexes()}
        single_selection = len(selected_rows) == 1

        row  = selected[0].row()
        item = self.quotation_table.item(row, 0)
        self.current_quotation = item.data(Qt.UserRole)

        if self.current_quotation:
            can_convert = self.current_quotation.can_convert_to_sale()
            self.convert_btn.setEnabled(can_convert)
            self.delete_btn.setEnabled(True)
            self.label_preview_btn.setEnabled(single_selection)
            self.reprint_btn.setEnabled(single_selection)
            self._display_quotation_details(self.current_quotation)
            self.convert_btn.setToolTip(
                "Load quotation items into cart" if can_convert
                else f"Cannot load — status is '{self.current_quotation.status}'"
            )

    def _on_double_click(self, index):
        if self.current_quotation and self.current_quotation.can_convert_to_sale():
            self._convert_to_sale()

    def _display_quotation_details(self, quotation):
        self.customer_name_label.setText(quotation.customer or "—")
        self.quotation_ref_label.setText(quotation.name or "—")
        self.company_label.setText(quotation.company or "—")

        date_str = (quotation.transaction_date[:10]
                    if len(quotation.transaction_date) >= 10
                    else quotation.transaction_date)
        self.transaction_date_label.setText(date_str)

        valid = (quotation.valid_till[:10]
                 if quotation.valid_till and len(quotation.valid_till) >= 10
                 else (quotation.valid_till or "—"))
        self.valid_till_label.setText(valid)

        # Status badge
        STATUS_BADGE = {
            "Submitted": ("SUBMITTED", "#16a34a", "white"),
            "Draft":     ("DRAFT",     "#f59e0b", "white"),
            "Cancelled": ("CANCELLED", "#ef4444", "white"),
        }
        text, bg, fg = STATUS_BADGE.get(quotation.status, (quotation.status, "#e2e8f0", "#64748b"))
        self.status_badge.setText(text)
        self.status_badge.setStyleSheet(f"""
            QLabel {{
                background: {bg}; color: {fg};
                border-radius: 12px; padding: 2px 14px;
                font-weight: 700; font-size: 11px;
            }}
        """)

        # Summary — show line count, not sum of qtys
        self.items_count_label.setText(str(len(quotation.items)))
        self.grand_total_label.setText(f"${quotation.grand_total:,.2f}")

        # Items table
        self.items_table.setRowCount(0)
        for row, item in enumerate(quotation.items):
            self.items_table.insertRow(row)

            self.items_table.setItem(row, 0, QTableWidgetItem(item.item_code))
            self.items_table.setItem(row, 1, QTableWidgetItem(item.description or item.item_name))

            # Qty: show as integer if whole number, else 2dp
            qty_val = item.qty
            qty_str = str(int(qty_val)) if qty_val == int(qty_val) else f"{qty_val:,.2f}"
            qty_item = QTableWidgetItem(qty_str)
            qty_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.items_table.setItem(row, 2, qty_item)

            rate_item = QTableWidgetItem(f"${item.rate:,.2f}")
            rate_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.items_table.setItem(row, 3, rate_item)

            amount_item = QTableWidgetItem(f"${item.amount:,.2f}")
            amount_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.items_table.setItem(row, 4, amount_item)

            self.items_table.setRowHeight(row, 34)

    # ─────────────────────────────────────────────────────────────────
    # Convert to cart
    # ─────────────────────────────────────────────────────────────────

    def _convert_to_sale(self):
        if not self.current_quotation:
            return

        if not self.current_quotation.can_convert_to_sale():
            QMessageBox.warning(
                self, "Cannot Load",
                f"This quotation has status '{self.current_quotation.status}'.\n"
                "Cancelled or already-converted quotations cannot be loaded."
            )
            return

        try:
            from models.quotation import convert_quotation_to_cart
            cart_items = convert_quotation_to_cart(self.current_quotation)

            conversion_data = {
                "cart_items":     cart_items,
                "customer":       self.current_quotation.customer,
                "quotation_name": self.current_quotation.name,
                "quotation_ref":  self.current_quotation.reference_number,
                "grand_total":    self.current_quotation.grand_total,
            }

            self.quotation_converted.emit(conversion_data)
            self.status_label_bottom.setText(
                f"Loaded: {self.current_quotation.name} — {len(cart_items)} line(s)"
            )

            # Removed confirmation dialog
            self.accept()

        except Exception as e:
            self.status_label_bottom.setText(f"Error: {str(e)[:60]}")
            QMessageBox.critical(self, "Load Error", f"Failed to load quotation:\n{e}")
            traceback.print_exc()

    # ─────────────────────────────────────────────────────────────────
    # Pharmacy label preview
    # ─────────────────────────────────────────────────────────────────

    def _preview_pharmacy_labels(self):
        """Open a print preview of pharmacy labels for the selected quotation."""
        if not self.current_quotation:
            return
        qid = getattr(self.current_quotation, "local_id", None)
        if not qid:
            QMessageBox.warning(
                self, "Preview Label",
                "Cannot preview labels — quotation is not saved locally yet."
            )
            return
        try:
            from services.pharmacy_label_print import preview_labels_for_quotation
            preview_labels_for_quotation(self, int(qid))
        except Exception as e:
            traceback.print_exc()
            QMessageBox.warning(
                self, "Preview Label",
                f"Failed to open label preview:\n{e}"
            )

    # ─────────────────────────────────────────────────────────────────
    # Delete
    # ─────────────────────────────────────────────────────────────────

    def _delete_quotation(self):
        if not self.current_quotation:
            return

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete quotation {self.current_quotation.name}?\n\n"
            f"Customer : {self.current_quotation.customer}\n"
            f"Total    : ${self.current_quotation.grand_total:,.2f}\n\n"
            "This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        try:
            from models.quotation import delete_quotation
            if delete_quotation(self.current_quotation.local_id):
                self.status_label_bottom.setText(f"Deleted: {self.current_quotation.name}")
                self._load_quotations()
                self.current_quotation = None
                self.convert_btn.setEnabled(False)
                self.delete_btn.setEnabled(False)
                self.label_preview_btn.setEnabled(False)
                # Reset detail panel
                for lbl in (self.customer_name_label, self.quotation_ref_label,
                            self.company_label, self.transaction_date_label,
                            self.valid_till_label):
                    lbl.setText("—")
                self.items_count_label.setText("—")
                self.grand_total_label.setText("—")
                self.items_table.setRowCount(0)
                self.status_badge.setText("—")
                self.status_badge.setStyleSheet("""
                    QLabel { background: #e2e8f0; color: #64748b;
                             border-radius: 12px; padding: 2px 14px;
                             font-weight: 700; font-size: 11px; }
                """)
                QMessageBox.information(self, "Deleted", "Quotation deleted successfully.")
            else:
                QMessageBox.warning(self, "Error", "Failed to delete quotation.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to delete:\n{e}")
            traceback.print_exc()

    # ─────────────────────────────────────────────────────────────────
    # External site
    # ─────────────────────────────────────────────────────────────────

    # Commented out external settings method
    # def _open_external_settings(self):
    #     from views.dialogs.external_quotation_settings_dialog import ExternalQuotationSettingsDialog
    #     dlg = ExternalQuotationSettingsDialog(self)
    #     dlg.exec()

    def _reprint_labels(self):
        """Reprint all pharmacy ZPL labels for the selected quotation, inline."""
        if not self.current_quotation:
            return
        qid = getattr(self.current_quotation, "local_id", None)
        if not qid:
            QMessageBox.warning(
                self, "Reprint Labels",
                "Cannot reprint — quotation is not saved locally yet."
            )
            return
        try:
            from services.pharmacy_label_zpl_printer import (
                _get_pharmacy_items_from_quotation,
                _get_pharmacy_printer_name,
                _build_zpl_label,
                _send_to_printer,
            )
        except Exception as e:
            QMessageBox.critical(self, "Reprint Labels", f"Could not load printer service:\n{e}")
            return

        printer_name = _get_pharmacy_printer_name()
        if not printer_name or printer_name == "(None)":
            QMessageBox.warning(
                self, "No Printer Configured",
                "No pharmacy label printer is set.\n"
                "Go to Settings \u2192 Hardware Settings and select a ZPL printer."
            )
            return

        try:
            labels = _get_pharmacy_items_from_quotation(int(qid))
        except Exception as e:
            QMessageBox.critical(self, "Reprint Labels", f"Failed to load pharmacy items:\n{e}")
            return

        if not labels:
            QMessageBox.information(
                self, "Reprint Labels",
                "No pharmacy items found on this quotation."
            )
            return

        printed = 0
        failed  = 0
        for lbl in labels:
            expiry = lbl.get("expiry_date")
            zpl = _build_zpl_label(
                product_name    = lbl.get("product_name", ""),
                part_no         = lbl.get("part_no", ""),
                qty             = lbl.get("qty", 0),
                uom             = lbl.get("uom", ""),
                price           = lbl.get("price", 0),
                batch_no        = lbl.get("batch_no", ""),
                expiry_date     = expiry,
                dosage          = lbl.get("dosage", ""),
                doctor_name     = lbl.get("doctor_name", ""),
                pharmacist_name = lbl.get("pharmacist_name", ""),
            )
            if _send_to_printer(zpl):
                printed += 1
            else:
                failed += 1

        if failed == 0:
            self.status_label_bottom.setText(
                f"\u2713  Reprinted {printed} label(s) \u2192 '{printer_name}'"
            )
        else:
            self.status_label_bottom.setText(
                f"Sent {printed}, failed {failed} \u2014 check printer connection."
            )
            QMessageBox.warning(
                self, "Reprint Labels",
                f"Sent {printed} label(s), but {failed} failed.\n"
                "Check the printer connection."
            )

    def _fetch_external_quotations(self):
        if getattr(self, "_ext_fetch_running", False):
            self.status_label_bottom.setText("Already fetching — please wait...")
            return
        self._ext_fetch_running = True

        self.fetch_external_btn.setEnabled(False)
        self.fetch_external_btn.setText("Fetching...")
        self.sync_progress.setVisible(True)
        self.sync_progress.setRange(0, 0)
        self.status_label_bottom.setText("Connecting to external site... (check console for progress)")
        QApplication.processEvents()

        print("[QuotationDialog] Starting external fetch thread...")

        class _FetchWorker(QObject):
            finished = Signal()

            def run(self):
                print("[FetchWorker] Thread started — calling pull_all_external_quotations()")
                try:
                    from services.external_quotation_service import pull_all_external_quotations
                    self.result = pull_all_external_quotations()
                    print(f"[FetchWorker] Done — result: {self.result}")
                except Exception as e:
                    print(f"[FetchWorker] UNCAUGHT EXCEPTION: {e}")
                    traceback.print_exc()
                    self.result = {
                        "fetched": 0, "saved": 0, "skipped": 0,
                        "errors": 1, "pages": 0,
                        "error": f"{type(e).__name__}: {e}"
                    }
                finally:
                    self.finished.emit()

        self._ext_worker        = _FetchWorker()
        self._ext_worker.result = {}
        self._ext_thread        = QThread(self)
        self._ext_worker.moveToThread(self._ext_thread)
        self._ext_thread.started.connect(self._ext_worker.run)
        self._ext_worker.finished.connect(self._ext_thread.quit)
        self._ext_worker.finished.connect(self._on_external_fetch_done)
        self._ext_thread.start()

    def _on_external_fetch_done(self):
        self._ext_fetch_running = False
        self.fetch_external_btn.setEnabled(True)
        self.fetch_external_btn.setText("Fetch External")
        self.sync_progress.setVisible(False)

        stats = getattr(self._ext_worker, "result", {})
        error = stats.get("error")

        if error:
            self.status_label_bottom.setText(f"External fetch failed: {error[:80]}")
            QMessageBox.warning(
                self, "External Fetch Failed",
                f"Could not fetch from external site:\n\n{error}\n\n"
                "Check:\n"
                "  - URL is correct (include https://)\n"
                "  - API Key and Secret are valid\n"
                "  - User has Quotation read permission\n"
                "  - Console output for detailed debug info"
            )
        else:
            self.status_label_bottom.setText(
                f"External fetch done — "
                f"Saved: {stats.get('saved', 0)}  |  "
                f"Skipped: {stats.get('skipped', 0)}  |  "
                f"Errors: {stats.get('errors', 0)}"
            )
            QMessageBox.information(
                self, "External Fetch Complete",
                f"Quotations pulled from external site:\n\n"
                f"  Newly saved        : {stats.get('saved', 0)}\n"
                f"  Already existed    : {stats.get('skipped', 0)}\n"
                f"  Errors             : {stats.get('errors', 0)}\n"
                f"  Pages fetched      : {stats.get('pages', 0)}"
            )
            self._load_quotations()

        self._ext_thread.wait(3000)

    # ─────────────────────────────────────────────────────────────────
    # Keyboard
    # ─────────────────────────────────────────────────────────────────

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.accept()
        elif event.key() == Qt.Key_F5:
            self._load_quotations()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if self.current_quotation and self.current_quotation.can_convert_to_sale():
                self._convert_to_sale()
        else:
            super().keyPressEvent(event)


def show_quotation_dialog(parent=None):
    dialog = QuotationDialog(parent)
    return dialog.exec()