import os
root = 'frontend/apps/web-antd/src'
extensions = {'.ts','.vue','.json','.tsx','.js','.jsx'}
for dirpath, _, filenames in os.walk(root):
    for fname in filenames:
        if not any(fname.endswith(ext) for ext in extensions):
            continue
        path = os.path.join(dirpath, fname)
        try:
            with open(path, encoding='utf-8') as f:
                text = f.read()
        except Exception:
            continue
        if 'mdi:' in text:
            print(path)
