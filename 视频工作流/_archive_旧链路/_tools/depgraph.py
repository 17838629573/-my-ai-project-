#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""depgraph —— 依赖图生成器（轻量·纯标准库·取代手工维护 deps.md）

背景：deps.md 由 deps_sync.py 生成，但改了 import 不重跑就会漂移。
      本工具把「图」和「校验」合一：图永远由源码反推，且能查出漂移。

用法:
    python3 depgraph.py            # 重生成 deps.md + deps.mmd（文本 + mermaid）
    python3 depgraph.py --check    # 只校验：图是否与源码一致，不符退出码 1（接门禁）
    python3 depgraph.py --cycles   # 只列循环依赖
    python3 depgraph.py --layers   # 只列跨大模块依赖（分层违规候选）

产出:
    deps.md    分层文本表（兼容原格式）
    deps.mmd   mermaid 图（可粘进 markdown 渲染）

原理: AST 扫 import → 只留本仓模块 → Tarjan 找 SCC(环) → 拓扑分层 → 落盘
"""
import ast
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 工作流根（本工具在 _tools/）

EXTERNAL = {'os','sys','json','math','numpy','np','cv2','re','time','random',
            'collections','itertools','functools','typing','dataclasses','pathlib',
            'subprocess','shutil','glob','abc','enum','copy','csv','struct',
            'builtins','io','pickle','hashlib','textwrap'}

# 破环白名单（硬编码最小集，须附理由）
BREAK = {('solver_check','solver')}


def local_modules():
    return {f[:-3] for f in os.listdir(BASE)
            if f.endswith('.py') and not f.startswith('__')}


def build():
    mods = local_modules()
    deps = {}
    for m in sorted(mods):
        p = os.path.join(BASE, m + '.py')
        try:
            t = ast.parse(open(p, encoding='utf-8', errors='replace').read())
        except SyntaxError:
            deps[m] = []
            continue
        out = set()
        for n in ast.walk(t):
            if isinstance(n, ast.Import):
                for a in n.names:
                    out.add(a.name.split('.')[0])
            elif isinstance(n, ast.ImportFrom):
                if n.module and n.level == 0:
                    out.add(n.module.split('.')[0])
        deps[m] = sorted(x for x in out
                         if x in mods and x != m and (m, x) not in BREAK)
    return deps


def lazy_edges(deps_all):
    """非顶层 import 的边（函数内 / __main__ 内），被 import 时不执行"""
    out = []
    for m, xs in deps_all.items():
        top = set(top_level_deps().get(m, []))
        for x in xs:
            if x not in top:
                out.append((m, x))
    return out


def top_level_deps():
    """只取顶层 import（函数内懒加载 / __main__ 守卫内的不算）
    依据：懒加载与 __main__ 守卫在模块被 import 时不执行，不构成真环。
    """
    mods = local_modules()
    out = {}
    for m in sorted(mods):
        p = os.path.join(BASE, m + '.py')
        try:
            tree = ast.parse(open(p, encoding='utf-8', errors='replace').read())
        except SyntaxError:
            out[m] = []
            continue
        top = set()
        for n in tree.body:
            if isinstance(n, ast.Import):
                for a in n.names:
                    top.add(a.name.split('.')[0])
            elif isinstance(n, ast.ImportFrom):
                if n.module and n.level == 0:
                    top.add(n.module.split('.')[0])
        # 排除 __main__ 守卫内的
        mr = [(n.lineno, n.end_lineno) for n in tree.body
              if isinstance(n, ast.If) and '__main__' in ast.dump(n.test)]
        top = {d for d in top
               if not any(a <= l <= b for a, b in mr
                          for l in [0])}  # 占位，实际用下法
        keep = set()
        for n in tree.body:
            if isinstance(n, ast.Import):
                for a in n.names:
                    if not any(a_ <= n.lineno <= b_ for a_, b_ in mr):
                        keep.add(a.name.split('.')[0])
            elif isinstance(n, ast.ImportFrom):
                if n.module and n.level == 0:
                    if not any(a_ <= n.lineno <= b_ for a_, b_ in mr):
                        keep.add(n.module.split('.')[0])
        out[m] = sorted(d for d in keep if d in mods and d != m
                        and (m, d) not in BREAK)
    return out


def tarjan(deps):
    """Tarjan SCC：size>=2 的强连通分量即循环依赖"""
    index = {}
    low = {}
    stack = []
    on = set()
    res = []
    counter = [0]

    def strong(m):
        work = [(m, iter(deps[m]))]
        index[m] = low[m] = counter[0]; counter[0] += 1
        stack.append(m); on.add(m)
        while work:
            v, it = work[-1]
            adv = False
            for w in it:
                if w not in deps:
                    continue
                if w not in index:
                    index[w] = low[w] = counter[0]; counter[0] += 1
                    stack.append(w); on.add(w)
                    work.append((w, iter(deps[w])))
                    adv = True
                    break
                elif w in on:
                    low[v] = min(low[v], index[w])
            if adv:
                continue
            work.pop()
            if work:
                p = work[-1][0]
                low[p] = min(low[p], low[v])
            if low[v] == index[v]:
                comp = []
                while True:
                    w = stack.pop(); on.discard(w); comp.append(w)
                    if w == v:
                        break
                if len(comp) > 1:
                    res.append(sorted(comp))
        return res

    for m in deps:
        if m not in index:
            strong(m)
    return res


def topo(deps):
    """拓扑深度；有环的归到环内最大深度"""
    depth = {}
    for _ in range(20):
        ch = False
        for m in deps:
            d = 0
            for x in deps[m]:
                if x in depth:
                    d = max(d, depth[x] + 1)
            if depth.get(m) != d:
                depth[m] = d; ch = True
        if not ch:
            break
    return depth


def layer_of(m):
    """从 hier.py 取大模块归属；取不到返回 None"""
    try:
        sys.path.insert(0, BASE)
        from hier import HIER, TOP
        for L, ms in HIER.items():
            for M, ss in ms.items():
                if m in ss:
                    return L
        for L, ts in TOP.items():
            if m in ts:
                return L
    except Exception:
        pass
    return None


def render_text(deps, depth, cycles, lazy=None):
    """deps 应为顶层真边；lazy 边以 # 注释列出（enforce 解析时会跳过注释）"""
    L = ['# deps.md — 模块依赖登记表',
         '# 由 depgraph.py 自动从源码 import 反推，禁止手填',
         '# 改了任何 import 后重跑: python3 depgraph.py',
         '# 校验是否漂移: python3 depgraph.py --check',
         '']
    by = {}
    for m, d in depth.items():
        by.setdefault(d, []).append(m)
    for d in sorted(by):
        L.append(f'# L{d}' + (' 原子层（无本项目依赖）' if d == 0 else ''))
        for m in sorted(by[d]):
            v = deps[m]
            L.append(f'{m} -> ' + (', '.join(v) if v else '(无)'))
        L.append('')
    if lazy:
        L.append('# 懒加载边：函数内 / __main__ 内 import，被 import 时不执行，不构成环')
        for a, b in sorted(lazy):
            L.append(f'{a} -> {b} [runtime]')
        L.append('')
    if cycles:
        L.append('# 循环依赖（SCC，基于顶层真边）')
        for c in cycles:
            L.append('  CYCLE: ' + ' <-> '.join(c))
        L.append('')
    L.append(f'# 模块 {len(deps)} 个 | 边 {sum(len(v) for v in deps.values())} 条 '
             f'| 环 {len(cycles)} 个')
    return '\n'.join(L) + '\n'


def render_mmd(deps, depth):
    L = ['```mermaid', 'graph TD']
    for m in sorted(deps):
        lay = layer_of(m) or '?'
        for x in deps[m]:
            L.append(f'  {m} --> {x}')
    L.append('```')
    # 分层子图
    by = {}
    for m in sorted(deps):
        by.setdefault(layer_of(m) or 'OTHER', []).append(m)
    M = ['', '## 分层归属', '']
    for k in sorted(by):
        M.append(f'- **{k}** ({len(by[k])}): ' + ', '.join(by[k]))
    return '\n'.join(L) + '\n' + '\n'.join(M) + '\n'


def main():
    deps = build()
    cycles = tarjan(top_level_deps())   # 真环：只算顶层 import
    depth = topo(deps)
    args = sys.argv[1:]

    if '--cycles' in args:
        print(f'循环依赖 {len(cycles)} 个')
        for c in cycles:
            print('  ' + ' <-> '.join(c))
        return 1 if cycles else 0

    if '--layers' in args:
        cross = []
        for m in sorted(deps):
            a = layer_of(m)
            for x in deps[m]:
                b = layer_of(x)
                if a and b and a != b:
                    cross.append(f'{m}({a}) -> {x}({b})')
        print(f'跨大模块依赖 {len(cross)} 条')
        for c in cross[:40]:
            print('  ' + c)
        if len(cross) > 40:
            print(f'  … 另 {len(cross)-40} 条')
        return 0

    txt = render_text(top_level_deps(), depth, cycles, lazy_edges(deps))
    if '--check' in args:
        p = os.path.join(BASE, 'deps.md')
        if not os.path.exists(p):
            print('FAIL deps.md 不存在，跑 python3 depgraph.py 生成')
            return 1
        old = open(p, encoding='utf-8').read()
        # 比对正文（跳过前 4 行注释头）
        norm = lambda s: '\n'.join(l for l in s.splitlines()
                                   if l.strip() and not l.startswith('# 由')
                                   and not l.startswith('# 校验')
                                   and not l.startswith('# 改了'))
        if norm(old) == norm(txt):
            print(f'PASS 依赖图与源码一致（{len(deps)} 模块）')
            return 0
        print('FAIL 依赖图已漂移，跑 python3 depgraph.py 重新生成')
        import difflib
        for l in list(difflib.unified_diff(norm(old).splitlines(),
                                            norm(txt).splitlines(),
                                            'deps.md', '源码实际', lineterm=''))[:30]:
            print('  ' + l)
        return 1

    open(os.path.join(BASE, 'deps.md'), 'w', encoding='utf-8').write(txt)
    open(os.path.join(BASE, 'deps.mmd'), 'w', encoding='utf-8').write(
        render_mmd(deps, depth))
    print(f'[OK] deps.md + deps.mmd 已重生成  '
          f'{len(deps)} 模块 / {sum(len(v) for v in deps.values())} 边 / {len(cycles)} 环')
    return 0


if __name__ == '__main__':
    sys.exit(main())
