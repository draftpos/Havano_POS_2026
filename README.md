# Havano POS 2026

## Font Resilience & Self-Healing Architecture (`utils/icon_utils.py`)

Havano POS includes an automated font integrity, self-healing, and call-site fallback subsystem to ensure that antivirus quarantine, file transfer glitches, or 0-byte font corruption on customer Windows machines never cause an application crash or present cryptic "Critical Error" dialogs to non-technical store staff.

### How It Works:

1. **Pre-Flight Startup Integrity Verification**:
   - `verify_and_heal_fonts()` runs early in `main.py` before any UI component or QtAwesome font is initialized.
   - It checks all `.ttf` font files in both the runtime `qtawesome/fonts/` directory and Windows `%LOCALAPPDATA%\Microsoft\Windows\Fonts\`.
   - Any font file missing or under **10KB (10,240 bytes)** is flagged as corrupted.

2. **Automatic Self-Healing**:
   - Clean, read-only backup copies of all QtAwesome font files (`.ttf` and `.json`) are bundled inside `assets/fonts_backup/`.
   - If a corrupted or 0-byte font is detected, the self-healing engine automatically deletes the corrupted stub and re-copies the valid font file from `assets/fonts_backup/`.
   - Detailed diagnostics (file paths, timestamp, expected vs actual file sizes, self-heal outcome) are logged to `app_data/font_integrity.log`.

3. **Graceful Degraded UI Fallback Mode**:
   - If self-healing fails (e.g. strict system permissions block font file replacement), the app sets `QTA_DISABLED = True`.
   - The application **does not crash**. Instead, it operates in degraded UI mode, rendering plain text labels or fallback icons while allowing store staff to continue processing sales.

4. **Call-Site Exception Guard (`safe_icon` & `safe_pixmap`)**:
   - `utils/icon_utils.py` provides `safe_icon(name, color=None, fallback=None, **kwargs)` and `safe_pixmap(name, width=16, height=16, color=None, fallback=None)`.
   - All `qtawesome` calls wrapped in `safe_icon` handle any runtime font or rendering exceptions gracefully at the call site, returning `fallback` or a blank `QIcon()` without raising exceptions.
