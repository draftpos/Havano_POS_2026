from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox, QWidget
)
from PySide6.QtCore import Qt, QThread, Signal
import qtawesome as qta

from models.fiscal_settings import FiscalSettingsRepository

class RevmaxOperationThread(QThread):
    finished_signal = Signal(bool, str)

    def __init__(self, action: str):
        super().__init__()
        self.action = action

    def run(self):
        try:
            from services.revmax_api_service import get_revmax_api_service
            repo = FiscalSettingsRepository()
            settings = repo.get_settings()
            if not settings or not settings.enabled or settings.provider != "revmax":
                self.finished_signal.emit(False, "Revmax API is not configured or enabled.")
                return

            service = get_revmax_api_service()
            
            if self.action == "open":
                self.finished_signal.emit(True, "Fiscal Day opened implicitly by Revmax (if applicable).")
            elif self.action == "close":
                result = service.close_fiscal_day(settings)
                if result.is_success:
                    self.finished_signal.emit(True, "Fiscal Day closed successfully (ZReport).")
                else:
                    self.finished_signal.emit(False, f"Failed to close Fiscal Day: {result.error}")
            elif self.action == "status":
                status_res = service.ping_revmax(settings)
                if status_res.is_success:
                    data = status_res.data
                    self.finished_signal.emit(True, f"Device Online. Status Data: {data}")
                else:
                    self.finished_signal.emit(False, f"Device Offline: {status_res.error}")
        except Exception as e:
            self.finished_signal.emit(False, f"Exception during Revmax operation: {str(e)}")

class RevmaxFiscalDialog(QDialog):
    """
    A smart dialog to handle Revmax fiscal day operations (Open/Close shift).
    """
    def __init__(self, parent=None, initial_action=None):
        """
        initial_action can be "open", "close", or None (for options menu view).
        """
        super().__init__(parent)
        self.setWindowTitle("Revmax Fiscalization")
        self.setMinimumWidth(600)
        self.setMinimumHeight(250)
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setStyleSheet("QDialog { background-color: #ffffff; }")
        
        self.initial_action = initial_action
        self._thread = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(25, 25, 25, 25)

        # Title / Info
        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        if self.initial_action == "open":
            self.info_label.setText("Shift has started.\n\nPlease open the fiscal day on the Revmax device to begin recording fiscal sales.")
        elif self.initial_action == "close":
            self.info_label.setText("Shift has closed.\n\nPlease close the fiscal day on the Revmax device to finalize the Z-Report.")
        else:
            self.info_label.setText("Revmax Fiscal Operations\n\nManage the hardware device's fiscal day.")
        
        self.info_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #1a5fb4;")
        self.info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.info_label)

        # Status
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 12px; color: #64748b;")
        layout.addWidget(self.status_label)
        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_open = QPushButton("Open Fiscal Day")
        self.btn_open.setFixedHeight(40)
        self.btn_open.setStyleSheet("background-color: #10b981; color: white; font-weight: bold; border-radius: 5px;")
        self.btn_open.clicked.connect(lambda: self._perform_action("open"))

        self.btn_close = QPushButton("Close Fiscal Day (Z-Report)")
        self.btn_close.setFixedHeight(40)
        self.btn_close.setStyleSheet("background-color: #b02020; color: white; font-weight: bold; border-radius: 5px;")
        self.btn_close.clicked.connect(lambda: self._perform_action("close"))

        self.btn_cancel = QPushButton("Close")
        self.btn_cancel.setFixedHeight(40)
        self.btn_cancel.setStyleSheet("background-color: #e4eaf4; color: #1a5fb4; font-weight: bold; border-radius: 5px;")
        self.btn_cancel.clicked.connect(self.reject)

        # Highlight the primary button if this dialog was opened automatically
        if self.initial_action == "open":
            self.btn_close.setVisible(False)
            btn_layout.addWidget(self.btn_open)
        elif self.initial_action == "close":
            self.btn_open.setVisible(False)
            btn_layout.addWidget(self.btn_close)
        else:
            # Show both for Options menu
            self.btn_status = QPushButton("Check Status")
            self.btn_status.setFixedHeight(40)
            self.btn_status.setStyleSheet("background-color: #1a5fb4; color: white; font-weight: bold; border-radius: 5px;")
            self.btn_status.clicked.connect(lambda: self._perform_action("status"))
            
            btn_layout.addWidget(self.btn_open)
            btn_layout.addWidget(self.btn_status)
            btn_layout.addWidget(self.btn_close)

        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

    def _perform_action(self, action: str):
        self.btn_open.setEnabled(False)
        self.btn_close.setEnabled(False)
        if hasattr(self, 'btn_status'):
            self.btn_status.setEnabled(False)
        
        self.status_label.setText(f"Processing '{action}'...")
        self.status_label.setStyleSheet("color: #1a5fb4; font-weight: bold;")
        
        self._thread = RevmaxOperationThread(action)
        self._thread.finished_signal.connect(self._on_action_finished)
        self._thread.start()

    def _on_action_finished(self, success: bool, message: str):
        self.btn_open.setEnabled(True)
        self.btn_close.setEnabled(True)
        if hasattr(self, 'btn_status'):
            self.btn_status.setEnabled(True)

        if success:
            self.status_label.setText(f"Success: {message}")
            self.status_label.setStyleSheet("color: #10b981; font-weight: bold;")
            QMessageBox.information(self, "Success", message)
            if self.initial_action in ("open", "close"):
                self.accept()
        else:
            self.status_label.setText(f"Error: {message}")
            self.status_label.setStyleSheet("color: #b02020; font-weight: bold;")
            QMessageBox.warning(self, "Fiscal Operation Failed", message)
