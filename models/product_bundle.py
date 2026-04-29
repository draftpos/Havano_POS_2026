from database.db import get_connection, fetchall_dicts, fetchone_dict

def get_all_bundles():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, description, sync_status FROM product_bundles ORDER BY name")
    bundles = fetchall_dicts(cur)
    conn.close()
    return bundles

def get_bundle_prices_map():
    """Returns a map of {bundle_name: total_price} summed from bundle_items"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT pb.name, SUM(bi.quantity * bi.rate) as total_price
            FROM product_bundles pb
            JOIN bundle_items bi ON pb.id = bi.bundle_id
            GROUP BY pb.name
        """)
        rows = cur.fetchall()
        return {str(name).upper().strip(): float(price or 0) for name, price in rows}
    except Exception as e:
        print(f"[Bundle] Error fetching bundle prices map: {e}")
        return {}
    finally:
        conn.close()

def get_all_bundles_with_items() -> dict[str, list[dict]]:
    """Returns {bundle_name: [{'item_code': ..., 'quantity': ..., 'rate': ...}, ...]}"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, name FROM product_bundles")
        bundles = cur.fetchall()
        result = {}
        for bid, bname in bundles:
            cur.execute("SELECT item_code, quantity, rate FROM bundle_items WHERE bundle_id = ?", (bid,))
            items = fetchall_dicts(cur)
            result[str(bname).upper().strip()] = items
        return result
    except Exception as e:
        print(f"[Bundle] Error fetching bundles with items: {e}")
        return {}
    finally:
        conn.close()

def get_bundle_by_id(bundle_id):
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT id, name, description, sync_status FROM product_bundles WHERE id = ?", (bundle_id,))
    bundle = fetchone_dict(cur)
    
    if bundle:
        cur.execute("""
            SELECT item_code, quantity, rate, uom
            FROM bundle_items 
            WHERE bundle_id = ?
        """, (bundle_id,))
        bundle['items'] = fetchall_dicts(cur)
    
    conn.close()
    return bundle

def get_bundle_by_name(bundle_name):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, description, sync_status FROM product_bundles WHERE name = ?", (bundle_name,))
    bundle = fetchone_dict(cur)
    
    if bundle:
        cur.execute("""
            SELECT item_code, quantity, rate, uom
            FROM bundle_items 
            WHERE bundle_id = ?
        """, (bundle['id'],))
        bundle['items'] = fetchall_dicts(cur)
    
    conn.close()
    return bundle

def create_bundle(bundle_name, items, description=""):
    """Create bundle with items"""
    if not bundle_name:
        raise ValueError("Bundle name is required")
    if not items:
        raise ValueError("At least one item is required")
    
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        # Insert bundle and get ID
        cur.execute("""
            INSERT INTO product_bundles (name, description, sync_status)
            OUTPUT INSERTED.id
            VALUES (?, ?, 'pending')
        """, (bundle_name.strip(), description.strip()))
        
        # Fetch the inserted ID
        row = cur.fetchone()
        if not row or row[0] is None:
            raise Exception("Failed to get bundle ID after insert")
        
        bundle_id = int(row[0])
        
        # Insert items - CRITICAL: Make sure items are inserted
        inserted_count = 0
        for item in items:
            item_code = item.get('item_code') or item.get('product_part_no', '')
            quantity = float(item.get('quantity', 1))
            rate = float(item.get('rate', item.get('price', 0)))
            uom = item.get('uom', 'Nos')
            
            if not item_code:
                print(f"[Bundle] Skipping item with no code")
                continue
                
            cur.execute("""
                INSERT INTO bundle_items (bundle_id, item_code, quantity, rate, uom)
                VALUES (?, ?, ?, ?, ?)
            """, (bundle_id, item_code, quantity, rate, uom))
            inserted_count += 1
        
        conn.commit()
        print(f"[Bundle] ✅ Created bundle '{bundle_name}' with ID {bundle_id}, {inserted_count} item(s)")
        
        if inserted_count == 0:
            raise Exception("No items were inserted")
            
        return bundle_id
        
    except Exception as e:
        conn.rollback()
        print(f"[Bundle] ❌ Error creating bundle: {e}")
        raise e
    finally:
        conn.close()

def update_bundle(bundle_id, bundle_name, items, description=""):
    """Update existing bundle"""
    if not bundle_id:
        raise ValueError("Bundle ID is required")
    if not bundle_name:
        raise ValueError("Bundle name is required")
    if not items:
        raise ValueError("At least one item is required")
    
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        # Update bundle info
        cur.execute("""
            UPDATE product_bundles 
            SET name = ?, description = ?, sync_status = 'pending'
            WHERE id = ?
        """, (bundle_name.strip(), description.strip(), bundle_id))
        
        # Delete old items
        cur.execute("DELETE FROM bundle_items WHERE bundle_id = ?", (bundle_id,))
        
        # Insert new items
        inserted_count = 0
        for item in items:
            item_code = item.get('item_code') or item.get('product_part_no', '')
            quantity = float(item.get('quantity', 1))
            rate = float(item.get('rate', item.get('price', 0)))
            uom = item.get('uom', 'Nos')
            
            if not item_code:
                print(f"[Bundle] Skipping item with no code")
                continue
                
            cur.execute("""
                INSERT INTO bundle_items (bundle_id, item_code, quantity, rate, uom)
                VALUES (?, ?, ?, ?, ?)
            """, (bundle_id, item_code, quantity, rate, uom))
            inserted_count += 1
        
        conn.commit()
        print(f"[Bundle] ✅ Updated bundle '{bundle_name}' (ID: {bundle_id}) with {inserted_count} item(s)")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"[Bundle] ❌ Error updating bundle: {e}")
        raise e
    finally:
        conn.close()

def delete_bundle(bundle_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM product_bundles WHERE id = ?", (bundle_id,))
    affected = cur.rowcount
    conn.commit()
    conn.close()
    print(f"[Bundle] {'✅' if affected > 0 else '❌'} Deleted bundle ID: {bundle_id}")
    return affected > 0

def update_bundle_sync_status(bundle_id, status):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE product_bundles SET sync_status = ? WHERE id = ?", (status, bundle_id))
    conn.commit()
    conn.close()
    print(f"[Bundle] Updated bundle {bundle_id} sync_status to '{status}'")

def get_bundles_pending_sync():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, description, sync_status FROM product_bundles WHERE sync_status = 'pending'")
    bundles = fetchall_dicts(cur)
    
    for bundle in bundles:
        cur.execute("""
            SELECT item_code, quantity, rate, uom
            FROM bundle_items 
            WHERE bundle_id = ?
        """, (bundle['id'],))
        bundle['items'] = fetchall_dicts(cur)
        
    conn.close()
    return bundles