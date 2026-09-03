import sys, os
from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

app = QApplication.instance() or QApplication(sys.argv)

from views.dialogs.payment_dialog import PaymentDialog, _get_local_rate

print("Testing _get_local_rate normalization:")
print("  ZIG -> USD:", _get_local_rate("ZIG", "USD"))
print("  USD -> ZIG:", _get_local_rate("USD", "ZIG"))
print("  ZAR -> USD:", _get_local_rate("ZAR", "USD"))
print("  USD -> ZAR:", _get_local_rate("USD", "ZAR"))
print("  AMD -> USD:", _get_local_rate("AMD", "USD"))
print("  USD -> AMD:", _get_local_rate("USD", "AMD"))

try:
    dlg = PaymentDialog(total=50.0, items=[], cashier_id=1)
    print("\n[SUCCESS] PaymentDialog initialized cleanly with all currencies.")
except Exception as e:
    import traceback
    print("[ERROR] PaymentDialog failed to initialize:")
    traceback.print_exc()
