from models.database import get_db_connection

conn = get_db_connection()
cur = conn.cursor()
try:
    cur.execute("SELECT id, note FROM restaurant_predefined_notes")
    rows = cur.fetchall()
    
    with open(r'c:\Users\DELL\New_POS\Havano_POS_2026\_predef_notes.txt', 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(repr(r) + '\n')
            
            # If it's mojibake, clean it up!
            if '\u2261' in r[1] or '\u0393' in r[1]:
                clean_note = r[1].replace('\u2261\u0192\u00FB\u00E8', '🍔')
                clean_note = clean_note.replace('\u2261\u0192\u00F4\u00EE', '📌')
                clean_note = clean_note.replace('\u0393\u00A3\u00F4', 'OK')
                clean_note = clean_note.replace('\u0393\u00AE\u00BF', 'KB')
                clean_note = clean_note.replace('\u0393\u00A3\u00F2', 'Clear')
                # Actually, let's just strip all the mojibake entirely. The user doesn't want it: "please dont".
                # Wait, they asked "what are these signs here... please dont"
                # Let's just remove the emojis. They don't want them.
                clean_note = r[1].replace('\u2261\u0192\u00FB\u00E8', '')
                clean_note = clean_note.replace('\u2261\u0192\u00F4\u00EE', '')
                clean_note = clean_note.replace('🍔', '')
                clean_note = clean_note.replace('📌', '')
                clean_note = clean_note.strip()
                
                f.write(f"  Fixed to: {clean_note}\n")
                
                upd = conn.cursor()
                upd.execute("UPDATE restaurant_predefined_notes SET note=? WHERE id=?", (clean_note, r[0]))
                conn.commit()

except Exception as e:
    with open(r'c:\Users\DELL\New_POS\Havano_POS_2026\_predef_notes.txt', 'w', encoding='utf-8') as f:
        f.write(str(e))
