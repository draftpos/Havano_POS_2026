from database.db import get_connection, fetchall_dicts

def get_sales_items_report(date_from: str, date_to: str) -> list[dict]:
    """
    Retrieves a summary of items sold within a date range, 
    including their Unit of Measure (UOM).
    """
    conn = get_connection()
    cur  = conn.cursor()
    
    # We join sale_items with products to get the UOM and sales to filter by date
    query = """
        SELECT 
            si.product_name, 
            si.part_no,
            p.uom, 
            SUM(si.qty) AS total_qty, 
            SUM(si.total) AS total_revenue
        FROM sale_items si
        LEFT JOIN products p ON si.part_no = p.part_no
        INNER JOIN sales s ON si.sale_id = s.id
        WHERE CAST(s.created_at AS DATE) BETWEEN ? AND ?
        GROUP BY si.product_name, si.part_no, p.uom
        ORDER BY total_revenue DESC
    """
    
    cur.execute(query, (date_from, date_to))
    rows = fetchall_dicts(cur)
    conn.close()
    return rows