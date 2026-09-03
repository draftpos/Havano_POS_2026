from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QDateEdit, QPushButton, QFrame, QSizePolicy,
    QTableWidget, QHeaderView, QMenu, QLineEdit, QTableWidgetItem, QToolButton, QDialog, QComboBox
)
from PySide6.QtCore import Qt, QDate, QEvent
import qtawesome as qta

class AdvancedFilterDialog(QDialog):
    def __init__(self, headers, current_col, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Advanced Filter")
        self.setFixedSize(450, 120)
        self.setStyleSheet("background-color: white;")
        
        layout = QVBoxLayout(self)
        
        row_layout = QHBoxLayout()
        self.col_combo = QComboBox()
        self.col_combo.addItems(headers)
        self.col_combo.setCurrentIndex(current_col)
        self.col_combo.setStyleSheet("padding: 4px; border: 1px solid #c8d8ec; border-radius: 4px; color: #333;")
        
        op_label = QLabel("Equals")
        op_label.setStyleSheet("background: #f5f8fc; border: 1px solid #c8d8ec; padding: 4px 12px; border-radius: 4px; color: #333;")
        
        self.val_input = QLineEdit()
        self.val_input.setPlaceholderText("Enter value...")
        self.val_input.setStyleSheet("padding: 4px; border: 1px solid #c8d8ec; border-radius: 4px; color: #333; min-height: 20px;")
        
        row_layout.addWidget(self.col_combo)
        row_layout.addWidget(op_label)
        row_layout.addWidget(self.val_input)
        
        layout.addLayout(row_layout)
        
        btn_layout = QHBoxLayout()
        
        btn_layout.addStretch()
        
        btn_close = QPushButton("Clear Filters")
        btn_close.setStyleSheet("background-color: #f5f8fc; color: #333; border: 1px solid #c8d8ec; border-radius: 4px; padding: 6px 12px;")
        btn_close.clicked.connect(self.reject)
        
        self.btn_apply = QPushButton("Apply Filters")
        self.btn_apply.setStyleSheet("background-color: #1a5fb4; color: white; border: none; border-radius: 4px; padding: 6px 12px; font-weight: bold;")
        self.btn_apply.clicked.connect(self.accept)
        
        btn_layout.addWidget(btn_close)
        btn_layout.addWidget(self.btn_apply)
        
        layout.addLayout(btn_layout)


class ReportTemplate(QWidget):
    """
    A unified standard template for all reports and listviews in Havano POS.
    """
    def __init__(self, title="Sales Invoices", is_report=False, show_date_filter=True, parent=None, show_column_filters=True):
        super().__init__(parent)
        self.is_report = is_report
        self.show_date_filter = show_date_filter
        self.show_column_filters = show_column_filters
        clean_title = title.replace(" List", "").strip()
        self.title_text = clean_title
        self.headers = []
        self.setStyleSheet("background-color: #f5f8fc;")
        
        self.current_sort_col = 0
        self.current_sort_order = Qt.AscendingOrder
        self.sort_buttons = []
        
        self._build_template()

    def _build_template(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.top_frame = QFrame()
        self.top_frame.setStyleSheet("background-color: #ffffff; border-bottom: 1px solid #e4eaf4;")
        self.top_layout = QVBoxLayout(self.top_frame)
        self.top_layout.setContentsMargins(15, 8, 15, 6)
        self.top_layout.setSpacing(6)

        try:
            from models.company_defaults import get_defaults
            comp = get_defaults()
            c_name = comp.get('company_name') or ''
        except:
            c_name = ""
            
        display_title = f"{c_name} - {self.title_text}" if c_name else self.title_text
        self.title_label = QLabel(display_title)
        self.title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #1a5fb4; border: none; padding: 0px; margin: 0px;")
        self.top_layout.addWidget(self.title_label)

        self.filters_layout = QHBoxLayout()
        self.filters_layout.setContentsMargins(0, 0, 0, 0)
        self.filters_layout.setSpacing(8)

        date_style = "padding: 3px 6px; font-size: 11px; border: 1px solid #c8d8ec; border-radius: 4px; background: white; color: #333333;"
        calendar_style = """
            QCalendarWidget QWidget#qt_calendar_navigationbar {
                background-color: #1a5fb4;
                min-height: 36px;
            }
            QCalendarWidget QToolButton {
                color: #ffffff;
                font-weight: bold;
                font-size: 12px;
                background-color: #1a5fb4;
                border: none;
                border-radius: 4px;
                margin: 2px;
                padding: 4px 6px;
            }
            QCalendarWidget QToolButton:hover {
                background-color: #1c6dd0;
            }
            QCalendarWidget QToolButton#qt_calendar_monthbutton,
            QCalendarWidget QToolButton#qt_calendar_yearbutton {
                color: #ffffff;
                font-weight: bold;
                font-size: 12px;
                background-color: #162d52;
                border: 1px solid #3b82f6;
                border-radius: 4px;
                padding: 4px 10px;
                margin: 2px 4px;
            }
            QCalendarWidget QToolButton#qt_calendar_monthbutton:hover,
            QCalendarWidget QToolButton#qt_calendar_yearbutton:hover {
                background-color: #1c6dd0;
                color: #ffffff;
            }
            QCalendarWidget QToolButton::menu-indicator {
                image: none;
                width: 0px;
            }
            QCalendarWidget QMenu {
                background-color: #ffffff;
                color: #1a5fb4;
                font-weight: bold;
                font-size: 12px;
                border: 1px solid #c8d8ec;
                border-radius: 6px;
                padding: 4px;
            }
            QCalendarWidget QMenu::item {
                color: #1a5fb4;
                background-color: #ffffff;
                padding: 6px 18px;
            }
            QCalendarWidget QMenu::item:selected {
                background-color: #1a5fb4;
                color: #ffffff;
            }
            QCalendarWidget QSpinBox#qt_calendar_yearedit {
                color: #1a5fb4;
                font-weight: bold;
                font-size: 12px;
                background-color: #ffffff;
                border: 1.5px solid #1a5fb4;
                border-radius: 4px;
                padding: 2px 4px;
                selection-background-color: #1a5fb4;
                selection-color: #ffffff;
            }
            QCalendarWidget QAbstractItemView:enabled {
                color: #0d1f3c;
                font-size: 12px;
                background-color: #ffffff;
                selection-background-color: #1a5fb4;
                selection-color: #ffffff;
            }
            QCalendarWidget QAbstractItemView:disabled {
                color: #94a3b8;
            }
        """

        self.lbl_date_from = QLabel("Date From:", styleSheet="font-weight: bold; color: #1a5fb4; font-size: 11px;")
        self.filters_layout.addWidget(self.lbl_date_from)
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate())
        self.start_date.setDisplayFormat("dd MMM yyyy")
        self.start_date.setStyleSheet(date_style)
        self.start_date.calendarWidget().setStyleSheet(calendar_style)
        self.filters_layout.addWidget(self.start_date)

        self.lbl_date_to = QLabel("To:", styleSheet="font-weight: bold; color: #1a5fb4; font-size: 11px;")
        self.filters_layout.addWidget(self.lbl_date_to)
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setDisplayFormat("dd MMM yyyy")
        self.end_date.setStyleSheet(date_style)
        self.end_date.calendarWidget().setStyleSheet(calendar_style)
        self.filters_layout.addWidget(self.end_date)
        
        self.btn_apply = QPushButton(" Apply Filters")
        self.start_date.dateChanged.connect(self.btn_apply.click)
        self.end_date.dateChanged.connect(self.btn_apply.click)
        self.btn_apply.setIcon(qta.icon("fa5s.sync", color="#ffffff", scale_factor=0.7))
        self.btn_apply.setStyleSheet("""
            QPushButton { background-color: #1a5fb4; color: white; border: none; border-radius: 4px; padding: 4px 8px; font-weight: bold; font-size: 11px; }
            QPushButton:hover { background-color: #1c6dd0; }
        """)
        self.filters_layout.addWidget(self.btn_apply)

        if not self.show_date_filter:
            self.lbl_date_from.hide()
            self.start_date.hide()
            self.lbl_date_to.hide()
            self.end_date.hide()
            self.btn_apply.hide()

        self.filters_layout.addStretch()

        self.global_search = QLineEdit()
        self.global_search.setPlaceholderText("Search all columns...")
        self.global_search.setFixedWidth(200)
        self.global_search.setStyleSheet("""
            QLineEdit { border: 1px solid #c8d8ec; border-radius: 4px; padding: 4px 8px; font-size: 11px; background: white; color: #333; }
            QLineEdit:focus { border: 1px solid #1a5fb4; }
        """)
        self.global_search.textChanged.connect(self._apply_filters)
        self.global_search.installEventFilter(self)
        self.filters_layout.addWidget(self.global_search)

        self.filters_layout.addStretch()


        self.btn_pdf = QToolButton()
        self.btn_pdf.setToolTip("Preview PDF")
        self.btn_pdf.setIcon(qta.icon("fa5s.file-pdf", color="#ffffff", scale_factor=0.7))
        self.btn_pdf.setFixedSize(30, 30)
        self.btn_pdf.setStyleSheet("""
            QToolButton { background-color: #b02020; color: white; border: none; border-radius: 4px; }
            QToolButton:hover { background-color: #c92a2a; }
        """)
        self.btn_pdf.clicked.connect(self._export_pdf)
        self.filters_layout.addWidget(self.btn_pdf)

        self.btn_excel = QToolButton()
        self.btn_excel.setToolTip("Export Excel")
        self.btn_excel.setIcon(qta.icon("fa5s.file-excel", color="#ffffff", scale_factor=0.7))
        self.btn_excel.setFixedSize(30, 30)
        self.btn_excel.setStyleSheet("""
            QToolButton { background-color: #1a7a3c; color: white; border: none; border-radius: 4px; }
            QToolButton:hover { background-color: #1e8f46; }
        """)
        self.btn_excel.clicked.connect(self._export_excel)
        self.filters_layout.addWidget(self.btn_excel)


        self.filters_layout.addSpacing(15)

        self.btn_add = QPushButton(" Add")
        self.btn_add.setIcon(qta.icon("fa5s.plus", color="white", scale_factor=0.7))
        self.btn_add.setFixedHeight(30) # Fix height to identically match PDF/Excel
        self.btn_add.setStyleSheet("""
            QPushButton { background-color: #1a5fb4; color: white; border: none; border-radius: 4px; padding: 0px 12px; font-weight: bold; font-size: 11px; }
            QPushButton:hover { background-color: #1c6dd0; }
        """)
        self.filters_layout.addWidget(self.btn_add)
        
        if self.is_report:
            self.btn_add.hide()

        self.filters_layout.addSpacing(10)

        self.btn_columns_header = QToolButton()
        self.btn_columns_header.setToolTip("Toggle Columns")
        self.btn_columns_header.setIcon(qta.icon("fa5s.sliders-h", color="#1a5fb4", scale_factor=0.8))
        self.btn_columns_header.setFixedSize(30, 30)
        self.btn_columns_header.setStyleSheet("""
            QToolButton { background-color: transparent; color: #1a5fb4; border: 1px solid #c8d8ec; border-radius: 4px; }
            QToolButton:hover { background-color: #e4eaf4; }
            QToolButton::menu-indicator { image: none; }
        """)
        self.btn_columns_header.setPopupMode(QToolButton.InstantPopup)
        self.filters_layout.addWidget(self.btn_columns_header)

        self.top_layout.addLayout(self.filters_layout)
        self.main_layout.addWidget(self.top_frame)

        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(15, 5, 15, 15)
        self.content_layout.setSpacing(0)
        self.main_layout.addLayout(self.content_layout)
        
        self.columns_menu = QMenu(self)
        self.columns_menu.setStyleSheet("""
            QMenu { background-color: white; border: 1px solid #c8d8ec; } 
            QMenu::item { padding: 6px 25px 6px 25px; color: #1a5fb4; } 
            QMenu::item:selected { background-color: #e8f1f8; color: #1a5fb4; }
        """)
        
        self._create_table()

    def _create_table(self):
        self.table = QTableWidget(0, 0)
        self.table.setStyleSheet(self.get_table_stylesheet())
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        
        header = self.table.horizontalHeader()
        header.setSortIndicatorShown(False)
        header.setSectionsClickable(False)
        
        header.sectionResized.connect(self._reposition_header_buttons)
        header.geometriesChanged.connect(self._reposition_header_buttons)
        self.table.horizontalScrollBar().valueChanged.connect(self._reposition_header_buttons)
        
        self.content_layout.addWidget(self.table)
        
        # Sync scrolling and resizing
        # (Footer table removed, totals now strictly inside main table)

    def set_headers(self, headers):
        self.headers = headers
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        self.columns_menu.clear()
        for btn in self.sort_buttons:
            btn.deleteLater()
        self.sort_buttons.clear()
            
        header_viewport = self.table.horizontalHeader().viewport()
        
        for col, header in enumerate(headers):
            action = self.columns_menu.addAction(header)
            action.setCheckable(True)
            action.setChecked(True)
            action.toggled.connect(lambda checked, c=col: self._toggle_column_visibility(c, checked))
            
            btn = QToolButton(header_viewport)
            btn.setIcon(qta.icon("fa5s.caret-down", color="#1a5fb4", scale_factor=0.9))
            btn.setStyleSheet("QToolButton { border: none; background: transparent; } QToolButton:hover { background: #e4eaf4; border-radius: 4px; } QToolButton::menu-indicator { image: none; }")
            btn.setPopupMode(QToolButton.InstantPopup)
            btn.setFixedSize(22, 22)
            
            menu = QMenu(btn)
            menu.setStyleSheet("QMenu { background: white; border: 1px solid #c8d8ec; } QMenu::item { padding: 8px 25px; color: #1a5fb4; } QMenu::item:selected { background: #e8f1f8; }")
            asc = menu.addAction("Sort Ascending")
            desc = menu.addAction("Sort Descending")
            menu.addSeparator()
            eq = menu.addAction("Filter (Equal To)")
            
            asc.triggered.connect(lambda checked=False, c=col: self._sort_column(c, Qt.AscendingOrder))
            desc.triggered.connect(lambda checked=False, c=col: self._sort_column(c, Qt.DescendingOrder))
            eq.triggered.connect(lambda checked=False, c=col: self._focus_search(c))
            
            btn.setMenu(menu)
            self.sort_buttons.append(btn)
            
        self.btn_columns_header.setMenu(self.columns_menu)
            
        if self.show_column_filters:
            self._setup_filter_row()
        self._reposition_header_buttons()

    def _toggle_column_visibility(self, col, checked):
        if not checked:
            visible_count = sum(1 for i in range(self.table.columnCount()) if not self.table.isColumnHidden(i))
            if visible_count <= 2:
                action = self.columns_menu.actions()[col]
                action.blockSignals(True)
                action.setChecked(True)
                action.blockSignals(False)
                return
                
        self.table.setColumnHidden(col, not checked)
        self._reposition_header_buttons()

    def _reposition_header_buttons(self, *args):
        if not self.sort_buttons: return
        
        header = self.table.horizontalHeader()
        
        for col, btn in enumerate(self.sort_buttons):
            if header.isSectionHidden(col):
                btn.hide()
                continue
            btn.show()
            x = header.sectionViewportPosition(col)
            w = header.sectionSize(col)
            btn.move(x + w - 28, 6)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition_header_buttons()

    def _focus_search(self, col):
        """Displays an advanced Equal To popup that pushes values cleanly into the inline filter."""
        dlg = AdvancedFilterDialog(self.headers, col, self)
        if dlg.exec() == QDialog.Accepted:
            selected_col = dlg.col_combo.currentIndex()
            val = dlg.val_input.text()
            
            sb = self.table.cellWidget(0, selected_col)
            if sb:
                search_box = sb.findChild(QLineEdit)
                if search_box:
                    search_box.setText(val)

    def _setup_filter_row(self):
        if self.table.rowCount() == 0:
            self.table.insertRow(0)
            
        self.table.setRowHeight(0, 40)
            
        for col in range(self.table.columnCount()):
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(4, 4, 4, 4)
            layout.setSpacing(0)
            
            search_box = QLineEdit()
            search_box.setPlaceholderText("Search...")
            search_box.setStyleSheet("""
                QLineEdit { 
                    border: none; border-bottom: 1px solid #c8d8ec;
                    background: transparent; 
                    font-size: 13px; color: #1a5fb4;
                    padding: 0px 4px;
                    min-height: 26px;
                }
                QLineEdit:focus { border-bottom: 2px solid #1a5fb4; }
            """)
            search_box.textChanged.connect(self._apply_filters)
            layout.addWidget(search_box)
            self.table.setCellWidget(0, col, container)

    def _sort_column(self, col_index, order):
        self.current_sort_col = col_index
        self.current_sort_order = order
        
        has_totals = False
        last_row_idx = self.table.rowCount() - 1
        if last_row_idx > 0:
            first_item = self.table.item(last_row_idx, 0)
            if first_item and first_item.text().strip() == "Totals:":
                has_totals = True
                
        sort_end = last_row_idx if has_totals else self.table.rowCount()
        
        rows_data = []
        for r in range(1, sort_end):
            row_items = []
            for c in range(self.table.columnCount()):
                item = self.table.item(r, c)
                row_items.append(item.text() if item else "")
            rows_data.append(row_items)
            
        def sort_key(row):
            val = row[col_index]
            try:
                clean_val = val.replace("$", "").replace(",", "").strip()
                if not clean_val:
                    return (0, -float('inf'))
                return (0, float(clean_val))
            except ValueError:
                return (1, val.lower())
                
        rows_data.sort(key=sort_key, reverse=(order == Qt.DescendingOrder))
        
        for r_idx, row_items in enumerate(rows_data, start=1):
            for c_idx, val in enumerate(row_items):
                item = self.table.item(r_idx, c_idx)
                if item:
                    item.setText(val)
        
        self._apply_filters()

    def _apply_filters(self):
        filters = {}
        for col in range(self.table.columnCount()):
            widget = self.table.cellWidget(0, col)
            if widget:
                search_box = widget.findChild(QLineEdit)
                if search_box:
                    txt = search_box.text().lower()
                    if txt:
                        filters[col] = txt
                        
        global_txt = ""
        if hasattr(self, 'global_search'):
            global_txt = self.global_search.text().lower()
            
        has_totals = False
        last_row_idx = self.table.rowCount() - 1
        if last_row_idx > 0:
            first_item = self.table.item(last_row_idx, 0)
            if first_item and first_item.text().strip() == "Totals:":
                has_totals = True
                
        filter_end = last_row_idx if has_totals else self.table.rowCount()
                    
        for row in range(1, filter_end):
            match = True
            
            for col, txt in filters.items():
                item = self.table.item(row, col)
                if not item or txt not in item.text().lower():
                    match = False
                    break
                    
            if match and global_txt:
                global_match = False
                for col in range(self.table.columnCount()):
                    item = self.table.item(row, col)
                    if item and global_txt in item.text().lower():
                        global_match = True
                        break
                if not global_match:
                    match = False
                    
            self.table.setRowHidden(row, not match)
            
        if has_totals:
            self.table.setRowHidden(last_row_idx, False)
            
        self._update_totals()

    def _update_totals(self):
        """Automatically calculates sums for numerical columns and embeds the Totals row physically inside the table."""
        has_totals = False
        last_row_idx = self.table.rowCount() - 1
        if last_row_idx > 0:
            first_item = self.table.item(last_row_idx, 0)
            if first_item and first_item.text().strip() == "Totals:":
                has_totals = True
                
        calc_end = last_row_idx if has_totals else self.table.rowCount()
        
        totals_map = {}
        for col in range(self.table.columnCount()):
            total = 0
            is_numeric = False
            is_currency = False
            
            for row in range(1, calc_end):
                if self.table.isRowHidden(row): continue
                item = self.table.item(row, col)
                if not item: continue
                val = item.text().strip()
                if not val: continue
                
                if val.startswith('$'):
                    is_currency = True
                    val = val.replace('$', '').replace(',', '')
                else:
                    val = val.replace(',', '')
                    
                if val == '-':
                    num = 0.0
                    is_numeric = True
                else:
                    try:
                        num = float(val)
                        is_numeric = True
                    except ValueError:
                        is_numeric = False
                        break 
                
                total += num
            
            if is_numeric:
                if is_currency:
                    totals_map[col] = f"${total:,.2f}"
                elif total.is_integer():
                    if isinstance(total, (int, float)):
                        totals_map[col] = f"{int(total):,}" if float(total).is_integer() else f"{total:,.2f}"
                    else:
                        totals_map[col] = str(total)
                else:
                    totals_map[col] = f"{total:,.2f}"
            else:
                totals_map[col] = ""
                
        if not has_totals:
            self.table.insertRow(self.table.rowCount())
            last_row_idx = self.table.rowCount() - 1
            has_totals = True
            
        for col in range(self.table.columnCount()):
            item = self.table.item(last_row_idx, col)
            if not item:
                from PySide6.QtGui import QBrush, QColor
                item = QTableWidgetItem()
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                item.setBackground(QBrush(QColor("#fdfbf7")))
                self.table.setItem(last_row_idx, col, item)
            
            if col == 0:
                item.setText("Totals:")
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            else:
                val = totals_map.get(col, "")
                item.setText(val)
                if val:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

    def set_data(self, data_list):
        while self.table.rowCount() > 1:
            self.table.removeRow(1)
            
        self.table.setRowHeight(0, 40)
            
        for row_idx, row_data in enumerate(data_list, start=1):
            self.table.insertRow(row_idx)
            for col_idx, item in enumerate(row_data):
                val_str = str(item)
                table_item = QTableWidgetItem(val_str)
                
                # Auto-align numbers/currency to the right
                is_num = False
                clean_val = val_str.replace('$', '').replace(',', '').strip()
                if clean_val:
                    try:
                        float(clean_val)
                        is_num = True
                    except ValueError:
                        is_num = False
                
                if is_num:
                    table_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                else:
                    table_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                    
                self.table.setItem(row_idx, col_idx, table_item)
        
        # Must recalculate totals after fresh data insertion before sorting
        self._update_totals()
        
        if self.current_sort_col != -1:
            self._sort_column(self.current_sort_col, self.current_sort_order)
            
        self._apply_filters()

    def set_content(self, widget):
        if hasattr(self, 'table') and self.table is not None:
            self.table.setParent(None)
            self.table.deleteLater()
            self.table = None
        self.content_layout.addWidget(widget)

    def eventFilter(self, obj, event):
        if obj == self.global_search and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Down:
                self.table.setFocus()
                if self.table.rowCount() > 0 and not self.table.selectedItems():
                    self.table.selectRow(0)
                return True
            elif event.key() == Qt.Key_Up:
                self.table.setFocus()
                if self.table.rowCount() > 0 and not self.table.selectedItems():
                    self.table.selectRow(self.table.rowCount() - 1)
                return True
        ret = super().eventFilter(obj, event)
        return bool(ret) if ret is not None else False

    def get_table_stylesheet(self):
        return '''
            QTableWidget { gridline-color: #b0bec5; border: 1px solid #c8d8ec; background-color: white; font-size: 13px; color: #333333; }
            QHeaderView::section { background-color: #fdfbf7; padding: 8px 30px 8px 8px; border: none; border-bottom: 2px solid #e4eaf4; border-right: 1px solid #e4eaf4; font-weight: bold; font-size: 13px; color: #1a5fb4; }
            QTableWidget::item { padding: 6px; border-bottom: 1px solid #f0f4f8; }
            QTableWidget::item:selected { background-color: #e8f1f8; color: #1a5fb4; }
        '''

    def _export_pdf(self):
        from PySide6.QtWidgets import QMessageBox
        from PySide6.QtCore import QStandardPaths
        from PySide6.QtPrintSupport import QPrinter
        from PySide6.QtGui import QTextDocument, QPageSize, QPageLayout
        from models.company_defaults import get_defaults
        from views.dialogs.pdf_preview_dialog import PdfPreviewDialog
        import os
        
        if not hasattr(self, 'table') or self.table is None or self.table.rowCount() <= 1:
            QMessageBox.information(self, "Empty", "No data to export.")
            return

        try:
            comp = get_defaults()
            c_name = comp.get('company_name') or 'Havano POS'
        except:
            c_name = "Havano POS"

        df = self.start_date.date().toString("yyyy-MM-dd")
        dt = self.end_date.date().toString("yyyy-MM-dd")
        period = f"{df} to {dt}"

        c_header = f"<div style='font-size: 24px; font-weight: bold; color: #1a5fb4; margin:0; margin-bottom:10px;'>{c_name}</div>" if c_name.strip() else ""

        html = f"""<html><body style="font-family: 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; margin: 0; padding: 0;">
    <div style="text-align:center; margin-bottom: 10px;">{c_header}<div style="font-size: 18px; font-weight: bold; color: #1a5fb4; margin-top: 5px; margin-bottom: 5px;">{self.title_text}</div><div style="color: #666; font-size:12px; margin: 0;">Period: {period}</div></div>
    <table width="100%" cellpadding="10" cellspacing="0" style="border-collapse: collapse; font-size: 12px;">
                <thead>
                    <tr style="background-color: #1a5fb4; color: white; text-align: left;">
        """
        
        for i, h in enumerate(self.headers):
            if not self.table.isColumnHidden(i):
                html += f"<th style='text-align:left;'>{h}</th>"
        html += "</tr></thead><tbody>"

        for r in range(self.table.rowCount()):
            if self.table.isRowHidden(r):
                continue
            bg = "#fdfbf7" if r % 2 == 0 else "#ffffff"
            html += f"<tr style='background-color: {bg}; border-bottom: 1px solid #ddd;'>"
            for c in range(self.table.columnCount()):
                if self.table.isColumnHidden(c):
                    continue
                val = self.table.item(r, c).text() if self.table.item(r, c) else ""
                html += f"<td style='text-align:left; color:#333;'>{val}</td>"
            html += "</tr>"

        html += """
                </tbody>
            </table>
            <div style="margin-top:40px; font-size:10px; color:#888; text-align:center;">
                Generated by Havano ERP Business Intelligence Module
            </div>
        </body>
        </html>
        """
        
        docs = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        export_path = os.path.join(docs, f"{self.title_text.replace(' ', '_')}_{df}_{dt}.pdf")

        printer = QPrinter()
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(export_path)
        printer.setFullPage(True)
        printer.setPageSize(QPageSize(QPageSize.A4))
        printer.setPageOrientation(QPageLayout.Landscape)
        from PySide6.QtCore import QMarginsF
        printer.setPageMargins(QMarginsF(10, 2, 10, 10), QPageLayout.Millimeter)

        doc = QTextDocument()
        doc.setDocumentMargin(0)
        doc.setHtml(html.replace('\n', '').replace('\r', ''))
        doc.print_(printer)

        try:
            dlg = PdfPreviewDialog(export_path, title=f"Preview: {self.title_text}", parent=self)
            dlg.exec()
        except Exception as e:
            QMessageBox.information(self, "PDF Saved", f"Report saved successfully to:\n{export_path}\n(Preview error: {e})")

    def _export_excel(self):
        from PySide6.QtWidgets import QMessageBox, QFileDialog
        from PySide6.QtCore import QStandardPaths
        import os
        import csv
        
        if not hasattr(self, 'table') or self.table is None or self.table.rowCount() <= 1:
            QMessageBox.information(self, "Empty", "No data to export.")
            return
            
        docs = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        df = self.start_date.date().toString("yyyy-MM-dd")
        dt = self.end_date.date().toString("yyyy-MM-dd")
        default_name = f"{self.title_text.replace(' ', '_')}_{df}_{dt}.csv"
        export_path, _ = QFileDialog.getSaveFileName(self, "Save Excel/CSV", os.path.join(docs, default_name), "CSV Files (*.csv)")
        
        if not export_path:
            return
            
        try:
            with open(export_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                visible_headers = [h for i, h in enumerate(self.headers) if not self.table.isColumnHidden(i)]
                writer.writerow(visible_headers)
                for r in range(self.table.rowCount()):
                    if self.table.isRowHidden(r):
                        continue
                    row_data = []
                    for c in range(self.table.columnCount()):
                        if self.table.isColumnHidden(c):
                            continue
                        item = self.table.item(r, c)
                        row_data.append(item.text() if item else "")
                    writer.writerow(row_data)
            QMessageBox.information(self, "Export Successful", f"Report exported successfully to:\n{export_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export report:\n{e}")
