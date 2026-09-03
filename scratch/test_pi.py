import sys
import os
sys.path.insert(0, r"c:\Users\DELL\New_POS\Havano_POS_2026")

from PySide6.QtWidgets import QApplication

def test():
    app = QApplication([])
    print("QApplication created successfully")
    try:
        from views.dialogs.purchase_invoice_dialog import PurchaseInvoiceDialog
        from PySide6.QtWidgets import QMainWindow
        parent = QMainWindow()
        print("Imported PurchaseInvoiceDialog successfully")
        dlg = PurchaseInvoiceDialog(parent)
        print("Instantiated PurchaseInvoiceDialog with parent successfully")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test()
