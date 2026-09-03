# -*- coding: utf-8 -*-
with open('views/main_window.py', 'r', encoding='utf-8') as f:
    code = f.read()

old_code = '''            # Remap DB field names   print_s field names
            raw_items = get_order_items(order_id)
            items = []
            for it in raw_items:
                items.append({
                    "product_name": it.get("item_name") or it.get("product_name", ""),
                    "qty":          it.get("quantity") or it.get("qty") or 1,
                    "price":        it.get("rate") or it.get("price") or 0,
                    "part_no":      it.get("item_code") or it.get("part_no", ""),
                    "notes":        it.get("item_notes") or it.get("notes", ""),
                    "order_1":      it.get("order_1", 0),
                    "order_2":      it.get("order_2", 0),
                    "order_3":      it.get("order_3", 0),
                    "order_4":      it.get("order_4", 0),
                    "order_5":      it.get("order_5", 0),
                    "order_6":      it.get("order_6", 0),
                })'''

new_code = '''            # Remap DB field names   print_s field names
            if diff_items is not None:
                items = diff_items
            else:
                raw_items = get_order_items(order_id)
                items = []
                for it in raw_items:
                    items.append({
                        "product_name": it.get("item_name") or it.get("product_name", ""),
                        "qty":          it.get("quantity") or it.get("qty") or 1,
                        "price":        it.get("rate") or it.get("price") or 0,
                        "part_no":      it.get("item_code") or it.get("part_no", ""),
                        "notes":        it.get("item_notes") or it.get("notes", ""),
                        "order_1":      it.get("order_1", 0),
                        "order_2":      it.get("order_2", 0),
                        "order_3":      it.get("order_3", 0),
                        "order_4":      it.get("order_4", 0),
                        "order_5":      it.get("order_5", 0),
                        "order_6":      it.get("order_6", 0),
                    })'''

if old_code in code:
    code = code.replace(old_code, new_code)
else:
    print("Could not find old_code block!")

# Also fix the sale_stub inside _print_kot to pass is_modified and modify_reason
old_stub = '''            sale_stub = {
                "invoice_no":    f"ORD-{order_id}",
                "items":         items,
                "cashier_name":  waiter_name,
                "waiter_name":   waiter_name,
                "table_name":    order.get("table_name", f"Table {order.get('table_id', '')}"),
                "customer_name": order.get("customer_name", ""),
                "bill_notes":    order.get("bill_notes", ""),
                "order_number":  order_id,
            }'''

new_stub = '''            sale_stub = {
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

if old_stub in code:
    code = code.replace(old_stub, new_stub)

with open('views/main_window.py', 'w', encoding='utf-8') as f:
    f.write(code)
print('Done patching diff_items logic!')
