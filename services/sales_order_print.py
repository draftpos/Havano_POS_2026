# =============================================================================
# services/sales_order_print.py  —  Sales Order / Laybye receipt printing
#
# Produces a receipt that is visually and structurally distinct from a normal
# POS sales invoice:
#
#   doc_type = "sales_order"   → C# PrintingManager routes to the SO template
#   receiptType                → "Sales Order"  |  "Laybye Deposit"
#
# What appears on the printed slip:
#   ┌─────────────────────────────────────┐
#   │        [Company Header]             │
#   │   *** SALES ORDER ***               │  ← large heading, not "TAX INVOICE"
#   │   Order No: SO-0042                 │
#   │   Order Date: 2025-07-01            │
#   │   Delivery Date: 2025-07-15         │  ← if set
#   │   Status: Confirmed                 │
#   │   Customer: John Doe                │
#   ├─────────────────────────────────────┤
#   │   # | Item          | Qty | Amount  │
#   │   1 | Widget A      |   2 | 10.00   │
#   │   2 | Widget B      |   1 |  5.00   │
#   ├─────────────────────────────────────┤
#   │   Order Total:   USD 15.00          │  ← multiCurrencyDetails rows
#   │   Deposit Paid:  USD  5.00          │
#   │   Balance Due:   USD 10.00          │
#   ├─────────────────────────────────────┤
#   │   Payment Method: EcoCash           │
#   ├─────────────────────────────────────┤
#   │   TERMS & CONDITIONS                │  ← salesOrderTerms block
#   │   1. This Sales Order is not a ...  │
#   │   2. Goods remain the property …    │
#   │   …                                 │
#   ├─────────────────────────────────────┤
#   │   [footer text]                     │
#   └─────────────────────────────────────┘
#
# Public API
# ----------
#   print_sales_order(order_id)      — full Sales Order slip
#   print_laybye_deposit(order_id)   — Laybye Deposit confirmation slip
#
# Both return True if at least one printer succeeded.
# =============================================================================

from __future__ import annotations
import json
import logging
from pathlib import Path
from datetime import datetime

log = logging.getLogger("sales_order_print")


# ---------------------------------------------------------------------------
# Default terms printed on every Sales Order slip.
# Override per-company by adding a `sales_order_terms` column to
# company_defaults and populating it there.
# ---------------------------------------------------------------------------
_DEFAULT_SO_TERMS = (
    "1. This Sales Order is not a tax invoice.\n"
    "2. Goods remain the property of the seller until paid in full.\n"
    "3. Laybye items are held for 30 days from order date.\n"
    "4. Deposits are non-refundable unless goods are unavailable.\n"
    "5. Full payment is required before goods are released."
)


# =============================================================================
# Internal helpers
# =============================================================================

def _get_active_printers() -> list[str]:
    """Read main_printer from hardware_settings.json (same logic as sale.py)."""
    hw_file = Path("app_data/hardware_settings.json")
    try:
        with open(hw_file, "r", encoding="utf-8") as f:
            hw = json.load(f)
        printers = []
        if hw.get("main_printer") and hw["main_printer"] != "(None)":
            printers.append(hw["main_printer"])
        return list(dict.fromkeys(printers))
    except Exception as exc:
        log.warning("Could not read hardware_settings.json: %s", exc)
        return []


def _get_company_defaults() -> dict:
    """Pull company defaults the same way sale.py does via CROSS JOIN."""
    try:
        from models.company_defaults import get_defaults
        return get_defaults() or {}
    except Exception:
        return {}


def _format_date(raw: str) -> str:
    """Return a printable date string from an ISO date/datetime."""
    if not raw:
        return datetime.today().strftime("%Y-%m-%d")
    try:
        return datetime.fromisoformat(raw).strftime("%Y-%m-%d")
    except Exception:
        return raw


# =============================================================================
# Core builder
# =============================================================================

def _build_receipt(order: dict, receipt_type: str = "Sales Order") -> "ReceiptData":
    """
    Map a sales_order dict (from get_order_by_id) to a ReceiptData object
    with doc_type = "sales_order".

    receipt_type:
        "Sales Order"    — full order slip, shows the complete order total
        "Laybye Deposit" — deposit confirmation, highlights deposit paid
                           and outstanding balance
    """
    from models.receipt import ReceiptData, Item, MultiCurrencyDetail

    co = _get_company_defaults()

    # ── Customer ─────────────────────────────────────────────────────────────
    customer_name    = order.get("customer_name") or "Walk-in Customer"
    customer_contact = order.get("customer_contact") or ""

    # ── Dates ─────────────────────────────────────────────────────────────────
    order_date    = _format_date(order.get("order_date", ""))
    delivery_date = _format_date(order.get("delivery_date", "")) if order.get("delivery_date") else ""

    # ── Money ─────────────────────────────────────────────────────────────────
    total          = float(order.get("total",          0))
    deposit_amount = float(order.get("deposit_amount", 0))
    balance_due    = float(order.get("balance_due",    0))
    order_status   = order.get("status", "")

    # ── Terms — use company override if available, else default ───────────────
    so_terms = co.get("sales_order_terms") or _DEFAULT_SO_TERMS

    # ── Footer ────────────────────────────────────────────────────────────────
    base_footer = co.get("footer_text") or "Thank you for your business!"

    # ── Receipt-type-specific fields ──────────────────────────────────────────
    if receipt_type == "Laybye Deposit":
        # amountTendered = deposit paid today  (not the full order total)
        tendered     = deposit_amount
        change       = 0.0
        # customerRef prints as a prominent reference line in the totals area
        customer_ref = f"BALANCE DUE:  {order.get('currency', 'USD')} {balance_due:.2f}"
        footer       = base_footer
    else:
        # Full Sales Order slip — tendered = full total
        tendered     = total
        change       = 0.0
        customer_ref = ""
        footer       = base_footer

    receipt = ReceiptData(
        # ── Routing: tells the C# PrintingManager to use the SO template ─────
        doc_type    = "sales_order",
        receiptType = receipt_type,        # "Sales Order"  |  "Laybye Deposit"

        # ── Company header ────────────────────────────────────────────────────
        companyName         = co.get("company_name", ""),
        companyAddress      = co.get("address_1",    ""),
        companyAddressLine1 = co.get("address_2",    ""),
        companyEmail        = co.get("email",         ""),
        tel                 = co.get("phone",         ""),
        tin                 = co.get("tin_number",    ""),
        vatNo               = co.get("vat_number",    ""),
        # Intentionally NOT setting deviceSerial / deviceId — this is not a
        # fiscal document, so ZIMRA fields must stay blank.
        deviceSerial        = "",
        deviceId            = "",

        # ── Order reference ───────────────────────────────────────────────────
        invoiceNo   = order.get("order_no", ""),
        invoiceDate = order_date,

        # ── Cashier / customer ────────────────────────────────────────────────
        cashierName     = "",            # not tied to a POS cashier
        customerName    = customer_name,
        customerContact = customer_contact,
        customerRef     = customer_ref,  # "BALANCE DUE: USD X.XX" (deposit slip)

        # ── Totals ────────────────────────────────────────────────────────────
        grandTotal     = total,          # full order value
        subtotal       = total,
        totalVat       = 0.0,            # SO is pre-invoice — no VAT line
        amountTendered = tendered,       # deposit on deposit slip; total on SO
        change         = change,
        discAmt        = 0.0,

        # ── Payment ───────────────────────────────────────────────────────────
        paymentMode = order.get("deposit_method", ""),
        currency    = order.get("currency", "USD"),
        footer      = footer,

        # ── Sales-Order-specific ──────────────────────────────────────────────
        deliveryDate    = delivery_date,
        salesOrderTerms = so_terms,
        orderStatus     = order_status,
    )

    # ── Deposit / balance summary (multiCurrencyDetails rows) ─────────────────
    # These always appear on both slip types so the customer can clearly see:
    #   ORDER TOTAL  /  DEPOSIT PAID  /  BALANCE DUE
    receipt.multiCurrencyDetails = [
        MultiCurrencyDetail(key="Order Total",  value=round(total,          2)),
        MultiCurrencyDetail(key="Deposit Paid", value=round(deposit_amount, 2)),
        MultiCurrencyDetail(key="Balance Due",  value=round(balance_due,    2)),
    ]

    # ── Line items ────────────────────────────────────────────────────────────
    for it in order.get("items", []):
        qty    = float(it.get("qty",    1))
        rate   = float(it.get("rate",   0))
        amount = float(it.get("amount") or qty * rate)
        receipt.items.append(Item(
            productName = it.get("item_name") or it.get("item_code") or "",
            productid   = it.get("item_code", ""),
            qty         = qty,
            price       = rate,
            amount      = amount,
            tax_amount  = 0.0,
        ))

    # Keep itemlist in sync (backward-compat with PrintingManager)
    receipt.itemlist = receipt.items
    return receipt


# =============================================================================
# Public API
# =============================================================================

def print_sales_order(order_id: int) -> bool:
    """
    Print a full Sales Order slip.

    The receipt will show:
      • "SALES ORDER" heading (not "TAX INVOICE")
      • Order No, Order Date, Delivery Date, Status
      • Customer name
      • Line items table
      • Order Total / Deposit Paid / Balance Due summary
      • Terms & Conditions block
      • Company footer

    Returns True if at least one printer succeeded.
    """
    from models.sales_order import get_order_by_id
    from services.printing_service import printing_service

    order = get_order_by_id(order_id)
    if not order:
        log.error("print_sales_order: order %d not found", order_id)
        return False

    printers = _get_active_printers()
    if not printers:
        log.warning("print_sales_order: no active printers configured")
        return False

    receipt = _build_receipt(order, receipt_type="Sales Order")
    ok = False
    for printer_name in printers:
        try:
            success = printing_service.print_receipt(receipt, printer_name=printer_name)
            if success:
                log.info("✅ Sales Order %s printed → %s", order.get("order_no"), printer_name)
                ok = True
            else:
                log.warning("⚠️  Sales Order print failed on %s", printer_name)
        except Exception as exc:
            log.error("❌ Printer error on %s: %s", printer_name, exc)
    return ok


def print_laybye_deposit(order_id: int) -> bool:
    """
    Print a Laybye Deposit confirmation slip.

    The receipt will show:
      • "LAYBYE DEPOSIT" heading
      • Order No, Order Date, Customer name
      • Line items table
      • Order Total / Deposit Paid / Balance Due summary  ← always visible
      • "BALANCE DUE: USD X.XX" reference line
      • Terms & Conditions block
      • Company footer

    Call this immediately after LaybyePaymentDialog.accept() and
    create_sales_order() / add_deposit_payment().

    Returns True if at least one printer succeeded.
    """
    from models.sales_order import get_order_by_id
    from services.printing_service import printing_service

    order = get_order_by_id(order_id)
    if not order:
        log.error("print_laybye_deposit: order %d not found", order_id)
        return False

    printers = _get_active_printers()
    if not printers:
        log.warning("print_laybye_deposit: no active printers configured")
        return False

    receipt = _build_receipt(order, receipt_type="Laybye Deposit")
    ok = False
    for printer_name in printers:
        try:
            success = printing_service.print_receipt(receipt, printer_name=printer_name)
            if success:
                log.info("✅ Laybye deposit slip %s printed → %s",
                         order.get("order_no"), printer_name)
                ok = True
            else:
                log.warning("⚠️  Deposit slip print failed on %s", printer_name)
        except Exception as exc:
            log.error("❌ Printer error on %s: %s", printer_name, exc)
    return ok