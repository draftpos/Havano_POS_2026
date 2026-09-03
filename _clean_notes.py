from models.restaurant_order import get_predefined_notes

try:
    notes = get_predefined_notes()
    with open(r'c:\Users\DELL\New_POS\Havano_POS_2026\_predef_notes.txt', 'w', encoding='utf-8') as f:
        for n in notes:
            f.write(repr(n) + '\n')
            
            if '\u2261' in n or '\u0393' in n or '🍔' in n or '📌' in n:
                import pyodbc
                # Get conn using the standard module
                try:
                    from database import get_db_connection
                    conn = get_db_connection()
                except:
                    from models import get_db_connection
                    conn = get_db_connection()
                    
                clean_note = n.replace('\u2261\u0192\u00FB\u00E8', '')
                clean_note = clean_note.replace('\u2261\u0192\u00F4\u00EE', '')
                clean_note = clean_note.replace('🍔', '')
                clean_note = clean_note.replace('📌', '')
                clean_note = clean_note.replace('≡ƒùè', '')
                clean_note = clean_note.strip()
                
                cur = conn.cursor()
                cur.execute("UPDATE restaurant_predefined_notes SET note=? WHERE note=?", (clean_note, n))
                conn.commit()
                f.write(f"  Fixed to: {clean_note}\n")
except Exception as e:
    with open(r'c:\Users\DELL\New_POS\Havano_POS_2026\_predef_notes.txt', 'w', encoding='utf-8') as f:
        import traceback
        f.write(traceback.format_exc())
