#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""doc_lint —— 文档结构化门禁（散文检测器）

判定 md 是否为"字段式"而非"散文式"。用途：让工具查出哪些文档还没结构化，
避免人工逐篇判读（人工判读 = AI 幻觉风险）。

规则（可配）:
  R1 连续散文行: 连续 >=PROSE_RUN 行不含字段名前缀 -> 违规
     字段名前缀 = `name:` 或 `name |` 或 `- ` 开头
  R2 长段落: 单行 >LINE_MAX 字符且不含字段名 -> 违规
  R3 无字段: 整份文档字段名行数 <FIELD_MIN -> 违规
  R4 表格外长句: 以中文句号结尾且 >SENT_MAX 字符的行 -> 疑似散文

输出: 每份 md 的违规计数 + 明细；退出码 1 = 有违规（可接门禁）

用法:
    python3 doc_lint.py                # 全量
    python3 doc_lint.py IMPROVE_water.md
    python3 doc_lint.py --json         # 机器可读
"""
import os
import re
import sys
import json
import glob

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 工作流根（本工具在 _tools/）
SKIP = {"_INDEX.md"}

PROSE_RUN = 5      # 连续多少行无字段名 -> 违规
LINE_MAX = 120     # 单行超多少字符且无字段名 -> 违规
FIELD_MIN = 3      # 整份少于多少字段行 -> 违规
SENT_MAX = 60      # 长句阈值

# 字段名: 冒号或竖线跟随，或列表项，或表头
FIELD_RE = re.compile(
    r"^\s*(?:"
    r"[A-Za-z_][\w\.]*\s*[:\|]"            # name: / name |
    r"|[\u4e00-\u9fff]{1,8}\s*[:：\|]"      # 中文字段: 接口: 参数: 注意:
    r"|\*\*[\w\u4e00-\u9fff]+\*\*"        # **模块名**
    r"|-\s"                                   # - 列表
    r"|\|"                                    # 表格
    r"|#{1,6}\s"                              # 标题
    r"|```"                                   # 代码块
    r"|[一二三四五六七八九十]+、"               # 中文编号
    r"|\d+\.\s"                             # 数字编号
    r"|[\w\u4e00-\u9fff]+\s*->"              # 依赖箭头 a -> b
    r")"
)


GEN_MARK = re.compile(r"gen:contract_gen|机器生成|勿手改|机器翻译")


def is_generated(path):
    """机器生成件：只看开头 3 行的标记（正文提及"机器生成"不算）"""
    head = "".join(open(path, encoding="utf-8", errors="replace").readlines()[:3])
    return bool(GEN_MARK.search(head))


def lint_generated(txt, path):
    """机器生成件分两层查（路径一律相对 BASE 拼接，勿再拼子目录）"""
    import os, re
    base = os.path.dirname(os.path.abspath(path))
    iss = []
    in_detail = os.path.basename(base) == "detail"
    if in_detail:
        # 事实层：要求有 api/const 或 up/down 之一即可
        if not re.search(r"^api:|^const:|^up:", txt, re.M):
            iss.append((0, "事实层缺 api/const/up"))
        return iss
    # 定位层
    for f in ("does:", "fact:"):
        if f not in txt:
            iss.append((0, f"缺字段 {f}"))
    m = re.search(r"fact:\s*(\S+)\.md", txt)
    if m and not os.path.exists(os.path.join(BASE, m.group(1) + ".md")):
        iss.append((0, f"fact 断链 {m.group(1)}"))
    for mm in re.finditer(r"^up:\s*(.+)$", txt, re.M):
        for x in mm.group(1).split(","):
            x = x.strip()
            if x and not os.path.exists(os.path.join(BASE, x + ".py")):
                iss.append((0, f"up 断链 {x}"))
    return iss


def lint(path):
    txt = open(path, encoding="utf-8", errors="replace").read()
    if is_generated(path):
        return lint_generated(txt, path), len(txt.splitlines()), 0
    lines = txt.splitlines()
    issues = []
    run = 0
    field_lines = 0
    in_code = False
    for i, ln in enumerate(lines, 1):
        s = ln.strip()
        if s.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not s:
            run = 0
            continue
        is_field = bool(FIELD_RE.match(s))
        if is_field:
            field_lines += 1
            run = 0
        else:
            run += 1
            if run == PROSE_RUN:
                issues.append((i, f"散文段：连续 {PROSE_RUN} 行无字段名"))
        if len(s) > LINE_MAX and not is_field:
            issues.append((i, f"长行 {len(s)} 字符且无字段名"))
        if s.endswith("。") and len(s) > SENT_MAX and not is_field:
            issues.append((i, f"长句 {len(s)} 字符，疑似散文"))
    fname = os.path.basename(path)
    is_m = re.match(r"^[A-Z]+\.[a-z]+\.md$", fname)      # M 层: ATOM.cam.md
    is_l = re.match(r"^[A-Z]+\.md$", fname)               # L 层: ATOM.md
    min_req = 1 if (is_m or is_l) else FIELD_MIN
    if field_lines < min_req:
        issues.append((0, f"字段行仅 {field_lines} 个 < {min_req}"))
    return issues, len(lines), field_lines


def main():
    args = [a for a in sys.argv[1:]]
    as_json = "--json" in args
    args = [a for a in args if not a.startswith("--")]
    if args:
        files = [os.path.join(BASE, a) for a in args]
    else:
        files = []
        for pat in ["*.md", "contracts/*.md", "detail/*.md", "notes/*.md"]:
            files += glob.glob(os.path.join(BASE, pat))
    res = []
    for f in sorted(files):
        if os.path.basename(f) in SKIP:
            continue
        iss, nlines, nfield = lint(f)
        res.append({"file": os.path.relpath(f, BASE), "lines": nlines,
                    "fields": nfield, "issues": len(iss),
                    "detail": [f"L{i}: {m}" if i else m for i, m in iss[:5]]})
    for r in res:
        r["gen"] = is_generated(os.path.join(BASE, r["file"]))
    bad = [r for r in res if r["issues"] > 0]
    if as_json:
        print(json.dumps({"total": len(res), "bad": len(bad), "files": res},
                         ensure_ascii=False, indent=1))
        return 1 if bad else 0
    hum=[r for r in bad if not r['gen']]; gen=[r for r in bad if r['gen']]
    print(f"doc_lint: {len(res)} 份  违规 {len(bad)} 份"
          f"  (人工 {len(hum)} / 机器生成 {len(gen)})\n")
    if gen:
        print("  机器生成件缺字段（改生成器，勿改文档）:")
        for r in gen[:10]: print(f"    {r['file']}: {r['detail'][:2]}")
        print()
    for r in sorted(bad, key=lambda x: -x["issues"])[:30]:
        print(f"  {r['issues']:3d} 处  {r['file']}  (行{r['lines']}/字段{r['fields']})")
        for d in r["detail"][:3]:
            print(f"        {d}")
    if len(bad) > 30:
        print(f"  … 另 {len(bad)-30} 份")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
