# =============================================================================
# services/credentials.py
#
# Single credential store for all sync daemons.
#
# The token changes every login — so this module:
#   1. On first call, reads whatever is stored in company_defaults (last session)
#   2. After login, the new token is pushed here via set_session()
#   3. Any daemon calling get_credentials() always gets the latest token
#
# Column it reads/writes: api_key + api_secret in company_defaults (id=1)
# =============================================================================

import logging
log = logging.getLogger("credentials")

_session: dict = {}
_loaded_from_db: bool = False   # only read DB once per process


def set_session(api_key: str, api_secret: str, **extra):
    """
    Called after every login (PIN or password).
    Stores in memory AND persists to DB so next startup has fresh token.
    """
    global _loaded_from_db
    k = str(api_key    or "").strip()
    s = str(api_secret or "").strip()
    _session.clear()
    _session["api_key"]    = k
    _session["api_secret"] = s
    _session.update(extra)
    _loaded_from_db = True   # no need to re-read DB this session

    if k and s:
        _persist_to_db(k, s)
        log.debug("[credentials] Session set and persisted: %s...", k[:8])


def get_session() -> dict:
    return dict(_session)


def get_credentials() -> tuple[str, str]:
    """
    Returns (api_key, api_secret).
    Loads from DB on first call if session not yet set (daemon startup case).
    """
    global _loaded_from_db

    # 1. Already in memory (fastest path — covers mid-session calls)
    if _session.get("api_key") and _session.get("api_secret"):
        return _session["api_key"], _session["api_secret"]

    # 2. Read from DB once per process (covers startup before login and PIN login)
    if not _loaded_from_db:
        _loaded_from_db = True
        k, s = _read_from_db()
        if k and s:
            _session["api_key"]    = k
            _session["api_secret"] = s
            log.debug("[credentials] Loaded from DB: %s...", k[:8])
            return k, s
        else:
            log.warning("[credentials] api_key/api_secret columns are empty in DB — "
                        "login with username+password once to populate them.")

    # 3. Environment variables (CI / headless fallback)
    import os
    k = os.environ.get("HAVANO_API_KEY",    "").strip()
    s = os.environ.get("HAVANO_API_SECRET", "").strip()
    if k and s:
        _session["api_key"]    = k
        _session["api_secret"] = s
        log.debug("[credentials] Loaded from environment")
        return k, s

    log.warning("[credentials] No credentials available")
    return "", ""


# ─────────────────────────────────────────────────────────────────────────────

def _read_from_db() -> tuple[str, str]:
    """Read api_key / api_secret from company_defaults. Never raises."""
    try:
        from database.db import get_connection
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute("SELECT api_key, api_secret FROM company_defaults WHERE id = 1")
        row = cur.fetchone()
        conn.close()
        if row:
            k = str(row[0] or "").strip()
            s = str(row[1] or "").strip()
            if k and s:
                return k, s
    except Exception as e:
        log.debug("[credentials] DB read error: %s", e)
    return "", ""


def _persist_to_db(api_key: str, api_secret: str):
    """Write the latest token back to DB. Never raises."""
    try:
        from database.db import get_connection
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute("""
            UPDATE company_defaults
            SET    api_key = ?, api_secret = ?
            WHERE  id = (SELECT MIN(id) FROM company_defaults)
        """, (api_key, api_secret))
        conn.commit()
        conn.close()
        log.debug("[credentials] Persisted to DB")
    except Exception as e:
        log.warning("[credentials] Could not persist to DB: %s", e)