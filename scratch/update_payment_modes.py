import os
import re

path = r'c:\Users\DELL\New_POS\Havano_POS_2026\views\dialogs\payment_modes_dialog.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

target_start = '    def _build(self):'
target_end = '    # ── Data ──'

start_idx = content.find(target_start)
end_idx = content.find(target_end)

new_build = '''    def _build(self):
        from views.reports.report_template import ReportTemplate
        import qtawesome as qta
        
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        
        self.report = ReportTemplate("Payment Modes", is_report=False, show_date_filter=False, parent=self)
        self.report.set_headers([h for h, _k, _w in _COLUMNS])
        
        self._tbl = self.report.table
        self._tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tbl.setSelectionMode(QAbstractItemView.SingleSelection)
        self._tbl.itemSelectionChanged.connect(self._on_selection_changed)
        
        hh = self._tbl.horizontalHeader()
        for idx, (_h, _k, w) in enumerate(_COLUMNS):
            hh.setSectionResizeMode(idx, QHeaderView.Interactive)
            self._tbl.setColumnWidth(idx, w)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        
        self._add_btn = self.report.btn_add
        self._add_btn.clicked.connect(self._on_add)
        
        self._sync_btn = QPushButton(" Sync Frappe")
        self._sync_btn.setIcon(qta.icon("fa5s.sync", color="white"))
        self._sync_btn.setStyleSheet(f"background:{ACCENT}; color:{WHITE}; padding:8px 15px; border-radius:4px; font-weight:bold;")
        self._sync_btn.clicked.connect(self._on_sync_frappe)
        
        self._del_btn = QPushButton(" Delete")
        self._del_btn.setIcon(qta.icon("fa5s.trash", color="white"))
        self._del_btn.setStyleSheet(f"background:{DANGER}; color:{WHITE}; padding:8px 15px; border-radius:4px; font-weight:bold;")
        self._del_btn.setEnabled(False)
        self._del_btn.clicked.connect(self._on_delete)
        
        self._rates_btn = QPushButton(" Rates")
        self._rates_btn.setIcon(qta.icon("fa5s.coins", color="white"))
        self._rates_btn.setStyleSheet(f"background:{ACCENT}; color:{WHITE}; padding:8px 15px; border-radius:4px; font-weight:bold;")
        self._rates_btn.clicked.connect(self._on_exchange_rates)
        
        self._toggle_btn = QPushButton(" Disable")
        self._toggle_btn.setIcon(qta.icon("fa5s.ban", color="white"))
        self._toggle_btn.setStyleSheet(f"background:{AMBER}; color:{WHITE}; padding:8px 15px; border-radius:4px; font-weight:bold;")
        self._toggle_btn.setEnabled(False)
        self._toggle_btn.clicked.connect(self._on_toggle)
        
        self._up_btn = QPushButton(" UP")
        self._up_btn.setStyleSheet(f"background:{ACCENT}; color:{WHITE}; padding:8px 15px; border-radius:4px; font-weight:bold;")
        self._up_btn.setEnabled(False)
        self._up_btn.clicked.connect(lambda: self._move(-1))
        
        self._down_btn = QPushButton(" DOWN")
        self._down_btn.setStyleSheet(f"background:{ACCENT}; color:{WHITE}; padding:8px 15px; border-radius:4px; font-weight:bold;")
        self._down_btn.setEnabled(False)
        self._down_btn.clicked.connect(lambda: self._move(+1))
        
        self._save_btn = QPushButton(" Save")
        self._save_btn.setIcon(qta.icon("fa5s.save", color="white"))
        self._save_btn.setStyleSheet(f"background:{SUCCESS}; color:{WHITE}; padding:8px 15px; border-radius:4px; font-weight:bold;")
        self._save_btn.clicked.connect(self._on_save)
        
        self.report.filters_layout.addWidget(self._sync_btn)
        self.report.filters_layout.addWidget(self._rates_btn)
        self.report.filters_layout.addWidget(self._up_btn)
        self.report.filters_layout.addWidget(self._down_btn)
        self.report.filters_layout.addWidget(self._toggle_btn)
        self.report.filters_layout.addWidget(self._del_btn)
        self.report.filters_layout.addWidget(self._save_btn)
        
        root.addWidget(self.report)
        
        self._status_lbl = QLabel("")
        root.addWidget(self._status_lbl)

'''

if start_idx != -1 and end_idx != -1:
    new_content = content[:start_idx] + new_build + content[end_idx:]
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Done")
