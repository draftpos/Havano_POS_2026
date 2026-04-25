# services/pharmacy_label_zpl_printer.py

from __future__ import annotations

import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import QMessageBox, QWidget

from models.company_defaults import get_defaults

# =============================================================================
# Load printer from hardware settings
# =============================================================================
_HW_FILE = Path("app_data/hardware_settings.json")

def _get_pharmacy_printer_name() -> str:
    """Get pharmacy label printer from hardware settings"""
    try:
        if _HW_FILE.exists():
            with open(_HW_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("pharmacy_label_printer", "(None)")
    except Exception:
        pass
    return "(None)"

# Company details from database
class Company:
    """Company details pulled directly from database - no hardcoded defaults."""
    __slots__ = ('name', 'address', 'phone', 'footer')
    
    def __init__(self):
        try:
            d = get_defaults()
            self.name = d.get('company_name', '')
            self.address = ', '.join(filter(None, [d.get('address_1', ''), d.get('address_2', '')]))
            self.phone = d.get('phone', '')
            self.footer = d.get('footer_text', '')
        except Exception as e:
            print(f"[ZPL] Error loading company details: {e}")
            self.name = ''
            self.address = ''
            self.phone = ''
            self.footer = ''

# Load once at module start
COMPANY = Company()

# =============================================================================
# CONFIGURATION - Now read from hardware settings
# =============================================================================

LABEL_WIDTH_DOTS = 400
LABEL_HEIGHT_DOTS = 240

# =============================================================================
# ZPL Label Builder (unchanged)
# =============================================================================
def _build_zpl_label(
    product_name: str,
    part_no: str,
    qty: float,
    uom: str,
    price: float,
    batch_no: str,
    expiry_date,
    dosage: str = "",
    doctor_name: str = "",
    pharmacist_name: str = "",
) -> bytes:
    """Pharmacy label — bold product name, labelled fields, tight spacing."""
    try:
        # Expiry date
        if expiry_date:
            expiry_date_str = (
                expiry_date.isoformat()[:10]
                if hasattr(expiry_date, "isoformat")
                else str(expiry_date)[:10]
            )
        else:
            expiry_date_str = "N/A"

        # Field prep
        product_name    = (product_name or "UNKNOWN PRODUCT")[:32].upper()
        qty_val         = int(qty) if qty == int(qty) else round(qty, 2)
        qty_str         = f"{qty_val} {uom}".strip() if uom else str(qty_val)
        # price_str       = f"${price:,.2f}" if price else "$0.00"
        batch_no        = (batch_no or "N/A")[:20]
        dosage          = (dosage or "")[:40]
        pharmacist_name = (pharmacist_name or "")[:28]

        company_name    = COMPANY.name    or ""
        company_address = COMPANY.address or ""
        company_phone   = COMPANY.phone   or ""

        # Layout constants
        W   = LABEL_WIDTH_DOTS
        H   = LABEL_HEIGHT_DOTS
        X   = 10
        MID = 210

        zpl = [
            "^XA",
            f"^PW{W}",
            f"^LL{H}",
            "^CI28",
        ]

        y = 10

        # Product name
        zpl.append(f"^FO{X},{y}^FB{W - X * 2},2,0,L^A0N,34,28^FD{product_name}^FS")
        y += 42

        # Separator 1
        zpl.append(f"^FO{X},{y}^GB{W - X * 2},1,1^FS")
        y += 6

        # Qty / Price row
        zpl.append(f"^FO{X},{y}^A0N,20,15^FDQTY^FS")
        # zpl.append(f"^FO{MID},{y}^A0N,20,15^FDPRICE^FS")
        y += 20
        zpl.append(f"^FO{X},{y}^A0N,26,20^FD{qty_str}^FS")
        # zpl.append(f"^FO{MID},{y}^A0N,26,20^FD{price_str}^FS")
        y += 30

        # Batch / Expiry row
        zpl.append(f"^FO{X},{y}^A0N,20,15^FDBATCH^FS")
        zpl.append(f"^FO{MID},{y}^A0N,20,15^FDEXPIRY^FS")
        y += 20
        zpl.append(f"^FO{X},{y}^A0N,26,20^FD{batch_no}^FS")
        zpl.append(f"^FO{MID},{y}^A0N,26,20^FD{expiry_date_str}^FS")
        y += 32

        # Separator 2
        zpl.append(f"^FO{X},{y}^GB{W - X * 2},1,1^FS")
        y += 6

        # Dosage (only if present)
        if dosage:
            zpl.append(f"^FO{X},{y}^A0N,20,15^FDDOSAGE^FS")
            y += 20
            zpl.append(f"^FO{X},{y}^FB{W - X * 2},2,0,L^A0N,24,18^FD{dosage}^FS")
            y += 34
            zpl.append(f"^FO{X},{y}^GB{W - X * 2},1,1^FS")
            y += 6

        # Company block
        if company_name:
            zpl.append(f"^FO{X},{y}^A0N,26,20^FD{company_name}^FS")
            y += 28
        if company_address:
            zpl.append(f"^FO{X},{y}^A0N,20,14^FD{company_address}^FS")
            y += 22
        if company_phone:
            zpl.append(f"^FO{X},{y}^A0N,20,14^FD{company_phone}^FS")
            y += 22

        # Pharmacist
        if pharmacist_name:
            zpl.append(f"^FO{X},{y}^GB{W - X * 2},1,1^FS")
            y += 6
            zpl.append(
                f"^FO{X},{y}^A0N,20,15^FDPharmacist: {pharmacist_name}^FS"
            )

        zpl.append("^XZ")
        return "\n".join(zpl).encode("utf-8")

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[ZPL] Label build error: {e}")
        return (
            f"^XA\n"
            f"^FO10,10^A0N,24,20^FDLABEL ERROR^FS\n"
            f"^FO10,40^A0N,18,14^FD{str(e)[:50]}^FS\n"
            f"^XZ"
        ).encode("utf-8")
    

def _send_to_printer(zpl_bytes: bytes) -> bool:
    """Send ZPL to physical printer - uses printer from hardware settings"""
    printer_name = _get_pharmacy_printer_name()
    
    if printer_name == "(None)" or not printer_name:
        print("[ERROR] No pharmacy label printer configured in Hardware Settings")
        return False
    
    try:
        import win32print
    except ImportError:
        print("[ERROR] pywin32 not installed. Run: pip install pywin32")
        return False
    
    try:
        h_printer = win32print.OpenPrinter(printer_name)
        try:
            win32print.StartDocPrinter(h_printer, 1, ("Pharmacy Label", None, "RAW"))
            win32print.StartPagePrinter(h_printer)
            win32print.WritePrinter(h_printer, zpl_bytes)
            win32print.EndPagePrinter(h_printer)
            win32print.EndDocPrinter(h_printer)
        finally:
            win32print.ClosePrinter(h_printer)
        return True
    except Exception as e:
        print(f"[ERROR] Print failed for printer '{printer_name}': {e}")
        return False

# =============================================================================
# REAL DATA FETCHERS (unchanged)
# =============================================================================

def _get_pharmacy_context() -> dict:
    """Get REAL pharmacy name/address from company defaults"""
    try:
        from models.company_defaults import get_defaults
        d = get_defaults() or {}
    except Exception:
        d = {}
    
    name = (d.get("company_name") or COMPANY.name).strip()
    a1 = (d.get("address_1") or "").strip()
    a2 = (d.get("address_2") or "").strip()
    addr = ", ".join(p for p in (a1, a2) if p)
    return {"pharmacy_name": name, "pharmacy_address": addr}


def _get_current_pharmacist() -> str:
    """Get REAL logged-in pharmacist name"""
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


def _get_doctor_for_customer(customer_name: str) -> Optional[str]:
    """Get REAL doctor from customer record"""
    if not customer_name:
        return None
    
    try:
        from models.customer import get_customer_by_name
        cust = get_customer_by_name(customer_name)
    except Exception:
        return None
    
    if not cust:
        return None
    
    doc_id = cust.get("doctor_id")
    doc_name = (cust.get("doctor_frappe_name") or "").strip()
    
    try:
        from models.doctor import get_doctor_by_id, get_doctor_by_frappe_name
        doc = None
        if doc_id:
            try:
                doc = get_doctor_by_id(int(doc_id))
            except Exception:
                pass
        if not doc and doc_name:
            doc = get_doctor_by_frappe_name(doc_name)
        if doc and hasattr(doc, "full_name"):
            return doc.full_name
    except Exception:
        pass
    
    return doc_name or None


def _get_pharmacy_items_from_quotation(quotation_id: int) -> List[Dict[str, Any]]:
    """Fetch ONLY pharmacy items from a quotation"""
    from database.db import get_connection, fetchall_dicts
    
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT customer, cashier_name 
            FROM quotations WHERE id = ?
        """, (quotation_id,))
        header = fetchall_dicts(cur)
        header = header[0] if header else {}
        
        cur.execute("""
            SELECT 
                qi.item_name,
                qi.part_no,
                qi.qty,
                qi.uom,
                qi.dosage,
                qi.batch_no,
                qi.expiry_date,
                qi.rate as price
            FROM quotation_items qi
            WHERE qi.quotation_id = ? AND qi.is_pharmacy = 1
        """, (quotation_id,))
        
        rows = fetchall_dicts(cur)
        
        if not rows:
            return []
        
        pharm = _get_pharmacy_context()
        doctor = _get_doctor_for_customer(header.get("customer", ""))
        pharmacist = header.get("cashier_name") or _get_current_pharmacist()
        
        labels = []
        for row in rows:
            labels.append({
                "product_name": row.get("item_name") or "",
                "part_no": row.get("part_no") or "",
                "qty": row.get("qty", 0),
                "uom": row.get("uom") or "",
                "dosage": row.get("dosage") or "",
                "batch_no": row.get("batch_no") or "",
                "expiry_date": row.get("expiry_date") or "",
                "price": row.get("price", 0),
                "doctor_name": doctor,
                "pharmacist_name": pharmacist,
                "pharmacy_name": pharm["pharmacy_name"],
                "pharmacy_address": pharm["pharmacy_address"],
            })
        return labels
    except Exception as e:
        print(f"[ERROR] Failed to get pharmacy items from quotation {quotation_id}: {e}")
        return []
    finally:
        conn.close()


def _get_pharmacy_items_from_sale(sale_id: int) -> List[Dict[str, Any]]:
    """Fetch ONLY pharmacy items from a sale"""
    from models.sale import get_sale_by_id
    
    sale = get_sale_by_id(sale_id)
    if not sale:
        return []
    
    items = sale.get("items") or []
    pharm_items = [it for it in items if it.get("is_pharmacy")]
    
    if not pharm_items:
        return []
    
    pharm = _get_pharmacy_context()
    doctor = _get_doctor_for_customer(sale.get("customer_name") or "")
    pharmacist = sale.get("cashier_name") or sale.get("user") or _get_current_pharmacist()
    
    labels = []
    for it in pharm_items:
        labels.append({
            "product_name": it.get("product_name") or it.get("part_no") or "",
            "part_no": it.get("part_no") or "",
            "qty": it.get("qty", 0),
            "uom": it.get("uom") or "",
            "dosage": it.get("dosage") or "",
            "batch_no": it.get("batch_no") or "",
            "expiry_date": it.get("expiry_date") or "",
            "price": it.get("price", 0),
            "doctor_name": doctor,
            "pharmacist_name": pharmacist,
            "pharmacy_name": pharm["pharmacy_name"],
            "pharmacy_address": pharm["pharmacy_address"],
        })
    return labels


# =============================================================================
# PUBLIC API - Call these from your quotation/sale handlers
# =============================================================================

def auto_print_pharmacy_labels_for_quotation(
    quotation_id: int, 
    parent: Optional[QWidget] = None,
    silent: bool = True
) -> int:
    """Automatically print labels when a quotation WITH pharmacy items is created."""
    try:
        labels = _get_pharmacy_items_from_quotation(quotation_id)
    except Exception as e:
        print(f"[ERROR] Failed to get pharmacy items from quotation {quotation_id}: {e}")
        return 0
    
    if not labels:
        print(f"[Pharmacy Print] Quotation {quotation_id} has no pharmacy items - nothing printed")
        return 0
    
    printer_name = _get_pharmacy_printer_name()
    if printer_name == "(None)":
        print(f"[Pharmacy Print] No pharmacy label printer configured - skipping")
        if parent and not silent:
            QMessageBox.warning(parent, "Pharmacy Labels", 
                               "No pharmacy label printer configured.\nPlease configure in Settings → Hardware Settings.")
        return 0
    
    printed = 0
    for label in labels:
        zpl = _build_zpl_label(
            product_name=label["product_name"],
            part_no=label["part_no"],
            qty=label["qty"],
            uom=label["uom"],
            price=label["price"],
            batch_no=label["batch_no"],
            expiry_date=label["expiry_date"],
            dosage=label["dosage"],
            doctor_name=label["doctor_name"],
            pharmacist_name=label["pharmacist_name"],
        )
        
        if _send_to_printer(zpl):
            printed += 1
            print(f"  ✓ Printed: {label['product_name']} (x{label['qty']})")
        else:
            print(f"  ✗ Failed: {label['product_name']}")
    
    print(f"[Pharmacy Print] Quotation {quotation_id}: {printed}/{len(labels)} labels printed")
    
    if parent and not silent and printed > 0:
        QMessageBox.information(parent, "Pharmacy Labels", 
                               f"Printed {printed} pharmacy label(s) for quotation.")
    
    return printed


def auto_print_pharmacy_labels_for_sale(
    sale_id: int,
    parent: Optional[QWidget] = None,
    silent: bool = True
) -> int:
    """Automatically print labels when a sale WITH pharmacy items is confirmed."""
    try:
        labels = _get_pharmacy_items_from_sale(sale_id)
    except Exception as e:
        print(f"[ERROR] Failed to get pharmacy items from sale {sale_id}: {e}")
        return 0
    
    if not labels:
        print(f"[Pharmacy Print] Sale {sale_id} has no pharmacy items - nothing printed")
        return 0
    
    printer_name = _get_pharmacy_printer_name()
    if printer_name == "(None)":
        print(f"[Pharmacy Print] No pharmacy label printer configured - skipping")
        if parent and not silent:
            QMessageBox.warning(parent, "Pharmacy Labels", 
                               "No pharmacy label printer configured.\nPlease configure in Settings → Hardware Settings.")
        return 0
    
    printed = 0
    for label in labels:
        zpl = _build_zpl_label(
            product_name=label["product_name"],
            part_no=label["part_no"],
            qty=label["qty"],
            uom=label["uom"],
            price=label["price"],
            batch_no=label["batch_no"],
            expiry_date=label["expiry_date"],
            dosage=label["dosage"],
            doctor_name=label["doctor_name"],
            pharmacist_name=label["pharmacist_name"],
        )
        
        if _send_to_printer(zpl):
            printed += 1
            print(f"  ✓ Printed: {label['product_name']} (x{label['qty']})")
        else:
            print(f"  ✗ Failed: {label['product_name']}")
    
    print(f"[Pharmacy Print] Sale {sale_id}: {printed}/{len(labels)} labels printed")
    
    if parent and not silent and printed > 0:
        QMessageBox.information(parent, "Pharmacy Labels", 
                               f"Printed {printed} pharmacy label(s) for sale.")
    
    return printed


def test_printer_connection(parent: Optional[QWidget] = None) -> bool:
    """Test if configured pharmacy label printer is reachable"""
    printer_name = _get_pharmacy_printer_name()
    
    if printer_name == "(None)" or not printer_name:
        if parent:
            QMessageBox.warning(parent, "Printer Test", 
                               "No pharmacy label printer configured.\nPlease configure in Settings → Hardware Settings.")
        return False
    
    test_zpl = f"""^XA
^PW400
^LL240
^FO10,10^A0N,28,28^FDTEST PRINT^FS
^FO10,45^GB380,2,2^FS
^FO10,55^A0N,18,18^FDIf you see this, printer works!^FS
^XZ"""
    
    success = _send_to_printer(test_zpl.encode("utf-8"))
    
    if parent:
        if success:
            QMessageBox.information(parent, "Printer Test", 
                                   f"Test sent to {printer_name} successfully!")
        else:
            QMessageBox.warning(parent, "Printer Test", 
                               f"Failed to reach printer '{printer_name}'.\nMake sure it's turned on and connected.")
    return success