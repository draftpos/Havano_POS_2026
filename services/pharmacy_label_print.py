# =============================================================================
# services/pharmacy_label_print.py
# -----------------------------------------------------------------------------
# Pharmacy label PREVIEW service.
#
# Renders a small thermal label (50mm x 30mm) per pharmacy line item on a
# quotation or sale, and shows the batch in a QPrintPreviewDialog.
# No actual printing is performed here — preview only.
#
# Public API:
#   render_label_html(label: dict) -> str
#   preview_labels_for_quotation(parent, quotation_id: int) -> None
#   preview_labels_for_sale(parent, sale_id: int) -> None
# =============================================================================

from __future__ import annotations

import html
import traceback
from typing import List, Optional

from PySide6.QtCore import QSizeF, Qt
from PySide6.QtGui import QPageSize, QPageLayout, QTextDocument
from PySide6.QtPrintSupport import QPrinter, QPrintPreviewDialog
from PySide6.QtWidgets import QMessageBox, QWidget


# =============================================================================
# Small utility helpers
# =============================================================================

def _clean(value, fallback: str = "—") -> str:
    """Return a safe display string for a possibly-empty/None value."""
    if value is None:
        return fallback
    s = str(value).strip()
    return s or fallback


def _fmt_qty(qty) -> str:
    """Format qty as int when whole, else 2dp."""
    try:
        q = float(qty or 0)
    except Exception:
        return _clean(qty)
    return str(int(q)) if q == int(q) else f"{q:.2f}"


def _fmt_date(value) -> str:
    """Normalise a date value (datetime / date / str) to ISO-ish display."""
    if value is None or value == "":
        return "—"
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()[:10]
        except Exception:
            pass
    s = str(value).strip()
    return s[:10] if len(s) >= 10 else (s or "—")


# =============================================================================
# HTML template
# =============================================================================

_LABEL_TEMPLATE = (
    "<div style=\"font-family:'Segoe UI',Arial,sans-serif; padding:3mm; font-size:8pt;\">"
    # Pharmacy block goes ABOVE the drug details per UX request
    "<div style=\"font-weight:bold; font-size:8pt; text-align:center;\">{pharmacy_name}</div>"
    "<div style=\"font-size:7pt; color:#444; text-align:center;\">{pharmacy_address}</div>"
    "<hr style=\"margin:1mm 0;\">"
    "<div style=\"font-weight:bold; font-size:9pt;\">{item_name}</div>"
    "<div>{qty} by {uom}</div>"
    "<div>Dosage: {dosage}</div>"
    "<div>Batch: {batch_no} &nbsp;&nbsp; Exp: {expiry_date}</div>"
    "{doctor_block}"
    "<div style=\"margin-top:1mm;\">Pharmacist: {pharmacist_name}</div>"
    "</div>"
)


def render_label_html(label: dict) -> str:
    """Return HTML string for a single pharmacy label.

    Missing / empty fields fall back to "—" so the label never crashes and
    always renders something placeholder-shaped.
    """
    label = label or {}

    item_name       = html.escape(_clean(label.get("item_name")))
    qty             = html.escape(_fmt_qty(label.get("qty")))
    uom             = html.escape(_clean(label.get("uom"), ""))
    dosage          = html.escape(_clean(label.get("dosage")))
    batch_no        = html.escape(_clean(label.get("batch_no")))
    expiry_date     = html.escape(_fmt_date(label.get("expiry_date")))
    pharmacist      = html.escape(_clean(label.get("pharmacist_name")))
    pharmacy_name   = html.escape(_clean(label.get("pharmacy_name"), ""))
    pharmacy_addr   = html.escape(_clean(label.get("pharmacy_address"), ""))

    doctor_name_raw = label.get("doctor_name")
    if doctor_name_raw and str(doctor_name_raw).strip():
        doctor_block = (
            "<div>Doctor: "
            f"{html.escape(str(doctor_name_raw).strip())}"
            "</div>"
        )
    else:
        doctor_block = ""

    return _LABEL_TEMPLATE.format(
        item_name=item_name,
        qty=qty,
        uom=uom,
        dosage=dosage,
        batch_no=batch_no,
        expiry_date=expiry_date,
        doctor_block=doctor_block,
        pharmacist_name=pharmacist,
        pharmacy_name=pharmacy_name,
        pharmacy_address=pharmacy_addr,
    )


# =============================================================================
# Context builders
# =============================================================================

def _get_pharmacy_context() -> dict:
    """Pull pharmacy name + address from company_defaults (safe on empty)."""
    try:
        from models.company_defaults import get_defaults
        d = get_defaults() or {}
    except Exception as e:
        print(f"[pharmacy_label_print] company_defaults load failed: {e}")
        d = {}

    name = (d.get("company_name") or "").strip()
    a1   = (d.get("address_1")    or "").strip()
    a2   = (d.get("address_2")    or "").strip()
    addr = ", ".join(p for p in (a1, a2) if p)
    return {"pharmacy_name": name, "pharmacy_address": addr}


def _get_current_pharmacist_fallback() -> str:
    """When the document itself has no cashier/creator, fall back to the
    currently logged-in user's name (from company_defaults.server_* fields).

    This is a best-effort fallback — the sale record stores its own
    cashier_name, so sales won't hit this path.
    """
    try:
        from models.company_defaults import get_defaults
        d = get_defaults() or {}
    except Exception:
        d = {}
    for key in ("server_full_name", "server_username", "server_email"):
        v = (d.get(key) or "").strip()
        if v:
            return v
    return ""


def _resolve_doctor_name_for_customer(customer_name: str) -> Optional[str]:
    """Given a customer name (as stored on the document), look up the customer
    row and resolve the attached doctor (if any) by doctor_id or
    doctor_frappe_name. Returns None if the customer has no doctor.
    """
    if not customer_name:
        return None
    try:
        from models.customer import get_customer_by_name
        cust = get_customer_by_name(customer_name)
    except Exception as e:
        print(f"[pharmacy_label_print] customer lookup failed: {e}")
        return None
    if not cust:
        return None

    doc_id   = cust.get("doctor_id")
    doc_name = (cust.get("doctor_frappe_name") or "").strip()

    try:
        from models.doctor import get_doctor_by_id, get_doctor_by_frappe_name
        doc = None
        if doc_id:
            try:
                doc = get_doctor_by_id(int(doc_id))
            except Exception:
                doc = None
        if not doc and doc_name:
            doc = get_doctor_by_frappe_name(doc_name)
        if doc and getattr(doc, "full_name", None):
            return doc.full_name
    except Exception as e:
        print(f"[pharmacy_label_print] doctor lookup failed: {e}")

    # As a last resort, fall back to the stored frappe doctor name string
    return doc_name or None


# =============================================================================
# Quotation: load + build labels
# =============================================================================

def _fetch_pharmacy_items_for_quotation(quotation_id: int) -> list[dict]:
    """Query quotation_items directly so we can apply COALESCE defensively
    and still read the pharmacy fields even on legacy/partial rows.

    Returns a list of dicts with keys:
      item_name, qty, uom, dosage, batch_no, expiry_date
    """
    from database.db import get_connection, fetchall_dicts
    conn = get_connection()
    cur  = conn.cursor()
    try:
        try:
            cur.execute("""
                SELECT item_code, item_name, qty, uom,
                       COALESCE(is_pharmacy, 0) AS is_pharmacy,
                       dosage, batch_no, expiry_date
                FROM quotation_items
                WHERE quotation_id = ?
                ORDER BY id
            """, (quotation_id,))
            rows = fetchall_dicts(cur)
        except Exception:
            # Pharmacy columns not present yet — no pharmacy items possible.
            cur.execute("""
                SELECT item_code, item_name, qty, uom
                FROM quotation_items
                WHERE quotation_id = ?
                ORDER BY id
            """, (quotation_id,))
            raw = fetchall_dicts(cur)
            rows = []
            for r in raw:
                r["is_pharmacy"]  = 0
                r["dosage"]       = None
                r["batch_no"]     = None
                r["expiry_date"]  = None
                rows.append(r)
    finally:
        conn.close()

    items: list[dict] = []
    for r in rows:
        if not r.get("is_pharmacy"):
            continue
        items.append({
            "item_name":   r.get("item_name") or r.get("item_code") or "",
            "qty":         r.get("qty"),
            "uom":         r.get("uom") or "",
            "dosage":      r.get("dosage"),
            "batch_no":    r.get("batch_no"),
            "expiry_date": r.get("expiry_date"),
        })
    return items


def _fetch_quotation_header(quotation_id: int) -> Optional[dict]:
    """Return {customer, name, cashier_name} for a quotation id, or None if missing."""
    from database.db import get_connection, fetchone_dict
    conn = get_connection()
    cur  = conn.cursor()
    try:
        # cashier_name may be missing on legacy DBs that haven't migrated yet —
        # so guard the SELECT with a fallback to the legacy column set.
        try:
            cur.execute(
                "SELECT id, name, customer, "
                "       COALESCE(cashier_name, '') AS cashier_name "
                "FROM quotations WHERE id = ?",
                (quotation_id,),
            )
            row = fetchone_dict(cur)
        except Exception:
            cur.execute(
                "SELECT id, name, customer FROM quotations WHERE id = ?",
                (quotation_id,),
            )
            row = fetchone_dict(cur)
            if row is not None:
                row["cashier_name"] = ""
    finally:
        conn.close()
    return row


def _build_labels_for_quotation(quotation_id: int) -> list[dict]:
    header = _fetch_quotation_header(quotation_id)
    if not header:
        raise LookupError(f"Quotation id={quotation_id} not found")

    customer_name = header.get("customer") or ""

    pharm = _get_pharmacy_context()
    doctor_name = _resolve_doctor_name_for_customer(customer_name)
    # Prefer the creator stamped on the quote itself (Phase 9). Only fall back
    # to the currently-logged-in user when the quote predates that column or
    # was saved before the field was populated.
    pharmacist_name = (header.get("cashier_name") or "").strip()
    if not pharmacist_name:
        pharmacist_name = _get_current_pharmacist_fallback()

    line_items = _fetch_pharmacy_items_for_quotation(quotation_id)

    labels: list[dict] = []
    for li in line_items:
        labels.append({
            "item_name":       li["item_name"],
            "qty":             li["qty"],
            "uom":             li["uom"],
            "dosage":          li["dosage"],
            "batch_no":        li["batch_no"],
            "expiry_date":     li["expiry_date"],
            "pharmacist_name": pharmacist_name,
            "doctor_name":     doctor_name,
            "pharmacy_name":   pharm["pharmacy_name"],
            "pharmacy_address": pharm["pharmacy_address"],
        })
    return labels


# =============================================================================
# Sale: load + build labels
# =============================================================================

def _build_labels_for_sale(sale_id: int) -> list[dict]:
    from models.sale import get_sale_by_id

    sale = get_sale_by_id(sale_id)
    if not sale:
        raise LookupError(f"Sale id={sale_id} not found")

    items = sale.get("items") or []
    pharm_items = [it for it in items if it.get("is_pharmacy")]

    pharm = _get_pharmacy_context()
    doctor_name = _resolve_doctor_name_for_customer(sale.get("customer_name") or "")

    pharmacist_name = (sale.get("cashier_name") or sale.get("user") or "").strip()
    if not pharmacist_name:
        pharmacist_name = _get_current_pharmacist_fallback()

    labels: list[dict] = []
    for it in pharm_items:
        labels.append({
            # sale items store the product name under 'product_name'
            "item_name":       it.get("product_name") or it.get("part_no") or "",
            "qty":             it.get("qty"),
            # Phase 9: sale_items.uom is now populated from the cart on save.
            # Legacy rows stay empty and render qty alone.
            "uom":             it.get("uom") or "",
            "dosage":          it.get("dosage"),
            "batch_no":        it.get("batch_no"),
            "expiry_date":     it.get("expiry_date"),
            "pharmacist_name": pharmacist_name,
            "doctor_name":     doctor_name,
            "pharmacy_name":   pharm["pharmacy_name"],
            "pharmacy_address": pharm["pharmacy_address"],
        })
    return labels


# =============================================================================
# Print preview plumbing
# =============================================================================

# Label physical size (mm) — common small pharmacy thermal label
_LABEL_W_MM = 50.0
_LABEL_H_MM = 30.0


def _make_label_printer() -> QPrinter:
    printer = QPrinter(QPrinter.HighResolution)
    page_size = QPageSize(QSizeF(_LABEL_W_MM, _LABEL_H_MM),
                          QPageSize.Millimeter,
                          "PharmacyLabel")
    printer.setPageSize(page_size)
    printer.setPageOrientation(QPageLayout.Portrait)
    try:
        from PySide6.QtCore import QMarginsF
        printer.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Millimeter)
    except Exception:
        pass
    printer.setFullPage(True)
    return printer


def _build_document(labels: list[dict], printer: QPrinter) -> QTextDocument:
    """Assemble a single QTextDocument with one label per page."""
    pages_html: list[str] = []
    for idx, lbl in enumerate(labels):
        body = render_label_html(lbl)
        # Force a hard page break between labels (but not after the last).
        if idx < len(labels) - 1:
            body += "<div style=\"page-break-after: always;\"></div>"
        pages_html.append(body)

    full_html = (
        "<html><head><style>"
        "body { margin: 0; padding: 0; }"
        "</style></head><body>"
        + "".join(pages_html)
        + "</body></html>"
    )

    doc = QTextDocument()
    # Match the document page size to the printer so "one label per page"
    # renders cleanly in the preview.
    try:
        page_rect = printer.pageRect(QPrinter.DevicePixel)
        doc.setPageSize(QSizeF(page_rect.width(), page_rect.height()))
    except Exception:
        # Fall back to millimetre sizing if DevicePixel is unavailable
        pass
    doc.setHtml(full_html)
    return doc


def _show_preview(parent: Optional[QWidget],
                  labels: list[dict],
                  window_title: str) -> None:
    """Open a QPrintPreviewDialog rendering the given labels."""
    printer = _make_label_printer()
    doc = _build_document(labels, printer)

    dlg = QPrintPreviewDialog(printer, parent)
    dlg.setWindowTitle(window_title)
    try:
        dlg.setWindowState(Qt.WindowMaximized)
    except Exception:
        pass

    # Re-render the document into the preview every time it refreshes
    dlg.paintRequested.connect(lambda p: doc.print_(p))

    print(f"[pharmacy_label_print] Preview opened — {len(labels)} label(s).")
    dlg.exec()


def _toast_info(parent: Optional[QWidget], title: str, text: str) -> None:
    try:
        QMessageBox.information(parent, title, text)
    except Exception:
        print(f"[pharmacy_label_print] {title}: {text}")


def _toast_error(parent: Optional[QWidget], title: str, text: str) -> None:
    try:
        QMessageBox.warning(parent, title, text)
    except Exception:
        print(f"[pharmacy_label_print] {title}: {text}")


# =============================================================================
# Public entry points
# =============================================================================

def preview_labels_for_quotation(parent, quotation_id: int) -> None:
    """Open QPrintPreviewDialog showing one page per pharmacy line item on
    the given quotation. Shows a friendly message and returns if there are
    no pharmacy items, or if the quotation can't be loaded."""
    try:
        labels = _build_labels_for_quotation(int(quotation_id))
    except LookupError as e:
        print(f"[pharmacy_label_print] {e}")
        _toast_error(parent, "Preview Label",
                     "Could not load the selected quotation.")
        return
    except Exception as e:
        traceback.print_exc()
        _toast_error(parent, "Preview Label",
                     f"Failed to prepare labels:\n{e}")
        return

    if not labels:
        _toast_info(parent, "Preview Label",
                    "No pharmacy items on this document.")
        return

    try:
        _show_preview(parent, labels, "Pharmacy Label Preview — Quotation")
    except Exception as e:
        traceback.print_exc()
        _toast_error(parent, "Preview Label",
                     f"Could not open print preview:\n{e}")


def preview_labels_for_sale(parent, sale_id: int) -> None:
    """Open QPrintPreviewDialog showing one page per pharmacy line item on
    the given sale. Shows a friendly message and returns if there are no
    pharmacy items, or if the sale can't be loaded."""
    try:
        labels = _build_labels_for_sale(int(sale_id))
    except LookupError as e:
        print(f"[pharmacy_label_print] {e}")
        _toast_error(parent, "Preview Label",
                     "Could not load the selected invoice.")
        return
    except Exception as e:
        traceback.print_exc()
        _toast_error(parent, "Preview Label",
                     f"Failed to prepare labels:\n{e}")
        return

    if not labels:
        _toast_info(parent, "Preview Label",
                    "No pharmacy items on this document.")
        return

    try:
        _show_preview(parent, labels, "Pharmacy Label Preview — Invoice")
    except Exception as e:
        traceback.print_exc()
        _toast_error(parent, "Preview Label",
                     f"Could not open print preview:\n{e}")


# =============================================================================
# Dev-only self-test: render a dummy label so the layout can be eyeballed
# without needing a real quotation / sale in the DB.
# =============================================================================

if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)

    dummy_labels = [
        {
            "item_name":        "Paracetamol 500mg Tablets",
            "qty":              30,
            "uom":              "tablets",
            "dosage":           "1 tablet every 6 hours",
            "batch_no":         "BATCH-A12345",
            "expiry_date":      "2026-12-31",
            "pharmacist_name":  "Jane Doe",
            "doctor_name":      "Dr. John Smith",
            "pharmacy_name":    "Havano Pharmacy",
            "pharmacy_address": "123 Main Street, Harare",
        },
        {
            "item_name":        "Amoxicillin 250mg Capsules",
            "qty":              21,
            "uom":              "caps",
            "dosage":           "1 capsule 3x daily for 7 days",
            "batch_no":         "AMX-9988",
            "expiry_date":      "2025-06-30",
            "pharmacist_name":  "Jane Doe",
            "doctor_name":      "",
            "pharmacy_name":    "Havano Pharmacy",
            "pharmacy_address": "123 Main Street, Harare",
        },
    ]

    _show_preview(None, dummy_labels, "Pharmacy Label Preview — Demo")

    # Do not start the Qt loop; _show_preview opens exec() modally.
    sys.exit(0)
