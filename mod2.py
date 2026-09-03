import sys

with open('views/main_window.py', 'r', encoding='utf-8') as f:
    lines = f.read().splitlines()

code = """            if hasattr(self, '_sales_chart_qty'):
                from PySide6.QtCharts import QPieSeries

                self._sales_chart_qty.removeAllSeries()
                for ax in self._sales_chart_qty.axes():
                    self._sales_chart_qty.removeAxis(ax)

                series_qty = QPieSeries()
                series_qty.setHoleSize(0.35)

                if top_s:
                    for i, (name, d) in enumerate(top_s[:5]):
                        cat_name = name if len(name) <= 15 else name[:13] + ".."
                        val = float(d["qty"])
                        slice = series_qty.append(f"{cat_name} ({val:g})", val)
                        slice.setLabelVisible(True)
                else:
                    series_qty.append("No Data", 1)

                self._sales_chart_qty.addSeries(series_qty)

            if hasattr(self, '_sales_chart_prof'):
                from PySide6.QtCharts import QPieSeries

                self._sales_chart_prof.removeAllSeries()
                for ax in self._sales_chart_prof.axes():
                    self._sales_chart_prof.removeAxis(ax)

                series_prof = QPieSeries()
                series_prof.setHoleSize(0.35)

                if top_p:
                    for i, (name, d) in enumerate(top_p[:5]):
                        cat_name = name if len(name) <= 15 else name[:13] + ".."
                        val = float(d["profit"])
                        slice = series_prof.append(f"{cat_name} (${val:,.2f})", val)
                        slice.setLabelVisible(True)
                else:
                    series_prof.append("No Data", 1)

                self._sales_chart_prof.addSeries(series_prof)"""

start = next(i for i, l in enumerate(lines) if "            if hasattr(self, '_sales_chart_qty'):" in l and i > 5000)
end = next(i for i, l in enumerate(lines) if "                series_prof.attachAxis(axisY)" in l and i > start)

lines[start:end+1] = code.splitlines()

with open('views/main_window.py', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines) + '\n')
print("Successfully modified pie charts")
