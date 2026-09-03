# from __future__ import annotations

# import json
# import logging
# import time
# import threading
# import urllib.request
# import urllib.error
# import urllib.parse
# from datetime import datetime, date

# log = logging.getLogger("SalesOrderUpload")

# UPLOAD_INTERVAL  = 60        # seconds between full sync cycles
# REQUEST_TIMEOUT  = 30        # HTTP timeout per request
# MAX_PER_MINUTE   = 20
# INTER_PUSH_DELAY = 60 / MAX_PER_MINUTE   # 3 s between pushes


# # =============================================================================
# # JSON encoder — handles datetime/date objects
# # =============================================================================

# class _DateTimeEncoder(json.JSONEncoder):
#     def default(self, obj):
#         if isinstance(obj, (datetime, date)):
#             return obj.isoformat()
#         return super().default(obj)


# def _dumps(obj) -> str:
#     return json.dumps(obj, cls=_DateTimeEncoder)


# # =============================================================================
# # Credentials / defaults  (same helpers as pos_upload_service)
# # =============================================================================

# def _get_credentials() -> tuple[str, str]:
#     try:
#         from services.credentials import get_credentials
#         return get_credentials()
#     except Exception:
#         return "", ""


# def _get_defaults() -> dict:
#     try:
#         from models.company_defaults import get_defaults
#         return get_defaults() or {}
#     except Exception:
#         return {}
# from services.site_config import get_host as _get_host

# # =============================================================================
# # Build ERPNext Sales Order payload
# # =============================================================================

# def _build_so_payload(order: dict, items: list[dict], defaults: dict) -> dict | None:
#     """
#     Construct the JSON body for POST /api/resource/Sales Order.
#     Returns None if there are no valid line items (caller skips this order).
#     """
#     frappe_items = []
#     warehouse    = defaults.get("server_warehouse", "").strip()
#     cost_center  = defaults.get("server_cost_center", "").strip()

#     # Use the saved delivery_date; fall back to order_date, then today
#     delivery_date = (
#         order.get("delivery_date")
#         or order.get("order_date")
#         or date.today().isoformat()
#     )
#     # Ensure it's a plain ISO string (strip time component if present)
#     if delivery_date and "T" in str(delivery_date):
#         delivery_date = str(delivery_date).split("T")[0]

#     for it in items:
#         code = (it.get("item_code") or "").strip()
#         if not code:
#             continue
#         qty  = float(it.get("qty")  or 1)
#         rate = float(it.get("rate") or 0)
#         row  = {
#             "item_code":     code,
#             "item_name":     it.get("item_name") or code,
#             "qty":           qty,
#             "rate":          rate,
#             "amount":        round(qty * rate, 4),
#             "delivery_date": delivery_date,
#         }
#         if warehouse:
#             row["warehouse"] = warehouse
#         if cost_center:
#             row["cost_center"] = cost_center
#         frappe_items.append(row)

#     if not frappe_items:
#         return None

#     walk_in  = defaults.get("server_walk_in_customer", "default").strip() or "default"
#     customer = (order.get("customer_name") or "").strip() or walk_in
#     company  = (order.get("company") or defaults.get("server_company", "")).strip()

#     payload = {
#         "doctype":          "Sales Order",
#         "docstatus":        1,            # 1 = Submitted (was 0 = Draft)
#         "customer":         customer,
#         "transaction_date": order.get("order_date") or date.today().isoformat(),
#         "delivery_date":    delivery_date,  # actual delivery date from order
#         "order_type":       order.get("order_type") or "Sales",
#         "reserve_stock":    1,            # reserve stock on submit
#         "items":            frappe_items,
#     }

#     if company:
#         payload["company"] = company
#     if cost_center:
#         payload["cost_center"] = cost_center

#     # Advance / deposit note (actual payment entry handled separately in ERPNext)
#     deposit = float(order.get("deposit_amount") or 0)
#     if deposit > 0:
#         method = order.get("deposit_method") or ""
#         payload["remarks"] = (
#             f"Laybye deposit: USD {deposit:.2f}"
#             + (f" via {method}" if method else "")
#         )

#     taxes_and_charges = defaults.get("server_taxes_and_charges", "").strip()
#     if taxes_and_charges:
#         payload["taxes_and_charges"] = taxes_and_charges

#     return payload


# # =============================================================================
# # Push one order to Frappe
# # =============================================================================

# _PERMANENT_ERRORS = (
#     "not marked as sales item",
#     "is not a sales item",
#     "account is required",
#     "customer not found",
# )


# def _push_order(order: dict, api_key: str, api_secret: str,
#                 defaults: dict, host: str):
#     """
#     Returns:
#         str   — server doc name on success
#         True  — permanent skip (data error / already exists), mark synced
#         False — transient failure, retry next cycle
#     """
#     order_no  = order.get("order_no") or str(order["id"])
#     customer  = order.get("customer_name") or ""
#     amount    = float(order.get("total") or 0)

#     def _fail(code: str, msg: str) -> bool:
#         log.error("❌ Order %s  %s: %s", order_no, code, msg)
#         try:
#             from services.sync_errors_service import record_error
#             record_error("SO", order_no, msg,
#                          customer=customer, amount=amount, error_code=code)
#         except Exception as _re:
#             log.debug("sync_errors record_error skipped: %s", _re)
#         try:
#             from main_window import sync_error_bus
#             sync_error_bus.post_error("SalesOrderUpload", order_no,
#                                       f"{code}: {msg}")
#         except Exception:
#             pass
#         return False

#     try:
#         from models.sales_order import get_order_items
#         items = get_order_items(order["id"])
#     except Exception as e:
#         return _fail("DB_ERROR", f"Could not load order items: {e}")

#     payload = _build_so_payload(order, items, defaults)
#     if not payload:
#         log.warning("Order %s — no valid items, skipping.", order_no)
#         return True

#     url = f"{host}/api/resource/Sales%20Order"

#     try:
#         body = _dumps(payload).encode("utf-8")
#     except Exception as e:
#         return _fail("JSON_ERROR", f"Could not serialise order: {e}")

#     req = urllib.request.Request(
#         url=url,
#         data=body,
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
#             log.info("✅ Order %s synced → %s", order_no, name)
#             # clear any previous errors for this order
#             try:
#                 from services.sync_errors_service import resolve
#                 resolve("SO", order_no)
#             except Exception:
#                 pass
#             return name if name else True

#     except urllib.error.HTTPError as e:
#         try:
#             err_body = json.loads(e.read().decode())
#             msg = (
#                 err_body.get("exception")
#                 or err_body.get("message")
#                 or str(err_body.get("_server_messages", ""))
#                 or f"HTTP {e.code}"
#             )
#         except Exception:
#             msg = f"HTTP {e.code}"

#         if e.code == 409:
#             log.info("Order %s already exists on server (409) — marking synced.", order_no)
#             try:
#                 from services.sync_errors_service import resolve
#                 resolve("SO", order_no)
#             except Exception:
#                 pass
#             return True

#         if e.code == 417 and any(kw in msg.lower() for kw in _PERMANENT_ERRORS):
#             log.warning("Order %s — permanent data error, marking synced.\n  %s",
#                         order_no, msg)
#             return _fail(f"HTTP {e.code}", msg) or True  # record then skip

#         return _fail(f"HTTP {e.code}", msg)

#     except urllib.error.URLError as e:
#         return _fail("NETWORK", f"Cannot reach server: {e.reason} — check site URL in Company Defaults.")

#     except Exception as e:
#         return _fail("UNKNOWN", str(e))


# # =============================================================================
# # PUBLIC — push all unsynced orders (called by worker loop)
# # =============================================================================

# def push_unsynced_orders() -> dict:
#     result = {"pushed": 0, "failed": 0, "total": 0}

#     api_key, api_secret = _get_credentials()
#     if not api_key or not api_secret:
#         log.warning("No API credentials — skipping Sales Order upload cycle.")
#         return result

#     host     = _get_host()
#     defaults = _get_defaults()

#     try:
#         from models.sales_order import get_unsynced_orders, mark_order_synced
#         orders = get_unsynced_orders()
#     except Exception as e:
#         log.error("Could not read unsynced orders: %s", e)
#         return result

#     result["total"] = len(orders)
#     if not orders:
#         log.debug("No unsynced sales orders.")
#         return result

#     log.info("Pushing %d Sales Order(s) to Frappe…", len(orders))

#     for idx, order in enumerate(orders):
#         # Rate-limit: pause after every MAX_PER_MINUTE pushes
#         if idx > 0 and idx % MAX_PER_MINUTE == 0:
#             log.info("Rate limit pause — waiting 60 s…")
#             time.sleep(60)

#         res = _push_order(order, api_key, api_secret, defaults, host)

#         if res:
#             frappe_ref = res if isinstance(res, str) else ""
#             try:
#                 mark_order_synced(order["id"], frappe_ref)
#                 result["pushed"] += 1
#             except Exception as e:
#                 log.error("mark_order_synced failed for %s: %s", order["id"], e)
#                 result["failed"] += 1

#             # Link deposit payment entry to Frappe SO ref so the
#             # payment daemon can push it automatically
#             if frappe_ref and isinstance(frappe_ref, str):
#                 try:
#                     from services.laybye_payment_entry_service import link_laybye_payment_to_frappe
#                     link_laybye_payment_to_frappe(order.get("order_no", ""), frappe_ref)
#                 except Exception as _lpe:
#                     log.warning("[so-sync] link laybye payment failed for %s: %s",
#                                 order.get("order_no", ""), _lpe)
#         else:
#             result["failed"] += 1

#         if idx < len(orders) - 1:
#             time.sleep(INTER_PUSH_DELAY)

#     log.info(
#         "Sales Order upload done — ✅ %d pushed  ❌ %d failed  (of %d)",
#         result["pushed"], result["failed"], result["total"],
#     )
#     return result


# # =============================================================================
# # QThread worker  (same pattern as UploadWorker in pos_upload_service)
# # =============================================================================

# try:
#     from PySide6.QtCore import QObject  # type: ignore

#     class SalesOrderUploadWorker(QObject):
#         def run(self) -> None:
#             log.info("Sales Order upload worker started.")
#             while True:
#                 try:
#                     push_unsynced_orders()
#                 except Exception as exc:
#                     log.error("Unhandled error in SO upload worker: %s", exc)
#                 time.sleep(UPLOAD_INTERVAL)

# except ImportError:
#     class SalesOrderUploadWorker:  # type: ignore[no-redef]
#         def run(self) -> None:
#             pass


# def start_so_upload_thread() -> object:
#     """
#     Start the Sales Order upload background thread.
#     Call once from MainWindow after login.
#     Returns the QThread (or plain Thread if PySide6 is unavailable).
#     """
#     try:
#         from PySide6.QtCore import QThread  # type: ignore

#         thread = QThread()
#         worker = SalesOrderUploadWorker()
#         worker.moveToThread(thread)
#         thread.started.connect(worker.run)
#         thread._worker = worker   # keep reference so GC doesn't destroy it
#         thread.start()
#         log.info("Sales Order upload QThread started.")
#         return thread

#     except ImportError:
#         def _loop():
#             while True:
#                 try:
#                     push_unsynced_orders()
#                 except Exception as exc:
#                     log.error("Unhandled error: %s", exc)
#                 time.sleep(UPLOAD_INTERVAL)

#         t = threading.Thread(target=_loop, daemon=True, name="SOUploadThread")
#         t.start()
#         log.info("Sales Order upload Thread started (no PySide6).")
#         return t
from __future__ import annotations

import json
import logging
import time
import threading
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, date

log = logging.getLogger("SalesOrderUpload")

UPLOAD_INTERVAL  = 60        # seconds between full sync cycles
REQUEST_TIMEOUT  = 30        # HTTP timeout per request
MAX_PER_MINUTE   = 20
INTER_PUSH_DELAY = 60 / MAX_PER_MINUTE   # 3 s between pushes


# =============================================================================
# JSON encoder — handles datetime/date objects
# =============================================================================

class _DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


def _dumps(obj) -> str:
    return json.dumps(obj, cls=_DateTimeEncoder)


# =============================================================================
# Credentials / defaults  (same helpers as pos_upload_service)
# =============================================================================

def _get_credentials() -> tuple[str, str]:
    try:
        from services.credentials import get_credentials
        return get_credentials()
    except Exception:
        return "", ""


def _get_defaults() -> dict:
    try:
        from models.company_defaults import get_defaults
        return get_defaults() or {}
    except Exception:
        return {}
from services.site_config import get_host as _get_host

# =============================================================================
# Build ERPNext Sales Order payload
# =============================================================================

def _build_so_payload(order: dict, items: list[dict], defaults: dict) -> dict | None:
    """
    Construct the JSON body for POST /api/resource/Sales Order.
    Returns None if there are no valid line items (caller skips this order).
    """
    frappe_items = []
    warehouse    = defaults.get("server_warehouse", "").strip()
    cost_center  = defaults.get("server_cost_center", "").strip()

    # Use the saved delivery_date; fall back to order_date, then today
    delivery_date = (
        order.get("delivery_date")
        or order.get("order_date")
        or date.today().isoformat()
    )
    # Ensure it's a plain ISO string (strip time component if present)
    if delivery_date and "T" in str(delivery_date):
        delivery_date = str(delivery_date).split("T")[0]

    for it in items:
        code = (it.get("item_code") or "").strip()
        if not code:
            continue
        qty  = float(it.get("qty")  or 1)
        rate = float(it.get("rate") or 0)
        row  = {
            "item_code":     code,
            "item_name":     it.get("item_name") or code,
            "qty":           qty,
            "rate":          rate,
            "amount":        round(qty * rate, 4),
            "delivery_date": delivery_date,
        }
        if warehouse:
            row["warehouse"] = warehouse
        if cost_center:
            row["cost_center"] = cost_center
        frappe_items.append(row)

    if not frappe_items:
        return None

    walk_in  = defaults.get("server_walk_in_customer", "default").strip() or "default"
    customer = (order.get("customer_name") or "").strip() or walk_in
    company  = (order.get("company") or defaults.get("server_company", "")).strip()

    payload = {
        "doctype":          "Sales Order",
        "docstatus":        1,            # 1 = Submitted (was 0 = Draft)
        "customer":         customer,
        "transaction_date": order.get("order_date") or date.today().isoformat(),
        "delivery_date":    delivery_date,  # actual delivery date from order
        "order_type":       order.get("order_type") or "Sales",
        "reserve_stock":    1,            # reserve stock on submit
        "items":            frappe_items,
    }

    if company:
        payload["company"] = company
    if cost_center:
        payload["cost_center"] = cost_center

    # Advance / deposit note (actual payment entry handled separately in ERPNext)
    deposit = float(order.get("deposit_amount") or 0)
    if deposit > 0:
        method = order.get("deposit_method") or ""
        payload["remarks"] = (
            f"Laybye deposit: USD {deposit:.2f}"
            + (f" via {method}" if method else "")
        )

    taxes_and_charges = defaults.get("server_taxes_and_charges", "").strip()
    if taxes_and_charges:
        payload["taxes_and_charges"] = taxes_and_charges

    return payload


# =============================================================================
# Push one order to Frappe
# =============================================================================

_RETRYABLE_ERRORS = (
    "negativestockerror",
    "not enough stock",
)

_PERMANENT_ERRORS = (
    "not marked as sales item",
    "is not a sales item",
    "account is required",
    "customer not found",
)


def _push_order(order: dict, api_key: str, api_secret: str,
                defaults: dict, host: str):
    """
    Returns:
        str   — server doc name on success
        True  — permanent skip (data error / already exists), mark synced
        False — transient failure, retry next cycle
    """
    order_no  = order.get("order_no") or str(order["id"])
    customer  = order.get("customer_name") or ""
    amount    = float(order.get("total") or 0)

    def _fail(code: str, msg: str) -> bool:
        log.error("❌ Order %s  %s: %s", order_no, code, msg)
        try:
            from services.sync_errors_service import record_error
            record_error("SO", order_no, msg,
                         customer=customer, amount=amount, error_code=code)
        except Exception as _re:
            log.debug("sync_errors record_error skipped: %s", _re)
        try:
            from main_window import sync_error_bus
            sync_error_bus.post_error("SalesOrderUpload", order_no,
                                      f"{code}: {msg}")
        except Exception:
            pass
        return False

    try:
        from models.sales_order import get_order_items
        items = get_order_items(order["id"])
    except Exception as e:
        return _fail("DB_ERROR", f"Could not load order items: {e}")

    payload = _build_so_payload(order, items, defaults)
    if not payload:
        log.warning("Order %s — no valid items, skipping.", order_no)
        return True

    url = f"{host}/api/resource/Sales%20Order"

    try:
        body = _dumps(payload).encode("utf-8")
    except Exception as e:
        return _fail("JSON_ERROR", f"Could not serialise order: {e}")

    req = urllib.request.Request(
        url=url,
        data=body,
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
            log.info("✅ Order %s synced → %s", order_no, name)
            # clear any previous errors for this order
            try:
                from services.sync_errors_service import resolve
                resolve("SO", order_no)
            except Exception:
                pass
            return name if name else True

    except urllib.error.HTTPError as e:
        try:
            msg = e.read().decode("utf-8", errors="replace")
        except Exception:
            msg = f"HTTP {e.code}"
        if not msg.strip():
            msg = f"HTTP {e.code}"

        if e.code == 409:
            log.info("Order %s already exists on server (409) — marking synced.", order_no)
            try:
                from services.sync_errors_service import resolve
                resolve("SO", order_no)
            except Exception:
                pass
            return True

        if e.code == 417 and any(kw in msg.lower() for kw in _RETRYABLE_ERRORS):
            log.warning("Order %s — retryable Frappe error (keeping in queue).\n  %s",
                        order_no, msg)
            return _fail(f"HTTP {e.code}", msg)

        if e.code == 417 and any(kw in msg.lower() for kw in _PERMANENT_ERRORS):
            log.warning("Order %s — permanent data error (recorded, marked synced).\n  %s",
                        order_no, msg)
            return _fail(f"HTTP {e.code}", msg) or True

        return _fail(f"HTTP {e.code}", msg)

    except urllib.error.URLError as e:
        return _fail("NETWORK", f"Cannot reach server: {e.reason} — check site URL in Company Defaults.")

    except Exception as e:
        return _fail("UNKNOWN", str(e))


# =============================================================================
# PUBLIC — push all unsynced orders (called by worker loop)
# =============================================================================

def push_unsynced_orders() -> dict:
    result = {"pushed": 0, "failed": 0, "total": 0}

    api_key, api_secret = _get_credentials()
    if not api_key or not api_secret:
        log.warning("No API credentials — skipping Sales Order upload cycle.")
        return result

    host     = _get_host()
    defaults = _get_defaults()

    try:
        from models.sales_order import get_unsynced_orders, mark_order_synced
        orders = get_unsynced_orders()
    except Exception as e:
        log.error("Could not read unsynced orders: %s", e)
        return result

    result["total"] = len(orders)
    if not orders:
        log.debug("No unsynced sales orders.")
        return result

    log.info("Pushing %d Sales Order(s) to Frappe…", len(orders))

    for idx, order in enumerate(orders):
        # Rate-limit: pause after every MAX_PER_MINUTE pushes
        if idx > 0 and idx % MAX_PER_MINUTE == 0:
            log.info("Rate limit pause — waiting 60 s…")
            time.sleep(60)

        res = _push_order(order, api_key, api_secret, defaults, host)

        if res:
            frappe_ref = res if isinstance(res, str) else ""
            try:
                mark_order_synced(order["id"], frappe_ref)
                result["pushed"] += 1
            except Exception as e:
                log.error("mark_order_synced failed for %s: %s", order["id"], e)
                result["failed"] += 1

            # Link deposit payment entry to Frappe SO ref so the
            # payment daemon can push it automatically
            if frappe_ref and isinstance(frappe_ref, str):
                try:
                    from services.laybye_payment_entry_service import link_laybye_payment_to_frappe
                    link_laybye_payment_to_frappe(order.get("order_no", ""), frappe_ref)
                except Exception as _lpe:
                    log.warning("[so-sync] link laybye payment failed for %s: %s",
                                order.get("order_no", ""), _lpe)
        else:
            result["failed"] += 1

        if idx < len(orders) - 1:
            time.sleep(INTER_PUSH_DELAY)

    log.info(
        "Sales Order upload done — ✅ %d pushed  ❌ %d failed  (of %d)",
        result["pushed"], result["failed"], result["total"],
    )
    return result


# =============================================================================
# QThread worker  (same pattern as UploadWorker in pos_upload_service)
# =============================================================================

try:
    from PySide6.QtCore import QObject  # type: ignore

    class SalesOrderUploadWorker(QObject):
        def run(self) -> None:
            log.info("Sales Order upload worker started.")
            while True:
                try:
                    push_unsynced_orders()
                except Exception as exc:
                    log.error("Unhandled error in SO upload worker: %s", exc)
                time.sleep(UPLOAD_INTERVAL)

except ImportError:
    class SalesOrderUploadWorker:  # type: ignore[no-redef]
        def run(self) -> None:
            pass


def start_so_upload_thread() -> object:
    """
    Start the Sales Order upload background thread.
    Call once from MainWindow after login.
    Returns the QThread (or plain Thread if PySide6 is unavailable).
    """
    try:
        from PySide6.QtCore import QThread  # type: ignore

        thread = QThread()
        worker = SalesOrderUploadWorker()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        thread._worker = worker   # keep reference so GC doesn't destroy it
        thread.start()
        log.info("Sales Order upload QThread started.")
        return thread

    except ImportError:
        def _loop():
            while True:
                try:
                    push_unsynced_orders()
                except Exception as exc:
                    log.error("Unhandled error: %s", exc)
                time.sleep(UPLOAD_INTERVAL)

        t = threading.Thread(target=_loop, daemon=True, name="SOUploadThread")
        t.start()
        log.info("Sales Order upload Thread started (no PySide6).")
        return t