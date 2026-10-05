#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gate_pre.py —— 改代码前必跑。强制三条：
  R1 依赖图无漂移（改了 import 必须重生成 deps）
  R2 先看依赖图：打印目标模块的上下游，禁止盲改
  R3 目标文件体积未超标（超标须先拆分，禁止提阈值绕过）

用法:
  python3 _tools/gate_pre.py systems_view.py
  python3 _tools/gate_pre.py systems_view.py chroma.py
"""
import ast, json, os, subprocess, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEPS_MD = os.path.join(BASE, "deps.md")
DEPS_MMD = os.path.join(BASE, "deps.mmd")
MAX_LINE, MAX_CHAR = 400, 12000


def run(cmd):
    return subprocess.run(cmd, shell=True, cwd=BASE, capture_output=True, text=True)


def load_deps():
    """从 deps.md 解析 模块 -> 依赖列表。
    注意：同一模块可能出现多次（静态边 + [runtime] 边），必须合并而非覆盖。
    """
    d = {}
    if not os.path.exists(DEPS_MD):
        return d
    for ln in open(DEPS_MD, encoding="utf-8").read().split("\n"):
        s = ln.strip()
        if not s or s.startswith("#") or " -> " not in s:
            continue
        k, v = s.split(" -> ", 1)
        k = k.strip()
        items = [x.strip() for x in v.split(",") if x.strip() and x.strip() != "(无)"]
        cur = set(d.get(k, []))
        for it in items:
            cur.add(it.replace("[runtime]", "").strip())
        d[k] = sorted(cur)
    return d


def upstream_of(target, deps):
    """谁 import 了 target = 改它会影响谁。"""
    return sorted([m for m, ds in deps.items() if target in ds])


def check_size(f):
    p = os.path.join(BASE, f)
    if not os.path.exists(p):
        return None
    src = open(p, encoding="utf-8").read()
    n = len(src.split("\n"))
    return n, len(src), (n > MAX_LINE or len(src) > MAX_CHAR)


def split_candidates(f):
    """体积超标时，工具给出拆分候选：按顶层函数聚类，标出可独立成模块的一组。"""
    p = os.path.join(BASE, f)
    src = open(p, encoding="utf-8").read()
    t = ast.parse(src)
    fns = [(n.name, n.lineno, (ast.get_docstring(n) or "").split("\n")[0][:44])
           for n in t.body if isinstance(n, ast.FunctionDef)]
    # 按名字前缀聚类
    groups = {}
    for name, ln, doc in fns:
        key = name.split("_")[0] if "_" in name else name
        groups.setdefault(key, []).append((name, ln, doc))
    return [(k, v) for k, v in sorted(groups.items(), key=lambda x: -len(x[1])) if len(v) >= 2]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        print("用法: python3 _tools/gate_pre.py <目标文件> [...]")
        return 2

    print("=" * 62)
    print("R1 依赖图漂移检查")
    print("=" * 62)
    r = run("python3 _tools/depgraph.py --check")
    drift = r.returncode != 0
    print(r.stdout[-800:] if r.stdout else "(无输出)")
    if drift:
        print("[FAIL] 依赖图有漂移 —— 先跑: python3 _tools/depgraph.py --write")
        print("       禁止在漂移状态下改代码")
        return 1
    print("[PASS] 依赖图与源码一致")

    deps = load_deps()
    print(f"\n[INFO] 已载入依赖图: {len(deps)} 个模块")

    print("\n" + "=" * 62)
    print("R2 依赖上下文（改前必看）")
    print("=" * 62)
    for f in args:
        mod = f[:-3] if f.endswith(".py") else f
        down = deps.get(mod, [])
        up = upstream_of(mod, deps)
        print(f"\n  {mod}")
        print(f"    down (它依赖谁): {', '.join(down) if down else '（无）'}")
        print(f"    up   (谁依赖它): {', '.join(up) if up else '（无）'}")
        if up:
            print(f"    -> 改它会影响 {len(up)} 个上游模块，改完必须验这些")

    print("\n" + "=" * 62)
    print("R3 体积检查（超标须先拆，禁止提阈值）")
    print("=" * 62)
    over = []
    for f in args:
        sz = check_size(f)
        if sz is None:
            print(f"  [跳过] {f} 不存在")
            continue
        n, c, bad = sz
        flag = "FAIL" if bad else "ok  "
        print(f"  {flag} {f}: {n}行 / {c}字符  (阈值 {MAX_LINE}/{MAX_CHAR})")
        if bad:
            over.append(f)
    if over:
        print("\n  超限模块必须拆分（工具给出候选，不是建议，是要求）：")
        for f in over:
            print(f"\n  --- {f} 拆分候选（按函数名前缀聚类）---")
            for k, v in split_candidates(f)[:6]:
                print(f"    组 '{k}'  ({len(v)} 个函数):")
                for name, ln, doc in v[:8]:
                    print(f"      L{ln:<5} {name}  # {doc}")
            print(f"    判定: 存在 >=2 个函数的组 => 可拆，禁止改为提阈值")
        return 1

    print("\n[PASS] 可开始改动")
    print("       改完后必跑: python3 _tools/gate_post.py " + " ".join(args))
    return 0


if __name__ == "__main__":
    sys.exit(main())
