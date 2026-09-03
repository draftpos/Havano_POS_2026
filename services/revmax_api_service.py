# services/revmax_api_service.py

import requests
import threading
from typing import Optional, List, Any
from dataclasses import dataclass
import json

from services.zimra_api_service import ApiResult, FiscalInvoiceResponse
from models.fiscal_settings import FiscalSettings

_revmax_send_lock = threading.Lock()

class RevmaxApiService:
    """
    Revmax Hardware Integration API Wrapper.
    """
    
    def ping_revmax(self, settings: FiscalSettings) -> ApiResult:
        """
        Tests the connection to the Revmax server by calling GetDayStatus.
        """
        if not settings.base_url:
            return ApiResult.error("Base URL is required for Revmax.")
            
        url = f"{settings.base_url.rstrip('/')}/api/RevmaxAPI/GetDayStatus"
        try:
            headers = {"Accept": "application/json"}
            resp = requests.get(url, headers=headers, timeout=10)
            
            if resp.status_code == 200:
                return ApiResult.success(resp.json())
            return ApiResult.error(f"HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            return ApiResult.error(f"Ping error: {e}")

    def send_invoice(self, settings: FiscalSettings, invoice_number: str, currency: str,
                     customer_name: str, trade_name: str, fiscal_items: List[Any],
                     tendered: float, **kwargs) -> ApiResult:
        """
        Sends an invoice or credit note to the Revmax TransactM endpoint.
        """
        with _revmax_send_lock:
            if not settings.base_url:
                return ApiResult.error("Base URL is missing for Revmax provider.")

            raw_flag = kwargs.get("invoice_flag", 0)
            original_invoice_no = kwargs.get("original_invoice_no", "")
            global_invoice_no = kwargs.get("global_invoice_no", "")
            
            # Revmax expects the local original invoice number, NOT the global one
            revmax_orig_no = str(original_invoice_no)
            
            if str(raw_flag) == "0":
                istatus = "01"
            elif str(raw_flag) in ("1", "3"):
                istatus = "02"
            else:
                istatus = "01"
            
            # Map items to Revmax JSON array
            items_xml = []
            invoice_amount = 0.0
            invoice_tax_amount = 0.0
            
            for item in fiscal_items:
                # Using the FiscalInvoiceItem attributes from fiscalization_service
                items_xml.append({
                    "HH": str(item.line_number),
                    "ITEMCODE": str(item.item_code),
                    "ITEMNAME1": str(item.item_name)[:100],
                    "ITEMNAME2": str(item.item_name2)[:100],
                    "QTY": f"{item.quantity:.2f}",
                    "PRICE": f"{item.price:.2f}",
                    "AMT": f"{item.total:.2f}",
                    "TAX": f"{item.vat:.2f}",
                    "TAXR": f"{item.vat_rate:.3f}"
                })
                invoice_amount += item.total
                invoice_tax_amount += item.vat
            
            # Currencies structure
            currencies_xml = [{
                "Name": str(currency),
                "Amount": f"{tendered:.2f}",
                "Rate": "1.00"
            }]
            
            address_parts = [
                str(kwargs.get("buyer_house_no", "")).strip(),
                str(kwargs.get("buyer_street", "")).strip(),
                str(kwargs.get("buyer_city", "")).strip(),
                str(kwargs.get("buyer_province", "")).strip()
            ]
            customer_address = ", ".join([p for p in address_parts if p])

            # Build TransactM payload
            payload = {
                "Currency": str(currency),
                "BranchName": "",
                "InvoiceNumber": str(invoice_number),
                "OriginalInvoiceNumber": revmax_orig_no,
                "CustomerName": str(customer_name),
                "CustomerVatNumber": str(kwargs.get("buyer_vat", "")),
                "CustomerAddress": customer_address,
                "CustomerTelephone": str(kwargs.get("buyer_phone", "")),
                "CustomerEmail": str(kwargs.get("buyer_email", "")),
                "CustomerBPN": str(kwargs.get("buyer_tin", "")),
                "InvoiceAmount": f"{invoice_amount:.2f}",
                "InvoiceTaxAmount": f"{invoice_tax_amount:.2f}",
                "Istatus": istatus,
                "Cashier": "Admin",  # Could be passed via kwargs if needed
                "InvoiceComment": "Standard Sale",
                "ItemsXml": items_xml,
                "CurrenciesXml": currencies_xml
            }
            
            url = f"{settings.base_url.rstrip('/')}/api/RevmaxAPI/TransactM"
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
            
            print(f"[REVMAX] Sending TransactM payload to {url}:")
            print(json.dumps(payload, indent=2))
            
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=60)
                print(f"[REVMAX] Response {resp.status_code}: {resp.text}")
                
                if resp.status_code != 200:
                    return ApiResult.error(f"HTTP {resp.status_code}: {resp.text}")
                
                resp_data = resp.json()
                
                # Assume Revmax returns QRcode and VerificationCode fields upon success
                # e.g., {"QRcode": "...", "VerificationCode": "...", "Message": "Success"}
                qr_code = resp_data.get("QRcode", resp_data.get("qrcode", ""))
                v_code = resp_data.get("VerificationCode", resp_data.get("verificationcode", ""))
                msg = resp_data.get("Message", resp_data.get("message", ""))
                
                if not qr_code and "success" not in str(msg).lower():
                    return ApiResult.error(f"Revmax Error: {msg or resp_data}")
                
                receipt_data = resp_data.get("Data", {})
                if isinstance(receipt_data, dict) and "receipt" in receipt_data:
                    receipt_data = receipt_data["receipt"]
                elif isinstance(receipt_data, str) and receipt_data:
                    try:
                        parsed_data = json.loads(receipt_data)
                        if isinstance(parsed_data, dict) and "receipt" in parsed_data:
                            receipt_data = parsed_data["receipt"]
                        else:
                            receipt_data = parsed_data
                    except Exception:
                        receipt_data = {}
                else:
                    receipt_data = {}

                # Wrap response in standard FiscalInvoiceResponse
                fiscal_resp = FiscalInvoiceResponse(
                    message=str(msg),
                    qr_code=str(qr_code),
                    verification_code=str(v_code),
                    device_id=str(resp_data.get("DeviceID", "")),
                    fiscal_day=str(resp_data.get("FiscalDay", "")),
                    receipt_type=str(receipt_data.get("receiptType", "")),
                    receipt_currency=str(receipt_data.get("receiptCurrency", "")),
                    receipt_counter=int(receipt_data.get("receiptCounter", 0) or 0),
                    receipt_global_no=int(receipt_data.get("receiptGlobalNo", 0) or 0),
                    efd_serial=str(resp_data.get("DeviceSerialNumber", ""))
                )
                
                return ApiResult.success(fiscal_resp)
                
            except Exception as e:
                return ApiResult.error(str(e))

    def close_fiscal_day(self, settings: FiscalSettings) -> ApiResult:
        """
        Closes the fiscal day by calling the ZReport endpoint.
        """
        if not settings.base_url:
            return ApiResult.error("Base URL is missing for Revmax provider.")
            
        url = f"{settings.base_url.rstrip('/')}/api/RevmaxAPI/ZReport"
        try:
            headers = {"Accept": "application/json"}
            resp = requests.get(url, headers=headers, timeout=30)
            
            if resp.status_code == 200:
                return ApiResult.success(resp.json())
            return ApiResult.error(f"HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            return ApiResult.error(f"ZReport error: {e}")

_revmax_api_service: Optional["RevmaxApiService"] = None

def get_revmax_api_service() -> RevmaxApiService:
    global _revmax_api_service
    if _revmax_api_service is None:
        _revmax_api_service = RevmaxApiService()
    return _revmax_api_service
