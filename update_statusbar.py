import re

path = r'c:\Users\DELL\New_POS\Havano_POS_2026\views\main_window.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

target = '''        _uname = self.user.get("username", "")
        _urole = self.user.get("role", "cashier")
        _user_lbl = QLabel(f"  {_uname} [{_urole.upper()}]  ")'''

injection = '''        _sys_mode_lower = get_system_mode().lower()
        if _sys_mode_lower == "saas":
            _defs = get_defaults() or {}
            _wh = _defs.get("server_warehouse") or ""
            if not _wh:
                _wh = _defs.get("server_shop_id") or "Main Store"
            _store_lbl = QLabel(f"  Store: {_wh}  | ")
            _store_lbl.setStyleSheet(f"color: {MID}; font-size: 11px; font-weight: bold;")
            self._status_bar.addPermanentWidget(_store_lbl)

        _uname = self.user.get("username", "")
        _urole = self.user.get("role", "cashier")
        _user_lbl = QLabel(f"  {_uname} [{_urole.upper()}]  ")'''

if target in content:
    content = content.replace(target, injection)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('Status bar updated!')
else:
    print('Target not found!')
