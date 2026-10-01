#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rk_cve.py —— 版本 × CVE 确定性比对

为什么这块必须代码化（本项目血泪）：
  我在对话里凭模型内部知识判 CVE，犯了两次错——
    * 把 CVE-2025-55754 当成 RCE（实为 ANSI 控制台操纵，官方定 Low）
    * 漏掉 2026 年发布的一整批 CVE（因为模型知识停在 2025）
  而 9.0.108 正好是 CVE-2025-55752 影响范围的**上界**（<=9.0.108，修复版 9.0.109），
  这种边界值人工看最容易错。

分工：
  数据获取 = AI 用联网搜索（本沙盒对 NVD/OSV 出口受限）
  命中判定 = 本脚本（确定性，不会错）

用法:
  # 1) 生成一个空的 feed 模板，交给 AI 去搜
  python3 rk_cve.py --init apache-tomcat --version 9.0.108
  # 2) AI 把搜到的 CVE 填进 feed 后，做比对
  python3 rk_cve.py --feed tomcat.json --version 9.0.108
  # 3) 快速手判单条
  python3 rk_cve.py --version 9.0.108 --intro 9.0.0.M11 --fixed 9.0.109 --id CVE-2025-55752
"""
import argparse, json, os, re, sys


def vkey(v):
    """Tomcat 风格版本号 -> 可比较元组。支持 9.0.108 / 7.0.109 / 9.0.0.M11 / 8.5.100"""
    v = (v or "").strip()
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:[\.\-](M\d+|[A-Za-z]+\d*|\d+))?$", v)
    if not m:
        m2 = re.match(r"^(\d+)\.(\d+)(?:[\.\-](\d+))?", v)
        if not m2:
            return (0, 0, 0, "", 0)
        a, b, c = int(m2.group(1)), int(m2.group(2)), int(m2.group(3) or 0)
        return (a, b, c, "", 0)
    a, b, c = int(m.group(1)), int(m.group(2)), int(m.group(3))
    suf = m.group(4) or ""
    # 里程碑 M11 排在正式版之前
    if re.match(r"^M\d+$", suf):
        return (a, b, c, "M", int(suf[1:]) - 1000)
    if re.match(r"^\d+$", suf):
        return (a, b, int(suf), "", 0)
    return (a, b, c, suf, 0)


def cmp(a, b):
    ka, kb = vkey(a), vkey(b)
    return (ka > kb) - (ka < kb)


def in_range(ver, intro=None, fixed=None):
    """判断 ver 是否落在 [intro, fixed) 或 [intro, <=fixed-1]。
    Tomcat 官方语义：Affects: intro through last_bad，修复版 = fixed。
    即命中条件： ver >= intro  且  ver < fixed
    """
    if not ver:
        return None
    lo_ok = True if not intro else cmp(ver, intro) >= 0
    hi_ok = True if not fixed else cmp(ver, fixed) < 0
    return lo_ok and hi_ok


def judge(ver, e):
    hit = in_range(ver, e.get("intro"), e.get("fixed"))
    flags = []
    if hit and e.get("fixed") and cmp(ver, e["fixed"]) < 0:
        # 是否边界命中：目标版本是"最后一个受影响版本"
        flags.append("需升级至 " + e["fixed"])
    if hit and not e.get("fixed"):
        flags.append("无修复版本")
    if e.get("eol"):
        flags.append("EOL分支:上游不再提供补丁")
    if hit and e.get("note"):
        flags.append(e["note"])
    return {"id": e.get("id", "?"), "hit": hit,
            "cvss": e.get("cvss"), "epss": e.get("epss"),
            "summary": e.get("summary", ""), "flags": flags,
            "fixed": e.get("fixed"), "intro": e.get("intro")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--feed", help="CVE feed JSON")
    ap.add_argument("--version", default=None, help="目标版本，如 9.0.108")
    ap.add_argument("--init", help="生成空 feed 模板（给产品名）")
    ap.add_argument("--id", help="单条快速判定的 CVE 编号")
    ap.add_argument("--intro", help="单条：起始受影响版本")
    ap.add_argument("--fixed", help="单条：修复版本")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.init is None and a.version is None and a.feed is None:
        ap.error("用 --init 生成模板，或 --version X [--feed f] 判定")

    if a.init:
        tpl = {
            "product": a.init, "checked_version": a.version,
            "source": "由 AI 联网搜索填充（NVD/CVE.org/厂商公告/EPSS），勿凭模型记忆",
            "entries": [
                {"id": "CVE-YYYY-NNNNN", "intro": "9.0.0", "fixed": "9.0.109",
                 "cvss": 0.0, "epss": "", "eol": False,
                 "summary": "一句话危害（务必核对真实危害，别看标题想当然）",
                 "note": "触发条件/前提，如 需rewrite valve / 需Windows控制台"}
            ]
        }
        print(json.dumps(tpl, ensure_ascii=False, indent=2))
        return

    if a.id:
        r = judge(a.version, {"id": a.id, "intro": a.intro, "fixed": a.fixed})
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return

    if not a.feed:
        ap.error("给 --feed 或 --init 或 --id")

    feed = json.load(open(a.feed, encoding="utf-8"))
    rows = [judge(a.version, e) for e in feed.get("entries", [])]
    hits = [r for r in rows if r["hit"]]
    miss = [r for r in rows if not r["hit"]]

    print(f"目标版本 {a.version}   产品 {feed.get('product','?')}")
    print("=" * 90)
    print(f"命中 {len(hits)} / 共 {len(rows)}\n")
    for r in hits:
        cv = f"CVSS {r['cvss']}" if r["cvss"] else "CVSS ?"
        print(f"  [命中] {r['id']}  {cv}  {r['summary']}")
        for f in r["flags"]:
            print(f"         - {f}")
    if miss:
        print(f"\n未命中 {len(miss)}:")
        for r in miss:
            print(f"  [ - ] {r['id']}  (范围 {r['intro'] or '?'} ~ {r['fixed'] or '?'})")

    if a.json:
        print(json.dumps({"version": a.version, "hits": hits, "miss": miss},
                         ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
