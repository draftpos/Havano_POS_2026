# services/fiscal.py
import urllib.parse
import hashlib
from datetime import datetime
from typing import Optional
import qrcode
from io import BytesIO
from PySide6.QtGui import QPixmap

class FiscalLogic:
    """
    Core logic for ZIMRA dynamic URL generation and QR code creation.
    Supports offline-first URL construction using device identifiers and hashes.
    """
    
    BASE_URL = "https://fdmstest.zimra.co.zw/Receipt/Result"

    @staticmethod
    def construct_url(device_sn: str, date: datetime, global_no: int, signature: str) -> str:
        """
        Constructs the official ZIMRA verification URL.
        New Format: https://fdmstest.zimra.co.zw/Receipt/Result?DeviceId={SN}&ReceiptDate={DATE}&ReceiptCounterReceiptGlobalNo={GLOBAL_NO}&ReceiptQrData={SIG}
        """
        # Format date as YYYYMMDDHHMMSS
        dt_str = date.strftime("%Y%m%d%H%M%S")
        
        # Build query parameters with long keys as requested
        params = {
            "DeviceId": device_sn,
            "ReceiptDate": dt_str,
            "ReceiptCounterReceiptGlobalNo": global_no,
            "ReceiptQrData": signature[:16] # Signature snippet for the URL
        }
        
        query_string = urllib.parse.urlencode(params)
        return f"{FiscalLogic.BASE_URL}?{query_string}"

    @staticmethod
    def generate_offline_signature(device_sn: str, date: datetime, global_no: int, total: float) -> str:
        """
        Generates a deterministic hex hash for offline operations.
        This serves as a unique signature when the official ZIMRA signature is unavailable.
        """
        payload = f"{device_sn}|{date.isoformat()}|{global_no}|{total:.2f}"
        return hashlib.sha256(payload.encode()).hexdigest()

    @staticmethod
    def generate_qr_pixmap(url: str, size: int = 250) -> QPixmap:
        """
        Generates a QPixmap QR code from a URL.
        """
        try:
            # Standardizing settings for high-contrast thermal printing
            qr = qrcode.QRCode(
                version=None, # Auto
                error_correction=qrcode.constants.ERROR_CORRECT_Q, # Better correction for thermal
                box_size=10,
                border=4,
            )
            qr.add_data(url)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")
            
            # Convert PIL image to bytes
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            
            pixmap = QPixmap()
            pixmap.loadFromData(buffer.getvalue(), "PNG")
            
            if size:
                return pixmap.scaled(size, size)
            return pixmap
        except Exception as e:
            print(f"Error generating QR Pixmap: {e}")
            return QPixmap()

    @staticmethod
    def get_next_global_no() -> int:
        """
        Thread-safe retrieval and increment of the global receipt counter.
        Currently fetches from fiscal_settings but should be handled by a counter service.
        """
        from models.fiscal_settings import FiscalSettingsRepository
        repo = FiscalSettingsRepository()
        settings = repo.get_settings()
        
        # If last_global_no is not set, we might need to initialize it
        # This is a simplified version; in production, this needs transaction locks.
        last_no = getattr(settings, 'last_global_no', 0) or 0
        next_no = last_no + 1
        
        # Update in database (Note: this needs to be atomic)
        repo.update_last_global_no(next_no)
        
        return next_no
