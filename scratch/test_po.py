import sys
import os
sys.path.insert(0, r"c:\Users\DELL\New_POS\Havano_POS_2026")

from PySide6.QtWidgets import QApplication

# Create application instance
app = QApplication(sys.argv)
print("QApplication created successfully")

from views.dialogs.purchase_order_dialog import PurchaseOrderDialog
print("Imported PurchaseOrderDialog successfully")

# Instantiate dialog
print("Instantiating PurchaseOrderDialog...")
dialog = PurchaseOrderDialog()
assert dialog is not None
print("Success: PurchaseOrderDialog instantiated successfully!")

# Verify layout items
print("Checking UI widgets...")
assert hasattr(dialog, "table")
assert dialog.table.columnCount() == 9
assert hasattr(dialog, "inline_search_edit")
assert hasattr(dialog, "sup_combo")
assert hasattr(dialog, "wh_combo")
assert hasattr(dialog, "cc_combo")
print("Success: Redesigned UI widgets verified successfully!")

print("All redesigned purchase order dialog tests passed successfully!")
sys.exit(0)
