# -*- coding: utf-8 -*-
with open('services/printing_service.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Add MODIFIED below heading
old_heading = '''            # Title (KOT or Station name)
            painter.setFont(header_font)
            title_rect = painter.boundingRect(0, y, pW, 500, Qt.AlignHCenter | Qt.TextWordWrap, station)
            painter.drawText(title_rect, Qt.AlignHCenter | Qt.TextWordWrap, station)
            y += title_rect.height() + 2'''

new_heading = '''            # Title (KOT or Station name)
            painter.setFont(header_font)
            title_rect = painter.boundingRect(0, y, pW, 500, Qt.AlignHCenter | Qt.TextWordWrap, station)
            painter.drawText(title_rect, Qt.AlignHCenter | Qt.TextWordWrap, station)
            y += title_rect.height() + 2
            
            if getattr(receipt, "is_modified", False):
                painter.setFont(normal_font)
                mod_rect = painter.boundingRect(0, y, pW, 500, Qt.AlignHCenter | Qt.TextWordWrap, "*** MODIFIED ***")
                painter.drawText(mod_rect, Qt.AlignHCenter | Qt.TextWordWrap, "*** MODIFIED ***")
                y += mod_rect.height() + 2'''

if old_heading in code:
    code = code.replace(old_heading, new_heading)
else:
    print("Could not find old_heading!")

# Update item printing logic
old_item_print = '''            for it in items:
                # Format: "  <qty> x <name>"
                line_str = f"  {it.qty:g} x {it.productName}"
                i_rect = painter.boundingRect(0, y, pW, 500, Qt.AlignLeft | Qt.TextWordWrap, line_str)
                painter.drawText(i_rect, Qt.AlignLeft | Qt.TextWordWrap, line_str)
                y += i_rect.height()

                # Print item notes if present
                if getattr(it, "item_notes", ""):
                    painter.setFont(small_font)
                    note_str = f"    * {it.item_notes}"
                    n_rect = painter.boundingRect(0, y, pW, 500, Qt.AlignLeft | Qt.TextWordWrap, note_str)
                    painter.drawText(n_rect, Qt.AlignLeft | Qt.TextWordWrap, note_str)
                    y += n_rect.height() + 1
                    painter.setFont(bold_font)'''

new_item_print = '''            for it in items:
                # Format: "  <qty> x <name>"
                
                is_cancelled = getattr(it, "is_cancelled", False)
                old_qty = getattr(it, "old_qty", 0.0)
                
                if is_cancelled:
                    line_str = f"  {it.qty:g} x {it.productName}"
                elif old_qty > 0 and old_qty != it.qty:
                    line_str = f"  {old_qty:g} -> {it.qty:g} x {it.productName}"
                else:
                    line_str = f"  {it.qty:g} x {it.productName}"
                
                i_rect = painter.boundingRect(0, y, pW, 500, Qt.AlignLeft | Qt.TextWordWrap, line_str)
                
                if is_cancelled:
                    # Strikeout font
                    strike_font = painter.font()
                    strike_font.setStrikeOut(True)
                    painter.setFont(strike_font)
                    painter.drawText(i_rect, Qt.AlignLeft | Qt.TextWordWrap, line_str)
                    painter.setFont(bold_font)  # Restore
                else:
                    painter.drawText(i_rect, Qt.AlignLeft | Qt.TextWordWrap, line_str)
                    
                y += i_rect.height()

                # Print item notes if present
                if getattr(it, "item_notes", "") and not is_cancelled:
                    painter.setFont(small_font)
                    note_str = f"    * {it.item_notes}"
                    n_rect = painter.boundingRect(0, y, pW, 500, Qt.AlignLeft | Qt.TextWordWrap, note_str)
                    painter.drawText(n_rect, Qt.AlignLeft | Qt.TextWordWrap, note_str)
                    y += n_rect.height() + 1
                    painter.setFont(bold_font)'''

if old_item_print in code:
    code = code.replace(old_item_print, new_item_print)
else:
    print("Could not find old_item_print!")

with open('services/printing_service.py', 'w', encoding='utf-8') as f:
    f.write(code)
print('Done patching printing_service.py')
