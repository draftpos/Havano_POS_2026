import sys
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QApplication
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QColor, QPainter, QPixmap

class SleekLoaderOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("SleekLoaderOverlay { background-color: transparent; }")
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setAlignment(Qt.AlignCenter)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        
        from PySide6.QtWidgets import QPushButton, QLabel
        from PySide6.QtCore import QSize
        
        # Spinner
        self.spinner_btn = QPushButton(self)
        self.spinner_btn.setFlat(True)
        self.spinner_btn.setStyleSheet("background: transparent; border: none;")
        self.spinner_btn.setIconSize(QSize(48, 48))
        try:
            import qtawesome as qta
            self._spin_anim = qta.Spin(self.spinner_btn, interval=8, step=5)
            icon = qta.icon("fa5s.spinner", color="#3b82f6", animation=self._spin_anim)
            self.spinner_btn.setIcon(icon)
        except Exception:
            pass
            
        self.main_layout.addWidget(self.spinner_btn)
        
        # Loading Text
        self.text_lbl = QLabel("Loading...", self)
        self.text_lbl.setAlignment(Qt.AlignCenter)
        self.text_lbl.setStyleSheet("color: #1e293b; font-weight: bold; font-family: 'Segoe UI'; font-size: 14px;")
        self.main_layout.addWidget(self.text_lbl)
        
        self.hide()

    _active_loader = None

    def paintEvent(self, event):
        # Paint a sleek rounded semi-transparent background
        from PySide6.QtGui import QPainter, QColor
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, 240))
        painter.drawRoundedRect(self.rect(), 12, 12)

    def set_status(self, status, detail=""):
        try:
            txt = str(status or "")
            if detail:
                txt = f"{txt}\n{detail}"
            self.text_lbl.setText(txt)
            self.text_lbl.adjustSize()
            if not self.parent():
                fm = self.text_lbl.fontMetrics()
                lines = txt.split("\n") if txt else [""]
                max_w = max([fm.horizontalAdvance(line) for line in lines])
                w = max(200, max_w + 50)
                h = max(120, 65 + len(lines) * 22)
                self.resize(w, h)
                screen_geo = QApplication.primaryScreen().geometry()
                self.move(screen_geo.center() - self.rect().center())
            QApplication.processEvents()
        except Exception:
            pass

    def show_loading(self, timeout_ms=2000):
        try:
            if SleekLoaderOverlay._active_loader and SleekLoaderOverlay._active_loader != self:
                try:
                    SleekLoaderOverlay._active_loader.hide_loading()
                except Exception:
                    pass
            SleekLoaderOverlay._active_loader = self

            if self.parent():
                self.resize(self.parent().size())
            else:
                self.resize(140, 120)
                screen_geo = QApplication.primaryScreen().geometry()
                self.move(screen_geo.center() - self.rect().center())
            self.show()
            self.raise_()

            if timeout_ms > 0:
                QTimer.singleShot(timeout_ms, self._watchdog_dismiss)
        except Exception:
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
        except Exception:
            pass
