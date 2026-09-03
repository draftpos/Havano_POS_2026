import os

path = r'c:\Users\DELL\New_POS\Havano_POS_2026\views\main_window.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Inject the bundle stock calculation
target_str = 'p_is_bundle = p.get("is_product_bundle", False)'
injection = '''p_is_bundle = p.get("is_product_bundle", False)
                            
                            if p_is_bundle:
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

# We also need to fix info.get("is_bundle") in _recalc_row
target_str2 = 'p_is_bundle = info.get("is_bundle", False)'
injection2 = '''p_is_bundle = info.get("is_bundle", False)
                            if p_is_bundle:
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

target_str3 = 'p_is_bundle = bool(p.get("is_product_bundle", False))'
injection3 = '''p_is_bundle = bool(p.get("is_product_bundle", False))
                            if p_is_bundle:
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

# 2. Remove 'or p_is_bundle' from allow_zero check
content = content.replace('if not p_track_stock or p_is_bundle:', 'if not p_track_stock:')
content = content.replace('if not p_track_stock or p_is_bundle or not block_rule:', 'if not p_track_stock or not block_rule:')

# Apply injections
content = content.replace(target_str, injection)
content = content.replace(target_str2, injection2)
content = content.replace(target_str3, injection3)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Done!')
