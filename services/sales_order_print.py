# =============================================================================
# services/sales_order_print.py  —  Sales Order / Laybye receipt printing
#
# Drop-in alongside sale.py.  Zero changes to sale.py or payment_dialog.py.
#
# Public API
# ----------
#   print_sales_order(order_id)          — print the full order receipt
#   print_laybye_deposit(order_id)       — print a deposit confirmation slip
#
# Both functions follow the exact same pattern used in sale.py:
#   1. Load company defaults (company_defaults table)
#   2. Build a ReceiptData object
#   3. Resolve active printers from hardware_settings.json
#   4. Call printing_service.print_receipt() for each printer
# =============================================================================

from __future__ import annotations
import json
import logging
from pathlib import Path
from datetime import datetime

log = logging.getLogger("sales_order_print")


# =============================================================================
# Internal helpers  (mirrors sale.py helpers — no shared state)
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


def _format_order_date(raw: str) -> str:
    """Return a printable date string from an ISO date/datetime."""
    if not raw:
        return datetime.today().strftime("%Y-%m-%d")
    try:
        return datetime.fromisoformat(raw).strftime("%Y-%m-%d")
    except Exception:
        return raw


# =============================================================================
# Core builder  — constructs the ReceiptData for a sales order
# =============================================================================

def _build_receipt(order: dict, receipt_type: str = "Sales Order") -> "ReceiptData":
    """
    Map a sales_order dict (from get_order_by_id) to a ReceiptData object.

    receipt_type:
        "Sales Order"  — full order, shows grand total
        "Laybye Deposit" — deposit slip, shows deposit paid + balance due
    """
    from models.receipt import ReceiptData, Item

    co = _get_company_defaults()

    # ── Customer fields ───────────────────────────────────────────────────────
    customer_name    = order.get("customer_name") or "Walk-in Customer"
    customer_contact = ""                           # sales_order has no contact col (yet)

    # ── Money fields ──────────────────────────────────────────────────────────
    total          = float(order.get("total",          0))
    deposit_amount = float(order.get("deposit_amount", 0))
    balance_due    = float(order.get("balance_due",    0))

    # For a deposit slip the "tendered" is the deposit; for a full order it is
    # the total (full payment scenario).
    if receipt_type == "Laybye Deposit":
        tendered = deposit_amount
        change   = 0.0
        footer   = (co.get("footer_text") or
                    "Thank you!  Please keep this slip — "
                    f"Balance due: USD {balance_due:.2f}")
    else:
        tendered = total
        change   = 0.0
        footer   = co.get("footer_text") or "Thank you for your purchase!"

    receipt = ReceiptData(
        receiptType    = receipt_type,

        # Company info
        companyName         = co.get("company_name", ""),
        companyAddress      = co.get("address_1",    ""),
        companyAddressLine1 = co.get("address_2",    ""),
        companyEmail        = co.get("email",         ""),
        tel                 = co.get("phone",         ""),
        tin                 = co.get("tin_number",    ""),
        vatNo               = co.get("vat_number",    ""),
        deviceSerial        = co.get("zimra_serial_no", ""),
        deviceId            = co.get("zimra_device_id", ""),

        # Order / invoice reference
        invoiceNo   = order.get("order_no", ""),
        invoiceDate = _format_order_date(order.get("order_date", "")),

        # Cashier / customer
        cashierName     = "",          # sales orders are not tied to a cashier
        customerName    = customer_name,
        customerContact = customer_contact,

        # Totals
        grandTotal      = total,
        subtotal        = total,       # no VAT breakdown on orders (add if needed)
        totalVat        = 0.0,
        amountTendered  = tendered,
        change          = change,
        discAmt         = 0.0,

        # Payment
        paymentMode     = order.get("deposit_method", ""),
        currency        = "USD",
        footer          = footer,
    )

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
    Print a full Sales Order receipt.

    Mirrors the pattern in sale.py create_sale():
        order  = get_order_by_id(order_id)
        receipt = _build_receipt(order, "Sales Order")
        printing_service.print_receipt(receipt, printer_name=...)

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
                log.warning("⚠️  Print failed on %s", printer_name)
        except Exception as exc:
            log.error("❌ Printer error on %s: %s", printer_name, exc)
    return ok


def print_laybye_deposit(order_id: int) -> bool:
    """
    Print a Laybye deposit confirmation slip.

    Same printer resolution + ReceiptData pipeline as print_sales_order(),
    but receiptType = "Laybye Deposit" and amountTendered = deposit_amount.
    The footer automatically shows the remaining balance.

    Call this right after LaybyePaymentDialog.accept() and create_sales_order().

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