#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_batch.py —— 分批自检跑批器
==============================
沙盒会超时（全量 validate + check-status 曾 502 中断），故分批处理。

用法:
    python3 run_batch.py active 0     # 活跃层第 0 批（每批 4 个）
    python3 run_batch.py active 1
    python3 run_batch.py active 2
    python3 run_batch.py active 3
    python3 run_batch.py dormant 0    # 休眠层
    ...
    python3 run_batch.py report       # 汇总所有已跑结果

单模块超时（默认 45s）→ 标 TIMEOUT，不卡住，继续下一个。
结果落盘 _batch/<批名>.json，report 汇总。
"""
import json
import os
import subprocess
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "_batch")
TIMEOUT = 45
BATCH_SIZE = 4

# 每个模块的自检入口：优先 __main__ 自检，其次 check_contract
def probe(mod):
    p = os.path.join(BASE, mod + ".py")
    if not os.path.exists(p):
        return ("NOFILE", "文件不存在", -1)
    src = open(p, encoding="utf-8", errors="ignore").read()
    if "def self_check" not in src and "__main__" not in src:
        return ("NO_SELFTEST", "模块无 __main__ 也无 self_check —— "
                "python3 <mod>.py 只会 import 成功即退出，零验证（假PASS）", 0)
    if "def self_check" not in src and "def main()" in src:
        # 有 __main__ 但入口是渲染/主流程，跑它会真渲染
        return ("NO_SELFTEST", "有 __main__ 但入口是主流程（非自检），"
                "跑它会真渲染 -> 需补 self_check()", 0)
    t0 = time.time()
    try:
        r = subprocess.run([sys.executable, p], cwd=BASE,
                           capture_output=True, timeout=TIMEOUT)
        dt = time.time() - t0
        out = (r.stdout.decode("utf-8", "ignore") +
               r.stderr.decode("utf-8", "ignore")).strip()
        if r.returncode != 0:
            return ("FAIL", out, dt)
        if len(out) < 30:
            return ("SUSPECT", "输出过短(%d字符)，疑似未真正自检: %r" % (len(out), out[:60]), dt)
        return ("PASS", out, dt)
    except subprocess.TimeoutExpired:
        return ("TIMEOUT", "超过 %ds 未返回" % TIMEOUT, TIMEOUT)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 0
    group, idx = sys.argv[1], int(sys.argv[2])
    sys.path.insert(0, BASE)
    import enforce
    deps, layer, order, _ = enforce.parse_deps()
    if group == "active":
        mods = [m for m in order if layer.get(m) in enforce.ACTIVE_SECTIONS]
    else:
        mods = [m for m in order if layer.get(m) in enforce.DORMANT_SECTIONS]
    chunk = mods[idx * BATCH_SIZE:(idx + 1) * BATCH_SIZE]
    if not chunk:
        print("批次为空（共 %d 个模块，%d 批）" %
              (len(mods), (len(mods) + BATCH_SIZE - 1) // BATCH_SIZE))
        return 0
    os.makedirs(OUT, exist_ok=True)
    print("=" * 66)
    print("批次 %s/%d  共 %d 个模块 / %d 批" %
          (group, idx, len(mods), (len(mods) + BATCH_SIZE - 1) // BATCH_SIZE))
    print("=" * 66)
    res = {}
    for m in chunk:
        st, out, dt = probe(m)
        res[m] = {"state": st, "sec": round(dt, 1) if dt > 0 else None,
                  "tail": out.splitlines()[-3:] if out else []}
        print(f"  {m:<20} {st:<8} {('%0.1fs' % dt) if dt > 0 else ''}")
        for l in res[m]["tail"]:
            print(f"      | {l[:72]}")
    f = os.path.join(OUT, f"{group}_{idx}.json")
    json.dump(res, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n落盘 {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
