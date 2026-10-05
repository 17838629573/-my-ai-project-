#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""next_step.py —— 流程锁。输出「当前该做哪一个」，禁止凭记忆跳步。

用法:
  python3 _tools/next_step.py            # 输出当前步骤
  python3 _tools/next_step.py --run      # 顺带跑该步验收命令
  python3 _tools/next_step.py --all      # 列出全部
"""
import json, os, subprocess, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASKS = os.path.join(BASE, "TASKS.json")


def load():
    with open(TASKS, encoding="utf-8") as f:
        return json.load(f)


def pick(tasks):
    """第一条 前置全部完成 且 自身未完成 的任务。"""
    done = {t["id"] for t in tasks if t.get("状态") == "done"}
    for t in tasks:
        if t.get("状态") == "done":
            continue
        pre = t.get("前置", [])
        if all(p in done for p in pre):
            return t, [p for p in pre if p not in done]
    return None, []


def show(t, blocked):
    print("=" * 60)
    print(f"当前步骤: {t['id']}  {t['title']}")
    print("=" * 60)
    print(f"why : {t['why']}")
    if t.get("前置"):
        print(f"前置: {', '.join(t['前置']) or '无'}")
    print(f"\n该读:")
    for f in t.get("读", []):
        print(f"  - {f}")
    if t.get("改"):
        print(f"\n该改:")
        for f in t["改"]:
            print(f"  - {f}")
    print(f"\n验收命令:")
    print(f"  {t['验收']}")
    print(f"期望: {t['期望']}")
    if blocked:
        print(f"\n[HALT] 前置未完成: {', '.join(blocked)}")
    print("\n改完后跑: python3 _tools/next_step.py --run  # 通过才解锁下一步")


def main():
    a = sys.argv[1:]
    R = load()
    tasks = R["tasks"]

    if "--all" in a:
        for t in tasks:
            mark = "[x]" if t.get("状态") == "done" else "[ ]"
            print(f"{mark} {t['id']}  {t['title']}")
            print(f"      前置={','.join(t.get('前置',[])) or '无'}  验收: {t['验收']}")
        return 0

    t, blocked = pick(tasks)
    if t is None:
        print("[DONE] 无可执行步骤：全部完成，或全部被未完成的前置阻塞。")
        for x in tasks:
            if x.get("状态") != "done":
                miss = [p for p in x.get("前置", [])
                        if all(q["id"] != p or q.get("状态") != "done" for q in tasks)]
                if miss:
                    print(f"  {x['id']} 阻塞于 {', '.join(miss)}")
        return 1

    show(t, blocked)

    if "--run" in a:
        print("\n" + "-" * 60)
        print("执行验收命令:")
        print(f"$ {t['验收']}")
        print("-" * 60)
        rc = subprocess.call(t["验收"], shell=True, cwd=BASE)
        print("-" * 60)
        if rc == 0:
            print(f"[PASS] {t['id']} 验收通过 —— 可推进下一步")
            print("       如需标记完成，人工确认后改 TASKS.json 状态为 done")
        else:
            print(f"[FAIL] {t['id']} 验收未通过（退出码 {rc}）—— 不得推进")
        return rc
    return 0


if __name__ == "__main__":
    sys.exit(main())
