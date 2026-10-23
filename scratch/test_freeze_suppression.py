import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.bugsink_service import is_network_or_suppressed_error

msg = "Freeze alert: 5.0s at [Startup] -> tenant_reset.py:256 'cur.execute(\"EXEC sp_MSforeachtable 'ALTER TABLE ? NOCHECK CONSTRAINT ALL'\")'"
is_suppressed = is_network_or_suppressed_error(msg)
print('is_suppressed (should be True):', is_suppressed)
assert is_suppressed is True, 'Error: Message not suppressed!'

print('All suppression assertions passed!')
