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
    is_admin = bool(user.get("is_admin")) or bool(user_block.get("is_admin")) or any(k in user_role_raw for k in ("admin", "system manager", "tenant_admin", "super", "owner"))
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

        # Check sql_settings.json if empty in company_defaults
        if not term_id or term_id == "1":
            try:
                import os, json
                cfg_path = os.path.join("app_data", "sql_settings.json")
                if os.path.exists(cfg_path):
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        cfg_d = json.load(f)
                        saved_tid = str(cfg_d.get("server_terminal_id") or "").strip()
                        if saved_tid and saved_tid != "1":
                            term_id = saved_tid
                        if not shop_id:
                            shop_id = str(cfg_d.get("server_shop_id") or "").strip()
            except Exception:
                pass

        bound_dev = str(existing_defaults.get("bound_device_id") or existing_defaults.get("device_hardware_id") or "").strip()
        if not bound_dev:
            try:
                import os, json
                cfg_path = os.path.join("app_data", "sql_settings.json")
                if os.path.exists(cfg_path):
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        cfg_d = json.load(f)
                        saved_b = str(cfg_d.get("bound_device_id") or "").strip()
                        if saved_b:
                            bound_dev = saved_b
            except Exception:
                pass

        if not bound_dev or not term_id or term_id == "1":
            try:
                from database.db import get_connection
                conn = get_connection(); cur = conn.cursor()
                cur.execute("SELECT TOP 1 terminal_id, terminal_name, device_hardware_id FROM terminal_reference ORDER BY id ASC")
                trow = cur.fetchone(); conn.close()
                if trow:
                    if not term_id or term_id == "1":
                        term_id = str(trow[0] or "").strip()
                        term_name = term_name or str(trow[1] or "").strip()
                    if not bound_dev:
                        bound_dev = str(trow[2] or "").strip()
            except Exception:
                pass

        # Validation removed (Option 2): never block logins on terminal device mismatch
        if not term_id or term_id == "1":
            term_id = str(existing_defaults.get("server_terminal_id") or "1").strip()
            term_name = str(existing_defaults.get("server_terminal_name") or f"Terminal {term_id}").strip()

        existing_defaults["server_terminal_id"]   = term_id
        existing_defaults["server_terminal_name"] = term_name or f"Terminal {term_id}"
        if shop_id:
            existing_defaults["server_shop_id"]   = shop_id
        if user_warehouse and not existing_defaults.get("server_warehouse"):
            existing_defaults["server_warehouse"] = user_warehouse

        save_defaults(existing_defaults)
        print(f"[saas_assignment] [OK] Successfully bound terminal '{term_name}' (ID: {term_id}) for session on device '{current_device_id}'.")
        return True

    # ── 2. STORE SELECTION & PERMISSION CHECK ──────────────────────────
    current_shops = list(shops)
    selected_shop = None

    saved_shop_id = str(existing_defaults.get("server_shop_id") or "").strip()
    payload_shop_id = str(raw_data.get("selected_shop_id") or user_block.get("selected_shop_id") or saved_shop_id or "").strip()

    # If this machine already has a valid saved store in company_defaults, reuse it without prompting
    matched_saved_shop = None
    if saved_shop_id:
        matched_saved_shop = next((s for s in current_shops if str(s.get("id")) == str(saved_shop_id)), None)

    if matched_saved_shop:
        selected_shop = matched_saved_shop
        print(f"[saas_assignment] Auto-reusing configured store '{selected_shop.get('name') or selected_shop.get('shop_name')}' (ID: {saved_shop_id}) from defaults.")
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
    elif len(current_shops) == 1:
        selected_shop = current_shops[0]
        print(f"[saas_assignment] Auto-selected single available store '{selected_shop.get('name') or selected_shop.get('shop_name')}'")
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
        print(f"[saas_assignment] Error: Store '{shop_name}' has no terminals configured on backend.")
        QMessageBox.critical(
            parent_widget,
            "No Terminals Configured",
            f"Store '{shop_name}' has no POS terminals configured in the SaaS Backoffice.\n\n"
            "Please create a POS terminal for this store in your Backoffice dashboard before logging in."
        )
        return False

    saved_term_id = str(existing_defaults.get("server_terminal_id") or "").strip()
    payload_term_id = str(raw_data.get("selected_terminal_id") or user_block.get("selected_terminal_id") or saved_term_id or "").strip()

    selected_terminal = None
    # If this machine already has a valid saved terminal for this store in company_defaults, reuse it without prompting
    matched_saved_term = None
    if saved_term_id:
        matched_saved_term = next((t for t in terminals if str(t.get("id")) == str(saved_term_id)), None)

    if matched_saved_term:
        selected_terminal = matched_saved_term
        print(f"[saas_assignment] Auto-reusing configured terminal '{selected_terminal.get('name')}' (ID: {saved_term_id}) from defaults.")
    elif len(terminals) > 1:
        dlg = TerminalSelectionDialog(terminals, user_email, current_device_id, is_admin=is_admin, parent=parent_widget)
        target_tid = payload_term_id or saved_term_id
        if target_tid:
            for idx in range(dlg.list_widget.count()):
                item = dlg.list_widget.item(idx)
                tdata = item.data(Qt.UserRole) or {}
                if str(tdata.get("id")) == str(target_tid):
                    dlg.list_widget.setCurrentRow(idx)
                    break
        if dlg.exec() == TerminalSelectionDialog.Accepted and dlg.selected_terminal:
            selected_terminal = dlg.selected_terminal
        else:
            print("[saas_assignment] Terminal selection cancelled.")
            return False
    elif len(terminals) == 1:
        selected_terminal = terminals[0]
        print(f"[saas_assignment] Auto-selected single available terminal '{selected_terminal.get('name')}' (ID: {selected_terminal.get('id')})")
    else:
        print("[saas_assignment] Error: No terminals available.")
        return False

    terminal_id = str(selected_terminal.get("id") or "")
    terminal_name = str(selected_terminal.get("name") or f"Terminal {terminal_id}")
    print(f"[saas_assignment] >>> Selected Terminal: {terminal_name} (ID: {terminal_id})")

    # ── 5. TAKEOVER CHECK (MATCHES MOBILE POS LOGIC) ─────────────────────────
    # Determine if terminal is occupied by a *different* device/user.
    saved_bound_id = str(existing_defaults.get("bound_device_id") or existing_defaults.get("device_hardware_id") or "").strip()
    is_already_saved_in_defaults = (
        bool(saved_term_id) and 
        str(saved_term_id) == str(terminal_id) and 
        (not saved_bound_id or is_same_device(saved_bound_id, current_device_id))
    )

    taken_by_field = (
        selected_terminal.get("taken_by") or
        selected_terminal.get("active_user") or
        ""
    )
    is_taken = bool(
        selected_terminal.get("is_taken") or
        selected_terminal.get("taken") or
        selected_terminal.get("occupied") or
        taken_by_field
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
    is_same_dev = bool(term_dev) and is_same_device(term_dev, current_device_id)

    # Require takeover whenever terminal is active on another device or marked occupied
    takeover_required = (is_taken and not is_same_dev) or (bool(term_dev) and not is_same_dev)

    if takeover_required:
        msg = f"Terminal '{terminal_name}' is currently active on another device (User: {taken_by}).\n\nConnecting here will switch the active session to this device. Continue?"
        dlg = TerminalTakeoverDialog(msg, is_admin=is_admin, parent=parent_widget)
        dlg.exec()
        action = dlg.result_action

        if action is True:  # Switch session (takeover)
            print(f"[saas_assignment] Executing session takeover for terminal '{terminal_name}' (ID: {terminal_id}) on device '{current_device_id}'...")
            term_res = select_terminal(terminal_id, takeover=True, user_email=user_email)
            if not isinstance(term_res, dict) or (not term_res.get("success") and not term_res.get("skipped")):
                err_str = term_res.get("error", "Failed to switch terminal session.") if isinstance(term_res, dict) else "No response from server."
                QMessageBox.warning(parent_widget, "Terminal Switch Error", err_str)
                return False
            print(f"[saas_assignment] [OK] Session takeover accepted for device '{current_device_id}'.")
        else:  # Cancelled
            print("[saas_assignment] Session takeover cancelled by user.")
            return False
    else:
        term_res = select_terminal(terminal_id, takeover=False, user_email=user_email)
        if not isinstance(term_res, dict) or (not term_res.get("success") and not term_res.get("skipped")):
            err_msg = (term_res.get("error") or term_res.get("message")) if isinstance(term_res, dict) else "No response from server."
            print(f"[saas_assignment] select_terminal response: {err_msg}")
            
            # If server indicates takeover or session re-claim is needed:
            is_takeover_conflict = any(kw in str(err_msg).lower() for kw in [
                "assigned to another", "taken over", "already in use", "take over", "occupied", "another device"
            ])
            if is_takeover_conflict:
                msg = f"Terminal '{terminal_name}' is active on another device.\n\nConnecting here will switch the active session to this device. Continue?"
                dlg = TerminalTakeoverDialog(msg, is_admin=is_admin, parent=parent_widget)
                dlg.exec()
                if dlg.result_action is True:
                    print(f"[saas_assignment] User confirmed takeover after server conflict. Retrying with takeover=True...")
                    term_res = select_terminal(terminal_id, takeover=True, user_email=user_email)
                else:
                    print("[saas_assignment] Session takeover declined after server conflict.")
                    return False

            if not isinstance(term_res, dict) or (not term_res.get("success") and not term_res.get("skipped")):
                err_msg = (term_res.get("error") or term_res.get("message")) if isinstance(term_res, dict) else "No response from server."
                # If terminal is already bound to this device or user is a cashier on configured terminal,
                # do not wipe existing configuration on server hiccups or store permission mismatch
                if is_same_dev or (not is_admin and str(existing_defaults.get("server_terminal_id") or "") == str(terminal_id)):
                    print(f"[saas_assignment] Server select_terminal returned ({err_msg}), but terminal is already bound to this device. Proceeding with local binding.")
                else:
                    existing_defaults["server_shop_id"] = ""
                    existing_defaults["server_terminal_id"] = ""
                    existing_defaults["server_terminal_name"] = ""
                    save_defaults(existing_defaults)
                    try:
                        import os, json
                        from database.db import get_app_data_dir
                        cfg_p = os.path.join(get_app_data_dir(), "sql_settings.json")
                        if not os.path.exists(cfg_p):
                            cfg_p = os.path.join("app_data", "sql_settings.json")
                        if os.path.exists(cfg_p):
                            with open(cfg_p, "r", encoding="utf-8") as _f:
                                _cfg = json.load(_f)
                            _cfg["server_terminal_id"] = ""
                            with open(cfg_p, "w", encoding="utf-8") as _f:
                                json.dump(_cfg, _f, indent=4)
                    except Exception:
                        pass
                    QMessageBox.critical(
                        parent_widget,
                        "Terminal Assignment Error",
                        f"Cannot select Terminal '{terminal_name}' (ID: {terminal_id}):\n\n{err_msg}\n\nPlease ensure this terminal is properly configured for your tenant in SaaS Backoffice."
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

    # Lock initial terminal reference (write-once policy)
    try:
        from services.auth_service import init_terminal_reference
        init_terminal_reference(
            terminal_id=str(terminal_id or "").strip(),
            terminal_name=str(terminal_name or "").strip(),
            store_id=str(shop_id or "").strip(),
            store_name=str(shop_name or "").strip(),
            device_hardware_id=str(current_device_id or "").strip(),
        )
    except Exception as _itre:
        print(f"[saas_assignment] Warning calling init_terminal_reference: {_itre}")

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
