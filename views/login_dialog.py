from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QWidget, QGraphicsDropShadowEffect,
    QStackedWidget, QGridLayout, QSizePolicy, QApplication,
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
NAVY      = "#0d1f3c"
NAVY_2    = "#162d52"
NAVY_3    = "#1e3d6e"
ACCENT    = "#1a5fb4"
ACCENT_H  = "#2468c8"
WHITE     = "#ffffff"
OFF_WHITE = "#f5f8fc"
LIGHT     = "#e4eaf4"
BORDER    = "#c8d8ec"
MID       = "#8fa8c8"
MUTED     = "#5a7a9a"
DANGER    = "#c0392b"
SUCCESS   = "#1a7a3c"
WARNING   = "#e67e22"
CREAM     = "#f0e8d0"

try:
    from services.site_config import get_host as _gh
    SITE_URL = _gh().replace("https://", "").replace("http://", "").rstrip("/")
except Exception:
    SITE_URL = "havano.cloud"

# =============================================================================
# Connectivity helper  (fast, non-blocking check)
# =============================================================================
def _is_online(timeout: float = 3.0) -> bool:
    """
    Quick TCP-level reachability check.
    Returns True if the site host is reachable on port 443.
    Falls back to HTTP GET if TCP probe fails (proxy / firewall).
    """
    import socket
    host = SITE_URL.split("/")[0]           # strip any path component
    port = 443

    # 1. TCP probe — fastest path
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return True
    except OSError:
        pass

    # 2. HTTP fallback — handles transparent proxies
    try:
        import urllib.request
        urllib.request.urlopen(f"https://{host}", timeout=timeout)
        return True
    except Exception:
        return False


# =============================================================================
# Background workers
# =============================================================================
class LoginWorker(QThread):
    """
    Runs auth_service.login() off the main thread.

    Strategy (in order):
      1. Quick connectivity check (TCP, 3 s).
      2. If online  → attempt server login (timeout-guarded).
      3. If offline → fall straight through to local DB check.
      4. Always emit a result dict — never crash silently.
    """
    finished = Signal(dict)

    # Hard ceiling for the whole online-login attempt (seconds).
    # auth_service.login() does: HTTP login → token save → product auto-sync
    # → local credential persist.  Give it plenty of room on slow connections.
    ONLINE_TIMEOUT = 60

    def __init__(self, username: str, password: str):
        super().__init__()
        self.username = username
        self.password = password

    # ------------------------------------------------------------------
    def run(self):
        print(f"[LoginWorker] ▶ started  username={self.username!r}")

        online = _is_online(timeout=3.0)
        print(f"[LoginWorker] connectivity={online}")

        if online:
            result = self._try_online()
            # If online path returned a genuine credential error, don't
            # silently fall back — surface it immediately so the user knows.
            if result.get("success") or result.get("source") == "online":
                self.finished.emit(result)
                return
            # Any other online failure (timeout, parse error, 5xx …)
            # → try local DB before giving up.
            print(f"[LoginWorker] online failed ({result.get('error')}), trying local …")

        result = self._try_local()
        self.finished.emit(result)

    # ------------------------------------------------------------------
    def _try_online(self) -> dict:
        import concurrent.futures, traceback
        def _call():
            from services.auth_service import login
            return login(self.username, self.password)

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(_call)
            try:
                result = future.result(timeout=self.ONLINE_TIMEOUT)
                print(f"[LoginWorker] online result: success={result.get('success')} "
                      f"source={result.get('source')!r}")
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
            print("[LoginWorker] authenticate_local → no match")
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
            print("[LoginWorker] authenticate → no match")
            return {"success": False,
                    "error": "Incorrect username or password.",
                    "source": "offline"}
        except ImportError:
            print("[LoginWorker] authenticate not found, trying DB fallback…")
        except Exception as exc:
            print(f"[LoginWorker] authenticate error: {exc}")

        # ── Strategy 3: raw DB query (SQL Server — pyodbc style) ─────────────
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
                "WHERE (username=? OR email=?) AND password_hash=? AND active=1",
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
            print("[LoginWorker] raw DB → no match")
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
        for label, func_path in [
            ("users",         "services.user_sync_service.sync_users"),
            ("products+taxes","services.sync_service.SyncWorker"),
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
                print(f"[bg-sync] ✅ {label}")
            except Exception as e:
                print(f"[bg-sync] ⚠️  {label}: {e}")


# ------------------------------------------------------------------
class ConnectivityWorker(QThread):
    """Non-blocking connectivity check that emits a result signal."""
    result = Signal(bool)

    def run(self):
        self.result.emit(_is_online(timeout=4.0))


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
# Main Login Dialog
# =============================================================================
class LoginDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Havano POS")
        self.setFixedSize(480, 700)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.logged_in_user: dict | None  = None
        self.login_source:   str  | None  = None
        self._worker:        LoginWorker | None = None
        self._conn_worker:   ConnectivityWorker | None = None
        self._pin_buffer:    str = ""

        # PIN setup state
        self._pin_setup_overlay: QWidget | None = None
        self._pin_setup_user:    dict = {}
        self._pin_setup_source:  str  = ""
        self._pin_setup_buf:     str  = ""
        self._pin_setup_step:    str  = "enter"
        self._pin_setup_first:   str  = ""

        self._build_ui()

        # Async connectivity check — never blocks UI
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
        return super().eventFilter(obj, event)

    # =========================================================================
    # Window lifecycle
    # =========================================================================
    def closeEvent(self, event):
        self._cleanup()
        QApplication.quit()
        event.accept()

    def reject(self):
        pass   # prevent Escape from dismissing

    def _cleanup(self):
        QApplication.instance().removeEventFilter(self)
        for w in (self._worker, self._conn_worker):
            if w and w.isRunning():
                w.quit()
                w.wait(500)

    # =========================================================================
    # UI construction
    # =========================================================================
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)

        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet("QFrame#card { background:#ffffff; border-radius:20px; }")

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(60); shadow.setXOffset(0); shadow.setYOffset(16)
        shadow.setColor(QColor(13, 31, 60, 100))
        card.setGraphicsEffect(shadow)

        vl = QVBoxLayout(card)
        vl.setSpacing(0); vl.setContentsMargins(0, 0, 0, 0)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setFixedHeight(148)
        hdr.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 {NAVY}, stop:0.6 {NAVY_2}, stop:1 {NAVY_3});
                border-top-left-radius:20px; border-top-right-radius:20px;
            }}
        """)
        hl = QVBoxLayout(hdr)
        hl.setContentsMargins(0, 12, 12, 20); hl.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.addStretch()
        self.close_btn = QPushButton()
        self.close_btn.setIcon(qta.icon("fa5s.times", color=WHITE))
        self.close_btn.setFixedSize(32, 32)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setFocusPolicy(Qt.NoFocus)
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                background:rgba(255,255,255,0.15); border:none;
                border-radius:16px;
            }}
            QPushButton:hover   {{ background:rgba(255,255,255,0.25); }}
            QPushButton:pressed {{ background:rgba(255,255,255,0.35); }}
        """)
        self.close_btn.clicked.connect(self.close)
        top_row.addWidget(self.close_btn)
        hl.addLayout(top_row)

        logo_lbl = QLabel("H")
        logo_lbl.setAlignment(Qt.AlignCenter)
        logo_lbl.setFixedSize(44, 44)
        logo_lbl.setStyleSheet(f"""
            background:{ACCENT}; color:{WHITE}; border-radius:12px;
            font-size:22px; font-weight:900; letter-spacing:-1px;
        """)
        logo_row = QHBoxLayout()
        logo_row.addStretch(); logo_row.addWidget(logo_lbl); logo_row.addStretch()
        hl.addLayout(logo_row)

        title = QLabel("Havano POS")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            f"color:{WHITE}; font-size:22px; font-weight:800; "
            "background:transparent; letter-spacing:1px;"
        )
        hl.addWidget(title)
        vl.addWidget(hdr)

        # ── Accent line ───────────────────────────────────────────────────────
        al = QFrame(); al.setFixedHeight(3)
        al.setStyleSheet(f"""
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 {NAVY_3}, stop:0.3 {ACCENT},
                stop:0.7 {ACCENT_H}, stop:1 {NAVY_3});
        """)
        vl.addWidget(al)

        # ── Status bar ────────────────────────────────────────────────────────
        self._status_bar = QWidget()
        self._status_bar.setFixedHeight(24)
        self._status_bar.setStyleSheet(f"background:{NAVY_2}; border:none;")
        sl = QHBoxLayout(self._status_bar)
        sl.setContentsMargins(20, 0, 20, 0); sl.setSpacing(6)
        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet(f"color:{MID}; font-size:7px; background:transparent;")
        self._status_lbl = QLabel("Checking connection…")
        self._status_lbl.setStyleSheet(f"color:{MID}; font-size:10px; background:transparent;")
        sl.addStretch()
        sl.addWidget(self._status_dot); sl.addWidget(self._status_lbl)
        sl.addStretch()
        vl.addWidget(self._status_bar)

        # ── Tab row ───────────────────────────────────────────────────────────
        tab_row = QWidget()
        tab_row.setStyleSheet(f"background:{OFF_WHITE};")
        tl = QHBoxLayout(tab_row)
        tl.setContentsMargins(28, 10, 28, 0); tl.setSpacing(8)
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
        tl.addWidget(self._pin_tab); tl.addWidget(self._email_tab)
        vl.addWidget(tab_row)

        # ── Stack ─────────────────────────────────────────────────────────────
        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background:{OFF_WHITE};")
        self._stack.addWidget(self._build_pin_page())
        self._stack.addWidget(self._build_email_page())
        vl.addWidget(self._stack, 1)

        # ── Error label ───────────────────────────────────────────────────────
        err_w = QWidget(); err_w.setStyleSheet(f"background:{OFF_WHITE};")
        el = QHBoxLayout(err_w); el.setContentsMargins(28, 0, 28, 4)
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

        # ── SQL settings link ─────────────────────────────────────────────────
        sql_w = QWidget(); sql_w.setStyleSheet(f"background:{OFF_WHITE};")
        sql_l = QHBoxLayout(sql_w)
        sql_l.setContentsMargins(28, 0, 28, 8); sql_l.setSpacing(6)
        sql_l.addStretch()
        gear = QLabel()
        gear.setPixmap(qta.icon("fa5s.cog", color=MUTED).pixmap(11, 11))
        gear.setStyleSheet("background:transparent;")
        self._sql_link_btn = QPushButton("Database & Site Configuration")
        self._sql_link_btn.setCursor(Qt.PointingHandCursor)
        self._sql_link_btn.setFocusPolicy(Qt.NoFocus)
        self._sql_link_btn.setStyleSheet(f"""
            QPushButton {{
                background:transparent; color:{MUTED}; border:none;
                font-size:11px; font-weight:600; padding:0;
            }}
            QPushButton:hover {{ color:{ACCENT}; text-decoration:underline; }}
        """)
        self._sql_link_btn.clicked.connect(self._open_sql_settings)
        sql_l.addWidget(gear); sql_l.addWidget(self._sql_link_btn); sql_l.addStretch()
        vl.addWidget(sql_w)

        # ── Footer ────────────────────────────────────────────────────────────
        footer = QWidget(); footer.setFixedHeight(36)
        footer.setStyleSheet(
            f"background:{CREAM}; border-bottom-left-radius:20px; "
            "border-bottom-right-radius:20px;"
        )
        fl = QHBoxLayout(footer); fl.setContentsMargins(0, 0, 0, 0)
        fl.addStretch()
        globe = QLabel()
        globe.setPixmap(qta.icon("fa5s.globe", color=NAVY).pixmap(10, 10))
        globe.setStyleSheet("background:transparent;")
        site_lbl = QLabel(SITE_URL)
        site_lbl.setAlignment(Qt.AlignCenter)
        site_lbl.setStyleSheet(
            f"font-size:10px; color:{NAVY}; background:transparent; "
            "letter-spacing:0.5px; font-weight:bold;"
        )
        fl.addWidget(globe); fl.addSpacing(6); fl.addWidget(site_lbl); fl.addStretch()
        vl.addWidget(footer)

        root.addWidget(card)
        self._switch_mode(0)

    # =========================================================================
    # SQL settings
    # =========================================================================
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

    # =========================================================================
    # PIN page
    # =========================================================================
    def _build_pin_page(self) -> QWidget:
        page = QWidget(); page.setStyleSheet(f"background:{OFF_WHITE};")
        pl = QVBoxLayout(page)
        pl.setContentsMargins(28, 18, 28, 12); pl.setSpacing(14)
        pl.setAlignment(Qt.AlignTop)

        dot_card = QWidget()
        dot_card.setStyleSheet(f"""
            background:{WHITE}; border-radius:14px; border:1.5px solid {BORDER};
        """)
        dot_card.setFixedHeight(58)
        dcl = QHBoxLayout(dot_card); dcl.setContentsMargins(0, 0, 0, 0)
        self._pin_dots = PinDots(4)
        dcl.addStretch(); dcl.addWidget(self._pin_dots); dcl.addStretch()
        pl.addWidget(dot_card)

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
        return page

    # =========================================================================
    # Email / Password page
    # =========================================================================
    def _build_email_page(self) -> QWidget:
        page = QWidget(); page.setStyleSheet(f"background:{OFF_WHITE};")
        pl = QVBoxLayout(page)
        pl.setContentsMargins(28, 20, 28, 12); pl.setSpacing(6)
        pl.setAlignment(Qt.AlignTop)

        pl.addWidget(self._field_lbl("USERNAME / EMAIL"))
        pl.addSpacing(4)
        self.username_input = self._input("Enter your username or email")
        self.username_input.returnPressed.connect(lambda: self.password_input.setFocus())
        pl.addWidget(self.username_input)
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

        self._email_btn = QPushButton("Sign In  →")
        self._email_btn.setFixedHeight(52)
        self._email_btn.setCursor(Qt.PointingHandCursor)
        self._email_btn.setFocusPolicy(Qt.NoFocus)
        self._set_btn_normal(self._email_btn)
        self._email_btn.clicked.connect(self._login_email)
        pl.addWidget(self._email_btn)
        pl.addStretch()
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
        active   = (f"QPushButton {{ background:{NAVY}; color:{WHITE}; border:none; "
                    "border-radius:10px; font-size:12px; font-weight:bold; }}")
        inactive = (f"QPushButton {{ background:{WHITE}; color:{MUTED}; "
                    f"border:1.5px solid {BORDER}; border-radius:10px; font-size:12px; }}"
                    f"QPushButton:hover {{ background:{LIGHT}; color:{NAVY}; }}")
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
        if self._worker is not None and self._worker.isRunning():
            return
        u = self.username_input.text().strip()
        p = self.password_input.text().strip()
        if not u or not p:
            self._show_error("Please enter your username and password.")
            return

        self._set_btn_loading(self._email_btn)
        self.error_label.hide()

        if self._local_catalogue_is_empty():
            self._set_status(
                "First-time setup — signing in and syncing catalogue…",
                "#c05a00",
            )

        self._worker = LoginWorker(u, p)
        self._worker.finished.connect(self._on_login_done)
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

    def _on_login_done(self, result: dict):
        self._worker = None
        self._set_btn_normal(self._email_btn)

        if result.get("success"):
            user   = result["user"]
            source = result.get("source", "online")
            if source == "offline":
                self._show_info("Offline mode — using local account.")
            self._validate_and_accept(user, source)
            return

        # ── Map error to a user-friendly message ─────────────────────────────
        err    = result.get("error", "Login failed.")
        source = result.get("source", "")

        if any(x in err.lower() for x in ("wrong", "incorrect", "invalid",
                                           "password", "credential")):
            display = "Incorrect username or password.  Please try again."
        elif source == "timeout":
            display = "Server took too long to respond — trying local account…"
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

    def _try_local_fallback_after_timeout(self, username: str, password: str):
        """
        Silent local-DB check shown as a second chance after a server timeout.
        Tries the same function-name chain as LoginWorker._try_local().
        """
        import hashlib

        user = None

        # Strategy 1 — authenticate_local()
        try:
            from models.user import authenticate_local
            user = authenticate_local(username, password)
        except ImportError:
            pass
        except Exception as e:
            print(f"[login] fallback authenticate_local: {e}")

        # Strategy 2 — authenticate()
        if user is None:
            try:
                from models.user import authenticate
                user = authenticate(username, password)
            except ImportError:
                pass
            except Exception as e:
                print(f"[login] fallback authenticate: {e}")

        # Strategy 3 — raw SQL Server query
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
            self._show_info("Server slow — logged in with saved local account.")
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

        # Warehouse / Company guard — online logins only
        if source == "online":
            warehouse = (user.get("warehouse") or "").strip()
            company   = (user.get("company")   or "").strip()
            missing   = [x for x, v in [("Warehouse", warehouse), ("Company", company)] if not v]
            if missing:
                missing_str = " and ".join(missing)
                print(f"[login] ❌ BLOCKED: missing {missing_str}")
                CatchyErrorDialog(
                    "Configuration Missing",
                    f"Your account is missing a {missing_str} assignment.\n"
                    "Please contact your administrator.",
                    self,
                ).exec()
                self._show_error(f"Missing {missing_str}")
                if hasattr(self, "_email_btn"):
                    self._set_btn_error(self._email_btn)
                self._shake(); self._pin_clear()
                self.password_input.clear()
                return

        # PIN check — populate from local DB if API didn't provide it
        if not (user.get("pin") or "").strip():
            user["pin"] = self._fetch_local_pin(user)

        if source in ("online", "offline") and not (user.get("pin") or "").strip():
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
            print(f"[login] ⚠️  _fetch_local_pin: {e}")
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
        skip_btn = QPushButton("Skip — I'll set my PIN later")
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
                self._pin_setup_sub.setText("PINs didn't match — please try again")
                self._pin_setup_err.setText("PINs did not match — starting over.")
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
                    # SQL Server syntax (TOP 1) — matches the project's DB engine
                    cur.execute(
                        "SELECT TOP 1 id FROM users "
                        "WHERE email=? OR frappe_user=? OR username=?",
                        (email, email, username),
                    )
                    row = cur.fetchone()
                    conn.close()
                    if row:
                        user_id = row[0]

                if user_id:
                    if set_user_pin(user_id, pin):
                        self._pin_setup_user["pin"] = pin
                        print(f"[login] ✅ PIN saved  user_id={user_id}")
                    else:
                        self._pin_setup_buf   = ""
                        self._pin_setup_step  = "enter"
                        self._pin_setup_first = ""
                        self._pin_setup_dots.set_filled(0)
                        self._pin_setup_title.setText("Choose a Different PIN")
                        self._pin_setup_sub.setText("That PIN is already used by another account.")
                        self._pin_setup_err.setText("PIN already in use — try another.")
                        self._pin_setup_err.show()
                        return
                else:
                    print("[login] ⚠️  Could not find local user to save PIN")
            except Exception as e:
                print(f"[login] ⚠️  PIN save error: {e}")

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
            print(f"[login] ⚠️  default customer: {e}")

    def _accept_user(self, user: dict, source: str):
        print(f"[login] ✅ _accept_user  {user.get('username', user.get('email'))!r}  {source!r}")
        self._cleanup()

        self.logged_in_user = user
        self.login_source   = source

        k, s = "", ""
        try:
            from services.credentials import get_credentials, set_session
            k, s = get_credentials()
            if k and s:
                set_session(k, s)
                print(f"[login] credentials set: {k[:8]}…")
            else:
                print("[login] ⚠️  no credentials — sync skipped")
        except Exception as e:
            print(f"[login] credential init: {e}")

        self._ensure_default_customer()
        self.hide()

        if k and s:
            self._bg_sync = BackgroundSyncWorker()
            self._bg_sync.start()
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
        self._conn_worker = ConnectivityWorker()
        self._conn_worker.result.connect(self._on_connectivity_result)
        self._conn_worker.start()

    def _on_connectivity_result(self, online: bool):
        if online:
            self._set_status(f"Online — {SITE_URL}", SUCCESS)
        else:
            self._set_status("Offline — local database only", WARNING)

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
        btn.setEnabled(True); btn.setText("Sign In  →")
        btn.setStyleSheet(f"""
            QPushButton {{
                background:{NAVY}; color:{WHITE}; font-size:15px; font-weight:bold;
                border-radius:12px; border:none;
            }}
            QPushButton:hover   {{ background:{NAVY_3}; }}
            QPushButton:pressed {{ background:{ACCENT}; }}
        """)
        for inp in (getattr(self, "username_input", None),
                    getattr(self, "password_input", None)):
            if inp: inp.setEnabled(True)

    def _set_btn_loading(self, btn: QPushButton):
        btn.setEnabled(False); btn.setText("Signing in…")
        btn.setStyleSheet(f"""
            QPushButton {{
                background:{NAVY_2}; color:{MID}; font-size:15px; font-weight:bold;
                border-radius:12px; border:none;
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
            color:{WHITE}; background:{WARNING}; font-size:12px; font-weight:bold;
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