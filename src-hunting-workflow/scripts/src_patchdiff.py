#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
src_patchdiff.py —— 补丁前后行为对比器（校验点定位器）

核心用途：回答「厂商到底在哪一道加了检查」。

原理：
  同一组探针请求，分别打在「修复前版本」和「修复后版本」上，
  比对响应差异。**差异点 = 校验点**。
  尤其是「修复版新增的拒绝」——那条拒绝消息本身就是漏洞位置的坐标。

这比读公告准得多：
  - 公告是「说法」，改动是「行为」
  - 两者对齐 → 精确定位
  - 两者不对齐 → 那道缝就是洞（例：Redis 8.6.4 的 patch guard omission）

子命令：
  run     对两版本跑同一组探针，输出差异
  guard   从差异中提取「新增的拒绝」（校验点指纹）
  demo    本地 mock 靶场跑通全流程
  signals 打印六类改动信号清单（闭源环境下逐项去核对）
"""

import argparse
import difflib
import json
import os
import sys
import time
from urllib.parse import urljoin

import requests

requests.packages.urllib3.disable_warnings()

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"

# 探针集：覆盖常见的「校验点」位置。可自行扩展。
DEFAULT_PROBES = [
    # (名称, 方法, 路径, 头, 体)
    ("根路径", "GET", "/", {}, None),
    ("列表接口", "GET", "/api/items", {}, None),
    ("详情接口-越界ID", "GET", "/api/items/99999999", {}, None),
    ("详情接口-负数ID", "GET", "/api/items/-1", {}, None),
    ("管理路径", "GET", "/admin", {}, None),
    ("管理API", "GET", "/api/admin/users", {}, None),
    ("Actuator", "GET", "/actuator/env", {}, None),
    ("Swagger", "GET", "/v2/api-docs", {}, None),
    ("未授权资源", "GET", "/api/orders", {}, None),
    ("路径穿越探针", "GET", "/api/file?name=..%2f..%2fetc%2fpasswd", {}, None),
    ("老版本前缀", "GET", "/v1/api/items", {}, None),
    ("方法变换-DELETE", "DELETE", "/api/items/1", {}, None),
    ("方法变换-PUT", "PUT", "/api/items/1", {}, None),
    ("内部头覆盖", "GET", "/api/items", {"X-Internal-Env": "canary-probe"}, None),
    ("内部头-租户", "GET", "/api/items", {"X-Tenant-Id": "canary-probe"}, None),
    ("重复头", "GET", "/api/items", {"X-Forwarded-Host": "canary.probe.test"}, None),
    ("TRACE方法", "TRACE", "/", {}, None),
    ("OPTIONS", "OPTIONS", "/api/items", {}, None),
]

# 判定为「拒绝」的信号词——出现在修复版而未出现在修复前版，即为新增校验
REJECT_WORDS = [
    "forbidden", "denied", "unauthorized", "not allowed", "rejected",
    "invalid", "illegal", "blocked", "禁止", "无权", "拒绝", "非法",
    "不允许", "校验失败", "must be", "required", "malformed",
    "doesn't exist", "does not exist", "unsupported", "not permitted",
]


def do(base, method, path, headers=None, body=None, timeout=10, proxy=None, delay=0.0):
    url = urljoin(base.rstrip("/") + "/", path.lstrip("/"))
    h = {"User-Agent": UA}
    h.update(headers or {})
    try:
        r = requests.request(method, url, headers=h, data=body, timeout=timeout,
                             verify=False, allow_redirects=False,
                             proxies=({"http": proxy, "https": proxy} if proxy else None))
        return {"ok": True, "status": r.status_code,
                "body": r.text[:4000], "len": len(r.content),
                "headers": dict(r.headers)}
    except Exception as e:
        return {"ok": False, "status": 0, "body": str(e)[:200], "len": 0, "headers": {}}
    finally:
        if delay:
            time.sleep(delay)


def is_reject(text):
    t = (text or "").lower()
    return any(w in t for w in REJECT_WORDS)


def sig(r):
    """响应的粗指纹：状态码 + 长度 + 首 200 字符"""
    if not r.get("ok"):
        return f"ERR:{r.get('body','')[:60]}"
    return f"{r['status']}|{r['len']}|{(r['body'] or '')[:200]}"


def diff_probes(before_base, after_base, probes, timeout=10, proxy=None, delay=0.1):
    rows = []
    for name, method, path, headers, body in probes:
        rb = do(before_base, method, path, headers, body, timeout, proxy)
        ra = do(after_base, method, path, headers, body, timeout, proxy)
        time.sleep(delay)

        same = sig(rb) == sig(ra)
        new_reject = (not is_reject(rb.get("body", ""))) and is_reject(ra.get("body", ""))
        lost_reject = is_reject(rb.get("body", "")) and (not is_reject(ra.get("body", "")))
        status_changed = rb.get("status") != ra.get("status")

        # 新增响应头（常是新增的安全头或新增的拒绝原因）
        new_headers = sorted(set(ra.get("headers", {})) - set(rb.get("headers", {})))
        gone_headers = sorted(set(rb.get("headers", {})) - set(ra.get("headers", {})))

        rows.append({
            "probe": name, "method": method, "path": path,
            "before": {"status": rb.get("status"), "len": rb.get("len"),
                       "preview": (rb.get("body") or "")[:160]},
            "after": {"status": ra.get("status"), "len": ra.get("len"),
                      "preview": (ra.get("body") or "")[:160]},
            "identical": same,
            "new_reject": new_reject,
            "lost_reject": lost_reject,
            "status_changed": status_changed,
            "new_headers": new_headers,
            "gone_headers": gone_headers,
        })
    return rows


def print_rows(rows, verbose=False):
    print("\n" + "=" * 72)
    print(" 补丁前后行为对比结果")
    print("=" * 72)
    changed = [r for r in rows if not r["identical"]]
    print(f" 共 {len(rows)} 个探针，{len(changed)} 个存在差异\n")

    for r in rows:
        if r["identical"] and not verbose:
            continue
        flag = []
        if r["new_reject"]:
            flag.append("★新增拒绝")
        if r["lost_reject"]:
            flag.append("⚠拒绝消失")
        if r["status_changed"]:
            flag.append("状态码变化")
        if r["new_headers"]:
            flag.append("新增响应头")
        if not flag and r["identical"]:
            flag.append("一致")

        print(f"--- {r['probe']}  [{r['method']} {r['path']}]")
        print(f"    标记: {', '.join(flag)}")
        print(f"    修复前: {r['before']['status']} len={r['before']['len']}")
        print(f"    修复后: {r['after']['status']} len={r['after']['len']}")
        if r["new_headers"]:
            print(f"    新增头: {', '.join(r['new_headers'][:6])}")
        if r["gone_headers"]:
            print(f"    消失头: {', '.join(r['gone_headers'][:6])}")
        print(f"    前: {r['before']['preview'][:110]}")
        print(f"    后: {r['after']['preview'][:110]}")
        print()

    guards = [r for r in rows if r["new_reject"]]
    if guards:
        print("=" * 72)
        print(f" ★ 定位到 {len(guards)} 处新增校验（这些就是补丁的检查点）")
        print("=" * 72)
        for r in guards:
            print(f"  [{r['method']} {r['path']}]  {r['probe']}")
            print(f"     修复后拒绝内容: {r['after']['preview'][:150]}")
        print("\n 提示：拒绝消息里的字段名/路径/条件，就是漏洞位置的直接坐标。")
        print("      把这些字段拿去做等价变形，就是绕过测试的第一步。")

    lost = [r for r in rows if r["lost_reject"]]
    if lost:
        print("\n" + "=" * 72)
        print(" ⚠ 修复后反而放开了的探针（可能是补丁缝隙或回退）")
        print("=" * 72)
        for r in lost:
            print(f"  [{r['method']} {r['path']}]  {r['probe']}")


def cmd_run(a):
    probes = DEFAULT_PROBES
    if a.probes:
        probes = []
        for line in open(a.probes, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 3:
                hdrs = {}
                if len(parts) >= 4 and parts[3]:
                    for kv in parts[3].split(";"):
                        if ":" in kv:
                            k, v = kv.split(":", 1)
                            hdrs[k.strip()] = v.strip()
                probes.append((parts[0], parts[1].upper(), parts[2], hdrs,
                               parts[4] if len(parts) >= 5 else None))
    print(f"[*] 修复前: {a.before}")
    print(f"[*] 修复后: {a.after}")
    print(f"[*] 探针数: {len(probes)}")
    rows = diff_probes(a.before, a.after, probes, a.timeout, a.proxy, a.delay)
    print_rows(rows, a.verbose)
    if a.out:
        json.dump(rows, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"\n[+] 已写入 {a.out}")


def cmd_guard(a):
    """从已保存的对比结果里提取新增校验的指纹"""
    if not a.out and not os.path.exists("patchdiff.json"):
        print("需要 --out 指定的结果文件")
        return 1
    f = a.out or "patchdiff.json"
    rows = json.load(open(f, encoding="utf-8"))
    guards = [r for r in rows if r.get("new_reject")]
    print(f"\n新增校验 {len(guards)} 处：\n")
    for r in guards:
        print(f"● {r['method']} {r['path']}  ({r['probe']})")
        b, af = r["before"]["preview"], r["after"]["preview"]
        print(f"  前: {b[:120]}")
        print(f"  后: {af[:120]}")
        # 提取拒绝消息里可能是字段名的 token
        import re
        toks = set(re.findall(r"[A-Za-z_][A-Za-z0-9_\-\.]{3,30}", af))
        stop = {"the", "and", "for", "not", "this", "that", "with", "must",
                "invalid", "error", "request", "field", "value", "http"}
        cand = [t for t in toks if t.lower() not in stop][:12]
        if cand:
            print(f"  候选字段/路径 token: {', '.join(cand)}")
        print()
    return 0


SIGNALS = """
六类改动信号 —— 闭源环境下逐项核对（公告是说法，这些是行为）

1. 版本串与构建号
   修复版本号、SMR/补丁级别、内部 build 号。
   例：Chrome 151.0.7922.109、OMSA 11.1.0.2、DualDAR 2026-09-01、
       GitLab 18.11.11/19.0.8/19.1.6/19.2.4、Langflow 1.9.0、Exim 4.99.3
   → 闭源没有源码可 diff，版本边界是唯一坐标。必须精确到具体版本串，
     不能只记「已升级」。

2. API 签名与参数变化
   handler 签名、参数增删、必填项变化。
   例：Langflow 修复方式是从 handler 签名去掉 data 参数
       → 打过补丁的版本直接返回 422（FastAPI 校验层拒绝）
   → 「422 vs 404/200/5xx」就是最好的版本指纹，非破坏性。

3. 新增的拒绝消息 / 错误码
   修复版多出来的 "xxx is required"、"invalid xxx"、"not permitted"。
   → 这条消息本身就是漏洞位置的坐标：它点名了字段、路径或条件。
   → 拿到之后立刻做等价变形，就是绕过测试的第一步。

4. 默认值变更
   出厂默认由「开」变「关」、由「允许」变「拒绝」。
   例：阿里云 ACK 托管节点池 management.auto_vul_fix 与 auto_repair
       默认值统一变更为 false（2025-08-31 起）
   → 默认值变更 = 厂商承认原来的默认值不安全。原默认值就是攻击面。

5. 依赖项版本提升
   第三方库版本跳跃、SDK 升级要求。
   例：Adobe 要求升级 C2PA SDK（c2pa-web ≤0.7.1 / c2pa ≤0.80.1 → 0.8.3/0.85.1）
   → 依赖升级把根因锁到了具体解析库，可顺藤摸瓜看该库的其他 CVE。

6. 文档与配置项的新增/删除
   新增的配置项（如 Playwright MCP 的 allowedHosts）、
   文档中被删掉的说明、新增的安全公告页。
   → 新增配置项 = 原来缺的那道检查。配置项名字直接告诉你检查的是什么。

核对纪律：
  - 公告说的 vs 实际改的，逐条对齐
  - 对齐 → 精确定位，确认修复
  - 不对齐 → 记录为「缝隙」，这是最高价值的产出
  - 例证：Redis 8.6.4 release notes 声称通过 PR #15081 修复，
    但审计发现该 duplicate-ownership check 实际只存在于 8.6.5，
    8.6.4 的源码里没有 → 整个 8.6.4 的用户以为自己安全，实际没有。
"""


def cmd_signals(a):
    print(SIGNALS)


def cmd_demo(a):
    print("[*] 本 Demo 需要本地起两个 mock 服务模拟修复前/后版本")
    print("[*] 启动方式：")
    print("    python3 mock_patchdiff.py        # 会同时起 :8901(前) 和 :8902(后)")
    print("    python3 src_patchdiff.py run --before http://127.0.0.1:8901 "
          "--after http://127.0.0.1:8902")
    print("\n[*] 若已启动，直接尝试连接...\n")
    try:
        rows = diff_probes("http://127.0.0.1:8901", "http://127.0.0.1:8902",
                           DEFAULT_PROBES, timeout=3, delay=0.02)
        print_rows(rows)
    except Exception as e:
        print(f"[!] 未连接成功: {e}")
        print("[*] 先运行 mock_patchdiff.py")


def main():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--timeout", type=float, default=10)
    common.add_argument("--delay", type=float, default=0.1, help="每探针间隔，避免触发限速")
    common.add_argument("--proxy")
    common.add_argument("--out")

    ap = argparse.ArgumentParser(description="补丁前后行为对比器：用响应差异定位校验点")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("run", parents=[common], help="对两版本跑同一组探针")
    s.add_argument("--before", required=True, help="修复前版本 base URL")
    s.add_argument("--after", required=True, help="修复后版本 base URL")
    s.add_argument("--probes", help="自定义探针文件，格式: 名称|方法|路径|头(k:v;k:v)|体")
    s.add_argument("--verbose", action="store_true", help="也打印一致的探针")
    s.set_defaults(func=cmd_run)

    sub.add_parser("guard", parents=[common], help="从结果中提取新增校验指纹").set_defaults(func=cmd_guard)
    sub.add_parser("signals", parents=[common], help="六类改动信号清单").set_defaults(func=cmd_signals)
    sub.add_parser("demo", parents=[common], help="本地 mock 演示").set_defaults(func=cmd_demo)

    a = ap.parse_args()
    rc = a.func(a)
    sys.exit(rc or 0)


if __name__ == "__main__":
    main()
