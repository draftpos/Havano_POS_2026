# models/sql_settings.py
from dataclasses import dataclass
from pathlib import Path
import json

@dataclass
class SQLSettings:
    auth_mode: str = "Windows"      # "Windows" or "SQL"
    server: str = "."
    database: str = "POS_DB"
    username: str = ""
    password: str = ""

    # API Settings
    api_url: str = ""
    api_token: str = ""
    api_key: str = ""
    api_secret: str = ""

    @classmethod
    def load(cls):
        path = Path("app_data/sql_settings.json")
        if not path.exists():
            default = cls()
            default.save()
            return default

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})
        except:
            default = cls()
            default.save()
            return default

    def save(self):
        Path("app_data").mkdir(exist_ok=True)
        data = {
            "auth_mode": self.auth_mode,
            "server": self.server,
            "database": self.database,
            "username": self.username,
            "password": self.password,
            "api_url": self.api_url,
            "api_token": self.api_token,
            "api_key": self.api_key,
            "api_secret": self.api_secret,
        }
        with open("app_data/sql_settings.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)