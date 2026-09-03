import os, glob

files = glob.glob(r'C:\Users\DELL\New_POS\Havano_POS_2026\views\**\*.py', recursive=True)

for full_path in files:
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        new_content = content
        
        # Replace <h2> with <div>
        new_content = new_content.replace("<h2 style=", "<div style=\"font-size: 24px; font-weight: bold; ")
        new_content = new_content.replace("</h2>", "</div>")
        
        # Replace <h3> with <div>
        new_content = new_content.replace("<h3 style=", "<div style=\"font-size: 18px; font-weight: bold; ")
        new_content = new_content.replace("</h3>", "</div>")
        
        # Replace <p> with <div>
        new_content = new_content.replace("<p style=", "<div style=")
        new_content = new_content.replace("</p>", "</div>")
        
        if new_content != content:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"Fixed {full_path}")
    except Exception as e:
        print(e)
