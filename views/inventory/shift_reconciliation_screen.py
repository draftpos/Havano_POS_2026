import os
import json
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QMessageBox, QHeaderView
)
from PySide6.QtCore import Qt
from database.db import get_connection, fetchall_dicts
import qtawesome as qta
from theme import *
from views.reports.report_template import ReportTemplate

class ShiftReconciliationScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {WHITE};")
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)
        
        from views.reports.report_template import ReportTemplate
        self.report = ReportTemplate("ShiftReconciliation", is_report=False, show_date_filter=True, parent=self)
        self.report.set_headers(["ID", "Name"])
        
        self._tbl = self.report.table
        hh = self._tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        
        self.report.btn_add.clicked.connect(self._open_add_dialog)
        
        if hasattr(self, '_export_pdf'):
            self.report.btn_pdf.clicked.connect(self._export_pdf)
            
        if hasattr(self, '_export_excel'):
            self.report.btn_excel.clicked.connect(self._export_excel)
            
        if hasattr(self, '_on_search'):
            self.report.global_search.textChanged.connect(self._on_search)
            self._search_input = self.report.global_search

        main_lay.addWidget(self.report, 1)

    def _load_data(self):
        data = []
        try:
            start_dt = self.report.start_date.date().toString('yyyy-MM-dd') + ' 00:00:00'
            end_dt = self.report.end_date.date().toString('yyyy-MM-dd') + ' 23:59:59'
            sql = """
                SELECT sr.id, s.shift_number as shift_no, s.created_at, sr.created_at as recon_date,
                       sr.closing_cashier_name, sr.total_expected, sr.total_counted
                FROM shift_reconciliations sr
                JOIN shifts s ON sr.shift_id = s.id
                WHERE sr.created_at BETWEEN ? AND ?
                ORDER BY sr.id DESC
            """
            conn = get_connection(); cur = conn.cursor()
            cur.execute(sql, (start_dt, end_dt))
            rows = fetchall_dicts(cur)
            conn.close()

            for row in rows:
                expected_total = float(row['total_expected'] or 0)
                counted_total = float(row['total_counted'] or 0)
                recon_date = str(row['recon_date']).split(".")[0]
                
                data.append([
                    recon_date,
                    str(row['shift_no']),
                    str(row['closing_cashier_name'] or 'Admin'),
                    f"{expected_total:.2f}",
                    f"{counted_total:.2f}"
                ])
                
        except Exception as e:
            print(f"Error loading shift reconciliations: {e}")
            
        self.report.set_data(data)

    def _open_add_dialog(self):
        from views.dialogs.shift_reconciliation_dialog import ShiftReconciliationDialog
        dlg = ShiftReconciliationDialog(self.window())
        dlg.exec()
        if hasattr(self, "_load_data"): self._load_data()
