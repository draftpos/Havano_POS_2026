# =============================================================================
# services/a4_shift_recon_service.py
#
# Official A4 Full-Page Shift Reconciliation Report Renderer
# High-Resolution Pt-scaled Vector Formatting matching native A4 PDF preview standards.
#
# Page geometry:
#   format=A4, orientation=Portrait, margin_top=6mm, margin_bottom=6mm,
#   margin_left=8mm, margin_right=8mm, header_line=False, dpi=90
# =============================================================================

import os
import sys
import json
import base64
import logging
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QMarginsF, QEventLoop, QTimer
from PySide6.QtGui import QPageSize, QPageLayout

log = logging.getLogger("a4_shift_recon_service")

MARGIN_TOP_MM = 6
MARGIN_BOTTOM_MM = 6
MARGIN_LEFT_MM = 8
MARGIN_RIGHT_MM = 8


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
                    return f'<img src="data:{mime};base64,{b64}" style="max-height: 40pt; max-width: 90pt; margin-right: 8pt; display: inline-block; vertical-align: middle;" alt="Logo"/>'
    except Exception as e:
        log.warning("Logo load error: %s", e)
    return ""


def _get_embedded_font_css() -> str:
    """Embeds bundled Poppins .ttf files if available, with safe system fallbacks."""
    try:
        base_dir = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
        fonts_dir = os.path.join(base_dir, "assets", "fonts")
        weights = {
            "400": "Poppins-Regular.ttf",
            "500": "Poppins-Medium.ttf",
            "600": "Poppins-SemiBold.ttf",
            "700": "Poppins-Bold.ttf",
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
        log.warning("Embedded font load error: %s", e)
        return ""


def _icon_svg(name: str, size: float = 9, color: str = "#ffffff") -> str:
    """Inline SVG icons for cross-platform rendering."""
    icons = {
        "pin": f'<svg width="{size}pt" height="{size}pt" viewBox="0 0 24 24" fill="{color}" style="vertical-align:middle;"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5A2.5 2.5 0 1 1 12 6.5a2.5 2.5 0 0 1 0 5z"/></svg>',
        "phone": f'<svg width="{size}pt" height="{size}pt" viewBox="0 0 24 24" fill="{color}" style="vertical-align:middle;"><path d="M6.6 10.8c1.4 2.8 3.8 5.1 6.6 6.6l2.2-2.2c.3-.3.7-.4 1-.2 1.1.4 2.3.6 3.6.6.6 0 1 .4 1 1V20c0 .6-.4 1-1 1C10.9 21 3 13.1 3 3.9c0-.6.4-1 1-1H7.6c.6 0 1 .4 1 1 0 1.3.2 2.5.6 3.6.1.4 0 .8-.2 1L6.6 10.8z"/></svg>',
        "mail": f'<svg width="{size}pt" height="{size}pt" viewBox="0 0 24 24" fill="{color}" style="vertical-align:middle;"><path d="M20 4H4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2zm0 4-8 5-8-5V6l8 5 8-5v2z"/></svg>',
        "user": f'<svg width="{size}pt" height="{size}pt" viewBox="0 0 24 24" fill="{color}" style="vertical-align:middle;"><path d="M12 12a5 5 0 1 0 0-10 5 5 0 0 0 0 10zm0 2c-4.4 0-8 2.2-8 5v2h16v-2c0-2.8-3.6-5-8-5z"/></svg>',
        "calendar": f'<svg width="{size}pt" height="{size}pt" viewBox="0 0 24 24" fill="{color}" style="vertical-align:middle;"><path d="M19 4h-1V2h-2v2H8V2H6v2H5c-1.11 0-1.99.9-1.99 2L3 20c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 16H5V10h14v10zm0-12H5V6h14v2z"/></svg>',
        "clock": f'<svg width="{size}pt" height="{size}pt" viewBox="0 0 24 24" fill="{color}" style="vertical-align:middle;"><path d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z"/></svg>',
        "computer": f'<svg width="{size}pt" height="{size}pt" viewBox="0 0 24 24" fill="{color}" style="vertical-align:middle;"><path d="M20 18c1.1 0 1.99-.9 1.99-2L22 6c0-1.1-.9-2-2-2H4c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2H0v2h24v-2h-4zM4 6h16v10H4V6z"/></svg>',
        "cash": f'<svg width="{size}pt" height="{size}pt" viewBox="0 0 24 24" fill="{color}" style="vertical-align:middle;"><path d="M11.8 10.9c-2.27-.59-3-1.2-3-2.15 0-1.09 1.01-1.85 2.7-1.85 1.78 0 2.44.85 2.5 2.1h2.21c-.07-1.72-1.12-3.3-3.21-3.81V3h-3v2.16c-1.94.42-3.5 1.68-3.5 3.61 0 2.31 1.91 3.46 4.7 4.13 2.5.6 3 1.48 3 2.41 0 .69-.49 1.79-2.7 1.79-2.06 0-2.87-.92-2.98-2.1h-2.2c.12 2.19 1.76 3.42 3.68 3.83V21h3v-2.15c1.95-.37 3.5-1.5 3.5-3.55 0-2.84-2.43-3.81-4.7-4.4z"/></svg>',
        "check": f'<svg width="{size}pt" height="{size}pt" viewBox="0 0 24 24" fill="{color}" style="vertical-align:middle;"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>',
        "alert": f'<svg width="{size}pt" height="{size}pt" viewBox="0 0 24 24" fill="{color}" style="vertical-align:middle;"><path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/></svg>',
    }
    return icons.get(name, "")


def render_a4_shift_recon_html(
    shift: dict | None = None,
    totals: list | None = None,
    reconciliation_data: dict | None = None,
    print_data: dict | None = None,
    is_reprint: bool = False,
) -> str:
    """
    Renders an official vector A4 Shift Reconciliation Report HTML.
    """
    from models.company_defaults import get_defaults
    co = get_defaults() or {}
    
    from models.advance_settings import AdvanceSettings
    settings = AdvanceSettings.load_from_file()

    # Determine company details
    company_name = (
        co.get("company_name")
        or getattr(settings, "companyName", None)
        or "HAVANO POS"
    )
    address_parts = [
        co.get("address_line1") or getattr(settings, "companyAddress", ""),
        co.get("address_line2") or getattr(settings, "companyAddressLine1", ""),
        f"{co.get('city') or ''} {co.get('state') or ''}".strip(),
    ]
    address_str = ", ".join([p for p in address_parts if p])
    tel = co.get("phone") or getattr(settings, "tel", "")
    email = co.get("email") or getattr(settings, "companyEmail", "")
    tin = co.get("tin") or getattr(settings, "tin", "")
    vat_no = co.get("vat_no") or getattr(settings, "vatNo", "")

    logo_img = _get_logo_data_uri(co)
    embedded_fonts = _get_embedded_font_css()

    # Extract shift meta
    opening_balance = 0.0
    if reconciliation_data:
        shift_num = reconciliation_data.get('shift_number', '-')
        station = reconciliation_data.get('station', '')
        station_name = reconciliation_data.get('station_name', '')
        shift_date = reconciliation_data.get('date', datetime.now().strftime("%Y-%m-%d"))
        start_time = reconciliation_data.get('start_time', '-')
        end_time = reconciliation_data.get('end_time', datetime.now().strftime("%H:%M:%S"))
        closing_cashier = reconciliation_data.get('closing_cashier_name', '')
        opening_balance = float(reconciliation_data.get('opening_balance', reconciliation_data.get('start_float', 0.0)) or 0.0)
    elif print_data:
        shift_num = print_data.get('shift_number', '-')
        station = print_data.get('station', '')
        station_name = print_data.get('station_name', '')
        shift_date = print_data.get('date', datetime.now().strftime("%Y-%m-%d"))
        start_time = print_data.get('start_time', '-')
        end_time = print_data.get('end_time', datetime.now().strftime("%H:%M:%S"))
        closing_cashier = print_data.get('closing_cashier_name', '')
        opening_balance = float(print_data.get('opening_balance', print_data.get('start_float', 0.0)) or 0.0)
    else:
        shift_num = shift.get('shift_number', '-') if shift else '-'
        station = shift.get('station', '') if shift else ''
        station_name = shift.get('station_name', '') if shift else ''
        shift_date = shift.get('date', datetime.now().strftime("%Y-%m-%d")) if shift else datetime.now().strftime("%Y-%m-%d")
        start_time = shift.get('start_time', '-') if shift else '-'
        end_time = datetime.now().strftime("%H:%M:%S")
        closing_cashier = ''
        opening_balance = float(shift.get('opening_balance', shift.get('start_float', 0.0)) if shift else 0.0)

    shift_id = (shift.get('id', shift.get('shift_id')) if shift else None) or \
               (reconciliation_data.get('shift_id') if reconciliation_data else None) or \
               (print_data.get('shift_id') if print_data else None)

    if opening_balance == 0.0 and shift_id:
        try:
            from database.db import get_connection
            conn_ob = get_connection()
            cur_ob = conn_ob.cursor()
            cur_ob.execute("SELECT SUM(start_float) FROM shift_rows WHERE shift_id = ?", (shift_id,))
            ob_res = cur_ob.fetchone()
            if ob_res and ob_res[0] is not None:
                opening_balance = float(ob_res[0])
            conn_ob.close()
        except Exception:
            pass

    # Harvest Cashiers & Payment Methods
    cashiers = []
    payment_methods = []
    grand_expected = 0.0
    grand_counted = 0.0

    if reconciliation_data:
        cashiers = reconciliation_data.get('cashiers', [])
        payment_methods = reconciliation_data.get('payment_methods', [])
        grand_expected = float(reconciliation_data.get('total_expected', 0))
        grand_counted = float(reconciliation_data.get('total_counted', 0))
    elif print_data:
        cashiers = print_data.get('cashiers', [])
        payment_methods = print_data.get('payment_methods', [])
        grand_expected = float(print_data.get('grand_expected', print_data.get('total_expected', 0)))
        grand_counted = float(print_data.get('grand_counted', print_data.get('total_counted', 0)))
    elif totals:
        for t in totals:
            payment_methods.append({
                'method': t.get('method'),
                'currency': t.get('currency', 'USD'),
                'expected': float(t.get('expected', 0)),
                'counted': float(t.get('actual', t.get('counted', 0))),
                'variance': float(t.get('variance', 0))
            })
        grand_expected = sum(float(t.get('expected', 0)) for t in totals)
        grand_counted = sum(float(t.get('actual', t.get('counted', 0))) for t in totals)

    # Harvest Shift Credit Notes & Till Expenses
    credit_notes_list = []
    total_credit_notes = 0.0
    expenses_list = []
    total_expenses = 0.0

    if shift_id:
        try:
            from database.db import get_connection
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT created_at, end_time FROM shifts WHERE id = ?", (shift_id,))
            shift_times = cur.fetchone()
            if shift_times:
                st = shift_times[0]
                et = shift_times[1] if shift_times[1] else datetime.now()
                cur.execute("""
                    SELECT cn_number, total, COALESCE(currency, 'USD') as currency, COALESCE(customer_name, 'Walk-in') as customer, cashier_name
                    FROM credit_notes
                    WHERE (shift_id = ? OR (shift_id IS NULL AND created_at >= ? AND created_at <= ?))
                    ORDER BY id ASC
                """, (shift_id, st, et))
                credit_notes_list = cur.fetchall()
                total_credit_notes = sum(float(r[1] or 0) for r in credit_notes_list)

                cur.execute("""
                    SELECT e.expense_number, e.amount, COALESCE(c.name, 'Expense') as category, e.name as title, e.cashier_name,
                           COALESCE(NULLIF(LTRIM(RTRIM(e.payment_method)), ''), 'Cash') as payment_method
                    FROM expenses e
                    LEFT JOIN expense_categories c ON e.expense_category_id = c.id
                    WHERE e.paid = 1
                      AND (e.shift_id = ? OR (e.shift_id IS NULL AND e.created_at >= ? AND e.created_at <= ?))
                    ORDER BY e.id ASC
                """, (shift_id, st, et))
                expenses_list = cur.fetchall()
                total_expenses = sum(float(r[1] or 0) for r in expenses_list)
            conn.close()
        except Exception as e:
            log.warning("Error fetching credit notes/expenses: %s", e)

    # Check for total invoices
    total_invoices = 0
    if reconciliation_data and reconciliation_data.get('total_invoices') is not None:
        total_invoices = reconciliation_data.get('total_invoices')
    elif cashiers:
        total_invoices = sum(int(c.get('transaction_count', c.get('transactions', 0))) for c in cashiers)
    elif shift_id:
        try:
            from database.db import get_connection
            conn = get_connection(); cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM sales WHERE shift_id = ?", (shift_id,))
            r = cur.fetchone()
            if r: total_invoices = int(r[0])
            conn.close()
        except Exception:
            pass

    # Build Global Summary Rows HTML
    summary_rows_html = ""
    summary_curr_totals = {}
    for pm in payment_methods:
        method = pm.get('method', '')
        currency = (pm.get('currency') or '').strip().upper()
        if not currency:
            if " (" in method and method.endswith(")"):
                currency = method.split(" (")[-1].rstrip(")").strip().upper()
        if not currency:
            currency = 'USD'
            
        expected = float(pm.get('expected', 0))
        counted = float(pm.get('counted', pm.get('actual', 0)))
        variance = counted - expected

        if currency not in summary_curr_totals:
            summary_curr_totals[currency] = {'expected': 0.0, 'counted': 0.0}
        summary_curr_totals[currency]['expected'] += expected
        summary_curr_totals[currency]['counted'] += counted

        var_color = "#16a34a" if variance > 0.001 else ("#dc2626" if variance < -0.001 else "#475569")
        var_badge = f'<span style="color: {var_color}; font-weight: 700;">{variance:+,.2f}</span>' if abs(variance) > 0.001 else '<span style="color: #64748b;">0.00</span>'

        is_on_acc = method.upper() == "ON ACCOUNT"
        row_bg = "#fef3c7" if is_on_acc else ""
        acc_tag = '<span style="font-size: 7pt; background: #d97706; color: white; padding: 1pt 4pt; border-radius: 3pt; margin-left: 4pt;">Credit Sales</span>' if is_on_acc else ''

        summary_rows_html += f"""
        <tr style="{'background-color:' + row_bg if row_bg else ''}">
            <td style="padding: 5pt 8pt; border-bottom: 1px solid #e2e8f0; font-weight: 600;">{method}{acc_tag}</td>
            <td style="padding: 5pt 8pt; border-bottom: 1px solid #e2e8f0; text-align: center; color: #475569;">{currency}</td>
            <td style="padding: 5pt 8pt; border-bottom: 1px solid #e2e8f0; text-align: right;">{expected:,.2f}</td>
            <td style="padding: 5pt 8pt; border-bottom: 1px solid #e2e8f0; text-align: right; font-weight: 600;">{counted:,.2f}</td>
            <td style="padding: 5pt 8pt; border-bottom: 1px solid #e2e8f0; text-align: right;">{var_badge}</td>
        </tr>
        """

    # Add Summary Grand Totals (if single currency)
    summary_totals_html = ""
    if len(summary_curr_totals) == 1:
        for ccy, g_tot in summary_curr_totals.items():
            g_exp = g_tot['expected']
            g_cnt = g_tot['counted']
            g_var = g_cnt - g_exp
            g_color = "#16a34a" if g_var > 0.001 else ("#dc2626" if g_var < -0.001 else "#0f172a")
            summary_totals_html += f"""
            <tr style="background-color: #f1f5f9; font-weight: 700;">
                <td colspan="2" style="padding: 6pt 8pt; border-top: 2px solid #0f172a; color: #0f172a;">GRAND TOTAL ({ccy})</td>
                <td style="padding: 6pt 8pt; border-top: 2px solid #0f172a; text-align: right; color: #0f172a;">{g_exp:,.2f}</td>
                <td style="padding: 6pt 8pt; border-top: 2px solid #0f172a; text-align: right; color: #0f172a;">{g_cnt:,.2f}</td>
                <td style="padding: 6pt 8pt; border-top: 2px solid #0f172a; text-align: right; color: {g_color};">{g_var:+,.2f}</td>
            </tr>
            """

    # Build Cashiers Breakdown Section HTML
    cashiers_html = ""
    if cashiers:
        cashiers_html += """
        <div style="margin-top: 14pt;">
            <div style="font-size: 11pt; font-weight: 700; color: #0a2342; border-bottom: 2px solid #0a2342; padding-bottom: 3pt; margin-bottom: 6pt;">
                CASHIER SESSION BREAKDOWNS
            </div>
        """
        for cashier in cashiers:
            c_name = cashier.get('cashier_name') or cashier.get('username', 'Unknown')
            c_id = cashier.get('cashier_id') or '-'
            c_sales = float(cashier.get('total_sales', 0))
            c_tx = cashier.get('transaction_count', cashier.get('transactions', 0))
            c_items = cashier.get('total_items', 0)
            rows = cashier.get('rows') or cashier.get('payment_breakdown', [])

            c_cns = [cn for cn in credit_notes_list if (str(cn[4] or '').strip().lower() == str(c_name).strip().lower())]
            if len(cashiers) == 1 and not c_cns and credit_notes_list:
                c_cns = credit_notes_list
            c_cn_count = len(c_cns)
            c_cn_total = sum(float(cn[1] or 0) for cn in c_cns)
            c_final_sales = c_sales - c_cn_total

            cashiers_html += f"""
            <div style="margin-bottom: 10pt; border: 1px solid #cbd5e1; border-radius: 4pt; overflow: hidden;">
                <div style="background-color: #f8fafc; padding: 5pt 8pt; border-bottom: 1px solid #cbd5e1; display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-weight: 700; color: #0f172a; font-size: 9pt;">👤 {c_name} <span style="font-size: 8pt; color: #64748b; font-weight: normal;">(ID: {c_id})</span></span>
                    <span style="font-size: 8pt; color: #334155;">Sales: <b>${c_sales:,.2f}</b> | CNs: <b style="color: #dc2626;">-${c_cn_total:,.2f}</b> | Final Sales: <b style="color: #16a34a;">${c_final_sales:,.2f}</b> | Invoices: <b>{c_tx}</b> | Items Sold: <b>{c_items}</b></span>
                </div>
                <table style="width: 100%; border-collapse: collapse; font-size: 8.5pt;">
                    <thead>
                        <tr style="background-color: #f1f5f9; color: #475569; font-size: 7.5pt; text-transform: uppercase;">
                            <th style="padding: 4pt 8pt; text-align: left;">Payment Method</th>
                            <th style="padding: 4pt 8pt; text-align: center;">Currency</th>
                            <th style="padding: 4pt 8pt; text-align: right;">Expected</th>
                            <th style="padding: 4pt 8pt; text-align: right;">Counted</th>
                            <th style="padding: 4pt 8pt; text-align: right;">Variance</th>
                            <th style="padding: 4pt 8pt; text-align: center;">Tx Count</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            for r in rows:
                r_method = r.get('method', '')
                r_curr = r.get('currency', 'USD')
                r_exp = float(r.get('expected', 0))
                r_cnt = float(r.get('counted', r.get('collected', 0)))
                r_var = r_cnt - r_exp
                r_tx = r.get('transaction_count', '-')
                r_var_color = "#16a34a" if r_var > 0.001 else ("#dc2626" if r_var < -0.001 else "#475569")
                r_var_str = f"{r_var:+,.2f}" if abs(r_var) > 0.001 else "0.00"

                cashiers_html += f"""
                <tr>
                    <td style="padding: 3.5pt 8pt; border-bottom: 1px solid #f1f5f9; font-weight: 500;">{r_method}</td>
                    <td style="padding: 3.5pt 8pt; border-bottom: 1px solid #f1f5f9; text-align: center; color: #64748b;">{r_curr}</td>
                    <td style="padding: 3.5pt 8pt; border-bottom: 1px solid #f1f5f9; text-align: right;">{r_exp:,.2f}</td>
                    <td style="padding: 3.5pt 8pt; border-bottom: 1px solid #f1f5f9; text-align: right; font-weight: 600;">{r_cnt:,.2f}</td>
                    <td style="padding: 3.5pt 8pt; border-bottom: 1px solid #f1f5f9; text-align: right; color: {r_var_color}; font-weight: 600;">{r_var_str}</td>
                    <td style="padding: 3.5pt 8pt; border-bottom: 1px solid #f1f5f9; text-align: center; color: #64748b;">{r_tx}</td>
                </tr>
                """

            cashiers_html += """
                    </tbody>
                </table>
            </div>
            """
        cashiers_html += "</div>"

    # Build Shift Deductions & Expenses Section HTML
    deductions_html = ""
    if credit_notes_list or expenses_list:
        deductions_html += """
        <div style="margin-top: 14pt;">
            <div style="font-size: 11pt; font-weight: 700; color: #0a2342; border-bottom: 2px solid #0a2342; padding-bottom: 3pt; margin-bottom: 6pt;">
                SHIFT DEDUCTIONS & TILL EXPENSES
            </div>
            <table style="width: 100%; border-collapse: collapse; font-size: 8.5pt;">
                <thead>
                    <tr style="background-color: #f1f5f9; color: #475569; font-size: 7.5pt; text-transform: uppercase;">
                        <th style="padding: 4pt 8pt; text-align: left;">Type / Ref #</th>
                        <th style="padding: 4pt 8pt; text-align: left;">Description / Customer / Category</th>
                        <th style="padding: 4pt 8pt; text-align: center;">Payment Method</th>
                        <th style="padding: 4pt 8pt; text-align: right;">Amount</th>
                    </tr>
                </thead>
                <tbody>
        """
        for cn in credit_notes_list:
            cn_num = cn[0] or 'CN'
            cn_tot = float(cn[1] or 0)
            cn_curr = cn[2] or 'USD'
            cn_cust = cn[3] if len(cn) > 3 else 'Walk-in'
            deductions_html += f"""
            <tr>
                <td style="padding: 3.5pt 8pt; border-bottom: 1px solid #f1f5f9; font-weight: 600; color: #b91c1c;">CREDIT NOTE #{cn_num}</td>
                <td style="padding: 3.5pt 8pt; border-bottom: 1px solid #f1f5f9;">Return: {cn_cust}</td>
                <td style="padding: 3.5pt 8pt; border-bottom: 1px solid #f1f5f9; text-align: center;">Account / {cn_curr}</td>
                <td style="padding: 3.5pt 8pt; border-bottom: 1px solid #f1f5f9; text-align: right; color: #b91c1c; font-weight: 700;">-${cn_tot:,.2f}</td>
            </tr>
            """
        for exp in expenses_list:
            e_num = exp[0] or '-'
            e_amt = float(exp[1] or 0)
            e_cat = exp[2] or 'Expense'
            e_title = exp[3] or ''
            e_cashier = exp[4] or ''
            e_pm = exp[5] or 'Cash'
            deductions_html += f"""
            <tr>
                <td style="padding: 3.5pt 8pt; border-bottom: 1px solid #f1f5f9; font-weight: 600; color: #d97706;">EXPENSE #{e_num}</td>
                <td style="padding: 3.5pt 8pt; border-bottom: 1px solid #f1f5f9;">[{e_cat}] {e_title} {f'(By: {e_cashier})' if e_cashier else ''}</td>
                <td style="padding: 3.5pt 8pt; border-bottom: 1px solid #f1f5f9; text-align: center;">{e_pm}</td>
                <td style="padding: 3.5pt 8pt; border-bottom: 1px solid #f1f5f9; text-align: right; color: #d97706; font-weight: 700;">-${e_amt:,.2f}</td>
            </tr>
            """
        deductions_html += f"""
                <tr style="background-color: #fef2f2; font-weight: 700;">
                    <td colspan="3" style="padding: 5pt 8pt; border-top: 1px solid #f87171; color: #991b1b;">TOTAL SHIFT DEDUCTIONS</td>
                    <td style="padding: 5pt 8pt; border-top: 1px solid #f87171; text-align: right; color: #991b1b;">-${(total_credit_notes + total_expenses):,.2f}</td>
                </tr>
                </tbody>
            </table>
        </div>
        """

    # Station display
    station_str = f"Station {station}" if station else "POS Station"
    if station_name:
        station_str += f" ({station_name})"

    # App version
    try:
        import main as _m_main
        app_v = getattr(_m_main, "APP_VERSION", "2.0.8.48")
    except Exception:
        app_v = "2.0.8.48"

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
    f_title = f"{round(base_font_pt * 1.53, 1)}pt"
    f_h1 = f"{round(base_font_pt * 1.45, 1)}pt"
    f_head = f"{round(base_font_pt * 1.05, 1)}pt"

    reprint_badge = """
    <div style="display: inline-block; background-color: #fee2e2; color: #b91c1c; border: 1px solid #f87171; font-size: 8pt; font-weight: 700; padding: 2pt 8pt; border-radius: 3pt; margin-left: 8pt;">
        *** REPRINT ***
    </div>
    """ if is_reprint else ""

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Shift Reconciliation Report - #{shift_num}</title>
    <style>
        {embedded_fonts}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: 'Poppins', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            font-size: {f_base};
            color: #0f172a;
            background-color: #ffffff;
            line-height: 1.35;
        }}
        .page-container {{
            width: 100%;
            padding: 0;
        }}
        .header-table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 12pt;
        }}
        .meta-card {{
            background-color: #f8fafc;
            border: 1px solid #cbd5e1;
            border-radius: 5pt;
            padding: 8pt 12pt;
            margin-bottom: 12pt;
        }}
        .meta-grid {{
            width: 100%;
            border-collapse: collapse;
        }}
        .meta-grid td {{
            padding: 2.5pt 4pt;
            font-size: 8.5pt;
        }}
        .meta-label {{
            color: #64748b;
            font-weight: 500;
        }}
        .meta-value {{
            color: #0f172a;
            font-weight: 700;
        }}
        .signoff-box {{
            margin-top: 18pt;
            border-top: 1px dashed #94a3b8;
            padding-top: 10pt;
        }}
        .signoff-table {{
            width: 100%;
            border-collapse: collapse;
        }}
        .signoff-line {{
            border-bottom: 1px solid #0f172a;
            height: 24pt;
            margin-bottom: 4pt;
        }}
    </style>
</head>
<body>
    <div class="page-container">
        <!-- Company & Report Header -->
        <table class="header-table">
            <tr>
                <td style="vertical-align: top; width: 60%;">
                    <div style="display: flex; align-items: center;">
                        {logo_img}
                        <div>
                            <div style="font-size: 14pt; font-weight: 800; color: #0a2342; letter-spacing: -0.2pt;">{company_name}</div>
                            {f'<div style="font-size: 8pt; color: #475569;">{address_str}</div>' if address_str else ''}
                            <div style="font-size: 8pt; color: #475569;">
                                {f'Tel: {tel} ' if tel else ''}
                                {f'| Email: {email}' if email else ''}
                            </div>
                            <div style="font-size: 7.5pt; color: #64748b;">
                                {f'TIN: <b>{tin}</b> ' if tin else ''}
                                {f'| VAT: <b>{vat_no}</b>' if vat_no else ''}
                            </div>
                        </div>
                    </div>
                </td>
                <td style="vertical-align: top; text-align: right; width: 40%;">
                    <div style="font-size: 13pt; font-weight: 800; color: #0a2342; text-transform: uppercase;">
                        Shift Reconciliation{reprint_badge}
                    </div>
                    <div style="font-size: 9.5pt; font-weight: 700; color: #1e3a8a; margin-top: 2pt;">
                        Shift #{shift_num}
                    </div>
                    <div style="font-size: 8pt; color: #64748b; margin-top: 2pt;">
                        Date: <b>{shift_date}</b>
                    </div>
                </td>
            </tr>
        </table>

        <!-- Shift Overview Meta Card -->
        <div class="meta-card">
            <table class="meta-grid">
                <tr>
                    <td style="width: 25%;"><span class="meta-label">Workstation:</span></td>
                    <td style="width: 25%;"><span class="meta-value">{station_str}</span></td>
                    <td style="width: 25%;"><span class="meta-label">Shift Duration:</span></td>
                    <td style="width: 25%;"><span class="meta-value">{start_time} - {end_time}</span></td>
                </tr>
                <tr>
                    <td><span class="meta-label">Closing Cashier:</span></td>
                    <td><span class="meta-value">{closing_cashier or 'Manager / Admin'}</span></td>
                    <td><span class="meta-label">Total Invoices:</span></td>
                    <td><span class="meta-value">{total_invoices}</span></td>
                </tr>
                <tr>
                    <td><span class="meta-label">Opening Balance:</span></td>
                    <td><span class="meta-value">${opening_balance:,.2f}</span></td>
                    <td><span class="meta-label">Generated At:</span></td>
                    <td><span class="meta-value">{datetime.now().strftime("%d/%m/%Y %H:%M:%S")}</span></td>
                </tr>
            </table>
        </div>

        <!-- Payment Methods Summary Table -->
        <div>
            <div style="font-size: 11pt; font-weight: 700; color: #0a2342; border-bottom: 2px solid #0a2342; padding-bottom: 3pt; margin-bottom: 6pt;">
                PAYMENT METHODS SUMMARY
            </div>
            <table style="width: 100%; border-collapse: collapse; font-size: 8.5pt;">
                <thead>
                    <tr style="background-color: #0a2342; color: #ffffff; font-size: 8pt; text-transform: uppercase;">
                        <th style="padding: 6pt 8pt; text-align: left;">Payment Method</th>
                        <th style="padding: 6pt 8pt; text-align: center;">Currency</th>
                        <th style="padding: 6pt 8pt; text-align: right;">Expected</th>
                        <th style="padding: 6pt 8pt; text-align: right;">Counted / Actual</th>
                        <th style="padding: 6pt 8pt; text-align: right;">Variance</th>
                    </tr>
                </thead>
                <tbody>
                    {summary_rows_html}
                    {summary_totals_html}
                </tbody>
            </table>
        </div>

        <!-- Cashier Breakdown Section -->
        {cashiers_html}

        <!-- Shift Deductions Section -->
        {deductions_html}

        <!-- Manager & Cashier Sign-off Block -->
        <div class="signoff-box">
            <table class="signoff-table">
                <tr>
                    <td style="width: 45%; vertical-align: top;">
                        <div style="font-size: 8pt; font-weight: 700; color: #475569;">CASHIER / OPERATOR SIGNATURE:</div>
                        <div class="signoff-line"></div>
                        <div style="font-size: 7.5pt; color: #64748b; display: flex; justify-content: space-between;">
                            <span>Name: {closing_cashier or '___________________'}</span>
                            <span>Date: ________________</span>
                        </div>
                    </td>
                    <td style="width: 10%;"></td>
                    <td style="width: 45%; vertical-align: top;">
                        <div style="font-size: 8pt; font-weight: 700; color: #475569;">SUPERVISOR / MANAGER SIGNATURE:</div>
                        <div class="signoff-line"></div>
                        <div style="font-size: 7.5pt; color: #64748b; display: flex; justify-content: space-between;">
                            <span>Name: ___________________</span>
                            <span>Date: ________________</span>
                        </div>
                    </td>
                </tr>
            </table>
        </div>

        <!-- Footer -->
        <div style="margin-top: 14pt; border-top: 1px solid #e2e8f0; padding-top: 5pt; text-align: center; font-size: 7.5pt; color: #94a3b8;">
            Havano POS & ERP System &bull; Version {app_v} &bull; End of Shift Reconciliation Report &bull; Page 1 of 1
        </div>
    </div>
</body>
</html>
"""
    return html


def _html_to_pdf(html_content: str, pdf_path: str, timeout_ms: int = 15000) -> None:
    """Renders HTML to PDF using QWebEngineView (Chromium) or native QTextDocument fallback."""
    os.environ.setdefault(
        "QTWEBENGINE_CHROMIUM_FLAGS",
        "--disable-gpu --disable-software-rasterizer --disable-gpu-compositing --no-sandbox",
    )

    from PySide6.QtGui import QTextDocument, QPageSize, QPageLayout
    from PySide6.QtPrintSupport import QPrinter

    # 1. Attempt QWebEngineView
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
                log.warning("[a4_shift_recon] QWebEngine PDF export timed out - falling back to QTextDocument")
        else:
            log.warning("[a4_shift_recon] QWebEngine failed to load HTML - falling back to QTextDocument")
    except Exception as e:
        log.warning(f"[a4_shift_recon] QWebEngineView failed ({e}) - falling back to QTextDocument")

    # 2. Universal fallback: QTextDocument + QPrinter
    try:
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
            log.info("[a4_shift_recon] Successfully generated A4 PDF via QTextDocument fallback.")
            return
        raise RuntimeError("QTextDocument failed to create PDF file.")
    except Exception as e:
        log.error(f"[a4_shift_recon] All PDF generation methods failed: {e}", exc_info=True)
        raise


def show_a4_shift_recon_preview(
    shift: dict | None = None,
    totals: list | None = None,
    reconciliation_data: dict | None = None,
    print_data: dict | None = None,
    is_reprint: bool = False,
    parent=None
) -> bool:
    """
    Renders the A4 Shift Reconciliation Report and launches PdfPreviewDialog.
    """
    try:
        import tempfile, os
        from views.dialogs.pdf_preview_dialog import PdfPreviewDialog

        html_content = render_a4_shift_recon_html(
            shift=shift,
            totals=totals,
            reconciliation_data=reconciliation_data,
            print_data=print_data,
            is_reprint=is_reprint,
        )

        s_num = (
            (reconciliation_data.get('shift_number') if reconciliation_data else None)
            or (print_data.get('shift_number') if print_data else None)
            or (shift.get('shift_number') if shift else None)
            or 'Current'
        )
        pdf_path = os.path.join(tempfile.gettempdir(), f"Shift_Recon_A4_Shift_{s_num}.pdf")

        _html_to_pdf(html_content, pdf_path)

        dlg = PdfPreviewDialog(pdf_path, title=f"A4 Shift Reconciliation - Shift #{s_num}", parent=parent)
        dlg.exec()
        return True

    except Exception as exc:
        log.error("Failed to show A4 Shift Reconciliation Preview: %s", exc, exc_info=True)
        from PySide6.QtWidgets import QMessageBox, QApplication
        active_w = parent or QApplication.activeWindow()
        QMessageBox.critical(active_w, "Preview Error", f"Could not generate A4 Shift Reconciliation Preview:\n{exc}")
        return False
