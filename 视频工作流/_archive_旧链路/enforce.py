#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
执行门禁（契约强制性检查）
==================================================
用法：
  python3 enforce.py validate                 全量校验（文件存在/无环/未声明引用）
  python3 enforce.py check-contract <模块>     模块是否已在 deps.md 声明
  python3 enforce.py check-deps                依赖无环 + 被依赖文件真实存在
  python3 enforce.py check-assets              资产硬阻断(角色/背景/道具/走路帧)
  python3 enforce.py check-evidence <码> <依据> 判定须附退出码与依据
  python3 enforce.py gate post-stage <N>       过门：强制追加 WORKLOG.md

铁律1：判定靠命令输出。本脚本所有结论均来自文件系统与正则解析，不做推测。
"""
import os
import re
import subprocess
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
DEPS = os.path.join(BASE, "deps.md")
WORKLOG = os.path.join(BASE, "WORKLOG.md")

ACTIVE_SECTIONS = ("L0", "L1", "L2", "L3", "A")
DORMANT_SECTIONS = ("X", "Z")


# ------------------------------------------------------------------ 解析
def parse_deps():
    """
    解析 deps.md -> (deps, layer, order, runtime)
    【关键】同名模块多处声明时依赖【累加】而非覆盖 —— 否则
    "外部进程依赖"段会把 L3 段的依赖覆盖掉（实测踩过）。
    """
    deps, layer, order, runtime = {}, {}, [], set()
    cur = None
    with open(DEPS, encoding="utf-8") as f:
        for ln in f:
            t = ln.strip()
            if t.startswith("#"):
                head = t.lstrip("#").strip()
                key = head.split()[0] if head else ""
                if key in ACTIVE_SECTIONS + DORMANT_SECTIONS:
                    cur = key
                continue
            if not t:
                continue
            m = re.match(r"^(\S+)\s*->\s*(.*)$", t)
            if not m:
                continue
            mod, rhs = m.group(1), m.group(2)
            is_rt = "[runtime]" in rhs
            # 先剥方括号与圆括号（避免括号内的逗号被当分隔符）
            cleaned = re.sub(r"\[.*?\]", "", rhs)
            cleaned = re.sub(r"\(.*?\)", "", cleaned)
            ds = []
            for d in cleaned.split(","):
                d = d.strip()
                if not d or d == "-":
                    continue
                ds.append(d)
            if is_rt:
                for d in ds:
                    runtime.add((mod, d))
            if mod in deps:
                for d in ds:
                    if d not in deps[mod]:
                        deps[mod].append(d)
            else:
                deps[mod] = ds
                order.append(mod)
            layer[mod] = cur
    return deps, layer, order, runtime


def module_exists(name):
    """模块名 -> 实际路径（.py 文件或目录），不存在返回 None"""
    p = os.path.join(BASE, name)
    if os.path.isdir(p):
        return p
    if os.path.isfile(p + ".py"):
        return p + ".py"
    return None


# ------------------------------------------------------------------ 图算法
def static_deps(deps, runtime):
    """剔除 [runtime] 懒加载边后的静态依赖图。
    依据：懒加载 / __main__ 守卫内的 import 在模块被 import 时不执行，
    不构成真实循环依赖。环检测必须基于本图，否则全是假阳性。"""
    return {m: [d for d in ds if (m, d) not in runtime]
            for m, ds in deps.items()}


def find_cycle(deps):
    """DFS 三色标记找环"""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {m: WHITE for m in deps}
    path, cycles = [], []

    def dfs(u):
        color[u] = GRAY
        path.append(u)
        for v in deps.get(u, []):
            if v not in color:
                continue
            if color[v] == GRAY:
                i = path.index(v)
                cycles.append(path[i:] + [v])
            elif color[v] == WHITE:
                dfs(v)
        path.pop()
        color[u] = BLACK

    for m in deps:
        if color[m] == WHITE:
            dfs(m)
    return cycles


def local_imports(py_path):
    """扫出文件里 import 的【本地】模块（同目录存在 .py 的）"""
    try:
        src = open(py_path, encoding="utf-8", errors="ignore").read()
    except OSError:
        return set()
    names = set()
    for m in re.finditer(r"^\s*from\s+([A-Za-z_][\w]*)\s+import", src, re.M):
        names.add(m.group(1))
    # 注意：必须支持 `import a, b` 逗号形式，只取首个名会漏报（曾误判 _问卷/骨架_幡旗）
    for m in re.finditer(r"^\s*import\s+([A-Za-z_][\w]*(?:\s*,\s*[A-Za-z_][\w]*)*)", src, re.M):
        for n in m.group(1).split(","):
            names.add(n.strip())
    out = set()
    for n in names:
        if os.path.exists(os.path.join(BASE, n + ".py")):
            out.add(n)
    return out


# ------------------------------------------------------------------ 命令
MODULES = ["actors", "character_sheet", "chroma", "film_assemble",
           "loop_engine", "motion_lib", "photo_rules", "physics_rules",
           "render_v4", "skeleton_runtime", "subtitle", "systems"]


def cmd_status(*a, **k):
    from enforce_cmds import cmd_status as _f
    return _f(*a, **k)


def cmd_validate(*a, **k):
    from enforce_cmds import cmd_validate as _f
    return _f(*a, **k)


def cmd_check_contract(*a, **k):
    from enforce_cmds import cmd_check_contract as _f
    return _f(*a, **k)


def cmd_check_deps(*a, **k):
    from enforce_cmds import cmd_check_deps as _f
    return _f(*a, **k)


def cmd_check_evidence(*a, **k):
    from enforce_cmds import cmd_check_evidence as _f
    return _f(*a, **k)


def cmd_gate(*a, **k):
    from enforce_cmds import cmd_gate as _f
    return _f(*a, **k)


def cmd_check_assets(*a, **k):
    from enforce_cmds import cmd_check_assets as _f
    return _f(*a, **k)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd = sys.argv[1]
    if cmd == "validate":
        return cmd_validate()
    if cmd == "check-status":
        return cmd_status()
    if cmd == "check-contract":
        return cmd_check_contract(sys.argv[2]) if len(sys.argv) > 2 else 2
    if cmd == "check-assets":
        return cmd_check_assets()
    if cmd == "check-deps":
        return cmd_check_deps()
    if cmd == "check-evidence":
        return (cmd_check_evidence(sys.argv[2], sys.argv[3])
                if len(sys.argv) > 3 else 2)
    if cmd == "gate":
        return (cmd_gate(sys.argv[2], sys.argv[3])
                if len(sys.argv) > 3 else 2)
    print(f"未知命令 {cmd}")
    return 2


if __name__ == "__main__":
    sys.exit(main())


# ---------------------------------------------------------------- 资产门禁