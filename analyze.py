import ast

filename = r'c:\Users\DELL\New_POS\Havano_POS_2026\views\new_d.py'
with open(filename, 'r', encoding='utf-8') as f:
    source = f.read()

tree = ast.parse(source)

classes = []
for node in ast.walk(tree):
    if isinstance(node, ast.ClassDef):
        methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
        classes.append({"name": node.name, "methods": methods})

print("Classes found:")
for c in classes:
    print(f"Class: {c['name']}")
    print(f"Methods: {', '.join(c['methods'][:10])}{'...' if len(c['methods']) > 10 else ''}")
