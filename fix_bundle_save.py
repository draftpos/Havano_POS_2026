import re

path = 'views/dialogs/stock_file_dialog.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

# Replace _on_new bundle components logic
old_new_bundle = """                # Bundle Components
                if dlg.result_data.get('is_product_bundle') and 'bundle_components' in dlg.result_data:
                    try:
                        from models.product_bundle import create_bundle
                        create_bundle(dlg.result_data['name'], dlg.result_data['bundle_components'])
                    except Exception as e:
                        print(f"Error creating product bundle: {e}")"""

new_new_bundle = """                # Bundle Components
                if dlg.result_data.get('is_product_bundle') and 'bundle_components' in dlg.result_data:
                    try:
                        import json
                        from database.db import get_connection
                        lines_json = json.dumps(dlg.result_data['bundle_components'])
                        conn = get_connection()
                        cur = conn.cursor()
                        cur.execute("UPDATE products SET bundle_lines = ? WHERE part_no = ?", (lines_json, updated_p['part_no']))
                        conn.commit()
                        conn.close()
                    except Exception as e:
                        print(f"Error creating product bundle: {e}")"""

if old_new_bundle in text:
    text = text.replace(old_new_bundle, new_new_bundle)
    print("Replaced _on_new bundle logic")
else:
    print("Could not find _on_new bundle logic")

# Replace _on_modify bundle components logic
old_modify_bundle = """                # Bundle Components
                if dlg.result_data.get('is_product_bundle') and 'bundle_components' in dlg.result_data:
                    try:
                        from models.product_bundle import get_bundle_by_name, create_bundle, update_bundle
                        b = get_bundle_by_name(dlg.result_data['name'])
                        if b:
                            update_bundle(b['id'], dlg.result_data['name'], dlg.result_data['bundle_components'])
                        else:
                            create_bundle(dlg.result_data['name'], dlg.result_data['bundle_components'])
                    except Exception as e:
                        print(f"Error updating product bundle: {e}")"""

new_modify_bundle = """                # Bundle Components
                if dlg.result_data.get('is_product_bundle') and 'bundle_components' in dlg.result_data:
                    try:
                        import json
                        from database.db import get_connection
                        lines_json = json.dumps(dlg.result_data['bundle_components'])
                        conn = get_connection()
                        cur = conn.cursor()
                        cur.execute("UPDATE products SET bundle_lines = ? WHERE part_no = ?", (lines_json, updated_p['part_no']))
                        conn.commit()
                        conn.close()
                    except Exception as e:
                        print(f"Error updating product bundle: {e}")"""

if old_modify_bundle in text:
    text = text.replace(old_modify_bundle, new_modify_bundle)
    print("Replaced _on_modify bundle logic")
else:
    print("Could not find _on_modify bundle logic")

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)
print("Done")
