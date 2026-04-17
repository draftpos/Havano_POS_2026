# =============================================================================
# views/dialogs/day_shift_dialog.py — Clean shift manager without icons
# =============================================================================
from datetime import date as _date
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame, QAbstractItemView, QMessageBox
)
from PySide6.QtCore import Qt, QTimer, QTime
from PySide6.QtGui import QFont, QColor

NAVY      = "#0d1f3c"
NAVY_2    = "#162d52"
ACCENT    = "#1a5fb4"
WHITE     = "#ffffff"
OFF_WHITE = "#f8fafc"
LIGHT     = "#eef2f7"
BORDER    = "#d1d9e6"
DARK_TEXT = "#1e293b"
MUTED     = "#64748b"
SUCCESS   = "#10b981"
SUCCESS_H = "#059669"
DANGER    = "#b02020"
DANGER_H  = "#cc2828"
ORANGE    = "#c05a00"
GOLD      = "#f59e0b"


class DayShiftDialog(QDialog):
    def __init__(self, parent=None, user=None):
        super().__init__(parent)
        self.user = user or {"id": None, "username": "admin"}
        self._shift_id = None
        self._elapsed_secs = 0
        self._is_started = False

        self.PAYMENT_ROWS = self._load_payment_methods()

        self.setFixedSize(900, 600)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setStyleSheet(f"""
            QDialog {{ 
                background: {WHITE};
                border: 1px solid {BORDER};
                border-radius: 12px;
            }}
        """)

        self._build_ui()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

        # Live income refresh every 30 seconds while shift is open
        self._income_timer = QTimer(self)
        self._income_timer.setInterval(30_000)
        self._income_timer.timeout.connect(self._refresh_income_display)

    def _load_payment_methods(self) -> list:
        """Load all GL account names — no type filter, matches payment dialog."""
        try:
            from models.gl_account import get_all_accounts
            accounts = get_all_accounts() or []
            methods = [a["name"] for a in accounts if a.get("name")]
            if methods:
                return methods
        except Exception as e:
            print(f"Error loading GL accounts: {e}")
        return ["CASH", "CHECK", "CREDIT CARD", "EFTPOS", "BANK TRANSFER"]

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Top Header ──────────────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(70)
        header.setStyleSheet(f"""
            background: {NAVY};
            border-top-left-radius: 12px;
            border-top-right-radius: 12px;
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
        header_layout.addSpacing(10)
        header_layout.addWidget(self.close_btn)
        
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

        self.table.setRowCount(len(self.PAYMENT_ROWS))
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

        root.addWidget(self.table)

        # ── Footer with Total Summary ─────────────────────────────────────────
        footer = QWidget()
        footer.setFixedHeight(50)
        footer.setStyleSheet(f"""
            background: {LIGHT};
            border-top: 1px solid {BORDER};
            border-bottom-left-radius: 12px;
            border-bottom-right-radius: 12px;
        """)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(25, 0, 25, 0)
        
        self.total_opening_label = QLabel("Opening: $0.00")
        self.total_opening_label.setStyleSheet(f"font-weight: bold; color: {NAVY}; font-size: 12px;")
        
        self.total_income_label = QLabel("Income: $0.00")
        self.total_income_label.setStyleSheet(f"font-weight: bold; color: {SUCCESS}; font-size: 12px;")
        
        self.total_label = QLabel("Total: $0.00")
        self.total_label.setStyleSheet(f"font-weight: bold; color: {ACCENT}; font-size: 13px;")
        
        footer_layout.addWidget(self.total_opening_label)
        footer_layout.addWidget(self.total_income_label)
        footer_layout.addStretch()
        footer_layout.addWidget(self.total_label)
        
        root.addWidget(footer)

    def _update_totals(self):
        """Update footer totals based on current table data"""
        total_opening = 0.0
        total_income = 0.0
        total_all = 0.0
        
        for row in range(self.table.rowCount()):
            try:
                opening = float(self.table.item(row, 1).text() or "0")
                income = float(self.table.item(row, 2).text() or "0")
                total = opening + income
                
                total_opening += opening
                total_income += income
                total_all += total
            except (ValueError, AttributeError):
                pass
        
        self.total_opening_label.setText(f"Opening: ${total_opening:,.2f}")
        self.total_income_label.setText(f"Income: ${total_income:,.2f}")
        self.total_label.setText(f"Total: ${total_all:,.2f}")

    def _tick(self):
        self._elapsed_secs += 1
        hours = self._elapsed_secs // 3600
        minutes = (self._elapsed_secs % 3600) // 60
        seconds = self._elapsed_secs % 60
        self.timer_lbl.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")

    def _on_start(self):
        opening_floats = {}
        for row in range(self.table.rowCount()):
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
        for row in range(self.table.rowCount()):
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
        self.start_btn.setEnabled(False)
        self.start_btn.setText("Recording")
        self.status_label.setText("● Shift Active")
        self.status_label.setStyleSheet(f"color: {SUCCESS}; font-size: 11px; font-weight: bold;")
        self.close_btn.setFocus()
        
        # Update totals
        self._update_totals()

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
            
            for row in range(self.table.rowCount()):
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
                    self.start_btn.setEnabled(False)
                    self.start_btn.setText("Recording")
                    self.status_label.setText("● Shift Active")
                    self.status_label.setStyleSheet(f"color: {SUCCESS}; font-size: 11px; font-weight: bold;")
                    
                    # Load opening floats
                    for row in range(self.table.rowCount()):
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
        except Exception as e:
            print(f"Error checking active shift: {e}")