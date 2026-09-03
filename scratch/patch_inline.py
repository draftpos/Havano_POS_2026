import re

filepath = 'views/main_window.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Increase inline search debounce from 80ms to 400ms
content = content.replace('self._inline_search_timer.start(80)', 'self._inline_search_timer.start(400)')

# 2. Add loader to _inline_refresh_popup
# Find the start of the try block in _inline_refresh_popup
search_inline_popup = '''        try:
            from models.product import search_products
            wh_id = getattr(self, "_get_active_warehouse_id", lambda: None)()
            products = search_products(query, warehouse_id=wh_id)
        except Exception:'''

replace_inline_popup = '''        # Show loader before blocking DB query
        from views.components.sleek_loader import SleekLoaderOverlay
        from PySide6.QtWidgets import QApplication
        if not hasattr(self, '_cat_loader'):
            self._cat_loader = SleekLoaderOverlay(self)
        self._cat_loader.set_status("Searching...", "Please wait")
        self._cat_loader.show_loading()
        QApplication.processEvents()
        
        try:
            from models.product import search_products
            wh_id = getattr(self, "_get_active_warehouse_id", lambda: None)()
            products = search_products(query, warehouse_id=wh_id)
        except Exception:'''

content = content.replace(search_inline_popup, replace_inline_popup)

# Hide it after
search_inline_hide = '''        if not products:
            popup.hide(); return'''

replace_inline_hide = '''        if hasattr(self, '_cat_loader'):
            self._cat_loader.hide_loading()

        if not products:
            popup.hide(); return'''

content = content.replace(search_inline_hide, replace_inline_hide)

# Write back
with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("Inline search patch applied successfully.")
