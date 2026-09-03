import codecs
import re

path = r'c:\Users\DELL\New_POS\Havano_POS_2026\services\product_sync_windows_service.py'
content = codecs.open(path, 'r', 'utf-8').read()

# Add _extract_cost_price function
if '_extract_cost_price' not in content:
    func = '''def _extract_cost_price(prices: list, stock_uom: str = "Nos") -> float:
    buying = [p for p in (prices or []) if str(p.get("type", "")).lower() == "buying"]
    if not buying:
        return 0.0
    for p in buying:
        if str(p.get("uom") or "").strip().lower() == stock_uom.strip().lower():
            try:
                return float(p.get("price") or 0)
            except (TypeError, ValueError):
                pass
    for p in buying:
        if "standard buying" in str(p.get("priceName") or "").lower():
            try:
                return float(p.get("price") or 0)
            except (TypeError, ValueError):
                pass
    try:
        return float(buying[0].get("price") or 0)
    except (TypeError, ValueError):
        return 0.0

'''
    content = content.replace('def _extract_selling_price', func + 'def _extract_selling_price')

# update _parse_product
content = re.sub(
    r'price = _extract_selling_price\(p\.get\(\"prices\"\) or \[\], stock_uom\)\n\s+stock = _extract_stock',
    r'price = _extract_selling_price(p.get("prices") or [], stock_uom)\n    cost_price = _extract_cost_price(p.get("prices") or [], stock_uom)\n    stock = _extract_stock',
    content
)

content = re.sub(
    r'\"price\":\s+price,\n\s+\"stock\":\s+stock,',
    r'"price":               price,\n        "cost_price":          cost_price,\n        "stock":               stock,',
    content
)

# update _upsert_parsed_product
content = re.sub(
    r'def _upsert_parsed_product\(cur, conn, p: dict, local_part_nos: set\) -> bool:.*?except Exception as e:\s+log\.warning\(\"\[sync\] DB products row fail for %s: %s\", part_no, e\)',
    r'''def _upsert_parsed_product(cur, conn, p: dict, local_part_nos: set) -> bool:
    part_no           = p["part_no"]
    tax_rate          = p.get("tax_rate",          0.0)
    tax_type          = p.get("tax_type",          "VAT")
    item_tax_template = p.get("item_tax_template", "")
    is_pharm          = p.get("is_pharmacy_product", 0)
    order_flags       = tuple(int(p.get(f"order_{i}", 0) or 0) for i in range(1, 7))
    cost_price        = p.get("cost_price", 0.0)

    is_new = part_no not in local_part_nos

    try:
        if is_new:
            cur.execute(
                """
                INSERT INTO products
                    (part_no, name, price, cost_price, stock, category,
                     uom, conversion_factor,
                     tax_rate, tax_type, item_tax_template,
                     is_pharmacy_product,
                     order_1, order_2, order_3, order_4, order_5, order_6)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1.0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    part_no, p["name"], p["price"], cost_price, p["stock"], p["category"],
                    p.get("uom", "Nos"),
                    tax_rate, tax_type, item_tax_template,
                    is_pharm,
                    *order_flags,
                ),
            )
            local_part_nos.add(part_no)
        else:
            cur.execute(
                """
                UPDATE products
                SET name = ?, price = ?, cost_price = ?, stock = ?, category = CASE WHEN ? <> '' THEN ? ELSE category END,
                    uom = ?, conversion_factor = 1.0,
                    tax_rate = ?, tax_type = ?, item_tax_template = ?,
                    is_pharmacy_product = ?,
                    order_1 = ?, order_2 = ?, order_3 = ?, order_4 = ?, order_5 = ?, order_6 = ?
                WHERE part_no = ?
                """,
                (
                    p["name"], p["price"], cost_price, p["stock"], p["category"], p["category"],
                    p.get("uom", "Nos"),
                    tax_rate, tax_type, item_tax_template,
                    is_pharm,
                    *order_flags,
                    part_no,
                ),
            )
    except Exception as e:
        log.warning("[sync] DB products row fail for %s: %s", part_no, e)''',
    content, flags=re.DOTALL
)

codecs.open(path, 'w', 'utf-8').write(content)
print('Updated product_sync_windows_service.py successfully.')
