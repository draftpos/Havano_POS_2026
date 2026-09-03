# -*- coding: utf-8 -*-
with open('services/printing_service.py', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Add MODIFIED text under the KOT banner
old_banner = '''            painter.drawText(self.margin, y, self.paper_width - self.margin * 2, banner_h,
                             Qt.AlignCenter, banner_text)
            y += banner_h + 8
            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)'''

new_banner = '''            painter.drawText(self.margin, y, self.paper_width - self.margin * 2, banner_h,
                             Qt.AlignCenter, banner_text)
            y += banner_h + 4
            
            if getattr(receipt, "is_modified", False):
                painter.setFont(normal_font)
                mod_h = painter.fontMetrics().height() + 8
                painter.drawText(self.margin, y, self.paper_width - self.margin * 2, mod_h,
                                 Qt.AlignCenter, "*** MODIFIED ***")
                y += mod_h + 4
                painter.setFont(kot_hdr_font) # restore
                
            y += 4
            painter.drawLine(self.margin, y, self.paper_width - self.margin, y)'''

if old_banner in code:
    code = code.replace(old_banner, new_banner)

# 2. Update item loop to add strikeout and old_qty
old_item_loop = '''            for item in receipt.items:
                name  = (getattr(item, "productName", "") or "").strip() or "(item)"
                qty   = float(getattr(item, "qty", 1) or 1)
                notes = (getattr(item, "item_notes", "") or "").strip()

                # Item name — word-wrap if long
                name_rect = fm.boundingRect(0, 0, QTY_X - self.margin - 6, 1000,
                                            Qt.TextWordWrap, name)
                painter.drawText(self.margin, y, QTY_X - self.margin - 6,
                                 name_rect.height(), Qt.TextWordWrap, name)

                qty_str = str(int(qty)) if qty == int(qty) else f"{qty:.2f}"
                painter.drawText(QTY_X, y, max_qty_w, line_h, Qt.AlignRight, qty_str)
                y += max(name_rect.height(), line_h) + 4'''

new_item_loop = '''            for item in receipt.items:
                name  = (getattr(item, "productName", "") or "").strip() or "(item)"
                qty   = float(getattr(item, "qty", 1) or 1)
                notes = (getattr(item, "item_notes", "") or "").strip()
                is_cancelled = getattr(item, "is_cancelled", False)
                old_qty = getattr(item, "old_qty", 0.0)

                qty_str = str(int(qty)) if qty == int(qty) else f"{qty:.2f}"
                if old_qty > 0 and old_qty != qty:
                    old_str = str(int(old_qty)) if old_qty == int(old_qty) else f"{old_qty:.2f}"
                    qty_str = f"{old_str} -> {qty_str}"

                # Handle strikeout for cancelled items
                if is_cancelled:
                    strike_font = painter.font()
                    strike_font.setStrikeOut(True)
                    painter.setFont(strike_font)

                # Item name — word-wrap if long
                name_rect = fm.boundingRect(0, 0, QTY_X - self.margin - 6, 1000,
                                            Qt.TextWordWrap, name)
                painter.drawText(self.margin, y, QTY_X - self.margin - 6,
                                 name_rect.height(), Qt.TextWordWrap, name)

                painter.drawText(QTY_X, y, max_qty_w, line_h, Qt.AlignRight, qty_str)
                
                if is_cancelled:
                    painter.setFont(normal_font) # restore

                y += max(name_rect.height(), line_h) + 4'''

if old_item_loop in code:
    code = code.replace(old_item_loop, new_item_loop)

with open('services/printing_service.py', 'w', encoding='utf-8') as f:
    f.write(code)
print('Done patching printing_service.py items')
