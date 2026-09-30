#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
src_stack.py —— 底层根因映射引擎（P10 / P12 / P13）

核心认知：**底层漏洞不是靶子，是导航图。**

协议层（NAT/DNS/BGP）、运行时层（CPython/OpenJDK/V8）、框架层（LangChain/MCP）
的 CVE 本身报不了 SRC——你证明不了"某网站受 NAT 漏洞影响"。

能报的是**映射后的应用层形态**：

    底层 CVE → 抽根因 → 在应用层长什么样 → 在目标上验证这个形态

为什么值得做：同一个根因会从协议层一直投影到应用层。
GoBGP 的"CapLen=0 却读后续字节"，在应用层就是
"Content-Length 声明 N 实际读 M"、"签名覆盖范围 ≠ 实际取值字段"。

四个命令：
  lang    语言/运行时根因族（P13）
  proto   协议层根因族（P12）
  frame   框架自身攻击面（P10）
  map     把底层根因映射到应用层可测形态（核心）
"""

import argparse
import json
import sys
from collections import OrderedDict

# ── 根因族定义：每条含 底层实例 / 根因 / 应用层映射形态 / 验证动作 ──────────
FAMILIES = OrderedDict()

FAMILIES["declared_boundary"] = {
    "name": "声明边界 ≠ 实际处理边界",
    "desc": "系统按声明值分配或校验，但实际读写的范围超出该声明",
    "base": 92,
    "ground": [
        ("协议", "GoBGP CVE-2026-49837", "capability 声明 CapLen=0，解码器却从完整缓冲区读 4 字节当 AS 号"),
        ("协议", "Unbound CVE-2026-44690", "RRSIG.Labels 与实际 label 数不符仍被接受 + 过早缓存写入"),
        ("协议", "NatJack (BH USA 2026)", "NAT 表项标记关闭却仍在内存，可被复用注入（Win 30ms / Linux 8-12ms / 路由器 4s）"),
        ("协议", "REBIRTHDAY", "ECS 使查询聚合键失效，22 款 DNS 软件 18 款有缺陷"),
        ("运行时", "CPython tarfile CVE-2026-19672", "成员名 ../evil/../dest/file 离返，包含检查用了解析后路径但中间组件未查"),
        ("运行时", "CPython tarfile CVE-2026-82049", "归档内硬链接指向符号链接，可改目的地外文件权限/时间（8.4 HIGH）"),
        ("运行时", "CPython tarfile CVE-2026-87910", "不支持链接时 fallback 提取，filter 被调用两次，第二次 name 是链接位置"),
        ("运行时", "OpenJDK CVE-2026-47058", "DataView 用绝对 ByteBuffer 索引、忽略 offset，读写超出预期窗口"),
        ("运行时", "CPython zipfile CVE-2026-15310", "bzip2/LZMA/Zstd 成员无 max_length 上限，用攻击者控制的大小预分配内存"),
        ("应用", "GitLab SAML CVE-2024-45409", "删掉 ds:Signature 节点，签名覆盖范围与实际取值分离"),
        ("应用", "Traefik CVE-2026-48020", "StripPrefix 使「匹配到的路径」≠「实际执行的路径」"),
        ("应用", "Kestra CVE-2026-49869", "AuthenticationFilter 用后缀路径匹配白名单，路径可操纵绕过 Basic Auth"),
    ],
    "app_forms": [
        ("HTTP 长度语义", "Content-Length 声明 N、实际读 M；chunked 分块边界；multipart boundary 与实际字段"),
        ("序列化长度前缀", "声明的元素数/长度 vs 实际元素；msgpack/protobuf 嵌套深度声明"),
        ("签名覆盖范围", "签名的字段 vs 实际被使用的字段（GHES HMAC 只覆盖时间戳，不覆盖路径和 body）"),
        ("路由匹配 vs 执行", "中间件改写后的路径是否重新走鉴权；前后缀匹配 vs 精确匹配"),
        ("文件解压", "压缩包声明的文件名/大小 vs 实际；符号链接/硬链接是否跟随"),
        ("数组/缓冲区", "声明容量 vs 实际索引；相对偏移 vs 绝对索引"),
    ],
    "probe": "构造「声明值」与「实际内容」不一致的输入，观察系统是否按声明值放行。"
             "例：Content-Length 小于实际 body、protobuf 深度声明与实际不符、"
             "签名覆盖 A 字段但请求改 B 字段。命中判据=系统按声明值放行且实际使用了超出部分。",
}

FAMILIES["api_misuse"] = {
    "name": "不当 API / 查找路径误用（不是缺校验，是走错路）",
    "desc": "正常输入下完美工作，代码审查看不出问题，只在攻击者控制的键名下崩溃或越界",
    "base": 85,
    "ground": [
        ("运行时", "protobufjs CVE-2026-54269",
         "schema 字段名 hasOwnProperty 遮蔽 Object.prototype 方法 → TypeError；"
         "方法名 rpcCall 遮蔽内部方法 → 无限递归栈溢出"),
        ("运行时", "OpenJDK CVE-2026-47058", "DataView 绝对索引忽略 offset，读写越出窗口"),
        ("应用", "Python eval/pickle 误用", "pickle.loads 处理跨信任边界数据 → RCE；yaml.load 未用 SafeLoader"),
    ],
    "app_forms": [
        ("原型/内部方法遮蔽", "用户可控的字段名/方法名能否覆盖 hasOwnProperty/constructor/__proto__/toString"),
        ("危险函数直达", "eval / exec / pickle.loads / yaml.load / render_template_string 是否接收不可信输入"),
        ("相对 vs 绝对", "切片、缓冲区读写用的是相对偏移还是绝对索引"),
        ("路径字符串判断", "包含判断用的是原始字符串还是规范化后的路径"),
        ("黑名单函数名过滤", "可用 getattr / importlib / 编码 / 大小写变形绕过"),
    ],
    "probe": "把字段名/方法名换成内部标识符（hasOwnProperty、constructor、__proto__、"
             "toString、valueOf、rpcCall 之类），观察是否走到非预期实现路径。"
             "命中判据=程序崩溃、栈溢出、或访问到本不该访问的内部属性。"
             "注意：这类在正常输入下完全正常，必须专门构造键名才能触发。",
}

FAMILIES["trust_inversion"] = {
    "name": "信任域反转 / 权限继承",
    "desc": "高权限组件默认信任协作方的输入，攻击者触达输入即获得高权限",
    "base": 88,
    "ground": [
        ("框架", "MCP STDIO (OX Security, 2026-04)",
         "10 个官方 SDK 全中，1.5 亿下载、20 万实例。"
         "命令在握手验证前就已执行。Anthropic 回应「这是设计如此」，拒绝修改"),
        ("框架", "Windsurf CVE-2026-30615", "零点击：处理恶意 HTML 即改 MCP 配置，无需用户交互"),
        ("框架", "Microsoft Agent Framework", "提示注入 payload 潜伏在 checkpoint 文件，他人回退会话时触发 → shell"),
        ("框架", "Google ADK", "默认云部署暴露未授权开发助手，可写并执行 Python，拿到 API key 与 GCP 服务账号凭证"),
        ("多Agent", "confused deputy", "低权限 Agent 请高权限 Agent 干活，权限沿委托链继承"),
    ],
    "app_forms": [
        ("Agent 输入是否当可信配置", "Agent 提供的路径/命令串是否直接进 subprocess，还是按不可信输入处理"),
        ("内部头可覆盖性", "X-Internal-* / X-Tenant-Id 能否由客户端写入；重复字段谁生效"),
        ("委托是否带作用域信封", "高权限接口校验的是「谁请求的」还是「请求的范围是否在授权内」"),
        ("内网流量默认可信", "内部服务间调用是否免鉴权；能否从低权限面触达高权限面"),
    ],
    "probe": "追问「这个值被谁信任了」。若是前端/Agent/第三方回调/内部服务提供，"
             "就试着改写它，看高权限组件是否照单执行。"
             "命中判据=低权限面提供的值被高权限组件无校验使用。",
}

FAMILIES["repeated_patch"] = {
    "name": "同模块短周期连环修复（补手法不重构）",
    "desc": "修复针对具体输入形态而非重构校验模型，必有下一种形态",
    "base": 90,
    "ground": [
        ("运行时", "CPython tarfile 三个月三连",
         "19672(名离返) → 82049(硬链指软链) → 87910(fallback 双调用)，间隔约一个月"),
        ("应用", "GitLab SAML 两年两连", "2024-45409(删签名) → 2025-25291(CDATA 注入绕过补丁)，EPSS 0.107→0.206"),
    ],
    "app_forms": [
        ("按模块聚合历史 CVE", "同模块名 + 同 CWE + 数月内多次 → 补手法信号"),
        ("对比每次修复的形态", "列出已被堵的形态，剩下的形态就是候选"),
        ("EPSS 是否升高", "后出 CVE 的 EPSS 更高 = 补丁绕过比原洞更活跃，优先级上调"),
    ],
    "probe": "src_rules.py vendor 找跨年重复厂商；再按模块名聚合同项目 CVE。"
             "命中判据=同模块 3-6 个月内 2 个以上同 CWE 修复，且每次针对具体输入形态。",
}

# ── 语言/运行时池（P13）───────────────────────────────────────────────────
LANG_RISK = {
    "python": {
        "runtime_cve_pool": "CPython（一年约 72 个 CVE）",
        "hot_modules": ["tarfile", "zipfile", "pickle", "yaml", "xml/expat",
                        "html.parser", "csv", "unicodedata", "urllib.request",
                        "stringprep", "re"],
        "dangerous_sinks": [
            ("pickle.loads / yaml.load", "反序列化 RCE，跨信任边界必查"),
            ("eval / exec", "代码执行"),
            ("render_template_string", "SSTI"),
            ("subprocess shell=True", "命令注入"),
            ("tarfile/zipfile extract", "路径穿越 + 链接跟随（tarfile 已三连修）"),
        ],
        "recurring_classes": ["路径包含检查", "解压炸弹/内存预分配",
                              "正则回溯 O(n²)", "Unicode 规范化复杂度", "栈溢出/递归深度"],
    },
    "java": {
        "runtime_cve_pool": "OpenJDK（单次公告可达 11 个 CVE）",
        "hot_modules": ["xml/jaxp", "core-libs/java.net", "security-libs/java.security",
                        "client-libs/2d", "org.ietf.jgss", "java.util"],
        "dangerous_sinks": [
            ("反序列化 / readObject", "gadget 链"),
            ("JNDI / LDAP lookup", "Log4Shell 类"),
            ("SpEL / OGNL 表达式", "表达式注入"),
            ("XML 外部实体", "XXE"),
            ("DataView / ByteBuffer 绝对索引", "越界读写"),
        ],
        "recurring_classes": ["证书校验不当", "正则复杂度", "O(n²) 处理",
                              "整数溢出", "越界写", "图像处理内存边界"],
    },
    "js": {
        "runtime_cve_pool": "V8 / Node",
        "hot_modules": ["protobufjs", "原型链", "模板引擎", "yaml", "vm"],
        "dangerous_sinks": [
            ("原型属性遮蔽", "hasOwnProperty/constructor/__proto__ 被字段名覆盖"),
            ("vm.runInContext", "沙箱逃逸"),
            ("Function 构造器", "动态代码生成"),
            ("模板字符串拼接编译", "注入"),
        ],
        "recurring_classes": ["原型污染", "递归深度未限制", "动态编译注入"],
    },
    "go": {
        "runtime_cve_pool": "Go runtime / 标准库",
        "hot_modules": ["net/http", "encoding", "crypto/tls", "archive"],
        "dangerous_sinks": [
            ("template.HTML", "XSS"),
            ("os/exec 拼接", "命令注入"),
            ("unsafe / 反射", "内存问题"),
        ],
        "recurring_classes": ["协议解析器边界", "并发竞态", "资源管理"],
    },
}

# ── 协议层池（P12）───────────────────────────────────────────────────────
PROTO_POOL = [
    ("NAT", "NatJack (BH USA 2026)", "连接表项关闭与复用之间存在时间窗",
     "13 厂商 32 配置全中；Cisco/Apple 认为是设计限制"),
    ("DNS", "REBIRTHDAY", "ECS 扩展使查询聚合失效，复活生日攻击",
     "22 款 DNS 软件 18 款有缺陷"),
    ("DNS", "Unbound CVE-2026-44690", "RRSIG.Labels 校验不足 + 过早缓存写入", ""),
    ("DNS", "Unbound CVE-2026-42960", "附加段地址记录被信任缓存（CWE-349）", "CVSS 10.0"),
    ("BGP", "GoBGP CVE-2026-49837", "CapLen=0 仍读后续字节作 AS 号", "影响 peer AS 校验"),
    ("TLS", "OpenJDK wantClientAuth", "客户端发 no_certificate 告警时证书不被校验", "CWE-295"),
    ("HTTP/3", "DNSdist CVE-2026-40211", "DoH3 并发流异常导致缓冲区延迟释放 → OOM", ""),
    ("IP", "BGP 前缀劫持", "更长前缀匹配劫持流量（Virtualizor 被劫持 22 小时）", "无源认证是根因"),
]

# ── 框架池（P10）─────────────────────────────────────────────────────────
FRAME_POOL = [
    ("MCP", "STDIO 传输命令注入", "设计缺陷，厂商拒绝修复",
     "10 SDK 全中 / 1.5 亿下载 / 20 万实例"),
    ("LangGraph", "checkpointer SQLi + msgpack 反序列化 → RCE",
     "链条：CVE-2025-67644 + CVE-2026-28277 + CVE-2026-27022", "月下载 5000 万"),
    ("LangChain", "路径遍历 + 环境变量泄露 + 会话历史", "CVSS 9.3", ""),
    ("Langflow", "CVE-2026-5027 路径遍历", "默认未授权自动登录，无需凭证", "约 7000 公开实例"),
    ("Kestra", "CVE-2026-49869 / 53576 认证绕过", "后缀路径匹配绕过", "CVSS 10.0"),
    ("Traefik", "CVE-2026-48020 / 48491 / 53622", "中间件路径处理三连", "CVSS 10.0"),
    ("n8n", "CVE-2026-54309 MCP 端点未授权", "", "CVSS 10.0"),
    ("Budibase", "CVE-2026-54350 NoSQL 操作符注入", "JSON 元字符覆盖查询过滤", "CVSS 10.0"),
    ("Gogs", "CVE-2026-52813 组织名路径穿越", "", "CVSS 10.0"),
    ("Flowise", "CVE-2025-71338 未授权路径穿越 → RCE", "", "CVSS 10.0"),
    ("WordPress", "CVE-2026-87902 模板路径遍历", "CVSS 9.2，需 page- 目录 + 本地可利用 php", "占全球 40% 网站"),
    ("WordPress", "CVE-2026-63030 REST batch RCE", "CVSS 9.8", ""),
]


def show_families(a):
    print("=" * 74)
    print(" 底层根因族（协议层 / 运行时层 / 框架层 → 应用层映射）")
    print("=" * 74)
    for k, f in FAMILIES.items():
        print(f"\n● {k}  [{f['base']}分]  {f['name']}")
        print(f"   {f['desc']}")
        print("\n   ── 底层实证 ──")
        for layer, name, detail in f["ground"]:
            print(f"   [{layer:4}] {name}")
            print(f"         {detail}")
        print("\n   ── 应用层映射形态 ──")
        for title, form in f["app_forms"]:
            print(f"   · {title}: {form}")
        print(f"\n   ── 验证动作 ──\n   {f['probe']}")
        print()
    print("=" * 74)
    print("""
核心纪律：底层 CVE 是导航图，不是靶子。

协议层/运行时层/框架层的漏洞本身报不了 SRC——
你证明不了「某网站受 NAT 漏洞影响」。

能报的是映射后的应用层形态：它在目标的代码里，在 SRC 范围内。
""")


def show_lang(a):
    lang = a.lang.lower()
    if lang not in LANG_RISK:
        print(f"[!] 未收录 {lang}，可选: {', '.join(LANG_RISK)}")
        return 1
    d = LANG_RISK[lang]
    print("=" * 74)
    print(f" {lang} · 运行时与标准库攻击面（P13）")
    print("=" * 74)
    print(f"\nCVE 池: {d['runtime_cve_pool']}")
    print("\n── 高危模块 ──")
    for m in d["hot_modules"]:
        print(f"   {m}")
    print("\n── 危险 sink ──")
    for s, why in d["dangerous_sinks"]:
        print(f"   {s}")
        print(f"      {why}")
    print("\n── 该语言的复发漏洞类 ──")
    for c in d["recurring_classes"]:
        print(f"   {c}")
    print(f"""
── 用法 ──
1. 这些 CVE 不是靶子，是导航图
2. 用 src_variant.py gen 对每条抽根因（重点看 declared_boundary / api_misuse）
3. 映射到目标代码：目标有没有同类形态
4. 只有映射后的应用层形态才进验证队列

示例：
  python3 src_stack.py map --family declared_boundary
""")
    return 0


def show_proto(a):
    print("=" * 74)
    print(" 协议层根因池（P12 · 自下而上映射）")
    print("=" * 74)
    for proto, name, detail, note in PROTO_POOL:
        print(f"\n● [{proto}] {name}")
        print(f"   {detail}")
        if note:
            print(f"   → {note}")
    print(f"""
══════════════════════════════════════════════════════════════════════
 为什么协议层漏洞值得追：同一根因会一路投影到应用层
══════════════════════════════════════════════════════════════════════

  GoBGP  CapLen=0 却读后续字节
     ↓  同一个根因
  应用层 Content-Length 声明 N 实际读 M
         chunked 边界、multipart boundary
         签名覆盖范围 ≠ 实际取值字段

  Unbound  RRSIG.Labels 与实际不符仍接受
     ↓
  应用层 声明的长度/数量/类型未与实际核对

  NatJack  表项标记关闭却仍在内存
     ↓
  应用层 状态转换处未重新验证（GHES HMAC 只覆盖时间戳）

══════════════════════════════════════════════════════════════════════
 能提交的是映射后的形态，不是协议层 CVE 本身
══════════════════════════════════════════════════════════════════════
""")
    return 0


def show_frame(a):
    print("=" * 74)
    print(" 框架自身攻击面（P10 · 挖框架而非应用）")
    print("=" * 74)
    print("\n框架层一个洞影响所有下游——这是杠杆最高的方向\n")
    for name, vuln, note, scale in FRAME_POOL:
        print(f"● {name}")
        print(f"   {vuln}")
        if note:
            print(f"   {note}")
        if scale:
            print(f"   规模: {scale}")
        print()
    print("""══════════════════════════════════════════════════════════════════════
 信号优先级（与本工作流其他步骤一致）
══════════════════════════════════════════════════════════════════════

 厂商拒绝修复  ★★★★★  永久有效，不会有人来修（MCP STDIO）
 静默补丁      ★★★★   修了不认领，竞争几乎为零
 修复不完整    ★★★★   换形态就能打
 公开 CVE      ★★     竞争最激烈，比手速

注意：框架层是公开舞台，盯的人远多于单个站点。
差异化不靠「知道得早」，靠「看到别人没看的关联」。

══════════════════════════════════════════════════════════════════════
 建站框架的特殊性
══════════════════════════════════════════════════════════════════════

攻击面主要在插件生态，不在核心——核心修得快，插件没人管。
（ASD 警报列出 17 个 WordPress 插件 CVE，全在未授权上传/RCE/SSRF/反序列化）

WordPress 占全球约 40% 网站，是最大的单一靶池。
""")
    return 0


def show_map(a):
    if a.family not in FAMILIES:
        print(f"[!] 未找到 {a.family}，可选: {', '.join(FAMILIES)}")
        return 1
    f = FAMILIES[a.family]
    print("=" * 74)
    print(f" 映射 · {a.family}  [{f['base']}分] {f['name']}")
    print("=" * 74)
    print(f"\n{f['desc']}\n")
    print("── 应用层可测形态（这些才进验证队列）──")
    for i, (title, form) in enumerate(f["app_forms"], 1):
        print(f"\n{i}. {title}")
        print(f"   {form}")
    print(f"\n── 验证动作 ──\n{f['probe']}")
    print(f"""
── 状态标记纪律 ──
[!] 命中：有客观差异（响应不同 / 越权读到他人数据 / 崩溃栈可复现）
[~] 假设：只有推理链，无客观差异 —— 不是发现，不写进报告
[x] 排除：必须写排除理由

── 提交纪律 ──
底层 CVE 本身不提交（报不了，会被打回）。
只提交映射后在目标代码里复现出的应用层形态。
""")
    return 0


def main():
    ap = argparse.ArgumentParser(description="底层根因映射引擎：协议/运行时/框架 → 应用层")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("families", help="全部根因族").set_defaults(func=show_families)

    s = sub.add_parser("lang", help="语言/运行时攻击面（P13）")
    s.add_argument("--lang", required=True, choices=list(LANG_RISK))
    s.set_defaults(func=show_lang)

    sub.add_parser("proto", help="协议层根因池（P12）").set_defaults(func=show_proto)
    sub.add_parser("frame", help="框架自身攻击面（P10）").set_defaults(func=show_frame)

    s = sub.add_parser("map", help="根因 → 应用层映射（核心）")
    s.add_argument("--family", required=True, choices=list(FAMILIES))
    s.set_defaults(func=show_map)

    a = ap.parse_args()
    sys.exit(a.func(a) or 0)


if __name__ == "__main__":
    main()
