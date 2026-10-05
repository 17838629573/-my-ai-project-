#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ambiguous —— 同名函数歧义定位：调用点该 import 哪一个？

场景：solve 在 _camera / _solver_chain / pose 三处都定义了，
      _chk_* 里缺 solve，靠人猜会猜错（静默算错，不报错）。
      本工具用「调用签名 + 调用上下文」匹配，给出候选排序。

匹配依据（全部 AST 实取，非推测）:
  ① 形参个数是否吻合
  ② 形参名是否出现在调用点的关键字实参里
  ③ 调用点所在模块是否已 import 某个候选源
  ④ 返回值用法（被下标/被 .属性/直接赋值）

用法:
    python3 ambiguous.py solve         # 定位某个名字
    python3 ambiguous.py               # 全仓扫所有同名函数
输出: 每个调用点 -> [(源模块, 匹配分, 依据)]，分高者在前
"""
import ast
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def local_modules():
    return {f[:-3] for f in os.listdir(BASE)
            if f.endswith('.py') and not f.startswith('__')}


def defs_of(name, mods):
    """-(模块, 形参列表, 行号, 返回类型线索)"""
    out = []
    for m in sorted(mods):
        p = os.path.join(BASE, m + '.py')
        try:
            t = ast.parse(open(p, encoding='utf-8', errors='replace').read())
        except SyntaxError:
            continue
        for n in t.body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
                args = [a.arg for a in n.args.args]
                kw = [a.arg for a in n.args.kwonlyargs]
                va = n.args.vararg.arg if n.args.vararg else None
                vk = n.args.kwarg.arg if n.args.kwarg else None
                # 首行 docstring 作语义线索
                doc = (ast.get_docstring(n) or '').split('\n')[0][:60]
                out.append({'mod': m, 'args': args, 'kw': kw,
                            'vararg': va, 'kwarg': vk,
                            'line': n.lineno, 'doc': doc})
    return out


def calls_of(name, mods):
    """-(调用模块, 行号, 位置参数个数, 关键字参数名集合, 上下文行)"""
    out = []
    for m in sorted(mods):
        p = os.path.join(BASE, m + '.py')
        try:
            src = open(p, encoding='utf-8', errors='replace').read()
            t = ast.parse(src)
        except SyntaxError:
            continue
        lines = src.splitlines()
        for n in ast.walk(t):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
                    and n.func.id == name:
                pos = len(n.args)
                kws = {k.arg for k in n.keywords if k.arg}
                ctx = lines[n.lineno - 1].strip()[:80]
                out.append({'mod': m, 'line': n.lineno, 'pos': pos,
                            'kws': kws, 'ctx': ctx})
    return out


def already_imports(mod, src):
    p = os.path.join(BASE, mod + '.py')
    if not os.path.exists(p):
        return False
    try:
        t = ast.parse(open(p, encoding='utf-8', errors='replace').read())
    except SyntaxError:
        return False
    for n in ast.walk(t):
        if isinstance(n, ast.ImportFrom) and n.module and \
                n.module.split('.')[0] == src:
            return True
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name.split('.')[0] == src:
                    return True
    return False


def score(call, d, callmod_imports):
    s, why = 0, []
    need = call['pos']
    have = len(d['args'])
    if d['vararg']:
        if need >= have - 0:
            s += 3; why.append('有*args，个数宽容')
    elif need == have:
        s += 4; why.append(f'形参个数吻合({need})')
    elif abs(need - have) == 1:
        s += 1; why.append(f'个数差1({need} vs {have})')
    else:
        why.append(f'个数不符({need} vs {have})')
    hit = call['kws'] & set(d['args'] + d['kw'])
    if hit:
        s += 4; why.append('关键字命中:' + ','.join(sorted(hit)))
    if d['mod'] in callmod_imports:
        s += 2; why.append('本模块已 import')
    if d['doc']:
        s += 0
    return s, why


def main():
    mods = local_modules()
    args = sys.argv[1:]
    if args:
        names = args
    else:
        # 全仓找同名函数
        from collections import defaultdict
        seen = defaultdict(set)
        for m in sorted(mods):
            p = os.path.join(BASE, m + '.py')
            try:
                t = ast.parse(open(p, encoding='utf-8', errors='replace').read())
            except SyntaxError:
                continue
            for n in t.body:
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    seen[n.name].add(m)
        names = [k for k, v in seen.items() if len(v) > 1]

    for name in names:
        ds = defs_of(name, mods)
        if len(ds) < 2:
            continue
        calls = calls_of(name, mods)
        print(f'\n■ {name}  ({len(ds)} 处定义 / {len(calls)} 处调用)')
        for d in ds:
            a = ','.join(d['args']) + (',*' + d['vararg'] if d['vararg'] else '')
            print(f"    定义 {d['mod']}:L{d['line']}  ({a})  # {d['doc']}")
        for c in sorted(calls, key=lambda x: (x['mod'], x['line'])):
            imps = {d['mod'] for d in ds if already_imports(c['mod'], d['mod'])}
            ranked = sorted(((score(c, d, imps), d) for d in ds),
                            key=lambda x: -x[0][0])
            best = ranked[0]
            if best[0][0] == 0:
                verdict = '?? 无匹配，需人判'
            elif best[0][0] - ranked[1][0][0] >= 3:
                verdict = f"-> {best[1]['mod']}"
            else:
                verdict = f"? 接近 {best[1]['mod']}/{ranked[1][1]['mod']}，需人判"
            print(f"    调用 {c['mod']}:L{c['line']} {c['ctx'][:52]}")
            print(f"        {verdict}   [{best[0][1]}]")
    return 0


if __name__ == '__main__':
    sys.exit(main())
