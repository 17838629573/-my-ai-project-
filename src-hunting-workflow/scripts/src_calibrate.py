#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
src_calibrate.py —— 工作流反向校准器

用途：用「最近三个月公开的真实漏洞」反过来检验工作流本身。

核心逻辑：
  把这批漏洞逐个喂给工作流，问一句：
    「我的工作流，在哪一步能发现它？」
  - 能定位到某一步 → 该步骤记一次命中
  - 定位不到 → **缺口**，必须补进工作流

这解决的是工作流最大的隐患：
  清单是我们自己写的，它只能覆盖「我们已经想到」的攻击面。
  用真实漏洞反向校准，才能发现「我们没想到」的部分。

同时做第二件事：
  校准完的这批漏洞，直接进泛化引擎，产出外推假设待测队列。
  **校准与情报收集合并为一步。**

用法：
  python3 src_calibrate.py demo                    # 内置 15 个样本跑通
  python3 src_calibrate.py load --file vulns.json  # 载入自己收集的最近三月漏洞
  python3 src_calibrate.py steps                   # 查看工作流步骤定义
"""

import argparse
import json
import os
import sys
from collections import OrderedDict, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))

# ==================== 工作流步骤定义 ====================
# 每一步定义：它能发现什么（可判定的匹配信号）

STEPS = OrderedDict()


def step(key, name, detects, script):
    """detects: 漏洞满足什么特征时，这一步能发现它"""
    STEPS[key] = {"name": name, "detects": detects, "script": script}


step("P2", "资产测绘与暴露面",
     ["泄露", "暴露", "备份", "swagger", "actuator", "目录", "未授权访问",
      "默认口令", "配置不当", "信息泄露", "遍历可枚举"],
     "run.py p0 / src_scout.py leak")

step("P3", "越权与未授权（含入口一致性）",
     ["越权", "未授权", "idor", "authz", "对象级", "水平权限", "垂直权限",
      "任意用户", "任意查看", "遍历ID", "批量接口", "缺失鉴权"],
     "run.py p1 / src_scout.py idor")

step("P4", "业务逻辑（并发、状态机、金额）",
     ["逻辑", "并发", "竞态", "超领", "超卖", "金额", "支付", "优惠券",
      "库存", "状态机", "步骤跳过", "重放", "复用"],
     "手工 + 并发脚本")

step("P5", "注入与服务端（含语义复活化）",
     ["注入", "sqli", "命令执行", "rce", "反序列化", "ssti", "模板",
      "表达式", "escape后被还原", "文件上传", "解析", "xxe", "溢出"],
     "手工 + 变形字典")

step("P6", "补丁对齐（厂商改动法）",
     ["修复不完整", "绕过补丁", "静默修复", "bypass", "incomplete",
      "版本边界", "分支遗漏", "声称已修实际未修", "回归"],
     "src_patchdiff.py run")

step("P7", "信任域与内部元数据",
     ["内部头", "x-internal", "x-forwarded", "host", "sni", "元数据",
      "覆盖", "伪头", "重复字段", "协议字段", "信任边界"],
     "手工 + 头变异")

step("P9", "根因族关联（规则库/跨年复发）",
     ["签名", "签名验证", "cwe-347", "bypass", "绕过补丁", "不完整",
      "跨年", "复发", "同一组件", "历史cve", "epss", "检测规则",
      "saml", "jwt", "hmac", "digest"],
     "src_rules.py cwe / vendor / coord")

step("P10", "框架自身攻击面（框架≠应用）",
     ["框架", "framework", "sdk", "中间件", "协议设计", "specification",
      "设计缺陷", "by design", "厂商拒绝修复", "架构缺陷",
      "langchain", "langgraph", "langflow", "mcp", "autogen", "crewai",
      "traefik", "nextcloud", "gogs", "n8n", "kestra"],
     "src_rules.py cwe / vendor + 框架 CVE 池")

step("P11", "多 Agent 信任边界（confused deputy / 权限继承）",
     ["多agent", "multi-agent", "委托", "delegation", "confused deputy",
      "权限继承", "信任传递", "内部流量", "inter-agent", "a2a",
      "沙箱逃逸", "sandbox escape", "权限提升", "scope"],
     "头变异 / 委托链测试")

step("P12", "协议层根因映射（自下而上）",
     ["协议", "protocol", "nat", "dns", "bgp", "tls", "http语义",
      "rfc", "specification", "natjack", "rebirthday", "ecs",
      "conntrack", "声明长度", "caplen", "rrsig"],
     "src_rules.py cwe + 协议 CVE → 应用层映射")

step("P13", "运行时根因映射（语言/标准库）",
     ["cpython", "openjdk", "jvm", "v8", "runtime", "标准库",
      "tarfile", "zipfile", "pickle", "eval", "反序列化",
      "原型污染", "protobuf", "dataview", "正则回溯",
      "o(n", "复杂度", "栈溢出", "递归"],
     "src_stack.py lang --lang python / runtime")

step("P8", "AI / Agent 决策边界",
     ["提示注入", "prompt", "agent", "工具调用", "llm", "rag",
      "mcp", "语音", "asr", "模型", "指令"],
     "手工 + 多载体测试")


# ==================== 校准 ====================

def match_steps(v):
    """判断每个漏洞能被哪些步骤发现"""
    blob = json.dumps(v, ensure_ascii=False).lower()
    hits = []
    for key, s in STEPS.items():
        for kw in s["detects"]:
            if kw.lower() in blob:
                hits.append(key)
                break
    return hits


def calibrate(vulns, topn=12):
    rows = []
    uncovered = []
    for v in vulns:
        hits = match_steps(v)
        if not hits:
            uncovered.append(v)
        rows.append({
            "title": v.get("title", "(无标题)"),
            "cve": v.get("cve", "-"),
            "date": v.get("date", "-"),
            "steps": hits,
            "covered": bool(hits),
        })
    return rows, uncovered


def contribution(rows):
    c = defaultdict(int)
    for r in rows:
        for s in r["steps"]:
            c[s] += 1
    return c


def print_report(rows, uncovered, vulns):
    n = len(vulns)
    cov = sum(1 for r in rows if r["covered"])
    print("\n" + "=" * 74)
    print(" 工作流反向校准报告")
    print("=" * 74)
    print(f"\n 样本数: {n}   已覆盖: {cov}   覆盖率: {cov*100//max(n,1)}%")

    print("\n── 各步骤命中贡献 ──\n")
    c = contribution(rows)
    for k, s in STEPS.items():
        cnt = c.get(k, 0)
        bar = "█" * cnt
        print(f"  {k}  {s['name']:<22} {cnt:>2}/{n}  {bar}")

    print("\n── 逐条覆盖情况 ──\n")
    for r in rows:
        mark = "✓" if r["covered"] else "✗ 缺口"
        print(f"  [{mark}] {r['title'][:56]}")
        if r["steps"]:
            print(f"         → {' / '.join(r['steps'])}")
        print()

    if uncovered:
        print("=" * 74)
        print(f" ★ 工作流缺口：{len(uncovered)} 个漏洞无法被任何步骤发现")
        print("=" * 74)
        print("\n 这些是工作流真正的盲区——不是没测到，是**压根没想到**。\n")
        for v in uncovered:
            print(f"  ● {v.get('title', '(无标题)')}")
            for f in ("cve", "date", "vuln_class", "root_cause", "trigger"):
                if v.get(f):
                    print(f"      {f}: {v[f]}")
            print()
        print(" 处理：把它们的根因抽象成新步骤，或加进现有步骤的检测信号。")
        print("       补完再跑一次校准，覆盖率应上升。")
    else:
        print("\n 本批样本无缺口。注意：这不代表工作流完备，只代表它能覆盖这批样本。")

    print("\n" + "=" * 74)
    print(" 下一步：把这批漏洞送进泛化引擎，产出待测假设")
    print("   python3 src_variant.py gen --file <本批文件> --top 8")
    print("=" * 74)


# ==================== 内置样本（近三月公开漏洞的结构示例） ====================

DEMO = [
    {"title": "GitLab GraphQL 未授权任意方法调用（@gl_introduced 回退字段绕过鉴权）",
     "cve": "CVE-2026-19478", "date": "2026-08", "vuln_class": "authz",
     "root_cause": "missing_authz", "defense": "none",
     "trigger": "GraphQL 未知字段回退 resolver 直接 public_send"},

    {"title": "Langflow 未授权 RCE（build_public_tmp 端点把 code 值送进 exec）",
     "cve": "CVE-2026-33017", "date": "2026-07", "vuln_class": "rce",
     "root_cause": "trust_client", "defense": "none",
     "trigger": "data.nodes[].data.node.template.code.value"},

    {"title": "GitHub Enterprise Server 未认证路径穿越（unsanitized X-GitHub-Request-Id）",
     "cve": "CVE-2026-17556", "date": "2026-08", "vuln_class": "traversal",
     "root_cause": "trust_client", "defense": "none",
     "trigger": "请求头值进入缓冲目录路径"},

    {"title": "GitHub Enterprise Server Manage API 未认证出站请求（HMAC 仅覆盖时间戳）",
     "cve": "CVE-2026-18730", "date": "2026-09", "vuln_class": "ssrf",
     "root_cause": "incomplete_fix", "defense": "hmac",
     "trigger": "攻击者提供集群配置触发出站"},

    {"title": "GitHub Enterprise Server 绕过外部 IdP 注册（signup 未纳入策略）",
     "cve": "CVE-2026-6736", "date": "2026-05", "vuln_class": "auth",
     "root_cause": "missing_authz", "defense": "none",
     "trigger": "SAML/OIDC 开启时仍可本地建号"},

    {"title": "libssh2 预认证堆溢出（packet_length 整数回绕）",
     "cve": "CVE-2026-55200", "date": "2026-06", "vuln_class": "rce",
     "root_cause": "unknown", "defense": "none",
     "trigger": "超大 packet_length 致 malloc 尺寸回绕"},

    {"title": "Gitea act_runner 容器逃逸（Docker 后端权限控制不当）",
     "cve": "CVE-2026-58053", "date": "2026-06", "vuln_class": "privilege",
     "root_cause": "missing_authz", "defense": "none",
     "trigger": "Docker 后端默认鉴权绕过"},

    {"title": "Meta Muse 桌面代理 0day（未公开配置可改语音转录端点窃取 Token）",
     "cve": "-", "date": "2026-09", "vuln_class": "agent",
     "root_cause": "trust_client", "defense": "none",
     "trigger": "本地任意进程可改未公开配置项"},

    {"title": "Playwright MCP Host 校验修复不完整（仅 HTTP 传输加白名单）",
     "cve": "-", "date": "2025", "vuln_class": "authz",
     "root_cause": "incomplete_fix", "defense": "whitelist",
     "trigger": "allowedHosts 仅覆盖 HTTP，WS/回环未验证"},

    {"title": "tj-actions/branch-names 命令注入（printf %q 转义后 eval 再还原）",
     "cve": "CVE-2025-54416", "date": "2025", "vuln_class": "rce",
     "root_cause": "trust_client", "defense": "escape",
     "trigger": "escape→decode→解释器 链路"},

    {"title": "GitHub X-Stat 内部头覆盖（最后写入生效，可改 rails_env 等内部配置）",
     "cve": "CVE-2026-3854", "date": "2026", "vuln_class": "trust_boundary",
     "root_cause": "trust_client", "defense": "none",
     "trigger": "git push 选项嵌入分号分隔的内部头"},

    {"title": "GPT Researcher MCP 配置命令注入（command/args 字段被解释为 shell）",
     "cve": "CVE-2025-65720", "date": "2025", "vuln_class": "rce",
     "root_cause": "trust_client", "defense": "none",
     "trigger": "MCP server 配置直接进入进程创建"},

    {"title": "Exim BDAT 同会话响应差异（GnuTLS STARTTLS 下 UAF）",
     "cve": "CVE-2026-45185", "date": "2026", "vuln_class": "uaf",
     "root_cause": "unknown", "defense": "none",
     "trigger": "SMTP BDAT 分块解析时序"},

    {"title": "三星 DualDAR 驱动输入校验缺失（本地提权至 root）",
     "cve": "CVE-2026-21101", "date": "2026-09", "vuln_class": "privilege",
     "root_cause": "unknown", "defense": "none",
     "trigger": "闭源驱动未校验本地传入数据"},

    {"title": "GitLab SAML 认证绕过（删除 ds:Signature 节点）",
     "cve": "CVE-2024-45409", "date": "2024", "vuln_class": "authz",
     "root_cause": "trust_client", "cwe": "CWE-347", "defense": "signature",
     "trigger": "断言无签名仍被接受，NameID 可任意改写"},

    {"title": "GitLab SAML 认证绕过（CDATA 注入绕过 2024 补丁）",
     "cve": "CVE-2025-25291", "date": "2025", "vuln_class": "authz",
     "root_cause": "incomplete_fix", "cwe": "CWE-347", "defense": "signature",
     "trigger": "CDATA 使签名验证与取值看到不同结构"},

    {"title": "UpdraftPlus UDRPC 认证绕过（客户端指定 key_name 选密钥）",
     "cve": "CVE-2026-10795", "date": "2026", "vuln_class": "authz",
     "root_cause": "trust_client", "cwe": "CWE-347", "defense": "encryption",
     "trigger": "key_name 由客户端提供，服务端据此选解密密钥"},

    {"title": "Dell OMSA 相对路径遍历（未限制最终落点目录）",
     "cve": "CVE-2026-56794", "date": "2026-08", "vuln_class": "traversal",
     "root_cause": "unknown", "defense": "none",
     "trigger": "请求路径未规范化与目录范围校验"},
]


def cmd_demo(a):
    rows, unc = calibrate(DEMO, a.top)
    print_report(rows, unc, DEMO)
    if a.out:
        json.dump(DEMO, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"\n[+] 样本已写入 {a.out}")


def cmd_load(a):
    data = json.load(open(a.file, encoding="utf-8"))
    vulns = data if isinstance(data, list) else [data]
    if len(vulns) < 10:
        print(f"[!] 样本仅 {len(vulns)} 个，建议 15 个左右（少于 10 个统计无意义）")
    if len(vulns) > 25:
        print(f"[!] 样本 {len(vulns)} 个，校准成本偏高，建议先取 15-20 个")
    rows, unc = calibrate(vulns, a.top)
    print_report(rows, unc, vulns)
    if a.out:
        json.dump({"coverage": rows, "gaps": unc},
                  open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"\n[+] 已写入 {a.out}")


def cmd_steps(a):
    print("\n工作流步骤定义（校准用的判定基准）\n" + "=" * 74)
    for k, s in STEPS.items():
        print(f"\n● {k}  {s['name']}")
        print(f"   脚本: {s['script']}")
        print(f"   能发现: {', '.join(s['detects'])}")
    print("\n" + "=" * 74)
    print("""
校准用法：
  1. 收集最近三个月公开漏洞 15 个左右
  2. 每条至少填 title / vuln_class / root_cause
  3. python3 src_calibrate.py load --file vulns.json
  4. 看「工作流缺口」——那才是真正要补的东西
  5. 补完再校准一次，覆盖率应上升
  6. 校准完的样本直接进 src_variant.py 做外推
""")


def main():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--top", type=int, default=12)
    common.add_argument("--out")

    ap = argparse.ArgumentParser(description="工作流反向校准器：用近三月真实漏洞检验工作流")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("demo", parents=[common], help="内置 15 个样本").set_defaults(func=cmd_demo)
    s = sub.add_parser("load", parents=[common], help="载入自己收集的漏洞")
    s.add_argument("--file", required=True)
    s.set_defaults(func=cmd_load)
    sub.add_parser("steps", parents=[common], help="查看步骤定义").set_defaults(func=cmd_steps)
    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
