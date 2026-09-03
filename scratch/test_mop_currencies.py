import sys, os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from database.db import get_connection, fetchall_dicts

try:
    conn = get_connection()
    cur = conn.cursor()
    
    print("--- MODES OF PAYMENT ---")
    cur.execute("SELECT id, name, gl_account, account_currency, enabled FROM modes_of_payment")
    mops = fetchall_dicts(cur)
    for m in mops:
        print(f"MOP ID: {m.get('id')}, Name: '{m.get('name')}', GL: '{m.get('gl_account')}', Currency: '{m.get('account_currency')}', Enabled: {m.get('enabled')}")
        
    print("\n--- SHIFT ROWS IN ACTIVE OR RECENT SHIFTS ---")
    cur.execute("SELECT TOP 20 id, shift_id, method, currency, start_float, income, counted FROM shift_rows ORDER BY id DESC")
    srows = fetchall_dicts(cur)
    for r in srows:
        print(f"ShiftRow ID: {r.get('id')}, Shift: #{r.get('shift_id')}, Method: '{r.get('method')}', Currency: '{r.get('currency')}', Income: {r.get('income')}")

    print("\n--- PAYMENT ENTRIES ---")
    cur.execute("SELECT TOP 20 id, shift_id, mode_of_payment, received_amount, currency, paid_to FROM payment_entries ORDER BY id DESC")
    pes = fetchall_dicts(cur)
    for p in pes:
        print(f"PE ID: {p.get('id')}, Shift: #{p.get('shift_id')}, Method: '{p.get('mode_of_payment')}', Amount: {p.get('received_amount')}, Currency: '{p.get('currency')}', PaidTo: '{p.get('paid_to')}'")

    conn.close()
except Exception as e:
    print(f"Error: {e}")
