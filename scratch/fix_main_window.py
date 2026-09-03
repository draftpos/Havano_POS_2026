import re
import sys

try:
    text = open('views/main_window.py', encoding='utf-8').read()

    # Find the set_headers part
    old1 = """self.stock_report.set_headers([
            "Part No.", "Product Name", "Category",
            "Qty on Hand", "Cost Price", "Sale Price",
            "Value @ Cost", "Value @ Sale", "Potential Profit"
        ])"""
        
    new1 = """self.stock_report.set_headers([
            "", "Part No.", "Product Name", "Category",
            "Qty on Hand", "Cost Price", "Sale Price",
            "Value @ Cost", "Value @ Sale", "Potential Profit"
        ])
        
        self.stock_report.table.setColumnHidden(0, True)"""

    text = text.replace(old1, new1)

    # Find the hh.setSectionResizeMode part
    old1b = """hh.setSectionResizeMode(1, QHeaderView.Stretch)"""
    new1b = """hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)"""
    text = text.replace(old1b, new1b)

    # Find the vals array
    old2 = """vals = [
                p.get("part_no", ""),
                p.get("name", ""),
                p.get("category", ""),
                f"{qty:.2f}",
                f"${cost:.2f}",
                f"${sell:.2f}",
                f"${val_cost:.2f}",
                f"${val_sell:.2f}",
                f"${(val_sell - val_cost):.2f}"
            ]"""
            
    new2 = """vals = [
                "",
                p.get("part_no", ""),
                p.get("name", ""),
                p.get("category", ""),
                f"{qty:.2f}",
                f"${cost:.2f}",
                f"${sell:.2f}",
                f"${val_cost:.2f}",
                f"${val_sell:.2f}",
                f"${(val_sell - val_cost):.2f}"
            ]"""
            
    text = text.replace(old2, new2)
    
    # Fix the alignments array
    old3 = """alignments = [
                Qt.AlignCenter,
                Qt.AlignCenter,
                Qt.AlignCenter,
                Qt.AlignCenter,
                Qt.AlignRight | Qt.AlignVCenter,
                Qt.AlignRight | Qt.AlignVCenter,
                Qt.AlignRight | Qt.AlignVCenter,
                Qt.AlignRight | Qt.AlignVCenter,
                Qt.AlignRight | Qt.AlignVCenter,
            ]"""
            
    new3 = """alignments = [
                Qt.AlignCenter,
                Qt.AlignCenter,
                Qt.AlignCenter,
                Qt.AlignCenter,
                Qt.AlignCenter,
                Qt.AlignRight | Qt.AlignVCenter,
                Qt.AlignRight | Qt.AlignVCenter,
                Qt.AlignRight | Qt.AlignVCenter,
                Qt.AlignRight | Qt.AlignVCenter,
                Qt.AlignRight | Qt.AlignVCenter,
            ]"""
    
    text = text.replace(old3, new3)

    # Find cellWidget initialization to avoid index out of bounds
    old4 = """if ci == 0:
                    it.setData(Qt.UserRole, p)
                if ci == 3 and qty <= 5:
                    it.setForeground(QColor(DANGER))
                if ci == 6:
                    it.setForeground(QColor(NAVY))
                if ci == 7:
                    it.setForeground(QColor(ACCENT))"""
                    
    new4 = """if ci == 0: continue
                if ci == 1:
                    it.setData(Qt.UserRole, p)
                if ci == 4 and qty <= 5:
                    it.setForeground(QColor(DANGER))
                if ci == 7:
                    it.setForeground(QColor(NAVY))
                if ci == 8:
                    it.setForeground(QColor(ACCENT))"""
    
    text = text.replace(old4, new4)

    open('views/main_window.py', 'w', encoding='utf-8').write(text)
    print("SUCCESS")
except Exception as e:
    print("ERROR:", e)
