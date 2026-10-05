#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""next_fix.py —— 一次只给一个改动方案。禁止自行挑活、禁止并行改多处。

用法:
  python3 _tools/next_fix.py             # 输出当前唯一该做的一步
  python3 _tools/next_fix.py --done B5   # 标记完成，解锁下一步
  python3 _tools/next_fix.py --list      # 列出全部及依赖
"""
import json, os, subprocess, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = os.path.join(BASE, "RULES.json")
PROG = os.path.join(BASE, "PROGRESS.json")


def load():
    return json.load(open(R, encoding="utf-8"))


def load_prog():
    if os.path.exists(PROG):
        return json.load(open(PROG, encoding="utf-8"))
    return {"done": []}


def save_prog(p):
    json.dump(p, open(PROG, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def main():
    a = sys.argv[1:]
    D = load()
    # 顺序图分域存放：顶层是 matte/合成域，interaction 域自带 9 步。
    # 两域都读，否则 interaction 的步骤永远排不进来（曾导致 X_g 起一直报 DONE）。
    order = list(D["顺序图"])
    for dom in ("interaction", "motion"):
        sec = D.get(dom)
        if isinstance(sec, dict) and "顺序图" in sec:
            for it in sec["顺序图"]:
                order.append({"步": it["id"], "动作": it["name"],
                              "依赖": [it["依赖"]] if it.get("依赖") not in (None, "-", "") else [],
                              "业界怎么做": it.get("证据", "")[:120],
                              "该读": [], "改": [it.get("改", "")],
                              "验收": it.get("验收", "")})
    prog = load_prog()

    if "--list" in a:
        for s in order:
            mark = "[x]" if s["步"] in prog["done"] else "[ ]"
            dep = ",".join(s.get("依赖", [])) or "-"
            print(f"{mark} {s['步']:<4} 依赖={dep:<8} {s['动作']}")
        return 0

    if "--done" in a:
        i = a.index("--done")
        step = a[i + 1]
        if step not in prog["done"]:
            prog["done"].append(step)
            save_prog(prog)
        print(f"[OK] 已标记完成: {step}")
        print(f"     已完成: {', '.join(prog['done'])}")
        return 0

    # 找当前步：依赖全部完成 且 自身未完成
    for s in order:
        if s["步"] in prog["done"]:
            continue
        dep = s.get("依赖", [])
        if all(d in prog["done"] for d in dep):
            print("=" * 62)
            print(f"当前唯一该做的一步: {s['步']}")
            print("=" * 62)
            print(f"\n动作: {s['动作']}")
            print(f"\n业界怎么做:")
            print(f"  {s['业界']}")
            print(f"\n该读:")
            for f in s.get("读", []):
                print(f"  - {f}")
            print(f"\n该改（只改这些，不得扩散）:")
            for f in s.get("改", []):
                print(f"  - {f}")
            print(f"\n" + "-" * 62)
            print("强制流程（三步，缺一不可）:")
            print("-" * 62)
            files = " ".join(s.get("改", []))
            print(f"  1) 改前: python3 _tools/gate_pre.py {files}")
            print(f"       -> 依赖图漂移检查 + 打印上下游 + 体积检查")
            print(f"       -> 不通过就不许动手")
            print(f"  2) 按上面的『业界怎么做』改，只改列出的文件")
            print(f"  3) 改后: python3 _tools/gate_post.py {files}")
            print(f"       -> 自动重生成依赖图 + 未定义名清零 + 体积检查")
            print(f"\n  4) 通过后: python3 _tools/next_fix.py --done {s['步']}")
            print(f"\n（原验收命令: {s['验收']}）")
            return 0

    print("[DONE] 全部步骤完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
