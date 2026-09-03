# =============================================================================
# utils/title_bar.py - Havano POS Custom Title Bar & Window Decoration
# =============================================================================

import sys
import ctypes
from PySide6.QtCore import QObject, QEvent

# Windows DWM Constants
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36

def _set_window_title_bar_color(hwnd, color_hex="#1a5fb4", text_color_hex="#ffffff"):
    """Applies Havano Blue title bar caption and white text color on Windows 10/11."""
    if sys.platform != "win32":
        return
    try:
        def hex_to_bgr(h):
            h = h.lstrip("#")
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            return (b << 16) | (g << 8) | r

        caption_bgr = hex_to_bgr(color_hex)
        text_bgr = hex_to_bgr(text_color_hex)

        dwmapi = ctypes.windll.dwmapi
        dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_CAPTION_COLOR,
            ctypes.byref(ctypes.c_uint32(caption_bgr)),
            ctypes.sizeof(ctypes.c_uint32)
        )
        dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_TEXT_COLOR,
            ctypes.byref(ctypes.c_uint32(text_bgr)),
            ctypes.sizeof(ctypes.c_uint32)
        )
    except Exception:
        pass


class _TitleBarEventFilter(QObject):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self._processing = set()
        self._in_filter = False

    def eventFilter(self, obj, event):
        from PySide6.QtWidgets import QWidget
        from PySide6.QtCore import Qt
        if getattr(self, "_in_filter", False):
            ret = super().eventFilter(obj, event)
            return bool(ret) if ret is not None else False
        self._in_filter = True
        try:
            if event.type() == QEvent.Show and isinstance(obj, QWidget):
                obj_id = id(obj)
                if obj.isWindow() and obj_id not in self._processing:
                    if not (obj.windowFlags() & Qt.FramelessWindowHint):
                        self._processing.add(obj_id)
                        try:
                            hwnd = int(obj.winId())
                        _set_window_title_bar_color(hwnd, "#1a5fb4", "#ffffff")
                    except Exception:
                        pass
                    finally:
                        self._processing.discard(obj_id)
        finally:
            self._in_filter = False
        ret = super().eventFilter(obj, event)
        return bool(ret) if ret is not None else False


def install_global_title_bar_hook(app):
    """Installs global Havano Blue title bar hook for all windows and dialogs."""
    try:
        app._title_bar_filter = _TitleBarEventFilter(app)
        app.installEventFilter(app._title_bar_filter)
    except Exception as e:
        print(f"[title_bar] Failed to install title bar hook: {e}")
