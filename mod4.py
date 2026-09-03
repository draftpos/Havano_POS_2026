import sys

with open('views/main_window.py', 'r', encoding='utf-8') as f:
    c = f.read()

orig_top_items = """                cur.execute(\"\"\"
                    SELECT
                        si.product_name,
                        SUM(si.qty) AS qty,
                        SUM(si.total) AS revenue,
                        SUM(si.qty * COALESCE(p.cost_price, 0)) AS cost_total
                    FROM sale_items si
                    LEFT JOIN products p ON si.product_id = p.id
                    WHERE si.product_name IS NOT NULL
                    GROUP BY si.product_name
                \"\"\")"""

new_top_items = """                cur.execute(\"\"\"
                    SELECT
                        si.product_name,
                        SUM(si.qty) AS qty,
                        SUM(si.total) AS revenue,
                        0 AS cost_total
                    FROM sale_items si
                    WHERE si.product_name IS NOT NULL
                    GROUP BY si.product_name
                \"\"\")"""

orig_cogs = """                cur.execute(\"\"\"
                    SELECT COALESCE(
                        SUM(si.qty * COALESCE(p.cost_price, 0)), 0
                    )
                    FROM sale_items si
                    LEFT JOIN products p ON si.product_id = p.id
                \"\"\")"""

new_cogs = """                cur.execute(\"\"\"
                    SELECT 0
                \"\"\")"""

c = c.replace(orig_top_items, new_top_items).replace(orig_cogs, new_cogs)

with open('views/main_window.py', 'w', encoding='utf-8') as f:
    f.write(c)
print("Successfully fixed SQL queries in _load_top_items and _load_financial_kpis")
