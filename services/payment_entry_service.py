# # # # # # # # =============================================================================
# # # # # # # # services/payment_entry_service.py
# # # # # # # #
# # # # # # # # Manages local payment_entries table and syncs them to Frappe.
# # # # # # # #
# # # # # # # # FLOW:
# # # # # # # #   1. When a sale is saved locally → create_payment_entry() stores it locally
# # # # # # # #      with synced=0
# # # # # # # #   2. When the Sales Invoice is confirmed on Frappe (frappe_ref is set) →
# # # # # # # #      push_unsynced_payment_entries() pushes the Payment Entry to Frappe
# # # # # # # #   3. Frappe returns a PAY-xxxxx ref → stored as frappe_payment_ref, synced=1
# # # # # # # #
# # # # # # # # PAYLOAD SENT TO FRAPPE:
# # # # # # # #   POST /api/resource/Payment Entry
# # # # # # # #   {
# # # # # # # #     "doctype":              "Payment Entry",
# # # # # # # #     "payment_type":         "Receive",
# # # # # # # #     "party_type":           "Customer",
# # # # # # # #     "party":                "Cathy",
# # # # # # # #     "paid_to":              "Cash ZWG - H",
# # # # # # # #     "paid_to_account_currency": "USD",
# # # # # # # #     "paid_amount":          32.45,
# # # # # # # #     "received_amount":      32.45,
# # # # # # # #     "source_exchange_rate": 1.0,
# # # # # # # #     "reference_no":         "ACC-SINV-2026-00034",
# # # # # # # #     "reference_date":       "2026-03-19",
# # # # # # # #     "remarks":              "POS Payment — Cash",
# # # # # # # #     "docstatus":            1,
# # # # # # # #     "references": [{
# # # # # # # #         "reference_doctype": "Sales Invoice",
# # # # # # # #         "reference_name":    "ACC-SINV-2026-00565",
# # # # # # # #         "allocated_amount":  32.45
# # # # # # # #     }]
# # # # # # # #   }
# # # # # # # # =============================================================================

# # # # # # # from __future__ import annotations

# # # # # # # import json
# # # # # # # import logging
# # # # # # # import time
# # # # # # # import threading
# # # # # # # import urllib.request
# # # # # # # import urllib.error
# # # # # # # from datetime import date

# # # # # # # log = logging.getLogger("PaymentEntry")

# # # # # # # SYNC_INTERVAL   = 60      # seconds between auto-sync cycles
# # # # # # # REQUEST_TIMEOUT = 30

# # # # # # # # Exchange rate cache: "FROM::TO::DATE" → float
# # # # # # # _RATE_CACHE: dict[str, float] = {}


# # # # # # # def _get_exchange_rate(from_currency: str, to_currency: str,
# # # # # # #                        transaction_date: str,
# # # # # # #                        api_key: str, api_secret: str, host: str) -> float:
# # # # # # #     """
# # # # # # #     Fetch live exchange rate from Frappe.
# # # # # # #     Returns 1.0 for same currency, 0.0 if fetch fails (Frappe uses its own rate).
# # # # # # #     """
# # # # # # #     if not from_currency or from_currency.upper() == to_currency.upper():
# # # # # # #         return 1.0

# # # # # # #     cache_key = f"{from_currency.upper()}::{to_currency.upper()}::{transaction_date}"
# # # # # # #     if cache_key in _RATE_CACHE:
# # # # # # #         return _RATE_CACHE[cache_key]

# # # # # # #     try:
# # # # # # #         import urllib.parse
# # # # # # #         url = (
# # # # # # #             f"{host}/api/method/erpnext.setup.utils.get_exchange_rate"
# # # # # # #             f"?from_currency={urllib.parse.quote(from_currency)}"
# # # # # # #             f"&to_currency={urllib.parse.quote(to_currency)}"
# # # # # # #             f"&transaction_date={transaction_date}"
# # # # # # #         )
# # # # # # #         req = urllib.request.Request(url)
# # # # # # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # # # # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # # # # # #             data = json.loads(r.read().decode())
# # # # # # #             rate = float(data.get("message") or data.get("result") or 0)
# # # # # # #             if rate > 0:
# # # # # # #                 _RATE_CACHE[cache_key] = rate
# # # # # # #                 log.debug("Rate %s→%s on %s: %.6f", from_currency, to_currency, transaction_date, rate)
# # # # # # #                 return rate
# # # # # # #     except Exception as e:
# # # # # # #         log.debug("Rate fetch failed (%s→%s): %s", from_currency, to_currency, e)

# # # # # # #     return 0.0

# # # # # # # _sync_lock:   threading.Lock          = threading.Lock()
# # # # # # # _sync_thread: threading.Thread | None = None

# # # # # # # # Method → Frappe Mode of Payment name
# # # # # # # _METHOD_MAP = {
# # # # # # #     "CASH":     "Cash",
# # # # # # #     "CARD":     "Credit Card",
# # # # # # #     "C / CARD": "Credit Card",
# # # # # # #     "EFTPOS":   "Credit Card",
# # # # # # #     "CHECK":    "Cheque",
# # # # # # #     "CHEQUE":   "Cheque",
# # # # # # #     "MOBILE":   "Mobile Money",
# # # # # # #     "CREDIT":   "Credit",
# # # # # # #     "TRANSFER": "Bank Transfer",
# # # # # # # }


# # # # # # # # =============================================================================
# # # # # # # # CREDENTIALS / HOST / DEFAULTS
# # # # # # # # =============================================================================

# # # # # # # def _get_credentials() -> tuple[str, str]:
# # # # # # #     try:
# # # # # # #         from services.auth_service import get_session
# # # # # # #         s = get_session()
# # # # # # #         if s.get("api_key") and s.get("api_secret"):
# # # # # # #             return s["api_key"], s["api_secret"]
# # # # # # #     except Exception:
# # # # # # #         pass
# # # # # # #     try:
# # # # # # #         from database.db import get_connection
# # # # # # #         conn = get_connection(); cur = conn.cursor()
# # # # # # #         cur.execute("SELECT api_key, api_secret FROM company_defaults WHERE id = 1")
# # # # # # #         row = cur.fetchone(); conn.close()
# # # # # # #         if row and row[0] and row[1]:
# # # # # # #             return row[0], row[1]
# # # # # # #     except Exception:
# # # # # # #         pass
# # # # # # #     import os
# # # # # # #     return os.environ.get("HAVANO_API_KEY", ""), os.environ.get("HAVANO_API_SECRET", "")


# # # # # # # def _get_host() -> str:
# # # # # # #     try:
# # # # # # #         from models.company_defaults import get_defaults
# # # # # # #         host = (get_defaults() or {}).get("server_api_host", "").strip().rstrip("/")
# # # # # # #         if host:
# # # # # # #             return host
# # # # # # #     except Exception:
# # # # # # #         pass
# # # # # # #     return "https://apk.havano.cloud"


# # # # # # # def _get_defaults() -> dict:
# # # # # # #     try:
# # # # # # #         from models.company_defaults import get_defaults
# # # # # # #         return get_defaults() or {}
# # # # # # #     except Exception:
# # # # # # #         return {}


# # # # # # # # =============================================================================
# # # # # # # # GL ACCOUNT RESOLVER  (which account to credit for each payment method)
# # # # # # # # =============================================================================

# # # # # # # _ACCOUNT_CACHE: dict[str, str] = {}


# # # # # # # def _resolve_paid_to_account(mop_name: str, company: str, currency: str,
# # # # # # #                               api_key: str, api_secret: str, host: str) -> str:
# # # # # # #     """
# # # # # # #     Looks up the GL account for a Mode of Payment from Frappe.
# # # # # # #     Tries to match by currency if multiple accounts exist for the company.
# # # # # # #     Falls back to server_pos_account in company_defaults.
# # # # # # #     """
# # # # # # #     cache_key = f"{mop_name}::{company}::{currency}"
# # # # # # #     if cache_key in _ACCOUNT_CACHE:
# # # # # # #         return _ACCOUNT_CACHE[cache_key]

# # # # # # #     try:
# # # # # # #         import urllib.parse
# # # # # # #         url = (f"{host}/api/resource/Mode%20of%20Payment/"
# # # # # # #                f"{urllib.parse.quote(mop_name)}?fields=[\"accounts\"]")
# # # # # # #         req = urllib.request.Request(url)
# # # # # # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # # # # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # # # # # #             data     = json.loads(r.read().decode())
# # # # # # #             accounts = (data.get("data") or {}).get("accounts", [])

# # # # # # #         company_accts = [a for a in accounts
# # # # # # #                          if not company or a.get("company") == company]

# # # # # # #         # Prefer account whose name contains the currency code
# # # # # # #         matched = ""
# # # # # # #         if currency:
# # # # # # #             for a in company_accts:
# # # # # # #                 if currency.upper() in (a.get("default_account") or "").upper():
# # # # # # #                     matched = a["default_account"]; break

# # # # # # #         if not matched and company_accts:
# # # # # # #             matched = company_accts[0].get("default_account", "")

# # # # # # #         if matched:
# # # # # # #             _ACCOUNT_CACHE[cache_key] = matched
# # # # # # #             return matched

# # # # # # #     except Exception as e:
# # # # # # #         log.debug("MOP account lookup failed for '%s': %s", mop_name, e)

# # # # # # #     # Fallback
# # # # # # #     fallback = _get_defaults().get("server_pos_account", "").strip()
# # # # # # #     if fallback:
# # # # # # #         _ACCOUNT_CACHE[cache_key] = fallback
# # # # # # #         return fallback

# # # # # # #     log.warning("No GL account for MOP '%s' currency=%s — Payment Entry may fail.",
# # # # # # #                 mop_name, currency)
# # # # # # #     return ""


# # # # # # # # =============================================================================
# # # # # # # # LOCAL DB  — create / read / update payment_entries
# # # # # # # # =============================================================================

# # # # # # # def create_payment_entry(sale: dict, override_rate: float = None,
# # # # # # #                          override_account: str = None) -> int | None:
# # # # # # #     """
# # # # # # #     Called immediately after a sale is saved locally.
# # # # # # #     Stores a payment_entry row with synced=0.
# # # # # # #     Returns the new payment_entry id, or None on error.

# # # # # # #     Will only create the entry once per sale (idempotent).
# # # # # # #     """
# # # # # # #     from database.db import get_connection
# # # # # # #     conn = get_connection(); cur = conn.cursor()

# # # # # # #     # Idempotency: don't create twice for the same sale
# # # # # # #     cur.execute("SELECT id FROM payment_entries WHERE sale_id = ?", (sale["id"],))
# # # # # # #     if cur.fetchone():
# # # # # # #         conn.close()
# # # # # # #         return None

# # # # # # #     customer   = (sale.get("customer_name") or "default").strip()
# # # # # # #     currency   = (sale.get("currency")      or "USD").strip().upper()
# # # # # # #     amount     = float(sale.get("total")    or 0)
# # # # # # #     inv_no     = sale.get("invoice_no", "")
# # # # # # #     inv_date   = sale.get("invoice_date") or date.today().isoformat()
# # # # # # #     method     = str(sale.get("method", "CASH")).upper().strip()
# # # # # # #     mop        = _METHOD_MAP.get(method, "Cash")

# # # # # # #     # Use override rate (from split) or fetch from Frappe
# # # # # # #     if override_rate is not None:
# # # # # # #         exch_rate = override_rate
# # # # # # #     else:
# # # # # # #         try:
# # # # # # #             api_key, api_secret = _get_credentials()
# # # # # # #             host = _get_host()
# # # # # # #             defaults = _get_defaults()
# # # # # # #             company_currency = defaults.get("server_company_currency", "USD").strip().upper() or "USD"
# # # # # # #             exch_rate = _get_exchange_rate(
# # # # # # #                 currency, company_currency, inv_date, api_key, api_secret, host
# # # # # # #             ) if currency != company_currency else 1.0
# # # # # # #         except Exception:
# # # # # # #             exch_rate = 1.0

# # # # # # #     cur.execute("""
# # # # # # #         INSERT INTO payment_entries (
# # # # # # #             sale_id, sale_invoice_no, frappe_invoice_ref,
# # # # # # #             party, party_name,
# # # # # # #             paid_amount, received_amount, source_exchange_rate,
# # # # # # #             paid_to_account_currency, currency,
# # # # # # #             mode_of_payment,
# # # # # # #             reference_no, reference_date,
# # # # # # #             remarks, synced
# # # # # # #         ) OUTPUT INSERTED.id
# # # # # # #         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # # # # # #     """, (
# # # # # # #         sale["id"], inv_no,
# # # # # # #         sale.get("frappe_ref") or None,
# # # # # # #         customer, customer,
# # # # # # #         amount, amount, exch_rate or 1.0,
# # # # # # #         currency, currency,
# # # # # # #         mop,
# # # # # # #         inv_no, inv_date,
# # # # # # #         f"POS Payment — {mop}",
# # # # # # #     ))
# # # # # # #     new_id = int(cur.fetchone()[0])
# # # # # # #     conn.commit(); conn.close()
# # # # # # #     log.debug("Payment entry %d created locally for sale %s", new_id, inv_no)
# # # # # # #     return new_id


# # # # # # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # # # # # #     """
# # # # # # #     Called when cashier uses Split payment.
# # # # # # #     Creates one payment_entry row per currency in splits list.
# # # # # # #     splits = [{"mode": "CASH", "currency": "USD", "amount": 5.0,
# # # # # # #                "rate": 1.0, "base_amount": 5.0, "account": "Cash - AT"}, ...]
# # # # # # #     Returns list of new payment_entry ids.
# # # # # # #     """
# # # # # # #     ids = []
# # # # # # #     for split in splits:
# # # # # # #         if not split.get("amount") or float(split["amount"]) <= 0:
# # # # # # #             continue
# # # # # # #         # Build a sale-like dict with the split's currency and amount
# # # # # # #         split_sale = dict(sale)
# # # # # # #         split_sale["currency"]      = split.get("currency", "USD")
# # # # # # #         split_sale["total"]         = float(split.get("amount", 0))
# # # # # # #         split_sale["method"]        = split.get("mode", "CASH")
# # # # # # #         # Override exchange rate from split data
# # # # # # #         new_id = create_payment_entry(
# # # # # # #             split_sale,
# # # # # # #             override_rate=float(split.get("rate", 1.0)),
# # # # # # #             override_account=split.get("account", ""),
# # # # # # #         )
# # # # # # #         if new_id:
# # # # # # #             ids.append(new_id)
# # # # # # #     return ids


# # # # # # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # # # # # #     """
# # # # # # #     Creates one payment_entry per currency from a split payment.
# # # # # # #     Groups splits by currency, sums amounts, creates one entry each.
# # # # # # #     Returns list of created payment_entry ids.
# # # # # # #     """
# # # # # # #     from datetime import date as _date

# # # # # # #     # Group by currency
# # # # # # #     by_currency: dict[str, dict] = {}
# # # # # # #     for s in splits:
# # # # # # #         curr = s.get("account_currency", "USD").upper()
# # # # # # #         if curr not in by_currency:
# # # # # # #             by_currency[curr] = {
# # # # # # #                 "currency":      curr,
# # # # # # #                 "paid_amount":   0.0,
# # # # # # #                 "base_value":    0.0,
# # # # # # #                 "rate":          s.get("rate", 1.0),
# # # # # # #                 "account_name":  s.get("account_name", ""),
# # # # # # #                 "mode":          s.get("mode", "Cash"),
# # # # # # #             }
# # # # # # #         by_currency[curr]["paid_amount"] += s.get("amount_paid", 0.0)
# # # # # # #         by_currency[curr]["base_value"]  += s.get("base_value",  0.0)

# # # # # # #     ids = []
# # # # # # #     inv_no   = sale.get("invoice_no", "")
# # # # # # #     inv_date = sale.get("invoice_date") or _date.today().isoformat()
# # # # # # #     customer = (sale.get("customer_name") or "default").strip()

# # # # # # #     from database.db import get_connection
# # # # # # #     conn = get_connection(); cur = conn.cursor()

# # # # # # #     for curr, grp in by_currency.items():
# # # # # # #         # Idempotency: skip if already exists for this sale+currency
# # # # # # #         cur.execute(
# # # # # # #             "SELECT id FROM payment_entries WHERE sale_id=? AND currency=?",
# # # # # # #             (sale["id"], curr)
# # # # # # #         )
# # # # # # #         if cur.fetchone():
# # # # # # #             continue

# # # # # # #         mop = _METHOD_MAP.get(grp["mode"].upper(), "Cash")

# # # # # # #         cur.execute("""
# # # # # # #             INSERT INTO payment_entries (
# # # # # # #                 sale_id, sale_invoice_no, frappe_invoice_ref,
# # # # # # #                 party, party_name,
# # # # # # #                 paid_amount, received_amount, source_exchange_rate,
# # # # # # #                 paid_to_account_currency, currency,
# # # # # # #                 paid_to,
# # # # # # #                 mode_of_payment,
# # # # # # #                 reference_no, reference_date,
# # # # # # #                 remarks, synced
# # # # # # #             ) OUTPUT INSERTED.id
# # # # # # #             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # # # # # #         """, (
# # # # # # #             sale["id"], inv_no,
# # # # # # #             sale.get("frappe_ref") or None,
# # # # # # #             customer, customer,
# # # # # # #             grp["paid_amount"],
# # # # # # #             grp["base_value"],
# # # # # # #             float(grp["rate"] or 1.0),
# # # # # # #             curr, curr,
# # # # # # #             grp["account_name"],
# # # # # # #             mop,
# # # # # # #             inv_no, inv_date,
# # # # # # #             f"POS Split Payment — {mop} ({curr})",
# # # # # # #         ))
# # # # # # #         new_id = int(cur.fetchone()[0])
# # # # # # #         ids.append(new_id)
# # # # # # #         log.debug("Split payment entry %d created: %s %.2f %s",
# # # # # # #                   new_id, curr, grp["paid_amount"], inv_no)

# # # # # # #     conn.commit(); conn.close()
# # # # # # #     return ids


# # # # # # # def get_unsynced_payment_entries() -> list[dict]:
# # # # # # #     """Returns payment entries that are ready to push (synced=0)."""
# # # # # # #     from database.db import get_connection, fetchall_dicts
# # # # # # #     conn = get_connection(); cur = conn.cursor()
# # # # # # #     cur.execute("""
# # # # # # #         SELECT pe.*, s.frappe_ref AS sale_frappe_ref
# # # # # # #         FROM payment_entries pe
# # # # # # #         LEFT JOIN sales s ON s.id = pe.sale_id
# # # # # # #         WHERE pe.synced = 0
# # # # # # #           AND (pe.frappe_invoice_ref IS NOT NULL
# # # # # # #                OR s.frappe_ref IS NOT NULL)
# # # # # # #         ORDER BY pe.id
# # # # # # #     """)
# # # # # # #     rows = fetchall_dicts(cur); conn.close()
# # # # # # #     return rows


# # # # # # # def mark_payment_synced(pe_id: int, frappe_payment_ref: str = "") -> None:
# # # # # # #     from database.db import get_connection
# # # # # # #     conn = get_connection(); cur = conn.cursor()
# # # # # # #     cur.execute(
# # # # # # #         "UPDATE payment_entries SET synced=1, frappe_payment_ref=? WHERE id=?",
# # # # # # #         (frappe_payment_ref or None, pe_id)
# # # # # # #     )
# # # # # # #     # Also update the sales row
# # # # # # #     cur.execute("""
# # # # # # #         UPDATE sales SET payment_entry_ref=?, payment_synced=1
# # # # # # #         WHERE id = (SELECT sale_id FROM payment_entries WHERE id=?)
# # # # # # #     """, (frappe_payment_ref or None, pe_id))
# # # # # # #     conn.commit(); conn.close()


# # # # # # # def refresh_frappe_refs() -> int:
# # # # # # #     """
# # # # # # #     For payment entries that have no frappe_invoice_ref yet, copy it from
# # # # # # #     the parent sale's frappe_ref. Call this before pushing payments.
# # # # # # #     Returns count updated.
# # # # # # #     """
# # # # # # #     from database.db import get_connection
# # # # # # #     conn = get_connection(); cur = conn.cursor()
# # # # # # #     cur.execute("""
# # # # # # #         UPDATE pe
# # # # # # #         SET pe.frappe_invoice_ref = s.frappe_ref
# # # # # # #         FROM payment_entries pe
# # # # # # #         JOIN sales s ON s.id = pe.sale_id
# # # # # # #         WHERE pe.synced = 0
# # # # # # #           AND (pe.frappe_invoice_ref IS NULL OR pe.frappe_invoice_ref = '')
# # # # # # #           AND s.frappe_ref IS NOT NULL AND s.frappe_ref != ''
# # # # # # #     """)
# # # # # # #     count = cur.rowcount
# # # # # # #     conn.commit(); conn.close()
# # # # # # #     return count


# # # # # # # # =============================================================================
# # # # # # # # BUILD FRAPPE PAYLOAD
# # # # # # # # =============================================================================

# # # # # # # def _build_payload(pe: dict, defaults: dict,
# # # # # # #                    api_key: str, api_secret: str, host: str) -> dict:
# # # # # # #     company  = defaults.get("server_company", "")
# # # # # # #     currency = (pe.get("currency") or pe.get("paid_to_account_currency") or "USD").upper()
# # # # # # #     mop      = pe.get("mode_of_payment") or "Cash"
# # # # # # #     amount   = float(pe.get("paid_amount") or 0)
# # # # # # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()

# # # # # # #     paid_to = _resolve_paid_to_account(mop, company, currency, api_key, api_secret, host)

# # # # # # #     payload = {
# # # # # # #         "doctype":                  "Payment Entry",
# # # # # # #         "payment_type":             "Receive",
# # # # # # #         "party_type":               "Customer",
# # # # # # #         "party":                    pe.get("party") or "default",
# # # # # # #         "party_name":               pe.get("party_name") or "default",
# # # # # # #         "paid_to_account_currency": currency,
# # # # # # #         "paid_amount":              amount,
# # # # # # #         "received_amount":          amount,
# # # # # # #         "source_exchange_rate":     float(pe.get("source_exchange_rate") or 1.0),
# # # # # # #         "reference_no":             pe.get("reference_no") or pe.get("sale_invoice_no", ""),
# # # # # # #         "reference_date":           pe.get("reference_date") or date.today().isoformat(),
# # # # # # #         "remarks":                  pe.get("remarks") or f"POS Payment — {mop}",
# # # # # # #         "mode_of_payment":          mop,
# # # # # # #         "docstatus":                1,
# # # # # # #     }

# # # # # # #     if paid_to:
# # # # # # #         payload["paid_to"] = paid_to
# # # # # # #     if company:
# # # # # # #         payload["company"] = company

# # # # # # #     # Link to the Sales Invoice on Frappe
# # # # # # #     if frappe_inv:
# # # # # # #         payload["references"] = [{
# # # # # # #             "reference_doctype": "Sales Invoice",
# # # # # # #             "reference_name":    frappe_inv,
# # # # # # #             "allocated_amount":  amount,
# # # # # # #         }]

# # # # # # #     return payload


# # # # # # # # =============================================================================
# # # # # # # # PUSH ONE PAYMENT ENTRY
# # # # # # # # =============================================================================

# # # # # # # def _push_payment_entry(pe: dict, api_key: str, api_secret: str,
# # # # # # #                         defaults: dict, host: str) -> str | None:
# # # # # # #     """
# # # # # # #     Posts one payment entry to Frappe.
# # # # # # #     Returns Frappe's PAY-xxxxx name on success, None on failure.
# # # # # # #     """
# # # # # # #     pe_id  = pe["id"]
# # # # # # #     inv_no = pe.get("sale_invoice_no", str(pe_id))

# # # # # # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()
# # # # # # #     if not frappe_inv:
# # # # # # #         log.warning("Payment %d — Sales Invoice not yet on Frappe, skipping.", pe_id)
# # # # # # #         return None

# # # # # # #     payload = _build_payload(pe, defaults, api_key, api_secret, host)

# # # # # # #     url = f"{host}/api/resource/Payment%20Entry"
# # # # # # #     req = urllib.request.Request(
# # # # # # #         url=url,
# # # # # # #         data=json.dumps(payload).encode("utf-8"),
# # # # # # #         method="POST",
# # # # # # #         headers={
# # # # # # #             "Content-Type":  "application/json",
# # # # # # #             "Accept":        "application/json",
# # # # # # #             "Authorization": f"token {api_key}:{api_secret}",
# # # # # # #         },
# # # # # # #     )

# # # # # # #     try:
# # # # # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
# # # # # # #             data = json.loads(resp.read().decode())
# # # # # # #             name = (data.get("data") or {}).get("name", "")
# # # # # # #             log.info("✅ Payment Entry %d → Frappe %s  [%s  %s %.2f]",
# # # # # # #                      pe_id, name, inv_no,
# # # # # # #                      pe.get("currency", ""), float(pe.get("paid_amount", 0)))
# # # # # # #             return name or "SYNCED"

# # # # # # #     except urllib.error.HTTPError as e:
# # # # # # #         try:
# # # # # # #             err = json.loads(e.read().decode())
# # # # # # #             msg = (err.get("exception") or err.get("message") or
# # # # # # #                    str(err.get("_server_messages", "")) or f"HTTP {e.code}")
# # # # # # #         except Exception:
# # # # # # #             msg = f"HTTP {e.code}"

# # # # # # #         if e.code == 409:
# # # # # # #             log.info("Payment %d already on Frappe (409) — marking synced.", pe_id)
# # # # # # #             return "DUPLICATE"

# # # # # # #         log.error("❌ Payment Entry %d  HTTP %s: %s", pe_id, e.code, msg)
# # # # # # #         return None

# # # # # # #     except urllib.error.URLError as e:
# # # # # # #         log.warning("Network error pushing payment %d: %s", pe_id, e.reason)
# # # # # # #         return None

# # # # # # #     except Exception as e:
# # # # # # #         log.error("Unexpected error pushing payment %d: %s", pe_id, e)
# # # # # # #         return None


# # # # # # # # =============================================================================
# # # # # # # # PUBLIC — push all unsynced payment entries
# # # # # # # # =============================================================================

# # # # # # # def push_unsynced_payment_entries() -> dict:
# # # # # # #     """
# # # # # # #     1. Refresh frappe_invoice_ref from parent sales that were confirmed.
# # # # # # #     2. Push each unsynced payment entry to Frappe.
# # # # # # #     3. Mark synced with the returned PAY-xxxxx ref.
# # # # # # #     """
# # # # # # #     result = {"pushed": 0, "failed": 0, "skipped": 0, "total": 0}

# # # # # # #     api_key, api_secret = _get_credentials()
# # # # # # #     if not api_key or not api_secret:
# # # # # # #         log.warning("No credentials — skipping payment entry sync.")
# # # # # # #         return result

# # # # # # #     host     = _get_host()
# # # # # # #     defaults = _get_defaults()

# # # # # # #     # First: pull frappe_refs from confirmed invoices into pending payment entries
# # # # # # #     updated = refresh_frappe_refs()
# # # # # # #     if updated:
# # # # # # #         log.info("Refreshed frappe_invoice_ref on %d payment entry(ies).", updated)

# # # # # # #     entries = get_unsynced_payment_entries()
# # # # # # #     result["total"] = len(entries)

# # # # # # #     if not entries:
# # # # # # #         log.debug("No unsynced payment entries.")
# # # # # # #         return result

# # # # # # #     log.info("Pushing %d payment entry(ies) to Frappe…", len(entries))

# # # # # # #     for pe in entries:
# # # # # # #         frappe_name = _push_payment_entry(pe, api_key, api_secret, defaults, host)
# # # # # # #         if frappe_name:
# # # # # # #             mark_payment_synced(pe["id"], frappe_name)
# # # # # # #             result["pushed"] += 1
# # # # # # #         elif frappe_name is None:
# # # # # # #             # None = permanent skip (no frappe_inv yet), not a real failure
# # # # # # #             result["skipped"] += 1
# # # # # # #         else:
# # # # # # #             result["failed"] += 1

# # # # # # #         time.sleep(3)   # rate limit — 20/min max

# # # # # # #     log.info("Payment sync done — ✅ %d pushed  ❌ %d failed  ⏭ %d skipped",
# # # # # # #              result["pushed"], result["failed"], result["skipped"])
# # # # # # #     return result


# # # # # # # # =============================================================================
# # # # # # # # BACKGROUND DAEMON THREAD
# # # # # # # # =============================================================================

# # # # # # # def _sync_loop():
# # # # # # #     log.info("Payment entry sync daemon started (interval=%ds).", SYNC_INTERVAL)
# # # # # # #     while True:
# # # # # # #         if _sync_lock.acquire(blocking=False):
# # # # # # #             try:
# # # # # # #                 push_unsynced_payment_entries()
# # # # # # #             except Exception as e:
# # # # # # #                 log.error("Payment sync cycle error: %s", e)
# # # # # # #             finally:
# # # # # # #                 _sync_lock.release()
# # # # # # #         else:
# # # # # # #             log.debug("Previous payment sync still running — skipping.")
# # # # # # #         time.sleep(SYNC_INTERVAL)


# # # # # # # def start_payment_sync_daemon() -> threading.Thread:
# # # # # # #     """Non-blocking — safe to call from MainWindow.__init__."""
# # # # # # #     global _sync_thread
# # # # # # #     if _sync_thread and _sync_thread.is_alive():
# # # # # # #         return _sync_thread
# # # # # # #     t = threading.Thread(target=_sync_loop, daemon=True, name="PaymentSyncDaemon")
# # # # # # #     t.start()
# # # # # # #     _sync_thread = t
# # # # # # #     log.info("Payment entry sync daemon started.")
# # # # # # #     return t


# # # # # # # # =============================================================================
# # # # # # # # DEBUG
# # # # # # # # =============================================================================

# # # # # # # if __name__ == "__main__":
# # # # # # #     logging.basicConfig(level=logging.INFO,
# # # # # # #                         format="%(asctime)s [%(levelname)s] %(message)s")
# # # # # # #     print("Running one payment entry sync cycle...")
# # # # # # #     r = push_unsynced_payment_entries()
# # # # # # #     print(f"\nResult: {r['pushed']} pushed, {r['failed']} failed, "
# # # # # # #           f"{r['skipped']} skipped (of {r['total']} total)")
# # # # # # # =============================================================================
# # # # # # # services/payment_entry_service.py
# # # # # # #
# # # # # # # Manages local payment_entries table and syncs them to Frappe.
# # # # # # #
# # # # # # # FLOW:
# # # # # # #   1. When a sale is saved locally → create_payment_entry() stores it locally
# # # # # # #      with synced=0
# # # # # # #   2. When the Sales Invoice is confirmed on Frappe (frappe_ref is set) →
# # # # # # #      push_unsynced_payment_entries() pushes the Payment Entry to Frappe
# # # # # # #   3. Frappe returns a PAY-xxxxx ref → stored as frappe_payment_ref, synced=1
# # # # # # #
# # # # # # # PAYLOAD SENT TO FRAPPE:
# # # # # # #   POST /api/resource/Payment Entry
# # # # # # #   {
# # # # # # #     "doctype":              "Payment Entry",
# # # # # # #     "payment_type":         "Receive",
# # # # # # #     "party_type":           "Customer",
# # # # # # #     "party":                "Cathy",
# # # # # # #     "paid_to":              "Cash ZWG - H",
# # # # # # #     "paid_to_account_currency": "USD",
# # # # # # #     "paid_amount":          32.45,
# # # # # # #     "received_amount":      32.45,
# # # # # # #     "source_exchange_rate": 1.0,
# # # # # # #     "reference_no":         "ACC-SINV-2026-00034",
# # # # # # #     "reference_date":       "2026-03-19",
# # # # # # #     "remarks":              "POS Payment — Cash",
# # # # # # #     "docstatus":            1,
# # # # # # #     "references": [{
# # # # # # #         "reference_doctype": "Sales Invoice",
# # # # # # #         "reference_name":    "ACC-SINV-2026-00565",
# # # # # # #         "allocated_amount":  32.45
# # # # # # #     }]
# # # # # # #   }
# # # # # # # =============================================================================

# # # # # # from __future__ import annotations

# # # # # # import json
# # # # # # import logging
# # # # # # import time
# # # # # # import threading
# # # # # # import urllib.request
# # # # # # import urllib.error
# # # # # # from datetime import date

# # # # # # log = logging.getLogger("PaymentEntry")

# # # # # # SYNC_INTERVAL   = 60      # seconds between auto-sync cycles
# # # # # # REQUEST_TIMEOUT = 30

# # # # # # # Exchange rate cache: "FROM::TO::DATE" → float
# # # # # # _RATE_CACHE: dict[str, float] = {}


# # # # # # def _get_exchange_rate(from_currency: str, to_currency: str,
# # # # # #                        transaction_date: str,
# # # # # #                        api_key: str, api_secret: str, host: str) -> float:
# # # # # #     """
# # # # # #     Fetch live exchange rate from Frappe.
# # # # # #     Returns 1.0 for same currency, 0.0 if fetch fails (Frappe uses its own rate).
# # # # # #     """
# # # # # #     if not from_currency or from_currency.upper() == to_currency.upper():
# # # # # #         return 1.0

# # # # # #     cache_key = f"{from_currency.upper()}::{to_currency.upper()}::{transaction_date}"
# # # # # #     if cache_key in _RATE_CACHE:
# # # # # #         return _RATE_CACHE[cache_key]

# # # # # #     try:
# # # # # #         import urllib.parse
# # # # # #         url = (
# # # # # #             f"{host}/api/method/erpnext.setup.utils.get_exchange_rate"
# # # # # #             f"?from_currency={urllib.parse.quote(from_currency)}"
# # # # # #             f"&to_currency={urllib.parse.quote(to_currency)}"
# # # # # #             f"&transaction_date={transaction_date}"
# # # # # #         )
# # # # # #         req = urllib.request.Request(url)
# # # # # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # # # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # # # # #             data = json.loads(r.read().decode())
# # # # # #             rate = float(data.get("message") or data.get("result") or 0)
# # # # # #             if rate > 0:
# # # # # #                 _RATE_CACHE[cache_key] = rate
# # # # # #                 log.debug("Rate %s→%s on %s: %.6f", from_currency, to_currency, transaction_date, rate)
# # # # # #                 return rate
# # # # # #     except Exception as e:
# # # # # #         log.debug("Rate fetch failed (%s→%s): %s", from_currency, to_currency, e)

# # # # # #     return 0.0

# # # # # # _sync_lock:   threading.Lock          = threading.Lock()
# # # # # # _sync_thread: threading.Thread | None = None

# # # # # # # Method → Frappe Mode of Payment name
# # # # # # _METHOD_MAP = {
# # # # # #     "CASH":     "Cash",
# # # # # #     "CARD":     "Credit Card",
# # # # # #     "C / CARD": "Credit Card",
# # # # # #     "EFTPOS":   "Credit Card",
# # # # # #     "CHECK":    "Cheque",
# # # # # #     "CHEQUE":   "Cheque",
# # # # # #     "MOBILE":   "Mobile Money",
# # # # # #     "CREDIT":   "Credit",
# # # # # #     "TRANSFER": "Bank Transfer",
# # # # # # }


# # # # # # # =============================================================================
# # # # # # # CREDENTIALS / HOST / DEFAULTS
# # # # # # # =============================================================================

# # # # # # def _get_credentials() -> tuple[str, str]:
# # # # # #     try:
# # # # # #         from services.auth_service import get_session
# # # # # #         s = get_session()
# # # # # #         if s.get("api_key") and s.get("api_secret"):
# # # # # #             return s["api_key"], s["api_secret"]
# # # # # #     except Exception:
# # # # # #         pass
# # # # # #     try:
# # # # # #         from database.db import get_connection
# # # # # #         conn = get_connection(); cur = conn.cursor()
# # # # # #         cur.execute("SELECT api_key, api_secret FROM company_defaults WHERE id = 1")
# # # # # #         row = cur.fetchone(); conn.close()
# # # # # #         if row and row[0] and row[1]:
# # # # # #             return row[0], row[1]
# # # # # #     except Exception:
# # # # # #         pass
# # # # # #     import os
# # # # # #     return os.environ.get("HAVANO_API_KEY", ""), os.environ.get("HAVANO_API_SECRET", "")


# # # # # # def _get_host() -> str:
# # # # # #     try:
# # # # # #         from models.company_defaults import get_defaults
# # # # # #         host = (get_defaults() or {}).get("server_api_host", "").strip().rstrip("/")
# # # # # #         if host:
# # # # # #             return host
# # # # # #     except Exception:
# # # # # #         pass
# # # # # #     return "https://apk.havano.cloud"


# # # # # # def _get_defaults() -> dict:
# # # # # #     try:
# # # # # #         from models.company_defaults import get_defaults
# # # # # #         return get_defaults() or {}
# # # # # #     except Exception:
# # # # # #         return {}


# # # # # # # =============================================================================
# # # # # # # GL ACCOUNT RESOLVER  (which account to credit for each payment method)
# # # # # # # =============================================================================

# # # # # # _ACCOUNT_CACHE: dict[str, str] = {}


# # # # # # def _resolve_paid_to_account(mop_name: str, company: str, currency: str,
# # # # # #                               api_key: str, api_secret: str, host: str) -> str:
# # # # # #     """
# # # # # #     Looks up the GL account for a Mode of Payment from Frappe.
# # # # # #     Tries to match by currency if multiple accounts exist for the company.
# # # # # #     Falls back to server_pos_account in company_defaults.
# # # # # #     """
# # # # # #     cache_key = f"{mop_name}::{company}::{currency}"
# # # # # #     if cache_key in _ACCOUNT_CACHE:
# # # # # #         return _ACCOUNT_CACHE[cache_key]

# # # # # #     try:
# # # # # #         import urllib.parse
# # # # # #         url = (f"{host}/api/resource/Mode%20of%20Payment/"
# # # # # #                f"{urllib.parse.quote(mop_name)}?fields=[\"accounts\"]")
# # # # # #         req = urllib.request.Request(url)
# # # # # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # # # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # # # # #             data     = json.loads(r.read().decode())
# # # # # #             accounts = (data.get("data") or {}).get("accounts", [])

# # # # # #         company_accts = [a for a in accounts
# # # # # #                          if not company or a.get("company") == company]

# # # # # #         # Prefer account whose name contains the currency code
# # # # # #         matched = ""
# # # # # #         if currency:
# # # # # #             for a in company_accts:
# # # # # #                 if currency.upper() in (a.get("default_account") or "").upper():
# # # # # #                     matched = a["default_account"]; break

# # # # # #         if not matched and company_accts:
# # # # # #             matched = company_accts[0].get("default_account", "")

# # # # # #         if matched:
# # # # # #             _ACCOUNT_CACHE[cache_key] = matched
# # # # # #             return matched

# # # # # #     except Exception as e:
# # # # # #         log.debug("MOP account lookup failed for '%s': %s", mop_name, e)

# # # # # #     # Fallback
# # # # # #     fallback = _get_defaults().get("server_pos_account", "").strip()
# # # # # #     if fallback:
# # # # # #         _ACCOUNT_CACHE[cache_key] = fallback
# # # # # #         return fallback

# # # # # #     log.warning("No GL account for MOP '%s' currency=%s — Payment Entry may fail.",
# # # # # #                 mop_name, currency)
# # # # # #     return ""


# # # # # # # =============================================================================
# # # # # # # LOCAL DB  — create / read / update payment_entries
# # # # # # # =============================================================================

# # # # # # def create_payment_entry(sale: dict, override_rate: float = None,
# # # # # #                          override_account: str = None) -> int | None:
# # # # # #     """
# # # # # #     Called immediately after a sale is saved locally.
# # # # # #     Stores a payment_entry row with synced=0.
# # # # # #     Returns the new payment_entry id, or None on error.

# # # # # #     Will only create the entry once per sale (idempotent).
# # # # # #     """
# # # # # #     from database.db import get_connection
# # # # # #     conn = get_connection(); cur = conn.cursor()

# # # # # #     # Idempotency: don't create twice for the same sale
# # # # # #     cur.execute("SELECT id FROM payment_entries WHERE sale_id = ?", (sale["id"],))
# # # # # #     if cur.fetchone():
# # # # # #         conn.close()
# # # # # #         return None

# # # # # #     customer   = (sale.get("customer_name") or "default").strip()
# # # # # #     currency   = (sale.get("currency")      or "USD").strip().upper()
# # # # # #     amount     = float(sale.get("total")    or 0)
# # # # # #     inv_no     = sale.get("invoice_no", "")
# # # # # #     inv_date   = sale.get("invoice_date") or date.today().isoformat()
# # # # # #     method     = str(sale.get("method", "CASH")).upper().strip()
# # # # # #     mop        = _METHOD_MAP.get(method, "Cash")

# # # # # #     # Use override rate (from split) or fetch from Frappe
# # # # # #     if override_rate is not None:
# # # # # #         exch_rate = override_rate
# # # # # #     else:
# # # # # #         try:
# # # # # #             api_key, api_secret = _get_credentials()
# # # # # #             host = _get_host()
# # # # # #             defaults = _get_defaults()
# # # # # #             company_currency = defaults.get("server_company_currency", "USD").strip().upper() or "USD"
# # # # # #             exch_rate = _get_exchange_rate(
# # # # # #                 currency, company_currency, inv_date, api_key, api_secret, host
# # # # # #             ) if currency != company_currency else 1.0
# # # # # #         except Exception:
# # # # # #             exch_rate = 1.0

# # # # # #     cur.execute("""
# # # # # #         INSERT INTO payment_entries (
# # # # # #             sale_id, sale_invoice_no, frappe_invoice_ref,
# # # # # #             party, party_name,
# # # # # #             paid_amount, received_amount, source_exchange_rate,
# # # # # #             paid_to_account_currency, currency,
# # # # # #             mode_of_payment,
# # # # # #             reference_no, reference_date,
# # # # # #             remarks, synced
# # # # # #         ) OUTPUT INSERTED.id
# # # # # #         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # # # # #     """, (
# # # # # #         sale["id"], inv_no,
# # # # # #         sale.get("frappe_ref") or None,
# # # # # #         customer, customer,
# # # # # #         amount, amount, exch_rate or 1.0,
# # # # # #         currency, currency,
# # # # # #         mop,
# # # # # #         inv_no, inv_date,
# # # # # #         f"POS Payment — {mop}",
# # # # # #     ))
# # # # # #     new_id = int(cur.fetchone()[0])
# # # # # #     conn.commit(); conn.close()
# # # # # #     log.debug("Payment entry %d created locally for sale %s", new_id, inv_no)
# # # # # #     return new_id


# # # # # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # # # # #     """
# # # # # #     Called when cashier uses Split payment.
# # # # # #     Creates one payment_entry row per currency in splits list.
# # # # # #     splits = [{"mode": "CASH", "currency": "USD", "amount": 5.0,
# # # # # #                "rate": 1.0, "base_amount": 5.0, "account": "Cash - AT"}, ...]
# # # # # #     Returns list of new payment_entry ids.
# # # # # #     """
# # # # # #     ids = []
# # # # # #     for split in splits:
# # # # # #         if not split.get("amount") or float(split["amount"]) <= 0:
# # # # # #             continue
# # # # # #         # Build a sale-like dict with the split's currency and amount
# # # # # #         split_sale = dict(sale)
# # # # # #         split_sale["currency"]      = split.get("currency", "USD")
# # # # # #         split_sale["total"]         = float(split.get("amount", 0))
# # # # # #         split_sale["method"]        = split.get("mode", "CASH")
# # # # # #         # Override exchange rate from split data
# # # # # #         new_id = create_payment_entry(
# # # # # #             split_sale,
# # # # # #             override_rate=float(split.get("rate", 1.0)),
# # # # # #             override_account=split.get("account", ""),
# # # # # #         )
# # # # # #         if new_id:
# # # # # #             ids.append(new_id)
# # # # # #     return ids


# # # # # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # # # # #     """
# # # # # #     Creates one payment_entry per currency from a split payment.
# # # # # #     Groups splits by currency, sums amounts, creates one entry each.
# # # # # #     Returns list of created payment_entry ids.
# # # # # #     """
# # # # # #     from datetime import date as _date

# # # # # #     # Group by currency
# # # # # #     by_currency: dict[str, dict] = {}
# # # # # #     for s in splits:
# # # # # #         curr = s.get("account_currency", "USD").upper()
# # # # # #         if curr not in by_currency:
# # # # # #             by_currency[curr] = {
# # # # # #                 "currency":      curr,
# # # # # #                 "paid_amount":   0.0,
# # # # # #                 "base_value":    0.0,
# # # # # #                 "rate":          s.get("rate", 1.0),
# # # # # #                 "account_name":  s.get("account_name", ""),
# # # # # #                 "mode":          s.get("mode", "Cash"),
# # # # # #             }
# # # # # #         by_currency[curr]["paid_amount"] += s.get("amount_paid", 0.0)
# # # # # #         by_currency[curr]["base_value"]  += s.get("base_value",  0.0)

# # # # # #     ids = []
# # # # # #     inv_no   = sale.get("invoice_no", "")
# # # # # #     inv_date = sale.get("invoice_date") or _date.today().isoformat()
# # # # # #     customer = (sale.get("customer_name") or "default").strip()

# # # # # #     from database.db import get_connection
# # # # # #     conn = get_connection(); cur = conn.cursor()

# # # # # #     for curr, grp in by_currency.items():
# # # # # #         # Idempotency: skip if already exists for this sale+currency
# # # # # #         cur.execute(
# # # # # #             "SELECT id FROM payment_entries WHERE sale_id=? AND currency=?",
# # # # # #             (sale["id"], curr)
# # # # # #         )
# # # # # #         if cur.fetchone():
# # # # # #             continue

# # # # # #         mop = _METHOD_MAP.get(grp["mode"].upper(), "Cash")

# # # # # #         cur.execute("""
# # # # # #             INSERT INTO payment_entries (
# # # # # #                 sale_id, sale_invoice_no, frappe_invoice_ref,
# # # # # #                 party, party_name,
# # # # # #                 paid_amount, received_amount, source_exchange_rate,
# # # # # #                 paid_to_account_currency, currency,
# # # # # #                 paid_to,
# # # # # #                 mode_of_payment,
# # # # # #                 reference_no, reference_date,
# # # # # #                 remarks, synced
# # # # # #             ) OUTPUT INSERTED.id
# # # # # #             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # # # # #         """, (
# # # # # #             sale["id"], inv_no,
# # # # # #             sale.get("frappe_ref") or None,
# # # # # #             customer, customer,
# # # # # #             grp["paid_amount"],
# # # # # #             grp["base_value"],
# # # # # #             float(grp["rate"] or 1.0),
# # # # # #             curr, curr,
# # # # # #             grp["account_name"],
# # # # # #             mop,
# # # # # #             inv_no, inv_date,
# # # # # #             f"POS Split Payment — {mop} ({curr})",
# # # # # #         ))
# # # # # #         new_id = int(cur.fetchone()[0])
# # # # # #         ids.append(new_id)
# # # # # #         log.debug("Split payment entry %d created: %s %.2f %s",
# # # # # #                   new_id, curr, grp["paid_amount"], inv_no)

# # # # # #     conn.commit(); conn.close()
# # # # # #     return ids


# # # # # # def get_unsynced_payment_entries() -> list[dict]:
# # # # # #     """Returns payment entries that are ready to push (synced=0)."""
# # # # # #     from database.db import get_connection, fetchall_dicts
# # # # # #     conn = get_connection(); cur = conn.cursor()
# # # # # #     cur.execute("""
# # # # # #         SELECT pe.*, s.frappe_ref AS sale_frappe_ref
# # # # # #         FROM payment_entries pe
# # # # # #         LEFT JOIN sales s ON s.id = pe.sale_id
# # # # # #         WHERE pe.synced = 0
# # # # # #           AND (pe.frappe_invoice_ref IS NOT NULL
# # # # # #                OR s.frappe_ref IS NOT NULL)
# # # # # #         ORDER BY pe.id
# # # # # #     """)
# # # # # #     rows = fetchall_dicts(cur); conn.close()
# # # # # #     return rows


# # # # # # def mark_payment_synced(pe_id: int, frappe_payment_ref: str = "") -> None:
# # # # # #     from database.db import get_connection
# # # # # #     conn = get_connection(); cur = conn.cursor()
# # # # # #     cur.execute(
# # # # # #         "UPDATE payment_entries SET synced=1, frappe_payment_ref=? WHERE id=?",
# # # # # #         (frappe_payment_ref or None, pe_id)
# # # # # #     )
# # # # # #     # Also update the sales row
# # # # # #     cur.execute("""
# # # # # #         UPDATE sales SET payment_entry_ref=?, payment_synced=1
# # # # # #         WHERE id = (SELECT sale_id FROM payment_entries WHERE id=?)
# # # # # #     """, (frappe_payment_ref or None, pe_id))
# # # # # #     conn.commit(); conn.close()


# # # # # # def refresh_frappe_refs() -> int:
# # # # # #     """
# # # # # #     For payment entries that have no frappe_invoice_ref yet, copy it from
# # # # # #     the parent sale's frappe_ref. Call this before pushing payments.
# # # # # #     Returns count updated.
# # # # # #     """
# # # # # #     from database.db import get_connection
# # # # # #     conn = get_connection(); cur = conn.cursor()
# # # # # #     cur.execute("""
# # # # # #         UPDATE pe
# # # # # #         SET pe.frappe_invoice_ref = s.frappe_ref
# # # # # #         FROM payment_entries pe
# # # # # #         JOIN sales s ON s.id = pe.sale_id
# # # # # #         WHERE pe.synced = 0
# # # # # #           AND (pe.frappe_invoice_ref IS NULL OR pe.frappe_invoice_ref = '')
# # # # # #           AND s.frappe_ref IS NOT NULL AND s.frappe_ref != ''
# # # # # #     """)
# # # # # #     count = cur.rowcount
# # # # # #     conn.commit(); conn.close()
# # # # # #     return count


# # # # # # # =============================================================================
# # # # # # # BUILD FRAPPE PAYLOAD
# # # # # # # =============================================================================

# # # # # # def _build_payload(pe: dict, defaults: dict,
# # # # # #                    api_key: str, api_secret: str, host: str) -> dict:
# # # # # #     company  = defaults.get("server_company", "")
# # # # # #     currency = (pe.get("currency") or pe.get("paid_to_account_currency") or "USD").upper()
# # # # # #     mop      = pe.get("mode_of_payment") or "Cash"
# # # # # #     amount   = float(pe.get("paid_amount") or 0)
# # # # # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()

# # # # # #     # Use local gl_accounts table first (synced from Frappe)
# # # # # #     paid_to          = (pe.get("paid_to") or "").strip()
# # # # # #     paid_to_currency = currency
# # # # # #     if not paid_to:
# # # # # #         try:
# # # # # #             from models.gl_account import get_account_for_payment
# # # # # #             acct = get_account_for_payment(currency, company)
# # # # # #             if acct:
# # # # # #                 paid_to          = acct["name"]
# # # # # #                 paid_to_currency = acct["account_currency"]
# # # # # #         except Exception as _e:
# # # # # #             log.debug("gl_account lookup failed: %s", _e)

# # # # # #     # Fallback to live Frappe lookup
# # # # # #     if not paid_to:
# # # # # #         paid_to = _resolve_paid_to_account(mop, company, currency, api_key, api_secret, host)

# # # # # #     # Use local exchange rate if not stored
# # # # # #     exch_rate = float(pe.get("source_exchange_rate") or 1.0)
# # # # # #     if exch_rate == 1.0 and currency not in ("USD", ""):
# # # # # #         try:
# # # # # #             from models.exchange_rate import get_rate
# # # # # #             stored = get_rate(currency, "USD")
# # # # # #             if stored:
# # # # # #                 exch_rate = stored
# # # # # #         except Exception:
# # # # # #             pass

# # # # # #     payload = {
# # # # # #         "doctype":                  "Payment Entry",
# # # # # #         "payment_type":             "Receive",
# # # # # #         "party_type":               "Customer",
# # # # # #         "party":                    pe.get("party") or "default",
# # # # # #         "party_name":               pe.get("party_name") or "default",
# # # # # #         "paid_to_account_currency": paid_to_currency,
# # # # # #         "paid_amount":              amount,
# # # # # #         "received_amount":          amount,
# # # # # #         "source_exchange_rate":     exch_rate,
# # # # # #         "reference_no":             pe.get("reference_no") or pe.get("sale_invoice_no", ""),
# # # # # #         "reference_date":           pe.get("reference_date") or date.today().isoformat(),
# # # # # #         "remarks":                  pe.get("remarks") or f"POS Payment — {mop}",
# # # # # #         "mode_of_payment":          mop,
# # # # # #         "docstatus":                1,
# # # # # #     }

# # # # # #     if paid_to:
# # # # # #         payload["paid_to"] = paid_to
# # # # # #     if company:
# # # # # #         payload["company"] = company

# # # # # #     # Link to the Sales Invoice on Frappe
# # # # # #     if frappe_inv:
# # # # # #         payload["references"] = [{
# # # # # #             "reference_doctype": "Sales Invoice",
# # # # # #             "reference_name":    frappe_inv,
# # # # # #             "allocated_amount":  amount,
# # # # # #         }]

# # # # # #     return payload


# # # # # # # =============================================================================
# # # # # # # PUSH ONE PAYMENT ENTRY
# # # # # # # =============================================================================

# # # # # # def _push_payment_entry(pe: dict, api_key: str, api_secret: str,
# # # # # #                         defaults: dict, host: str) -> str | None:
# # # # # #     """
# # # # # #     Posts one payment entry to Frappe.
# # # # # #     Returns Frappe's PAY-xxxxx name on success, None on failure.
# # # # # #     """
# # # # # #     pe_id  = pe["id"]
# # # # # #     inv_no = pe.get("sale_invoice_no", str(pe_id))

# # # # # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()
# # # # # #     if not frappe_inv:
# # # # # #         log.warning("Payment %d — Sales Invoice not yet on Frappe, skipping.", pe_id)
# # # # # #         return None

# # # # # #     payload = _build_payload(pe, defaults, api_key, api_secret, host)

# # # # # #     url = f"{host}/api/resource/Payment%20Entry"
# # # # # #     req = urllib.request.Request(
# # # # # #         url=url,
# # # # # #         data=json.dumps(payload).encode("utf-8"),
# # # # # #         method="POST",
# # # # # #         headers={
# # # # # #             "Content-Type":  "application/json",
# # # # # #             "Accept":        "application/json",
# # # # # #             "Authorization": f"token {api_key}:{api_secret}",
# # # # # #         },
# # # # # #     )

# # # # # #     try:
# # # # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
# # # # # #             data = json.loads(resp.read().decode())
# # # # # #             name = (data.get("data") or {}).get("name", "")
# # # # # #             log.info("✅ Payment Entry %d → Frappe %s  [%s  %s %.2f]",
# # # # # #                      pe_id, name, inv_no,
# # # # # #                      pe.get("currency", ""), float(pe.get("paid_amount", 0)))
# # # # # #             return name or "SYNCED"

# # # # # #     except urllib.error.HTTPError as e:
# # # # # #         try:
# # # # # #             err = json.loads(e.read().decode())
# # # # # #             msg = (err.get("exception") or err.get("message") or
# # # # # #                    str(err.get("_server_messages", "")) or f"HTTP {e.code}")
# # # # # #         except Exception:
# # # # # #             msg = f"HTTP {e.code}"

# # # # # #         if e.code == 409:
# # # # # #             log.info("Payment %d already on Frappe (409) - marking synced.", pe_id)
# # # # # #             return "DUPLICATE"

# # # # # #         # Invoice already paid (is_pos:1 on old invoices) - stop retrying
# # # # # #         if e.code == 417:
# # # # # #             _perma = ("already been fully paid", "already paid", "fully paid")
# # # # # #             if any(p in msg.lower() for p in _perma):
# # # # # #                 log.info("Payment %d - invoice already paid on Frappe, marking synced.", pe_id)
# # # # # #                 return "ALREADY_PAID"

# # # # # #         log.error("FAIL Payment Entry %d  HTTP %s: %s", pe_id, e.code, msg)
# # # # # #         return None

# # # # # #     except urllib.error.URLError as e:
# # # # # #         log.warning("Network error pushing payment %d: %s", pe_id, e.reason)
# # # # # #         return None

# # # # # #     except Exception as e:
# # # # # #         log.error("Unexpected error pushing payment %d: %s", pe_id, e)
# # # # # #         return None


# # # # # # # =============================================================================
# # # # # # # PUBLIC — push all unsynced payment entries
# # # # # # # =============================================================================

# # # # # # def push_unsynced_payment_entries() -> dict:
# # # # # #     """
# # # # # #     1. Refresh frappe_invoice_ref from parent sales that were confirmed.
# # # # # #     2. Push each unsynced payment entry to Frappe.
# # # # # #     3. Mark synced with the returned PAY-xxxxx ref.
# # # # # #     """
# # # # # #     result = {"pushed": 0, "failed": 0, "skipped": 0, "total": 0}

# # # # # #     api_key, api_secret = _get_credentials()
# # # # # #     if not api_key or not api_secret:
# # # # # #         log.warning("No credentials — skipping payment entry sync.")
# # # # # #         return result

# # # # # #     host     = _get_host()
# # # # # #     defaults = _get_defaults()

# # # # # #     # First: pull frappe_refs from confirmed invoices into pending payment entries
# # # # # #     updated = refresh_frappe_refs()
# # # # # #     if updated:
# # # # # #         log.info("Refreshed frappe_invoice_ref on %d payment entry(ies).", updated)

# # # # # #     entries = get_unsynced_payment_entries()
# # # # # #     result["total"] = len(entries)

# # # # # #     if not entries:
# # # # # #         log.debug("No unsynced payment entries.")
# # # # # #         return result

# # # # # #     log.info("Pushing %d payment entry(ies) to Frappe…", len(entries))

# # # # # #     for pe in entries:
# # # # # #         frappe_name = _push_payment_entry(pe, api_key, api_secret, defaults, host)
# # # # # #         if frappe_name:
# # # # # #             mark_payment_synced(pe["id"], frappe_name)
# # # # # #             result["pushed"] += 1
# # # # # #         elif frappe_name is None:
# # # # # #             # None = permanent skip (no frappe_inv yet), not a real failure
# # # # # #             result["skipped"] += 1
# # # # # #         else:
# # # # # #             result["failed"] += 1

# # # # # #         time.sleep(3)   # rate limit — 20/min max

# # # # # #     log.info("Payment sync done — ✅ %d pushed  ❌ %d failed  ⏭ %d skipped",
# # # # # #              result["pushed"], result["failed"], result["skipped"])
# # # # # #     return result


# # # # # # # =============================================================================
# # # # # # # BACKGROUND DAEMON THREAD
# # # # # # # =============================================================================

# # # # # # def _sync_loop():
# # # # # #     log.info("Payment entry sync daemon started (interval=%ds).", SYNC_INTERVAL)
# # # # # #     while True:
# # # # # #         if _sync_lock.acquire(blocking=False):
# # # # # #             try:
# # # # # #                 push_unsynced_payment_entries()
# # # # # #             except Exception as e:
# # # # # #                 log.error("Payment sync cycle error: %s", e)
# # # # # #             finally:
# # # # # #                 _sync_lock.release()
# # # # # #         else:
# # # # # #             log.debug("Previous payment sync still running — skipping.")
# # # # # #         time.sleep(SYNC_INTERVAL)


# # # # # # def start_payment_sync_daemon() -> threading.Thread:
# # # # # #     """Non-blocking — safe to call from MainWindow.__init__."""
# # # # # #     global _sync_thread
# # # # # #     if _sync_thread and _sync_thread.is_alive():
# # # # # #         return _sync_thread
# # # # # #     t = threading.Thread(target=_sync_loop, daemon=True, name="PaymentSyncDaemon")
# # # # # #     t.start()
# # # # # #     _sync_thread = t
# # # # # #     log.info("Payment entry sync daemon started.")
# # # # # #     return t


# # # # # # # =============================================================================
# # # # # # # DEBUG
# # # # # # # =============================================================================

# # # # # # if __name__ == "__main__":
# # # # # #     logging.basicConfig(level=logging.INFO,
# # # # # #                         format="%(asctime)s [%(levelname)s] %(message)s")
# # # # # #     print("Running one payment entry sync cycle...")
# # # # # #     r = push_unsynced_payment_entries()
# # # # # #     print(f"\nResult: {r['pushed']} pushed, {r['failed']} failed, "
# # # # # #           f"{r['skipped']} skipped (of {r['total']} total)")

# # # # # # =============================================================================
# # # # # # services/payment_entry_service.py
# # # # # #
# # # # # # Manages local payment_entries table and syncs them to Frappe.
# # # # # #
# # # # # # FLOW:
# # # # # #   1. When a sale is saved locally → create_payment_entry() stores it locally
# # # # # #      with synced=0
# # # # # #   2. When the Sales Invoice is confirmed on Frappe (frappe_ref is set) →
# # # # # #      push_unsynced_payment_entries() pushes the Payment Entry to Frappe
# # # # # #   3. Frappe returns a PAY-xxxxx ref → stored as frappe_payment_ref, synced=1
# # # # # #
# # # # # # PAYLOAD SENT TO FRAPPE:
# # # # # #   POST /api/resource/Payment Entry
# # # # # #   {
# # # # # #     "doctype":              "Payment Entry",
# # # # # #     "payment_type":         "Receive",
# # # # # #     "party_type":           "Customer",
# # # # # #     "party":                "Cathy",
# # # # # #     "paid_to":              "Cash ZWG - H",
# # # # # #     "paid_to_account_currency": "USD",
# # # # # #     "paid_amount":          32.45,
# # # # # #     "received_amount":      32.45,
# # # # # #     "source_exchange_rate": 1.0,
# # # # # #     "reference_no":         "ACC-SINV-2026-00034",
# # # # # #     "reference_date":       "2026-03-19",
# # # # # #     "remarks":              "POS Payment — Cash",
# # # # # #     "docstatus":            1,
# # # # # #     "references": [{
# # # # # #         "reference_doctype": "Sales Invoice",
# # # # # #         "reference_name":    "ACC-SINV-2026-00565",
# # # # # #         "allocated_amount":  32.45
# # # # # #     }]
# # # # # #   }
# # # # # # =============================================================================

# # # # # from __future__ import annotations

# # # # # import json
# # # # # import logging
# # # # # import time
# # # # # import threading
# # # # # import urllib.request
# # # # # import urllib.error
# # # # # from datetime import date

# # # # # log = logging.getLogger("PaymentEntry")

# # # # # SYNC_INTERVAL   = 60      # seconds between auto-sync cycles
# # # # # REQUEST_TIMEOUT = 30

# # # # # # Exchange rate cache: "FROM::TO::DATE" → float
# # # # # _RATE_CACHE: dict[str, float] = {}


# # # # # def _get_exchange_rate(from_currency: str, to_currency: str,
# # # # #                        transaction_date: str,
# # # # #                        api_key: str, api_secret: str, host: str) -> float:
# # # # #     """
# # # # #     Fetch live exchange rate from Frappe.
# # # # #     Returns 1.0 for same currency, 0.0 if fetch fails (Frappe uses its own rate).
# # # # #     """
# # # # #     if not from_currency or from_currency.upper() == to_currency.upper():
# # # # #         return 1.0

# # # # #     cache_key = f"{from_currency.upper()}::{to_currency.upper()}::{transaction_date}"
# # # # #     if cache_key in _RATE_CACHE:
# # # # #         return _RATE_CACHE[cache_key]

# # # # #     try:
# # # # #         import urllib.parse
# # # # #         url = (
# # # # #             f"{host}/api/method/erpnext.setup.utils.get_exchange_rate"
# # # # #             f"?from_currency={urllib.parse.quote(from_currency)}"
# # # # #             f"&to_currency={urllib.parse.quote(to_currency)}"
# # # # #             f"&transaction_date={transaction_date}"
# # # # #         )
# # # # #         req = urllib.request.Request(url)
# # # # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # # # #             data = json.loads(r.read().decode())
# # # # #             rate = float(data.get("message") or data.get("result") or 0)
# # # # #             if rate > 0:
# # # # #                 _RATE_CACHE[cache_key] = rate
# # # # #                 log.debug("Rate %s→%s on %s: %.6f", from_currency, to_currency, transaction_date, rate)
# # # # #                 return rate
# # # # #     except Exception as e:
# # # # #         log.debug("Rate fetch failed (%s→%s): %s", from_currency, to_currency, e)

# # # # #     return 0.0

# # # # # _sync_lock:   threading.Lock          = threading.Lock()
# # # # # _sync_thread: threading.Thread | None = None

# # # # # # Method → Frappe Mode of Payment name
# # # # # _METHOD_MAP = {
# # # # #     "CASH":     "Cash",
# # # # #     "CARD":     "Credit Card",
# # # # #     "C / CARD": "Credit Card",
# # # # #     "EFTPOS":   "Credit Card",
# # # # #     "CHECK":    "Cheque",
# # # # #     "CHEQUE":   "Cheque",
# # # # #     "MOBILE":   "Mobile Money",
# # # # #     "CREDIT":   "Credit",
# # # # #     "TRANSFER": "Bank Transfer",
# # # # # }


# # # # # # =============================================================================
# # # # # # CREDENTIALS / HOST / DEFAULTS
# # # # # # =============================================================================

# # # # # def _get_credentials() -> tuple[str, str]:
# # # # #     try:
# # # # #         from services.credentials import get_credentials
# # # # #         return get_credentials()
# # # # #     except Exception:
# # # # #         pass
# # # # #     return "", ""


# # # # # def _get_host() -> str:
# # # # #     try:
# # # # #         from models.company_defaults import get_defaults
# # # # #         host = (get_defaults() or {}).get("server_api_host", "").strip().rstrip("/")
# # # # #         if host:
# # # # #             return host
# # # # #     except Exception:
# # # # #         pass
# # # # #     return "https://apk.havano.cloud"


# # # # # def _get_defaults() -> dict:
# # # # #     try:
# # # # #         from models.company_defaults import get_defaults
# # # # #         return get_defaults() or {}
# # # # #     except Exception:
# # # # #         return {}


# # # # # # =============================================================================
# # # # # # GL ACCOUNT RESOLVER  (which account to credit for each payment method)
# # # # # # =============================================================================

# # # # # _ACCOUNT_CACHE: dict[str, str] = {}


# # # # # def _resolve_paid_to_account(mop_name: str, company: str, currency: str,
# # # # #                               api_key: str, api_secret: str, host: str) -> str:
# # # # #     """
# # # # #     Looks up the GL account for a Mode of Payment from Frappe.
# # # # #     Tries to match by currency if multiple accounts exist for the company.
# # # # #     Falls back to server_pos_account in company_defaults.
# # # # #     """
# # # # #     cache_key = f"{mop_name}::{company}::{currency}"
# # # # #     if cache_key in _ACCOUNT_CACHE:
# # # # #         return _ACCOUNT_CACHE[cache_key]

# # # # #     try:
# # # # #         import urllib.parse
# # # # #         url = (f"{host}/api/resource/Mode%20of%20Payment/"
# # # # #                f"{urllib.parse.quote(mop_name)}?fields=[\"accounts\"]")
# # # # #         req = urllib.request.Request(url)
# # # # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # # # #             data     = json.loads(r.read().decode())
# # # # #             accounts = (data.get("data") or {}).get("accounts", [])

# # # # #         company_accts = [a for a in accounts
# # # # #                          if not company or a.get("company") == company]

# # # # #         # Prefer account whose name contains the currency code
# # # # #         matched = ""
# # # # #         if currency:
# # # # #             for a in company_accts:
# # # # #                 if currency.upper() in (a.get("default_account") or "").upper():
# # # # #                     matched = a["default_account"]; break

# # # # #         if not matched and company_accts:
# # # # #             matched = company_accts[0].get("default_account", "")

# # # # #         if matched:
# # # # #             _ACCOUNT_CACHE[cache_key] = matched
# # # # #             return matched

# # # # #     except Exception as e:
# # # # #         log.debug("MOP account lookup failed for '%s': %s", mop_name, e)

# # # # #     # Fallback
# # # # #     fallback = _get_defaults().get("server_pos_account", "").strip()
# # # # #     if fallback:
# # # # #         _ACCOUNT_CACHE[cache_key] = fallback
# # # # #         return fallback

# # # # #     log.warning("No GL account for MOP '%s' currency=%s — Payment Entry may fail.",
# # # # #                 mop_name, currency)
# # # # #     return ""


# # # # # # =============================================================================
# # # # # # LOCAL DB  — create / read / update payment_entries
# # # # # # =============================================================================

# # # # # def create_payment_entry(sale: dict, override_rate: float = None,
# # # # #                          override_account: str = None) -> int | None:
# # # # #     """
# # # # #     Called immediately after a sale is saved locally.
# # # # #     Stores a payment_entry row with synced=0.
# # # # #     Returns the new payment_entry id, or None on error.

# # # # #     Will only create the entry once per sale (idempotent).
# # # # #     """
# # # # #     from database.db import get_connection
# # # # #     conn = get_connection(); cur = conn.cursor()

# # # # #     # Idempotency: don't create twice for the same sale
# # # # #     cur.execute("SELECT id FROM payment_entries WHERE sale_id = ?", (sale["id"],))
# # # # #     if cur.fetchone():
# # # # #         conn.close()
# # # # #         return None

# # # # #     customer   = (sale.get("customer_name") or "default").strip()
# # # # #     currency   = (sale.get("currency")      or "USD").strip().upper()
# # # # #     amount     = float(sale.get("total")    or 0)
# # # # #     inv_no     = sale.get("invoice_no", "")
# # # # #     inv_date   = sale.get("invoice_date") or date.today().isoformat()
# # # # #     method     = str(sale.get("method", "CASH")).upper().strip()
# # # # #     mop        = _METHOD_MAP.get(method, "Cash")

# # # # #     # Use override rate (from split) or fetch from Frappe
# # # # #     if override_rate is not None:
# # # # #         exch_rate = override_rate
# # # # #     else:
# # # # #         try:
# # # # #             api_key, api_secret = _get_credentials()
# # # # #             host = _get_host()
# # # # #             defaults = _get_defaults()
# # # # #             company_currency = defaults.get("server_company_currency", "USD").strip().upper() or "USD"
# # # # #             exch_rate = _get_exchange_rate(
# # # # #                 currency, company_currency, inv_date, api_key, api_secret, host
# # # # #             ) if currency != company_currency else 1.0
# # # # #         except Exception:
# # # # #             exch_rate = 1.0

# # # # #     cur.execute("""
# # # # #         INSERT INTO payment_entries (
# # # # #             sale_id, sale_invoice_no, frappe_invoice_ref,
# # # # #             party, party_name,
# # # # #             paid_amount, received_amount, source_exchange_rate,
# # # # #             paid_to_account_currency, currency,
# # # # #             mode_of_payment,
# # # # #             reference_no, reference_date,
# # # # #             remarks, synced
# # # # #         ) OUTPUT INSERTED.id
# # # # #         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # # # #     """, (
# # # # #         sale["id"], inv_no,
# # # # #         sale.get("frappe_ref") or None,
# # # # #         customer, customer,
# # # # #         amount, amount, exch_rate or 1.0,
# # # # #         currency, currency,
# # # # #         mop,
# # # # #         inv_no, inv_date,
# # # # #         f"POS Payment — {mop}",
# # # # #     ))
# # # # #     new_id = int(cur.fetchone()[0])
# # # # #     conn.commit(); conn.close()
# # # # #     log.debug("Payment entry %d created locally for sale %s", new_id, inv_no)
# # # # #     return new_id


# # # # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # # # #     """
# # # # #     Called when cashier uses Split payment.
# # # # #     Creates one payment_entry row per currency in splits list.
# # # # #     splits = [{"mode": "CASH", "currency": "USD", "amount": 5.0,
# # # # #                "rate": 1.0, "base_amount": 5.0, "account": "Cash - AT"}, ...]
# # # # #     Returns list of new payment_entry ids.
# # # # #     """
# # # # #     ids = []
# # # # #     for split in splits:
# # # # #         if not split.get("amount") or float(split["amount"]) <= 0:
# # # # #             continue
# # # # #         # Build a sale-like dict with the split's currency and amount
# # # # #         split_sale = dict(sale)
# # # # #         split_sale["currency"]      = split.get("currency", "USD")
# # # # #         split_sale["total"]         = float(split.get("amount", 0))
# # # # #         split_sale["method"]        = split.get("mode", "CASH")
# # # # #         # Override exchange rate from split data
# # # # #         new_id = create_payment_entry(
# # # # #             split_sale,
# # # # #             override_rate=float(split.get("rate", 1.0)),
# # # # #             override_account=split.get("account", ""),
# # # # #         )
# # # # #         if new_id:
# # # # #             ids.append(new_id)
# # # # #     return ids


# # # # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # # # #     """
# # # # #     Creates one payment_entry per currency from a split payment.
# # # # #     Groups splits by currency, sums amounts, creates one entry each.
# # # # #     Returns list of created payment_entry ids.
# # # # #     """
# # # # #     from datetime import date as _date

# # # # #     # Group by currency
# # # # #     by_currency: dict[str, dict] = {}
# # # # #     for s in splits:
# # # # #         curr = s.get("account_currency", "USD").upper()
# # # # #         if curr not in by_currency:
# # # # #             by_currency[curr] = {
# # # # #                 "currency":      curr,
# # # # #                 "paid_amount":   0.0,
# # # # #                 "base_value":    0.0,
# # # # #                 "rate":          s.get("rate", 1.0),
# # # # #                 "account_name":  s.get("account_name", ""),
# # # # #                 "mode":          s.get("mode", "Cash"),
# # # # #             }
# # # # #         by_currency[curr]["paid_amount"] += s.get("amount_paid", 0.0)
# # # # #         by_currency[curr]["base_value"]  += s.get("base_value",  0.0)

# # # # #     ids = []
# # # # #     inv_no   = sale.get("invoice_no", "")
# # # # #     inv_date = sale.get("invoice_date") or _date.today().isoformat()
# # # # #     customer = (sale.get("customer_name") or "default").strip()

# # # # #     from database.db import get_connection
# # # # #     conn = get_connection(); cur = conn.cursor()

# # # # #     for curr, grp in by_currency.items():
# # # # #         # Idempotency: skip if already exists for this sale+currency
# # # # #         cur.execute(
# # # # #             "SELECT id FROM payment_entries WHERE sale_id=? AND currency=?",
# # # # #             (sale["id"], curr)
# # # # #         )
# # # # #         if cur.fetchone():
# # # # #             continue

# # # # #         mop = _METHOD_MAP.get(grp["mode"].upper(), "Cash")

# # # # #         cur.execute("""
# # # # #             INSERT INTO payment_entries (
# # # # #                 sale_id, sale_invoice_no, frappe_invoice_ref,
# # # # #                 party, party_name,
# # # # #                 paid_amount, received_amount, source_exchange_rate,
# # # # #                 paid_to_account_currency, currency,
# # # # #                 paid_to,
# # # # #                 mode_of_payment,
# # # # #                 reference_no, reference_date,
# # # # #                 remarks, synced
# # # # #             ) OUTPUT INSERTED.id
# # # # #             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # # # #         """, (
# # # # #             sale["id"], inv_no,
# # # # #             sale.get("frappe_ref") or None,
# # # # #             customer, customer,
# # # # #             grp["paid_amount"],
# # # # #             grp["base_value"],
# # # # #             float(grp["rate"] or 1.0),
# # # # #             curr, curr,
# # # # #             grp["account_name"],
# # # # #             mop,
# # # # #             inv_no, inv_date,
# # # # #             f"POS Split Payment — {mop} ({curr})",
# # # # #         ))
# # # # #         new_id = int(cur.fetchone()[0])
# # # # #         ids.append(new_id)
# # # # #         log.debug("Split payment entry %d created: %s %.2f %s",
# # # # #                   new_id, curr, grp["paid_amount"], inv_no)

# # # # #     conn.commit(); conn.close()
# # # # #     return ids


# # # # # def get_unsynced_payment_entries() -> list[dict]:
# # # # #     """Returns payment entries that are ready to push (synced=0)."""
# # # # #     from database.db import get_connection, fetchall_dicts
# # # # #     conn = get_connection(); cur = conn.cursor()
# # # # #     cur.execute("""
# # # # #         SELECT pe.*, s.frappe_ref AS sale_frappe_ref
# # # # #         FROM payment_entries pe
# # # # #         LEFT JOIN sales s ON s.id = pe.sale_id
# # # # #         WHERE pe.synced = 0
# # # # #           AND (pe.frappe_invoice_ref IS NOT NULL
# # # # #                OR s.frappe_ref IS NOT NULL)
# # # # #         ORDER BY pe.id
# # # # #     """)
# # # # #     rows = fetchall_dicts(cur); conn.close()
# # # # #     return rows


# # # # # def mark_payment_synced(pe_id: int, frappe_payment_ref: str = "") -> None:
# # # # #     from database.db import get_connection
# # # # #     conn = get_connection(); cur = conn.cursor()
# # # # #     cur.execute(
# # # # #         "UPDATE payment_entries SET synced=1, frappe_payment_ref=? WHERE id=?",
# # # # #         (frappe_payment_ref or None, pe_id)
# # # # #     )
# # # # #     # Also update the sales row
# # # # #     cur.execute("""
# # # # #         UPDATE sales SET payment_entry_ref=?, payment_synced=1
# # # # #         WHERE id = (SELECT sale_id FROM payment_entries WHERE id=?)
# # # # #     """, (frappe_payment_ref or None, pe_id))
# # # # #     conn.commit(); conn.close()


# # # # # def refresh_frappe_refs() -> int:
# # # # #     """
# # # # #     For payment entries that have no frappe_invoice_ref yet, copy it from
# # # # #     the parent sale's frappe_ref. Call this before pushing payments.
# # # # #     Returns count updated.
# # # # #     """
# # # # #     from database.db import get_connection
# # # # #     conn = get_connection(); cur = conn.cursor()
# # # # #     cur.execute("""
# # # # #         UPDATE pe
# # # # #         SET pe.frappe_invoice_ref = s.frappe_ref
# # # # #         FROM payment_entries pe
# # # # #         JOIN sales s ON s.id = pe.sale_id
# # # # #         WHERE pe.synced = 0
# # # # #           AND (pe.frappe_invoice_ref IS NULL OR pe.frappe_invoice_ref = '')
# # # # #           AND s.frappe_ref IS NOT NULL AND s.frappe_ref != ''
# # # # #     """)
# # # # #     count = cur.rowcount
# # # # #     conn.commit(); conn.close()
# # # # #     return count


# # # # # # =============================================================================
# # # # # # BUILD FRAPPE PAYLOAD
# # # # # # =============================================================================

# # # # # def _build_payload(pe: dict, defaults: dict,
# # # # #                    api_key: str, api_secret: str, host: str) -> dict:
# # # # #     company  = defaults.get("server_company", "")
# # # # #     currency = (pe.get("currency") or pe.get("paid_to_account_currency") or "USD").upper()
# # # # #     mop      = pe.get("mode_of_payment") or "Cash"
# # # # #     amount   = float(pe.get("paid_amount") or 0)
# # # # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()

# # # # #     # Use local gl_accounts table first (synced from Frappe)
# # # # #     paid_to          = (pe.get("paid_to") or "").strip()
# # # # #     paid_to_currency = currency
# # # # #     if not paid_to:
# # # # #         try:
# # # # #             from models.gl_account import get_account_for_payment
# # # # #             acct = get_account_for_payment(currency, company)
# # # # #             if acct:
# # # # #                 paid_to          = acct["name"]
# # # # #                 paid_to_currency = acct["account_currency"]
# # # # #         except Exception as _e:
# # # # #             log.debug("gl_account lookup failed: %s", _e)

# # # # #     # Fallback to live Frappe lookup
# # # # #     if not paid_to:
# # # # #         paid_to = _resolve_paid_to_account(mop, company, currency, api_key, api_secret, host)

# # # # #     # Use local exchange rate if not stored
# # # # #     exch_rate = float(pe.get("source_exchange_rate") or 1.0)
# # # # #     if exch_rate == 1.0 and currency not in ("USD", ""):
# # # # #         try:
# # # # #             from models.exchange_rate import get_rate
# # # # #             stored = get_rate(currency, "USD")
# # # # #             if stored:
# # # # #                 exch_rate = stored
# # # # #         except Exception:
# # # # #             pass

# # # # #     payload = {
# # # # #         "doctype":                  "Payment Entry",
# # # # #         "payment_type":             "Receive",
# # # # #         "party_type":               "Customer",
# # # # #         "party":                    pe.get("party") or "default",
# # # # #         "party_name":               pe.get("party_name") or "default",
# # # # #         "paid_to_account_currency": paid_to_currency,
# # # # #         "paid_amount":              amount,
# # # # #         "received_amount":          amount,
# # # # #         "source_exchange_rate":     exch_rate,
# # # # #         "reference_no":             pe.get("reference_no") or pe.get("sale_invoice_no", ""),
# # # # #         "reference_date":           pe.get("reference_date") or date.today().isoformat(),
# # # # #         "remarks":                  pe.get("remarks") or f"POS Payment — {mop}",
# # # # #         "mode_of_payment":          mop,
# # # # #         "docstatus":                1,
# # # # #     }

# # # # #     if paid_to:
# # # # #         payload["paid_to"] = paid_to
# # # # #     if company:
# # # # #         payload["company"] = company

# # # # #     # Link to the Sales Invoice on Frappe
# # # # #     if frappe_inv:
# # # # #         payload["references"] = [{
# # # # #             "reference_doctype": "Sales Invoice",
# # # # #             "reference_name":    frappe_inv,
# # # # #             "allocated_amount":  amount,
# # # # #         }]

# # # # #     return payload


# # # # # # =============================================================================
# # # # # # PUSH ONE PAYMENT ENTRY
# # # # # # =============================================================================

# # # # # def _push_payment_entry(pe: dict, api_key: str, api_secret: str,
# # # # #                         defaults: dict, host: str) -> str | None:
# # # # #     """
# # # # #     Posts one payment entry to Frappe.
# # # # #     Returns Frappe's PAY-xxxxx name on success, None on failure.
# # # # #     """
# # # # #     pe_id  = pe["id"]
# # # # #     inv_no = pe.get("sale_invoice_no", str(pe_id))

# # # # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()
# # # # #     if not frappe_inv:
# # # # #         log.warning("Payment %d — Sales Invoice not yet on Frappe, skipping.", pe_id)
# # # # #         return None

# # # # #     payload = _build_payload(pe, defaults, api_key, api_secret, host)

# # # # #     url = f"{host}/api/resource/Payment%20Entry"
# # # # #     req = urllib.request.Request(
# # # # #         url=url,
# # # # #         data=json.dumps(payload).encode("utf-8"),
# # # # #         method="POST",
# # # # #         headers={
# # # # #             "Content-Type":  "application/json",
# # # # #             "Accept":        "application/json",
# # # # #             "Authorization": f"token {api_key}:{api_secret}",
# # # # #         },
# # # # #     )

# # # # #     try:
# # # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
# # # # #             data = json.loads(resp.read().decode())
# # # # #             name = (data.get("data") or {}).get("name", "")
# # # # #             log.info("✅ Payment Entry %d → Frappe %s  [%s  %s %.2f]",
# # # # #                      pe_id, name, inv_no,
# # # # #                      pe.get("currency", ""), float(pe.get("paid_amount", 0)))
# # # # #             return name or "SYNCED"

# # # # #     except urllib.error.HTTPError as e:
# # # # #         try:
# # # # #             err = json.loads(e.read().decode())
# # # # #             msg = (err.get("exception") or err.get("message") or
# # # # #                    str(err.get("_server_messages", "")) or f"HTTP {e.code}")
# # # # #         except Exception:
# # # # #             msg = f"HTTP {e.code}"

# # # # #         if e.code == 409:
# # # # #             log.info("Payment %d already on Frappe (409) - marking synced.", pe_id)
# # # # #             return "DUPLICATE"

# # # # #         # Invoice already paid (is_pos:1 on old invoices) - stop retrying
# # # # #         if e.code == 417:
# # # # #             _perma = ("already been fully paid", "already paid", "fully paid")
# # # # #             if any(p in msg.lower() for p in _perma):
# # # # #                 log.info("Payment %d - invoice already paid on Frappe, marking synced.", pe_id)
# # # # #                 return "ALREADY_PAID"

# # # # #         log.error("FAIL Payment Entry %d  HTTP %s: %s", pe_id, e.code, msg)
# # # # #         return None

# # # # #     except urllib.error.URLError as e:
# # # # #         log.warning("Network error pushing payment %d: %s", pe_id, e.reason)
# # # # #         return None

# # # # #     except Exception as e:
# # # # #         log.error("Unexpected error pushing payment %d: %s", pe_id, e)
# # # # #         return None


# # # # # # =============================================================================
# # # # # # PUBLIC — push all unsynced payment entries
# # # # # # =============================================================================

# # # # # def push_unsynced_payment_entries() -> dict:
# # # # #     """
# # # # #     1. Refresh frappe_invoice_ref from parent sales that were confirmed.
# # # # #     2. Push each unsynced payment entry to Frappe.
# # # # #     3. Mark synced with the returned PAY-xxxxx ref.
# # # # #     """
# # # # #     result = {"pushed": 0, "failed": 0, "skipped": 0, "total": 0}

# # # # #     api_key, api_secret = _get_credentials()
# # # # #     if not api_key or not api_secret:
# # # # #         log.warning("No credentials — skipping payment entry sync.")
# # # # #         return result

# # # # #     host     = _get_host()
# # # # #     defaults = _get_defaults()

# # # # #     # First: pull frappe_refs from confirmed invoices into pending payment entries
# # # # #     updated = refresh_frappe_refs()
# # # # #     if updated:
# # # # #         log.info("Refreshed frappe_invoice_ref on %d payment entry(ies).", updated)

# # # # #     entries = get_unsynced_payment_entries()
# # # # #     result["total"] = len(entries)

# # # # #     if not entries:
# # # # #         log.debug("No unsynced payment entries.")
# # # # #         return result

# # # # #     log.info("Pushing %d payment entry(ies) to Frappe…", len(entries))

# # # # #     for pe in entries:
# # # # #         frappe_name = _push_payment_entry(pe, api_key, api_secret, defaults, host)
# # # # #         if frappe_name:
# # # # #             mark_payment_synced(pe["id"], frappe_name)
# # # # #             result["pushed"] += 1
# # # # #         elif frappe_name is None:
# # # # #             # None = permanent skip (no frappe_inv yet), not a real failure
# # # # #             result["skipped"] += 1
# # # # #         else:
# # # # #             result["failed"] += 1

# # # # #         time.sleep(3)   # rate limit — 20/min max

# # # # #     log.info("Payment sync done — ✅ %d pushed  ❌ %d failed  ⏭ %d skipped",
# # # # #              result["pushed"], result["failed"], result["skipped"])
# # # # #     return result


# # # # # # =============================================================================
# # # # # # BACKGROUND DAEMON THREAD
# # # # # # =============================================================================

# # # # # def _sync_loop():
# # # # #     log.info("Payment entry sync daemon started (interval=%ds).", SYNC_INTERVAL)
# # # # #     while True:
# # # # #         if _sync_lock.acquire(blocking=False):
# # # # #             try:
# # # # #                 push_unsynced_payment_entries()
# # # # #             except Exception as e:
# # # # #                 log.error("Payment sync cycle error: %s", e)
# # # # #             finally:
# # # # #                 _sync_lock.release()
# # # # #         else:
# # # # #             log.debug("Previous payment sync still running — skipping.")
# # # # #         time.sleep(SYNC_INTERVAL)


# # # # # def start_payment_sync_daemon() -> threading.Thread:
# # # # #     """Non-blocking — safe to call from MainWindow.__init__."""
# # # # #     global _sync_thread
# # # # #     if _sync_thread and _sync_thread.is_alive():
# # # # #         return _sync_thread
# # # # #     t = threading.Thread(target=_sync_loop, daemon=True, name="PaymentSyncDaemon")
# # # # #     t.start()
# # # # #     _sync_thread = t
# # # # #     log.info("Payment entry sync daemon started.")
# # # # #     return t


# # # # # # =============================================================================
# # # # # # DEBUG
# # # # # # =============================================================================

# # # # # if __name__ == "__main__":
# # # # #     logging.basicConfig(level=logging.INFO,
# # # # #                         format="%(asctime)s [%(levelname)s] %(message)s")
# # # # #     print("Running one payment entry sync cycle...")
# # # # #     r = push_unsynced_payment_entries()
# # # # #     print(f"\nResult: {r['pushed']} pushed, {r['failed']} failed, "
# # # # #           f"{r['skipped']} skipped (of {r['total']} total)")

# # # # # =============================================================================
# # # # # services/payment_entry_service.py
# # # # #
# # # # # Manages local payment_entries table and syncs them to Frappe.
# # # # #
# # # # # FLOW:
# # # # #   1. When a sale is saved locally → create_payment_entry() stores it locally
# # # # #      with synced=0
# # # # #   2. When the Sales Invoice is confirmed on Frappe (frappe_ref is set) →
# # # # #      push_unsynced_payment_entries() pushes the Payment Entry to Frappe
# # # # #   3. Frappe returns a PAY-xxxxx ref → stored as frappe_payment_ref, synced=1
# # # # #
# # # # # PAYLOAD SENT TO FRAPPE:
# # # # #   POST /api/resource/Payment Entry
# # # # #   {
# # # # #     "doctype":              "Payment Entry",
# # # # #     "payment_type":         "Receive",
# # # # #     "party_type":           "Customer",
# # # # #     "party":                "Cathy",
# # # # #     "paid_to":              "Cash ZWG - H",
# # # # #     "paid_to_account_currency": "USD",
# # # # #     "paid_amount":          32.45,
# # # # #     "received_amount":      32.45,
# # # # #     "source_exchange_rate": 1.0,
# # # # #     "reference_no":         "ACC-SINV-2026-00034",
# # # # #     "reference_date":       "2026-03-19",
# # # # #     "remarks":              "POS Payment — Cash",
# # # # #     "docstatus":            1,
# # # # #     "references": [{
# # # # #         "reference_doctype": "Sales Invoice",
# # # # #         "reference_name":    "ACC-SINV-2026-00565",
# # # # #         "allocated_amount":  32.45
# # # # #     }]
# # # # #   }
# # # # # =============================================================================

# # # # from __future__ import annotations

# # # # import json
# # # # import logging
# # # # import time
# # # # import threading
# # # # import urllib.request
# # # # import urllib.error
# # # # from datetime import date

# # # # log = logging.getLogger("PaymentEntry")

# # # # SYNC_INTERVAL   = 60      # seconds between auto-sync cycles
# # # # REQUEST_TIMEOUT = 30

# # # # # Exchange rate cache: "FROM::TO::DATE" → float
# # # # _RATE_CACHE: dict[str, float] = {}


# # # # def _get_exchange_rate(from_currency: str, to_currency: str,
# # # #                        transaction_date: str,
# # # #                        api_key: str, api_secret: str, host: str) -> float:
# # # #     """
# # # #     Fetch live exchange rate from Frappe.
# # # #     Returns 1.0 for same currency, 0.0 if fetch fails (Frappe uses its own rate).
# # # #     """
# # # #     if not from_currency or from_currency.upper() == to_currency.upper():
# # # #         return 1.0

# # # #     cache_key = f"{from_currency.upper()}::{to_currency.upper()}::{transaction_date}"
# # # #     if cache_key in _RATE_CACHE:
# # # #         return _RATE_CACHE[cache_key]

# # # #     try:
# # # #         import urllib.parse
# # # #         url = (
# # # #             f"{host}/api/method/erpnext.setup.utils.get_exchange_rate"
# # # #             f"?from_currency={urllib.parse.quote(from_currency)}"
# # # #             f"&to_currency={urllib.parse.quote(to_currency)}"
# # # #             f"&transaction_date={transaction_date}"
# # # #         )
# # # #         req = urllib.request.Request(url)
# # # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # # #             data = json.loads(r.read().decode())
# # # #             rate = float(data.get("message") or data.get("result") or 0)
# # # #             if rate > 0:
# # # #                 _RATE_CACHE[cache_key] = rate
# # # #                 log.debug("Rate %s→%s on %s: %.6f", from_currency, to_currency, transaction_date, rate)
# # # #                 return rate
# # # #     except Exception as e:
# # # #         log.debug("Rate fetch failed (%s→%s): %s", from_currency, to_currency, e)

# # # #     return 0.0

# # # # _sync_lock:   threading.Lock          = threading.Lock()
# # # # _sync_thread: threading.Thread | None = None

# # # # # Method → Frappe Mode of Payment name
# # # # _METHOD_MAP = {
# # # #     "CASH":     "Cash",
# # # #     "CARD":     "Credit Card",
# # # #     "C / CARD": "Credit Card",
# # # #     "EFTPOS":   "Credit Card",
# # # #     "CHECK":    "Cheque",
# # # #     "CHEQUE":   "Cheque",
# # # #     "MOBILE":   "Mobile Money",
# # # #     "CREDIT":   "Credit",
# # # #     "TRANSFER": "Bank Transfer",
# # # # }


# # # # # =============================================================================
# # # # # CREDENTIALS / HOST / DEFAULTS
# # # # # =============================================================================

# # # # def _get_credentials() -> tuple[str, str]:
# # # #     try:
# # # #         from services.credentials import get_credentials
# # # #         return get_credentials()
# # # #     except Exception:
# # # #         pass
# # # #     return "", ""

# # # # def _get_host() -> str:
# # # #     try:
# # # #         from models.company_defaults import get_defaults
# # # #         host = (get_defaults() or {}).get("server_api_host", "").strip().rstrip("/")
# # # #         if host:
# # # #             return host
# # # #     except Exception:
# # # #         pass
# # # #     return "https://apk.havano.cloud"


# # # # def _get_defaults() -> dict:
# # # #     try:
# # # #         from models.company_defaults import get_defaults
# # # #         return get_defaults() or {}
# # # #     except Exception:
# # # #         return {}


# # # # # =============================================================================
# # # # # GL ACCOUNT RESOLVER  (which account to credit for each payment method)
# # # # # =============================================================================

# # # # _ACCOUNT_CACHE: dict[str, str] = {}


# # # # def _resolve_paid_to_account(mop_name: str, company: str, currency: str,
# # # #                               api_key: str, api_secret: str, host: str) -> str:
# # # #     """
# # # #     Looks up the GL account for a Mode of Payment from Frappe.
# # # #     Tries to match by currency if multiple accounts exist for the company.
# # # #     Falls back to server_pos_account in company_defaults.
# # # #     """
# # # #     cache_key = f"{mop_name}::{company}::{currency}"
# # # #     if cache_key in _ACCOUNT_CACHE:
# # # #         return _ACCOUNT_CACHE[cache_key]

# # # #     try:
# # # #         import urllib.parse
# # # #         url = (f"{host}/api/resource/Mode%20of%20Payment/"
# # # #                f"{urllib.parse.quote(mop_name)}?fields=[\"accounts\"]")
# # # #         req = urllib.request.Request(url)
# # # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # # #             data     = json.loads(r.read().decode())
# # # #             accounts = (data.get("data") or {}).get("accounts", [])

# # # #         company_accts = [a for a in accounts
# # # #                          if not company or a.get("company") == company]

# # # #         # Prefer account whose name contains the currency code
# # # #         matched = ""
# # # #         if currency:
# # # #             for a in company_accts:
# # # #                 if currency.upper() in (a.get("default_account") or "").upper():
# # # #                     matched = a["default_account"]; break

# # # #         if not matched and company_accts:
# # # #             matched = company_accts[0].get("default_account", "")

# # # #         if matched:
# # # #             _ACCOUNT_CACHE[cache_key] = matched
# # # #             return matched

# # # #     except Exception as e:
# # # #         log.debug("MOP account lookup failed for '%s': %s", mop_name, e)

# # # #     # Fallback
# # # #     fallback = _get_defaults().get("server_pos_account", "").strip()
# # # #     if fallback:
# # # #         _ACCOUNT_CACHE[cache_key] = fallback
# # # #         return fallback

# # # #     log.warning("No GL account for MOP '%s' currency=%s — Payment Entry may fail.",
# # # #                 mop_name, currency)
# # # #     return ""


# # # # # =============================================================================
# # # # # LOCAL DB  — create / read / update payment_entries
# # # # # =============================================================================

# # # # def create_payment_entry(sale: dict, override_rate: float = None,
# # # #                          override_account: str = None) -> int | None:
# # # #     """
# # # #     Called immediately after a sale is saved locally.
# # # #     Stores a payment_entry row with synced=0.
# # # #     Returns the new payment_entry id, or None on error.

# # # #     Will only create the entry once per sale (idempotent).
# # # #     """
# # # #     from database.db import get_connection
# # # #     conn = get_connection(); cur = conn.cursor()

# # # #     # Idempotency: don't create twice for the same sale
# # # #     cur.execute("SELECT id FROM payment_entries WHERE sale_id = ?", (sale["id"],))
# # # #     if cur.fetchone():
# # # #         conn.close()
# # # #         return None

# # # #     customer   = (sale.get("customer_name") or "default").strip()
# # # #     currency   = (sale.get("currency")      or "USD").strip().upper()
# # # #     amount     = float(sale.get("total")    or 0)
# # # #     inv_no     = sale.get("invoice_no", "")
# # # #     inv_date   = sale.get("invoice_date") or date.today().isoformat()
# # # #     method     = str(sale.get("method", "CASH")).upper().strip()
# # # #     mop        = _METHOD_MAP.get(method, "Cash")

# # # #     # Use override rate (from split) or fetch from Frappe
# # # #     if override_rate is not None:
# # # #         exch_rate = override_rate
# # # #     else:
# # # #         try:
# # # #             api_key, api_secret = _get_credentials()
# # # #             host = _get_host()
# # # #             defaults = _get_defaults()
# # # #             company_currency = defaults.get("server_company_currency", "USD").strip().upper() or "USD"
# # # #             exch_rate = _get_exchange_rate(
# # # #                 currency, company_currency, inv_date, api_key, api_secret, host
# # # #             ) if currency != company_currency else 1.0
# # # #         except Exception:
# # # #             exch_rate = 1.0

# # # #     cur.execute("""
# # # #         INSERT INTO payment_entries (
# # # #             sale_id, sale_invoice_no, frappe_invoice_ref,
# # # #             party, party_name,
# # # #             paid_amount, received_amount, source_exchange_rate,
# # # #             paid_to_account_currency, currency,
# # # #             mode_of_payment,
# # # #             reference_no, reference_date,
# # # #             remarks, synced
# # # #         ) OUTPUT INSERTED.id
# # # #         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # # #     """, (
# # # #         sale["id"], inv_no,
# # # #         sale.get("frappe_ref") or None,
# # # #         customer, customer,
# # # #         amount, amount, exch_rate or 1.0,
# # # #         currency, currency,
# # # #         mop,
# # # #         inv_no, inv_date,
# # # #         f"POS Payment — {mop}",
# # # #     ))
# # # #     new_id = int(cur.fetchone()[0])
# # # #     conn.commit(); conn.close()
# # # #     log.debug("Payment entry %d created locally for sale %s", new_id, inv_no)
# # # #     return new_id


# # # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # # #     """
# # # #     Called when cashier uses Split payment.
# # # #     Creates one payment_entry row per currency in splits list.
# # # #     splits = [{"mode": "CASH", "currency": "USD", "amount": 5.0,
# # # #                "rate": 1.0, "base_amount": 5.0, "account": "Cash - AT"}, ...]
# # # #     Returns list of new payment_entry ids.
# # # #     """
# # # #     ids = []
# # # #     for split in splits:
# # # #         if not split.get("amount") or float(split["amount"]) <= 0:
# # # #             continue
# # # #         # Build a sale-like dict with the split's currency and amount
# # # #         split_sale = dict(sale)
# # # #         split_sale["currency"]      = split.get("currency", "USD")
# # # #         split_sale["total"]         = float(split.get("amount", 0))
# # # #         split_sale["method"]        = split.get("mode", "CASH")
# # # #         # Override exchange rate from split data
# # # #         new_id = create_payment_entry(
# # # #             split_sale,
# # # #             override_rate=float(split.get("rate", 1.0)),
# # # #             override_account=split.get("account", ""),
# # # #         )
# # # #         if new_id:
# # # #             ids.append(new_id)
# # # #     return ids


# # # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # # #     """
# # # #     Creates one payment_entry per currency from a split payment.
# # # #     Groups splits by currency, sums amounts, creates one entry each.
# # # #     Returns list of created payment_entry ids.
# # # #     """
# # # #     from datetime import date as _date

# # # #     # Group by currency
# # # #     by_currency: dict[str, dict] = {}
# # # #     for s in splits:
# # # #         curr = s.get("account_currency", "USD").upper()
# # # #         if curr not in by_currency:
# # # #             by_currency[curr] = {
# # # #                 "currency":      curr,
# # # #                 "paid_amount":   0.0,
# # # #                 "base_value":    0.0,
# # # #                 "rate":          s.get("rate", 1.0),
# # # #                 "account_name":  s.get("account_name", ""),
# # # #                 "mode":          s.get("mode", "Cash"),
# # # #             }
# # # #         by_currency[curr]["paid_amount"] += s.get("amount_paid", 0.0)
# # # #         by_currency[curr]["base_value"]  += s.get("base_value",  0.0)

# # # #     ids = []
# # # #     inv_no   = sale.get("invoice_no", "")
# # # #     inv_date = sale.get("invoice_date") or _date.today().isoformat()
# # # #     customer = (sale.get("customer_name") or "default").strip()

# # # #     from database.db import get_connection
# # # #     conn = get_connection(); cur = conn.cursor()

# # # #     for curr, grp in by_currency.items():
# # # #         # Idempotency: skip if already exists for this sale+currency
# # # #         cur.execute(
# # # #             "SELECT id FROM payment_entries WHERE sale_id=? AND currency=?",
# # # #             (sale["id"], curr)
# # # #         )
# # # #         if cur.fetchone():
# # # #             continue

# # # #         mop = _METHOD_MAP.get(grp["mode"].upper(), "Cash")

# # # #         cur.execute("""
# # # #             INSERT INTO payment_entries (
# # # #                 sale_id, sale_invoice_no, frappe_invoice_ref,
# # # #                 party, party_name,
# # # #                 paid_amount, received_amount, source_exchange_rate,
# # # #                 paid_to_account_currency, currency,
# # # #                 paid_to,
# # # #                 mode_of_payment,
# # # #                 reference_no, reference_date,
# # # #                 remarks, synced
# # # #             ) OUTPUT INSERTED.id
# # # #             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # # #         """, (
# # # #             sale["id"], inv_no,
# # # #             sale.get("frappe_ref") or None,
# # # #             customer, customer,
# # # #             grp["paid_amount"],
# # # #             grp["base_value"],
# # # #             float(grp["rate"] or 1.0),
# # # #             curr, curr,
# # # #             grp["account_name"],
# # # #             mop,
# # # #             inv_no, inv_date,
# # # #             f"POS Split Payment — {mop} ({curr})",
# # # #         ))
# # # #         new_id = int(cur.fetchone()[0])
# # # #         ids.append(new_id)
# # # #         log.debug("Split payment entry %d created: %s %.2f %s",
# # # #                   new_id, curr, grp["paid_amount"], inv_no)

# # # #     conn.commit(); conn.close()
# # # #     return ids


# # # # def get_unsynced_payment_entries() -> list[dict]:
# # # #     """Returns payment entries that are ready to push (synced=0)."""
# # # #     from database.db import get_connection, fetchall_dicts
# # # #     conn = get_connection(); cur = conn.cursor()
# # # #     cur.execute("""
# # # #         SELECT pe.*, s.frappe_ref AS sale_frappe_ref
# # # #         FROM payment_entries pe
# # # #         LEFT JOIN sales s ON s.id = pe.sale_id
# # # #         WHERE pe.synced = 0
# # # #           AND (pe.frappe_invoice_ref IS NOT NULL
# # # #                OR s.frappe_ref IS NOT NULL)
# # # #         ORDER BY pe.id
# # # #     """)
# # # #     rows = fetchall_dicts(cur); conn.close()
# # # #     return rows


# # # # def mark_payment_synced(pe_id: int, frappe_payment_ref: str = "") -> None:
# # # #     from database.db import get_connection
# # # #     conn = get_connection(); cur = conn.cursor()
# # # #     cur.execute(
# # # #         "UPDATE payment_entries SET synced=1, frappe_payment_ref=? WHERE id=?",
# # # #         (frappe_payment_ref or None, pe_id)
# # # #     )
# # # #     # Also update the sales row
# # # #     cur.execute("""
# # # #         UPDATE sales SET payment_entry_ref=?, payment_synced=1
# # # #         WHERE id = (SELECT sale_id FROM payment_entries WHERE id=?)
# # # #     """, (frappe_payment_ref or None, pe_id))
# # # #     conn.commit(); conn.close()


# # # # def refresh_frappe_refs() -> int:
# # # #     """
# # # #     For payment entries that have no frappe_invoice_ref yet, copy it from
# # # #     the parent sale's frappe_ref. Call this before pushing payments.
# # # #     Returns count updated.
# # # #     """
# # # #     from database.db import get_connection
# # # #     conn = get_connection(); cur = conn.cursor()
# # # #     cur.execute("""
# # # #         UPDATE pe
# # # #         SET pe.frappe_invoice_ref = s.frappe_ref
# # # #         FROM payment_entries pe
# # # #         JOIN sales s ON s.id = pe.sale_id
# # # #         WHERE pe.synced = 0
# # # #           AND (pe.frappe_invoice_ref IS NULL OR pe.frappe_invoice_ref = '')
# # # #           AND s.frappe_ref IS NOT NULL AND s.frappe_ref != ''
# # # #     """)
# # # #     count = cur.rowcount
# # # #     conn.commit(); conn.close()
# # # #     return count


# # # # # =============================================================================
# # # # # BUILD FRAPPE PAYLOAD
# # # # # =============================================================================

# # # # def _build_payload(pe: dict, defaults: dict,
# # # #                    api_key: str, api_secret: str, host: str) -> dict:
# # # #     company  = defaults.get("server_company", "")
# # # #     currency = (pe.get("currency") or pe.get("paid_to_account_currency") or "USD").upper()
# # # #     mop      = pe.get("mode_of_payment") or "Cash"
# # # #     amount   = float(pe.get("paid_amount") or 0)
# # # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()

# # # #     # Use local gl_accounts table first (synced from Frappe)
# # # #     paid_to          = (pe.get("paid_to") or "").strip()
# # # #     paid_to_currency = currency
# # # #     if not paid_to:
# # # #         try:
# # # #             from models.gl_account import get_account_for_payment
# # # #             acct = get_account_for_payment(currency, company)
# # # #             if acct:
# # # #                 paid_to          = acct["name"]
# # # #                 paid_to_currency = acct["account_currency"]
# # # #         except Exception as _e:
# # # #             log.debug("gl_account lookup failed: %s", _e)

# # # #     # Fallback to live Frappe lookup
# # # #     if not paid_to:
# # # #         paid_to = _resolve_paid_to_account(mop, company, currency, api_key, api_secret, host)

# # # #     # Use local exchange rate if not stored
# # # #     exch_rate = float(pe.get("source_exchange_rate") or 1.0)
# # # #     if exch_rate == 1.0 and currency not in ("USD", ""):
# # # #         try:
# # # #             from models.exchange_rate import get_rate
# # # #             stored = get_rate(currency, "USD")
# # # #             if stored:
# # # #                 exch_rate = stored
# # # #         except Exception:
# # # #             pass

# # # #     payload = {
# # # #         "doctype":                  "Payment Entry",
# # # #         "payment_type":             "Receive",
# # # #         "party_type":               "Customer",
# # # #         "party":                    pe.get("party") or "default",
# # # #         "party_name":               pe.get("party_name") or "default",
# # # #         "paid_to_account_currency": paid_to_currency,
# # # #         "paid_amount":              amount,
# # # #         "received_amount":          amount,
# # # #         "source_exchange_rate":     exch_rate,
# # # #         "reference_no":             pe.get("reference_no") or pe.get("sale_invoice_no", ""),
# # # #         "reference_date":           pe.get("reference_date") or date.today().isoformat(),
# # # #         "remarks":                  pe.get("remarks") or f"POS Payment — {mop}",
# # # #         "mode_of_payment":          mop,
# # # #         "docstatus":                1,
# # # #     }

# # # #     if paid_to:
# # # #         payload["paid_to"] = paid_to
# # # #     if company:
# # # #         payload["company"] = company

# # # #     # Link to the Sales Invoice on Frappe
# # # #     if frappe_inv:
# # # #         payload["references"] = [{
# # # #             "reference_doctype": "Sales Invoice",
# # # #             "reference_name":    frappe_inv,
# # # #             "allocated_amount":  amount,
# # # #         }]

# # # #     return payload


# # # # # =============================================================================
# # # # # PUSH ONE PAYMENT ENTRY
# # # # # =============================================================================

# # # # def _push_payment_entry(pe: dict, api_key: str, api_secret: str,
# # # #                         defaults: dict, host: str) -> str | None:
# # # #     """
# # # #     Posts one payment entry to Frappe.
# # # #     Returns Frappe's PAY-xxxxx name on success, None on failure.
# # # #     """
# # # #     pe_id  = pe["id"]
# # # #     inv_no = pe.get("sale_invoice_no", str(pe_id))

# # # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()
# # # #     if not frappe_inv:
# # # #         log.warning("Payment %d — Sales Invoice not yet on Frappe, skipping.", pe_id)
# # # #         return None

# # # #     payload = _build_payload(pe, defaults, api_key, api_secret, host)

# # # #     url = f"{host}/api/resource/Payment%20Entry"
# # # #     req = urllib.request.Request(
# # # #         url=url,
# # # #         data=json.dumps(payload).encode("utf-8"),
# # # #         method="POST",
# # # #         headers={
# # # #             "Content-Type":  "application/json",
# # # #             "Accept":        "application/json",
# # # #             "Authorization": f"token {api_key}:{api_secret}",
# # # #         },
# # # #     )

# # # #     try:
# # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
# # # #             data = json.loads(resp.read().decode())
# # # #             name = (data.get("data") or {}).get("name", "")
# # # #             log.info("✅ Payment Entry %d → Frappe %s  [%s  %s %.2f]",
# # # #                      pe_id, name, inv_no,
# # # #                      pe.get("currency", ""), float(pe.get("paid_amount", 0)))
# # # #             return name or "SYNCED"

# # # #     except urllib.error.HTTPError as e:
# # # #         try:
# # # #             err = json.loads(e.read().decode())
# # # #             msg = (err.get("exception") or err.get("message") or
# # # #                    str(err.get("_server_messages", "")) or f"HTTP {e.code}")
# # # #         except Exception:
# # # #             msg = f"HTTP {e.code}"

# # # #         if e.code == 409:
# # # #             log.info("Payment %d already on Frappe (409) - marking synced.", pe_id)
# # # #             return "DUPLICATE"

# # # #         # Invoice already paid (is_pos:1 on old invoices) - stop retrying
# # # #         if e.code == 417:
# # # #             _perma = ("already been fully paid", "already paid", "fully paid")
# # # #             if any(p in msg.lower() for p in _perma):
# # # #                 log.info("Payment %d - invoice already paid on Frappe, marking synced.", pe_id)
# # # #                 return "ALREADY_PAID"

# # # #         log.error("FAIL Payment Entry %d  HTTP %s: %s", pe_id, e.code, msg)
# # # #         return None

# # # #     except urllib.error.URLError as e:
# # # #         log.warning("Network error pushing payment %d: %s", pe_id, e.reason)
# # # #         return None

# # # #     except Exception as e:
# # # #         log.error("Unexpected error pushing payment %d: %s", pe_id, e)
# # # #         return None


# # # # # =============================================================================
# # # # # PUBLIC — push all unsynced payment entries
# # # # # =============================================================================

# # # # def push_unsynced_payment_entries() -> dict:
# # # #     """
# # # #     1. Refresh frappe_invoice_ref from parent sales that were confirmed.
# # # #     2. Push each unsynced payment entry to Frappe.
# # # #     3. Mark synced with the returned PAY-xxxxx ref.
# # # #     """
# # # #     result = {"pushed": 0, "failed": 0, "skipped": 0, "total": 0}

# # # #     api_key, api_secret = _get_credentials()
# # # #     if not api_key or not api_secret:
# # # #         log.warning("No credentials — skipping payment entry sync.")
# # # #         return result

# # # #     host     = _get_host()
# # # #     defaults = _get_defaults()

# # # #     # First: pull frappe_refs from confirmed invoices into pending payment entries
# # # #     updated = refresh_frappe_refs()
# # # #     if updated:
# # # #         log.info("Refreshed frappe_invoice_ref on %d payment entry(ies).", updated)

# # # #     entries = get_unsynced_payment_entries()
# # # #     result["total"] = len(entries)

# # # #     if not entries:
# # # #         log.debug("No unsynced payment entries.")
# # # #         return result

# # # #     log.info("Pushing %d payment entry(ies) to Frappe…", len(entries))

# # # #     for pe in entries:
# # # #         frappe_name = _push_payment_entry(pe, api_key, api_secret, defaults, host)
# # # #         if frappe_name:
# # # #             mark_payment_synced(pe["id"], frappe_name)
# # # #             result["pushed"] += 1
# # # #         elif frappe_name is None:
# # # #             # None = permanent skip (no frappe_inv yet), not a real failure
# # # #             result["skipped"] += 1
# # # #         else:
# # # #             result["failed"] += 1

# # # #         time.sleep(3)   # rate limit — 20/min max

# # # #     log.info("Payment sync done — ✅ %d pushed  ❌ %d failed  ⏭ %d skipped",
# # # #              result["pushed"], result["failed"], result["skipped"])
# # # #     return result


# # # # # =============================================================================
# # # # # BACKGROUND DAEMON THREAD
# # # # # =============================================================================

# # # # def _sync_loop():
# # # #     log.info("Payment entry sync daemon started (interval=%ds).", SYNC_INTERVAL)
# # # #     while True:
# # # #         if _sync_lock.acquire(blocking=False):
# # # #             try:
# # # #                 push_unsynced_payment_entries()
# # # #             except Exception as e:
# # # #                 log.error("Payment sync cycle error: %s", e)
# # # #             finally:
# # # #                 _sync_lock.release()
# # # #         else:
# # # #             log.debug("Previous payment sync still running — skipping.")
# # # #         time.sleep(SYNC_INTERVAL)


# # # # def start_payment_sync_daemon() -> threading.Thread:
# # # #     """Non-blocking — safe to call from MainWindow.__init__."""
# # # #     global _sync_thread
# # # #     if _sync_thread and _sync_thread.is_alive():
# # # #         return _sync_thread
# # # #     t = threading.Thread(target=_sync_loop, daemon=True, name="PaymentSyncDaemon")
# # # #     t.start()
# # # #     _sync_thread = t
# # # #     log.info("Payment entry sync daemon started.")
# # # #     return t


# # # # # =============================================================================
# # # # # DEBUG
# # # # # =============================================================================

# # # # if __name__ == "__main__":
# # # #     logging.basicConfig(level=logging.INFO,
# # # #                         format="%(asctime)s [%(levelname)s] %(message)s")
# # # #     print("Running one payment entry sync cycle...")
# # # #     r = push_unsynced_payment_entries()
# # # #     print(f"\nResult: {r['pushed']} pushed, {r['failed']} failed, "
# # # #           f"{r['skipped']} skipped (of {r['total']} total)")


# # # # =============================================================================
# # # # services/payment_entry_service.py
# # # #
# # # # Manages local payment_entries table and syncs them to Frappe.
# # # #
# # # # FLOW:
# # # #   1. When a sale is saved locally → create_payment_entry() stores it locally
# # # #      with synced=0
# # # #   2. When the Sales Invoice is confirmed on Frappe (frappe_ref is set) →
# # # #      push_unsynced_payment_entries() pushes the Payment Entry to Frappe
# # # #   3. Frappe returns a PAY-xxxxx ref → stored as frappe_payment_ref, synced=1
# # # #
# # # # PAYLOAD SENT TO FRAPPE:
# # # #   POST /api/resource/Payment Entry
# # # #   {
# # # #     "doctype":              "Payment Entry",
# # # #     "payment_type":         "Receive",
# # # #     "party_type":           "Customer",
# # # #     "party":                "Cathy",
# # # #     "paid_to":              "Cash ZWG - H",
# # # #     "paid_to_account_currency": "USD",
# # # #     "paid_amount":          32.45,
# # # #     "received_amount":      32.45,
# # # #     "source_exchange_rate": 1.0,
# # # #     "reference_no":         "ACC-SINV-2026-00034",
# # # #     "reference_date":       "2026-03-19",
# # # #     "remarks":              "POS Payment — Cash",
# # # #     "docstatus":            1,
# # # #     "references": [{
# # # #         "reference_doctype": "Sales Invoice",
# # # #         "reference_name":    "ACC-SINV-2026-00565",
# # # #         "allocated_amount":  32.45
# # # #     }]
# # # #   }
# # # # =============================================================================

# # # from __future__ import annotations

# # # import json
# # # import logging
# # # import time
# # # import threading
# # # import urllib.request
# # # import urllib.error
# # # from datetime import date

# # # log = logging.getLogger("PaymentEntry")

# # # SYNC_INTERVAL   = 60      # seconds between auto-sync cycles
# # # REQUEST_TIMEOUT = 30

# # # # Exchange rate cache: "FROM::TO::DATE" → float
# # # _RATE_CACHE: dict[str, float] = {}


# # # def _get_exchange_rate(from_currency: str, to_currency: str,
# # #                        transaction_date: str,
# # #                        api_key: str, api_secret: str, host: str) -> float:
# # #     """
# # #     Fetch live exchange rate from Frappe.
# # #     Returns 1.0 for same currency, 0.0 if fetch fails (Frappe uses its own rate).
# # #     """
# # #     if not from_currency or from_currency.upper() == to_currency.upper():
# # #         return 1.0

# # #     cache_key = f"{from_currency.upper()}::{to_currency.upper()}::{transaction_date}"
# # #     if cache_key in _RATE_CACHE:
# # #         return _RATE_CACHE[cache_key]

# # #     try:
# # #         import urllib.parse
# # #         url = (
# # #             f"{host}/api/method/erpnext.setup.utils.get_exchange_rate"
# # #             f"?from_currency={urllib.parse.quote(from_currency)}"
# # #             f"&to_currency={urllib.parse.quote(to_currency)}"
# # #             f"&transaction_date={transaction_date}"
# # #         )
# # #         req = urllib.request.Request(url)
# # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # #             data = json.loads(r.read().decode())
# # #             rate = float(data.get("message") or data.get("result") or 0)
# # #             if rate > 0:
# # #                 _RATE_CACHE[cache_key] = rate
# # #                 log.debug("Rate %s→%s on %s: %.6f", from_currency, to_currency, transaction_date, rate)
# # #                 return rate
# # #     except Exception as e:
# # #         log.debug("Rate fetch failed (%s→%s): %s", from_currency, to_currency, e)

# # #     return 0.0

# # # _sync_lock:   threading.Lock          = threading.Lock()
# # # _sync_thread: threading.Thread | None = None

# # # # Method → Frappe Mode of Payment name
# # # _METHOD_MAP = {
# # #     "CASH":     "Cash",
# # #     "CARD":     "Credit Card",
# # #     "C / CARD": "Credit Card",
# # #     "EFTPOS":   "Credit Card",
# # #     "CHECK":    "Cheque",
# # #     "CHEQUE":   "Cheque",
# # #     "MOBILE":   "Mobile Money",
# # #     "CREDIT":   "Credit",
# # #     "TRANSFER": "Bank Transfer",
# # # }


# # # # =============================================================================
# # # # CREDENTIALS / HOST / DEFAULTS
# # # # =============================================================================

# # # def _get_credentials() -> tuple[str, str]:
# # #     try:
# # #         from services.credentials import get_credentials
# # #         return get_credentials()
# # #     except Exception:
# # #         pass
# # #     return "", ""

# # # def _get_host() -> str:
# # #     try:
# # #         from models.company_defaults import get_defaults
# # #         host = (get_defaults() or {}).get("server_api_host", "").strip().rstrip("/")
# # #         if host:
# # #             return host
# # #     except Exception:
# # #         pass
# # #     return "https://apk.havano.cloud"


# # # def _get_defaults() -> dict:
# # #     try:
# # #         from models.company_defaults import get_defaults
# # #         return get_defaults() or {}
# # #     except Exception:
# # #         return {}


# # # # =============================================================================
# # # # GL ACCOUNT RESOLVER  (which account to credit for each payment method)
# # # # =============================================================================

# # # _ACCOUNT_CACHE: dict[str, str] = {}


# # # def _resolve_paid_to_account(mop_name: str, company: str, currency: str,
# # #                               api_key: str, api_secret: str, host: str) -> str:
# # #     """
# # #     Looks up the GL account for a Mode of Payment from Frappe.
# # #     Tries to match by currency if multiple accounts exist for the company.
# # #     Falls back to server_pos_account in company_defaults.
# # #     """
# # #     cache_key = f"{mop_name}::{company}::{currency}"
# # #     if cache_key in _ACCOUNT_CACHE:
# # #         return _ACCOUNT_CACHE[cache_key]

# # #     try:
# # #         import urllib.parse
# # #         url = (f"{host}/api/resource/Mode%20of%20Payment/"
# # #                f"{urllib.parse.quote(mop_name)}?fields=[\"accounts\"]")
# # #         req = urllib.request.Request(url)
# # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # #             data     = json.loads(r.read().decode())
# # #             accounts = (data.get("data") or {}).get("accounts", [])

# # #         company_accts = [a for a in accounts
# # #                          if not company or a.get("company") == company]

# # #         # Prefer account whose name contains the currency code
# # #         matched = ""
# # #         if currency:
# # #             for a in company_accts:
# # #                 if currency.upper() in (a.get("default_account") or "").upper():
# # #                     matched = a["default_account"]; break

# # #         if not matched and company_accts:
# # #             matched = company_accts[0].get("default_account", "")

# # #         if matched:
# # #             _ACCOUNT_CACHE[cache_key] = matched
# # #             return matched

# # #     except Exception as e:
# # #         log.debug("MOP account lookup failed for '%s': %s", mop_name, e)

# # #     # Fallback
# # #     fallback = _get_defaults().get("server_pos_account", "").strip()
# # #     if fallback:
# # #         _ACCOUNT_CACHE[cache_key] = fallback
# # #         return fallback

# # #     log.warning("No GL account for MOP '%s' currency=%s — Payment Entry may fail.",
# # #                 mop_name, currency)
# # #     return ""


# # # # =============================================================================
# # # # LOCAL DB  — create / read / update payment_entries
# # # # =============================================================================

# # # def create_payment_entry(sale: dict, override_rate: float = None,
# # #                          override_account: str = None) -> int | None:
# # #     """
# # #     Called immediately after a sale is saved locally.
# # #     Stores a payment_entry row with synced=0.
# # #     Returns the new payment_entry id, or None on error.

# # #     Will only create the entry once per sale (idempotent).
# # #     """
# # #     from database.db import get_connection
# # #     conn = get_connection(); cur = conn.cursor()

# # #     # Idempotency: don't create twice for the same sale
# # #     cur.execute("SELECT id FROM payment_entries WHERE sale_id = ?", (sale["id"],))
# # #     if cur.fetchone():
# # #         conn.close()
# # #         return None

# # #     customer   = (sale.get("customer_name") or "default").strip()
# # #     currency   = (sale.get("currency")      or "USD").strip().upper()
# # #     amount     = float(sale.get("total")    or 0)
# # #     inv_no     = sale.get("invoice_no", "")
# # #     inv_date   = sale.get("invoice_date") or date.today().isoformat()
# # #     method     = str(sale.get("method", "CASH")).upper().strip()
# # #     mop        = _METHOD_MAP.get(method, "Cash")

# # #     # Use override rate (from split) or fetch from Frappe
# # #     if override_rate is not None:
# # #         exch_rate = override_rate
# # #     else:
# # #         try:
# # #             api_key, api_secret = _get_credentials()
# # #             host = _get_host()
# # #             defaults = _get_defaults()
# # #             company_currency = defaults.get("server_company_currency", "USD").strip().upper() or "USD"
# # #             exch_rate = _get_exchange_rate(
# # #                 currency, company_currency, inv_date, api_key, api_secret, host
# # #             ) if currency != company_currency else 1.0
# # #         except Exception:
# # #             exch_rate = 1.0

# # #     cur.execute("""
# # #         INSERT INTO payment_entries (
# # #             sale_id, sale_invoice_no, frappe_invoice_ref,
# # #             party, party_name,
# # #             paid_amount, received_amount, source_exchange_rate,
# # #             paid_to_account_currency, currency,
# # #             mode_of_payment,
# # #             reference_no, reference_date,
# # #             remarks, synced
# # #         ) OUTPUT INSERTED.id
# # #         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # #     """, (
# # #         sale["id"], inv_no,
# # #         sale.get("frappe_ref") or None,
# # #         customer, customer,
# # #         amount, amount, exch_rate or 1.0,
# # #         currency, currency,
# # #         mop,
# # #         inv_no, inv_date,
# # #         f"POS Payment — {mop}",
# # #     ))
# # #     new_id = int(cur.fetchone()[0])
# # #     conn.commit(); conn.close()
# # #     log.debug("Payment entry %d created locally for sale %s", new_id, inv_no)
# # #     return new_id


# # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # #     """
# # #     Called when cashier uses Split payment.
# # #     Creates one payment_entry row per currency in splits list.
# # #     splits = [{"mode": "CASH", "currency": "USD", "amount": 5.0,
# # #                "rate": 1.0, "base_amount": 5.0, "account": "Cash - AT"}, ...]
# # #     Returns list of new payment_entry ids.
# # #     """
# # #     ids = []
# # #     for split in splits:
# # #         if not split.get("amount") or float(split["amount"]) <= 0:
# # #             continue
# # #         # Build a sale-like dict with the split's currency and amount
# # #         split_sale = dict(sale)
# # #         split_sale["currency"]      = split.get("currency", "USD")
# # #         split_sale["total"]         = float(split.get("amount", 0))
# # #         split_sale["method"]        = split.get("mode", "CASH")
# # #         # Override exchange rate from split data
# # #         new_id = create_payment_entry(
# # #             split_sale,
# # #             override_rate=float(split.get("rate", 1.0)),
# # #             override_account=split.get("account", ""),
# # #         )
# # #         if new_id:
# # #             ids.append(new_id)
# # #     return ids


# # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # #     """
# # #     Creates one payment_entry per currency from a split payment.
# # #     Groups splits by currency, sums amounts, creates one entry each.
# # #     Returns list of created payment_entry ids.
# # #     """
# # #     from datetime import date as _date

# # #     # Group by currency
# # #     by_currency: dict[str, dict] = {}
# # #     for s in splits:
# # #         curr = s.get("account_currency", "USD").upper()
# # #         if curr not in by_currency:
# # #             by_currency[curr] = {
# # #                 "currency":      curr,
# # #                 "paid_amount":   0.0,
# # #                 "base_value":    0.0,
# # #                 "rate":          s.get("rate", 1.0),
# # #                 "account_name":  s.get("account_name", ""),
# # #                 "mode":          s.get("mode", "Cash"),
# # #             }
# # #         by_currency[curr]["paid_amount"] += s.get("amount_paid", 0.0)
# # #         by_currency[curr]["base_value"]  += s.get("base_value",  0.0)

# # #     ids = []
# # #     inv_no   = sale.get("invoice_no", "")
# # #     inv_date = sale.get("invoice_date") or _date.today().isoformat()
# # #     customer = (sale.get("customer_name") or "default").strip()

# # #     from database.db import get_connection
# # #     conn = get_connection(); cur = conn.cursor()

# # #     for curr, grp in by_currency.items():
# # #         # Idempotency: skip if already exists for this sale+currency
# # #         cur.execute(
# # #             "SELECT id FROM payment_entries WHERE sale_id=? AND currency=?",
# # #             (sale["id"], curr)
# # #         )
# # #         if cur.fetchone():
# # #             continue

# # #         mop = _METHOD_MAP.get(grp["mode"].upper(), "Cash")

# # #         cur.execute("""
# # #             INSERT INTO payment_entries (
# # #                 sale_id, sale_invoice_no, frappe_invoice_ref,
# # #                 party, party_name,
# # #                 paid_amount, received_amount, source_exchange_rate,
# # #                 paid_to_account_currency, currency,
# # #                 paid_to,
# # #                 mode_of_payment,
# # #                 reference_no, reference_date,
# # #                 remarks, synced
# # #             ) OUTPUT INSERTED.id
# # #             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # #         """, (
# # #             sale["id"], inv_no,
# # #             sale.get("frappe_ref") or None,
# # #             customer, customer,
# # #             grp["paid_amount"],
# # #             grp["base_value"],
# # #             float(grp["rate"] or 1.0),
# # #             curr, curr,
# # #             grp["account_name"],
# # #             mop,
# # #             inv_no, inv_date,
# # #             f"POS Split Payment — {mop} ({curr})",
# # #         ))
# # #         new_id = int(cur.fetchone()[0])
# # #         ids.append(new_id)
# # #         log.debug("Split payment entry %d created: %s %.2f %s",
# # #                   new_id, curr, grp["paid_amount"], inv_no)

# # #     conn.commit(); conn.close()
# # #     return ids


# # # def get_unsynced_payment_entries() -> list[dict]:
# # #     """Returns payment entries that are ready to push (synced=0)."""
# # #     from database.db import get_connection, fetchall_dicts
# # #     conn = get_connection(); cur = conn.cursor()
# # #     cur.execute("""
# # #         SELECT pe.*, s.frappe_ref AS sale_frappe_ref
# # #         FROM payment_entries pe
# # #         LEFT JOIN sales s ON s.id = pe.sale_id
# # #         WHERE pe.synced = 0
# # #           AND (pe.frappe_invoice_ref IS NOT NULL
# # #                OR s.frappe_ref IS NOT NULL)
# # #         ORDER BY pe.id
# # #     """)
# # #     rows = fetchall_dicts(cur); conn.close()
# # #     return rows


# # # def mark_payment_synced(pe_id: int, frappe_payment_ref: str = "") -> None:
# # #     from database.db import get_connection
# # #     conn = get_connection(); cur = conn.cursor()
# # #     cur.execute(
# # #         "UPDATE payment_entries SET synced=1, frappe_payment_ref=? WHERE id=?",
# # #         (frappe_payment_ref or None, pe_id)
# # #     )
# # #     # Also update the sales row
# # #     cur.execute("""
# # #         UPDATE sales SET payment_entry_ref=?, payment_synced=1
# # #         WHERE id = (SELECT sale_id FROM payment_entries WHERE id=?)
# # #     """, (frappe_payment_ref or None, pe_id))
# # #     conn.commit(); conn.close()


# # # def refresh_frappe_refs() -> int:
# # #     """
# # #     For payment entries that have no frappe_invoice_ref yet, copy it from
# # #     the parent sale's frappe_ref. Call this before pushing payments.
# # #     Returns count updated.
# # #     """
# # #     from database.db import get_connection
# # #     conn = get_connection(); cur = conn.cursor()
# # #     cur.execute("""
# # #         UPDATE pe
# # #         SET pe.frappe_invoice_ref = s.frappe_ref
# # #         FROM payment_entries pe
# # #         JOIN sales s ON s.id = pe.sale_id
# # #         WHERE pe.synced = 0
# # #           AND (pe.frappe_invoice_ref IS NULL OR pe.frappe_invoice_ref = '')
# # #           AND s.frappe_ref IS NOT NULL AND s.frappe_ref != ''
# # #     """)
# # #     count = cur.rowcount
# # #     conn.commit(); conn.close()
# # #     return count


# # # # =============================================================================
# # # # BUILD FRAPPE PAYLOAD
# # # # =============================================================================

# # # def _build_payload(pe: dict, defaults: dict,
# # #                    api_key: str, api_secret: str, host: str) -> dict:
# # #     company  = defaults.get("server_company", "")
# # #     currency = (pe.get("currency") or pe.get("paid_to_account_currency") or "USD").upper()
# # #     mop      = pe.get("mode_of_payment") or "Cash"
# # #     amount   = float(pe.get("paid_amount") or 0)
# # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()

# # #     # Use local gl_accounts table first (synced from Frappe)
# # #     paid_to          = (pe.get("paid_to") or "").strip()
# # #     paid_to_currency = currency
# # #     if not paid_to:
# # #         try:
# # #             from models.gl_account import get_account_for_payment
# # #             acct = get_account_for_payment(currency, company)
# # #             if acct:
# # #                 paid_to          = acct["name"]
# # #                 paid_to_currency = acct["account_currency"]
# # #         except Exception as _e:
# # #             log.debug("gl_account lookup failed: %s", _e)

# # #     # Fallback to live Frappe lookup
# # #     if not paid_to:
# # #         paid_to = _resolve_paid_to_account(mop, company, currency, api_key, api_secret, host)

# # #     # Use local exchange rate if not stored
# # #     exch_rate = float(pe.get("source_exchange_rate") or 1.0)
# # #     if exch_rate == 1.0 and currency not in ("USD", ""):
# # #         try:
# # #             from models.exchange_rate import get_rate
# # #             stored = get_rate(currency, "USD")
# # #             if stored:
# # #                 exch_rate = stored
# # #         except Exception:
# # #             pass

# # #     payload = {
# # #         "doctype":                  "Payment Entry",
# # #         "payment_type":             "Receive",
# # #         "party_type":               "Customer",
# # #         "party":                    pe.get("party") or "default",
# # #         "party_name":               pe.get("party_name") or "default",
# # #         "paid_to_account_currency": paid_to_currency,
# # #         "paid_amount":              amount,
# # #         "received_amount":          amount,
# # #         "source_exchange_rate":     exch_rate,
# # #         "reference_no":             pe.get("reference_no") or pe.get("sale_invoice_no", ""),
# # #         "reference_date":           (
# # #             pe.get("reference_date").isoformat()
# # #             if hasattr(pe.get("reference_date"), "isoformat")
# # #             else pe.get("reference_date") or date.today().isoformat()
# # #         ),
# # #         "remarks":                  pe.get("remarks") or f"POS Payment — {mop}",
# # #         "mode_of_payment":          mop,
# # #         "docstatus":                1,
# # #     }

# # #     if paid_to:
# # #         payload["paid_to"] = paid_to
# # #     if company:
# # #         payload["company"] = company

# # #     # Link to the Sales Invoice on Frappe
# # #     if frappe_inv:
# # #         payload["references"] = [{
# # #             "reference_doctype": "Sales Invoice",
# # #             "reference_name":    frappe_inv,
# # #             "allocated_amount":  amount,
# # #         }]

# # #     return payload


# # # # =============================================================================
# # # # PUSH ONE PAYMENT ENTRY
# # # # =============================================================================

# # # def _push_payment_entry(pe: dict, api_key: str, api_secret: str,
# # #                         defaults: dict, host: str) -> str | None:
# # #     """
# # #     Posts one payment entry to Frappe.
# # #     Returns Frappe's PAY-xxxxx name on success, None on failure.
# # #     """
# # #     pe_id  = pe["id"]
# # #     inv_no = pe.get("sale_invoice_no", str(pe_id))

# # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()
# # #     if not frappe_inv:
# # #         log.warning("Payment %d — Sales Invoice not yet on Frappe, skipping.", pe_id)
# # #         return None

# # #     payload = _build_payload(pe, defaults, api_key, api_secret, host)

# # #     url = f"{host}/api/resource/Payment%20Entry"
# # #     req = urllib.request.Request(
# # #         url=url,
# # #         data=json.dumps(payload, default=lambda o: o.isoformat() if hasattr(o, 'isoformat') else str(o)).encode("utf-8"),
# # #         method="POST",
# # #         headers={
# # #             "Content-Type":  "application/json",
# # #             "Accept":        "application/json",
# # #             "Authorization": f"token {api_key}:{api_secret}",
# # #         },
# # #     )

# # #     try:
# # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
# # #             data = json.loads(resp.read().decode())
# # #             name = (data.get("data") or {}).get("name", "")
# # #             log.info("✅ Payment Entry %d → Frappe %s  [%s  %s %.2f]",
# # #                      pe_id, name, inv_no,
# # #                      pe.get("currency", ""), float(pe.get("paid_amount", 0)))
# # #             return name or "SYNCED"

# # #     except urllib.error.HTTPError as e:
# # #         try:
# # #             err = json.loads(e.read().decode())
# # #             msg = (err.get("exception") or err.get("message") or
# # #                    str(err.get("_server_messages", "")) or f"HTTP {e.code}")
# # #         except Exception:
# # #             msg = f"HTTP {e.code}"

# # #         if e.code == 409:
# # #             log.info("Payment %d already on Frappe (409) - marking synced.", pe_id)
# # #             return "DUPLICATE"

# # #         # Invoice already paid (is_pos:1 on old invoices) - stop retrying
# # #         if e.code == 417:
# # #             _perma = ("already been fully paid", "already paid", "fully paid")
# # #             if any(p in msg.lower() for p in _perma):
# # #                 log.info("Payment %d - invoice already paid on Frappe, marking synced.", pe_id)
# # #                 return "ALREADY_PAID"

# # #         log.error("FAIL Payment Entry %d  HTTP %s: %s", pe_id, e.code, msg)
# # #         return None

# # #     except urllib.error.URLError as e:
# # #         log.warning("Network error pushing payment %d: %s", pe_id, e.reason)
# # #         return None

# # #     except Exception as e:
# # #         log.error("Unexpected error pushing payment %d: %s", pe_id, e)
# # #         return None


# # # # =============================================================================
# # # # PUBLIC — push all unsynced payment entries
# # # # =============================================================================

# # # def push_unsynced_payment_entries() -> dict:
# # #     """
# # #     1. Refresh frappe_invoice_ref from parent sales that were confirmed.
# # #     2. Push each unsynced payment entry to Frappe.
# # #     3. Mark synced with the returned PAY-xxxxx ref.
# # #     """
# # #     result = {"pushed": 0, "failed": 0, "skipped": 0, "total": 0}

# # #     api_key, api_secret = _get_credentials()
# # #     if not api_key or not api_secret:
# # #         log.warning("No credentials — skipping payment entry sync.")
# # #         return result

# # #     host     = _get_host()
# # #     defaults = _get_defaults()

# # #     # First: pull frappe_refs from confirmed invoices into pending payment entries
# # #     updated = refresh_frappe_refs()
# # #     if updated:
# # #         log.info("Refreshed frappe_invoice_ref on %d payment entry(ies).", updated)

# # #     entries = get_unsynced_payment_entries()
# # #     result["total"] = len(entries)

# # #     if not entries:
# # #         log.debug("No unsynced payment entries.")
# # #         return result

# # #     log.info("Pushing %d payment entry(ies) to Frappe…", len(entries))

# # #     for pe in entries:
# # #         frappe_name = _push_payment_entry(pe, api_key, api_secret, defaults, host)
# # #         if frappe_name:
# # #             mark_payment_synced(pe["id"], frappe_name)
# # #             result["pushed"] += 1
# # #         elif frappe_name is None:
# # #             # None = permanent skip (no frappe_inv yet), not a real failure
# # #             result["skipped"] += 1
# # #         else:
# # #             result["failed"] += 1

# # #         time.sleep(3)   # rate limit — 20/min max

# # #     log.info("Payment sync done — ✅ %d pushed  ❌ %d failed  ⏭ %d skipped",
# # #              result["pushed"], result["failed"], result["skipped"])
# # #     return result


# # # # =============================================================================
# # # # BACKGROUND DAEMON THREAD
# # # # =============================================================================

# # # def _sync_loop():
# # #     log.info("Payment entry sync daemon started (interval=%ds).", SYNC_INTERVAL)
# # #     while True:
# # #         if _sync_lock.acquire(blocking=False):
# # #             try:
# # #                 push_unsynced_payment_entries()
# # #             except Exception as e:
# # #                 log.error("Payment sync cycle error: %s", e)
# # #             finally:
# # #                 _sync_lock.release()
# # #         else:
# # #             log.debug("Previous payment sync still running — skipping.")
# # #         time.sleep(SYNC_INTERVAL)


# # # def start_payment_sync_daemon() -> threading.Thread:
# # #     """Non-blocking — safe to call from MainWindow.__init__."""
# # #     global _sync_thread
# # #     if _sync_thread and _sync_thread.is_alive():
# # #         return _sync_thread
# # #     t = threading.Thread(target=_sync_loop, daemon=True, name="PaymentSyncDaemon")
# # #     t.start()
# # #     _sync_thread = t
# # #     log.info("Payment entry sync daemon started.")
# # #     return t


# # # # =============================================================================
# # # # DEBUG
# # # # =============================================================================

# # # if __name__ == "__main__":
# # #     logging.basicConfig(level=logging.INFO,
# # #                         format="%(asctime)s [%(levelname)s] %(message)s")
# # #     print("Running one payment entry sync cycle...")
# # #     r = push_unsynced_payment_entries()
# # #     print(f"\nResult: {r['pushed']} pushed, {r['failed']} failed, "
# # #           f"{r['skipped']} skipped (of {r['total']} total)")


# # # # # # # =============================================================================
# # # # # # # services/payment_entry_service.py
# # # # # # #
# # # # # # # Manages local payment_entries table and syncs them to Frappe.
# # # # # # #
# # # # # # # FLOW:
# # # # # # #   1. When a sale is saved locally → create_payment_entry() stores it locally
# # # # # # #      with synced=0
# # # # # # #   2. When the Sales Invoice is confirmed on Frappe (frappe_ref is set) →
# # # # # # #      push_unsynced_payment_entries() pushes the Payment Entry to Frappe
# # # # # # #   3. Frappe returns a PAY-xxxxx ref → stored as frappe_payment_ref, synced=1
# # # # # # #
# # # # # # # PAYLOAD SENT TO FRAPPE:
# # # # # # #   POST /api/resource/Payment Entry
# # # # # # #   {
# # # # # # #     "doctype":              "Payment Entry",
# # # # # # #     "payment_type":         "Receive",
# # # # # # #     "party_type":           "Customer",
# # # # # # #     "party":                "Cathy",
# # # # # # #     "paid_to":              "Cash ZWG - H",
# # # # # # #     "paid_to_account_currency": "USD",
# # # # # # #     "paid_amount":          32.45,
# # # # # # #     "received_amount":      32.45,
# # # # # # #     "source_exchange_rate": 1.0,
# # # # # # #     "reference_no":         "ACC-SINV-2026-00034",
# # # # # # #     "reference_date":       "2026-03-19",
# # # # # # #     "remarks":              "POS Payment — Cash",
# # # # # # #     "docstatus":            1,
# # # # # # #     "references": [{
# # # # # # #         "reference_doctype": "Sales Invoice",
# # # # # # #         "reference_name":    "ACC-SINV-2026-00565",
# # # # # # #         "allocated_amount":  32.45
# # # # # # #     }]
# # # # # # #   }
# # # # # # # =============================================================================

# # # # # # from __future__ import annotations

# # # # # # import json
# # # # # # import logging
# # # # # # import time
# # # # # # import threading
# # # # # # import urllib.request
# # # # # # import urllib.error
# # # # # # from datetime import date

# # # # # # log = logging.getLogger("PaymentEntry")

# # # # # # SYNC_INTERVAL   = 60      # seconds between auto-sync cycles
# # # # # # REQUEST_TIMEOUT = 30

# # # # # # # Exchange rate cache: "FROM::TO::DATE" → float
# # # # # # _RATE_CACHE: dict[str, float] = {}


# # # # # # def _get_exchange_rate(from_currency: str, to_currency: str,
# # # # # #                        transaction_date: str,
# # # # # #                        api_key: str, api_secret: str, host: str) -> float:
# # # # # #     """
# # # # # #     Fetch live exchange rate from Frappe.
# # # # # #     Returns 1.0 for same currency, 0.0 if fetch fails (Frappe uses its own rate).
# # # # # #     """
# # # # # #     if not from_currency or from_currency.upper() == to_currency.upper():
# # # # # #         return 1.0

# # # # # #     cache_key = f"{from_currency.upper()}::{to_currency.upper()}::{transaction_date}"
# # # # # #     if cache_key in _RATE_CACHE:
# # # # # #         return _RATE_CACHE[cache_key]

# # # # # #     try:
# # # # # #         import urllib.parse
# # # # # #         url = (
# # # # # #             f"{host}/api/method/erpnext.setup.utils.get_exchange_rate"
# # # # # #             f"?from_currency={urllib.parse.quote(from_currency)}"
# # # # # #             f"&to_currency={urllib.parse.quote(to_currency)}"
# # # # # #             f"&transaction_date={transaction_date}"
# # # # # #         )
# # # # # #         req = urllib.request.Request(url)
# # # # # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # # # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # # # # #             data = json.loads(r.read().decode())
# # # # # #             rate = float(data.get("message") or data.get("result") or 0)
# # # # # #             if rate > 0:
# # # # # #                 _RATE_CACHE[cache_key] = rate
# # # # # #                 log.debug("Rate %s→%s on %s: %.6f", from_currency, to_currency, transaction_date, rate)
# # # # # #                 return rate
# # # # # #     except Exception as e:
# # # # # #         log.debug("Rate fetch failed (%s→%s): %s", from_currency, to_currency, e)

# # # # # #     return 0.0

# # # # # # _sync_lock:   threading.Lock          = threading.Lock()
# # # # # # _sync_thread: threading.Thread | None = None

# # # # # # # Method → Frappe Mode of Payment name
# # # # # # _METHOD_MAP = {
# # # # # #     "CASH":     "Cash",
# # # # # #     "CARD":     "Credit Card",
# # # # # #     "C / CARD": "Credit Card",
# # # # # #     "EFTPOS":   "Credit Card",
# # # # # #     "CHECK":    "Cheque",
# # # # # #     "CHEQUE":   "Cheque",
# # # # # #     "MOBILE":   "Mobile Money",
# # # # # #     "CREDIT":   "Credit",
# # # # # #     "TRANSFER": "Bank Transfer",
# # # # # # }


# # # # # # # =============================================================================
# # # # # # # CREDENTIALS / HOST / DEFAULTS
# # # # # # # =============================================================================

# # # # # # def _get_credentials() -> tuple[str, str]:
# # # # # #     try:
# # # # # #         from services.auth_service import get_session
# # # # # #         s = get_session()
# # # # # #         if s.get("api_key") and s.get("api_secret"):
# # # # # #             return s["api_key"], s["api_secret"]
# # # # # #     except Exception:
# # # # # #         pass
# # # # # #     try:
# # # # # #         from database.db import get_connection
# # # # # #         conn = get_connection(); cur = conn.cursor()
# # # # # #         cur.execute("SELECT api_key, api_secret FROM company_defaults WHERE id = 1")
# # # # # #         row = cur.fetchone(); conn.close()
# # # # # #         if row and row[0] and row[1]:
# # # # # #             return row[0], row[1]
# # # # # #     except Exception:
# # # # # #         pass
# # # # # #     import os
# # # # # #     return os.environ.get("HAVANO_API_KEY", ""), os.environ.get("HAVANO_API_SECRET", "")


# # # # # # def _get_host() -> str:
# # # # # #     try:
# # # # # #         from models.company_defaults import get_defaults
# # # # # #         host = (get_defaults() or {}).get("server_api_host", "").strip().rstrip("/")
# # # # # #         if host:
# # # # # #             return host
# # # # # #     except Exception:
# # # # # #         pass
# # # # # #     return "https://apk.havano.cloud"


# # # # # # def _get_defaults() -> dict:
# # # # # #     try:
# # # # # #         from models.company_defaults import get_defaults
# # # # # #         return get_defaults() or {}
# # # # # #     except Exception:
# # # # # #         return {}


# # # # # # # =============================================================================
# # # # # # # GL ACCOUNT RESOLVER  (which account to credit for each payment method)
# # # # # # # =============================================================================

# # # # # # _ACCOUNT_CACHE: dict[str, str] = {}


# # # # # # def _resolve_paid_to_account(mop_name: str, company: str, currency: str,
# # # # # #                               api_key: str, api_secret: str, host: str) -> str:
# # # # # #     """
# # # # # #     Looks up the GL account for a Mode of Payment from Frappe.
# # # # # #     Tries to match by currency if multiple accounts exist for the company.
# # # # # #     Falls back to server_pos_account in company_defaults.
# # # # # #     """
# # # # # #     cache_key = f"{mop_name}::{company}::{currency}"
# # # # # #     if cache_key in _ACCOUNT_CACHE:
# # # # # #         return _ACCOUNT_CACHE[cache_key]

# # # # # #     try:
# # # # # #         import urllib.parse
# # # # # #         url = (f"{host}/api/resource/Mode%20of%20Payment/"
# # # # # #                f"{urllib.parse.quote(mop_name)}?fields=[\"accounts\"]")
# # # # # #         req = urllib.request.Request(url)
# # # # # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # # # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # # # # #             data     = json.loads(r.read().decode())
# # # # # #             accounts = (data.get("data") or {}).get("accounts", [])

# # # # # #         company_accts = [a for a in accounts
# # # # # #                          if not company or a.get("company") == company]

# # # # # #         # Prefer account whose name contains the currency code
# # # # # #         matched = ""
# # # # # #         if currency:
# # # # # #             for a in company_accts:
# # # # # #                 if currency.upper() in (a.get("default_account") or "").upper():
# # # # # #                     matched = a["default_account"]; break

# # # # # #         if not matched and company_accts:
# # # # # #             matched = company_accts[0].get("default_account", "")

# # # # # #         if matched:
# # # # # #             _ACCOUNT_CACHE[cache_key] = matched
# # # # # #             return matched

# # # # # #     except Exception as e:
# # # # # #         log.debug("MOP account lookup failed for '%s': %s", mop_name, e)

# # # # # #     # Fallback
# # # # # #     fallback = _get_defaults().get("server_pos_account", "").strip()
# # # # # #     if fallback:
# # # # # #         _ACCOUNT_CACHE[cache_key] = fallback
# # # # # #         return fallback

# # # # # #     log.warning("No GL account for MOP '%s' currency=%s — Payment Entry may fail.",
# # # # # #                 mop_name, currency)
# # # # # #     return ""


# # # # # # # =============================================================================
# # # # # # # LOCAL DB  — create / read / update payment_entries
# # # # # # # =============================================================================

# # # # # # def create_payment_entry(sale: dict, override_rate: float = None,
# # # # # #                          override_account: str = None) -> int | None:
# # # # # #     """
# # # # # #     Called immediately after a sale is saved locally.
# # # # # #     Stores a payment_entry row with synced=0.
# # # # # #     Returns the new payment_entry id, or None on error.

# # # # # #     Will only create the entry once per sale (idempotent).
# # # # # #     """
# # # # # #     from database.db import get_connection
# # # # # #     conn = get_connection(); cur = conn.cursor()

# # # # # #     # Idempotency: don't create twice for the same sale
# # # # # #     cur.execute("SELECT id FROM payment_entries WHERE sale_id = ?", (sale["id"],))
# # # # # #     if cur.fetchone():
# # # # # #         conn.close()
# # # # # #         return None

# # # # # #     customer   = (sale.get("customer_name") or "default").strip()
# # # # # #     currency   = (sale.get("currency")      or "USD").strip().upper()
# # # # # #     amount     = float(sale.get("total")    or 0)
# # # # # #     inv_no     = sale.get("invoice_no", "")
# # # # # #     inv_date   = sale.get("invoice_date") or date.today().isoformat()
# # # # # #     method     = str(sale.get("method", "CASH")).upper().strip()
# # # # # #     mop        = _METHOD_MAP.get(method, "Cash")

# # # # # #     # Use override rate (from split) or fetch from Frappe
# # # # # #     if override_rate is not None:
# # # # # #         exch_rate = override_rate
# # # # # #     else:
# # # # # #         try:
# # # # # #             api_key, api_secret = _get_credentials()
# # # # # #             host = _get_host()
# # # # # #             defaults = _get_defaults()
# # # # # #             company_currency = defaults.get("server_company_currency", "USD").strip().upper() or "USD"
# # # # # #             exch_rate = _get_exchange_rate(
# # # # # #                 currency, company_currency, inv_date, api_key, api_secret, host
# # # # # #             ) if currency != company_currency else 1.0
# # # # # #         except Exception:
# # # # # #             exch_rate = 1.0

# # # # # #     cur.execute("""
# # # # # #         INSERT INTO payment_entries (
# # # # # #             sale_id, sale_invoice_no, frappe_invoice_ref,
# # # # # #             party, party_name,
# # # # # #             paid_amount, received_amount, source_exchange_rate,
# # # # # #             paid_to_account_currency, currency,
# # # # # #             mode_of_payment,
# # # # # #             reference_no, reference_date,
# # # # # #             remarks, synced
# # # # # #         ) OUTPUT INSERTED.id
# # # # # #         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # # # # #     """, (
# # # # # #         sale["id"], inv_no,
# # # # # #         sale.get("frappe_ref") or None,
# # # # # #         customer, customer,
# # # # # #         amount, amount, exch_rate or 1.0,
# # # # # #         currency, currency,
# # # # # #         mop,
# # # # # #         inv_no, inv_date,
# # # # # #         f"POS Payment — {mop}",
# # # # # #     ))
# # # # # #     new_id = int(cur.fetchone()[0])
# # # # # #     conn.commit(); conn.close()
# # # # # #     log.debug("Payment entry %d created locally for sale %s", new_id, inv_no)
# # # # # #     return new_id


# # # # # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # # # # #     """
# # # # # #     Called when cashier uses Split payment.
# # # # # #     Creates one payment_entry row per currency in splits list.
# # # # # #     splits = [{"mode": "CASH", "currency": "USD", "amount": 5.0,
# # # # # #                "rate": 1.0, "base_amount": 5.0, "account": "Cash - AT"}, ...]
# # # # # #     Returns list of new payment_entry ids.
# # # # # #     """
# # # # # #     ids = []
# # # # # #     for split in splits:
# # # # # #         if not split.get("amount") or float(split["amount"]) <= 0:
# # # # # #             continue
# # # # # #         # Build a sale-like dict with the split's currency and amount
# # # # # #         split_sale = dict(sale)
# # # # # #         split_sale["currency"]      = split.get("currency", "USD")
# # # # # #         split_sale["total"]         = float(split.get("amount", 0))
# # # # # #         split_sale["method"]        = split.get("mode", "CASH")
# # # # # #         # Override exchange rate from split data
# # # # # #         new_id = create_payment_entry(
# # # # # #             split_sale,
# # # # # #             override_rate=float(split.get("rate", 1.0)),
# # # # # #             override_account=split.get("account", ""),
# # # # # #         )
# # # # # #         if new_id:
# # # # # #             ids.append(new_id)
# # # # # #     return ids


# # # # # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # # # # #     """
# # # # # #     Creates one payment_entry per currency from a split payment.
# # # # # #     Groups splits by currency, sums amounts, creates one entry each.
# # # # # #     Returns list of created payment_entry ids.
# # # # # #     """
# # # # # #     from datetime import date as _date

# # # # # #     # Group by currency
# # # # # #     by_currency: dict[str, dict] = {}
# # # # # #     for s in splits:
# # # # # #         curr = s.get("account_currency", "USD").upper()
# # # # # #         if curr not in by_currency:
# # # # # #             by_currency[curr] = {
# # # # # #                 "currency":      curr,
# # # # # #                 "paid_amount":   0.0,
# # # # # #                 "base_value":    0.0,
# # # # # #                 "rate":          s.get("rate", 1.0),
# # # # # #                 "account_name":  s.get("account_name", ""),
# # # # # #                 "mode":          s.get("mode", "Cash"),
# # # # # #             }
# # # # # #         by_currency[curr]["paid_amount"] += s.get("amount_paid", 0.0)
# # # # # #         by_currency[curr]["base_value"]  += s.get("base_value",  0.0)

# # # # # #     ids = []
# # # # # #     inv_no   = sale.get("invoice_no", "")
# # # # # #     inv_date = sale.get("invoice_date") or _date.today().isoformat()
# # # # # #     customer = (sale.get("customer_name") or "default").strip()

# # # # # #     from database.db import get_connection
# # # # # #     conn = get_connection(); cur = conn.cursor()

# # # # # #     for curr, grp in by_currency.items():
# # # # # #         # Idempotency: skip if already exists for this sale+currency
# # # # # #         cur.execute(
# # # # # #             "SELECT id FROM payment_entries WHERE sale_id=? AND currency=?",
# # # # # #             (sale["id"], curr)
# # # # # #         )
# # # # # #         if cur.fetchone():
# # # # # #             continue

# # # # # #         mop = _METHOD_MAP.get(grp["mode"].upper(), "Cash")

# # # # # #         cur.execute("""
# # # # # #             INSERT INTO payment_entries (
# # # # # #                 sale_id, sale_invoice_no, frappe_invoice_ref,
# # # # # #                 party, party_name,
# # # # # #                 paid_amount, received_amount, source_exchange_rate,
# # # # # #                 paid_to_account_currency, currency,
# # # # # #                 paid_to,
# # # # # #                 mode_of_payment,
# # # # # #                 reference_no, reference_date,
# # # # # #                 remarks, synced
# # # # # #             ) OUTPUT INSERTED.id
# # # # # #             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # # # # #         """, (
# # # # # #             sale["id"], inv_no,
# # # # # #             sale.get("frappe_ref") or None,
# # # # # #             customer, customer,
# # # # # #             grp["paid_amount"],
# # # # # #             grp["base_value"],
# # # # # #             float(grp["rate"] or 1.0),
# # # # # #             curr, curr,
# # # # # #             grp["account_name"],
# # # # # #             mop,
# # # # # #             inv_no, inv_date,
# # # # # #             f"POS Split Payment — {mop} ({curr})",
# # # # # #         ))
# # # # # #         new_id = int(cur.fetchone()[0])
# # # # # #         ids.append(new_id)
# # # # # #         log.debug("Split payment entry %d created: %s %.2f %s",
# # # # # #                   new_id, curr, grp["paid_amount"], inv_no)

# # # # # #     conn.commit(); conn.close()
# # # # # #     return ids


# # # # # # def get_unsynced_payment_entries() -> list[dict]:
# # # # # #     """Returns payment entries that are ready to push (synced=0)."""
# # # # # #     from database.db import get_connection, fetchall_dicts
# # # # # #     conn = get_connection(); cur = conn.cursor()
# # # # # #     cur.execute("""
# # # # # #         SELECT pe.*, s.frappe_ref AS sale_frappe_ref
# # # # # #         FROM payment_entries pe
# # # # # #         LEFT JOIN sales s ON s.id = pe.sale_id
# # # # # #         WHERE pe.synced = 0
# # # # # #           AND (pe.frappe_invoice_ref IS NOT NULL
# # # # # #                OR s.frappe_ref IS NOT NULL)
# # # # # #         ORDER BY pe.id
# # # # # #     """)
# # # # # #     rows = fetchall_dicts(cur); conn.close()
# # # # # #     return rows


# # # # # # def mark_payment_synced(pe_id: int, frappe_payment_ref: str = "") -> None:
# # # # # #     from database.db import get_connection
# # # # # #     conn = get_connection(); cur = conn.cursor()
# # # # # #     cur.execute(
# # # # # #         "UPDATE payment_entries SET synced=1, frappe_payment_ref=? WHERE id=?",
# # # # # #         (frappe_payment_ref or None, pe_id)
# # # # # #     )
# # # # # #     # Also update the sales row
# # # # # #     cur.execute("""
# # # # # #         UPDATE sales SET payment_entry_ref=?, payment_synced=1
# # # # # #         WHERE id = (SELECT sale_id FROM payment_entries WHERE id=?)
# # # # # #     """, (frappe_payment_ref or None, pe_id))
# # # # # #     conn.commit(); conn.close()


# # # # # # def refresh_frappe_refs() -> int:
# # # # # #     """
# # # # # #     For payment entries that have no frappe_invoice_ref yet, copy it from
# # # # # #     the parent sale's frappe_ref. Call this before pushing payments.
# # # # # #     Returns count updated.
# # # # # #     """
# # # # # #     from database.db import get_connection
# # # # # #     conn = get_connection(); cur = conn.cursor()
# # # # # #     cur.execute("""
# # # # # #         UPDATE pe
# # # # # #         SET pe.frappe_invoice_ref = s.frappe_ref
# # # # # #         FROM payment_entries pe
# # # # # #         JOIN sales s ON s.id = pe.sale_id
# # # # # #         WHERE pe.synced = 0
# # # # # #           AND (pe.frappe_invoice_ref IS NULL OR pe.frappe_invoice_ref = '')
# # # # # #           AND s.frappe_ref IS NOT NULL AND s.frappe_ref != ''
# # # # # #     """)
# # # # # #     count = cur.rowcount
# # # # # #     conn.commit(); conn.close()
# # # # # #     return count


# # # # # # # =============================================================================
# # # # # # # BUILD FRAPPE PAYLOAD
# # # # # # # =============================================================================

# # # # # # def _build_payload(pe: dict, defaults: dict,
# # # # # #                    api_key: str, api_secret: str, host: str) -> dict:
# # # # # #     company  = defaults.get("server_company", "")
# # # # # #     currency = (pe.get("currency") or pe.get("paid_to_account_currency") or "USD").upper()
# # # # # #     mop      = pe.get("mode_of_payment") or "Cash"
# # # # # #     amount   = float(pe.get("paid_amount") or 0)
# # # # # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()

# # # # # #     paid_to = _resolve_paid_to_account(mop, company, currency, api_key, api_secret, host)

# # # # # #     payload = {
# # # # # #         "doctype":                  "Payment Entry",
# # # # # #         "payment_type":             "Receive",
# # # # # #         "party_type":               "Customer",
# # # # # #         "party":                    pe.get("party") or "default",
# # # # # #         "party_name":               pe.get("party_name") or "default",
# # # # # #         "paid_to_account_currency": currency,
# # # # # #         "paid_amount":              amount,
# # # # # #         "received_amount":          amount,
# # # # # #         "source_exchange_rate":     float(pe.get("source_exchange_rate") or 1.0),
# # # # # #         "reference_no":             pe.get("reference_no") or pe.get("sale_invoice_no", ""),
# # # # # #         "reference_date":           pe.get("reference_date") or date.today().isoformat(),
# # # # # #         "remarks":                  pe.get("remarks") or f"POS Payment — {mop}",
# # # # # #         "mode_of_payment":          mop,
# # # # # #         "docstatus":                1,
# # # # # #     }

# # # # # #     if paid_to:
# # # # # #         payload["paid_to"] = paid_to
# # # # # #     if company:
# # # # # #         payload["company"] = company

# # # # # #     # Link to the Sales Invoice on Frappe
# # # # # #     if frappe_inv:
# # # # # #         payload["references"] = [{
# # # # # #             "reference_doctype": "Sales Invoice",
# # # # # #             "reference_name":    frappe_inv,
# # # # # #             "allocated_amount":  amount,
# # # # # #         }]

# # # # # #     return payload


# # # # # # # =============================================================================
# # # # # # # PUSH ONE PAYMENT ENTRY
# # # # # # # =============================================================================

# # # # # # def _push_payment_entry(pe: dict, api_key: str, api_secret: str,
# # # # # #                         defaults: dict, host: str) -> str | None:
# # # # # #     """
# # # # # #     Posts one payment entry to Frappe.
# # # # # #     Returns Frappe's PAY-xxxxx name on success, None on failure.
# # # # # #     """
# # # # # #     pe_id  = pe["id"]
# # # # # #     inv_no = pe.get("sale_invoice_no", str(pe_id))

# # # # # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()
# # # # # #     if not frappe_inv:
# # # # # #         log.warning("Payment %d — Sales Invoice not yet on Frappe, skipping.", pe_id)
# # # # # #         return None

# # # # # #     payload = _build_payload(pe, defaults, api_key, api_secret, host)

# # # # # #     url = f"{host}/api/resource/Payment%20Entry"
# # # # # #     req = urllib.request.Request(
# # # # # #         url=url,
# # # # # #         data=json.dumps(payload).encode("utf-8"),
# # # # # #         method="POST",
# # # # # #         headers={
# # # # # #             "Content-Type":  "application/json",
# # # # # #             "Accept":        "application/json",
# # # # # #             "Authorization": f"token {api_key}:{api_secret}",
# # # # # #         },
# # # # # #     )

# # # # # #     try:
# # # # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
# # # # # #             data = json.loads(resp.read().decode())
# # # # # #             name = (data.get("data") or {}).get("name", "")
# # # # # #             log.info("✅ Payment Entry %d → Frappe %s  [%s  %s %.2f]",
# # # # # #                      pe_id, name, inv_no,
# # # # # #                      pe.get("currency", ""), float(pe.get("paid_amount", 0)))
# # # # # #             return name or "SYNCED"

# # # # # #     except urllib.error.HTTPError as e:
# # # # # #         try:
# # # # # #             err = json.loads(e.read().decode())
# # # # # #             msg = (err.get("exception") or err.get("message") or
# # # # # #                    str(err.get("_server_messages", "")) or f"HTTP {e.code}")
# # # # # #         except Exception:
# # # # # #             msg = f"HTTP {e.code}"

# # # # # #         if e.code == 409:
# # # # # #             log.info("Payment %d already on Frappe (409) — marking synced.", pe_id)
# # # # # #             return "DUPLICATE"

# # # # # #         log.error("❌ Payment Entry %d  HTTP %s: %s", pe_id, e.code, msg)
# # # # # #         return None

# # # # # #     except urllib.error.URLError as e:
# # # # # #         log.warning("Network error pushing payment %d: %s", pe_id, e.reason)
# # # # # #         return None

# # # # # #     except Exception as e:
# # # # # #         log.error("Unexpected error pushing payment %d: %s", pe_id, e)
# # # # # #         return None


# # # # # # # =============================================================================
# # # # # # # PUBLIC — push all unsynced payment entries
# # # # # # # =============================================================================

# # # # # # def push_unsynced_payment_entries() -> dict:
# # # # # #     """
# # # # # #     1. Refresh frappe_invoice_ref from parent sales that were confirmed.
# # # # # #     2. Push each unsynced payment entry to Frappe.
# # # # # #     3. Mark synced with the returned PAY-xxxxx ref.
# # # # # #     """
# # # # # #     result = {"pushed": 0, "failed": 0, "skipped": 0, "total": 0}

# # # # # #     api_key, api_secret = _get_credentials()
# # # # # #     if not api_key or not api_secret:
# # # # # #         log.warning("No credentials — skipping payment entry sync.")
# # # # # #         return result

# # # # # #     host     = _get_host()
# # # # # #     defaults = _get_defaults()

# # # # # #     # First: pull frappe_refs from confirmed invoices into pending payment entries
# # # # # #     updated = refresh_frappe_refs()
# # # # # #     if updated:
# # # # # #         log.info("Refreshed frappe_invoice_ref on %d payment entry(ies).", updated)

# # # # # #     entries = get_unsynced_payment_entries()
# # # # # #     result["total"] = len(entries)

# # # # # #     if not entries:
# # # # # #         log.debug("No unsynced payment entries.")
# # # # # #         return result

# # # # # #     log.info("Pushing %d payment entry(ies) to Frappe…", len(entries))

# # # # # #     for pe in entries:
# # # # # #         frappe_name = _push_payment_entry(pe, api_key, api_secret, defaults, host)
# # # # # #         if frappe_name:
# # # # # #             mark_payment_synced(pe["id"], frappe_name)
# # # # # #             result["pushed"] += 1
# # # # # #         elif frappe_name is None:
# # # # # #             # None = permanent skip (no frappe_inv yet), not a real failure
# # # # # #             result["skipped"] += 1
# # # # # #         else:
# # # # # #             result["failed"] += 1

# # # # # #         time.sleep(3)   # rate limit — 20/min max

# # # # # #     log.info("Payment sync done — ✅ %d pushed  ❌ %d failed  ⏭ %d skipped",
# # # # # #              result["pushed"], result["failed"], result["skipped"])
# # # # # #     return result


# # # # # # # =============================================================================
# # # # # # # BACKGROUND DAEMON THREAD
# # # # # # # =============================================================================

# # # # # # def _sync_loop():
# # # # # #     log.info("Payment entry sync daemon started (interval=%ds).", SYNC_INTERVAL)
# # # # # #     while True:
# # # # # #         if _sync_lock.acquire(blocking=False):
# # # # # #             try:
# # # # # #                 push_unsynced_payment_entries()
# # # # # #             except Exception as e:
# # # # # #                 log.error("Payment sync cycle error: %s", e)
# # # # # #             finally:
# # # # # #                 _sync_lock.release()
# # # # # #         else:
# # # # # #             log.debug("Previous payment sync still running — skipping.")
# # # # # #         time.sleep(SYNC_INTERVAL)


# # # # # # def start_payment_sync_daemon() -> threading.Thread:
# # # # # #     """Non-blocking — safe to call from MainWindow.__init__."""
# # # # # #     global _sync_thread
# # # # # #     if _sync_thread and _sync_thread.is_alive():
# # # # # #         return _sync_thread
# # # # # #     t = threading.Thread(target=_sync_loop, daemon=True, name="PaymentSyncDaemon")
# # # # # #     t.start()
# # # # # #     _sync_thread = t
# # # # # #     log.info("Payment entry sync daemon started.")
# # # # # #     return t


# # # # # # # =============================================================================
# # # # # # # DEBUG
# # # # # # # =============================================================================

# # # # # # if __name__ == "__main__":
# # # # # #     logging.basicConfig(level=logging.INFO,
# # # # # #                         format="%(asctime)s [%(levelname)s] %(message)s")
# # # # # #     print("Running one payment entry sync cycle...")
# # # # # #     r = push_unsynced_payment_entries()
# # # # # #     print(f"\nResult: {r['pushed']} pushed, {r['failed']} failed, "
# # # # # #           f"{r['skipped']} skipped (of {r['total']} total)")
# # # # # # =============================================================================
# # # # # # services/payment_entry_service.py
# # # # # #
# # # # # # Manages local payment_entries table and syncs them to Frappe.
# # # # # #
# # # # # # FLOW:
# # # # # #   1. When a sale is saved locally → create_payment_entry() stores it locally
# # # # # #      with synced=0
# # # # # #   2. When the Sales Invoice is confirmed on Frappe (frappe_ref is set) →
# # # # # #      push_unsynced_payment_entries() pushes the Payment Entry to Frappe
# # # # # #   3. Frappe returns a PAY-xxxxx ref → stored as frappe_payment_ref, synced=1
# # # # # #
# # # # # # PAYLOAD SENT TO FRAPPE:
# # # # # #   POST /api/resource/Payment Entry
# # # # # #   {
# # # # # #     "doctype":              "Payment Entry",
# # # # # #     "payment_type":         "Receive",
# # # # # #     "party_type":           "Customer",
# # # # # #     "party":                "Cathy",
# # # # # #     "paid_to":              "Cash ZWG - H",
# # # # # #     "paid_to_account_currency": "USD",
# # # # # #     "paid_amount":          32.45,
# # # # # #     "received_amount":      32.45,
# # # # # #     "source_exchange_rate": 1.0,
# # # # # #     "reference_no":         "ACC-SINV-2026-00034",
# # # # # #     "reference_date":       "2026-03-19",
# # # # # #     "remarks":              "POS Payment — Cash",
# # # # # #     "docstatus":            1,
# # # # # #     "references": [{
# # # # # #         "reference_doctype": "Sales Invoice",
# # # # # #         "reference_name":    "ACC-SINV-2026-00565",
# # # # # #         "allocated_amount":  32.45
# # # # # #     }]
# # # # # #   }
# # # # # # =============================================================================

# # # # # from __future__ import annotations

# # # # # import json
# # # # # import logging
# # # # # import time
# # # # # import threading
# # # # # import urllib.request
# # # # # import urllib.error
# # # # # from datetime import date

# # # # # log = logging.getLogger("PaymentEntry")

# # # # # SYNC_INTERVAL   = 60      # seconds between auto-sync cycles
# # # # # REQUEST_TIMEOUT = 30

# # # # # # Exchange rate cache: "FROM::TO::DATE" → float
# # # # # _RATE_CACHE: dict[str, float] = {}


# # # # # def _get_exchange_rate(from_currency: str, to_currency: str,
# # # # #                        transaction_date: str,
# # # # #                        api_key: str, api_secret: str, host: str) -> float:
# # # # #     """
# # # # #     Fetch live exchange rate from Frappe.
# # # # #     Returns 1.0 for same currency, 0.0 if fetch fails (Frappe uses its own rate).
# # # # #     """
# # # # #     if not from_currency or from_currency.upper() == to_currency.upper():
# # # # #         return 1.0

# # # # #     cache_key = f"{from_currency.upper()}::{to_currency.upper()}::{transaction_date}"
# # # # #     if cache_key in _RATE_CACHE:
# # # # #         return _RATE_CACHE[cache_key]

# # # # #     try:
# # # # #         import urllib.parse
# # # # #         url = (
# # # # #             f"{host}/api/method/erpnext.setup.utils.get_exchange_rate"
# # # # #             f"?from_currency={urllib.parse.quote(from_currency)}"
# # # # #             f"&to_currency={urllib.parse.quote(to_currency)}"
# # # # #             f"&transaction_date={transaction_date}"
# # # # #         )
# # # # #         req = urllib.request.Request(url)
# # # # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # # # #             data = json.loads(r.read().decode())
# # # # #             rate = float(data.get("message") or data.get("result") or 0)
# # # # #             if rate > 0:
# # # # #                 _RATE_CACHE[cache_key] = rate
# # # # #                 log.debug("Rate %s→%s on %s: %.6f", from_currency, to_currency, transaction_date, rate)
# # # # #                 return rate
# # # # #     except Exception as e:
# # # # #         log.debug("Rate fetch failed (%s→%s): %s", from_currency, to_currency, e)

# # # # #     return 0.0

# # # # # _sync_lock:   threading.Lock          = threading.Lock()
# # # # # _sync_thread: threading.Thread | None = None

# # # # # # Method → Frappe Mode of Payment name
# # # # # _METHOD_MAP = {
# # # # #     "CASH":     "Cash",
# # # # #     "CARD":     "Credit Card",
# # # # #     "C / CARD": "Credit Card",
# # # # #     "EFTPOS":   "Credit Card",
# # # # #     "CHECK":    "Cheque",
# # # # #     "CHEQUE":   "Cheque",
# # # # #     "MOBILE":   "Mobile Money",
# # # # #     "CREDIT":   "Credit",
# # # # #     "TRANSFER": "Bank Transfer",
# # # # # }


# # # # # # =============================================================================
# # # # # # CREDENTIALS / HOST / DEFAULTS
# # # # # # =============================================================================

# # # # # def _get_credentials() -> tuple[str, str]:
# # # # #     try:
# # # # #         from services.auth_service import get_session
# # # # #         s = get_session()
# # # # #         if s.get("api_key") and s.get("api_secret"):
# # # # #             return s["api_key"], s["api_secret"]
# # # # #     except Exception:
# # # # #         pass
# # # # #     try:
# # # # #         from database.db import get_connection
# # # # #         conn = get_connection(); cur = conn.cursor()
# # # # #         cur.execute("SELECT api_key, api_secret FROM company_defaults WHERE id = 1")
# # # # #         row = cur.fetchone(); conn.close()
# # # # #         if row and row[0] and row[1]:
# # # # #             return row[0], row[1]
# # # # #     except Exception:
# # # # #         pass
# # # # #     import os
# # # # #     return os.environ.get("HAVANO_API_KEY", ""), os.environ.get("HAVANO_API_SECRET", "")


# # # # # def _get_host() -> str:
# # # # #     try:
# # # # #         from models.company_defaults import get_defaults
# # # # #         host = (get_defaults() or {}).get("server_api_host", "").strip().rstrip("/")
# # # # #         if host:
# # # # #             return host
# # # # #     except Exception:
# # # # #         pass
# # # # #     return "https://apk.havano.cloud"


# # # # # def _get_defaults() -> dict:
# # # # #     try:
# # # # #         from models.company_defaults import get_defaults
# # # # #         return get_defaults() or {}
# # # # #     except Exception:
# # # # #         return {}


# # # # # # =============================================================================
# # # # # # GL ACCOUNT RESOLVER  (which account to credit for each payment method)
# # # # # # =============================================================================

# # # # # _ACCOUNT_CACHE: dict[str, str] = {}


# # # # # def _resolve_paid_to_account(mop_name: str, company: str, currency: str,
# # # # #                               api_key: str, api_secret: str, host: str) -> str:
# # # # #     """
# # # # #     Looks up the GL account for a Mode of Payment from Frappe.
# # # # #     Tries to match by currency if multiple accounts exist for the company.
# # # # #     Falls back to server_pos_account in company_defaults.
# # # # #     """
# # # # #     cache_key = f"{mop_name}::{company}::{currency}"
# # # # #     if cache_key in _ACCOUNT_CACHE:
# # # # #         return _ACCOUNT_CACHE[cache_key]

# # # # #     try:
# # # # #         import urllib.parse
# # # # #         url = (f"{host}/api/resource/Mode%20of%20Payment/"
# # # # #                f"{urllib.parse.quote(mop_name)}?fields=[\"accounts\"]")
# # # # #         req = urllib.request.Request(url)
# # # # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # # # #             data     = json.loads(r.read().decode())
# # # # #             accounts = (data.get("data") or {}).get("accounts", [])

# # # # #         company_accts = [a for a in accounts
# # # # #                          if not company or a.get("company") == company]

# # # # #         # Prefer account whose name contains the currency code
# # # # #         matched = ""
# # # # #         if currency:
# # # # #             for a in company_accts:
# # # # #                 if currency.upper() in (a.get("default_account") or "").upper():
# # # # #                     matched = a["default_account"]; break

# # # # #         if not matched and company_accts:
# # # # #             matched = company_accts[0].get("default_account", "")

# # # # #         if matched:
# # # # #             _ACCOUNT_CACHE[cache_key] = matched
# # # # #             return matched

# # # # #     except Exception as e:
# # # # #         log.debug("MOP account lookup failed for '%s': %s", mop_name, e)

# # # # #     # Fallback
# # # # #     fallback = _get_defaults().get("server_pos_account", "").strip()
# # # # #     if fallback:
# # # # #         _ACCOUNT_CACHE[cache_key] = fallback
# # # # #         return fallback

# # # # #     log.warning("No GL account for MOP '%s' currency=%s — Payment Entry may fail.",
# # # # #                 mop_name, currency)
# # # # #     return ""


# # # # # # =============================================================================
# # # # # # LOCAL DB  — create / read / update payment_entries
# # # # # # =============================================================================

# # # # # def create_payment_entry(sale: dict, override_rate: float = None,
# # # # #                          override_account: str = None) -> int | None:
# # # # #     """
# # # # #     Called immediately after a sale is saved locally.
# # # # #     Stores a payment_entry row with synced=0.
# # # # #     Returns the new payment_entry id, or None on error.

# # # # #     Will only create the entry once per sale (idempotent).
# # # # #     """
# # # # #     from database.db import get_connection
# # # # #     conn = get_connection(); cur = conn.cursor()

# # # # #     # Idempotency: don't create twice for the same sale
# # # # #     cur.execute("SELECT id FROM payment_entries WHERE sale_id = ?", (sale["id"],))
# # # # #     if cur.fetchone():
# # # # #         conn.close()
# # # # #         return None

# # # # #     customer   = (sale.get("customer_name") or "default").strip()
# # # # #     currency   = (sale.get("currency")      or "USD").strip().upper()
# # # # #     amount     = float(sale.get("total")    or 0)
# # # # #     inv_no     = sale.get("invoice_no", "")
# # # # #     inv_date   = sale.get("invoice_date") or date.today().isoformat()
# # # # #     method     = str(sale.get("method", "CASH")).upper().strip()
# # # # #     mop        = _METHOD_MAP.get(method, "Cash")

# # # # #     # Use override rate (from split) or fetch from Frappe
# # # # #     if override_rate is not None:
# # # # #         exch_rate = override_rate
# # # # #     else:
# # # # #         try:
# # # # #             api_key, api_secret = _get_credentials()
# # # # #             host = _get_host()
# # # # #             defaults = _get_defaults()
# # # # #             company_currency = defaults.get("server_company_currency", "USD").strip().upper() or "USD"
# # # # #             exch_rate = _get_exchange_rate(
# # # # #                 currency, company_currency, inv_date, api_key, api_secret, host
# # # # #             ) if currency != company_currency else 1.0
# # # # #         except Exception:
# # # # #             exch_rate = 1.0

# # # # #     cur.execute("""
# # # # #         INSERT INTO payment_entries (
# # # # #             sale_id, sale_invoice_no, frappe_invoice_ref,
# # # # #             party, party_name,
# # # # #             paid_amount, received_amount, source_exchange_rate,
# # # # #             paid_to_account_currency, currency,
# # # # #             mode_of_payment,
# # # # #             reference_no, reference_date,
# # # # #             remarks, synced
# # # # #         ) OUTPUT INSERTED.id
# # # # #         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # # # #     """, (
# # # # #         sale["id"], inv_no,
# # # # #         sale.get("frappe_ref") or None,
# # # # #         customer, customer,
# # # # #         amount, amount, exch_rate or 1.0,
# # # # #         currency, currency,
# # # # #         mop,
# # # # #         inv_no, inv_date,
# # # # #         f"POS Payment — {mop}",
# # # # #     ))
# # # # #     new_id = int(cur.fetchone()[0])
# # # # #     conn.commit(); conn.close()
# # # # #     log.debug("Payment entry %d created locally for sale %s", new_id, inv_no)
# # # # #     return new_id


# # # # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # # # #     """
# # # # #     Called when cashier uses Split payment.
# # # # #     Creates one payment_entry row per currency in splits list.
# # # # #     splits = [{"mode": "CASH", "currency": "USD", "amount": 5.0,
# # # # #                "rate": 1.0, "base_amount": 5.0, "account": "Cash - AT"}, ...]
# # # # #     Returns list of new payment_entry ids.
# # # # #     """
# # # # #     ids = []
# # # # #     for split in splits:
# # # # #         if not split.get("amount") or float(split["amount"]) <= 0:
# # # # #             continue
# # # # #         # Build a sale-like dict with the split's currency and amount
# # # # #         split_sale = dict(sale)
# # # # #         split_sale["currency"]      = split.get("currency", "USD")
# # # # #         split_sale["total"]         = float(split.get("amount", 0))
# # # # #         split_sale["method"]        = split.get("mode", "CASH")
# # # # #         # Override exchange rate from split data
# # # # #         new_id = create_payment_entry(
# # # # #             split_sale,
# # # # #             override_rate=float(split.get("rate", 1.0)),
# # # # #             override_account=split.get("account", ""),
# # # # #         )
# # # # #         if new_id:
# # # # #             ids.append(new_id)
# # # # #     return ids


# # # # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # # # #     """
# # # # #     Creates one payment_entry per currency from a split payment.
# # # # #     Groups splits by currency, sums amounts, creates one entry each.
# # # # #     Returns list of created payment_entry ids.
# # # # #     """
# # # # #     from datetime import date as _date

# # # # #     # Group by currency
# # # # #     by_currency: dict[str, dict] = {}
# # # # #     for s in splits:
# # # # #         curr = s.get("account_currency", "USD").upper()
# # # # #         if curr not in by_currency:
# # # # #             by_currency[curr] = {
# # # # #                 "currency":      curr,
# # # # #                 "paid_amount":   0.0,
# # # # #                 "base_value":    0.0,
# # # # #                 "rate":          s.get("rate", 1.0),
# # # # #                 "account_name":  s.get("account_name", ""),
# # # # #                 "mode":          s.get("mode", "Cash"),
# # # # #             }
# # # # #         by_currency[curr]["paid_amount"] += s.get("amount_paid", 0.0)
# # # # #         by_currency[curr]["base_value"]  += s.get("base_value",  0.0)

# # # # #     ids = []
# # # # #     inv_no   = sale.get("invoice_no", "")
# # # # #     inv_date = sale.get("invoice_date") or _date.today().isoformat()
# # # # #     customer = (sale.get("customer_name") or "default").strip()

# # # # #     from database.db import get_connection
# # # # #     conn = get_connection(); cur = conn.cursor()

# # # # #     for curr, grp in by_currency.items():
# # # # #         # Idempotency: skip if already exists for this sale+currency
# # # # #         cur.execute(
# # # # #             "SELECT id FROM payment_entries WHERE sale_id=? AND currency=?",
# # # # #             (sale["id"], curr)
# # # # #         )
# # # # #         if cur.fetchone():
# # # # #             continue

# # # # #         mop = _METHOD_MAP.get(grp["mode"].upper(), "Cash")

# # # # #         cur.execute("""
# # # # #             INSERT INTO payment_entries (
# # # # #                 sale_id, sale_invoice_no, frappe_invoice_ref,
# # # # #                 party, party_name,
# # # # #                 paid_amount, received_amount, source_exchange_rate,
# # # # #                 paid_to_account_currency, currency,
# # # # #                 paid_to,
# # # # #                 mode_of_payment,
# # # # #                 reference_no, reference_date,
# # # # #                 remarks, synced
# # # # #             ) OUTPUT INSERTED.id
# # # # #             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # # # #         """, (
# # # # #             sale["id"], inv_no,
# # # # #             sale.get("frappe_ref") or None,
# # # # #             customer, customer,
# # # # #             grp["paid_amount"],
# # # # #             grp["base_value"],
# # # # #             float(grp["rate"] or 1.0),
# # # # #             curr, curr,
# # # # #             grp["account_name"],
# # # # #             mop,
# # # # #             inv_no, inv_date,
# # # # #             f"POS Split Payment — {mop} ({curr})",
# # # # #         ))
# # # # #         new_id = int(cur.fetchone()[0])
# # # # #         ids.append(new_id)
# # # # #         log.debug("Split payment entry %d created: %s %.2f %s",
# # # # #                   new_id, curr, grp["paid_amount"], inv_no)

# # # # #     conn.commit(); conn.close()
# # # # #     return ids


# # # # # def get_unsynced_payment_entries() -> list[dict]:
# # # # #     """Returns payment entries that are ready to push (synced=0)."""
# # # # #     from database.db import get_connection, fetchall_dicts
# # # # #     conn = get_connection(); cur = conn.cursor()
# # # # #     cur.execute("""
# # # # #         SELECT pe.*, s.frappe_ref AS sale_frappe_ref
# # # # #         FROM payment_entries pe
# # # # #         LEFT JOIN sales s ON s.id = pe.sale_id
# # # # #         WHERE pe.synced = 0
# # # # #           AND (pe.frappe_invoice_ref IS NOT NULL
# # # # #                OR s.frappe_ref IS NOT NULL)
# # # # #         ORDER BY pe.id
# # # # #     """)
# # # # #     rows = fetchall_dicts(cur); conn.close()
# # # # #     return rows


# # # # # def mark_payment_synced(pe_id: int, frappe_payment_ref: str = "") -> None:
# # # # #     from database.db import get_connection
# # # # #     conn = get_connection(); cur = conn.cursor()
# # # # #     cur.execute(
# # # # #         "UPDATE payment_entries SET synced=1, frappe_payment_ref=? WHERE id=?",
# # # # #         (frappe_payment_ref or None, pe_id)
# # # # #     )
# # # # #     # Also update the sales row
# # # # #     cur.execute("""
# # # # #         UPDATE sales SET payment_entry_ref=?, payment_synced=1
# # # # #         WHERE id = (SELECT sale_id FROM payment_entries WHERE id=?)
# # # # #     """, (frappe_payment_ref or None, pe_id))
# # # # #     conn.commit(); conn.close()


# # # # # def refresh_frappe_refs() -> int:
# # # # #     """
# # # # #     For payment entries that have no frappe_invoice_ref yet, copy it from
# # # # #     the parent sale's frappe_ref. Call this before pushing payments.
# # # # #     Returns count updated.
# # # # #     """
# # # # #     from database.db import get_connection
# # # # #     conn = get_connection(); cur = conn.cursor()
# # # # #     cur.execute("""
# # # # #         UPDATE pe
# # # # #         SET pe.frappe_invoice_ref = s.frappe_ref
# # # # #         FROM payment_entries pe
# # # # #         JOIN sales s ON s.id = pe.sale_id
# # # # #         WHERE pe.synced = 0
# # # # #           AND (pe.frappe_invoice_ref IS NULL OR pe.frappe_invoice_ref = '')
# # # # #           AND s.frappe_ref IS NOT NULL AND s.frappe_ref != ''
# # # # #     """)
# # # # #     count = cur.rowcount
# # # # #     conn.commit(); conn.close()
# # # # #     return count


# # # # # # =============================================================================
# # # # # # BUILD FRAPPE PAYLOAD
# # # # # # =============================================================================

# # # # # def _build_payload(pe: dict, defaults: dict,
# # # # #                    api_key: str, api_secret: str, host: str) -> dict:
# # # # #     company  = defaults.get("server_company", "")
# # # # #     currency = (pe.get("currency") or pe.get("paid_to_account_currency") or "USD").upper()
# # # # #     mop      = pe.get("mode_of_payment") or "Cash"
# # # # #     amount   = float(pe.get("paid_amount") or 0)
# # # # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()

# # # # #     # Use local gl_accounts table first (synced from Frappe)
# # # # #     paid_to          = (pe.get("paid_to") or "").strip()
# # # # #     paid_to_currency = currency
# # # # #     if not paid_to:
# # # # #         try:
# # # # #             from models.gl_account import get_account_for_payment
# # # # #             acct = get_account_for_payment(currency, company)
# # # # #             if acct:
# # # # #                 paid_to          = acct["name"]
# # # # #                 paid_to_currency = acct["account_currency"]
# # # # #         except Exception as _e:
# # # # #             log.debug("gl_account lookup failed: %s", _e)

# # # # #     # Fallback to live Frappe lookup
# # # # #     if not paid_to:
# # # # #         paid_to = _resolve_paid_to_account(mop, company, currency, api_key, api_secret, host)

# # # # #     # Use local exchange rate if not stored
# # # # #     exch_rate = float(pe.get("source_exchange_rate") or 1.0)
# # # # #     if exch_rate == 1.0 and currency not in ("USD", ""):
# # # # #         try:
# # # # #             from models.exchange_rate import get_rate
# # # # #             stored = get_rate(currency, "USD")
# # # # #             if stored:
# # # # #                 exch_rate = stored
# # # # #         except Exception:
# # # # #             pass

# # # # #     payload = {
# # # # #         "doctype":                  "Payment Entry",
# # # # #         "payment_type":             "Receive",
# # # # #         "party_type":               "Customer",
# # # # #         "party":                    pe.get("party") or "default",
# # # # #         "party_name":               pe.get("party_name") or "default",
# # # # #         "paid_to_account_currency": paid_to_currency,
# # # # #         "paid_amount":              amount,
# # # # #         "received_amount":          amount,
# # # # #         "source_exchange_rate":     exch_rate,
# # # # #         "reference_no":             pe.get("reference_no") or pe.get("sale_invoice_no", ""),
# # # # #         "reference_date":           pe.get("reference_date") or date.today().isoformat(),
# # # # #         "remarks":                  pe.get("remarks") or f"POS Payment — {mop}",
# # # # #         "mode_of_payment":          mop,
# # # # #         "docstatus":                1,
# # # # #     }

# # # # #     if paid_to:
# # # # #         payload["paid_to"] = paid_to
# # # # #     if company:
# # # # #         payload["company"] = company

# # # # #     # Link to the Sales Invoice on Frappe
# # # # #     if frappe_inv:
# # # # #         payload["references"] = [{
# # # # #             "reference_doctype": "Sales Invoice",
# # # # #             "reference_name":    frappe_inv,
# # # # #             "allocated_amount":  amount,
# # # # #         }]

# # # # #     return payload


# # # # # # =============================================================================
# # # # # # PUSH ONE PAYMENT ENTRY
# # # # # # =============================================================================

# # # # # def _push_payment_entry(pe: dict, api_key: str, api_secret: str,
# # # # #                         defaults: dict, host: str) -> str | None:
# # # # #     """
# # # # #     Posts one payment entry to Frappe.
# # # # #     Returns Frappe's PAY-xxxxx name on success, None on failure.
# # # # #     """
# # # # #     pe_id  = pe["id"]
# # # # #     inv_no = pe.get("sale_invoice_no", str(pe_id))

# # # # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()
# # # # #     if not frappe_inv:
# # # # #         log.warning("Payment %d — Sales Invoice not yet on Frappe, skipping.", pe_id)
# # # # #         return None

# # # # #     payload = _build_payload(pe, defaults, api_key, api_secret, host)

# # # # #     url = f"{host}/api/resource/Payment%20Entry"
# # # # #     req = urllib.request.Request(
# # # # #         url=url,
# # # # #         data=json.dumps(payload).encode("utf-8"),
# # # # #         method="POST",
# # # # #         headers={
# # # # #             "Content-Type":  "application/json",
# # # # #             "Accept":        "application/json",
# # # # #             "Authorization": f"token {api_key}:{api_secret}",
# # # # #         },
# # # # #     )

# # # # #     try:
# # # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
# # # # #             data = json.loads(resp.read().decode())
# # # # #             name = (data.get("data") or {}).get("name", "")
# # # # #             log.info("✅ Payment Entry %d → Frappe %s  [%s  %s %.2f]",
# # # # #                      pe_id, name, inv_no,
# # # # #                      pe.get("currency", ""), float(pe.get("paid_amount", 0)))
# # # # #             return name or "SYNCED"

# # # # #     except urllib.error.HTTPError as e:
# # # # #         try:
# # # # #             err = json.loads(e.read().decode())
# # # # #             msg = (err.get("exception") or err.get("message") or
# # # # #                    str(err.get("_server_messages", "")) or f"HTTP {e.code}")
# # # # #         except Exception:
# # # # #             msg = f"HTTP {e.code}"

# # # # #         if e.code == 409:
# # # # #             log.info("Payment %d already on Frappe (409) - marking synced.", pe_id)
# # # # #             return "DUPLICATE"

# # # # #         # Invoice already paid (is_pos:1 on old invoices) - stop retrying
# # # # #         if e.code == 417:
# # # # #             _perma = ("already been fully paid", "already paid", "fully paid")
# # # # #             if any(p in msg.lower() for p in _perma):
# # # # #                 log.info("Payment %d - invoice already paid on Frappe, marking synced.", pe_id)
# # # # #                 return "ALREADY_PAID"

# # # # #         log.error("FAIL Payment Entry %d  HTTP %s: %s", pe_id, e.code, msg)
# # # # #         return None

# # # # #     except urllib.error.URLError as e:
# # # # #         log.warning("Network error pushing payment %d: %s", pe_id, e.reason)
# # # # #         return None

# # # # #     except Exception as e:
# # # # #         log.error("Unexpected error pushing payment %d: %s", pe_id, e)
# # # # #         return None


# # # # # # =============================================================================
# # # # # # PUBLIC — push all unsynced payment entries
# # # # # # =============================================================================

# # # # # def push_unsynced_payment_entries() -> dict:
# # # # #     """
# # # # #     1. Refresh frappe_invoice_ref from parent sales that were confirmed.
# # # # #     2. Push each unsynced payment entry to Frappe.
# # # # #     3. Mark synced with the returned PAY-xxxxx ref.
# # # # #     """
# # # # #     result = {"pushed": 0, "failed": 0, "skipped": 0, "total": 0}

# # # # #     api_key, api_secret = _get_credentials()
# # # # #     if not api_key or not api_secret:
# # # # #         log.warning("No credentials — skipping payment entry sync.")
# # # # #         return result

# # # # #     host     = _get_host()
# # # # #     defaults = _get_defaults()

# # # # #     # First: pull frappe_refs from confirmed invoices into pending payment entries
# # # # #     updated = refresh_frappe_refs()
# # # # #     if updated:
# # # # #         log.info("Refreshed frappe_invoice_ref on %d payment entry(ies).", updated)

# # # # #     entries = get_unsynced_payment_entries()
# # # # #     result["total"] = len(entries)

# # # # #     if not entries:
# # # # #         log.debug("No unsynced payment entries.")
# # # # #         return result

# # # # #     log.info("Pushing %d payment entry(ies) to Frappe…", len(entries))

# # # # #     for pe in entries:
# # # # #         frappe_name = _push_payment_entry(pe, api_key, api_secret, defaults, host)
# # # # #         if frappe_name:
# # # # #             mark_payment_synced(pe["id"], frappe_name)
# # # # #             result["pushed"] += 1
# # # # #         elif frappe_name is None:
# # # # #             # None = permanent skip (no frappe_inv yet), not a real failure
# # # # #             result["skipped"] += 1
# # # # #         else:
# # # # #             result["failed"] += 1

# # # # #         time.sleep(3)   # rate limit — 20/min max

# # # # #     log.info("Payment sync done — ✅ %d pushed  ❌ %d failed  ⏭ %d skipped",
# # # # #              result["pushed"], result["failed"], result["skipped"])
# # # # #     return result


# # # # # # =============================================================================
# # # # # # BACKGROUND DAEMON THREAD
# # # # # # =============================================================================

# # # # # def _sync_loop():
# # # # #     log.info("Payment entry sync daemon started (interval=%ds).", SYNC_INTERVAL)
# # # # #     while True:
# # # # #         if _sync_lock.acquire(blocking=False):
# # # # #             try:
# # # # #                 push_unsynced_payment_entries()
# # # # #             except Exception as e:
# # # # #                 log.error("Payment sync cycle error: %s", e)
# # # # #             finally:
# # # # #                 _sync_lock.release()
# # # # #         else:
# # # # #             log.debug("Previous payment sync still running — skipping.")
# # # # #         time.sleep(SYNC_INTERVAL)


# # # # # def start_payment_sync_daemon() -> threading.Thread:
# # # # #     """Non-blocking — safe to call from MainWindow.__init__."""
# # # # #     global _sync_thread
# # # # #     if _sync_thread and _sync_thread.is_alive():
# # # # #         return _sync_thread
# # # # #     t = threading.Thread(target=_sync_loop, daemon=True, name="PaymentSyncDaemon")
# # # # #     t.start()
# # # # #     _sync_thread = t
# # # # #     log.info("Payment entry sync daemon started.")
# # # # #     return t


# # # # # # =============================================================================
# # # # # # DEBUG
# # # # # # =============================================================================

# # # # # if __name__ == "__main__":
# # # # #     logging.basicConfig(level=logging.INFO,
# # # # #                         format="%(asctime)s [%(levelname)s] %(message)s")
# # # # #     print("Running one payment entry sync cycle...")
# # # # #     r = push_unsynced_payment_entries()
# # # # #     print(f"\nResult: {r['pushed']} pushed, {r['failed']} failed, "
# # # # #           f"{r['skipped']} skipped (of {r['total']} total)")

# # # # # =============================================================================
# # # # # services/payment_entry_service.py
# # # # #
# # # # # Manages local payment_entries table and syncs them to Frappe.
# # # # #
# # # # # FLOW:
# # # # #   1. When a sale is saved locally → create_payment_entry() stores it locally
# # # # #      with synced=0
# # # # #   2. When the Sales Invoice is confirmed on Frappe (frappe_ref is set) →
# # # # #      push_unsynced_payment_entries() pushes the Payment Entry to Frappe
# # # # #   3. Frappe returns a PAY-xxxxx ref → stored as frappe_payment_ref, synced=1
# # # # #
# # # # # PAYLOAD SENT TO FRAPPE:
# # # # #   POST /api/resource/Payment Entry
# # # # #   {
# # # # #     "doctype":              "Payment Entry",
# # # # #     "payment_type":         "Receive",
# # # # #     "party_type":           "Customer",
# # # # #     "party":                "Cathy",
# # # # #     "paid_to":              "Cash ZWG - H",
# # # # #     "paid_to_account_currency": "USD",
# # # # #     "paid_amount":          32.45,
# # # # #     "received_amount":      32.45,
# # # # #     "source_exchange_rate": 1.0,
# # # # #     "reference_no":         "ACC-SINV-2026-00034",
# # # # #     "reference_date":       "2026-03-19",
# # # # #     "remarks":              "POS Payment — Cash",
# # # # #     "docstatus":            1,
# # # # #     "references": [{
# # # # #         "reference_doctype": "Sales Invoice",
# # # # #         "reference_name":    "ACC-SINV-2026-00565",
# # # # #         "allocated_amount":  32.45
# # # # #     }]
# # # # #   }
# # # # # =============================================================================

# # # # from __future__ import annotations

# # # # import json
# # # # import logging
# # # # import time
# # # # import threading
# # # # import urllib.request
# # # # import urllib.error
# # # # from datetime import date

# # # # log = logging.getLogger("PaymentEntry")

# # # # SYNC_INTERVAL   = 60      # seconds between auto-sync cycles
# # # # REQUEST_TIMEOUT = 30

# # # # # Exchange rate cache: "FROM::TO::DATE" → float
# # # # _RATE_CACHE: dict[str, float] = {}


# # # # def _get_exchange_rate(from_currency: str, to_currency: str,
# # # #                        transaction_date: str,
# # # #                        api_key: str, api_secret: str, host: str) -> float:
# # # #     """
# # # #     Fetch live exchange rate from Frappe.
# # # #     Returns 1.0 for same currency, 0.0 if fetch fails (Frappe uses its own rate).
# # # #     """
# # # #     if not from_currency or from_currency.upper() == to_currency.upper():
# # # #         return 1.0

# # # #     cache_key = f"{from_currency.upper()}::{to_currency.upper()}::{transaction_date}"
# # # #     if cache_key in _RATE_CACHE:
# # # #         return _RATE_CACHE[cache_key]

# # # #     try:
# # # #         import urllib.parse
# # # #         url = (
# # # #             f"{host}/api/method/erpnext.setup.utils.get_exchange_rate"
# # # #             f"?from_currency={urllib.parse.quote(from_currency)}"
# # # #             f"&to_currency={urllib.parse.quote(to_currency)}"
# # # #             f"&transaction_date={transaction_date}"
# # # #         )
# # # #         req = urllib.request.Request(url)
# # # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # # #             data = json.loads(r.read().decode())
# # # #             rate = float(data.get("message") or data.get("result") or 0)
# # # #             if rate > 0:
# # # #                 _RATE_CACHE[cache_key] = rate
# # # #                 log.debug("Rate %s→%s on %s: %.6f", from_currency, to_currency, transaction_date, rate)
# # # #                 return rate
# # # #     except Exception as e:
# # # #         log.debug("Rate fetch failed (%s→%s): %s", from_currency, to_currency, e)

# # # #     return 0.0

# # # # _sync_lock:   threading.Lock          = threading.Lock()
# # # # _sync_thread: threading.Thread | None = None

# # # # # Method → Frappe Mode of Payment name
# # # # _METHOD_MAP = {
# # # #     "CASH":     "Cash",
# # # #     "CARD":     "Credit Card",
# # # #     "C / CARD": "Credit Card",
# # # #     "EFTPOS":   "Credit Card",
# # # #     "CHECK":    "Cheque",
# # # #     "CHEQUE":   "Cheque",
# # # #     "MOBILE":   "Mobile Money",
# # # #     "CREDIT":   "Credit",
# # # #     "TRANSFER": "Bank Transfer",
# # # # }


# # # # # =============================================================================
# # # # # CREDENTIALS / HOST / DEFAULTS
# # # # # =============================================================================

# # # # def _get_credentials() -> tuple[str, str]:
# # # #     try:
# # # #         from services.credentials import get_credentials
# # # #         return get_credentials()
# # # #     except Exception:
# # # #         pass
# # # #     return "", ""


# # # # def _get_host() -> str:
# # # #     try:
# # # #         from models.company_defaults import get_defaults
# # # #         host = (get_defaults() or {}).get("server_api_host", "").strip().rstrip("/")
# # # #         if host:
# # # #             return host
# # # #     except Exception:
# # # #         pass
# # # #     return "https://apk.havano.cloud"


# # # # def _get_defaults() -> dict:
# # # #     try:
# # # #         from models.company_defaults import get_defaults
# # # #         return get_defaults() or {}
# # # #     except Exception:
# # # #         return {}


# # # # # =============================================================================
# # # # # GL ACCOUNT RESOLVER  (which account to credit for each payment method)
# # # # # =============================================================================

# # # # _ACCOUNT_CACHE: dict[str, str] = {}


# # # # def _resolve_paid_to_account(mop_name: str, company: str, currency: str,
# # # #                               api_key: str, api_secret: str, host: str) -> str:
# # # #     """
# # # #     Looks up the GL account for a Mode of Payment from Frappe.
# # # #     Tries to match by currency if multiple accounts exist for the company.
# # # #     Falls back to server_pos_account in company_defaults.
# # # #     """
# # # #     cache_key = f"{mop_name}::{company}::{currency}"
# # # #     if cache_key in _ACCOUNT_CACHE:
# # # #         return _ACCOUNT_CACHE[cache_key]

# # # #     try:
# # # #         import urllib.parse
# # # #         url = (f"{host}/api/resource/Mode%20of%20Payment/"
# # # #                f"{urllib.parse.quote(mop_name)}?fields=[\"accounts\"]")
# # # #         req = urllib.request.Request(url)
# # # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # # #             data     = json.loads(r.read().decode())
# # # #             accounts = (data.get("data") or {}).get("accounts", [])

# # # #         company_accts = [a for a in accounts
# # # #                          if not company or a.get("company") == company]

# # # #         # Prefer account whose name contains the currency code
# # # #         matched = ""
# # # #         if currency:
# # # #             for a in company_accts:
# # # #                 if currency.upper() in (a.get("default_account") or "").upper():
# # # #                     matched = a["default_account"]; break

# # # #         if not matched and company_accts:
# # # #             matched = company_accts[0].get("default_account", "")

# # # #         if matched:
# # # #             _ACCOUNT_CACHE[cache_key] = matched
# # # #             return matched

# # # #     except Exception as e:
# # # #         log.debug("MOP account lookup failed for '%s': %s", mop_name, e)

# # # #     # Fallback
# # # #     fallback = _get_defaults().get("server_pos_account", "").strip()
# # # #     if fallback:
# # # #         _ACCOUNT_CACHE[cache_key] = fallback
# # # #         return fallback

# # # #     log.warning("No GL account for MOP '%s' currency=%s — Payment Entry may fail.",
# # # #                 mop_name, currency)
# # # #     return ""


# # # # # =============================================================================
# # # # # LOCAL DB  — create / read / update payment_entries
# # # # # =============================================================================

# # # # def create_payment_entry(sale: dict, override_rate: float = None,
# # # #                          override_account: str = None) -> int | None:
# # # #     """
# # # #     Called immediately after a sale is saved locally.
# # # #     Stores a payment_entry row with synced=0.
# # # #     Returns the new payment_entry id, or None on error.

# # # #     Will only create the entry once per sale (idempotent).
# # # #     """
# # # #     from database.db import get_connection
# # # #     conn = get_connection(); cur = conn.cursor()

# # # #     # Idempotency: don't create twice for the same sale
# # # #     cur.execute("SELECT id FROM payment_entries WHERE sale_id = ?", (sale["id"],))
# # # #     if cur.fetchone():
# # # #         conn.close()
# # # #         return None

# # # #     customer   = (sale.get("customer_name") or "default").strip()
# # # #     currency   = (sale.get("currency")      or "USD").strip().upper()
# # # #     amount     = float(sale.get("total")    or 0)
# # # #     inv_no     = sale.get("invoice_no", "")
# # # #     inv_date   = sale.get("invoice_date") or date.today().isoformat()
# # # #     method     = str(sale.get("method", "CASH")).upper().strip()
# # # #     mop        = _METHOD_MAP.get(method, "Cash")

# # # #     # Use override rate (from split) or fetch from Frappe
# # # #     if override_rate is not None:
# # # #         exch_rate = override_rate
# # # #     else:
# # # #         try:
# # # #             api_key, api_secret = _get_credentials()
# # # #             host = _get_host()
# # # #             defaults = _get_defaults()
# # # #             company_currency = defaults.get("server_company_currency", "USD").strip().upper() or "USD"
# # # #             exch_rate = _get_exchange_rate(
# # # #                 currency, company_currency, inv_date, api_key, api_secret, host
# # # #             ) if currency != company_currency else 1.0
# # # #         except Exception:
# # # #             exch_rate = 1.0

# # # #     cur.execute("""
# # # #         INSERT INTO payment_entries (
# # # #             sale_id, sale_invoice_no, frappe_invoice_ref,
# # # #             party, party_name,
# # # #             paid_amount, received_amount, source_exchange_rate,
# # # #             paid_to_account_currency, currency,
# # # #             mode_of_payment,
# # # #             reference_no, reference_date,
# # # #             remarks, synced
# # # #         ) OUTPUT INSERTED.id
# # # #         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # # #     """, (
# # # #         sale["id"], inv_no,
# # # #         sale.get("frappe_ref") or None,
# # # #         customer, customer,
# # # #         amount, amount, exch_rate or 1.0,
# # # #         currency, currency,
# # # #         mop,
# # # #         inv_no, inv_date,
# # # #         f"POS Payment — {mop}",
# # # #     ))
# # # #     new_id = int(cur.fetchone()[0])
# # # #     conn.commit(); conn.close()
# # # #     log.debug("Payment entry %d created locally for sale %s", new_id, inv_no)
# # # #     return new_id


# # # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # # #     """
# # # #     Called when cashier uses Split payment.
# # # #     Creates one payment_entry row per currency in splits list.
# # # #     splits = [{"mode": "CASH", "currency": "USD", "amount": 5.0,
# # # #                "rate": 1.0, "base_amount": 5.0, "account": "Cash - AT"}, ...]
# # # #     Returns list of new payment_entry ids.
# # # #     """
# # # #     ids = []
# # # #     for split in splits:
# # # #         if not split.get("amount") or float(split["amount"]) <= 0:
# # # #             continue
# # # #         # Build a sale-like dict with the split's currency and amount
# # # #         split_sale = dict(sale)
# # # #         split_sale["currency"]      = split.get("currency", "USD")
# # # #         split_sale["total"]         = float(split.get("amount", 0))
# # # #         split_sale["method"]        = split.get("mode", "CASH")
# # # #         # Override exchange rate from split data
# # # #         new_id = create_payment_entry(
# # # #             split_sale,
# # # #             override_rate=float(split.get("rate", 1.0)),
# # # #             override_account=split.get("account", ""),
# # # #         )
# # # #         if new_id:
# # # #             ids.append(new_id)
# # # #     return ids


# # # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # # #     """
# # # #     Creates one payment_entry per currency from a split payment.
# # # #     Groups splits by currency, sums amounts, creates one entry each.
# # # #     Returns list of created payment_entry ids.
# # # #     """
# # # #     from datetime import date as _date

# # # #     # Group by currency
# # # #     by_currency: dict[str, dict] = {}
# # # #     for s in splits:
# # # #         curr = s.get("account_currency", "USD").upper()
# # # #         if curr not in by_currency:
# # # #             by_currency[curr] = {
# # # #                 "currency":      curr,
# # # #                 "paid_amount":   0.0,
# # # #                 "base_value":    0.0,
# # # #                 "rate":          s.get("rate", 1.0),
# # # #                 "account_name":  s.get("account_name", ""),
# # # #                 "mode":          s.get("mode", "Cash"),
# # # #             }
# # # #         by_currency[curr]["paid_amount"] += s.get("amount_paid", 0.0)
# # # #         by_currency[curr]["base_value"]  += s.get("base_value",  0.0)

# # # #     ids = []
# # # #     inv_no   = sale.get("invoice_no", "")
# # # #     inv_date = sale.get("invoice_date") or _date.today().isoformat()
# # # #     customer = (sale.get("customer_name") or "default").strip()

# # # #     from database.db import get_connection
# # # #     conn = get_connection(); cur = conn.cursor()

# # # #     for curr, grp in by_currency.items():
# # # #         # Idempotency: skip if already exists for this sale+currency
# # # #         cur.execute(
# # # #             "SELECT id FROM payment_entries WHERE sale_id=? AND currency=?",
# # # #             (sale["id"], curr)
# # # #         )
# # # #         if cur.fetchone():
# # # #             continue

# # # #         mop = _METHOD_MAP.get(grp["mode"].upper(), "Cash")

# # # #         cur.execute("""
# # # #             INSERT INTO payment_entries (
# # # #                 sale_id, sale_invoice_no, frappe_invoice_ref,
# # # #                 party, party_name,
# # # #                 paid_amount, received_amount, source_exchange_rate,
# # # #                 paid_to_account_currency, currency,
# # # #                 paid_to,
# # # #                 mode_of_payment,
# # # #                 reference_no, reference_date,
# # # #                 remarks, synced
# # # #             ) OUTPUT INSERTED.id
# # # #             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # # #         """, (
# # # #             sale["id"], inv_no,
# # # #             sale.get("frappe_ref") or None,
# # # #             customer, customer,
# # # #             grp["paid_amount"],
# # # #             grp["base_value"],
# # # #             float(grp["rate"] or 1.0),
# # # #             curr, curr,
# # # #             grp["account_name"],
# # # #             mop,
# # # #             inv_no, inv_date,
# # # #             f"POS Split Payment — {mop} ({curr})",
# # # #         ))
# # # #         new_id = int(cur.fetchone()[0])
# # # #         ids.append(new_id)
# # # #         log.debug("Split payment entry %d created: %s %.2f %s",
# # # #                   new_id, curr, grp["paid_amount"], inv_no)

# # # #     conn.commit(); conn.close()
# # # #     return ids


# # # # def get_unsynced_payment_entries() -> list[dict]:
# # # #     """Returns payment entries that are ready to push (synced=0)."""
# # # #     from database.db import get_connection, fetchall_dicts
# # # #     conn = get_connection(); cur = conn.cursor()
# # # #     cur.execute("""
# # # #         SELECT pe.*, s.frappe_ref AS sale_frappe_ref
# # # #         FROM payment_entries pe
# # # #         LEFT JOIN sales s ON s.id = pe.sale_id
# # # #         WHERE pe.synced = 0
# # # #           AND (pe.frappe_invoice_ref IS NOT NULL
# # # #                OR s.frappe_ref IS NOT NULL)
# # # #         ORDER BY pe.id
# # # #     """)
# # # #     rows = fetchall_dicts(cur); conn.close()
# # # #     return rows


# # # # def mark_payment_synced(pe_id: int, frappe_payment_ref: str = "") -> None:
# # # #     from database.db import get_connection
# # # #     conn = get_connection(); cur = conn.cursor()
# # # #     cur.execute(
# # # #         "UPDATE payment_entries SET synced=1, frappe_payment_ref=? WHERE id=?",
# # # #         (frappe_payment_ref or None, pe_id)
# # # #     )
# # # #     # Also update the sales row
# # # #     cur.execute("""
# # # #         UPDATE sales SET payment_entry_ref=?, payment_synced=1
# # # #         WHERE id = (SELECT sale_id FROM payment_entries WHERE id=?)
# # # #     """, (frappe_payment_ref or None, pe_id))
# # # #     conn.commit(); conn.close()


# # # # def refresh_frappe_refs() -> int:
# # # #     """
# # # #     For payment entries that have no frappe_invoice_ref yet, copy it from
# # # #     the parent sale's frappe_ref. Call this before pushing payments.
# # # #     Returns count updated.
# # # #     """
# # # #     from database.db import get_connection
# # # #     conn = get_connection(); cur = conn.cursor()
# # # #     cur.execute("""
# # # #         UPDATE pe
# # # #         SET pe.frappe_invoice_ref = s.frappe_ref
# # # #         FROM payment_entries pe
# # # #         JOIN sales s ON s.id = pe.sale_id
# # # #         WHERE pe.synced = 0
# # # #           AND (pe.frappe_invoice_ref IS NULL OR pe.frappe_invoice_ref = '')
# # # #           AND s.frappe_ref IS NOT NULL AND s.frappe_ref != ''
# # # #     """)
# # # #     count = cur.rowcount
# # # #     conn.commit(); conn.close()
# # # #     return count


# # # # # =============================================================================
# # # # # BUILD FRAPPE PAYLOAD
# # # # # =============================================================================

# # # # def _build_payload(pe: dict, defaults: dict,
# # # #                    api_key: str, api_secret: str, host: str) -> dict:
# # # #     company  = defaults.get("server_company", "")
# # # #     currency = (pe.get("currency") or pe.get("paid_to_account_currency") or "USD").upper()
# # # #     mop      = pe.get("mode_of_payment") or "Cash"
# # # #     amount   = float(pe.get("paid_amount") or 0)
# # # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()

# # # #     # Use local gl_accounts table first (synced from Frappe)
# # # #     paid_to          = (pe.get("paid_to") or "").strip()
# # # #     paid_to_currency = currency
# # # #     if not paid_to:
# # # #         try:
# # # #             from models.gl_account import get_account_for_payment
# # # #             acct = get_account_for_payment(currency, company)
# # # #             if acct:
# # # #                 paid_to          = acct["name"]
# # # #                 paid_to_currency = acct["account_currency"]
# # # #         except Exception as _e:
# # # #             log.debug("gl_account lookup failed: %s", _e)

# # # #     # Fallback to live Frappe lookup
# # # #     if not paid_to:
# # # #         paid_to = _resolve_paid_to_account(mop, company, currency, api_key, api_secret, host)

# # # #     # Use local exchange rate if not stored
# # # #     exch_rate = float(pe.get("source_exchange_rate") or 1.0)
# # # #     if exch_rate == 1.0 and currency not in ("USD", ""):
# # # #         try:
# # # #             from models.exchange_rate import get_rate
# # # #             stored = get_rate(currency, "USD")
# # # #             if stored:
# # # #                 exch_rate = stored
# # # #         except Exception:
# # # #             pass

# # # #     payload = {
# # # #         "doctype":                  "Payment Entry",
# # # #         "payment_type":             "Receive",
# # # #         "party_type":               "Customer",
# # # #         "party":                    pe.get("party") or "default",
# # # #         "party_name":               pe.get("party_name") or "default",
# # # #         "paid_to_account_currency": paid_to_currency,
# # # #         "paid_amount":              amount,
# # # #         "received_amount":          amount,
# # # #         "source_exchange_rate":     exch_rate,
# # # #         "reference_no":             pe.get("reference_no") or pe.get("sale_invoice_no", ""),
# # # #         "reference_date":           pe.get("reference_date") or date.today().isoformat(),
# # # #         "remarks":                  pe.get("remarks") or f"POS Payment — {mop}",
# # # #         "mode_of_payment":          mop,
# # # #         "docstatus":                1,
# # # #     }

# # # #     if paid_to:
# # # #         payload["paid_to"] = paid_to
# # # #     if company:
# # # #         payload["company"] = company

# # # #     # Link to the Sales Invoice on Frappe
# # # #     if frappe_inv:
# # # #         payload["references"] = [{
# # # #             "reference_doctype": "Sales Invoice",
# # # #             "reference_name":    frappe_inv,
# # # #             "allocated_amount":  amount,
# # # #         }]

# # # #     return payload


# # # # # =============================================================================
# # # # # PUSH ONE PAYMENT ENTRY
# # # # # =============================================================================

# # # # def _push_payment_entry(pe: dict, api_key: str, api_secret: str,
# # # #                         defaults: dict, host: str) -> str | None:
# # # #     """
# # # #     Posts one payment entry to Frappe.
# # # #     Returns Frappe's PAY-xxxxx name on success, None on failure.
# # # #     """
# # # #     pe_id  = pe["id"]
# # # #     inv_no = pe.get("sale_invoice_no", str(pe_id))

# # # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()
# # # #     if not frappe_inv:
# # # #         log.warning("Payment %d — Sales Invoice not yet on Frappe, skipping.", pe_id)
# # # #         return None

# # # #     payload = _build_payload(pe, defaults, api_key, api_secret, host)

# # # #     url = f"{host}/api/resource/Payment%20Entry"
# # # #     req = urllib.request.Request(
# # # #         url=url,
# # # #         data=json.dumps(payload).encode("utf-8"),
# # # #         method="POST",
# # # #         headers={
# # # #             "Content-Type":  "application/json",
# # # #             "Accept":        "application/json",
# # # #             "Authorization": f"token {api_key}:{api_secret}",
# # # #         },
# # # #     )

# # # #     try:
# # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
# # # #             data = json.loads(resp.read().decode())
# # # #             name = (data.get("data") or {}).get("name", "")
# # # #             log.info("✅ Payment Entry %d → Frappe %s  [%s  %s %.2f]",
# # # #                      pe_id, name, inv_no,
# # # #                      pe.get("currency", ""), float(pe.get("paid_amount", 0)))
# # # #             return name or "SYNCED"

# # # #     except urllib.error.HTTPError as e:
# # # #         try:
# # # #             err = json.loads(e.read().decode())
# # # #             msg = (err.get("exception") or err.get("message") or
# # # #                    str(err.get("_server_messages", "")) or f"HTTP {e.code}")
# # # #         except Exception:
# # # #             msg = f"HTTP {e.code}"

# # # #         if e.code == 409:
# # # #             log.info("Payment %d already on Frappe (409) - marking synced.", pe_id)
# # # #             return "DUPLICATE"

# # # #         # Invoice already paid (is_pos:1 on old invoices) - stop retrying
# # # #         if e.code == 417:
# # # #             _perma = ("already been fully paid", "already paid", "fully paid")
# # # #             if any(p in msg.lower() for p in _perma):
# # # #                 log.info("Payment %d - invoice already paid on Frappe, marking synced.", pe_id)
# # # #                 return "ALREADY_PAID"

# # # #         log.error("FAIL Payment Entry %d  HTTP %s: %s", pe_id, e.code, msg)
# # # #         return None

# # # #     except urllib.error.URLError as e:
# # # #         log.warning("Network error pushing payment %d: %s", pe_id, e.reason)
# # # #         return None

# # # #     except Exception as e:
# # # #         log.error("Unexpected error pushing payment %d: %s", pe_id, e)
# # # #         return None


# # # # # =============================================================================
# # # # # PUBLIC — push all unsynced payment entries
# # # # # =============================================================================

# # # # def push_unsynced_payment_entries() -> dict:
# # # #     """
# # # #     1. Refresh frappe_invoice_ref from parent sales that were confirmed.
# # # #     2. Push each unsynced payment entry to Frappe.
# # # #     3. Mark synced with the returned PAY-xxxxx ref.
# # # #     """
# # # #     result = {"pushed": 0, "failed": 0, "skipped": 0, "total": 0}

# # # #     api_key, api_secret = _get_credentials()
# # # #     if not api_key or not api_secret:
# # # #         log.warning("No credentials — skipping payment entry sync.")
# # # #         return result

# # # #     host     = _get_host()
# # # #     defaults = _get_defaults()

# # # #     # First: pull frappe_refs from confirmed invoices into pending payment entries
# # # #     updated = refresh_frappe_refs()
# # # #     if updated:
# # # #         log.info("Refreshed frappe_invoice_ref on %d payment entry(ies).", updated)

# # # #     entries = get_unsynced_payment_entries()
# # # #     result["total"] = len(entries)

# # # #     if not entries:
# # # #         log.debug("No unsynced payment entries.")
# # # #         return result

# # # #     log.info("Pushing %d payment entry(ies) to Frappe…", len(entries))

# # # #     for pe in entries:
# # # #         frappe_name = _push_payment_entry(pe, api_key, api_secret, defaults, host)
# # # #         if frappe_name:
# # # #             mark_payment_synced(pe["id"], frappe_name)
# # # #             result["pushed"] += 1
# # # #         elif frappe_name is None:
# # # #             # None = permanent skip (no frappe_inv yet), not a real failure
# # # #             result["skipped"] += 1
# # # #         else:
# # # #             result["failed"] += 1

# # # #         time.sleep(3)   # rate limit — 20/min max

# # # #     log.info("Payment sync done — ✅ %d pushed  ❌ %d failed  ⏭ %d skipped",
# # # #              result["pushed"], result["failed"], result["skipped"])
# # # #     return result


# # # # # =============================================================================
# # # # # BACKGROUND DAEMON THREAD
# # # # # =============================================================================

# # # # def _sync_loop():
# # # #     log.info("Payment entry sync daemon started (interval=%ds).", SYNC_INTERVAL)
# # # #     while True:
# # # #         if _sync_lock.acquire(blocking=False):
# # # #             try:
# # # #                 push_unsynced_payment_entries()
# # # #             except Exception as e:
# # # #                 log.error("Payment sync cycle error: %s", e)
# # # #             finally:
# # # #                 _sync_lock.release()
# # # #         else:
# # # #             log.debug("Previous payment sync still running — skipping.")
# # # #         time.sleep(SYNC_INTERVAL)


# # # # def start_payment_sync_daemon() -> threading.Thread:
# # # #     """Non-blocking — safe to call from MainWindow.__init__."""
# # # #     global _sync_thread
# # # #     if _sync_thread and _sync_thread.is_alive():
# # # #         return _sync_thread
# # # #     t = threading.Thread(target=_sync_loop, daemon=True, name="PaymentSyncDaemon")
# # # #     t.start()
# # # #     _sync_thread = t
# # # #     log.info("Payment entry sync daemon started.")
# # # #     return t


# # # # # =============================================================================
# # # # # DEBUG
# # # # # =============================================================================

# # # # if __name__ == "__main__":
# # # #     logging.basicConfig(level=logging.INFO,
# # # #                         format="%(asctime)s [%(levelname)s] %(message)s")
# # # #     print("Running one payment entry sync cycle...")
# # # #     r = push_unsynced_payment_entries()
# # # #     print(f"\nResult: {r['pushed']} pushed, {r['failed']} failed, "
# # # #           f"{r['skipped']} skipped (of {r['total']} total)")

# # # # =============================================================================
# # # # services/payment_entry_service.py
# # # #
# # # # Manages local payment_entries table and syncs them to Frappe.
# # # #
# # # # FLOW:
# # # #   1. When a sale is saved locally → create_payment_entry() stores it locally
# # # #      with synced=0
# # # #   2. When the Sales Invoice is confirmed on Frappe (frappe_ref is set) →
# # # #      push_unsynced_payment_entries() pushes the Payment Entry to Frappe
# # # #   3. Frappe returns a PAY-xxxxx ref → stored as frappe_payment_ref, synced=1
# # # #
# # # # PAYLOAD SENT TO FRAPPE:
# # # #   POST /api/resource/Payment Entry
# # # #   {
# # # #     "doctype":              "Payment Entry",
# # # #     "payment_type":         "Receive",
# # # #     "party_type":           "Customer",
# # # #     "party":                "Cathy",
# # # #     "paid_to":              "Cash ZWG - H",
# # # #     "paid_to_account_currency": "USD",
# # # #     "paid_amount":          32.45,
# # # #     "received_amount":      32.45,
# # # #     "source_exchange_rate": 1.0,
# # # #     "reference_no":         "ACC-SINV-2026-00034",
# # # #     "reference_date":       "2026-03-19",
# # # #     "remarks":              "POS Payment — Cash",
# # # #     "docstatus":            1,
# # # #     "references": [{
# # # #         "reference_doctype": "Sales Invoice",
# # # #         "reference_name":    "ACC-SINV-2026-00565",
# # # #         "allocated_amount":  32.45
# # # #     }]
# # # #   }
# # # # =============================================================================

# # # from __future__ import annotations

# # # import json
# # # import logging
# # # import time
# # # import threading
# # # import urllib.request
# # # import urllib.error
# # # from datetime import date

# # # log = logging.getLogger("PaymentEntry")

# # # SYNC_INTERVAL   = 60      # seconds between auto-sync cycles
# # # REQUEST_TIMEOUT = 30

# # # # Exchange rate cache: "FROM::TO::DATE" → float
# # # _RATE_CACHE: dict[str, float] = {}


# # # def _get_exchange_rate(from_currency: str, to_currency: str,
# # #                        transaction_date: str,
# # #                        api_key: str, api_secret: str, host: str) -> float:
# # #     """
# # #     Fetch live exchange rate from Frappe.
# # #     Returns 1.0 for same currency, 0.0 if fetch fails (Frappe uses its own rate).
# # #     """
# # #     if not from_currency or from_currency.upper() == to_currency.upper():
# # #         return 1.0

# # #     cache_key = f"{from_currency.upper()}::{to_currency.upper()}::{transaction_date}"
# # #     if cache_key in _RATE_CACHE:
# # #         return _RATE_CACHE[cache_key]

# # #     try:
# # #         import urllib.parse
# # #         url = (
# # #             f"{host}/api/method/erpnext.setup.utils.get_exchange_rate"
# # #             f"?from_currency={urllib.parse.quote(from_currency)}"
# # #             f"&to_currency={urllib.parse.quote(to_currency)}"
# # #             f"&transaction_date={transaction_date}"
# # #         )
# # #         req = urllib.request.Request(url)
# # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # #             data = json.loads(r.read().decode())
# # #             rate = float(data.get("message") or data.get("result") or 0)
# # #             if rate > 0:
# # #                 _RATE_CACHE[cache_key] = rate
# # #                 log.debug("Rate %s→%s on %s: %.6f", from_currency, to_currency, transaction_date, rate)
# # #                 return rate
# # #     except Exception as e:
# # #         log.debug("Rate fetch failed (%s→%s): %s", from_currency, to_currency, e)

# # #     return 0.0

# # # _sync_lock:   threading.Lock          = threading.Lock()
# # # _sync_thread: threading.Thread | None = None

# # # # Method → Frappe Mode of Payment name
# # # _METHOD_MAP = {
# # #     "CASH":     "Cash",
# # #     "CARD":     "Credit Card",
# # #     "C / CARD": "Credit Card",
# # #     "EFTPOS":   "Credit Card",
# # #     "CHECK":    "Cheque",
# # #     "CHEQUE":   "Cheque",
# # #     "MOBILE":   "Mobile Money",
# # #     "CREDIT":   "Credit",
# # #     "TRANSFER": "Bank Transfer",
# # # }


# # # # =============================================================================
# # # # CREDENTIALS / HOST / DEFAULTS
# # # # =============================================================================

# # # def _get_credentials() -> tuple[str, str]:
# # #     try:
# # #         from services.credentials import get_credentials
# # #         return get_credentials()
# # #     except Exception:
# # #         pass
# # #     return "", ""

# # # def _get_host() -> str:
# # #     try:
# # #         from models.company_defaults import get_defaults
# # #         host = (get_defaults() or {}).get("server_api_host", "").strip().rstrip("/")
# # #         if host:
# # #             return host
# # #     except Exception:
# # #         pass
# # #     return "https://apk.havano.cloud"


# # # def _get_defaults() -> dict:
# # #     try:
# # #         from models.company_defaults import get_defaults
# # #         return get_defaults() or {}
# # #     except Exception:
# # #         return {}


# # # # =============================================================================
# # # # GL ACCOUNT RESOLVER  (which account to credit for each payment method)
# # # # =============================================================================

# # # _ACCOUNT_CACHE: dict[str, str] = {}


# # # def _resolve_paid_to_account(mop_name: str, company: str, currency: str,
# # #                               api_key: str, api_secret: str, host: str) -> str:
# # #     """
# # #     Looks up the GL account for a Mode of Payment from Frappe.
# # #     Tries to match by currency if multiple accounts exist for the company.
# # #     Falls back to server_pos_account in company_defaults.
# # #     """
# # #     cache_key = f"{mop_name}::{company}::{currency}"
# # #     if cache_key in _ACCOUNT_CACHE:
# # #         return _ACCOUNT_CACHE[cache_key]

# # #     try:
# # #         import urllib.parse
# # #         url = (f"{host}/api/resource/Mode%20of%20Payment/"
# # #                f"{urllib.parse.quote(mop_name)}?fields=[\"accounts\"]")
# # #         req = urllib.request.Request(url)
# # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # #             data     = json.loads(r.read().decode())
# # #             accounts = (data.get("data") or {}).get("accounts", [])

# # #         company_accts = [a for a in accounts
# # #                          if not company or a.get("company") == company]

# # #         # Prefer account whose name contains the currency code
# # #         matched = ""
# # #         if currency:
# # #             for a in company_accts:
# # #                 if currency.upper() in (a.get("default_account") or "").upper():
# # #                     matched = a["default_account"]; break

# # #         if not matched and company_accts:
# # #             matched = company_accts[0].get("default_account", "")

# # #         if matched:
# # #             _ACCOUNT_CACHE[cache_key] = matched
# # #             return matched

# # #     except Exception as e:
# # #         log.debug("MOP account lookup failed for '%s': %s", mop_name, e)

# # #     # Fallback
# # #     fallback = _get_defaults().get("server_pos_account", "").strip()
# # #     if fallback:
# # #         _ACCOUNT_CACHE[cache_key] = fallback
# # #         return fallback

# # #     log.warning("No GL account for MOP '%s' currency=%s — Payment Entry may fail.",
# # #                 mop_name, currency)
# # #     return ""


# # # # =============================================================================
# # # # LOCAL DB  — create / read / update payment_entries
# # # # =============================================================================

# # # def create_payment_entry(sale: dict, override_rate: float = None,
# # #                          override_account: str = None) -> int | None:
# # #     """
# # #     Called immediately after a sale is saved locally.
# # #     Stores a payment_entry row with synced=0.
# # #     Returns the new payment_entry id, or None on error.

# # #     Will only create the entry once per sale (idempotent).
# # #     """
# # #     from database.db import get_connection
# # #     conn = get_connection(); cur = conn.cursor()

# # #     # Idempotency: don't create twice for the same sale
# # #     cur.execute("SELECT id FROM payment_entries WHERE sale_id = ?", (sale["id"],))
# # #     if cur.fetchone():
# # #         conn.close()
# # #         return None

# # #     customer   = (sale.get("customer_name") or "default").strip()
# # #     currency   = (sale.get("currency")      or "USD").strip().upper()
# # #     amount     = float(sale.get("total")    or 0)
# # #     inv_no     = sale.get("invoice_no", "")
# # #     inv_date   = sale.get("invoice_date") or date.today().isoformat()
# # #     method     = str(sale.get("method", "CASH")).upper().strip()
# # #     mop        = _METHOD_MAP.get(method, "Cash")

# # #     # Use override rate (from split) or fetch from Frappe
# # #     if override_rate is not None:
# # #         exch_rate = override_rate
# # #     else:
# # #         try:
# # #             api_key, api_secret = _get_credentials()
# # #             host = _get_host()
# # #             defaults = _get_defaults()
# # #             company_currency = defaults.get("server_company_currency", "USD").strip().upper() or "USD"
# # #             exch_rate = _get_exchange_rate(
# # #                 currency, company_currency, inv_date, api_key, api_secret, host
# # #             ) if currency != company_currency else 1.0
# # #         except Exception:
# # #             exch_rate = 1.0

# # #     cur.execute("""
# # #         INSERT INTO payment_entries (
# # #             sale_id, sale_invoice_no, frappe_invoice_ref,
# # #             party, party_name,
# # #             paid_amount, received_amount, source_exchange_rate,
# # #             paid_to_account_currency, currency,
# # #             mode_of_payment,
# # #             reference_no, reference_date,
# # #             remarks, synced
# # #         ) OUTPUT INSERTED.id
# # #         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # #     """, (
# # #         sale["id"], inv_no,
# # #         sale.get("frappe_ref") or None,
# # #         customer, customer,
# # #         amount, amount, exch_rate or 1.0,
# # #         currency, currency,
# # #         mop,
# # #         inv_no, inv_date,
# # #         f"POS Payment — {mop}",
# # #     ))
# # #     new_id = int(cur.fetchone()[0])
# # #     conn.commit(); conn.close()
# # #     log.debug("Payment entry %d created locally for sale %s", new_id, inv_no)
# # #     return new_id


# # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # #     """
# # #     Called when cashier uses Split payment.
# # #     Creates one payment_entry row per currency in splits list.
# # #     splits = [{"mode": "CASH", "currency": "USD", "amount": 5.0,
# # #                "rate": 1.0, "base_amount": 5.0, "account": "Cash - AT"}, ...]
# # #     Returns list of new payment_entry ids.
# # #     """
# # #     ids = []
# # #     for split in splits:
# # #         if not split.get("amount") or float(split["amount"]) <= 0:
# # #             continue
# # #         # Build a sale-like dict with the split's currency and amount
# # #         split_sale = dict(sale)
# # #         split_sale["currency"]      = split.get("currency", "USD")
# # #         split_sale["total"]         = float(split.get("amount", 0))
# # #         split_sale["method"]        = split.get("mode", "CASH")
# # #         # Override exchange rate from split data
# # #         new_id = create_payment_entry(
# # #             split_sale,
# # #             override_rate=float(split.get("rate", 1.0)),
# # #             override_account=split.get("account", ""),
# # #         )
# # #         if new_id:
# # #             ids.append(new_id)
# # #     return ids


# # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # #     """
# # #     Creates one payment_entry per currency from a split payment.
# # #     Groups splits by currency, sums amounts, creates one entry each.
# # #     Returns list of created payment_entry ids.
# # #     """
# # #     from datetime import date as _date

# # #     # Group by currency
# # #     by_currency: dict[str, dict] = {}
# # #     for s in splits:
# # #         curr = s.get("account_currency", "USD").upper()
# # #         if curr not in by_currency:
# # #             by_currency[curr] = {
# # #                 "currency":      curr,
# # #                 "paid_amount":   0.0,
# # #                 "base_value":    0.0,
# # #                 "rate":          s.get("rate", 1.0),
# # #                 "account_name":  s.get("account_name", ""),
# # #                 "mode":          s.get("mode", "Cash"),
# # #             }
# # #         by_currency[curr]["paid_amount"] += s.get("amount_paid", 0.0)
# # #         by_currency[curr]["base_value"]  += s.get("base_value",  0.0)

# # #     ids = []
# # #     inv_no   = sale.get("invoice_no", "")
# # #     inv_date = sale.get("invoice_date") or _date.today().isoformat()
# # #     customer = (sale.get("customer_name") or "default").strip()

# # #     from database.db import get_connection
# # #     conn = get_connection(); cur = conn.cursor()

# # #     for curr, grp in by_currency.items():
# # #         # Idempotency: skip if already exists for this sale+currency
# # #         cur.execute(
# # #             "SELECT id FROM payment_entries WHERE sale_id=? AND currency=?",
# # #             (sale["id"], curr)
# # #         )
# # #         if cur.fetchone():
# # #             continue

# # #         mop = _METHOD_MAP.get(grp["mode"].upper(), "Cash")

# # #         cur.execute("""
# # #             INSERT INTO payment_entries (
# # #                 sale_id, sale_invoice_no, frappe_invoice_ref,
# # #                 party, party_name,
# # #                 paid_amount, received_amount, source_exchange_rate,
# # #                 paid_to_account_currency, currency,
# # #                 paid_to,
# # #                 mode_of_payment,
# # #                 reference_no, reference_date,
# # #                 remarks, synced
# # #             ) OUTPUT INSERTED.id
# # #             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # #         """, (
# # #             sale["id"], inv_no,
# # #             sale.get("frappe_ref") or None,
# # #             customer, customer,
# # #             grp["paid_amount"],
# # #             grp["base_value"],
# # #             float(grp["rate"] or 1.0),
# # #             curr, curr,
# # #             grp["account_name"],
# # #             mop,
# # #             inv_no, inv_date,
# # #             f"POS Split Payment — {mop} ({curr})",
# # #         ))
# # #         new_id = int(cur.fetchone()[0])
# # #         ids.append(new_id)
# # #         log.debug("Split payment entry %d created: %s %.2f %s",
# # #                   new_id, curr, grp["paid_amount"], inv_no)

# # #     conn.commit(); conn.close()
# # #     return ids


# # # def get_unsynced_payment_entries() -> list[dict]:
# # #     """Returns payment entries that are ready to push (synced=0)."""
# # #     from database.db import get_connection, fetchall_dicts
# # #     conn = get_connection(); cur = conn.cursor()
# # #     cur.execute("""
# # #         SELECT pe.*, s.frappe_ref AS sale_frappe_ref
# # #         FROM payment_entries pe
# # #         LEFT JOIN sales s ON s.id = pe.sale_id
# # #         WHERE pe.synced = 0
# # #           AND (pe.frappe_invoice_ref IS NOT NULL
# # #                OR s.frappe_ref IS NOT NULL)
# # #         ORDER BY pe.id
# # #     """)
# # #     rows = fetchall_dicts(cur); conn.close()
# # #     return rows


# # # def mark_payment_synced(pe_id: int, frappe_payment_ref: str = "") -> None:
# # #     from database.db import get_connection
# # #     conn = get_connection(); cur = conn.cursor()
# # #     cur.execute(
# # #         "UPDATE payment_entries SET synced=1, frappe_payment_ref=? WHERE id=?",
# # #         (frappe_payment_ref or None, pe_id)
# # #     )
# # #     # Also update the sales row
# # #     cur.execute("""
# # #         UPDATE sales SET payment_entry_ref=?, payment_synced=1
# # #         WHERE id = (SELECT sale_id FROM payment_entries WHERE id=?)
# # #     """, (frappe_payment_ref or None, pe_id))
# # #     conn.commit(); conn.close()


# # # def refresh_frappe_refs() -> int:
# # #     """
# # #     For payment entries that have no frappe_invoice_ref yet, copy it from
# # #     the parent sale's frappe_ref. Call this before pushing payments.
# # #     Returns count updated.
# # #     """
# # #     from database.db import get_connection
# # #     conn = get_connection(); cur = conn.cursor()
# # #     cur.execute("""
# # #         UPDATE pe
# # #         SET pe.frappe_invoice_ref = s.frappe_ref
# # #         FROM payment_entries pe
# # #         JOIN sales s ON s.id = pe.sale_id
# # #         WHERE pe.synced = 0
# # #           AND (pe.frappe_invoice_ref IS NULL OR pe.frappe_invoice_ref = '')
# # #           AND s.frappe_ref IS NOT NULL AND s.frappe_ref != ''
# # #     """)
# # #     count = cur.rowcount
# # #     conn.commit(); conn.close()
# # #     return count


# # # # =============================================================================
# # # # BUILD FRAPPE PAYLOAD
# # # # =============================================================================

# # # def _build_payload(pe: dict, defaults: dict,
# # #                    api_key: str, api_secret: str, host: str) -> dict:
# # #     company  = defaults.get("server_company", "")
# # #     currency = (pe.get("currency") or pe.get("paid_to_account_currency") or "USD").upper()
# # #     mop      = pe.get("mode_of_payment") or "Cash"
# # #     amount   = float(pe.get("paid_amount") or 0)
# # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()

# # #     # Use local gl_accounts table first (synced from Frappe)
# # #     paid_to          = (pe.get("paid_to") or "").strip()
# # #     paid_to_currency = currency
# # #     if not paid_to:
# # #         try:
# # #             from models.gl_account import get_account_for_payment
# # #             acct = get_account_for_payment(currency, company)
# # #             if acct:
# # #                 paid_to          = acct["name"]
# # #                 paid_to_currency = acct["account_currency"]
# # #         except Exception as _e:
# # #             log.debug("gl_account lookup failed: %s", _e)

# # #     # Fallback to live Frappe lookup
# # #     if not paid_to:
# # #         paid_to = _resolve_paid_to_account(mop, company, currency, api_key, api_secret, host)

# # #     # Use local exchange rate if not stored
# # #     exch_rate = float(pe.get("source_exchange_rate") or 1.0)
# # #     if exch_rate == 1.0 and currency not in ("USD", ""):
# # #         try:
# # #             from models.exchange_rate import get_rate
# # #             stored = get_rate(currency, "USD")
# # #             if stored:
# # #                 exch_rate = stored
# # #         except Exception:
# # #             pass

# # #     payload = {
# # #         "doctype":                  "Payment Entry",
# # #         "payment_type":             "Receive",
# # #         "party_type":               "Customer",
# # #         "party":                    pe.get("party") or "default",
# # #         "party_name":               pe.get("party_name") or "default",
# # #         "paid_to_account_currency": paid_to_currency,
# # #         "paid_amount":              amount,
# # #         "received_amount":          amount,
# # #         "source_exchange_rate":     exch_rate,
# # #         "reference_no":             pe.get("reference_no") or pe.get("sale_invoice_no", ""),
# # #         "reference_date":           pe.get("reference_date") or date.today().isoformat(),
# # #         "remarks":                  pe.get("remarks") or f"POS Payment — {mop}",
# # #         "mode_of_payment":          mop,
# # #         "docstatus":                1,
# # #     }

# # #     if paid_to:
# # #         payload["paid_to"] = paid_to
# # #     if company:
# # #         payload["company"] = company

# # #     # Link to the Sales Invoice on Frappe
# # #     if frappe_inv:
# # #         payload["references"] = [{
# # #             "reference_doctype": "Sales Invoice",
# # #             "reference_name":    frappe_inv,
# # #             "allocated_amount":  amount,
# # #         }]

# # #     return payload


# # # # =============================================================================
# # # # PUSH ONE PAYMENT ENTRY
# # # # =============================================================================

# # # def _push_payment_entry(pe: dict, api_key: str, api_secret: str,
# # #                         defaults: dict, host: str) -> str | None:
# # #     """
# # #     Posts one payment entry to Frappe.
# # #     Returns Frappe's PAY-xxxxx name on success, None on failure.
# # #     """
# # #     pe_id  = pe["id"]
# # #     inv_no = pe.get("sale_invoice_no", str(pe_id))

# # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()
# # #     if not frappe_inv:
# # #         log.warning("Payment %d — Sales Invoice not yet on Frappe, skipping.", pe_id)
# # #         return None

# # #     payload = _build_payload(pe, defaults, api_key, api_secret, host)

# # #     url = f"{host}/api/resource/Payment%20Entry"
# # #     req = urllib.request.Request(
# # #         url=url,
# # #         data=json.dumps(payload).encode("utf-8"),
# # #         method="POST",
# # #         headers={
# # #             "Content-Type":  "application/json",
# # #             "Accept":        "application/json",
# # #             "Authorization": f"token {api_key}:{api_secret}",
# # #         },
# # #     )

# # #     try:
# # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
# # #             data = json.loads(resp.read().decode())
# # #             name = (data.get("data") or {}).get("name", "")
# # #             log.info("✅ Payment Entry %d → Frappe %s  [%s  %s %.2f]",
# # #                      pe_id, name, inv_no,
# # #                      pe.get("currency", ""), float(pe.get("paid_amount", 0)))
# # #             return name or "SYNCED"

# # #     except urllib.error.HTTPError as e:
# # #         try:
# # #             err = json.loads(e.read().decode())
# # #             msg = (err.get("exception") or err.get("message") or
# # #                    str(err.get("_server_messages", "")) or f"HTTP {e.code}")
# # #         except Exception:
# # #             msg = f"HTTP {e.code}"

# # #         if e.code == 409:
# # #             log.info("Payment %d already on Frappe (409) - marking synced.", pe_id)
# # #             return "DUPLICATE"

# # #         # Invoice already paid (is_pos:1 on old invoices) - stop retrying
# # #         if e.code == 417:
# # #             _perma = ("already been fully paid", "already paid", "fully paid")
# # #             if any(p in msg.lower() for p in _perma):
# # #                 log.info("Payment %d - invoice already paid on Frappe, marking synced.", pe_id)
# # #                 return "ALREADY_PAID"

# # #         log.error("FAIL Payment Entry %d  HTTP %s: %s", pe_id, e.code, msg)
# # #         return None

# # #     except urllib.error.URLError as e:
# # #         log.warning("Network error pushing payment %d: %s", pe_id, e.reason)
# # #         return None

# # #     except Exception as e:
# # #         log.error("Unexpected error pushing payment %d: %s", pe_id, e)
# # #         return None


# # # # =============================================================================
# # # # PUBLIC — push all unsynced payment entries
# # # # =============================================================================

# # # def push_unsynced_payment_entries() -> dict:
# # #     """
# # #     1. Refresh frappe_invoice_ref from parent sales that were confirmed.
# # #     2. Push each unsynced payment entry to Frappe.
# # #     3. Mark synced with the returned PAY-xxxxx ref.
# # #     """
# # #     result = {"pushed": 0, "failed": 0, "skipped": 0, "total": 0}

# # #     api_key, api_secret = _get_credentials()
# # #     if not api_key or not api_secret:
# # #         log.warning("No credentials — skipping payment entry sync.")
# # #         return result

# # #     host     = _get_host()
# # #     defaults = _get_defaults()

# # #     # First: pull frappe_refs from confirmed invoices into pending payment entries
# # #     updated = refresh_frappe_refs()
# # #     if updated:
# # #         log.info("Refreshed frappe_invoice_ref on %d payment entry(ies).", updated)

# # #     entries = get_unsynced_payment_entries()
# # #     result["total"] = len(entries)

# # #     if not entries:
# # #         log.debug("No unsynced payment entries.")
# # #         return result

# # #     log.info("Pushing %d payment entry(ies) to Frappe…", len(entries))

# # #     for pe in entries:
# # #         frappe_name = _push_payment_entry(pe, api_key, api_secret, defaults, host)
# # #         if frappe_name:
# # #             mark_payment_synced(pe["id"], frappe_name)
# # #             result["pushed"] += 1
# # #         elif frappe_name is None:
# # #             # None = permanent skip (no frappe_inv yet), not a real failure
# # #             result["skipped"] += 1
# # #         else:
# # #             result["failed"] += 1

# # #         time.sleep(3)   # rate limit — 20/min max

# # #     log.info("Payment sync done — ✅ %d pushed  ❌ %d failed  ⏭ %d skipped",
# # #              result["pushed"], result["failed"], result["skipped"])
# # #     return result


# # # # =============================================================================
# # # # BACKGROUND DAEMON THREAD
# # # # =============================================================================

# # # def _sync_loop():
# # #     log.info("Payment entry sync daemon started (interval=%ds).", SYNC_INTERVAL)
# # #     while True:
# # #         if _sync_lock.acquire(blocking=False):
# # #             try:
# # #                 push_unsynced_payment_entries()
# # #             except Exception as e:
# # #                 log.error("Payment sync cycle error: %s", e)
# # #             finally:
# # #                 _sync_lock.release()
# # #         else:
# # #             log.debug("Previous payment sync still running — skipping.")
# # #         time.sleep(SYNC_INTERVAL)


# # # def start_payment_sync_daemon() -> threading.Thread:
# # #     """Non-blocking — safe to call from MainWindow.__init__."""
# # #     global _sync_thread
# # #     if _sync_thread and _sync_thread.is_alive():
# # #         return _sync_thread
# # #     t = threading.Thread(target=_sync_loop, daemon=True, name="PaymentSyncDaemon")
# # #     t.start()
# # #     _sync_thread = t
# # #     log.info("Payment entry sync daemon started.")
# # #     return t


# # # # =============================================================================
# # # # DEBUG
# # # # =============================================================================

# # # if __name__ == "__main__":
# # #     logging.basicConfig(level=logging.INFO,
# # #                         format="%(asctime)s [%(levelname)s] %(message)s")
# # #     print("Running one payment entry sync cycle...")
# # #     r = push_unsynced_payment_entries()
# # #     print(f"\nResult: {r['pushed']} pushed, {r['failed']} failed, "
# # #           f"{r['skipped']} skipped (of {r['total']} total)")


# # # =============================================================================
# # # services/payment_entry_service.py
# # #
# # # Manages local payment_entries table and syncs them to Frappe.
# # #
# # # FLOW:
# # #   1. When a sale is saved locally → create_payment_entry() stores it locally
# # #      with synced=0
# # #   2. When the Sales Invoice is confirmed on Frappe (frappe_ref is set) →
# # #      push_unsynced_payment_entries() pushes the Payment Entry to Frappe
# # #   3. Frappe returns a PAY-xxxxx ref → stored as frappe_payment_ref, synced=1
# # #
# # # PAYLOAD SENT TO FRAPPE:
# # #   POST /api/resource/Payment Entry
# # #   {
# # #     "doctype":              "Payment Entry",
# # #     "payment_type":         "Receive",
# # #     "party_type":           "Customer",
# # #     "party":                "Cathy",
# # #     "paid_to":              "Cash ZWG - H",
# # #     "paid_to_account_currency": "USD",
# # #     "paid_amount":          32.45,
# # #     "received_amount":      32.45,
# # #     "source_exchange_rate": 1.0,
# # #     "reference_no":         "ACC-SINV-2026-00034",
# # #     "reference_date":       "2026-03-19",
# # #     "remarks":              "POS Payment — Cash",
# # #     "docstatus":            1,
# # #     "references": [{
# # #         "reference_doctype": "Sales Invoice",
# # #         "reference_name":    "ACC-SINV-2026-00565",
# # #         "allocated_amount":  32.45
# # #     }]
# # #   }
# # # =============================================================================

# # from __future__ import annotations

# # import json
# # import logging
# # import time
# # import threading
# # import urllib.request
# # import urllib.error
# # from datetime import date

# # log = logging.getLogger("PaymentEntry")

# # SYNC_INTERVAL   = 60      # seconds between auto-sync cycles
# # REQUEST_TIMEOUT = 30

# # # Exchange rate cache: "FROM::TO::DATE" → float
# # _RATE_CACHE: dict[str, float] = {}


# # def _get_exchange_rate(from_currency: str, to_currency: str,
# #                        transaction_date: str,
# #                        api_key: str, api_secret: str, host: str) -> float:
# #     """
# #     Fetch live exchange rate from Frappe.
# #     Returns 1.0 for same currency, 0.0 if fetch fails (Frappe uses its own rate).
# #     """
# #     if not from_currency or from_currency.upper() == to_currency.upper():
# #         return 1.0

# #     cache_key = f"{from_currency.upper()}::{to_currency.upper()}::{transaction_date}"
# #     if cache_key in _RATE_CACHE:
# #         return _RATE_CACHE[cache_key]

# #     try:
# #         import urllib.parse
# #         url = (
# #             f"{host}/api/method/erpnext.setup.utils.get_exchange_rate"
# #             f"?from_currency={urllib.parse.quote(from_currency)}"
# #             f"&to_currency={urllib.parse.quote(to_currency)}"
# #             f"&transaction_date={transaction_date}"
# #         )
# #         req = urllib.request.Request(url)
# #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# #             data = json.loads(r.read().decode())
# #             rate = float(data.get("message") or data.get("result") or 0)
# #             if rate > 0:
# #                 _RATE_CACHE[cache_key] = rate
# #                 log.debug("Rate %s→%s on %s: %.6f", from_currency, to_currency, transaction_date, rate)
# #                 return rate
# #     except Exception as e:
# #         log.debug("Rate fetch failed (%s→%s): %s", from_currency, to_currency, e)

# #     return 0.0

# # _sync_lock:   threading.Lock          = threading.Lock()
# # _sync_thread: threading.Thread | None = None

# # # Method → Frappe Mode of Payment name
# # _METHOD_MAP = {
# #     "CASH":     "Cash",
# #     "CARD":     "Credit Card",
# #     "C / CARD": "Credit Card",
# #     "EFTPOS":   "Credit Card",
# #     "CHECK":    "Cheque",
# #     "CHEQUE":   "Cheque",
# #     "MOBILE":   "Mobile Money",
# #     "CREDIT":   "Credit",
# #     "TRANSFER": "Bank Transfer",
# # }


# # # =============================================================================
# # # CREDENTIALS / HOST / DEFAULTS
# # # =============================================================================

# # def _get_credentials() -> tuple[str, str]:
# #     try:
# #         from services.credentials import get_credentials
# #         return get_credentials()
# #     except Exception:
# #         pass
# #     return "", ""

# # def _get_host() -> str:
# #     try:
# #         from models.company_defaults import get_defaults
# #         host = (get_defaults() or {}).get("server_api_host", "").strip().rstrip("/")
# #         if host:
# #             return host
# #     except Exception:
# #         pass
# #     return "https://apk.havano.cloud"


# # def _get_defaults() -> dict:
# #     try:
# #         from models.company_defaults import get_defaults
# #         return get_defaults() or {}
# #     except Exception:
# #         return {}


# # # =============================================================================
# # # GL ACCOUNT RESOLVER  (which account to credit for each payment method)
# # # =============================================================================

# # _ACCOUNT_CACHE: dict[str, str] = {}


# # def _resolve_paid_to_account(mop_name: str, company: str, currency: str,
# #                               api_key: str, api_secret: str, host: str) -> str:
# #     """
# #     Looks up the GL account for a Mode of Payment from Frappe.
# #     Tries to match by currency if multiple accounts exist for the company.
# #     Falls back to server_pos_account in company_defaults.
# #     """
# #     cache_key = f"{mop_name}::{company}::{currency}"
# #     if cache_key in _ACCOUNT_CACHE:
# #         return _ACCOUNT_CACHE[cache_key]

# #     try:
# #         import urllib.parse
# #         url = (f"{host}/api/resource/Mode%20of%20Payment/"
# #                f"{urllib.parse.quote(mop_name)}?fields=[\"accounts\"]")
# #         req = urllib.request.Request(url)
# #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# #             data     = json.loads(r.read().decode())
# #             accounts = (data.get("data") or {}).get("accounts", [])

# #         company_accts = [a for a in accounts
# #                          if not company or a.get("company") == company]

# #         # Prefer account whose name contains the currency code
# #         matched = ""
# #         if currency:
# #             for a in company_accts:
# #                 if currency.upper() in (a.get("default_account") or "").upper():
# #                     matched = a["default_account"]; break

# #         if not matched and company_accts:
# #             matched = company_accts[0].get("default_account", "")

# #         if matched:
# #             _ACCOUNT_CACHE[cache_key] = matched
# #             return matched

# #     except Exception as e:
# #         log.debug("MOP account lookup failed for '%s': %s", mop_name, e)

# #     # Fallback
# #     fallback = _get_defaults().get("server_pos_account", "").strip()
# #     if fallback:
# #         _ACCOUNT_CACHE[cache_key] = fallback
# #         return fallback

# #     log.warning("No GL account for MOP '%s' currency=%s — Payment Entry may fail.",
# #                 mop_name, currency)
# #     return ""


# # # =============================================================================
# # # LOCAL DB  — create / read / update payment_entries
# # # =============================================================================

# # def create_payment_entry(sale: dict, override_rate: float = None,
# #                          override_account: str = None) -> int | None:
# #     """
# #     Called immediately after a sale is saved locally.
# #     Stores a payment_entry row with synced=0.
# #     Returns the new payment_entry id, or None on error.

# #     Will only create the entry once per sale (idempotent).
# #     """
# #     from database.db import get_connection
# #     conn = get_connection(); cur = conn.cursor()

# #     # Idempotency: don't create twice for the same sale
# #     cur.execute("SELECT id FROM payment_entries WHERE sale_id = ?", (sale["id"],))
# #     if cur.fetchone():
# #         conn.close()
# #         return None

# #     customer   = (sale.get("customer_name") or "default").strip()
# #     currency   = (sale.get("currency")      or "USD").strip().upper()
# #     amount     = float(sale.get("total")    or 0)
# #     inv_no     = sale.get("invoice_no", "")
# #     inv_date   = sale.get("invoice_date") or date.today().isoformat()
# #     method     = str(sale.get("method", "CASH")).upper().strip()
# #     mop        = _METHOD_MAP.get(method, "Cash")

# #     # Use override rate (from split) or fetch from Frappe
# #     if override_rate is not None:
# #         exch_rate = override_rate
# #     else:
# #         try:
# #             api_key, api_secret = _get_credentials()
# #             host = _get_host()
# #             defaults = _get_defaults()
# #             company_currency = defaults.get("server_company_currency", "USD").strip().upper() or "USD"
# #             exch_rate = _get_exchange_rate(
# #                 currency, company_currency, inv_date, api_key, api_secret, host
# #             ) if currency != company_currency else 1.0
# #         except Exception:
# #             exch_rate = 1.0

# #     cur.execute("""
# #         INSERT INTO payment_entries (
# #             sale_id, sale_invoice_no, frappe_invoice_ref,
# #             party, party_name,
# #             paid_amount, received_amount, source_exchange_rate,
# #             paid_to_account_currency, currency,
# #             mode_of_payment,
# #             reference_no, reference_date,
# #             remarks, synced
# #         ) OUTPUT INSERTED.id
# #         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# #     """, (
# #         sale["id"], inv_no,
# #         sale.get("frappe_ref") or None,
# #         customer, customer,
# #         amount, amount, exch_rate or 1.0,
# #         currency, currency,
# #         mop,
# #         inv_no, inv_date,
# #         f"POS Payment — {mop}",
# #     ))
# #     new_id = int(cur.fetchone()[0])
# #     conn.commit(); conn.close()
# #     log.debug("Payment entry %d created locally for sale %s", new_id, inv_no)
# #     return new_id


# # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# #     """
# #     Called when cashier uses Split payment.
# #     Creates one payment_entry row per currency in splits list.
# #     splits = [{"mode": "CASH", "currency": "USD", "amount": 5.0,
# #                "rate": 1.0, "base_amount": 5.0, "account": "Cash - AT"}, ...]
# #     Returns list of new payment_entry ids.
# #     """
# #     ids = []
# #     for split in splits:
# #         if not split.get("amount") or float(split["amount"]) <= 0:
# #             continue
# #         # Build a sale-like dict with the split's currency and amount
# #         split_sale = dict(sale)
# #         split_sale["currency"]      = split.get("currency", "USD")
# #         split_sale["total"]         = float(split.get("amount", 0))
# #         split_sale["method"]        = split.get("mode", "CASH")
# #         # Override exchange rate from split data
# #         new_id = create_payment_entry(
# #             split_sale,
# #             override_rate=float(split.get("rate", 1.0)),
# #             override_account=split.get("account", ""),
# #         )
# #         if new_id:
# #             ids.append(new_id)
# #     return ids


# # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# #     """
# #     Creates one payment_entry per currency from a split payment.
# #     Groups splits by currency, sums amounts, creates one entry each.
# #     Returns list of created payment_entry ids.
# #     """
# #     from datetime import date as _date

# #     # Group by currency
# #     by_currency: dict[str, dict] = {}
# #     for s in splits:
# #         curr = s.get("account_currency", "USD").upper()
# #         if curr not in by_currency:
# #             by_currency[curr] = {
# #                 "currency":      curr,
# #                 "paid_amount":   0.0,
# #                 "base_value":    0.0,
# #                 "rate":          s.get("rate", 1.0),
# #                 "account_name":  s.get("account_name", ""),
# #                 "mode":          s.get("mode", "Cash"),
# #             }
# #         by_currency[curr]["paid_amount"] += s.get("amount_paid", 0.0)
# #         by_currency[curr]["base_value"]  += s.get("base_value",  0.0)

# #     ids = []
# #     inv_no   = sale.get("invoice_no", "")
# #     inv_date = sale.get("invoice_date") or _date.today().isoformat()
# #     customer = (sale.get("customer_name") or "default").strip()

# #     from database.db import get_connection
# #     conn = get_connection(); cur = conn.cursor()

# #     for curr, grp in by_currency.items():
# #         # Idempotency: skip if already exists for this sale+currency
# #         cur.execute(
# #             "SELECT id FROM payment_entries WHERE sale_id=? AND currency=?",
# #             (sale["id"], curr)
# #         )
# #         if cur.fetchone():
# #             continue

# #         mop = _METHOD_MAP.get(grp["mode"].upper(), "Cash")

# #         cur.execute("""
# #             INSERT INTO payment_entries (
# #                 sale_id, sale_invoice_no, frappe_invoice_ref,
# #                 party, party_name,
# #                 paid_amount, received_amount, source_exchange_rate,
# #                 paid_to_account_currency, currency,
# #                 paid_to,
# #                 mode_of_payment,
# #                 reference_no, reference_date,
# #                 remarks, synced
# #             ) OUTPUT INSERTED.id
# #             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# #         """, (
# #             sale["id"], inv_no,
# #             sale.get("frappe_ref") or None,
# #             customer, customer,
# #             grp["paid_amount"],
# #             grp["base_value"],
# #             float(grp["rate"] or 1.0),
# #             curr, curr,
# #             grp["account_name"],
# #             mop,
# #             inv_no, inv_date,
# #             f"POS Split Payment — {mop} ({curr})",
# #         ))
# #         new_id = int(cur.fetchone()[0])
# #         ids.append(new_id)
# #         log.debug("Split payment entry %d created: %s %.2f %s",
# #                   new_id, curr, grp["paid_amount"], inv_no)

# #     conn.commit(); conn.close()
# #     return ids


# # def get_unsynced_payment_entries() -> list[dict]:
# #     """
# #     Returns payment entries that are ready to push (synced=0).

# #     Two kinds of entries are included:
# #       1. Normal sale payments  — frappe_invoice_ref set directly, OR
# #                                  parent sale has a frappe_ref
# #       2. CN refund payments    — payment_type='Pay' with frappe_invoice_ref
# #                                  set by link_cn_payment_to_frappe().
# #                                  These have no parent sale frappe_ref to
# #                                  fall back on, so we must NOT require it.
# #     """
# #     from database.db import get_connection, fetchall_dicts
# #     conn = get_connection(); cur = conn.cursor()
# #     cur.execute("""
# #         SELECT pe.*, s.frappe_ref AS sale_frappe_ref
# #         FROM payment_entries pe
# #         LEFT JOIN sales s ON s.id = pe.sale_id
# #         WHERE pe.synced = 0
# #           AND (
# #               -- Normal path: frappe_invoice_ref already set on the PE row
# #               pe.frappe_invoice_ref IS NOT NULL
# #               AND pe.frappe_invoice_ref != ''
# #           OR
# #               -- Fallback for sale payments: pull ref from the parent sale
# #               (
# #                   (pe.payment_type IS NULL OR pe.payment_type = 'Receive')
# #                   AND s.frappe_ref IS NOT NULL
# #                   AND s.frappe_ref != ''
# #               )
# #           )
# #         ORDER BY pe.id
# #     """)
# #     rows = fetchall_dicts(cur); conn.close()
# #     return rows


# # def mark_payment_synced(pe_id: int, frappe_payment_ref: str = "") -> None:
# #     from database.db import get_connection
# #     conn = get_connection(); cur = conn.cursor()
# #     cur.execute(
# #         "UPDATE payment_entries SET synced=1, frappe_payment_ref=? WHERE id=?",
# #         (frappe_payment_ref or None, pe_id)
# #     )
# #     # Also update the sales row
# #     cur.execute("""
# #         UPDATE sales SET payment_entry_ref=?, payment_synced=1
# #         WHERE id = (SELECT sale_id FROM payment_entries WHERE id=?)
# #     """, (frappe_payment_ref or None, pe_id))
# #     conn.commit(); conn.close()


# # def refresh_frappe_refs() -> int:
# #     """
# #     For payment entries that have no frappe_invoice_ref yet, copy it from
# #     the parent sale's frappe_ref. Call this before pushing payments.
# #     Returns count updated.
# #     """
# #     from database.db import get_connection
# #     conn = get_connection(); cur = conn.cursor()
# #     cur.execute("""
# #         UPDATE pe
# #         SET pe.frappe_invoice_ref = s.frappe_ref
# #         FROM payment_entries pe
# #         JOIN sales s ON s.id = pe.sale_id
# #         WHERE pe.synced = 0
# #           AND (pe.frappe_invoice_ref IS NULL OR pe.frappe_invoice_ref = '')
# #           AND s.frappe_ref IS NOT NULL AND s.frappe_ref != ''
# #     """)
# #     count = cur.rowcount
# #     conn.commit(); conn.close()
# #     return count


# # # =============================================================================
# # # BUILD FRAPPE PAYLOAD
# # # =============================================================================

# # def _build_payload(pe: dict, defaults: dict,
# #                    api_key: str, api_secret: str, host: str) -> dict:
# #     company  = defaults.get("server_company", "")
# #     currency = (pe.get("currency") or pe.get("paid_to_account_currency") or "USD").upper()
# #     mop      = pe.get("mode_of_payment") or "Cash"
# #     amount   = float(pe.get("paid_amount") or 0)
# #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()

# #     # Use local gl_accounts table first (synced from Frappe)
# #     paid_to          = (pe.get("paid_to") or "").strip()
# #     paid_to_currency = currency
# #     if not paid_to:
# #         try:
# #             from models.gl_account import get_account_for_payment
# #             acct = get_account_for_payment(currency, company)
# #             if acct:
# #                 paid_to          = acct["name"]
# #                 paid_to_currency = acct["account_currency"]
# #         except Exception as _e:
# #             log.debug("gl_account lookup failed: %s", _e)

# #     # Fallback to live Frappe lookup
# #     if not paid_to:
# #         paid_to = _resolve_paid_to_account(mop, company, currency, api_key, api_secret, host)

# #     # Use local exchange rate if not stored
# #     exch_rate = float(pe.get("source_exchange_rate") or 1.0)
# #     if exch_rate == 1.0 and currency not in ("USD", ""):
# #         try:
# #             from models.exchange_rate import get_rate
# #             stored = get_rate(currency, "USD")
# #             if stored:
# #                 exch_rate = stored
# #         except Exception:
# #             pass

# #     # Respect the payment_type stored on the row — CN refunds are 'Pay'
# #     payment_type = (pe.get("payment_type") or "Receive").strip() or "Receive"
# #     is_refund    = payment_type == "Pay"

# #     ref_date = pe.get("reference_date")
# #     ref_date_str = (
# #         ref_date.isoformat()
# #         if hasattr(ref_date, "isoformat")
# #         else ref_date or date.today().isoformat()
# #     )

# #     payload = {
# #         "doctype":       "Payment Entry",
# #         "payment_type":  payment_type,
# #         "party_type":    "Customer",
# #         "party":         pe.get("party") or "default",
# #         "party_name":    pe.get("party_name") or "default",
# #         "paid_amount":   amount,
# #         "received_amount": amount,
# #         "source_exchange_rate": exch_rate,
# #         "reference_no":  pe.get("reference_no") or pe.get("sale_invoice_no", ""),
# #         "reference_date": ref_date_str,
# #         "remarks":       pe.get("remarks") or f"POS Payment — {mop}",
# #         "mode_of_payment": mop,
# #         "docstatus":     1,
# #     }

# #     if is_refund:
# #         # Money goes OUT to customer — Frappe needs paid_from (the cash/bank account)
# #         payload["paid_from_account_currency"] = paid_to_currency
# #         if paid_to:
# #             payload["paid_from"] = paid_to
# #     else:
# #         # Normal receipt — money comes IN
# #         payload["paid_to_account_currency"] = paid_to_currency
# #         if paid_to:
# #             payload["paid_to"] = paid_to

# #     if company:
# #         payload["company"] = company

# #     # Link to the Frappe Sales Invoice (original invoice for receipts, CN invoice for refunds)
# #     if frappe_inv:
# #         payload["references"] = [{
# #             "reference_doctype": "Sales Invoice",
# #             "reference_name":    frappe_inv,
# #             "allocated_amount":  amount,
# #         }]

# #     return payload


# # # =============================================================================
# # # PUSH ONE PAYMENT ENTRY
# # # =============================================================================

# # def _push_payment_entry(pe: dict, api_key: str, api_secret: str,
# #                         defaults: dict, host: str) -> str | None:
# #     """
# #     Posts one payment entry to Frappe.
# #     Returns Frappe's PAY-xxxxx name on success, None on failure.
# #     """
# #     pe_id  = pe["id"]
# #     inv_no = pe.get("sale_invoice_no", str(pe_id))

# #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()
# #     if not frappe_inv:
# #         log.warning("Payment %d — Sales Invoice not yet on Frappe, skipping.", pe_id)
# #         return None

# #     payload = _build_payload(pe, defaults, api_key, api_secret, host)

# #     url = f"{host}/api/resource/Payment%20Entry"
# #     req = urllib.request.Request(
# #         url=url,
# #         data=json.dumps(payload, default=lambda o: o.isoformat() if hasattr(o, 'isoformat') else str(o)).encode("utf-8"),
# #         method="POST",
# #         headers={
# #             "Content-Type":  "application/json",
# #             "Accept":        "application/json",
# #             "Authorization": f"token {api_key}:{api_secret}",
# #         },
# #     )

# #     try:
# #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
# #             data = json.loads(resp.read().decode())
# #             name = (data.get("data") or {}).get("name", "")
# #             log.info("✅ Payment Entry %d → Frappe %s  [%s  %s %.2f]",
# #                      pe_id, name, inv_no,
# #                      pe.get("currency", ""), float(pe.get("paid_amount", 0)))
# #             return name or "SYNCED"

# #     except urllib.error.HTTPError as e:
# #         try:
# #             err = json.loads(e.read().decode())
# #             msg = (err.get("exception") or err.get("message") or
# #                    str(err.get("_server_messages", "")) or f"HTTP {e.code}")
# #         except Exception:
# #             msg = f"HTTP {e.code}"

# #         if e.code == 409:
# #             log.info("Payment %d already on Frappe (409) - marking synced.", pe_id)
# #             return "DUPLICATE"

# #         # Invoice already paid (is_pos:1 on old invoices) - stop retrying
# #         if e.code == 417:
# #             _perma = ("already been fully paid", "already paid", "fully paid")
# #             if any(p in msg.lower() for p in _perma):
# #                 log.info("Payment %d - invoice already paid on Frappe, marking synced.", pe_id)
# #                 return "ALREADY_PAID"

# #         log.error("FAIL Payment Entry %d  HTTP %s: %s", pe_id, e.code, msg)
# #         return None

# #     except urllib.error.URLError as e:
# #         log.warning("Network error pushing payment %d: %s", pe_id, e.reason)
# #         return None

# #     except Exception as e:
# #         log.error("Unexpected error pushing payment %d: %s", pe_id, e)
# #         return None


# # # =============================================================================
# # # PUBLIC — push all unsynced payment entries
# # # =============================================================================

# # def push_unsynced_payment_entries() -> dict:
# #     """
# #     1. Refresh frappe_invoice_ref from parent sales that were confirmed.
# #     2. Push each unsynced payment entry to Frappe.
# #     3. Mark synced with the returned PAY-xxxxx ref.
# #     """
# #     result = {"pushed": 0, "failed": 0, "skipped": 0, "total": 0}

# #     api_key, api_secret = _get_credentials()
# #     if not api_key or not api_secret:
# #         log.warning("No credentials — skipping payment entry sync.")
# #         return result

# #     host     = _get_host()
# #     defaults = _get_defaults()

# #     # First: pull frappe_refs from confirmed invoices into pending payment entries
# #     updated = refresh_frappe_refs()
# #     if updated:
# #         log.info("Refreshed frappe_invoice_ref on %d payment entry(ies).", updated)

# #     entries = get_unsynced_payment_entries()
# #     result["total"] = len(entries)

# #     if not entries:
# #         log.debug("No unsynced payment entries.")
# #         return result

# #     log.info("Pushing %d payment entry(ies) to Frappe…", len(entries))

# #     for pe in entries:
# #         frappe_name = _push_payment_entry(pe, api_key, api_secret, defaults, host)
# #         if frappe_name:
# #             mark_payment_synced(pe["id"], frappe_name)
# #             result["pushed"] += 1
# #         elif frappe_name is None:
# #             # None = permanent skip (no frappe_inv yet), not a real failure
# #             result["skipped"] += 1
# #         else:
# #             result["failed"] += 1

# #         time.sleep(3)   # rate limit — 20/min max

# #     log.info("Payment sync done — ✅ %d pushed  ❌ %d failed  ⏭ %d skipped",
# #              result["pushed"], result["failed"], result["skipped"])
# #     return result


# # # =============================================================================
# # # BACKGROUND DAEMON THREAD
# # # =============================================================================

# # def _sync_loop():
# #     log.info("Payment entry sync daemon started (interval=%ds).", SYNC_INTERVAL)
# #     while True:
# #         if _sync_lock.acquire(blocking=False):
# #             try:
# #                 push_unsynced_payment_entries()
# #             except Exception as e:
# #                 log.error("Payment sync cycle error: %s", e)
# #             finally:
# #                 _sync_lock.release()
# #         else:
# #             log.debug("Previous payment sync still running — skipping.")
# #         time.sleep(SYNC_INTERVAL)


# # def start_payment_sync_daemon() -> threading.Thread:
# #     """Non-blocking — safe to call from MainWindow.__init__."""
# #     global _sync_thread
# #     if _sync_thread and _sync_thread.is_alive():
# #         return _sync_thread
# #     t = threading.Thread(target=_sync_loop, daemon=True, name="PaymentSyncDaemon")
# #     t.start()
# #     _sync_thread = t
# #     log.info("Payment entry sync daemon started.")
# #     return t


# # # =============================================================================
# # # DEBUG
# # # =============================================================================

# # if __name__ == "__main__":
# #     logging.basicConfig(level=logging.INFO,
# #                         format="%(asctime)s [%(levelname)s] %(message)s")
# #     print("Running one payment entry sync cycle...")
# #     r = push_unsynced_payment_entries()
# #     print(f"\nResult: {r['pushed']} pushed, {r['failed']} failed, "
# #           f"{r['skipped']} skipped (of {r['total']} total)")

# # # # # # =============================================================================
# # # # # # services/payment_entry_service.py
# # # # # #
# # # # # # Manages local payment_entries table and syncs them to Frappe.
# # # # # #
# # # # # # FLOW:
# # # # # #   1. When a sale is saved locally → create_payment_entry() stores it locally
# # # # # #      with synced=0
# # # # # #   2. When the Sales Invoice is confirmed on Frappe (frappe_ref is set) →
# # # # # #      push_unsynced_payment_entries() pushes the Payment Entry to Frappe
# # # # # #   3. Frappe returns a PAY-xxxxx ref → stored as frappe_payment_ref, synced=1
# # # # # #
# # # # # # PAYLOAD SENT TO FRAPPE:
# # # # # #   POST /api/resource/Payment Entry
# # # # # #   {
# # # # # #     "doctype":              "Payment Entry",
# # # # # #     "payment_type":         "Receive",
# # # # # #     "party_type":           "Customer",
# # # # # #     "party":                "Cathy",
# # # # # #     "paid_to":              "Cash ZWG - H",
# # # # # #     "paid_to_account_currency": "USD",
# # # # # #     "paid_amount":          32.45,
# # # # # #     "received_amount":      32.45,
# # # # # #     "source_exchange_rate": 1.0,
# # # # # #     "reference_no":         "ACC-SINV-2026-00034",
# # # # # #     "reference_date":       "2026-03-19",
# # # # # #     "remarks":              "POS Payment — Cash",
# # # # # #     "docstatus":            1,
# # # # # #     "references": [{
# # # # # #         "reference_doctype": "Sales Invoice",
# # # # # #         "reference_name":    "ACC-SINV-2026-00565",
# # # # # #         "allocated_amount":  32.45
# # # # # #     }]
# # # # # #   }
# # # # # # =============================================================================

# # # # # from __future__ import annotations

# # # # # import json
# # # # # import logging
# # # # # import time
# # # # # import threading
# # # # # import urllib.request
# # # # # import urllib.error
# # # # # from datetime import date

# # # # # log = logging.getLogger("PaymentEntry")

# # # # # SYNC_INTERVAL   = 60      # seconds between auto-sync cycles
# # # # # REQUEST_TIMEOUT = 30

# # # # # # Exchange rate cache: "FROM::TO::DATE" → float
# # # # # _RATE_CACHE: dict[str, float] = {}


# # # # # def _get_exchange_rate(from_currency: str, to_currency: str,
# # # # #                        transaction_date: str,
# # # # #                        api_key: str, api_secret: str, host: str) -> float:
# # # # #     """
# # # # #     Fetch live exchange rate from Frappe.
# # # # #     Returns 1.0 for same currency, 0.0 if fetch fails (Frappe uses its own rate).
# # # # #     """
# # # # #     if not from_currency or from_currency.upper() == to_currency.upper():
# # # # #         return 1.0

# # # # #     cache_key = f"{from_currency.upper()}::{to_currency.upper()}::{transaction_date}"
# # # # #     if cache_key in _RATE_CACHE:
# # # # #         return _RATE_CACHE[cache_key]

# # # # #     try:
# # # # #         import urllib.parse
# # # # #         url = (
# # # # #             f"{host}/api/method/erpnext.setup.utils.get_exchange_rate"
# # # # #             f"?from_currency={urllib.parse.quote(from_currency)}"
# # # # #             f"&to_currency={urllib.parse.quote(to_currency)}"
# # # # #             f"&transaction_date={transaction_date}"
# # # # #         )
# # # # #         req = urllib.request.Request(url)
# # # # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # # # #             data = json.loads(r.read().decode())
# # # # #             rate = float(data.get("message") or data.get("result") or 0)
# # # # #             if rate > 0:
# # # # #                 _RATE_CACHE[cache_key] = rate
# # # # #                 log.debug("Rate %s→%s on %s: %.6f", from_currency, to_currency, transaction_date, rate)
# # # # #                 return rate
# # # # #     except Exception as e:
# # # # #         log.debug("Rate fetch failed (%s→%s): %s", from_currency, to_currency, e)

# # # # #     return 0.0

# # # # # _sync_lock:   threading.Lock          = threading.Lock()
# # # # # _sync_thread: threading.Thread | None = None

# # # # # # Method → Frappe Mode of Payment name
# # # # # _METHOD_MAP = {
# # # # #     "CASH":     "Cash",
# # # # #     "CARD":     "Credit Card",
# # # # #     "C / CARD": "Credit Card",
# # # # #     "EFTPOS":   "Credit Card",
# # # # #     "CHECK":    "Cheque",
# # # # #     "CHEQUE":   "Cheque",
# # # # #     "MOBILE":   "Mobile Money",
# # # # #     "CREDIT":   "Credit",
# # # # #     "TRANSFER": "Bank Transfer",
# # # # # }


# # # # # # =============================================================================
# # # # # # CREDENTIALS / HOST / DEFAULTS
# # # # # # =============================================================================

# # # # # def _get_credentials() -> tuple[str, str]:
# # # # #     try:
# # # # #         from services.auth_service import get_session
# # # # #         s = get_session()
# # # # #         if s.get("api_key") and s.get("api_secret"):
# # # # #             return s["api_key"], s["api_secret"]
# # # # #     except Exception:
# # # # #         pass
# # # # #     try:
# # # # #         from database.db import get_connection
# # # # #         conn = get_connection(); cur = conn.cursor()
# # # # #         cur.execute("SELECT api_key, api_secret FROM company_defaults WHERE id = 1")
# # # # #         row = cur.fetchone(); conn.close()
# # # # #         if row and row[0] and row[1]:
# # # # #             return row[0], row[1]
# # # # #     except Exception:
# # # # #         pass
# # # # #     import os
# # # # #     return os.environ.get("HAVANO_API_KEY", ""), os.environ.get("HAVANO_API_SECRET", "")


# # # # # def _get_host() -> str:
# # # # #     try:
# # # # #         from models.company_defaults import get_defaults
# # # # #         host = (get_defaults() or {}).get("server_api_host", "").strip().rstrip("/")
# # # # #         if host:
# # # # #             return host
# # # # #     except Exception:
# # # # #         pass
# # # # #     return "https://apk.havano.cloud"


# # # # # def _get_defaults() -> dict:
# # # # #     try:
# # # # #         from models.company_defaults import get_defaults
# # # # #         return get_defaults() or {}
# # # # #     except Exception:
# # # # #         return {}


# # # # # # =============================================================================
# # # # # # GL ACCOUNT RESOLVER  (which account to credit for each payment method)
# # # # # # =============================================================================

# # # # # _ACCOUNT_CACHE: dict[str, str] = {}


# # # # # def _resolve_paid_to_account(mop_name: str, company: str, currency: str,
# # # # #                               api_key: str, api_secret: str, host: str) -> str:
# # # # #     """
# # # # #     Looks up the GL account for a Mode of Payment from Frappe.
# # # # #     Tries to match by currency if multiple accounts exist for the company.
# # # # #     Falls back to server_pos_account in company_defaults.
# # # # #     """
# # # # #     cache_key = f"{mop_name}::{company}::{currency}"
# # # # #     if cache_key in _ACCOUNT_CACHE:
# # # # #         return _ACCOUNT_CACHE[cache_key]

# # # # #     try:
# # # # #         import urllib.parse
# # # # #         url = (f"{host}/api/resource/Mode%20of%20Payment/"
# # # # #                f"{urllib.parse.quote(mop_name)}?fields=[\"accounts\"]")
# # # # #         req = urllib.request.Request(url)
# # # # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # # # #             data     = json.loads(r.read().decode())
# # # # #             accounts = (data.get("data") or {}).get("accounts", [])

# # # # #         company_accts = [a for a in accounts
# # # # #                          if not company or a.get("company") == company]

# # # # #         # Prefer account whose name contains the currency code
# # # # #         matched = ""
# # # # #         if currency:
# # # # #             for a in company_accts:
# # # # #                 if currency.upper() in (a.get("default_account") or "").upper():
# # # # #                     matched = a["default_account"]; break

# # # # #         if not matched and company_accts:
# # # # #             matched = company_accts[0].get("default_account", "")

# # # # #         if matched:
# # # # #             _ACCOUNT_CACHE[cache_key] = matched
# # # # #             return matched

# # # # #     except Exception as e:
# # # # #         log.debug("MOP account lookup failed for '%s': %s", mop_name, e)

# # # # #     # Fallback
# # # # #     fallback = _get_defaults().get("server_pos_account", "").strip()
# # # # #     if fallback:
# # # # #         _ACCOUNT_CACHE[cache_key] = fallback
# # # # #         return fallback

# # # # #     log.warning("No GL account for MOP '%s' currency=%s — Payment Entry may fail.",
# # # # #                 mop_name, currency)
# # # # #     return ""


# # # # # # =============================================================================
# # # # # # LOCAL DB  — create / read / update payment_entries
# # # # # # =============================================================================

# # # # # def create_payment_entry(sale: dict, override_rate: float = None,
# # # # #                          override_account: str = None) -> int | None:
# # # # #     """
# # # # #     Called immediately after a sale is saved locally.
# # # # #     Stores a payment_entry row with synced=0.
# # # # #     Returns the new payment_entry id, or None on error.

# # # # #     Will only create the entry once per sale (idempotent).
# # # # #     """
# # # # #     from database.db import get_connection
# # # # #     conn = get_connection(); cur = conn.cursor()

# # # # #     # Idempotency: don't create twice for the same sale
# # # # #     cur.execute("SELECT id FROM payment_entries WHERE sale_id = ?", (sale["id"],))
# # # # #     if cur.fetchone():
# # # # #         conn.close()
# # # # #         return None

# # # # #     customer   = (sale.get("customer_name") or "default").strip()
# # # # #     currency   = (sale.get("currency")      or "USD").strip().upper()
# # # # #     amount     = float(sale.get("total")    or 0)
# # # # #     inv_no     = sale.get("invoice_no", "")
# # # # #     inv_date   = sale.get("invoice_date") or date.today().isoformat()
# # # # #     method     = str(sale.get("method", "CASH")).upper().strip()
# # # # #     mop        = _METHOD_MAP.get(method, "Cash")

# # # # #     # Use override rate (from split) or fetch from Frappe
# # # # #     if override_rate is not None:
# # # # #         exch_rate = override_rate
# # # # #     else:
# # # # #         try:
# # # # #             api_key, api_secret = _get_credentials()
# # # # #             host = _get_host()
# # # # #             defaults = _get_defaults()
# # # # #             company_currency = defaults.get("server_company_currency", "USD").strip().upper() or "USD"
# # # # #             exch_rate = _get_exchange_rate(
# # # # #                 currency, company_currency, inv_date, api_key, api_secret, host
# # # # #             ) if currency != company_currency else 1.0
# # # # #         except Exception:
# # # # #             exch_rate = 1.0

# # # # #     cur.execute("""
# # # # #         INSERT INTO payment_entries (
# # # # #             sale_id, sale_invoice_no, frappe_invoice_ref,
# # # # #             party, party_name,
# # # # #             paid_amount, received_amount, source_exchange_rate,
# # # # #             paid_to_account_currency, currency,
# # # # #             mode_of_payment,
# # # # #             reference_no, reference_date,
# # # # #             remarks, synced
# # # # #         ) OUTPUT INSERTED.id
# # # # #         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # # # #     """, (
# # # # #         sale["id"], inv_no,
# # # # #         sale.get("frappe_ref") or None,
# # # # #         customer, customer,
# # # # #         amount, amount, exch_rate or 1.0,
# # # # #         currency, currency,
# # # # #         mop,
# # # # #         inv_no, inv_date,
# # # # #         f"POS Payment — {mop}",
# # # # #     ))
# # # # #     new_id = int(cur.fetchone()[0])
# # # # #     conn.commit(); conn.close()
# # # # #     log.debug("Payment entry %d created locally for sale %s", new_id, inv_no)
# # # # #     return new_id


# # # # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # # # #     """
# # # # #     Called when cashier uses Split payment.
# # # # #     Creates one payment_entry row per currency in splits list.
# # # # #     splits = [{"mode": "CASH", "currency": "USD", "amount": 5.0,
# # # # #                "rate": 1.0, "base_amount": 5.0, "account": "Cash - AT"}, ...]
# # # # #     Returns list of new payment_entry ids.
# # # # #     """
# # # # #     ids = []
# # # # #     for split in splits:
# # # # #         if not split.get("amount") or float(split["amount"]) <= 0:
# # # # #             continue
# # # # #         # Build a sale-like dict with the split's currency and amount
# # # # #         split_sale = dict(sale)
# # # # #         split_sale["currency"]      = split.get("currency", "USD")
# # # # #         split_sale["total"]         = float(split.get("amount", 0))
# # # # #         split_sale["method"]        = split.get("mode", "CASH")
# # # # #         # Override exchange rate from split data
# # # # #         new_id = create_payment_entry(
# # # # #             split_sale,
# # # # #             override_rate=float(split.get("rate", 1.0)),
# # # # #             override_account=split.get("account", ""),
# # # # #         )
# # # # #         if new_id:
# # # # #             ids.append(new_id)
# # # # #     return ids


# # # # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # # # #     """
# # # # #     Creates one payment_entry per currency from a split payment.
# # # # #     Groups splits by currency, sums amounts, creates one entry each.
# # # # #     Returns list of created payment_entry ids.
# # # # #     """
# # # # #     from datetime import date as _date

# # # # #     # Group by currency
# # # # #     by_currency: dict[str, dict] = {}
# # # # #     for s in splits:
# # # # #         curr = s.get("account_currency", "USD").upper()
# # # # #         if curr not in by_currency:
# # # # #             by_currency[curr] = {
# # # # #                 "currency":      curr,
# # # # #                 "paid_amount":   0.0,
# # # # #                 "base_value":    0.0,
# # # # #                 "rate":          s.get("rate", 1.0),
# # # # #                 "account_name":  s.get("account_name", ""),
# # # # #                 "mode":          s.get("mode", "Cash"),
# # # # #             }
# # # # #         by_currency[curr]["paid_amount"] += s.get("amount_paid", 0.0)
# # # # #         by_currency[curr]["base_value"]  += s.get("base_value",  0.0)

# # # # #     ids = []
# # # # #     inv_no   = sale.get("invoice_no", "")
# # # # #     inv_date = sale.get("invoice_date") or _date.today().isoformat()
# # # # #     customer = (sale.get("customer_name") or "default").strip()

# # # # #     from database.db import get_connection
# # # # #     conn = get_connection(); cur = conn.cursor()

# # # # #     for curr, grp in by_currency.items():
# # # # #         # Idempotency: skip if already exists for this sale+currency
# # # # #         cur.execute(
# # # # #             "SELECT id FROM payment_entries WHERE sale_id=? AND currency=?",
# # # # #             (sale["id"], curr)
# # # # #         )
# # # # #         if cur.fetchone():
# # # # #             continue

# # # # #         mop = _METHOD_MAP.get(grp["mode"].upper(), "Cash")

# # # # #         cur.execute("""
# # # # #             INSERT INTO payment_entries (
# # # # #                 sale_id, sale_invoice_no, frappe_invoice_ref,
# # # # #                 party, party_name,
# # # # #                 paid_amount, received_amount, source_exchange_rate,
# # # # #                 paid_to_account_currency, currency,
# # # # #                 paid_to,
# # # # #                 mode_of_payment,
# # # # #                 reference_no, reference_date,
# # # # #                 remarks, synced
# # # # #             ) OUTPUT INSERTED.id
# # # # #             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # # # #         """, (
# # # # #             sale["id"], inv_no,
# # # # #             sale.get("frappe_ref") or None,
# # # # #             customer, customer,
# # # # #             grp["paid_amount"],
# # # # #             grp["base_value"],
# # # # #             float(grp["rate"] or 1.0),
# # # # #             curr, curr,
# # # # #             grp["account_name"],
# # # # #             mop,
# # # # #             inv_no, inv_date,
# # # # #             f"POS Split Payment — {mop} ({curr})",
# # # # #         ))
# # # # #         new_id = int(cur.fetchone()[0])
# # # # #         ids.append(new_id)
# # # # #         log.debug("Split payment entry %d created: %s %.2f %s",
# # # # #                   new_id, curr, grp["paid_amount"], inv_no)

# # # # #     conn.commit(); conn.close()
# # # # #     return ids


# # # # # def get_unsynced_payment_entries() -> list[dict]:
# # # # #     """Returns payment entries that are ready to push (synced=0)."""
# # # # #     from database.db import get_connection, fetchall_dicts
# # # # #     conn = get_connection(); cur = conn.cursor()
# # # # #     cur.execute("""
# # # # #         SELECT pe.*, s.frappe_ref AS sale_frappe_ref
# # # # #         FROM payment_entries pe
# # # # #         LEFT JOIN sales s ON s.id = pe.sale_id
# # # # #         WHERE pe.synced = 0
# # # # #           AND (pe.frappe_invoice_ref IS NOT NULL
# # # # #                OR s.frappe_ref IS NOT NULL)
# # # # #         ORDER BY pe.id
# # # # #     """)
# # # # #     rows = fetchall_dicts(cur); conn.close()
# # # # #     return rows


# # # # # def mark_payment_synced(pe_id: int, frappe_payment_ref: str = "") -> None:
# # # # #     from database.db import get_connection
# # # # #     conn = get_connection(); cur = conn.cursor()
# # # # #     cur.execute(
# # # # #         "UPDATE payment_entries SET synced=1, frappe_payment_ref=? WHERE id=?",
# # # # #         (frappe_payment_ref or None, pe_id)
# # # # #     )
# # # # #     # Also update the sales row
# # # # #     cur.execute("""
# # # # #         UPDATE sales SET payment_entry_ref=?, payment_synced=1
# # # # #         WHERE id = (SELECT sale_id FROM payment_entries WHERE id=?)
# # # # #     """, (frappe_payment_ref or None, pe_id))
# # # # #     conn.commit(); conn.close()


# # # # # def refresh_frappe_refs() -> int:
# # # # #     """
# # # # #     For payment entries that have no frappe_invoice_ref yet, copy it from
# # # # #     the parent sale's frappe_ref. Call this before pushing payments.
# # # # #     Returns count updated.
# # # # #     """
# # # # #     from database.db import get_connection
# # # # #     conn = get_connection(); cur = conn.cursor()
# # # # #     cur.execute("""
# # # # #         UPDATE pe
# # # # #         SET pe.frappe_invoice_ref = s.frappe_ref
# # # # #         FROM payment_entries pe
# # # # #         JOIN sales s ON s.id = pe.sale_id
# # # # #         WHERE pe.synced = 0
# # # # #           AND (pe.frappe_invoice_ref IS NULL OR pe.frappe_invoice_ref = '')
# # # # #           AND s.frappe_ref IS NOT NULL AND s.frappe_ref != ''
# # # # #     """)
# # # # #     count = cur.rowcount
# # # # #     conn.commit(); conn.close()
# # # # #     return count


# # # # # # =============================================================================
# # # # # # BUILD FRAPPE PAYLOAD
# # # # # # =============================================================================

# # # # # def _build_payload(pe: dict, defaults: dict,
# # # # #                    api_key: str, api_secret: str, host: str) -> dict:
# # # # #     company  = defaults.get("server_company", "")
# # # # #     currency = (pe.get("currency") or pe.get("paid_to_account_currency") or "USD").upper()
# # # # #     mop      = pe.get("mode_of_payment") or "Cash"
# # # # #     amount   = float(pe.get("paid_amount") or 0)
# # # # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()

# # # # #     paid_to = _resolve_paid_to_account(mop, company, currency, api_key, api_secret, host)

# # # # #     payload = {
# # # # #         "doctype":                  "Payment Entry",
# # # # #         "payment_type":             "Receive",
# # # # #         "party_type":               "Customer",
# # # # #         "party":                    pe.get("party") or "default",
# # # # #         "party_name":               pe.get("party_name") or "default",
# # # # #         "paid_to_account_currency": currency,
# # # # #         "paid_amount":              amount,
# # # # #         "received_amount":          amount,
# # # # #         "source_exchange_rate":     float(pe.get("source_exchange_rate") or 1.0),
# # # # #         "reference_no":             pe.get("reference_no") or pe.get("sale_invoice_no", ""),
# # # # #         "reference_date":           pe.get("reference_date") or date.today().isoformat(),
# # # # #         "remarks":                  pe.get("remarks") or f"POS Payment — {mop}",
# # # # #         "mode_of_payment":          mop,
# # # # #         "docstatus":                1,
# # # # #     }

# # # # #     if paid_to:
# # # # #         payload["paid_to"] = paid_to
# # # # #     if company:
# # # # #         payload["company"] = company

# # # # #     # Link to the Sales Invoice on Frappe
# # # # #     if frappe_inv:
# # # # #         payload["references"] = [{
# # # # #             "reference_doctype": "Sales Invoice",
# # # # #             "reference_name":    frappe_inv,
# # # # #             "allocated_amount":  amount,
# # # # #         }]

# # # # #     return payload


# # # # # # =============================================================================
# # # # # # PUSH ONE PAYMENT ENTRY
# # # # # # =============================================================================

# # # # # def _push_payment_entry(pe: dict, api_key: str, api_secret: str,
# # # # #                         defaults: dict, host: str) -> str | None:
# # # # #     """
# # # # #     Posts one payment entry to Frappe.
# # # # #     Returns Frappe's PAY-xxxxx name on success, None on failure.
# # # # #     """
# # # # #     pe_id  = pe["id"]
# # # # #     inv_no = pe.get("sale_invoice_no", str(pe_id))

# # # # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()
# # # # #     if not frappe_inv:
# # # # #         log.warning("Payment %d — Sales Invoice not yet on Frappe, skipping.", pe_id)
# # # # #         return None

# # # # #     payload = _build_payload(pe, defaults, api_key, api_secret, host)

# # # # #     url = f"{host}/api/resource/Payment%20Entry"
# # # # #     req = urllib.request.Request(
# # # # #         url=url,
# # # # #         data=json.dumps(payload).encode("utf-8"),
# # # # #         method="POST",
# # # # #         headers={
# # # # #             "Content-Type":  "application/json",
# # # # #             "Accept":        "application/json",
# # # # #             "Authorization": f"token {api_key}:{api_secret}",
# # # # #         },
# # # # #     )

# # # # #     try:
# # # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
# # # # #             data = json.loads(resp.read().decode())
# # # # #             name = (data.get("data") or {}).get("name", "")
# # # # #             log.info("✅ Payment Entry %d → Frappe %s  [%s  %s %.2f]",
# # # # #                      pe_id, name, inv_no,
# # # # #                      pe.get("currency", ""), float(pe.get("paid_amount", 0)))
# # # # #             return name or "SYNCED"

# # # # #     except urllib.error.HTTPError as e:
# # # # #         try:
# # # # #             err = json.loads(e.read().decode())
# # # # #             msg = (err.get("exception") or err.get("message") or
# # # # #                    str(err.get("_server_messages", "")) or f"HTTP {e.code}")
# # # # #         except Exception:
# # # # #             msg = f"HTTP {e.code}"

# # # # #         if e.code == 409:
# # # # #             log.info("Payment %d already on Frappe (409) — marking synced.", pe_id)
# # # # #             return "DUPLICATE"

# # # # #         log.error("❌ Payment Entry %d  HTTP %s: %s", pe_id, e.code, msg)
# # # # #         return None

# # # # #     except urllib.error.URLError as e:
# # # # #         log.warning("Network error pushing payment %d: %s", pe_id, e.reason)
# # # # #         return None

# # # # #     except Exception as e:
# # # # #         log.error("Unexpected error pushing payment %d: %s", pe_id, e)
# # # # #         return None


# # # # # # =============================================================================
# # # # # # PUBLIC — push all unsynced payment entries
# # # # # # =============================================================================

# # # # # def push_unsynced_payment_entries() -> dict:
# # # # #     """
# # # # #     1. Refresh frappe_invoice_ref from parent sales that were confirmed.
# # # # #     2. Push each unsynced payment entry to Frappe.
# # # # #     3. Mark synced with the returned PAY-xxxxx ref.
# # # # #     """
# # # # #     result = {"pushed": 0, "failed": 0, "skipped": 0, "total": 0}

# # # # #     api_key, api_secret = _get_credentials()
# # # # #     if not api_key or not api_secret:
# # # # #         log.warning("No credentials — skipping payment entry sync.")
# # # # #         return result

# # # # #     host     = _get_host()
# # # # #     defaults = _get_defaults()

# # # # #     # First: pull frappe_refs from confirmed invoices into pending payment entries
# # # # #     updated = refresh_frappe_refs()
# # # # #     if updated:
# # # # #         log.info("Refreshed frappe_invoice_ref on %d payment entry(ies).", updated)

# # # # #     entries = get_unsynced_payment_entries()
# # # # #     result["total"] = len(entries)

# # # # #     if not entries:
# # # # #         log.debug("No unsynced payment entries.")
# # # # #         return result

# # # # #     log.info("Pushing %d payment entry(ies) to Frappe…", len(entries))

# # # # #     for pe in entries:
# # # # #         frappe_name = _push_payment_entry(pe, api_key, api_secret, defaults, host)
# # # # #         if frappe_name:
# # # # #             mark_payment_synced(pe["id"], frappe_name)
# # # # #             result["pushed"] += 1
# # # # #         elif frappe_name is None:
# # # # #             # None = permanent skip (no frappe_inv yet), not a real failure
# # # # #             result["skipped"] += 1
# # # # #         else:
# # # # #             result["failed"] += 1

# # # # #         time.sleep(3)   # rate limit — 20/min max

# # # # #     log.info("Payment sync done — ✅ %d pushed  ❌ %d failed  ⏭ %d skipped",
# # # # #              result["pushed"], result["failed"], result["skipped"])
# # # # #     return result


# # # # # # =============================================================================
# # # # # # BACKGROUND DAEMON THREAD
# # # # # # =============================================================================

# # # # # def _sync_loop():
# # # # #     log.info("Payment entry sync daemon started (interval=%ds).", SYNC_INTERVAL)
# # # # #     while True:
# # # # #         if _sync_lock.acquire(blocking=False):
# # # # #             try:
# # # # #                 push_unsynced_payment_entries()
# # # # #             except Exception as e:
# # # # #                 log.error("Payment sync cycle error: %s", e)
# # # # #             finally:
# # # # #                 _sync_lock.release()
# # # # #         else:
# # # # #             log.debug("Previous payment sync still running — skipping.")
# # # # #         time.sleep(SYNC_INTERVAL)


# # # # # def start_payment_sync_daemon() -> threading.Thread:
# # # # #     """Non-blocking — safe to call from MainWindow.__init__."""
# # # # #     global _sync_thread
# # # # #     if _sync_thread and _sync_thread.is_alive():
# # # # #         return _sync_thread
# # # # #     t = threading.Thread(target=_sync_loop, daemon=True, name="PaymentSyncDaemon")
# # # # #     t.start()
# # # # #     _sync_thread = t
# # # # #     log.info("Payment entry sync daemon started.")
# # # # #     return t


# # # # # # =============================================================================
# # # # # # DEBUG
# # # # # # =============================================================================

# # # # # if __name__ == "__main__":
# # # # #     logging.basicConfig(level=logging.INFO,
# # # # #                         format="%(asctime)s [%(levelname)s] %(message)s")
# # # # #     print("Running one payment entry sync cycle...")
# # # # #     r = push_unsynced_payment_entries()
# # # # #     print(f"\nResult: {r['pushed']} pushed, {r['failed']} failed, "
# # # # #           f"{r['skipped']} skipped (of {r['total']} total)")
# # # # # =============================================================================
# # # # # services/payment_entry_service.py
# # # # #
# # # # # Manages local payment_entries table and syncs them to Frappe.
# # # # #
# # # # # FLOW:
# # # # #   1. When a sale is saved locally → create_payment_entry() stores it locally
# # # # #      with synced=0
# # # # #   2. When the Sales Invoice is confirmed on Frappe (frappe_ref is set) →
# # # # #      push_unsynced_payment_entries() pushes the Payment Entry to Frappe
# # # # #   3. Frappe returns a PAY-xxxxx ref → stored as frappe_payment_ref, synced=1
# # # # #
# # # # # PAYLOAD SENT TO FRAPPE:
# # # # #   POST /api/resource/Payment Entry
# # # # #   {
# # # # #     "doctype":              "Payment Entry",
# # # # #     "payment_type":         "Receive",
# # # # #     "party_type":           "Customer",
# # # # #     "party":                "Cathy",
# # # # #     "paid_to":              "Cash ZWG - H",
# # # # #     "paid_to_account_currency": "USD",
# # # # #     "paid_amount":          32.45,
# # # # #     "received_amount":      32.45,
# # # # #     "source_exchange_rate": 1.0,
# # # # #     "reference_no":         "ACC-SINV-2026-00034",
# # # # #     "reference_date":       "2026-03-19",
# # # # #     "remarks":              "POS Payment — Cash",
# # # # #     "docstatus":            1,
# # # # #     "references": [{
# # # # #         "reference_doctype": "Sales Invoice",
# # # # #         "reference_name":    "ACC-SINV-2026-00565",
# # # # #         "allocated_amount":  32.45
# # # # #     }]
# # # # #   }
# # # # # =============================================================================

# # # # from __future__ import annotations

# # # # import json
# # # # import logging
# # # # import time
# # # # import threading
# # # # import urllib.request
# # # # import urllib.error
# # # # from datetime import date

# # # # log = logging.getLogger("PaymentEntry")

# # # # SYNC_INTERVAL   = 60      # seconds between auto-sync cycles
# # # # REQUEST_TIMEOUT = 30

# # # # # Exchange rate cache: "FROM::TO::DATE" → float
# # # # _RATE_CACHE: dict[str, float] = {}


# # # # def _get_exchange_rate(from_currency: str, to_currency: str,
# # # #                        transaction_date: str,
# # # #                        api_key: str, api_secret: str, host: str) -> float:
# # # #     """
# # # #     Fetch live exchange rate from Frappe.
# # # #     Returns 1.0 for same currency, 0.0 if fetch fails (Frappe uses its own rate).
# # # #     """
# # # #     if not from_currency or from_currency.upper() == to_currency.upper():
# # # #         return 1.0

# # # #     cache_key = f"{from_currency.upper()}::{to_currency.upper()}::{transaction_date}"
# # # #     if cache_key in _RATE_CACHE:
# # # #         return _RATE_CACHE[cache_key]

# # # #     try:
# # # #         import urllib.parse
# # # #         url = (
# # # #             f"{host}/api/method/erpnext.setup.utils.get_exchange_rate"
# # # #             f"?from_currency={urllib.parse.quote(from_currency)}"
# # # #             f"&to_currency={urllib.parse.quote(to_currency)}"
# # # #             f"&transaction_date={transaction_date}"
# # # #         )
# # # #         req = urllib.request.Request(url)
# # # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # # #             data = json.loads(r.read().decode())
# # # #             rate = float(data.get("message") or data.get("result") or 0)
# # # #             if rate > 0:
# # # #                 _RATE_CACHE[cache_key] = rate
# # # #                 log.debug("Rate %s→%s on %s: %.6f", from_currency, to_currency, transaction_date, rate)
# # # #                 return rate
# # # #     except Exception as e:
# # # #         log.debug("Rate fetch failed (%s→%s): %s", from_currency, to_currency, e)

# # # #     return 0.0

# # # # _sync_lock:   threading.Lock          = threading.Lock()
# # # # _sync_thread: threading.Thread | None = None

# # # # # Method → Frappe Mode of Payment name
# # # # _METHOD_MAP = {
# # # #     "CASH":     "Cash",
# # # #     "CARD":     "Credit Card",
# # # #     "C / CARD": "Credit Card",
# # # #     "EFTPOS":   "Credit Card",
# # # #     "CHECK":    "Cheque",
# # # #     "CHEQUE":   "Cheque",
# # # #     "MOBILE":   "Mobile Money",
# # # #     "CREDIT":   "Credit",
# # # #     "TRANSFER": "Bank Transfer",
# # # # }


# # # # # =============================================================================
# # # # # CREDENTIALS / HOST / DEFAULTS
# # # # # =============================================================================

# # # # def _get_credentials() -> tuple[str, str]:
# # # #     try:
# # # #         from services.auth_service import get_session
# # # #         s = get_session()
# # # #         if s.get("api_key") and s.get("api_secret"):
# # # #             return s["api_key"], s["api_secret"]
# # # #     except Exception:
# # # #         pass
# # # #     try:
# # # #         from database.db import get_connection
# # # #         conn = get_connection(); cur = conn.cursor()
# # # #         cur.execute("SELECT api_key, api_secret FROM company_defaults WHERE id = 1")
# # # #         row = cur.fetchone(); conn.close()
# # # #         if row and row[0] and row[1]:
# # # #             return row[0], row[1]
# # # #     except Exception:
# # # #         pass
# # # #     import os
# # # #     return os.environ.get("HAVANO_API_KEY", ""), os.environ.get("HAVANO_API_SECRET", "")


# # # # def _get_host() -> str:
# # # #     try:
# # # #         from models.company_defaults import get_defaults
# # # #         host = (get_defaults() or {}).get("server_api_host", "").strip().rstrip("/")
# # # #         if host:
# # # #             return host
# # # #     except Exception:
# # # #         pass
# # # #     return "https://apk.havano.cloud"


# # # # def _get_defaults() -> dict:
# # # #     try:
# # # #         from models.company_defaults import get_defaults
# # # #         return get_defaults() or {}
# # # #     except Exception:
# # # #         return {}


# # # # # =============================================================================
# # # # # GL ACCOUNT RESOLVER  (which account to credit for each payment method)
# # # # # =============================================================================

# # # # _ACCOUNT_CACHE: dict[str, str] = {}


# # # # def _resolve_paid_to_account(mop_name: str, company: str, currency: str,
# # # #                               api_key: str, api_secret: str, host: str) -> str:
# # # #     """
# # # #     Looks up the GL account for a Mode of Payment from Frappe.
# # # #     Tries to match by currency if multiple accounts exist for the company.
# # # #     Falls back to server_pos_account in company_defaults.
# # # #     """
# # # #     cache_key = f"{mop_name}::{company}::{currency}"
# # # #     if cache_key in _ACCOUNT_CACHE:
# # # #         return _ACCOUNT_CACHE[cache_key]

# # # #     try:
# # # #         import urllib.parse
# # # #         url = (f"{host}/api/resource/Mode%20of%20Payment/"
# # # #                f"{urllib.parse.quote(mop_name)}?fields=[\"accounts\"]")
# # # #         req = urllib.request.Request(url)
# # # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # # #             data     = json.loads(r.read().decode())
# # # #             accounts = (data.get("data") or {}).get("accounts", [])

# # # #         company_accts = [a for a in accounts
# # # #                          if not company or a.get("company") == company]

# # # #         # Prefer account whose name contains the currency code
# # # #         matched = ""
# # # #         if currency:
# # # #             for a in company_accts:
# # # #                 if currency.upper() in (a.get("default_account") or "").upper():
# # # #                     matched = a["default_account"]; break

# # # #         if not matched and company_accts:
# # # #             matched = company_accts[0].get("default_account", "")

# # # #         if matched:
# # # #             _ACCOUNT_CACHE[cache_key] = matched
# # # #             return matched

# # # #     except Exception as e:
# # # #         log.debug("MOP account lookup failed for '%s': %s", mop_name, e)

# # # #     # Fallback
# # # #     fallback = _get_defaults().get("server_pos_account", "").strip()
# # # #     if fallback:
# # # #         _ACCOUNT_CACHE[cache_key] = fallback
# # # #         return fallback

# # # #     log.warning("No GL account for MOP '%s' currency=%s — Payment Entry may fail.",
# # # #                 mop_name, currency)
# # # #     return ""


# # # # # =============================================================================
# # # # # LOCAL DB  — create / read / update payment_entries
# # # # # =============================================================================

# # # # def create_payment_entry(sale: dict, override_rate: float = None,
# # # #                          override_account: str = None) -> int | None:
# # # #     """
# # # #     Called immediately after a sale is saved locally.
# # # #     Stores a payment_entry row with synced=0.
# # # #     Returns the new payment_entry id, or None on error.

# # # #     Will only create the entry once per sale (idempotent).
# # # #     """
# # # #     from database.db import get_connection
# # # #     conn = get_connection(); cur = conn.cursor()

# # # #     # Idempotency: don't create twice for the same sale
# # # #     cur.execute("SELECT id FROM payment_entries WHERE sale_id = ?", (sale["id"],))
# # # #     if cur.fetchone():
# # # #         conn.close()
# # # #         return None

# # # #     customer   = (sale.get("customer_name") or "default").strip()
# # # #     currency   = (sale.get("currency")      or "USD").strip().upper()
# # # #     amount     = float(sale.get("total")    or 0)
# # # #     inv_no     = sale.get("invoice_no", "")
# # # #     inv_date   = sale.get("invoice_date") or date.today().isoformat()
# # # #     method     = str(sale.get("method", "CASH")).upper().strip()
# # # #     mop        = _METHOD_MAP.get(method, "Cash")

# # # #     # Use override rate (from split) or fetch from Frappe
# # # #     if override_rate is not None:
# # # #         exch_rate = override_rate
# # # #     else:
# # # #         try:
# # # #             api_key, api_secret = _get_credentials()
# # # #             host = _get_host()
# # # #             defaults = _get_defaults()
# # # #             company_currency = defaults.get("server_company_currency", "USD").strip().upper() or "USD"
# # # #             exch_rate = _get_exchange_rate(
# # # #                 currency, company_currency, inv_date, api_key, api_secret, host
# # # #             ) if currency != company_currency else 1.0
# # # #         except Exception:
# # # #             exch_rate = 1.0

# # # #     cur.execute("""
# # # #         INSERT INTO payment_entries (
# # # #             sale_id, sale_invoice_no, frappe_invoice_ref,
# # # #             party, party_name,
# # # #             paid_amount, received_amount, source_exchange_rate,
# # # #             paid_to_account_currency, currency,
# # # #             mode_of_payment,
# # # #             reference_no, reference_date,
# # # #             remarks, synced
# # # #         ) OUTPUT INSERTED.id
# # # #         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # # #     """, (
# # # #         sale["id"], inv_no,
# # # #         sale.get("frappe_ref") or None,
# # # #         customer, customer,
# # # #         amount, amount, exch_rate or 1.0,
# # # #         currency, currency,
# # # #         mop,
# # # #         inv_no, inv_date,
# # # #         f"POS Payment — {mop}",
# # # #     ))
# # # #     new_id = int(cur.fetchone()[0])
# # # #     conn.commit(); conn.close()
# # # #     log.debug("Payment entry %d created locally for sale %s", new_id, inv_no)
# # # #     return new_id


# # # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # # #     """
# # # #     Called when cashier uses Split payment.
# # # #     Creates one payment_entry row per currency in splits list.
# # # #     splits = [{"mode": "CASH", "currency": "USD", "amount": 5.0,
# # # #                "rate": 1.0, "base_amount": 5.0, "account": "Cash - AT"}, ...]
# # # #     Returns list of new payment_entry ids.
# # # #     """
# # # #     ids = []
# # # #     for split in splits:
# # # #         if not split.get("amount") or float(split["amount"]) <= 0:
# # # #             continue
# # # #         # Build a sale-like dict with the split's currency and amount
# # # #         split_sale = dict(sale)
# # # #         split_sale["currency"]      = split.get("currency", "USD")
# # # #         split_sale["total"]         = float(split.get("amount", 0))
# # # #         split_sale["method"]        = split.get("mode", "CASH")
# # # #         # Override exchange rate from split data
# # # #         new_id = create_payment_entry(
# # # #             split_sale,
# # # #             override_rate=float(split.get("rate", 1.0)),
# # # #             override_account=split.get("account", ""),
# # # #         )
# # # #         if new_id:
# # # #             ids.append(new_id)
# # # #     return ids


# # # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # # #     """
# # # #     Creates one payment_entry per currency from a split payment.
# # # #     Groups splits by currency, sums amounts, creates one entry each.
# # # #     Returns list of created payment_entry ids.
# # # #     """
# # # #     from datetime import date as _date

# # # #     # Group by currency
# # # #     by_currency: dict[str, dict] = {}
# # # #     for s in splits:
# # # #         curr = s.get("account_currency", "USD").upper()
# # # #         if curr not in by_currency:
# # # #             by_currency[curr] = {
# # # #                 "currency":      curr,
# # # #                 "paid_amount":   0.0,
# # # #                 "base_value":    0.0,
# # # #                 "rate":          s.get("rate", 1.0),
# # # #                 "account_name":  s.get("account_name", ""),
# # # #                 "mode":          s.get("mode", "Cash"),
# # # #             }
# # # #         by_currency[curr]["paid_amount"] += s.get("amount_paid", 0.0)
# # # #         by_currency[curr]["base_value"]  += s.get("base_value",  0.0)

# # # #     ids = []
# # # #     inv_no   = sale.get("invoice_no", "")
# # # #     inv_date = sale.get("invoice_date") or _date.today().isoformat()
# # # #     customer = (sale.get("customer_name") or "default").strip()

# # # #     from database.db import get_connection
# # # #     conn = get_connection(); cur = conn.cursor()

# # # #     for curr, grp in by_currency.items():
# # # #         # Idempotency: skip if already exists for this sale+currency
# # # #         cur.execute(
# # # #             "SELECT id FROM payment_entries WHERE sale_id=? AND currency=?",
# # # #             (sale["id"], curr)
# # # #         )
# # # #         if cur.fetchone():
# # # #             continue

# # # #         mop = _METHOD_MAP.get(grp["mode"].upper(), "Cash")

# # # #         cur.execute("""
# # # #             INSERT INTO payment_entries (
# # # #                 sale_id, sale_invoice_no, frappe_invoice_ref,
# # # #                 party, party_name,
# # # #                 paid_amount, received_amount, source_exchange_rate,
# # # #                 paid_to_account_currency, currency,
# # # #                 paid_to,
# # # #                 mode_of_payment,
# # # #                 reference_no, reference_date,
# # # #                 remarks, synced
# # # #             ) OUTPUT INSERTED.id
# # # #             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # # #         """, (
# # # #             sale["id"], inv_no,
# # # #             sale.get("frappe_ref") or None,
# # # #             customer, customer,
# # # #             grp["paid_amount"],
# # # #             grp["base_value"],
# # # #             float(grp["rate"] or 1.0),
# # # #             curr, curr,
# # # #             grp["account_name"],
# # # #             mop,
# # # #             inv_no, inv_date,
# # # #             f"POS Split Payment — {mop} ({curr})",
# # # #         ))
# # # #         new_id = int(cur.fetchone()[0])
# # # #         ids.append(new_id)
# # # #         log.debug("Split payment entry %d created: %s %.2f %s",
# # # #                   new_id, curr, grp["paid_amount"], inv_no)

# # # #     conn.commit(); conn.close()
# # # #     return ids


# # # # def get_unsynced_payment_entries() -> list[dict]:
# # # #     """Returns payment entries that are ready to push (synced=0)."""
# # # #     from database.db import get_connection, fetchall_dicts
# # # #     conn = get_connection(); cur = conn.cursor()
# # # #     cur.execute("""
# # # #         SELECT pe.*, s.frappe_ref AS sale_frappe_ref
# # # #         FROM payment_entries pe
# # # #         LEFT JOIN sales s ON s.id = pe.sale_id
# # # #         WHERE pe.synced = 0
# # # #           AND (pe.frappe_invoice_ref IS NOT NULL
# # # #                OR s.frappe_ref IS NOT NULL)
# # # #         ORDER BY pe.id
# # # #     """)
# # # #     rows = fetchall_dicts(cur); conn.close()
# # # #     return rows


# # # # def mark_payment_synced(pe_id: int, frappe_payment_ref: str = "") -> None:
# # # #     from database.db import get_connection
# # # #     conn = get_connection(); cur = conn.cursor()
# # # #     cur.execute(
# # # #         "UPDATE payment_entries SET synced=1, frappe_payment_ref=? WHERE id=?",
# # # #         (frappe_payment_ref or None, pe_id)
# # # #     )
# # # #     # Also update the sales row
# # # #     cur.execute("""
# # # #         UPDATE sales SET payment_entry_ref=?, payment_synced=1
# # # #         WHERE id = (SELECT sale_id FROM payment_entries WHERE id=?)
# # # #     """, (frappe_payment_ref or None, pe_id))
# # # #     conn.commit(); conn.close()


# # # # def refresh_frappe_refs() -> int:
# # # #     """
# # # #     For payment entries that have no frappe_invoice_ref yet, copy it from
# # # #     the parent sale's frappe_ref. Call this before pushing payments.
# # # #     Returns count updated.
# # # #     """
# # # #     from database.db import get_connection
# # # #     conn = get_connection(); cur = conn.cursor()
# # # #     cur.execute("""
# # # #         UPDATE pe
# # # #         SET pe.frappe_invoice_ref = s.frappe_ref
# # # #         FROM payment_entries pe
# # # #         JOIN sales s ON s.id = pe.sale_id
# # # #         WHERE pe.synced = 0
# # # #           AND (pe.frappe_invoice_ref IS NULL OR pe.frappe_invoice_ref = '')
# # # #           AND s.frappe_ref IS NOT NULL AND s.frappe_ref != ''
# # # #     """)
# # # #     count = cur.rowcount
# # # #     conn.commit(); conn.close()
# # # #     return count


# # # # # =============================================================================
# # # # # BUILD FRAPPE PAYLOAD
# # # # # =============================================================================

# # # # def _build_payload(pe: dict, defaults: dict,
# # # #                    api_key: str, api_secret: str, host: str) -> dict:
# # # #     company  = defaults.get("server_company", "")
# # # #     currency = (pe.get("currency") or pe.get("paid_to_account_currency") or "USD").upper()
# # # #     mop      = pe.get("mode_of_payment") or "Cash"
# # # #     amount   = float(pe.get("paid_amount") or 0)
# # # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()

# # # #     # Use local gl_accounts table first (synced from Frappe)
# # # #     paid_to          = (pe.get("paid_to") or "").strip()
# # # #     paid_to_currency = currency
# # # #     if not paid_to:
# # # #         try:
# # # #             from models.gl_account import get_account_for_payment
# # # #             acct = get_account_for_payment(currency, company)
# # # #             if acct:
# # # #                 paid_to          = acct["name"]
# # # #                 paid_to_currency = acct["account_currency"]
# # # #         except Exception as _e:
# # # #             log.debug("gl_account lookup failed: %s", _e)

# # # #     # Fallback to live Frappe lookup
# # # #     if not paid_to:
# # # #         paid_to = _resolve_paid_to_account(mop, company, currency, api_key, api_secret, host)

# # # #     # Use local exchange rate if not stored
# # # #     exch_rate = float(pe.get("source_exchange_rate") or 1.0)
# # # #     if exch_rate == 1.0 and currency not in ("USD", ""):
# # # #         try:
# # # #             from models.exchange_rate import get_rate
# # # #             stored = get_rate(currency, "USD")
# # # #             if stored:
# # # #                 exch_rate = stored
# # # #         except Exception:
# # # #             pass

# # # #     payload = {
# # # #         "doctype":                  "Payment Entry",
# # # #         "payment_type":             "Receive",
# # # #         "party_type":               "Customer",
# # # #         "party":                    pe.get("party") or "default",
# # # #         "party_name":               pe.get("party_name") or "default",
# # # #         "paid_to_account_currency": paid_to_currency,
# # # #         "paid_amount":              amount,
# # # #         "received_amount":          amount,
# # # #         "source_exchange_rate":     exch_rate,
# # # #         "reference_no":             pe.get("reference_no") or pe.get("sale_invoice_no", ""),
# # # #         "reference_date":           pe.get("reference_date") or date.today().isoformat(),
# # # #         "remarks":                  pe.get("remarks") or f"POS Payment — {mop}",
# # # #         "mode_of_payment":          mop,
# # # #         "docstatus":                1,
# # # #     }

# # # #     if paid_to:
# # # #         payload["paid_to"] = paid_to
# # # #     if company:
# # # #         payload["company"] = company

# # # #     # Link to the Sales Invoice on Frappe
# # # #     if frappe_inv:
# # # #         payload["references"] = [{
# # # #             "reference_doctype": "Sales Invoice",
# # # #             "reference_name":    frappe_inv,
# # # #             "allocated_amount":  amount,
# # # #         }]

# # # #     return payload


# # # # # =============================================================================
# # # # # PUSH ONE PAYMENT ENTRY
# # # # # =============================================================================

# # # # def _push_payment_entry(pe: dict, api_key: str, api_secret: str,
# # # #                         defaults: dict, host: str) -> str | None:
# # # #     """
# # # #     Posts one payment entry to Frappe.
# # # #     Returns Frappe's PAY-xxxxx name on success, None on failure.
# # # #     """
# # # #     pe_id  = pe["id"]
# # # #     inv_no = pe.get("sale_invoice_no", str(pe_id))

# # # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()
# # # #     if not frappe_inv:
# # # #         log.warning("Payment %d — Sales Invoice not yet on Frappe, skipping.", pe_id)
# # # #         return None

# # # #     payload = _build_payload(pe, defaults, api_key, api_secret, host)

# # # #     url = f"{host}/api/resource/Payment%20Entry"
# # # #     req = urllib.request.Request(
# # # #         url=url,
# # # #         data=json.dumps(payload).encode("utf-8"),
# # # #         method="POST",
# # # #         headers={
# # # #             "Content-Type":  "application/json",
# # # #             "Accept":        "application/json",
# # # #             "Authorization": f"token {api_key}:{api_secret}",
# # # #         },
# # # #     )

# # # #     try:
# # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
# # # #             data = json.loads(resp.read().decode())
# # # #             name = (data.get("data") or {}).get("name", "")
# # # #             log.info("✅ Payment Entry %d → Frappe %s  [%s  %s %.2f]",
# # # #                      pe_id, name, inv_no,
# # # #                      pe.get("currency", ""), float(pe.get("paid_amount", 0)))
# # # #             return name or "SYNCED"

# # # #     except urllib.error.HTTPError as e:
# # # #         try:
# # # #             err = json.loads(e.read().decode())
# # # #             msg = (err.get("exception") or err.get("message") or
# # # #                    str(err.get("_server_messages", "")) or f"HTTP {e.code}")
# # # #         except Exception:
# # # #             msg = f"HTTP {e.code}"

# # # #         if e.code == 409:
# # # #             log.info("Payment %d already on Frappe (409) - marking synced.", pe_id)
# # # #             return "DUPLICATE"

# # # #         # Invoice already paid (is_pos:1 on old invoices) - stop retrying
# # # #         if e.code == 417:
# # # #             _perma = ("already been fully paid", "already paid", "fully paid")
# # # #             if any(p in msg.lower() for p in _perma):
# # # #                 log.info("Payment %d - invoice already paid on Frappe, marking synced.", pe_id)
# # # #                 return "ALREADY_PAID"

# # # #         log.error("FAIL Payment Entry %d  HTTP %s: %s", pe_id, e.code, msg)
# # # #         return None

# # # #     except urllib.error.URLError as e:
# # # #         log.warning("Network error pushing payment %d: %s", pe_id, e.reason)
# # # #         return None

# # # #     except Exception as e:
# # # #         log.error("Unexpected error pushing payment %d: %s", pe_id, e)
# # # #         return None


# # # # # =============================================================================
# # # # # PUBLIC — push all unsynced payment entries
# # # # # =============================================================================

# # # # def push_unsynced_payment_entries() -> dict:
# # # #     """
# # # #     1. Refresh frappe_invoice_ref from parent sales that were confirmed.
# # # #     2. Push each unsynced payment entry to Frappe.
# # # #     3. Mark synced with the returned PAY-xxxxx ref.
# # # #     """
# # # #     result = {"pushed": 0, "failed": 0, "skipped": 0, "total": 0}

# # # #     api_key, api_secret = _get_credentials()
# # # #     if not api_key or not api_secret:
# # # #         log.warning("No credentials — skipping payment entry sync.")
# # # #         return result

# # # #     host     = _get_host()
# # # #     defaults = _get_defaults()

# # # #     # First: pull frappe_refs from confirmed invoices into pending payment entries
# # # #     updated = refresh_frappe_refs()
# # # #     if updated:
# # # #         log.info("Refreshed frappe_invoice_ref on %d payment entry(ies).", updated)

# # # #     entries = get_unsynced_payment_entries()
# # # #     result["total"] = len(entries)

# # # #     if not entries:
# # # #         log.debug("No unsynced payment entries.")
# # # #         return result

# # # #     log.info("Pushing %d payment entry(ies) to Frappe…", len(entries))

# # # #     for pe in entries:
# # # #         frappe_name = _push_payment_entry(pe, api_key, api_secret, defaults, host)
# # # #         if frappe_name:
# # # #             mark_payment_synced(pe["id"], frappe_name)
# # # #             result["pushed"] += 1
# # # #         elif frappe_name is None:
# # # #             # None = permanent skip (no frappe_inv yet), not a real failure
# # # #             result["skipped"] += 1
# # # #         else:
# # # #             result["failed"] += 1

# # # #         time.sleep(3)   # rate limit — 20/min max

# # # #     log.info("Payment sync done — ✅ %d pushed  ❌ %d failed  ⏭ %d skipped",
# # # #              result["pushed"], result["failed"], result["skipped"])
# # # #     return result


# # # # # =============================================================================
# # # # # BACKGROUND DAEMON THREAD
# # # # # =============================================================================

# # # # def _sync_loop():
# # # #     log.info("Payment entry sync daemon started (interval=%ds).", SYNC_INTERVAL)
# # # #     while True:
# # # #         if _sync_lock.acquire(blocking=False):
# # # #             try:
# # # #                 push_unsynced_payment_entries()
# # # #             except Exception as e:
# # # #                 log.error("Payment sync cycle error: %s", e)
# # # #             finally:
# # # #                 _sync_lock.release()
# # # #         else:
# # # #             log.debug("Previous payment sync still running — skipping.")
# # # #         time.sleep(SYNC_INTERVAL)


# # # # def start_payment_sync_daemon() -> threading.Thread:
# # # #     """Non-blocking — safe to call from MainWindow.__init__."""
# # # #     global _sync_thread
# # # #     if _sync_thread and _sync_thread.is_alive():
# # # #         return _sync_thread
# # # #     t = threading.Thread(target=_sync_loop, daemon=True, name="PaymentSyncDaemon")
# # # #     t.start()
# # # #     _sync_thread = t
# # # #     log.info("Payment entry sync daemon started.")
# # # #     return t


# # # # # =============================================================================
# # # # # DEBUG
# # # # # =============================================================================

# # # # if __name__ == "__main__":
# # # #     logging.basicConfig(level=logging.INFO,
# # # #                         format="%(asctime)s [%(levelname)s] %(message)s")
# # # #     print("Running one payment entry sync cycle...")
# # # #     r = push_unsynced_payment_entries()
# # # #     print(f"\nResult: {r['pushed']} pushed, {r['failed']} failed, "
# # # #           f"{r['skipped']} skipped (of {r['total']} total)")

# # # # =============================================================================
# # # # services/payment_entry_service.py
# # # #
# # # # Manages local payment_entries table and syncs them to Frappe.
# # # #
# # # # FLOW:
# # # #   1. When a sale is saved locally → create_payment_entry() stores it locally
# # # #      with synced=0
# # # #   2. When the Sales Invoice is confirmed on Frappe (frappe_ref is set) →
# # # #      push_unsynced_payment_entries() pushes the Payment Entry to Frappe
# # # #   3. Frappe returns a PAY-xxxxx ref → stored as frappe_payment_ref, synced=1
# # # #
# # # # PAYLOAD SENT TO FRAPPE:
# # # #   POST /api/resource/Payment Entry
# # # #   {
# # # #     "doctype":              "Payment Entry",
# # # #     "payment_type":         "Receive",
# # # #     "party_type":           "Customer",
# # # #     "party":                "Cathy",
# # # #     "paid_to":              "Cash ZWG - H",
# # # #     "paid_to_account_currency": "USD",
# # # #     "paid_amount":          32.45,
# # # #     "received_amount":      32.45,
# # # #     "source_exchange_rate": 1.0,
# # # #     "reference_no":         "ACC-SINV-2026-00034",
# # # #     "reference_date":       "2026-03-19",
# # # #     "remarks":              "POS Payment — Cash",
# # # #     "docstatus":            1,
# # # #     "references": [{
# # # #         "reference_doctype": "Sales Invoice",
# # # #         "reference_name":    "ACC-SINV-2026-00565",
# # # #         "allocated_amount":  32.45
# # # #     }]
# # # #   }
# # # # =============================================================================

# # # from __future__ import annotations

# # # import json
# # # import logging
# # # import time
# # # import threading
# # # import urllib.request
# # # import urllib.error
# # # from datetime import date

# # # log = logging.getLogger("PaymentEntry")

# # # SYNC_INTERVAL   = 60      # seconds between auto-sync cycles
# # # REQUEST_TIMEOUT = 30

# # # # Exchange rate cache: "FROM::TO::DATE" → float
# # # _RATE_CACHE: dict[str, float] = {}


# # # def _get_exchange_rate(from_currency: str, to_currency: str,
# # #                        transaction_date: str,
# # #                        api_key: str, api_secret: str, host: str) -> float:
# # #     """
# # #     Fetch live exchange rate from Frappe.
# # #     Returns 1.0 for same currency, 0.0 if fetch fails (Frappe uses its own rate).
# # #     """
# # #     if not from_currency or from_currency.upper() == to_currency.upper():
# # #         return 1.0

# # #     cache_key = f"{from_currency.upper()}::{to_currency.upper()}::{transaction_date}"
# # #     if cache_key in _RATE_CACHE:
# # #         return _RATE_CACHE[cache_key]

# # #     try:
# # #         import urllib.parse
# # #         url = (
# # #             f"{host}/api/method/erpnext.setup.utils.get_exchange_rate"
# # #             f"?from_currency={urllib.parse.quote(from_currency)}"
# # #             f"&to_currency={urllib.parse.quote(to_currency)}"
# # #             f"&transaction_date={transaction_date}"
# # #         )
# # #         req = urllib.request.Request(url)
# # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # #             data = json.loads(r.read().decode())
# # #             rate = float(data.get("message") or data.get("result") or 0)
# # #             if rate > 0:
# # #                 _RATE_CACHE[cache_key] = rate
# # #                 log.debug("Rate %s→%s on %s: %.6f", from_currency, to_currency, transaction_date, rate)
# # #                 return rate
# # #     except Exception as e:
# # #         log.debug("Rate fetch failed (%s→%s): %s", from_currency, to_currency, e)

# # #     return 0.0

# # # _sync_lock:   threading.Lock          = threading.Lock()
# # # _sync_thread: threading.Thread | None = None

# # # # Method → Frappe Mode of Payment name
# # # _METHOD_MAP = {
# # #     "CASH":     "Cash",
# # #     "CARD":     "Credit Card",
# # #     "C / CARD": "Credit Card",
# # #     "EFTPOS":   "Credit Card",
# # #     "CHECK":    "Cheque",
# # #     "CHEQUE":   "Cheque",
# # #     "MOBILE":   "Mobile Money",
# # #     "CREDIT":   "Credit",
# # #     "TRANSFER": "Bank Transfer",
# # # }


# # # # =============================================================================
# # # # CREDENTIALS / HOST / DEFAULTS
# # # # =============================================================================

# # # def _get_credentials() -> tuple[str, str]:
# # #     try:
# # #         from services.credentials import get_credentials
# # #         return get_credentials()
# # #     except Exception:
# # #         pass
# # #     return "", ""


# # # def _get_host() -> str:
# # #     try:
# # #         from models.company_defaults import get_defaults
# # #         host = (get_defaults() or {}).get("server_api_host", "").strip().rstrip("/")
# # #         if host:
# # #             return host
# # #     except Exception:
# # #         pass
# # #     return "https://apk.havano.cloud"


# # # def _get_defaults() -> dict:
# # #     try:
# # #         from models.company_defaults import get_defaults
# # #         return get_defaults() or {}
# # #     except Exception:
# # #         return {}


# # # # =============================================================================
# # # # GL ACCOUNT RESOLVER  (which account to credit for each payment method)
# # # # =============================================================================

# # # _ACCOUNT_CACHE: dict[str, str] = {}


# # # def _resolve_paid_to_account(mop_name: str, company: str, currency: str,
# # #                               api_key: str, api_secret: str, host: str) -> str:
# # #     """
# # #     Looks up the GL account for a Mode of Payment from Frappe.
# # #     Tries to match by currency if multiple accounts exist for the company.
# # #     Falls back to server_pos_account in company_defaults.
# # #     """
# # #     cache_key = f"{mop_name}::{company}::{currency}"
# # #     if cache_key in _ACCOUNT_CACHE:
# # #         return _ACCOUNT_CACHE[cache_key]

# # #     try:
# # #         import urllib.parse
# # #         url = (f"{host}/api/resource/Mode%20of%20Payment/"
# # #                f"{urllib.parse.quote(mop_name)}?fields=[\"accounts\"]")
# # #         req = urllib.request.Request(url)
# # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # #             data     = json.loads(r.read().decode())
# # #             accounts = (data.get("data") or {}).get("accounts", [])

# # #         company_accts = [a for a in accounts
# # #                          if not company or a.get("company") == company]

# # #         # Prefer account whose name contains the currency code
# # #         matched = ""
# # #         if currency:
# # #             for a in company_accts:
# # #                 if currency.upper() in (a.get("default_account") or "").upper():
# # #                     matched = a["default_account"]; break

# # #         if not matched and company_accts:
# # #             matched = company_accts[0].get("default_account", "")

# # #         if matched:
# # #             _ACCOUNT_CACHE[cache_key] = matched
# # #             return matched

# # #     except Exception as e:
# # #         log.debug("MOP account lookup failed for '%s': %s", mop_name, e)

# # #     # Fallback
# # #     fallback = _get_defaults().get("server_pos_account", "").strip()
# # #     if fallback:
# # #         _ACCOUNT_CACHE[cache_key] = fallback
# # #         return fallback

# # #     log.warning("No GL account for MOP '%s' currency=%s — Payment Entry may fail.",
# # #                 mop_name, currency)
# # #     return ""


# # # # =============================================================================
# # # # LOCAL DB  — create / read / update payment_entries
# # # # =============================================================================

# # # def create_payment_entry(sale: dict, override_rate: float = None,
# # #                          override_account: str = None) -> int | None:
# # #     """
# # #     Called immediately after a sale is saved locally.
# # #     Stores a payment_entry row with synced=0.
# # #     Returns the new payment_entry id, or None on error.

# # #     Will only create the entry once per sale (idempotent).
# # #     """
# # #     from database.db import get_connection
# # #     conn = get_connection(); cur = conn.cursor()

# # #     # Idempotency: don't create twice for the same sale
# # #     cur.execute("SELECT id FROM payment_entries WHERE sale_id = ?", (sale["id"],))
# # #     if cur.fetchone():
# # #         conn.close()
# # #         return None

# # #     customer   = (sale.get("customer_name") or "default").strip()
# # #     currency   = (sale.get("currency")      or "USD").strip().upper()
# # #     amount     = float(sale.get("total")    or 0)
# # #     inv_no     = sale.get("invoice_no", "")
# # #     inv_date   = sale.get("invoice_date") or date.today().isoformat()
# # #     method     = str(sale.get("method", "CASH")).upper().strip()
# # #     mop        = _METHOD_MAP.get(method, "Cash")

# # #     # Use override rate (from split) or fetch from Frappe
# # #     if override_rate is not None:
# # #         exch_rate = override_rate
# # #     else:
# # #         try:
# # #             api_key, api_secret = _get_credentials()
# # #             host = _get_host()
# # #             defaults = _get_defaults()
# # #             company_currency = defaults.get("server_company_currency", "USD").strip().upper() or "USD"
# # #             exch_rate = _get_exchange_rate(
# # #                 currency, company_currency, inv_date, api_key, api_secret, host
# # #             ) if currency != company_currency else 1.0
# # #         except Exception:
# # #             exch_rate = 1.0

# # #     cur.execute("""
# # #         INSERT INTO payment_entries (
# # #             sale_id, sale_invoice_no, frappe_invoice_ref,
# # #             party, party_name,
# # #             paid_amount, received_amount, source_exchange_rate,
# # #             paid_to_account_currency, currency,
# # #             mode_of_payment,
# # #             reference_no, reference_date,
# # #             remarks, synced
# # #         ) OUTPUT INSERTED.id
# # #         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # #     """, (
# # #         sale["id"], inv_no,
# # #         sale.get("frappe_ref") or None,
# # #         customer, customer,
# # #         amount, amount, exch_rate or 1.0,
# # #         currency, currency,
# # #         mop,
# # #         inv_no, inv_date,
# # #         f"POS Payment — {mop}",
# # #     ))
# # #     new_id = int(cur.fetchone()[0])
# # #     conn.commit(); conn.close()
# # #     log.debug("Payment entry %d created locally for sale %s", new_id, inv_no)
# # #     return new_id


# # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # #     """
# # #     Called when cashier uses Split payment.
# # #     Creates one payment_entry row per currency in splits list.
# # #     splits = [{"mode": "CASH", "currency": "USD", "amount": 5.0,
# # #                "rate": 1.0, "base_amount": 5.0, "account": "Cash - AT"}, ...]
# # #     Returns list of new payment_entry ids.
# # #     """
# # #     ids = []
# # #     for split in splits:
# # #         if not split.get("amount") or float(split["amount"]) <= 0:
# # #             continue
# # #         # Build a sale-like dict with the split's currency and amount
# # #         split_sale = dict(sale)
# # #         split_sale["currency"]      = split.get("currency", "USD")
# # #         split_sale["total"]         = float(split.get("amount", 0))
# # #         split_sale["method"]        = split.get("mode", "CASH")
# # #         # Override exchange rate from split data
# # #         new_id = create_payment_entry(
# # #             split_sale,
# # #             override_rate=float(split.get("rate", 1.0)),
# # #             override_account=split.get("account", ""),
# # #         )
# # #         if new_id:
# # #             ids.append(new_id)
# # #     return ids


# # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # #     """
# # #     Creates one payment_entry per currency from a split payment.
# # #     Groups splits by currency, sums amounts, creates one entry each.
# # #     Returns list of created payment_entry ids.
# # #     """
# # #     from datetime import date as _date

# # #     # Group by currency
# # #     by_currency: dict[str, dict] = {}
# # #     for s in splits:
# # #         curr = s.get("account_currency", "USD").upper()
# # #         if curr not in by_currency:
# # #             by_currency[curr] = {
# # #                 "currency":      curr,
# # #                 "paid_amount":   0.0,
# # #                 "base_value":    0.0,
# # #                 "rate":          s.get("rate", 1.0),
# # #                 "account_name":  s.get("account_name", ""),
# # #                 "mode":          s.get("mode", "Cash"),
# # #             }
# # #         by_currency[curr]["paid_amount"] += s.get("amount_paid", 0.0)
# # #         by_currency[curr]["base_value"]  += s.get("base_value",  0.0)

# # #     ids = []
# # #     inv_no   = sale.get("invoice_no", "")
# # #     inv_date = sale.get("invoice_date") or _date.today().isoformat()
# # #     customer = (sale.get("customer_name") or "default").strip()

# # #     from database.db import get_connection
# # #     conn = get_connection(); cur = conn.cursor()

# # #     for curr, grp in by_currency.items():
# # #         # Idempotency: skip if already exists for this sale+currency
# # #         cur.execute(
# # #             "SELECT id FROM payment_entries WHERE sale_id=? AND currency=?",
# # #             (sale["id"], curr)
# # #         )
# # #         if cur.fetchone():
# # #             continue

# # #         mop = _METHOD_MAP.get(grp["mode"].upper(), "Cash")

# # #         cur.execute("""
# # #             INSERT INTO payment_entries (
# # #                 sale_id, sale_invoice_no, frappe_invoice_ref,
# # #                 party, party_name,
# # #                 paid_amount, received_amount, source_exchange_rate,
# # #                 paid_to_account_currency, currency,
# # #                 paid_to,
# # #                 mode_of_payment,
# # #                 reference_no, reference_date,
# # #                 remarks, synced
# # #             ) OUTPUT INSERTED.id
# # #             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # #         """, (
# # #             sale["id"], inv_no,
# # #             sale.get("frappe_ref") or None,
# # #             customer, customer,
# # #             grp["paid_amount"],
# # #             grp["base_value"],
# # #             float(grp["rate"] or 1.0),
# # #             curr, curr,
# # #             grp["account_name"],
# # #             mop,
# # #             inv_no, inv_date,
# # #             f"POS Split Payment — {mop} ({curr})",
# # #         ))
# # #         new_id = int(cur.fetchone()[0])
# # #         ids.append(new_id)
# # #         log.debug("Split payment entry %d created: %s %.2f %s",
# # #                   new_id, curr, grp["paid_amount"], inv_no)

# # #     conn.commit(); conn.close()
# # #     return ids


# # # def get_unsynced_payment_entries() -> list[dict]:
# # #     """Returns payment entries that are ready to push (synced=0)."""
# # #     from database.db import get_connection, fetchall_dicts
# # #     conn = get_connection(); cur = conn.cursor()
# # #     cur.execute("""
# # #         SELECT pe.*, s.frappe_ref AS sale_frappe_ref
# # #         FROM payment_entries pe
# # #         LEFT JOIN sales s ON s.id = pe.sale_id
# # #         WHERE pe.synced = 0
# # #           AND (pe.frappe_invoice_ref IS NOT NULL
# # #                OR s.frappe_ref IS NOT NULL)
# # #         ORDER BY pe.id
# # #     """)
# # #     rows = fetchall_dicts(cur); conn.close()
# # #     return rows


# # # def mark_payment_synced(pe_id: int, frappe_payment_ref: str = "") -> None:
# # #     from database.db import get_connection
# # #     conn = get_connection(); cur = conn.cursor()
# # #     cur.execute(
# # #         "UPDATE payment_entries SET synced=1, frappe_payment_ref=? WHERE id=?",
# # #         (frappe_payment_ref or None, pe_id)
# # #     )
# # #     # Also update the sales row
# # #     cur.execute("""
# # #         UPDATE sales SET payment_entry_ref=?, payment_synced=1
# # #         WHERE id = (SELECT sale_id FROM payment_entries WHERE id=?)
# # #     """, (frappe_payment_ref or None, pe_id))
# # #     conn.commit(); conn.close()


# # # def refresh_frappe_refs() -> int:
# # #     """
# # #     For payment entries that have no frappe_invoice_ref yet, copy it from
# # #     the parent sale's frappe_ref. Call this before pushing payments.
# # #     Returns count updated.
# # #     """
# # #     from database.db import get_connection
# # #     conn = get_connection(); cur = conn.cursor()
# # #     cur.execute("""
# # #         UPDATE pe
# # #         SET pe.frappe_invoice_ref = s.frappe_ref
# # #         FROM payment_entries pe
# # #         JOIN sales s ON s.id = pe.sale_id
# # #         WHERE pe.synced = 0
# # #           AND (pe.frappe_invoice_ref IS NULL OR pe.frappe_invoice_ref = '')
# # #           AND s.frappe_ref IS NOT NULL AND s.frappe_ref != ''
# # #     """)
# # #     count = cur.rowcount
# # #     conn.commit(); conn.close()
# # #     return count


# # # # =============================================================================
# # # # BUILD FRAPPE PAYLOAD
# # # # =============================================================================

# # # def _build_payload(pe: dict, defaults: dict,
# # #                    api_key: str, api_secret: str, host: str) -> dict:
# # #     company  = defaults.get("server_company", "")
# # #     currency = (pe.get("currency") or pe.get("paid_to_account_currency") or "USD").upper()
# # #     mop      = pe.get("mode_of_payment") or "Cash"
# # #     amount   = float(pe.get("paid_amount") or 0)
# # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()

# # #     # Use local gl_accounts table first (synced from Frappe)
# # #     paid_to          = (pe.get("paid_to") or "").strip()
# # #     paid_to_currency = currency
# # #     if not paid_to:
# # #         try:
# # #             from models.gl_account import get_account_for_payment
# # #             acct = get_account_for_payment(currency, company)
# # #             if acct:
# # #                 paid_to          = acct["name"]
# # #                 paid_to_currency = acct["account_currency"]
# # #         except Exception as _e:
# # #             log.debug("gl_account lookup failed: %s", _e)

# # #     # Fallback to live Frappe lookup
# # #     if not paid_to:
# # #         paid_to = _resolve_paid_to_account(mop, company, currency, api_key, api_secret, host)

# # #     # Use local exchange rate if not stored
# # #     exch_rate = float(pe.get("source_exchange_rate") or 1.0)
# # #     if exch_rate == 1.0 and currency not in ("USD", ""):
# # #         try:
# # #             from models.exchange_rate import get_rate
# # #             stored = get_rate(currency, "USD")
# # #             if stored:
# # #                 exch_rate = stored
# # #         except Exception:
# # #             pass

# # #     payload = {
# # #         "doctype":                  "Payment Entry",
# # #         "payment_type":             "Receive",
# # #         "party_type":               "Customer",
# # #         "party":                    pe.get("party") or "default",
# # #         "party_name":               pe.get("party_name") or "default",
# # #         "paid_to_account_currency": paid_to_currency,
# # #         "paid_amount":              amount,
# # #         "received_amount":          amount,
# # #         "source_exchange_rate":     exch_rate,
# # #         "reference_no":             pe.get("reference_no") or pe.get("sale_invoice_no", ""),
# # #         "reference_date":           pe.get("reference_date") or date.today().isoformat(),
# # #         "remarks":                  pe.get("remarks") or f"POS Payment — {mop}",
# # #         "mode_of_payment":          mop,
# # #         "docstatus":                1,
# # #     }

# # #     if paid_to:
# # #         payload["paid_to"] = paid_to
# # #     if company:
# # #         payload["company"] = company

# # #     # Link to the Sales Invoice on Frappe
# # #     if frappe_inv:
# # #         payload["references"] = [{
# # #             "reference_doctype": "Sales Invoice",
# # #             "reference_name":    frappe_inv,
# # #             "allocated_amount":  amount,
# # #         }]

# # #     return payload


# # # # =============================================================================
# # # # PUSH ONE PAYMENT ENTRY
# # # # =============================================================================

# # # def _push_payment_entry(pe: dict, api_key: str, api_secret: str,
# # #                         defaults: dict, host: str) -> str | None:
# # #     """
# # #     Posts one payment entry to Frappe.
# # #     Returns Frappe's PAY-xxxxx name on success, None on failure.
# # #     """
# # #     pe_id  = pe["id"]
# # #     inv_no = pe.get("sale_invoice_no", str(pe_id))

# # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()
# # #     if not frappe_inv:
# # #         log.warning("Payment %d — Sales Invoice not yet on Frappe, skipping.", pe_id)
# # #         return None

# # #     payload = _build_payload(pe, defaults, api_key, api_secret, host)

# # #     url = f"{host}/api/resource/Payment%20Entry"
# # #     req = urllib.request.Request(
# # #         url=url,
# # #         data=json.dumps(payload).encode("utf-8"),
# # #         method="POST",
# # #         headers={
# # #             "Content-Type":  "application/json",
# # #             "Accept":        "application/json",
# # #             "Authorization": f"token {api_key}:{api_secret}",
# # #         },
# # #     )

# # #     try:
# # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
# # #             data = json.loads(resp.read().decode())
# # #             name = (data.get("data") or {}).get("name", "")
# # #             log.info("✅ Payment Entry %d → Frappe %s  [%s  %s %.2f]",
# # #                      pe_id, name, inv_no,
# # #                      pe.get("currency", ""), float(pe.get("paid_amount", 0)))
# # #             return name or "SYNCED"

# # #     except urllib.error.HTTPError as e:
# # #         try:
# # #             err = json.loads(e.read().decode())
# # #             msg = (err.get("exception") or err.get("message") or
# # #                    str(err.get("_server_messages", "")) or f"HTTP {e.code}")
# # #         except Exception:
# # #             msg = f"HTTP {e.code}"

# # #         if e.code == 409:
# # #             log.info("Payment %d already on Frappe (409) - marking synced.", pe_id)
# # #             return "DUPLICATE"

# # #         # Invoice already paid (is_pos:1 on old invoices) - stop retrying
# # #         if e.code == 417:
# # #             _perma = ("already been fully paid", "already paid", "fully paid")
# # #             if any(p in msg.lower() for p in _perma):
# # #                 log.info("Payment %d - invoice already paid on Frappe, marking synced.", pe_id)
# # #                 return "ALREADY_PAID"

# # #         log.error("FAIL Payment Entry %d  HTTP %s: %s", pe_id, e.code, msg)
# # #         return None

# # #     except urllib.error.URLError as e:
# # #         log.warning("Network error pushing payment %d: %s", pe_id, e.reason)
# # #         return None

# # #     except Exception as e:
# # #         log.error("Unexpected error pushing payment %d: %s", pe_id, e)
# # #         return None


# # # # =============================================================================
# # # # PUBLIC — push all unsynced payment entries
# # # # =============================================================================

# # # def push_unsynced_payment_entries() -> dict:
# # #     """
# # #     1. Refresh frappe_invoice_ref from parent sales that were confirmed.
# # #     2. Push each unsynced payment entry to Frappe.
# # #     3. Mark synced with the returned PAY-xxxxx ref.
# # #     """
# # #     result = {"pushed": 0, "failed": 0, "skipped": 0, "total": 0}

# # #     api_key, api_secret = _get_credentials()
# # #     if not api_key or not api_secret:
# # #         log.warning("No credentials — skipping payment entry sync.")
# # #         return result

# # #     host     = _get_host()
# # #     defaults = _get_defaults()

# # #     # First: pull frappe_refs from confirmed invoices into pending payment entries
# # #     updated = refresh_frappe_refs()
# # #     if updated:
# # #         log.info("Refreshed frappe_invoice_ref on %d payment entry(ies).", updated)

# # #     entries = get_unsynced_payment_entries()
# # #     result["total"] = len(entries)

# # #     if not entries:
# # #         log.debug("No unsynced payment entries.")
# # #         return result

# # #     log.info("Pushing %d payment entry(ies) to Frappe…", len(entries))

# # #     for pe in entries:
# # #         frappe_name = _push_payment_entry(pe, api_key, api_secret, defaults, host)
# # #         if frappe_name:
# # #             mark_payment_synced(pe["id"], frappe_name)
# # #             result["pushed"] += 1
# # #         elif frappe_name is None:
# # #             # None = permanent skip (no frappe_inv yet), not a real failure
# # #             result["skipped"] += 1
# # #         else:
# # #             result["failed"] += 1

# # #         time.sleep(3)   # rate limit — 20/min max

# # #     log.info("Payment sync done — ✅ %d pushed  ❌ %d failed  ⏭ %d skipped",
# # #              result["pushed"], result["failed"], result["skipped"])
# # #     return result


# # # # =============================================================================
# # # # BACKGROUND DAEMON THREAD
# # # # =============================================================================

# # # def _sync_loop():
# # #     log.info("Payment entry sync daemon started (interval=%ds).", SYNC_INTERVAL)
# # #     while True:
# # #         if _sync_lock.acquire(blocking=False):
# # #             try:
# # #                 push_unsynced_payment_entries()
# # #             except Exception as e:
# # #                 log.error("Payment sync cycle error: %s", e)
# # #             finally:
# # #                 _sync_lock.release()
# # #         else:
# # #             log.debug("Previous payment sync still running — skipping.")
# # #         time.sleep(SYNC_INTERVAL)


# # # def start_payment_sync_daemon() -> threading.Thread:
# # #     """Non-blocking — safe to call from MainWindow.__init__."""
# # #     global _sync_thread
# # #     if _sync_thread and _sync_thread.is_alive():
# # #         return _sync_thread
# # #     t = threading.Thread(target=_sync_loop, daemon=True, name="PaymentSyncDaemon")
# # #     t.start()
# # #     _sync_thread = t
# # #     log.info("Payment entry sync daemon started.")
# # #     return t


# # # # =============================================================================
# # # # DEBUG
# # # # =============================================================================

# # # if __name__ == "__main__":
# # #     logging.basicConfig(level=logging.INFO,
# # #                         format="%(asctime)s [%(levelname)s] %(message)s")
# # #     print("Running one payment entry sync cycle...")
# # #     r = push_unsynced_payment_entries()
# # #     print(f"\nResult: {r['pushed']} pushed, {r['failed']} failed, "
# # #           f"{r['skipped']} skipped (of {r['total']} total)")

# # # =============================================================================
# # # services/payment_entry_service.py
# # #
# # # Manages local payment_entries table and syncs them to Frappe.
# # #
# # # FLOW:
# # #   1. When a sale is saved locally → create_payment_entry() stores it locally
# # #      with synced=0
# # #   2. When the Sales Invoice is confirmed on Frappe (frappe_ref is set) →
# # #      push_unsynced_payment_entries() pushes the Payment Entry to Frappe
# # #   3. Frappe returns a PAY-xxxxx ref → stored as frappe_payment_ref, synced=1
# # #
# # # PAYLOAD SENT TO FRAPPE:
# # #   POST /api/resource/Payment Entry
# # #   {
# # #     "doctype":              "Payment Entry",
# # #     "payment_type":         "Receive",
# # #     "party_type":           "Customer",
# # #     "party":                "Cathy",
# # #     "paid_to":              "Cash ZWG - H",
# # #     "paid_to_account_currency": "USD",
# # #     "paid_amount":          32.45,
# # #     "received_amount":      32.45,
# # #     "source_exchange_rate": 1.0,
# # #     "reference_no":         "ACC-SINV-2026-00034",
# # #     "reference_date":       "2026-03-19",
# # #     "remarks":              "POS Payment — Cash",
# # #     "docstatus":            1,
# # #     "references": [{
# # #         "reference_doctype": "Sales Invoice",
# # #         "reference_name":    "ACC-SINV-2026-00565",
# # #         "allocated_amount":  32.45
# # #     }]
# # #   }
# # # =============================================================================

# # from __future__ import annotations

# # import json
# # import logging
# # import time
# # import threading
# # import urllib.request
# # import urllib.error
# # from datetime import date

# # log = logging.getLogger("PaymentEntry")

# # SYNC_INTERVAL   = 60      # seconds between auto-sync cycles
# # REQUEST_TIMEOUT = 30

# # # Exchange rate cache: "FROM::TO::DATE" → float
# # _RATE_CACHE: dict[str, float] = {}


# # def _get_exchange_rate(from_currency: str, to_currency: str,
# #                        transaction_date: str,
# #                        api_key: str, api_secret: str, host: str) -> float:
# #     """
# #     Fetch live exchange rate from Frappe.
# #     Returns 1.0 for same currency, 0.0 if fetch fails (Frappe uses its own rate).
# #     """
# #     if not from_currency or from_currency.upper() == to_currency.upper():
# #         return 1.0

# #     cache_key = f"{from_currency.upper()}::{to_currency.upper()}::{transaction_date}"
# #     if cache_key in _RATE_CACHE:
# #         return _RATE_CACHE[cache_key]

# #     try:
# #         import urllib.parse
# #         url = (
# #             f"{host}/api/method/erpnext.setup.utils.get_exchange_rate"
# #             f"?from_currency={urllib.parse.quote(from_currency)}"
# #             f"&to_currency={urllib.parse.quote(to_currency)}"
# #             f"&transaction_date={transaction_date}"
# #         )
# #         req = urllib.request.Request(url)
# #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# #             data = json.loads(r.read().decode())
# #             rate = float(data.get("message") or data.get("result") or 0)
# #             if rate > 0:
# #                 _RATE_CACHE[cache_key] = rate
# #                 log.debug("Rate %s→%s on %s: %.6f", from_currency, to_currency, transaction_date, rate)
# #                 return rate
# #     except Exception as e:
# #         log.debug("Rate fetch failed (%s→%s): %s", from_currency, to_currency, e)

# #     return 0.0

# # _sync_lock:   threading.Lock          = threading.Lock()
# # _sync_thread: threading.Thread | None = None

# # # Method → Frappe Mode of Payment name
# # _METHOD_MAP = {
# #     "CASH":     "Cash",
# #     "CARD":     "Credit Card",
# #     "C / CARD": "Credit Card",
# #     "EFTPOS":   "Credit Card",
# #     "CHECK":    "Cheque",
# #     "CHEQUE":   "Cheque",
# #     "MOBILE":   "Mobile Money",
# #     "CREDIT":   "Credit",
# #     "TRANSFER": "Bank Transfer",
# # }


# # # =============================================================================
# # # CREDENTIALS / HOST / DEFAULTS
# # # =============================================================================

# # def _get_credentials() -> tuple[str, str]:
# #     try:
# #         from services.credentials import get_credentials
# #         return get_credentials()
# #     except Exception:
# #         pass
# #     return "", ""

# # def _get_host() -> str:
# #     try:
# #         from models.company_defaults import get_defaults
# #         host = (get_defaults() or {}).get("server_api_host", "").strip().rstrip("/")
# #         if host:
# #             return host
# #     except Exception:
# #         pass
# #     return "https://apk.havano.cloud"


# # def _get_defaults() -> dict:
# #     try:
# #         from models.company_defaults import get_defaults
# #         return get_defaults() or {}
# #     except Exception:
# #         return {}


# # # =============================================================================
# # # GL ACCOUNT RESOLVER  (which account to credit for each payment method)
# # # =============================================================================

# # _ACCOUNT_CACHE: dict[str, str] = {}


# # def _resolve_paid_to_account(mop_name: str, company: str, currency: str,
# #                               api_key: str, api_secret: str, host: str) -> str:
# #     """
# #     Looks up the GL account for a Mode of Payment from Frappe.
# #     Tries to match by currency if multiple accounts exist for the company.
# #     Falls back to server_pos_account in company_defaults.
# #     """
# #     cache_key = f"{mop_name}::{company}::{currency}"
# #     if cache_key in _ACCOUNT_CACHE:
# #         return _ACCOUNT_CACHE[cache_key]

# #     try:
# #         import urllib.parse
# #         url = (f"{host}/api/resource/Mode%20of%20Payment/"
# #                f"{urllib.parse.quote(mop_name)}?fields=[\"accounts\"]")
# #         req = urllib.request.Request(url)
# #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# #             data     = json.loads(r.read().decode())
# #             accounts = (data.get("data") or {}).get("accounts", [])

# #         company_accts = [a for a in accounts
# #                          if not company or a.get("company") == company]

# #         # Prefer account whose name contains the currency code
# #         matched = ""
# #         if currency:
# #             for a in company_accts:
# #                 if currency.upper() in (a.get("default_account") or "").upper():
# #                     matched = a["default_account"]; break

# #         if not matched and company_accts:
# #             matched = company_accts[0].get("default_account", "")

# #         if matched:
# #             _ACCOUNT_CACHE[cache_key] = matched
# #             return matched

# #     except Exception as e:
# #         log.debug("MOP account lookup failed for '%s': %s", mop_name, e)

# #     # Fallback
# #     fallback = _get_defaults().get("server_pos_account", "").strip()
# #     if fallback:
# #         _ACCOUNT_CACHE[cache_key] = fallback
# #         return fallback

# #     log.warning("No GL account for MOP '%s' currency=%s — Payment Entry may fail.",
# #                 mop_name, currency)
# #     return ""


# # # =============================================================================
# # # LOCAL DB  — create / read / update payment_entries
# # # =============================================================================

# # def create_payment_entry(sale: dict, override_rate: float = None,
# #                          override_account: str = None) -> int | None:
# #     """
# #     Called immediately after a sale is saved locally.
# #     Stores a payment_entry row with synced=0.
# #     Returns the new payment_entry id, or None on error.

# #     Will only create the entry once per sale (idempotent).
# #     """
# #     from database.db import get_connection
# #     conn = get_connection(); cur = conn.cursor()

# #     # Idempotency: don't create twice for the same sale
# #     cur.execute("SELECT id FROM payment_entries WHERE sale_id = ?", (sale["id"],))
# #     if cur.fetchone():
# #         conn.close()
# #         return None

# #     customer   = (sale.get("customer_name") or "default").strip()
# #     currency   = (sale.get("currency")      or "USD").strip().upper()
# #     amount     = float(sale.get("total")    or 0)
# #     inv_no     = sale.get("invoice_no", "")
# #     inv_date   = sale.get("invoice_date") or date.today().isoformat()
# #     method     = str(sale.get("method", "CASH")).upper().strip()
# #     mop        = _METHOD_MAP.get(method, "Cash")

# #     # Use override rate (from split) or fetch from Frappe
# #     if override_rate is not None:
# #         exch_rate = override_rate
# #     else:
# #         try:
# #             api_key, api_secret = _get_credentials()
# #             host = _get_host()
# #             defaults = _get_defaults()
# #             company_currency = defaults.get("server_company_currency", "USD").strip().upper() or "USD"
# #             exch_rate = _get_exchange_rate(
# #                 currency, company_currency, inv_date, api_key, api_secret, host
# #             ) if currency != company_currency else 1.0
# #         except Exception:
# #             exch_rate = 1.0

# #     cur.execute("""
# #         INSERT INTO payment_entries (
# #             sale_id, sale_invoice_no, frappe_invoice_ref,
# #             party, party_name,
# #             paid_amount, received_amount, source_exchange_rate,
# #             paid_to_account_currency, currency,
# #             mode_of_payment,
# #             reference_no, reference_date,
# #             remarks, synced
# #         ) OUTPUT INSERTED.id
# #         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# #     """, (
# #         sale["id"], inv_no,
# #         sale.get("frappe_ref") or None,
# #         customer, customer,
# #         amount, amount, exch_rate or 1.0,
# #         currency, currency,
# #         mop,
# #         inv_no, inv_date,
# #         f"POS Payment — {mop}",
# #     ))
# #     new_id = int(cur.fetchone()[0])
# #     conn.commit(); conn.close()
# #     log.debug("Payment entry %d created locally for sale %s", new_id, inv_no)
# #     return new_id


# # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# #     """
# #     Called when cashier uses Split payment.
# #     Creates one payment_entry row per currency in splits list.
# #     splits = [{"mode": "CASH", "currency": "USD", "amount": 5.0,
# #                "rate": 1.0, "base_amount": 5.0, "account": "Cash - AT"}, ...]
# #     Returns list of new payment_entry ids.
# #     """
# #     ids = []
# #     for split in splits:
# #         if not split.get("amount") or float(split["amount"]) <= 0:
# #             continue
# #         # Build a sale-like dict with the split's currency and amount
# #         split_sale = dict(sale)
# #         split_sale["currency"]      = split.get("currency", "USD")
# #         split_sale["total"]         = float(split.get("amount", 0))
# #         split_sale["method"]        = split.get("mode", "CASH")
# #         # Override exchange rate from split data
# #         new_id = create_payment_entry(
# #             split_sale,
# #             override_rate=float(split.get("rate", 1.0)),
# #             override_account=split.get("account", ""),
# #         )
# #         if new_id:
# #             ids.append(new_id)
# #     return ids


# # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# #     """
# #     Creates one payment_entry per currency from a split payment.
# #     Groups splits by currency, sums amounts, creates one entry each.
# #     Returns list of created payment_entry ids.
# #     """
# #     from datetime import date as _date

# #     # Group by currency
# #     by_currency: dict[str, dict] = {}
# #     for s in splits:
# #         curr = s.get("account_currency", "USD").upper()
# #         if curr not in by_currency:
# #             by_currency[curr] = {
# #                 "currency":      curr,
# #                 "paid_amount":   0.0,
# #                 "base_value":    0.0,
# #                 "rate":          s.get("rate", 1.0),
# #                 "account_name":  s.get("account_name", ""),
# #                 "mode":          s.get("mode", "Cash"),
# #             }
# #         by_currency[curr]["paid_amount"] += s.get("amount_paid", 0.0)
# #         by_currency[curr]["base_value"]  += s.get("base_value",  0.0)

# #     ids = []
# #     inv_no   = sale.get("invoice_no", "")
# #     inv_date = sale.get("invoice_date") or _date.today().isoformat()
# #     customer = (sale.get("customer_name") or "default").strip()

# #     from database.db import get_connection
# #     conn = get_connection(); cur = conn.cursor()

# #     for curr, grp in by_currency.items():
# #         # Idempotency: skip if already exists for this sale+currency
# #         cur.execute(
# #             "SELECT id FROM payment_entries WHERE sale_id=? AND currency=?",
# #             (sale["id"], curr)
# #         )
# #         if cur.fetchone():
# #             continue

# #         mop = _METHOD_MAP.get(grp["mode"].upper(), "Cash")

# #         cur.execute("""
# #             INSERT INTO payment_entries (
# #                 sale_id, sale_invoice_no, frappe_invoice_ref,
# #                 party, party_name,
# #                 paid_amount, received_amount, source_exchange_rate,
# #                 paid_to_account_currency, currency,
# #                 paid_to,
# #                 mode_of_payment,
# #                 reference_no, reference_date,
# #                 remarks, synced
# #             ) OUTPUT INSERTED.id
# #             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# #         """, (
# #             sale["id"], inv_no,
# #             sale.get("frappe_ref") or None,
# #             customer, customer,
# #             grp["paid_amount"],
# #             grp["base_value"],
# #             float(grp["rate"] or 1.0),
# #             curr, curr,
# #             grp["account_name"],
# #             mop,
# #             inv_no, inv_date,
# #             f"POS Split Payment — {mop} ({curr})",
# #         ))
# #         new_id = int(cur.fetchone()[0])
# #         ids.append(new_id)
# #         log.debug("Split payment entry %d created: %s %.2f %s",
# #                   new_id, curr, grp["paid_amount"], inv_no)

# #     conn.commit(); conn.close()
# #     return ids


# # def get_unsynced_payment_entries() -> list[dict]:
# #     """Returns payment entries that are ready to push (synced=0)."""
# #     from database.db import get_connection, fetchall_dicts
# #     conn = get_connection(); cur = conn.cursor()
# #     cur.execute("""
# #         SELECT pe.*, s.frappe_ref AS sale_frappe_ref
# #         FROM payment_entries pe
# #         LEFT JOIN sales s ON s.id = pe.sale_id
# #         WHERE pe.synced = 0
# #           AND (pe.frappe_invoice_ref IS NOT NULL
# #                OR s.frappe_ref IS NOT NULL)
# #         ORDER BY pe.id
# #     """)
# #     rows = fetchall_dicts(cur); conn.close()
# #     return rows


# # def mark_payment_synced(pe_id: int, frappe_payment_ref: str = "") -> None:
# #     from database.db import get_connection
# #     conn = get_connection(); cur = conn.cursor()
# #     cur.execute(
# #         "UPDATE payment_entries SET synced=1, frappe_payment_ref=? WHERE id=?",
# #         (frappe_payment_ref or None, pe_id)
# #     )
# #     # Also update the sales row
# #     cur.execute("""
# #         UPDATE sales SET payment_entry_ref=?, payment_synced=1
# #         WHERE id = (SELECT sale_id FROM payment_entries WHERE id=?)
# #     """, (frappe_payment_ref or None, pe_id))
# #     conn.commit(); conn.close()


# # def refresh_frappe_refs() -> int:
# #     """
# #     For payment entries that have no frappe_invoice_ref yet, copy it from
# #     the parent sale's frappe_ref. Call this before pushing payments.
# #     Returns count updated.
# #     """
# #     from database.db import get_connection
# #     conn = get_connection(); cur = conn.cursor()
# #     cur.execute("""
# #         UPDATE pe
# #         SET pe.frappe_invoice_ref = s.frappe_ref
# #         FROM payment_entries pe
# #         JOIN sales s ON s.id = pe.sale_id
# #         WHERE pe.synced = 0
# #           AND (pe.frappe_invoice_ref IS NULL OR pe.frappe_invoice_ref = '')
# #           AND s.frappe_ref IS NOT NULL AND s.frappe_ref != ''
# #     """)
# #     count = cur.rowcount
# #     conn.commit(); conn.close()
# #     return count


# # # =============================================================================
# # # BUILD FRAPPE PAYLOAD
# # # =============================================================================

# # def _build_payload(pe: dict, defaults: dict,
# #                    api_key: str, api_secret: str, host: str) -> dict:
# #     company  = defaults.get("server_company", "")
# #     currency = (pe.get("currency") or pe.get("paid_to_account_currency") or "USD").upper()
# #     mop      = pe.get("mode_of_payment") or "Cash"
# #     amount   = float(pe.get("paid_amount") or 0)
# #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()

# #     # Use local gl_accounts table first (synced from Frappe)
# #     paid_to          = (pe.get("paid_to") or "").strip()
# #     paid_to_currency = currency
# #     if not paid_to:
# #         try:
# #             from models.gl_account import get_account_for_payment
# #             acct = get_account_for_payment(currency, company)
# #             if acct:
# #                 paid_to          = acct["name"]
# #                 paid_to_currency = acct["account_currency"]
# #         except Exception as _e:
# #             log.debug("gl_account lookup failed: %s", _e)

# #     # Fallback to live Frappe lookup
# #     if not paid_to:
# #         paid_to = _resolve_paid_to_account(mop, company, currency, api_key, api_secret, host)

# #     # Use local exchange rate if not stored
# #     exch_rate = float(pe.get("source_exchange_rate") or 1.0)
# #     if exch_rate == 1.0 and currency not in ("USD", ""):
# #         try:
# #             from models.exchange_rate import get_rate
# #             stored = get_rate(currency, "USD")
# #             if stored:
# #                 exch_rate = stored
# #         except Exception:
# #             pass

# #     payload = {
# #         "doctype":                  "Payment Entry",
# #         "payment_type":             "Receive",
# #         "party_type":               "Customer",
# #         "party":                    pe.get("party") or "default",
# #         "party_name":               pe.get("party_name") or "default",
# #         "paid_to_account_currency": paid_to_currency,
# #         "paid_amount":              amount,
# #         "received_amount":          amount,
# #         "source_exchange_rate":     exch_rate,
# #         "reference_no":             pe.get("reference_no") or pe.get("sale_invoice_no", ""),
# #         "reference_date":           pe.get("reference_date") or date.today().isoformat(),
# #         "remarks":                  pe.get("remarks") or f"POS Payment — {mop}",
# #         "mode_of_payment":          mop,
# #         "docstatus":                1,
# #     }

# #     if paid_to:
# #         payload["paid_to"] = paid_to
# #     if company:
# #         payload["company"] = company

# #     # Link to the Sales Invoice on Frappe
# #     if frappe_inv:
# #         payload["references"] = [{
# #             "reference_doctype": "Sales Invoice",
# #             "reference_name":    frappe_inv,
# #             "allocated_amount":  amount,
# #         }]

# #     return payload


# # # =============================================================================
# # # PUSH ONE PAYMENT ENTRY
# # # =============================================================================

# # def _push_payment_entry(pe: dict, api_key: str, api_secret: str,
# #                         defaults: dict, host: str) -> str | None:
# #     """
# #     Posts one payment entry to Frappe.
# #     Returns Frappe's PAY-xxxxx name on success, None on failure.
# #     """
# #     pe_id  = pe["id"]
# #     inv_no = pe.get("sale_invoice_no", str(pe_id))

# #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()
# #     if not frappe_inv:
# #         log.warning("Payment %d — Sales Invoice not yet on Frappe, skipping.", pe_id)
# #         return None

# #     payload = _build_payload(pe, defaults, api_key, api_secret, host)

# #     url = f"{host}/api/resource/Payment%20Entry"
# #     req = urllib.request.Request(
# #         url=url,
# #         data=json.dumps(payload).encode("utf-8"),
# #         method="POST",
# #         headers={
# #             "Content-Type":  "application/json",
# #             "Accept":        "application/json",
# #             "Authorization": f"token {api_key}:{api_secret}",
# #         },
# #     )

# #     try:
# #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
# #             data = json.loads(resp.read().decode())
# #             name = (data.get("data") or {}).get("name", "")
# #             log.info("✅ Payment Entry %d → Frappe %s  [%s  %s %.2f]",
# #                      pe_id, name, inv_no,
# #                      pe.get("currency", ""), float(pe.get("paid_amount", 0)))
# #             return name or "SYNCED"

# #     except urllib.error.HTTPError as e:
# #         try:
# #             err = json.loads(e.read().decode())
# #             msg = (err.get("exception") or err.get("message") or
# #                    str(err.get("_server_messages", "")) or f"HTTP {e.code}")
# #         except Exception:
# #             msg = f"HTTP {e.code}"

# #         if e.code == 409:
# #             log.info("Payment %d already on Frappe (409) - marking synced.", pe_id)
# #             return "DUPLICATE"

# #         # Invoice already paid (is_pos:1 on old invoices) - stop retrying
# #         if e.code == 417:
# #             _perma = ("already been fully paid", "already paid", "fully paid")
# #             if any(p in msg.lower() for p in _perma):
# #                 log.info("Payment %d - invoice already paid on Frappe, marking synced.", pe_id)
# #                 return "ALREADY_PAID"

# #         log.error("FAIL Payment Entry %d  HTTP %s: %s", pe_id, e.code, msg)
# #         return None

# #     except urllib.error.URLError as e:
# #         log.warning("Network error pushing payment %d: %s", pe_id, e.reason)
# #         return None

# #     except Exception as e:
# #         log.error("Unexpected error pushing payment %d: %s", pe_id, e)
# #         return None


# # # =============================================================================
# # # PUBLIC — push all unsynced payment entries
# # # =============================================================================

# # def push_unsynced_payment_entries() -> dict:
# #     """
# #     1. Refresh frappe_invoice_ref from parent sales that were confirmed.
# #     2. Push each unsynced payment entry to Frappe.
# #     3. Mark synced with the returned PAY-xxxxx ref.
# #     """
# #     result = {"pushed": 0, "failed": 0, "skipped": 0, "total": 0}

# #     api_key, api_secret = _get_credentials()
# #     if not api_key or not api_secret:
# #         log.warning("No credentials — skipping payment entry sync.")
# #         return result

# #     host     = _get_host()
# #     defaults = _get_defaults()

# #     # First: pull frappe_refs from confirmed invoices into pending payment entries
# #     updated = refresh_frappe_refs()
# #     if updated:
# #         log.info("Refreshed frappe_invoice_ref on %d payment entry(ies).", updated)

# #     entries = get_unsynced_payment_entries()
# #     result["total"] = len(entries)

# #     if not entries:
# #         log.debug("No unsynced payment entries.")
# #         return result

# #     log.info("Pushing %d payment entry(ies) to Frappe…", len(entries))

# #     for pe in entries:
# #         frappe_name = _push_payment_entry(pe, api_key, api_secret, defaults, host)
# #         if frappe_name:
# #             mark_payment_synced(pe["id"], frappe_name)
# #             result["pushed"] += 1
# #         elif frappe_name is None:
# #             # None = permanent skip (no frappe_inv yet), not a real failure
# #             result["skipped"] += 1
# #         else:
# #             result["failed"] += 1

# #         time.sleep(3)   # rate limit — 20/min max

# #     log.info("Payment sync done — ✅ %d pushed  ❌ %d failed  ⏭ %d skipped",
# #              result["pushed"], result["failed"], result["skipped"])
# #     return result


# # # =============================================================================
# # # BACKGROUND DAEMON THREAD
# # # =============================================================================

# # def _sync_loop():
# #     log.info("Payment entry sync daemon started (interval=%ds).", SYNC_INTERVAL)
# #     while True:
# #         if _sync_lock.acquire(blocking=False):
# #             try:
# #                 push_unsynced_payment_entries()
# #             except Exception as e:
# #                 log.error("Payment sync cycle error: %s", e)
# #             finally:
# #                 _sync_lock.release()
# #         else:
# #             log.debug("Previous payment sync still running — skipping.")
# #         time.sleep(SYNC_INTERVAL)


# # def start_payment_sync_daemon() -> threading.Thread:
# #     """Non-blocking — safe to call from MainWindow.__init__."""
# #     global _sync_thread
# #     if _sync_thread and _sync_thread.is_alive():
# #         return _sync_thread
# #     t = threading.Thread(target=_sync_loop, daemon=True, name="PaymentSyncDaemon")
# #     t.start()
# #     _sync_thread = t
# #     log.info("Payment entry sync daemon started.")
# #     return t


# # # =============================================================================
# # # DEBUG
# # # =============================================================================

# # if __name__ == "__main__":
# #     logging.basicConfig(level=logging.INFO,
# #                         format="%(asctime)s [%(levelname)s] %(message)s")
# #     print("Running one payment entry sync cycle...")
# #     r = push_unsynced_payment_entries()
# #     print(f"\nResult: {r['pushed']} pushed, {r['failed']} failed, "
# #           f"{r['skipped']} skipped (of {r['total']} total)")


# # =============================================================================
# # services/payment_entry_service.py
# #
# # Manages local payment_entries table and syncs them to Frappe.
# #
# # FLOW:
# #   1. When a sale is saved locally → create_payment_entry() stores it locally
# #      with synced=0
# #   2. When the Sales Invoice is confirmed on Frappe (frappe_ref is set) →
# #      push_unsynced_payment_entries() pushes the Payment Entry to Frappe
# #   3. Frappe returns a PAY-xxxxx ref → stored as frappe_payment_ref, synced=1
# #
# # PAYLOAD SENT TO FRAPPE:
# #   POST /api/resource/Payment Entry
# #   {
# #     "doctype":              "Payment Entry",
# #     "payment_type":         "Receive",
# #     "party_type":           "Customer",
# #     "party":                "Cathy",
# #     "paid_to":              "Cash ZWG - H",
# #     "paid_to_account_currency": "USD",
# #     "paid_amount":          32.45,
# #     "received_amount":      32.45,
# #     "source_exchange_rate": 1.0,
# #     "reference_no":         "ACC-SINV-2026-00034",
# #     "reference_date":       "2026-03-19",
# #     "remarks":              "POS Payment — Cash",
# #     "docstatus":            1,
# #     "references": [{
# #         "reference_doctype": "Sales Invoice",
# #         "reference_name":    "ACC-SINV-2026-00565",
# #         "allocated_amount":  32.45
# #     }]
# #   }
# # =============================================================================

# from __future__ import annotations

# import json
# import logging
# import time
# import threading
# import urllib.request
# import urllib.error
# from datetime import date

# log = logging.getLogger("PaymentEntry")

# SYNC_INTERVAL   = 60      # seconds between auto-sync cycles
# REQUEST_TIMEOUT = 30

# # Exchange rate cache: "FROM::TO::DATE" → float
# _RATE_CACHE: dict[str, float] = {}


# def _get_exchange_rate(from_currency: str, to_currency: str,
#                        transaction_date: str,
#                        api_key: str, api_secret: str, host: str) -> float:
#     """
#     Fetch live exchange rate from Frappe.
#     Returns 1.0 for same currency, 0.0 if fetch fails (Frappe uses its own rate).
#     """
#     if not from_currency or from_currency.upper() == to_currency.upper():
#         return 1.0

#     cache_key = f"{from_currency.upper()}::{to_currency.upper()}::{transaction_date}"
#     if cache_key in _RATE_CACHE:
#         return _RATE_CACHE[cache_key]

#     try:
#         import urllib.parse
#         url = (
#             f"{host}/api/method/erpnext.setup.utils.get_exchange_rate"
#             f"?from_currency={urllib.parse.quote(from_currency)}"
#             f"&to_currency={urllib.parse.quote(to_currency)}"
#             f"&transaction_date={transaction_date}"
#         )
#         req = urllib.request.Request(url)
#         req.add_header("Authorization", f"token {api_key}:{api_secret}")
#         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
#             data = json.loads(r.read().decode())
#             rate = float(data.get("message") or data.get("result") or 0)
#             if rate > 0:
#                 _RATE_CACHE[cache_key] = rate
#                 log.debug("Rate %s→%s on %s: %.6f", from_currency, to_currency, transaction_date, rate)
#                 return rate
#     except Exception as e:
#         log.debug("Rate fetch failed (%s→%s): %s", from_currency, to_currency, e)

#     return 0.0

# _sync_lock:   threading.Lock          = threading.Lock()
# _sync_thread: threading.Thread | None = None

# # Method → Frappe Mode of Payment name
# _METHOD_MAP = {
#     "CASH":     "Cash",
#     "CARD":     "Credit Card",
#     "C / CARD": "Credit Card",
#     "EFTPOS":   "Credit Card",
#     "CHECK":    "Cheque",
#     "CHEQUE":   "Cheque",
#     "MOBILE":   "Mobile Money",
#     "CREDIT":   "Credit",
#     "TRANSFER": "Bank Transfer",
# }


# # =============================================================================
# # CREDENTIALS / HOST / DEFAULTS
# # =============================================================================

# def _get_credentials() -> tuple[str, str]:
#     try:
#         from services.credentials import get_credentials
#         return get_credentials()
#     except Exception:
#         pass
#     return "", ""

# def _get_host() -> str:
#     try:
#         from models.company_defaults import get_defaults
#         host = (get_defaults() or {}).get("server_api_host", "").strip().rstrip("/")
#         if host:
#             return host
#     except Exception:
#         pass
#     return "https://apk.havano.cloud"


# def _get_defaults() -> dict:
#     try:
#         from models.company_defaults import get_defaults
#         return get_defaults() or {}
#     except Exception:
#         return {}


# # =============================================================================
# # GL ACCOUNT RESOLVER  (which account to credit for each payment method)
# # =============================================================================

# _ACCOUNT_CACHE: dict[str, str] = {}


# def _resolve_paid_to_account(mop_name: str, company: str, currency: str,
#                               api_key: str, api_secret: str, host: str) -> str:
#     """
#     Looks up the GL account for a Mode of Payment from Frappe.
#     Tries to match by currency if multiple accounts exist for the company.
#     Falls back to server_pos_account in company_defaults.
#     """
#     cache_key = f"{mop_name}::{company}::{currency}"
#     if cache_key in _ACCOUNT_CACHE:
#         return _ACCOUNT_CACHE[cache_key]

#     try:
#         import urllib.parse
#         url = (f"{host}/api/resource/Mode%20of%20Payment/"
#                f"{urllib.parse.quote(mop_name)}?fields=[\"accounts\"]")
#         req = urllib.request.Request(url)
#         req.add_header("Authorization", f"token {api_key}:{api_secret}")
#         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
#             data     = json.loads(r.read().decode())
#             accounts = (data.get("data") or {}).get("accounts", [])

#         company_accts = [a for a in accounts
#                          if not company or a.get("company") == company]

#         # Prefer account whose name contains the currency code
#         matched = ""
#         if currency:
#             for a in company_accts:
#                 if currency.upper() in (a.get("default_account") or "").upper():
#                     matched = a["default_account"]; break

#         if not matched and company_accts:
#             matched = company_accts[0].get("default_account", "")

#         if matched:
#             _ACCOUNT_CACHE[cache_key] = matched
#             return matched

#     except Exception as e:
#         log.debug("MOP account lookup failed for '%s': %s", mop_name, e)

#     # Fallback
#     fallback = _get_defaults().get("server_pos_account", "").strip()
#     if fallback:
#         _ACCOUNT_CACHE[cache_key] = fallback
#         return fallback

#     log.warning("No GL account for MOP '%s' currency=%s — Payment Entry may fail.",
#                 mop_name, currency)
#     return ""


# # =============================================================================
# # LOCAL DB  — create / read / update payment_entries
# # =============================================================================

# def create_payment_entry(sale: dict, override_rate: float = None,
#                          override_account: str = None) -> int | None:
#     """
#     Called immediately after a sale is saved locally.
#     Stores a payment_entry row with synced=0.
#     Returns the new payment_entry id, or None on error.

#     Will only create the entry once per sale (idempotent).
#     """
#     from database.db import get_connection
#     conn = get_connection(); cur = conn.cursor()

#     # Idempotency: don't create twice for the same sale
#     cur.execute("SELECT id FROM payment_entries WHERE sale_id = ?", (sale["id"],))
#     if cur.fetchone():
#         conn.close()
#         return None

#     _walk_in   = _get_defaults().get("server_walk_in_customer", "").strip() or "default"
#     customer   = (sale.get("customer_name") or "").strip() or _walk_in
#     currency   = (sale.get("currency")      or "USD").strip().upper()
#     amount     = float(sale.get("total")    or 0)
#     inv_no     = sale.get("invoice_no", "")
#     inv_date   = sale.get("invoice_date") or date.today().isoformat()
#     method     = str(sale.get("method", "CASH")).upper().strip()
#     mop        = _METHOD_MAP.get(method, "Cash")

#     # Use override rate (from split) or fetch from Frappe
#     if override_rate is not None:
#         exch_rate = override_rate
#     else:
#         try:
#             api_key, api_secret = _get_credentials()
#             host = _get_host()
#             defaults = _get_defaults()
#             company_currency = defaults.get("server_company_currency", "USD").strip().upper() or "USD"
#             exch_rate = _get_exchange_rate(
#                 currency, company_currency, inv_date, api_key, api_secret, host
#             ) if currency != company_currency else 1.0
#         except Exception:
#             exch_rate = 1.0

#     cur.execute("""
#         INSERT INTO payment_entries (
#             sale_id, sale_invoice_no, frappe_invoice_ref,
#             party, party_name,
#             paid_amount, received_amount, source_exchange_rate,
#             paid_to_account_currency, currency,
#             mode_of_payment,
#             reference_no, reference_date,
#             remarks, synced
#         ) OUTPUT INSERTED.id
#         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
#     """, (
#         sale["id"], inv_no,
#         sale.get("frappe_ref") or None,
#         customer, customer,
#         amount, amount, exch_rate or 1.0,
#         currency, currency,
#         mop,
#         inv_no, inv_date,
#         f"POS Payment — {mop}",
#     ))
#     new_id = int(cur.fetchone()[0])
#     conn.commit(); conn.close()
#     log.debug("Payment entry %d created locally for sale %s", new_id, inv_no)
#     return new_id


# def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
#     """
#     Called when cashier uses Split payment.
#     Creates one payment_entry row per currency in splits list.
#     splits = [{"mode": "CASH", "currency": "USD", "amount": 5.0,
#                "rate": 1.0, "base_amount": 5.0, "account": "Cash - AT"}, ...]
#     Returns list of new payment_entry ids.
#     """
#     ids = []
#     for split in splits:
#         if not split.get("amount") or float(split["amount"]) <= 0:
#             continue
#         # Build a sale-like dict with the split's currency and amount
#         split_sale = dict(sale)
#         split_sale["currency"]      = split.get("currency", "USD")
#         split_sale["total"]         = float(split.get("amount", 0))
#         split_sale["method"]        = split.get("mode", "CASH")
#         # Override exchange rate from split data
#         new_id = create_payment_entry(
#             split_sale,
#             override_rate=float(split.get("rate", 1.0)),
#             override_account=split.get("account", ""),
#         )
#         if new_id:
#             ids.append(new_id)
#     return ids


# def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
#     """
#     Creates one payment_entry per currency from a split payment.
#     Groups splits by currency, sums amounts, creates one entry each.
#     Returns list of created payment_entry ids.
#     """
#     from datetime import date as _date

#     # Group by currency
#     by_currency: dict[str, dict] = {}
#     for s in splits:
#         curr = s.get("account_currency", "USD").upper()
#         if curr not in by_currency:
#             by_currency[curr] = {
#                 "currency":      curr,
#                 "paid_amount":   0.0,
#                 "base_value":    0.0,
#                 "rate":          s.get("rate", 1.0),
#                 "account_name":  s.get("account_name", ""),
#                 "mode":          s.get("mode", "Cash"),
#             }
#         by_currency[curr]["paid_amount"] += s.get("amount_paid", 0.0)
#         by_currency[curr]["base_value"]  += s.get("base_value",  0.0)

#     ids = []
#     inv_no   = sale.get("invoice_no", "")
#     inv_date = sale.get("invoice_date") or _date.today().isoformat()
#     _walk_in = _get_defaults().get("server_walk_in_customer", "").strip() or "default"
#     customer = (sale.get("customer_name") or "").strip() or _walk_in

#     from database.db import get_connection
#     conn = get_connection(); cur = conn.cursor()

#     for curr, grp in by_currency.items():
#         # Idempotency: skip if already exists for this sale+currency
#         cur.execute(
#             "SELECT id FROM payment_entries WHERE sale_id=? AND currency=?",
#             (sale["id"], curr)
#         )
#         if cur.fetchone():
#             continue

#         mop = _METHOD_MAP.get(grp["mode"].upper(), "Cash")

#         cur.execute("""
#             INSERT INTO payment_entries (
#                 sale_id, sale_invoice_no, frappe_invoice_ref,
#                 party, party_name,
#                 paid_amount, received_amount, source_exchange_rate,
#                 paid_to_account_currency, currency,
#                 paid_to,
#                 mode_of_payment,
#                 reference_no, reference_date,
#                 remarks, synced
#             ) OUTPUT INSERTED.id
#             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
#         """, (
#             sale["id"], inv_no,
#             sale.get("frappe_ref") or None,
#             customer, customer,
#             grp["paid_amount"],
#             grp["base_value"],
#             float(grp["rate"] or 1.0),
#             curr, curr,
#             grp["account_name"],
#             mop,
#             inv_no, inv_date,
#             f"POS Split Payment — {mop} ({curr})",
#         ))
#         new_id = int(cur.fetchone()[0])
#         ids.append(new_id)
#         log.debug("Split payment entry %d created: %s %.2f %s",
#                   new_id, curr, grp["paid_amount"], inv_no)

#     conn.commit(); conn.close()
#     return ids


# def get_unsynced_payment_entries() -> list[dict]:
#     """Returns payment entries that are ready to push (synced=0)."""
#     from database.db import get_connection, fetchall_dicts
#     conn = get_connection(); cur = conn.cursor()
#     cur.execute("""
#         SELECT pe.*, s.frappe_ref AS sale_frappe_ref
#         FROM payment_entries pe
#         LEFT JOIN sales s ON s.id = pe.sale_id
#         WHERE pe.synced = 0
#           AND (pe.frappe_invoice_ref IS NOT NULL
#                OR s.frappe_ref IS NOT NULL)
#         ORDER BY pe.id
#     """)
#     rows = fetchall_dicts(cur); conn.close()
#     return rows


# def mark_payment_synced(pe_id: int, frappe_payment_ref: str = "") -> None:
#     from database.db import get_connection
#     conn = get_connection(); cur = conn.cursor()
#     cur.execute(
#         "UPDATE payment_entries SET synced=1, frappe_payment_ref=? WHERE id=?",
#         (frappe_payment_ref or None, pe_id)
#     )
#     # Also update the sales row
#     cur.execute("""
#         UPDATE sales SET payment_entry_ref=?, payment_synced=1
#         WHERE id = (SELECT sale_id FROM payment_entries WHERE id=?)
#     """, (frappe_payment_ref or None, pe_id))
#     conn.commit(); conn.close()


# def refresh_frappe_refs() -> int:
#     """
#     For payment entries that have no frappe_invoice_ref yet, copy it from
#     the parent sale's frappe_ref. Call this before pushing payments.
#     Returns count updated.
#     """
#     from database.db import get_connection
#     conn = get_connection(); cur = conn.cursor()
#     cur.execute("""
#         UPDATE pe
#         SET pe.frappe_invoice_ref = s.frappe_ref
#         FROM payment_entries pe
#         JOIN sales s ON s.id = pe.sale_id
#         WHERE pe.synced = 0
#           AND (pe.frappe_invoice_ref IS NULL OR pe.frappe_invoice_ref = '')
#           AND s.frappe_ref IS NOT NULL AND s.frappe_ref != ''
#     """)
#     count = cur.rowcount
#     conn.commit(); conn.close()
#     return count


# # =============================================================================
# # BUILD FRAPPE PAYLOAD
# # =============================================================================

# def _build_payload(pe: dict, defaults: dict,
#                    api_key: str, api_secret: str, host: str) -> dict:
#     company  = defaults.get("server_company", "")
#     currency = (pe.get("currency") or pe.get("paid_to_account_currency") or "USD").upper()
#     mop      = pe.get("mode_of_payment") or "Cash"
#     amount   = float(pe.get("paid_amount") or 0)
#     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()

#     # Use local gl_accounts table first (synced from Frappe)
#     paid_to          = (pe.get("paid_to") or "").strip()
#     paid_to_currency = currency
#     if not paid_to:
#         try:
#             from models.gl_account import get_account_for_payment
#             acct = get_account_for_payment(currency, company)
#             if acct:
#                 paid_to          = acct["name"]
#                 paid_to_currency = acct["account_currency"]
#         except Exception as _e:
#             log.debug("gl_account lookup failed: %s", _e)

#     # Fallback to live Frappe lookup
#     if not paid_to:
#         paid_to = _resolve_paid_to_account(mop, company, currency, api_key, api_secret, host)

#     # Use local exchange rate if not stored
#     exch_rate = float(pe.get("source_exchange_rate") or 1.0)
#     if exch_rate == 1.0 and currency not in ("USD", ""):
#         try:
#             from models.exchange_rate import get_rate
#             stored = get_rate(currency, "USD")
#             if stored:
#                 exch_rate = stored
#         except Exception:
#             pass

#     payload = {
#         "doctype":                  "Payment Entry",
#         "payment_type":             "Receive",
#         "party_type":               "Customer",
#         "party":                    pe.get("party") or defaults.get("server_walk_in_customer", "").strip() or "default",
#         "party_name":               pe.get("party_name") or defaults.get("server_walk_in_customer", "").strip() or "default",
#         "paid_to_account_currency": paid_to_currency,
#         "paid_amount":              amount,
#         "received_amount":          amount,
#         "source_exchange_rate":     exch_rate,
#         "reference_no":             pe.get("reference_no") or pe.get("sale_invoice_no", ""),
#         "reference_date":           (
#             pe.get("reference_date").isoformat()
#             if hasattr(pe.get("reference_date"), "isoformat")
#             else pe.get("reference_date") or date.today().isoformat()
#         ),
#         "remarks":                  pe.get("remarks") or f"POS Payment — {mop}",
#         "mode_of_payment":          mop,
#         "docstatus":                1,
#     }

#     if paid_to:
#         payload["paid_to"] = paid_to
#     if company:
#         payload["company"] = company

#     # Link to the Sales Invoice on Frappe
#     if frappe_inv:
#         payload["references"] = [{
#             "reference_doctype": "Sales Invoice",
#             "reference_name":    frappe_inv,
#             "allocated_amount":  amount,
#         }]

#     return payload


# # =============================================================================
# # PUSH ONE PAYMENT ENTRY
# # =============================================================================

# def _push_payment_entry(pe: dict, api_key: str, api_secret: str,
#                         defaults: dict, host: str) -> str | None:
#     """
#     Posts one payment entry to Frappe.
#     Returns Frappe's PAY-xxxxx name on success, None on failure.
#     """
#     pe_id  = pe["id"]
#     inv_no = pe.get("sale_invoice_no", str(pe_id))

#     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()
#     if not frappe_inv:
#         log.warning("Payment %d — Sales Invoice not yet on Frappe, skipping.", pe_id)
#         return None

#     payload = _build_payload(pe, defaults, api_key, api_secret, host)

#     url = f"{host}/api/resource/Payment%20Entry"
#     req = urllib.request.Request(
#         url=url,
#         data=json.dumps(payload, default=lambda o: o.isoformat() if hasattr(o, 'isoformat') else str(o)).encode("utf-8"),
#         method="POST",
#         headers={
#             "Content-Type":  "application/json",
#             "Accept":        "application/json",
#             "Authorization": f"token {api_key}:{api_secret}",
#         },
#     )

#     try:
#         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
#             data = json.loads(resp.read().decode())
#             name = (data.get("data") or {}).get("name", "")
#             log.info("✅ Payment Entry %d → Frappe %s  [%s  %s %.2f]",
#                      pe_id, name, inv_no,
#                      pe.get("currency", ""), float(pe.get("paid_amount", 0)))
#             return name or "SYNCED"

#     except urllib.error.HTTPError as e:
#         try:
#             err = json.loads(e.read().decode())
#             msg = (err.get("exception") or err.get("message") or
#                    str(err.get("_server_messages", "")) or f"HTTP {e.code}")
#         except Exception:
#             msg = f"HTTP {e.code}"

#         if e.code == 409:
#             log.info("Payment %d already on Frappe (409) - marking synced.", pe_id)
#             return "DUPLICATE"

#         # Invoice already paid (is_pos:1 on old invoices) - stop retrying
#         if e.code == 417:
#             _perma = ("already been fully paid", "already paid", "fully paid")
#             if any(p in msg.lower() for p in _perma):
#                 log.info("Payment %d - invoice already paid on Frappe, marking synced.", pe_id)
#                 return "ALREADY_PAID"

#         log.error("FAIL Payment Entry %d  HTTP %s: %s", pe_id, e.code, msg)
#         return None

#     except urllib.error.URLError as e:
#         log.warning("Network error pushing payment %d: %s", pe_id, e.reason)
#         return None

#     except Exception as e:
#         log.error("Unexpected error pushing payment %d: %s", pe_id, e)
#         return None


# # =============================================================================
# # PUBLIC — push all unsynced payment entries
# # =============================================================================

# def push_unsynced_payment_entries() -> dict:
#     """
#     1. Refresh frappe_invoice_ref from parent sales that were confirmed.
#     2. Push each unsynced payment entry to Frappe.
#     3. Mark synced with the returned PAY-xxxxx ref.
#     """
#     result = {"pushed": 0, "failed": 0, "skipped": 0, "total": 0}

#     api_key, api_secret = _get_credentials()
#     if not api_key or not api_secret:
#         log.warning("No credentials — skipping payment entry sync.")
#         return result

#     host     = _get_host()
#     defaults = _get_defaults()

#     # First: pull frappe_refs from confirmed invoices into pending payment entries
#     updated = refresh_frappe_refs()
#     if updated:
#         log.info("Refreshed frappe_invoice_ref on %d payment entry(ies).", updated)

#     entries = get_unsynced_payment_entries()
#     result["total"] = len(entries)

#     if not entries:
#         log.debug("No unsynced payment entries.")
#         return result

#     log.info("Pushing %d payment entry(ies) to Frappe…", len(entries))

#     for pe in entries:
#         frappe_name = _push_payment_entry(pe, api_key, api_secret, defaults, host)
#         if frappe_name:
#             mark_payment_synced(pe["id"], frappe_name)
#             result["pushed"] += 1
#         elif frappe_name is None:
#             # None = permanent skip (no frappe_inv yet), not a real failure
#             result["skipped"] += 1
#         else:
#             result["failed"] += 1

#         time.sleep(3)   # rate limit — 20/min max

#     log.info("Payment sync done — ✅ %d pushed  ❌ %d failed  ⏭ %d skipped",
#              result["pushed"], result["failed"], result["skipped"])
#     return result


# # =============================================================================
# # BACKGROUND DAEMON THREAD
# # =============================================================================

# def _sync_loop():
#     log.info("Payment entry sync daemon started (interval=%ds).", SYNC_INTERVAL)
#     while True:
#         if _sync_lock.acquire(blocking=False):
#             try:
#                 push_unsynced_payment_entries()
#             except Exception as e:
#                 log.error("Payment sync cycle error: %s", e)
#             finally:
#                 _sync_lock.release()
#         else:
#             log.debug("Previous payment sync still running — skipping.")
#         time.sleep(SYNC_INTERVAL)


# def start_payment_sync_daemon() -> threading.Thread:
#     """Non-blocking — safe to call from MainWindow.__init__."""
#     global _sync_thread
#     if _sync_thread and _sync_thread.is_alive():
#         return _sync_thread
#     t = threading.Thread(target=_sync_loop, daemon=True, name="PaymentSyncDaemon")
#     t.start()
#     _sync_thread = t
#     log.info("Payment entry sync daemon started.")
#     return t


# # =============================================================================
# # DEBUG
# # =============================================================================

# if __name__ == "__main__":
#     logging.basicConfig(level=logging.INFO,
#                         format="%(asctime)s [%(levelname)s] %(message)s")
#     print("Running one payment entry sync cycle...")
#     r = push_unsynced_payment_entries()
#     print(f"\nResult: {r['pushed']} pushed, {r['failed']} failed, "
#           f"{r['skipped']} skipped (of {r['total']} total)")
# # # # # # # =============================================================================
# # # # # # # services/payment_entry_service.py
# # # # # # #
# # # # # # # Manages local payment_entries table and syncs them to Frappe.
# # # # # # #
# # # # # # # FLOW:
# # # # # # #   1. When a sale is saved locally → create_payment_entry() stores it locally
# # # # # # #      with synced=0
# # # # # # #   2. When the Sales Invoice is confirmed on Frappe (frappe_ref is set) →
# # # # # # #      push_unsynced_payment_entries() pushes the Payment Entry to Frappe
# # # # # # #   3. Frappe returns a PAY-xxxxx ref → stored as frappe_payment_ref, synced=1
# # # # # # #
# # # # # # # PAYLOAD SENT TO FRAPPE:
# # # # # # #   POST /api/resource/Payment Entry
# # # # # # #   {
# # # # # # #     "doctype":              "Payment Entry",
# # # # # # #     "payment_type":         "Receive",
# # # # # # #     "party_type":           "Customer",
# # # # # # #     "party":                "Cathy",
# # # # # # #     "paid_to":              "Cash ZWG - H",
# # # # # # #     "paid_to_account_currency": "USD",
# # # # # # #     "paid_amount":          32.45,
# # # # # # #     "received_amount":      32.45,
# # # # # # #     "source_exchange_rate": 1.0,
# # # # # # #     "reference_no":         "ACC-SINV-2026-00034",
# # # # # # #     "reference_date":       "2026-03-19",
# # # # # # #     "remarks":              "POS Payment — Cash",
# # # # # # #     "docstatus":            1,
# # # # # # #     "references": [{
# # # # # # #         "reference_doctype": "Sales Invoice",
# # # # # # #         "reference_name":    "ACC-SINV-2026-00565",
# # # # # # #         "allocated_amount":  32.45
# # # # # # #     }]
# # # # # # #   }
# # # # # # # =============================================================================

# # # # # # from __future__ import annotations

# # # # # # import json
# # # # # # import logging
# # # # # # import time
# # # # # # import threading
# # # # # # import urllib.request
# # # # # # import urllib.error
# # # # # # from datetime import date

# # # # # # log = logging.getLogger("PaymentEntry")

# # # # # # SYNC_INTERVAL   = 60      # seconds between auto-sync cycles
# # # # # # REQUEST_TIMEOUT = 30

# # # # # # # Exchange rate cache: "FROM::TO::DATE" → float
# # # # # # _RATE_CACHE: dict[str, float] = {}


# # # # # # def _get_exchange_rate(from_currency: str, to_currency: str,
# # # # # #                        transaction_date: str,
# # # # # #                        api_key: str, api_secret: str, host: str) -> float:
# # # # # #     """
# # # # # #     Fetch live exchange rate from Frappe.
# # # # # #     Returns 1.0 for same currency, 0.0 if fetch fails (Frappe uses its own rate).
# # # # # #     """
# # # # # #     if not from_currency or from_currency.upper() == to_currency.upper():
# # # # # #         return 1.0

# # # # # #     cache_key = f"{from_currency.upper()}::{to_currency.upper()}::{transaction_date}"
# # # # # #     if cache_key in _RATE_CACHE:
# # # # # #         return _RATE_CACHE[cache_key]

# # # # # #     try:
# # # # # #         import urllib.parse
# # # # # #         url = (
# # # # # #             f"{host}/api/method/erpnext.setup.utils.get_exchange_rate"
# # # # # #             f"?from_currency={urllib.parse.quote(from_currency)}"
# # # # # #             f"&to_currency={urllib.parse.quote(to_currency)}"
# # # # # #             f"&transaction_date={transaction_date}"
# # # # # #         )
# # # # # #         req = urllib.request.Request(url)
# # # # # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # # # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # # # # #             data = json.loads(r.read().decode())
# # # # # #             rate = float(data.get("message") or data.get("result") or 0)
# # # # # #             if rate > 0:
# # # # # #                 _RATE_CACHE[cache_key] = rate
# # # # # #                 log.debug("Rate %s→%s on %s: %.6f", from_currency, to_currency, transaction_date, rate)
# # # # # #                 return rate
# # # # # #     except Exception as e:
# # # # # #         log.debug("Rate fetch failed (%s→%s): %s", from_currency, to_currency, e)

# # # # # #     return 0.0

# # # # # # _sync_lock:   threading.Lock          = threading.Lock()
# # # # # # _sync_thread: threading.Thread | None = None

# # # # # # # Method → Frappe Mode of Payment name
# # # # # # _METHOD_MAP = {
# # # # # #     "CASH":     "Cash",
# # # # # #     "CARD":     "Credit Card",
# # # # # #     "C / CARD": "Credit Card",
# # # # # #     "EFTPOS":   "Credit Card",
# # # # # #     "CHECK":    "Cheque",
# # # # # #     "CHEQUE":   "Cheque",
# # # # # #     "MOBILE":   "Mobile Money",
# # # # # #     "CREDIT":   "Credit",
# # # # # #     "TRANSFER": "Bank Transfer",
# # # # # # }


# # # # # # # =============================================================================
# # # # # # # CREDENTIALS / HOST / DEFAULTS
# # # # # # # =============================================================================

# # # # # # def _get_credentials() -> tuple[str, str]:
# # # # # #     try:
# # # # # #         from services.auth_service import get_session
# # # # # #         s = get_session()
# # # # # #         if s.get("api_key") and s.get("api_secret"):
# # # # # #             return s["api_key"], s["api_secret"]
# # # # # #     except Exception:
# # # # # #         pass
# # # # # #     try:
# # # # # #         from database.db import get_connection
# # # # # #         conn = get_connection(); cur = conn.cursor()
# # # # # #         cur.execute("SELECT api_key, api_secret FROM company_defaults WHERE id = 1")
# # # # # #         row = cur.fetchone(); conn.close()
# # # # # #         if row and row[0] and row[1]:
# # # # # #             return row[0], row[1]
# # # # # #     except Exception:
# # # # # #         pass
# # # # # #     import os
# # # # # #     return os.environ.get("HAVANO_API_KEY", ""), os.environ.get("HAVANO_API_SECRET", "")


# # # # # # def _get_host() -> str:
# # # # # #     try:
# # # # # #         from models.company_defaults import get_defaults
# # # # # #         host = (get_defaults() or {}).get("server_api_host", "").strip().rstrip("/")
# # # # # #         if host:
# # # # # #             return host
# # # # # #     except Exception:
# # # # # #         pass
# # # # # #     return "https://apk.havano.cloud"


# # # # # # def _get_defaults() -> dict:
# # # # # #     try:
# # # # # #         from models.company_defaults import get_defaults
# # # # # #         return get_defaults() or {}
# # # # # #     except Exception:
# # # # # #         return {}


# # # # # # # =============================================================================
# # # # # # # GL ACCOUNT RESOLVER  (which account to credit for each payment method)
# # # # # # # =============================================================================

# # # # # # _ACCOUNT_CACHE: dict[str, str] = {}


# # # # # # def _resolve_paid_to_account(mop_name: str, company: str, currency: str,
# # # # # #                               api_key: str, api_secret: str, host: str) -> str:
# # # # # #     """
# # # # # #     Looks up the GL account for a Mode of Payment from Frappe.
# # # # # #     Tries to match by currency if multiple accounts exist for the company.
# # # # # #     Falls back to server_pos_account in company_defaults.
# # # # # #     """
# # # # # #     cache_key = f"{mop_name}::{company}::{currency}"
# # # # # #     if cache_key in _ACCOUNT_CACHE:
# # # # # #         return _ACCOUNT_CACHE[cache_key]

# # # # # #     try:
# # # # # #         import urllib.parse
# # # # # #         url = (f"{host}/api/resource/Mode%20of%20Payment/"
# # # # # #                f"{urllib.parse.quote(mop_name)}?fields=[\"accounts\"]")
# # # # # #         req = urllib.request.Request(url)
# # # # # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # # # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # # # # #             data     = json.loads(r.read().decode())
# # # # # #             accounts = (data.get("data") or {}).get("accounts", [])

# # # # # #         company_accts = [a for a in accounts
# # # # # #                          if not company or a.get("company") == company]

# # # # # #         # Prefer account whose name contains the currency code
# # # # # #         matched = ""
# # # # # #         if currency:
# # # # # #             for a in company_accts:
# # # # # #                 if currency.upper() in (a.get("default_account") or "").upper():
# # # # # #                     matched = a["default_account"]; break

# # # # # #         if not matched and company_accts:
# # # # # #             matched = company_accts[0].get("default_account", "")

# # # # # #         if matched:
# # # # # #             _ACCOUNT_CACHE[cache_key] = matched
# # # # # #             return matched

# # # # # #     except Exception as e:
# # # # # #         log.debug("MOP account lookup failed for '%s': %s", mop_name, e)

# # # # # #     # Fallback
# # # # # #     fallback = _get_defaults().get("server_pos_account", "").strip()
# # # # # #     if fallback:
# # # # # #         _ACCOUNT_CACHE[cache_key] = fallback
# # # # # #         return fallback

# # # # # #     log.warning("No GL account for MOP '%s' currency=%s — Payment Entry may fail.",
# # # # # #                 mop_name, currency)
# # # # # #     return ""


# # # # # # # =============================================================================
# # # # # # # LOCAL DB  — create / read / update payment_entries
# # # # # # # =============================================================================

# # # # # # def create_payment_entry(sale: dict, override_rate: float = None,
# # # # # #                          override_account: str = None) -> int | None:
# # # # # #     """
# # # # # #     Called immediately after a sale is saved locally.
# # # # # #     Stores a payment_entry row with synced=0.
# # # # # #     Returns the new payment_entry id, or None on error.

# # # # # #     Will only create the entry once per sale (idempotent).
# # # # # #     """
# # # # # #     from database.db import get_connection
# # # # # #     conn = get_connection(); cur = conn.cursor()

# # # # # #     # Idempotency: don't create twice for the same sale
# # # # # #     cur.execute("SELECT id FROM payment_entries WHERE sale_id = ?", (sale["id"],))
# # # # # #     if cur.fetchone():
# # # # # #         conn.close()
# # # # # #         return None

# # # # # #     customer   = (sale.get("customer_name") or "default").strip()
# # # # # #     currency   = (sale.get("currency")      or "USD").strip().upper()
# # # # # #     amount     = float(sale.get("total")    or 0)
# # # # # #     inv_no     = sale.get("invoice_no", "")
# # # # # #     inv_date   = sale.get("invoice_date") or date.today().isoformat()
# # # # # #     method     = str(sale.get("method", "CASH")).upper().strip()
# # # # # #     mop        = _METHOD_MAP.get(method, "Cash")

# # # # # #     # Use override rate (from split) or fetch from Frappe
# # # # # #     if override_rate is not None:
# # # # # #         exch_rate = override_rate
# # # # # #     else:
# # # # # #         try:
# # # # # #             api_key, api_secret = _get_credentials()
# # # # # #             host = _get_host()
# # # # # #             defaults = _get_defaults()
# # # # # #             company_currency = defaults.get("server_company_currency", "USD").strip().upper() or "USD"
# # # # # #             exch_rate = _get_exchange_rate(
# # # # # #                 currency, company_currency, inv_date, api_key, api_secret, host
# # # # # #             ) if currency != company_currency else 1.0
# # # # # #         except Exception:
# # # # # #             exch_rate = 1.0

# # # # # #     cur.execute("""
# # # # # #         INSERT INTO payment_entries (
# # # # # #             sale_id, sale_invoice_no, frappe_invoice_ref,
# # # # # #             party, party_name,
# # # # # #             paid_amount, received_amount, source_exchange_rate,
# # # # # #             paid_to_account_currency, currency,
# # # # # #             mode_of_payment,
# # # # # #             reference_no, reference_date,
# # # # # #             remarks, synced
# # # # # #         ) OUTPUT INSERTED.id
# # # # # #         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # # # # #     """, (
# # # # # #         sale["id"], inv_no,
# # # # # #         sale.get("frappe_ref") or None,
# # # # # #         customer, customer,
# # # # # #         amount, amount, exch_rate or 1.0,
# # # # # #         currency, currency,
# # # # # #         mop,
# # # # # #         inv_no, inv_date,
# # # # # #         f"POS Payment — {mop}",
# # # # # #     ))
# # # # # #     new_id = int(cur.fetchone()[0])
# # # # # #     conn.commit(); conn.close()
# # # # # #     log.debug("Payment entry %d created locally for sale %s", new_id, inv_no)
# # # # # #     return new_id


# # # # # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # # # # #     """
# # # # # #     Called when cashier uses Split payment.
# # # # # #     Creates one payment_entry row per currency in splits list.
# # # # # #     splits = [{"mode": "CASH", "currency": "USD", "amount": 5.0,
# # # # # #                "rate": 1.0, "base_amount": 5.0, "account": "Cash - AT"}, ...]
# # # # # #     Returns list of new payment_entry ids.
# # # # # #     """
# # # # # #     ids = []
# # # # # #     for split in splits:
# # # # # #         if not split.get("amount") or float(split["amount"]) <= 0:
# # # # # #             continue
# # # # # #         # Build a sale-like dict with the split's currency and amount
# # # # # #         split_sale = dict(sale)
# # # # # #         split_sale["currency"]      = split.get("currency", "USD")
# # # # # #         split_sale["total"]         = float(split.get("amount", 0))
# # # # # #         split_sale["method"]        = split.get("mode", "CASH")
# # # # # #         # Override exchange rate from split data
# # # # # #         new_id = create_payment_entry(
# # # # # #             split_sale,
# # # # # #             override_rate=float(split.get("rate", 1.0)),
# # # # # #             override_account=split.get("account", ""),
# # # # # #         )
# # # # # #         if new_id:
# # # # # #             ids.append(new_id)
# # # # # #     return ids


# # # # # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # # # # #     """
# # # # # #     Creates one payment_entry per currency from a split payment.
# # # # # #     Groups splits by currency, sums amounts, creates one entry each.
# # # # # #     Returns list of created payment_entry ids.
# # # # # #     """
# # # # # #     from datetime import date as _date

# # # # # #     # Group by currency
# # # # # #     by_currency: dict[str, dict] = {}
# # # # # #     for s in splits:
# # # # # #         curr = s.get("account_currency", "USD").upper()
# # # # # #         if curr not in by_currency:
# # # # # #             by_currency[curr] = {
# # # # # #                 "currency":      curr,
# # # # # #                 "paid_amount":   0.0,
# # # # # #                 "base_value":    0.0,
# # # # # #                 "rate":          s.get("rate", 1.0),
# # # # # #                 "account_name":  s.get("account_name", ""),
# # # # # #                 "mode":          s.get("mode", "Cash"),
# # # # # #             }
# # # # # #         by_currency[curr]["paid_amount"] += s.get("amount_paid", 0.0)
# # # # # #         by_currency[curr]["base_value"]  += s.get("base_value",  0.0)

# # # # # #     ids = []
# # # # # #     inv_no   = sale.get("invoice_no", "")
# # # # # #     inv_date = sale.get("invoice_date") or _date.today().isoformat()
# # # # # #     customer = (sale.get("customer_name") or "default").strip()

# # # # # #     from database.db import get_connection
# # # # # #     conn = get_connection(); cur = conn.cursor()

# # # # # #     for curr, grp in by_currency.items():
# # # # # #         # Idempotency: skip if already exists for this sale+currency
# # # # # #         cur.execute(
# # # # # #             "SELECT id FROM payment_entries WHERE sale_id=? AND currency=?",
# # # # # #             (sale["id"], curr)
# # # # # #         )
# # # # # #         if cur.fetchone():
# # # # # #             continue

# # # # # #         mop = _METHOD_MAP.get(grp["mode"].upper(), "Cash")

# # # # # #         cur.execute("""
# # # # # #             INSERT INTO payment_entries (
# # # # # #                 sale_id, sale_invoice_no, frappe_invoice_ref,
# # # # # #                 party, party_name,
# # # # # #                 paid_amount, received_amount, source_exchange_rate,
# # # # # #                 paid_to_account_currency, currency,
# # # # # #                 paid_to,
# # # # # #                 mode_of_payment,
# # # # # #                 reference_no, reference_date,
# # # # # #                 remarks, synced
# # # # # #             ) OUTPUT INSERTED.id
# # # # # #             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # # # # #         """, (
# # # # # #             sale["id"], inv_no,
# # # # # #             sale.get("frappe_ref") or None,
# # # # # #             customer, customer,
# # # # # #             grp["paid_amount"],
# # # # # #             grp["base_value"],
# # # # # #             float(grp["rate"] or 1.0),
# # # # # #             curr, curr,
# # # # # #             grp["account_name"],
# # # # # #             mop,
# # # # # #             inv_no, inv_date,
# # # # # #             f"POS Split Payment — {mop} ({curr})",
# # # # # #         ))
# # # # # #         new_id = int(cur.fetchone()[0])
# # # # # #         ids.append(new_id)
# # # # # #         log.debug("Split payment entry %d created: %s %.2f %s",
# # # # # #                   new_id, curr, grp["paid_amount"], inv_no)

# # # # # #     conn.commit(); conn.close()
# # # # # #     return ids


# # # # # # def get_unsynced_payment_entries() -> list[dict]:
# # # # # #     """Returns payment entries that are ready to push (synced=0)."""
# # # # # #     from database.db import get_connection, fetchall_dicts
# # # # # #     conn = get_connection(); cur = conn.cursor()
# # # # # #     cur.execute("""
# # # # # #         SELECT pe.*, s.frappe_ref AS sale_frappe_ref
# # # # # #         FROM payment_entries pe
# # # # # #         LEFT JOIN sales s ON s.id = pe.sale_id
# # # # # #         WHERE pe.synced = 0
# # # # # #           AND (pe.frappe_invoice_ref IS NOT NULL
# # # # # #                OR s.frappe_ref IS NOT NULL)
# # # # # #         ORDER BY pe.id
# # # # # #     """)
# # # # # #     rows = fetchall_dicts(cur); conn.close()
# # # # # #     return rows


# # # # # # def mark_payment_synced(pe_id: int, frappe_payment_ref: str = "") -> None:
# # # # # #     from database.db import get_connection
# # # # # #     conn = get_connection(); cur = conn.cursor()
# # # # # #     cur.execute(
# # # # # #         "UPDATE payment_entries SET synced=1, frappe_payment_ref=? WHERE id=?",
# # # # # #         (frappe_payment_ref or None, pe_id)
# # # # # #     )
# # # # # #     # Also update the sales row
# # # # # #     cur.execute("""
# # # # # #         UPDATE sales SET payment_entry_ref=?, payment_synced=1
# # # # # #         WHERE id = (SELECT sale_id FROM payment_entries WHERE id=?)
# # # # # #     """, (frappe_payment_ref or None, pe_id))
# # # # # #     conn.commit(); conn.close()


# # # # # # def refresh_frappe_refs() -> int:
# # # # # #     """
# # # # # #     For payment entries that have no frappe_invoice_ref yet, copy it from
# # # # # #     the parent sale's frappe_ref. Call this before pushing payments.
# # # # # #     Returns count updated.
# # # # # #     """
# # # # # #     from database.db import get_connection
# # # # # #     conn = get_connection(); cur = conn.cursor()
# # # # # #     cur.execute("""
# # # # # #         UPDATE pe
# # # # # #         SET pe.frappe_invoice_ref = s.frappe_ref
# # # # # #         FROM payment_entries pe
# # # # # #         JOIN sales s ON s.id = pe.sale_id
# # # # # #         WHERE pe.synced = 0
# # # # # #           AND (pe.frappe_invoice_ref IS NULL OR pe.frappe_invoice_ref = '')
# # # # # #           AND s.frappe_ref IS NOT NULL AND s.frappe_ref != ''
# # # # # #     """)
# # # # # #     count = cur.rowcount
# # # # # #     conn.commit(); conn.close()
# # # # # #     return count


# # # # # # # =============================================================================
# # # # # # # BUILD FRAPPE PAYLOAD
# # # # # # # =============================================================================

# # # # # # def _build_payload(pe: dict, defaults: dict,
# # # # # #                    api_key: str, api_secret: str, host: str) -> dict:
# # # # # #     company  = defaults.get("server_company", "")
# # # # # #     currency = (pe.get("currency") or pe.get("paid_to_account_currency") or "USD").upper()
# # # # # #     mop      = pe.get("mode_of_payment") or "Cash"
# # # # # #     amount   = float(pe.get("paid_amount") or 0)
# # # # # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()

# # # # # #     paid_to = _resolve_paid_to_account(mop, company, currency, api_key, api_secret, host)

# # # # # #     payload = {
# # # # # #         "doctype":                  "Payment Entry",
# # # # # #         "payment_type":             "Receive",
# # # # # #         "party_type":               "Customer",
# # # # # #         "party":                    pe.get("party") or "default",
# # # # # #         "party_name":               pe.get("party_name") or "default",
# # # # # #         "paid_to_account_currency": currency,
# # # # # #         "paid_amount":              amount,
# # # # # #         "received_amount":          amount,
# # # # # #         "source_exchange_rate":     float(pe.get("source_exchange_rate") or 1.0),
# # # # # #         "reference_no":             pe.get("reference_no") or pe.get("sale_invoice_no", ""),
# # # # # #         "reference_date":           pe.get("reference_date") or date.today().isoformat(),
# # # # # #         "remarks":                  pe.get("remarks") or f"POS Payment — {mop}",
# # # # # #         "mode_of_payment":          mop,
# # # # # #         "docstatus":                1,
# # # # # #     }

# # # # # #     if paid_to:
# # # # # #         payload["paid_to"] = paid_to
# # # # # #     if company:
# # # # # #         payload["company"] = company

# # # # # #     # Link to the Sales Invoice on Frappe
# # # # # #     if frappe_inv:
# # # # # #         payload["references"] = [{
# # # # # #             "reference_doctype": "Sales Invoice",
# # # # # #             "reference_name":    frappe_inv,
# # # # # #             "allocated_amount":  amount,
# # # # # #         }]

# # # # # #     return payload


# # # # # # # =============================================================================
# # # # # # # PUSH ONE PAYMENT ENTRY
# # # # # # # =============================================================================

# # # # # # def _push_payment_entry(pe: dict, api_key: str, api_secret: str,
# # # # # #                         defaults: dict, host: str) -> str | None:
# # # # # #     """
# # # # # #     Posts one payment entry to Frappe.
# # # # # #     Returns Frappe's PAY-xxxxx name on success, None on failure.
# # # # # #     """
# # # # # #     pe_id  = pe["id"]
# # # # # #     inv_no = pe.get("sale_invoice_no", str(pe_id))

# # # # # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()
# # # # # #     if not frappe_inv:
# # # # # #         log.warning("Payment %d — Sales Invoice not yet on Frappe, skipping.", pe_id)
# # # # # #         return None

# # # # # #     payload = _build_payload(pe, defaults, api_key, api_secret, host)

# # # # # #     url = f"{host}/api/resource/Payment%20Entry"
# # # # # #     req = urllib.request.Request(
# # # # # #         url=url,
# # # # # #         data=json.dumps(payload).encode("utf-8"),
# # # # # #         method="POST",
# # # # # #         headers={
# # # # # #             "Content-Type":  "application/json",
# # # # # #             "Accept":        "application/json",
# # # # # #             "Authorization": f"token {api_key}:{api_secret}",
# # # # # #         },
# # # # # #     )

# # # # # #     try:
# # # # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
# # # # # #             data = json.loads(resp.read().decode())
# # # # # #             name = (data.get("data") or {}).get("name", "")
# # # # # #             log.info("✅ Payment Entry %d → Frappe %s  [%s  %s %.2f]",
# # # # # #                      pe_id, name, inv_no,
# # # # # #                      pe.get("currency", ""), float(pe.get("paid_amount", 0)))
# # # # # #             return name or "SYNCED"

# # # # # #     except urllib.error.HTTPError as e:
# # # # # #         try:
# # # # # #             err = json.loads(e.read().decode())
# # # # # #             msg = (err.get("exception") or err.get("message") or
# # # # # #                    str(err.get("_server_messages", "")) or f"HTTP {e.code}")
# # # # # #         except Exception:
# # # # # #             msg = f"HTTP {e.code}"

# # # # # #         if e.code == 409:
# # # # # #             log.info("Payment %d already on Frappe (409) — marking synced.", pe_id)
# # # # # #             return "DUPLICATE"

# # # # # #         log.error("❌ Payment Entry %d  HTTP %s: %s", pe_id, e.code, msg)
# # # # # #         return None

# # # # # #     except urllib.error.URLError as e:
# # # # # #         log.warning("Network error pushing payment %d: %s", pe_id, e.reason)
# # # # # #         return None

# # # # # #     except Exception as e:
# # # # # #         log.error("Unexpected error pushing payment %d: %s", pe_id, e)
# # # # # #         return None


# # # # # # # =============================================================================
# # # # # # # PUBLIC — push all unsynced payment entries
# # # # # # # =============================================================================

# # # # # # def push_unsynced_payment_entries() -> dict:
# # # # # #     """
# # # # # #     1. Refresh frappe_invoice_ref from parent sales that were confirmed.
# # # # # #     2. Push each unsynced payment entry to Frappe.
# # # # # #     3. Mark synced with the returned PAY-xxxxx ref.
# # # # # #     """
# # # # # #     result = {"pushed": 0, "failed": 0, "skipped": 0, "total": 0}

# # # # # #     api_key, api_secret = _get_credentials()
# # # # # #     if not api_key or not api_secret:
# # # # # #         log.warning("No credentials — skipping payment entry sync.")
# # # # # #         return result

# # # # # #     host     = _get_host()
# # # # # #     defaults = _get_defaults()

# # # # # #     # First: pull frappe_refs from confirmed invoices into pending payment entries
# # # # # #     updated = refresh_frappe_refs()
# # # # # #     if updated:
# # # # # #         log.info("Refreshed frappe_invoice_ref on %d payment entry(ies).", updated)

# # # # # #     entries = get_unsynced_payment_entries()
# # # # # #     result["total"] = len(entries)

# # # # # #     if not entries:
# # # # # #         log.debug("No unsynced payment entries.")
# # # # # #         return result

# # # # # #     log.info("Pushing %d payment entry(ies) to Frappe…", len(entries))

# # # # # #     for pe in entries:
# # # # # #         frappe_name = _push_payment_entry(pe, api_key, api_secret, defaults, host)
# # # # # #         if frappe_name:
# # # # # #             mark_payment_synced(pe["id"], frappe_name)
# # # # # #             result["pushed"] += 1
# # # # # #         elif frappe_name is None:
# # # # # #             # None = permanent skip (no frappe_inv yet), not a real failure
# # # # # #             result["skipped"] += 1
# # # # # #         else:
# # # # # #             result["failed"] += 1

# # # # # #         time.sleep(3)   # rate limit — 20/min max

# # # # # #     log.info("Payment sync done — ✅ %d pushed  ❌ %d failed  ⏭ %d skipped",
# # # # # #              result["pushed"], result["failed"], result["skipped"])
# # # # # #     return result


# # # # # # # =============================================================================
# # # # # # # BACKGROUND DAEMON THREAD
# # # # # # # =============================================================================

# # # # # # def _sync_loop():
# # # # # #     log.info("Payment entry sync daemon started (interval=%ds).", SYNC_INTERVAL)
# # # # # #     while True:
# # # # # #         if _sync_lock.acquire(blocking=False):
# # # # # #             try:
# # # # # #                 push_unsynced_payment_entries()
# # # # # #             except Exception as e:
# # # # # #                 log.error("Payment sync cycle error: %s", e)
# # # # # #             finally:
# # # # # #                 _sync_lock.release()
# # # # # #         else:
# # # # # #             log.debug("Previous payment sync still running — skipping.")
# # # # # #         time.sleep(SYNC_INTERVAL)


# # # # # # def start_payment_sync_daemon() -> threading.Thread:
# # # # # #     """Non-blocking — safe to call from MainWindow.__init__."""
# # # # # #     global _sync_thread
# # # # # #     if _sync_thread and _sync_thread.is_alive():
# # # # # #         return _sync_thread
# # # # # #     t = threading.Thread(target=_sync_loop, daemon=True, name="PaymentSyncDaemon")
# # # # # #     t.start()
# # # # # #     _sync_thread = t
# # # # # #     log.info("Payment entry sync daemon started.")
# # # # # #     return t


# # # # # # # =============================================================================
# # # # # # # DEBUG
# # # # # # # =============================================================================

# # # # # # if __name__ == "__main__":
# # # # # #     logging.basicConfig(level=logging.INFO,
# # # # # #                         format="%(asctime)s [%(levelname)s] %(message)s")
# # # # # #     print("Running one payment entry sync cycle...")
# # # # # #     r = push_unsynced_payment_entries()
# # # # # #     print(f"\nResult: {r['pushed']} pushed, {r['failed']} failed, "
# # # # # #           f"{r['skipped']} skipped (of {r['total']} total)")
# # # # # # =============================================================================
# # # # # # services/payment_entry_service.py
# # # # # #
# # # # # # Manages local payment_entries table and syncs them to Frappe.
# # # # # #
# # # # # # FLOW:
# # # # # #   1. When a sale is saved locally → create_payment_entry() stores it locally
# # # # # #      with synced=0
# # # # # #   2. When the Sales Invoice is confirmed on Frappe (frappe_ref is set) →
# # # # # #      push_unsynced_payment_entries() pushes the Payment Entry to Frappe
# # # # # #   3. Frappe returns a PAY-xxxxx ref → stored as frappe_payment_ref, synced=1
# # # # # #
# # # # # # PAYLOAD SENT TO FRAPPE:
# # # # # #   POST /api/resource/Payment Entry
# # # # # #   {
# # # # # #     "doctype":              "Payment Entry",
# # # # # #     "payment_type":         "Receive",
# # # # # #     "party_type":           "Customer",
# # # # # #     "party":                "Cathy",
# # # # # #     "paid_to":              "Cash ZWG - H",
# # # # # #     "paid_to_account_currency": "USD",
# # # # # #     "paid_amount":          32.45,
# # # # # #     "received_amount":      32.45,
# # # # # #     "source_exchange_rate": 1.0,
# # # # # #     "reference_no":         "ACC-SINV-2026-00034",
# # # # # #     "reference_date":       "2026-03-19",
# # # # # #     "remarks":              "POS Payment — Cash",
# # # # # #     "docstatus":            1,
# # # # # #     "references": [{
# # # # # #         "reference_doctype": "Sales Invoice",
# # # # # #         "reference_name":    "ACC-SINV-2026-00565",
# # # # # #         "allocated_amount":  32.45
# # # # # #     }]
# # # # # #   }
# # # # # # =============================================================================

# # # # # from __future__ import annotations

# # # # # import json
# # # # # import logging
# # # # # import time
# # # # # import threading
# # # # # import urllib.request
# # # # # import urllib.error
# # # # # from datetime import date

# # # # # log = logging.getLogger("PaymentEntry")

# # # # # SYNC_INTERVAL   = 60      # seconds between auto-sync cycles
# # # # # REQUEST_TIMEOUT = 30

# # # # # # Exchange rate cache: "FROM::TO::DATE" → float
# # # # # _RATE_CACHE: dict[str, float] = {}


# # # # # def _get_exchange_rate(from_currency: str, to_currency: str,
# # # # #                        transaction_date: str,
# # # # #                        api_key: str, api_secret: str, host: str) -> float:
# # # # #     """
# # # # #     Fetch live exchange rate from Frappe.
# # # # #     Returns 1.0 for same currency, 0.0 if fetch fails (Frappe uses its own rate).
# # # # #     """
# # # # #     if not from_currency or from_currency.upper() == to_currency.upper():
# # # # #         return 1.0

# # # # #     cache_key = f"{from_currency.upper()}::{to_currency.upper()}::{transaction_date}"
# # # # #     if cache_key in _RATE_CACHE:
# # # # #         return _RATE_CACHE[cache_key]

# # # # #     try:
# # # # #         import urllib.parse
# # # # #         url = (
# # # # #             f"{host}/api/method/erpnext.setup.utils.get_exchange_rate"
# # # # #             f"?from_currency={urllib.parse.quote(from_currency)}"
# # # # #             f"&to_currency={urllib.parse.quote(to_currency)}"
# # # # #             f"&transaction_date={transaction_date}"
# # # # #         )
# # # # #         req = urllib.request.Request(url)
# # # # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # # # #             data = json.loads(r.read().decode())
# # # # #             rate = float(data.get("message") or data.get("result") or 0)
# # # # #             if rate > 0:
# # # # #                 _RATE_CACHE[cache_key] = rate
# # # # #                 log.debug("Rate %s→%s on %s: %.6f", from_currency, to_currency, transaction_date, rate)
# # # # #                 return rate
# # # # #     except Exception as e:
# # # # #         log.debug("Rate fetch failed (%s→%s): %s", from_currency, to_currency, e)

# # # # #     return 0.0

# # # # # _sync_lock:   threading.Lock          = threading.Lock()
# # # # # _sync_thread: threading.Thread | None = None

# # # # # # Method → Frappe Mode of Payment name
# # # # # _METHOD_MAP = {
# # # # #     "CASH":     "Cash",
# # # # #     "CARD":     "Credit Card",
# # # # #     "C / CARD": "Credit Card",
# # # # #     "EFTPOS":   "Credit Card",
# # # # #     "CHECK":    "Cheque",
# # # # #     "CHEQUE":   "Cheque",
# # # # #     "MOBILE":   "Mobile Money",
# # # # #     "CREDIT":   "Credit",
# # # # #     "TRANSFER": "Bank Transfer",
# # # # # }


# # # # # # =============================================================================
# # # # # # CREDENTIALS / HOST / DEFAULTS
# # # # # # =============================================================================

# # # # # def _get_credentials() -> tuple[str, str]:
# # # # #     try:
# # # # #         from services.auth_service import get_session
# # # # #         s = get_session()
# # # # #         if s.get("api_key") and s.get("api_secret"):
# # # # #             return s["api_key"], s["api_secret"]
# # # # #     except Exception:
# # # # #         pass
# # # # #     try:
# # # # #         from database.db import get_connection
# # # # #         conn = get_connection(); cur = conn.cursor()
# # # # #         cur.execute("SELECT api_key, api_secret FROM company_defaults WHERE id = 1")
# # # # #         row = cur.fetchone(); conn.close()
# # # # #         if row and row[0] and row[1]:
# # # # #             return row[0], row[1]
# # # # #     except Exception:
# # # # #         pass
# # # # #     import os
# # # # #     return os.environ.get("HAVANO_API_KEY", ""), os.environ.get("HAVANO_API_SECRET", "")


# # # # # def _get_host() -> str:
# # # # #     try:
# # # # #         from models.company_defaults import get_defaults
# # # # #         host = (get_defaults() or {}).get("server_api_host", "").strip().rstrip("/")
# # # # #         if host:
# # # # #             return host
# # # # #     except Exception:
# # # # #         pass
# # # # #     return "https://apk.havano.cloud"


# # # # # def _get_defaults() -> dict:
# # # # #     try:
# # # # #         from models.company_defaults import get_defaults
# # # # #         return get_defaults() or {}
# # # # #     except Exception:
# # # # #         return {}


# # # # # # =============================================================================
# # # # # # GL ACCOUNT RESOLVER  (which account to credit for each payment method)
# # # # # # =============================================================================

# # # # # _ACCOUNT_CACHE: dict[str, str] = {}


# # # # # def _resolve_paid_to_account(mop_name: str, company: str, currency: str,
# # # # #                               api_key: str, api_secret: str, host: str) -> str:
# # # # #     """
# # # # #     Looks up the GL account for a Mode of Payment from Frappe.
# # # # #     Tries to match by currency if multiple accounts exist for the company.
# # # # #     Falls back to server_pos_account in company_defaults.
# # # # #     """
# # # # #     cache_key = f"{mop_name}::{company}::{currency}"
# # # # #     if cache_key in _ACCOUNT_CACHE:
# # # # #         return _ACCOUNT_CACHE[cache_key]

# # # # #     try:
# # # # #         import urllib.parse
# # # # #         url = (f"{host}/api/resource/Mode%20of%20Payment/"
# # # # #                f"{urllib.parse.quote(mop_name)}?fields=[\"accounts\"]")
# # # # #         req = urllib.request.Request(url)
# # # # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # # # #             data     = json.loads(r.read().decode())
# # # # #             accounts = (data.get("data") or {}).get("accounts", [])

# # # # #         company_accts = [a for a in accounts
# # # # #                          if not company or a.get("company") == company]

# # # # #         # Prefer account whose name contains the currency code
# # # # #         matched = ""
# # # # #         if currency:
# # # # #             for a in company_accts:
# # # # #                 if currency.upper() in (a.get("default_account") or "").upper():
# # # # #                     matched = a["default_account"]; break

# # # # #         if not matched and company_accts:
# # # # #             matched = company_accts[0].get("default_account", "")

# # # # #         if matched:
# # # # #             _ACCOUNT_CACHE[cache_key] = matched
# # # # #             return matched

# # # # #     except Exception as e:
# # # # #         log.debug("MOP account lookup failed for '%s': %s", mop_name, e)

# # # # #     # Fallback
# # # # #     fallback = _get_defaults().get("server_pos_account", "").strip()
# # # # #     if fallback:
# # # # #         _ACCOUNT_CACHE[cache_key] = fallback
# # # # #         return fallback

# # # # #     log.warning("No GL account for MOP '%s' currency=%s — Payment Entry may fail.",
# # # # #                 mop_name, currency)
# # # # #     return ""


# # # # # # =============================================================================
# # # # # # LOCAL DB  — create / read / update payment_entries
# # # # # # =============================================================================

# # # # # def create_payment_entry(sale: dict, override_rate: float = None,
# # # # #                          override_account: str = None) -> int | None:
# # # # #     """
# # # # #     Called immediately after a sale is saved locally.
# # # # #     Stores a payment_entry row with synced=0.
# # # # #     Returns the new payment_entry id, or None on error.

# # # # #     Will only create the entry once per sale (idempotent).
# # # # #     """
# # # # #     from database.db import get_connection
# # # # #     conn = get_connection(); cur = conn.cursor()

# # # # #     # Idempotency: don't create twice for the same sale
# # # # #     cur.execute("SELECT id FROM payment_entries WHERE sale_id = ?", (sale["id"],))
# # # # #     if cur.fetchone():
# # # # #         conn.close()
# # # # #         return None

# # # # #     customer   = (sale.get("customer_name") or "default").strip()
# # # # #     currency   = (sale.get("currency")      or "USD").strip().upper()
# # # # #     amount     = float(sale.get("total")    or 0)
# # # # #     inv_no     = sale.get("invoice_no", "")
# # # # #     inv_date   = sale.get("invoice_date") or date.today().isoformat()
# # # # #     method     = str(sale.get("method", "CASH")).upper().strip()
# # # # #     mop        = _METHOD_MAP.get(method, "Cash")

# # # # #     # Use override rate (from split) or fetch from Frappe
# # # # #     if override_rate is not None:
# # # # #         exch_rate = override_rate
# # # # #     else:
# # # # #         try:
# # # # #             api_key, api_secret = _get_credentials()
# # # # #             host = _get_host()
# # # # #             defaults = _get_defaults()
# # # # #             company_currency = defaults.get("server_company_currency", "USD").strip().upper() or "USD"
# # # # #             exch_rate = _get_exchange_rate(
# # # # #                 currency, company_currency, inv_date, api_key, api_secret, host
# # # # #             ) if currency != company_currency else 1.0
# # # # #         except Exception:
# # # # #             exch_rate = 1.0

# # # # #     cur.execute("""
# # # # #         INSERT INTO payment_entries (
# # # # #             sale_id, sale_invoice_no, frappe_invoice_ref,
# # # # #             party, party_name,
# # # # #             paid_amount, received_amount, source_exchange_rate,
# # # # #             paid_to_account_currency, currency,
# # # # #             mode_of_payment,
# # # # #             reference_no, reference_date,
# # # # #             remarks, synced
# # # # #         ) OUTPUT INSERTED.id
# # # # #         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # # # #     """, (
# # # # #         sale["id"], inv_no,
# # # # #         sale.get("frappe_ref") or None,
# # # # #         customer, customer,
# # # # #         amount, amount, exch_rate or 1.0,
# # # # #         currency, currency,
# # # # #         mop,
# # # # #         inv_no, inv_date,
# # # # #         f"POS Payment — {mop}",
# # # # #     ))
# # # # #     new_id = int(cur.fetchone()[0])
# # # # #     conn.commit(); conn.close()
# # # # #     log.debug("Payment entry %d created locally for sale %s", new_id, inv_no)
# # # # #     return new_id


# # # # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # # # #     """
# # # # #     Called when cashier uses Split payment.
# # # # #     Creates one payment_entry row per currency in splits list.
# # # # #     splits = [{"mode": "CASH", "currency": "USD", "amount": 5.0,
# # # # #                "rate": 1.0, "base_amount": 5.0, "account": "Cash - AT"}, ...]
# # # # #     Returns list of new payment_entry ids.
# # # # #     """
# # # # #     ids = []
# # # # #     for split in splits:
# # # # #         if not split.get("amount") or float(split["amount"]) <= 0:
# # # # #             continue
# # # # #         # Build a sale-like dict with the split's currency and amount
# # # # #         split_sale = dict(sale)
# # # # #         split_sale["currency"]      = split.get("currency", "USD")
# # # # #         split_sale["total"]         = float(split.get("amount", 0))
# # # # #         split_sale["method"]        = split.get("mode", "CASH")
# # # # #         # Override exchange rate from split data
# # # # #         new_id = create_payment_entry(
# # # # #             split_sale,
# # # # #             override_rate=float(split.get("rate", 1.0)),
# # # # #             override_account=split.get("account", ""),
# # # # #         )
# # # # #         if new_id:
# # # # #             ids.append(new_id)
# # # # #     return ids


# # # # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # # # #     """
# # # # #     Creates one payment_entry per currency from a split payment.
# # # # #     Groups splits by currency, sums amounts, creates one entry each.
# # # # #     Returns list of created payment_entry ids.
# # # # #     """
# # # # #     from datetime import date as _date

# # # # #     # Group by currency
# # # # #     by_currency: dict[str, dict] = {}
# # # # #     for s in splits:
# # # # #         curr = s.get("account_currency", "USD").upper()
# # # # #         if curr not in by_currency:
# # # # #             by_currency[curr] = {
# # # # #                 "currency":      curr,
# # # # #                 "paid_amount":   0.0,
# # # # #                 "base_value":    0.0,
# # # # #                 "rate":          s.get("rate", 1.0),
# # # # #                 "account_name":  s.get("account_name", ""),
# # # # #                 "mode":          s.get("mode", "Cash"),
# # # # #             }
# # # # #         by_currency[curr]["paid_amount"] += s.get("amount_paid", 0.0)
# # # # #         by_currency[curr]["base_value"]  += s.get("base_value",  0.0)

# # # # #     ids = []
# # # # #     inv_no   = sale.get("invoice_no", "")
# # # # #     inv_date = sale.get("invoice_date") or _date.today().isoformat()
# # # # #     customer = (sale.get("customer_name") or "default").strip()

# # # # #     from database.db import get_connection
# # # # #     conn = get_connection(); cur = conn.cursor()

# # # # #     for curr, grp in by_currency.items():
# # # # #         # Idempotency: skip if already exists for this sale+currency
# # # # #         cur.execute(
# # # # #             "SELECT id FROM payment_entries WHERE sale_id=? AND currency=?",
# # # # #             (sale["id"], curr)
# # # # #         )
# # # # #         if cur.fetchone():
# # # # #             continue

# # # # #         mop = _METHOD_MAP.get(grp["mode"].upper(), "Cash")

# # # # #         cur.execute("""
# # # # #             INSERT INTO payment_entries (
# # # # #                 sale_id, sale_invoice_no, frappe_invoice_ref,
# # # # #                 party, party_name,
# # # # #                 paid_amount, received_amount, source_exchange_rate,
# # # # #                 paid_to_account_currency, currency,
# # # # #                 paid_to,
# # # # #                 mode_of_payment,
# # # # #                 reference_no, reference_date,
# # # # #                 remarks, synced
# # # # #             ) OUTPUT INSERTED.id
# # # # #             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # # # #         """, (
# # # # #             sale["id"], inv_no,
# # # # #             sale.get("frappe_ref") or None,
# # # # #             customer, customer,
# # # # #             grp["paid_amount"],
# # # # #             grp["base_value"],
# # # # #             float(grp["rate"] or 1.0),
# # # # #             curr, curr,
# # # # #             grp["account_name"],
# # # # #             mop,
# # # # #             inv_no, inv_date,
# # # # #             f"POS Split Payment — {mop} ({curr})",
# # # # #         ))
# # # # #         new_id = int(cur.fetchone()[0])
# # # # #         ids.append(new_id)
# # # # #         log.debug("Split payment entry %d created: %s %.2f %s",
# # # # #                   new_id, curr, grp["paid_amount"], inv_no)

# # # # #     conn.commit(); conn.close()
# # # # #     return ids


# # # # # def get_unsynced_payment_entries() -> list[dict]:
# # # # #     """Returns payment entries that are ready to push (synced=0)."""
# # # # #     from database.db import get_connection, fetchall_dicts
# # # # #     conn = get_connection(); cur = conn.cursor()
# # # # #     cur.execute("""
# # # # #         SELECT pe.*, s.frappe_ref AS sale_frappe_ref
# # # # #         FROM payment_entries pe
# # # # #         LEFT JOIN sales s ON s.id = pe.sale_id
# # # # #         WHERE pe.synced = 0
# # # # #           AND (pe.frappe_invoice_ref IS NOT NULL
# # # # #                OR s.frappe_ref IS NOT NULL)
# # # # #         ORDER BY pe.id
# # # # #     """)
# # # # #     rows = fetchall_dicts(cur); conn.close()
# # # # #     return rows


# # # # # def mark_payment_synced(pe_id: int, frappe_payment_ref: str = "") -> None:
# # # # #     from database.db import get_connection
# # # # #     conn = get_connection(); cur = conn.cursor()
# # # # #     cur.execute(
# # # # #         "UPDATE payment_entries SET synced=1, frappe_payment_ref=? WHERE id=?",
# # # # #         (frappe_payment_ref or None, pe_id)
# # # # #     )
# # # # #     # Also update the sales row
# # # # #     cur.execute("""
# # # # #         UPDATE sales SET payment_entry_ref=?, payment_synced=1
# # # # #         WHERE id = (SELECT sale_id FROM payment_entries WHERE id=?)
# # # # #     """, (frappe_payment_ref or None, pe_id))
# # # # #     conn.commit(); conn.close()


# # # # # def refresh_frappe_refs() -> int:
# # # # #     """
# # # # #     For payment entries that have no frappe_invoice_ref yet, copy it from
# # # # #     the parent sale's frappe_ref. Call this before pushing payments.
# # # # #     Returns count updated.
# # # # #     """
# # # # #     from database.db import get_connection
# # # # #     conn = get_connection(); cur = conn.cursor()
# # # # #     cur.execute("""
# # # # #         UPDATE pe
# # # # #         SET pe.frappe_invoice_ref = s.frappe_ref
# # # # #         FROM payment_entries pe
# # # # #         JOIN sales s ON s.id = pe.sale_id
# # # # #         WHERE pe.synced = 0
# # # # #           AND (pe.frappe_invoice_ref IS NULL OR pe.frappe_invoice_ref = '')
# # # # #           AND s.frappe_ref IS NOT NULL AND s.frappe_ref != ''
# # # # #     """)
# # # # #     count = cur.rowcount
# # # # #     conn.commit(); conn.close()
# # # # #     return count


# # # # # # =============================================================================
# # # # # # BUILD FRAPPE PAYLOAD
# # # # # # =============================================================================

# # # # # def _build_payload(pe: dict, defaults: dict,
# # # # #                    api_key: str, api_secret: str, host: str) -> dict:
# # # # #     company  = defaults.get("server_company", "")
# # # # #     currency = (pe.get("currency") or pe.get("paid_to_account_currency") or "USD").upper()
# # # # #     mop      = pe.get("mode_of_payment") or "Cash"
# # # # #     amount   = float(pe.get("paid_amount") or 0)
# # # # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()

# # # # #     # Use local gl_accounts table first (synced from Frappe)
# # # # #     paid_to          = (pe.get("paid_to") or "").strip()
# # # # #     paid_to_currency = currency
# # # # #     if not paid_to:
# # # # #         try:
# # # # #             from models.gl_account import get_account_for_payment
# # # # #             acct = get_account_for_payment(currency, company)
# # # # #             if acct:
# # # # #                 paid_to          = acct["name"]
# # # # #                 paid_to_currency = acct["account_currency"]
# # # # #         except Exception as _e:
# # # # #             log.debug("gl_account lookup failed: %s", _e)

# # # # #     # Fallback to live Frappe lookup
# # # # #     if not paid_to:
# # # # #         paid_to = _resolve_paid_to_account(mop, company, currency, api_key, api_secret, host)

# # # # #     # Use local exchange rate if not stored
# # # # #     exch_rate = float(pe.get("source_exchange_rate") or 1.0)
# # # # #     if exch_rate == 1.0 and currency not in ("USD", ""):
# # # # #         try:
# # # # #             from models.exchange_rate import get_rate
# # # # #             stored = get_rate(currency, "USD")
# # # # #             if stored:
# # # # #                 exch_rate = stored
# # # # #         except Exception:
# # # # #             pass

# # # # #     payload = {
# # # # #         "doctype":                  "Payment Entry",
# # # # #         "payment_type":             "Receive",
# # # # #         "party_type":               "Customer",
# # # # #         "party":                    pe.get("party") or "default",
# # # # #         "party_name":               pe.get("party_name") or "default",
# # # # #         "paid_to_account_currency": paid_to_currency,
# # # # #         "paid_amount":              amount,
# # # # #         "received_amount":          amount,
# # # # #         "source_exchange_rate":     exch_rate,
# # # # #         "reference_no":             pe.get("reference_no") or pe.get("sale_invoice_no", ""),
# # # # #         "reference_date":           pe.get("reference_date") or date.today().isoformat(),
# # # # #         "remarks":                  pe.get("remarks") or f"POS Payment — {mop}",
# # # # #         "mode_of_payment":          mop,
# # # # #         "docstatus":                1,
# # # # #     }

# # # # #     if paid_to:
# # # # #         payload["paid_to"] = paid_to
# # # # #     if company:
# # # # #         payload["company"] = company

# # # # #     # Link to the Sales Invoice on Frappe
# # # # #     if frappe_inv:
# # # # #         payload["references"] = [{
# # # # #             "reference_doctype": "Sales Invoice",
# # # # #             "reference_name":    frappe_inv,
# # # # #             "allocated_amount":  amount,
# # # # #         }]

# # # # #     return payload


# # # # # # =============================================================================
# # # # # # PUSH ONE PAYMENT ENTRY
# # # # # # =============================================================================

# # # # # def _push_payment_entry(pe: dict, api_key: str, api_secret: str,
# # # # #                         defaults: dict, host: str) -> str | None:
# # # # #     """
# # # # #     Posts one payment entry to Frappe.
# # # # #     Returns Frappe's PAY-xxxxx name on success, None on failure.
# # # # #     """
# # # # #     pe_id  = pe["id"]
# # # # #     inv_no = pe.get("sale_invoice_no", str(pe_id))

# # # # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()
# # # # #     if not frappe_inv:
# # # # #         log.warning("Payment %d — Sales Invoice not yet on Frappe, skipping.", pe_id)
# # # # #         return None

# # # # #     payload = _build_payload(pe, defaults, api_key, api_secret, host)

# # # # #     url = f"{host}/api/resource/Payment%20Entry"
# # # # #     req = urllib.request.Request(
# # # # #         url=url,
# # # # #         data=json.dumps(payload).encode("utf-8"),
# # # # #         method="POST",
# # # # #         headers={
# # # # #             "Content-Type":  "application/json",
# # # # #             "Accept":        "application/json",
# # # # #             "Authorization": f"token {api_key}:{api_secret}",
# # # # #         },
# # # # #     )

# # # # #     try:
# # # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
# # # # #             data = json.loads(resp.read().decode())
# # # # #             name = (data.get("data") or {}).get("name", "")
# # # # #             log.info("✅ Payment Entry %d → Frappe %s  [%s  %s %.2f]",
# # # # #                      pe_id, name, inv_no,
# # # # #                      pe.get("currency", ""), float(pe.get("paid_amount", 0)))
# # # # #             return name or "SYNCED"

# # # # #     except urllib.error.HTTPError as e:
# # # # #         try:
# # # # #             err = json.loads(e.read().decode())
# # # # #             msg = (err.get("exception") or err.get("message") or
# # # # #                    str(err.get("_server_messages", "")) or f"HTTP {e.code}")
# # # # #         except Exception:
# # # # #             msg = f"HTTP {e.code}"

# # # # #         if e.code == 409:
# # # # #             log.info("Payment %d already on Frappe (409) - marking synced.", pe_id)
# # # # #             return "DUPLICATE"

# # # # #         # Invoice already paid (is_pos:1 on old invoices) - stop retrying
# # # # #         if e.code == 417:
# # # # #             _perma = ("already been fully paid", "already paid", "fully paid")
# # # # #             if any(p in msg.lower() for p in _perma):
# # # # #                 log.info("Payment %d - invoice already paid on Frappe, marking synced.", pe_id)
# # # # #                 return "ALREADY_PAID"

# # # # #         log.error("FAIL Payment Entry %d  HTTP %s: %s", pe_id, e.code, msg)
# # # # #         return None

# # # # #     except urllib.error.URLError as e:
# # # # #         log.warning("Network error pushing payment %d: %s", pe_id, e.reason)
# # # # #         return None

# # # # #     except Exception as e:
# # # # #         log.error("Unexpected error pushing payment %d: %s", pe_id, e)
# # # # #         return None


# # # # # # =============================================================================
# # # # # # PUBLIC — push all unsynced payment entries
# # # # # # =============================================================================

# # # # # def push_unsynced_payment_entries() -> dict:
# # # # #     """
# # # # #     1. Refresh frappe_invoice_ref from parent sales that were confirmed.
# # # # #     2. Push each unsynced payment entry to Frappe.
# # # # #     3. Mark synced with the returned PAY-xxxxx ref.
# # # # #     """
# # # # #     result = {"pushed": 0, "failed": 0, "skipped": 0, "total": 0}

# # # # #     api_key, api_secret = _get_credentials()
# # # # #     if not api_key or not api_secret:
# # # # #         log.warning("No credentials — skipping payment entry sync.")
# # # # #         return result

# # # # #     host     = _get_host()
# # # # #     defaults = _get_defaults()

# # # # #     # First: pull frappe_refs from confirmed invoices into pending payment entries
# # # # #     updated = refresh_frappe_refs()
# # # # #     if updated:
# # # # #         log.info("Refreshed frappe_invoice_ref on %d payment entry(ies).", updated)

# # # # #     entries = get_unsynced_payment_entries()
# # # # #     result["total"] = len(entries)

# # # # #     if not entries:
# # # # #         log.debug("No unsynced payment entries.")
# # # # #         return result

# # # # #     log.info("Pushing %d payment entry(ies) to Frappe…", len(entries))

# # # # #     for pe in entries:
# # # # #         frappe_name = _push_payment_entry(pe, api_key, api_secret, defaults, host)
# # # # #         if frappe_name:
# # # # #             mark_payment_synced(pe["id"], frappe_name)
# # # # #             result["pushed"] += 1
# # # # #         elif frappe_name is None:
# # # # #             # None = permanent skip (no frappe_inv yet), not a real failure
# # # # #             result["skipped"] += 1
# # # # #         else:
# # # # #             result["failed"] += 1

# # # # #         time.sleep(3)   # rate limit — 20/min max

# # # # #     log.info("Payment sync done — ✅ %d pushed  ❌ %d failed  ⏭ %d skipped",
# # # # #              result["pushed"], result["failed"], result["skipped"])
# # # # #     return result


# # # # # # =============================================================================
# # # # # # BACKGROUND DAEMON THREAD
# # # # # # =============================================================================

# # # # # def _sync_loop():
# # # # #     log.info("Payment entry sync daemon started (interval=%ds).", SYNC_INTERVAL)
# # # # #     while True:
# # # # #         if _sync_lock.acquire(blocking=False):
# # # # #             try:
# # # # #                 push_unsynced_payment_entries()
# # # # #             except Exception as e:
# # # # #                 log.error("Payment sync cycle error: %s", e)
# # # # #             finally:
# # # # #                 _sync_lock.release()
# # # # #         else:
# # # # #             log.debug("Previous payment sync still running — skipping.")
# # # # #         time.sleep(SYNC_INTERVAL)


# # # # # def start_payment_sync_daemon() -> threading.Thread:
# # # # #     """Non-blocking — safe to call from MainWindow.__init__."""
# # # # #     global _sync_thread
# # # # #     if _sync_thread and _sync_thread.is_alive():
# # # # #         return _sync_thread
# # # # #     t = threading.Thread(target=_sync_loop, daemon=True, name="PaymentSyncDaemon")
# # # # #     t.start()
# # # # #     _sync_thread = t
# # # # #     log.info("Payment entry sync daemon started.")
# # # # #     return t


# # # # # # =============================================================================
# # # # # # DEBUG
# # # # # # =============================================================================

# # # # # if __name__ == "__main__":
# # # # #     logging.basicConfig(level=logging.INFO,
# # # # #                         format="%(asctime)s [%(levelname)s] %(message)s")
# # # # #     print("Running one payment entry sync cycle...")
# # # # #     r = push_unsynced_payment_entries()
# # # # #     print(f"\nResult: {r['pushed']} pushed, {r['failed']} failed, "
# # # # #           f"{r['skipped']} skipped (of {r['total']} total)")

# # # # # =============================================================================
# # # # # services/payment_entry_service.py
# # # # #
# # # # # Manages local payment_entries table and syncs them to Frappe.
# # # # #
# # # # # FLOW:
# # # # #   1. When a sale is saved locally → create_payment_entry() stores it locally
# # # # #      with synced=0
# # # # #   2. When the Sales Invoice is confirmed on Frappe (frappe_ref is set) →
# # # # #      push_unsynced_payment_entries() pushes the Payment Entry to Frappe
# # # # #   3. Frappe returns a PAY-xxxxx ref → stored as frappe_payment_ref, synced=1
# # # # #
# # # # # PAYLOAD SENT TO FRAPPE:
# # # # #   POST /api/resource/Payment Entry
# # # # #   {
# # # # #     "doctype":              "Payment Entry",
# # # # #     "payment_type":         "Receive",
# # # # #     "party_type":           "Customer",
# # # # #     "party":                "Cathy",
# # # # #     "paid_to":              "Cash ZWG - H",
# # # # #     "paid_to_account_currency": "USD",
# # # # #     "paid_amount":          32.45,
# # # # #     "received_amount":      32.45,
# # # # #     "source_exchange_rate": 1.0,
# # # # #     "reference_no":         "ACC-SINV-2026-00034",
# # # # #     "reference_date":       "2026-03-19",
# # # # #     "remarks":              "POS Payment — Cash",
# # # # #     "docstatus":            1,
# # # # #     "references": [{
# # # # #         "reference_doctype": "Sales Invoice",
# # # # #         "reference_name":    "ACC-SINV-2026-00565",
# # # # #         "allocated_amount":  32.45
# # # # #     }]
# # # # #   }
# # # # # =============================================================================

# # # # from __future__ import annotations

# # # # import json
# # # # import logging
# # # # import time
# # # # import threading
# # # # import urllib.request
# # # # import urllib.error
# # # # from datetime import date

# # # # log = logging.getLogger("PaymentEntry")

# # # # SYNC_INTERVAL   = 60      # seconds between auto-sync cycles
# # # # REQUEST_TIMEOUT = 30

# # # # # Exchange rate cache: "FROM::TO::DATE" → float
# # # # _RATE_CACHE: dict[str, float] = {}


# # # # def _get_exchange_rate(from_currency: str, to_currency: str,
# # # #                        transaction_date: str,
# # # #                        api_key: str, api_secret: str, host: str) -> float:
# # # #     """
# # # #     Fetch live exchange rate from Frappe.
# # # #     Returns 1.0 for same currency, 0.0 if fetch fails (Frappe uses its own rate).
# # # #     """
# # # #     if not from_currency or from_currency.upper() == to_currency.upper():
# # # #         return 1.0

# # # #     cache_key = f"{from_currency.upper()}::{to_currency.upper()}::{transaction_date}"
# # # #     if cache_key in _RATE_CACHE:
# # # #         return _RATE_CACHE[cache_key]

# # # #     try:
# # # #         import urllib.parse
# # # #         url = (
# # # #             f"{host}/api/method/erpnext.setup.utils.get_exchange_rate"
# # # #             f"?from_currency={urllib.parse.quote(from_currency)}"
# # # #             f"&to_currency={urllib.parse.quote(to_currency)}"
# # # #             f"&transaction_date={transaction_date}"
# # # #         )
# # # #         req = urllib.request.Request(url)
# # # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # # #             data = json.loads(r.read().decode())
# # # #             rate = float(data.get("message") or data.get("result") or 0)
# # # #             if rate > 0:
# # # #                 _RATE_CACHE[cache_key] = rate
# # # #                 log.debug("Rate %s→%s on %s: %.6f", from_currency, to_currency, transaction_date, rate)
# # # #                 return rate
# # # #     except Exception as e:
# # # #         log.debug("Rate fetch failed (%s→%s): %s", from_currency, to_currency, e)

# # # #     return 0.0

# # # # _sync_lock:   threading.Lock          = threading.Lock()
# # # # _sync_thread: threading.Thread | None = None

# # # # # Method → Frappe Mode of Payment name
# # # # _METHOD_MAP = {
# # # #     "CASH":     "Cash",
# # # #     "CARD":     "Credit Card",
# # # #     "C / CARD": "Credit Card",
# # # #     "EFTPOS":   "Credit Card",
# # # #     "CHECK":    "Cheque",
# # # #     "CHEQUE":   "Cheque",
# # # #     "MOBILE":   "Mobile Money",
# # # #     "CREDIT":   "Credit",
# # # #     "TRANSFER": "Bank Transfer",
# # # # }


# # # # # =============================================================================
# # # # # CREDENTIALS / HOST / DEFAULTS
# # # # # =============================================================================

# # # # def _get_credentials() -> tuple[str, str]:
# # # #     try:
# # # #         from services.credentials import get_credentials
# # # #         return get_credentials()
# # # #     except Exception:
# # # #         pass
# # # #     return "", ""


# # # # def _get_host() -> str:
# # # #     try:
# # # #         from models.company_defaults import get_defaults
# # # #         host = (get_defaults() or {}).get("server_api_host", "").strip().rstrip("/")
# # # #         if host:
# # # #             return host
# # # #     except Exception:
# # # #         pass
# # # #     return "https://apk.havano.cloud"


# # # # def _get_defaults() -> dict:
# # # #     try:
# # # #         from models.company_defaults import get_defaults
# # # #         return get_defaults() or {}
# # # #     except Exception:
# # # #         return {}


# # # # # =============================================================================
# # # # # GL ACCOUNT RESOLVER  (which account to credit for each payment method)
# # # # # =============================================================================

# # # # _ACCOUNT_CACHE: dict[str, str] = {}


# # # # def _resolve_paid_to_account(mop_name: str, company: str, currency: str,
# # # #                               api_key: str, api_secret: str, host: str) -> str:
# # # #     """
# # # #     Looks up the GL account for a Mode of Payment from Frappe.
# # # #     Tries to match by currency if multiple accounts exist for the company.
# # # #     Falls back to server_pos_account in company_defaults.
# # # #     """
# # # #     cache_key = f"{mop_name}::{company}::{currency}"
# # # #     if cache_key in _ACCOUNT_CACHE:
# # # #         return _ACCOUNT_CACHE[cache_key]

# # # #     try:
# # # #         import urllib.parse
# # # #         url = (f"{host}/api/resource/Mode%20of%20Payment/"
# # # #                f"{urllib.parse.quote(mop_name)}?fields=[\"accounts\"]")
# # # #         req = urllib.request.Request(url)
# # # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # # #             data     = json.loads(r.read().decode())
# # # #             accounts = (data.get("data") or {}).get("accounts", [])

# # # #         company_accts = [a for a in accounts
# # # #                          if not company or a.get("company") == company]

# # # #         # Prefer account whose name contains the currency code
# # # #         matched = ""
# # # #         if currency:
# # # #             for a in company_accts:
# # # #                 if currency.upper() in (a.get("default_account") or "").upper():
# # # #                     matched = a["default_account"]; break

# # # #         if not matched and company_accts:
# # # #             matched = company_accts[0].get("default_account", "")

# # # #         if matched:
# # # #             _ACCOUNT_CACHE[cache_key] = matched
# # # #             return matched

# # # #     except Exception as e:
# # # #         log.debug("MOP account lookup failed for '%s': %s", mop_name, e)

# # # #     # Fallback
# # # #     fallback = _get_defaults().get("server_pos_account", "").strip()
# # # #     if fallback:
# # # #         _ACCOUNT_CACHE[cache_key] = fallback
# # # #         return fallback

# # # #     log.warning("No GL account for MOP '%s' currency=%s — Payment Entry may fail.",
# # # #                 mop_name, currency)
# # # #     return ""


# # # # # =============================================================================
# # # # # LOCAL DB  — create / read / update payment_entries
# # # # # =============================================================================

# # # # def create_payment_entry(sale: dict, override_rate: float = None,
# # # #                          override_account: str = None) -> int | None:
# # # #     """
# # # #     Called immediately after a sale is saved locally.
# # # #     Stores a payment_entry row with synced=0.
# # # #     Returns the new payment_entry id, or None on error.

# # # #     Will only create the entry once per sale (idempotent).
# # # #     """
# # # #     from database.db import get_connection
# # # #     conn = get_connection(); cur = conn.cursor()

# # # #     # Idempotency: don't create twice for the same sale
# # # #     cur.execute("SELECT id FROM payment_entries WHERE sale_id = ?", (sale["id"],))
# # # #     if cur.fetchone():
# # # #         conn.close()
# # # #         return None

# # # #     customer   = (sale.get("customer_name") or "default").strip()
# # # #     currency   = (sale.get("currency")      or "USD").strip().upper()
# # # #     amount     = float(sale.get("total")    or 0)
# # # #     inv_no     = sale.get("invoice_no", "")
# # # #     inv_date   = sale.get("invoice_date") or date.today().isoformat()
# # # #     method     = str(sale.get("method", "CASH")).upper().strip()
# # # #     mop        = _METHOD_MAP.get(method, "Cash")

# # # #     # Use override rate (from split) or fetch from Frappe
# # # #     if override_rate is not None:
# # # #         exch_rate = override_rate
# # # #     else:
# # # #         try:
# # # #             api_key, api_secret = _get_credentials()
# # # #             host = _get_host()
# # # #             defaults = _get_defaults()
# # # #             company_currency = defaults.get("server_company_currency", "USD").strip().upper() or "USD"
# # # #             exch_rate = _get_exchange_rate(
# # # #                 currency, company_currency, inv_date, api_key, api_secret, host
# # # #             ) if currency != company_currency else 1.0
# # # #         except Exception:
# # # #             exch_rate = 1.0

# # # #     cur.execute("""
# # # #         INSERT INTO payment_entries (
# # # #             sale_id, sale_invoice_no, frappe_invoice_ref,
# # # #             party, party_name,
# # # #             paid_amount, received_amount, source_exchange_rate,
# # # #             paid_to_account_currency, currency,
# # # #             mode_of_payment,
# # # #             reference_no, reference_date,
# # # #             remarks, synced
# # # #         ) OUTPUT INSERTED.id
# # # #         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # # #     """, (
# # # #         sale["id"], inv_no,
# # # #         sale.get("frappe_ref") or None,
# # # #         customer, customer,
# # # #         amount, amount, exch_rate or 1.0,
# # # #         currency, currency,
# # # #         mop,
# # # #         inv_no, inv_date,
# # # #         f"POS Payment — {mop}",
# # # #     ))
# # # #     new_id = int(cur.fetchone()[0])
# # # #     conn.commit(); conn.close()
# # # #     log.debug("Payment entry %d created locally for sale %s", new_id, inv_no)
# # # #     return new_id


# # # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # # #     """
# # # #     Called when cashier uses Split payment.
# # # #     Creates one payment_entry row per currency in splits list.
# # # #     splits = [{"mode": "CASH", "currency": "USD", "amount": 5.0,
# # # #                "rate": 1.0, "base_amount": 5.0, "account": "Cash - AT"}, ...]
# # # #     Returns list of new payment_entry ids.
# # # #     """
# # # #     ids = []
# # # #     for split in splits:
# # # #         if not split.get("amount") or float(split["amount"]) <= 0:
# # # #             continue
# # # #         # Build a sale-like dict with the split's currency and amount
# # # #         split_sale = dict(sale)
# # # #         split_sale["currency"]      = split.get("currency", "USD")
# # # #         split_sale["total"]         = float(split.get("amount", 0))
# # # #         split_sale["method"]        = split.get("mode", "CASH")
# # # #         # Override exchange rate from split data
# # # #         new_id = create_payment_entry(
# # # #             split_sale,
# # # #             override_rate=float(split.get("rate", 1.0)),
# # # #             override_account=split.get("account", ""),
# # # #         )
# # # #         if new_id:
# # # #             ids.append(new_id)
# # # #     return ids


# # # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # # #     """
# # # #     Creates one payment_entry per currency from a split payment.
# # # #     Groups splits by currency, sums amounts, creates one entry each.
# # # #     Returns list of created payment_entry ids.
# # # #     """
# # # #     from datetime import date as _date

# # # #     # Group by currency
# # # #     by_currency: dict[str, dict] = {}
# # # #     for s in splits:
# # # #         curr = s.get("account_currency", "USD").upper()
# # # #         if curr not in by_currency:
# # # #             by_currency[curr] = {
# # # #                 "currency":      curr,
# # # #                 "paid_amount":   0.0,
# # # #                 "base_value":    0.0,
# # # #                 "rate":          s.get("rate", 1.0),
# # # #                 "account_name":  s.get("account_name", ""),
# # # #                 "mode":          s.get("mode", "Cash"),
# # # #             }
# # # #         by_currency[curr]["paid_amount"] += s.get("amount_paid", 0.0)
# # # #         by_currency[curr]["base_value"]  += s.get("base_value",  0.0)

# # # #     ids = []
# # # #     inv_no   = sale.get("invoice_no", "")
# # # #     inv_date = sale.get("invoice_date") or _date.today().isoformat()
# # # #     customer = (sale.get("customer_name") or "default").strip()

# # # #     from database.db import get_connection
# # # #     conn = get_connection(); cur = conn.cursor()

# # # #     for curr, grp in by_currency.items():
# # # #         # Idempotency: skip if already exists for this sale+currency
# # # #         cur.execute(
# # # #             "SELECT id FROM payment_entries WHERE sale_id=? AND currency=?",
# # # #             (sale["id"], curr)
# # # #         )
# # # #         if cur.fetchone():
# # # #             continue

# # # #         mop = _METHOD_MAP.get(grp["mode"].upper(), "Cash")

# # # #         cur.execute("""
# # # #             INSERT INTO payment_entries (
# # # #                 sale_id, sale_invoice_no, frappe_invoice_ref,
# # # #                 party, party_name,
# # # #                 paid_amount, received_amount, source_exchange_rate,
# # # #                 paid_to_account_currency, currency,
# # # #                 paid_to,
# # # #                 mode_of_payment,
# # # #                 reference_no, reference_date,
# # # #                 remarks, synced
# # # #             ) OUTPUT INSERTED.id
# # # #             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # # #         """, (
# # # #             sale["id"], inv_no,
# # # #             sale.get("frappe_ref") or None,
# # # #             customer, customer,
# # # #             grp["paid_amount"],
# # # #             grp["base_value"],
# # # #             float(grp["rate"] or 1.0),
# # # #             curr, curr,
# # # #             grp["account_name"],
# # # #             mop,
# # # #             inv_no, inv_date,
# # # #             f"POS Split Payment — {mop} ({curr})",
# # # #         ))
# # # #         new_id = int(cur.fetchone()[0])
# # # #         ids.append(new_id)
# # # #         log.debug("Split payment entry %d created: %s %.2f %s",
# # # #                   new_id, curr, grp["paid_amount"], inv_no)

# # # #     conn.commit(); conn.close()
# # # #     return ids


# # # # def get_unsynced_payment_entries() -> list[dict]:
# # # #     """Returns payment entries that are ready to push (synced=0)."""
# # # #     from database.db import get_connection, fetchall_dicts
# # # #     conn = get_connection(); cur = conn.cursor()
# # # #     cur.execute("""
# # # #         SELECT pe.*, s.frappe_ref AS sale_frappe_ref
# # # #         FROM payment_entries pe
# # # #         LEFT JOIN sales s ON s.id = pe.sale_id
# # # #         WHERE pe.synced = 0
# # # #           AND (pe.frappe_invoice_ref IS NOT NULL
# # # #                OR s.frappe_ref IS NOT NULL)
# # # #         ORDER BY pe.id
# # # #     """)
# # # #     rows = fetchall_dicts(cur); conn.close()
# # # #     return rows


# # # # def mark_payment_synced(pe_id: int, frappe_payment_ref: str = "") -> None:
# # # #     from database.db import get_connection
# # # #     conn = get_connection(); cur = conn.cursor()
# # # #     cur.execute(
# # # #         "UPDATE payment_entries SET synced=1, frappe_payment_ref=? WHERE id=?",
# # # #         (frappe_payment_ref or None, pe_id)
# # # #     )
# # # #     # Also update the sales row
# # # #     cur.execute("""
# # # #         UPDATE sales SET payment_entry_ref=?, payment_synced=1
# # # #         WHERE id = (SELECT sale_id FROM payment_entries WHERE id=?)
# # # #     """, (frappe_payment_ref or None, pe_id))
# # # #     conn.commit(); conn.close()


# # # # def refresh_frappe_refs() -> int:
# # # #     """
# # # #     For payment entries that have no frappe_invoice_ref yet, copy it from
# # # #     the parent sale's frappe_ref. Call this before pushing payments.
# # # #     Returns count updated.
# # # #     """
# # # #     from database.db import get_connection
# # # #     conn = get_connection(); cur = conn.cursor()
# # # #     cur.execute("""
# # # #         UPDATE pe
# # # #         SET pe.frappe_invoice_ref = s.frappe_ref
# # # #         FROM payment_entries pe
# # # #         JOIN sales s ON s.id = pe.sale_id
# # # #         WHERE pe.synced = 0
# # # #           AND (pe.frappe_invoice_ref IS NULL OR pe.frappe_invoice_ref = '')
# # # #           AND s.frappe_ref IS NOT NULL AND s.frappe_ref != ''
# # # #     """)
# # # #     count = cur.rowcount
# # # #     conn.commit(); conn.close()
# # # #     return count


# # # # # =============================================================================
# # # # # BUILD FRAPPE PAYLOAD
# # # # # =============================================================================

# # # # def _build_payload(pe: dict, defaults: dict,
# # # #                    api_key: str, api_secret: str, host: str) -> dict:
# # # #     company  = defaults.get("server_company", "")
# # # #     currency = (pe.get("currency") or pe.get("paid_to_account_currency") or "USD").upper()
# # # #     mop      = pe.get("mode_of_payment") or "Cash"
# # # #     amount   = float(pe.get("paid_amount") or 0)
# # # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()

# # # #     # Use local gl_accounts table first (synced from Frappe)
# # # #     paid_to          = (pe.get("paid_to") or "").strip()
# # # #     paid_to_currency = currency
# # # #     if not paid_to:
# # # #         try:
# # # #             from models.gl_account import get_account_for_payment
# # # #             acct = get_account_for_payment(currency, company)
# # # #             if acct:
# # # #                 paid_to          = acct["name"]
# # # #                 paid_to_currency = acct["account_currency"]
# # # #         except Exception as _e:
# # # #             log.debug("gl_account lookup failed: %s", _e)

# # # #     # Fallback to live Frappe lookup
# # # #     if not paid_to:
# # # #         paid_to = _resolve_paid_to_account(mop, company, currency, api_key, api_secret, host)

# # # #     # Use local exchange rate if not stored
# # # #     exch_rate = float(pe.get("source_exchange_rate") or 1.0)
# # # #     if exch_rate == 1.0 and currency not in ("USD", ""):
# # # #         try:
# # # #             from models.exchange_rate import get_rate
# # # #             stored = get_rate(currency, "USD")
# # # #             if stored:
# # # #                 exch_rate = stored
# # # #         except Exception:
# # # #             pass

# # # #     payload = {
# # # #         "doctype":                  "Payment Entry",
# # # #         "payment_type":             "Receive",
# # # #         "party_type":               "Customer",
# # # #         "party":                    pe.get("party") or "default",
# # # #         "party_name":               pe.get("party_name") or "default",
# # # #         "paid_to_account_currency": paid_to_currency,
# # # #         "paid_amount":              amount,
# # # #         "received_amount":          amount,
# # # #         "source_exchange_rate":     exch_rate,
# # # #         "reference_no":             pe.get("reference_no") or pe.get("sale_invoice_no", ""),
# # # #         "reference_date":           pe.get("reference_date") or date.today().isoformat(),
# # # #         "remarks":                  pe.get("remarks") or f"POS Payment — {mop}",
# # # #         "mode_of_payment":          mop,
# # # #         "docstatus":                1,
# # # #     }

# # # #     if paid_to:
# # # #         payload["paid_to"] = paid_to
# # # #     if company:
# # # #         payload["company"] = company

# # # #     # Link to the Sales Invoice on Frappe
# # # #     if frappe_inv:
# # # #         payload["references"] = [{
# # # #             "reference_doctype": "Sales Invoice",
# # # #             "reference_name":    frappe_inv,
# # # #             "allocated_amount":  amount,
# # # #         }]

# # # #     return payload


# # # # # =============================================================================
# # # # # PUSH ONE PAYMENT ENTRY
# # # # # =============================================================================

# # # # def _push_payment_entry(pe: dict, api_key: str, api_secret: str,
# # # #                         defaults: dict, host: str) -> str | None:
# # # #     """
# # # #     Posts one payment entry to Frappe.
# # # #     Returns Frappe's PAY-xxxxx name on success, None on failure.
# # # #     """
# # # #     pe_id  = pe["id"]
# # # #     inv_no = pe.get("sale_invoice_no", str(pe_id))

# # # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()
# # # #     if not frappe_inv:
# # # #         log.warning("Payment %d — Sales Invoice not yet on Frappe, skipping.", pe_id)
# # # #         return None

# # # #     payload = _build_payload(pe, defaults, api_key, api_secret, host)

# # # #     url = f"{host}/api/resource/Payment%20Entry"
# # # #     req = urllib.request.Request(
# # # #         url=url,
# # # #         data=json.dumps(payload).encode("utf-8"),
# # # #         method="POST",
# # # #         headers={
# # # #             "Content-Type":  "application/json",
# # # #             "Accept":        "application/json",
# # # #             "Authorization": f"token {api_key}:{api_secret}",
# # # #         },
# # # #     )

# # # #     try:
# # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
# # # #             data = json.loads(resp.read().decode())
# # # #             name = (data.get("data") or {}).get("name", "")
# # # #             log.info("✅ Payment Entry %d → Frappe %s  [%s  %s %.2f]",
# # # #                      pe_id, name, inv_no,
# # # #                      pe.get("currency", ""), float(pe.get("paid_amount", 0)))
# # # #             return name or "SYNCED"

# # # #     except urllib.error.HTTPError as e:
# # # #         try:
# # # #             err = json.loads(e.read().decode())
# # # #             msg = (err.get("exception") or err.get("message") or
# # # #                    str(err.get("_server_messages", "")) or f"HTTP {e.code}")
# # # #         except Exception:
# # # #             msg = f"HTTP {e.code}"

# # # #         if e.code == 409:
# # # #             log.info("Payment %d already on Frappe (409) - marking synced.", pe_id)
# # # #             return "DUPLICATE"

# # # #         # Invoice already paid (is_pos:1 on old invoices) - stop retrying
# # # #         if e.code == 417:
# # # #             _perma = ("already been fully paid", "already paid", "fully paid")
# # # #             if any(p in msg.lower() for p in _perma):
# # # #                 log.info("Payment %d - invoice already paid on Frappe, marking synced.", pe_id)
# # # #                 return "ALREADY_PAID"

# # # #         log.error("FAIL Payment Entry %d  HTTP %s: %s", pe_id, e.code, msg)
# # # #         return None

# # # #     except urllib.error.URLError as e:
# # # #         log.warning("Network error pushing payment %d: %s", pe_id, e.reason)
# # # #         return None

# # # #     except Exception as e:
# # # #         log.error("Unexpected error pushing payment %d: %s", pe_id, e)
# # # #         return None


# # # # # =============================================================================
# # # # # PUBLIC — push all unsynced payment entries
# # # # # =============================================================================

# # # # def push_unsynced_payment_entries() -> dict:
# # # #     """
# # # #     1. Refresh frappe_invoice_ref from parent sales that were confirmed.
# # # #     2. Push each unsynced payment entry to Frappe.
# # # #     3. Mark synced with the returned PAY-xxxxx ref.
# # # #     """
# # # #     result = {"pushed": 0, "failed": 0, "skipped": 0, "total": 0}

# # # #     api_key, api_secret = _get_credentials()
# # # #     if not api_key or not api_secret:
# # # #         log.warning("No credentials — skipping payment entry sync.")
# # # #         return result

# # # #     host     = _get_host()
# # # #     defaults = _get_defaults()

# # # #     # First: pull frappe_refs from confirmed invoices into pending payment entries
# # # #     updated = refresh_frappe_refs()
# # # #     if updated:
# # # #         log.info("Refreshed frappe_invoice_ref on %d payment entry(ies).", updated)

# # # #     entries = get_unsynced_payment_entries()
# # # #     result["total"] = len(entries)

# # # #     if not entries:
# # # #         log.debug("No unsynced payment entries.")
# # # #         return result

# # # #     log.info("Pushing %d payment entry(ies) to Frappe…", len(entries))

# # # #     for pe in entries:
# # # #         frappe_name = _push_payment_entry(pe, api_key, api_secret, defaults, host)
# # # #         if frappe_name:
# # # #             mark_payment_synced(pe["id"], frappe_name)
# # # #             result["pushed"] += 1
# # # #         elif frappe_name is None:
# # # #             # None = permanent skip (no frappe_inv yet), not a real failure
# # # #             result["skipped"] += 1
# # # #         else:
# # # #             result["failed"] += 1

# # # #         time.sleep(3)   # rate limit — 20/min max

# # # #     log.info("Payment sync done — ✅ %d pushed  ❌ %d failed  ⏭ %d skipped",
# # # #              result["pushed"], result["failed"], result["skipped"])
# # # #     return result


# # # # # =============================================================================
# # # # # BACKGROUND DAEMON THREAD
# # # # # =============================================================================

# # # # def _sync_loop():
# # # #     log.info("Payment entry sync daemon started (interval=%ds).", SYNC_INTERVAL)
# # # #     while True:
# # # #         if _sync_lock.acquire(blocking=False):
# # # #             try:
# # # #                 push_unsynced_payment_entries()
# # # #             except Exception as e:
# # # #                 log.error("Payment sync cycle error: %s", e)
# # # #             finally:
# # # #                 _sync_lock.release()
# # # #         else:
# # # #             log.debug("Previous payment sync still running — skipping.")
# # # #         time.sleep(SYNC_INTERVAL)


# # # # def start_payment_sync_daemon() -> threading.Thread:
# # # #     """Non-blocking — safe to call from MainWindow.__init__."""
# # # #     global _sync_thread
# # # #     if _sync_thread and _sync_thread.is_alive():
# # # #         return _sync_thread
# # # #     t = threading.Thread(target=_sync_loop, daemon=True, name="PaymentSyncDaemon")
# # # #     t.start()
# # # #     _sync_thread = t
# # # #     log.info("Payment entry sync daemon started.")
# # # #     return t


# # # # # =============================================================================
# # # # # DEBUG
# # # # # =============================================================================

# # # # if __name__ == "__main__":
# # # #     logging.basicConfig(level=logging.INFO,
# # # #                         format="%(asctime)s [%(levelname)s] %(message)s")
# # # #     print("Running one payment entry sync cycle...")
# # # #     r = push_unsynced_payment_entries()
# # # #     print(f"\nResult: {r['pushed']} pushed, {r['failed']} failed, "
# # # #           f"{r['skipped']} skipped (of {r['total']} total)")

# # # # =============================================================================
# # # # services/payment_entry_service.py
# # # #
# # # # Manages local payment_entries table and syncs them to Frappe.
# # # #
# # # # FLOW:
# # # #   1. When a sale is saved locally → create_payment_entry() stores it locally
# # # #      with synced=0
# # # #   2. When the Sales Invoice is confirmed on Frappe (frappe_ref is set) →
# # # #      push_unsynced_payment_entries() pushes the Payment Entry to Frappe
# # # #   3. Frappe returns a PAY-xxxxx ref → stored as frappe_payment_ref, synced=1
# # # #
# # # # PAYLOAD SENT TO FRAPPE:
# # # #   POST /api/resource/Payment Entry
# # # #   {
# # # #     "doctype":              "Payment Entry",
# # # #     "payment_type":         "Receive",
# # # #     "party_type":           "Customer",
# # # #     "party":                "Cathy",
# # # #     "paid_to":              "Cash ZWG - H",
# # # #     "paid_to_account_currency": "USD",
# # # #     "paid_amount":          32.45,
# # # #     "received_amount":      32.45,
# # # #     "source_exchange_rate": 1.0,
# # # #     "reference_no":         "ACC-SINV-2026-00034",
# # # #     "reference_date":       "2026-03-19",
# # # #     "remarks":              "POS Payment — Cash",
# # # #     "docstatus":            1,
# # # #     "references": [{
# # # #         "reference_doctype": "Sales Invoice",
# # # #         "reference_name":    "ACC-SINV-2026-00565",
# # # #         "allocated_amount":  32.45
# # # #     }]
# # # #   }
# # # # =============================================================================

# # # from __future__ import annotations

# # # import json
# # # import logging
# # # import time
# # # import threading
# # # import urllib.request
# # # import urllib.error
# # # from datetime import date

# # # log = logging.getLogger("PaymentEntry")

# # # SYNC_INTERVAL   = 60      # seconds between auto-sync cycles
# # # REQUEST_TIMEOUT = 30

# # # # Exchange rate cache: "FROM::TO::DATE" → float
# # # _RATE_CACHE: dict[str, float] = {}


# # # def _get_exchange_rate(from_currency: str, to_currency: str,
# # #                        transaction_date: str,
# # #                        api_key: str, api_secret: str, host: str) -> float:
# # #     """
# # #     Fetch live exchange rate from Frappe.
# # #     Returns 1.0 for same currency, 0.0 if fetch fails (Frappe uses its own rate).
# # #     """
# # #     if not from_currency or from_currency.upper() == to_currency.upper():
# # #         return 1.0

# # #     cache_key = f"{from_currency.upper()}::{to_currency.upper()}::{transaction_date}"
# # #     if cache_key in _RATE_CACHE:
# # #         return _RATE_CACHE[cache_key]

# # #     try:
# # #         import urllib.parse
# # #         url = (
# # #             f"{host}/api/method/erpnext.setup.utils.get_exchange_rate"
# # #             f"?from_currency={urllib.parse.quote(from_currency)}"
# # #             f"&to_currency={urllib.parse.quote(to_currency)}"
# # #             f"&transaction_date={transaction_date}"
# # #         )
# # #         req = urllib.request.Request(url)
# # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # #             data = json.loads(r.read().decode())
# # #             rate = float(data.get("message") or data.get("result") or 0)
# # #             if rate > 0:
# # #                 _RATE_CACHE[cache_key] = rate
# # #                 log.debug("Rate %s→%s on %s: %.6f", from_currency, to_currency, transaction_date, rate)
# # #                 return rate
# # #     except Exception as e:
# # #         log.debug("Rate fetch failed (%s→%s): %s", from_currency, to_currency, e)

# # #     return 0.0

# # # _sync_lock:   threading.Lock          = threading.Lock()
# # # _sync_thread: threading.Thread | None = None

# # # # Method → Frappe Mode of Payment name
# # # _METHOD_MAP = {
# # #     "CASH":     "Cash",
# # #     "CARD":     "Credit Card",
# # #     "C / CARD": "Credit Card",
# # #     "EFTPOS":   "Credit Card",
# # #     "CHECK":    "Cheque",
# # #     "CHEQUE":   "Cheque",
# # #     "MOBILE":   "Mobile Money",
# # #     "CREDIT":   "Credit",
# # #     "TRANSFER": "Bank Transfer",
# # # }


# # # # =============================================================================
# # # # CREDENTIALS / HOST / DEFAULTS
# # # # =============================================================================

# # # def _get_credentials() -> tuple[str, str]:
# # #     try:
# # #         from services.credentials import get_credentials
# # #         return get_credentials()
# # #     except Exception:
# # #         pass
# # #     return "", ""

# # # def _get_host() -> str:
# # #     try:
# # #         from models.company_defaults import get_defaults
# # #         host = (get_defaults() or {}).get("server_api_host", "").strip().rstrip("/")
# # #         if host:
# # #             return host
# # #     except Exception:
# # #         pass
# # #     return "https://apk.havano.cloud"


# # # def _get_defaults() -> dict:
# # #     try:
# # #         from models.company_defaults import get_defaults
# # #         return get_defaults() or {}
# # #     except Exception:
# # #         return {}


# # # # =============================================================================
# # # # GL ACCOUNT RESOLVER  (which account to credit for each payment method)
# # # # =============================================================================

# # # _ACCOUNT_CACHE: dict[str, str] = {}


# # # def _resolve_paid_to_account(mop_name: str, company: str, currency: str,
# # #                               api_key: str, api_secret: str, host: str) -> str:
# # #     """
# # #     Looks up the GL account for a Mode of Payment from Frappe.
# # #     Tries to match by currency if multiple accounts exist for the company.
# # #     Falls back to server_pos_account in company_defaults.
# # #     """
# # #     cache_key = f"{mop_name}::{company}::{currency}"
# # #     if cache_key in _ACCOUNT_CACHE:
# # #         return _ACCOUNT_CACHE[cache_key]

# # #     try:
# # #         import urllib.parse
# # #         url = (f"{host}/api/resource/Mode%20of%20Payment/"
# # #                f"{urllib.parse.quote(mop_name)}?fields=[\"accounts\"]")
# # #         req = urllib.request.Request(url)
# # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # #             data     = json.loads(r.read().decode())
# # #             accounts = (data.get("data") or {}).get("accounts", [])

# # #         company_accts = [a for a in accounts
# # #                          if not company or a.get("company") == company]

# # #         # Prefer account whose name contains the currency code
# # #         matched = ""
# # #         if currency:
# # #             for a in company_accts:
# # #                 if currency.upper() in (a.get("default_account") or "").upper():
# # #                     matched = a["default_account"]; break

# # #         if not matched and company_accts:
# # #             matched = company_accts[0].get("default_account", "")

# # #         if matched:
# # #             _ACCOUNT_CACHE[cache_key] = matched
# # #             return matched

# # #     except Exception as e:
# # #         log.debug("MOP account lookup failed for '%s': %s", mop_name, e)

# # #     # Fallback
# # #     fallback = _get_defaults().get("server_pos_account", "").strip()
# # #     if fallback:
# # #         _ACCOUNT_CACHE[cache_key] = fallback
# # #         return fallback

# # #     log.warning("No GL account for MOP '%s' currency=%s — Payment Entry may fail.",
# # #                 mop_name, currency)
# # #     return ""


# # # # =============================================================================
# # # # LOCAL DB  — create / read / update payment_entries
# # # # =============================================================================

# # # def create_payment_entry(sale: dict, override_rate: float = None,
# # #                          override_account: str = None) -> int | None:
# # #     """
# # #     Called immediately after a sale is saved locally.
# # #     Stores a payment_entry row with synced=0.
# # #     Returns the new payment_entry id, or None on error.

# # #     Will only create the entry once per sale (idempotent).
# # #     """
# # #     from database.db import get_connection
# # #     conn = get_connection(); cur = conn.cursor()

# # #     # Idempotency: don't create twice for the same sale
# # #     cur.execute("SELECT id FROM payment_entries WHERE sale_id = ?", (sale["id"],))
# # #     if cur.fetchone():
# # #         conn.close()
# # #         return None

# # #     customer   = (sale.get("customer_name") or "default").strip()
# # #     currency   = (sale.get("currency")      or "USD").strip().upper()
# # #     amount     = float(sale.get("total")    or 0)
# # #     inv_no     = sale.get("invoice_no", "")
# # #     inv_date   = sale.get("invoice_date") or date.today().isoformat()
# # #     method     = str(sale.get("method", "CASH")).upper().strip()
# # #     mop        = _METHOD_MAP.get(method, "Cash")

# # #     # Use override rate (from split) or fetch from Frappe
# # #     if override_rate is not None:
# # #         exch_rate = override_rate
# # #     else:
# # #         try:
# # #             api_key, api_secret = _get_credentials()
# # #             host = _get_host()
# # #             defaults = _get_defaults()
# # #             company_currency = defaults.get("server_company_currency", "USD").strip().upper() or "USD"
# # #             exch_rate = _get_exchange_rate(
# # #                 currency, company_currency, inv_date, api_key, api_secret, host
# # #             ) if currency != company_currency else 1.0
# # #         except Exception:
# # #             exch_rate = 1.0

# # #     cur.execute("""
# # #         INSERT INTO payment_entries (
# # #             sale_id, sale_invoice_no, frappe_invoice_ref,
# # #             party, party_name,
# # #             paid_amount, received_amount, source_exchange_rate,
# # #             paid_to_account_currency, currency,
# # #             mode_of_payment,
# # #             reference_no, reference_date,
# # #             remarks, synced
# # #         ) OUTPUT INSERTED.id
# # #         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # #     """, (
# # #         sale["id"], inv_no,
# # #         sale.get("frappe_ref") or None,
# # #         customer, customer,
# # #         amount, amount, exch_rate or 1.0,
# # #         currency, currency,
# # #         mop,
# # #         inv_no, inv_date,
# # #         f"POS Payment — {mop}",
# # #     ))
# # #     new_id = int(cur.fetchone()[0])
# # #     conn.commit(); conn.close()
# # #     log.debug("Payment entry %d created locally for sale %s", new_id, inv_no)
# # #     return new_id


# # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # #     """
# # #     Called when cashier uses Split payment.
# # #     Creates one payment_entry row per currency in splits list.
# # #     splits = [{"mode": "CASH", "currency": "USD", "amount": 5.0,
# # #                "rate": 1.0, "base_amount": 5.0, "account": "Cash - AT"}, ...]
# # #     Returns list of new payment_entry ids.
# # #     """
# # #     ids = []
# # #     for split in splits:
# # #         if not split.get("amount") or float(split["amount"]) <= 0:
# # #             continue
# # #         # Build a sale-like dict with the split's currency and amount
# # #         split_sale = dict(sale)
# # #         split_sale["currency"]      = split.get("currency", "USD")
# # #         split_sale["total"]         = float(split.get("amount", 0))
# # #         split_sale["method"]        = split.get("mode", "CASH")
# # #         # Override exchange rate from split data
# # #         new_id = create_payment_entry(
# # #             split_sale,
# # #             override_rate=float(split.get("rate", 1.0)),
# # #             override_account=split.get("account", ""),
# # #         )
# # #         if new_id:
# # #             ids.append(new_id)
# # #     return ids


# # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # #     """
# # #     Creates one payment_entry per currency from a split payment.
# # #     Groups splits by currency, sums amounts, creates one entry each.
# # #     Returns list of created payment_entry ids.
# # #     """
# # #     from datetime import date as _date

# # #     # Group by currency
# # #     by_currency: dict[str, dict] = {}
# # #     for s in splits:
# # #         curr = s.get("account_currency", "USD").upper()
# # #         if curr not in by_currency:
# # #             by_currency[curr] = {
# # #                 "currency":      curr,
# # #                 "paid_amount":   0.0,
# # #                 "base_value":    0.0,
# # #                 "rate":          s.get("rate", 1.0),
# # #                 "account_name":  s.get("account_name", ""),
# # #                 "mode":          s.get("mode", "Cash"),
# # #             }
# # #         by_currency[curr]["paid_amount"] += s.get("amount_paid", 0.0)
# # #         by_currency[curr]["base_value"]  += s.get("base_value",  0.0)

# # #     ids = []
# # #     inv_no   = sale.get("invoice_no", "")
# # #     inv_date = sale.get("invoice_date") or _date.today().isoformat()
# # #     customer = (sale.get("customer_name") or "default").strip()

# # #     from database.db import get_connection
# # #     conn = get_connection(); cur = conn.cursor()

# # #     for curr, grp in by_currency.items():
# # #         # Idempotency: skip if already exists for this sale+currency
# # #         cur.execute(
# # #             "SELECT id FROM payment_entries WHERE sale_id=? AND currency=?",
# # #             (sale["id"], curr)
# # #         )
# # #         if cur.fetchone():
# # #             continue

# # #         mop = _METHOD_MAP.get(grp["mode"].upper(), "Cash")

# # #         cur.execute("""
# # #             INSERT INTO payment_entries (
# # #                 sale_id, sale_invoice_no, frappe_invoice_ref,
# # #                 party, party_name,
# # #                 paid_amount, received_amount, source_exchange_rate,
# # #                 paid_to_account_currency, currency,
# # #                 paid_to,
# # #                 mode_of_payment,
# # #                 reference_no, reference_date,
# # #                 remarks, synced
# # #             ) OUTPUT INSERTED.id
# # #             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # #         """, (
# # #             sale["id"], inv_no,
# # #             sale.get("frappe_ref") or None,
# # #             customer, customer,
# # #             grp["paid_amount"],
# # #             grp["base_value"],
# # #             float(grp["rate"] or 1.0),
# # #             curr, curr,
# # #             grp["account_name"],
# # #             mop,
# # #             inv_no, inv_date,
# # #             f"POS Split Payment — {mop} ({curr})",
# # #         ))
# # #         new_id = int(cur.fetchone()[0])
# # #         ids.append(new_id)
# # #         log.debug("Split payment entry %d created: %s %.2f %s",
# # #                   new_id, curr, grp["paid_amount"], inv_no)

# # #     conn.commit(); conn.close()
# # #     return ids


# # # def get_unsynced_payment_entries() -> list[dict]:
# # #     """Returns payment entries that are ready to push (synced=0)."""
# # #     from database.db import get_connection, fetchall_dicts
# # #     conn = get_connection(); cur = conn.cursor()
# # #     cur.execute("""
# # #         SELECT pe.*, s.frappe_ref AS sale_frappe_ref
# # #         FROM payment_entries pe
# # #         LEFT JOIN sales s ON s.id = pe.sale_id
# # #         WHERE pe.synced = 0
# # #           AND (pe.frappe_invoice_ref IS NOT NULL
# # #                OR s.frappe_ref IS NOT NULL)
# # #         ORDER BY pe.id
# # #     """)
# # #     rows = fetchall_dicts(cur); conn.close()
# # #     return rows


# # # def mark_payment_synced(pe_id: int, frappe_payment_ref: str = "") -> None:
# # #     from database.db import get_connection
# # #     conn = get_connection(); cur = conn.cursor()
# # #     cur.execute(
# # #         "UPDATE payment_entries SET synced=1, frappe_payment_ref=? WHERE id=?",
# # #         (frappe_payment_ref or None, pe_id)
# # #     )
# # #     # Also update the sales row
# # #     cur.execute("""
# # #         UPDATE sales SET payment_entry_ref=?, payment_synced=1
# # #         WHERE id = (SELECT sale_id FROM payment_entries WHERE id=?)
# # #     """, (frappe_payment_ref or None, pe_id))
# # #     conn.commit(); conn.close()


# # # def refresh_frappe_refs() -> int:
# # #     """
# # #     For payment entries that have no frappe_invoice_ref yet, copy it from
# # #     the parent sale's frappe_ref. Call this before pushing payments.
# # #     Returns count updated.
# # #     """
# # #     from database.db import get_connection
# # #     conn = get_connection(); cur = conn.cursor()
# # #     cur.execute("""
# # #         UPDATE pe
# # #         SET pe.frappe_invoice_ref = s.frappe_ref
# # #         FROM payment_entries pe
# # #         JOIN sales s ON s.id = pe.sale_id
# # #         WHERE pe.synced = 0
# # #           AND (pe.frappe_invoice_ref IS NULL OR pe.frappe_invoice_ref = '')
# # #           AND s.frappe_ref IS NOT NULL AND s.frappe_ref != ''
# # #     """)
# # #     count = cur.rowcount
# # #     conn.commit(); conn.close()
# # #     return count


# # # # =============================================================================
# # # # BUILD FRAPPE PAYLOAD
# # # # =============================================================================

# # # def _build_payload(pe: dict, defaults: dict,
# # #                    api_key: str, api_secret: str, host: str) -> dict:
# # #     company  = defaults.get("server_company", "")
# # #     currency = (pe.get("currency") or pe.get("paid_to_account_currency") or "USD").upper()
# # #     mop      = pe.get("mode_of_payment") or "Cash"
# # #     amount   = float(pe.get("paid_amount") or 0)
# # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()

# # #     # Use local gl_accounts table first (synced from Frappe)
# # #     paid_to          = (pe.get("paid_to") or "").strip()
# # #     paid_to_currency = currency
# # #     if not paid_to:
# # #         try:
# # #             from models.gl_account import get_account_for_payment
# # #             acct = get_account_for_payment(currency, company)
# # #             if acct:
# # #                 paid_to          = acct["name"]
# # #                 paid_to_currency = acct["account_currency"]
# # #         except Exception as _e:
# # #             log.debug("gl_account lookup failed: %s", _e)

# # #     # Fallback to live Frappe lookup
# # #     if not paid_to:
# # #         paid_to = _resolve_paid_to_account(mop, company, currency, api_key, api_secret, host)

# # #     # Use local exchange rate if not stored
# # #     exch_rate = float(pe.get("source_exchange_rate") or 1.0)
# # #     if exch_rate == 1.0 and currency not in ("USD", ""):
# # #         try:
# # #             from models.exchange_rate import get_rate
# # #             stored = get_rate(currency, "USD")
# # #             if stored:
# # #                 exch_rate = stored
# # #         except Exception:
# # #             pass

# # #     payload = {
# # #         "doctype":                  "Payment Entry",
# # #         "payment_type":             "Receive",
# # #         "party_type":               "Customer",
# # #         "party":                    pe.get("party") or "default",
# # #         "party_name":               pe.get("party_name") or "default",
# # #         "paid_to_account_currency": paid_to_currency,
# # #         "paid_amount":              amount,
# # #         "received_amount":          amount,
# # #         "source_exchange_rate":     exch_rate,
# # #         "reference_no":             pe.get("reference_no") or pe.get("sale_invoice_no", ""),
# # #         "reference_date":           pe.get("reference_date") or date.today().isoformat(),
# # #         "remarks":                  pe.get("remarks") or f"POS Payment — {mop}",
# # #         "mode_of_payment":          mop,
# # #         "docstatus":                1,
# # #     }

# # #     if paid_to:
# # #         payload["paid_to"] = paid_to
# # #     if company:
# # #         payload["company"] = company

# # #     # Link to the Sales Invoice on Frappe
# # #     if frappe_inv:
# # #         payload["references"] = [{
# # #             "reference_doctype": "Sales Invoice",
# # #             "reference_name":    frappe_inv,
# # #             "allocated_amount":  amount,
# # #         }]

# # #     return payload


# # # # =============================================================================
# # # # PUSH ONE PAYMENT ENTRY
# # # # =============================================================================

# # # def _push_payment_entry(pe: dict, api_key: str, api_secret: str,
# # #                         defaults: dict, host: str) -> str | None:
# # #     """
# # #     Posts one payment entry to Frappe.
# # #     Returns Frappe's PAY-xxxxx name on success, None on failure.
# # #     """
# # #     pe_id  = pe["id"]
# # #     inv_no = pe.get("sale_invoice_no", str(pe_id))

# # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()
# # #     if not frappe_inv:
# # #         log.warning("Payment %d — Sales Invoice not yet on Frappe, skipping.", pe_id)
# # #         return None

# # #     payload = _build_payload(pe, defaults, api_key, api_secret, host)

# # #     url = f"{host}/api/resource/Payment%20Entry"
# # #     req = urllib.request.Request(
# # #         url=url,
# # #         data=json.dumps(payload).encode("utf-8"),
# # #         method="POST",
# # #         headers={
# # #             "Content-Type":  "application/json",
# # #             "Accept":        "application/json",
# # #             "Authorization": f"token {api_key}:{api_secret}",
# # #         },
# # #     )

# # #     try:
# # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
# # #             data = json.loads(resp.read().decode())
# # #             name = (data.get("data") or {}).get("name", "")
# # #             log.info("✅ Payment Entry %d → Frappe %s  [%s  %s %.2f]",
# # #                      pe_id, name, inv_no,
# # #                      pe.get("currency", ""), float(pe.get("paid_amount", 0)))
# # #             return name or "SYNCED"

# # #     except urllib.error.HTTPError as e:
# # #         try:
# # #             err = json.loads(e.read().decode())
# # #             msg = (err.get("exception") or err.get("message") or
# # #                    str(err.get("_server_messages", "")) or f"HTTP {e.code}")
# # #         except Exception:
# # #             msg = f"HTTP {e.code}"

# # #         if e.code == 409:
# # #             log.info("Payment %d already on Frappe (409) - marking synced.", pe_id)
# # #             return "DUPLICATE"

# # #         # Invoice already paid (is_pos:1 on old invoices) - stop retrying
# # #         if e.code == 417:
# # #             _perma = ("already been fully paid", "already paid", "fully paid")
# # #             if any(p in msg.lower() for p in _perma):
# # #                 log.info("Payment %d - invoice already paid on Frappe, marking synced.", pe_id)
# # #                 return "ALREADY_PAID"

# # #         log.error("FAIL Payment Entry %d  HTTP %s: %s", pe_id, e.code, msg)
# # #         return None

# # #     except urllib.error.URLError as e:
# # #         log.warning("Network error pushing payment %d: %s", pe_id, e.reason)
# # #         return None

# # #     except Exception as e:
# # #         log.error("Unexpected error pushing payment %d: %s", pe_id, e)
# # #         return None


# # # # =============================================================================
# # # # PUBLIC — push all unsynced payment entries
# # # # =============================================================================

# # # def push_unsynced_payment_entries() -> dict:
# # #     """
# # #     1. Refresh frappe_invoice_ref from parent sales that were confirmed.
# # #     2. Push each unsynced payment entry to Frappe.
# # #     3. Mark synced with the returned PAY-xxxxx ref.
# # #     """
# # #     result = {"pushed": 0, "failed": 0, "skipped": 0, "total": 0}

# # #     api_key, api_secret = _get_credentials()
# # #     if not api_key or not api_secret:
# # #         log.warning("No credentials — skipping payment entry sync.")
# # #         return result

# # #     host     = _get_host()
# # #     defaults = _get_defaults()

# # #     # First: pull frappe_refs from confirmed invoices into pending payment entries
# # #     updated = refresh_frappe_refs()
# # #     if updated:
# # #         log.info("Refreshed frappe_invoice_ref on %d payment entry(ies).", updated)

# # #     entries = get_unsynced_payment_entries()
# # #     result["total"] = len(entries)

# # #     if not entries:
# # #         log.debug("No unsynced payment entries.")
# # #         return result

# # #     log.info("Pushing %d payment entry(ies) to Frappe…", len(entries))

# # #     for pe in entries:
# # #         frappe_name = _push_payment_entry(pe, api_key, api_secret, defaults, host)
# # #         if frappe_name:
# # #             mark_payment_synced(pe["id"], frappe_name)
# # #             result["pushed"] += 1
# # #         elif frappe_name is None:
# # #             # None = permanent skip (no frappe_inv yet), not a real failure
# # #             result["skipped"] += 1
# # #         else:
# # #             result["failed"] += 1

# # #         time.sleep(3)   # rate limit — 20/min max

# # #     log.info("Payment sync done — ✅ %d pushed  ❌ %d failed  ⏭ %d skipped",
# # #              result["pushed"], result["failed"], result["skipped"])
# # #     return result


# # # # =============================================================================
# # # # BACKGROUND DAEMON THREAD
# # # # =============================================================================

# # # def _sync_loop():
# # #     log.info("Payment entry sync daemon started (interval=%ds).", SYNC_INTERVAL)
# # #     while True:
# # #         if _sync_lock.acquire(blocking=False):
# # #             try:
# # #                 push_unsynced_payment_entries()
# # #             except Exception as e:
# # #                 log.error("Payment sync cycle error: %s", e)
# # #             finally:
# # #                 _sync_lock.release()
# # #         else:
# # #             log.debug("Previous payment sync still running — skipping.")
# # #         time.sleep(SYNC_INTERVAL)


# # # def start_payment_sync_daemon() -> threading.Thread:
# # #     """Non-blocking — safe to call from MainWindow.__init__."""
# # #     global _sync_thread
# # #     if _sync_thread and _sync_thread.is_alive():
# # #         return _sync_thread
# # #     t = threading.Thread(target=_sync_loop, daemon=True, name="PaymentSyncDaemon")
# # #     t.start()
# # #     _sync_thread = t
# # #     log.info("Payment entry sync daemon started.")
# # #     return t


# # # # =============================================================================
# # # # DEBUG
# # # # =============================================================================

# # # if __name__ == "__main__":
# # #     logging.basicConfig(level=logging.INFO,
# # #                         format="%(asctime)s [%(levelname)s] %(message)s")
# # #     print("Running one payment entry sync cycle...")
# # #     r = push_unsynced_payment_entries()
# # #     print(f"\nResult: {r['pushed']} pushed, {r['failed']} failed, "
# # #           f"{r['skipped']} skipped (of {r['total']} total)")


# # # =============================================================================
# # # services/payment_entry_service.py
# # #
# # # Manages local payment_entries table and syncs them to Frappe.
# # #
# # # FLOW:
# # #   1. When a sale is saved locally → create_payment_entry() stores it locally
# # #      with synced=0
# # #   2. When the Sales Invoice is confirmed on Frappe (frappe_ref is set) →
# # #      push_unsynced_payment_entries() pushes the Payment Entry to Frappe
# # #   3. Frappe returns a PAY-xxxxx ref → stored as frappe_payment_ref, synced=1
# # #
# # # PAYLOAD SENT TO FRAPPE:
# # #   POST /api/resource/Payment Entry
# # #   {
# # #     "doctype":              "Payment Entry",
# # #     "payment_type":         "Receive",
# # #     "party_type":           "Customer",
# # #     "party":                "Cathy",
# # #     "paid_to":              "Cash ZWG - H",
# # #     "paid_to_account_currency": "USD",
# # #     "paid_amount":          32.45,
# # #     "received_amount":      32.45,
# # #     "source_exchange_rate": 1.0,
# # #     "reference_no":         "ACC-SINV-2026-00034",
# # #     "reference_date":       "2026-03-19",
# # #     "remarks":              "POS Payment — Cash",
# # #     "docstatus":            1,
# # #     "references": [{
# # #         "reference_doctype": "Sales Invoice",
# # #         "reference_name":    "ACC-SINV-2026-00565",
# # #         "allocated_amount":  32.45
# # #     }]
# # #   }
# # # =============================================================================

# # from __future__ import annotations

# # import json
# # import logging
# # import time
# # import threading
# # import urllib.request
# # import urllib.error
# # from datetime import date

# # log = logging.getLogger("PaymentEntry")

# # SYNC_INTERVAL   = 60      # seconds between auto-sync cycles
# # REQUEST_TIMEOUT = 30

# # # Exchange rate cache: "FROM::TO::DATE" → float
# # _RATE_CACHE: dict[str, float] = {}


# # def _get_exchange_rate(from_currency: str, to_currency: str,
# #                        transaction_date: str,
# #                        api_key: str, api_secret: str, host: str) -> float:
# #     """
# #     Fetch live exchange rate from Frappe.
# #     Returns 1.0 for same currency, 0.0 if fetch fails (Frappe uses its own rate).
# #     """
# #     if not from_currency or from_currency.upper() == to_currency.upper():
# #         return 1.0

# #     cache_key = f"{from_currency.upper()}::{to_currency.upper()}::{transaction_date}"
# #     if cache_key in _RATE_CACHE:
# #         return _RATE_CACHE[cache_key]

# #     try:
# #         import urllib.parse
# #         url = (
# #             f"{host}/api/method/erpnext.setup.utils.get_exchange_rate"
# #             f"?from_currency={urllib.parse.quote(from_currency)}"
# #             f"&to_currency={urllib.parse.quote(to_currency)}"
# #             f"&transaction_date={transaction_date}"
# #         )
# #         req = urllib.request.Request(url)
# #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# #             data = json.loads(r.read().decode())
# #             rate = float(data.get("message") or data.get("result") or 0)
# #             if rate > 0:
# #                 _RATE_CACHE[cache_key] = rate
# #                 log.debug("Rate %s→%s on %s: %.6f", from_currency, to_currency, transaction_date, rate)
# #                 return rate
# #     except Exception as e:
# #         log.debug("Rate fetch failed (%s→%s): %s", from_currency, to_currency, e)

# #     return 0.0

# # _sync_lock:   threading.Lock          = threading.Lock()
# # _sync_thread: threading.Thread | None = None

# # # Method → Frappe Mode of Payment name
# # _METHOD_MAP = {
# #     "CASH":     "Cash",
# #     "CARD":     "Credit Card",
# #     "C / CARD": "Credit Card",
# #     "EFTPOS":   "Credit Card",
# #     "CHECK":    "Cheque",
# #     "CHEQUE":   "Cheque",
# #     "MOBILE":   "Mobile Money",
# #     "CREDIT":   "Credit",
# #     "TRANSFER": "Bank Transfer",
# # }


# # # =============================================================================
# # # CREDENTIALS / HOST / DEFAULTS
# # # =============================================================================

# # def _get_credentials() -> tuple[str, str]:
# #     try:
# #         from services.credentials import get_credentials
# #         return get_credentials()
# #     except Exception:
# #         pass
# #     return "", ""

# # def _get_host() -> str:
# #     try:
# #         from models.company_defaults import get_defaults
# #         host = (get_defaults() or {}).get("server_api_host", "").strip().rstrip("/")
# #         if host:
# #             return host
# #     except Exception:
# #         pass
# #     return "https://apk.havano.cloud"


# # def _get_defaults() -> dict:
# #     try:
# #         from models.company_defaults import get_defaults
# #         return get_defaults() or {}
# #     except Exception:
# #         return {}


# # # =============================================================================
# # # GL ACCOUNT RESOLVER  (which account to credit for each payment method)
# # # =============================================================================

# # _ACCOUNT_CACHE: dict[str, str] = {}


# # def _resolve_paid_to_account(mop_name: str, company: str, currency: str,
# #                               api_key: str, api_secret: str, host: str) -> str:
# #     """
# #     Looks up the GL account for a Mode of Payment from Frappe.
# #     Tries to match by currency if multiple accounts exist for the company.
# #     Falls back to server_pos_account in company_defaults.
# #     """
# #     cache_key = f"{mop_name}::{company}::{currency}"
# #     if cache_key in _ACCOUNT_CACHE:
# #         return _ACCOUNT_CACHE[cache_key]

# #     try:
# #         import urllib.parse
# #         url = (f"{host}/api/resource/Mode%20of%20Payment/"
# #                f"{urllib.parse.quote(mop_name)}?fields=[\"accounts\"]")
# #         req = urllib.request.Request(url)
# #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# #             data     = json.loads(r.read().decode())
# #             accounts = (data.get("data") or {}).get("accounts", [])

# #         company_accts = [a for a in accounts
# #                          if not company or a.get("company") == company]

# #         # Prefer account whose name contains the currency code
# #         matched = ""
# #         if currency:
# #             for a in company_accts:
# #                 if currency.upper() in (a.get("default_account") or "").upper():
# #                     matched = a["default_account"]; break

# #         if not matched and company_accts:
# #             matched = company_accts[0].get("default_account", "")

# #         if matched:
# #             _ACCOUNT_CACHE[cache_key] = matched
# #             return matched

# #     except Exception as e:
# #         log.debug("MOP account lookup failed for '%s': %s", mop_name, e)

# #     # Fallback
# #     fallback = _get_defaults().get("server_pos_account", "").strip()
# #     if fallback:
# #         _ACCOUNT_CACHE[cache_key] = fallback
# #         return fallback

# #     log.warning("No GL account for MOP '%s' currency=%s — Payment Entry may fail.",
# #                 mop_name, currency)
# #     return ""


# # # =============================================================================
# # # LOCAL DB  — create / read / update payment_entries
# # # =============================================================================

# # def create_payment_entry(sale: dict, override_rate: float = None,
# #                          override_account: str = None) -> int | None:
# #     """
# #     Called immediately after a sale is saved locally.
# #     Stores a payment_entry row with synced=0.
# #     Returns the new payment_entry id, or None on error.

# #     Will only create the entry once per sale (idempotent).
# #     """
# #     from database.db import get_connection
# #     conn = get_connection(); cur = conn.cursor()

# #     # Idempotency: don't create twice for the same sale
# #     cur.execute("SELECT id FROM payment_entries WHERE sale_id = ?", (sale["id"],))
# #     if cur.fetchone():
# #         conn.close()
# #         return None

# #     customer   = (sale.get("customer_name") or "default").strip()
# #     currency   = (sale.get("currency")      or "USD").strip().upper()
# #     amount     = float(sale.get("total")    or 0)
# #     inv_no     = sale.get("invoice_no", "")
# #     inv_date   = sale.get("invoice_date") or date.today().isoformat()
# #     method     = str(sale.get("method", "CASH")).upper().strip()
# #     mop        = _METHOD_MAP.get(method, "Cash")

# #     # Use override rate (from split) or fetch from Frappe
# #     if override_rate is not None:
# #         exch_rate = override_rate
# #     else:
# #         try:
# #             api_key, api_secret = _get_credentials()
# #             host = _get_host()
# #             defaults = _get_defaults()
# #             company_currency = defaults.get("server_company_currency", "USD").strip().upper() or "USD"
# #             exch_rate = _get_exchange_rate(
# #                 currency, company_currency, inv_date, api_key, api_secret, host
# #             ) if currency != company_currency else 1.0
# #         except Exception:
# #             exch_rate = 1.0

# #     cur.execute("""
# #         INSERT INTO payment_entries (
# #             sale_id, sale_invoice_no, frappe_invoice_ref,
# #             party, party_name,
# #             paid_amount, received_amount, source_exchange_rate,
# #             paid_to_account_currency, currency,
# #             mode_of_payment,
# #             reference_no, reference_date,
# #             remarks, synced
# #         ) OUTPUT INSERTED.id
# #         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# #     """, (
# #         sale["id"], inv_no,
# #         sale.get("frappe_ref") or None,
# #         customer, customer,
# #         amount, amount, exch_rate or 1.0,
# #         currency, currency,
# #         mop,
# #         inv_no, inv_date,
# #         f"POS Payment — {mop}",
# #     ))
# #     new_id = int(cur.fetchone()[0])
# #     conn.commit(); conn.close()
# #     log.debug("Payment entry %d created locally for sale %s", new_id, inv_no)
# #     return new_id


# # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# #     """
# #     Called when cashier uses Split payment.
# #     Creates one payment_entry row per currency in splits list.
# #     splits = [{"mode": "CASH", "currency": "USD", "amount": 5.0,
# #                "rate": 1.0, "base_amount": 5.0, "account": "Cash - AT"}, ...]
# #     Returns list of new payment_entry ids.
# #     """
# #     ids = []
# #     for split in splits:
# #         if not split.get("amount") or float(split["amount"]) <= 0:
# #             continue
# #         # Build a sale-like dict with the split's currency and amount
# #         split_sale = dict(sale)
# #         split_sale["currency"]      = split.get("currency", "USD")
# #         split_sale["total"]         = float(split.get("amount", 0))
# #         split_sale["method"]        = split.get("mode", "CASH")
# #         # Override exchange rate from split data
# #         new_id = create_payment_entry(
# #             split_sale,
# #             override_rate=float(split.get("rate", 1.0)),
# #             override_account=split.get("account", ""),
# #         )
# #         if new_id:
# #             ids.append(new_id)
# #     return ids


# # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# #     """
# #     Creates one payment_entry per currency from a split payment.
# #     Groups splits by currency, sums amounts, creates one entry each.
# #     Returns list of created payment_entry ids.
# #     """
# #     from datetime import date as _date

# #     # Group by currency
# #     by_currency: dict[str, dict] = {}
# #     for s in splits:
# #         curr = s.get("account_currency", "USD").upper()
# #         if curr not in by_currency:
# #             by_currency[curr] = {
# #                 "currency":      curr,
# #                 "paid_amount":   0.0,
# #                 "base_value":    0.0,
# #                 "rate":          s.get("rate", 1.0),
# #                 "account_name":  s.get("account_name", ""),
# #                 "mode":          s.get("mode", "Cash"),
# #             }
# #         by_currency[curr]["paid_amount"] += s.get("amount_paid", 0.0)
# #         by_currency[curr]["base_value"]  += s.get("base_value",  0.0)

# #     ids = []
# #     inv_no   = sale.get("invoice_no", "")
# #     inv_date = sale.get("invoice_date") or _date.today().isoformat()
# #     customer = (sale.get("customer_name") or "default").strip()

# #     from database.db import get_connection
# #     conn = get_connection(); cur = conn.cursor()

# #     for curr, grp in by_currency.items():
# #         # Idempotency: skip if already exists for this sale+currency
# #         cur.execute(
# #             "SELECT id FROM payment_entries WHERE sale_id=? AND currency=?",
# #             (sale["id"], curr)
# #         )
# #         if cur.fetchone():
# #             continue

# #         mop = _METHOD_MAP.get(grp["mode"].upper(), "Cash")

# #         cur.execute("""
# #             INSERT INTO payment_entries (
# #                 sale_id, sale_invoice_no, frappe_invoice_ref,
# #                 party, party_name,
# #                 paid_amount, received_amount, source_exchange_rate,
# #                 paid_to_account_currency, currency,
# #                 paid_to,
# #                 mode_of_payment,
# #                 reference_no, reference_date,
# #                 remarks, synced
# #             ) OUTPUT INSERTED.id
# #             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# #         """, (
# #             sale["id"], inv_no,
# #             sale.get("frappe_ref") or None,
# #             customer, customer,
# #             grp["paid_amount"],
# #             grp["base_value"],
# #             float(grp["rate"] or 1.0),
# #             curr, curr,
# #             grp["account_name"],
# #             mop,
# #             inv_no, inv_date,
# #             f"POS Split Payment — {mop} ({curr})",
# #         ))
# #         new_id = int(cur.fetchone()[0])
# #         ids.append(new_id)
# #         log.debug("Split payment entry %d created: %s %.2f %s",
# #                   new_id, curr, grp["paid_amount"], inv_no)

# #     conn.commit(); conn.close()
# #     return ids


# # def get_unsynced_payment_entries() -> list[dict]:
# #     """Returns payment entries that are ready to push (synced=0)."""
# #     from database.db import get_connection, fetchall_dicts
# #     conn = get_connection(); cur = conn.cursor()
# #     cur.execute("""
# #         SELECT pe.*, s.frappe_ref AS sale_frappe_ref
# #         FROM payment_entries pe
# #         LEFT JOIN sales s ON s.id = pe.sale_id
# #         WHERE pe.synced = 0
# #           AND (pe.frappe_invoice_ref IS NOT NULL
# #                OR s.frappe_ref IS NOT NULL)
# #         ORDER BY pe.id
# #     """)
# #     rows = fetchall_dicts(cur); conn.close()
# #     return rows


# # def mark_payment_synced(pe_id: int, frappe_payment_ref: str = "") -> None:
# #     from database.db import get_connection
# #     conn = get_connection(); cur = conn.cursor()
# #     cur.execute(
# #         "UPDATE payment_entries SET synced=1, frappe_payment_ref=? WHERE id=?",
# #         (frappe_payment_ref or None, pe_id)
# #     )
# #     # Also update the sales row
# #     cur.execute("""
# #         UPDATE sales SET payment_entry_ref=?, payment_synced=1
# #         WHERE id = (SELECT sale_id FROM payment_entries WHERE id=?)
# #     """, (frappe_payment_ref or None, pe_id))
# #     conn.commit(); conn.close()


# # def refresh_frappe_refs() -> int:
# #     """
# #     For payment entries that have no frappe_invoice_ref yet, copy it from
# #     the parent sale's frappe_ref. Call this before pushing payments.
# #     Returns count updated.
# #     """
# #     from database.db import get_connection
# #     conn = get_connection(); cur = conn.cursor()
# #     cur.execute("""
# #         UPDATE pe
# #         SET pe.frappe_invoice_ref = s.frappe_ref
# #         FROM payment_entries pe
# #         JOIN sales s ON s.id = pe.sale_id
# #         WHERE pe.synced = 0
# #           AND (pe.frappe_invoice_ref IS NULL OR pe.frappe_invoice_ref = '')
# #           AND s.frappe_ref IS NOT NULL AND s.frappe_ref != ''
# #     """)
# #     count = cur.rowcount
# #     conn.commit(); conn.close()
# #     return count


# # # =============================================================================
# # # BUILD FRAPPE PAYLOAD
# # # =============================================================================

# # def _build_payload(pe: dict, defaults: dict,
# #                    api_key: str, api_secret: str, host: str) -> dict:
# #     company  = defaults.get("server_company", "")
# #     currency = (pe.get("currency") or pe.get("paid_to_account_currency") or "USD").upper()
# #     mop      = pe.get("mode_of_payment") or "Cash"
# #     amount   = float(pe.get("paid_amount") or 0)
# #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()

# #     # Use local gl_accounts table first (synced from Frappe)
# #     paid_to          = (pe.get("paid_to") or "").strip()
# #     paid_to_currency = currency
# #     if not paid_to:
# #         try:
# #             from models.gl_account import get_account_for_payment
# #             acct = get_account_for_payment(currency, company)
# #             if acct:
# #                 paid_to          = acct["name"]
# #                 paid_to_currency = acct["account_currency"]
# #         except Exception as _e:
# #             log.debug("gl_account lookup failed: %s", _e)

# #     # Fallback to live Frappe lookup
# #     if not paid_to:
# #         paid_to = _resolve_paid_to_account(mop, company, currency, api_key, api_secret, host)

# #     # Use local exchange rate if not stored
# #     exch_rate = float(pe.get("source_exchange_rate") or 1.0)
# #     if exch_rate == 1.0 and currency not in ("USD", ""):
# #         try:
# #             from models.exchange_rate import get_rate
# #             stored = get_rate(currency, "USD")
# #             if stored:
# #                 exch_rate = stored
# #         except Exception:
# #             pass

# #     payload = {
# #         "doctype":                  "Payment Entry",
# #         "payment_type":             "Receive",
# #         "party_type":               "Customer",
# #         "party":                    pe.get("party") or "default",
# #         "party_name":               pe.get("party_name") or "default",
# #         "paid_to_account_currency": paid_to_currency,
# #         "paid_amount":              amount,
# #         "received_amount":          amount,
# #         "source_exchange_rate":     exch_rate,
# #         "reference_no":             pe.get("reference_no") or pe.get("sale_invoice_no", ""),
# #         "reference_date":           (
# #             pe.get("reference_date").isoformat()
# #             if hasattr(pe.get("reference_date"), "isoformat")
# #             else pe.get("reference_date") or date.today().isoformat()
# #         ),
# #         "remarks":                  pe.get("remarks") or f"POS Payment — {mop}",
# #         "mode_of_payment":          mop,
# #         "docstatus":                1,
# #     }

# #     if paid_to:
# #         payload["paid_to"] = paid_to
# #     if company:
# #         payload["company"] = company

# #     # Link to the Sales Invoice on Frappe
# #     if frappe_inv:
# #         payload["references"] = [{
# #             "reference_doctype": "Sales Invoice",
# #             "reference_name":    frappe_inv,
# #             "allocated_amount":  amount,
# #         }]

# #     return payload


# # # =============================================================================
# # # PUSH ONE PAYMENT ENTRY
# # # =============================================================================

# # def _push_payment_entry(pe: dict, api_key: str, api_secret: str,
# #                         defaults: dict, host: str) -> str | None:
# #     """
# #     Posts one payment entry to Frappe.
# #     Returns Frappe's PAY-xxxxx name on success, None on failure.
# #     """
# #     pe_id  = pe["id"]
# #     inv_no = pe.get("sale_invoice_no", str(pe_id))

# #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()
# #     if not frappe_inv:
# #         log.warning("Payment %d — Sales Invoice not yet on Frappe, skipping.", pe_id)
# #         return None

# #     payload = _build_payload(pe, defaults, api_key, api_secret, host)

# #     url = f"{host}/api/resource/Payment%20Entry"
# #     req = urllib.request.Request(
# #         url=url,
# #         data=json.dumps(payload, default=lambda o: o.isoformat() if hasattr(o, 'isoformat') else str(o)).encode("utf-8"),
# #         method="POST",
# #         headers={
# #             "Content-Type":  "application/json",
# #             "Accept":        "application/json",
# #             "Authorization": f"token {api_key}:{api_secret}",
# #         },
# #     )

# #     try:
# #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
# #             data = json.loads(resp.read().decode())
# #             name = (data.get("data") or {}).get("name", "")
# #             log.info("✅ Payment Entry %d → Frappe %s  [%s  %s %.2f]",
# #                      pe_id, name, inv_no,
# #                      pe.get("currency", ""), float(pe.get("paid_amount", 0)))
# #             return name or "SYNCED"

# #     except urllib.error.HTTPError as e:
# #         try:
# #             err = json.loads(e.read().decode())
# #             msg = (err.get("exception") or err.get("message") or
# #                    str(err.get("_server_messages", "")) or f"HTTP {e.code}")
# #         except Exception:
# #             msg = f"HTTP {e.code}"

# #         if e.code == 409:
# #             log.info("Payment %d already on Frappe (409) - marking synced.", pe_id)
# #             return "DUPLICATE"

# #         # Invoice already paid (is_pos:1 on old invoices) - stop retrying
# #         if e.code == 417:
# #             _perma = ("already been fully paid", "already paid", "fully paid")
# #             if any(p in msg.lower() for p in _perma):
# #                 log.info("Payment %d - invoice already paid on Frappe, marking synced.", pe_id)
# #                 return "ALREADY_PAID"

# #         log.error("FAIL Payment Entry %d  HTTP %s: %s", pe_id, e.code, msg)
# #         return None

# #     except urllib.error.URLError as e:
# #         log.warning("Network error pushing payment %d: %s", pe_id, e.reason)
# #         return None

# #     except Exception as e:
# #         log.error("Unexpected error pushing payment %d: %s", pe_id, e)
# #         return None


# # # =============================================================================
# # # PUBLIC — push all unsynced payment entries
# # # =============================================================================

# # def push_unsynced_payment_entries() -> dict:
# #     """
# #     1. Refresh frappe_invoice_ref from parent sales that were confirmed.
# #     2. Push each unsynced payment entry to Frappe.
# #     3. Mark synced with the returned PAY-xxxxx ref.
# #     """
# #     result = {"pushed": 0, "failed": 0, "skipped": 0, "total": 0}

# #     api_key, api_secret = _get_credentials()
# #     if not api_key or not api_secret:
# #         log.warning("No credentials — skipping payment entry sync.")
# #         return result

# #     host     = _get_host()
# #     defaults = _get_defaults()

# #     # First: pull frappe_refs from confirmed invoices into pending payment entries
# #     updated = refresh_frappe_refs()
# #     if updated:
# #         log.info("Refreshed frappe_invoice_ref on %d payment entry(ies).", updated)

# #     entries = get_unsynced_payment_entries()
# #     result["total"] = len(entries)

# #     if not entries:
# #         log.debug("No unsynced payment entries.")
# #         return result

# #     log.info("Pushing %d payment entry(ies) to Frappe…", len(entries))

# #     for pe in entries:
# #         frappe_name = _push_payment_entry(pe, api_key, api_secret, defaults, host)
# #         if frappe_name:
# #             mark_payment_synced(pe["id"], frappe_name)
# #             result["pushed"] += 1
# #         elif frappe_name is None:
# #             # None = permanent skip (no frappe_inv yet), not a real failure
# #             result["skipped"] += 1
# #         else:
# #             result["failed"] += 1

# #         time.sleep(3)   # rate limit — 20/min max

# #     log.info("Payment sync done — ✅ %d pushed  ❌ %d failed  ⏭ %d skipped",
# #              result["pushed"], result["failed"], result["skipped"])
# #     return result


# # # =============================================================================
# # # BACKGROUND DAEMON THREAD
# # # =============================================================================

# # def _sync_loop():
# #     log.info("Payment entry sync daemon started (interval=%ds).", SYNC_INTERVAL)
# #     while True:
# #         if _sync_lock.acquire(blocking=False):
# #             try:
# #                 push_unsynced_payment_entries()
# #             except Exception as e:
# #                 log.error("Payment sync cycle error: %s", e)
# #             finally:
# #                 _sync_lock.release()
# #         else:
# #             log.debug("Previous payment sync still running — skipping.")
# #         time.sleep(SYNC_INTERVAL)


# # def start_payment_sync_daemon() -> threading.Thread:
# #     """Non-blocking — safe to call from MainWindow.__init__."""
# #     global _sync_thread
# #     if _sync_thread and _sync_thread.is_alive():
# #         return _sync_thread
# #     t = threading.Thread(target=_sync_loop, daemon=True, name="PaymentSyncDaemon")
# #     t.start()
# #     _sync_thread = t
# #     log.info("Payment entry sync daemon started.")
# #     return t


# # # =============================================================================
# # # DEBUG
# # # =============================================================================

# # if __name__ == "__main__":
# #     logging.basicConfig(level=logging.INFO,
# #                         format="%(asctime)s [%(levelname)s] %(message)s")
# #     print("Running one payment entry sync cycle...")
# #     r = push_unsynced_payment_entries()
# #     print(f"\nResult: {r['pushed']} pushed, {r['failed']} failed, "
# #           f"{r['skipped']} skipped (of {r['total']} total)")


# # # # # # =============================================================================
# # # # # # services/payment_entry_service.py
# # # # # #
# # # # # # Manages local payment_entries table and syncs them to Frappe.
# # # # # #
# # # # # # FLOW:
# # # # # #   1. When a sale is saved locally → create_payment_entry() stores it locally
# # # # # #      with synced=0
# # # # # #   2. When the Sales Invoice is confirmed on Frappe (frappe_ref is set) →
# # # # # #      push_unsynced_payment_entries() pushes the Payment Entry to Frappe
# # # # # #   3. Frappe returns a PAY-xxxxx ref → stored as frappe_payment_ref, synced=1
# # # # # #
# # # # # # PAYLOAD SENT TO FRAPPE:
# # # # # #   POST /api/resource/Payment Entry
# # # # # #   {
# # # # # #     "doctype":              "Payment Entry",
# # # # # #     "payment_type":         "Receive",
# # # # # #     "party_type":           "Customer",
# # # # # #     "party":                "Cathy",
# # # # # #     "paid_to":              "Cash ZWG - H",
# # # # # #     "paid_to_account_currency": "USD",
# # # # # #     "paid_amount":          32.45,
# # # # # #     "received_amount":      32.45,
# # # # # #     "source_exchange_rate": 1.0,
# # # # # #     "reference_no":         "ACC-SINV-2026-00034",
# # # # # #     "reference_date":       "2026-03-19",
# # # # # #     "remarks":              "POS Payment — Cash",
# # # # # #     "docstatus":            1,
# # # # # #     "references": [{
# # # # # #         "reference_doctype": "Sales Invoice",
# # # # # #         "reference_name":    "ACC-SINV-2026-00565",
# # # # # #         "allocated_amount":  32.45
# # # # # #     }]
# # # # # #   }
# # # # # # =============================================================================

# # # # # from __future__ import annotations

# # # # # import json
# # # # # import logging
# # # # # import time
# # # # # import threading
# # # # # import urllib.request
# # # # # import urllib.error
# # # # # from datetime import date

# # # # # log = logging.getLogger("PaymentEntry")

# # # # # SYNC_INTERVAL   = 60      # seconds between auto-sync cycles
# # # # # REQUEST_TIMEOUT = 30

# # # # # # Exchange rate cache: "FROM::TO::DATE" → float
# # # # # _RATE_CACHE: dict[str, float] = {}


# # # # # def _get_exchange_rate(from_currency: str, to_currency: str,
# # # # #                        transaction_date: str,
# # # # #                        api_key: str, api_secret: str, host: str) -> float:
# # # # #     """
# # # # #     Fetch live exchange rate from Frappe.
# # # # #     Returns 1.0 for same currency, 0.0 if fetch fails (Frappe uses its own rate).
# # # # #     """
# # # # #     if not from_currency or from_currency.upper() == to_currency.upper():
# # # # #         return 1.0

# # # # #     cache_key = f"{from_currency.upper()}::{to_currency.upper()}::{transaction_date}"
# # # # #     if cache_key in _RATE_CACHE:
# # # # #         return _RATE_CACHE[cache_key]

# # # # #     try:
# # # # #         import urllib.parse
# # # # #         url = (
# # # # #             f"{host}/api/method/erpnext.setup.utils.get_exchange_rate"
# # # # #             f"?from_currency={urllib.parse.quote(from_currency)}"
# # # # #             f"&to_currency={urllib.parse.quote(to_currency)}"
# # # # #             f"&transaction_date={transaction_date}"
# # # # #         )
# # # # #         req = urllib.request.Request(url)
# # # # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # # # #             data = json.loads(r.read().decode())
# # # # #             rate = float(data.get("message") or data.get("result") or 0)
# # # # #             if rate > 0:
# # # # #                 _RATE_CACHE[cache_key] = rate
# # # # #                 log.debug("Rate %s→%s on %s: %.6f", from_currency, to_currency, transaction_date, rate)
# # # # #                 return rate
# # # # #     except Exception as e:
# # # # #         log.debug("Rate fetch failed (%s→%s): %s", from_currency, to_currency, e)

# # # # #     return 0.0

# # # # # _sync_lock:   threading.Lock          = threading.Lock()
# # # # # _sync_thread: threading.Thread | None = None

# # # # # # Method → Frappe Mode of Payment name
# # # # # _METHOD_MAP = {
# # # # #     "CASH":     "Cash",
# # # # #     "CARD":     "Credit Card",
# # # # #     "C / CARD": "Credit Card",
# # # # #     "EFTPOS":   "Credit Card",
# # # # #     "CHECK":    "Cheque",
# # # # #     "CHEQUE":   "Cheque",
# # # # #     "MOBILE":   "Mobile Money",
# # # # #     "CREDIT":   "Credit",
# # # # #     "TRANSFER": "Bank Transfer",
# # # # # }


# # # # # # =============================================================================
# # # # # # CREDENTIALS / HOST / DEFAULTS
# # # # # # =============================================================================

# # # # # def _get_credentials() -> tuple[str, str]:
# # # # #     try:
# # # # #         from services.auth_service import get_session
# # # # #         s = get_session()
# # # # #         if s.get("api_key") and s.get("api_secret"):
# # # # #             return s["api_key"], s["api_secret"]
# # # # #     except Exception:
# # # # #         pass
# # # # #     try:
# # # # #         from database.db import get_connection
# # # # #         conn = get_connection(); cur = conn.cursor()
# # # # #         cur.execute("SELECT api_key, api_secret FROM company_defaults WHERE id = 1")
# # # # #         row = cur.fetchone(); conn.close()
# # # # #         if row and row[0] and row[1]:
# # # # #             return row[0], row[1]
# # # # #     except Exception:
# # # # #         pass
# # # # #     import os
# # # # #     return os.environ.get("HAVANO_API_KEY", ""), os.environ.get("HAVANO_API_SECRET", "")


# # # # # def _get_host() -> str:
# # # # #     try:
# # # # #         from models.company_defaults import get_defaults
# # # # #         host = (get_defaults() or {}).get("server_api_host", "").strip().rstrip("/")
# # # # #         if host:
# # # # #             return host
# # # # #     except Exception:
# # # # #         pass
# # # # #     return "https://apk.havano.cloud"


# # # # # def _get_defaults() -> dict:
# # # # #     try:
# # # # #         from models.company_defaults import get_defaults
# # # # #         return get_defaults() or {}
# # # # #     except Exception:
# # # # #         return {}


# # # # # # =============================================================================
# # # # # # GL ACCOUNT RESOLVER  (which account to credit for each payment method)
# # # # # # =============================================================================

# # # # # _ACCOUNT_CACHE: dict[str, str] = {}


# # # # # def _resolve_paid_to_account(mop_name: str, company: str, currency: str,
# # # # #                               api_key: str, api_secret: str, host: str) -> str:
# # # # #     """
# # # # #     Looks up the GL account for a Mode of Payment from Frappe.
# # # # #     Tries to match by currency if multiple accounts exist for the company.
# # # # #     Falls back to server_pos_account in company_defaults.
# # # # #     """
# # # # #     cache_key = f"{mop_name}::{company}::{currency}"
# # # # #     if cache_key in _ACCOUNT_CACHE:
# # # # #         return _ACCOUNT_CACHE[cache_key]

# # # # #     try:
# # # # #         import urllib.parse
# # # # #         url = (f"{host}/api/resource/Mode%20of%20Payment/"
# # # # #                f"{urllib.parse.quote(mop_name)}?fields=[\"accounts\"]")
# # # # #         req = urllib.request.Request(url)
# # # # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # # # #             data     = json.loads(r.read().decode())
# # # # #             accounts = (data.get("data") or {}).get("accounts", [])

# # # # #         company_accts = [a for a in accounts
# # # # #                          if not company or a.get("company") == company]

# # # # #         # Prefer account whose name contains the currency code
# # # # #         matched = ""
# # # # #         if currency:
# # # # #             for a in company_accts:
# # # # #                 if currency.upper() in (a.get("default_account") or "").upper():
# # # # #                     matched = a["default_account"]; break

# # # # #         if not matched and company_accts:
# # # # #             matched = company_accts[0].get("default_account", "")

# # # # #         if matched:
# # # # #             _ACCOUNT_CACHE[cache_key] = matched
# # # # #             return matched

# # # # #     except Exception as e:
# # # # #         log.debug("MOP account lookup failed for '%s': %s", mop_name, e)

# # # # #     # Fallback
# # # # #     fallback = _get_defaults().get("server_pos_account", "").strip()
# # # # #     if fallback:
# # # # #         _ACCOUNT_CACHE[cache_key] = fallback
# # # # #         return fallback

# # # # #     log.warning("No GL account for MOP '%s' currency=%s — Payment Entry may fail.",
# # # # #                 mop_name, currency)
# # # # #     return ""


# # # # # # =============================================================================
# # # # # # LOCAL DB  — create / read / update payment_entries
# # # # # # =============================================================================

# # # # # def create_payment_entry(sale: dict, override_rate: float = None,
# # # # #                          override_account: str = None) -> int | None:
# # # # #     """
# # # # #     Called immediately after a sale is saved locally.
# # # # #     Stores a payment_entry row with synced=0.
# # # # #     Returns the new payment_entry id, or None on error.

# # # # #     Will only create the entry once per sale (idempotent).
# # # # #     """
# # # # #     from database.db import get_connection
# # # # #     conn = get_connection(); cur = conn.cursor()

# # # # #     # Idempotency: don't create twice for the same sale
# # # # #     cur.execute("SELECT id FROM payment_entries WHERE sale_id = ?", (sale["id"],))
# # # # #     if cur.fetchone():
# # # # #         conn.close()
# # # # #         return None

# # # # #     customer   = (sale.get("customer_name") or "default").strip()
# # # # #     currency   = (sale.get("currency")      or "USD").strip().upper()
# # # # #     amount     = float(sale.get("total")    or 0)
# # # # #     inv_no     = sale.get("invoice_no", "")
# # # # #     inv_date   = sale.get("invoice_date") or date.today().isoformat()
# # # # #     method     = str(sale.get("method", "CASH")).upper().strip()
# # # # #     mop        = _METHOD_MAP.get(method, "Cash")

# # # # #     # Use override rate (from split) or fetch from Frappe
# # # # #     if override_rate is not None:
# # # # #         exch_rate = override_rate
# # # # #     else:
# # # # #         try:
# # # # #             api_key, api_secret = _get_credentials()
# # # # #             host = _get_host()
# # # # #             defaults = _get_defaults()
# # # # #             company_currency = defaults.get("server_company_currency", "USD").strip().upper() or "USD"
# # # # #             exch_rate = _get_exchange_rate(
# # # # #                 currency, company_currency, inv_date, api_key, api_secret, host
# # # # #             ) if currency != company_currency else 1.0
# # # # #         except Exception:
# # # # #             exch_rate = 1.0

# # # # #     cur.execute("""
# # # # #         INSERT INTO payment_entries (
# # # # #             sale_id, sale_invoice_no, frappe_invoice_ref,
# # # # #             party, party_name,
# # # # #             paid_amount, received_amount, source_exchange_rate,
# # # # #             paid_to_account_currency, currency,
# # # # #             mode_of_payment,
# # # # #             reference_no, reference_date,
# # # # #             remarks, synced
# # # # #         ) OUTPUT INSERTED.id
# # # # #         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # # # #     """, (
# # # # #         sale["id"], inv_no,
# # # # #         sale.get("frappe_ref") or None,
# # # # #         customer, customer,
# # # # #         amount, amount, exch_rate or 1.0,
# # # # #         currency, currency,
# # # # #         mop,
# # # # #         inv_no, inv_date,
# # # # #         f"POS Payment — {mop}",
# # # # #     ))
# # # # #     new_id = int(cur.fetchone()[0])
# # # # #     conn.commit(); conn.close()
# # # # #     log.debug("Payment entry %d created locally for sale %s", new_id, inv_no)
# # # # #     return new_id


# # # # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # # # #     """
# # # # #     Called when cashier uses Split payment.
# # # # #     Creates one payment_entry row per currency in splits list.
# # # # #     splits = [{"mode": "CASH", "currency": "USD", "amount": 5.0,
# # # # #                "rate": 1.0, "base_amount": 5.0, "account": "Cash - AT"}, ...]
# # # # #     Returns list of new payment_entry ids.
# # # # #     """
# # # # #     ids = []
# # # # #     for split in splits:
# # # # #         if not split.get("amount") or float(split["amount"]) <= 0:
# # # # #             continue
# # # # #         # Build a sale-like dict with the split's currency and amount
# # # # #         split_sale = dict(sale)
# # # # #         split_sale["currency"]      = split.get("currency", "USD")
# # # # #         split_sale["total"]         = float(split.get("amount", 0))
# # # # #         split_sale["method"]        = split.get("mode", "CASH")
# # # # #         # Override exchange rate from split data
# # # # #         new_id = create_payment_entry(
# # # # #             split_sale,
# # # # #             override_rate=float(split.get("rate", 1.0)),
# # # # #             override_account=split.get("account", ""),
# # # # #         )
# # # # #         if new_id:
# # # # #             ids.append(new_id)
# # # # #     return ids


# # # # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # # # #     """
# # # # #     Creates one payment_entry per currency from a split payment.
# # # # #     Groups splits by currency, sums amounts, creates one entry each.
# # # # #     Returns list of created payment_entry ids.
# # # # #     """
# # # # #     from datetime import date as _date

# # # # #     # Group by currency
# # # # #     by_currency: dict[str, dict] = {}
# # # # #     for s in splits:
# # # # #         curr = s.get("account_currency", "USD").upper()
# # # # #         if curr not in by_currency:
# # # # #             by_currency[curr] = {
# # # # #                 "currency":      curr,
# # # # #                 "paid_amount":   0.0,
# # # # #                 "base_value":    0.0,
# # # # #                 "rate":          s.get("rate", 1.0),
# # # # #                 "account_name":  s.get("account_name", ""),
# # # # #                 "mode":          s.get("mode", "Cash"),
# # # # #             }
# # # # #         by_currency[curr]["paid_amount"] += s.get("amount_paid", 0.0)
# # # # #         by_currency[curr]["base_value"]  += s.get("base_value",  0.0)

# # # # #     ids = []
# # # # #     inv_no   = sale.get("invoice_no", "")
# # # # #     inv_date = sale.get("invoice_date") or _date.today().isoformat()
# # # # #     customer = (sale.get("customer_name") or "default").strip()

# # # # #     from database.db import get_connection
# # # # #     conn = get_connection(); cur = conn.cursor()

# # # # #     for curr, grp in by_currency.items():
# # # # #         # Idempotency: skip if already exists for this sale+currency
# # # # #         cur.execute(
# # # # #             "SELECT id FROM payment_entries WHERE sale_id=? AND currency=?",
# # # # #             (sale["id"], curr)
# # # # #         )
# # # # #         if cur.fetchone():
# # # # #             continue

# # # # #         mop = _METHOD_MAP.get(grp["mode"].upper(), "Cash")

# # # # #         cur.execute("""
# # # # #             INSERT INTO payment_entries (
# # # # #                 sale_id, sale_invoice_no, frappe_invoice_ref,
# # # # #                 party, party_name,
# # # # #                 paid_amount, received_amount, source_exchange_rate,
# # # # #                 paid_to_account_currency, currency,
# # # # #                 paid_to,
# # # # #                 mode_of_payment,
# # # # #                 reference_no, reference_date,
# # # # #                 remarks, synced
# # # # #             ) OUTPUT INSERTED.id
# # # # #             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # # # #         """, (
# # # # #             sale["id"], inv_no,
# # # # #             sale.get("frappe_ref") or None,
# # # # #             customer, customer,
# # # # #             grp["paid_amount"],
# # # # #             grp["base_value"],
# # # # #             float(grp["rate"] or 1.0),
# # # # #             curr, curr,
# # # # #             grp["account_name"],
# # # # #             mop,
# # # # #             inv_no, inv_date,
# # # # #             f"POS Split Payment — {mop} ({curr})",
# # # # #         ))
# # # # #         new_id = int(cur.fetchone()[0])
# # # # #         ids.append(new_id)
# # # # #         log.debug("Split payment entry %d created: %s %.2f %s",
# # # # #                   new_id, curr, grp["paid_amount"], inv_no)

# # # # #     conn.commit(); conn.close()
# # # # #     return ids


# # # # # def get_unsynced_payment_entries() -> list[dict]:
# # # # #     """Returns payment entries that are ready to push (synced=0)."""
# # # # #     from database.db import get_connection, fetchall_dicts
# # # # #     conn = get_connection(); cur = conn.cursor()
# # # # #     cur.execute("""
# # # # #         SELECT pe.*, s.frappe_ref AS sale_frappe_ref
# # # # #         FROM payment_entries pe
# # # # #         LEFT JOIN sales s ON s.id = pe.sale_id
# # # # #         WHERE pe.synced = 0
# # # # #           AND (pe.frappe_invoice_ref IS NOT NULL
# # # # #                OR s.frappe_ref IS NOT NULL)
# # # # #         ORDER BY pe.id
# # # # #     """)
# # # # #     rows = fetchall_dicts(cur); conn.close()
# # # # #     return rows


# # # # # def mark_payment_synced(pe_id: int, frappe_payment_ref: str = "") -> None:
# # # # #     from database.db import get_connection
# # # # #     conn = get_connection(); cur = conn.cursor()
# # # # #     cur.execute(
# # # # #         "UPDATE payment_entries SET synced=1, frappe_payment_ref=? WHERE id=?",
# # # # #         (frappe_payment_ref or None, pe_id)
# # # # #     )
# # # # #     # Also update the sales row
# # # # #     cur.execute("""
# # # # #         UPDATE sales SET payment_entry_ref=?, payment_synced=1
# # # # #         WHERE id = (SELECT sale_id FROM payment_entries WHERE id=?)
# # # # #     """, (frappe_payment_ref or None, pe_id))
# # # # #     conn.commit(); conn.close()


# # # # # def refresh_frappe_refs() -> int:
# # # # #     """
# # # # #     For payment entries that have no frappe_invoice_ref yet, copy it from
# # # # #     the parent sale's frappe_ref. Call this before pushing payments.
# # # # #     Returns count updated.
# # # # #     """
# # # # #     from database.db import get_connection
# # # # #     conn = get_connection(); cur = conn.cursor()
# # # # #     cur.execute("""
# # # # #         UPDATE pe
# # # # #         SET pe.frappe_invoice_ref = s.frappe_ref
# # # # #         FROM payment_entries pe
# # # # #         JOIN sales s ON s.id = pe.sale_id
# # # # #         WHERE pe.synced = 0
# # # # #           AND (pe.frappe_invoice_ref IS NULL OR pe.frappe_invoice_ref = '')
# # # # #           AND s.frappe_ref IS NOT NULL AND s.frappe_ref != ''
# # # # #     """)
# # # # #     count = cur.rowcount
# # # # #     conn.commit(); conn.close()
# # # # #     return count


# # # # # # =============================================================================
# # # # # # BUILD FRAPPE PAYLOAD
# # # # # # =============================================================================

# # # # # def _build_payload(pe: dict, defaults: dict,
# # # # #                    api_key: str, api_secret: str, host: str) -> dict:
# # # # #     company  = defaults.get("server_company", "")
# # # # #     currency = (pe.get("currency") or pe.get("paid_to_account_currency") or "USD").upper()
# # # # #     mop      = pe.get("mode_of_payment") or "Cash"
# # # # #     amount   = float(pe.get("paid_amount") or 0)
# # # # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()

# # # # #     paid_to = _resolve_paid_to_account(mop, company, currency, api_key, api_secret, host)

# # # # #     payload = {
# # # # #         "doctype":                  "Payment Entry",
# # # # #         "payment_type":             "Receive",
# # # # #         "party_type":               "Customer",
# # # # #         "party":                    pe.get("party") or "default",
# # # # #         "party_name":               pe.get("party_name") or "default",
# # # # #         "paid_to_account_currency": currency,
# # # # #         "paid_amount":              amount,
# # # # #         "received_amount":          amount,
# # # # #         "source_exchange_rate":     float(pe.get("source_exchange_rate") or 1.0),
# # # # #         "reference_no":             pe.get("reference_no") or pe.get("sale_invoice_no", ""),
# # # # #         "reference_date":           pe.get("reference_date") or date.today().isoformat(),
# # # # #         "remarks":                  pe.get("remarks") or f"POS Payment — {mop}",
# # # # #         "mode_of_payment":          mop,
# # # # #         "docstatus":                1,
# # # # #     }

# # # # #     if paid_to:
# # # # #         payload["paid_to"] = paid_to
# # # # #     if company:
# # # # #         payload["company"] = company

# # # # #     # Link to the Sales Invoice on Frappe
# # # # #     if frappe_inv:
# # # # #         payload["references"] = [{
# # # # #             "reference_doctype": "Sales Invoice",
# # # # #             "reference_name":    frappe_inv,
# # # # #             "allocated_amount":  amount,
# # # # #         }]

# # # # #     return payload


# # # # # # =============================================================================
# # # # # # PUSH ONE PAYMENT ENTRY
# # # # # # =============================================================================

# # # # # def _push_payment_entry(pe: dict, api_key: str, api_secret: str,
# # # # #                         defaults: dict, host: str) -> str | None:
# # # # #     """
# # # # #     Posts one payment entry to Frappe.
# # # # #     Returns Frappe's PAY-xxxxx name on success, None on failure.
# # # # #     """
# # # # #     pe_id  = pe["id"]
# # # # #     inv_no = pe.get("sale_invoice_no", str(pe_id))

# # # # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()
# # # # #     if not frappe_inv:
# # # # #         log.warning("Payment %d — Sales Invoice not yet on Frappe, skipping.", pe_id)
# # # # #         return None

# # # # #     payload = _build_payload(pe, defaults, api_key, api_secret, host)

# # # # #     url = f"{host}/api/resource/Payment%20Entry"
# # # # #     req = urllib.request.Request(
# # # # #         url=url,
# # # # #         data=json.dumps(payload).encode("utf-8"),
# # # # #         method="POST",
# # # # #         headers={
# # # # #             "Content-Type":  "application/json",
# # # # #             "Accept":        "application/json",
# # # # #             "Authorization": f"token {api_key}:{api_secret}",
# # # # #         },
# # # # #     )

# # # # #     try:
# # # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
# # # # #             data = json.loads(resp.read().decode())
# # # # #             name = (data.get("data") or {}).get("name", "")
# # # # #             log.info("✅ Payment Entry %d → Frappe %s  [%s  %s %.2f]",
# # # # #                      pe_id, name, inv_no,
# # # # #                      pe.get("currency", ""), float(pe.get("paid_amount", 0)))
# # # # #             return name or "SYNCED"

# # # # #     except urllib.error.HTTPError as e:
# # # # #         try:
# # # # #             err = json.loads(e.read().decode())
# # # # #             msg = (err.get("exception") or err.get("message") or
# # # # #                    str(err.get("_server_messages", "")) or f"HTTP {e.code}")
# # # # #         except Exception:
# # # # #             msg = f"HTTP {e.code}"

# # # # #         if e.code == 409:
# # # # #             log.info("Payment %d already on Frappe (409) — marking synced.", pe_id)
# # # # #             return "DUPLICATE"

# # # # #         log.error("❌ Payment Entry %d  HTTP %s: %s", pe_id, e.code, msg)
# # # # #         return None

# # # # #     except urllib.error.URLError as e:
# # # # #         log.warning("Network error pushing payment %d: %s", pe_id, e.reason)
# # # # #         return None

# # # # #     except Exception as e:
# # # # #         log.error("Unexpected error pushing payment %d: %s", pe_id, e)
# # # # #         return None


# # # # # # =============================================================================
# # # # # # PUBLIC — push all unsynced payment entries
# # # # # # =============================================================================

# # # # # def push_unsynced_payment_entries() -> dict:
# # # # #     """
# # # # #     1. Refresh frappe_invoice_ref from parent sales that were confirmed.
# # # # #     2. Push each unsynced payment entry to Frappe.
# # # # #     3. Mark synced with the returned PAY-xxxxx ref.
# # # # #     """
# # # # #     result = {"pushed": 0, "failed": 0, "skipped": 0, "total": 0}

# # # # #     api_key, api_secret = _get_credentials()
# # # # #     if not api_key or not api_secret:
# # # # #         log.warning("No credentials — skipping payment entry sync.")
# # # # #         return result

# # # # #     host     = _get_host()
# # # # #     defaults = _get_defaults()

# # # # #     # First: pull frappe_refs from confirmed invoices into pending payment entries
# # # # #     updated = refresh_frappe_refs()
# # # # #     if updated:
# # # # #         log.info("Refreshed frappe_invoice_ref on %d payment entry(ies).", updated)

# # # # #     entries = get_unsynced_payment_entries()
# # # # #     result["total"] = len(entries)

# # # # #     if not entries:
# # # # #         log.debug("No unsynced payment entries.")
# # # # #         return result

# # # # #     log.info("Pushing %d payment entry(ies) to Frappe…", len(entries))

# # # # #     for pe in entries:
# # # # #         frappe_name = _push_payment_entry(pe, api_key, api_secret, defaults, host)
# # # # #         if frappe_name:
# # # # #             mark_payment_synced(pe["id"], frappe_name)
# # # # #             result["pushed"] += 1
# # # # #         elif frappe_name is None:
# # # # #             # None = permanent skip (no frappe_inv yet), not a real failure
# # # # #             result["skipped"] += 1
# # # # #         else:
# # # # #             result["failed"] += 1

# # # # #         time.sleep(3)   # rate limit — 20/min max

# # # # #     log.info("Payment sync done — ✅ %d pushed  ❌ %d failed  ⏭ %d skipped",
# # # # #              result["pushed"], result["failed"], result["skipped"])
# # # # #     return result


# # # # # # =============================================================================
# # # # # # BACKGROUND DAEMON THREAD
# # # # # # =============================================================================

# # # # # def _sync_loop():
# # # # #     log.info("Payment entry sync daemon started (interval=%ds).", SYNC_INTERVAL)
# # # # #     while True:
# # # # #         if _sync_lock.acquire(blocking=False):
# # # # #             try:
# # # # #                 push_unsynced_payment_entries()
# # # # #             except Exception as e:
# # # # #                 log.error("Payment sync cycle error: %s", e)
# # # # #             finally:
# # # # #                 _sync_lock.release()
# # # # #         else:
# # # # #             log.debug("Previous payment sync still running — skipping.")
# # # # #         time.sleep(SYNC_INTERVAL)


# # # # # def start_payment_sync_daemon() -> threading.Thread:
# # # # #     """Non-blocking — safe to call from MainWindow.__init__."""
# # # # #     global _sync_thread
# # # # #     if _sync_thread and _sync_thread.is_alive():
# # # # #         return _sync_thread
# # # # #     t = threading.Thread(target=_sync_loop, daemon=True, name="PaymentSyncDaemon")
# # # # #     t.start()
# # # # #     _sync_thread = t
# # # # #     log.info("Payment entry sync daemon started.")
# # # # #     return t


# # # # # # =============================================================================
# # # # # # DEBUG
# # # # # # =============================================================================

# # # # # if __name__ == "__main__":
# # # # #     logging.basicConfig(level=logging.INFO,
# # # # #                         format="%(asctime)s [%(levelname)s] %(message)s")
# # # # #     print("Running one payment entry sync cycle...")
# # # # #     r = push_unsynced_payment_entries()
# # # # #     print(f"\nResult: {r['pushed']} pushed, {r['failed']} failed, "
# # # # #           f"{r['skipped']} skipped (of {r['total']} total)")
# # # # # =============================================================================
# # # # # services/payment_entry_service.py
# # # # #
# # # # # Manages local payment_entries table and syncs them to Frappe.
# # # # #
# # # # # FLOW:
# # # # #   1. When a sale is saved locally → create_payment_entry() stores it locally
# # # # #      with synced=0
# # # # #   2. When the Sales Invoice is confirmed on Frappe (frappe_ref is set) →
# # # # #      push_unsynced_payment_entries() pushes the Payment Entry to Frappe
# # # # #   3. Frappe returns a PAY-xxxxx ref → stored as frappe_payment_ref, synced=1
# # # # #
# # # # # PAYLOAD SENT TO FRAPPE:
# # # # #   POST /api/resource/Payment Entry
# # # # #   {
# # # # #     "doctype":              "Payment Entry",
# # # # #     "payment_type":         "Receive",
# # # # #     "party_type":           "Customer",
# # # # #     "party":                "Cathy",
# # # # #     "paid_to":              "Cash ZWG - H",
# # # # #     "paid_to_account_currency": "USD",
# # # # #     "paid_amount":          32.45,
# # # # #     "received_amount":      32.45,
# # # # #     "source_exchange_rate": 1.0,
# # # # #     "reference_no":         "ACC-SINV-2026-00034",
# # # # #     "reference_date":       "2026-03-19",
# # # # #     "remarks":              "POS Payment — Cash",
# # # # #     "docstatus":            1,
# # # # #     "references": [{
# # # # #         "reference_doctype": "Sales Invoice",
# # # # #         "reference_name":    "ACC-SINV-2026-00565",
# # # # #         "allocated_amount":  32.45
# # # # #     }]
# # # # #   }
# # # # # =============================================================================

# # # # from __future__ import annotations

# # # # import json
# # # # import logging
# # # # import time
# # # # import threading
# # # # import urllib.request
# # # # import urllib.error
# # # # from datetime import date

# # # # log = logging.getLogger("PaymentEntry")

# # # # SYNC_INTERVAL   = 60      # seconds between auto-sync cycles
# # # # REQUEST_TIMEOUT = 30

# # # # # Exchange rate cache: "FROM::TO::DATE" → float
# # # # _RATE_CACHE: dict[str, float] = {}


# # # # def _get_exchange_rate(from_currency: str, to_currency: str,
# # # #                        transaction_date: str,
# # # #                        api_key: str, api_secret: str, host: str) -> float:
# # # #     """
# # # #     Fetch live exchange rate from Frappe.
# # # #     Returns 1.0 for same currency, 0.0 if fetch fails (Frappe uses its own rate).
# # # #     """
# # # #     if not from_currency or from_currency.upper() == to_currency.upper():
# # # #         return 1.0

# # # #     cache_key = f"{from_currency.upper()}::{to_currency.upper()}::{transaction_date}"
# # # #     if cache_key in _RATE_CACHE:
# # # #         return _RATE_CACHE[cache_key]

# # # #     try:
# # # #         import urllib.parse
# # # #         url = (
# # # #             f"{host}/api/method/erpnext.setup.utils.get_exchange_rate"
# # # #             f"?from_currency={urllib.parse.quote(from_currency)}"
# # # #             f"&to_currency={urllib.parse.quote(to_currency)}"
# # # #             f"&transaction_date={transaction_date}"
# # # #         )
# # # #         req = urllib.request.Request(url)
# # # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # # #             data = json.loads(r.read().decode())
# # # #             rate = float(data.get("message") or data.get("result") or 0)
# # # #             if rate > 0:
# # # #                 _RATE_CACHE[cache_key] = rate
# # # #                 log.debug("Rate %s→%s on %s: %.6f", from_currency, to_currency, transaction_date, rate)
# # # #                 return rate
# # # #     except Exception as e:
# # # #         log.debug("Rate fetch failed (%s→%s): %s", from_currency, to_currency, e)

# # # #     return 0.0

# # # # _sync_lock:   threading.Lock          = threading.Lock()
# # # # _sync_thread: threading.Thread | None = None

# # # # # Method → Frappe Mode of Payment name
# # # # _METHOD_MAP = {
# # # #     "CASH":     "Cash",
# # # #     "CARD":     "Credit Card",
# # # #     "C / CARD": "Credit Card",
# # # #     "EFTPOS":   "Credit Card",
# # # #     "CHECK":    "Cheque",
# # # #     "CHEQUE":   "Cheque",
# # # #     "MOBILE":   "Mobile Money",
# # # #     "CREDIT":   "Credit",
# # # #     "TRANSFER": "Bank Transfer",
# # # # }


# # # # # =============================================================================
# # # # # CREDENTIALS / HOST / DEFAULTS
# # # # # =============================================================================

# # # # def _get_credentials() -> tuple[str, str]:
# # # #     try:
# # # #         from services.auth_service import get_session
# # # #         s = get_session()
# # # #         if s.get("api_key") and s.get("api_secret"):
# # # #             return s["api_key"], s["api_secret"]
# # # #     except Exception:
# # # #         pass
# # # #     try:
# # # #         from database.db import get_connection
# # # #         conn = get_connection(); cur = conn.cursor()
# # # #         cur.execute("SELECT api_key, api_secret FROM company_defaults WHERE id = 1")
# # # #         row = cur.fetchone(); conn.close()
# # # #         if row and row[0] and row[1]:
# # # #             return row[0], row[1]
# # # #     except Exception:
# # # #         pass
# # # #     import os
# # # #     return os.environ.get("HAVANO_API_KEY", ""), os.environ.get("HAVANO_API_SECRET", "")


# # # # def _get_host() -> str:
# # # #     try:
# # # #         from models.company_defaults import get_defaults
# # # #         host = (get_defaults() or {}).get("server_api_host", "").strip().rstrip("/")
# # # #         if host:
# # # #             return host
# # # #     except Exception:
# # # #         pass
# # # #     return "https://apk.havano.cloud"


# # # # def _get_defaults() -> dict:
# # # #     try:
# # # #         from models.company_defaults import get_defaults
# # # #         return get_defaults() or {}
# # # #     except Exception:
# # # #         return {}


# # # # # =============================================================================
# # # # # GL ACCOUNT RESOLVER  (which account to credit for each payment method)
# # # # # =============================================================================

# # # # _ACCOUNT_CACHE: dict[str, str] = {}


# # # # def _resolve_paid_to_account(mop_name: str, company: str, currency: str,
# # # #                               api_key: str, api_secret: str, host: str) -> str:
# # # #     """
# # # #     Looks up the GL account for a Mode of Payment from Frappe.
# # # #     Tries to match by currency if multiple accounts exist for the company.
# # # #     Falls back to server_pos_account in company_defaults.
# # # #     """
# # # #     cache_key = f"{mop_name}::{company}::{currency}"
# # # #     if cache_key in _ACCOUNT_CACHE:
# # # #         return _ACCOUNT_CACHE[cache_key]

# # # #     try:
# # # #         import urllib.parse
# # # #         url = (f"{host}/api/resource/Mode%20of%20Payment/"
# # # #                f"{urllib.parse.quote(mop_name)}?fields=[\"accounts\"]")
# # # #         req = urllib.request.Request(url)
# # # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # # #             data     = json.loads(r.read().decode())
# # # #             accounts = (data.get("data") or {}).get("accounts", [])

# # # #         company_accts = [a for a in accounts
# # # #                          if not company or a.get("company") == company]

# # # #         # Prefer account whose name contains the currency code
# # # #         matched = ""
# # # #         if currency:
# # # #             for a in company_accts:
# # # #                 if currency.upper() in (a.get("default_account") or "").upper():
# # # #                     matched = a["default_account"]; break

# # # #         if not matched and company_accts:
# # # #             matched = company_accts[0].get("default_account", "")

# # # #         if matched:
# # # #             _ACCOUNT_CACHE[cache_key] = matched
# # # #             return matched

# # # #     except Exception as e:
# # # #         log.debug("MOP account lookup failed for '%s': %s", mop_name, e)

# # # #     # Fallback
# # # #     fallback = _get_defaults().get("server_pos_account", "").strip()
# # # #     if fallback:
# # # #         _ACCOUNT_CACHE[cache_key] = fallback
# # # #         return fallback

# # # #     log.warning("No GL account for MOP '%s' currency=%s — Payment Entry may fail.",
# # # #                 mop_name, currency)
# # # #     return ""


# # # # # =============================================================================
# # # # # LOCAL DB  — create / read / update payment_entries
# # # # # =============================================================================

# # # # def create_payment_entry(sale: dict, override_rate: float = None,
# # # #                          override_account: str = None) -> int | None:
# # # #     """
# # # #     Called immediately after a sale is saved locally.
# # # #     Stores a payment_entry row with synced=0.
# # # #     Returns the new payment_entry id, or None on error.

# # # #     Will only create the entry once per sale (idempotent).
# # # #     """
# # # #     from database.db import get_connection
# # # #     conn = get_connection(); cur = conn.cursor()

# # # #     # Idempotency: don't create twice for the same sale
# # # #     cur.execute("SELECT id FROM payment_entries WHERE sale_id = ?", (sale["id"],))
# # # #     if cur.fetchone():
# # # #         conn.close()
# # # #         return None

# # # #     customer   = (sale.get("customer_name") or "default").strip()
# # # #     currency   = (sale.get("currency")      or "USD").strip().upper()
# # # #     amount     = float(sale.get("total")    or 0)
# # # #     inv_no     = sale.get("invoice_no", "")
# # # #     inv_date   = sale.get("invoice_date") or date.today().isoformat()
# # # #     method     = str(sale.get("method", "CASH")).upper().strip()
# # # #     mop        = _METHOD_MAP.get(method, "Cash")

# # # #     # Use override rate (from split) or fetch from Frappe
# # # #     if override_rate is not None:
# # # #         exch_rate = override_rate
# # # #     else:
# # # #         try:
# # # #             api_key, api_secret = _get_credentials()
# # # #             host = _get_host()
# # # #             defaults = _get_defaults()
# # # #             company_currency = defaults.get("server_company_currency", "USD").strip().upper() or "USD"
# # # #             exch_rate = _get_exchange_rate(
# # # #                 currency, company_currency, inv_date, api_key, api_secret, host
# # # #             ) if currency != company_currency else 1.0
# # # #         except Exception:
# # # #             exch_rate = 1.0

# # # #     cur.execute("""
# # # #         INSERT INTO payment_entries (
# # # #             sale_id, sale_invoice_no, frappe_invoice_ref,
# # # #             party, party_name,
# # # #             paid_amount, received_amount, source_exchange_rate,
# # # #             paid_to_account_currency, currency,
# # # #             mode_of_payment,
# # # #             reference_no, reference_date,
# # # #             remarks, synced
# # # #         ) OUTPUT INSERTED.id
# # # #         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # # #     """, (
# # # #         sale["id"], inv_no,
# # # #         sale.get("frappe_ref") or None,
# # # #         customer, customer,
# # # #         amount, amount, exch_rate or 1.0,
# # # #         currency, currency,
# # # #         mop,
# # # #         inv_no, inv_date,
# # # #         f"POS Payment — {mop}",
# # # #     ))
# # # #     new_id = int(cur.fetchone()[0])
# # # #     conn.commit(); conn.close()
# # # #     log.debug("Payment entry %d created locally for sale %s", new_id, inv_no)
# # # #     return new_id


# # # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # # #     """
# # # #     Called when cashier uses Split payment.
# # # #     Creates one payment_entry row per currency in splits list.
# # # #     splits = [{"mode": "CASH", "currency": "USD", "amount": 5.0,
# # # #                "rate": 1.0, "base_amount": 5.0, "account": "Cash - AT"}, ...]
# # # #     Returns list of new payment_entry ids.
# # # #     """
# # # #     ids = []
# # # #     for split in splits:
# # # #         if not split.get("amount") or float(split["amount"]) <= 0:
# # # #             continue
# # # #         # Build a sale-like dict with the split's currency and amount
# # # #         split_sale = dict(sale)
# # # #         split_sale["currency"]      = split.get("currency", "USD")
# # # #         split_sale["total"]         = float(split.get("amount", 0))
# # # #         split_sale["method"]        = split.get("mode", "CASH")
# # # #         # Override exchange rate from split data
# # # #         new_id = create_payment_entry(
# # # #             split_sale,
# # # #             override_rate=float(split.get("rate", 1.0)),
# # # #             override_account=split.get("account", ""),
# # # #         )
# # # #         if new_id:
# # # #             ids.append(new_id)
# # # #     return ids


# # # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # # #     """
# # # #     Creates one payment_entry per currency from a split payment.
# # # #     Groups splits by currency, sums amounts, creates one entry each.
# # # #     Returns list of created payment_entry ids.
# # # #     """
# # # #     from datetime import date as _date

# # # #     # Group by currency
# # # #     by_currency: dict[str, dict] = {}
# # # #     for s in splits:
# # # #         curr = s.get("account_currency", "USD").upper()
# # # #         if curr not in by_currency:
# # # #             by_currency[curr] = {
# # # #                 "currency":      curr,
# # # #                 "paid_amount":   0.0,
# # # #                 "base_value":    0.0,
# # # #                 "rate":          s.get("rate", 1.0),
# # # #                 "account_name":  s.get("account_name", ""),
# # # #                 "mode":          s.get("mode", "Cash"),
# # # #             }
# # # #         by_currency[curr]["paid_amount"] += s.get("amount_paid", 0.0)
# # # #         by_currency[curr]["base_value"]  += s.get("base_value",  0.0)

# # # #     ids = []
# # # #     inv_no   = sale.get("invoice_no", "")
# # # #     inv_date = sale.get("invoice_date") or _date.today().isoformat()
# # # #     customer = (sale.get("customer_name") or "default").strip()

# # # #     from database.db import get_connection
# # # #     conn = get_connection(); cur = conn.cursor()

# # # #     for curr, grp in by_currency.items():
# # # #         # Idempotency: skip if already exists for this sale+currency
# # # #         cur.execute(
# # # #             "SELECT id FROM payment_entries WHERE sale_id=? AND currency=?",
# # # #             (sale["id"], curr)
# # # #         )
# # # #         if cur.fetchone():
# # # #             continue

# # # #         mop = _METHOD_MAP.get(grp["mode"].upper(), "Cash")

# # # #         cur.execute("""
# # # #             INSERT INTO payment_entries (
# # # #                 sale_id, sale_invoice_no, frappe_invoice_ref,
# # # #                 party, party_name,
# # # #                 paid_amount, received_amount, source_exchange_rate,
# # # #                 paid_to_account_currency, currency,
# # # #                 paid_to,
# # # #                 mode_of_payment,
# # # #                 reference_no, reference_date,
# # # #                 remarks, synced
# # # #             ) OUTPUT INSERTED.id
# # # #             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # # #         """, (
# # # #             sale["id"], inv_no,
# # # #             sale.get("frappe_ref") or None,
# # # #             customer, customer,
# # # #             grp["paid_amount"],
# # # #             grp["base_value"],
# # # #             float(grp["rate"] or 1.0),
# # # #             curr, curr,
# # # #             grp["account_name"],
# # # #             mop,
# # # #             inv_no, inv_date,
# # # #             f"POS Split Payment — {mop} ({curr})",
# # # #         ))
# # # #         new_id = int(cur.fetchone()[0])
# # # #         ids.append(new_id)
# # # #         log.debug("Split payment entry %d created: %s %.2f %s",
# # # #                   new_id, curr, grp["paid_amount"], inv_no)

# # # #     conn.commit(); conn.close()
# # # #     return ids


# # # # def get_unsynced_payment_entries() -> list[dict]:
# # # #     """Returns payment entries that are ready to push (synced=0)."""
# # # #     from database.db import get_connection, fetchall_dicts
# # # #     conn = get_connection(); cur = conn.cursor()
# # # #     cur.execute("""
# # # #         SELECT pe.*, s.frappe_ref AS sale_frappe_ref
# # # #         FROM payment_entries pe
# # # #         LEFT JOIN sales s ON s.id = pe.sale_id
# # # #         WHERE pe.synced = 0
# # # #           AND (pe.frappe_invoice_ref IS NOT NULL
# # # #                OR s.frappe_ref IS NOT NULL)
# # # #         ORDER BY pe.id
# # # #     """)
# # # #     rows = fetchall_dicts(cur); conn.close()
# # # #     return rows


# # # # def mark_payment_synced(pe_id: int, frappe_payment_ref: str = "") -> None:
# # # #     from database.db import get_connection
# # # #     conn = get_connection(); cur = conn.cursor()
# # # #     cur.execute(
# # # #         "UPDATE payment_entries SET synced=1, frappe_payment_ref=? WHERE id=?",
# # # #         (frappe_payment_ref or None, pe_id)
# # # #     )
# # # #     # Also update the sales row
# # # #     cur.execute("""
# # # #         UPDATE sales SET payment_entry_ref=?, payment_synced=1
# # # #         WHERE id = (SELECT sale_id FROM payment_entries WHERE id=?)
# # # #     """, (frappe_payment_ref or None, pe_id))
# # # #     conn.commit(); conn.close()


# # # # def refresh_frappe_refs() -> int:
# # # #     """
# # # #     For payment entries that have no frappe_invoice_ref yet, copy it from
# # # #     the parent sale's frappe_ref. Call this before pushing payments.
# # # #     Returns count updated.
# # # #     """
# # # #     from database.db import get_connection
# # # #     conn = get_connection(); cur = conn.cursor()
# # # #     cur.execute("""
# # # #         UPDATE pe
# # # #         SET pe.frappe_invoice_ref = s.frappe_ref
# # # #         FROM payment_entries pe
# # # #         JOIN sales s ON s.id = pe.sale_id
# # # #         WHERE pe.synced = 0
# # # #           AND (pe.frappe_invoice_ref IS NULL OR pe.frappe_invoice_ref = '')
# # # #           AND s.frappe_ref IS NOT NULL AND s.frappe_ref != ''
# # # #     """)
# # # #     count = cur.rowcount
# # # #     conn.commit(); conn.close()
# # # #     return count


# # # # # =============================================================================
# # # # # BUILD FRAPPE PAYLOAD
# # # # # =============================================================================

# # # # def _build_payload(pe: dict, defaults: dict,
# # # #                    api_key: str, api_secret: str, host: str) -> dict:
# # # #     company  = defaults.get("server_company", "")
# # # #     currency = (pe.get("currency") or pe.get("paid_to_account_currency") or "USD").upper()
# # # #     mop      = pe.get("mode_of_payment") or "Cash"
# # # #     amount   = float(pe.get("paid_amount") or 0)
# # # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()

# # # #     # Use local gl_accounts table first (synced from Frappe)
# # # #     paid_to          = (pe.get("paid_to") or "").strip()
# # # #     paid_to_currency = currency
# # # #     if not paid_to:
# # # #         try:
# # # #             from models.gl_account import get_account_for_payment
# # # #             acct = get_account_for_payment(currency, company)
# # # #             if acct:
# # # #                 paid_to          = acct["name"]
# # # #                 paid_to_currency = acct["account_currency"]
# # # #         except Exception as _e:
# # # #             log.debug("gl_account lookup failed: %s", _e)

# # # #     # Fallback to live Frappe lookup
# # # #     if not paid_to:
# # # #         paid_to = _resolve_paid_to_account(mop, company, currency, api_key, api_secret, host)

# # # #     # Use local exchange rate if not stored
# # # #     exch_rate = float(pe.get("source_exchange_rate") or 1.0)
# # # #     if exch_rate == 1.0 and currency not in ("USD", ""):
# # # #         try:
# # # #             from models.exchange_rate import get_rate
# # # #             stored = get_rate(currency, "USD")
# # # #             if stored:
# # # #                 exch_rate = stored
# # # #         except Exception:
# # # #             pass

# # # #     payload = {
# # # #         "doctype":                  "Payment Entry",
# # # #         "payment_type":             "Receive",
# # # #         "party_type":               "Customer",
# # # #         "party":                    pe.get("party") or "default",
# # # #         "party_name":               pe.get("party_name") or "default",
# # # #         "paid_to_account_currency": paid_to_currency,
# # # #         "paid_amount":              amount,
# # # #         "received_amount":          amount,
# # # #         "source_exchange_rate":     exch_rate,
# # # #         "reference_no":             pe.get("reference_no") or pe.get("sale_invoice_no", ""),
# # # #         "reference_date":           pe.get("reference_date") or date.today().isoformat(),
# # # #         "remarks":                  pe.get("remarks") or f"POS Payment — {mop}",
# # # #         "mode_of_payment":          mop,
# # # #         "docstatus":                1,
# # # #     }

# # # #     if paid_to:
# # # #         payload["paid_to"] = paid_to
# # # #     if company:
# # # #         payload["company"] = company

# # # #     # Link to the Sales Invoice on Frappe
# # # #     if frappe_inv:
# # # #         payload["references"] = [{
# # # #             "reference_doctype": "Sales Invoice",
# # # #             "reference_name":    frappe_inv,
# # # #             "allocated_amount":  amount,
# # # #         }]

# # # #     return payload


# # # # # =============================================================================
# # # # # PUSH ONE PAYMENT ENTRY
# # # # # =============================================================================

# # # # def _push_payment_entry(pe: dict, api_key: str, api_secret: str,
# # # #                         defaults: dict, host: str) -> str | None:
# # # #     """
# # # #     Posts one payment entry to Frappe.
# # # #     Returns Frappe's PAY-xxxxx name on success, None on failure.
# # # #     """
# # # #     pe_id  = pe["id"]
# # # #     inv_no = pe.get("sale_invoice_no", str(pe_id))

# # # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()
# # # #     if not frappe_inv:
# # # #         log.warning("Payment %d — Sales Invoice not yet on Frappe, skipping.", pe_id)
# # # #         return None

# # # #     payload = _build_payload(pe, defaults, api_key, api_secret, host)

# # # #     url = f"{host}/api/resource/Payment%20Entry"
# # # #     req = urllib.request.Request(
# # # #         url=url,
# # # #         data=json.dumps(payload).encode("utf-8"),
# # # #         method="POST",
# # # #         headers={
# # # #             "Content-Type":  "application/json",
# # # #             "Accept":        "application/json",
# # # #             "Authorization": f"token {api_key}:{api_secret}",
# # # #         },
# # # #     )

# # # #     try:
# # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
# # # #             data = json.loads(resp.read().decode())
# # # #             name = (data.get("data") or {}).get("name", "")
# # # #             log.info("✅ Payment Entry %d → Frappe %s  [%s  %s %.2f]",
# # # #                      pe_id, name, inv_no,
# # # #                      pe.get("currency", ""), float(pe.get("paid_amount", 0)))
# # # #             return name or "SYNCED"

# # # #     except urllib.error.HTTPError as e:
# # # #         try:
# # # #             err = json.loads(e.read().decode())
# # # #             msg = (err.get("exception") or err.get("message") or
# # # #                    str(err.get("_server_messages", "")) or f"HTTP {e.code}")
# # # #         except Exception:
# # # #             msg = f"HTTP {e.code}"

# # # #         if e.code == 409:
# # # #             log.info("Payment %d already on Frappe (409) - marking synced.", pe_id)
# # # #             return "DUPLICATE"

# # # #         # Invoice already paid (is_pos:1 on old invoices) - stop retrying
# # # #         if e.code == 417:
# # # #             _perma = ("already been fully paid", "already paid", "fully paid")
# # # #             if any(p in msg.lower() for p in _perma):
# # # #                 log.info("Payment %d - invoice already paid on Frappe, marking synced.", pe_id)
# # # #                 return "ALREADY_PAID"

# # # #         log.error("FAIL Payment Entry %d  HTTP %s: %s", pe_id, e.code, msg)
# # # #         return None

# # # #     except urllib.error.URLError as e:
# # # #         log.warning("Network error pushing payment %d: %s", pe_id, e.reason)
# # # #         return None

# # # #     except Exception as e:
# # # #         log.error("Unexpected error pushing payment %d: %s", pe_id, e)
# # # #         return None


# # # # # =============================================================================
# # # # # PUBLIC — push all unsynced payment entries
# # # # # =============================================================================

# # # # def push_unsynced_payment_entries() -> dict:
# # # #     """
# # # #     1. Refresh frappe_invoice_ref from parent sales that were confirmed.
# # # #     2. Push each unsynced payment entry to Frappe.
# # # #     3. Mark synced with the returned PAY-xxxxx ref.
# # # #     """
# # # #     result = {"pushed": 0, "failed": 0, "skipped": 0, "total": 0}

# # # #     api_key, api_secret = _get_credentials()
# # # #     if not api_key or not api_secret:
# # # #         log.warning("No credentials — skipping payment entry sync.")
# # # #         return result

# # # #     host     = _get_host()
# # # #     defaults = _get_defaults()

# # # #     # First: pull frappe_refs from confirmed invoices into pending payment entries
# # # #     updated = refresh_frappe_refs()
# # # #     if updated:
# # # #         log.info("Refreshed frappe_invoice_ref on %d payment entry(ies).", updated)

# # # #     entries = get_unsynced_payment_entries()
# # # #     result["total"] = len(entries)

# # # #     if not entries:
# # # #         log.debug("No unsynced payment entries.")
# # # #         return result

# # # #     log.info("Pushing %d payment entry(ies) to Frappe…", len(entries))

# # # #     for pe in entries:
# # # #         frappe_name = _push_payment_entry(pe, api_key, api_secret, defaults, host)
# # # #         if frappe_name:
# # # #             mark_payment_synced(pe["id"], frappe_name)
# # # #             result["pushed"] += 1
# # # #         elif frappe_name is None:
# # # #             # None = permanent skip (no frappe_inv yet), not a real failure
# # # #             result["skipped"] += 1
# # # #         else:
# # # #             result["failed"] += 1

# # # #         time.sleep(3)   # rate limit — 20/min max

# # # #     log.info("Payment sync done — ✅ %d pushed  ❌ %d failed  ⏭ %d skipped",
# # # #              result["pushed"], result["failed"], result["skipped"])
# # # #     return result


# # # # # =============================================================================
# # # # # BACKGROUND DAEMON THREAD
# # # # # =============================================================================

# # # # def _sync_loop():
# # # #     log.info("Payment entry sync daemon started (interval=%ds).", SYNC_INTERVAL)
# # # #     while True:
# # # #         if _sync_lock.acquire(blocking=False):
# # # #             try:
# # # #                 push_unsynced_payment_entries()
# # # #             except Exception as e:
# # # #                 log.error("Payment sync cycle error: %s", e)
# # # #             finally:
# # # #                 _sync_lock.release()
# # # #         else:
# # # #             log.debug("Previous payment sync still running — skipping.")
# # # #         time.sleep(SYNC_INTERVAL)


# # # # def start_payment_sync_daemon() -> threading.Thread:
# # # #     """Non-blocking — safe to call from MainWindow.__init__."""
# # # #     global _sync_thread
# # # #     if _sync_thread and _sync_thread.is_alive():
# # # #         return _sync_thread
# # # #     t = threading.Thread(target=_sync_loop, daemon=True, name="PaymentSyncDaemon")
# # # #     t.start()
# # # #     _sync_thread = t
# # # #     log.info("Payment entry sync daemon started.")
# # # #     return t


# # # # # =============================================================================
# # # # # DEBUG
# # # # # =============================================================================

# # # # if __name__ == "__main__":
# # # #     logging.basicConfig(level=logging.INFO,
# # # #                         format="%(asctime)s [%(levelname)s] %(message)s")
# # # #     print("Running one payment entry sync cycle...")
# # # #     r = push_unsynced_payment_entries()
# # # #     print(f"\nResult: {r['pushed']} pushed, {r['failed']} failed, "
# # # #           f"{r['skipped']} skipped (of {r['total']} total)")

# # # # =============================================================================
# # # # services/payment_entry_service.py
# # # #
# # # # Manages local payment_entries table and syncs them to Frappe.
# # # #
# # # # FLOW:
# # # #   1. When a sale is saved locally → create_payment_entry() stores it locally
# # # #      with synced=0
# # # #   2. When the Sales Invoice is confirmed on Frappe (frappe_ref is set) →
# # # #      push_unsynced_payment_entries() pushes the Payment Entry to Frappe
# # # #   3. Frappe returns a PAY-xxxxx ref → stored as frappe_payment_ref, synced=1
# # # #
# # # # PAYLOAD SENT TO FRAPPE:
# # # #   POST /api/resource/Payment Entry
# # # #   {
# # # #     "doctype":              "Payment Entry",
# # # #     "payment_type":         "Receive",
# # # #     "party_type":           "Customer",
# # # #     "party":                "Cathy",
# # # #     "paid_to":              "Cash ZWG - H",
# # # #     "paid_to_account_currency": "USD",
# # # #     "paid_amount":          32.45,
# # # #     "received_amount":      32.45,
# # # #     "source_exchange_rate": 1.0,
# # # #     "reference_no":         "ACC-SINV-2026-00034",
# # # #     "reference_date":       "2026-03-19",
# # # #     "remarks":              "POS Payment — Cash",
# # # #     "docstatus":            1,
# # # #     "references": [{
# # # #         "reference_doctype": "Sales Invoice",
# # # #         "reference_name":    "ACC-SINV-2026-00565",
# # # #         "allocated_amount":  32.45
# # # #     }]
# # # #   }
# # # # =============================================================================

# # # from __future__ import annotations

# # # import json
# # # import logging
# # # import time
# # # import threading
# # # import urllib.request
# # # import urllib.error
# # # from datetime import date

# # # log = logging.getLogger("PaymentEntry")

# # # SYNC_INTERVAL   = 60      # seconds between auto-sync cycles
# # # REQUEST_TIMEOUT = 30

# # # # Exchange rate cache: "FROM::TO::DATE" → float
# # # _RATE_CACHE: dict[str, float] = {}


# # # def _get_exchange_rate(from_currency: str, to_currency: str,
# # #                        transaction_date: str,
# # #                        api_key: str, api_secret: str, host: str) -> float:
# # #     """
# # #     Fetch live exchange rate from Frappe.
# # #     Returns 1.0 for same currency, 0.0 if fetch fails (Frappe uses its own rate).
# # #     """
# # #     if not from_currency or from_currency.upper() == to_currency.upper():
# # #         return 1.0

# # #     cache_key = f"{from_currency.upper()}::{to_currency.upper()}::{transaction_date}"
# # #     if cache_key in _RATE_CACHE:
# # #         return _RATE_CACHE[cache_key]

# # #     try:
# # #         import urllib.parse
# # #         url = (
# # #             f"{host}/api/method/erpnext.setup.utils.get_exchange_rate"
# # #             f"?from_currency={urllib.parse.quote(from_currency)}"
# # #             f"&to_currency={urllib.parse.quote(to_currency)}"
# # #             f"&transaction_date={transaction_date}"
# # #         )
# # #         req = urllib.request.Request(url)
# # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # #             data = json.loads(r.read().decode())
# # #             rate = float(data.get("message") or data.get("result") or 0)
# # #             if rate > 0:
# # #                 _RATE_CACHE[cache_key] = rate
# # #                 log.debug("Rate %s→%s on %s: %.6f", from_currency, to_currency, transaction_date, rate)
# # #                 return rate
# # #     except Exception as e:
# # #         log.debug("Rate fetch failed (%s→%s): %s", from_currency, to_currency, e)

# # #     return 0.0

# # # _sync_lock:   threading.Lock          = threading.Lock()
# # # _sync_thread: threading.Thread | None = None

# # # # Method → Frappe Mode of Payment name
# # # _METHOD_MAP = {
# # #     "CASH":     "Cash",
# # #     "CARD":     "Credit Card",
# # #     "C / CARD": "Credit Card",
# # #     "EFTPOS":   "Credit Card",
# # #     "CHECK":    "Cheque",
# # #     "CHEQUE":   "Cheque",
# # #     "MOBILE":   "Mobile Money",
# # #     "CREDIT":   "Credit",
# # #     "TRANSFER": "Bank Transfer",
# # # }


# # # # =============================================================================
# # # # CREDENTIALS / HOST / DEFAULTS
# # # # =============================================================================

# # # def _get_credentials() -> tuple[str, str]:
# # #     try:
# # #         from services.credentials import get_credentials
# # #         return get_credentials()
# # #     except Exception:
# # #         pass
# # #     return "", ""


# # # def _get_host() -> str:
# # #     try:
# # #         from models.company_defaults import get_defaults
# # #         host = (get_defaults() or {}).get("server_api_host", "").strip().rstrip("/")
# # #         if host:
# # #             return host
# # #     except Exception:
# # #         pass
# # #     return "https://apk.havano.cloud"


# # # def _get_defaults() -> dict:
# # #     try:
# # #         from models.company_defaults import get_defaults
# # #         return get_defaults() or {}
# # #     except Exception:
# # #         return {}


# # # # =============================================================================
# # # # GL ACCOUNT RESOLVER  (which account to credit for each payment method)
# # # # =============================================================================

# # # _ACCOUNT_CACHE: dict[str, str] = {}


# # # def _resolve_paid_to_account(mop_name: str, company: str, currency: str,
# # #                               api_key: str, api_secret: str, host: str) -> str:
# # #     """
# # #     Looks up the GL account for a Mode of Payment from Frappe.
# # #     Tries to match by currency if multiple accounts exist for the company.
# # #     Falls back to server_pos_account in company_defaults.
# # #     """
# # #     cache_key = f"{mop_name}::{company}::{currency}"
# # #     if cache_key in _ACCOUNT_CACHE:
# # #         return _ACCOUNT_CACHE[cache_key]

# # #     try:
# # #         import urllib.parse
# # #         url = (f"{host}/api/resource/Mode%20of%20Payment/"
# # #                f"{urllib.parse.quote(mop_name)}?fields=[\"accounts\"]")
# # #         req = urllib.request.Request(url)
# # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # #             data     = json.loads(r.read().decode())
# # #             accounts = (data.get("data") or {}).get("accounts", [])

# # #         company_accts = [a for a in accounts
# # #                          if not company or a.get("company") == company]

# # #         # Prefer account whose name contains the currency code
# # #         matched = ""
# # #         if currency:
# # #             for a in company_accts:
# # #                 if currency.upper() in (a.get("default_account") or "").upper():
# # #                     matched = a["default_account"]; break

# # #         if not matched and company_accts:
# # #             matched = company_accts[0].get("default_account", "")

# # #         if matched:
# # #             _ACCOUNT_CACHE[cache_key] = matched
# # #             return matched

# # #     except Exception as e:
# # #         log.debug("MOP account lookup failed for '%s': %s", mop_name, e)

# # #     # Fallback
# # #     fallback = _get_defaults().get("server_pos_account", "").strip()
# # #     if fallback:
# # #         _ACCOUNT_CACHE[cache_key] = fallback
# # #         return fallback

# # #     log.warning("No GL account for MOP '%s' currency=%s — Payment Entry may fail.",
# # #                 mop_name, currency)
# # #     return ""


# # # # =============================================================================
# # # # LOCAL DB  — create / read / update payment_entries
# # # # =============================================================================

# # # def create_payment_entry(sale: dict, override_rate: float = None,
# # #                          override_account: str = None) -> int | None:
# # #     """
# # #     Called immediately after a sale is saved locally.
# # #     Stores a payment_entry row with synced=0.
# # #     Returns the new payment_entry id, or None on error.

# # #     Will only create the entry once per sale (idempotent).
# # #     """
# # #     from database.db import get_connection
# # #     conn = get_connection(); cur = conn.cursor()

# # #     # Idempotency: don't create twice for the same sale
# # #     cur.execute("SELECT id FROM payment_entries WHERE sale_id = ?", (sale["id"],))
# # #     if cur.fetchone():
# # #         conn.close()
# # #         return None

# # #     customer   = (sale.get("customer_name") or "default").strip()
# # #     currency   = (sale.get("currency")      or "USD").strip().upper()
# # #     amount     = float(sale.get("total")    or 0)
# # #     inv_no     = sale.get("invoice_no", "")
# # #     inv_date   = sale.get("invoice_date") or date.today().isoformat()
# # #     method     = str(sale.get("method", "CASH")).upper().strip()
# # #     mop        = _METHOD_MAP.get(method, "Cash")

# # #     # Use override rate (from split) or fetch from Frappe
# # #     if override_rate is not None:
# # #         exch_rate = override_rate
# # #     else:
# # #         try:
# # #             api_key, api_secret = _get_credentials()
# # #             host = _get_host()
# # #             defaults = _get_defaults()
# # #             company_currency = defaults.get("server_company_currency", "USD").strip().upper() or "USD"
# # #             exch_rate = _get_exchange_rate(
# # #                 currency, company_currency, inv_date, api_key, api_secret, host
# # #             ) if currency != company_currency else 1.0
# # #         except Exception:
# # #             exch_rate = 1.0

# # #     cur.execute("""
# # #         INSERT INTO payment_entries (
# # #             sale_id, sale_invoice_no, frappe_invoice_ref,
# # #             party, party_name,
# # #             paid_amount, received_amount, source_exchange_rate,
# # #             paid_to_account_currency, currency,
# # #             mode_of_payment,
# # #             reference_no, reference_date,
# # #             remarks, synced
# # #         ) OUTPUT INSERTED.id
# # #         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # #     """, (
# # #         sale["id"], inv_no,
# # #         sale.get("frappe_ref") or None,
# # #         customer, customer,
# # #         amount, amount, exch_rate or 1.0,
# # #         currency, currency,
# # #         mop,
# # #         inv_no, inv_date,
# # #         f"POS Payment — {mop}",
# # #     ))
# # #     new_id = int(cur.fetchone()[0])
# # #     conn.commit(); conn.close()
# # #     log.debug("Payment entry %d created locally for sale %s", new_id, inv_no)
# # #     return new_id


# # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # #     """
# # #     Called when cashier uses Split payment.
# # #     Creates one payment_entry row per currency in splits list.
# # #     splits = [{"mode": "CASH", "currency": "USD", "amount": 5.0,
# # #                "rate": 1.0, "base_amount": 5.0, "account": "Cash - AT"}, ...]
# # #     Returns list of new payment_entry ids.
# # #     """
# # #     ids = []
# # #     for split in splits:
# # #         if not split.get("amount") or float(split["amount"]) <= 0:
# # #             continue
# # #         # Build a sale-like dict with the split's currency and amount
# # #         split_sale = dict(sale)
# # #         split_sale["currency"]      = split.get("currency", "USD")
# # #         split_sale["total"]         = float(split.get("amount", 0))
# # #         split_sale["method"]        = split.get("mode", "CASH")
# # #         # Override exchange rate from split data
# # #         new_id = create_payment_entry(
# # #             split_sale,
# # #             override_rate=float(split.get("rate", 1.0)),
# # #             override_account=split.get("account", ""),
# # #         )
# # #         if new_id:
# # #             ids.append(new_id)
# # #     return ids


# # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # #     """
# # #     Creates one payment_entry per currency from a split payment.
# # #     Groups splits by currency, sums amounts, creates one entry each.
# # #     Returns list of created payment_entry ids.
# # #     """
# # #     from datetime import date as _date

# # #     # Group by currency
# # #     by_currency: dict[str, dict] = {}
# # #     for s in splits:
# # #         curr = s.get("account_currency", "USD").upper()
# # #         if curr not in by_currency:
# # #             by_currency[curr] = {
# # #                 "currency":      curr,
# # #                 "paid_amount":   0.0,
# # #                 "base_value":    0.0,
# # #                 "rate":          s.get("rate", 1.0),
# # #                 "account_name":  s.get("account_name", ""),
# # #                 "mode":          s.get("mode", "Cash"),
# # #             }
# # #         by_currency[curr]["paid_amount"] += s.get("amount_paid", 0.0)
# # #         by_currency[curr]["base_value"]  += s.get("base_value",  0.0)

# # #     ids = []
# # #     inv_no   = sale.get("invoice_no", "")
# # #     inv_date = sale.get("invoice_date") or _date.today().isoformat()
# # #     customer = (sale.get("customer_name") or "default").strip()

# # #     from database.db import get_connection
# # #     conn = get_connection(); cur = conn.cursor()

# # #     for curr, grp in by_currency.items():
# # #         # Idempotency: skip if already exists for this sale+currency
# # #         cur.execute(
# # #             "SELECT id FROM payment_entries WHERE sale_id=? AND currency=?",
# # #             (sale["id"], curr)
# # #         )
# # #         if cur.fetchone():
# # #             continue

# # #         mop = _METHOD_MAP.get(grp["mode"].upper(), "Cash")

# # #         cur.execute("""
# # #             INSERT INTO payment_entries (
# # #                 sale_id, sale_invoice_no, frappe_invoice_ref,
# # #                 party, party_name,
# # #                 paid_amount, received_amount, source_exchange_rate,
# # #                 paid_to_account_currency, currency,
# # #                 paid_to,
# # #                 mode_of_payment,
# # #                 reference_no, reference_date,
# # #                 remarks, synced
# # #             ) OUTPUT INSERTED.id
# # #             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # #         """, (
# # #             sale["id"], inv_no,
# # #             sale.get("frappe_ref") or None,
# # #             customer, customer,
# # #             grp["paid_amount"],
# # #             grp["base_value"],
# # #             float(grp["rate"] or 1.0),
# # #             curr, curr,
# # #             grp["account_name"],
# # #             mop,
# # #             inv_no, inv_date,
# # #             f"POS Split Payment — {mop} ({curr})",
# # #         ))
# # #         new_id = int(cur.fetchone()[0])
# # #         ids.append(new_id)
# # #         log.debug("Split payment entry %d created: %s %.2f %s",
# # #                   new_id, curr, grp["paid_amount"], inv_no)

# # #     conn.commit(); conn.close()
# # #     return ids


# # # def get_unsynced_payment_entries() -> list[dict]:
# # #     """Returns payment entries that are ready to push (synced=0)."""
# # #     from database.db import get_connection, fetchall_dicts
# # #     conn = get_connection(); cur = conn.cursor()
# # #     cur.execute("""
# # #         SELECT pe.*, s.frappe_ref AS sale_frappe_ref
# # #         FROM payment_entries pe
# # #         LEFT JOIN sales s ON s.id = pe.sale_id
# # #         WHERE pe.synced = 0
# # #           AND (pe.frappe_invoice_ref IS NOT NULL
# # #                OR s.frappe_ref IS NOT NULL)
# # #         ORDER BY pe.id
# # #     """)
# # #     rows = fetchall_dicts(cur); conn.close()
# # #     return rows


# # # def mark_payment_synced(pe_id: int, frappe_payment_ref: str = "") -> None:
# # #     from database.db import get_connection
# # #     conn = get_connection(); cur = conn.cursor()
# # #     cur.execute(
# # #         "UPDATE payment_entries SET synced=1, frappe_payment_ref=? WHERE id=?",
# # #         (frappe_payment_ref or None, pe_id)
# # #     )
# # #     # Also update the sales row
# # #     cur.execute("""
# # #         UPDATE sales SET payment_entry_ref=?, payment_synced=1
# # #         WHERE id = (SELECT sale_id FROM payment_entries WHERE id=?)
# # #     """, (frappe_payment_ref or None, pe_id))
# # #     conn.commit(); conn.close()


# # # def refresh_frappe_refs() -> int:
# # #     """
# # #     For payment entries that have no frappe_invoice_ref yet, copy it from
# # #     the parent sale's frappe_ref. Call this before pushing payments.
# # #     Returns count updated.
# # #     """
# # #     from database.db import get_connection
# # #     conn = get_connection(); cur = conn.cursor()
# # #     cur.execute("""
# # #         UPDATE pe
# # #         SET pe.frappe_invoice_ref = s.frappe_ref
# # #         FROM payment_entries pe
# # #         JOIN sales s ON s.id = pe.sale_id
# # #         WHERE pe.synced = 0
# # #           AND (pe.frappe_invoice_ref IS NULL OR pe.frappe_invoice_ref = '')
# # #           AND s.frappe_ref IS NOT NULL AND s.frappe_ref != ''
# # #     """)
# # #     count = cur.rowcount
# # #     conn.commit(); conn.close()
# # #     return count


# # # # =============================================================================
# # # # BUILD FRAPPE PAYLOAD
# # # # =============================================================================

# # # def _build_payload(pe: dict, defaults: dict,
# # #                    api_key: str, api_secret: str, host: str) -> dict:
# # #     company  = defaults.get("server_company", "")
# # #     currency = (pe.get("currency") or pe.get("paid_to_account_currency") or "USD").upper()
# # #     mop      = pe.get("mode_of_payment") or "Cash"
# # #     amount   = float(pe.get("paid_amount") or 0)
# # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()

# # #     # Use local gl_accounts table first (synced from Frappe)
# # #     paid_to          = (pe.get("paid_to") or "").strip()
# # #     paid_to_currency = currency
# # #     if not paid_to:
# # #         try:
# # #             from models.gl_account import get_account_for_payment
# # #             acct = get_account_for_payment(currency, company)
# # #             if acct:
# # #                 paid_to          = acct["name"]
# # #                 paid_to_currency = acct["account_currency"]
# # #         except Exception as _e:
# # #             log.debug("gl_account lookup failed: %s", _e)

# # #     # Fallback to live Frappe lookup
# # #     if not paid_to:
# # #         paid_to = _resolve_paid_to_account(mop, company, currency, api_key, api_secret, host)

# # #     # Use local exchange rate if not stored
# # #     exch_rate = float(pe.get("source_exchange_rate") or 1.0)
# # #     if exch_rate == 1.0 and currency not in ("USD", ""):
# # #         try:
# # #             from models.exchange_rate import get_rate
# # #             stored = get_rate(currency, "USD")
# # #             if stored:
# # #                 exch_rate = stored
# # #         except Exception:
# # #             pass

# # #     payload = {
# # #         "doctype":                  "Payment Entry",
# # #         "payment_type":             "Receive",
# # #         "party_type":               "Customer",
# # #         "party":                    pe.get("party") or "default",
# # #         "party_name":               pe.get("party_name") or "default",
# # #         "paid_to_account_currency": paid_to_currency,
# # #         "paid_amount":              amount,
# # #         "received_amount":          amount,
# # #         "source_exchange_rate":     exch_rate,
# # #         "reference_no":             pe.get("reference_no") or pe.get("sale_invoice_no", ""),
# # #         "reference_date":           pe.get("reference_date") or date.today().isoformat(),
# # #         "remarks":                  pe.get("remarks") or f"POS Payment — {mop}",
# # #         "mode_of_payment":          mop,
# # #         "docstatus":                1,
# # #     }

# # #     if paid_to:
# # #         payload["paid_to"] = paid_to
# # #     if company:
# # #         payload["company"] = company

# # #     # Link to the Sales Invoice on Frappe
# # #     if frappe_inv:
# # #         payload["references"] = [{
# # #             "reference_doctype": "Sales Invoice",
# # #             "reference_name":    frappe_inv,
# # #             "allocated_amount":  amount,
# # #         }]

# # #     return payload


# # # # =============================================================================
# # # # PUSH ONE PAYMENT ENTRY
# # # # =============================================================================

# # # def _push_payment_entry(pe: dict, api_key: str, api_secret: str,
# # #                         defaults: dict, host: str) -> str | None:
# # #     """
# # #     Posts one payment entry to Frappe.
# # #     Returns Frappe's PAY-xxxxx name on success, None on failure.
# # #     """
# # #     pe_id  = pe["id"]
# # #     inv_no = pe.get("sale_invoice_no", str(pe_id))

# # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()
# # #     if not frappe_inv:
# # #         log.warning("Payment %d — Sales Invoice not yet on Frappe, skipping.", pe_id)
# # #         return None

# # #     payload = _build_payload(pe, defaults, api_key, api_secret, host)

# # #     url = f"{host}/api/resource/Payment%20Entry"
# # #     req = urllib.request.Request(
# # #         url=url,
# # #         data=json.dumps(payload).encode("utf-8"),
# # #         method="POST",
# # #         headers={
# # #             "Content-Type":  "application/json",
# # #             "Accept":        "application/json",
# # #             "Authorization": f"token {api_key}:{api_secret}",
# # #         },
# # #     )

# # #     try:
# # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
# # #             data = json.loads(resp.read().decode())
# # #             name = (data.get("data") or {}).get("name", "")
# # #             log.info("✅ Payment Entry %d → Frappe %s  [%s  %s %.2f]",
# # #                      pe_id, name, inv_no,
# # #                      pe.get("currency", ""), float(pe.get("paid_amount", 0)))
# # #             return name or "SYNCED"

# # #     except urllib.error.HTTPError as e:
# # #         try:
# # #             err = json.loads(e.read().decode())
# # #             msg = (err.get("exception") or err.get("message") or
# # #                    str(err.get("_server_messages", "")) or f"HTTP {e.code}")
# # #         except Exception:
# # #             msg = f"HTTP {e.code}"

# # #         if e.code == 409:
# # #             log.info("Payment %d already on Frappe (409) - marking synced.", pe_id)
# # #             return "DUPLICATE"

# # #         # Invoice already paid (is_pos:1 on old invoices) - stop retrying
# # #         if e.code == 417:
# # #             _perma = ("already been fully paid", "already paid", "fully paid")
# # #             if any(p in msg.lower() for p in _perma):
# # #                 log.info("Payment %d - invoice already paid on Frappe, marking synced.", pe_id)
# # #                 return "ALREADY_PAID"

# # #         log.error("FAIL Payment Entry %d  HTTP %s: %s", pe_id, e.code, msg)
# # #         return None

# # #     except urllib.error.URLError as e:
# # #         log.warning("Network error pushing payment %d: %s", pe_id, e.reason)
# # #         return None

# # #     except Exception as e:
# # #         log.error("Unexpected error pushing payment %d: %s", pe_id, e)
# # #         return None


# # # # =============================================================================
# # # # PUBLIC — push all unsynced payment entries
# # # # =============================================================================

# # # def push_unsynced_payment_entries() -> dict:
# # #     """
# # #     1. Refresh frappe_invoice_ref from parent sales that were confirmed.
# # #     2. Push each unsynced payment entry to Frappe.
# # #     3. Mark synced with the returned PAY-xxxxx ref.
# # #     """
# # #     result = {"pushed": 0, "failed": 0, "skipped": 0, "total": 0}

# # #     api_key, api_secret = _get_credentials()
# # #     if not api_key or not api_secret:
# # #         log.warning("No credentials — skipping payment entry sync.")
# # #         return result

# # #     host     = _get_host()
# # #     defaults = _get_defaults()

# # #     # First: pull frappe_refs from confirmed invoices into pending payment entries
# # #     updated = refresh_frappe_refs()
# # #     if updated:
# # #         log.info("Refreshed frappe_invoice_ref on %d payment entry(ies).", updated)

# # #     entries = get_unsynced_payment_entries()
# # #     result["total"] = len(entries)

# # #     if not entries:
# # #         log.debug("No unsynced payment entries.")
# # #         return result

# # #     log.info("Pushing %d payment entry(ies) to Frappe…", len(entries))

# # #     for pe in entries:
# # #         frappe_name = _push_payment_entry(pe, api_key, api_secret, defaults, host)
# # #         if frappe_name:
# # #             mark_payment_synced(pe["id"], frappe_name)
# # #             result["pushed"] += 1
# # #         elif frappe_name is None:
# # #             # None = permanent skip (no frappe_inv yet), not a real failure
# # #             result["skipped"] += 1
# # #         else:
# # #             result["failed"] += 1

# # #         time.sleep(3)   # rate limit — 20/min max

# # #     log.info("Payment sync done — ✅ %d pushed  ❌ %d failed  ⏭ %d skipped",
# # #              result["pushed"], result["failed"], result["skipped"])
# # #     return result


# # # # =============================================================================
# # # # BACKGROUND DAEMON THREAD
# # # # =============================================================================

# # # def _sync_loop():
# # #     log.info("Payment entry sync daemon started (interval=%ds).", SYNC_INTERVAL)
# # #     while True:
# # #         if _sync_lock.acquire(blocking=False):
# # #             try:
# # #                 push_unsynced_payment_entries()
# # #             except Exception as e:
# # #                 log.error("Payment sync cycle error: %s", e)
# # #             finally:
# # #                 _sync_lock.release()
# # #         else:
# # #             log.debug("Previous payment sync still running — skipping.")
# # #         time.sleep(SYNC_INTERVAL)


# # # def start_payment_sync_daemon() -> threading.Thread:
# # #     """Non-blocking — safe to call from MainWindow.__init__."""
# # #     global _sync_thread
# # #     if _sync_thread and _sync_thread.is_alive():
# # #         return _sync_thread
# # #     t = threading.Thread(target=_sync_loop, daemon=True, name="PaymentSyncDaemon")
# # #     t.start()
# # #     _sync_thread = t
# # #     log.info("Payment entry sync daemon started.")
# # #     return t


# # # # =============================================================================
# # # # DEBUG
# # # # =============================================================================

# # # if __name__ == "__main__":
# # #     logging.basicConfig(level=logging.INFO,
# # #                         format="%(asctime)s [%(levelname)s] %(message)s")
# # #     print("Running one payment entry sync cycle...")
# # #     r = push_unsynced_payment_entries()
# # #     print(f"\nResult: {r['pushed']} pushed, {r['failed']} failed, "
# # #           f"{r['skipped']} skipped (of {r['total']} total)")

# # # =============================================================================
# # # services/payment_entry_service.py
# # #
# # # Manages local payment_entries table and syncs them to Frappe.
# # #
# # # FLOW:
# # #   1. When a sale is saved locally → create_payment_entry() stores it locally
# # #      with synced=0
# # #   2. When the Sales Invoice is confirmed on Frappe (frappe_ref is set) →
# # #      push_unsynced_payment_entries() pushes the Payment Entry to Frappe
# # #   3. Frappe returns a PAY-xxxxx ref → stored as frappe_payment_ref, synced=1
# # #
# # # PAYLOAD SENT TO FRAPPE:
# # #   POST /api/resource/Payment Entry
# # #   {
# # #     "doctype":              "Payment Entry",
# # #     "payment_type":         "Receive",
# # #     "party_type":           "Customer",
# # #     "party":                "Cathy",
# # #     "paid_to":              "Cash ZWG - H",
# # #     "paid_to_account_currency": "USD",
# # #     "paid_amount":          32.45,
# # #     "received_amount":      32.45,
# # #     "source_exchange_rate": 1.0,
# # #     "reference_no":         "ACC-SINV-2026-00034",
# # #     "reference_date":       "2026-03-19",
# # #     "remarks":              "POS Payment — Cash",
# # #     "docstatus":            1,
# # #     "references": [{
# # #         "reference_doctype": "Sales Invoice",
# # #         "reference_name":    "ACC-SINV-2026-00565",
# # #         "allocated_amount":  32.45
# # #     }]
# # #   }
# # # =============================================================================

# # from __future__ import annotations

# # import json
# # import logging
# # import time
# # import threading
# # import urllib.request
# # import urllib.error
# # from datetime import date

# # log = logging.getLogger("PaymentEntry")

# # SYNC_INTERVAL   = 60      # seconds between auto-sync cycles
# # REQUEST_TIMEOUT = 30

# # # Exchange rate cache: "FROM::TO::DATE" → float
# # _RATE_CACHE: dict[str, float] = {}


# # def _get_exchange_rate(from_currency: str, to_currency: str,
# #                        transaction_date: str,
# #                        api_key: str, api_secret: str, host: str) -> float:
# #     """
# #     Fetch live exchange rate from Frappe.
# #     Returns 1.0 for same currency, 0.0 if fetch fails (Frappe uses its own rate).
# #     """
# #     if not from_currency or from_currency.upper() == to_currency.upper():
# #         return 1.0

# #     cache_key = f"{from_currency.upper()}::{to_currency.upper()}::{transaction_date}"
# #     if cache_key in _RATE_CACHE:
# #         return _RATE_CACHE[cache_key]

# #     try:
# #         import urllib.parse
# #         url = (
# #             f"{host}/api/method/erpnext.setup.utils.get_exchange_rate"
# #             f"?from_currency={urllib.parse.quote(from_currency)}"
# #             f"&to_currency={urllib.parse.quote(to_currency)}"
# #             f"&transaction_date={transaction_date}"
# #         )
# #         req = urllib.request.Request(url)
# #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# #             data = json.loads(r.read().decode())
# #             rate = float(data.get("message") or data.get("result") or 0)
# #             if rate > 0:
# #                 _RATE_CACHE[cache_key] = rate
# #                 log.debug("Rate %s→%s on %s: %.6f", from_currency, to_currency, transaction_date, rate)
# #                 return rate
# #     except Exception as e:
# #         log.debug("Rate fetch failed (%s→%s): %s", from_currency, to_currency, e)

# #     return 0.0

# # _sync_lock:   threading.Lock          = threading.Lock()
# # _sync_thread: threading.Thread | None = None

# # # Method → Frappe Mode of Payment name
# # _METHOD_MAP = {
# #     "CASH":     "Cash",
# #     "CARD":     "Credit Card",
# #     "C / CARD": "Credit Card",
# #     "EFTPOS":   "Credit Card",
# #     "CHECK":    "Cheque",
# #     "CHEQUE":   "Cheque",
# #     "MOBILE":   "Mobile Money",
# #     "CREDIT":   "Credit",
# #     "TRANSFER": "Bank Transfer",
# # }


# # # =============================================================================
# # # CREDENTIALS / HOST / DEFAULTS
# # # =============================================================================

# # def _get_credentials() -> tuple[str, str]:
# #     try:
# #         from services.credentials import get_credentials
# #         return get_credentials()
# #     except Exception:
# #         pass
# #     return "", ""

# # def _get_host() -> str:
# #     try:
# #         from models.company_defaults import get_defaults
# #         host = (get_defaults() or {}).get("server_api_host", "").strip().rstrip("/")
# #         if host:
# #             return host
# #     except Exception:
# #         pass
# #     return "https://apk.havano.cloud"


# # def _get_defaults() -> dict:
# #     try:
# #         from models.company_defaults import get_defaults
# #         return get_defaults() or {}
# #     except Exception:
# #         return {}


# # # =============================================================================
# # # GL ACCOUNT RESOLVER  (which account to credit for each payment method)
# # # =============================================================================

# # _ACCOUNT_CACHE: dict[str, str] = {}


# # def _resolve_paid_to_account(mop_name: str, company: str, currency: str,
# #                               api_key: str, api_secret: str, host: str) -> str:
# #     """
# #     Looks up the GL account for a Mode of Payment from Frappe.
# #     Tries to match by currency if multiple accounts exist for the company.
# #     Falls back to server_pos_account in company_defaults.
# #     """
# #     cache_key = f"{mop_name}::{company}::{currency}"
# #     if cache_key in _ACCOUNT_CACHE:
# #         return _ACCOUNT_CACHE[cache_key]

# #     try:
# #         import urllib.parse
# #         url = (f"{host}/api/resource/Mode%20of%20Payment/"
# #                f"{urllib.parse.quote(mop_name)}?fields=[\"accounts\"]")
# #         req = urllib.request.Request(url)
# #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# #             data     = json.loads(r.read().decode())
# #             accounts = (data.get("data") or {}).get("accounts", [])

# #         company_accts = [a for a in accounts
# #                          if not company or a.get("company") == company]

# #         # Prefer account whose name contains the currency code
# #         matched = ""
# #         if currency:
# #             for a in company_accts:
# #                 if currency.upper() in (a.get("default_account") or "").upper():
# #                     matched = a["default_account"]; break

# #         if not matched and company_accts:
# #             matched = company_accts[0].get("default_account", "")

# #         if matched:
# #             _ACCOUNT_CACHE[cache_key] = matched
# #             return matched

# #     except Exception as e:
# #         log.debug("MOP account lookup failed for '%s': %s", mop_name, e)

# #     # Fallback
# #     fallback = _get_defaults().get("server_pos_account", "").strip()
# #     if fallback:
# #         _ACCOUNT_CACHE[cache_key] = fallback
# #         return fallback

# #     log.warning("No GL account for MOP '%s' currency=%s — Payment Entry may fail.",
# #                 mop_name, currency)
# #     return ""


# # # =============================================================================
# # # LOCAL DB  — create / read / update payment_entries
# # # =============================================================================

# # def create_payment_entry(sale: dict, override_rate: float = None,
# #                          override_account: str = None) -> int | None:
# #     """
# #     Called immediately after a sale is saved locally.
# #     Stores a payment_entry row with synced=0.
# #     Returns the new payment_entry id, or None on error.

# #     Will only create the entry once per sale (idempotent).
# #     """
# #     from database.db import get_connection
# #     conn = get_connection(); cur = conn.cursor()

# #     # Idempotency: don't create twice for the same sale
# #     cur.execute("SELECT id FROM payment_entries WHERE sale_id = ?", (sale["id"],))
# #     if cur.fetchone():
# #         conn.close()
# #         return None

# #     customer   = (sale.get("customer_name") or "default").strip()
# #     currency   = (sale.get("currency")      or "USD").strip().upper()
# #     amount     = float(sale.get("total")    or 0)
# #     inv_no     = sale.get("invoice_no", "")
# #     inv_date   = sale.get("invoice_date") or date.today().isoformat()
# #     method     = str(sale.get("method", "CASH")).upper().strip()
# #     mop        = _METHOD_MAP.get(method, "Cash")

# #     # Use override rate (from split) or fetch from Frappe
# #     if override_rate is not None:
# #         exch_rate = override_rate
# #     else:
# #         try:
# #             api_key, api_secret = _get_credentials()
# #             host = _get_host()
# #             defaults = _get_defaults()
# #             company_currency = defaults.get("server_company_currency", "USD").strip().upper() or "USD"
# #             exch_rate = _get_exchange_rate(
# #                 currency, company_currency, inv_date, api_key, api_secret, host
# #             ) if currency != company_currency else 1.0
# #         except Exception:
# #             exch_rate = 1.0

# #     cur.execute("""
# #         INSERT INTO payment_entries (
# #             sale_id, sale_invoice_no, frappe_invoice_ref,
# #             party, party_name,
# #             paid_amount, received_amount, source_exchange_rate,
# #             paid_to_account_currency, currency,
# #             mode_of_payment,
# #             reference_no, reference_date,
# #             remarks, synced
# #         ) OUTPUT INSERTED.id
# #         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# #     """, (
# #         sale["id"], inv_no,
# #         sale.get("frappe_ref") or None,
# #         customer, customer,
# #         amount, amount, exch_rate or 1.0,
# #         currency, currency,
# #         mop,
# #         inv_no, inv_date,
# #         f"POS Payment — {mop}",
# #     ))
# #     new_id = int(cur.fetchone()[0])
# #     conn.commit(); conn.close()
# #     log.debug("Payment entry %d created locally for sale %s", new_id, inv_no)
# #     return new_id


# # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# #     """
# #     Called when cashier uses Split payment.
# #     Creates one payment_entry row per currency in splits list.
# #     splits = [{"mode": "CASH", "currency": "USD", "amount": 5.0,
# #                "rate": 1.0, "base_amount": 5.0, "account": "Cash - AT"}, ...]
# #     Returns list of new payment_entry ids.
# #     """
# #     ids = []
# #     for split in splits:
# #         if not split.get("amount") or float(split["amount"]) <= 0:
# #             continue
# #         # Build a sale-like dict with the split's currency and amount
# #         split_sale = dict(sale)
# #         split_sale["currency"]      = split.get("currency", "USD")
# #         split_sale["total"]         = float(split.get("amount", 0))
# #         split_sale["method"]        = split.get("mode", "CASH")
# #         # Override exchange rate from split data
# #         new_id = create_payment_entry(
# #             split_sale,
# #             override_rate=float(split.get("rate", 1.0)),
# #             override_account=split.get("account", ""),
# #         )
# #         if new_id:
# #             ids.append(new_id)
# #     return ids


# # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# #     """
# #     Creates one payment_entry per currency from a split payment.
# #     Groups splits by currency, sums amounts, creates one entry each.
# #     Returns list of created payment_entry ids.
# #     """
# #     from datetime import date as _date

# #     # Group by currency
# #     by_currency: dict[str, dict] = {}
# #     for s in splits:
# #         curr = s.get("account_currency", "USD").upper()
# #         if curr not in by_currency:
# #             by_currency[curr] = {
# #                 "currency":      curr,
# #                 "paid_amount":   0.0,
# #                 "base_value":    0.0,
# #                 "rate":          s.get("rate", 1.0),
# #                 "account_name":  s.get("account_name", ""),
# #                 "mode":          s.get("mode", "Cash"),
# #             }
# #         by_currency[curr]["paid_amount"] += s.get("amount_paid", 0.0)
# #         by_currency[curr]["base_value"]  += s.get("base_value",  0.0)

# #     ids = []
# #     inv_no   = sale.get("invoice_no", "")
# #     inv_date = sale.get("invoice_date") or _date.today().isoformat()
# #     customer = (sale.get("customer_name") or "default").strip()

# #     from database.db import get_connection
# #     conn = get_connection(); cur = conn.cursor()

# #     for curr, grp in by_currency.items():
# #         # Idempotency: skip if already exists for this sale+currency
# #         cur.execute(
# #             "SELECT id FROM payment_entries WHERE sale_id=? AND currency=?",
# #             (sale["id"], curr)
# #         )
# #         if cur.fetchone():
# #             continue

# #         mop = _METHOD_MAP.get(grp["mode"].upper(), "Cash")

# #         cur.execute("""
# #             INSERT INTO payment_entries (
# #                 sale_id, sale_invoice_no, frappe_invoice_ref,
# #                 party, party_name,
# #                 paid_amount, received_amount, source_exchange_rate,
# #                 paid_to_account_currency, currency,
# #                 paid_to,
# #                 mode_of_payment,
# #                 reference_no, reference_date,
# #                 remarks, synced
# #             ) OUTPUT INSERTED.id
# #             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# #         """, (
# #             sale["id"], inv_no,
# #             sale.get("frappe_ref") or None,
# #             customer, customer,
# #             grp["paid_amount"],
# #             grp["base_value"],
# #             float(grp["rate"] or 1.0),
# #             curr, curr,
# #             grp["account_name"],
# #             mop,
# #             inv_no, inv_date,
# #             f"POS Split Payment — {mop} ({curr})",
# #         ))
# #         new_id = int(cur.fetchone()[0])
# #         ids.append(new_id)
# #         log.debug("Split payment entry %d created: %s %.2f %s",
# #                   new_id, curr, grp["paid_amount"], inv_no)

# #     conn.commit(); conn.close()
# #     return ids


# # def get_unsynced_payment_entries() -> list[dict]:
# #     """Returns payment entries that are ready to push (synced=0)."""
# #     from database.db import get_connection, fetchall_dicts
# #     conn = get_connection(); cur = conn.cursor()
# #     cur.execute("""
# #         SELECT pe.*, s.frappe_ref AS sale_frappe_ref
# #         FROM payment_entries pe
# #         LEFT JOIN sales s ON s.id = pe.sale_id
# #         WHERE pe.synced = 0
# #           AND (pe.frappe_invoice_ref IS NOT NULL
# #                OR s.frappe_ref IS NOT NULL)
# #         ORDER BY pe.id
# #     """)
# #     rows = fetchall_dicts(cur); conn.close()
# #     return rows


# # def mark_payment_synced(pe_id: int, frappe_payment_ref: str = "") -> None:
# #     from database.db import get_connection
# #     conn = get_connection(); cur = conn.cursor()
# #     cur.execute(
# #         "UPDATE payment_entries SET synced=1, frappe_payment_ref=? WHERE id=?",
# #         (frappe_payment_ref or None, pe_id)
# #     )
# #     # Also update the sales row
# #     cur.execute("""
# #         UPDATE sales SET payment_entry_ref=?, payment_synced=1
# #         WHERE id = (SELECT sale_id FROM payment_entries WHERE id=?)
# #     """, (frappe_payment_ref or None, pe_id))
# #     conn.commit(); conn.close()


# # def refresh_frappe_refs() -> int:
# #     """
# #     For payment entries that have no frappe_invoice_ref yet, copy it from
# #     the parent sale's frappe_ref. Call this before pushing payments.
# #     Returns count updated.
# #     """
# #     from database.db import get_connection
# #     conn = get_connection(); cur = conn.cursor()
# #     cur.execute("""
# #         UPDATE pe
# #         SET pe.frappe_invoice_ref = s.frappe_ref
# #         FROM payment_entries pe
# #         JOIN sales s ON s.id = pe.sale_id
# #         WHERE pe.synced = 0
# #           AND (pe.frappe_invoice_ref IS NULL OR pe.frappe_invoice_ref = '')
# #           AND s.frappe_ref IS NOT NULL AND s.frappe_ref != ''
# #     """)
# #     count = cur.rowcount
# #     conn.commit(); conn.close()
# #     return count


# # # =============================================================================
# # # BUILD FRAPPE PAYLOAD
# # # =============================================================================

# # def _build_payload(pe: dict, defaults: dict,
# #                    api_key: str, api_secret: str, host: str) -> dict:
# #     company  = defaults.get("server_company", "")
# #     currency = (pe.get("currency") or pe.get("paid_to_account_currency") or "USD").upper()
# #     mop      = pe.get("mode_of_payment") or "Cash"
# #     amount   = float(pe.get("paid_amount") or 0)
# #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()

# #     # Use local gl_accounts table first (synced from Frappe)
# #     paid_to          = (pe.get("paid_to") or "").strip()
# #     paid_to_currency = currency
# #     if not paid_to:
# #         try:
# #             from models.gl_account import get_account_for_payment
# #             acct = get_account_for_payment(currency, company)
# #             if acct:
# #                 paid_to          = acct["name"]
# #                 paid_to_currency = acct["account_currency"]
# #         except Exception as _e:
# #             log.debug("gl_account lookup failed: %s", _e)

# #     # Fallback to live Frappe lookup
# #     if not paid_to:
# #         paid_to = _resolve_paid_to_account(mop, company, currency, api_key, api_secret, host)

# #     # Use local exchange rate if not stored
# #     exch_rate = float(pe.get("source_exchange_rate") or 1.0)
# #     if exch_rate == 1.0 and currency not in ("USD", ""):
# #         try:
# #             from models.exchange_rate import get_rate
# #             stored = get_rate(currency, "USD")
# #             if stored:
# #                 exch_rate = stored
# #         except Exception:
# #             pass

# #     payload = {
# #         "doctype":                  "Payment Entry",
# #         "payment_type":             "Receive",
# #         "party_type":               "Customer",
# #         "party":                    pe.get("party") or "default",
# #         "party_name":               pe.get("party_name") or "default",
# #         "paid_to_account_currency": paid_to_currency,
# #         "paid_amount":              amount,
# #         "received_amount":          amount,
# #         "source_exchange_rate":     exch_rate,
# #         "reference_no":             pe.get("reference_no") or pe.get("sale_invoice_no", ""),
# #         "reference_date":           pe.get("reference_date") or date.today().isoformat(),
# #         "remarks":                  pe.get("remarks") or f"POS Payment — {mop}",
# #         "mode_of_payment":          mop,
# #         "docstatus":                1,
# #     }

# #     if paid_to:
# #         payload["paid_to"] = paid_to
# #     if company:
# #         payload["company"] = company

# #     # Link to the Sales Invoice on Frappe
# #     if frappe_inv:
# #         payload["references"] = [{
# #             "reference_doctype": "Sales Invoice",
# #             "reference_name":    frappe_inv,
# #             "allocated_amount":  amount,
# #         }]

# #     return payload


# # # =============================================================================
# # # PUSH ONE PAYMENT ENTRY
# # # =============================================================================

# # def _push_payment_entry(pe: dict, api_key: str, api_secret: str,
# #                         defaults: dict, host: str) -> str | None:
# #     """
# #     Posts one payment entry to Frappe.
# #     Returns Frappe's PAY-xxxxx name on success, None on failure.
# #     """
# #     pe_id  = pe["id"]
# #     inv_no = pe.get("sale_invoice_no", str(pe_id))

# #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()
# #     if not frappe_inv:
# #         log.warning("Payment %d — Sales Invoice not yet on Frappe, skipping.", pe_id)
# #         return None

# #     payload = _build_payload(pe, defaults, api_key, api_secret, host)

# #     url = f"{host}/api/resource/Payment%20Entry"
# #     req = urllib.request.Request(
# #         url=url,
# #         data=json.dumps(payload).encode("utf-8"),
# #         method="POST",
# #         headers={
# #             "Content-Type":  "application/json",
# #             "Accept":        "application/json",
# #             "Authorization": f"token {api_key}:{api_secret}",
# #         },
# #     )

# #     try:
# #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
# #             data = json.loads(resp.read().decode())
# #             name = (data.get("data") or {}).get("name", "")
# #             log.info("✅ Payment Entry %d → Frappe %s  [%s  %s %.2f]",
# #                      pe_id, name, inv_no,
# #                      pe.get("currency", ""), float(pe.get("paid_amount", 0)))
# #             return name or "SYNCED"

# #     except urllib.error.HTTPError as e:
# #         try:
# #             err = json.loads(e.read().decode())
# #             msg = (err.get("exception") or err.get("message") or
# #                    str(err.get("_server_messages", "")) or f"HTTP {e.code}")
# #         except Exception:
# #             msg = f"HTTP {e.code}"

# #         if e.code == 409:
# #             log.info("Payment %d already on Frappe (409) - marking synced.", pe_id)
# #             return "DUPLICATE"

# #         # Invoice already paid (is_pos:1 on old invoices) - stop retrying
# #         if e.code == 417:
# #             _perma = ("already been fully paid", "already paid", "fully paid")
# #             if any(p in msg.lower() for p in _perma):
# #                 log.info("Payment %d - invoice already paid on Frappe, marking synced.", pe_id)
# #                 return "ALREADY_PAID"

# #         log.error("FAIL Payment Entry %d  HTTP %s: %s", pe_id, e.code, msg)
# #         return None

# #     except urllib.error.URLError as e:
# #         log.warning("Network error pushing payment %d: %s", pe_id, e.reason)
# #         return None

# #     except Exception as e:
# #         log.error("Unexpected error pushing payment %d: %s", pe_id, e)
# #         return None


# # # =============================================================================
# # # PUBLIC — push all unsynced payment entries
# # # =============================================================================

# # def push_unsynced_payment_entries() -> dict:
# #     """
# #     1. Refresh frappe_invoice_ref from parent sales that were confirmed.
# #     2. Push each unsynced payment entry to Frappe.
# #     3. Mark synced with the returned PAY-xxxxx ref.
# #     """
# #     result = {"pushed": 0, "failed": 0, "skipped": 0, "total": 0}

# #     api_key, api_secret = _get_credentials()
# #     if not api_key or not api_secret:
# #         log.warning("No credentials — skipping payment entry sync.")
# #         return result

# #     host     = _get_host()
# #     defaults = _get_defaults()

# #     # First: pull frappe_refs from confirmed invoices into pending payment entries
# #     updated = refresh_frappe_refs()
# #     if updated:
# #         log.info("Refreshed frappe_invoice_ref on %d payment entry(ies).", updated)

# #     entries = get_unsynced_payment_entries()
# #     result["total"] = len(entries)

# #     if not entries:
# #         log.debug("No unsynced payment entries.")
# #         return result

# #     log.info("Pushing %d payment entry(ies) to Frappe…", len(entries))

# #     for pe in entries:
# #         frappe_name = _push_payment_entry(pe, api_key, api_secret, defaults, host)
# #         if frappe_name:
# #             mark_payment_synced(pe["id"], frappe_name)
# #             result["pushed"] += 1
# #         elif frappe_name is None:
# #             # None = permanent skip (no frappe_inv yet), not a real failure
# #             result["skipped"] += 1
# #         else:
# #             result["failed"] += 1

# #         time.sleep(3)   # rate limit — 20/min max

# #     log.info("Payment sync done — ✅ %d pushed  ❌ %d failed  ⏭ %d skipped",
# #              result["pushed"], result["failed"], result["skipped"])
# #     return result


# # # =============================================================================
# # # BACKGROUND DAEMON THREAD
# # # =============================================================================

# # def _sync_loop():
# #     log.info("Payment entry sync daemon started (interval=%ds).", SYNC_INTERVAL)
# #     while True:
# #         if _sync_lock.acquire(blocking=False):
# #             try:
# #                 push_unsynced_payment_entries()
# #             except Exception as e:
# #                 log.error("Payment sync cycle error: %s", e)
# #             finally:
# #                 _sync_lock.release()
# #         else:
# #             log.debug("Previous payment sync still running — skipping.")
# #         time.sleep(SYNC_INTERVAL)


# # def start_payment_sync_daemon() -> threading.Thread:
# #     """Non-blocking — safe to call from MainWindow.__init__."""
# #     global _sync_thread
# #     if _sync_thread and _sync_thread.is_alive():
# #         return _sync_thread
# #     t = threading.Thread(target=_sync_loop, daemon=True, name="PaymentSyncDaemon")
# #     t.start()
# #     _sync_thread = t
# #     log.info("Payment entry sync daemon started.")
# #     return t


# # # =============================================================================
# # # DEBUG
# # # =============================================================================

# # if __name__ == "__main__":
# #     logging.basicConfig(level=logging.INFO,
# #                         format="%(asctime)s [%(levelname)s] %(message)s")
# #     print("Running one payment entry sync cycle...")
# #     r = push_unsynced_payment_entries()
# #     print(f"\nResult: {r['pushed']} pushed, {r['failed']} failed, "
# #           f"{r['skipped']} skipped (of {r['total']} total)")


# # =============================================================================
# # services/payment_entry_service.py
# #
# # Manages local payment_entries table and syncs them to Frappe.
# #
# # FLOW:
# #   1. When a sale is saved locally → create_payment_entry() stores it locally
# #      with synced=0
# #   2. When the Sales Invoice is confirmed on Frappe (frappe_ref is set) →
# #      push_unsynced_payment_entries() pushes the Payment Entry to Frappe
# #   3. Frappe returns a PAY-xxxxx ref → stored as frappe_payment_ref, synced=1
# #
# # PAYLOAD SENT TO FRAPPE:
# #   POST /api/resource/Payment Entry
# #   {
# #     "doctype":              "Payment Entry",
# #     "payment_type":         "Receive",
# #     "party_type":           "Customer",
# #     "party":                "Cathy",
# #     "paid_to":              "Cash ZWG - H",
# #     "paid_to_account_currency": "USD",
# #     "paid_amount":          32.45,
# #     "received_amount":      32.45,
# #     "source_exchange_rate": 1.0,
# #     "reference_no":         "ACC-SINV-2026-00034",
# #     "reference_date":       "2026-03-19",
# #     "remarks":              "POS Payment — Cash",
# #     "docstatus":            1,
# #     "references": [{
# #         "reference_doctype": "Sales Invoice",
# #         "reference_name":    "ACC-SINV-2026-00565",
# #         "allocated_amount":  32.45
# #     }]
# #   }
# # =============================================================================

# from __future__ import annotations

# import json
# import logging
# import time
# import threading
# import urllib.request
# import urllib.error
# from datetime import date

# log = logging.getLogger("PaymentEntry")

# SYNC_INTERVAL   = 60      # seconds between auto-sync cycles
# REQUEST_TIMEOUT = 30

# # Exchange rate cache: "FROM::TO::DATE" → float
# _RATE_CACHE: dict[str, float] = {}


# def _get_exchange_rate(from_currency: str, to_currency: str,
#                        transaction_date: str,
#                        api_key: str, api_secret: str, host: str) -> float:
#     """
#     Fetch live exchange rate from Frappe.
#     Returns 1.0 for same currency, 0.0 if fetch fails (Frappe uses its own rate).
#     """
#     if not from_currency or from_currency.upper() == to_currency.upper():
#         return 1.0

#     cache_key = f"{from_currency.upper()}::{to_currency.upper()}::{transaction_date}"
#     if cache_key in _RATE_CACHE:
#         return _RATE_CACHE[cache_key]

#     try:
#         import urllib.parse
#         url = (
#             f"{host}/api/method/erpnext.setup.utils.get_exchange_rate"
#             f"?from_currency={urllib.parse.quote(from_currency)}"
#             f"&to_currency={urllib.parse.quote(to_currency)}"
#             f"&transaction_date={transaction_date}"
#         )
#         req = urllib.request.Request(url)
#         req.add_header("Authorization", f"token {api_key}:{api_secret}")
#         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
#             data = json.loads(r.read().decode())
#             rate = float(data.get("message") or data.get("result") or 0)
#             if rate > 0:
#                 _RATE_CACHE[cache_key] = rate
#                 log.debug("Rate %s→%s on %s: %.6f", from_currency, to_currency, transaction_date, rate)
#                 return rate
#     except Exception as e:
#         log.debug("Rate fetch failed (%s→%s): %s", from_currency, to_currency, e)

#     return 0.0

# _sync_lock:   threading.Lock          = threading.Lock()
# _sync_thread: threading.Thread | None = None

# # Method → Frappe Mode of Payment name
# _METHOD_MAP = {
#     "CASH":     "Cash",
#     "CARD":     "Credit Card",
#     "C / CARD": "Credit Card",
#     "EFTPOS":   "Credit Card",
#     "CHECK":    "Cheque",
#     "CHEQUE":   "Cheque",
#     "MOBILE":   "Mobile Money",
#     "CREDIT":   "Credit",
#     "TRANSFER": "Bank Transfer",
# }


# # =============================================================================
# # CREDENTIALS / HOST / DEFAULTS
# # =============================================================================

# def _get_credentials() -> tuple[str, str]:
#     try:
#         from services.credentials import get_credentials
#         return get_credentials()
#     except Exception:
#         pass
#     return "", ""

# def _get_host() -> str:
#     try:
#         from models.company_defaults import get_defaults
#         host = (get_defaults() or {}).get("server_api_host", "").strip().rstrip("/")
#         if host:
#             return host
#     except Exception:
#         pass
#     return "https://apk.havano.cloud"


# def _get_defaults() -> dict:
#     try:
#         from models.company_defaults import get_defaults
#         return get_defaults() or {}
#     except Exception:
#         return {}


# # =============================================================================
# # GL ACCOUNT RESOLVER  (which account to credit for each payment method)
# # =============================================================================

# _ACCOUNT_CACHE: dict[str, str] = {}


# def _resolve_paid_to_account(mop_name: str, company: str, currency: str,
#                               api_key: str, api_secret: str, host: str) -> str:
#     """
#     Looks up the GL account for a Mode of Payment from Frappe.
#     Tries to match by currency if multiple accounts exist for the company.
#     Falls back to server_pos_account in company_defaults.
#     """
#     cache_key = f"{mop_name}::{company}::{currency}"
#     if cache_key in _ACCOUNT_CACHE:
#         return _ACCOUNT_CACHE[cache_key]

#     try:
#         import urllib.parse
#         url = (f"{host}/api/resource/Mode%20of%20Payment/"
#                f"{urllib.parse.quote(mop_name)}?fields=[\"accounts\"]")
#         req = urllib.request.Request(url)
#         req.add_header("Authorization", f"token {api_key}:{api_secret}")
#         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
#             data     = json.loads(r.read().decode())
#             accounts = (data.get("data") or {}).get("accounts", [])

#         company_accts = [a for a in accounts
#                          if not company or a.get("company") == company]

#         # Prefer account whose name contains the currency code
#         matched = ""
#         if currency:
#             for a in company_accts:
#                 if currency.upper() in (a.get("default_account") or "").upper():
#                     matched = a["default_account"]; break

#         if not matched and company_accts:
#             matched = company_accts[0].get("default_account", "")

#         if matched:
#             _ACCOUNT_CACHE[cache_key] = matched
#             return matched

#     except Exception as e:
#         log.debug("MOP account lookup failed for '%s': %s", mop_name, e)

#     # Fallback
#     fallback = _get_defaults().get("server_pos_account", "").strip()
#     if fallback:
#         _ACCOUNT_CACHE[cache_key] = fallback
#         return fallback

#     log.warning("No GL account for MOP '%s' currency=%s — Payment Entry may fail.",
#                 mop_name, currency)
#     return ""


# # =============================================================================
# # LOCAL DB  — create / read / update payment_entries
# # =============================================================================

# def create_payment_entry(sale: dict, override_rate: float = None,
#                          override_account: str = None) -> int | None:
#     """
#     Called immediately after a sale is saved locally.
#     Stores a payment_entry row with synced=0.
#     Returns the new payment_entry id, or None on error.

#     Will only create the entry once per sale (idempotent).
#     """
#     from database.db import get_connection
#     conn = get_connection(); cur = conn.cursor()

#     # Idempotency: don't create twice for the same sale
#     cur.execute("SELECT id FROM payment_entries WHERE sale_id = ?", (sale["id"],))
#     if cur.fetchone():
#         conn.close()
#         return None

#     customer   = (sale.get("customer_name") or "default").strip()
#     currency   = (sale.get("currency")      or "USD").strip().upper()
#     amount     = float(sale.get("total")    or 0)
#     inv_no     = sale.get("invoice_no", "")
#     inv_date   = sale.get("invoice_date") or date.today().isoformat()
#     method     = str(sale.get("method", "CASH")).upper().strip()
#     mop        = _METHOD_MAP.get(method, "Cash")

#     # Use override rate (from split) or fetch from Frappe
#     if override_rate is not None:
#         exch_rate = override_rate
#     else:
#         try:
#             api_key, api_secret = _get_credentials()
#             host = _get_host()
#             defaults = _get_defaults()
#             company_currency = defaults.get("server_company_currency", "USD").strip().upper() or "USD"
#             exch_rate = _get_exchange_rate(
#                 currency, company_currency, inv_date, api_key, api_secret, host
#             ) if currency != company_currency else 1.0
#         except Exception:
#             exch_rate = 1.0

#     cur.execute("""
#         INSERT INTO payment_entries (
#             sale_id, sale_invoice_no, frappe_invoice_ref,
#             party, party_name,
#             paid_amount, received_amount, source_exchange_rate,
#             paid_to_account_currency, currency,
#             mode_of_payment,
#             reference_no, reference_date,
#             remarks, synced
#         ) OUTPUT INSERTED.id
#         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
#     """, (
#         sale["id"], inv_no,
#         sale.get("frappe_ref") or None,
#         customer, customer,
#         amount, amount, exch_rate or 1.0,
#         currency, currency,
#         mop,
#         inv_no, inv_date,
#         f"POS Payment — {mop}",
#     ))
#     new_id = int(cur.fetchone()[0])
#     conn.commit(); conn.close()
#     log.debug("Payment entry %d created locally for sale %s", new_id, inv_no)
#     return new_id


# def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
#     """
#     Called when cashier uses Split payment.
#     Creates one payment_entry row per currency in splits list.
#     splits = [{"mode": "CASH", "currency": "USD", "amount": 5.0,
#                "rate": 1.0, "base_amount": 5.0, "account": "Cash - AT"}, ...]
#     Returns list of new payment_entry ids.
#     """
#     ids = []
#     for split in splits:
#         if not split.get("amount") or float(split["amount"]) <= 0:
#             continue
#         # Build a sale-like dict with the split's currency and amount
#         split_sale = dict(sale)
#         split_sale["currency"]      = split.get("currency", "USD")
#         split_sale["total"]         = float(split.get("amount", 0))
#         split_sale["method"]        = split.get("mode", "CASH")
#         # Override exchange rate from split data
#         new_id = create_payment_entry(
#             split_sale,
#             override_rate=float(split.get("rate", 1.0)),
#             override_account=split.get("account", ""),
#         )
#         if new_id:
#             ids.append(new_id)
#     return ids


# def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
#     """
#     Creates one payment_entry per currency from a split payment.
#     Groups splits by currency, sums amounts, creates one entry each.
#     Returns list of created payment_entry ids.
#     """
#     from datetime import date as _date

#     # Group by currency
#     by_currency: dict[str, dict] = {}
#     for s in splits:
#         curr = s.get("account_currency", "USD").upper()
#         if curr not in by_currency:
#             by_currency[curr] = {
#                 "currency":      curr,
#                 "paid_amount":   0.0,
#                 "base_value":    0.0,
#                 "rate":          s.get("rate", 1.0),
#                 "account_name":  s.get("account_name", ""),
#                 "mode":          s.get("mode", "Cash"),
#             }
#         by_currency[curr]["paid_amount"] += s.get("amount_paid", 0.0)
#         by_currency[curr]["base_value"]  += s.get("base_value",  0.0)

#     ids = []
#     inv_no   = sale.get("invoice_no", "")
#     inv_date = sale.get("invoice_date") or _date.today().isoformat()
#     customer = (sale.get("customer_name") or "default").strip()

#     from database.db import get_connection
#     conn = get_connection(); cur = conn.cursor()

#     for curr, grp in by_currency.items():
#         # Idempotency: skip if already exists for this sale+currency
#         cur.execute(
#             "SELECT id FROM payment_entries WHERE sale_id=? AND currency=?",
#             (sale["id"], curr)
#         )
#         if cur.fetchone():
#             continue

#         mop = _METHOD_MAP.get(grp["mode"].upper(), "Cash")

#         cur.execute("""
#             INSERT INTO payment_entries (
#                 sale_id, sale_invoice_no, frappe_invoice_ref,
#                 party, party_name,
#                 paid_amount, received_amount, source_exchange_rate,
#                 paid_to_account_currency, currency,
#                 paid_to,
#                 mode_of_payment,
#                 reference_no, reference_date,
#                 remarks, synced
#             ) OUTPUT INSERTED.id
#             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
#         """, (
#             sale["id"], inv_no,
#             sale.get("frappe_ref") or None,
#             customer, customer,
#             grp["paid_amount"],
#             grp["base_value"],
#             float(grp["rate"] or 1.0),
#             curr, curr,
#             grp["account_name"],
#             mop,
#             inv_no, inv_date,
#             f"POS Split Payment — {mop} ({curr})",
#         ))
#         new_id = int(cur.fetchone()[0])
#         ids.append(new_id)
#         log.debug("Split payment entry %d created: %s %.2f %s",
#                   new_id, curr, grp["paid_amount"], inv_no)

#     conn.commit(); conn.close()
#     return ids


# def get_unsynced_payment_entries() -> list[dict]:
#     """
#     Returns payment entries that are ready to push (synced=0).

#     Two kinds of entries are included:
#       1. Normal sale payments  — frappe_invoice_ref set directly, OR
#                                  parent sale has a frappe_ref
#       2. CN refund payments    — payment_type='Pay' with frappe_invoice_ref
#                                  set by link_cn_payment_to_frappe().
#                                  These have no parent sale frappe_ref to
#                                  fall back on, so we must NOT require it.
#     """
#     from database.db import get_connection, fetchall_dicts
#     conn = get_connection(); cur = conn.cursor()
#     cur.execute("""
#         SELECT pe.*, s.frappe_ref AS sale_frappe_ref
#         FROM payment_entries pe
#         LEFT JOIN sales s ON s.id = pe.sale_id
#         WHERE pe.synced = 0
#           AND (
#               -- Normal path: frappe_invoice_ref already set on the PE row
#               pe.frappe_invoice_ref IS NOT NULL
#               AND pe.frappe_invoice_ref != ''
#           OR
#               -- Fallback for sale payments: pull ref from the parent sale
#               (
#                   (pe.payment_type IS NULL OR pe.payment_type = 'Receive')
#                   AND s.frappe_ref IS NOT NULL
#                   AND s.frappe_ref != ''
#               )
#           )
#         ORDER BY pe.id
#     """)
#     rows = fetchall_dicts(cur); conn.close()
#     return rows


# def mark_payment_synced(pe_id: int, frappe_payment_ref: str = "") -> None:
#     from database.db import get_connection
#     conn = get_connection(); cur = conn.cursor()
#     cur.execute(
#         "UPDATE payment_entries SET synced=1, frappe_payment_ref=? WHERE id=?",
#         (frappe_payment_ref or None, pe_id)
#     )
#     # Also update the sales row
#     cur.execute("""
#         UPDATE sales SET payment_entry_ref=?, payment_synced=1
#         WHERE id = (SELECT sale_id FROM payment_entries WHERE id=?)
#     """, (frappe_payment_ref or None, pe_id))
#     conn.commit(); conn.close()


# def refresh_frappe_refs() -> int:
#     """
#     For payment entries that have no frappe_invoice_ref yet, copy it from
#     the parent sale's frappe_ref. Call this before pushing payments.
#     Returns count updated.
#     """
#     from database.db import get_connection
#     conn = get_connection(); cur = conn.cursor()
#     cur.execute("""
#         UPDATE pe
#         SET pe.frappe_invoice_ref = s.frappe_ref
#         FROM payment_entries pe
#         JOIN sales s ON s.id = pe.sale_id
#         WHERE pe.synced = 0
#           AND (pe.frappe_invoice_ref IS NULL OR pe.frappe_invoice_ref = '')
#           AND s.frappe_ref IS NOT NULL AND s.frappe_ref != ''
#     """)
#     count = cur.rowcount
#     conn.commit(); conn.close()
#     return count


# # =============================================================================
# # BUILD FRAPPE PAYLOAD
# # =============================================================================

# def _build_payload(pe: dict, defaults: dict,
#                    api_key: str, api_secret: str, host: str) -> dict:
#     company  = defaults.get("server_company", "")
#     currency = (pe.get("currency") or pe.get("paid_to_account_currency") or "USD").upper()
#     mop      = pe.get("mode_of_payment") or "Cash"
#     amount   = float(pe.get("paid_amount") or 0)
#     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()

#     # Use local gl_accounts table first (synced from Frappe)
#     paid_to          = (pe.get("paid_to") or "").strip()
#     paid_to_currency = currency
#     if not paid_to:
#         try:
#             from models.gl_account import get_account_for_payment
#             acct = get_account_for_payment(currency, company)
#             if acct:
#                 paid_to          = acct["name"]
#                 paid_to_currency = acct["account_currency"]
#         except Exception as _e:
#             log.debug("gl_account lookup failed: %s", _e)

#     # Fallback to live Frappe lookup
#     if not paid_to:
#         paid_to = _resolve_paid_to_account(mop, company, currency, api_key, api_secret, host)

#     # Use local exchange rate if not stored
#     exch_rate = float(pe.get("source_exchange_rate") or 1.0)
#     if exch_rate == 1.0 and currency not in ("USD", ""):
#         try:
#             from models.exchange_rate import get_rate
#             stored = get_rate(currency, "USD")
#             if stored:
#                 exch_rate = stored
#         except Exception:
#             pass

#     # Respect the payment_type stored on the row — CN refunds are 'Pay'
#     payment_type = (pe.get("payment_type") or "Receive").strip() or "Receive"
#     is_refund    = payment_type == "Pay"

#     ref_date = pe.get("reference_date")
#     ref_date_str = (
#         ref_date.isoformat()
#         if hasattr(ref_date, "isoformat")
#         else ref_date or date.today().isoformat()
#     )

#     payload = {
#         "doctype":       "Payment Entry",
#         "payment_type":  payment_type,
#         "party_type":    "Customer",
#         "party":         pe.get("party") or "default",
#         "party_name":    pe.get("party_name") or "default",
#         "paid_amount":   amount,
#         "received_amount": amount,
#         "source_exchange_rate": exch_rate,
#         "reference_no":  pe.get("reference_no") or pe.get("sale_invoice_no", ""),
#         "reference_date": ref_date_str,
#         "remarks":       pe.get("remarks") or f"POS Payment — {mop}",
#         "mode_of_payment": mop,
#         "docstatus":     1,
#     }

#     if is_refund:
#         # Money goes OUT to customer — Frappe needs paid_from (the cash/bank account)
#         payload["paid_from_account_currency"] = paid_to_currency
#         if paid_to:
#             payload["paid_from"] = paid_to
#     else:
#         # Normal receipt — money comes IN
#         payload["paid_to_account_currency"] = paid_to_currency
#         if paid_to:
#             payload["paid_to"] = paid_to

#     if company:
#         payload["company"] = company

#     # Link to the Frappe Sales Invoice (original invoice for receipts, CN invoice for refunds)
#     if frappe_inv:
#         payload["references"] = [{
#             "reference_doctype": "Sales Invoice",
#             "reference_name":    frappe_inv,
#             "allocated_amount":  amount,
#         }]

#     return payload


# # =============================================================================
# # PUSH ONE PAYMENT ENTRY
# # =============================================================================

# def _push_payment_entry(pe: dict, api_key: str, api_secret: str,
#                         defaults: dict, host: str) -> str | None:
#     """
#     Posts one payment entry to Frappe.
#     Returns Frappe's PAY-xxxxx name on success, None on failure.
#     """
#     pe_id  = pe["id"]
#     inv_no = pe.get("sale_invoice_no", str(pe_id))

#     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()
#     if not frappe_inv:
#         log.warning("Payment %d — Sales Invoice not yet on Frappe, skipping.", pe_id)
#         return None

#     payload = _build_payload(pe, defaults, api_key, api_secret, host)

#     url = f"{host}/api/resource/Payment%20Entry"
#     req = urllib.request.Request(
#         url=url,
#         data=json.dumps(payload, default=lambda o: o.isoformat() if hasattr(o, 'isoformat') else str(o)).encode("utf-8"),
#         method="POST",
#         headers={
#             "Content-Type":  "application/json",
#             "Accept":        "application/json",
#             "Authorization": f"token {api_key}:{api_secret}",
#         },
#     )

#     try:
#         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
#             data = json.loads(resp.read().decode())
#             name = (data.get("data") or {}).get("name", "")
#             log.info("✅ Payment Entry %d → Frappe %s  [%s  %s %.2f]",
#                      pe_id, name, inv_no,
#                      pe.get("currency", ""), float(pe.get("paid_amount", 0)))
#             return name or "SYNCED"

#     except urllib.error.HTTPError as e:
#         try:
#             err = json.loads(e.read().decode())
#             msg = (err.get("exception") or err.get("message") or
#                    str(err.get("_server_messages", "")) or f"HTTP {e.code}")
#         except Exception:
#             msg = f"HTTP {e.code}"

#         if e.code == 409:
#             log.info("Payment %d already on Frappe (409) - marking synced.", pe_id)
#             return "DUPLICATE"

#         # Invoice already paid (is_pos:1 on old invoices) - stop retrying
#         if e.code == 417:
#             _perma = ("already been fully paid", "already paid", "fully paid")
#             if any(p in msg.lower() for p in _perma):
#                 log.info("Payment %d - invoice already paid on Frappe, marking synced.", pe_id)
#                 return "ALREADY_PAID"

#         log.error("FAIL Payment Entry %d  HTTP %s: %s", pe_id, e.code, msg)
#         return None

#     except urllib.error.URLError as e:
#         log.warning("Network error pushing payment %d: %s", pe_id, e.reason)
#         return None

#     except Exception as e:
#         log.error("Unexpected error pushing payment %d: %s", pe_id, e)
#         return None


# # =============================================================================
# # PUBLIC — push all unsynced payment entries
# # =============================================================================

# def push_unsynced_payment_entries() -> dict:
#     """
#     1. Refresh frappe_invoice_ref from parent sales that were confirmed.
#     2. Push each unsynced payment entry to Frappe.
#     3. Mark synced with the returned PAY-xxxxx ref.
#     """
#     result = {"pushed": 0, "failed": 0, "skipped": 0, "total": 0}

#     api_key, api_secret = _get_credentials()
#     if not api_key or not api_secret:
#         log.warning("No credentials — skipping payment entry sync.")
#         return result

#     host     = _get_host()
#     defaults = _get_defaults()

#     # First: pull frappe_refs from confirmed invoices into pending payment entries
#     updated = refresh_frappe_refs()
#     if updated:
#         log.info("Refreshed frappe_invoice_ref on %d payment entry(ies).", updated)

#     entries = get_unsynced_payment_entries()
#     result["total"] = len(entries)

#     if not entries:
#         log.debug("No unsynced payment entries.")
#         return result

#     log.info("Pushing %d payment entry(ies) to Frappe…", len(entries))

#     for pe in entries:
#         frappe_name = _push_payment_entry(pe, api_key, api_secret, defaults, host)
#         if frappe_name:
#             mark_payment_synced(pe["id"], frappe_name)
#             result["pushed"] += 1
#         elif frappe_name is None:
#             # None = permanent skip (no frappe_inv yet), not a real failure
#             result["skipped"] += 1
#         else:
#             result["failed"] += 1

#         time.sleep(3)   # rate limit — 20/min max

#     log.info("Payment sync done — ✅ %d pushed  ❌ %d failed  ⏭ %d skipped",
#              result["pushed"], result["failed"], result["skipped"])
#     return result


# # =============================================================================
# # BACKGROUND DAEMON THREAD
# # =============================================================================

# def _sync_loop():
#     log.info("Payment entry sync daemon started (interval=%ds).", SYNC_INTERVAL)
#     while True:
#         if _sync_lock.acquire(blocking=False):
#             try:
#                 push_unsynced_payment_entries()
#             except Exception as e:
#                 log.error("Payment sync cycle error: %s", e)
#             finally:
#                 _sync_lock.release()
#         else:
#             log.debug("Previous payment sync still running — skipping.")
#         time.sleep(SYNC_INTERVAL)


# def start_payment_sync_daemon() -> threading.Thread:
#     """Non-blocking — safe to call from MainWindow.__init__."""
#     global _sync_thread
#     if _sync_thread and _sync_thread.is_alive():
#         return _sync_thread
#     t = threading.Thread(target=_sync_loop, daemon=True, name="PaymentSyncDaemon")
#     t.start()
#     _sync_thread = t
#     log.info("Payment entry sync daemon started.")
#     return t


# # =============================================================================
# # DEBUG
# # =============================================================================

# if __name__ == "__main__":
#     logging.basicConfig(level=logging.INFO,
#                         format="%(asctime)s [%(levelname)s] %(message)s")
#     print("Running one payment entry sync cycle...")
#     r = push_unsynced_payment_entries()
#     print(f"\nResult: {r['pushed']} pushed, {r['failed']} failed, "
#           f"{r['skipped']} skipped (of {r['total']} total)")

# # # # # =============================================================================
# # # # # services/payment_entry_service.py
# # # # #
# # # # # Manages local payment_entries table and syncs them to Frappe.
# # # # #
# # # # # FLOW:
# # # # #   1. When a sale is saved locally → create_payment_entry() stores it locally
# # # # #      with synced=0
# # # # #   2. When the Sales Invoice is confirmed on Frappe (frappe_ref is set) →
# # # # #      push_unsynced_payment_entries() pushes the Payment Entry to Frappe
# # # # #   3. Frappe returns a PAY-xxxxx ref → stored as frappe_payment_ref, synced=1
# # # # #
# # # # # PAYLOAD SENT TO FRAPPE:
# # # # #   POST /api/resource/Payment Entry
# # # # #   {
# # # # #     "doctype":              "Payment Entry",
# # # # #     "payment_type":         "Receive",
# # # # #     "party_type":           "Customer",
# # # # #     "party":                "Cathy",
# # # # #     "paid_to":              "Cash ZWG - H",
# # # # #     "paid_to_account_currency": "USD",
# # # # #     "paid_amount":          32.45,
# # # # #     "received_amount":      32.45,
# # # # #     "source_exchange_rate": 1.0,
# # # # #     "reference_no":         "ACC-SINV-2026-00034",
# # # # #     "reference_date":       "2026-03-19",
# # # # #     "remarks":              "POS Payment — Cash",
# # # # #     "docstatus":            1,
# # # # #     "references": [{
# # # # #         "reference_doctype": "Sales Invoice",
# # # # #         "reference_name":    "ACC-SINV-2026-00565",
# # # # #         "allocated_amount":  32.45
# # # # #     }]
# # # # #   }
# # # # # =============================================================================

# # # # from __future__ import annotations

# # # # import json
# # # # import logging
# # # # import time
# # # # import threading
# # # # import urllib.request
# # # # import urllib.error
# # # # from datetime import date

# # # # log = logging.getLogger("PaymentEntry")

# # # # SYNC_INTERVAL   = 60      # seconds between auto-sync cycles
# # # # REQUEST_TIMEOUT = 30

# # # # # Exchange rate cache: "FROM::TO::DATE" → float
# # # # _RATE_CACHE: dict[str, float] = {}


# # # # def _get_exchange_rate(from_currency: str, to_currency: str,
# # # #                        transaction_date: str,
# # # #                        api_key: str, api_secret: str, host: str) -> float:
# # # #     """
# # # #     Fetch live exchange rate from Frappe.
# # # #     Returns 1.0 for same currency, 0.0 if fetch fails (Frappe uses its own rate).
# # # #     """
# # # #     if not from_currency or from_currency.upper() == to_currency.upper():
# # # #         return 1.0

# # # #     cache_key = f"{from_currency.upper()}::{to_currency.upper()}::{transaction_date}"
# # # #     if cache_key in _RATE_CACHE:
# # # #         return _RATE_CACHE[cache_key]

# # # #     try:
# # # #         import urllib.parse
# # # #         url = (
# # # #             f"{host}/api/method/erpnext.setup.utils.get_exchange_rate"
# # # #             f"?from_currency={urllib.parse.quote(from_currency)}"
# # # #             f"&to_currency={urllib.parse.quote(to_currency)}"
# # # #             f"&transaction_date={transaction_date}"
# # # #         )
# # # #         req = urllib.request.Request(url)
# # # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # # #             data = json.loads(r.read().decode())
# # # #             rate = float(data.get("message") or data.get("result") or 0)
# # # #             if rate > 0:
# # # #                 _RATE_CACHE[cache_key] = rate
# # # #                 log.debug("Rate %s→%s on %s: %.6f", from_currency, to_currency, transaction_date, rate)
# # # #                 return rate
# # # #     except Exception as e:
# # # #         log.debug("Rate fetch failed (%s→%s): %s", from_currency, to_currency, e)

# # # #     return 0.0

# # # # _sync_lock:   threading.Lock          = threading.Lock()
# # # # _sync_thread: threading.Thread | None = None

# # # # # Method → Frappe Mode of Payment name
# # # # _METHOD_MAP = {
# # # #     "CASH":     "Cash",
# # # #     "CARD":     "Credit Card",
# # # #     "C / CARD": "Credit Card",
# # # #     "EFTPOS":   "Credit Card",
# # # #     "CHECK":    "Cheque",
# # # #     "CHEQUE":   "Cheque",
# # # #     "MOBILE":   "Mobile Money",
# # # #     "CREDIT":   "Credit",
# # # #     "TRANSFER": "Bank Transfer",
# # # # }


# # # # # =============================================================================
# # # # # CREDENTIALS / HOST / DEFAULTS
# # # # # =============================================================================

# # # # def _get_credentials() -> tuple[str, str]:
# # # #     try:
# # # #         from services.auth_service import get_session
# # # #         s = get_session()
# # # #         if s.get("api_key") and s.get("api_secret"):
# # # #             return s["api_key"], s["api_secret"]
# # # #     except Exception:
# # # #         pass
# # # #     try:
# # # #         from database.db import get_connection
# # # #         conn = get_connection(); cur = conn.cursor()
# # # #         cur.execute("SELECT api_key, api_secret FROM company_defaults WHERE id = 1")
# # # #         row = cur.fetchone(); conn.close()
# # # #         if row and row[0] and row[1]:
# # # #             return row[0], row[1]
# # # #     except Exception:
# # # #         pass
# # # #     import os
# # # #     return os.environ.get("HAVANO_API_KEY", ""), os.environ.get("HAVANO_API_SECRET", "")


# # # # def _get_host() -> str:
# # # #     try:
# # # #         from models.company_defaults import get_defaults
# # # #         host = (get_defaults() or {}).get("server_api_host", "").strip().rstrip("/")
# # # #         if host:
# # # #             return host
# # # #     except Exception:
# # # #         pass
# # # #     return "https://apk.havano.cloud"


# # # # def _get_defaults() -> dict:
# # # #     try:
# # # #         from models.company_defaults import get_defaults
# # # #         return get_defaults() or {}
# # # #     except Exception:
# # # #         return {}


# # # # # =============================================================================
# # # # # GL ACCOUNT RESOLVER  (which account to credit for each payment method)
# # # # # =============================================================================

# # # # _ACCOUNT_CACHE: dict[str, str] = {}


# # # # def _resolve_paid_to_account(mop_name: str, company: str, currency: str,
# # # #                               api_key: str, api_secret: str, host: str) -> str:
# # # #     """
# # # #     Looks up the GL account for a Mode of Payment from Frappe.
# # # #     Tries to match by currency if multiple accounts exist for the company.
# # # #     Falls back to server_pos_account in company_defaults.
# # # #     """
# # # #     cache_key = f"{mop_name}::{company}::{currency}"
# # # #     if cache_key in _ACCOUNT_CACHE:
# # # #         return _ACCOUNT_CACHE[cache_key]

# # # #     try:
# # # #         import urllib.parse
# # # #         url = (f"{host}/api/resource/Mode%20of%20Payment/"
# # # #                f"{urllib.parse.quote(mop_name)}?fields=[\"accounts\"]")
# # # #         req = urllib.request.Request(url)
# # # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # # #             data     = json.loads(r.read().decode())
# # # #             accounts = (data.get("data") or {}).get("accounts", [])

# # # #         company_accts = [a for a in accounts
# # # #                          if not company or a.get("company") == company]

# # # #         # Prefer account whose name contains the currency code
# # # #         matched = ""
# # # #         if currency:
# # # #             for a in company_accts:
# # # #                 if currency.upper() in (a.get("default_account") or "").upper():
# # # #                     matched = a["default_account"]; break

# # # #         if not matched and company_accts:
# # # #             matched = company_accts[0].get("default_account", "")

# # # #         if matched:
# # # #             _ACCOUNT_CACHE[cache_key] = matched
# # # #             return matched

# # # #     except Exception as e:
# # # #         log.debug("MOP account lookup failed for '%s': %s", mop_name, e)

# # # #     # Fallback
# # # #     fallback = _get_defaults().get("server_pos_account", "").strip()
# # # #     if fallback:
# # # #         _ACCOUNT_CACHE[cache_key] = fallback
# # # #         return fallback

# # # #     log.warning("No GL account for MOP '%s' currency=%s — Payment Entry may fail.",
# # # #                 mop_name, currency)
# # # #     return ""


# # # # # =============================================================================
# # # # # LOCAL DB  — create / read / update payment_entries
# # # # # =============================================================================

# # # # def create_payment_entry(sale: dict, override_rate: float = None,
# # # #                          override_account: str = None) -> int | None:
# # # #     """
# # # #     Called immediately after a sale is saved locally.
# # # #     Stores a payment_entry row with synced=0.
# # # #     Returns the new payment_entry id, or None on error.

# # # #     Will only create the entry once per sale (idempotent).
# # # #     """
# # # #     from database.db import get_connection
# # # #     conn = get_connection(); cur = conn.cursor()

# # # #     # Idempotency: don't create twice for the same sale
# # # #     cur.execute("SELECT id FROM payment_entries WHERE sale_id = ?", (sale["id"],))
# # # #     if cur.fetchone():
# # # #         conn.close()
# # # #         return None

# # # #     customer   = (sale.get("customer_name") or "default").strip()
# # # #     currency   = (sale.get("currency")      or "USD").strip().upper()
# # # #     amount     = float(sale.get("total")    or 0)
# # # #     inv_no     = sale.get("invoice_no", "")
# # # #     inv_date   = sale.get("invoice_date") or date.today().isoformat()
# # # #     method     = str(sale.get("method", "CASH")).upper().strip()
# # # #     mop        = _METHOD_MAP.get(method, "Cash")

# # # #     # Use override rate (from split) or fetch from Frappe
# # # #     if override_rate is not None:
# # # #         exch_rate = override_rate
# # # #     else:
# # # #         try:
# # # #             api_key, api_secret = _get_credentials()
# # # #             host = _get_host()
# # # #             defaults = _get_defaults()
# # # #             company_currency = defaults.get("server_company_currency", "USD").strip().upper() or "USD"
# # # #             exch_rate = _get_exchange_rate(
# # # #                 currency, company_currency, inv_date, api_key, api_secret, host
# # # #             ) if currency != company_currency else 1.0
# # # #         except Exception:
# # # #             exch_rate = 1.0

# # # #     cur.execute("""
# # # #         INSERT INTO payment_entries (
# # # #             sale_id, sale_invoice_no, frappe_invoice_ref,
# # # #             party, party_name,
# # # #             paid_amount, received_amount, source_exchange_rate,
# # # #             paid_to_account_currency, currency,
# # # #             mode_of_payment,
# # # #             reference_no, reference_date,
# # # #             remarks, synced
# # # #         ) OUTPUT INSERTED.id
# # # #         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # # #     """, (
# # # #         sale["id"], inv_no,
# # # #         sale.get("frappe_ref") or None,
# # # #         customer, customer,
# # # #         amount, amount, exch_rate or 1.0,
# # # #         currency, currency,
# # # #         mop,
# # # #         inv_no, inv_date,
# # # #         f"POS Payment — {mop}",
# # # #     ))
# # # #     new_id = int(cur.fetchone()[0])
# # # #     conn.commit(); conn.close()
# # # #     log.debug("Payment entry %d created locally for sale %s", new_id, inv_no)
# # # #     return new_id


# # # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # # #     """
# # # #     Called when cashier uses Split payment.
# # # #     Creates one payment_entry row per currency in splits list.
# # # #     splits = [{"mode": "CASH", "currency": "USD", "amount": 5.0,
# # # #                "rate": 1.0, "base_amount": 5.0, "account": "Cash - AT"}, ...]
# # # #     Returns list of new payment_entry ids.
# # # #     """
# # # #     ids = []
# # # #     for split in splits:
# # # #         if not split.get("amount") or float(split["amount"]) <= 0:
# # # #             continue
# # # #         # Build a sale-like dict with the split's currency and amount
# # # #         split_sale = dict(sale)
# # # #         split_sale["currency"]      = split.get("currency", "USD")
# # # #         split_sale["total"]         = float(split.get("amount", 0))
# # # #         split_sale["method"]        = split.get("mode", "CASH")
# # # #         # Override exchange rate from split data
# # # #         new_id = create_payment_entry(
# # # #             split_sale,
# # # #             override_rate=float(split.get("rate", 1.0)),
# # # #             override_account=split.get("account", ""),
# # # #         )
# # # #         if new_id:
# # # #             ids.append(new_id)
# # # #     return ids


# # # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # # #     """
# # # #     Creates one payment_entry per currency from a split payment.
# # # #     Groups splits by currency, sums amounts, creates one entry each.
# # # #     Returns list of created payment_entry ids.
# # # #     """
# # # #     from datetime import date as _date

# # # #     # Group by currency
# # # #     by_currency: dict[str, dict] = {}
# # # #     for s in splits:
# # # #         curr = s.get("account_currency", "USD").upper()
# # # #         if curr not in by_currency:
# # # #             by_currency[curr] = {
# # # #                 "currency":      curr,
# # # #                 "paid_amount":   0.0,
# # # #                 "base_value":    0.0,
# # # #                 "rate":          s.get("rate", 1.0),
# # # #                 "account_name":  s.get("account_name", ""),
# # # #                 "mode":          s.get("mode", "Cash"),
# # # #             }
# # # #         by_currency[curr]["paid_amount"] += s.get("amount_paid", 0.0)
# # # #         by_currency[curr]["base_value"]  += s.get("base_value",  0.0)

# # # #     ids = []
# # # #     inv_no   = sale.get("invoice_no", "")
# # # #     inv_date = sale.get("invoice_date") or _date.today().isoformat()
# # # #     customer = (sale.get("customer_name") or "default").strip()

# # # #     from database.db import get_connection
# # # #     conn = get_connection(); cur = conn.cursor()

# # # #     for curr, grp in by_currency.items():
# # # #         # Idempotency: skip if already exists for this sale+currency
# # # #         cur.execute(
# # # #             "SELECT id FROM payment_entries WHERE sale_id=? AND currency=?",
# # # #             (sale["id"], curr)
# # # #         )
# # # #         if cur.fetchone():
# # # #             continue

# # # #         mop = _METHOD_MAP.get(grp["mode"].upper(), "Cash")

# # # #         cur.execute("""
# # # #             INSERT INTO payment_entries (
# # # #                 sale_id, sale_invoice_no, frappe_invoice_ref,
# # # #                 party, party_name,
# # # #                 paid_amount, received_amount, source_exchange_rate,
# # # #                 paid_to_account_currency, currency,
# # # #                 paid_to,
# # # #                 mode_of_payment,
# # # #                 reference_no, reference_date,
# # # #                 remarks, synced
# # # #             ) OUTPUT INSERTED.id
# # # #             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # # #         """, (
# # # #             sale["id"], inv_no,
# # # #             sale.get("frappe_ref") or None,
# # # #             customer, customer,
# # # #             grp["paid_amount"],
# # # #             grp["base_value"],
# # # #             float(grp["rate"] or 1.0),
# # # #             curr, curr,
# # # #             grp["account_name"],
# # # #             mop,
# # # #             inv_no, inv_date,
# # # #             f"POS Split Payment — {mop} ({curr})",
# # # #         ))
# # # #         new_id = int(cur.fetchone()[0])
# # # #         ids.append(new_id)
# # # #         log.debug("Split payment entry %d created: %s %.2f %s",
# # # #                   new_id, curr, grp["paid_amount"], inv_no)

# # # #     conn.commit(); conn.close()
# # # #     return ids


# # # # def get_unsynced_payment_entries() -> list[dict]:
# # # #     """Returns payment entries that are ready to push (synced=0)."""
# # # #     from database.db import get_connection, fetchall_dicts
# # # #     conn = get_connection(); cur = conn.cursor()
# # # #     cur.execute("""
# # # #         SELECT pe.*, s.frappe_ref AS sale_frappe_ref
# # # #         FROM payment_entries pe
# # # #         LEFT JOIN sales s ON s.id = pe.sale_id
# # # #         WHERE pe.synced = 0
# # # #           AND (pe.frappe_invoice_ref IS NOT NULL
# # # #                OR s.frappe_ref IS NOT NULL)
# # # #         ORDER BY pe.id
# # # #     """)
# # # #     rows = fetchall_dicts(cur); conn.close()
# # # #     return rows


# # # # def mark_payment_synced(pe_id: int, frappe_payment_ref: str = "") -> None:
# # # #     from database.db import get_connection
# # # #     conn = get_connection(); cur = conn.cursor()
# # # #     cur.execute(
# # # #         "UPDATE payment_entries SET synced=1, frappe_payment_ref=? WHERE id=?",
# # # #         (frappe_payment_ref or None, pe_id)
# # # #     )
# # # #     # Also update the sales row
# # # #     cur.execute("""
# # # #         UPDATE sales SET payment_entry_ref=?, payment_synced=1
# # # #         WHERE id = (SELECT sale_id FROM payment_entries WHERE id=?)
# # # #     """, (frappe_payment_ref or None, pe_id))
# # # #     conn.commit(); conn.close()


# # # # def refresh_frappe_refs() -> int:
# # # #     """
# # # #     For payment entries that have no frappe_invoice_ref yet, copy it from
# # # #     the parent sale's frappe_ref. Call this before pushing payments.
# # # #     Returns count updated.
# # # #     """
# # # #     from database.db import get_connection
# # # #     conn = get_connection(); cur = conn.cursor()
# # # #     cur.execute("""
# # # #         UPDATE pe
# # # #         SET pe.frappe_invoice_ref = s.frappe_ref
# # # #         FROM payment_entries pe
# # # #         JOIN sales s ON s.id = pe.sale_id
# # # #         WHERE pe.synced = 0
# # # #           AND (pe.frappe_invoice_ref IS NULL OR pe.frappe_invoice_ref = '')
# # # #           AND s.frappe_ref IS NOT NULL AND s.frappe_ref != ''
# # # #     """)
# # # #     count = cur.rowcount
# # # #     conn.commit(); conn.close()
# # # #     return count


# # # # # =============================================================================
# # # # # BUILD FRAPPE PAYLOAD
# # # # # =============================================================================

# # # # def _build_payload(pe: dict, defaults: dict,
# # # #                    api_key: str, api_secret: str, host: str) -> dict:
# # # #     company  = defaults.get("server_company", "")
# # # #     currency = (pe.get("currency") or pe.get("paid_to_account_currency") or "USD").upper()
# # # #     mop      = pe.get("mode_of_payment") or "Cash"
# # # #     amount   = float(pe.get("paid_amount") or 0)
# # # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()

# # # #     paid_to = _resolve_paid_to_account(mop, company, currency, api_key, api_secret, host)

# # # #     payload = {
# # # #         "doctype":                  "Payment Entry",
# # # #         "payment_type":             "Receive",
# # # #         "party_type":               "Customer",
# # # #         "party":                    pe.get("party") or "default",
# # # #         "party_name":               pe.get("party_name") or "default",
# # # #         "paid_to_account_currency": currency,
# # # #         "paid_amount":              amount,
# # # #         "received_amount":          amount,
# # # #         "source_exchange_rate":     float(pe.get("source_exchange_rate") or 1.0),
# # # #         "reference_no":             pe.get("reference_no") or pe.get("sale_invoice_no", ""),
# # # #         "reference_date":           pe.get("reference_date") or date.today().isoformat(),
# # # #         "remarks":                  pe.get("remarks") or f"POS Payment — {mop}",
# # # #         "mode_of_payment":          mop,
# # # #         "docstatus":                1,
# # # #     }

# # # #     if paid_to:
# # # #         payload["paid_to"] = paid_to
# # # #     if company:
# # # #         payload["company"] = company

# # # #     # Link to the Sales Invoice on Frappe
# # # #     if frappe_inv:
# # # #         payload["references"] = [{
# # # #             "reference_doctype": "Sales Invoice",
# # # #             "reference_name":    frappe_inv,
# # # #             "allocated_amount":  amount,
# # # #         }]

# # # #     return payload


# # # # # =============================================================================
# # # # # PUSH ONE PAYMENT ENTRY
# # # # # =============================================================================

# # # # def _push_payment_entry(pe: dict, api_key: str, api_secret: str,
# # # #                         defaults: dict, host: str) -> str | None:
# # # #     """
# # # #     Posts one payment entry to Frappe.
# # # #     Returns Frappe's PAY-xxxxx name on success, None on failure.
# # # #     """
# # # #     pe_id  = pe["id"]
# # # #     inv_no = pe.get("sale_invoice_no", str(pe_id))

# # # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()
# # # #     if not frappe_inv:
# # # #         log.warning("Payment %d — Sales Invoice not yet on Frappe, skipping.", pe_id)
# # # #         return None

# # # #     payload = _build_payload(pe, defaults, api_key, api_secret, host)

# # # #     url = f"{host}/api/resource/Payment%20Entry"
# # # #     req = urllib.request.Request(
# # # #         url=url,
# # # #         data=json.dumps(payload).encode("utf-8"),
# # # #         method="POST",
# # # #         headers={
# # # #             "Content-Type":  "application/json",
# # # #             "Accept":        "application/json",
# # # #             "Authorization": f"token {api_key}:{api_secret}",
# # # #         },
# # # #     )

# # # #     try:
# # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
# # # #             data = json.loads(resp.read().decode())
# # # #             name = (data.get("data") or {}).get("name", "")
# # # #             log.info("✅ Payment Entry %d → Frappe %s  [%s  %s %.2f]",
# # # #                      pe_id, name, inv_no,
# # # #                      pe.get("currency", ""), float(pe.get("paid_amount", 0)))
# # # #             return name or "SYNCED"

# # # #     except urllib.error.HTTPError as e:
# # # #         try:
# # # #             err = json.loads(e.read().decode())
# # # #             msg = (err.get("exception") or err.get("message") or
# # # #                    str(err.get("_server_messages", "")) or f"HTTP {e.code}")
# # # #         except Exception:
# # # #             msg = f"HTTP {e.code}"

# # # #         if e.code == 409:
# # # #             log.info("Payment %d already on Frappe (409) — marking synced.", pe_id)
# # # #             return "DUPLICATE"

# # # #         log.error("❌ Payment Entry %d  HTTP %s: %s", pe_id, e.code, msg)
# # # #         return None

# # # #     except urllib.error.URLError as e:
# # # #         log.warning("Network error pushing payment %d: %s", pe_id, e.reason)
# # # #         return None

# # # #     except Exception as e:
# # # #         log.error("Unexpected error pushing payment %d: %s", pe_id, e)
# # # #         return None


# # # # # =============================================================================
# # # # # PUBLIC — push all unsynced payment entries
# # # # # =============================================================================

# # # # def push_unsynced_payment_entries() -> dict:
# # # #     """
# # # #     1. Refresh frappe_invoice_ref from parent sales that were confirmed.
# # # #     2. Push each unsynced payment entry to Frappe.
# # # #     3. Mark synced with the returned PAY-xxxxx ref.
# # # #     """
# # # #     result = {"pushed": 0, "failed": 0, "skipped": 0, "total": 0}

# # # #     api_key, api_secret = _get_credentials()
# # # #     if not api_key or not api_secret:
# # # #         log.warning("No credentials — skipping payment entry sync.")
# # # #         return result

# # # #     host     = _get_host()
# # # #     defaults = _get_defaults()

# # # #     # First: pull frappe_refs from confirmed invoices into pending payment entries
# # # #     updated = refresh_frappe_refs()
# # # #     if updated:
# # # #         log.info("Refreshed frappe_invoice_ref on %d payment entry(ies).", updated)

# # # #     entries = get_unsynced_payment_entries()
# # # #     result["total"] = len(entries)

# # # #     if not entries:
# # # #         log.debug("No unsynced payment entries.")
# # # #         return result

# # # #     log.info("Pushing %d payment entry(ies) to Frappe…", len(entries))

# # # #     for pe in entries:
# # # #         frappe_name = _push_payment_entry(pe, api_key, api_secret, defaults, host)
# # # #         if frappe_name:
# # # #             mark_payment_synced(pe["id"], frappe_name)
# # # #             result["pushed"] += 1
# # # #         elif frappe_name is None:
# # # #             # None = permanent skip (no frappe_inv yet), not a real failure
# # # #             result["skipped"] += 1
# # # #         else:
# # # #             result["failed"] += 1

# # # #         time.sleep(3)   # rate limit — 20/min max

# # # #     log.info("Payment sync done — ✅ %d pushed  ❌ %d failed  ⏭ %d skipped",
# # # #              result["pushed"], result["failed"], result["skipped"])
# # # #     return result


# # # # # =============================================================================
# # # # # BACKGROUND DAEMON THREAD
# # # # # =============================================================================

# # # # def _sync_loop():
# # # #     log.info("Payment entry sync daemon started (interval=%ds).", SYNC_INTERVAL)
# # # #     while True:
# # # #         if _sync_lock.acquire(blocking=False):
# # # #             try:
# # # #                 push_unsynced_payment_entries()
# # # #             except Exception as e:
# # # #                 log.error("Payment sync cycle error: %s", e)
# # # #             finally:
# # # #                 _sync_lock.release()
# # # #         else:
# # # #             log.debug("Previous payment sync still running — skipping.")
# # # #         time.sleep(SYNC_INTERVAL)


# # # # def start_payment_sync_daemon() -> threading.Thread:
# # # #     """Non-blocking — safe to call from MainWindow.__init__."""
# # # #     global _sync_thread
# # # #     if _sync_thread and _sync_thread.is_alive():
# # # #         return _sync_thread
# # # #     t = threading.Thread(target=_sync_loop, daemon=True, name="PaymentSyncDaemon")
# # # #     t.start()
# # # #     _sync_thread = t
# # # #     log.info("Payment entry sync daemon started.")
# # # #     return t


# # # # # =============================================================================
# # # # # DEBUG
# # # # # =============================================================================

# # # # if __name__ == "__main__":
# # # #     logging.basicConfig(level=logging.INFO,
# # # #                         format="%(asctime)s [%(levelname)s] %(message)s")
# # # #     print("Running one payment entry sync cycle...")
# # # #     r = push_unsynced_payment_entries()
# # # #     print(f"\nResult: {r['pushed']} pushed, {r['failed']} failed, "
# # # #           f"{r['skipped']} skipped (of {r['total']} total)")
# # # # =============================================================================
# # # # services/payment_entry_service.py
# # # #
# # # # Manages local payment_entries table and syncs them to Frappe.
# # # #
# # # # FLOW:
# # # #   1. When a sale is saved locally → create_payment_entry() stores it locally
# # # #      with synced=0
# # # #   2. When the Sales Invoice is confirmed on Frappe (frappe_ref is set) →
# # # #      push_unsynced_payment_entries() pushes the Payment Entry to Frappe
# # # #   3. Frappe returns a PAY-xxxxx ref → stored as frappe_payment_ref, synced=1
# # # #
# # # # PAYLOAD SENT TO FRAPPE:
# # # #   POST /api/resource/Payment Entry
# # # #   {
# # # #     "doctype":              "Payment Entry",
# # # #     "payment_type":         "Receive",
# # # #     "party_type":           "Customer",
# # # #     "party":                "Cathy",
# # # #     "paid_to":              "Cash ZWG - H",
# # # #     "paid_to_account_currency": "USD",
# # # #     "paid_amount":          32.45,
# # # #     "received_amount":      32.45,
# # # #     "source_exchange_rate": 1.0,
# # # #     "reference_no":         "ACC-SINV-2026-00034",
# # # #     "reference_date":       "2026-03-19",
# # # #     "remarks":              "POS Payment — Cash",
# # # #     "docstatus":            1,
# # # #     "references": [{
# # # #         "reference_doctype": "Sales Invoice",
# # # #         "reference_name":    "ACC-SINV-2026-00565",
# # # #         "allocated_amount":  32.45
# # # #     }]
# # # #   }
# # # # =============================================================================

# # # from __future__ import annotations

# # # import json
# # # import logging
# # # import time
# # # import threading
# # # import urllib.request
# # # import urllib.error
# # # from datetime import date

# # # log = logging.getLogger("PaymentEntry")

# # # SYNC_INTERVAL   = 60      # seconds between auto-sync cycles
# # # REQUEST_TIMEOUT = 30

# # # # Exchange rate cache: "FROM::TO::DATE" → float
# # # _RATE_CACHE: dict[str, float] = {}


# # # def _get_exchange_rate(from_currency: str, to_currency: str,
# # #                        transaction_date: str,
# # #                        api_key: str, api_secret: str, host: str) -> float:
# # #     """
# # #     Fetch live exchange rate from Frappe.
# # #     Returns 1.0 for same currency, 0.0 if fetch fails (Frappe uses its own rate).
# # #     """
# # #     if not from_currency or from_currency.upper() == to_currency.upper():
# # #         return 1.0

# # #     cache_key = f"{from_currency.upper()}::{to_currency.upper()}::{transaction_date}"
# # #     if cache_key in _RATE_CACHE:
# # #         return _RATE_CACHE[cache_key]

# # #     try:
# # #         import urllib.parse
# # #         url = (
# # #             f"{host}/api/method/erpnext.setup.utils.get_exchange_rate"
# # #             f"?from_currency={urllib.parse.quote(from_currency)}"
# # #             f"&to_currency={urllib.parse.quote(to_currency)}"
# # #             f"&transaction_date={transaction_date}"
# # #         )
# # #         req = urllib.request.Request(url)
# # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # #             data = json.loads(r.read().decode())
# # #             rate = float(data.get("message") or data.get("result") or 0)
# # #             if rate > 0:
# # #                 _RATE_CACHE[cache_key] = rate
# # #                 log.debug("Rate %s→%s on %s: %.6f", from_currency, to_currency, transaction_date, rate)
# # #                 return rate
# # #     except Exception as e:
# # #         log.debug("Rate fetch failed (%s→%s): %s", from_currency, to_currency, e)

# # #     return 0.0

# # # _sync_lock:   threading.Lock          = threading.Lock()
# # # _sync_thread: threading.Thread | None = None

# # # # Method → Frappe Mode of Payment name
# # # _METHOD_MAP = {
# # #     "CASH":     "Cash",
# # #     "CARD":     "Credit Card",
# # #     "C / CARD": "Credit Card",
# # #     "EFTPOS":   "Credit Card",
# # #     "CHECK":    "Cheque",
# # #     "CHEQUE":   "Cheque",
# # #     "MOBILE":   "Mobile Money",
# # #     "CREDIT":   "Credit",
# # #     "TRANSFER": "Bank Transfer",
# # # }


# # # # =============================================================================
# # # # CREDENTIALS / HOST / DEFAULTS
# # # # =============================================================================

# # # def _get_credentials() -> tuple[str, str]:
# # #     try:
# # #         from services.auth_service import get_session
# # #         s = get_session()
# # #         if s.get("api_key") and s.get("api_secret"):
# # #             return s["api_key"], s["api_secret"]
# # #     except Exception:
# # #         pass
# # #     try:
# # #         from database.db import get_connection
# # #         conn = get_connection(); cur = conn.cursor()
# # #         cur.execute("SELECT api_key, api_secret FROM company_defaults WHERE id = 1")
# # #         row = cur.fetchone(); conn.close()
# # #         if row and row[0] and row[1]:
# # #             return row[0], row[1]
# # #     except Exception:
# # #         pass
# # #     import os
# # #     return os.environ.get("HAVANO_API_KEY", ""), os.environ.get("HAVANO_API_SECRET", "")


# # # def _get_host() -> str:
# # #     try:
# # #         from models.company_defaults import get_defaults
# # #         host = (get_defaults() or {}).get("server_api_host", "").strip().rstrip("/")
# # #         if host:
# # #             return host
# # #     except Exception:
# # #         pass
# # #     return "https://apk.havano.cloud"


# # # def _get_defaults() -> dict:
# # #     try:
# # #         from models.company_defaults import get_defaults
# # #         return get_defaults() or {}
# # #     except Exception:
# # #         return {}


# # # # =============================================================================
# # # # GL ACCOUNT RESOLVER  (which account to credit for each payment method)
# # # # =============================================================================

# # # _ACCOUNT_CACHE: dict[str, str] = {}


# # # def _resolve_paid_to_account(mop_name: str, company: str, currency: str,
# # #                               api_key: str, api_secret: str, host: str) -> str:
# # #     """
# # #     Looks up the GL account for a Mode of Payment from Frappe.
# # #     Tries to match by currency if multiple accounts exist for the company.
# # #     Falls back to server_pos_account in company_defaults.
# # #     """
# # #     cache_key = f"{mop_name}::{company}::{currency}"
# # #     if cache_key in _ACCOUNT_CACHE:
# # #         return _ACCOUNT_CACHE[cache_key]

# # #     try:
# # #         import urllib.parse
# # #         url = (f"{host}/api/resource/Mode%20of%20Payment/"
# # #                f"{urllib.parse.quote(mop_name)}?fields=[\"accounts\"]")
# # #         req = urllib.request.Request(url)
# # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # #             data     = json.loads(r.read().decode())
# # #             accounts = (data.get("data") or {}).get("accounts", [])

# # #         company_accts = [a for a in accounts
# # #                          if not company or a.get("company") == company]

# # #         # Prefer account whose name contains the currency code
# # #         matched = ""
# # #         if currency:
# # #             for a in company_accts:
# # #                 if currency.upper() in (a.get("default_account") or "").upper():
# # #                     matched = a["default_account"]; break

# # #         if not matched and company_accts:
# # #             matched = company_accts[0].get("default_account", "")

# # #         if matched:
# # #             _ACCOUNT_CACHE[cache_key] = matched
# # #             return matched

# # #     except Exception as e:
# # #         log.debug("MOP account lookup failed for '%s': %s", mop_name, e)

# # #     # Fallback
# # #     fallback = _get_defaults().get("server_pos_account", "").strip()
# # #     if fallback:
# # #         _ACCOUNT_CACHE[cache_key] = fallback
# # #         return fallback

# # #     log.warning("No GL account for MOP '%s' currency=%s — Payment Entry may fail.",
# # #                 mop_name, currency)
# # #     return ""


# # # # =============================================================================
# # # # LOCAL DB  — create / read / update payment_entries
# # # # =============================================================================

# # # def create_payment_entry(sale: dict, override_rate: float = None,
# # #                          override_account: str = None) -> int | None:
# # #     """
# # #     Called immediately after a sale is saved locally.
# # #     Stores a payment_entry row with synced=0.
# # #     Returns the new payment_entry id, or None on error.

# # #     Will only create the entry once per sale (idempotent).
# # #     """
# # #     from database.db import get_connection
# # #     conn = get_connection(); cur = conn.cursor()

# # #     # Idempotency: don't create twice for the same sale
# # #     cur.execute("SELECT id FROM payment_entries WHERE sale_id = ?", (sale["id"],))
# # #     if cur.fetchone():
# # #         conn.close()
# # #         return None

# # #     customer   = (sale.get("customer_name") or "default").strip()
# # #     currency   = (sale.get("currency")      or "USD").strip().upper()
# # #     amount     = float(sale.get("total")    or 0)
# # #     inv_no     = sale.get("invoice_no", "")
# # #     inv_date   = sale.get("invoice_date") or date.today().isoformat()
# # #     method     = str(sale.get("method", "CASH")).upper().strip()
# # #     mop        = _METHOD_MAP.get(method, "Cash")

# # #     # Use override rate (from split) or fetch from Frappe
# # #     if override_rate is not None:
# # #         exch_rate = override_rate
# # #     else:
# # #         try:
# # #             api_key, api_secret = _get_credentials()
# # #             host = _get_host()
# # #             defaults = _get_defaults()
# # #             company_currency = defaults.get("server_company_currency", "USD").strip().upper() or "USD"
# # #             exch_rate = _get_exchange_rate(
# # #                 currency, company_currency, inv_date, api_key, api_secret, host
# # #             ) if currency != company_currency else 1.0
# # #         except Exception:
# # #             exch_rate = 1.0

# # #     cur.execute("""
# # #         INSERT INTO payment_entries (
# # #             sale_id, sale_invoice_no, frappe_invoice_ref,
# # #             party, party_name,
# # #             paid_amount, received_amount, source_exchange_rate,
# # #             paid_to_account_currency, currency,
# # #             mode_of_payment,
# # #             reference_no, reference_date,
# # #             remarks, synced
# # #         ) OUTPUT INSERTED.id
# # #         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # #     """, (
# # #         sale["id"], inv_no,
# # #         sale.get("frappe_ref") or None,
# # #         customer, customer,
# # #         amount, amount, exch_rate or 1.0,
# # #         currency, currency,
# # #         mop,
# # #         inv_no, inv_date,
# # #         f"POS Payment — {mop}",
# # #     ))
# # #     new_id = int(cur.fetchone()[0])
# # #     conn.commit(); conn.close()
# # #     log.debug("Payment entry %d created locally for sale %s", new_id, inv_no)
# # #     return new_id


# # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # #     """
# # #     Called when cashier uses Split payment.
# # #     Creates one payment_entry row per currency in splits list.
# # #     splits = [{"mode": "CASH", "currency": "USD", "amount": 5.0,
# # #                "rate": 1.0, "base_amount": 5.0, "account": "Cash - AT"}, ...]
# # #     Returns list of new payment_entry ids.
# # #     """
# # #     ids = []
# # #     for split in splits:
# # #         if not split.get("amount") or float(split["amount"]) <= 0:
# # #             continue
# # #         # Build a sale-like dict with the split's currency and amount
# # #         split_sale = dict(sale)
# # #         split_sale["currency"]      = split.get("currency", "USD")
# # #         split_sale["total"]         = float(split.get("amount", 0))
# # #         split_sale["method"]        = split.get("mode", "CASH")
# # #         # Override exchange rate from split data
# # #         new_id = create_payment_entry(
# # #             split_sale,
# # #             override_rate=float(split.get("rate", 1.0)),
# # #             override_account=split.get("account", ""),
# # #         )
# # #         if new_id:
# # #             ids.append(new_id)
# # #     return ids


# # # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# # #     """
# # #     Creates one payment_entry per currency from a split payment.
# # #     Groups splits by currency, sums amounts, creates one entry each.
# # #     Returns list of created payment_entry ids.
# # #     """
# # #     from datetime import date as _date

# # #     # Group by currency
# # #     by_currency: dict[str, dict] = {}
# # #     for s in splits:
# # #         curr = s.get("account_currency", "USD").upper()
# # #         if curr not in by_currency:
# # #             by_currency[curr] = {
# # #                 "currency":      curr,
# # #                 "paid_amount":   0.0,
# # #                 "base_value":    0.0,
# # #                 "rate":          s.get("rate", 1.0),
# # #                 "account_name":  s.get("account_name", ""),
# # #                 "mode":          s.get("mode", "Cash"),
# # #             }
# # #         by_currency[curr]["paid_amount"] += s.get("amount_paid", 0.0)
# # #         by_currency[curr]["base_value"]  += s.get("base_value",  0.0)

# # #     ids = []
# # #     inv_no   = sale.get("invoice_no", "")
# # #     inv_date = sale.get("invoice_date") or _date.today().isoformat()
# # #     customer = (sale.get("customer_name") or "default").strip()

# # #     from database.db import get_connection
# # #     conn = get_connection(); cur = conn.cursor()

# # #     for curr, grp in by_currency.items():
# # #         # Idempotency: skip if already exists for this sale+currency
# # #         cur.execute(
# # #             "SELECT id FROM payment_entries WHERE sale_id=? AND currency=?",
# # #             (sale["id"], curr)
# # #         )
# # #         if cur.fetchone():
# # #             continue

# # #         mop = _METHOD_MAP.get(grp["mode"].upper(), "Cash")

# # #         cur.execute("""
# # #             INSERT INTO payment_entries (
# # #                 sale_id, sale_invoice_no, frappe_invoice_ref,
# # #                 party, party_name,
# # #                 paid_amount, received_amount, source_exchange_rate,
# # #                 paid_to_account_currency, currency,
# # #                 paid_to,
# # #                 mode_of_payment,
# # #                 reference_no, reference_date,
# # #                 remarks, synced
# # #             ) OUTPUT INSERTED.id
# # #             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# # #         """, (
# # #             sale["id"], inv_no,
# # #             sale.get("frappe_ref") or None,
# # #             customer, customer,
# # #             grp["paid_amount"],
# # #             grp["base_value"],
# # #             float(grp["rate"] or 1.0),
# # #             curr, curr,
# # #             grp["account_name"],
# # #             mop,
# # #             inv_no, inv_date,
# # #             f"POS Split Payment — {mop} ({curr})",
# # #         ))
# # #         new_id = int(cur.fetchone()[0])
# # #         ids.append(new_id)
# # #         log.debug("Split payment entry %d created: %s %.2f %s",
# # #                   new_id, curr, grp["paid_amount"], inv_no)

# # #     conn.commit(); conn.close()
# # #     return ids


# # # def get_unsynced_payment_entries() -> list[dict]:
# # #     """Returns payment entries that are ready to push (synced=0)."""
# # #     from database.db import get_connection, fetchall_dicts
# # #     conn = get_connection(); cur = conn.cursor()
# # #     cur.execute("""
# # #         SELECT pe.*, s.frappe_ref AS sale_frappe_ref
# # #         FROM payment_entries pe
# # #         LEFT JOIN sales s ON s.id = pe.sale_id
# # #         WHERE pe.synced = 0
# # #           AND (pe.frappe_invoice_ref IS NOT NULL
# # #                OR s.frappe_ref IS NOT NULL)
# # #         ORDER BY pe.id
# # #     """)
# # #     rows = fetchall_dicts(cur); conn.close()
# # #     return rows


# # # def mark_payment_synced(pe_id: int, frappe_payment_ref: str = "") -> None:
# # #     from database.db import get_connection
# # #     conn = get_connection(); cur = conn.cursor()
# # #     cur.execute(
# # #         "UPDATE payment_entries SET synced=1, frappe_payment_ref=? WHERE id=?",
# # #         (frappe_payment_ref or None, pe_id)
# # #     )
# # #     # Also update the sales row
# # #     cur.execute("""
# # #         UPDATE sales SET payment_entry_ref=?, payment_synced=1
# # #         WHERE id = (SELECT sale_id FROM payment_entries WHERE id=?)
# # #     """, (frappe_payment_ref or None, pe_id))
# # #     conn.commit(); conn.close()


# # # def refresh_frappe_refs() -> int:
# # #     """
# # #     For payment entries that have no frappe_invoice_ref yet, copy it from
# # #     the parent sale's frappe_ref. Call this before pushing payments.
# # #     Returns count updated.
# # #     """
# # #     from database.db import get_connection
# # #     conn = get_connection(); cur = conn.cursor()
# # #     cur.execute("""
# # #         UPDATE pe
# # #         SET pe.frappe_invoice_ref = s.frappe_ref
# # #         FROM payment_entries pe
# # #         JOIN sales s ON s.id = pe.sale_id
# # #         WHERE pe.synced = 0
# # #           AND (pe.frappe_invoice_ref IS NULL OR pe.frappe_invoice_ref = '')
# # #           AND s.frappe_ref IS NOT NULL AND s.frappe_ref != ''
# # #     """)
# # #     count = cur.rowcount
# # #     conn.commit(); conn.close()
# # #     return count


# # # # =============================================================================
# # # # BUILD FRAPPE PAYLOAD
# # # # =============================================================================

# # # def _build_payload(pe: dict, defaults: dict,
# # #                    api_key: str, api_secret: str, host: str) -> dict:
# # #     company  = defaults.get("server_company", "")
# # #     currency = (pe.get("currency") or pe.get("paid_to_account_currency") or "USD").upper()
# # #     mop      = pe.get("mode_of_payment") or "Cash"
# # #     amount   = float(pe.get("paid_amount") or 0)
# # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()

# # #     # Use local gl_accounts table first (synced from Frappe)
# # #     paid_to          = (pe.get("paid_to") or "").strip()
# # #     paid_to_currency = currency
# # #     if not paid_to:
# # #         try:
# # #             from models.gl_account import get_account_for_payment
# # #             acct = get_account_for_payment(currency, company)
# # #             if acct:
# # #                 paid_to          = acct["name"]
# # #                 paid_to_currency = acct["account_currency"]
# # #         except Exception as _e:
# # #             log.debug("gl_account lookup failed: %s", _e)

# # #     # Fallback to live Frappe lookup
# # #     if not paid_to:
# # #         paid_to = _resolve_paid_to_account(mop, company, currency, api_key, api_secret, host)

# # #     # Use local exchange rate if not stored
# # #     exch_rate = float(pe.get("source_exchange_rate") or 1.0)
# # #     if exch_rate == 1.0 and currency not in ("USD", ""):
# # #         try:
# # #             from models.exchange_rate import get_rate
# # #             stored = get_rate(currency, "USD")
# # #             if stored:
# # #                 exch_rate = stored
# # #         except Exception:
# # #             pass

# # #     payload = {
# # #         "doctype":                  "Payment Entry",
# # #         "payment_type":             "Receive",
# # #         "party_type":               "Customer",
# # #         "party":                    pe.get("party") or "default",
# # #         "party_name":               pe.get("party_name") or "default",
# # #         "paid_to_account_currency": paid_to_currency,
# # #         "paid_amount":              amount,
# # #         "received_amount":          amount,
# # #         "source_exchange_rate":     exch_rate,
# # #         "reference_no":             pe.get("reference_no") or pe.get("sale_invoice_no", ""),
# # #         "reference_date":           pe.get("reference_date") or date.today().isoformat(),
# # #         "remarks":                  pe.get("remarks") or f"POS Payment — {mop}",
# # #         "mode_of_payment":          mop,
# # #         "docstatus":                1,
# # #     }

# # #     if paid_to:
# # #         payload["paid_to"] = paid_to
# # #     if company:
# # #         payload["company"] = company

# # #     # Link to the Sales Invoice on Frappe
# # #     if frappe_inv:
# # #         payload["references"] = [{
# # #             "reference_doctype": "Sales Invoice",
# # #             "reference_name":    frappe_inv,
# # #             "allocated_amount":  amount,
# # #         }]

# # #     return payload


# # # # =============================================================================
# # # # PUSH ONE PAYMENT ENTRY
# # # # =============================================================================

# # # def _push_payment_entry(pe: dict, api_key: str, api_secret: str,
# # #                         defaults: dict, host: str) -> str | None:
# # #     """
# # #     Posts one payment entry to Frappe.
# # #     Returns Frappe's PAY-xxxxx name on success, None on failure.
# # #     """
# # #     pe_id  = pe["id"]
# # #     inv_no = pe.get("sale_invoice_no", str(pe_id))

# # #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()
# # #     if not frappe_inv:
# # #         log.warning("Payment %d — Sales Invoice not yet on Frappe, skipping.", pe_id)
# # #         return None

# # #     payload = _build_payload(pe, defaults, api_key, api_secret, host)

# # #     url = f"{host}/api/resource/Payment%20Entry"
# # #     req = urllib.request.Request(
# # #         url=url,
# # #         data=json.dumps(payload).encode("utf-8"),
# # #         method="POST",
# # #         headers={
# # #             "Content-Type":  "application/json",
# # #             "Accept":        "application/json",
# # #             "Authorization": f"token {api_key}:{api_secret}",
# # #         },
# # #     )

# # #     try:
# # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
# # #             data = json.loads(resp.read().decode())
# # #             name = (data.get("data") or {}).get("name", "")
# # #             log.info("✅ Payment Entry %d → Frappe %s  [%s  %s %.2f]",
# # #                      pe_id, name, inv_no,
# # #                      pe.get("currency", ""), float(pe.get("paid_amount", 0)))
# # #             return name or "SYNCED"

# # #     except urllib.error.HTTPError as e:
# # #         try:
# # #             err = json.loads(e.read().decode())
# # #             msg = (err.get("exception") or err.get("message") or
# # #                    str(err.get("_server_messages", "")) or f"HTTP {e.code}")
# # #         except Exception:
# # #             msg = f"HTTP {e.code}"

# # #         if e.code == 409:
# # #             log.info("Payment %d already on Frappe (409) - marking synced.", pe_id)
# # #             return "DUPLICATE"

# # #         # Invoice already paid (is_pos:1 on old invoices) - stop retrying
# # #         if e.code == 417:
# # #             _perma = ("already been fully paid", "already paid", "fully paid")
# # #             if any(p in msg.lower() for p in _perma):
# # #                 log.info("Payment %d - invoice already paid on Frappe, marking synced.", pe_id)
# # #                 return "ALREADY_PAID"

# # #         log.error("FAIL Payment Entry %d  HTTP %s: %s", pe_id, e.code, msg)
# # #         return None

# # #     except urllib.error.URLError as e:
# # #         log.warning("Network error pushing payment %d: %s", pe_id, e.reason)
# # #         return None

# # #     except Exception as e:
# # #         log.error("Unexpected error pushing payment %d: %s", pe_id, e)
# # #         return None


# # # # =============================================================================
# # # # PUBLIC — push all unsynced payment entries
# # # # =============================================================================

# # # def push_unsynced_payment_entries() -> dict:
# # #     """
# # #     1. Refresh frappe_invoice_ref from parent sales that were confirmed.
# # #     2. Push each unsynced payment entry to Frappe.
# # #     3. Mark synced with the returned PAY-xxxxx ref.
# # #     """
# # #     result = {"pushed": 0, "failed": 0, "skipped": 0, "total": 0}

# # #     api_key, api_secret = _get_credentials()
# # #     if not api_key or not api_secret:
# # #         log.warning("No credentials — skipping payment entry sync.")
# # #         return result

# # #     host     = _get_host()
# # #     defaults = _get_defaults()

# # #     # First: pull frappe_refs from confirmed invoices into pending payment entries
# # #     updated = refresh_frappe_refs()
# # #     if updated:
# # #         log.info("Refreshed frappe_invoice_ref on %d payment entry(ies).", updated)

# # #     entries = get_unsynced_payment_entries()
# # #     result["total"] = len(entries)

# # #     if not entries:
# # #         log.debug("No unsynced payment entries.")
# # #         return result

# # #     log.info("Pushing %d payment entry(ies) to Frappe…", len(entries))

# # #     for pe in entries:
# # #         frappe_name = _push_payment_entry(pe, api_key, api_secret, defaults, host)
# # #         if frappe_name:
# # #             mark_payment_synced(pe["id"], frappe_name)
# # #             result["pushed"] += 1
# # #         elif frappe_name is None:
# # #             # None = permanent skip (no frappe_inv yet), not a real failure
# # #             result["skipped"] += 1
# # #         else:
# # #             result["failed"] += 1

# # #         time.sleep(3)   # rate limit — 20/min max

# # #     log.info("Payment sync done — ✅ %d pushed  ❌ %d failed  ⏭ %d skipped",
# # #              result["pushed"], result["failed"], result["skipped"])
# # #     return result


# # # # =============================================================================
# # # # BACKGROUND DAEMON THREAD
# # # # =============================================================================

# # # def _sync_loop():
# # #     log.info("Payment entry sync daemon started (interval=%ds).", SYNC_INTERVAL)
# # #     while True:
# # #         if _sync_lock.acquire(blocking=False):
# # #             try:
# # #                 push_unsynced_payment_entries()
# # #             except Exception as e:
# # #                 log.error("Payment sync cycle error: %s", e)
# # #             finally:
# # #                 _sync_lock.release()
# # #         else:
# # #             log.debug("Previous payment sync still running — skipping.")
# # #         time.sleep(SYNC_INTERVAL)


# # # def start_payment_sync_daemon() -> threading.Thread:
# # #     """Non-blocking — safe to call from MainWindow.__init__."""
# # #     global _sync_thread
# # #     if _sync_thread and _sync_thread.is_alive():
# # #         return _sync_thread
# # #     t = threading.Thread(target=_sync_loop, daemon=True, name="PaymentSyncDaemon")
# # #     t.start()
# # #     _sync_thread = t
# # #     log.info("Payment entry sync daemon started.")
# # #     return t


# # # # =============================================================================
# # # # DEBUG
# # # # =============================================================================

# # # if __name__ == "__main__":
# # #     logging.basicConfig(level=logging.INFO,
# # #                         format="%(asctime)s [%(levelname)s] %(message)s")
# # #     print("Running one payment entry sync cycle...")
# # #     r = push_unsynced_payment_entries()
# # #     print(f"\nResult: {r['pushed']} pushed, {r['failed']} failed, "
# # #           f"{r['skipped']} skipped (of {r['total']} total)")

# # # =============================================================================
# # # services/payment_entry_service.py
# # #
# # # Manages local payment_entries table and syncs them to Frappe.
# # #
# # # FLOW:
# # #   1. When a sale is saved locally → create_payment_entry() stores it locally
# # #      with synced=0
# # #   2. When the Sales Invoice is confirmed on Frappe (frappe_ref is set) →
# # #      push_unsynced_payment_entries() pushes the Payment Entry to Frappe
# # #   3. Frappe returns a PAY-xxxxx ref → stored as frappe_payment_ref, synced=1
# # #
# # # PAYLOAD SENT TO FRAPPE:
# # #   POST /api/resource/Payment Entry
# # #   {
# # #     "doctype":              "Payment Entry",
# # #     "payment_type":         "Receive",
# # #     "party_type":           "Customer",
# # #     "party":                "Cathy",
# # #     "paid_to":              "Cash ZWG - H",
# # #     "paid_to_account_currency": "USD",
# # #     "paid_amount":          32.45,
# # #     "received_amount":      32.45,
# # #     "source_exchange_rate": 1.0,
# # #     "reference_no":         "ACC-SINV-2026-00034",
# # #     "reference_date":       "2026-03-19",
# # #     "remarks":              "POS Payment — Cash",
# # #     "docstatus":            1,
# # #     "references": [{
# # #         "reference_doctype": "Sales Invoice",
# # #         "reference_name":    "ACC-SINV-2026-00565",
# # #         "allocated_amount":  32.45
# # #     }]
# # #   }
# # # =============================================================================

# # from __future__ import annotations

# # import json
# # import logging
# # import time
# # import threading
# # import urllib.request
# # import urllib.error
# # from datetime import date

# # log = logging.getLogger("PaymentEntry")

# # SYNC_INTERVAL   = 60      # seconds between auto-sync cycles
# # REQUEST_TIMEOUT = 30

# # # Exchange rate cache: "FROM::TO::DATE" → float
# # _RATE_CACHE: dict[str, float] = {}


# # def _get_exchange_rate(from_currency: str, to_currency: str,
# #                        transaction_date: str,
# #                        api_key: str, api_secret: str, host: str) -> float:
# #     """
# #     Fetch live exchange rate from Frappe.
# #     Returns 1.0 for same currency, 0.0 if fetch fails (Frappe uses its own rate).
# #     """
# #     if not from_currency or from_currency.upper() == to_currency.upper():
# #         return 1.0

# #     cache_key = f"{from_currency.upper()}::{to_currency.upper()}::{transaction_date}"
# #     if cache_key in _RATE_CACHE:
# #         return _RATE_CACHE[cache_key]

# #     try:
# #         import urllib.parse
# #         url = (
# #             f"{host}/api/method/erpnext.setup.utils.get_exchange_rate"
# #             f"?from_currency={urllib.parse.quote(from_currency)}"
# #             f"&to_currency={urllib.parse.quote(to_currency)}"
# #             f"&transaction_date={transaction_date}"
# #         )
# #         req = urllib.request.Request(url)
# #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# #             data = json.loads(r.read().decode())
# #             rate = float(data.get("message") or data.get("result") or 0)
# #             if rate > 0:
# #                 _RATE_CACHE[cache_key] = rate
# #                 log.debug("Rate %s→%s on %s: %.6f", from_currency, to_currency, transaction_date, rate)
# #                 return rate
# #     except Exception as e:
# #         log.debug("Rate fetch failed (%s→%s): %s", from_currency, to_currency, e)

# #     return 0.0

# # _sync_lock:   threading.Lock          = threading.Lock()
# # _sync_thread: threading.Thread | None = None

# # # Method → Frappe Mode of Payment name
# # _METHOD_MAP = {
# #     "CASH":     "Cash",
# #     "CARD":     "Credit Card",
# #     "C / CARD": "Credit Card",
# #     "EFTPOS":   "Credit Card",
# #     "CHECK":    "Cheque",
# #     "CHEQUE":   "Cheque",
# #     "MOBILE":   "Mobile Money",
# #     "CREDIT":   "Credit",
# #     "TRANSFER": "Bank Transfer",
# # }


# # # =============================================================================
# # # CREDENTIALS / HOST / DEFAULTS
# # # =============================================================================

# # def _get_credentials() -> tuple[str, str]:
# #     try:
# #         from services.credentials import get_credentials
# #         return get_credentials()
# #     except Exception:
# #         pass
# #     return "", ""


# # def _get_host() -> str:
# #     try:
# #         from models.company_defaults import get_defaults
# #         host = (get_defaults() or {}).get("server_api_host", "").strip().rstrip("/")
# #         if host:
# #             return host
# #     except Exception:
# #         pass
# #     return "https://apk.havano.cloud"


# # def _get_defaults() -> dict:
# #     try:
# #         from models.company_defaults import get_defaults
# #         return get_defaults() or {}
# #     except Exception:
# #         return {}


# # # =============================================================================
# # # GL ACCOUNT RESOLVER  (which account to credit for each payment method)
# # # =============================================================================

# # _ACCOUNT_CACHE: dict[str, str] = {}


# # def _resolve_paid_to_account(mop_name: str, company: str, currency: str,
# #                               api_key: str, api_secret: str, host: str) -> str:
# #     """
# #     Looks up the GL account for a Mode of Payment from Frappe.
# #     Tries to match by currency if multiple accounts exist for the company.
# #     Falls back to server_pos_account in company_defaults.
# #     """
# #     cache_key = f"{mop_name}::{company}::{currency}"
# #     if cache_key in _ACCOUNT_CACHE:
# #         return _ACCOUNT_CACHE[cache_key]

# #     try:
# #         import urllib.parse
# #         url = (f"{host}/api/resource/Mode%20of%20Payment/"
# #                f"{urllib.parse.quote(mop_name)}?fields=[\"accounts\"]")
# #         req = urllib.request.Request(url)
# #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# #             data     = json.loads(r.read().decode())
# #             accounts = (data.get("data") or {}).get("accounts", [])

# #         company_accts = [a for a in accounts
# #                          if not company or a.get("company") == company]

# #         # Prefer account whose name contains the currency code
# #         matched = ""
# #         if currency:
# #             for a in company_accts:
# #                 if currency.upper() in (a.get("default_account") or "").upper():
# #                     matched = a["default_account"]; break

# #         if not matched and company_accts:
# #             matched = company_accts[0].get("default_account", "")

# #         if matched:
# #             _ACCOUNT_CACHE[cache_key] = matched
# #             return matched

# #     except Exception as e:
# #         log.debug("MOP account lookup failed for '%s': %s", mop_name, e)

# #     # Fallback
# #     fallback = _get_defaults().get("server_pos_account", "").strip()
# #     if fallback:
# #         _ACCOUNT_CACHE[cache_key] = fallback
# #         return fallback

# #     log.warning("No GL account for MOP '%s' currency=%s — Payment Entry may fail.",
# #                 mop_name, currency)
# #     return ""


# # # =============================================================================
# # # LOCAL DB  — create / read / update payment_entries
# # # =============================================================================

# # def create_payment_entry(sale: dict, override_rate: float = None,
# #                          override_account: str = None) -> int | None:
# #     """
# #     Called immediately after a sale is saved locally.
# #     Stores a payment_entry row with synced=0.
# #     Returns the new payment_entry id, or None on error.

# #     Will only create the entry once per sale (idempotent).
# #     """
# #     from database.db import get_connection
# #     conn = get_connection(); cur = conn.cursor()

# #     # Idempotency: don't create twice for the same sale
# #     cur.execute("SELECT id FROM payment_entries WHERE sale_id = ?", (sale["id"],))
# #     if cur.fetchone():
# #         conn.close()
# #         return None

# #     customer   = (sale.get("customer_name") or "default").strip()
# #     currency   = (sale.get("currency")      or "USD").strip().upper()
# #     amount     = float(sale.get("total")    or 0)
# #     inv_no     = sale.get("invoice_no", "")
# #     inv_date   = sale.get("invoice_date") or date.today().isoformat()
# #     method     = str(sale.get("method", "CASH")).upper().strip()
# #     mop        = _METHOD_MAP.get(method, "Cash")

# #     # Use override rate (from split) or fetch from Frappe
# #     if override_rate is not None:
# #         exch_rate = override_rate
# #     else:
# #         try:
# #             api_key, api_secret = _get_credentials()
# #             host = _get_host()
# #             defaults = _get_defaults()
# #             company_currency = defaults.get("server_company_currency", "USD").strip().upper() or "USD"
# #             exch_rate = _get_exchange_rate(
# #                 currency, company_currency, inv_date, api_key, api_secret, host
# #             ) if currency != company_currency else 1.0
# #         except Exception:
# #             exch_rate = 1.0

# #     cur.execute("""
# #         INSERT INTO payment_entries (
# #             sale_id, sale_invoice_no, frappe_invoice_ref,
# #             party, party_name,
# #             paid_amount, received_amount, source_exchange_rate,
# #             paid_to_account_currency, currency,
# #             mode_of_payment,
# #             reference_no, reference_date,
# #             remarks, synced
# #         ) OUTPUT INSERTED.id
# #         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# #     """, (
# #         sale["id"], inv_no,
# #         sale.get("frappe_ref") or None,
# #         customer, customer,
# #         amount, amount, exch_rate or 1.0,
# #         currency, currency,
# #         mop,
# #         inv_no, inv_date,
# #         f"POS Payment — {mop}",
# #     ))
# #     new_id = int(cur.fetchone()[0])
# #     conn.commit(); conn.close()
# #     log.debug("Payment entry %d created locally for sale %s", new_id, inv_no)
# #     return new_id


# # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# #     """
# #     Called when cashier uses Split payment.
# #     Creates one payment_entry row per currency in splits list.
# #     splits = [{"mode": "CASH", "currency": "USD", "amount": 5.0,
# #                "rate": 1.0, "base_amount": 5.0, "account": "Cash - AT"}, ...]
# #     Returns list of new payment_entry ids.
# #     """
# #     ids = []
# #     for split in splits:
# #         if not split.get("amount") or float(split["amount"]) <= 0:
# #             continue
# #         # Build a sale-like dict with the split's currency and amount
# #         split_sale = dict(sale)
# #         split_sale["currency"]      = split.get("currency", "USD")
# #         split_sale["total"]         = float(split.get("amount", 0))
# #         split_sale["method"]        = split.get("mode", "CASH")
# #         # Override exchange rate from split data
# #         new_id = create_payment_entry(
# #             split_sale,
# #             override_rate=float(split.get("rate", 1.0)),
# #             override_account=split.get("account", ""),
# #         )
# #         if new_id:
# #             ids.append(new_id)
# #     return ids


# # def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
# #     """
# #     Creates one payment_entry per currency from a split payment.
# #     Groups splits by currency, sums amounts, creates one entry each.
# #     Returns list of created payment_entry ids.
# #     """
# #     from datetime import date as _date

# #     # Group by currency
# #     by_currency: dict[str, dict] = {}
# #     for s in splits:
# #         curr = s.get("account_currency", "USD").upper()
# #         if curr not in by_currency:
# #             by_currency[curr] = {
# #                 "currency":      curr,
# #                 "paid_amount":   0.0,
# #                 "base_value":    0.0,
# #                 "rate":          s.get("rate", 1.0),
# #                 "account_name":  s.get("account_name", ""),
# #                 "mode":          s.get("mode", "Cash"),
# #             }
# #         by_currency[curr]["paid_amount"] += s.get("amount_paid", 0.0)
# #         by_currency[curr]["base_value"]  += s.get("base_value",  0.0)

# #     ids = []
# #     inv_no   = sale.get("invoice_no", "")
# #     inv_date = sale.get("invoice_date") or _date.today().isoformat()
# #     customer = (sale.get("customer_name") or "default").strip()

# #     from database.db import get_connection
# #     conn = get_connection(); cur = conn.cursor()

# #     for curr, grp in by_currency.items():
# #         # Idempotency: skip if already exists for this sale+currency
# #         cur.execute(
# #             "SELECT id FROM payment_entries WHERE sale_id=? AND currency=?",
# #             (sale["id"], curr)
# #         )
# #         if cur.fetchone():
# #             continue

# #         mop = _METHOD_MAP.get(grp["mode"].upper(), "Cash")

# #         cur.execute("""
# #             INSERT INTO payment_entries (
# #                 sale_id, sale_invoice_no, frappe_invoice_ref,
# #                 party, party_name,
# #                 paid_amount, received_amount, source_exchange_rate,
# #                 paid_to_account_currency, currency,
# #                 paid_to,
# #                 mode_of_payment,
# #                 reference_no, reference_date,
# #                 remarks, synced
# #             ) OUTPUT INSERTED.id
# #             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
# #         """, (
# #             sale["id"], inv_no,
# #             sale.get("frappe_ref") or None,
# #             customer, customer,
# #             grp["paid_amount"],
# #             grp["base_value"],
# #             float(grp["rate"] or 1.0),
# #             curr, curr,
# #             grp["account_name"],
# #             mop,
# #             inv_no, inv_date,
# #             f"POS Split Payment — {mop} ({curr})",
# #         ))
# #         new_id = int(cur.fetchone()[0])
# #         ids.append(new_id)
# #         log.debug("Split payment entry %d created: %s %.2f %s",
# #                   new_id, curr, grp["paid_amount"], inv_no)

# #     conn.commit(); conn.close()
# #     return ids


# # def get_unsynced_payment_entries() -> list[dict]:
# #     """Returns payment entries that are ready to push (synced=0)."""
# #     from database.db import get_connection, fetchall_dicts
# #     conn = get_connection(); cur = conn.cursor()
# #     cur.execute("""
# #         SELECT pe.*, s.frappe_ref AS sale_frappe_ref
# #         FROM payment_entries pe
# #         LEFT JOIN sales s ON s.id = pe.sale_id
# #         WHERE pe.synced = 0
# #           AND (pe.frappe_invoice_ref IS NOT NULL
# #                OR s.frappe_ref IS NOT NULL)
# #         ORDER BY pe.id
# #     """)
# #     rows = fetchall_dicts(cur); conn.close()
# #     return rows


# # def mark_payment_synced(pe_id: int, frappe_payment_ref: str = "") -> None:
# #     from database.db import get_connection
# #     conn = get_connection(); cur = conn.cursor()
# #     cur.execute(
# #         "UPDATE payment_entries SET synced=1, frappe_payment_ref=? WHERE id=?",
# #         (frappe_payment_ref or None, pe_id)
# #     )
# #     # Also update the sales row
# #     cur.execute("""
# #         UPDATE sales SET payment_entry_ref=?, payment_synced=1
# #         WHERE id = (SELECT sale_id FROM payment_entries WHERE id=?)
# #     """, (frappe_payment_ref or None, pe_id))
# #     conn.commit(); conn.close()


# # def refresh_frappe_refs() -> int:
# #     """
# #     For payment entries that have no frappe_invoice_ref yet, copy it from
# #     the parent sale's frappe_ref. Call this before pushing payments.
# #     Returns count updated.
# #     """
# #     from database.db import get_connection
# #     conn = get_connection(); cur = conn.cursor()
# #     cur.execute("""
# #         UPDATE pe
# #         SET pe.frappe_invoice_ref = s.frappe_ref
# #         FROM payment_entries pe
# #         JOIN sales s ON s.id = pe.sale_id
# #         WHERE pe.synced = 0
# #           AND (pe.frappe_invoice_ref IS NULL OR pe.frappe_invoice_ref = '')
# #           AND s.frappe_ref IS NOT NULL AND s.frappe_ref != ''
# #     """)
# #     count = cur.rowcount
# #     conn.commit(); conn.close()
# #     return count


# # # =============================================================================
# # # BUILD FRAPPE PAYLOAD
# # # =============================================================================

# # def _build_payload(pe: dict, defaults: dict,
# #                    api_key: str, api_secret: str, host: str) -> dict:
# #     company  = defaults.get("server_company", "")
# #     currency = (pe.get("currency") or pe.get("paid_to_account_currency") or "USD").upper()
# #     mop      = pe.get("mode_of_payment") or "Cash"
# #     amount   = float(pe.get("paid_amount") or 0)
# #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()

# #     # Use local gl_accounts table first (synced from Frappe)
# #     paid_to          = (pe.get("paid_to") or "").strip()
# #     paid_to_currency = currency
# #     if not paid_to:
# #         try:
# #             from models.gl_account import get_account_for_payment
# #             acct = get_account_for_payment(currency, company)
# #             if acct:
# #                 paid_to          = acct["name"]
# #                 paid_to_currency = acct["account_currency"]
# #         except Exception as _e:
# #             log.debug("gl_account lookup failed: %s", _e)

# #     # Fallback to live Frappe lookup
# #     if not paid_to:
# #         paid_to = _resolve_paid_to_account(mop, company, currency, api_key, api_secret, host)

# #     # Use local exchange rate if not stored
# #     exch_rate = float(pe.get("source_exchange_rate") or 1.0)
# #     if exch_rate == 1.0 and currency not in ("USD", ""):
# #         try:
# #             from models.exchange_rate import get_rate
# #             stored = get_rate(currency, "USD")
# #             if stored:
# #                 exch_rate = stored
# #         except Exception:
# #             pass

# #     payload = {
# #         "doctype":                  "Payment Entry",
# #         "payment_type":             "Receive",
# #         "party_type":               "Customer",
# #         "party":                    pe.get("party") or "default",
# #         "party_name":               pe.get("party_name") or "default",
# #         "paid_to_account_currency": paid_to_currency,
# #         "paid_amount":              amount,
# #         "received_amount":          amount,
# #         "source_exchange_rate":     exch_rate,
# #         "reference_no":             pe.get("reference_no") or pe.get("sale_invoice_no", ""),
# #         "reference_date":           pe.get("reference_date") or date.today().isoformat(),
# #         "remarks":                  pe.get("remarks") or f"POS Payment — {mop}",
# #         "mode_of_payment":          mop,
# #         "docstatus":                1,
# #     }

# #     if paid_to:
# #         payload["paid_to"] = paid_to
# #     if company:
# #         payload["company"] = company

# #     # Link to the Sales Invoice on Frappe
# #     if frappe_inv:
# #         payload["references"] = [{
# #             "reference_doctype": "Sales Invoice",
# #             "reference_name":    frappe_inv,
# #             "allocated_amount":  amount,
# #         }]

# #     return payload


# # # =============================================================================
# # # PUSH ONE PAYMENT ENTRY
# # # =============================================================================

# # def _push_payment_entry(pe: dict, api_key: str, api_secret: str,
# #                         defaults: dict, host: str) -> str | None:
# #     """
# #     Posts one payment entry to Frappe.
# #     Returns Frappe's PAY-xxxxx name on success, None on failure.
# #     """
# #     pe_id  = pe["id"]
# #     inv_no = pe.get("sale_invoice_no", str(pe_id))

# #     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()
# #     if not frappe_inv:
# #         log.warning("Payment %d — Sales Invoice not yet on Frappe, skipping.", pe_id)
# #         return None

# #     payload = _build_payload(pe, defaults, api_key, api_secret, host)

# #     url = f"{host}/api/resource/Payment%20Entry"
# #     req = urllib.request.Request(
# #         url=url,
# #         data=json.dumps(payload).encode("utf-8"),
# #         method="POST",
# #         headers={
# #             "Content-Type":  "application/json",
# #             "Accept":        "application/json",
# #             "Authorization": f"token {api_key}:{api_secret}",
# #         },
# #     )

# #     try:
# #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
# #             data = json.loads(resp.read().decode())
# #             name = (data.get("data") or {}).get("name", "")
# #             log.info("✅ Payment Entry %d → Frappe %s  [%s  %s %.2f]",
# #                      pe_id, name, inv_no,
# #                      pe.get("currency", ""), float(pe.get("paid_amount", 0)))
# #             return name or "SYNCED"

# #     except urllib.error.HTTPError as e:
# #         try:
# #             err = json.loads(e.read().decode())
# #             msg = (err.get("exception") or err.get("message") or
# #                    str(err.get("_server_messages", "")) or f"HTTP {e.code}")
# #         except Exception:
# #             msg = f"HTTP {e.code}"

# #         if e.code == 409:
# #             log.info("Payment %d already on Frappe (409) - marking synced.", pe_id)
# #             return "DUPLICATE"

# #         # Invoice already paid (is_pos:1 on old invoices) - stop retrying
# #         if e.code == 417:
# #             _perma = ("already been fully paid", "already paid", "fully paid")
# #             if any(p in msg.lower() for p in _perma):
# #                 log.info("Payment %d - invoice already paid on Frappe, marking synced.", pe_id)
# #                 return "ALREADY_PAID"

# #         log.error("FAIL Payment Entry %d  HTTP %s: %s", pe_id, e.code, msg)
# #         return None

# #     except urllib.error.URLError as e:
# #         log.warning("Network error pushing payment %d: %s", pe_id, e.reason)
# #         return None

# #     except Exception as e:
# #         log.error("Unexpected error pushing payment %d: %s", pe_id, e)
# #         return None


# # # =============================================================================
# # # PUBLIC — push all unsynced payment entries
# # # =============================================================================

# # def push_unsynced_payment_entries() -> dict:
# #     """
# #     1. Refresh frappe_invoice_ref from parent sales that were confirmed.
# #     2. Push each unsynced payment entry to Frappe.
# #     3. Mark synced with the returned PAY-xxxxx ref.
# #     """
# #     result = {"pushed": 0, "failed": 0, "skipped": 0, "total": 0}

# #     api_key, api_secret = _get_credentials()
# #     if not api_key or not api_secret:
# #         log.warning("No credentials — skipping payment entry sync.")
# #         return result

# #     host     = _get_host()
# #     defaults = _get_defaults()

# #     # First: pull frappe_refs from confirmed invoices into pending payment entries
# #     updated = refresh_frappe_refs()
# #     if updated:
# #         log.info("Refreshed frappe_invoice_ref on %d payment entry(ies).", updated)

# #     entries = get_unsynced_payment_entries()
# #     result["total"] = len(entries)

# #     if not entries:
# #         log.debug("No unsynced payment entries.")
# #         return result

# #     log.info("Pushing %d payment entry(ies) to Frappe…", len(entries))

# #     for pe in entries:
# #         frappe_name = _push_payment_entry(pe, api_key, api_secret, defaults, host)
# #         if frappe_name:
# #             mark_payment_synced(pe["id"], frappe_name)
# #             result["pushed"] += 1
# #         elif frappe_name is None:
# #             # None = permanent skip (no frappe_inv yet), not a real failure
# #             result["skipped"] += 1
# #         else:
# #             result["failed"] += 1

# #         time.sleep(3)   # rate limit — 20/min max

# #     log.info("Payment sync done — ✅ %d pushed  ❌ %d failed  ⏭ %d skipped",
# #              result["pushed"], result["failed"], result["skipped"])
# #     return result


# # # =============================================================================
# # # BACKGROUND DAEMON THREAD
# # # =============================================================================

# # def _sync_loop():
# #     log.info("Payment entry sync daemon started (interval=%ds).", SYNC_INTERVAL)
# #     while True:
# #         if _sync_lock.acquire(blocking=False):
# #             try:
# #                 push_unsynced_payment_entries()
# #             except Exception as e:
# #                 log.error("Payment sync cycle error: %s", e)
# #             finally:
# #                 _sync_lock.release()
# #         else:
# #             log.debug("Previous payment sync still running — skipping.")
# #         time.sleep(SYNC_INTERVAL)


# # def start_payment_sync_daemon() -> threading.Thread:
# #     """Non-blocking — safe to call from MainWindow.__init__."""
# #     global _sync_thread
# #     if _sync_thread and _sync_thread.is_alive():
# #         return _sync_thread
# #     t = threading.Thread(target=_sync_loop, daemon=True, name="PaymentSyncDaemon")
# #     t.start()
# #     _sync_thread = t
# #     log.info("Payment entry sync daemon started.")
# #     return t


# # # =============================================================================
# # # DEBUG
# # # =============================================================================

# # if __name__ == "__main__":
# #     logging.basicConfig(level=logging.INFO,
# #                         format="%(asctime)s [%(levelname)s] %(message)s")
# #     print("Running one payment entry sync cycle...")
# #     r = push_unsynced_payment_entries()
# #     print(f"\nResult: {r['pushed']} pushed, {r['failed']} failed, "
# #           f"{r['skipped']} skipped (of {r['total']} total)")

# # =============================================================================
# # services/payment_entry_service.py
# #
# # Manages local payment_entries table and syncs them to Frappe.
# #
# # FLOW:
# #   1. When a sale is saved locally → create_payment_entry() stores it locally
# #      with synced=0
# #   2. When the Sales Invoice is confirmed on Frappe (frappe_ref is set) →
# #      push_unsynced_payment_entries() pushes the Payment Entry to Frappe
# #   3. Frappe returns a PAY-xxxxx ref → stored as frappe_payment_ref, synced=1
# #
# # PAYLOAD SENT TO FRAPPE:
# #   POST /api/resource/Payment Entry
# #   {
# #     "doctype":              "Payment Entry",
# #     "payment_type":         "Receive",
# #     "party_type":           "Customer",
# #     "party":                "Cathy",
# #     "paid_to":              "Cash ZWG - H",
# #     "paid_to_account_currency": "USD",
# #     "paid_amount":          32.45,
# #     "received_amount":      32.45,
# #     "source_exchange_rate": 1.0,
# #     "reference_no":         "ACC-SINV-2026-00034",
# #     "reference_date":       "2026-03-19",
# #     "remarks":              "POS Payment — Cash",
# #     "docstatus":            1,
# #     "references": [{
# #         "reference_doctype": "Sales Invoice",
# #         "reference_name":    "ACC-SINV-2026-00565",
# #         "allocated_amount":  32.45
# #     }]
# #   }
# # =============================================================================

# from __future__ import annotations

# import json
# import logging
# import time
# import threading
# import urllib.request
# import urllib.error
# from datetime import date

# log = logging.getLogger("PaymentEntry")

# SYNC_INTERVAL   = 60      # seconds between auto-sync cycles
# REQUEST_TIMEOUT = 30

# # Exchange rate cache: "FROM::TO::DATE" → float
# _RATE_CACHE: dict[str, float] = {}


# def _get_exchange_rate(from_currency: str, to_currency: str,
#                        transaction_date: str,
#                        api_key: str, api_secret: str, host: str) -> float:
#     """
#     Fetch live exchange rate from Frappe.
#     Returns 1.0 for same currency, 0.0 if fetch fails (Frappe uses its own rate).
#     """
#     if not from_currency or from_currency.upper() == to_currency.upper():
#         return 1.0

#     cache_key = f"{from_currency.upper()}::{to_currency.upper()}::{transaction_date}"
#     if cache_key in _RATE_CACHE:
#         return _RATE_CACHE[cache_key]

#     try:
#         import urllib.parse
#         url = (
#             f"{host}/api/method/erpnext.setup.utils.get_exchange_rate"
#             f"?from_currency={urllib.parse.quote(from_currency)}"
#             f"&to_currency={urllib.parse.quote(to_currency)}"
#             f"&transaction_date={transaction_date}"
#         )
#         req = urllib.request.Request(url)
#         req.add_header("Authorization", f"token {api_key}:{api_secret}")
#         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
#             data = json.loads(r.read().decode())
#             rate = float(data.get("message") or data.get("result") or 0)
#             if rate > 0:
#                 _RATE_CACHE[cache_key] = rate
#                 log.debug("Rate %s→%s on %s: %.6f", from_currency, to_currency, transaction_date, rate)
#                 return rate
#     except Exception as e:
#         log.debug("Rate fetch failed (%s→%s): %s", from_currency, to_currency, e)

#     return 0.0

# _sync_lock:   threading.Lock          = threading.Lock()
# _sync_thread: threading.Thread | None = None

# # Method → Frappe Mode of Payment name
# _METHOD_MAP = {
#     "CASH":     "Cash",
#     "CARD":     "Credit Card",
#     "C / CARD": "Credit Card",
#     "EFTPOS":   "Credit Card",
#     "CHECK":    "Cheque",
#     "CHEQUE":   "Cheque",
#     "MOBILE":   "Mobile Money",
#     "CREDIT":   "Credit",
#     "TRANSFER": "Bank Transfer",
# }


# # =============================================================================
# # CREDENTIALS / HOST / DEFAULTS
# # =============================================================================

# def _get_credentials() -> tuple[str, str]:
#     try:
#         from services.credentials import get_credentials
#         return get_credentials()
#     except Exception:
#         pass
#     return "", ""

# def _get_host() -> str:
#     try:
#         from models.company_defaults import get_defaults
#         host = (get_defaults() or {}).get("server_api_host", "").strip().rstrip("/")
#         if host:
#             return host
#     except Exception:
#         pass
#     return "https://apk.havano.cloud"


# def _get_defaults() -> dict:
#     try:
#         from models.company_defaults import get_defaults
#         return get_defaults() or {}
#     except Exception:
#         return {}


# # =============================================================================
# # GL ACCOUNT RESOLVER  (which account to credit for each payment method)
# # =============================================================================

# _ACCOUNT_CACHE: dict[str, str] = {}


# def _resolve_paid_to_account(mop_name: str, company: str, currency: str,
#                               api_key: str, api_secret: str, host: str) -> str:
#     """
#     Looks up the GL account for a Mode of Payment from Frappe.
#     Tries to match by currency if multiple accounts exist for the company.
#     Falls back to server_pos_account in company_defaults.
#     """
#     cache_key = f"{mop_name}::{company}::{currency}"
#     if cache_key in _ACCOUNT_CACHE:
#         return _ACCOUNT_CACHE[cache_key]

#     try:
#         import urllib.parse
#         url = (f"{host}/api/resource/Mode%20of%20Payment/"
#                f"{urllib.parse.quote(mop_name)}?fields=[\"accounts\"]")
#         req = urllib.request.Request(url)
#         req.add_header("Authorization", f"token {api_key}:{api_secret}")
#         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
#             data     = json.loads(r.read().decode())
#             accounts = (data.get("data") or {}).get("accounts", [])

#         company_accts = [a for a in accounts
#                          if not company or a.get("company") == company]

#         # Prefer account whose name contains the currency code
#         matched = ""
#         if currency:
#             for a in company_accts:
#                 if currency.upper() in (a.get("default_account") or "").upper():
#                     matched = a["default_account"]; break

#         if not matched and company_accts:
#             matched = company_accts[0].get("default_account", "")

#         if matched:
#             _ACCOUNT_CACHE[cache_key] = matched
#             return matched

#     except Exception as e:
#         log.debug("MOP account lookup failed for '%s': %s", mop_name, e)

#     # Fallback
#     fallback = _get_defaults().get("server_pos_account", "").strip()
#     if fallback:
#         _ACCOUNT_CACHE[cache_key] = fallback
#         return fallback

#     log.warning("No GL account for MOP '%s' currency=%s — Payment Entry may fail.",
#                 mop_name, currency)
#     return ""


# # =============================================================================
# # LOCAL DB  — create / read / update payment_entries
# # =============================================================================

# def create_payment_entry(sale: dict, override_rate: float = None,
#                          override_account: str = None) -> int | None:
#     """
#     Called immediately after a sale is saved locally.
#     Stores a payment_entry row with synced=0.
#     Returns the new payment_entry id, or None on error.

#     Will only create the entry once per sale (idempotent).
#     """
#     from database.db import get_connection
#     conn = get_connection(); cur = conn.cursor()

#     # Idempotency: don't create twice for the same sale
#     cur.execute("SELECT id FROM payment_entries WHERE sale_id = ?", (sale["id"],))
#     if cur.fetchone():
#         conn.close()
#         return None

#     customer   = (sale.get("customer_name") or "default").strip()
#     currency   = (sale.get("currency")      or "USD").strip().upper()
#     amount     = float(sale.get("total")    or 0)
#     inv_no     = sale.get("invoice_no", "")
#     inv_date   = sale.get("invoice_date") or date.today().isoformat()
#     method     = str(sale.get("method", "CASH")).upper().strip()
#     mop        = _METHOD_MAP.get(method, "Cash")

#     # Use override rate (from split) or fetch from Frappe
#     if override_rate is not None:
#         exch_rate = override_rate
#     else:
#         try:
#             api_key, api_secret = _get_credentials()
#             host = _get_host()
#             defaults = _get_defaults()
#             company_currency = defaults.get("server_company_currency", "USD").strip().upper() or "USD"
#             exch_rate = _get_exchange_rate(
#                 currency, company_currency, inv_date, api_key, api_secret, host
#             ) if currency != company_currency else 1.0
#         except Exception:
#             exch_rate = 1.0

#     cur.execute("""
#         INSERT INTO payment_entries (
#             sale_id, sale_invoice_no, frappe_invoice_ref,
#             party, party_name,
#             paid_amount, received_amount, source_exchange_rate,
#             paid_to_account_currency, currency,
#             mode_of_payment,
#             reference_no, reference_date,
#             remarks, synced
#         ) OUTPUT INSERTED.id
#         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
#     """, (
#         sale["id"], inv_no,
#         sale.get("frappe_ref") or None,
#         customer, customer,
#         amount, amount, exch_rate or 1.0,
#         currency, currency,
#         mop,
#         inv_no, inv_date,
#         f"POS Payment — {mop}",
#     ))
#     new_id = int(cur.fetchone()[0])
#     conn.commit(); conn.close()
#     log.debug("Payment entry %d created locally for sale %s", new_id, inv_no)
#     return new_id


# def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
#     """
#     Called when cashier uses Split payment.
#     Creates one payment_entry row per currency in splits list.
#     splits = [{"mode": "CASH", "currency": "USD", "amount": 5.0,
#                "rate": 1.0, "base_amount": 5.0, "account": "Cash - AT"}, ...]
#     Returns list of new payment_entry ids.
#     """
#     ids = []
#     for split in splits:
#         if not split.get("amount") or float(split["amount"]) <= 0:
#             continue
#         # Build a sale-like dict with the split's currency and amount
#         split_sale = dict(sale)
#         split_sale["currency"]      = split.get("currency", "USD")
#         split_sale["total"]         = float(split.get("amount", 0))
#         split_sale["method"]        = split.get("mode", "CASH")
#         # Override exchange rate from split data
#         new_id = create_payment_entry(
#             split_sale,
#             override_rate=float(split.get("rate", 1.0)),
#             override_account=split.get("account", ""),
#         )
#         if new_id:
#             ids.append(new_id)
#     return ids


# def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
#     """
#     Creates one payment_entry per currency from a split payment.
#     Groups splits by currency, sums amounts, creates one entry each.
#     Returns list of created payment_entry ids.
#     """
#     from datetime import date as _date

#     # Group by currency
#     by_currency: dict[str, dict] = {}
#     for s in splits:
#         curr = s.get("account_currency", "USD").upper()
#         if curr not in by_currency:
#             by_currency[curr] = {
#                 "currency":      curr,
#                 "paid_amount":   0.0,
#                 "base_value":    0.0,
#                 "rate":          s.get("rate", 1.0),
#                 "account_name":  s.get("account_name", ""),
#                 "mode":          s.get("mode", "Cash"),
#             }
#         by_currency[curr]["paid_amount"] += s.get("amount_paid", 0.0)
#         by_currency[curr]["base_value"]  += s.get("base_value",  0.0)

#     ids = []
#     inv_no   = sale.get("invoice_no", "")
#     inv_date = sale.get("invoice_date") or _date.today().isoformat()
#     customer = (sale.get("customer_name") or "default").strip()

#     from database.db import get_connection
#     conn = get_connection(); cur = conn.cursor()

#     for curr, grp in by_currency.items():
#         # Idempotency: skip if already exists for this sale+currency
#         cur.execute(
#             "SELECT id FROM payment_entries WHERE sale_id=? AND currency=?",
#             (sale["id"], curr)
#         )
#         if cur.fetchone():
#             continue

#         mop = _METHOD_MAP.get(grp["mode"].upper(), "Cash")

#         cur.execute("""
#             INSERT INTO payment_entries (
#                 sale_id, sale_invoice_no, frappe_invoice_ref,
#                 party, party_name,
#                 paid_amount, received_amount, source_exchange_rate,
#                 paid_to_account_currency, currency,
#                 paid_to,
#                 mode_of_payment,
#                 reference_no, reference_date,
#                 remarks, synced
#             ) OUTPUT INSERTED.id
#             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
#         """, (
#             sale["id"], inv_no,
#             sale.get("frappe_ref") or None,
#             customer, customer,
#             grp["paid_amount"],
#             grp["base_value"],
#             float(grp["rate"] or 1.0),
#             curr, curr,
#             grp["account_name"],
#             mop,
#             inv_no, inv_date,
#             f"POS Split Payment — {mop} ({curr})",
#         ))
#         new_id = int(cur.fetchone()[0])
#         ids.append(new_id)
#         log.debug("Split payment entry %d created: %s %.2f %s",
#                   new_id, curr, grp["paid_amount"], inv_no)

#     conn.commit(); conn.close()
#     return ids


# def get_unsynced_payment_entries() -> list[dict]:
#     """Returns payment entries that are ready to push (synced=0)."""
#     from database.db import get_connection, fetchall_dicts
#     conn = get_connection(); cur = conn.cursor()
#     cur.execute("""
#         SELECT pe.*, s.frappe_ref AS sale_frappe_ref
#         FROM payment_entries pe
#         LEFT JOIN sales s ON s.id = pe.sale_id
#         WHERE pe.synced = 0
#           AND (pe.frappe_invoice_ref IS NOT NULL
#                OR s.frappe_ref IS NOT NULL)
#         ORDER BY pe.id
#     """)
#     rows = fetchall_dicts(cur); conn.close()
#     return rows


# def mark_payment_synced(pe_id: int, frappe_payment_ref: str = "") -> None:
#     from database.db import get_connection
#     conn = get_connection(); cur = conn.cursor()
#     cur.execute(
#         "UPDATE payment_entries SET synced=1, frappe_payment_ref=? WHERE id=?",
#         (frappe_payment_ref or None, pe_id)
#     )
#     # Also update the sales row
#     cur.execute("""
#         UPDATE sales SET payment_entry_ref=?, payment_synced=1
#         WHERE id = (SELECT sale_id FROM payment_entries WHERE id=?)
#     """, (frappe_payment_ref or None, pe_id))
#     conn.commit(); conn.close()


# def refresh_frappe_refs() -> int:
#     """
#     For payment entries that have no frappe_invoice_ref yet, copy it from
#     the parent sale's frappe_ref. Call this before pushing payments.
#     Returns count updated.
#     """
#     from database.db import get_connection
#     conn = get_connection(); cur = conn.cursor()
#     cur.execute("""
#         UPDATE pe
#         SET pe.frappe_invoice_ref = s.frappe_ref
#         FROM payment_entries pe
#         JOIN sales s ON s.id = pe.sale_id
#         WHERE pe.synced = 0
#           AND (pe.frappe_invoice_ref IS NULL OR pe.frappe_invoice_ref = '')
#           AND s.frappe_ref IS NOT NULL AND s.frappe_ref != ''
#     """)
#     count = cur.rowcount
#     conn.commit(); conn.close()
#     return count


# # =============================================================================
# # BUILD FRAPPE PAYLOAD
# # =============================================================================

# def _build_payload(pe: dict, defaults: dict,
#                    api_key: str, api_secret: str, host: str) -> dict:
#     company  = defaults.get("server_company", "")
#     currency = (pe.get("currency") or pe.get("paid_to_account_currency") or "USD").upper()
#     mop      = pe.get("mode_of_payment") or "Cash"
#     amount   = float(pe.get("paid_amount") or 0)
#     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()

#     # Use local gl_accounts table first (synced from Frappe)
#     paid_to          = (pe.get("paid_to") or "").strip()
#     paid_to_currency = currency
#     if not paid_to:
#         try:
#             from models.gl_account import get_account_for_payment
#             acct = get_account_for_payment(currency, company)
#             if acct:
#                 paid_to          = acct["name"]
#                 paid_to_currency = acct["account_currency"]
#         except Exception as _e:
#             log.debug("gl_account lookup failed: %s", _e)

#     # Fallback to live Frappe lookup
#     if not paid_to:
#         paid_to = _resolve_paid_to_account(mop, company, currency, api_key, api_secret, host)

#     # Use local exchange rate if not stored
#     exch_rate = float(pe.get("source_exchange_rate") or 1.0)
#     if exch_rate == 1.0 and currency not in ("USD", ""):
#         try:
#             from models.exchange_rate import get_rate
#             stored = get_rate(currency, "USD")
#             if stored:
#                 exch_rate = stored
#         except Exception:
#             pass

#     payload = {
#         "doctype":                  "Payment Entry",
#         "payment_type":             "Receive",
#         "party_type":               "Customer",
#         "party":                    pe.get("party") or "default",
#         "party_name":               pe.get("party_name") or "default",
#         "paid_to_account_currency": paid_to_currency,
#         "paid_amount":              amount,
#         "received_amount":          amount,
#         "source_exchange_rate":     exch_rate,
#         "reference_no":             pe.get("reference_no") or pe.get("sale_invoice_no", ""),
#         "reference_date":           pe.get("reference_date") or date.today().isoformat(),
#         "remarks":                  pe.get("remarks") or f"POS Payment — {mop}",
#         "mode_of_payment":          mop,
#         "docstatus":                1,
#     }

#     if paid_to:
#         payload["paid_to"] = paid_to
#     if company:
#         payload["company"] = company

#     # Link to the Sales Invoice on Frappe
#     if frappe_inv:
#         payload["references"] = [{
#             "reference_doctype": "Sales Invoice",
#             "reference_name":    frappe_inv,
#             "allocated_amount":  amount,
#         }]

#     return payload


# # =============================================================================
# # PUSH ONE PAYMENT ENTRY
# # =============================================================================

# def _push_payment_entry(pe: dict, api_key: str, api_secret: str,
#                         defaults: dict, host: str) -> str | None:
#     """
#     Posts one payment entry to Frappe.
#     Returns Frappe's PAY-xxxxx name on success, None on failure.
#     """
#     pe_id  = pe["id"]
#     inv_no = pe.get("sale_invoice_no", str(pe_id))

#     frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()
#     if not frappe_inv:
#         log.warning("Payment %d — Sales Invoice not yet on Frappe, skipping.", pe_id)
#         return None

#     payload = _build_payload(pe, defaults, api_key, api_secret, host)

#     url = f"{host}/api/resource/Payment%20Entry"
#     req = urllib.request.Request(
#         url=url,
#         data=json.dumps(payload).encode("utf-8"),
#         method="POST",
#         headers={
#             "Content-Type":  "application/json",
#             "Accept":        "application/json",
#             "Authorization": f"token {api_key}:{api_secret}",
#         },
#     )

#     try:
#         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
#             data = json.loads(resp.read().decode())
#             name = (data.get("data") or {}).get("name", "")
#             log.info("✅ Payment Entry %d → Frappe %s  [%s  %s %.2f]",
#                      pe_id, name, inv_no,
#                      pe.get("currency", ""), float(pe.get("paid_amount", 0)))
#             return name or "SYNCED"

#     except urllib.error.HTTPError as e:
#         try:
#             err = json.loads(e.read().decode())
#             msg = (err.get("exception") or err.get("message") or
#                    str(err.get("_server_messages", "")) or f"HTTP {e.code}")
#         except Exception:
#             msg = f"HTTP {e.code}"

#         if e.code == 409:
#             log.info("Payment %d already on Frappe (409) - marking synced.", pe_id)
#             return "DUPLICATE"

#         # Invoice already paid (is_pos:1 on old invoices) - stop retrying
#         if e.code == 417:
#             _perma = ("already been fully paid", "already paid", "fully paid")
#             if any(p in msg.lower() for p in _perma):
#                 log.info("Payment %d - invoice already paid on Frappe, marking synced.", pe_id)
#                 return "ALREADY_PAID"

#         log.error("FAIL Payment Entry %d  HTTP %s: %s", pe_id, e.code, msg)
#         return None

#     except urllib.error.URLError as e:
#         log.warning("Network error pushing payment %d: %s", pe_id, e.reason)
#         return None

#     except Exception as e:
#         log.error("Unexpected error pushing payment %d: %s", pe_id, e)
#         return None


# # =============================================================================
# # PUBLIC — push all unsynced payment entries
# # =============================================================================

# def push_unsynced_payment_entries() -> dict:
#     """
#     1. Refresh frappe_invoice_ref from parent sales that were confirmed.
#     2. Push each unsynced payment entry to Frappe.
#     3. Mark synced with the returned PAY-xxxxx ref.
#     """
#     result = {"pushed": 0, "failed": 0, "skipped": 0, "total": 0}

#     api_key, api_secret = _get_credentials()
#     if not api_key or not api_secret:
#         log.warning("No credentials — skipping payment entry sync.")
#         return result

#     host     = _get_host()
#     defaults = _get_defaults()

#     # First: pull frappe_refs from confirmed invoices into pending payment entries
#     updated = refresh_frappe_refs()
#     if updated:
#         log.info("Refreshed frappe_invoice_ref on %d payment entry(ies).", updated)

#     entries = get_unsynced_payment_entries()
#     result["total"] = len(entries)

#     if not entries:
#         log.debug("No unsynced payment entries.")
#         return result

#     log.info("Pushing %d payment entry(ies) to Frappe…", len(entries))

#     for pe in entries:
#         frappe_name = _push_payment_entry(pe, api_key, api_secret, defaults, host)
#         if frappe_name:
#             mark_payment_synced(pe["id"], frappe_name)
#             result["pushed"] += 1
#         elif frappe_name is None:
#             # None = permanent skip (no frappe_inv yet), not a real failure
#             result["skipped"] += 1
#         else:
#             result["failed"] += 1

#         time.sleep(3)   # rate limit — 20/min max

#     log.info("Payment sync done — ✅ %d pushed  ❌ %d failed  ⏭ %d skipped",
#              result["pushed"], result["failed"], result["skipped"])
#     return result


# # =============================================================================
# # BACKGROUND DAEMON THREAD
# # =============================================================================

# def _sync_loop():
#     log.info("Payment entry sync daemon started (interval=%ds).", SYNC_INTERVAL)
#     while True:
#         if _sync_lock.acquire(blocking=False):
#             try:
#                 push_unsynced_payment_entries()
#             except Exception as e:
#                 log.error("Payment sync cycle error: %s", e)
#             finally:
#                 _sync_lock.release()
#         else:
#             log.debug("Previous payment sync still running — skipping.")
#         time.sleep(SYNC_INTERVAL)


# def start_payment_sync_daemon() -> threading.Thread:
#     """Non-blocking — safe to call from MainWindow.__init__."""
#     global _sync_thread
#     if _sync_thread and _sync_thread.is_alive():
#         return _sync_thread
#     t = threading.Thread(target=_sync_loop, daemon=True, name="PaymentSyncDaemon")
#     t.start()
#     _sync_thread = t
#     log.info("Payment entry sync daemon started.")
#     return t


# # =============================================================================
# # DEBUG
# # =============================================================================

# if __name__ == "__main__":
#     logging.basicConfig(level=logging.INFO,
#                         format="%(asctime)s [%(levelname)s] %(message)s")
#     print("Running one payment entry sync cycle...")
#     r = push_unsynced_payment_entries()
#     print(f"\nResult: {r['pushed']} pushed, {r['failed']} failed, "
#           f"{r['skipped']} skipped (of {r['total']} total)")


# =============================================================================
# services/payment_entry_service.py
#
# Manages local payment_entries table and syncs them to Frappe.
#
# FLOW:
#   1. When a sale is saved locally → create_payment_entry() stores it locally
#      with synced=0
#   2. When the Sales Invoice is confirmed on Frappe (frappe_ref is set) →
#      push_unsynced_payment_entries() pushes the Payment Entry to Frappe
#   3. Frappe returns a PAY-xxxxx ref → stored as frappe_payment_ref, synced=1
#
# PAYLOAD SENT TO FRAPPE:
#   POST /api/resource/Payment Entry
#   {
#     "doctype":              "Payment Entry",
#     "payment_type":         "Receive",
#     "party_type":           "Customer",
#     "party":                "Cathy",
#     "paid_to":              "Cash ZWG - H",
#     "paid_to_account_currency": "USD",
#     "paid_amount":          32.45,
#     "received_amount":      32.45,
#     "source_exchange_rate": 1.0,
#     "reference_no":         "ACC-SINV-2026-00034",
#     "reference_date":       "2026-03-19",
#     "remarks":              "POS Payment — Cash",
#     "docstatus":            1,
#     "references": [{
#         "reference_doctype": "Sales Invoice",
#         "reference_name":    "ACC-SINV-2026-00565",
#         "allocated_amount":  32.45
#     }]
#   }
# =============================================================================

from __future__ import annotations

import json
import logging
import time
import threading
import urllib.request
import urllib.error
from datetime import date

log = logging.getLogger("PaymentEntry")

SYNC_INTERVAL   = 60      # seconds between auto-sync cycles
REQUEST_TIMEOUT = 30

# Exchange rate cache: "FROM::TO::DATE" → float
_RATE_CACHE: dict[str, float] = {}


def _get_exchange_rate(from_currency: str, to_currency: str,
                       transaction_date: str,
                       api_key: str, api_secret: str, host: str) -> float:
    """
    Fetch live exchange rate from Frappe.
    Returns 1.0 for same currency, 0.0 if fetch fails (Frappe uses its own rate).
    """
    if not from_currency or from_currency.upper() == to_currency.upper():
        return 1.0

    cache_key = f"{from_currency.upper()}::{to_currency.upper()}::{transaction_date}"
    if cache_key in _RATE_CACHE:
        return _RATE_CACHE[cache_key]

    try:
        import urllib.parse
        url = (
            f"{host}/api/method/erpnext.setup.utils.get_exchange_rate"
            f"?from_currency={urllib.parse.quote(from_currency)}"
            f"&to_currency={urllib.parse.quote(to_currency)}"
            f"&transaction_date={transaction_date}"
        )
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"token {api_key}:{api_secret}")
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
            data = json.loads(r.read().decode())
            rate = float(data.get("message") or data.get("result") or 0)
            if rate > 0:
                _RATE_CACHE[cache_key] = rate
                log.debug("Rate %s→%s on %s: %.6f", from_currency, to_currency, transaction_date, rate)
                return rate
    except Exception as e:
        log.debug("Rate fetch failed (%s→%s): %s", from_currency, to_currency, e)

    return 0.0

_sync_lock:   threading.Lock          = threading.Lock()
_sync_thread: threading.Thread | None = None

# Method → Frappe Mode of Payment name
_METHOD_MAP = {
    "CASH":     "Cash",
    "CARD":     "Credit Card",
    "C / CARD": "Credit Card",
    "EFTPOS":   "Credit Card",
    "CHECK":    "Cheque",
    "CHEQUE":   "Cheque",
    "MOBILE":   "Mobile Money",
    "CREDIT":   "Credit",
    "TRANSFER": "Bank Transfer",
}


# =============================================================================
# CREDENTIALS / HOST / DEFAULTS
# =============================================================================

def _get_credentials() -> tuple[str, str]:
    try:
        from services.credentials import get_credentials
        return get_credentials()
    except Exception:
        pass
    return "", ""

def _get_host() -> str:
    try:
        from models.company_defaults import get_defaults
        host = (get_defaults() or {}).get("server_api_host", "").strip().rstrip("/")
        if host:
            return host
    except Exception:
        pass
    return "https://apk.havano.cloud"


def _get_defaults() -> dict:
    try:
        from models.company_defaults import get_defaults
        return get_defaults() or {}
    except Exception:
        return {}


# =============================================================================
# GL ACCOUNT RESOLVER  (which account to credit for each payment method)
# =============================================================================

_ACCOUNT_CACHE: dict[str, str] = {}


def _resolve_paid_to_account(mop_name: str, company: str, currency: str,
                              api_key: str, api_secret: str, host: str) -> str:
    """
    Looks up the GL account for a Mode of Payment from Frappe.
    Tries to match by currency if multiple accounts exist for the company.
    Falls back to server_pos_account in company_defaults.
    """
    cache_key = f"{mop_name}::{company}::{currency}"
    if cache_key in _ACCOUNT_CACHE:
        return _ACCOUNT_CACHE[cache_key]

    try:
        import urllib.parse
        url = (f"{host}/api/resource/Mode%20of%20Payment/"
               f"{urllib.parse.quote(mop_name)}?fields=[\"accounts\"]")
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"token {api_key}:{api_secret}")
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
            data     = json.loads(r.read().decode())
            accounts = (data.get("data") or {}).get("accounts", [])

        company_accts = [a for a in accounts
                         if not company or a.get("company") == company]

        # Prefer account whose name contains the currency code
        matched = ""
        if currency:
            for a in company_accts:
                if currency.upper() in (a.get("default_account") or "").upper():
                    matched = a["default_account"]; break

        if not matched and company_accts:
            matched = company_accts[0].get("default_account", "")

        if matched:
            _ACCOUNT_CACHE[cache_key] = matched
            return matched

    except Exception as e:
        log.debug("MOP account lookup failed for '%s': %s", mop_name, e)

    # Fallback
    fallback = _get_defaults().get("server_pos_account", "").strip()
    if fallback:
        _ACCOUNT_CACHE[cache_key] = fallback
        return fallback

    log.warning("No GL account for MOP '%s' currency=%s — Payment Entry may fail.",
                mop_name, currency)
    return ""


# =============================================================================
# LOCAL DB  — create / read / update payment_entries
# =============================================================================

def create_payment_entry(sale: dict, override_rate: float = None,
                         override_account: str = None) -> int | None:
    """
    Called immediately after a sale is saved locally.
    Stores a payment_entry row with synced=0.
    Returns the new payment_entry id, or None on error.

    Will only create the entry once per sale (idempotent).
    """
    from database.db import get_connection
    conn = get_connection(); cur = conn.cursor()

    # Idempotency: don't create twice for the same sale
    cur.execute("SELECT id FROM payment_entries WHERE sale_id = ?", (sale["id"],))
    if cur.fetchone():
        conn.close()
        return None

    _walk_in   = _get_defaults().get("server_walk_in_customer", "").strip() or "default"
    customer   = (sale.get("customer_name") or "").strip() or _walk_in
    currency   = (sale.get("currency")      or "USD").strip().upper()
    amount     = float(sale.get("total")    or 0)
    inv_no     = sale.get("invoice_no", "")
    inv_date   = sale.get("invoice_date") or date.today().isoformat()
    method     = str(sale.get("method", "CASH")).upper().strip()
    mop        = _METHOD_MAP.get(method, "Cash")

    # Use override rate (from split) or fetch from Frappe
    if override_rate is not None:
        exch_rate = override_rate
    else:
        try:
            api_key, api_secret = _get_credentials()
            host = _get_host()
            defaults = _get_defaults()
            company_currency = defaults.get("server_company_currency", "USD").strip().upper() or "USD"
            exch_rate = _get_exchange_rate(
                currency, company_currency, inv_date, api_key, api_secret, host
            ) if currency != company_currency else 1.0
        except Exception:
            exch_rate = 1.0

    cur.execute("""
        INSERT INTO payment_entries (
            sale_id, sale_invoice_no, frappe_invoice_ref,
            party, party_name,
            paid_amount, received_amount, source_exchange_rate,
            paid_to_account_currency, currency,
            mode_of_payment,
            reference_no, reference_date,
            remarks, synced
        ) OUTPUT INSERTED.id
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
    """, (
        sale["id"], inv_no,
        sale.get("frappe_ref") or None,
        customer, customer,
        amount, amount, exch_rate or 1.0,
        currency, currency,
        mop,
        inv_no, inv_date,
        f"POS Payment — {mop}",
    ))
    new_id = int(cur.fetchone()[0])
    conn.commit(); conn.close()
    log.debug("Payment entry %d created locally for sale %s", new_id, inv_no)
    return new_id


def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
    """
    Called when cashier uses Split payment.
    Creates one payment_entry row per currency in splits list.
    splits = [{"mode": "CASH", "currency": "USD", "amount": 5.0,
               "rate": 1.0, "base_amount": 5.0, "account": "Cash - AT"}, ...]
    Returns list of new payment_entry ids.
    """
    ids = []
    for split in splits:
        if not split.get("amount") or float(split["amount"]) <= 0:
            continue
        # Build a sale-like dict with the split's currency and amount
        split_sale = dict(sale)
        split_sale["currency"]      = split.get("currency", "USD")
        split_sale["total"]         = float(split.get("amount", 0))
        split_sale["method"]        = split.get("mode", "CASH")
        # Override exchange rate from split data
        new_id = create_payment_entry(
            split_sale,
            override_rate=float(split.get("rate", 1.0)),
            override_account=split.get("account", ""),
        )
        if new_id:
            ids.append(new_id)
    return ids


def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
    """
    Creates one payment_entry per currency from a split payment.
    Groups splits by currency, sums amounts, creates one entry each.
    Returns list of created payment_entry ids.
    """
    from datetime import date as _date

    # Group by currency
    by_currency: dict[str, dict] = {}
    for s in splits:
        curr = s.get("account_currency", "USD").upper()
        if curr not in by_currency:
            by_currency[curr] = {
                "currency":      curr,
                "paid_amount":   0.0,
                "base_value":    0.0,
                "rate":          s.get("rate", 1.0),
                "account_name":  s.get("account_name", ""),
                "mode":          s.get("mode", "Cash"),
            }
        by_currency[curr]["paid_amount"] += s.get("amount_paid", 0.0)
        by_currency[curr]["base_value"]  += s.get("base_value",  0.0)

    ids = []
    inv_no   = sale.get("invoice_no", "")
    inv_date = sale.get("invoice_date") or _date.today().isoformat()
    _walk_in = _get_defaults().get("server_walk_in_customer", "").strip() or "default"
    customer = (sale.get("customer_name") or "").strip() or _walk_in

    from database.db import get_connection
    conn = get_connection(); cur = conn.cursor()

    for curr, grp in by_currency.items():
        # Idempotency: skip if already exists for this sale+currency
        cur.execute(
            "SELECT id FROM payment_entries WHERE sale_id=? AND currency=?",
            (sale["id"], curr)
        )
        if cur.fetchone():
            continue

        mop = _METHOD_MAP.get(grp["mode"].upper(), "Cash")

        cur.execute("""
            INSERT INTO payment_entries (
                sale_id, sale_invoice_no, frappe_invoice_ref,
                party, party_name,
                paid_amount, received_amount, source_exchange_rate,
                paid_to_account_currency, currency,
                paid_to,
                mode_of_payment,
                reference_no, reference_date,
                remarks, synced
            ) OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        """, (
            sale["id"], inv_no,
            sale.get("frappe_ref") or None,
            customer, customer,
            grp["paid_amount"],
            grp["base_value"],
            float(grp["rate"] or 1.0),
            curr, curr,
            grp["account_name"],
            mop,
            inv_no, inv_date,
            f"POS Split Payment — {mop} ({curr})",
        ))
        new_id = int(cur.fetchone()[0])
        ids.append(new_id)
        log.debug("Split payment entry %d created: %s %.2f %s",
                  new_id, curr, grp["paid_amount"], inv_no)

    conn.commit(); conn.close()
    return ids


def get_unsynced_payment_entries() -> list[dict]:
    """
    Returns regular payment entries (Sales Receipts) that are ready to push (synced=0).
    Filters out Credit Note payments ('Pay') so they don't block the queue.
    """
    from database.db import get_connection, fetchall_dicts
    conn = get_connection()
    cur = conn.cursor()
    
    # We add (pe.payment_type IS NULL OR pe.payment_type = 'Receive')
    # This ensures old records (where type might be null) and new regular sales 
    # are processed, but it EXCLUDES 'Pay' (Credit Notes).
    cur.execute("""
        SELECT pe.*, s.frappe_ref AS sale_frappe_ref
        FROM payment_entries pe
        LEFT JOIN sales s ON s.id = pe.sale_id
        WHERE pe.synced = 0
          AND (pe.payment_type IS NULL OR pe.payment_type = 'Receive')
          AND (pe.frappe_invoice_ref IS NOT NULL
               OR s.frappe_ref IS NOT NULL)
        ORDER BY pe.id
    """)
    
    rows = fetchall_dicts(cur)
    conn.close()
    return rows

def mark_payment_synced(pe_id: int, frappe_payment_ref: str = "") -> None:
    from database.db import get_connection
    conn = get_connection(); cur = conn.cursor()
    cur.execute(
        "UPDATE payment_entries SET synced=1, frappe_payment_ref=? WHERE id=?",
        (frappe_payment_ref or None, pe_id)
    )
    # Also update the sales row
    cur.execute("""
        UPDATE sales SET payment_entry_ref=?, payment_synced=1
        WHERE id = (SELECT sale_id FROM payment_entries WHERE id=?)
    """, (frappe_payment_ref or None, pe_id))
    conn.commit(); conn.close()


def refresh_frappe_refs() -> int:
    """
    For payment entries that have no frappe_invoice_ref yet, copy it from
    the parent sale's frappe_ref. Call this before pushing payments.
    Returns count updated.
    """
    from database.db import get_connection
    conn = get_connection(); cur = conn.cursor()
    cur.execute("""
        UPDATE pe
        SET pe.frappe_invoice_ref = s.frappe_ref
        FROM payment_entries pe
        JOIN sales s ON s.id = pe.sale_id
        WHERE pe.synced = 0
          AND (pe.frappe_invoice_ref IS NULL OR pe.frappe_invoice_ref = '')
          AND s.frappe_ref IS NOT NULL AND s.frappe_ref != ''
    """)
    count = cur.rowcount
    conn.commit(); conn.close()
    return count


# =============================================================================
# BUILD FRAPPE PAYLOAD
# =============================================================================

def _build_payload(pe: dict, defaults: dict,
                   api_key: str, api_secret: str, host: str) -> dict:
    company  = defaults.get("server_company", "")
    currency = (pe.get("currency") or pe.get("paid_to_account_currency") or "USD").upper()
    mop      = pe.get("mode_of_payment") or "Cash"
    amount   = float(pe.get("paid_amount") or 0)
    frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()

    # Use local gl_accounts table first (synced from Frappe)
    paid_to          = (pe.get("paid_to") or "").strip()
    paid_to_currency = currency
    if not paid_to:
        try:
            from models.gl_account import get_account_for_payment
            acct = get_account_for_payment(currency, company)
            if acct:
                paid_to          = acct["name"]
                paid_to_currency = acct["account_currency"]
        except Exception as _e:
            log.debug("gl_account lookup failed: %s", _e)

    # Fallback to live Frappe lookup
    if not paid_to:
        paid_to = _resolve_paid_to_account(mop, company, currency, api_key, api_secret, host)

    # Use local exchange rate if not stored
    exch_rate = float(pe.get("source_exchange_rate") or 1.0)
    if exch_rate == 1.0 and currency not in ("USD", ""):
        try:
            from models.exchange_rate import get_rate
            stored = get_rate(currency, "USD")
            if stored:
                exch_rate = stored
        except Exception:
            pass

    # Resolve walk-in: if party stored as "Walk-in" substitute with server_walk_in_customer
    # so it matches the exact name used when the sales invoice was pushed to Frappe
    _walk_in  = defaults.get("server_walk_in_customer", "").strip() or "default"
    _WALK_IN_ALIASES = {"walk-in", "walk in", "walkin", ""}
    raw_party = (pe.get("party") or "").strip()
    party     = _walk_in if raw_party.lower() in _WALK_IN_ALIASES else raw_party or _walk_in

    payload = {
        "doctype":                  "Payment Entry",
        "payment_type":             "Receive",
        "party_type":               "Customer",
        "party":                    party,
        "party_name":               party,
        "paid_to_account_currency": paid_to_currency,
        "paid_amount":              amount,
        "received_amount":          amount,
        "source_exchange_rate":     exch_rate,
        "reference_no":             pe.get("reference_no") or pe.get("sale_invoice_no", ""),
        "reference_date":           (
            pe.get("reference_date").isoformat()
            if hasattr(pe.get("reference_date"), "isoformat")
            else pe.get("reference_date") or date.today().isoformat()
        ),
        "remarks":                  pe.get("remarks") or f"POS Payment — {mop}",
        "mode_of_payment":          mop,
        "docstatus":                1,
    }

    if paid_to:
        payload["paid_to"] = paid_to
    if company:
        payload["company"] = company

    # Link to the Sales Invoice on Frappe
    if frappe_inv:
        payload["references"] = [{
            "reference_doctype": "Sales Invoice",
            "reference_name":    frappe_inv,
            "allocated_amount":  amount,
        }]

    return payload


# =============================================================================
# PUSH ONE PAYMENT ENTRY
# =============================================================================

def _push_payment_entry(pe: dict, api_key: str, api_secret: str,
                        defaults: dict, host: str) -> str | None:
    """
    Posts one payment entry to Frappe.
    Returns Frappe's PAY-xxxxx name on success, None on failure.
    """
    pe_id  = pe["id"]
    inv_no = pe.get("sale_invoice_no", str(pe_id))

    frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()
    if not frappe_inv:
        log.warning("Payment %d — Sales Invoice not yet on Frappe, skipping.", pe_id)
        return None

    payload = _build_payload(pe, defaults, api_key, api_secret, host)

    url = f"{host}/api/resource/Payment%20Entry"
    req = urllib.request.Request(
        url=url,
        data=json.dumps(payload, default=lambda o: o.isoformat() if hasattr(o, 'isoformat') else str(o)).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type":  "application/json",
            "Accept":        "application/json",
            "Authorization": f"token {api_key}:{api_secret}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
            name = (data.get("data") or {}).get("name", "")
            log.info("✅ Payment Entry %d → Frappe %s  [%s  %s %.2f]",
                     pe_id, name, inv_no,
                     pe.get("currency", ""), float(pe.get("paid_amount", 0)))
            return name or "SYNCED"

    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode())
            msg = (err.get("exception") or err.get("message") or
                   str(err.get("_server_messages", "")) or f"HTTP {e.code}")
        except Exception:
            msg = f"HTTP {e.code}"

        if e.code == 409:
            log.info("Payment %d already on Frappe (409) - marking synced.", pe_id)
            return "DUPLICATE"

        # Invoice already paid (is_pos:1 on old invoices) - stop retrying
        if e.code == 417:
            _perma = ("already been fully paid", "already paid", "fully paid")
            if any(p in msg.lower() for p in _perma):
                log.info("Payment %d - invoice already paid on Frappe, marking synced.", pe_id)
                return "ALREADY_PAID"

        log.error("FAIL Payment Entry %d  HTTP %s: %s", pe_id, e.code, msg)
        return None

    except urllib.error.URLError as e:
        log.warning("Network error pushing payment %d: %s", pe_id, e.reason)
        return None

    except Exception as e:
        log.error("Unexpected error pushing payment %d: %s", pe_id, e)
        return None


# =============================================================================
# PUBLIC — push all unsynced payment entries
# =============================================================================

def push_unsynced_payment_entries() -> dict:
    """
    1. Refresh frappe_invoice_ref from parent sales that were confirmed.
    2. Push each unsynced payment entry to Frappe.
    3. Mark synced with the returned PAY-xxxxx ref.
    """
    result = {"pushed": 0, "failed": 0, "skipped": 0, "total": 0}

    api_key, api_secret = _get_credentials()
    if not api_key or not api_secret:
        log.warning("No credentials — skipping payment entry sync.")
        return result

    host     = _get_host()
    defaults = _get_defaults()

    # First: pull frappe_refs from confirmed invoices into pending payment entries
    updated = refresh_frappe_refs()
    if updated:
        log.info("Refreshed frappe_invoice_ref on %d payment entry(ies).", updated)

    entries = get_unsynced_payment_entries()
    result["total"] = len(entries)

    if not entries:
        log.debug("No unsynced payment entries.")
        return result

    log.info("Pushing %d payment entry(ies) to Frappe…", len(entries))

    for pe in entries:
        frappe_name = _push_payment_entry(pe, api_key, api_secret, defaults, host)
        if frappe_name:
            mark_payment_synced(pe["id"], frappe_name)
            result["pushed"] += 1
        elif frappe_name is None:
            # None = permanent skip (no frappe_inv yet), not a real failure
            result["skipped"] += 1
        else:
            result["failed"] += 1

        time.sleep(3)   # rate limit — 20/min max

    log.info("Payment sync done — ✅ %d pushed  ❌ %d failed  ⏭ %d skipped",
             result["pushed"], result["failed"], result["skipped"])
    return result


# =============================================================================
# BACKGROUND DAEMON THREAD
# =============================================================================

def _sync_loop():
    log.info("Payment entry sync daemon started (interval=%ds).", SYNC_INTERVAL)
    while True:
        if _sync_lock.acquire(blocking=False):
            try:
                push_unsynced_payment_entries()
            except Exception as e:
                log.error("Payment sync cycle error: %s", e)
            finally:
                _sync_lock.release()
        else:
            log.debug("Previous payment sync still running — skipping.")
        time.sleep(SYNC_INTERVAL)


def start_payment_sync_daemon() -> threading.Thread:
    """Non-blocking — safe to call from MainWindow.__init__."""
    global _sync_thread
    if _sync_thread and _sync_thread.is_alive():
        return _sync_thread
    t = threading.Thread(target=_sync_loop, daemon=True, name="PaymentSyncDaemon")
    t.start()
    _sync_thread = t
    log.info("Payment entry sync daemon started.")
    return t


# =============================================================================
# DEBUG
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    print("Running one payment entry sync cycle...")
    r = push_unsynced_payment_entries()
    print(f"\nResult: {r['pushed']} pushed, {r['failed']} failed, "
          f"{r['skipped']} skipped (of {r['total']} total)")