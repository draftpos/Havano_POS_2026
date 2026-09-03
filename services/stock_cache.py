# =============================================================================
# services/stock_cache.py - Fast JSON & Memory Stock Cache for Havano POS
# =============================================================================
import os
import json
import threading
from datetime import datetime

CACHE_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "stock_cache.json")
_CACHE_LOCK = threading.Lock()

_MEMORY_CACHE = {
    "by_id": {},
    "by_part_no": {},
    "by_name": {},
    "warehouse_id": None,
    "last_updated": None
}

def init_stock_cache(warehouse_id: int = None) -> dict:
    """
    Loads all product stock levels from the database into memory and dumps
    them to stock_cache.json for fast O(1) checks.
    """
    global _MEMORY_CACHE
    try:
        from database.db import get_connection, fetchall_dicts
        from services.sync_service import _ensure_product_schema
        conn = get_connection()
        cur = conn.cursor()
        try:
            _ensure_product_schema(cur)
        except Exception:
            pass
        
        stock_expr = "p.stock"
        join_clause = ""
        if warehouse_id:
            stock_expr = "COALESCE(pws.stock, 0) AS stock"
            join_clause = f"LEFT JOIN product_warehouse_stock pws ON p.id = pws.product_id AND pws.warehouse_id = {int(warehouse_id)}"
            
        sql = f"""
            SELECT p.id, p.part_no, p.name, {stock_expr},
                   COALESCE(p.track_stock, 1) AS track_stock,
                   COALESCE(p.is_product_bundle, 0) AS is_product_bundle,
                   p.category
            FROM products p WITH (NOLOCK)
            {join_clause}
            WHERE COALESCE(p.active, 1) = 1
        """
        cur.execute(sql)
        rows = fetchall_dicts(cur)
        conn.close()

        by_id = {}
        by_part_no = {}
        by_name = {}

        for r in rows:
            p_id = str(r.get("id"))
            p_no = str(r.get("part_no") or "").upper().strip()
            p_name = str(r.get("name") or "").upper().strip()
            stock_val = float(r.get("stock") if r.get("stock") is not None else 0.0)
            meta = {
                "stock": stock_val,
                "track_stock": bool(r.get("track_stock", True)),
                "is_bundle": bool(r.get("is_product_bundle", False)),
                "category": r.get("category") or "",
            }

            if p_id:
                by_id[p_id] = meta
            if p_no:
                by_part_no[p_no] = meta
            if p_name:
                by_name[p_name] = meta

        new_cache = {
            "by_id": by_id,
            "by_part_no": by_part_no,
            "by_name": by_name,
            "warehouse_id": warehouse_id,
            "last_updated": datetime.now().isoformat()
        }

        with _CACHE_LOCK:
            _MEMORY_CACHE = new_cache

        _save_cache_to_disk(new_cache)
        return _MEMORY_CACHE
    except Exception as e:
        print(f"[StockCache] Error initializing stock cache: {e}")
        return _load_cache_from_disk()

def _save_cache_to_disk(data: dict):
    """Saves cache dictionary to stock_cache.json."""
    try:
        with open(CACHE_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"[StockCache] Error writing stock_cache.json: {e}")

def _load_cache_from_disk() -> dict:
    """Fallback: loads stock_cache.json from disk if DB is unavailable."""
    global _MEMORY_CACHE
    if os.path.exists(CACHE_FILE_PATH):
        try:
            with open(CACHE_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                with _CACHE_LOCK:
                    _MEMORY_CACHE = data
                return data
        except Exception as e:
            print(f"[StockCache] Error reading stock_cache.json: {e}")
    return _MEMORY_CACHE

def get_cached_product_info(product_id=None, part_no=None, name=None) -> dict | None:
    """
    Fast O(1) in-memory lookup for stock, track_stock, is_bundle, category.
    Zero DB latency!
    """
    with _CACHE_LOCK:
        if product_id and str(product_id) in _MEMORY_CACHE.get("by_id", {}):
            return _MEMORY_CACHE["by_id"][str(product_id)]
        
        if part_no and str(part_no).upper().strip() in _MEMORY_CACHE.get("by_part_no", {}):
            return _MEMORY_CACHE["by_part_no"][str(part_no).upper().strip()]

        if name and str(name).upper().strip() in _MEMORY_CACHE.get("by_name", {}):
            return _MEMORY_CACHE["by_name"][str(name).upper().strip()]

    return None

def update_cached_stock(product_id=None, part_no=None, delta: float = 0.0, new_stock: float = None):
    """
    Updates the cached stock value after sales or stock adjustments.
    """
    with _CACHE_LOCK:
        info = None
        if product_id and str(product_id) in _MEMORY_CACHE.get("by_id", {}):
            info = _MEMORY_CACHE["by_id"][str(product_id)]
        elif part_no and str(part_no).upper().strip() in _MEMORY_CACHE.get("by_part_no", {}):
            info = _MEMORY_CACHE["by_part_no"][str(part_no).upper().strip()]

        if info:
            if new_stock is not None:
                info["stock"] = float(new_stock)
            else:
                info["stock"] = float(info.get("stock", 0.0)) + delta

        _MEMORY_CACHE["last_updated"] = datetime.now().isoformat()
        data_to_save = dict(_MEMORY_CACHE)

    threading.Thread(target=_save_cache_to_disk, args=(data_to_save,), daemon=True).start()
