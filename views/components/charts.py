from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush

class SimpleBarChart(QWidget):
    def __init__(self, title, labels, values, parent=None):
        super().__init__(parent)
        self.title = title
        self.labels = labels
        self.values = values
        self.setMinimumSize(300, 200)
        self.setStyleSheet("background-color: white; border: 1px solid #c8d8ec; border-radius: 5px;")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw background
        painter.fillRect(self.rect(), QColor("#ffffff"))
        
        # Draw title
        painter.setPen(QColor("#1a5fb4"))
        font = QFont("Segoe UI", 12, QFont.Bold)
        painter.setFont(font)
        painter.drawText(10, 25, self.title)
        
        if not self.values:
            painter.drawText(10, 50, "No data")
            return
            
        max_val = max(self.values)
        if max_val == 0:
            max_val = 1
            
        w = self.width()
        h = self.height()
        
        chart_x = 40
        chart_y = 40
        chart_w = w - 60
        chart_h = h - 70
        
        # Draw axes
        painter.setPen(QPen(QColor("#c8d8ec"), 2))
        painter.drawLine(chart_x, chart_y, chart_x, chart_y + chart_h)
        painter.drawLine(chart_x, chart_y + chart_h, chart_x + chart_w, chart_y + chart_h)
        
        # Draw bars
        n = len(self.values)
        bar_w = (chart_w / n) * 0.6
        spacing = (chart_w / n) * 0.4
        
        painter.setFont(QFont("Segoe UI", 8))
        for i, (lbl, val) in enumerate(zip(self.labels, self.values)):
            bar_h = (val / max_val) * (chart_h - 20)
            x = chart_x + spacing/2 + i * (bar_w + spacing)
            y = chart_y + chart_h - bar_h
            
            painter.setBrush(QBrush(QColor("#1a5fb4")))
            painter.setPen(Qt.NoPen)
            painter.drawRect(int(x), int(y), int(bar_w), int(bar_h))
            
            # Label
            painter.setPen(QColor("#1a5fb4"))
            painter.drawText(int(x), int(chart_y + chart_h + 15), str(lbl)[:6])
            # Value
            painter.drawText(int(x), int(y - 5), str(val))

class SimpleLineChart(QWidget):
    def __init__(self, title, labels, values, parent=None):
        super().__init__(parent)
        self.title = title
        self.labels = labels
        self.values = values
        self.setMinimumSize(300, 200)
        self.setStyleSheet("background-color: white; border: 1px solid #c8d8ec; border-radius: 5px;")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw background
        painter.fillRect(self.rect(), QColor("#ffffff"))
        
        # Draw title
        painter.setPen(QColor("#1a5fb4"))
        font = QFont("Segoe UI", 12, QFont.Bold)
        painter.setFont(font)
        painter.drawText(10, 25, self.title)
        
        if not self.values:
            painter.drawText(10, 50, "No data")
            return
            
        max_val = max(self.values)
        if max_val == 0:
            max_val = 1
            
        w = self.width()
        h = self.height()
        
        chart_x = 40
        chart_y = 40
        chart_w = w - 60
        chart_h = h - 70
        
        # Draw axes
        painter.setPen(QPen(QColor("#c8d8ec"), 2))
        painter.drawLine(chart_x, chart_y, chart_x, chart_y + chart_h)
        painter.drawLine(chart_x, chart_y + chart_h, chart_x + chart_w, chart_y + chart_h)
        
        # Draw line
        n = len(self.values)
        if n < 2:
            return
            
        spacing = chart_w / (n - 1)
        
        points = []
        for i, val in enumerate(self.values):
            x = chart_x + i * spacing
            y = chart_y + chart_h - (val / max_val) * (chart_h - 20)
            points.append((x, y))
            
        painter.setPen(QPen(QColor("#1a5fb4"), 3))
        for i in range(n - 1):
            painter.drawLine(int(points[i][0]), int(points[i][1]), int(points[i+1][0]), int(points[i+1][1]))
            
        painter.setFont(QFont("Segoe UI", 8))
        for i, (lbl, val) in enumerate(zip(self.labels, self.values)):
            x, y = points[i]
            painter.setBrush(QBrush(QColor("#ffffff")))
            painter.setPen(QPen(QColor("#1a5fb4"), 2))
            painter.drawEllipse(int(x-4), int(y-4), 8, 8)
            
            painter.setPen(QColor("#1a5fb4"))
            painter.drawText(int(x-10), int(chart_y + chart_h + 15), str(lbl)[:6])

def create_bar_chart(title, labels, values):
    return SimpleBarChart(title, labels, values)

def create_line_chart(title, labels, values):
    return SimpleLineChart(title, labels, values)
