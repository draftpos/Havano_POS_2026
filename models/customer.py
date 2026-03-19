# models/customer.py
from database.db import get_connection, fetchall_dicts, fetchone_dict

_SELECT = """
    SELECT cu.id, cu.customer_name, cu.customer_group_id,
           cg.name AS customer_group_name, cu.customer_type,
           cu.custom_trade_name, cu.custom_telephone_number,
           cu.custom_email_address, cu.custom_city, cu.custom_house_no,
           cu.custom_warehouse_id, w.name AS warehouse_name,
           cu.custom_cost_center_id, cc.name AS cost_center_name,
           cu.default_price_list_id, pl.name AS price_list_name,
           cu.balance, cu.outstanding_amount, cu.loyalty_points
    FROM customers cu
    LEFT JOIN customer_groups cg ON cg.id = cu.customer_group_id
    LEFT JOIN warehouses       w  ON w.id  = cu.custom_warehouse_id
    LEFT JOIN cost_centers     cc ON cc.id = cu.custom_cost_center_id
    LEFT JOIN price_lists      pl ON pl.id = cu.default_price_list_id
"""

def get_all_customers() -> list[dict]:
    conn = get_connection(); cur = conn.cursor()
    cur.execute(_SELECT + " ORDER BY cu.customer_name")
    rows = fetchall_dicts(cur); conn.close()
    return [_to_dict(r) for r in rows]

def search_customers(query: str) -> list[dict]:
    like = f"%{query}%"
    conn = get_connection(); cur = conn.cursor()
    cur.execute(_SELECT +
        " WHERE cu.customer_name LIKE ? OR cu.custom_trade_name LIKE ?"
        " OR cu.custom_telephone_number LIKE ? ORDER BY cu.customer_name",
        (like, like, like))
    rows = fetchall_dicts(cur); conn.close()
    return [_to_dict(r) for r in rows]

def get_customer_by_id(customer_id: int) -> dict | None:
    conn = get_connection(); cur = conn.cursor()
    cur.execute(_SELECT + " WHERE cu.id = ?", (customer_id,))
    row = fetchone_dict(cur); conn.close()
    return _to_dict(row) if row else None

def get_customer_by_name(name: str) -> dict | None:
    conn = get_connection(); cur = conn.cursor()
    cur.execute(_SELECT + " WHERE cu.customer_name = ?", (name,))
    row = fetchone_dict(cur); conn.close()
    return _to_dict(row) if row else None

def upsert_from_frappe(c: dict):
    """
    Handles payload from Frappe. Matches existing customers by name.
    Strictly follows 'No Fake Data' - if a name lookup fails, the ID remains NULL.
    """
    conn = get_connection()
    cur = conn.cursor()

    # 1. Resolve Foreign Key IDs by Name (returning None if not found)
    def find_id(table, name):
        if not name: return None
        cur.execute(f"SELECT id FROM {table} WHERE name = ?", (name,))
        row = cur.fetchone()
        return row[0] if row else None

    warehouse_id = find_id("warehouses", c.get("custom_warehouse"))
    cost_center_id = find_id("cost_centers", c.get("custom_cost_center"))
    price_list_id = find_id("price_lists", c.get("default_price_list"))
    group_id = find_id("customer_groups", c.get("customer_group"))

    # 2. Check existence
    cur.execute("SELECT id FROM customers WHERE customer_name = ?", (c.get("customer_name"),))
    existing = cur.fetchone()

    if existing:
        # UPDATE: We use ISNULL(?, col) for IDs to prevent overwriting existing 
        # local data if the Frappe payload is missing the field.
        cur.execute("""
            UPDATE customers SET
                customer_type = ?, 
                customer_group_id = ISNULL(?, customer_group_id),
                custom_warehouse_id = ISNULL(?, custom_warehouse_id), 
                custom_cost_center_id = ISNULL(?, custom_cost_center_id), 
                default_price_list_id = ISNULL(?, default_price_list_id),
                balance = ?, 
                outstanding_amount = ?, 
                loyalty_points = ?
            WHERE customer_name = ?
        """, (
            c.get("customer_type"), group_id, warehouse_id, cost_center_id, price_list_id,
            c.get("balance", 0), c.get("outstanding_amount", 0), c.get("loyalty_points", 0),
            c.get("customer_name")
        ))
    else:
        # INSERT: New record from Frappe.
        cur.execute("""
            INSERT INTO customers (
                customer_name, customer_type, customer_group_id,
                custom_warehouse_id, custom_cost_center_id, default_price_list_id,
                balance, outstanding_amount, loyalty_points
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            c.get("customer_name"), c.get("customer_type"), group_id,
            warehouse_id, cost_center_id, price_list_id,
            c.get("balance", 0), c.get("outstanding_amount", 0), c.get("loyalty_points", 0)
        ))
    
    conn.commit()
    conn.close()

def create_customer(customer_name: str, customer_group_id: int,
                    custom_warehouse_id: int, custom_cost_center_id: int,
                    default_price_list_id: int, **kwargs) -> dict:
    """Manual creation helper."""
    conn = get_connection(); cur = conn.cursor()
    cur.execute("""
        INSERT INTO customers (
            customer_name, customer_group_id, customer_type,
            custom_trade_name, custom_telephone_number, custom_email_address,
            custom_city, custom_house_no,
            custom_warehouse_id, custom_cost_center_id, default_price_list_id
        ) OUTPUT INSERTED.id VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (customer_name.strip(), customer_group_id, kwargs.get("customer_type"),
          kwargs.get("custom_trade_name", ""), kwargs.get("custom_telephone_number", ""), 
          kwargs.get("custom_email_address", ""), kwargs.get("custom_city", ""), 
          kwargs.get("custom_house_no", ""),
          custom_warehouse_id, custom_cost_center_id, default_price_list_id))
    new_id = int(cur.fetchone()[0]); conn.commit(); conn.close()
    return get_customer_by_id(new_id)

def update_customer(customer_id: int, **kwargs) -> dict | None:
    """Manual update helper."""
    c = get_customer_by_id(customer_id)
    if not c: return None
    
    conn = get_connection(); cur = conn.cursor()
    cur.execute("""
        UPDATE customers SET
            customer_name=?, customer_group_id=?, customer_type=?,
            custom_trade_name=?, custom_telephone_number=?, custom_email_address=?,
            custom_city=?, custom_house_no=?,
            custom_warehouse_id=?, custom_cost_center_id=?, default_price_list_id=?
        WHERE id=?
    """, (kwargs.get("customer_name", c["customer_name"]), 
          kwargs.get("customer_group_id", c["customer_group_id"]), 
          kwargs.get("customer_type", c["customer_type"]),
          kwargs.get("custom_trade_name", c["custom_trade_name"]), 
          kwargs.get("custom_telephone_number", c["custom_telephone_number"]), 
          kwargs.get("custom_email_address", c["custom_email_address"]),
          kwargs.get("custom_city", c["custom_city"]), 
          kwargs.get("custom_house_no", c["custom_house_no"]),
          kwargs.get("custom_warehouse_id", c["custom_warehouse_id"]), 
          kwargs.get("custom_cost_center_id", c["custom_cost_center_id"]),
          kwargs.get("default_price_list_id", c["default_price_list_id"]), 
          customer_id))
    conn.commit(); conn.close()
    return get_customer_by_id(customer_id)

def delete_customer(customer_id: int) -> bool:
    conn = get_connection(); cur = conn.cursor()
    cur.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
    affected = cur.rowcount; conn.commit(); conn.close()
    return affected > 0

def _to_dict(row: dict) -> dict | None:
    if not row: return None
    # Standardize output: converts None to empty strings or 0.0 for safety
    d = dict(row)
    for k, v in d.items():
        if v is None:
            if k in ['balance', 'outstanding_amount', 'loyalty_points', 'id', 'customer_group_id', 
                     'custom_warehouse_id', 'custom_cost_center_id', 'default_price_list_id']:
                d[k] = 0 if 'id' not in k else None
            else:
                d[k] = ""
    return d