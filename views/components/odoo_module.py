from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QStackedWidget, QLabel, QFrame
)
from PySide6.QtCore import Qt
from views.components.odoo_nav_bar import OdooNavBar

WHITE = "#ffffff"
from theme import *

class DefaultDashboardCharts(QWidget):
    """A placeholder widget for the Charts on the Dashboard tab."""
    def __init__(self, module_name: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {OFF_WHITE};")
        layout = QVBoxLayout(self)
        
        lbl = QLabel(f"{module_name} Dashboard Charts")
        lbl.setStyleSheet(f"color: {NAVY}; font-size: 24px; font-weight: bold;")
        lbl.setAlignment(Qt.AlignCenter)
        
        frame = QFrame()
        frame.setStyleSheet(f"background: {WHITE}; border: 1px solid {BORDER}; border-radius: 8px;")
        frame_layout = QVBoxLayout(frame)
        frame_layout.addWidget(lbl)
        
        desc = QLabel("Visual charts will be rendered here.")
        desc.setStyleSheet(f"color: #7f8c8d; font-size: 14px;")
        desc.setAlignment(Qt.AlignCenter)
        frame_layout.addWidget(desc)
        
        layout.addWidget(frame)
        layout.setContentsMargins(40, 40, 40, 40)


class OdooModuleView(QWidget):
    """
    A unified view for an App module (e.g., Sales, Inventory).
    Contains an OdooNavBar at the top and a QStackedWidget below it.
    """
    def __init__(self, app_title: str, parent=None):
        super().__init__(parent)
        self.app_title = app_title
        self._build()

    def _build(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # 1. Nav Bar
        self.nav_bar = OdooNavBar(self.app_title, self)
        self.layout.addWidget(self.nav_bar)

        # 2. Stacked Widget for content pages
        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background-color: {OFF_WHITE};")
        self.layout.addWidget(self.stack, 1)

        self.default_dashboard = DefaultDashboardCharts(self.app_title)

    def on_back_requested(self, callback):
        """Connect the nav bar's back button to a callback (e.g., to go back to the app grid)."""
        self.nav_bar.back_requested.connect(callback)

    def add_tab_dropdown(self, tab_name: str):
        """Add a horizontal tab that acts as a dropdown menu."""
        self.nav_bar.add_tab(tab_name)

    def add_tab_direct(self, tab_name: str, widget: QWidget):
        """Add a horizontal tab that directly opens a widget when clicked (like Dashboard)."""
        idx = self.stack.addWidget(widget)
        self.nav_bar.add_tab(tab_name, lambda: self.stack.setCurrentIndex(idx))

    def add_dropdown_screen(self, tab_name: str, item_label: str, widget: QWidget):
        """
        Add a screen to the stacked widget, and a dropdown item to the specified tab 
        that switches to this screen when clicked.
        """
        idx = self.stack.addWidget(widget)
        self.nav_bar.add_dropdown_item(tab_name, item_label, lambda: self.stack.setCurrentIndex(idx))

    def add_dropdown_action(self, tab_name: str, item_label: str, callback):
        """
        Add a dropdown item to the specified tab that executes a callback function when clicked
        (e.g., to open a modal dialog instead of switching a stacked widget screen).
        """
        self.nav_bar.add_dropdown_item(tab_name, item_label, callback)

    def show_dashboard(self):
        """Switch the stack back to the default Dashboard view."""
        self.stack.setCurrentIndex(0)

