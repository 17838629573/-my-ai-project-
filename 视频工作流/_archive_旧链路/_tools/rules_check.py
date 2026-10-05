#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rules_check.py —— RULES.json 完整性门禁。
列出：未填条目 / 缺证据条目 / 缺顺序条目 / 已登记 bug 数。
退出码 1 = 有未填，禁止据此改代码。
"""
import json, os, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = os.path.join(BASE, "RULES.json")


def load():
    with open(R, encoding="utf-8") as f:
        return json.load(f)


def main():
    D = load()
    unfilled, no_evidence, no_order = [], [], []
    total = 0

    for domain in ("matte", "motion"):
        sec = D.get(domain, {})
        for it in sec.get("候选枚举", []):
            total += 1
            eid = it.get("id", "?")
            name = it.get("name", "?")
            filled = bool(it.get("source")) and bool(it.get("适用")) and bool(it.get("证据"))
            if not filled:
                unfilled.append((domain, eid, name,
                                 "缺 source" if not it.get("source") else
                                 "缺 适用" if not it.get("适用") else "缺 证据"))
            elif not it.get("证据"):
                no_evidence.append((domain, eid, name))
            if filled and not it.get("顺序"):
                no_order.append((domain, eid, name))

    bugs = D.get("bug清单", [])
    pending = [b for b in bugs if b.get("状态") != "done"]

    print("=" * 62)
    print("RULES.json 完整性")
    print("=" * 62)
    print(f"候选条目总数 : {total}")
    print(f"已填         : {total - len(unfilled)}")
    print(f"未填         : {len(unfilled)}")
    print(f"缺顺序       : {len(no_order)}")
    print(f"已登记 bug   : {len(bugs)}  (未修 {len(pending)})")

    if unfilled:
        print("\n--- 未填（禁止据此改代码）---")
        for d, eid, name, why in unfilled:
            print(f"  [{d}] {eid}  {name}   <{why}>")

    if no_order:
        print("\n--- 已填但无执行顺序 ---")
        for d, eid, name in no_order:
            print(f"  [{d}] {eid}  {name}")

    if pending:
        print("\n--- 未修 bug ---")
        for b in pending:
            print(f"  {b.get('id','?')}  {b.get('标题','?')}")
            print(f"      现象: {b.get('现象','-')}")

    # 顺序图自检：被依赖的 id 必须存在
    print("\n--- 顺序图 ---")
    order = D.get("顺序图", [])
    if not order:
        print("  (空)")
    else:
        for step in order:
            dep = step.get("依赖", [])
            print(f"  {step.get('步','?')}  {step.get('动作','?')}")
            if dep:
                print(f"       依赖: {', '.join(dep)}")
            for x in dep:
                if not any(b.get("id") == x for b in bugs):
                    print(f"       [警告] 依赖的 {x} 不在 bug清单 中")

    ok = not unfilled
    print("\n" + ("[PASS] 表已填全，可按顺序改代码" if ok else "[FAIL] 表未填全，禁止改代码"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
