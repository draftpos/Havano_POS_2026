# # # =============================================================================
# # # services/customer_sync_service.py
# # # (credentials delegated to services.credentials)
# # # =============================================================================

# # from __future__ import annotations

# # import json
# # import logging
# # import time
# # import urllib.request

# # log = logging.getLogger("CustomerSync")

# # CUSTOMER_SYNC_INTERVAL = 300   # 5 minutes


# # def _get_credentials() -> tuple[str, str]:
# #     try:
# #         from services.credentials import get_credentials
# #         return get_credentials()
# #     except Exception:
# #         pass
# #     return "", ""


# # def sync_customers():
# #     api_key, api_secret = _get_credentials()
# #     if not api_key or not api_secret:
# #         log.warning("[customer-sync] No credentials — skipping.")
# #         return

# #     from services.site_config import get_host as _gh
# #     url = f"{_gh()}/api/method/havano_pos_integration.api.get_customer?page=1&limit=100"
# #     req = urllib.request.Request(url)
# #     req.add_header("Authorization", f"token {api_key}:{api_secret}")

# #     try:
# #         log.info("[customer-sync] Starting...")
# #         with urllib.request.urlopen(req, timeout=30) as response:
# #             data = json.loads(response.read().decode())
# #             msg = data.get("message", {})
# #             customer_list = msg.get("customers", []) if isinstance(msg, dict) else msg

# #             if not customer_list:
# #                 log.info("[customer-sync] No customers in payload.")
# #                 return

# #             from models.customer import upsert_from_frappe
# #             ok = err = 0
# #             for cust in customer_list:
# #                 try:
# #                     upsert_from_frappe(cust)
# #                     ok += 1
# #                 except Exception as e:
# #                     err += 1
# #                     log.error("[customer-sync] Error: %s — %s", cust.get("customer_name"), e)

# #             log.info("[customer-sync] Done — %d synced, %d errors.", ok, err)

# #     except Exception as e:
# #         log.error("[customer-sync] Network error: %s", e)


# # # =============================================================================
# # # BACKGROUND THREAD (PySide6)
# # # =============================================================================

# # try:
# #     from PySide6.QtCore import QObject, QThread, Signal

# #     class CustomerSyncWorker(QObject):
# #         finished = Signal()

# #         def run(self) -> None:
# #             log.info("[customer-sync] Worker thread started (interval=%ds).", CUSTOMER_SYNC_INTERVAL)
# #             while True:
# #                 try:
# #                     sync_customers()
# #                 except Exception as exc:
# #                     log.error("[customer-sync] Worker loop error: %s", exc)
# #                 time.sleep(CUSTOMER_SYNC_INTERVAL)

# #     def start_customer_sync_thread():
# #         thread = QThread()
# #         worker = CustomerSyncWorker()
# #         worker.moveToThread(thread)
# #         thread.started.connect(worker.run)
# #         thread.worker = worker    # prevent GC
# #         thread.start()
# #         log.info("[customer-sync] Thread started.")
# #         return thread

# # except ImportError:
# #     log.warning("PySide6 not found — background customer sync disabled.")

# #     def start_customer_sync_thread():
# #         import threading
# #         t = threading.Thread(target=lambda: [sync_customers() or time.sleep(CUSTOMER_SYNC_INTERVAL)],
# #                              daemon=True, name="CustomerSyncThread")
# #         t.start()
# #         return t


# # if __name__ == "__main__":
# #     import logging as _l
# #     _l.basicConfig(level=_l.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
# #     sync_customers()
# # =============================================================================
# # services/customer_sync_service.py
# # (credentials delegated to services.credentials)
# # Updated: now supports pagination + upsert_from_frappe
# # =============================================================================

# from __future__ import annotations

# import json
# import logging
# import time
# import urllib.request

# log = logging.getLogger("CustomerSync")

# CUSTOMER_SYNC_INTERVAL = 300   # 5 minutes
# PAGE_LIMIT = 200               # pull up to 200 customers per sync cycle


# def _get_credentials() -> tuple[str, str]:
#     try:
#         from services.credentials import get_credentials
#         return get_credentials()
#     except Exception:
#         pass
#     try:
#         from database.db import get_connection
#         conn = get_connection()
#         cur  = conn.cursor()
#         cur.execute(
#             "SELECT api_key, api_secret FROM companies "
#             "WHERE id=(SELECT MIN(id) FROM companies)"
#         )
#         row = cur.fetchone()
#         conn.close()
#         if row and row[0]:
#             return str(row[0]), str(row[1] or "")
#     except Exception:
#         pass
#     return "", ""


# def sync_customers():
#     api_key, api_secret = _get_credentials()
#     if not api_key or not api_secret:
#         log.warning("[customer-sync] No credentials — skipping.")
#         return

#     from services.site_config import get_host as _gh
#     base_url = _gh()

#     ok = err = 0
#     page = 1

#     while True:
#         url = (
#             f"{base_url}/api/method/havano_pos_integration.api.get_customer"
#             f"?page={page}&limit={PAGE_LIMIT}"
#         )
#         req = urllib.request.Request(url)
#         req.add_header("Authorization", f"token {api_key}:{api_secret}")

#         try:
#             log.info("[customer-sync] Fetching page %d…", page)
#             with urllib.request.urlopen(req, timeout=30) as response:
#                 data = json.loads(response.read().decode())
#                 msg  = data.get("message", {})
#                 customer_list = (
#                     msg.get("customers", []) if isinstance(msg, dict) else msg
#                 )

#                 if not customer_list:
#                     log.info("[customer-sync] No more customers on page %d.", page)
#                     break

#                 from models.customer import upsert_from_frappe
#                 for cust in customer_list:
#                     try:
#                         upsert_from_frappe(cust)
#                         ok += 1
#                     except Exception as e:
#                         err += 1
#                         log.error(
#                             "[customer-sync] Error: %s — %s",
#                             cust.get("customer_name"), e,
#                         )

#                 # If we got fewer than PAGE_LIMIT, we're on the last page
#                 if len(customer_list) < PAGE_LIMIT:
#                     break
#                 page += 1

#         except Exception as e:
#             log.error("[customer-sync] Network error on page %d: %s", page, e)
#             break

#     log.info("[customer-sync] Done — %d synced, %d errors.", ok, err)


# # =============================================================================
# # BACKGROUND THREAD (PySide6)
# # =============================================================================

# try:
#     from PySide6.QtCore import QObject, QThread, Signal

#     class CustomerSyncWorker(QObject):
#         finished = Signal()

#         def run(self) -> None:
#             log.info(
#                 "[customer-sync] Worker thread started (interval=%ds).",
#                 CUSTOMER_SYNC_INTERVAL,
#             )
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
#         t = threading.Thread(
#             target=lambda: [sync_customers() or time.sleep(CUSTOMER_SYNC_INTERVAL)],
#             daemon=True,
#             name="CustomerSyncThread",
#         )
#         t.start()
#         return t


# if __name__ == "__main__":
#     import logging as _l
#     _l.basicConfig(level=_l.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
#     sync_customers()

# =============================================================================
# services/customer_sync_service.py
# (credentials delegated to services.credentials)
# Updated: now supports pagination + correct mapping for Warehouse/Cost Center
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
    """Retrieves API keys from credentials service or fallback to DB."""
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
    """
    Fetches customers from Frappe in pages and upserts them into the local DB.
    Handles mapping for custom_warehouse and custom_cost_center.
    """
    api_key, api_secret = _get_credentials()
    if not api_key or not api_secret:
        log.warning("[customer-sync] No credentials — skipping.")
        return

    from services.site_config import get_host as _gh
    base_url = _gh()

    ok = err = 0
    page = 1

    log.info("[customer-sync] Starting sync cycle...")

    while True:
        # API call to the custom integration method
        url = (
            f"{base_url}/api/method/havano_pos_integration.api.get_customer"
            f"?page={page}&limit={PAGE_LIMIT}"
        )
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"token {api_key}:{api_secret}")

        try:
            log.info("[customer-sync] Fetching page %d...", page)
            with urllib.request.urlopen(req, timeout=30) as response:
                raw_data = response.read().decode()
                data = json.loads(raw_data)
                
                # Frappe usually wraps the result in 'message'
                msg = data.get("message", {})
                
                # Check if it's the dictionary structure you shared or a flat list
                if isinstance(msg, dict):
                    customer_list = msg.get("customers", [])
                else:
                    customer_list = msg

                if not customer_list:
                    log.info("[customer-sync] No more customers found on page %d.", page)
                    break

                from models.customer import upsert_from_frappe
                
                for cust in customer_list:
                    try:
                        # This function in models/customer.py handles the DB logic
                        upsert_from_frappe(cust)
                        ok += 1
                    except Exception as e:
                        err += 1
                        log.error(
                            "[customer-sync] Error processing '%s': %s",
                            cust.get("customer_name", "Unknown"), e
                        )

                # If the current page is not full, we have reached the end of the server list
                if len(customer_list) < PAGE_LIMIT:
                    break
                
                page += 1

        except Exception as e:
            log.error("[customer-sync] Network or Server error on page %d: %s", page, e)
            break

    log.info("[customer-sync] Finished. Successfully synced: %d, Errors: %d", ok, err)


# =============================================================================
# BACKGROUND THREAD (PySide6 / Threading Fallback)
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
        thread.worker = worker    # prevent garbage collection
        thread.start()
        log.info("[customer-sync] PySide6 Thread started.")
        return thread

except ImportError:
    log.warning("PySide6 not found — using standard threading for background sync.")

    def start_customer_sync_thread():
        import threading
        t = threading.Thread(
            target=lambda: [sync_customers() or time.sleep(CUSTOMER_SYNC_INTERVAL)],
            daemon=True,
            name="CustomerSyncThread",
        )
        t.start()
        log.info("[customer-sync] Standard Thread started.")
        return t


if __name__ == "__main__":
    # For testing the file standalone
    import logging as _l
    _l.basicConfig(level=_l.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    sync_customers()