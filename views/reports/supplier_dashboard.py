from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from database.db import get_connection, fetchall_dicts

class SupplierDashboardWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #f5f8fc;")
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        
        hdr = QLabel("Supplier Overview")
        hdr.setStyleSheet("color:#1a5fb4; font-size:24px; font-weight:bold;")
        layout.addWidget(hdr)
        
        try:
            from PySide6.QtCharts import QChart, QChartView, QPieSeries
            
            self._chart = QChart()
            self._chart.setTitle("Top Suppliers by Spend")
            self._chart.setAnimationOptions(QChart.SeriesAnimations)
            self._chart.legend().setAlignment(Qt.AlignBottom)
            f = self._chart.legend().font()
            f.setPointSize(10)
            self._chart.legend().setFont(f)
            
            series = QPieSeries()
            series.setHoleSize(0.35)
            series.setPieSize(0.85)
            
            # Fetch real data
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT TOP 5 s.name, ISNULL(SUM(e.amount), 0) as total 
                FROM suppliers s 
                LEFT JOIN expenses e ON e.supplier_id = s.id 
                GROUP BY s.name 
                HAVING SUM(e.amount) > 0
                ORDER BY total DESC
            """)
            rows = fetchall_dicts(cur)
            conn.close()
            
            has_data = False
            for r in rows:
                val = float(r['total'])
                if val > 0:
                    lbl = f"{r['name']} ({val:.0f})"
                    series.append(lbl, val).setLabelVisible(False)
                    has_data = True
                    
            if not has_data:
                series.append("No Data (0)", 1).setLabelVisible(False)
                
            self._chart.addSeries(series)
            
            cv = QChartView(self._chart)
            cv.setRenderHint(QPainter.Antialiasing)
            cv.setStyleSheet("background:#ffffff; border:none; border-radius:8px;")
            layout.addWidget(cv, 1)
            
        except ImportError:
            lbl = QLabel("QtCharts not available.")
            layout.addWidget(lbl)
