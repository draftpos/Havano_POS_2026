import os

stock_section = """

---

## 6. Stock & Inventory Management

- **Header**: `Authorization: Bearer <token>`
- **Content-Type**: `application/json`

### `GET /api/method/erpnext.stock.utils.get_stock_balance`
*Retrieves the current real-time stock on hand for an item in a specific warehouse/store.*

**Query Parameters:**
- `item_code`: The item code / barcode (e.g. `103`)
- `warehouse`: The name of the store / warehouse (e.g. `store 2`)

**Request Example:**
`GET /api/method/erpnext.stock.utils.get_stock_balance?item_code=103&warehouse=store%202`

**Response (200):**
```json
{
  "message": 25.0
}
```

---

### `POST /api/resource/Stock Entry`
*Creates and records a Stock Entry (Material Transfer between stores, Material Receipt into store, or Material Issue out of store). Automatically updates warehouse stock valuation and the stock ledger upon submission.*

**Supported `stock_entry_type` values:**
- `"Material Transfer"` (requires `from_warehouse` and `to_warehouse`)
- `"Material Receipt"` (requires `to_warehouse`)
- `"Material Issue"` (requires `from_warehouse`)

**Request (Material Transfer between Warehouses):**
```json
{
  "stock_entry_type": "Material Transfer",
  "from_warehouse": "Dreamwiseagency",
  "to_warehouse": "store 2",
  "posting_date": "2026-09-09",
  "remarks": "Inter-branch inventory transfer from main depot",
  "docstatus": 1,
  "items": [
    {
      "item_code": "103",
      "qty": 10.0,
      "uom": "Each",
      "basic_rate": 45.00
    }
  ]
}
```

**Response (200):**
```json
{
  "data": {
    "name": "STE-00015",
    "stock_entry_type": "Material Transfer",
    "posting_date": "2026-09-09 00:00:00",
    "from_warehouse": "Dreamwiseagency",
    "to_warehouse": "store 2",
    "remarks": "Inter-branch inventory transfer from main depot",
    "docstatus": 1
  }
}
```

---

### `GET /api/resource/Stock Entry`
*Lists recorded stock entries/transfers scoped to the user's accessible stores and tenant.*

**Optional Query Parameters:**
- `filters`: JSON array e.g. `[["from_warehouse", "=", "Dreamwiseagency"]]`
- `limit_page_length`: Maximum records to return (default `100`)
- `limit_start`: Offset for pagination (default `0`)

**Response (200):**
```json
{
  "data": [
    {
      "name": "STE-00015",
      "posting_date": "2026-09-09 00:00:00",
      "from_warehouse": "Dreamwiseagency",
      "to_warehouse": "store 2",
      "total_outgoing_value": 450.0,
      "remarks": "Inter-branch inventory transfer from main depot",
      "docstatus": 1
    }
  ]
}
```

---

### `GET /api/resource/Stock Entry/<name>`
*Retrieves complete details of a specific Stock Entry including line items.*

**Response (200):**
```json
{
  "data": {
    "name": "STE-00015",
    "stock_entry_type": "Material Transfer",
    "posting_date": "2026-09-09 00:00:00",
    "from_warehouse": "Dreamwiseagency",
    "to_warehouse": "store 2",
    "remarks": "Inter-branch inventory transfer from main depot",
    "total_outgoing_value": 450.0,
    "docstatus": 1,
    "items": [
      {
        "item_code": "103",
        "item_name": "Stock 4",
        "qty": 10.0,
        "uom": "Each",
        "s_warehouse": "Dreamwiseagency",
        "t_warehouse": "store 2",
        "basic_rate": 45.0,
        "basic_amount": 450.0
      }
    ]
  }
}
```

---

### `PUT /api/resource/Stock Entry/<name>`
*Cancels a submitted stock entry and rolls back inventory movements.*

**Request:**
```json
{
  "docstatus": 2
}
```

**Response (200):**
```json
{
  "data": {
    "name": "STE-00015",
    "status": "cancelled",
    "docstatus": 2
  }
}
```

---

### `POST /api/resource/Stock Reconciliation`
*Performs physical stock take / inventory adjustment. Compares counted physical quantities against current system valuation, computes variance, creates an audit record, and synchronizes on-hand stock.*

**Request:**
```json
{
  "company": "store 2",
  "posting_date": "2026-09-09 16:30:00",
  "remarks": "Weekly physical stock count",
  "items": [
    {
      "item_code": "103",
      "warehouse": "store 2",
      "qty": 30.0
    }
  ]
}
```

**Response (200):**
```json
{
  "data": {
    "name": "ADJ-00008",
    "company": "store 2",
    "posting_date": "2026-09-09 16:30:00",
    "docstatus": 1
  }
}
```

---

### `GET /api/method/saas_api.www.api.get_stock_reconciliation_with_items`
*Retrieves history of stock reconciliations / adjustments with line items and count differences.*

**Query Parameters:**
- `from_date`: Start date (`YYYY-MM-DD`)
- `to_date`: End date (`YYYY-MM-DD`)
- `cost_center`: Warehouse/Store name

**Response (200):**
```json
{
  "message": [
    {
      "name": "ADJ-00008",
      "posting_date": "2026-09-09 16:30:00",
      "store": "store 2",
      "status": "posted",
      "items": [
        {
          "item_code": "103",
          "item_name": "Stock 4",
          "on_hand": 25.0,
          "counted": 30.0,
          "difference": 5.0
        }
      ]
    }
  ]
}
```

---

### `GET /api/method/saas_api.www.api.get_stock_purchases_with_items`
*Retrieves incoming supplier purchase stock receipts with line item details.*

**Query Parameters:**
- `from_date`: Start date (`YYYY-MM-DD`)
- `to_date`: End date (`YYYY-MM-DD`)
- `supplier`: Optional supplier name filter

**Response (200):**
```json
{
  "message": [
    {
      "name": "PUR-2026-00005",
      "posting_date": "2026-09-08",
      "supplier": "ABC Distributors",
      "store": "store 2",
      "total_amount": 450.00,
      "items": [
        {
          "item_code": "103",
          "item_name": "Stock 4",
          "qty": 10.0,
          "rate": 45.00,
          "amount": 450.00
        }
      ]
    }
  ]
}
```

---

### `GET /api/resource/Warehouse`
*Returns all active stores/warehouses accessible for stock movements and allocation.*

**Alias:** `GET /api/method/havano_pos_integration.api.get_warehouses`

**Response (200):**
```json
{
  "data": [
    {
      "name": "store 2",
      "warehouse_name": "store 2",
      "is_default": true
    },
    {
      "name": "Dreamwiseagency",
      "warehouse_name": "Dreamwiseagency",
      "is_default": false
    }
  ]
}
```
"""

odoo_doc_path = r'C:\Program Files\Odoo 19.0.20260803\server\addons\custom-addons\havanoposdesk_odoo\API_DOCUMENTATION.md'
try:
    with open(odoo_doc_path, 'r', encoding='utf-8') as f:
        content = f.read()

    if '## 6. Stock & Inventory Management' not in content:
        with open(odoo_doc_path, 'a', encoding='utf-8') as f:
            f.write(stock_section)
        print('Successfully appended Section 6 to Odoo API_DOCUMENTATION.md')
    else:
        print('Section 6 already present in Odoo API_DOCUMENTATION.md')
except Exception as e:
    print('Failed to update Odoo API_DOCUMENTATION.md:', e)

scratch_doc = r'c:\Users\user\Desktop\Havano_POS_2026-main\scratch\havanoposdesk_odoo\API_DOCUMENTATION.md'
try:
    with open(scratch_doc, 'r', encoding='utf-8') as f:
        s_content = f.read()
    if '## 6. Stock & Inventory Management' not in s_content:
        with open(scratch_doc, 'a', encoding='utf-8') as f:
            f.write(stock_section)
        print('Successfully appended Section 6 to scratch API_DOCUMENTATION.md')
except Exception as e:
    print('Scratch doc:', e)
