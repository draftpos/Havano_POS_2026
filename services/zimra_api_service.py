# services/zimra_api_service.py

import requests
import threading
from dataclasses import dataclass
from typing import Optional, Any, List
import xml.etree.ElementTree as ET


@dataclass
class ApiResult:
    is_success: bool
    data: Any = None
    error: Optional[str] = None

    @classmethod
    def success(cls, data):
        return cls(is_success=True, data=data)

    @classmethod
    def error(cls, error_msg):
        return cls(is_success=False, error=error_msg)


@dataclass
class FiscalInvoiceResponse:
    """Response from ZIMRA API - matches Postman response"""
    message: str
    qr_code: str
    verification_code: str
    device_id: str
    fiscal_day: str
    receipt_type: str
    receipt_currency: str
    receipt_counter: int
    receipt_global_no: int
    efd_serial: str

    @classmethod
    def from_dict(cls, data: dict) -> "FiscalInvoiceResponse":
        msg = data.get("message", data)

        if isinstance(msg, str):
            return cls(
                message=msg,
                qr_code="",
                verification_code="",
                device_id="",
                fiscal_day="",
                receipt_type="",
                receipt_currency="",
                receipt_counter=0,
                receipt_global_no=0,
                efd_serial=""
            )

        return cls(
            message=str(msg.get("Message", "")),
            qr_code=str(msg.get("QRcode", "")),
            verification_code=str(msg.get("VerificationCode", "")),
            device_id=str(msg.get("DeviceID", "")),
            fiscal_day=str(msg.get("FiscalDay", "")),
            receipt_type=str(msg.get("receiptType", "")),
            receipt_currency=str(msg.get("receiptCurrency", "")),
            receipt_counter=int(msg.get("receiptCounter", 0)),
            receipt_global_no=int(msg.get("receiptGlobalNo", 0)),
            efd_serial=str(msg.get("EFDSERIAL", ""))
        )


# Module-level lock — shared across ALL instances and ALL threads
_send_lock = threading.Lock()


class ZimraApiService:
    """
    Stateless ZIMRA API wrapper.
    Every send_invoice call gets its own fresh session + token,
    exactly like the working test_simple_invoice.py script.
    Module-level lock ensures concurrent sales never interleave.
    """

    def _fetch_token(self, settings, session: requests.Session) -> tuple:
        """
        Internal helper — fetches a fresh CSRF token.
        Returns (True, csrf_token) on success, (False, error_message) on failure.
        Shared by both get_token() and send_invoice() to avoid duplication.
        """
        token_url = f"{settings.base_url}/api/method/havanozimracloud.api.token"
        try:
            print(f"[ZIMRA] Getting token...")
            token_resp = session.post(token_url, timeout=30)
            if token_resp.status_code != 200:
                return False, f"Token request failed HTTP {token_resp.status_code}: {token_resp.text}"
            token_data = token_resp.json()
            csrf_token = token_data.get("token") or token_data.get("message")
            if not csrf_token:
                return False, f"No token in response: {token_data}"
            print(f"[ZIMRA] Token obtained")
            return True, csrf_token
        except Exception as e:
            return False, f"Token error: {e}"

    def get_token(self, settings) -> ApiResult:
        """
        Public method used by Device Monitor for ping / health checks.
        Fetches a fresh token and returns it wrapped in ApiResult.
        """
        session = requests.Session()
        ok, result = self._fetch_token(settings, session)
        if ok:
            return ApiResult.success(result)
        return ApiResult.error(result)

    def send_invoice(self, settings, invoice_number: str, currency: str,
                     customer_name: str, trade_name: str, items_xml: str,
                     **kwargs) -> ApiResult:
        """
        Send a single invoice to ZIMRA.
        Always fetches a fresh token and uses a brand-new session.
        Serialised via module-level lock so two threads cannot interleave.

        kwargs accepted:
          invoice_flag        (int)   — 0=normal sale, 3=credit note  (default: 0)
          original_invoice_no (str)   — original invoice number for credit notes (default: "")
          global_invoice_no   (str)   — original fiscal global number for credit notes (default: "")
          tendered            (float) — payment amount; negative for credit notes (default: 0)
        """
        with _send_lock:
            # ── Read optional kwargs ──────────────────────────────────────────
            invoice_flag        = kwargs.get("invoice_flag", 0)
            original_invoice_no = kwargs.get("original_invoice_no", "")
            global_invoice_no   = kwargs.get("global_invoice_no", "")
            tendered            = float(kwargs.get("tendered", 0))

            # ── 1. Fresh session per call ──
            session = requests.Session()

            # ── 2. Fresh token via shared helper ──
            ok, result = self._fetch_token(settings, session)
            if not ok:
                return ApiResult.error(result)
            csrf_token = result

            # ── 3. Send invoice ──
            invoice_url = f"{settings.base_url}/api/method/havanozimracloud.api.sendinvoice"

            headers = {
                "X-Frappe-CSRF-Token": csrf_token,
                "Authorization": f"token {settings.api_key}:{settings.api_secret}",
                "Content-Type": "application/x-www-form-urlencoded",
            }

            data = {
                "device_sn":                str(settings.device_sn),
                "add_customer":             "0",
                "invoice_flag":             str(invoice_flag),
                "currency":                 str(currency),
                "invoice_number":           str(invoice_number),
                "customer_name":            str(customer_name),
                "trade_name":               str(trade_name),
                "customer_vat_number":      "000000000",
                "customer_address":         "",
                "customer_telephone_number": "",
                "customer_tin":             "111111111",
                "customer_province":        "",
                "customer_street":          "",
                "customer_houseNo":         "",
                "customer_city":            "",
                "customer_email":           "",
                "invoice_comment":          "",
                "original_invoice_no":      str(original_invoice_no),
                "global_invoice_no":        str(global_invoice_no) if global_invoice_no else "",
                "tendered":                 f"{tendered:.2f}",
                "items_xml":                items_xml,
            }

            print(f"[ZIMRA] Sending invoice: {invoice_number}")
            print(f"[ZIMRA DEBUG] ── Full payload being sent ──────────────────────")
            print(f"[ZIMRA DEBUG]   URL        : {invoice_url}")
            print(f"[ZIMRA DEBUG]   device_sn  : {data['device_sn']}")
            print(f"[ZIMRA DEBUG]   invoice_no : {data['invoice_number']}")
            print(f"[ZIMRA DEBUG]   currency   : {data['currency']}")
            print(f"[ZIMRA DEBUG]   customer   : {data['customer_name']}")
            print(f"[ZIMRA DEBUG]   trade_name : {data['trade_name']}")
            print(f"[ZIMRA DEBUG]   cust_vat   : {data['customer_vat_number']}")
            print(f"[ZIMRA DEBUG]   cust_tin   : {data['customer_tin']}")
            print(f"[ZIMRA DEBUG]   add_cust   : {data['add_customer']}")
            print(f"[ZIMRA DEBUG]   inv_flag   : {data['invoice_flag']}")
            print(f"[ZIMRA DEBUG]   orig_inv   : {data['original_invoice_no']}")
            print(f"[ZIMRA DEBUG]   global_inv : {data['global_invoice_no']}")
            print(f"[ZIMRA DEBUG]   tendered   : {data['tendered']}")
            print(f"[ZIMRA DEBUG]   items_xml  :\n{data['items_xml']}")
            print(f"[ZIMRA DEBUG]   headers    : { {k: v for k, v in headers.items()} }")
            print(f"[ZIMRA DEBUG] ────────────────────────────────────────────────")

            try:
                response = session.post(invoice_url, data=data, headers=headers, timeout=60)

                print(f"[ZIMRA] Response status: {response.status_code}")
                raw = response.text[:500] if response.text else "empty"
                print(f"[ZIMRA] Raw response text: {raw}")

                if response.status_code != 200:
                    return ApiResult.error(f"HTTP {response.status_code}: {response.text}")

                if not response.text or not response.text.strip():
                    return ApiResult.error(
                        "Empty response body - invoice may already exist on device"
                    )

                try:
                    resp_data = response.json()
                except Exception as e:
                    return ApiResult.error(f"JSON parse error: {e} — raw: {response.text[:200]}")

                print(f"[ZIMRA] Parsed response: {resp_data}")

                # Empty dict {}
                if resp_data == {}:
                    return ApiResult.error(
                        "Empty response {} - invoice number may already exist or device needs reset"
                    )

                # Unwrap {"message": {...}} or use top-level dict directly
                msg = resp_data.get("message", resp_data)

                if isinstance(msg, dict):
                    if msg.get("QRcode"):
                        print(f"[ZIMRA] ✅ Success! QR Code received")
                        return ApiResult.success(FiscalInvoiceResponse.from_dict(resp_data))
                    if msg.get("Message"):
                        if "success" in str(msg["Message"]).lower():
                            print(f"[ZIMRA] ✅ Success message received")
                            return ApiResult.success(FiscalInvoiceResponse.from_dict(resp_data))
                        else:
                            print(f"[ZIMRA] ❌ Error in message: {msg['Message']}")
                            return ApiResult.error(msg["Message"])
                elif isinstance(msg, str):
                    if "success" in msg.lower():
                        print(f"[ZIMRA] ✅ Success string received")
                        return ApiResult.success(FiscalInvoiceResponse.from_dict(resp_data))
                    else:
                        print(f"[ZIMRA] ❌ Error string: {msg}")
                        return ApiResult.error(msg)

                # Top-level QRcode / Message keys (no wrapper)
                if resp_data.get("QRcode"):
                    print(f"[ZIMRA] ✅ Success! QR Code at top level")
                    return ApiResult.success(FiscalInvoiceResponse.from_dict(resp_data))
                if resp_data.get("Message"):
                    if "success" in str(resp_data["Message"]).lower():
                        return ApiResult.success(FiscalInvoiceResponse.from_dict(resp_data))
                    return ApiResult.error(resp_data["Message"])

                return ApiResult.error(f"Unrecognised response format: {resp_data}")

            except Exception as e:
                return ApiResult.error(str(e))


# ---------------------------------------------------------------------------
# Module-level helper — keeps callers working unchanged
# ---------------------------------------------------------------------------
_zimra_service: Optional["ZimraApiService"] = None


def get_zimra_service() -> ZimraApiService:
    global _zimra_service
    if _zimra_service is None:
        _zimra_service = ZimraApiService()
    return _zimra_service