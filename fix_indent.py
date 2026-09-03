import re

path = r'c:\Users\DELL\New_POS\Havano_POS_2026\views\main_window.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Define the block we injected, without leading spaces so we can re-indent it correctly
block_lines = '''if p_is_bundle:
    try:
        from database.db import get_connection
        _conn = get_connection(); _c = _conn.cursor()
        _c.execute("SELECT id FROM product_bundles WHERE name=?", (p.get("name"),))
        _b = _c.fetchone()
        if _b:
            _c.execute("SELECT item_code, quantity FROM bundle_items WHERE bundle_id=?", (_b[0],))
            _items = _c.fetchall()
            _bundle_stock = 999999.0
            for _icode, _qty in _items:
                _c.execute("SELECT stock FROM products WHERE part_no=?", (_icode,))
                _prow = _c.fetchone()
                if _prow:
                    _cstock = float(_prow[0] if _prow[0] is not None else 0)
                    _req = float(_qty)
                    if _req > 0:
                        _possible = _cstock / _req
                        if _possible < _bundle_stock: _bundle_stock = _possible
            item_stock = _bundle_stock if _items else item_stock
        _conn.close()
    except Exception:
        pass'''

block_lines2 = '''if p_is_bundle:
    try:
        from database.db import get_connection
        _conn = get_connection(); _c = _conn.cursor()
        _c.execute("SELECT id FROM product_bundles WHERE name=?", (info.get("name"),))
        _b = _c.fetchone()
        if _b:
            _c.execute("SELECT item_code, quantity FROM bundle_items WHERE bundle_id=?", (_b[0],))
            _items = _c.fetchall()
            _bundle_stock = 999999.0
            for _icode, _qty in _items:
                _c.execute("SELECT stock FROM products WHERE part_no=?", (_icode,))
                _prow = _c.fetchone()
                if _prow:
                    _cstock = float(_prow[0] if _prow[0] is not None else 0)
                    _req = float(_qty)
                    if _req > 0:
                        _possible = _cstock / _req
                        if _possible < _bundle_stock: _bundle_stock = _possible
            item_stock = _bundle_stock if _items else item_stock
        _conn.close()
    except Exception:
        pass'''

def fix_indentation(match):
    indent = match.group(1)
    assignment = match.group(2)
    # Re-indent the block lines
    is_info = 'info.get' in assignment
    bl = block_lines2 if is_info else block_lines
    reindented = []
    for line in bl.split('\n'):
        if not line.strip():
            reindented.append('')
        else:
            reindented.append(indent + line)
    
    return indent + assignment + '\n' + '\n'.join(reindented)

# We want to match:
# [spaces]p_is_bundle = ...
# [spaces]if p_is_bundle:
# ... up to pass
pattern = re.compile(r'^([ \t]*)(p_is_bundle = [^\n]+)\n\s*if p_is_bundle:\n(?:[ \t]+.*\n)*?[ \t]+pass', re.MULTILINE)

new_content = pattern.sub(fix_indentation, content)

with open(path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print('Indentation fixed!')
