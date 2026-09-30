#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
src_rules.py —— 公开检测规则库挖掘引擎

核心认知：**规则库不是拿来跑扫描的，是拿来读的。**

一个 CVE 公告说"存在认证绕过"。
一个检测规则给你精确到字节的构造——端点、参数路径、密钥、编码格式、
脆弱/已修的响应判据、FOFA/Shodan 语法、是否在野利用（vkev）。

这是二手但密度极高的知识源：别人已经验证过的攻击构造，直接白送。

三个挖掘模式：
  cwe      按根因族检索 —— 跨协议、跨产品的同根因漏洞自动聚合
  vendor   同一厂商跨年 CVE 分布 —— 连续出洞 = 修复不彻底
  coord    提取单条规则的完整攻击坐标（端点/参数/载荷/判据/测绘语法）

外加：
  download 下载规则库（GitHub codeload 可达）
  patterns 输出「高频根因族」速查表
"""

import argparse
import json
import os
import re
import sys
import urllib.request
from collections import defaultdict, OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LIB = os.path.join(HERE, "oss", "nuclei-templates-main")

CWE_NAME = {
    "CWE-347": "加密签名验证不当（验证对象 ≠ 取值对象）",
    "CWE-287": "认证机制不当",
    "CWE-20": "输入校验不充分",
    "CWE-200": "信息泄露",
    "CWE-79": "XSS",
    "CWE-89": "SQL 注入",
    "CWE-94": "代码注入",
    "CWE-502": "不安全反序列化",
    "CWE-787": "越界写",
    "CWE-918": "SSRF",
    "CWE-22": "路径穿越",
    "CWE-306": "关键功能缺失认证",
    "CWE-862": "缺失授权",
    "CWE-639": "越权（对象级）",
    "CWE-88": "参数注入",
    "CWE-77": "命令注入",
    "CWE-78": "OS 命令注入",
    "CWE-416": "UAF",
    "CWE-121": "栈溢出",
    "CWE-1321": "原型污染",
}

# 高价值根因族：这些是「按根因泛化」时命中率最高的
PRIME_FAMILIES = [
    ("CWE-347", "签名验证与取值对象分离",
     "外推：任何「校验看到的对象」与「实际使用的对象」可能分离的位置——"
     "删节点、CDATA/注释包裹、命名空间变体、重复字段优先级、编码差异"),
    ("CWE-287", "认证机制不当",
     "外推：条件校验 vs 强制校验。代码写 if(sig){verify()} 而非 if(!sig){reject()}"),
    ("CWE-306", "关键功能缺失认证",
     "外推：同族扩展。一个端点没鉴权，同批代码写的端点大概率都没有"),
    ("CWE-639", "对象级越权",
     "外推：主资源校验了子资源没校验；列表接口 pageSize 调大拿全量"),
    ("CWE-502", "不安全反序列化",
     "外推：黑名单 gadget 的等价变形；同生态其他库同根因"),
]


def load_lib(lib):
    if not os.path.isdir(lib):
        return []
    out = []
    for root, _, files in os.walk(lib):
        for f in files:
            if f.endswith(".yaml") or f.endswith(".yml"):
                out.append(os.path.join(root, f))
    return out


def parse(path):
    """提取规则的元数据与攻击坐标"""
    try:
        s = open(path, encoding="utf-8", errors="ignore").read()
    except Exception:
        return None
    d = {"path": path, "file": os.path.basename(path)}

    def one(k):
        """单行取值；若遇到 YAML 块标量（| 或 >），拼接后续缩进行。

         nuclei 模板的 description 常写成：
             description: |
               AAA
               BBB
         只取首行会丢掉绝大部分内容。
        """
        m = re.search(r"^\s*%s:?\s*(.*)$" % re.escape(k), s, re.M)
        if not m:
            return None
        val = m.group(1).strip()
        if val in ("|", ">", "|-", ">-", "|+"):
            # 块标量：收集后续比当前行缩进更深的行
            base_indent = len(m.group(0)) - len(m.group(0).lstrip())
            lines = s[m.end():].split("\n")
            out = []
            for ln in lines:
                if not ln.strip():
                    out.append("")
                    continue
                ind = len(ln) - len(ln.lstrip())
                if ind <= base_indent:
                    break
                out.append(ln.strip())
            return " ".join(x for x in out if x).strip() or None
        return val or None

    for k in ("id", "name", "severity", "description", "impact",
              "remediation", "vendor", "product", "verified"):
        d[k] = one(k)
    for k in ("cvss-score", "epss-score", "epss-percentile", "cve-id",
              "cwe-id", "cvss-metrics"):
        d[k.replace("-", "_")] = one(k)

    d["tags"] = []
    m = re.search(r"^\s*tags:\s*(.+)$", s, re.M)
    if m:
        d["tags"] = [t.strip() for t in m.group(1).split(",") if t.strip()]

    # 测绘语法（直接给出资产定位能力）
    for k in ("fofa-query", "shodan-query", "google-query"):
        d[k.replace("-", "_")] = one(k)

    # 攻击坐标
    d["endpoints"] = sorted(set(re.findall(
        r"\{\{BaseURL\}\}([^\s`'\"]{1,80})", s)))[:12]
    d["paths"] = sorted(set(re.findall(
        r"^\s*-\s+((?:GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+"
        r"\{\{BaseURL\}\}[^\s]*)$", s, re.M)))[:12]
    d["params"] = sorted(set(re.findall(r"([a-zA-Z_][\w\.\[\]-]{2,30})\s*=", s)))[:20]
    # 硬编码密钥 / 常量（最值钱的坐标）
    d["consts"] = sorted(set(re.findall(
        r"\b(?:key|secret|iv|Key|IV|SECRET)[^\n]{0,10}[:=]\s*"
        r"[\"']?([0-9a-fA-F]{16,}|[A-Za-z0-9+/]{16,}={0,2})", s)))[:8]
    d["has_code_block"] = bool(re.search(r"^\s*code:\s*$", s, re.M))
    d["self_contained"] = bool(re.search(r"^self-contained:\s*true", s, re.M))
    return d


def cmd_download(a):
    url = ("https://codeload.github.com/projectdiscovery/"
           "nuclei-templates/tar.gz/refs/heads/main")
    os.makedirs(a.dir, exist_ok=True)
    dst = os.path.join(a.dir, "nuclei-templates.tar.gz")
    print(f"[*] 下载 {url}")
    try:
        urllib.request.urlretrieve(url, dst)
        print(f"[+] 已保存 {dst} ({os.path.getsize(dst)//1024} KB)")
        print(f"[*] 解压: tar xzf {dst} -C {a.dir}")
    except Exception as e:
        print(f"[!] 下载失败: {e}")
        return 1
    return 0


def cmd_cwe(a):
    files = load_lib(a.lib)
    if not files:
        print(f"[!] 规则库为空: {a.lib}")
        print(f"[*] 先跑: python3 src_rules.py download --dir {a.lib}")
        return 1
    print(f"[*] 扫描 {len(files)} 个规则文件\n")
    fam = defaultdict(list)
    for p in files:
        d = parse(p)
        if not d or not d.get("cwe_id"):
            continue
        fam[d["cwe_id"]].append(d)

    if a.cwe:
        fam = {k: v for k, v in fam.items() if k.upper() == a.cwe.upper()}
    rows = sorted(fam.items(), key=lambda x: -len(x[1]))

    print("=" * 74)
    print(" 根因族分布（按 CWE 聚合）")
    print("=" * 74)
    for cwe, items in rows[:a.top]:
        print(f"\n● {cwe}  {CWE_NAME.get(cwe, '')}   —— {len(items)} 例")
        sev = defaultdict(int)
        for it in items:
            sev[it.get("severity") or "?"] += 1
        print(f"   严重度: {dict(sev)}")
        for it in sorted(items, key=lambda x: -(float(x.get("epss_score") or 0)))[:5]:
            nm = (it.get("name") or it.get("id") or "?")[:56]
            print(f"   [{it.get('severity','?'):8}] {nm}")
            print(f"            CVE:{it.get('cve_id','-')}  "
                  f"CVSS:{it.get('cvss_score','-')}  "
                  f"EPSS:{it.get('epss_score','-')}  "
                  f"{it.get('vendor') or ''}/{it.get('product') or ''}")
    print("\n" + "=" * 74)
    print(" 用法提示")
    print("=" * 74)
    print("""
按 CWE 检索而不是按 CVE 检索——同根因的会自动聚到一起，
哪怕它们分属完全不同的协议和产品。

看三点：
  1. 同一 vendor 是否跨年重复出现 → 修复不彻底，必有第三次
  2. EPSS 是否在后出版本上升   → 补丁绕过往往比原洞更活跃
  3. 跨产品同根因              → 该根因是当前周期的高频模式

然后：python3 src_rules.py coord --cve <CVE>  拿完整攻击坐标
""")
    if a.out:
        json.dump({k: v for k, v in rows[:a.top]},
                  open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"\n[+] 已写入 {a.out}")
    return 0


def cmd_vendor(a):
    """同一厂商跨年 CVE 分布 —— 连续出洞 = 修复不彻底"""
    files = load_lib(a.lib)
    if not files:
        print(f"[!] 规则库为空: {a.lib}")
        return 1
    print(f"[*] 扫描 {len(files)} 个规则文件\n")
    byv = defaultdict(list)
    for p in files:
        d = parse(p)
        if not d or not d.get("vendor"):
            continue
        y = ""
        m = re.search(r"CVE-(\d{4})-", d.get("cve_id") or "")
        if m:
            y = m.group(1)
        elif "cve" in d.get("tags", []):
            m2 = re.search(r"(20\d{2})", p)
            y = m2.group(1) if m2 else "?"
        byv[d["vendor"].lower()].append({**d, "year": y})

    hits = []
    for v, items in byv.items():
        years = sorted({i["year"] for i in items if i["year"] and i["year"] != "?"})
        if len(years) >= 2:
            hits.append((v, years, items))
    hits.sort(key=lambda x: -len(x[1]))

    print("=" * 74)
    print(" 同一厂商跨年 CVE（修复不彻底信号）")
    print("=" * 74)
    if not hits:
        print("\n 无跨年重复的厂商。")
        return 0
    for v, years, items in hits[:a.top]:
        print(f"\n● {v}   年份: {', '.join(years)}   共 {len(items)} 例")
        for y in years:
            sub = [i for i in items if i["year"] == y]
            print(f"   ── {y}: {len(sub)} 例")
            for it in sorted(sub, key=lambda x: -(float(x.get("epss_score") or 0)))[:4]:
                print(f"      [{it.get('severity','?'):8}] "
                      f"{(it.get('name') or it.get('id') or '?')[:48]}")
                print(f"               CVE:{it.get('cve_id','-')}  "
                      f"CVSS:{it.get('cvss_score','-')}  "
                      f"EPSS:{it.get('epss_score','-')}  "
                      f"CWE:{it.get('cwe_id','-')}")
    print("\n" + "=" * 74)
    print(" 判定")
    print("=" * 74)
    print("""
同一组件跨年出洞，且 CWE 相同 → **修复是补手法，不是重构校验模型**。

这类必出第三次。外推优先级拉到最高：
  1. src_rules.py coord --cve <最新的那个>  拿完整构造
  2. 列出同类手法的全部等价变体
  3. 检查其他入口/协议是否同步修了

EPSS 若在较新 CVE 上更高 → 说明补丁绕过比原洞更活跃，
未打补丁的实例更集中，优先级上调。
""")
    return 0


def cmd_coord(a):
    """提取单条规则的完整攻击坐标"""
    files = load_lib(a.lib)
    if not files:
        print(f"[!] 规则库为空: {a.lib}")
        return 1
    target = None
    for p in files:
        if a.cve.lower() in os.path.basename(p).lower():
            target = p
            break
    if not target:
        for p in files:
            try:
                s = open(p, encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            if a.cve.lower() in s.lower():
                target = p
                break
    if not target:
        print(f"[!] 未找到 {a.cve}")
        return 1

    d = parse(target)
    print("=" * 74)
    print(f" 攻击坐标 · {d.get('cve_id') or d.get('id')}")
    print("=" * 74)
    print(f"\n名称    : {d.get('name')}")
    print(f"严重度  : {d.get('severity')}   CVSS:{d.get('cvss_score')}   "
          f"EPSS:{d.get('epss_score')} (分位 {d.get('epss_percentile')})")
    print(f"CWE     : {d.get('cwe_id')}  {CWE_NAME.get(d.get('cwe_id',''),'')}")
    print(f"厂商    : {d.get('vendor')} / {d.get('product')}")
    print(f"标签    : {', '.join(d.get('tags',[]))}")
    print(f"已验证  : {d.get('verified')}")
    if d.get("description"):
        print(f"\n描述:\n  {d['description'][:400]}")
    if d.get("impact"):
        print(f"\n影响:\n  {d['impact'][:300]}")

    print("\n" + "-" * 74)
    print(" 测绘语法（资产定位）")
    print("-" * 74)
    for k in ("fofa_query", "shodan_query", "google_query"):
        if d.get(k):
            print(f"  {k}: {d[k]}")

    print("\n" + "-" * 74)
    print(" 端点与参数")
    print("-" * 74)
    for e in (d.get("paths") or d.get("endpoints") or [])[:10]:
        print(f"  {e}")
    if d.get("params"):
        print(f"  参数: {', '.join(d['params'][:14])}")
    if d.get("consts"):
        print("\n" + "-" * 74)
        print(" ★ 硬编码常量（密钥/IV/种子）——最值钱的坐标")
        print("-" * 74)
        for c in d["consts"]:
            print(f"  {c}")

    print("\n" + "-" * 74)
    print(" 外推方向")
    print("-" * 74)
    cwe = d.get("cwe_id", "")
    for c, name, ext in PRIME_FAMILIES:
        if c == cwe:
            print(f"  [{c}] {name}")
            print(f"  {ext}")
            break
    else:
        print(f"  根因族 {cwe} 不在速查表内，按通用维度展开：")
        print("   同族 / 对称性 / 方法变换 / 入口一致性 / 等价变形")
    print(f"\n  完整规则: {target}")
    print("\n  下一步: python3 src_variant.py gen --cve <...> 生成变体假设")
    return 0


def cmd_patterns(a):
    print("""
高频根因族速查表（按根因泛化时优先级最高的几族）
""" + "=" * 74)
    for c, name, ext in PRIME_FAMILIES:
        print(f"\n● {c}  {name}")
        print(f"  {ext}")
    print("\n" + "=" * 74)
    print("""
用法：
  python3 src_rules.py cwe --cwe CWE-347     # 拉出该族全部案例
  python3 src_rules.py vendor                # 找跨年重复出洞的厂商
  python3 src_rules.py coord --cve CVE-2024-45409   # 拿完整攻击坐标

关键认知：
  按 CWE 检索，不按 CVE 检索 —— 同根因的会自动聚合，
  哪怕它们分属不同协议、不同产品、不同年份。
""")


def main():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--lib", default=DEFAULT_LIB, help="规则库目录")

    ap = argparse.ArgumentParser(description="公开检测规则库挖掘引擎")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("download", help="下载规则库")
    s.add_argument("--dir", default=os.path.join(HERE, "oss"))
    s.set_defaults(func=cmd_download)

    s = sub.add_parser("cwe", parents=[common], help="按根因族检索")
    s.add_argument("--cwe", help="限定某个 CWE，如 CWE-347")
    s.add_argument("--top", type=int, default=12)
    s.add_argument("--out")
    s.set_defaults(func=cmd_cwe)

    s = sub.add_parser("vendor", parents=[common], help="同厂商跨年分布")
    s.add_argument("--top", type=int, default=10)
    s.set_defaults(func=cmd_vendor)

    s = sub.add_parser("coord", parents=[common], help="提取攻击坐标")
    s.add_argument("--cve", required=True)
    s.set_defaults(func=cmd_coord)

    sub.add_parser("patterns", help="高频根因族速查表").set_defaults(func=cmd_patterns)

    a = ap.parse_args()
    sys.exit(a.func(a) or 0)


if __name__ == "__main__":
    main()
