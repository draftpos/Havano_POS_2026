import sys
import os
sys.path.insert(0, r"c:\Users\DELL\New_POS\Havano_POS_2026")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

# Create app
app = QApplication(sys.argv)

from views.dialogs.purchase_invoice_dialog import PurchaseInvoiceDialog, QuickAddSupplierDialog

print("Running New Supplier Flow integration tests...")

# 1. Test QuickAddSupplierDialog layout and field setup
dlg = QuickAddSupplierDialog()
assert dlg._f_name is not None
assert dlg._f_address is not None
assert dlg._f_phone is not None
print("Success: QuickAddSupplierDialog fields created correctly!")

# 2. Test PurchaseInvoiceDialog address read-only and stylesheet
pi_dlg = PurchaseInvoiceDialog()
assert pi_dlg.address_edit.isReadOnly() is True, "Address field must be read-only"
print("Success: PurchaseInvoiceDialog address field is correctly configured as read-only!")

# 3. Test balance/paid toggling logic
# Check defaults
assert pi_dlg.paid_checkbox.isChecked() is False, "By default the checkbox is unchecked (not paid)"
assert pi_dlg.balance_edit.isReadOnly() is False, "When not paid, balance should be editable"

# Add mock products to generate some grand total
mock_product = {
    "id": 8888,
    "part_no": "TEST-FLOW",
    "name": "Integration Test Product",
    "cost": 150.00,
    "price": 200.00,
    "uom": "Unit"
}
pi_dlg.add_product(mock_product)
pi_dlg._recalc_totals()

# Verify balance mirrors the grand total because it was not paid and not manually edited
grand_total = float(pi_dlg.lbl_grand_total.text().replace("$", ""))
balance = float(pi_dlg.balance_edit.text())
print(f"Grand Total: {grand_total}, Balance: {balance}")
assert grand_total == 150.00, f"Expected Grand Total to be 150.00, got {grand_total}"
assert balance == 150.00, f"Expected Balance to be 150.00, got {balance}"
print("Success: Balance starts exactly at the Grand Total when not paid!")

# Check that checking 'paid_checkbox' makes it 0.00 and read-only
pi_dlg.paid_checkbox.setChecked(True)
assert pi_dlg.balance_edit.text() == "0.00", "Checking paid should set balance to 0.00"
assert pi_dlg.balance_edit.isReadOnly() is True, "Checking paid should make balance read-only"
print("Success: Checking 'Mark as Paid' sets balance to 0.00 and locks it!")

# Uncheck paid and make sure it goes back to grand total
pi_dlg.paid_checkbox.setChecked(False)
assert pi_dlg.balance_edit.text() == "150.00", "Unchecking paid should restore balance to grand total"
assert pi_dlg.balance_edit.isReadOnly() is False, "Unchecking paid should unlock balance"
print("Success: Unchecking 'Mark as Paid' unlocks balance and restores grand total!")

# Test manual edit override protection
pi_dlg.balance_edit.setText("50.00")
pi_dlg._on_balance_edited() # Simulate manual typing signal trigger

# Add another product to increment grand total to 300.00
pi_dlg.add_product(mock_product)
pi_dlg._recalc_totals()

# Grand total should be 300.00, but manually typed balance should remain 50.00!
new_grand_total = float(pi_dlg.lbl_grand_total.text().replace("$", ""))
new_balance = float(pi_dlg.balance_edit.text())
print(f"New Grand Total: {new_grand_total}, New Balance (should be 50.00): {new_balance}")
assert new_grand_total == 300.00, f"Expected Grand Total to be 300.00, got {new_grand_total}"
assert new_balance == 50.00, f"Expected Balance to preserve manual 50.00, got {new_balance}"
print("Success: Manually typed balance is successfully preserved from automatic recalculations!")

print("All supplier and balance flow integration tests passed successfully!")
sys.exit(0)
