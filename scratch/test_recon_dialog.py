import sys, os
from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

app = QApplication.instance() or QApplication(sys.argv)

from views.dialogs.shift_reconciliation_dialog import ShiftReconciliationDialog

try:
    dlg = ShiftReconciliationDialog(cashier_id=1, cashier_name="James Madison")
    print("[SUCCESS] ShiftReconciliationDialog initialized cleanly.")
except Exception as e:
    import traceback
    print("[ERROR] ShiftReconciliationDialog failed to initialize:")
    traceback.print_exc()
