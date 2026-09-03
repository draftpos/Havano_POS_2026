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
            text = re.sub(
                r'<body style=[\'"]font-family: Arial, sans-serif; margin: 40px;[\'"]>',
                '<body style="font-family: \'Segoe UI\', Roboto, \'Helvetica Neue\', Arial, sans-serif; margin: 15px 30px;">',
                text
            )
            
            text = re.sub(
                r'<body style=[\'"]font-family:Arial,sans-serif; font-size:12px; color:#222; margin:10px; padding:0;[\'"]>',
                '<body style="font-family: \'Segoe UI\', Roboto, \'Helvetica Neue\', Arial, sans-serif; font-size:12px; color:#222; margin:15px 30px; padding:0;">',
                text
            )
            
            # Replace company name rendering to collapse if empty
            text = re.sub(
                r'<h2 style=[\'"]color: #1a5fb4; margin:0;[\'"]>\{c_name\}</h2>',
                '{f\'<h2 style="color: #1a5fb4; margin:0;">{c_name}</h2>\' if c_name.strip() else ""}',
                text
            )
            
            # Replace company address rendering to collapse if empty
            text = re.sub(
                r'<p style=[\'"]color: #666; margin:0;[\'"]>\{c_addr\}</p>',
                '{f\'<p style="color: #666; margin:0; margin-bottom:10px;">{c_addr}</p>\' if c_addr.strip() else ""}',
                text
            )
            
            if text != orig_text:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(text)
                print(f"Patched {path}")

