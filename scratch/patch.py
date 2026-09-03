import os

filepath = 'views/main_window.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Define what to find and replace
search_str = '''    def _load_category_products(self, idx, name):
        """
        Load products for a category, overlay the active customer's
        price-list prices, and stash variant metadata for tap-time lookup.
        """
        try:'''

replace_str = '''    def _load_category_products(self, idx, name):
        """
        Load products for a category, overlay the active customer's
        price-list prices, and stash variant metadata for tap-time lookup.
        """
        from views.components.sleek_loader import SleekLoaderOverlay
        from PySide6.QtWidgets import QApplication
        if not hasattr(self, '_cat_loader'):
            self._cat_loader = SleekLoaderOverlay(self)
        self._cat_loader.set_status(f"Optimizing {name}...", "Please wait")
        self._cat_loader.show_loading()
        QApplication.processEvents()
        
        try:'''

# Hide loader logic
search_hide = '''            self._has_any_product_image = False

        # Always reset to first page when switching categories
        self._product_page = 0
        self._render_product_page()'''

replace_hide = '''            self._has_any_product_image = False

        if hasattr(self, '_cat_loader'):
            self._cat_loader.hide_loading()

        # Always reset to first page when switching categories
        self._product_page = 0
        self._render_product_page()'''

# Perform replacements
new_content = content.replace(search_str, replace_str)
new_content = new_content.replace(search_hide, replace_hide)

# Change processEvents interval
new_content = new_content.replace('if i > 0 and i % 500 == 0:', 'if i > 0 and i % 50 == 0:')

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Patch applied successfully.")
