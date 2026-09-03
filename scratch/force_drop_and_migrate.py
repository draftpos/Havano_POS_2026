import sys
import os
sys.path.insert(0, os.path.abspath("."))

import logging
logging.basicConfig(level=logging.INFO)

print("=" * 60)
print("[FORCE RESET] Dropping all database tables completely...")
print("=" * 60)

from database.tenant_reset import drop_all_tables_completely
summary = drop_all_tables_completely()
print(f"[FORCE RESET] Drop result: {summary}")

print("\n" + "=" * 60)
print("[FORCE RESET] Running setup_database.py migrations from scratch...")
print("=" * 60)

import setup_database
setup_database.run()

print("\n" + "=" * 60)
print("[FORCE RESET] Database completely dropped and re-migrated successfully!")
print("=" * 60)
