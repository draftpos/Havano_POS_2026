# =============================================================================
# views/dialogs/shop_terminal_dialogs.py
#
# SaaS Shop Selection, Terminal Selection, and Session Takeover Dialogs
# Matching the exact behavior of Havano Mobile POS (Flutter).
# =============================================================================

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QListWidget, QListWidgetItem, QWidget, QFrame, QMessageBox
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QIcon
from utils.icon_utils import safe_icon, safe_pixmap
try:
    import qtawesome as qta
except Exception:
    qta = None

# Color Palette matching Havano POS
NAVY     = "#1A2530"
NAVY_2   = "#2C3E50"
ACCENT   = "#2980B9"
ACCENT_H = "#3498DB"
WHITE    = "#FFFFFF"
OFF_WHITE= "#F8F9FA"
BORDER   = "#E2E8F0"
MUTED    = "#718096"
SUCCESS  = "#2ECC71"
WARNING  = "#E67E22"
DANGER   = "#E74C3C"


class ShopSelectionDialog(QDialog):
    """Dialog allowing users (Admins) to select a Shop/Store in SaaS Mode."""
    def __init__(self, shops: list[dict], parent=None):
        super().__init__(parent)
        self.shops = shops
        self.selected_shop = None
        self.setWindowTitle("Select Shop - Havano POS")
        self.setFixedSize(480, 520)
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet(f"background-color: {OFF_WHITE};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        hdr = QWidget()
        hdr.setFixedHeight(90)
        hdr.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {NAVY}, stop:1 {NAVY_2});
            border-top-left-radius: 12px; border-top-right-radius: 12px;
        """)
        hl = QVBoxLayout(hdr)
        hl.setContentsMargins(20, 15, 20, 15)

        title = QLabel("Select Store / Shop")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setStyleSheet(f"color: {WHITE}; background: transparent;")
        hl.addWidget(title)

        sub = QLabel("Select the store you wish to operate in this session")
        sub.setFont(QFont("Segoe UI", 10))
        sub.setStyleSheet(f"color: {BORDER}; background: transparent;")
        hl.addWidget(sub)
        layout.addWidget(hdr)

        # Content
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(20, 15, 20, 15)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                background: {WHITE}; border: 1.5px solid {BORDER}; border-radius: 10px;
                padding: 5px;
            }}
            QListWidget::item {{
                padding: 12px; border-bottom: 1px solid {BORDER}; border-radius: 6px;
            }}
            QListWidget::item:hover {{
                background: #EDF2F7;
            }}
            QListWidget::item:selected {{
                background: {ACCENT}; color: {WHITE}; font-weight: bold;
            }}
        """)

        for shop in self.shops:
            name = str(shop.get("name") or shop.get("shop_name") or f"Shop {shop.get('id')}")
            shop_id = shop.get("id")
            days_left = shop.get("days_left") or shop.get("subscription_days")
            
            exp_text = ""
            if days_left is not None:
                try:
                    d_int = int(days_left)
                    if d_int <= 0:
                        exp_text = " ⚠️ [EXPIRED]"
                    elif d_int <= 3:
                        exp_text = f" ⚠️ [{d_int} days left]"
                    else:
                        exp_text = f" ({d_int} days left)"
                except Exception:
                    exp_text = f" ({days_left})"

            item = QListWidgetItem(f"🏬 {name}{exp_text}")
            item.setData(Qt.UserRole, shop)
            if exp_text and "EXPIRED" in exp_text:
                item.setForeground(Qt.red)
            self.list_widget.addItem(item)

        if self.shops:
            self.list_widget.setCurrentRow(0)

        cl.addWidget(self.list_widget)

        # Footer Actions
        footer = QWidget()
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(20, 10, 20, 20)

        confirm_btn = QPushButton("Confirm Shop")
        confirm_btn.setFixedHeight(44)
        confirm_btn.setFont(QFont("Segoe UI", 11, QFont.Bold))
        confirm_btn.setCursor(Qt.PointingHandCursor)
        confirm_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT}; color: {WHITE}; border-radius: 8px; border: none;
            }}
            QPushButton:hover {{ background: {ACCENT_H}; }}
        """)
        confirm_btn.clicked.connect(self._on_confirm)
        fl.addWidget(confirm_btn)

        layout.addWidget(content, 1)
        layout.addWidget(footer)

    def _on_confirm(self):
        item = self.list_widget.currentItem()
        if item:
            shop = item.data(Qt.UserRole)
            shop_name = str(shop.get("name") or shop.get("shop_name") or "Shop")
            days_left = shop.get("days_left") or shop.get("subscription_days")
            if days_left is not None:
                try:
                    d_int = int(days_left)
                    if d_int <= 0:
                        show_subscription_expired_dialog(self, shop_name)
                        return
                    elif d_int <= 3:
                        show_subscription_warning_dialog(self, shop_name, d_int)
                except Exception:
                    pass

            self.selected_shop = shop
            self.accept()
        else:
            QMessageBox.warning(self, "Selection Required", "Please select a shop to continue.")


class TerminalSelectionDialog(QDialog):
    """Dialog allowing users (Admins) to select a Terminal for the chosen shop."""
    def __init__(self, terminals: list[dict], current_user_email: str, current_device_id: str, is_admin: bool = True, parent=None):
        super().__init__(parent)
        self.terminals = terminals
        self.current_user_email = current_user_email.strip().lower()
        self.current_device_id = current_device_id.strip().lower()
        self.is_admin = is_admin
        self.selected_terminal = None
        self.setWindowTitle("Select Terminal - Havano POS")
        self.setFixedSize(520, 560)
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet(f"background-color: {OFF_WHITE};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header
        hdr = QWidget()
        hdr.setFixedHeight(90)
        hdr.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {NAVY}, stop:1 {NAVY_2});
            border-top-left-radius: 12px; border-top-right-radius: 12px;
        """)
        hl = QVBoxLayout(hdr)
        hl.setContentsMargins(20, 15, 20, 15)

        title = QLabel("Select Terminal Register")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setStyleSheet(f"color: {WHITE}; background: transparent;")
        hl.addWidget(title)

        sub = QLabel("Select the POS terminal register for this machine")
        sub.setFont(QFont("Segoe UI", 10))
        sub.setStyleSheet(f"color: {BORDER}; background: transparent;")
        hl.addWidget(sub)
        layout.addWidget(hdr)

        # Content
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(20, 15, 20, 15)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                background: {WHITE}; border: 1.5px solid {BORDER}; border-radius: 10px; padding: 5px;
            }}
            QListWidget::item {{
                padding: 12px; border-bottom: 1px solid {BORDER}; border-radius: 6px;
            }}
            QListWidget::item:hover {{ background: #EDF2F7; }}
            QListWidget::item:selected {{ background: {ACCENT}; color: {WHITE}; font-weight: bold; }}
        """)

        for term in self.terminals:
            t_name = str(term.get("name") or f"Terminal {term.get('id')}")
            is_taken = bool(term.get("is_taken") or term.get("taken_by"))
            taken_by = str(term.get("taken_by_user_name") or term.get("taken_by_user_email") or term.get("taken_by") or "").strip()
            term_device = str(term.get("device_hardware_id") or "").strip().lower()

            status_str = "🟢 Available"
            if is_taken:
                status_str = f"🟠 Taken by {taken_by}"
            if term_device and term_device == self.current_device_id:
                status_str += " (This Machine)"

            item = QListWidgetItem(f"🖥️  {t_name}  |  {status_str}")
            item.setData(Qt.UserRole, term)
            self.list_widget.addItem(item)

        if self.terminals:
            self.list_widget.setCurrentRow(0)

        cl.addWidget(self.list_widget)

        # Footer Actions
        footer = QWidget()
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(20, 10, 20, 20)

        confirm_btn = QPushButton("Select Terminal")
        confirm_btn.setFixedHeight(44)
        confirm_btn.setFont(QFont("Segoe UI", 11, QFont.Bold))
        confirm_btn.setCursor(Qt.PointingHandCursor)
        confirm_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT}; color: {WHITE}; border-radius: 8px; border: none;
            }}
            QPushButton:hover {{ background: {ACCENT_H}; }}
        """)
        confirm_btn.clicked.connect(self._on_confirm)
        fl.addWidget(confirm_btn)

        layout.addWidget(content, 1)
        layout.addWidget(footer)

    def _on_confirm(self):
        item = self.list_widget.currentItem()
        if item:
            self.selected_terminal = item.data(Qt.UserRole)
            self.accept()
        else:
            QMessageBox.warning(self, "Selection Required", "Please select a terminal to continue.")


class TerminalTakeoverDialog(QDialog):
    """
    Dialog shown when a user selects a terminal actively assigned to another session/device.
    Matches the Flutter takeover prompt options.
    """
    def __init__(self, message: str, is_admin: bool = True, parent=None):
        super().__init__(parent)
        self.message = message
        self.is_admin = is_admin
        self.result_action = None  # True: Takeover, False: Restricted/No Terminal, None: Cancel
        self.setWindowTitle("Terminal Session Active - Havano POS")
        self.setFixedSize(480, 240)
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet(f"background-color: {WHITE};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        title = QLabel("⚠️ Terminal Session Active")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setStyleSheet(f"color: {WARNING};")
        layout.addWidget(title)

        msg_lbl = QLabel(self.message)
        msg_lbl.setWordWrap(True)
        msg_lbl.setFont(QFont("Segoe UI", 10))
        msg_lbl.setStyleSheet(f"color: {NAVY};")
        layout.addWidget(msg_lbl)

        layout.addStretch()

        btns_layout = QHBoxLayout()
        btns_layout.setSpacing(10)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(40)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(f"background: {OFF_WHITE}; color: {NAVY}; border: 1px solid {BORDER}; border-radius: 6px;")
        cancel_btn.clicked.connect(self._on_cancel)
        btns_layout.addWidget(cancel_btn)

        no_term_btn = QPushButton("Login without Terminal" if not self.is_admin else "No Terminal Mode")
        no_term_btn.setFixedHeight(40)
        no_term_btn.setCursor(Qt.PointingHandCursor)
        no_term_btn.setStyleSheet(f"background: {OFF_WHITE}; color: {NAVY_2}; border: 1px solid {BORDER}; border-radius: 6px;")
        no_term_btn.clicked.connect(self._on_no_terminal)
        btns_layout.addWidget(no_term_btn)

        switch_btn = QPushButton("Switch Session")
        switch_btn.setFixedHeight(40)
        switch_btn.setFont(QFont("Segoe UI", 10, QFont.Bold))
        switch_btn.setCursor(Qt.PointingHandCursor)
        switch_btn.setStyleSheet(f"background: {ACCENT}; color: {WHITE}; border-radius: 6px; border: none;")
        switch_btn.clicked.connect(self._on_switch)
        btns_layout.addWidget(switch_btn)

        layout.addLayout(btns_layout)

    def _on_cancel(self):
        self.result_action = None
        self.reject()

    def _on_no_terminal(self):
        self.result_action = False
        self.accept()

    def _on_switch(self):
        self.result_action = True
        self.accept()


class StoreAccessDeniedDialog(QDialog):
    """
    Uniform popup dialog informing the user that store access is denied,
    matching the exact visual design of Shop & Terminal dialogs.
    """
    def __init__(self, message: str, store_name: str = "", parent=None):
        super().__init__(parent)
        self.message = message
        self.store_name = store_name
        self.setWindowTitle("Store Access Denied - Havano POS")
        self.setFixedSize(480, 260)
        self.setModal(True)
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet(f"background-color: {OFF_WHITE};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header Bar matching ShopSelectionDialog
        hdr = QWidget()
        hdr.setFixedHeight(80)
        hdr.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {NAVY}, stop:1 {NAVY_2});
            border-top-left-radius: 8px; border-top-right-radius: 8px;
        """)
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(20, 15, 20, 15)
        hl.setSpacing(12)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(safe_pixmap("fa5s.ban", 28, 28, color=DANGER))
        hl.addWidget(icon_lbl)

        title = QLabel("Store Access Denied")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setStyleSheet(f"color: {WHITE}; background: transparent;")
        hl.addWidget(title, 1)

        layout.addWidget(hdr)

        # Body Message Area
        body = QWidget()
        body.setStyleSheet(f"background: {WHITE};")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(24, 20, 24, 16)
        bl.setSpacing(10)

        msg_text = self.message or f"User does not belong to Store {self.store_name}."
        msg_lbl = QLabel(msg_text)
        msg_lbl.setWordWrap(True)
        msg_lbl.setFont(QFont("Segoe UI", 12, QFont.Bold))
        msg_lbl.setStyleSheet(f"color: {NAVY};")
        bl.addWidget(msg_lbl)

        sub_lbl = QLabel("Your account is not authorized to log in or operate on this store's POS terminal. Please contact your system administrator.")
        sub_lbl.setWordWrap(True)
        sub_lbl.setFont(QFont("Segoe UI", 10))
        sub_lbl.setStyleSheet(f"color: {MUTED};")
        bl.addWidget(sub_lbl)

        bl.addStretch()

        # Footer / Close Button
        footer = QWidget()
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(20, 10, 20, 20)

        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(44)
        close_btn.setFont(QFont("Segoe UI", 11, QFont.Bold))
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT}; color: {WHITE}; border-radius: 8px; border: none;
            }}
            QPushButton:hover {{ background: {ACCENT_H}; }}
        """)
        close_btn.clicked.connect(self.accept)
        fl.addWidget(close_btn)

        layout.addWidget(body, 1)
        layout.addWidget(footer)


def show_store_access_denied_dialog(parent_widget, message: str, store_name: str = ""):
    """Displays the smart Store Access Denied popup dialog with a clean Close button."""
    dlg = StoreAccessDeniedDialog(message=message, store_name=store_name, parent=parent_widget)
    dlg.exec()


class SubscriptionExpiredDialog(QDialog):
    """
    Smart modal dialog informing the user that their store subscription has expired,
    blocking login and execution.
    """
    def __init__(self, store_name: str = "", parent=None):
        super().__init__(parent)
        self.store_name = store_name
        self.setWindowTitle("Subscription Expired - Havano POS")
        self.setFixedSize(460, 270)
        self.setModal(True)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet(f"QDialog {{ background-color: {WHITE}; border: 2px solid {DANGER}; border-radius: 12px; }}")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header Bar
        hdr = QWidget()
        hdr.setFixedHeight(64)
        hdr.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #900C3F, stop:1 {DANGER});
            border-top-left-radius: 10px; border-top-right-radius: 10px;
        """)
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(20, 12, 20, 12)
        hl.setSpacing(12)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(safe_pixmap("fa5s.exclamation-triangle", 26, 26, color=WHITE))
        hl.addWidget(icon_lbl)

        title = QLabel("Subscription Expired")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setStyleSheet(f"color: {WHITE}; background: transparent;")
        hl.addWidget(title, 1)

        layout.addWidget(hdr)

        # Body
        body = QWidget()
        body.setStyleSheet(f"background: {WHITE};")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(24, 18, 24, 14)
        bl.setSpacing(10)

        store_str = f"Store '{self.store_name}'" if self.store_name else "Your store"
        msg_lbl = QLabel(f"Subscription for {store_str} has EXPIRED.")
        msg_lbl.setWordWrap(True)
        msg_lbl.setFont(QFont("Segoe UI", 12, QFont.Bold))
        msg_lbl.setStyleSheet(f"color: {DANGER};")
        bl.addWidget(msg_lbl)

        sub_lbl = QLabel("You cannot log in or process transactions for this store. Please renew your subscription or contact Havano support to reactivate access.")
        sub_lbl.setWordWrap(True)
        sub_lbl.setFont(QFont("Segoe UI", 9.5))
        sub_lbl.setStyleSheet(f"color: {NAVY};")
        bl.addWidget(sub_lbl)

        bl.addStretch()

        # Footer
        footer = QWidget()
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(24, 0, 24, 18)

        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(42)
        close_btn.setFont(QFont("Segoe UI", 10, QFont.Bold))
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: {DANGER}; color: {WHITE}; border-radius: 8px; border: none;
            }}
            QPushButton:hover {{ background: #C0392B; }}
        """)
        close_btn.clicked.connect(self.accept)
        fl.addWidget(close_btn)

        layout.addWidget(body, 1)
        layout.addWidget(footer)


class SubscriptionWarningDialog(QDialog):
    """
    Smart modal prompt informing the user each time they log in when 3 days or fewer
    remain on their store subscription.
    """
    def __init__(self, store_name: str = "", days_left: int = 3, parent=None):
        super().__init__(parent)
        self.store_name = store_name
        self.days_left = days_left
        self.setWindowTitle("Subscription Warning - Havano POS")
        self.setFixedSize(460, 270)
        self.setModal(True)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet(f"QDialog {{ background-color: {WHITE}; border: 2px solid {WARNING}; border-radius: 12px; }}")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header Bar
        hdr = QWidget()
        hdr.setFixedHeight(64)
        hdr.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #D35400, stop:1 {WARNING});
            border-top-left-radius: 10px; border-top-right-radius: 10px;
        """)
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(20, 12, 20, 12)
        hl.setSpacing(12)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(safe_pixmap("fa5s.clock", 26, 26, color=WHITE))
        hl.addWidget(icon_lbl)

        title = QLabel("Subscription Expiring Soon")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setStyleSheet(f"color: {WHITE}; background: transparent;")
        hl.addWidget(title, 1)

        layout.addWidget(hdr)

        # Body
        body = QWidget()
        body.setStyleSheet(f"background: {WHITE};")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(24, 18, 24, 14)
        bl.setSpacing(10)

        store_str = f"Store '{self.store_name}'" if self.store_name else "Your store"
        days_str = f"{self.days_left} day{'s' if self.days_left != 1 else ''}"
        msg_lbl = QLabel(f"Warning: {store_str} subscription expires in {days_str}!")
        msg_lbl.setWordWrap(True)
        msg_lbl.setFont(QFont("Segoe UI", 11.5, QFont.Bold))
        msg_lbl.setStyleSheet(f"color: {WARNING};")
        bl.addWidget(msg_lbl)

        sub_lbl = QLabel("Your store subscription is ending soon. Please renew your subscription to prevent service disruption.")
        sub_lbl.setWordWrap(True)
        sub_lbl.setFont(QFont("Segoe UI", 9.5))
        sub_lbl.setStyleSheet(f"color: {NAVY};")
        bl.addWidget(sub_lbl)

        bl.addStretch()

        # Footer
        footer = QWidget()
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(24, 0, 24, 18)

        cont_btn = QPushButton("Continue to POS")
        cont_btn.setFixedHeight(42)
        cont_btn.setFont(QFont("Segoe UI", 10, QFont.Bold))
        cont_btn.setCursor(Qt.PointingHandCursor)
        cont_btn.setStyleSheet(f"""
            QPushButton {{
                background: {NAVY}; color: {WHITE}; border-radius: 8px; border: none;
            }}
            QPushButton:hover {{ background: {NAVY_2}; }}
        """)
        cont_btn.clicked.connect(self.accept)
        fl.addWidget(cont_btn)

        layout.addWidget(body, 1)
        layout.addWidget(footer)


def show_subscription_expired_dialog(parent_widget, store_name: str = ""):
    """Displays the Subscription Expired dialog, blocking user login."""
    dlg = SubscriptionExpiredDialog(store_name=store_name, parent=parent_widget)
    dlg.exec()


def show_subscription_warning_dialog(parent_widget, store_name: str = "", days_left: int = 3):
    """Displays the 3-day subscription expiry warning prompt each time user logs in."""
    dlg = SubscriptionWarningDialog(store_name=store_name, days_left=days_left, parent=parent_widget)
    dlg.exec()
