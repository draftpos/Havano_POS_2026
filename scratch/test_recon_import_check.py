import sys, os
from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

app = QApplication.instance() or QApplication(sys.argv)

from models.shift import get_shift_by_id
from views.dialogs.shift_reconciliation_dialog import ShiftReconciliationDialog

shift = get_shift_by_id(3)
if shift:
    dlg = ShiftReconciliationDialog(cashier_id=1, cashier_name="Admin")
    dlg._active_shift = shift
    dlg._load_data()
    print("\n[SUCCESS] ShiftReconciliationDialog initialized without any NameError.")
    print("Table columns:", dlg.table.columnCount())
    print("Base currency header:", dlg.table.horizontalHeaderItem(5).text())
