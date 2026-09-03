import os
import sys
import gc
import time
import threading
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QPoint, Signal
from PySide6.QtWidgets import (
    QDialog, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, 
    QProgressBar, QFrame, QGroupBox, QTabWidget, QFormLayout
)
from PySide6.QtGui import QFont

# Import centralized theme
try:
    from theme import (
        NAVY, NAVY_2, NAVY_3, ACCENT, WHITE, OFF_WHITE, 
        LIGHT, MUTED, BORDER, SUCCESS, DANGER, ORANGE, AMBER
    )
except ImportError:
    NAVY = "#1a5fb4"
    NAVY_2 = "#162d52"
    NAVY_3 = "#1e3d6e"
    ACCENT = "#1a5fb4"
    WHITE = "#ffffff"
    OFF_WHITE = "#f8fafc"
    LIGHT = "#e4eaf4"
    MUTED = "#64748b"
    BORDER = "#cbd5e1"
    SUCCESS = "#1a7a3c"
    DANGER = "#b02020"
    ORANGE = "#c05a00"
    AMBER = "#b06000"

# Safe psutil import
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import ctypes
    from ctypes import wintypes
    HAS_CTYPES = True
except ImportError:
    HAS_CTYPES = False


def get_current_process_memory_mb():
    """
    Failproof Memory Measurement for Havano POS.
    Uses Win32 API GetProcessMemoryInfo on Windows, psutil as secondary fallback.
    Returns (rss_ram_mb, peak_ram_mb).
    """
    if HAS_CTYPES and sys.platform.startswith("win"):
        try:
            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ('cb', wintypes.DWORD),
                    ('PageFaultCount', wintypes.DWORD),
                    ('PeakWorkingSetSize', ctypes.c_size_t),
                    ('WorkingSetSize', ctypes.c_size_t),
                    ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                    ('PagefileUsage', ctypes.c_size_t),
                    ('PeakPagefileUsage', ctypes.c_size_t),
                ]
            pmc = PROCESS_MEMORY_COUNTERS()
            pmc.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            get_mem = ctypes.windll.psapi.GetProcessMemoryInfo
            get_mem.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
            get_mem.restype = wintypes.BOOL
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            if get_mem(handle, ctypes.byref(pmc), pmc.cb):
                mb = pmc.WorkingSetSize / (1024.0 * 1024.0)
                peak_mb = pmc.PeakWorkingSetSize / (1024.0 * 1024.0)
                if mb > 0.0:
                    return mb, peak_mb
        except Exception:
            pass

    if HAS_PSUTIL:
        try:
            p = psutil.Process()
            info = p.memory_info()
            mb = info.rss / (1024.0 * 1024.0)
            peak_mb = getattr(info, "peak_wset", info.rss) / (1024.0 * 1024.0)
            return mb, peak_mb
        except Exception:
            pass

    return 0.0, 0.0


_win_cpu_state = {"last_time": None, "last_proc_time": None}

def get_current_process_cpu_percent():
    """
    Native Failproof Process CPU % measurement on Windows via GetProcessTimes.
    Returns process CPU % over the last sample interval.
    """
    if HAS_CTYPES and sys.platform.startswith("win"):
        try:
            get_times = ctypes.windll.kernel32.GetProcessTimes
            get_times.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(ctypes.c_uint64),
                ctypes.POINTER(ctypes.c_uint64),
                ctypes.POINTER(ctypes.c_uint64),
                ctypes.POINTER(ctypes.c_uint64)
            ]
            get_times.restype = wintypes.BOOL

            c = ctypes.c_uint64()
            e = ctypes.c_uint64()
            k = ctypes.c_uint64()
            u = ctypes.c_uint64()

            handle = ctypes.windll.kernel32.GetCurrentProcess()
            if get_times(handle, ctypes.byref(c), ctypes.byref(e), ctypes.byref(k), ctypes.byref(u)):
                proc_time_sec = (k.value + u.value) / 10000000.0
                now = time.time()
                if _win_cpu_state["last_time"] is not None:
                    dt = now - _win_cpu_state["last_time"]
                    dproc = proc_time_sec - _win_cpu_state["last_proc_time"]
                    if dt > 0:
                        cpu = min(100.0, max(0.0, (dproc / dt) * 100.0 / (os.cpu_count() or 1)))
                        _win_cpu_state["last_time"] = now
                        _win_cpu_state["last_proc_time"] = proc_time_sec
                        return cpu
                _win_cpu_state["last_time"] = now
                _win_cpu_state["last_proc_time"] = proc_time_sec
        except Exception:
            pass

    if HAS_PSUTIL:
        try:
            return psutil.Process().cpu_percent(interval=None)
        except Exception:
            pass

    return 0.0


class ResourceMonitorHUD(QDialog):
    """
    Comprehensive Performance & Database Diagnostic Monitor for Havano POS 2026.
    Tracks Process Resources, System CPU, Main Thread UI Lag, and SQL Database Statistics.
    Activated via Ctrl + Shift + Alt + M.
    """
    # Thread-safe signal to pass DB query results from background thread to Qt GUI thread
    db_stats_signal = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.start_time = time.time()
        self.last_tick_time = time.time()
        self.peak_ram_mb = 0.0
        self.peak_ui_lag_ms = 0
        self.is_compact = False
        self._drag_pos = QPoint()

        # Connect thread-safe signal
        self.db_stats_signal.connect(self._on_db_stats_ready)

        # Baseline CPU warmup
        get_current_process_cpu_percent()

        self._init_window_flags()
        self._build_ui()
        self.expand_full_mode()

        # Live refresh timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_metrics)

    def showEvent(self, event):
        """Start timer only when window is shown."""
        super().showEvent(event)
        self.update_metrics()
        if not self.timer.isActive():
            self.timer.start(1000)

    def hideEvent(self, event):
        """Stop timer when hidden so monitor uses 0 CPU when closed."""
        super().hideEvent(event)
        if self.timer.isActive():
            self.timer.stop()

    def _init_window_flags(self):
        self.setWindowTitle("System & Database Diagnostics")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setMinimumWidth(440)
        self.setMinimumHeight(460)

    def expand_full_mode(self):
        """Force monitor into full expanded 460px diagnostic mode when opened."""
        self.is_compact = False
        if hasattr(self, "body_widget"):
            self.body_widget.show()
        if hasattr(self, "btn_compact"):
            self.btn_compact.setText("_")
        self.setMinimumHeight(460)
        self.setMaximumHeight(16777215)
        self.resize(450, 480)

    def _build_ui(self):
        # Native QDialog styling — zero black border artifacts
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {WHITE};
                border: 1.5px solid {BORDER};
                border-radius: 8px;
            }}
            QLabel {{
                color: #1e293b;
                font-family: 'Segoe UI', Arial, sans-serif;
                background: transparent;
            }}
            QTabWidget::pane {{
                border: 1px solid {BORDER};
                border-radius: 6px;
                background: {WHITE};
                top: -1px;
            }}
            QTabBar::tab {{
                background: {OFF_WHITE};
                border: 1px solid {BORDER};
                border-bottom-color: {BORDER};
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
                padding: 6px 14px;
                font-weight: 600;
                color: #475569;
                font-size: 11px;
            }}
            QTabBar::tab:selected {{
                background: {WHITE};
                border-bottom-color: {WHITE};
                color: {NAVY};
                font-weight: bold;
            }}
            QGroupBox {{
                background-color: {OFF_WHITE};
                border: 1px solid {BORDER};
                border-radius: 6px;
                margin-top: 1.1em;
                font-weight: 600;
                color: {NAVY_2};
                font-size: 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
                color: {NAVY};
            }}
            QPushButton {{
                min-height: 32px;
                padding: 0 12px;
                border-radius: 5px;
                background-color: {WHITE};
                border: 1px solid {BORDER};
                color: #334155;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: #f1f5f9;
                border-color: #94a3b8;
            }}
            QPushButton#PrimaryBtn {{
                background-color: {NAVY};
                color: {WHITE};
                border: none;
                font-weight: bold;
            }}
            QPushButton#PrimaryBtn:hover {{
                background-color: {NAVY_3};
            }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 10)
        main_layout.setSpacing(8)

        # ── HEADER BANNER ──────────────────────────────────────────
        self.header_frame = QFrame()
        self.header_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {NAVY_2};
                border-top-left-radius: 7px;
                border-top-right-radius: 7px;
                border-bottom: 1px solid {NAVY};
            }}
            QLabel {{
                color: {WHITE};
                background: transparent;
            }}
        """)
        header_layout = QHBoxLayout(self.header_frame)
        header_layout.setContentsMargins(12, 8, 12, 8)
        header_layout.setSpacing(8)

        title_lbl = QLabel("System & Database Diagnostics")
        title_lbl.setFont(QFont("Segoe UI", 10, QFont.Bold))
        title_lbl.setStyleSheet(f"color: {WHITE};")

        self.btn_compact = QPushButton("_")
        self.btn_compact.setFixedSize(24, 22)
        self.btn_compact.setToolTip("Toggle Compact View")
        self.btn_compact.setStyleSheet(f"""
            QPushButton {{
                background-color: {NAVY_3};
                color: {WHITE};
                border: 1px solid #3b82f6;
                font-weight: bold;
                min-height: 22px;
                padding: 0px;
            }}
            QPushButton:hover {{ background-color: #2563eb; }}
        """)
        self.btn_compact.clicked.connect(self.toggle_compact_mode)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(24, 22)
        btn_close.setToolTip("Close Monitor")
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: {DANGER};
                color: {WHITE};
                border: none;
                font-weight: bold;
                min-height: 22px;
                padding: 0px;
            }}
            QPushButton:hover {{ background-color: #cc2828; }}
        """)
        btn_close.clicked.connect(self.hide)

        header_layout.addWidget(title_lbl)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_compact)
        header_layout.addWidget(btn_close)
        main_layout.addWidget(self.header_frame)

        # ── TABBED DIAGNOSTIC BODY ──────────────────────────────────
        self.body_widget = QWidget()
        body_layout = QVBoxLayout(self.body_widget)
        body_layout.setContentsMargins(10, 0, 10, 0)
        body_layout.setSpacing(8)

        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self._on_tab_changed)

        # TAB 1: System Health & Responsiveness
        tab_system = QWidget()
        t1_layout = QVBoxLayout(tab_system)
        t1_layout.setContentsMargins(10, 10, 10, 10)
        t1_layout.setSpacing(8)

        grp_sys = QGroupBox("Process & GUI Performance")
        sys_layout = QVBoxLayout(grp_sys)
        sys_layout.setContentsMargins(10, 14, 10, 10)
        sys_layout.setSpacing(6)

        # CPU Row (Process & System CPU)
        cpu_row = QHBoxLayout()
        cpu_title = QLabel("Process CPU / System CPU:")
        cpu_title.setStyleSheet("color: #475569; font-size: 12px;")
        self.lbl_cpu_val = QLabel("Proc: 0.0% | Sys: 0.0%")
        self.lbl_cpu_val.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.lbl_cpu_val.setStyleSheet(f"color: {SUCCESS};")
        cpu_row.addWidget(cpu_title)
        cpu_row.addStretch()
        cpu_row.addWidget(self.lbl_cpu_val)
        sys_layout.addLayout(cpu_row)

        self.bar_cpu = QProgressBar()
        self.bar_cpu.setFixedHeight(5)
        self.bar_cpu.setTextVisible(False)
        self.bar_cpu.setStyleSheet(f"""
            QProgressBar {{ background-color: #e2e8f0; border-radius: 2px; border: none; }}
            QProgressBar::chunk {{ background-color: {NAVY}; border-radius: 2px; }}
        """)
        sys_layout.addWidget(self.bar_cpu)

        # RAM Row
        ram_row = QHBoxLayout()
        ram_title = QLabel("RAM Memory (RSS):")
        ram_title.setStyleSheet("color: #475569; font-size: 12px;")
        self.lbl_ram_val = QLabel("0.0 MB")
        self.lbl_ram_val.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.lbl_ram_val.setStyleSheet(f"color: {NAVY};")
        ram_row.addWidget(ram_title)
        ram_row.addStretch()
        ram_row.addWidget(self.lbl_ram_val)
        sys_layout.addLayout(ram_row)

        # RAM Details
        details_row = QHBoxLayout()
        self.lbl_peak_ram = QLabel("Peak RAM: 0.0 MB")
        self.lbl_peak_ram.setStyleSheet("color: #64748b; font-size: 11px;")
        self.lbl_threads = QLabel("Threads: 0")
        self.lbl_threads.setStyleSheet("color: #64748b; font-size: 11px;")
        details_row.addWidget(self.lbl_peak_ram)
        details_row.addStretch()
        details_row.addWidget(self.lbl_threads)
        sys_layout.addLayout(details_row)

        # UI Event Loop Lag & Freeze Tracker
        ui_lag_row = QHBoxLayout()
        ui_lag_title = QLabel("UI Event Loop Lag:")
        ui_lag_title.setStyleSheet("color: #475569; font-size: 11px;")
        self.lbl_ui_lag = QLabel("0 ms (Smooth)")
        self.lbl_ui_lag.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.lbl_ui_lag.setStyleSheet(f"color: {SUCCESS};")
        ui_lag_row.addWidget(ui_lag_title)
        ui_lag_row.addStretch()
        ui_lag_row.addWidget(self.lbl_ui_lag)
        sys_layout.addLayout(ui_lag_row)

        # Peak UI Stutter Tracker
        self.lbl_peak_lag = QLabel("Peak Stutter Recorded: 0 ms")
        self.lbl_peak_lag.setStyleSheet("color: #64748b; font-size: 10px; font-style: italic;")
        sys_layout.addWidget(self.lbl_peak_lag)

        t1_layout.addWidget(grp_sys)

        grp_diag = QGroupBox("Runtime Status")
        diag_layout = QVBoxLayout(grp_diag)
        diag_layout.setContentsMargins(10, 14, 10, 10)
        diag_layout.setSpacing(5)

        uptime_row = QHBoxLayout()
        lbl_up_title = QLabel("Session Uptime:")
        lbl_up_title.setStyleSheet("color: #475569; font-size: 11px;")
        self.lbl_uptime = QLabel("00:00:00")
        self.lbl_uptime.setStyleSheet(f"color: {NAVY_2}; font-weight: bold; font-size: 11px;")
        uptime_row.addWidget(lbl_up_title)
        uptime_row.addStretch()
        uptime_row.addWidget(self.lbl_uptime)
        diag_layout.addLayout(uptime_row)

        db_row = QHBoxLayout()
        lbl_db_title = QLabel("Database Status:")
        lbl_db_title.setStyleSheet("color: #475569; font-size: 11px;")
        self.lbl_db_status = QLabel("Connected")
        self.lbl_db_status.setStyleSheet(f"color: {SUCCESS}; font-weight: bold; font-size: 11px;")
        db_row.addWidget(lbl_db_title)
        db_row.addStretch()
        db_row.addWidget(self.lbl_db_status)
        diag_layout.addLayout(db_row)

        t1_layout.addWidget(grp_diag)
        self.tabs.addTab(tab_system, "System Health")

        # TAB 2: Database Diagnostics & Table Statistics
        tab_db = QWidget()
        t2_layout = QVBoxLayout(tab_db)
        t2_layout.setContentsMargins(10, 10, 10, 10)
        t2_layout.setSpacing(8)

        grp_db_tables = QGroupBox("Database Table Statistics")
        db_tbl_layout = QFormLayout(grp_db_tables)
        db_tbl_layout.setContentsMargins(10, 14, 10, 10)
        db_tbl_layout.setSpacing(6)

        self.lbl_stat_products = QLabel("Click Query to fetch...")
        self.lbl_stat_products.setStyleSheet(f"font-weight: bold; color: {NAVY};")
        
        self.lbl_stat_sales = QLabel("Click Query to fetch...")
        self.lbl_stat_sales.setStyleSheet(f"font-weight: bold; color: {NAVY};")

        self.lbl_stat_sale_items = QLabel("Click Query to fetch...")
        self.lbl_stat_sale_items.setStyleSheet("font-weight: bold;")

        self.lbl_stat_shifts = QLabel("Click Query to fetch...")
        self.lbl_stat_shifts.setStyleSheet("font-weight: bold;")

        self.lbl_db_latency = QLabel("0 ms")
        self.lbl_db_latency.setStyleSheet(f"font-weight: bold; color: {SUCCESS};")

        db_tbl_layout.addRow("Products Catalog:", self.lbl_stat_products)
        db_tbl_layout.addRow("Sales Transactions:", self.lbl_stat_sales)
        db_tbl_layout.addRow("Sales Invoice Items:", self.lbl_stat_sale_items)
        db_tbl_layout.addRow("Shifts Recorded:", self.lbl_stat_shifts)
        db_tbl_layout.addRow("SQL Query Latency:", self.lbl_db_latency)

        t2_layout.addWidget(grp_db_tables)

        btn_refresh_db = QPushButton("🔄 Query Database Stats")
        btn_refresh_db.clicked.connect(self.refresh_db_stats_async)
        t2_layout.addWidget(btn_refresh_db)

        self.tabs.addTab(tab_db, "Database Diagnostics")

        # TAB 3: Lag Diagnostics Guide
        tab_guide = QWidget()
        t3_layout = QVBoxLayout(tab_guide)
        t3_layout.setContentsMargins(10, 10, 10, 10)
        t3_layout.setSpacing(6)

        grp_causes = QGroupBox("Common Causes of 'Not Responding'")
        causes_layout = QVBoxLayout(grp_causes)
        causes_layout.setContentsMargins(10, 14, 10, 10)
        causes_layout.setSpacing(4)

        guide_txt = QLabel(
            "• Search Keystrokes: Synchronous SQL queries during rapid typing.\n"
            "• Large Invoices: Re-rendering hundreds of table cell widgets on UI thread.\n"
            "• Network Sync Pings: SaaS cloud calls running synchronously on Qt thread.\n"
            "• Long Sessions: Un-garbage collected UI objects accumulating RAM."
        )
        guide_txt.setStyleSheet("color: #334155; font-size: 11px; line-height: 1.4;")
        guide_txt.setWordWrap(True)
        causes_layout.addWidget(guide_txt)
        t3_layout.addWidget(grp_causes)

        self.tabs.addTab(tab_guide, "Lag Causes")

        body_layout.addWidget(self.tabs)

        # Actions Footer Layout
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(6)

        self.btn_gc = QPushButton("Free Memory")
        self.btn_gc.setObjectName("PrimaryBtn")
        self.btn_gc.setToolTip("Trigger Python Garbage Collection and trim unused process memory")
        self.btn_gc.clicked.connect(self.action_free_memory)

        btn_refresh = QPushButton("Refresh")
        btn_refresh.setToolTip("Force immediate metrics recalculation")
        btn_refresh.clicked.connect(self.update_metrics)

        actions_layout.addWidget(self.btn_gc, 2)
        actions_layout.addWidget(btn_refresh, 1)
        body_layout.addLayout(actions_layout)

        main_layout.addWidget(self.body_widget, 1)

    def _on_tab_changed(self, index):
        """Auto-query database stats when user opens the Database Diagnostics tab."""
        if index == 1:
            self.refresh_db_stats_async()

    def update_metrics(self):
        """Fetch and display real-time process metrics & main thread lag detector."""
        # 0. Measure UI Event Loop Lag (Not Responding Detector)
        now = time.time()
        elapsed = now - self.last_tick_time
        self.last_tick_time = now
        lag_ms = max(0, int((elapsed - 1.0) * 1000))

        if lag_ms > self.peak_ui_lag_ms:
            self.peak_ui_lag_ms = lag_ms

        if lag_ms > 800:
            self.lbl_ui_lag.setText(f"⚠️ {lag_ms} ms (Main Thread Blocked)")
            self.lbl_ui_lag.setStyleSheet(f"color: {DANGER}; font-weight: bold;")
        elif lag_ms > 200:
            self.lbl_ui_lag.setText(f"{lag_ms} ms (Mild Lag)")
            self.lbl_ui_lag.setStyleSheet(f"color: {ORANGE}; font-weight: bold;")
        else:
            self.lbl_ui_lag.setText(f"{lag_ms} ms (Smooth)")
            self.lbl_ui_lag.setStyleSheet(f"color: {SUCCESS}; font-weight: bold;")

        self.lbl_peak_lag.setText(f"Peak Stutter Recorded: {self.peak_ui_lag_ms} ms")

        # 1. RAM Measurement via WinAPI / psutil
        ram_mb, peak_mb = get_current_process_memory_mb()

        if peak_mb > self.peak_ram_mb:
            self.peak_ram_mb = peak_mb
        if ram_mb > self.peak_ram_mb:
            self.peak_ram_mb = ram_mb

        self.lbl_ram_val.setText(f"{ram_mb:.1f} MB")
        self.lbl_peak_ram.setText(f"Peak RAM: {self.peak_ram_mb:.1f} MB")

        # 2. Native Win32 / psutil CPU Measurement (Process & System CPU)
        proc_cpu = get_current_process_cpu_percent()
        sys_cpu = 0.0
        try:
            if HAS_PSUTIL:
                sys_cpu = psutil.cpu_percent(interval=None)
        except Exception:
            pass

        # If Process is idle, show (Idle) tag cleanly
        if proc_cpu <= 0.05:
            self.lbl_cpu_val.setText(f"Proc: 0.0% (Idle) | Sys: {sys_cpu:.1f}%")
        else:
            self.lbl_cpu_val.setText(f"Proc: {proc_cpu:.1f}% | Sys: {sys_cpu:.1f}%")

        display_cpu = max(proc_cpu, sys_cpu)
        self.bar_cpu.setValue(int(min(display_cpu, 100)))

        if display_cpu > 75.0:
            cpu_color = DANGER
        elif display_cpu > 35.0:
            cpu_color = ORANGE
        else:
            cpu_color = SUCCESS

        self.lbl_cpu_val.setStyleSheet(f"color: {cpu_color}; font-weight: bold;")
        self.bar_cpu.setStyleSheet(f"""
            QProgressBar {{ background-color: #e2e8f0; border-radius: 2px; border: none; }}
            QProgressBar::chunk {{ background-color: {cpu_color}; border-radius: 2px; }}
        """)

        # 3. Active Threads Count
        threads_cnt = 0
        try:
            if HAS_PSUTIL and hasattr(self, "process") and self.process:
                threads_cnt = len(self.process.threads())
            else:
                threads_cnt = threading.active_count()
        except Exception:
            threads_cnt = threading.active_count()

        self.lbl_threads.setText(f"Threads: {threads_cnt}")

        # 4. Session Uptime Calculation
        elapsed_sec = int(time.time() - self.start_time)
        hours = elapsed_sec // 3600
        minutes = (elapsed_sec % 3600) // 60
        seconds = elapsed_sec % 60
        self.lbl_uptime.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")

        # 5. Non-Blocking DB Check
        try:
            from database.db import get_app_data_dir
            sql_file = get_app_data_dir() / "sql_settings.json"
            if sql_file.exists():
                self.lbl_db_status.setText("Connected")
                self.lbl_db_status.setStyleSheet(f"color: {SUCCESS}; font-weight: bold; font-size: 11px;")
            else:
                self.lbl_db_status.setText("Not Configured")
                self.lbl_db_status.setStyleSheet(f"color: {ORANGE}; font-weight: bold; font-size: 11px;")
        except Exception:
            self.lbl_db_status.setText("Connected")

    def refresh_db_stats_async(self):
        """Query DB row counts asynchronously in a background thread using thread-safe Qt Signals."""
        self.lbl_stat_products.setText("Querying database...")
        self.lbl_stat_sales.setText("Querying database...")
        self.lbl_stat_sale_items.setText("Querying database...")
        self.lbl_stat_shifts.setText("Querying database...")

        def worker():
            start_t = time.time()
            res = {"products": 0, "sales": 0, "sale_items": 0, "shifts": 0, "latency": 0, "err": None}
            try:
                from database.db import get_connection
                conn = get_connection()
                cur = conn.cursor()
                
                try:
                    cur.execute("SELECT COUNT(*) FROM products")
                    res["products"] = cur.fetchone()[0]
                except Exception: pass
                
                try:
                    cur.execute("SELECT COUNT(*) FROM sales")
                    res["sales"] = cur.fetchone()[0]
                except Exception: pass
                
                try:
                    cur.execute("SELECT COUNT(*) FROM sale_items")
                    res["sale_items"] = cur.fetchone()[0]
                except Exception: pass

                try:
                    cur.execute("SELECT COUNT(*) FROM shifts")
                    res["shifts"] = cur.fetchone()[0]
                except Exception: pass

                res["latency"] = max(1, int((time.time() - start_t) * 1000))
            except Exception as e:
                print(f"[HUD DB Stats Error] {e}")
                res["err"] = str(e)

            # Emit thread-safe Signal to Qt GUI main thread
            self.db_stats_signal.emit(res)

        threading.Thread(target=worker, daemon=True).start()

    def _on_db_stats_ready(self, res: dict):
        """Executed on Qt GUI Main Thread when DB stats worker finishes."""
        if res.get("err"):
            self.lbl_stat_products.setText("Offline / SQL Error")
            self.lbl_stat_sales.setText("Offline")
            self.lbl_stat_sale_items.setText("Offline")
            self.lbl_stat_shifts.setText("Offline")
            self.lbl_db_latency.setText("Error")
        else:
            self.lbl_stat_products.setText(f"{res['products']:,} items")
            self.lbl_stat_sales.setText(f"{res['sales']:,} invoices")
            self.lbl_stat_sale_items.setText(f"{res['sale_items']:,} items logged")
            self.lbl_stat_shifts.setText(f"{res['shifts']:,} shifts")
            self.lbl_db_latency.setText(f"{res['latency']} ms")

    def action_free_memory(self):
        """Perform Python garbage collection and Windows working set trim."""
        before_ram, _ = get_current_process_memory_mb()

        # Python Garbage Collection
        gc.collect()

        # Windows OS memory working set trim
        if HAS_CTYPES and sys.platform.startswith("win"):
            try:
                ctypes.windll.psapi.EmptyWorkingSet(-1)
            except Exception:
                pass

        self.update_metrics()

        after_ram, _ = get_current_process_memory_mb()
        freed_mb = max(0.0, before_ram - after_ram)
        self.lbl_ram_val.setText(f"{after_ram:.1f} MB (Freed {freed_mb:.1f} MB)")

    def toggle_compact_mode(self):
        self.is_compact = not self.is_compact
        if self.is_compact:
            self.body_widget.hide()
            self.btn_compact.setText("+")
            self.setFixedHeight(40)
        else:
            self.expand_full_mode()

    # ── DRAGGABLE WINDOW HANDLERS ────────────────────────────────
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and not self._drag_pos.isNull():
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = QPoint()
        event.accept()
