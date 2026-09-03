import codecs
import re

path = r'c:\Users\DELL\New_POS\Havano_POS_2026\views\pages\company_defaults_page.py'
content = codecs.open(path, 'r', 'utf-8').read()

new_content = re.sub(r'"TIN Number[^"]*"', '"TIN Number"', content)

codecs.open(path, 'w', 'utf-8').write(new_content)
print('Replaced TIN emojis in company defaults!')
