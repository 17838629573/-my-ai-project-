#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gate_post.py —— 改完代码后必跑。强制三条：
  P1 依赖图同步重生成（改了 import 就必须更新 deps.md / deps.mmd）
  P2 未定义名清零
  P3 体积未超标（超标必须拆，不接受提阈值）

用法:
  python3 _tools/gate_post.py systems_view.py
"""
import os, subprocess, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_LINE, MAX_CHAR = 400, 12000


def run(cmd):
    return subprocess.run(cmd, shell=True, cwd=BASE, capture_output=True, text=True)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        print("用法: python3 _tools/gate_post.py <改过的文件> [...]")
        return 2

    fails = []

    print("=" * 62)
    print("P1 依赖图同步")
    print("=" * 62)
    r = run("python3 _tools/depgraph.py --check")
    if r.returncode != 0:
        print("[漂移] 自动重生成 deps.md / deps.mmd ...")
        r2 = run("python3 _tools/depgraph.py --write")
        print(r2.stdout[-600:] if r2.stdout else "")
        r3 = run("python3 _tools/depgraph.py --check")
        if r3.returncode != 0:
            print("[FAIL] 重生成后仍漂移")
            fails.append("depgraph 重生成失败")
        else:
            print("[PASS] 依赖图已同步（自动重生成）")
    else:
        print("[PASS] 依赖图本就一致")

    print("\n" + "=" * 62)
    print("P1.5 契约对账（reconciliation test）")
    print("=" * 62)
    # 业界依据：Living Documentation「Always Test Consistency」——
    #   每份活文档背后必须有对账测试，分歧时报错而非静默通过。
    #   漂移则自动重生成契约，再验一遍（与 P1 同策略：自动修而非只提醒）。
    r = run("python3 _tools/contract_recon.py")
    if r.returncode != 0:
        print("[漂移] 自动重生成 contracts/ ...")
        r2 = run("python3 _tools/contract_gen.py")
        print((r2.stdout or "").strip()[-300:])
        r3 = run("python3 _tools/contract_recon.py")
        print((r3.stdout or "").strip()[-500:])
        if r3.returncode != 0:
            print("[FAIL] 重生成后契约仍与代码不一致")
            fails.append("contract_recon 对账失败")
        else:
            print("[PASS] 契约已同步（自动重生成）")
    else:
        print("[PASS] 契约本就一致")

    print("\n" + "=" * 62)
    print("P2 未定义名")
    print("=" * 62)
    r = run("python3 _tools/undef_check.py " + " ".join(args))
    out = r.stdout or ""
    head = [l for l in out.split("\n") if l.strip()][:20]
    print("\n".join(head))
    if r.returncode != 0:
        fails.append("存在未定义名")

    print("\n" + "=" * 62)
    print("P3 体积")
    print("=" * 62)
    for f in args:
        p = os.path.join(BASE, f)
        if not os.path.exists(p):
            continue
        src = open(p, encoding="utf-8").read()
        n, c = len(src.split("\n")), len(src)
        bad = n > MAX_LINE or c > MAX_CHAR
        print(f"  {'FAIL' if bad else 'ok  '} {f}: {n}行 / {c}字符")
        if bad:
            fails.append(f"{f} 体积超标，必须拆分（禁止提阈值）")

    print("\n" + "=" * 62)
    if fails:
        print("[FAIL] 未通过:")
        for x in fails:
            print(f"  - {x}")
        print("\n  拆分时: python3 _tools/gate_pre.py <文件>  会给出拆分候选")
        return 1
    print("[PASS] 改动可接受 —— 可标记该步完成")
    print("       下一步: python3 _tools/next_fix.py --done <当前步>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
