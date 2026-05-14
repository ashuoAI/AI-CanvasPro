import re

c = open(r'd:\works\windsurf\expo-AI-CanvasPro\src\modules\previewUploadEntry.js', 'r', encoding='utf-8').read()

# Find the string table
m = re.search(r"function a291_0x3ed5\(\)\{const _0x1e2b2c=\[(.+?)\];a291_0x3ed5=function", c)
if m:
    arr_str = m.group(1)
    items = re.findall(r"'([^']*)'", arr_str)
    for i, item in enumerate(items):
        print(f"  {i}: '{item}'")
    print(f"\nTotal items: {len(items)}")
else:
    print("Not found - trying alternative pattern")
    m = re.search(r"function a291_0x3ed5\(\)\{const _0x[0-9a-f]+=\[(.+?)\];a291_0x3ed5=function", c)
    if m:
        arr_str = m.group(1)
        items = re.findall(r"'([^']*)'", arr_str)
        for i, item in enumerate(items):
            print(f"  {i}: '{item}'")
    else:
        print("Still not found")