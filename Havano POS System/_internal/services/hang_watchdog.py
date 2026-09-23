# =============================================================================
# services/hang_watchdog.py
# In-Process UI Freeze & Hang Watchdog for Havano POS
# =============================================================================
"""
Monitors the Qt main GUI thread for unresponsiveness.
If the UI thread freezes for > 5 seconds, it captures the exact line of code /
stacktrace of the main thread, the current screen/page, and tenant details,
and reports it directly to Bugsink as a high-severity hang alert.
"""

from __future__ import annotations

import sys
import time
import socket
import logging
import threading
import traceback
from pathlib import Path
from datetime import datetime
from typing import Optional

from PySide6.QtCore import QObject, Signal, Slot
from services.bugsink_service import (
    capture_message,
    capture_freeze_event,
    add_breadcrumb,
    get_current_page,
)

_logger = logging.getLogger("hang_watchdog")

# Escalating thresholds in seconds to alert on
FREEZE_ALERT_THRESHOLDS = [5.0, 15.0, 30.0, 60.0]


class _HeartbeatHelper(QObject):
    pong_signal = Signal()

    def __init__(self):
        super().__init__()


class HangWatchdog:
    """
    Monitors the main GUI thread. Posts heartbeats onto the Qt event loop.
    If the event loop does not answer within the threshold, a hang alert is
    dispatched to Bugsink with stack trace and tenant/page context.
    """

    def __init__(
        self,
        check_interval_seconds: float = 1.0,
        main_thread_ident: Optional[int] = None,
    ):
        self._check_interval = check_interval_seconds
        self._main_thread_ident = main_thread_ident or threading.main_thread().ident
        self._last_heartbeat_time = time.time()
        self._stop_event = threading.Event()
        self._watchdog_thread: Optional[threading.Thread] = None

        self._qt_helper = _HeartbeatHelper()
        self._qt_helper.pong_signal.connect(self._on_main_thread_pong)

        self._is_frozen = False
        self._freeze_start_time: Optional[float] = None
        self._reported_thresholds: set[float] = set()

    @Slot()
    def _on_main_thread_pong(self):
        """Executed on the Qt main GUI thread whenever it processes events."""
        now = time.time()
        if self._is_frozen and self._freeze_start_time:
            freeze_duration = now - self._freeze_start_time
            current_page = get_current_page()
            _logger.info(f"[Watchdog] UI recovered after {freeze_duration:.1f}s at [{current_page}]")
            add_breadcrumb(
                category="ui_hang",
                message=f"UI Recovered from freeze after {freeze_duration:.1f}s at [{current_page}]",
                level="info",
                data={"hang_duration_seconds": round(freeze_duration, 2), "page": current_page},
            )
            # Send recovery event if it was a severe freeze (>= 5s)
            if freeze_duration >= 5.0:
                capture_message(
                    f"UI Recovered from {freeze_duration:.1f}s Freeze at [{current_page}]",
                    level="info",
                    extra={
                        "hang_duration_seconds": round(freeze_duration, 2),
                        "page": current_page,
                        "recovered_at": datetime.now().isoformat(),
                    },
                    tags={
                        "ui_hang": "recovered",
                        "hang_duration": f"{int(freeze_duration)}s",
                        "page": current_page,
                    },
                )

        self._is_frozen = False
        self._freeze_start_time = None
        self._reported_thresholds.clear()
        self._last_heartbeat_time = now

    def start(self):
        if self._watchdog_thread and self._watchdog_thread.is_alive():
            return
        # Ensure dump directory exists on disk
        try:
            import os
            os.makedirs(r"C:\PosDumps", exist_ok=True)
        except Exception:
            pass
        self._last_heartbeat_time = time.time()
        self._stop_event.clear()
        self._watchdog_thread = threading.Thread(
            target=self._run_watchdog,
            name="UIHangWatchdog",
            daemon=True,
        )
        self._watchdog_thread.start()
        _logger.info("[Watchdog] UI Freeze Watchdog started.")

    def stop(self):
        self._stop_event.set()

    def _get_process_memory_mb(self) -> float:
        try:
            import psutil
            return float(psutil.Process().memory_info().rss) / (1024 * 1024)
        except Exception:
            pass
        return 0.0

    def _run_watchdog(self):
        while not self._stop_event.is_set():
            time.sleep(self._check_interval)

            # Post a ping request to the Qt event loop
            try:
                self._qt_helper.pong_signal.emit()
            except Exception:
                pass

            now = time.time()
            elapsed_since_pong = now - self._last_heartbeat_time

            # Check each threshold (5s, 15s, 30s, 60s)
            for threshold in FREEZE_ALERT_THRESHOLDS:
                if elapsed_since_pong >= threshold and threshold not in self._reported_thresholds:
                    self._reported_thresholds.add(threshold)
                    if not self._is_frozen:
                        self._is_frozen = True
                        self._freeze_start_time = self._last_heartbeat_time

                    self._report_freeze(elapsed_since_pong, threshold)

    def _report_freeze(self, elapsed: float, threshold: float):
        current_page = get_current_page()
        mem_mb = self._get_process_memory_mb()

        # Capture the main thread stacktrace & exact line of code
        frame = sys._current_frames().get(self._main_thread_ident)
        frames_data = []
        exact_code_line = "Unknown"
        blocked_file = "Unknown"
        blocked_lineno = 0
        blocked_func = "Unknown"
        app_code_line = ""
        app_file = ""
        app_lineno = 0
        app_func = ""

        if frame:
            extracted = traceback.extract_stack(frame)
            stack_text = "".join(traceback.format_list(extracted))

            # Build structured Sentry/Bugsink frames
            for f in extracted:
                fn_lower = f.filename.replace("\\", "/").lower()
                is_app = (
                    any(p in fn_lower for p in ("havano", "views", "services", "models", "database", "updater"))
                    and "python3" not in fn_lower
                    and "site-packages" not in fn_lower
                )
                frames_data.append({
                    "filename": f.filename,
                    "function": f.name,
                    "lineno": f.lineno,
                    "context_line": f.line,
                    "in_app": is_app,
                })

            if extracted:
                leaf = extracted[-1]
                blocked_file = leaf.filename
                blocked_lineno = leaf.lineno
                blocked_func = leaf.name
                exact_code_line = (leaf.line or "").strip()

                # Walk backwards to find the last in-app frame (the POS code responsible)
                for f in reversed(extracted):
                    fn_lower = f.filename.replace("\\", "/").lower()
                    if (
                        any(p in fn_lower for p in ("havano", "views", "services", "models", "database", "updater"))
                        and "hang_watchdog" not in fn_lower
                        and "python3" not in fn_lower
                        and "site-packages" not in fn_lower
                    ):
                        app_file = f.filename
                        app_lineno = f.lineno
                        app_func = f.name
                        app_code_line = (f.line or "").strip()
                        break
        else:
            stack_text = "Stack trace not available"

        leaf_file_short = Path(blocked_file).name if blocked_file != "Unknown" else "Unknown"
        app_file_short = Path(app_file).name if app_file else ""

        # Construct high-visibility title with the exact code line
        if app_file and app_file_short != leaf_file_short:
            title = (
                f"UI Freeze ({elapsed:.1f}s) at [{current_page}]: "
                f"{app_file_short}:{app_lineno} in {app_func}() -> '{app_code_line}' "
                f"[blocked at {leaf_file_short}:{blocked_lineno}: '{exact_code_line}']"
            )
        else:
            title = (
                f"UI Freeze ({elapsed:.1f}s) at [{current_page}]: "
                f"{leaf_file_short}:{blocked_lineno} in {blocked_func}() -> '{exact_code_line}'"
            )

        severity = "warning" if threshold < 10.0 else "error"

        _logger.warning(
            f"[Watchdog] {title}\n"
            f"  Page: {current_page}\n"
            f"  Memory: {mem_mb:.1f} MB\n"
            f"  Exact Code Line: {exact_code_line}\n"
            f"  App Code Line: {app_code_line or exact_code_line}\n"
        )

        add_breadcrumb(
            category="ui_hang",
            message=f"Freeze alert: {elapsed:.1f}s at [{current_page}] -> {app_file_short or leaf_file_short}:{app_lineno or blocked_lineno} '{app_code_line or exact_code_line}'",
            level="error",
            data={
                "duration_seconds": round(elapsed, 2),
                "page": current_page,
                "memory_mb": round(mem_mb, 1),
                "exact_code_line": exact_code_line,
                "app_code_line": app_code_line,
            },
        )

        capture_freeze_event(
            title=title,
            frames=frames_data,
            level=severity,
            extra={
                "exact_code_line": exact_code_line,
                "app_code_line": app_code_line,
                "blocked_file": blocked_file,
                "blocked_lineno": blocked_lineno,
                "blocked_func": blocked_func,
                "app_file": app_file,
                "app_lineno": app_lineno,
                "app_func": app_func,
                "hang_duration_seconds": round(elapsed, 2),
                "threshold_seconds": threshold,
                "page": current_page,
                "process_memory_mb": round(mem_mb, 2),
                "frozen_stacktrace": stack_text,
                "detected_at": datetime.now().isoformat(),
            },
            tags={
                "ui_hang": "true",
                "hang_duration": f"{int(threshold)}s+",
                "page": current_page,
                "blocked_file": app_file_short or leaf_file_short,
                "blocked_lineno": str(app_lineno or blocked_lineno),
                "blocked_func": app_func or blocked_func,
                "exact_code_line": (app_code_line or exact_code_line)[:120],
            },
            raw_traceback=stack_text,
        )


_watchdog_instance: Optional[HangWatchdog] = None


def start_hang_watchdog(check_interval_seconds: float = 1.0) -> HangWatchdog:
    """Start the global UI Freeze Watchdog."""
    global _watchdog_instance
    if _watchdog_instance is None:
        _watchdog_instance = HangWatchdog(check_interval_seconds=check_interval_seconds)
        _watchdog_instance.start()
    return _watchdog_instance
