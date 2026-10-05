#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""plan_next —— 工作安排的单一驱动入口。

铁律：
  1. 一次只吐【一步】，禁止一次改多处
  2. 依赖未 done 的步骤不解锁
  3. 阶段 A 没走完不许进 B；A+B 没走完不许进 C
  4. --done 只改 status，验收命令由 operator 自己跑（本工具不代跑，
     因为验收脚本各步不同，代跑会变成"自动通过"）

用法:
  python3 plan_next.py                 # 显示下一步
  python3 plan_next.py --done P12      # 标记完成
  python3 plan_next.py --all           # 显示全表
"""
import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAN = os.path.join(_HERE, "WORKPLAN.json")

PHASE_ORDER = ["A_代码错误", "B_图表重生成", "C_循环验证"]


def load():
    with open(PLAN, encoding="utf-8") as f:
        return json.load(f)


def save(p):
    with open(PLAN, "w", encoding="utf-8") as f:
        json.dump(p, f, ensure_ascii=False, indent=2)


def done_ids(p):
    return {s["id"] for s in p["步骤"] if s.get("状态") == "完成"}


def unlocked(p):
    d = done_ids(p)
    out = []
    for s in p["步骤"]:
        if s.get("状态") == "完成":
            continue
        if all(x in d for x in s["依赖"]):
            out.append(s)
    return out


def phase_blocked(p, ph):
    """前序阶段是否还有未完成的步骤。"""
    idx = PHASE_ORDER.index(ph)
    for prev in PHASE_ORDER[:idx]:
        if any(s["阶段"] == prev and s.get("状态") != "完成"
               for s in p["步骤"]):
            return prev
    return None


def show(s, n_total):
    print("=" * 62)
    print("当前一步: [%s] %s  (%s)" % (s["阶段"], s["id"], s["名"]))
    print("=" * 62)
    print("根因  : %s" % s["根因"])
    if s.get("业界"):
        print("业界  : %s" % s["业界"])
    if s.get("教训"):
        print("教训  : %s" % s["教训"])
    if s.get("依赖"):
        print("依赖  : %s（已满足）" % ", ".join(s["依赖"]))
    print("只改  : %s" % ", ".join(s["改"]))
    print("验收  : %s" % s["验收"])
    print("-" * 62)
    print("做完先自己跑验收命令，通过再执行：")
    print("  python3 plan_next.py --done %s" % s["id"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--done")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    p = load()

    if a.done:
        hit = [s for s in p["步骤"] if s["id"] == a.done]
        if not hit:
            print("FAIL 无此步骤: %s" % a.done)
            return 1
        s = hit[0]
        miss = [x for x in s["依赖"] if x not in done_ids(p)]
        if miss:
            print("FAIL %s 的依赖未完成: %s —— 不许跳步" % (a.done, miss))
            return 1
        s["状态"] = "完成"
        save(p)
        print("OK %s 已标记完成" % a.done)
        return 0

    if a.all:
        d = done_ids(p)
        for ph in PHASE_ORDER:
            print("\n【%s】%s" % (ph, p["阶段"][ph]["目的"]))
            for s in p["步骤"]:
                if s["阶段"] != ph:
                    continue
                mark = "[x]" if s["id"] in d else "[ ]"
                dep = ",".join(s["依赖"]) or "-"
                print("  %s %-4s 依赖=%-14s %s" % (mark, s["id"], dep, s["名"]))
        return 0

    cand = unlocked(p)
    if not cand:
        print("全部完成")
        return 0
    # 按阶段顺序 + 序 取第一个
    cand.sort(key=lambda s: (PHASE_ORDER.index(s["阶段"]), s["序"]))
    nxt = cand[0]
    blk = phase_blocked(p, nxt["阶段"])
    if blk:
        left = [s["id"] for s in p["步骤"]
                if s["阶段"] == blk and s.get("状态") != "完成"]
        print("BLOCKED 阶段 %s 未完成，不许进 %s" % (blk, nxt["阶段"]))
        print("  剩余: %s" % ", ".join(left))
        print("  理由: %s" % p["阶段"][nxt["阶段"]].get("依赖", ""))
        return 1
    show(nxt, len(p["步骤"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
