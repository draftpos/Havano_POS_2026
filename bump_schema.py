path = r'c:\Users\DELL\New_POS\Havano_POS_2026\setup_database.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('SCHEMA_VERSION = "2026.08.06.1"', 'SCHEMA_VERSION = "2026.08.07.1"')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Bumped SCHEMA_VERSION!')
