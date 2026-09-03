import sys
import re

with open('views/main_window.py', 'r', encoding='utf-8') as f:
    c = f.read()

# 1. Modify the pie size and remove slice labels in _render_dashboard
orig_render = """                series_qty = QPieSeries()
                series_qty.setHoleSize(0.35)

                if top_s:
                    for i, (name, d) in enumerate(top_s[:5]):
                        cat_name = name if len(name) <= 15 else name[:13] + ".."
                        val = float(d["qty"])
                        slice = series_qty.append(f"{cat_name} ({val:g})", val)
                        slice.setLabelVisible(True)
                else:
                    series_qty.append("No Data", 1)"""

new_render = """                series_qty = QPieSeries()
                series_qty.setHoleSize(0.35)
                series_qty.setPieSize(0.85)

                if top_s:
                    for i, (name, d) in enumerate(top_s[:5]):
                        cat_name = name if len(name) <= 15 else name[:13] + ".."
                        val = float(d["qty"])
                        slice = series_qty.append(f"{cat_name} ({val:g})", val)
                        slice.setLabelVisible(False)
                else:
                    series_qty.append("No Data", 1)"""

orig_render_prof = """                series_prof = QPieSeries()
                series_prof.setHoleSize(0.35)

                if top_p:
                    for i, (name, d) in enumerate(top_p[:5]):
                        cat_name = name if len(name) <= 15 else name[:13] + ".."
                        val = float(d["profit"])
                        slice = series_prof.append(f"{cat_name} (${val:,.2f})", val)
                        slice.setLabelVisible(True)
                else:
                    series_prof.append("No Data", 1)"""

new_render_prof = """                series_prof = QPieSeries()
                series_prof.setHoleSize(0.35)
                series_prof.setPieSize(0.85)

                if top_p:
                    for i, (name, d) in enumerate(top_p[:5]):
                        cat_name = name if len(name) <= 15 else name[:13] + ".."
                        val = float(d["profit"])
                        slice = series_prof.append(f"{cat_name} (${val:,.2f})", val)
                        slice.setLabelVisible(False)
                else:
                    series_prof.append("No Data", 1)"""

c = c.replace(orig_render, new_render).replace(orig_render_prof, new_render_prof)

# 2. Modify charts in _build_overview_tab to have legend at bottom
orig_charts_qty = """            self._sales_chart_qty = QChart()
            self._sales_chart_qty.setTitle("Top Products by Quantity")
            self._sales_chart_qty.setAnimationOptions(QChart.SeriesAnimations)"""

new_charts_qty = """            from PySide6.QtCore import Qt
            self._sales_chart_qty = QChart()
            self._sales_chart_qty.setTitle("Top Products by Quantity")
            self._sales_chart_qty.setAnimationOptions(QChart.SeriesAnimations)
            self._sales_chart_qty.legend().setAlignment(Qt.AlignBottom)
            f = self._sales_chart_qty.legend().font()
            f.setPointSize(10)
            self._sales_chart_qty.legend().setFont(f)"""

orig_charts_prof = """            self._sales_chart_prof = QChart()
            self._sales_chart_prof.setTitle("Top Products by Profit")
            self._sales_chart_prof.setAnimationOptions(QChart.SeriesAnimations)"""

new_charts_prof = """            from PySide6.QtCore import Qt
            self._sales_chart_prof = QChart()
            self._sales_chart_prof.setTitle("Top Products by Profit")
            self._sales_chart_prof.setAnimationOptions(QChart.SeriesAnimations)
            self._sales_chart_prof.legend().setAlignment(Qt.AlignBottom)
            f = self._sales_chart_prof.legend().font()
            f.setPointSize(10)
            self._sales_chart_prof.legend().setFont(f)"""

c = c.replace(orig_charts_qty, new_charts_qty).replace(orig_charts_prof, new_charts_prof)

# 3. Modify Finance and Expenses charts
orig_finance = """            self._finance_chart = QChart()
            self._finance_chart.setTitle("Monthly Revenue vs Expenses")
            self._finance_chart.setAnimationOptions(QChart.SeriesAnimations)
            
            series = QPieSeries()
            series.setHoleSize(0.35)
            series.append("Revenue", 7000).setLabelVisible(True)
            series.append("Expenses", 3000).setLabelVisible(True)"""

new_finance = """            from PySide6.QtCore import Qt
            self._finance_chart = QChart()
            self._finance_chart.setTitle("Monthly Revenue vs Expenses")
            self._finance_chart.setAnimationOptions(QChart.SeriesAnimations)
            self._finance_chart.legend().setAlignment(Qt.AlignBottom)
            f = self._finance_chart.legend().font()
            f.setPointSize(10)
            self._finance_chart.legend().setFont(f)
            
            series = QPieSeries()
            series.setHoleSize(0.35)
            series.setPieSize(0.85)
            series.append("Revenue (7000)", 7000).setLabelVisible(False)
            series.append("Expenses (3000)", 3000).setLabelVisible(False)"""

orig_expenses = """            self._expenses_chart = QChart()
            self._expenses_chart.setTitle("Expenses by Category")
            self._expenses_chart.setAnimationOptions(QChart.SeriesAnimations)
            
            series = QPieSeries()
            series.setHoleSize(0.35)
            series.append("Rent", 1200).setLabelVisible(True)
            series.append("Utilities", 300).setLabelVisible(True)
            series.append("Payroll", 4500).setLabelVisible(True)
            series.append("Supplies", 800).setLabelVisible(True)"""

new_expenses = """            from PySide6.QtCore import Qt
            self._expenses_chart = QChart()
            self._expenses_chart.setTitle("Expenses by Category")
            self._expenses_chart.setAnimationOptions(QChart.SeriesAnimations)
            self._expenses_chart.legend().setAlignment(Qt.AlignBottom)
            f = self._expenses_chart.legend().font()
            f.setPointSize(10)
            self._expenses_chart.legend().setFont(f)
            
            series = QPieSeries()
            series.setHoleSize(0.35)
            series.setPieSize(0.85)
            series.append("Rent (1200)", 1200).setLabelVisible(False)
            series.append("Utilities (300)", 300).setLabelVisible(False)
            series.append("Payroll (4500)", 4500).setLabelVisible(False)
            series.append("Supplies (800)", 800).setLabelVisible(False)"""

c = c.replace(orig_finance, new_finance).replace(orig_expenses, new_expenses)

with open('views/main_window.py', 'w', encoding='utf-8') as f:
    f.write(c)

print("Successfully increased pie size and moved legend to bottom")
