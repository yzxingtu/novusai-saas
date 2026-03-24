import os
root='frontend'
for dirpath, dirnames, filenames in os.walk(root):
    for fname in filenames:
        if fname.endswith('menu.json'):
            print(os.path.join(dirpath, fname))
