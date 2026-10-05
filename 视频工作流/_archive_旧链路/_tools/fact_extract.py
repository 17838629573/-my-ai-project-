#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fact_extract —— 从 AST 抽取模块事实（contract_gen.py 拆出，过体积门禁）

只做「读代码」，不做判断。所有字段可由 AST 证实。
"""
import ast
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 工作流根（本工具在 _tools/）
CONTRACTS = os.path.join(BASE, "contracts")


def imports_of(mod):
    p = os.path.join(BASE, mod + ".py")
    if not os.path.exists(p):
        return set(), set()
    try:
        t = ast.parse(open(p, encoding="utf-8", errors="replace").read())
    except SyntaxError:
        return set(), set()
    mods, aliases = set(), set()
    for n in ast.walk(t):
        if isinstance(n, ast.Import):
            for a in n.names:
                mods.add(a.name.split(".")[0])
                aliases.add(a.asname or a.name.split(".")[0])
        elif isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module.split(".")[0])
            for a in n.names:
                aliases.add(a.asname or a.name)
    return mods, aliases
def sig_of(n):
    a = [x.arg for x in n.args.args]
    if n.args.kwonlyargs:
        a += ["*"] + [x.arg for x in n.args.kwonlyargs]
    if n.args.vararg:
        a.append("*" + n.args.vararg.arg)
    if n.args.kwarg:
        a.append("**" + n.args.kwarg.arg)
    return f"{n.name}({','.join(a)})"
def callees_of(fn, top_names):
    local, ext = set(), set()
    for n in ast.walk(fn):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name):
                local.add(f.id)
            elif isinstance(f, ast.Attribute):
                cur = f
                while isinstance(cur, ast.Attribute):
                    cur = cur.value
                if isinstance(cur, ast.Name):
                    ext.add(cur.id)
    return (local & top_names), ext
def early_returns_of(fn):
    out = []
    for n in fn.body:
        if isinstance(n, ast.If):
            for sub in ast.walk(n):
                if isinstance(sub, ast.Raise):
                    out.append(("raise", n.lineno))
                    break
                if isinstance(sub, ast.Return) and sub.value is not None:
                    out.append(("return", n.lineno))
                    break
    return out[:6]
def const_of(mod, values=True):
    """values=False 时只抽常量名，不带值（给定位层用）"""
    p = os.path.join(BASE, mod + ".py")
    if not os.path.exists(p):
        return []
    try:
        t = ast.parse(open(p, encoding="utf-8", errors="replace").read())
    except SyntaxError:
        return []
    out = []
    for n in t.body:
        if isinstance(n, ast.Assign):
            for tg in n.targets:
                if isinstance(tg, ast.Name) and tg.id.isupper():
                    if not values:
                        out.append(tg.id)
                        continue
                    v = n.value
                    if isinstance(v, ast.Constant):
                        out.append(f"{tg.id}={v.value!r}")
                    elif isinstance(v, ast.Dict):
                        out.append(f"{tg.id}[{len(v.keys)}]")
                    elif isinstance(v, (ast.List, ast.Tuple)):
                        out.append(f"{tg.id}[{len(v.elts)}]")
                    else:
                        out.append(tg.id)
    return out
def rules_of(mod):
    src = ""
    for p in [os.path.join(BASE, mod + ".py"), os.path.join(CONTRACTS, mod + ".md")]:
        if os.path.exists(p):
            src += open(p, encoding="utf-8", errors="replace").read()
    ns = set(re.findall(r"铁律\s*(\d{1,3})", src)) | \
         set(re.findall(r"(?<![\w])T(\d{2,3})\b", src))
    ns = {n for n in ns if n.isdigit() and int(n) <= 200}
    return " ".join(f"T{n}" for n in sorted(ns, key=int))
def module_facts(mod):
    p = os.path.join(BASE, mod + ".py")
    if not os.path.exists(p):
        return None
    src = open(p, encoding="utf-8", errors="replace").read()
    try:
        t = ast.parse(src)
    except SyntaxError as e:
        return {"module": mod, "error": f"SyntaxError L{e.lineno}"}
    top_names = set()
    for n in t.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            top_names.add(n.name)
        elif isinstance(n, ast.Assign):
            for tg in n.targets:
                if isinstance(tg, ast.Name):
                    top_names.add(tg.id)
    doc = (ast.get_docstring(t) or "").strip()
    fns = []
    for n in t.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            loc, ext = callees_of(n, top_names)
            fns.append({
                "name": n.name,
                "sig": sig_of(n),
                "line": n.lineno,
                "public": not n.name.startswith("_"),
                "doc": (ast.get_docstring(n) or "").strip().split("\n")[0][:60],
                "calls_local": sorted(x for x in loc if x != n.name),
                "calls_ext": sorted(ext),
                "early": early_returns_of(n),
            })
    return {
        "module": mod,
        "lines": len(src.splitlines()),
        "doc": doc,
        "fns": fns,
        "const": const_of(mod),
        "const_names": const_of(mod, values=False),
        "has_main": "__main__" in src,
        "main_at": next((n.lineno for n in t.body
                         if isinstance(n, ast.If) and "__main__" in ast.dump(n.test)), None),
        "sc_at": next((n.lineno for n in t.body
                       if isinstance(n, ast.FunctionDef) and n.name == "self_check"), None),
    }
