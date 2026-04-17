# services/payment_upload_service.py

import json
import logging
import time
import threading
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, date

log = logging.getLogger("PaymentUpload")

SYNC_INTERVAL = 30
REQUEST_TIMEOUT = 30

_sync_lock = threading.RLock()
_sync_thread = None

# =============================================================================
# HELPERS
# =============================================================================

def _get_credentials():
    try:
        from services.credentials import get_credentials
        return get_credentials()
    except Exception:
        return "", ""

from services.site_config import get_host as _get_host

def _get_defaults():
    try:
        from models.company_defaults import get_defaults
        return get_defaults() or {}
    except Exception:
        return {}

def _save_payment_to_log(payment, payload, status, error=None):
    try:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "payment_id": payment.get("id"),
            "customer": payment.get("customer_name"),
            "amount": payment.get("amount"),
            "status": status,
            "error": error,
            "payload": payload
        }
        with open("payment_upload_service.log", "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except Exception as e:
        log.error(f"Failed to log payment: {e}")


def _fetch_receivable_account(customer_name: str, company: str,
                               api_key: str, api_secret: str, host: str) -> str | None:
    if not customer_name or not company:
        return None
    try:
        url = (
            f"{host}/api/method/erpnext.accounts.party.get_party_account"
            f"?party_type=Customer"
            f"&party={urllib.parse.quote(customer_name)}"
            f"&company={urllib.parse.quote(company)}"
        )
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"token {api_key}:{api_secret}")
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
            data = json.loads(r.read().decode())
            account = (data.get("message") or data.get("result") or "").strip()
            if account:
                log.debug("Receivable account for %s: %s", customer_name, account)
                return str(account)
    except Exception as e:
        log.debug("Could not fetch receivable account for %s: %s", customer_name, e)
    return None


# =============================================================================
# PAYLOAD BUILDER
# =============================================================================

def _build_payment_payload(payment: dict, defaults: dict,
                            api_key: str = "", api_secret: str = "",
                            host: str = "", leg: dict = None) -> dict:
    """
    Build a Frappe Payment Entry payload.
    'leg' allows splitting one POS payment into multiple Frappe Payment Entries.
    """
    source = leg if leg else payment
    
    amount = float(source.get("amount") or 0)
    if amount <= 0:
        return {}

    customer_name = (payment.get("customer_name") or "").strip()
    if not customer_name:
        log.warning("Payment %s has no customer_name.", payment.get("id"))
        return {}

    # USE CORRECT KEYS: 'method' (pos db) or 'payment_method' (some dicts)
    method = source.get("method") or source.get("payment_method") or payment.get("method") or "Cash"
    
    currency = (source.get("currency") or "USD").upper()
    rate     = float(source.get("exchange_rate") or 0)
    
    # If rate is missing or 1.0 but it's ZiG, try to fetch current rate from DB
    if (rate <= 1.0 or rate == 0) and currency in ("ZIG", "ZWG", "ZWD"):
        try:
            from models.exchange_rate import get_rate
            fetched = get_rate("USD", currency)
            if fetched:
                rate = fetched
                log.debug("Using fetched exchange rate for %s: %.4f", currency, rate)
            else:
                rate = 1.0
        except Exception as e:
            log.warning("Could not fetch rate for %s: %s", currency, e)
            rate = 1.0
    elif rate <= 0:
        rate = 1.0

    # Resolve amounts for Frappe (handle ZIG/USD conversion)
    if currency in ("ZIG", "ZWG", "ZWD"):
        if rate > 1:
            # If rate is e.g. 30 ZIG per 1 USD
            # paid_amount is in the paid_from currency (USD Debtors)
            paid_amount_for_frappe     = round(amount / rate, 4)
            # received_amount is in the paid_to currency (ZiG Bank)
            received_amount_for_frappe = amount
            target_exch_rate           = rate
        else:
            paid_amount_for_frappe     = amount
            received_amount_for_frappe = amount
            target_exch_rate           = 1.0
    else:
        # Standard USD or other
        paid_amount_for_frappe     = amount
        received_amount_for_frappe = amount
        target_exch_rate           = 1.0

    # Reference
    base_ref = payment.get("reference") or f"PAY-{payment.get('id'):07d}"
    if leg:
        reference_no = f"{base_ref}-{leg.get('id', 'S')}"
    else:
        reference_no = base_ref
        
    reference_date = payment.get("payment_date")
    if hasattr(reference_date, "isoformat"):
        reference_date = reference_date.isoformat()

    remarks = payment.get("remarks") or f"Customer Payment via {method}"
    if leg:
        remarks += f" (Part: {currency} {amount})"

    # Resolve MOP and GL
    from services.payment_entry_sync_service import _resolve_mop
    mop_name, gl_account = _resolve_mop(method, source.get("gl_account"), currency)

    paid_to_currency = currency if currency in ("ZIG", "ZWG", "ZWD") else "USD"

    company = defaults.get("server_company", "").strip()
    paid_from_account = _fetch_receivable_account(
        customer_name, company, api_key, api_secret, host
    )
    if not paid_from_account:
        paid_from_account = defaults.get("server_receivable_account", "").strip() or None

    payload: dict = {
        "doctype":                    "Payment Entry",
        "payment_type":               "Receive",
        "party_type":                 "Customer",
        "party":                      customer_name,
        "party_name":                 customer_name,
        "paid_to":                    gl_account,
        "mode_of_payment":            mop_name,
        "paid_from_account_currency": "USD",
        "paid_to_account_currency":   paid_to_currency,
        "paid_amount":                paid_amount_for_frappe,
        "received_amount":            received_amount_for_frappe,
        "source_exchange_rate":       1.0,
        "target_exchange_rate":       target_exch_rate,
        "reference_no":               reference_no,
        "reference_date":             reference_date,
        "remarks":                    remarks,
        "docstatus":                  1,
    }

    if paid_from_account:
        payload["paid_from"] = paid_from_account
    if company:
        payload["company"] = company
    cost_center = defaults.get("server_cost_center", "").strip()
    if cost_center:
        payload["cost_center"] = cost_center

    return payload


# =============================================================================
# SYNC LOGIC
# =============================================================================

def post_payment_entry_to_frappe(payment_id: int) -> bool:
    """Atomic sync one payment (and its splits) to Frappe."""
    from models.payment import (
        try_lock_customer_payment, 
        unlock_customer_payment, 
        get_payment_by_id, 
        mark_payment_synced,
        mark_payment_sync_failed
    )

    if not try_lock_customer_payment(payment_id):
        return False

    try:
        payment = get_payment_by_id(payment_id)
        if not payment or payment.get("synced"):
            return False

        api_key, api_secret = _get_credentials()
        host     = _get_host()
        defaults = _get_defaults()
        
        splits = payment.get("splits", [])
        refs = []
        
        if splits:
            log.info(f"Syncing split payment {payment_id} ({len(splits)} legs)")
            for leg in splits:
                payload = _build_payment_payload(payment, defaults, api_key, api_secret, host, leg=leg)
                if not payload: continue
                
                name = _push_payload(payload, api_key, api_secret, host)
                if name:
                    refs.append(name)
                else:
                    # If one leg fails, we stop and mark overall failed
                    raise Exception(f"Split leg {leg.get('method')} failed.")
        else:
            log.info(f"Syncing single payment {payment_id}")
            payload = _build_payment_payload(payment, defaults, api_key, api_secret, host)
            if payload:
                name = _push_payload(payload, api_key, api_secret, host)
                if name:
                    refs.append(name)
            else:
                mark_payment_synced(payment_id, "SKIPPED")
                return True

        if refs:
            mark_payment_synced(payment_id, ",".join(refs))
            log.info(f"\u2705 Payment {payment_id} synced: {refs}")
            return True
        return False

    except Exception as e:
        log.error(f"Sync error on {payment_id}: {e}")
        mark_payment_sync_failed(payment_id, str(e))
        return False
    finally:
        unlock_customer_payment(payment_id)

def _push_payload(payload, api_key, api_secret, host):
    url = f"{host}/api/resource/Payment%20Entry"
    body = json.dumps(payload, default=str).encode("utf-8")
    req = urllib.request.Request(
        url=url, data=body, method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"token {api_key}:{api_secret}",
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
            return (data.get("data") or {}).get("name")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        log.error(f"Frappe HTTP {e.code}: {error_body}")
        if e.code == 409 or "already exists" in error_body.lower():
            return "DUPLICATE"
        return None
    except Exception as e:
        log.error(f"Push error: {e}")
        return None


# =============================================================================
# DAEMON
# =============================================================================

def push_unsynced_payments():
    """Sequential, thread-safe sync of all pending payments."""
    # Use non-blocking acquire: if another sweep is already running, just return.
    if not _sync_lock.acquire(blocking=False):
        log.debug("Sync sweep already in progress. Skipping.")
        return

    try:
        from models.payment import get_unsynced_payments
        payments = get_unsynced_payments()
        if not payments:
            return
        
        log.info(f"Processing {len(payments)} unsynced payments sequentially.")
        for p in payments:
            try:
                post_payment_entry_to_frappe(p["id"])
            except Exception as e:
                log.error(f"Error syncing payment {p.get('id')}: {e}")
            
            # Brief pause to be nice to the network/server
            time.sleep(0.5)
            
    except Exception as e:
        log.error(f"Daemon sweep failed: {e}")
    finally:
        _sync_lock.release()

def _sync_loop():
    while True:
        try:
            push_unsynced_payments()
        except Exception as e:
            log.error(f"Loop error: {e}")
        time.sleep(SYNC_INTERVAL)

def start_payment_sync_daemon():
    global _sync_thread
    if _sync_thread and _sync_thread.is_alive(): return _sync_thread
    _sync_thread = threading.Thread(target=_sync_loop, daemon=True, name="PaymentSync")
    _sync_thread.start()
    return _sync_thread