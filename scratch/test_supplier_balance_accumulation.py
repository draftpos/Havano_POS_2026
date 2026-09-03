import sys
import os
sys.path.insert(0, r"c:\Users\DELL\New_POS\Havano_POS_2026")

from PySide6.QtWidgets import QApplication
from database.db import get_connection
from models.supplier import get_all_suppliers, create_supplier, ensure_supplier_table
from models.stock_entry import create_stock_entry, migrate as migrate_stock_entry
from views.dialogs.purchase_invoice_dialog import PurchaseInvoiceDialog

# Initialize DB tables
ensure_supplier_table()
migrate_stock_entry()

# Initialize Qt App
app = QApplication.instance() or QApplication(sys.argv)

print("Starting Supplier Balance Accumulation Integration Tests...")

conn = get_connection()
cur = conn.cursor()

# 1. Clean up any previous test suppliers to have a clean state
cur.execute("DELETE FROM suppliers WHERE UPPER(TRIM(name)) = 'TEST SUPPLIER ACCUMULATE'")
conn.commit()

# 2. Create a new test supplier
cur.execute("""
    INSERT INTO suppliers (name, email, phone, address, balance)
    OUTPUT INSERTED.id
    VALUES ('TEST SUPPLIER ACCUMULATE', 'test@accumulate.com', '123456789', '123 Accumulate St', 100.00)
""")
sup_id = int(cur.fetchone()[0])
conn.commit()
print(f"Created supplier 'TEST SUPPLIER ACCUMULATE' with initial balance of $100.00.")

# 3. Create a PurchaseInvoiceDialog instance
pi_dlg = PurchaseInvoiceDialog()

# Reload the combobox cache so it registers our new supplier
pi_dlg._load_combos()

# Select the newly created supplier
idx = pi_dlg.sup_combo.findText("TEST SUPPLIER ACCUMULATE")
assert idx >= 0, "Test supplier not found in combo box!"
pi_dlg.sup_combo.setCurrentIndex(idx)

# Verify address and previous balance are correctly populated
assert pi_dlg.address_edit.text() == "123 Accumulate St", f"Expected '123 Accumulate St', got '{pi_dlg.address_edit.text()}'"
assert pi_dlg._supplier_prev_balance == 100.00, f"Expected previous balance to be 100.00, got {pi_dlg._supplier_prev_balance}"
assert float(pi_dlg.balance_edit.text()) == 100.00, f"Expected balance field to display 100.00, got {pi_dlg.balance_edit.text()}"
print("Success: Dialog successfully fetched and displayed supplier's previous balance of $100.00!")

# 4. Add a mock product and check accumulation
mock_product = {
    "id": 1,
    "part_no": "TEST-ACCUM",
    "name": "Accumulation Item",
    "cost": 50.00,
    "price": 75.00,
    "uom": "Unit"
}
pi_dlg.add_product(mock_product)
pi_dlg._recalc_totals()

# Accumulated balance should be: prev_bal (100.00) + grand_total (50.00) = 150.00
grand_total = float(pi_dlg.lbl_grand_total.text().replace("$", ""))
balance_edit_val = float(pi_dlg.balance_edit.text())
print(f"New Invoice Grand Total: {grand_total}, Dialog Balance field: {balance_edit_val}")
assert grand_total == 50.00, f"Expected Grand Total to be 50.00, got {grand_total}"
assert balance_edit_val == 150.00, f"Expected Balance field to accumulate to 150.00, got {balance_edit_val}"
print("Success: Dialog successfully accumulated previous balance + new invoice total ($100.00 + $50.00 = $150.00)!")

# 5. Toggle 'Paid' button state and check
pi_dlg.paid_btn.setChecked(True) # Set to Paid
# Since current invoice is paid, unpaid balance of current invoice is 0.0. 
# So the displayed balance should go back to the previous outstanding balance ($100.00).
balance_edit_val = float(pi_dlg.balance_edit.text())
assert balance_edit_val == 100.00, f"Expected balance to show only previous 100.00 when current is paid, got {balance_edit_val}"
print("Success: Dialog correctly displays only previous balance ($100.00) when the new invoice is marked as Paid!")

# Untoggle Paid back to Unpaid
pi_dlg.paid_btn.setChecked(False)
balance_edit_val = float(pi_dlg.balance_edit.text())
assert balance_edit_val == 150.00, f"Expected balance to return to 150.00 when unchecked, got {balance_edit_val}"
print("Success: Untoggling 'Mark as Paid' correctly restored the accumulated balance ($150.00)!")

# 6. Verify invoice saving updates the database correctly
# We mock save by calling create_stock_entry with the calculated balance_val from our _on_save logic
is_paid = pi_dlg.paid_btn.isChecked()
balance_to_save = 0.0
if not is_paid:
    entered_val = float(pi_dlg.balance_edit.text().strip() or 0.0)
    prev_bal = pi_dlg._supplier_prev_balance
    balance_to_save = max(entered_val - prev_bal, 0.0)

assert balance_to_save == 50.00, f"Expected unpaid balance to save to be 50.00, got {balance_to_save}"

# Call create_stock_entry to commit to database
success = create_stock_entry(
    warehouse_id=pi_dlg.wh_combo.currentData() or 1,
    price_list_id=1,
    items=[{"product_id": mock_product["id"], "qty": 1, "cost": mock_product["cost"], "selling": mock_product["price"]}],
    supplier="TEST SUPPLIER ACCUMULATE",
    doc_no=pi_dlg.doc_no_edit.text(),
    date_time=pi_dlg.date_time_edit.text(),
    balance=balance_to_save,
    is_paid=is_paid
)

assert success is True, "Failed to save stock entry!"

# Check that the supplier's balance in the database has accumulated to $150.00
cur.execute("SELECT balance FROM suppliers WHERE id = ?", (sup_id,))
new_db_balance = float(cur.fetchone()[0])
assert new_db_balance == 150.00, f"Expected new database balance of supplier to be 150.00, got {new_db_balance}"
print(f"Success: Supplier balance in database successfully accumulated to ${new_db_balance:.2f}!")

# Clean up database
cur.execute("DELETE FROM stock_entry_items WHERE parent_id IN (SELECT id FROM stock_entries WHERE supplier = 'TEST SUPPLIER ACCUMULATE')")
cur.execute("DELETE FROM stock_entries WHERE supplier = 'TEST SUPPLIER ACCUMULATE'")
cur.execute("DELETE FROM suppliers WHERE id = ?", (sup_id,))
conn.commit()
conn.close()

print("All Supplier Balance Accumulation Integration Tests passed successfully!")
sys.exit(0)
