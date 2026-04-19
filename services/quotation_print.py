from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger("quotation_print")


def _get_active_printers() -> list[str]:
    hw_file = Path("app_data/hardware_settings.json")
    try:
        with open(hw_file, "r", encoding="utf-8") as f:
            hw = json.load(f)
    except Exception as e:
        log.warning("quotation_print: hardware_settings.json missing/invalid — %s", e)
        return []
    names: list[str] = []
    main = (hw.get("main_printer") or "").strip()
    if main:
        names.append(main)
    return names


def _get_company_defaults() -> dict:
    try:
        from models.company_defaults import get_defaults
        return get_defaults() or {}
    except Exception as e:
        log.warning("quotation_print: get_defaults failed — %s", e)
        return {}


def _format_date(raw) -> str:
    if not raw:
        return ""
    if hasattr(raw, "strftime"):
        return raw.strftime("%Y-%m-%d")
    s = str(raw)
    return s.split(" ")[0].split("T")[0]


def _build_receipt(quotation) -> "ReceiptData":
    from models.receipt import ReceiptData, Item, MultiCurrencyDetail

    co = _get_company_defaults()

    customer_name = quotation.customer or "Walk-in Customer"
    quote_date    = _format_date(quotation.transaction_date)
    valid_till    = _format_date(quotation.valid_till)

    # Quotations aren't payments — no tendered/change/deposit. Reuse the
    # customerRef line to print "Valid Till" so it shows prominently.
    customer_ref = f"Valid Till:  {valid_till}" if valid_till else ""

    so_terms = (co.get("terms_and_conditions") or "").strip() or (
        "1. This is a quotation — not a tax invoice.\n"
        "2. Prices are indicative and subject to change.\n"
        "3. Quotation is valid until the date shown above."
    )

    total = float(quotation.grand_total or 0)

    receipt = ReceiptData(
        doc_type    = "sales_order",        # reuse Sales Order print template
        receiptType = "Quotation",          # → heading "*** QUOTATION ***"

        companyName         = co.get("company_name", ""),
        companyAddress      = co.get("address_1",    ""),
        companyAddressLine1 = co.get("address_2",    ""),
        companyEmail        = co.get("email",        ""),
        tel                 = co.get("phone",        ""),
        tin                 = co.get("tin_number",   ""),
        vatNo               = co.get("vat_number",   ""),
        deviceSerial        = "",
        deviceId            = "",

        invoiceNo   = quotation.name or "",
        invoiceDate = quote_date,

        cashierName     = quotation.cashier_name or "",
        customerName    = customer_name,
        customerContact = "",
        customerRef     = customer_ref,

        grandTotal     = total,
        subtotal       = total,
        totalVat       = 0.0,
        amountTendered = 0.0,
        change         = 0.0,
        discAmt        = 0.0,

        paymentMode = "",
        currency    = "USD",
        footer      = co.get("footer_text") or "Thank you for your business!",

        # Leave deliveryDate empty — valid_till is printed via customerRef
        deliveryDate    = "",
        salesOrderTerms = so_terms,
        orderStatus     = quotation.status or "Draft",
    )

    # Summary block — just the total (no deposit/balance)
    receipt.multiCurrencyDetails = [
        MultiCurrencyDetail(key="Total", value=round(total, 2)),
    ]
    receipt.paymentItems = []

    for it in (quotation.items or []):
        qty    = float(getattr(it, "qty",    1) or 1)
        rate   = float(getattr(it, "rate",   0) or 0)
        amount = float(getattr(it, "amount", 0) or (qty * rate))
        receipt.items.append(Item(
            productName = getattr(it, "item_name", "") or getattr(it, "item_code", "") or "",
            productid   = getattr(it, "item_code", "") or "",
            qty         = qty,
            price       = rate,
            amount      = amount,
            tax_amount  = 0.0,
        ))
    receipt.itemlist = receipt.items
    return receipt


def print_quotation(ref) -> bool:
    """
    Print a quotation to the main receipt printer.

    `ref` may be:
      - a Quotation name string (Frappe name, e.g. "QUO-0001")
      - an int local id (for Drafts that haven't been pushed to Frappe)
      - a dict (the row from QuotationsDialog / get_all_quotations().to_dict())
        — we pull name → falls back to local_id if name is blank.
    """
    from models.quotation import get_quotation_by_name, get_quotation_by_local_id
    from services.printing_service import printing_service

    quotation = None
    resolved  = None

    if isinstance(ref, dict):
        name      = (ref.get("name") or "").strip()
        local_id  = ref.get("local_id") or ref.get("id")
        if name:
            quotation = get_quotation_by_name(name)
            resolved  = name
        if quotation is None and local_id:
            quotation = get_quotation_by_local_id(int(local_id))
            resolved  = f"local_id={local_id}"
    elif isinstance(ref, int):
        quotation = get_quotation_by_local_id(ref)
        resolved  = f"local_id={ref}"
    else:
        name = (str(ref) or "").strip()
        if name:
            quotation = get_quotation_by_name(name)
            resolved  = name

    if not quotation:
        log.error("print_quotation: quotation not found (ref=%r, resolved=%r)", ref, resolved)
        return False

    printers = _get_active_printers()
    if not printers:
        log.warning("print_quotation: no active printer configured in "
                    "hardware_settings.json (main_printer)")
        return False

    receipt = _build_receipt(quotation)
    ok = False
    for printer_name in printers:
        try:
            success = printing_service.print_receipt(receipt, printer_name=printer_name)
            if success:
                log.info("Quotation %s printed -> %s", quotation.name or resolved, printer_name)
                ok = True
            else:
                log.warning("Quotation print failed on %s", printer_name)
        except Exception as exc:
            log.error("Printer error on %s: %s", printer_name, exc)
    return ok
