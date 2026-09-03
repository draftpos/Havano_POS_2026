# =============================================================================
# views/dialogs/stock_file_dialog.py  -  Updated for UOM & Conversion
# =============================================================================

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QComboBox, QFrame, QGroupBox,
    QMessageBox, QSizePolicy, QFormLayout, QCheckBox, QTabWidget
)
from PySide6.QtCore import Qt, QEvent, QTimer
from PySide6.QtGui import QColor, QDoubleValidator
import qtawesome as qta

from models.product import (
    get_all_products,
    search_products,
    get_categories,
    create_product,
    update_product,
    get_product_by_part_no,
)

# ── colours ───────────────────────────────────────────────────────────────────
from theme import *

# =============================================================================
# HELPERS
# =============================================================================

def _hr():
    ln = QFrame()
    ln.setFrameShape(QFrame.HLine)
    ln.setStyleSheet(f"background: {BORDER}; border: none;")
    ln.setFixedHeight(1)
    return ln

def _btn(text, bg, hov, w=100, h=64):
    b = QPushButton(text)
    b.setFixedSize(w, h)
    b.setCursor(Qt.PointingHandCursor)
    b.setStyleSheet(f"""
        QPushButton {{
            background-color: {bg}; color: {WHITE}; border: none;
            border-radius: 8px; font-size: 11px; font-weight: bold; text-align: center;
        }}
        QPushButton:hover   {{ background-color: {hov}; }}
        QPushButton:pressed {{ background-color: {NAVY_3}; }}
        QPushButton:disabled {{ background-color: {LIGHT}; color: {MUTED}; }}
    """)
    return b

def _combo():
    c = QComboBox()
    c.setFixedHeight(28)
    c.setStyleSheet(f"""
        QComboBox {{
            background-color: {WHITE}; color: {DARK_TEXT};
            border: 1px solid {BORDER}; border-radius: 4px;
            padding: 2px 8px; font-size: 12px;
        }}
        QComboBox::drop-down {{ border: none; width: 20px; }}
        QComboBox QAbstractItemView {{
            background: {WHITE}; border: 1px solid {BORDER};
            selection-background-color: {ACCENT}; selection-color: {WHITE};
        }}
    """)
    return c

# =============================================================================
# ITEM CODE INPUT DIALOG - shown when user double-clicks the Item Code cell
# =============================================================================
class _ItemCodeInputDialog(QDialog):
    def __init__(self, current_code: str, parent=None):
        super().__init__(parent)
        self.value = ""
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(380)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)

        card = QFrame()
        card.setObjectName("icard")
        card.setStyleSheet(f"""
            QFrame#icard {{
                background:{WHITE}; border-radius:12px;
                border:1px solid {BORDER};
            }}
        """)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)

        # Header
        hdr = QWidget()
        hdr.setFixedHeight(52)
        hdr.setStyleSheet(f"background:{NAVY}; border-top-left-radius:12px; border-top-right-radius:12px;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(16, 0, 16, 0)
        lbl = QLabel("Change Item Code")
        lbl.setStyleSheet(f"color:{WHITE}; font-size:14px; font-weight:bold;")
        hl.addWidget(lbl)
        cl.addWidget(hdr)

        body = QVBoxLayout()
        body.setContentsMargins(20, 20, 20, 20)
        body.setSpacing(14)

        sub = QLabel("Enter the item code for this wholesale price row:")
        sub.setStyleSheet(f"color:{MUTED}; font-size:11px;")
        body.addWidget(sub)

        self._edit = QLineEdit(current_code)
        self._edit.setFixedHeight(40)
        self._edit.setAlignment(Qt.AlignCenter)
        self._edit.setStyleSheet(f"""
            QLineEdit {{
                background:{OFF_WHITE}; color:{DARK_TEXT};
                border:2px solid {ACCENT}; border-radius:6px;
                font-size:16px; font-weight:bold; padding:0 10px;
            }}
        """)
        self._edit.selectAll()
        body.addWidget(self._edit)

        btns = QHBoxLayout()
        btns.setSpacing(8)
        ok = QPushButton("  Confirm")
        ok.setFixedHeight(36)
        ok.setCursor(Qt.PointingHandCursor)
        ok.setStyleSheet(f"background:{SUCCESS}; color:{WHITE}; border-radius:6px; font-weight:bold; font-size:12px;")
        ok.clicked.connect(self._accept)
        cancel = QPushButton("Cancel")
        cancel.setFixedHeight(36)
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.setStyleSheet(f"background:{NAVY_2}; color:{WHITE}; border-radius:6px; font-size:12px;")
        cancel.clicked.connect(self.reject)
        btns.addWidget(ok)
        btns.addWidget(cancel)
        body.addLayout(btns)

        cl.addLayout(body)
        outer.addWidget(card)
        self._edit.returnPressed.connect(self._accept)

    def _accept(self):
        self.value = self._edit.text().strip().upper()
        self.accept()


# =============================================================================
# EDIT DIALOG (Requirement 6: UOM & Conversion)
# =============================================================================
class StockEditDialog(QDialog):
    def __init__(self, parent=None, product=None):
        super().__init__(parent)
        self.product = product # None if new
        self.setWindowTitle("Edit Product" if product else "New Product")
        self.result_data = {}
        self._build_ui()
        if product:
            self._load_product()
        else:
            self.f_cat.setText("Basic")
            self.f_uom.setCurrentText("Unit")
            import random
            self.f_part.setText(f"{random.randint(10000, 99999)}")
            try:
                from models.price_list import get_all_price_lists
                pls = get_all_price_lists()
                if pls:
                    for pl in pls:
                        self._add_price_row_to_table(self.f_part.text(), pl["name"], "Unit", 0.00)
                else:
                    self._add_price_row_to_table(self.f_part.text(), "Standard Selling", "Unit", 0.00)
            except Exception:
                self._add_price_row_to_table(self.f_part.text(), "Standard Selling", "Unit", 0.00)
        # Auto-sync item code column whenever the part number field changes
        self.f_part.textChanged.connect(self._sync_item_code_column)
        self.resize(850, 600)

    def _build_ui(self):
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(10, 10, 10, 10)
        
        card = QFrame()
        card.setObjectName("editCard")
        card.setStyleSheet(f"""
            QFrame#editCard {{
                background:{WHITE}; border-radius:12px;
                border: 1px solid {BORDER};
            }}
        """)
        main_lay.addWidget(card)
        
        cl = QVBoxLayout(card); cl.setContentsMargins(0, 0, 0, 0); cl.setSpacing(0)
        
        # Header
        hdr = QWidget(); hdr.setFixedHeight(70)
        hdr.setStyleSheet(f"""
            QWidget {{
                background: {NAVY};
                border-top-left-radius:15px; border-top-right-radius:15px;
            }}
        """)
        hl = QHBoxLayout(hdr); hl.setContentsMargins(20, 0, 20, 0)
        
        title = QLabel("Add New Product" if not self.product else "Edit Product")
        title.setStyleSheet(f"color:{WHITE}; font-size:15px; font-weight:bold;")
        hl.addWidget(title)
        hl.addStretch()
        
        # Actions at top
        save = QPushButton("  Save")
        save.setIcon(qta.icon("fa5s.save", color="white"))
        save.setFixedSize(90, 36)
        save.setCursor(Qt.PointingHandCursor)
        save.setStyleSheet(f"""
            QPushButton {{
                background: {SUCCESS}; color: white; border-radius: 8px; font-weight: bold;
            }}
            QPushButton:hover {{ background: {SUCCESS_H}; }}
        """)
        save.clicked.connect(self._on_save)
        
        if self.product:
            delete_btn = QPushButton("  Delete")
            delete_btn.setIcon(qta.icon("fa5s.trash", color="white"))
            delete_btn.setFixedSize(90, 36)
            delete_btn.setCursor(Qt.PointingHandCursor)
            delete_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {DANGER}; color: white; border-radius: 8px; font-weight: bold;
                }}
                QPushButton:hover {{ background: {DANGER_H}; }}
            """)
            delete_btn.clicked.connect(self._on_delete)
            hl.addWidget(delete_btn)
            hl.addSpacing(8)
        
        cancel = QPushButton("  Cancel")
        cancel.setIcon(qta.icon("fa5s.times", color="white"))
        cancel.setFixedSize(90, 36)
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.setStyleSheet(f"""
            QPushButton {{
                background: {NAVY_2}; color: white; border-radius: 8px; font-weight: bold;
            }}
            QPushButton:hover {{ background: {ACCENT}; }}
        """)
        cancel.clicked.connect(self.reject)
        
        hl.addWidget(save)
        hl.addSpacing(8)
        hl.addWidget(cancel)
        cl.addWidget(hdr)

        # Body with Tabs
        body = QWidget(); bl = QVBoxLayout(body); bl.setContentsMargins(20, 20, 20, 20)
        
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: 1px solid {BORDER}; border-radius: 6px; background: {WHITE}; }}
            QTabBar::tab {{ background: {LIGHT}; color: {DARK_TEXT}; padding: 8px 16px; margin-right: 2px; border-top-left-radius: 6px; border-top-right-radius: 6px; }}
            QTabBar::tab:selected {{ background: {WHITE}; border: 1px solid {BORDER}; border-bottom: none; font-weight: bold; }}
        """)
        
        self.tab_detail = QWidget()
        self.tab_pricelists = QWidget()
        self.tab_advanced = QWidget()
        self.tab_components = QWidget()
        
        self.tabs.addTab(self.tab_detail, "Detail")
        self.tabs.addTab(self.tab_pricelists, "Wholesale Price")
        self.tabs.addTab(self.tab_advanced, "Advanced")
        self.tabs.addTab(self.tab_components, "Product Bundle")
        
        bl.addWidget(self.tabs)
        cl.addWidget(body)
        
        # Wire pricelist table double-click handler (called after tabs built)
        QTimer.singleShot(0, self._setup_pl_table_edit)

        edit_style = f"border:1px solid {BORDER}; border-radius:6px; padding:6px 10px; background:{WHITE};"
        
        # --- Detail Tab ---
        detail_lay = QHBoxLayout(self.tab_detail)
        left_form = QFormLayout()
        left_form.setLabelAlignment(Qt.AlignLeft)
        right_form = QFormLayout()
        right_form.setLabelAlignment(Qt.AlignLeft)
        
        self.f_part = QLineEdit(); self.f_part.setStyleSheet(edit_style); self.f_part.setFixedHeight(34)
        self.f_name = QLineEdit(); self.f_name.setStyleSheet(edit_style); self.f_name.setFixedHeight(34)
        self.f_hs_code = QLineEdit(); self.f_hs_code.setStyleSheet(edit_style); self.f_hs_code.setFixedHeight(34)
        
        from PySide6.QtWidgets import QCompleter
        self.f_cat = QLineEdit()
        self.f_cat.setPlaceholderText("Select or type category...")
        self.f_cat.setStyleSheet(edit_style)
        self.f_cat.setFixedHeight(34)
        self._cat_completer = QCompleter(get_categories())
        self._cat_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._cat_completer.setFilterMode(Qt.MatchContains)
        self._style_completer(self._cat_completer)
        self._cat_completer.popup().window().setAttribute(Qt.WA_TranslucentBackground, False)
        self.f_cat.setCompleter(self._cat_completer)
        self.f_cat.installEventFilter(self)
        self._cat_completer.activated.connect(lambda text: self._on_completer_activated(self.f_cat))



        self.f_cost = QLineEdit(); self.f_cost.setStyleSheet(edit_style); self.f_cost.setFixedHeight(34)
        self.f_price = QLineEdit(); self.f_price.setStyleSheet(edit_style); self.f_price.setFixedHeight(34)
        
        self.f_price.textChanged.connect(self._sync_selling_price)
        
        self.f_uom = QComboBox(); self.f_uom.setStyleSheet(edit_style); self.f_uom.setFixedHeight(34)
        uom_names = []
        try:
            from models.uom import get_all_uoms
            uoms = get_all_uoms()
            uom_names = [u["name"] for u in uoms] if uoms else []
        except Exception:
            pass
        if not uom_names:
            uom_names = ["Unit", "Kg", "Litre", "Meter", "Box", "Pack", "Gram", "Plate", "Dozen"]
        self.f_uom.addItems(uom_names)
        self.f_uom.view().window().setAttribute(Qt.WA_TranslucentBackground, False)
        self.f_uom.currentTextChanged.connect(self._sync_selling_uom)
        
        
        self.f_stock = QLineEdit(); self.f_stock.setStyleSheet(edit_style); self.f_stock.setFixedHeight(34)
        self.f_reorder = QLineEdit(); self.f_reorder.setStyleSheet(edit_style); self.f_reorder.setFixedHeight(34)
        
        try:
            from settings.pharmacy_settings import get_pharmacy_mode
            is_pharm_mode = get_pharmacy_mode()
        except Exception:
            is_pharm_mode = False
        self.f_is_pharmacy = QCheckBox("Pharmacy Product" if is_pharm_mode else "Pharmacy Product / Batch Tracking")
        self.f_is_pharmacy.setStyleSheet(f"""
            QCheckBox {{ color: #1a5fb4; font-size: 13px; font-weight: bold; }}
            QCheckBox::indicator {{ width: 18px; height: 18px; border: 2px solid #c8d8ec; border-radius: 4px; background-color: #ffffff; }}
            QCheckBox::indicator:checked {{ background-color: #1a7a3c; border: 2px solid #1a7a3c; image: url(assets/check.svg); }}
        """)
        
        self.f_track_stock = QCheckBox("Track Stock")
        self.f_track_stock.setChecked(True)
        self.f_track_stock.setStyleSheet(f"""
            QCheckBox {{ color: #1a5fb4; font-size: 13px; font-weight: bold; }}
            QCheckBox::indicator {{ width: 18px; height: 18px; border: 2px solid #c8d8ec; border-radius: 4px; background-color: #ffffff; }}
            QCheckBox::indicator:checked {{ background-color: #1a7a3c; border: 2px solid #1a7a3c; image: url(assets/check.svg); }}
        """)
        
        self.f_is_bundle = QCheckBox("Product Bundle")
        self.f_is_bundle.setStyleSheet(f"""
            QCheckBox {{ color: #1a5fb4; font-size: 13px; font-weight: bold; }}
            QCheckBox::indicator {{ width: 18px; height: 18px; border: 2px solid #c8d8ec; border-radius: 4px; background-color: #ffffff; }}
            QCheckBox::indicator:checked {{ background-color: #1a7a3c; border: 2px solid #1a7a3c; image: url(assets/check.svg); }}
        """)
        
        self.f_is_butchery = QCheckBox("Butchery Item")
        self.f_is_butchery.setStyleSheet(f"""
            QCheckBox {{ color: #1a5fb4; font-size: 13px; font-weight: bold; }}
            QCheckBox::indicator {{ width: 18px; height: 18px; border: 2px solid #c8d8ec; border-radius: 4px; background-color: #ffffff; }}
            QCheckBox::indicator:checked {{ background-color: #1a7a3c; border: 2px solid #1a7a3c; image: url(assets/check.svg); }}
        """)

        
        self.f_tax_rule = QComboBox(); self.f_tax_rule.setFixedHeight(34)
        self.f_tax_rule.setStyleSheet(edit_style)
        try:
            from models.tax_rule import TaxRuleRepository
            rules = TaxRuleRepository.get_all()
            self.f_tax_rule.addItem("No Tax", 0.0)
            for r in rules:
                self.f_tax_rule.addItem(f"{r.tax_name} ({r.tax_rate}%)", r.tax_name)
        except Exception:
            self.f_tax_rule.addItem("No Tax", 0.0)
        self.f_tax_rule.view().window().setAttribute(Qt.WA_TranslucentBackground, False)
        


        def add_row(form, label, field):
            ll = QLabel(label.upper())
            ll.setStyleSheet(f"color:{MUTED}; font-size:10px; font-weight:bold; margin-top:5px;")
            form.addRow(ll, field)
            return ll
            
        add_row(left_form, "Item Code", self.f_part)
        add_row(left_form, "Item Name", self.f_name)
        add_row(left_form, "Category", self.f_cat)
        lbl_hs = add_row(left_form, "HS Code", self.f_hs_code)
        
        try:
            from models.fiscal_settings import FiscalSettingsRepository
            fiscal = FiscalSettingsRepository.get_settings()
            if not fiscal or not fiscal.enabled:
                self.f_hs_code.hide()
                lbl_hs.hide()
        except Exception as e:
            print(f"Error checking fiscal settings: {e}")
            self.f_hs_code.hide()
            lbl_hs.hide()
        
        add_row(left_form, "Tax Rule", self.f_tax_rule)
        self._lbl_cost = add_row(left_form, "Purchase Price", self.f_cost)
        self._lbl_price = add_row(left_form, "Selling Price", self.f_price)
        add_row(left_form, "Base UOM", self.f_uom)
        
        self._lbl_stock = add_row(right_form, "Opening Stock", self.f_stock)
        self._lbl_reorder = add_row(right_form, "Reorder Level", self.f_reorder)
        
        # Batch Tracking, Track Stock & Product Bundle
        right_form.addRow("", self.f_is_pharmacy)
        right_form.addRow("", self.f_track_stock)
        right_form.addRow("", self.f_is_bundle)
        right_form.addRow("", self.f_is_butchery)

        # Hide pharmacy/butchery checkboxes if respective modes are not active in settings
        try:
            from models.company_defaults import get_defaults
            defaults = get_defaults()
            pharmacy_mode_active = defaults.get("pharmacy_mode") == "1"
            butchery_mode_active = defaults.get("butchery_mode") == "1"
        except Exception:
            pharmacy_mode_active = False
            butchery_mode_active = False

        if not pharmacy_mode_active:
            self.f_is_pharmacy.hide()
        if not butchery_mode_active:
            self.f_is_butchery.hide()

        self.f_is_pharmacy.stateChanged.connect(self._toggle_opening_stock)
        self.f_is_bundle.stateChanged.connect(self._toggle_bundle_state)


        detail_lay.addLayout(left_form)
        detail_lay.addSpacing(20)
        detail_lay.addLayout(right_form)

        # --- Pricelists Tab ---
        pl_lay = QVBoxLayout(self.tab_pricelists)
        pl_lay.setContentsMargins(10, 15, 10, 10)
        pl_lay.setSpacing(15)
        
        pl_actions = QHBoxLayout()
        btn_add_pl = QPushButton("  Add Row")
        btn_add_pl.setIcon(qta.icon("fa5s.plus", color="white"))
        btn_add_pl.setStyleSheet(f"background:{SUCCESS}; color:{WHITE}; padding:6px; border-radius:4px; font-weight:bold;")
        btn_add_pl.clicked.connect(self._add_empty_price_row)
        
        btn_rem_pl = QPushButton("  Remove Row")
        btn_rem_pl.setIcon(qta.icon("fa5s.trash", color="white"))
        btn_rem_pl.setStyleSheet(f"background:{DANGER}; color:{WHITE}; padding:6px; border-radius:4px; font-weight:bold;")
        btn_rem_pl.clicked.connect(self._remove_price_row_clicked)
        
        pl_actions.addWidget(btn_add_pl)
        pl_actions.addWidget(btn_rem_pl)
        pl_actions.addStretch()
        pl_lay.addLayout(pl_actions)

        self.pl_table = QTableWidget(0, 5)
        self.pl_table.setHorizontalHeaderLabels(["Item Code", "Wholesale Price", "UOM", "Qty", "Price"])
        self.pl_table.verticalHeader().setVisible(False)
        self.pl_table.setAlternatingRowColors(True)
        self.pl_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.pl_table.setShowGrid(True)
        self.pl_table.setStyleSheet(f"""
            QTableWidget {{
                background:{WHITE}; border:1px solid {BORDER};
                gridline-color:{BORDER}; outline:none;
            }}
            QHeaderView::section {{
                background:{NAVY}; color:{WHITE}; font-weight:bold;
                padding:10px 8px; border:none;
                border-right:1px solid {NAVY_2}; font-size:11px;
            }}
            QTableWidget::item {{ padding:4px 8px; }}
            QTableWidget::item:selected {{ background:{ACCENT}; color:{WHITE}; }}
        """)
        
        hdr = self.pl_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Fixed)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)  # Wholesale Price fills remaining
        hdr.setSectionResizeMode(2, QHeaderView.Fixed)    # UOM fixed
        hdr.setSectionResizeMode(3, QHeaderView.Fixed)    # Qty fixed
        hdr.setSectionResizeMode(4, QHeaderView.Fixed)    # Price fixed
        self.pl_table.setColumnWidth(0, 150)
        self.pl_table.setColumnWidth(2, 140)
        self.pl_table.setColumnWidth(3, 80)
        self.pl_table.setColumnWidth(4, 110)
        pl_lay.addWidget(self.pl_table)

        # --- Advanced Tab ---
        adv_lay = QVBoxLayout(self.tab_advanced)
        adv_lay.setContentsMargins(20, 20, 20, 20)
        adv_lay.setSpacing(15)

        info_lbl = QLabel("Configure advanced product order settings:")
        info_lbl.setStyleSheet(f"color:{MUTED}; font-size:12px; font-weight:bold;")
        adv_lay.addWidget(info_lbl)

        vbox = QVBoxLayout()
        vbox.setSpacing(15)

        self.f_orders = []
        for i in range(1, 7):
            f_ord = QCheckBox(f"Order {i}")
            f_ord.setStyleSheet(f"""
                QCheckBox {{
                    color: {DARK_TEXT};
                    font-size: 13px;
                    font-weight: bold;
                }}
                QCheckBox::indicator {{
                    width: 18px;
                    height: 18px;
                    border: 2px solid {BORDER};
                    border-radius: 4px;
                    background-color: {WHITE};
                }}
                QCheckBox::indicator:checked {{
                    background-color: {SUCCESS};
                    border: 2px solid {SUCCESS};
                    image: url(assets/check.svg);
                }}
            """)
            self.f_orders.append(f_ord)
            vbox.addWidget(f_ord)

        adv_lay.addLayout(vbox)
        adv_lay.addStretch()

        # --- Components Tab ---
        comp_lay = QVBoxLayout(self.tab_components)
        comp_lay.setContentsMargins(10, 15, 10, 10)
        comp_lay.setSpacing(15)
        self.comp_search = QLineEdit(self.tab_components)
        self.comp_search.setPlaceholderText("Search...")
        self.comp_search.setStyleSheet("background: rgba(255,255,255,230); color: #333; font-weight: bold; border: 2px solid #1a5fb4;")
        self.comp_search.hide()
        
        # Load completer for components
        try:
            from database.db import get_connection
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT part_no, name FROM products WHERE ISNULL(active, 1) = 1")
            prods = cur.fetchall()
            conn.close()
            
            words = []
            for p in prods:
                if p[0]: words.append(str(p[0]))
                if p[1]: words.append(str(p[1]))
            
            self._comp_completer = QCompleter(list(set(words)))
            self._comp_completer.setCaseSensitivity(Qt.CaseInsensitive)
            self._comp_completer.setFilterMode(Qt.MatchContains)
            self._style_completer(self._comp_completer)
            self._comp_completer.popup().window().setAttribute(Qt.WA_TranslucentBackground, False)
            self.comp_search.setCompleter(self._comp_completer)
            self._comp_completer.activated.connect(self._add_component_row)
        except Exception as e:
            print("Error loading components autocomplete:", e)
        self.comp_table = QTableWidget(15, 4)
        self.comp_table.setHorizontalHeaderLabels(["Part No", "Product Name", "Qty", "Action"])
        self.comp_table.setAlternatingRowColors(True)
        self.comp_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.comp_table.setShowGrid(True)
        self.comp_table.verticalHeader().setVisible(False)
        self.comp_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {WHITE}; color: {NAVY};
                border: 1px solid {BORDER}; gridline-color: #b0bec5;
                font-size: 12px; outline: none;
                selection-background-color: transparent;
            }}
            QTableWidget::item {{
                padding: 0 4px; color: {NAVY}; border-bottom: 1px solid {LIGHT};
            }}
            QTableWidget::item:selected {{
                background-color: #fff8e1; color: {NAVY};
            }}
            QHeaderView::section {{
                background-color: #f0e8d0; color: {NAVY};
                padding: 4px 6px; border: none; border-right: 1px solid {BORDER};
                font-size: 11px; font-weight: bold; letter-spacing: 0.3px;
            }}
        """)
        
        chdr = self.comp_table.horizontalHeader()
        chdr.setSectionResizeMode(0, QHeaderView.Interactive)
        self.comp_table.setColumnWidth(0, 150)
        chdr.setSectionResizeMode(1, QHeaderView.Stretch)
        chdr.setSectionResizeMode(2, QHeaderView.Fixed)
        chdr.setSectionResizeMode(3, QHeaderView.Fixed)
        self.comp_table.setColumnWidth(2, 100)
        self.comp_table.setColumnWidth(3, 80)
        
        for r in range(15):
            self.comp_table.setRowHeight(r, 38)
            for c in range(2):
                it = QTableWidgetItem("")
                if c == 0: it.setTextAlignment(Qt.AlignCenter)
                else: it.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                self.comp_table.setItem(r, c, it)

        comp_lay.addWidget(self.comp_table)
        self.comp_table.cellClicked.connect(self._open_comp_inline_search)
        
        self.comp_search.setParent(self.comp_table.viewport())

    def _open_comp_inline_search(self, row, col):
        if col != 0:
            self.comp_search.hide()
            return
            
        self._current_comp_row = row
        rect = self.comp_table.visualRect(self.comp_table.model().index(row, 0))
        self.comp_search.setGeometry(rect)
        
        existing = self.comp_table.item(row, 0)
        seed = existing.text().strip() if existing else ""
        self.comp_search.setText(seed)
        self.comp_search.selectAll()
        
        self.comp_search.show()
        self.comp_search.setFocus()

    def _add_component_row(self, text, part_no=None, name=None, qty=1):
        print(f"[BUNDLE-ROW] _add_component_row called: text={text!r}  part_no={part_no!r}  name={name!r}  qty={qty}")
        if not part_no or not name:
            try:
                from database.db import get_connection
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("SELECT part_no, name FROM products WHERE part_no = ? OR name = ?", (text, text))
                row = cur.fetchone()
                conn.close()
                if row:
                    part_no, name = row
                    print(f"[BUNDLE-ROW] Resolved from DB: part_no={part_no!r}  name={name!r}")
                else:
                    print(f"[BUNDLE-ROW] Could not resolve product for text={text!r}")
            except Exception as e:
                print(f"[BUNDLE-ROW] DB lookup error: {e}")
                
        if not part_no:
            print(f"[BUNDLE-ROW] ABORTED — no part_no resolved")
            return
        
        # Check for duplicates
        for r in range(self.comp_table.rowCount()):
            it = self.comp_table.item(r, 0)
            if it and it.text() == part_no:
                print(f"[BUNDLE-ROW] DUPLICATE rejected: {part_no!r} already in row {r}")
                self.comp_search.clear()
                self.comp_search.hide()
                return

        # Determine which row to use
        r = getattr(self, "_current_comp_row", -1)
        
        # If programmatic insert (search not visible), find first empty row
        if r == -1 or not self.comp_search.isVisible():
            r = 0
            while r < self.comp_table.rowCount():
                it = self.comp_table.item(r, 0)
                if not it or not it.text().strip():
                    break
                r += 1
            if r == self.comp_table.rowCount():
                self.comp_table.insertRow(r)
                self.comp_table.setRowHeight(r, 38)
        
        # Ensure cells exist before writing — they may be None for freshly-inserted rows
        i0 = self.comp_table.item(r, 0)
        if not i0:
            i0 = QTableWidgetItem()
            i0.setTextAlignment(Qt.AlignCenter)
            i0.setFlags(i0.flags() & ~Qt.ItemIsEditable)
            self.comp_table.setItem(r, 0, i0)
        i0.setText(str(part_no))
        
        i1 = self.comp_table.item(r, 1)
        if not i1:
            i1 = QTableWidgetItem()
            i1.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            i1.setFlags(i1.flags() & ~Qt.ItemIsEditable)
            self.comp_table.setItem(r, 1, i1)
        i1.setText(str(name))
        print(f"[BUNDLE-ROW] Written to table row {r}: part_no={part_no!r}  name={name!r}  qty={qty}")
        
        qty_edit = QLineEdit(str(qty))
        qty_edit.setAlignment(Qt.AlignCenter)
        qty_edit.setStyleSheet(f"border: none; background: transparent; color: {NAVY}; font-size: 13px;")
        qty_edit.setFixedHeight(28)
        qty_edit.textChanged.connect(lambda t: self._update_bundle_totals())
        self.comp_table.setCellWidget(r, 2, qty_edit)
        
        btn_del = QPushButton()
        import qtawesome as qta
        btn_del.setIcon(qta.icon("fa5s.trash", color="#c0392b"))
        btn_del.setFixedSize(28, 28)
        btn_del.setCursor(Qt.PointingHandCursor)
        btn_del.setStyleSheet("background: transparent; border: none;")
        btn_del.clicked.connect(lambda checked=False, item_ref=i0: self._remove_comp_row(item_ref))
        
        # When pressing Enter in qty_edit, jump to next row inline search
        def on_qty_enter():
            next_r = r + 1
            if next_r < self.comp_table.rowCount():
                self.comp_table.setCurrentCell(next_r, 0)
                self._open_comp_inline_search(next_r, 0)
                
        from PySide6.QtCore import QObject, QEvent
                
        class QtyEventFilter(QObject):
            def eventFilter(self, obj, event):
                if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
                    on_qty_enter()
                    return True
                ret = super().eventFilter(obj, event)
                return bool(ret) if ret is not None else False
                
        
        qef = QtyEventFilter(qty_edit)
        qty_edit.installEventFilter(qef)
        qty_edit._filter = qef
        
        del_lay = QHBoxLayout()
        del_lay.setContentsMargins(0,0,0,0)
        del_lay.addWidget(btn_del)
        w = QWidget()
        w.setLayout(del_lay)
        self.comp_table.setCellWidget(r, 3, w)
        
        self.comp_search.clear()
        self.comp_search.hide()
        
        qty_edit.setFocus()
        qty_edit.selectAll()
        
        self._update_bundle_totals()


    def _remove_comp_row(self, item_ref):
        if not item_ref: return
        row = item_ref.row()
        if row >= 0 and row < self.comp_table.rowCount():
            self.comp_table.removeRow(row)
            self._update_bundle_totals()
            
            # Append a new empty row at the bottom to maintain the table height/grid
            r = self.comp_table.rowCount()
            self.comp_table.insertRow(r)
            self.comp_table.setRowHeight(r, 38)
            for c in range(2):
                it = QTableWidgetItem("")
                if c == 0: it.setTextAlignment(Qt.AlignCenter)
                else: it.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                self.comp_table.setItem(r, c, it)

    def _update_bundle_totals(self):
        if not (hasattr(self, 'f_is_bundle') and self.f_is_bundle.isChecked()):
            return
            
        total_price = 0.0
        total_cost = 0.0
        
        try:
            from database.db import get_connection
            conn = get_connection()
            cur = conn.cursor()
            
            for r in range(self.comp_table.rowCount()):
                part_item = self.comp_table.item(r, 0)
                if not part_item: continue
                part_no = part_item.text().strip()
                if not part_no: continue
                
                qty_widget = self.comp_table.cellWidget(r, 2)
                qty = 1.0
                if qty_widget and isinstance(qty_widget, QLineEdit):
                    try:
                        qty = float(qty_widget.text().strip() or 1.0)
                    except ValueError:
                        qty = 1.0
                        
                cur.execute("SELECT price, cost_price FROM products WHERE part_no = ?", (part_no,))
                row = cur.fetchone()
                if row:
                    p = float(row[0] or 0.0)
                    c = float(row[1] or 0.0)
                    total_price += p * qty
                    total_cost += c * qty
                    
            conn.close()
            
            if total_price > 0:
                self.f_price.setText(f"{total_price:.2f}")
            if total_cost > 0:
                self.f_cost.setText(f"{total_cost:.2f}")
                
        except Exception as e:
            print(f"Error calculating bundle totals: {e}")

    def _sync_selling_price(self, text):
        if self.pl_table.rowCount() > 0:
            item = self.pl_table.item(0, 4)
            if not item:
                item = QTableWidgetItem()
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.pl_table.setItem(0, 4, item)
            self.pl_table.blockSignals(True)
            item.setText(text)
            self.pl_table.blockSignals(False)

    def _sync_selling_uom(self, text):
        if self.pl_table.rowCount() > 0:
            uom_widget = self.pl_table.cellWidget(0, 2)
            if isinstance(uom_widget, QComboBox):
                if uom_widget.findText(text) < 0:
                    uom_widget.insertItem(0, text)
                uom_widget.setCurrentText(text)

    def _toggle_bundle_state(self):
        is_bundle = hasattr(self, 'f_is_bundle') and self.f_is_bundle.isChecked()
            
        if is_bundle:
            self.f_track_stock.setChecked(False)
            self.f_track_stock.setEnabled(False)
            self.f_is_pharmacy.setChecked(False)
            self.f_is_pharmacy.setVisible(False)
            self.f_is_butchery.setChecked(False)
            self.f_is_butchery.setVisible(False)
            self.f_stock.setText("0")
            self.f_stock.setEnabled(False)
            self.f_stock.setVisible(False)
            if hasattr(self, '_lbl_stock'): self._lbl_stock.setVisible(False)
            
            # Hide cost, price, and reorder level
            self.f_cost.setVisible(False)
            self.f_price.setVisible(False)
            self.f_reorder.setVisible(False)
            if hasattr(self, '_lbl_cost'): self._lbl_cost.setVisible(False)
            if hasattr(self, '_lbl_price'): self._lbl_price.setVisible(False)
            if hasattr(self, '_lbl_reorder'): self._lbl_reorder.setVisible(False)
        else:
            self.f_track_stock.setEnabled(True)
            self.f_is_pharmacy.setVisible(True)
            self.f_is_butchery.setVisible(True)
            self._toggle_opening_stock()
            
            # Show cost, price, and reorder level
            self.f_cost.setVisible(True)
            self.f_price.setVisible(True)
            self.f_reorder.setVisible(True)
            if hasattr(self, '_lbl_cost'): self._lbl_cost.setVisible(True)
            if hasattr(self, '_lbl_price'): self._lbl_price.setVisible(True)
            if hasattr(self, '_lbl_reorder'): self._lbl_reorder.setVisible(True)

    def _toggle_opening_stock(self):
        is_batch = self.f_is_pharmacy.isChecked()
        self.f_stock.setVisible(not is_batch)
        if hasattr(self, '_lbl_stock'):
            self._lbl_stock.setVisible(not is_batch)
        if is_batch:
            self.f_stock.setText("0")



    def _add_price_row_to_table(self, item_code, price_list, uom, price, qty=1.0):
        row = self.pl_table.rowCount()
        self.pl_table.insertRow(row)
        self.pl_table.setRowHeight(row, 38)

        _cb_style = f"""
            QComboBox {{
                background:{WHITE}; color:{DARK_TEXT};
                border:none; padding:4px 8px;
                font-size:12px; font-weight:500;
            }}
            QComboBox::drop-down {{ border:none; width:22px; }}
            QComboBox QAbstractItemView {{
                background:{WHITE}; border:1px solid {BORDER};
                selection-background-color:{ACCENT}; selection-color:{WHITE};
                font-size:12px; outline:none;
            }}
        """

        # ── Col 0: Item Code - read-only cell, double-click opens input dialog ──
        i0 = QTableWidgetItem(str(item_code).strip().upper())
        i0.setTextAlignment(Qt.AlignCenter)
        i0.setForeground(QColor(ACCENT))
        # Mark as "click to edit" by storing a flag
        i0.setData(Qt.UserRole, "item_code_cell")
        i0.setToolTip("Double-click to change item code")
        self.pl_table.setItem(row, 0, i0)

        # ── Col 1: Wholesale Price - non-editable dropdown from DB ──
        cb_pl = QComboBox()
        cb_pl.setEditable(False)
        cb_pl.setStyleSheet(_cb_style)
        try:
            from models.price_list import get_all_price_lists
            pls = get_all_price_lists()
            if pls:
                cb_pl.addItems([p["name"] for p in pls])
            else:
                cb_pl.addItems(["Standard Selling", "Standard Buying"])
        except:
            cb_pl.addItems(["Standard Selling", "Standard Buying"])
        idx = cb_pl.findText(price_list, Qt.MatchFixedString)
        cb_pl.setCurrentIndex(idx if idx >= 0 else 0)
        cb_pl.view().window().setAttribute(Qt.WA_TranslucentBackground, False)
        self.pl_table.setCellWidget(row, 1, cb_pl)

        # ── Col 2: UOM - editable QLineEdit with QCompleter ──
        target = uom if uom else "Unit"
        le_uom = QLineEdit(target)
        le_uom.setStyleSheet(f"background:{WHITE}; color:{DARK_TEXT}; border:none; padding:4px 8px; font-size:12px; font-weight:500;")
        
        uom_names = []
        try:
            from models.uom import get_all_uoms
            uom_records = get_all_uoms()
            uom_names = [u["name"] for u in uom_records] if uom_records else []
        except Exception:
            pass
        if not uom_names:
            uom_names = ["Unit", "Kg", "Litre", "Meter", "Box", "Pack", "Gram", "Plate", "Dozen"]
            
        from PySide6.QtWidgets import QCompleter
        completer = QCompleter(uom_names)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        
        comp_view = completer.popup()
        comp_view.setStyleSheet(f"QListView {{ background:{WHITE}; border:1px solid {BORDER}; selection-background-color:{ACCENT}; selection-color:{WHITE}; font-size:12px; outline:none; }}")
        comp_view.window().setAttribute(Qt.WA_TranslucentBackground, False)
        
        le_uom.setCompleter(completer)
        self.pl_table.setCellWidget(row, 2, le_uom)

        # ── Col 3: Qty - editable cell ──
        i3 = QTableWidgetItem(f"{float(qty):.2f}")
        i3.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.pl_table.setItem(row, 3, i3)

        # ── Col 4: Price - editable cell ──
        i4 = QTableWidgetItem(f"{float(price):.2f}")
        i4.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.pl_table.setItem(row, 4, i4)

    def _setup_pl_table_edit(self):
        """Connect double-click on item code cell to show an input dialog."""
        self.pl_table.cellDoubleClicked.connect(self._on_pl_cell_double_clicked)
        self.pl_table.cellChanged.connect(self._on_pl_cell_changed)

    def _on_pl_cell_changed(self, row, col):
        if col == 4 and row == 0:
            item = self.pl_table.item(row, col)
            if item:
                self.f_price.blockSignals(True)
                self.f_price.setText(item.text().strip())
                self.f_price.blockSignals(False)

    def _on_pl_cell_double_clicked(self, row, col):
        if col == 0:
            # Item Code - show a styled input dialog
            current = self.pl_table.item(row, 0).text() if self.pl_table.item(row, 0) else ""
            dlg = _ItemCodeInputDialog(current, self)
            if dlg.exec() == QDialog.Accepted and dlg.value:
                it = self.pl_table.item(row, 0)
                if it:
                    it.setText(dlg.value.strip().upper())

    def _add_empty_price_row(self):
        self._add_price_row_to_table(self.f_part.text(), "Standard Selling", "Unit", 0.00)

    def _sync_item_code_column(self, text: str):
        """Keep the Item Code column in sync when the user types in the Part No field."""
        for r in range(self.pl_table.rowCount()):
            item = self.pl_table.item(r, 0)
            if item is not None:
                item.setText(text.strip().upper())

    def _remove_price_row_clicked(self):
        button = self.sender()
        if button:
            index = self.pl_table.indexAt(button.pos())
            if index.isValid():
                self.pl_table.removeRow(index.row())

    def _load_product(self):
        self.f_part.setText(self.product['part_no'])
        self.f_name.setText(self.product['name'])
        self.f_hs_code.setText(self.product.get('hs_code') or "")
        self.f_cost.setText(f"{self.product.get('cost_price', 0.0):.2f}")
        self.f_stock.setText(str(self.product['stock']))
        self.f_cat.setText(self.product['category'])
        self.f_reorder.setText(str(self.product.get('reorder_level', 0.0)))
        
        for i in range(1, 7):
            self.f_orders[i-1].setChecked(bool(self.product.get(f'order_{i}', False)))
            
        self.f_is_pharmacy.setChecked(bool(self.product.get('is_pharmacy_product', False)))
        self.f_is_butchery.setChecked(bool(self.product.get('is_butchery_product', False)))
        self.f_track_stock.setChecked(bool(self.product.get('track_stock', True)))
        if 'is_product_bundle' in self.product:
            self.f_is_bundle.setChecked(bool(self.product.get('is_product_bundle', False)))
        
        self._toggle_opening_stock()
        self._toggle_bundle_state()
        
        tax_type = self.product.get('tax_type')
        if tax_type:
            idx = self.f_tax_rule.findData(tax_type)
            if idx >= 0:
                self.f_tax_rule.setCurrentIndex(idx)
            

        # Load pricelists into table
        try:
            from database.db import get_connection, fetchall_dicts
            conn = get_connection(); cur = conn.cursor()
            
            # Load components if bundle
            print(f"[BUNDLE-LOAD] Product is_product_bundle: {self.product.get('is_product_bundle')}")
            if self.product.get('is_product_bundle'):
                bundle_lines = self.product.get('bundle_lines')
                print(f"[BUNDLE-LOAD] bundle_lines JSON string: {bundle_lines!r}")
                if bundle_lines:
                    import json
                    try:
                        comps = json.loads(bundle_lines)
                        print(f"[BUNDLE-LOAD] Parsed JSON list: {comps}")
                        for comp in comps:
                            self._add_component_row(
                                comp.get('item_code', ''), 
                                comp.get('item_code', ''), 
                                comp.get('item_name', ''), 
                                float(comp.get('quantity', 1.0))
                            )
                    except Exception as e:
                        print(f"Failed to load bundle_lines: {e}")
                    
            cur.execute("SELECT price_list, uom, price, qty FROM item_prices WHERE part_no = ?", (self.product['part_no'],))
            prices = fetchall_dicts(cur)
            conn.close()
            
            self.pl_table.setRowCount(0)
            for pr in prices:
                self._add_price_row_to_table(self.product['part_no'], pr['price_list'], pr.get('uom', ''), pr.get('price', 0.0), pr.get('qty', 1.0))
                
            if prices:
                self.f_price.blockSignals(True)
                self.f_price.setText(f"{prices[0].get('price', 0.0):.2f}")
                self.f_price.blockSignals(False)
                
                self.f_uom.blockSignals(True)
                uom_val = prices[0].get('uom', '')
                if uom_val:
                    if self.f_uom.findText(uom_val) < 0:
                        self.f_uom.insertItem(0, uom_val)
                    self.f_uom.setCurrentText(uom_val)
                self.f_uom.blockSignals(False)
        except Exception as e:
            print("Error loading pricelists tab:", e)

    def eventFilter(self, obj, event):
        """Auto-popup completers on focus or click."""
        if obj in (self.f_cat,):
            if event.type() == QEvent.FocusIn:
                if event.reason() == Qt.TabFocusReason:
                    QTimer.singleShot(100, lambda: self._show_completer(obj))
            elif event.type() == QEvent.MouseButtonRelease:
                self._show_completer(obj)
        ret = super().eventFilter(obj, event)
        return bool(ret) if ret is not None else False

    def _on_completer_activated(self, widget):
        """Explicitly hide and move focus after selection."""
        if widget.completer():
            widget.completer().popup().hide()
        # Move focus to next logical widget to prevent re-triggering
        self.focusNextChild()

    def _show_completer(self, widget):
        if widget.completer() and not widget.completer().popup().isVisible():
            widget.completer().complete()

    def _style_completer(self, completer):
        """Apply clean white theme to the popup list."""
        popup = completer.popup()
        popup.setStyleSheet(f"""
            QListView {{
                background: {WHITE}; border: 2px solid {ACCENT};
                border-radius: 0px; font-size: 13px; color: {DARK_TEXT}; outline: none;
            }}
            QListView::item           {{ padding: 6px 10px; min-height: 28px; color: {DARK_TEXT}; }}
            QListView::item:selected  {{ background-color: {ACCENT}; color: {WHITE}; }}
            QListView::item:selected:!active {{ background-color: {ACCENT}; color: {WHITE}; }}
            QListView::item:hover     {{ background-color: {LIGHT}; color: {NAVY}; }}
        """)

    def _on_delete(self):
        reply = QMessageBox.question(
            self, "Delete Product",
            f"Are you sure you want to delete '{self.product['name']}'?\n\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                from models.product import delete_product
                if delete_product(self.product['id']):
                    QMessageBox.information(self, "Deleted", "Product deleted successfully.")
                    
                    # Refresh parent table if available
                    p = self.parent()
                    while p:
                        if hasattr(p, '_load_stock_data'):
                            p._load_stock_data()
                            break
                        if hasattr(p, '_load_data'):
                            p._load_data()
                            break
                        p = p.parent()
                        
                    self.reject()
                else:
                    QMessageBox.warning(self, "Failed", "Could not delete product. It may be in use.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete product:\n{e}")

    def _on_save(self):
        if not self.f_part.text() or not self.f_name.text():
            QMessageBox.warning(self, "Error", "Item Code and Item Name are required.")
            return
        # Uniqueness check
        part_no = self.f_part.text().strip().upper()
        existing = get_product_by_part_no(part_no)
        if existing:
            # If new product, or modifying to a different existing part_no
            if not self.product or existing['id'] != self.product['id']:
                QMessageBox.warning(self, "Duplicate Item Code", 
                                  f"A product with Item Code '{part_no}' already exists.\n"
                                  "Please use a unique Item Code.")
                return

        # Name Uniqueness check
        product_name = self.f_name.text().strip()
        from database.db import get_connection
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM products WHERE LOWER(name) = ?", (product_name.lower(),))
        existing_name = cur.fetchone()
        conn.close()

        if existing_name:
            if not self.product or existing_name[0] != self.product['id']:
                QMessageBox.warning(self, "Duplicate Item Name", 
                                  f"A product with Item Name '{product_name}' already exists.\n"
                                  "Please use a unique Item Name.")
                return

        tax_name = self.f_tax_rule.currentData()
        if tax_name == 0.0: # No Tax
            tax_name = ""
            
        try:
            from models.tax_rule import TaxRuleRepository
            rules = TaxRuleRepository.get_all()
            rate = 0.0
            for r in rules:
                if r.tax_name == tax_name:
                    rate = r.tax_rate
                    break
        except Exception:
            rate = 0.0
            
        self.prices_to_save = []
        seen_pl_uom = set()
        for r in range(self.pl_table.rowCount()):
            it_code = self.pl_table.item(r, 0).text().strip() if self.pl_table.item(r, 0) else ""
            if not it_code:
                it_code = self.f_part.text().strip().upper()
                
            pl_widget = self.pl_table.cellWidget(r, 1)
            plist = pl_widget.currentText().strip() if isinstance(pl_widget, QComboBox) else (self.pl_table.item(r, 1).text().strip() if self.pl_table.item(r, 1) else "Standard Selling")
            
            uom_widget = self.pl_table.cellWidget(r, 2)
            if isinstance(uom_widget, QLineEdit):
                uom_val = uom_widget.text().strip()
            elif isinstance(uom_widget, QComboBox):
                uom_val = uom_widget.currentText().strip()
            else:
                uom_val = self.pl_table.item(r, 2).text().strip() if self.pl_table.item(r, 2) else "Unit"
            
            key = (plist.lower(), uom_val.lower())
            if key in seen_pl_uom:
                QMessageBox.warning(self, "Duplicate Pricelist / UOM", f"You cannot have multiple rows with the same Price List ('{plist}') and UOM ('{uom_val}').")
                return
            seen_pl_uom.add(key)
            
            try:
                qty_val = float(self.pl_table.item(r, 3).text().strip() or 1.0) if self.pl_table.item(r, 3) else 1.0
            except ValueError:
                qty_val = 1.0
                
            try:
                price_val = float(self.pl_table.item(r, 4).text().strip() or 0.0) if self.pl_table.item(r, 4) else 0.0
            except ValueError:
                price_val = 0.0
                
            self.prices_to_save.append({
                "item_code": it_code,
                "price_list": plist,
                "uom": uom_val,
                "qty": qty_val,
                "price": price_val
            })

        first_uom = self.prices_to_save[0]["uom"] if self.prices_to_save else "Unit"
        first_pl = self.prices_to_save[0]["price_list"] if self.prices_to_save else "Standard Selling"
        first_price = self.prices_to_save[0]["price"] if self.prices_to_save else 0.0

        try:
            cost_price_val = float(self.f_cost.text().strip() or 0.0)
            stock_val = float(self.f_stock.text().strip() or 0.0)
            reorder_val = float(self.f_reorder.text().strip() or 0.0)
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Cost, Stock, and Reorder Level must be valid numeric values.")
            return

        self.result_data = {
            "part_no": self.f_part.text().strip().upper(),
            "name": self.f_name.text().strip(),
            "description": "",
            "cost_price": cost_price_val,
            "price": first_price,
            "stock": stock_val,
            "category": self.f_cat.text().strip(),
            "hs_code": self.f_hs_code.text().strip() if hasattr(self, 'f_hs_code') else "",
            "uom": first_uom,
            "conversion_factor": 1.0,
            "is_pharmacy_product": self.f_is_pharmacy.isChecked() if hasattr(self, 'f_is_pharmacy') else False,
            "track_stock": self.f_track_stock.isChecked() if hasattr(self, 'f_track_stock') else True,
            "is_product_bundle": self.f_is_bundle.isChecked() if hasattr(self, 'f_is_bundle') else False,
            "is_butchery_product": self.f_is_butchery.isChecked() if hasattr(self, 'f_is_butchery') else False,
            "price_list": first_pl,
            "tax_type": tax_name,
            "tax_rate": rate,
            "reorder_level": reorder_val,
        }
        for i in range(1, 7):
            self.result_data[f"order_{i}"] = self.f_orders[i-1].isChecked()
            
        # Collect Bundle Components — always set even if empty (clears stale data)
        is_bundle_checked = self.f_is_bundle.isChecked() if hasattr(self, 'f_is_bundle') else False
        print(f"[BUNDLE] is_product_bundle checkbox = {is_bundle_checked}")

        if is_bundle_checked:
            components = []
            total_rows = self.comp_table.rowCount()
            print(f"[BUNDLE] comp_table has {total_rows} rows")

            for r in range(total_rows):
                part_item = self.comp_table.item(r, 0)
                name_item = self.comp_table.item(r, 1)
                qty_widget = self.comp_table.cellWidget(r, 2)

                part_text = part_item.text().strip() if part_item else ""
                name_text = name_item.text().strip() if name_item else ""
                qty_text  = qty_widget.text().strip() if (qty_widget and isinstance(qty_widget, QLineEdit)) else "N/A"

                print(f"[BUNDLE]   row {r}: part_item={part_item!r}  part_text={part_text!r}  "
                      f"name_text={name_text!r}  qty_widget={qty_widget!r}  qty_text={qty_text!r}")

                if not part_text:
                    print(f"[BUNDLE]   row {r}: SKIPPED (empty part_text)")
                    continue

                qty = 1.0
                if qty_widget and isinstance(qty_widget, QLineEdit):
                    try:
                        qty = float(qty_text or 1.0)
                    except ValueError:
                        qty = 1.0
                name_val = name_text if name_text else part_text
                components.append({
                    "item_code": part_text,
                    "item_name": name_val,
                    "quantity": qty
                })
                print(f"[BUNDLE]   row {r}: ADDED component {components[-1]}")

            print(f"[BUNDLE] Final components list ({len(components)} items): {components}")
            # Always write to result_data — allows clearing stale bundle_lines
            self.result_data['bundle_components'] = components

        self.accept()


# =============================================================================
# MAIN STOCK FILE DIALOG
# =============================================================================
class StockFileDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Stock File")
        self.setMinimumSize(1000, 650)
        self.setWindowFlags(Qt.Window | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)
        self.setModal(True)
        self._all_products = []
        
        self._build_ui()
        self._load_data()
        
        self.showMaximized()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)

        # Header with Buttons
        hdr_widget = QWidget()
        hdr_widget.setFixedHeight(80)
        hdr_widget.setStyleSheet(f"background: {NAVY}; border-top-left-radius: 12px; border-top-right-radius: 12px;")
        hdr_lay = QHBoxLayout(hdr_widget)
        hdr_lay.setContentsMargins(20, 0, 20, 0)

        v_title = QVBoxLayout(); v_title.setSpacing(2); v_title.setAlignment(Qt.AlignVCenter)
        title_lbl = QLabel("STOCK ENTRY")
        title_lbl.setStyleSheet(f"color:{WHITE}; font-size:20px; font-weight:bold; background:transparent;")
        sub_lbl = QLabel("Manage products and inventory levels")
        sub_lbl.setStyleSheet(f"color:{MUTED}; font-size:11px; background:transparent;")
        v_title.addWidget(title_lbl); v_title.addWidget(sub_lbl)
        hdr_lay.addLayout(v_title)

        hdr_lay.addStretch()

        # Action Buttons on Top
        def _top_btn(text, icon, bg, hov):
            b = QPushButton(f"  {text}")
            b.setIcon(qta.icon(icon, color="white"))
            b.setFixedSize(110, 42)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"""
                QPushButton {{
                    background: {bg}; color: white; border-radius: 8px; font-weight: bold; font-size: 12px;
                }}
                QPushButton:hover {{ background: {hov}; }}
            """)
            return b

        self._new_btn = _top_btn("New", "fa5s.plus", ACCENT, ACCENT_H)
        self._modify_btn = _top_btn("Edit", "fa5s.edit", SUCCESS, SUCCESS_H)
        self._prices_btn = _top_btn("Prices", "fa5s.tag", ACCENT, ACCENT_H)
        self._select_btn = _top_btn("Select", "fa5s.check-square", NAVY_2, NAVY_3)
        self._delete_btn = _top_btn("Delete", "fa5s.trash", DANGER, DANGER_H)
        self._close_btn = _top_btn("Close", "fa5s.times", MUTED, "#6a8aaa")

        self._new_btn.clicked.connect(self._on_new)
        self._modify_btn.clicked.connect(self._on_modify)
        self._prices_btn.clicked.connect(self._on_prices)
        self._select_btn.clicked.connect(self._toggle_select_mode)
        self._delete_btn.clicked.connect(self._on_delete)
        self._close_btn.clicked.connect(self.reject)

        hdr_lay.addWidget(self._new_btn)
        hdr_lay.addWidget(self._modify_btn)
        hdr_lay.addWidget(self._prices_btn)
        hdr_lay.addWidget(self._select_btn)
        hdr_lay.addWidget(self._delete_btn)

        try:
            from settings.pharmacy_settings import get_pharmacy_mode
            if get_pharmacy_mode():
                self._dosages_btn = _top_btn("Dosages", "fa5s.prescription-bottle-alt", NAVY_2, NAVY_3)
                self._dosages_btn.clicked.connect(self._on_dosages)
                hdr_lay.addWidget(self._dosages_btn)
        except Exception:
            pass

        hdr_lay.addSpacing(10)
        hdr_lay.addWidget(self._close_btn)

        root.addWidget(hdr_widget)

        # Search Bar
        # Search and Filter
        filter_lay = QHBoxLayout()
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search by Part No or Name...")
        
        self.filter_cat = QComboBox()
        self.filter_cat.addItem("All Categories", "all")
        self.filter_cat.setFixedHeight(34)
        self.filter_cat.addItems(get_categories())

        self.filter_plist = QComboBox()
        self.filter_plist.setFixedHeight(34)
        try:
            from models.price_list import get_all_price_lists
            pls = get_all_price_lists()
            self.filter_plist.addItem("Default (Standard)", "default")
            for p in pls:
                self.filter_plist.addItem(p["name"], p["name"])
        except:
            self.filter_plist.addItem("Standard Selling", "Standard Selling")

        filter_lay.addWidget(QLabel("Search:"))
        filter_lay.addWidget(self._search_input, 1)
        filter_lay.addWidget(QLabel("Category:"))
        filter_lay.addWidget(self.filter_cat)
        filter_lay.addWidget(QLabel("Wholesale Price:"))
        filter_lay.addWidget(self.filter_plist)
        filter_lay.addStretch()

        self._search_input.textChanged.connect(self._load_data)
        self.filter_cat.currentIndexChanged.connect(self._load_data)
        self.filter_plist.currentIndexChanged.connect(self._load_data)

        root.addLayout(filter_lay)

        # Table
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "", "Part No.", "Product Name", "UOM", "Stock", "Price", "Wholesale Price"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 0) # Hidden by default
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.doubleClicked.connect(self._on_modify)
        self.table.selectionModel().selectionChanged.connect(self._on_selection)
        root.addWidget(self.table)
        
        self._selection_mode = False

    def _toggle_select_mode(self):
        self._selection_mode = not self._selection_mode
        if self._selection_mode:
            self.table.setColumnWidth(0, 40)
            self._select_btn.setText("  Cancel Select")
            self._delete_btn.setText("  Delete Selected")
            # Uncheck all initially
            for r in range(self.table.rowCount()):
                cb = self.table.cellWidget(r, 0)
                if cb: cb.setChecked(False)
        else:
            self.table.setColumnWidth(0, 0)
            self._select_btn.setText("  Select")
            self._delete_btn.setText("  Delete")

        # No bottom button row needed

    def _load_data(self):
        query = self._search_input.text().strip().lower()
        cat = self.filter_cat.currentData()
        plist = self.filter_plist.currentData()
        
        try:
            from database.db import get_connection, fetchall_dicts
            conn = get_connection(); cur = conn.cursor()
            
            # Base query
            sql = """
                SELECT p.id, p.part_no, p.name, p.uom, p.stock, p.category, p.price,
                       p.conversion_factor, COALESCE(p.is_pharmacy_product, 0) as is_pharmacy_product,
                       p.is_product_bundle, p.bundle_lines,
                       COALESCE(ip.price, p.price) as display_price,
                       ? as active_price_list
                FROM products p
                LEFT JOIN item_prices ip ON p.part_no = ip.part_no AND ip.price_list = ?
                WHERE p.active = 1
            """
            params = [plist, plist]
            
            if query:
                sql += " AND (p.part_no LIKE ? OR p.name LIKE ?)"
                params.extend([f"%{query}%", f"%{query}%"])
            
            if cat and cat != "all":
                sql += " AND p.category = ?"
                params.append(cat)
                
            sql += " ORDER BY p.id DESC"
            
            cur.execute(sql, params)
            rows = fetchall_dicts(cur)
            conn.close()
            
            self._all_products = rows
            self._render_table(rows)
                
        except Exception as e:
            print(f"Error loading stock data: {e}")
            self.table.setRowCount(0)

    def _do_search(self):
        query = self._search_input.text().strip().lower()
        if not query:
            self._load_data()
            return
        filtered = [p for p in self._all_products if query in p['name'].lower() or query in p['part_no'].lower()]
        self._render_table(filtered)

    def _render_table(self, products):
        self.table.setRowCount(len(products))
        for r, p in enumerate(products):
            cb = QCheckBox()
            cb.setStyleSheet("margin-left: 10px;")
            self.table.setCellWidget(r, 0, cb)
            
            self.table.setItem(r, 1, QTableWidgetItem(p['part_no']))
            self.table.setItem(r, 2, QTableWidgetItem(p['name']))
            self.table.setItem(r, 3, QTableWidgetItem(p.get('uom', 'Unit')))
            self.table.setItem(r, 4, QTableWidgetItem(str(p['stock'])))
            
            price_item = QTableWidgetItem(f"{float(p.get('display_price', p['price'])):.2f}")
            price_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(r, 5, price_item)
            
            pl_label = "Default" if getattr(self, 'filter_plist', None) and self.filter_plist.currentData() == "default" else (p.get('active_price_list') or "Standard Selling")
            self.table.setItem(r, 6, QTableWidgetItem(pl_label))
            
            self.table.item(r, 1).setData(Qt.UserRole, p)


    def _apply_category_filter(self, cat):
        if cat == "All":
            self._render_table(self._all_products)
        else:
            filtered = [p for p in self._all_products if p['category'] == cat]
            self._render_table(filtered)

    def _on_selection(self):
        has_sel = len(self.table.selectionModel().selectedRows()) > 0
        self._modify_btn.setEnabled(has_sel)
        self._prices_btn.setEnabled(has_sel)
        self._delete_btn.setEnabled(has_sel)

    def _get_selected(self):
        rows = self.table.selectionModel().selectedRows()
        return self.table.item(rows[0].row(), 1).data(Qt.UserRole) if rows else None

    def _show_blur_overlay(self):
        from PySide6.QtWidgets import QLabel, QWidget, QGraphicsBlurEffect
        main_win = self.window()
        
        self._blur_container = QWidget(main_win)
        self._blur_container.resize(main_win.size())
        
        # Grab static background
        self._bg_label = QLabel(self._blur_container)
        self._bg_label.setPixmap(main_win.grab())
        self._bg_label.resize(main_win.size())
        
        # Apply blur to background
        self._blur_effect = QGraphicsBlurEffect()
        self._blur_effect.setBlurRadius(20)
        self._bg_label.setGraphicsEffect(self._blur_effect)
        
        # Add dark tint
        self._tint_overlay = QWidget(self._blur_container)
        self._tint_overlay.setStyleSheet("background-color: rgba(0, 0, 0, 100);")
        self._tint_overlay.resize(main_win.size())
        
        self._blur_container.show()

    def _hide_blur_overlay(self):
        if hasattr(self, '_blur_container') and self._blur_container:
            self._blur_container.hide()
            self._blur_container.deleteLater()
            self._blur_container = None

    def _on_new(self):
        self._show_blur_overlay()
        dlg = StockEditDialog(self)
        if dlg.exec() == QDialog.Accepted:
            try:
                from models.product import create_product, upsert_item_price
                p = create_product(**dlg.result_data)
                
                # Main price (from Detail tab)
                upsert_item_price(
                    p['part_no'], 
                    dlg.result_data.get('price_list', 'Standard Selling'),
                    p.get('uom', 'Unit'),
                    dlg.result_data['price']
                )
                
                # Pricelist tab rows
                for row in getattr(dlg, 'prices_to_save', []):
                    part = row.get('item_code') or p['part_no']
                    uom_val = row.get('uom', 'Unit')
                    
                    # Ensure UOM exists in database
                    try:
                        from database.db import get_connection
                        conn = get_connection()
                        cur = conn.cursor()
                        cur.execute("IF NOT EXISTS (SELECT 1 FROM uoms WHERE name = ?) INSERT INTO uoms (name) VALUES (?)", (uom_val, uom_val))
                        conn.commit()
                        conn.close()
                    except Exception:
                        pass
                        
                    upsert_item_price(
                        part,
                        row.get('price_list', 'Standard Selling'),
                        uom_val,
                        row.get('price', 0.0),
                        "Selling",
                        row.get('qty', 1.0)
                    )
                
                # Bundle Components — always write bundle_lines if it is a bundle
                print(f"[BUNDLE-SAVE] is_product_bundle = {dlg.result_data.get('is_product_bundle')}")
                print(f"[BUNDLE-SAVE] bundle_components in result_data = {'bundle_components' in dlg.result_data}")
                print(f"[BUNDLE-SAVE] bundle_components = {dlg.result_data.get('bundle_components')}")
                if dlg.result_data.get('is_product_bundle'):
                    try:
                        import json
                        from database.db import get_connection
                        components_to_save = dlg.result_data.get('bundle_components', [])
                        lines_json = json.dumps(components_to_save)
                        print(f"[BUNDLE-SAVE] Writing bundle_lines JSON: {lines_json}")
                        print(f"[BUNDLE-SAVE] For part_no: {p['part_no']}")
                        conn = get_connection()
                        cur = conn.cursor()
                        cur.execute("UPDATE products SET bundle_lines = ?, sync_status = 'pending' WHERE part_no = ?", (lines_json, p['part_no']))
                        affected = cur.rowcount
                        conn.commit()
                        conn.close()
                        print(f"[BUNDLE-SAVE] DB UPDATE done. Rows affected: {affected}")
                    except Exception as e:
                        print(f"[BUNDLE-SAVE] ERROR writing bundle_lines: {e}")


                self._load_data()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not create product:\n{str(e)}")
        self._hide_blur_overlay()

    def _on_modify(self):
        p = self._get_selected()
        if not p: return
        self._show_blur_overlay()
        dlg = StockEditDialog(self, product=p)
        if dlg.exec() == QDialog.Accepted:
            try:
                from models.product import update_product, upsert_item_price
                updated_p = update_product(p['id'], **dlg.result_data)
                
                # Main price (from Detail tab)
                upsert_item_price(
                    updated_p['part_no'], 
                    dlg.result_data.get('price_list', 'Standard Selling'),
                    updated_p.get('uom', 'Unit'),
                    dlg.result_data['price']
                )
                
                # Pricelist tab rows
                for row in getattr(dlg, 'prices_to_save', []):
                    part = row.get('item_code') or updated_p['part_no']
                    uom_val = row.get('uom', 'Unit')
                    
                    # Ensure UOM exists in database
                    try:
                        from database.db import get_connection
                        conn = get_connection()
                        cur = conn.cursor()
                        cur.execute("IF NOT EXISTS (SELECT 1 FROM uoms WHERE name = ?) INSERT INTO uoms (name) VALUES (?)", (uom_val, uom_val))
                        conn.commit()
                        conn.close()
                    except Exception:
                        pass
                        
                    upsert_item_price(
                        part,
                        row.get('price_list', 'Standard Selling'),
                        uom_val,
                        row.get('price', 0.0),
                        "Selling",
                        row.get('qty', 1.0)
                    )
                
                # Bundle Components — always write bundle_lines if it is a bundle
                print(f"[BUNDLE-SAVE-MOD] is_product_bundle = {dlg.result_data.get('is_product_bundle')}")
                if dlg.result_data.get('is_product_bundle'):
                    try:
                        import json
                        from database.db import get_connection
                        comps_to_save = dlg.result_data.get('bundle_components', [])
                        lines_json = json.dumps(comps_to_save)
                        print(f"[BUNDLE-SAVE-MOD] Writing JSON: {lines_json} for part_no {updated_p['part_no']}")
                        conn = get_connection()
                        cur = conn.cursor()
                        cur.execute("UPDATE products SET bundle_lines = ?, sync_status = 'pending' WHERE part_no = ?", (lines_json, updated_p['part_no']))
                        print(f"[BUNDLE-SAVE-MOD] Rows affected: {cur.rowcount}")
                        conn.commit()
                        conn.close()
                    except Exception as e:
                        print(f"[BUNDLE-SAVE-MOD] Error updating product bundle: {e}")

                self._load_data()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not update product:\n{str(e)}")
        self._hide_blur_overlay()

    def _on_prices(self):
        p = self._get_selected()
        if not p: return
        from views.dialogs.product_price_dialog import ProductPriceDialog
        dlg = ProductPriceDialog(self, product=p)
        dlg.exec()

    def _on_delete(self):
        if self._selection_mode:
            to_delete = []
            for r in range(self.table.rowCount()):
                cb = self.table.cellWidget(r, 0)
                if cb and cb.isChecked():
                    p = self.table.item(r, 1).data(Qt.UserRole)
                    if p: to_delete.append(p)
            if not to_delete: return
            ans = QMessageBox.question(self, "Delete Multiple", f"Are you sure you want to delete {len(to_delete)} products?", QMessageBox.Yes | QMessageBox.No)
            if ans == QMessageBox.Yes:
                try:
                    from database.db import get_connection
                    conn = get_connection()
                    cur = conn.cursor()
                    for p in to_delete:
                        cur.execute("UPDATE products SET active = 0 WHERE id = ?", (p['id'],))
                    conn.commit()
                    conn.close()
                    self._load_data()
                    self._toggle_select_mode() # Turn off selection mode
                except Exception as e:
                    QMessageBox.critical(self, "Deletion Failed", str(e))
        else:
            p = self._get_selected()
            if not p: return
            ans = QMessageBox.question(self, "Delete", f"Are you sure you want to delete {p['part_no']}?", QMessageBox.Yes | QMessageBox.No)
            if ans == QMessageBox.Yes:
                try:
                    from database.db import get_connection
                    conn = get_connection()
                    cur = conn.cursor()
                    cur.execute("UPDATE products SET active = 0 WHERE id = ?", (p['id'],))
                    conn.commit()
                    conn.close()
                    self._load_data()
                except Exception as e:
                    QMessageBox.critical(self, "Deletion Failed", str(e))

    def _on_dosages(self):
        try:
            from views.dialogs.pharmacy_masters_dialog import PharmacyMastersDialog
            dlg = PharmacyMastersDialog(self)
            # Switch to Dosages tab
            if hasattr(dlg, '_tabs'):
                dlg._tabs.setCurrentIndex(1)
            dlg.exec()
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Error", f"Could not open Dosages dialog:\n{e}")