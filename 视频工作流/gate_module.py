#!/usr/bin/env python3
"""模块体积门禁：单模块 ≤400 行 且 ≤12000 字符（约 128K 上下文的 30%）。
用法: python3 gate_module.py"""
import ast, os, sys
ROOT = os.path.dirname(os.path.abspath(__file__))
MAX_LINE, MAX_CHAR = 400, 12000
EXCL = ('_archive', '__pycache__', '.bak', '_bak')
bad, rows = [], []
for f in sorted(os.listdir(ROOT)):
    if not f.endswith('.py') or f.startswith('_gate') or f == 'gate_module.py': continue
    if any(x in f for x in EXCL): continue
    try: src = open(os.path.join(ROOT, f), encoding='utf-8').read()
    except Exception: continue
    if len(src) < 200: continue
    n = sum(1 for _ in src.split('\n'))
    if n > MAX_LINE or len(src) > MAX_CHAR:
        bad.append((f, n, len(src)))
    rows.append((n, len(src), f))
rows.sort(reverse=True)
print(f'活跃模块 {len(rows)} 个 | 阈值 {MAX_LINE}行/{MAX_CHAR}字符')
print('\n超标模块:')
if not bad: print('  （无）')
for f, n, c in sorted(bad, key=lambda x: -x[1]):
    print(f'  FAIL {f}: {n}行 / {c}字符')
print('\nTop10 体积:')
for n, c, f in rows[:10]:
    flag = 'FAIL' if (n > MAX_LINE or c > MAX_CHAR) else 'ok  '
    print(f'  {flag} {f}: {n}行 / {c}字符')
sys.exit(1 if bad else 0)
