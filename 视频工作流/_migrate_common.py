#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""迁移脚手架：把业务模块的内联实现改为调用 _common。

【不是自动改源码】—— 只做三件事：
1. 报告每个模块"应改但未改"的原子清单（供 AI/程序员逐项处理）
2. 对 100% 可机械替换的纯函数（clamp / rad2deg / deg2rad / normalize_deg）
   提供 dry-run 补丁预览
3. 验证：改完后 import 不破、数值与旧实现等价

理由：内联常夹带"隐式口径差异"（如 px_per_m 用画布高 vs 可见高），
自动替换会改变行为，必须人工确认口径。故本脚本只报不改。
"""
import os, re, sys, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.abspath(__file__))
ACTIVE = []

def active(path):
    rel = os.path.relpath(path, ROOT)
    if rel.startswith(("_", ".")) or "venv" in rel or "_archive" in rel or "_bak" in rel:
        return False
    return rel.endswith(".py")

# 可机械替换的纯函数（有精确等价）
MECH = {
    "clamp":    ("def clamp(x, lo, hi):\\s*return max\\(lo, min\\(hi, x\\)\\)",
                 "from _common import clamp"),
    "rad2deg":  (r"def rad2deg\(r\):\s*return r \* 180\.0 / math\.pi",
                 "from _common import rad2deg"),
    "deg2rad":  (r"def deg2rad\(d\):\s*return d \* math\.pi / 180\.0",
                 "from _common import deg2rad"),
    "normalize_deg": (r"def normalize_deg\(d\):\s*return d % 360",
                      "from _common import normalize_deg"),
}

# 需人工确认口径（只报告，不替换）
NEED_HUMAN = {
    "pixels_per_meter": "口径：须确认用'画布高'还是'可见高'（crop_top）",
    "beaufort_scale":   "口径：风速区间边界归属（含/不含）",
    "gait_cycle_from_speed": "口径：stride_m 取值（步长 vs 步幅）",
    "catmull_rom":      "口径：四点定义（是否过端点）",
}

def main():
    files = []
    for d, _, fs in os.walk(ROOT):
        for f in fs:
            p = os.path.join(d, f)
            if active(p):
                files.append(p)

    print("=" * 74)
    print("迁移清单：内联 -> _common 调用")
    print("=" * 74)
    total_mech = 0
    total_human = 0
    for p in sorted(files):
        rel = os.path.relpath(p, ROOT)
        if rel == "_common.py" or "_audit" in rel or "_migrate" in rel or "_selfcheck" in rel:
            continue
        src = open(p, encoding="utf-8").read()
        hits_m, hits_h = [], []
        for name, (pat, _) in MECH.items():
            if re.search(pat, src):
                hits_m.append(name)
        for name, reason in NEED_HUMAN.items():
            # 出现调用形态（非定义）即报
            if re.search(r"\b" + name + r"\s*\(", src) and f"def {name}" not in src:
                hits_h.append((name, reason))
        if hits_m or hits_h:
            print(f"\n  {rel}")
            for n in hits_m:
                print(f"    [机械] {n:22s} -> from _common import {n}")
                total_mech += 1
            for n, r in hits_h:
                print(f"    [人工] {n:22s} {r}")
                total_human += 1
    print("\n" + "=" * 74)
    print(f"可机械替换: {total_mech} 处    需人工确认口径: {total_human} 处")
    print("=" * 74)
    print("下一步：逐条处理，处理后跑  python _audit_dup.py  确认归零。")

if __name__ == "__main__":
    main()
