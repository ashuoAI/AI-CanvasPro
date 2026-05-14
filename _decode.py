import re

c = open(r'd:\works\windsurf\expo-AI-CanvasPro\src\modules\devEntry.js', 'r', encoding='utf-8').read()

# Find the string table
# The pattern is like: '0x132','hidden'
# Let's find all string mappings
matches = re.findall(r"'0x([0-9a-f]+)','([^']+)'", c)
string_map = {}
for hex_val, string_val in matches:
    string_map[int(hex_val, 16)] = string_val

# Print the ones we care about
for key in [0x110, 0x132, 0x138, 0x11b]:
    print(f"0x{key:x}: {string_map.get(key, 'NOT FOUND')}")