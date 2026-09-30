#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
src_intel.py —— SRC 漏洞情报聚合与优先级排序器

定位：把"最新披露的漏洞情报"变成"我今天该测什么"的优先队列。
解决两个问题：
  1. 源头太多、噪音太大 —— 自动按你的技术栈过滤
  2. 情报太多、不知先打哪个 —— 自动打分排序

设计原则：离线优先。
  在线拉取在你本机跑（沙盒/内网环境常无外网）；
  离线模式下，把各平台导出的 JSON / 手工整理的条目喂进来即可完成打分排序。

子命令：
  fetch   在线拉取（需外网，可选源见 SOURCES）
  load    导入本地 JSON 文件（平台导出 / 手工整理）
  rank    打分排序，输出优先队列
  demo    用内置样本跑通全流程（验证打分逻辑，无需网络）
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

# ---------------- 配置区：改成你自己的技术栈 ----------------

DEFAULT_PROFILE = {
    "stack": [
        # 你常遇到的组件，命中即加分。改成你自己的。
        "spring", "shiro", "fastjson", "jackson", "log4j", "struts",
        "thinkphp", "laravel", "django", "flask", "express", "nginx",
        "tomcat", "jenkins", "gitlab", "redis", "elasticsearch",
        "weblogic", "jboss", "solr", "nacos", "apollo", "xxl-job",
    ],
    "lang": ["java", "php", "python", "node", "go"],
    "vuln_pref": [
        # 你想要的类型，命中即加分
        "rce", "代码执行", "远程代码执行",
        "未授权", "unauth", "鉴权绕过", "auth bypass",
        "idor", "越权",
        "ssrf", "sql注入", "sqli", "反序列化", "deserial",
        "文件上传", "路径穿越", "path traversal", "任意文件读",
    ],
    # 你不想要的（DoS 类在很多 SRC 不算分或评级低）
    "vuln_avoid": ["dos", "拒绝服务", "denial of service"],
}

# 打分权重
W = {
    "stack_hit": 30,        # 命中你的技术栈
    "lang_hit": 10,         # 命中你的语言生态
    "pref_hit": 25,         # 命中你想要的漏洞类型
    "avoid_hit": -40,       # 命中你不想做的类型
    "kev": 50,              # 已被在野利用（CISA KEV）→ 说明真能打
    "poc_public": 20,       # 有公开 PoC → 可直接复现
    "no_poc": 15,           # 无 PoC → 说明补丁对比/自写 PoC 的空间（竞争少）
    "incomplete_fix": 60,   # 修复不完整 / 补丁被绕过 → 极可能是新洞
    "silent_patch": 25,     # 静默安全补丁 → 1-day 富矿
    "critical": 25, "high": 15, "moderate": 0, "low": -10,
    "fresh_7d": 20,         # 7 天内
    "fresh_30d": 10,        # 30 天内
    "old": -15,             # 一年以上（已被大量挖过）
}

SOURCES = {
    "github_advisory": "https://github.com/advisories  (可按 ecosystem 过滤 npm/pip/Maven/Go)",
    "nvd_api": "https://services.nvd.nist.gov/rest/json/cves/2.0?keywordSearch=",
    "cisa_kev": "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json",
    "cnnvd": "https://www.cnnvd.org.cn/  (国内权威，中文，含通报)",
    "cnvd": "https://www.cnvd.org.cn/",
    "cncert": "https://www.cert.org.cn/",
    "oss_security": "https://www.openwall.com/lists/oss-security/  (邮件列表，一手披露)",
    "fulldisclosure": "https://seclists.org/fulldisclosure/",
    "exploitdb": "https://www.exploit-db.com/",
    "freebuf": "https://www.freebuf.com/",
    "anquanke": "https://www.anquanke.com/",
    "xz": "https://xz.aliyun.com/  (先知社区)",
    "butian": "https://forum.butian.net/  (补天社区)",
    "t00ls": "https://www.t00ls.net/  (邀请制)",
    "thehackernews": "https://thehackernews.com/",
    "rapid7": "https://www.rapid7.com/blog/",
    "msrc": "https://msrc.microsoft.com/update-guide",
    "oracle_cspu": "https://www.oracle.com/security-alerts/",
    "red_hat": "https://access.redhat.com/security/cve/",
}


# ---------------- 打分引擎 ----------------

def _norm(s):
    return (s or "").lower()


def days_ago(datestr):
    if not datestr:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%SZ", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"):
        try:
            d = datetime.strptime(datestr[:len(fmt) + 2].strip(), fmt)
            d = d.replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - d).days
        except Exception:
            continue
    return None


def score_item(item, profile):
    """返回 (分数, 命中理由列表)"""
    text = _norm(
        " ".join(str(item.get(k, "")) for k in
                 ("title", "summary", "description", "component", "cve", "id", "tags"))
    )
    score = 0
    reasons = []

    for s in profile.get("stack", []):
        if _norm(s) in text:
            score += W["stack_hit"]
            reasons.append(f"技术栈命中:{s}")
            break

    for s in profile.get("lang", []):
        if _norm(s) in text:
            score += W["lang_hit"]
            reasons.append(f"语言生态命中:{s}")
            break

    for s in profile.get("vuln_pref", []):
        if _norm(s) in text:
            score += W["pref_hit"]
            reasons.append(f"类型命中:{s}")
            break

    for s in profile.get("vuln_avoid", []):
        if _norm(s) in text:
            score += W["avoid_hit"]
            reasons.append(f"低价值类型:{s}")
            break

    if item.get("kev") or "known exploited" in text:
        score += W["kev"]
        reasons.append("已在野利用(KEV)")

    if item.get("poc_public"):
        score += W["poc_public"]
        reasons.append("有公开PoC→可直接复现")
    elif item.get("poc_public") is False:
        score += W["no_poc"]
        reasons.append("无公开PoC→补丁对比空间大")

    # 修复不完整 / 补丁绕过 —— 最高价值信号
    pat_incomplete = ["incomplete fix", "不完整", "bypass", "绕过", "regression",
                      "still present", "partially", "insufficient"]
    if any(p in text for p in pat_incomplete):
        score += W["incomplete_fix"]
        reasons.append("★修复不完整/可绕过→极可能是新洞")

    # 静默安全补丁
    pat_silent = ["silent", "静默", "improve buffer", "fix edge case",
                  "refactor", "hardening", "security fix"]
    if any(p in text for p in pat_silent):
        score += W["silent_patch"]
        reasons.append("疑似静默安全补丁→1-day富矿")

    sev = _norm(item.get("severity", ""))
    for k in ("critical", "high", "moderate", "low"):
        if k in sev:
            score += W[k]
            if W[k]:
                reasons.append(f"危害:{k}")

    d = days_ago(item.get("published") or item.get("date"))
    if d is not None:
        if d <= 7:
            score += W["fresh_7d"]
            reasons.append(f"新({d}天内)")
        elif d <= 30:
            score += W["fresh_30d"]
            reasons.append(f"较新({d}天)")
        elif d > 365:
            score += W["old"]
            reasons.append(f"老洞({d}天)→已被大量挖过")

    return score, reasons


def rank_items(items, profile, topn=15, minscore=0):
    scored = []
    for it in items:
        s, r = score_item(it, profile)
        if s >= minscore:
            scored.append((s, r, it))
    scored.sort(key=lambda x: -x[0])
    return scored[:topn]


def print_queue(scored):
    print("\n" + "=" * 68)
    print(" 今日优先队列（分数高的先打）")
    print("=" * 68)
    if not scored:
        print(" 无符合条目。放宽 --minscore 或调整 profile 的 stack/vuln_pref。")
        return
    for i, (s, r, it) in enumerate(scored, 1):
        title = it.get("title") or it.get("summary") or it.get("cve") or "(无标题)"
        print(f"\n[{i}] {s} 分  {title[:70]}")
        print(f"     组件: {it.get('component', '-')}  "
              f"危害: {it.get('severity', '-')}  时间: {it.get('published', '-')}")
        print(f"     理由: {'; '.join(r[:4])}")
        if it.get("url"):
            print(f"     链接: {it['url']}")


# ---------------- 子命令 ----------------

DEMO_ITEMS = [
    {"cve": "CVE-2026-77310", "component": "jackson-databind",
     "title": "Incomplete fix for CVE-2026-54514: eager DNS resolution (SSRF) still present",
     "severity": "Moderate", "published": "2026-09-28", "poc_public": False,
     "url": "https://github.com/advisories"},
    {"cve": "CVE-2026-49268", "component": "shiro-core",
     "title": "Apache Shiro: LDAP DN Injection in DefaultLdapRealm",
     "severity": "High", "published": "2026-06-17", "poc_public": False,
     "url": "https://github.com/advisories"},
    {"cve": "CVE-2026-85706", "component": "gitlab",
     "title": "Critical GitLab Path Traversal Exploited in the Wild",
     "severity": "Critical", "published": "2026-09-20", "poc_public": True,
     "kev": True, "url": "https://www.rapid7.com/blog/"},
    {"cve": "CVE-2026-88932", "component": "multer",
     "title": "multer vulnerable to Denial of Service via orphaned disk writes",
     "severity": "Moderate", "published": "2026-09-28", "poc_public": False,
     "url": "https://github.com/advisories"},
    {"cve": "CVE-2021-44228", "component": "log4j",
     "title": "Log4Shell remote code execution",
     "severity": "Critical", "published": "2021-12-10", "poc_public": True,
     "url": "https://nvd.nist.gov"},
    {"cve": "CVE-2026-3514", "component": "prefect",
     "title": "Authentication Middleware Bypass when URL paths appended with health or ready",
     "severity": "High", "published": "2026-06-02", "poc_public": False,
     "url": "https://github.com/advisories"},
    {"cve": "CVE-2026-101913", "component": "ip-address",
     "title": "Address6.isLinkLocal() allowing SSRF and trust-boundary bypass",
     "severity": "Moderate", "published": "2026-09-28", "poc_public": False,
     "url": "https://github.com/advisories"},
    {"cve": "CVE-2026-76844", "component": "webpack-dev-middleware",
     "title": "Path Traversal via non-slash-terminated publicPath",
     "severity": "High", "published": "2026-09-29", "poc_public": False,
     "url": "https://github.com/advisories"},
]


def cmd_demo(args):
    profile = load_profile(args.profile)
    print("[*] 用内置样本验证打分逻辑（无需网络）")
    print(f"[*] 技术栈: {', '.join(profile['stack'][:8])} ...")
    scored = rank_items(DEMO_ITEMS, profile, topn=args.top, minscore=args.minscore)
    print_queue(scored)
    print("\n[*] 预期：修复不完整的 jackson-databind、在野利用的 GitLab、")
    print("    鉴权绕过的 prefect 排前面；DoS 类和 2021 年的 log4j 被压低。")


def cmd_load(args):
    profile = load_profile(args.profile)
    with open(args.file, encoding="utf-8") as f:
        data = json.load(f)
    items = data if isinstance(data, list) else data.get("items", data.get("vulnerabilities", []))
    print(f"[*] 载入 {len(items)} 条")
    scored = rank_items(items, profile, topn=args.top, minscore=args.minscore)
    print_queue(scored)
    if args.out:
        dump = [{"score": s, "reasons": r, "item": it} for s, r, it in scored]
        json.dump(dump, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"\n[+] 已写入 {args.out}")


def cmd_fetch(args):
    print("[!] 在线拉取依赖外网。若当前环境不可达，请改用 load 导入，")
    print("    或在你本机运行本命令后把结果存成 JSON。\n")
    print("可用情报源（按一手程度排序）：\n")
    for k, v in SOURCES.items():
        print(f"  {k:18s} {v}")
    print("\n拉取后统一成如下格式存 JSON，再用 load 打分：")
    print(json.dumps([{
        "cve": "CVE-2026-XXXXX", "component": "组件名",
        "title": "标题", "severity": "Critical/High/Moderate/Low",
        "published": "2026-09-28", "poc_public": True/False,
        "kev": True/False, "url": "链接"
    }], ensure_ascii=False, indent=2))


def cmd_rank(args):
    cmd_load(args)


def load_profile(path):
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "intel_profile.json")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return DEFAULT_PROFILE


def main():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--profile", help="技术栈 profile JSON 路径")
    common.add_argument("--top", type=int, default=15)
    common.add_argument("--minscore", type=int, default=0)
    common.add_argument("--out", help="输出 JSON 路径")

    ap = argparse.ArgumentParser(description="SRC 漏洞情报聚合与优先级排序器")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("demo", parents=[common], help="内置样本跑通全流程").set_defaults(func=cmd_demo)
    s2 = sub.add_parser("load", parents=[common], help="导入本地 JSON 打分排序")
    s2.add_argument("--file", required=True)
    s2.set_defaults(func=cmd_load)
    sub.add_parser("fetch", parents=[common], help="显示可用情报源与数据格式").set_defaults(func=cmd_fetch)
    s3 = sub.add_parser("rank", parents=[common], help="同 load")
    s3.add_argument("--file", required=True)
    s3.set_defaults(func=cmd_rank)
    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
