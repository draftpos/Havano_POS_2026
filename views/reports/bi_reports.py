# views/reports/bi_reports.py

import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton,
    QLabel, QDateEdit, QMessageBox, QFileDialog, QSizePolicy
)
from PySide6.QtCore import Qt, QDate, QStandardPaths
from PySide6.QtGui import QColor, QTextDocument, QPageSize, QPageLayout
from PySide6.QtPrintSupport import QPrinter

import qtawesome as qta
from database.db import get_connection, fetchall_dicts
from models.company_defaults import get_defaults
from views.dialogs.pdf_preview_dialog import PdfPreviewDialog
from theme import *


class BaseReportDialog(QDialog):
    """
    Base dialog for all standalone BI reports using the new ReportTemplate.
    """
    def __init__(self, parent=None, title="Report"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.report_title = title
        self.setWindowState(Qt.WindowMaximized)
        self.setStyleSheet("QDialog { background-color: white; }")
        self.headers = []

    def setup_ui(self, headers):
        from views.reports.report_template import ReportTemplate
        self.headers = headers
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.report_template = ReportTemplate(title=self.report_title, is_report=True, parent=self)
        self.report_template.set_headers(self.headers)
        
        self.date_from = self.report_template.start_date
        self.date_to = self.report_template.end_date
        
        # Connect the Apply Filters button to trigger the SQL fetch
        self.report_template.btn_apply.clicked.connect(self._load_data)
        
        layout.addWidget(self.report_template)
        
        # Setup initial 30 day range to match old behavior
        self.date_from.setDate(QDate.currentDate().addDays(-30))
        self.date_to.setDate(QDate.currentDate())
        
        # Load initial data
        self._load_data()

    def _get_dates(self):
        return self.date_from.date().toString("yyyy-MM-dd"), self.date_to.date().toString("yyyy-MM-dd")

    def _format_money(self, amount):
        return f"${float(amount):,.2f}"
    
    def _format_qty(self, qty):
        return f"{float(qty):,.2f}"

    def _populate_table(self, data_rows):
        clean_data = []
        for r in data_rows:
            if r and isinstance(r[0], str) and "TOTALS" in r[0].upper():
                continue
            clean_data.append(r)
        
        self.report_template.set_data(clean_data)

    def _load_data(self):
        pass


class ItemSalesReportDialog(BaseReportDialog):
    def __init__(self, parent=None):
        super().__init__(parent, "Item Sales Report")
        self.setup_ui(["Item Name", "Qty Sold", "Value Sold", "% Contribution"])

    def _load_data(self):
        df, dt = self._get_dates()
        sql = """
            SELECT 
                COALESCE(si.product_name, 'Unknown Item') as item_name,
                SUM(si.qty) as qty_sold,
                SUM(si.qty * si.price) as value_sold
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            WHERE s.invoice_date >= ? AND s.invoice_date <= ?
            GROUP BY si.part_no, si.product_name
            ORDER BY value_sold DESC
        """
        conn = get_connection(); cur = conn.cursor()
        cur.execute(sql, (df, dt)); rows = fetchall_dicts(cur)
        conn.close()

        total_sales = sum(float(r['value_sold'] or 0) for r in rows)
        data = []
        for r in rows:
            val = float(r['value_sold'] or 0)
            contrib = (val / total_sales * 100) if total_sales > 0 else 0
            data.append([
                r['item_name'], 
                self._format_qty(r['qty_sold'] or 0), 
                self._format_money(val), 
                f"{contrib:.2f}%"
            ])
        if data:
            data.append(["TOTALS", "", self._format_money(total_sales), "100.00%"])
        self._populate_table(data)


class CategorySalesReportDialog(BaseReportDialog):
    def __init__(self, parent=None):
        super().__init__(parent, "Category Sales Report")
        self.setup_ui(["Category Name", "Qty Sold", "Value Sold"])

    def _load_data(self):
        df, dt = self._get_dates()
        sql = """
            SELECT 
                COALESCE(p.category, 'Uncategorized') as category,
                SUM(si.qty) as qty_sold,
                SUM(si.qty * si.price) as value_sold
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            LEFT JOIN products p ON si.part_no = p.part_no
            WHERE s.invoice_date >= ? AND s.invoice_date <= ?
            GROUP BY category
            ORDER BY value_sold DESC
        """
        conn = get_connection(); cur = conn.cursor()
        cur.execute(sql, (df, dt)); rows = fetchall_dicts(cur)
        conn.close()

        total_sales = sum(float(r['value_sold'] or 0) for r in rows)
        data = []
        for r in rows:
            val = float(r['value_sold'] or 0)
            data.append([
                r['category'], 
                self._format_qty(r['qty_sold'] or 0), 
                self._format_money(val)
            ])
        if data:
            data.append(["TOTALS", "", self._format_money(total_sales)])
        self._populate_table(data)


class ItemProfitabilityReportDialog(BaseReportDialog):
    def __init__(self, parent=None):
        super().__init__(parent, "Item Profitability Report")
        self.setup_ui(["Item Name", "Qty Sold", "Value Sold", "Cost", "Profit", "Margin %"])

    def _load_data(self):
        df, dt = self._get_dates()
        sql = """
            SELECT 
                COALESCE(si.product_name, 'Unknown Item') as item_name,
                SUM(si.qty) as qty_sold,
                SUM(si.qty * si.price) as value_sold,
                SUM(si.qty * COALESCE(si.cost_price, p.cost_price, 0)) as total_cost
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            LEFT JOIN products p ON si.part_no = p.part_no
            WHERE s.invoice_date >= ? AND s.invoice_date <= ?
            GROUP BY si.part_no, si.product_name
            ORDER BY value_sold DESC
        """
        conn = get_connection(); cur = conn.cursor()
        cur.execute(sql, (df, dt)); rows = fetchall_dicts(cur)
        conn.close()

        data = []
        t_val = t_cost = t_prof = 0
        for r in rows:
            val = float(r['value_sold'] or 0)
            cost = float(r['total_cost'] or 0)
            profit = val - cost
            margin = (profit / val * 100) if val > 0 else 0
            
            t_val += val; t_cost += cost; t_prof += profit
            
            data.append([
                r['item_name'], self._format_qty(r['qty_sold'] or 0),
                self._format_money(val), self._format_money(cost),
                self._format_money(profit), f"{margin:.2f}%"
            ])
        
        if data:
            t_margin = (t_prof / t_val * 100) if t_val > 0 else 0
            data.append(["TOTALS", "", self._format_money(t_val), self._format_money(t_cost), self._format_money(t_prof), f"{t_margin:.2f}%"])
        self._populate_table(data)


class CategoryProfitabilityReportDialog(BaseReportDialog):
    def __init__(self, parent=None):
        super().__init__(parent, "Category Profitability Report")
        self.setup_ui(["Category Name", "Qty Sold", "Value Sold", "Cost", "Profit", "Margin %"])

    def _load_data(self):
        df, dt = self._get_dates()
        sql = """
            SELECT 
                COALESCE(p.category, 'Uncategorized') as category,
                SUM(si.qty) as qty_sold,
                SUM(si.qty * si.price) as value_sold,
                SUM(si.qty * COALESCE(si.cost_price, p.cost_price, 0)) as total_cost
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            LEFT JOIN products p ON si.part_no = p.part_no
            WHERE s.invoice_date >= ? AND s.invoice_date <= ?
            GROUP BY category
            ORDER BY value_sold DESC
        """
        conn = get_connection(); cur = conn.cursor()
        cur.execute(sql, (df, dt)); rows = fetchall_dicts(cur)
        conn.close()

        data = []
        t_val = t_cost = t_prof = 0
        for r in rows:
            val = float(r['value_sold'] or 0)
            cost = float(r['total_cost'] or 0)
            profit = val - cost
            margin = (profit / val * 100) if val > 0 else 0
            
            t_val += val; t_cost += cost; t_prof += profit
            
            data.append([
                r['category'], self._format_qty(r['qty_sold'] or 0),
                self._format_money(val), self._format_money(cost),
                self._format_money(profit), f"{margin:.2f}%"
            ])
        
        if data:
            t_margin = (t_prof / t_val * 100) if t_val > 0 else 0
            data.append(["TOTALS", "", self._format_money(t_val), self._format_money(t_cost), self._format_money(t_prof), f"{t_margin:.2f}%"])
        self._populate_table(data)


class CashierSalesReportDialog(BaseReportDialog):
    def __init__(self, parent=None):
        super().__init__(parent, "Cashier Sales Report")
        self.setup_ui(["Cashier Name", "Sales Value", "Profit per Cashier"])

    def _load_data(self):
        df, dt = self._get_dates()
        sql = """
            SELECT 
                COALESCE(u.username, 'Unknown Cashier') as cashier_name,
                SUM(si.qty * si.price) as value_sold,
                SUM(si.qty * COALESCE(si.cost_price, p.cost_price, 0)) as total_cost
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            LEFT JOIN users u ON s.cashier_id = u.id
            LEFT JOIN products p ON si.part_no = p.part_no
            WHERE s.invoice_date >= ? AND s.invoice_date <= ?
            GROUP BY s.cashier_id, u.username
            ORDER BY value_sold DESC
        """
        conn = get_connection(); cur = conn.cursor()
        cur.execute(sql, (df, dt)); rows = fetchall_dicts(cur)
        conn.close()

        data = []
        t_val = t_prof = 0
        for r in rows:
            val = float(r['value_sold'] or 0)
            cost = float(r['total_cost'] or 0)
            profit = val - cost
            
            t_val += val; t_prof += profit
            
            data.append([
                r['cashier_name'], 
                self._format_money(val), 
                self._format_money(profit)
            ])
            
        if data:
            data.append(["TOTALS", self._format_money(t_val), self._format_money(t_prof)])
        self._populate_table(data)


class TillProfitabilityReportDialog(BaseReportDialog):
    def __init__(self, parent=None):
        super().__init__(parent, "Till Profitability Report")
        self.setup_ui(["Station / Till", "Cashier", "Sales Value", "Cost", "Profit", "Margin %"])

    def _load_data(self):
        df, dt = self._get_dates()
        sql = """
            SELECT 
                COALESCE(sh.station, 1) as station_id,
                COALESCE(u.username, 'Unknown Cashier') as cashier_name,
                SUM(si.qty * si.price) as value_sold,
                SUM(si.qty * COALESCE(si.cost_price, p.cost_price, 0)) as total_cost
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            LEFT JOIN shifts sh ON s.shift_id = sh.id
            LEFT JOIN users u ON s.cashier_id = u.id
            LEFT JOIN products p ON si.part_no = p.part_no
            WHERE s.invoice_date >= ? AND s.invoice_date <= ?
            GROUP BY sh.station, u.username
            ORDER BY sh.station, value_sold DESC
        """
        conn = get_connection(); cur = conn.cursor()
        cur.execute(sql, (df, dt)); rows = fetchall_dicts(cur)
        conn.close()

        data = []
        t_val = t_cost = t_prof = 0
        for r in rows:
            val = float(r['value_sold'] or 0)
            cost = float(r['total_cost'] or 0)
            profit = val - cost
            margin = (profit / val * 100) if val > 0 else 0
            
            t_val += val; t_cost += cost; t_prof += profit
            
            data.append([
                f"Till {r['station_id']}",
                r['cashier_name'],
                self._format_money(val), self._format_money(cost),
                self._format_money(profit), f"{margin:.2f}%"
            ])
            
        if data:
            t_margin = (t_prof / t_val * 100) if t_val > 0 else 0
            data.append(["TOTALS", "", self._format_money(t_val), self._format_money(t_cost), self._format_money(t_prof), f"{t_margin:.2f}%"])
        self._populate_table(data)


class LowStockReportDialog(BaseReportDialog):
    def __init__(self, parent=None):
        super().__init__(parent, "Low Stock Report")
        self.setup_ui(["Item Name", "Part No", "Category", "Current Stock", "Reorder Level", "Deficit"])

    def _ensure_reorder_level_column(self):
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("""
                IF COL_LENGTH('products', 'reorder_level') IS NULL
                BEGIN
                    ALTER TABLE products ADD reorder_level DECIMAL(12,4) NULL DEFAULT 0;
                END
            """)
            conn.commit(); conn.close()
        except Exception as e:
            print(f"Error ensuring reorder_level: {e}")

    def _load_data(self):
        self._ensure_reorder_level_column()
        sql = """
            SELECT part_no, name, category, stock, COALESCE(reorder_level, 0) as reorder_level
            FROM products
            WHERE ISNULL(active, 1) = 1 AND (stock <= 0 OR stock <= COALESCE(reorder_level, 0))
            ORDER BY category, name
        """
        conn = get_connection(); cur = conn.cursor()
        cur.execute(sql); rows = fetchall_dicts(cur)
        conn.close()

        data = []
        for r in rows:
            stock = float(r['stock'] or 0)
            reorder = float(r['reorder_level'] or 0)
            deficit = reorder - stock
            data.append([
                r['name'], r['part_no'], r['category'] or 'General',
                f"{stock:.2f}", f"{reorder:.2f}", f"{deficit:.2f}"
            ])
        
        self._populate_table(data)


class ExpiredGoodsReportDialog(BaseReportDialog):
    def __init__(self, parent=None):
        super().__init__(parent, "Expired Goods Report")
        self.setup_ui(["Item Name", "Part No", "Batch No", "Expiry Date", "Qty Remaining"])

    def _load_data(self):
        sql = """
            SELECT p.name, p.part_no, pb.batch_no, pb.expiry_date, pb.qty
            FROM product_batches pb
            JOIN products p ON pb.product_id = p.id
            WHERE pb.expiry_date <= CAST(SYSDATETIME() AS DATE) AND pb.qty > 0
            ORDER BY pb.expiry_date
        """
        conn = get_connection(); cur = conn.cursor()
        cur.execute(sql); rows = fetchall_dicts(cur)
        conn.close()

        data = []
        for r in rows:
            exp_date = r['expiry_date'].isoformat() if r['expiry_date'] else "Unknown"
            data.append([
                r['name'], r['part_no'], r['batch_no'],
                exp_date, f"{float(r['qty'] or 0):.2f}"
            ])
        
        self._populate_table(data)


class BatchStockReportDialog(BaseReportDialog):
    def __init__(self, parent=None):
        super().__init__(parent, "Batch Wise Stock Report")
        self.setup_ui(["Item Name", "Part No", "Batch No", "Expiry Date", "Qty Remaining"])

    def _load_data(self):
        sql = """
            SELECT p.name, p.part_no, pb.batch_no, pb.expiry_date, pb.qty
            FROM product_batches pb
            JOIN products p ON pb.product_id = p.id
            WHERE pb.qty > 0
            ORDER BY p.name, pb.expiry_date
        """
        conn = get_connection(); cur = conn.cursor()
        cur.execute(sql); rows = fetchall_dicts(cur)
        conn.close()

        data = []
        for r in rows:
            exp_date = r['expiry_date'].isoformat() if r['expiry_date'] else "No Expiry"
            data.append([
                r['name'], r['part_no'], r['batch_no'],
                exp_date, f"{float(r['qty'] or 0):.2f}"
            ])
        
        self._populate_table(data)


class HistoricalValuationReportDialog(BaseReportDialog):
    def __init__(self, parent=None):
        super().__init__(parent, "Valuation Report")
        self.setup_ui(["Item Name", "Part No", "Category", "Quantity", "Cost Price", "Cost Value", "Sale Value"])
        self.date_to.setVisible(False)
        self.date_from.setDate(QDate.currentDate())
        
        filter_lay = self.report_template.filters_layout
        filter_lay.itemAt(0).widget().setText("<b>Target Date:</b>")
        filter_lay.itemAt(2).widget().setVisible(False)
        
        self._load_data()

    def _load_data(self):
        target_date = self.date_from.date().toString("yyyy-MM-dd") + " 23:59:59"
        # We calculate stock from the ground up to guarantee perfect parity with the Ledger.
        # Everything <= target_date is considered.
        sql = """
            WITH AllMovements AS (
                -- 1. Sales (Out)
                SELECT p.part_no, 0 as qty_in, si.qty as qty_out
                FROM sales s
                JOIN sale_items si ON s.id = si.sale_id
                JOIN products p ON si.part_no = p.part_no
                WHERE s.created_at <= ?
                
                UNION ALL
                
                -- 2. Credit Notes (In)
                SELECT p.part_no, cni.qty as qty_in, 0 as qty_out
                FROM credit_notes cn
                JOIN credit_note_items cni ON cn.id = cni.credit_note_id
                JOIN products p ON cni.part_no = p.part_no
                WHERE cn.created_at <= ?
                
                UNION ALL
                
                -- 3. Purchase Invoices / Orders (In)
                SELECT p.part_no, poi.qty as qty_in, 0 as qty_out
                FROM purchase_orders po
                JOIN purchase_order_items poi ON po.id = poi.parent_id
                JOIN products p ON poi.product_id = p.id
                WHERE po.date <= ?
                
                UNION ALL
                
                -- 4. Stock Entries (Opening / Adjs / etc)
                SELECT p.part_no,
                       CASE 
                         WHEN se.doc_no LIKE 'PRET-%' THEN 0 
                         WHEN sei.qty < 0 THEN 0 
                         ELSE sei.qty 
                       END as qty_in, 
                       CASE 
                         WHEN se.doc_no LIKE 'PRET-%' THEN sei.qty 
                         WHEN sei.qty < 0 THEN ABS(sei.qty) 
                         ELSE 0 
                       END as qty_out
                FROM stock_entries se
                JOIN stock_entry_items sei ON se.id = sei.parent_id
                JOIN products p ON sei.product_id = p.id
                WHERE se.date <= ?
            )
            SELECT 
                p.name, p.part_no, p.category, 
                p.cost_price, p.price,
                ISNULL(SUM(m.qty_in), 0) - ISNULL(SUM(m.qty_out), 0) as historic_qty
            FROM products p
            LEFT JOIN AllMovements m ON p.part_no = m.part_no
            WHERE ISNULL(p.active, 1) = 1 AND ISNULL(p.is_template, 0) = 0 AND ISNULL(p.has_variants, 0) = 0
            GROUP BY p.part_no, p.name, p.category, p.cost_price, p.price
            HAVING (ISNULL(SUM(m.qty_in), 0) - ISNULL(SUM(m.qty_out), 0)) != 0
        """
        
        # We need to pass target_date 4 times for the 4 UNION ALL blocks
        params = (target_date, target_date, target_date, target_date)
        
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute(sql, params); rows = fetchall_dicts(cur)
            conn.close()
        except Exception as e:
            # If purchase_orders or something doesn't exist, fallback gracefully
            print(f"Error in Valuation Report SQL: {e}")
            rows = []

        data = []
        total_val = 0
        total_sale_val = 0
        total_qty = 0
        total_cost = 0
        for r in rows:
            historic_qty = float(r['historic_qty'] or 0)
            cost = float(r['cost_price'] or 0)
            price = float(r['price'] or 0)
            val = historic_qty * cost
            sale_val = historic_qty * price
            
            total_val += val
            total_sale_val += sale_val
            total_qty += historic_qty
            total_cost += cost
            
            data.append([
                r['name'], r['part_no'], r['category'] or 'General',
                f"{historic_qty:.2f}", self._format_money(cost), self._format_money(val), self._format_money(sale_val)
            ])
                
        if data:
            data.append(["TOTALS", "", "", f"{total_qty:.2f}", self._format_money(total_cost), self._format_money(total_val), self._format_money(total_sale_val)])
        
        self._populate_table(data)

class StockAdjustmentReportDialog(BaseReportDialog):
    def __init__(self, parent=None, reason="Adjustments", title="Adjustments Report"):
        super().__init__(parent, title)
        self.reason = reason
        self.setup_ui(["Date", "Doc No", "Created By", "Item Code", "Item Name", "Action", "Qty", "Unit Cost", "Variance Value"])

    def _load_data(self):
        d_from = self.date_from.date().toString("yyyy-MM-dd")
        d_to = self.date_to.date().toString("yyyy-MM-dd")
        
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("""
                SELECT se.date, se.doc_no, se.created_by, p.part_no, p.name, 
                       sei.qty, sei.cost_price, sei.selling_price
                FROM stock_entries se
                JOIN stock_entry_items sei ON se.id = sei.parent_id
                JOIN products p ON sei.product_id = p.id
                WHERE se.reference = ? AND CAST(se.date AS DATE) BETWEEN ? AND ?
                ORDER BY se.date DESC, se.id DESC
            """, (self.reason, d_from, d_to))
            rows = fetchall_dicts(cur)
            conn.close()

            data = []
            total_variance = 0.0
            
            for row in rows:
                qty = float(row['qty'] or 0)
                cost = float(row['cost_price'] or 0)
                if cost == 0.0:
                    cost = float(row['selling_price'] or 0)
                var = abs(qty) * cost
                total_variance += var
                action = "Add" if qty > 0 else "Subtract"
                
                date_str = str(row['date']).split(" ")[0] if row['date'] else ""
                data.append([
                    date_str,
                    row['doc_no'] or "",
                    row.get('created_by') or "Admin",
                    row['part_no'] or "",
                    row['name'] or "",
                    action,
                    f"{abs(qty):.2f}",
                    self._format_money(cost),
                    self._format_money(var)
                ])
                
            if data:
                data.append([
                    "TOTALS", "", "", "", "", "", "", self._format_money(total_variance)
                ])
                
            self._populate_table(data)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load report:\n{e}")


class DailyAverageProfitReportDialog(BaseReportDialog):
    def __init__(self, parent=None):
        super().__init__(parent, "Daily Average Profit per Invoice")
        self.setup_ui(["Date", "Total Invoices", "Sales Value", "Total Profit", "Avg Profit / Inv", "Avg Profit %"])
        from PySide6.QtCore import QDate
        today = QDate.currentDate()
        self.date_from.setDate(QDate(today.year(), today.month(), 1))

    def _load_data(self):
        date_from = self.report_template.start_date.date().toString("yyyy-MM-dd") + " 00:00:00"
        date_to = self.report_template.end_date.date().toString("yyyy-MM-dd") + " 23:59:59"
        
        from models.reports import get_daily_profit_trend
        rows = get_daily_profit_trend(date_from, date_to)
        
        data = []
        t_invs = 0; t_sales = 0.0; t_prof = 0.0
        
        for r in rows:
            invs = r["invoices"]
            sales = r["sales"]
            profit = r["profit"]
            avg_prof = r["avg_profit"]
            avg_perc = r["avg_perc"]
            
            t_invs += invs; t_sales += sales; t_prof += profit
            
            data.append([
                str(r["date"]),
                str(invs),
                self._format_money(sales),
                self._format_money(profit),
                self._format_money(avg_prof),
                f"{avg_perc:.2f}%"
            ])
            
        avg_tot_prof = (t_prof / t_invs) if t_invs > 0 else 0.0
        avg_tot_perc = (t_prof / t_sales * 100) if t_sales > 0 else 0.0
        self._populate_table(data)

class ManagementReportDialog(BaseReportDialog):
    def __init__(self, parent=None):
        super().__init__(parent, "Management Report")
        self.setup_ui(["Sales", "Costing", "Gross Profit", "Expenses", "Net Profit", "Total Orders", "Avg Profit / Inv", "Avg Profit %"])

    def _load_data(self):
        date_from = self.report_template.start_date.date().toString("yyyy-MM-dd") + " 00:00:00"
        date_to = self.report_template.end_date.date().toString("yyyy-MM-dd") + " 23:59:59"
        
        from models.reports import get_management_report_data
        r = get_management_report_data(date_from, date_to)
        
        data = [[
            self._format_money(r["sales"]),
            self._format_money(r["costing"]),
            self._format_money(r["gross_profit"]),
            self._format_money(r["expenses"]),
            self._format_money(r["net_profit"]),
            str(r["orders"]),
            self._format_money(r["avg_inv_profit"]),
            f"{r['avg_perc_profit']:.2f}%"
        ]]
        
        self._populate_table(data)
