#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dispatch.py —— 唯一决策入口。
从 DISPATCH.json 读规则，按输入字段判定唯一方法。
未命中任何规则 = HALT 报错（禁止 silent fallback）。

用法:
  python3 dispatch.py matte  has_clean_plate=1 camera_locked=1 lighting_stable=1
  python3 dispatch.py motion motion_type=periodic has_skeleton=1
  python3 dispatch.py capacity --grid 8 --per-cell 4
"""
import json, re, os, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES = os.path.join(BASE, "DISPATCH.json")

BOOL_TRUE = {"1", "true", "yes", "y", "on"}
BOOL_FALSE = {"0", "false", "no", "n", "off"}


def load():
    with open(RULES, encoding="utf-8") as f:
        return json.load(f)


def as_bool(v):
    s = str(v).strip().lower()
    if s in BOOL_TRUE:
        return True
    if s in BOOL_FALSE:
        return False
    raise ValueError(f"无法解析为布尔: {v!r}")


def coerce(v):
    """字段值可能是 bool 或字符串枚举。"""
    s = str(v).strip().lower()
    if s in BOOL_TRUE:
        return True
    if s in BOOL_FALSE:
        return False
    return s


def match(when, given):
    """所有条件都满足才算命中。返回 (命中?, 不满足的字段列表)。"""
    miss = []
    for k, want in when.items():
        if k not in given:
            miss.append(f"{k}(未提供)")
            continue
        got = coerce(given[k])
        want_c = coerce(want)
        if isinstance(want_c, bool):
            if got is not want_c:
                miss.append(f"{k}={got}(需{want_c})")
        else:
            if got != want_c:
                miss.append(f"{k}={got}(需{want_c})")
    return (not miss), miss


def run(domain, given):
    R = load()
    if domain not in R:
        print(f"[HALT] 未知域: {domain}")
        print(f"       可用域: {', '.join(k for k in R if k != 'meta')}")
        return 2
    sec = R[domain]
    rules = sorted(sec.get("rules", []), key=lambda r: r.get("priority", 99))

    # 校验输入字段是否合法
    known = set(sec.get("输入字段", {}))
    unknown = [k for k in given if k not in known]
    if unknown:
        print(f"[HALT] 未知输入字段: {', '.join(unknown)}")
        print(f"       本域合法字段: {', '.join(sorted(known))}")
        return 2

    # 枚举校验：无效值直接拦下，不静默落入 HALT
    bad = []
    for k, v in given.items():
        desc = sec["输入字段"].get(k, "")
        m = re.match(r"[\w.\-]+(?:\s*\|\s*[\w.\-]+)+", desc)
        if m:
            allowed = [x.strip() for x in m.group(0).split("|")]
            if v not in allowed:
                bad.append((k, v, allowed))
    if bad:
        print("[HALT] 枚举值非法:")
        for k, v, allowed in bad:
            print(f"       {k}={v}   合法值: {allowed}")
        return 2

    for r in rules:
        ok, miss = match(r["when"], given)
        if ok:
            print(f"[OK] {r['id']} → {r['use']}")
            print(f"     impl : {r['impl']}")
            print(f"     why  : {r['why']}")
            print(f"     src  : {r.get('source','-')}")
            print(f"     verify: {r.get('verify','-')}")
            if r.get("reject"):
                print("     reject:")
                for x in r["reject"]:
                    print(f"       - {x}")
            if r.get("status"):
                print(f"     status: {r['status']}")
            # 未判定字段提醒：命中不等于完备，列出本域其他规则依赖但本次未给的字段
            undetermined = []
            for other in rules:
                if other["id"] == r["id"]:
                    continue
                for k in other["when"]:
                    if k not in given and k not in undetermined:
                        undetermined.append(k)
            if undetermined:
                print(f"\n     [注意] 以下字段未判定，可能影响是否应选更高优先级规则:")
                for k in undetermined:
                    print(f"       - {k}  ({sec['输入字段'].get(k,'')})")
                print("       补齐后重跑，确认无更高优先级规则被跳过。")
            return 0

    # 未命中
    print(f"[HALT] {domain}: 输入未命中任何规则，禁止推测。")
    print(f"       给定: {given}")
    print("       各规则未满足项:")
    for r in rules:
        ok, miss = match(r["when"], given)
        print(f"         {r['id']} ({r['use']}): {', '.join(miss) if miss else '命中'}")
    print("\n       处理: 补齐字段后重试，或新增规则到 DISPATCH.json（需人工审定）。")
    return 1


def capacity(grid, per_cell):
    R = load()
    cap = R["capacity"]
    print(f"定律: {cap['定律']}")
    print(f"来源: {cap['source']}\n")
    eq = grid * per_cell
    print(f"请求: {grid} 格 × 每格 {per_cell} 帧 = 等效 {eq} 帧")
    hit = None
    for row in cap["表"]:
        if row["格子数"] == grid and row["每格帧数"] == per_cell:
            hit = row
    if hit:
        print(f"每帧分辨率: {hit['每帧分辨率']}")
        print(f"判定: {hit['判定']}")
    else:
        print(f"每帧分辨率: 约 1/{per_cell} 幅（格子数 {grid}）")
        print("判定: 未在对照表中，按信息守恒估算")
    print("\n警告:")
    for w in cap["警告"]:
        print(f"  - {w}")
    print(f"\n结论: {cap['结论']}")
    return 0


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        return 2
    if a[0] == "capacity":
        g = p = None
        for x in a[1:]:
            if x.startswith("--grid="):
                g = int(x.split("=", 1)[1])
            elif x.startswith("--per-cell="):
                p = int(x.split("=", 1)[1])
        if g is None or p is None:
            print("用法: dispatch.py capacity --grid=8 --per-cell=4")
            return 2
        return capacity(g, p)

    domain = a[0]
    given = {}
    for x in a[1:]:
        if "=" not in x:
            print(f"[HALT] 参数格式错误: {x}（应为 key=value）")
            return 2
        k, v = x.split("=", 1)
        given[k.strip()] = v.strip()
    return run(domain, given)


if __name__ == "__main__":
    sys.exit(main())
