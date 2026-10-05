#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""why_gen —— 生成结构化 why 层（IMPROVE_<m>.md）桩文件

规则:
  - 已存在的人写 IMPROVE_<m>.md **绝不覆盖**（人工智慧优先）
  - 只补缺失的，字段式，禁散文；未知字段留 `?` 待人工补
  - 字段: basis(依据) / trap(坑) / intent(意图) / impact(改动下游)
    impact 由依赖图自动算出，其余从源码注释抽取已知部分

用法: python3 why_gen.py
"""
import ast
import os
import re
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 工作流根（本工具在 _tools/）
CONTRACTS = os.path.join(BASE, "contracts")

TPL = """# WHY {mod}   (结构化·禁散文)

meta: tier={tier} | {lines}行 | 上游{ndep} 下游{ndown}

## basis 依据（搜证值/公式出处；改常数前必看）
{basis}

## trap 坑（勿回退 / 已修 / 冲突）
{trap}

## intent 意图（为何存在）
{intent}

## impact 改动影响（改本模块须回头验）
{impact}
"""


def local_modules():
    return {f[:-3] for f in os.listdir(BASE) if f.endswith(".py")}


def deps_graph():
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


def harvest_basis(src):
    """从源码注释抽依据：来源/文献/实测/铁律出处"""
    out = []
    for ln in src.splitlines():
        s = ln.strip()
        if not s.startswith("#"):
            continue
        s = s.lstrip("#").strip()
        if re.search(r"来源|依据|文献|实测|搜证|标准|出自|参见|铁律\d+|et al\.|20\d\d|ISO|GB/|ASTM", s):
            s = re.sub(r"\s+", " ", s)[:110]
            if s not in out:
                out.append(s)
    return out[:6]


def harvest_trap(src):
    out = []
    for ln in src.splitlines():
        s = ln.strip()
        if not s.startswith("#"):
            continue
        s = s.lstrip("#").strip()
        if re.search(r"勿|禁|已修|旧|曾|坑|注意|警告|WARN|TODO|待修|冲突|回退|bug|BUG|错", s):
            s = re.sub(r"\s+", " ", s)[:110]
            if s not in out:
                out.append(s)
    return out[:6]


def fmt(items, fallback):
    if not items:
        return fallback
    return "\n".join("- " + i for i in items)


def main():
    mods = local_modules()
    dep, rdep = deps_graph()
    made, skipped = [], []
    for m in sorted(mods):
        p = os.path.join(BASE, f"IMPROVE_{m}.md")
        if os.path.exists(p):
            skipped.append(m)
            continue
        src = ""
        sp = os.path.join(BASE, m + ".py")
        if os.path.exists(sp):
            src = open(sp, encoding="utf-8", errors="replace").read()
        lines = len(src.splitlines())
        basis = harvest_basis(src)
        trap = harvest_trap(src)
        intent = (ast.get_docstring(ast.parse(src)) or "").strip().split("\n")[0] \
            if src.strip() else "?"
        try:
            intent = intent[:110]
        except Exception:
            pass
        down = sorted(rdep[m])
        impact = "- 直接下游: " + (", ".join(down) if down else "无")
        if down:
            impact += f"\n- 验证命令: python3 impact.py {m}"
        tier = "S"
        for f in ["contracts/" + m + ".md"]:
            cp = os.path.join(BASE, f)
            if os.path.exists(cp):
                t = open(cp, encoding="utf-8").read()
                mm = re.search(r"@(\w+)/(\S+)", t)
                if mm:
                    tier = f"{mm.group(1)}/{mm.group(2)}"
        open(p, "w", encoding="utf-8").write(TPL.format(
            mod=m, tier=tier, lines=lines, ndep=len(dep[m]), ndown=len(down),
            basis=fmt(basis, "- ? 待补（改常数前必补）"),
            trap=fmt(trap, "- ? 待补"),
            intent=intent or "- ? 待补",
            impact=impact))
        made.append(m)
    print(f"[OK] 新生成 {len(made)} 份 why 桩；已存在跳过 {len(skipped)} 份（未覆盖）")
    tot = sum(len(open(os.path.join(BASE, f"IMPROVE_{m}.md"), encoding="utf-8").read())
              for m in made)
    print(f"     新增 {tot} 字符")


if __name__ == "__main__":
    main()
