#!/usr/bin/env python3
"""本地前置检索：先查项目前置库，未达阈值才建议联网搜（不静默跳过）。

契约: _proc/tools/presearch
  输入: 查询词（命令行参数），或 --panel 看面板
  输出: 命中 → INTERNAL 出处清单；未命中 → WEB_NEEDED + 该搜什么
  依赖: 标准库 json/re/os/sys；前置库 FORMULA_REGISTRY.json / beat.py / docs/
  被依赖: 任何"新能力开工前"的动作；check.py R11
  约束: 阈值 HIT_MIN=0.75 不可下调；未命中必须显式报 WEB_NEEDED，不许凭记忆凑
  校验: python3 _proc/tools/presearch.py "可灵 motion control"

设计依据（不凭记忆，逐条可查）：
  - Agentic RAG 两阶段：先检索本地库，由"充分性判定"决定是否 fall back
    到联网检索，而非默认联网（deepwiki Agentic RAG Implementations）。
  - Grounded RAG Fallback Chain：本地相似度低于阈值才升级到 web，
    生产日志调优区间 0.72~0.78，取中值 0.75（AWS Bedrock 实践）。
  - provenance 标签：每条结论标 INTERNAL / WEB，让用户知道出处在哪
    （同上，synthesise with provenance labels）。
  - local-first preflight：mimry / skill-preflight 均要求"用前先查本地索引，
    grep 只用于验证"。
"""
# 自举：__file__ 锚定上溯定位 _proc，支持直接 python3 xxx.py 运行
import ast
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROC = os.path.dirname(_HERE)
for _p in (_PROC, os.path.dirname(_PROC)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import json
import math
import re

ROOT = _PROC
REG = os.path.join(ROOT, "FORMULA_REGISTRY.json")
DOCS = os.path.join(ROOT, "docs")
HIT_MIN = 0.75          # Bedrock 生产调优区间 0.72~0.78 的中值
AMBIG_MIN = 0.30        # 低于此才判 WEB_NEEDED；中间档强制先看本地候选
MIN_SOURCE = 8          # 出处字符串最小长度，低于此视为"没写出处"


def _tokens(s):
    """中英混合分词：英文取词，中文取单字 + 2-gram。"""
    out = set()
    for w in re.findall(r"[A-Za-z][A-Za-z0-9_]{1,}", s.lower()):
        out.add(w)
    for seg in re.findall(r"[\u4e00-\u9fff]+", s):
        for i in range(len(seg)):
            out.add(seg[i])
            if i + 1 < len(seg):
                out.add(seg[i:i + 2])
    return out


def _blob(it):
    doc = " ".join(str(it.get(k, "")) for k in
                   ("id", "name", "group", "source", "note", "hint"))
    return doc, _tokens(doc)


def _vocab(items):
    """索引词汇表：只取 id/name 的 token。

    作用是把"路步""作参"这类中文 2-gram 噪声挡在分母外——它们不在任何
    id/name 里，属查询自身措辞产生的伪词，不该拉低得分。
    """
    v = set()
    for it in items:
        v |= _tokens(str(it.get("id", "")) + " " + str(it.get("name", "")))
    return v


def _idf(items, vocab):
    """逆文档频率权重：罕见词权高、通用词权低。

    没有它，"动作"这类通用词一命中就满分，导致"可灵 motion control"
    误判为本地已有。加了它，只有"走路""motion"这种专名命中才算数。
    """
    n = len(items)
    df = {}
    for it in items:
        for t in _blob(it)[1] & vocab:
            df[t] = df.get(t, 0) + 1
    return {t: math.log(n / (1.0 + c)) for t, c in df.items()}


def _score(q, text, vocab, idf):
    """IDF 加权覆盖率：命中词的稀有度权重占查询总权重之比。"""
    qt = _tokens(q) & vocab
    if not qt:
        return 0.0
    dt = _tokens(text)
    hit = sum(idf.get(t, 0.0) for t in qt if t in dt)
    tot = sum(idf.get(t, 0.0) for t in qt)
    return hit / tot if tot > 0 else 0.0


def load_formula():
    """前置库源 1：公式注册表（65 条）。"""
    if not os.path.exists(REG):
        return []
    reg = json.load(open(REG, encoding="utf-8"))
    out = []
    for g in reg.get("groups", []):
        for it in g.get("items", []):
            out.append({
                "kind": "formula",
                "id": it.get("id", ""),
                "name": it.get("name", ""),
                "status": it.get("status", ""),
                "source": it.get("src", "") or it.get("source", ""),
                "hint": it.get("search_hint", ""),
                "note": it.get("note", ""),
                "group": g.get("name", ""),
            })
    return out


def _walk_py():
    """遍历 _proc 下全部 py，跳过备份与字节码目录。"""
    skip = {"_bak", "__pycache__"}
    for dp, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in skip]
        for fn in sorted(files):
            if fn.endswith(".py"):
                yield os.path.join(dp, fn)


def _caps_in_tree(tree):
    """从 AST 取 @capability 的 (名字, 出处)。

    不依赖 import：装饰器只在模块被导入时才执行，逐个 import 既慢又会
    因缺依赖整片丢失，导致已登记的能力被误报成"缺出处"。
    """
    got = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for d in node.decorator_list:
            if not (isinstance(d, ast.Call) and isinstance(d.func, ast.Name)):
                continue
            if d.func.id != "capability" or not d.args:
                continue
            if not isinstance(d.args[0], ast.Constant):
                continue
            name = str(d.args[0].value)
            source = ""
            if len(d.args) > 1 and isinstance(d.args[1], ast.Constant):
                source = str(d.args[1].value)
            for kw in d.keywords:
                if kw.arg == "source" and isinstance(kw.value, ast.Constant):
                    source = str(kw.value.value)
            got.append((name, source))
    return got


def load_caps():
    """前置库源 2：能力表出处（源码静态扫 @capability）与搜索提示。"""
    out, errs = [], []
    for f in _walk_py():
        try:
            tree = ast.parse(open(f, encoding="utf-8").read())
        except SyntaxError as exc:
            errs.append("%s: %s" % (os.path.basename(f), exc))
            continue
        for name, src in _caps_in_tree(tree):
            out.append({"kind": "capability", "id": name, "name": name,
                        "status": "IMPL", "source": src, "hint": "",
                        "note": os.path.basename(f), "group": "角色能力"})
    out += _missing_hints()
    return out, ("; ".join(errs) if errs else "")


def _missing_hints():
    """MISSING_HINT：未实现能力的搜索提示，静态取，不靠 import。"""
    path = os.path.join(ROOT, "motion", "beat.py")
    if not os.path.exists(path):
        return []
    try:
        tree = ast.parse(open(path, encoding="utf-8").read())
    except SyntaxError:
        return []
    for node in tree.body:
        if not (isinstance(node, ast.Assign) and node.targets
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "MISSING_HINT"):
            continue
        if not isinstance(node.value, ast.Dict):
            return []
        got = []
        for k, v in zip(node.value.keys, node.value.values):
            if isinstance(k, ast.Constant) and isinstance(v, ast.Constant):
                got.append({"kind": "capability", "id": str(k.value),
                            "name": str(k.value), "status": "STUB",
                            "source": "", "hint": str(v.value),
                            "note": "未实现", "group": "角色能力"})
        return got
    return []


def load_docs():
    """前置库源 3：docs/ 下的踩坑记录，按二级标题切块。"""
    out = []
    if not os.path.isdir(DOCS):
        return out
    for fn in sorted(os.listdir(DOCS)):
        if not fn.endswith(".md"):
            continue
        path = os.path.join(DOCS, fn)
        cur = fn
        buf = []
        for ln in open(path, encoding="utf-8"):
            if ln.startswith("## "):
                if buf:
                    out.append({"kind": "doc", "id": "%s#%s" % (fn, cur),
                                "name": cur, "status": "IMPL",
                                "source": fn, "hint": "",
                                "note": "".join(buf)[:400], "group": "踩坑记录"})
                cur, buf = ln[3:].strip(), []
            else:
                buf.append(ln)
        if buf:
            out.append({"kind": "doc", "id": "%s#%s" % (fn, cur),
                        "name": cur, "status": "IMPL", "source": fn,
                        "hint": "", "note": "".join(buf)[:400],
                        "group": "踩坑记录"})
    return out


def index_all():
    """汇总三个源，附带导入失败的可见警告。"""
    items = load_formula()
    caps, warn = load_caps()
    items += caps + load_docs()
    return items, warn


def search(query, top=6):
    """本地检索：按覆盖率排序，返回 (命中项, 最高分, 警告)。"""
    items, warn = index_all()
    vocab = _vocab(items)
    idf = _idf(items, vocab)
    scored = []
    for it in items:
        s = _score(query, _blob(it)[0], vocab, idf)
        if s > 0:
            scored.append((s, it))
    scored.sort(key=lambda x: -x[0])
    return scored[:top], warn


def _fmt_hit(s, it):
    src = it.get("source", "") or "（无出处）"
    return ("  %.3f [%s] %-14s %s\n        出处: %s%s"
            % (s, it["kind"], it.get("id", ""), it.get("name", ""),
               src,
               ("\n        提示: " + it["hint"]) if it.get("hint") else ""))


def run(query, top=6):
    """主流程：本地命中达阈值 → INTERNAL；否则 → WEB_NEEDED。"""
    hits, warn = search(query, top)
    if warn:
        print("  ! " + warn)
    print("查询: %r" % query)
    if hits and hits[0][0] >= HIT_MIN:
        print("判定: INTERNAL（本地前置库命中，无需联网）")
        for s, it in hits:
            if s >= HIT_MIN:
                print(_fmt_hit(s, it))
        return 0
    if hits and hits[0][0] >= AMBIG_MIN:
        print("判定: AMBIGUOUS（有本地候选但未达 %.2f，先确认再用联网）" % HIT_MIN)
        print("  本地候选（很可能已经够用，先逐条看）：")
        for s, it in hits[:top]:
            print(_fmt_hit(s, it))
        print("\n  确认这些都不是所需后，才用下列词联网：")
        print("    %s" % " / ".join(sorted(_tokens(query))[:8]))
        return 2
    print("判定: WEB_NEEDED（本地无有效候选，才允许联网搜）")
    if hits:
        print("  弱相关（仅供参考，不足以替代联网检索）：")
        for s, it in hits[:3]:
            print(_fmt_hit(s, it))
    print("\n  建议搜索词:")
    print("    %s" % " / ".join(sorted(_tokens(query))[:8]))
    return 1


def panel():
    """面板：前置库现有条目按组统计，缺口一目了然。"""
    items, warn = index_all()
    if warn:
        print("! " + warn)
    by = {}
    for it in items:
        by.setdefault(it["group"], []).append(it)
    print("前置库面板（%d 条）" % len(items))
    for g in sorted(by):
        grp = by[g]
        done = [i for i in grp if i.get("status") == "IMPL"]
        miss = sum(1 for i in done if len(i.get("source", "")) < MIN_SOURCE)
        stub = len(grp) - len(done)
        print("  %-14s %3d 条   已实现 %2d（缺出处 %d）   未实现 %d"
              % (g, len(grp), len(done), miss, stub))
    print("\n  未实现项无出处属正常，缺出处只统计已实现的")
    return 0


def main():
    """命令行入口：查询 / --panel / --json。"""
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__.strip().splitlines()[-1].strip())
        print("用法: python3 presearch.py <查询词> | --panel [--json]")
        return 2
    if argv[0] == "--panel":
        return panel()
    return run(" ".join(a for a in argv if not a.startswith("--")))


if __name__ == "__main__":
    sys.exit(main())
