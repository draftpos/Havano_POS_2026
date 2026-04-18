# =============================================================================
# utils/toast.py  —  Lightweight, non-blocking floating toast for the POS
# =============================================================================
#
# A floating QLabel shown over a parent widget. Non-modal, does NOT steal focus
# (uses Qt.ToolTip | Qt.FramelessWindowHint). Auto-fades after duration_ms via
# QTimer.singleShot.
#
# Pharmacy flow uses the "warn" kind when blocking a non-pharmacist cashier
# from adding a pharmacy product to the cart.
# =============================================================================

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QWidget


# Palette mirrors views/main_window.py (NAVY/AMBER/DANGER/SUCCESS constants)
_KIND_STYLE = {
    "warn":    {"bg": "#b06000", "fg": "#ffffff"},
    "error":   {"bg": "#b02020", "fg": "#ffffff"},
    "info":    {"bg": "#0d1f3c", "fg": "#ffffff"},
    "success": {"bg": "#1a7a3c", "fg": "#ffffff"},
}


def show_toast(parent: QWidget, message: str,
               duration_ms: int = 3000, kind: str = "warn") -> QLabel:
    """
    Show a floating toast over `parent` for `duration_ms` milliseconds.
    Returns the QLabel (caller can discard — auto-deletes on timer fire).
    """
    if parent is None:
        return None

    style = _KIND_STYLE.get(kind, _KIND_STYLE["warn"])

    toast = QLabel(message, parent)
    # ToolTip flag keeps it non-focusable; FramelessWindowHint removes the titlebar.
    toast.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint)
    toast.setAttribute(Qt.WA_ShowWithoutActivating, True)
    toast.setWordWrap(True)
    toast.setAlignment(Qt.AlignCenter)
    toast.setStyleSheet(f"""
        QLabel {{
            background-color: {style['bg']};
            color: {style['fg']};
            border-radius: 6px;
            padding: 10px 16px;
            font-size: 12px;
            font-weight: bold;
            border: 1px solid rgba(0,0,0,60);
        }}
    """)
    toast.setMaximumWidth(420)
    toast.adjustSize()

    # Position top-right of the parent (with a small margin)
    try:
        p_rect = parent.rect()
        top_left_global = parent.mapToGlobal(p_rect.topRight())
        x = top_left_global.x() - toast.width() - 20
        y = top_left_global.y() + 60
        toast.move(x, y)
    except Exception:
        # Worst-case: center on primary screen
        pass

    toast.show()
    toast.raise_()
    # Auto-remove after the timer — safe even if parent is destroyed first.
    QTimer.singleShot(max(500, int(duration_ms)), toast.deleteLater)
    return toast
