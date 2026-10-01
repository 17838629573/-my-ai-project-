#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rk_extract.py —— 从页面源码里抠「目标自述路径」

本项目最亏的一步：猜了十几轮路径，最后发现登录页自己写了 10 条真实功能路径
（含"查看成绩"），而它们历史零探测。而且存档是 GBK，直接 grep 中文返回 0。

这个脚本做三件事：
  1. 自动判编码（meta charset / GBK / UTF-8），不再踩编码坑
  2. 抠 href / action / onclick / location.href / ajax url
  3. 抠 JS 变量拼接（_webRootPath + "xxx"）—— jwmis 的路径就是这么藏的

用法:
  python3 rk_extract.py -f page.html --base https://jwmis.example.com/hsjw/
  python3 rk_extract.py -d evidence/t13/ --json
"""
import argparse, os, re, json, sys, glob

PATS = [
    ("href", re.compile(r'''href\s*=\s*["']([^"']{1,300})["']''', re.I)),
    ("action", re.compile(r'''action\s*=\s*["']([^"']{1,300})["']''', re.I)),
    ("onclick", re.compile(r'''onclick\s*=\s*["']([^"']{1,400})["']''', re.I)),
    ("lochref", re.compile(r'''(?:window\.)?(?:document\.)?location(?:\.href)?\s*=\s*["']([^"']{1,300})["']''', re.I)),
    ("jspath", re.compile(r'''_webRootPath\s*\+\s*["']([^"']{1,300})["']''', re.I)),
    ("jsvar", re.compile(r'''(?:var|let|const)\s+(?:url|uri|path|action|href)\s*=\s*["']([^"']{1,300})["']''', re.I)),
    ("ajax", re.compile(r'''url\s*:\s*["']([^"']{1,300})["']''', re.I)),
    ("open", re.compile(r'''window\.open\(\s*["']([^"']{1,300})["']''', re.I)),
    ("src", re.compile(r'''src\s*=\s*["']([^"']{1,300})["']''', re.I)),
]

# 从 onclick / JS 片段里再抠一层字符串拼接
CONCAT = re.compile(r'''\+\s*["']([A-Za-z0-9_\-./?=&%]{2,200})["']''')
PARAMS = re.compile(r'''[?&]([A-Za-z_][A-Za-z0-9_]{0,30})\s*=''')

INPUT_NAME = re.compile(r'''<input[^>]*name\s*=\s*["']([^"']{1,80})["']''', re.I)


def guess_bytes(raw: bytes):
    """按优先级尝试解码，覆盖 GBK 坑。"""
    head = raw[:2048]
    m = re.search(rb'''charset\s*=\s*["']?\s*([A-Za-z0-9\-_]{2,20})''', head, re.I)
    cands = []
    if m:
        cands.append(m.group(1).decode("ascii", "ignore"))
    cands += ["utf-8", "gbk", "gb18030", "latin-1"]
    for c in cands:
        try:
            t = raw.decode(c)
            return t, c
        except Exception:
            continue
    return raw.decode("utf-8", "replace"), "utf-8(replace)"


def extract(text, base=""):
    out, seen = [], set()

    def add(kind, val, note=""):
        v = (val or "").strip()
        if not v or v.startswith(("#", "javascript:", "mailto:", "data:")):
            return
        if v.startswith("/") and base:
            full = base.rstrip("/") + v
        elif v.startswith("http"):
            full = v
        elif base:
            full = base.rstrip("/") + "/" + v.lstrip("/")
        else:
            full = v
        key = (kind, full)
        if key in seen:
            return
        seen.add(key)
        out.append({"kind": kind, "raw": v, "url": full, "note": note})

    for kind, pat in PATS:
        for m in pat.finditer(text):
            add(kind, m.group(1))
            # onclick 里可能还有 _webRootPath + "..." 的拼接
            if kind in ("onclick", "jsvar", "lochref"):
                for c in CONCAT.finditer(m.group(1)):
                    add(kind + "+concat", c.group(1), note="JS拼接")
                for p in PARAMS.finditer(m.group(1)):
                    add("param", p.group(1), note="参数名")

    for m in CONCAT.finditer(text):
        add("concat", m.group(1), note="JS拼接")
    for m in INPUT_NAME.finditer(text):
        add("input", m.group(1), note="表单字段名")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-f", "--file", action="append", help="HTML 文件，可多次")
    ap.add_argument("-d", "--dir", help="目录，扫 *.html/*.body/*.b")
    ap.add_argument("--base", default="", help="根路径，用于拼出完整 URL")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--urls-only", action="store_true", help="只输出 URL 清单，可直接喂 rk_probe")
    ap.add_argument("--kind", action="append", help="只保留指定 kind，可多次")
    a = ap.parse_args()

    files = list(a.file or [])
    if a.dir:
        for pat in ("*.html", "*.body", "*.b", "*.htm"):
            files += glob.glob(os.path.join(a.dir, pat))
    if not files:
        ap.error("给 -f 或 -d")

    allrows = []
    for fn in files:
        raw = open(fn, "rb").read()
        text, enc = guess_bytes(raw)
        rows = extract(text, a.base)
        for r in rows:
            r["src"] = os.path.basename(fn)
            r["enc"] = enc
        allrows += rows
        print(f"# {fn}  ({enc}, {len(raw)}B) -> {len(rows)} 条", file=sys.stderr)

    if a.kind:
        allrows = [r for r in allrows if r["kind"] in a.kind]

    # 去重
    seen, uniq = set(), []
    for r in allrows:
        k = (r["kind"], r["url"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)

    if a.urls_only:
        for r in uniq:
            if r["kind"] in ("input", "param"):
                continue
            print(r["url"])
        return
    if a.json:
        print(json.dumps(uniq, ensure_ascii=False, indent=2))
        return

    print(f"\n{'KIND':<16}{'URL'}")
    print("-" * 100)
    for r in sorted(uniq, key=lambda x: (x["kind"], x["url"])):
        note = f"   [{r['note']}]" if r.get("note") else ""
        print(f"{r['kind']:<16}{r['url']}{note}")
    print(f"\n[+] {len(uniq)} 条（来源 {len(files)} 文件）")


if __name__ == "__main__":
    main()
