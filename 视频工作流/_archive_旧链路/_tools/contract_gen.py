#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""contract_gen —— 代码 → 结构化契约 的翻译器（零手写转述）

用法:
    python3 contract_gen.py            # 全量重生成
    python3 contract_gen.py physics    # 只生成一个

三层分离（勿混）:
    contracts/<m>.md   定位层：内部大概做了什么 + 大类 + api 名（无行号/无签名/无值）
    detail/<m>.md      事实层：机器翻译的详细实现（行号/签名/调用/常量/边界）
    IMPROVE_<m>.md     why 层：人工写的依据/踩坑/意图（本脚本**从不覆盖**）

契约层末尾两行指针:
    fact: detail/<m>.md       —— 机器保证与代码同步
    why : IMPROVE_<m>.md      —— 可能缺失，缺失即提示

事实层禁止手写；why 层禁止机器生成。两者分开存，互不污染。
"""
import ast
import os
import re
import sys
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 工作流根（本工具在 _tools/）
CONTRACTS = os.path.join(BASE, "contracts")
DETAIL = os.path.join(BASE, "detail")

from hier import HIER, TOP, LDESC
TOP_ALL = sorted({m for v in TOP.values() for m in v})
from fact_extract import (imports_of, module_facts, rules_of)
from contract_render import render_S, render_D


def local_modules():
    return {f[:-3] for f in os.listdir(BASE) if f.endswith(".py")}
















# ---------- 定位层（精简） ----------


# ---------- 事实层（详细） ----------


def main():
    os.makedirs(CONTRACTS, exist_ok=True)
    os.makedirs(DETAIL, exist_ok=True)
    mods = local_modules()
    loc_map = {}
    for L, ms in HIER.items():
        for M, ss in ms.items():
            for s in ss:
                loc_map[s] = (L, M)
    for L, ts in TOP.items():
        for t in ts:
            loc_map[t] = (L, "_top")

    dep, rdep = defaultdict(set), defaultdict(set)
    for m in mods:
        im, _ = imports_of(m)
        for x in im:
            if x in mods and x != m:
                dep[m].add(x)
                rdep[x].add(m)
    depth = {}

    def dd(m, seen=None):
        if m in depth:
            return depth[m]
        seen = seen or set()
        if m in seen:
            return 0
        seen.add(m)
        ds = [dd(x, seen) for x in dep[m]]
        depth[m] = 0 if not ds else max(ds) + 1
        return depth[m]
    for m in mods:
        dd(m)

    targets = [sys.argv[1]] if len(sys.argv) > 1 else sorted(mods)
    facts = {}
    _broken = []
    for m in targets:
        f = module_facts(m)
        if not f:
            continue
        # 【No Silent Extraction Failures】业界原话：解析失败必须中止构建或让
        #   测试失败，而不是生成空/残缺输出。旧实现只写一行 error: 照常出契约，
        #   等于静默产出残缺文档——正是业界明令禁止的失败模式。
        if f.get("error"):
            _broken.append("%s: %s" % (m, f["error"]))
            continue
        facts[m] = f
        open(os.path.join(CONTRACTS, m + ".md"), "w", encoding="utf-8").write(
            render_S(m, f, dep[m], rdep[m], depth[m], loc_map) + "\n")
        # 【已停用】detail/ 事实层不再生成：全量 AST 转储维护成本高、正文价值低。
        #   契约自带 impl:（粗略内部实现）足够定位；细节直接读源码。
        #   open(os.path.join(DETAIL, m + ".md"), "w", encoding="utf-8").write(
        #       render_D(m, f, dep[m], rdep[m]) + "\n")

    # 【No Silent Extraction Failures】解析失败必须中止，且中止发生在【写完之后】
    #   （先把能生成的写好，再整体失败退出）——注释见上。
    if _broken:
        raise SystemExit("[FAIL] 源码解析失败，契约生成中止（禁静默产出残缺）：\n  "
                         + "\n  ".join(_broken))

    # 清理旧的 M/L/INDEX
    for fn in list(os.listdir(CONTRACTS)):
        if not fn.endswith(".md"):
            continue
        stem = fn[:-3]
        if stem == "_INDEX" or stem in LDESC or ("." in stem and stem.split(".")[0] in HIER):
            os.remove(os.path.join(CONTRACTS, fn))

    # 【补】清理源码已删的模块契约。
    #   旧逻辑只清 M/L/INDEX，导致已删模块（如 deps_sync）的契约永久残留，
    #   contract_recon 会一直报假幽灵。业界：生成必须可重跑且不留残骸。
    _alive = {m for L in HIER for M in HIER[L] for m in HIER[L][M]} | \
             {t for ts in TOP.values() for t in ts}
    for fn in list(os.listdir(CONTRACTS)):
        if not fn.endswith(".md"):
            continue
        stem = fn[:-3]
        if stem.startswith("_") or "." in stem or stem in LDESC:
            continue
        if stem not in _alive:
            os.remove(os.path.join(CONTRACTS, fn))

    mn = lambda L, M: f"{L}/{M}"
    allmods = {m for L in HIER for M in HIER[L] for m in HIER[L][M]} | \
              {t for ts in TOP.values() for t in ts}
    mout, muses, minner = defaultdict(set), defaultdict(set), defaultdict(int)
    for L, ms in HIER.items():
        for M, ss in ms.items():
            for s in ss:
                for d in dep[s]:
                    if d in allmods:
                        dl, dm = loc_map.get(d, ("?", "?"))
                        if (dl, dm) == (L, M):
                            minner[(L, M)] += 1
                        else:
                            muses[(L, M)].add(mn(dl, dm))
                for r in rdep[s]:
                    if r in allmods:
                        rl, rm = loc_map.get(r, ("?", "?"))
                        if (rl, rm) != (L, M) and rm != "_top":
                            mout[(L, M)].add(mn(rl, rm))
    for L, ms in HIER.items():
        for M, ss in ms.items():
            lines = [f"[M] {mn(L, M)}  S={len(ss)}: {','.join(ss)}"]
            r = " ".join(sorted({t for s in ss for t in rules_of(s).split()}))
            if r.strip():
                lines.append("rule: " + r)
            if muses[(L, M)]:
                lines.append("uses: " + ",".join(sorted(muses[(L, M)])))
            if mout[(L, M)]:
                lines.append("usedby: " + ",".join(sorted(mout[(L, M)])))
            lines.append(f"inner_calls={minner[(L, M)]}")
            open(os.path.join(CONTRACTS, mn(L, M).replace("/", ".") + ".md"), "w",
                 encoding="utf-8").write("\n".join(lines) + "\n")
    for L in HIER:
        ms = list(HIER[L])
        tops = TOP.get(L, [])
        ss = [s for M in ms for s in HIER[L][M]]
        ext = set()
        for M in ms:
            ext |= muses[(L, M)]
        ext = {e for e in ext if not e.startswith(L + "/")}
        lines = [f"[L] {L}  M={len(ms)}  S={len(ss)}", "desc: " + LDESC[L],
                 "M: " + ", ".join(mn(L, m) for m in ms) +
                 (f"  +TOP:{','.join(tops)}" if tops else "")]
        if ext:
            lines.append("uses_out: " + ",".join(sorted(ext)))
        r = " ".join(sorted({t for s in ss + tops for t in rules_of(s).split()}))
        if r.strip():
            lines.append("rule: " + r)
        open(os.path.join(CONTRACTS, L + ".md"), "w", encoding="utf-8").write(
            "\n".join(lines) + "\n")
    idx = ["# INDEX（机器生成，勿手改）", "",
           "两层分离：contracts/<m>.md 定位（含 impl 粗略实现）→ IMPROVE_<m>.md 依据（人工，脚本从不覆盖）",
           "detail/ 事实层已停用（全量 AST 转储维护成本高、正文价值低），细节直接读源码。",
           "读法：先查 FILEMAP.md 按用途定位文件 → [L] 大模块 → [M] 中模块 → [S] 具体模块 → 按 why 指针取依据。",
           "改任一模块前，看该契约的 edit: 行——列出必须同步核对的文件，禁止一次性读全量。", ""]
    for L in HIER:
        tot = sum(len(v) for v in HIER[L].values())
        idx.append(f"## {L}  ({len(HIER[L])}M / {tot}S{'+TOP' if TOP.get(L) else ''})")
        for M in HIER[L]:
            idx.append(f"  {M:10s} <- {','.join(HIER[L][M])}")
        if TOP.get(L):
            idx.append(f"  [TOP] {','.join(TOP[L])}")
        idx.append("")
    idx.append("## 工具")
    idx.append("  python3 contract_gen.py          # 全量重生成（改代码后必跑）")
    idx.append("  python3 contract_gen.py physics  # 只生成一个")
    open(os.path.join(CONTRACTS, "_INDEX.md"), "w", encoding="utf-8").write(
        "\n".join(idx) + "\n")

    # ---- FILEMAP：明文文件清单，回答"哪个文件是做什么的 / 改它要动哪些文件" ----
    fm = ["# FILEMAP（机器生成，勿手改）", "",
          "用途：不读全量代码即可定位。每行 = 一个文件做什么 + 改它必须同步核对哪些文件。",
          "格式：文件  @层/组  | 用途  | edit: 改前须核对的文件", ""]
    for m in sorted(facts):
        f = facts[m]
        L, M = loc_map.get(m, ("?", "?"))
        brief = (f["doc"].split("\n")[0][:70] if f["doc"] else "").strip()
        if not brief:
            pub = [x["name"] for x in f["fns"] if x["public"]]
            brief = "提供 " + ", ".join(pub[:5]) if pub else "（内部模块，无公开接口）"
        touch = sorted(set(dep.get(m, [])) | set(rdep.get(m, [])))
        fm.append("%-22s @%s/%-8s | %s | edit: %s"
                  % (m + ".py", L, M, brief, ",".join(touch) if touch else "（无）"))
    fm.append("")
    fm.append("## 顶层入口（不在 HIER 分组内，独立成片/装配入口）")
    for m in sorted(TOP_ALL):
        f = facts.get(m)
        brief = (f["doc"].split("\n")[0][:70] if f and f["doc"] else "（见源码）").strip()
        touch = sorted(set(dep.get(m, [])) | set(rdep.get(m, [])))
        fm.append("%-22s @TOP         | %s | edit: %s"
                  % (m + ".py", brief, ",".join(touch) if touch else "（无）"))
    open(os.path.join(BASE, "FILEMAP.md"), "w", encoding="utf-8").write(
        "\n".join(fm) + "\n")

    nc = len([f for f in os.listdir(CONTRACTS) if f.endswith(".md")])
    tc = sum(len(open(os.path.join(CONTRACTS, f), encoding="utf-8").read())
             for f in os.listdir(CONTRACTS) if f.endswith(".md"))
    print(f"[OK] contracts/ {nc} 份 {tc} 字符   （detail/ 已停用）")


if __name__ == "__main__":
    main()
