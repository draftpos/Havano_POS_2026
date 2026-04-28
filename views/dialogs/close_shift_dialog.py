# # =============================================================================
# # views/dialogs/close_shift_dialog.py
# # =============================================================================

# from PySide6.QtWidgets import (
#     QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
#     QPushButton, QLabel, QLineEdit, QTableWidget,
#     QTableWidgetItem, QHeaderView, QAbstractItemView, QMessageBox,
#     QDateTimeEdit, QGroupBox
# )
# # from PySide6.QtCore import Qt, QDateTime, QTimer
# from PySide6.QtGui import QDoubleValidator, QColor

# # Import colors
# NAVY      = "#0d1f3c"
# NAVY_2    = "#162d52"
# NAVY_3    = "#1e3d6e"
# ACCENT    = "#1a5fb4"
# ACCENT_H  = "#1c6dd0"
# WHITE     = "#ffffff"
# OFF_WHITE = "#f5f8fc"
# LIGHT     = "#e4eaf4"
# MID       = "#8fa8c8"
# DARK_TEXT = "#0d1f3c"
# MUTED     = "#5a7a9a"
# BORDER    = "#c8d8ec"
# ROW_ALT   = "#edf3fb"
# SUCCESS   = "#1a7a3c"
# SUCCESS_H = "#1f9447"
# DANGER    = "#b02020"
# DANGER_H  = "#cc2828"
# ORANGE    = "#c05a00"
# AMBER     = "#b06000"


# def navy_btn(text, height=36, font_size=12, width=None, color=None, hover=None):
#     bg  = color or NAVY
#     hov = hover or NAVY_2
#     btn = QPushButton(text)
#     btn.setFixedHeight(height)
#     if width:
#         btn.setFixedWidth(width)
#     btn.setCursor(Qt.PointingHandCursor)
#     btn.setStyleSheet(f"""
#         QPushButton {{
#             background-color: {bg}; color: {WHITE}; border: none;
#             border-radius: 5px; font-size: {font_size}px; font-weight: bold; padding: 0 14px;
#         }}
#         QPushButton:hover   {{ background-color: {hov}; }}
#         QPushButton:pressed {{ background-color: {NAVY_3}; }}
#     """)
#     return btn


# def hr():
#     from PySide6.QtWidgets import QFrame
#     line = QFrame()
#     line.setFrameShape(QFrame.HLine)
#     line.setStyleSheet(f"background-color: {BORDER}; border: none;")
#     line.setFixedHeight(1)
#     return line


# class CloseShiftDialog(QDialog):
#     def __init__(self, parent=None, user=None):
#         super().__init__(parent)
#         self.user = user or {}
#         self.setWindowTitle("Close Shift")
#         self.setMinimumSize(700, 600)
#         self.setStyleSheet(f"QDialog {{ background-color: {WHITE}; }}")
#         self._build()
#         self._load_shift_data()

#     def _build(self):
#         layout = QVBoxLayout(self)
#         layout.setSpacing(12)
#         layout.setContentsMargins(20, 16, 20, 16)

#         # Header
#         hdr = QWidget()
#         hdr.setFixedHeight(44)
#         hdr.setStyleSheet(f"background-color: {NAVY}; border-radius: 5px;")
#         hl = QHBoxLayout(hdr)
#         hl.setContentsMargins(16, 0, 16, 0)
#         title = QLabel("Close Shift")
#         title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {WHITE}; background: transparent;")

#         shift_info = QLabel(f"Cashier: {self.user.get('username', 'Unknown')}")
#         shift_info.setStyleSheet(f"font-size: 12px; color: {MID}; background: transparent;")

#         hl.addWidget(title)
#         hl.addStretch()
#         hl.addWidget(shift_info)
#         layout.addWidget(hdr)

#         # Shift Information
#         info_group = QGroupBox("Shift Information")
#         info_group.setStyleSheet(f"""
#             QGroupBox {{
#                 font-weight: bold; border: 1px solid {BORDER}; border-radius: 5px;
#                 margin-top: 10px; padding-top: 10px;
#             }}
#             QGroupBox::title {{
#                 subcontrol-origin: margin; left: 10px; padding: 0 5px 0 5px;
#                 color: {NAVY}; background: transparent;
#             }}
#         """)
#         info_layout = QGridLayout(info_group)
#         info_layout.setSpacing(10)
#         info_layout.setContentsMargins(16, 16, 16, 16)

#         # Shift start time
#         start_lbl = QLabel("Shift Started:")
#         start_lbl.setStyleSheet(f"color: {MUTED}; font-size: 13px; background: transparent;")
#         self._start_time = QLabel("--")
#         self._start_time.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {DARK_TEXT}; background: transparent;")
#         info_layout.addWidget(start_lbl, 0, 0)
#         info_layout.addWidget(self._start_time, 0, 1)

#         # Current time
#         current_lbl = QLabel("Current Time:")
#         current_lbl.setStyleSheet(f"color: {MUTED}; font-size: 13px; background: transparent;")
#         self._current_time = QLabel(QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss"))
#         self._current_time.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {DARK_TEXT}; background: transparent;")
#         info_layout.addWidget(current_lbl, 0, 2)
#         info_layout.addWidget(self._current_time, 0, 3)

#         # Shift duration
#         duration_lbl = QLabel("Shift Duration:")
#         duration_lbl.setStyleSheet(f"color: {MUTED}; font-size: 13px; background: transparent;")
#         self._duration = QLabel("--")
#         self._duration.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {DARK_TEXT}; background: transparent;")
#         info_layout.addWidget(duration_lbl, 1, 0)
#         info_layout.addWidget(self._duration, 1, 1)

#         # Invoice count — running total of finalised sales in this shift.
#         # Populated by _load_shift_data; also printed on the shift summary.
#         invoices_lbl = QLabel("Invoices:")
#         invoices_lbl.setStyleSheet(f"color: {MUTED}; font-size: 13px; background: transparent;")
#         self._invoice_count = QLabel("0")
#         self._invoice_count.setStyleSheet(
#             f"font-size: 14px; font-weight: bold; color: {NAVY}; background: transparent;"
#         )
#         info_layout.addWidget(invoices_lbl,        1, 2)
#         info_layout.addWidget(self._invoice_count, 1, 3)

#         layout.addWidget(info_group)

#         # Sales Summary
#         sales_group = QGroupBox("Sales Summary")
#         sales_group.setStyleSheet(f"""
#             QGroupBox {{
#                 font-weight: bold; border: 1px solid {BORDER}; border-radius: 5px;
#                 margin-top: 10px; padding-top: 10px;
#             }}
#             QGroupBox::title {{
#                 subcontrol-origin: margin; left: 10px; padding: 0 5px 0 5px;
#                 color: {NAVY}; background: transparent;
#             }}
#         """)
#         sales_layout = QGridLayout(sales_group)
#         sales_layout.setSpacing(10)
#         sales_layout.setContentsMargins(16, 16, 16, 16)

#         # Sales by payment method
#         sales_layout.addWidget(QLabel("Payment Method"), 0, 0)
#         sales_layout.addWidget(QLabel("Count"), 0, 1)
#         sales_layout.addWidget(QLabel("Total"), 0, 2)
#         sales_layout.addWidget(QLabel("Expected"), 0, 3)

#         self._method_rows = {}

#         methods = ["Cash", "Card", "Mobile", "Credit", "Other"]
#         for i, method in enumerate(methods):
#             lbl = QLabel(method)
#             lbl.setStyleSheet(f"color: {DARK_TEXT}; font-size: 13px; background: transparent;")

#             count_lbl = QLabel("0")
#             count_lbl.setAlignment(Qt.AlignRight)
#             count_lbl.setStyleSheet(f"color: {DARK_TEXT}; font-size: 13px; background: transparent;")

#             total_lbl = QLabel("$0.00")
#             total_lbl.setAlignment(Qt.AlignRight)
#             total_lbl.setStyleSheet(f"color: {DARK_TEXT}; font-size: 13px; font-weight: bold; background: transparent;")

#             expected_edit = QLineEdit("0.00")
#             expected_edit.setFixedHeight(30)
#             expected_edit.setAlignment(Qt.AlignRight)
#             expected_edit.setValidator(QDoubleValidator(0.0, 999999.99, 2))
#             expected_edit.textChanged.connect(self._calculate_variance)

#             sales_layout.addWidget(lbl, i + 1, 0)
#             sales_layout.addWidget(count_lbl, i + 1, 1)
#             sales_layout.addWidget(total_lbl, i + 1, 2)
#             sales_layout.addWidget(expected_edit, i + 1, 3)

#             self._method_rows[method] = {
#                 "count": count_lbl,
#                 "total": total_lbl,
#                 "expected": expected_edit
#             }

#         # Totals
#         sales_layout.addWidget(hr(), len(methods) + 1, 0, 1, 4)

#         total_sales_lbl = QLabel("Total Sales:")
#         total_sales_lbl.setStyleSheet(f"color: {NAVY}; font-size: 14px; font-weight: bold; background: transparent;")

#         self._total_sales = QLabel("$0.00")
#         self._total_sales.setAlignment(Qt.AlignRight)
#         self._total_sales.setStyleSheet(f"color: {NAVY}; font-size: 14px; font-weight: bold; background: transparent;")

#         sales_layout.addWidget(total_sales_lbl, len(methods) + 2, 0, 1, 2)
#         sales_layout.addWidget(self._total_sales, len(methods) + 2, 2, 1, 2)

#         layout.addWidget(sales_group)

#         # Variance
#         variance_group = QGroupBox("Variance")
#         variance_group.setStyleSheet(f"""
#             QGroupBox {{
#                 font-weight: bold; border: 1px solid {BORDER}; border-radius: 5px;
#                 margin-top: 10px; padding-top: 10px;
#             }}
#             QGroupBox::title {{
#                 subcontrol-origin: margin; left: 10px; padding: 0 5px 0 5px;
#                 color: {NAVY}; background: transparent;
#             }}
#         """)
#         variance_layout = QGridLayout(variance_group)
#         variance_layout.setSpacing(10)
#         variance_layout.setContentsMargins(16, 16, 16, 16)

#         variance_layout.addWidget(QLabel("Total Expected:"), 0, 0)
#         self._total_expected = QLabel("$0.00")
#         self._total_expected.setAlignment(Qt.AlignRight)
#         self._total_expected.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {DARK_TEXT}; background: transparent;")
#         variance_layout.addWidget(self._total_expected, 0, 1)

#         variance_layout.addWidget(QLabel("Total Actual:"), 1, 0)
#         self._total_actual = QLabel("$0.00")
#         self._total_actual.setAlignment(Qt.AlignRight)
#         self._total_actual.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {DARK_TEXT}; background: transparent;")
#         variance_layout.addWidget(self._total_actual, 1, 1)

#         variance_layout.addWidget(QLabel("Variance:"), 2, 0)
#         self._variance = QLabel("$0.00")
#         self._variance.setAlignment(Qt.AlignRight)
#         self._variance.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {DARK_TEXT}; background: transparent;")
#         variance_layout.addWidget(self._variance, 2, 1)

#         layout.addWidget(variance_group)

#         # Notes
#         notes_lbl = QLabel("Shift Notes:")
#         notes_lbl.setStyleSheet(f"color: {MUTED}; font-size: 13px; background: transparent;")
#         layout.addWidget(notes_lbl)

#         self._notes_edit = QLineEdit()
#         self._notes_edit.setPlaceholderText("Any notes about this shift...")
#         self._notes_edit.setFixedHeight(34)
#         self._notes_edit.setStyleSheet(f"""
#             QLineEdit {{
#                 background-color: {WHITE}; color: {DARK_TEXT};
#                 border: 1px solid {BORDER}; border-radius: 5px;
#                 padding: 6px 10px; font-size: 13px;
#             }}
#             QLineEdit:focus {{ border: 2px solid {ACCENT}; }}
#         """)
#         layout.addWidget(self._notes_edit)

#         layout.addWidget(hr())

#         # Button row
#         btn_row = QHBoxLayout()
#         btn_row.setSpacing(8)

#         self._status = QLabel("")
#         self._status.setStyleSheet(f"font-size: 12px; color: {SUCCESS}; background: transparent;")

#         close_btn = navy_btn("Close Shift", height=38, color=SUCCESS, hover=SUCCESS_H)
#         close_btn.clicked.connect(self._close_shift)

#         cancel_btn = navy_btn("Cancel", height=38, color=NAVY_2, hover=NAVY_3)
#         cancel_btn.clicked.connect(self.reject)

#         btn_row.addWidget(self._status, 1)
#         btn_row.addWidget(close_btn)
#         btn_row.addWidget(cancel_btn)
#         layout.addLayout(btn_row)

#         # Timer to update current time
#         self._timer = QTimer(self)
#         self._timer.timeout.connect(self._update_time)
#         self._timer.start(1000)

#     def _load_shift_data(self):
#         try:
#             from models.shift import get_current_shift, get_shift_sales_by_method

#             shift = get_current_shift(self.user.get("id"))
#             if shift:
#                 self._start_time.setText(shift.get("start_time", "--"))
#                 self._duration.setText(shift.get("duration", "--"))

#                 # Load sales by method
#                 sales_by_method = get_shift_sales_by_method(shift["id"])
#                 total_sales = 0.0
#                 total_invoices = 0

#                 for method, data in sales_by_method.items():
#                     if method in self._method_rows:
#                         self._method_rows[method]["count"].setText(str(data["count"]))
#                         self._method_rows[method]["total"].setText(f"${data['total']:.2f}")
#                         total_sales    += data["total"]
#                         total_invoices += int(data.get("count") or 0)

#                 self._total_sales.setText(f"${total_sales:.2f}")
#                 self._total_actual.setText(f"${total_sales:.2f}")
#                 # Method counts overlap when a single sale is split across
#                 # methods, so prefer a direct DB count when we can.
#                 self._invoice_count.setText(
#                     str(self._direct_invoice_count(shift["id"]) or total_invoices)
#                 )
#             else:
#                 # No active shift - show message
#                 self._start_time.setText("No active shift")

#         except Exception as e:
#             print(f"Error loading shift data: {e}")
#             # Demo data
#             self._start_time.setText("2024-01-15 08:30:00")
#             self._duration.setText("7h 30m")

#             demo_data = {
#                 "Cash": {"count": 15, "total": 1250.50},
#                 "Card": {"count": 8, "total": 890.00},
#                 "Mobile": {"count": 5, "total": 320.75},
#                 "Credit": {"count": 2, "total": 150.00},
#                 "Other": {"count": 0, "total": 0.00}
#             }

#             total = 0.0
#             for method, data in demo_data.items():
#                 if method in self._method_rows:
#                     self._method_rows[method]["count"].setText(str(data["count"]))
#                     self._method_rows[method]["total"].setText(f"${data['total']:.2f}")
#                     total += data["total"]

#             self._total_sales.setText(f"${total:.2f}")
#             self._total_actual.setText(f"${total:.2f}")

#     def _direct_invoice_count(self, shift_id: int) -> int | None:
#         """Authoritative count — one row per finalised sale for this shift."""
#         try:
#             from database.db import get_connection
#             conn = get_connection()
#             cur  = conn.cursor()
#             cur.execute(
#                 "SELECT COUNT(*) FROM sales WHERE shift_id = ?",
#                 (int(shift_id),),
#             )
#             row = cur.fetchone()
#             conn.close()
#             return int(row[0]) if row and row[0] is not None else None
#         except Exception as e:
#             print(f"[close-shift] invoice count lookup failed: {e}")
#             return None

#     def _update_time(self):
#         self._current_time.setText(QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss"))

#     def _calculate_variance(self):
#         total_expected = 0.0

#         for method, widgets in self._method_rows.items():
#             try:
#                 expected = float(widgets["expected"].text() or "0")
#             except ValueError:
#                 expected = 0.0
#             total_expected += expected

#         self._total_expected.setText(f"${total_expected:.2f}")

#         try:
#             total_actual = float(self._total_sales.text().replace("$", ""))
#         except ValueError:
#             total_actual = 0.0

#         variance = total_actual - total_expected
#         self._variance.setText(f"${variance:.2f}")

#         if variance > 0:
#             self._variance.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {SUCCESS}; background: transparent;")
#         elif variance < 0:
#             self._variance.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {DANGER}; background: transparent;")
#         else:
#             self._variance.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {DARK_TEXT}; background: transparent;")

#     def _close_shift(self):
#         # Collect expected amounts by method
#         expected_amounts = {}
#         for method, widgets in self._method_rows.items():
#             try:
#                 expected = float(widgets["expected"].text() or "0")
#             except ValueError:
#                 expected = 0.0
#             if expected > 0:
#                 expected_amounts[method] = expected

#         if not expected_amounts:
#             reply = QMessageBox.question(self, "Confirm Close Shift",
#                 "No expected amounts entered. Are you sure you want to close the shift?",
#                 QMessageBox.Yes | QMessageBox.No)
#             if reply != QMessageBox.Yes:
#                 return

#         try:
#             from models.shift import close_shift

#             total_actual = float(self._total_sales.text().replace("$", ""))
#             total_expected = float(self._total_expected.text().replace("$", ""))
#             variance = total_actual - total_expected

#             shift_data = {
#                 "cashier_id": self.user.get("id"),
#                 "cashier_name": self.user.get("username", ""),
#                 "end_time": QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss"),
#                 "total_sales": total_actual,
#                 "total_expected": total_expected,
#                 "variance": variance,
#                 "expected_by_method": expected_amounts,
#                 "notes": self._notes_edit.text().strip()
#             }

#             result = close_shift(shift_data)

#             if result:
#                 self._show_status(f"Shift closed. Variance: ${variance:.2f}")
#                 QTimer.singleShot(1500, self.accept)
#             else:
#                 self._show_status("Error closing shift.", error=True)

#         except Exception as e:
#             self._show_status(str(e), error=True)

#     def _show_status(self, msg, error=False):
#         color = DANGER if error else SUCCESS
#         self._status.setStyleSheet(f"font-size: 12px; color: {color}; background: transparent;")
#         self._status.setText(msg)