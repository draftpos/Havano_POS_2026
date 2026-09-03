# =============================================================================
# views/dialogs/uom_dialog.py
# =============================================================================

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QMessageBox,
    QDoubleSpinBox, QComboBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor

# Import colors
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


def navy_btn(text, height=36, font_size=12, width=None, color=None, hover=None):
    bg  = color or NAVY
    hov = hover or NAVY_2
    btn = QPushButton(text)
    btn.setFixedHeight(height)
    if width:
        btn.setFixedWidth(width)
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


def hr():
    from PySide6.QtWidgets import QFrame
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet(f"background-color: {BORDER}; border: none;")
    line.setFixedHeight(1)
    return line


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


class UOMDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Unit of Measure Management")
        self.setMinimumSize(700, 500)
        self.setStyleSheet(f"QDialog {{ background-color:{WHITE}; }}")
        self._build()
        self._reload()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.setContentsMargins(20, 16, 20, 16)

        # Header
        hdr = QWidget()
        hdr.setFixedHeight(44)
        hdr.setStyleSheet(f"background-color:{NAVY}; border-radius:5px;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(16, 0, 16, 0)
        hl.addWidget(QLabel("Unit of Measure Management",
                    styleSheet=f"font-size:15px;font-weight:bold;color:{WHITE};background:transparent;"))
        lay.addWidget(hdr)

        # UOM Table
        self._tbl = QTableWidget(0, 4)
        self._tbl.setHorizontalHeaderLabels(["UOM Name", "Abbreviation", "Category", "Conversion Factor"])
        hh = self._tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.Fixed)
        hh.setSectionResizeMode(2, QHeaderView.Fixed)
        hh.setSectionResizeMode(3, QHeaderView.Fixed)
        self._tbl.setColumnWidth(1, 120)
        self._tbl.setColumnWidth(2, 120)
        self._tbl.setColumnWidth(3, 130)

        self._tbl.verticalHeader().setVisible(False)
        self._tbl.setAlternatingRowColors(True)
        self._tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tbl.setStyleSheet(_settings_table_style())
        lay.addWidget(self._tbl, 1)
        lay.addWidget(hr())

        # Form for adding/editing
        form = QGridLayout()
        form.setSpacing(8)

        # Labels
        form.addWidget(QLabel("UOM Name *"), 0, 0)
        form.addWidget(QLabel("Abbreviation *"), 0, 1)
        form.addWidget(QLabel("Category"), 1, 0)
        form.addWidget(QLabel("Conversion Factor *"), 1, 1)

        # Inputs
        self._f_name = QLineEdit()
        self._f_name.setPlaceholderText("e.g., Kilogram")
        self._f_name.setFixedHeight(32)
        form.addWidget(self._f_name, 0, 2)

        self._f_abbr = QLineEdit()
        self._f_abbr.setPlaceholderText("e.g., kg")
        self._f_abbr.setFixedHeight(32)
        self._f_abbr.setMaxLength(10)
        form.addWidget(self._f_abbr, 0, 3)

        self._f_category = QComboBox()
        self._f_category.addItems(["Weight", "Volume", "Length", "Count", "Time", "Other"])
        self._f_category.setFixedHeight(32)
        form.addWidget(self._f_category, 1, 2)

        self._f_conversion = QDoubleSpinBox()
        self._f_conversion.setRange(0.001, 999999.0)
        self._f_conversion.setValue(1.0)
        self._f_conversion.setSingleStep(0.1)
        self._f_conversion.setDecimals(3)
        self._f_conversion.setFixedHeight(32)
        self._f_conversion.setSuffix(" (base unit)")
        form.addWidget(self._f_conversion, 1, 3)

        lay.addLayout(form)

        # Info label
        info = QLabel("Conversion Factor: How many of this unit equals the base unit (e.g., 1 kg = 1000 g → factor 1000)")
        info.setStyleSheet(f"color: {MUTED}; font-size: 11px; background: transparent;")
        lay.addWidget(info)

        # Button row
        br = QHBoxLayout()
        br.setSpacing(8)

        self._status = QLabel("")
        self._status.setStyleSheet(f"font-size:12px;color:{SUCCESS};background:transparent;")

        add_btn = navy_btn("Add UOM", height=34, color=SUCCESS, hover=SUCCESS_H)
        add_btn.clicked.connect(self._add)

        edit_btn = navy_btn("Edit Selected", height=34, color=NAVY, hover=NAVY_2)
        edit_btn.clicked.connect(self._edit)

        del_btn = navy_btn("Delete", height=34, color=DANGER, hover=DANGER_H)
        del_btn.clicked.connect(self._delete)

        cls_btn = navy_btn("Close", height=34)
        cls_btn.clicked.connect(self.accept)

        br.addWidget(self._status, 1)
        br.addWidget(add_btn)
        br.addWidget(edit_btn)
        br.addWidget(del_btn)
        br.addWidget(cls_btn)
        lay.addLayout(br)

    def _reload(self):
        self._tbl.setRowCount(0)
        try:
            from models.uom import get_all_uoms
            uoms = get_all_uoms()
        except Exception:
            uoms = []

        if not uoms:
            # Demo data
            uoms = [
                {"id": 1, "name": "Kilogram", "abbreviation": "kg", "category": "Weight", "conversion": 1.0},
                {"id": 2, "name": "Gram", "abbreviation": "g", "category": "Weight", "conversion": 0.001},
                {"id": 3, "name": "Liter", "abbreviation": "L", "category": "Volume", "conversion": 1.0},
                {"id": 4, "name": "Milliliter", "abbreviation": "ml", "category": "Volume", "conversion": 0.001},
                {"id": 5, "name": "Piece", "abbreviation": "pc", "category": "Count", "conversion": 1.0},
                {"id": 6, "name": "Dozen", "abbreviation": "dz", "category": "Count", "conversion": 12.0},
            ]

        for uom in uoms:
            r = self._tbl.rowCount()
            self._tbl.insertRow(r)
            for col, (key, align) in enumerate([
                ("name", Qt.AlignLeft),
                ("abbreviation", Qt.AlignCenter),
                ("category", Qt.AlignCenter),
                ("conversion", Qt.AlignRight | Qt.AlignVCenter),
            ]):
                val = uom.get(key, "")
                if key == "conversion":
                    val = f"{val:.3f}"
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(align)
                if key == "conversion":
                    item.setForeground(QColor(ACCENT))
                item.setData(Qt.UserRole, uom)
                self._tbl.setItem(r, col, item)
            self._tbl.setRowHeight(r, 32)

    def _add(self):
        name = self._f_name.text().strip()
        abbr = self._f_abbr.text().strip()
        category = self._f_category.currentText()
        conversion = self._f_conversion.value()

        if not name or not abbr:
            self._show_status("UOM Name and Abbreviation are required.", error=True)
            return

        try:
            from models.uom import create_uom
            create_uom(name, abbr, category, conversion)
            self._clear_form()
            self._reload()
            self._show_status(f"UOM '{name}' added.")
        except Exception as e:
            self._show_status(str(e), error=True)

    def _edit(self):
        row = self._tbl.currentRow()
        if row < 0:
            self._show_status("Select a UOM to edit.", error=True)
            return

        uom = self._tbl.item(row, 0).data(Qt.UserRole)

        # Populate form
        self._f_name.setText(uom.get("name", ""))
        self._f_abbr.setText(uom.get("abbreviation", ""))
        self._f_category.setCurrentText(uom.get("category", "Other"))
        self._f_conversion.setValue(uom.get("conversion", 1.0))

        # Change add button to update
        sender = self.sender()
        if sender.text() == "Edit Selected":
            sender.setText("Update UOM")
            sender.setStyleSheet(f"""
                QPushButton {{
                    background-color: {NAVY}; color: {WHITE}; border: none;
                    border-radius: 5px; font-size: 12px; font-weight: bold; padding: 0 14px;
                }}
                QPushButton:hover {{ background-color: {NAVY_2}; }}
            """)
            sender.clicked.disconnect()
            sender.clicked.connect(lambda: self._update(uom["id"]))

    def _update(self, uom_id):
        name = self._f_name.text().strip()
        abbr = self._f_abbr.text().strip()

        if not name or not abbr:
            self._show_status("UOM Name and Abbreviation are required.", error=True)
            return

        try:
            from models.uom import update_uom
            update_uom(
                uom_id=uom_id,
                name=name,
                abbreviation=abbr,
                category=self._f_category.currentText(),
                conversion=self._f_conversion.value()
            )
            self._clear_form()
            self._reload()
            self._show_status(f"UOM '{name}' updated.")

            # Reset edit button
            self._reset_edit_button()

        except Exception as e:
            self._show_status(str(e), error=True)

    def _delete(self):
        row = self._tbl.currentRow()
        if row < 0:
            self._show_status("Select a UOM to delete.", error=True)
            return

        uom = self._tbl.item(row, 0).data(Qt.UserRole)
        if QMessageBox.question(self, "Delete", f"Delete UOM '{uom['name']}'?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return

        try:
            from models.uom import delete_uom
            delete_uom(uom["id"])
            self._reload()
            self._show_status("Deleted.")
        except Exception as e:
            self._show_status(str(e), error=True)

    def _clear_form(self):
        self._f_name.clear()
        self._f_abbr.clear()
        self._f_category.setCurrentIndex(0)
        self._f_conversion.setValue(1.0)
        self._reset_edit_button()

    def _reset_edit_button(self):
        for btn in self.findChildren(QPushButton):
            if btn.text() == "Update UOM":
                btn.setText("Edit Selected")
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {NAVY}; color: {WHITE}; border: none;
                        border-radius: 5px; font-size: 12px; font-weight: bold; padding: 0 14px;
                    }}
                    QPushButton:hover {{ background-color: {NAVY_2}; }}
                """)
                btn.clicked.disconnect()
                btn.clicked.connect(self._edit)
                break

    def _show_status(self, msg, error=False):
        color = DANGER if error else SUCCESS
        self._status.setStyleSheet(f"font-size:12px;color:{color};background:transparent;")
        self._status.setText(msg)
        QTimer.singleShot(4000, lambda: self._status.setText(""))