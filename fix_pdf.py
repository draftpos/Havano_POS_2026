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
            
            # Replace body style
            text = text.replace(
                '<body style="font-family: Arial, sans-serif; margin: 40px;">',
                '<body style="font-family: \'Segoe UI\', Roboto, \'Helvetica Neue\', Arial, sans-serif; margin: 15px 30px;">'
            )
            
            # Replace company name rendering to collapse if empty
            text = text.replace(
                '<h2 style="color: #1a5fb4; margin:0;">{c_name}</h2>',
                '{f\'<h2 style="color: #1a5fb4; margin:0;">{c_name}</h2>\' if c_name.strip() else ""}'
            )
            
            # Replace company address rendering to collapse if empty
            text = text.replace(
                '<p style="color: #666; margin:0;">{c_addr}</p>',
                '{f\'<p style="color: #666; margin:0; margin-bottom:10px;">{c_addr}</p>\' if c_addr.strip() else ""}'
            )
            
            # Adjust the heading's top margin if the company name was empty
            text = text.replace(
                '<h3 style="color: #1a5fb4; margin-top: 15px;">',
                '<h3 style="color: #1a5fb4; margin-top: 5px; margin-bottom: 5px;">'
            )
            
            # If changed, write back
            if text != orig_text:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(text)
                print(f"Patched {path}")

