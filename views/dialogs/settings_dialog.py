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
from PySide6.QtGui  import QColor
import json
import os as _os

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
_HW_FILE = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "hardware_settings.json")
_ORDER_STATIONS = [f"Order {i}" for i in range(1, 7)]

def _load_hw() -> dict:
    try:
        if _os.path.exists(_HW_FILE):
            with open(_HW_FILE, "r") as f:
                return json.load(f)
    except Exception: pass
    return {"main_printer": "(None)", "orders": {}}

def _save_hw(data: dict):
    try:
        with open(_HW_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception: pass

def _get_system_printers() -> list[str]:
    printers = ["(None)"]
    # Windows specific check
    try:
        import win32print
        for p in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS):
            printers.append(p[2])
    except Exception:
        # Fallback to PySide generic check
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
# Section Dialogs (Companies, Groups, Warehouses, etc.)
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

class CustomerGroupDialog(_Base):
    TITLE = "Customer Groups"; W=620
    def _build(self, lay):
        self._t=_tbl(); self._t.setColumnCount(2); self._t.setHorizontalHeaderLabels(["Name","Parent Group"])
        h=self._t.horizontalHeader(); h.setSectionResizeMode(0,QHeaderView.Stretch); h.setSectionResizeMode(1,QHeaderView.Stretch)
        lay.addWidget(self._t,1); lay.addWidget(_hr())
        row=QHBoxLayout(); row.setSpacing(8)
        self._n=_input("Group name *"); self._p=_combo()
        row.addWidget(QLabel("Name:",styleSheet="background:transparent;font-size:12px;")); row.addWidget(self._n,2)
        row.addWidget(QLabel("Parent:",styleSheet="background:transparent;font-size:12px;")); row.addWidget(self._p,1)
        lay.addLayout(row); self._status(lay)
        br=QHBoxLayout(); br.setSpacing(8)
        a=_btn("Add",color=SUCCESS,hover=SUCCESS_H); d=_btn("Delete",color=DANGER,hover=DANGER_H)
        a.clicked.connect(self._add); d.clicked.connect(self._del)
        br.addStretch(); br.addWidget(a); br.addWidget(d); lay.addLayout(br); self._load()

    def _load(self):
        self._t.setRowCount(0); self._p.clear(); self._p.addItem("(No parent)",None)
        try:
            from models.customer_group import get_all_customer_groups
            gs=get_all_customer_groups()
        except Exception: gs=[]
        for g in gs:
            r=self._t.rowCount(); self._t.insertRow(r)
            pn=next((x["name"] for x in gs if x["id"]==g.get("parent_group_id")),"—")
            for col,v in enumerate([g["name"],pn]):
                it=QTableWidgetItem(v); it.setData(Qt.UserRole,g); self._t.setItem(r,col,it)
            self._t.setRowHeight(r,34); self._p.addItem(g["name"],g["id"])

    def _add(self):
        n=self._n.text().strip()
        if not n: self._msg("Name required.",True); return
        try:
            from models.customer_group import create_customer_group; create_customer_group(n,self._p.currentData())
            self._n.clear(); self._load(); self._msg(f"'{n}' added.")
        except Exception as e: self._msg(_friendly_error(e),True)

    def _del(self):
        row=self._t.currentRow()
        if row<0: self._msg("Select a row.",True); return
        g=self._t.item(row,0).data(Qt.UserRole)
        if QMessageBox.question(self,"Delete",f"Delete '{g['name']}'?",QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes: return
        try:
            from models.customer_group import delete_customer_group; delete_customer_group(g["id"]); self._load(); self._msg("Deleted.")
        except Exception as e: self._msg(_friendly_error(e),True)

class WarehouseDialog(_Base):
    TITLE = "Warehouses"; W=620
    def _build(self, lay):
        self._t=_tbl(); self._t.setColumnCount(2); self._t.setHorizontalHeaderLabels(["Name","Company"])
        h=self._t.horizontalHeader(); h.setSectionResizeMode(0,QHeaderView.Stretch); h.setSectionResizeMode(1,QHeaderView.Stretch)
        lay.addWidget(self._t,1); lay.addWidget(_hr())
        row=QHBoxLayout(); row.setSpacing(8)
        self._n=_input("Warehouse name *"); self._c=_combo()
        row.addWidget(QLabel("Name:",styleSheet="background:transparent;font-size:12px;")); row.addWidget(self._n,2)
        row.addWidget(QLabel("Company:",styleSheet="background:transparent;font-size:12px;")); row.addWidget(self._c,1)
        lay.addLayout(row); self._status(lay)
        br=QHBoxLayout(); br.setSpacing(8)
        a=_btn("Add",color=SUCCESS,hover=SUCCESS_H); d=_btn("Delete",color=DANGER,hover=DANGER_H)
        a.clicked.connect(self._add); d.clicked.connect(self._del)
        br.addStretch(); br.addWidget(a); br.addWidget(d); lay.addLayout(br); self._load()

    def _load(self):
        self._t.setRowCount(0); self._c.clear()
        try:
            from models.warehouse import get_all_warehouses
            from models.company   import get_all_companies
            for w in get_all_warehouses():
                r=self._t.rowCount(); self._t.insertRow(r)
                for col,v in enumerate([w["name"],w.get("company_name","")]):
                    it=QTableWidgetItem(v); it.setData(Qt.UserRole,w); self._t.setItem(r,col,it)
                self._t.setRowHeight(r,34)
            for c in get_all_companies(): self._c.addItem(c["name"],c["id"])
        except Exception: pass

    def _add(self):
        n=self._n.text().strip(); cid=self._c.currentData()
        if not n or not cid: self._msg("Name and company required.",True); return
        try:
            from models.warehouse import create_warehouse; create_warehouse(n,cid)
            self._n.clear(); self._load(); self._msg(f"'{n}' added.")
        except Exception as e: self._msg(_friendly_error(e),True)

    def _del(self):
        row=self._t.currentRow()
        if row<0: self._msg("Select a row.",True); return
        w=self._t.item(row,0).data(Qt.UserRole)
        if QMessageBox.question(self,"Delete",f"Delete '{w['name']}'?",QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes: return
        try:
            from models.warehouse import delete_warehouse; delete_warehouse(w["id"]); self._load(); self._msg("Deleted.")
        except Exception as e: self._msg(_friendly_error(e),True)

class CostCenterDialog(_Base):
    TITLE = "Cost Centers"; W=620
    def _build(self, lay):
        self._t=_tbl(); self._t.setColumnCount(2); self._t.setHorizontalHeaderLabels(["Name","Company"])
        h=self._t.horizontalHeader(); h.setSectionResizeMode(0,QHeaderView.Stretch); h.setSectionResizeMode(1,QHeaderView.Stretch)
        lay.addWidget(self._t,1); lay.addWidget(_hr())
        row=QHBoxLayout(); row.setSpacing(8)
        self._n=_input("Cost center name *"); self._c=_combo()
        row.addWidget(QLabel("Name:",styleSheet="background:transparent;font-size:12px;")); row.addWidget(self._n,2)
        row.addWidget(QLabel("Company:",styleSheet="background:transparent;font-size:12px;")); row.addWidget(self._c,1)
        lay.addLayout(row); self._status(lay)
        br=QHBoxLayout(); br.setSpacing(8)
        a=_btn("Add",color=SUCCESS,hover=SUCCESS_H); d=_btn("Delete",color=DANGER,hover=DANGER_H)
        a.clicked.connect(self._add); d.clicked.connect(self._del)
        br.addStretch(); br.addWidget(a); br.addWidget(d); lay.addLayout(br); self._load()

    def _load(self):
        self._t.setRowCount(0); self._c.clear()
        try:
            from models.cost_center import get_all_cost_centers
            from models.company     import get_all_companies
            for cc in get_all_cost_centers():
                r=self._t.rowCount(); self._t.insertRow(r)
                for col,v in enumerate([cc["name"],cc.get("company_name","")]):
                    it=QTableWidgetItem(v); it.setData(Qt.UserRole,cc); self._t.setItem(r,col,it)
                self._t.setRowHeight(r,34)
            for c in get_all_companies(): self._c.addItem(c["name"],c["id"])
        except Exception: pass

    def _add(self):
        n=self._n.text().strip(); cid=self._c.currentData()
        if not n or not cid: self._msg("Name and company required.",True); return
        try:
            from models.cost_center import create_cost_center; create_cost_center(n,cid)
            self._n.clear(); self._load(); self._msg(f"'{n}' added.")
        except Exception as e: self._msg(_friendly_error(e),True)

    def _del(self):
        row=self._t.currentRow()
        if row<0: self._msg("Select a row.",True); return
        cc=self._t.item(row,0).data(Qt.UserRole)
        if QMessageBox.question(self,"Delete",f"Delete '{cc['name']}'?",QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes: return
        try:
            from models.cost_center import delete_cost_center; delete_cost_center(cc["id"]); self._load(); self._msg("Deleted.")
        except Exception as e: self._msg(_friendly_error(e),True)

class PriceListDialog(_Base):
    TITLE = "Price Lists"; W=520
    def _build(self, lay):
        self._t=_tbl(); self._t.setColumnCount(2); self._t.setHorizontalHeaderLabels(["Name","Selling"])
        h=self._t.horizontalHeader(); h.setSectionResizeMode(0,QHeaderView.Stretch)
        h.setSectionResizeMode(1,QHeaderView.Fixed); self._t.setColumnWidth(1,100)
        lay.addWidget(self._t,1); lay.addWidget(_hr())
        row=QHBoxLayout(); row.setSpacing(8)
        self._n=_input("Price list name *"); self._s=_combo(); self._s.addItems(["Selling","Not Selling"]); self._s.setFixedWidth(140)
        row.addWidget(QLabel("Name:",styleSheet="background:transparent;font-size:12px;")); row.addWidget(self._n,2)
        row.addWidget(QLabel("Type:",styleSheet="background:transparent;font-size:12px;")); row.addWidget(self._s)
        lay.addLayout(row); self._status(lay)
        br=QHBoxLayout(); br.setSpacing(8)
        a=_btn("Add",color=SUCCESS,hover=SUCCESS_H); d=_btn("Delete",color=DANGER,hover=DANGER_H)
        a.clicked.connect(self._add); d.clicked.connect(self._del)
        br.addStretch(); br.addWidget(a); br.addWidget(d); lay.addLayout(br); self._load()

    def _load(self):
        self._t.setRowCount(0)
        try:
            from models.price_list import get_all_price_lists
            for pl in get_all_price_lists():
                r=self._t.rowCount(); self._t.insertRow(r)
                for col,v in enumerate([pl["name"],"Yes" if pl["selling"] else "No"]):
                    it=QTableWidgetItem(v); it.setData(Qt.UserRole,pl); self._t.setItem(r,col,it)
                self._t.setRowHeight(r,34)
        except Exception: pass

    def _add(self):
        n=self._n.text().strip()
        if not n: self._msg("Name required.",True); return
        try:
            from models.price_list import create_price_list; create_price_list(n,self._s.currentIndex()==0)
            self._n.clear(); self._load(); self._msg(f"'{n}' added.")
        except Exception as e: self._msg(_friendly_error(e),True)

    def _del(self):
        row=self._t.currentRow()
        if row<0: self._msg("Select a row.",True); return
        pl=self._t.item(row,0).data(Qt.UserRole)
        if QMessageBox.question(self,"Delete",f"Delete '{pl['name']}'?",QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes: return
        try:
            from models.price_list import delete_price_list; delete_price_list(pl["id"]); self._load(); self._msg("Deleted.")
        except Exception as e: self._msg(_friendly_error(e),True)

class CustomerDialog(_Base):
    TITLE = "Customers"; W=900; H=640
    def _build(self, lay):
        sr=QHBoxLayout(); self._q=_input("Search by name, trade name or phone…")
        self._q.textChanged.connect(self._search); sr.addWidget(self._q); lay.addLayout(sr)
        self._t=_tbl(); self._t.setColumnCount(5); self._t.setHorizontalHeaderLabels(["Name","Type","Group","Phone","City"])
        h=self._t.horizontalHeader(); h.setSectionResizeMode(0,QHeaderView.Stretch)
        for i in [1,2,3,4]: h.setSectionResizeMode(i,QHeaderView.Fixed); self._t.setColumnWidth(i,110)
        lay.addWidget(self._t,1); lay.addWidget(_hr())
        g=QGridLayout(); g.setSpacing(8)
        self._fn=_input("Name *"); self._ft=_combo(); self._ft.addItems(["","Individual","Company"])
        self._ftr=_input("Trade"); self._fph=_input("Phone"); self._fem=_input("Email"); self._fct=_input("City")
        self._fg=_combo(); self._fw=_combo(); self._fc=_combo(); self._fp=_combo()
        for row,col,lbl,w in [(0,0,"Name *",self._fn),(0,2,"Type",self._ft),(1,0,"Trade",self._ftr),(1,2,"Phone",self._fph),(2,0,"Email",self._fem),(2,2,"City",self._fct),(3,0,"Group *",self._fg),(3,2,"Warehouse *",self._fw),(4,0,"Cost Center *",self._fc),(4,2,"Price List *",self._fp)]:
            g.addWidget(QLabel(lbl,styleSheet="background:transparent;font-size:12px;"),row,col)
            g.addWidget(w,row,col+1)
        lay.addLayout(g); self._status(lay)
        br=QHBoxLayout(); br.setSpacing(8)
        a=_btn("Add Customer",color=SUCCESS,hover=SUCCESS_H); d=_btn("Delete",color=DANGER,hover=DANGER_H)
        a.clicked.connect(self._add); d.clicked.connect(self._del)
        br.addStretch(); br.addWidget(a); br.addWidget(d); lay.addLayout(br); self._load()

    def _load(self):
        self._t.setRowCount(0)
        try:
            from models.customer import get_all_customers; custs=get_all_customers()
        except Exception: custs=[]
        self._fill(custs); self._combos()

    def _search(self,q):
        if not q.strip(): self._load(); return
        try:
            from models.customer import search_customers; self._fill(search_customers(q))
        except Exception: pass

    def _fill(self,custs):
        self._t.setRowCount(0)
        for c in custs:
            r=self._t.rowCount(); self._t.insertRow(r)
            for col,v in enumerate([c["customer_name"],c.get("customer_type",""),c.get("customer_group_name",""),c.get("custom_telephone_number",""),c.get("custom_city","")]):
                it=QTableWidgetItem(str(v)); it.setData(Qt.UserRole,c); self._t.setItem(r,col,it)
            self._t.setRowHeight(r,34)

    def _combos(self):
        try:
            from models.customer_group import get_all_customer_groups
            from models.warehouse       import get_all_warehouses
            from models.cost_center     import get_all_cost_centers
            from models.price_list      import get_all_price_lists
            gs=get_all_customer_groups(); ws=get_all_warehouses(); cs=get_all_cost_centers(); ps=get_all_price_lists()
        except Exception: gs=[];ws=[];cs=[];ps=[]
        for cb in [self._fg,self._fw,self._fc,self._fp]: cb.clear()
        for g in gs: self._fg.addItem(g["name"],g["id"])
        for w in ws: self._fw.addItem(f"{w['name']} ({w.get('company_name','')})",w["id"])
        for c in cs: self._fc.addItem(f"{c['name']} ({c.get('company_name','')})",c["id"])
        for p in ps: self._fp.addItem(p["name"],p["id"])

    def _add(self):
        n=self._fn.text().strip()
        if not n: self._msg("Name required.",True); return
        gid=self._fg.currentData(); wid=self._fw.currentData(); cid=self._fc.currentData(); pid=self._fp.currentData()
        if not all([gid,wid,cid,pid]): self._msg("Group, Warehouse, Cost Center and Price List required.",True); return
        try:
            from models.customer import create_customer
            create_customer(customer_name=n,customer_group_id=gid,custom_warehouse_id=wid,custom_cost_center_id=cid,default_price_list_id=pid,customer_type=self._ft.currentText() or None,custom_trade_name=self._ftr.text().strip(),custom_telephone_number=self._fph.text().strip(),custom_email_address=self._fem.text().strip(),custom_city=self._fct.text().strip())
            for f in [self._fn,self._ftr,self._fph,self._fem,self._fct]: f.clear()
            self._load(); self._msg(f"'{n}' added.")
        except Exception as e: self._msg(_friendly_error(e),True)

    def _del(self):
        row=self._t.currentRow()
        if row<0: self._msg("Select a row.",True); return
        c=self._t.item(row,0).data(Qt.UserRole)
        if QMessageBox.question(self,"Delete",f"Delete '{c['customer_name']}'?",QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes: return
        try:
            from models.customer import delete_customer; delete_customer(c["id"]); self._load(); self._msg("Deleted.")
        except Exception as e: self._msg(_friendly_error(e),True)

class UsersDialog(_Base):
    TITLE = "Users"; W=640
    def __init__(self, parent=None, current_user=None, **kw):
        self._cu = current_user or {}
        super().__init__(parent, **kw)

    def _build(self, lay):
        self._t=_tbl(); self._t.setColumnCount(3); self._t.setHorizontalHeaderLabels(["ID","Username","Role"])
        h=self._t.horizontalHeader(); h.setSectionResizeMode(0,QHeaderView.Fixed); self._t.setColumnWidth(0,60)
        h.setSectionResizeMode(1,QHeaderView.Stretch); h.setSectionResizeMode(2,QHeaderView.Fixed); self._t.setColumnWidth(2,110)
        lay.addWidget(self._t,1); lay.addWidget(_hr())
        row=QHBoxLayout(); row.setSpacing(8)
        self._u=_input("Username *"); self._u.setFixedWidth(180)
        self._pw=_input("Password *"); self._pw.setEchoMode(QLineEdit.Password); self._pw.setFixedWidth(180)
        self._r=_combo(); self._r.addItems(["cashier","admin"]); self._r.setFixedWidth(110)
        row.addWidget(self._u); row.addWidget(self._pw); row.addWidget(self._r); row.addStretch(); lay.addLayout(row)
        self._status(lay)
        br=QHBoxLayout(); br.setSpacing(8)
        a=_btn("Add User",color=SUCCESS,hover=SUCCESS_H); d=_btn("Delete",color=DANGER,hover=DANGER_H)
        a.clicked.connect(self._add); d.clicked.connect(self._del)
        br.addStretch(); br.addWidget(a); br.addWidget(d); lay.addLayout(br); self._load()

    def _load(self):
        self._t.setRowCount(0)
        try:
            from models.user import get_all_users
            for u in get_all_users():
                r=self._t.rowCount(); self._t.insertRow(r)
                for col,k in enumerate(["id","username","role"]):
                    it=QTableWidgetItem(str(u.get(k,""))); it.setData(Qt.UserRole,u)
                    it.setTextAlignment(Qt.AlignCenter if col!=1 else Qt.AlignLeft|Qt.AlignVCenter)
                    if k=="role": it.setForeground(QColor(ACCENT if u["role"]=="admin" else MUTED))
                    self._t.setItem(r,col,it)
                self._t.setRowHeight(r,34)
        except Exception: pass

    def _add(self):
        u=self._u.text().strip(); p=self._pw.text().strip()
        if not u or not p: self._msg("Username and password required.",True); return
        try:
            from models.user import create_user; create_user(u,p,self._r.currentText())
            self._u.clear(); self._pw.clear(); self._load(); self._msg(f"'{u}' created.")
        except Exception as e: self._msg(_friendly_error(e),True)

    def _del(self):
        row=self._t.currentRow()
        if row<0: self._msg("Select a row.",True); return
        u=self._t.item(row,0).data(Qt.UserRole)
        if u["id"]==self._cu.get("id"): self._msg("Cannot delete your own account.",True); return
        if QMessageBox.question(self,"Delete",f"Delete '{u['username']}'?",QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes: return
        try:
            from models.user import delete_user; delete_user(u["id"]); self._load(); self._msg("Deleted.")
        except Exception as e: self._msg(_friendly_error(e),True)

# =============================================================================
# HardwareDialog — Hardware Settings
# =============================================================================
class HardwareDialog(_Base):
    TITLE = "Hardware Settings"
    W, H = 520, 420

    def _build(self, lay):
        hw = _load_hw()
        
        # Printer Row
        pr_row = QHBoxLayout(); pr_row.setSpacing(12)
        pr_lbl = QLabel("Main Receipt Printer")
        pr_lbl.setStyleSheet(f"color:{DARK_TEXT};font-size:13px;font-weight:bold;background:transparent;")
        
        self._main_printer = _combo(); self._main_printer.setFixedWidth(240)
        printers = _get_system_printers()
        for p in printers: self._main_printer.addItem(p)
        
        idx = self._main_printer.findText(hw.get("main_printer", "(None)"))
        self._main_printer.setCurrentIndex(idx if idx >= 0 else 0)
        
        pr_row.addWidget(pr_lbl); pr_row.addStretch(); pr_row.addWidget(self._main_printer)
        lay.addLayout(pr_row); lay.addSpacing(10); lay.addWidget(_hr()); lay.addSpacing(10)

        # Order Stations
        ord_lbl = QLabel("Active Order Stations")
        ord_lbl.setStyleSheet(f"font-size:13px;font-weight:bold;color:{NAVY};background:transparent;")
        lay.addWidget(ord_lbl); lay.addSpacing(10)

        order_cfg = hw.get("orders", {})
        self._order_checks = []
        chk_style = f"""
            QCheckBox {{ font-size:13px; color:{DARK_TEXT}; background:transparent; padding:4px; }}
            QCheckBox::indicator {{ width:18px; height:18px; border:1px solid {BORDER}; background:{WHITE}; }}
            QCheckBox::indicator:checked {{ background:{ACCENT}; border-color:{ACCENT}; }}
        """

        for name in _ORDER_STATIONS:
            row = QHBoxLayout()
            lbl = QLabel(name); lbl.setStyleSheet(f"font-size:13px;color:{DARK_TEXT};")
            chk = QCheckBox(); chk.setStyleSheet(chk_style)
            chk.setChecked(order_cfg.get(name, {}).get("active", False))
            
            row.addWidget(lbl); row.addStretch(); row.addWidget(chk)
            lay.addLayout(row)
            self._order_checks.append(chk)
        
        lay.addStretch(); self._status(lay)

    def _save(self):
        data = {"main_printer": self._main_printer.currentText(), "orders": {}}
        for chk, name in zip(self._order_checks, _ORDER_STATIONS):
            data["orders"][name] = {"active": chk.isChecked()}
        _save_hw(data)
        self._msg("Hardware settings saved.")

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