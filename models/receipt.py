# # models/receipt.py
# from dataclasses import dataclass, asdict, field
# from typing import List, Optional
# import json
# from datetime import datetime

# @dataclass
# class Item:
#     """Single line item on the receipt (matches your C# Item class)"""
#     productName: str
#     productid: str = ""
#     qty: float = 0.0
#     price: float = 0.0
#     amount: float = 0.0
#     tax_amount: float = 0.0
#     batch_no: str = ""
#     expiry_date: str = ""


# @dataclass
# class MultiCurrencyDetail:
#     """Multi-currency breakdown"""
#     key: str
#     value: float


# @dataclass
# class ReceiptData:
#     """Full receipt model — identical structure to your ReceiptData.cs"""
    
#     doc_type: str = "receipt"
#     receiptType: str = "Sales"
    
#     companyLogoPath: str = ""
#     companyName: str = ""
#     KOT: str = ""
    
#     companyAddress: str = ""
#     companyAddressLine1: str = ""
#     companyAddressLine2: str = ""
#     # companyEmail: str = ""
#     city: str = ""
#     state: str = ""
#     postcode: str = ""
    
#     cashier: str = ""
#     contact: str = ""
#     companyEmail: str = ""
#     tin: str = ""
#     vatNo: str = ""
#     tel: str = ""
    
#     invoiceNo: str = ""
#     invoiceDate: str = ""
#     cashierName: str = ""
    
#     customerName: str = ""
#     customerContact: str = ""
#     customerTradeName: str = ""
#     customerEmail: str = ""
#     customerTin: str = ""
#     customerVat: str = ""
#     customeraddress: str = ""
    
#     amountTendered: float = 0.0
#     change: float = 0.0
    
#     qrCodePath: str = ""
#     qrCodePath2: str = ""
#     currency: str = "USD"
#     footer: str = "Thank you for your purchase!"
    
#     multiCurrencyDetails: List[MultiCurrencyDetail] = field(default_factory=list)
    
#     deviceId: str = ""
#     fiscalDay: str = ""
#     deviceSerial: str = ""
#     receiptNo: str = ""
#     customerRef: str = ""
#     vCode: str = ""
#     qrCode: str = ""
    
#     discAmt: float = 0.0
#     grandTotal: float = 0.0
#     subtotal: float = 0.0
#     totalVat: float = 0.0
#     taxType: str = ""
#     paymentMode: str = "CASH"
    
#     items: List[Item] = field(default_factory=list)
#     itemlist: List[Item] = field(default_factory=list)   # for backward compatibility with your .NET app


#     def to_json(self) -> str:
#         """Convert to exact JSON your PrintingManager expects"""
#         data = asdict(self)
#         # Make sure both "items" and "itemlist" are populated
#         data["itemlist"] = data["items"]
#         return json.dumps(data, indent=2, ensure_ascii=False)


#     def save_to_file(self, filename: str = None) -> str:
#         """Save as JSON file (ready for PrintingManager)"""
#         if filename is None:
#             timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#             filename = f"receipt_{timestamp}.json"
        
#         filepath = f"receipts/{filename}"
#         with open(filepath, "w", encoding="utf-8") as f:
#             f.write(self.to_json())
#         return filepath


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
    batch_no: str = ""
    expiry_date: str = ""


@dataclass
class MultiCurrencyDetail:
    """Multi-currency breakdown"""
    key: str
    value: float


@dataclass
class ReceiptData:
    """Full receipt model — identical structure to your ReceiptData.cs

    doc_type routing:
        "receipt"       → standard sales invoice template  (existing behaviour)
        "sales_order"   → Sales Order / Laybye template    (new)

    The C# PrintingManager should switch templates based on doc_type.
    """

    # ── Routing ──────────────────────────────────────────────────────────────
    # "receipt"      → standard POS invoice  (no change to existing behaviour)
    # "sales_order"  → Sales Order / Laybye receipt  (new dedicated template)
    doc_type: str = "receipt"

    receiptType: str = "Sales"
    fiscal_pending: bool = False 
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
    # Per-shift running order number. 0 = unset / not yet migrated.
    orderNumber: int = 0

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
    receiptHeader: str = ""
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

    # ── Sales Order specific fields ───────────────────────────────────────────
    # deliveryDate  — expected collection / delivery date shown on the order slip
    deliveryDate: str = ""

    # salesOrderTerms — printed as a "Terms & Conditions" block at the bottom
    # of every Sales Order / Laybye receipt.  Populate from company_defaults
    # (sales_order_terms column) or fall back to the hard-coded default below.
    # Each line is separated by "\n"; the C# template should split and render
    # each line as a separate paragraph.
    salesOrderTerms: str = (
        "1. This Sales Order is not a tax invoice.\n"
        "2. Goods remain the property of the seller until paid in full.\n"
        "3. Laybye items are held for 30 days from order date.\n"
        "4. Deposits are non-refundable unless goods are unavailable.\n"
        "5. Full payment is required before goods are released."
    )

    # orderStatus — "Draft" | "Confirmed" | "Completed" | "Cancelled"
    # Shown as a status badge on the printed slip so staff can see at a glance
    # whether the order is still outstanding.
    orderStatus: str = ""

    items: List[Item] = field(default_factory=list)
    itemlist: List[Item] = field(default_factory=list)   # backward-compat with .NET app
    # Payment method breakdown — one Item per method paid:
    #   productName = method label (e.g. "CASH", "ECOCASH")
    #   productid   = native currency code (e.g. "ZIG", "USD")
    #   price       = native amount  (e.g. 9000.00)
    #   amount      = USD base value (e.g. 297.00)
    paymentItems: List[Item] = field(default_factory=list)


    def to_json(self) -> str:
        """Convert to the exact JSON your PrintingManager expects."""
        data = asdict(self)
        # Keep both lists in sync (PrintingManager reads itemlist)
        data["itemlist"] = data["items"]
        return json.dumps(data, indent=2, ensure_ascii=False)


    def save_to_file(self, filename: str = None) -> str:
        """Save as JSON file (ready for PrintingManager)."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"receipt_{timestamp}.json"

        filepath = f"receipts/{filename}"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self.to_json())
        return filepath