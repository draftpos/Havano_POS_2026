import sys, os, json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database.db import get_connection, fetchall_dicts, fetchone_dict

conn = get_connection()
cur = conn.cursor()

cur.execute("SELECT * FROM credit_notes WHERE cn_number LIKE '%165228%'")
cn = fetchone_dict(cur)
print("CN:", cn)

cur.execute("SELECT * FROM credit_note_items WHERE credit_note_id = ?", (cn['id'],))
items = fetchall_dicts(cur)
print("Items:", items)

cur.execute("SELECT * FROM sales WHERE id = ?", (cn['original_sale_id'],))
sale = fetchone_dict(cur)
print("Original Sale:", sale)

from services.credit_note_sync_service import _build_cn_payload
from models.company_defaults import get_defaults
defaults = get_defaults()
payload = _build_cn_payload(cn, items, defaults, defaults.get("api_key"), defaults.get("api_secret"), defaults.get("server_url"))
print("\nGenerated CN Payload:")
print(json.dumps(payload, indent=2, default=str))

conn.close()
