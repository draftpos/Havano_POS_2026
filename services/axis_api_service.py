# services/axis_api_service.py

import requests
import threading
from dataclasses import dataclass
from typing import Optional, Any, List

from services.zimra_api_service import ApiResult

@dataclass
class AxisInvoiceResponse:
    """Response from Axis Virtual API"""
    qr_code: str
    verification_code: str
    device_id: str
    receipt_counter: int
    receipt_global_no: int
    device_serial: str = ""
    fiscal_day: str = ""
    
    @classmethod
    def from_dict(cls, data: dict) -> "AxisInvoiceResponse":
        return cls(
            qr_code=str(data.get("qrCode") or data.get("QRcode") or data.get("QRCode") or ""),
            verification_code=str(data.get("verificationCode") or data.get("VerificationCode") or ""),
            device_id=str(data.get("deviceId") or data.get("DeviceID") or ""),
            receipt_counter=int(data.get("receiptCounter") or data.get("ReceiptCounter") or 0),
            receipt_global_no=int(data.get("receiptGlobalNo") or data.get("ReceiptGlobalNo") or data.get("FDMSInvoiceNo") or 0),
            device_serial=str(data.get("DeviceSerialNumber") or data.get("deviceSerialNumber") or ""),
            fiscal_day=str(data.get("FiscalDayNo") or data.get("fiscalDayNo") or "")
        )

# Module-level lock
_axis_send_lock = threading.Lock()

class AxisApiService:
    """
    Axis Virtual API Wrapper.
    Uses JSON payloads and Bearer token authentication.
    """

    def _fetch_token(self, settings, session: requests.Session) -> tuple:
        login_url = f"{settings.base_url}/api/Auth/login"
        payload = {
            "email": settings.axis_email,
            "password": settings.axis_password
        }
        try:
            print("[Axis] Getting token...")
            resp = session.post(login_url, json=payload, timeout=30)
            if resp.status_code != 200:
                return False, f"Auth failed HTTP {resp.status_code}: {resp.text}"
            
            token_data = resp.json()
            token = token_data.get("token") or token_data.get("accessToken")
            if not token:
                # If the API returns the token directly as string or differently:
                if isinstance(token_data, str):
                    token = token_data
                else:
                    return False, f"No token in response: {token_data}"
            print("[Axis] Token obtained")
            return True, token
        except Exception as e:
            return False, f"Auth error: {e}"

    def get_token(self, settings) -> ApiResult:
        session = requests.Session()
        ok, result = self._fetch_token(settings, session)
        if ok:
            return ApiResult.success(result)
        return ApiResult.error(result)

    def ping_axis(self, settings) -> ApiResult:
        """Test connection and return device status"""
        session = requests.Session()
        ok, token = self._fetch_token(settings, session)
        if not ok:
            return ApiResult.error(token)

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        url = f"{settings.base_url}/api/VirtualDevice/GetConfig"
        try:
            resp = session.get(url, headers=headers, timeout=30)
            if resp.status_code == 200:
                return ApiResult.success(resp.json())
            return ApiResult.error(f"HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            return ApiResult.error(f"Ping error: {e}")

    def open_fiscal_day(self, settings) -> ApiResult:
        session = requests.Session()
        ok, token = self._fetch_token(settings, session)
        if not ok:
            return ApiResult.error(token)

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        url = f"{settings.base_url}/api/VirtualDevice/OpenFiscalDay"
        try:
            resp = session.get(url, headers=headers, timeout=30)
            if resp.status_code == 200:
                resp_data = resp.json()
                if str(resp_data.get("Code", "")) == "0" or str(resp_data.get("code", "")) == "0":
                    msg = resp_data.get("Message") or resp_data.get("message") or "Unknown API error"
                    if "already" in msg.lower(): # e.g. 'already open'
                        return ApiResult.success(resp_data)
                    return ApiResult.error(f"Axis API Rejected: {msg}")
                return ApiResult.success(resp_data)
            return ApiResult.error(f"HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            return ApiResult.error(f"Open Fiscal Day error: {e}")

    def close_fiscal_day(self, settings) -> ApiResult:
        session = requests.Session()
        ok, token = self._fetch_token(settings, session)
        if not ok:
            return ApiResult.error(token)

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        url = f"{settings.base_url}/api/VirtualDevice/CloseFiscalDay"
        try:
            resp = session.get(url, headers=headers, timeout=30)
            if resp.status_code == 200:
                resp_data = resp.json()
                if str(resp_data.get("Code", "")) == "0" or str(resp_data.get("code", "")) == "0":
                    msg = resp_data.get("Message") or resp_data.get("message") or "Unknown API error"
                    return ApiResult.error(f"Axis API Rejected: {msg}")
                return ApiResult.success(resp_data)
            return ApiResult.error(f"HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            return ApiResult.error(f"Close Fiscal Day error: {e}")

    def get_device_status(self, settings) -> ApiResult:
        session = requests.Session()
        ok, token = self._fetch_token(settings, session)
        if not ok:
            return ApiResult.error(token)

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        url = f"{settings.base_url}/api/VirtualDevice/GetStatus"
        try:
            resp = session.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                return ApiResult.success(resp.json())
            return ApiResult.error(f"HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            return ApiResult.error(f"Get Status error: {e}")

    def send_invoice(self, settings, invoice_number: str, currency: str,
                     customer_name: str, trade_name: str, fiscal_items: list,
                     **kwargs) -> ApiResult:
        with _axis_send_lock:
            invoice_flag = kwargs.get("invoice_flag", 0)
            original_invoice_no = kwargs.get("original_invoice_no", "")
            global_invoice_no = kwargs.get("global_invoice_no", "")
            tendered = float(kwargs.get("tendered", 0))

            session = requests.Session()
            ok, token = self._fetch_token(settings, session)
            if not ok:
                return ApiResult.error(token)

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            # Map the items to Axis payload format
            # Determine endpoint and receipt type
            if invoice_flag == 1 or invoice_flag == 3:  # Credit note
                url = f"{settings.base_url}/api/VirtualDevice/SubmitReceiptExt"
                receipt_type = "CreditNote"
            else:
                url = f"{settings.base_url}/api/VirtualDevice/SubmitReceipt"
                receipt_type = "FiscalInvoice"

            receipt_lines = []
            invoice_amount = 0.0
            invoice_tax_amount = 0.0
            
            # For Credit Notes, Axis expects negative values
            multiplier = -1.0 if receipt_type == "CreditNote" else 1.0

            for item in fiscal_items:
                receipt_lines.append({
                    "receiptLineType": "Sale",
                    "receiptLineNo": item.line_number,
                    "receiptLineHSCode": item.item_code,
                    "receiptLineName": item.item_name,
                    "receiptLinePrice": item.price,
                    "receiptLineQuantity": item.quantity * multiplier,
                    "receiptLineTotal": item.total * multiplier,
                    "taxCode": item.vat_name,
                    "taxPercent": item.vat_rate * 100
                })
                invoice_amount += (item.total * multiplier)
                invoice_tax_amount += (item.vat * multiplier)

            payload = {
                "receiptType": receipt_type,
                "receiptCurrency": currency,
                "invoiceNo": str(invoice_number),
                "referenceNumber": str(original_invoice_no) if original_invoice_no else str(invoice_number),
                "invoiceAmount": invoice_amount,
                "invoiceTaxAmount": invoice_tax_amount,
                "receiptNotes": "POS Sale",
                "receiptLinesTaxInclusive": True,
                "moneyTypeCode": "Cash",  # Defaulting, or can be dynamic
                "receiptPrintForm": "Receipt48",
                "buyerRegisterName": str(customer_name),
                "buyerTradeName": str(trade_name),
                "vatNumber": str(kwargs.get("buyer_vat", "")),
                "buyerTIN": str(kwargs.get("buyer_tin", "")),
                "buyerPhoneNo": str(kwargs.get("buyer_phone", "")),
                "buyerEmail": str(kwargs.get("buyer_email", "")),
                "buyerProvince": str(kwargs.get("buyer_province", "")),
                "buyerStreet": str(kwargs.get("buyer_street", "")),
                "buyerHouseNo": str(kwargs.get("buyer_house_no", "")),
                "buyerCity": str(kwargs.get("buyer_city", "")),
                "receiptLines": receipt_lines
            }
            
            receipt_date = kwargs.get("receipt_date", "")
            if receipt_date:
                payload["receiptDate"] = receipt_date
            
            if receipt_type == "CreditNote":
                payload["refReceiptGlobalnumber"] = str(global_invoice_no)
                
                # Fetch current DeviceID and FiscalDayNo via GetStatus to satisfy Axis requirements
                try:
                    status_url = f"{settings.base_url}/api/VirtualDevice/GetStatus"
                    status_resp = session.get(status_url, headers=headers, timeout=10)
                    if status_resp.status_code == 200:
                        status_data = status_resp.json()
                        payload["refDeviceID"] = str(status_data.get("DeviceID", status_data.get("deviceId", "")))
                        payload["refFiscalDay"] = str(status_data.get("FiscalDayNo", status_data.get("fiscalDayNo", "")))
                        
                        # Fallback if GetStatus doesn't return them directly
                        if not payload["refDeviceID"] and "Data" in status_data:
                            payload["refDeviceID"] = str(status_data["Data"].get("DeviceID", ""))
                        if not payload["refFiscalDay"] and "Data" in status_data:
                            payload["refFiscalDay"] = str(status_data["Data"].get("FiscalDayNo", ""))
                except Exception as e:
                    print(f"[Axis] Failed to get device status for credit note: {e}")
                    
                # Hard fallback just in case
                if not payload.get("refDeviceID"):
                    payload["refDeviceID"] = "21890"  # Fallback to known development device ID
                if not payload.get("refFiscalDay"):
                    payload["refFiscalDay"] = "445"   # Fallback to known fiscal day

            print("\n" + "="*60)
            print("AXIS API PAYLOAD:")
            print("="*60)
            import json
            print(json.dumps(payload, indent=4))
            print("="*60 + "\n")

            url = f"{settings.base_url}/api/VirtualDevice/SubmitReceipt"
            print(f"[Axis] Sending invoice: {invoice_number} to {url}")
            
            try:
                response = session.post(url, json=payload, headers=headers, timeout=60)
                print(f"[Axis] Response status: {response.status_code}")
                
                if response.status_code != 200:
                    return ApiResult.error(f"HTTP {response.status_code}: {response.text}")
                    
                resp_data = response.json()
                print(f"[Axis] Parsed response: {resp_data}")

                # Axis often wraps errors in a 200 OK with Code="0"
                code_val = str(resp_data.get("Code", ""))
                if code_val == "0" or str(resp_data.get("code", "")) == "0":
                    msg = resp_data.get("Message") or resp_data.get("message") or "Unknown API error"
                    return ApiResult.error(f"Axis API Rejected: {msg}")

                # Format assumption based on typical Axis API, mapping back to our generic format
                if resp_data.get("QRcode") or resp_data.get("QRCode") or resp_data.get("qrCode") or resp_data.get("receiptGlobalNo") or resp_data.get("ReceiptGlobalNo") or resp_data.get("FDMSInvoiceNo"):
                    return ApiResult.success(AxisInvoiceResponse.from_dict(resp_data))
                
                # Check for wrapped structure
                if "data" in resp_data:
                    return ApiResult.success(AxisInvoiceResponse.from_dict(resp_data["data"]))
                elif "Data" in resp_data and isinstance(resp_data["Data"], dict):
                    return ApiResult.success(AxisInvoiceResponse.from_dict(resp_data["Data"]))

                return ApiResult.error(f"Unrecognized response format: {resp_data}")

            except Exception as e:
                return ApiResult.error(str(e))

_axis_api_service: Optional["AxisApiService"] = None

def get_axis_api_service() -> AxisApiService:
    global _axis_api_service
    if _axis_api_service is None:
        _axis_api_service = AxisApiService()
    return _axis_api_service
