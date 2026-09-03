from __future__ import annotations
from typing import Optional
from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QWidget, QLineEdit, QDateEdit
)

# Havano Palette
from theme import *

def _btn(text, bg, hov):
    b = QPushButton(text)
    b.setFixedHeight(34)
    b.setCursor(Qt.PointingHandCursor)
    b.setStyleSheet(f"""
        QPushButton {{
            background:{bg}; color:{WHITE}; border:none; border-radius:6px;
            font-size:12px; font-weight:bold; padding:0 14px;
        }}
        QPushButton:hover {{ background:{hov}; }}
    """)
    return b

class ExchangeRateDialog(QDialog):
    """Manage all exchange rates globally."""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Exchange Rates")
        self.resize(700, 500)
        self.setStyleSheet(f"QDialog {{ background:{WHITE}; }}")
        self._build()
        self._reload()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        hdr = QWidget(); hdr.setFixedHeight(80); hdr.setStyleSheet(f"background:{NAVY};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(20, 0, 20, 0)
        
        v = QVBoxLayout(); v.setSpacing(2); v.setAlignment(Qt.AlignVCenter)
        title = QLabel("EXCHANGE RATES")
        title.setStyleSheet(f"color:{WHITE}; font-size:18px; font-weight:bold;")
        sub = QLabel("Manage currency conversion rates to USD")
        sub.setStyleSheet(f"color:{MUTED}; font-size:11px;")
        v.addWidget(title); v.addWidget(sub)
        hl.addLayout(v)
        hl.addStretch()

        self._close_btn = _btn("Close", MUTED, "#6a8aaa")
        self._close_btn.clicked.connect(self.accept)
        hl.addWidget(self._close_btn)
        root.addWidget(hdr)

        # Content
        body = QWidget(); bl = QVBoxLayout(body); bl.setContentsMargins(20, 20, 20, 20)
        
        # Form
        fl = QHBoxLayout(); fl.setSpacing(10)
        self._f_from = QLineEdit()
        self._f_from.setPlaceholderText("From (e.g. ZAR)")
        self._f_from.setFixedHeight(34)
        self._f_from.setMaxLength(5)

        self._f_to = QLineEdit("USD")
        self._f_to.setPlaceholderText("To")
        self._f_to.setFixedHeight(34)
        self._f_to.setFixedWidth(60)

        self._f_rate = QLineEdit()
        self._f_rate.setPlaceholderText("Rate")
        self._f_rate.setFixedHeight(34)

        self._f_date = QDateEdit()
        self._f_date.setCalendarPopup(True)
        self._f_date.setDate(QDate.currentDate())
        self._f_date.setFixedHeight(34)

        add_btn = _btn("+ Add Rate", SUCCESS, SUCCESS_H)
        add_btn.clicked.connect(self._on_add)

        fl.addWidget(self._f_from, 2)
        fl.addWidget(QLabel("->"))
        fl.addWidget(self._f_to, 1)
        fl.addWidget(self._f_rate, 1)
        fl.addWidget(self._f_date, 2)
        fl.addWidget(add_btn)
        bl.addLayout(fl)
        bl.addSpacing(15)

        # Table
        self._tbl = QTableWidget(0, 5)
        self._tbl.setHorizontalHeaderLabels(["From", "To", "Rate", "Date", "Action"])
        self._tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._tbl.verticalHeader().setVisible(False)
        self._tbl.setAlternatingRowColors(True)
        self._tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tbl.setStyleSheet(f"""
            QTableWidget {{ background:{WHITE}; border:1px solid {BORDER}; }}
            QHeaderView::section {{ background:{OFF_WHITE}; font-weight:bold; padding:8px; }}
        """)
        bl.addWidget(self._tbl)
        
        root.addWidget(body)

    def _reload(self):
        self._tbl.setRowCount(0)
        try:
            from models.exchange_rate import get_all_rates
            rows = get_all_rates()
            for r in rows:
                idx = self._tbl.rowCount()
                self._tbl.insertRow(idx)
                self._tbl.setItem(idx, 0, QTableWidgetItem(r['from_currency']))
                self._tbl.setItem(idx, 1, QTableWidgetItem(r['to_currency']))
                
                rate_val = float(r['rate'])
                p_item = QTableWidgetItem(f"{rate_val:.6f}")
                p_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self._tbl.setItem(idx, 2, p_item)

                date_str = r.get('rate_date')
                if hasattr(date_str, 'strftime'):
                    date_str = date_str.strftime("%Y-%m-%d")
                self._tbl.setItem(idx, 3, QTableWidgetItem(str(date_str)))

                del_btn = QPushButton("Delete")
                del_btn.setStyleSheet(f"color:{DANGER}; border:none; background:transparent; font-weight:bold;")
                del_btn.setCursor(Qt.PointingHandCursor)
                # Note: exchange_rate model doesn't have a delete by ID yet, we'll need to add it or use currencies
                del_btn.clicked.connect(lambda _, curr=r['from_currency'], d=date_str: self._on_delete(curr, d))
                self._tbl.setCellWidget(idx, 4, del_btn)
        except Exception as e:
            print(f"Error loading rates: {e}")

    def _on_add(self):
        frm = self._f_from.text().strip().upper()
        to = self._f_to.text().strip().upper()
        rate_txt = self._f_rate.text().strip()
        dt = self._f_date.date().toString("yyyy-MM-dd")
        
        if not frm or not to or not rate_txt:
            QMessageBox.warning(self, "Required", "All fields are required.")
            return
        
        try:
            val = float(rate_txt)
            from models.exchange_rate import upsert_rate
            upsert_rate(frm, to, val, dt)
            self._f_rate.clear()
            self._f_from.clear()
            self._reload()
        except ValueError:
            QMessageBox.warning(self, "Invalid Rate", "Please enter a valid number.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save rate: {e}")

    def _on_delete(self, curr, dt):
        if QMessageBox.question(self, "Confirm", f"Delete rate for {curr} on {dt}?") == QMessageBox.Yes:
            try:
                # We'll need to implement a delete in models/exchange_rate.py
                from database.db import get_connection
                conn = get_connection(); cur = conn.cursor()
                cur.execute("DELETE FROM exchange_rates WHERE from_currency = ? AND rate_date = ?", (curr, dt))
                conn.commit(); conn.close()
                self._reload()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete: {e}")
