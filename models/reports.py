# =============================================================================
# models/reports.py - SQL Server Reporting Logic
# =============================================================================
from database.db import get_connection, fetchall_dicts, fetchone_dict

def get_sales_items_report(date_from: str, date_to: str) -> list[dict]:
    """
    Requirement 7: Retrieves a summary of items sold within a date range.
    Includes UOM from the products table via a LEFT JOIN to preserve historical data.
    """
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
    except:
        pass
    
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

def get_consumed_bundle_items_report(date_from: str, date_to: str) -> list[dict]:
    """
    Retrieves individual component items consumed as part of product bundles sold within a date range.
    Returns: [{'parent_bundle': '...', 'component_part_no': '...', 'component_name': '...', 'consumed_qty': ...}]
    """
    import json
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
    except:
        pass
    
    query = """
        SELECT 
            si.part_no AS parent_part_no,
            si.product_name AS parent_name,
            p.bundle_lines,
            SUM(si.qty) AS total_bundle_qty
        FROM sale_items si
        INNER JOIN sales s ON si.sale_id = s.id
        INNER JOIN products p ON si.part_no = p.part_no
        WHERE CAST(s.created_at AS DATE) BETWEEN ? AND ?
          AND p.is_product_bundle = 1
        GROUP BY si.part_no, si.product_name, p.bundle_lines
    """
    
    consumed = {}
    try:
        cur.execute(query, (date_from, date_to))
        rows = fetchall_dicts(cur)
        for row in rows:
            parent = f"{row['parent_part_no']} - {row['parent_name']}"
            b_qty = float(row['total_bundle_qty'] or 0)
            lines_str = row['bundle_lines'] or "[]"
            try:
                lines = json.loads(lines_str)
                for line in lines:
                    c_code = (line.get('item_code') or line.get('product_code') or line.get('code') or line.get('part_no') or "").upper().strip()
                    c_name = line.get('item_name') or line.get('product_name') or line.get('name') or ""
                    c_qty_per_bundle = float(line.get('quantity') or 0)
                    total_consumed = b_qty * c_qty_per_bundle
                    
                    if total_consumed > 0:
                        key = (parent, c_code, c_name)
                        if key in consumed:
                            consumed[key] += total_consumed
                        else:
                            consumed[key] = total_consumed
            except Exception as e:
                print(f"Error parsing bundle_lines for {parent}: {e}")
                
        costs = {}
        if consumed:
            component_codes = list({k[1] for k in consumed.keys()})
            if component_codes:
                placeholders = ",".join("?" for _ in component_codes)
                cur.execute(f"SELECT part_no, name, cost_price, price FROM products WHERE part_no IN ({placeholders})", component_codes)
                costs = {row['part_no']: (row['name'], float(row['cost_price'] or 0), float(row['price'] or 0)) for row in fetchall_dicts(cur)}

    except Exception as e:
        print(f"Error generating consumed bundle items report: {e}")
    finally:
        conn.close()
        
    result = []
    for (parent, c_code, c_name), qty in consumed.items():
        db_name, c_cost, c_price = costs.get(c_code, ("", 0.0, 0.0))
        final_name = c_name if c_name else db_name
        total_price = qty * c_price
        total_cost = qty * c_cost
        profit = total_price - total_cost
        profit_perc = (profit / total_price * 100) if total_price > 0 else 0.0
        
        result.append({
            "parent_bundle": parent,
            "component_part_no": c_code,
            "component_name": final_name,
            "consumed_qty": qty,
            "total_cost": total_cost,
            "selling_price": total_price,
            "profit": profit,
            "profit_perc": profit_perc
        })
        
    # Sort by parent bundle then component code
    result.sort(key=lambda x: (x["parent_bundle"], x["component_part_no"]))
    return result

def get_total_sales_summary(date_from: str, date_to: str) -> dict:
    """Helper for dashboard-style summaries if needed."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
    except:
        pass
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

def get_daily_profit_trend(date_from: str, date_to: str) -> list[dict]:
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
    except: pass
    
    query = """
        SELECT 
            CAST(s.created_at AS DATE) as ddate,
            COUNT(s.id) as num_invoices,
            COALESCE(SUM(s.total), 0) as total_sales,
            (SELECT COALESCE(SUM(si.qty * si.cost_price), 0) 
             FROM sale_items si WHERE si.sale_id IN 
             (SELECT id FROM sales s2 WHERE CAST(s2.created_at AS DATE) = CAST(s.created_at AS DATE))) as total_cost
        FROM sales s
        WHERE CAST(s.created_at AS DATE) BETWEEN ? AND ?
        GROUP BY CAST(s.created_at AS DATE)
        ORDER BY CAST(s.created_at AS DATE) DESC
    """
    cur.execute(query, (date_from, date_to))
    rows = fetchall_dicts(cur)
    conn.close()
    
    res = []
    for r in rows:
        sales = float(r['total_sales'])
        cost = float(r['total_cost'])
        profit = sales - cost
        invs = int(r['num_invoices'])
        avg_profit = profit / invs if invs > 0 else 0.0
        avg_perc = (profit / sales * 100) if sales > 0 else 0.0
        res.append({
            "date": r['ddate'],
            "invoices": invs,
            "sales": sales,
            "profit": profit,
            "avg_profit": avg_profit,
            "avg_perc": avg_perc
        })
    return res

def get_management_report_data(date_from: str, date_to: str) -> dict:
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
    except: pass
    
    # 1. Sales and COGS
    cur.execute("""
        SELECT 
            COALESCE(SUM(s.total), 0) as sales,
            COUNT(s.id) as orders,
            (SELECT COALESCE(SUM(si.qty * si.cost_price), 0) 
             FROM sale_items si 
             INNER JOIN sales s2 ON s2.id = si.sale_id
             WHERE CAST(s2.created_at AS DATE) BETWEEN ? AND ?) as costing
        FROM sales s
        WHERE CAST(s.created_at AS DATE) BETWEEN ? AND ?
    """, (date_from, date_to, date_from, date_to))
    r1 = fetchone_dict(cur)
    sales = float(r1['sales'] if r1 else 0)
    orders = int(r1['orders'] if r1 else 0)
    costing = float(r1['costing'] if r1 else 0)
    
    # 2. Expenses
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) as exp
        FROM expenses
        WHERE CAST(created_at AS DATE) BETWEEN ? AND ?
    """, (date_from, date_to))
    r2 = cur.fetchone()
    expenses = float(r2[0] if r2 else 0)
    
    # 3. Cash on hand by method
    cur.execute("""
        SELECT method, COALESCE(SUM(total), 0) as val
        FROM sales
        WHERE CAST(created_at AS DATE) BETWEEN ? AND ?
        GROUP BY method
    """, (date_from, date_to))
    method_rows = fetchall_dicts(cur)
    methods = {r['method']: float(r['val']) for r in method_rows}
    
    # 4. Top 10 Profitable Items
    cur.execute("""
        SELECT TOP 10 
            si.product_name, 
            SUM((si.price - si.cost_price) * si.qty) as item_profit
        FROM sale_items si
        INNER JOIN sales s ON s.id = si.sale_id
        WHERE CAST(s.created_at AS DATE) BETWEEN ? AND ?
        GROUP BY si.product_name
        ORDER BY item_profit DESC
    """, (date_from, date_to))
    top_profit = fetchall_dicts(cur)
    
    # 5. Top 10 Sales (by qty)
    cur.execute("""
        SELECT TOP 10 
            si.product_name, 
            SUM(si.qty) as item_qty
        FROM sale_items si
        INNER JOIN sales s ON s.id = si.sale_id
        WHERE CAST(s.created_at AS DATE) BETWEEN ? AND ?
        GROUP BY si.product_name
        ORDER BY item_qty DESC
    """, (date_from, date_to))
    top_sales = fetchall_dicts(cur)
    
    conn.close()
    
    gross_profit = sales - costing
    net_profit = gross_profit - expenses
    avg_inv_profit = (gross_profit / orders) if orders > 0 else 0.0
    avg_perc_profit = (gross_profit / sales * 100) if sales > 0 else 0.0
    
    return {
        "sales": sales,
        "costing": costing,
        "gross_profit": gross_profit,
        "expenses": expenses,
        "net_profit": net_profit,
        "orders": orders,
        "avg_inv_profit": avg_inv_profit,
        "avg_perc_profit": avg_perc_profit,
        "methods": methods,
        "top_profit": top_profit,
        "top_sales": top_sales
    }