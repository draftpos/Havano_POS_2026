# services/payment_print.py
import logging
from models.receipt import ReceiptData, Item, MultiCurrencyDetail
from services.printing_service import PrintingService

log = logging.getLogger(__name__)
printing_service = PrintingService()

def print_customer_payment_receipt(payment_data: dict, customer_name: str) -> bool:
    """
    Constructs and prints a receipt for a general customer payment (debt reduction).

    payment_data keys used:
      id             — reference number
      cashier_id     — cashier identifier
      amount         — total amount paid (USD)
      currency       — primary currency of payment
      customer_balance — remaining balance after this payment (optional)
      payment_splits — dict of {method_label: amount} for split payments (optional)
      method         — single payment method label (used when no splits)
      is_laybye_deposit — bool, if True shows "Laybye Deposit" section (optional)
      laybye_ref     — laybye/sales-order reference (optional)
    """
    try:
        amount = float(payment_data.get("amount", 0))
        currency = payment_data.get("currency", "USD")

        # ── 1. Payment splits (forms of payment) ─────────────────────────────
        # Prefer explicit splits dict; fall back to single method entry.
        raw_splits: dict = payment_data.get("payment_splits") or {}
        if not raw_splits:
            method_label = payment_data.get("method", "Cash")
            raw_splits = {method_label: amount}

        payment_splits = {k: float(v) for k, v in raw_splits.items() if float(v) > 0}

        # ── 2. Build ReceiptData ──────────────────────────────────────────────
        receipt = ReceiptData()
        receipt.receiptType   = "PAYMENT RECEIPT"
        receipt.doc_type      = "payment"
        receipt.customerName  = customer_name          # used by _print_payment_receipt
        receipt.customer      = customer_name          # legacy field
        receipt.cashier       = str(payment_data.get("cashier_id", ""))
        receipt.orderNo       = f"PAY-{payment_data.get('id', '000')}"
        # Date: use print date (datetime.now is called in printing_service)
        # No receipt.date override needed — printer always uses current datetime.

        # ── 3. Line items: one row per payment method ─────────────────────────
        items = []
        for method_label, method_amount in payment_splits.items():
            items.append(Item(
                productName=method_label,
                qty=1,
                price=float(method_amount),
                amount=float(method_amount),
            ))
        receipt.items = items

        # ── 4. Totals ─────────────────────────────────────────────────────────
        receipt.total           = amount
        receipt.amountReceived  = amount
        receipt.balanceDue      = float(payment_data.get("customer_balance", 0.0) or 0.0)

        # ── 5. Multi-currency breakdown (one entry per split) ─────────────────
        receipt.multiCurrencyDetails = [
            MultiCurrencyDetail(key=label, value=amt)
            for label, amt in payment_splits.items()
        ]

        # ── 6. Laybye deposit info (optional) ─────────────────────────────────
        receipt.is_laybye_deposit = bool(payment_data.get("is_laybye_deposit", False))
        receipt.laybye_ref        = payment_data.get("laybye_ref", "")

        receipt.footer = "Thank you for your payment!"

        # ── 7. Print ──────────────────────────────────────────────────────────
        return printing_service.print_receipt(receipt)

    except Exception as e:
        log.error(f"Failed to print payment receipt: {e}")
        return False