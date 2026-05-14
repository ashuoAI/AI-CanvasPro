c = open(r'd:\works\windsurf\expo-AI-CanvasPro\src\modules\devEntry.js', 'r', encoding='utf-8').read()
idx = c.find("document['createElement']")
print('Found at:', idx)
print(repr(c[idx:idx+300]))