# =============================================================================
# views/pages/company_defaults_page.py
# =============================================================================
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTextEdit, QPushButton, QFrame, QSizePolicy, QScrollArea,
    QSpinBox, QMessageBox, QProgressBar, QDialog, QGroupBox, QFileDialog
)
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, Property as _Prop, QThread, Signal, QDir, QFileInfo
from PySide6.QtGui  import QPainter, QColor, QLinearGradient, QRadialGradient, QPixmap
import qtawesome as qta
import os
import shutil

NAVY      = "#0d1f3c"
NAVY_2    = "#162d52"
NAVY_3    = "#1e3d6e"
ACCENT    = "#1a5fb4"
ACCENT_H  = "#1c6dd0"
WHITE     = "#ffffff"
OFF_WHITE = "#f5f8fc"
LIGHT     = "#e4eaf4"
BORDER    = "#c8d8ec"
MID       = "#8fa8c8"
MUTED     = "#5a7a9a"
DARK_TEXT = "#0d1f3c"
SUCCESS   = "#1a7a3c"
SUCCESS_H = "#1f9447"
DANGER    = "#b02020"
ORANGE    = "#c05a00"

FIELD_H = 38
LBL_W   = 160
ROW_SP  = 12


# =============================================================================
# ToggleSwitch — pill toggle (same as payment_dialog)
# =============================================================================

class _TogglePill(QWidget):
    def __init__(self, size=20, parent=None):
        super().__init__(parent)
        self._size     = size
        self._checked  = False
        self._knob_pos = 0.0
        self.setFixedSize(int(2.2 * size), size)
        self.setCursor(Qt.PointingHandCursor)
        self._anim = QPropertyAnimation(self, b"knob_pos", self)
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.InOutCubic)

    def _get_knob_pos(self): return self._knob_pos
    def _set_knob_pos(self, v):
        self._knob_pos = v; self.update()
    knob_pos = _Prop(float, _get_knob_pos, _set_knob_pos)

    def isChecked(self): return self._checked
    def setChecked(self, value: bool, animated=False):
        self._checked = bool(value)
        target = 1.0 if self._checked else 0.0
        if animated:
            self._anim.stop()
            self._anim.setStartValue(self._knob_pos)
            self._anim.setEndValue(target)
            self._anim.start()
        else:
            self._knob_pos = target; self.update()
    def mousePressEvent(self, _ev):
        self.setChecked(not self._checked, animated=True)

    def paintEvent(self, _ev):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        s = self._size; w = self.width(); h = self.height(); r = h / 2
        t = self._knob_pos
        if t < 0.01:
            p.setBrush(QColor("#d7d7d7")); p.setPen(Qt.NoPen)
            p.drawRoundedRect(0, 0, w, h, r, r)
        else:
            grad = QLinearGradient(0, 0, w, 0)
            grad.setColorAt(0, QColor("#f19af3")); grad.setColorAt(1, QColor("#f099b5"))
            p.setBrush(QColor("#d7d7d7")); p.setPen(Qt.NoPen)
            p.drawRoundedRect(0, 0, w, h, r, r)
            if t > 0.99:
                p.setBrush(grad); p.drawRoundedRect(0, 0, w, h, r, r)
            else:
                p.setOpacity(t); p.setBrush(grad)
                p.drawRoundedRect(0, 0, w, h, r, r); p.setOpacity(1.0)
        knob_d = 0.8*s; knob_r = knob_d/2
        off_x = 0.1*s; on_x = 1.3*s
        knob_x = off_x + self._knob_pos*(on_x - off_x); knob_y = 0.1*s
        cx = knob_x+knob_r; cy = knob_y+knob_r
        shadow = QRadialGradient(cx, cy+4, knob_r*1.1)
        shadow.setColorAt(0, QColor(0,0,0,55)); shadow.setColorAt(0.6, QColor(0,0,0,30))
        shadow.setColorAt(1, QColor(0,0,0,0))
        p.setBrush(shadow); p.setPen(Qt.NoPen)
        p.drawEllipse(int(knob_x-knob_r*0.15), int(knob_y+knob_r*0.5),
                      int(knob_d*1.3), int(knob_d*0.9))
        kg = QLinearGradient(cx, knob_y, cx, knob_y+knob_d)
        kg.setColorAt(0, QColor("#dedede")); kg.setColorAt(1, QColor("#ffffff"))
        p.setBrush(kg); p.setPen(Qt.NoPen)
        p.drawEllipse(int(knob_x), int(knob_y), int(knob_d), int(knob_d))
        p.end()


class _ToggleSwitch(QWidget):
    """Pill toggle + label. API: isChecked() / setChecked(bool)."""
    def __init__(self, label: str, size: int = 20, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self._pill = _TogglePill(size=size, parent=self)
        layout.addWidget(self._pill)
        self._lbl = QLabel(label)
        self._lbl.setStyleSheet(
            f"font-size:12px;font-weight:600;color:{DARK_TEXT};background:transparent;")
        layout.addWidget(self._lbl)
        layout.addStretch()

    def isChecked(self) -> bool: return self._pill.isChecked()
    def setChecked(self, value: bool): self._pill.setChecked(value, animated=False)


# =============================================================================
# Test Connection Thread for Fiscalization
# =============================================================================

class TestConnectionThread(QThread):
    finished_signal = Signal(bool, str)  # success, message
    
    def __init__(self, base_url: str, api_key: str, api_secret: str, device_sn: str):
        super().__init__()
        self.base_url = base_url
        self.api_key = api_key
        self.api_secret = api_secret
        self.device_sn = device_sn
    
    def run(self):
        try:
            import requests
            
            # Step 1: Get CSRF Token
            token_url = f"{self.base_url}/api/method/havanozimracloud.api.token"
            token_resp = requests.post(token_url, timeout=30)
            
            if token_resp.status_code != 200:
                self.finished_signal.emit(False, f"Token failed: HTTP {token_resp.status_code}")
                return
            
            token_data = token_resp.json()
            csrf_token = token_data.get("message")
            if not csrf_token:
                self.finished_signal.emit(False, "Invalid token response")
                return
            
            # Step 2: Ping ZIMRA
            ping_url = f"{self.base_url}/api/method/havanozimracloud.api.pingzimra"
            headers = {
                "X-Frappe-CSRF-Token": csrf_token,
                "Authorization": f"token {self.api_key}:{self.api_secret}",
                "Content-Type": "application/x-www-form-urlencoded",
            }
            
            ping_resp = requests.post(ping_url, data={"device_sn": self.device_sn}, 
                                      headers=headers, timeout=30)
            
            if ping_resp.status_code != 200:
                self.finished_signal.emit(False, f"Ping failed: HTTP {ping_resp.status_code}")
                return
            
            ping_data = ping_resp.json()
            message = ping_data.get("message")
            
            if isinstance(message, str):
                self.finished_signal.emit(False, message)
            elif isinstance(message, dict):
                self.finished_signal.emit(
                    True, 
                    f"Connected!\nDevice: {message.get('device_sn', 'N/A')}\n"
                    f"Reporting Frequency: {message.get('reporting_frequency', 'N/A')} min"
                )
            else:
                self.finished_signal.emit(False, "Invalid ping response format")
                
        except Exception as e:
            self.finished_signal.emit(False, f"Connection error: {str(e)}")


# =============================================================================
# Helper widgets
# =============================================================================

def _sec(text):
    l = QLabel(text.upper())
    l.setStyleSheet(
        f"color:{MUTED}; font-size:10px; font-weight:bold;"
        f" background:transparent; letter-spacing:1.5px;"
    )
    l.setFixedHeight(20)
    return l


def _hr():
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setFixedHeight(1)
    f.setStyleSheet(f"background:{BORDER}; border:none;")
    return f


def _lbl(text, w=LBL_W):
    l = QLabel(text)
    l.setFixedWidth(w)
    l.setFixedHeight(FIELD_H)
    l.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    l.setStyleSheet(
        f"color:{MUTED}; font-size:12px; font-weight:bold; background:transparent;"
    )
    return l


def _inp(pwd=False, placeholder=""):
    i = QLineEdit()
    i.setFixedHeight(FIELD_H)
    if pwd:
        i.setEchoMode(QLineEdit.Password)
    if placeholder:
        i.setPlaceholderText(placeholder)
    i.setStyleSheet(f"""
        QLineEdit {{
            background:{WHITE}; color:{DARK_TEXT};
            border:1px solid {BORDER}; border-radius:6px;
            padding:0 12px; font-size:13px;
        }}
        QLineEdit:focus {{ border:2px solid {ACCENT}; }}
        QLineEdit:hover {{ border:1px solid {MID}; }}
    """)
    return i


def _ro(text="—"):
    l = QLabel(text)
    l.setFixedHeight(FIELD_H)
    l.setStyleSheet(
        f"color:{DARK_TEXT}; font-size:13px;"
        f" background:{LIGHT}; border:1px solid {BORDER};"
        f" border-radius:6px; padding:0 12px;"
    )
    return l


def _spinbox():
    s = QSpinBox()
    s.setFixedHeight(FIELD_H)
    s.setMinimum(0)
    s.setMaximum(9999999)
    s.setValue(0)
    s.setStyleSheet(f"""
        QSpinBox {{
            background:{WHITE}; color:{DARK_TEXT};
            border:1px solid {BORDER}; border-radius:6px;
            padding:0 12px; font-size:13px;
        }}
        QSpinBox:focus {{ border:2px solid {ACCENT}; }}
        QSpinBox::up-button, QSpinBox::down-button {{
            width:24px; border:none;
            background:{LIGHT}; border-radius:3px;
        }}
        QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
            background:{BORDER};
        }}
    """)
    return s


def _field_row(label_text, widget, lw=LBL_W):
    row = QHBoxLayout()
    row.setSpacing(16)
    row.setContentsMargins(0, 0, 0, 0)
    row.addWidget(_lbl(label_text, lw))
    row.addWidget(widget, 1)
    return row


def _section_header(layout, title, top_margin=16):
    layout.addSpacing(top_margin)
    layout.addWidget(_sec(title))
    layout.addSpacing(6)
    layout.addWidget(_hr())
    layout.addSpacing(10)


def _card(bg=WHITE):
    w = QWidget()
    w.setObjectName("card")
    w.setStyleSheet(
        f"QWidget#card {{ background:{bg}; border:1px solid {BORDER};"
        f" border-radius:8px; }}"
    )
    return w


# =============================================================================
class CompanyDefaultsPage(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"QWidget {{ background:{OFF_WHITE}; }}")
        self._inputs    = {}
        self._ro_labels = {}
        self._test_thread = None
        self._fiscal_settings = {}  # Store tested fiscal settings
        self._build()
        self._load()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setSpacing(0)
        outer.setContentsMargins(0, 0, 0, 0)

        # ── Header bar ────────────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setFixedHeight(64)
        hdr.setStyleSheet(f"background:{NAVY};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(32, 0, 32, 0)
        hl.setSpacing(16)

        title = QLabel("Company Defaults")
        title.setStyleSheet(
            f"font-size:18px; font-weight:bold; color:{WHITE}; background:transparent;"
        )

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(
            f"font-size:13px; background:transparent; color:#2ecc71;"
        )

        # ── FISCALIZATION BUTTON ──────────────────────────────────────────────
        fiscal_btn = QPushButton("Fiscalization")
        fiscal_btn.setIcon(qta.icon("fa5s.cog", color="white"))
        fiscal_btn.setFixedHeight(38)
        fiscal_btn.setCursor(Qt.PointingHandCursor)
        fiscal_btn.setStyleSheet(f"""
            QPushButton {{
                background:{NAVY_2}; color:{WHITE}; border:1px solid {ACCENT};
                border-radius:6px; font-size:12px; font-weight:bold; padding:0 16px;
            }}
            QPushButton:hover   {{ background:{NAVY_3}; border:1px solid {ACCENT_H}; }}
            QPushButton:pressed {{ background:{NAVY}; }}
        """)
        fiscal_btn.clicked.connect(self._open_fiscalization_dialog)

        # ── EXTERNAL SITE SETTINGS BUTTON ─────────────────────────────────────
        external_btn = QPushButton("External Site")
        external_btn.setIcon(qta.icon("fa5s.globe", color="white"))
        external_btn.setFixedHeight(38)
        external_btn.setCursor(Qt.PointingHandCursor)
        external_btn.setStyleSheet(f"""
            QPushButton {{
                background:{NAVY_2}; color:{WHITE}; border:1px solid {ORANGE};
                border-radius:6px; font-size:12px; font-weight:bold; padding:0 16px;
            }}
            QPushButton:hover   {{ background:{NAVY_3}; border:1px solid {ORANGE}; }}
            QPushButton:pressed {{ background:{NAVY}; }}
        """)
        external_btn.clicked.connect(self._open_external_site_settings)

        # ── PHARMACY MASTERS BUTTON (visible only in pharmacy mode) ──────────
        pharmacy_btn = QPushButton("Pharmacy Masters")
        pharmacy_btn.setIcon(qta.icon("fa5s.prescription-bottle-alt", color="white"))
        pharmacy_btn.setFixedHeight(38)
        pharmacy_btn.setCursor(Qt.PointingHandCursor)
        pharmacy_btn.setStyleSheet(f"""
            QPushButton {{
                background:{NAVY_2}; color:{WHITE}; border:1px solid #7c3aed;
                border-radius:6px; font-size:12px; font-weight:bold; padding:0 16px;
            }}
            QPushButton:hover   {{ background:{NAVY_3}; border:1px solid #9461ff; }}
            QPushButton:pressed {{ background:{NAVY}; }}
        """)
        pharmacy_btn.clicked.connect(self._open_pharmacy_masters_dialog)
        try:
            from settings.pharmacy_settings import get_pharmacy_mode
            _pharmacy_on = bool(get_pharmacy_mode())
        except Exception as _e:
            print(f"[CompanyDefaults] get_pharmacy_mode failed: {_e}")
            _pharmacy_on = False
        pharmacy_btn.setVisible(_pharmacy_on)

        # ── SAVE CHANGES BUTTON ───────────────────────────────────────────────
        save_btn = QPushButton("  Save Changes  ")
        save_btn.setFixedHeight(38)
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background:{SUCCESS}; color:{WHITE}; border:none;
                border-radius:6px; font-size:13px; font-weight:bold; padding:0 24px;
            }}
            QPushButton:hover   {{ background:{SUCCESS_H}; }}
            QPushButton:pressed {{ background:{NAVY_3}; }}
        """)
        save_btn.clicked.connect(self._save)

        hl.addWidget(title)
        hl.addStretch()
        hl.addWidget(self._status_lbl)
        hl.addWidget(fiscal_btn)
        hl.addWidget(external_btn)  # External site button after fiscalization
        hl.addWidget(pharmacy_btn)  # Pharmacy masters (hidden unless pharmacy mode)
        hl.addWidget(save_btn)
        outer.addWidget(hdr)

        bar = QFrame()
        bar.setFixedHeight(3)
        bar.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {NAVY}, stop:0.5 {ACCENT}, stop:1 {NAVY_3});
        """)
        outer.addWidget(bar)

        # ── Scroll area ───────────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet(f"""
            QScrollArea {{ border:none; background:{OFF_WHITE}; }}
            QScrollBar:vertical   {{ background:{LIGHT}; width:8px; border-radius:4px; }}
            QScrollBar::handle:vertical  {{ background:#b0c4de; border-radius:4px; min-height:32px; }}
            QScrollBar:horizontal {{ background:{LIGHT}; height:8px; border-radius:4px; }}
            QScrollBar::handle:horizontal {{ background:#b0c4de; border-radius:4px; min-width:32px; }}
        """)

        content = QWidget()
        content.setStyleSheet(f"background:{OFF_WHITE};")
        root = QVBoxLayout(content)
        root.setSpacing(20)
        root.setContentsMargins(32, 28, 32, 40)

        # ═════════════════════════════════════════════════════════════════════
        # ROW 1: Receipt Details | Invoice Numbering | Payment Settings
        # ═════════════════════════════════════════════════════════════════════
        row1 = QHBoxLayout()
        row1.setSpacing(16)

        # Receipt Details
        rc = _card()
        rcl = QVBoxLayout(rc)
        rcl.setContentsMargins(28, 20, 28, 24)
        rcl.setSpacing(ROW_SP)
        _section_header(rcl, "Receipt Details", top_margin=0)
        for label, key in [
            ("Company Name",   "company_name"),
            ("Address Line 1", "address_1"),
            ("Address Line 2", "address_2"),
            ("Email",          "email"),
            ("Phone",          "phone"),
            ("VAT Number",     "vat_number"),
            ("TIN Number",     "tin_number"),
        ]:
            inp = _inp()
            self._inputs[key] = inp
            rcl.addLayout(_field_row(label, inp))
        
        # --- Company Logo Selection ---
        _section_header(rcl, "Company Logo")
        logo_row = QHBoxLayout()
        logo_row.setSpacing(16)
        
        # Logo Preview
        self._logo_preview = QLabel("No Logo")
        self._logo_preview.setFixedSize(100, 100)
        self._logo_preview.setAlignment(Qt.AlignCenter)
        self._logo_preview.setStyleSheet(f"""
            QLabel {{
                background:{LIGHT}; border:1px solid {BORDER};
                border-radius:6px; color:{MUTED}; font-size:11px;
                font-weight:bold;
            }}
        """)
        
        logo_btn_lay = QVBoxLayout()
        logo_btn_lay.setSpacing(8)
        
        self._select_logo_btn = QPushButton(" Select Logo ")
        self._select_logo_btn.setFixedHeight(34)
        self._select_logo_btn.setCursor(Qt.PointingHandCursor)
        self._select_logo_btn.setStyleSheet(f"""
            QPushButton {{
                background:{NAVY_2}; color:{WHITE}; border:none;
                border-radius:4px; font-size:11px; font-weight:bold;
            }}
            QPushButton:hover {{ background:{NAVY_3}; }}
        """)
        self._select_logo_btn.clicked.connect(self._select_logo)
        
        self._clear_logo_btn = QPushButton(" Clear ")
        self._clear_logo_btn.setFixedHeight(34)
        self._clear_logo_btn.setCursor(Qt.PointingHandCursor)
        self._clear_logo_btn.setStyleSheet(f"""
            QPushButton {{
                background:transparent; color:{DANGER}; border:1px solid {DANGER};
                border-radius:4px; font-size:11px; font-weight:bold;
            }}
            QPushButton:hover {{ background:{DANGER}; color:{WHITE}; }}
        """)
        self._clear_logo_btn.clicked.connect(self._clear_logo)
        
        logo_btn_lay.addWidget(self._select_logo_btn)
        logo_btn_lay.addWidget(self._clear_logo_btn)
        logo_btn_lay.addStretch()
        
        logo_row.addWidget(_lbl("Receipt Logo", LBL_W))
        logo_row.addWidget(self._logo_preview)
        logo_row.addLayout(logo_btn_lay)
        logo_row.addStretch()
        
        rcl.addLayout(logo_row)
        rcl.addStretch()

        # Invoice Numbering
        ic = _card()
        icl = QVBoxLayout(ic)
        icl.setContentsMargins(28, 20, 28, 24)
        icl.setSpacing(ROW_SP)
        _section_header(icl, "Invoice Numbering", top_margin=0)

        self._prefix_inp = _inp(placeholder="e.g. ABC  (max 6 chars)")
        self._prefix_inp.setMaxLength(6)
        self._prefix_inp.textChanged.connect(self._update_preview)
        icl.addLayout(_field_row("Prefix", self._prefix_inp))

        self._start_num = _spinbox()
        self._start_num.valueChanged.connect(self._update_preview)
        icl.addLayout(_field_row("Starting from", self._start_num))

        prev_row = QHBoxLayout()
        prev_row.setSpacing(16)
        prev_row.setContentsMargins(0, 4, 0, 0)
        prev_row.addWidget(_lbl("Preview"))
        self._preview_lbl = QLabel("000001")
        self._preview_lbl.setFixedHeight(FIELD_H)
        self._preview_lbl.setStyleSheet(
            f"color:{ACCENT}; font-size:14px; font-weight:bold;"
            f" background:{LIGHT}; border:1px solid {BORDER};"
            f" border-radius:6px; padding:0 14px;"
        )
        prev_row.addWidget(self._preview_lbl)
        prev_row.addStretch()
        icl.addLayout(prev_row)
        icl.addStretch()

        # Payment Settings
        pc = _card()
        pcl = QVBoxLayout(pc)
        pcl.setContentsMargins(28, 20, 28, 24)
        pcl.setSpacing(ROW_SP)
        _section_header(pcl, "Payment Settings", top_margin=0)

        self._allow_credit_chk = _ToggleSwitch("Allow Credit Sales  (On Account)", size=20)

        hint = QLabel(
            "When enabled, cashiers can choose <b>On Account</b> as a payment "
            "method. The system records the sale but skips the payment entry "
            "for the on-account portion — letting the customer pay later."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(
            f"color:{MUTED}; font-size:11px; background:{LIGHT};"
            f" border:1px solid {BORDER}; border-radius:6px; padding:10px 12px;"
        )

        pcl.addWidget(self._allow_credit_chk)
        pcl.addSpacing(8)
        pcl.addWidget(hint)

        # Pharmacy Mode — terminal-local, persisted to app_data/pharmacy_settings.json
        self._pharmacy_mode_chk = _ToggleSwitch(
            "Pharmacy Mode  (enables dosage + batch prompts)", size=20)
        pharm_hint = QLabel(
            "When enabled on this terminal, pharmacy-flagged products prompt "
            "for dosage and batch at add-to-cart, and cashiers are blocked "
            "from modifying pharmacy lines on existing quotes. Saved per "
            "terminal (not synced)."
        )
        pharm_hint.setWordWrap(True)
        pharm_hint.setStyleSheet(
            f"color:{MUTED}; font-size:11px; background:{LIGHT};"
            f" border:1px solid {BORDER}; border-radius:6px; padding:10px 12px;"
        )
        pcl.addSpacing(12)
        pcl.addWidget(self._pharmacy_mode_chk)
        pcl.addSpacing(8)
        pcl.addWidget(pharm_hint)

        pcl.addStretch()

        row1.addWidget(rc,  3)
        row1.addWidget(ic,  2)
        row1.addWidget(pc,  2)
        root.addLayout(row1)

        # ═════════════════════════════════════════════════════════════════════
        # ROW 2: Footer Text | ZIMRA Settings | Login Defaults
        # ═════════════════════════════════════════════════════════════════════
        row2 = QHBoxLayout()
        row2.setSpacing(16)

        # Footer Text
        fc = _card()
        fcl = QVBoxLayout(fc)
        fcl.setContentsMargins(28, 20, 28, 24)
        fcl.setSpacing(ROW_SP)

        # Receipt Header — single line printed bold/centered below company block.
        # Blank falls back to "*** SALES RECEIPT ***" in services/printing_service.py.
        _section_header(fcl, "Receipt Header", top_margin=0)
        self._receipt_header = _inp()
        self._receipt_header.setPlaceholderText("*** SALES RECEIPT ***")
        fcl.addLayout(_field_row("Header", self._receipt_header, lw=70))

        _section_header(fcl, "Footer Text")
        self._footer = QTextEdit()
        self._footer.setMinimumHeight(160)
        self._footer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._footer.setStyleSheet(f"""
            QTextEdit {{
                background:{WHITE}; color:{DARK_TEXT};
                border:1px solid {BORDER}; border-radius:6px;
                padding:10px 12px; font-size:13px;
            }}
            QTextEdit:focus {{ border:2px solid {ACCENT}; }}
        """)
        fcl.addWidget(self._footer, 1)

        # ZIMRA Settings
        zc = _card(OFF_WHITE)
        zcl = QVBoxLayout(zc)
        zcl.setContentsMargins(28, 20, 28, 24)
        zcl.setSpacing(ROW_SP)
        _section_header(zcl, "ZIMRA Settings", top_margin=0)
        for label, key, pwd in [
            ("Serial No", "zimra_serial_no", False),
            ("Device ID", "zimra_device_id", False),
            ("API URL",   "zimra_api_url",   False),
            ("API Key",   "zimra_api_key",   True),
        ]:
            inp = _inp(pwd=pwd)
            self._inputs[key] = inp
            zcl.addLayout(_field_row(label, inp, lw=90))
        zcl.addStretch()

        # Login Defaults
        lc = _card()
        lcl = QVBoxLayout(lc)
        lcl.setContentsMargins(28, 20, 28, 24)
        lcl.setSpacing(ROW_SP)
        _section_header(lcl, "Login Defaults", top_margin=0)
        for label, key in [
            ("Company",     "server_company"),
            ("Warehouse",   "server_warehouse"),
            ("Cost Centre", "server_cost_center"),
            ("Username",    "server_username"),
            ("First Name",  "server_first_name"),
            ("Last Name",   "server_last_name"),
            ("Email",       "server_email"),
            ("Mobile",      "server_mobile"),
            ("Full Name",   "server_full_name"),
            ("Role",        "server_role"),
        ]:
            ro = _ro()
            self._ro_labels[key] = ro
            lcl.addLayout(_field_row(label, ro, lw=110))
        lcl.addStretch()

        row2.addWidget(fc,  2)
        row2.addWidget(zc,  2)
        row2.addWidget(lc,  3)
        root.addLayout(row2)

        # ═════════════════════════════════════════════════════════════════════
        # ROW 3: Terms & Conditions (full width)
        # ═════════════════════════════════════════════════════════════════════
        tc = _card()
        tcl = QVBoxLayout(tc)
        tcl.setContentsMargins(28, 20, 28, 24)
        tcl.setSpacing(ROW_SP)
        _section_header(tcl, "Terms & Conditions  (printed on Sales Orders)", top_margin=0)
        self._terms = QTextEdit()
        self._terms.setMinimumHeight(160)
        self._terms.setPlaceholderText(
            "Enter your sales order terms & conditions here.\n"
            "Each line will be printed as a separate paragraph."
        )
        self._terms.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._terms.setStyleSheet(f"""
            QTextEdit {{
                background:{WHITE}; color:{DARK_TEXT};
                border:1px solid {BORDER}; border-radius:6px;
                padding:10px 12px; font-size:13px;
            }}
            QTextEdit:focus {{ border:2px solid {ACCENT}; }}
        """)
        tcl.addWidget(self._terms, 1)
        root.addWidget(tc)

        root.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

    # ── Live invoice preview ──────────────────────────────────────────────────

    def _update_preview(self):
        prefix = self._prefix_inp.text().strip().upper()
        num    = self._start_num.value()
        text   = f"{prefix}{num:06d}" if prefix else f"{num:06d}"
        self._preview_lbl.setText(text)

    # ── External Site Settings ────────────────────────────────────────────────

    def _open_external_site_settings(self):
        """Open the external quotation site settings dialog"""
        try:
            from views.dialogs.external_quotation_settings_dialog import ExternalQuotationSettingsDialog
            dialog = ExternalQuotationSettingsDialog(self)
            dialog.exec()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open external site settings:\n{e}")

    # ── Pharmacy Masters (Doctors / Dosages) ──────────────────────────────────

    def _open_pharmacy_masters_dialog(self):
        """Open the read-only pharmacy masters viewer (Doctors + Dosages)."""
        try:
            from views.dialogs.pharmacy_masters_dialog import PharmacyMastersDialog
            PharmacyMastersDialog(self).exec()
        except Exception as e:
            QMessageBox.warning(self, "Error",
                                f"Could not open pharmacy masters:\n{e}")

    # ── Fiscalization Dialog ─────────────────────────────────────────────────

    def _open_fiscalization_dialog(self):
        """Open the fiscalization settings dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Fiscalization Settings")
        dialog.setMinimumSize(500, 580)
        dialog.setModal(True)
        dialog.setStyleSheet(f"QDialog {{ background:{OFF_WHITE}; }}")
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)
        layout.setContentsMargins(25, 20, 25, 20)
        
        # Title
        title = QLabel("ZIMRA Fiscalization Configuration")
        title_font = title.font()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Enable checkbox
        self._fiscal_enable = _ToggleSwitch("Enable Fiscalization", size=20)
        layout.addWidget(self._fiscal_enable)
        layout.addSpacing(10)
        
        # Connection settings group
        conn_group = QGroupBox("Connection Settings")
        conn_layout = QVBoxLayout(conn_group)
        conn_layout.setSpacing(12)
        
        # Base URL
        self._fiscal_base_url = _inp(placeholder="https://your-zimra-server.com")
        conn_layout.addLayout(_field_row("Base URL:", self._fiscal_base_url, lw=120))
        
        # API Key
        self._fiscal_api_key = _inp(pwd=True)
        conn_layout.addLayout(_field_row("API Key:", self._fiscal_api_key, lw=120))
        
        # API Secret
        self._fiscal_api_secret = _inp(pwd=True)
        conn_layout.addLayout(_field_row("API Secret:", self._fiscal_api_secret, lw=120))
        
        # Device SN
        self._fiscal_device_sn = _inp(placeholder="ZIMRA device serial number")
        conn_layout.addLayout(_field_row("Device SN:", self._fiscal_device_sn, lw=120))
        
        # Ping Interval
        self._fiscal_ping_interval = _spinbox()
        self._fiscal_ping_interval.setRange(1, 60)
        self._fiscal_ping_interval.setValue(5)
        conn_layout.addLayout(_field_row("Ping Interval (min):", self._fiscal_ping_interval, lw=120))
        
        layout.addWidget(conn_group)
        
        # Status display
        status_group = QGroupBox("Device Status")
        status_layout = QVBoxLayout(status_group)
        self._fiscal_status_label = QLabel("Not tested")
        self._fiscal_status_label.setWordWrap(True)
        self._fiscal_status_label.setStyleSheet(f"color:{MUTED}; padding:8px;")
        status_layout.addWidget(self._fiscal_status_label)
        layout.addWidget(status_group)
        
        # Progress bar
        self._fiscal_progress = QProgressBar()
        self._fiscal_progress.setVisible(False)
        self._fiscal_progress.setRange(0, 0)
        layout.addWidget(self._fiscal_progress)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        test_btn = QPushButton("Test Connection")
        test_btn.setIcon(qta.icon("fa5s.plug", color="white"))
        test_btn.setFixedHeight(40)
        test_btn.setCursor(Qt.PointingHandCursor)
        test_btn.setStyleSheet(f"""
            QPushButton {{
                background:{NAVY_2}; color:{WHITE}; border:none;
                border-radius:6px; font-size:12px; font-weight:bold; padding:0 20px;
            }}
            QPushButton:hover {{ background:{NAVY_3}; }}
        """)
        test_btn.clicked.connect(self._test_fiscal_connection)
        
        save_fiscal_btn = QPushButton("Save Fiscal Settings")
        save_fiscal_btn.setIcon(qta.icon("fa5s.save", color="white"))
        save_fiscal_btn.setFixedHeight(40)
        save_fiscal_btn.setCursor(Qt.PointingHandCursor)
        save_fiscal_btn.setStyleSheet(f"""
            QPushButton {{
                background:{SUCCESS}; color:{WHITE}; border:none;
                border-radius:6px; font-size:12px; font-weight:bold; padding:0 20px;
            }}
            QPushButton:hover {{ background:{SUCCESS_H}; }}
        """)
        save_fiscal_btn.clicked.connect(lambda: self._save_fiscal_settings(dialog))
        
        close_btn = QPushButton("Cancel")
        close_btn.setFixedHeight(40)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background:{LIGHT}; color:{DARK_TEXT}; border:none;
                border-radius:6px; font-size:12px; padding:0 20px;
            }}
            QPushButton:hover {{ background:{BORDER}; }}
        """)
        close_btn.clicked.connect(dialog.reject)
        
        btn_layout.addWidget(test_btn)
        btn_layout.addWidget(save_fiscal_btn)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
        
        # Load existing settings
        self._load_fiscal_settings_into_dialog()
        
        dialog.exec()
    
    def _load_fiscal_settings_into_dialog(self):
        """Load existing fiscal settings into the dialog fields"""
        try:
            from models.fiscal_settings import FiscalSettingsRepository
            repo = FiscalSettingsRepository()
            settings = repo.get_settings()
            
            if settings:
                self._fiscal_enable.setChecked(settings.enabled)
                self._fiscal_base_url.setText(settings.base_url)
                self._fiscal_api_key.setText(settings.api_key)
                self._fiscal_api_secret.setText(settings.api_secret)
                self._fiscal_device_sn.setText(settings.device_sn)
                self._fiscal_ping_interval.setValue(settings.ping_interval_minutes)
                
                if settings.device_status == "online":
                    self._fiscal_status_label.setText(
                        f"Device Online\nLast ping: {settings.last_ping_time or 'Never'}"
                    )
                    self._fiscal_status_label.setStyleSheet(f"color:{SUCCESS}; padding:8px;")
                elif settings.device_status == "offline":
                    self._fiscal_status_label.setText("Device Offline - Last connection failed")
                    self._fiscal_status_label.setStyleSheet(f"color:{ORANGE}; padding:8px;")
                elif settings.device_status == "error":
                    self._fiscal_status_label.setText("Connection Error")
                    self._fiscal_status_label.setStyleSheet(f"color:{DANGER}; padding:8px;")
                else:
                    self._fiscal_status_label.setText("Status unknown - Test connection to verify")
                    self._fiscal_status_label.setStyleSheet(f"color:{MUTED}; padding:8px;")
        except Exception as e:
            print(f"[Fiscal] Error loading settings: {e}")
    
    def _test_fiscal_connection(self):
        """Test connection to ZIMRA"""
        base_url = self._fiscal_base_url.text().strip()
        api_key = self._fiscal_api_key.text().strip()
        api_secret = self._fiscal_api_secret.text().strip()
        device_sn = self._fiscal_device_sn.text().strip()
        
        # Validate
        if not base_url:
            QMessageBox.warning(self, "Missing Field", "Please enter the Base URL")
            return
        if not api_key:
            QMessageBox.warning(self, "Missing Field", "Please enter the API Key")
            return
        if not api_secret:
            QMessageBox.warning(self, "Missing Field", "Please enter the API Secret")
            return
        if not device_sn:
            QMessageBox.warning(self, "Missing Field", "Please enter the Device SN")
            return
        
        # Disable buttons during test
        self._fiscal_progress.setVisible(True)
        self._fiscal_status_label.setText("Testing connection...")
        self._fiscal_status_label.setStyleSheet(f"color:{ACCENT}; padding:8px;")
        
        # Start test thread
        self._test_thread = TestConnectionThread(base_url, api_key, api_secret, device_sn)
        self._test_thread.finished_signal.connect(self._on_test_finished)
        self._test_thread.start()
    
    def _on_test_finished(self, success: bool, message: str):
        """Handle test connection result and update device status"""
        self._fiscal_progress.setVisible(False)
        
        if success:
            self._fiscal_status_label.setText(f"{message}")
            self._fiscal_status_label.setStyleSheet(f"color:{SUCCESS}; padding:8px;")
            
            # Update device status to online in the database
            try:
                from models.fiscal_settings import FiscalSettingsRepository
                repo = FiscalSettingsRepository()
                repo.update_device_status(status="online", reporting_frequency=5)
                print("[Fiscal] Device status updated to online")
            except Exception as e:
                print(f"[Fiscal] Could not update device status: {e}")
            
            QMessageBox.information(
                self, "Connection Successful", 
                f"Successfully connected to ZIMRA!\n\n{message}\n\nYou can now save these settings."
            )
        else:
            self._fiscal_status_label.setText(f"{message}")
            self._fiscal_status_label.setStyleSheet(f"color:{DANGER}; padding:8px;")
            
            # Update device status to offline/error
            try:
                from models.fiscal_settings import FiscalSettingsRepository
                repo = FiscalSettingsRepository()
                repo.update_device_status(status="offline")
                print("[Fiscal] Device status updated to offline")
            except Exception as e:
                pass
            
            QMessageBox.warning(
                self, "Connection Failed", 
                f"Could not connect to ZIMRA:\n\n{message}\n\nPlease check your settings and try again."
            )
    
    def _save_fiscal_settings(self, dialog: QDialog):
        """Save fiscal settings to database"""
        # Check if test was performed and successful
        is_online = "Connected" in self._fiscal_status_label.text() and SUCCESS in self._fiscal_status_label.styleSheet()
        
        if not is_online:
            reply = QMessageBox.question(
                self, "Confirm Save",
                "You haven't successfully tested the connection yet.\n\n"
                "Do you still want to save these settings?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
        
        try:
            from models.fiscal_settings import FiscalSettings, FiscalSettingsRepository
            from services.fiscal_device_monitor import get_device_monitor_service
            
            # Determine device status based on test result
            device_status = "online" if is_online else "unknown"
            
            settings = FiscalSettings(
                enabled=self._fiscal_enable.isChecked(),
                base_url=self._fiscal_base_url.text().strip(),
                api_key=self._fiscal_api_key.text().strip(),
                api_secret=self._fiscal_api_secret.text().strip(),
                device_sn=self._fiscal_device_sn.text().strip(),
                ping_interval_minutes=self._fiscal_ping_interval.value(),
                device_status=device_status,
            )
            
            repo = FiscalSettingsRepository()
            repo.save_settings(settings)
            
            # Restart device monitor if enabled
            if settings.enabled:
                monitor = get_device_monitor_service()
                monitor.restart_monitoring()
            
            QMessageBox.information(self, "Saved", "Fiscalization settings saved successfully!")
            dialog.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save settings: {e}")

    # ── Load ─────────────────────────────────────────────────────────────────

    def _load(self):
        try:
            from models.company_defaults import get_defaults
            data = get_defaults()
        except Exception as e:
            print(f"[CompanyDefaultsPage] load error: {e}")
            data = {}

        for key, inp in self._inputs.items():
            val = data.get(key, "")
            if key == "company_name" and not val:
                val = data.get("server_company", "")
            inp.setText(val)

        self._receipt_header.setText(data.get("receipt_header", ""))
        self._footer.setPlainText(data.get("footer_text", ""))
        self._terms.setPlainText(data.get("terms_and_conditions", ""))

        for key, lbl in self._ro_labels.items():
            val = data.get(key, "")
            lbl.setText(val if val else "—")

        self._prefix_inp.setText(data.get("invoice_prefix", ""))
        try:
            self._start_num.setValue(int(data.get("invoice_start_number", 0) or 0))
        except (ValueError, TypeError):
            self._start_num.setValue(0)

        self._allow_credit_chk.setChecked(
            str(data.get("allow_credit_sales", "0")).strip() == "1"
        )

        # Pharmacy mode — terminal-local (not in company_defaults DB record)
        try:
            from settings.pharmacy_settings import get_pharmacy_mode
            self._pharmacy_mode_chk.setChecked(bool(get_pharmacy_mode()))
        except Exception as e:
            print(f"[CompanyDefaultsPage] pharmacy_mode load skipped: {e}")

        # Current logo path
        self._current_logo_name = data.get("logo_path", "")
        self._update_logo_preview(self._current_logo_name)

        self._update_preview()

    # --- Logo Selection Helpers ---

    def _select_logo(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Company Logo", "", "Images (*.png *.jpg *.jpeg *.bmp *.ico)"
        )
        if not file_path:
            return

        try:
            # Ensure logos directory exists
            from database.db import get_app_data_dir
            logos_dir = os.path.join(get_app_data_dir(), "logos")
            if not os.path.exists(logos_dir):
                os.makedirs(logos_dir)

            # Generate filename
            ext = os.path.splitext(file_path)[1]
            filename = f"company_logo{ext}"
            dest_path = os.path.join(logos_dir, filename)

            # Copy file
            shutil.copy2(file_path, dest_path)
            
            self._current_logo_name = filename
            self._update_logo_preview(filename)
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to select logo: {e}")

    def _clear_logo(self):
        self._current_logo_name = ""
        self._logo_preview.setText("No Logo")
        self._logo_preview.setPixmap(QPixmap())

    def _update_logo_preview(self, filename):
        if not filename:
            self._logo_preview.setText("No Logo")
            self._logo_preview.setPixmap(QPixmap())
            return
            
        try:
            from database.db import get_app_data_dir
            path = os.path.join(get_app_data_dir(), "logos", filename)
            if os.path.exists(path):
                pix = QPixmap(path)
                if not pix.isNull():
                    scaled = pix.scaled(90, 90, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self._logo_preview.setPixmap(scaled)
                    return
            self._logo_preview.setText("Logo Not Found")
        except Exception:
            self._logo_preview.setText("Preview Error")

    # ── Save ─────────────────────────────────────────────────────────────────

    def _save(self):
        data = {k: i.text().strip() for k, i in self._inputs.items()}
        data["receipt_header"]       = self._receipt_header.text().strip()
        data["footer_text"]          = self._footer.toPlainText().strip()
        data["terms_and_conditions"] = self._terms.toPlainText().strip()
        data["invoice_prefix"]       = self._prefix_inp.text().strip().upper()
        data["invoice_start_number"] = str(self._start_num.value())
        data["allow_credit_sales"]   = "1" if self._allow_credit_chk.isChecked() else "0"
        data["logo_path"]            = self._current_logo_name

        # Pharmacy mode — terminal-local, saved to app_data/pharmacy_settings.json
        try:
            from settings.pharmacy_settings import set_pharmacy_mode
            set_pharmacy_mode(bool(self._pharmacy_mode_chk.isChecked()))
        except Exception as e:
            print(f"[CompanyDefaultsPage] pharmacy_mode save skipped: {e}")

        for key, lbl in self._ro_labels.items():
            v = lbl.text()
            data[key] = "" if v == "—" else v

        try:
            from models.company_defaults import save_defaults
            save_defaults(data)
            self._show_status("Saved successfully.")
        except Exception as e:
            self._show_status(f"{e}", error=True)

    def _show_status(self, msg, error=False):
        color = DANGER if error else "#2ecc71"
        self._status_lbl.setStyleSheet(
            f"font-size:13px; background:transparent; color:{color};"
        )
        self._status_lbl.setText(msg)
        import shiboken6
        QTimer.singleShot(3000, lambda: (
            shiboken6.isValid(self._status_lbl) and self._status_lbl.setText("")
        ))