# services/payment_print.py
import logging
from models.receipt import ReceiptData, Item, MultiCurrencyDetail
from services.printing_service import PrintingService

log = logging.getLogger(__name__)
printing_service = PrintingService()

def print_customer_payment_receipt(payment_data: dict, customer_name: str) -> bool:
    """
    Constructs and prints a receipt for a general customer payment (debt reduction).
    """
    try:
        # 1. Build Receipt Data
        receipt = ReceiptData()
        receipt.receiptType = "PAYMENT RECEIPT"
        receipt.doc_type = "payment"  # Useful for template routing
        
        receipt.customer = customer_name
        receipt.cashier = str(payment_data.get("cashier_id", ""))
        receipt.orderNo = f"PAY-{payment_data.get('id', '000')}"
        receipt.date = payment_data.get("payment_date") or ""
        
        # 2. Add the payment as a line item
        payment_item = Item(
            productName=f"Account Payment - {payment_data.get('method', 'Cash')}",
            qty=1,
            price=float(payment_data.get("amount", 0)),
            amount=float(payment_data.get("amount", 0))
        )
        receipt.items = [payment_item]
        
        # 3. Summary totals
        receipt.total = float(payment_data.get("amount", 0))
        receipt.amountReceived = receipt.total
        receipt.balanceDue = 0.0  # This specific transaction is paid
        
        # 4. Multi-currency detail (if applicable)
        receipt.multiCurrencyDetails = [
            MultiCurrencyDetail(key=payment_data.get("currency", "USD"), value=receipt.total)
        ]
        
        receipt.footer = "Thank you for your payment!"
        
        # 5. Send to default printer (or loop through active printers)
        # You can fetch printer names from your settings similar to sales_order_print.py
        return printing_service.print_receipt(receipt)

    except Exception as e:
        log.error(f"Failed to print payment receipt: {e}")
        return False