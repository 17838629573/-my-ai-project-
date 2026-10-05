#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""undef_check —— 未定义名检测（漏 import / 名字凭空出现）

背景：本项目已有 2 处同类 bug
  ① render_v4_main.py 用 systems.REAL_HEIGHT_M / actors.ACTORS 但未 import → NameError
  ② _chk_base.py 用 solve 但未 import → 56 项自检从未真跑通
本工具用 AST 全仓扫描，一次性把这类问题全部找出来。

原理：
  收集每个模块的「已绑定名」= 顶层 def/class/赋值/import + 函数内的
  参数、局部赋值、for 目标、with-as、except-as、推导式变量、global 声明
  再收集「被读取的 Name(Load)」，差集即未定义名
  最后在全仓查该名字是否在别处定义 → 输出「应从哪 import」

纯 AST，不执行被检文件（组内有 top-level 副作用的脚本，import 会炸）。

用法:
    python3 undef_check.py                 # 全仓
    python3 undef_check.py render_v4_main  # 单模块
    python3 undef_check.py --fixable       # 只列「能从别处 import」的（可机械修）
"""
import ast
import builtins
import os
import sys
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 工作流根（本工具在 _tools/）
BUILTINS = set(dir(builtins)) | {'__file__','__name__','__doc__','__package__','__loader__','__spec__','__builtins__','__path__','__all__','__debug__'}


def local_modules():
    return {f[:-3] for f in os.listdir(BASE) if f.endswith(".py")}


def bound_names(tree):
    """文件内所有已绑定名（含函数作用域）"""
    b = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Lambda):
            a = n.args
            for x in list(a.posonlyargs) + list(a.args) + list(a.kwonlyargs):
                b.add(x.arg)
            if a.vararg:
                b.add(a.vararg.arg)
            if a.kwarg:
                b.add(a.kwarg.arg)
            continue
        if isinstance(n, ast.ClassDef):
            b.add(n.name)
            for d in n.decorator_list:
                for sub in ast.walk(d):
                    if isinstance(sub, ast.Name):
                        b.add(sub.id)
            continue
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            b.add(n.name)
            a = n.args
            for x in list(a.posonlyargs) + list(a.args) + list(a.kwonlyargs):
                b.add(x.arg)
            if a.vararg:
                b.add(a.vararg.arg)
            if a.kwarg:
                b.add(a.kwarg.arg)
            for d in n.decorator_list:
                for sub in ast.walk(d):
                    if isinstance(sub, ast.Name):
                        b.add(sub.id)
        elif isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            b.add(n.id)
        elif isinstance(n, ast.Import):
            for al in n.names:
                b.add(al.asname or al.name.split(".")[0])
        elif isinstance(n, ast.ImportFrom):
            for al in n.names:
                b.add(al.asname or al.name)
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            b.update(n.names)
        elif isinstance(n, ast.ExceptHandler):
            if n.name:
                b.add(n.name)
        elif isinstance(n, ast.alias):
            b.add(n.asname or n.name.split(".")[0])
    return b


def loaded_names(tree):
    """被读取的裸名（不含属性访问的基名以外）"""
    out = defaultdict(list)
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
            out[n.id].append(n.lineno)
    return out


def top_defs(mod):
    """返回 (原生定义集, {别名: (类型, 原始module或None)})
    原生 = def/class/顶层赋值；转手 = import 进来的（不该从本仓 import）"""
    p = os.path.join(BASE, mod + ".py")
    if not os.path.exists(p):
        return set(), {}
    try:
        t = ast.parse(open(p, encoding="utf-8", errors="replace").read())
    except SyntaxError:
        return set(), {}
    native, reexport = set(), {}
    for n in t.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            native.add(n.name)
        elif isinstance(n, ast.Assign):
            for tg in n.targets:
                if isinstance(tg, ast.Name):
                    native.add(tg.id)
                elif isinstance(tg, (ast.Tuple, ast.List)):
                    for el in tg.elts:          # (W, H) = (540, 960)
                        if isinstance(el, ast.Name):
                            native.add(el.id)
        elif isinstance(n, ast.Import):
            for a in n.names:
                nm = a.asname or a.name.split(".")[0]
                reexport[nm] = ("mod", a.name)
        elif isinstance(n, ast.ImportFrom):
            for a in n.names:
                nm = a.asname or a.name
                reexport[nm] = ("from", n.module)
    return native, reexport


def fix_hint(name, src_native, src_reexport):
    """给出正确的 import 语句"""
    if name in src_native:
        return f"from {src_native} import {name}", True
    return None, False


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    fixable_only = "--fixable" in sys.argv
    mods = local_modules()
    targets = args if args else sorted(mods)
    nativemap = {}
    reemap = {}
    for m in mods:
        nativemap[m], reemap[m] = top_defs(m)

    grand = []
    for m in targets:
        p = os.path.join(BASE, m + ".py")
        if not os.path.exists(p):
            continue
        src = open(p, encoding="utf-8", errors="replace").read()
        try:
            t = ast.parse(src)
        except SyntaxError as e:
            print(f"  {m}: SyntaxError L{e.lineno}")
            continue
        bound = bound_names(t)
        loaded = loaded_names(t)
        unk = {k: v for k, v in loaded.items()
               if k not in bound and k not in BUILTINS}
        if not unk:
            continue
        rows = []
        for k, ls in sorted(unk.items(), key=lambda x: -len(x[1])):
            cands = [x for x in mods if x != m and k in nativemap[x]]
            # 优先级：文件名同源（render_v4_main → render_v4）> 其它
            stem = m
            same = [x for x in cands if stem.startswith(x) or x.startswith(stem)]
            src_mod = (same[0] if same else (cands[0] if cands else None))
            if len(cands) > 1:
                src_mod = sorted(same or cands, key=lambda x: (not stem.startswith(x), len(x)))[0]
            hint = f"from {src_mod} import {k}" if src_mod else None
            if not hint:
                # 查是否别人 import 过（第三方/stdlib），给出原始来源
                for x in mods:
                    if x != m and k in reemap[x]:
                        ty, org = reemap[x][k]
                        hint = (f"import {org}" if ty == "mod"
                                else f"from {org} import {k}")
                        break
            kind = "本仓" if src_mod else ("第三方/stdlib" if hint else "未知")
            rows.append((k, len(ls), ls[0], hint, kind))
        if fixable_only:
            rows = [r for r in rows if r[3]]
        if not rows:
            continue
        grand.append((m, rows))

    print(f"undef_check: 检出 {len(grand)} 个模块有未定义名\n")
    tot_fix = 0
    for m, rows in sorted(grand, key=lambda x: -sum(r[1] for r in x[1])):
        nfix = sum(1 for r in rows if r[3])
        tot_fix += nfix
        print(f"■ {m}  ({len(rows)} 个未定义名，{nfix} 个可从本仓 import)")
        for k, c, ln, sm, kind in rows[:14]:
            tag = f"→ {sm}" if sm else f"[{kind}]"
            print(f"    {k:26s} ×{c:<3d} L{ln:<5d} {tag}")
        if len(rows) > 14:
            print(f"    … 另 {len(rows)-14} 个")
    print(f"\n合计可机械修复（补 import）: {tot_fix} 个名字")
    return 1 if grand else 0


if __name__ == "__main__":
    sys.exit(main())
