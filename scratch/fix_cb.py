import re
text = open('views/main_window.py', encoding='utf-8').read()
text = text.replace('cb = self.stock_report.table.cellWidget(r, 0)\n                    if cb: cb.setChecked(False)', 'container = self.stock_report.table.cellWidget(r, 0)\n                    if container:\n                        cb = container.findChild(QCheckBox)\n                        if cb: cb.setChecked(False)')
text = text.replace('cb = self.stock_report.table.cellWidget(r, 0)\n                    if cb and cb.isChecked():', 'container = self.stock_report.table.cellWidget(r, 0)\n                    if container:\n                        cb = container.findChild(QCheckBox)\n                        if cb and cb.isChecked():')
text = text.replace('cb = QCheckBox()\n            cb.setStyleSheet("margin-left: 10px;")\n            self.stock_report.table.setCellWidget(r, 0, cb)', 'container = QWidget()\n            l = QHBoxLayout(container)\n            l.setContentsMargins(10, 0, 0, 0)\n            cb = QCheckBox()\n            l.addWidget(cb)\n            self.stock_report.table.setCellWidget(r, 0, container)')
open('views/main_window.py', 'w', encoding='utf-8').write(text)
