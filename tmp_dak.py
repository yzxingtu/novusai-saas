import pathlib
needle='dakkii'
root=pathlib.Path('.')
paths=[]
for p in root.rglob('*'):
    if p.is_file():
        try:
            if needle.lower() in p.read_text(encoding='utf-8',errors='ignore').lower():
                paths.append(p)
        except Exception:
            pass
for p in paths:
    print(p)
