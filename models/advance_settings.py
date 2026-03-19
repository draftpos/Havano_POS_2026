# models/advance_settings.py
from dataclasses import dataclass, asdict, field
from typing import Optional
import json
from pathlib import Path

@dataclass
class AdvanceSettings:
    """
    Advanced printing & font settings.
    Exact mirror of your C# AdvanceSettings.cs + new receipt layout options
    """

    # Font settings (unchanged)
    contentFontName: str = "Arial"
    contentFontSize: int = 8
    contentFontStyle: str = "Regular"

    contentHeaderFontName: str = "Arial"
    contentHeaderSize: int = 10
    contentHeaderStyle: str = "Bold"

    subheaderFontName: str = "Times New Roman"
    subheaderSize: int = 19
    subheaderStyle: str = "italic"

    orderContentFontName: str = "Arial"
    orderContentFontSize: int = 10
    orderContentStyle: str = "Bold"

    # Logo
    logoDirectory: str = ""

    # Other settings
    charactersPerLine: int = 48

    # ── NEW RECEIPT LAYOUT CHECKBOXES ──
    showSubtotalExclusive: bool = True      # Show Subtotal line (exclusive of VAT)
    showInclusive: bool = False             # Show Inclusive VAT total
    showDescriptionLabel: bool = True       # Show "Description" / product name label
    showPayment: bool = True                # Show Paid / Change / Payment Mode

    @classmethod
    def load_from_file(cls, file_path: str = "settings/advance_settings.json") -> "AdvanceSettings":
        settings = cls()
        path = Path(file_path)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            settings.save_to_file(file_path)
            return settings

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for key, value in data.items():
                if hasattr(settings, key) and value is not None:
                    setattr(settings, key, value)
        except Exception as e:
            print(f"[AdvanceSettings] Load error: {e} — using defaults")

        return settings

    def save_to_file(self, file_path: str = "settings/advance_settings.json") -> None:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"[AdvanceSettings] Saved → LogoDirectory = {self.logoDirectory}")

    def to_dict(self) -> dict:
        return asdict(self)