# =============================================================================
# seed_all.py  —  Seeds all reference data into the database
# Usage:  python seed_all.py
# Run AFTER migrate.py — tables must already exist.
# Safe to re-run — skips anything that already exists.
# =============================================================================

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DIVIDER = "=" * 60

def section(title):
    print(f"\n{DIVIDER}")
    print(f"  {title}")
    print(DIVIDER)

def ok(msg):   print(f"  ✅  {msg}")
def skip(msg): print(f"  ──  SKIP  {msg}")
def err(msg):  print(f"  ❌  ERR   {msg}")


# =============================================================================
# 1. COMPANIES
# =============================================================================
COMPANIES = [
    # (name,                    abbreviation, currency, country)
    ("Havano Trading (Pvt) Ltd", "HVN",        "USD",    "Zimbabwe"),
    ("Havano Retail Store",      "HRS",        "USD",    "Zimbabwe"),
]

def seed_companies():
    section("Companies")
    from models.company import get_all_companies, create_company
    existing = {c["name"] for c in get_all_companies()}
    for name, abbr, curr, country in COMPANIES:
        if name in existing:
            skip(name)
        else:
            try:
                create_company(name, abbr, curr, country)
                ok(f"{name}  ({abbr})")
            except Exception as e:
                err(f"{name} → {e}")


# =============================================================================
# 2. CUSTOMER GROUPS
# =============================================================================
CUSTOMER_GROUPS = [
    # (name,              parent_name or None)
    ("Retail",            None),
    ("Wholesale",         None),
    ("Walk-in",           "Retail"),
    ("Corporate",         "Wholesale"),
    ("VIP",               "Retail"),
]

def seed_customer_groups():
    section("Customer Groups")
    from models.customer_group import get_all_customer_groups, create_customer_group
    existing = {g["name"]: g for g in get_all_customer_groups()}

    for name, parent_name in CUSTOMER_GROUPS:
        if name in existing:
            skip(name); continue
        parent_id = existing[parent_name]["id"] if parent_name and parent_name in existing else None
        try:
            g = create_customer_group(name, parent_id)
            existing[name] = g
            parent_str = f"  (parent: {parent_name})" if parent_name else ""
            ok(f"{name}{parent_str}")
        except Exception as e:
            err(f"{name} → {e}")


# =============================================================================
# 3. WAREHOUSES
# =============================================================================
WAREHOUSES = [
    # (name,             company_name)
    ("Main Warehouse",   "Havano Trading (Pvt) Ltd"),
    ("Retail Floor",     "Havano Retail Store"),
    ("Back Store",       "Havano Trading (Pvt) Ltd"),
]

def seed_warehouses():
    section("Warehouses")
    from models.warehouse import get_all_warehouses, create_warehouse
    from models.company   import get_all_companies
    companies = {c["name"]: c["id"] for c in get_all_companies()}
    existing  = {w["name"] for w in get_all_warehouses()}

    for name, company_name in WAREHOUSES:
        if name in existing:
            skip(name); continue
        cid = companies.get(company_name)
        if not cid:
            err(f"{name} — company '{company_name}' not found"); continue
        try:
            create_warehouse(name, cid)
            ok(f"{name}  (company: {company_name})")
        except Exception as e:
            err(f"{name} → {e}")


# =============================================================================
# 4. COST CENTERS
# =============================================================================
COST_CENTERS = [
    # (name,             company_name)
    ("Sales",            "Havano Trading (Pvt) Ltd"),
    ("Operations",       "Havano Trading (Pvt) Ltd"),
    ("Retail Sales",     "Havano Retail Store"),
]

def seed_cost_centers():
    section("Cost Centers")
    from models.cost_center import get_all_cost_centers, create_cost_center
    from models.company     import get_all_companies
    companies = {c["name"]: c["id"] for c in get_all_companies()}
    existing  = {cc["name"] for cc in get_all_cost_centers()}

    for name, company_name in COST_CENTERS:
        if name in existing:
            skip(name); continue
        cid = companies.get(company_name)
        if not cid:
            err(f"{name} — company '{company_name}' not found"); continue
        try:
            create_cost_center(name, cid)
            ok(f"{name}  (company: {company_name})")
        except Exception as e:
            err(f"{name} → {e}")


# =============================================================================
# 5. PRICE LISTS
# =============================================================================
PRICE_LISTS = [
    # (name,            selling)
    ("Standard Price",  True),
    ("Wholesale Price", True),
    ("VIP Price",       True),
    ("Cost Price",      False),
]

def seed_price_lists():
    section("Price Lists")
    from models.price_list import get_all_price_lists, create_price_list
    existing = {pl["name"] for pl in get_all_price_lists()}

    for name, selling in PRICE_LISTS:
        if name in existing:
            skip(name); continue
        try:
            create_price_list(name, selling)
            ok(f"{name}  ({'Selling' if selling else 'Not Selling'})")
        except Exception as e:
            err(f"{name} → {e}")


# =============================================================================
# 6. CUSTOMERS
# =============================================================================
CUSTOMERS = [
    # name,         group,      type,         trade_name,      phone,          email,                    city,      wh_name,         cc_name,    pl_name
    ("Walk-in",     "Walk-in",  "Individual", "",              "",             "",                       "Harare",  "Retail Floor",  "Retail Sales", "Standard Price"),
    ("John Moyo",   "Retail",   "Individual", "",              "+263712345678","john@example.com",       "Harare",  "Retail Floor",  "Retail Sales", "Standard Price"),
    ("ABC Company", "Corporate","Company",    "ABC Trading",   "+263712000001","abc@example.com",        "Bulawayo","Main Warehouse","Sales",         "Wholesale Price"),
    ("Farai Dube",  "VIP",      "Individual", "",              "+263771234567","farai@example.com",      "Harare",  "Retail Floor",  "Retail Sales", "VIP Price"),
]

def seed_customers():
    section("Customers")
    from models.customer       import get_all_customers, create_customer
    from models.customer_group import get_all_customer_groups
    from models.warehouse      import get_all_warehouses
    from models.cost_center    import get_all_cost_centers
    from models.price_list     import get_all_price_lists

    existing   = {c["customer_name"] for c in get_all_customers()}
    groups     = {g["name"]: g["id"] for g in get_all_customer_groups()}
    warehouses = {w["name"]: w["id"] for w in get_all_warehouses()}
    ccs        = {cc["name"]: cc["id"] for cc in get_all_cost_centers()}
    pls        = {pl["name"]: pl["id"] for pl in get_all_price_lists()}

    for name, group, ctype, trade, phone, email, city, wh, cc, pl in CUSTOMERS:
        if name in existing:
            skip(name); continue
        gid  = groups.get(group)
        wid  = warehouses.get(wh)
        ccid = ccs.get(cc)
        plid = pls.get(pl)
        missing = [k for k,v in [("group",gid),("warehouse",wid),("cost_center",ccid),("price_list",plid)] if not v]
        if missing:
            err(f"{name} — missing: {', '.join(missing)}"); continue
        try:
            create_customer(
                customer_name=name,
                customer_group_id=gid,
                custom_warehouse_id=wid,
                custom_cost_center_id=ccid,
                default_price_list_id=plid,
                customer_type=ctype or None,
                custom_trade_name=trade,
                custom_telephone_number=phone,
                custom_email_address=email,
                custom_city=city,
            )
            ok(f"{name}  ({group})")
        except Exception as e:
            err(f"{name} → {e}")


# =============================================================================
# 7. PRODUCTS  (same as seed.py but combined here)
# =============================================================================
PRODUCTS = [
    # (part_no,   name,                    price,   stock, category)
    ("DK001",  "Coca-Cola 500ml",           1.20,   50,  "Drinks"),
    ("DK002",  "Fanta Orange 500ml",        1.20,   50,  "Drinks"),
    ("DK003",  "Mineral Water 750ml",       0.80,   80,  "Drinks"),
    ("DK004",  "Orange Juice 1L",           2.50,   30,  "Drinks"),
    ("DK005",  "Sprite 500ml",              1.20,   50,  "Drinks"),
    ("DK006",  "Tanganda Tea 250ml",        0.90,   40,  "Drinks"),
    ("DK007",  "Mazoe Orange Crush 2L",     3.50,   30,  "Drinks"),
    ("DK008",  "Energy Drink 330ml",        2.00,   35,  "Drinks"),
    ("GR001",  "Cooking Oil 2L",            3.50,   40,  "Grocery"),
    ("GR002",  "Sugar 2kg",                 2.00,   60,  "Grocery"),
    ("GR003",  "Bread Loaf",                1.50,   25,  "Grocery"),
    ("GR004",  "Rice 5kg",                  6.00,   35,  "Grocery"),
    ("GR005",  "Maize Meal 10kg",           8.00,   20,  "Grocery"),
    ("SN001",  "Lay's Chips 100g",          1.00,   45,  "Snacks"),
    ("SN002",  "Biscuits Assorted 200g",    1.50,   40,  "Snacks"),
    ("SN003",  "Chocolate Bar 50g",         0.90,   60,  "Snacks"),
    ("HH001",  "Washing Powder 1kg",        3.00,   30,  "Household"),
    ("HH002",  "Dish Soap 500ml",           1.80,   35,  "Household"),
    ("HH003",  "Toilet Paper 6-pack",       4.50,   25,  "Household"),
    ("TB001",  "Toothpaste 100ml",          2.20,   30,  "Toiletries"),
    ("TB002",  "Soap Bar 150g",             0.70,   50,  "Toiletries"),
    ("TB003",  "Shampoo 400ml",             3.80,   20,  "Toiletries"),
    ("EL001",  "AA Batteries 4-pack",       2.50,   40,  "Electronics"),
    ("S",      "Service Charge",           50.00,    0,  "Services"),
]

def seed_products():
    section("Products")
    from models.product import get_all_products, create_product
    existing = {p["part_no"] for p in get_all_products()}
    for part_no, name, price, stock, category in PRODUCTS:
        if part_no in existing:
            skip(f"{part_no:<8}  {name}")
        else:
            try:
                p = create_product(part_no, name, price, stock, category)
                ok(f"{p['part_no']:<8}  {p['name']:<30}  ${p['price']:.2f}")
            except Exception as e:
                err(f"{part_no} → {e}")


# =============================================================================
# 8. DEFAULT ADMIN USER
# =============================================================================
def seed_admin():
    section("Admin User")
    from database.db import get_connection
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
    if cur.fetchone()[0]:
        skip("admin user already exists")
        conn.close(); return
    conn.close()
    try:
        from models.user import create_user
        create_user("admin", "admin123", "admin")
        ok("admin user created  (username: admin  /  password: admin123)")
    except Exception as e:
        err(f"admin → {e}")


# =============================================================================
# MAIN
# =============================================================================
if __name__ == "__main__":
    print(f"\n  Havano POS — Full Database Seed")

    steps = [
        ("Companies",       seed_companies),
        ("Customer Groups",  seed_customer_groups),
        ("Warehouses",       seed_warehouses),
        ("Cost Centers",     seed_cost_centers),
        ("Price Lists",      seed_price_lists),
        ("Customers",        seed_customers),
        ("Products",         seed_products),
        ("Admin User",       seed_admin),
    ]

    for label, fn in steps:
        try:
            fn()
        except Exception as e:
            print(f"\n  ❌  {label} failed: {e}")

    print(f"\n{DIVIDER}")
    print("  🎉  Seed complete — run:  py main.py")
    print(f"{DIVIDER}\n")