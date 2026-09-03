import os, glob, re

files = glob.glob(r'C:\Users\DELL\New_POS\Havano_POS_2026\views\**\*.py', recursive=True)

for full_path in files:
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        new_content = re.sub(r'f\"\"\"\s*<html>\s*<body', 'f\"\"\"<html><body', content)
        new_content = re.sub(r'\"\"\"\s*<html>\s*<body', '\"\"\"<html><body', new_content)
        new_content = re.sub(r'f\"\"\"\s*<html', 'f\"\"\"<html', new_content)
        
        if new_content != content:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f'Fixed {full_path}')
    except Exception as e:
        print(e)
