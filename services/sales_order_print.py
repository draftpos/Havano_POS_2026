# =============================================================================
# services/sales_order_print.py  —  Sales Order / Laybye receipt printing
#
# Produces a receipt that is visually and structurally distinct from a normal
# POS sales invoice:
#
#   doc_type = "sales_order"   → PrintingService routes to the SO template
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
#   │   Customer: John Doe               │
#   ├─────────────────────────────────────┤
#   │   # | Item          | Qty | Amount  │
#   │   1 | Widget A      |   2 | 10.00   │
#   │   2 | Widget B      |   1 |  5.00   │
#   ├─────────────────────────────────────┤
#   │   Order Total:   USD 15.00          │  ← multiCurrencyDetails rows
#   │   Deposit Paid:  USD  5.00          │
#   │   Balance Due:   USD 10.00          │
#   ├─────────────────────────────────────┤
#   │   Forms of Payment                  │
#   │   CASH                   3.00       │  ← ALL payment methods listed
#   │   ECOCASH               2.00        │
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
# Default terms printed on every Sales Order slip if nothing is saved in
# company_defaults.terms_and_conditions yet.
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

    FIXED: Reads deposit_methods (list) for multi-payment support, falls back
           to single deposit_method string for backward compatibility.
    FIXED: salesOrderTerms is always populated — from DB or built-in default —
           so terms never silently disappear from the printed slip.
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

    # ── Terms — use company_defaults.terms_and_conditions, else built-in default
    # Always guaranteed to be a non-empty string so the printer never skips it.
    so_terms = (
        co.get("terms_and_conditions")
        or _DEFAULT_SO_TERMS
    )

    # ── Footer ────────────────────────────────────────────────────────────────
    base_footer = co.get("footer_text") or "Thank you for your business!"

    # ── Receipt-type-specific fields ──────────────────────────────────────────
    if receipt_type == "Laybye Deposit":
        tendered     = deposit_amount
        change       = 0.0
        customer_ref = f"BALANCE DUE:  {order.get('currency', 'USD')} {balance_due:.2f}"
        footer       = base_footer
    else:
        tendered     = total
        change       = 0.0
        customer_ref = ""
        footer       = base_footer

    # ── Payment methods — support BOTH multi-payment list AND single string ───
    #
    # New orders save:  deposit_methods = [{"method": "CASH", "amount": 50.0},
    #                                      {"method": "ECOCASH", "amount": 30.0}]
    # Old orders save:  deposit_method  = "CASH"   (single string, no list)
    #
    raw_methods   = order.get("deposit_methods") or []   # preferred: list of dicts
    single_method = order.get("deposit_method",  "") or ""  # fallback: plain string

    payment_items: list[Item] = []

    if raw_methods:
        # Multi-payment: build one Item per method
        for pm in raw_methods:
            m_name   = str(pm.get("method", "Payment"))
            m_amount = float(pm.get("amount", 0.0))
            payment_items.append(Item(
                productName = m_name,
                qty         = 1,
                price       = m_amount,
                amount      = m_amount,
                tax_amount  = 0.0,
            ))
        payment_mode_str = " + ".join(pm.get("method", "") for pm in raw_methods)
    elif single_method:
        # Legacy single-method order
        payment_items.append(Item(
            productName = single_method,
            qty         = 1,
            price       = deposit_amount,
            amount      = deposit_amount,
            tax_amount  = 0.0,
        ))
        payment_mode_str = single_method
    else:
        payment_mode_str = ""

    receipt = ReceiptData(
        # ── Routing: tells PrintingService to use the SO template ─────────────
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
        # Intentionally NOT setting deviceSerial / deviceId — not a fiscal doc
        deviceSerial        = "",
        deviceId            = "",

        # ── Order reference ───────────────────────────────────────────────────
        invoiceNo   = order.get("order_no", ""),
        invoiceDate = order_date,

        # ── Cashier / customer ────────────────────────────────────────────────
        cashierName     = "",
        customerName    = customer_name,
        customerContact = customer_contact,
        customerRef     = customer_ref,

        # ── Totals ────────────────────────────────────────────────────────────
        grandTotal     = total,
        subtotal       = total,
        totalVat       = 0.0,
        amountTendered = tendered,
        change         = change,
        discAmt        = 0.0,

        # ── Payment ───────────────────────────────────────────────────────────
        paymentMode = payment_mode_str,    # "CASH + ECOCASH" or single name
        currency    = order.get("currency", "USD"),
        footer      = footer,

        # ── Sales-Order-specific ──────────────────────────────────────────────
        deliveryDate    = delivery_date,
        salesOrderTerms = so_terms,        # always non-empty — guaranteed above
        orderStatus     = order_status,
    )

    # ── Deposit / balance summary (multiCurrencyDetails rows) ─────────────────
    receipt.multiCurrencyDetails = [
        MultiCurrencyDetail(key="Order Total",  value=round(total,          2)),
        MultiCurrencyDetail(key="Deposit Paid", value=round(deposit_amount, 2)),
        MultiCurrencyDetail(key="Balance Due",  value=round(balance_due,    2)),
    ]

    # ── Payment method items — stored separately so they don't mix with
    #    product line items in the items table
    receipt.paymentItems = payment_items

    # ── Line items (products) ─────────────────────────────────────────────────
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

    # Keep itemlist in sync (backward-compat)
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
      • Forms of Payment — ALL methods listed (Cash, EcoCash, etc.)
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
      • Forms of Payment — ALL methods listed (Cash, EcoCash, etc.)
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