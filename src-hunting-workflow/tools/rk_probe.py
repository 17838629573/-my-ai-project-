#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rk_probe.py —— 批量只读探测 + 自动分层打标 + 落盘

AI 在这步只做一件事：看输出表里的 NEW / 异常行，判断它意味着什么。
分类、比对、存档全部由脚本完成。

用法:
  python3 rk_probe.py -f urls.txt --baseline baseline.json --out r1.json --ev evidence/t1
  python3 rk_probe.py -u https://a/ -u https://b/ --delay 8
  python3 rk_probe.py -f urls.txt --scan-version

输出:
  * 终端表格：URL / 状态 / 长度 / 类型 / 层标签 / 是否 NEW
  * JSON：全量指纹
  * --ev 目录：每请求存 .h(响应头) .b(正文) .json(指纹)
"""
import argparse, os, sys, json, time
import rk_core as C
from rk_baseline import scan_versions

BAR = "-" * 100


def load_urls(a):
    urls = []
    if a.file:
        with open(a.file, encoding="utf-8") as f:
            for l in f:
                l = l.split("#")[0].strip() if a.strip_comment else l.strip()
                if l:
                    urls.append(l.split("\t")[0].strip())
    urls += list(a.url or [])
    return urls


def run(urls, a):
    base = C.load_baseline(a.baseline) if a.baseline else {}
    layers = base.get("layers", {}) if isinstance(base, dict) else {}
    rows, new_hits, versions = [], [], {}

    print(BAR)
    print(f"{'#':>3} {'ST':>4} {'LEN':>7} {'CTYPE':<20} {'LAYER':<14} {'FLAG':<6} URL")
    print(BAR)

    for i, u in enumerate(urls, 1):
        if a.allow_host and not C.check_host(u, a.allow_host):
            print(f"  [x] 跳过（域名白名单外）: {u}")
            continue
        f, resp = C.observe(u, timeout=a.timeout, verify=a.verify,
                            allow_redirects=a.redirect)
        if i > 1:
            time.sleep(a.delay)
        if f is None:
            print(f"{i:>3} {'ERR':>4} {'-':>7} {'-':<20} {'-':<14} {'-':<6} {u}  [{resp[:40]}]")
            rows.append({"url": u, "error": resp})
            continue

        layer = C.match_layer(f, layers)
        flag = ""
        if layer == "NEW" or layer.endswith("?"):
            flag = "NEW"
            new_hits.append((u, f))
        if f["real_len"] == 0 and f["status"] == 200:
            flag = (flag + ",0B").lstrip(",")
        if f["status"] in (301, 302, 307, 308):
            flag = (flag + f",{f['status']}").lstrip(",")

        if a.scan_version and resp is not None:
            body = resp.content.decode("utf-8", "replace")
            vs = scan_versions(body + " " + (f.get("server") or ""))
            for k, v in vs.items():
                versions.setdefault(k, []).extend(v)

        print(f"{i:>3} {f['status']:>4} {f['real_len']:>7} {(f['ct'] or '-')[:19]:<20} "
              f"{layer:<14} {flag:<6} {u}")

        rec = {"url": u, "layer": layer, "flag": flag, **{k: v for k, v in f.items() if k != "headers"}}
        if a.keep_headers:
            rec["headers"] = f["headers"]
        rows.append(rec)

        if a.ev:
            tag = f"r{i:02d}-{abs(hash(u)) % 10000:04d}"
            C.save_evidence(a.ev, tag, f, resp)

    print(BAR)
    print(f"[+] 完成 {len(rows)} 条    NEW/异常 {len(new_hits)} 条")

    if new_hits:
        print("\n[!] 与基线不一致的响应（重点看这里）：")
        for u, f in new_hits:
            print(f"    {u}")
            print(f"       {f['status']}·{f['real_len']}B·{f['ct']}·md5={f['md5'][:12]}")
            print(f"       head: {f['head'][:160]!r}")

    if a.scan_version and versions:
        for k in versions:
            versions[k] = sorted(set(versions[k]))
        print("\n[+] 版本串:", json.dumps(versions, ensure_ascii=False))

    if a.out:
        meta = {"target": urls[0] if urls else "", "count": len(rows),
                "baseline": a.baseline or "", "rows": rows, "versions": versions}
        with open(a.out, "w", encoding="utf-8") as fo:
            json.dump(meta, fo, ensure_ascii=False, indent=2)
        print(f"\n[+] JSON 写入 {a.out}")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-f", "--file", help="URL 清单文件")
    ap.add_argument("-u", "--url", action="append", help="单条 URL，可多次")
    ap.add_argument("--baseline", help="baseline.json，用于自动分层打标")
    ap.add_argument("--out", help="结果 JSON")
    ap.add_argument("--ev", help="证据落盘目录")
    ap.add_argument("--delay", type=float, default=8.0, help="请求间隔秒（默认8）")
    ap.add_argument("--timeout", type=float, default=12.0)
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--redirect", action="store_true", help="跟随重定向")
    ap.add_argument("--scan-version", action="store_true", help="扫响应正文里的版本串")
    ap.add_argument("--keep-headers", action="store_true")
    ap.add_argument("--allow-host", action="append", help="域名白名单，可多次")
    ap.add_argument("--strip-comment", action="store_true", help="剥离 # 后注释")
    a = ap.parse_args()
    urls = load_urls(a)
    if not urls:
        ap.error("没有 URL：用 -f 或 -u")
    run(urls, a)


if __name__ == "__main__":
    main()
