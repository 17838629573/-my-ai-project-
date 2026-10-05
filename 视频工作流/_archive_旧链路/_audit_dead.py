import ast, os, sys, re
from collections import defaultdict

files = sorted(f for f in os.listdir('.') if f.endswith('.py'))
imports = defaultdict(set)   # module -> set of referrers
for f in files:
    try:
        t = ast.parse(open(f, encoding='utf-8').read())
    except Exception as e:
        print(f'PARSE-FAIL {f}: {e}'); continue
    mods = set()
    for n in ast.walk(t):
        if isinstance(n, ast.Import):
            for a in n.names: mods.add(a.name.split('.')[0])
        elif isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module.split('.')[0])
    for m in mods:
        imports[m].add(f)
    # sys.path.insert / exec / __import__ 动态
    src = open(f, encoding='utf-8').read()
    if re.search(r'__import__|importlib|exec\(', src):
        imports['<dynamic>'].add(f)

# 也扫描 md 里提到的模块名（文档引用不算活）
print('=== 未被任何 py 文件 import 的模块 ===')
dead = []
for f in files:
    name = f[:-3]
    refs = imports.get(name, set()) - {f}
    if not refs:
        dead.append(f)
print(f'共 {len(dead)} 个:')
for d in dead: print('  ', d)

print()
print('=== 仅被自己/自检引用的 ===')
semi = []
for f in files:
    name = f[:-3]
    refs = imports.get(name, set()) - {f}
    refs = {r for r in refs if 'check' not in r and 'audit' not in r and 'enforce' not in r}
    if not refs:
        semi.append((f, imports.get(name, set()) - {f}))
for f, r in semi: print('  ', f, '<-', sorted(r))
