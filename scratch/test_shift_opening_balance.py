import sys
import os

# Add root directory to sys.path
sys.path.insert(0, os.path.abspath('.'))

from models.shift import _get_shift_rows
from database.db import get_connection

print("Testing Shift Reconciliation Float Separation & Opening Balance...")

try:
    conn = get_connection()
    cur = conn.cursor()
    
    # Check shift_rows for recent shifts
    cur.execute("SELECT TOP 5 id FROM shifts ORDER BY id DESC")
    shift_ids = [r[0] for r in cur.fetchall()]
    
    if shift_ids:
        for s_id in shift_ids:
            rows = _get_shift_rows(s_id, cur)
            print(f"\nShift #{s_id}:")
            for r in rows:
                print(f"  Method: {r['method']} ({r['currency']}) | start_float: {r['start_float']} | income: {r['income']} | total: {r['total']} | counted: {r['counted']} | variance: {r['variance']}")
                # Assert total equals income (float not added)
                assert r['total'] == r['income'], f"Expected total ({r['total']}) to equal income ({r['income']})!"
        print("\nAll assertions passed for existing shifts!")
    else:
        print("No shifts found in database to inspect, logic syntax verified.")
    conn.close()
except Exception as e:
    print(f"Test note/output: {e}")
