import sys
import os
sys.path.insert(0, r"c:\Users\DELL\New_POS\Havano_POS_2026")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

# Create app
app = QApplication(sys.argv)

from views.dialogs.purchase_invoice_dialog import PurchaseInvoiceDialog

print("Running inline search UI integration tests...")

# 1. Instantiate dialog
dialog = PurchaseInvoiceDialog()
print("Success: Dialog instantiated successfully!")

# 2. Check if table has a row and if it is the search row
row_count = dialog.table.rowCount()
print(f"Initial table rows: {row_count}")
assert row_count == 1, f"Expected exactly 1 row (search row), got {row_count}"

# 3. Verify the cell widget is our inline search QLineEdit
search_widget = dialog.table.cellWidget(0, 0)
assert search_widget is not None, "Cell widget at row 0 column 0 should not be None"
assert getattr(search_widget, "is_inline_search", False) is True, "Cell widget should be marked as is_inline_search"
print("Success: Inline search QLineEdit is correctly populated in the table!")

# 4. Check span of first row
span = dialog.table.columnSpan(0, 0)
assert span == 2, f"Expected column span to be 2, got {span}"
print("Success: Inline search row spans columns 0 and 1 correctly!")

# 5. Add a product and verify the product row is inserted BEFORE the search row
mock_product = {
    "id": 9999,
    "part_no": "TEST-123",
    "name": "Test Item Inline",
    "cost": 15.50,
    "price": 20.00,
    "uom": "Unit"
}

print("Adding test product...")
dialog.add_product(mock_product)

# The table should now have 2 rows: Product at row 0, and Search row at row 1
new_row_count = dialog.table.rowCount()
print(f"Table rows after adding product: {new_row_count}")
assert new_row_count == 2, f"Expected 2 rows after adding product, got {new_row_count}"

# Verify row 0 is the product
part_no_item = dialog.table.item(0, 0)
name_item = dialog.table.item(0, 1)
assert part_no_item.text() == "TEST-123", f"Expected part no 'TEST-123', got '{part_no_item.text()}'"
assert name_item.text() == "Test Item Inline", f"Expected name 'Test Item Inline', got '{name_item.text()}'"
print("Success: Real product row correctly added at index 0!")

# Verify row 1 is still the search row
shifted_widget = dialog.table.cellWidget(1, 0)
assert shifted_widget is not None, "Cell widget at row 1 column 0 should not be None"
assert getattr(shifted_widget, "is_inline_search", False) is True, "Search widget should shift down to row 1"
print("Success: Search row correctly shifted to the bottom (index 1)!")

print("All inline search UI tests passed successfully!")
sys.exit(0)
