import time
import traceback
from services.credentials import get_credentials
from services.site_config import get_host
from models.company_defaults import get_defaults

from services.user_sync_service import sync_users
from services.customer_sync_service import sync_customers
from services.product_sync_windows_service import sync_products_smart
from services.bundle_sync_service import pull_all_bundles
from services.sync_service import sync_exchange_rates, sync_gl_accounts, sync_modes_of_payment
from models.user import migrate as ensure_default_users

def sync_everything():
    """
    Master orchestrator for syncing all core entities from the Frappe server.
    Ensures that users, customers, products, bundles, exchange rates, GL accounts,
    and modes of payment are synchronized, and logs heavily to the terminal.
    """
    print("==================================================", flush=True)
    print("[sync_all] STARTING FULL SYNC FROM SERVER", flush=True)
    print("==================================================", flush=True)
    
    key, secret = get_credentials()
    if not key:
        print("[sync_all] ERROR: No credentials found! Log in to authenticate.", flush=True)
        return {"errors": 1, "inserted": 0, "updated": 0, "total_api": 0}
        
    host = get_host()
    defaults = get_defaults() or {}
    company = defaults.get("server_company", "")
    
    total_inserted = 0
    total_updated = 0
    total_api = 0
    total_errors = 0

    # 1. Sync Users
    print("\n[sync_all] ---> 1. Syncing Users...", flush=True)
    try:
        user_res = sync_users()
        if user_res:
            u_upd = user_res.get("synced", 0)
            u_err = user_res.get("errors", 0)
            total_updated += u_upd
            total_api += u_upd
            total_errors += u_err
            print(f"[sync_all] Users synced: {u_upd} synced, {u_err} errors.", flush=True)
        else:
            print("[sync_all] User sync returned None.", flush=True)
    except Exception as e:
        print(f"[sync_all] ERROR syncing users: {e}", flush=True)
        total_errors += 1

    # 2. Sync Customers
    print("\n[sync_all] ---> 2. Syncing Customers...", flush=True)
    try:
        cust_res = sync_customers()
        if cust_res:
            c_ins = cust_res.get("inserted", 0)
            c_upd = cust_res.get("updated", 0)
            total_inserted += c_ins
            total_updated += c_upd
            total_api += (c_ins + c_upd)
            print(f"[sync_all] Customers synced: {c_ins} inserted, {c_upd} updated.", flush=True)
        else:
            print("[sync_all] Customer sync returned None.", flush=True)
    except Exception as e:
        print(f"[sync_all] ERROR syncing customers: {e}", flush=True)
        total_errors += 1

    # 3. Sync Products
    print("\n[sync_all] ---> 3. Syncing Products...", flush=True)
    try:
        prod_res = sync_products_smart(key, secret)
        if prod_res:
            p_ins = prod_res.get("inserted", 0)
            p_upd = prod_res.get("updated", 0)
            p_tot = prod_res.get("total_api", p_ins + p_upd)
            total_inserted += p_ins
            total_updated += p_upd
            total_api += p_tot
            print(f"[sync_all] Products synced: {p_ins} inserted, {p_upd} updated (of {p_tot}).", flush=True)
        else:
            print("[sync_all] Product sync returned None.", flush=True)
    except Exception as e:
        print(f"[sync_all] ERROR syncing products: {e}", flush=True)
        total_errors += 1

    # 4. Sync Product Bundles
    print("\n[sync_all] ---> 4. Syncing Product Bundles...", flush=True)
    try:
        bun_res = pull_all_bundles()
        if bun_res:
            b_ins = bun_res.get("saved", 0)
            b_upd = bun_res.get("skipped", 0)
            total_inserted += b_ins
            total_updated += b_upd
            total_api += bun_res.get("total", b_ins + b_upd)
            print(f"[sync_all] Bundles synced: {b_ins} inserted, {b_upd} updated.", flush=True)
        else:
            print("[sync_all] Bundle sync returned None.", flush=True)
    except Exception as e:
        print(f"[sync_all] ERROR syncing bundles: {e}", flush=True)
        total_errors += 1
        
    # 5. Sync GL Accounts
    print(f"\n[sync_all] ---> 5. Syncing GL Accounts for {company or 'default'}...", flush=True)
    try:
        gls = sync_gl_accounts(key, secret, host, company)
        total_updated += gls
        total_api += gls
        print(f"[sync_all] GL accounts synced: {gls}", flush=True)
    except Exception as e:
        print(f"[sync_all] ERROR syncing GL accounts: {e}", flush=True)
        total_errors += 1

    # 6. Sync Modes of Payment
    print(f"\n[sync_all] ---> 6. Syncing Modes of Payment for {company or 'default'}...", flush=True)
    try:
        mops = sync_modes_of_payment(key, secret, host, company)
        total_updated += mops
        total_api += mops
        print(f"[sync_all] Modes of Payment synced: {mops}", flush=True)
    except Exception as e:
        print(f"[sync_all] ERROR syncing Modes of Payment: {e}", flush=True)
        total_errors += 1

    # 7. Sync Exchange Rates
    print("\n[sync_all] ---> 7. Syncing Exchange Rates...", flush=True)
    try:
        rates = sync_exchange_rates(key, secret, host, _force=True)
        total_updated += rates
        total_api += rates
        print(f"[sync_all] Exchange rates synced: {rates}", flush=True)
    except Exception as e:
        print(f"[sync_all] ERROR syncing exchange rates: {e}", flush=True)
        total_errors += 1

    # 8. Ensure Default Local Users
    print("\n[sync_all] ---> 8. Ensuring Default Local Users...", flush=True)
    try:
        ensure_default_users()
        print("[sync_all] Default users ensured.", flush=True)
    except Exception as e:
        print(f"[sync_all] ERROR ensuring default users: {e}", flush=True)

    print("\n==================================================", flush=True)
    print(f"[sync_all] FULL SYNC COMPLETE! Errors: {total_errors}", flush=True)
    print("==================================================", flush=True)
    
    return {
        "inserted": total_inserted,
        "updated": total_updated,
        "total_api": total_api,
        "errors": total_errors
    }
