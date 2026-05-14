import os, re

results = []
for root, dirs, files in os.walk(r'd:\works\windsurf\expo-AI-CanvasPro\src'):
    for f in files:
        if f.endswith('.js'):
            path = os.path.join(root, f)
            try:
                c = open(path, 'r', encoding='utf-8').read()
                if 'handleFileDrop(' in c:
                    results.append(path)
            except:
                pass

for r in results:
    print(r)