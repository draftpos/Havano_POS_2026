import re, glob, os

files = [
    'views/reports/consumed_items_report_page.py',
    'views/reports/daily_profit_report.py',
    'views/reports/expense_list_report.py',
    'views/reports/detailed_inventory_ledger.py',
    'views/reports/summary_inventory_ledger.py',
    'views/reports/pos_reports.py'
]

pattern = re.compile(r'\s*try:\s*self\.(?:[a-zA-Z0-9_]+\.)?btn_apply\.clicked\.disconnect\(\)\s*except.*?:.*?pass', re.DOTALL)

for f in files:
    if os.path.exists(f):
        with open(f, 'r', encoding='utf-8') as file:
            content = file.read()
        
        new_content = pattern.sub('', content)
        
        if content != new_content:
            with open(f, 'w', encoding='utf-8') as file:
                file.write(new_content)
            print(f"Fixed {f}")
