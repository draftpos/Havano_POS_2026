# =============================================================================
# models/item_group.py  —  SQL Server  (synced with Frappe/ERPNext API)
# Fields match: name, item_group_name, parent_item_group
# =============================================================================

from database.db import get_connection, fetchall_dicts, fetchone_dict
from services.site_config import get_host as _get_host
FRAPPE_API_URL = (
    _get_host() + "/api/resource/Item%20Group"
    '?fields=["name","item_group_name","parent_item_group"]&limit_page_length=500'
)

# =============================================================================
# MIGRATION
# =============================================================================

def migrate():
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = 'item_groups'
        )
        CREATE TABLE item_groups (
            id                 INT           IDENTITY(1,1) PRIMARY KEY,
            name               NVARCHAR(100) NOT NULL,
            item_group_name    NVARCHAR(100) NOT NULL DEFAULT '',
            parent_item_group  NVARCHAR(100) NOT NULL DEFAULT '',
            synced_from_api    BIT           NOT NULL DEFAULT 0,
            created_at         DATETIME2     NOT NULL DEFAULT SYSDATETIME(),
            updated_at         DATETIME2     NOT NULL DEFAULT SYSDATETIME(),
            CONSTRAINT UQ_item_groups_name UNIQUE (name)
        )
    """)

    # Defensive: add new columns if table already existed without them
    for col, definition in [
        ("item_group_name",   "NVARCHAR(100) NOT NULL DEFAULT ''"),
        ("parent_item_group", "NVARCHAR(100) NOT NULL DEFAULT ''"),
        ("synced_from_api",   "BIT           NOT NULL DEFAULT 0"),
        ("updated_at",        "DATETIME2     NOT NULL DEFAULT SYSDATETIME()"),
    ]:
        cur.execute(f"""
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = 'item_groups' AND COLUMN_NAME = '{col}'
            )
            ALTER TABLE item_groups ADD {col} {definition}
        """)

    conn.commit()
    conn.close()


# =============================================================================
# READ
# =============================================================================

def get_all_item_groups() -> list[dict]:
    conn = get_connection(); cur = conn.cursor()
    cur.execute("""
        SELECT id, name, item_group_name, parent_item_group,
               synced_from_api, created_at, updated_at
        FROM item_groups ORDER BY id
    """)
    rows = fetchall_dicts(cur)
    conn.close()
    return rows


def get_item_group_by_id(group_id: int) -> dict | None:
    conn = get_connection(); cur = conn.cursor()
    cur.execute("""
        SELECT id, name, item_group_name, parent_item_group,
               synced_from_api, created_at, updated_at
        FROM item_groups WHERE id = ?
    """, (group_id,))
    row = fetchone_dict(cur)
    conn.close()
    return row


def get_item_group_by_name(name: str) -> dict | None:
    conn = get_connection(); cur = conn.cursor()
    cur.execute("""
        SELECT id, name, item_group_name, parent_item_group,
               synced_from_api, created_at, updated_at
        FROM item_groups WHERE name = ?
    """, (name,))
    row = fetchone_dict(cur)
    conn.close()
    return row


def search_item_groups(query: str) -> list[dict]:
    conn = get_connection(); cur = conn.cursor()
    cur.execute("""
        SELECT id, name, item_group_name, parent_item_group,
               synced_from_api, created_at, updated_at
        FROM item_groups
        WHERE name LIKE ? OR item_group_name LIKE ? OR parent_item_group LIKE ?
        ORDER BY id
    """, (f"%{query}%", f"%{query}%", f"%{query}%"))
    rows = fetchall_dicts(cur)
    conn.close()
    return rows


# =============================================================================
# WRITE
# =============================================================================

def create_item_group(name: str, item_group_name: str = "",
                      parent_item_group: str = "",
                      synced_from_api: bool = False) -> dict:
    name = name.strip()
    if not name:
        raise ValueError("Item group name cannot be empty.")
    conn = get_connection(); cur = conn.cursor()
    cur.execute("""
        INSERT INTO item_groups (name, item_group_name, parent_item_group, synced_from_api)
        OUTPUT INSERTED.id
        VALUES (?, ?, ?, ?)
    """, (name, item_group_name or name, parent_item_group, 1 if synced_from_api else 0))
    new_id = int(cur.fetchone()[0])
    conn.commit(); conn.close()
    return get_item_group_by_id(new_id)


def update_item_group(group_id: int, name: str,
                      item_group_name: str = "",
                      parent_item_group: str = "") -> dict | None:
    name = name.strip()
    if not name:
        raise ValueError("Item group name cannot be empty.")
    conn = get_connection(); cur = conn.cursor()
    cur.execute("""
        UPDATE item_groups
        SET name = ?, item_group_name = ?, parent_item_group = ?,
            updated_at = SYSDATETIME()
        WHERE id = ?
    """, (name, item_group_name or name, parent_item_group, group_id))
    conn.commit(); conn.close()
    return get_item_group_by_id(group_id)


def delete_item_group(group_id: int) -> bool:
    conn = get_connection(); cur = conn.cursor()
    cur.execute("DELETE FROM item_groups WHERE id = ?", (group_id,))
    deleted = cur.rowcount > 0
    conn.commit(); conn.close()
    return deleted


# =============================================================================
# API SYNC  (Frappe / ERPNext)
# =============================================================================

def sync_from_api(api_key: str = "", api_secret: str = "",
                  prefetched: list = None) -> dict:
    """
    Upserts Item Groups from  into the local item_groups table.

    If `prefetched` is supplied (a list of dicts already fetched by the caller)
    the HTTP request is skipped — this is the normal path when called from
    item_group_dialog.SyncWorker which fetches and passes data in one shot.

    Returns: {"inserted": int, "updated": int, "errors": list[str]}
    """
    inserted = updated = 0
    errors = []

    # ── Fetch if not prefetched ───────────────────────────────────────────────
    if prefetched is not None:
        records = prefetched
    else:
        import urllib.request, json
        headers = {"Accept": "application/json"}
        if api_key and api_secret:
            # Frappe uses Token auth, NOT Basic
            headers["Authorization"] = f"token {api_key}:{api_secret}"
        try:
            req = urllib.request.Request(FRAPPE_API_URL, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                payload = json.loads(resp.read().decode())
            records = payload.get("data", [])
        except Exception as e:
            return {"inserted": 0, "updated": 0, "errors": [str(e)]}

    if not records:
        return {
            "inserted": 0, "updated": 0,
            "errors": ["API returned 0 records."]
        }

    # ── Upsert ────────────────────────────────────────────────────────────────
    conn = get_connection(); cur = conn.cursor()
    for rec in records:
        name              = (rec.get("name") or "").strip()
        item_group_name   = (rec.get("item_group_name") or name).strip()
        parent_item_group = (rec.get("parent_item_group") or "").strip()
        if not name:
            continue
        try:
            cur.execute("SELECT id FROM item_groups WHERE name = ?", (name,))
            if cur.fetchone():
                cur.execute("""
                    UPDATE item_groups
                    SET item_group_name = ?, parent_item_group = ?,
                        synced_from_api = 1, updated_at = SYSDATETIME()
                    WHERE name = ?
                """, (item_group_name, parent_item_group, name))
                updated += 1
            else:
                cur.execute("""
                    INSERT INTO item_groups
                        (name, item_group_name, parent_item_group, synced_from_api)
                    VALUES (?, ?, ?, 1)
                """, (name, item_group_name, parent_item_group))
                inserted += 1
        except Exception as e:
            errors.append(f"{name}: {e}")

    conn.commit(); conn.close()
    return {"inserted": inserted, "updated": updated, "errors": errors}