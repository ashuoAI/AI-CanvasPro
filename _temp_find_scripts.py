import re
content = open(r'd:\works\windsurf\expo-AI-CanvasPro\index.html', 'r', encoding='utf-8').read()
# Find the script tag
match = re.search(r'<script[^>]*src="([^"]+)"[^>]*>', content)
if match:
    print(f"Found: {match.group(0)}")
    print(f"Position: {match.start()}-{match.end()}")
    # Show context around the script tag
    start = max(0, match.start() - 50)
    end = min(len(content), match.end() + 50)
    print(f"Context: ...{content[start:end]}...")
else:
    print("No script tag found")
    # Search for main.js
    idx = content.find('main.js')
    if idx >= 0:
        print(f"main.js found at position {idx}")
        print(f"Context: ...{content[max(0,idx-50):idx+50]}...")