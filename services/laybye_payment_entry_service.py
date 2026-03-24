# =============================================================================
# services/laybye_payment_entry_service.py
#
# Standalone service — does NOT touch any existing files.
#
# WHAT IT DOES:
#   1. After a Sales Order (Laybye) is created locally with a deposit →
#      create_laybye_payment_entry() inserts a row into payment_entries
#      (payment_type='Receive', synced=0).
#      frappe_invoice_ref is NULL until the SO lands on Frappe.
#
#   2. After the SO syncs to Frappe and we have a frappe_ref →
#      link_laybye_payment_to_frappe() sets frappe_invoice_ref so the
#      existing push_unsynced_payment_entries() daemon picks it up.
#
# HOW TO WIRE IT IN (two one-liners, nothing else changes):
#
#   In main_window.py — right after _create_sales_order() succeeds
#   (after line: order_id = _create_sales_order(...)):
#
#       if deposit_amount and deposit_amount > 0:
#           try:
#               from services.laybye_payment_entry_service import create_laybye_payment_entry
#               from models.sales_order import get_order_by_id
#               so = get_order_by_id(order_id)
#               create_laybye_payment_entry(so)
#           except Exception as _e:
#               import logging; logging.getLogger("Laybye").warning(
#                   "Laybye payment entry skipped: %s", _e)
#
#   In services/sales_order_upload_service.py — right after mark_order_synced():
#
#       if frappe_ref and isinstance(frappe_ref, str):
#           try:
#               from services.laybye_payment_entry_service import link_laybye_payment_to_frappe
#               link_laybye_payment_to_frappe(order.get("order_no", ""), frappe_ref)
#           except Exception as _e:
#               log.warning("[so-sync] link laybye payment failed: %s", _e)
#
# =============================================================================
from __future__ import annotations

import json
import logging
import urllib.request
import urllib.error
from datetime import date

log = logging.getLogger("LaybyePaymentEntry")


# =============================================================================
# HELPERS
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
# 1. CREATE — called right after _create_sales_order() succeeds (deposit > 0)
# =============================================================================

def create_laybye_payment_entry(so: dict) -> int | None:
    """
    Inserts one 'Receive' (deposit) row into payment_entries for the given SO.

    so dict must contain:
        order_no, customer_name, deposit_amount, deposit_method, company

    frappe_invoice_ref is left NULL — link_laybye_payment_to_frappe() fills
    it in once the SO is confirmed on Frappe, at which point the existing
    push_unsynced_payment_entries() daemon will push it automatically.

    Returns the new payment_entry id, or None if no deposit / already exists / error.
    """
    order_no       = (so.get("order_no") or "").strip()
    deposit_amount = float(so.get("deposit_amount") or 0)

    if not order_no:
        log.warning("create_laybye_payment_entry called with no order_no — skipping.")
        return None

    if deposit_amount <= 0:
        log.debug("Order %s has no deposit — skipping payment entry.", order_no)
        return None

    from database.db import get_connection
    conn = get_connection()
    cur  = conn.cursor()

    # Idempotency: one payment entry per order_no
    cur.execute(
        "SELECT id FROM payment_entries WHERE reference_no = ? AND payment_type = 'Receive'",
        (order_no,)
    )
    if cur.fetchone():
        conn.close()
        log.debug("Laybye payment entry already exists for %s — skipping.", order_no)
        return None

    customer = (so.get("customer_name") or "default").strip() or "default"
    currency = (so.get("currency")      or "USD").strip().upper() or "USD"
    method   = (so.get("deposit_method") or "Cash").strip() or "Cash"
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
            so.get("id"),                              # sale_id (local SO id)
            order_no,                                  # sale_invoice_no (display)
            customer, customer,                        # party, party_name
            deposit_amount, deposit_amount,            # paid_amount, received_amount
            currency, currency,                        # paid_to_account_currency, currency
            method,                                    # mode_of_payment
            order_no,                                  # reference_no
            today,                                     # reference_date
            f"Laybye Deposit — {order_no} via {method}",  # remarks
            "Receive",                                 # payment_type
        ))
        new_id = int(cur.fetchone()[0])
        conn.commit()
        log.info("Laybye payment entry %d created for %s (%.2f %s via %s)",
                 new_id, order_no, deposit_amount, currency, method)
        return new_id

    except Exception as e:
        conn.rollback()
        log.error("Failed to create laybye payment entry for %s: %s", order_no, e)
        return None
    finally:
        conn.close()


# =============================================================================
# 2. LINK — called by sales_order_upload_service after SO is confirmed on Frappe
# =============================================================================

def link_laybye_payment_to_frappe(order_no: str, frappe_so_ref: str) -> None:
    """
    Sets frappe_invoice_ref on the 'Receive' payment entry for this SO.
    Once set, the existing push_unsynced_payment_entries() daemon will
    pick it up and push the Payment Entry to Frappe automatically.
    """
    if not order_no or not frappe_so_ref:
        return

    from database.db import get_connection
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        UPDATE payment_entries
        SET    frappe_invoice_ref = ?
        WHERE  reference_no  = ?
          AND  payment_type  = 'Receive'
          AND  synced        = 0
          AND  (frappe_invoice_ref IS NULL OR frappe_invoice_ref = '')
    """, (frappe_so_ref, order_no))
    updated = cur.rowcount
    conn.commit()
    conn.close()

    if updated:
        log.info("Linked SO %s → Frappe ref %s on laybye payment entry.",
                 order_no, frappe_so_ref)
    else:
        log.debug("link_laybye_payment_to_frappe: no unlinked row found for %s.", order_no)


# =============================================================================
# 3. PUSH — build the Frappe payload for a Laybye deposit Payment Entry
#    The existing push_unsynced_payment_entries() daemon calls this
#    automatically once frappe_invoice_ref is set. You don't need to call
#    this directly unless you want to push immediately.
# =============================================================================

def _build_laybye_payload(pe: dict, defaults: dict) -> dict:
    """
    Builds the Frappe Payment Entry payload for a laybye deposit.

    Key difference from CN: payment_type = "Receive" (money comes IN).
    References the Frappe Sales Order (not a Sales Invoice).
    """
    company  = defaults.get("server_company",   "")
    currency = (pe.get("currency") or "USD").upper()
    amount   = abs(float(pe.get("paid_amount") or 0))
    mop      = pe.get("mode_of_payment") or "Cash"

    # Resolve the GL account to receive into
    paid_to = (pe.get("paid_to") or "").strip()
    if not paid_to:
        try:
            from models.gl_account import get_account_for_payment
            acct = get_account_for_payment(currency, company)
            if acct:
                paid_to = acct["name"]
        except Exception:
            pass

    if not paid_to:
        paid_to = defaults.get("server_pos_account", "")

    frappe_so_ref = (pe.get("frappe_invoice_ref") or "").strip()

    payload: dict = {
        "doctype":                    "Payment Entry",
        "payment_type":               "Receive",
        "party_type":                 "Customer",
        "party":                      pe.get("party") or "default",
        "party_name":                 pe.get("party_name") or "default",
        "paid_to_account_currency":   currency,
        "paid_amount":                amount,
        "received_amount":            amount,
        "source_exchange_rate":       float(pe.get("source_exchange_rate") or 1.0),
        "reference_no":               pe.get("reference_no") or pe.get("sale_invoice_no", ""),
        "reference_date":             pe.get("reference_date") or date.today().isoformat(),
        "remarks":                    pe.get("remarks") or f"Laybye Deposit — {mop}",
        "mode_of_payment":            mop,
        "docstatus":                  1,
    }

    if paid_to:
        payload["paid_to"] = paid_to
    if company:
        payload["company"] = company

    # Link to the Frappe Sales Order
    if frappe_so_ref:
        payload["references"] = [{
            "reference_doctype": "Sales Order",
            "reference_name":    frappe_so_ref,
            "allocated_amount":  amount,
        }]

    return payload


def push_laybye_payment_entry(pe: dict) -> str | None:
    """
    Optional: push a single laybye payment entry directly (bypasses the daemon).
    Returns Frappe PAY-xxxxx ref on success, None on failure.
    """
    api_key, api_secret = _get_credentials()
    if not api_key or not api_secret:
        log.warning("push_laybye_payment_entry: no credentials.")
        return None

    host     = _get_host()
    defaults = _get_defaults()
    payload  = _build_laybye_payload(pe, defaults)

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
            log.info("Laybye Payment Entry pushed → Frappe %s", name)
            return name or "SYNCED"

    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode())
            msg = err.get("exception") or err.get("message") or f"HTTP {e.code}"
        except Exception:
            msg = f"HTTP {e.code}"
        if e.code == 409:
            return "DUPLICATE"
        log.error("Laybye Payment Entry HTTP %s: %s", e.code, msg)
        return None

    except urllib.error.URLError as e:
        log.warning("Laybye Payment Entry network error: %s", e.reason)
        return None

    except Exception as e:
        log.error("Laybye Payment Entry unexpected error: %s", e)
        return None