# views/login_dialog.py
# =============================================================================
#  Havano POS — Login dialog
#
#  ALL login is LOCAL ONLY — no online Frappe auth.
#  Users must exist in local DB (synced from Frappe via Sync Users or created
#  manually in Admin → Manage Users).
#
#  Completeness check on every login:
#    User must have company, warehouse, cost_center set.
#    If missing → login rejected with a clear message telling admin to fix it.
#
#  After exec() == Accepted:
#    dialog.logged_in_user  → {"id", "username", "role", "company", ...}
#    dialog.login_source    → "pin" | "local"
# =============================================================================
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QWidget, QGraphicsDropShadowEffect,
    QStackedWidget, QGridLayout, QSizePolicy
)
from PySide6.QtCore import Qt, QPropertyAnimation, QPoint, QTimer, QEasingCurve, QThread, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen

# ── Palette ───────────────────────────────────────────────────────────────────
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

SITE_URL = "apk.havano.cloud"


# =============================================================================
# Background user sync — runs after login, non-blocking
# =============================================================================
class PreLoginSyncWorker(QThread):
    """
    Runs user sync BEFORE the login dialog is shown so that
    brand-new Frappe users are already in the local DB and can log in immediately.
    Non-blocking — the login dialog shows instantly, sync runs in background.
    If network is unavailable it silently skips (existing users still work).
    """
    finished = Signal()

    def run(self):
        try:
            from services.credentials import get_credentials
            k, s = get_credentials()
            if not k or not s:
                return   # no credentials yet — skip silently
            from services.user_sync_service import sync_users
            sync_users()
        except Exception as e:
            print(f"[pre-login sync] {e}")
        finally:
            self.finished.emit()


class BackgroundSyncWorker(QThread):
    """Runs AFTER login — kept for any post-login tasks."""
    def run(self):
        pass   # user sync moved to PreLoginSyncWorker


# =============================================================================
# PIN dot widget
# =============================================================================
class PinDots(QWidget):
    def __init__(self, length=6, parent=None):
        super().__init__(parent)
        self.length = length
        self.filled = 0
        self.setFixedSize(length * 28 + (length - 1) * 10, 22)

    def set_filled(self, n):
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
# Completeness check — same rules as user_sync_service filter
# =============================================================================
def _check_user_complete(user: dict) -> tuple[bool, str]:
    """
    Returns (True, "") if user has all required fields.
    Returns (False, human-readable reason) if not.
    """
    missing = []
    if not str(user.get("company")     or user.get("server_company")     or "").strip():
        missing.append("Company")
    if not str(user.get("warehouse")   or user.get("server_warehouse")   or "").strip():
        missing.append("Warehouse")
    if not str(user.get("cost_center") or user.get("server_cost_center") or "").strip():
        missing.append("Cost Centre")

    if missing:
        return False, (
            f"Your account is missing: {', '.join(missing)}.\n"
            f"Ask your admin to set these in Frappe → User → {user.get('username', '')} "
            f"then do Admin → Sync Users."
        )
    return True, ""


# =============================================================================
# Main dialog
# =============================================================================
class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Havano POS")
        self.setFixedSize(440, 620)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.logged_in_user = None
        self.login_source   = None
        self._pin_buffer    = ""
        self._build_ui()
        QTimer.singleShot(400, self._check_connectivity)
        # Sync users from Frappe before login so new users can log in immediately
        self._pre_sync = PreLoginSyncWorker()
        self._pre_sync.start()

    # ─────────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)

        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet("QFrame#card { background-color: #ffffff; border-radius: 20px; }")
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(60); shadow.setXOffset(0); shadow.setYOffset(16)
        shadow.setColor(QColor(13, 31, 60, 100))
        card.setGraphicsEffect(shadow)

        vl = QVBoxLayout(card)
        vl.setSpacing(0); vl.setContentsMargins(0, 0, 0, 0)

        # Header
        hdr = QWidget(); hdr.setFixedHeight(90)
        hdr.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 {NAVY}, stop:0.6 {NAVY_2}, stop:1 {NAVY_3});
                border-top-left-radius: 20px; border-top-right-radius: 20px;
            }}
        """)
        hl = QVBoxLayout(hdr); hl.setContentsMargins(0, 16, 0, 16); hl.setSpacing(0)

        logo = QLabel(); logo.setAlignment(Qt.AlignCenter); logo.setFixedSize(60, 60)
        logo.setStyleSheet("background:transparent;")
        try:
            from PySide6.QtGui import QPixmap
            for path in ("assets/havano-logo.jpeg", "assets/havano-logo.png", "assets/logo.png"):
                pix = QPixmap(path)
                if not pix.isNull():
                    logo.setPixmap(pix.scaled(60, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    break
        except Exception:
            pass
        lr = QHBoxLayout(); lr.addStretch(); lr.addWidget(logo); lr.addStretch()
        hl.addLayout(lr)
        vl.addWidget(hdr)

        # Accent line
        al = QFrame(); al.setFixedHeight(3)
        al.setStyleSheet(f"background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {NAVY_3}, stop:0.4 {ACCENT}, stop:1 {NAVY_3});")
        vl.addWidget(al)

        # Status bar
        self._status_bar = QWidget(); self._status_bar.setFixedHeight(24)
        self._status_bar.setStyleSheet(f"background:{NAVY_2};")
        sl = QHBoxLayout(self._status_bar); sl.setContentsMargins(16,0,16,0); sl.setSpacing(5)
        self._status_dot = QLabel("●"); self._status_dot.setStyleSheet(f"color:{MID}; font-size:7px; background:transparent;")
        self._status_lbl = QLabel("Checking connection…"); self._status_lbl.setStyleSheet(f"color:{MID}; font-size:10px; background:transparent;")
        sl.addStretch(); sl.addWidget(self._status_dot); sl.addWidget(self._status_lbl); sl.addStretch()
        vl.addWidget(self._status_bar)

        # Tabs
        tab_row = QWidget(); tab_row.setStyleSheet(f"background:{OFF_WHITE};")
        tl = QHBoxLayout(tab_row); tl.setContentsMargins(28, 10, 28, 0); tl.setSpacing(8)
        self._pin_tab = QPushButton("  🔢  PIN")
        self._pw_tab  = QPushButton("  🔑  Password")
        for b in (self._pin_tab, self._pw_tab):
            b.setFixedHeight(36); b.setCursor(Qt.PointingHandCursor)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._pin_tab.clicked.connect(lambda: self._switch_mode(0))
        self._pw_tab.clicked.connect(lambda: self._switch_mode(1))
        tl.addWidget(self._pin_tab); tl.addWidget(self._pw_tab)
        vl.addWidget(tab_row)

        # Pages
        self._stack = QStackedWidget(); self._stack.setStyleSheet(f"background:{OFF_WHITE};")
        self._stack.addWidget(self._build_pin_page())
        self._stack.addWidget(self._build_pw_page())
        vl.addWidget(self._stack, 1)

        # Error label
        err_w = QWidget(); err_w.setStyleSheet(f"background:{OFF_WHITE};")
        el = QHBoxLayout(err_w); el.setContentsMargins(28, 0, 28, 8)
        self.error_label = QLabel("")
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet(f"""
            color:{WHITE}; background:{DANGER}; font-size:11px; font-weight:bold;
            border-radius:8px; padding:8px 14px;
        """)
        self.error_label.hide()
        el.addWidget(self.error_label)
        vl.addWidget(err_w)

        # Footer
        footer = QWidget(); footer.setFixedHeight(40)
        footer.setStyleSheet(f"background:{CREAM}; border-bottom-left-radius:20px; border-bottom-right-radius:20px;")
        fl = QHBoxLayout(footer); fl.setContentsMargins(0,0,0,0)
        fl.addWidget(self._mk_lbl(f"🌐  {SITE_URL}", f"font-size:10px; color:{NAVY}; background:transparent; font-weight:bold;"))
        vl.addWidget(footer)

        root.addWidget(card)
        self._switch_mode(0)

    # ── PIN page ──────────────────────────────────────────────────────────────
    def _build_pin_page(self):
        page = QWidget(); page.setStyleSheet(f"background:{OFF_WHITE};")
        pl = QVBoxLayout(page)
        pl.setContentsMargins(16, 12, 16, 10)
        pl.setSpacing(8)
        pl.setAlignment(Qt.AlignTop)

        # ── Dot indicator ─────────────────────────────────────────────────────
        dot_card = QWidget()
        dot_card.setStyleSheet(f"""
            background:{WHITE}; border-radius:14px;
            border:1.5px solid {BORDER};
        """)
        dot_card.setFixedHeight(60)
        dcl = QHBoxLayout(dot_card); dcl.setContentsMargins(0, 0, 0, 0)
        self._pin_dots = PinDots(6)
        dcl.addStretch(); dcl.addWidget(self._pin_dots); dcl.addStretch()
        pl.addWidget(dot_card)
        pl.addSpacing(10)

        # ── Numpad ────────────────────────────────────────────────────────────
        grid_w = QWidget(); grid_w.setStyleSheet("background:transparent;")
        grid = QGridLayout(grid_w)
        grid.setSpacing(8)
        grid.setContentsMargins(4, 4, 4, 4)

        for col in range(3):
            grid.setColumnStretch(col, 1)

        keys = [
            ("1","d"),("2","d"),("3","d"),
            ("4","d"),("5","d"),("6","d"),
            ("7","d"),("8","d"),("9","d"),
            ("⌫","b"),("0","d"),("✓","e"),
        ]
        BTN_H = 46   # compact fixed height — no overlap, no giant buttons
        for i, (lbl, kind) in enumerate(keys):
            btn = QPushButton(lbl)
            btn.setFixedHeight(BTN_H)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setCursor(Qt.PointingHandCursor)
            if kind == "d":
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background:{WHITE}; color:{NAVY};
                        border:1.5px solid {BORDER}; border-radius:8px;
                        font-size:16px; font-weight:bold;
                    }}
                    QPushButton:hover   {{ background:{LIGHT}; border-color:{ACCENT}; }}
                    QPushButton:pressed {{ background:{ACCENT}; color:{WHITE}; border-color:{ACCENT}; }}
                """)
                btn.clicked.connect(lambda _, x=lbl: self._pin_press(x))
            elif kind == "b":
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background:{LIGHT}; color:{MUTED};
                        border:1.5px solid {BORDER}; border-radius:8px;
                        font-size:16px; font-weight:bold;
                    }}
                    QPushButton:hover   {{ background:{BORDER}; color:{NAVY}; }}
                    QPushButton:pressed {{ background:{DANGER}; color:{WHITE}; border-color:{DANGER}; }}
                """)
                btn.clicked.connect(self._pin_backspace)
                btn.setAutoRepeat(True)
                btn.setAutoRepeatDelay(500)
                btn.setAutoRepeatInterval(100)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background:{ACCENT}; color:{WHITE};
                        border:none; border-radius:8px;
                        font-size:18px; font-weight:bold;
                    }}
                    QPushButton:hover   {{ background:{ACCENT_H}; }}
                    QPushButton:pressed {{ background:{NAVY_2}; }}
                """)
                btn.clicked.connect(self._login_pin)
            grid.addWidget(btn, i // 3, i % 3)

        pl.addWidget(grid_w)
        pl.addSpacing(8)

        # ── CLR button ────────────────────────────────────────────────────────
        clr_btn = QPushButton("CLR  —  Clear all")
        clr_btn.setFixedHeight(40)
        clr_btn.setCursor(Qt.PointingHandCursor)
        clr_btn.setStyleSheet(f"""
            QPushButton {{
                background:transparent; color:{MUTED};
                border:1.5px solid {BORDER}; border-radius:10px;
                font-size:12px; font-weight:bold;
            }}
            QPushButton:hover   {{ background:{LIGHT}; color:{DANGER}; border-color:{DANGER}; }}
            QPushButton:pressed {{ background:{DANGER}; color:{WHITE}; }}
        """)
        clr_btn.clicked.connect(self._pin_clear)
        pl.addWidget(clr_btn)
        pl.addSpacing(6)

        return page

    # ── Password page ─────────────────────────────────────────────────────────
    def _build_pw_page(self):
        page = QWidget(); page.setStyleSheet(f"background:{OFF_WHITE};")
        pl = QVBoxLayout(page); pl.setContentsMargins(20,8,20,8); pl.setSpacing(6); pl.setAlignment(Qt.AlignTop)

        pl.addWidget(self._field_lbl("USERNAME")); pl.addSpacing(4)
        self.username_input = self._input("Enter your username")
        pl.addWidget(self.username_input); pl.addSpacing(14)

        pl.addWidget(self._field_lbl("PASSWORD")); pl.addSpacing(4)
        self.password_input = self._input("Enter your password", pw=True)
        self.password_input.returnPressed.connect(self._login_pw)
        pl.addWidget(self.password_input); pl.addSpacing(18)

        self._pw_btn = QPushButton("Sign In  →")
        self._pw_btn.setFixedHeight(50); self._pw_btn.setCursor(Qt.PointingHandCursor)
        self._set_btn_normal(self._pw_btn)
        self._pw_btn.clicked.connect(self._login_pw)
        pl.addWidget(self._pw_btn)
        pl.addStretch()
        return page

    # ── Tab switching ─────────────────────────────────────────────────────────
    def _switch_mode(self, idx):
        self._stack.setCurrentIndex(idx)
        self.error_label.hide()
        active   = f"QPushButton {{ background:{NAVY}; color:{WHITE}; border:none; border-radius:10px; font-size:12px; font-weight:bold; }}"
        inactive = f"QPushButton {{ background:{WHITE}; color:{MUTED}; border:1.5px solid {BORDER}; border-radius:10px; font-size:12px; }} QPushButton:hover {{ background:{LIGHT}; color:{NAVY}; }}"
        self._pin_tab.setStyleSheet(active if idx == 0 else inactive)
        self._pw_tab.setStyleSheet(active if idx == 1 else inactive)
        if idx == 0:
            self._pin_clear()
        else:
            self.username_input.setFocus()

    # ── PIN login (local only) ────────────────────────────────────────────────
    def _pin_press(self, digit):
        if len(self._pin_buffer) >= 6: return
        self._pin_buffer += digit
        self._pin_dots.set_filled(len(self._pin_buffer))
        self.error_label.hide()
        if len(self._pin_buffer) == 6:
            QTimer.singleShot(120, self._login_pin)

    def _pin_backspace(self):
        # Works at any point — including after wrong 6-digit attempt
        self._pin_buffer = self._pin_buffer[:-1]
        self._pin_dots.set_filled(len(self._pin_buffer))
        self.error_label.hide()

    def _pin_clear(self):
        """Reset everything — called after wrong PIN so user can retry."""
        self._pin_buffer = ""
        self._pin_dots.set_filled(0)
        self.error_label.hide()

    def _login_pin(self):
        pin = self._pin_buffer.strip()
        if not pin:
            self._show_error("Invalid credentials."); return
        try:
            from models.user import authenticate_by_pin
            user = authenticate_by_pin(pin)
        except Exception as e:
            self._show_error("Invalid credentials."); return
        if not user:
            self._show_error("Invalid credentials.")
            self._pin_clear()
            self._shake(); return
        self._validate_and_accept(user, "pin")

    # ── Password login (local only) ───────────────────────────────────────────
    def _login_pw(self):
        u = self.username_input.text().strip()
        p = self.password_input.text().strip()
        if not u or not p:
            self._show_error("Invalid credentials."); return
        try:
            from models.user import authenticate
            user = authenticate(u, p)
        except Exception as e:
            self._show_error("Invalid credentials."); return
        if not user:
            self._show_error("Invalid credentials.")
            self._set_btn_error(self._pw_btn)
            self._shake()
            self.password_input.clear(); self.password_input.setFocus()
            QTimer.singleShot(1400, lambda: self._set_btn_normal(self._pw_btn))
            return
        self._validate_and_accept(user, "local")

    # ── Completeness gate ─────────────────────────────────────────────────────
    def _validate_and_accept(self, user: dict, source: str):
        """
        Runs the completeness check before allowing login.
        Admin users bypass the check — they need to be able to fix things.
        """
        role = str(user.get("role") or "").lower()
        if role != "admin":
            ok, reason = _check_user_complete(user)
            if not ok:
                self._show_error("Invalid credentials.")
                self._shake()
                # Reset PIN buffer so they can't retry the same PIN
                self._pin_clear()
                return
        self._accept_user(user, source)

    # ── Accept ────────────────────────────────────────────────────────────────
    def _accept_user(self, user: dict, source: str):
        self.logged_in_user = user
        self.login_source   = source
        # Load API credentials from DB into memory for sync daemons
        try:
            from services.credentials import get_credentials, set_session
            k, s = get_credentials()
            if k and s:
                set_session(k, s)
                print(f"[login] ✅ Credentials ready ({source}): {k[:8]}...")
            else:
                print("[login] ⚠️  No API credentials in DB — syncing disabled until online login.")
        except Exception as e:
            print(f"[login] credential init: {e}")
        # Background user sync (non-blocking)
        self._bg_sync = BackgroundSyncWorker()
        self._bg_sync.start()
        self.accept()

    # ── Connectivity (display only — no auth decision made here) ──────────────
    def _check_connectivity(self):
        import urllib.request
        try:
            urllib.request.urlopen(f"https://{SITE_URL}", timeout=4)
            self._set_status(f"Online — {SITE_URL}", "#27ae60")
        except Exception:
            self._set_status("Offline — local database only", WARNING)

    def _set_status(self, msg, colour):
        self._status_dot.setStyleSheet(f"color:{colour}; font-size:7px; background:transparent;")
        self._status_lbl.setStyleSheet(f"color:{colour}; font-size:10px; background:transparent;")
        self._status_lbl.setText(msg)

    # ── Button helpers ────────────────────────────────────────────────────────
    def _set_btn_normal(self, btn):
        btn.setEnabled(True); btn.setText("Sign In  →")
        btn.setStyleSheet(f"""
            QPushButton {{ background:{NAVY}; color:{WHITE}; font-size:15px; font-weight:bold; border-radius:12px; border:none; }}
            QPushButton:hover   {{ background:{NAVY_3}; }}
            QPushButton:pressed {{ background:{ACCENT}; }}
        """)

    def _set_btn_loading(self, btn):
        btn.setEnabled(False); btn.setText("Signing in…")
        btn.setStyleSheet(f"QPushButton {{ background:{NAVY_2}; color:{MID}; font-size:15px; font-weight:bold; border-radius:12px; border:none; }}")

    def _set_btn_error(self, btn):
        btn.setEnabled(True); btn.setText("Try Again")
        btn.setStyleSheet(f"QPushButton {{ background:{DANGER}; color:{WHITE}; font-size:15px; font-weight:bold; border-radius:12px; border:none; }}")

    # ── Widget helpers ────────────────────────────────────────────────────────
    def _field_lbl(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color:{MUTED}; font-size:10px; font-weight:bold; background:transparent; letter-spacing:1.4px;")
        return lbl

    def _mk_lbl(self, text, style):
        lbl = QLabel(text); lbl.setAlignment(Qt.AlignCenter); lbl.setStyleSheet(style)
        return lbl

    def _input(self, placeholder, pw=False):
        inp = QLineEdit(); inp.setPlaceholderText(placeholder); inp.setFixedHeight(48)
        if pw: inp.setEchoMode(QLineEdit.Password)
        inp.setStyleSheet(f"""
            QLineEdit {{ background:{WHITE}; color:{NAVY}; border:1.5px solid {BORDER}; border-radius:12px; padding:0 18px; font-size:14px; }}
            QLineEdit:focus {{ border:1.5px solid {ACCENT}; }}
            QLineEdit:hover {{ border:1.5px solid {MID}; }}
        """)
        return inp

    def _show_error(self, msg):
        self.error_label.setText(f"  {msg}  ")
        self.error_label.show()

    def keyPressEvent(self, event):
        """Route keyboard digits/backspace/enter to PIN pad when on PIN tab."""
        if self._stack.currentIndex() != 0:
            super().keyPressEvent(event)
            return
        key = event.key()
        # Only numeric keys — NOT Enter/Return (those submit, not input)
        if Qt.Key_0 <= key <= Qt.Key_9 and key not in (Qt.Key_Return, Qt.Key_Enter):
            self._pin_press(str(key - Qt.Key_0))
        elif key in (Qt.Key_Backspace, Qt.Key_Delete):
            self._pin_backspace()
        elif key in (Qt.Key_Return, Qt.Key_Enter):
            self._login_pin()
        elif key == Qt.Key_Escape:
            self._pin_buffer = ""
            self._pin_dots.set_filled(0)
            self.error_label.hide()
        else:
            super().keyPressEvent(event)

    def _shake(self):
        pos = self.pos()
        self.anim = QPropertyAnimation(self, b"pos")
        self.anim.setDuration(280); self.anim.setEasingCurve(QEasingCurve.OutElastic)
        for t, dx in [(0,0),(0.15,-12),(0.35,12),(0.55,-8),(0.75,8),(1,0)]:
            self.anim.setKeyValueAt(t, pos + QPoint(dx, 0))
        self.anim.start()