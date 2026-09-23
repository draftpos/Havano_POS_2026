import sys, os
sys.path.insert(0, os.path.abspath("."))
from database.db import get_connection

conn = get_connection()
c = conn.cursor()
c.execute("SELECT id, part_no, name, category, price, active, is_template, variant_of FROM products WHERE name LIKE ? OR part_no LIKE ?", ('%test%', '%101%'))
print('Test/101 prods:', c.fetchall())

c.execute("SELECT category, COUNT(*) FROM products GROUP BY category")
print('Categories in products:', c.fetchall())

c.execute("SELECT COUNT(*) FROM products WHERE (active = 1 OR active IS NULL)")
print('Active products count:', c.fetchone())

c.execute("SELECT COUNT(*) FROM products WHERE (variant_of IS NULL OR variant_of = '')")
print('Non-variant products count:', c.fetchone())

conn.close()
