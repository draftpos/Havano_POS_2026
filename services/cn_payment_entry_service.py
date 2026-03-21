# =============================================================================
# services/cn_payment_entry_service.py
#
# Standalone service — does NOT touch any existing files.
#
# WHAT IT DOES:
#   1. After a credit note is created locally → create_cn_payment_entry()
#      inserts a row into payment_entries (payment_type='Pay', synced=0).
#      frappe_invoice_ref is NULL until the CN lands on Frappe.
#
#   2. After the CN syncs to Frappe and we have a frappe_cn_ref →
#      link_cn_payment_to_frappe() sets frappe_invoice_ref so the existing
#      push_unsynced_payment_entries() daemon picks it up automatically.
#
#   3. _build_cn_payload() pushes a "Pay" Payment Entry to Frappe that
#      references the Frappe credit note invoice.
#
# HOW TO WIRE IT IN (two one-liners, nothing else changes):
#
#   In models/credit_note.py — at the bottom of create_credit_note(),
#   just before the return statement:
#
#       try:
#           from services.cn_payment_entry_service import create_cn_payment_entry
#           create_cn_payment_entry(cn_result)
#       except Exception as _e:
#           import logging; logging.getLogger("CreditNote").warning(
#               "CN payment entry skipped: %s", _e)
#
#   In services/credit_note_sync_service.py — right after mark_cn_synced():
#
#       if frappe_cn_ref and frappe_cn_ref not in ("True", "SYNCED", True):
#           try:
#               from services.cn_payment_entry_service import link_cn_payment_to_frappe
#               link_cn_payment_to_frappe(cn.get("cn_number", ""), frappe_cn_ref)
#           except Exception as _e:
#               log.warning("[cn-sync] link payment failed: %s", _e)
#
# DB MIGRATION (run once — only if payment_type column doesn't exist yet):
#
#   ALTER TABLE payment_entries
#       ADD payment_type NVARCHAR(20) NOT NULL DEFAULT 'Receive';
#
# =============================================================================
from __future__ import annotations

import json
import logging
import urllib.request
import urllib.error
from datetime import date

log = logging.getLogger("CnPaymentEntry")


# =============================================================================
# HELPERS — reuse the same credential/host/defaults pattern as other services
# =============================================================================

def _get_credentials() -> tuple[str, str]:
    try:
        from services.credentials import get_credentials
        return get_credentials()
    except Exception:
        pass
    try:
        from database.db import get_connection
        conn = get_connection(); cur = conn.cursor()
        cur.execute("SELECT api_key, api_secret FROM company_defaults WHERE id = 1")
        row = cur.fetchone(); conn.close()
        if row and row[0] and row[1]:
            return row[0], row[1]
    except Exception:
        pass
    import os
    return os.environ.get("HAVANO_API_KEY", ""), os.environ.get("HAVANO_API_SECRET", "")


def _get_defaults() -> dict:
    try:
        from models.company_defaults import get_defaults
        return get_defaults() or {}
    except Exception:
        return {}


def _get_host() -> str:
    try:
        host = _get_defaults().get("server_api_host", "").strip().rstrip("/")
        if host:
            return host
    except Exception:
        pass
    return "https://apk.havano.cloud"


# =============================================================================
# 1. CREATE — called right after create_credit_note() succeeds
# =============================================================================

def create_cn_payment_entry(cn: dict) -> int | None:
    """
    Inserts one 'Pay' (refund) row into payment_entries for the given CN.

    cn dict must contain:
        cn_number, original_sale_id, customer_name, currency, total

    frappe_invoice_ref is left NULL — link_cn_payment_to_frappe() fills it
    in once the CN is confirmed on Frappe, at which point the existing
    push_unsynced_payment_entries() daemon will push it automatically.

    Returns the new payment_entry id, or None if already exists / error.
    """
    from database.db import get_connection
    conn = get_connection()
    cur  = conn.cursor()

    cn_num = cn.get("cn_number", "")
    if not cn_num:
        log.warning("create_cn_payment_entry called with no cn_number — skipping.")
        return None

    # Idempotency: one payment entry per CN
    cur.execute(
        "SELECT id FROM payment_entries WHERE reference_no = ? AND payment_type = 'Pay'",
        (cn_num,)
    )
    if cur.fetchone():
        conn.close()
        log.debug("CN payment entry already exists for %s — skipping.", cn_num)
        return None

    customer = (cn.get("customer_name") or "default").strip() or "default"
    currency = (cn.get("currency")      or "USD").strip().upper()
    amount   = float(cn.get("total")    or 0)
    today    = date.today().isoformat()

    try:
        cur.execute("""
            INSERT INTO payment_entries (
                sale_id, sale_invoice_no, frappe_invoice_ref,
                party, party_name,
                paid_amount, received_amount, source_exchange_rate,
                paid_to_account_currency, currency,
                mode_of_payment,
                reference_no, reference_date,
                remarks, payment_type, synced
            ) OUTPUT INSERTED.id
            VALUES (?, ?, NULL, ?, ?, ?, ?, 1.0, ?, ?, ?, ?, ?, ?, ?, 0)
        """, (
            cn.get("original_sale_id"),        # sale_id
            cn_num,                            # sale_invoice_no (display label)
            customer, customer,                # party, party_name
            amount, amount,                    # paid_amount, received_amount
            currency, currency,                # paid_to_account_currency, currency
            "Cash",                            # mode_of_payment — refund default
            cn_num,                            # reference_no
            today,                             # reference_date
            f"Credit Note Refund — {cn_num}",  # remarks
            "Pay",                             # payment_type ← refund direction
        ))
        new_id = int(cur.fetchone()[0])
        conn.commit()
        log.info("CN payment entry %d created for %s (%.2f %s)",
                 new_id, cn_num, amount, currency)
        return new_id

    except Exception as e:
        conn.rollback()
        log.error("Failed to create CN payment entry for %s: %s", cn_num, e)
        return None
    finally:
        conn.close()


# =============================================================================
# 2. LINK — called by credit_note_sync_service after CN is confirmed on Frappe
# =============================================================================

def link_cn_payment_to_frappe(cn_number: str, frappe_cn_ref: str) -> None:
    """
    Sets frappe_invoice_ref on the 'Pay' payment entry for this CN.
    Once set, the existing push_unsynced_payment_entries() daemon will
    pick it up and push the Payment Entry to Frappe automatically.
    """
    if not cn_number or not frappe_cn_ref:
        return

    from database.db import get_connection
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        UPDATE payment_entries
        SET    frappe_invoice_ref = ?
        WHERE  reference_no = ?
          AND  payment_type  = 'Pay'
          AND  synced        = 0
          AND  (frappe_invoice_ref IS NULL OR frappe_invoice_ref = '')
    """, (frappe_cn_ref, cn_number))
    updated = cur.rowcount
    conn.commit()
    conn.close()

    if updated:
        log.info("Linked CN %s → Frappe ref %s on payment entry.", cn_number, frappe_cn_ref)
    else:
        log.debug("link_cn_payment_to_frappe: no unlinked row found for %s.", cn_number)


# =============================================================================
# 3. PUSH — build the Frappe payload for a 'Pay' payment entry
#    Called by _push_payment_entry() in payment_entry_service.py IF you want
#    this service to push independently. Otherwise the existing daemon handles
#    it once frappe_invoice_ref is set. Both approaches work.
# =============================================================================

def _build_cn_payload(pe: dict, defaults: dict,
                      api_key: str, api_secret: str, host: str) -> dict:
    """
    Builds the Frappe Payment Entry payload for a credit note refund.

    Key differences from a normal sale payment:
      - payment_type = "Pay"   (money goes OUT to the customer)
      - paid_from              (the cash/bank account, not paid_to)
      - references the Frappe credit-note Sales Invoice
    """
    company  = defaults.get("server_company",   "")
    currency = (pe.get("currency") or "USD").upper()
    amount   = abs(float(pe.get("paid_amount") or 0))
    mop      = pe.get("mode_of_payment") or "Cash"

    # Resolve the GL account (same logic as the normal payment service)
    paid_from = (pe.get("paid_to") or "").strip()
    if not paid_from:
        try:
            from models.gl_account import get_account_for_payment
            acct = get_account_for_payment(currency, company)
            if acct:
                paid_from = acct["name"]
        except Exception:
            pass

    if not paid_from:
        paid_from = defaults.get("server_pos_account", "")

    frappe_cn_ref = (pe.get("frappe_invoice_ref") or "").strip()

    payload: dict = {
        "doctype":                  "Payment Entry",
        "payment_type":             "Pay",
        "party_type":               "Customer",
        "party":                    pe.get("party") or "default",
        "party_name":               pe.get("party_name") or "default",
        "paid_from_account_currency": currency,
        "paid_amount":              amount,
        "received_amount":          amount,
        "source_exchange_rate":     float(pe.get("source_exchange_rate") or 1.0),
        "reference_no":             pe.get("reference_no") or pe.get("sale_invoice_no", ""),
        "reference_date":           pe.get("reference_date") or date.today().isoformat(),
        "remarks":                  pe.get("remarks") or f"Credit Note Refund — {mop}",
        "mode_of_payment":          mop,
        "docstatus":                1,
    }

    if paid_from:
        payload["paid_from"] = paid_from
    if company:
        payload["company"] = company

    # Link to the Frappe credit-note Sales Invoice
    if frappe_cn_ref:
        payload["references"] = [{
            "reference_doctype": "Sales Invoice",
            "reference_name":    frappe_cn_ref,
            "allocated_amount":  amount,
        }]

    return payload


def push_cn_payment_entry(pe: dict) -> str | None:
    """
    Optional: push a single CN payment entry directly (bypasses the daemon).
    Returns Frappe PAY-xxxxx ref on success, None on failure.
    """
    api_key, api_secret = _get_credentials()
    if not api_key or not api_secret:
        log.warning("push_cn_payment_entry: no credentials.")
        return None

    host     = _get_host()
    defaults = _get_defaults()
    payload  = _build_cn_payload(pe, defaults, api_key, api_secret, host)

    req = urllib.request.Request(
        url=f"{host}/api/resource/Payment%20Entry",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type":  "application/json",
            "Accept":        "application/json",
            "Authorization": f"token {api_key}:{api_secret}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            name = (json.loads(resp.read()).get("data") or {}).get("name", "")
            log.info("CN Payment Entry pushed → Frappe %s", name)
            return name or "SYNCED"

    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode())
            msg = err.get("exception") or err.get("message") or f"HTTP {e.code}"
        except Exception:
            msg = f"HTTP {e.code}"
        if e.code == 409:
            return "DUPLICATE"
        log.error("CN Payment Entry HTTP %s: %s", e.code, msg)
        return None

    except urllib.error.URLError as e:
        log.warning("CN Payment Entry network error: %s", e.reason)
        return None

    except Exception as e:
        log.error("CN Payment Entry unexpected error: %s", e)
        return None