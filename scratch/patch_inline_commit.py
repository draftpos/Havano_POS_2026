import re

filepath = 'views/main_window.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Add loader to _inline_commit_query
search_commit = '''        # ΓöÇΓöÇ Alternative barcode lookup (fetches specific UOM) ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
        try:
            from models.product import get_product_by_barcode'''

replace_commit = '''        # Show loader before blocking DB query
        from views.components.sleek_loader import SleekLoaderOverlay
        from PySide6.QtWidgets import QApplication
        if not hasattr(self, '_cat_loader'):
            self._cat_loader = SleekLoaderOverlay(self)
        self._cat_loader.set_status("Finding item...", "Please wait")
        self._cat_loader.show_loading()
        QApplication.processEvents()

        # ΓöÇΓöÇ Alternative barcode lookup (fetches specific UOM) ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
        try:
            from models.product import get_product_by_barcode'''

content = content.replace(search_commit, replace_commit)

# Hide loader after processing the product
search_commit_hide = '''        if product:
            self._inline_commit_product(product, scale_qty=scale_qty, override_uom=barcode_uom)
        else:'''

replace_commit_hide = '''        if hasattr(self, '_cat_loader'):
            self._cat_loader.hide_loading()

        if product:
            self._inline_commit_product(product, scale_qty=scale_qty, override_uom=barcode_uom)
        else:'''

content = content.replace(search_commit_hide, replace_commit_hide)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("Inline commit patch applied successfully.")
