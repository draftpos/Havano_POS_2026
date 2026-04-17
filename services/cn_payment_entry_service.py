# # =============================================================================
# # services/cn_payment_entry_service.py
# #
# # Creates and manages Payment Entries for Credit Note refunds.
# #
# # KEY CONCEPT: For Credit Notes in ERPNext/Frappe:
# #   - payment_type = "Pay" (money going OUT to customer)
# #   - paid_from = Bank/Cash account (where money comes FROM)
# #   - paid_to = Receivables/Debtors account (where money goes TO)
# #   - References the Credit Note Sales Invoice
# #
# # FLOW:
# #   1. After credit note created locally → create_cn_payment_entry()
# #      inserts a row into payment_entries (payment_type='Pay', synced=0)
# #
# #   2. After CN syncs to Frappe → link_cn_payment_to_frappe()
# #      sets frappe_invoice_ref so the existing payment sync daemon picks it up
# #
# #   3. Payment sync daemon pushes the "Pay" Payment Entry to Frappe
# # =============================================================================
# from __future__ import annotations

# import json
# import logging
# import urllib.request
# import urllib.error
# from datetime import date

# log = logging.getLogger("CnPaymentEntry")


# # =============================================================================
# # HELPERS — reuse the same credential/host/defaults pattern as other services
# # =============================================================================

# def _get_credentials() -> tuple[str, str]:
#     try:
#         from services.credentials import get_credentials
#         return get_credentials()
#     except Exception:
#         pass
#     try:
#         from database.db import get_connection
#         conn = get_connection()
#         cur = conn.cursor()
#         cur.execute("SELECT api_key, api_secret FROM company_defaults WHERE id = 1")
#         row = cur.fetchone()
#         conn.close()
#         if row and row[0] and row[1]:
#             return row[0], row[1]
#     except Exception:
#         pass
#     import os
#     return os.environ.get("HAVANO_API_KEY", ""), os.environ.get("HAVANO_API_SECRET", "")


# def _get_defaults() -> dict:
#     try:
#         from models.company_defaults import get_defaults
#         return get_defaults() or {}
#     except Exception:
#         return {}


# from services.site_config import get_host as _get_host


# def _get_cash_account(currency: str = "USD", company: str = "") -> str:
#     """
#     Get a cash/bank account (where money comes FROM for refunds).
#     This is the paid_from account.
#     """
#     try:
#         from models.gl_account import get_all_accounts
#         accounts = get_all_accounts()
        
#         # Look for Cash or Bank accounts
#         for acc in accounts:
#             acc_type = acc.get("account_type", "").lower()
#             acc_curr = acc.get("account_currency", "USD").upper()
#             acc_name = acc.get("name", "")
#             is_group = acc.get("is_group", 0)
            
#             if is_group: # Skip group accounts
#                 continue
                
#             if (acc_type in ["cash", "bank", "payment account"] or 
#                 "cash" in acc_name.lower() or 
#                 "bank" in acc_name.lower()):
#                 if acc_curr == currency.upper():
#                     log.debug(f"Found cash/bank account: {acc_name}")
#                     return acc_name
        
#         # Fallback: try to get from company defaults
#         defaults = _get_defaults()
#         cash_acc = defaults.get("server_pos_account", "")
#         if cash_acc:
#             log.debug(f"Using fallback cash account from defaults: {cash_acc}")
#             return cash_acc
                
#     except Exception as e:
#         log.warning(f"Error getting cash account: {e}")
    
#     log.warning("No cash account found for refund payment entry")
#     return ""


# def _get_receivables_account(currency: str = "USD", company: str = "") -> str:
#     """
#     Get a receivables/debtors account (where money goes TO for refunds).
#     This is the paid_to account.
#     """
#     try:
#         from models.gl_account import get_all_accounts
#         accounts = get_all_accounts()
        
#         # Look for Receivable or Debtors accounts
#         for acc in accounts:
#             acc_type = acc.get("account_type", "").lower()
#             acc_curr = acc.get("account_currency", "USD").upper()
#             acc_name = acc.get("name", "")
#             is_group = acc.get("is_group", 0)
            
#             if is_group: # Skip group accounts
#                 continue
                
#             if (acc_type == "receivable" or 
#                 "debtors" in acc_name.lower() or 
#                 "receivable" in acc_name.lower()):
#                 if acc_curr == currency.upper():
#                     log.debug(f"Found receivables account: {acc_name}")
#                     return acc_name
        
#         # Fallback: derive from company abbreviation
#         if company and " - " in company:
#             abbr = company.split(" - ")[-1].strip()
#             fallback = f"Debtors - {abbr}"
#             log.debug(f"Using fallback receivables account: {fallback}")
#             return fallback
                
#     except Exception as e:
#         log.warning(f"Error getting receivables account: {e}")
    
#     log.warning("No receivables account found for refund payment entry")
#     return ""


# # =============================================================================
# # 1. CREATE — called right after create_credit_note() succeeds
# # =============================================================================

# def create_cn_payment_entry(cn: dict) -> int | None:
#     """
#     Inserts one 'Pay' (refund) row into payment_entries for the given CN.

#     cn dict must contain:
#         cn_number, original_sale_id, customer_name, currency, total

#     Returns the new payment_entry id, or None if already exists / error.
#     """
#     from database.db import get_connection
#     conn = get_connection()
#     cur = conn.cursor()

#     cn_num = cn.get("cn_number", "")
#     if not cn_num:
#         log.warning("create_cn_payment_entry called with no cn_number — skipping.")
#         return None

#     # Idempotency: one payment entry per CN
#     cur.execute(
#         "SELECT id FROM payment_entries WHERE reference_no = ? AND payment_type = 'Pay'",
#         (cn_num,)
#     )
#     if cur.fetchone():
#         conn.close()
#         log.debug("CN payment entry already exists for %s — skipping.", cn_num)
#         return None

#     customer = (cn.get("customer_name") or "Default").strip() or "Default"
#     currency = (cn.get("currency") or "USD").strip().upper()
#     amount = float(cn.get("total") or 0)
#     today = date.today().isoformat()

#     try:
#         cur.execute("""
#             INSERT INTO payment_entries (
#                 sale_id, sale_invoice_no, frappe_invoice_ref,
#                 party, party_name,
#                 paid_amount, received_amount, source_exchange_rate,
#                 paid_to_account_currency, currency,
#                 mode_of_payment,
#                 reference_no, reference_date,
#                 remarks, payment_type, synced
#             ) OUTPUT INSERTED.id
#             VALUES (?, ?, NULL, ?, ?, ?, ?, 1.0, ?, ?, ?, ?, ?, ?, ?, 0)
#         """, (
#             cn.get("original_sale_id"),        # sale_id
#             cn_num,                            # sale_invoice_no
#             customer, customer,                # party, party_name
#             amount, amount,                    # paid_amount, received_amount
#             currency, currency,                # paid_to_account_currency, currency
#             "Cash",                            # mode_of_payment
#             cn_num,                            # reference_no
#             today,                             # reference_date
#             f"Credit Note Refund — {cn_num}",  # remarks
#             "Pay",                             # payment_type ← refund direction
#         ))
#         new_id = int(cur.fetchone()[0])
#         conn.commit()
#         log.info("CN payment entry %d created for %s (%.2f %s)",
#                  new_id, cn_num, amount, currency)
#         return new_id

#     except Exception as e:
#         conn.rollback()
#         log.error("Failed to create CN payment entry for %s: %s", cn_num, e)
#         return None
#     finally:
#         conn.close()


# # =============================================================================
# # 2. LINK — called by credit_note_sync_service after CN is confirmed on Frappe
# # =============================================================================

# def link_cn_payment_to_frappe(cn_number: str, frappe_cn_ref: str) -> None:
#     """
#     Sets frappe_invoice_ref on the 'Pay' payment entry for this CN.
#     Once set, the existing push_unsynced_payment_entries() daemon will
#     pick it up and push the Payment Entry to Frappe automatically.
#     """
#     if not cn_number or not frappe_cn_ref:
#         return

#     from database.db import get_connection
#     conn = get_connection()
#     cur = conn.cursor()
#     cur.execute("""
#         UPDATE payment_entries
#         SET    frappe_invoice_ref = ?
#         WHERE  reference_no = ?
#           AND  payment_type  = 'Pay'
#           AND  synced        = 0
#           AND  (frappe_invoice_ref IS NULL OR frappe_invoice_ref = '')
#     """, (frappe_cn_ref, cn_number))
#     updated = cur.rowcount
#     conn.commit()
#     conn.close()

#     if updated:
#         log.info("Linked CN %s → Frappe ref %s on payment entry.", cn_number, frappe_cn_ref)
#     else:
#         log.debug("link_cn_payment_to_frappe: no unlinked row found for %s.", cn_number)


# # =============================================================================
# # 3. BUILD PAYLOAD — for a 'Pay' Payment Entry (refund)
# # =============================================================================

# def _build_cn_payload(pe: dict, defaults: dict,
#                       api_key: str, api_secret: str, host: str) -> dict:
#     """
#     Builds the Frappe Payment Entry payload for a credit note refund.

#     CORRECT ERPNext/Frappe structure for Credit Note refund:
#         payment_type = "Pay"  (money going OUT to customer)
#         paid_from = Cash/Bank account (where money comes FROM)
#         paid_to = Debtors/Receivables account (where money goes TO)
#         references the Credit Note Sales Invoice
#     """
#     company = defaults.get("server_company", "")
#     currency = (pe.get("currency") or "USD").upper()
#     amount = abs(float(pe.get("paid_amount") or 0))
#     mop = pe.get("mode_of_payment") or "Cash"

#     # For refund: paid_from = Cash/Bank account (source of funds)
#     paid_from = _get_cash_account(currency, company)
#     if not paid_from:
#         # Try to get from the payment entry itself
#         paid_from = (pe.get("paid_to") or "").strip()  # Note: stored in paid_to field
#         if not paid_from:
#             paid_from = defaults.get("server_pos_account", "")
    
#     # For refund: paid_to = Receivables/Debtors account (destination)
#     paid_to = _get_receivables_account(currency, company)
#     if not paid_to:
#         # Fallback to a reasonable default
#         if company and " - " in company:
#             abbr = company.split(" - ")[-1].strip()
#             paid_to = f"Debtors - {abbr}"
#         else:
#             paid_to = "Debtors"

#     frappe_cn_ref = (pe.get("frappe_invoice_ref") or "").strip()
#     party = pe.get("party") or "Default"
#     reference_no = pe.get("reference_no") or pe.get("sale_invoice_no", "")
#     reference_date = pe.get("reference_date") or date.today().isoformat()

#     payload = {
#         "doctype": "Payment Entry",
#         "payment_type": "Pay",  # ← KEY: refund direction
#         "party_type": "Customer",
#         "party": party,
#         "party_name": party,
#         # Money comes FROM cash/bank account
#         "paid_from": paid_from,
#         "paid_from_account_currency": currency,
#         # Money goes TO receivables/debtors account
#         "paid_to": paid_to,
#         "paid_to_account_currency": currency,
#         "paid_amount": amount,
#         "paid_amount_after_tax": amount,
#         "received_amount": amount,
#         "received_amount_after_tax": amount,
#         "source_exchange_rate": float(pe.get("source_exchange_rate") or 1.0),
#         "reference_no": reference_no,
#         "reference_date": reference_date,
#         "remarks": pe.get("remarks") or f"Credit Note Refund — {mop}",
#         "mode_of_payment": mop,
#         "docstatus": 1,
#     }

#     if company:
#         payload["company"] = company

#     # Link to the Frappe Credit Note (Sales Invoice with negative total)
#     if frappe_cn_ref:
#         payload["references"] = [{
#             "reference_doctype": "Sales Invoice",
#             "reference_name": frappe_cn_ref,
#             "allocated_amount": amount,
#             "total_amount": amount,
#         }]

#     # Debug logging
#     log.debug(f"CN Payment Payload - paid_from: {paid_from}, paid_to: {paid_to}, type: Pay")
    
#     return payload


# # =============================================================================
# # 4. PUSH — directly push a CN payment entry (alternative to using daemon)
# # =============================================================================

# def push_cn_payment_entry(pe: dict) -> str | None:
#     """
#     Push a single CN payment entry directly to Frappe.
#     Returns Frappe PAY-xxxxx ref on success, None on failure.
#     """
#     api_key, api_secret = _get_credentials()
#     if not api_key or not api_secret:
#         log.warning("push_cn_payment_entry: no credentials.")
#         return None

#     host = _get_host()
#     defaults = _get_defaults()
#     payload = _build_cn_payload(pe, defaults, api_key, api_secret, host)

#     print("\n" + "="*60)
#     print("CN REFUND PAYMENT ENTRY PAYLOAD:")
#     print(json.dumps(payload, indent=2, default=str))
#     print("="*60 + "\n")

#     req = urllib.request.Request(
#         url=f"{host}/api/resource/Payment%20Entry",
#         data=json.dumps(payload, default=str).encode("utf-8"),
#         method="POST",
#         headers={
#             "Content-Type": "application/json",
#             "Accept": "application/json",
#             "Authorization": f"token {api_key}:{api_secret}",
#         },
#     )
    
#     try:
#         with urllib.request.urlopen(req, timeout=30) as resp:
#             data = json.loads(resp.read().decode())
#             name = (data.get("data") or {}).get("name", "")
#             log.info(f"✅ CN Payment Entry pushed → Frappe {name}")
#             return name or "SYNCED"

#     except urllib.error.HTTPError as e:
#         try:
#             err = json.loads(e.read().decode())
#             msg = err.get("exception") or err.get("message") or f"HTTP {e.code}"
#         except Exception:
#             msg = f"HTTP {e.code}"
        
#         print(f"\n❌ Frappe rejected CN Payment Entry: {msg}")
        
#         if e.code == 409:
#             return "DUPLICATE"
#         log.error(f"CN Payment Entry HTTP {e.code}: {msg}")
#         return None

#     except urllib.error.URLError as e:
#         log.warning(f"CN Payment Entry network error: {e.reason}")
#         return None

#     except Exception as e:
#         log.error(f"CN Payment Entry unexpected error: {e}")
#         return None