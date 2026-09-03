import os
import re

filepath = 'views/main_window.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# We want to replace the current `_load_category_products` logic with the threaded one.
# Since there are TWO identical POSView classes in the file, we can replace both using regex.

# We will match the entire method using regex.
pattern = re.compile(
    r'(?P<def>    def _load_category_products\(self, idx, name\):\s+"""[\s\S]*?""")\s*'
    r'from views\.components\.sleek_loader import SleekLoaderOverlay[\s\S]*?QApplication\.processEvents\(\)\s*'
    r'(?P<body>try:[\s\S]*?self\._has_any_product_image = False)\s*'
    r'if hasattr\(self, \'_cat_loader\'\):[\s\S]*?self\._render_product_page\(\)'
)

def replacer(match):
    def_part = match.group('def')
    body_part = match.group('body')
    
    # We need to indent the body part by 4 spaces because it goes inside a nested function
    indented_body = "\n".join("    " + line if line else line for line in body_part.split("\n"))
    
    new_func = f'''{def_part}
        from views.components.sleek_loader import SleekLoaderOverlay
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QTimer
        import threading
        
        if not hasattr(self, '_cat_loader'):
            self._cat_loader = SleekLoaderOverlay(self)
        self._cat_loader.set_status(f"Optimizing {{name}}...", "Please wait")
        self._cat_loader.show_loading()
        QApplication.processEvents()

        def background_load():
        {indented_body}
            
            QTimer.singleShot(0, _finish_render)

        def _finish_render():
            if hasattr(self, '_cat_loader'):
                self._cat_loader.hide_loading()
            self._product_page = 0
            self._render_product_page()

        threading.Thread(target=background_load, daemon=True).start()'''
    return new_func

new_content = pattern.sub(replacer, content)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Threaded patch applied successfully.")
