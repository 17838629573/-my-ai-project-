#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
src_variant.py —— 漏洞模式泛化引擎

定位：把「一篇公开漏洞报告」变成「一组可测的变体假设」。

解决的问题：
  公开报告通常只讲一个点（某个接口、某个参数、某种触发方式）。
  但根因往往是通用的。本脚本按泛化维度自动推导：
  "这个根因还可能在哪些地方、以什么形式出现？"

输出不是漏洞，是**假设**。每个假设带操作与命中判据，需人工验证。

用法：
  python3 src_variant.py demo            # 内置样例跑通
  python3 src_variant.py gen --file vuln.json --top 12
  python3 src_variant.py dims            # 查看全部泛化维度
"""

import argparse
import json
import os
from collections import OrderedDict

# ==================== 泛化维度库 ====================
# 每个维度：适用条件 → 操作 → 命中判据 → 基础分（历史命中率）

DIMS = OrderedDict()


def dim(key, name, applies, action, judge, base, note=""):
    DIMS[key] = {"name": name, "applies": applies, "action": action,
                 "judge": judge, "base": base, "note": note}


dim(
    "symmetry", "对称性：反向/互补操作",
    lambda v: True,
    "原洞是「读」，就测「写/改/删」；原洞是「上传」，就测「下载/删除/列举」；"
    "原洞是「创建」，就测「修改/转移归属」",
    "反向操作的响应中同样缺失原漏洞点所缺失的那道校验",
    85,
    "命中率最高的维度。多数开发只校验了用户看得到的那个方向",
)

dim(
    "sibling", "同族：同模块其他接口 / 其他端点",
    lambda v: True,
    "列出同模块全部接口，套用同一手法；再扩展到 PC端/移动端/小程序端/管理端"
    "的同名接口",
    "同族接口出现相同的校验缺失",
    90,
    "一个接口有问题，同一批代码写的接口大概率都有",
)

dim(
    "method", "方法变换：HTTP Method",
    lambda v: True,
    "GET 能触发就试 POST/PUT/PATCH/DELETE；再试 HEAD、OPTIONS；"
    "再试用 X-HTTP-Method-Override 头改写方法",
    "其他方法绕过校验，或触发不同的后端处理分支（往往更松）",
    70,
    "网关按方法做鉴权是常见做法，改方法常能穿透",
)

dim(
    "encode", "等价变形：编码与绕过（针对过滤类防护）",
    lambda v: v.get("defense") in ("blacklist", "filter", "waf", "regex"),
    "列出全部等价表示：URL 编码/双重编码、Unicode 归一化、大小写、"
    "路径分隔符替换（/ ↔ \\）、点号变体（../ ↔ ..;/ ↔ ..%00/）、"
    "换行与空白、注释插入、协议大小写、IP 进制/域名指回",
    "变形后的输入到达了原被拦截的位置并生效",
    88,
    "黑名单几乎总能绕。这是补丁修复不完整类情报的头号突破口",
)

dim(
    "sig_separation", "★签名/校验对象与取值对象分离（CWE-347族）",
    lambda v: (v.get("root_cause") in ("incomplete_fix", "trust_client")
               or "347" in str(v.get("vuln_class", "")) + str(v.get("cwe", ""))
               or any(k in str(v.get("trigger", "")).lower()
                      for k in ("sign", "signature", "hmac", "jwt", "saml",
                                "key_name", "digest", "verify"))),
    "构造让「校验看到的对象」与「实际使用的对象」分离的变体："
    "①删掉签名/校验节点本身；②CDATA/XML注释包裹使两解析器看到不同结构；"
    "③命名空间前缀变体与重复字段（测最后写入生效 vs 先到优先）；"
    "④编码差异（UTF-16/双重编码/实体引用）；"
    "⑤客户端提供的标识符（如 key_name）能否切换服务端选用的密钥",
    "签名验证通过，但实际取到的值与被签名覆盖的内容不一致",
    95,
    "CWE-347 族实证：GitLab SAML 2024(删签名)→2025(CDATA注入)两次绕过、"
    "UpdraftPlus(客户端指定key_name)。三者协议完全不同，根因同一",
)

dim(
    "conditional_guard", "条件校验 vs 强制校验",
    lambda v: True,
    "审查校验代码的分支形态：是 if(x){verify(x)} 还是 if(!x){reject()}？"
    "前者在 x 缺失/为空/为 null 时直接跳过校验，后者才是不变量。"
    "重点测：字段缺失、空字符串、null、空数组、字段类型错误",
    "缺失或异常形态的字段导致校验被整体跳过",
    88,
    "「没有签名就跳过验证」是 CWE-347 与 CWE-287 的共同形态",
)

dim(
    "vendor_recurrence", "★同厂商/同组件跨年复发",
    lambda v: True,
    "查该 vendor/product 的历史 CVE（按 CWE 聚合，不按 CVE 编号）。"
    "若同 CWE 跨年重复出现，说明修复是补手法而非重构校验模型——必有第三次。"
    "再对比 EPSS：若较新 CVE 的 EPSS 更高，说明补丁绕过比原洞更活跃",
    "找到同组件、同 CWE、跨年的第二个以上 CVE，且根因形态未被结构性修复",
    92,
    "实证：GitLab SAML 2024→2025，EPSS 0.107→0.206 翻倍。"
    "工具：src_rules.py vendor / src_rules.py cwe --cwe CWE-XXX",
)

dim(
    "rule_coord", "★规则库坐标提取（读规则而非跑扫描）",
    lambda v: True,
    "在公开检测规则库里按 CWE 检索该根因族，读取完整攻击坐标："
    "端点、参数路径、硬编码密钥/IV/种子、编码格式、脆弱与已修的响应判据、"
    "FOFA/Shodan 测绘语法、是否在野利用(vkev)。"
    "公告只说「存在绕过」，规则给到字节级构造",
    "找到同根因族的公开规则，并从中提取出至少一个可复用的攻击构造要素",
    90,
    "规则库是二手但密度最高的知识源。工具：src_rules.py coord --cve <CVE>",
)

dim(
    "boundary", "信任边界：上游/下游/回调",
    lambda v: True,
    "追问「这个值被谁信任了」：前端传的值？第三方回调？内部服务调用？"
    "消息队列？定时任务？分别尝试伪造该来源",
    "越过边界后，原本被信任的输入可被外部控制",
    80,
    "越权/伪造类漏洞的根源，往往是信任了不该信任的来源",
)

dim(
    "state", "状态机：步骤乱序 / 跳过 / 重放",
    lambda v: True,
    "多步流程：跳过前置步骤直接请求最后一步；调换顺序；"
    "重放已完成的步骤；回退到中间态后再走分支",
    "状态校验不依赖步骤完整性，某一步可独立触发",
    75,
    "前端跳转不等于后端校验",
)

dim(
    "concurrency", "时序：并发与竞态",
    lambda v: v.get("vuln_class") in ("logic", "idor", "payment", "coupon",
                                      "inventory", "auth", "token", "upload"),
    "同一操作并发 N 次（限领1张券/库存1件/单次验证码）；"
    "或并发不同操作制造 TOCTOU（校验与执行之间的窗口）",
    "限制被突破（领取多次/超卖/验证码复用），或出现校验后的状态被改",
    82,
    "单线程测必定正常，必须并发。SRC 逻辑漏洞主力",
)

dim(
    "param_shape", "参数形态：类型与边界值",
    lambda v: True,
    "对同名字段做形态变异：负数、0、小数、极大值（溢出）、空、null、"
    "数组而非标量（JSON 类型混淆）、超长字符串、特殊字符、"
    "嵌套对象、字段重复出现两次",
    "服务端接受了异常形态并按异常逻辑处理（如类型混淆绕过校验）",
    68,
    "JSON 传数组 vs 字符串，常能绕过只校验其中一种的代码",
)

dim(
    "version", "版本：老接口 / 灰度 / 备用路径",
    lambda v: True,
    "试 /v1/ /v2/ /api/internal/ /beta/ /test/ 前缀；"
    "试接口名加 -old/-bak/2；试直连后端端口与内网 IP 绕过网关",
    "老版本或内部路径使用了更弱的校验，或绕过网关鉴权",
    72,
    "网关拦新版，老接口往往没人管",
)

dim(
    "ecosystem", "生态迁移：同类组件 / 同类实现",
    lambda v: True,
    "该组件有这个问题 → 同生态其他组件呢？"
    "（jackson-databind SSRF → fastjson/Gson/snakeyaml？）"
    "该业务有这个问题 → 同行业其他家的同款功能呢？",
    "同类组件存在相同的根因但不同的触发细节",
    65,
    "适合跨目标复用，一次研究多次产出",
)

dim(
    "chain", "串联：与其他低危组合",
    lambda v: True,
    "找能和它组合的其他弱点：CORS+XSS、开放重定向+OAuth、"
    "信息泄露+密钥、SSRF+内网服务、任意文件读+配置文件",
    "组合后危害显著高于任一单点",
    78,
    "两个低危拼一个高危，评级跃迁的主要方式",
)

dim(
    "silent", "静默补丁：往回翻未认领的修复",
    lambda v: v.get("root_cause") in ("incomplete_fix", "silent_patch", "unknown"),
    "在该组件的 git log 里搜改动集中在校验/边界/过滤、但描述平淡的 commit"
    "（improve check / fix edge case / refactor / hardening）",
    "找到未被公开认领的安全修复 → 即未披露的 1-day",
    92,
    "竞争几乎为零。修复不完整类情报必做",
)

# ===== 以下 5 个维度来自前沿研究归纳（2025-2026）=====
# 来源：《前沿漏洞拆解与外推分析》——10 个案例归并为 5 类根因族
# 核心发现：高价值漏洞不源于"某个危险函数"，而源于
#           **系统在某个状态转换处没有重新验证**

dim(
    "invariant", "★ 不变量冲突：同一对象的两种表示走不同校验路径",
    lambda v: True,
    "构造两个「描述同一对象但表示不同」的输入，比较它们的校验结果。"
    "具体配对：不同端口/协议（HTTP↔WS↔Unix socket↔回环 IPv4/IPv6）、"
    "Host↔SNI↔X-Forwarded-Host、查询↔响应的扩展字段（DNS ECS）、"
    "外部内容↔系统提示、包名↔代码来源、命令↔参数、内部头↔用户输入",
    "两种表示得到不同的权限判定、路由结果或状态归属，"
    "且该差异可重复、可解释",
    95,
    "★ 前沿研究归纳出的最高价值方法。十个案例的共同底层结构："
    "系统没有在状态转换处重新验证",
)

dim(
    "boundary_all", "边界一致性：所有入口是否以同一方式验证来源",
    lambda v: v.get("root_cause") in ("missing_authz", "trust_client", "incomplete_fix"),
    "枚举全部入口：HTTP/HTTPS/WS/WSS/Unix socket/回环 IPv4+IPv6/"
    "容器内部服务名/同 Pod sidecar/K8s service/NodePort/本地代理端口，"
    "对同一资源发同一请求，比较 403/200/101 与响应内容",
    "某一入口返回成功而其他入口被拒绝 → 授权入口不一致",
    88,
    "Playwright MCP 案例：补丁只给 HTTP 加了 allowedHosts，"
    "WebSocket 与回环地址是否被覆盖需逐传输验证",
)

dim(
    "meta_consistency", "元数据一致性：查询与响应是否维护同一不变量",
    lambda v: v.get("vuln_class") in ("cache", "dns", "signature", "ssrf", "token"),
    "构造「安全不等价但缓存键/签名键可能等价」的两组请求。"
    "方法：交替发送带/不带扩展字段、重复扩展字段、"
    "大小写或顺序不同的同名字段、不同传输（DoH/DoT/明文），"
    "观察响应来源、TTL、缓存命中标识",
    "攻击者可控的响应进入本应绑定另一元数据的缓存/状态，"
    "且能被后续请求命中",
    86,
    "RebirthDay 案例：22 款 DNS 软件中 18 款在 ECS 处理上存在缺陷，"
    "说明「修复一个实现」≠「修复协议扩展的一致性族」",
)

dim(
    "decode_chain", "语义复活化：转义后又被还原",
    lambda v: v.get("defense") in ("blacklist", "filter", "regex", "waf"),
    "追踪是否存在 encode→decode→解释器 链路。"
    "重点四类：printf %q 再 eval printf %s、JSON 转义再 shell、"
    "YAML 折叠再模板、Base64 再 decode 再执行",
    "最终解释点看到的不再是「已定型的值」，"
    "而是重新获得执行语义的原始不可信输入",
    90,
    "tj-actions/branch-names 案例：转义是编码决策，不是永久属性。"
    "一旦重新解释，不可信来源重新获得执行语义",
)

dim(
    "internal_field", "信任域反转：内部元数据可被外部输入覆盖",
    lambda v: v.get("root_cause") in ("trust_client", "missing_authz", "unknown"),
    "在合法请求中追加/重复具有内部语义的字段："
    "X-Internal-* 、以 : 开头的伪头、trace/tenant/region/env/hook/path。"
    "值设为可观察标记。再测字段名大小写、重复头、不同分隔符、"
    "URL 编码、Unicode 规范化，比较「外部先/内部先」的优先级",
    "外部字段覆盖了系统已设定的安全属性，且产生可观察的安全影响",
    87,
    "GitHub X-Stat 案例：解析采用「最后写入生效」，"
    "攻击者可覆盖 rails_env / custom_hooks_dir 等内部配置",
)


# ==================== 适用性与加权 ====================

BOOST = {
    "incomplete_fix": {"encode": 25, "silent": 30, "sibling": 10, "invariant": 20,
                       "boundary_all": 15, "decode_chain": 20},
    "silent_patch": {"silent": 30, "encode": 15, "invariant": 15},
    "missing_authz": {"sibling": 20, "symmetry": 15, "method": 15, "version": 10,
                      "boundary_all": 25, "invariant": 20},
    "trust_client": {"boundary": 25, "param_shape": 15,
                     "internal_field": 25, "invariant": 20},
    "blacklist": {"encode": 30, "silent": 15, "decode_chain": 25, "invariant": 15},
    "race": {"concurrency": 30},
    "deserial": {"ecosystem": 20, "encode": 15, "param_shape": 15},
    "path_traversal": {"encode": 30, "sibling": 10, "method": 10},
}


def gen_variants(v, topn=12, minscore=0):
    out = []
    rc = (v.get("root_cause") or "").lower()
    cls = (v.get("vuln_class") or "").lower()
    boost = BOOST.get(rc, {})

    for key, d in DIMS.items():
        try:
            if not d["applies"](v):
                continue
        except Exception:
            pass
        score = d["base"] + boost.get(key, 0)

        # 类型微调
        if cls in ("ssrf", "sqli", "cmd", "ssti", "upload", "traversal"):
            if key == "encode":
                score += 10
        if cls in ("idor", "authz", "auth", "unauth"):
            if key in ("sibling", "symmetry", "method", "version"):
                score += 8
        if cls in ("logic", "payment", "coupon", "inventory"):
            if key in ("concurrency", "state", "param_shape"):
                score += 12

        if score < minscore:
            continue
        out.append({
            "dim": key, "name": d["name"], "score": score,
            "action": d["action"], "judge": d["judge"],
            "note": d["note"],
        })

    out.sort(key=lambda x: -x["score"])
    return out[:topn]


def print_variants(v, vs):
    print("\n" + "=" * 70)
    print(f" 原洞: {v.get('title', '(无标题)')}")
    print(f" 组件: {v.get('component', '-')} | 根因: {v.get('root_cause', '-')} "
          f"| 类型: {v.get('vuln_class', '-')} | 防护: {v.get('defense', '-')}")
    print("=" * 70)
    if not vs:
        print(" 无可用假设。检查 root_cause / vuln_class 是否填写。")
        return
    print(f"\n 共 {len(vs)} 条变体假设（**均为假设，需逐个验证**）\n")
    for i, x in enumerate(vs, 1):
        print(f"[{i}] {x['score']} 分  {x['name']}  ({x['dim']})")
        print(f"     操作: {x['action']}")
        print(f"     判据: {x['judge']}")
        if x["note"]:
            print(f"     备注: {x['note']}")
        print()


# ==================== 样例 ====================

DEMO = {
    "title": "jackson-databind: Incomplete fix for CVE-2026-54514 — "
             "eager DNS resolution (SSRF) still present in InetAddress deserialization",
    "component": "jackson-databind",
    "root_cause": "incomplete_fix",
    "defense": "blacklist",
    "vuln_class": "ssrf",
    "trigger": {"location": "body-json", "param": "InetAddress field"},
    "affected_ops": ["deserialize"],
}

DEMO2 = {
    "title": "某订单接口未授权访问：改 orderId 可读他人订单",
    "component": "自研业务",
    "root_cause": "missing_authz",
    "defense": "none",
    "vuln_class": "idor",
    "trigger": {"location": "query", "param": "orderId"},
    "affected_ops": ["read"],
}


def cmd_demo(args):
    for v in (DEMO, DEMO2):
        vs = gen_variants(v, topn=args.top, minscore=args.minscore)
        print_variants(v, vs)


def cmd_gen(args):
    with open(args.file, encoding="utf-8") as f:
        data = json.load(f)
    items = data if isinstance(data, list) else [data]
    for v in items:
        vs = gen_variants(v, topn=args.top, minscore=args.minscore)
        print_variants(v, vs)
    if args.out:
        dump = [{"source": v.get("title"), "variants": gen_variants(v, 99, args.minscore)}
                for v in items]
        json.dump(dump, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"[+] 已写入 {args.out}")


def cmd_dims(args):
    print("\n泛化维度库（共 %d 个）\n" % len(DIMS))
    print("=" * 70)
    for k, d in DIMS.items():
        print(f"\n● {d['name']}  [{k}]  基础分 {d['base']}")
        print(f"  操作: {d['action']}")
        print(f"  判据: {d['judge']}")
        if d["note"]:
            print(f"  备注: {d['note']}")


def main():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--top", type=int, default=12)
    common.add_argument("--minscore", type=int, default=0)
    common.add_argument("--out")

    ap = argparse.ArgumentParser(description="漏洞模式泛化引擎：从一篇报告推一组变体假设")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("demo", parents=[common], help="内置样例").set_defaults(func=cmd_demo)
    s = sub.add_parser("gen", parents=[common], help="从 JSON 生成变体假设")
    s.add_argument("--file", required=True)
    s.set_defaults(func=cmd_gen)
    sub.add_parser("dims", parents=[common], help="查看维度库").set_defaults(func=cmd_dims)
    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
