"""
Test script for Bugsink integration.
Sends a real test exception to the configured Bugsink endpoint.
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.bugsink_service import (
    init_bugsink, capture_exception, capture_message,
    set_user_context, refresh_tenant_context, shutdown,
    _parse_dsn, _build_tags, _load_config,
)

def test_dsn_parsing():
    print("=== DSN Parsing ===")
    dsn = "https://54ee3e24f4bd4da79ecd8336094a8312@bugsink.havano.cloud/4"
    store_url, key, proj = _parse_dsn(dsn)
    print(f"  Store URL:  {store_url}")
    print(f"  Key:        {key}")
    print(f"  Project ID: {proj}")
    assert "bugsink.havano.cloud" in store_url
    assert key == "54ee3e24f4bd4da79ecd8336094a8312"
    assert proj == "4"
    print("  ✅ DSN parsing correct\n")

def test_config_loading():
    print("=== Config Loading ===")
    cfg = _load_config()
    print(f"  enabled:    {cfg.get('enabled')}")
    print(f"  dsn:        {cfg.get('dsn', '')[:50]}...")
    print(f"  env:        {cfg.get('environment')}")
    assert cfg.get("dsn"), "DSN should be loaded from bugsink_config.json"
    print("  ✅ Config loaded successfully\n")

def test_init_and_tags():
    print("=== Init & Tags ===")
    init_bugsink(version="2.0.8.40")
    set_user_context(username="test_user", role="admin")
    tags = _build_tags()
    print(f"  Tags: {tags}")
    assert tags.get("version") == "2.0.8.40"
    assert tags.get("os"), "OS tag should be set"
    print("  ✅ Tags built correctly\n")

def test_capture_exception():
    print("=== Capture Exception (LIVE SEND) ===")
    try:
        x = 1 / 0
    except ZeroDivisionError as e:
        event_id = capture_exception(e, extra={"test_run": True, "origin": "test_bugsink.py"})
        print(f"  Event ID: {event_id}")
        if event_id:
            print("  ✅ Exception queued for delivery")
        else:
            print("  ⚠️  Event was not queued (check if enabled)")
    print()

def test_capture_message():
    print("=== Capture Message (LIVE SEND) ===")
    event_id = capture_message(
        "Bugsink integration test — this is a test message from Havano POS",
        level="info",
        extra={"test_run": True, "origin": "test_bugsink.py"},
    )
    print(f"  Event ID: {event_id}")
    if event_id:
        print("  ✅ Message queued for delivery")
    else:
        print("  ⚠️  Message was not queued")
    print()

if __name__ == "__main__":
    test_dsn_parsing()
    test_config_loading()
    test_init_and_tags()
    test_capture_exception()
    test_capture_message()

    # Give the worker thread time to flush
    import time
    print("Waiting 5 seconds for background worker to deliver events...")
    time.sleep(5)
    shutdown()
    print("\n🎉 All tests passed! Check Bugsink dashboard at https://bugsink.havano.cloud")
