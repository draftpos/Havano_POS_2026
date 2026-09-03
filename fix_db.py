import sys
import pyodbc
import json
import os

db_path = "c:\\Users\\DELL\\New_POS\\Havano_POS_2026\\database\\sql_settings.json"
try:
    with open(db_path, "r") as f:
        settings = json.load(f)
    conn_str = f"DRIVER={{{settings['driver']}}};SERVER={settings['server']};DATABASE={settings['database']};UID={settings['username']};PWD={settings['password']}"
    conn = pyodbc.connect(conn_str)
    cur = conn.cursor()
    cur.execute("IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID(N'[dbo].[stock_entries]') AND name = 'source_doc_no') BEGIN ALTER TABLE [dbo].[stock_entries] ADD [source_doc_no] NVARCHAR(100) NULL END")
    conn.commit()
    print("Database patched successfully!")
except Exception as e:
    print(f"Error: {e}")
