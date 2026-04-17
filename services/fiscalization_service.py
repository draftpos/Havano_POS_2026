# services/fiscalization_service.py - PRODUCTION READY (FINAL - NO CONVERSION FOR ZIG)

import threading
import time
from typing import Optional, List
from dataclasses import dataclass
import xml.etree.ElementTree as ET
import json

from models.fiscal_settings import FiscalSettingsRepository
from services.zimra_api_service import get_zimra_service
from database.db import get_connection, fetchone_dict, fetchall_dicts

HS_CODE_DEFAULT = "99999999"


@dataclass
class FiscalInvoiceItem:
    line_number: int
    item_code:   str
    item_name:   str
    item_name2:  str
    quantity:    float
    price:       float
    total:       float
    vat:         float
    vat_rate:    float
    vat_name:    str

    @staticmethod
    def build_items_xml(items: List["FiscalInvoiceItem"]) -> str:
        root = ET.Element("ITEMS")
        for item in items:
            item_elem = ET.SubElement(root, "ITEM")
            ET.SubElement(item_elem, "HH").text       = str(item.line_number)
            ET.SubElement(item_elem, "ITEMCODE").text  = HS_CODE_DEFAULT
            ET.SubElement(item_elem, "ITEMNAME").text  = str(item.item_name)[:100]
            ET.SubElement(item_elem, "ITEMNAME2").text = str(item.item_name2)[:100]
            ET.SubElement(item_elem, "QTY").text       = f"{item.quantity:.2f}"
            ET.SubElement(item_elem, "PRICE").text     = f"{item.price:.2f}"
            ET.SubElement(item_elem, "TOTAL").text     = f"{item.total:.2f}"
            ET.SubElement(item_elem, "VAT").text       = f"{item.vat:.2f}"
            ET.SubElement(item_elem, "VATR").text      = f"{item.vat_rate:.3f}"
            ET.SubElement(item_elem, "VNAME").text     = str(item.vat_name)[:20]
        return ET.tostring(root, encoding="unicode")


@dataclass
class FiscalizationBatchResult:
    total_count:   int = 0
    success_count: int = 0
    failed_count:  int = 0
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class FiscalizationService:

    def __init__(self):
        self._settings_repo = FiscalSettingsRepository()
        self._zimra_service = get_zimra_service()

    def is_fiscalization_enabled(self) -> bool:
        settings = self._settings_repo.get_settings()
        return settings is not None and settings.enabled

    # =========================================================================
    # SALE FISCALIZATION - NO CONVERSION EVER
    # =========================================================================

    def process_sale_fiscalization(self, sale_id: int, skip_sync: bool = False) -> bool:
        try:
            settings = self._settings_repo.get_settings()

            if not settings or not settings.enabled:
                print(f"ℹ️ Fiscalization disabled, skipping for sale {sale_id}")
                self._update_sale_fiscal_status(sale_id, "not_required")
                return True

            sale = self._get_sale_by_id(sale_id)
            if not sale:
                raise Exception(f"Sale not found: {sale_id}")

            if sale.get("fiscal_status") == "fiscalized":
                print(f"✓ Sale {sale_id} is already fiscalized")
                return True

            print(f"📝 Starting fiscalization for sale {sale_id}")
            self._update_sale_fiscal_status(sale_id, "pending")

            sale_items = self._get_sale_items(sale_id)
            if not sale_items:
                print(f"⚠️ No items found for sale {sale_id}")
                self._update_sale_fiscal_status(sale_id, "failed")
                return False

            # Get currency from sale record - USE AS IS, NO CONVERSION
            fiscal_currency = sale.get("currency", "USD").upper()
            fiscal_tendered = abs(float(sale.get("tendered") or 0))
            
            # Map Zimbabwe currencies to ZIG for ZIMRA
            if fiscal_currency in ("ZWD", "ZWL", "ZWG"):
                fiscal_currency = "ZIG"
            
            # Build items using values as-is from database (already in correct currency)
            fiscal_items = self._build_fiscal_items(sale_items)
            items_xml = FiscalInvoiceItem.build_items_xml(fiscal_items)

            invoice_number = str(sale.get("invoice_no", sale_id))
            customer_name = sale.get("customer_name", "Walk-in Customer") or "Walk-in Customer"

            print(f"\n{'='*60}")
            print(f"SALE FISCALIZATION PAYLOAD:")
            print(f"{'='*60}")
            print(f"  invoice_flag: 0")
            print(f"  currency: {fiscal_currency}")
            print(f"  invoice_number: {invoice_number}")
            print(f"  tendered: {fiscal_tendered:.2f}")
            print(f"{'='*60}\n")

            result = self._zimra_service.send_invoice(
                settings=settings,
                invoice_number=invoice_number,
                currency=fiscal_currency,
                customer_name=customer_name,
                trade_name=customer_name,
                items_xml=items_xml,
                tendered=fiscal_tendered,
            )

            if not result.is_success:
                raise Exception(f"ZIMRA API error: {result.error}")
            if result.data is None:
                raise Exception("No data returned from ZIMRA")

            fd = result.data
            self._update_sale_fiscal_data(
                sale_id=sale_id,
                fiscal_status="fiscalized",
                qr_code=fd.qr_code,
                verification_code=fd.verification_code,
                receipt_counter=fd.receipt_counter,
                global_no=str(fd.receipt_global_no),
            )

            print(f"✅ Sale {sale_id} fiscalized — Global No: {fd.receipt_global_no}")
            return True

        except Exception as e:
            error_msg = str(e)
            print(f"❌ Fiscalization failed for sale {sale_id}: {error_msg}")
            import traceback
            traceback.print_exc()
            self._update_sale_fiscal_error(sale_id, error_msg)
            return False

    # =========================================================================
    # CREDIT NOTE FISCALIZATION - NO CONVERSION EVER
    # =========================================================================

    def process_credit_note_fiscalization(self, cn_id: int) -> bool:
        try:
            settings = self._settings_repo.get_settings()

            if not settings or not settings.enabled:
                print(f"ℹ️ Fiscalization disabled — skipping credit note {cn_id}")
                self._update_cn_fiscal_status(cn_id, "not_required")
                return True

            cn = self._get_cn_by_id(cn_id)
            if not cn:
                raise Exception(f"Credit note not found: {cn_id}")

            if cn.get("fiscal_status") == "fiscalized":
                print(f"✓ Credit note {cn_id} already fiscalized")
                return True

            cn_number = cn.get("cn_number", str(cn_id))
            original_inv_no = cn.get("original_invoice_no", "")
            original_sale_id = cn.get("original_sale_id")
            
            original_global_no = ""
            if original_sale_id:
                original_sale = self._get_sale_by_id(original_sale_id)
                if original_sale:
                    original_global_no = original_sale.get("fiscal_global_no", "")
                    print(f"📋 Original sale {original_sale_id} fiscal_global_no: {original_global_no}")
            
            # USE CREDIT NOTE'S OWN CURRENCY - NO CONVERSION
            fiscal_currency = cn.get("currency", "USD").upper()
            fiscal_tendered = abs(float(cn.get("total") or 0))
            customer_name = cn.get("customer_name", "Walk-in Customer") or "Walk-in Customer"
            
            # Map Zimbabwe currencies to ZIG for ZIMRA
            if fiscal_currency in ("ZWD", "ZWL", "ZWG"):
                fiscal_currency = "ZIG"

            print(f"📝 Credit note: {cn_number}")
            print(f"   Original invoice: {original_inv_no}")
            print(f"   Original global_no: {original_global_no}")
            print(f"   Currency: {fiscal_currency}")
            print(f"   Tendered: {fiscal_tendered:.2f}")
            
            self._update_cn_fiscal_status(cn_id, "pending")

            cn_items = self._get_cn_items(cn_id)
            if not cn_items:
                raise Exception(f"No items found for credit note {cn_id}")

            # Build items - USE EXACT VALUES, NO CONVERSION
            fiscal_items = []
            for idx, item in enumerate(cn_items, 1):
                qty = abs(float(item.get("qty", 0)))
                price = abs(float(item.get("price", 0)))
                total = abs(float(item.get("total", qty * price)))
                tax_amount = abs(float(item.get("tax_amount", 0)))
                tax_rate = float(item.get("tax_rate", 0))
                tax_type = str(item.get("tax_type", "")).upper()

                if tax_amount <= 0.005 or tax_rate <= 0:
                    vat_name = "EXEMPT"
                elif tax_type in ("VAT", "STANDARD VAT"):
                    vat_name = "VAT"
                elif tax_type in ("ZERO", "ZERO RATED"):
                    vat_name = "ZERO RATED"
                else:
                    vat_name = "VAT" if tax_rate > 0 else "EXEMPT"

                print(f"   CN Item {idx}: {item.get('product_name')}  "
                      f"qty={qty}  price={price:.2f}  total={total:.2f}  "
                      f"vat={tax_amount:.2f}  rate={tax_rate}%")

                fiscal_items.append(FiscalInvoiceItem(
                    line_number=idx,
                    item_code=HS_CODE_DEFAULT,
                    item_name=str(item.get("product_name", ""))[:100],
                    item_name2=str(item.get("product_name", ""))[:100],
                    quantity=qty,
                    price=price,
                    total=total,
                    vat=tax_amount,
                    vat_rate=tax_rate / 100,
                    vat_name=vat_name,
                ))
            
            items_xml = FiscalInvoiceItem.build_items_xml(fiscal_items)

            print(f"\n{'='*60}")
            print(f"CREDIT NOTE PAYLOAD:")
            print(f"{'='*60}")
            print(f"  invoice_flag: 1")
            print(f"  currency: {fiscal_currency}")
            print(f"  invoice_number: {cn_number}")
            print(f"  original_invoice_no: {original_inv_no}")
            print(f"  global_invoice_no: {original_global_no}")
            print(f"  tendered: {fiscal_tendered:.2f}")
            print(f"{'='*60}\n")

            result = self._zimra_service.send_invoice(
                settings=settings,
                invoice_number=cn_number,
                currency=fiscal_currency,
                customer_name=customer_name,
                trade_name=customer_name,
                items_xml=items_xml,
                invoice_flag=1,
                original_invoice_no=original_inv_no,
                global_invoice_no=original_global_no,
                tendered=fiscal_tendered,
            )

            if not result.is_success:
                if result.error and "already exist" in result.error.lower():
                    print(f"⚠️ CN {cn_id} already exists — marking fiscalized")
                    self._update_cn_fiscal_status(cn_id, "fiscalized")
                    return True
                raise Exception(f"ZIMRA API error: {result.error}")
            
            if result.data is None:
                raise Exception("No data returned from ZIMRA")

            fd = result.data
            self._update_cn_fiscal_data(
                cn_id=cn_id,
                fiscal_status="fiscalized",
                qr_code=fd.qr_code,
                verification_code=fd.verification_code,
                receipt_counter=fd.receipt_counter,
                global_no=str(fd.receipt_global_no),
            )

            print(f"✅ Credit note {cn_number} fiscalized successfully")
            print(f"   New Global No: {fd.receipt_global_no}")
            return True

        except Exception as e:
            error_msg = str(e)
            print(f"❌ Credit note fiscalization failed for {cn_id}: {error_msg}")
            import traceback
            traceback.print_exc()
            self._update_cn_fiscal_error(cn_id, error_msg)
            return False

    def trigger_credit_note_fiscalization_background(self, cn_id: int):
        def _run():
            retry_delay = 30
            attempt = 0
            time.sleep(5)
            while True:
                attempt += 1
                try:
                    if not self.is_fiscalization_enabled():
                        self._update_cn_fiscal_status(cn_id, "not_required")
                        return
                    cn = self._get_cn_by_id(cn_id)
                    if cn and cn.get("fiscal_status") == "fiscalized":
                        print(f"[CN] CN {cn_id} already fiscalized — stopping")
                        return
                    print(f"[CN] Attempt {attempt} for CN {cn_id}")
                    if self.process_credit_note_fiscalization(cn_id):
                        print(f"[CN] ✅ CN {cn_id} done")
                        return
                    print(f"[CN] ❌ CN {cn_id} failed, retry in {retry_delay}s")
                    time.sleep(retry_delay)
                except Exception as e:
                    print(f"[CN] Error CN {cn_id}: {e}, retry in {retry_delay}s")
                    time.sleep(retry_delay)

        threading.Thread(target=_run, daemon=True).start()

    # =========================================================================
    # ITEM BUILDERS - NO CONVERSION, USE VALUES AS-IS
    # =========================================================================

    def _build_fiscal_items(self, sale_items: list) -> List[FiscalInvoiceItem]:
        """Build fiscal items using values as-is from database (already correct currency)."""
        fiscal_items = []
        for idx, item in enumerate(sale_items, 1):
            price = abs(float(item.get("price", 0)))
            qty = abs(float(item.get("qty", 1)))
            total = abs(float(item.get("total", 0)))
            tax_rate = float(item.get("tax_rate", 0))
            vat_amount = abs(float(item.get("tax_amount", 0)))
            tax_type = str(item.get("tax_type", "")).upper()

            if vat_amount <= 0.005 or tax_rate <= 0:
                vat_name = "EXEMPT"
            elif tax_type in ("VAT", "STANDARD VAT"):
                vat_name = "VAT"
            else:
                vat_name = "VAT" if tax_rate > 0 else "EXEMPT"

            fiscal_items.append(FiscalInvoiceItem(
                line_number=idx,
                item_code=HS_CODE_DEFAULT,
                item_name=str(item.get("product_name", ""))[:100],
                item_name2=str(item.get("product_name", ""))[:100],
                quantity=qty,
                price=price,
                total=total,
                vat=vat_amount,
                vat_rate=tax_rate / 100,
                vat_name=vat_name,
            ))
        return fiscal_items

    # =========================================================================
    # DATABASE HELPERS
    # =========================================================================

    def _get_sale_by_id(self, sale_id: int) -> Optional[dict]:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT id, invoice_no, invoice_number, total, tendered, method,
                       currency, customer_name, frappe_ref, created_at,
                       fiscal_status, fiscal_qr_code, fiscal_verification_code,
                       fiscal_receipt_counter, fiscal_global_no, fiscal_sync_date,
                       fiscal_error
                FROM sales WHERE id = ?
            """, (sale_id,))
            return fetchone_dict(cursor)
        finally:
            conn.close()

    def _get_sale_items(self, sale_id: int) -> List[dict]:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT id, part_no, product_name, qty, price, discount,
                       tax, total, tax_type, tax_rate, tax_amount, remarks
                FROM sale_items WHERE sale_id = ?
                ORDER BY id
            """, (sale_id,))
            return fetchall_dicts(cursor)
        finally:
            conn.close()

    def _update_sale_fiscal_status(self, sale_id: int, status: str) -> bool:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE sales SET fiscal_status = ? WHERE id = ?", (status, sale_id))
            conn.commit()
            return True
        finally:
            conn.close()

    def _update_sale_fiscal_data(self, sale_id: int, fiscal_status: str, qr_code: str = None,
                                  verification_code: str = None, receipt_counter: int = None,
                                  global_no: str = None) -> bool:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE sales
                SET fiscal_status = ?, fiscal_qr_code = ?, fiscal_verification_code = ?,
                    fiscal_receipt_counter = ?, fiscal_global_no = ?,
                    fiscal_sync_date = SYSDATETIME(), fiscal_error = NULL
                WHERE id = ?
            """, (fiscal_status, qr_code, verification_code, receipt_counter, global_no, sale_id))
            conn.commit()
            return True
        finally:
            conn.close()

    def _update_sale_fiscal_error(self, sale_id: int, error: str) -> bool:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE sales SET fiscal_status = 'failed', fiscal_error = ?,
                fiscal_sync_date = SYSDATETIME() WHERE id = ?
            """, (error[:500], sale_id))
            conn.commit()
            return True
        finally:
            conn.close()

    def _get_cn_by_id(self, cn_id: int) -> Optional[dict]:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT id, cn_number, original_sale_id, original_invoice_no,
                       frappe_ref, total, currency, cashier_name, customer_name, cn_status,
                       COALESCE(fiscal_status, 'pending') AS fiscal_status,
                       COALESCE(fiscal_qr_code, '') AS fiscal_qr_code,
                       COALESCE(fiscal_verification_code,'') AS fiscal_verification_code,
                       fiscal_receipt_counter, COALESCE(fiscal_global_no, '') AS fiscal_global_no,
                       fiscal_error
                FROM credit_notes WHERE id = ?
            """, (cn_id,))
            return fetchone_dict(cursor)
        finally:
            conn.close()

    def _get_cn_items(self, cn_id: int) -> List[dict]:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT part_no, product_name, qty, price, total, reason,
                       tax_amount, tax_rate, tax_type
                FROM credit_note_items WHERE credit_note_id = ?
                ORDER BY id
            """, (cn_id,))
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, r)) for r in cursor.fetchall()]
        finally:
            conn.close()

    def _update_cn_fiscal_status(self, cn_id: int, status: str) -> bool:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE credit_notes SET fiscal_status = ? WHERE id = ?", (status, cn_id))
            conn.commit()
            return True
        finally:
            conn.close()

    def _update_cn_fiscal_data(self, cn_id: int, fiscal_status: str, qr_code: str = None,
                                verification_code: str = None, receipt_counter: int = None,
                                global_no: str = None) -> bool:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE credit_notes
                SET fiscal_status = ?, fiscal_qr_code = ?, fiscal_verification_code = ?,
                    fiscal_receipt_counter = ?, fiscal_global_no = ?,
                    fiscal_sync_date = SYSDATETIME(), fiscal_error = NULL
                WHERE id = ?
            """, (fiscal_status, qr_code, verification_code, receipt_counter, global_no, cn_id))
            conn.commit()
            return True
        finally:
            conn.close()

    def _update_cn_fiscal_error(self, cn_id: int, error: str) -> bool:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE credit_notes SET fiscal_status = 'failed', fiscal_error = ?,
                fiscal_sync_date = SYSDATETIME() WHERE id = ?
            """, (error[:500], cn_id))
            conn.commit()
            return True
        finally:
            conn.close()

    def retry_fiscalization(self, sale_id: int) -> bool:
        return self.process_sale_fiscalization(sale_id, skip_sync=True)

    def get_pending_fiscalization_count(self) -> int:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM sales WHERE fiscal_status IN ('pending', 'failed')")
            row = cursor.fetchone()
            return int(row[0]) if row else 0
        finally:
            conn.close()

    def process_all_pending(self) -> FiscalizationBatchResult:
        result = FiscalizationBatchResult()
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id FROM sales WHERE fiscal_status IN ('pending', 'failed') ORDER BY id")
            pending = cursor.fetchall()
            result.total_count = len(pending)
        finally:
            conn.close()

        for row in pending:
            try:
                if self.process_sale_fiscalization(row[0], skip_sync=True):
                    result.success_count += 1
                else:
                    result.failed_count += 1
                    result.errors.append(f"Sale {row[0]}: Failed")
            except Exception as e:
                result.failed_count += 1
                result.errors.append(f"Sale {row[0]}: {e}")
        return result

    def get_pending_z_details(self) -> List[dict]:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT tax_type, tax_rate, SUM(tax_amount) AS total_vat,
                       SUM(total) AS total_gross, SUM(total - tax_amount) AS total_net
                FROM sale_items
                WHERE sale_id IN (SELECT id FROM sales WHERE fiscal_status IN ('pending', 'failed'))
                GROUP BY tax_type, tax_rate ORDER BY tax_rate DESC
            """)
            return fetchall_dicts(cursor)
        finally:
            conn.close()


_fiscalization_service = None

def get_fiscalization_service() -> FiscalizationService:
    global _fiscalization_service
    if _fiscalization_service is None:
        _fiscalization_service = FiscalizationService()
    return _fiscalization_service