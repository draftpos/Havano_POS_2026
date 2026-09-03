# views/dialogs/tax_rules_dialog.py
from __future__ import annotations
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QWidget, QLineEdit, QCheckBox
)
from models.tax_rule import TaxRule, TaxRuleRepository

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

class TaxRulesDialog(QDialog):
    """Manage offline tax rules globally."""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Tax Settings")
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
        title = QLabel("TAX SETTINGS")
        title.setStyleSheet(f"color:{WHITE}; font-size:18px; font-weight:bold;")
        sub = QLabel("Manage offline tax categories and rates")
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
        self._f_name = QLineEdit()
        self._f_name.setPlaceholderText("Tax Name (e.g. VAT)")
        self._f_name.setFixedHeight(34)

        self._f_rate = QLineEdit()
        self._f_rate.setPlaceholderText("Rate (e.g. 15.0)")
        self._f_rate.setFixedHeight(34)
        self._f_rate.setFixedWidth(120)

        self._f_default = QCheckBox("Set Default")
        self._f_default.setFixedHeight(34)
        self._f_default.setStyleSheet(f"color: {DARK_TEXT}; font-weight: bold;")

        add_btn = _btn("+ Add Tax", SUCCESS, SUCCESS_H)
        add_btn.clicked.connect(self._on_add)

        fl.addWidget(self._f_name, 2)
        fl.addWidget(self._f_rate, 1)
        fl.addWidget(self._f_default, 1)
        fl.addWidget(add_btn)
        bl.addLayout(fl)
        bl.addSpacing(15)

        # Table
        self._tbl = QTableWidget(0, 4)
        self._tbl.setHorizontalHeaderLabels(["Tax Name", "Rate (%)", "Default", "Action"])
        self._tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._tbl.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._tbl.verticalHeader().setVisible(False)
        self._tbl.setAlternatingRowColors(True)
        self._tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tbl.setStyleSheet(f"""
            QTableWidget {{ background:{WHITE}; border:1px solid {BORDER}; color:{DARK_TEXT}; }}
            QHeaderView::section {{ background:{OFF_WHITE}; font-weight:bold; padding:8px; color:{DARK_TEXT}; border:none; }}
            QTableWidget::item {{ padding: 5px; }}
        """)
        bl.addWidget(self._tbl)
        
        root.addWidget(body)

    def _reload(self):
        self._tbl.setRowCount(0)
        try:
            rules = TaxRuleRepository.get_all()
            for r in rules:
                idx = self._tbl.rowCount()
                self._tbl.insertRow(idx)
                
                self._tbl.setItem(idx, 0, QTableWidgetItem(r.tax_name))
                
                rate_item = QTableWidgetItem(f"{r.tax_rate:.2f}")
                rate_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self._tbl.setItem(idx, 1, rate_item)
                
                def_item = QTableWidgetItem("Yes" if r.is_default else "No")
                def_item.setTextAlignment(Qt.AlignCenter)
                if r.is_default:
                    def_item.setForeground(Qt.green)
                self._tbl.setItem(idx, 2, def_item)

                del_btn = QPushButton("Delete")
                del_btn.setStyleSheet(f"color:{DANGER}; border:none; background:transparent; font-weight:bold;")
                del_btn.setCursor(Qt.PointingHandCursor)
                del_btn.clicked.connect(lambda _, rule_id=r.id, name=r.tax_name: self._on_delete(rule_id, name))
                self._tbl.setCellWidget(idx, 3, del_btn)
        except Exception as e:
            print(f"Error loading tax rules: {e}")

    def _on_add(self):
        name = self._f_name.text().strip()
        rate_txt = self._f_rate.text().strip()
        
        if not name:
            QMessageBox.warning(self, "Required", "Tax Name is required.")
            return
            
        try:
            rate_val = float(rate_txt or "0")
            rule = TaxRule(
                tax_name=name,
                tax_rate=rate_val,
                is_default=self._f_default.isChecked()
            )
            TaxRuleRepository.save(rule)
            
            self._f_name.clear()
            self._f_rate.clear()
            self._f_default.setChecked(False)
            self._reload()
        except ValueError:
            QMessageBox.warning(self, "Invalid Rate", "Please enter a valid number for Tax Rate.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save tax rule: {e}")

    def _on_delete(self, rule_id, name):
        if QMessageBox.question(self, "Confirm", f"Delete tax rule '{name}'?") == QMessageBox.Yes:
            try:
                TaxRuleRepository.delete(rule_id)
                self._reload()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete: {e}")
