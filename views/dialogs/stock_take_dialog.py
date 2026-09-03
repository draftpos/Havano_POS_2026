from PySide6.QtWidgets import QComboBox, QPushButton, QLineEdit, QTableWidgetItem, QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
import qtawesome as qta

from views.reports.modal_template import ModalTemplate
from models.product import get_all_products

class StockTakeDialog(ModalTemplate):
    def __init__(self, parent=None):
        super().__init__(
            title="STOCK TAKE", 
            subtitle="Adjust inventory levels to match physical count", 
            parent=parent
        )
        
        self._setup_tools()
        self.set_headers(["CODE", "ITEM NAME", "CATEGORY", "SYSTEM QTY", "PHYSICAL QTY", "VARIANCE"])
        from PySide6.QtWidgets import QHeaderView
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.setColumnWidth(0, 180)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setEditTriggers(self.table.DoubleClicked | self.table.SelectedClicked | self.table.AnyKeyPressed)
        self.table.itemChanged.connect(self._on_item_changed)
        
        self.btn_submit.clicked.connect(self._on_submit)
        
        self._load_data()
        
    def _setup_tools(self):
        self.combo = QComboBox()
        self.combo.addItem("Fetch all items")
        self.combo.setStyleSheet("padding: 6px; border: 1px solid #c8d8ec; border-radius: 4px; color: #333; background: white;")
        
        self.btn_fetch = QPushButton(" Fetch")
        self.btn_fetch.setIcon(qta.icon("fa5s.download", color="white"))
        self.btn_fetch.setStyleSheet("background-color: #1a5fb4; color: white; border-radius: 4px; padding: 6px 16px; font-weight: bold;")
        self.btn_fetch.clicked.connect(self._load_data)
        
        self.rem = QLineEdit()
        self.rem.setPlaceholderText("Enter global remarks here...")
        self.rem.setStyleSheet("padding: 6px; border: 1px solid #c8d8ec; border-radius: 4px; color: #333; min-width: 300px; background: white;")
        
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search in table...")
        self.search.setStyleSheet("padding: 6px; border: 1px solid #c8d8ec; border-radius: 4px; color: #333; min-width: 250px; background: white;")
        self.search.textChanged.connect(self._on_search)
        
        self.tools_layout.addWidget(self.combo)
        self.tools_layout.addWidget(self.btn_fetch)
        self.tools_layout.addWidget(self.rem)
        self.tools_layout.addStretch()
        self.tools_layout.addWidget(self.search)

    def _load_data(self, *args, **kwargs):
        try:
            self.products = get_all_products()
            self.table.blockSignals(True)
            self._render_table(self.products)
            self.table.blockSignals(False)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load stock: {e}")

    def _render_table(self, products):
        try:
            self.table.setRowCount(0)
            for p in products:
                r = self.table.rowCount()
                self.table.insertRow(r)
                
                sys_qty = float(p.get("stock", 0) or 0)
                
                items = [
                    QTableWidgetItem(str(p.get("part_no", "") or p.get("product_id", ""))),
                    QTableWidgetItem(str(p.get("name", ""))),
                    QTableWidgetItem(str(p.get("category", ""))),
                    QTableWidgetItem(f"{sys_qty:.2f}"),
                    QTableWidgetItem(""),  # Physical Qty
                    QTableWidgetItem("")   # Variance
                ]
                
                alignments = [Qt.AlignLeft, Qt.AlignLeft, Qt.AlignCenter, Qt.AlignRight, Qt.AlignRight, Qt.AlignRight]
                for c, (item, aln) in enumerate(zip(items, alignments)):
                    item.setTextAlignment(aln | Qt.AlignVCenter)
                    
                    # Store product dict in first column
                    if c == 0:
                        item.setData(Qt.UserRole, p)
                    
                    if c == 3 and sys_qty <= 0:
                        item.setForeground(QColor("#c0392b"))
                    
                    if c == 4:
                        item.setFlags(item.flags() | Qt.ItemIsEditable)
                        item.setBackground(QColor("#e8f1f8"))
                    else:
                        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                        if c == 5:  # Variance column styling
                            item.setBackground(QColor("#fcfcfc"))
                        
                    self.table.setItem(r, c, item)
                self.table.setRowHeight(r, 34)
        except Exception as e:
            QMessageBox.warning(self, "Render Error", f"Error rendering table: {e}")

    def _on_search(self, text):
        query = text.lower()
        for r in range(self.table.rowCount()):
            match = False
            for c in range(self.table.columnCount()):
                item = self.table.item(r, c)
                if item and query in item.text().lower():
                    match = True
                    break
            self.table.setRowHidden(r, not match)

    def _on_item_changed(self, item):
        if item.column() == 5:  # Physical Qty changed
            r = item.row()
            try:
                sys_item = self.table.item(r, 4)
                var_item = self.table.item(r, 6)
                if not sys_item or not var_item: return
                
                sys_qty = float(sys_item.text() or 0)
                phys_text = item.text().strip()
                
                if phys_text:
                    phys_qty = float(phys_text)
                    variance = phys_qty - sys_qty
                    var_item.setText(f"{variance:+.2f}")
                    if variance < 0:
                        var_item.setForeground(QColor("#c0392b"))  # Red
                    elif variance > 0:
                        var_item.setForeground(QColor("#27ae60"))  # Green
                    else:
                        var_item.setForeground(QColor("#333333"))  # Black
                else:
                    var_item.setText("")
            except ValueError:
                pass

    def _on_submit(self):
        # TODO: Implement stock take submission logic.
        pass
