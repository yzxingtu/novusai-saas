import os
root='backend'
target='NovusPluginShared'
for dirpath, _, filenames in os.walk(root):
    for fname in filenames:
        if not fname.endswith(('.py','.ts','.vue','.json')):
            continue
        path=os.path.join(dirpath,fname)
        try:
            text=open(path,encoding='utf-8').read()
        except Exception:
            continue
        if target in text:
            print(path)
