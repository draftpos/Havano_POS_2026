# =============================================================================
# views/components/blur_overlay.py
# Reusable background blur and dimming overlay for modal dialogs & QMessageBoxes in Havano POS
# =============================================================================

from __future__ import annotations
import logging
from PySide6.QtWidgets import (
    QWidget, QLabel, QGraphicsBlurEffect, QDialog, QMessageBox, QApplication
)
from PySide6.QtCore import Qt, QEvent, QObject

log = logging.getLogger("BlurOverlay")

DEFAULT_BLUR_RADIUS: int = 7
DEFAULT_TINT_RGBA: str = "rgba(15, 23, 42, 25)"

_global_blur_radius: int = DEFAULT_BLUR_RADIUS
_global_tint_rgba: str = DEFAULT_TINT_RGBA


class BlurOverlay(QWidget):
    """
    Frosted glass blur and dim overlay for in-window modal dialogs.
    Grabs the target window canvas, applies a smooth QGraphicsBlurEffect,
    and adds a modern translucent dark tint over the window content.
    """

    def __init__(self, target_window: QWidget, blur_radius: int = DEFAULT_BLUR_RADIUS, tint_rgba: str = DEFAULT_TINT_RGBA):
        # Host on centralWidget if target is a QMainWindow so the overlay sits in front of all views
        host = target_window
        if hasattr(target_window, "centralWidget") and target_window.centralWidget():
            host = target_window.centralWidget()

        super().__init__(host)
        self.target_window = target_window
        self.host_widget = host
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setGeometry(host.rect())

        # Background snapshot label
        self._bg_label = QLabel(self)
        self._bg_label.setScaledContents(True)
        self._bg_label.setGeometry(self.rect())
        try:
            pix = target_window.grab()
            if pix and not pix.isNull():
                self._bg_label.setPixmap(pix)
        except Exception as e:
            log.debug("Failed grabbing window pixmap for blur: %s", e)

        # Blur effect
        self._blur_effect = QGraphicsBlurEffect(self)
        self._blur_effect.setBlurRadius(blur_radius)
        self._bg_label.setGraphicsEffect(self._blur_effect)

        # Translucent dark tint
        self._tint = QWidget(self)
        self._tint.setStyleSheet(f"background-color: {tint_rgba};")
        self._tint.setGeometry(self.rect())

        # Track resize events
        self.host_widget.installEventFilter(self)
        if self.host_widget != self.target_window:
            self.target_window.installEventFilter(self)

        self.show()
        self.raise_()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() in (QEvent.Resize, QEvent.LayoutRequest):
            r = self.host_widget.rect()
            self.setGeometry(r)
            self._bg_label.setGeometry(self.rect())
            self._tint.setGeometry(self.rect())
        return super().eventFilter(watched, event)

    def remove(self):
        try:
            if self.host_widget:
                self.host_widget.removeEventFilter(self)
            if self.target_window and self.target_window != self.host_widget:
                self.target_window.removeEventFilter(self)
            self.hide()
            self.deleteLater()
        except Exception:
            pass


class FullscreenBlurBackdrop(QWidget):
    """
    A full-screen frosted glass blur and dim backdrop for standalone top-level
    dialogs (like LoginDialog on startup or lock screen).
    """

    def __init__(self, target_dialog: QDialog, blur_radius: int = DEFAULT_BLUR_RADIUS, tint_rgba: str = DEFAULT_TINT_RGBA):
        super().__init__(None)
        self.target_dialog = target_dialog
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)

        screen = QApplication.primaryScreen()
        screen_geo = screen.geometry() if screen else target_dialog.geometry()
        self.setGeometry(screen_geo)

        # Background snapshot label
        self._bg_label = QLabel(self)
        self._bg_label.setGeometry(self.rect())

        try:
            if screen:
                pix = screen.grabWindow(0)
                if pix and not pix.isNull():
                    self._bg_label.setPixmap(pix)
                    self._bg_label.setScaledContents(True)
        except Exception as e:
            log.debug("Failed grabbing desktop screen for blur: %s", e)

        # Blur effect
        self._blur_effect = QGraphicsBlurEffect(self)
        self._blur_effect.setBlurRadius(blur_radius)
        self._bg_label.setGraphicsEffect(self._blur_effect)

        # Translucent dark tint layer
        self._tint = QWidget(self)
        self._tint.setStyleSheet(f"background-color: {tint_rgba};")
        self._tint.setGeometry(self.rect())

        self.show()
        self.raise_()
        if self.target_dialog:
            self.target_dialog.raise_()
            self.target_dialog.activateWindow()

    def remove(self):
        try:
            self.hide()
            self.deleteLater()
        except Exception:
            pass


class BlurredDialog(QDialog):
    """
    Base QDialog class that automatically blurs and dims the background
    (either the parent window or full desktop) when displayed, and cleans up when closed.
    """

    def __init__(self, parent=None, blur_radius: int = DEFAULT_BLUR_RADIUS, tint_rgba: str = DEFAULT_TINT_RGBA):
        super().__init__(parent)
        self._blur_radius = blur_radius
        self._tint_rgba = tint_rgba
        self._blur_overlay: BlurOverlay | FullscreenBlurBackdrop | None = None

    def _resolve_target_window(self) -> QWidget | None:
        p = self.parent()
        if p and hasattr(p, "window"):
            w = p.window()
            if w and w != self and w.isVisible():
                return w
        for top in QApplication.topLevelWidgets():
            if top.isVisible() and top != self and not isinstance(top, QDialog):
                return top
        return None

    def showEvent(self, event):
        super().showEvent(event)
        self._show_blur()

    def hideEvent(self, event):
        self._hide_blur()
        super().hideEvent(event)

    def closeEvent(self, event):
        self._hide_blur()
        super().closeEvent(event)

    def done(self, r):
        self._hide_blur()
        super().done(r)

    def _show_blur(self):
        if self._blur_overlay is not None:
            return
        target = self._resolve_target_window()
        try:
            if target:
                self._blur_overlay = BlurOverlay(target, blur_radius=self._blur_radius, tint_rgba=self._tint_rgba)
            else:
                self._blur_overlay = FullscreenBlurBackdrop(self, blur_radius=self._blur_radius, tint_rgba=self._tint_rgba)
            self.raise_()
            self.activateWindow()
        except Exception as e:
            log.debug("Could not display blur overlay: %s", e)

    def _hide_blur(self):
        if self._blur_overlay is not None:
            try:
                self._blur_overlay.remove()
            except Exception:
                pass
            self._blur_overlay = None


def _resolve_active_window(parent: QWidget | None = None) -> QWidget | None:
    """Helper to find the best active non-dialog window to blur."""
    if parent and hasattr(parent, "window"):
        w = parent.window()
        if w and w.isVisible() and not isinstance(w, QDialog):
            return w
    for top in QApplication.topLevelWidgets():
        if top.isVisible() and not isinstance(top, QDialog):
            return top
    return None


_active_overlays: dict[QWidget, BlurOverlay] = {}
_is_patched = False


def _patch_dialog_helpers():
    """
    Wrap QMessageBox and QInputDialog static methods and exec() so that ANY
    confirmation, input prompt, warning, question, or alert dialog anywhere
    in the application automatically displays the frosted glass background blur.
    """
    global _is_patched
    if _is_patched:
        return
    _is_patched = True

    # 1. Patch QMessageBox static methods (question, warning, information, critical, about)
    for method_name in ("question", "warning", "information", "critical", "about"):
        if not hasattr(QMessageBox, method_name):
            continue
        orig = getattr(QMessageBox, method_name)

        def make_wrapper(orig_func):
            def wrapped(parent=None, *args, **kwargs):
                target = _resolve_active_window(parent)
                overlay = None
                if target and target not in _active_overlays:
                    try:
                        overlay = BlurOverlay(target, blur_radius=_global_blur_radius, tint_rgba=_global_tint_rgba)
                        _active_overlays[target] = overlay
                    except Exception as e:
                        log.debug("QMessageBox static blur error: %s", e)
                try:
                    return orig_func(parent, *args, **kwargs)
                finally:
                    if overlay and target in _active_overlays:
                        _active_overlays.pop(target, None)
                        overlay.remove()
            return wrapped

        setattr(QMessageBox, method_name, staticmethod(make_wrapper(orig)))

    # 2. Patch instance exec() / exec_() for instantiated QMessageBoxes (e.g. msg = QMessageBox(self); msg.exec())
    for exec_name in ("exec", "exec_"):
        if not hasattr(QMessageBox, exec_name):
            continue
        orig_exec = getattr(QMessageBox, exec_name)

        def make_exec_wrapper(orig_fn):
            def wrapped_exec(self_box, *args, **kwargs):
                target = _resolve_active_window(self_box.parent())
                overlay = None
                if target and target not in _active_overlays:
                    try:
                        overlay = BlurOverlay(target, blur_radius=_global_blur_radius, tint_rgba=_global_tint_rgba)
                        _active_overlays[target] = overlay
                        self_box.raise_()
                        self_box.activateWindow()
                    except Exception as e:
                        log.debug("QMessageBox exec blur error: %s", e)
                try:
                    return orig_fn(self_box, *args, **kwargs)
                finally:
                    if overlay and target in _active_overlays:
                        _active_overlays.pop(target, None)
                        overlay.remove()
            return wrapped_exec

        setattr(QMessageBox, exec_name, make_exec_wrapper(orig_exec))

    # 3. Patch QInputDialog static methods (getText, getDouble, getInt, getItem, getMultiLineText)
    try:
        from PySide6.QtWidgets import QInputDialog
        for input_name in ("getText", "getDouble", "getInt", "getItem", "getMultiLineText"):
            if not hasattr(QInputDialog, input_name):
                continue
            orig_inp = getattr(QInputDialog, input_name)

            def make_input_wrapper(orig_func):
                def wrapped_input(parent=None, *args, **kwargs):
                    target = _resolve_active_window(parent)
                    overlay = None
                    if target and target not in _active_overlays:
                        try:
                            overlay = BlurOverlay(target, blur_radius=_global_blur_radius, tint_rgba=_global_tint_rgba)
                            _active_overlays[target] = overlay
                        except Exception as e:
                            log.debug("QInputDialog static blur error: %s", e)
                    try:
                        return orig_func(parent, *args, **kwargs)
                    finally:
                        if overlay and target in _active_overlays:
                            _active_overlays.pop(target, None)
                            overlay.remove()
                return wrapped_input

            setattr(QInputDialog, input_name, staticmethod(make_input_wrapper(orig_inp)))

        for exec_name in ("exec", "exec_"):
            if not hasattr(QInputDialog, exec_name):
                continue
            orig_inp_exec = getattr(QInputDialog, exec_name)

            def make_inp_exec_wrapper(orig_fn):
                def wrapped_inp_exec(self_inp, *args, **kwargs):
                    target = _resolve_active_window(self_inp.parent())
                    overlay = None
                    if target and target not in _active_overlays:
                        try:
                            overlay = BlurOverlay(target, blur_radius=_global_blur_radius, tint_rgba=_global_tint_rgba)
                            _active_overlays[target] = overlay
                            self_inp.raise_()
                            self_inp.activateWindow()
                        except Exception as e:
                            log.debug("QInputDialog exec blur error: %s", e)
                    try:
                        return orig_fn(self_inp, *args, **kwargs)
                    finally:
                        if overlay and target in _active_overlays:
                            _active_overlays.pop(target, None)
                            overlay.remove()
                return wrapped_inp_exec

            setattr(QInputDialog, exec_name, make_inp_exec_wrapper(orig_inp_exec))
    except Exception as e:
        log.debug("Failed patching QInputDialog: %s", e)


def install_global_dialog_blur(blur_radius: int = DEFAULT_BLUR_RADIUS, tint_rgba: str = DEFAULT_TINT_RGBA):
    """
    Install universal background blur for all dialogs, QMessageBoxes, and QInput dialogs across the app.
    """
    global _global_blur_radius, _global_tint_rgba
    _global_blur_radius = blur_radius
    _global_tint_rgba = tint_rgba
    _patch_dialog_helpers()
    log.info("Universal dialog & prompt blur system installed successfully (radius=%s, tint=%s).", blur_radius, tint_rgba)
