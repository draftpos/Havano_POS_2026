import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db import get_connection, fetchall_dicts
import json

conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT id, part_no, name, is_template, has_variants, variant_of, attributes FROM products WHERE name LIKE ? OR part_no LIKE ?", ('%Iphone 12%', '%Iphone 12%'))
rows = fetchall_dicts(cur)
print(f"Found {len(rows)} products:")
for r in rows:
    print(json.dumps(r, indent=2, default=str))

# Check any products with variant_of or is_template
cur.execute("SELECT id, part_no, name, is_template, has_variants, variant_of, attributes FROM products WHERE variant_of IS NOT NULL AND variant_of != ''")
variants = fetchall_dicts(cur)
print(f"\nFound {len(variants)} products with variant_of set:")
for v in variants[:10]:
    print(json.dumps(v, indent=2, default=str))
