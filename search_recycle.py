import os
for dirpath, _, filenames in os.walk('backend'):
    for fname in filenames:
        if not fname.endswith('.py'):
            continue
        path=os.path.join(dirpath,fname)
        try:
            with open(path, encoding='utf-8') as f:
                if 'recycle-bin' in f.read():
                    print(path)
        except Exception:
            continue
