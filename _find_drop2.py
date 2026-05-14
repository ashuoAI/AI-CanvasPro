import os, re

results = []
for root, dirs, files in os.walk(r'd:\works\windsurf\expo-AI-CanvasPro'):
    # Skip node_modules and .git
    if 'node_modules' in root or '.git' in root:
        continue
    for f in files:
        if f.endswith('.js') or f.endswith('.html') or f.endswith('.ts'):
            path = os.path.join(root, f)
            try:
                c = open(path, 'r', encoding='utf-8').read()
                if 'handleFileDrop' in c:
                    results.append(path)
            except:
                pass

for r in results:
    print(r)