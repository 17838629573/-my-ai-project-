#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rk_baseline.py —— 建立目标的「响应层字典」

本项目最贵的一条教训：前四轮 215 个请求全废，因为不知道目标的响应分几层。
这个脚本把"建立基线"变成 5-8 个请求的机械动作，AI 不再需要凭经验猜。

用法:
  python3 rk_baseline.py https://www.example.com
  python3 rk_baseline.py https://www.example.com --auth /system/ --jsp /x.jsp
  python3 rk_baseline.py https://jwmis.example.com --out base_jwmis.json

输出 baseline.json，供 rk_probe.py 自动打标签。
"""
import sys, os, json, argparse, re
from collections import OrderedDict
import rk_core as C

# 版本串正则：本项目靠人眼在 404 页脚发现 Apache Tomcat/9.0.99，这里代码化
VER_PATTERNS = [
    (r"Apache[ -]Tomcat[/ ]([0-9][0-9A-Za-z.\-]*)", "Apache Tomcat"),
    (r"\bTomcat[/ ]([0-9][0-9A-Za-z.\-]*)", "Tomcat"),
    (r"nginx[/ ]([0-9][0-9A-Za-z.\-]*)", "nginx"),
    (r"Apache[/ ]([0-9][0-9A-Za-z.\-]*)", "Apache httpd"),
    (r"OpenResty[/ ]?([0-9][0-9A-Za-z.\-]*)", "OpenResty"),
    (r"PHP[/ ]([0-9][0-9A-Za-z.\-]*)", "PHP"),
    (r"Jetty[/ ]?\(?([0-9][0-9A-Za-z.\-]*)", "Jetty"),
    (r"WebLogic[ ]?([0-9][0-9A-Za-z.\-]*)", "WebLogic"),
    (r"<定制容器名>[/ ]([0-9][0-9A-Za-z.\-]*)", "<定制容器名>"),
    (r"Java[/ ]([0-9][0-9A-Za-z._\-]*)", "Java"),
    (r"Spring[ ]?WebFlow[ ]?([0-9][0-9A-Za-z.\-]*)", "Spring WebFlow"),
    (r"Resin[/ ]([0-9][0-9A-Za-z.\-]*)", "Resin"),
    (r"JBoss[^0-9]{0,6}([0-9][0-9A-Za-z.\-]*)", "JBoss"),
    (r"WAF|waf", None),
]

AUTH_HINTS = ["登录", "登錄", "login", "sign in", "请登录", "需要登录", "未登录",
              "凭证已失效", "会话", "session expired", "unauthorized"]


def looks_auth(text, ct):
    low = (text or "").lower()
    return sum(1 for h in AUTH_HINTS if h.lower() in low) >= 1


def scan_versions(text):
    """从任意响应正文里扫版本串。jwmis 的 9.0.99 就是这样捡到的。"""
    out = {}
    for pat, name in VER_PATTERNS:
        if name is None:
            continue
        m = re.search(pat, text or "")
        if m:
            out.setdefault(name, set()).add(m.group(1).rstrip(".</"))
    return {k: sorted(v) for k, v in out.items()}


def probe(base, paths, delay, timeout, verify, redirect):
    rows = []
    for p in paths:
        url = base.rstrip("/") + p if p.startswith("/") else base.rstrip("/") + "/" + p
        f, resp = C.observe(url, timeout=timeout, delay=delay, verify=verify,
                            allow_redirects=redirect)
        if f is None:
            rows.append((url, None, resp))
            continue
        rows.append((url, f, resp))
    return rows


def build(base, args):
    rnd = C.rand_str(10)
    paths = []

    # 1) 随机根路径（不存在）—— 通常暴露网关/容器默认 404
    paths.append(f"/{rnd}")
    paths.append(f"/{rnd}/")
    # 2) 随机 .jsp —— 探测应用层是否接管后缀（本项目关键分流点）
    paths.append(f"/{rnd}.jsp")
    # 3) 随机 .html
    paths.append(f"/{rnd}.html")
    # 4) 已知鉴权面（用户可指定）
    for a in (args.auth or []):
        paths.append(a if a.startswith("/") else "/" + a)
    # 5) 根目录本身
    paths.append("/")

    rows = probe(base, paths, args.delay, args.timeout, args.verify, args.redirect)

    layers = OrderedDict()
    versions = {}
    seen_md5 = {}
    seq = {"404": 0, "200": 0, "other": 0}

    for url, f, resp in rows:
        if f is None:
            print(f"  [!] {url} -> ERROR: {resp}")
            continue
        body = resp.content.decode("utf-8", "replace") if resp.content is not None else ""
        vs = scan_versions(body + " " + (f.get("server") or ""))
        for k, v in vs.items():
            versions.setdefault(k, []).extend(v)
        for k in versions:
            versions[k] = sorted(set(versions[k]))

        st = f["status"]
        if st == 404:
            seq["404"] += 1
            name = "404_1" if seq["404"] == 1 else f"404_{seq['404']}"
        elif st == 200:
            if f["real_len"] == 0:
                name = "200_empty"
            elif looks_auth(body, f["ct"]):
                name = "auth_wall"
            else:
                seq["200"] += 1
                name = "200_ok" if seq["200"] == 1 else f"200_ok_{seq['200']}"
        elif st in (301, 302, 307, 308):
            name = f"redirect_{st}"
        elif st == 400:
            name = "400_badreq"
        elif st in (401, 403):
            name = f"deny_{st}"
        elif st >= 500:
            name = f"error_{st}"
        else:
            seq["other"] += 1
            name = f"other_{st}"

        # 同一 md5 只保留首次出现的层名（去重：多个随机路径可能打到同一层）
        if f["md5"] in seen_md5:
            continue
        seen_md5[f["md5"]] = name
        layers[name] = {
            "status": st, "cl": f["real_len"], "md5": f["md5"],
            "ct": f["ct"], "sample_url": url,
            "head": f["head"][:200],
            "server": f["server"], "envoy": f["envoy"],
            "location": f["location"],
        }
        print(f"  [{name:12s}] {st}·{f['real_len']}B·{f['ct'] or '-':20s} {url}")

    out = {
        "target": base,
        "built_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "layers": layers,
        "versions": versions,
        "notes": "由 rk_baseline.py 生成。md5 用于 rk_probe.py 精确比对。",
    }
    with open(args.out, "w", encoding="utf-8") as fo:
        json.dump(out, fo, ensure_ascii=False, indent=2)
    print(f"\n[+] 基线写入 {args.out}   层数={len(layers)}")
    if versions:
        print("[+] 扫到版本串:", json.dumps(versions, ensure_ascii=False))
    else:
        print("[.] 未扫到版本串（可能被定制错误页隐藏，或需 --auth 指定更有信息量的面）")
    return out


def main():
    ap = argparse.ArgumentParser(description="建立目标响应层基线")
    ap.add_argument("base", help="目标根 URL，如 https://www.example.com")
    ap.add_argument("--auth", action="append", help="已知鉴权路径，可多次，如 /system/")
    ap.add_argument("--delay", type=float, default=8.0, help="请求间隔秒（默认8）")
    ap.add_argument("--timeout", type=float, default=12.0)
    ap.add_argument("--out", default="baseline.json")
    ap.add_argument("--verify", action="store_true", help="校验证书")
    ap.add_argument("--redirect", action="store_true", help="跟随重定向（默认不跟随，以观察30x）")
    a = ap.parse_args()
    print(f"[*] 基线探测 {a.base}  间隔 {a.delay}s")
    build(a.base, a)


if __name__ == "__main__":
    main()
