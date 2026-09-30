#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
src_gate.py —— 确定性规则硬化引擎

设计动机：WORKFLOW.md 实测 557 行里，引导提问只占 21%，
而"必须/禁止/一律"这类要记住并执行的硬性措辞出现 44 次。

规则是要逐条比对、持续占用注意力的；提问是读完就理解的叙事。
所以把**可判定的规则搬进代码**，文档只留提问。

硬化的是**判据**，不是**路径**：
  ✅ 硬化：什么叫命中、够不够格提交、限速多少、证据够不够
  ❌ 不硬化：往哪找、这个根因像什么、要不要换角度（这些留给提问）

六个闸门：
  rate      限速（按平台判定，不靠自觉）
  evidence  证据链完整性（缺请求/响应/判定数值 → 拦下）
  merge     同根因是否该合并报
  intel     高价值情报是否完成二次源验证
  quota     注意力配额（每批 ≤4 探针、每天 ≤10 假设）
  preflight 开工前置检查（凭证齐备？）

外加：
  rules     打印所有硬规则（人看）
  check     一次跑完所有闸门
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, ".gate_state.json")

# ── 硬规则数据（这些原本写在文档里，现在由代码判定）────────────────────────

# 限速：实测不同平台差两个数量级，用错即违规
RATE_LIMITS = {
    "atmail": {"rps": 5, "notes": "≤5 req/s per host；禁止无人值守扫描"},
    "kernel": {"rps": 10, "notes": "≤10 req/s；需带 X-HackerOne-Research 头"},
    "openbugbounty": {"rps": 10 / 60, "notes": "≤10 req/min；登录尝试 ≤10/h"},
    "hackerone": {"rps": 5, "notes": "默认保守值，按项目策略调整"},
    "bugcrowd": {"rps": 5, "notes": "默认保守值，按项目策略调整"},
    "edusrc": {"rps": 1, "notes": "教育行业 SRC，保守值"},
    "cnvd": {"rps": 1, "notes": "保守值"},
    "default": {"rps": 1, "notes": "未收录平台 → 一律按最保守值，不要猜"},
}

# 证据链必备字段（Atmail 规则：scanner output 必须 manually confirmed）
EVIDENCE_REQUIRED = {
    "request": "请求原文（含方法/路径/头/体）",
    "response": "响应原文（状态码 + 关键片段）",
    "verdict": "代码判定数值（sim/status/reject_hit 等）",
    "precondition": "复现前置条件（需要什么账号/配置/版本）",
}

# 提交禁令（这些是纪律，硬化为拦截）
SUBMIT_BLOCKS = [
    ("scanner_only", "脚本产出未经人工复现", "Atmail: automated scanners ineligible"),
    ("no_evidence", "证据链不完整", "缺请求/响应/判定数值/前置条件任一"),
    ("speculative", "只有推理链无客观差异", "臆测一律丢弃"),
    ("raw_cve", "直接提交底层/协议层 CVE", "报不了，会被打回"),
    ("exceed_rate", "超出平台限速", "用错即违规"),
]


# ── 状态存取（用于 quota 追踪）─────────────────────────────────────────────
def load_state():
    if os.path.exists(STATE):
        try:
            return json.load(open(STATE, encoding="utf-8"))
        except Exception:
            pass
    return {"day": None, "hypotheses": 0, "batches": []}


def save_state(st):
    json.dump(st, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def today():
    return datetime.now().strftime("%Y-%m-%d")


# ── 闸门实现 ──────────────────────────────────────────────────────────────
def gate_rate(a):
    key = (a.platform or "default").lower()
    cfg = RATE_LIMITS.get(key, RATE_LIMITS["default"])
    rps = cfg["rps"]
    if a.rps is None:
        print(f"[{key}] 限速 {rps:.4g} req/s —— {cfg['notes']}")
        print(f"\n  --delay 是必填项，不是可选优化项。")
        if rps >= 1:
            print(f"  建议 --delay 0（{rps:.0f} req/s 上限内）")
        else:
            print(f"  建议 --delay {1 / rps:.0f}（对应 {rps:.4g} req/s）")
        return 0
    ok = a.rps <= rps
    tag = "OK  " if ok else "FAIL"
    print(f"[{tag}] {key}: 设定 {a.rps} req/s vs 上限 {rps:.4g} req/s")
    if not ok:
        print(f"   [x] 超出限速 —— 违规风险，必须调低")
        print(f"   {cfg['notes']}")
        return 1
    print(f"   [x] 合规")
    return 0


def gate_evidence(a):
    """检查疑似项证据链是否完整"""
    if not a.file:
        print("用法: src_gate.py evidence --file item.json")
        print("\n必备字段:")
        for k, v in EVIDENCE_REQUIRED.items():
            print(f"   {k:14} {v}")
        return 0
    d = json.load(open(a.file, encoding="utf-8"))
    items = d if isinstance(d, list) else [d]
    bad = 0
    for i, it in enumerate(items, 1):
        miss = [k for k in EVIDENCE_REQUIRED if not it.get(k)]
        title = it.get("title") or it.get("id") or f"#{i}"
        if miss:
            bad += 1
            print(f"   [x] {title} —— 缺: {', '.join(miss)}")
        else:
            print(f"   [OK] {title}")
    print(f"\n{bad}/{len(items)} 项证据不完整")
    if bad:
        print("\n判据：交给不了解目标的人，能不能照着证据独立复现？")
        print("不能 → 不算发现，不许提交。")
    return 1 if bad else 0


def gate_merge(a):
    """同根因是否该合并报（EDUSRC: 多处相似漏洞降等级）"""
    if not a.file:
        print("用法: src_gate.py merge --file items.json")
        print("\n按 root_cause + cwe 聚合，同组应合并为一份报告。")
        return 0
    items = json.load(open(a.file, encoding="utf-8"))
    items = items if isinstance(items, list) else [items]
    groups = {}
    for it in items:
        k = (it.get("root_cause", "?"), it.get("cwe", "?"))
        groups.setdefault(k, []).append(it.get("title") or it.get("id") or "?")
    print("=" * 70)
    print(" 合并判定（同根因应合并，拆开报会被降等级）")
    print("=" * 70)
    for (rc, cwe), titles in groups.items():
        print(f"\n● 根因={rc}  CWE={cwe}   共 {len(titles)} 条")
        for t in titles:
            print(f"   - {t}")
        if len(titles) > 1:
            print(f"   → [!] 应合并为一份，按整体影响面定级")
    return 0


def gate_intel(a):
    """高价值情报二次源验证（EPSS>0.5 或 KEV 在列）"""
    epss = a.epss
    kev = a.kev
    if epss is None and not kev:
        print("用法: src_gate.py intel --epss 0.93723 [--kev]")
        print("\nEPSS > 0.5 或 KEV 在列 → 必须完成三层验证才能使用。")
        return 0
    need = (epss is not None and epss > 0.5) or kev
    print("=" * 70)
    print(" 情报二次源验证")
    print("=" * 70)
    print(f"EPSS: {epss}  KEV: {kev}")
    if not need:
        print("\n[OK] 非高价值情报，无需强制交叉验证")
        return 0
    print("\n[!] 高价值情报 —— 必须完成三层，缺一不可:\n")
    print("  1. 本地源原文：该字段是否逐行独立、无跨行挪用")
    print("  2. 解析链路：脚本是逐字段独立提取，还是按行号拼接")
    print("  3. 官方 API 交叉：")
    print(f"     curl https://api.first.org/data/v1/epss?cve={a.cve or '<CVE>'}")
    print("\n理由：FOFA 语法错了还能重扫，优先级排错了浪费整个周期。")
    print(f"\n三层状态（--src/--parse/--api 标记已完成项）:")
    done = sum([bool(a.src), bool(a.parse), bool(a.api)])
    for name, flag in (("本地源原文", a.src), ("解析链路", a.parse), ("官方API", a.api)):
        print(f"   [{'x' if flag else ' '}] {name}")
    if done < 3:
        print(f"\n   [x] 未完成 {3 - done} 层 —— 该情报暂不可用于优先级决策")
        return 1
    print("\n   [OK] 三层齐全，可使用")
    return 0


def gate_quota(a):
    """注意力配额：每批 ≤4 探针组、每天 ≤10 假设"""
    st = load_state()
    if st.get("day") != today():
        st = {"day": today(), "hypotheses": 0, "batches": []}
    if a.add:
        st["hypotheses"] += a.add
        save_state(st)
    print("=" * 70)
    print(f" 注意力配额（今日 {today()}）")
    print("=" * 70)
    print(f"   待验证假设: {st['hypotheses']}/10")
    if st["hypotheses"] >= 10:
        print("\n   [x] 已达上限 —— 停止发散，转入验证")
        print("      12 个维度 × N 条情报会爆炸，发散必须有配额")
        return 1
    if st["hypotheses"] >= 7:
        print("\n   [!] 接近上限，优先验证已有假设，不要再发散")
    print("\n   每批最多 4 个探针组（超过 4 个判据会互相干扰）")
    return 0


def gate_preflight(a):
    """开工前置检查（R1）"""
    print("=" * 70)
    print(" 开工前置检查")
    print("=" * 70)
    checks = [
        ("授权范围", a.scope, "域名/IP/组件清单，缺一不可"),
        ("平台限速", a.rate, "开工前按平台规则设定 --delay"),
        ("A/B 凭证", a.cred, "无 A/B 账号 → 跳过 P3，不空跑"),
        ("目标非纯静态", a.interactive, "纯静态官网 → 探测器照不到，尽早换目标"),
    ]
    bad = 0
    for name, ok, hint in checks:
        mark = "OK  " if ok else "FAIL"
        print(f"   [{mark}] {name:12} {'' if ok else hint}")
        if not ok:
            bad += 1
    print()
    if bad:
        print(f"   [x] {bad} 项不通过")
        print("      凭证/目标类缺口要在 P2 选目标时就确认，不要等 P3 门口才发现")
        return 1
    print("   [OK] 全部通过，可以开工")
    return 0


def cmd_rules(a):
    print("""
已硬化的规则（由代码判定，不需要记忆）
""" + "=" * 70)
    print("\n1. 限速 —— 按平台自动判定")
    for k, v in RATE_LIMITS.items():
        print(f"   {k:16} {v['rps']:.4g} req/s   {v['notes']}")
    print("\n2. 证据链 —— 四项必备，缺一拦下")
    for k, v in EVIDENCE_REQUIRED.items():
        print(f"   {k:14} {v}")
    print("\n3. 提交禁令 —— 触发任一即拦截")
    for k, cond, why in SUBMIT_BLOCKS:
        print(f"   {k:16} {cond}")
        print(f"   {'':16} {why}")
    print("\n4. 配额 —— 每批 ≤4 探针、每天 ≤10 假设")
    print("5. 合并 —— 同 root_cause + 同 CWE 应合并报")
    print("6. 情报 —— EPSS>0.5 或 KEV 需三层交叉验证")
    print("\n" + "=" * 70)
    print("""
未硬化（仍靠提问引导，这是留给模型的部分）：
  往哪找、这个根因像什么、要不要换角度、业务语义判断

硬化的边界是「判据」，不是「路径」。
如果连往哪想都硬化了，AI 就退化成脚本执行器。
""")


def cmd_check(a):
    """一次跑完所有闸门"""
    print("=" * 70)
    print(" 全部闸门检查")
    print("=" * 70 + "\n")
    rc = 0
    for name, fn in (("限速", lambda: gate_rate(a)),
                     ("证据链", lambda: gate_evidence(a)),
                     ("情报验证", lambda: gate_intel(a)),
                     ("配额", lambda: gate_quota(a)),
                     ("开工前置", lambda: gate_preflight(a))):
        print(f"──── {name} ────")
        try:
            rc |= fn()
        except SystemExit:
            pass
        except Exception as e:
            print(f"   (跳过: {e})")
        print()
    print("=" * 70)
    print(" [OK] 全部通过" if rc == 0 else " [x] 存在未通过项")
    return rc


def main():
    ap = argparse.ArgumentParser(description="确定性规则硬化引擎：把可判定的规则搬进代码")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("rate", help="限速判定")
    s.add_argument("--platform", default="default")
    s.add_argument("--rps", type=float)
    s.set_defaults(func=gate_rate)

    s = sub.add_parser("evidence", help="证据链完整性")
    s.add_argument("--file")
    s.set_defaults(func=gate_evidence)

    s = sub.add_parser("merge", help="同根因合并判定")
    s.add_argument("--file")
    s.set_defaults(func=gate_merge)

    s = sub.add_parser("intel", help="情报二次源验证")
    s.add_argument("--epss", type=float)
    s.add_argument("--kev", action="store_true")
    s.add_argument("--cve")
    s.add_argument("--src", action="store_true", help="本地源原文已核")
    s.add_argument("--parse", action="store_true", help="解析链路已核")
    s.add_argument("--api", action="store_true", help="官方API已核")
    s.set_defaults(func=gate_intel)

    s = sub.add_parser("quota", help="注意力配额")
    s.add_argument("--add", type=int, default=0)
    s.set_defaults(func=gate_quota)

    s = sub.add_parser("preflight", help="开工前置检查")
    s.add_argument("--scope", action="store_true")
    s.add_argument("--rate", action="store_true")
    s.add_argument("--cred", action="store_true")
    s.add_argument("--interactive", action="store_true")
    s.set_defaults(func=gate_preflight)

    s = sub.add_parser("rules", help="打印所有硬规则")
    s.set_defaults(func=cmd_rules)

    s = sub.add_parser("check", help="一次跑完所有闸门")
    s.add_argument("--platform", default="default")
    s.add_argument("--rps", type=float)
    s.add_argument("--file")
    s.add_argument("--epss", type=float)
    s.add_argument("--kev", action="store_true")
    s.add_argument("--cve")
    s.add_argument("--src", action="store_true")
    s.add_argument("--parse", action="store_true")
    s.add_argument("--api", action="store_true")
    s.add_argument("--scope", action="store_true")
    s.add_argument("--rate", dest="rate_ok", action="store_true")
    s.add_argument("--cred", action="store_true")
    s.add_argument("--interactive", action="store_true")
    s.set_defaults(func=cmd_check)

    a = ap.parse_args()
    sys.exit(a.func(a) or 0)


if __name__ == "__main__":
    main()
