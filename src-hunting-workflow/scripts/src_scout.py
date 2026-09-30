#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
src_scout.py —— SRC 自动化前置扫描器（漏斗第一层）

定位：只做「穷举 + 粗判」，产出【疑似清单】交给人工按测试卡深挖。
本脚本不做最终漏洞判定，也不提交任何报告。

子命令：
  leak    信息泄露路径批量探测            → 对应测试卡 E
  unauth  删凭证未授权访问批量探测         → 对应测试卡 A1
  idor    A/B 凭证资源 ID 越权批量探测     → 对应测试卡 A2/A3
  diff    任意两请求响应差异对比（辅助判据）

通用原则：
  1. 一律以「黄金标准」做对比，而非凭状态码臆断（降低误报）
  2. 默认低并发 + 可限速，避免触发 SRC 速率限制
  3. 输出仅含疑似项与判定理由，人工复验后才算命中
"""

import argparse
import concurrent.futures as cf
import json
import os
import random
import string
import sys
import time
from urllib.parse import urlparse, urlencode, parse_qsl, urlunparse

import requests
from difflib import SequenceMatcher

requests.packages.urllib3.disable_warnings()

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

AUTH_WORDS = [
    "未登录", "请先登录", "登录已失效", "请先登錄", "登錄",
    "unauthorized", "unauthorised", "not login", "please login",
    "login required", "invalid token", "token expired",
    "no permission", "forbidden", "access denied", "无权限", "权限不足",
    "sign in", "authentication failed", "session expired",
]


# ---------------- 基础工具 ----------------

def rand_str(n=12):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=n))


def similarity(a, b):
    if a is None or b is None:
        return 0.0
    return SequenceMatcher(None, a[:8000], b[:8000]).ratio()


def _unescape(t):
    """响应中常见 \\uXXXX 转义，还原后再做关键词匹配，否则会漏判鉴权墙"""
    if "\\u" in t:
        try:
            import codecs
            return codecs.decode(t, "unicode_escape")
        except Exception:
            return t
    return t


def looks_like_auth_wall(text):
    t = (text or "").lower()
    t2 = _unescape(t).lower()
    for cand in (t, t2):
        if any(w in cand for w in AUTH_WORDS):
            return True
    return False


def do_request(method, url, headers=None, body=None, timeout=10,
               allow_redirects=False, proxy=None):
    try:
        r = requests.request(
            method.upper(), url, headers=headers or {}, data=body,
            timeout=timeout, verify=False, allow_redirects=allow_redirects,
            proxies=({"http": proxy, "https": proxy} if proxy else None),
        )
        return {
            "ok": True,
            "status": r.status_code,
            "len": len(r.content),
            "text": r.text[:8000],
            "headers": dict(r.headers),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:200], "status": 0, "len": 0, "text": "", "headers": {}}


def parse_raw_request(raw, scheme=None):
    """解析 Burp 复制出的原始 HTTP 请求"""
    lines = raw.replace("\r\n", "\n").split("\n")
    method, path = None, None
    headers, i = {}, 0
    for idx, line in enumerate(lines):
        if not line.strip():
            i = idx
            break
        if idx == 0:
            parts = line.split()
            if len(parts) >= 2:
                method, path = parts[0], parts[1]
        elif ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip()] = v.strip()
    body = "\n".join(lines[i + 1:]).strip()
    host = headers.get("Host", "")
    if path.startswith("http://") or path.startswith("https://"):
        url = path
    else:
        if not scheme:
            scheme = "http" if host.split(":")[0] in ("127.0.0.1", "localhost") else "https"
        url = f"{scheme}://{host}{path}"
    return method or "GET", url, headers, body


def set_param(method, url, headers, body, name, value):
    """在 path/query/body(json或form)/header 中替换同名参数"""
    changed = []
    u = urlparse(url)

    # query
    if u.query:
        qs = parse_qsl(u.query, keep_blank_values=True)
        hit = False
        newqs = []
        for k, v in qs:
            if k == name:
                newqs.append((k, str(value)))
                hit = True
            else:
                newqs.append((k, v))
        if hit:
            u = u._replace(query=urlencode(newqs))
            changed.append("query")
    url = urlunparse(u)

    # header
    for k in list(headers.keys()):
        if k.lower() == name.lower():
            headers[k] = str(value)
            changed.append("header")

    # body json
    if body:
        try:
            obj = json.loads(body)
            if isinstance(obj, dict) and name in obj:
                obj[name] = value
                body = json.dumps(obj, ensure_ascii=False)
                changed.append("body-json")
            elif isinstance(obj, dict):
                # 递归一层
                for kk, vv in obj.items():
                    if isinstance(vv, dict) and name in vv:
                        vv[name] = value
                        body = json.dumps(obj, ensure_ascii=False)
                        changed.append("body-json-nested")
        except Exception:
            try:
                qs = parse_qsl(body, keep_blank_values=True)
                hit = False
                nq = []
                for k, v in qs:
                    if k == name:
                        nq.append((k, str(value)))
                        hit = True
                    else:
                        nq.append((k, v))
                if hit:
                    body = urlencode(nq)
                    changed.append("body-form")
            except Exception:
                pass

    # path：/api/order/{id} 或 /api/order/123
    if not changed and name.lower() in ("id", "pathid"):
        segs = u.path.rstrip("/").split("/")
        if segs:
            segs[-1] = str(value)
            u = u._replace(path="/".join(segs))
            url = urlunparse(u)
            changed.append("path")

    return url, headers, body, changed


# ---------------- 子命令 1：leak ----------------

LEAK_PATHS = [
    "/.git/config", "/.git/HEAD", "/.svn/entries", "/.DS_Store",
    "/.env", "/web.config", "/WEB-INF/web.xml",
    "/swagger-ui.html", "/swagger/index.html", "/api-docs", "/v2/api-docs", "/v3/api-docs",
    "/actuator", "/actuator/env", "/actuator/heapdump", "/actuator/metrics",
    "/env", "/metrics", "/health", "/info",
    "/druid/index.html", "/druid",
    "/www.zip", "/www.rar", "/wwwroot.zip", "/backup.zip", "/backup.sql", "/db.sql",
    "/console", "/admin", "/admin/login", "/manage", "/login",
    "/robots.txt", "/sitemap.xml", "/crossdomain.xml",
    "/phpinfo.php", "/test.php", "/info.php",
    "/jenkins", "/solr/admin/info/system",
    "/debug/default/view", "/_profiler",
]


def cmd_leak(args):
    base = args.url.rstrip("/")
    hdrs = {"User-Agent": UA}
    if args.cookie:
        hdrs["Cookie"] = args.cookie
    if args.header:
        for h in args.header:
            k, v = h.split(":", 1)
            hdrs[k.strip()] = v.strip()

    # 404 基线：排除"所有路径都返回 200 的站点"
    rnd = f"/{rand_str(16)}"
    base404 = do_request("GET", base + rnd, hdrs, timeout=args.timeout, proxy=args.proxy)
    print(f"[*] 404 基线: status={base404['status']} len={base404['len']}")

    results = []

    def probe(p):
        r = do_request("GET", base + p, hdrs, timeout=args.timeout, proxy=args.proxy)
        if not r["ok"]:
            return None
        sim = similarity(r["text"], base404["text"])
        if r["status"] == 200 and sim < args.sim and r["len"] > args.minlen:
            return {"path": p, "status": r["status"], "len": r["len"],
                    "sim_to_404": round(sim, 3), "preview": r["text"][:300]}
        return None

    with cf.ThreadPoolExecutor(max_workers=args.threads) as ex:
        for res in ex.map(probe, LEAK_PATHS):
            if res:
                results.append(res)
            time.sleep(args.delay)

    emit(results, args, title="信息泄露疑似清单", card="E 模块 / 手工复核")


# ---------------- 子命令 2：unauth ----------------

def cmd_unauth(args):
    raw = open(args.file, encoding="utf-8", errors="ignore").read()
    method, url, headers, body = parse_raw_request(raw, args.scheme)
    headers.setdefault("User-Agent", UA)

    # 黄金标准 A：带凭证
    gold = do_request(method, url, headers, body, args.timeout, proxy=args.proxy)
    print(f"[*] 带凭证基线: status={gold['status']} len={gold['len']}")

    # 变体 B：删凭证
    stripped = {k: v for k, v in headers.items()
                if k.lower() not in ("cookie", "authorization", "token", "x-token", "x-auth-token")}
    noauth = do_request(method, url, stripped, body, args.timeout, proxy=args.proxy)

    # 变体 C：空凭证
    empty = dict(stripped)
    empty["Cookie"] = ""
    emptyauth = do_request(method, url, empty, body, args.timeout, proxy=args.proxy)

    out = []
    for tag, r in (("删除凭证头", noauth), ("空 Cookie", emptyauth)):
        if not r["ok"]:
            continue
        sim = similarity(r["text"], gold["text"])
        authwall = looks_like_auth_wall(r["text"])
        reason = []
        if r["status"] == 200:
            reason.append("返回 200")
        if sim > args.sim:
            reason.append(f"与带凭证响应相似度 {sim:.2f}")
        if not authwall:
            reason.append("响应中未见登录/鉴权提示")
        if r["status"] in (401, 403):
            continue
        if reason:
            out.append({"变体": tag, "status": r["status"], "len": r["len"],
                        "sim_to_authed": round(sim, 3), "判定理由": "; ".join(reason),
                        "preview": r["text"][:400]})

    print(f"\n[带凭证] status={gold['status']} len={gold['len']}")
    print(f"[删凭证] status={noauth.get('status')} len={noauth.get('len')}")
    print(f"[空凭证] status={emptyauth.get('status')} len={emptyauth.get('len')}")
    emit(out, args, title="未授权访问疑似清单", card="A1 卡 / 人工用 B 账号复核")


# ---------------- 子命令 3：idor ----------------

def cmd_idor(args):
    with open(args.file, encoding="utf-8", errors="ignore") as f:
        raw = f.read()
    method, url, headers, body = parse_raw_request(raw, args.scheme)
    headers.setdefault("User-Agent", UA)

    hdrs_a = dict(headers)
    hdrs_b = dict(headers)
    if args.cookie_a:
        hdrs_a["Cookie"] = args.cookie_a
    if args.cookie_b:
        hdrs_b["Cookie"] = args.cookie_b
    if args.token_a:
        hdrs_a["Authorization"] = args.token_a
    if args.token_b:
        hdrs_b["Authorization"] = args.token_b

    ids_b = [l.strip() for l in open(args.ids, encoding="utf-8") if l.strip()]
    print(f"[*] A 凭证 + B 的资源 ID 共 {len(ids_b)} 个；参数名: {args.param}")

    out = []

    def test(bid):
        u1, h1, b1, ch = set_param(method, url, dict(hdrs_a), body, args.param, bid)
        if not ch:
            return {"id": bid, "错误": f"未在请求中找到参数 {args.param}"}
        ra = do_request(method, u1, h1, b1, args.timeout, proxy=args.proxy)

        u2, h2, b2, _ = set_param(method, url, dict(hdrs_b), body, args.param, bid)
        rb = do_request(method, u2, h2, b2, args.timeout, proxy=args.proxy)

        if not ra["ok"] or not rb["ok"]:
            return {"id": bid, "错误": "请求失败"}

        sim = similarity(ra["text"], rb["text"])
        if ra["status"] == 200 and sim > args.sim and not looks_like_auth_wall(ra["text"]):
            return {"id": bid, "status": ra["status"], "len": ra["len"],
                    "sim_to_owner": round(sim, 3), "替换位置": ",".join(ch),
                    "判定理由": f"A 凭证读取 B 资源，与 B 本人读取结果相似度 {sim:.2f}",
                    "preview": ra["text"][:400]}
        return {"id": bid, "status": ra["status"], "sim_to_owner": round(sim, 3),
                "判定理由": "未命中（响应与被访者本人不一致或需鉴权）"}

    with cf.ThreadPoolExecutor(max_workers=args.threads) as ex:
        for res in ex.map(test, ids_b):
            if res and "判定理由" in res and "未命中" not in res["判定理由"]:
                out.append(res)
            time.sleep(args.delay)

    emit(out, args, title="越权（IDOR）疑似清单", card="A2/A3 卡 / 人工确认数据归属")


# ---------------- 子命令 4：diff ----------------

def cmd_diff(args):
    raw = open(args.file, encoding="utf-8", errors="ignore").read()
    method, url, headers, body = parse_raw_request(raw, args.scheme)
    headers.setdefault("User-Agent", UA)
    h2 = dict(headers)
    for h in args.replace:
        k, v = h.split(":", 1)
        h2[k.strip()] = v.strip()
    r1 = do_request(method, url, headers, body, args.timeout, proxy=args.proxy)
    r2 = do_request(method, url, h2, body, args.timeout, proxy=args.proxy)
    print(f"[原始] status={r1['status']} len={r1['len']}")
    print(f"[变体] status={r2['status']} len={r2['len']}")
    print(f"[相似度] {similarity(r1['text'], r2['text']):.3f}")
    print("\n--- 原始响应预览 ---\n" + r1["text"][:600])
    print("\n--- 变体响应预览 ---\n" + r2["text"][:600])


# ---------------- 输出 ----------------

def emit(rows, args, title, card):
    print("\n" + "=" * 60)
    print(f" {title}（疑似 {len(rows)} 项）")
    print(f" 下一步：按 {card} 人工复验")
    print("=" * 60)
    if not rows:
        print(" 未发现疑似项 —— 记为 [~] 排除，请填写排除理由")
        return
    for r in rows:
        print("\n---")
        for k, v in r.items():
            if k == "preview":
                v = (str(v).replace("\n", " "))[:200] + " ..."
            print(f"  {k}: {v}")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
        print(f"\n[+] 已写入 {args.out}")


def main():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--proxy", help="代理，如 http://127.0.0.1:8080")
    common.add_argument("--timeout", type=float, default=10)
    common.add_argument("--threads", type=int, default=5)
    common.add_argument("--delay", type=float, default=0.2, help="每次请求间隔，避免触发限速")
    common.add_argument("--sim", type=float, default=0.85, help="相似度阈值")
    common.add_argument("--minlen", type=int, default=10, help="响应最小长度，过滤空响应")
    common.add_argument("--out", help="结果输出 JSON 路径")
    common.add_argument("--scheme", choices=["http", "https"], default=None,
                        help="强制协议，默认按 Host 判断（localhost 走 http）")

    p = argparse.ArgumentParser(description="SRC 自动化前置扫描器（仅产出疑似清单）")
    sub = p.add_subparsers(dest="cmd", required=True)

    s1 = sub.add_parser("leak", help="信息泄露路径探测", parents=[common])
    s1.add_argument("--url", required=True)
    s1.add_argument("--cookie")
    s1.add_argument("--header", action="append")
    s1.set_defaults(func=cmd_leak)

    s2 = sub.add_parser("unauth", help="删凭证未授权探测", parents=[common])
    s2.add_argument("--file", required=True, help="原始 HTTP 请求文件")
    s2.set_defaults(func=cmd_unauth)

    s3 = sub.add_parser("idor", help="A/B 凭证越权探测", parents=[common])
    s3.add_argument("--file", required=True)
    s3.add_argument("--param", required=True, help="要替换的参数名，如 orderId")
    s3.add_argument("--ids", required=True, help="B 账号资源 ID 列表文件")
    s3.add_argument("--cookie-a", help="A 账号 Cookie")
    s3.add_argument("--cookie-b", help="B 账号 Cookie")
    s3.add_argument("--token-a")
    s3.add_argument("--token-b")
    s3.set_defaults(func=cmd_idor)

    s4 = sub.add_parser("diff", help="两请求响应差异对比", parents=[common])
    s4.add_argument("--file", required=True)
    s4.add_argument("--replace", action="append", required=True, help="要替换的头，如 'Cookie: xxx'")
    s4.set_defaults(func=cmd_diff)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
