import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import json
from services.havano_zimra_offline_service import get_havano_zimra_offline_service
from services.fiscalization_service import FiscalInvoiceItem

def run_tests():
    print("=== Testing HavanoZimra Offline Extension ===")
    service = get_havano_zimra_offline_service()

    # 1. Ping
    ping_res = service.ping_device()
    print("1. Ping Result:", ping_res.is_success)
    assert ping_res.is_success, f"Ping failed: {ping_res.error}"
    print("   Ping Data:", ping_res.data)

    # 2. Build Fiscal Items XML using POS standard logic
    item1 = FiscalInvoiceItem(
        line_number=1,
        item_code="99999999",
        item_name="Mineral Water 500ml",
        item_name2="Mineral Water 500ml",
        quantity=2.0,
        price=1.0,
        total=2.0,
        vat=0.26,
        vat_rate=0.15,
        vat_name="VAT"
    )
    items_xml = FiscalInvoiceItem.build_items_xml([item1])
    print("2. Generated items XML:\n", items_xml)

    # 3. Send Sale Invoice
    inv_res = service.send_invoice(
        settings=None,
        invoice_number="INV-TEST-001",
        currency="USD",
        customer_name="Cash Customer",
        trade_name="Cash Customer",
        items_xml=items_xml,
        tendered=2.0
    )
    print("3. Sale Invoice Result:", inv_res.is_success)
    assert inv_res.is_success, f"Invoice signing failed: {inv_res.error}"
    fd = inv_res.data
    print(f"   Message: {fd.message}")
    print(f"   QR Code: {fd.qr_code}")
    print(f"   Verification Code: {fd.verification_code}")
    print(f"   Device ID: {fd.device_id}")
    print(f"   Receipt Type: {fd.receipt_type}")
    print(f"   Global No: {fd.receipt_global_no}")
    print(f"   Counter: {fd.receipt_counter}")
    assert fd.receipt_global_no > 0
    assert fd.receipt_counter > 0
    assert len(fd.verification_code) > 0

    first_global = fd.receipt_global_no

    # 4. Send Credit Note
    cn_res = service.send_invoice(
        settings=None,
        invoice_number="CN-TEST-001",
        currency="USD",
        customer_name="Cash Customer",
        trade_name="Cash Customer",
        items_xml=items_xml,
        invoice_flag=1,
        original_invoice_no="INV-TEST-001",
        global_invoice_no=first_global,
        tendered=2.0
    )
    print("4. Credit Note Result:", cn_res.is_success)
    assert cn_res.is_success, f"Credit note signing failed: {cn_res.error}"
    cn_fd = cn_res.data
    print(f"   CN Receipt Type: {cn_fd.receipt_type}")
    print(f"   CN Global No: {cn_fd.receipt_global_no}")
    print(f"   CN Counter: {cn_fd.receipt_counter}")
    assert cn_fd.receipt_global_no == first_global + 1
    assert cn_fd.receipt_counter == fd.receipt_counter + 1

    print("\n=== ALL TESTS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    run_tests()
