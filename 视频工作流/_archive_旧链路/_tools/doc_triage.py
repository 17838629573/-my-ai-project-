#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""doc_triage —— 散文文档分诊：机器先分类，人只复核低置信部分

核心问题：这份文档里的信息，AI 丢了它还能不能从代码重建？
  REDOABLE  可从代码 AST 重建（签名/依赖/常量/调用）→ 压缩不损失
  WHY       代码里没有的因果/依据/坑/意图        → 必须保留，丢即永久损失
  META      路由指针/状态表/清单                → 可机械转字段
  FILLER    过渡句/修辞/重复                    → 可删

置信度：按命中关键词数打分。低置信行单独列出，**只复核这些**。

用法:
    python3 doc_triage.py                 # 全量（doc_lint 报的人工文档）
    python3 doc_triage.py CONTRACT.md     # 单份，打印逐行判定
    python3 doc_triage.py --low           # 只看低置信行（待人工复核）
"""
import os
import re
import sys
import glob

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 工作流根（本工具在 _tools/）

# 因果/依据/坑：代码里推不出来的东西
WHY_RE = re.compile(
    r"因为|所以|因此|由于|导致|原因|曾|曾经|翻车|教训|勿|禁|不要回退|已修|"
    r"旧|原来|之前|冲突|不一致|bug|BUG|失效|假|误|错|来源|依据|文献|实测|"
    r"搜证|标准|et al|20\d\d|→|=>|故|坑|注意|警告|根因|为什么")
# 可从 AST 重建的事实
REDO_RE = re.compile(
    r"def |import |class |\(\)\s*->|参数|返回值|调用|依赖|被依赖|常量|字段|"
    r"函数|模块|签名|行号|接口")
# 元数据/清单
META_RE = re.compile(r"^\s*\| |状态|清单|表|路由|指针|路径|命令|python3 |退出码|PASS|FAIL")


NOISE = re.compile(r"^[\s\-\|=\*\.:>`~_]+$")


def classify(line):
    s = line.strip()
    if not s or s.startswith("#") or s.startswith("```") or s.startswith(">"):
        return "SKIP", 1.0, "标题/代码/引用"
    if NOISE.match(s):
        return "SKIP", 1.0, "分隔线/表格边框"
    # 实质内容太短（<8字符）也算噪音
    if len(re.sub(r"[^\w\u4e00-\u9fff]", "", s)) < 4:
        return "SKIP", 1.0, "无实质内容"
    w = len(WHY_RE.findall(s))
    r = len(REDO_RE.findall(s))
    m = 1 if META_RE.search(s) else 0
    if m:
        return "META", 0.9, "清单/表格/命令"
    if w >= 2:
        return "WHY", 0.9, f"因果词×{w}"
    if w == 1 and r == 0:
        return "WHY", 0.5, "仅1个因果词，需复核"
    if r >= 1 and w == 0:
        return "REDOABLE", 0.8, f"可从代码重建×{r}"
    # 无因果、无可重建特征：看是不是举例/场景描述（多为可删的展开说明）
    if re.search(r"比如|例如|例：|场景|用法|效果|步骤|如下|下面|具体", s):
        return "FILLER", 0.7, "举例/展开说明，可压缩"
    return "UNKNOWN", 0.2, "无特征，需复核"


def triage(path):
    out = []
    for i, ln in enumerate(open(path, encoding="utf-8", errors="replace"), 1):
        k, conf, why = classify(ln)
        if k == "SKIP":
            continue
        out.append((i, k, conf, why, ln.strip()[:90]))
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    low_only = "--low" in sys.argv
    if args:
        files = [os.path.join(BASE, a) for a in args]
    else:
        files = [f for f in glob.glob(os.path.join(BASE, "*.md"))
                 if os.path.basename(f) != "_INDEX.md"]

    grand = {"WHY": 0, "REDOABLE": 0, "META": 0, "UNKNOWN": 0, "FILLER": 0}
    lows = []
    report = []
    for f in sorted(files):
        rows = triage(f)
        if not rows:
            continue
        c = {"WHY": 0, "REDOABLE": 0, "META": 0, "UNKNOWN": 0, "FILLER": 0}
        for _, k, _, _, _ in rows:
            c[k] += 1
            grand[k] += 1
        for r in rows:
            if r[2] < 0.6:
                lows.append((os.path.basename(f),) + r)
        report.append((os.path.basename(f), len(rows), c))

    print(f"doc_triage: {len(files)} 份  "
          f"WHY {grand['WHY']} / REDOABLE {grand['REDOABLE']} / "
          f"META {grand['META']} / FILLER {grand['FILLER']} / "
          f"UNKNOWN {grand['UNKNOWN']}\n")
    if not low_only:
        for name, n, c in sorted(report, key=lambda x: -x[2]["WHY"])[:20]:
            print(f"  WHY{c['WHY']:3d} REDO{c['REDOABLE']:3d} "
                  f"META{c['META']:3d} ?{c['UNKNOWN']:3d}   {name}")
    print(f"\n=== 低置信行（仅复核这些，共 {len(lows)} 行）===")
    for fn, i, k, conf, why, txt in lows[:40]:
        print(f"  {fn}:L{i} [{k} {conf}] {why}")
        print(f"      {txt}")
    if len(lows) > 40:
        print(f"  … 另 {len(lows)-40} 行")


if __name__ == "__main__":
    main()
