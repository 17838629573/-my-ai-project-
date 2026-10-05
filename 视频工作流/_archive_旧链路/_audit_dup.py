#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""真实扫描：找出可复用却被重复实现的逻辑。
读取活跃 py 源码，做三件事：
1. 函数级重复（同名或近似实现）
2. 片段级重复（>=6 行的重复代码块）
3. 数学原子是否已在 _common，却被各模块手写为内联
只扫活跃模块（排除 _bak / 归档 / 本脚本）。
"""
import os, re, ast, hashlib
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
SKIP = {"_bak", "_archive", "_audit", "__pycache__", "venv", "node_modules"}

def active(path):
    parts = set(os.path.relpath(path, ROOT).split(os.sep))
    return not (parts & SKIP) and path.endswith(".py") and not os.path.basename(path).startswith("_audit")

files = []
for d, _, fs in os.walk(ROOT):
    for f in fs:
        p = os.path.join(d, f)
        if active(p):
            files.append(p)

# ---------- 1. 内联数学原子（应走 _common 却手写的） ----------
ATOMS = {
    "clamp":   [r"\bclamp\s*\("],
    "lerp":    [r"\blerp\s*\(", r"[a-z_]\s*\*\s*\(1-[a-z_]\w*\)\s*\+"],
    "deg_norm":[r"deg\s*%\s*360", r"angle\s*%\s*360", r"\bmod\s*\([^,]+,\s*360"],
    "rad2deg": [r"180\s*/\s*math\.pi", r"\*\s*180\s*/\s*math\.pi", r"math\.degrees"],
    "px_per_m":[r"px_per_m", r"pixels_per_meter", r"/\s*height_m"],
    "catmull": [r"catmull", r"t0\*t0\*t0", r"0\.5\s*\*\s*\(.*\+.*\*.*t"],
}

print("=" * 72)
print("[扫描1] 数学原子内联（应复用 _common 却手写）")
print("=" * 72)
atom_hits = defaultdict(list)
for p in files:
    try:
        src = open(p, encoding="utf-8").read()
    except Exception:
        continue
    name = os.path.relpath(p, ROOT)
    if "_common" in name or "_audit" in name:
        continue
    for atom, pats in ATOMS.items():
        for pat in pats:
            for m in re.finditer(pat, src):
                line = src.count("\n", 0, m.start()) + 1
                atom_hits[(atom, name)].append(line)
                break  # 每文件每原子只报一次
for (atom, name), lines in sorted(atom_hits.items()):
    print(f"  {atom:10s}  {name:28s}  行:{lines}")

# ---------- 2. 重复代码块（>=6 行完全相同） ----------
print()
print("=" * 72)
print("[扫描2] 重复代码块 >= 6 行")
print("=" * 72)
norm = lambda s: re.sub(r"\s+", " ", s).strip()
blocks = defaultdict(list)  # hash -> [(file, start, end)]
for p in files:
    try:
        lines = open(p, encoding="utf-8").read().split("\n")
    except Exception:
        continue
    name = os.path.relpath(p, ROOT)
    for i in range(0, len(lines) - 5):
        blk = "\n".join(lines[i:i+6])
        nb = norm(blk)
        if len(nb) < 120:
            continue
        if re.match(r"^(\s*(#|@|import|from|def |class )\s*)*$", nb):
            continue
        h = hashlib.md5(nb.encode()).hexdigest()
        blocks[h].append((name, i+1, i+6))

dups = {h: v for h, v in blocks.items() if len(v) >= 2}
print(f"  重复块数: {len(dups)}")
for h, occ in sorted(dups.items(), key=lambda kv: -len(kv[1])):
    print(f"  --- 出现 {len(occ)} 次 ---")
    for name, s, e in occ[:6]:
        print(f"      {name} L{s}-{e}")

# ---------- 3. 同名函数 ----------
print()
print("=" * 72)
print("[扫描3] 同名函数定义")
print("=" * 72)
fndef = defaultdict(list)
for p in files:
    try:
        tree = ast.parse(open(p, encoding="utf-8").read())
    except Exception:
        continue
    name = os.path.relpath(p, ROOT)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fndef[node.name].append((name, node.lineno))
# 排除测试/私有/魔术
for fn, occ in sorted(fndef.items()):
    if len(occ) >= 2 and not fn.startswith(("_", "test")) and not fn.startswith("__"):
        print(f"  {fn}:")
        for name, ln in occ:
            print(f"      {name}:{ln}")

# ---------- 4. 模块长度 vs 400 行软上限 ----------
print()
print("=" * 72)
print("[扫描4] 超过 400 行软上限的模块")
print("=" * 72)
for p in sorted(files, key=lambda x: -len(open(x, encoding="utf-8").read().split("\n"))):
    n = len(open(p, encoding="utf-8").read().split("\n"))
    if n > 400:
        print(f"  {n:5d}  {os.path.relpath(p, ROOT)}")
