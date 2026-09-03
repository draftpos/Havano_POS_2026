import os
import tempfile
import webbrowser
from PySide6.QtWidgets import QTableWidget

class BrowserPrintService:
    @staticmethod
    def print_table(table: QTableWidget, title: str, meta_info: list[str] = None):
        """
        Extracts headers and rows from a QTableWidget and renders it as a beautifully styled HTML file,
        then opens it in the default system browser for perfect printing.
        
        :param table: The QTableWidget to print.
        :param title: The title of the report (e.g., "Detailed Inventory Ledger").
        :param meta_info: A list of metadata strings (e.g., ["From: 2026-01-01", "To: 2026-12-31"]).
        """
        company_name = "Havano POS"
        try:
            from database.db import get_connection
            conn = get_connection()
            if conn:
                cur = conn.cursor()
                cur.execute("SELECT company_name FROM company_settings LIMIT 1")
                row = cur.fetchone()
                if row and row[0]:
                    company_name = str(row[0])
                conn.close()
        except Exception:
            pass

        # Determine which columns to hide (either hidden by table or completely empty)
        empty_columns = set()
        for c in range(table.columnCount()):
            if table.isColumnHidden(c):
                empty_columns.add(c)
                continue
            
            has_content = False
            for r in range(table.rowCount()):
                if table.isRowHidden(r):
                    continue
                item = table.item(r, c)
                if item and item.text().strip() != "":
                    has_content = True
                    break
                    
            if not has_content:
                empty_columns.add(c)

        # Parse table headers
        headers = []
        for c in range(table.columnCount()):
            if c in empty_columns:
                continue
                
            item = table.horizontalHeaderItem(c)
            text = item.text() if item else ""
            
            align = "left"
            if item:
                try:
                    alignment = int(item.textAlignment())
                    if alignment & 0x0002: # Qt.AlignRight
                        align = "right"
                    elif alignment & 0x0004: # Qt.AlignHCenter
                        align = "center"
                except Exception:
                    pass
                    
            headers.append({"text": text, "align": align, "col_idx": c})

        # Base HTML and CSS
        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>{title}</title>
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
                body {{
                    font-family: 'Inter', sans-serif;
                    margin: 40px auto;
                    max-width: 1200px;
                    color: #334155;
                    background-color: #ffffff;
                }}
                .header-container {{
                    text-align: center;
                    margin-bottom: 30px;
                    padding-bottom: 20px;
                    border-bottom: 2px solid #e2e8f0;
                }}
                .company-name {{
                    font-size: 28px;
                    font-weight: 700;
                    color: #0f172a;
                    margin: 0 0 5px 0;
                }}
                .report-title {{
                    font-size: 22px;
                    font-weight: 600;
                    color: #2563eb;
                    margin: 0 0 15px 0;
                }}
                .meta-info {{
                    font-size: 14px;
                    color: #64748b;
                    display: flex;
                    justify-content: center;
                    flex-wrap: wrap;
                    gap: 20px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    font-size: 13px;
                }}
                th {{
                    background-color: #f8fafc;
                    color: #475569;
                    font-weight: 600;
                    padding: 12px 8px;
                    border-bottom: 2px solid #cbd5e1;
                    /* text-align is now dynamic per-column */
                }}
                td {{
                    padding: 10px 8px;
                    border-bottom: 1px solid #f1f5f9;
                }}
                tr:nth-child(even) td {{
                    background-color: #f8fafc;
                }}
                
                @media print {{
                    body {{ margin: 0; max-width: none; }}
                    .header-container {{ border-bottom: 1px solid #000; }}
                    th {{ background-color: #f0f0f0 !important; -webkit-print-color-adjust: exact; }}
                    tr {{ page-break-inside: avoid; }}
                    @page {{ size: landscape; margin: 1cm; }}
                }}
            </style>
        </head>
        <body>
            <div class="header-container">
                <div class="company-name">{company_name}</div>
                <div class="report-title">{title}</div>
                <div class="meta-info">
        """
        
        if meta_info:
            for info in meta_info:
                html += f"<span>{info}</span>"
                
        html += """
                </div>
            </div>
            <table>
                <thead>
                    <tr>
        """
        
        for h in headers:
            html += f"<th style='text-align: {h['align']};'>{h['text']}</th>"
            
        html += "</tr></thead><tbody>"
        
        # Parse table rows
        for r in range(table.rowCount()):
            # Check if row is hidden
            if table.isRowHidden(r):
                continue
                
            html += "<tr>"
            for c in range(table.columnCount()):
                # Check if column is hidden or completely empty
                if c in empty_columns:
                    continue
                    
                item = table.item(r, c)
                text = item.text() if item else ""
                
                # Check alignment of the item in the table to guess text-align
                align = "left"
                if item:
                    try:
                        alignment = int(item.textAlignment())
                        if alignment & 0x0002: # Qt.AlignRight
                            align = "right"
                        elif alignment & 0x0004: # Qt.AlignHCenter
                            align = "center"
                    except Exception:
                        pass
                
                html += f"<td style='text-align: {align};'>{text}</td>"
            html += "</tr>"
            
        html += "</tbody></table>"
        html += "<div style='margin-top: 40px; font-size: 10px; color: #888; text-align: center;'>Powered by Havano ERP</div>"
        html += "</body></html>"
        
        try:
            import subprocess
            import time
            
            if not os.path.exists("app_data"):
                os.makedirs("app_data")
                
            temp_html_path = os.path.abspath(os.path.join("app_data", "temp_browser_report.html"))
            with open(temp_html_path, 'w', encoding='utf-8') as f:
                f.write(html)
            
            # Generate a unique temp pdf path so it doesn't fail if the old one is still open
            pdf_path = os.path.abspath(os.path.join("app_data", f"preview_{int(time.time())}.pdf"))
            wkhtmltopdf_path = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
            
            if os.path.exists(wkhtmltopdf_path):
                from PySide6.QtWidgets import QProgressDialog, QApplication
                from PySide6.QtCore import Qt
                
                parent_window = table.window() if table else None
                progress = QProgressDialog("Generating PDF Report...", None, 0, 0, parent_window)
                progress.setWindowTitle("Please Wait")
                progress.setWindowModality(Qt.WindowModal)
                progress.setCancelButton(None)
                progress.setStyleSheet("""
                    QProgressDialog {
                        background-color: #ffffff;
                        color: #0f172a;
                        font-family: 'Inter', sans-serif;
                    }
                    QLabel {
                        color: #334155;
                        font-size: 14px;
                        font-weight: 500;
                    }
                    QProgressBar {
                        border: 1px solid #e2e8f0;
                        border-radius: 4px;
                        background-color: #f1f5f9;
                        text-align: center;
                    }
                    QProgressBar::chunk {
                        background-color: #2563eb;
                        width: 10px;
                    }
                """)
                progress.show()
                QApplication.processEvents()
                
                try:
                    subprocess.run([
                        wkhtmltopdf_path,
                        "--quiet",
                        "--enable-local-file-access",
                        "--orientation", "Landscape",
                        "--margin-top", "10mm",
                        "--margin-bottom", "10mm",
                        "--margin-left", "10mm",
                        "--margin-right", "10mm",
                        temp_html_path,
                        pdf_path
                    ], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
                finally:
                    progress.close()
                from views.dialogs.pdf_preview_dialog import PdfPreviewDialog
                dialog = PdfPreviewDialog(pdf_path, title)
                dialog.exec()
                return pdf_path
            else:
                import webbrowser
                webbrowser.open(f"file:///{temp_html_path}")
                return temp_html_path
                
        except Exception as e:
            try:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.critical(None, "Print Error", f"Failed to generate PDF report: {e}")
            except:
                print("Failed to generate PDF report:", e)
            return None

    @staticmethod
    def print_html(html_content: str, filename: str = "report.pdf"):
        """
        Saves raw HTML content to a temporary file and opens it in the browser for printing.
        
        :param html_content: The full HTML string to render.
        :param filename: Fallback filename (usually .pdf to hint at print target).
        """
        try:
            import subprocess
            import time
            
            if not os.path.exists("app_data"):
                os.makedirs("app_data")
                
            temp_html_path = os.path.abspath(os.path.join("app_data", "temp_browser_report.html"))
            with open(temp_html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            pdf_path = os.path.abspath(os.path.join("app_data", f"preview_{int(time.time())}.pdf"))
            wkhtmltopdf_path = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
            
            if os.path.exists(wkhtmltopdf_path):
                from PySide6.QtWidgets import QProgressDialog, QApplication
                from PySide6.QtCore import Qt
                
                progress = QProgressDialog("Generating PDF Report...", None, 0, 0)
                progress.setWindowTitle("Please Wait")
                progress.setWindowModality(Qt.WindowModal)
                progress.setCancelButton(None)
                progress.setStyleSheet("""
                    QProgressDialog {
                        background-color: #ffffff;
                        color: #0f172a;
                        font-family: 'Inter', sans-serif;
                    }
                    QLabel {
                        color: #334155;
                        font-size: 14px;
                        font-weight: 500;
                    }
                    QProgressBar {
                        border: 1px solid #e2e8f0;
                        border-radius: 4px;
                        background-color: #f1f5f9;
                        text-align: center;
                    }
                    QProgressBar::chunk {
                        background-color: #2563eb;
                        width: 10px;
                    }
                """)
                progress.show()
                QApplication.processEvents()
                
                try:
                    subprocess.run([
                        wkhtmltopdf_path,
                        "--quiet",
                        "--enable-local-file-access",
                        "--orientation", "Portrait", # Usually portrait for non-table direct HTML
                        "--margin-top", "10mm",
                        "--margin-bottom", "10mm",
                        "--margin-left", "10mm",
                        "--margin-right", "10mm",
                        temp_html_path,
                        pdf_path
                    ], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
                finally:
                    progress.close()
                from views.dialogs.pdf_preview_dialog import PdfPreviewDialog
                dialog = PdfPreviewDialog(pdf_path, filename)
                dialog.exec()
                return pdf_path
            else:
                import webbrowser
                webbrowser.open(f"file:///{temp_html_path}")
                return temp_html_path
                
        except Exception as e:
            try:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.critical(None, "Print Error", f"Failed to generate PDF: {e}")
            except:
                print("Failed to generate PDF:", e)
            return None
