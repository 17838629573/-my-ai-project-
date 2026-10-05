#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""interaction_gen.py —— 交互域规则表的建表与校验。

核心抽象（业界统一）：交互 = 接触事件 ContactEvent
  事件 e = (a, b, kind, [ts, te])
    a, b : 接触的两方（部位/角色/地面/物体）
    kind : contact 距离≈0 / separation 距离>阈值 / support 支撑
           / slip 滑移 / impact 冲击 / balance 平衡
    [ts,te] : 接触持续的时间区间（duration = te - ts）
  来源：InterControl 的 contact_list/separation_list/contact_bound；
        接触网络的形式化定义 contact=(u,v) + event=(u,v,ts,te)

用法: python3 _tools/interaction_gen.py check
"""
import json, os, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = os.path.join(BASE, "RULES.json")

# 输入维度：判定"这条规则适用不适用"只看这些（枚举，不允许自由文本）
DIMS = {
    "pair": ["角色-地面", "角色-角色", "角色-物体", "角色-自身"],
    "kind": ["support", "contact", "separation", "slip", "impact", "balance", "one-shot"],
    "periodic": ["周期", "一次性"],
}
# 输出字段：不是判定条件，而是"命中后该用什么解法"。
# 放在输入空间里枚举是错的 —— 那会让每个 pair/kind 只覆盖 1/6 组合，制造假空洞。
OUT_FIELD = "solve"
OUT_VALUES = ["IK锁定", "准物理解算", "空间约束优化", "ZMP投影", "动画资源", "参数判据"]
REQUIRED = ["id", "name", "pair", "kind", "periodic", "solve",
            "detect", "已有实现", "状态", "证据", "cond"]
VALID_STATE = ["已有", "部分", "缺失"]


def load():
    return json.load(open(R, encoding="utf-8"))


def check():
    D = load()
    if "interaction" not in D:
        print("[FAIL] RULES.json 无 interaction 域"); return 1
    sec = D["interaction"]
    items = sec["候选枚举"] if "候选枚举" in sec else sec
    fails, warns = [], []

    seen = {}
    for it in items:
        rid = it.get("id")
        if rid in seen:
            fails.append(f"{rid} 重复")
        seen[rid] = 1
        for k in REQUIRED:
            if k not in it or it[k] in ("", None, []):
                fails.append(f"{rid} 缺 {k}")
        if it.get("状态") not in VALID_STATE:
            fails.append(f"{rid} 状态非法: {it.get('状态')}")
        c = it.get("cond") or {}
        for k, v in c.items():
            if k not in DIMS:
                fails.append(f"{rid}.cond.{k} 未知维度"); continue
            vs = v if isinstance(v, list) else [v]
            for x in vs:
                if x != "任意" and x not in DIMS[k]:
                    fails.append(f"{rid}.cond.{k}={x} 非枚举值")
        # cond 必须覆盖全部输入维度，否则无法判定
        for k in DIMS:
            if k not in c:
                fails.append(f"{rid}.cond 缺维度 {k}")
        if OUT_FIELD in c:
            fails.append(f"{rid}.cond 不应含输出字段 {OUT_FIELD}")
        # cross-check: cond.pair 与顶层 pair 字段要一致
        if c.get("pair") and it.get("pair") and c["pair"] != it["pair"]:
            fails.append(f"{rid} pair 与 cond.pair 不一致")

    print("=" * 60)
    print("interaction 域校验")
    print("=" * 60)
    print(f"条目数: {len(items)}")
    from collections import Counter
    print("状态分布:", dict(Counter(i.get("状态") for i in items)))
    print("pair 分布:", dict(Counter(i.get("pair") for i in items)))
    if fails:
        print("\n[FAIL]")
        for f in fails:
            print("  " + f)
        return 1
    # 重合检查：同一输入组合命中多条 = 无裁决
    import itertools
    keys = list(DIMS)
    combos = list(itertools.product(*[DIMS[k] for k in keys]))
    clash = []
    for c in combos:
        ctx = dict(zip(keys, c))
        hit = []
        for it in items:
            cd = it.get("cond") or {}
            okk = True
            for k, want in cd.items():
                if k not in DIMS: continue
                if want == "任意" or (isinstance(want, list) and "任意" in want):
                    continue
                allow = want if isinstance(want, list) else [want]
                if ctx.get(k) not in allow:
                    okk = False; break
            if okk: hit.append((it["id"], it.get("solve")))
        if len(hit) > 1:
            clash.append((ctx, hit))
    ruled = {tuple(r.get("候选", []))
             for r in D.get("dispatch", {}).get("裁决", [])}
    unresolved = []
    for ctx, hit in clash:
        ids = tuple(h[0] for h in hit)
        if ids in ruled:
            print(f"  [已裁决] {ctx} -> {hit}")
        else:
            unresolved.append((ctx, hit))
    if unresolved:
        print(f"\n[重合] 未裁决: {len(unresolved)} 处")
        for ctx, hit in unresolved[:6]:
            print(f"  {ctx} -> {hit}")
        return 1

    print("\n[PASS] interaction 域自洽（无重合）")
    return 0


if __name__ == "__main__":
    sys.exit(check())
