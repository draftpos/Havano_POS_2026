# =============================================================================
# services/bugsink_service.py
# Bugsink / Sentry-compatible error tracking for Havano POS
# =============================================================================
"""
Lightweight, zero-external-dependency Sentry/Bugsink client.

Uses only Python stdlib (urllib, threading, queue, json, uuid) so it works
on deployed .exe terminals without needing `pip install sentry-sdk`.

Public API
----------
    init_bugsink()                       — call once during startup
    capture_exception(exc, extra=None)   — send an exception event
    capture_message(msg, level, extra)   — send a plain message event
    set_user_context(username, role)     — attach logged-in user info
    add_breadcrumb(category, msg, level) — record recent action breadcrumb
    get_log_handler()                    — returns a logging.Handler
"""

from __future__ import annotations

import json
import logging
import os
import platform
import queue
import socket
import sys
import threading
import traceback
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError

# ─── Module-level state ──────────────────────────────────────────────────────
_logger = logging.getLogger("bugsink")

_dsn: str = ""
_store_url: str = ""           # POST endpoint derived from DSN
_public_key: str = ""          # Sentry auth header key
_environment: str = "production"
_sample_rate: float = 1.0
_enabled: bool = False
_max_queue_size: int = 200

_event_queue: queue.Queue | None = None
_worker_thread: threading.Thread | None = None
_shutdown_event: threading.Event = threading.Event()

# Mutable context dicts – enriched lazily on first event and via set_*()
_user_context: Dict[str, str] = {}
_tenant_context: Dict[str, str] = {}
_app_version: str = "unknown"
_initialised: bool = False

_breadcrumbs = deque(maxlen=50)
_breadcrumbs_lock = threading.Lock()


_current_page: str = "Startup"


def set_current_page(page_name: str) -> None:
    """Set the currently active page/screen/dialog for error and hang reporting."""
    global _current_page
    _current_page = str(page_name or "Unknown")
    add_breadcrumb(category="navigation", message=f"Navigated to {_current_page}", level="info")


def get_current_page() -> str:
    """Get the currently active page/screen/dialog."""
    return _current_page


def add_breadcrumb(
    category: str = "default",
    message: str = "",
    level: str = "info",
    data: dict | None = None,
) -> None:
    """
    Record a breadcrumb for Bugsink / Sentry error context.
    Also forwards to sentry_sdk.add_breadcrumb if sentry_sdk is available.
    """
    # Suppress startup / migration / schema DDL freeze breadcrumbs completely
    if category == "ui_hang" or "freeze alert" in str(message).lower():
        msg_lower = (str(message) + " " + str(data or "")).lower()
        if any(ig in msg_lower for ig in ("setup_database", "migrate.py", "apply_performance_indexes", "information_schema", "startup", "fontintegrity")):
            return

    crumb = {
        "timestamp": datetime.now(timezone.utc).timestamp(),
        "type": "default",
        "category": str(category or "default"),
        "message": str(message or ""),
        "level": str(level or "info"),
        "data": dict(data) if data else {},
    }
    with _breadcrumbs_lock:
        _breadcrumbs.append(crumb)

    try:
        import sentry_sdk
        sentry_sdk.add_breadcrumb(category=category, message=message, level=level, data=data)
    except Exception:
        pass


# ─── DSN Parsing ──────────────────────────────────────────────────────────────

def _parse_dsn(dsn: str) -> tuple[str, str, str]:
    """
    Parse a Sentry-style DSN into (store_url, public_key, project_id).

    DSN format:  https://<public_key>@<host>/<project_id>
    Store URL:   https://<host>/api/<project_id>/store/
    """
    parsed = urlparse(dsn)
    public_key = parsed.username or ""
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    scheme = parsed.scheme or "https"
    project_id = parsed.path.strip("/")

    store_url = f"{scheme}://{host}{port}/api/{project_id}/store/"
    return store_url, public_key, project_id


# ─── Configuration Loading ────────────────────────────────────────────────────

def _get_app_data_dir() -> Path:
    """Mirror the app_data resolution from database/db.py."""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys.executable).parent / "app_data"
    return Path(__file__).resolve().parent.parent / "app_data"


def _load_config() -> dict:
    """
    Load Bugsink config with priority:
      1. Environment variable  BUGSINK_DSN / SENTRY_DSN
      2. app_data/bugsink_config.json
    """
    cfg: dict = {
        "enabled": True,
        "dsn": "https://54ee3e24f4bd4da79ecd8336094a8312@bugsink.havano.cloud/4",
        "environment": "production",
        "sample_rate": 1.0,
        "max_queue_size": 200,
    }

    # File-based config
    cfg_path = _get_app_data_dir() / "bugsink_config.json"
    if cfg_path.exists():
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                file_cfg = json.load(f)
            cfg.update(file_cfg)
        except Exception as e:
            _logger.warning("Failed to read bugsink_config.json: %s", e)

    # Environment variable override (highest priority)
    env_dsn = os.environ.get("BUGSINK_DSN") or os.environ.get("SENTRY_DSN")
    if env_dsn:
        cfg["dsn"] = env_dsn

    return cfg


# ─── Context Enrichment ───────────────────────────────────────────────────────

def _collect_tenant_context() -> Dict[str, str]:
    """Pull tenant metadata from company_defaults and sql_settings (lazy, cached)."""
    ctx: Dict[str, str] = {}
    try:
        from models.company_defaults import get_defaults
        d = get_defaults()
        ctx["tenant"]       = d.get("company_name", "") or ""
        ctx["company"]      = d.get("server_company", "") or ctx["tenant"]
        ctx["warehouse"]    = d.get("server_warehouse", "") or ""
        ctx["terminal_id"]  = str(d.get("server_terminal_id", "") or "")
        ctx["terminal"]     = d.get("server_terminal_name", "") or ""
        ctx["store"]        = str(d.get("server_shop_id", "") or "")
        ctx["store_name"]   = d.get("company_name", "") or ""
        ctx["api_host"]     = d.get("server_api_host", "") or ""
        ctx["currency"]     = d.get("server_company_currency", "USD") or "USD"
        ctx["pharmacy_mode"] = str(d.get("pharmacy_mode", "0") or "0")
        ctx["butchery_mode"] = str(d.get("butchery_mode", "0") or "0")
    except Exception:
        pass

    # Enrich from sql_settings.json for SaaS metadata
    try:
        from database.db import _load_settings
        s = _load_settings()
        if not ctx.get("tenant"):
            ctx["tenant"] = str(s.get("database", "") or "")
        if not ctx.get("store"):
            ctx["store"] = str(s.get("server_shop_id", "") or "")
        if not ctx.get("terminal_id"):
            ctx["terminal_id"] = str(s.get("server_terminal_id", "") or "")
        ctx["tenant_email"] = str(s.get("active_user_email", "") or s.get("user_email", "") or "")
        ctx["device_id"]    = str(s.get("bound_device_id", "") or "")
        ctx["api_url"]      = str(s.get("api_url", "") or "")
    except Exception:
        pass

    return ctx


def _collect_db_context() -> Dict[str, str]:
    """Pull database server & name from db.py settings."""
    ctx: Dict[str, str] = {}
    try:
        from database.db import _load_settings
        s = _load_settings()
        ctx["db_server"]   = s.get("server", "") or ""
        ctx["db_name"]     = s.get("database", "") or ""
        ctx["db_auth"]     = s.get("auth_mode", "") or ""
    except Exception:
        pass
    return ctx


def _build_tags() -> Dict[str, str]:
    """Assemble the full tag dictionary for an event."""
    tags: Dict[str, str] = {
        "version":     _app_version,
        "environment": _environment,
        "os":          platform.system(),
        "os_version":  platform.version(),
        "python":      platform.python_version(),
        "machine":     socket.gethostname(),
        "page":        _current_page,
    }

    # User context
    u = _build_user()
    if u:
        user_ident = u.get("username") or u.get("email") or u.get("name")
        if user_ident:
            tags["user"] = str(user_ident)
            tags["logged_in_user"] = str(user_ident)
        if u.get("role"):
            tags["user_role"] = str(u["role"])

    # Tenant context (cached after first call)
    global _tenant_context
    if not _tenant_context:
        _tenant_context = _collect_tenant_context()
    tags.update({k: v for k, v in _tenant_context.items() if v})

    # Database context
    db_ctx = _collect_db_context()
    tags.update({k: v for k, v in db_ctx.items() if v})

    return tags


def _build_user() -> Dict[str, str]:
    """Return the current user context block, resolving dynamically if not yet cached."""
    global _user_context
    u = dict(_user_context) if _user_context else {}

    # If username or email is missing, attempt to resolve from active app / session state
    if not u.get("username") and not u.get("email"):
        try:
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                mw = getattr(app, "_main_window", None)
                if mw and hasattr(mw, "user") and isinstance(mw.user, dict):
                    app_user = mw.user
                    if app_user.get("username"):
                        u["username"] = str(app_user.get("username"))
                    if app_user.get("email") or app_user.get("frappe_user"):
                        u["email"] = str(app_user.get("email") or app_user.get("frappe_user"))
                    if app_user.get("role"):
                        u["role"] = str(app_user.get("role"))
                    if app_user.get("id"):
                        u["id"] = str(app_user.get("id"))
                    if app_user.get("full_name"):
                        u["name"] = str(app_user.get("full_name"))
        except Exception:
            pass

    if not u.get("username") and not u.get("email"):
        try:
            from services.auth_service import get_active_session_user
            sess_user = get_active_session_user()
            if sess_user:
                if "@" in sess_user:
                    u["email"] = sess_user
                else:
                    u["username"] = sess_user
        except Exception:
            pass

    if not u.get("username") and not u.get("email"):
        try:
            from database.db import _load_settings
            s = _load_settings()
            email = s.get("active_user_email") or s.get("user_email") or s.get("last_logged_in_user")
            if email:
                u["email"] = str(email)
        except Exception:
            pass

    return {k: str(v) for k, v in u.items() if v}


# ─── Event Building ───────────────────────────────────────────────────────────

def _build_exception_event(
    exc: BaseException,
    tb_str: str | None = None,
    extra: dict | None = None,
    level: str = "error",
) -> dict:
    """Build a Sentry-compatible event envelope for an exception."""
    event_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()

    # Extract exception chain
    exc_type = type(exc).__name__
    exc_module = type(exc).__module__ or ""
    exc_value = str(exc)

    if tb_str is None:
        tb_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

    # Build frames from traceback
    frames = []
    tb_obj = exc.__traceback__
    while tb_obj is not None:
        frame = tb_obj.tb_frame
        frames.append({
            "filename": frame.f_code.co_filename,
            "function": frame.f_code.co_name,
            "lineno": tb_obj.tb_lineno,
            "module": frame.f_globals.get("__name__", ""),
        })
        tb_obj = tb_obj.tb_next

    event_extra = dict(extra) if extra else {}
    u = _build_user()
    if u and "logged_in_user" not in event_extra:
        event_extra["logged_in_user"] = u.get("username") or u.get("email") or u.get("name") or "unknown"
        event_extra["user_context"] = u

    event = {
        "event_id": event_id,
        "timestamp": now,
        "level": level,
        "platform": "python",
        "release": f"havano-pos@{_app_version}",
        "environment": _environment,
        "server_name": socket.gethostname(),
        "tags": _build_tags(),
        "user": u,
        "exception": {
            "values": [{
                "type": exc_type,
                "value": exc_value,
                "module": exc_module,
                "stacktrace": {
                    "frames": frames,
                } if frames else None,
            }],
        },
        "extra": event_extra,
        "contexts": {
            "os": {
                "name": platform.system(),
                "version": platform.version(),
            },
            "runtime": {
                "name": "CPython",
                "version": platform.python_version(),
            },
            "app": {
                "app_name": "Havano POS",
                "app_version": _app_version,
            },
        },
    }

    # Attach raw traceback text for readability
    if tb_str:
        event["extra"]["raw_traceback"] = tb_str

    with _breadcrumbs_lock:
        crumbs = list(_breadcrumbs)
    if crumbs:
        event["breadcrumbs"] = {"values": crumbs}

    return event


def _build_message_event(
    message: str,
    level: str = "info",
    extra: dict | None = None,
    tags: dict | None = None,
) -> dict:
    """Build a Sentry-compatible event envelope for a plain message."""
    event_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()

    merged_tags = _build_tags()
    if tags:
        merged_tags.update({str(k): str(v) for k, v in tags.items() if v is not None})

    event_extra = dict(extra) if extra else {}
    u = _build_user()
    if u and "logged_in_user" not in event_extra:
        event_extra["logged_in_user"] = u.get("username") or u.get("email") or u.get("name") or "unknown"
        event_extra["user_context"] = u

    event = {
        "event_id": event_id,
        "timestamp": now,
        "level": level,
        "platform": "python",
        "release": f"havano-pos@{_app_version}",
        "environment": _environment,
        "server_name": socket.gethostname(),
        "tags": merged_tags,
        "user": u,
        "message": {"formatted": message},
        "extra": event_extra,
        "contexts": {
            "os": {
                "name": platform.system(),
                "version": platform.version(),
            },
            "runtime": {
                "name": "CPython",
                "version": platform.python_version(),
            },
            "app": {
                "app_name": "Havano POS",
                "app_version": _app_version,
            },
        },
    }

    with _breadcrumbs_lock:
        crumbs = list(_breadcrumbs)
    if crumbs:
        event["breadcrumbs"] = {"values": crumbs}

    return event


# ─── Network Transport ───────────────────────────────────────────────────────

def _send_event(event: dict) -> bool:
    """POST a single event to the Bugsink store endpoint. Returns True on success."""
    if not _store_url or not _public_key:
        return False

    body = json.dumps(event).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-Sentry-Auth": (
            f"Sentry sentry_version=7, "
            f"sentry_client=havano-pos/{_app_version}, "
            f"sentry_key={_public_key}"
        ),
    }

    try:
        req = Request(_store_url, data=body, headers=headers, method="POST")
        with urlopen(req, timeout=5) as resp:
            return 200 <= resp.status < 300
    except URLError as e:
        _logger.debug("Bugsink send failed (network): %s", e)
        return False
    except Exception as e:
        _logger.debug("Bugsink send failed: %s", e)
        return False


# ─── Background Worker ────────────────────────────────────────────────────────

def _worker_loop():
    """Drain the event queue and POST each event. Runs in a daemon thread."""
    while not _shutdown_event.is_set():
        try:
            event = _event_queue.get(timeout=2.0)
        except queue.Empty:
            continue

        if event is None:  # Sentinel to stop
            break

        try:
            success = _send_event(event)
            if not success:
                # Retry once after a short delay
                _shutdown_event.wait(1.0)
                if not _shutdown_event.is_set():
                    _send_event(event)
        except Exception:
            pass  # Never crash the worker

    _logger.debug("Bugsink worker thread exiting")


# ─── Public API ───────────────────────────────────────────────────────────────

def init_bugsink(version: str = "unknown", enabled: Optional[bool] = None):
    """
    Initialize the Bugsink error tracking service.
    Call once during application startup from main.py.
    Pass enabled=False to disable error tracking (e.g. during local Debug development).
    """
    global _dsn, _store_url, _public_key, _environment, _sample_rate
    global _enabled, _max_queue_size, _event_queue, _worker_thread
    global _app_version, _initialised

    if _initialised:
        return

    _app_version = version
    cfg = _load_config()

    _dsn = cfg.get("dsn", "")
    _environment = cfg.get("environment", "production")
    _sample_rate = cfg.get("sample_rate", 1.0)
    _max_queue_size = cfg.get("max_queue_size", 200)

    if enabled is not None:
        _enabled = bool(enabled) and bool(_dsn)
    else:
        _enabled = bool(cfg.get("enabled", True)) and bool(_dsn)

    if not _enabled:
        _logger.info("Bugsink disabled (Debug mode active or no DSN)")
        _initialised = True
        return

    try:
        _store_url, _public_key, _ = _parse_dsn(_dsn)
    except Exception as e:
        _logger.warning("Failed to parse Bugsink DSN: %s", e)
        _enabled = False
        _initialised = True
        return

    # Start the async dispatcher
    _event_queue = queue.Queue(maxsize=_max_queue_size)
    _worker_thread = threading.Thread(target=_worker_loop, name="bugsink-worker", daemon=True)
    _worker_thread.start()

    _initialised = True
    _logger.info("Bugsink initialized — DSN=%s, env=%s, version=%s",
                 _dsn[:40] + "...", _environment, _app_version)


def shutdown():
    """Gracefully drain remaining events and stop the worker."""
    global _enabled
    if _event_queue and _worker_thread and _worker_thread.is_alive():
        _shutdown_event.set()
        try:
            _event_queue.put_nowait(None)  # Sentinel
        except queue.Full:
            pass
        _worker_thread.join(timeout=3.0)
    _enabled = False


# ─── Network Error Filter ──────────────────────────────────────────────────

_NETWORK_EXCEPTION_NAMES = {
    "ConnectionError", "ConnectTimeout", "ReadTimeout", "Timeout",
    "URLError", "RemoteDisconnected", "IncompleteRead",
    "CannotSendRequest", "gaierror", "timeout", "ConnectionResetError",
    "ConnectionRefusedError", "ConnectionAbortedError", "TimeoutError",
    "SSLError", "NewConnectionError", "MaxRetryError",
}

_NETWORK_PATTERNS = [
    "read operation timed out",
    "the read operation timed out",
    "timed out",
    "connection reset",
    "connection refused",
    "connection aborted",
    "remote disconnected",
    "failed to establish a new connection",
    "nameresolutionerror",
    "getaddrinfo failed",
    "max retries exceeded",
    "network is unreachable",
    "no route to host",
    "host is unreachable",
    "winerror 10060",
    "winerror 10061",
    "winerror 10054",
    "no credentials found",
    "uncaught exception",
]

_SUPPRESSED_PATTERNS = [
    "havanoposdesk.product' object has no attribute 'default_code'",
    "object has no attribute 'default_code'",
    "could not fetch users from any endpoint",
    "[user-sync] could not fetch users from any endpoint",
    "failed to sync quotation",
    "freeze alert",
    "ui_hang",
    "ui recovered from",
    "recovered from freeze",
    "migrate.py",
    "_add_column_if_missing",
    "setup_database.py",
    "tenant_reset.py",
    "sp_msforeachtable",
    "nocheck constraint",
    "information_schema",
    "if not exists (select 1 from information_schema",
    "[dosage-sync] http 404",
    "[doctor-sync] http 404",
    "[dosage-push] http 404",
    "[doctor-push] http 404",
    "dosagesync: [dosage-sync] http 404",
    "doctorsync: [doctor-sync] http 404",
    "dosage-sync] http 404",
    "doctor-sync] http 404",
    "[saas_snapshot] failed to take saas snapshot",
    "[saas_snapshot] failed to update saas snapshot",
    "ui freeze",
    "uifreezehang",
    "[startup]",
    "at [startup]",
    "col_exists",
    "object has no attribute 'quantity'",
    'object has no attribute "quantity"',
    "object has no attribute quantity",
    "havanoposdesk.sale.line",
    "havanoposdesk.sale",
    "object has no attribute 'timeout'",
    'object has no attribute "timeout"',
    "object has no attribute timeout",
    "has no attribute 'timeout'",
    "has no attribute timeout",
    "laybye_payment_entry_service: get_unsynced_payment_entries failed",
    "payment sync cycle error",
    "error fetching page 1:",
]


def is_network_or_suppressed_error(message: str = "", exc: Optional[BaseException] = None) -> bool:
    """
    Returns True ONLY if the given exception or log message represents a
    pure network dropout, timeout, socket connection failure, or specifically
    muted known non-critical backend errors.
    Application errors, HTTP status errors, and logic bugs are NOT filtered.
    """
    if exc is not None:
        exc_type_name = type(exc).__name__
        if exc_type_name in _NETWORK_EXCEPTION_NAMES:
            return True
        if isinstance(exc, (ConnectionError, TimeoutError, socket.error, URLError)):
            return True
        try:
            import requests.exceptions as req_exc
            if isinstance(exc, (req_exc.ConnectionError, req_exc.Timeout, req_exc.ConnectTimeout, req_exc.ReadTimeout)):
                return True
        except ImportError:
            pass

    combined_text = f"{str(message)} {str(exc) if exc else ''}".lower()

    # Mute 404 / NOT FOUND errors for pharmacy/dosage/doctor sync and push endpoints
    if any(k in combined_text for k in ("dosage-sync", "dosagesync", "dosage-push", "doctor-sync", "doctorsync", "doctor-push")) and ("404" in combined_text or "not found" in combined_text):
        return True

    for pat in _NETWORK_PATTERNS + _SUPPRESSED_PATTERNS:
        if pat in combined_text:
            return True

    return False


def capture_exception(
    exc: BaseException,
    extra: Optional[Dict[str, Any]] = None,
    level: str = "error",
) -> Optional[str]:
    """
    Capture an exception and queue it for delivery to Bugsink.
    Returns the event_id on success, None if disabled/full/suppressed.
    """
    if not _enabled or not _event_queue:
        return None

    if is_network_or_suppressed_error(message=str(exc), exc=exc):
        _logger.debug("Bugsink suppressed network/transient exception: %s", exc)
        return None

    try:
        event = _build_exception_event(exc, extra=extra, level=level)
        _event_queue.put_nowait(event)
        return event.get("event_id")
    except queue.Full:
        _logger.debug("Bugsink queue full, dropping event")
        return None
    except Exception:
        return None


def capture_message(
    message: str,
    level: str = "info",
    extra: Optional[Dict[str, Any]] = None,
    tags: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    """Capture a plain message and queue it for delivery."""
    if not _enabled or not _event_queue:
        return None

    if is_network_or_suppressed_error(message=message):
        _logger.debug("Bugsink suppressed network/transient log message: %s", message[:80])
        return None

    try:
        event = _build_message_event(message, level=level, extra=extra, tags=tags)
        _event_queue.put_nowait(event)
        return event.get("event_id")
    except queue.Full:
        return None
    except Exception:
        return None


def capture_freeze_event(
    title: str,
    frames: list[dict],
    level: str = "error",
    extra: Optional[Dict[str, Any]] = None,
    tags: Optional[Dict[str, str]] = None,
    raw_traceback: str = "",
) -> Optional[str]:
    """Capture a UI freeze event with structured stack frames and exact code line for Bugsink."""
    if not _enabled or not _event_queue:
        return None

    # Filter out deliberate startup initialization, migrations, tenant reset, and DDL setup
    ignored_keywords = (
        "setup_database",
        "migrate.py",
        "_add_column_if_missing",
        "tenant_reset",
        "drop_all_tables",
        "wipe_all_tenant_data",
        "apply_performance_indexes",
        "verify_and_heal_fonts",
        "updater.py",
        "sp_msforeachtable",
        "nocheck constraint",
        "information_schema",
        "[startup]",
        "at [startup]",
        "col_exists",
    )
    combined_check = f"{title or ''} {str(extra or '')} {str(tags or '')} {raw_traceback or ''}".lower()
    if any(ig in combined_check for ig in ignored_keywords):
        _logger.debug("Suppressed Bugsink freeze reporting for startup/migration/reset operation.")
        return None

    try:
        event_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc).isoformat()

        merged_tags = _build_tags()
        if tags:
            merged_tags.update({str(k): str(v) for k, v in tags.items() if v is not None})

        blocked_code = extra.get("exact_code_line", "") if extra else ""

        freeze_extra = dict(extra) if extra else {}
        u = _build_user()
        if u and "logged_in_user" not in freeze_extra:
            freeze_extra["logged_in_user"] = u.get("username") or u.get("email") or u.get("name") or "unknown"
            freeze_extra["user_context"] = u

        event = {
            "event_id": event_id,
            "timestamp": now,
            "level": level,
            "platform": "python",
            "release": f"havano-pos@{_app_version}",
            "environment": _environment,
            "server_name": socket.gethostname(),
            "tags": merged_tags,
            "user": u,
            "message": {"formatted": title},
            "exception": {
                "values": [{
                    "type": "UIFreezeHang",
                    "value": f"{title} | Code: {blocked_code}",
                    "module": "services.hang_watchdog",
                    "stacktrace": {
                        "frames": frames,
                    } if frames else None,
                }],
            },
            "extra": freeze_extra,
            "contexts": {
                "os": {
                    "name": platform.system(),
                    "version": platform.version(),
                },
                "runtime": {
                    "name": "CPython",
                    "version": platform.python_version(),
                },
                "app": {
                    "app_name": "Havano POS",
                    "app_version": _app_version,
                },
            },
        }

        if raw_traceback:
            event["extra"]["raw_traceback"] = raw_traceback

        with _breadcrumbs_lock:
            crumbs = list(_breadcrumbs)
        if crumbs:
            event["breadcrumbs"] = {"values": crumbs}

        _event_queue.put_nowait(event)
        return event_id
    except queue.Full:
        return None
    except Exception as e:
        _logger.debug("Failed to queue freeze event: %s", e)
        return None


def set_user_context(
    username: str = "",
    role: str = "",
    email: str = "",
    user_id: str = "",
    name: str = "",
    **extra_attrs,
):
    """Attach the currently logged-in user to all future events."""
    global _user_context
    ctx: Dict[str, str] = {}
    if username:
        ctx["username"] = str(username)
    if role:
        ctx["role"] = str(role)
    if email:
        ctx["email"] = str(email)
    if user_id:
        ctx["id"] = str(user_id)
    if name:
        ctx["name"] = str(name)
    for k, v in extra_attrs.items():
        if v is not None:
            ctx[str(k)] = str(v)
    _user_context = ctx

    try:
        import sentry_sdk
        sentry_sdk.set_user(ctx if ctx else None)
    except Exception:
        pass


def set_logged_in_user(user: dict | None):
    """Helper to set user context directly from a user dict or object."""
    if not user or not isinstance(user, dict):
        set_user_context()
        return
    set_user_context(
        username=user.get("username") or user.get("full_name") or "",
        role=user.get("role") or "",
        email=user.get("email") or user.get("frappe_user") or "",
        user_id=str(user.get("id") or ""),
        name=user.get("full_name") or "",
    )


def refresh_tenant_context():
    """Force re-reading tenant/company data from DB (e.g., after login)."""
    global _tenant_context
    _tenant_context = _collect_tenant_context()


def check_and_report_saas_empty_catalog(context: str = "general", extra_info: dict | None = None) -> bool:
    """
    Checks if the system is in SaaS mode and if the local database is empty or has 0 products.
    If empty, sends an error alert to Bugsink and returns True (indicating empty).
    """
    try:
        from services.credentials import get_system_mode
        if get_system_mode() != "saas":
            return False

        from database.db import get_connection, _load_settings
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM products WITH (NOLOCK)")
        p_cnt = int(cur.fetchone()[0] or 0)
        cur.execute("SELECT COUNT(*) FROM users WITH (NOLOCK)")
        u_cnt = int(cur.fetchone()[0] or 0)
        conn.close()

        if p_cnt == 0:
            cfg = _load_settings()
            db_name = cfg.get("database") or "unknown_db"
            extra = {
                "database": db_name,
                "server": cfg.get("server"),
                "system_mode": "saas",
                "product_count": p_cnt,
                "user_count": u_cnt,
                "check_context": context,
                "error_type": "empty_database_saas",
            }
            if extra_info:
                extra.update(extra_info)
            capture_message(
                f"Empty database / Missing products in SaaS mode ({context}): Database '{db_name}' has 0 products",
                level="error",
                extra=extra
            )
            return True
        return False
    except Exception as e:
        _logger.warning("[bugsink] check_and_report_saas_empty_catalog error: %s", e)
        return False


_last_known_db: str | None = None


def check_and_report_database_change(current_db: str = None, context: str = "general") -> tuple[bool, str]:
    """
    Checks if the active database has changed compared to the last known database.
    If changed, sends an error alert to Bugsink and persists the new database name.
    Returns (changed: bool, message: str).
    """
    global _last_known_db
    try:
        from database.db import get_app_data_dir, _load_settings
        cfg = _load_settings()
        curr = str(current_db or cfg.get("database") or "").strip()
        if not curr:
            return (False, "")

        tracker_file = get_app_data_dir() / "last_active_database.txt"
        prev_db = ""
        if tracker_file.exists():
            try:
                prev_db = tracker_file.read_text(encoding="utf-8").strip()
            except Exception:
                pass

        if not prev_db and _last_known_db:
            prev_db = _last_known_db

        _last_known_db = curr

        if prev_db and prev_db.lower() != curr.lower():
            tracker_file.write_text(curr, encoding="utf-8")
            msg = f"Database configuration changed ({context}): Switched from '{prev_db}' to '{curr}'"
            extra = {
                "previous_database": prev_db,
                "current_database": curr,
                "server": cfg.get("server"),
                "system_mode": cfg.get("system_mode"),
                "context": context,
                "error_type": "database_switched",
            }
            capture_message(msg, level="error", extra=extra)
            _logger.error("[bugsink] %s", msg)
            return (True, f"Database changed from '{prev_db}' to '{curr}'")
        else:
            if not tracker_file.exists():
                tracker_file.write_text(curr, encoding="utf-8")
            return (False, "")
    except Exception as e:
        _logger.warning("[bugsink] check_and_report_database_change error: %s", e)
        return (False, "")


# ─── Logging Handler ──────────────────────────────────────────────────────────

class BugsinkLogHandler(logging.Handler):
    """
    A Python logging.Handler that forwards ERROR and CRITICAL log records
    to Bugsink as message events. Transient network & sync errors are filtered out.
    """

    def __init__(self, level=logging.ERROR):
        super().__init__(level)

    def emit(self, record: logging.LogRecord):
        if not _enabled:
            return

        msg = self.format(record)
        exc = record.exc_info[1] if record.exc_info else None

        # Filter out all network drops, timeouts, 404s, and sync retries
        if is_network_or_suppressed_error(message=msg, exc=exc):
            return

        level_map = {
            logging.CRITICAL: "fatal",
            logging.ERROR: "error",
            logging.WARNING: "warning",
        }
        level = level_map.get(record.levelno, "error")

        extra = {
            "logger": record.name,
            "pathname": record.pathname,
            "lineno": record.lineno,
            "funcName": record.funcName,
        }
        u = _build_user()
        if u:
            extra["logged_in_user"] = u.get("username") or u.get("email") or u.get("name") or "unknown"
            extra["user_context"] = u

        capture_message(msg, level=level, extra=extra)


def get_log_handler() -> BugsinkLogHandler:
    """Return a BugsinkLogHandler instance ready to attach to a logger."""
    handler = BugsinkLogHandler(level=logging.ERROR)
    handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
    return handler
