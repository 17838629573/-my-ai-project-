#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""why_fill —— 为「人写 IMPROVE」生成补槽位工作单（工具做检索，模型填语义）

流程分工（铁律：工具能做的一律工具做）：
  工具: 定位缺失槽位 → 从原文捞候选句 → 从源码注释捞候选 → 输出到 worklist
  模型: 只看 worklist，逐条判断「候选是否命中 / 要不要另写一句」
        禁止模型全文通读后自由发挥（那正是幻觉来源）

产出: _worklist/<模块>.md   每个缺失槽位下列出原文候选句（带行号）+ 源码注释候选
      模型只需在 `pick:` 后填 `L<行号>` 或 `NEW: ...`，不写散文

用法:
    python3 why_fill.py              # 生成全部人写文档的工作单
    python3 why_fill.py perspective  # 单份
"""
import os
import re
import sys
import glob

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 工作流根（本工具在 _tools/）
WL = os.path.join(BASE, "_worklist")
sys.path.insert(0, BASE)
from why_struct import extract, SLOT_ORDER, SLOT_CN   # 复用槽位定义


def is_stub(txt):
    return txt.startswith("# WHY")


def human_files():
    out = []
    for f in sorted(glob.glob(os.path.join(BASE, "IMPROVE_*.md"))):
        t = open(f, encoding="utf-8", errors="replace").read()
        if not is_stub(t):
            out.append(f)
    return out


def candidates(mod):
    """返回 {slot: [(来源, 行号, 文本)]} —— 工具只做检索，不判断"""
    p = os.path.join(BASE, f"IMPROVE_{mod}.md")
    src_txt = open(p, encoding="utf-8", errors="replace").read()
    doc_lines = [(f"IMPROVE:{os.path.basename(p)}", i, l.strip())
                 for i, l in enumerate(src_txt.splitlines(), 1)
                 if l.strip() and not l.strip().startswith("```")]
    sp = os.path.join(BASE, mod + ".py")
    py_lines = []
    if os.path.exists(sp):
        py_lines = [(f"{mod}.py", i, l.strip().lstrip("#").strip())
                    for i, l in enumerate(open(sp, encoding="utf-8",
                                                errors="replace"), 1)
                    if l.strip().startswith("#") and len(l.strip()) > 6]
    # 宽口径关键词（比 extract 松，宁可多捞给模型筛）
    WIDE = {
        "context":   r"模块|用于|负责|场景|需求|背景|提供|实现",
        "facing":    r"缺失|不足|无法|不能|不|问题|坑|错|误|bug|BUG|旧|曾|冲突|失效|假|硬编码|手填",
        "decided":   r"采用|选择|决定|改用|实现|使用|改为|用|解法|方案|做法|必须|应",
        "neglected": r"而非|而不是|不用|弃用|否决|排除|放弃|不采用|却|但|旧|原|曾用|之前",
        "achieve":   r"以|从而|为了|使得|好处|优势|收益|解决|满足|保证|确保|能|可",
        "accepting": r"代价|缺点|局限|牺牲|风险|代价|不足|但|然而|接受|损失|差|误",
        "basis":     r"来源|依据|文献|实测|搜证|标准|et al|20\d\d|论文|公式|参考|业界",
    }
    out = {s: [] for s in SLOT_ORDER}
    for src, ln, txt in doc_lines + py_lines:
        for slot in SLOT_ORDER:
            if len(re.findall(WIDE[slot], txt)) >= 1 and len(txt) > 8:
                if len(out[slot]) < 6:
                    out[slot].append((src, ln, txt[:120]))
    return out


def main():
    args = sys.argv[1:]
    os.makedirs(WL, exist_ok=True)
    files = human_files()
    if args:
        files = [f for f in files if os.path.basename(f)[8:-3] in args]
    made = 0
    for f in files:
        mod = os.path.basename(f)[8:-3]
        txt = open(f, encoding="utf-8", errors="replace").read()
        e = extract(txt)                       # 已有槽位
        cand = candidates(mod)
        lack = [s for s in SLOT_ORDER if not e[s]]
        if not lack:
            continue
        L = [f"# FILL {mod}   缺 {len(lack)} 槽位   （模型只填 pick，勿写散文）", ""]
        for s in lack:
            L.append(f"## {SLOT_CN[s]} ({s})")
            L.append(f"已填: 无")
            if cand[s]:
                for src, ln, t in cand[s][:5]:
                    L.append(f"  [{src}:L{ln}] {t}")
            else:
                L.append("  (无候选 —— 若确无，填 `NEW: N/A 无记录`)")
            L.append(f"  pick: ____")
            L.append("")
        open(os.path.join(WL, mod + ".md"), "w", encoding="utf-8").write("\n".join(L))
        made += 1
    print(f"[OK] 工作单 {made} 份 -> _worklist/")
    tot = sum(len(open(os.path.join(WL, f), encoding='utf-8').read())
              for f in os.listdir(WL) if f.endswith('.md'))
    print(f"     共 {tot} 字符")


if __name__ == "__main__":
    main()
