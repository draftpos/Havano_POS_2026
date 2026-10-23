import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.a4_invoice_service import render_a4_invoice_html
from models.receipt import ReceiptData, Item

def test_a4_invoice_with_customer_details():
    # 1. Test A4 Sales Invoice with customer details explicitly enabled
    invoice = {
        "invoice_no": "INV-2026-TEST-001",
        "invoice_date": "2026-10-14",
        "customer_name": "Mega Wholesale Pvt Ltd",
        "customer_phone": "+263 77 111 2222",
        "customer_email": "accounts@megawholesale.co.zw",
        "customer_address": "45 Robert Mugabe Way, Harare",
        "customer_tin": "2000998877",
        "customer_vat": "100554433",
        "total": 250.00,
        "subtotal": 217.39,
        "total_vat": 32.61,
        "currency": "USD",
        "print_customer_details": True,
        "items": [
            {"product_name": "Test Item 1", "qty": 2, "price": 100.0, "total": 200.0, "tax_amount": 26.09},
            {"product_name": "Test Item 2", "qty": 1, "price": 50.0, "total": 50.0, "tax_amount": 6.52},
        ]
    }

    html = render_a4_invoice_html(invoice)
    print("Testing A4 Invoice with print_customer_details=True...")
    assert "Mega Wholesale Pvt Ltd" in html, "Customer Name missing"
    assert "+263 77 111 2222" in html, "Customer Phone missing"
    assert "accounts@megawholesale.co.zw" in html, "Customer Email missing"
    assert "45 Robert Mugabe Way, Harare" in html, "Customer Address missing"
    assert "2000998877" in html, "Customer TIN missing"
    assert "100554433" in html, "Customer VAT missing"
    print("[OK] A4 Sales Invoice with customer details passed!")

def test_a4_credit_note_with_customer_details():
    # 2. Test A4 Credit Note with customer details explicitly enabled
    cn_receipt = ReceiptData(
        doc_type="credit_note",
        invoiceNo="CRN-2026-TEST-002",
        invoiceDate="2026-10-14",
        cashierName="Admin",
        customerName="Delta Beverages Ltd",
        customerContact="+263 71 999 8888",
        customerEmail="finance@delta.co.zw",
        customeraddress="Stand 104, Southerton, Harare",
        customerTin="2000123456",
        customerVat="10098765",
        grandTotal=145.00,
        subtotal=126.09,
        totalVat=18.91,
        currency="USD",
        footer="Credit notes are valid for 90 days."
    )
    cn_receipt.originalInvoiceNo = "INV-2026-0482"
    cn_receipt.creditNoteReason = "Damaged packaging on delivery"
    cn_receipt.print_customer_details = True
    cn_receipt.items.append(Item(
        productName="Refined Sugar 2kg",
        productid="SUG-002",
        qty=20.0,
        price=5.00,
        amount=100.00,
        tax_amount=13.04
    ))
    cn_receipt.itemlist = cn_receipt.items

    html = render_a4_invoice_html(cn_receipt)
    print("Testing A4 Credit Note with print_customer_details=True...")
    assert "CREDIT NOTE" in html, "Document title CREDIT NOTE missing"
    assert "CRN-2026-TEST-002" in html, "Credit Note No missing"
    assert "INV-2026-0482" in html, "Orig Invoice missing"
    assert "Delta Beverages Ltd" in html, "Customer Name missing"
    assert "+263 71 999 8888" in html, "Customer Contact missing"
    assert "finance@delta.co.zw" in html, "Customer Email missing"
    assert "Stand 104, Southerton, Harare" in html, "Customer Address missing"
    assert "2000123456" in html, "Customer TIN missing"
    assert "10098765" in html, "Customer VAT missing"
    print("[OK] A4 Credit Note with customer details passed!")

def test_a4_invoice_without_customer_details():
    # 3. Test when print_customer_details is False
    invoice = {
        "invoice_no": "INV-2026-TEST-003",
        "invoice_date": "2026-10-14",
        "customer_name": "Basic Customer",
        "customer_phone": "+263 77 000 0000",
        "customer_email": "hidden@email.com",
        "customer_tin": "TIN_SHOULD_BE_HIDDEN",
        "customer_vat": "VAT_SHOULD_BE_HIDDEN",
        "total": 10.00,
        "currency": "USD",
        "print_customer_details": False,
        "items": []
    }
    html = render_a4_invoice_html(invoice)
    print("Testing A4 Invoice with print_customer_details=False...")
    assert "Basic Customer" in html
    assert "TIN_SHOULD_BE_HIDDEN" not in html, "TIN should be omitted when setting is False"
    assert "VAT_SHOULD_BE_HIDDEN" not in html, "VAT should be omitted when setting is False"
    assert "hidden@email.com" not in html, "Email should be omitted when setting is False"
    print("[OK] A4 Invoice without customer details passed!")

if __name__ == "__main__":
    test_a4_invoice_with_customer_details()
    test_a4_credit_note_with_customer_details()
    test_a4_invoice_without_customer_details()
    print("\n[ALL TESTS PASSED SUCCESSFULLY!]")
