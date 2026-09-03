import pyodbc
from database.db import get_connection

conn = get_connection()
cursor = conn.cursor()

def print_cols(table):
    try:
        cols = [col[0] for col in cursor.execute(f"SELECT name FROM sys.columns WHERE object_id = OBJECT_ID('{table}')").fetchall()]
        print(f"{table}: {cols}")
    except Exception as e:
        print(f"Error {table}: {e}")

print_cols('sales_invoices')
print_cols('sales_invoice_items')
print_cols('products')
print_cols('company_defaults')
print_cols('stock_entries')
print_cols('stock_entry_items')
