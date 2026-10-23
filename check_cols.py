from database.db import get_connection
import re

conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'company_defaults'")
live_cols = [r[0].lower() for r in cur.fetchall()]
conn.close()

with open('setup_database.py', 'r', encoding='utf-8') as f:
    setup_code = f.read()

alter_cols = re.findall(r'ALTER TABLE company_defaults ADD\s+(\w+)', setup_code, re.IGNORECASE)
alter_cols = [c.lower() for c in alter_cols]

match = re.search(r'CREATE TABLE company_defaults\s*\((.*?)\)', setup_code, re.DOTALL | re.IGNORECASE)
setup_cols = []
if match:
    for line in match.group(1).split('\n'):
        line = line.strip().strip(',')
        if line and not line.startswith('--') and not line.startswith('PRIMARY KEY') and not line.startswith('CONSTRAINT'):
            parts = line.split()
            if parts:
                setup_cols.append(parts[0].lower())

all_setup_cols = set(setup_cols + alter_cols)

print(f"Total Live Columns: {len(live_cols)}")
print(f"Total Setup Columns: {len(all_setup_cols)}")

missing_in_setup = [c for c in live_cols if c not in all_setup_cols]
print(f"Live columns missing in setup_database.py: {missing_in_setup}")

with open('models/company_defaults.py', 'r', encoding='utf-8') as f:
    model_code = f.read()

needed_tuples = re.findall(r'\("(\w+)",\s*"([^"]+)"\)', model_code)
print(f"Columns in models/company_defaults needed list: {needed_tuples}")
