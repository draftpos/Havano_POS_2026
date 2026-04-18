# views/dialogs/fiscal_settings_dialog.py

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QCheckBox, QGroupBox,
    QMessageBox, QProgressBar
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
import qtawesome as qta

from models.fiscal_settings import FiscalSettings, FiscalSettingsRepository
from services.zimra_api_service import get_zimra_service
from services.fiscal_device_monitor import get_device_monitor_service


class TestConnectionThread(QThread):
    """Thread for testing ZIMRA connection"""
    finished_signal = Signal(bool, str)  # success, message
    
    def __init__(self, settings: FiscalSettings):
        super().__init__()
        self.settings = settings
    
    def run(self):
        service = get_zimra_service()
        
        try:
            # First test token retrieval
            token_result = service.get_token(self.settings)
            if not token_result.is_success:
                self.finished_signal.emit(False, f"Token failed: {token_result.error}")
                return
            
            # Then test ping
            ping_result = service.ping_zimra(self.settings)
            if ping_result.is_success and ping_result.data:
                response = ping_result.data
                self.finished_signal.emit(
                    True, 
                    f"Connected! Device: {response.device_sn}\n"
                    f"Reporting Frequency: {response.reporting_frequency} min\n"
                    f"Operation ID: {response.operation_id}"
                )
            else:
                self.finished_signal.emit(False, f"Ping failed: {ping_result.error}")
                
        except Exception as e:
            self.finished_signal.emit(False, f"Connection error: {str(e)}")


class FiscalSettingsDialog(QDialog):
    """Dialog for configuring fiscalization settings with test connection first"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings_repo = FiscalSettingsRepository()
        self.settings = self.settings_repo.get_settings() or FiscalSettings()
        
        self.setWindowTitle("Fiscalization Settings")
        self.setMinimumSize(550, 500)
        self.setModal(True)
        
        self._test_thread: TestConnectionThread | None = None
        
        self._build_ui()
        self._load_settings()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Header
        header = QLabel("ZIMRA Fiscalization Configuration")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header.setFont(header_font)
        layout.addWidget(header)
        
        # Main group
        main_group = QGroupBox("Connection Settings")
        main_layout = QGridLayout(main_group)
        main_layout.setSpacing(10)
        
        # Enable checkbox
        self.enable_check = QCheckBox("Enable Fiscalization")
        main_layout.addWidget(self.enable_check, 0, 0, 1, 2)
        
        # Base URL
        main_layout.addWidget(QLabel("Base URL:"), 1, 0)
        self.base_url_edit = QLineEdit()
        self.base_url_edit.setPlaceholderText("https://your-zimra-server.com")
        main_layout.addWidget(self.base_url_edit, 1, 1)
        
        # API Key
        main_layout.addWidget(QLabel("API Key:"), 2, 0)
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        main_layout.addWidget(self.api_key_edit, 2, 1)
        
        # API Secret
        main_layout.addWidget(QLabel("API Secret:"), 3, 0)
        self.api_secret_edit = QLineEdit()
        self.api_secret_edit.setEchoMode(QLineEdit.Password)
        main_layout.addWidget(self.api_secret_edit, 3, 1)
        
        # Device Serial Number
        main_layout.addWidget(QLabel("Device SN:"), 4, 0)
        self.device_sn_edit = QLineEdit()
        self.device_sn_edit.setPlaceholderText("ZIMRA device serial number")
        main_layout.addWidget(self.device_sn_edit, 4, 1)
        
        # Ping Interval
        main_layout.addWidget(QLabel("Ping Interval (minutes):"), 5, 0)
        self.ping_interval_edit = QLineEdit()
        self.ping_interval_edit.setPlaceholderText("5")
        main_layout.addWidget(self.ping_interval_edit, 5, 1)
        
        layout.addWidget(main_group)
        
        # Status group
        status_group = QGroupBox("Device Status")
        status_layout = QVBoxLayout(status_group)
        
        self.status_label = QLabel("Not tested")
        self.status_label.setWordWrap(True)
        status_layout.addWidget(self.status_label)
        
        layout.addWidget(status_group)
        
        # Progress bar for testing
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        layout.addWidget(self.progress_bar)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.test_btn = QPushButton("Test Connection")
        self.test_btn.setIcon(qta.icon("fa5s.plug"))
        self.test_btn.clicked.connect(self._test_connection)
        self.test_btn.setMinimumHeight(40)
        
        self.save_btn = QPushButton("Save Settings")
        self.save_btn.setIcon(qta.icon("fa5s.save"))
        self.save_btn.clicked.connect(self._save_settings)
        self.save_btn.setMinimumHeight(40)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.cancel_btn.setMinimumHeight(40)
        
        btn_layout.addWidget(self.test_btn)
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(btn_layout)
        
        # Help text
        help_label = QLabel(
            "Note: You must test the connection before saving settings.\n"
            "The device must be registered with ZIMRA first."
        )
        help_label.setStyleSheet("color: gray; font-size: 10px;")
        help_label.setWordWrap(True)
        layout.addWidget(help_label)
    
    def _load_settings(self):
        """Load settings into UI"""
        self.enable_check.setChecked(self.settings.enabled)
        self.base_url_edit.setText(self.settings.base_url)
        self.api_key_edit.setText(self.settings.api_key)
        self.api_secret_edit.setText(self.settings.api_secret)
        self.device_sn_edit.setText(self.settings.device_sn)
        self.ping_interval_edit.setText(str(self.settings.ping_interval_minutes))
        
        # Update status based on device status
        if self.settings.device_status == "online":
            self.status_label.setText(
                f"Device Online\n"
                f"Last ping: {self.settings.last_ping_time or 'Never'}\n"
                f"Reporting frequency: {self.settings.reporting_frequency or 'N/A'} min"
            )
            self.status_label.setStyleSheet("color: green;")
        elif self.settings.device_status == "offline":
            self.status_label.setText("Device Offline - Last connection failed")
            self.status_label.setStyleSheet("color: orange;")
        elif self.settings.device_status == "error":
            self.status_label.setText("Connection Error - Check network and credentials")
            self.status_label.setStyleSheet("color: red;")
        else:
            self.status_label.setText("Status unknown - Test connection to verify")
            self.status_label.setStyleSheet("color: gray;")
    
    def _test_connection(self):
        """Test connection to ZIMRA"""
        # Build settings from UI
        test_settings = FiscalSettings(
            enabled=self.enable_check.isChecked(),
            base_url=self.base_url_edit.text().strip(),
            api_key=self.api_key_edit.text().strip(),
            api_secret=self.api_secret_edit.text().strip(),
            device_sn=self.device_sn_edit.text().strip(),
            ping_interval_minutes=int(self.ping_interval_edit.text() or 5),
        )
        
        # Validate required fields
        if not test_settings.base_url:
            QMessageBox.warning(self, "Missing Field", "Please enter the Base URL")
            return
        if not test_settings.api_key:
            QMessageBox.warning(self, "Missing Field", "Please enter the API Key")
            return
        if not test_settings.api_secret:
            QMessageBox.warning(self, "Missing Field", "Please enter the API Secret")
            return
        if not test_settings.device_sn:
            QMessageBox.warning(self, "Missing Field", "Please enter the Device SN")
            return
        
        # Disable buttons during test
        self.test_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Testing connection...")
        self.status_label.setStyleSheet("color: blue;")
        
        # Start test thread
        self._test_thread = TestConnectionThread(test_settings)
        self._test_thread.finished_signal.connect(self._on_test_finished)
        self._test_thread.start()
    
    def _on_test_finished(self, success: bool, message: str):
        """Handle test connection result"""
        self.test_btn.setEnabled(True)
        self.save_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        if success:
            self.status_label.setText(f"{message}")
            self.status_label.setStyleSheet("color: green;")
            
            # Store the settings that worked (but don't save to DB yet)
            self._tested_settings = FiscalSettings(
                enabled=self.enable_check.isChecked(),
                base_url=self.base_url_edit.text().strip(),
                api_key=self.api_key_edit.text().strip(),
                api_secret=self.api_secret_edit.text().strip(),
                device_sn=self.device_sn_edit.text().strip(),
                ping_interval_minutes=int(self.ping_interval_edit.text() or 5),
                device_status="online",
            )
            
            QMessageBox.information(
                self, 
                "Connection Successful", 
                f"Successfully connected to ZIMRA!\n\n{message}\n\nYou can now save these settings."
            )
        else:
            self.status_label.setText(f"{message}")
            self.status_label.setStyleSheet("color: red;")
            
            QMessageBox.warning(
                self, 
                "Connection Failed", 
                f"Could not connect to ZIMRA:\n\n{message}\n\nPlease check your settings and try again."
            )
    
    def _save_settings(self):
        """Save settings to database"""
        # Check if we have a successful test first
        if not hasattr(self, '_tested_settings') or self._tested_settings is None:
            QMessageBox.warning(
                self,
                "Test Required",
                "You must test the connection successfully before saving settings.\n\n"
                "Click 'Test Connection' first."
            )
            return
        
        # Update settings with current UI values
        self.settings.enabled = self.enable_check.isChecked()
        self.settings.base_url = self._tested_settings.base_url
        self.settings.api_key = self._tested_settings.api_key
        self.settings.api_secret = self._tested_settings.api_secret
        self.settings.device_sn = self._tested_settings.device_sn
        self.settings.ping_interval_minutes = self._tested_settings.ping_interval_minutes
        self.settings.device_status = self._tested_settings.device_status
        
        # Save to database
        self.settings_repo.save_settings(self.settings)
        
        # Restart device monitor if needed
        if self.settings.enabled:
            from services.fiscal_device_monitor import get_device_monitor_service
            monitor = get_device_monitor_service()
            monitor.restart_monitoring()
        
        QMessageBox.information(self, "Saved", "Fiscalization settings saved successfully!")
        self.accept()