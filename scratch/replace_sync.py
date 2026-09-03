import codecs
import re

path = r'c:\Users\DELL\New_POS\Havano_POS_2026\services\sync_service.py'
content = codecs.open(path, 'r', 'utf-8').read()

new_content = re.sub(
    r'def _upsert_parsed_product\(cur, conn, p: dict, local_part_nos: set\) -> bool:.*?except Exception as e:\s+log\.warning\(\"\[sync\] DB products row fail for %s: %s\", part_no, e\)',
    r'''def _upsert_parsed_product(cur, conn, p: dict, local_part_nos: set) -> bool:
    """
    Upsert one fully-parsed product dict (from _parse_product) to the DB.
    Returns True if a new row was inserted, False if updated.
    """
    part_no           = p["part_no"]
    tax_rate          = p.get("tax_rate",          0.0)
    tax_type          = p.get("tax_type",          "VAT")
    item_tax_template = p.get("item_tax_template", "")
    is_pharm          = p.get("is_pharmacy_product", 0)
    order_flags       = tuple(int(p.get(f"order_{i}", 0) or 0) for i in range(1, 7))
    cost_price        = p.get("cost_price", 0.0)

    is_new = part_no not in local_part_nos

    # ── INSERT or UPDATE products row ──────────────────────────────────
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
            log.debug(
                "[sync] Inserted: %s  tax_rate=%.4f  tax_type=%s  orders=%s",
                part_no, tax_rate, tax_type, order_flags,
            )
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
            log.debug(
                "[sync] Updated: %s  tax_rate=%.4f  tax_type=%s  orders=%s",
                part_no, tax_rate, tax_type, order_flags,
            )
    except Exception as e:
        log.warning("[sync] DB products row fail for %s: %s", part_no, e)''',
    content, flags=re.DOTALL
)

codecs.open(path, 'w', 'utf-8').write(new_content)
