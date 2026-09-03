import sys
sys.path.insert(0, "c:\\Users\\DELL\\New_POS\\Havano_POS_2026")
from database.db import get_connection

try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID(N'[dbo].[stock_entries]') AND name = 'source_doc_no') BEGIN ALTER TABLE [dbo].[stock_entries] ADD [source_doc_no] NVARCHAR(100) NULL END")
    conn.commit()
    print("Database patched successfully!")
except Exception as e:
    print(f"Error: {e}")
