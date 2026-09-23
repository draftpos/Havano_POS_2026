# =============================================================================
# services/a4_invoice_service.py
#
# Official A4 Full-Page Sales Document Renderer (Odoo QWeb report_sale_document format)
# High-Resolution Pt-scaled Vector Formatting matching native A4 PDF preview standards.
#
# Page geometry mirrors Odoo's paperformat "A4 No Top Margin":
#   format=A4, orientation=Portrait, margin_top=5mm, margin_bottom=5mm,
#   margin_left=7mm, margin_right=7mm, header_line=False, dpi=90
#
# CROSS-MACHINE RELIABILITY NOTES (read before touching the CSS):
#   1. NEVER load fonts from the internet (@import url(fonts.googleapis.com...)).
#      If the target PC has no internet access (or is firewalled), the font
#      silently falls back to whatever's on that machine, and every line
#      height / wrap point shifts -> "layout looks different on other PCs".
#      Fonts are now embedded as base64 @font-face (see _get_embedded_font_css)
#      with a safe system-font fallback stack if the .ttf files aren't bundled.
#   2. NEVER use emoji characters (👤📄🏦 etc.) for icons. Emoji glyphs are
#      drawn by the OS's colour-emoji font, which varies by machine (some
#      Windows/Linux boxes have none) -> icons render as blank boxes on some
#      PCs. Icons are now inline SVG (see _icon_svg), which render identically
#      everywhere because they're vector paths, not font glyphs.
#   3. QWebEngineView (Chromium) can fail to initialize on machines with
#      unusual/older GPU drivers and silently fall back to QTextDocument,
#      which does NOT support flexbox/position/etc. -> broken header layout.
#      We now force software rendering via QTWEBENGINE_CHROMIUM_FLAGS so the
#      GPU driver is taken out of the equation entirely.
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

# Printable page height in pt, used to force the footer to the true bottom
# of the A4 page regardless of how little content is on the invoice.
# A4 = 297mm tall. Minus top/bottom margins -> printable height.
# 1mm = 72/25.4 pt
_MM_TO_PT = 72.0 / 25.4
PAGE_CONTENT_HEIGHT_PT = round((297 - MARGIN_TOP_MM - MARGIN_BOTTOM_MM) * _MM_TO_PT, 1)  # ~813.3pt


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


def _get_embedded_font_css() -> str:
    """
    Embeds bundled Poppins .ttf files (if present) as base64 @font-face rules
    so the invoice renders with the exact same typeface, weights, line-height
    and wrapping on EVERY machine, with zero internet dependency and zero
    reliance on Poppins being installed system-wide.

    Expected bundle layout (ship these alongside the app / add to PyInstaller
    as data files):
        <app_dir>/assets/fonts/Poppins-Regular.ttf    (weight 400)
        <app_dir>/assets/fonts/Poppins-Medium.ttf     (weight 500)
        <app_dir>/assets/fonts/Poppins-SemiBold.ttf   (weight 600)
        <app_dir>/assets/fonts/Poppins-Bold.ttf       (weight 700)
        <app_dir>/assets/fonts/Poppins-ExtraBold.ttf  (weight 800)

    If none are found (e.g. not bundled yet), this returns "" and the CSS
    font-family fallback stack (system-safe fonts) is used instead -- so the
    document still looks correct and IDENTICAL across machines, just with a
    different (but universally available) typeface.
    """
    try:
        # sys._MEIPASS is set inside a PyInstaller onefile/onefolder bundle.
        base_dir = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
        fonts_dir = os.path.join(base_dir, "assets", "fonts")
        weights = {
            "400": "Poppins-Regular.ttf",
            "500": "Poppins-Medium.ttf",
            "600": "Poppins-SemiBold.ttf",
            "700": "Poppins-Bold.ttf",
            "800": "Poppins-ExtraBold.ttf",
        }
        face_rules = []
        for weight, fname in weights.items():
            fpath = os.path.join(fonts_dir, fname)
            if os.path.exists(fpath):
                with open(fpath, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                face_rules.append(f"""
        @font-face {{
            font-family: 'Poppins';
            font-style: normal;
            font-weight: {weight};
            font-display: block;
            src: url(data:font/truetype;base64,{b64}) format('truetype');
        }}""")
        return "\n".join(face_rules)
    except Exception as e:
        log.warning("Embedded font load error (falling back to system fonts): %s", e)
        return ""


def _icon_svg(name: str, size: float = 8, color: str = "#ffffff") -> str:
    """
    Tiny inline vector icons used instead of emoji. Emoji glyphs are drawn by
    whatever colour-emoji font happens to be installed on a given machine
    (many Windows Server / minimal Linux boxes have none at all), which is a
    common cause of icons silently disappearing on "some other computer".
    SVG paths render identically everywhere because there's no font lookup.
    """
    icons = {
        "pin": f'<svg width="{size}pt" height="{size}pt" viewBox="0 0 24 24" fill="{color}" style="vertical-align:middle;"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5A2.5 2.5 0 1 1 12 6.5a2.5 2.5 0 0 1 0 5z"/></svg>',
        "phone": f'<svg width="{size}pt" height="{size}pt" viewBox="0 0 24 24" fill="{color}" style="vertical-align:middle;"><path d="M6.6 10.8c1.4 2.8 3.8 5.1 6.6 6.6l2.2-2.2c.3-.3.7-.4 1-.2 1.1.4 2.3.6 3.6.6.6 0 1 .4 1 1V20c0 .6-.4 1-1 1C10.9 21 3 13.1 3 3.9c0-.6.4-1 1-1H7.6c.6 0 1 .4 1 1 0 1.3.2 2.5.6 3.6.1.4 0 .8-.2 1L6.6 10.8z"/></svg>',
        "mail": f'<svg width="{size}pt" height="{size}pt" viewBox="0 0 24 24" fill="{color}" style="vertical-align:middle;"><path d="M20 4H4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2zm0 4-8 5-8-5V6l8 5 8-5v2z"/></svg>',
        "user": f'<svg width="{size}pt" height="{size}pt" viewBox="0 0 24 24" fill="{color}" style="vertical-align:middle;"><path d="M12 12a5 5 0 1 0 0-10 5 5 0 0 0 0 10zm0 2c-4.4 0-8 2.2-8 5v2h16v-2c0-2.8-3.6-5-8-5z"/></svg>',
        "doc": f'<svg width="{size}pt" height="{size}pt" viewBox="0 0 24 24" fill="{color}" style="vertical-align:middle;"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6zm0 6V3.5L18.5 8H14z"/></svg>',
        "bank": f'<svg width="{size}pt" height="{size}pt" viewBox="0 0 24 24" fill="{color}" style="vertical-align:middle;"><path d="M12 2 2 8v2h20V8L12 2zM4 11v8H2v2h20v-2h-2v-8h-2v8h-3v-8h-2v8h-3v-8H6v8H4v-8z"/></svg>',
        "shake": f'<svg width="{size}pt" height="{size}pt" viewBox="0 0 24 24" fill="{color}" style="vertical-align:middle;"><path d="M11 7 8 4 2 10l3 3 1-1 5 5 2-2-5-5 1-1 3 3 3-3-3-3-1 1z"/></svg>',
    }
    return icons.get(name, "")


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
    is_quote = "quotation" in receipt_type.lower() or "quotation" in doc_type or "quote" in receipt_type.lower() or bool(_get("is_quote")) or bool(_get("is_quotation"))
    is_return = "credit" in receipt_type.lower() or "return" in receipt_type.lower() or "credit_note" in doc_type or "credit" in doc_type or bool(_get("is_return")) or bool(_get("is_credit_note"))
    is_order = "order" in receipt_type.lower() or "take away" in receipt_type.lower() or "takeaway" in receipt_type.lower() or "sit in" in receipt_type.lower() or "sitin" in receipt_type.lower()

    original_invoice_no = (
        _get("originalInvoiceNo")
        or _get("original_invoice_no")
        or _get("orig_invoice")
        or _get("invoice_no") if is_return else ""
    )
    if is_return and str(original_invoice_no) == str(invoice_no):
        original_invoice_no = ""

    return_reason = (
        _get("creditNoteReason")
        or _get("return_reason")
        or _get("reason")
        or ""
    )
    cashier_name = _get("cashierName") or _get("cashier_name") or ""

    if is_quote:
        doc_title = "QUOTATION"
        doc_no_label = "Quote No."
        doc_date_label = "Quote Date"
    elif is_return:
        doc_title = "CREDIT NOTE"
        doc_no_label = "Credit Note No."
        doc_date_label = "Date"
    elif is_order:
        doc_title = "ORDER"
        doc_no_label = "Order No."
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

    # Original Invoice & Reason metadata for Credit Notes
    credit_note_meta_html = ""
    if is_return:
        cn_meta_rows = []
        if original_invoice_no:
            cn_meta_rows.append(f'<tr><td class="prop-label">Orig. Invoice</td><td class="prop-colon">:</td><td style="font-weight: bold; color: #0a2342;">{original_invoice_no}</td></tr>')
        if return_reason:
            cn_meta_rows.append(f'<tr><td class="prop-label">Reason</td><td class="prop-colon">:</td><td>{return_reason}</td></tr>')
        if cashier_name:
            cn_meta_rows.append(f'<tr><td class="prop-label">Cashier</td><td class="prop-colon">:</td><td>{cashier_name}</td></tr>')
        credit_note_meta_html = "".join(cn_meta_rows)

    if is_quote:
        terms_text = (co.get("quotation_terms") or "").strip() or (co.get("terms_and_conditions") or "").strip() or _get("quotation_terms") or _get("salesOrderTerms")
    elif is_return:
        terms_text = (co.get("credit_note_terms") or "").strip() or (co.get("terms_and_conditions") or "").strip() or _get("credit_note_terms")
    else:
        terms_text = (co.get("terms_and_conditions") or "").strip() or _get("salesOrderTerms") or _get("terms_and_conditions")
    banking_text = (co.get("banking_details") or "").strip() or _get("banking_details") or ""

    if is_return and not terms_text.strip():
        terms_html = "1. This Credit Note is issued in accordance with our return and refund policy.<br>2. Store credit or refund will be processed as stated."
    elif is_quote and not terms_text.strip():
        terms_html = "1. This is a quotation - not a tax invoice.<br>2. Prices are indicative and subject to change.<br>3. Quotation is valid until the date shown above."
    elif terms_text.strip():
        terms_html = "<br>".join([line.strip() for line in terms_text.strip().splitlines() if line.strip()])
    else:
        terms_html = "<i style='color: #94a3b8;'>Standard terms & conditions apply.</i>"

    banking_html = "<br>".join([line.strip() for line in banking_text.strip().splitlines() if line.strip()]) if banking_text.strip() else "<i style='color: #94a3b8;'>No banking details provided.</i>"

    subtotal = float(_get("subtotal", 0.0) or _get("total", 0.0))
    total_vat = float(_get("totalVat", 0.0) or _get("total_vat", 0.0))
    grand_total = float(_get("grandTotal", 0.0) or _get("total", 0.0))

    # Amount tendered / change (e.g. cash sale) — shown only when tendered > 0
    amount_tendered = float(_get("amountTendered", 0.0) or _get("amount_tendered", 0.0) or _get("tendered", 0.0) or 0.0)
    change_amount = float(_get("change", 0.0) or _get("change_amount", 0.0) or _get("changeAmount", 0.0) or 0.0)


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
        })

    # Render table rows matching Odoo report_sale_document main-table
    item_rows_html = ""
    for idx, item in enumerate(items, start=1):
        bg_style = 'style="background-color: #f8fafc;"' if idx % 2 == 0 else ''
        item_rows_html += f"""
        <tr {bg_style}>
            <td class="idx-col" style="text-align: center; padding: 4pt 4pt; border: 1pt solid #e2e8f0; font-size: 8.5pt;">{idx}</td>
            <td class="desc-col" style="text-align: left; padding: 4pt 6pt; border: 1pt solid #e2e8f0; font-size: 8.5pt; font-weight: 500;">{item['name']}</td>
            <td style="text-align: center; padding: 4pt 4pt; border: 1pt solid #e2e8f0; font-size: 8.5pt;">{item['qty']:.1f}</td>
            <td style="text-align: right; padding: 4pt 6pt; border: 1pt solid #e2e8f0; font-size: 8.5pt;">{item['price']:,.2f}</td>
            <td style="text-align: right; padding: 4pt 6pt; border: 1pt solid #e2e8f0; font-size: 8.5pt;">{item['tax']:,.2f}</td>
            <td style="text-align: right; padding: 4pt 6pt; border: 1pt solid #e2e8f0; font-size: 8.5pt; font-weight: bold;">{item['total']:,.2f}</td>
        </tr>
        """

    # Tendered / Change rows — only rendered when a tendered amount was recorded
    tendered_change_html = ""
    if amount_tendered > 0:
        tendered_change_html += f"""
                        <tr>
                            <td style="padding: 3pt 5pt; border: 1pt solid #e2e8f0; font-weight: bold; font-size: 8.5pt; text-align: left;">AMOUNT TENDERED</td>
                            <td style="padding: 3pt 5pt; border: 1pt solid #e2e8f0; font-size: 8.5pt; text-align: right;">{currency} {amount_tendered:,.2f}</td>
                        </tr>
                        <tr>
                            <td style="padding: 3pt 5pt; border: 1pt solid #e2e8f0; font-weight: bold; color: #16a34a; font-size: 8.5pt; text-align: left;">CHANGE</td>
                            <td style="padding: 3pt 5pt; border: 1pt solid #e2e8f0; color: #16a34a; font-weight: bold; font-size: 8.5pt; text-align: right;">{currency} {change_amount:,.2f}</td>
                        </tr>
        """

    logo_html = _get_logo_data_uri(co)
    embedded_font_css = _get_embedded_font_css()

    # Address block
    full_address = address
    if address2:
        full_address += f", {address2}"

    # ZIMRA Block detection
    # ReceiptData field mapping:
    #   receiptNo    -> global invoice number (fiscal_global_no in DB)
    #   vCode        -> verification code     (fiscal_verification_code in DB)
    #   deviceSerial -> EFD serial number
    #   deviceId     -> EFD device ID
    #   fiscalDay    -> fiscal day string
    #   qrCode       -> verification URL (raw string, not base64 PNG)
    zimra_html = ""
    fiscal_status = str(_get("fiscal_status") or _get("fiscalStatus") or "").strip().lower()
    zimra_serial = _get("deviceSerial") or co.get("zimra_serial_no", "")
    # Support both ReceiptData attribute names and dict key names
    zimra_global = (
        _get("receiptNo")
        or _get("fiscalGlobalNo")
        or _get("fiscal_global_no", "")
    )
    zimra_vcode = (
        _get("vCode")
        or _get("verificationCode")
        or _get("fiscal_verification_code", "")
    )
    # Format 16-char vcode with dashes for readability
    if zimra_vcode and len(str(zimra_vcode)) == 16:
        _vc = str(zimra_vcode)
        zimra_vcode = f"{_vc[:4]}-{_vc[4:8]}-{_vc[8:12]}-{_vc[12:]}"
    zimra_qr_raw = _get("qrCode") or _get("fiscal_qr_code", "")
    zimra_day = _get("fiscalDay") or _get("fiscal_day", "")

    # Dynamic A4 Font Size from Company Defaults
    try:
        base_font_pt = float(co.get("a4_font_size", 8.5) or 8.5)
        if base_font_pt < 6 or base_font_pt > 16:
            base_font_pt = 8.5
    except Exception:
        base_font_pt = 8.5

    f_base = f"{base_font_pt}pt"
    f_small = f"{round(base_font_pt * 0.94, 1)}pt"
    f_tiny = f"{round(base_font_pt * 0.85, 1)}pt"
    f_micro = f"{round(base_font_pt * 0.75, 1)}pt"
    f_title = f"{round(base_font_pt * 1.53, 1)}pt"
    f_h1 = f"{round(base_font_pt * 1.45, 1)}pt"
    f_head = f"{round(base_font_pt * 1.05, 1)}pt"

    # Only show ZIMRA block when the sale is actually fiscalized (or pending-sync)
    _show_zimra = (
        fiscal_status in ("fiscalized", "pending_sync")
        or (zimra_serial or zimra_global or zimra_qr_raw)
    )
    zimra_present = _show_zimra and bool(zimra_serial or zimra_global or zimra_qr_raw)
    
    zimra_footer_cell = ""
    if zimra_present:
        # Try to generate a real QR code image from the URL string
        qr_img_html = ""
        qr_link_html = ""
        if zimra_qr_raw:
            try:
                import qrcode, io
                qr_img_obj = qrcode.make(zimra_qr_raw)
                buf = io.BytesIO()
                qr_img_obj.save(buf, format="PNG")
                qr_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                qr_img_html = (
                    f'<img src="data:image/png;base64,{qr_b64}" '
                    f'style="width:48pt; height:48pt; display:inline-block;" alt="ZIMRA QR Code"/>'
                )
            except Exception:
                if zimra_qr_raw.startswith("http"):
                    qr_link_html = (
                        f'<a href="{zimra_qr_raw}" style="font-size:5.5pt; color:#0a2342; word-break:break-all;">'
                        f'[Scan to Verify]</a>'
                    )
        pending_note_html = ""
        if fiscal_status == "pending_sync":
            pending_note_html = (
                f'<div style="color:#c05a00; font-weight:bold; font-size:{f_micro}; padding-top:1pt;">'
                '&#9888; Pending sync</div>'
            )

        zimra_footer_cell = f"""
        <td class="align-top" style="width: 32%; padding-left: 8pt; vertical-align: top;">
            <div style="padding: 4pt 6pt; border: 1.2pt solid #0a2342; border-radius: 4pt; background-color: #f0f4fa;">
                <div style="font-weight: 800; font-size: {f_tiny}; color: #0a2342; margin-bottom: 2pt; text-align:center; letter-spacing:0.3pt;">
                    &#x2713;&nbsp; ZIMRA FISCAL VERIFICATION
                </div>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="width: 52pt; text-align: center; vertical-align: middle; padding-right: 4pt;">
                            {qr_img_html or qr_link_html or f'<span style="font-size:7pt; color:#64748b;">QR</span>'}
                        </td>
                        <td style="vertical-align: top; font-size: {f_micro}; line-height: 1.25;">
                            {'<div style="color:#0a2342; font-weight:bold;"><b>Inv:</b> ' + str(zimra_global) + '</div>' if zimra_global else ''}
                            {'<div style="color:#334155; font-family:monospace; word-break:break-all;"><b>VCode:</b> ' + str(zimra_vcode) + '</div>' if zimra_vcode else ''}
                            {'<div style="color:#64748b;"><b>EFD:</b> ' + str(zimra_serial) + '</div>' if zimra_serial else ''}
                            {'<div style="color:#64748b;"><b>Day:</b> ' + str(zimra_day) + '</div>' if zimra_day else ''}
                            {pending_note_html}
                        </td>
                    </tr>
                </table>
            </div>
        </td>
        """

    terms_width = "34%" if zimra_present else "50%"
    banking_width = "34%" if zimra_present else "50%"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>{doc_title} - {invoice_no}</title>
    <style>
        {embedded_font_css}

        * {{ box-sizing: border-box; }}

        html, body {{
            margin: 0 !important;
            padding: 0 !important;
            background: #ffffff;
            font-family: 'Poppins', 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
            font-size: {f_base};
            color: #1e293b;
            line-height: 1.35;
        }}

        .page {{
            display: flex;
            flex-direction: column;
            min-height: {PAGE_CONTENT_HEIGHT_PT}pt;
            width: 100%;
        }}
        .page-body {{ flex: 0 0 auto; }}
        .page-footer {{ margin-top: auto; flex: 0 0 auto; }}

        .text-primary-dark {{ color: #0a2342; }}
        .bg-primary-dark {{ background-color: #0a2342; color: #ffffff; }}

        .icon-circle {{
            display: inline-block; width: 13pt; height: 13pt;
            background: #0a2342; color: #ffffff; border-radius: 50%;
            text-align: center; line-height: 13pt; margin-right: 4pt; font-size: {f_micro};
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

        .header-brand-table {{ border-collapse: collapse; }}
        .header-brand-table td {{ vertical-align: middle; padding: 0; }}

        .main-table {{ width: 100%; border-collapse: collapse; margin-top: 6pt; table-layout: fixed; }}
        .main-table th {{ background: #0a2342; color: #ffffff; padding: 4.5pt 5pt; font-size: {f_base}; border: 1pt solid #ffffff; text-align: center; word-wrap: break-word; }}
        .main-table td {{ padding: 3.5pt 5pt; border: 1pt solid #e2e8f0; text-align: center; font-size: {f_base}; word-wrap: break-word; }}
        .main-table td.desc-col {{ text-align: left; font-weight: 500; }}
        .main-table td.idx-col {{ font-weight: bold; }}

        .prop-table {{ width: 100%; border-collapse: collapse; font-size: {f_base}; }}
        .prop-table td {{ padding: 2pt 0; vertical-align: top; }}
        .prop-label {{ font-weight: bold; width: 80pt; }}
        .prop-colon {{ width: 8pt; text-align: center; }}
    </style>
</head>
<body>
    <div class="print-container page">
        <div class="page-body">
            <!-- Top Center Title -->
            <div class="text-center" style="margin-top: 0px; margin-bottom: 6pt;">
                <span style="font-size: {f_title}; font-weight: 800; letter-spacing: 2.5pt; color: #0a2342; display: inline-block;">
                    &mdash;&mdash;&nbsp;&nbsp;{doc_title}&nbsp;&nbsp;&mdash;&mdash;
                </span>
            </div>

            <!-- Top Header Row -->
            <table width="100%" cellpadding="0" cellspacing="0" class="w-100" style="width: 100%; margin-bottom: 6pt; border-bottom: 1.5pt solid #0a2342; padding-bottom: 5pt; border-collapse: collapse;">
                <tr>
                    <!-- Left: Logo & Company Name -->
                    <td width="50%" valign="middle" align="left" class="w-50 align-middle text-left" style="width: 50%; vertical-align: middle; text-align: left;">
                        <table cellpadding="0" cellspacing="0" class="header-brand-table" style="border-collapse: collapse;">
                            <tr>
                                <td valign="middle" style="vertical-align: middle;">{logo_html}</td>
                                <td valign="middle" style="vertical-align: middle; padding-left: 5pt;">
                                    <h1 style="color: #0a2342; font-size: {f_h1}; font-weight: 800; margin: 0; line-height: 1.15;">
                                        {company_name_upper}
                                    </h1>
                                </td>
                            </tr>
                        </table>
                    </td>
                    <!-- Right: Contact Details -->
                    <td width="50%" valign="middle" align="right" class="w-50 align-middle text-right" style="width: 50%; vertical-align: middle; text-align: right; font-size: {f_small}; line-height: 1.35;">
                        <table cellpadding="0" cellspacing="0" style="margin-left: auto; border-collapse: collapse;">
                            <tr><td style="padding-bottom: 1.5pt; text-align: left; vertical-align: top; font-weight: bold;">{company_name_upper}</td></tr>
                            {'<tr><td style="padding-bottom: 1.5pt; text-align: left; vertical-align: top;">' + _icon_svg('pin', 7.5, '#0a2342') + ' ' + full_address + '</td></tr>' if full_address else ''}
                            {'<tr><td style="padding-bottom: 1.5pt; text-align: left; vertical-align: top;">' + _icon_svg('phone', 7.5, '#0a2342') + ' ' + phone + '</td></tr>' if phone else ''}
                            {'<tr><td style="padding-bottom: 1.5pt; text-align: left; vertical-align: top;">' + _icon_svg('mail', 7.5, '#0a2342') + ' ' + company_email + '</td></tr>' if company_email else ''}
                            <tr>
                                <td style="padding-bottom: 1.5pt; text-align: left; vertical-align: top;">
                                    <span class="font-bold">TIN:</span> {tin_no} &nbsp;|&nbsp; <span class="font-bold">VAT No:</span> {vat_no}
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>

            <!-- Mid Section: Customer & Document Info -->
            <table width="100%" cellpadding="0" cellspacing="0" class="w-100" style="width: 100%; margin-bottom: 8pt; border-collapse: collapse;">
                <tr>
                    <!-- Customer Info -->
                    <td width="50%" valign="top" class="w-50 align-top" style="width: 50%; vertical-align: top; padding-right: 12pt;">
                        <div style="margin-bottom: 4pt;">
                            <span class="icon-circle">{_icon_svg('user', 7)}</span>
                            <span class="text-primary-dark font-bold" style="font-size: {f_head};">CUSTOMER DETAILS</span>
                        </div>
                        <table width="100%" cellpadding="1" cellspacing="0" class="prop-table" style="width: 100%; border-collapse: collapse; font-size: {f_base};">
                            <tr>
                                <td width="35%" class="prop-label" style="width: 35%; font-weight: bold; padding: 2.5pt 0; vertical-align: top;">Customer Name</td>
                                <td width="5%" class="prop-colon" style="width: 5%; text-align: center; padding: 2.5pt 0; vertical-align: top;">:</td>
                                <td width="60%" style="width: 60%; padding: 2.5pt 0; vertical-align: top;">{customer_name}</td>
                            </tr>
                            {'<tr><td width="35%" class="prop-label" style="width: 35%; font-weight: bold; padding: 2.5pt 0; vertical-align: top;">Address</td><td width="5%" class="prop-colon" style="width: 5%; text-align: center; padding: 2.5pt 0; vertical-align: top;">:</td><td width="60%" style="width: 60%; padding: 2.5pt 0; vertical-align: top;">' + customer_address + '</td></tr>' if customer_address else ''}
                            {'<tr><td width="35%" class="prop-label" style="width: 35%; font-weight: bold; padding: 2.5pt 0; vertical-align: top;">Phone</td><td width="5%" class="prop-colon" style="width: 5%; text-align: center; padding: 2.5pt 0; vertical-align: top;">:</td><td width="60%" style="width: 60%; padding: 2.5pt 0; vertical-align: top;">' + customer_phone + '</td></tr>' if customer_phone else ''}
                        </table>
                    </td>

                    <!-- Document Info -->
                    <td width="50%" valign="top" class="w-50 align-top" style="width: 50%; vertical-align: top; border-left: 1.5pt solid #e2e8f0; padding-left: 12pt;">
                        <table width="100%" cellpadding="1" cellspacing="0" class="prop-table" style="width: 100%; border-collapse: collapse; font-size: {f_base};">
                            <tr>
                                <td width="35%" class="prop-label" style="width: 35%; font-weight: bold; padding: 2.5pt 0; vertical-align: top;">{doc_no_label}</td>
                                <td width="5%" class="prop-colon" style="width: 5%; text-align: center; padding: 2.5pt 0; vertical-align: top;">:</td>
                                <td width="60%" style="width: 60%; padding: 2.5pt 0; vertical-align: top; font-weight: bold;">{invoice_no}</td>
                            </tr>
                            <tr>
                                <td width="35%" class="prop-label" style="width: 35%; font-weight: bold; padding: 2.5pt 0; vertical-align: top;">{doc_date_label}</td>
                                <td width="5%" class="prop-colon" style="width: 5%; text-align: center; padding: 2.5pt 0; vertical-align: top;">:</td>
                                <td width="60%" style="width: 60%; padding: 2.5pt 0; vertical-align: top;">{invoice_date}</td>
                            </tr>
                            {valid_until_html}
                            {credit_note_meta_html}
                            <tr>
                                <td width="35%" class="prop-label" style="width: 35%; font-weight: bold; padding: 2.5pt 0; vertical-align: top;">Currency</td>
                                <td width="5%" class="prop-colon" style="width: 5%; text-align: center; padding: 2.5pt 0; vertical-align: top;">:</td>
                                <td width="60%" style="width: 60%; padding: 2.5pt 0; vertical-align: top;">{currency}</td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>

            <!-- Order Lines Table -->
            <table width="100%" cellpadding="3" cellspacing="0" class="main-table" style="width: 100%; border-collapse: collapse; margin-top: 6pt;">
                <thead>
                    <tr style="background-color: #0a2342; color: #ffffff;">
                        <th width="5%" style="width: 5%; background-color: #0a2342; color: #ffffff; padding: 4.5pt 3pt; font-size: {f_base}; text-align: center; border: 1pt solid #ffffff;">#</th>
                        <th width="35%" class="text-left" style="width: 35%; background-color: #0a2342; color: #ffffff; padding: 4.5pt 5pt; font-size: {f_base}; text-align: left; border: 1pt solid #ffffff;">Description</th>
                        <th width="10%" style="width: 10%; background-color: #0a2342; color: #ffffff; padding: 4.5pt 3pt; font-size: {f_base}; text-align: center; border: 1pt solid #ffffff;">{'Qty Returned' if is_return else 'Qty'}</th>
                        <th width="16%" style="width: 16%; background-color: #0a2342; color: #ffffff; padding: 4.5pt 5pt; font-size: {f_base}; text-align: right; border: 1pt solid #ffffff;">Unit Price ({currency})</th>
                        <th width="16%" style="width: 16%; background-color: #0a2342; color: #ffffff; padding: 4.5pt 5pt; font-size: {f_base}; text-align: right; border: 1pt solid #ffffff;">Tax Amount ({currency})</th>
                        <th width="18%" style="width: 18%; background-color: #0a2342; color: #ffffff; padding: 4.5pt 5pt; font-size: {f_base}; text-align: right; border: 1pt solid #ffffff;">{'Total Credit (' + currency + ')' if is_return else 'Total Amount (' + currency + ')'}</th>
                    </tr>
                </thead>
                <tbody>
                    {item_rows_html}
                </tbody>
            </table>

            <!-- Totals Section -->
            <table width="100%" cellpadding="0" cellspacing="0" class="w-100" style="width: 100%; margin-top: 5pt; border-collapse: collapse;">
                <tr>
                    <td width="55%" valign="top" class="w-60" style="width: 55%; vertical-align: top;">
                    </td>
                    <td width="45%" valign="top" class="w-40 text-right" style="width: 45%; vertical-align: top; text-align: right;">
                        <table width="100%" cellpadding="2" cellspacing="0" style="width: 100%; border-collapse: collapse; text-align: right; font-size: {f_base};">
                            <tr>
                                <td style="padding: 3pt 5pt; border: 1pt solid #e2e8f0; font-weight: bold; text-align: left;">SUBTOTAL (Excl. Tax)</td>
                                <td style="padding: 3pt 5pt; border: 1pt solid #e2e8f0; width: 45%; text-align: right;">{currency} {subtotal:,.2f}</td>
                            </tr>
                            <tr>
                                <td style="padding: 3pt 5pt; border: 1pt solid #e2e8f0; font-weight: bold; text-align: left;">TOTAL TAX</td>
                                <td style="padding: 3pt 5pt; border: 1pt solid #e2e8f0; text-align: right;">{currency} {total_vat:,.2f}</td>
                            </tr>
                            <tr class="bg-primary-dark" style="background-color: #0a2342; color: #ffffff;">
                                <td style="padding: 4.5pt 5pt; font-weight: bold; font-size: {f_head}; color: #ffffff; text-align: left;">{'TOTAL CREDIT (Incl. Tax)' if is_return else 'TOTAL (Incl. Tax)'}</td>
                                <td style="padding: 4.5pt 5pt; font-weight: bold; font-size: {f_head}; color: #ffffff; text-align: right;">{currency} {grand_total:,.2f}</td>
                            </tr>
                            {tendered_change_html}
                        </table>
                    </td>
                </tr>
            </table>
        </div>

        <!-- ============================================================
             PAGE FOOTER — pinned to the bottom of the printable A4 page
             Includes Terms & Conditions, Banking Details, and ZIMRA/QR Code
             all aligned horizontally in the SAME ROW for optimal space use.
             ============================================================ -->
        <div class="page-footer">
            <table class="w-100" style="margin-top: 6pt; margin-bottom: 3pt; border-collapse: collapse;">
                <tr>
                    <!-- Column 1: Terms & Conditions -->
                    <td class="align-top" style="width: {terms_width}; padding-right: 6pt; vertical-align: top;">
                        <div style="margin-bottom: 2pt; border-bottom: 1pt solid #0a2342; padding-bottom: 2pt; width: 100%;">
                            <span class="icon-circle">{_icon_svg('doc', 7)}</span>
                            <span class="text-primary-dark font-bold" style="font-size: {f_small};">TERMS &amp; CONDITIONS</span>
                        </div>
                        <div style="font-size: {f_small}; line-height: 1.3; color: #334155; min-height: 16pt;">
                            {terms_html}
                        </div>

                        <!-- Signature Block -->
                        <div style="margin-top: 6pt;">
                            <div style="border-bottom: 1pt dashed #0a2342; width: 110pt; height: 10pt; margin-bottom: 2pt;"></div>
                            <div style="font-weight: bold; font-size: {f_tiny};">Authorised Signatory</div>
                            <div style="font-size: {f_tiny}; color: #0a2342; font-weight: bold;">{company_name_upper}</div>
                        </div>
                    </td>

                    <!-- Column 2: Banking Details -->
                    <td class="align-top" style="width: {banking_width}; padding-left: 6pt; padding-right: { '6pt' if zimra_present else '0' }; vertical-align: top;">
                        <div style="margin-bottom: 2pt; border-bottom: 1pt solid #0a2342; padding-bottom: 2pt; width: 100%;">
                            <span class="icon-circle">{_icon_svg('bank', 7)}</span>
                            <span class="text-primary-dark font-bold" style="font-size: {f_small};">BANKING DETAILS</span>
                        </div>
                        <div style="font-size: {f_small}; line-height: 1.3; color: #334155; margin-bottom: 3pt;">
                            {banking_html}
                        </div>

                        <!-- Thank you message -->
                        <table style="margin-top: 3pt; border-collapse: collapse;">
                            <tr>
                                <td style="vertical-align: middle;">
                                    <span class="icon-circle" style="font-size: {f_tiny}; width: 14pt; height: 14pt; line-height: 14pt;">{_icon_svg('shake', 7)}</span>
                                </td>
                                <td style="vertical-align: middle; padding-left: 4pt;">
                                    <div class="text-primary-dark font-bold" style="font-size: {f_small};">Thank you for your business!</div>
                                    <div style="font-size: {f_tiny}; color: #475569;">{footer_text}</div>
                                </td>
                            </tr>
                        </table>
                    </td>

                    <!-- Column 3: ZIMRA Fiscal Details & QR Code (in same row!) -->
                    {zimra_footer_cell}
                </tr>
            </table>

            <!-- Very Bottom Banner -->
            <div class="bg-primary-dark text-center" style="padding: 3pt; font-size: {f_tiny}; font-weight: bold; margin-top: 4pt; color: #ffffff;">
                Powered by HavanoERP
            </div>
        </div>
    </div>
</body>
</html>
"""
    return html


def _html_to_pdf(html_content: str, pdf_path: str, timeout_ms: int = 15000) -> None:
    """
    Renders `html_content` to `pdf_path`.
    Tries Chromium QWebEngineView first if available.
    If QWebEngineView is not packaged (e.g. excluded in PyInstaller builds),
    seamlessly falls back to native QTextDocument + QPrinter which is 100% built-in
    and always works on any computer without external dependencies.

    Reliability fix: QWebEngineView (Chromium) can fail to initialize on
    machines with older/unusual GPU drivers, which used to silently drop us
    into the much more limited QTextDocument fallback (no flexbox support,
    weaker CSS support) -> the PDF would look different on that machine.
    We now force Chromium onto software rendering via
    QTWEBENGINE_CHROMIUM_FLAGS so GPU driver differences between machines
    can no longer cause that silent downgrade.
    """
    # Must be set before the QWebEngine profile initializes (i.e. before the
    # first QWebEngineView is constructed anywhere in the process).
    os.environ.setdefault(
        "QTWEBENGINE_CHROMIUM_FLAGS",
        "--disable-gpu --disable-software-rasterizer --disable-gpu-compositing --no-sandbox",
    )

    from PySide6.QtGui import QTextDocument, QPageSize, QPageLayout
    from PySide6.QtPrintSupport import QPrinter

    # 1. Attempt QWebEngineView (Chromium rendering)
    try:
        from PySide6.QtWebEngineWidgets import QWebEngineView

        view = QWebEngineView()
        view.setHtml(html_content)

        load_loop = QEventLoop()
        load_ok = {"ok": False}

        def _on_load_finished(ok):
            load_ok["ok"] = ok
            load_loop.quit()

        view.loadFinished.connect(_on_load_finished)
        QTimer.singleShot(timeout_ms, load_loop.quit)
        load_loop.exec()

        if load_ok["ok"]:
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
            QTimer.singleShot(timeout_ms, print_loop.quit)
            print_loop.exec()

            view.deleteLater()

            if print_ok["ok"] and os.path.exists(pdf_path):
                return
            else:
                log.warning("[a4_invoice] QWebEngine loaded but PDF export failed/timed out - falling back to QTextDocument")
        else:
            log.warning("[a4_invoice] QWebEngine failed to load HTML (ok=False) - falling back to QTextDocument")
    except (ImportError, ModuleNotFoundError) as e:
        log.info(f"[a4_invoice] QWebEngineView not available ({e}) - using native QTextDocument fallback")
    except Exception as e:
        log.warning(f"[a4_invoice] QWebEngineView failed ({e}) - falling back to QTextDocument")

    # 2. Universal fallback: QTextDocument + QPrinter (always bundled in PySide6)
    #    NOTE: this renderer does not support flexbox/position/border-radius/
    #    @font-face reliably, so the "page-footer at bottom" behaviour and
    #    embedded font may not apply here -- it still produces a correct,
    #    readable PDF, just with simpler layout. The primary path above
    #    (now GPU-independent) should be used on essentially all machines.
    try:
        from PySide6.QtGui import QTextDocument, QPageSize, QPageLayout
        from PySide6.QtPrintSupport import QPrinter

        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(pdf_path)
        printer.setFullPage(True)
        page_layout = QPageLayout(
            QPageSize(QPageSize.PageSizeId.A4),
            QPageLayout.Orientation.Portrait,
            QMarginsF(MARGIN_LEFT_MM, MARGIN_TOP_MM, MARGIN_RIGHT_MM, MARGIN_BOTTOM_MM),
            QPageLayout.Unit.Millimeter,
        )
        printer.setPageLayout(page_layout)

        doc = QTextDocument()
        doc.setDocumentMargin(0)
        doc.setHtml(html_content)
        doc.print_(printer)

        if os.path.exists(pdf_path):
            log.info("[a4_invoice] Successfully generated A4 PDF via QTextDocument fallback.")
            return
        raise RuntimeError("QTextDocument failed to create PDF file.")
    except Exception as e:
        log.error(f"[a4_invoice] All PDF generation methods failed: {e}", exc_info=True)
        raise


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
        from PySide6.QtWidgets import QMessageBox, QApplication
        active_w = parent or QApplication.activeWindow()
        QMessageBox.critical(active_w, "Preview Error", f"Could not generate A4 Preview:\n{exc}")
        return False


def show_a4_credit_note_preview(credit_note_data: dict | object, parent=None):
    """
    Renders the A4 Credit Note with full vector formatting and launches PdfPreviewDialog.
    """
    return show_a4_invoice_preview(credit_note_data, parent=parent)