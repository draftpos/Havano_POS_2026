import sys, os
sys.path.insert(0, os.path.abspath("."))
from PySide6.QtWidgets import QApplication
import utils.license_manager

# Mock read_license_key to return empty string (unlicensed)
utils.license_manager.read_license_key = lambda: ""

from views.dialogs.license_dialog import LicenseDialog

app = QApplication.instance() or QApplication(sys.argv)
dlg = LicenseDialog()
print("LicenseDialog initialized successfully.")
print(f"show_trial_button: {dlg._show_trial_button}")
assert dlg._show_trial_button == True, "Trial button must be shown when unlicensed!"
print("PASSED: Activate 30-Day Free Trial button is visible when unlicensed!")
