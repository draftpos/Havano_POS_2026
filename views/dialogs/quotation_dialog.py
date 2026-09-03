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
except Exception:  # pragma: no cover - icons are optional decoration
    qta = None


class OdooInvoiceFetchWorker(QObject):
    finished = Signal()
    
    def run(self):
        try:
            from services.credentials import get_system_mode
            if get_system_mode() == "odoo":
                from database.db import get_connection
                conn = get_connection(); cur = conn.cursor()
                cur.execute("SELECT setting_value FROM pos_settings WHERE setting_key = 'fetch_invoices_as_quotations'")
                row = cur.fetchone()
                conn.close()
                if row and str(row[0]).strip() == "1":
                    from services.quotation_sync_service import sync_invoices_as_quotations_from_odoo
                    sync_invoices_as_quotations_from_odoo()
        except Exception as e:
            print(f"[OdooFetch] Worker error: {e}")
        finally:
            self.finished.emit()

class QuotationDialog(QDialog):

    quotation_converted = Signal(dict)

    def __init__(self, parent=None, user=None):
        super().__init__(parent)
        self.user = user

        try:
            from utils.roles import is_pharmacist
            self._is_pharm = is_pharmacist(self.user)
        except Exception:
            self._is_pharm = False

        self.current_quotation = None
        self.quotations = []
        self.all_quotations = []

        self._lbl_quotation = "Order" if self._is_pharm else "Quotation"
        self._lbl_quotations = "Orders" if self._is_pharm else "Quotations"
        self._lbl_quotation_upper = "ORDER" if self._is_pharm else "QUOTATION"

        self.setWindowTitle(self._lbl_quotations)
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

        title = QLabel(self._lbl_quotations)
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #1e40af; letter-spacing: -0.3px;")
        header_row.addWidget(title)
        header_row.addStretch()

        # Buttons on the right of the header
        # self.fetch_external_btn = QPushButton("Fetch External")
        # self.fetch_external_btn.setObjectName("warningBtn")
        # self.fetch_external_btn.setToolTip(f"Pull {self._lbl_quotations.lower()} from the configured external site")
        # self.fetch_external_btn.clicked.connect(self._fetch_external_quotations)
        # header_row.addWidget(self.fetch_external_btn)

        # Commented out external settings button
        # self.ext_settings_btn = QPushButton("External Site Settings")
        # self.ext_settings_btn.setObjectName("secondaryBtn")
        # self.ext_settings_btn.setToolTip("Configure URL / API key for external site")
        # self.ext_settings_btn.clicked.connect(self._open_external_settings)
        # header_row.addWidget(self.ext_settings_btn)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setObjectName("primaryBtn")
        self.refresh_btn.clicked.connect(self._start_odoo_fetch)
        header_row.addWidget(self.refresh_btn)

        # Back to POS - lets the user close the Quotations view and return to
        # the cart (important for pharmacists who auto-land here on login).
        self.back_to_pos_btn = QPushButton("Home")
        self.back_to_pos_btn.setObjectName("secondaryBtn")
        self.back_to_pos_btn.setToolTip(f"Close {self._lbl_quotations} and return to Home")
        if qta is not None:
            try:
                self.back_to_pos_btn.setIcon(qta.icon("fa5s.home", color="white"))
            except Exception:
                pass
        self.back_to_pos_btn.clicked.connect(self.reject)
        header_row.addWidget(self.back_to_pos_btn)

        main_layout.addLayout(header_row)

        # ── Main splitter ─────────────────────────────────────────────
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(2)

        # Left - quotations list
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        from views.reports.report_template import ReportTemplate
        self.report = ReportTemplate(self._lbl_quotations, is_report=True, parent=self)
        self.report.set_headers([
            self._lbl_quotation, "Date", "Customer", "Status", "Total"
        ])
        self.report.title_label.hide()
        self.report.table.itemSelectionChanged.connect(self._on_quotation_selected)
        self.report.table.doubleClicked.connect(self._on_double_click)
        self.report.btn_apply.clicked.connect(self._load_quotations)

        # Add custom status filter to the template's filter layout
        status_lbl = QLabel("Status:")
        status_lbl.setStyleSheet("font-weight: 600; color: #475569; font-size: 12px; margin-left: 10px;")
        
        self.status_filter = QComboBox()
        self.status_filter.addItems(["All", "Submitted", "Draft", "Cancelled"])
        self.status_filter.setFixedWidth(130)
        self.status_filter.currentTextChanged.connect(self._apply_search)
        
        self.report.filters_layout.addWidget(status_lbl)
        self.report.filters_layout.addWidget(self.status_filter)

        left_layout.addWidget(self.report)

        # Right - details panel
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
        self.customer_name_label = QLabel("-")
        self.customer_name_label.setStyleSheet("font-size: 17px; font-weight: 700; color: #1e40af;")
        top_row.addWidget(self.customer_name_label)
        top_row.addStretch()

        self.status_badge = QLabel("-")
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
                val = QLabel("-")
                val.setStyleSheet("font-size: 13px; font-weight: 600; color: #1a1a2e;")
                col.addWidget(val)
                labels.append(val)
                col.addSpacing(6)
            return col, labels

        col1, [self.quotation_ref_label, self.company_label] = _detail_col(
            (self._lbl_quotation_upper, ""), ("COMPANY", "")
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
            v = QLabel("-")
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

        self.items_table = QTableWidget(0, 6)
        self.items_table.setHorizontalHeaderLabels(["LN", "Item Code", "Description", "Qty", "Rate", "Amount"])
        iv = self.items_table.horizontalHeader()
        iv.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        iv.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        iv.setSectionResizeMode(2, QHeaderView.Stretch)
        iv.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        iv.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        iv.setSectionResizeMode(5, QHeaderView.ResizeToContents)
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

        # Pharmacy label preview - enabled only when exactly one row is selected
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

        # Reprint - prints ZPL labels for the selected quotation inline
        self.reprint_btn = QPushButton("Reprint Label")
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

    def _apply_search(self):
        status_filter = self.status_filter.currentText()
        filtered = []
        for q in self.all_quotations:
            if status_filter != "All" and q.status != status_filter:
                continue
            filtered.append(q)

        self.quotations = filtered
        self._update_quotation_table()
        
        total = len(self.all_quotations)
        shown = len(filtered)
        lbl_lower = self._lbl_quotations.lower()
        self.status_label_bottom.setText(
            f"{shown} of {total} {lbl_lower}" if shown != total else f"{total} {lbl_lower}"
        )

    # ─────────────────────────────────────────────────────────────────
    # Load / table
    # ─────────────────────────────────────────────────────────────────

    def _start_odoo_fetch(self):
        self.refresh_btn.setEnabled(False)
        self.status_label_bottom.setText("Fetching invoices from Odoo...")
        self.sync_progress.setRange(0, 0)
        self.sync_progress.setVisible(True)
        
        self.fetch_thread = QThread()
        self.fetch_worker = OdooInvoiceFetchWorker()
        self.fetch_worker.moveToThread(self.fetch_thread)
        
        self.fetch_thread.started.connect(self.fetch_worker.run)
        self.fetch_worker.finished.connect(self.fetch_thread.quit)
        self.fetch_worker.finished.connect(self.fetch_worker.deleteLater)
        self.fetch_thread.finished.connect(self.fetch_thread.deleteLater)
        self.fetch_thread.finished.connect(self._on_fetch_finished)
        
        self.fetch_thread.start()

    def _on_fetch_finished(self):
        self.sync_progress.setVisible(False)
        self.refresh_btn.setEnabled(True)
        self._load_quotations()

    def _load_quotations(self):
        try:
            from models.quotation import get_all_quotations
            self.status_label_bottom.setText("Loading...")
            QApplication.processEvents()
            self.all_quotations = get_all_quotations()
            self._apply_search()
            self.status_label_bottom.setText(f"Loaded {len(self.all_quotations)} {self._lbl_quotations.lower()}")
        except Exception as e:
            self.status_label_bottom.setText(f"Error: {str(e)[:60]}")
            QMessageBox.warning(self, "Load Error", f"Failed to load quotations:\n{e}")
            traceback.print_exc()

    def _update_quotation_table(self):
        data = []
        for q in self.quotations:
            date_str = q.transaction_date[:10] if len(q.transaction_date) >= 10 else q.transaction_date
            data.append([
                q.name,
                date_str,
                q.customer,
                q.status,
                f"${q.grand_total:,.2f}"
            ])
            
        self.report.set_data(data)
        
        # Colorize status column
        STATUS_COLORS = {
            "Submitted": "#16a34a",
            "Draft":     "#d97706",
            "Cancelled": "#ef4444",
            "Dispensed": "#0ea5e9",
        }
        for r in range(1, self.report.table.rowCount() - 1):
            status_item = self.report.table.item(r, 3)
            if status_item:
                color = STATUS_COLORS.get(status_item.text(), "#64748b")
                status_item.setForeground(QColor(color))
                f = status_item.font()
                f.setBold(True)
                status_item.setFont(f)

    # ─────────────────────────────────────────────────────────────────
    # Selection / details
    # ─────────────────────────────────────────────────────────────────

    def _on_quotation_selected(self):
        rows = self.report.table.selectionModel().selectedRows()
        if not rows:
            self.convert_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            self.label_preview_btn.setEnabled(False)
            self.reprint_btn.setEnabled(False)
            self.current_quotation = None
            return
            
        row = rows[0].row()
        if row == 0 or row == self.report.table.rowCount() - 1:
            self.current_quotation = None
            self.convert_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            self.label_preview_btn.setEnabled(False)
            self.reprint_btn.setEnabled(False)
            return

        single_selection = len(rows) == 1
        name_item = self.report.table.item(row, 0)
        if not name_item: return
        
        q_name = name_item.text()
        self.current_quotation = next((q for q in self.quotations if q.name == q_name), None)

        if self.current_quotation:
            can_convert = self.current_quotation.can_convert_to_sale()
            self.convert_btn.setEnabled(can_convert)
            self.delete_btn.setEnabled(True)
            self.label_preview_btn.setEnabled(single_selection)
            self.reprint_btn.setEnabled(single_selection)
            self._display_quotation_details(self.current_quotation)
            self.convert_btn.setToolTip(
                "Load quotation items into cart" if can_convert
                else f"Cannot load - status is '{self.current_quotation.status}'"
            )

    def _on_double_click(self, index):
        if self.current_quotation and self.current_quotation.can_convert_to_sale():
            self._convert_to_sale()

    def _display_quotation_details(self, quotation):
        self.customer_name_label.setText(quotation.customer or "-")
        self.quotation_ref_label.setText(quotation.name or "-")
        self.company_label.setText(quotation.company or "-")

        date_str = (quotation.transaction_date[:10]
                    if len(quotation.transaction_date) >= 10
                    else quotation.transaction_date)
        self.transaction_date_label.setText(date_str)

        valid = (quotation.valid_till[:10]
                 if quotation.valid_till and len(quotation.valid_till) >= 10
                 else (quotation.valid_till or "-"))
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

        # Summary - show line count, not sum of qtys
        self.items_count_label.setText(str(len(quotation.items)))
        self.grand_total_label.setText(f"${quotation.grand_total:,.2f}")

        # Items table
        self.items_table.setRowCount(0)
        for row, item in enumerate(quotation.items):
            self.items_table.insertRow(row)
            
            ln_item = QTableWidgetItem(str(row + 1))
            ln_item.setTextAlignment(Qt.AlignCenter)
            self.items_table.setItem(row, 0, ln_item)

            self.items_table.setItem(row, 1, QTableWidgetItem(item.item_code))
            self.items_table.setItem(row, 2, QTableWidgetItem(item.description or item.item_name))

            # Qty: show as integer if whole number, else 2dp
            qty_val = item.qty
            qty_str = str(int(qty_val)) if qty_val == int(qty_val) else f"{qty_val:,.2f}"
            qty_item = QTableWidgetItem(qty_str)
            qty_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.items_table.setItem(row, 3, qty_item)

            rate_item = QTableWidgetItem(f"${item.rate:,.2f}")
            rate_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.items_table.setItem(row, 4, rate_item)

            amount_item = QTableWidgetItem(f"${item.amount:,.2f}")
            amount_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.items_table.setItem(row, 5, amount_item)

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
                f"Loaded: {self.current_quotation.name} - {len(cart_items)} line(s)"
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
                "Cannot preview labels - quotation is not saved locally yet."
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
                    lbl.setText("-")
                self.items_count_label.setText("-")
                self.grand_total_label.setText("-")
                self.items_table.setRowCount(0)
                self.status_badge.setText("-")
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
        """Reprint pharmacy ZPL labels for the selected quotation.

        Shows a selection dialog so the user can choose to reprint all labels
        or pick a single item label to reprint.
        """
        if not self.current_quotation:
            return
        qid = getattr(self.current_quotation, "local_id", None)
        if not qid:
            QMessageBox.warning(
                self, "",
                "Cannot reprint - quotation is not saved locally yet."
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
            QMessageBox.critical(self, "Reprint Label", f"Could not load printer service:\n{e}")
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
            QMessageBox.critical(self, "Reprint Label", f"Failed to load pharmacy items:\n{e}")
            return

        if not labels:
            QMessageBox.information(
                self, "",
                "No pharmacy items found on this quotation."
            )
            return

        # ── Label Selection Dialog ────────────────────────────────────────────
        sel_dlg = QDialog(self)
        sel_dlg.setWindowTitle("Select Labels to Reprint")
        sel_dlg.setMinimumWidth(420)
        sel_dlg.setWindowFlags(sel_dlg.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        sel_lay = QVBoxLayout(sel_dlg)
        sel_lay.setSpacing(10)
        sel_lay.setContentsMargins(16, 16, 16, 12)

        hdr_lbl = QLabel("Choose which label(s) to reprint:")
        hdr_lbl.setStyleSheet("font-weight:bold; font-size:13px;")
        sel_lay.addWidget(hdr_lbl)

        from PySide6.QtWidgets import QListWidget, QListWidgetItem, QAbstractItemView
        lw = QListWidget()
        lw.setSelectionMode(QAbstractItemView.SingleSelection)
        lw.setStyleSheet(
            "QListWidget { border:1px solid #c8d5e3; border-radius:4px; font-size:12px; }"
            "QListWidget::item { padding:6px 10px; }"
            "QListWidget::item:selected { background:#1a5fb4; color:#fff; }"
        )

        # First entry = "All Labels"
        all_item = QListWidgetItem("\u2605  All Labels  (%d item%s)" % (len(labels), "s" if len(labels) != 1 else ""))
        all_item.setData(Qt.UserRole, None)          # None = print all
        lw.addItem(all_item)

        for lbl in labels:
            pname  = lbl.get("product_name", "(Unknown)")
            batch  = lbl.get("batch_no", "")
            qty    = lbl.get("qty", 0)
            suffix = f"  |  Batch: {batch}" if batch else ""
            display = f"{pname}  (Qty: {qty:.4g}){suffix}"
            li = QListWidgetItem(display)
            li.setData(Qt.UserRole, lbl)
            lw.addItem(li)

        lw.setCurrentRow(0)
        sel_lay.addWidget(lw)

        btn_row = QHBoxLayout(); btn_row.setSpacing(8)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(32)
        cancel_btn.clicked.connect(sel_dlg.reject)
        print_btn = QPushButton("\u2192  Print Selected")
        print_btn.setFixedHeight(32)
        print_btn.setStyleSheet(
            "QPushButton { background:#1a5fb4; color:#fff; border:none; border-radius:4px; font-weight:bold; }"
            "QPushButton:hover { background:#1248a0; }"
        )
        print_btn.clicked.connect(sel_dlg.accept)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(print_btn)
        sel_lay.addLayout(btn_row)

        if sel_dlg.exec() != QDialog.Accepted:
            return

        selected_item = lw.currentItem()
        if not selected_item:
            return

        chosen_lbl = selected_item.data(Qt.UserRole)   # None = all, dict = single
        to_print = labels if chosen_lbl is None else [chosen_lbl]
        # ─────────────────────────────────────────────────────────────────────

        printed = 0
        failed  = 0
        for lbl in to_print:
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
                self, "Reprint Label",
                f"Sent {printed} label(s), but {failed} failed.\n"
                "Check the printer connection."
            )

    def _fetch_external_quotations(self):
        if getattr(self, "_ext_fetch_running", False):
            self.status_label_bottom.setText("Already fetching - please wait...")
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
                print("[FetchWorker] Thread started - calling pull_all_external_quotations()")
                try:
                    from services.external_quotation_service import pull_all_external_quotations
                    self.result = pull_all_external_quotations()
                    print(f"[FetchWorker] Done - result: {self.result}")
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
                f"External fetch done - "
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
            # Switch date filter to 'All' so the user actually sees the newly pulled quotations
            # (which might have older transaction dates than 'Today')
            self.date_filter.setCurrentText("All")
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