#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""contract_recon —— 契约对账测试（reconciliation test）

业界依据（Living Documentation / ShipDocs / Augment）：
  "Always Test Consistency: Every living document must be backed by a
   reconciliation test or contract check that alerts developers of mismatches."
  "Enforcement beats reminders —— 文档更新必须是强制条件，不是靠记得跑。"

本项目此前契约过期 13 小时、8 个新模块未登记，根因就是 contract_gen
靠手动跑。本工具把"契约是否追上代码"变成【可失败】的检查。

检查项:
  R1  每个本地 .py 都有契约（未登记 = 新增模块没进 hier.py）
  R2  契约里的模块都真实存在（幽灵模块）
  R3  契约 mtime 不早于源码 mtime（代码改了没重生成 = 过期）
  R4  契约 api 行与源码公开函数集一致（签名集漂移）
  R5  解析失败的契约不得存在（No Silent Extraction Failures）

退出码: 0=一致 / 1=有漂移（可接 gate_post / CI）
"""
import ast
import os
import sys
import glob

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTRACTS = os.path.join(BASE, "contracts")


def src_modules():
    return {os.path.basename(f)[:-3] for f in glob.glob(os.path.join(BASE, "*.py"))}


def contract_modules():
    """只认 [S]/[TOP] 开头的模块契约。

    contracts/ 下还有 L 层(ATOM.md)、M 层(ATOM.path.md)、_INDEX.md，
    它们不是模块契约，不能拿来和 .py 对账——否则会报一堆假幽灵。
    """
    out = set()
    for f in glob.glob(os.path.join(CONTRACTS, "*.md")):
        stem = os.path.basename(f)[:-3]
        if stem.startswith("_") or "." in stem:
            continue
        try:
            head = open(f, encoding="utf-8").readline()
        except Exception:
            continue
        if head.startswith("[S] ") or head.startswith("[TOP] "):
            out.add(stem)
    return out


def public_fns(mod):
    p = os.path.join(BASE, mod + ".py")
    try:
        t = ast.parse(open(p, encoding="utf-8", errors="replace").read())
    except SyntaxError:
        return None
    return {n.name for n in t.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not n.name.startswith("_")}


def api_of(text):
    for ln in text.split("\n"):
        if ln.startswith("api:"):
            body = ln[4:].strip()
            body = body.split("(+")[0]
            return {x.strip() for x in body.split(",") if x.strip()}
    return set()


def main():
    fails = []
    srcs = src_modules()
    cons = contract_modules()

    # R1 未登记
    hier_missing = []
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import hier
        reg = set()
        for mids in hier.HIER.values():
            for mods in mids.values():
                reg.update(mods)
        reg |= {m for v in hier.TOP.values() for m in v}
        hier_missing = sorted(srcs - reg)
    except Exception as e:
        fails.append("R1 hier.py 导入失败: %s" % type(e).__name__)

    if hier_missing:
        fails.append("R1 源码存在但 hier.py 未登记(%d): %s"
                     % (len(hier_missing), ",".join(hier_missing[:8])))

    # R2 幽灵契约
    ghosts = sorted(cons - srcs)
    if ghosts:
        fails.append("R2 契约存在但源码已删(%d): %s" % (len(ghosts), ",".join(ghosts[:8])))

    # R3/R4/R5 逐模块
    stale, apidrift, errdoc = [], [], []
    for m in sorted(cons & srcs):
        cp = os.path.join(CONTRACTS, m + ".md")
        sp = os.path.join(BASE, m + ".py")
        txt = open(cp, encoding="utf-8").read()
        if "error:" in txt:
            errdoc.append(m)
            continue
        if os.path.getmtime(cp) < os.path.getmtime(sp) - 1:
            stale.append(m)
        src_api = public_fns(m)
        if src_api is not None:
            c_api = api_of(txt)
            # api 行截断到 12 个，只对未截断的做全等比较
            if c_api and "(+" not in txt.split("api:")[1][:400] and c_api != src_api:
                apidrift.append("%s(契约%d/源码%d)" % (m, len(c_api), len(src_api)))

    if stale:
        fails.append("R3 契约过期(代码比契约新，%d): %s" % (len(stale), ",".join(stale[:10])))
    if apidrift:
        fails.append("R4 api 集漂移(%d): %s" % (len(apidrift), ",".join(apidrift[:6])))
    if errdoc:
        fails.append("R5 存在解析失败的契约(须先修源码): %s" % ",".join(errdoc[:6]))

    # R6 why 层缺失。why 是人工写的因果/踩坑（业界 ADR 层），机器不生成。
    #   缺失即"决策没被记录"，将来会重复踩。新增模块尤其容易漏。
    nowhy = []
    for m in sorted(cons & srcs):
        txt = open(os.path.join(CONTRACTS, m + ".md"), encoding="utf-8").read()
        if "why : （缺" in txt:
            nowhy.append(m)
    if nowhy:
        fails.append("R6 缺 why 层文档(%d): %s" % (len(nowhy), ",".join(nowhy[:10])))

    # R7 契约 why 指针指向的文件必须真实存在。
    #   【判据修正记录】最初我写的是"IMPROVE_*.md 无对应 .py 即孤儿"，
    #   实测报 40 个，其中 30 个其实在 _tools/ 下（我只扫了顶层）、
    #   另有 refactor 这类主题型文档本来就不对应模块 —— 全是误报。
    #   这与 V2 那三次误报同源：源码集定义不全。故改为只查【指针有效性】，
    #   这是硬的：契约写了 why: IMPROVE_x.md 而文件不存在 = 真漂移。
    allsrc = set(srcs) | {os.path.basename(f)[:-3] for f in glob.glob(os.path.join(BASE, "_tools", "*.py"))} \
             | {os.path.basename(f)[:-3] for f in glob.glob(os.path.join(BASE, "_tools", "qcheck", "*.py"))}
    badptr = []
    for m in sorted(cons & srcs):
        txt = open(os.path.join(CONTRACTS, m + ".md"), encoding="utf-8").read()
        for ln in txt.split("\n"):
            if ln.startswith("why : ") and ln[6:].strip().endswith(".md"):
                tgt = ln[6:].strip()
                if not os.path.exists(os.path.join(BASE, tgt)):
                    badptr.append("%s→%s" % (m, tgt))
    if badptr:
        fails.append("R7 why 指针指向不存在的文件(%d): %s" % (len(badptr), ",".join(badptr[:6])))

    print("contract_recon: 源码%d 契约%d" % (len(srcs), len(cons)))
    if fails:
        print("\n[FAIL] 契约与代码不一致：")
        for f in fails:
            print("  " + f)
        print("\n修复: python3 _tools/contract_gen.py")
        return 1
    print("[PASS] 契约与代码一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
