import os
import re

for root, dirs, files in os.walk('views'):
    for file in files:
        if file.endswith('.py'):
            path = os.path.join(root, file)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    text = f.read()
            except Exception:
                continue
            
            orig_text = text
            
            # Find the printer.setPageOrientation line
            # It could be QPageLayout.Landscape or Portrait
            pattern = r'(printer\.setPageOrientation\(QPageLayout\.(?:Landscape|Portrait)\))'
            
            replacement = r'\1\n        from PySide6.QtCore import QMarginsF\n        printer.setPageMargins(QMarginsF(12, 12, 12, 12), QPageLayout.Millimeter)'
            
            # For views/dialogs/pos_reports.py and others that might have different indentation:
            def replacer(match):
                indent = match.group(0).split('printer')[0]
                return match.group(1) + f"\n{indent}from PySide6.QtCore import QMarginsF\n{indent}printer.setPageMargins(QMarginsF(10, 10, 10, 10), QPageLayout.Millimeter)"
            
            # Since my pattern regex only matches the line without indent, I need to match the whole line:
            pattern = r'([ \t]+)(printer\.setPageOrientation\(QPageLayout\.(?:Landscape|Portrait)\))'
            
            def replacer2(match):
                indent = match.group(1)
                call = match.group(2)
                return f"{indent}{call}\n{indent}from PySide6.QtCore import QMarginsF\n{indent}printer.setPageMargins(QMarginsF(10, 10, 10, 10), QPageLayout.Millimeter)"
                
            if 'QMarginsF' not in text and 'printer.setPageOrientation' in text:
                text = re.sub(pattern, replacer2, text)
            
            # Let's also check if there is an explicit <div style="margin-bottom: 20px;"> we can reduce
            text = text.replace('margin-bottom: 20px;', 'margin-bottom: 10px;')
            text = text.replace('margin: 15px 30px;', 'margin: 5px 15px;')
            text = text.replace('margin:15px 30px;', 'margin: 5px 15px;')
            
            if text != orig_text:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(text)
                print(f"Patched margins in {path}")

