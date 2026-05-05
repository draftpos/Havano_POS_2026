"""
ZIMRA Fiscalization API - Python Test Script (v2 - fixed)
Run: python test_zimra.py

Fixes from v1:
  - global_invoice_no must be "0" not "" (server does int() on it)
  - Token is response["message"] as a plain string, not nested dict
  - Ping success = HTTP 200 + operationID present (no ResponseCode field)
  - Response fields: QRcode, VerificationCode, receiptCounter, receiptGlobalNo
"""

import requests
import json
from datetime import datetime

# =============================================================================
# CONFIG
# =============================================================================
BASE_URL   = "https://erpfiscal.havano.online"
API_KEY    = "105399628d8d243"
API_SECRET = "02d4fb4d0d22f09"
DEVICE_SN  = "EC-01"

TIMESTAMP  = datetime.now().strftime("%Y%m%d%H%M%S")
INVOICE_NO = f"TEST-{TIMESTAMP}"
CREDIT_NO  = f"CN-{TIMESTAMP}"

# =============================================================================
# HELPERS
# =============================================================================

def separator(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def pretty(data):
    print(json.dumps(data, indent=2))

def get_auth_headers(csrf_token=None):
    headers = {
        "Authorization": f"token {API_KEY}:{API_SECRET}",
        "Content-Type":  "application/x-www-form-urlencoded",
    }
    if csrf_token:
        headers["X-Frappe-CSRF-Token"] = csrf_token
    return headers

def build_items_xml(items):
    """
    items = list of dicts:
      { code, name, qty, price, total, vat, vat_rate, vat_name }
    vat_name options: VAT | ZERO RATED | EXEMPT
    Negative qty/total/vat for credit notes.
    """
    xml = "<ITEMS>"
    for i, item in enumerate(items, start=1):
        xml += (
            f"<ITEM>"
            f"<HH>{i}</HH>"
            f"<ITEMCODE>{item['code']}</ITEMCODE>"
            f"<ITEMNAME>{item['name']}</ITEMNAME>"
            f"<ITEMNAME2>{item['name']}</ITEMNAME2>"
            f"<QTY>{item['qty']}</QTY>"
            f"<PRICE>{item['price']:.2f}</PRICE>"
            f"<TOTAL>{item['total']:.2f}</TOTAL>"
            f"<VAT>{item['vat']:.2f}</VAT>"
            f"<VATR>{item['vat_rate']:.2f}</VATR>"
            f"<VNAME>{item['vat_name']}</VNAME>"
            f"</ITEM>"
        )
    xml += "</ITEMS>"
    return xml

def extract_fiscal_data(response_json):
    """
    Pull fiscal fields out of a successful response.
    Returns dict or None.
    Confirmed response shape:
      { "message": { "Message": "...", "QRcode": "...", "VerificationCode": "...",
                     "receiptCounter": 138, "receiptGlobalNo": 621, ... } }
    """
    msg = response_json.get("message", {})
    if not isinstance(msg, dict):
        return None
    if "QRcode" not in msg:
        return None
    return {
        "qr_code":           msg.get("QRcode", ""),
        "verification_code": msg.get("VerificationCode", ""),
        "receipt_counter":   msg.get("receiptCounter"),
        "receipt_global_no": msg.get("receiptGlobalNo"),
        "device_id":         msg.get("DeviceID", ""),
        "fiscal_day":        msg.get("FiscalDay", ""),
        "receipt_type":      msg.get("receiptType", ""),
        "efd_serial":        msg.get("EFDSERIAL", ""),
    }


# =============================================================================
# STEP 1: GET CSRF TOKEN
# =============================================================================

def step1_get_token():
    separator("STEP 1: Get CSRF Token")
    url = f"{BASE_URL}/api/method/havanozimracloud.api.token"

    resp = requests.post(url, headers=get_auth_headers())
    print(f"Status: {resp.status_code}")
    data = resp.json()
    pretty(data)

    # Token = response["message"] as a plain string
    token = data.get("message") if isinstance(data.get("message"), str) else None

    if token:
        print(f"\n✅ CSRF Token: {token}")
    else:
        print("\n❌ Could not extract token")
    return token


# =============================================================================
# STEP 2: PING ZIMRA
# =============================================================================

def step2_ping(csrf_token):
    separator("STEP 2: Ping ZIMRA Server")
    url = f"{BASE_URL}/api/method/havanozimracloud.api.pingzimra"

    resp = requests.post(
        url,
        headers=get_auth_headers(csrf_token),
        data={"device_sn": DEVICE_SN},
    )
    print(f"Status: {resp.status_code}")
    data = resp.json()
    pretty(data)

    # Success = HTTP 200 + operationID in message (no ResponseCode field)
    msg = data.get("message", {})
    if resp.status_code == 200 and isinstance(msg, dict) and "operationID" in msg:
        print(f"\n✅ Ping successful — EC-01 is reachable")
        print(f"   operationID:        {msg.get('operationID')}")
        print(f"   reportingFrequency: {msg.get('reportingFrequency')}")
    else:
        print(f"\n⚠️  Unexpected ping response")

    return resp.status_code == 200


# =============================================================================
# STEP 3: SEND NORMAL INVOICE
# =============================================================================

def step3_send_invoice(csrf_token):
    separator("STEP 3: Send Invoice")
    url = f"{BASE_URL}/api/method/havanozimracloud.api.sendinvoice"

    items = [
        {
            "code": "99001868", "name": "Milo",
            "qty": 1, "price": 6.10, "total": 6.10,
            "vat": 0.80, "vat_rate": 0.15, "vat_name": "VAT",
        },
        {
            "code": "99002638", "name": "Dano Refill",
            "qty": 1, "price": 5.10, "total": 5.10,
            "vat": 0.00, "vat_rate": 0.00, "vat_name": "ZERO RATED",
        },
    ]

    payload = {
        "device_sn":                 DEVICE_SN,
        "add_customer":              "0",
        "invoice_flag":              "1",
        "currency":                  "USD",
        "invoice_number":            INVOICE_NO,
        "customer_name":             "Default",
        "trade_name":                "",
        "customer_vat_number":       "",
        "customer_address":          "",
        "customer_telephone_number": "",
        "customer_tin":              "",
        "customer_province":         "",
        "customer_street":           "",
        "customer_houseNo":          "",
        "customer_city":             "",
        "customer_email":            "",
        "invoice_comment":           "Test from Python script",
        "original_invoice_no":       "",
        "global_invoice_no":         "0",    # FIX: must be "0" not "" (server does int() on this)
        "items_xml":                 build_items_xml(items),
    }

    print(f"Invoice Number: {INVOICE_NO}")
    print(f"Items XML:\n{payload['items_xml']}\n")

    resp = requests.post(url, headers=get_auth_headers(csrf_token), data=payload)
    print(f"Status: {resp.status_code}")
    data = resp.json()
    pretty(data)

    fiscal = extract_fiscal_data(data)
    if fiscal:
        print("\n✅ Invoice fiscalized successfully!")
        print(f"   QR Code:           {fiscal['qr_code']}")
        print(f"   Verification Code: {fiscal['verification_code']}")
        print(f"   Receipt Counter:   {fiscal['receipt_counter']}")
        print(f"   Global No:         {fiscal['receipt_global_no']}")
    else:
        print(f"\n❌ Invoice failed — see response above")

    return fiscal


# =============================================================================
# STEP 4: SEND CREDIT NOTE
# =============================================================================

def step4_send_credit_note(csrf_token, original_invoice_no=None):
    separator("STEP 4: Send Credit Note (Return)")
    url = f"{BASE_URL}/api/method/havanozimracloud.api.sendinvoice"

    original = original_invoice_no or INVOICE_NO

    items = [
        {
            "code": "99001868", "name": "Milo",
            "qty": -1, "price": 6.10, "total": -6.10,
            "vat": -0.80, "vat_rate": 0.15, "vat_name": "VAT",
        },
    ]

    payload = {
        "device_sn":                 DEVICE_SN,
        "add_customer":              "0",
        "invoice_flag":              "3",       # 3 = credit note / return
        "currency":                  "USD",
        "invoice_number":            CREDIT_NO,
        "customer_name":             "Walk-in Customer",
        "trade_name":                "",
        "customer_vat_number":       "",
        "customer_address":          "",
        "customer_telephone_number": "",
        "customer_tin":              "",
        "customer_province":         "",
        "customer_street":           "",
        "customer_houseNo":          "",
        "customer_city":             "",
        "customer_email":            "",
        "invoice_comment":           "Customer return",
        "original_invoice_no":       original,
        "global_invoice_no":         "0",       # same fix
        "items_xml":                 build_items_xml(items),
    }

    print(f"Credit Note Number: {CREDIT_NO}")
    print(f"Original Invoice:   {original}")
    print(f"Items XML:\n{payload['items_xml']}\n")

    resp = requests.post(url, headers=get_auth_headers(csrf_token), data=payload)
    print(f"Status: {resp.status_code}")
    data = resp.json()
    pretty(data)

    fiscal = extract_fiscal_data(data)
    if fiscal:
        print("\n✅ Credit note fiscalized successfully!")
        print(f"   QR Code:           {fiscal['qr_code']}")
        print(f"   Verification Code: {fiscal['verification_code']}")
        print(f"   Receipt Counter:   {fiscal['receipt_counter']}")
        print(f"   Global No:         {fiscal['receipt_global_no']}")
    else:
        print(f"\n❌ Credit note failed — see response above")

    return fiscal


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print(f"\n🚀 ZIMRA API Test v2  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Base URL:  {BASE_URL}")
    print(f"   Device:    {DEVICE_SN}")
    print(f"   Invoice:   {INVOICE_NO}")
    print(f"   Credit:    {CREDIT_NO}")

    # Step 1
    csrf_token = step1_get_token()
    if not csrf_token:
        print("\n❌ Cannot continue without CSRF token.")
        exit(1)

    # Step 2
    step2_ping(csrf_token)

    # Step 3
    invoice_fiscal = step3_send_invoice(csrf_token)

    # Step 4
    step4_send_credit_note(csrf_token, original_invoice_no=INVOICE_NO)

    separator("SUMMARY")
    print(f"Invoice No:  {INVOICE_NO}")
    print(f"Credit No:   {CREDIT_NO}")
    if invoice_fiscal:
        print(f"Invoice QR:  {invoice_fiscal['qr_code']}")
        print(f"Invoice VC:  {invoice_fiscal['verification_code']}")
    print()