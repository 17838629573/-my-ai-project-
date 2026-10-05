#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""why_apply —— 把 _worklist/ 的 pick 回填进 IMPROVE_*.md

模型只填了 pick 行（工具做不了的那部分），其余由本工具完成：
  读 pick → 解析 `IMPROVE_x.md:<行>` / `<mod>.py:<行>` / `NEW: <文本>`
  → 从源文件取原文 → 生成七槽 Y-Statement 块 → 写回 IMPROVE_*.md

幂等：已带 gen:why_apply 标记的块跳过，不重复生成。

用法:
    python3 why_apply.py             # 全量应用
    python3 why_apply.py physics     # 单份
    python3 why_apply.py --dry       # 只打印不写
"""
import os
import re
import sys
import glob

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 工作流根（本工具在 _tools/）
sys.path.insert(0, BASE)
from why_struct import extract as ws_extract  # 复用槽位抽取，避免标记冲突
WL = os.path.join(BASE, "_worklist")
MARK = "gen:why_apply"
SLOT_ORDER = ["context", "facing", "decided", "neglected",
              "achieve", "accepting", "basis"]
SLOT_CN = {"context": "处境", "facing": "问题", "decided": "决定",
           "neglected": "否决方案", "achieve": "收益", "accepting": "代价",
           "basis": "依据出处"}


def src_line(ref):
    """IMPROVE_x.md:12 / mod.py:12 -> 原文那一行（去注释符）"""
    m = re.match(r"^([\w\.]+\.(?:md|py)):(\d+)$", ref.strip())
    if not m:
        return None
    p = os.path.join(BASE, m.group(1))
    if not os.path.exists(p):
        return None
    lines = open(p, encoding="utf-8", errors="replace").read().splitlines()
    i = int(m.group(2)) - 1
    if i >= len(lines):
        return None
    s = lines[i].strip()
    if m.group(1).endswith(".py"):
        s = s.lstrip("#").strip()
    s = s.lstrip("-*|>").strip()
    return re.sub(r"\s+", " ", s)[:200]


def resolve(pick):
    pick = pick.strip()
    if pick.startswith("原文已载:"):
        return pick[len("原文已载:"):].strip()
    if pick.startswith("NEW:"):
        return pick[4:].strip()
    v = src_line(pick)
    return v if v else f"(待补: {pick})"


def parse_worklist(path):
    """-> [(slot, pick)] 只取已填的"""
    out = []
    cur = None
    for ln in open(path, encoding="utf-8", errors="replace"):
        m = re.match(r"^## \S+ \((\w+)\)", ln)
        if m:
            cur = m.group(1)
            continue
        m2 = re.match(r"^\s*pick:\s*(.+)$", ln)
        if m2 and cur:
            v = m2.group(1).strip()
            if v and v != "____":
                out.append((cur, v))
    return out


def build_block(mod, pairs, existing=None):
    d = dict(pairs)
    if existing:
        for s, cands in existing.items():
            if cands and s not in d:
                # 取置信最高的候选，标注来源为「原文已载」
                best = max(cands, key=lambda x: x[1])
                d[s] = "原文已载: " + best[0]
    lines = [f"\n---\n## Y-Statement（{MARK} 勿手改）\n"]
    lines.append(f"meta: {mod}")
    for s in SLOT_ORDER:
        if s in d:
            lines.append(f"{SLOT_CN[s]}: {resolve(d[s])}")
        else:
            lines.append(f"{SLOT_CN[s]}: （缺）")
    return "\n".join(lines) + "\n"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry" in sys.argv
    if args:
        files = [os.path.join(WL, a + ".md") for a in args]
    else:
        files = sorted(glob.glob(os.path.join(WL, "*.md")))
    ok = skip = 0
    for wf in files:
        mod = os.path.basename(wf)[:-3]
        tgt = os.path.join(BASE, f"IMPROVE_{mod}.md")
        if os.path.exists(tgt) and MARK in open(tgt, encoding="utf-8", errors="replace").read():
            skip += 1
            continue
        pairs = parse_worklist(wf)
        if not pairs:
            continue
        ex = None
        if os.path.exists(tgt):
            ex = ws_extract(open(tgt, encoding="utf-8", errors="replace").read())
        block = build_block(mod, pairs, ex)
        if dry:
            print(f"[dry] {mod}: {len(pairs)} 槽")
            print(block)
            continue
        old = open(tgt, encoding="utf-8").read() if os.path.exists(tgt) else f"# IMPROVE {mod}\n"
        open(tgt, "w", encoding="utf-8").write(old.rstrip() + "\n" + block)
        ok += 1
    print(f"[OK] 回填 {ok} 份，跳过已生成 {skip} 份")


if __name__ == "__main__":
    main()
