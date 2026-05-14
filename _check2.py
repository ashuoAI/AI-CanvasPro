c = open(r'd:\works\windsurf\expo-AI-CanvasPro\src\modules\previewUploadEntry.js', 'r', encoding='utf-8').read()

# Find the click handler
idx = c.find("setAttribute('multiple'")
if idx >= 0:
    print("Found setAttribute('multiple' at:", idx)
    print(repr(c[max(0,idx-200):idx+200]))
else:
    print("setAttribute('multiple' not found")
    # Try finding 'multiple' 
    idx = c.find('multiple')
    print("'multiple' found at:", idx)
    if idx >= 0:
        print(repr(c[max(0,idx-200):idx+200]))