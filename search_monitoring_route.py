import os
root='frontend'
target='/admin/system-maintenance/monitoring'
for dirpath, dirnames, filenames in os.walk(root):
    for fname in filenames:
        if not fname.endswith(('.ts','.vue','.json')):
            continue
        path=os.path.join(dirpath,fname)
        try:
            with open(path, encoding='utf-8') as f:
                text=f.read()
        except Exception:
            continue
        if target in text:
            print(path)
