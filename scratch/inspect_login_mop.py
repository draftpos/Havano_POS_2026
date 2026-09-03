import json
import os
import sqlite3
import urllib.request
import ssl

def inspect_db_and_login():
    try:
        from database.db import get_connection
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT name, mop_type, gl_account, account_currency FROM modes_of_payment")
        mops = cur.fetchall()
        print("--- Local SQLite/SQL Server modes_of_payment table ---")
        for m in mops:
            print(" ", m)
            
        cur.execute("SELECT name, account_name, account_type, account_currency FROM gl_accounts WHERE is_group = 0 AND account_type IN ('Cash', 'Bank')")
        gls = cur.fetchall()
        print("\n--- Local gl_accounts (Cash/Bank) ---")
        for g in gls:
            print(" ", g)
            
        cur.execute("SELECT TOP 1 server_company_currency FROM company_defaults")
        row = cur.fetchone()
        print(f"\n--- company_defaults.server_company_currency: {row[0] if row else 'None'} ---")
        conn.close()
    except Exception as e:
        print("DB inspection error:", e)

if __name__ == "__main__":
    inspect_db_and_login()
