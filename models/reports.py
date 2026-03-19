# =============================================================================
# models/reports.py — SQL Server Reporting Logic
# =============================================================================
from database.db import get_connection, fetchall_dicts

def get_sales_items_report(date_from: str, date_to: str) -> list[dict]:
    """
    Requirement 7: Retrieves a summary of items sold within a date range.
    Includes UOM from the products table via a LEFT JOIN to preserve historical data.
    """
    conn = get_connection()
    cur  = conn.cursor()
    
    # We join sale_items with products to get the UOM (Requirement 6) 
    # and join with sales to filter by the transaction date.
    query = """
        SELECT 
            si.product_name, 
            si.part_no,
            COALESCE(p.uom, 'Unit') AS uom, 
            SUM(si.qty) AS total_qty, 
            SUM(si.total) AS total_revenue
        FROM sale_items si
        LEFT JOIN products p ON si.part_no = p.part_no
        INNER JOIN sales s ON si.sale_id = s.id
        WHERE CAST(s.created_at AS DATE) BETWEEN ? AND ?
        GROUP BY si.product_name, si.part_no, p.uom
        ORDER BY total_revenue DESC
    """
    
    try:
        cur.execute(query, (date_from, date_to))
        rows = fetchall_dicts(cur)
    except Exception as e:
        print(f"Error generating sales items report: {e}")
        rows = []
    finally:
        conn.close()
        
    return rows

def get_total_sales_summary(date_from: str, date_to: str) -> dict:
    """Helper for dashboard-style summaries if needed."""
    conn = get_connection()
    cur = conn.cursor()
    query = """
        SELECT 
            COUNT(id) as transaction_count,
            SUM(total) as grand_total
        FROM sales
        WHERE CAST(created_at AS DATE) BETWEEN ? AND ?
    """
    cur.execute(query, (date_from, date_to))
    row = cur.fetchone()
    conn.close()
    return {"count": row[0] or 0, "revenue": float(row[1] or 0.0)}