# # =============================================================================
# # services/customer_sync_service.py
# # (credentials delegated to services.credentials)
# # =============================================================================

# from __future__ import annotations

# import json
# import logging
# import time
# import urllib.request

# log = logging.getLogger("CustomerSync")

# CUSTOMER_SYNC_INTERVAL = 300   # 5 minutes


# def _get_credentials() -> tuple[str, str]:
#     try:
#         from services.credentials import get_credentials
#         return get_credentials()
#     except Exception:
#         pass
#     return "", ""


# def sync_customers():
#     api_key, api_secret = _get_credentials()
#     if not api_key or not api_secret:
#         log.warning("[customer-sync] No credentials — skipping.")
#         return

#     from services.site_config import get_host as _gh
#     url = f"{_gh()}/api/method/havano_pos_integration.api.get_customer?page=1&limit=100"
#     req = urllib.request.Request(url)
#     req.add_header("Authorization", f"token {api_key}:{api_secret}")

#     try:
#         log.info("[customer-sync] Starting...")
#         with urllib.request.urlopen(req, timeout=30) as response:
#             data = json.loads(response.read().decode())
#             msg = data.get("message", {})
#             customer_list = msg.get("customers", []) if isinstance(msg, dict) else msg

#             if not customer_list:
#                 log.info("[customer-sync] No customers in payload.")
#                 return

#             from models.customer import upsert_from_frappe
#             ok = err = 0
#             for cust in customer_list:
#                 try:
#                     upsert_from_frappe(cust)
#                     ok += 1
#                 except Exception as e:
#                     err += 1
#                     log.error("[customer-sync] Error: %s — %s", cust.get("customer_name"), e)

#             log.info("[customer-sync] Done — %d synced, %d errors.", ok, err)

#     except Exception as e:
#         log.error("[customer-sync] Network error: %s", e)


# # =============================================================================
# # BACKGROUND THREAD (PySide6)
# # =============================================================================

# try:
#     from PySide6.QtCore import QObject, QThread, Signal

#     class CustomerSyncWorker(QObject):
#         finished = Signal()

#         def run(self) -> None:
#             log.info("[customer-sync] Worker thread started (interval=%ds).", CUSTOMER_SYNC_INTERVAL)
#             while True:
#                 try:
#                     sync_customers()
#                 except Exception as exc:
#                     log.error("[customer-sync] Worker loop error: %s", exc)
#                 time.sleep(CUSTOMER_SYNC_INTERVAL)

#     def start_customer_sync_thread():
#         thread = QThread()
#         worker = CustomerSyncWorker()
#         worker.moveToThread(thread)
#         thread.started.connect(worker.run)
#         thread.worker = worker    # prevent GC
#         thread.start()
#         log.info("[customer-sync] Thread started.")
#         return thread

# except ImportError:
#     log.warning("PySide6 not found — background customer sync disabled.")

#     def start_customer_sync_thread():
#         import threading
#         t = threading.Thread(target=lambda: [sync_customers() or time.sleep(CUSTOMER_SYNC_INTERVAL)],
#                              daemon=True, name="CustomerSyncThread")
#         t.start()
#         return t


# if __name__ == "__main__":
#     import logging as _l
#     _l.basicConfig(level=_l.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
#     sync_customers()
# =============================================================================
# services/customer_sync_service.py
# (credentials delegated to services.credentials)
# Updated: now supports pagination + upsert_from_frappe
# =============================================================================

from __future__ import annotations

import json
import logging
import time
import urllib.request

log = logging.getLogger("CustomerSync")

CUSTOMER_SYNC_INTERVAL = 300   # 5 minutes
PAGE_LIMIT = 200               # pull up to 200 customers per sync cycle


def _get_credentials() -> tuple[str, str]:
    try:
        from services.credentials import get_credentials
        return get_credentials()
    except Exception:
        pass
    try:
        from database.db import get_connection
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute(
            "SELECT api_key, api_secret FROM companies "
            "WHERE id=(SELECT MIN(id) FROM companies)"
        )
        row = cur.fetchone()
        conn.close()
        if row and row[0]:
            return str(row[0]), str(row[1] or "")
    except Exception:
        pass
    return "", ""


def sync_customers():
    api_key, api_secret = _get_credentials()
    if not api_key or not api_secret:
        log.warning("[customer-sync] No credentials — skipping.")
        return

    from services.site_config import get_host as _gh
    base_url = _gh()

    ok = err = 0
    page = 1

    while True:
        url = (
            f"{base_url}/api/method/havano_pos_integration.api.get_customer"
            f"?page={page}&limit={PAGE_LIMIT}"
        )
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"token {api_key}:{api_secret}")

        try:
            log.info("[customer-sync] Fetching page %d…", page)
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode())
                msg  = data.get("message", {})
                customer_list = (
                    msg.get("customers", []) if isinstance(msg, dict) else msg
                )

                if not customer_list:
                    log.info("[customer-sync] No more customers on page %d.", page)
                    break

                from models.customer import upsert_from_frappe
                for cust in customer_list:
                    try:
                        upsert_from_frappe(cust)
                        ok += 1
                    except Exception as e:
                        err += 1
                        log.error(
                            "[customer-sync] Error: %s — %s",
                            cust.get("customer_name"), e,
                        )

                # If we got fewer than PAGE_LIMIT, we're on the last page
                if len(customer_list) < PAGE_LIMIT:
                    break
                page += 1

        except Exception as e:
            log.error("[customer-sync] Network error on page %d: %s", page, e)
            break

    log.info("[customer-sync] Done — %d synced, %d errors.", ok, err)


# =============================================================================
# BACKGROUND THREAD (PySide6)
# =============================================================================

try:
    from PySide6.QtCore import QObject, QThread, Signal

    class CustomerSyncWorker(QObject):
        finished = Signal()

        def run(self) -> None:
            log.info(
                "[customer-sync] Worker thread started (interval=%ds).",
                CUSTOMER_SYNC_INTERVAL,
            )
            while True:
                try:
                    sync_customers()
                except Exception as exc:
                    log.error("[customer-sync] Worker loop error: %s", exc)
                time.sleep(CUSTOMER_SYNC_INTERVAL)

    def start_customer_sync_thread():
        thread = QThread()
        worker = CustomerSyncWorker()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        thread.worker = worker    # prevent GC
        thread.start()
        log.info("[customer-sync] Thread started.")
        return thread

except ImportError:
    log.warning("PySide6 not found — background customer sync disabled.")

    def start_customer_sync_thread():
        import threading
        t = threading.Thread(
            target=lambda: [sync_customers() or time.sleep(CUSTOMER_SYNC_INTERVAL)],
            daemon=True,
            name="CustomerSyncThread",
        )
        t.start()
        return t


if __name__ == "__main__":
    import logging as _l
    _l.basicConfig(level=_l.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    sync_customers()