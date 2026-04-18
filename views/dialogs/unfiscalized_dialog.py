# views/dialogs/unfiscalized_dialog.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QAbstractItemView, QMessageBox, 
    QApplication, QTabWidget, QWidget
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
import qtawesome as qta
from database.db import get_connection, fetchall_dicts

# Colors matching system palette
NAVY = "#0d1f3c"
WHITE = "#ffffff"
OFF_WHITE = "#f5f8fc"
ACCENT = "#1a5fb4"
ACCENT_H = "#1c6dd0"
DANGER = "#b02020"
SUCCESS = "#1a7a3c"
MUTED = "#5a7a9a"
BORDER = "#c8d8ec"
ROW_ALT = "#edf3fb"


class UnfiscalizedDialog(QDialog):
    """Dialog to show and retry unfiscalized sales and Z-Report summaries"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Fiscalization Dashboard")
        self.setMinimumSize(1000, 650)
        self.setModal(True)
        self.setStyleSheet(f"QDialog {{ background: {OFF_WHITE}; }}")
        self._sales = []
        self._build()
        self._load_data()
    
    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 16, 20, 16)
        
        # Header
        hdr = QWidget()
        hdr.setFixedHeight(44)
        hdr.setStyleSheet(f"background-color: {NAVY}; border-radius: 5px;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(16, 0, 16, 0)
        title = QLabel("Unfiscalized Items Dashboard (Z)")
        title.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {WHITE}; background: transparent;")
        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet(f"color: #8fa8c8; font-size: 11px; background: transparent;")
        hl.addWidget(title)
        hl.addStretch()
        hl.addWidget(self._count_lbl)
        layout.addWidget(hdr)
        
        # Tabs
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: 1px solid {BORDER}; background: {WHITE}; }}
            QTabBar::tab {{
                background: {OFF_WHITE}; color: {NAVY};
                padding: 10px 24px; font-size: 12px; font-weight: bold;
                border: 1px solid {BORDER}; border-bottom: none;
                margin-right: 2px; border-radius: 5px 5px 0 0;
            }}
            QTabBar::tab:selected {{ background: {WHITE}; color: {ACCENT}; border-top: 3px solid {ACCENT}; }}
            QTabBar::tab:hover {{ background: {ROW_ALT}; }}
        """)
        
        # Tab 1: Sales List
        self._sales_tab = self._build_sales_tab()
        self._tabs.addTab(self._sales_tab, qta.icon("fa5s.clipboard"), "Pending Invoices")
        
        # Tab 2: Aggregated Summary (The "Z" Details)
        self._summary_tab = self._build_summary_tab()
        self._tabs.addTab(self._summary_tab, qta.icon("fa5s.chart-line"), "Fiscal Day Summary (Z)")
        
        layout.addWidget(self._tabs, 1)
        
        # Bottom Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        self._retry_btn = QPushButton("Retry Selected")
        self._retry_btn.setIcon(qta.icon("fa5s.sync-alt"))
        self._retry_btn.setFixedHeight(36)
        self._retry_btn.setCursor(Qt.PointingHandCursor)
        self._retry_btn.setEnabled(False)
        self._retry_btn.setStyleSheet(self._btn_ss(ACCENT, ACCENT_H))
        self._retry_btn.clicked.connect(self._retry_selected)
        
        self._retry_all_btn = QPushButton("Retry All Pending")
        self._retry_all_btn.setIcon(qta.icon("fa5s.sync-alt"))
        self._retry_all_btn.setFixedHeight(36)
        self._retry_all_btn.setCursor(Qt.PointingHandCursor)
        self._retry_all_btn.setStyleSheet(self._btn_ss(SUCCESS, "#1f9447"))
        self._retry_all_btn.clicked.connect(self._retry_all)
        
        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(36)
        close_btn.setFixedWidth(100)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(self._btn_ss(NAVY, "#162d52"))
        close_btn.clicked.connect(self.accept)
        
        btn_layout.addWidget(self._retry_btn)
        btn_layout.addWidget(self._retry_all_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _btn_ss(self, bg, hover):
        return f"""
            QPushButton {{
                background-color: {bg}; color: {WHITE}; border: none;
                border-radius: 5px; font-size: 12px; font-weight: bold; padding: 0 16px;
            }}
            QPushButton:hover {{ background-color: {hover}; }}
            QPushButton:disabled {{ background-color: {MUTED}; }}
        """

    def _build_sales_tab(self) -> QWidget:
        w = QWidget(); l = QVBoxLayout(w)
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["Sale ID", "Invoice No", "Customer", "Total", "Status"])
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed); self._table.setColumnWidth(0, 80)
        hh.setSectionResizeMode(1, QHeaderView.Fixed); self._table.setColumnWidth(1, 180)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.Fixed); self._table.setColumnWidth(3, 120)
        hh.setSectionResizeMode(4, QHeaderView.Fixed); self._table.setColumnWidth(4, 120)
        
        self._style_table(self._table)
        self._table.cellClicked.connect(self._on_selection_changed)
        l.addWidget(self._table)
        return w

    def _build_summary_tab(self) -> QWidget:
        """New tab requested by user showing Net/Tax/Gross breakdown for Z-report"""
        w = QWidget(); l = QVBoxLayout(w)
        
        info = QLabel("Below is the aggregated breakdown for all invoices currently pending fiscalization.")
        info.setStyleSheet(f"color: {MUTED}; font-size: 12px; margin-bottom: 5px;")
        l.addWidget(info)
        
        self._sum_table = QTableWidget(0, 4)
        self._sum_table.setHorizontalHeaderLabels(["Tax Category", "Net Amount", "VAT Amount", "Gross Total"])
        hh = self._sum_table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Stretch)
        
        self._style_table(self._sum_table)
        l.addWidget(self._sum_table)
        
        return w

    def _style_table(self, tbl):
        tbl.verticalHeader().setVisible(False)
        tbl.setAlternatingRowColors(True)
        tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        tbl.setSelectionMode(QAbstractItemView.SingleSelection)
        tbl.setStyleSheet(f"""
            QTableWidget {{
                background: {WHITE}; border: none;
                gridline-color: {BORDER}; outline: none;
            }}
            QTableWidget::item {{ padding: 12px; }}
            QTableWidget::item:selected {{ background-color: {ACCENT}; color: {WHITE}; }}
            QHeaderView::section {{
                background-color: {NAVY}; color: {WHITE};
                padding: 10px; border: none;
                font-size: 11px; font-weight: bold;
            }}
        """)

    def _load_data(self):
        # 1. Load Sales List
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, invoice_no, customer_name, total, fiscal_status, fiscal_error
            FROM sales 
            WHERE fiscal_status IN ('pending', 'failed')
            ORDER BY id DESC
        """)
        rows = fetchall_dicts(cursor)
        conn.close()
        
        self._sales = rows
        self._table.setRowCount(0)
        for sale in rows:
            r = self._table.rowCount()
            self._table.insertRow(r)
            status = sale.get("fiscal_status", "unknown")
            status_color = DANGER if status == "failed" else "#e67e22"
            
            self._table.setItem(r, 0, QTableWidgetItem(str(sale.get("id", ""))))
            self._table.setItem(r, 1, QTableWidgetItem(sale.get("invoice_no", "")))
            self._table.setItem(r, 2, QTableWidgetItem(sale.get("customer_name") or "Walk-in"))
            
            total_val = float(sale.get('total', 0) or 0)
            total_item = QTableWidgetItem(f"${total_val:,.2f}")
            total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._table.setItem(r, 3, total_item)
            
            status_item = QTableWidgetItem(status.upper())
            status_item.setForeground(QColor(status_color))
            status_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(r, 4, status_item)
            
            if sale.get("fiscal_error"):
                self._table.item(r, 4).setToolTip(f"Error: {sale.get('fiscal_error')}")
        
        self._count_lbl.setText(f"{len(rows)} item(s) pending")
        
        # 2. Load Z-Report Summary Details
        from services.fiscalization_service import get_fiscalization_service
        service = get_fiscalization_service()
        z_details = service.get_pending_z_details()
        
        self._sum_table.setRowCount(0)
        grand_net = grand_vat = grand_gross = 0.0
        
        for item in z_details:
            r = self._sum_table.rowCount()
            self._sum_table.insertRow(r)
            
            t_type = str(item.get("tax_type") or "VAT")
            t_rate = float(item.get("tax_rate") or 0)
            net = float(item.get("total_net") or 0)
            vat = float(item.get("total_vat") or 0)
            gross = float(item.get("total_gross") or 0)
            
            grand_net += net
            grand_vat += vat
            grand_gross += gross
            
            cat_name = f"{t_type} ({t_rate:g}%)"
            if t_rate <= 0: cat_name = "EXEMPT / ZERO RATED"
            
            self._sum_table.setItem(r, 0, QTableWidgetItem(cat_name))
            self._sum_table.setItem(r, 1, self._v_cell(net))
            self._sum_table.setItem(r, 2, self._v_cell(vat))
            self._sum_table.setItem(r, 3, self._v_cell(gross, bold=True))
            
        # Add Total row
        if z_details:
            r = self._sum_table.rowCount()
            self._sum_table.insertRow(r)
            self._sum_table.setItem(r, 0, QTableWidgetItem("TOTAL ALL CATEGORIES"))
            self._sum_table.setItem(r, 1, self._v_cell(grand_net, bold=True))
            self._sum_table.setItem(r, 2, self._v_cell(grand_vat, bold=True))
            self._sum_table.setItem(r, 3, self._v_cell(grand_gross, bold=True))
            self._sum_table.item(r, 0).setForeground(QColor(ACCENT))
            for c in range(4):
                self._sum_table.item(r, c).setBackground(QColor(ROW_ALT))

    def _v_cell(self, val, bold=False):
        it = QTableWidgetItem(f"${val:,.2f}")
        it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        if bold:
            font = it.font(); font.setBold(True); it.setFont(font)
        return it

    def _on_selection_changed(self, row, col):
        self._retry_btn.setEnabled(True)
    
    def _retry_selected(self):
        row = self._table.currentRow()
        if row < 0: return
        sale_id = int(self._table.item(row, 0).text())
        sale_inv = self._table.item(row, 1).text()
        
        reply = QMessageBox.question(self, "Retry Fiscalization",
            f"Retry invoice {sale_inv}?", QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self._retry_sale(sale_id)
    
    def _retry_all(self):
        if not self._sales: return
        reply = QMessageBox.question(self, "Retry All",
            f"Retry fiscalization for all {len(self._sales)} items?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            for sale in self._sales:
                self._retry_sale(sale.get("id"))
    
    def _retry_sale(self, sale_id: int):
        try:
            from services.fiscalization_service import get_fiscalization_service
            service = get_fiscalization_service()
            service.retry_fiscalization(sale_id)
        except Exception as e:
            print(f"Error retrying sale {sale_id}: {e}")
        
        QTimer.singleShot(1500, self._load_data)