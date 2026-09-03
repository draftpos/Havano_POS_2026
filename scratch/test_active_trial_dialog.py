import sys, os
sys.path.insert(0, os.path.abspath("."))
from PySide6.QtWidgets import QApplication
import utils.license_manager

utils.license_manager.read_license_key = lambda: ""
utils.license_manager.get_trial_info = lambda: {"status": "Active", "days_remaining": 30}

from views.dialogs.license_dialog import LicenseDialog

app = QApplication.instance() or QApplication(sys.argv)
dlg = LicenseDialog()
print("Title:", dlg.title_lbl.text())
print("Status:", dlg.lbl_status.text())
print("Expiry:", dlg.lbl_expiry.text())

assert dlg.title_lbl.text() == "Free Trial Active"
assert "30 days" in dlg.lbl_expiry.text() or "30 Days" in dlg.btn_trial.text()
print("PASSED: LicenseDialog shows Free Trial Active status and remaining days!")
