# =============================================================================
# views/dialogs/day_shift_dialog.py  —  fully wired to models/shift.py
# =============================================================================

from datetime import date as _date
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame, QSpinBox, QAbstractItemView, QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt, QTimer, QTime
from PySide6.QtGui import QFont, QColor

# ── colours ───────────────────────────────────────────────────────────────────
NAVY      = "#0d1f3c"
NAVY_2    = "#162d52"
NAVY_3    = "#1e3d6e"
ACCENT    = "#1a5fb4"
ACCENT_H  = "#1c6dd0"
WHITE     = "#ffffff"
OFF_WHITE = "#f5f8fc"
LIGHT     = "#e4eaf4"
BORDER    = "#c8d8ec"
DARK_TEXT = "#0d1f3c"
MUTED     = "#5a7a9a"
SUCCESS   = "#1a7a3c"
SUCCESS_H = "#1f9447"
DANGER    = "#b02020"
DANGER_H  = "#cc2828"
ROW_ALT   = "#edf3fb"


# ── helpers ───────────────────────────────────────────────────────────────────
def _hr():
    ln = QFrame()
    ln.setFrameShape(QFrame.HLine)
    ln.setStyleSheet(f"background: {BORDER}; border: none;")
    ln.setFixedHeight(1)
    return ln

def _lbl(text, bold=False, color=DARK_TEXT, size=13, align=None):
    w = QLabel(text)
    w.setStyleSheet(
        f"color:{color}; font-size:{size}px; "
        f"font-weight:{'bold' if bold else 'normal'}; background:transparent;"
    )
    if align:
        w.setAlignment(align)
    return w

def _btn(text, height=40, width=None, bg=NAVY, hov=NAVY_2, fs=12):
    b = QPushButton(text)
    b.setFixedHeight(height)
    if width:
        b.setFixedWidth(width)
    b.setCursor(Qt.PointingHandCursor)
    b.setStyleSheet(f"""
        QPushButton {{
            background:{bg}; color:{WHITE}; border:none;
            border-radius:6px; font-size:{fs}px; font-weight:bold; padding:0 14px;
        }}
        QPushButton:hover   {{ background:{hov}; }}
        QPushButton:pressed {{ background:{NAVY_3}; }}
    """)
    return b

def _inp(ph="0.00", width=None, right=False):
    w = QLineEdit()
    w.setPlaceholderText(ph)
    w.setFixedHeight(30)
    if width:
        w.setFixedWidth(width)
    w.setStyleSheet(f"""
        QLineEdit {{
            background:{WHITE}; color:{DARK_TEXT};
            border:1px solid {BORDER}; border-radius:5px;
            padding:4px 8px; font-size:13px;
        }}
        QLineEdit:focus {{ border:2px solid {ACCENT}; }}
    """)
    if right:
        w.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    return w

def _msgbox(parent, title, text, color=None):
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setStyleSheet(f"""
        QMessageBox {{ background:{WHITE}; }}
        QLabel {{ color:{DARK_TEXT}; font-size:13px; }}
        QPushButton {{
            background:{color or ACCENT}; color:{WHITE}; border:none;
            border-radius:6px; padding:8px 20px; min-width:80px;
        }}
    """)
    msg.exec()


# =============================================================================
class DayShiftDialog(QDialog):
    """
    Cash Drawer Reconciliation — fully wired to models/shift.py.

    On open:
      • Checks for an active (un-ended) shift → resumes it
      • Pre-fills Shift Number from DB auto-increment
      • Pre-fills Income $ from today's actual sales
      • Pre-fills date from system clock

    On Start Shift  → creates shift record in DB, stores shift_id
    On End Shift    → writes end_time + counted values to DB
    On Save (F2)    → updates opening floats in DB mid-shift
    On File         → exports to CSV
    """

    PAYMENT_ROWS = ["CASH", "CHECK", "C / CARD", "AMEX", "DINERS", "EFTPOS"]

    def __init__(self, parent=None, user=None):
        super().__init__(parent)
        self.user           = user or {"id": None, "username": "admin", "role": "admin"}
        self._shift_id      = None   # set after start_shift() DB call
        self._shift_running = False
        self._elapsed_secs  = 0

        # Try to resume an active shift
        self._active_shift  = None
        try:
            from models.shift import get_active_shift, get_next_shift_number, get_income_by_method
            self._active_shift     = get_active_shift()
            self._next_shift_num   = get_next_shift_number()
            self._income_by_method = get_income_by_method()
        except Exception:
            self._next_shift_num   = 1
            self._income_by_method = {}

        self.setWindowTitle("Cash Drawer Reconciliation")
        self.setFixedSize(820, 600)
        self.setModal(True)
        self.setStyleSheet(f"""
            QDialog {{ background:{OFF_WHITE}; }}
            QWidget {{ background:{OFF_WHITE}; color:{DARK_TEXT}; font-size:13px; }}
            QSpinBox {{
                background:{WHITE}; color:{DARK_TEXT};
                border:1px solid {BORDER}; border-radius:5px;
                padding:4px 6px; font-size:13px;
            }}
            QSpinBox:focus {{ border:2px solid {ACCENT}; }}
        """)

        self._build_ui()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

        # Resume active shift if one exists
        if self._active_shift:
            self._resume_shift(self._active_shift)

    # =========================================================================
    # BUILD UI
    # =========================================================================
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(16, 16, 16, 16)
        root.addWidget(self._build_header())
        root.addWidget(_hr())
        root.addWidget(self._build_table(), 1)
        root.addWidget(_hr())
        root.addWidget(self._build_footer_row())
        root.addWidget(_hr())
        root.addWidget(self._build_action_buttons())

    # ── header ────────────────────────────────────────────────────────────────
    def _build_header(self):
        card = QWidget()
        card.setStyleSheet(f"background:{WHITE}; border:1px solid {BORDER}; border-radius:8px;")
        lay = QHBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(20)

        # Date
        c = QVBoxLayout(); c.setSpacing(4)
        c.addWidget(_lbl("Date", bold=True, color=MUTED, size=11))
        self.date_input = _inp(width=110)
        self.date_input.setText(_date.today().strftime("%m/%d/%Y"))
        c.addWidget(self.date_input)
        lay.addLayout(c)

        # Station
        c = QVBoxLayout(); c.setSpacing(4)
        c.addWidget(_lbl("Station", bold=True, color=MUTED, size=11))
        self.station_spin = QSpinBox()
        self.station_spin.setRange(1, 99)
        self.station_spin.setValue(1)
        self.station_spin.setFixedSize(80, 30)
        c.addWidget(self.station_spin)
        lay.addLayout(c)

        # Shift Number
        c = QVBoxLayout(); c.setSpacing(4)
        c.addWidget(_lbl("Shift #", bold=True, color=MUTED, size=11))
        self.shift_spin = QSpinBox()
        self.shift_spin.setRange(1, 9999)
        self.shift_spin.setValue(self._next_shift_num)
        self.shift_spin.setFixedSize(80, 30)
        c.addWidget(self.shift_spin)
        lay.addLayout(c)

        lay.addStretch()

        # Start Shift
        c = QVBoxLayout(); c.setSpacing(4)
        self.start_btn = _btn("Start Shift", height=36, width=110, bg=SUCCESS, hov=SUCCESS_H)
        self.start_btn.clicked.connect(self._on_start_shift)
        self.start_time_lbl = QLabel("00:00:00")
        self.start_time_lbl.setFixedWidth(110)
        self.start_time_lbl.setAlignment(Qt.AlignCenter)
        self.start_time_lbl.setStyleSheet(f"""
            color:{DARK_TEXT}; font-size:14px; font-weight:bold;
            background:{LIGHT}; border:1px solid {BORDER};
            border-radius:5px; padding:4px;
        """)
        c.addWidget(self.start_btn)
        c.addWidget(self.start_time_lbl)
        lay.addLayout(c)

        # End Shift
        c = QVBoxLayout(); c.setSpacing(4)
        self.end_btn = _btn("End Shift", height=36, width=110, bg=DANGER, hov=DANGER_H)
        self.end_btn.setEnabled(False)
        self.end_btn.clicked.connect(self._on_end_shift)
        self.end_time_lbl = QLabel("--:--:--")
        self.end_time_lbl.setFixedWidth(110)
        self.end_time_lbl.setAlignment(Qt.AlignCenter)
        self.end_time_lbl.setStyleSheet(f"""
            color:{DARK_TEXT}; font-size:14px; font-weight:bold;
            background:{LIGHT}; border:1px solid {BORDER};
            border-radius:5px; padding:4px;
        """)
        c.addWidget(self.end_btn)
        c.addWidget(self.end_time_lbl)
        lay.addLayout(c)

        return card

    # ── table ─────────────────────────────────────────────────────────────────
    def _build_table(self):
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["Details", "Start $", "Income $", "Total $", "Counted $", "Variance $"]
        )
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        for c in range(1, 6):
            hh.setSectionResizeMode(c, QHeaderView.Fixed)
            self.table.setColumnWidth(c, 105)

        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background:{WHITE}; color:{DARK_TEXT};
                border:1px solid {BORDER}; gridline-color:{LIGHT};
                font-size:13px; outline:none;
            }}
            QTableWidget::item           {{ padding:6px 8px; }}
            QTableWidget::item:selected  {{ background:{ACCENT}; color:{WHITE}; }}
            QTableWidget::item:alternate {{ background:{ROW_ALT}; }}
            QHeaderView::section {{
                background:{NAVY}; color:{WHITE};
                padding:9px 8px; border:none;
                border-right:1px solid {NAVY_2};
                font-size:11px; font-weight:bold;
            }}
        """)

        total_rows = len(self.PAYMENT_ROWS) + 3  # +3 blank spacers
        self.table.setRowCount(total_rows)

        for r, method in enumerate(self.PAYMENT_ROWS):
            self.table.setRowHeight(r, 34)
            income = self._income_by_method.get(method, 0.0)
            self._set_row(r, method, start=0.0, income=income, counted=0.0)

        for r in range(len(self.PAYMENT_ROWS), total_rows):
            self.table.setRowHeight(r, 34)
            for c in range(6):
                item = QTableWidgetItem("")
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(r, c, item)

        # totals row
        self._totals_row = self.table.rowCount()
        self.table.setRowCount(self._totals_row + 1)
        self.table.setRowHeight(self._totals_row, 36)
        self._update_totals_row()

        self.table.cellChanged.connect(self._on_cell_changed)
        return self.table

    def _set_row(self, row, method, start=0.0, income=0.0, counted=0.0):
        total    = start + income
        variance = total - counted

        def _item(val, editable=False, bold=False, is_var=False):
            text = f"{val:.2f}" if isinstance(val, float) else str(val)
            it = QTableWidgetItem(text)
            it.setTextAlignment(
                Qt.AlignLeft | Qt.AlignVCenter if val == method
                else Qt.AlignRight | Qt.AlignVCenter
            )
            if not editable:
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
            if bold:
                f = QFont(); f.setBold(True); it.setFont(f)
            if is_var and isinstance(val, float):
                it.setForeground(QColor(DANGER if abs(val) > 0.001 else SUCCESS))
            return it

        items = [
            _item(method,   editable=False, bold=True),
            _item(start,    editable=True,  bold=True),
            _item(income,   editable=False),
            _item(total,    editable=False),
            _item(counted,  editable=True,  bold=True),
            _item(variance, editable=False, is_var=True),
        ]
        for c, it in enumerate(items):
            self.table.setItem(row, c, it)

    def _on_cell_changed(self, row, col):
        if row >= len(self.PAYMENT_ROWS) or col not in (1, 4):
            return
        self.table.blockSignals(True)
        try:
            start   = float((self.table.item(row, 1) or QTableWidgetItem("0")).text() or "0")
            income  = float((self.table.item(row, 2) or QTableWidgetItem("0")).text() or "0")
            counted = float((self.table.item(row, 4) or QTableWidgetItem("0")).text() or "0")
            total    = start + income
            variance = total - counted

            ti = QTableWidgetItem(f"{total:.2f}")
            ti.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            ti.setFlags(ti.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 3, ti)

            vi = QTableWidgetItem(f"{variance:.2f}")
            vi.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            vi.setFlags(vi.flags() & ~Qt.ItemIsEditable)
            vi.setForeground(QColor(DANGER if abs(variance) > 0.001 else SUCCESS))
            self.table.setItem(row, 5, vi)
        except ValueError:
            pass
        self.table.blockSignals(False)
        self._update_totals_row()

    def _update_totals_row(self):
        self.table.blockSignals(True)
        totals = [0.0] * 5
        for r in range(len(self.PAYMENT_ROWS)):
            for ci, col in enumerate([1, 2, 3, 4, 5]):
                it = self.table.item(r, col)
                try:
                    totals[ci] += float(it.text() or "0") if it else 0.0
                except ValueError:
                    pass

        for c, text in enumerate(["TOTALS", *[f"{v:.2f}" for v in totals]]):
            it = QTableWidgetItem(text)
            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
            it.setTextAlignment(
                Qt.AlignLeft | Qt.AlignVCenter if c == 0
                else Qt.AlignRight | Qt.AlignVCenter
            )
            f = QFont(); f.setBold(True); it.setFont(f)
            it.setBackground(QColor(LIGHT))
            if c == 5:
                it.setForeground(QColor(DANGER if abs(totals[4]) > 0.001 else SUCCESS))
            self.table.setItem(self._totals_row, c, it)
        self.table.blockSignals(False)

    # ── footer ────────────────────────────────────────────────────────────────
    def _build_footer_row(self):
        bar = QWidget()
        bar.setFixedHeight(44)
        bar.setStyleSheet(f"background:{WHITE}; border:1px solid {BORDER}; border-radius:6px;")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 6, 16, 6)
        lay.setSpacing(24)

        lay.addWidget(_lbl("Door Counter:", bold=True, color=MUTED))
        self.door_counter = _inp("0", width=90)
        self.door_counter.setText("0")
        lay.addWidget(self.door_counter)

        lay.addStretch()

        lay.addWidget(_lbl("Customers:", bold=True, color=MUTED))
        self.customers_input = _inp("0", width=90)
        self.customers_input.setText("0")
        lay.addWidget(self.customers_input)

        lay.addStretch()
        lay.addWidget(_lbl(f"Cashier: {self.user['username']}", color=MUTED))
        return bar

    # ── action buttons ────────────────────────────────────────────────────────
    def _build_action_buttons(self):
        bar = QWidget()
        bar.setFixedHeight(80)
        bar.setStyleSheet(f"background:{WHITE}; border:1px solid {BORDER}; border-radius:8px;")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(20, 12, 20, 12)
        lay.setSpacing(12)

        for label, bg, hov, handler in [
            ("💾\nSave (F2)",   NAVY,   NAVY_2,   self._on_save),
            ("🧾\nReceipt",     ACCENT, ACCENT_H, self._on_receipt),
            ("🖨\nPrint (F3)",  NAVY,   NAVY_2,   self._on_print),
            ("📁\nExport CSV",  NAVY_2, NAVY_3,   self._on_file),
            ("✕\nClose (Esc)", DANGER, DANGER_H, self.reject),
        ]:
            b = QPushButton(label)
            b.setFixedSize(110, 56)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"""
                QPushButton {{
                    background:{bg}; color:{WHITE}; border:none;
                    border-radius:8px; font-size:12px; font-weight:bold; text-align:center;
                }}
                QPushButton:hover   {{ background:{hov}; }}
                QPushButton:pressed {{ background:{NAVY_3}; }}
            """)
            b.clicked.connect(handler)
            lay.addWidget(b)

        lay.addStretch()

        self.status_badge = QLabel("  ⚫  Shift Not Started  ")
        self.status_badge.setFixedHeight(36)
        self.status_badge.setAlignment(Qt.AlignCenter)
        self.status_badge.setStyleSheet(f"""
            background:{LIGHT}; color:{MUTED};
            border:1px solid {BORDER}; border-radius:18px;
            font-size:12px; font-weight:bold; padding:0 16px;
        """)
        lay.addWidget(self.status_badge)
        return bar

    # =========================================================================
    # SHIFT LOGIC
    # =========================================================================
    def _on_start_shift(self):
        try:
            from models.shift import start_shift
            shift = start_shift(
                station=self.station_spin.value(),
                shift_number=self.shift_spin.value(),
                cashier_id=self.user.get("id"),
                date=self.date_input.text(),
                opening_floats=self._collect_start_values(),
            )
            self._shift_id = shift["id"]
            # Reload income from DB (shift start_shift fills it)
            for r, method in enumerate(self.PAYMENT_ROWS):
                for row_data in shift.get("rows", []):
                    if row_data["method"] == method:
                        self.table.blockSignals(True)
                        it = self.table.item(r, 2)
                        if it:
                            it.setText(f"{row_data['income']:.2f}")
                        self.table.blockSignals(False)
        except Exception as e:
            _msgbox(self, "DB Error", f"Could not save shift to DB:\n{e}", DANGER)

        self._shift_running = True
        self._elapsed_secs  = 0
        self.start_btn.setEnabled(False)
        self.end_btn.setEnabled(True)
        self.date_input.setReadOnly(True)
        self.station_spin.setEnabled(False)
        self.shift_spin.setEnabled(False)
        from datetime import datetime
        self.start_time_lbl.setText(datetime.now().strftime("%H:%M:%S"))
        self._set_status_badge("running")
        self._timer.start(1000)
        self._update_totals_row()

    def _on_end_shift(self):
        if not self._shift_id:
            _msgbox(self, "Error", "No active shift ID found. Was Start Shift pressed?", DANGER)
            return

        try:
            from models.shift import end_shift
            end_shift(
                shift_id=self._shift_id,
                counted_values=self._collect_counted_values(),
                door_counter=int(self.door_counter.text() or 0),
                customers=int(self.customers_input.text() or 0),
            )
        except Exception as e:
            _msgbox(self, "DB Error", f"Could not save end shift:\n{e}", DANGER)

        self._timer.stop()
        self._shift_running = False
        from datetime import datetime
        self.end_time_lbl.setText(datetime.now().strftime("%H:%M:%S"))
        self.end_btn.setEnabled(False)
        self._set_status_badge("ended")

        # Lock Counted $ column
        for r in range(len(self.PAYMENT_ROWS)):
            it = self.table.item(r, 4)
            if it:
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)

        _msgbox(self, "Shift Ended", "✅  Shift closed and saved to database.")

    def _resume_shift(self, shift: dict):
        """Reload UI state from an active shift already in the DB."""
        self._shift_id      = shift["id"]
        self._shift_running = True

        self.shift_spin.setValue(shift["shift_number"])
        self.station_spin.setValue(shift["station"])
        self.date_input.setText(shift["date"])
        self.start_time_lbl.setText(shift["start_time"])

        # Refresh income from today's sales
        try:
            from models.shift import refresh_income
            refresh_income(self._shift_id)
            from models.shift import get_shift_by_id
            shift = get_shift_by_id(self._shift_id)
        except Exception:
            pass

        # Fill table rows from DB
        self.table.blockSignals(True)
        for r, method in enumerate(self.PAYMENT_ROWS):
            for row_data in shift.get("rows", []):
                if row_data["method"] == method:
                    self._set_row(
                        r, method,
                        start=row_data["start_float"],
                        income=row_data["income"],
                        counted=row_data["counted"],
                    )
        self.table.blockSignals(False)
        self._update_totals_row()

        self.start_btn.setEnabled(False)
        self.end_btn.setEnabled(True)
        self.date_input.setReadOnly(True)
        self.station_spin.setEnabled(False)
        self.shift_spin.setEnabled(False)
        self._set_status_badge("running")
        self._timer.start(1000)

    def _tick(self):
        self._elapsed_secs += 1
        elapsed = QTime(0, 0).addSecs(self._elapsed_secs)
        self.start_time_lbl.setText(elapsed.toString("HH:mm:ss"))

    def _set_status_badge(self, state: str):
        if state == "running":
            self.status_badge.setText("  🟢  Shift Running  ")
            self.status_badge.setStyleSheet(f"""
                background:#d4edda; color:{SUCCESS};
                border:1px solid {SUCCESS}; border-radius:18px;
                font-size:12px; font-weight:bold; padding:0 16px;
            """)
        elif state == "ended":
            self.status_badge.setText("  🔴  Shift Ended  ")
            self.status_badge.setStyleSheet(f"""
                background:#fde8e8; color:{DANGER};
                border:1px solid {DANGER}; border-radius:18px;
                font-size:12px; font-weight:bold; padding:0 16px;
            """)

    # =========================================================================
    # BUTTON HANDLERS
    # =========================================================================
    def _on_save(self):
        if not self._shift_id:
            _msgbox(self, "Not Started", "Start the shift before saving.", DANGER)
            return
        try:
            from models.shift import save_shift_floats
            save_shift_floats(self._shift_id, self._collect_start_values())
            _msgbox(self, "Saved", "✅  Shift data saved to database.")
        except Exception as e:
            _msgbox(self, "Save Error", str(e), DANGER)

    def _on_receipt(self):
        data = self._collect_all()
        lines = [
            "=" * 38,
            "   SHIFT RECONCILIATION REPORT",
            "=" * 38,
            f"Date:    {data['date']}",
            f"Shift:   #{data['shift_number']}   Station: {data['station']}",
            f"Cashier: {data['cashier']}",
            f"Start:   {data['start_time']}   End: {data['end_time']}",
            "-" * 38,
            f"{'Method':<12} {'Start':>7} {'Income':>7} {'Total':>7} {'Count':>7} {'Var':>7}",
            "-" * 38,
        ]
        for method in self.PAYMENT_ROWS:
            r = self.PAYMENT_ROWS.index(method)
            def _v(col):
                it = self.table.item(r, col)
                return it.text() if it else "0.00"
            lines.append(
                f"{method:<12} {_v(1):>7} {_v(2):>7} {_v(3):>7} {_v(4):>7} {_v(5):>7}"
            )
        lines += [
            "-" * 38,
            f"Door Counter: {data['door_counter']}   Customers: {data['customers']}",
            "=" * 38,
        ]
        msg = QMessageBox(self)
        msg.setWindowTitle("Shift Receipt")
        msg.setText("\n".join(lines))
        msg.setStyleSheet(f"""
            QMessageBox {{ background:{WHITE}; }}
            QLabel {{ color:{DARK_TEXT}; font-family:Courier New; font-size:12px; }}
            QPushButton {{
                background:{ACCENT}; color:{WHITE}; border:none;
                border-radius:6px; padding:8px 20px; min-width:80px;
            }}
        """)
        msg.exec()

    def _on_print(self):
        self._on_receipt()   # same content — hook to QPrinter later

    def _on_file(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Shift Report",
            f"shift_{self.shift_spin.value()}_{self.date_input.text().replace('/', '-')}.csv",
            "CSV Files (*.csv)"
        )
        if not path:
            return
        try:
            data = self._collect_all()
            with open(path, "w", newline="") as f:
                f.write("Method,Start $,Income $,Total $,Counted $,Variance $\n")
                for r, method in enumerate(self.PAYMENT_ROWS):
                    def _v(col):
                        it = self.table.item(r, col)
                        return it.text() if it else "0.00"
                    f.write(f"{method},{_v(1)},{_v(2)},{_v(3)},{_v(4)},{_v(5)}\n")
                f.write(f"\nDate,{data['date']}\n")
                f.write(f"Shift #,{data['shift_number']}\n")
                f.write(f"Cashier,{data['cashier']}\n")
                f.write(f"Start Time,{data['start_time']}\n")
                f.write(f"End Time,{data['end_time']}\n")
                f.write(f"Door Counter,{data['door_counter']}\n")
                f.write(f"Customers,{data['customers']}\n")
            _msgbox(self, "Exported", f"✅  Saved to:\n{path}")
        except Exception as e:
            _msgbox(self, "Export Error", str(e), DANGER)

    # =========================================================================
    # DATA COLLECTORS
    # =========================================================================
    def _collect_start_values(self) -> dict:
        result = {}
        for r, method in enumerate(self.PAYMENT_ROWS):
            it = self.table.item(r, 1)
            try:
                result[method] = float(it.text() or "0") if it else 0.0
            except ValueError:
                result[method] = 0.0
        return result

    def _collect_counted_values(self) -> dict:
        result = {}
        for r, method in enumerate(self.PAYMENT_ROWS):
            it = self.table.item(r, 4)
            try:
                result[method] = float(it.text() or "0") if it else 0.0
            except ValueError:
                result[method] = 0.0
        return result

    def _collect_all(self) -> dict:
        return {
            "date":         self.date_input.text(),
            "station":      self.station_spin.value(),
            "shift_number": self.shift_spin.value(),
            "cashier":      self.user["username"],
            "start_time":   self.start_time_lbl.text(),
            "end_time":     self.end_time_lbl.text(),
            "door_counter": self.door_counter.text(),
            "customers":    self.customers_input.text(),
        }

    # =========================================================================
    # KEYBOARD
    # =========================================================================
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F2:
            self._on_save()
        elif event.key() == Qt.Key_F3:
            self._on_print()
        elif event.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)