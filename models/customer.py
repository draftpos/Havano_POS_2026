# models/customer.py
from database.db import get_connection, fetchall_dicts, fetchone_dict

_SELECT = """
    SELECT cu.id, cu.customer_name, cu.customer_group_id,
           cg.name AS customer_group_name, cu.customer_type,
           cu.custom_trade_name, cu.custom_telephone_number,
           cu.custom_email_address, cu.custom_city, cu.custom_house_no,
           cu.custom_warehouse_id, w.name AS warehouse_name,
           cu.custom_cost_center_id, cc.name AS cost_center_name,
           cu.default_price_list_id, pl.name AS price_list_name
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


def create_customer(customer_name: str, customer_group_id: int,
                    custom_warehouse_id: int, custom_cost_center_id: int,
                    default_price_list_id: int, customer_type: str = None,
                    custom_trade_name: str = "", custom_telephone_number: str = "",
                    custom_email_address: str = "", custom_city: str = "",
                    custom_house_no: str = "") -> dict:
    _validate(customer_group_id, custom_warehouse_id, custom_cost_center_id, default_price_list_id)
    conn = get_connection(); cur = conn.cursor()
    cur.execute("""
        INSERT INTO customers (
            customer_name, customer_group_id, customer_type,
            custom_trade_name, custom_telephone_number, custom_email_address,
            custom_city, custom_house_no,
            custom_warehouse_id, custom_cost_center_id, default_price_list_id
        ) OUTPUT INSERTED.id VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (customer_name.strip(), customer_group_id, customer_type,
          custom_trade_name, custom_telephone_number, custom_email_address,
          custom_city, custom_house_no,
          custom_warehouse_id, custom_cost_center_id, default_price_list_id))
    new_id = int(cur.fetchone()[0]); conn.commit(); conn.close()
    return get_customer_by_id(new_id)


def update_customer(customer_id: int, **kwargs) -> dict | None:
    c = get_customer_by_id(customer_id)
    if not c: return None
    fields = {
        "customer_name":           kwargs.get("customer_name",           c["customer_name"]),
        "customer_group_id":       kwargs.get("customer_group_id",       c["customer_group_id"]),
        "customer_type":           kwargs.get("customer_type",           c["customer_type"]),
        "custom_trade_name":       kwargs.get("custom_trade_name",       c["custom_trade_name"]),
        "custom_telephone_number": kwargs.get("custom_telephone_number", c["custom_telephone_number"]),
        "custom_email_address":    kwargs.get("custom_email_address",    c["custom_email_address"]),
        "custom_city":             kwargs.get("custom_city",             c["custom_city"]),
        "custom_house_no":         kwargs.get("custom_house_no",         c["custom_house_no"]),
        "custom_warehouse_id":     kwargs.get("custom_warehouse_id",     c["custom_warehouse_id"]),
        "custom_cost_center_id":   kwargs.get("custom_cost_center_id",   c["custom_cost_center_id"]),
        "default_price_list_id":   kwargs.get("default_price_list_id",   c["default_price_list_id"]),
    }
    _validate(fields["customer_group_id"], fields["custom_warehouse_id"],
              fields["custom_cost_center_id"], fields["default_price_list_id"])
    conn = get_connection(); cur = conn.cursor()
    cur.execute("""
        UPDATE customers SET
            customer_name=?, customer_group_id=?, customer_type=?,
            custom_trade_name=?, custom_telephone_number=?, custom_email_address=?,
            custom_city=?, custom_house_no=?,
            custom_warehouse_id=?, custom_cost_center_id=?, default_price_list_id=?
        WHERE id=?
    """, (fields["customer_name"], fields["customer_group_id"], fields["customer_type"],
          fields["custom_trade_name"], fields["custom_telephone_number"], fields["custom_email_address"],
          fields["custom_city"], fields["custom_house_no"],
          fields["custom_warehouse_id"], fields["custom_cost_center_id"],
          fields["default_price_list_id"], customer_id))
    conn.commit(); conn.close()
    return get_customer_by_id(customer_id)


def delete_customer(customer_id: int) -> bool:
    conn = get_connection(); cur = conn.cursor()
    cur.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
    affected = cur.rowcount; conn.commit(); conn.close()
    return affected > 0


def _validate(customer_group_id, warehouse_id, cost_center_id, price_list_id):
    from models.customer_group import get_customer_group_by_id
    from models.warehouse       import get_warehouse_by_id
    from models.cost_center     import get_cost_center_by_id
    from models.price_list      import get_price_list_by_id
    if not get_customer_group_by_id(customer_group_id):
        raise ValueError(f"Customer group {customer_group_id} does not exist.")
    w = get_warehouse_by_id(warehouse_id)
    if not w: raise ValueError(f"Warehouse {warehouse_id} does not exist.")
    cc = get_cost_center_by_id(cost_center_id)
    if not cc: raise ValueError(f"Cost center {cost_center_id} does not exist.")
    if w["company_id"] != cc["company_id"]:
        raise ValueError("Warehouse and Cost Center must belong to the same company.")
    if not get_price_list_by_id(price_list_id):
        raise ValueError(f"Price list {price_list_id} does not exist.")


def _to_dict(row: dict) -> dict | None:
    if not row: return None
    return {
        "id":                      row["id"],
        "customer_name":           row["customer_name"]           or "",
        "customer_group_id":       row["customer_group_id"],
        "customer_group_name":     row.get("customer_group_name") or "",
        "customer_type":           row.get("customer_type")       or "",
        "custom_trade_name":       row.get("custom_trade_name")   or "",
        "custom_telephone_number": row.get("custom_telephone_number") or "",
        "custom_email_address":    row.get("custom_email_address")    or "",
        "custom_city":             row.get("custom_city")         or "",
        "custom_house_no":         row.get("custom_house_no")     or "",
        "custom_warehouse_id":     row.get("custom_warehouse_id"),
        "warehouse_name":          row.get("warehouse_name")      or "",
        "custom_cost_center_id":   row.get("custom_cost_center_id"),
        "cost_center_name":        row.get("cost_center_name")    or "",
        "default_price_list_id":   row.get("default_price_list_id"),
        "price_list_name":         row.get("price_list_name")     or "",
    }
