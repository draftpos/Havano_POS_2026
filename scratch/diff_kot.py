# -*- coding: utf-8 -*-
import re

with open('views/main_window.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Replace _save_restaurant_order DB logic to capture diff
old_save = '''            order_id = getattr(self, "_current_order_id", None)
            table_id = self._current_table["id"]
            cust_name = (self._selected_customer or {}).get("customer_name", "Walk-in")

            if order_id:
                if getattr(self, "_restaurant_append_mode", False):
                    # We are adding on top, do NOT delete old items!
                    cur.execute("UPDATE restaurant_orders SET updated_at = CURRENT_TIMESTAMP, bill_notes = ? WHERE id = ?", (self._bill_notes, order_id))
                else:
                    # Update existing order by replacing items
                    cur.execute("DELETE FROM restaurant_order_items WHERE order_id = ?", (order_id,))
                    cur.execute("UPDATE restaurant_orders SET updated_at = CURRENT_TIMESTAMP, bill_notes = ? WHERE id = ?", (self._bill_notes, order_id))
            else:'''

new_save = '''            order_id = getattr(self, "_current_order_id", None)
            table_id = self._current_table["id"]
            cust_name = (self._selected_customer or {}).get("customer_name", "Walk-in")
            
            diff_items = None
            is_modified = False

            if order_id:
                if getattr(self, "_restaurant_append_mode", False):
                    # We are adding on top, do NOT delete old items!
                    cur.execute("UPDATE restaurant_orders SET updated_at = CURRENT_TIMESTAMP, bill_notes = ? WHERE id = ?", (self._bill_notes, order_id))
                else:
                    is_modified = True
                    # 0. Capture old items to calculate diff for KOT printout
                    old_items_map = {}
                    cur.execute("SELECT item_code, item_name, quantity, item_notes, rate, order_1, order_2, order_3, order_4, order_5, order_6 FROM restaurant_order_items WHERE order_id = ?", (order_id,))
                    for r in cur.fetchall():
                        old_items_map[r[0]] = {
                            "part_no": r[0],
                            "product_name": r[1],
                            "qty": float(r[2] or 0),
                            "notes": r[3] or "",
                            "price": float(r[4] or 0),
                            "flags": (r[5], r[6], r[7], r[8], r[9], r[10])
                        }

                    # Update existing order by replacing items
                    cur.execute("DELETE FROM restaurant_order_items WHERE order_id = ?", (order_id,))
                    cur.execute("UPDATE restaurant_orders SET updated_at = CURRENT_TIMESTAMP, bill_notes = ? WHERE id = ?", (self._bill_notes, order_id))
                    
                    # Calculate diff
                    diff_items = []
                    new_item_dict = {str(it.get("part_no", "")).strip(): it for it in items}
                    
                    for part_no, new_it in new_item_dict.items():
                        new_it_copy = dict(new_it)
                        if part_no in old_items_map:
                            old_it = old_items_map[part_no]
                            if old_it["qty"] != new_it["qty"]:
                                new_it_copy["old_qty"] = old_it["qty"]
                                diff_items.append(new_it_copy)
                        else:
                            diff_items.append(new_it_copy)
                    
                    for part_no, old_it in old_items_map.items():
                        if part_no not in new_item_dict:
                            removed_it = {
                                "part_no": part_no,
                                "product_name": old_it["product_name"],
                                "qty": old_it["qty"],
                                "notes": old_it["notes"],
                                "price": old_it["price"],
                                "is_cancelled": True,
                                "item_name": old_it["product_name"]
                            }
                            diff_items.append(removed_it)
                            
            else:'''

if old_save in code:
    code = code.replace(old_save, new_save)
else:
    print("Could not find old_save block!")

# Replace print_kot call
old_print_call = '''            if self.parent_window:
                self.parent_window._print_kot(order_id)'''
new_print_call = '''            if self.parent_window:
                modify_reason = getattr(self, "_last_modify_reason", "")
                self.parent_window._print_kot(order_id, diff_items=diff_items, is_modified=is_modified, modify_reason=modify_reason)'''

if old_print_call in code:
    code = code.replace(old_print_call, new_print_call)

# Update _print_kot signature and logic
old_print_kot_def = '''    def _print_kot(self, order_id: int):
        """Print KOT production slips for each kitchen station, then one full
        summary receipt to the main invoice printer."""'''

new_print_kot_def = '''    def _print_kot(self, order_id: int, diff_items: list = None, is_modified: bool = False, modify_reason: str = ""):
        """Print KOT production slips for each kitchen station, then one full
        summary receipt to the main invoice printer."""'''

if old_print_kot_def in code:
    code = code.replace(old_print_kot_def, new_print_kot_def)

# Update _print_kot items retrieval
old_items_retrieval = '''            items = get_order_items(order_id)
            if not order or not items:
                print(f"[KOT] Could not find order or items for ORD-{order_id}")
                return

            waiter_name = get_waiter_name(order.get("waiter_id"))

            sale_stub = {
                "invoice_no":    f"ORD-{order_id}",
                "items":         items,
                "cashier_name":  waiter_name,
                "waiter_name":   waiter_name,
                "table_name":    order.get("table_name", f"Table {order.get('table_id', '')}"),
                "customer_name": order.get("customer_name", ""),
                "bill_notes":    order.get("bill_notes", ""),
                "order_number":  order_id,
            }'''

new_items_retrieval = '''            items = diff_items if diff_items is not None else get_order_items(order_id)
            if not order or not items:
                print(f"[KOT] Could not find order or items for ORD-{order_id}")
                return

            waiter_name = get_waiter_name(order.get("waiter_id"))

            sale_stub = {
                "invoice_no":    f"ORD-{order_id}",
                "items":         items,
                "cashier_name":  waiter_name,
                "waiter_name":   waiter_name,
                "table_name":    order.get("table_name", f"Table {order.get('table_id', '')}"),
                "customer_name": order.get("customer_name", ""),
                "bill_notes":    order.get("bill_notes", ""),
                "order_number":  order_id,
                "is_modified":   is_modified,
                "modify_reason": modify_reason,
            }'''

if old_items_retrieval in code:
    code = code.replace(old_items_retrieval, new_items_retrieval)

with open('views/main_window.py', 'w', encoding='utf-8') as f:
    f.write(code)
print('Done diff patching main_window.py')
