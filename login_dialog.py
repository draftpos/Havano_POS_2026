# =============================================================================
# views/login_dialog.py  —  Havano POS Login Dialog
# =============================================================================
#
#  Changes implemented (from task list):
#
#  #1  — Cancel button removed. The dialog is FramelessWindowHint with no
#         reject path; closing the OS window quits the application.
#
#  #18 — MainWindow now always starts at stack index 0 (POS view) for ALL
#         users, including admin.  The dashboard is still available via the
#         menu but is not the first screen.  See main_window.py note at the
#         bottom of this file.
#
#  #19 — PIN login is the PRIMARY tab (index 0).  Each user record in the
#         local DB has a `pin` column (4–6 digits).  `authenticate_by_pin()`
#         in models/user.py is used directly.  The online email/password tab
#         is still available as the secondary ("Email") tab.
#
#  #27 — After accept() the caller (main.py / _logout) replaces this dialog
#         with the MainWindow.  The dialog is not kept alive behind the POS.
#         We also call self.hide() immediately inside _accept_user() so that
#         the dialog disappears the instant the user is authenticated, before
#         MainWindow.show() is called by the caller.
#
#  #40 — On the Email/Password tab a small eye-toggle button sits inside the
#         password field.  Clicking it toggles between Password and Normal
#         echo mode so the user can verify what they typed.
#
#  OFFLINE FIX — LoginWorker calls auth_service.login() which already
#         handles the online→offline fallback internally.  If online fails
#         (network error / timeout) it automatically tries models.user.authenticate
#         against the local SQLite DB.  auth_failed=True (wrong password) skips
#         the offline attempt so a bad password is rejected immediately.
#
# =============================================================================

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QWidget, QGraphicsDropShadowEffect,
    QStackedWidget, QGridLayout, QSizePolicy, QApplication,
)
from PySide6.QtCore import (
    Qt, QPropertyAnimation, QPoint, QTimer, QEasingCurve,
    QThread, Signal, QSize,
)
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen

# =============================================================================
# Palette  (mirrors main_window.py so the two files stay in sync)
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
# Background workers
# =============================================================================
class LoginWorker(QThread):
    """
    Runs auth_service.login() off the UI thread.

    auth_service.login() already handles the full online → offline fallback:
      1. Tries online API.
      2. If network fails  → falls back to models.user.authenticate (local DB).
      3. If auth_failed    → skips offline (wrong password) and returns error.

    So the dialog does NOT need its own offline retry — it just reads
    result["source"] to know how the login succeeded.
    """
    finished = Signal(dict)

    def __init__(self, username: str, password: str):
        super().__init__()
        self.username = username
        self.password = password

    def run(self):
        print(f"[login] ▶ LoginWorker started — username={self.username!r}")
        try:
            from services.auth_service import login
            result = login(self.username, self.password)
            print(f"[login] ◀ auth_service.login() returned: "
                  f"success={result.get('success')}, "
                  f"source={result.get('source')!r}, "
                  f"error={result.get('error')!r}")
            self.finished.emit(result)
        except Exception as e:
            import traceback
            print(f"[login] ✗ LoginWorker EXCEPTION:\n{traceback.format_exc()}")
            self.finished.emit({"success": False, "error": str(e), "source": "exception"})


class BackgroundSyncWorker(QThread):
    """Syncs users + products after a successful login (non-blocking)."""

    def run(self):
        try:
            from services.user_sync_service import sync_users
            sync_users()
        except Exception as e:
            print(f"[bg-sync] users: {e}")
        try:
            from services.sync_service import SyncWorker
            SyncWorker().run()
        except Exception as e:
            print(f"[bg-sync] products: {e}")


# =============================================================================
# PIN dot indicator widget
# =============================================================================
class PinDots(QWidget):
    """Draws N circles, filling them as the user types their PIN."""

    def __init__(self, length: int = 6, parent=None):
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
        r    = 9
        gap  = 28
        x0   = (self.width() - (self.length * gap - 2)) // 2
        y    = self.height() // 2
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
# Main dialog
# =============================================================================
class LoginDialog(QDialog):
    """
    Login dialog — PIN-first, Email/Password as fallback tab.

    After exec() == QDialog.Accepted:
        dialog.logged_in_user  → {"id", "username", "role", ...}
        dialog.login_source    → "pin" | "online" | "offline"
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Havano POS")
        self.setFixedSize(480, 670)

        # #1 — No cancel: FramelessWindowHint removes the OS close button from
        #      the dialog chrome.  closeEvent below quits the app instead.
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.logged_in_user: dict | None = None
        self.login_source: str | None    = None
        self._worker: LoginWorker | None = None
        self._pin_buffer: str            = ""

        self._build_ui()
        QTimer.singleShot(400, self._check_connectivity)

    # -------------------------------------------------------------------------
    # #1 — Prevent the dialog from being dismissed without logging in
    # -------------------------------------------------------------------------
    def closeEvent(self, event):
        """Closing the login dialog exits the application entirely."""
        QApplication.quit()
        event.accept()

    def reject(self):
        """Disable the default Escape-to-close behaviour."""
        pass

    # =========================================================================
    # UI construction
    # =========================================================================
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)

        # ── Outer card ────────────────────────────────────────────────────────
        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet("QFrame#card { background-color: #ffffff; border-radius: 20px; }")

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(60)
        shadow.setXOffset(0)
        shadow.setYOffset(16)
        shadow.setColor(QColor(13, 31, 60, 100))
        card.setGraphicsEffect(shadow)

        vl = QVBoxLayout(card)
        vl.setSpacing(0)
        vl.setContentsMargins(0, 0, 0, 0)

        # ── Header with close button ───────────────────────────────────────────
        hdr = QWidget()
        hdr.setFixedHeight(148)
        hdr.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 {NAVY}, stop:0.6 {NAVY_2}, stop:1 {NAVY_3});
                border-top-left-radius: 20px;
                border-top-right-radius: 20px;
            }}
        """)
        hl = QVBoxLayout(hdr)
        hl.setContentsMargins(0, 12, 12, 20)
        hl.setSpacing(6)

        # Top row with close button
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.addStretch()
        
        # Close button (X) - stays with existing styling
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(32, 32)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255, 255, 255, 0.15);
                color: {WHITE};
                border: none;
                border-radius: 16px;
                font-size: 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: rgba(255, 255, 255, 0.25);
            }}
            QPushButton:pressed {{
                background: rgba(255, 255, 255, 0.35);
            }}
        """)
        self.close_btn.clicked.connect(self._close_app)
        top_row.addWidget(self.close_btn)
        hl.addLayout(top_row)

        logo_lbl = QLabel("H")
        logo_lbl.setAlignment(Qt.AlignCenter)
        logo_lbl.setFixedSize(44, 44)
        logo_lbl.setStyleSheet(f"""
            background: {ACCENT}; color: {WHITE}; border-radius: 12px;
            font-size: 22px; font-weight: 900; letter-spacing: -1px;
        """)
        logo_row = QHBoxLayout()
        logo_row.addStretch()
        logo_row.addWidget(logo_lbl)
        logo_row.addStretch()
        hl.addLayout(logo_row)

        title = QLabel("Havano POS")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            f"color:{WHITE}; font-size:22px; font-weight:800; "
            "background:transparent; letter-spacing:1px;"
        )
        hl.addWidget(title)

        sub = QLabel("Sign in to continue")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet(
            f"color:{MID}; font-size:11px; background:transparent; letter-spacing:0.4px;"
        )
        hl.addWidget(sub)
        vl.addWidget(hdr)

        # ── Accent line ───────────────────────────────────────────────────────
        accent_line = QFrame()
        accent_line.setFixedHeight(3)
        accent_line.setStyleSheet(f"""
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 {NAVY_3}, stop:0.3 {ACCENT}, stop:0.7 {ACCENT_H}, stop:1 {NAVY_3});
        """)
        vl.addWidget(accent_line)

        # ── Connectivity status bar ───────────────────────────────────────────
        self._status_bar = QWidget()
        self._status_bar.setFixedHeight(24)
        self._status_bar.setStyleSheet(f"background:{NAVY_2}; border:none;")
        sl = QHBoxLayout(self._status_bar)
        sl.setContentsMargins(20, 0, 20, 0)
        sl.setSpacing(6)
        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet(f"color:{MID}; font-size:7px; background:transparent;")
        self._status_lbl = QLabel("Checking connection…")
        self._status_lbl.setStyleSheet(f"color:{MID}; font-size:10px; background:transparent;")
        sl.addStretch()
        sl.addWidget(self._status_dot)
        sl.addWidget(self._status_lbl)
        sl.addStretch()
        vl.addWidget(self._status_bar)

        # ── Tab toggle: PIN | Email ───────────────────────────────────────────
        tab_row = QWidget()
        tab_row.setStyleSheet(f"background:{OFF_WHITE};")
        tl = QHBoxLayout(tab_row)
        tl.setContentsMargins(28, 10, 28, 0)
        tl.setSpacing(8)

        self._pin_tab   = QPushButton("  🔢  PIN")
        self._email_tab = QPushButton("  🔑  Email Login")
        for b in (self._pin_tab, self._email_tab):
            b.setFixedHeight(36)
            b.setCursor(Qt.PointingHandCursor)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._pin_tab.clicked.connect(lambda: self._switch_mode(0))
        self._email_tab.clicked.connect(lambda: self._switch_mode(1))
        tl.addWidget(self._pin_tab)
        tl.addWidget(self._email_tab)
        vl.addWidget(tab_row)

        # ── Stacked pages ─────────────────────────────────────────────────────
        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background:{OFF_WHITE};")
        self._stack.addWidget(self._build_pin_page())    # index 0 — PIN  (#19)
        self._stack.addWidget(self._build_email_page())  # index 1 — Email (#40)
        vl.addWidget(self._stack, 1)

        # ── Error label ───────────────────────────────────────────────────────
        err_w = QWidget()
        err_w.setStyleSheet(f"background:{OFF_WHITE};")
        el = QHBoxLayout(err_w)
        el.setContentsMargins(28, 0, 28, 8)
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

        # ── Footer ────────────────────────────────────────────────────────────
        footer = QWidget()
        footer.setFixedHeight(36)
        footer.setStyleSheet(
            f"background:{CREAM}; border-bottom-left-radius:20px; "
            "border-bottom-right-radius:20px;"
        )
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(f"🌐  {SITE_URL}")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(
            f"font-size:10px; color:{NAVY}; background:transparent; "
            "letter-spacing:0.5px; font-weight:bold;"
        )
        fl.addWidget(lbl)
        vl.addWidget(footer)

        root.addWidget(card)
        self._switch_mode(0)   # start on PIN tab

    def _close_app(self):
        """Close the application when the X button is clicked."""
        # Call the close event which will quit the application
        self.close()

    # =========================================================================
    # PIN page  (#19 — PIN login as primary method)
    # =========================================================================
    def _build_pin_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet(f"background:{OFF_WHITE};")
        pl = QVBoxLayout(page)
        pl.setContentsMargins(28, 18, 28, 12)
        pl.setSpacing(14)
        pl.setAlignment(Qt.AlignTop)

        # Dot indicator card
        dot_card = QWidget()
        dot_card.setStyleSheet(f"""
            background:{WHITE}; border-radius:14px;
            border:1.5px solid {BORDER};
        """)
        dot_card.setFixedHeight(58)
        dcl = QHBoxLayout(dot_card)
        dcl.setContentsMargins(0, 0, 0, 0)
        self._pin_dots = PinDots(6)
        dcl.addStretch()
        dcl.addWidget(self._pin_dots)
        dcl.addStretch()
        pl.addWidget(dot_card)

        # Numpad grid
        grid_w = QWidget()
        grid_w.setStyleSheet("background:transparent;")
        grid = QGridLayout(grid_w)
        grid.setSpacing(10)
        grid.setContentsMargins(0, 0, 0, 0)

        keys = [
            ("1", "d"), ("2", "d"), ("3", "d"),
            ("4", "d"), ("5", "d"), ("6", "d"),
            ("7", "d"), ("8", "d"), ("9", "d"),
            ("⌫", "b"), ("0", "d"), ("✓", "e"),
        ]
        for i, (label, kind) in enumerate(keys):
            btn = QPushButton(label)
            btn.setFixedSize(108, 52)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFont(QFont("Segoe UI", 16, QFont.Bold))

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
                btn.clicked.connect(lambda _, d=label: self._pin_press(d))

            elif kind == "b":
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background:{LIGHT}; color:{MUTED};
                        border:1.5px solid {BORDER}; border-radius:12px;
                        font-size:18px; font-weight:bold;
                    }}
                    QPushButton:hover   {{ background:{BORDER}; color:{NAVY}; }}
                    QPushButton:pressed {{ background:{NAVY}; color:{WHITE}; }}
                """)
                btn.clicked.connect(self._pin_backspace)

            elif kind == "e":
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background:{ACCENT}; color:{WHITE};
                        border:none; border-radius:12px;
                        font-size:20px; font-weight:bold;
                    }}
                    QPushButton:hover   {{ background:{ACCENT_H}; }}
                    QPushButton:pressed {{ background:{NAVY_2}; }}
                """)
                btn.clicked.connect(self._login_pin)

            grid.addWidget(btn, i // 3, i % 3)

        pl.addWidget(grid_w)
        return page

    # =========================================================================
    # Email / Password page  (#40 — password visibility toggle)
    # =========================================================================
    def _build_email_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet(f"background:{OFF_WHITE};")
        pl = QVBoxLayout(page)
        pl.setContentsMargins(28, 20, 28, 12)
        pl.setSpacing(6)
        pl.setAlignment(Qt.AlignTop)

        # Username
        pl.addWidget(self._field_lbl("USERNAME / EMAIL"))
        pl.addSpacing(4)
        self.username_input = self._input("Enter your username or email")
        self.username_input.returnPressed.connect(
            lambda: self.password_input.setFocus()
        )
        pl.addWidget(self.username_input)
        pl.addSpacing(14)

        # Password row with eye-toggle (#40)
        pl.addWidget(self._field_lbl("PASSWORD"))
        pl.addSpacing(4)

        pw_container = QWidget()
        pw_container.setStyleSheet("background:transparent;")
        pw_row = QHBoxLayout(pw_container)
        pw_row.setContentsMargins(0, 0, 0, 0)
        pw_row.setSpacing(0)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Enter your password")
        self.password_input.setFixedHeight(48)
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setStyleSheet(f"""
            QLineEdit {{
                background:{WHITE}; color:{NAVY};
                border:1.5px solid {BORDER};
                border-top-left-radius:12px;
                border-bottom-left-radius:12px;
                border-top-right-radius:0px;
                border-bottom-right-radius:0px;
                padding:0 14px; font-size:14px;
            }}
            QLineEdit:focus {{ border:1.5px solid {ACCENT}; }}
            QLineEdit:hover {{ border:1.5px solid {MID}; }}
        """)
        self.password_input.returnPressed.connect(self._login_email)

        # Eye-toggle button
        self._eye_btn = QPushButton("👁")
        self._eye_btn.setFixedSize(48, 48)
        self._eye_btn.setCursor(Qt.PointingHandCursor)
        self._eye_btn.setCheckable(True)
        self._eye_btn.setStyleSheet(f"""
            QPushButton {{
                background:{WHITE}; color:{MUTED};
                border:1.5px solid {BORDER};
                border-left:none;
                border-top-right-radius:12px;
                border-bottom-right-radius:12px;
                font-size:16px;
            }}
            QPushButton:hover   {{ background:{LIGHT}; color:{NAVY}; }}
            QPushButton:checked {{ background:{LIGHT}; color:{ACCENT}; }}
        """)
        self._eye_btn.toggled.connect(self._toggle_password_visibility)

        pw_row.addWidget(self.password_input, 1)
        pw_row.addWidget(self._eye_btn)
        pl.addWidget(pw_container)
        pl.addSpacing(18)

        # Sign-in button
        self._email_btn = QPushButton("Sign In  →")
        self._email_btn.setFixedHeight(52)
        self._email_btn.setCursor(Qt.PointingHandCursor)
        self._set_btn_normal(self._email_btn)
        self._email_btn.clicked.connect(self._login_email)
        pl.addWidget(self._email_btn)
        pl.addStretch()
        return page

    # =========================================================================
    # Tab switching
    # =========================================================================
    def _switch_mode(self, idx: int):
        self._stack.setCurrentIndex(idx)
        self.error_label.hide()

        active_style = f"""
            QPushButton {{
                background:{NAVY}; color:{WHITE}; border:none;
                border-radius:10px; font-size:12px; font-weight:bold;
            }}
        """
        inactive_style = f"""
            QPushButton {{
                background:{WHITE}; color:{MUTED}; border:1.5px solid {BORDER};
                border-radius:10px; font-size:12px;
            }}
            QPushButton:hover {{ background:{LIGHT}; color:{NAVY}; }}
        """
        self._pin_tab.setStyleSheet(active_style if idx == 0 else inactive_style)
        self._email_tab.setStyleSheet(active_style if idx == 1 else inactive_style)

        if idx == 0:
            self.setFocus()   # keyboard digits go to keyPressEvent → _pin_press
        else:
            self.username_input.setFocus()

    # =========================================================================
    # #40 — Password visibility toggle
    # =========================================================================
    def _toggle_password_visibility(self, checked: bool):
        self.password_input.setEchoMode(
            QLineEdit.Normal if checked else QLineEdit.Password
        )

    # =========================================================================
    # PIN login  (#19)
    # =========================================================================
    def _pin_press(self, digit: str):
        if len(self._pin_buffer) >= 6:
            return
        self._pin_buffer += digit
        self._pin_dots.set_filled(len(self._pin_buffer))
        self.error_label.hide()

        if len(self._pin_buffer) == 6:
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
        print(f"[login] PIN attempt — length={len(pin)}")
        try:
            from models.user import authenticate_by_pin
            user = authenticate_by_pin(pin)
            print(f"[login] authenticate_by_pin() returned: {user!r}")
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"[login] PIN auth EXCEPTION:\n{tb}")
            self._show_error(f"Local DB error: {e}")
            return
        if not user:
            print("[login] PIN not found in DB")
            self._show_error("Incorrect PIN.  Please try again.")
            self._pin_clear()
            self._shake()
            return
        print(f"[login] PIN OK — user={user.get('username')!r} role={user.get('role')!r}")
        self._validate_and_accept(user, "pin")

    # =========================================================================
    # Email / Password login
    # auth_service.login() handles the full online → offline fallback:
    #   • Online succeeds       → source = "online"
    #   • Network fails         → offline DB attempted → source = "offline"
    #   • Wrong password online → auth_failed=True, offline skipped → error shown
    # =========================================================================
    def _login_email(self):
        u = self.username_input.text().strip()
        p = self.password_input.text().strip()
        if not u or not p:
            self._show_error("Please enter your username and password.")
            return

        self._set_btn_loading(self._email_btn)
        self.error_label.hide()

        self._worker = LoginWorker(u, p)
        self._worker.finished.connect(self._on_email_login_done)
        self._worker.start()

    def _on_email_login_done(self, result: dict):
        self._worker = None
        print(f"[login] _on_email_login_done — success={result.get('success')}, "
              f"source={result.get('source')!r}, error={result.get('error')!r}")

        if result.get("success"):
            user   = result["user"]
            source = result.get("source", "online")  # "online" or "offline"
            self._set_btn_normal(self._email_btn)
            print(f"[login] Logged in as {user.get('username')!r} "
                  f"role={user.get('role')!r} source={source!r}")
            print(f"[login] User fields — company={user.get('company')!r} "
                  f"warehouse={user.get('warehouse')!r} "
                  f"cost_center={user.get('cost_center')!r}")

            # Show a brief offline notice so the cashier knows they're offline
            if source == "offline":
                self._show_info("⚠️  Offline mode — using local account.")

            self._validate_and_accept(user, source)
            return

        # Both online and offline failed
        err = result.get("error", "Login failed.")
        source = result.get("source", "")
        print(f"[login] FAILED — source={source!r} error={err!r}")
        print(f"[login] Full result dict: {result}")

        # Give a clearer message depending on where it failed
        if source == "offline":
            display_err = f"Login failed (offline): {err}"
        else:
            display_err = err

        self._show_error(display_err)
        self._set_btn_error(self._email_btn)
        self._shake()
        self.password_input.clear()
        self.password_input.setFocus()
        QTimer.singleShot(1800, lambda: self._set_btn_normal(self._email_btn))
        QTimer.singleShot(500, self._check_connectivity)

    # =========================================================================
    # Completeness gate
    # =========================================================================
    def _validate_and_accept(self, user: dict, source: str):
        """
        Admin users bypass the completeness check.
        PIN logins pass even without company/warehouse/cost_center.
        Email logins check completeness and, if the user has no PIN set,
        prompt them to create one before proceeding.
        """
        role = str(user.get("role") or "").lower()
        print(f"[login] _validate_and_accept — role={role!r} source={source!r}")

        if role != "admin":
            ok, reason = _check_user_complete(user, source)
            print(f"[login] completeness check — ok={ok} reason={reason!r}")
            if not ok:
                self._show_error(reason)
                self._shake()
                self._pin_clear()
                return

        # After a successful email/online login, if the user has no PIN yet,
        # ask them to set one now so they can use the PIN tab next time.
        if source in ("online", "offline") and not (user.get("pin") or "").strip():
            self._prompt_set_pin(user, source)
            return

        self._accept_user(user, source)

    # =========================================================================
    # PIN setup prompt — shown after first email login when no PIN exists
    # =========================================================================
    def _prompt_set_pin(self, user: dict, source: str):
        """
        Shows a modal PIN-setup overlay so the user can set their 4-6 digit
        PIN right after their first email login.  Saving the PIN calls
        models.user.set_user_pin() which writes to the local DB only —
        sync will never overwrite a non-empty local PIN.
        """
        self._pin_setup_user   = user
        self._pin_setup_source = source
        self._pin_setup_buf    = ""
        self._pin_setup_step   = "enter"   # "enter" | "confirm"
        self._pin_setup_first  = ""

        # ── Overlay widget ────────────────────────────────────────────────────
        overlay = QWidget(self)
        overlay.setObjectName("pinSetupOverlay")
        overlay.setGeometry(0, 0, self.width(), self.height())
        overlay.setStyleSheet("""
            QWidget#pinSetupOverlay {
                background: rgba(13, 31, 60, 0.92);
                border-radius: 20px;
            }
        """)

        vl = QVBoxLayout(overlay)
        vl.setContentsMargins(36, 48, 36, 36)
        vl.setSpacing(16)

        # Skip button (top-right)
        skip_row = QHBoxLayout()
        skip_row.addStretch()
        skip_btn = QPushButton("Skip for now")
        skip_btn.setCursor(Qt.PointingHandCursor)
        skip_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {MID};
                border: 1px solid {MUTED}; border-radius: 8px;
                font-size: 11px; padding: 4px 12px;
            }}
            QPushButton:hover {{ color: {WHITE}; border-color: {WHITE}; }}
        """)
        skip_btn.clicked.connect(lambda: self._finish_pin_setup(overlay, save=False))
        skip_row.addWidget(skip_btn)
        vl.addLayout(skip_row)

        # Icon + title
        icon_lbl = QLabel("🔢")
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("font-size: 36px; background: transparent;")
        vl.addWidget(icon_lbl)

        self._pin_setup_title = QLabel("Set Your PIN")
        self._pin_setup_title.setAlignment(Qt.AlignCenter)
        self._pin_setup_title.setStyleSheet(
            f"color: {WHITE}; font-size: 20px; font-weight: 800; background: transparent;"
        )
        vl.addWidget(self._pin_setup_title)

        self._pin_setup_sub = QLabel("Enter a 4–6 digit PIN for quick login next time.")
        self._pin_setup_sub.setAlignment(Qt.AlignCenter)
        self._pin_setup_sub.setWordWrap(True)
        self._pin_setup_sub.setStyleSheet(
            f"color: {MID}; font-size: 12px; background: transparent;"
        )
        vl.addWidget(self._pin_setup_sub)

        # Dot indicator
        dot_card = QWidget()
        dot_card.setStyleSheet(f"""
            background: rgba(255,255,255,0.08); border-radius: 12px;
            border: 1px solid rgba(255,255,255,0.15);
        """)
        dot_card.setFixedHeight(52)
        dcl = QHBoxLayout(dot_card)
        self._pin_setup_dots = PinDots(6)
        dcl.addStretch()
        dcl.addWidget(self._pin_setup_dots)
        dcl.addStretch()
        vl.addWidget(dot_card)

        # Error label for setup
        self._pin_setup_err = QLabel("")
        self._pin_setup_err.setAlignment(Qt.AlignCenter)
        self._pin_setup_err.setStyleSheet(
            f"color: {DANGER}; font-size: 12px; font-weight: bold; background: transparent;"
        )
        self._pin_setup_err.hide()
        vl.addWidget(self._pin_setup_err)

        # Numpad
        grid_w = QWidget()
        grid_w.setStyleSheet("background: transparent;")
        grid = QGridLayout(grid_w)
        grid.setSpacing(8)
        grid.setContentsMargins(0, 0, 0, 0)

        keys = [
            ("1","d"),("2","d"),("3","d"),
            ("4","d"),("5","d"),("6","d"),
            ("7","d"),("8","d"),("9","d"),
            ("⌫","b"),("0","d"),("✓","e"),
        ]
        for i, (label, kind) in enumerate(keys):
            btn = QPushButton(label)
            btn.setFixedSize(98, 46)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFont(QFont("Segoe UI", 15, QFont.Bold))
            if kind == "d":
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: rgba(255,255,255,0.12); color: {WHITE};
                        border: 1px solid rgba(255,255,255,0.2); border-radius: 10px;
                        font-size: 17px; font-weight: bold;
                    }}
                    QPushButton:hover   {{ background: rgba(255,255,255,0.22); }}
                    QPushButton:pressed {{ background: {ACCENT}; border-color: {ACCENT}; }}
                """)
                btn.clicked.connect(lambda _, d=label: self._pin_setup_press(d))
            elif kind == "b":
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: rgba(255,255,255,0.07); color: {MID};
                        border: 1px solid rgba(255,255,255,0.12); border-radius: 10px;
                        font-size: 17px;
                    }}
                    QPushButton:hover {{ background: rgba(255,255,255,0.15); color: {WHITE}; }}
                """)
                btn.clicked.connect(self._pin_setup_backspace)
            elif kind == "e":
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {ACCENT}; color: {WHITE};
                        border: none; border-radius: 10px;
                        font-size: 20px; font-weight: bold;
                    }}
                    QPushButton:hover   {{ background: {ACCENT_H}; }}
                    QPushButton:pressed {{ background: {NAVY_2}; }}
                """)
                btn.clicked.connect(self._pin_setup_confirm)
            grid.addWidget(btn, i // 3, i % 3)

        vl.addWidget(grid_w)
        overlay.show()
        self._pin_setup_overlay = overlay

    def _pin_setup_press(self, digit: str):
        if len(self._pin_setup_buf) >= 6:
            return
        self._pin_setup_buf += digit
        self._pin_setup_dots.set_filled(len(self._pin_setup_buf))
        self._pin_setup_err.hide()

    def _pin_setup_backspace(self):
        self._pin_setup_buf = self._pin_setup_buf[:-1]
        self._pin_setup_dots.set_filled(len(self._pin_setup_buf))

    def _pin_setup_confirm(self):
        buf = self._pin_setup_buf.strip()
        if len(buf) < 4:
            self._pin_setup_err.setText("PIN must be at least 4 digits.")
            self._pin_setup_err.show()
            return

        if self._pin_setup_step == "enter":
            # First entry — ask to confirm
            self._pin_setup_first = buf
            self._pin_setup_buf   = ""
            self._pin_setup_step  = "confirm"
            self._pin_setup_dots.set_filled(0)
            self._pin_setup_title.setText("Confirm Your PIN")
            self._pin_setup_sub.setText("Enter the same PIN again to confirm.")
            self._pin_setup_err.hide()
        else:
            # Confirmation step
            if buf != self._pin_setup_first:
                self._pin_setup_buf  = ""
                self._pin_setup_step = "enter"
                self._pin_setup_first = ""
                self._pin_setup_dots.set_filled(0)
                self._pin_setup_title.setText("Set Your PIN")
                self._pin_setup_sub.setText("PINs didn't match — try again.")
                self._pin_setup_err.setText("PINs did not match.  Please start over.")
                self._pin_setup_err.show()
                return
            # Save PIN
            self._finish_pin_setup(self._pin_setup_overlay, save=True, pin=buf)

    def _finish_pin_setup(self, overlay: QWidget, save: bool, pin: str = ""):
        if save and pin:
            user_id = self._pin_setup_user.get("id")
            if user_id:
                try:
                    from models.user import set_user_pin
                    set_user_pin(user_id, pin)
                    self._pin_setup_user["pin"] = pin
                    print(f"[login] ✅ PIN saved for user id={user_id}")
                except Exception as e:
                    print(f"[login] ⚠️  Could not save PIN: {e}")
        overlay.hide()
        overlay.deleteLater()
        self._accept_user(self._pin_setup_user, self._pin_setup_source)

    # =========================================================================
    # Accept  (#27 — hide immediately so POS appears without the dialog behind)
    # =========================================================================
    def _accept_user(self, user: dict, source: str):
        self.logged_in_user = user
        self.login_source   = source

        # Restore credentials into memory so background daemons can sync
        try:
            from services.credentials import get_credentials, set_session
            k, s = get_credentials()
            if k and s:
                set_session(k, s)
                print(f"[login] ✅ Credentials ready ({source}): {k[:8]}…")
            else:
                print("[login] ⚠️  No API credentials — log in with email once to enable sync.")
        except Exception as e:
            print(f"[login] credential init: {e}")

        # #27 — hide the dialog immediately; MainWindow appears with nothing behind it
        self.hide()

        # Background sync (non-blocking) — runs for ALL login sources
        # (pin, online, offline) as long as stored API credentials exist.
        # PIN logins reuse the credentials saved from the last email login.
        try:
            from services.credentials import get_credentials
            k, s = get_credentials()
            has_creds = bool(k and s)
        except Exception:
            has_creds = False

        if has_creds:
            self._bg_sync = BackgroundSyncWorker()
            self._bg_sync.start()
            print(f"[login] 🔄 Background sync started (source={source!r})")
        else:
            print("[login] ⚠️  No credentials found — sync skipped. Log in with email once.")

        self.accept()   # QDialog.Accepted — caller can read .logged_in_user

    # =========================================================================
    # Connectivity check
    # =========================================================================
    def _check_connectivity(self):
        import urllib.request
        try:
            urllib.request.urlopen(f"https://{SITE_URL}", timeout=4)
            self._set_status(f"Online — {SITE_URL}", "#27ae60")
        except Exception:
            self._set_status("Offline — local database only", WARNING)

    def _set_status(self, msg: str, colour: str):
        self._status_dot.setStyleSheet(
            f"color:{colour}; font-size:7px; background:transparent;"
        )
        self._status_lbl.setStyleSheet(
            f"color:{colour}; font-size:10px; background:transparent;"
        )
        self._status_lbl.setText(msg)

    # =========================================================================
    # Button helpers
    # =========================================================================
    def _set_btn_normal(self, btn: QPushButton):
        btn.setEnabled(True)
        btn.setText("Sign In  →")
        btn.setStyleSheet(f"""
            QPushButton {{
                background:{NAVY}; color:{WHITE}; font-size:15px; font-weight:bold;
                border-radius:12px; border:none;
            }}
            QPushButton:hover   {{ background:{NAVY_3}; }}
            QPushButton:pressed {{ background:{ACCENT}; }}
        """)

    def _set_btn_loading(self, btn: QPushButton):
        btn.setEnabled(False)
        btn.setText("Signing in…")
        btn.setStyleSheet(f"""
            QPushButton {{
                background:{NAVY_2}; color:{MID}; font-size:15px; font-weight:bold;
                border-radius:12px; border:none;
            }}
        """)

    def _set_btn_error(self, btn: QPushButton):
        btn.setEnabled(True)
        btn.setText("Try Again")
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
        inp.setPlaceholderText(placeholder)
        inp.setFixedHeight(48)
        inp.setStyleSheet(f"""
            QLineEdit {{
                background:{WHITE}; color:{NAVY};
                border:1.5px solid {BORDER}; border-radius:12px;
                padding:0 18px; font-size:14px;
            }}
            QLineEdit:focus {{ border:1.5px solid {ACCENT}; }}
            QLineEdit:hover {{ border:1.5px solid {MID}; }}
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
        """Shows a non-error (warning/info) message in the status area."""
        self.error_label.setStyleSheet(f"""
            color:{WHITE}; background:{WARNING}; font-size:12px; font-weight:bold;
            border-radius:8px; padding:6px 14px;
        """)
        self.error_label.setText(f"  {msg}  ")
        self.error_label.show()
        QTimer.singleShot(3000, self.error_label.hide)

    # =========================================================================
    # Keyboard handling
    # =========================================================================
    def keyPressEvent(self, event):
        key = event.key()

        if self._stack.currentIndex() == 0:
            # ── PIN tab ───────────────────────────────────────────────────────
            if key in (Qt.Key_Return, Qt.Key_Enter):
                self._login_pin()
            elif Qt.Key_0 <= key <= Qt.Key_9:
                self._pin_press(str(key - Qt.Key_0))
            elif key in (Qt.Key_Backspace, Qt.Key_Delete):
                self._pin_backspace()
            elif key == Qt.Key_Escape:
                self._pin_clear()
            else:
                super().keyPressEvent(event)
        else:
            # ── Email tab — QLineEdit returnPressed signals handle Enter ──────
            super().keyPressEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self.setFocus()
        self.activateWindow()
        self.raise_()

    # =========================================================================
    # Shake animation (wrong PIN / bad credentials)
    # =========================================================================
    def _shake(self):
        pos = self.pos()
        self.anim = QPropertyAnimation(self, b"pos")
        self.anim.setDuration(280)
        self.anim.setEasingCurve(QEasingCurve.OutElastic)
        for t, dx in [(0, 0), (0.15, -12), (0.35, 12), (0.55, -8), (0.75, 8), (1, 0)]:
            self.anim.setKeyValueAt(t, pos + QPoint(dx, 0))
        self.anim.start()


# =============================================================================
# Completeness check helper
# =============================================================================
def _check_user_complete(user: dict, source: str = "") -> tuple[bool, str]:
    """
    Returns (True, "") if the user record has all required fields,
    or (False, reason_string) if something is missing.

    Rules:
    - Disabled accounts are always blocked.
    - PIN logins: only blocked if account is disabled — missing company/
      warehouse/cost_center are NOT a blocker (those come from server defaults
      set during an online email login).
    - Email (online/offline) logins: company, warehouse and cost_center must
      all be present; missing fields are listed explicitly in the error.
    """
    if not user.get("active", True):
        return False, "Your account is disabled.  Please contact your administrator."

    if source == "pin":
        return True, ""

    required = {
        "company":     "Company",
        "warehouse":   "Warehouse",
        "cost_center": "Cost Center",
    }
    missing = [label for field, label in required.items()
               if not (user.get(field) or "").strip()]
    if missing:
        fields = ",  ".join(missing)
        return (
            False,
            f"Account incomplete — missing: {fields}.  Ask your administrator to update your server profile."
        )
    return True, ""


# =============================================================================
# NOTE for main_window.py — Point #18
# =============================================================================
# In MainWindow.__init__, change:
#
#   if is_admin(self.user):
#       self._stack.setCurrentIndex(1)   ← goes to dashboard
#   else:
#       self._stack.setCurrentIndex(0)
#
# To:
#
#   self._stack.setCurrentIndex(0)       ← always start on POS
#
# The dashboard remains accessible via the "Sales" or navigation menu.
# This ensures ALL users — including admin — land on the POS screen first.
# =============================================================================