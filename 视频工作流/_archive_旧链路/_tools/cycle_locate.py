#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cycle_locate —— 真环定位：区分「顶层 import」与「函数内懒加载」

关键区分（depgraph 未做，故可能报假环）：
    顶层 import   → 模块加载时执行 → 会成真环（ImportError / 半初始化）
    函数内 import  → 调用时才执行 → 不成环，是合法的破环手段

用法:
    python3 cycle_locate.py           # 列真环（只算顶层边）
    python3 cycle_locate.py --all     # 同时列懒加载边（对比用）
    python3 cycle_locate.py --why X   # 看 X 参与了哪些边、是顶层还是懒加载

退出码: 有真环 = 1
"""
import ast
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def local_modules():
    return {f[:-3] for f in os.listdir(BASE)
            if f.endswith('.py') and not f.startswith('__')}


def edges_with_kind(mods):
    """-> {module: [(dep, kind)]}  kind = 'top' | 'lazy'"""
    out = {}
    for m in sorted(mods):
        p = os.path.join(BASE, m + '.py')
        try:
            tree = ast.parse(open(p, encoding='utf-8', errors='replace').read())
        except SyntaxError:
            out[m] = []
            continue
        # 顶层 import
        top = set()
        for n in tree.body:
            if isinstance(n, ast.Import):
                for a in n.names:
                    top.add(a.name.split('.')[0])
            elif isinstance(n, ast.ImportFrom):
                if n.module and n.level == 0:
                    top.add(n.module.split('.')[0])
        # 所有 import（含函数内）
        allimp = set()
        funcs = [n for n in tree.body
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for a in n.names:
                    allimp.add(a.name.split('.')[0])
            elif isinstance(n, ast.ImportFrom):
                if n.module and n.level == 0:
                    allimp.add(n.module.split('.')[0])
        # 判断归属：函数内(懒加载) / __main__ 守卫块 / 顶层(真边)
        lazy, mainblk = set(), set()
        franges = [(n.lineno, n.end_lineno) for n in funcs]
        mranges = []
        for n in tree.body:
            if isinstance(n, ast.If) and '__main__' in ast.dump(n.test):
                mranges.append((n.lineno, n.end_lineno))
        for n in ast.walk(tree):
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                tgt = (n.module.split('.')[0] if isinstance(n, ast.ImportFrom)
                       else n.names[0].name.split('.')[0])
                if any(a <= n.lineno <= b for a, b in mranges):
                    mainblk.add(tgt)
                elif any(a <= n.lineno <= b for a, b in franges):
                    lazy.add(tgt)
        res = []
        for d in sorted(allimp):
            if d not in mods or d == m:
                continue
            kind = ('main' if d in mainblk and d not in top
                    else 'lazy' if d in lazy and d not in top else 'top')
            res.append((d, kind))
        out[m] = res
    return out


def scc(graph):
    """Tarjan 强连通分量（size>=2 即环）；graph 为 {node: [succ]}"""
    idx, low, stack, on, res = {}, {}, [], set(), []
    counter = [0]

    def dfs(root):
        work = [(root, iter(graph.get(root, [])))]
        idx[root] = low[root] = counter[0]; counter[0] += 1
        stack.append(root); on.add(root)
        while work:
            v, it = work[-1]
            adv = False
            for w in it:
                if w not in graph:
                    continue
                if w not in idx:
                    idx[w] = low[w] = counter[0]; counter[0] += 1
                    stack.append(w); on.add(w)
                    work.append((w, iter(graph.get(w, []))))
                    adv = True
                    break
                elif w in on:
                    low[v] = min(low[v], idx[w])
            if adv:
                continue
            work.pop()
            if work:
                p = work[-1][0]
                low[p] = min(low[p], low[v])
            if low[v] == idx[v]:
                comp = []
                while True:
                    w = stack.pop(); on.discard(w); comp.append(w)
                    if w == v:
                        break
                if len(comp) > 1:
                    res.append(sorted(comp))
    for n in graph:
        if n not in idx:
            dfs(n)
    return res


def main():
    mods = local_modules()
    E = edges_with_kind(mods)
    args = sys.argv[1:]

    if '--why' in args:
        i = args.index('--why')
        tgt = args[i + 1] if i + 1 < len(args) else None
        if not tgt:
            print('用法: cycle_locate.py --why <模块>')
            return 2
        print(f'=== {tgt} 的出边 ===')
        for d, k in E.get(tgt, []):
            print(f'  {tgt} -> {d}   [{k}]')
        print(f'\n=== 谁依赖 {tgt} ===')
        for m in sorted(E):
            for d, k in E[m]:
                if d == tgt:
                    print(f'  {m} -> {tgt}   [{k}]')
        return 0

    top_g = {m: [d for d, k in E[m] if k == 'top'] for m in E}
    main_edges = [(m, d) for m in E for d, k in E[m] if k == 'main']
    all_g = {m: [d for d, k in E[m]] for m in E}

    real = scc(top_g)
    incl = scc(all_g)

    print(f'真环（只算顶层 import）: {len(real)} 个')
    for c in real:
        print('  ' + ' <-> '.join(c))
    print(f'\n__main__ 守卫内 import: {len(main_edges)} 条（被 import 时不执行，不成环）')
    for m, d in main_edges[:10]:
        print(f'  {m} -> {d}   [仅直接运行时]')
    print(f'\n含懒加载的环（depgraph 口径）: {len(incl)} 个')
    for c in incl:
        print('  ' + ' <-> '.join(c))
    fake = [c for c in incl if c not in real]
    print(f'\n假环（懒加载造成，不需破）: {len(fake)} 个')
    for c in fake:
        print('  ' + ' <-> '.join(c))
    if '--all' in args:
        print('\n=== 懒加载边明细 ===')
        n = 0
        for m in sorted(E):
            for d, k in E[m]:
                if k == 'lazy':
                    print(f'  {m} -> {d}  [懒加载]')
                    n += 1
        print(f'  共 {n} 条')
    return 1 if real else 0


if __name__ == '__main__':
    sys.exit(main())
