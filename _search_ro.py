import codecs
content = codecs.open(r'c:\Users\DELL\New_POS\Havano_POS_2026\models\restaurant_order.py', 'r', 'utf-8').read()
lines = content.split('\n')
with open(r'c:\Users\DELL\New_POS\Havano_POS_2026\_mojibake_ro.txt', 'w', encoding='utf-8') as f:
    for i, line in enumerate(lines):
        if 'get_predefined_notes' in line or 'predefined_notes' in line or 'Grays' in line or '\u2261' in line or '\u0393' in line:
            f.write(f'{i+1}: {line.strip()[:100]}\n')
