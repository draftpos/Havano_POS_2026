import os
import re

path = 'views/main_window.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

old_loop = r'''            for ci, \(val, aln\) in enumerate\(zip\(vals, alignments\)\):
                it = QTableWidgetItem\(val\)
                it\.setTextAlignment\(aln\)
                if ci == 0:
                    it\.setData\(Qt\.UserRole, p\)
                if ci == 3 and qty <= 5:
                    it\.setForeground\(QColor\(DANGER\)\)
                if ci == 6:
                    it\.setForeground\(QColor\(NAVY\)\)
                if ci == 7:
                    it\.setForeground\(QColor\(ACCENT\)\)
                self\.stock_report\.table\.setItem\(r, ci, it\)'''

new_loop = """            for ci, (val, aln) in enumerate(zip(vals, alignments)):
                it = QTableWidgetItem(val)
                it.setTextAlignment(aln)
                if ci >= 10:
                    val_str = str(val).strip()
                    it.setText(val_str if val_str else "N/A")
                if ci == 0:
                    it.setData(Qt.UserRole, p)
                if ci == 3 and qty <= 5:
                    it.setForeground(QColor(DANGER))
                if ci == 6:
                    it.setForeground(QColor(NAVY))
                if ci == 7:
                    it.setForeground(QColor(ACCENT))
                self.stock_report.table.setItem(r, ci, it)"""

if re.search(old_loop, text):
    text = re.sub(old_loop, new_loop, text)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    print("Replaced loop in main_window.py")
else:
    print("Could not find loop to replace")
