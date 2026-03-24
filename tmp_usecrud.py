import os
root = 'frontend/apps/web-antd/src'
target = 'useCrudDrawer'
for dirpath, dirnames, filenames in os.walk(root):
    if 'dist' in dirpath:
        continue
    for fname in filenames:
        if not fname.endswith(('.ts','.vue')):
            continue
        path = os.path.join(dirpath, fname)
        try:
            with open(path, encoding='utf-8') as f:
                text = f.read()
        except Exception:
            continue
        if target in text:
            print(path)
