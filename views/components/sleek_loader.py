import sys
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGraphicsDropShadowEffect,
    QApplication, QFrame, QHBoxLayout
)
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QColor, QPainter, QPen

class SleekLoaderOverlay(QWidget):
    """
    An extremely minimal, small loading box.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("SleekLoaderOverlay { background: transparent; }")
        
        # Layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setAlignment(Qt.AlignCenter)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        # The actual small dialog box
        self.box = QFrame()
        self.box.setFixedSize(250, 80)
        self.box.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 12px;
                border: 1px solid #cbd5e1;
            }
        """)
        
        # Box layout (horizontal)
        self.box_layout = QHBoxLayout(self.box)
        self.box_layout.setContentsMargins(20, 0, 20, 0)
        self.box_layout.setSpacing(15)
        
        # Restore the round spinner
        self.spinner = SpinnerWidget(self)
        self.box_layout.addWidget(self.spinner)
        
        # Status
        self.status_label = QLabel("Initializing...", self)
        self.status_label.setStyleSheet("""
            QLabel {
                color: #1e293b;
                font-size: 14px;
                font-weight: 600;
                font-family: 'Segoe UI', sans-serif;
                background: transparent;
                border: none;
            }
        """)
        self.status_label.setAlignment(Qt.AlignCenter)
        self.box_layout.addWidget(self.status_label)
        
        # Shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 60))
        self.box.setGraphicsEffect(shadow)
        
        self.main_layout.addWidget(self.box)
        self.hide()

    _active_loader = None

    def paintEvent(self, event):
        # Draw a faint dark overlay to dim the UI behind it
        if self.parent():
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor(0, 0, 0, 80))

    def set_status(self, status, detail=""):
        try:
            self.status_label.setText(status)
        except (RuntimeError, Exception):
            pass

    def show_loading(self, timeout_ms=2000):
        try:
            # Automatically close any previous loader so they NEVER overlap
            if SleekLoaderOverlay._active_loader and SleekLoaderOverlay._active_loader != self:
                try:
                    SleekLoaderOverlay._active_loader.hide_loading()
                except Exception:
                    pass
            SleekLoaderOverlay._active_loader = self

            if self.parent():
                self.resize(self.parent().size())
            else:
                # Standalone mode: just size to the box and center
                self.resize(250, 80)
                screen_geo = QApplication.primaryScreen().geometry()
                x = (screen_geo.width() - 250) // 2
                y = (screen_geo.height() - 80) // 2
                self.move(x, y)
            self.show()
            self.raise_()

            # Watchdog safety: auto-dismiss if left hanging
            if timeout_ms > 0:
                QTimer.singleShot(timeout_ms, self._watchdog_dismiss)
        except (RuntimeError, Exception):
            pass

    def _watchdog_dismiss(self):
        try:
            if self.isVisible():
                self.hide_loading()
        except Exception:
            pass

    def hide_loading(self):
        try:
            if SleekLoaderOverlay._active_loader == self:
                SleekLoaderOverlay._active_loader = None
            self.hide()
            self.close()
            self.deleteLater()
            try:
                from PySide6.QtWidgets import QApplication
                QApplication.processEvents()
            except Exception:
                pass
        except (RuntimeError, Exception):
            pass

    def resizeEvent(self, event):
        super().resizeEvent(event)

class SpinnerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(24, 24)
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._rotate)
        self.timer.start(16)

    def _rotate(self):
        self.angle = (self.angle + 10) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(3, 3, -3, -3)
        
        pen = QPen(QColor(241, 245, 249))
        pen.setWidth(3)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawEllipse(rect)
        
        pen.setColor(QColor("#3b82f6"))
        painter.setPen(pen)
        painter.drawArc(rect, -self.angle * 16, 100 * 16)
