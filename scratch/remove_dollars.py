with open(r'c:\Users\DELL\New_POS\Havano_POS_2026\views\main_window.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('f"${cashier_counted_sum:,.2f}"', 'f"{cashier_counted_sum:,.2f}"')
content = content.replace('f"${variance:,.2f}"', 'f"{variance:,.2f}"')
content = content.replace('f"${cashier_expected_sum:,.2f}"', 'f"{cashier_expected_sum:,.2f}"')
content = content.replace('f"${mode_counted:,.2f}"', 'f"{mode_counted:,.2f}"')
content = content.replace('f"${mode_variance:,.2f}"', 'f"{mode_variance:,.2f}"')
content = content.replace('f"${mode_expected:,.2f}"', 'f"{mode_expected:,.2f}"')

with open(r'c:\Users\DELL\New_POS\Havano_POS_2026\views\main_window.py', 'w', encoding='utf-8') as f:
    f.write(content)
