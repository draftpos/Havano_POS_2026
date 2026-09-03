# -*- coding: utf-8 -*-
with open('models/sale.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Update ReceiptData fields
old_receipt_data = '''    receipt.bill_notes         = sale.get("bill_notes", "")
    receipt.customerName       = sale.get("customer_name", "Walk-in")
    receipt.tableName          = sale.get("table_name", "")'''

new_receipt_data = '''    receipt.bill_notes         = sale.get("bill_notes", "")
    receipt.customerName       = sale.get("customer_name", "Walk-in")
    receipt.tableName          = sale.get("table_name", "")
    receipt.is_modified        = sale.get("is_modified", False)'''

if old_receipt_data in code:
    code = code.replace(old_receipt_data, new_receipt_data)

# Update Item mapping
old_item = '''        try:
            qty = float(it.get("qty") or 1)
            price = float(it.get("price") or 0)
        except:
            qty, price = 1.0, 0.0

        item = Item(
            productName = it.get("product_name", "Unknown"),
            productid   = it.get("part_no", ""),
            qty         = qty,
            price       = price,
            amount      = qty * price,
            item_notes  = it.get("notes", ""),
            KOT         = it.get("KOT", "")
        )'''

new_item = '''        try:
            qty = float(it.get("qty") or 1)
            price = float(it.get("price") or 0)
        except:
            qty, price = 1.0, 0.0

        item = Item(
            productName = it.get("product_name", "Unknown"),
            productid   = it.get("part_no", ""),
            qty         = qty,
            price       = price,
            amount      = qty * price,
            item_notes  = it.get("notes", ""),
            KOT         = it.get("KOT", ""),
            is_cancelled= it.get("is_cancelled", False),
            old_qty     = float(it.get("old_qty", 0.0))
        )'''

if old_item in code:
    code = code.replace(old_item, new_item)

with open('models/sale.py', 'w', encoding='utf-8') as f:
    f.write(code)
print('Done patching sale.py')
