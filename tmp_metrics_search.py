import os
root='backend/app'
ignore_dirs={'backend/app/__pycache__'}
extensions={'.py'}
for dirpath, dirnames, filenames in os.walk(root):
    if any(part in ignore_dirs for part in dirpath.replace('\\','/').split('/') if part):
        continue
    for fname in filenames:
        if not any(fname.endswith(ext) for ext in extensions):
            continue
        path=os.path.join(dirpath,fname)
        try:
            with open(path,'r',encoding='utf-8') as f:
                text=f.read()
        except Exception:
            continue
        if 'metrics' in text.lower():
            print(path)
