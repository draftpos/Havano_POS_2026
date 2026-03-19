# models/advance_settings.py
from dataclasses import dataclass, asdict, field
from typing import Optional
import json
from pathlib import Path

@dataclass
class AdvanceSettings:
    """
    Advanced printing & font settings.
    Exact mirror of your C# AdvanceSettings.cs (including persistent LogoDirectory)
    """

    # Font settings
    contentFontName: str = "Arial"
    contentFontSize: int = 10
    contentFontStyle: str = "Regular"

    contentHeaderFontName: str = "Arial"
    contentHeaderSize: int = 11
    contentHeaderStyle: str = "Bold"

    subheaderFontName: str = "Times New Roman"
    subheaderSize: int = 10
    subheaderStyle: str = "Bold"

    orderContentFontName: str = "Arial"
    orderContentFontSize: int = 10
    orderContentStyle: str = "Bold"

    # ── NEW: Persistent Logo Directory (exactly like C#) ──
    logoDirectory: str = ""          # empty = first run → will prompt later

    # Other settings
    charactersPerLine: int = 48

    @classmethod
    def load_from_file(cls, file_path: str = "settings/advance_settings.json") -> "AdvanceSettings":
        """Load from JSON (same behavior as C# LoadFromFile)"""
        settings = cls()  # start with defaults

        path = Path(file_path)
        if not path.exists():
            # First run → create folder and save defaults
            path.parent.mkdir(parents=True, exist_ok=True)
            settings.save_to_file(file_path)
            return settings

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Update only existing fields (safe merge)
            for key, value in data.items():
                if hasattr(settings, key) and value is not None:
                    if key in ("contentFontSize", "contentHeaderSize", "subheaderSize", "orderContentFontSize"):
                        if value > 0:
                            setattr(settings, key, int(value))
                    else:
                        setattr(settings, key, value)

        except Exception as e:
            print(f"[AdvanceSettings] Load error: {e} — using defaults")

        return settings

    def save_to_file(self, file_path: str = "settings/advance_settings.json") -> None:
        """Save to JSON (same as C# SaveToFile)"""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = asdict(self)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        print(f"[LOGO] Settings saved → LogoDirectory = {self.logoDirectory}")

    def to_dict(self) -> dict:
        """For easy use in printing logic"""
        return asdict(self)