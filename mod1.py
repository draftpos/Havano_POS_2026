import sys

with open('views/main_window.py', 'r', encoding='utf-8') as f:
    lines = f.read().splitlines()

code = """        # Product Performance Insights (Charts)
        try:
            from PySide6.QtCharts import QChart, QChartView
            from PySide6.QtGui import QPainter

            charts_lay = QHBoxLayout()
            charts_lay.setSpacing(16)

            self._sales_chart_qty = QChart()
            self._sales_chart_qty.setTitle("Top Products by Quantity")
            self._sales_chart_qty.setAnimationOptions(QChart.SeriesAnimations)
            cv1 = QChartView(self._sales_chart_qty)
            cv1.setRenderHint(QPainter.Antialiasing)
            cv1.setStyleSheet("background:#ffffff; border:1px solid #c8d8ec; border-radius:8px;")
            cv1.setFixedHeight(300)
            charts_lay.addWidget(cv1)

            self._sales_chart_prof = QChart()
            self._sales_chart_prof.setTitle("Top Products by Profit")
            self._sales_chart_prof.setAnimationOptions(QChart.SeriesAnimations)
            cv2 = QChartView(self._sales_chart_prof)
            cv2.setRenderHint(QPainter.Antialiasing)
            cv2.setStyleSheet("background:#ffffff; border:1px solid #c8d8ec; border-radius:8px;")
            cv2.setFixedHeight(300)
            charts_lay.addWidget(cv2)

            o_lay.addWidget(self._section_label("Product Performance Insights"))
            o_lay.addLayout(charts_lay)
        except Exception:
            pass

        # KPI row 1: Financial
        o_lay.addWidget(self._section_label("Financial Summary"))
        o_lay.addLayout(self._build_kpi_row_1())

        # KPI row 2: Stock values
        o_lay.addWidget(self._section_label("Stock Value Summary"))
        o_lay.addLayout(self._build_kpi_row_2())

        o_lay.addStretch()"""

start = next(i for i, l in enumerate(lines) if '        # KPI row 1: Financial' in l and i > 3360)
end = next(i for i, l in enumerate(lines) if '        o_lay.addStretch()' in l and i > start)

lines[start:end+1] = code.splitlines()

with open('views/main_window.py', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines) + '\n')
print("Successfully modified _build_overview_tab")
