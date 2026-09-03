import codecs

path = r'c:\Users\DELL\New_POS\Havano_POS_2026\views\main_window.py'
# Read as binary to avoid line ending issues
data = open(path, 'rb').read()
content = data.decode('utf-8')
changes = 0

def do_replace(old, new, desc):
    global content, changes
    c = content.count(old)
    if c:
        content = content.replace(old, new)
        changes += c
        print(f"  {desc}: {c} replacements")

# ── VISIBLE UI FIXES (mojibake button labels in second POSView) ─────────

# Bill notes dialog buttons (lines ~18885-18918)
do_replace('QPushButton("\u0393\u00A3\u00F4")', 'QPushButton("OK")', 'Mojibake checkmark btn')
do_replace('QPushButton("\u0393\u00AE\u00BF")', 'QPushButton("KB")', 'Mojibake keyboard btn')
do_replace('QPushButton("\u0393\u00A3\u00F2")', 'QPushButton("Clear")', 'Mojibake cross btn')

# Category/grid nav buttons (lines ~22770-22838)
do_replace('QPushButton("\u0393\u00F9\u00C7")', 'QPushButton("<")', 'Mojibake left arrow')
do_replace('QPushButton("\u0393\u00F9\u00C7 Prev")', 'QPushButton("< Prev")', 'Mojibake prev arrow')

# Discount range indicator (─ is a dash, ΓÇô)
do_replace('\u0393\u00C7\u00F4', '-', 'Mojibake dash in discount range')

# Options > Save Quotation  
do_replace('\u0393\u00C7\u0551', '>', 'Mojibake guillemet')

# Set Image... ellipsis
do_replace('\u0393\u00C7\u00AA', '...', 'Mojibake ellipsis')

print(f"\nTotal: {changes}")

# Write back as binary to preserve line endings
out = content.encode('utf-8')
open(path, 'wb').write(out)
print("Saved.")
