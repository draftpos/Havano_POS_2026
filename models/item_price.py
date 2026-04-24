"""
models/item_price.py
────────────────────
Read-side API for the `item_prices` cache.

The cache is populated by `services/product_sync_windows_service.py` from the
`prices` array returned by the ERPNext app's `get_products` endpoint (see
`havano_pos_integration/api.py`). One row per (part_no, price_list, uom,
price_type).

Lookup model — **no fallbacks**. This matches the user's requirement:

    "If there is no pricelist leave it as zero and we can't sell zero products."

If a given (item, price_list) combination has no row, callers get `None`
from `get_price()` / `0.0` from `get_prices_map()`. The POS should refuse
to add a zero-priced item to the cart and tell the cashier why.

Price list names are carried end-to-end as their ERPNext `priceName` string
(e.g. "Standard Selling", "Retail USD"). Callers holding a `price_list_id`
from the `customers` table should resolve to name via `price_lists.name`
first — or use the `_id` helpers below which do the JOIN for you.
"""

from __future__ import annotations

import logging
from typing import Optional

from database.db import get_connection

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core lookups (by price-list NAME)
# ---------------------------------------------------------------------------

def get_price(
    part_no: str,
    price_list: str,
    uom: Optional[str] = None,
    price_type: str = "selling",
) -> Optional[float]:
    """
    Return the cached rate for (part_no, price_list[, uom]) or None.

    When `uom` is omitted we try the item's stock UOM first, then any row
    for that price list. This keeps callers simple — they rarely know the
    uom up-front, but the underlying data often has just one row anyway.
    """
    part_no    = (part_no    or "").strip().upper()
    price_list = (price_list or "").strip()
    if not part_no or not price_list:
        return None

    conn = get_connection()
    cur  = conn.cursor()
    try:
        if uom:
            cur.execute("""
                SELECT TOP 1 price
                FROM   item_prices
                WHERE  part_no = ? AND price_list = ?
                  AND  uom = ? AND price_type = ?
            """, (part_no, price_list, uom.strip(), price_type))
            row = cur.fetchone()
            if row:
                return float(row[0] or 0)

        # No uom supplied OR uom-specific lookup missed — pick any row. We
        # order by uom='nos' first since that's the default the backend
        # fills in when UOM is blank.
        cur.execute("""
            SELECT TOP 1 price
            FROM   item_prices
            WHERE  part_no = ? AND price_list = ? AND price_type = ?
            ORDER  BY CASE WHEN uom = 'nos' THEN 0 ELSE 1 END, id
        """, (part_no, price_list, price_type))
        row = cur.fetchone()
        return float(row[0] or 0) if row else None
    except Exception as e:
        log.warning("get_price(%s, %s) failed: %s", part_no, price_list, e)
        return None
    finally:
        conn.close()


def get_prices_map(
    price_list: str,
    price_type: str = "selling",
) -> dict[str, float]:
    """
    Return a {part_no: price} map for the whole catalogue in one round-trip.
    Used by the product-grid refresh path when the active customer changes —
    we don't want N individual SELECTs per grid render.

    If a part_no has multiple rows for the price list (different UOMs) the
    first row wins, with uom='nos' preferred.
    """
    price_list = (price_list or "").strip()
    if not price_list:
        return {}

    conn = get_connection()
    cur  = conn.cursor()
    try:
        # Window function picks the winner per part_no without GROUP BY.
        cur.execute("""
            SELECT part_no, price
            FROM (
                SELECT part_no, price,
                       ROW_NUMBER() OVER (
                           PARTITION BY part_no
                           ORDER BY CASE WHEN uom = 'nos' THEN 0 ELSE 1 END, id
                       ) AS rn
                FROM   item_prices
                WHERE  price_list = ? AND price_type = ?
            ) t
            WHERE rn = 1
        """, (price_list, price_type))
        out: dict[str, float] = {}
        for part_no, price in cur.fetchall():
            if part_no:
                out[str(part_no).strip().upper()] = float(price or 0)
        return out
    except Exception as e:
        log.warning("get_prices_map(%s) failed: %s", price_list, e)
        return {}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Convenience helpers (by price-list ID — joins on price_lists.name)
# ---------------------------------------------------------------------------

def resolve_price_list_name(price_list_id: Optional[int]) -> Optional[str]:
    """Turn a customer.default_price_list_id into the ERPNext price_list name."""
    if not price_list_id:
        return None
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("SELECT name FROM price_lists WHERE id = ?", (int(price_list_id),))
        row = cur.fetchone()
        return (str(row[0]).strip() if row and row[0] else None)
    except Exception as e:
        log.warning("resolve_price_list_name(%s) failed: %s", price_list_id, e)
        return None
    finally:
        conn.close()


def get_price_by_list_id(
    part_no: str,
    price_list_id: Optional[int],
    uom: Optional[str] = None,
) -> Optional[float]:
    """Convenience: skip the name resolution step at the call site."""
    name = resolve_price_list_name(price_list_id)
    if not name:
        log.debug("get_price_by_list_id: price_list_id=%s not found", price_list_id)
        return None
    return get_price(part_no, name, uom=uom)
