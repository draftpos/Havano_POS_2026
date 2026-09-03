# # =============================================================================
# # services/laybye_payment_entry_service.py
# #
# # Records laybye deposit Payment Entries in a local queue table,
# # then syncs them to Frappe via /api/resource/Payment Entry.
# #
# # Payload sent — exactly this, nothing more:
# # {
# #   "doctype":                    "Payment Entry",
# #   "payment_type":               "Receive",
# #   "party_type":                 "Customer",
# #   "party":                      "<customer_name>",
# #   "party_name":                 "<customer_name>",
# #   "paid_to":                    "<cash_account from company_defaults>",
# #   "paid_to_account_currency":   "USD",
# #   "paid_from_account_currency": "USD",
# #   "paid_amount":                150.75,
# #   "paid_amount_after_tax":      150.75,
# #   "received_amount":            150.75,
# #   "received_amount_after_tax":  150.75,
# #   "reference_no":               "<deposit_method or order_no>",
# #   "reference_date":             "2026-03-25",
# #   "remarks":                    "Laybye deposit — SO-0042",
# #   "docstatus":                  1,
# #   "references":                 []
# # }
# #
# # No Sales Order lookup. No GL account search. No reference linking.
# # =============================================================================

# from __future__ import annotations
# import logging
# import requests
# from datetime import date, datetime

# log = logging.getLogger("laybye_payment_entry_service")


# # =============================================================================
# # Helpers
# # =============================================================================

# def _get_conn():
#     from database.db import get_connection
#     return get_connection()


# def _get_credentials() -> tuple[str, str]:
#     """Return (api_key, api_secret) from company_defaults."""
#     try:
#         from models.company_defaults import get_defaults
#         d = get_defaults() or {}
#         return d.get("api_key", ""), d.get("api_secret", "")
#     except Exception:
#         return "", ""


# def _get_host() -> str:
#     """Return the base Frappe URL, e.g. https://erp.mycompany.com"""
#     try:
#         from services.site_config import get_host_label
#         host = get_host_label()
#         if host and not host.startswith("http"):
#             host = "https://" + host
#         return host.rstrip("/")
#     except Exception:
#         return ""


# def _get_cash_account() -> str:
#     """
#     Return the 'paid_to' account name from company_defaults.
#     Add a column called  cash_account  to company_defaults and set it to
#     the exact account name in Frappe, e.g. "Cash - AT".
#     Falls back to "Cash" if not configured.
#     """
#     try:
#         from models.company_defaults import get_defaults
#         d = get_defaults() or {}
#         return d.get("cash_account", "") or "Cash"
#     except Exception:
#         return "Cash"


# def _round2(val) -> float:
#     return round(float(val or 0), 2)


# # =============================================================================
# # Local queue table
# # =============================================================================

# def _ensure_table():
#     """Create laybye_payment_entries table if it does not exist."""
#     conn = _get_conn()
#     cur  = conn.cursor()
#     cur.execute(
#         "SELECT 1 FROM sys.objects "
#         "WHERE object_id = OBJECT_ID('laybye_payment_entries') AND type = 'U'"
#     )
#     if cur.fetchone() is None:
#         cur.execute("""
#             CREATE TABLE laybye_payment_entries (
#                 id               INT           PRIMARY KEY IDENTITY(1,1),
#                 sales_order_id   INT           NOT NULL,
#                 order_no         NVARCHAR(100) NOT NULL DEFAULT '',
#                 customer_name    NVARCHAR(255) NOT NULL DEFAULT '',
#                 deposit_amount   FLOAT         NOT NULL DEFAULT 0,
#                 deposit_method   NVARCHAR(100) NOT NULL DEFAULT '',
#                 frappe_pe_ref    NVARCHAR(255) NOT NULL DEFAULT '',
#                 status           NVARCHAR(50)  NOT NULL DEFAULT 'pending',
#                 sync_attempts    INT           NOT NULL DEFAULT 0,
#                 created_at       NVARCHAR(50)  NOT NULL DEFAULT '',
#                 last_attempt_at  NVARCHAR(50)  NOT NULL DEFAULT '',
#                 error_message    NVARCHAR(MAX) NOT NULL DEFAULT ''
#             )
#         """)
#         conn.commit()
#         log.info("Created table: laybye_payment_entries")
#     return conn


# # =============================================================================
# # Public API
# # =============================================================================

# def create_laybye_payment_entry(order: dict) -> int | None:
#     """
#     Queue a laybye deposit for sync.
#     Call this immediately after create_sales_order() or add_deposit_payment().
#     Returns the new queue row id, or None if nothing to queue.
#     """
#     if not order:
#         return None

#     deposit_amount = _round2(order.get("deposit_amount") or 0)
#     if deposit_amount <= 0:
#         return None

#     try:
#         conn = _ensure_table()
#         cur  = conn.cursor()
#         cur.execute("""
#             INSERT INTO laybye_payment_entries
#                 (sales_order_id, order_no, customer_name,
#                  deposit_amount, deposit_method, status, created_at)
#             OUTPUT INSERTED.id
#             VALUES (?, ?, ?, ?, ?, 'pending', ?)
#         """, (
#             int(order["id"]),
#             order.get("order_no") or "",
#             order.get("customer_name") or "Walk-in Customer",
#             deposit_amount,
#             order.get("deposit_method") or "",
#             datetime.now().isoformat(timespec="seconds"),
#         ))
#         pe_id = cur.fetchone()[0]
#         conn.commit()
#         log.info("Queued laybye PE id=%d  order=%s  amount=%.2f",
#                  pe_id, order.get("order_no"), deposit_amount)
#         return pe_id
#     except Exception as exc:
#         log.error("create_laybye_payment_entry failed: %s", exc)
#         return None


# def sync_laybye_payment_entries():
#     """
#     Push all pending/retry entries to Frappe.
#     Stops after 5 failed attempts per entry.
#     """
#     try:
#         conn = _ensure_table()
#         cur  = conn.cursor()
#         cur.execute("""
#             SELECT id, order_no, customer_name,
#                    deposit_amount, deposit_method, sync_attempts
#             FROM   laybye_payment_entries
#             WHERE  status IN ('pending', 'retry')
#             AND    sync_attempts < 5
#             ORDER  BY id ASC
#         """)
#         rows = cur.fetchall()
#         cols = [d[0] for d in cur.description]
#         pending = [dict(zip(cols, r)) for r in rows]
#     except Exception as exc:
#         log.error("sync — DB read failed: %s", exc)
#         return

#     if not pending:
#         return

#     api_key, api_secret = _get_credentials()
#     host = _get_host()
#     if not api_key or not host:
#         log.warning("sync — missing api_key or host, skipping")
#         return

#     cash_account = _get_cash_account()

#     for pe in pending:
#         _sync_single(pe, api_key, api_secret, host, cash_account)


# def _sync_single(pe: dict, api_key: str, api_secret: str,
#                  host: str, cash_account: str):
#     """POST a single clean Payment Entry to Frappe."""
#     pe_id  = pe["id"]
#     conn   = _get_conn()
#     amount = _round2(pe.get("deposit_amount"))

#     # ── exact payload — matches your working example ──────────────────────────
#     payload = {
#         "doctype":                    "Payment Entry",
#         "payment_type":               "Receive",
#         "party_type":                 "Customer",
#         "party":                      pe.get("customer_name") or "Walk-in Customer",
#         "party_name":                 pe.get("customer_name") or "Walk-in Customer",
#         "paid_to":                    cash_account,
#         "paid_to_account_currency":   "USD",
#         "paid_from_account_currency": "USD",
#         "paid_amount":                amount,
#         "paid_amount_after_tax":      amount,
#         "received_amount":            amount,
#         "received_amount_after_tax":  amount,
#         "reference_no":               pe.get("deposit_method") or pe.get("order_no") or "Laybye",
#         "reference_date":             date.today().isoformat(),
#         "remarks":                    f"Laybye deposit — {pe.get('order_no')}" if pe.get("order_no") else "Laybye deposit",
#         "docstatus":                  1,
#         "references":                 [],
#     }

#     url     = f"{host}/api/resource/Payment Entry"
#     headers = {
#         "Authorization": f"token {api_key}:{api_secret}",
#         "Content-Type":  "application/json",
#     }

#     # mark attempt
#     try:
#         conn.execute(
#             "UPDATE laybye_payment_entries "
#             "SET sync_attempts = sync_attempts + 1, last_attempt_at = ? "
#             "WHERE id = ?",
#             (datetime.now().isoformat(timespec="seconds"), pe_id)
#         )
#         conn.commit()
#     except Exception as exc:
#         log.warning("Could not increment attempt counter for PE %d: %s", pe_id, exc)

#     # fire
#     response = None
#     try:
#         response = requests.post(url, json=payload, headers=headers, timeout=30)
#         response.raise_for_status()

#         frappe_name = response.json().get("data", {}).get("name", "")
#         conn.execute(
#             "UPDATE laybye_payment_entries "
#             "SET status = 'synced', frappe_pe_ref = ?, error_message = '' "
#             "WHERE id = ?",
#             (frappe_name, pe_id)
#         )
#         conn.commit()
#         log.info("✅ PE %d synced → %s", pe_id, frappe_name)

#     except Exception as exc:
#         err = response.text[:500] if response is not None else str(exc)[:500]
#         log.error("❌ PE %d failed: %s", pe_id, err)
#         attempts = int(pe.get("sync_attempts", 0)) + 1
#         new_status = "failed" if attempts >= 5 else "retry"
#         try:
#             conn.execute(
#                 "UPDATE laybye_payment_entries "
#                 "SET status = ?, error_message = ?, last_attempt_at = ? "
#                 "WHERE id = ?",
#                 (new_status, err, datetime.now().isoformat(timespec="seconds"), pe_id)
#             )
#             conn.commit()
#         except Exception as db_exc:
#             log.error("Could not update failure status for PE %d: %s", pe_id, db_exc)


# # =============================================================================
# # Background sync daemon  (call once at app startup)
# # =============================================================================

# def start_laybye_pe_sync_daemon():
#     """Retry pending payment entries every 60 seconds in a background thread."""
#     import threading
#     import time

#     def _loop():
#         while True:
#             try:
#                 sync_laybye_payment_entries()
#             except Exception as exc:
#                 log.error("Daemon error: %s", exc)
#             time.sleep(60)

#     t = threading.Thread(target=_loop, daemon=True, name="laybye_pe_sync")
#     t.start()
#     log.info("Laybye PE sync daemon started.")