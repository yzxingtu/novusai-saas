import os
root='backend/app'
target='system-logs'
for dirpath, _, filenames in os.walk(root):
    for fname in filenames:
        if not fname.endswith('.py'):
            continue
        path=os.path.join(dirpath,fname)
        try:
            with open(path, encoding='utf-8') as f:
                if target in f.read():
                    print(path)
        except Exception:
            continue
