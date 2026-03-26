# # # =============================================================================
# # # services/credit_note_sync_service.py
# # #
# # # Pushes local credit notes to Frappe as Sales Invoice returns.
# # #
# # # THE FRAPPE API — same endpoint as a normal invoice, two extra fields:
# # #
# # #   POST /api/resource/Sales Invoice
# # #   {
# # #       "is_return":      1,
# # #       "return_against": "ACC-SINV-2026-00063",  <- original Frappe doc name
# # #       "customer":       "default",
# # #       "posting_date":   "2026-03-20",
# # #       "docstatus":      1,
# # #       "items": [
# # #           {"item_code": "PART-001", "qty": -2, "rate": 5.00},
# # #       ],
# # #       ... same company/warehouse/cost_center as normal invoices ...
# # #   }
# # #
# # # Quantities MUST be negative. The original invoice name (frappe_ref on
# # # the local sale) goes in return_against.
# # #
# # # Call start_credit_note_sync_daemon() once from MainWindow.__init__.
# # # =============================================================================
# # from __future__ import annotations

# # import json
# # import logging
# # import time
# # import threading
# # import urllib.request
# # import urllib.error
# # from datetime import datetime

# # log = logging.getLogger("CreditNoteSync")

# # SYNC_INTERVAL   = 60
# # REQUEST_TIMEOUT = 30

# # _thread: threading.Thread | None = None
# # _lock   = threading.Lock()


# # # =============================================================================
# # # CREDENTIALS / DEFAULTS  (same as pos_upload_service)
# # # =============================================================================

# # def _get_credentials() -> tuple[str, str]:
# #     try:
# #         from services.credentials import get_credentials
# #         return get_credentials()
# #     except Exception:
# #         pass
# #     try:
# #         from database.db import get_connection
# #         conn = get_connection(); cur = conn.cursor()
# #         cur.execute("SELECT api_key, api_secret FROM company_defaults WHERE id = 1")
# #         row = cur.fetchone(); conn.close()
# #         if row and row[0] and row[1]:
# #             return row[0], row[1]
# #     except Exception:
# #         pass
# #     import os
# #     return os.environ.get("HAVANO_API_KEY", ""), os.environ.get("HAVANO_API_SECRET", "")


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
# # # BUILD PAYLOAD
# # # =============================================================================

# # def _build_payload(cn: dict, defaults: dict) -> dict:
# #     company           = defaults.get("server_company",           "")
# #     warehouse         = defaults.get("server_warehouse",         "")
# #     cost_center       = defaults.get("server_cost_center",       "")
# #     taxes_and_charges = defaults.get("server_taxes_and_charges", "")
# #     walk_in           = defaults.get("server_walk_in_customer",  "default").strip() or "default"

# #     customer = (cn.get("customer_name") or "").strip() or walk_in

# #     frappe_items = []
# #     for item in cn.get("items_to_return", []):
# #         item_code = (item.get("part_no") or "").strip()
# #         qty       = float(item.get("qty",   0))
# #         rate      = float(item.get("price", 0))
# #         if not item_code or qty <= 0:
# #             continue
# #         row = {"item_code": item_code, "qty": -abs(qty), "rate": rate}
# #         if cost_center:
# #             row["cost_center"] = cost_center
# #         frappe_items.append(row)

# #     if not frappe_items:
# #         return {}

# #     payload = {
# #         "is_return":           1,
# #         "return_against":      cn["frappe_ref"],
# #         "customer":            customer,
# #         "posting_date":        datetime.today().strftime("%Y-%m-%d"),
# #         "posting_time":        datetime.now().strftime("%H:%M:%S"),
# #         "currency":            (cn.get("currency") or "USD").upper(),
# #         "is_pos":              0,
# #         "update_stock":        0,
# #         "docstatus":           1,
# #         "custom_cn_reference": cn.get("cn_number", ""),
# #         "items":               frappe_items,
# #     }
# #     if company:           payload["company"]           = company
# #     if cost_center:       payload["cost_center"]       = cost_center
# #     if warehouse:         payload["set_warehouse"]     = warehouse
# #     if taxes_and_charges: payload["taxes_and_charges"] = taxes_and_charges
# #     return payload


# # # =============================================================================
# # # PUSH ONE CN
# # # =============================================================================

# # def _push_cn(cn: dict, api_key: str, api_secret: str,
# #              defaults: dict, host: str):
# #     cn_num  = cn.get("cn_number", str(cn["id"]))
# #     payload = _build_payload(cn, defaults)
# #     if not payload:
# #         log.warning("CN %s — no valid items.", cn_num)
# #         return True

# #     req = urllib.request.Request(
# #         url=f"{host}/api/resource/Sales%20Invoice",
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
# #             name = (json.loads(resp.read()).get("data") or {}).get("name", "")
# #             log.info("CN %s -> Frappe %s (return_against=%s)", cn_num, name, cn["frappe_ref"])
# #             return name if name else True

# #     except urllib.error.HTTPError as e:
# #         try:
# #             err = json.loads(e.read().decode())
# #             msg = (err.get("exception") or err.get("message") or
# #                    str(err.get("_server_messages", "")) or f"HTTP {e.code}")
# #         except Exception:
# #             msg = f"HTTP {e.code}"

# #         if e.code == 409:
# #             return True   # already exists

# #         _PERM = ("negativestockerror", "not marked as sales item",
# #                  "is not a sales item", "return_against")
# #         if e.code == 417 and any(p in msg.lower() for p in _PERM):
# #             log.warning("CN %s permanent error: %s", cn_num, msg)
# #             return True

# #         log.error("CN %s HTTP %s: %s", cn_num, e.code, msg)
# #         return False

# #     except urllib.error.URLError as e:
# #         log.warning("CN %s network error: %s", cn_num, e.reason)
# #         return False
# #     except Exception as e:
# #         log.error("CN %s unexpected: %s", cn_num, e)
# #         return False


# # # =============================================================================
# # # PUBLIC
# # # =============================================================================

# # def push_unsynced_credit_notes() -> dict:
# #     result = {"pushed": 0, "failed": 0, "skipped": 0, "total": 0}

# #     api_key, api_secret = _get_credentials()
# #     if not api_key or not api_secret:
# #         log.warning("[cn-sync] No credentials.")
# #         return result

# #     host     = _get_host()
# #     defaults = _get_defaults()

# #     try:
# #         from models.credit_note import get_pending_credit_notes, mark_cn_synced
# #         pending = get_pending_credit_notes()
# #     except Exception as e:
# #         log.error("[cn-sync] DB error: %s", e)
# #         return result

# #     result["total"] = len(pending)
# #     if not pending:
# #         return result

# #     log.info("[cn-sync] Pushing %d credit note(s)...", len(pending))

# #     for cn in pending:
# #         if not cn.get("frappe_ref"):
# #             result["skipped"] += 1
# #             continue

# #         val = _push_cn(cn, api_key, api_secret, defaults, host)
# #         if val:
# #             try:
# #                 mark_cn_synced(cn["id"], val if isinstance(val, str) else "")
# #                 result["pushed"] += 1
# #             except Exception as e:
# #                 log.error("[cn-sync] mark_cn_synced failed: %s", e)
# #                 result["failed"] += 1
# #         else:
# #             result["failed"] += 1

# #     log.info("[cn-sync] Done: %d pushed, %d failed, %d skipped",
# #              result["pushed"], result["failed"], result["skipped"])
# #     return result


# # def _loop():
# #     log.info("[cn-sync] Daemon started (interval=%ds).", SYNC_INTERVAL)
# #     while True:
# #         if _lock.acquire(blocking=False):
# #             try:
# #                 push_unsynced_credit_notes()
# #             except Exception as e:
# #                 log.error("[cn-sync] Error: %s", e)
# #             finally:
# #                 _lock.release()
# #         time.sleep(SYNC_INTERVAL)


# # def start_credit_note_sync_daemon() -> threading.Thread:
# #     """Call once from MainWindow.__init__ alongside the other daemons."""
# #     global _thread
# #     if _thread and _thread.is_alive():
# #         return _thread
# #     _thread = threading.Thread(target=_loop, daemon=True, name="CreditNoteSyncDaemon")
# #     _thread.start()
# #     log.info("[cn-sync] Daemon started.")
# #     return _thread

# # =============================================================================
# # services/credit_note_sync_service.py
# #
# # Pushes local credit notes to Frappe as Sales Invoice returns.
# #
# # THE FRAPPE API — same endpoint as a normal invoice, two extra fields:
# #
# #   POST /api/resource/Sales Invoice
# #   {
# #       "is_return":      1,
# #       "return_against": "ACC-SINV-2026-00063",  <- original Frappe doc name
# #       "customer":       "default",
# #       "posting_date":   "2026-03-20",
# #       "docstatus":      1,
# #       "items": [
# #           {"item_code": "PART-001", "qty": -2, "rate": 5.00},
# #       ],
# #       ... same company/warehouse/cost_center as normal invoices ...
# #   }
# #
# # Quantities MUST be negative. The original invoice name (frappe_ref on
# # the local sale) goes in return_against.
# #
# # Call start_credit_note_sync_daemon() once from MainWindow.__init__.
# # =============================================================================
# from __future__ import annotations

# import json
# import logging
# import time
# import threading
# import urllib.request
# import urllib.error
# from datetime import datetime

# log = logging.getLogger("CreditNoteSync")

# SYNC_INTERVAL   = 60
# REQUEST_TIMEOUT = 30

# _thread: threading.Thread | None = None
# _lock   = threading.Lock()


# # =============================================================================
# # CREDENTIALS / DEFAULTS  (same as pos_upload_service)
# # =============================================================================

# def _get_credentials() -> tuple[str, str]:
#     try:
#         from services.credentials import get_credentials
#         return get_credentials()
#     except Exception:
#         pass
#     try:
#         from database.db import get_connection
#         conn = get_connection(); cur = conn.cursor()
#         cur.execute("SELECT api_key, api_secret FROM company_defaults WHERE id = 1")
#         row = cur.fetchone(); conn.close()
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


# def _get_host() -> str:
#     try:
#         host = _get_defaults().get("server_api_host", "").strip().rstrip("/")
#         if host:
#             return host
#     except Exception:
#         pass
#     return "https://apk.havano.cloud"


# # =============================================================================
# # BUILD PAYLOAD
# # =============================================================================

# def _build_payload(cn: dict, defaults: dict) -> dict:
#     company           = defaults.get("server_company",           "")
#     warehouse         = defaults.get("server_warehouse",         "")
#     cost_center       = defaults.get("server_cost_center",       "")
#     taxes_and_charges = defaults.get("server_taxes_and_charges", "")
#     walk_in           = defaults.get("server_walk_in_customer",  "default").strip() or "default"

#     customer = (cn.get("customer_name") or "").strip() or walk_in

#     frappe_items = []
#     for item in cn.get("items_to_return", []):
#         item_code = (item.get("part_no") or "").strip()
#         qty       = float(item.get("qty",   0))
#         rate      = float(item.get("price", 0))
#         if not item_code or qty <= 0:
#             continue
#         row = {"item_code": item_code, "qty": -abs(qty), "rate": rate}
#         if cost_center:
#             row["cost_center"] = cost_center
#         frappe_items.append(row)

#     if not frappe_items:
#         return {}

#     payload = {
#         "is_return":           1,
#         "return_against":      cn["frappe_ref"],
#         "customer":            customer,
#         "posting_date":        datetime.today().strftime("%Y-%m-%d"),
#         "posting_time":        datetime.now().strftime("%H:%M:%S"),
#         "currency":            (cn.get("currency") or "USD").upper(),
#         "is_pos":              0,
#         "update_stock":        0,
#         "docstatus":           1,
#         "custom_cn_reference": cn.get("cn_number", ""),
#         "items":               frappe_items,
#     }
#     if company:           payload["company"]           = company
#     if cost_center:       payload["cost_center"]       = cost_center
#     if warehouse:         payload["set_warehouse"]     = warehouse
#     if taxes_and_charges: payload["taxes_and_charges"] = taxes_and_charges
#     return payload


# # =============================================================================
# # PUSH ONE CN
# # =============================================================================

# def _push_cn(cn: dict, api_key: str, api_secret: str,
#              defaults: dict, host: str):
#     cn_num  = cn.get("cn_number", str(cn["id"]))
#     payload = _build_payload(cn, defaults)
#     if not payload:
#         log.warning("CN %s — no valid items.", cn_num)
#         return True

#     req = urllib.request.Request(
#         url=f"{host}/api/resource/Sales%20Invoice",
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
#             name = (json.loads(resp.read()).get("data") or {}).get("name", "")
#             log.info("CN %s -> Frappe %s (return_against=%s)", cn_num, name, cn["frappe_ref"])
#             return name if name else True

#     except urllib.error.HTTPError as e:
#         try:
#             err = json.loads(e.read().decode())
#             msg = (err.get("exception") or err.get("message") or
#                    str(err.get("_server_messages", "")) or f"HTTP {e.code}")
#         except Exception:
#             msg = f"HTTP {e.code}"

#         if e.code == 409:
#             return True   # already exists

#         _PERM = ("negativestockerror", "not marked as sales item",
#                  "is not a sales item", "return_against")
#         if e.code == 417 and any(p in msg.lower() for p in _PERM):
#             log.warning("CN %s permanent error: %s", cn_num, msg)
#             return True

#         log.error("CN %s HTTP %s: %s", cn_num, e.code, msg)
#         return False

#     except urllib.error.URLError as e:
#         log.warning("CN %s network error: %s", cn_num, e.reason)
#         return False
#     except Exception as e:
#         log.error("CN %s unexpected: %s", cn_num, e)
#         return False


# # =============================================================================
# # AUTO PAYMENT ENTRY — triggered after a CN is confirmed on Frappe
# # =============================================================================

# def _create_cn_payment_entry(cn: dict) -> None:
#     """
#     Creates a local 'Pay' payment entry for the CN so the existing
#     payment sync daemon picks it up and pushes it to Frappe automatically.
#     Only called once, right after create_credit_note() succeeds locally.
#     """
#     try:
#         from services.cn_payment_entry_service import create_cn_payment_entry
#         create_cn_payment_entry(cn)
#     except Exception as e:
#         log.warning("[cn-sync] Auto payment entry creation failed for %s: %s",
#                     cn.get("cn_number", "?"), e)


# def _link_cn_payment_to_frappe(cn_number: str, frappe_cn_ref: str) -> None:
#     """
#     After the CN lands on Frappe and we have its document name, set
#     frappe_invoice_ref on the matching 'Pay' payment entry row so the
#     payment sync daemon can push it.
#     """
#     if not cn_number or not frappe_cn_ref:
#         return
#     try:
#         from services.cn_payment_entry_service import link_cn_payment_to_frappe
#         link_cn_payment_to_frappe(cn_number, frappe_cn_ref)
#     except Exception as e:
#         log.warning("[cn-sync] link_cn_payment_to_frappe failed for %s: %s", cn_number, e)


# # =============================================================================
# # PUBLIC
# # =============================================================================

# def push_unsynced_credit_notes() -> dict:
#     result = {"pushed": 0, "failed": 0, "skipped": 0, "total": 0}

#     api_key, api_secret = _get_credentials()
#     if not api_key or not api_secret:
#         log.warning("[cn-sync] No credentials.")
#         return result

#     host     = _get_host()
#     defaults = _get_defaults()

#     try:
#         from models.credit_note import get_pending_credit_notes, mark_cn_synced
#         pending = get_pending_credit_notes()
#     except Exception as e:
#         log.error("[cn-sync] DB error: %s", e)
#         return result

#     result["total"] = len(pending)
#     if not pending:
#         return result

#     log.info("[cn-sync] Pushing %d credit note(s)...", len(pending))

#     for cn in pending:
#         if not cn.get("frappe_ref"):
#             result["skipped"] += 1
#             continue

#         val = _push_cn(cn, api_key, api_secret, defaults, host)
#         if val:
#             frappe_cn_ref = val if isinstance(val, str) and val not in ("True", "SYNCED") else ""
#             try:
#                 mark_cn_synced(cn["id"], frappe_cn_ref)
#                 result["pushed"] += 1
#             except Exception as e:
#                 log.error("[cn-sync] mark_cn_synced failed: %s", e)
#                 result["failed"] += 1
#                 continue

#             # Auto-create / link the refund payment entry
#             if frappe_cn_ref:
#                 _link_cn_payment_to_frappe(cn.get("cn_number", ""), frappe_cn_ref)
#             else:
#                 log.debug("[cn-sync] No frappe_cn_ref returned for %s — payment entry "
#                           "will be linked on next sync cycle once ref is available.",
#                           cn.get("cn_number", "?"))
#         else:
#             result["failed"] += 1

#     log.info("[cn-sync] Done: %d pushed, %d failed, %d skipped",
#              result["pushed"], result["failed"], result["skipped"])
#     return result


# def _loop():
#     log.info("[cn-sync] Daemon started (interval=%ds).", SYNC_INTERVAL)
#     while True:
#         if _lock.acquire(blocking=False):
#             try:
#                 push_unsynced_credit_notes()
#             except Exception as e:
#                 log.error("[cn-sync] Error: %s", e)
#             finally:
#                 _lock.release()
#         time.sleep(SYNC_INTERVAL)


# def start_credit_note_sync_daemon() -> threading.Thread:
#     """Call once from MainWindow.__init__ alongside the other daemons."""
#     global _thread
#     if _thread and _thread.is_alive():
#         return _thread
#     _thread = threading.Thread(target=_loop, daemon=True, name="CreditNoteSyncDaemon")
#     _thread.start()
#     log.info("[cn-sync] Daemon started.")
#     return _thread