# Fix all emoji and mojibake in main_window.py
import codecs

path = r'c:\Users\DELL\New_POS\Havano_POS_2026\views\main_window.py'
content = codecs.open(path, 'r', 'utf-8').read()

original_len = len(content)
changes = 0

def do_replace(old, new, desc):
    global content, changes
    c = content.count(old)
    if c:
        content = content.replace(old, new)
        changes += c
        print(f"  {desc}: {c} replacements")

# ─── 1. NOTES COLUMN: Replace pen/pin emoji with simple text marker ───
# First POSView (proper emoji)
do_replace('\U0001F58A', '*', 'Pen emoji -> asterisk')
do_replace('\U0001F4CC', '', 'Pin emoji -> empty')

# Second POSView (mojibake versions)
do_replace('\u2261\u0192\u00FB\u00E8', '*', 'Corrupted pen mojibake -> asterisk')
do_replace('\u2261\u0192\u00F4\u00EE', '', 'Corrupted pin mojibake -> empty')

# Remaining mojibake fragments (e.g. in print/debug lines) 
do_replace('\u2261\u0192\u00C4\u00BB', '', 'Corrupted target emoji')

# ─── 2. BUTTON LABELS: Replace emoji with ASCII text ───────────────────
# These are the visible button labels that show as garbled on Windows
do_replace('QPushButton("\u2713")', 'QPushButton("OK")', 'Checkmark button -> OK')
do_replace('QPushButton("\u2715")', 'QPushButton("Clear")', 'Cross button -> Clear')
do_replace('QPushButton("\u2328")', 'QPushButton("KB")', 'Keyboard button -> KB')

# Cancel reason dialog buttons with checkmark
do_replace('\u2713  Modify KOT', 'Modify KOT', 'Modify KOT checkmark prefix')
do_replace('\u2713  Cancel KOT', 'Cancel KOT', 'Cancel KOT checkmark prefix')

# Dismiss button
do_replace('QPushButton("\u2715")', 'QPushButton("X")', 'Dismiss X button')

# ─── 3. RETURN BUTTON: Fix corrupted arrow ────────────────────────────
do_replace('\u0393\u00E5\u2310   Return', 'Return', 'Corrupted return arrow')
do_replace('\u21A9   Return', 'Return', 'Return arrow emoji -> text')

# ─── 4. NAV ARROWS: Keep as simple < and > ─────────────────────────────
do_replace('QPushButton("\u25C0")', 'QPushButton("<")', 'Left triangle -> <')
do_replace('QPushButton("\u25B6")', 'QPushButton(">")', 'Right triangle -> >')
do_replace('QPushButton("\u25C0 Prev")', 'QPushButton("< Prev")', 'Prev arrow')
do_replace('QPushButton("Next \u25B6")', 'QPushButton("Next >")', 'Next arrow')

# Second POSView corrupted nav arrows
do_replace('QPushButton("\u2562")', 'QPushButton(">")', 'Corrupted right arrow')
do_replace('QPushButton("Next \u2562")', 'QPushButton("Next >")', 'Corrupted next arrow')

# ─── 5. CUSTOMER BUTTON: Fix corrupted return indicator ────────────────
do_replace('\u0393\u00E5\u2310  {cust}  (RETURN)', '{cust}  (RETURN)', 'Customer return arrow')
do_replace('\u21A9  {cust}  (RETURN)', '{cust}  (RETURN)', 'Customer return arrow 2')

# ─── 6. HOURGLASS in fiscalization loader ──────────────────────────────
do_replace('QLabel("\u23F3")', 'QLabel("...")', 'Hourglass -> dots')

# ─── 7. STATUS BAR MOJIBAKE ───────────────────────────────────────────
do_replace('\u0393\u00C7\u0551', '>', 'Corrupted right guillemet')  # Options > 
do_replace('\u203A', '>', 'Single right guillemet')  # Options > 

# ─── 8. DOSAGE SEPARATOR MOJIBAKE ─────────────────────────────────────
do_replace('  \u252C\u2557  ', '  |  ', 'Corrupted dot separator')
do_replace('  \u00B7  ', '  |  ', 'Middle dot separator (if any)')

print(f"\nTotal replacements: {changes}")
print(f"File size: {original_len} -> {len(content)}")

# Write back
with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print("File saved successfully.")
