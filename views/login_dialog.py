# views/login_dialog.py
# =============================================================================
#  Refined navy-and-white login — supports admin & cashier roles.
#  After exec() == Accepted, read:
#    dialog.logged_in_user  →  {"id": int, "username": str, "role": "admin"|"cashier"}
# =============================================================================
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QWidget, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, QPropertyAnimation, QPoint, QTimer, QEasingCurve
from PySide6.QtGui import QFont, QColor

# ── Palette ───────────────────────────────────────────────────────────────────
NAVY      = "#0d1f3c"
NAVY_2    = "#162d52"
NAVY_3    = "#1e3d6e"
ACCENT    = "#1a5fb4"
WHITE     = "#ffffff"
OFF_WHITE = "#f5f8fc"
LIGHT     = "#e4eaf4"
BORDER    = "#c8d8ec"
MID       = "#8fa8c8"
MUTED     = "#5a7a9a"
DANGER    = "#b02020"
SUCCESS   = "#1a7a3c"


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("POS Login")
        self.setFixedSize(440, 480)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.logged_in_user = None
        self._build_ui()

    # ──────────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(16, 16, 16, 16)

        # ── Card shell ────────────────────────────────────────────────────────
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {WHITE};
                border-radius: 16px;
            }}
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setXOffset(0)
        shadow.setYOffset(8)
        shadow.setColor(QColor(13, 31, 60, 80))
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(0)
        card_layout.setContentsMargins(0, 0, 0, 0)

        # ── Header ────────────────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(130)
        header.setStyleSheet(f"""
            QWidget {{
                background-color: {NAVY};
                border-top-left-radius: 16px;
                border-top-right-radius: 16px;
            }}
        """)

        hdr_layout = QVBoxLayout(header)
        hdr_layout.setContentsMargins(0, 28, 0, 22)
        hdr_layout.setSpacing(6)

        dot_row = QHBoxLayout()
        dot = QLabel("●")
        dot.setAlignment(Qt.AlignCenter)
        dot.setStyleSheet(f"""
            color: {ACCENT};
            font-size: 10px;
            background: transparent;
            letter-spacing: 8px;
        """)
        dot_row.addStretch()
        dot_row.addWidget(dot)
        dot_row.addStretch()

        title = QLabel("Havano POS System")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"""
            font-size: 26px;
            font-weight: 700;
            color: {WHITE};
            background: transparent;
            letter-spacing: 2px;
        """)

        subtitle = QLabel("Sign in to your account")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet(f"""
            font-size: 12px;
            color: {MID};
            background: transparent;
            letter-spacing: 0.3px;
        """)

        hdr_layout.addLayout(dot_row)
        hdr_layout.addWidget(title)
        hdr_layout.addWidget(subtitle)

        card_layout.addWidget(header)

        # ── Divider line ──────────────────────────────────────────────────────
        divider = QFrame()
        divider.setFixedHeight(3)
        divider.setStyleSheet(f"""
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:0,
                stop:0 {NAVY},
                stop:0.4 {ACCENT},
                stop:1 {NAVY_3}
            );
        """)
        card_layout.addWidget(divider)

        # ── Form ──────────────────────────────────────────────────────────────
        form = QWidget()
        form.setStyleSheet(f"background: {WHITE}; border-radius: 0;")
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(44, 40, 44, 0)
        form_layout.setSpacing(0)

        # Username
        form_layout.addWidget(self._field_label("USERNAME"))
        form_layout.addSpacing(6)
        self.username_input = self._text_field("Enter your username")
        form_layout.addWidget(self.username_input)
        form_layout.addSpacing(20)

        # Password
        form_layout.addWidget(self._field_label("PASSWORD"))
        form_layout.addSpacing(6)
        self.password_input = self._text_field("Enter your password", password=True)
        self.password_input.returnPressed.connect(self._login)
        form_layout.addWidget(self.password_input)
        form_layout.addSpacing(16)

        # Error label
        self.error_label = QLabel("")
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.setFixedHeight(18)
        self.error_label.setStyleSheet(f"""
            color: {DANGER};
            font-size: 12px;
            background: transparent;
        """)
        self.error_label.hide()
        form_layout.addWidget(self.error_label)
        form_layout.addSpacing(12)

        # Sign-in button
        self.login_btn = QPushButton("Sign In")
        self.login_btn.setFixedHeight(50)
        self.login_btn.setCursor(Qt.PointingHandCursor)
        self._set_btn_normal()
        self.login_btn.clicked.connect(self._login)
        form_layout.addWidget(self.login_btn)

        card_layout.addWidget(form)

        # ── Footer ────────────────────────────────────────────────────────────
        footer = QWidget()
        footer.setFixedHeight(48)
        footer.setStyleSheet(f"""
            QWidget {{
                background-color: {OFF_WHITE};
                border-bottom-left-radius: 16px;
                border-bottom-right-radius: 16px;
            }}
        """)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)

        footer_lbl = QLabel("© Havano Point of Sale")
        footer_lbl.setAlignment(Qt.AlignCenter)
        footer_lbl.setStyleSheet(f"""
            font-size: 10px;
            color: {MID};
            background: transparent;
            letter-spacing: 0.8px;
        """)
        footer_layout.addWidget(footer_lbl)
        card_layout.addWidget(footer)

        root.addWidget(card)

    # ── Helpers ────────────────────────────────────────────────────────────────
    def _field_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"""
            color: {MUTED};
            font-size: 10px;
            font-weight: bold;
            background: transparent;
            letter-spacing: 1.2px;
        """)
        return lbl

    def _text_field(self, placeholder, password=False):
        inp = QLineEdit()
        inp.setPlaceholderText(placeholder)
        inp.setFixedHeight(46)
        if password:
            inp.setEchoMode(QLineEdit.Password)
        inp.setStyleSheet(f"""
            QLineEdit {{
                background-color: {OFF_WHITE};
                color: {NAVY};
                border: 1.5px solid {BORDER};
                border-radius: 10px;
                padding: 0 16px;
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border: 1.5px solid {ACCENT};
                background-color: {WHITE};
            }}
            QLineEdit:hover {{
                border: 1.5px solid {MID};
            }}
        """)
        return inp

    def _set_btn_normal(self):
        self.login_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {NAVY};
                color: {WHITE};
                font-size: 14px;
                font-weight: bold;
                border-radius: 10px;
                border: none;
                letter-spacing: 1.5px;
            }}
            QPushButton:hover {{
                background-color: {NAVY_3};
            }}
            QPushButton:pressed {{
                background-color: {ACCENT};
            }}
        """)

    def _set_btn_error(self):
        self.login_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DANGER};
                color: {WHITE};
                font-size: 14px;
                font-weight: bold;
                border-radius: 10px;
                border: none;
                letter-spacing: 1.5px;
            }}
        """)

    # ── Login logic ────────────────────────────────────────────────────────────
    def _login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()

        if not username or not password:
            self._show_error("Please fill in both fields.")
            return

        from models.user import authenticate
        user = authenticate(username, password)
        if user:
            self.logged_in_user = user
            self.accept()
        else:
            self._show_error("Wrong username or password.")
            self._set_btn_error()
            self._shake()
            self.password_input.clear()
            self.password_input.setFocus()
            QTimer.singleShot(1200, self._set_btn_normal)

    def _show_error(self, msg):
        self.error_label.setText(msg)
        self.error_label.show()

    def _shake(self):
        pos = self.pos()
        self.anim = QPropertyAnimation(self, b"pos")
        self.anim.setDuration(300)
        self.anim.setEasingCurve(QEasingCurve.OutElastic)
        self.anim.setKeyValueAt(0,   pos)
        self.anim.setKeyValueAt(0.2, pos + QPoint(-10, 0))
        self.anim.setKeyValueAt(0.4, pos + QPoint(10,  0))
        self.anim.setKeyValueAt(0.6, pos + QPoint(-8,  0))
        self.anim.setKeyValueAt(0.8, pos + QPoint(8,   0))
        self.anim.setKeyValueAt(1.0, pos)
        self.anim.start()