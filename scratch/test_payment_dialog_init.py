import sys, os
from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

app = QApplication.instance() or QApplication(sys.argv)

from views.dialogs.payment_dialog import PaymentDialog

try:
    dlg = PaymentDialog(total=100.0, items=[], cashier_id=1)
    print("[SUCCESS] PaymentDialog initialized cleanly.")
    print("Methods loaded:", [m["label"] + " (" + m["currency"] + ")" for m in dlg._methods])
except Exception as e:
    import traceback
    print("[ERROR] PaymentDialog failed to initialize:")
    traceback.print_exc()
