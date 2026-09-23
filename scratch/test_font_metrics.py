from PySide6.QtGui import QFont, QFontMetrics

font = QFont("Arial", 12, QFont.Bold)
fm = QFontMetrics(font)

label = "Opening Bal:"
try:
    w1 = fm.horizontalAdvance(label)
    print(f"horizontalAdvance('{label}') = {w1}")
except Exception as e:
    print(f"horizontalAdvance error: {e}")

try:
    w2 = fm.boundingRect(label).width()
    print(f"boundingRect('{label}').width() = {w2}")
except Exception as e:
    print(f"boundingRect error: {e}")
