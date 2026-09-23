import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.a4_invoice_service import render_a4_invoice_html
from models.receipt import ReceiptData, Item

cn_receipt = ReceiptData(
    doc_type="credit_note",
    companyName="Havano Technologies (Pvt) Ltd",
    companyAddress="123 Samora Machel Ave",
    companyAddressLine1="Harare, Zimbabwe",
    companyEmail="sales@havano.cloud",
    tel="+263 77 123 4567",
    tin="2000123456",
    vatNo="10098765",
    invoiceNo="CRN-2026-0012",
    invoiceDate="2026-09-11",
    cashierName="Tendai (Admin)",
    customerName="Delta Beverages Ltd",
    customerContact="+263 71 999 8888",
    grandTotal=145.00,
    subtotal=126.09,
    totalVat=18.91,
    currency="USD",
    footer="Credit notes are valid for 90 days. Thank you for your business."
)
cn_receipt.originalInvoiceNo = "INV-2026-0482"
cn_receipt.creditNoteReason = "Damaged packaging on delivery"
cn_receipt.items.append(Item(
    productName="Refined Sugar 2kg",
    productid="SUG-002",
    qty=20.0,
    price=5.00,
    amount=100.00,
    tax_amount=13.04
))
cn_receipt.items.append(Item(
    productName="Cooking Oil 2L",
    productid="OIL-002",
    qty=10.0,
    price=4.50,
    amount=45.00,
    tax_amount=5.87
))
cn_receipt.itemlist = cn_receipt.items

html = render_a4_invoice_html(cn_receipt)
print("HTML Generated successfully! Length:", len(html))
assert "CREDIT NOTE" in html
assert "CRN-2026-0012" in html
assert "INV-2026-0482" in html
assert "Damaged packaging on delivery" in html
assert "TOTAL CREDIT (Incl. Tax)" in html
assert "Qty Returned" in html
print("[SUCCESS] All Credit Note A4 assertions passed!")
