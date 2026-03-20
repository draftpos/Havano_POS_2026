# =============================================================================
# views/dialogs/settings_dialog.py
# =============================================================================
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QFrame, QLineEdit, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QMessageBox, QCheckBox, QScrollArea,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtPrintSupport import QPrinter, QPrinterInfo
from datetime import datetime
from models.advance_settings import AdvanceSettings
import json
import os as _os
# from views.dialogs.customer_dialog import CustomerDialog

# ── Palette ───────────────────────────────────────────────────────────────────
NAVY      = "#0d1f3c"
NAVY_2    = "#162d52"
NAVY_3    = "#1e3d6e"
ACCENT    = "#1a5fb4"
ACCENT_H  = "#1c6dd0"
WHITE     = "#ffffff"
OFF_WHITE = "#f5f8fc"
LIGHT     = "#e4eaf4"
MID       = "#8fa8c8"
DARK_TEXT = "#0d1f3c"
MUTED     = "#5a7a9a"
BORDER    = "#c8d8ec"
ROW_ALT   = "#edf3fb"
SUCCESS   = "#1a7a3c"
SUCCESS_H = "#1f9447"
DANGER    = "#b02020"
DANGER_H  = "#cc2828"

# ── Helpers ───────────────────────────────────────────────────────────────────

def _friendly_error(e):
    msg = str(e)
    if "REFERENCE constraint" in msg or "FK_" in msg or "foreign key" in msg.lower():
        return "Cannot delete — record is still linked to other data. Remove those links first."
    if "UNIQUE" in msg or "duplicate key" in msg.lower():
        return "A record with that name already exists."
    if "Cannot insert the value NULL" in msg:
        return "A required field is missing."
    return msg

def _hr():
    f = QFrame(); f.setFrameShape(QFrame.HLine)
    f.setStyleSheet(f"background:{BORDER}; border:none;"); f.setFixedHeight(1)
    return f

def _btn(text, color=None, hover=None, height=34, width=None):
    b = QPushButton(text)
    b.setFixedHeight(height)
    if width: b.setFixedWidth(width)
    b.setCursor(Qt.PointingHandCursor); b.setFocusPolicy(Qt.NoFocus)
    bg = color or NAVY; hov = hover or NAVY_2
    b.setStyleSheet(f"""
        QPushButton {{
            background:{bg}; color:{WHITE}; border:none;
            border-radius:5px; font-size:12px; font-weight:bold; padding:0 14px;
        }}
        QPushButton:hover {{ background:{hov}; }}
    """)
    return b

def _input(ph="", h=34):
    e = QLineEdit(); e.setPlaceholderText(ph); e.setFixedHeight(h)
    e.setStyleSheet(f"""
        QLineEdit {{
            background:{WHITE}; color:{DARK_TEXT}; border:1px solid {BORDER};
            border-radius:5px; font-size:13px; padding:0 10px;
        }}
        QLineEdit:focus {{ border:2px solid {ACCENT}; }}
    """)
    return e

def _combo(h=34):
    c = QComboBox(); c.setFixedHeight(h)
    c.setStyleSheet(f"""
        QComboBox {{
            background:{WHITE}; color:{DARK_TEXT}; border:1px solid {BORDER};
            border-radius:5px; font-size:13px; padding:0 10px;
        }}
        QComboBox::drop-down {{ border:none; width:24px; }}
        QComboBox QAbstractItemView {{
            background:{WHITE}; border:1px solid {BORDER};
            selection-background-color:{ACCENT}; selection-color:{WHITE};
        }}
    """)
    return c

def _tbl():
    t = QTableWidget()
    t.verticalHeader().setVisible(False)
    t.setAlternatingRowColors(True)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setSelectionMode(QAbstractItemView.SingleSelection)
    t.setStyleSheet(f"""
        QTableWidget {{
            background:{WHITE}; border:1px solid {BORDER};
            gridline-color:{LIGHT}; font-size:13px; outline:none;
        }}
        QTableWidget::item           {{ padding:8px; color:{DARK_TEXT}; }}
        QTableWidget::item:selected  {{ background:{ACCENT}; color:{WHITE}; }}
        QTableWidget::item:alternate {{ background:{ROW_ALT}; }}
        QHeaderView::section {{
            background:{NAVY}; color:{WHITE};
            padding:10px 8px; border:none;
            border-right:1px solid {NAVY_2};
            font-size:11px; font-weight:bold;
        }}
    """)
    return t

# ── Hardware Config Logic ─────────────────────────────────────────────────────
# _HW_FILE = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "hardware_settings.json")
_HW_FILE = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "hardware_settings.json")
_ORDER_STATIONS = [f"Order {i}" for i in range(1, 7)]

def _load_hw() -> dict:
    try:
        if _os.path.exists(_HW_FILE):
            with open(_HW_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception: pass
    return {"main_printer": "(None)", "orders": {}}

def _save_hw(data: dict):
    try:
        with open(_HW_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception: pass

def _get_system_printers() -> list[str]:
    printers = ["(None)"]
    try:
        import win32print
        for p in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS):
            printers.append(p[2])
    except Exception:
        try:
            from PySide6.QtPrintSupport import QPrinterInfo
            for p in QPrinterInfo.availablePrinters():
                name = p.printerName()
                if name and name not in printers:
                    printers.append(name)
        except Exception: pass
    return printers

# =============================================================================
# BASE — all section dialogs inherit from this
# =============================================================================
class _Base(QDialog):
    TITLE  = "Settings"
    W, H   = 740, 540

    def __init__(self, parent=None, **kw):
        super().__init__(parent)
        self.__dict__.update(kw)
        self.setWindowTitle(self.TITLE)
        self.setMinimumSize(self.W, self.H)
        self.setModal(True)
        self.setStyleSheet(f"QDialog {{ background:{WHITE}; }}")
        self._sl = None 

        root = QVBoxLayout(self)
        root.setSpacing(0); root.setContentsMargins(0, 0, 0, 0)

        hdr = QWidget(); hdr.setFixedHeight(50); hdr.setStyleSheet(f"background:{NAVY};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(20, 0, 20, 0)

        title = QLabel(self.TITLE)
        title.setStyleSheet(f"font-size:15px;font-weight:bold;color:{WHITE};background:transparent;")
        hl.addWidget(title); hl.addStretch()

        if hasattr(self, "_save"):
            cb = _btn("💾 Save Settings", color=SUCCESS, hover=SUCCESS_H, height=30, width=150)
            cb.clicked.connect(self._save)
        else:
            cb = _btn("✕ Close", color=DANGER, hover=DANGER_H, height=30, width=90)
            cb.clicked.connect(self.accept)

        hl.addWidget(cb); root.addWidget(hdr)
        body = QWidget(); body.setStyleSheet(f"background:{WHITE};")
        bl = QVBoxLayout(body); bl.setSpacing(12); bl.setContentsMargins(24, 18, 24, 18)
        self._build(bl)
        root.addWidget(body, 1)

    def _build(self, lay): raise NotImplementedError
    
    def _status(self, lay):
        self._sl = QLabel(""); self._sl.setStyleSheet(f"font-size:12px;background:transparent;color:{SUCCESS};")
        lay.addWidget(self._sl)

    def _msg(self, text, error=False):
        if not self._sl: return
        self._sl.setStyleSheet(f"font-size:12px;background:transparent;color:{DANGER if error else SUCCESS};")
        self._sl.setText(text)
        QTimer.singleShot(5000, lambda: self._sl.setText("") if self._sl else None)

# =============================================================================
# Section Dialogs (Companies, Customer Groups, etc.) — unchanged
# =============================================================================

class CompanyDialog(_Base):
    TITLE = "Companies"
    def _build(self, lay):
        self._t = _tbl(); self._t.setColumnCount(4)
        self._t.setHorizontalHeaderLabels(["Name","Abbreviation","Currency","Country"])
        h = self._t.horizontalHeader(); h.setSectionResizeMode(0, QHeaderView.Stretch)
        for i in [1,2,3]: h.setSectionResizeMode(i, QHeaderView.Fixed); self._t.setColumnWidth(i,110)
        lay.addWidget(self._t, 1); lay.addWidget(_hr())
        row = QHBoxLayout(); row.setSpacing(8)
        self._n=_input("Name *"); self._a=_input("Abbr *"); self._c=_input("Currency"); self._c.setText("USD"); self._co=_input("Country *")
        for w in [self._n, self._a, self._c, self._co]: row.addWidget(w)
        lay.addLayout(row); self._status(lay)
        br=QHBoxLayout(); br.setSpacing(8)
        a=_btn("Add",color=SUCCESS,hover=SUCCESS_H); d=_btn("Delete",color=DANGER,hover=DANGER_H)
        a.clicked.connect(self._add); d.clicked.connect(self._del)
        br.addStretch(); br.addWidget(a); br.addWidget(d); lay.addLayout(br); self._load()

    def _load(self):
        self._t.setRowCount(0)
        try:
            from models.company import get_all_companies
            for c in get_all_companies():
                r=self._t.rowCount(); self._t.insertRow(r)
                for col,k in enumerate(["name","abbreviation","default_currency","country"]):
                    it=QTableWidgetItem(str(c.get(k,""))); it.setData(Qt.UserRole,c); self._t.setItem(r,col,it)
                self._t.setRowHeight(r,34)
        except Exception: pass

    def _add(self):
        n=self._n.text().strip(); a=self._a.text().strip(); c=self._c.text().strip(); co=self._co.text().strip()
        if not all([n,a,c,co]): self._msg("All fields required.",True); return
        try:
            from models.company import create_company; create_company(n,a,c,co)
            for f in [self._n,self._a,self._co]: f.clear(); self._c.setText("USD"); self._load(); self._msg(f"'{n}' added.")
        except Exception as e: self._msg(_friendly_error(e),True)

    def _del(self):
        row=self._t.currentRow()
        if row<0: self._msg("Select a row.",True); return
        c=self._t.item(row,0).data(Qt.UserRole)
        if QMessageBox.question(self,"Delete",f"Delete '{c['name']}'?",QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes: return
        try:
            from models.company import delete_company; delete_company(c["id"]); self._load(); self._msg("Deleted.")
        except Exception as e: self._msg(_friendly_error(e),True)

# (The other dialogs — CustomerGroupDialog, WarehouseDialog, CostCenterDialog, PriceListDialog, CustomerDialog, UsersDialog — remain exactly as in your original code. I'm not repeating them here to save space.)

# =============================================================================
# HardwareDialog — Hardware Settings (Enhanced)
# =============================================================================
# =============================================================================
# HardwareDialog — Hardware Settings (Fixed & Working)
# =============================================================================
class HardwareDialog(_Base):
    TITLE = "Hardware Settings"
    W, H = 580, 520 

    def _build(self, lay):
        hw = _load_hw()
        self._system_printers = _get_system_printers()
        
        # Status label at top
        self._status_lbl = QLabel("Loaded printers: " + ", ".join(self._system_printers[:3]) + (" ..." if len(self._system_printers) > 3 else ""))
        self._status_lbl.setStyleSheet(f"font-size:12px; color:{MUTED}; background:transparent;")
        lay.addWidget(self._status_lbl)
        lay.addSpacing(8)

        # Refresh printers button
        refresh_btn = _btn("🔄 Refresh Printer List", color=ACCENT, hover=ACCENT_H, height=28)
        refresh_btn.clicked.connect(self._refresh_printers)
        lay.addWidget(refresh_btn, alignment=Qt.AlignRight)
        lay.addSpacing(10); lay.addWidget(_hr()); lay.addSpacing(10)

        # --- Main Receipt Printer ---
        pr_row = QHBoxLayout(); pr_row.setSpacing(12)
        pr_lbl = QLabel("Primary Receipt Printer")
        pr_lbl.setStyleSheet(f"color:{DARK_TEXT};font-size:13px;font-weight:bold;background:transparent;")
        
        self._main_printer = _combo(); self._main_printer.setFixedWidth(260)
        self._main_printer.addItem("(None)")
        for p in self._system_printers: self._main_printer.addItem(p)
        
        idx = self._main_printer.findText(hw.get("main_printer", "(None)"))
        self._main_printer.setCurrentIndex(idx if idx >= 0 else 0)
        
        test_main = _btn("Test", color=ACCENT, hover=ACCENT_H, height=28, width=60)
        test_main.clicked.connect(lambda: self._test_printer(self._main_printer.currentText()))
        
        pr_row.addWidget(pr_lbl); pr_row.addStretch(); pr_row.addWidget(self._main_printer); pr_row.addWidget(test_main)
        lay.addLayout(pr_row); lay.addSpacing(10); lay.addWidget(_hr()); lay.addSpacing(10)

        # --- Order Stations ---
        ord_lbl = QLabel("Assign Kitchen / Order Station Printers")
        ord_lbl.setStyleSheet(f"font-size:13px;font-weight:bold;color:{NAVY};background:transparent;")
        lay.addWidget(ord_lbl); lay.addSpacing(10)

        order_cfg = hw.get("orders", {})
        self._station_widgets = [] 

        for name in _ORDER_STATIONS:
            cfg = order_cfg.get(name, {})
            row = QHBoxLayout(); row.setSpacing(12)
            
            lbl = QLabel(name)
            lbl.setStyleSheet(f"font-size:13px; color:{DARK_TEXT}; font-weight:bold; background:transparent; min-width:90px;")
            
            st_printer = _combo(); st_printer.setFixedWidth(260)
            st_printer.addItem("(None)")
            for p in self._system_printers: st_printer.addItem(p)
            
            saved_st_p = cfg.get("printer", "(None)")
            p_idx = st_printer.findText(saved_st_p)
            st_printer.setCurrentIndex(p_idx if p_idx >= 0 else 0)
            
            test_btn = _btn("Test", color=ACCENT, hover=ACCENT_H, height=28, width=60)
            test_btn.clicked.connect(lambda _, cb=st_printer: self._test_printer(cb.currentText()))
            
            row.addWidget(lbl); row.addStretch(); row.addWidget(st_printer); row.addWidget(test_btn)
            lay.addLayout(row)
            self._station_widgets.append((st_printer, name))
        
        lay.addStretch(); self._status(lay)

    def _refresh_printers(self):
        self._system_printers = _get_system_printers()
        self._status_lbl.setText("Refreshed: " + ", ".join(self._system_printers[:3]) + (" ..." if len(self._system_printers) > 3 else ""))
        
        for combo_widget, _ in [(self._main_printer, None)] + self._station_widgets:
            current = combo_widget.currentText()
            combo_widget.clear()
            combo_widget.addItem("(None)")
            for p in self._system_printers:
                combo_widget.addItem(p)
            idx = combo_widget.findText(current)
            combo_widget.setCurrentIndex(idx if idx >= 0 else 0)

    def _test_printer(self, printer_name: str):
        if printer_name == "(None)":
            QMessageBox.information(self, "Test Print", "No printer selected.", QMessageBox.Ok)
            return
        
        try:
            printer = QPrinter(QPrinterInfo.printerInfo(printer_name))
            if not printer.isValid():
                raise Exception("Printer not found or invalid")

            painter = QPainter(printer)
            
            bold_font = QFont("Arial", 14)
            bold_font.setBold(True)
            normal_font = QFont("Arial", 10)

            painter.setFont(bold_font)
            painter.drawText(20, 120, "TEST PRINT from Havano POS")

            painter.setFont(normal_font)
            painter.drawText(10, 160, f"Printer : {printer_name}")
            painter.drawText(10, 190, f"Date    : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            painter.drawText(10, 220, "Status  : OK ✓")
            painter.drawText(10, 260, "This is a test page from Havano POS System.")
            painter.drawText(10, 300, "Developed by Havano Team.")

            painter.end()

            QMessageBox.information(
                self, 
                "Test Print Success", 
                f"Test page sent successfully to:\n{printer_name}\n\nCheck your printer!", 
                QMessageBox.Ok
            )

        except Exception as e:
            QMessageBox.warning(
                self, 
                "Test Print Failed", 
                f"Could not print test page:\n{str(e)}\n\n"
                "Make sure the printer is turned on and connected.", 
                QMessageBox.Ok
            )

    def _save(self):
        try:
            data = {
                "main_printer": self._main_printer.currentText(),
                "orders": {}
            }
            
            for combo, name in self._station_widgets:
                p_name = combo.currentText()
                data["orders"][name] = {
                    "active": p_name != "(None)",
                    "printer": p_name
                }
            
            _save_hw(data)
            
            QMessageBox.information(
                self, 
                "Settings Saved", 
                "Hardware settings and printer assignments saved successfully.",
                QMessageBox.Ok
            )
            self.accept()
            
        except Exception as e:
            self._msg(f"Error saving settings: {str(e)}", error=True)
     
def _test_printer(self, printer_name: str):
        if printer_name == "(None)":
            QMessageBox.information(self, "Test Print", "No printer selected.", QMessageBox.Ok)
            return
         
        try:
            printer = QPrinter(QPrinterInfo.printerInfo(printer_name))
            if not printer.isValid():
                raise Exception("Printer not found or invalid")

            painter = QPainter(printer)
            
            # Safe font creation with explicit positive sizes
            bold_font = QFont("Arial", 14)
            bold_font.setBold(True)
            normal_font = QFont("Arial", 10)

            painter.setFont(bold_font)
            painter.drawText(80, 120, "TEST PRINT from Havano POS")

            painter.setFont(normal_font)
            painter.drawText(80, 160, f"Printer : {printer_name}")
            painter.drawText(80, 190, f"Date    : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            painter.drawText(80, 220, "Status  : OK ✓")
            painter.drawText(80, 260, "This is a test page from Havano POS System.")

            painter.end()   # ← Always call this

            QMessageBox.information(
                self, 
                "Test Print Success", 
                f"Test page sent successfully to:\n{printer_name}\n\nCheck your printer!", 
                QMessageBox.Ok
            )

        except Exception as e:
            QMessageBox.warning(
                self, 
                "Test Print Failed", 
                f"Could not print test page:\n{str(e)}\n\n"
                "Make sure the printer is turned on and connected.", 
                QMessageBox.Ok
            )


def _save(self):
        try:
            data = {
                "main_printer": self._main_printer.currentText(),
                "orders": {}
            }
            
            for combo, name in self._station_widgets:
                p_name = combo.currentText()
                data["orders"][name] = {
                    "active": p_name != "(None)",
                    "printer": p_name
                }
            
            _save_hw(data)
            
            QMessageBox.information(
                self, 
                "Settings Saved", 
                "Hardware settings and printer assignments saved successfully.",
                QMessageBox.Ok
            )
            self.accept()
            
        except Exception as e:
            self._msg(f"Error saving settings: {str(e)}", error=True)

# =============================================================================
# SettingsDialog — Main Menu
# =============================================================================
class SettingsDialog(QDialog):
    def __init__(self, parent=None, user=None):
        super().__init__(parent)
        self.user = user or {}
        self.setWindowTitle("Settings")
        self.setFixedWidth(320)
        self.setModal(True)
        self.setStyleSheet(f"QDialog {{ background:{WHITE}; }}")
        self._build()

    def _build(self):
        root = QVBoxLayout(self); root.setSpacing(0); root.setContentsMargins(0, 0, 0, 0)
        hdr = QWidget(); hdr.setFixedHeight(50); hdr.setStyleSheet(f"background:{NAVY};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(20, 0, 20, 0)
        hl.addWidget(QLabel("Settings", styleSheet=f"font-size:15px;font-weight:bold;color:{WHITE};background:transparent;"))
        hl.addStretch()
        cb = _btn("✕", color=NAVY_2, hover=DANGER, height=28, width=32)
        cb.clicked.connect(self.accept); hl.addWidget(cb); root.addWidget(hdr)

        menu = QWidget(); menu.setStyleSheet(f"background:{WHITE};")
        ml = QVBoxLayout(menu); ml.setSpacing(0); ml.setContentsMargins(0, 0, 0, 0)

        items = [
            ("🏢", "Companies",         lambda: CompanyDialog(self).exec()),
            ("👥", "Customer Groups",   lambda: CustomerGroupDialog(self).exec()),
            ("🏭", "Warehouses",        lambda: WarehouseDialog(self).exec()),
            ("💰", "Cost Centers",      lambda: CostCenterDialog(self).exec()),
            ("🏷", "Price Lists",       lambda: PriceListDialog(self).exec()),
            ("👤", "Customers",         lambda: CustomerDialog(self).exec()),
            ("🔑", "Users",             lambda: UsersDialog(self, current_user=self.user).exec()),
            ("🖨", "Hardware Settings", lambda: HardwareDialog(self).exec()),
        ]

        for icon, label, handler in items:
            row = QPushButton(f"   {icon}   {label}")
            row.setFixedHeight(48); row.setCursor(Qt.PointingHandCursor); row.setFocusPolicy(Qt.NoFocus)
            row.setStyleSheet(f"""
                QPushButton {{
                    background:{WHITE}; color:{DARK_TEXT}; border:none; border-bottom:1px solid {BORDER};
                    font-size:13px; text-align:left; padding:0 16px;
                }}
                QPushButton:hover {{ background:{LIGHT}; color:{NAVY}; border-left:3px solid {ACCENT}; }}
            """)
            row.clicked.connect(handler); ml.addWidget(row)
        root.addWidget(menu, 1)

    def _switch(self, idx: int):
        mapping = {
            0: lambda: HardwareDialog(self).exec(),
            1: lambda: CompanyDialog(self).exec(),
            2: lambda: CustomerGroupDialog(self).exec(),
            3: lambda: WarehouseDialog(self).exec(),
            4: lambda: CostCenterDialog(self).exec(),
            5: lambda: PriceListDialog(self).exec(),
            6: lambda: CustomerDialog(self).exec(),
            7: lambda: UsersDialog(self, current_user=self.user).exec()
        }
        fn = mapping.get(idx)
        if fn: fn()
        else: self.exec()