# -*- coding: utf-8 -*-
with open('views/main_window.py', 'r', encoding='utf-8') as f:
    code = f.read()

old_link_sig = '''    def link_to_table(self, table_data: dict, append_mode: bool = False, order_id: int = None, force_new: bool = False):'''
new_link_sig = '''    def link_to_table(self, table_data: dict, append_mode: bool = False, order_id: int = None, force_new: bool = False, edit_mode: bool = False):'''

if old_link_sig in code:
    code = code.replace(old_link_sig, new_link_sig)
else:
    print("Could not find old_link_sig!")

old_link_set = '''        self._restaurant_mode = True
        self._restaurant_append_mode = append_mode'''
new_link_set = '''        self._restaurant_mode = True
        self._restaurant_append_mode = append_mode
        self._restaurant_edit_mode = edit_mode'''

if old_link_set in code:
    code = code.replace(old_link_set, new_link_set)
else:
    print("Could not find old_link_set!")

old_on_kot = '''        self._pos_view.link_to_table(td, append_mode=False, order_id=order_data["id"])'''
new_on_kot = '''        self._pos_view.link_to_table(td, append_mode=False, order_id=order_data["id"], edit_mode=(action == "edit"))'''

if old_on_kot in code:
    code = code.replace(old_on_kot, new_on_kot)
else:
    print("Could not find old_on_kot!")

old_refresh = '''        elif getattr(self, "_restaurant_mode", False):
            if getattr(self, "_current_order_id", None) and not getattr(self, "_restaurant_append_mode", False):
                # Order loaded from an occupied table — ready for checkout
                self.btn_pay.setText("PAY ORDER (F5)")
                self.btn_pay.setStyleSheet(
                    f"background-color: {SUCCESS}; color: {WHITE}; font-weight: bold; "
                    f"border-radius: 6px; font-size: 17px;"
                )
            else:
                # Fresh table or Append Mode — save the order first
                self.btn_pay.setText("SAVE ORDER (F5)")
                self.btn_pay.setStyleSheet(
                    f"background-color: #3498db; color: {WHITE}; font-weight: bold; "
                    f"border-radius: 6px; font-size: 17px;"
                )'''

new_refresh = '''        elif getattr(self, "_restaurant_mode", False):
            if getattr(self, "_restaurant_edit_mode", False):
                self.btn_pay.setText("MODIFY KOT (F5)")
                self.btn_pay.setStyleSheet(
                    f"background-color: #f39c12; color: {WHITE}; font-weight: bold; "
                    f"border-radius: 6px; font-size: 17px;"
                )
            elif getattr(self, "_current_order_id", None) and not getattr(self, "_restaurant_append_mode", False):
                # Order loaded from an occupied table — ready for checkout
                self.btn_pay.setText("PAY ORDER (F5)")
                self.btn_pay.setStyleSheet(
                    f"background-color: {SUCCESS}; color: {WHITE}; font-weight: bold; "
                    f"border-radius: 6px; font-size: 17px;"
                )
            else:
                # Fresh table or Append Mode — save the order first
                self.btn_pay.setText("SAVE ORDER (F5)")
                self.btn_pay.setStyleSheet(
                    f"background-color: #3498db; color: {WHITE}; font-weight: bold; "
                    f"border-radius: 6px; font-size: 17px;"
                )'''

if old_refresh in code:
    code = code.replace(old_refresh, new_refresh)
else:
    print("Could not find old_refresh!")

old_open_pay = '''        if getattr(self, "_restaurant_mode", False):
            btn_text = self.btn_pay.text().upper()'''

new_open_pay = '''        if getattr(self, "_restaurant_mode", False):
            if getattr(self, "_restaurant_edit_mode", False):
                self._save_restaurant_order()
                return
            btn_text = self.btn_pay.text().upper()'''

if old_open_pay in code:
    code = code.replace(old_open_pay, new_open_pay)
else:
    print("Could not find old_open_pay!")

with open('views/main_window.py', 'w', encoding='utf-8') as f:
    f.write(code)

print('Done patching Modify KOT button!')
