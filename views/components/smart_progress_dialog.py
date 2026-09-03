import time
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton, QApplication
)
from PySide6.QtGui import QFont

class SmartProgressDialog(QDialog):
    """
    Modern, High-Performance Smart Loader with real-time speed (items/sec) & ETA for Havano POS 2026.
    """
    canceled = Signal()

    def __init__(self, title="Processing Batch Operations", total_items=100, parent=None):
        super().__init__(parent)
        self.total_items = max(1, total_items)
        self.start_time = time.time()
        self.last_update_time = time.time()
        self.current_value = 0
        self.cancelled = False
        
        self.setWindowTitle(title)
        self.setFixedSize(460, 180)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setWindowModality(Qt.WindowModal)
        self._build_ui(title)

    def _build_ui(self, title):
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
                border: 2px solid #1e293b;
                border-radius: 8px;
            }
            QLabel {
                font-family: 'Segoe UI', Arial, sans-serif;
                background: transparent;
            }
            QProgressBar {
                background-color: #e2e8f0;
                border: none;
                border-radius: 6px;
                text-align: center;
                color: #ffffff;
                font-weight: bold;
                font-size: 11px;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a5fb4, stop:1 #3b82f6);
                border-radius: 6px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)

        # Title Banner
        title_lbl = QLabel(title)
        title_lbl.setFont(QFont("Segoe UI", 12, QFont.Bold))
        title_lbl.setStyleSheet("color: #1e293b;")
        layout.addWidget(title_lbl)

        # Status Detail Label
        self.lbl_status = QLabel("Initializing operation...")
        self.lbl_status.setStyleSheet("color: #475569; font-size: 12px;")
        layout.addWidget(self.lbl_status)

        # Progress Bar
        self.bar = QProgressBar()
        self.bar.setFixedHeight(22)
        self.bar.setRange(0, self.total_items)
        self.bar.setValue(0)
        layout.addWidget(self.bar)

        # Live Metrics Row (Speed & ETA - No Emojis)
        metrics_layout = QHBoxLayout()
        self.lbl_speed = QLabel("Speed: 0 items/sec")
        self.lbl_speed.setStyleSheet("color: #15803d; font-size: 11px; font-weight: 600;")
        
        self.lbl_eta = QLabel("ETA: Calculating...")
        self.lbl_eta.setStyleSheet("color: #1d4ed8; font-size: 11px; font-weight: 600;")
        
        metrics_layout.addWidget(self.lbl_speed)
        metrics_layout.addStretch()
        metrics_layout.addWidget(self.lbl_eta)
        layout.addLayout(metrics_layout)

        # Action Button Row (Cancel)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setFixedSize(85, 26)
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #475569;
                border: 1px solid #cbd5e1;
                border-radius: 5px;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #e2e8f0;
                color: #1e293b;
            }
        """)
        self.btn_cancel.clicked.connect(self._on_cancel)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

    def _on_cancel(self):
        self.cancelled = True
        self.lbl_status.setText("Cancelling operation...")
        self.btn_cancel.setEnabled(False)
        self.canceled.emit()

    def update_progress(self, current, item_name=""):
        """Update loader progress bar, speed (items/sec), and ETA."""
        self.current_value = current
        self.bar.setValue(current)
        
        now = time.time()
        elapsed = max(0.001, now - self.start_time)
        rate = current / elapsed
        remaining_items = max(0, self.total_items - current)
        eta_sec = remaining_items / rate if rate > 0 else 0

        item_desc = f" ({item_name})" if item_name else ""
        pct = int((current / self.total_items) * 100)
        self.lbl_status.setText(f"Processing {current:,} of {self.total_items:,}{item_desc} • {pct}%")
        self.lbl_speed.setText(f"Speed: {rate:,.0f} items/sec")
        
        if eta_sec < 1:
            self.lbl_eta.setText("ETA: Almost done")
        elif eta_sec < 60:
            self.lbl_eta.setText(f"ETA: {eta_sec:.1f}s")
        else:
            self.lbl_eta.setText(f"ETA: {int(eta_sec // 60)}m {int(eta_sec % 60)}s")

        QApplication.processEvents()

    def was_canceled(self):
        return self.cancelled
