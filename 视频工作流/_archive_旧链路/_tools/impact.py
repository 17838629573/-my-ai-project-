#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""impact —— 改动影响分析：改 X 后，哪些模块必须回头验

用法:
    python3 impact.py physics          # 只看直接下游清单
    python3 impact.py physics --check  # 实跑下游自检（默认超时 300s/个）
    python3 impact.py physics --depth 2  # 传播两层（默认 1）

输出退出码: 0=下游全过 / 1=有失败 / 2=用法错

说明: 下游 = import 本模块的模块（反向依赖图，AST 实扫，非手写）。
      --check 用 subprocess 逐个跑（组内有 top-level 副作用的脚本，import 会炸）。
"""
import ast
import os
import subprocess
import sys
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 工作流根（本工具在 _tools/）


def local_modules():
    return {f[:-3] for f in os.listdir(BASE) if f.endswith(".py")}


def build():
    mods = local_modules()
    dep, rdep = defaultdict(set), defaultdict(set)
    for m in mods:
        p = os.path.join(BASE, m + ".py")
        try:
            t = ast.parse(open(p, encoding="utf-8", errors="replace").read())
        except (SyntaxError, FileNotFoundError):
            continue
        ms = set()
        for n in ast.walk(t):
            if isinstance(n, ast.Import):
                for a in n.names:
                    ms.add(a.name.split(".")[0])
            elif isinstance(n, ast.ImportFrom) and n.module:
                ms.add(n.module.split(".")[0])
        for x in ms:
            if x in mods and x != m:
                dep[m].add(x)
                rdep[x].add(m)
    return dep, rdep


def downstream(m, rdep, depth=1):
    """按层返回: [(层号, [模块...])]"""
    out = []
    cur, seen = {m}, {m}
    for d in range(1, depth + 1):
        nxt = set()
        for x in cur:
            for r in rdep[x]:
                if r not in seen:
                    seen.add(r)
                    nxt.add(r)
        if not nxt:
            break
        out.append((d, sorted(nxt)))
        cur = nxt
    return out


def run_check(mods, timeout=300):
    ok = True
    for m in mods:
        p = os.path.join(BASE, m + ".py")
        if not os.path.exists(p):
            print(f"  FAIL {m}  文件缺失")
            ok = False
            continue
        try:
            r = subprocess.run([sys.executable, p], cwd=BASE,
                               capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            print(f"  FAIL {m}  超时 {timeout}s")
            ok = False
            continue
        o = (r.stdout + r.stderr).decode("utf-8", "replace").strip().splitlines()
        tail = o[-1][:70] if o else "(无输出)"
        print(f"  {'PASS' if r.returncode == 0 else 'FAIL'} {m}  {tail}")
        ok = ok and (r.returncode == 0)
    return ok


def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
        return 2
    target = a[0]
    check = "--check" in a
    depth = 1
    for i, x in enumerate(a):
        if x == "--depth" and i + 1 < len(a):
            depth = int(a[i + 1])
    _, rdep = build()
    if target not in {f[:-3] for f in os.listdir(BASE) if f.endswith(".py")}:
        print(f"未知模块: {target}")
        return 2
    layers = downstream(target, rdep, depth)
    total = sum(len(v) for _, v in layers)
    print(f"impact {target}  depth={depth}  下游 {total} 个")
    flat = []
    for d, ms in layers:
        print(f"  L{d} ({len(ms)}): {', '.join(ms)}")
        flat += ms
    if not check:
        print("  (加 --check 实跑下游自检)")
        return 0
    print("  --- 实跑 ---")
    return 0 if run_check(flat) else 1


if __name__ == "__main__":
    sys.exit(main())
