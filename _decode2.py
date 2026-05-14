import re

c = open(r'd:\works\windsurf\expo-AI-CanvasPro\src\modules\devEntry.js', 'r', encoding='utf-8').read()

# Find the string table function
m = re.search(r"function a223_0x5cdb\(\)\{const _0x1e2b2c=\[(.+?)\];a223_0x5cdb=function", c)
if m:
    arr_str = m.group(1)
    # Split by commas, but be careful with quoted strings
    items = re.findall(r"'([^']*)'", arr_str)
    for i, item in enumerate(items):
        print(f"  {i}: '{item}'")
    print(f"\nTotal items: {len(items)}")
else:
    print("Not found")