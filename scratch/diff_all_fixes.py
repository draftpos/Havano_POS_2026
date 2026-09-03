# -*- coding: utf-8 -*-
# 1. Fix get_sales_by_waiter to include time in end_date
with open('models/restaurant_order.py', 'r', encoding='utf-8') as f:
    code1 = f.read()

old_end_date = '''        if end_date:
            query += " AND invoice_date <= ?"
            params.append(end_date)'''

new_end_date = '''        if end_date:
            query += " AND invoice_date <= ?"
            params.append(end_date + " 23:59:59")'''

if old_end_date in code1:
    code1 = code1.replace(old_end_date, new_end_date)
else:
    print("Could not find old_end_date!")
with open('models/restaurant_order.py', 'w', encoding='utf-8') as f:
    f.write(code1)

# 2. Fix main_window.py for always showing reason popup AND append_mode
with open('views/main_window.py', 'r', encoding='utf-8') as f:
    code2 = f.read()

old_reason = '''        if action == "edit":
            from models.restaurant_order import get_restaurant_settings
            rs = get_restaurant_settings()
            if rs.get("require_modify_reason"):
                from models.restaurant_order import get_cancel_reasons
                predefined_reasons = get_cancel_reasons()
                reason = self._show_cancel_reason_dialog(order_data["id"], predefined_reasons, title="Modify Reason", action_text="?  Modify KOT", is_danger=False)
                if reason is None or not reason.strip():
                    # Cancelled edit
                    return
                self._last_modify_reason = reason.strip()'''

new_reason = '''        if action == "edit":
            from models.restaurant_order import get_cancel_reasons
            predefined_reasons = get_cancel_reasons()
            reason = self._show_cancel_reason_dialog(order_data["id"], predefined_reasons, title="Modify Reason", action_text="?  Modify KOT", is_danger=False)
            if reason is None or not reason.strip():
                # Cancelled edit
                return
            self._last_modify_reason = reason.strip()'''

if old_reason in code2:
    code2 = code2.replace(old_reason, new_reason)
else:
    print("Could not find old_reason!")

old_append = '''        self._pos_view.link_to_table(td, append_mode=(action == "edit"), order_id=order_data["id"])'''
new_append = '''        self._pos_view.link_to_table(td, append_mode=False, order_id=order_data["id"])'''

if old_append in code2:
    code2 = code2.replace(old_append, new_append)
else:
    print("Could not find old_append!")

with open('views/main_window.py', 'w', encoding='utf-8') as f:
    f.write(code2)

print('Done patching fixes!')
