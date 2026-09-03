from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QWidget, QGraphicsDropShadowEffect,
    QStackedWidget, QGridLayout, QSizePolicy, QApplication, QMessageBox, QFormLayout,
    QComboBox,
)
from PySide6.QtCore import (
    Qt, QTimer, QEvent,
    QThread, Signal, QSize, QObject,
)
from PySide6.QtGui import QColor, QFont, QPainter, QPen
import sys
import os
import qtawesome as qta

# =============================================================================
# Palette
# =============================================================================
from theme import *

def get_current_site_url():
    try:
        from services.site_config import get_host
        return get_host().rstrip("/")
    except Exception:
        return "Not Configured"

# =============================================================================
# Connectivity helper  (fast, non-blocking check)
# =============================================================================
def _is_online(timeout: float = 2.0) -> bool:
    """
    Quick TCP-level reachability check.
    Parses SITE_URL to determine the correct host and port (defaulting to 443/80).
    """
    import socket
    from urllib.parse import urlparse
    import time
    
    # SITE_URL might be "mysite.com" or "http://mysite.com:8069"
    url = get_current_site_url()
    if url == "Not Configured":
        return False

    parsed = urlparse(url)
    host = parsed.hostname or url
    try:
        port = parsed.port
    except ValueError:
        port = None
    if not port:
        port = 443 if parsed.scheme == "https" else 80

    # 1. TCP probe
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return True
    except OSError:
        pass

    # 2. HTTP fallback
    try:
        import urllib.request
        urllib.request.urlopen(url, timeout=timeout)
        return True
    except Exception:
        pass

    return False

# =============================================================================
# Background workers
# =============================================================================
class LoginWorker(QThread):
    """
    Runs auth_service.login() off the main thread.

    Strategy (in order):
      1. Quick connectivity check (TCP, 3 s).
      2. If online  -> attempt server login (timeout-guarded).
      3. If offline -> fall straight through to local DB check.
      4. Always emit a result dict - never crash silently.
    """
    finished = Signal(object)

    # Hard ceiling for the whole online-login attempt (seconds).
    # auth_service.login() does: HTTP login -> token save -> product auto-sync
    # -> local credential persist.  Give it plenty of room on slow connections.
    ONLINE_TIMEOUT = 60

    def __init__(self, username: str, password: str, database: str = "", system_mode: str = "frappe"):
        super().__init__()
        self.username = username
        self.password = password
        self.database = database
        self.system_mode = system_mode

    # ------------------------------------------------------------------
    def run(self):
        print(f"[LoginWorker] ▶ started  username={self.username!r}")

        # Check for work_offline setting
        is_offline_mode = False
        try:
            from models.company_defaults import get_defaults
            d = get_defaults()
            is_offline_mode = (d.get("work_offline") == "1")
        except Exception:
            pass

        # Strategy: 
        # 1. If username is 'admin' or we are in 'work_offline' mode, try local FIRST.
        # 2. Otherwise, check connectivity and try online.
        # 3. Fallback to local if online fails (but not if it's a genuine auth rejection, 
        #    UNLESS it's a timeout or network error).
        
        should_try_local_first = (self.username.lower() == 'admin' or is_offline_mode)
        
        if should_try_local_first:
            print(f"[LoginWorker] prioritizing local auth (admin or offline_mode)")
            result = self._try_local()
            if result.get("success"):
                self.finished.emit(result)
                return
            print(f"[LoginWorker] local auth failed for {self.username}, continuing to online check...")

        online = _is_online(timeout=8.0)
        print(f"[LoginWorker] connectivity={online}")

        if online:
            result = self._try_online()
            # If online path returned a genuine credential error, don't
            # silently fall back - surface it immediately so the user knows.
            # EXCEPT if we didn't try local yet and it might be a local-only user.
            if result.get("success"):
                self.finished.emit(result)
                return
            
            if result.get("source") == "online" and not should_try_local_first:
                # If it's a genuine credential failure from server, we usually stop.
                # But if it's a local-only user created during setup, we should try local.
                print(f"[LoginWorker] online rejected, trying local fallback just in case...")
            else:
                # Any other online failure (timeout, parse error, 5xx …)
                # -> try local DB before giving up.
                print(f"[LoginWorker] online failed ({result.get('error')}), trying local …")

        result = self._try_local()
        self.finished.emit(result)

    # ------------------------------------------------------------------
    def _try_online(self) -> dict:
        import concurrent.futures, traceback
        def _call():
            if self.system_mode == 'odoo':
                from services.odoo.auth_service import login
                return login(self.username, self.password, self.database)
            else:
                from services.auth_service import login
                return login(self.username, self.password)

        print(f"[LoginWorker] Starting {self.system_mode.upper()} auth attempt...")
        print(f"  - User: {self.username}")
        print(f"  - Mode: {self.system_mode}")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(_call)
            try:
                result = future.result(timeout=self.ONLINE_TIMEOUT)
                print(f"[LoginWorker] online result: success={result.get('success')} "
                      f"source={result.get('source')!r} error={result.get('error')}")
                # Normalise source so callers can always trust it
                result.setdefault("source", "online")
                return result
            except concurrent.futures.TimeoutError:
                print(f"[LoginWorker] online timed out after {self.ONLINE_TIMEOUT}s")
                return {"success": False,
                        "error": f"Server did not respond within {self.ONLINE_TIMEOUT} seconds.",
                        "source": "timeout"}
            except Exception as exc:
                print(f"[LoginWorker] online exception:\n{traceback.format_exc()}")
                return {"success": False, "error": str(exc), "source": "exception"}

    # ------------------------------------------------------------------
    def _try_local(self) -> dict:
        """
        Attempt authentication against the local SQL Server database only.

        The models.user module may expose different function names depending on
        the project version.  We try every known variant in order so this never
        ImportErrors on the user.
        """
        import traceback, hashlib

        # ── Strategy 1: dedicated authenticate_local() helper ────────────────
        try:
            from models.user import authenticate_local
            user = authenticate_local(self.username, self.password)
            if user:
                print(f"[LoginWorker] local auth OK (authenticate_local)  "
                      f"user={user.get('username')!r}")
                return {"success": True, "user": user, "source": "offline"}
            print("[LoginWorker] authenticate_local -> no match")
            return {"success": False,
                    "error": "Incorrect username or password.",
                    "source": "offline"}
        except ImportError:
            print("[LoginWorker] authenticate_local not found, trying fallbacks…")
        except Exception as exc:
            print(f"[LoginWorker] authenticate_local error: {exc}")

        # ── Strategy 2: authenticate(username, password) ─────────────────────
        try:
            from models.user import authenticate
            user = authenticate(self.username, self.password)
            if user:
                print(f"[LoginWorker] local auth OK (authenticate)  "
                      f"user={user.get('username')!r}")
                return {"success": True, "user": user, "source": "offline"}
            print("[LoginWorker] authenticate -> no match")
            return {"success": False,
                    "error": "Incorrect username or password.",
                    "source": "offline"}
        except ImportError:
            print("[LoginWorker] authenticate not found, trying DB fallback…")
        except Exception as exc:
            print(f"[LoginWorker] authenticate error: {exc}")

        # ── Strategy 3: raw DB query (SQL Server - pyodbc style) ─────────────
        # Hashes the password the same way auth_service does (sha-256 hex).
        try:
            from database.db import get_connection
            pw_hash = hashlib.sha256(self.password.encode()).hexdigest()
            conn = get_connection()
            cur  = conn.cursor()
            cur.execute(
                "SELECT TOP 1 id, username, email, full_name, role, "
                "           warehouse, company, pin, active "
                "FROM users "
                "WHERE (username=? OR email=?) AND password=? AND active=1",
                (self.username, self.username, pw_hash),
            )
            row = cur.fetchone()
            conn.close()
            if row:
                cols = ["id", "username", "email", "full_name", "role",
                        "warehouse", "company", "pin", "active"]
                user = dict(zip(cols, row))
                print(f"[LoginWorker] local auth OK (raw DB)  "
                      f"user={user.get('username')!r}")
                return {"success": True, "user": user, "source": "offline"}
            print("[LoginWorker] raw DB -> no match")
            return {"success": False,
                    "error": "Incorrect username or password.",
                    "source": "offline"}
        except Exception as exc:
            print(f"[LoginWorker] raw DB fallback exception:\n{traceback.format_exc()}")
            return {"success": False,
                    "error": "Could not reach server and local login failed.",
                    "source": "local_error"}


# ------------------------------------------------------------------
class BackgroundSyncWorker(QThread):
    """Syncs users, products and taxes after a successful login."""

    def run(self):
        from services.credentials import get_system_mode
        mode = get_system_mode()
        
        if mode == "odoo":
            print("[bg-sync] Detected Odoo mode - triggering Odoo sync...")
            try:
                from services.odoo.sync_service import sync_all_odoo
                sync_all_odoo()
                print("[bg-sync] [OK] Odoo sync complete")
            except Exception as e:
                print(f"[bg-sync] [!] Odoo sync failed: {e}")
            return

        # Frappe mode (original logic)
        for label, func_path in [
            ("users",         "services.user_sync_service.sync_users"),
        ]:
            try:
                module, attr = func_path.rsplit(".", 1)
                import importlib
                mod = importlib.import_module(module)
                obj = getattr(mod, attr)
                if callable(obj) and not isinstance(obj, type):
                    obj()
                else:
                    obj().run()
                print(f"[bg-sync] [OK] {label}")
            except Exception as e:
                print(f"[bg-sync] [!]  {label}: {e}")


# ------------------------------------------------------------------
class ConnectivityWorker(QThread):
    """Non-blocking connectivity check that emits a result signal."""
    result = Signal(bool)

    def run(self):
        self.result.emit(_is_online(timeout=8.0))


# =============================================================================
# PIN dot indicator widget
# =============================================================================
class PinDots(QWidget):
    def __init__(self, length: int = 4, parent=None):
        super().__init__(parent)
        self.length = length
        self.filled = 0
        self.setFixedSize(length * 28 + (length - 1) * 10, 24)

    def set_filled(self, n: int):
        self.filled = max(0, min(n, self.length))
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r   = 9
        gap = 28
        x0  = (self.width() - (self.length * gap - 2)) // 2
        y   = self.height() // 2
        for i in range(self.length):
            cx = x0 + i * gap + r
            if i < self.filled:
                p.setBrush(QColor(ACCENT))
                p.setPen(QPen(QColor(ACCENT), 2))
            else:
                p.setBrush(QColor(WHITE))
                p.setPen(QPen(QColor(BORDER), 2))
            p.drawEllipse(cx - r, y - r, r * 2, r * 2)
        p.end()


# =============================================================================
# Catchy Error Dialog
# =============================================================================
class CatchyErrorDialog(QDialog):
    def __init__(self, title: str, message: str, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(400, 220)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)

        card = QFrame()
        card.setObjectName("errCard")
        card.setStyleSheet(f"""
            QFrame#errCard {{
                background:#1e1e2e; border:2px solid {DANGER};
                border-radius:15px;
            }}
        """)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(24, 20, 24, 20)
        cl.setSpacing(12)

        hdr = QHBoxLayout()
        ico = QLabel()
        ico.setPixmap(qta.icon("fa5s.exclamation-triangle", color=DANGER).pixmap(22, 22))
        ttl = QLabel(title)
        ttl.setStyleSheet(f"color:{WHITE}; font-size:15px; font-weight:bold;")
        hdr.addWidget(ico)
        hdr.addSpacing(8)
        hdr.addWidget(ttl)
        hdr.addStretch()
        cl.addLayout(hdr)

        msg = QLabel(message)
        msg.setWordWrap(True)
        msg.setStyleSheet(f"color:{MID}; font-size:12px; line-height:16px;")
        cl.addWidget(msg, 1)

        btn = QPushButton("Understood")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setMinimumHeight(42)
        btn.setStyleSheet(f"""
            QPushButton {{
                background:{DANGER}; color:{WHITE};
                border-radius:10px; font-weight:bold; font-size:13px;
            }}
            QPushButton:hover   {{ background:#e74c3c; }}
            QPushButton:pressed {{ background:#c0392b; }}
        """)
        btn.clicked.connect(self.accept)
        cl.addWidget(btn)

        outer.addWidget(card)


# =============================================================================
# Quick Local Setup Dialog
# =============================================================================
class OfflineSetupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Quick Local Setup")
        self.setFixedSize(480, 660)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setStyleSheet(f"background: {WHITE};")
        self._build_ui()

    def _build_ui(self):
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(10, 10, 10, 10)

        card = QFrame()
        card.setObjectName("setupCard")
        card.setStyleSheet(f"""
            QFrame#setupCard {{
                background:#ffffff; border-radius:24px;
                border: 1px solid #e2e8f0;
            }}
        """)
        # Soft Shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30); shadow.setXOffset(0); shadow.setYOffset(10)
        shadow.setColor(QColor(0, 0, 0, 20))
        card.setGraphicsEffect(shadow)
        main_lay.addWidget(card)

        cl = QVBoxLayout(card); cl.setContentsMargins(0, 0, 0, 0); cl.setSpacing(0)

        # Clean Header
        hdr = QWidget(); hdr.setFixedHeight(100)
        hdr.setStyleSheet(f"background: {WHITE}; border-top-left-radius:24px; border-top-right-radius:24px;")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(40, 20, 40, 0); hl.setSpacing(15)
        
        v_ttl = QVBoxLayout(); v_ttl.setSpacing(2); v_ttl.setAlignment(Qt.AlignVCenter)
        ttl = QLabel("Local Profile")
        ttl.setStyleSheet(f"color:{NAVY}; font-size:26px; font-weight:800; background:transparent;")
        sub = QLabel("Configure your store details for offline mode.")
        sub.setStyleSheet(f"color:{MUTED}; font-size:12px; background:transparent;")
        v_ttl.addWidget(ttl); v_ttl.addWidget(sub)
        hl.addLayout(v_ttl)
        
        hl.addStretch()
        cl.addWidget(hdr)

        # Body
        body = QWidget()
        bl = QVBoxLayout(body); bl.setContentsMargins(40, 10, 40, 30); bl.setSpacing(20)
        
        from models.company_defaults import get_defaults
        defaults = get_defaults() or {}

        def _combo_group(label, initial, items=None):
            group = QVBoxLayout(); group.setSpacing(8)
            lbl = QLabel(label.upper())
            lbl.setStyleSheet("color:#94a3b8; font-size:11px; font-weight:700; letter-spacing:0.5px;")
            combo = QComboBox()
            combo.setEditable(True)
            combo.setFixedHeight(48)
            combo.setStyleSheet(f"""
                QComboBox {{
                    background:#f8fafc; color:#1e293b;
                    border:1px solid #e2e8f0; border-radius:12px;
                    padding:0 16px; font-size:15px;
                }}
                QComboBox:focus {{ border:2px solid {ACCENT}; background:#ffffff; }}
                QComboBox::drop-down {{ border:none; }}
            """)
            if items:
                combo.addItems(items)
            combo.setEditText(initial)
            group.addWidget(lbl); group.addWidget(combo)
            return group, combo

        # Fetch data for combos
        companies = []
        try:
            from models.company import get_all_companies
            companies = [c["name"] for c in get_all_companies()]
        except: pass
        
        comp_group, self.company = _combo_group("Company Name", defaults.get("company_name", ""), companies)
        bl.addLayout(comp_group)

        warehouses = []
        try:
            from models.warehouse import get_all_warehouses
            warehouses = [w["name"] for w in get_all_warehouses()]
        except: pass
        
        wh_group, self.warehouse = _combo_group("Warehouse", defaults.get("server_warehouse", ""), warehouses)
        bl.addLayout(wh_group)

        cost_centers = []
        try:
            from models.cost_center import get_all_cost_centers
            cost_centers = [cc["name"] for cc in get_all_cost_centers()]
        except: pass
        
        cc_group, self.cost_center = _combo_group("Cost Center", defaults.get("server_cost_center", ""), cost_centers)
        bl.addLayout(cc_group)
        

        agent_group, self.agent_num = _combo_group("Agent Number", defaults.get("agent_number", "Agent"))
        bl.addLayout(agent_group)

        cl.addWidget(body, 1)

        # Bottom Actions
        actions = QWidget(); al = QHBoxLayout(actions); al.setContentsMargins(40, 0, 40, 30)
        
        save_btn = QPushButton("Complete Setup")
        save_btn.setFixedSize(180, 48); save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background:{SUCCESS}; color:#ffffff; font-size:14px; font-weight:bold;
                border-radius:12px; border:none;
            }}
            QPushButton:hover {{ background:#1f9447; }}
        """)
        save_btn.clicked.connect(self._save)
        
        cancel_btn = QPushButton("Discard")
        cancel_btn.setFixedSize(100, 48); cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(f"background:{LIGHT}; color:{NAVY}; font-size:13px; font-weight:600; border:none; border-radius:12px;")
        cancel_btn.clicked.connect(self.reject)
        
        al.addWidget(cancel_btn); al.addSpacing(10); al.addWidget(save_btn)
        cl.addWidget(actions)

    def _save(self):
        from models.company_defaults import get_defaults, save_defaults
        defaults = get_defaults() or {}
        comp_name = self.company.currentText().strip()
        wh_name   = self.warehouse.currentText().strip()
        cc_name   = self.cost_center.currentText().strip()

        if not comp_name or not wh_name or not cc_name:
            QMessageBox.warning(self, "Incomplete Setup", "Please ensure Company, Warehouse and Cost Center are all filled in.")
            return

        defaults["company_name"] = comp_name
        defaults["server_warehouse"] = wh_name
        defaults["server_cost_center"] = cc_name
        defaults["agent_number"] = self.agent_num.currentText().strip()
        defaults["work_offline"] = "1"
        save_defaults(defaults)
        
        try:
            from database.db import get_connection
            import hashlib
            conn = get_connection()
            cur = conn.cursor()

            # 1. Ensure Company exists
            cur.execute("SELECT id FROM companies WHERE name = ?", (comp_name,))
            comp_row = cur.fetchone()
            if comp_row:
                comp_id = comp_row[0]
            else:
                # Provide mandatory columns for the companies table
                abbr = "".join([w[0] for w in comp_name.split() if w])[:5].upper() or "POS"
                cur.execute("""
                    INSERT INTO companies (name, abbreviation, default_currency, country) 
                    OUTPUT INSERTED.id 
                    VALUES (?, ?, ?, ?)
                """, (comp_name, abbr, "USD", "Zimbabwe"))
                comp_id = int(cur.fetchone()[0])

            # 2. Ensure Warehouse exists
            cur.execute("SELECT id FROM warehouses WHERE name = ?", (wh_name,))
            wh_row = cur.fetchone()
            if not wh_row:
                cur.execute("INSERT INTO warehouses (name, company_id) OUTPUT INSERTED.id VALUES (?, ?)", (wh_name, comp_id))
                wh_id = int(cur.fetchone()[0])
            else:
                wh_id = wh_row[0]

            # 3. Ensure Cost Center exists
            cur.execute("SELECT id FROM cost_centers WHERE name = ?", (cc_name,))
            cc_row = cur.fetchone()
            if not cc_row:
                cur.execute("INSERT INTO cost_centers (name, company_id) OUTPUT INSERTED.id VALUES (?, ?)", (cc_name, comp_id))
                cc_id = int(cur.fetchone()[0])
            else:
                cc_id = cc_row[0]

            
            # 4. Ensure 'TawneyStardsDm' user exists and is configured
            cur.execute("SELECT id FROM users WHERE username = 'TawneyStardsDm'")
            row = cur.fetchone()
            
            pw_hash = hashlib.sha256("admin123".encode()).hexdigest()
            if row:
                cur.execute("""
                    UPDATE users SET 
                        company = ?, warehouse = ?, warehouse_id = ?, cost_center_id = ?, active = 1, password = ?, pin = '1234'
                    WHERE id = ?
                """, (comp_name, wh_name, wh_id, cc_id, pw_hash, row[0]))
            else:
                cur.execute("""
                    INSERT INTO users (username, password, pin, role, display_name, full_name, active, company, warehouse, warehouse_id, cost_center_id)
                    VALUES ('TawneyStardsDm', ?, '1234', 'admin', 'Administrator', 'Administrator', 1, ?, ?, ?, ?)
                """, (pw_hash, comp_name, wh_name, wh_id, cc_id))

            
            conn.commit()
            conn.close()
            print(f"[OfflineSetup] Successfully updated master tables for {comp_name}")
        except Exception as e:
            import traceback
            print(f"[OfflineSetup] Error updating master data:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "Database Error", f"Failed to update local master data: {e}")
            return # Don't accept if DB update failed

        self.accept()

# =============================================================================
# Settings Hub Dialog
# =============================================================================
class SettingsHubDialog(QDialog):
    """Premium settings launcher - shown after admin password is verified."""

    def __init__(self, login_ref, parent=None):
        super().__init__(parent)
        self._login = login_ref
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(380)
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)

        card = QFrame()
        card.setObjectName("shCard")
        card.setStyleSheet(f"QFrame#shCard {{ background:{WHITE}; border-radius:20px; }}")
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(50); shadow.setXOffset(0); shadow.setYOffset(12)
        shadow.setColor(QColor(13, 31, 60, 120))
        card.setGraphicsEffect(shadow)
        outer.addWidget(card)

        root = QVBoxLayout(card)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        hdr = QWidget()
        hdr.setFixedHeight(80)
        hdr.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 {NAVY}, stop:0.6 {NAVY_2}, stop:1 {NAVY_3});
                border-top-left-radius:20px; border-top-right-radius:20px;
            }}
        """)
        hh = QHBoxLayout(hdr)
        hh.setContentsMargins(22, 0, 16, 0)

        ico_lbl = QLabel()
        ico_lbl.setPixmap(qta.icon("fa5s.cog", color=WHITE).pixmap(22, 22))
        ico_lbl.setStyleSheet("background:transparent;")
        ttl_lbl = QLabel("System Settings")
        ttl_lbl.setFont(QFont("Segoe UI", 15, QFont.Bold))
        ttl_lbl.setStyleSheet(f"color:{WHITE}; background:transparent; letter-spacing:0.4px;")
        hh.addWidget(ico_lbl)
        hh.addSpacing(10)
        hh.addWidget(ttl_lbl)
        hh.addStretch()

        close_x = QPushButton("✕")
        close_x.setFixedSize(28, 28)
        close_x.setCursor(Qt.PointingHandCursor)
        close_x.setFocusPolicy(Qt.NoFocus)
        close_x.setStyleSheet(f"""
            QPushButton {{ background:rgba(255,255,255,0.15); color:{WHITE};
                border:none; border-radius:14px; font-size:12px; font-weight:bold; }}
            QPushButton:hover {{ background:rgba(255,255,255,0.28); }}
        """)
        close_x.clicked.connect(self.reject)
        hh.addWidget(close_x)
        root.addWidget(hdr)

        # Accent bar
        ab = QFrame(); ab.setFixedHeight(3)
        ab.setStyleSheet(f"""
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 {NAVY_3}, stop:0.3 {ACCENT}, stop:0.7 {ACCENT_H}, stop:1 {NAVY_3});
        """)
        root.addWidget(ab)

        # Cards body
        body = QWidget()
        body.setStyleSheet(f"background:{OFF_WHITE};")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(18, 18, 18, 18)
        bl.setSpacing(10)

        items = [
            ("Local POS Setup", "Set company, warehouse & cost center.", self._do_local_setup),
            ("Agent & Support", "Configure agent number & contact info.", self._do_local_setup),
            ("Mode Setup",      "Switch system modes.", self._do_mode_setup),
            ("Database",        "Configure SQL Server connection.",      self._do_database),
            ("License",         "Activate or view software license.",    self._do_license),
        ]

        for title, subtitle, handler in items:
            btn = QFrame()
            btn.setCursor(Qt.PointingHandCursor)
            btn.setObjectName("settingCard")
            btn.setStyleSheet(f"""
                QFrame#settingCard {{
                    background:{WHITE}; border-radius:12px;
                    border:1.5px solid {BORDER};
                }}
                QFrame#settingCard:hover {{
                    background:{LIGHT}; border-color:{ACCENT};
                }}
            """)
            btn.setFixedHeight(56)
            row = QHBoxLayout(btn)
            row.setContentsMargins(18, 0, 16, 0)
            row.setSpacing(10)

            # Text
            txt_col = QVBoxLayout(); txt_col.setSpacing(0)
            t1 = QLabel(title)
            t1.setFont(QFont("Segoe UI", 12, QFont.Bold))
            t1.setStyleSheet(f"color:{NAVY}; background:transparent;")
            t2 = QLabel(subtitle)
            t2.setFont(QFont("Segoe UI", 9))
            t2.setStyleSheet(f"color:{MUTED}; background:transparent;")
            txt_col.addStretch()
            txt_col.addWidget(t1)
            txt_col.addWidget(t2)
            txt_col.addStretch()

            arr = QLabel("›")
            arr.setStyleSheet(f"color:{MID}; font-size:20px; background:transparent;")

            row.addLayout(txt_col, 1)
            row.addWidget(arr)

            # Make the whole card clickable via mouse press
            btn.mousePressEvent = lambda _e, h=handler: h()
            bl.addWidget(btn)

        root.addWidget(body)

        # Footer
        ftr = QFrame()
        ftr.setFixedHeight(42)
        ftr.setStyleSheet(f"""
            background:{CREAM};
            border-bottom-left-radius:20px;
            border-bottom-right-radius:20px;
        """)
        fl = QHBoxLayout(ftr)
        fl.setContentsMargins(20, 0, 20, 0)
        note = QLabel("Admin access required to modify these settings.")
        note.setStyleSheet(f"color:{MUTED}; font-size:10px; background:transparent;")
        fl.addStretch(); fl.addWidget(note); fl.addStretch()
        root.addWidget(ftr)

    # ── handlers ──────────────────────────────────────────────────────────────
    def _do_local_setup(self):
        self.accept()
        self._login._open_quick_setup()

    def _do_mode_setup(self):
        self.accept()
        self._login._open_onboarding()

    def _do_database(self):
        self.accept()
        self._login._open_sql_settings()

    def _do_license(self):
        self.accept()
        self._login._open_license_dialog()


# =============================================================================
# Main Login Dialog
# =============================================================================
class LoginDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Havano POS")
        self.setFixedSize(850, 600)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.logged_in_user: dict | None  = None
        self.login_source:   str  | None  = None
        self._worker:        LoginWorker | None = None
        self._conn_worker:   ConnectivityWorker | None = None
        self._pin_buffer:    str = ""
        self.system_mode:    str = "frappe"
        self.default_db:     str = ""
        
        # 1. Primary check: get_system_mode() from company_defaults
        try:
            from services.credentials import get_system_mode
            self.system_mode = get_system_mode()
        except Exception:
            pass



        # Also grab the database name from sql_settings.json as a fallback default
        try:
            import json, os
            path = os.path.join("app_data", "sql_settings.json")
            if os.path.exists(path):
                with open(path, "r") as f:
                    data = json.load(f)
                    self.default_db = data.get("database", "")
        except Exception:
            pass

        # PIN setup state
        self._pin_setup_overlay: QWidget | None = None
        self._pin_setup_user:    dict = {}
        self._pin_setup_source:  str  = ""
        self._pin_setup_buf:     str  = ""
        self._pin_setup_step:    str  = "enter"
        self._pin_setup_first:   str  = ""

        self._build_ui()

        # Async connectivity check - never blocks UI
        self._refresh_connectivity()

        QApplication.instance().installEventFilter(self)

    # =========================================================================
    # Event filter
    # =========================================================================
    def eventFilter(self, obj, event):
        try:
            from PySide6.QtGui import QKeyEvent
            if event.type() == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
                key = event.key()

                # PIN setup overlay
                if self._pin_setup_overlay and self._pin_setup_overlay.isVisible():
                    if key in (Qt.Key_Return, Qt.Key_Enter):
                        self._pin_setup_confirm(); return True
                    elif key in (Qt.Key_Backspace, Qt.Key_Delete):
                        self._pin_setup_backspace(); return True
                    elif key == Qt.Key_Escape:
                        self._pin_setup_buf = ""
                        self._pin_setup_dots.set_filled(0); return True
                    elif Qt.Key_0 <= key <= Qt.Key_9:
                        self._pin_setup_press(str(key - Qt.Key_0)); return True
                    elif hasattr(event, "text") and event.text().isdigit():
                        self._pin_setup_press(event.text()); return True
                    return False

                # Normal PIN tab
                if hasattr(self, "_stack") and self._stack.currentIndex() == 0:
                    # Ignore if another modal dialog is active
                    active = QApplication.activeModalWidget()
                    if active and active != self:
                        return False
                    if key in (Qt.Key_Return, Qt.Key_Enter):
                        self._login_pin(); return True
                    elif key in (Qt.Key_Backspace, Qt.Key_Delete):
                        self._pin_backspace(); return True
                    elif key == Qt.Key_Escape:
                        self._pin_clear(); return True
                    elif Qt.Key_0 <= key <= Qt.Key_9:
                        self._pin_press(str(key - Qt.Key_0)); return True
                    elif hasattr(event, "text") and event.text().isdigit():
                        self._pin_press(event.text()); return True
        except Exception:
            pass
        ret = super().eventFilter(obj, event)
        return bool(ret) if ret is not None else False

    # =========================================================================
    # Window lifecycle
    # =========================================================================
    def closeEvent(self, event):
        self._cleanup()
        if not self.parent():
            QApplication.quit()
        event.accept()

    def reject(self):
        pass   # prevent Escape from dismissing

    def _cleanup(self):
        QApplication.instance().removeEventFilter(self)
        for w in (self._worker, self._conn_worker):
            if w:
                try:
                    if w.isRunning():
                        w.quit()
                        w.wait(500)
                except RuntimeError:
                    pass

    # =========================================================================
    # UI construction
    # =========================================================================
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet(f"QFrame#card {{ background:{WHITE}; border-radius:20px; }}")

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(60); shadow.setXOffset(0); shadow.setYOffset(16)
        shadow.setColor(QColor(13, 31, 60, 100))
        card.setGraphicsEffect(shadow)
        
        main_h = QHBoxLayout(card)
        main_h.setContentsMargins(0, 0, 0, 0)
        main_h.setSpacing(0)

        # ── Left Column ────────────────────────────────────────────────────────
        left_w = QWidget()
        left_w.setFixedWidth(280)
        left_w.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 {OFF_WHITE}, stop:1 #e6edf5);
                border-top-left-radius:20px; border-bottom-left-radius:20px;
                border-right: 1px solid {BORDER};
            }}
        """)
        left_l = QVBoxLayout(left_w)
        left_l.setContentsMargins(30, 40, 30, 30)
        left_l.setSpacing(15)

        # Logo
        import os
        from PySide6.QtGui import QPixmap
        from PySide6.QtCore import Qt
        
        logo_lbl = QLabel()
        logo_lbl.setAlignment(Qt.AlignCenter)
        logo_lbl.setFixedSize(64, 64)
        
        logo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "havano_new_blue.png"))
        pix = QPixmap(logo_path)
        if not pix.isNull():
            logo_lbl.setPixmap(pix.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            logo_lbl.setText("H")
            logo_lbl.setStyleSheet(f"background:{ACCENT}; color:{WHITE}; border-radius:16px; font-size:32px; font-weight:900;")
        
        logo_row = QHBoxLayout()
        logo_row.addStretch(); logo_row.addWidget(logo_lbl); logo_row.addStretch()
        
        title = QLabel("Havano POS")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"color:{NAVY}; font-size:24px; font-weight:800; background:transparent; margin-top:10px;")
        
        title_row = QHBoxLayout()
        title_row.addStretch(); title_row.addWidget(title); title_row.addStretch()
        
        left_l.addStretch()
        left_l.addLayout(logo_row)
        left_l.addLayout(title_row)
        left_l.addStretch()
        
        # Details column
        _app_version = "2.0.0"
        try:
            import main as _main_mod
            _app_version = getattr(_main_mod, "APP_VERSION", _app_version)
        except: pass
            
        try:
            from models.company_defaults import get_defaults
            d = get_defaults() or {}
            _sup_num = "+263 779 973 028"
            _agent_num = d.get("agent_number", "Agent")
        except:
            _sup_num = "+263 779 973 028"
            _agent_num = "Agent"
            
        if _sup_num == "0782168407":
            _sup_num = "+263 779 973 028"

        def add_info(label, value, link=False):
            w = QWidget(); w.setStyleSheet("background:transparent; border:none;")
            l = QVBoxLayout(w); l.setContentsMargins(0,0,0,0); l.setSpacing(4)
            lbl1 = QLabel(label); lbl1.setStyleSheet(f"color:{MUTED}; font-size:11px; font-weight:800; letter-spacing:1px;")
            lbl1.setAlignment(Qt.AlignCenter)
            
            if link:
                lbl2 = QLabel(f'<a href="https://{value}/" style="color:{ACCENT}; text-decoration:none; font-weight:bold;">{value}</a>')
                lbl2.setOpenExternalLinks(True)
            else:
                lbl2 = QLabel(value)
                
            lbl2.setAlignment(Qt.AlignCenter)
            lbl2.setStyleSheet(f"color:{NAVY_2}; font-size:15px; font-weight:700;")
            lbl2.setWordWrap(True)
            l.addWidget(lbl1); l.addWidget(lbl2)
            left_l.addWidget(w)
            left_l.addStretch()

        if _agent_num and str(_agent_num).strip().lower() != "agent":
            add_info("AGENT NUMBER", _agent_num)
            
        add_info("SUPPORT & WHATSAPP", _sup_num)
        add_info("SALES", "+263 778 078 440")
        add_info("EMAIL ADDRESS", "support@havanoerp.com")
        add_info("WEBSITE", "www.havanoerp.com", link=True)
        
        # ── Download Progress ──────────────────────────────────────────────────
        self.download_lbl = QLabel("")
        self.download_lbl.setStyleSheet(f"color:{SUCCESS}; font-size:13px; font-weight:bold; margin-top:20px;")
        self.download_lbl.setAlignment(Qt.AlignCenter)
        self.download_lbl.hide()
        left_l.addWidget(self.download_lbl)

        try:
            from updater import update_notifier
            def _on_update_progress_login(val):
                self.download_lbl.setText(f"Downloading update... {val}%")
                self.download_lbl.show()

            def _on_update_finished_login():
                self.download_lbl.setText("Update ready to install!")
                self.download_lbl.show()

            update_notifier.progress.connect(_on_update_progress_login)
            update_notifier.finished.connect(_on_update_finished_login)
        except Exception:
            pass


        # ── Right Column ────────────────────────────────────────────────────────
        right_w = QWidget()
        vl = QVBoxLayout(right_w)
        vl.setSpacing(0); vl.setContentsMargins(0, 0, 0, 0)
        
        # Top row with status bar and close btn
        top_row = QHBoxLayout()
        top_row.setContentsMargins(40, 16, 16, 0)
        
        # Status bar items
        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet(f"color:{MID}; font-size:7px; background:transparent;")
        self._status_lbl = QLabel("Checking connection…")
        self._status_lbl.setStyleSheet(f"color:{MUTED}; font-size:11px; background:transparent;")
        
        top_row.addWidget(self._status_dot)
        top_row.addWidget(self._status_lbl)
        top_row.addStretch()
        
        self.close_btn = QPushButton()
        self.close_btn.setIcon(qta.icon("fa5s.times", color=MUTED))
        self.close_btn.setFixedSize(32, 32)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setFocusPolicy(Qt.NoFocus)
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:none; border-radius:16px;
            }}
            QPushButton:hover   {{ background:{LIGHT}; }}
            QPushButton:pressed {{ background:{BORDER}; }}
        """)
        self.close_btn.clicked.connect(self.close)
        top_row.addWidget(self.close_btn)
        vl.addLayout(top_row)
        
        vl.addSpacing(10)

        # Tab row
        tab_row = QWidget()
        tab_row.setStyleSheet(f"background:transparent;")
        tl = QHBoxLayout(tab_row)
        tl.setContentsMargins(40, 10, 40, 0); tl.setSpacing(8)
        self._pin_tab   = QPushButton("PIN")
        self._pin_tab.setIcon(qta.icon("fa5s.hashtag"))
        self._email_tab = QPushButton("Email Login")
        self._email_tab.setIcon(qta.icon("fa5s.key"))
        for b in (self._pin_tab, self._email_tab):
            b.setFixedHeight(36); b.setCursor(Qt.PointingHandCursor)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            b.setFocusPolicy(Qt.NoFocus)
        self._pin_tab.clicked.connect(lambda: self._switch_mode(0))
        self._email_tab.clicked.connect(lambda: self._switch_mode(1))
        tl.addWidget(self._pin_tab)
        if self.system_mode != "offline":
            tl.addWidget(self._email_tab)
        vl.addWidget(tab_row)

        # Stack
        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background:transparent;")
        self._stack.addWidget(self._build_pin_page())
        self._stack.addWidget(self._build_email_page())
        vl.addWidget(self._stack, 1)

        # Error label
        err_w = QWidget(); err_w.setStyleSheet(f"background:transparent;")
        el = QHBoxLayout(err_w); el.setContentsMargins(40, 0, 40, 10)
        self.error_label = QLabel("")
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet(f"""
            color:{WHITE}; background:{DANGER}; font-size:12px; font-weight:bold;
            border-radius:8px; padding:8px 14px;
        """)
        self.error_label.hide()
        el.addWidget(self.error_label)
        vl.addWidget(err_w)

        # Settings gear
        gear_w = QWidget(); gear_w.setStyleSheet(f"background:transparent;")
        gear_l = QHBoxLayout(gear_w)
        gear_l.setContentsMargins(40, 0, 20, 20); gear_l.setSpacing(0)
        
        ver_lbl = QLabel(f"Version {_app_version}")
        ver_lbl.setStyleSheet(f"color:{MUTED}; font-size:11px; font-weight:bold; background:transparent;")
        gear_l.addWidget(ver_lbl)
        
        gear_l.addStretch()

        self._gear_btn = QPushButton()
        self._gear_btn.setIcon(qta.icon("fa5s.cog", color=MUTED))
        self._gear_btn.setIconSize(QSize(16, 16))
        self._gear_btn.setFixedSize(36, 36)
        self._gear_btn.setCursor(Qt.PointingHandCursor)
        self._gear_btn.setFocusPolicy(Qt.NoFocus)
        self._gear_btn.setToolTip("System Settings (Admin only)")
        self._gear_btn.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:none; border-radius:18px;
            }}
            QPushButton:hover   {{ background:{LIGHT}; }}
            QPushButton:pressed {{ background:{BORDER}; }}
        """)
        self._gear_btn.clicked.connect(self._open_settings_hub)
        gear_l.addWidget(self._gear_btn)
        vl.addWidget(gear_w)
        
        main_h.addWidget(left_w)
        main_h.addWidget(right_w)

        root.addWidget(card)
        self._switch_mode(0)

    # =========================================================================
    # SQL settings
    # =========================================================================
    # =========================================================================
    # Settings Hub (gear icon)
    # =========================================================================
    def _open_settings_hub(self):
        """Ask for admin password, then open the Settings Hub dialog."""
        import hashlib

        # ── Password prompt ───────────────────────────────────────────────────
        pwd_dlg = QDialog(self)
        pwd_dlg.setWindowTitle("Admin Access")
        pwd_dlg.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        pwd_dlg.setAttribute(Qt.WA_TranslucentBackground)
        pwd_dlg.setFixedWidth(320)

        outer = QVBoxLayout(pwd_dlg)
        outer.setContentsMargins(12, 12, 12, 12)
        card2 = QFrame()
        card2.setObjectName("pwCard")
        card2.setStyleSheet(f"QFrame#pwCard {{ background:{WHITE}; border-radius:16px; }}")
        sh2 = QGraphicsDropShadowEffect()
        sh2.setBlurRadius(40); sh2.setXOffset(0); sh2.setYOffset(10)
        sh2.setColor(QColor(13,31,60,100))
        card2.setGraphicsEffect(sh2)
        outer.addWidget(card2)

        cl2 = QVBoxLayout(card2)
        cl2.setContentsMargins(24, 20, 24, 20)
        cl2.setSpacing(12)

        ph = QHBoxLayout()
        p_ico = QLabel()
        p_ico.setPixmap(qta.icon("fa5s.lock", color=NAVY).pixmap(18, 18))
        p_ico.setStyleSheet("background:transparent;")
        p_ttl = QLabel("Admin Access Required")
        p_ttl.setFont(QFont("Segoe UI", 13, QFont.Bold))
        p_ttl.setStyleSheet(f"color:{NAVY}; background:transparent;")
        ph.addWidget(p_ico); ph.addSpacing(8); ph.addWidget(p_ttl); ph.addStretch()
        cl2.addLayout(ph)

        p_sub = QLabel("Enter the admin password to access system settings.")
        p_sub.setWordWrap(True)
        p_sub.setStyleSheet(f"color:{MUTED}; font-size:11px; background:transparent;")
        cl2.addWidget(p_sub)

        pw_edit = QLineEdit()
        pw_edit.setPlaceholderText("Admin password…")
        pw_edit.setEchoMode(QLineEdit.Password)
        pw_edit.setFixedHeight(42)
        pw_edit.setStyleSheet(f"""
            QLineEdit {{
                background:{OFF_WHITE}; color:{NAVY};
                border:1.5px solid {BORDER}; border-radius:10px;
                padding-left: 12px; padding-right: 12px; font-size:15px;
            }}
            QLineEdit:focus {{ border-color:{ACCENT}; background:{WHITE}; }}
        """)
        cl2.addWidget(pw_edit)

        err_lbl = QLabel("")
        err_lbl.setStyleSheet(f"color:{DANGER}; font-size:11px; background:transparent;")
        err_lbl.hide()
        cl2.addWidget(err_lbl)

        btn_row2 = QHBoxLayout()
        cancel2 = QPushButton("Cancel")
        cancel2.setFixedHeight(38)
        cancel2.setMinimumWidth(100)
        cancel2.setCursor(Qt.PointingHandCursor)
        cancel2.setStyleSheet(f"""
            QPushButton {{
                background:{LIGHT}; color:{NAVY}; border:none; border-radius:9px;
                font-weight:600; font-size:12px; padding: 0 18px;
            }}
            QPushButton:hover {{ background:{BORDER}; }}
        """)
        cancel2.clicked.connect(pwd_dlg.reject)

        unlock2 = QPushButton("Unlock")
        unlock2.setFixedHeight(38)
        unlock2.setMinimumWidth(110)
        unlock2.setCursor(Qt.PointingHandCursor)
        unlock2.setDefault(True)
        unlock2.setStyleSheet(f"""
            QPushButton {{
                background:{ACCENT}; color:{WHITE}; border:none; border-radius:9px;
                font-weight:700; font-size:12px; padding: 0 20px;
            }}
            QPushButton:hover {{ background:{ACCENT_H}; }}
        """)
        btn_row2.addWidget(cancel2); btn_row2.addStretch(); btn_row2.addWidget(unlock2)
        cl2.addLayout(btn_row2)

        def _attempt_unlock():
            pwd = pw_edit.text().strip()
            if not pwd:
                err_lbl.setText("Please enter a password."); err_lbl.show(); return
            pw_hash = hashlib.sha256(pwd.encode()).hexdigest()
            try:
                from database.db import get_connection
                conn = get_connection()
                cur  = conn.cursor()
                cur.execute(
                    "SELECT id FROM users WHERE role='admin' AND (password=? OR pin=?) AND active=1",
                    (pw_hash, pwd)
                )
                row = cur.fetchone()
                conn.close()
                if row:
                    pwd_dlg.accept()
                else:
                    err_lbl.setText("Incorrect password - admin access denied."); err_lbl.show()
            except Exception as ex:
                err_lbl.setText(f"DB error: {ex}"); err_lbl.show()

        unlock2.clicked.connect(_attempt_unlock)
        pw_edit.returnPressed.connect(_attempt_unlock)

        if pwd_dlg.exec() == QDialog.Accepted:
            SettingsHubDialog(self, parent=self).exec()

    def _open_sql_settings(self):
        for mod_path in ("views.dialogs.sql_settings_dialog", "sql_settings_dialog"):
            try:
                import importlib
                mod = importlib.import_module(mod_path)
                mod.SqlSettingsDialog(self).exec()
                return
            except ImportError:
                continue
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(self, "Not Found",
                            "sql_settings_dialog.py could not be located.\n"
                            "Place it in views/dialogs/ and restart.")

    def _open_quick_setup(self):
        if OfflineSetupDialog(self).exec():
            if hasattr(self, "password_input"):
                self.password_input.setFocus()

    def _open_onboarding(self):
        try:
            from views.dialogs.onboarding_dialog import OnboardingDialog
            dlg = OnboardingDialog(self)
            if dlg.exec() == QDialog.Accepted:
                # Open SQL Settings immediately so the user can configure the new mode's DB or wipe data
                from views.dialogs.sql_settings_dialog import SqlSettingsDialog
                sql_dlg = SqlSettingsDialog(self)
                sql_dlg.exec()

                QMessageBox.information(
                    self, "Mode Changed", 
                    "System mode has been updated. The application will now restart to apply changes."
                )
                import sys, subprocess, os
                exe = sys.executable
                venv_path = os.environ.get("VIRTUAL_ENV")
                if venv_path:
                    venv_exe = os.path.join(venv_path, "Scripts", "python.exe") if os.name == "nt" else os.path.join(venv_path, "bin", "python")
                    if os.path.exists(venv_exe):
                        exe = venv_exe
                elif hasattr(sys, "real_prefix") or (hasattr(sys, "base_prefix") and sys.prefix != sys.base_prefix):
                    venv_exe = os.path.join(sys.prefix, "Scripts", "python.exe") if os.name == "nt" else os.path.join(sys.prefix, "bin", "python")
                    if os.path.exists(venv_exe):
                        exe = venv_exe
                subprocess.Popen([exe] + sys.argv)
                os._exit(0)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open Mode Setup:\n{e}")

    def _open_license_dialog(self):
        try:
            from views.dialogs.license_dialog import LicenseDialog
            dlg = LicenseDialog()
            dlg.exec()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open License window:\n{e}")

    # =========================================================================
    # PIN page
    # =========================================================================
    def _build_pin_page(self) -> QWidget:
        page = QWidget(); page.setStyleSheet(f"background:{OFF_WHITE};")
        pl = QVBoxLayout(page)
        pl.setContentsMargins(28, 18, 28, 12); pl.setSpacing(14)
        pl.addStretch(1)

        dot_card = QWidget()
        dot_card.setStyleSheet(f"""
            background:{WHITE}; border-radius:14px; border:1.5px solid {BORDER};
        """)
        dot_card.setFixedHeight(58)
        dcl = QHBoxLayout(dot_card); dcl.setContentsMargins(0, 0, 0, 0)
        self._pin_dots = PinDots(4)
        dcl.addStretch(); dcl.addWidget(self._pin_dots); dcl.addStretch()
        pl.addWidget(dot_card)

        has_default_pin = False
        try:
            from database.db import get_connection
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT pin FROM users WHERE username='admin'")
            row = cur.fetchone()
            if row and row[0] == '1234':
                has_default_pin = True
            conn.close()
        except Exception:
            pass

        setup_lbl = QLabel("Default Admin PIN: 1234")
        setup_lbl.setAlignment(Qt.AlignCenter)
        setup_lbl.setStyleSheet(f"color:{MUTED}; font-size:11px; font-weight:bold; background:transparent;")
        if not has_default_pin:
            setup_lbl.hide()
        pl.addWidget(setup_lbl)

        grid_w = QWidget(); grid_w.setStyleSheet("background:transparent;")
        grid = QGridLayout(grid_w); grid.setSpacing(10); grid.setContentsMargins(0,0,0,0)

        keys = [
            ("1","d"),("2","d"),("3","d"),
            ("4","d"),("5","d"),("6","d"),
            ("7","d"),("8","d"),("9","d"),
            ("","b"), ("0","d"),("","e"),
        ]
        for i, (label, kind) in enumerate(keys):
            btn = self._make_numpad_btn(label, kind,
                                        on_digit=self._pin_press,
                                        on_back=self._pin_backspace,
                                        on_enter=self._login_pin,
                                        h=52)
            grid.addWidget(btn, i // 3, i % 3)

        pl.addWidget(grid_w)
        pl.addStretch(1)
        return page

    # =========================================================================
    # Email / Password page
    # =========================================================================
    def _build_email_page(self) -> QWidget:
        page = QWidget(); page.setStyleSheet(f"background:{OFF_WHITE};")
        pl = QVBoxLayout(page)
        pl.setContentsMargins(28, 20, 28, 12); pl.setSpacing(6)
        pl.addStretch(1)



        pl.addWidget(self._field_lbl("USERNAME / EMAIL"))
        pl.addSpacing(4)
        
        un_container = QWidget(); un_container.setStyleSheet("background:transparent;")
        un_row = QHBoxLayout(un_container); un_row.setContentsMargins(0,0,0,0); un_row.setSpacing(0)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter your username or email")
        self.username_input.setFixedHeight(48)
        self.username_input.setStyleSheet(f"""
            QLineEdit {{
                background:{WHITE}; color:{NAVY};
                border:1.5px solid {BORDER};
                border-radius:12px;
                padding:0 14px; font-size:14px;
            }}
            QLineEdit:focus {{ border:1.5px solid {ACCENT}; }}
            QLineEdit:hover {{ border:1.5px solid {MID};    }}
        """)
        
        self.username_input.returnPressed.connect(lambda: self.password_input.setFocus())

        un_row.addWidget(self.username_input, 1)
        pl.addWidget(un_container)
        pl.addSpacing(14)

        pl.addWidget(self._field_lbl("PASSWORD"))
        pl.addSpacing(4)

        pw_container = QWidget(); pw_container.setStyleSheet("background:transparent;")
        pw_row = QHBoxLayout(pw_container); pw_row.setContentsMargins(0,0,0,0); pw_row.setSpacing(0)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Enter your password")
        self.password_input.setFixedHeight(48)
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setStyleSheet(f"""
            QLineEdit {{
                background:{WHITE}; color:{NAVY};
                border:1.5px solid {BORDER};
                border-top-left-radius:12px; border-bottom-left-radius:12px;
                border-top-right-radius:0; border-bottom-right-radius:0;
                padding:0 14px; font-size:14px;
            }}
            QLineEdit:focus {{ border:1.5px solid {ACCENT}; }}
            QLineEdit:hover {{ border:1.5px solid {MID};    }}
        """)
        self.password_input.returnPressed.connect(self._login_email)

        self._eye_btn = QPushButton()
        self._eye_btn.setIcon(qta.icon("fa5s.eye", color=MUTED))
        self._eye_btn.setFixedSize(48, 48)
        self._eye_btn.setCursor(Qt.PointingHandCursor)
        self._eye_btn.setCheckable(True)
        self._eye_btn.setFocusPolicy(Qt.NoFocus)
        self._eye_btn.setStyleSheet(f"""
            QPushButton {{
                background:{WHITE}; border:1.5px solid {BORDER};
                border-left:none;
                border-top-right-radius:12px; border-bottom-right-radius:12px;
            }}
            QPushButton:hover   {{ background:{LIGHT}; }}
            QPushButton:checked {{ background:{LIGHT}; color:{ACCENT}; }}
        """)
        self._eye_btn.toggled.connect(
            lambda c: self.password_input.setEchoMode(
                QLineEdit.Normal if c else QLineEdit.Password
            )
        )
        pw_row.addWidget(self.password_input, 1)
        pw_row.addWidget(self._eye_btn)
        pl.addWidget(pw_container)
        pl.addSpacing(18)

        self._email_btn = QPushButton("Sign In")
        self._email_btn.setFixedHeight(52)
        self._email_btn.setCursor(Qt.PointingHandCursor)
        self._email_btn.setFocusPolicy(Qt.NoFocus)
        self._set_btn_normal(self._email_btn)
        self._email_btn.clicked.connect(self._login_email)
        pl.addWidget(self._email_btn)
        pl.addStretch(1)
        return page

    # =========================================================================
    # Shared numpad button factory
    # =========================================================================
    def _make_numpad_btn(self, label, kind, *,
                         on_digit, on_back, on_enter, h=48) -> QPushButton:
        btn = QPushButton(label)
        btn.setFixedSize(108, h)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFont(QFont("Segoe UI", 16, QFont.Bold))
        btn.setFocusPolicy(Qt.NoFocus)

        if kind == "d":
            btn.setStyleSheet(f"""
                QPushButton {{
                    background:{WHITE}; color:{NAVY};
                    border:1.5px solid {BORDER}; border-radius:12px;
                    font-size:18px; font-weight:bold;
                }}
                QPushButton:hover   {{ background:{LIGHT}; border-color:{ACCENT}; }}
                QPushButton:pressed {{ background:{ACCENT}; color:{WHITE}; border-color:{ACCENT}; }}
            """)
            btn.clicked.connect(lambda _, d=label: on_digit(d))
        elif kind == "b":
            btn.setIcon(qta.icon("fa5s.backspace", color=MUTED))
            btn.setIconSize(QSize(22, 22))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background:{LIGHT}; border:1.5px solid {BORDER}; border-radius:12px;
                }}
                QPushButton:hover   {{ background:{BORDER}; }}
                QPushButton:pressed {{ background:{NAVY}; }}
            """)
            btn.clicked.connect(on_back)
        elif kind == "e":
            btn.setIcon(qta.icon("fa5s.check", color=WHITE))
            btn.setIconSize(QSize(22, 22))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background:{ACCENT}; border:none; border-radius:12px;
                }}
                QPushButton:hover   {{ background:{ACCENT_H}; }}
                QPushButton:pressed {{ background:{NAVY_2}; }}
            """)
            btn.clicked.connect(on_enter)
        return btn

    # =========================================================================
    # Tab switching
    # =========================================================================
    def _switch_mode(self, idx: int):
        self._stack.setCurrentIndex(idx)
        self.error_label.hide()
        active   = (f"QPushButton {{ background:{ACCENT}; color:{WHITE}; border:2px solid {ACCENT_H}; "
                    "border-radius:10px; font-size:13px; font-weight:bold; padding: 4px 12px; }}")
        inactive = (f"QPushButton {{ background:{WHITE}; color:{MUTED}; "
                    f"border:2px solid {BORDER}; border-radius:10px; font-size:13px; font-weight:bold; padding: 4px 12px; }}"
                    f"QPushButton:hover {{ background:{LIGHT}; color:{NAVY}; border-color:{MID}; }}")
        self._pin_tab.setStyleSheet(active   if idx == 0 else inactive)
        self._email_tab.setStyleSheet(active if idx == 1 else inactive)
        (self if idx == 0 else self.username_input).setFocus()

    # =========================================================================
    # PIN login
    # =========================================================================
    def _pin_press(self, digit: str):
        if len(self._pin_buffer) >= 4:
            return
        self._pin_buffer += digit
        self._pin_dots.set_filled(len(self._pin_buffer))
        self.error_label.hide()
        if len(self._pin_buffer) == 4:
            QTimer.singleShot(120, self._login_pin)

    def _pin_backspace(self):
        self._pin_buffer = self._pin_buffer[:-1]
        self._pin_dots.set_filled(len(self._pin_buffer))
        self.error_label.hide()

    def _pin_clear(self):
        self._pin_buffer = ""
        self._pin_dots.set_filled(0)
        self.error_label.hide()

    def _login_pin(self):
        pin = self._pin_buffer.strip()
        if not pin:
            self._show_error("Please enter your PIN.")
            return
        try:
            from models.user import authenticate_by_pin
            user = authenticate_by_pin(pin)
        except Exception as e:
            import traceback; traceback.print_exc()
            self._show_error(f"Local DB error: {e}")
            return
        if not user:
            self._show_error("Incorrect PIN.  Please try again.")
            self._pin_clear(); self._shake()
            return
        self._validate_and_accept(user, "pin")

    # =========================================================================
    # Email / Password login
    # =========================================================================
    def _login_email(self):
        if self._worker is not None:
            try:
                if self._worker.isRunning():
                    return
            except RuntimeError:
                self._worker = None
        u = self.username_input.text().strip()
        p = self.password_input.text().strip()
        db = ""
        
        if not u or not p:
            self._show_error("Please enter your username and password.")
            return

        self._set_btn_loading(self._email_btn)
        self.error_label.hide()

        if self._local_catalogue_is_empty():
            self._set_status(
                "First-time setup - signing in and syncing catalogue…",
                "#c05a00",
            )

        self._worker = LoginWorker(u, p, db, self.system_mode)
        self._worker.finished.connect(self._on_login_done)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.start()

    def _local_catalogue_is_empty(self) -> bool:
        try:
            from database.db import get_connection
            conn = get_connection()
            cur  = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM products")
            n = int(cur.fetchone()[0] or 0)
            conn.close()
            return n == 0
        except Exception:
            return False

    def _on_login_done(self, result):
        try:
            print(f"DEBUG: Entering _on_login_done with result: {result.keys() if isinstance(result, dict) else 'Not a dict'}")
            # Do NOT set self._worker = None here; it destroys the PyObject wrapper 
            # while the C++ thread is still in the middle of emitting this very signal, causing a segfault!
            # self._worker = None 
            self._set_btn_normal(self._email_btn)

            if result.get("success"):
                user   = result["user"]
                source = result.get("source", "online")
                if source == "offline":
                    self._show_info("Offline mode - using local account.")
                self._validate_and_accept(user, source)
                return

            # ── Map error to a user-friendly message ─────────────────────────────
            err    = result.get("error", "Login failed.")
            source = result.get("source", "")

            # Always show the real error for transparency, especially for Odoo setup
            display = f"Login Failed: {err}"
            
            if "timeout" in err.lower() or source == "timeout":
                display = "Server took too long to respond - trying local account…"
                # Transparent retry with local-only flag
                self._try_local_fallback_after_timeout(
                    self.username_input.text().strip(),
                    self.password_input.text().strip(),
                )
                return
            elif source in ("offline", "local_error"):
                display = ("No internet connection and no matching local account found.\n"
                           "Check your credentials or connect to the network.")
            else:
                display = err

            self._show_error(display)
            self._shake()
            self.password_input.clear()
            self.password_input.setFocus()
            # Refresh connectivity status quietly
            self._refresh_connectivity()
        except Exception as e:
            import traceback
            print(f"CRASH IN _on_login_done: {traceback.format_exc()}")

    def _try_local_fallback_after_timeout(self, username: str, password: str):
        """
        Silent local-DB check shown as a second chance after a server timeout.
        Tries the same function-name chain as LoginWorker._try_local().
        """
        import hashlib

        user = None

        # Strategy 1 - authenticate_local()
        try:
            from models.user import authenticate_local
            user = authenticate_local(username, password)
        except ImportError:
            pass
        except Exception as e:
            print(f"[login] fallback authenticate_local: {e}")

        # Strategy 2 - authenticate()
        if user is None:
            try:
                from models.user import authenticate
                user = authenticate(username, password)
            except ImportError:
                pass
            except Exception as e:
                print(f"[login] fallback authenticate: {e}")

        # Strategy 3 - raw SQL Server query
        if user is None:
            try:
                from database.db import get_connection
                pw_hash = hashlib.sha256(password.encode()).hexdigest()
                conn = get_connection()
                cur  = conn.cursor()
                cur.execute(
                    "SELECT TOP 1 id, username, email, full_name, role, "
                    "           warehouse, company, pin, active "
                    "FROM users "
                    "WHERE (username=? OR email=?) AND password_hash=? AND active=1",
                    (username, username, pw_hash),
                )
                row = cur.fetchone()
                conn.close()
                if row:
                    cols = ["id", "username", "email", "full_name", "role",
                            "warehouse", "company", "pin", "active"]
                    user = dict(zip(cols, row))
            except Exception as e:
                print(f"[login] fallback raw DB: {e}")

        if user:
            self._show_info("Server slow - logged in with saved local account.")
            self._validate_and_accept(user, "offline")
            return

        self._show_error(
            "Server timed out and no local account matched.\n"
            "Please check your internet connection and try again."
        )
        self._shake()
        self.password_input.clear()
        self.password_input.setFocus()

    # =========================================================================
    # Validate + accept gate
    # =========================================================================
    def _validate_and_accept(self, user: dict, source: str):
        print(f"[login] _validate_and_accept  source={source!r}  "
              f"user={user.get('username', user.get('email'))!r}")

        if not user.get("active", True):
            self._show_error("Your account has been disabled.  Contact your administrator.")
            self._shake(); self._pin_clear()
            return

        # Cost Center / Warehouse check (relaxed non-blocking notice)
        cost_center = (user.get("cost_center") or "").strip()
        warehouse   = (user.get("warehouse")   or "").strip()
        if not cost_center or not warehouse:
            print(f"[login] ⚠️ Notice: User '{user.get('username')}' has empty cost_center='{cost_center}' or warehouse='{warehouse}'. Proceeding with defaults.")

        # PIN check - populate from local DB if API didn't provide it
        if not (user.get("pin") or "").strip():
            user["pin"] = self._fetch_local_pin(user)

        pin_val = (user.get("pin") or "").strip()
        if source in ("online", "offline", "pin") and (not pin_val or pin_val == "1234"):
            self._prompt_set_pin(user, source)
            return

        self._accept_user(user, source)

    def _fetch_local_pin(self, user: dict) -> str:
        """Look up an existing PIN in the local SQL Server DB for this user."""
        try:
            from database.db import get_connection
            email    = (user.get("email")       or "").strip()
            frappe   = (user.get("name") or user.get("frappe_user") or "").strip()
            username = (user.get("username")    or "").strip()
            conn = get_connection()
            cur  = conn.cursor()
            cur.execute(
                "SELECT TOP 1 pin FROM users "
                "WHERE (email=? AND email<>'') "
                "   OR (frappe_user=? AND frappe_user<>'') "
                "   OR username=?",
                (email, frappe, username),
            )
            row = cur.fetchone()
            conn.close()
            if row and row[0]:
                print(f"[login] Found existing local PIN for {username!r}")
                return row[0]
        except Exception as e:
            print(f"[login] [!]  _fetch_local_pin: {e}")
        return ""

    # =========================================================================
    # PIN setup overlay
    # =========================================================================
    def _prompt_set_pin(self, user: dict, source: str):
        print("[login] _prompt_set_pin")
        self._pin_setup_user   = user
        self._pin_setup_source = source
        self._pin_setup_buf    = ""
        self._pin_setup_step   = "enter"
        self._pin_setup_first  = ""

        overlay = QWidget(self)
        overlay.setObjectName("pinSetupOverlay")
        overlay.setGeometry(0, 0, self.width(), self.height())
        overlay.setStyleSheet(
            f"QWidget#pinSetupOverlay {{ background:{WHITE}; border-radius:20px; }}"
        )

        root = QVBoxLayout(overlay)
        root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

        # Header
        hdr = QWidget(); hdr.setFixedHeight(120)
        hdr.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 {NAVY}, stop:0.6 {NAVY_2}, stop:1 {NAVY_3});
                border-top-left-radius:20px; border-top-right-radius:20px;
            }}
        """)
        hl = QVBoxLayout(hdr); hl.setContentsMargins(20,16,20,16); hl.setSpacing(4)

        self._pin_setup_title = QLabel("Create Your PIN")
        self._pin_setup_title.setAlignment(Qt.AlignCenter)
        self._pin_setup_title.setStyleSheet(
            f"color:{WHITE}; font-size:20px; font-weight:800; background:transparent;"
        )
        hl.addWidget(self._pin_setup_title)

        self._pin_setup_sub = QLabel("Enter a 4-digit PIN for quick login next time")
        self._pin_setup_sub.setAlignment(Qt.AlignCenter)
        self._pin_setup_sub.setWordWrap(True)
        self._pin_setup_sub.setStyleSheet(f"color:{MID}; font-size:11px; background:transparent;")
        hl.addWidget(self._pin_setup_sub)
        root.addWidget(hdr)

        accent = QFrame(); accent.setFixedHeight(3)
        accent.setStyleSheet(f"""
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 {NAVY_3}, stop:0.3 {ACCENT},
                stop:0.7 {ACCENT_H}, stop:1 {NAVY_3});
        """)
        root.addWidget(accent)

        body = QWidget(); body.setStyleSheet(f"background:{OFF_WHITE};")
        bl = QVBoxLayout(body); bl.setContentsMargins(28,20,28,16); bl.setSpacing(14)

        dot_card = QWidget()
        dot_card.setStyleSheet(
            f"background:{WHITE}; border-radius:14px; border:1.5px solid {BORDER};"
        )
        dot_card.setFixedHeight(58)
        dcl = QHBoxLayout(dot_card); dcl.setContentsMargins(0,0,0,0)
        self._pin_setup_dots = PinDots(4)
        dcl.addStretch(); dcl.addWidget(self._pin_setup_dots); dcl.addStretch()
        bl.addWidget(dot_card)

        self._pin_setup_err = QLabel("")
        self._pin_setup_err.setAlignment(Qt.AlignCenter)
        self._pin_setup_err.setWordWrap(True)
        self._pin_setup_err.setStyleSheet(f"""
            color:{WHITE}; background:{DANGER}; font-size:11px; font-weight:bold;
            border-radius:8px; padding:5px 12px;
        """)
        self._pin_setup_err.hide()
        bl.addWidget(self._pin_setup_err)

        grid_w = QWidget(); grid_w.setStyleSheet("background:transparent;")
        grid = QGridLayout(grid_w); grid.setSpacing(10); grid.setContentsMargins(0,0,0,0)

        keys = [
            ("1","d"),("2","d"),("3","d"),
            ("4","d"),("5","d"),("6","d"),
            ("7","d"),("8","d"),("9","d"),
            ("","b"), ("0","d"),("","e"),
        ]
        for i, (label, kind) in enumerate(keys):
            btn = self._make_numpad_btn(label, kind,
                                        on_digit=self._pin_setup_press,
                                        on_back=self._pin_setup_backspace,
                                        on_enter=self._pin_setup_confirm,
                                        h=48)
            grid.addWidget(btn, i // 3, i % 3)

        bl.addWidget(grid_w)
        root.addWidget(body, 1)

        footer = QWidget(); footer.setFixedHeight(44)
        footer.setStyleSheet(f"""
            background:{CREAM}; border-bottom-left-radius:20px;
            border-bottom-right-radius:20px;
        """)
        fl = QHBoxLayout(footer); fl.setContentsMargins(0,0,0,0)
        skip_btn = QPushButton("Skip - I'll set my PIN later")
        skip_btn.setCursor(Qt.PointingHandCursor); skip_btn.setFocusPolicy(Qt.NoFocus)
        skip_btn.setStyleSheet(f"""
            QPushButton {{ background:transparent; color:{MUTED}; border:none; font-size:11px; }}
            QPushButton:hover {{ color:{NAVY}; text-decoration:underline; }}
        """)
        skip_btn.clicked.connect(lambda: self._finish_pin_setup(overlay, save=False))
        fl.addWidget(skip_btn, alignment=Qt.AlignCenter)
        root.addWidget(footer)

        overlay.show()
        self._pin_setup_overlay = overlay

    def _pin_setup_press(self, digit: str):
        if len(self._pin_setup_buf) >= 4:
            return
        self._pin_setup_buf += digit
        self._pin_setup_dots.set_filled(len(self._pin_setup_buf))
        self._pin_setup_err.hide()
        if len(self._pin_setup_buf) == 4:
            QTimer.singleShot(120, self._pin_setup_confirm)

    def _pin_setup_backspace(self):
        self._pin_setup_buf = self._pin_setup_buf[:-1]
        self._pin_setup_dots.set_filled(len(self._pin_setup_buf))

    def _pin_setup_confirm(self):
        buf = self._pin_setup_buf.strip()
        if len(buf) < 4:
            self._pin_setup_err.setText("PIN must be 4 digits.")
            self._pin_setup_err.show(); return

        if self._pin_setup_step == "enter":
            self._pin_setup_first = buf
            self._pin_setup_buf   = ""
            self._pin_setup_step  = "confirm"
            self._pin_setup_dots.set_filled(0)
            self._pin_setup_title.setText("Confirm Your PIN")
            self._pin_setup_sub.setText("Enter the same PIN again to confirm")
            self._pin_setup_err.hide()
        else:
            if buf != self._pin_setup_first:
                self._pin_setup_buf   = ""
                self._pin_setup_step  = "enter"
                self._pin_setup_first = ""
                self._pin_setup_dots.set_filled(0)
                self._pin_setup_title.setText("Create Your PIN")
                self._pin_setup_sub.setText("PINs didn't match - please try again")
                self._pin_setup_err.setText("PINs did not match - starting over.")
                self._pin_setup_err.show()
                return
            self._finish_pin_setup(self._pin_setup_overlay, save=True, pin=buf)

    def _finish_pin_setup(self, overlay: QWidget, save: bool, pin: str = ""):
        if save and pin:
            try:
                from models.user import set_user_pin
                from database.db import get_connection

                user_id = self._pin_setup_user.get("id")

                if not user_id:
                    email    = (self._pin_setup_user.get("email")    or "").strip()
                    username = (self._pin_setup_user.get("username") or "").strip()
                    conn = get_connection()
                    cur  = conn.cursor()
                    frappe_user = (self._pin_setup_user.get("frappe_user") or self._pin_setup_user.get("name") or "").strip()
                    cur.execute(
                        "SELECT TOP 1 id FROM users "
                        "WHERE (email=? AND email<>'') "
                        "   OR (frappe_user=? AND frappe_user<>'') "
                        "   OR (username=? AND username<>'')",
                        (email, frappe_user, username),
                    )
                    row = cur.fetchone()
                    conn.close()
                    if row:
                        user_id = row[0]

                if user_id:
                    if set_user_pin(user_id, pin):
                        self._pin_setup_user["pin"] = pin
                        print(f"[login] [OK] PIN saved  user_id={user_id}")
                    else:
                        self._pin_setup_buf   = ""
                        self._pin_setup_step  = "enter"
                        self._pin_setup_first = ""
                        self._pin_setup_dots.set_filled(0)
                        self._pin_setup_title.setText("Choose a Different PIN")
                        self._pin_setup_sub.setText("That PIN is already used by another account.")
                        self._pin_setup_err.setText("PIN already in use - try another.")
                        self._pin_setup_err.show()
                        return
                else:
                    print("[login] [!]  Could not find local user to save PIN")
            except Exception as e:
                print(f"[login] [!]  PIN save error: {e}")

        overlay.hide()
        overlay.deleteLater()
        self._pin_setup_overlay = None
        self._accept_user(self._pin_setup_user, self._pin_setup_source)

    # =========================================================================
    # Accept
    # =========================================================================
    def _ensure_default_customer(self):
        try:
            from models.default_customer import create_default_customer
            result = create_default_customer()
            print(f"[login] default customer: {'ready' if result else 'skipped'}")
        except Exception as e:
            print(f"[login] [!]  default customer: {e}")

    def _accept_user(self, user: dict, source: str):
        print(f"[login] [OK] _accept_user  {user.get('username', user.get('email'))!r}  {source!r}")
        
        # ── Offline License & Trial Check ────────────────────────────────────────
        if self.system_mode == "offline":
            from utils.license_manager import is_system_licensed, get_trial_info
            if not is_system_licensed():
                trial_info = get_trial_info()
                if trial_info["status"] == "Active":
                    rem = trial_info["days_remaining"]
                    from PySide6.QtWidgets import QMessageBox
                    ans = QMessageBox.question(
                        self, "Free Trial Active",
                        f"You are currently using the free trial.\n\nYou have {rem} days remaining.\n\nDo you want to continue on trial?",
                        QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
                    )
                    if ans != QMessageBox.Yes:
                        self._open_license_dialog()
                        return
                else:
                    self._open_license_dialog()
                    return
        # ─────────────────────────────────────────────────────────────────────────
        
        # ── Initial Company Setup (Offline First Run) ────────────────────────────
        if self.system_mode == "offline":
            try:
                from models.company_defaults import get_defaults
                comp = get_defaults()
                if not comp or not comp.get('company_name'):
                    from views.dialogs.initial_company_setup_dialog import InitialCompanySetupDialog
                    from PySide6.QtWidgets import QDialog
                    dlg = InitialCompanySetupDialog(self)
                    if dlg.exec() != QDialog.Accepted:
                        # Required setup not completed
                        return
            except Exception as e:
                print(f"[login] initial company setup error: {e}")
        # ─────────────────────────────────────────────────────────────────────────
        
        self._cleanup()

        self.logged_in_user = user
        self.login_source   = source

        valid_creds = False
        try:
            from services.credentials import get_all_credentials, set_session, has_credentials
            creds = get_all_credentials()
            
            # If we just logged in via Odoo, the creds in memory might already be fresh
            # because OdooLoginWorker calls set_session.
            valid_creds = has_credentials()
            
            if not valid_creds and self.system_mode != "offline":
                 print("[login] [!]  no credentials - sync skipped")
            else:
                 print(f"[login] credentials ready (Mode: {self.system_mode})")
                 
        except Exception as e:
            print(f"[login] credential init: {e}")

        self._ensure_default_customer()
        self.hide()

        if valid_creds and self.system_mode != "offline":
            # Keep reference alive on the global application instance so it isn't GC'd when dialog closes
            app = QApplication.instance()
            app._bg_sync = BackgroundSyncWorker()
            app._bg_sync.finished.connect(app._bg_sync.deleteLater)
            app._bg_sync.start()
            print("[login] 🔄 background sync started")

        self.accept()

    # =========================================================================
    # Connectivity (async, non-blocking)
    # =========================================================================
    def _refresh_connectivity(self):
        """Fire a background connectivity check; update status bar on result."""
        if self._conn_worker and self._conn_worker.isRunning():
            return
        self._set_status("Checking connection…", MID)
        self._conn_worker = ConnectivityWorker(self)
        self._conn_worker.result.connect(self._on_connectivity_result)
        self._conn_worker.start()

    def _on_connectivity_result(self, online: bool):
        if self.system_mode == "offline":
            self._set_status("Offline Mode", SUCCESS)
            return
            
        mode_str = "Havano Mode" if self.system_mode == "odoo" else "SaaS Mode"
            
        if online:
            url_disp = get_current_site_url().replace("https://", "").replace("http://", "")
            self._set_status(f"Online ({mode_str}) - {url_disp}", SUCCESS)
        else:
            self._set_status(f"Offline ({mode_str}) - local database only", ORANGE)

    def _set_status(self, msg: str, colour: str):
        for w in (self._status_dot, self._status_lbl):
            w.setStyleSheet(
                w.styleSheet().replace(
                    w.styleSheet().split("color:")[1].split(";")[0],
                    colour,
                ) if "color:" in w.styleSheet() else
                f"color:{colour}; font-size:{'7' if w is self._status_dot else '10'}px; "
                "background:transparent;"
            )
        self._status_lbl.setText(msg)
        self._status_dot.setStyleSheet(f"color:{colour}; font-size:7px; background:transparent;")
        self._status_lbl.setStyleSheet(f"color:{colour}; font-size:10px; background:transparent;")

    # =========================================================================
    # Button helpers
    # =========================================================================
    def _set_btn_normal(self, btn: QPushButton):
        btn.setEnabled(True); btn.setText("Sign In")
        btn.setStyleSheet(f"""
            QPushButton {{
                background:{ACCENT}; color:{WHITE}; font-size:15px; font-weight:bold;
                border-radius:12px; border:2px solid {ACCENT_H};
            }}
            QPushButton:hover   {{ background:{ACCENT_H}; }}
            QPushButton:pressed {{ background:{NAVY}; }}
        """)
        for inp in (getattr(self, "username_input", None),
                    getattr(self, "password_input", None)):
            if inp: inp.setEnabled(True)

    def _set_btn_loading(self, btn: QPushButton):
        btn.setEnabled(False); btn.setText("Signing in…")
        btn.setStyleSheet(f"""
            QPushButton {{
                background:{LIGHT}; color:{MUTED}; font-size:15px; font-weight:bold;
                border-radius:12px; border:2px solid {BORDER};
            }}
        """)
        for inp in (getattr(self, "username_input", None),
                    getattr(self, "password_input", None)):
            if inp: inp.setEnabled(False)

    def _set_btn_error(self, btn: QPushButton):
        btn.setEnabled(True); btn.setText("Try Again")
        btn.setStyleSheet(f"""
            QPushButton {{
                background:{DANGER}; color:{WHITE}; font-size:15px; font-weight:bold;
                border-radius:12px; border:none;
            }}
        """)

    # =========================================================================
    # Widget helpers
    # =========================================================================
    def _field_lbl(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color:{MUTED}; font-size:10px; font-weight:bold; "
            "background:transparent; letter-spacing:1.4px;"
        )
        return lbl

    def _input(self, placeholder: str) -> QLineEdit:
        inp = QLineEdit()
        inp.setPlaceholderText(placeholder); inp.setFixedHeight(48)
        inp.setStyleSheet(f"""
            QLineEdit {{
                background:{WHITE}; color:{NAVY};
                border:1.5px solid {BORDER}; border-radius:12px;
                padding:0 18px; font-size:14px;
            }}
            QLineEdit:focus {{ border:1.5px solid {ACCENT}; }}
            QLineEdit:hover {{ border:1.5px solid {MID};    }}
        """)
        return inp

    def _show_error(self, msg: str):
        self.error_label.setStyleSheet(f"""
            color:{WHITE}; background:{DANGER}; font-size:12px; font-weight:bold;
            border-radius:8px; padding:6px 14px;
        """)
        self.error_label.setText(f"  {msg}  ")
        self.error_label.show()

    def _show_info(self, msg: str):
        self.error_label.setStyleSheet(f"""
            color:{WHITE}; background:{ORANGE}; font-size:12px; font-weight:bold;
            border-radius:8px; padding:6px 14px;
        """)
        self.error_label.setText(f"  {msg}  ")
        self.error_label.show()
        QTimer.singleShot(4000, self.error_label.hide)

    def keyPressEvent(self, event):
        if self._stack.currentIndex() != 0:
            super().keyPressEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self.setFocus(); self.activateWindow(); self.raise_()
        try:
            from PySide6.QtGui import QGuiApplication
            screen = QGuiApplication.primaryScreen().geometry()
            size = self.geometry()
            self.move((screen.width() - size.width()) // 2,
                      (screen.height() - size.height()) // 2)
        except Exception:
            pass

    # =========================================================================
    # Error flash (shake)
    # =========================================================================
    def _shake(self):
        card = self.findChild(QFrame, "card")
        if not card: return
        orig  = card.styleSheet()
        flash = "QFrame#card { background:#ffffff; border-radius:20px; border:2.5px solid #c0392b; }"
        alt   = flash.replace("#c0392b", "#e74c3c")
        for ms, style in [(0, flash), (120, alt), (240, flash), (360, alt), (480, orig)]:
            QTimer.singleShot(ms, lambda s=style: card.setStyleSheet(s))