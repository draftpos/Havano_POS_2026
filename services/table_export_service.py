import csv
import os
from PySide6.QtWidgets import QFileDialog, QMessageBox, QTableWidget

class TableExportService:
    @staticmethod
    def export_to_csv(table: QTableWidget, default_filename: str = "Export.csv", parent=None):
        try:
            from PySide6.QtCore import QStandardPaths
            downloads_dir = QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)
            if not downloads_dir:
                downloads_dir = os.path.expanduser("~/Downloads")
            default_path = os.path.join(downloads_dir, default_filename)
            
            path, _ = QFileDialog.getSaveFileName(parent, "Export Excel (CSV)", default_path, "CSV Files (*.csv)")
            if not path:
                return False
                
            with open(path, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Write Headers
                headers = []
                for c in range(table.columnCount()):
                    if not table.isColumnHidden(c):
                        item = table.horizontalHeaderItem(c)
                        headers.append(item.text() if item else f"Column {c}")
                writer.writerow(headers)
                
                # Write Rows
                for r in range(table.rowCount()):
                    if table.isRowHidden(r):
                        continue
                        
                    row_data = []
                    for c in range(table.columnCount()):
                        if not table.isColumnHidden(c):
                            item = table.item(r, c)
                            row_data.append(item.text() if item else "")
                    writer.writerow(row_data)
                    
            QMessageBox.information(parent, "Success", f"Data exported successfully to\n{path}")
            
            # Auto-open the folder
            try:
                import subprocess
                if os.name == 'nt':
                    subprocess.Popen(rf'explorer /select,"{os.path.normpath(path)}"')
            except:
                pass
                
            return True
        except Exception as e:
            QMessageBox.critical(parent, "Error", f"Failed to export data:\n{e}")
            return False
