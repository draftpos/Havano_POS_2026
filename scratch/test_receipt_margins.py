import sys
import os
sys.path.insert(0, r"c:\Users\DELL\New_POS\Havano_POS_2026")

from PySide6.QtWidgets import QApplication

# Create application instance
app = QApplication(sys.argv)

from services.printing_service import PrintingService
from models.receipt import ReceiptData

print("Instantiating PrintingService...")
ps = PrintingService()
assert ps is not None
print("Success: PrintingService instantiated successfully!")

print("Creating dummy ReceiptData to check structure...")
dummy = ReceiptData(
    companyName="Test Company",
    companyAddress="123 Test Street",
    invoiceNo="INV-0001",
    grandTotal=100.0,
    items=[]
)
assert dummy.companyName == "Test Company"
print("Success: Dummy ReceiptData prepared successfully!")

print("All printing service setup tests completed successfully!")
sys.exit(0)
