# =============================================================================
# views/dialogs/day_shift_dialog.py - Clean shift manager without icons
# =============================================================================
from datetime import date as _date
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame, QAbstractItemView, QMessageBox
)
from PySide6.QtCore import Qt, QTimer, QTime
from PySide6.QtGui import QFont, QColor
from theme import *


class DayShiftDialog(QDialog):
    def __init__(self, parent=None, user=None):
        super().__init__(parent)
        self.user = user or {"id": None, "username": "admin"}
        self._shift_id = None
        self._elapsed_secs = 0
        self._is_started = False

        self.PAYMENT_ROWS = self._load_payment_methods()

        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        self.setFixedSize(650, 550)
        self.setStyleSheet(f"""
            QDialog {{ 
                background: {WHITE};
            }}
        """)
        
        # Center the dialog relative to its parent, or the screen if no parent
        if parent:
            # Force it to be modal so it's always on top of the parent
            self.setWindowModality(Qt.WindowModal)
            center_point = parent.geometry().center()
            self.move(center_point.x() - self.width() // 2, center_point.y() - self.height() // 2)
        else:
            self.setWindowModality(Qt.ApplicationModal)

        self._build_ui()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

        # Live income refresh every 30 seconds while shift is open
        self._income_timer = QTimer(self)
        self._income_timer.setInterval(30_000)
        self._income_timer.timeout.connect(self._refresh_income_display)

    def _load_payment_methods(self) -> list:
        """
        Load payment methods from modes_of_payment - same source as the payment dialog.
        Only enabled MOPs with a valid gl_account (leaf accounts only) are included.
        Returns a list of MOP name strings.
        """
        try:
            from database.db import get_connection, fetchall_dicts, fetchone_dict
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT
                    m.name       AS mop_name,
                    m.gl_account AS gl_account
                FROM modes_of_payment m
                WHERE m.gl_account IS NOT NULL
                  AND m.gl_account <> \'\'
                  AND m.enabled = 1
                ORDER BY COALESCE(m.display_order, 0), m.name
            """)
            rows = fetchall_dicts(cur)
            allowed_methods = None
            cashier_id = self.user.get("id")
            if cashier_id:
                try:
                    cur.execute("SELECT allowed_payment_methods FROM users WHERE id=?", (cashier_id,))
                    urow = fetchone_dict(cur)
                    if urow and urow.get("allowed_payment_methods"):
                        pm_str = urow["allowed_payment_methods"]
                        if pm_str != "ALL":
                            allowed_methods = [x.strip().lower() for x in pm_str.split(",")]
                except Exception as e:
                    print(f"Error fetching allowed payment methods: {e}")
                    
            conn.close()

            methods = []
            seen = set()
            for row in rows:
                mop_name   = (row.get("mop_name")   or "").strip()
                gl_account = (row.get("gl_account") or "").strip()
                if not mop_name or not gl_account:
                    continue
                if allowed_methods is not None and mop_name.lower() not in allowed_methods:
                    continue
                # Skip group GL accounts (same logic as payment dialog)
                try:
                    from database.db import get_connection as _gc, fetchone_dict as _fd
                    _conn = _gc(); _cur = _conn.cursor()
                    _cur.execute(
                        "SELECT account_type FROM gl_accounts WHERE name = ?",
                        (gl_account,)
                    )
                    _row = _fd(_cur)
                    _conn.close()
                    if _row is not None and (_row.get("account_type") or "").strip() == "":
                        continue  # group account - skip
                except Exception:
                    pass

                key = mop_name.lower()
                if key in seen:
                    continue
                seen.add(key)
                methods.append(mop_name)

            if methods:
                print(f"[DayShift] Loaded {len(methods)} payment methods: {methods}")
                return methods
        except Exception as e:
            print(f"[DayShift] Error loading payment methods: {e}")

        # If database is empty or fails, we return an empty list or a very minimal default
        # But the user specifically asked to remove hardcoded ones.
        return []

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Top Header ──────────────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(70)
        header.setStyleSheet(f"""
            background: {NAVY};
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(25, 0, 25, 0)

        # Title
        title_label = QLabel("Shift Manager")
        title_label.setStyleSheet(f"""
            color: {WHITE}; font-size: 18px; font-weight: bold;
            font-family: 'Segoe UI', Arial;
        """)
        
        # Timer
        self.timer_lbl = QLabel("00:00:00")
        self.timer_lbl.setStyleSheet(f"""
            font-family: 'Courier New', monospace; 
            font-size: 24px; 
            font-weight: bold; 
            color: {GOLD};
            background: rgba(255,255,255,0.1);
            padding: 5px 15px;
            border-radius: 8px;
        """)
        
        # Buttons
        self.start_btn = QPushButton("Start Session")
        self.start_btn.setFixedSize(140, 38)
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.setStyleSheet(f"""
            QPushButton {{
                background: {SUCCESS};
                color: white; 
                border-radius: 6px;
                font-weight: bold; 
                font-size: 12px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background: {SUCCESS_H};
            }}
            QPushButton:disabled {{
                background: {MUTED};
            }}
        """)
        self.start_btn.clicked.connect(self._on_start)

        self.close_btn = QPushButton("Close")
        self.close_btn.setFixedSize(80, 38)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                background: {MUTED};
                color: white;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background: {DANGER};
            }}
        """)
        self.close_btn.clicked.connect(self.reject)

        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.timer_lbl)
        header_layout.addSpacing(20)
        header_layout.addWidget(self.start_btn)
        # Close button removed - use the native title bar ✕ to close
        
        root.addWidget(header)

        # ── Status Bar ────────────────────────────────────────────────────────
        status_bar = QWidget()
        status_bar.setFixedHeight(36)
        status_bar.setStyleSheet(f"background: {OFF_WHITE}; border-bottom: 1px solid {BORDER};")
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(25, 0, 25, 0)
        
        self.status_label = QLabel("● Not Started")
        self.status_label.setStyleSheet(f"color: {DANGER}; font-size: 11px; font-weight: bold;")
        
        self.cashier_label = QLabel(f"Cashier: {self.user.get('username', 'Unknown')}")
        self.cashier_label.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
        
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        status_layout.addWidget(self.cashier_label)
        
        root.addWidget(status_bar)

        # ── Table ───────────────────────────────────────────────────────────
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Payment Method", "Opening Float", "Income", "Total"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setShowGrid(False)
        self.table.setStyleSheet(f"""
            QTableWidget {{ 
                background: {WHITE}; 
                border: none;
                margin: 10px;
            }}
            QHeaderView::section {{
                background: {LIGHT};
                color: {NAVY};
                padding: 10px;
                border: none;
                border-bottom: 2px solid {ACCENT};
                font-weight: bold;
                font-size: 11px;
            }}
            QTableWidget::item {{
                padding: 10px;
                color: {DARK_TEXT};
                font-size: 12px;
            }}
            QTableWidget::item:selected {{
                background: {OFF_WHITE};
            }}
        """)

        self.table.setRowCount(len(self.PAYMENT_ROWS) + 1)
        for r, method in enumerate(self.PAYMENT_ROWS):
            # Method name without icons
            method_item = QTableWidgetItem(method)
            font = QFont()
            font.setBold(True)
            method_item.setFont(font)
            self.table.setItem(r, 0, method_item)
            
            # Opening float (editable)
            opening_item = QTableWidgetItem("0.00")
            opening_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
            opening_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            opening_item.setForeground(QColor(NAVY))
            self.table.setItem(r, 1, opening_item)
            
            # Income (read-only)
            income_item = QTableWidgetItem("0.00")
            income_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            income_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            income_item.setForeground(QColor(SUCCESS))
            self.table.setItem(r, 2, income_item)
            
            # Total (read-only)
            total_item = QTableWidgetItem("0.00")
            total_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            total_item.setForeground(QColor(ACCENT))
            self.table.setItem(r, 3, total_item)

        # TOTAL inline row
        total_row_idx = len(self.PAYMENT_ROWS)
        tot_lbl_item = QTableWidgetItem("TOTAL")
        tot_font = QFont()
        tot_font.setBold(True)
        tot_lbl_item.setFont(tot_font)
        tot_lbl_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        tot_lbl_item.setBackground(QColor("#eceff1"))
        self.table.setItem(total_row_idx, 0, tot_lbl_item)
        
        for col in range(1, 4):
            item = QTableWidgetItem("0.00")
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item.setFont(tot_font)
            item.setBackground(QColor("#eceff1"))
            self.table.setItem(total_row_idx, col, item)

        root.addWidget(self.table)


    def _update_totals(self):
        """Update inline totals row based on current table data"""
        total_opening = 0.0
        total_income = 0.0
        total_all = 0.0
        
        for row in range(self.table.rowCount() - 1):
            try:
                opening = float(self.table.item(row, 1).text() or "0")
                income = float(self.table.item(row, 2).text() or "0")
                total = opening + income
                
                total_opening += opening
                total_income += income
                total_all += total
            except (ValueError, AttributeError):
                pass
        
        total_row_idx = self.table.rowCount() - 1
        self.table.item(total_row_idx, 1).setText(f"{total_opening:,.2f}")
        self.table.item(total_row_idx, 2).setText(f"{total_income:,.2f}")
        self.table.item(total_row_idx, 3).setText(f"{total_all:,.2f}")

    def _tick(self):
        self._elapsed_secs += 1
        hours = self._elapsed_secs // 3600
        minutes = (self._elapsed_secs % 3600) // 60
        seconds = self._elapsed_secs % 60
        self.timer_lbl.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")

    def _on_start(self):
        if self._is_started:
            self.accept()
            return
            
        opening_floats = {}
        for row in range(self.table.rowCount() - 1):
            method = self.table.item(row, 0).text()
            opening_item = self.table.item(row, 1)
            try:
                value = float(opening_item.text()) if opening_item and opening_item.text().strip() else 0.0
                if value < 0:
                    QMessageBox.warning(self, "Invalid Input",
                                        f"Opening float for {method} cannot be negative.")
                    return
                opening_floats[method.upper()] = value
            except ValueError:
                QMessageBox.warning(self, "Invalid Input",
                                    f"Please enter a valid number for {method}.")
                return

        try:
            from models.shift import start_shift, get_next_shift_number
            shift_number = get_next_shift_number()
            shift_data = start_shift(
                station=1,
                shift_number=shift_number,
                cashier_id=self.user.get("id"),
                date=_date.today().strftime("%Y-%m-%d"),
                opening_floats=opening_floats,
            )
            if not shift_data:
                raise RuntimeError("start_shift returned None")
            self._shift_id = shift_data.get("id")
        except Exception as e:
            QMessageBox.critical(self, "Error Starting Shift",
                                 f"Could not start shift: {str(e)}")
            return

        # Lock opening floats
        for row in range(self.table.rowCount() - 1):
            item = self.table.item(row, 1)
            if item:
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                item.setForeground(QColor(MUTED))

        # Start elapsed-time ticker
        self._timer.start(1000)

        # Immediately pull live income and then refresh every 30 s
        self._refresh_income_display()
        self._income_timer.start()
        
        # Update status
        self._is_started = True
        self.start_btn.setEnabled(True)
        self.start_btn.setText("Continue")
        self.start_btn.setStyleSheet(f"""
            QPushButton {{ background: {NAVY}; color: white; border-radius: 6px; font-weight: bold; font-size: 12px; padding: 8px 16px; }}
            QPushButton:hover {{ background: {NAVY_2}; }}
        """)
        self.status_label.setText("● Shift Active")
        self.status_label.setStyleSheet(f"color: {SUCCESS}; font-size: 11px; font-weight: bold;")
        self.start_btn.setFocus()
        
        # Update totals
        self._update_totals()

        # Check for Axis Fiscal Provider and prompt to Open Fiscal Day
        try:
            from models.fiscal_settings import FiscalSettingsRepository
            repo = FiscalSettingsRepository()
            settings = repo.get_settings()
            if settings and settings.enabled and settings.provider == "axis":
                from views.dialogs.axis_fiscal_dialog import AxisFiscalDialog
                # Run this after a tiny delay to ensure dialog rendering finishes nicely
                QTimer.singleShot(500, lambda: AxisFiscalDialog(self, initial_action="open").exec())
            elif settings and settings.enabled and settings.provider == "revmax":
                from views.dialogs.revmax_fiscal_dialog import RevmaxFiscalDialog
                QTimer.singleShot(500, lambda: RevmaxFiscalDialog(self, initial_action="open").exec())
        except Exception as e:
            print(f"[DayShift] Error showing Fiscal Dialog: {e}")

    def _refresh_income_display(self):
        """
        Pull the latest income from the DB and update columns 2 & 3.
        Called immediately after shift start and then every 30 seconds.
        """
        if not self._shift_id or not self._is_started:
            return
        try:
            from models.shift import refresh_income, get_shift_by_id
            refresh_income(self._shift_id)
            shift_data = get_shift_by_id(self._shift_id)
            if not shift_data:
                return
            
            # Create a map with case-insensitive matching
            row_map = {}
            for r in shift_data.get("rows", []):
                row_map[r["method"].upper()] = r
            
            for row in range(self.table.rowCount() - 1):
                method = self.table.item(row, 0).text().upper()
                sr = row_map.get(method)
                if sr:
                    # Update income
                    income_item = QTableWidgetItem(f"{sr['income']:,.2f}")
                    income_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    income_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    income_item.setForeground(QColor(SUCCESS))
                    self.table.setItem(row, 2, income_item)

                    # Update total
                    total_item = QTableWidgetItem(f"{sr['total']:,.2f}")
                    total_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    total_item.setForeground(QColor(ACCENT))
                    self.table.setItem(row, 3, total_item)
            
            # Update footer totals
            self._update_totals()
            
        except Exception as e:
            print(f"Income refresh error: {e}")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            if self._is_started:
                reply = QMessageBox.question(
                    self,
                    "Confirm Exit",
                    "Shift is currently active. Are you sure you want to close?\n"
                    "You can reopen the shift manager from the POS menu.",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    self.reject()
            else:
                self.reject()
        else:
            super().keyPressEvent(event)

    def showEvent(self, event):
        """Handle dialog show event"""
        super().showEvent(event)
        # Check if there's an active shift already
        try:
            from models.shift import get_active_shift
            active_shift = get_active_shift()
            if active_shift:
                reply = QMessageBox.question(
                    self,
                    "Active Shift Found",
                    f"There is already an active shift (Shift #{active_shift.get('shift_number')}).\n\n"
                    "Would you like to view the current shift status?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )
                if reply == QMessageBox.Yes:
                    # Load the active shift data
                    self._shift_id = active_shift.get("id")
                    self._is_started = True
                    self.start_btn.setEnabled(True)
                    self.start_btn.setText("Continue")
                    self.start_btn.setStyleSheet(f"""
                        QPushButton {{ background: {NAVY}; color: white; border-radius: 6px; font-weight: bold; font-size: 12px; padding: 8px 16px; }}
                        QPushButton:hover {{ background: {NAVY_2}; }}
                    """)
                    self.status_label.setText("● Shift Active")
                    self.status_label.setStyleSheet(f"color: {SUCCESS}; font-size: 11px; font-weight: bold;")
                    self.start_btn.setFocus()
                    
                    # Load opening floats
                    for row in range(self.table.rowCount() - 1):
                        method = self.table.item(row, 0).text().upper()
                        for sr in active_shift.get("rows", []):
                            if sr["method"].upper() == method:
                                opening_item = QTableWidgetItem(f"{sr['start_float']:.2f}")
                                opening_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                                opening_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                                opening_item.setForeground(QColor(MUTED))
                                self.table.setItem(row, 1, opening_item)
                                break
                    
                    # Start timers
                    self._timer.start(1000)
                    self._income_timer.start()
                    self._refresh_income_display()
                else:
                    self.reject() # close if they click No? Wait, if they don't want to view it, let's keep it open but they can close. Or we can just reject.
            else:
                # No active shift found, auto-start it silently!
                QTimer.singleShot(100, self._on_start)
        except Exception as e:
            print(f"Error checking active shift: {e}")