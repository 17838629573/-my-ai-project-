#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rk_morph.py —— 生成「形态变体」URL 清单

本项目在同一个坑上栽了两次：
  主站   /examples/        -> <LEN-1693> 网关拦   （判"面不存在"）
         /examples/index.jsp -> <LEN-2455> 穿透   （面其实是通的）
  jwmis  /public/<自述路径·教室状态> -> <LEN-577> 拦
         /public/<自述路径·校历> -> 200 放行
结论：同一路径换后缀/换形态，可能走完全不同的路由。这个脚本把它变成机械动作。

用法:
  python3 rk_morph.py /examples/ <APPROOT>/public/<自述路径·教室状态> --base https://www.example.com
  python3 rk_morph.py -f paths.txt --base https://x.com --out urls.txt
"""
import argparse, os, sys, json, urllib.parse

JSP = ["index.jsp", "index.html", "index", "main.jsp", "default.jsp", "default.html"]
SUFFIX_SWAP = [".jsp", ".html", ".action", ".do", ".asp", ".aspx", ".php", ""]


def variants(path):
    """对单条路径生成形态变体，返回 [(变体路径, 类型说明)]"""
    out = []
    p = path.rstrip("/")
    has_suffix = "." in os.path.basename(p)
    stem, ext = os.path.splitext(p) if has_suffix else (p, "")

    # 1. 目录 vs 文件
    out.append((path if path.endswith("/") else path + "/", "目录(带尾斜杠)"))
    out.append((path.rstrip("/"), "目录(无尾斜杠)"))

    # 2. 常见首页名
    for j in JSP:
        out.append((p + "/" + j if not has_suffix else os.path.dirname(p) + "/" + j, f"猜测首页:{j}"))

    # 3. 后缀互换 —— 本项目最关键的一档
    if has_suffix:
        for s in SUFFIX_SWAP:
            if s == ext:
                continue
            out.append((stem + s, f"后缀互换:{ext or '(无)'}->{s or '(无)'}"))
        # show.jsp 型：<自述路径·教室状态> -> kbbp.ckjsizt.show.jsp / ckjsizt.show.jsp
        base_name = os.path.basename(stem)
        out.append((stem + ".show.jsp", "数据面变体:.show.jsp"))
        out.append((stem + ".show.html", "数据面变体:.show.html"))

    # 4. 编码变体（观察性，非利用）
    out.append((p + "/%2e%2e%2f", "编码:单层..%2f"))
    out.append((p + "/%252e%252e%252f", "编码:双层%252f"))
    out.append((p + "/..%3b/", "编码:分号路径参数"))

    # 5. 大小写（Windows/部分容器不敏感）
    if has_suffix:
        out.append((stem + ext.upper(), "大小写后缀"))

    # 去重保序
    seen, res = set(), []
    for u, t in out:
        u2 = u.replace("//", "/") if not u.startswith("http") else u
        if u2 in seen or not u2:
            continue
        seen.add(u2)
        res.append((u2, t))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", help="基础路径")
    ap.add_argument("-f", "--file", help="路径清单文件，一行一条")
    ap.add_argument("--base", default="", help="根 URL，拼到路径前")
    ap.add_argument("--out", default="", help="输出文件（默认打印）")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    paths = list(a.paths)
    if a.file:
        with open(a.file, encoding="utf-8") as f:
            paths += [l.strip() for l in f if l.strip() and not l.startswith("#")]
    if not paths:
        ap.error("至少给一条路径或 -f 文件")

    rows = []
    for p in paths:
        for v, t in variants(p):
            rows.append({"url": a.base.rstrip("/") + v, "path": v, "morph": t, "src": p})

    if a.json or a.out.endswith(".json"):
        s = json.dumps(rows, ensure_ascii=False, indent=2)
        print(s)
        if a.out:
            open(a.out, "w", encoding="utf-8").write(s)
        return
    lines = [f"{r['url']}\t# {r['morph']}" for r in rows]
    txt = "\n".join(lines)
    print(txt)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(txt + "\n")
    print(f"\n[+] {len(rows)} 条变体（来自 {len(paths)} 条基础路径）", file=sys.stderr)


if __name__ == "__main__":
    main()
