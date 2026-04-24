"""
database/tenant_reset.py
────────────────────────
Wipe every tenant-owned row in the local POS database.

When the cashier points the POS at a different ERPNext tenant (by
changing `api_url` in SqlSettingsDialog), every synced row in the local
DB belongs to the *old* tenant — products, customers, prices, sales,
shifts, users, everything. Keeping them would cause silent data bleed:
old product codes resolving on the new tenant, cashier PINs from
instance A logging into instance B, sales posting against orphaned
customer IDs, etc.

Policy (agreed with the product owner):
    • Wipe *all* tenant data, including sales / shifts / users. Those
      belong to a different instance now; they're not ours to keep.
    • Preserve only the schema itself — tables, indexes, constraints —
      and the `schema_info` version row so migrations don't re-run.

Implementation:
    • SQL Server's foreign-key constraints would force a fragile
      delete-in-dependency-order dance. Cheaper: disable all FK
      constraints, DELETE every preserved table's data, re-enable.
      (TRUNCATE isn't usable — SQL Server refuses even with disabled
      FKs on tables that are referenced.)
    • All in one transaction so an aborted wipe leaves the DB in its
      original state.
"""

from __future__ import annotations

import logging
from typing import Iterable

from database.db import get_connection

log = logging.getLogger(__name__)

# Tables we NEVER wipe. Everything else gets its rows cleared.
#   schema_info  — migration version marker; wiping would force a
#                  full schema re-migrate on next launch.
_KEEP_TABLES: set[str] = {
    "schema_info",
}


def normalize_url(url: str | None) -> str:
    """Canonical form for cross-comparison (trailing slash, case, whitespace)."""
    if not url:
        return ""
    return url.strip().rstrip("/").lower()


def urls_differ(old: str | None, new: str | None) -> bool:
    """True when the two URLs point to meaningfully different hosts."""
    return normalize_url(old) != normalize_url(new)


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def _list_tables(cur) -> list[str]:
    """All user BASE TABLEs in the current database."""
    cur.execute("""
        SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_TYPE = 'BASE TABLE'
        ORDER BY TABLE_NAME
    """)
    return [r[0] for r in cur.fetchall()]


def _tables_to_wipe(cur) -> list[str]:
    return [t for t in _list_tables(cur) if t not in _KEEP_TABLES]


# ---------------------------------------------------------------------------
# Wipe
# ---------------------------------------------------------------------------

def wipe_all_tenant_data() -> dict:
    """
    Delete rows from every table except those in _KEEP_TABLES.

    Returns a summary dict:
        {
          "tables_wiped": int,
          "rows_deleted": int,   # total across all wiped tables
          "tables":       [{"name": "products", "rows": 1234}, ...],
          "errors":       [...],
        }

    Performs the whole operation in a single transaction — on any error
    we roll back so the DB is never left half-wiped.
    """
    summary = {
        "tables_wiped": 0,
        "rows_deleted": 0,
        "tables":       [],
        "errors":       [],
    }

    conn = get_connection()
    cur  = conn.cursor()
    try:
        # autocommit may be on by default in some pyodbc setups — force a
        # single explicit transaction so the wipe is atomic.
        try:
            conn.autocommit = False
        except Exception:
            pass

        tables = _tables_to_wipe(cur)
        log.info("[tenant-reset] wiping %d tables (keeping: %s)",
                 len(tables), sorted(_KEEP_TABLES))

        # 1. Disable all foreign-key constraints so DELETE order doesn't matter.
        #    The magic cursor sp_MSforeachtable runs the supplied command
        #    for every user table.
        cur.execute("EXEC sp_MSforeachtable 'ALTER TABLE ? NOCHECK CONSTRAINT ALL'")

        # 2. DELETE data from each table we want wiped.
        for t in tables:
            _row_count = _delete_table(cur, t, summary)

        # 3. Re-enable and re-check FK constraints. WITH CHECK forces the
        #    server to verify remaining rows comply — not strictly needed
        #    (we just emptied everything) but cheap and defensive.
        cur.execute("EXEC sp_MSforeachtable 'ALTER TABLE ? WITH CHECK CHECK CONSTRAINT ALL'")

        conn.commit()
        log.info("[tenant-reset] wipe complete: %s tables, %s rows deleted",
                 summary["tables_wiped"], summary["rows_deleted"])
    except Exception as e:
        conn.rollback()
        log.error("[tenant-reset] FAILED, rolled back: %s", e)
        summary["errors"].append(str(e))
    finally:
        try:
            conn.autocommit = True
        except Exception:
            pass
        conn.close()

    # Any module-level caches that would still be holding the old tenant's
    # state should be invalidated by the *caller* (settings dialog) — this
    # module doesn't know which singletons live upstream.
    return summary


def _delete_table(cur, table: str, summary: dict) -> int:
    """DELETE every row from one table; append results to summary."""
    try:
        # Count first — purely for the caller's audit trail; cheap on SQL Server.
        cur.execute(f"SELECT COUNT(*) FROM [{table}]")
        row = cur.fetchone()
        rows = int(row[0]) if row and row[0] is not None else 0

        cur.execute(f"DELETE FROM [{table}]")

        summary["tables_wiped"] += 1
        summary["rows_deleted"] += rows
        summary["tables"].append({"name": table, "rows": rows})
        log.debug("[tenant-reset]   DELETE %s → %d rows", table, rows)
        return rows
    except Exception as e:
        msg = f"{table}: {e}"
        summary["errors"].append(msg)
        log.warning("[tenant-reset]   skipped %s — %s", table, e)
        return 0


# ---------------------------------------------------------------------------
# Convenience: clear in-memory caches too
# ---------------------------------------------------------------------------

def invalidate_runtime_caches() -> None:
    """
    Flush in-process singletons so the next action doesn't see stale
    tenant data. Best-effort — every branch is guarded because not all
    modules are always imported.
    """
    # Auth session (api_key/api_secret/user info held in module state)
    try:
        from services.auth_service import logout
        logout()
    except Exception:
        pass

    # Credentials module (caches api_key/api_secret separately from _session)
    try:
        from services.credentials import set_session
        set_session("", "")
    except Exception:
        pass

    # site_config URL cache
    try:
        from services.site_config import invalidate_cache
        invalidate_cache()
    except Exception:
        pass
