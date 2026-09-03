# =============================================================================
# services/a4_invoice_service.py
#
# Official A4 Full-Page Sales Document Renderer (Odoo QWeb report_sale_document format)
# High-Resolution Pt-scaled Vector Formatting matching native A4 PDF preview standards.
#
# Page geometry mirrors Odoo's paperformat "A4 No Top Margin":
#   format=A4, orientation=Portrait, margin_top=5mm, margin_bottom=5mm,
#   margin_left=7mm, margin_right=7mm, header_line=False, dpi=90
# =============================================================================

import os
import sys
import json
import base64
import logging
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QMessageBox
from PySide6.QtCore import Qt, QSize, QSizeF, QMarginsF, QEventLoop, QTimer
from PySide6.QtGui import QPageSize, QPageLayout

log = logging.getLogger("a4_invoice_service")

# --- Paperformat constants, mirrored from Odoo's <report.paperformat> record ---
PAPER_DPI = 90
MARGIN_TOP_MM = 5
MARGIN_BOTTOM_MM = 5
MARGIN_LEFT_MM = 7
MARGIN_RIGHT_MM = 7


def _get_logo_data_uri(co: dict) -> str:
    """Helper to convert company logo image to base64 data URI for HTML printing."""
    try:
        from database.db import get_app_data_dir
        l_name = co.get("logo_path")
        if not l_name:
            cfg_file = os.path.join(get_app_data_dir(), "logo_config.json")
            if os.path.exists(cfg_file):
                with open(cfg_file, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    l_name = cfg.get("logo_path")
        if l_name:
            l_path = os.path.join(get_app_data_dir(), "logos", l_name)
            if os.path.exists(l_path):
                with open(l_path, "rb") as img_f:
                    b64 = base64.b64encode(img_f.read()).decode("utf-8")
                    ext = os.path.splitext(l_path)[1].replace(".", "").lower()
                    mime = "image/png" if ext == "png" else f"image/{ext}"
                    return f'<img src="data:{mime};base64,{b64}" style="max-height: 34pt; max-width: 80pt; margin-right: 6pt; display: inline-block; vertical-align: middle;" alt="Logo"/>'
    except Exception as e:
        log.warning("Logo load error: %s", e)
    return ""


def render_a4_invoice_html(sale_data: dict | object) -> str:
    """
    Generate clean, high-precision HTML using point-based (pt) sizing for perfect A4 vector rendering.
    """
    from models.company_defaults import get_defaults
    co = get_defaults() or {}

    def _get(key, default=""):
        if isinstance(sale_data, dict):
            return sale_data.get(key, default)
        return getattr(sale_data, key, default)

    company_name = _get("companyName") or co.get("company_name", "HAVANO POS")
    company_name_upper = company_name.upper()
    company_email = _get("companyEmail") or co.get("email", "")
    tin_no = _get("tin") or co.get("tin_number", "N/A")
    vat_no = _get("vatNo") or co.get("vat_number", "N/A")
    address = _get("companyAddress") or co.get("address_1", "")
    address2 = _get("companyAddressLine1") or co.get("address_2", "")
    phone = _get("tel") or co.get("phone", "")
    footer_text = co.get("footer_text") or "Thank you for your business!"

    invoice_no = _get("invoiceNo") or _get("invoice_no") or _get("name") or "N/A"
    raw_date = _get("invoiceDate") or _get("invoice_date") or _get("date") or datetime.now()
    if isinstance(raw_date, datetime):
        invoice_date = raw_date.strftime("%Y-%m-%d")
    elif hasattr(raw_date, "strftime"):
        invoice_date = raw_date.strftime("%Y-%m-%d")
    else:
        invoice_date = str(raw_date).split(" ")[0].split("T")[0]

    currency = _get("currency", "USD") or "USD"
    customer_name = _get("customerName") or _get("customer_name") or "Cash Customer"
    customer_address = _get("customerAddress") or _get("customer_address") or ""
    customer_phone = _get("customerContact") or _get("customer_phone") or ""

    doc_type = str(_get("doc_type") or _get("docType") or "").lower()
    receipt_type = str(_get("receiptType") or _get("receipt_type") or "").upper()
    is_quote = "quotation" in receipt_type.lower() or "quotation" in doc_type or "quote" in receipt_type.lower()
    is_return = "credit" in receipt_type.lower() or "return" in receipt_type.lower() or "credit_note" in doc_type

    if is_quote:
        doc_title = "QUOTATION"
        doc_no_label = "Quote No."
        doc_date_label = "Quote Date"
    elif is_return:
        doc_title = "CREDIT NOTE"
        doc_no_label = "Credit Note No."
        doc_date_label = "Date"
    else:
        doc_title = "INVOICE"
        doc_no_label = "Invoice No."
        doc_date_label = "Date"

    # Validity date for quotations (+14 days)
    valid_until_html = ""
    if is_quote:
        try:
            d_obj = datetime.strptime(invoice_date, "%Y-%m-%d")
            v_date = (d_obj + timedelta(days=14)).strftime("%d %B %Y")
            valid_until_html = f'<tr><td class="prop-label">Valid Until</td><td class="prop-colon">:</td><td>{v_date}</td></tr>'
        except Exception:
            pass

    terms_text = _get("salesOrderTerms") or _get("terms_and_conditions") or co.get("terms_and_conditions", "")
    banking_text = _get("banking_details") or co.get("banking_details", "")

    terms_html = "<br>".join([line.strip() for line in terms_text.strip().splitlines() if line.strip()]) if terms_text.strip() else "<i style='color: #94a3b8;'>Standard terms & conditions apply.</i>"
    banking_html = "<br>".join([line.strip() for line in banking_text.strip().splitlines() if line.strip()]) if banking_text.strip() else "<i style='color: #94a3b8;'>No banking details provided.</i>"

    subtotal = float(_get("subtotal", 0.0) or _get("total", 0.0))
    total_vat = float(_get("totalVat", 0.0) or _get("total_vat", 0.0))
    grand_total = float(_get("grandTotal", 0.0) or _get("total", 0.0))

    # Amount tendered / change (e.g. cash sale) — shown only when tendered > 0
    amount_tendered = float(_get("amountTendered", 0.0) or _get("amount_tendered", 0.0) or _get("tendered", 0.0) or 0.0)
    change_amount = float(_get("change", 0.0) or _get("change_amount", 0.0) or _get("changeAmount", 0.0) or 0.0)

    # ------------------------------------------------------------------
    # PLACEHOLDER: dual-currency conversion (secondary/base currency columns)
    # Wire real values from sale_data / company defaults here. Until then
    # this defaults to a 1:1 rate so the extra columns just mirror the
    # primary currency amounts.
    # TODO: replace with your actual exchange-rate source, e.g.:
    #   exchange_rate = _get("exchangeRate") or _get("exchange_rate") or co.get("exchange_rate", 1.0)
    #   base_currency = _get("baseCurrency") or _get("base_currency") or co.get("base_currency", "USD")
    # ------------------------------------------------------------------
    exchange_rate = float(_get("exchangeRate") or _get("exchange_rate") or co.get("exchange_rate", 1.0) or 1.0)
    base_currency = _get("baseCurrency") or _get("base_currency") or co.get("base_currency", "USD") or "USD"
    show_dual_currency = bool(_get("showDualCurrency", True))  # TODO: wire real flag / just remove if always on

    # Items extraction
    items = []
    raw_items = _get("items") or _get("itemlist") or []
    for it in raw_items:
        if isinstance(it, dict):
            p_name = it.get("product_name") or it.get("productName") or it.get("item_name") or "Item"
            qty = float(it.get("qty", 1))
            price = float(it.get("price", 0.0) or it.get("rate", 0.0))
            tax = float(it.get("tax_amount", 0.0))
            tot = float(it.get("total", 0.0) or it.get("amount", qty * price))
        else:
            p_name = getattr(it, "productName", None) or getattr(it, "item_name", None) or getattr(it, "product_name", "Item")
            qty = float(getattr(it, "qty", 1) or 1)
            price = float(getattr(it, "price", 0.0) or getattr(it, "rate", 0.0))
            tax = float(getattr(it, "tax_amount", 0.0) or 0.0)
            tot = float(getattr(it, "amount", 0.0) or getattr(it, "total", qty * price))
        items.append({
            "name": p_name, "qty": qty, "price": price, "tax": tax, "total": tot,
            # PLACEHOLDER conversion — TODO: replace with a real converted value
            # (per-line rate if it can differ from the document-level rate).
            "tax_conv": tax * exchange_rate,
        })

    # Render table rows matching Odoo report_sale_document main-table
    item_rows_html = ""
    for idx, item in enumerate(items, start=1):
        bg_style = 'style="background-color: #f8fafc;"' if idx % 2 == 0 else ''
        item_rows_html += f"""
        <tr {bg_style}>
            <td class="idx-col">{idx}</td>
            <td class="desc-col">{item['name']}</td>
            <td>{item['qty']:.1f}</td>
            <td>{item['price']:.2f}</td>
            <td>{item['tax']:.2f}</td>
            <td style="font-weight: bold;">{item['total']:.2f}</td>
        </tr>
        """

    exchange_rate_html = f"""
        <div style="font-size: 6.5pt; color: #475569; margin-top: 4pt;">
            Exchange Rate: 1 {currency} = {exchange_rate:.4f} {base_currency}
        </div>
    """ if show_dual_currency else ""

    # Tendered / Change rows — only rendered when a tendered amount was recorded
    tendered_change_html = ""
    if amount_tendered > 0:
        tendered_change_html += f"""
                        <tr>
                            <td style="padding: 2pt 4pt; border: 1pt solid #e2e8f0; font-weight: bold;">AMOUNT TENDERED</td>
                            <td style="padding: 2pt 4pt; border: 1pt solid #e2e8f0;">{currency} {amount_tendered:,.2f}</td>
                        </tr>
                        <tr>
                            <td style="padding: 2pt 4pt; border: 1pt solid #e2e8f0; font-weight: bold; color: #16a34a;">CHANGE</td>
                            <td style="padding: 2pt 4pt; border: 1pt solid #e2e8f0; color: #16a34a; font-weight: bold;">{currency} {change_amount:,.2f}</td>
                        </tr>
        """

    logo_html = _get_logo_data_uri(co)

    # Address block
    full_address = address
    if address2:
        full_address += f", {address2}"

    # ZIMRA Block detection
    zimra_html = ""
    zimra_serial = _get("deviceSerial") or co.get("zimra_serial_no", "")
    zimra_global = _get("fiscalGlobalNo") or _get("fiscal_global_no", "")
    zimra_vcode = _get("verificationCode") or _get("fiscal_verification_code", "")
    zimra_qr = _get("qrCode") or _get("fiscal_qr_code", "")
    zimra_day = _get("fiscalDay") or _get("fiscal_day", "")

    if zimra_serial or zimra_global or zimra_qr:
        qr_img_html = f'<img src="data:image/png;base64,{zimra_qr}" style="width:50pt; height:50pt; display:inline-block;" alt="ZIMRA QR Code"/>' if (len(zimra_qr) > 50) else ''
        zimra_html = f"""
        <div style="margin-top: 8pt; padding: 5pt; border: 1pt solid #0a2342; border-radius: 3pt; background-color: #f8fafc;">
            <table class="w-100" style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="width: 55pt; text-align: center; vertical-align: middle;">
                        {qr_img_html}
                    </td>
                    <td style="vertical-align: middle; padding-left: 5pt; font-size: 6.5pt; line-height: 1.3;">
                        <div style="font-weight: 800; font-size: 7.5pt; color: #0a2342; margin-bottom: 1.5pt;">
                            ZIMRA ELECTRONIC FISCAL VERIFICATION
                        </div>
                        <table class="prop-table" style="font-size: 6.5pt; width: 100%;">
                            {'<tr><td class="font-bold" style="width: 100pt;">Global Invoice No</td><td class="prop-colon">:</td><td>' + zimra_global + '</td></tr>' if zimra_global else ''}
                            {'<tr><td class="font-bold">Verification Code</td><td class="prop-colon">:</td><td>' + zimra_vcode + '</td></tr>' if zimra_vcode else ''}
                            {'<tr><td class="font-bold">EFD Serial Number</td><td class="prop-colon">:</td><td>' + zimra_serial + '</td></tr>' if zimra_serial else ''}
                            {'<tr><td class="font-bold">Fiscal Day</td><td class="prop-colon">:</td><td>' + str(zimra_day) + '</td></tr>' if zimra_day else ''}
                        </table>
                    </td>
                </tr>
            </table>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>{doc_title} - {invoice_no}</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800;900&display=swap');

        body {{
            margin: 0 !important;
            padding: 0 !important;
            background: #ffffff;
            font-family: 'Poppins', 'Helvetica Neue', Helvetica, Arial, sans-serif;
            font-size: 7pt;
            color: #1e293b;
            line-height: 1.3;
        }}
        .print-container {{
            width: 100%;
            margin: 0 !important;
            padding: 0 !important;
            box-sizing: border-box;
            background: #ffffff;
        }}
        .text-primary-dark {{ color: #0a2342; }}
        .bg-primary-dark {{ background-color: #0a2342; color: #ffffff; }}

        .icon-circle {{
            display: inline-block; width: 11pt; height: 11pt;
            background: #0a2342; color: #ffffff; border-radius: 50%;
            text-align: center; line-height: 11pt; margin-right: 3pt; font-size: 6.5pt;
        }}

        .w-100 {{ width: 100%; border-collapse: collapse; }}
        .w-50 {{ width: 50%; vertical-align: top; }}
        .w-40 {{ width: 40%; }}
        .w-60 {{ width: 60%; }}
        .text-left {{ text-align: left; }}
        .text-right {{ text-align: right; }}
        .text-center {{ text-align: center; }}
        .align-top {{ vertical-align: top; }}
        .align-middle {{ vertical-align: middle; }}
        .font-bold {{ font-weight: bold; }}

        /* Fixed table layout so column widths below are respected exactly
           instead of the browser auto-sizing them from cell content
           (which is what was causing the columns to look misaligned/broken). */
        .main-table {{ width: 100%; border-collapse: collapse; margin-top: 6pt; table-layout: fixed; }}
        .main-table th {{ background: #0a2342; color: #ffffff; padding: 3pt 4pt; font-size: 7pt; border: 1pt solid #ffffff; text-align: center; word-wrap: break-word; }}
        .main-table td {{ padding: 3pt 4pt; border: 1pt solid #e2e8f0; text-align: center; font-size: 7pt; word-wrap: break-word; }}
        .main-table td.desc-col {{ text-align: left; font-weight: 500; }}
        .main-table td.idx-col {{ font-weight: bold; }}

        .prop-table {{ width: 100%; border-collapse: collapse; font-size: 7pt; }}
        .prop-table td {{ padding: 1.5pt 0; vertical-align: top; }}
        .prop-label {{ font-weight: bold; width: 70pt; }}
        .prop-colon {{ width: 8pt; text-align: center; }}
    </style>
</head>
<body>
    <div class="print-container">
        <!-- Top Center Title -->
        <div class="text-center" style="margin-top: 0px; margin-bottom: 6pt;">
            <span style="font-size: 10pt; font-weight: 800; letter-spacing: 2pt; color: #0a2342; display: inline-block;">
                &mdash;&mdash;&nbsp;&nbsp;{doc_title}&nbsp;&nbsp;&mdash;&mdash;
            </span>
        </div>

        <!-- Top Header Row -->
        <table class="w-100" style="margin-bottom: 6pt; border-bottom: 1.5pt solid #0a2342; padding-bottom: 5pt; border-collapse: collapse;">
            <tr>
                <!-- Left: Logo & Company Name -->
                <td class="w-50 align-middle text-left">
                    <div style="display: flex; align-items: center;">
                        {logo_html}
                        <div>
                            <h1 style="color: #0a2342; font-size: 10.5pt; font-weight: 800; margin: 0; line-height: 1.1;">
                                {company_name_upper}
                            </h1>
                        </div>
                    </div>
                </td>
                <!-- Right: Contact Details -->
                <td class="w-50 align-middle text-right" style="font-size: 6.5pt; line-height: 1.3;">
                    <table style="margin-left: auto; border-collapse: collapse;">
                        <tr><td style="padding-bottom: 1pt; text-align: left; vertical-align: top; font-weight: bold;">{company_name_upper}</td></tr>
                        {'<tr><td style="padding-bottom: 1pt; text-align: left; vertical-align: top;">📍 ' + full_address + '</td></tr>' if full_address else ''}
                        {'<tr><td style="padding-bottom: 1pt; text-align: left; vertical-align: top;">📞 ' + phone + '</td></tr>' if phone else ''}
                        {'<tr><td style="padding-bottom: 1pt; text-align: left; vertical-align: top;">✉ ' + company_email + '</td></tr>' if company_email else ''}
                        <tr>
                            <td style="padding-bottom: 1pt; text-align: left; vertical-align: top;">
                                <span class="font-bold">TIN:</span> {tin_no} &nbsp;|&nbsp; <span class="font-bold">VAT No:</span> {vat_no}
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>

        <!-- Mid Section: Customer & Document Info -->
        <table class="w-100" style="margin-bottom: 6pt; border-collapse: collapse;">
            <tr>
                <!-- Customer Info -->
                <td class="w-50 align-top" style="padding-right: 8pt;">
                    <div style="margin-bottom: 3pt; display: flex; align-items: center;">
                        <span class="icon-circle">👤</span>
                        <span class="text-primary-dark font-bold" style="font-size: 7pt;">CUSTOMER DETAILS</span>
                    </div>
                    <table class="prop-table">
                        <tr>
                            <td class="prop-label">Customer Name</td><td class="prop-colon">:</td>
                            <td>{customer_name}</td>
                        </tr>
                        {'<tr><td class="prop-label">Address</td><td class="prop-colon">:</td><td>' + customer_address + '</td></tr>' if customer_address else ''}
                        {'<tr><td class="prop-label">Phone</td><td class="prop-colon">:</td><td>' + customer_phone + '</td></tr>' if customer_phone else ''}
                    </table>
                </td>

                <!-- Document Info -->
                <td class="w-50 align-top" style="border-left: 1.5pt solid #e2e8f0; padding-left: 8pt;">
                    <table class="prop-table" style="margin-left: 3pt;">
                        <tr>
                            <td class="prop-label">{doc_no_label}</td>
                            <td class="prop-colon">:</td>
                            <td>{invoice_no}</td>
                        </tr>
                        <tr>
                            <td class="prop-label">{doc_date_label}</td>
                            <td class="prop-colon">:</td>
                            <td>{invoice_date}</td>
                        </tr>
                        {valid_until_html}
                        <tr>
                            <td class="prop-label">Currency</td><td class="prop-colon">:</td>
                            <td>{currency}</td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>

        <!-- Order Lines Table -->
        <table class="main-table">
            <thead>
                <tr>
                    <th style="width: 5%;">#</th>
                    <th class="text-left" style="width: 32%;">Description</th>
                    <th style="width: 8%;">Qty</th>
                    <th style="width: 18%;">Unit Price ({currency})</th>
                    <th style="width: 18%;">Tax Amount ({currency})</th>
                    <th style="width: 19%;">Total Amount ({currency})</th>
                </tr>
            </thead>
            <tbody>
                {item_rows_html}
            </tbody>
        </table>

        <!-- Totals Section -->
        <table class="w-100" style="margin-top: 5pt; border-collapse: collapse;">
            <tr>
                <td class="w-60"></td>
                <td class="w-40 text-right">
                    <table style="width: 100%; border-collapse: collapse; text-align: right; font-size: 7pt;">
                        <tr>
                            <td style="padding: 2pt 4pt; border: 1pt solid #e2e8f0; font-weight: bold;">SUBTOTAL (Excl. Tax)</td>
                            <td style="padding: 2pt 4pt; border: 1pt solid #e2e8f0; width: 45%;">{currency} {subtotal:,.2f}</td>
                        </tr>
                        <tr>
                            <td style="padding: 2pt 4pt; border: 1pt solid #e2e8f0; font-weight: bold;">TOTAL TAX</td>
                            <td style="padding: 2pt 4pt; border: 1pt solid #e2e8f0;">{currency} {total_vat:,.2f}</td>
                        </tr>
                        <tr class="bg-primary-dark">
                            <td style="padding: 3.5pt 4pt; font-weight: bold; font-size: 7.5pt; color: #ffffff;">TOTAL (Incl. Tax)</td>
                            <td style="padding: 3.5pt 4pt; font-weight: bold; font-size: 8pt; color: #ffffff;">{currency} {grand_total:,.2f}</td>
                        </tr>
                        {tendered_change_html}
                    </table>
                </td>
            </tr>
        </table>
        {exchange_rate_html}

        <!-- Bottom Footer Section -->
        <table class="w-100" style="margin-top: 10pt; margin-bottom: 5pt; border-collapse: collapse;">
            <tr>
                <!-- Left: Terms & Conditions -->
                <td class="w-50 align-top" style="padding-right: 8pt;">
                    <div style="margin-bottom: 3pt; border-bottom: 1pt solid #0a2342; padding-bottom: 1.5pt; width: 100%;">
                        <span class="icon-circle">📄</span>
                        <span class="text-primary-dark font-bold" style="font-size: 7pt;">TERMS &amp; CONDITIONS</span>
                    </div>
                    <div style="font-size: 6.5pt; line-height: 1.25; color: #334155; min-height: 22pt;">
                        {terms_html}
                    </div>

                    <!-- Signature -->
                    <div style="margin-top: 8pt;">
                        <div style="border-bottom: 1pt dashed #0a2342; width: 110pt; height: 12pt; margin-bottom: 1.5pt;"></div>
                        <div style="font-weight: bold; font-size: 6.5pt;">Authorised Signatory</div>
                        <div style="font-size: 6.5pt; color: #0a2342; font-weight: bold;">{company_name_upper}</div>
                    </div>
                </td>

                <!-- Right: Banking Details -->
                <td class="w-50 align-top" style="padding-left: 8pt;">
                    <div style="margin-bottom: 3pt; border-bottom: 1pt solid #0a2342; padding-bottom: 1.5pt; width: 100%;">
                        <span class="icon-circle">🏦</span>
                        <span class="text-primary-dark font-bold" style="font-size: 7pt;">BANKING DETAILS</span>
                    </div>
                    <div style="font-size: 6.5pt; line-height: 1.25; color: #334155; margin-bottom: 5pt;">
                        {banking_html}
                    </div>

                    <!-- Thank you message -->
                    <div style="margin-top: 6pt; display: flex; align-items: center;">
                        <span class="icon-circle" style="font-size: 7pt; width: 14pt; height: 14pt; line-height: 14pt;">🤝</span>
                        <div style="margin-left: 4pt;">
                            <div class="text-primary-dark font-bold" style="font-size: 7pt;">Thank you for your business!</div>
                            <div style="font-size: 6.5pt; color: #475569;">{footer_text}</div>
                        </div>
                    </div>
                </td>
            </tr>
        </table>

        {zimra_html}

        <!-- Very Bottom Banner -->
        <div class="bg-primary-dark text-center" style="padding: 3pt; font-size: 6.5pt; font-weight: bold; margin-top: 6pt; color: #ffffff;">
            Powered by HavanoERP
        </div>
    </div>
</body>
</html>
"""
    return html


def _html_to_pdf(html_content: str, pdf_path: str, timeout_ms: int = 15000) -> None:
    """
    Renders `html_content` to `pdf_path` using a real Chromium engine
    (QWebEngineView), so full CSS (flexbox, fonts, emoji, etc.) is honoured
    exactly as it would be in a browser, and the resulting PDF page is
    genuinely A4-sized — no QTextDocument pt/dpi guesswork involved.

    This function pumps a local QEventLoop, so it must be called from the
    Qt GUI thread (same as the old QTextDocument/QPrinter approach).
    """
    from PySide6.QtWebEngineWidgets import QWebEngineView

    view = QWebEngineView()
    view.setHtml(html_content)

    # Wait for the page to finish loading before printing it.
    load_loop = QEventLoop()
    load_ok = {"ok": False}

    def _on_load_finished(ok):
        load_ok["ok"] = ok
        load_loop.quit()

    view.loadFinished.connect(_on_load_finished)
    QTimer.singleShot(timeout_ms, load_loop.quit)  # safety timeout
    load_loop.exec()

    if not load_ok["ok"]:
        raise RuntimeError("Failed to load invoice HTML in QWebEngineView.")

    # A4, portrait, margins matching Odoo's paperformat exactly.
    page_layout = QPageLayout(
        QPageSize(QPageSize.PageSizeId.A4),
        QPageLayout.Orientation.Portrait,
        QMarginsF(MARGIN_LEFT_MM, MARGIN_TOP_MM, MARGIN_RIGHT_MM, MARGIN_BOTTOM_MM),
        QPageLayout.Unit.Millimeter,
    )

    print_loop = QEventLoop()
    print_ok = {"ok": False}

    def _on_pdf_finished(path, ok):
        print_ok["ok"] = ok
        print_loop.quit()

    view.page().pdfPrintingFinished.connect(_on_pdf_finished)
    view.page().printToPdf(pdf_path, page_layout)
    QTimer.singleShot(timeout_ms, print_loop.quit)  # safety timeout
    print_loop.exec()

    if not print_ok["ok"] or not os.path.exists(pdf_path):
        raise RuntimeError("QWebEngine failed to print the invoice to PDF.")

    # Keep the view alive until printToPdf's signal has actually fired above;
    # safe to drop the reference now that we're done with it.
    view.deleteLater()


def show_a4_invoice_preview(sale_data: dict | object, parent=None):
    """
    Renders the A4 Tax Invoice/Quotation with correct A4 page geometry (matching
    Odoo's 'A4 No Top Margin' paperformat: 5mm top/bottom, 7mm left/right)
    and launches PdfPreviewDialog.
    """
    try:
        import tempfile, os
        from views.dialogs.pdf_preview_dialog import PdfPreviewDialog

        html_content = render_a4_invoice_html(sale_data)

        inv_no = (
            getattr(sale_data, 'invoiceNo', None)
            or (sale_data.get('invoice_no') if isinstance(sale_data, dict) else None)
            or getattr(sale_data, 'name', None)
            or 'Invoice'
        )
        safe_inv_no = "".join([c if c.isalnum() else "_" for c in str(inv_no)])
        pdf_path = os.path.join(tempfile.gettempdir(), f"Doc_{safe_inv_no}.pdf")

        _html_to_pdf(html_content, pdf_path)

        dlg = PdfPreviewDialog(pdf_path, title=f"Preview: {inv_no}", parent=parent)
        dlg.exec()
        return True

    except Exception as exc:
        log.error("Failed to show A4 Preview: %s", exc, exc_info=True)
        if parent:
            QMessageBox.critical(parent, "Preview Error", f"Could not generate A4 Preview:\n{exc}")
        return False