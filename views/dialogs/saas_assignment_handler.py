from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox
from services.credentials import get_system_mode
from services.auth_service import select_shop, select_terminal
from utils.hardware import get_machine_id
from models.company_defaults import get_defaults, save_defaults
from views.dialogs.shop_terminal_dialogs import (
    ShopSelectionDialog, TerminalSelectionDialog, TerminalTakeoverDialog,
    show_store_access_denied_dialog
)


def handle_saas_shop_and_terminal_selection(parent_widget, user: dict, raw_data: dict = None) -> bool:
    """
    Handles Shop & Terminal selection for SaaS mode.
    Runs ONLY if get_system_mode() == "saas".
    Returns True if selection/assignment succeeded or if not in SaaS mode.
    Returns False if assignment failed or was cancelled by user.
    """
    # ── 1. STRICT SAAS MODE GUARD ──────────────────────────────────────────────
    if get_system_mode() != "saas":
        return True

    print("[saas_assignment] Executing SaaS Mode Shop & Terminal Assignment...")

    raw_data = raw_data or {}
    user_block = raw_data.get("user") or {}
    existing_defaults = get_defaults() or {}

    # Extract available shops
    shops = user_block.get("shops") or raw_data.get("shops") or []
    user_days_left = raw_data.get("days_left") or user_block.get("days_left") or user.get("days_left")
    for s in shops:
        if isinstance(s, dict) and s.get("days_left") is None and user_days_left is not None:
            s["days_left"] = user_days_left
    user_role_raw = str(user.get("role") or user_block.get("role") or (user_block.get("user_rights") or {}).get("profile_name") or "").strip().lower()
    is_admin = any(k in user_role_raw for k in ("admin", "system manager", "tenant_admin", "super", "owner"))
    user_username = str(user.get("username") or user_block.get("username") or "").strip()
    user_email = str(user.get("email") or user_block.get("email") or "").strip()
    user_warehouse = str(user.get("warehouse") or user_block.get("warehouse") or "").strip()
    current_device_id = get_machine_id()

    GENERIC_WORDS = {"store", "legends", "shop", "pos", "branch", "pvt", "ltd", "warehouse", "inc"}

    def _get_store_keywords(name: str) -> set:
        tokens = [t.strip().lower() for t in (name or "").replace("-", " ").replace("_", " ").split()]
        return {t for t in tokens if t and t not in GENERIC_WORDS and len(t) > 1}

    def _is_store_allowed(target_store: str) -> bool:
        if is_admin or not target_store:
            return True
        tw_low = target_store.lower().strip()
        target_kw = _get_store_keywords(tw_low)

        candidate_stores = []
        if user_warehouse:
            candidate_stores.extend([s.strip().lower() for s in user_warehouse.split(",") if s.strip()])
        if shops and isinstance(shops, list):
            for s in shops:
                sn = str(s.get("name") or s.get("shop_name") or "").strip().lower()
                if sn:
                    candidate_stores.append(sn)

        if not candidate_stores:
            return True

        for cand in candidate_stores:
            if tw_low == cand or tw_low in cand or cand in tw_low:
                return True
            cand_kw = _get_store_keywords(cand)
            if target_kw and cand_kw and bool(target_kw & cand_kw):
                return True

        return False

    print(f"[saas_assignment] User Role: {user_role_raw} | Admin: {is_admin} | Device ID: {current_device_id}")

    if not shops:
        print("[saas_assignment] Notice: No shops array in payload (e.g. PIN or offline login). Restoring saved terminal credentials...")
        term_id = str(existing_defaults.get("server_terminal_id") or "").strip()
        term_name = str(existing_defaults.get("server_terminal_name") or "").strip()
        shop_id = str(existing_defaults.get("server_shop_id") or "").strip()

        if not term_id:
            term_id = "1"
            term_name = "Terminal 1"

        existing_defaults["server_terminal_id"]   = term_id
        existing_defaults["server_terminal_name"] = term_name
        if shop_id:
            existing_defaults["server_shop_id"]   = shop_id
        if user_warehouse and not existing_defaults.get("server_warehouse"):
            existing_defaults["server_warehouse"] = user_warehouse

        save_defaults(existing_defaults)
        print(f"[saas_assignment] [OK] Successfully bound terminal '{term_name}' (ID: {term_id}) for session.")
        return True

    # ── 2. STORE SELECTION & PERMISSION CHECK ──────────────────────────
    current_shops = list(shops)
    selected_shop = None

    saved_shop_id = str(existing_defaults.get("server_shop_id") or "").strip()
    payload_shop_id = str(raw_data.get("selected_shop_id") or user_block.get("selected_shop_id") or saved_shop_id or "").strip()

    # Restore saved shop from local database if explicitly saved on this machine
    if saved_shop_id:
        for s in current_shops:
            s_id = str(s.get("id") or s.get("shop_id") or "").strip()
            if str(s_id) == str(saved_shop_id):
                selected_shop = s
                print(f"[saas_assignment] Restored saved active store '{selected_shop.get('name') or selected_shop.get('shop_name')}' (ID: {selected_shop.get('id')})")
                break

    if not selected_shop:
        if len(current_shops) == 1:
            selected_shop = current_shops[0]
            print(f"[saas_assignment] Auto-selected single available store '{selected_shop.get('name') or selected_shop.get('shop_name')}'")
        elif len(current_shops) > 1:
            dlg = ShopSelectionDialog(current_shops, parent=parent_widget)
            if payload_shop_id:
                for idx in range(dlg.list_widget.count()):
                    item = dlg.list_widget.item(idx)
                    sdata = item.data(Qt.UserRole) or {}
                    if str(sdata.get("id")) == str(payload_shop_id):
                        dlg.list_widget.setCurrentRow(idx)
                        break
            if dlg.exec() == ShopSelectionDialog.Accepted and dlg.selected_shop:
                selected_shop = dlg.selected_shop
            else:
                print("[saas_assignment] Shop selection cancelled.")
                return False
        else:
            print("[saas_assignment] Error: No stores available for user.")
            show_store_access_denied_dialog(parent_widget, "No stores available for this user.")
            return False

    shop_id = selected_shop.get("id")
    shop_name = selected_shop.get("name") or selected_shop.get("shop_name") or f"Shop {shop_id}"
    print(f"[saas_assignment] >>> Active Shop: {shop_name} (ID: {shop_id})")

    # ── SUBSCRIPTION EXPIRY CHECK ──────────────────────────────────────
    from datetime import datetime, date
    sub_block = raw_data.get("subscription") if isinstance(raw_data, dict) else {}
    if not isinstance(sub_block, dict):
        sub_block = {}

    raw_exp = (
        selected_shop.get("subscription_expiry") or 
        selected_shop.get("expiry_date") or 
        selected_shop.get("valid_till") or 
        selected_shop.get("expires_at") or 
        selected_shop.get("subscription_end_date") or 
        sub_block.get("end_date") or
        sub_block.get("subscription_expiry") or
        user_block.get("subscription_expiry") or 
        raw_data.get("subscription_expiry") or 
        ""
    )
    days_left = (
        selected_shop.get("days_left") or 
        selected_shop.get("subscription_days") or 
        selected_shop.get("days_remaining") or 
        sub_block.get("days_left") or
        user_days_left or 
        user_block.get("days_left") or 
        raw_data.get("days_left")
    )
    if days_left is None and raw_exp:
        try:
            exp_str = str(raw_exp)[:10]
            exp_dt = datetime.strptime(exp_str, "%Y-%m-%d").date()
            days_left = (exp_dt - date.today()).days
        except Exception as _expe:
            print(f"[saas_assignment] Warning: Expiry date parse failed ({raw_exp}): {_expe}")

    if days_left is not None:
        if days_left < 0:
            exp_msg = f"Subscription for Store '{shop_name}' has expired on {raw_exp[:10]}. Access Denied."
            print(f"[saas_assignment] 🛑 {exp_msg}")
            QMessageBox.critical(parent_widget, "Subscription Expired", exp_msg)
            return False
        elif days_left <= 3:
            warn_msg = f"Warning: Your subscription for Store '{shop_name}' is about to expire in {days_left} day(s). Please renew your subscription."
            print(f"[saas_assignment] ⚠️ {warn_msg}")
            QMessageBox.warning(parent_widget, "Subscription Expiry Warning", warn_msg)

    # Call backend select_shop API
    shop_res = select_shop(shop_id)
    if not shop_res.get("success") and not shop_res.get("skipped"):
        err_msg = shop_res.get("error") or shop_res.get("message") or f"Access denied for Store '{shop_name}'."
        print(f"[saas_assignment] select_shop failed for Store '{shop_name}' (ID: {shop_id}): {err_msg}")
        existing_defaults["server_shop_id"] = ""
        existing_defaults["server_terminal_id"] = ""
        existing_defaults["server_terminal_name"] = ""
        save_defaults(existing_defaults)
        show_store_access_denied_dialog(parent_widget, f"Access denied for Store '{shop_name}':\n\n{err_msg}")
        return False

    if shop_res.get("data", {}).get("user", {}).get("shops"):
        updated_shops = shop_res["data"]["user"]["shops"]
        match = next((s for s in updated_shops if str(s.get("id")) == str(shop_id)), None)
        if match:
            selected_shop = match

    # ── 3. TERMINAL SELECTION FOR THE SELECTED STORE ─────────────────
    terminals = selected_shop.get("terminals") or []
    if not terminals:
        terminals = [{"id": "1", "name": "Terminal 1", "is_taken": False}]
        print(f"[saas_assignment] Warning: Store '{shop_name}' has no terminals configured on backend.")

    saved_term_id = str(existing_defaults.get("server_terminal_id") or "").strip()
    payload_term_id = str(raw_data.get("selected_terminal_id") or user_block.get("selected_terminal_id") or saved_term_id or "").strip()

    # Restore saved terminal from local database if explicitly saved on this machine
    selected_terminal = None
    if saved_term_id:
        for t in terminals:
            t_id = str(t.get("id") or t.get("terminal_id") or "").strip()
            if str(t_id) == str(saved_term_id):
                selected_terminal = t
                print(f"[saas_assignment] Restored saved terminal '{selected_terminal.get('name') or selected_terminal.get('id')}' (ID: {selected_terminal.get('id')})")
                break

    if not selected_terminal:
        if len(terminals) == 1:
            selected_terminal = terminals[0]
            print(f"[saas_assignment] Auto-selected single available terminal '{selected_terminal.get('name')}'")
        elif len(terminals) > 1:
            dlg = TerminalSelectionDialog(terminals, user_email, current_device_id, is_admin=is_admin, parent=parent_widget)
            if payload_term_id:
                for idx in range(dlg.list_widget.count()):
                    item = dlg.list_widget.item(idx)
                    tdata = item.data(Qt.UserRole) or {}
                    if str(tdata.get("id")) == str(payload_term_id):
                        dlg.list_widget.setCurrentRow(idx)
                        break
            if dlg.exec() == TerminalSelectionDialog.Accepted and dlg.selected_terminal:
                selected_terminal = dlg.selected_terminal
            else:
                print("[saas_assignment] Terminal selection cancelled.")
                return False
        else:
            print("[saas_assignment] Error: No terminals available.")
            return False

    terminal_id = str(selected_terminal.get("id") or "")
    terminal_name = str(selected_terminal.get("name") or f"Terminal {terminal_id}")
    print(f"[saas_assignment] >>> Selected Terminal: {terminal_name} (ID: {terminal_id})")

    # ── 5. TAKEOVER CHECK (MATCHES MOBILE POS LOGIC) ─────────────────────────
    is_taken = bool(
        selected_terminal.get("is_taken") or 
        selected_terminal.get("taken_by") or 
        selected_terminal.get("is_active") or 
        selected_terminal.get("taken") or
        selected_terminal.get("active_user") or
        selected_terminal.get("occupied")
    )
    taken_by = str(
        selected_terminal.get("taken_by_user_name") or 
        selected_terminal.get("taken_by_user_email") or 
        selected_terminal.get("taken_by") or 
        selected_terminal.get("active_user") or
        "another device/user"
    )
    term_dev = str(
        selected_terminal.get("device_hardware_id") or 
        selected_terminal.get("device_id") or 
        selected_terminal.get("hardware_id") or 
        selected_terminal.get("mac_address") or 
        ""
    )
    from utils.hardware import is_same_device
    is_same_dev = is_same_device(term_dev, current_device_id)

    takeover_required = False
    if is_taken and not is_same_dev:
        takeover_required = True

    if takeover_required:
        msg = f"Terminal '{terminal_name}' is currently active under user {taken_by}.\n\nConnecting here will switch the active session to this device. Continue?"
        dlg = TerminalTakeoverDialog(msg, is_admin=is_admin, parent=parent_widget)
        dlg.exec()
        action = dlg.result_action

        if action is True:  # Switch session (takeover)
            print(f"[saas_assignment] Executing session takeover for terminal '{terminal_name}' (ID: {terminal_id}) on device '{current_device_id}'...")
            term_res = select_terminal(terminal_id, takeover=True, user_email=user_email)
            if not term_res.get("success") and not term_res.get("skipped"):
                QMessageBox.warning(parent_widget, "Terminal Switch Error", term_res.get("error", "Failed to switch terminal session."))
                return False
            print(f"[saas_assignment] [OK] Session takeover accepted for device '{current_device_id}'.")
        else:  # Cancelled
            print("[saas_assignment] Session takeover cancelled by user.")
            return False
    else:
        term_res = select_terminal(terminal_id, takeover=False, user_email=user_email)
        if not term_res.get("success") and not term_res.get("skipped"):
            err_msg = term_res.get("error") or term_res.get("message") or "Failed to select terminal."
            print(f"[saas_assignment] select_terminal failed: {err_msg}")
            
            is_net_timeout = any(kw in str(err_msg).lower() for kw in ["timed out", "timeout", "handshake", "connection refused", "network error"])
            if is_net_timeout and saved_term_id and str(saved_term_id) == str(terminal_id):
                print(f"[saas_assignment] ⚠️ Transient network/handshake timeout reaching select-terminal endpoint, but terminal '{terminal_name}' (ID: {terminal_id}) is already assigned locally. Proceeding with active session.")
            else:
                existing_defaults["server_shop_id"] = ""
                existing_defaults["server_terminal_id"] = ""
                existing_defaults["server_terminal_name"] = ""
                save_defaults(existing_defaults)
                QMessageBox.warning(
                    parent_widget,
                    "Terminal Access Error",
                    f"Cannot select Terminal '{terminal_name}' (ID: {terminal_id}):\n\n{err_msg}\n\nPlease re-select a store and terminal assigned to your user account."
                )
                return False

    # ── 6. PERSIST DEFAULTS ────────────────────────────────────────────────────
    existing_defaults["server_shop_id"]       = str(shop_id or "")
    existing_defaults["server_terminal_id"]   = str(terminal_id or "")
    existing_defaults["server_terminal_name"] = str(terminal_name or "")
    existing_defaults["bound_device_id"]      = str(current_device_id or "").strip()
    existing_defaults["device_hardware_id"]  = str(current_device_id or "").strip()
    if shop_name:
        existing_defaults["server_warehouse"] = shop_name
        existing_defaults["warehouse"] = shop_name
        existing_defaults["server_cost_center"] = shop_name
        existing_defaults["cost_center"] = shop_name
        existing_defaults["server_company"] = shop_name
        existing_defaults["company_name"] = shop_name

    if days_left is not None:
        existing_defaults["subscription_days_left"] = str(days_left)
    if raw_exp:
        existing_defaults["subscription_expiry"] = str(raw_exp)[:10]

    company_val = shop_name or selected_shop.get("company") or user_block.get("company") or raw_data.get("company") or existing_defaults.get("server_company", "")
    cost_center_val = shop_name or selected_shop.get("cost_center") or user_block.get("cost_center") or raw_data.get("cost_center") or existing_defaults.get("server_cost_center", "")

    if company_val:
        existing_defaults["server_company"] = str(company_val)
        existing_defaults["company_name"] = str(company_val)
    if cost_center_val:
        existing_defaults["server_cost_center"] = str(cost_center_val)

    # ── Base Currency & Symbol Extraction in SaaS Assignment ───────────────────
    primary_ccy = str(user_block.get("currency") or raw_data.get("currency") or selected_shop.get("currency") or "").strip()
    currencies_arr = user_block.get("currencies") or raw_data.get("currencies") or selected_shop.get("currencies") or []
    primary_symbol = ""

    if isinstance(currencies_arr, list) and len(currencies_arr) > 0:
        for c_entry in currencies_arr:
            if isinstance(c_entry, dict):
                c_name = str(c_entry.get("name") or "").strip()
                c_sym  = str(c_entry.get("symbol") or "").strip()
                if primary_ccy and (c_name.upper() == primary_ccy.upper() or c_sym.upper() == primary_ccy.upper()):
                    primary_symbol = c_name or c_sym
                    if not primary_ccy:
                        primary_ccy = c_sym or c_name
                    break
                elif not primary_ccy and (c_name or c_sym):
                    primary_ccy = c_sym or c_name
                    primary_symbol = c_name or c_sym
                    break

    if primary_ccy:
        existing_defaults["server_company_currency"] = primary_ccy
        existing_defaults["server_company_currency_symbol"] = primary_symbol or primary_ccy
        print(f"[saas_assignment] Base currency extracted on login: '{primary_ccy}' (symbol: '{existing_defaults['server_company_currency_symbol']}')")

    save_defaults(existing_defaults)
    print(f"[saas_assignment] [OK] Successfully saved SaaS store '{shop_name}' (Company: '{company_val}', CostCenter: '{cost_center_val}', Currency: '{primary_ccy}') & terminal '{terminal_name}' (ID: {terminal_id}).")

    if user_email and not is_admin:
        try:
            from database.db import get_connection
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
                UPDATE users SET 
                    company = ?, 
                    warehouse = ?, 
                    cost_center = ?
                WHERE (email = ? AND email <> '') OR username = ? OR frappe_user = ?
            """, (existing_defaults.get("server_company", ""),
                  existing_defaults.get("server_warehouse", ""),
                  existing_defaults.get("server_cost_center", ""),
                  user_email, user_email, user_email))
            conn.commit()
            conn.close()
        except Exception as _ue:
            print(f"[saas_assignment] User store sync warning: {_ue}")

    # ── 7. UPSERT CUSTOMERS FROM PAYLOAD ──────────────────────────────────────
    payload_custs = user_block.get("customers") or raw_data.get("customers") or []
    if payload_custs and isinstance(payload_custs, list):
        try:
            from models.customer import upsert_from_frappe
            saved_count = 0
            for cust in payload_custs:
                if isinstance(cust, dict):
                    upsert_from_frappe(cust)
                    saved_count += 1
            print(f"[saas_assignment] [OK] Upserted {saved_count} initial customer(s) from login payload.")
        except Exception as _ce:
            print(f"[saas_assignment] Warning: Customer payload upsert failed: {_ce}")

    return True
