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
from pathlib import Path
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
# _HW_FILE = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "hardware_settings.json")
# _ORDER_STATIONS = [f"Order {i}" for i in range(1, 7)]
# ── Hardware Config Logic ─────────────────────────────────────────────────────
_HW_FILE = Path("app_data/hardware_settings.json")   # ← now matches sql_settings.json
_ORDER_STATIONS = [f"Order {i}" for i in range(1, 7)]
def _load_hw() -> dict:
    try:
        _HW_FILE.parent.mkdir(parents=True, exist_ok=True)   # ensure app_data/ exists
        if _HW_FILE.exists():
            with open(_HW_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {"main_printer": "(None)", "orders": {}}

def _save_hw(data: dict):
    try:
        _HW_FILE.parent.mkdir(parents=True, exist_ok=True)   # ensure app_data/ exists
        with open(_HW_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass
    
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

# ── Users dialog — separate file, no circular dependency ─────────────────────
try:
    from views.dialogs.users_dialog import ManageUsersDialog, UsersDialog
except Exception:
    # Fallback: define minimal stub so SettingsDialog still opens
    from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel
    class ManageUsersDialog(QDialog):
        def __init__(self, parent=None, current_user=None):
            super().__init__(parent)
            self.setWindowTitle("Users")
            lay = QVBoxLayout(self)
            lay.addWidget(QLabel("Users dialog unavailable."))
    UsersDialog = ManageUsersDialog

# ── Helpers — defined locally to avoid importing from main_window ─────────────
def _friendly_db_error(e):
    msg = str(e)
    if "REFERENCE constraint" in msg or "FK_" in msg or "foreign key" in msg.lower():
        return "Cannot delete — record is still linked to other data."
    if "UNIQUE" in msg or "duplicate key" in msg.lower():
        return "A record with that name already exists."
    if "Cannot insert the value NULL" in msg:
        return "A required field is missing."
    return msg

def _settings_table_style():
    return f"""
        QTableWidget {{ background:{WHITE}; border:1px solid {BORDER};
            gridline-color:{LIGHT}; outline:none; font-size:13px; }}
        QTableWidget::item           {{ padding:8px; }}
        QTableWidget::item:selected  {{ background-color:{ACCENT}; color:{WHITE}; }}
        QTableWidget::item:alternate {{ background-color:{ROW_ALT}; }}
        QHeaderView::section {{
            background-color:{NAVY}; color:{WHITE};
            padding:10px 8px; border:none; border-right:1px solid {NAVY_2};
            font-size:11px; font-weight:bold;
        }}
    """

def navy_btn(text, height=36, font_size=12, width=None, color=None, hover=None):
    from PySide6.QtWidgets import QPushButton
    from PySide6.QtCore import Qt
    bg  = color or NAVY
    hov = hover or NAVY_2
    btn = QPushButton(text)
    btn.setFixedHeight(height)
    if width: btn.setFixedWidth(width)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {bg}; color: {WHITE}; border: none;
            border-radius: 5px; font-size: {font_size}px; font-weight: bold; padding: 0 14px;
        }}
        QPushButton:hover   {{ background-color: {hov}; }}
        QPushButton:pressed {{ background-color: {NAVY_3}; }}
    """)
    return btn

def hr(horizontal=True):
    from PySide6.QtWidgets import QFrame
    line = QFrame()
    line.setFrameShape(QFrame.HLine if horizontal else QFrame.VLine)
    line.setStyleSheet(f"background-color: {BORDER}; border: none;")
    if horizontal: line.setFixedHeight(1)
    else: line.setFixedWidth(1)
    return line

class CustomerGroupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Customer Groups"); self.setMinimumSize(560, 420)
        self.setStyleSheet(f"QDialog {{ background-color:{WHITE}; }}")
        self._build(); self._reload()

    def _build(self):
        lay = QVBoxLayout(self); lay.setSpacing(10); lay.setContentsMargins(20,16,20,16)
        hdr = QWidget(); hdr.setFixedHeight(44); hdr.setStyleSheet(f"background-color:{NAVY}; border-radius:5px;")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(16,0,16,0)
        hl.addWidget(QLabel("Customer Groups",styleSheet=f"font-size:15px;font-weight:bold;color:{WHITE};background:transparent;"))
        lay.addWidget(hdr)
        self._tbl = QTableWidget(0,2); self._tbl.setHorizontalHeaderLabels(["Name","Parent Group"])
        self._tbl.horizontalHeader().setStretchLastSection(True); self._tbl.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch)
        self._tbl.verticalHeader().setVisible(False); self._tbl.setAlternatingRowColors(True)
        self._tbl.setEditTriggers(QAbstractItemView.NoEditTriggers); self._tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tbl.setStyleSheet(_settings_table_style()); lay.addWidget(self._tbl,1); lay.addWidget(hr())
        fr = QHBoxLayout(); fr.setSpacing(8)
        self._f_name = QLineEdit(); self._f_name.setPlaceholderText("Group name *"); self._f_name.setFixedHeight(34)
        self._f_parent = QComboBox(); self._f_parent.setFixedHeight(34); self._f_parent.addItem("(No parent)", None)
        fr.addWidget(self._f_name,2); fr.addWidget(QLabel("Parent:",styleSheet="background:transparent;"),0); fr.addWidget(self._f_parent,1)
        lay.addLayout(fr)
        br = QHBoxLayout(); br.setSpacing(8)
        self._status = QLabel(""); self._status.setStyleSheet(f"font-size:12px;color:{SUCCESS};background:transparent;")
        add_btn=navy_btn("Add",height=34,color=SUCCESS,hover=SUCCESS_H); del_btn=navy_btn("Delete",height=34,color=DANGER,hover=DANGER_H); cls_btn=navy_btn("Close",height=34)
        add_btn.clicked.connect(self._add); del_btn.clicked.connect(self._delete); cls_btn.clicked.connect(self.accept)
        br.addWidget(self._status,1); br.addWidget(add_btn); br.addWidget(del_btn); br.addWidget(cls_btn)
        lay.addLayout(br)

    def _reload(self):
        self._tbl.setRowCount(0); self._f_parent.clear(); self._f_parent.addItem("(No parent)", None)
        try:
            from models.customer_group import get_all_customer_groups
            groups = get_all_customer_groups()
        except Exception: groups=[]
        for g in groups:
            r=self._tbl.rowCount(); self._tbl.insertRow(r)
            parent_name = next((x["name"] for x in groups if x["id"]==g.get("parent_group_id")),"—")
            for col,val in enumerate([g["name"],parent_name]):
                it=QTableWidgetItem(val); it.setData(Qt.UserRole,g); self._tbl.setItem(r,col,it)
            self._tbl.setRowHeight(r,32)
            self._f_parent.addItem(g["name"], g["id"])

    def _add(self):
        name=self._f_name.text().strip()
        if not name: self._status.setText("Name required."); return
        parent_id=self._f_parent.currentData()
        try:
            from models.customer_group import create_customer_group
            create_customer_group(name,parent_id); self._f_name.clear(); self._reload()
            self._status.setText(f"Group '{name}' added."); self._status.setStyleSheet(f"color:{SUCCESS};font-size:12px;background:transparent;")
        except Exception as e: self._status.setText(_friendly_db_error(e)); self._status.setStyleSheet(f"color:{DANGER};font-size:12px;background:transparent;")

    def _delete(self):
        row=self._tbl.currentRow()
        if row<0: self._status.setText("Select a group first."); return
        g=self._tbl.item(row,0).data(Qt.UserRole)
        if QMessageBox.question(self,"Delete",f"Delete '{g['name']}'?",QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes: return
        try:
            from models.customer_group import delete_customer_group
            delete_customer_group(g["id"]); self._reload()
            self._status.setText("Deleted."); self._status.setStyleSheet(f"color:{SUCCESS};font-size:12px;background:transparent;")
        except Exception as e: self._status.setText(_friendly_db_error(e)); self._status.setStyleSheet(f"color:{DANGER};font-size:12px;background:transparent;")


class WarehouseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Warehouses"); self.setMinimumSize(560,420)
        self.setStyleSheet(f"QDialog {{ background-color:{WHITE}; }}")
        self._build(); self._reload()

    def _build(self):
        lay=QVBoxLayout(self); lay.setSpacing(10); lay.setContentsMargins(20,16,20,16)
        hdr=QWidget(); hdr.setFixedHeight(44); hdr.setStyleSheet(f"background-color:{NAVY}; border-radius:5px;")
        hl=QHBoxLayout(hdr); hl.setContentsMargins(16,0,16,0)
        hl.addWidget(QLabel("Warehouses",styleSheet=f"font-size:15px;font-weight:bold;color:{WHITE};background:transparent;"))
        lay.addWidget(hdr)
        self._tbl=QTableWidget(0,2); self._tbl.setHorizontalHeaderLabels(["Name","Company"])
        self._tbl.horizontalHeader().setStretchLastSection(True); self._tbl.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch)
        self._tbl.verticalHeader().setVisible(False); self._tbl.setAlternatingRowColors(True)
        self._tbl.setEditTriggers(QAbstractItemView.NoEditTriggers); self._tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tbl.setStyleSheet(_settings_table_style()); lay.addWidget(self._tbl,1); lay.addWidget(hr())
        fr=QHBoxLayout(); fr.setSpacing(8)
        self._f_name=QLineEdit(); self._f_name.setPlaceholderText("Warehouse name *"); self._f_name.setFixedHeight(34)
        self._f_company=QComboBox(); self._f_company.setFixedHeight(34)
        fr.addWidget(self._f_name,2); fr.addWidget(QLabel("Company:",styleSheet="background:transparent;"),0); fr.addWidget(self._f_company,1)
        lay.addLayout(fr)
        br=QHBoxLayout(); br.setSpacing(8)
        self._status=QLabel(""); self._status.setStyleSheet(f"font-size:12px;color:{SUCCESS};background:transparent;")
        add_btn=navy_btn("Add",height=34,color=SUCCESS,hover=SUCCESS_H); del_btn=navy_btn("Delete",height=34,color=DANGER,hover=DANGER_H); cls_btn=navy_btn("Close",height=34)
        add_btn.clicked.connect(self._add); del_btn.clicked.connect(self._delete); cls_btn.clicked.connect(self.accept)
        br.addWidget(self._status,1); br.addWidget(add_btn); br.addWidget(del_btn); br.addWidget(cls_btn)
        lay.addLayout(br)

    def _reload(self):
        self._tbl.setRowCount(0); self._f_company.clear()
        try:
            from models.warehouse import get_all_warehouses
            from models.company import get_all_companies
            rows=get_all_warehouses(); companies=get_all_companies()
        except Exception: rows=[]; companies=[]
        for w in rows:
            r=self._tbl.rowCount(); self._tbl.insertRow(r)
            for col,val in enumerate([w["name"],w.get("company_name","")]):
                it=QTableWidgetItem(val); it.setData(Qt.UserRole,w); self._tbl.setItem(r,col,it)
            self._tbl.setRowHeight(r,32)
        for c in companies: self._f_company.addItem(c["name"],c["id"])

    def _add(self):
        name=self._f_name.text().strip(); cid=self._f_company.currentData()
        if not name or not cid: self._status.setText("Name and company required."); self._status.setStyleSheet(f"color:{DANGER};font-size:12px;background:transparent;"); return
        try:
            from models.warehouse import create_warehouse
            create_warehouse(name,cid); self._f_name.clear(); self._reload()
            self._status.setText(f"Warehouse '{name}' added."); self._status.setStyleSheet(f"color:{SUCCESS};font-size:12px;background:transparent;")
        except Exception as e: self._status.setText(_friendly_db_error(e)); self._status.setStyleSheet(f"color:{DANGER};font-size:12px;background:transparent;")

    def _delete(self):
        row=self._tbl.currentRow()
        if row<0: self._status.setText("Select a warehouse first."); return
        w=self._tbl.item(row,0).data(Qt.UserRole)
        if QMessageBox.question(self,"Delete",f"Delete '{w['name']}'?",QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes: return
        try:
            from models.warehouse import delete_warehouse
            delete_warehouse(w["id"]); self._reload()
            self._status.setText("Deleted."); self._status.setStyleSheet(f"color:{SUCCESS};font-size:12px;background:transparent;")
        except Exception as e: self._status.setText(_friendly_db_error(e)); self._status.setStyleSheet(f"color:{DANGER};font-size:12px;background:transparent;")


class CostCenterDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cost Centers"); self.setMinimumSize(560,420)
        self.setStyleSheet(f"QDialog {{ background-color:{WHITE}; }}")
        self._build(); self._reload()

    def _build(self):
        lay=QVBoxLayout(self); lay.setSpacing(10); lay.setContentsMargins(20,16,20,16)
        hdr=QWidget(); hdr.setFixedHeight(44); hdr.setStyleSheet(f"background-color:{NAVY}; border-radius:5px;")
        hl=QHBoxLayout(hdr); hl.setContentsMargins(16,0,16,0)
        hl.addWidget(QLabel("Cost Centers",styleSheet=f"font-size:15px;font-weight:bold;color:{WHITE};background:transparent;"))
        lay.addWidget(hdr)
        self._tbl=QTableWidget(0,2); self._tbl.setHorizontalHeaderLabels(["Name","Company"])
        self._tbl.horizontalHeader().setStretchLastSection(True); self._tbl.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch)
        self._tbl.verticalHeader().setVisible(False); self._tbl.setAlternatingRowColors(True)
        self._tbl.setEditTriggers(QAbstractItemView.NoEditTriggers); self._tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tbl.setStyleSheet(_settings_table_style()); lay.addWidget(self._tbl,1); lay.addWidget(hr())
        fr=QHBoxLayout(); fr.setSpacing(8)
        self._f_name=QLineEdit(); self._f_name.setPlaceholderText("Cost center name *"); self._f_name.setFixedHeight(34)
        self._f_company=QComboBox(); self._f_company.setFixedHeight(34)
        fr.addWidget(self._f_name,2); fr.addWidget(QLabel("Company:",styleSheet="background:transparent;"),0); fr.addWidget(self._f_company,1)
        lay.addLayout(fr)
        br=QHBoxLayout(); br.setSpacing(8)
        self._status=QLabel(""); self._status.setStyleSheet(f"font-size:12px;color:{SUCCESS};background:transparent;")
        add_btn=navy_btn("Add",height=34,color=SUCCESS,hover=SUCCESS_H); del_btn=navy_btn("Delete",height=34,color=DANGER,hover=DANGER_H); cls_btn=navy_btn("Close",height=34)
        add_btn.clicked.connect(self._add); del_btn.clicked.connect(self._delete); cls_btn.clicked.connect(self.accept)
        br.addWidget(self._status,1); br.addWidget(add_btn); br.addWidget(del_btn); br.addWidget(cls_btn)
        lay.addLayout(br)

    def _reload(self):
        self._tbl.setRowCount(0); self._f_company.clear()
        try:
            from models.cost_center import get_all_cost_centers
            from models.company import get_all_companies
            rows=get_all_cost_centers(); companies=get_all_companies()
        except Exception: rows=[]; companies=[]
        for cc in rows:
            r=self._tbl.rowCount(); self._tbl.insertRow(r)
            for col,val in enumerate([cc["name"],cc.get("company_name","")]):
                it=QTableWidgetItem(val); it.setData(Qt.UserRole,cc); self._tbl.setItem(r,col,it)
            self._tbl.setRowHeight(r,32)
        for c in companies: self._f_company.addItem(c["name"],c["id"])

    def _add(self):
        name=self._f_name.text().strip(); cid=self._f_company.currentData()
        if not name or not cid: self._status.setText("Name and company required."); self._status.setStyleSheet(f"color:{DANGER};font-size:12px;background:transparent;"); return
        try:
            from models.cost_center import create_cost_center
            create_cost_center(name,cid); self._f_name.clear(); self._reload()
            self._status.setText(f"Cost center '{name}' added."); self._status.setStyleSheet(f"color:{SUCCESS};font-size:12px;background:transparent;")
        except Exception as e: self._status.setText(_friendly_db_error(e)); self._status.setStyleSheet(f"color:{DANGER};font-size:12px;background:transparent;")

    def _delete(self):
        row=self._tbl.currentRow()
        if row<0: self._status.setText("Select a cost center first."); return
        cc=self._tbl.item(row,0).data(Qt.UserRole)
        if QMessageBox.question(self,"Delete",f"Delete '{cc['name']}'?",QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes: return
        try:
            from models.cost_center import delete_cost_center
            delete_cost_center(cc["id"]); self._reload()
            self._status.setText("Deleted."); self._status.setStyleSheet(f"color:{SUCCESS};font-size:12px;background:transparent;")
        except Exception as e: self._status.setText(_friendly_db_error(e)); self._status.setStyleSheet(f"color:{DANGER};font-size:12px;background:transparent;")


class PriceListDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Price Lists"); self.setMinimumSize(480,380)
        self.setStyleSheet(f"QDialog {{ background-color:{WHITE}; }}")
        self._build(); self._reload()

    def _build(self):
        lay=QVBoxLayout(self); lay.setSpacing(10); lay.setContentsMargins(20,16,20,16)
        hdr=QWidget(); hdr.setFixedHeight(44); hdr.setStyleSheet(f"background-color:{NAVY}; border-radius:5px;")
        hl=QHBoxLayout(hdr); hl.setContentsMargins(16,0,16,0)
        hl.addWidget(QLabel("Price Lists",styleSheet=f"font-size:15px;font-weight:bold;color:{WHITE};background:transparent;"))
        lay.addWidget(hdr)
        self._tbl=QTableWidget(0,2); self._tbl.setHorizontalHeaderLabels(["Name","Selling"])
        self._tbl.horizontalHeader().setStretchLastSection(True); self._tbl.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch)
        self._tbl.verticalHeader().setVisible(False); self._tbl.setAlternatingRowColors(True)
        self._tbl.setEditTriggers(QAbstractItemView.NoEditTriggers); self._tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tbl.setStyleSheet(_settings_table_style()); lay.addWidget(self._tbl,1); lay.addWidget(hr())
        fr=QHBoxLayout(); fr.setSpacing(8)
        self._f_name=QLineEdit(); self._f_name.setPlaceholderText("Price list name *"); self._f_name.setFixedHeight(34)
        self._f_selling=QComboBox(); self._f_selling.addItems(["Selling","Not Selling"]); self._f_selling.setFixedHeight(34)
        fr.addWidget(self._f_name,2); fr.addWidget(self._f_selling,1)
        lay.addLayout(fr)
        br=QHBoxLayout(); br.setSpacing(8)
        self._status=QLabel(""); self._status.setStyleSheet(f"font-size:12px;color:{SUCCESS};background:transparent;")
        add_btn=navy_btn("Add",height=34,color=SUCCESS,hover=SUCCESS_H); del_btn=navy_btn("Delete",height=34,color=DANGER,hover=DANGER_H); cls_btn=navy_btn("Close",height=34)
        add_btn.clicked.connect(self._add); del_btn.clicked.connect(self._delete); cls_btn.clicked.connect(self.accept)
        br.addWidget(self._status,1); br.addWidget(add_btn); br.addWidget(del_btn); br.addWidget(cls_btn)
        lay.addLayout(br)

    def _reload(self):
        self._tbl.setRowCount(0)
        try:
            from models.price_list import get_all_price_lists
            rows=get_all_price_lists()
        except Exception: rows=[]
        for pl in rows:
            r=self._tbl.rowCount(); self._tbl.insertRow(r)
            for col,val in enumerate([pl["name"],"Yes" if pl["selling"] else "No"]):
                it=QTableWidgetItem(val); it.setData(Qt.UserRole,pl); self._tbl.setItem(r,col,it)
            self._tbl.setRowHeight(r,32)

    def _add(self):
        name=self._f_name.text().strip(); selling=self._f_selling.currentIndex()==0
        if not name: self._status.setText("Name required."); self._status.setStyleSheet(f"color:{DANGER};font-size:12px;background:transparent;"); return
        try:
            from models.price_list import create_price_list
            create_price_list(name,selling); self._f_name.clear(); self._reload()
            self._status.setText(f"Price list '{name}' added."); self._status.setStyleSheet(f"color:{SUCCESS};font-size:12px;background:transparent;")
        except Exception as e: self._status.setText(_friendly_db_error(e)); self._status.setStyleSheet(f"color:{DANGER};font-size:12px;background:transparent;")

    def _delete(self):
        row=self._tbl.currentRow()
        if row<0: self._status.setText("Select a price list first."); return
        pl=self._tbl.item(row,0).data(Qt.UserRole)
        if QMessageBox.question(self,"Delete",f"Delete '{pl['name']}'?",QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes: return
        try:
            from models.price_list import delete_price_list
            delete_price_list(pl["id"]); self._reload()
            self._status.setText("Deleted."); self._status.setStyleSheet(f"color:{SUCCESS};font-size:12px;background:transparent;")
        except Exception as e: self._status.setText(_friendly_db_error(e)); self._status.setStyleSheet(f"color:{DANGER};font-size:12px;background:transparent;")


class CustomerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Customers"); self.setMinimumSize(860,560)
        self.setStyleSheet(f"QDialog {{ background-color:{WHITE}; }}")
        self._build(); self._reload()

    def _build(self):
        lay=QVBoxLayout(self); lay.setSpacing(10); lay.setContentsMargins(20,16,20,16)
        hdr=QWidget(); hdr.setFixedHeight(44); hdr.setStyleSheet(f"background-color:{NAVY}; border-radius:5px;")
        hl=QHBoxLayout(hdr); hl.setContentsMargins(16,0,16,0)
        hl.addWidget(QLabel("Customers",styleSheet=f"font-size:15px;font-weight:bold;color:{WHITE};background:transparent;"))
        lay.addWidget(hdr)

        sr=QHBoxLayout(); sr.setSpacing(8)
        self._search=QLineEdit(); self._search.setPlaceholderText("Search by name, trade name or phone…"); self._search.setFixedHeight(34)
        self._search.textChanged.connect(self._do_search)
        sr.addWidget(self._search)
        lay.addLayout(sr)

        self._tbl=QTableWidget(0,6)
        self._tbl.setHorizontalHeaderLabels(["Name","Type","Group","Phone","City","Price List"])
        hh=self._tbl.horizontalHeader(); hh.setSectionResizeMode(0,QHeaderView.Stretch)
        for ci in [1,2,3,4,5]: hh.setSectionResizeMode(ci,QHeaderView.Fixed); self._tbl.setColumnWidth(ci,110)
        self._tbl.verticalHeader().setVisible(False); self._tbl.setAlternatingRowColors(True)
        self._tbl.setEditTriggers(QAbstractItemView.NoEditTriggers); self._tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tbl.setStyleSheet(_settings_table_style()); lay.addWidget(self._tbl,1); lay.addWidget(hr())

        form=QGridLayout(); form.setSpacing(8)
        self._f_name  =QLineEdit(); self._f_name.setPlaceholderText("Customer name *"); self._f_name.setFixedHeight(32)
        self._f_type  =QComboBox(); self._f_type.addItems(["","Individual","Company"]); self._f_type.setFixedHeight(32)
        self._f_trade =QLineEdit(); self._f_trade.setPlaceholderText("Trade name"); self._f_trade.setFixedHeight(32)
        self._f_phone =QLineEdit(); self._f_phone.setPlaceholderText("Phone"); self._f_phone.setFixedHeight(32)
        self._f_email =QLineEdit(); self._f_email.setPlaceholderText("Email"); self._f_email.setFixedHeight(32)
        self._f_city  =QLineEdit(); self._f_city.setPlaceholderText("City"); self._f_city.setFixedHeight(32)
        self._f_house =QLineEdit(); self._f_house.setPlaceholderText("House No."); self._f_house.setFixedHeight(32)
        self._f_group =QComboBox(); self._f_group.setFixedHeight(32)
        self._f_wh    =QComboBox(); self._f_wh.setFixedHeight(32)
        self._f_cc    =QComboBox(); self._f_cc.setFixedHeight(32)
        self._f_pl    =QComboBox(); self._f_pl.setFixedHeight(32)

        for lbl_txt, widget, r, c in [
            ("Name *",       self._f_name,  0,0), ("Type",         self._f_type,  0,2),
            ("Trade Name",   self._f_trade, 1,0), ("Phone",        self._f_phone, 1,2),
            ("Email",        self._f_email, 2,0), ("City",         self._f_city,  2,2),
            ("House No.",    self._f_house, 3,0), ("Group *",      self._f_group, 3,2),
            ("Warehouse *",  self._f_wh,    4,0), ("Cost Center *",self._f_cc,    4,2),
            ("Price List *", self._f_pl,    5,0),
        ]:
            form.addWidget(QLabel(lbl_txt,styleSheet="background:transparent;font-size:12px;"),r,c)
            form.addWidget(widget,r,c+1)
        lay.addLayout(form)

        br=QHBoxLayout(); br.setSpacing(8)
        self._status=QLabel(""); self._status.setStyleSheet(f"font-size:12px;color:{SUCCESS};background:transparent;")
        add_btn=navy_btn("Add Customer",height=34,color=SUCCESS,hover=SUCCESS_H)
        del_btn=navy_btn("Delete",height=34,color=DANGER,hover=DANGER_H)
        cls_btn=navy_btn("Close",height=34)
        add_btn.clicked.connect(self._add); del_btn.clicked.connect(self._delete); cls_btn.clicked.connect(self.accept)
        br.addWidget(self._status,1); br.addWidget(add_btn); br.addWidget(del_btn); br.addWidget(cls_btn)
        lay.addLayout(br)

    def _reload(self):
        self._tbl.setRowCount(0)
        try:
            from models.customer import get_all_customers
            custs=get_all_customers()
        except Exception: custs=[]
        self._populate_combos()
        self._populate_table(custs)

    def _do_search(self, query):
        if not query.strip(): self._reload(); return
        try:
            from models.customer import search_customers
            custs=search_customers(query)
        except Exception: custs=[]
        self._populate_table(custs)

    def _populate_table(self, custs):
        self._tbl.setRowCount(0)
        for c in custs:
            r=self._tbl.rowCount(); self._tbl.insertRow(r)
            for col,val in enumerate([
                c["customer_name"], c.get("customer_type",""),
                c.get("customer_group_name",""), c.get("custom_telephone_number",""),
                c.get("custom_city",""), c.get("price_list_name",""),
            ]):
                it=QTableWidgetItem(str(val)); it.setData(Qt.UserRole,c); self._tbl.setItem(r,col,it)
            self._tbl.setRowHeight(r,32)

    def _populate_combos(self):
        try:
            from models.customer_group import get_all_customer_groups
            from models.warehouse import get_all_warehouses
            from models.cost_center import get_all_cost_centers
            from models.price_list import get_all_price_lists
            groups=get_all_customer_groups(); whs=get_all_warehouses()
            ccs=get_all_cost_centers(); pls=get_all_price_lists()
        except Exception: groups=[];whs=[];ccs=[];pls=[]
        for cb in [self._f_group,self._f_wh,self._f_cc,self._f_pl]: cb.clear()
        for g in groups: self._f_group.addItem(g["name"],g["id"])
        for w in whs: self._f_wh.addItem(f"{w['name']} ({w.get('company_name','')})",w["id"])
        for cc in ccs: self._f_cc.addItem(f"{cc['name']} ({cc.get('company_name','')})",cc["id"])
        for pl in pls: self._f_pl.addItem(pl["name"],pl["id"])

    def _add(self):
        name=self._f_name.text().strip()
        if not name: self._status.setText("Customer name required."); self._status.setStyleSheet(f"color:{DANGER};font-size:12px;background:transparent;"); return
        gid=self._f_group.currentData(); wid=self._f_wh.currentData(); ccid=self._f_cc.currentData(); plid=self._f_pl.currentData()
        if not all([gid,wid,ccid,plid]): self._status.setText("Group, Warehouse, Cost Center and Price List are required."); self._status.setStyleSheet(f"color:{DANGER};font-size:12px;background:transparent;"); return
        try:
            from models.customer import create_customer
            create_customer(
                customer_name=name, customer_group_id=gid,
                custom_warehouse_id=wid, custom_cost_center_id=ccid,
                default_price_list_id=plid,
                customer_type=self._f_type.currentText() or None,
                custom_trade_name=self._f_trade.text().strip(),
                custom_telephone_number=self._f_phone.text().strip(),
                custom_email_address=self._f_email.text().strip(),
                custom_city=self._f_city.text().strip(),
                custom_house_no=self._f_house.text().strip(),
            )
            for f in [self._f_name,self._f_trade,self._f_phone,self._f_email,self._f_city,self._f_house]: f.clear()
            self._reload()
            self._status.setText(f"Customer '{name}' added."); self._status.setStyleSheet(f"color:{SUCCESS};font-size:12px;background:transparent;")
        except Exception as e: self._status.setText(_friendly_db_error(e)); self._status.setStyleSheet(f"color:{DANGER};font-size:12px;background:transparent;")

    def _delete(self):
        row=self._tbl.currentRow()
        if row<0: self._status.setText("Select a customer first."); return
        c=self._tbl.item(row,0).data(Qt.UserRole)
        if QMessageBox.question(self,"Delete",f"Delete '{c['customer_name']}'?",QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes: return
        try:
            from models.customer import delete_customer
            delete_customer(c["id"]); self._reload()
            self._status.setText("Deleted."); self._status.setStyleSheet(f"color:{SUCCESS};font-size:12px;background:transparent;")
        except Exception as e: self._status.setText(_friendly_db_error(e)); self._status.setStyleSheet(f"color:{DANGER};font-size:12px;background:transparent;")


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