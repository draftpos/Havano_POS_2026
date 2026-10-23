---
name: canonical-paths
description: Mandatory rule for Havano POS. Every access to app_data files (sql_settings.json, hardware_settings.json, saas_mop_rates.json, print_debug.log, etc.) MUST use database.db.get_app_data_dir(). Never use os.path.abspath("."), os.getcwd(), Path("app_data/..."), or os.path.join("app_data", ...). Must be read before writing or modifying any file I/O code in this project.
---

# Canonical Paths — No Hardcoded File Paths Policy

This skill defines the mandatory rule for resolving all `app_data/` file paths in
the Havano POS codebase. Violating this rule causes files to be read from / written
to the wrong directory when the app is launched via Windows shortcuts, auto-start
entries, or any launcher that does not set the working directory to the project root.

---

## The One Canonical Helper

`.python
from database.db import get_app_data_dir   # always import this

path = get_app_data_dir() / "sql_settings.json"       # correct
path = get_app_data_dir() / "hardware_settings.json"  # correct
path = get_app_data_dir() / "print_debug.log"         # correct
`

`get_app_data_dir()` resolves as follows:

| Runtime | Returns |
|---------|---------|
| Bundled .exe (PyInstaller / sys.frozen) | `Path(sys.executable).parent / "app_data"` |
| Dev (python main.py) | `Path(database/db.py).resolve().parent.parent / "app_data"` |

Always anchored to the executable or source file — never to the process working directory.

---

## Absolute Prohibitions

Never use any of the following patterns to build an `app_data` path:

`.python
# FORBIDDEN — all of these break under Windows shortcuts / launchers
Path("app_data/sql_settings.json")
Path("app_data") / "sql_settings.json"
os.path.join("app_data", "sql_settings.json")
os.path.join(os.path.abspath("."), "app_data", "sql_settings.json")
Path(os.path.abspath(".")) / "app_data" / "sql_settings.json"
Path(os.getcwd()) / "app_data" / "sql_settings.json"

# ALSO FORBIDDEN — private helpers that re-implement the logic
def _app_data_dir():
    if hasattr(sys, "_MEIPASS"):
        return Path(sys.executable).parent / "app_data"
    return Path(os.path.abspath(".")) / "app_data"   # still uses cwd
`

Do NOT create local helpers that duplicate `get_app_data_dir()`. Always import
and call the canonical one.

---

## The Only Legitimate Exception

`database/db.py` itself defines `get_app_data_dir()`. That single definition uses
`Path(__file__).resolve().parent` for dev and `Path(sys.executable).parent` for
frozen builds. No other file may re-implement this logic.

---

## Reading a config file

`.python
from database.db import get_app_data_dir
import json

cfg_path = get_app_data_dir() / "sql_settings.json"
if cfg_path.exists():
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
`

## Writing a config file — always merge, never overwrite

`.python
from database.db import get_app_data_dir
import json

cfg_path = get_app_data_dir() / "sql_settings.json"
cfg_path.parent.mkdir(parents=True, exist_ok=True)

data = {}
if cfg_path.exists():
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        pass
data["my_key"] = "my_value"
cfg_path.write_text(json.dumps(data, indent=4), encoding="utf-8")
`

## Module-level constants — FORBIDDEN

`.python
# WRONG — evaluated at import time with whatever cwd the interpreter has
_SETTINGS_FILE = Path("app_data/sql_settings.json")

# CORRECT — use a function so it resolves at call time
def _settings_path():
    from database.db import get_app_data_dir
    return get_app_data_dir() / "sql_settings.json"
`

---

## Key Files Already Compliant (as of 2026-09-24)

| File | Pattern |
|------|---------|
| `database/db.py` | Source — defines `get_app_data_dir()` |
| `main.py` | `from database.db import get_app_data_dir` |
| `services/credentials.py` | `_get_app_data_dir()` delegates to database.db |
| `services/auth_service.py` | `from database.db import get_app_data_dir` |
| `services/site_config.py` | `from database.db import get_app_data_dir` |
| `services/backup_service.py` | `from database.db import get_app_data_dir` |
| `services/saas_mop_rates.py` | `_app_data_dir()` delegates to database.db |
| `models/saas_snapshot.py` | `from database.db import get_app_data_dir` |
| `views/dialogs/sql_settings_dialog.py` | `from database.db import get_app_data_dir` |
| `views/dialogs/dining_option_dialog.py` | `_settings_file()` delegates to database.db |
| `views/dialogs/credit_notes_list_dialog.py` | `from database.db import get_app_data_dir` |
| `views/dialogs/saas_assignment_handler.py` | `from database.db import get_app_data_dir` |
| `views/login_dialog.py` | `from database.db import get_app_data_dir` |
| `views/main_window.py` | `from database.db import get_app_data_dir` |
| `services/printing_service.py` | `_get_app_data_dir()` delegates to database.db |

---

## Pre-Write Checklist

Before writing or reviewing ANY file I/O code in this project, confirm:

- [ ] No `Path("app_data/...")` anywhere in the new/changed code
- [ ] No `os.path.join("app_data", ...)` anywhere
- [ ] No `os.path.abspath(".")` used to build a data path
- [ ] No private helper duplicating `get_app_data_dir()` logic
- [ ] Writes merge into existing JSON, never overwrite the full file
- [ ] `system_mode` key is always preserved when saving `sql_settings.json`
