import sys, os
from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

app = QApplication.instance() or QApplication(sys.argv)

from models.shift import get_shift_by_id
from views.dialogs.shift_reconciliation_dialog import ShiftReconciliationDialog

shift = get_shift_by_id(3)
if shift:
    dlg = ShiftReconciliationDialog(cashier_id=1, cashier_name="James Madison")
    dlg._active_shift = shift
    dlg._load_data()
    print("\n[SUCCESS] Loaded Shift #3 into ShiftReconciliationDialog cleanly.")
    print("Table Column Count:", dlg.table.columnCount())
    headers = [dlg.table.horizontalHeaderItem(c).text() for c in range(dlg.table.columnCount())]
    print("Headers:", headers)
    for r in range(dlg.table.rowCount()):
        m = dlg.table.item(r, 0).text()
        c = dlg.table.item(r, 1).text()
        exp = dlg.table.item(r, 2).text()
        var_nat = dlg.table.item(r, 4).text() if dlg.table.item(r, 4) else ""
        var_base = dlg.table.item(r, 5).text() if dlg.table.item(r, 5) else ""
        print(f"  Row {r}: {m} ({c}) | Exp: {exp} | Var Native: {var_nat} | Var Base: {var_base}")
    print("\nSummary Label Text:")
    print(dlg.summary_label.text())
