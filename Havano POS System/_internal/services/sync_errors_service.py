# =============================================================================
# services/sync_errors_service.py
#
# A standalone sync_errors table that records every failed cloud push.
# No changes to any existing table — completely separate.
#
# Table columns:
#   id           INT IDENTITY PK
#   doc_type     NVARCHAR(20)   — 'SI', 'CN', 'SO', 'PE'
#   doc_ref      NVARCHAR(100)  — invoice_no / order_no / cn_number
#   customer     NVARCHAR(255)
#   amount       FLOAT
#   error_code   NVARCHAR(20)   — 'HTTP 417', 'NETWORK', etc.
#   error_msg    NVARCHAR(MAX)  — raw server response, stored verbatim
#   occurred_at  NVARCHAR(50)   — ISO timestamp
#   resolved     BIT DEFAULT 0  — set to 1 when doc later syncs OK
# =============================================================================

from __future__ import annotations
import logging
from datetime import datetime

log = logging.getLogger("SyncErrors")

_TABLE_SQL = """
IF NOT EXISTS (
    SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'sync_errors') AND type = 'U'
)
CREATE TABLE sync_errors (
    id          INT           NOT NULL PRIMARY KEY IDENTITY(1,1),
    doc_type    NVARCHAR(20)  NOT NULL DEFAULT '',
    doc_ref     NVARCHAR(100) NOT NULL DEFAULT '',
    customer    NVARCHAR(255) NOT NULL DEFAULT '',
    amount      FLOAT         NOT NULL DEFAULT 0,
    error_code  NVARCHAR(20)  NOT NULL DEFAULT '',
    error_msg   NVARCHAR(MAX) NOT NULL DEFAULT '',
    occurred_at NVARCHAR(50)  NOT NULL DEFAULT '',
    resolved    BIT           NOT NULL DEFAULT 0
)
"""


def _conn():
    from database.db import get_connection
    return get_connection()


def ensure_table():
    """Create sync_errors table if it does not exist. Safe to call repeatedly."""
    try:
        c = _conn()
        c.execute(_TABLE_SQL)
        c.commit()
    except Exception as e:
        log.warning("sync_errors ensure_table: %s", e)


def record_error(
    doc_type: str,
    doc_ref: str,
    error_msg: str,
    customer: str = "",
    amount: float = 0.0,
    error_code: str = "",
):
    """
    Write one sync failure to sync_errors.
    Automatically marks any previous unresolved row for the same doc resolved=0
    (keeps the latest error per doc).
    Safe to call from background threads.
    """
    try:
        ensure_table()
        c = _conn()
        # Mark old unresolved rows for same doc as superseded
        c.execute(
            "UPDATE sync_errors SET resolved = 1 "
            "WHERE doc_type = ? AND doc_ref = ? AND resolved = 0",
            (doc_type, doc_ref),
        )
        c.execute(
            """
            INSERT INTO sync_errors
                (doc_type, doc_ref, customer, amount, error_code, error_msg, occurred_at, resolved)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                doc_type,
                doc_ref,
                customer or "",
                float(amount or 0),
                error_code or "",
                str(error_msg) if error_msg else "",   # raw, no cleaning/truncation
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        c.commit()
        log.debug("Recorded sync error: [%s] %s — %s", doc_type, doc_ref, error_code)
    except Exception as e:
        log.warning("sync_errors record_error failed: %s", e)


def resolve(doc_type: str, doc_ref: str):
    """
    Mark all unresolved errors for this document as resolved.
    Call this when a document successfully syncs.
    """
    try:
        c = _conn()
        c.execute(
            "UPDATE sync_errors SET resolved = 1 "
            "WHERE doc_type = ? AND doc_ref = ? AND resolved = 0",
            (doc_type, doc_ref),
        )
        c.commit()
    except Exception as e:
        log.warning("sync_errors resolve failed: %s", e)


def get_unresolved(doc_type: str | None = None) -> list[dict]:
    """
    Return all unresolved errors, optionally filtered by doc_type.
    Newest first.
    """
    try:
        ensure_table()
        c = _conn()
        cur = c.cursor()
        if doc_type:
            cur.execute(
                "SELECT id, doc_type, doc_ref, customer, amount, "
                "       error_code, error_msg, occurred_at "
                "FROM sync_errors "
                "WHERE resolved = 0 AND doc_type = ? "
                "ORDER BY id DESC",
                (doc_type,),
            )
        else:
            cur.execute(
                "SELECT id, doc_type, doc_ref, customer, amount, "
                "       error_code, error_msg, occurred_at "
                "FROM sync_errors "
                "WHERE resolved = 0 "
                "ORDER BY id DESC"
            )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception as e:
        log.warning("sync_errors get_unresolved failed: %s", e)
        return []


def count_unresolved(doc_type: str | None = None) -> int:
    """Fast count of unresolved errors for badge display."""
    try:
        ensure_table()
        c = _conn()
        cur = c.cursor()
        if doc_type:
            cur.execute(
                "SELECT COUNT(*) FROM sync_errors "
                "WHERE resolved = 0 AND doc_type = ?",
                (doc_type,),
            )
        else:
            cur.execute(
                "SELECT COUNT(*) FROM sync_errors WHERE resolved = 0"
            )
        row = cur.fetchone()
        return int(row[0] or 0) if row else 0
    except Exception:
        return 0


def clear_resolved():
    """Housekeeping: delete rows older than 30 days that are resolved."""
    try:
        c = _conn()
        c.execute(
            "DELETE FROM sync_errors "
            "WHERE resolved = 1 "
            "AND DATEDIFF(day, CONVERT(datetime, occurred_at, 126), GETDATE()) > 30"
        )
        c.commit()
    except Exception as e:
        log.warning("sync_errors clear_resolved: %s", e)