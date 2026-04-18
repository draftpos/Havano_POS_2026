# =============================================================================
# services/sync_service.py  —  Product + GL Account + Mode of Payment Sync
# =============================================================================

import urllib.request
import urllib.error
import urllib.parse
import json
import logging

from database.db import get_connection, fetchone_dict
from services.site_config import get_host as _get_host

log = logging.getLogger("SyncService")

API_BASE_URL      = _get_host()
PRODUCTS_ENDPOINT = f"{API_BASE_URL}/api/method/havano_pos_integration.api.get_products"
PAGE_SIZE         = 100
MAX_PAGES         = 200


# =============================================================================
# PUBLIC — called on login and by SyncWorker
# =============================================================================

def sync_from_login_response(login_data: dict) -> dict:
    token_string = login_data.get("token_string", "")
    api_key = api_secret = ""
    if token_string and ":" in token_string:
        api_key, api_secret = token_string.split(":", 1)

    result = sync_products(api_key=api_key, api_secret=api_secret)

    # Also sync GL accounts and MOPs on every login
    try:
        from models.company_defaults import get_defaults
        company = (get_defaults() or {}).get("server_company", "")
        host    = _get_host()

        gl_count  = sync_gl_accounts(api_key, api_secret, host, company)
        mop_count = sync_modes_of_payment(api_key, api_secret, host, company)

        # Sync exchange rates immediately after GL accounts are loaded
        # (GL accounts give us the list of currencies we need rates for)
        rate_count = sync_exchange_rates(api_key, api_secret, host)

        result["gl_accounts_synced"]      = gl_count
        result["modes_of_payment_synced"] = mop_count
        result["exchange_rates_synced"]   = rate_count
    except Exception as e:
        log.warning("GL/MOP/rates sync during login failed: %s", e)
        result["gl_accounts_synced"]      = 0
        result["modes_of_payment_synced"] = 0
        result["exchange_rates_synced"]   = 0

    # Pharmacy reference data — best-effort, never blocks login.
    # Runs in the foreground here (same as GL/MOP above) but swallows all errors.
    try:
        from services.doctor_sync_service import sync_doctors
        from services.dosage_sync_service import sync_dosages
        doc_res = sync_doctors()
        dos_res = sync_dosages()
        result["doctors_synced"] = doc_res.get("synced", 0)
        result["dosages_synced"] = dos_res.get("synced", 0)
        print(f"[sync] ✅ Doctors synced: {result['doctors_synced']} | "
              f"Dosages synced: {result['dosages_synced']}")
    except Exception as e:
        log.warning("Doctor/Dosage sync during login failed: %s", e)
        result["doctors_synced"] = 0
        result["dosages_synced"] = 0

    return result


# =============================================================================
# GL ACCOUNT SYNC
# =============================================================================

def sync_gl_accounts(api_key: str, api_secret: str,
                     host: str, company: str) -> int:
    """
    Fetches ONLY Cash and Bank accounts from Frappe Chart of Accounts.
    Makes two separate requests (one for Cash, one for Bank).
    """
    from models.gl_account import upsert_account

    account_types_to_sync = ["Cash", "Bank"]
    all_accounts = []
    
    for account_type in account_types_to_sync:
        fields = json.dumps([
            "name", "account_name", "account_number",
            "company", "parent_account", "account_type", "account_currency",
            "is_group"
        ])
        
        filters = json.dumps([
            ["company", "=", company],
            ["account_type", "=", account_type]
        ])

        url = (
            f"{host}/api/resource/Account"
            f"?fields={urllib.parse.quote(fields)}"
            f"&filters={urllib.parse.quote(filters)}"
            f"&limit_page_length=500"
        )

        req = urllib.request.Request(url)
        req.add_header("Authorization", f"token {api_key}:{api_secret}")

        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                accounts = json.loads(r.read().decode()).get("data", [])
                all_accounts.extend(accounts)
                log.debug(f"Fetched {len(accounts)} {account_type} accounts")
        except Exception as e:
            log.warning(f"Failed to fetch {account_type} accounts: {e}")

    count = 0
    for acct in all_accounts:
        try:
            upsert_account({
                "name":             acct.get("name", ""),
                "account_name":     acct.get("account_name", ""),
                "account_number":   acct.get("account_number"),
                "company":          acct.get("company", company),
                "parent_account":   acct.get("parent_account", ""),
                "account_type":     acct.get("account_type", ""),
                "account_currency": acct.get("account_currency", "USD"),
            })
            count += 1
        except Exception as e:
            log.warning("Failed to upsert GL account '%s': %s", acct.get("name"), e)

    log.info(f"GL accounts synced (Cash/Bank only): {count}")
    print(f"[sync] ✅ GL accounts synced (Cash/Bank only): {count}")
    return count

# =============================================================================
# EXCHANGE RATE SYNC
# =============================================================================

def sync_exchange_rates(api_key: str, api_secret: str, host: str) -> int:
    """
    For each non-base currency found in gl_accounts, fetches today's
    exchange rate from Frappe and stores BOTH directions locally:
      - curr → base  (e.g. ZWD → USD = 0.00277)
      - base → curr  (e.g. USD → ZWD = 361.01)

    Storing both directions means the payment dialog can always resolve
    the correct rate regardless of which direction it queries.

    Returns count of currency pairs synced.
    """
    import urllib.parse as _up
    from datetime import date as _date
    from models.exchange_rate import upsert_rate

    # Resolve base currency from company defaults
    base_curr = "USD"
    try:
        from models.company_defaults import get_defaults
        d = get_defaults() or {}
        base_curr = d.get("server_company_currency", "USD").strip().upper() or "USD"
    except Exception:
        pass

    # Collect all non-base currencies from gl_accounts
    try:
        from models.gl_account import get_all_accounts
        accounts = get_all_accounts() or []
        currencies = {
            (a.get("account_currency") or "").upper()
            for a in accounts
            if (a.get("account_currency") or "").upper() not in ("", base_curr)
        }
    except Exception as e:
        log.warning("[rates] Could not load GL accounts for rate sync: %s", e)
        return 0

    if not currencies:
        log.info("[rates] No non-base currencies found — skipping rate sync.")
        return 0

    today = _date.today().isoformat()
    count = 0

    for curr in sorted(currencies):
        try:
            url = (
                f"{host}/api/method/erpnext.setup.utils.get_exchange_rate"
                f"?from_currency={_up.quote(curr)}"
                f"&to_currency={_up.quote(base_curr)}"
                f"&transaction_date={today}"
            )
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"token {api_key}:{api_secret}")

            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode())

            rate = float(data.get("message") or data.get("result") or 0)

            if rate > 0:
                # Store curr → base  (e.g. ZWD → USD)
                upsert_rate(curr, base_curr, rate, today)
                # Store base → curr  (e.g. USD → ZWD) so dialog can look either way
                upsert_rate(base_curr, curr, round(1.0 / rate, 8), today)
                count += 1
                log.info("[rates] %s → %s = %.8f  (1 %s = %.4f %s)",
                         curr, base_curr, rate, base_curr, 1.0 / rate, curr)
                print(f"[sync] ✅ Rate synced: 1 {curr} = {rate:.8f} {base_curr}  "
                      f"(1 {base_curr} = {1.0/rate:,.4f} {curr})")
            else:
                log.warning("[rates] Zero/null rate returned for %s → %s", curr, base_curr)
                print(f"[sync] ⚠  No rate returned for {curr} → {base_curr}")

        except Exception as e:
            log.error("[rates] Failed to fetch rate for %s → %s: %s", curr, base_curr, e)
            print(f"[sync] ❌ Rate fetch failed for {curr} → {base_curr}: {e}")

    log.info("[rates] ✅ %d exchange rate pair(s) synced (base=%s).", count, base_curr)
    return count


# =============================================================================
# MODE OF PAYMENT SYNC
# =============================================================================

def sync_modes_of_payment(api_key: str, api_secret: str,
                           host: str, company: str) -> int:
    """
    Fetches all enabled Modes of Payment from saas_api (ignore_permissions) and
    stores them locally. Single round-trip — the endpoint pre-filters the
    accounts child rows to the requested company and resolves the account
    currency server-side. Returns count of MOP records successfully synced.

    The older implementation hit /api/resource/Mode of Payment directly, which
    runs under the caller's session and 403s for any role (e.g. Pharmacist)
    that lacks read perm on the Mode of Payment doctype. The saas_api endpoint
    bypasses that check since this is internal master-data refresh.
    """
    from models.gl_account import upsert_mop

    url = (
        f"{host}/api/method/saas_api.www.api.get_modes_of_payment"
        f"?company={urllib.parse.quote(company or '')}"
    )
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"token {api_key}:{api_secret}")

    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            payload = json.loads(r.read().decode())
    except Exception as e:
        log.warning("MOP list fetch failed: %s", e)
        return 0

    msg = payload.get("message") or payload
    mop_list = (msg or {}).get("data") or []

    count = 0
    for mop in mop_list:
        mop_name = (mop.get("name") or "").strip()
        if not mop_name:
            continue
        try:
            currency = (mop.get("account_currency") or "USD").strip().upper() or "USD"
            upsert_mop({
                "name":             mop_name,
                "mop_type":         mop.get("type") or "Cash",
                "company":          mop.get("company") or company,
                "gl_account":       mop.get("default_account") or "",
                "account_currency": currency,
            })
            log.debug("MOP synced: %s → %s (%s)",
                      mop_name, mop.get("default_account", ""), currency)
            count += 1
        except Exception as e:
            log.warning("Failed to upsert MOP '%s': %s", mop_name, e)

    log.info("Modes of Payment synced: %d", count)
    print(f"[sync] ✅ Modes of Payment synced: {count}")
    return count


# =============================================================================
# PRODUCT SYNC
# =============================================================================

def sync_products(api_key: str = "", api_secret: str = "",
                  page: int = None) -> dict:
    result = {
        "products_synced":   0,
        "products_inserted": 0,
        "products_updated":  0,
        "skipped":           0,
        "total_api":         0,
        "pages_fetched":     0,
        "errors":            [],
    }

    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if api_key and api_secret:
        headers["Authorization"] = f"token {api_key}:{api_secret}"

    current_page = 1
    while True:
        url = f"{PRODUCTS_ENDPOINT}?page={current_page}&limit={PAGE_SIZE}"
        print(f"[sync] Fetching page {current_page}: {url}")

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode()[:200]
            except Exception:
                pass
            result["errors"].append(f"HTTP {e.code} on page {current_page}: {body}")
            break
        except Exception as e:
            result["errors"].append(f"Network error on page {current_page}: {e}")
            break

        message    = payload.get("message") or {}
        products   = message.get("products") or []
        pagination = message.get("pagination") or {}

        if not products:
            if current_page == 1:
                result["errors"].append(
                    f"API returned 0 products on page 1. "
                    f"Response keys: {list(payload.keys())}. "
                    f"message keys: {list(message.keys()) if isinstance(message, dict) else type(message).__name__}"
                )
            break

        result["pages_fetched"] += 1
        result["total_api"] = int(pagination.get("total_count") or 0)
        total_pages = int(pagination.get("total_pages") or 1)
        has_next    = bool(pagination.get("has_next_page"))

        print(f"[sync]   {len(products)} products on page {current_page}/{total_pages}")

        for raw in products:
            item_code = str(raw.get("itemcode") or "").strip()
            if not item_code:
                result["skipped"] += 1
                continue
            try:
                inserted = _upsert_product(raw)
                result["products_synced"] += 1
                if inserted:
                    result["products_inserted"] += 1
                else:
                    result["products_updated"] += 1
            except Exception as e:
                result["skipped"] += 1
                err_msg = f"{item_code}: {e}"
                result["errors"].append(err_msg)
                if result["skipped"] <= 5:
                    print(f"[sync] ❌ {err_msg}")

        if page is not None:
            break
        if not has_next or current_page >= total_pages or current_page >= MAX_PAGES:
            break
        current_page += 1

    print(
        f"[sync] ✅ Done — "
        f"{result['products_inserted']} inserted, "
        f"{result['products_updated']} updated, "
        f"{result['skipped']} skipped "
        f"({result['pages_fetched']} page(s) fetched of {result['total_api']} total API records)"
    )
    return result


# =============================================================================
# PRIVATE — product upsert helpers
# =============================================================================

def _upsert_product(raw: dict) -> bool:
    part_no = str(raw.get("itemcode") or "").strip().upper()
    name    = _clean_text(str(raw.get("itemname") or part_no))[:255]
    group   = str(raw.get("groupname") or "")[:100]
    uom     = str((raw.get("uom") or {}).get("stock_uom") or "Nos").strip()

    stock = 0.0
    for wh in (raw.get("warehouses") or []):
        try:
            stock += float(wh.get("qtyOnHand") or 0)
        except (TypeError, ValueError):
            pass

    server_price = 0.0
    for p in (raw.get("prices") or []):
        if str(p.get("type") or "").lower() == "selling":
            try:
                v = float(p.get("price") or 0)
                if v > server_price:
                    server_price = v
            except (TypeError, ValueError):
                pass

    category = group if group not in ("All Item Groups", "") else ""

    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("SELECT id, price FROM products WHERE part_no = ?", (part_no,))
        existing = fetchone_dict(cur)

        if existing:
            local_price = float(existing.get("price") or 0)
            new_price   = server_price if server_price > 0 else local_price
            cur.execute("""
                UPDATE products
                SET name     = ?,
                    stock    = ?,
                    uom      = ?,
                    price    = ?,
                    category = CASE WHEN ? <> '' THEN ? ELSE category END
                WHERE part_no = ?
            """, (name, stock, uom, new_price, category, category, part_no))
            conn.commit()
            _upsert_uom_prices(cur, part_no, raw.get("prices") or [])
            conn.commit()
            return False
        else:
            cur.execute("""
                INSERT INTO products
                    (part_no, name, price, stock, category,
                     uom, conversion_factor,
                     order_1, order_2, order_3, order_4, order_5, order_6)
                VALUES (?, ?, ?, ?, ?, ?, 1.0, 0, 0, 0, 0, 0, 0)
            """, (part_no, name, server_price, stock, category, uom))
            conn.commit()
            _upsert_uom_prices(cur, part_no, raw.get("prices") or [])
            conn.commit()
            return True
    finally:
        conn.close()


def _upsert_uom_prices(cur, part_no: str, prices: list) -> None:
    try:
        cur.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_NAME = 'product_uom_prices'
            )
            CREATE TABLE product_uom_prices (
                id      INT           IDENTITY(1,1) PRIMARY KEY,
                part_no NVARCHAR(50)  NOT NULL,
                uom     NVARCHAR(40)  NOT NULL,
                price   DECIMAL(12,2) NOT NULL DEFAULT 0,
                CONSTRAINT UQ_product_uom UNIQUE (part_no, uom)
            )
        """)
    except Exception:
        pass

    seen = set()
    for p in prices:
        if str(p.get("type") or "").lower() != "selling":
            continue
        uom_name  = str(p.get("uom") or "Nos").strip()
        uom_price = float(p.get("price") or 0)
        if not uom_name or uom_price <= 0 or uom_name in seen:
            continue
        seen.add(uom_name)
        try:
            cur.execute("""
                MERGE product_uom_prices AS target
                USING (SELECT ? AS part_no, ? AS uom) AS src
                    ON target.part_no = src.part_no
                   AND target.uom     = src.uom
                WHEN MATCHED THEN
                    UPDATE SET price = ?
                WHEN NOT MATCHED THEN
                    INSERT (part_no, uom, price) VALUES (?, ?, ?);
            """, (part_no, uom_name, uom_price, part_no, uom_name, uom_price))
        except Exception:
            pass


def _clean_text(text: str) -> str:
    if not text:
        return ""
    return (
        text
        .replace("&amp;",  "&")
        .replace("&lt;",   "<")
        .replace("&gt;",   ">")
        .replace("&quot;", '"')
        .replace("&#39;",  "'")
        .strip()
    )


# =============================================================================
# UI helper
# =============================================================================

def format_sync_result(result: dict) -> str:
    if not result:
        return "No sync performed."
    if "error" in result and not result.get("products_synced"):
        return f"❌ Sync failed: {result['error']}"
    lines = [
        f"✅ Sync complete  ({result.get('total_api', 0)} products on server)",
        f"   • {result.get('products_inserted', 0)} new products added",
        f"   • {result.get('products_updated',  0)} products updated",
    ]
    if result.get("skipped"):
        lines.append(f"   • {result['skipped']} skipped")
    if result.get("gl_accounts_synced") is not None:
        lines.append(f"   • {result['gl_accounts_synced']} GL accounts synced")
    if result.get("modes_of_payment_synced") is not None:
        lines.append(f"   • {result['modes_of_payment_synced']} modes of payment synced")
    if result.get("exchange_rates_synced") is not None:
        lines.append(f"   • {result['exchange_rates_synced']} exchange rate(s) synced")
    if result.get("errors"):
        lines.append(f"   ⚠  {result['errors'][0]}")
    return "\n".join(lines)


# =============================================================================
# SyncWorker — runs on login via QThread
# =============================================================================

PRODUCT_SYNC_INTERVAL_SECONDS = 15    # Aggressive Sync: 15 seconds
GL_MOP_SYNC_INTERVAL_SECONDS = 600   # Sync GL/MOP/Rates every 10 minutes

import time as _time

try:
    from PySide6.QtCore import QObject  # type: ignore

    class SyncWorker(QObject):
        """
        Background daemon that keeps products and stock in sync with Frappe.
        Runs continuously in a loop every PRODUCT_SYNC_INTERVAL_SECONDS.
        Also triggers sale upload retries after each successful stock pull.
        """

        def run(self) -> None:
            import subprocess
            import sys
            import os
            import time as _time_internal
            
            log.info("[sync] Aggressive Product Sync Worker started (interval=%ds)", 
                     PRODUCT_SYNC_INTERVAL_SECONDS)
            
            last_gl_sync = 0.0
            
            while True:
                try:
                    # 1. Product + tax sync via existing windows service script
                    _here  = os.path.dirname(os.path.abspath(__file__))
                    script = os.path.join(_here, "product_sync_windows_service.py")

                    if not os.path.exists(script):
                        log.error("[sync] Cannot find product_sync_windows_service.py at %s", script)
                    else:
                        # log.debug("[sync] Running product + tax sync...")
                        try:
                            # Use 'debug' argument to run once. 
                            # We manage the loop here for higher reliability.
                            subprocess.run(
                                [sys.executable, script, "debug"],
                                capture_output=True,
                                text=True,
                                timeout=120,
                                cwd=_here,
                            )
                        except subprocess.TimeoutExpired:
                            log.error("[sync] product+tax sync timed out after 120s")
                        except Exception as e:
                            log.error("[sync] product+tax sync error: %s", e)

                    # 2. GL accounts + MOP sync — runs less frequently
                    now = _time_internal.time()
                    if now - last_gl_sync > GL_MOP_SYNC_INTERVAL_SECONDS:
                        try:
                            from services.credentials import get_credentials
                            from models.company_defaults import get_defaults

                            api_key, api_secret = get_credentials()
                            host    = _get_host()
                            company = (get_defaults() or {}).get("server_company", "")

                            if api_key and api_secret:
                                sync_gl_accounts(api_key, api_secret, host, company)
                                sync_modes_of_payment(api_key, api_secret, host, company)
                                sync_exchange_rates(api_key, api_secret, host)
                                last_gl_sync = now
                                log.info("[sync] Hourly GL/MOP/Rates sync complete.")
                        except Exception as e:
                            log.error("[sync] GL/MOP/rates sync error: %s", e)

                    # 3. RETRY TRIGGER: Attempt to push unsynced sales right away
                    # Since stock might have just been updated locally, we kick 
                    # the upload service to try and recover any failed sales.
                    try:
                        from services.pos_upload_service import push_unsynced_sales
                        push_unsynced_sales()
                    except Exception as e:
                        log.error("[sync] Auto-recovery upload trigger failed: %s", e)

                except Exception as e:
                    log.error("[sync] Unexpected error in SyncWorker loop: %s", e)
                
                _time_internal.sleep(PRODUCT_SYNC_INTERVAL_SECONDS)

except ImportError:
    class SyncWorker:          # type: ignore[no-redef]
        """Stub used when PySide6 is unavailable."""
        def run(self) -> None:
            pass


# =============================================================================
# Backwards-compat shim
# =============================================================================

def _read_credentials() -> tuple:
    import os
    try:
        from services.credentials import get_credentials
        k, s = get_credentials()
        if k and s:
            return k, s
    except Exception:
        pass
    return (
        os.environ.get("HAVANO_API_KEY",    ""),
        os.environ.get("HAVANO_API_SECRET", ""),
    )