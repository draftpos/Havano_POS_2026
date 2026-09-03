from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
import json
from pathlib import Path
from theme import WHITE, NAVY, SUCCESS, SUCCESS_H, MUTED, LIGHT
from more import navy_btn, hr

_CAT_SETTINGS_FILE = Path("app_data/category_settings.json")

def load_category_settings() -> dict:
    if not _CAT_SETTINGS_FILE.exists():
        return {}
    try:
        return json.loads(_CAT_SETTINGS_FILE.read_text(encoding="utf-8"))
    except:
        return {}

def load_disabled_categories() -> list:
    return load_category_settings().get("disabled_categories", [])

def load_negative_stock_categories() -> list:
    return load_category_settings().get("negative_stock_categories", [])

def save_category_settings(disabled: list, negative_stock: list) -> None:
    try:
        _CAT_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = load_category_settings()
        data["disabled_categories"] = disabled
        data["negative_stock_categories"] = negative_stock
        _CAT_SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except: pass

class CategoryVisibilityDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Category Visibility")
        self.setMinimumSize(540, 600)
        self.setModal(True)
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)
        self.setStyleSheet(f"QDialog {{ background-color:{WHITE}; }}")
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)
        self.content = _CategoryVisibilityWidget(self)
        main_lay.addWidget(self.content)

class _CategoryVisibilityWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background:{WHITE};")
        self._checks: dict = {}
        self._zero_checks: dict = {}
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(16)
        lay.setContentsMargins(30, 15, 30, 25)

        header_lay = QHBoxLayout()
        title = QLabel("Category Visibility")
        title.setStyleSheet(f"font-size:20px; font-weight:bold; color:{NAVY};")
        save_btn = navy_btn("Save Settings", height=34, color=SUCCESS, hover=SUCCESS_H)
        save_btn.clicked.connect(self._save)
        header_lay.addWidget(title)
        header_lay.addStretch()
        header_lay.addWidget(save_btn)
        lay.addLayout(header_lay)
        lay.addWidget(hr())

        info = QLabel(
            "Manage category visibility for this branch. "
            "Unticked visibility means the category is hidden. "
            "Ticked 'Allow Zero Stock' means items in this category can be sold even when stock is 0."
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color:{MUTED}; font-size:12px; background:{LIGHT}; border:none; border-radius:6px; padding:10px 14px;")
        lay.addWidget(info)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"QScrollArea {{ border:none; border-radius:8px; background:{WHITE}; }}")

        chk_container = QWidget()
        chk_container.setStyleSheet(f"background:{WHITE};")
        chk_lay = QVBoxLayout(chk_container)
        chk_lay.setSpacing(4)
        chk_lay.setContentsMargins(15, 15, 15, 15)

        all_cats = []
        try:
            from models.product import get_categories
            all_cats = get_categories()
        except: pass

        disabled_now = set(load_disabled_categories())
        negative_now = set(load_negative_stock_categories())

        if not all_cats:
            no_lbl = QLabel("No categories found.")
            no_lbl.setStyleSheet(f"color:{MUTED}; font-size:13px;")
            chk_lay.addWidget(no_lbl)
        else:
            for cat in sorted(all_cats, key=str.lower):
                row_widget = QWidget()
                row_lay = QHBoxLayout(row_widget)
                row_lay.setContentsMargins(0, 0, 0, 0)
                
                chk = QCheckBox(cat)
                chk.setChecked(cat not in disabled_now)
                
                zero_chk = QCheckBox("Allow Zero Stock")
                zero_chk.setChecked(cat in negative_now)
                
                row_lay.addWidget(chk)
                row_lay.addStretch()
                row_lay.addWidget(zero_chk)
                
                chk_lay.addWidget(row_widget)
                
                self._checks[cat] = chk
                self._zero_checks[cat] = zero_chk

        chk_lay.addStretch()
        scroll.setWidget(chk_container)
        lay.addWidget(scroll, 1)

    def _save(self):
        disabled = [name for name, chk in self._checks.items() if not chk.isChecked()]
        negative = [name for name, chk in self._zero_checks.items() if chk.isChecked()]
        save_category_settings(disabled, negative)
        QMessageBox.information(self, "Saved", "Category Settings updated.\n\nRestart the POS screen to apply changes.")
