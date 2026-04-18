# views/dialogs/external_quotation_settings_dialog.py
# =============================================================================
# Settings dialog for fetching quotations from a SEPARATE external Frappe site.
# Stores: site URL, API key, API secret  →  app_data/xtrnal_qt_site_config.json
# =============================================================================

import sys
import json
import urllib.request
import urllib.error
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QMessageBox, QApplication
)
from PySide6.QtCore import Qt
import qtawesome as qta


# ---------------------------------------------------------------------------
# Path helpers — exe-safe, same logic as db.py
# ---------------------------------------------------------------------------

def _get_xtrnal_app_data_folder() -> Path:
    """Get the app_data folder path - unique name to avoid conflicts"""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys.executable).parent / "app_data"
    # Three levels up from views/dialogs/ → project root
    return Path(__file__).resolve().parent.parent.parent / "app_data"


# Unique file name that won't conflict with anything
XT_RNAL_SETTINGS_FILE = _get_xtrnal_app_data_folder() / "xtrnal_qt_site_config.json"


# ---------------------------------------------------------------------------
# Public helpers — used by external_quotation_service.py too
# ---------------------------------------------------------------------------

def load_xtrnal_site_config() -> dict:
    """Load external site credentials from disk. Returns defaults if not set."""
    try:
        if XT_RNAL_SETTINGS_FILE.exists():
            return json.loads(XT_RNAL_SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[XtrnalSiteConfig] Could not load config: {e}")
    return {"xtrnal_site_url": "", "xtrnal_api_key": "", "xtrnal_api_secret": ""}


def save_xtrnal_site_config(config_data: dict) -> None:
    """Persist external site credentials to disk."""
    _get_xtrnal_app_data_folder().mkdir(exist_ok=True)
    XT_RNAL_SETTINGS_FILE.write_text(json.dumps(config_data, indent=2), encoding="utf-8")
    print(f"[XtrnalSiteConfig] Saved config to {XT_RNAL_SETTINGS_FILE}")


def test_xtrnal_site_connection(site_url: str, api_key_str: str, api_secret_str: str) -> tuple[bool, str]:
    """
    Quick connectivity test — hits /api/method/frappe.auth.get_logged_user.
    Returns (success: bool, message: str).
    """
    if not site_url or not api_key_str or not api_secret_str:
        return False, "All fields are required."

    site_url = site_url.strip().rstrip("/")
    test_endpoint = f"{site_url}/api/method/frappe.auth.get_logged_user"
    print(f"[XtrnalSiteConfig] Testing connection: {test_endpoint}")

    try:
        web_request = urllib.request.Request(test_endpoint)
        web_request.add_header("Authorization", f"token {api_key_str}:{api_secret_str}")
        web_request.add_header("Accept", "application/json")

        with urllib.request.urlopen(web_request, timeout=8) as response:
            response_data = json.loads(response.read().decode())
            logged_user = response_data.get("message", "unknown user")
            print(f"[XtrnalSiteConfig] ✅ Connected as: {logged_user}")
            return True, f"Connected as: {logged_user}"

    except urllib.error.HTTPError as http_err:
        try:
            error_body = http_err.read().decode("utf-8", errors="replace")
        except Exception:
            error_body = ""
        print(f"[XtrnalSiteConfig] ❌ HTTP {http_err.code}: {error_body[:200]}")
        if http_err.code == 401:
            return False, "Invalid API key / secret (401 Unauthorized)."
        if http_err.code == 403:
            return False, "Access denied — check API key permissions (403 Forbidden)."
        if http_err.code == 404:
            return False, f"URL not found (404) — is the site URL correct?\n{test_endpoint}"
        return False, f"HTTP {http_err.code}: {error_body[:150]}"

    except urllib.error.URLError as url_err:
        print(f"[XtrnalSiteConfig] ❌ URLError: {url_err.reason}")
        return False, f"Cannot reach site: {url_err.reason}"

    except Exception as unexpected_err:
        print(f"[XtrnalSiteConfig] ❌ Unexpected: {unexpected_err}")
        return False, str(unexpected_err)


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

class ExternalQuotationSettingsDialog(QDialog):
    """
    Settings popup where the user enters the external Frappe site
    URL, API key and API secret used to pull quotations from a second site.
    """

    def __init__(self, parent_widget=None):
        super().__init__(parent_widget)
        self.setWindowTitle("External Quotation Source — Configuration")
        self.setMinimumWidth(500)
        self.setModal(True)
        self._setup_dialog_ui()
        self._load_existing_config()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _setup_dialog_ui(self):
        self.setStyleSheet("""
            QDialog   { background: #f7f7f7; }
            QLabel    { color: #333; font-size: 13px; }
            QLineEdit {
                background: white; color: #333;
                border: 1px solid #ccc; border-radius: 6px;
                padding: 8px 10px; font-size: 13px;
            }
            QLineEdit:focus { border: 2px solid #2196F3; }
            QPushButton {
                border: none; border-radius: 6px;
                padding: 9px 20px; font-size: 13px; font-weight: 600;
            }
            QPushButton#saveConfigBtn   { background: #2196F3; color: white; }
            QPushButton#saveConfigBtn:hover   { background: #1976D2; }
            QPushButton#testConnectionBtn   { background: #28a745; color: white; }
            QPushButton#testConnectionBtn:hover   { background: #218838; }
            QPushButton#cancelDialogBtn { background: #6c757d; color: white; }
            QPushButton#cancelDialogBtn:hover { background: #5a6268; }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(14)
        main_layout.setContentsMargins(24, 20, 24, 20)

        # Title
        title_label = QLabel("External Quotation Source")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2196F3;")
        main_layout.addWidget(title_label)

        # Separator
        separator_line = QFrame()
        separator_line.setFrameShape(QFrame.HLine)
        separator_line.setStyleSheet("color: #ddd;")
        main_layout.addWidget(separator_line)

        # Hint
        info_hint = QLabel(
            "Enter the credentials for the <b>external</b> site you want to pull "
            "quotations from.\nThese are stored locally in <i>app_data/xtrnal_qt_site_config.json</i>."
        )
        info_hint.setWordWrap(True)
        info_hint.setStyleSheet("color: #555; font-size: 12px;")
        main_layout.addWidget(info_hint)

        # Fields
        def _add_config_field(field_label_text, input_widget):
            field_label = QLabel(field_label_text)
            field_label.setStyleSheet("font-weight: 600; margin-top: 4px;")
            main_layout.addWidget(field_label)
            main_layout.addWidget(input_widget)

        self.site_url_input = QLineEdit()
        self.site_url_input.setPlaceholderText("https://external-site.example.com")
        _add_config_field("External Site URL", self.site_url_input)

        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("API Key from external site")
        _add_config_field("API Key", self.api_key_input)

        self.api_secret_input = QLineEdit()
        self.api_secret_input.setPlaceholderText("API Secret from external site")
        self.api_secret_input.setEchoMode(QLineEdit.Password)
        _add_config_field("API Secret", self.api_secret_input)

        # Status label
        self.connection_status_label = QLabel("")
        self.connection_status_label.setWordWrap(True)
        self.connection_status_label.setMinimumHeight(20)
        self.connection_status_label.setStyleSheet("font-size: 12px; color: #555;")
        main_layout.addWidget(self.connection_status_label)

        # Buttons
        button_row = QHBoxLayout()
        button_row.setSpacing(10)

        self.test_connection_btn = QPushButton("Test Connection")
        self.test_connection_btn.setIcon(qta.icon("fa5s.link"))
        self.test_connection_btn.setObjectName("testConnectionBtn")
        self.test_connection_btn.clicked.connect(self._test_xtrnal_connection)

        self.save_config_btn = QPushButton("Save Configuration")
        self.save_config_btn.setIcon(qta.icon("fa5s.save"))
        self.save_config_btn.setObjectName("saveConfigBtn")
        self.save_config_btn.clicked.connect(self._save_xtrnal_config)

        cancel_dialog_btn = QPushButton("Cancel")
        cancel_dialog_btn.setObjectName("cancelDialogBtn")
        cancel_dialog_btn.clicked.connect(self.reject)

        button_row.addWidget(self.test_connection_btn)
        button_row.addStretch()
        button_row.addWidget(cancel_dialog_btn)
        button_row.addWidget(self.save_config_btn)
        main_layout.addLayout(button_row)

    # ------------------------------------------------------------------
    # Logic
    # ------------------------------------------------------------------

    def _load_existing_config(self):
        saved_config = load_xtrnal_site_config()
        self.site_url_input.setText(saved_config.get("xtrnal_site_url", ""))
        self.api_key_input.setText(saved_config.get("xtrnal_api_key", ""))
        self.api_secret_input.setText(saved_config.get("xtrnal_api_secret", ""))

    def _test_xtrnal_connection(self):
        self.connection_status_label.setText("Testing connection…")
        self.connection_status_label.setStyleSheet("font-size: 12px; color: #555;")
        QApplication.processEvents()

        connection_ok, status_message = test_xtrnal_site_connection(
            self.site_url_input.text().strip(),
            self.api_key_input.text().strip(),
            self.api_secret_input.text().strip(),
        )
        
        if connection_ok:
            self.connection_status_label.setText(f"{status_message}")
            self.connection_status_label.setStyleSheet("font-size: 12px; color: #28a745; font-weight: 600;")
        else:
            self.connection_status_label.setText(f"{status_message}")
            self.connection_status_label.setStyleSheet("font-size: 12px; color: #dc3545; font-weight: 600;")

    def _save_xtrnal_config(self):
        xtrnal_url = self.site_url_input.text().strip().rstrip("/")
        xtrnal_key = self.api_key_input.text().strip()
        xtrnal_secret = self.api_secret_input.text().strip()

        if not xtrnal_url or not xtrnal_key or not xtrnal_secret:
            QMessageBox.warning(self, "Missing Information", "Please fill in all three fields before saving.")
            return

        config_to_save = {
            "xtrnal_site_url": xtrnal_url,
            "xtrnal_api_key": xtrnal_key,
            "xtrnal_api_secret": xtrnal_secret
        }
        
        save_xtrnal_site_config(config_to_save)
        self.connection_status_label.setText("Configuration saved successfully.")
        self.connection_status_label.setStyleSheet("font-size: 12px; color: #28a745; font-weight: 600;")
        self.accept()