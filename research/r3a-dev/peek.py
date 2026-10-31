import json, sys
d = json.load(open(sys.argv[1]))
def show(x, depth=0, key='root'):
    pad = '  ' * depth
    if isinstance(x, dict):
        print(f'{pad}{key}: dict {list(x)[:12]}')
        if depth < 3:
            for k in list(x)[:4]: show(x[k], depth + 1, k)
    elif isinstance(x, list):
        print(f'{pad}{key}: list len {len(x)}')
        if x and depth < 3: show(x[0], depth + 1, '[0]')
    else:
        print(f'{pad}{key}: {str(x)[:80]}')
show(d)
