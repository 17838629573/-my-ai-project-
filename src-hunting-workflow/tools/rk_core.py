#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rk_core.py —— 侦察工具箱内核

设计原则（本项目实战教训硬化）：
1. 纪律代码化：只允许 GET/HEAD/OPTIONS，POST/PUT/DELETE 在代码层直接拒绝，
   不留"AI 自觉"的空间。
2. 判据外置：响应分类不靠人眼看状态码，靠 baseline.json 里 md5/长度对照。
3. 全量落盘：每次请求都存 header+body+指纹，供后续零请求回溯。
"""
import os, sys, json, time, hashlib, random, string, re
import urllib.parse
import requests

# ============ 硬纪律：只允许安全方法 ============
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

class UnsafeMethod(Exception):
    pass

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def rand_str(n=12):
    return "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(n))


def md5s(b: bytes) -> str:
    return hashlib.md5(b).hexdigest()


def fp(resp) -> dict:
    """把一次响应压成可比对指纹。"""
    body = resp.content or b""
    h = {k.lower(): v for k, v in resp.headers.items()}
    try:
        head = body[:400].decode("utf-8", "replace")
    except Exception:
        head = ""
    return {
        "status": resp.status_code,
        "ct": (h.get("content-type") or "").split(";")[0].strip(),
        "cl": int(h.get("content-length") or len(body)),
        "real_len": len(body),
        "md5": md5s(body),
        "head": head,
        "server": h.get("server", ""),
        "location": h.get("location", ""),
        "x_power": h.get("x-powered-by", ""),
        "envoy": "x-envoy-upstream-service-time" in h,
        "headers": h,
    }


def safe_request(url, method="GET", timeout=12, allow_redirects=False,
                 headers=None, verify=False, delay=0.0, extra_headers=None):
    """唯一出口。非安全方法直接抛异常，永不发包。"""
    method = method.upper()
    if method not in SAFE_METHODS:
        raise UnsafeMethod(f"拒绝执行 {method}：本工具箱只允许 {sorted(SAFE_METHODS)}")
    if delay:
        time.sleep(delay)
    h = {"User-Agent": UA, "Accept": "*/*"}
    if extra_headers:
        h.update(extra_headers)
    if headers:
        h.update(headers)
    try:
        r = requests.request(method, url, headers=h, timeout=timeout,
                             allow_redirects=allow_redirects, verify=verify)
        return r
    except Exception as e:
        return {"__error__": str(e)}


def observe(url, **kw):
    """发一次安全请求并返回 (指纹, 原始响应) 。错误返回 (None, err)。"""
    r = safe_request(url, **kw)
    if isinstance(r, dict):
        return None, r["__error__"]
    return fp(r), r


# ============ 基线比对 ============
def load_baseline(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def match_layer(f, base):
    """把指纹对照基线，返回层名。命中 md5 最优先，其次长度，最后状态码。"""
    if not base:
        return "?"
    for layer, sig in base.items():
        if not isinstance(sig, dict):
            continue
        if sig.get("md5") and f.get("md5") == sig["md5"]:
            return layer
    for layer, sig in base.items():
        if not isinstance(sig, dict):
            continue
        if sig.get("cl") is not None and f.get("cl") == sig["cl"]:
            return f"{layer}?"
    return "NEW"


# ============ 落盘 ============
def save_evidence(outdir, tag, f, resp=None):
    os.makedirs(outdir, exist_ok=True)
    p = os.path.join(outdir, tag)
    if resp is not None:
        with open(p + ".h", "w", encoding="utf-8") as fh:
            fh.write(f"STATUS {resp.status_code}\n")
            for k, v in resp.headers.items():
                fh.write(f"{k}: {v}\n")
        with open(p + ".b", "wb") as fb:
            fb.write(resp.content or b"")
    with open(p + ".json", "w", encoding="utf-8") as fj:
        json.dump(f, fj, ensure_ascii=False, indent=2)
    return p


def host_of(url):
    return urllib.parse.urlsplit(url).netloc


def check_host(url, allowed):
    """域名白名单。allowed 为空则不限制。"""
    if not allowed:
        return True
    return host_of(url) in allowed
