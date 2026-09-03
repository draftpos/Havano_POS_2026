# -*- coding: utf-8 -*-
with open('services/printing_service.py', 'r', encoding='utf-8') as f:
    code = f.read()

old_footer = '''            painter.setFont(small_font)
            painter.drawText(self.margin, y, self.paper_width - self.margin * 2, 22,
                             Qt.AlignCenter, {kot_hdr_text})'''

new_footer = '''            painter.setFont(kot_hdr_font)
            footer_h = painter.fontMetrics().height() + 8
            painter.drawText(self.margin, y, self.paper_width - self.margin * 2, footer_h,
                             Qt.AlignCenter, banner_text)
            y += footer_h
            if getattr(receipt, "is_modified", False):
                painter.setFont(normal_font)
                mod_h = painter.fontMetrics().height() + 8
                painter.drawText(self.margin, y, self.paper_width - self.margin * 2, mod_h,
                                 Qt.AlignCenter, "*** MODIFIED ***")
                y += mod_h - 18 # adjust next y
            painter.setFont(small_font)'''

if old_footer in code:
    code = code.replace(old_footer, new_footer)
else:
    print("Could not find old_footer!")

with open('services/printing_service.py', 'w', encoding='utf-8') as f:
    f.write(code)
print('Done patching footer')
