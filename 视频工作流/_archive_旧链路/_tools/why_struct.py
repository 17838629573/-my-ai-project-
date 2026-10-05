#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""why_struct —— why 层结构化：散文 → Y-Statement 六槽位

模板（Olaf Zimmermann, SATURN 2012；源自 George Fairbanks Architecture Haiku）：
    In the context of <situation>, facing <concern>,
    we decided for <option> and neglected <alternatives>,
    to achieve <outcome>, accepting <downside>.

工具做什么:
  按六槽位关键词，从现有 IMPROVE_*.md / 源码注释里抽已存在的内容，
  逐槽位给置信度，输出「已抽到 / 缺失」。
工具不做什么:
  不编造语义、不重写文档。**只列缺失槽位清单** —— 那部分才由模型补。

用法:
    python3 why_struct.py                # 全量报告：每份缺哪几个槽位
    python3 why_struct.py physics        # 单份
    python3 why_struct.py --missing      # 只列缺失项（模型待办清单）
"""
import os
import re
import sys
import glob

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 工作流根（本工具在 _tools/）

# 六槽位关键词（中文 + 英文）
SLOTS = {
    # 六槽位（Y-Statement 原版）
    "context":    r"^(用户指出|需求|场景|背景)|在.{0,20}(中|下|场景)|本模块|该模块|负责|为什么需要",
    "facing":     r"缺失|不足|无法|不能|硬编码|问题|挑战|约束|难点|风险|原代码|痛点|导致",
    "decided":    r"采用|选择|决定|改用|实现为|使用|选用|改为|我们(用|以)|chose|decided",
    "neglected":  r"而非|而不是|不用|弃用|否决|排除|放弃|不采用|曾考虑.*但|旧(实现|做法)|原(来|先)",
    "achieve":    r"以(便|实现|达到)|从而|为了|使得|好处|优势|收益|解决|满足",
    "accepting":  r"代价|缺点|局限|牺牲|但会|风险是|接受|不足是|trade|downside",
    # 第七槽：你独有 —— 依据出处（防 AI 乱改常数）
    "basis":      r"来源|依据|文献|实测|搜证|标准|et al|20\d\d|ISO|GB/|ASTM|Hoiem|Izawa|Strouhal|"
                  r"Vogel|Blevins|论文|公式出处|参考",
}
SLOT_ORDER = ["context", "facing", "decided", "neglected", "achieve", "accepting", "basis"]
SLOT_CN = {"context": "处境", "facing": "问题", "decided": "决定",
           "neglected": "否决方案", "achieve": "收益", "accepting": "代价",
           "basis": "依据出处"}


def extract(text):
    """逐槽位抽句子，返回 {slot: [(句, 置信)]}"""
    out = {s: [] for s in SLOT_ORDER}
    for ln in text.splitlines():
        s = ln.strip().lstrip("#-*|").strip()
        if not s or len(s) < 6 or s.startswith("```"):
            continue
        for slot, pat in SLOTS.items():
            hits = re.findall(pat, s)
            if hits:
                # 置信：同一行命中多槽 -> 低（语义混杂）；长句更可能是完整论述
                conf = min(0.9, 0.4 + 0.1 * len(hits))
                if len(s) > 40:
                    conf = min(0.95, conf + 0.2)
                out[slot].append((s[:110], round(conf, 2)))
    return out


def module_text(m):
    """IMPROVE_<m>.md 优先；无则退回源码注释"""
    p = os.path.join(BASE, f"IMPROVE_{m}.md")
    if os.path.exists(p):
        return open(p, encoding="utf-8", errors="replace").read(), "IMPROVE"
    p = os.path.join(BASE, m + ".py")
    if os.path.exists(p):
        t = open(p, encoding="utf-8", errors="replace").read()
        return "\n".join(l for l in t.splitlines() if l.strip().startswith("#")), "源码注释"
    return "", "无来源"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    miss_only = "--missing" in sys.argv
    if args:
        mods = args
    else:
        mods = sorted({os.path.basename(f)[8:-3]
                       for f in glob.glob(os.path.join(BASE, "IMPROVE_*.md"))})

    rows = []
    for m in mods:
        txt, src = module_text(m)
        if not txt.strip():
            rows.append((m, src, {s: [] for s in SLOT_ORDER}))
            continue
        rows.append((m, src, extract(txt)))

    filled = {s: 0 for s in SLOT_ORDER}
    for _, _, e in rows:
        for s in SLOT_ORDER:
            if e[s]:
                filled[s] += 1
    n = len(rows)
    print(f"why_struct: {n} 份  Y-Statement 槽位覆盖率")
    for s in SLOT_ORDER:
        bar = "█" * int(filled[s] / max(n, 1) * 20)
        print(f"  {SLOT_CN[s]:6s} {filled[s]:3d}/{n}  {bar}")
    print()

    if not miss_only:
        for m, src, e in rows[:12]:
            got = [SLOT_CN[s] for s in SLOT_ORDER if e[s]]
            lack = [SLOT_CN[s] for s in SLOT_ORDER if not e[s]]
            print(f"  {m:24s} [{src}] 有:{','.join(got) or '—'}")
            if lack:
                print(f"  {'':24s} 缺:{','.join(lack)}")
        if len(rows) > 12:
            print(f"  … 另 {len(rows)-12} 份")

    print("\n=== 待补清单（工具抽不到，需模型判断）===")
    todo = []
    for m, src, e in rows:
        lack = [s for s in SLOT_ORDER if not e[s]]
        if lack:
            todo.append((m, lack, src))
    for m, lack, src in todo[:25]:
        print(f"  {m:24s} 缺 {','.join(SLOT_CN[x] for x in lack)}   (来源:{src})")
    print(f"\n  合计 {len(todo)} 份有缺失；{n-len(todo)} 份六槽位齐全")
    return 0


if __name__ == "__main__":
    sys.exit(main())
