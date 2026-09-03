import sys
import os
from pathlib import Path

# Ensure project root is in path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

print("[TEST] Running setup_database.py migration pass...")
try:
    from setup_database import run as run_setup_database
    run_setup_database()
    print("[TEST] Database migration completed successfully.")
except Exception as e:
    print(f"[TEST] Setup database error: {e}")
    sys.exit(1)

from database.db import get_connection
conn = get_connection()
cur = conn.cursor()

print("\n[TEST] Verifying table columns in SQL Server...")

def check_cols(table, cols):
    missing = []
    for c in cols:
        cur.execute(
            "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME=? AND COLUMN_NAME=?",
            (table, c)
        )
        if not cur.fetchone():
            missing.append(c)
    if missing:
        print(f"[MISSING] {table} missing columns: {missing}")
    else:
        print(f"[OK] {table} has all required columns: {cols}")

check_cols("sales", ["cashier_cloud_user_id", "pos_profile", "terminal_id", "store", "payment_method"])
check_cols("sale_items", ["uom", "cost_price", "batch_no", "expiry_date", "serial_no", "price_list_rate", "is_pharmacy", "dosage"])
check_cols("payment_entries", ["paid_amount", "received_amount", "mode_of_payment", "currency"])

conn.close()

print("\n[TEST] Testing create_sale() auto-population...")
from models.sale import create_sale, get_sale_by_id

test_items = [
    {
        "part_no": "TEST-ITEM-001",
        "product_name": "Test Alignment Item",
        "qty": 2,
        "price": 10.0,
        "total": 20.0,
        "discount": 0,
        "tax": "VAT",
        "tax_type": "VAT",
        "tax_rate": 15.0,
        "tax_amount": 3.0,
    }
]

sale = create_sale(
    items=test_items,
    total=20.0,
    tendered=20.0,
    method="Cash",
    cashier_name="Test Cashier",
    customer_name="Test Customer",
    skip_stock=True,
    skip_print=True
)

print(f"[TEST] Sale created with ID: {sale.get('id')}")
print("Sales Dictionary Payload Fields:")
print(f"  - pos_profile: {sale.get('pos_profile')!r}")
print(f"  - terminal_id: {sale.get('terminal_id')!r}")
print(f"  - store: {sale.get('store')!r}")
print(f"  - payment_method: {sale.get('payment_method')!r}")
print(f"  - cashier_cloud_user_id: {sale.get('cashier_cloud_user_id')!r}")

items = sale.get("items", [])
if items:
    it = items[0]
    print("Item Dictionary Payload Fields:")
    print(f"  - uom: {it.get('uom')!r}")
    print(f"  - cost_price: {it.get('cost_price')!r}")
    print(f"  - price_list_rate: {it.get('price_list_rate')!r}")
    print(f"  - serial_no: {it.get('serial_no')!r}")

print("\n[SUCCESS] Verification script completed successfully!")
