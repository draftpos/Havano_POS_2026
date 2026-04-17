# =============================================================================
# views/dialogs/shift_reprint_dialog.py
# Dialog for searching and reprinting shift reconciliations with autocomplete
# =============================================================================

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QLineEdit,
    QMessageBox, QPushButton, QFrame, QComboBox, QDateEdit, QGroupBox,
    QCompleter, QListView
)
from PySide6.QtCore import Qt, QDate, QStringListModel, QTimer
from PySide6.QtGui import QColor, QFont
from datetime import datetime, timedelta
import json


class ShiftReprintDialog(QDialog):
    """Dialog for searching and reprinting shift reconciliations."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowTitle("Reprint Shift Reconciliation")
        self.setMinimumSize(1000, 650)
        self.setModal(True)
        self._all_shift_numbers = []  # Store all shift numbers for autocomplete
        self._setup_styles()
        self._build_ui()
        self._load_shift_numbers_for_autocomplete()
        self._load_recent_shifts()
    
    def _setup_styles(self):
        self.setStyleSheet("""
            QDialog { background: white; }
            QLabel { color: #212121; font-size: 12px; }
            QLineEdit, QComboBox, QDateEdit {
                background: white; color: #212121;
                border: 1px solid #bdbdbd; border-radius: 4px;
                padding: 8px 10px; font-size: 13px;
                min-width: 150px;
            }
            QLineEdit:focus, QComboBox:focus, QDateEdit:focus {
                border: 2px solid #1976d2;
            }
            QPushButton {
                border: none;
                border-radius: 4px;
                padding: 10px 25px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton#searchBtn {
                background-color: #1976d2;
                color: white;
            }
            QPushButton#searchBtn:hover {
                background-color: #1565c0;
            }
            QPushButton#printBtn {
                background-color: #388e3c;
                color: white;
            }
            QPushButton#printBtn:hover {
                background-color: #2e7d32;
            }
            QPushButton#printBtn:disabled {
                background-color: #9e9e9e;
            }
            QPushButton#closeBtn {
                background-color: #757575;
                color: white;
            }
            QPushButton#closeBtn:hover {
                background-color: #616161;
            }
            QTableWidget {
                background: white; border: 1px solid #bdbdbd;
                gridline-color: #e0e0e0; font-size: 13px;
                alternate-background-color: #f5f5f5;
            }
            QTableWidget::item { padding: 10px 8px; }
            QTableWidget::item:selected { background-color: #1976d2; color: white; }
            QHeaderView::section {
                background: #e0e0e0; color: #212121;
                padding: 10px; font-weight: bold;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #bdbdbd;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QCompleter {
                background: white;
                border: 1px solid #bdbdbd;
                border-radius: 4px;
            }
            QCompleter::item {
                padding: 8px;
                color: #212121;
            }
            QCompleter::item:selected {
                background-color: #1976d2;
                color: white;
            }
        """)
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        header = QLabel("Reprint Shift Reconciliation")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #1976d2; padding-bottom: 10px; border-bottom: 2px solid #1976d2;")
        layout.addWidget(header)
        
        # Search section
        search_group = QGroupBox("Search Shift")
        search_layout = QHBoxLayout(search_group)
        
        # Search by shift number with autocomplete
        search_layout.addWidget(QLabel("Shift #:"))
        self.shift_number_input = QLineEdit()
        self.shift_number_input.setPlaceholderText("Enter Shift Number...")
        self.shift_number_input.setMinimumWidth(150)
        self.shift_number_input.returnPressed.connect(self._search_by_number)
        self.shift_number_input.textChanged.connect(self._on_shift_number_text_changed)
        search_layout.addWidget(self.shift_number_input)
        
        # OR label
        or_label = QLabel("OR")
        or_label.setStyleSheet("font-weight: bold; color: #757575; margin: 0 10px;")
        search_layout.addWidget(or_label)
        
        # Date range search
        search_layout.addWidget(QLabel("From:"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addDays(-7))
        self.date_from.setDisplayFormat("yyyy-MM-dd")
        search_layout.addWidget(self.date_from)
        
        search_layout.addWidget(QLabel("To:"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setDisplayFormat("yyyy-MM-dd")
        search_layout.addWidget(self.date_to)
        
        self.search_btn = QPushButton("Search")
        self.search_btn.setObjectName("searchBtn")
        self.search_btn.clicked.connect(self._search)
        search_layout.addWidget(self.search_btn)
        
        # Clear button
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setObjectName("clearBtn")
        self.clear_btn.setStyleSheet("""
            QPushButton#clearBtn {
                background-color: #ff9800;
                color: white;
            }
            QPushButton#clearBtn:hover {
                background-color: #f57c00;
            }
        """)
        self.clear_btn.clicked.connect(self._clear_search)
        search_layout.addWidget(self.clear_btn)
        
        layout.addWidget(search_group)
        
        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #757575; font-style: italic; padding: 5px;")
        layout.addWidget(self.status_label)
        
        # Results table
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "Recon ID", "Shift #", "Date", "Start Time", "End Time", 
            "Closed By", "Total Expected", "Total Variance"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.currentItemChanged.connect(self._on_current_item_changed)
        layout.addWidget(self.table)
        
        # Button panel
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        
        self.print_btn = QPushButton("Reprint Selected")
        self.print_btn.setObjectName("printBtn")
        self.print_btn.setEnabled(False)
        self.print_btn.clicked.connect(self._reprint)
        
        self.close_btn = QPushButton("Close")
        self.close_btn.setObjectName("closeBtn")
        self.close_btn.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.print_btn)
        button_layout.addWidget(self.close_btn)
        layout.addLayout(button_layout)
    
    def _load_shift_numbers_for_autocomplete(self):
        """Load all shift numbers for autocomplete functionality."""
        try:
            from models.shift import get_all_shift_reconciliations
            
            # Get all reconciliations (limit to last 500 for performance)
            reconciliations = get_all_shift_reconciliations(limit=500, offset=0)
            
            # Extract unique shift numbers
            shift_numbers = set()
            for rec in reconciliations:
                shift_num = rec.get('shift_number')
                if shift_num:
                    shift_numbers.add(str(shift_num))
            
            self._all_shift_numbers = sorted(shift_numbers, key=int, reverse=True)
            
            # Create completer
            completer = QCompleter()
            completer.setModel(QStringListModel(self._all_shift_numbers))
            completer.setCaseSensitivity(Qt.CaseInsensitive)
            completer.setFilterMode(Qt.MatchContains)
            completer.setCompletionMode(QCompleter.PopupCompletion)
            
            # Style the popup
            popup = QListView()
            popup.setStyleSheet("""
                QListView {
                    background: white;
                    border: 1px solid #bdbdbd;
                    border-radius: 4px;
                    padding: 4px;
                }
                QListView::item {
                    padding: 8px;
                    color: #212121;
                }
                QListView::item:selected {
                    background-color: #1976d2;
                    color: white;
                }
                QListView::item:hover {
                    background-color: #e3f2fd;
                }
            """)
            completer.setPopup(popup)
            
            self.shift_number_input.setCompleter(completer)
            
            print(f"[DEBUG] Loaded {len(self._all_shift_numbers)} shift numbers for autocomplete")
            
        except Exception as e:
            print(f"[DEBUG] Error loading shift numbers: {e}")
    
    def _on_shift_number_text_changed(self, text):
        """Handle text changes in shift number input for live search."""
        if len(text.strip()) >= 2:  # Search when 2 or more characters entered
            # Optional: Auto-search as user types
            QTimer.singleShot(500, self._search_by_number)
    
    def _load_recent_shifts(self):
        """Load recent shifts by default."""
        try:
            from models.shift import get_all_shift_reconciliations
            
            # Load last 50 reconciliations
            reconciliations = get_all_shift_reconciliations(limit=50, offset=0)
            
            if reconciliations:
                self._populate_table(reconciliations)
                self.status_label.setText(f"Showing last {len(reconciliations)} reconciliations")
            else:
                self.status_label.setText("No reconciliations found")
                
        except Exception as e:
            print(f"[DEBUG] Error loading recent shifts: {e}")
            self.status_label.setText(f"Error loading data: {str(e)}")
    
    def _search(self):
        """Perform search based on criteria."""
        shift_number = self.shift_number_input.text().strip()
        
        if shift_number:
            self._search_by_number()
        else:
            self._search_by_date()
    
    def _search_by_number(self):
        """Search for shift by number."""
        shift_number = self.shift_number_input.text().strip()
        
        if not shift_number:
            QMessageBox.warning(self, "Input Required", "Please enter a shift number to search.")
            return
        
        try:
            from models.shift import get_all_shift_reconciliations
            
            # Get all reconciliations and filter by shift number
            reconciliations = get_all_shift_reconciliations(limit=1000, offset=0)
            
            # Filter by shift number
            filtered = []
            for rec in reconciliations:
                if str(rec.get('shift_number', '')) == shift_number:
                    filtered.append(rec)
            
            if filtered:
                self._populate_table(filtered)
                self.status_label.setText(f"Found {len(filtered)} reconciliation(s) for Shift #{shift_number}")
            else:
                self.table.setRowCount(0)
                self.status_label.setText(f"No reconciliations found for Shift #{shift_number}")
                QMessageBox.information(self, "Not Found", f"No reconciliations found for Shift #{shift_number}")
                
        except Exception as e:
            print(f"[DEBUG] Error searching by number: {e}")
            QMessageBox.critical(self, "Error", f"Search failed: {str(e)}")
    
    def _search_by_date(self):
        """Search for shifts by date range."""
        date_from = self.date_from.date().toString("yyyy-MM-dd")
        date_to = self.date_to.date().toString("yyyy-MM-dd")
        
        if date_from > date_to:
            QMessageBox.warning(self, "Invalid Date Range", "From date cannot be after To date.")
            return
        
        try:
            from models.shift import get_all_shift_reconciliations
            
            # Get all reconciliations
            reconciliations = get_all_shift_reconciliations(limit=1000, offset=0)
            
            # Filter by date range
            filtered = []
            for rec in reconciliations:
                rec_date = rec.get('shift_date', '')
                if rec_date and date_from <= rec_date <= date_to:
                    filtered.append(rec)
            
            if filtered:
                self._populate_table(filtered)
                self.status_label.setText(f"Found {len(filtered)} reconciliations from {date_from} to {date_to}")
            else:
                self.table.setRowCount(0)
                self.status_label.setText(f"No reconciliations found from {date_from} to {date_to}")
                
        except Exception as e:
            print(f"[DEBUG] Error searching by date: {e}")
            QMessageBox.critical(self, "Error", f"Search failed: {str(e)}")
    
    def _clear_search(self):
        """Clear search inputs and reload recent shifts."""
        self.shift_number_input.clear()
        self.date_from.setDate(QDate.currentDate().addDays(-7))
        self.date_to.setDate(QDate.currentDate())
        self._load_recent_shifts()
        self.print_btn.setEnabled(False)
    
    def _populate_table(self, reconciliations):
        """Populate the table with reconciliation data."""
        # Block signals while rebuilding to prevent spurious enable/disable of print button
        self.table.blockSignals(True)
        self.table.setRowCount(len(reconciliations))
        self.table.clearSelection()
        self.print_btn.setEnabled(False)
        
        for row, rec in enumerate(reconciliations):
            # Recon ID
            recon_id_item = QTableWidgetItem(str(rec.get('id', '')))
            recon_id_item.setData(Qt.UserRole, rec.get('id'))
            self.table.setItem(row, 0, recon_id_item)
            
            # Shift #
            shift_num = rec.get('shift_number', '')
            shift_item = QTableWidgetItem(str(shift_num))
            self.table.setItem(row, 1, shift_item)
            
            # Date
            date_str = rec.get('shift_date', '')
            date_item = QTableWidgetItem(date_str)
            self.table.setItem(row, 2, date_item)
            
            # Start Time
            start_time = rec.get('start_time', '')
            start_item = QTableWidgetItem(start_time)
            self.table.setItem(row, 3, start_item)
            
            # End Time
            end_time = rec.get('end_time', '')
            end_item = QTableWidgetItem(end_time)
            self.table.setItem(row, 4, end_item)
            
            # Closed By
            closed_by = rec.get('closing_cashier_name', '')
            closed_item = QTableWidgetItem(closed_by)
            self.table.setItem(row, 5, closed_item)
            
            # Total Expected
            total_expected = float(rec.get('total_expected', 0))
            expected_item = QTableWidgetItem(f"${total_expected:,.2f}")
            expected_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 6, expected_item)
            
            # Total Variance
            total_variance = float(rec.get('total_variance', 0))
            variance_item = QTableWidgetItem(f"${total_variance:+,.2f}")
            variance_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if total_variance < 0:
                variance_item.setForeground(QColor("#d32f2f"))
            elif total_variance > 0:
                variance_item.setForeground(QColor("#388e3c"))
            else:
                variance_item.setForeground(QColor("#757575"))
            self.table.setItem(row, 7, variance_item)
        
        # Resize rows to content
        self.table.resizeRowsToContents()
        
        # Unblock signals, then auto-select the first row
        self.table.blockSignals(False)
        if reconciliations:
            self.table.selectRow(0)
    
    def _on_selection_changed(self):
        """Enable/disable print button based on selection."""
        selected = self.table.selectedItems()
        self.print_btn.setEnabled(len(selected) > 0)

    def _on_current_item_changed(self, current, previous):
        """Also enable button when keyboard navigation changes current item."""
        self.print_btn.setEnabled(current is not None)
    
    def _reprint(self):
        """Reprint the selected shift reconciliation."""
        selected_rows = set()
        for item in self.table.selectedItems():
            selected_rows.add(item.row())
        
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select a shift to reprint.")
            return
        
        # Get the first selected row
        row = list(selected_rows)[0]
        reconciliation_id = self.table.item(row, 0).data(Qt.UserRole)
        
        if not reconciliation_id:
            QMessageBox.warning(self, "Error", "Could not retrieve reconciliation ID.")
            return
        
        try:
            from models.shift import get_shift_reconciliation
            from services.printing_service import printing_service
            from models.advance_settings import AdvanceSettings
            
            # Get the reconciliation data
            reconciliation = get_shift_reconciliation(reconciliation_id)
            
            if not reconciliation:
                QMessageBox.warning(self, "Error", f"Could not load reconciliation #{reconciliation_id}")
                return
            
            # Parse the reconciliation data
            reconciliation_data = reconciliation.get('reconciliation_data', {})
            
            if not reconciliation_data:
                try:
                    import json
                    reconciliation_data = json.loads(reconciliation.get('reconciliation_json', '{}'))
                except:
                    reconciliation_data = {}
            
            # Get totals for printing
            totals = []
            payment_methods = reconciliation_data.get('payment_methods', [])
            for pm in payment_methods:
                totals.append({
                    'method': pm.get('method', ''),
                    'expected': pm.get('expected', 0),
                    'actual': pm.get('counted', 0),
                    'variance': pm.get('variance', 0)
                })
            
            # Get printer name
            settings = AdvanceSettings.load_from_file()
            printer_name = getattr(settings, "receiptPrinterName", None)
            
            # Reprint
            print(f"\n[DEBUG] Reprinting reconciliation #{reconciliation_id} for Shift #{reconciliation_data.get('shift_number')}")
            
            success = printing_service.print_shift_reconciliation(
                shift=None,  # Not needed for reprint
                totals=totals,
                reconciliation_data=reconciliation_data,
                printer_name=printer_name
            )
            
            if success:
                QMessageBox.information(
                    self, 
                    "Reprint Successful", 
                    f"Shift #{reconciliation_data.get('shift_number')} reconciliation reprinted successfully."
                )
            else:
                QMessageBox.warning(
                    self, 
                    "Reprint Failed", 
                    "Failed to print the reconciliation. Please check the printer."
                )
            
        except Exception as e:
            print(f"[DEBUG] Error reprinting: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to reprint: {str(e)}")
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.shift_number_input.hasFocus():
                self._search_by_number()
            elif self.print_btn.isEnabled():
                self._reprint()
        else:
            super().keyPressEvent(event)


def show_shift_reprint(parent=None):
    """Helper function to show the shift reprint dialog."""
    dialog = ShiftReprintDialog(parent)
    return dialog.exec()