# models/receipt.py
from dataclasses import dataclass, asdict, field
from typing import List, Optional
import json
from datetime import datetime

@dataclass
class Item:
    """Single line item on the receipt (matches your C# Item class)"""
    productName: str
    productid: str = ""
    qty: float = 0.0
    price: float = 0.0
    amount: float = 0.0
    tax_amount: float = 0.0


@dataclass
class MultiCurrencyDetail:
    """Multi-currency breakdown"""
    key: str
    value: float


@dataclass
class ReceiptData:
    """Full receipt model — identical structure to your ReceiptData.cs"""
    
    doc_type: str = "receipt"
    receiptType: str = "Sales"
    
    companyLogoPath: str = ""
    companyName: str = ""
    KOT: str = ""
    
    companyAddress: str = ""
    companyAddressLine1: str = ""
    companyAddressLine2: str = ""
    city: str = ""
    state: str = ""
    postcode: str = ""
    
    cashier: str = ""
    contact: str = ""
    companyEmail: str = ""
    tin: str = ""
    vatNo: str = ""
    tel: str = ""
    
    invoiceNo: str = ""
    invoiceDate: str = ""
    cashierName: str = ""
    
    customerName: str = ""
    customerContact: str = ""
    customerTradeName: str = ""
    customerEmail: str = ""
    customerTin: str = ""
    customerVat: str = ""
    customeraddress: str = ""
    
    amountTendered: float = 0.0
    change: float = 0.0
    
    qrCodePath: str = ""
    qrCodePath2: str = ""
    currency: str = "USD"
    footer: str = "Thank you for your purchase!"
    
    multiCurrencyDetails: List[MultiCurrencyDetail] = field(default_factory=list)
    
    deviceId: str = ""
    fiscalDay: str = ""
    deviceSerial: str = ""
    receiptNo: str = ""
    customerRef: str = ""
    vCode: str = ""
    qrCode: str = ""
    
    discAmt: float = 0.0
    grandTotal: float = 0.0
    subtotal: float = 0.0
    totalVat: float = 0.0
    taxType: str = ""
    paymentMode: str = "CASH"
    
    items: List[Item] = field(default_factory=list)
    itemlist: List[Item] = field(default_factory=list)   # for backward compatibility with your .NET app


    def to_json(self) -> str:
        """Convert to exact JSON your PrintingManager expects"""
        data = asdict(self)
        # Make sure both "items" and "itemlist" are populated
        data["itemlist"] = data["items"]
        return json.dumps(data, indent=2, ensure_ascii=False)


    def save_to_file(self, filename: str = None) -> str:
        """Save as JSON file (ready for PrintingManager)"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"receipt_{timestamp}.json"
        
        filepath = f"receipts/{filename}"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self.to_json())
        return filepath