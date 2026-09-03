import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QTextDocument, QPageSize, QPageLayout
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtCore import QMarginsF

app = QApplication(sys.argv)

html = '''<html><body style="margin: 0; padding: 0; background-color: yellow;">
<div style="background-color: lightblue; text-align:center;">
<h3 style="margin:0;">Low Stock Report</h3>
</div>
</body></html>'''

html = html.replace('\n', '').replace('\r', '')

printer = QPrinter()
printer.setOutputFormat(QPrinter.PdfFormat)
printer.setOutputFileName('test_pdf.pdf')
printer.setFullPage(True)
printer.setPageSize(QPageSize(QPageSize.A4))
printer.setPageOrientation(QPageLayout.Landscape)
printer.setPageMargins(QMarginsF(10, 2, 10, 10), QPageLayout.Millimeter)

doc = QTextDocument()
doc.setDocumentMargin(0)
doc.setHtml(html)
doc.print_(printer)
print('PDF created.')
