# services/havano_zimra_offline_service.py
"""
Havano ZIMRA Offline Fiscalization Service.
Implements offline signing of ZIMRA fiscal invoices using havanozimrapackage (ZimraDevice).
Generates SHA-256 hashes, RSA PKCS#1 v1.5 digital signatures using local private key,
creates official ZIMRA QR code URLs and verification codes.
"""

import os
import json
import threading
from typing import Optional, Dict, Any
from dataclasses import dataclass

from services.zimra_api_service import ApiResult, FiscalInvoiceResponse
from havanozimrapackage import ZimraDevice, Signature

_havano_offline_lock = threading.Lock()


@dataclass
class HavanoZimraOfflinePingResponse:
    device_sn: str
    device_id: str
    reporting_frequency: int
    operation_id: str
    config_file: str


class HavanoZimraOfflineService:
    """
    Offline Fiscalization Service powered by havanozimrapackage.
    Uses havanoconfig.ini and havano_cert/key.key to generate
    and sign ZIMRA fiscal receipts offline without internet access.
    """

    def __init__(self, config_path: Optional[str] = None):
        self._config_path = config_path

    def get_config_file_path(self, settings=None) -> str:
        """
        Locates havanoconfig.ini.
        Checks:
        1. Explicit config_path passed in constructor
        2. settings.base_url or settings.device_sn if pointing to a file
        3. Root directory of application (os.getcwd())
        4. Directory of this service file's parent
        """
        if self._config_path and os.path.exists(self._config_path):
            return self._config_path

        candidates = [
            os.path.join(os.getcwd(), "havanoconfig.ini"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "havanoconfig.ini"),
        ]

        if settings:
            base_url = str(getattr(settings, "base_url", "") or "").strip()
            if base_url and os.path.exists(base_url):
                candidates.insert(0, base_url)

        for path in candidates:
            if os.path.exists(path):
                return path

        return candidates[0]

    def _update_config_file_counters(self, config_file_path: str, global_no: int, counter: int, prev_hash: str):
        """
        Atomically updates ReceiptGlobalNo, ReceiptCounter, and PreviousReceiptHash
        in havanoconfig.ini to maintain the strict ZIMRA sequential hash chain.
        """
        if not os.path.exists(config_file_path):
            return

        try:
            with open(config_file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            updated_keys = set()
            new_lines = []

            for line in lines:
                stripped = line.strip()
                if ":" in stripped:
                    k, _ = stripped.split(":", 1)
                    k_clean = k.strip().lower()

                    if k_clean == "receiptglobalno":
                        new_lines.append(f"ReceiptGlobalNo:{global_no}\n")
                        updated_keys.add("receiptglobalno")
                        continue
                    elif k_clean == "receiptcounter":
                        new_lines.append(f"ReceiptCounter:{counter}\n")
                        updated_keys.add("receiptcounter")
                        continue
                    elif k_clean == "previousreceipthash":
                        new_lines.append(f"PreviousReceiptHash:{prev_hash}\n")
                        updated_keys.add("previousreceipthash")
                        continue

                new_lines.append(line)

            # If any keys were missing, append them
            if "receiptglobalno" not in updated_keys:
                new_lines.append(f"ReceiptGlobalNo:{global_no}\n")
            if "receiptcounter" not in updated_keys:
                new_lines.append(f"ReceiptCounter:{counter}\n")
            if "previousreceipthash" not in updated_keys:
                new_lines.append(f"PreviousReceiptHash:{prev_hash}\n")

            with open(config_file_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)

            print(f"[HavanoZimraOffline] Updated havanoconfig.ini -> GlobalNo:{global_no}, Counter:{counter}")

        except Exception as e:
            print(f"[HavanoZimraOffline] Warning: Could not update havanoconfig.ini counters: {e}")

    def ping_device(self, settings=None) -> ApiResult:
        """
        Checks that havanoconfig.ini and havano_cert/key.key exist and are valid.
        """
        config_path = self.get_config_file_path(settings)
        if not os.path.exists(config_path):
            return ApiResult.error(
                f"Configuration file not found: {config_path}. "
                "Please place havanoconfig.ini and havano_cert/key.key in the application root."
            )

        cert_dir = os.path.join(os.path.dirname(os.path.abspath(config_path)), "havano_cert")
        key_path = os.path.join(cert_dir, "key.key")
        if not os.path.exists(key_path):
            return ApiResult.error(
                f"Device signing private key not found at {key_path}. "
                "Please ensure havano_cert/key.key exists next to havanoconfig.ini."
            )

        try:
            device = ZimraDevice()
            device.load_config_file(config_path)
            device_sn = device.get_config_value("device_sn") or device.get_config_value("deviceSerialNo") or "Unknown"
            device_id = device.get_config_value("device_id") or "Unknown"

            # Check that private key is readable
            with open(key_path, "r", encoding="utf-8") as kf:
                key_content = kf.read()
            if "PRIVATE KEY" not in key_content:
                return ApiResult.error("Private key in havano_cert/key.key is not in valid PEM format.")

            return ApiResult.success(HavanoZimraOfflinePingResponse(
                device_sn=str(device_sn),
                device_id=str(device_id),
                reporting_frequency=getattr(settings, "ping_interval_minutes", 5) or 5,
                operation_id="OFFLINE-SIGNING-READY",
                config_file=config_path
            ))

        except Exception as e:
            return ApiResult.error(f"Failed loading offline device config: {e}")

    def send_invoice(self, settings, invoice_number: str, currency: str,
                     customer_name: str, trade_name: str, items_xml: str,
                     **kwargs) -> ApiResult:
        """
        Signs and fiscalizes a sales invoice or credit note offline using ZimraDevice.
        Serialised via _havano_offline_lock to prevent concurrent counter corruption.
        """
        with _havano_offline_lock:
            config_path = self.get_config_file_path(settings)
            if not os.path.exists(config_path):
                return ApiResult.error(f"havanoconfig.ini not found at {config_path}")

            invoice_flag = int(kwargs.get("invoice_flag", 0))
            original_invoice_no = str(kwargs.get("original_invoice_no", "") or "")
            global_invoice_no = kwargs.get("global_invoice_no", 0) or 0
            try:
                global_invoice_no = int(global_invoice_no)
            except (ValueError, TypeError):
                global_invoice_no = 0

            # Normalize currency (ZIG -> ZWG)
            fiscal_currency = str(currency).upper()
            if fiscal_currency in ("ZIG", "ZWL", "ZWD"):
                fiscal_currency = "ZWG"

            # Customer details
            cust_name = str(customer_name or "").strip()
            cust_trade = str(trade_name or cust_name or "").strip()
            is_cash = cust_name.lower() in ("", "cash customer", "walk-in", "walk in customer", "default customer")

            add_customer = "0" if is_cash else "1"
            cust_tin = str(kwargs.get("buyer_tin", "") or ("" if is_cash else "111111111"))
            cust_vat = str(kwargs.get("buyer_vat", "") or ("" if is_cash else "000000000"))
            cust_phone = str(kwargs.get("buyer_phone", "") or "")
            cust_email = str(kwargs.get("buyer_email", "") or "")
            cust_street = str(kwargs.get("buyer_street", "") or "")
            cust_city = str(kwargs.get("buyer_city", "") or "")
            cust_house_no = str(kwargs.get("buyer_house_no", "") or "")
            cust_province = str(kwargs.get("buyer_province", "") or "")
            cust_address = (f"{cust_house_no} {cust_street} {cust_city}").strip()

            try:
                device = ZimraDevice()
                device_sn = getattr(settings, "device_sn", None)
                if not device_sn:
                    device.load_config_file(config_path)
                    device_sn = device.get_config_value("device_sn") or device.get_config_value("deviceSerialNo") or "elisafinas_1"

                print(f"[HavanoZimraOffline] Signing receipt offline: {invoice_number} ({fiscal_currency})")

                raw_resp = device.send_offline_invoice(
                    config_file_path=config_path,
                    device_sn=str(device_sn),
                    AddCustomer=add_customer,
                    InvoiceFlag=invoice_flag,
                    Currency=fiscal_currency,
                    InvoiceNumber=str(invoice_number),
                    CustomerName=cust_name if not is_cash else "",
                    TradeName=cust_trade if not is_cash else "",
                    CustomerVATNumber=cust_vat if not is_cash else "",
                    CustomerAddress=cust_address if not is_cash else "",
                    CustomerTelephoneNumber=cust_phone if not is_cash else "",
                    CustomerTIN=cust_tin if not is_cash else "",
                    CustomerProvince=cust_province if not is_cash else None,
                    CustomerStreet=cust_street if not is_cash else None,
                    CustomerHouseNo=cust_house_no if not is_cash else None,
                    CustomerCity=cust_city if not is_cash else None,
                    CustomerEmail=cust_email if not is_cash else "",
                    InvoiceComment="",
                    OriginalInvoiceNo=original_invoice_no if invoice_flag == 1 else "",
                    GlobalInvoiceNo=global_invoice_no if invoice_flag == 1 else 0,
                    ItemsXML=items_xml,
                    invoice_tax_type=1  # Tax-inclusive lines default in Havano POS
                )

                # Check if raw_resp is an error string or dict
                if isinstance(raw_resp, str):
                    try:
                        resp_data = json.loads(raw_resp)
                    except Exception:
                        return ApiResult.error(f"Offline signing returned error: {raw_resp}")
                elif isinstance(raw_resp, dict):
                    resp_data = raw_resp
                else:
                    return ApiResult.error(f"Unexpected response type from ZimraDevice: {type(raw_resp)}")

                if "Message" in resp_data and "Invalid" in str(resp_data.get("Message", "")):
                    return ApiResult.error(resp_data["Message"])

                # Check QR code presence
                if not resp_data.get("QRcode") and not resp_data.get("VerificationCode"):
                    return ApiResult.error(f"Offline signing did not return QR or Verification Code: {resp_data}")

                # Compute current receipt hash to update PreviousReceiptHash for the next invoice
                current_receipt_hash = ""
                if getattr(Signature, "concate_data", ""):
                    try:
                        current_receipt_hash = Signature.compute_hash(Signature.concate_data)
                    except Exception as he:
                        print(f"[HavanoZimraOffline] Could not compute receipt hash: {he}")

                new_global_no = int(resp_data.get("receiptGlobalNo") or 0)
                new_counter = int(resp_data.get("receiptCounter") or 0)

                # Update havanoconfig.ini counters
                if new_global_no > 0:
                    self._update_config_file_counters(
                        config_file_path=config_path,
                        global_no=new_global_no,
                        counter=new_counter,
                        prev_hash=current_receipt_hash
                    )

                fiscal_response = FiscalInvoiceResponse(
                    message=str(resp_data.get("Message", "Invoice Successfully Sent to Zimra")),
                    qr_code=str(resp_data.get("QRcode", "")),
                    verification_code=str(resp_data.get("VerificationCode", "")),
                    device_id=str(resp_data.get("DeviceID", "")),
                    fiscal_day=str(resp_data.get("FiscalDay", "")),
                    receipt_type=str(resp_data.get("receiptType", "FISCALINVOICE")),
                    receipt_currency=str(resp_data.get("receiptCurrency", fiscal_currency)),
                    receipt_counter=new_counter,
                    receipt_global_no=new_global_no,
                    efd_serial=str(resp_data.get("EFDSERIAL") or device_sn or "")
                )

                print(f"[HavanoZimraOffline] [OK] Signed successfully! GlobalNo: {new_global_no}, Verification: {fiscal_response.verification_code}")
                return ApiResult.success(fiscal_response)

            except Exception as e:
                print(f"[HavanoZimraOffline] ❌ Exception during offline signing: {e}")
                return ApiResult.error(str(e))


_havano_zimra_offline_service: Optional[HavanoZimraOfflineService] = None


def get_havano_zimra_offline_service() -> HavanoZimraOfflineService:
    global _havano_zimra_offline_service
    if _havano_zimra_offline_service is None:
        _havano_zimra_offline_service = HavanoZimraOfflineService()
    return _havano_zimra_offline_service
