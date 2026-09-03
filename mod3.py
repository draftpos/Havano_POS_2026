import sys

with open('views/main_window.py', 'r', encoding='utf-8') as f:
    c = f.read()

orig1 = """        try:
            from PySide6.QtCharts import QChart, QChartView
            from PySide6.QtGui import QPainter
            self._finance_chart = QChart()
            self._finance_chart.setTitle("Monthly Revenue vs Expenses")
            self._finance_chart.setAnimationOptions(QChart.SeriesAnimations)
            cv = QChartView(self._finance_chart)
            cv.setRenderHint(QPainter.Antialiasing)
            cv.setStyleSheet(f"background:#ffffff; border:1px solid #c8d8ec; border-radius:8px;")
            lay.addWidget(cv, 1)
        except Exception:
            pass"""

new1 = """        try:
            from PySide6.QtCharts import QChart, QChartView, QPieSeries
            from PySide6.QtGui import QPainter
            self._finance_chart = QChart()
            self._finance_chart.setTitle("Monthly Revenue vs Expenses")
            self._finance_chart.setAnimationOptions(QChart.SeriesAnimations)
            
            series = QPieSeries()
            series.setHoleSize(0.35)
            series.append("Revenue", 7000).setLabelVisible(True)
            series.append("Expenses", 3000).setLabelVisible(True)
            self._finance_chart.addSeries(series)
            
            cv = QChartView(self._finance_chart)
            cv.setRenderHint(QPainter.Antialiasing)
            cv.setStyleSheet("background:#ffffff; border:1px solid #c8d8ec; border-radius:8px;")
            lay.addWidget(cv, 1)
        except Exception:
            pass"""

orig2 = """        try:
            from PySide6.QtCharts import QChart, QChartView
            from PySide6.QtGui import QPainter
            self._expenses_chart = QChart()
            self._expenses_chart.setTitle("Expenses by Category")
            self._expenses_chart.setAnimationOptions(QChart.SeriesAnimations)
            cv = QChartView(self._expenses_chart)
            cv.setRenderHint(QPainter.Antialiasing)
            cv.setStyleSheet(f"background:#ffffff; border:1px solid #c8d8ec; border-radius:8px;")
            lay.addWidget(cv, 1)
        except Exception:
            pass"""

new2 = """        try:
            from PySide6.QtCharts import QChart, QChartView, QPieSeries
            from PySide6.QtGui import QPainter
            self._expenses_chart = QChart()
            self._expenses_chart.setTitle("Expenses by Category")
            self._expenses_chart.setAnimationOptions(QChart.SeriesAnimations)
            
            series = QPieSeries()
            series.setHoleSize(0.35)
            series.append("Rent", 1200).setLabelVisible(True)
            series.append("Utilities", 300).setLabelVisible(True)
            series.append("Payroll", 4500).setLabelVisible(True)
            series.append("Supplies", 800).setLabelVisible(True)
            self._expenses_chart.addSeries(series)
            
            cv = QChartView(self._expenses_chart)
            cv.setRenderHint(QPainter.Antialiasing)
            cv.setStyleSheet("background:#ffffff; border:1px solid #c8d8ec; border-radius:8px;")
            lay.addWidget(cv, 1)
        except Exception:
            pass"""

c = c.replace(orig1, new1).replace(orig2, new2)

with open('views/main_window.py', 'w', encoding='utf-8') as f:
    f.write(c)
print("Successfully added pie charts to Finance and Expenses")
