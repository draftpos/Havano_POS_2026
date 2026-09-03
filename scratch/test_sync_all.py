import sys, os
sys.path.insert(0, os.path.abspath("."))
from services.pos_upload_service import push_unsynced_sales

print("Running push_unsynced_sales()...")
res = push_unsynced_sales()
print("push_unsynced_sales Result:", res)
