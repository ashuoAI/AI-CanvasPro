import re

c = open(r'd:\works\windsurf\expo-AI-CanvasPro\src\modules\previewUploadEntry.js', 'r', encoding='utf-8').read()

# Find all function definitions
funcs = re.findall(r'function\s+(a291_\w+)', c)
print("Functions:", funcs)

# Find the string table function - it's the one that returns an array
m = re.search(r'function\s+(a291_\w+)\s*\(\s*\)\s*\{\s*(?:const|var)\s+\w+=\[(.+?)\];\1=function', c)
if m:
    print("Found:", m.group(1))
    arr_str = m.group(2)
    items = re.findall(r"'([^']*)'", arr_str)
    for i, item in enumerate(items):
        print(f"  {i}: '{item}'")
    print(f"\nTotal items: {len(items)}")
else:
    print("Pattern 1 not found")
    # Try alternative
    m = re.search(r'function\s+(a291_\w+)\s*\(\s*\)\s*\{.+?\[(.+?)\];\1=function', c, re.DOTALL)
    if m:
        print("Found with DOTALL:", m.group(1))
        print(repr(m.group(2)[:500]))
    else:
        print("Pattern 2 not found")