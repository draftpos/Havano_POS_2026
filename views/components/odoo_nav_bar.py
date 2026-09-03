from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QLabel, QMenu, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
import qtawesome as qta

# Colors matching the main window palette
from theme import *

class OdooHoverMenuButton(QPushButton):
    """
    A navigation tab button that opens a drop-down menu on hover or click.
    If it has no menu items, it acts as a normal clickable tab.
    """
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setFixedHeight(30)
        self.setCursor(Qt.PointingHandCursor)
        self._menu = QMenu(self)
        self._menu.setStyleSheet(f"""
            QMenu {{
                background-color: {WHITE};
                border: 1px solid {BORDER};
                border-radius: 4px;
                padding: 4px 0;
                font-size: 13px;
                color: {DARK_TEXT};
            }}
            QMenu::item {{
                padding: 8px 24px;
                margin: 2px 4px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {ACCENT};
                color: {WHITE};
            }}
            QMenu::separator {{
                height: 1px;
                background: {BORDER};
                margin: 4px 10px;
            }}
        """)
        self._has_items = False
        self._apply_style(False)
        self.clicked.connect(self._show_menu_if_has_items)

    def _apply_style(self, hovered: bool):
        # Odoo style: transparent background, active text color
        if hovered:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {ACCENT_H}; color: {WHITE}; border: none;
                    border-radius: 4px; font-size: 13px; font-weight: 500; padding: 0 12px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent; color: {WHITE}; border: none;
                    font-size: 13px; font-weight: 500; padding: 0 12px;
                }}
                QPushButton:hover {{
                    background-color: {ACCENT_H}; border-radius: 4px;
                }}
            """)

    def add_menu_item(self, label: str, callback):
        self._has_items = True
        action = QAction(label, self)
        action.triggered.connect(callback)
        self._menu.addAction(action)

    def add_separator(self):
        if self._has_items:
            self._menu.addSeparator()

    def _show_menu_if_has_items(self):
        if self._has_items:
            pos = self.mapToGlobal(self.rect().bottomLeft())
            self._apply_style(True)
            self._menu.exec(pos)
            self._apply_style(False)

    def enterEvent(self, event):
        super().enterEvent(event)
        if self._has_items:
            self._show_menu_if_has_items()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._apply_style(False)


class OdooNavBar(QWidget):
    """
    Top navigation bar resembling Odoo's inner module navigation.
    Contains: Back button, App Title, and Tab Dropdowns.
    """
    back_requested = Signal()

    def __init__(self, app_title: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(50)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(f"OdooNavBar {{ background-color: {ACCENT}; border-bottom: 2px solid {ACCENT_H}; }}")
        self._tabs: dict[str, OdooHoverMenuButton] = {}
        self._build(app_title)

    def _build(self, app_title: str):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(16)

        # Back Button
        self.back_btn = QPushButton(" Home")
        self.back_btn.setIcon(qta.icon("fa5s.home", color=WHITE))
        self.back_btn.setFixedHeight(30)
        self.back_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn.setToolTip("Back to Apps")
        self.back_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent; color: {WHITE}; border: none;
                font-size: 13px; font-weight: 500; padding: 0 12px;
            }}
            QPushButton:hover {{
                background-color: {ACCENT_H}; border-radius: 4px;
            }}
        """)
        self.back_btn.clicked.connect(self.back_requested.emit)
        layout.addWidget(self.back_btn)

        # App Title
        title_lbl = QLabel(app_title)
        title_lbl.setStyleSheet(f"color: {WHITE}; font-size: 16px; font-weight: bold; background: transparent;")
        layout.addWidget(title_lbl)

        # Tabs Container
        self.tabs_layout = QHBoxLayout()
        self.tabs_layout.setSpacing(4)
        self.tabs_layout.setContentsMargins(16, 0, 0, 0)
        layout.addLayout(self.tabs_layout)

        layout.addStretch()

        # User / Logout Container
        user_container = QHBoxLayout()
        user_container.setSpacing(10)
        
        # Add Logout Button
        self.logout_btn = QPushButton(" Logout")
        self.logout_btn.setIcon(qta.icon("fa5s.power-off", color="white"))
        self.logout_btn.setFixedSize(90, 30)
        self.logout_btn.setCursor(Qt.PointingHandCursor)
        self.logout_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DANGER};
                color: {WHITE};
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 13px;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                background-color: {DANGER_H if 'DANGER_H' in globals() else '#c0392b'};
            }}
        """)
        
        # The parent window (main POS window) should handle the logout.
        def _trigger_logout():
            if hasattr(self.window(), '_logout'):
                self.window()._logout()
            else:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Error", "Logout function not found on main window.")

        self.logout_btn.clicked.connect(_trigger_logout)
        user_container.addWidget(self.logout_btn)
        
        layout.addLayout(user_container)

    def add_tab(self, tab_name: str, click_callback=None) -> OdooHoverMenuButton:
        """
        Add a top-level tab. 
        If click_callback is provided, clicking the tab itself triggers it (e.g., Dashboard).
        Returns the button so you can add drop-down items to it later.
        """
        btn = OdooHoverMenuButton(tab_name)
        if click_callback:
            btn.clicked.connect(click_callback)
        self.tabs_layout.addWidget(btn)
        self._tabs[tab_name] = btn
        return btn

    def add_dropdown_item(self, tab_name: str, item_label: str, callback):
        """Add an item to the dropdown menu of a specific tab."""
        if tab_name in self._tabs:
            self._tabs[tab_name].add_menu_item(item_label, callback)

