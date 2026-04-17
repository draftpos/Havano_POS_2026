from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QWidget, QGraphicsDropShadowEffect,
    QStackedWidget, QGridLayout, QSizePolicy, QApplication,
)
from PySide6.QtCore import (
    Qt, QTimer, QEvent,
    QThread, Signal, QSize,
)
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
import sys
import os

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
# Background workers
# =============================================================================
class LoginWorker(QThread):
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
    def run(self):
        # 1. Sync users
        try:
            from services.user_sync_service import sync_users
            sync_users()
        except Exception as e:
            print(f"[bg-sync] users: {e}")
        # 2. Sync products + taxes via SyncWorker (runs debug subprocess internally)
        try:
            from services.sync_service import SyncWorker
            SyncWorker().run()
        except Exception as e:
            print(f"[bg-sync] products+taxes: {e}")


# =============================================================================
# PIN dot indicator widget
# =============================================================================
class PinDots(QWidget):
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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Havano POS")
        self.setFixedSize(480, 700)

        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.logged_in_user: dict | None = None
        self.login_source: str | None    = None
        self._worker: LoginWorker | None = None
        self._pin_buffer: str            = ""

        self._build_ui()
        QTimer.singleShot(400, self._check_connectivity)

        # Install app-level event filter — catches keys no matter which
        # child widget has focus, so keyboard always feeds the PIN buffer.
        QApplication.instance().installEventFilter(self)

    # =========================================================================
    # App-level event filter
    # =========================================================================
    def eventFilter(self, obj, event):
        try:
            from PySide6.QtGui import QKeyEvent
            if event.type() == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
                key = event.key()

                # ── PIN setup overlay is visible — feed keys into it ──────────
                if hasattr(self, "_pin_setup_overlay") and self._pin_setup_overlay.isVisible():
                    if key in (Qt.Key_Return, Qt.Key_Enter):
                        self._pin_setup_confirm()
                        return True
                    elif key in (Qt.Key_Backspace, Qt.Key_Delete):
                        self._pin_setup_backspace()
                        return True
                    elif key == Qt.Key_Escape:
                        self._pin_setup_buf = ""
                        self._pin_setup_dots.set_filled(0)
                        return True
                    elif Qt.Key_0 <= key <= Qt.Key_9:
                        self._pin_setup_press(str(key - Qt.Key_0))
                        return True
                    elif hasattr(event, "text") and event.text().isdigit():
                        self._pin_setup_press(event.text())
                        return True
                    return False

                # ── Normal PIN login tab ──────────────────────────────────────
                if hasattr(self, "_stack") and self._stack.currentIndex() == 0:
                    if key in (Qt.Key_Return, Qt.Key_Enter):
                        self._login_pin()
                        return True
                    elif key in (Qt.Key_Backspace, Qt.Key_Delete):
                        self._pin_backspace()
                        return True
                    elif key == Qt.Key_Escape:
                        self._pin_clear()
                        return True
                    elif Qt.Key_0 <= key <= Qt.Key_9:
                        self._pin_press(str(key - Qt.Key_0))
                        return True
                    elif hasattr(event, "text") and event.text().isdigit():
                        self._pin_press(event.text())
                        return True
        except Exception:
            pass

        return super().eventFilter(obj, event)

    # -------------------------------------------------------------------------
    # Prevent dismiss without login
    # -------------------------------------------------------------------------
    def closeEvent(self, event):
        QApplication.instance().removeEventFilter(self)
        QApplication.quit()
        event.accept()

    def reject(self):
        pass

    # =========================================================================
    # UI construction
    # =========================================================================
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)

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

        # Header
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

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.addStretch()

        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(32, 32)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setFocusPolicy(Qt.NoFocus)
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255, 255, 255, 0.15);
                color: {WHITE};
                border: none;
                border-radius: 16px;
                font-size: 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: rgba(255, 255, 255, 0.25); }}
            QPushButton:pressed {{ background: rgba(255, 255, 255, 0.35); }}
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
        vl.addWidget(hdr)

        # Accent line
        accent_line = QFrame()
        accent_line.setFixedHeight(3)
        accent_line.setStyleSheet(f"""
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 {NAVY_3}, stop:0.3 {ACCENT}, stop:0.7 {ACCENT_H}, stop:1 {NAVY_3});
        """)
        vl.addWidget(accent_line)

        # Status bar
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

        # Tab row
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
            b.setFocusPolicy(Qt.NoFocus)
        self._pin_tab.clicked.connect(lambda: self._switch_mode(0))
        self._email_tab.clicked.connect(lambda: self._switch_mode(1))
        tl.addWidget(self._pin_tab)
        tl.addWidget(self._email_tab)
        vl.addWidget(tab_row)

        # Stack
        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background:{OFF_WHITE};")
        self._stack.addWidget(self._build_pin_page())
        self._stack.addWidget(self._build_email_page())
        vl.addWidget(self._stack, 1)

        # Error label
        err_w = QWidget()
        err_w.setStyleSheet(f"background:{OFF_WHITE};")
        el = QHBoxLayout(err_w)
        el.setContentsMargins(28, 0, 28, 4)
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

        # ── SQL Settings link row ─────────────────────────────────────────────
        sql_link_w = QWidget()
        sql_link_w.setStyleSheet(f"background:{OFF_WHITE};")
        sql_link_l = QHBoxLayout(sql_link_w)
        sql_link_l.setContentsMargins(28, 0, 28, 8)
        sql_link_l.setSpacing(6)

        sql_link_l.addStretch()
        gear_lbl = QLabel("⚙️")
        gear_lbl.setStyleSheet("background:transparent; font-size:11px;")
        self._sql_link_btn = QPushButton("Database & Site Configuration")
        self._sql_link_btn.setCursor(Qt.PointingHandCursor)
        self._sql_link_btn.setFocusPolicy(Qt.NoFocus)
        self._sql_link_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {MUTED};
                border: none;
                font-size: 11px;
                font-weight: 600;
                padding: 0;
                text-decoration: none;
            }}
            QPushButton:hover {{
                color: {ACCENT};
                text-decoration: underline;
            }}
        """)
        self._sql_link_btn.clicked.connect(self._open_sql_settings)
        sql_link_l.addWidget(gear_lbl)
        sql_link_l.addWidget(self._sql_link_btn)
        sql_link_l.addStretch()
        vl.addWidget(sql_link_w)

        # Footer
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
        self._switch_mode(0)

    def _close_app(self):
        self.close()

    # =========================================================================
    # SQL Settings link handler
    # =========================================================================
    def _open_sql_settings(self):
        try:
            from views.dialogs.sql_settings_dialog import SqlSettingsDialog
        except ImportError:
            try:
                from sql_settings_dialog import SqlSettingsDialog
            except ImportError:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self, "Not Found",
                    "sql_settings_dialog.py could not be located.\n"
                    "Place it in views/dialogs/ and restart."
                )
                return
        dlg = SqlSettingsDialog(self)
        dlg.exec()

    # =========================================================================
    # PIN page
    # =========================================================================
    def _build_pin_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet(f"background:{OFF_WHITE};")
        pl = QVBoxLayout(page)
        pl.setContentsMargins(28, 18, 28, 12)
        pl.setSpacing(14)
        pl.setAlignment(Qt.AlignTop)

        dot_card = QWidget()
        dot_card.setStyleSheet(f"""
            background:{WHITE}; border-radius:14px;
            border:1.5px solid {BORDER};
        """)
        dot_card.setFixedHeight(58)
        dcl = QHBoxLayout(dot_card)
        dcl.setContentsMargins(0, 0, 0, 0)
        self._pin_dots = PinDots(4)
        dcl.addStretch()
        dcl.addWidget(self._pin_dots)
        dcl.addStretch()
        pl.addWidget(dot_card)

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
    # Email / Password page
    # =========================================================================
    def _build_email_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet(f"background:{OFF_WHITE};")
        pl = QVBoxLayout(page)
        pl.setContentsMargins(28, 20, 28, 12)
        pl.setSpacing(6)
        pl.setAlignment(Qt.AlignTop)

        pl.addWidget(self._field_lbl("USERNAME / EMAIL"))
        pl.addSpacing(4)
        self.username_input = self._input("Enter your username or email")
        self.username_input.returnPressed.connect(
            lambda: self.password_input.setFocus()
        )
        pl.addWidget(self.username_input)
        pl.addSpacing(14)

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

        self._eye_btn = QPushButton("👁")
        self._eye_btn.setFixedSize(48, 48)
        self._eye_btn.setCursor(Qt.PointingHandCursor)
        self._eye_btn.setCheckable(True)
        self._eye_btn.setFocusPolicy(Qt.NoFocus)
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
            self.setFocus()
        else:
            self.username_input.setFocus()

    # =========================================================================
    # Password visibility toggle
    # =========================================================================
    def _toggle_password_visibility(self, checked: bool):
        self.password_input.setEchoMode(
            QLineEdit.Normal if checked else QLineEdit.Password
        )

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
        print(f"[login] PIN attempt — length={len(pin)}")
        try:
            from models.user import authenticate_by_pin
            user = authenticate_by_pin(pin)
            print(f"[login] authenticate_by_pin() returned: {user!r}")
        except Exception as e:
            import traceback
            print(f"[login] PIN auth EXCEPTION:\n{traceback.format_exc()}")
            self._show_error(f"Local DB error: {e}")
            return
        if not user:
            self._show_error("Incorrect PIN.  Please try again.")
            self._pin_clear()
            self._shake()
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

        self._worker = LoginWorker(u, p)
        self._worker.finished.connect(self._on_email_login_done)
        self._worker.start()

    def _on_email_login_done(self, result: dict):
        self._worker = None
        self._set_btn_normal(self._email_btn)

        if result.get("success"):
            user   = result["user"]
            source = result.get("source", "online")
            if source == "offline":
                self._show_info("⚠️  Offline mode — using local account.")
            self._validate_and_accept(user, source)
            return

        err    = result.get("error", "Login failed.")
        source = result.get("source", "")

        if "Wrong username or password" in err:
            display_err = "Incorrect username or password.  Please try again."
        elif source == "offline":
            display_err = "Could not connect to server and no local account matched."
        else:
            display_err = err

        self._show_error(display_err)
        self._shake()
        self.password_input.clear()
        self.password_input.setFocus()
        QTimer.singleShot(500, self._check_connectivity)

    # =========================================================================
    # Accept gate
    # =========================================================================
    def _validate_and_accept(self, user: dict, source: str):
        print("[login] 🔵 _validate_and_accept called")
        if not user.get("active", True):
            self._show_error("Your account has been disabled.  Contact your administrator.")
            self._shake()
            self._pin_clear()
            return

        if source in ("online", "offline") and not (user.get("pin") or "").strip():
            self._prompt_set_pin(user, source)
            return

        self._accept_user(user, source)

    # =========================================================================
    # PIN setup overlay
    # =========================================================================
    def _prompt_set_pin(self, user: dict, source: str):
        print("[login] 🟡 _prompt_set_pin called")
        self._pin_setup_user   = user
        self._pin_setup_source = source
        self._pin_setup_buf    = ""
        self._pin_setup_step   = "enter"
        self._pin_setup_first  = ""

        overlay = QWidget(self)
        overlay.setObjectName("pinSetupOverlay")
        overlay.setGeometry(0, 0, self.width(), self.height())
        overlay.setStyleSheet(f"QWidget#pinSetupOverlay {{ background: {WHITE}; border-radius: 20px; }}")

        root = QVBoxLayout(overlay)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        hdr = QWidget()
        hdr.setFixedHeight(120)
        hdr.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 {NAVY}, stop:0.6 {NAVY_2}, stop:1 {NAVY_3});
                border-top-left-radius: 20px;
                border-top-right-radius: 20px;
            }}
        """)
        hl = QVBoxLayout(hdr)
        hl.setContentsMargins(20, 16, 20, 16)
        hl.setSpacing(4)

        self._pin_setup_title = QLabel("Create Your PIN")
        self._pin_setup_title.setAlignment(Qt.AlignCenter)
        self._pin_setup_title.setStyleSheet(
            f"color:{WHITE}; font-size:20px; font-weight:800; background:transparent; letter-spacing:0.5px;"
        )
        hl.addWidget(self._pin_setup_title)

        self._pin_setup_sub = QLabel("Enter a 4-digit PIN for quick login next time")
        self._pin_setup_sub.setAlignment(Qt.AlignCenter)
        self._pin_setup_sub.setWordWrap(True)
        self._pin_setup_sub.setStyleSheet(f"color:{MID}; font-size:11px; background:transparent;")
        hl.addWidget(self._pin_setup_sub)
        root.addWidget(hdr)

        accent = QFrame()
        accent.setFixedHeight(3)
        accent.setStyleSheet(f"""
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 {NAVY_3}, stop:0.3 {ACCENT}, stop:0.7 {ACCENT_H}, stop:1 {NAVY_3});
        """)
        root.addWidget(accent)

        body = QWidget()
        body.setStyleSheet(f"background:{OFF_WHITE};")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(28, 20, 28, 16)
        bl.setSpacing(14)

        dot_card = QWidget()
        dot_card.setStyleSheet(f"background:{WHITE}; border-radius:14px; border:1.5px solid {BORDER};")
        dot_card.setFixedHeight(58)
        dcl = QHBoxLayout(dot_card)
        dcl.setContentsMargins(0, 0, 0, 0)
        self._pin_setup_dots = PinDots(4)
        dcl.addStretch()
        dcl.addWidget(self._pin_setup_dots)
        dcl.addStretch()
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

        grid_w = QWidget()
        grid_w.setStyleSheet("background:transparent;")
        grid = QGridLayout(grid_w)
        grid.setSpacing(10)
        grid.setContentsMargins(0, 0, 0, 0)

        keys = [
            ("1","d"),("2","d"),("3","d"),
            ("4","d"),("5","d"),("6","d"),
            ("7","d"),("8","d"),("9","d"),
            ("⌫","b"),("0","d"),("✓","e"),
        ]
        for i, (label, kind) in enumerate(keys):
            btn = QPushButton(label)
            btn.setFixedSize(108, 48)
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
                btn.clicked.connect(lambda _, d=label: self._pin_setup_press(d))
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
                btn.clicked.connect(self._pin_setup_backspace)
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
                btn.clicked.connect(self._pin_setup_confirm)
            grid.addWidget(btn, i // 3, i % 3)

        bl.addWidget(grid_w)
        root.addWidget(body, 1)

        footer = QWidget()
        footer.setFixedHeight(44)
        footer.setStyleSheet(f"""
            background:{CREAM}; border-bottom-left-radius:20px;
            border-bottom-right-radius:20px;
        """)
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(0, 0, 0, 0)
        skip_btn = QPushButton("Skip — I'll set my PIN later")
        skip_btn.setCursor(Qt.PointingHandCursor)
        skip_btn.setFocusPolicy(Qt.NoFocus)
        skip_btn.setStyleSheet(f"""
            QPushButton {{
                background:transparent; color:{MUTED};
                border:none; font-size:11px;
            }}
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
            self._pin_setup_err.setText("PIN must be at least 4 digits.")
            self._pin_setup_err.show()
            return

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
        print("[login] 🟢 _finish_pin_setup called")
        if save and pin:
            try:
                from models.user import set_user_pin
                from database.db import get_connection

                user_id = self._pin_setup_user.get("id")

                if not user_id:
                    email    = self._pin_setup_user.get("email") or ""
                    username = self._pin_setup_user.get("username") or ""
                    conn = get_connection()
                    cur  = conn.cursor()
                    cur.execute(
                        "SELECT TOP 1 id FROM users WHERE email=? OR frappe_user=? OR username=?",
                        (email, email, username)
                    )
                    row = cur.fetchone()
                    conn.close()
                    if row:
                        user_id = row[0]

                if user_id:
                    set_user_pin(user_id, pin)
                    self._pin_setup_user["pin"] = pin
                    print(f"[login] ✅ PIN saved for user id={user_id}")
                else:
                    print(f"[login] ⚠️  Could not find local user to save PIN")
            except Exception as e:
                print(f"[login] ⚠️  Could not save PIN: {e}")
        overlay.hide()
        overlay.deleteLater()
        self._accept_user(self._pin_setup_user, self._pin_setup_source)

    # =========================================================================
    # Ensure Default Customer
    # =========================================================================
    def _ensure_default_customer(self):
        """Create Default customer after successful login"""
        print("[login] 🔍 _ensure_default_customer CALLED!")
        try:
            from models.default_customer import create_default_customer
            print("[login] ✅ Successfully imported create_default_customer from models.default_customer")
            print("[login] Calling create_default_customer()...")
            result = create_default_customer()
            if result:
                print("[login] ✅ Default customer ready")
            else:
                print("[login] ⚠️ Could not create Default customer")
        except Exception as e:
            print(f"[login] ❌ Error ensuring default customer: {e}")
            import traceback
            traceback.print_exc()
        except Exception as e:
            print(f"[login] ❌ Error creating Default customer: {e}")
            import traceback
            traceback.print_exc()

    # =========================================================================
    # Accept
    # =========================================================================
    def _accept_user(self, user: dict, source: str):
        print("[login] 🔴 _accept_user CALLED!")
        print(f"[login] User: {user.get('username', user.get('email', 'unknown'))}")
        print(f"[login] Source: {source}")

        # Clean up filter before closing
        QApplication.instance().removeEventFilter(self)

        self.logged_in_user = user
        self.login_source   = source

        # Load credentials once — reuse the same k/s for both set_session
        # and the sync worker so we never do a second DB round-trip.
        k, s = "", ""
        try:
            from services.credentials import get_credentials, set_session
            k, s = get_credentials()
            if k and s:
                set_session(k, s)
                print(f"[login] ✅ Credentials set: {k[:8]}...")
            else:
                print("[login] ⚠️  No credentials found — sync will be skipped.")
        except Exception as e:
            print(f"[login] credential init: {e}")

        # Create Default customer after successful login
        print("[login] Calling _ensure_default_customer()...")
        self._ensure_default_customer()

        self.hide()

        # Always start background sync — it runs users + products + taxes.
        # Uses the credentials already fetched above (no second DB call).
        if k and s:
            self._bg_sync = BackgroundSyncWorker()
            self._bg_sync.start()
            print("[login] 🔄 Background sync started (users + products + taxes)")
        else:
            print("[login] ⚠️  Background sync skipped — no credentials")

        self.accept()

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
        try:
            self.username_input.setEnabled(True)
            self.password_input.setEnabled(True)
        except Exception:
            pass

    def _set_btn_loading(self, btn: QPushButton):
        btn.setEnabled(False)
        btn.setText("Signing in…")
        btn.setStyleSheet(f"""
            QPushButton {{
                background:{NAVY_2}; color:{MID}; font-size:15px; font-weight:bold;
                border-radius:12px; border:none;
            }}
        """)
        try:
            self.username_input.setEnabled(False)
            self.password_input.setEnabled(False)
        except Exception:
            pass

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
        self.error_label.setStyleSheet(f"""
            color:{WHITE}; background:{WARNING}; font-size:12px; font-weight:bold;
            border-radius:8px; padding:6px 14px;
        """)
        self.error_label.setText(f"  {msg}  ")
        self.error_label.show()
        QTimer.singleShot(3000, self.error_label.hide)

    # =========================================================================
    # keyPressEvent — safety net only; eventFilter handles PIN tab
    # =========================================================================
    def keyPressEvent(self, event):
        if self._stack.currentIndex() != 0:
            super().keyPressEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self.setFocus()
        self.activateWindow()
        self.raise_()

    # =========================================================================
    # Error flash
    # =========================================================================
    def _shake(self):
        card = self.findChild(QFrame, "card")
        if not card:
            return
        original = card.styleSheet()
        flash_style = "QFrame#card { background-color: #ffffff; border-radius: 20px; border: 2.5px solid #c0392b; }"
        card.setStyleSheet(flash_style)
        QTimer.singleShot(120, lambda: card.setStyleSheet(flash_style.replace("#c0392b", "#e74c3c")))
        QTimer.singleShot(240, lambda: card.setStyleSheet(flash_style))
        QTimer.singleShot(360, lambda: card.setStyleSheet(flash_style.replace("#c0392b", "#e74c3c")))
        QTimer.singleShot(480, lambda: card.setStyleSheet(original))