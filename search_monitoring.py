import os
root='backend/app'
target='/admin/monitoring'
for dirpath, _, filenames in os.walk(root):
    for fname in filenames:
        if not fname.endswith('.py'):
            continue
        path=os.path.join(dirpath,fname)
        try:
            with open(path, encoding='utf-8') as f:
                text=f.read()
        except Exception:
            continue
        if target in text:
            print(path)
