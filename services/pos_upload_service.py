# # # # # # =============================================================================
# # # # # # services/pos_upload_service.py  —  Push local POS sales → Frappe
# # # # # # Rate-limited to 20 invoices/minute to stay within Frappe's limits.
# # # # # # Sends as submitted (docstatus=1). Customer resolved dynamically — no hardcoding.
# # # # # # =============================================================================

# # # # # from __future__ import annotations

# # # # # import json
# # # # # import logging
# # # # # import time
# # # # # import threading
# # # # # import urllib.request
# # # # # import urllib.error
# # # # # import urllib.parse
# # # # # from datetime import datetime

# # # # # log = logging.getLogger("POSUpload")

# # # # # UPLOAD_INTERVAL   = 60    # seconds between full cycles
# # # # # REQUEST_TIMEOUT   = 30
# # # # # MAX_PER_MINUTE    = 20    # Frappe rate limit guard
# # # # # INTER_PUSH_DELAY  = 60 / MAX_PER_MINUTE   # 3 s between each push


# # # # # # =============================================================================
# # # # # # CREDENTIALS / DEFAULTS
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
# # # # #     return (os.environ.get("HAVANO_API_KEY", ""), os.environ.get("HAVANO_API_SECRET", ""))


# # # # # def _get_defaults() -> dict:
# # # # #     try:
# # # # #         from models.company_defaults import get_defaults
# # # # #         return get_defaults() or {}
# # # # #     except Exception:
# # # # #         return {}


# # # # # def _get_host() -> str:
# # # # #     try:
# # # # #         host = _get_defaults().get("server_api_host", "").strip().rstrip("/")
# # # # #         if host:
# # # # #             return host
# # # # #     except Exception:
# # # # #         pass
# # # # #     return "https://apk.havano.cloud"


# # # # # # =============================================================================
# # # # # # PAYMENT METHOD MAP + ACCOUNT RESOLVER
# # # # # # =============================================================================

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

# # # # # # Cache: mode_of_payment name → GL account string (fetched once per session)
# # # # # _MOP_ACCOUNT_CACHE: dict[str, str] = {}


# # # # # def _get_mop_account(mop_name: str, company: str,
# # # # #                      api_key: str, api_secret: str, host: str) -> str:
# # # # #     """
# # # # #     Returns the GL account for a Mode of Payment + Company combination.
# # # # #     Tries: 1) session cache  2) Frappe MOP API  3) company_defaults fallback
# # # # #     """
# # # # #     cache_key = f"{mop_name}::{company}"
# # # # #     if cache_key in _MOP_ACCOUNT_CACHE:
# # # # #         return _MOP_ACCOUNT_CACHE[cache_key]

# # # # #     # Try fetching from Frappe's Mode of Payment doctype
# # # # #     try:
# # # # #         url = (
# # # # #             f"{host}/api/resource/Mode%20of%20Payment/{urllib.parse.quote(mop_name)}"
# # # # #             f"?fields=[\"accounts\"]"
# # # # #         )
# # # # #         req = urllib.request.Request(url)
# # # # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # # # #             data     = json.loads(r.read().decode())
# # # # #             accounts = (data.get("data") or {}).get("accounts", [])
# # # # #             # accounts is a list of {company, default_account}
# # # # #             for row in accounts:
# # # # #                 if not company or row.get("company") == company:
# # # # #                     acct = row.get("default_account", "")
# # # # #                     if acct:
# # # # #                         _MOP_ACCOUNT_CACHE[cache_key] = acct
# # # # #                         log.debug("MOP account resolved: %s → %s", mop_name, acct)
# # # # #                         return acct
# # # # #     except Exception as e:
# # # # #         log.debug("Could not fetch MOP account for '%s': %s", mop_name, e)

# # # # #     # Fallback: use server_pos_account from company_defaults if set
# # # # #     fallback = _get_defaults().get("server_pos_account", "").strip()
# # # # #     if fallback:
# # # # #         _MOP_ACCOUNT_CACHE[cache_key] = fallback
# # # # #         log.debug("MOP account fallback (company_defaults): %s", fallback)
# # # # #         return fallback

# # # # #     log.warning(
# # # # #         "No GL account found for MOP '%s'. "
# # # # #         "Set 'server_pos_account' in company_defaults or configure accounts on "
# # # # #         "the Mode of Payment in Frappe.", mop_name
# # # # #     )
# # # # #     return ""


# # # # # # =============================================================================
# # # # # # BUILD PAYLOAD
# # # # # # =============================================================================

# # # # # def _build_payload(sale: dict, items: list[dict], defaults: dict,
# # # # #                    api_key: str = "", api_secret: str = "") -> dict:
# # # # #     company           = defaults.get("server_company",           "")
# # # # #     warehouse         = defaults.get("server_warehouse",         "")
# # # # #     cost_center       = defaults.get("server_cost_center",       "")
# # # # #     taxes_and_charges = defaults.get("server_taxes_and_charges", "")
# # # # #     walk_in           = defaults.get("server_walk_in_customer",  "default").strip() or "default"
# # # # #     host              = _get_host()

# # # # #     customer = (sale.get("customer_name") or "").strip() or walk_in

# # # # #     posting_date = sale.get("invoice_date") or datetime.today().strftime("%Y-%m-%d")
# # # # #     raw_time     = sale.get("time")         or datetime.now().strftime("%H:%M:%S")
# # # # #     posting_time = str(raw_time) if len(str(raw_time)) == 8 else str(raw_time) + ":00"

# # # # #     mode_of_payment = _METHOD_MAP.get(str(sale.get("method", "")).upper().strip(), "Cash")
# # # # #     mop_account     = _get_mop_account(mode_of_payment, company, api_key, api_secret, host)

# # # # #     frappe_items = []
# # # # #     for it in items:
# # # # #         item_code = (it.get("part_no") or "").strip()
# # # # #         qty       = float(it.get("qty",   0))
# # # # #         rate      = float(it.get("price", 0))
# # # # #         if not item_code or qty <= 0:
# # # # #             continue
# # # # #         row = {"item_code": item_code, "qty": qty, "rate": rate}
# # # # #         if cost_center:
# # # # #             row["cost_center"] = cost_center
# # # # #         frappe_items.append(row)

# # # # #     if not frappe_items:
# # # # #         return {}

# # # # #     total = float(sale.get("total", 0))

# # # # #     payment_entry = {"mode_of_payment": mode_of_payment, "amount": total}
# # # # #     if mop_account:
# # # # #         payment_entry["account"] = mop_account

# # # # #     payload = {
# # # # #         "customer":               customer,
# # # # #         "posting_date":           posting_date,
# # # # #         "posting_time":           posting_time,
# # # # #         "is_pos":                 1,   # honours payments[] and marks invoice paid
# # # # #         "update_stock":           0,   # POS owns stock — avoids NegativeStockError
# # # # #         "docstatus":              1,   # submit immediately
# # # # #         "custom_sales_reference": sale.get("invoice_no", ""),
# # # # #         "payments":               [payment_entry],
# # # # #         "items":                  frappe_items,
# # # # #     }

# # # # #     if company:           payload["company"]           = company
# # # # #     if cost_center:       payload["cost_center"]       = cost_center
# # # # #     if warehouse:         payload["set_warehouse"]     = warehouse
# # # # #     if taxes_and_charges: payload["taxes_and_charges"] = taxes_and_charges

# # # # #     return payload


# # # # # # =============================================================================
# # # # # # PUSH ONE SALE
# # # # # # =============================================================================

# # # # # def _push_sale(sale: dict, api_key: str, api_secret: str,
# # # # #                defaults: dict, host: str) -> bool:
# # # # #     inv_no  = sale.get("invoice_no", str(sale["id"]))
# # # # #     walk_in = defaults.get("server_walk_in_customer", "default").strip() or "default"

# # # # #     try:
# # # # #         from models.sale import get_sale_items
# # # # #         items = get_sale_items(sale["id"])
# # # # #     except Exception as e:
# # # # #         log.error("Items fetch failed for %s: %s", inv_no, e)
# # # # #         return False

# # # # #     payload = _build_payload(sale, items, defaults, api_key, api_secret)
# # # # #     if not payload:
# # # # #         log.warning("Sale %s — no valid items, skipping (marked synced).", inv_no)
# # # # #         return True

# # # # #     url = f"{host}/api/resource/Sales%20Invoice"

# # # # #     # Two attempts: real customer first, walk-in fallback second
# # # # #     attempts = [payload]
# # # # #     if payload["customer"] != walk_in:
# # # # #         attempts.append({**payload, "customer": walk_in})

# # # # #     for i, p in enumerate(attempts):
# # # # #         req = urllib.request.Request(
# # # # #             url=url,
# # # # #             data=json.dumps(p).encode("utf-8"),
# # # # #             method="POST",
# # # # #             headers={
# # # # #                 "Content-Type":  "application/json",
# # # # #                 "Accept":        "application/json",
# # # # #                 "Authorization": f"token {api_key}:{api_secret}",
# # # # #             },
# # # # #         )
# # # # #         try:
# # # # #             with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
# # # # #                 name = (json.loads(resp.read()).get("data") or {}).get("name", "")
# # # # #                 suffix = f" [walk-in fallback: {walk_in}]" if i > 0 else ""
# # # # #                 log.info("✅ %s → Frappe %s  customer=%s%s",
# # # # #                          inv_no, name, p["customer"], suffix)
# # # # #                 return True

# # # # #         except urllib.error.HTTPError as e:
# # # # #             try:
# # # # #                 err = json.loads(e.read().decode())
# # # # #                 msg = (err.get("exception") or err.get("message") or
# # # # #                        str(err.get("_server_messages", "")) or f"HTTP {e.code}")
# # # # #             except Exception:
# # # # #                 msg = f"HTTP {e.code}"

# # # # #             if e.code == 409:
# # # # #                 log.info("Sale %s already exists on Frappe (409) — marking synced.", inv_no)
# # # # #                 return True

# # # # #             # Permanent Frappe-side data errors — not retryable.
# # # # #             # Mark synced to stop the retry loop; fix the data in Frappe manually.
# # # # #             _PERMANENT_ERRORS = (
# # # # #                 "negativestockerror",
# # # # #                 "not marked as sales item",
# # # # #                 "is not a sales item",
# # # # #             )
# # # # #             if e.code == 417 and any(p in msg.lower() for p in _PERMANENT_ERRORS):
# # # # #                 log.warning(
# # # # #                     "⚠️  Sale %s — permanent Frappe data error (marked synced to stop loop).\n  %s",
# # # # #                     inv_no, msg,
# # # # #                 )
# # # # #                 return True   # mark_synced called by caller

# # # # #             # Customer-not-found error → retry with walk-in on next attempt
# # # # #             if i == 0 and e.code in (417, 500) and any(
# # # # #                 kw in msg.lower() for kw in ("customer", "payment_terms", "nonetype")
# # # # #             ):
# # # # #                 log.warning("Sale %s — customer '%s' rejected, retrying with walk-in…",
# # # # #                             inv_no, p["customer"])
# # # # #                 continue

# # # # #             log.error("❌ Sale %s  HTTP %s: %s", inv_no, e.code, msg)
# # # # #             return False

# # # # #         except urllib.error.URLError as e:
# # # # #             log.warning("Network error pushing %s: %s", inv_no, e.reason)
# # # # #             return False

# # # # #         except Exception as e:
# # # # #             log.error("Unexpected error pushing %s: %s", inv_no, e)
# # # # #             return False

# # # # #     return False


# # # # # # =============================================================================
# # # # # # PUBLIC — push all unsynced (rate-limited to MAX_PER_MINUTE)
# # # # # # =============================================================================

# # # # # def push_unsynced_sales() -> dict:
# # # # #     result = {"pushed": 0, "failed": 0, "total": 0}

# # # # #     api_key, api_secret = _get_credentials()
# # # # #     if not api_key or not api_secret:
# # # # #         log.warning("No API credentials — skipping upload cycle.")
# # # # #         return result

# # # # #     host     = _get_host()
# # # # #     defaults = _get_defaults()

# # # # #     try:
# # # # #         from models.sale import get_unsynced_sales, mark_synced
# # # # #         sales = get_unsynced_sales()
# # # # #     except Exception as e:
# # # # #         log.error("Could not read unsynced sales: %s", e)
# # # # #         return result

# # # # #     result["total"] = len(sales)
# # # # #     if not sales:
# # # # #         log.debug("No unsynced sales.")
# # # # #         return result

# # # # #     log.info("Pushing %d sale(s) to Frappe (max %d/min)…", len(sales), MAX_PER_MINUTE)

# # # # #     for idx, sale in enumerate(sales):
# # # # #         if idx > 0 and idx % MAX_PER_MINUTE == 0:
# # # # #             log.info("Rate limit pause — waiting 60s before next batch…")
# # # # #             time.sleep(60)

# # # # #         ok = _push_sale(sale, api_key, api_secret, defaults, host)
# # # # #         if ok:
# # # # #             try:
# # # # #                 mark_synced(sale["id"])
# # # # #                 result["pushed"] += 1
# # # # #             except Exception as e:
# # # # #                 log.error("mark_synced failed for sale %s: %s", sale["id"], e)
# # # # #                 result["failed"] += 1
# # # # #         else:
# # # # #             result["failed"] += 1

# # # # #         if idx < len(sales) - 1:
# # # # #             time.sleep(INTER_PUSH_DELAY)   # 3 s between each push

# # # # #     log.info("Upload done — ✅ %d pushed  ❌ %d failed  (of %d)",
# # # # #              result["pushed"], result["failed"], result["total"])
# # # # #     return result


# # # # # # =============================================================================
# # # # # # QTHREAD WORKER
# # # # # # =============================================================================

# # # # # try:
# # # # #     from PySide6.QtCore import QObject  # type: ignore

# # # # #     class UploadWorker(QObject):
# # # # #         def run(self) -> None:
# # # # #             log.info("POS upload worker started (interval=%ds, max=%d/min).",
# # # # #                      UPLOAD_INTERVAL, MAX_PER_MINUTE)
# # # # #             while True:
# # # # #                 try:
# # # # #                     push_unsynced_sales()
# # # # #                 except Exception as exc:
# # # # #                     log.error("Unhandled error in upload worker: %s", exc)
# # # # #                 time.sleep(UPLOAD_INTERVAL)

# # # # # except ImportError:
# # # # #     class UploadWorker:              # type: ignore[no-redef]
# # # # #         def run(self) -> None:
# # # # #             pass


# # # # # def start_upload_thread() -> object:
# # # # #     """Start the upload background thread — call once from MainWindow.__init__."""
# # # # #     try:
# # # # #         from PySide6.QtCore import QThread  # type: ignore
# # # # #         thread = QThread()
# # # # #         worker = UploadWorker()
# # # # #         worker.moveToThread(thread)
# # # # #         thread.started.connect(worker.run)
# # # # #         thread._worker = worker      # prevent GC
# # # # #         thread.start()
# # # # #         log.info("POS upload QThread started.")
# # # # #         return thread
# # # # #     except ImportError:
# # # # #         def _loop():
# # # # #             while True:
# # # # #                 try:
# # # # #                     push_unsynced_sales()
# # # # #                 except Exception as exc:
# # # # #                     log.error("Unhandled error: %s", exc)
# # # # #                 time.sleep(UPLOAD_INTERVAL)
# # # # #         t = threading.Thread(target=_loop, daemon=True, name="POSUploadThread")
# # # # #         t.start()
# # # # #         return t

# # # # # =============================================================================
# # # # # services/pos_upload_service.py  —  Push local POS sales → Frappe
# # # # # Rate-limited to 20 invoices/minute to stay within Frappe's limits.
# # # # # Sends as submitted (docstatus=1). Customer resolved dynamically — no hardcoding.
# # # # # =============================================================================

# # # # from __future__ import annotations

# # # # import json
# # # # import logging
# # # # import time
# # # # import threading
# # # # import urllib.request
# # # # import urllib.error
# # # # import urllib.parse
# # # # from datetime import datetime

# # # # log = logging.getLogger("POSUpload")

# # # # UPLOAD_INTERVAL   = 60    # seconds between full cycles
# # # # REQUEST_TIMEOUT   = 30
# # # # MAX_PER_MINUTE    = 20    # Frappe rate limit guard
# # # # INTER_PUSH_DELAY  = 60 / MAX_PER_MINUTE   # 3 s between each push


# # # # # =============================================================================
# # # # # CREDENTIALS / DEFAULTS
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
# # # #     return (os.environ.get("HAVANO_API_KEY", ""), os.environ.get("HAVANO_API_SECRET", ""))


# # # # def _get_defaults() -> dict:
# # # #     try:
# # # #         from models.company_defaults import get_defaults
# # # #         return get_defaults() or {}
# # # #     except Exception:
# # # #         return {}


# # # # def _get_host() -> str:
# # # #     try:
# # # #         host = _get_defaults().get("server_api_host", "").strip().rstrip("/")
# # # #         if host:
# # # #             return host
# # # #     except Exception:
# # # #         pass
# # # #     return "https://apk.havano.cloud"


# # # # # =============================================================================
# # # # # PAYMENT METHOD MAP + ACCOUNT RESOLVER
# # # # # =============================================================================

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

# # # # # Cache: mode_of_payment name → GL account string (fetched once per session)
# # # # _MOP_ACCOUNT_CACHE: dict[str, str] = {}


# # # # def _get_mop_account(mop_name: str, company: str,
# # # #                      api_key: str, api_secret: str, host: str) -> str:
# # # #     """
# # # #     Returns the GL account for a Mode of Payment + Company combination.
# # # #     Tries: 1) session cache  2) Frappe MOP API  3) company_defaults fallback
# # # #     """
# # # #     cache_key = f"{mop_name}::{company}"
# # # #     if cache_key in _MOP_ACCOUNT_CACHE:
# # # #         return _MOP_ACCOUNT_CACHE[cache_key]

# # # #     # Try fetching from Frappe's Mode of Payment doctype
# # # #     try:
# # # #         url = (
# # # #             f"{host}/api/resource/Mode%20of%20Payment/{urllib.parse.quote(mop_name)}"
# # # #             f"?fields=[\"accounts\"]"
# # # #         )
# # # #         req = urllib.request.Request(url)
# # # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # # #             data     = json.loads(r.read().decode())
# # # #             accounts = (data.get("data") or {}).get("accounts", [])
# # # #             # accounts is a list of {company, default_account}
# # # #             for row in accounts:
# # # #                 if not company or row.get("company") == company:
# # # #                     acct = row.get("default_account", "")
# # # #                     if acct:
# # # #                         _MOP_ACCOUNT_CACHE[cache_key] = acct
# # # #                         log.debug("MOP account resolved: %s → %s", mop_name, acct)
# # # #                         return acct
# # # #     except Exception as e:
# # # #         log.debug("Could not fetch MOP account for '%s': %s", mop_name, e)

# # # #     # Fallback: use server_pos_account from company_defaults if set
# # # #     fallback = _get_defaults().get("server_pos_account", "").strip()
# # # #     if fallback:
# # # #         _MOP_ACCOUNT_CACHE[cache_key] = fallback
# # # #         log.debug("MOP account fallback (company_defaults): %s", fallback)
# # # #         return fallback

# # # #     log.warning(
# # # #         "No GL account found for MOP '%s'. "
# # # #         "Set 'server_pos_account' in company_defaults or configure accounts on "
# # # #         "the Mode of Payment in Frappe.", mop_name
# # # #     )
# # # #     return ""


# # # # # =============================================================================
# # # # # BUILD PAYLOAD
# # # # # =============================================================================

# # # # def _build_payload(sale: dict, items: list[dict], defaults: dict,
# # # #                    api_key: str = "", api_secret: str = "") -> dict:
# # # #     company           = defaults.get("server_company",           "")
# # # #     warehouse         = defaults.get("server_warehouse",         "")
# # # #     cost_center       = defaults.get("server_cost_center",       "")
# # # #     taxes_and_charges = defaults.get("server_taxes_and_charges", "")
# # # #     walk_in           = defaults.get("server_walk_in_customer",  "default").strip() or "default"
# # # #     host              = _get_host()

# # # #     customer = (sale.get("customer_name") or "").strip() or walk_in

# # # #     posting_date = sale.get("invoice_date") or datetime.today().strftime("%Y-%m-%d")
# # # #     raw_time     = sale.get("time")         or datetime.now().strftime("%H:%M:%S")
# # # #     posting_time = str(raw_time) if len(str(raw_time)) == 8 else str(raw_time) + ":00"

# # # #     mode_of_payment = _METHOD_MAP.get(str(sale.get("method", "")).upper().strip(), "Cash")
# # # #     mop_account     = _get_mop_account(mode_of_payment, company, api_key, api_secret, host)

# # # #     frappe_items = []
# # # #     for it in items:
# # # #         item_code = (it.get("part_no") or "").strip()
# # # #         qty       = float(it.get("qty",   0))
# # # #         rate      = float(it.get("price", 0))
# # # #         if not item_code or qty <= 0:
# # # #             continue
# # # #         row = {"item_code": item_code, "qty": qty, "rate": rate}
# # # #         if cost_center:
# # # #             row["cost_center"] = cost_center
# # # #         frappe_items.append(row)

# # # #     if not frappe_items:
# # # #         return {}

# # # #     total = float(sale.get("total", 0))

# # # #     payment_entry = {"mode_of_payment": mode_of_payment, "amount": total}
# # # #     if mop_account:
# # # #         payment_entry["account"] = mop_account

# # # #     payload = {
# # # #         "customer":               customer,
# # # #         "posting_date":           posting_date,
# # # #         "posting_time":           posting_time,
# # # #         "is_pos":                 1,   # honours payments[] and marks invoice paid
# # # #         "update_stock":           0,   # POS owns stock — avoids NegativeStockError
# # # #         "docstatus":              1,   # submit immediately
# # # #         "custom_sales_reference": sale.get("invoice_no", ""),
# # # #         "payments":               [payment_entry],
# # # #         "items":                  frappe_items,
# # # #     }

# # # #     if company:           payload["company"]           = company
# # # #     if cost_center:       payload["cost_center"]       = cost_center
# # # #     if warehouse:         payload["set_warehouse"]     = warehouse
# # # #     if taxes_and_charges: payload["taxes_and_charges"] = taxes_and_charges

# # # #     return payload


# # # # # =============================================================================
# # # # # PUSH ONE SALE
# # # # # =============================================================================

# # # # def _push_sale(sale: dict, api_key: str, api_secret: str,
# # # #                defaults: dict, host: str) -> bool:
# # # #     inv_no  = sale.get("invoice_no", str(sale["id"]))
# # # #     walk_in = defaults.get("server_walk_in_customer", "default").strip() or "default"

# # # #     try:
# # # #         from models.sale import get_sale_items
# # # #         items = get_sale_items(sale["id"])
# # # #     except Exception as e:
# # # #         log.error("Items fetch failed for %s: %s", inv_no, e)
# # # #         return False

# # # #     payload = _build_payload(sale, items, defaults, api_key, api_secret)
# # # #     if not payload:
# # # #         log.warning("Sale %s — no valid items, skipping (marked synced).", inv_no)
# # # #         return True

# # # #     url = f"{host}/api/resource/Sales%20Invoice"

# # # #     # Two attempts: real customer first, walk-in fallback second
# # # #     attempts = [payload]
# # # #     if payload["customer"] != walk_in:
# # # #         attempts.append({**payload, "customer": walk_in})

# # # #     for i, p in enumerate(attempts):
# # # #         req = urllib.request.Request(
# # # #             url=url,
# # # #             data=json.dumps(p).encode("utf-8"),
# # # #             method="POST",
# # # #             headers={
# # # #                 "Content-Type":  "application/json",
# # # #                 "Accept":        "application/json",
# # # #                 "Authorization": f"token {api_key}:{api_secret}",
# # # #             },
# # # #         )
# # # #         try:
# # # #             with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
# # # #                 name = (json.loads(resp.read()).get("data") or {}).get("name", "")
# # # #                 suffix = f" [walk-in fallback: {walk_in}]" if i > 0 else ""
# # # #                 log.info("✅ %s → Frappe %s  customer=%s%s",
# # # #                          inv_no, name, p["customer"], suffix)
# # # #                 return name if name else True

# # # #         except urllib.error.HTTPError as e:
# # # #             try:
# # # #                 err = json.loads(e.read().decode())
# # # #                 msg = (err.get("exception") or err.get("message") or
# # # #                        str(err.get("_server_messages", "")) or f"HTTP {e.code}")
# # # #             except Exception:
# # # #                 msg = f"HTTP {e.code}"

# # # #             if e.code == 409:
# # # #                 log.info("Sale %s already exists on Frappe (409) — marking synced.", inv_no)
# # # #                 return True

# # # #             # Permanent Frappe-side data errors — not retryable.
# # # #             # Mark synced to stop the retry loop; fix the data in Frappe manually.
# # # #             _PERMANENT_ERRORS = (
# # # #                 "negativestockerror",
# # # #                 "not marked as sales item",
# # # #                 "is not a sales item",
# # # #             )
# # # #             if e.code == 417 and any(p in msg.lower() for p in _PERMANENT_ERRORS):
# # # #                 log.warning(
# # # #                     "⚠️  Sale %s — permanent Frappe data error (marked synced to stop loop).\n  %s",
# # # #                     inv_no, msg,
# # # #                 )
# # # #                 return True   # mark_synced called by caller

# # # #             # Customer-not-found error → retry with walk-in on next attempt
# # # #             if i == 0 and e.code in (417, 500) and any(
# # # #                 kw in msg.lower() for kw in ("customer", "payment_terms", "nonetype")
# # # #             ):
# # # #                 log.warning("Sale %s — customer '%s' rejected, retrying with walk-in…",
# # # #                             inv_no, p["customer"])
# # # #                 continue

# # # #             log.error("❌ Sale %s  HTTP %s: %s", inv_no, e.code, msg)
# # # #             return False

# # # #         except urllib.error.URLError as e:
# # # #             log.warning("Network error pushing %s: %s", inv_no, e.reason)
# # # #             return False

# # # #         except Exception as e:
# # # #             log.error("Unexpected error pushing %s: %s", inv_no, e)
# # # #             return False

# # # #     return False


# # # # # =============================================================================
# # # # # PUBLIC — push all unsynced (rate-limited to MAX_PER_MINUTE)
# # # # # =============================================================================

# # # # def push_unsynced_sales() -> dict:
# # # #     result = {"pushed": 0, "failed": 0, "total": 0}

# # # #     api_key, api_secret = _get_credentials()
# # # #     if not api_key or not api_secret:
# # # #         log.warning("No API credentials — skipping upload cycle.")
# # # #         return result

# # # #     host     = _get_host()
# # # #     defaults = _get_defaults()

# # # #     try:
# # # #         from models.sale import get_unsynced_sales, mark_synced, mark_synced_with_ref
# # # #         sales = get_unsynced_sales()
# # # #     except Exception as e:
# # # #         log.error("Could not read unsynced sales: %s", e)
# # # #         return result

# # # #     result["total"] = len(sales)
# # # #     if not sales:
# # # #         log.debug("No unsynced sales.")
# # # #         return result

# # # #     log.info("Pushing %d sale(s) to Frappe (max %d/min)…", len(sales), MAX_PER_MINUTE)

# # # #     for idx, sale in enumerate(sales):
# # # #         if idx > 0 and idx % MAX_PER_MINUTE == 0:
# # # #             log.info("Rate limit pause — waiting 60s before next batch…")
# # # #             time.sleep(60)

# # # #         result_val = _push_sale(sale, api_key, api_secret, defaults, host)
# # # #         if result_val:
# # # #             try:
# # # #                 # result_val is the Frappe doc name string on success, or True for
# # # #                 # permanent-error cases (409, NegativeStockError, not-sales-item)
# # # #                 frappe_ref = result_val if isinstance(result_val, str) else ""
# # # #                 mark_synced_with_ref(sale["id"], frappe_ref)
# # # #                 result["pushed"] += 1
# # # #             except Exception as e:
# # # #                 log.error("mark_synced failed for sale %s: %s", sale["id"], e)
# # # #                 result["failed"] += 1
# # # #         else:
# # # #             result["failed"] += 1

# # # #         if idx < len(sales) - 1:
# # # #             time.sleep(INTER_PUSH_DELAY)   # 3 s between each push

# # # #     log.info("Upload done — ✅ %d pushed  ❌ %d failed  (of %d)",
# # # #              result["pushed"], result["failed"], result["total"])
# # # #     return result


# # # # # =============================================================================
# # # # # QTHREAD WORKER
# # # # # =============================================================================

# # # # try:
# # # #     from PySide6.QtCore import QObject  # type: ignore

# # # #     class UploadWorker(QObject):
# # # #         def run(self) -> None:
# # # #             log.info("POS upload worker started (interval=%ds, max=%d/min).",
# # # #                      UPLOAD_INTERVAL, MAX_PER_MINUTE)
# # # #             while True:
# # # #                 try:
# # # #                     push_unsynced_sales()
# # # #                 except Exception as exc:
# # # #                     log.error("Unhandled error in upload worker: %s", exc)
# # # #                 time.sleep(UPLOAD_INTERVAL)

# # # # except ImportError:
# # # #     class UploadWorker:              # type: ignore[no-redef]
# # # #         def run(self) -> None:
# # # #             pass


# # # # def start_upload_thread() -> object:
# # # #     """Start the upload background thread — call once from MainWindow.__init__."""
# # # #     try:
# # # #         from PySide6.QtCore import QThread  # type: ignore
# # # #         thread = QThread()
# # # #         worker = UploadWorker()
# # # #         worker.moveToThread(thread)
# # # #         thread.started.connect(worker.run)
# # # #         thread._worker = worker      # prevent GC
# # # #         thread.start()
# # # #         log.info("POS upload QThread started.")
# # # #         return thread
# # # #     except ImportError:
# # # #         def _loop():
# # # #             while True:
# # # #                 try:
# # # #                     push_unsynced_sales()
# # # #                 except Exception as exc:
# # # #                     log.error("Unhandled error: %s", exc)
# # # #                 time.sleep(UPLOAD_INTERVAL)
# # # #         t = threading.Thread(target=_loop, daemon=True, name="POSUploadThread")
# # # #         t.start()
# # # #         return t

# # # # =============================================================================
# # # # services/pos_upload_service.py  —  Push local POS sales → Frappe
# # # # Rate-limited to 20 invoices/minute to stay within Frappe's limits.
# # # # Sends as submitted (docstatus=1). Customer resolved dynamically — no hardcoding.
# # # # =============================================================================

# # # from __future__ import annotations

# # # import json
# # # import logging
# # # import time
# # # import threading
# # # import urllib.request
# # # import urllib.error
# # # import urllib.parse
# # # from datetime import datetime

# # # log = logging.getLogger("POSUpload")

# # # UPLOAD_INTERVAL   = 60    # seconds between full cycles
# # # REQUEST_TIMEOUT   = 30
# # # MAX_PER_MINUTE    = 20    # Frappe rate limit guard
# # # INTER_PUSH_DELAY  = 60 / MAX_PER_MINUTE   # 3 s between each push


# # # # =============================================================================
# # # # CREDENTIALS / DEFAULTS
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
# # #     return (os.environ.get("HAVANO_API_KEY", ""), os.environ.get("HAVANO_API_SECRET", ""))


# # # def _get_defaults() -> dict:
# # #     try:
# # #         from models.company_defaults import get_defaults
# # #         return get_defaults() or {}
# # #     except Exception:
# # #         return {}


# # # def _get_host() -> str:
# # #     try:
# # #         host = _get_defaults().get("server_api_host", "").strip().rstrip("/")
# # #         if host:
# # #             return host
# # #     except Exception:
# # #         pass
# # #     return "https://apk.havano.cloud"


# # # # =============================================================================
# # # # PAYMENT METHOD MAP + ACCOUNT RESOLVER
# # # # =============================================================================

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

# # # # Cache: mode_of_payment name → GL account string (fetched once per session)
# # # _MOP_ACCOUNT_CACHE: dict[str, str] = {}

# # # # Cache: "FROM::TO::DATE" → exchange rate float
# # # _RATE_CACHE: dict[str, float] = {}


# # # def _get_exchange_rate(from_currency: str, to_currency: str,
# # #                        transaction_date: str,
# # #                        api_key: str, api_secret: str, host: str) -> float:
# # #     """
# # #     Fetch exchange rate from Frappe's built-in currency exchange API.
# # #     Returns 1.0 if same currency or if fetch fails (Frappe will use its own rate).

# # #     Endpoint:
# # #         GET /api/method/erpnext.setup.utils.get_exchange_rate
# # #             ?from_currency=ZWL&to_currency=USD&transaction_date=2026-03-19
# # #     """
# # #     if not from_currency or not to_currency:
# # #         return 1.0
# # #     if from_currency.upper() == to_currency.upper():
# # #         return 1.0

# # #     cache_key = f"{from_currency.upper()}::{to_currency.upper()}::{transaction_date}"
# # #     if cache_key in _RATE_CACHE:
# # #         return _RATE_CACHE[cache_key]

# # #     try:
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
# # #             # Frappe returns {"message": 361.5} or {"result": 361.5}
# # #             rate = data.get("message") or data.get("result") or 1.0
# # #             rate = float(rate)
# # #             if rate and rate > 0:
# # #                 _RATE_CACHE[cache_key] = rate
# # #                 log.debug("Exchange rate %s→%s on %s: %.4f",
# # #                           from_currency, to_currency, transaction_date, rate)
# # #                 return rate
# # #     except Exception as e:
# # #         log.debug("Exchange rate fetch failed (%s→%s): %s",
# # #                   from_currency, to_currency, e)

# # #     # If fetch fails, return 0 — Frappe will use its own configured rate
# # #     log.warning("Could not fetch exchange rate %s→%s — Frappe will use its default.",
# # #                 from_currency, to_currency)
# # #     return 0.0


# # # def _get_mop_account(mop_name: str, company: str,
# # #                      api_key: str, api_secret: str, host: str,
# # #                      currency: str = "") -> str:
# # #     """
# # #     Returns the GL account for a Mode of Payment + Company + Currency combination.

# # #     Frappe's Mode of Payment has an `accounts` child table:
# # #         company | default_account
# # #     Each account belongs to a company and implicitly a currency.
# # #     For multi-currency setups, Frappe stores one row per company — the account
# # #     currency must match the invoice currency or Frappe rejects it.

# # #     Resolution order:
# # #         1. Session cache (keyed by mop::company::currency)
# # #         2. Frappe MOP API — matches by company, then filters by account currency
# # #         3. server_pos_account fallback in company_defaults
# # #     """
# # #     cache_key = f"{mop_name}::{company}::{currency}"
# # #     if cache_key in _MOP_ACCOUNT_CACHE:
# # #         return _MOP_ACCOUNT_CACHE[cache_key]

# # #     # Try fetching from Frappe's Mode of Payment doctype
# # #     try:
# # #         url = (
# # #             f"{host}/api/resource/Mode%20of%20Payment/{urllib.parse.quote(mop_name)}"
# # #             f"?fields=[\"accounts\"]"
# # #         )
# # #         req = urllib.request.Request(url)
# # #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# # #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# # #             data     = json.loads(r.read().decode())
# # #             accounts = (data.get("data") or {}).get("accounts", [])

# # #         # Filter by company first
# # #         company_accounts = [
# # #             row for row in accounts
# # #             if not company or row.get("company") == company
# # #         ]

# # #         # If currency specified, prefer an account whose currency matches.
# # #         # Frappe account names often end in "- USD" or "- ZWL" — use that as hint.
# # #         matched_acct = ""
# # #         if currency and company_accounts:
# # #             for row in company_accounts:
# # #                 acct = row.get("default_account", "")
# # #                 # Check if account name contains the currency code
# # #                 if acct and currency.upper() in acct.upper():
# # #                     matched_acct = acct
# # #                     break

# # #         # Fall back to first company account if no currency match
# # #         if not matched_acct and company_accounts:
# # #             matched_acct = company_accounts[0].get("default_account", "")

# # #         if matched_acct:
# # #             _MOP_ACCOUNT_CACHE[cache_key] = matched_acct
# # #             log.debug("MOP account resolved: %s [%s] → %s", mop_name, currency, matched_acct)
# # #             return matched_acct

# # #     except Exception as e:
# # #         log.debug("Could not fetch MOP account for '%s': %s", mop_name, e)

# # #     # Fallback: use server_pos_account from company_defaults if set
# # #     fallback = _get_defaults().get("server_pos_account", "").strip()
# # #     if fallback:
# # #         _MOP_ACCOUNT_CACHE[cache_key] = fallback
# # #         log.debug("MOP account fallback (company_defaults): %s", fallback)
# # #         return fallback

# # #     log.warning(
# # #         "No GL account found for MOP '%s' (currency=%s). "
# # #         "Configure accounts on the Mode of Payment in Frappe "
# # #         "or set server_pos_account in company_defaults.", mop_name, currency or "any"
# # #     )
# # #     return ""


# # # # =============================================================================
# # # # BUILD PAYLOAD
# # # # =============================================================================

# # # def _build_payload(sale: dict, items: list[dict], defaults: dict,
# # #                    api_key: str = "", api_secret: str = "") -> dict:
# # #     company           = defaults.get("server_company",           "")
# # #     warehouse         = defaults.get("server_warehouse",         "")
# # #     cost_center       = defaults.get("server_cost_center",       "")
# # #     taxes_and_charges = defaults.get("server_taxes_and_charges", "")
# # #     walk_in           = defaults.get("server_walk_in_customer",  "default").strip() or "default"
# # #     host              = _get_host()

# # #     customer = (sale.get("customer_name") or "").strip() or walk_in

# # #     posting_date = sale.get("invoice_date") or datetime.today().strftime("%Y-%m-%d")
# # #     raw_time     = sale.get("time")         or datetime.now().strftime("%H:%M:%S")
# # #     posting_time = str(raw_time) if len(str(raw_time)) == 8 else str(raw_time) + ":00"

# # #     mode_of_payment  = _METHOD_MAP.get(str(sale.get("method", "")).upper().strip(), "Cash")
# # #     currency         = (sale.get("currency") or "USD").strip().upper()
# # #     mop_account      = _get_mop_account(mode_of_payment, company, api_key, api_secret, host, currency)

# # #     # Fetch exchange rate from Frappe for non-USD currencies
# # #     company_currency = defaults.get("server_company_currency", "USD").strip().upper() or "USD"
# # #     conversion_rate  = _get_exchange_rate(
# # #         currency, company_currency, posting_date, api_key, api_secret, host
# # #     ) if currency != company_currency else 1.0

# # #     frappe_items = []
# # #     for it in items:
# # #         item_code = (it.get("part_no") or "").strip()
# # #         qty       = float(it.get("qty",   0))
# # #         rate      = float(it.get("price", 0))
# # #         if not item_code or qty <= 0:
# # #             continue
# # #         row = {"item_code": item_code, "qty": qty, "rate": rate}
# # #         if cost_center:
# # #             row["cost_center"] = cost_center
# # #         frappe_items.append(row)

# # #     if not frappe_items:
# # #         return {}

# # #     total = float(sale.get("total", 0))

# # #     payload = {
# # #         "customer":               customer,
# # #         "posting_date":           posting_date,
# # #         "posting_time":           posting_time,
# # #         "currency":               currency,
# # #         "is_pos":                 0,   # unpaid — payment_entry_service pushes PE separately
# # #         "update_stock":           0,
# # #         "docstatus":              1,   # submitted but unpaid
# # #         "custom_sales_reference": sale.get("invoice_no", ""),
# # #         "items":                  frappe_items,
# # #     }

# # #     # Only set conversion_rate when not company currency
# # #     # 0.0 means fetch failed — omit it and let Frappe use its own rate
# # #     if conversion_rate and conversion_rate != 1.0:
# # #         payload["conversion_rate"] = conversion_rate

# # #     if company:           payload["company"]           = company
# # #     if cost_center:       payload["cost_center"]       = cost_center
# # #     if warehouse:         payload["set_warehouse"]     = warehouse
# # #     if taxes_and_charges: payload["taxes_and_charges"] = taxes_and_charges

# # #     return payload


# # # # =============================================================================
# # # # PUSH ONE SALE
# # # # =============================================================================

# # # def _push_sale(sale: dict, api_key: str, api_secret: str,
# # #                defaults: dict, host: str) -> bool:
# # #     inv_no  = sale.get("invoice_no", str(sale["id"]))
# # #     walk_in = defaults.get("server_walk_in_customer", "default").strip() or "default"

# # #     try:
# # #         from models.sale import get_sale_items
# # #         items = get_sale_items(sale["id"])
# # #     except Exception as e:
# # #         log.error("Items fetch failed for %s: %s", inv_no, e)
# # #         return False

# # #     payload = _build_payload(sale, items, defaults, api_key, api_secret)
# # #     if not payload:
# # #         log.warning("Sale %s — no valid items, skipping (marked synced).", inv_no)
# # #         return True

# # #     url = f"{host}/api/resource/Sales%20Invoice"

# # #     # Two attempts: real customer first, walk-in fallback second
# # #     attempts = [payload]
# # #     if payload["customer"] != walk_in:
# # #         attempts.append({**payload, "customer": walk_in})

# # #     for i, p in enumerate(attempts):
# # #         req = urllib.request.Request(
# # #             url=url,
# # #             data=json.dumps(p).encode("utf-8"),
# # #             method="POST",
# # #             headers={
# # #                 "Content-Type":  "application/json",
# # #                 "Accept":        "application/json",
# # #                 "Authorization": f"token {api_key}:{api_secret}",
# # #             },
# # #         )
# # #         try:
# # #             with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
# # #                 name = (json.loads(resp.read()).get("data") or {}).get("name", "")
# # #                 suffix = f" [walk-in fallback: {walk_in}]" if i > 0 else ""
# # #                 log.info("✅ %s → Frappe %s  customer=%s%s",
# # #                          inv_no, name, p["customer"], suffix)
# # #                 return name if name else True

# # #         except urllib.error.HTTPError as e:
# # #             try:
# # #                 err = json.loads(e.read().decode())
# # #                 msg = (err.get("exception") or err.get("message") or
# # #                        str(err.get("_server_messages", "")) or f"HTTP {e.code}")
# # #             except Exception:
# # #                 msg = f"HTTP {e.code}"

# # #             if e.code == 409:
# # #                 log.info("Sale %s already exists on Frappe (409) — marking synced.", inv_no)
# # #                 return True

# # #             # Permanent Frappe-side data errors — not retryable.
# # #             # Mark synced to stop the retry loop; fix the data in Frappe manually.
# # #             _PERMANENT_ERRORS = (
# # #                 "negativestockerror",
# # #                 "not marked as sales item",
# # #                 "is not a sales item",
# # #                 "account is required",   # MOP has no GL account — fix in Frappe
# # #             )
# # #             if e.code == 417 and any(p in msg.lower() for p in _PERMANENT_ERRORS):
# # #                 log.warning(
# # #                     "⚠️  Sale %s — permanent Frappe data error (marked synced to stop loop).\n  %s",
# # #                     inv_no, msg,
# # #                 )
# # #                 return True   # mark_synced called by caller

# # #             # Customer-not-found error → retry with walk-in on next attempt
# # #             if i == 0 and e.code in (417, 500) and any(
# # #                 kw in msg.lower() for kw in ("customer", "payment_terms", "nonetype")
# # #             ):
# # #                 log.warning("Sale %s — customer '%s' rejected, retrying with walk-in…",
# # #                             inv_no, p["customer"])
# # #                 continue

# # #             log.error("❌ Sale %s  HTTP %s: %s", inv_no, e.code, msg)
# # #             return False

# # #         except urllib.error.URLError as e:
# # #             log.warning("Network error pushing %s: %s", inv_no, e.reason)
# # #             return False

# # #         except Exception as e:
# # #             log.error("Unexpected error pushing %s: %s", inv_no, e)
# # #             return False

# # #     return False


# # # # =============================================================================
# # # # PUBLIC — push all unsynced (rate-limited to MAX_PER_MINUTE)
# # # # =============================================================================

# # # def push_unsynced_sales() -> dict:
# # #     result = {"pushed": 0, "failed": 0, "total": 0}

# # #     api_key, api_secret = _get_credentials()
# # #     if not api_key or not api_secret:
# # #         log.warning("No API credentials — skipping upload cycle.")
# # #         return result

# # #     host     = _get_host()
# # #     defaults = _get_defaults()

# # #     try:
# # #         from models.sale import get_unsynced_sales, mark_synced, mark_synced_with_ref
# # #         sales = get_unsynced_sales()
# # #     except Exception as e:
# # #         log.error("Could not read unsynced sales: %s", e)
# # #         return result

# # #     result["total"] = len(sales)
# # #     if not sales:
# # #         log.debug("No unsynced sales.")
# # #         return result

# # #     log.info("Pushing %d sale(s) to Frappe (max %d/min)…", len(sales), MAX_PER_MINUTE)

# # #     for idx, sale in enumerate(sales):
# # #         if idx > 0 and idx % MAX_PER_MINUTE == 0:
# # #             log.info("Rate limit pause — waiting 60s before next batch…")
# # #             time.sleep(60)

# # #         result_val = _push_sale(sale, api_key, api_secret, defaults, host)
# # #         if result_val:
# # #             try:
# # #                 # result_val is the Frappe doc name string on success, or True for
# # #                 # permanent-error cases (409, NegativeStockError, not-sales-item)
# # #                 frappe_ref = result_val if isinstance(result_val, str) else ""
# # #                 mark_synced_with_ref(sale["id"], frappe_ref)
# # #                 result["pushed"] += 1
# # #             except Exception as e:
# # #                 log.error("mark_synced failed for sale %s: %s", sale["id"], e)
# # #                 result["failed"] += 1
# # #         else:
# # #             result["failed"] += 1

# # #         if idx < len(sales) - 1:
# # #             time.sleep(INTER_PUSH_DELAY)   # 3 s between each push

# # #     log.info("Upload done — ✅ %d pushed  ❌ %d failed  (of %d)",
# # #              result["pushed"], result["failed"], result["total"])
# # #     return result


# # # # =============================================================================
# # # # QTHREAD WORKER
# # # # =============================================================================

# # # try:
# # #     from PySide6.QtCore import QObject  # type: ignore

# # #     class UploadWorker(QObject):
# # #         def run(self) -> None:
# # #             log.info("POS upload worker started (interval=%ds, max=%d/min).",
# # #                      UPLOAD_INTERVAL, MAX_PER_MINUTE)
# # #             while True:
# # #                 try:
# # #                     push_unsynced_sales()
# # #                 except Exception as exc:
# # #                     log.error("Unhandled error in upload worker: %s", exc)
# # #                 time.sleep(UPLOAD_INTERVAL)

# # # except ImportError:
# # #     class UploadWorker:              # type: ignore[no-redef]
# # #         def run(self) -> None:
# # #             pass


# # # def start_upload_thread() -> object:
# # #     """Start the upload background thread — call once from MainWindow.__init__."""
# # #     try:
# # #         from PySide6.QtCore import QThread  # type: ignore
# # #         thread = QThread()
# # #         worker = UploadWorker()
# # #         worker.moveToThread(thread)
# # #         thread.started.connect(worker.run)
# # #         thread._worker = worker      # prevent GC
# # #         thread.start()
# # #         log.info("POS upload QThread started.")
# # #         return thread
# # #     except ImportError:
# # #         def _loop():
# # #             while True:
# # #                 try:
# # #                     push_unsynced_sales()
# # #                 except Exception as exc:
# # #                     log.error("Unhandled error: %s", exc)
# # #                 time.sleep(UPLOAD_INTERVAL)
# # #         t = threading.Thread(target=_loop, daemon=True, name="POSUploadThread")
# # #         t.start()
# # #         return t

# # # =============================================================================
# # # services/pos_upload_service.py  —  Push local POS sales → Frappe
# # # Rate-limited to 20 invoices/minute to stay within Frappe's limits.
# # # Sends as submitted (docstatus=1). Customer resolved dynamically — no hardcoding.
# # # =============================================================================

# # from __future__ import annotations

# # import json
# # import logging
# # import time
# # import threading
# # import urllib.request
# # import urllib.error
# # import urllib.parse
# # from datetime import datetime

# # log = logging.getLogger("POSUpload")

# # UPLOAD_INTERVAL   = 60    # seconds between full cycles
# # REQUEST_TIMEOUT   = 30
# # MAX_PER_MINUTE    = 20    # Frappe rate limit guard
# # INTER_PUSH_DELAY  = 60 / MAX_PER_MINUTE   # 3 s between each push


# # # =============================================================================
# # # CREDENTIALS / DEFAULTS
# # # =============================================================================

# # def _get_credentials() -> tuple[str, str]:
# #     try:
# #         from services.credentials import get_credentials
# #         return get_credentials()
# #     except Exception:
# #         pass
# #     return "", ""
# # def _get_defaults() -> dict:
# #     try:
# #         from models.company_defaults import get_defaults
# #         return get_defaults() or {}
# #     except Exception:
# #         return {}


# # def _get_host() -> str:
# #     try:
# #         host = _get_defaults().get("server_api_host", "").strip().rstrip("/")
# #         if host:
# #             return host
# #     except Exception:
# #         pass
# #     return "https://apk.havano.cloud"


# # # =============================================================================
# # # PAYMENT METHOD MAP + ACCOUNT RESOLVER
# # # =============================================================================

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

# # # Cache: mode_of_payment name → GL account string (fetched once per session)
# # _MOP_ACCOUNT_CACHE: dict[str, str] = {}

# # # Cache: "FROM::TO::DATE" → exchange rate float
# # _RATE_CACHE: dict[str, float] = {}


# # def _get_exchange_rate(from_currency: str, to_currency: str,
# #                        transaction_date: str,
# #                        api_key: str, api_secret: str, host: str) -> float:
# #     """
# #     Fetch exchange rate from Frappe's built-in currency exchange API.
# #     Returns 1.0 if same currency or if fetch fails (Frappe will use its own rate).

# #     Endpoint:
# #         GET /api/method/erpnext.setup.utils.get_exchange_rate
# #             ?from_currency=ZWL&to_currency=USD&transaction_date=2026-03-19
# #     """
# #     if not from_currency or not to_currency:
# #         return 1.0
# #     if from_currency.upper() == to_currency.upper():
# #         return 1.0

# #     cache_key = f"{from_currency.upper()}::{to_currency.upper()}::{transaction_date}"
# #     if cache_key in _RATE_CACHE:
# #         return _RATE_CACHE[cache_key]

# #     try:
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
# #             # Frappe returns {"message": 361.5} or {"result": 361.5}
# #             rate = data.get("message") or data.get("result") or 1.0
# #             rate = float(rate)
# #             if rate and rate > 0:
# #                 _RATE_CACHE[cache_key] = rate
# #                 log.debug("Exchange rate %s→%s on %s: %.4f",
# #                           from_currency, to_currency, transaction_date, rate)
# #                 return rate
# #     except Exception as e:
# #         log.debug("Exchange rate fetch failed (%s→%s): %s",
# #                   from_currency, to_currency, e)

# #     # If fetch fails, return 0 — Frappe will use its own configured rate
# #     log.warning("Could not fetch exchange rate %s→%s — Frappe will use its default.",
# #                 from_currency, to_currency)
# #     return 0.0


# # def _get_mop_account(mop_name: str, company: str,
# #                      api_key: str, api_secret: str, host: str,
# #                      currency: str = "") -> str:
# #     """
# #     Returns the GL account for a Mode of Payment + Company + Currency combination.

# #     Frappe's Mode of Payment has an `accounts` child table:
# #         company | default_account
# #     Each account belongs to a company and implicitly a currency.
# #     For multi-currency setups, Frappe stores one row per company — the account
# #     currency must match the invoice currency or Frappe rejects it.

# #     Resolution order:
# #         1. Session cache (keyed by mop::company::currency)
# #         2. Frappe MOP API — matches by company, then filters by account currency
# #         3. server_pos_account fallback in company_defaults
# #     """
# #     cache_key = f"{mop_name}::{company}::{currency}"
# #     if cache_key in _MOP_ACCOUNT_CACHE:
# #         return _MOP_ACCOUNT_CACHE[cache_key]

# #     # Try fetching from Frappe's Mode of Payment doctype
# #     try:
# #         url = (
# #             f"{host}/api/resource/Mode%20of%20Payment/{urllib.parse.quote(mop_name)}"
# #             f"?fields=[\"accounts\"]"
# #         )
# #         req = urllib.request.Request(url)
# #         req.add_header("Authorization", f"token {api_key}:{api_secret}")
# #         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
# #             data     = json.loads(r.read().decode())
# #             accounts = (data.get("data") or {}).get("accounts", [])

# #         # Filter by company first
# #         company_accounts = [
# #             row for row in accounts
# #             if not company or row.get("company") == company
# #         ]

# #         # If currency specified, prefer an account whose currency matches.
# #         # Frappe account names often end in "- USD" or "- ZWL" — use that as hint.
# #         matched_acct = ""
# #         if currency and company_accounts:
# #             for row in company_accounts:
# #                 acct = row.get("default_account", "")
# #                 # Check if account name contains the currency code
# #                 if acct and currency.upper() in acct.upper():
# #                     matched_acct = acct
# #                     break

# #         # Fall back to first company account if no currency match
# #         if not matched_acct and company_accounts:
# #             matched_acct = company_accounts[0].get("default_account", "")

# #         if matched_acct:
# #             _MOP_ACCOUNT_CACHE[cache_key] = matched_acct
# #             log.debug("MOP account resolved: %s [%s] → %s", mop_name, currency, matched_acct)
# #             return matched_acct

# #     except Exception as e:
# #         log.debug("Could not fetch MOP account for '%s': %s", mop_name, e)

# #     # Fallback: use server_pos_account from company_defaults if set
# #     fallback = _get_defaults().get("server_pos_account", "").strip()
# #     if fallback:
# #         _MOP_ACCOUNT_CACHE[cache_key] = fallback
# #         log.debug("MOP account fallback (company_defaults): %s", fallback)
# #         return fallback

# #     log.warning(
# #         "No GL account found for MOP '%s' (currency=%s). "
# #         "Configure accounts on the Mode of Payment in Frappe "
# #         "or set server_pos_account in company_defaults.", mop_name, currency or "any"
# #     )
# #     return ""


# # # =============================================================================
# # # BUILD PAYLOAD
# # # =============================================================================

# # def _build_payload(sale: dict, items: list[dict], defaults: dict,
# #                    api_key: str = "", api_secret: str = "") -> dict:
# #     company           = defaults.get("server_company",           "")
# #     warehouse         = defaults.get("server_warehouse",         "")
# #     cost_center       = defaults.get("server_cost_center",       "")
# #     taxes_and_charges = defaults.get("server_taxes_and_charges", "")
# #     walk_in           = defaults.get("server_walk_in_customer",  "default").strip() or "default"
# #     host              = _get_host()

# #     customer = (sale.get("customer_name") or "").strip() or walk_in

# #     posting_date = sale.get("invoice_date") or datetime.today().strftime("%Y-%m-%d")
# #     raw_time     = sale.get("time")         or datetime.now().strftime("%H:%M:%S")
# #     posting_time = str(raw_time) if len(str(raw_time)) == 8 else str(raw_time) + ":00"

# #     mode_of_payment  = _METHOD_MAP.get(str(sale.get("method", "")).upper().strip(), "Cash")
# #     currency         = (sale.get("currency") or "USD").strip().upper()
# #     mop_account      = _get_mop_account(mode_of_payment, company, api_key, api_secret, host, currency)

# #     # Fetch exchange rate from Frappe for non-USD currencies
# #     company_currency = defaults.get("server_company_currency", "USD").strip().upper() or "USD"
# #     conversion_rate  = _get_exchange_rate(
# #         currency, company_currency, posting_date, api_key, api_secret, host
# #     ) if currency != company_currency else 1.0

# #     frappe_items = []
# #     for it in items:
# #         item_code = (it.get("part_no") or "").strip()
# #         qty       = float(it.get("qty",   0))
# #         rate      = float(it.get("price", 0))
# #         if not item_code or qty <= 0:
# #             continue
# #         row = {"item_code": item_code, "qty": qty, "rate": rate}
# #         if cost_center:
# #             row["cost_center"] = cost_center
# #         frappe_items.append(row)

# #     if not frappe_items:
# #         return {}

# #     total = float(sale.get("total", 0))

# #     payload = {
# #         "customer":               customer,
# #         "posting_date":           posting_date,
# #         "posting_time":           posting_time,
# #         "currency":               currency,
# #         "is_pos":                 0,   # unpaid — payment_entry_service pushes PE separately
# #         "update_stock":           0,
# #         "docstatus":              1,   # submitted but unpaid
# #         "custom_sales_reference": sale.get("invoice_no", ""),
# #         "items":                  frappe_items,
# #     }

# #     # Only set conversion_rate when not company currency
# #     # 0.0 means fetch failed — omit it and let Frappe use its own rate
# #     if conversion_rate and conversion_rate != 1.0:
# #         payload["conversion_rate"] = conversion_rate

# #     if company:           payload["company"]           = company
# #     if cost_center:       payload["cost_center"]       = cost_center
# #     if warehouse:         payload["set_warehouse"]     = warehouse
# #     if taxes_and_charges: payload["taxes_and_charges"] = taxes_and_charges

# #     return payload


# # # =============================================================================
# # # PUSH ONE SALE
# # # =============================================================================

# # def _push_sale(sale: dict, api_key: str, api_secret: str,
# #                defaults: dict, host: str) -> bool:
# #     inv_no  = sale.get("invoice_no", str(sale["id"]))
# #     walk_in = defaults.get("server_walk_in_customer", "default").strip() or "default"

# #     try:
# #         from models.sale import get_sale_items
# #         items = get_sale_items(sale["id"])
# #     except Exception as e:
# #         log.error("Items fetch failed for %s: %s", inv_no, e)
# #         return False

# #     payload = _build_payload(sale, items, defaults, api_key, api_secret)
# #     if not payload:
# #         log.warning("Sale %s — no valid items, skipping (marked synced).", inv_no)
# #         return True

# #     url = f"{host}/api/resource/Sales%20Invoice"

# #     # Two attempts: real customer first, walk-in fallback second
# #     attempts = [payload]
# #     if payload["customer"] != walk_in:
# #         attempts.append({**payload, "customer": walk_in})

# #     for i, p in enumerate(attempts):
# #         req = urllib.request.Request(
# #             url=url,
# #             data=json.dumps(p).encode("utf-8"),
# #             method="POST",
# #             headers={
# #                 "Content-Type":  "application/json",
# #                 "Accept":        "application/json",
# #                 "Authorization": f"token {api_key}:{api_secret}",
# #             },
# #         )
# #         try:
# #             with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
# #                 name = (json.loads(resp.read()).get("data") or {}).get("name", "")
# #                 suffix = f" [walk-in fallback: {walk_in}]" if i > 0 else ""
# #                 log.info("✅ %s → Frappe %s  customer=%s%s",
# #                          inv_no, name, p["customer"], suffix)
# #                 return name if name else True

# #         except urllib.error.HTTPError as e:
# #             try:
# #                 err = json.loads(e.read().decode())
# #                 msg = (err.get("exception") or err.get("message") or
# #                        str(err.get("_server_messages", "")) or f"HTTP {e.code}")
# #             except Exception:
# #                 msg = f"HTTP {e.code}"

# #             if e.code == 409:
# #                 log.info("Sale %s already exists on Frappe (409) — marking synced.", inv_no)
# #                 return True

# #             # Permanent Frappe-side data errors — not retryable.
# #             # Mark synced to stop the retry loop; fix the data in Frappe manually.
# #             _PERMANENT_ERRORS = (
# #                 "negativestockerror",
# #                 "not marked as sales item",
# #                 "is not a sales item",
# #                 "account is required",   # MOP has no GL account — fix in Frappe
# #             )
# #             if e.code == 417 and any(p in msg.lower() for p in _PERMANENT_ERRORS):
# #                 log.warning(
# #                     "⚠️  Sale %s — permanent Frappe data error (marked synced to stop loop).\n  %s",
# #                     inv_no, msg,
# #                 )
# #                 return True   # mark_synced called by caller

# #             # Customer-not-found error → retry with walk-in on next attempt
# #             if i == 0 and e.code in (417, 500) and any(
# #                 kw in msg.lower() for kw in ("customer", "payment_terms", "nonetype")
# #             ):
# #                 log.warning("Sale %s — customer '%s' rejected, retrying with walk-in…",
# #                             inv_no, p["customer"])
# #                 continue

# #             log.error("❌ Sale %s  HTTP %s: %s", inv_no, e.code, msg)
# #             return False

# #         except urllib.error.URLError as e:
# #             log.warning("Network error pushing %s: %s", inv_no, e.reason)
# #             return False

# #         except Exception as e:
# #             log.error("Unexpected error pushing %s: %s", inv_no, e)
# #             return False

# #     return False


# # # =============================================================================
# # # PUBLIC — push all unsynced (rate-limited to MAX_PER_MINUTE)
# # # =============================================================================

# # def push_unsynced_sales() -> dict:
# #     result = {"pushed": 0, "failed": 0, "total": 0}

# #     api_key, api_secret = _get_credentials()
# #     if not api_key or not api_secret:
# #         log.warning("No API credentials — skipping upload cycle.")
# #         return result

# #     host     = _get_host()
# #     defaults = _get_defaults()

# #     try:
# #         from models.sale import get_unsynced_sales, mark_synced, mark_synced_with_ref
# #         sales = get_unsynced_sales()
# #     except Exception as e:
# #         log.error("Could not read unsynced sales: %s", e)
# #         return result

# #     result["total"] = len(sales)
# #     if not sales:
# #         log.debug("No unsynced sales.")
# #         return result

# #     log.info("Pushing %d sale(s) to Frappe (max %d/min)…", len(sales), MAX_PER_MINUTE)

# #     for idx, sale in enumerate(sales):
# #         if idx > 0 and idx % MAX_PER_MINUTE == 0:
# #             log.info("Rate limit pause — waiting 60s before next batch…")
# #             time.sleep(60)

# #         result_val = _push_sale(sale, api_key, api_secret, defaults, host)
# #         if result_val:
# #             try:
# #                 # result_val is the Frappe doc name string on success, or True for
# #                 # permanent-error cases (409, NegativeStockError, not-sales-item)
# #                 frappe_ref = result_val if isinstance(result_val, str) else ""
# #                 mark_synced_with_ref(sale["id"], frappe_ref)
# #                 result["pushed"] += 1
# #             except Exception as e:
# #                 log.error("mark_synced failed for sale %s: %s", sale["id"], e)
# #                 result["failed"] += 1
# #         else:
# #             result["failed"] += 1

# #         if idx < len(sales) - 1:
# #             time.sleep(INTER_PUSH_DELAY)   # 3 s between each push

# #     log.info("Upload done — ✅ %d pushed  ❌ %d failed  (of %d)",
# #              result["pushed"], result["failed"], result["total"])
# #     return result


# # # =============================================================================
# # # QTHREAD WORKER
# # # =============================================================================

# # try:
# #     from PySide6.QtCore import QObject  # type: ignore

# #     class UploadWorker(QObject):
# #         def run(self) -> None:
# #             log.info("POS upload worker started (interval=%ds, max=%d/min).",
# #                      UPLOAD_INTERVAL, MAX_PER_MINUTE)
# #             while True:
# #                 try:
# #                     push_unsynced_sales()
# #                 except Exception as exc:
# #                     log.error("Unhandled error in upload worker: %s", exc)
# #                 time.sleep(UPLOAD_INTERVAL)

# # except ImportError:
# #     class UploadWorker:              # type: ignore[no-redef]
# #         def run(self) -> None:
# #             pass


# # def start_upload_thread() -> object:
# #     """Start the upload background thread — call once from MainWindow.__init__."""
# #     try:
# #         from PySide6.QtCore import QThread  # type: ignore
# #         thread = QThread()
# #         worker = UploadWorker()
# #         worker.moveToThread(thread)
# #         thread.started.connect(worker.run)
# #         thread._worker = worker      # prevent GC
# #         thread.start()
# #         log.info("POS upload QThread started.")
# #         return thread
# #     except ImportError:
# #         def _loop():
# #             while True:
# #                 try:
# #                     push_unsynced_sales()
# #                 except Exception as exc:
# #                     log.error("Unhandled error: %s", exc)
# #                 time.sleep(UPLOAD_INTERVAL)
# #         t = threading.Thread(target=_loop, daemon=True, name="POSUploadThread")
# #         t.start()
# #         return t

# # =============================================================================
# # services/pos_upload_service.py  —  Push local POS sales → Frappe
# # Rate-limited to 20 invoices/minute to stay within Frappe's limits.
# # Sends as submitted (docstatus=1). Customer resolved dynamically — no hardcoding.
# # =============================================================================

# from __future__ import annotations

# import json
# import logging
# import time
# import threading
# import urllib.request
# import urllib.error
# import urllib.parse
# from datetime import datetime

# log = logging.getLogger("POSUpload")

# UPLOAD_INTERVAL   = 60    # seconds between full cycles
# REQUEST_TIMEOUT   = 30
# MAX_PER_MINUTE    = 20    # Frappe rate limit guard
# INTER_PUSH_DELAY  = 60 / MAX_PER_MINUTE   # 3 s between each push


# # =============================================================================
# # CREDENTIALS / DEFAULTS
# # =============================================================================

# def _get_credentials() -> tuple[str, str]:
#     try:
#         from services.credentials import get_credentials
#         return get_credentials()
#     except Exception:
#         pass
#     return "", ""

# def _get_defaults() -> dict:
#     try:
#         from models.company_defaults import get_defaults
#         return get_defaults() or {}
#     except Exception:
#         return {}


# def _get_host() -> str:
#     try:
#         host = _get_defaults().get("server_api_host", "").strip().rstrip("/")
#         if host:
#             return host
#     except Exception:
#         pass
#     return "https://apk.havano.cloud"


# # =============================================================================
# # PAYMENT METHOD MAP + ACCOUNT RESOLVER
# # =============================================================================

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

# # Cache: mode_of_payment name → GL account string (fetched once per session)
# _MOP_ACCOUNT_CACHE: dict[str, str] = {}

# # Cache: "FROM::TO::DATE" → exchange rate float
# _RATE_CACHE: dict[str, float] = {}


# def _get_exchange_rate(from_currency: str, to_currency: str,
#                        transaction_date: str,
#                        api_key: str, api_secret: str, host: str) -> float:
#     """
#     Fetch exchange rate from Frappe's built-in currency exchange API.
#     Returns 1.0 if same currency or if fetch fails (Frappe will use its own rate).

#     Endpoint:
#         GET /api/method/erpnext.setup.utils.get_exchange_rate
#             ?from_currency=ZWL&to_currency=USD&transaction_date=2026-03-19
#     """
#     if not from_currency or not to_currency:
#         return 1.0
#     if from_currency.upper() == to_currency.upper():
#         return 1.0

#     cache_key = f"{from_currency.upper()}::{to_currency.upper()}::{transaction_date}"
#     if cache_key in _RATE_CACHE:
#         return _RATE_CACHE[cache_key]

#     try:
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
#             # Frappe returns {"message": 361.5} or {"result": 361.5}
#             rate = data.get("message") or data.get("result") or 1.0
#             rate = float(rate)
#             if rate and rate > 0:
#                 _RATE_CACHE[cache_key] = rate
#                 log.debug("Exchange rate %s→%s on %s: %.4f",
#                           from_currency, to_currency, transaction_date, rate)
#                 return rate
#     except Exception as e:
#         log.debug("Exchange rate fetch failed (%s→%s): %s",
#                   from_currency, to_currency, e)

#     # If fetch fails, return 0 — Frappe will use its own configured rate
#     log.warning("Could not fetch exchange rate %s→%s — Frappe will use its default.",
#                 from_currency, to_currency)
#     return 0.0


# def _get_mop_account(mop_name: str, company: str,
#                      api_key: str, api_secret: str, host: str,
#                      currency: str = "") -> str:
#     """
#     Returns the GL account for a Mode of Payment + Company + Currency combination.

#     Frappe's Mode of Payment has an `accounts` child table:
#         company | default_account
#     Each account belongs to a company and implicitly a currency.
#     For multi-currency setups, Frappe stores one row per company — the account
#     currency must match the invoice currency or Frappe rejects it.

#     Resolution order:
#         1. Session cache (keyed by mop::company::currency)
#         2. Frappe MOP API — matches by company, then filters by account currency
#         3. server_pos_account fallback in company_defaults
#     """
#     cache_key = f"{mop_name}::{company}::{currency}"
#     if cache_key in _MOP_ACCOUNT_CACHE:
#         return _MOP_ACCOUNT_CACHE[cache_key]

#     # Try fetching from Frappe's Mode of Payment doctype
#     try:
#         url = (
#             f"{host}/api/resource/Mode%20of%20Payment/{urllib.parse.quote(mop_name)}"
#             f"?fields=[\"accounts\"]"
#         )
#         req = urllib.request.Request(url)
#         req.add_header("Authorization", f"token {api_key}:{api_secret}")
#         with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
#             data     = json.loads(r.read().decode())
#             accounts = (data.get("data") or {}).get("accounts", [])

#         # Filter by company first
#         company_accounts = [
#             row for row in accounts
#             if not company or row.get("company") == company
#         ]

#         # If currency specified, prefer an account whose currency matches.
#         # Frappe account names often end in "- USD" or "- ZWL" — use that as hint.
#         matched_acct = ""
#         if currency and company_accounts:
#             for row in company_accounts:
#                 acct = row.get("default_account", "")
#                 # Check if account name contains the currency code
#                 if acct and currency.upper() in acct.upper():
#                     matched_acct = acct
#                     break

#         # Fall back to first company account if no currency match
#         if not matched_acct and company_accounts:
#             matched_acct = company_accounts[0].get("default_account", "")

#         if matched_acct:
#             _MOP_ACCOUNT_CACHE[cache_key] = matched_acct
#             log.debug("MOP account resolved: %s [%s] → %s", mop_name, currency, matched_acct)
#             return matched_acct

#     except Exception as e:
#         log.debug("Could not fetch MOP account for '%s': %s", mop_name, e)

#     # Fallback: use server_pos_account from company_defaults if set
#     fallback = _get_defaults().get("server_pos_account", "").strip()
#     if fallback:
#         _MOP_ACCOUNT_CACHE[cache_key] = fallback
#         log.debug("MOP account fallback (company_defaults): %s", fallback)
#         return fallback

#     log.warning(
#         "No GL account found for MOP '%s' (currency=%s). "
#         "Configure accounts on the Mode of Payment in Frappe "
#         "or set server_pos_account in company_defaults.", mop_name, currency or "any"
#     )
#     return ""


# # =============================================================================
# # BUILD PAYLOAD
# # =============================================================================

# def _build_payload(sale: dict, items: list[dict], defaults: dict,
#                    api_key: str = "", api_secret: str = "") -> dict:
#     company           = defaults.get("server_company",           "")
#     warehouse         = defaults.get("server_warehouse",         "")
#     cost_center       = defaults.get("server_cost_center",       "")
#     taxes_and_charges = defaults.get("server_taxes_and_charges", "")
#     walk_in           = defaults.get("server_walk_in_customer",  "default").strip() or "default"
#     host              = _get_host()

#     customer = (sale.get("customer_name") or "").strip() or walk_in

#     posting_date = sale.get("invoice_date") or datetime.today().strftime("%Y-%m-%d")
#     raw_time     = sale.get("time")         or datetime.now().strftime("%H:%M:%S")
#     posting_time = str(raw_time) if len(str(raw_time)) == 8 else str(raw_time) + ":00"

#     mode_of_payment  = _METHOD_MAP.get(str(sale.get("method", "")).upper().strip(), "Cash")
#     currency         = (sale.get("currency") or "USD").strip().upper()
#     mop_account      = _get_mop_account(mode_of_payment, company, api_key, api_secret, host, currency)

#     # Fetch exchange rate from Frappe for non-USD currencies
#     company_currency = defaults.get("server_company_currency", "USD").strip().upper() or "USD"
#     conversion_rate  = _get_exchange_rate(
#         currency, company_currency, posting_date, api_key, api_secret, host
#     ) if currency != company_currency else 1.0

#     frappe_items = []
#     for it in items:
#         item_code = (it.get("part_no") or "").strip()
#         qty       = float(it.get("qty",   0))
#         rate      = float(it.get("price", 0))
#         if not item_code or qty <= 0:
#             continue
#         row = {"item_code": item_code, "qty": qty, "rate": rate}
#         if cost_center:
#             row["cost_center"] = cost_center
#         frappe_items.append(row)

#     if not frappe_items:
#         return {}

#     total = float(sale.get("total", 0))

#     payload = {
#         "customer":               customer,
#         "posting_date":           posting_date,
#         "posting_time":           posting_time,
#         "currency":               currency,
#         "is_pos":                 0,   # unpaid — payment_entry_service pushes PE separately
#         "update_stock":           0,
#         "docstatus":              1,   # submitted but unpaid
#         "custom_sales_reference": sale.get("invoice_no", ""),
#         "items":                  frappe_items,
#     }

#     # Only set conversion_rate when not company currency
#     # 0.0 means fetch failed — omit it and let Frappe use its own rate
#     if conversion_rate and conversion_rate != 1.0:
#         payload["conversion_rate"] = conversion_rate

#     if company:           payload["company"]           = company
#     if cost_center:       payload["cost_center"]       = cost_center
#     if warehouse:         payload["set_warehouse"]     = warehouse
#     if taxes_and_charges: payload["taxes_and_charges"] = taxes_and_charges

#     return payload


# # =============================================================================
# # PUSH ONE SALE
# # =============================================================================

# def _push_sale(sale: dict, api_key: str, api_secret: str,
#                defaults: dict, host: str) -> bool:
#     inv_no  = sale.get("invoice_no", str(sale["id"]))
#     walk_in = defaults.get("server_walk_in_customer", "default").strip() or "default"

#     try:
#         from models.sale import get_sale_items
#         items = get_sale_items(sale["id"])
#     except Exception as e:
#         log.error("Items fetch failed for %s: %s", inv_no, e)
#         return False

#     payload = _build_payload(sale, items, defaults, api_key, api_secret)
#     if not payload:
#         log.warning("Sale %s — no valid items, skipping (marked synced).", inv_no)
#         return True

#     url = f"{host}/api/resource/Sales%20Invoice"

#     # Two attempts: real customer first, walk-in fallback second
#     attempts = [payload]
#     if payload["customer"] != walk_in:
#         attempts.append({**payload, "customer": walk_in})

#     for i, p in enumerate(attempts):
#         req = urllib.request.Request(
#             url=url,
#             data=json.dumps(p).encode("utf-8"),
#             method="POST",
#             headers={
#                 "Content-Type":  "application/json",
#                 "Accept":        "application/json",
#                 "Authorization": f"token {api_key}:{api_secret}",
#             },
#         )
#         try:
#             with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
#                 name = (json.loads(resp.read()).get("data") or {}).get("name", "")
#                 suffix = f" [walk-in fallback: {walk_in}]" if i > 0 else ""
#                 log.info("✅ %s → Frappe %s  customer=%s%s",
#                          inv_no, name, p["customer"], suffix)
#                 return name if name else True

#         except urllib.error.HTTPError as e:
#             try:
#                 err = json.loads(e.read().decode())
#                 msg = (err.get("exception") or err.get("message") or
#                        str(err.get("_server_messages", "")) or f"HTTP {e.code}")
#             except Exception:
#                 msg = f"HTTP {e.code}"

#             if e.code == 409:
#                 log.info("Sale %s already exists on Frappe (409) — marking synced.", inv_no)
#                 return True

#             # Permanent Frappe-side data errors — not retryable.
#             # Mark synced to stop the retry loop; fix the data in Frappe manually.
#             _PERMANENT_ERRORS = (
#                 "negativestockerror",
#                 "not marked as sales item",
#                 "is not a sales item",
#                 "account is required",   # MOP has no GL account — fix in Frappe
#             )
#             if e.code == 417 and any(p in msg.lower() for p in _PERMANENT_ERRORS):
#                 log.warning(
#                     "⚠️  Sale %s — permanent Frappe data error (marked synced to stop loop).\n  %s",
#                     inv_no, msg,
#                 )
#                 return True   # mark_synced called by caller

#             # Customer-not-found error → retry with walk-in on next attempt
#             if i == 0 and e.code in (417, 500) and any(
#                 kw in msg.lower() for kw in ("customer", "payment_terms", "nonetype")
#             ):
#                 log.warning("Sale %s — customer '%s' rejected, retrying with walk-in…",
#                             inv_no, p["customer"])
#                 continue

#             log.error("❌ Sale %s  HTTP %s: %s", inv_no, e.code, msg)
#             return False

#         except urllib.error.URLError as e:
#             log.warning("Network error pushing %s: %s", inv_no, e.reason)
#             return False

#         except Exception as e:
#             log.error("Unexpected error pushing %s: %s", inv_no, e)
#             return False

#     return False


# # =============================================================================
# # PUBLIC — push all unsynced (rate-limited to MAX_PER_MINUTE)
# # =============================================================================

# def push_unsynced_sales() -> dict:
#     result = {"pushed": 0, "failed": 0, "total": 0}

#     api_key, api_secret = _get_credentials()
#     if not api_key or not api_secret:
#         log.warning("No API credentials — skipping upload cycle.")
#         return result

#     host     = _get_host()
#     defaults = _get_defaults()

#     try:
#         from models.sale import get_unsynced_sales, mark_synced, mark_synced_with_ref
#         sales = get_unsynced_sales()
#     except Exception as e:
#         log.error("Could not read unsynced sales: %s", e)
#         return result

#     result["total"] = len(sales)
#     if not sales:
#         log.debug("No unsynced sales.")
#         return result

#     log.info("Pushing %d sale(s) to Frappe (max %d/min)…", len(sales), MAX_PER_MINUTE)

#     for idx, sale in enumerate(sales):
#         if idx > 0 and idx % MAX_PER_MINUTE == 0:
#             log.info("Rate limit pause — waiting 60s before next batch…")
#             time.sleep(60)

#         result_val = _push_sale(sale, api_key, api_secret, defaults, host)
#         if result_val:
#             try:
#                 # result_val is the Frappe doc name string on success, or True for
#                 # permanent-error cases (409, NegativeStockError, not-sales-item)
#                 frappe_ref = result_val if isinstance(result_val, str) else ""
#                 mark_synced_with_ref(sale["id"], frappe_ref)
#                 result["pushed"] += 1
#             except Exception as e:
#                 log.error("mark_synced failed for sale %s: %s", sale["id"], e)
#                 result["failed"] += 1
#         else:
#             result["failed"] += 1

#         if idx < len(sales) - 1:
#             time.sleep(INTER_PUSH_DELAY)   # 3 s between each push

#     log.info("Upload done — ✅ %d pushed  ❌ %d failed  (of %d)",
#              result["pushed"], result["failed"], result["total"])
#     return result


# # =============================================================================
# # QTHREAD WORKER
# # =============================================================================

# try:
#     from PySide6.QtCore import QObject  # type: ignore

#     class UploadWorker(QObject):
#         def run(self) -> None:
#             log.info("POS upload worker started (interval=%ds, max=%d/min).",
#                      UPLOAD_INTERVAL, MAX_PER_MINUTE)
#             while True:
#                 try:
#                     push_unsynced_sales()
#                 except Exception as exc:
#                     log.error("Unhandled error in upload worker: %s", exc)
#                 time.sleep(UPLOAD_INTERVAL)

# except ImportError:
#     class UploadWorker:              # type: ignore[no-redef]
#         def run(self) -> None:
#             pass


# def start_upload_thread() -> object:
#     """Start the upload background thread — call once from MainWindow.__init__."""
#     try:
#         from PySide6.QtCore import QThread  # type: ignore
#         thread = QThread()
#         worker = UploadWorker()
#         worker.moveToThread(thread)
#         thread.started.connect(worker.run)
#         thread._worker = worker      # prevent GC
#         thread.start()
#         log.info("POS upload QThread started.")
#         return thread
#     except ImportError:
#         def _loop():
#             while True:
#                 try:
#                     push_unsynced_sales()
#                 except Exception as exc:
#                     log.error("Unhandled error: %s", exc)
#                 time.sleep(UPLOAD_INTERVAL)
#         t = threading.Thread(target=_loop, daemon=True, name="POSUploadThread")
#         t.start()
#         return t

# =============================================================================
# services/pos_upload_service.py  —  Push local POS sales → Frappe
# Rate-limited to 20 invoices/minute to stay within Frappe's limits.
# Sends as submitted (docstatus=1). Customer resolved dynamically — no hardcoding.
# =============================================================================

from __future__ import annotations

import json
import logging
import time
import threading
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime

log = logging.getLogger("POSUpload")

UPLOAD_INTERVAL   = 60    # seconds between full cycles
REQUEST_TIMEOUT   = 30
MAX_PER_MINUTE    = 20    # Frappe rate limit guard
INTER_PUSH_DELAY  = 60 / MAX_PER_MINUTE   # 3 s between each push


# =============================================================================
# CREDENTIALS / DEFAULTS
# =============================================================================

def _get_credentials() -> tuple[str, str]:
    try:
        from services.credentials import get_credentials
        return get_credentials()
    except Exception:
        pass
    return "", ""

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
# PAYMENT METHOD MAP + ACCOUNT RESOLVER
# =============================================================================

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

# Cache: mode_of_payment name → GL account string (fetched once per session)
_MOP_ACCOUNT_CACHE: dict[str, str] = {}

# Cache: "FROM::TO::DATE" → exchange rate float
_RATE_CACHE: dict[str, float] = {}


def _get_exchange_rate(from_currency: str, to_currency: str,
                       transaction_date: str,
                       api_key: str, api_secret: str, host: str) -> float:
    """
    Fetch exchange rate from Frappe's built-in currency exchange API.
    Returns 1.0 if same currency or if fetch fails (Frappe will use its own rate).

    Endpoint:
        GET /api/method/erpnext.setup.utils.get_exchange_rate
            ?from_currency=ZWL&to_currency=USD&transaction_date=2026-03-19
    """
    if not from_currency or not to_currency:
        return 1.0
    if from_currency.upper() == to_currency.upper():
        return 1.0

    cache_key = f"{from_currency.upper()}::{to_currency.upper()}::{transaction_date}"
    if cache_key in _RATE_CACHE:
        return _RATE_CACHE[cache_key]

    try:
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
            # Frappe returns {"message": 361.5} or {"result": 361.5}
            rate = data.get("message") or data.get("result") or 1.0
            rate = float(rate)
            if rate and rate > 0:
                _RATE_CACHE[cache_key] = rate
                log.debug("Exchange rate %s→%s on %s: %.4f",
                          from_currency, to_currency, transaction_date, rate)
                return rate
    except Exception as e:
        log.debug("Exchange rate fetch failed (%s→%s): %s",
                  from_currency, to_currency, e)

    # If fetch fails, return 0 — Frappe will use its own configured rate
    log.warning("Could not fetch exchange rate %s→%s — Frappe will use its default.",
                from_currency, to_currency)
    return 0.0


def _get_mop_account(mop_name: str, company: str,
                     api_key: str, api_secret: str, host: str,
                     currency: str = "") -> str:
    """
    Returns the GL account for a Mode of Payment + Company + Currency combination.

    Frappe's Mode of Payment has an `accounts` child table:
        company | default_account
    Each account belongs to a company and implicitly a currency.
    For multi-currency setups, Frappe stores one row per company — the account
    currency must match the invoice currency or Frappe rejects it.

    Resolution order:
        1. Session cache (keyed by mop::company::currency)
        2. Frappe MOP API — matches by company, then filters by account currency
        3. server_pos_account fallback in company_defaults
    """
    cache_key = f"{mop_name}::{company}::{currency}"
    if cache_key in _MOP_ACCOUNT_CACHE:
        return _MOP_ACCOUNT_CACHE[cache_key]

    # Try fetching from Frappe's Mode of Payment doctype
    try:
        url = (
            f"{host}/api/resource/Mode%20of%20Payment/{urllib.parse.quote(mop_name)}"
            f"?fields=[\"accounts\"]"
        )
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"token {api_key}:{api_secret}")
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
            data     = json.loads(r.read().decode())
            accounts = (data.get("data") or {}).get("accounts", [])

        # Filter by company first
        company_accounts = [
            row for row in accounts
            if not company or row.get("company") == company
        ]

        # If currency specified, prefer an account whose currency matches.
        # Frappe account names often end in "- USD" or "- ZWL" — use that as hint.
        matched_acct = ""
        if currency and company_accounts:
            for row in company_accounts:
                acct = row.get("default_account", "")
                # Check if account name contains the currency code
                if acct and currency.upper() in acct.upper():
                    matched_acct = acct
                    break

        # Fall back to first company account if no currency match
        if not matched_acct and company_accounts:
            matched_acct = company_accounts[0].get("default_account", "")

        if matched_acct:
            _MOP_ACCOUNT_CACHE[cache_key] = matched_acct
            log.debug("MOP account resolved: %s [%s] → %s", mop_name, currency, matched_acct)
            return matched_acct

    except Exception as e:
        log.debug("Could not fetch MOP account for '%s': %s", mop_name, e)

    # Fallback: use server_pos_account from company_defaults if set
    fallback = _get_defaults().get("server_pos_account", "").strip()
    if fallback:
        _MOP_ACCOUNT_CACHE[cache_key] = fallback
        log.debug("MOP account fallback (company_defaults): %s", fallback)
        return fallback

    log.warning(
        "No GL account found for MOP '%s' (currency=%s). "
        "Configure accounts on the Mode of Payment in Frappe "
        "or set server_pos_account in company_defaults.", mop_name, currency or "any"
    )
    return ""


# =============================================================================
# BUILD PAYLOAD
# =============================================================================

def _build_payload(sale: dict, items: list[dict], defaults: dict,
                   api_key: str = "", api_secret: str = "") -> dict:
    company           = defaults.get("server_company",           "")
    warehouse         = defaults.get("server_warehouse",         "")
    cost_center       = defaults.get("server_cost_center",       "")
    taxes_and_charges = defaults.get("server_taxes_and_charges", "")
    walk_in           = defaults.get("server_walk_in_customer",  "default").strip() or "default"
    host              = _get_host()

    customer = (sale.get("customer_name") or "").strip() or walk_in

    posting_date = sale.get("invoice_date") or datetime.today().strftime("%Y-%m-%d")
    raw_time     = sale.get("time")         or datetime.now().strftime("%H:%M:%S")
    posting_time = str(raw_time) if len(str(raw_time)) == 8 else str(raw_time) + ":00"

    mode_of_payment  = _METHOD_MAP.get(str(sale.get("method", "")).upper().strip(), "Cash")
    currency         = (sale.get("currency") or "USD").strip().upper()
    mop_account      = _get_mop_account(mode_of_payment, company, api_key, api_secret, host, currency)

    # Fetch exchange rate from Frappe for non-USD currencies
    company_currency = defaults.get("server_company_currency", "USD").strip().upper() or "USD"
    conversion_rate  = _get_exchange_rate(
        currency, company_currency, posting_date, api_key, api_secret, host
    ) if currency != company_currency else 1.0

    frappe_items = []
    for it in items:
        item_code = (it.get("part_no") or "").strip()
        qty       = float(it.get("qty",   0))
        rate      = float(it.get("price", 0))
        if not item_code or qty <= 0:
            continue
        row = {"item_code": item_code, "qty": qty, "rate": rate}
        if cost_center:
            row["cost_center"] = cost_center
        frappe_items.append(row)

    if not frappe_items:
        return {}

    total = float(sale.get("total", 0))

    payload = {
        "customer":               customer,
        "posting_date":           posting_date,
        "posting_time":           posting_time,
        "currency":               currency,
        "is_pos":                 0,   # unpaid — payment_entry_service pushes PE separately
        "update_stock":           0,
        "docstatus":              1,   # submitted but unpaid
        "custom_sales_reference": sale.get("invoice_no", ""),
        "items":                  frappe_items,
    }

    # Only set conversion_rate when not company currency
    # 0.0 means fetch failed — omit it and let Frappe use its own rate
    if conversion_rate and conversion_rate != 1.0:
        payload["conversion_rate"] = conversion_rate

    if company:           payload["company"]           = company
    if cost_center:       payload["cost_center"]       = cost_center
    if warehouse:         payload["set_warehouse"]     = warehouse
    if taxes_and_charges: payload["taxes_and_charges"] = taxes_and_charges

    return payload


# =============================================================================
# PUSH ONE SALE
# =============================================================================

def _push_sale(sale: dict, api_key: str, api_secret: str,
               defaults: dict, host: str) -> bool:
    inv_no  = sale.get("invoice_no", str(sale["id"]))
    walk_in = defaults.get("server_walk_in_customer", "default").strip() or "default"

    try:
        from models.sale import get_sale_items
        items = get_sale_items(sale["id"])
    except Exception as e:
        log.error("Items fetch failed for %s: %s", inv_no, e)
        return False

    payload = _build_payload(sale, items, defaults, api_key, api_secret)
    if not payload:
        log.warning("Sale %s — no valid items, skipping (marked synced).", inv_no)
        return True

    url = f"{host}/api/resource/Sales%20Invoice"

    # Two attempts: real customer first, walk-in fallback second
    attempts = [payload]
    if payload["customer"] != walk_in:
        attempts.append({**payload, "customer": walk_in})

    for i, p in enumerate(attempts):
        req = urllib.request.Request(
            url=url,
            data=json.dumps(p).encode("utf-8"),
            method="POST",
            headers={
                "Content-Type":  "application/json",
                "Accept":        "application/json",
                "Authorization": f"token {api_key}:{api_secret}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                name = (json.loads(resp.read()).get("data") or {}).get("name", "")
                suffix = f" [walk-in fallback: {walk_in}]" if i > 0 else ""
                log.info("✅ %s → Frappe %s  customer=%s%s",
                         inv_no, name, p["customer"], suffix)
                return name if name else True

        except urllib.error.HTTPError as e:
            try:
                err = json.loads(e.read().decode())
                msg = (err.get("exception") or err.get("message") or
                       str(err.get("_server_messages", "")) or f"HTTP {e.code}")
            except Exception:
                msg = f"HTTP {e.code}"

            if e.code == 409:
                log.info("Sale %s already exists on Frappe (409) — marking synced.", inv_no)
                return True

            # Permanent Frappe-side data errors — not retryable.
            # Mark synced to stop the retry loop; fix the data in Frappe manually.
            _PERMANENT_ERRORS = (
                "negativestockerror",
                "not marked as sales item",
                "is not a sales item",
                "account is required",   # MOP has no GL account — fix in Frappe
            )
            if e.code == 417 and any(p in msg.lower() for p in _PERMANENT_ERRORS):
                log.warning(
                    "⚠️  Sale %s — permanent Frappe data error (marked synced to stop loop).\n  %s",
                    inv_no, msg,
                )
                return True   # mark_synced called by caller

            # Customer-not-found error → retry with walk-in on next attempt
            if i == 0 and e.code in (417, 500) and any(
                kw in msg.lower() for kw in ("customer", "payment_terms", "nonetype")
            ):
                log.warning("Sale %s — customer '%s' rejected, retrying with walk-in…",
                            inv_no, p["customer"])
                continue

            log.error("❌ Sale %s  HTTP %s: %s", inv_no, e.code, msg)
            return False

        except urllib.error.URLError as e:
            log.warning("Network error pushing %s: %s", inv_no, e.reason)
            return False

        except Exception as e:
            log.error("Unexpected error pushing %s: %s", inv_no, e)
            return False

    return False


# =============================================================================
# PUBLIC — push all unsynced (rate-limited to MAX_PER_MINUTE)
# =============================================================================

def push_unsynced_sales() -> dict:
    result = {"pushed": 0, "failed": 0, "total": 0}

    api_key, api_secret = _get_credentials()
    if not api_key or not api_secret:
        log.warning("No API credentials — skipping upload cycle.")
        return result

    host     = _get_host()
    defaults = _get_defaults()

    try:
        from models.sale import get_unsynced_sales, mark_synced, mark_synced_with_ref
        sales = get_unsynced_sales()
    except Exception as e:
        log.error("Could not read unsynced sales: %s", e)
        return result

    result["total"] = len(sales)
    if not sales:
        log.debug("No unsynced sales.")
        return result

    log.info("Pushing %d sale(s) to Frappe (max %d/min)…", len(sales), MAX_PER_MINUTE)

    for idx, sale in enumerate(sales):
        if idx > 0 and idx % MAX_PER_MINUTE == 0:
            log.info("Rate limit pause — waiting 60s before next batch…")
            time.sleep(60)

        result_val = _push_sale(sale, api_key, api_secret, defaults, host)
        if result_val:
            try:
                # result_val is the Frappe doc name string on success, or True for
                # permanent-error cases (409, NegativeStockError, not-sales-item)
                frappe_ref = result_val if isinstance(result_val, str) else ""
                mark_synced_with_ref(sale["id"], frappe_ref)
                result["pushed"] += 1
            except Exception as e:
                log.error("mark_synced failed for sale %s: %s", sale["id"], e)
                result["failed"] += 1
        else:
            result["failed"] += 1

        if idx < len(sales) - 1:
            time.sleep(INTER_PUSH_DELAY)   # 3 s between each push

    log.info("Upload done — ✅ %d pushed  ❌ %d failed  (of %d)",
             result["pushed"], result["failed"], result["total"])
    return result


# =============================================================================
# QTHREAD WORKER
# =============================================================================

try:
    from PySide6.QtCore import QObject  # type: ignore

    class UploadWorker(QObject):
        def run(self) -> None:
            log.info("POS upload worker started (interval=%ds, max=%d/min).",
                     UPLOAD_INTERVAL, MAX_PER_MINUTE)
            while True:
                try:
                    push_unsynced_sales()
                except Exception as exc:
                    log.error("Unhandled error in upload worker: %s", exc)
                time.sleep(UPLOAD_INTERVAL)

except ImportError:
    class UploadWorker:              # type: ignore[no-redef]
        def run(self) -> None:
            pass


def start_upload_thread() -> object:
    """Start the upload background thread — call once from MainWindow.__init__."""
    try:
        from PySide6.QtCore import QThread  # type: ignore
        thread = QThread()
        worker = UploadWorker()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        thread._worker = worker      # prevent GC
        thread.start()
        log.info("POS upload QThread started.")
        return thread
    except ImportError:
        def _loop():
            while True:
                try:
                    push_unsynced_sales()
                except Exception as exc:
                    log.error("Unhandled error: %s", exc)
                time.sleep(UPLOAD_INTERVAL)
        t = threading.Thread(target=_loop, daemon=True, name="POSUploadThread")
        t.start()
        return t